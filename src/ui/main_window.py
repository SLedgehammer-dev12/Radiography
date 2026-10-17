# -*- coding: utf-8 -*-

import os
import html
import json
import logging
from PyQt6.QtWidgets import (QMainWindow, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QMessageBox, QFormLayout, QDialog,
                             QProgressDialog, QSplitter)
from PyQt6.QtCore import Qt, QThread, QSettings, pyqtSignal, QUrl
from PyQt6.QtGui import QDoubleValidator, QAction, QDesktopServices

from src.core.translation import Translation
from src.core.calculator import RTCalculator
from src.core.engine import (CalculationEngine, GEOMETRY_KEYS)
from src.core.exposure_charts import ExposureChartDatabase, resource_path
from src.core.api1104 import API1104Evaluator
from src.ui.compensation import Level3Dialog
from src.core.report import PDFReportGenerator
from src.core.procedure_check import ProcedureComplianceChecker
from src.core.updater import UpdateChecker, GITHUB_REPO
from src.core.version import __version__ as CURRENT_VERSION
from src.core.asme_b36 import ASME_B36_10_PIPES
from src.ui.panels.input_panel import InputPanelMixin
from src.ui.panels.defect_panel import DefectPanelMixin
from src.ui.panels.form_state_panel import FormStateMixin
from src.ui.panels.report_panel import ReportExportMixin
from src.ui.panels.translation_panel import TranslationMixin
from src.ui.panels.ui_build_panel import UIBuildMixin
from src.ui.panels.warnings_compliance_panel import WarningsPanelMixin, CompliancePanelMixin


logger = logging.getLogger("radiography.ui.main_window")


