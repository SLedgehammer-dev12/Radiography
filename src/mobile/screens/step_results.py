from kivy.metrics import dp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.dialog import MDDialog

DEFECT_TYPES = ["crack", "ip", "if", "ic", "porosity", "slag", "undercut", "burn_through"]


class StepResults(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = None
        self._menus = {}
        self._dialog = None

    def on_enter(self):
        if self.state is None:
            from lib.app_state import AppState
            self.state = AppState()
        if self.state._calc_dirty:
            self.state.run_calculations()
        self._update_ui()

    def _update_ui(self):
        results = self.state.results
        compliance = self.state.compliance

        if not results:
            return

        is_compliant = compliance.get("is_compliant", False) if compliance else False
        self.ids.compliance_badge.text = "✅ UYGUN" if is_compliant else "❌ UYGUN DEĞİL"
        self.ids.compliance_badge.md_bg_color = (
            (0.2, 0.7, 0.3, 1) if is_compliant else (0.8, 0.2, 0.2, 1)
        )

        self.ids.w_nom_val.text = f"{results.get('w_nom', 0):.2f} mm"
        self.ids.w_eff_val.text = f"{results.get('w_eff', 0):.2f} mm"
        self.ids.u_max_val.text = f"{results.get('u_max', 0):.3f} mm"
        self.ids.sfd_min_val.text = f"{results.get('sfd_min', 0):.0f} mm"
        self.ids.iqi_val.text = str(results.get("single_wire_iqi", {}).get("label", "-"))
        self.ids.time_val.text = f"{results.get('calc_time', 0):.1f} sn"

        checks = compliance.get("checks", []) if compliance else []
        self.ids.compliance_container.clear_widgets()
        for c in checks:
            status = "🟢" if c.get("status") else "🔴"
            label = f"{status} {c.get('name', '')}: {c.get('details', '')}"
            self.ids.compliance_container.add_widget(
                MDLabel(text=label, size_hint_y=None, height=dp(28))
            )

    def open_defect_menu(self):
        items = [{
            "text": self.state.get_text(d),
            "on_release": lambda v=d: self._select_defect(v)
        } for d in DEFECT_TYPES]
        menu = MDDropdownMenu(
            caller=self.ids.defect_type_btn,
            items=items,
            width_mult=4,
        )
        menu.open()

    def _select_defect(self, value):
        self.state.set("defect_type", value)
        self.ids.defect_type_btn.text = self.state.get_text(value)
        self.ids.defect_result_label.text = ""

    def on_defect_length(self, text):
        try:
            self.state.set("defect_length", float(text.replace(",", ".")))
        except ValueError:
            pass

    def on_defect_width(self, text):
        try:
            self.state.set("defect_width", float(text.replace(",", ".")))
        except ValueError:
            pass

    def on_defect_accum(self, text):
        try:
            self.state.set("defect_accum", float(text.replace(",", ".")))
        except ValueError:
            pass

    def evaluate_defect(self):
        dt = self.state.get("defect_type", "crack")
        length = self.state.get("defect_length", 0)
        width = self.state.get("defect_width", 0)
        accum = self.state.get("defect_accum", 0)
        result = self.state.evaluate_defect(dt, length, width, accum)
        if result:
            status = "✅ ACCEPT" if result.get("status") else "❌ RED"
            details = result.get("result", "")
            self.ids.defect_result_label.text = f"{status}: {details}"

    def generate_report(self):
        try:
            from lib.pdf_helper import generate_mobile_pdf, get_pdf_path, share_pdf
            path = get_pdf_path()
            sketch_path = None
            try:
                sketch_path = self.manager.get_screen("sketch").ids.canvas.save_to_png(
                    path.replace(".pdf", "_sketch.png")
                )
            except Exception:
                pass
            ok = generate_mobile_pdf(
                path, self.state, self.state.results,
                self.state.compliance, self.state.defect_eval, sketch_path,
            )
            if ok:
                self._show_dialog("Rapor", f"Rapor kaydedildi:\n{path}")
                share_pdf(path)
            else:
                self._show_dialog("Hata", "Rapor oluşturulamadı")
        except Exception as e:
            self._show_dialog("Hata", f"Rapor oluşturulamadı: {e}")

    def _show_dialog(self, title, text):
        if self._dialog:
            self._dialog.dismiss()
        self._dialog = MDDialog(title=title, text=text, buttons=[("OK", lambda x: self._dialog.dismiss())])
        self._dialog.open()

    def on_next(self):
        self.manager.current = "sketch"

    def on_back(self):
        self.manager.current = "exposure"
