import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.clock import Clock
from kivymd.app import MDApp

from lib.app_state import AppState
from responsive.layout_selector import LayoutSelector

kv_dir = os.path.join(os.path.dirname(__file__), "kv")


def load_kv_files():
    for root, dirs, files in os.walk(kv_dir):
        for f in files:
            if f.endswith(".kv"):
                path = os.path.join(root, f)
                Builder.load_file(path)


class RadiographyApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = AppState()
        self.layout_selector = LayoutSelector()
        self._current_layout = None

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.secondary_palette = "Teal"
        self.theme_cls.tertiary_palette = "Orange"
        self.theme_cls.neutral_palette = "Neutral"
        self.theme_cls.material_style = "M3"
        self.theme_cls.theme_style = "Dark"

        load_kv_files()

        from screens.step_technique import StepTechnique
        from screens.step_dimensions import StepDimensions
        from screens.step_exposure import StepExposure
        from screens.step_results import StepResults
        from screens.step_sketch import StepSketch

        self.sm = ScreenManager()
        self.sm.add_widget(StepTechnique(name="technique"))
        self.sm.add_widget(StepDimensions(name="dimensions"))
        self.sm.add_widget(StepExposure(name="exposure"))
        self.sm.add_widget(StepResults(name="results"))
        self.sm.add_widget(StepSketch(name="sketch"))

        self.layout_selector.bind(on_layout_class_changed=self._on_layout_change)

        initial = self.layout_selector.get_layout_class()
        self._apply_layout(initial)
        return self._current_layout

    def _on_layout_change(self, selector, layout_class):
        self._apply_layout(layout_class)
        self.root = self._current_layout

    def _apply_layout(self, layout_class):
        if self.sm.parent:
            self.sm.parent.remove_widget(self.sm)
        if layout_class == "compact":
            self.sm.size_hint = (1, 1)
            self._current_layout = self.sm
        elif layout_class == "medium":
            from responsive.medium_layout import MediumLayout
            self._current_layout = MediumLayout(self, self.sm)
        else:
            from responsive.expanded_layout import ExpandedLayout
            self._current_layout = ExpandedLayout(self, self.sm)

    def toggle_theme(self):
        self.theme_cls.theme_style = "Light" if self.theme_cls.theme_style == "Dark" else "Dark"
        self.state.is_dark_theme = (self.theme_cls.theme_style == "Dark")

    def toggle_language(self):
        self.state.language = "en" if self.state.language == "tr" else "tr"
        self.state.trans.set_language(self.state.language)


if __name__ == "__main__":
    RadiographyApp().run()
