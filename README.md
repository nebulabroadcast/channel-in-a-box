# Nebula in a Box

A single-machine [Nebula](https://github.com/nebulabroadcast/nebula) deployment
that runs the whole broadcast chain - media asset management, scheduling,
import/conversion and a [CasparCG](https://github.com/CasparCG/server) playout
engine - from one `docker compose` stack.

The main idea of this stack is **channel-in-a-box**: production storage and
playout storage are the *same directory*. Media is imported once, straight into
the folder CasparCG plays from. There is no separate playout server, no copy
step and no PSM service.

- [Stack overview](#stack-overview)
- [Quick start](#quick-start)
- [Channel-in-a-box: colocated production and playout storage](#channel-in-a-box-colocated-production-and-playout-storage)
  - [Why it matters](#why-it-matters)
  - [The PSM service is not needed](#the-psm-service-is-not-needed)
  - [How the paths line up](#how-the-paths-line-up)
  - [Configuring CasparCG](#configuring-casparcg)
  - [CasparCG running outside docker](#casparcg-running-outside-docker)
  - [Checklist](#checklist)
  - [Troubleshooting](#troubleshooting)
- [Hardware output and GPU](#hardware-output-and-gpu)
- [Repository layout](#repository-layout)

## Stack overview

| Service        | Purpose                                                                   |
| -------------- | ------------------------------------------------------------------------- |
| `postgres`     | Nebula database                                                           |
| `redis`        | Messaging between Nebula components                                       |
| `setup`        | One-shot job: creates the DB schema and loads `./settings`                |
| `server`       | Nebula backend + web UI (3 replicas)                                      |
| `worker`       | Nebula services: broker, meta, **play**, import, conv (see `settings/services.py`) |
| `casparcg`     | Playout engine, controlled by the `play` service over AMCP (`:5250`)      |
| `loadbalancer` | Caddy, HTTPS on `:4455`, proxies to `server`                              |

`worker` has a static IP (`172.28.0.10`) because CasparCG's predefined OSC
clients cannot use hostnames.

## Quick start

```sh
cp .env.example .env        # set NEBULA_HOST to the IP/hostname clients use
docker compose up -d
```

Open `https://<NEBULA_HOST>:4455` and log in as `admin` / `nebula` (change the
password). Caddy uses its own internal CA (`tls internal`), so your browser will
warn until you trust it; the CA is kept in the `caddy_data` volume, so you only
do this once.

`.env.example` also enables `compose.dev.yml`, which mounts local checkouts of
`nebula-server/` and `nebula-worker/` over the code baked into the images. If
you just want to run the published images, remove the `COMPOSE_FILE` and
`NEBULA_*_PATH` lines from your `.env`.

Everything persistent lives in `./storage` (media, imports, CasparCG data and
templates) and the `db` volume.

## Channel-in-a-box: colocated production and playout storage

### Why it matters

Classic Nebula assumes a *production* storage (where assets are ingested,
edited and browsed) and a separate *playout* storage on the playout server.
Before an item can air, a PSM (playout storage manager) service copies it - and
a `conv` action transcodes it - into the channel's playout storage. Readiness is
tracked per channel in the `playout_status/<id_channel>` asset metadata.

In channel-in-a-box that whole step disappears. Assets are imported directly
into the directory CasparCG uses as its media path. As soon as an asset is
**online**, it is **playable**.

This is a fast path that is chosen per asset. An asset is *colocated* with a
channel when both of these are true:

1. `asset["id_storage"] == channel.playout_storage`
2. the asset's `path` lies under `channel.playout_dir`

For a colocated asset:

- the `play` service cues it straight from its own path (relative to
  `playout_dir`, without extension), based only on the asset's own status;
- the rundown derives the row status from the asset status, not from
  `playout_status/<id_channel>`.

Assets that don't meet the conditions still use the classic copy-based flow.

### The PSM service is not needed

**Do not run a `psm` service in this setup.** `settings/services.py` deliberately
lists only `broker`, `meta`, `play`, `import` and `conv`.

There is nothing for PSM to do: there is no second copy of the file to create
or track. (PSM skips colocated assets, so it would be harmless for them - but it
would still consume a service slot and it would try to transfer any asset that
is *not* under the playout dir.)

If you later mix in assets that live outside the playout dir, those are no
longer colocated and need PSM and a conversion action like in a classic setup.

### How the paths line up

Three independent path definitions must describe the same physical directory:

| Where                                  | Setting                                | Value in this repo           |
| -------------------------------------- | -------------------------------------- | ---------------------------- |
| `settings/storages.py`                 | storage `path` (as seen by Nebula)     | `/mnt/nebula_01`             |
| `settings/channels.py`                 | `playout_storage` / `playout_dir`      | `1` / `media.dir`            |
| `casparcg.config`                      | `<media-path>` (as seen by CasparCG)   | `/storage/media.dir`         |

and, on the Nebula side, new assets must be created *inside* the playout dir.
This is done by the asset validator in `plugins/validator/asset.py`:

```python
asset["id_storage"] = 1
asset["path"] = f"media.dir/{subdir}/{asset['id/main']}.mxf"
```

The rule that ties everything together:

> **CasparCG's `<media-path>` must be the directory
> `<storage path>/<playout_dir>`** - the same files, whatever path each side
> mounts them at.

In this repo `./storage` is mounted into the Nebula containers as
`/mnt/nebula_01` and into CasparCG as `/storage`:

```
host:      ./storage/media.dir/movies/00001a.mxf
nebula:    /mnt/nebula_01/media.dir/movies/00001a.mxf   (storage path + asset path)
casparcg:  /storage/media.dir/movies/00001a.mxf         (media-path + clip name)
```

The `play` service tells CasparCG to load the clip name
`movies/00001a` - the asset path relative to `playout_dir`, minus the
extension. CasparCG resolves that against its `<media-path>`, so the two sides
never need to agree on the absolute path, only on the directory.

### Configuring CasparCG

**1. Nebula channel** (`settings/channels.py`):

```python
channel1 = PlayoutChannelSettings(
    id=1,
    ...
    playout_storage=1,          # id of the storage below
    playout_dir="media.dir",    # directory inside that storage
    playout_container="mxf",
    config={
        "caspar_host": "casparcg",
        "caspar_port": 5250,
        "caspar_osc_port": 6251,
        "caspar_channel": 1,
        "caspar_feed_layer": 10,
    },
)
```

**2. Nebula storage** (`settings/storages.py`) - `path` is the mount point of the
shared directory inside the Nebula containers:

```python
StorageSettings(id=1, name="production", protocol="local", path="/mnt/nebula_01")
```

**3. CasparCG** (`casparcg.config`) - `media-path` is `<storage>/<playout_dir>`
as CasparCG sees it:

```xml
<paths>
    <media-path>/storage/media.dir</media-path>      <!-- = playout_dir -->
    <template-path>/storage/template.dir</template-path>
    <data-path>/storage/data.dir</data-path>
    <log-path disable="true">/storage/log.dir</log-path>
</paths>
```

Only `media-path` has to match `playout_dir`. `template-path`, `data-path` and
`log-path` are just conveniently placed in the same storage root here; they
don't have to be.

**4. Docker volume** (`compose.yml`) - both containers mount the same host
directory:

```yaml
worker:
  volumes:
    - "./storage:/mnt/nebula_01"
casparcg:
  volumes:
    - ./casparcg.config:/opt/casparcg/casparcg.config
    - ./storage:/storage
```

If you change `playout_dir` (say, to `playout.dir`), change `<media-path>` to
`/storage/playout.dir` and the validator's `asset["path"]` prefix to match.

### CasparCG running outside docker

The docker setup is a convenience, not a requirement. CasparCG can run
stand-alone - on the host, in a VM or on a dedicated playout machine - as long as
it sees the **same directory** Nebula writes assets to.

- **Same machine, no docker for CasparCG:** point `<media-path>` at the host
  path of the shared directory. With this repo's layout that is
  `/path/to/nebula-in-a-box/storage/media.dir`. Keep the Nebula containers'
  storage mount as it is.
- **Different machine:** export the storage over NFS/SMB and mount it on the
  CasparCG host, then point `<media-path>` at `<mount>/media.dir`. The Nebula
  storage `path` stays whatever it is on the Nebula side. Whichever way it is
  mounted, both must be the same files.
- **Other Nebula paths:** if your storage lives elsewhere, set the storage `path`
  to that mount point in the Nebula containers and adjust `playout_dir` if the
  media directory is not called `media.dir`.

Then update the channel's `config` in `settings/channels.py` so the `play`
service can reach it:

```python
config={
    "caspar_host": "192.168.1.50",   # hostname/IP of the CasparCG machine
    "caspar_port": 5250,             # AMCP
    "caspar_osc_port": 6251,         # must match <predefined-client> port
    ...
}
```

and in `casparcg.config`, make CasparCG send OSC to the `worker` (which runs the
`play` service) - use its reachable IP or, in docker, the static
`172.28.0.10`:

```xml
<osc>
  <predefined-clients>
    <predefined-client>
      <address>WORKER_IP</address>
      <port>6251</port>
    </predefined-client>
  </predefined-clients>
</osc>
```

### Checklist

- [ ] The storage that holds `playout_dir` is the channel's `playout_storage`.
- [ ] New assets get `id_storage == playout_storage` and a `path` that starts
      with `playout_dir` (`plugins/validator/asset.py`).
- [ ] The import action targets the same storage
      (`settings/actions/import.xml`, `<id_storage>`) and outputs a container
      CasparCG can play (`playout_container`, here `mxf`).
- [ ] CasparCG `<media-path>` is the same physical directory as
      `<storage path>/<playout_dir>`.
- [ ] No `psm` entry in `settings/services.py`.

**Files must be playable as they are.** Since nothing transcodes or renames the
file for playout, the import profile has to produce media that is already
correct for the channel: format and frame rate matching the channel, normalized
loudness, and a filename that is safe to use as a CasparCG clip name. Uploads
land in `import.dir`, which is *outside* the playout dir, and the import job
writes into `.nx/creating` before moving the finished file into its final
location, so CasparCG never sees half-written files.

### Troubleshooting

**"Unable to cue OFFLINE playout file"** - the asset is not colocated (or is not
online). Check that `id_storage` and `path` are as described above; a path like
`import.dir/foo.mxf` is outside `playout_dir` and falls back to the PSM flow.

**Cue succeeds in Nebula but CasparCG reports a missing clip** - the
`<media-path>` and the Nebula storage don't point at the same directory. From
inside each container, check that the file is where you expect:

```sh
docker compose exec worker ls /mnt/nebula_01/media.dir/movies/
docker compose exec casparcg ls /storage/media.dir/movies/
```

**Assets never turn playable** - check that the asset is `ONLINE` (the import
job finished) rather than `OFFLINE`. Only `ONLINE` and `CREATING` assets are cued.

## Hardware output and GPU

Optional compose overrides, add them to `COMPOSE_FILE`:

```sh
# .env
COMPOSE_FILE=compose.yml:compose.nvidia.yml           # NVIDIA GPU (via CDI)
COMPOSE_FILE=compose.yml:compose.blackmagic.yml       # DeckLink output
```

- `compose.nvidia.yml` passes `nvidia.com/gpu=all` to CasparCG.
- `compose.blackmagic.yml` mounts the host's DeckLink libraries
  (`/usr/lib/libDeckLinkAPI.so`, `libDeckLinkPreviewAPI.so`) and `/dev/blackmagic`.
  Add a `<decklink>` consumer to `casparcg.config`.

`compose.yml` gives CasparCG `/dev/dri` by default (software / Intel / AMD).

For a preview stream, uncomment the `mediamtx` service in `compose.yml` and the
`<ffmpeg>` consumer in `casparcg.config`; `mediamtx.yml` configures the UDP
MPEG-TS ingest and serves it over HLS/WebRTC.

## Repository layout

```
compose.yml               core stack
compose.dev.yml           dev override: mount local nebula-server / nebula-worker
compose.nvidia.yml        NVIDIA GPU for CasparCG
compose.blackmagic.yml    DeckLink for CasparCG
casparcg.config           CasparCG configuration (media-path is the key setting)
Caddyfile                 HTTPS load balancer
mediamtx.yml              optional preview stream
settings/                 Nebula settings, loaded by the `setup` job
  channels.py             playout channel (playout_storage, playout_dir, caspar_*)
  storages.py             storage definitions
  services.py             worker services (note: no PSM)
  actions/                import / proxy conversion actions
plugins/validator/        asset validator, places new assets under the playout dir
storage/                  shared media directory (mounted in Nebula and CasparCG)
  media.dir/              CasparCG media-path AND Nebula asset storage
  import.dir/             upload / import drop folder
  template.dir/           CasparCG HTML templates
  fonts.dir/              fonts used by proxy generation
```
