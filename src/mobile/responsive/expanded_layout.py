from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.navigationrail import MDNavigationRail, MDNavigationRailItem



STEP_NAMES = ["technique", "dimensions", "exposure", "results", "sketch"]
STEP_DATA = [
    ("tune", "Teknik"),
    ("ruler", "Boyutlar"),
    ("flash", "Pozlama"),
    ("clipboard-check", "Sonuçlar"),
    ("draw", "Çizim"),
]


class ExpandedLayout(BoxLayout):

    def __init__(self, app, screen_manager, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.sm = screen_manager
        self.orientation = "horizontal"
        self._build()

    def _build(self):
        rail = MDNavigationRail(type="labeled")
        self._rail_items = []
        for icon, label in STEP_DATA:
            item = MDNavigationRailItem(icon=icon, text=label)
            item.bind(on_release=lambda x, n=STEP_NAMES[STEP_DATA.index((icon, label))]: self._switch_to(n))
            rail.add_widget(item)
            self._rail_items.append(item)
        rail.size_hint_x = None
        rail.width = dp(168)
        self.add_widget(rail)

        self.sm.size_hint = (1, 1)
        self.add_widget(self.sm)

        self._update_rail_selection()

    def _switch_to(self, name):
        self.sm.current = name
        self._update_rail_selection()

    def _update_rail_selection(self):
        for i, name in enumerate(STEP_NAMES):
            if i < len(self._rail_items):
                self._rail_items[i].selected = (name == self.sm.current)
