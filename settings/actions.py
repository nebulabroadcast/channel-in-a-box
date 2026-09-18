from nebula.settings.models import ActionSettings


def load_cfg(filename: str) -> str:
    return open(f"/settings/actions/{filename}.xml").read()


ACTIONS = [
    ActionSettings(
        id=1, 
        name="proxy", 
        type="conv", 
        settings=load_cfg("proxy")
    ),
    ActionSettings(
        id=2, 
        name="import", 
        type="import", 
        settings=load_cfg("import")
    )
]
