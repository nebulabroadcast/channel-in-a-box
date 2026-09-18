from nebula.settings.models import PlayoutChannelSettings, AcceptModel


scheduler_accepts = AcceptModel(folders=[1, 2])
rundown_accepts = AcceptModel(folders=[1, 3, 4, 5, 6, 7, 8, 9, 10])


channel1 = PlayoutChannelSettings(
    id=1,
    name="Channel 1",
    fps=25.0,
    plugins=["nxtv"],
    solvers=["fill"],
    day_start=(7, 0),
    scheduler_accepts=scheduler_accepts,
    rundown_accepts=rundown_accepts,
    rundown_columns=[],
    send_action=2,
    engine="casparcg",
    allow_remote=False,
    controller_host="worker",
    controller_port=42101,
    playout_storage=1,
    playout_dir="media.dir",
    playout_container="mxf",
    config={
        "caspar_host": "casparcg",
        "caspar_port": 5250,
        "caspar_osc_port": 6251,
        "caspar_channel": 1,
        "caspar_feed_layer": 10,
        "live_source": "#c03a00",
    },
)


CHANNELS = [channel1]
