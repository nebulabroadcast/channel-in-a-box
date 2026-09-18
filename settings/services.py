from nebula.settings.models import ServiceSettings


def play_settings(id_channel: int) -> str:
    return f"<service><id_channel>{id_channel}</id_channel> </service>"


SERVICES = [
    ServiceSettings(id=1, type="broker", name="broker", host="worker"),
    ServiceSettings(id=2, type="meta", name="meta", host="worker", loop_delay=2),
    ServiceSettings(
        id=3, type="play", name="play1", host="worker", settings=play_settings(1)
    ),
    ServiceSettings(id=4, type="import", name="import", host="worker"),
    ServiceSettings(id=5, type="conv", name="conv1", host="worker"),
    ServiceSettings(id=6, type="conv", name="conv2", host="worker"),
]
