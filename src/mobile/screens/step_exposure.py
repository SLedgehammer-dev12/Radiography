from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu


FILM_CLASSES = ["C1", "C2", "C3", "C4", "C5", "C6"]
DETECTOR_TYPES = [
    ("cr_standard", "detector_cr_std"),
    ("cr_highres", "detector_cr_hires"),
    ("dda_si", "detector_dda_si"),
    ("dda_se", "detector_dda_se"),
    ("dda_gdos", "detector_dda_gdos"),
]


class StepExposure(MDScreen):
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
        is_digital = self.state.tech == "digital"
        self.ids.film_area.opacity = 0 if is_digital else 1
        self.ids.film_area.disabled = is_digital
        self.ids.detector_area.opacity = 1 if is_digital else 0
        self.ids.detector_area.disabled = not is_digital
        self.ids.film_class_btn.text = self.state.film_class
        self.ids.detector_btn.text = self.state.get_text(DETECTOR_TYPES[0][1])

    def on_kv(self, text):
        try:
            self.state.set("kv", float(text))
        except ValueError:
            pass

    def on_ma(self, text):
        try:
            self.state.set("ma", float(text))
        except ValueError:
            pass

    def on_time(self, text):
        try:
            self.state.set("exposure_time", float(text))
        except ValueError:
            pass

    def on_sfd(self, text):
        try:
            self.state.set("sfd", float(text))
        except ValueError:
            pass

    def on_slider_kv(self, value):
        self.state.set("kv", round(value, 1))
        self.ids.kv_input.text = str(round(value, 1))

    def on_slider_ma(self, value):
        self.state.set("ma", round(value, 1))
        self.ids.ma_input.text = str(round(value, 1))

    def on_slider_time(self, value):
        self.state.set("exposure_time", round(value, 1))
        self.ids.time_input.text = str(round(value, 1))

    def on_slider_sfd(self, value):
        self.state.set("sfd", round(value, 1))
        self.ids.sfd_input.text = str(round(value, 1))

    def open_film_menu(self):
        items = [{
            "text": c,
            "on_release": lambda v=c: self._select_film(v)
        } for c in FILM_CLASSES]
        menu = MDDropdownMenu(
            caller=self.ids.film_class_btn,
            items=items,
            width_mult=3,
        )
        menu.open()

    def open_detector_menu(self):
        items = [{
            "text": self.state.get_text(d[1]),
            "on_release": lambda v=d[0]: self._select_detector(v)
        } for d in DETECTOR_TYPES]
        menu = MDDropdownMenu(
            caller=self.ids.detector_btn,
            items=items,
            width_mult=4,
        )
        menu.open()

    def _select_film(self, value):
        self.state.set("film_class", value)
        self.state.set("film_class_used", value)
        self.ids.film_class_btn.text = value

    def _select_detector(self, value):
        self.state.set("detector_type", value)
        label = next((self.state.get_text(d[1]) for d in DETECTOR_TYPES if d[0] == value), value)
        self.ids.detector_btn.text = label

    def on_calculate(self):
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self._do_calc())

    def _do_calc(self):
        self.state.run_calculations()
        self.on_next()

    def on_source_side_change(self, active):
        self.state.set("source_side_iqi", active)

    def on_next(self):
        self.manager.current = "results"

    def on_back(self):
        self.manager.current = "dimensions"
