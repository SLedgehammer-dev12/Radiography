from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu

STD_PIPES = [
    ('1/2" (NPS 1/2)', 21.3, 2.77),
    ('3/4" (NPS 3/4)', 26.7, 2.87),
    ('1" (NPS 1)', 33.4, 3.38),
    ('1.5" (NPS 1.5)', 48.3, 3.68),
    ('2" (NPS 2)', 60.3, 3.91),
    ('3" (NPS 3)', 88.9, 5.49),
    ('4" (NPS 4)', 114.3, 6.02),
    ('6" (NPS 6)', 168.3, 7.11),
    ('8" (NPS 8)', 219.1, 8.18),
    ('10" (NPS 10)', 273.1, 9.27),
    ('12" (NPS 12)', 323.9, 10.31),
    ('14" (NPS 14)', 355.6, 11.13),
    ('16" (NPS 16)', 406.4, 12.70),
    ('20" (NPS 20)', 508.0, 15.09),
    ('24" (NPS 24)', 609.6, 17.48),
]


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
        self.ids.od_btn.text = self.state.get("pipe_od_std", STD_PIPES[5][0])
        self.ids.custom_od.text = str(self.state.pipe_od)
        self.ids.custom_wall.text = str(self.state.pipe_wall)
        self.ids.cap.text = str(self.state.cap)

    def open_pipe_menu(self):
        items = [{
            "text": p[0],
            "on_release": lambda n=p[0], o=p[1], w=p[2]: self._select_pipe(n, o, w)
        } for p in STD_PIPES]
        menu = MDDropdownMenu(
            caller=self.ids.od_btn,
            items=items,
            width_mult=4,
        )
        menu.open()

    def _select_pipe(self, name, od, wall):
        self.state.set("pipe_od_std", name)
        self.state.set("pipe_od", od)
        self.state.set("pipe_wall", wall)
        self.state.set("use_standard", True)
        self.ids.od_btn.text = name
        self.ids.custom_od.text = str(od)
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
