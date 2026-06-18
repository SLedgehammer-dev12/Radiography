from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.app import MDApp
# MDSegmentedButton not available in KivyMD 1.2.0; use MDBoxLayout + MDRaisedButton instead
from kivymd.uix.menu import MDDropdownMenu
from kivy.properties import StringProperty, ObjectProperty


TECHNIQUES = ["swsi", "dwsi", "dwdi_elliptic", "dwdi_super"]
MATERIALS = ["steel", "aluminum", "titanium", "copper_nickel"]
CLASSES = ["class_a", "class_b"]
SOURCES = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60"]
GEOMETRIES = ["swsi", "dwdi_elliptic", "dwdi_super", "dwsi"]


class StepTechnique(MDScreen):
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
        self.ids.tech_segment.opacity = 1

    def set_tech(self, value):
        self.state.set("tech", value)
        app = MDApp.get_running_app()
        unsel = app.theme_cls.bg_dark if app.theme_cls.theme_style == "Dark" else (0.85, 0.85, 0.85, 1)
        self.ids.tech_analog.md_bg_color = app.theme_cls.primary_color if value == "analog" else unsel
        self.ids.tech_digital.md_bg_color = app.theme_cls.primary_color if value == "digital" else unsel

    def on_next(self):
        self.manager.current = "dimensions"

    def on_back(self):
        pass

    def open_technique_menu(self):
        items = [{"text": t.upper(), "on_release": lambda v=t: self._select_technique(v)} for t in TECHNIQUES]
        self._show_menu("technique", items, self.ids.technique_btn)

    def open_material_menu(self):
        items = [{"text": self.state.get_text(m), "on_release": lambda v=m: self._select_material(v)} for m in MATERIALS]
        self._show_menu("material", items, self.ids.material_btn)

    def open_class_menu(self):
        items = [{"text": self.state.get_text(c), "on_release": lambda v=c: self._select_class(v)} for c in CLASSES]
        self._show_menu("class", items, self.ids.class_btn)

    def open_source_menu(self):
        items = [{"text": self.state.get_text(s), "on_release": lambda v=s: self._select_source(v)} for s in SOURCES]
        self._show_menu("source", items, self.ids.source_btn)

    def open_geometry_menu(self):
        items = [{"text": self.state.get_text(g), "on_release": lambda v=g: self._select_geometry(v)} for g in GEOMETRIES]
        self._show_menu("geometry", items, self.ids.geometry_btn)

    def _select_technique(self, value):
        self.state.set("technique", value)
        self.ids.technique_btn.text = value.upper()
        self._close_menu("technique")

    def _select_material(self, value):
        self.state.set("material", value)
        self.ids.material_btn.text = self.state.get_text(value)
        self._close_menu("material")

    def _select_class(self, value):
        self.state.set("testing_class", value)
        self.ids.class_btn.text = self.state.get_text(value)
        self._close_menu("class")

    def _select_source(self, value):
        self.state.set("source", value)
        self.ids.source_btn.text = self.state.get_text(value)
        self._close_menu("source")

    def _select_geometry(self, value):
        self.state.set("geometry", value)
        self.ids.geometry_btn.text = self.state.get_text(value)
        self._close_menu("geometry")

    def _show_menu(self, name, items, caller):
        self._close_menu(name)
        menu = MDDropdownMenu(
            caller=caller,
            items=[{"text": i["text"], "on_release": i["on_release"]} for i in items],
            width_mult=4,
        )
        menu.open()
        self._menus[name] = menu

    def _close_menu(self, name):
        if name in self._menus:
            self._menus[name].dismiss()
            del self._menus[name]
