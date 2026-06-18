from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, Ellipse, Line, Rectangle, Triangle
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivymd.uix.screen import MDScreen
from kivymd.uix.tab import MDTabs, MDTabsBase
from kivymd.app import MDApp
import math


SKETCH_TYPES = [
    "cross_section",
    "longitudinal",
    "double_wall",
    "elliptical",
    "superimposed",
    "panoramic",
    "girth_weld",
    "t_joint",
    "source_film",
    "defect_map",
]

SKETCH_LABELS = {
    "cross_section": "Kesit",
    "longitudinal": "Boyuna",
    "double_wall": "Çift Duvar",
    "elliptical": "Eliptik",
    "superimposed": "Süperpoze",
    "panoramic": "Panoramik",
    "girth_weld": "Çevresel",
    "t_joint": "T-Birleşim",
    "source_film": "Kaynak-Film",
    "defect_map": "Kusur Haritası",
}


class _TabContent(BoxLayout, MDTabsBase):
    pass


class WeldCanvas(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sketch_type = "cross_section"
        self._state = None

    @property
    def state(self):
        if self._state is None:
            from lib.app_state import AppState
            self._state = AppState()
        return self._state

    def on_size(self, *args):
        self.draw_weld()

    def draw_weld(self):
        self.canvas.before.clear()
        self.clear_widgets()
        w = self.width
        h = self.height
        if w < 10 or h < 10:
            return

        drawer = getattr(self, f"_draw_{self._sketch_type}", self._draw_cross_section)
        drawer(w, h)

    def toggle_sketch(self, sketch_type):
        self._sketch_type = sketch_type
        self.draw_weld()

    def _bg(self):
        Color(0.08, 0.08, 0.12, 1)
        Rectangle(pos=self.pos, size=self.size)

    def _dim_line(self, x1, y1, x2, y2, label_text):
        Color(0.6, 0.8, 1, 1)
        Line(points=[x1, y1, x2, y2], width=1)
        Color(0.6, 0.8, 1, 0.7)
        Line(points=[x1 - 4, y1 - 4, x1, y1], width=1)
        Line(points=[x2, y2, x2 + 4, y2 + 4], width=1)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        lbl = Label(
            text=label_text, color=(0.6, 0.8, 1, 1),
            font_size=dp(10), size_hint=(None, None),
            size=(dp(80), dp(16)), pos=(mx - dp(40), my - dp(8)),
        )
        self.add_widget(lbl)

    def _source_marker(self, x, y, label="X"):
        Color(0.95, 0.35, 0.2, 1)
        Ellipse(pos=(x - dp(6), y - dp(6)), size=(dp(12), dp(12)))
        Color(1, 1, 1, 1)
        Line(points=[x, y - dp(8), x, y - dp(3)], width=1.5)
        Line(points=[x, y + dp(3), x, y + dp(8)], width=1.5)
        Line(points=[x - dp(8), y, x - dp(3), y], width=1.5)
        Line(points=[x + dp(3), y, x + dp(8), y], width=1.5)
        lbl = Label(
            text=label, color=(0.95, 0.35, 0.2, 1),
            font_size=dp(11), bold=True, size_hint=(None, None),
            size=(dp(24), dp(16)), pos=(x - dp(12), y + dp(10)),
        )
        self.add_widget(lbl)

    def _film_marker(self, x, y, label="Film"):
        Color(0.25, 0.7, 0.45, 1)
        fw, fh = dp(4), dp(24)
        Rectangle(pos=(x - fw / 2, y - fh / 2), size=(fw, fh))
        lbl = Label(
            text=label, color=(0.25, 0.7, 0.45, 1),
            font_size=dp(10), size_hint=(None, None),
            size=(dp(32), dp(16)), pos=(x + dp(6), y - dp(8)),
        )
        self.add_widget(lbl)

    def _draw_cross_section(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.35
            od = self.state.pipe_od
            wall = self.state.pipe_wall
            r_od = r
            r_id = r * max(0.15, (od - 2 * wall) / od) if od > 0 else r * 0.8

            Color(0.3, 0.55, 0.95, 1)
            Ellipse(pos=(cx - r_od, cy - r_od), size=(r_od * 2, r_od * 2))
            Color(0.08, 0.08, 0.12, 1)
            Ellipse(pos=(cx - r_id, cy - r_id), size=(r_id * 2, r_id * 2))

            cap_w = r_od * 0.2
            cap_h = r_od * 0.12
            bottom_y = cy - math.sqrt(max(0, r_od ** 2 - cap_w ** 2))
            Color(0.85, 0.65, 0.15, 1)
            Line(points=[
                cx - cap_w, bottom_y,
                cx, cy - r_od - cap_h,
                cx + cap_w, bottom_y,
            ], width=2, close=True)
            top_y = cy + math.sqrt(max(0, r_od ** 2 - cap_w ** 2))
            Line(points=[
                cx - cap_w, top_y,
                cx, cy + r_od + cap_h,
                cx + cap_w, top_y,
            ], width=2, close=True)

            Color(1, 1, 1, 0.25)
            Line(points=[cx - r_od - dp(10), cy, cx + r_od + dp(10), cy], width=0.5, dash_length=3)

        self._dim_line(cx + r_od + dp(12), cy, cx + r_od + dp(12), cy - r_od, f"OD={od:.1f}")
        self._dim_line(cx + r_id + dp(4), cy, cx + r_od - dp(4), cy, f"t={wall:.1f}")

    def _draw_longitudinal(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            pw = min(w, h) * 0.55
            ph = min(w, h) * 0.22
            wall = self.state.pipe_wall

            Color(0.3, 0.55, 0.95, 1)
            Rectangle(pos=(cx - pw / 2, cy - ph / 2), size=(pw, ph))
            Color(0.08, 0.08, 0.12, 1)
            od = self.state.pipe_od
            inner_h = ph * max(0.15, (1 - 2 * wall / od)) if od > 0 else ph * 0.6
            Rectangle(pos=(cx - pw / 2, cy - inner_h / 2), size=(pw, inner_h))

            Color(0.85, 0.65, 0.15, 1)
            weld_w = pw * 0.08
            weld_h = ph * 0.15
            Line(points=[cx - weld_w / 2, cy - ph / 2, cx, cy - ph / 2 - weld_h, cx + weld_w / 2, cy - ph / 2], width=2, close=True)
            Line(points=[cx - weld_w / 2, cy + ph / 2, cx, cy + ph / 2 + weld_h, cx + weld_w / 2, cy + ph / 2], width=2, close=True)
            Color(0.85, 0.65, 0.15, 0.4)
            Rectangle(pos=(cx - 1, cy - ph / 2), size=(2, ph))

            Color(1, 1, 1, 0.3)
            Line(points=[cx - pw / 2, cy, cx + pw / 2, cy], width=0.5, dash_length=3)

        self._source_marker(cx - pw / 2 - dp(30), cy)
        self._film_marker(cx + pw / 2 + dp(30), cy)

    def _draw_double_wall(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.32
            od = self.state.pipe_od
            wall = self.state.pipe_wall
            id_ratio = max(0.1, (od - 2 * wall) / od) if od > 0 else 0.8

            Color(0.3, 0.55, 0.95, 0.6)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(0.08, 0.08, 0.12, 1)
            ir = r * id_ratio
            Ellipse(pos=(cx - ir, cy - ir), size=(ir * 2, ir * 2))

            offset = r * 0.15
            Color(0.3, 0.55, 0.95, 0.35)
            Ellipse(pos=(cx - r + offset, cy - r - offset), size=(r * 2, r * 2))
            Color(0.08, 0.08, 0.12, 1)
            Ellipse(pos=(cx - ir + offset, cy - ir - offset), size=(ir * 2, ir * 2))

            Color(0.85, 0.65, 0.15, 0.8)
            ew = r * 0.12
            eh = r * 0.06
            for dx, dy in [(0, 0), (offset, -offset)]:
                by = cy + dy - math.sqrt(max(0, r ** 2 - ew ** 2))
                Line(points=[cx + dx - ew, by, cx + dx, cy + dy - r - eh, cx + dx + ew, by], width=1.5, close=True)

    def _draw_elliptical(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            rx = min(w, h) * 0.38
            ry = rx * 0.55
            od = self.state.pipe_od
            wall = self.state.pipe_wall
            id_ratio = max(0.15, (od - 2 * wall) / od) if od > 0 else 0.8

            Color(0.3, 0.55, 0.95, 1)
            Ellipse(pos=(cx - rx, cy - ry), size=(rx * 2, ry * 2))
            Color(0.08, 0.08, 0.12, 1)
            irx = rx * id_ratio
            iry = ry * id_ratio
            Ellipse(pos=(cx - irx, cy - iry), size=(irx * 2, iry * 2))

            Color(0.85, 0.65, 0.15, 1)
            ew = rx * 0.15
            top_y = cy + math.sqrt(max(0, ry ** 2 - (ew * ry / rx) ** 2))
            Line(points=[cx - ew, top_y, cx, cy + ry + ry * 0.1, cx + ew, top_y], width=2, close=True)

            Color(1, 1, 1, 0.25)
            Line(points=[cx - rx - dp(5), cy, cx + rx + dp(5), cy], width=0.5, dash_length=3)
            Line(points=[cx, cy - ry - dp(5), cx, cy + ry + dp(5)], width=0.5, dash_length=3)

        self._source_marker(cx - rx - dp(25), cy + ry + dp(20))
        self._film_marker(cx + rx + dp(25), cy - ry - dp(20))

    def _draw_superimposed(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.32
            od = self.state.pipe_od
            wall = self.state.pipe_wall
            id_ratio = max(0.15, (od - 2 * wall) / od) if od > 0 else 0.8

            for angle in range(0, 360, 45):
                a = math.radians(angle)
                dx = r * 0.12 * math.cos(a)
                dy = r * 0.12 * math.sin(a)
                Color(0.3, 0.55, 0.95, 0.3)
                Ellipse(pos=(cx - r + dx, cy - r + dy), size=(r * 2, r * 2))
                ir = r * id_ratio
                Color(0.08, 0.08, 0.12, 0.5)
                Ellipse(pos=(cx - ir + dx, cy - ir + dy), size=(ir * 2, ir * 2))

            Color(0.3, 0.55, 0.95, 1)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(0.08, 0.08, 0.12, 1)
            ir = r * id_ratio
            Ellipse(pos=(cx - ir, cy - ir), size=(ir * 2, ir * 2))

            Color(0.85, 0.65, 0.15, 1)
            ew = r * 0.15
            by = cy - math.sqrt(max(0, r ** 2 - ew ** 2))
            Line(points=[cx - ew, by, cx, cy - r - r * 0.08, cx + ew, by], width=2, close=True)

    def _draw_panoramic(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.35
            od = self.state.pipe_od
            wall = self.state.pipe_wall
            id_ratio = max(0.15, (od - 2 * wall) / od) if od > 0 else 0.8

            Color(0.3, 0.55, 0.95, 1)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(0.08, 0.08, 0.12, 1)
            ir = r * id_ratio
            Ellipse(pos=(cx - ir, cy - ir), size=(ir * 2, ir * 2))

            Color(0.85, 0.65, 0.15, 1)
            ew = r * 0.12
            for a in [0, 120, 240]:
                rad = math.radians(a)
                wx = cx + r * 0.7 * math.cos(rad)
                wy = cy + r * 0.7 * math.sin(rad)
                nx = -math.cos(rad)
                ny = -math.sin(rad)
                px = ny
                py = -nx
                Line(points=[
                    wx + ew * px, wy + ew * py,
                    wx + ew * 1.8 * px - r * 0.12 * nx, wy + ew * 1.8 * py - r * 0.12 * ny,
                    wx - ew * px, wy - ew * py,
                ], width=1.5, close=True)

            Color(1, 1, 1, 0.4)
            Line(circle=(cx, cy, r * 0.6), width=1, dash_length=3)

        self._source_marker(cx, cy, "Ir")
        for a in [0, 90, 180, 270]:
            rad = math.radians(a)
            fx = cx + (r + dp(15)) * math.cos(rad)
            fy = cy + (r + dp(15)) * math.sin(rad)
            self._film_marker(fx, fy)

    def _draw_girth_weld(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            pw = min(w, h) * 0.45
            ph = min(w, h) * 0.35

            Color(0.3, 0.55, 0.95, 1)
            Rectangle(pos=(cx - pw / 2, cy - ph / 2), size=(pw, ph))
            Color(0.08, 0.08, 0.12, 1)
            inner_h = ph * 0.6
            Rectangle(pos=(cx - pw / 2, cy - inner_h / 2), size=(pw, inner_h))

            Color(0.85, 0.65, 0.15, 1)
            ww = pw * 0.06
            wh = ph * 0.2
            Line(points=[cx - ww / 2, cy - ph / 2 - wh / 2, cx, cy - ph / 2 - wh, cx + ww / 2, cy - ph / 2 - wh / 2], width=2, close=True)
            Line(points=[cx - ww / 2, cy + ph / 2 + wh / 2, cx, cy + ph / 2 + wh, cx + ww / 2, cy + ph / 2 + wh / 2], width=2, close=True)

            Color(0.85, 0.65, 0.15, 0.5)
            Line(points=[cx - pw / 2, cy - ph / 2 - wh / 2, cx - pw / 2, cy + ph / 2 + wh / 2], width=2)
            Line(points=[cx + pw / 2, cy - ph / 2 - wh / 2, cx + pw / 2, cy + ph / 2 + wh / 2], width=2)

        self._source_marker(cx - pw / 2 - dp(30), cy + ph + dp(20))
        self._film_marker(cx + pw / 2 + dp(30), cy - ph - dp(20))

    def _draw_t_joint(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            pw = min(w, h) * 0.35
            ph = min(w, h) * 0.5

            Color(0.3, 0.55, 0.95, 1)
            Rectangle(pos=(cx - pw, cy - ph * 0.15), size=(pw * 2, ph * 0.3))
            Color(0.08, 0.08, 0.12, 1)
            main_inner = ph * 0.15
            Rectangle(pos=(cx - pw, cy - main_inner / 2), size=(pw * 2, main_inner))

            Color(0.3, 0.55, 0.95, 1)
            Rectangle(pos=(cx - pw * 0.15, cy + ph * 0.08), size=(pw * 0.3, ph * 0.55))
            Color(0.08, 0.08, 0.12, 1)
            branch_inner = pw * 0.15
            Rectangle(pos=(cx - branch_inner / 2, cy + ph * 0.08), size=(branch_inner, ph * 0.55))

            Color(0.85, 0.65, 0.15, 1)
            Line(circle=(cx, cy + ph * 0.08), radius=pw * 0.22, width=3)
            Color(0.85, 0.65, 0.15, 0.3)
            Ellipse(pos=(cx - pw * 0.22, cy + ph * 0.08 - pw * 0.22), size=(pw * 0.44, pw * 0.44))

    def _draw_source_film(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            r = min(w, h) * 0.28

            Color(0.3, 0.55, 0.95, 1)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            od = self.state.pipe_od
            wall = self.state.pipe_wall
            id_ratio = max(0.15, (od - 2 * wall) / od) if od > 0 else 0.8
            Color(0.08, 0.08, 0.12, 1)
            ir = r * id_ratio
            Ellipse(pos=(cx - ir, cy - ir), size=(ir * 2, ir * 2))

            Color(0.85, 0.65, 0.15, 1)
            ew = r * 0.15
            by = cy + math.sqrt(max(0, r ** 2 - ew ** 2))
            Line(points=[cx - ew, by, cx, cy + r + r * 0.08, cx + ew, by], width=2, close=True)

            Color(0.85, 0.65, 0.15, 0.3)
            Line(points=[cx - ew, by, cx + ew, by], width=2)

            Color(1, 1, 0.4, 0.3)
            src_y = cy + r + dp(50)
            beam_w = r * 0.5
            Line(points=[cx, src_y, cx - beam_w, by], width=0.5)
            Line(points=[cx, src_y, cx + beam_w, by], width=0.5)
            Line(points=[cx, src_y, cx, by], width=0.5)

        self._source_marker(cx, cy + r + dp(50), "X")
        self._film_marker(cx, cy - r - dp(20))

    def _draw_defect_map(self, w, h):
        with self.canvas.before:
            self._bg()
            cx, cy = w / 2, h / 2
            pw = min(w, h) * 0.55
            ph = min(w, h) * 0.18

            Color(0.2, 0.2, 0.25, 1)
            Rectangle(pos=(cx - pw / 2, cy - ph / 2), size=(pw, ph))

            Color(0.85, 0.65, 0.15, 1)
            Rectangle(pos=(cx - pw * 0.02, cy - ph / 2), size=(pw * 0.04, ph))

            defects = [
                (cx - pw * 0.3, cy, 0.95, 0.2, 0.2, 4),
                (cx - pw * 0.1, cy + ph * 0.15, 0.2, 0.95, 0.2, 3),
                (cx + pw * 0.1, cy - ph * 0.1, 0.95, 0.95, 0.2, 5),
                (cx + pw * 0.3, cy + ph * 0.1, 0.95, 0.5, 0.2, 3),
                (cx + pw * 0.2, cy - ph * 0.15, 0.5, 0.5, 0.95, 4),
            ]
            for dx, dy, r_, g_, b_, size in defects:
                Color(r_, g_, b_, 0.8)
                Ellipse(pos=(dx - dp(size), dy - dp(size)), size=(dp(size * 2), dp(size * 2)))

            Color(1, 1, 1, 0.4)
            for i in range(1, 5):
                x = cx - pw / 2 + pw * i / 5
                Line(points=[x, cy - ph / 2, x, cy + ph / 2], width=0.3, dash_length=2)

        lbl = Label(
            text="Kusur Haritası (şematik)", color=(0.6, 0.6, 0.6, 1),
            font_size=dp(9), size_hint=(None, None),
            size=(dp(160), dp(16)), pos=(cx - dp(80), cy - dp(20)),
        )
        self.add_widget(lbl)

    def save_to_png(self, filepath):
        try:
            self.export_to_png(filepath)
            return filepath
        except Exception:
            return None


class StepSketch(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = None
        self._tabs_init = False

    def on_enter(self):
        if self.state is None:
            from lib.app_state import AppState
            self.state = AppState()
        if not self._tabs_init:
            self._init_tabs()
            self._tabs_init = True
        Clock.schedule_once(lambda dt: self.ids.canvas.draw_weld(), 0.1)

    def _init_tabs(self):
        tabs = self.ids.tabs
        for key in SKETCH_TYPES:
            label = SKETCH_LABELS.get(key, key)
            tab = _TabContent(text=label)
            tabs.add_widget(tab)

    def toggle_sketch(self, instance, tab, tab_text, tab_icon):
        for key, label in SKETCH_LABELS.items():
            if label == tab_text:
                self.ids.canvas.toggle_sketch(key)
                break

    def on_back(self):
        self.manager.current = "results"
