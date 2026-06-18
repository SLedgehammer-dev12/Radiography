from kivy.core.window import Window
from kivy.clock import Clock
from kivy.event import EventDispatcher


COMPACT_BREAKPOINT = 600
MEDIUM_BREAKPOINT = 840


class LayoutSelector(EventDispatcher):
    __events__ = ("on_layout_class_changed",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        w = Window.width
        if w < COMPACT_BREAKPOINT:
            self._last_class = "compact"
        elif w < MEDIUM_BREAKPOINT:
            self._last_class = "medium"
        else:
            self._last_class = "expanded"
        Window.bind(size=self._on_window_size)

    @property
    def is_compact(self):
        return self._last_class == "compact"

    @property
    def is_medium(self):
        return self._last_class == "medium"

    @property
    def is_expanded(self):
        return self._last_class == "expanded"

    def _on_window_size(self, instance, size):
        width = size[0]
        if width < COMPACT_BREAKPOINT:
            new_class = "compact"
        elif width < MEDIUM_BREAKPOINT:
            new_class = "medium"
        else:
            new_class = "expanded"

        if new_class != self._last_class:
            self._last_class = new_class
            self.dispatch("on_layout_class_changed", new_class)

    def get_layout_class(self):
        return self._last_class or "compact"

    def on_layout_class_changed(self, layout_class):
        pass
