from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from core.asme_b36 import ASME_B36_10_PIPES, get_pipe_schedules, get_default_schedule


PIPE_KEYS = sorted(ASME_B36_10_PIPES.keys(),
                   key=lambda k: float(k.split('"')[0].replace(" 1/4", ".25").replace(" 1/2", ".5").replace(" 3/4", ".75").replace(" 1/8", ".125").replace(" 3/8", ".375").replace(" 1 1/4", "1.25").replace(" 1 1/2", "1.5").replace(" 2 1/2", "2.5")))


class StepDimensions(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = None
        self._menus = {}

    def on_enter(self):
        if self.state is None:
            from lib.app_state import AppState
            self.state = AppState()
        self._update_ui()

    def _update_ui(self):
        pipe_key = self.state.get("pipe_od_std", PIPE_KEYS[5])
        self.ids.od_btn.text = pipe_key
        self.ids.custom_od.text = str(self.state.pipe_od)
        self.ids.custom_wall.text = str(self.state.pipe_wall)
        self.ids.cap.text = str(self.state.cap)
        self.ids.schedule_btn.text = self.state.get("pipe_schedule", "SCH 40 / STD")

    def open_pipe_menu(self):
        items = [{
            "text": key,
            "on_release": lambda k=key: self._on_pipe_selected(k)
        } for key in PIPE_KEYS]
        menu = MDDropdownMenu(
            caller=self.ids.od_btn,
            items=items,
            width_mult=4,
        )
        menu.open()

    def _on_pipe_selected(self, key):
        od = ASME_B36_10_PIPES[key][0]
        self.state.set("pipe_od_std", key)
        self.state.set("pipe_od", od)
        self.state.set("use_standard", True)
        self.ids.od_btn.text = key
        self.ids.custom_od.text = str(od)

        schedules = get_pipe_schedules(key)
        if len(schedules) == 1:
            wall, label = schedules[0]
            self._select_schedule(wall, label)
        else:
            self.open_schedule_menu(key)

    def open_schedule_menu(self, pipe_key=None):
        if pipe_key is None:
            pipe_key = self.state.get("pipe_od_std", PIPE_KEYS[5])
        schedules = get_pipe_schedules(pipe_key)
        items = [{
            "text": f"{label} ({wall:.2f} mm)",
            "on_release": lambda w=wall, l=label: self._select_schedule(w, l)
        } for wall, label in schedules]
        menu = MDDropdownMenu(
            caller=self.ids.schedule_btn,
            items=items,
            width_mult=4,
        )
        menu.open()

    def _select_schedule(self, wall, label):
        self.state.set("pipe_wall", wall)
        self.state.set("pipe_schedule", label)
        self.ids.schedule_btn.text = label
        self.ids.custom_wall.text = str(wall)

    def on_custom_od(self, text):
        try:
            val = float(text.replace(",", "."))
            self.state.set("pipe_od", val)
            self.state.set("use_standard", False)
        except ValueError:
            pass

    def on_custom_wall(self, text):
        try:
            val = float(text.replace(",", "."))
            self.state.set("pipe_wall", val)
            self.state.set("use_standard", False)
        except ValueError:
            pass

    def on_cap(self, text):
        try:
            self.state.set("cap", float(text.replace(",", ".")))
        except ValueError:
            pass

    def on_next(self):
        self.manager.current = "exposure"

    def on_back(self):
        self.manager.current = "technique"
