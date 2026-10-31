import json

from pydantic import BaseModel, Field

from nebula.plugins.playout import PlayoutPlugin, PlayoutPluginSlot


def jdata(**data):
    data = json.dumps(data).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{data}"'


class Context(BaseModel):
    showLogo: bool = Field(default=True, title="Show Logo")
    showClock: bool = Field(default=False, title="Show Clock")
    showInfo: bool = Field(default=False, title="Show Info")
    info: list[str] | None = Field(default=None, title="Info")


class Plugin(PlayoutPlugin):
    name = "nxtv"
    id_layer = 99
    slots = [
        PlayoutPluginSlot(type="action", name="Reboot"),
    ]

    def on_init(self):
        self.context = Context()
        self.boot()

    def boot(self):
        self.query(f"CG {self.layer()} ADD 0 nxtv 1")
        self.flush()

    def flush(self):
        payload = jdata(**self.context.dict())
        self.query(f"CG {self.layer()} UPDATE 0 {payload}")

    def on_change(self):
        ctx_changed = False

        self.tasks = []

        # do not show log on:
        # - folder 7 (jingles)
        # - folder 9 (ads)
        # - folder 10 (teleshopping)

        should_show_logo = self.current_item["id_folder"] not in [7, 9, 10]
        should_show_clock = self.current_item["id_folder"] not in [7, 9, 10]

        if should_show_logo != self.context.showLogo:
            self.context.showLogo = should_show_logo
            ctx_changed = True

        if should_show_clock != self.context.showClock:
            self.context.showClock = should_show_clock
            ctx_changed = True

        if self.current_item["id_folder"] in [1, 2, 3, 4, 5]:
            self.tasks.extend([self.show_now_playing, self.hide_now_playing])

        if ctx_changed:
            self.flush()

    def show_now_playing(self):
        if self.position < 5:
            return False
        self.context.showInfo = True
        self.context.info = ["Now Playing:", self.current_item["title"]]
        self.flush()
        return True

    def hide_now_playing(self):
        if self.position < 10:
            return False
        self.context.showInfo = False
        self.flush()
        return True

    def on_command(self, action, data):
        _ = action, data
        if action == "Reboot":
            self.boot()
            return True
