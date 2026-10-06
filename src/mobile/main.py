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

    # ------------------------------------------------------------------
    # Update management
    # ------------------------------------------------------------------
    def _close_update_dialog(self):
        dialog = getattr(self, "_update_dialog", None)
        if dialog is not None:
            dialog.dismiss()

    def _update_ok_buttons(self):
        from kivymd.uix.button import MDFlatButton
        return [MDFlatButton(text=self.state.get_text("dialog_ok"),
                             on_release=lambda *_a: self._close_update_dialog())]

    def check_for_updates(self):
        from kivymd.uix.dialog import MDDialog
        self._pending_release = None
        self._update_dialog = MDDialog(
            title=self.state.get_text("check_updates_btn"),
            text=self.state.get_text("checking_updates"),
        )
        self._update_dialog.open()

        def _worker():
            from core.updater import UpdateChecker
            res = UpdateChecker().check()
            Clock.schedule_once(lambda dt: self._on_update_check(res), 0)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_check(self, res):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton, MDRaisedButton
        self._close_update_dialog()
        title = self.state.get_text("check_updates_btn")
        if res.get("available"):
            self._pending_release = res
            text = (f"{self.state.trans.get('update_available', str(res.get('version', '?')))}\n\n"
                    f"{str(res.get('release_notes') or '')[:400]}")
            self._update_dialog = MDDialog(
                title=title, text=text,
                buttons=[
                    MDFlatButton(text=self.state.get_text("dialog_cancel"),
                                 on_release=lambda *_a: self._close_update_dialog()),
                    MDRaisedButton(text=self.state.get_text("update_download"),
                                   on_release=lambda *_a: self._download_update()),
                ],
            )
        elif res.get("error"):
            self._update_dialog = MDDialog(title=title, text=str(res["error"]),
                                           buttons=self._update_ok_buttons())
        else:
            self._update_dialog = MDDialog(
                title=title,
                text=self.state.trans.get("up_to_date", str(res.get("version", ""))),
                buttons=self._update_ok_buttons())
        self._update_dialog.open()

    def _download_update(self):
        from kivymd.uix.dialog import MDDialog
        release = getattr(self, "_pending_release", None)
        self._close_update_dialog()
        self._update_dialog = MDDialog(
            title=self.state.get_text("check_updates_btn"),
            text=self.state.get_text("checking_updates"))
        self._update_dialog.open()

        def _worker():
            from core.updater import UpdateChecker
            checker = UpdateChecker()
            try:
                asset = checker.get_download_asset(release) if release else None
                if not asset or not asset.get("url"):
                    raise RuntimeError("No compatible download found for this platform.")
                digest = checker._extract_sha256_from_release(release, asset["name"])
                path = checker.download_update(asset["url"], expected_sha256=digest)
                Clock.schedule_once(lambda dt: self._on_download_done(path, checker), 0)
            except Exception as exc:  # noqa: BLE001
                Clock.schedule_once(lambda dt: self._on_download_done(exc, checker), 0)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_done(self, path, checker):
        from kivymd.uix.dialog import MDDialog
        self._close_update_dialog()
        if path is None:
            return
        if isinstance(path, Exception):
            self._update_dialog = MDDialog(title=self.state.get_text("check_updates_btn"),
                                           text=str(path), buttons=self._update_ok_buttons())
            self._update_dialog.open()
            return
        try:
            checker.launch_installer(path)
        except Exception as exc:  # noqa: BLE001
            self._update_dialog = MDDialog(title=self.state.get_text("check_updates_btn"),
                                           text=str(exc), buttons=self._update_ok_buttons())
            self._update_dialog.open()


if __name__ == "__main__":
    RadiographyApp().run()