class MainWindow(QMainWindow,
                  UIBuildMixin,
                  InputPanelMixin,
                  DefectPanelMixin,
                  ReportExportMixin,
                  TranslationMixin,
                  FormStateMixin,
                  WarningsPanelMixin,
                  CompliancePanelMixin):
    # Cache of the last application-wide stylesheet, so the heavy
    # app.setStyleSheet() re-polish is only done when the theme actually changes.
    _app_css_cache = None

    def __init__(self):
        super().__init__()
        
        # Core engines
        self.trans = Translation()
        self.calc = RTCalculator()
        self.api_eval = API1104Evaluator()
        self.pdf_gen = PDFReportGenerator()
        self.proc_checker = ProcedureComplianceChecker()
        json_path = resource_path("exposure_chart_dataset.json")
        if os.path.exists(json_path):
            self.chart_db = ExposureChartDatabase(json_path)
        else:
            self.chart_db = ExposureChartDatabase()
            self.chart_db.generate_type_x_chart(self.calc)
        # Shared calculation engine: the single source of truth for the
        # calculation chain (also used by the mobile and web front-ends).
        self.engine = CalculationEngine(calc=self.calc, proc_checker=self.proc_checker,
                                        chart_db=self.chart_db)
        self.last_calculated = {}

        # State variables
        self.is_dark_theme = True
        self.use_inch = False
        self.lvl3_settings = {
            "sfd_comp": False,
            "voltage_override": False,
            "isotope_flex": False,
            "source_flex": False,
            "central_proj_reduction": False,
            "dw_reduction": False,
            "approval_note": ""
        }

        # QSettings persistence
        self._settings = QSettings("Radiography", "Radiography")

        # Set Window Title and size
        self.setWindowTitle(self.trans.get("app_title"))
        self.setMinimumSize(1200, 800)
        
        # Init layout
        self.init_ui()
        self._setup_menu_bar()

        # Restore persistent settings
        self._restore_settings()

        self.apply_theme()
        
        # Initialize standard figure list
        self.update_std_figure_list()
        
        # Start with the planar/rigid detector model (bed/bgap visible)
        self.txt_bed.setVisible(True)
        self.txt_bgap.setVisible(True)

        # Hide user geometry overrides until digital + relevant tech is confirmed
        self.lbl_f_source.setVisible(True)
        self.txt_f_source.setVisible(True)
        self.lbl_b_object.setVisible(True)
        self.txt_b_object.setVisible(True)

        # Trigger initial calculations. Always run: restored radios/combos are
        # applied with signals blocked, so the engine must be refreshed once the
        # full restored state is in place.
        self.update_calculations()

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _save_settings(self):
        s = self._settings
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state", self.saveState())
        s.setValue("window/is_dark_theme", self.is_dark_theme)

        # Splitter sizes
        for name in ("left_splitter",):
            w = getattr(self, name, None)
            if w:
                s.setValue(f"splitter/{name}", w.sizes())

        # Middle and right splitters
        for child in self.findChildren(QSplitter):
            obj_name = child.objectName() or ""
            if obj_name:
                s.setValue(f"splitter/{obj_name}", child.sizes())

        # Language
        s.setValue("ui/language", self.trans.language)

        # Form combo indices
        combo_map = {
            "cmb_material": None,
            "cmb_source": None,
            "cmb_class": None,
            "cmb_od": None,
            "cmb_t": None,
            "cmb_geometry": None,
            "cmb_film_class_used": None,
            "cmb_detector_type": None,
            "cmb_chart_source": None,
            "cmb_standard": None,
            "cmb_collimator": None,
            "cmb_gamma_convention": None,
            "cmb_asme_sensitivity": None,
            "cmb_activity_unit": None,
            "cmb_iqi_type": None,
            "cmb_snr_location": None,
            "cmb_app_wire": None,
            "cmb_app_duplex": None,
            "cmb_film_size": None,
        }
        for combo_name in combo_map:
            w = getattr(self, combo_name, None)
            if w:
                s.setValue(f"form/{combo_name}", w.currentIndex())

        # Form line edits
        line_edits = {
            "txt_custom_od": "",
            "txt_custom_t": "",
            "txt_cap": "3.0",
            "txt_weld_width": "8.0",
            "txt_d": "2.0",
            "txt_app_sfd": "600.0",
            "txt_output": "5.0",
            "txt_app_activity": "40.0",
            "txt_base_e": "3.0",
            "txt_barrier_limit": "20.0",
            "txt_report_no": "",
            "txt_report_rev": "",
            "txt_project": "",
            "txt_welder_id": "",
            "txt_joint_id": "",
            "txt_wps_pqr": "",
            "txt_lvl2_name": "",
            "txt_lvl2_cert": "",
            "txt_lvl3_name": "",
            "txt_lvl3_cert": "",
            "txt_procedure_no": "",
            "txt_device_serial": "",
            "txt_calibration_date": "",
            "txt_personnel": "",
            "txt_panel_width": "200.0",
            "txt_panel_height": "200.0",
            "txt_panel_overlap": "",
            "txt_app_exposures": "6",
            "txt_base_multiplier": "1.0",
            "txt_f_source": "",
            "txt_b_object": "",
            "txt_app_kv": "120.0",
            "txt_app_time": "120.0",
            "txt_app_overlap": "10.0",
            "txt_app_srb": "80.0",
            "txt_app_quality": "140",
            "txt_film_width": "100.0",
            "txt_film_height": "400.0",
            "txt_bed": "0.0",
            "txt_bgap": "5.0",
        }
        for le_name, default_val in line_edits.items():
            w = getattr(self, le_name, None)
            if w:
                val = w.text()
                if val != default_val or s.contains(f"form/{le_name}"):
                    s.setValue(f"form/{le_name}", val)

        # Radio buttons / checkboxes (technology mode, detector shape, IQI side)
        for name in ("rad_analog", "rad_digital", "rad_detector_flat",
                     "rad_detector_curved", "chk_source_side_iqi"):
            w = getattr(self, name, None)
            if w is not None:
                s.setValue(f"form/{name}", bool(w.isChecked()))

        # Unit mode — required so saved dimensional values are read back in the
        # same unit they were entered.
        s.setValue("ui/use_inch", bool(self.use_inch))

    def _restore_settings(self):
        self._restored_settings = False
        s = self._settings

        # Window geometry & state
        geom = s.value("window/geometry")
        if geom is not None:
            self.restoreGeometry(geom)
            self._restored_settings = True
        state = s.value("window/state")
        if state is not None:
            self.restoreState(state)

        # Theme
        theme_val = s.value("window/is_dark_theme", type=bool)
        if theme_val is not None:
            self.is_dark_theme = theme_val

        # Splitter sizes
        for child in self.findChildren(QSplitter):
            obj_name = child.objectName() or ""
            if obj_name:
                val = s.value(f"splitter/{obj_name}")
                if val is not None:
                    child.setSizes([int(v) for v in val])
        left_sizes = s.value("splitter/left_splitter")
        if left_sizes is not None:
            self.left_splitter.setSizes([int(v) for v in left_sizes])

        # Language
        lang = s.value("ui/language")
        if lang is not None and lang in ("tr", "en"):
            self.trans.set_language(lang)
            self.retranslate_ui()

        # Form combo indices
        combo_map = [
            "cmb_material", "cmb_source", "cmb_class", "cmb_od",
            "cmb_t", "cmb_geometry", "cmb_film_class_used",
            "cmb_detector_type", "cmb_chart_source",
            "cmb_standard", "cmb_collimator", "cmb_gamma_convention",
            "cmb_asme_sensitivity", "cmb_activity_unit",
            "cmb_iqi_type", "cmb_snr_location", "cmb_app_wire",
            "cmb_app_duplex", "cmb_film_size",
        ]
        for combo_name in combo_map:
            idx = s.value(f"form/{combo_name}", type=int)
            if idx is not None:
                w = getattr(self, combo_name, None)
                if w and 0 <= idx < w.count():
                    w.blockSignals(True)
                    w.setCurrentIndex(idx)
                    w.blockSignals(False)

        # Keep the tracked activity unit in sync with the restored selection so
        # the next toggle converts from the correct unit.
        if hasattr(self, "cmb_activity_unit"):
            self._activity_unit = self.cmb_activity_unit.currentText()

        # Radio buttons / checkboxes (technology mode, detector shape, IQI side)
        for name in ("rad_analog", "rad_digital", "rad_detector_flat",
                     "rad_detector_curved", "chk_source_side_iqi"):
            w = getattr(self, name, None)
            if w is None or not s.contains(f"form/{name}"):
                continue
            w.blockSignals(True)
            w.setChecked(s.value(f"form/{name}", type=bool))
            w.blockSignals(False)

        # Unit mode (set before line edits so conversion uses the right mode)
        use_inch = s.value("ui/use_inch")
        if use_inch is not None:
            self.use_inch = str(use_inch).lower() in ("true", "1")
            self.btn_units.setText("inç" if self.use_inch else "mm")

        # Form line edits
        line_edits = [
            "txt_custom_od", "txt_custom_t", "txt_cap", "txt_weld_width", "txt_d",
            "txt_app_sfd", "txt_output", "txt_app_activity", "txt_base_e",
            "txt_barrier_limit",
            "txt_report_no", "txt_report_rev", "txt_project", "txt_welder_id", "txt_joint_id", "txt_wps_pqr",
            "txt_lvl2_name", "txt_lvl2_cert", "txt_lvl3_name", "txt_lvl3_cert",
            "txt_procedure_no", "txt_device_serial", "txt_calibration_date", "txt_personnel",
            "txt_panel_width", "txt_panel_height", "txt_panel_overlap",
            "txt_app_exposures", "txt_base_multiplier", "txt_f_source",
            "txt_b_object",
            "txt_app_kv", "txt_app_time", "txt_app_overlap", "txt_app_srb",
            "txt_app_quality", "txt_film_width", "txt_film_height",
            "txt_bed", "txt_bgap",
        ]
        for le_name in line_edits:
            val = s.value(f"form/{le_name}")
            if val is not None:
                w = getattr(self, le_name, None)
                if w:
                    w.setText(val)

    def on_activity_unit_changed(self):
        """Converts the displayed activity when the unit toggles Ci <-> GBq.

        The combo reports only the new unit, so the previous unit is tracked in
        ``self._activity_unit``. Both directions must convert (1 Ci = 37 GBq),
        and signal blocking must always be paired with an unblock.
        """
        new_unit = self.cmb_activity_unit.currentText()
        prev_unit = getattr(self, "_activity_unit", new_unit)
        if new_unit != prev_unit:
            try:
                val = float(self.txt_app_activity.text().replace(",", "."))
            except ValueError:
                val = None
            if val is not None:
                if prev_unit == "Ci" and new_unit == "GBq":
                    val *= 37.0
                elif prev_unit == "GBq" and new_unit == "Ci":
                    val /= 37.0
                self.txt_app_activity.blockSignals(True)
                self.txt_app_activity.setText(f"{val:.1f}")
                self.txt_app_activity.blockSignals(False)
        self._activity_unit = new_unit
        self.update_calculations()

    def on_detector_type_changed(self):
        is_digital = self.rad_digital.isChecked()
        # Planar/rigid detectors need the edge lift (bed) and gap (bgap) inputs;
        # flexible detectors wrapped on the pipe do not.
        is_planar = is_digital and hasattr(self, 'rad_detector_flat') and self.rad_detector_flat.isChecked()
        if hasattr(self, 'lbl_bed'):
            self.lbl_bed.setVisible(is_planar)
            self.txt_bed.setVisible(is_planar)
            self.lbl_bgap.setVisible(is_planar)
            self.txt_bgap.setVisible(is_planar)
        # The available standard figures depend on the detector shape
        self.update_std_figure_list()
        self.update_calculations()

    def _update_output_visibility(self):
        if not hasattr(self, 'out_rows') or not self.out_rows:
            return
        is_digital = self.rad_digital.isChecked()
        is_xray = (self.cmb_source.currentIndex() == 0)

        # u_max only visible for X-Ray (isotopes do not have tube voltage)
        if "u_max" in self.out_rows:
            self.out_rows["u_max"].setVisible(is_xray)

        # duplex_iqi only visible for digital
        if "duplex_iqi" in self.out_rows:
            self.out_rows["duplex_iqi"].setVisible(is_digital)

        # exposures_panel only visible for digital
        if "exposures_panel" in self.out_rows:
            self.out_rows["exposures_panel"].setVisible(is_digital)

        # exposures_applied and exposures_check visible for both analog & digital
        if "exposures_applied" in self.out_rows:
            self.out_rows["exposures_applied"].setVisible(True)
        if "exposures_check" in self.out_rows:
            self.out_rows["exposures_check"].setVisible(True)

        # Dynamic output labels
        if "quality_target" in self.out_labels:
            target_name = "target_snr" if is_digital else "optical_density"
            self.out_labels["quality_target"][0].setText(self.trans.get(target_name))

        if "detector_quality" in self.out_labels:
            dq_name = "detector_quality" if is_digital else "film_class_req"
            self.out_labels["detector_quality"][0].setText(self.trans.get(dq_name))

        # SFD_min (analog) vs SDD_min (digital) row label
        if "sfd_min" in self.out_labels:
            self.out_labels["sfd_min"][0].setText(
                self.trans.get("sfd_min" if is_digital else "sfd_min_analog"))

        # Applied source-to-receptor distance label
        if hasattr(self, "lbl_app_sfd"):
            self.lbl_app_sfd.setText(
                self.trans.get("applied_sdd" if is_digital else "applied_sfd"))

        # asme_iqi only when ASME Sec V Art 2 standard is selected
        standard = self.cmb_standard.currentData() if hasattr(self, "cmb_standard") else "iso"
        if "asme_iqi" in self.out_rows:
            self.out_rows["asme_iqi"].setVisible(standard == "asme")

        # ASME-derived f_min row only when ASME is selected
        if "f_min_asme" in self.out_rows:
            self.out_rows["f_min_asme"].setVisible(standard == "asme")

        # barrier_distance only for isotopes
        if "barrier_distance" in self.out_rows:
            self.out_rows["barrier_distance"].setVisible(not is_xray)

    def on_tech_changed(self):
        is_digital = self.rad_digital.isChecked()

        # Show/hide detector selector vs film class selector
        self.lbl_detector_type.setVisible(is_digital)
        self.cmb_detector_type.setVisible(is_digital)
        self.lbl_film_class_used.setVisible(not is_digital)
        self.cmb_film_class_used.setVisible(not is_digital)

        # Overlap inputs visibility
        self.lbl_app_overlap.setVisible(not is_digital)
        self.txt_app_overlap.setVisible(not is_digital)

        # SRb, duplex inputs visibility
        self.lbl_app_srb.setVisible(is_digital)
        self.txt_app_srb.setVisible(is_digital)
        self.lbl_app_duplex.setVisible(is_digital)
        self.cmb_app_duplex.setVisible(is_digital)
        self.lbl_snr_location.setVisible(is_digital)
        self.cmb_snr_location.setVisible(is_digital)

        # Panel coverage inputs visibility (digital only)
        self.lbl_panel_width.setVisible(is_digital)
        self.txt_panel_width.setVisible(is_digital)
        self.lbl_panel_height.setVisible(is_digital)
        self.txt_panel_height.setVisible(is_digital)
        self.lbl_panel_overlap.setVisible(is_digital)
        self.txt_panel_overlap.setVisible(is_digital)

        # Applied exposures input is visible for both analog and digital!
        self.lbl_app_exposures.setVisible(True)
        self.txt_app_exposures.setVisible(True)

        # User geometry overrides visibility (digital only)
        self.lbl_f_source.setVisible(is_digital)
        self.txt_f_source.setVisible(is_digital)
        self.lbl_b_object.setVisible(is_digital)
        self.txt_b_object.setVisible(is_digital)

        # Input panel digital elements
        if hasattr(self, 'lbl_det_shape'):
            self.lbl_det_shape.setVisible(is_digital)
            self.det_type_widget.setVisible(is_digital)
        # Analog film sheet dimensions (df) / digital panel active area (dd)
        if hasattr(self, 'lbl_film_size'):
            self.lbl_film_size.setVisible(not is_digital)
            self.cmb_film_size.setVisible(not is_digital)
            self.lbl_film_width.setVisible(not is_digital)
            self.txt_film_width.setVisible(not is_digital)
            self.lbl_film_height.setVisible(not is_digital)
            self.txt_film_height.setVisible(not is_digital)
        is_planar = is_digital and hasattr(self, 'rad_detector_flat') and self.rad_detector_flat.isChecked()
        if hasattr(self, 'lbl_bed'):
            self.lbl_bed.setVisible(is_planar)
            self.txt_bed.setVisible(is_planar)
            self.lbl_bgap.setVisible(is_planar)
            self.txt_bgap.setVisible(is_planar)

        # Figure list and chart source list depend on technology and detector type
        self.update_std_figure_list()
        self.update_chart_source_list()
        
        # Also update procedure compliance label and default value
        if is_digital:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (SNR_N):")
            self.txt_app_quality.setValidator(QDoubleValidator(0.1, 1000.0, 1))
            try:
                val = float(self.txt_app_quality.text().replace(",", "."))
                if val < 5.0:
                    self.txt_app_quality.setText("140")
            except ValueError:
                self.txt_app_quality.setText("140")
        else:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (D):")
            self.txt_app_quality.setValidator(QDoubleValidator(0.1, 5.0, 2))
            try:
                val = float(self.txt_app_quality.text().replace(",", "."))
                if val >= 5.0:
                    self.txt_app_quality.setText("2.5")
            except ValueError:
                self.txt_app_quality.setText("2.5")

        self._update_output_visibility()
        self.update_calculations()

    def on_detector_model_changed(self):
        self.update_chart_source_list()
        self.update_calculations()

    def update_chart_source_list(self):
        """Populates cmb_chart_source with Analog Film charts or Digital CR/DDA methods based on radiation source."""
        if not hasattr(self, "cmb_chart_source"):
            return
        is_digital = self.rad_digital.isChecked() if hasattr(self, "rad_digital") else True
        source_idx = self.cmb_source.currentIndex() if hasattr(self, "cmb_source") else 0
        is_xray = (source_idx == 0)
        det_type = (
            self.cmb_detector_type.currentData()
            if hasattr(self, "cmb_detector_type")
            else "cr_standard"
        )
        is_dda = det_type in ("dda_si", "dda_se", "dda_gdos")
        prev_data = self.cmb_chart_source.currentData()

        if hasattr(self, "lbl_chart_source"):
            self.lbl_chart_source.setText(
                self.trans.get("chart_source_digital" if is_digital else "chart_source")
            )

        self.cmb_chart_source.blockSignals(True)
        self.cmb_chart_source.clear()

        if is_digital:
            self.cmb_chart_source.addItem(self.trans.get("chart_digital_model"), "model")
            if is_dda:
                self.cmb_chart_source.addItem(self.trans.get("chart_dda_frame"), "dda_frame_method")
                self.cmb_chart_source.addItem(self.trans.get("chart_dda_panel"), "dda_panel_chart")
                if is_xray:
                    self.cmb_chart_source.addItem(self.trans.get("chart_digital_xray"), "digital_xray_chart")
            else:
                if not is_xray:
                    self.cmb_chart_source.addItem(self.trans.get("chart_cr_ips"), "cr_ips_chart")
                else:
                    self.cmb_chart_source.addItem(self.trans.get("chart_digital_xray"), "digital_xray_chart")
        else:
            self.cmb_chart_source.addItem(self.trans.get("chart_model"), "model")
            if is_xray:
                self.cmb_chart_source.addItem(self.trans.get("chart_type_x"), "type_x")
            else:
                self.cmb_chart_source.addItem("AA400 (C5)", "AA400")
                self.cmb_chart_source.addItem("MX125 (C3)", "MX125")
                self.cmb_chart_source.addItem("T200 (C4)", "T200")
                self.cmb_chart_source.addItem("HS800 (C6)", "HS800")
                self.cmb_chart_source.addItem("M100 (C2)", "M100")

        idx = self.cmb_chart_source.findData(prev_data)
        if idx >= 0:
            self.cmb_chart_source.setCurrentIndex(idx)
        else:
            if is_digital:
                self.cmb_chart_source.setCurrentIndex(0)
            else:
                if is_xray:
                    type_x_idx = self.cmb_chart_source.findData("type_x")
                    self.cmb_chart_source.setCurrentIndex(type_x_idx if type_x_idx >= 0 else 0)
                else:
                    aa400_idx = self.cmb_chart_source.findData("AA400")
                    self.cmb_chart_source.setCurrentIndex(aa400_idx if aa400_idx >= 0 else 0)

        self.cmb_chart_source.blockSignals(False)
        self._update_base_e()

    def _update_base_e(self):
        """Refreshes the exposure chart constant (E) label, tooltip and visibility.

        E is only used by the physics model; when a manufacturer chart is
        selected the field is hidden because the chart path ignores E.
        """
        unit = "mA·min/m²" if self.cmb_source.currentIndex() == 0 else "Ci·min/m²"
        self.lbl_base_e.setText(f"{self.trans.get('base_factor')} ({unit}):")
        self.txt_base_e.setToolTip(self.trans.get("tt_base_factor"))
        chart = self.cmb_chart_source.currentData()
        visible = chart in ("model", "dda_frame_method")
        self.lbl_base_e.setVisible(visible)
        self.txt_base_e.setVisible(visible)

    def on_source_changed(self):
        source_idx = self.cmb_source.currentIndex()
        if source_idx == 0:  # X-Ray
            self.lbl_output.setText(self.trans.get("amperage"))
            if not self.txt_output.text():
                self.txt_output.setText("5.0")
            self.txt_base_e.setText("3.0")
            self._update_base_e()
            if hasattr(self, 'lbl_focal_size'):
                self.lbl_focal_size.setText(self.trans.get("focal_size"))
            
            # Show Tube Amperage & Voltage, Hide Activity
            self.lbl_output.setVisible(True)
            self.txt_output.setVisible(True)
            self.lbl_app_kv.setVisible(True)
            self.txt_app_kv.setVisible(True)
            self.lbl_app_activity.setVisible(False)
            if hasattr(self, 'act_widget'):
                self.act_widget.setVisible(False)
            else:
                self.txt_app_activity.setVisible(False)
            if hasattr(self, 'lbl_collimator'):
                self.lbl_collimator.setVisible(False)
                self.cmb_collimator.setVisible(False)
                self.lbl_barrier_limit.setVisible(False)
                self.txt_barrier_limit.setVisible(False)
                self.lbl_gamma_convention.setVisible(False)
                self.cmb_gamma_convention.setVisible(False)
                self.btn_decay.setVisible(False)
        else: # Isotopes
            # Hide Amperage & Voltage, Show Activity
            self.lbl_output.setVisible(False)
            self.txt_output.setVisible(False)
            self.lbl_app_kv.setVisible(False)
            self.txt_app_kv.setVisible(False)
            self.lbl_app_activity.setVisible(True)
            if hasattr(self, 'act_widget'):
                self.act_widget.setVisible(True)
            else:
                self.txt_app_activity.setVisible(True)

            if hasattr(self, 'lbl_collimator'):
                self.lbl_collimator.setVisible(True)
                self.cmb_collimator.setVisible(True)
                self.lbl_barrier_limit.setVisible(True)
                self.txt_barrier_limit.setVisible(True)
                self.lbl_gamma_convention.setVisible(True)
                self.cmb_gamma_convention.setVisible(True)
                self.btn_decay.setVisible(True)

            self._update_base_e()
            if hasattr(self, 'lbl_focal_size'):
                self.lbl_focal_size.setText(self.trans.get("source_size_d"))

            if not self.txt_app_activity.text():
                unit = self.cmb_activity_unit.currentText() if hasattr(self, 'cmb_activity_unit') else "Ci"
                self.txt_app_activity.setText("1480.0" if unit == "GBq" else "40.0")

            # Set base factor default per isotope
            if source_idx == 1:   # Ir-192
                self.txt_base_e.setText("30.0")
            elif source_idx == 2:  # Se-75
                self.txt_base_e.setText("40.0")
            elif source_idx == 3:  # Co-60
                self.txt_base_e.setText("20.0")
            elif source_idx == 4:  # Yb-169
                self.txt_base_e.setText("150.0")
            else:                  # Tm-170
                self.txt_base_e.setText("500.0")

        self.update_chart_source_list()
        self.update_calculations()

    def on_chart_source_changed(self):
        chart_source = self.cmb_chart_source.currentData()
        if chart_source in ("type_x", "digital_xray_chart"):
            if self.cmb_source.currentIndex() != 0:
                self.cmb_source.setCurrentIndex(0)
            self.txt_app_kv.setVisible(True)
            self.lbl_app_kv.setVisible(True)
        elif chart_source == "model":
            pass
        # E is only meaningful in the physics model -> hide when a chart is used
        self._update_base_e()
        self.update_calculations()

    def on_od_changed(self):
        self.populate_standard_thicknesses()
        self.update_calculations()

    def populate_standard_thicknesses(self):
        key = self.cmb_od.currentData()
        if not key or key not in ASME_B36_10_PIPES:
            return

        self.cmb_t.blockSignals(True)
        self.cmb_t.clear()

        od_val, schedules = ASME_B36_10_PIPES[key]
        for t_val, sch_label in schedules:
            self.cmb_t.addItem(f"{sch_label} ({t_val:.2f} mm)", t_val)

        # Select the thickness closest to 8.56 mm by default
        default_idx = 0
        min_diff = float('inf')
        for i in range(self.cmb_t.count()):
            t_val = self.cmb_t.itemData(i)
            if t_val is not None:
                diff = abs(t_val - 8.56)
                if diff < min_diff:
                    min_diff = diff
                    default_idx = i

        self.cmb_t.setCurrentIndex(default_idx)
        self.cmb_t.blockSignals(False)

    def on_geometry_changed(self):
        self.update_std_figure_list()
        self.update_calculations()

    def _update_weld_width_visibility(self, geometry=None):
        """Shows the weld-width input only for DWDI techniques."""
        if not hasattr(self, 'lbl_weld_width'):
            return
        if geometry is None:
            geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
            geometry = geom_keys[self.cmb_geometry.currentIndex()]
        visible = geometry in ["dwdi_elliptic", "dwdi_super"]
        self.lbl_weld_width.setVisible(visible)
        self.txt_weld_width.setVisible(visible)

    def update_std_figure_list(self):
        # Prevent recursion by temporarily disconnecting the signal
        self.cmb_std_figure.blockSignals(True)

        # Get selected geometry
        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]

        # Save previous selection
        prev_data = self.cmb_std_figure.currentData()

        is_digital = self.rad_digital.isChecked() if hasattr(self, "rad_digital") else True
        is_planar = is_digital and (
            self.rad_detector_flat.isChecked() if hasattr(self, "rad_detector_flat") else True)

        self.cmb_std_figure.clear()

        def add(key, data):
            self.cmb_std_figure.addItem(self.trans.get(key), data)

        # Butt-weld arrangements only: Figures 6/7/9/10 (and the digital
        # a/b equivalents) are set-in/set-on corner welds and are excluded.
        if is_digital:
            if geometry == "swsi":
                if is_planar:
                    add("fig2b_title", "fig2b")
                    add("fig5b_title", "fig5b")
                    add("fig8b_title", "fig8b")
                else:
                    add("fig2a_title", "fig2a")
                    add("fig5a_title", "fig5a")
                    add("fig8a_title", "fig8a")
            elif geometry in ["dwdi_elliptic", "dwdi_super"]:
                add("fig11_title", "fig11")
                add("fig12_title", "fig12")
            else:  # dwsi
                if is_planar:
                    add("fig13b_title", "fig13b")
                    add("fig14b_title", "fig14b")
                else:
                    add("fig13a_title", "fig13a")
                    add("fig14a_title", "fig14a")
        else:  # analog - ISO 17636-1 film arrangements
            if geometry == "swsi":
                add("fig2_title", "fig2")
                add("fig5_title", "fig5")
                add("fig8_title", "fig8")
            elif geometry in ["dwdi_elliptic", "dwdi_super"]:
                add("fig11_title", "fig11")
                add("fig12_title", "fig12")
            else:  # dwsi
                add("fig13_title", "fig13")
                add("fig14_title", "fig14")

        # Try to restore previous selection
        found = False
        for i in range(self.cmb_std_figure.count()):
            if self.cmb_std_figure.itemData(i) == prev_data:
                self.cmb_std_figure.setCurrentIndex(i)
                found = True
                break
        if not found:
            self.cmb_std_figure.setCurrentIndex(0)

        self._sync_std_figure_tab()

        self.cmb_std_figure.blockSignals(False)
        self.on_std_figure_changed()

    def _sync_std_figure_tab(self):
        tab = getattr(self, "cmb_std_figure_tab", None)
        if tab is None:
            return
        tab.blockSignals(True)
        tab.clear()
        for i in range(self.cmb_std_figure.count()):
            tab.addItem(self.cmb_std_figure.itemText(i), self.cmb_std_figure.itemData(i))
        tab.setCurrentIndex(self.cmb_std_figure.currentIndex())
        tab.blockSignals(False)

    def on_std_figure_tab_changed(self):
        tab = getattr(self, "cmb_std_figure_tab", None)
        if tab is None:
            return
        idx = self.cmb_std_figure.findData(tab.currentData())
        if idx >= 0 and idx != self.cmb_std_figure.currentIndex():
            self.cmb_std_figure.blockSignals(True)
            self.cmb_std_figure.setCurrentIndex(idx)
            self.cmb_std_figure.blockSignals(False)
        self.on_std_figure_changed()

    def on_std_figure_changed(self):
        fig_name = self.cmb_std_figure.currentData()
        if fig_name:
            self.std_canvas.draw_figure(fig_name, self.trans, self.is_dark_theme)

    def on_iqi_type_changed(self):
        # Prevent recursive calculation triggers while reloading items
        self.cmb_app_wire.blockSignals(True)
        self.cmb_app_wire.clear()
        
        iqi_type = self.cmb_iqi_type.currentData()
        if iqi_type == "step_hole":
            self.lbl_app_wire.setText(self.trans.get("applied_step_hole"))
            # H1 to H18
            for h_no in sorted(self.calc.step_hole_dias.keys()):
                self.cmb_app_wire.addItem(f"H {h_no} ({self.calc.step_hole_dias[h_no]:.3f} mm)", h_no)
            self.cmb_app_wire.setCurrentIndex(9) # default H10
        else: # wire
            self.lbl_app_wire.setText(self.trans.get("applied_wire"))
            for w_no in sorted(self.calc.wire_diameters.keys()):
                self.cmb_app_wire.addItem(f"W {w_no} ({self.calc.wire_diameters[w_no]:.3f} mm)", w_no)
            self.cmb_app_wire.setCurrentIndex(9) # default W10
            
        self.cmb_app_wire.blockSignals(False)
        self.update_calculations()

    def toggle_language(self):
        new_lang = "en" if self.trans.language == "tr" else "tr"
        self.trans.set_language(new_lang)
        self.retranslate_ui()

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.apply_theme()
        self.btn_theme.setText(self.trans.get("theme_light") if self.is_dark_theme else self.trans.get("theme_dark"))
        self.canvas.set_theme(self.is_dark_theme)
        self.std_canvas.set_theme(self.is_dark_theme)
        self.on_std_figure_changed()
        self.update_calculations()

    # Main dimensional inputs that participate in the mm <-> inch toggle.
    _MM_FIELDS = [
        "txt_custom_od", "txt_custom_t", "txt_cap", "txt_weld_width",
        "txt_d", "txt_app_sfd", "txt_bed", "txt_bgap",
        "txt_film_width", "txt_film_height",
        "txt_panel_width", "txt_panel_height", "txt_app_overlap",
        "txt_f_source", "txt_b_object",
        "txt_defect_length", "txt_defect_width", "txt_defect_accum",
    ]

    def _to_mm(self, value):
        """Converts a value to mm when the inch unit mode is active."""
        return value * 25.4 if self.use_inch else value

    def toggle_units(self):
        """Switches the displayed unit of the main dimensional inputs."""
        self.use_inch = not self.use_inch
        # mm -> in: /25.4 ; in -> mm: *25.4
        factor = (1.0 / 25.4) if self.use_inch else 25.4
        for attr in self._MM_FIELDS:
            w = getattr(self, attr, None)
            if w is None:
                continue
            try:
                val = float(w.text().strip().replace(",", "."))
            except ValueError:
                continue
            w.blockSignals(True)
            w.setText(f"{val * factor:.2f}")
            w.blockSignals(False)
        self.btn_units.setText("inç" if self.use_inch else "mm")
        self.update_calculations()

    def open_decay_dialog(self):
        """Isotope decay tool: computes the current activity from the initial
        activity and calibration date, and can apply it to the form."""
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60",
                       "isotope_yb169", "isotope_tm170"]
        source = source_keys[self.cmb_source.currentIndex()]
        if source == "x_ray":
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(self.trans.get("decay_dialog"))
        form = QFormLayout(dlg)
        txt_serial = QLineEdit()
        txt_serial.setPlaceholderText("Ir-192 / Sn 12345")
        txt_a0 = QLineEdit("40.0")
        txt_calib = QLineEdit("")
        txt_calib.setPlaceholderText("YYYY-MM-DD")
        lbl_current = QLabel("-")

        def _update():
            try:
                a0 = float(txt_a0.text().strip().replace(",", "."))
            except ValueError:
                lbl_current.setText("-")
                return
            try:
                current = self.calc.calculate_decayed_activity(
                    a0, txt_calib.text().strip(), None, source)
            except Exception:
                logger.exception("Isotope decay tool update failed")
                lbl_current.setText("-")
                return
            lbl_current.setText(f"{current:.1f} Ci")

        txt_a0.textChanged.connect(lambda *_: _update())
        txt_calib.textChanged.connect(lambda *_: _update())
        form.addRow(self.trans.get("decay_serial"), txt_serial)
        form.addRow(self.trans.get("decay_initial"), txt_a0)
        form.addRow(self.trans.get("decay_calib_date"), txt_calib)
        form.addRow(self.trans.get("decay_current"), lbl_current)

        def _apply():
            try:
                current = self.calc.calculate_decayed_activity(
                    float(txt_a0.text().strip().replace(",", ".")),
                    txt_calib.text().strip(), None, source)
            except Exception:
                current = 0.0
            if current > 0.0:
                unit = self.cmb_activity_unit.currentText() if hasattr(self, "cmb_activity_unit") else "Ci"
                self.txt_app_activity.setText(
                    f"{current * 37.0:.1f}" if unit == "GBq" else f"{current:.1f}")
            dlg.accept()

        btn_apply = QPushButton(self.trans.get("decay_apply"))
        btn_cancel = QPushButton(self.trans.get("dialog_cancel"))
        btn_apply.clicked.connect(_apply)
        btn_cancel.clicked.connect(dlg.reject)
        form.addRow(btn_apply, btn_cancel)
        _update()
        dlg.exec()

    def open_level3_dialog(self):
        dlg = Level3Dialog(self.trans, self, is_dark=self.is_dark_theme)
        dlg.set_settings(self.lvl3_settings)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.lvl3_settings = dlg.get_settings()
            self.update_calculations()

    def _validate_field(self, widget, min_val, max_val):
        text = widget.text().strip().replace(",", ".")
        if not text:
            widget.setStyleSheet("border: 2px solid orange;")
            widget.setToolTip("Empty field")
        else:
            try:
                val = float(text)
                if val < min_val or val > max_val:
                    widget.setStyleSheet("border: 2px solid red;")
                    widget.setToolTip(f"Value out of range [{min_val}, {max_val}]")
                else:
                    widget.setStyleSheet("")
                    widget.setToolTip("")
            except ValueError:
                widget.setStyleSheet("border: 2px solid red;")
                widget.setToolTip("Invalid number")

    def _setup_input_validation(self):
        fields = [
            (self.txt_custom_od, 1.0, 5000.0),
            (self.txt_custom_t, 0.1, 500.0),
            (self.txt_app_kv, 1.0, 1000.0),
            # Range matches the field validator; the field may hold Ci or GBq
            (self.txt_app_activity, 0.01, 100000.0),
            (self.txt_app_sfd, 10.0, 5000.0),
            (self.txt_d, 0.01, 20.0),
            (self.txt_cap, 0.0, 50.0),
            (self.txt_weld_width, 0.0, 500.0),
            (self.txt_output, 0.01, 1000.0),
            (self.txt_app_time, 0.1, 100000.0),
            (self.txt_base_e, 0.0001, 2000.0),
            (self.txt_barrier_limit, 0.1, 1000.0),
            (self.txt_app_overlap, 0.0, 500.0),
            (self.txt_app_srb, 1.0, 1000.0),
            (self.txt_app_quality, 0.01, 10000.0 if self.rad_digital.isChecked() else 5.0),
            (self.txt_panel_width, 10.0, 2000.0),
            (self.txt_panel_height, 10.0, 2000.0),
            (self.txt_panel_overlap, 0.0, 50.0),
            (self.txt_app_exposures, 1.0, 100.0),
            (self.txt_film_width, 1.0, 2000.0),
            (self.txt_film_height, 1.0, 2000.0),
            (self.txt_bed, 0.0, 500.0),
            (self.txt_bgap, 0.0, 100.0),
            (self.txt_f_source, 1.0, 5000.0),
            (self.txt_b_object, 0.0, 5000.0),
            (self.txt_base_multiplier, 0.01, 100.0),
            (self.txt_defect_length, 0.0, 1000.0),
            (self.txt_defect_width, 0.0, 100.0),
            (self.txt_defect_accum, 0.0, 300.0),
        ]
        for widget, mn, mx in fields:
            widget.textChanged.connect(lambda _, w=widget, lo=mn, hi=mx: self._validate_field(w, lo, hi))

    def get_applied_exposures(self):
        """
        Parses the user-entered applied exposures count.
        Returns int >= 0 (default 0 if empty/invalid).
        """
        if not hasattr(self, 'txt_app_exposures'):
            return 0
        text = self.txt_app_exposures.text().strip().replace(",", ".")
        if not text:
            return 0
        try:
            return max(0, int(float(text)))
        except (ValueError, TypeError):
            return 0

    def get_panel_inputs(self):
        """
        Parses the flat-panel DDA inputs. Blank overlap falls back to 10%.
        Returns (panel_width, panel_height, overlap_percent, applied_exposures).
        """
        def _float(widget, default):
            try:
                return float(widget.text().strip().replace(",", "."))
            except ValueError:
                return default

        panel_width = self._to_mm(max(10.0, _float(self.txt_panel_width, 200.0)))
        panel_height = self._to_mm(max(10.0, _float(self.txt_panel_height, 200.0)))
        overlap = _float(self.txt_panel_overlap, 10.0)
        overlap = max(0.0, min(overlap, 50.0))
        app_exposures = self.get_applied_exposures()
        if app_exposures <= 0:
            app_exposures = 6
        return panel_width, panel_height, overlap, app_exposures

    def get_film_inputs(self):
        """
        Parses the analog film sheet dimensions.
        Returns (width_mm, height_mm, diagonal_mm); diagonal is 0 when the
        dimensions are missing/invalid (ISO 17636-1:2022 df).
        """
        def _float(widget, default):
            try:
                return float(widget.text().strip().replace(",", "."))
            except (ValueError, AttributeError):
                return default

        width = self._to_mm(max(0.0, _float(getattr(self, "txt_film_width", None), 0.0)))
        height = self._to_mm(max(0.0, _float(getattr(self, "txt_film_height", None), 0.0)))
        return width, height, self.calc.calculate_diagonal(width, height)

    def get_geometry_override_inputs(self):
        """
        Parses the user-provided geometry overrides.
        Returns (f_source, b_object) where blank entries are None (auto mode).
        """
        def _float_opt(widget):
            try:
                val = float(widget.text().strip().replace(",", "."))
            except ValueError:
                return None
            if val <= 0.0:
                return None
            return self._to_mm(val)
        return _float_opt(self.txt_f_source), _float_opt(self.txt_b_object)

    def get_base_multiplier(self):
        """Returns the base exposure multiplier (default 1.0)."""
        try:
            val = float(self.txt_base_multiplier.text().strip().replace(",", "."))
        except ValueError:
            return 1.0
        if val <= 0.0:
            return 1.0
        return min(val, 100.0)

    def get_report_info(self):
        """Returns the report/procedure header fields as a dict."""
        info = {}
        for attr, key, _ in self._report_fields:
            w = getattr(self, attr, None)
            info[key] = w.text().strip() if w else ""
        return info

    # --- Presets / project data management ---------------------------------

    _NAMED_PRESETS = {
        "4 inç SCH40 DWDI X-Ray Atölye": {
            "cmb_source": "x_ray", "cmb_geometry": "dwdi_elliptic",
            "cmb_od": '4" (NPS 4)', "txt_custom_od": "", "txt_custom_t": "",
            "txt_output": "5.0", "txt_app_kv": "200",
        },
        "16 inç DWSI Ir-192 Saha": {
            "cmb_source": "isotope_ir192", "cmb_geometry": "dwsi",
            "cmb_od": '16" (NPS 16)', "txt_custom_od": "", "txt_custom_t": "",
            "txt_app_activity": "40.0",
        },
        "2 inç DDA Dijital RT": {
            "rad_digital": True, "rad_analog": False,
            "cmb_geometry": "dwsi", "cmb_od": '2" (NPS 2)',
            "txt_custom_od": "", "txt_custom_t": "",
        },
        "ASME VIII 25 mm SWSI Co-60": {
            "cmb_source": "isotope_co60", "cmb_geometry": "swsi",
            "cmb_standard": "asme", "txt_custom_od": "500", "txt_custom_t": "25",
        },
    }

    def apply_named_preset(self, name):
        preset = self._NAMED_PRESETS.get(name)
        if not preset:
            return
        state = self.collect_form_state()
        state.update(preset)
        self.apply_form_state(state)

    _PRESET_COMBOS = [
        "cmb_material", "cmb_source", "cmb_class", "cmb_od", "cmb_t",
        "cmb_geometry", "cmb_film_class_used", "cmb_detector_type",
        "cmb_chart_source", "cmb_standard", "cmb_collimator", "cmb_iqi_type",
        "cmb_snr_location", "cmb_app_duplex", "cmb_app_wire",
        "cmb_activity_unit", "cmb_std_figure", "cmb_film_size",
    ]
    _PRESET_EDITS = [
        "txt_custom_od", "txt_custom_t", "txt_cap", "txt_weld_width", "txt_d",
        "txt_app_sfd", "txt_output", "txt_app_activity", "txt_base_e",
        "txt_barrier_limit", "txt_report_no", "txt_report_rev", "txt_project",
        "txt_welder_id", "txt_joint_id", "txt_wps_pqr", "txt_lvl2_name",
        "txt_lvl2_cert", "txt_lvl3_name", "txt_lvl3_cert",
        "txt_procedure_no", "txt_device_serial",
        "txt_calibration_date", "txt_personnel", "txt_panel_width",
        "txt_panel_height", "txt_panel_overlap", "txt_app_exposures",
        "txt_base_multiplier", "txt_f_source", "txt_b_object", "txt_app_kv",
        "txt_app_time", "txt_app_overlap", "txt_app_srb", "txt_app_quality",
        "txt_film_width", "txt_film_height", "txt_bed", "txt_bgap",
    ]

    def collect_form_state(self):
        """Serializes the current form state into a JSON-friendly dict."""
        state = {
            "language": self.trans.language,
            "rad_analog": self.rad_analog.isChecked(),
            "rad_digital": self.rad_digital.isChecked(),
            "rad_detector_flat": self.rad_detector_flat.isChecked(),
            "rad_detector_curved": self.rad_detector_curved.isChecked(),
            "chk_source_side_iqi": self.chk_source_side_iqi.isChecked(),
        }
        for attr in self._PRESET_COMBOS:
            w = getattr(self, attr, None)
            if w is not None:
                # Store the data key for the standard figure: its list depends
                # on technology and detector shape, so an index is not stable.
                state[attr] = w.currentData() if attr == "cmb_std_figure" else w.currentIndex()
        for attr in self._PRESET_EDITS:
            w = getattr(self, attr, None)
            if w is None:
                continue
            text = w.text()
            if attr in self._MM_FIELDS and text.strip():
                # Persist dimensional fields in canonical mm so a preset saved
                # in inch mode round-trips correctly on any platform/unit mode.
                try:
                    mm = self._to_mm(float(text.replace(",", ".")))
                except ValueError:
                    state[attr] = text
                else:
                    state[attr] = round(mm, 4)
            else:
                state[attr] = text
        return state

    def apply_form_state(self, state):
        """Restores widget values from a collected state dict."""
        if not isinstance(state, dict):
            return
        if "language" in state and state["language"] in ("tr", "en"):
            self.trans.set_language(state["language"])
        for attr, widget in (("rad_analog", self.rad_analog),
                             ("rad_digital", self.rad_digital),
                             ("rad_detector_flat", self.rad_detector_flat),
                             ("rad_detector_curved", self.rad_detector_curved),
                             ("chk_source_side_iqi", self.chk_source_side_iqi)):
            if attr in state:
                v = state[attr]
                if isinstance(v, str):
                    v = v.lower() in ("1", "true", "yes", "checked")
                widget.setChecked(bool(v))
        for attr in self._PRESET_COMBOS:
            if attr == "cmb_chart_source":
                self.update_chart_source_list()
            w = getattr(self, attr, None)
            val = state.get(attr)
            if w is None or val is None:
                continue
            if isinstance(val, int):
                idx = val
            elif isinstance(val, str):
                idx = w.findData(val)
                if idx < 0:
                    try:
                        idx = int(val)
                    except ValueError:
                        idx = -1
            else:
                idx = w.findData(val)
            if 0 <= idx < w.count():
                w.blockSignals(True)
                w.setCurrentIndex(idx)
                w.blockSignals(False)
        for attr in self._PRESET_EDITS:
            w = getattr(self, attr, None)
            if w is None or attr not in state:
                continue
            raw = state[attr]
            if attr in self._MM_FIELDS and raw not in (None, ""):
                # State is canonical mm; convert to the current display unit.
                try:
                    mm = float(str(raw).replace(",", "."))
                except ValueError:
                    w.setText(str(raw))
                else:
                    display = mm / 25.4 if self.use_inch else mm
                    text_out = f"{display:.4f}".rstrip("0")
                    if text_out.endswith("."):
                        text_out += "0"
                    w.setText(text_out)
            else:
                w.setText(str(raw))
        self.retranslate_ui()
        self.update_calculations()

    def save_form_preset(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Preset", "rt_preset.json", "JSON Files (*.json)")
        if not filepath:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"type": "radiography_preset", "version": CURRENT_VERSION,
                           "state": self.collect_form_state()}, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Success", f"Preset saved: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save preset: {e}")

    def load_form_preset(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Preset", "", "JSON Files (*.json)")
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("type") != "radiography_preset":
                QMessageBox.warning(self, "Warning", "Not a valid Radiography preset file.")
                return
            self.apply_form_state(data.get("state", {}))
            QMessageBox.information(self, "Success", f"Preset loaded: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load preset: {e}")

    def export_project_json(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Project", "rt_project.json", "JSON Files (*.json)")
        if not filepath:
            return
        try:
            payload = {
                "type": "radiography_project",
                "version": CURRENT_VERSION,
                "state": self.collect_form_state(),
                "calculated": self.last_calculated,
                "warnings": self.txt_warnings.text(),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Success", f"Project exported: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not export project: {e}")

    def import_project_json(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Project", "", "JSON Files (*.json)")
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("type") != "radiography_project":
                QMessageBox.warning(self, "Warning", "Not a valid Radiography project file.")
                return
            self.apply_form_state(data.get("state", {}))
            QMessageBox.information(self, "Success", f"Project imported: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not import project: {e}")

    def export_project_csv(self):
        import csv
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Project (CSV)", "rt_project.csv", "CSV Files (*.csv)")
        if not filepath:
            return
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["field", "value"])
                for k, v in self.collect_form_state().items():
                    w.writerow([k, v])
                for k, v in (self.last_calculated or {}).items():
                    w.writerow([k, v])
            QMessageBox.information(self, "Success", f"Project exported: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not export CSV: {e}")

    def import_project_csv(self):
        import csv
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Project (CSV)", "", "CSV Files (*.csv)")
        if not filepath:
            return
        try:
            state = {}
            with open(filepath, "r", encoding="utf-8") as f:
                for row in csv.reader(f):
                    if len(row) >= 2 and row[0] != "field":
                        state[row[0]] = row[1]
            if state:
                self.apply_form_state(state)
                QMessageBox.information(self, "Success", f"Project imported: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not import CSV: {e}")

    def _compute_geometry(self, od, t, d, sfd, geometry, testing_class,
                          standard=None, lvl3_settings=None):
        """Delegates to the shared CalculationEngine (src/core/engine.py).

        Kept as a thin adapter so existing callers (update_calculations,
        export_pdf_report and the regression tests) keep the same signature.
        The geometry contract (b, b_eff, f_min, f_min*, sfd_min, sdd_min, Ug,
        bed handling, Level 3 reductions) lives in
        CalculationEngine.compute_geometry.
        """
        form = self._collect_engine_form()
        form.update({
            "od": od,
            "t": t,
            "d": d,
            "sfd": sfd,
            "geometry": geometry,
            "testing_class": testing_class,
        })
        if standard is not None:
            form["standard"] = standard
        return self.engine.compute_geometry(
            form,
            lvl3_settings if lvl3_settings is not None else self.lvl3_settings,
        )

    def _render_calculation(self, result):
        """Renders a CalculationEngine result into the desktop widgets."""
        display = result["display"]
        values = result["values"]
        warnings = result["warnings"]
        form = result["form"]

        label_key = "single_step_hole_iqi" if form.get("iqi_type") == "step_hole" else "single_wire_iqi"
        self.out_labels["single_wire_iqi"][0].setText(self.trans.get(label_key))

        for key, text in display.items():
            if key in self.out_labels:
                self.out_labels[key][1].setText(text)

        self._update_output_visibility()
        self.last_calculated = result["calculated"]

        # Dynamic provenance tooltips for output items (including exceptions & compensations).
        for out_name in (
            "sfd_min", "f_min", "req_exposures", "calc_time",
            "single_wire_iqi", "duplex_iqi", "quality_target",
            "detector_quality", "u_max", "ug"
        ):
            prov_text = result["values"].get(f"{out_name}_provenance_text")
            if prov_text and out_name in getattr(self, "info_buttons", {}):
                base_tt = self.trans.get(f"tt_{out_name}", "")
                combined = f"{base_tt}\n\n{prov_text}".strip() if base_tt else prov_text
                self.info_buttons[out_name].setToolTip(combined)

        if warnings:
            self.txt_warnings.setText("\n".join(warnings))
        else:
            self.txt_warnings.setText("No active warnings.")

        if hasattr(self, "lbl_dynamic_standard_ref") and hasattr(self, "cmb_std_figure"):
            self.lbl_dynamic_standard_ref.setText(
                f"{self.trans.get('standard_fig')} {self.cmb_std_figure.currentText()}")

        safety_r = values.get("safety_radius_m")
        if values["tech"] == "digital":
            self.canvas.draw_setup(
                values["od"], values["t"], values["cap"], values["geometry"],
                values["sfd"], self.trans, self.is_dark_theme,
                panel_width=values["panel_width"], panel_height=values["panel_height"],
                overlap_pct=values["panel_overlap"], n_panel=values["n_panel"],
                safety_radius_m=safety_r)
        else:
            self.canvas.draw_setup(
                values["od"], values["t"], values["cap"], values["geometry"],
                values["sfd"], self.trans, self.is_dark_theme,
                safety_radius_m=safety_r)

        self.check_procedure_compliance()

    def _format_sfd_provenance(self, provenance):
        """Localized tooltip text listing the SFD_min/SDD_min candidates."""
        from src.core.engine import format_sfd_provenance
        return format_sfd_provenance(provenance, self.trans)

    def _format_exposures_provenance(self, prov):
        """Localized explanation of how the required exposure count was found."""
        from src.core.engine import format_exposures_provenance
        return format_exposures_provenance(prov, self.trans)

    def _show_output_info(self, name: str) -> None:
        """Display an informational dialog showing provenance/details for an output item."""
        lbl_text = self.trans.get(name) if hasattr(self, "trans") else name
        if hasattr(self, "out_labels") and name in self.out_labels:
            lbl_widget = self.out_labels[name][0]
            lbl_text = lbl_widget.text().replace(":", "").strip()
        btn = getattr(self, "info_buttons", {}).get(name)
        info_text = btn.toolTip() if btn else ""
        if not info_text:
            info_text = self.trans.get("tt_" + name, "") if hasattr(self, "trans") else ""
        if info_text:
            QMessageBox.information(self, lbl_text, info_text)

    def update_calculations(self):
        # DWDI is only valid for OD <= 100 mm; force DWSI otherwise (UI mirror
        # of the engine rule) and remember the user's original selection so the
        # "forced to DWSI" warning is preserved.
        od = self.get_form_values()[0]
        user_geometry = GEOMETRY_KEYS[self.cmb_geometry.currentIndex()]
        self._update_weld_width_visibility(user_geometry)
        if od > 100.0 and user_geometry in ("dwdi_elliptic", "dwdi_super"):
            self.cmb_geometry.setCurrentIndex(0)

        form = self._collect_engine_form()
        form["user_geometry"] = user_geometry
        result = self.engine.calculate(form, self.lvl3_settings, self.trans.language)
        self._render_calculation(result)

    def evaluate_defect(self):
        # Read inputs
        t = self.get_form_values()[1] # get wall thickness
        
        defect_types = ["defect_ip", "defect_if", "defect_ic", "defect_porosity", "defect_crack", "defect_slag", "defect_undercut", "defect_burn_through"]
        defect_type = defect_types[self.cmb_defect_type.currentIndex()]

        try:
            length = self._to_mm(float(self.txt_defect_length.text().replace(",", ".")))
        except ValueError:
            length = 0.0

        try:
            width = self._to_mm(float(self.txt_defect_width.text().replace(",", ".")))
        except ValueError:
            width = 0.0

        try:
            accum = self._to_mm(float(self.txt_defect_accum.text().replace(",", ".")))
        except ValueError:
            accum = 0.0

        is_accepted, reason = self.api_eval.evaluate(defect_type, t, length, width, accum, self.trans.language)
        # Route to the selected defect standard
        defect_standard = self.cmb_defect_standard.currentData()
        approx = False
        if defect_standard == "iso5817":
            from src.core.iso5817 import ISO5817Evaluator
            level = self.cmb_quality_level.currentText()
            is_accepted, reason = ISO5817Evaluator().evaluate(
                defect_type, t, length, width, accum, level=level, lang=self.trans.language
            )
            approx = True
        elif defect_standard == "b31_3":
            from src.core.asme_b31_3 import ASMEB31_3Evaluator
            service = self.cmb_b31_service.currentData()
            is_accepted, reason = ASMEB31_3Evaluator().evaluate(
                defect_type, t, length, width, accum, service=service, lang=self.trans.language
            )
            approx = True
        elif defect_standard == "viii":
            from src.core.asme_viii import ASMEVIIIEvaluator
            mode = self.cmb_viii_mode.currentData()
            is_accepted, reason = ASMEVIIIEvaluator().evaluate(
                defect_type, t, length, width, accum, mode=mode, lang=self.trans.language
            )
            approx = True

        if approx:
            note = self.trans.get("defect_approx_note")
            reason = f"{reason}\n\n{note}"

        if is_accepted:
            self.lbl_defect_result.setText(self.trans.get("result_accept"))
            self.lbl_defect_result.setStyleSheet("color: #a6e3a1; font-weight: bold; background-color: #2e7d32; padding: 4px; border-radius: 4px;")
        else:
            self.lbl_defect_result.setText(self.trans.get("result_reject"))
            self.lbl_defect_result.setStyleSheet("color: #f38ba8; font-weight: bold; background-color: #c62828; padding: 4px; border-radius: 4px;")
        
        # Display reason in warning log as well
        # We can display a custom MessageBox
        QMessageBox.information(self, self.trans.get("evaluation_result"), reason)

    def check_procedure_compliance(self):
        # If last_calculated is empty, run update_calculations first
        if not self.last_calculated:
            self.update_calculations()

        form = self._collect_engine_form()
        res = self.engine.check_compliance(
            form, self.last_calculated, self.lvl3_settings, self.trans.language)

        is_compliant = res["is_compliant"]
        if is_compliant:
            self.lbl_compliance_result.setText(self.trans.get("compliant"))
            self.lbl_compliance_result.setStyleSheet("color: #a6e3a1; font-weight: bold; background-color: #2e7d32; padding: 6px; border-radius: 4px;")
        else:
            self.lbl_compliance_result.setText(self.trans.get("non_compliant"))
            self.lbl_compliance_result.setStyleSheet("color: #f38ba8; font-weight: bold; background-color: #c62828; padding: 6px; border-radius: 4px;")

        details_lines = []
        for chk in res["checks"]:
            symbol = "✓" if chk["status"] else "✗"
            color_style = "color: #a6e3a1;" if chk["status"] else "color: #f38ba8;"
            details_lines.append(f"<span style='{color_style}'>{symbol} {chk['details']}</span>")

        if res.get("activity_warning"):
            details_lines.append(f"<span style='color: #f9e2af;'>⚠ {res['activity_warning']}</span>")

        self.lbl_compliance_details.setText("<br>".join(details_lines))

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        self.update_menu = menu_bar.addMenu("&Updates")
        self.check_update_action = QAction("Check for Updates", self)
        self.check_update_action.triggered.connect(lambda: self.check_for_updates(silent=False))
        self.update_menu.addAction(self.check_update_action)

        data_menu = menu_bar.addMenu("&Data")
        act_save_preset = QAction("Save Preset (Şablon)", self)
        act_save_preset.triggered.connect(self.save_form_preset)
        data_menu.addAction(act_save_preset)
        act_load_preset = QAction("Load Preset (Şablon)", self)
        act_load_preset.triggered.connect(self.load_form_preset)
        data_menu.addAction(act_load_preset)
        # Named built-in templates
        named_menu = data_menu.addMenu("Hazır Şablonlar")
        for name in self._NAMED_PRESETS:
            act = QAction(name, self)
            act.triggered.connect(lambda _, n=name: self.apply_named_preset(n))
            named_menu.addAction(act)
        data_menu.addSeparator()
        act_export = QAction("Export Project (JSON)", self)
        act_export.triggered.connect(self.export_project_json)
        data_menu.addAction(act_export)
        act_import = QAction("Import Project (JSON)", self)
        act_import.triggered.connect(self.import_project_json)
        data_menu.addAction(act_import)
        act_export_csv = QAction("Export Project (CSV)", self)
        act_export_csv.triggered.connect(self.export_project_csv)
        data_menu.addAction(act_export_csv)
        act_import_csv = QAction("Import Project (CSV)", self)
        act_import_csv.triggered.connect(self.import_project_csv)
        data_menu.addAction(act_import_csv)

        help_menu = menu_bar.addMenu("&Help")
        act_report_issue = QAction(self.trans.get("report_issue"), self)
        act_report_issue.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/SLedgehammer-dev12/Radiography/issues")))
        help_menu.addAction(act_report_issue)

        act_contact_email = QAction(self.trans.get("contact_email_action"), self)
        act_contact_email.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("mailto:omer.erbas@botas.gov.tr")))
        help_menu.addAction(act_contact_email)

        help_menu.addSeparator()

        about_action = QAction(f"{self.trans.get('about_action')} (v{CURRENT_VERSION})", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle(self.trans.get("about_title"))
        title_text = f"<h3>Radiography v{CURRENT_VERSION}</h3><p>ISO 17636 / API 1104 / ASME Compliant</p>"
        owner_text = f"<p><b>{html.escape(self.trans.get('app_owner'))}</b></p>"
        disclaimer_header = f"<p><b>{html.escape(self.trans.get('engineering_disclaimer_title'))}</b></p>"
        disclaimer_body = f"<p style='font-size: 11px;'>{html.escape(self.trans.get('disclaimer'))}</p>"
        contact_header = f"<p><b>{html.escape(self.trans.get('contact_title'))}</b></p>"
        contact_body = (
            f"<ul>"
            f"<li><a href='https://github.com/SLedgehammer-dev12/Radiography/issues'>{html.escape(self.trans.get('report_issue'))}</a></li>"
            f"<li><a href='mailto:omer.erbas@botas.gov.tr'>{html.escape(self.trans.get('contact_email'))}</a></li>"
            f"</ul>"
        )
        msg.setText(f"{title_text}{owner_text}{disclaimer_header}{disclaimer_body}{contact_header}{contact_body}")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.exec()

    def check_for_updates(self, silent=True):
        self.check_update_action.setEnabled(False)
        self.check_update_action.setText("Checking...")

        class CheckThread(QThread):
            finished = pyqtSignal(object)

            def run(self):
                checker = UpdateChecker()
                result = checker.check()
                self.finished.emit(result)

        self._update_thread = CheckThread()
        self._update_thread.finished.connect(lambda res: self._on_update_check_result(res, silent))
        self._update_thread.start()

    def _on_update_check_result(self, result, silent):
        try:
            self.check_update_action.setEnabled(True)
            self.check_update_action.setText("Check for Updates")

            if result.get("available"):
                version = str(result.get("version", "?"))
                # release_notes may be None/null from the GitHub API -> slice a str
                notes = str(result.get("release_notes") or "")[:500]
                ssl_note = ""
                if result.get("ssl_fallback"):
                    is_tr = getattr(self, "trans", None) and getattr(self.trans, "language", "") == "tr"
                    ssl_note = (
                        "\n\n(Not: Ağınızda SSL denetimi / kurumsal filtre algılandı; dosya bütünlüğü SHA-256 ile doğrulanacaktır.)"
                        if is_tr
                        else "\n\n(Note: Network SSL inspection / corporate proxy detected; download integrity will be verified via SHA-256.)"
                    )
                reply = QMessageBox.question(
                    self, "Update Available",
                    f"A new version ({version}) is available.\n\n"
                    f"{notes}{ssl_note}\n\n"
                    f"Download and install now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._download_and_install(result)
            elif result.get("error"):
                if not silent:
                    err_str = str(result["error"])
                    err_lower = err_str.lower()
                    if "certificate_verify_failed" in err_lower or "certificate verify failed" in err_lower:
                        is_tr = getattr(self, "trans", None) and getattr(self.trans, "language", "") == "tr"
                        extra_hint = (
                            "\n\nİpucu: Ağınızda veya antivirüsünüzde SSL denetimi / kurumsal filtre bulunuyor olabilir."
                            f"\nGüncellemeyi doğrudan GitHub üzerinden de indirebilirsiniz:\nhttps://github.com/{GITHUB_REPO}/releases/latest"
                        ) if is_tr else (
                            "\n\nHint: A corporate proxy, firewall, or antivirus HTTPS inspection was detected."
                            f"\nYou can also download the update directly from:\nhttps://github.com/{GITHUB_REPO}/releases/latest"
                        )
                        err_str += extra_hint
                    QMessageBox.warning(self, "Update Check Failed",
                                        f"Could not check for updates:\n{err_str}")
            else:
                if not silent:
                    QMessageBox.information(self, "No Updates",
                                            f"You are running the latest version ({CURRENT_VERSION}).")
        except Exception:
            logger.exception("Update check result handling failed")

    def _download_and_install(self, release_data):
        checker = UpdateChecker()
        asset = checker.get_download_asset(release_data)
        if not asset or not asset.get("url"):
            QMessageBox.warning(self, "Download Error",
                                "No compatible download found for your platform.")
            return
        url = asset["url"]
        expected_sha256 = checker._extract_sha256_from_release(release_data, asset["name"])
        if not expected_sha256:
            reply = QMessageBox.warning(
                self, "Unverified Update",
                "No SHA-256 checksum was published for this release, so the "
                "download cannot be integrity-verified.\n\n"
                "Download and run it anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.progress = QProgressDialog("Downloading update...", "Cancel", 0, 100, self)
        self.progress.setWindowTitle("Update")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setAutoClose(True)
        self.progress.setMinimumDuration(0)
        self.progress.show()

        cancelled = [False]

        def on_cancel():
            cancelled[0] = True
            checker.cancel()

        self.progress.canceled.connect(on_cancel)

        class DownloadThread(QThread):
            finished = pyqtSignal(object)
            progress = pyqtSignal(int)

            def run(self):
                try:
                    filepath = checker.download_update(
                        url,
                        # Emit a signal instead of touching Qt widgets from the
                        # worker thread (Qt thread-safety -> crash otherwise).
                        progress_callback=lambda pct: self.progress.emit(int(pct * 100)),
                        expected_sha256=expected_sha256,
                    )
                    self.finished.emit(filepath)
                except Exception as e:
                    self.finished.emit(e)

        self._download_thread = DownloadThread()
        self._download_thread.progress.connect(self.progress.setValue)
        self._download_thread.finished.connect(lambda fp: self._on_download_finished(fp, checker))
        self._download_thread.start()

    def _on_download_finished(self, filepath, checker):
        try:
            self.progress.close()
            if filepath is None:
                return
            if isinstance(filepath, Exception):
                QMessageBox.critical(self, "Download Failed", str(filepath))
                return

            reply = QMessageBox.question(
                self, "Download Complete",
                "Update downloaded. Install now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    checker.launch_installer(filepath)
                    QMessageBox.information(self, "Installer Launched",
                                            "The installer has been launched. Please close the application and follow the installation steps.")
                except Exception as e:
                    QMessageBox.critical(self, "Launch Failed", str(e))
        except Exception:
            logger.exception("Update download completion handling failed")

    def apply_theme(self):
        """
        Applies styling to PyQt UI (main window + application-wide for dialogs)
        """
        if self.is_dark_theme:
            # Dark Theme Colors: Mocha styled
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            app_css = """
                QMessageBox {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                }
                QMessageBox QLabel {
                    color: #cdd6f4;
                }
                QMessageBox QPushButton {
                    background-color: #45475a;
                    color: #cdd6f4;
                    border: 1px solid #585b70;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #585b70;
                    color: #ffffff;
                }
                QProgressDialog {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                }
                QFileDialog {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                }
            """
            if app and app.styleSheet() != app_css:
                app.setStyleSheet(app_css)
            self._app_css_cache = app_css if app else None
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e2e;
                }
                QWidget {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                    font-family: Helvetica, Arial, sans-serif;
                }
                QGroupBox {
                    border: 2px solid #313244;
                    border-radius: 8px;
                    margin-top: 14px;
                    padding-top: 14px;
                    color: #fab387;
                    font-weight: bold;
                    font-size: 14px;
                    background-color: #181825;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                    left: 10px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QLabel {
                    color: #cdd6f4;
                    font-size: 11px;
                }
                QLineEdit {
                    background-color: #313244;
                    border: 1px solid #45475a;
                    border-radius: 6px;
                    color: #cdd6f4;
                    padding: 5px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #fab387;
                }
                QComboBox {
                    background-color: #313244;
                    border: 1px solid #45475a;
                    border-radius: 6px;
                    color: #cdd6f4;
                    padding: 5px;
                }
                QComboBox::drop-down {
                    border: 0px;
                }
                QRadioButton {
                    color: #cdd6f4;
                    font-size: 11px;
                }
                QPushButton {
                    background-color: #45475a;
                    color: #cdd6f4;
                    border: 1px solid #585b70;
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #585b70;
                    color: #ffffff;
                }
                #AppTitle {
                    color: #fab387;
                }
                #Level3Btn {
                    background-color: #f38ba8;
                    color: #11111b;
                }
                #Level3Btn:hover {
                    background-color: #f5c2e7;
                }
                #ExportBtn {
                    background-color: #a6e3a1;
                    color: #11111b;
                }
                #ExportBtn:hover {
                    background-color: #94e2d5;
                }
                QScrollArea {
                    border: none;
                    background-color: #1e1e2e;
                }
                #OutputsBox {
                    color: #89b4fa;
                }
                #WarningsBox {
                    color: #f38ba8;
                }
                QTabWidget::pane {
                    border: 1px solid #313244;
                    background-color: #181825;
                    border-radius: 6px;
                }
                QTabBar::tab {
                    background-color: #313244;
                    color: #cdd6f4;
                    padding: 6px 12px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #181825;
                    border: 1px solid #313244;
                    border-bottom-color: #181825;
                    font-weight: bold;
                    color: #fab387;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #45475a;
                }
                QSplitter::handle {
                    background-color: #313244;
                }
                QSplitter::handle:hover {
                    background-color: #fab387;
                }
            """)
        else:
            # Light Theme Colors: Professional slate light
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            app_css = """
                QMessageBox {
                    background-color: #f5f5f5;
                    color: #212121;
                }
                QMessageBox QLabel {
                    color: #212121;
                }
                QMessageBox QPushButton {
                    background-color: #e0e0e0;
                    color: #212121;
                    border: 1px solid #b0bec5;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #b0bec5;
                    color: #000000;
                }
                QProgressDialog {
                    background-color: #f5f5f5;
                    color: #212121;
                }
                QFileDialog {
                    background-color: #f5f5f5;
                    color: #212121;
                }
            """
            if app and app.styleSheet() != app_css:
                app.setStyleSheet(app_css)
            self._app_css_cache = app_css if app else None
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                }
                QWidget {
                    background-color: #f5f5f5;
                    color: #212121;
                    font-family: Helvetica, Arial, sans-serif;
                }
                QGroupBox {
                    border: 2px solid #cfd8dc;
                    border-radius: 8px;
                    margin-top: 14px;
                    padding-top: 14px;
                    color: #0d47a1;
                    font-weight: bold;
                    font-size: 14px;
                    background-color: #fafafa;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                    left: 10px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QLabel {
                    color: #37474f;
                    font-size: 11px;
                }
                QLineEdit {
                    background-color: #ffffff;
                    border: 1px solid #b0bec5;
                    border-radius: 6px;
                    color: #212121;
                    padding: 5px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #0d47a1;
                }
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #b0bec5;
                    border-radius: 6px;
                    color: #212121;
                    padding: 5px;
                }
                QRadioButton {
                    color: #37474f;
                    font-size: 11px;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: #212121;
                    border: 1px solid #b0bec5;
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #b0bec5;
                    color: #000000;
                }
                #AppTitle {
                    color: #0d47a1;
                }
                #Level3Btn {
                    background-color: #d32f2f;
                    color: #ffffff;
                }
                #Level3Btn:hover {
                    background-color: #b71c1c;
                }
                #ExportBtn {
                    background-color: #2e7d32;
                    color: #ffffff;
                }
                #ExportBtn:hover {
                    background-color: #1b5e20;
                }
                QScrollArea {
                    border: none;
                    background-color: #f5f5f5;
                }
                #OutputsBox {
                    color: #0d47a1;
                }
                #WarningsBox {
                    color: #d32f2f;
                }
                QTabWidget::pane {
                    border: 1px solid #cfd8dc;
                    background-color: #ffffff;
                    border-radius: 6px;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #37474f;
                    padding: 6px 12px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    border: 1px solid #cfd8dc;
                    border-bottom-color: #ffffff;
                    font-weight: bold;
                    color: #0d47a1;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #b0bec5;
                }
                QSplitter::handle {
                    background-color: #cfd8dc;
                }
                QSplitter::handle:hover {
                    background-color: #0d47a1;
                }
            """)
        self._update_theme_styles()

    def _update_theme_styles(self):
        is_dark = self.is_dark_theme
        ref_color = "#89b4fa" if is_dark else "#0d47a1"
        val_color = "#a6e3a1" if is_dark else "#2e7d32"
        warn_color = "#f38ba8" if is_dark else "#d32f2f"
        info_color = "#89b4fa" if is_dark else "#0d47a1"
        info_hover_bg = "#89b4fa" if is_dark else "#0d47a1"
        info_hover_text = "#1e1e2e" if is_dark else "#ffffff"
        self.lbl_dynamic_standard_ref.setStyleSheet(
            f"color: {ref_color}; font-size: 11px; font-weight: bold; padding: 4px;"
        )
        self.txt_warnings.setStyleSheet(
            f"color: {warn_color}; font-size: 10px; font-weight: bold;"
        )
        for name, (lbl, val) in self.out_labels.items():
            if name == "detector_quality":
                continue
            val.setStyleSheet(f"color: {val_color};")
        for name, btn in self.info_buttons.items():
            btn.setStyleSheet(f"""
                QPushButton#InfoBtn {{
                    border: 1px solid {info_color};
                    border-radius: 7px;
                    color: {info_color};
                    font-size: 8px;
                    font-weight: bold;
                    background-color: transparent;
                }}
                QPushButton#InfoBtn:hover {{
                    background-color: {info_hover_bg};
                    color: {info_hover_text};
                }}
            """)

# End of MainWindow definition
