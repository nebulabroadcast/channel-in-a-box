# Nebula in a Box

A complete TV channel on one machine: media asset management, ingest and
transcoding, scheduling and a [CasparCG](https://github.com/CasparCG/server)
playout server, all started with a single `docker compose up`.

It is built on [Nebula](https://nebulabroadcast.com), an open source broadcast
automation system. The stack works out of the box. You can upload a video,
put it in the schedule and watch it on air in your browser within minutes.

- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Your first broadcast](#your-first-broadcast)
- [Watching the output](#watching-the-output)
- [Everyday operation](#everyday-operation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [How it works](#how-it-works)
- [Repository layout](#repository-layout)

## Requirements

- Linux with [Docker](https://docs.docker.com/engine/install/) and the Docker
  Compose plugin
- A few GB of free disk space for media (all files live in `./storage`)
- Free ports `4443` (web interface, HTTPS), `4455` (web interface, plain HTTP),
  `8888` (preview stream) and `5250` (CasparCG)

## Quick start

```sh
git clone <this repository> nebula-in-a-box
cd nebula-in-a-box
docker compose up -d
```

The first start downloads the images and sets up the database, which takes a
minute or two. Then:

1. Open **<https://localhost:4443>**.
2. Your browser warns that the connection is not private. This is expected.
   The stack uses a self-signed certificate, so accept it (*Advanced →
   Proceed to localhost*). You only have to do this once.
3. Log in with username **`admin`** and password **`nebula`**.

Change the admin password after you log in for the first time.

No `.env` file is needed. For access from other computers, see
[Configuration](#configuration).

The same interface is also served over plain HTTP at <http://localhost:4455>,
with no certificate and no redirect. It is meant for development (for example
behind the Vite dev server). Use HTTPS for normal work.

## Your first broadcast

For a full guide to the web interface, see the
**[Nebula documentation](https://docs.nebulabroadcast.com)**. In short:

### 1. Create an asset

An *asset* is a media item (a movie, episode, jingle, commercial and so on)
together with its metadata. In the web interface, create a new asset, pick a
folder (for example *Movie*), give it a title and save it.

The new asset has no media file yet, so it shows as **offline**.

### 2. Upload a media file

Open the asset and upload a video file from your computer through the web
interface. Nearly any common format works (MP4, MOV, MXF, MKV...).

### 3. Wait for transcoding

Nebula transcodes the upload to the channel's production format,
**XDCAM HD 422 50 Mbps, 1080i50**, and stores it where the playout server can
play it directly. It also generates a low-resolution proxy for previewing in
the browser.

When transcoding finishes, the asset turns **online** and is ready to air.
Transcoding can take a while for long files. The job progress is shown in the
web interface.

### 4. Schedule it

- In the **Scheduler**, create a programme block for *Channel 1* (movies and
  episodes can be dragged straight into the scheduler).
- In the **Rundown**, add or adjust the items that should play within the
  block: your asset, plus any jingles, trailers and so on.

### 5. Play it out

In the rundown, cue the item and take it on air. Once it is running, playout
follows the rundown automatically.

## Watching the output

Open **<http://localhost:8888/live>** in your browser to watch what the channel
is playing. This is a preview stream (720p H.264 over HLS) that CasparCG
generates and [mediamtx](https://github.com/bluenviron/mediamtx) serves. It
lags a few seconds behind the actual output.

For lower latency, open **`rtsp://localhost:8554/live`** in a player such as
VLC or ffplay.

The stream only exists while CasparCG is running. If nothing is on air, you see
black.

To send real SDI output through a Blackmagic DeckLink card, see
[Hardware output and GPU](#hardware-output-and-gpu).

## Everyday operation

```sh
docker compose up -d          # start (or apply changes)
docker compose down           # stop
docker compose logs -f worker # follow ingest / transcoding / playout logs
docker compose ps             # service status

make setup                    # apply changes in ./settings (restarts server and worker)
make update                   # pull the latest Nebula / CasparCG images and recreate the stack
```

Your data survives restarts:

- **Media files** are in `./storage/media.dir`, sorted into subfolders
  (`movies/`, `episodes/`...).
- **Uploads** in progress are in `./storage/import.dir`.
- **The database** (assets, metadata, schedule, users) is in the `db` docker
  volume.

To start over from scratch, run `docker compose down -v` and delete the media
files from `./storage/media.dir`. Keep the directory itself.

## Configuration

There is little to configure. All settings are optional and go into a `.env`
file next to `compose.yml` (see `.env.example`).

### Access from other computers

By default the web interface's certificate is issued for `localhost`. To use
Nebula from other machines on your network, set the address they will use:

```sh
# .env
NEBULA_HOST=192.168.1.20
```

Then run `docker compose up -d` and open `https://192.168.1.20:4443`. The
preview stream is at `http://192.168.1.20:8888/live`.

### Hardware output and GPU

Optional compose overrides, enabled with `COMPOSE_FILE` in `.env`:

```sh
COMPOSE_FILE=compose.yml:compose.nvidia.yml           # NVIDIA GPU for CasparCG (via CDI)
COMPOSE_FILE=compose.yml:compose.blackmagic.yml       # Blackmagic DeckLink output
```

- `compose.nvidia.yml` passes `nvidia.com/gpu=all` to CasparCG.
- `compose.blackmagic.yml` mounts the host's DeckLink libraries
  (`/usr/lib/libDeckLinkAPI.so`, `libDeckLinkPreviewAPI.so`) and
  `/dev/blackmagic`. Also uncomment the `<decklink>` consumer in
  `casparcg.config`.

Without an override, CasparCG gets `/dev/dri` (software rendering, Intel or
AMD GPU).

### Channel format

The channel runs at **1080i50**. The import profile
(`settings/actions/import.xml`, `xdcamhd422-1080i50`) and the CasparCG video
mode (`casparcg.config`, `1080i5000`) must match. Change both together if you
need a different format.

### Development

To run local checkouts of `nebula-server` and `nebula-worker` instead of the
code baked into the images, uncomment the development lines in `.env.example`
and copy them into `.env`. This enables `compose.dev.yml`.

## Troubleshooting

**The browser refuses the certificate / keeps warning.** The certificate is
issued by Caddy's internal CA and is kept in the `caddy_data` volume. If you
changed `NEBULA_HOST`, open the new address and accept the certificate again.

**The asset stays offline after upload.** Transcoding is still running or has
failed. Check the job status in the web interface and look at
`docker compose logs -f worker`.

**"Unable to cue OFFLINE playout file".** The asset is not online yet, or its
file is outside `media.dir`. See [How it works](#how-it-works).

**Nebula cues the item but CasparCG reports a missing clip.** Check that the
file is visible from both sides:

```sh
docker compose exec worker   ls /mnt/nebula_01/media.dir/movies/
docker compose exec casparcg ls /storage/media.dir/movies/
```

**`localhost:8888/live` shows nothing.** Check that `mediamtx` and `casparcg`
are running (`docker compose ps`), then look at
`docker compose logs casparcg mediamtx`.

## How it works

### Services

| Service        | Purpose                                                                   |
| -------------- | ------------------------------------------------------------------------- |
| `postgres`     | Nebula database                                                           |
| `redis`        | Messaging between Nebula components                                       |
| `setup`        | One-shot job: creates the DB schema and loads `./settings`                |
| `server`       | Nebula backend + web UI (3 replicas)                                      |
| `worker`       | Nebula services: broker, meta, **play**, import, conv (see `settings/services.py`) |
| `casparcg`     | Playout engine, controlled by the `play` service over AMCP (`:5250`)      |
| `mediamtx`     | Serves CasparCG's preview stream as HLS on `:8888` and RTSP on `:8554`    |
| `loadbalancer` | Caddy, HTTPS on `:4443` and plain HTTP on `:4455`, proxies to `server`    |

`worker` has a static IP (`172.44.0.10`) because CasparCG sends OSC status
messages to it, and CasparCG's predefined OSC clients cannot use hostnames.

### Channel-in-a-box: one storage for production and playout

Classic Nebula uses separate *production* storage (where assets are ingested
and browsed) and *playout* storage on the playout server. A PSM (playout
storage manager) service copies each item to playout storage before it can air.

This stack drops that step: **production storage and playout storage are the
same directory**. Uploads are transcoded once, straight into the folder
CasparCG plays from, so an asset is playable as soon as it is online. There is
no copy step and no PSM service.

An asset is *colocated* with the channel (and takes this fast path) when:

1. `asset["id_storage"] == channel.playout_storage`, and
2. the asset's `path` lies under `channel.playout_dir`.

For such assets, the `play` service cues the file from its own path (relative
to `playout_dir`, without extension). The rundown takes the item's status from
the asset status instead of `playout_status/<id_channel>`. Assets that don't
meet the conditions fall back to the classic copy-based flow, which would need
PSM.

**Do not add a `psm` service** to `settings/services.py`. It has nothing to do
here and would try to transfer any asset that is not under the playout dir.

### How the paths line up

Three settings must describe the same physical directory:

| Where                  | Setting                              | Value                |
| ---------------------- | ------------------------------------ | -------------------- |
| `settings/storages.py` | storage `path` (as seen by Nebula)   | `/mnt/nebula_01`     |
| `settings/channels.py` | `playout_storage` / `playout_dir`    | `1` / `media.dir`    |
| `casparcg.config`      | `<media-path>` (as seen by CasparCG) | `/storage/media.dir` |

The rule: **CasparCG's `<media-path>` is `<storage path>/<playout_dir>`**. Both
sides see the same files, even though each mounts them at a different path.

New assets are placed inside the playout dir by the asset validator
(`plugins/validator/asset.py`):

```python
asset["id_storage"] = 1
asset["path"] = f"media.dir/{subdir}/{asset['id/main']}.mxf"
```

So the same file looks like this from each side:

```
host:      ./storage/media.dir/movies/00001a.mxf
nebula:    /mnt/nebula_01/media.dir/movies/00001a.mxf   (storage path + asset path)
casparcg:  /storage/media.dir/movies/00001a.mxf         (media-path + clip name)
```

The `play` service tells CasparCG to load `movies/00001a`, and CasparCG
resolves it against its `<media-path>`.

Uploads land in `import.dir`, which is outside the playout dir. The import job
writes into `.nx/creating` first and then moves the finished file into place,
so CasparCG never sees a half-written file. Nothing transcodes the file again
for playout, so the import profile must produce files that are already in the
channel's format.

If you rename `playout_dir`, update `<media-path>` and the validator's path
prefix to match.

### Running CasparCG outside docker

CasparCG can also run on the host or on a dedicated playout machine, as long
as it sees the same directory:

- Point `<media-path>` at the shared `media.dir`: the host path on the same
  machine, or an NFS/SMB mount on another one.
- In `settings/channels.py`, set `caspar_host` to the CasparCG machine's
  address.
- In `casparcg.config`, set the OSC `<predefined-client>` address to an address
  of the `worker` that CasparCG can reach (port `6251`, matching
  `caspar_osc_port`).

## Repository layout

```
compose.yml               core stack
compose.dev.yml           dev override: mount local nebula-server / nebula-worker
compose.nvidia.yml        NVIDIA GPU for CasparCG
compose.blackmagic.yml    DeckLink for CasparCG
casparcg.config           CasparCG configuration (video mode, media path, preview stream)
Caddyfile                 HTTPS load balancer
mediamtx.yml              preview stream server (HLS on :8888, RTSP on :8554)
settings/                 Nebula settings, loaded by the `setup` job
  channels.py             playout channel (playout_storage, playout_dir, caspar_*)
  storages.py             storage definitions
  services.py             worker services (note: no PSM)
  settings.py             general settings (upload directory...)
  actions/                import (XDCAM HD 1080i50) and proxy conversion actions
plugins/validator/        asset validator, places new assets under the playout dir
storage/                  shared media directory (mounted in Nebula and CasparCG)
  media.dir/              CasparCG media-path AND Nebula asset storage
  import.dir/             upload drop folder
  template.dir/           CasparCG HTML templates
  fonts.dir/              fonts used by proxy generation
```
