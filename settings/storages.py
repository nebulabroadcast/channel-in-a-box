from nebula.settings.models import StorageSettings


STORAGES = [
    StorageSettings(
        id=1,
        name="production",
        protocol="local",
        path="/mnt/nebula_01",
    )
]
