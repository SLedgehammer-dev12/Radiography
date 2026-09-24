# -*- coding: utf-8 -*-

import os
import json
import tempfile
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QComboBox, QLineEdit, QRadioButton, QButtonGroup, 
                             QCheckBox, QPushButton, QGroupBox, QScrollArea, QFileDialog, 
                             QMessageBox, QFormLayout, QTabWidget, QDialog, QProgressDialog,
                             QMenuBar, QSplitter)
from PyQt6.QtCore import Qt, QThread, QTimer, QSettings, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QDoubleValidator, QIntValidator, QAction

from src.core.translation import Translation
from src.core.calculator import RTCalculator
from src.core.exposure_charts import ExposureChartDatabase, resource_path
from src.core.api1104 import API1104Evaluator
from src.ui.sketch import WeldSketchCanvas, StandardSchematicCanvas
from src.ui.compensation import Level3Dialog
from src.core.report import PDFReportGenerator
from src.core.procedure_check import ProcedureComplianceChecker
from src.core.updater import UpdateChecker
from src.core.version import __version__ as CURRENT_VERSION
from src.core.asme_b36 import ASME_B36_10_PIPES
from src.ui.panels.input_panel import InputPanelMixin, QFormLayout_custom
from src.ui.panels.defect_panel import DefectPanelMixin
from src.ui.panels.warnings_compliance_panel import WarningsPanelMixin, CompliancePanelMixin


logger = logging.getLogger("radiography.ui.main_window")


class MainWindow(QMainWindow,
                  InputPanelMixin,
                  DefectPanelMixin,
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

        # Trigger initial calculations
        if not self._restored_settings:
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
        }
        for le_name, default_val in line_edits.items():
            w = getattr(self, le_name, None)
            if w:
                val = w.text()
                if val != default_val or s.contains(f"form/{le_name}"):
                    s.setValue(f"form/{le_name}", val)

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
            "cmb_asme_sensitivity",
        ]
        for combo_name in combo_map:
            idx = s.value(f"form/{combo_name}", type=int)
            if idx is not None:
                w = getattr(self, combo_name, None)
                if w and 0 <= idx < w.count():
                    w.blockSignals(True)
                    w.setCurrentIndex(idx)
                    w.blockSignals(False)

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
        ]
        for le_name in line_edits:
            val = s.value(f"form/{le_name}")
            if val is not None:
                w = getattr(self, le_name, None)
                if w:
                    w.setText(val)

    def init_ui(self):
        # Central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ---------------- TOP BAR ----------------
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel(self.trans.get("app_title"))
        self.lbl_title.setObjectName("AppTitle")
        self.lbl_title.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))

        # Language Switch Button
        self.btn_lang = QPushButton(self.trans.get("lang_switch"))
        self.btn_lang.setFixedWidth(100)
        self.btn_lang.clicked.connect(self.toggle_language)

        # Theme Switch Button
        self.btn_theme = QPushButton(self.trans.get("theme_light"))
        self.btn_theme.setFixedWidth(120)
        self.btn_theme.clicked.connect(self.toggle_theme)

        # Units toggle (metric / imperial) for the main dimensional inputs
        self.btn_units = QPushButton("mm")
        self.btn_units.setFixedWidth(50)
        self.btn_units.setToolTip("mm ↔ inç / inch")
        self.btn_units.clicked.connect(self.toggle_units)

        # Level 3 Exception Button
        self.btn_lvl3 = QPushButton(self.trans.get("level3_section"))
        self.btn_lvl3.clicked.connect(self.open_level3_dialog)
        self.btn_lvl3.setFixedWidth(160)
        self.btn_lvl3.setObjectName("Level3Btn")

        # PDF Export Button
        self.btn_export = QPushButton(self.trans.get("export_pdf"))
        self.btn_export.clicked.connect(self.export_pdf_report)
        self.btn_export.setFixedWidth(160)
        self.btn_export.setObjectName("ExportBtn")

        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_lang)
        top_bar.addWidget(self.btn_theme)
        top_bar.addWidget(self.btn_units)
        top_bar.addWidget(self.btn_lvl3)
        top_bar.addWidget(self.btn_export)
        main_layout.addLayout(top_bar)

        # ── MAIN 3-COLUMN SPLITTER ──────────────────────────────────────────
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setObjectName("main_splitter")
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(8)

        # ══════════════ COLUMN 1: Input Parameters (25%) ═══════════════════
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setObjectName("left_splitter")
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setHandleWidth(8)

        self.left_scroll_1 = QScrollArea()
        self.left_scroll_1.setWidgetResizable(True)
        self.left_scroll_1.setMinimumHeight(100)
        scroll_widget_1 = QWidget()
        scroll_layout_1 = QVBoxLayout(scroll_widget_1)
        scroll_layout_1.setContentsMargins(5, 5, 5, 5)
        scroll_layout_1.setSpacing(0)

        grp_inputs = QGroupBox(self.trans.get("inputs_section"))
        grp_inputs_layout = QFormLayout_custom()
        grp_inputs.setLayout(grp_inputs_layout)

        self._init_input_panel(grp_inputs_layout)

        self.chk_source_side_iqi = QCheckBox(self.trans.get("source_side_iqi"))
        self.chk_source_side_iqi.setChecked(True)
        self.chk_source_side_iqi.stateChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.chk_source_side_iqi)

        self.lbl_iqi_type = QLabel(self.trans.get("iqi_type"))
        self.cmb_iqi_type = QComboBox()
        self.cmb_iqi_type.addItem(self.trans.get("iqi_type_wire"), "wire")
        self.cmb_iqi_type.addItem(self.trans.get("iqi_type_step_hole"), "step_hole")
        self.cmb_iqi_type.currentIndexChanged.connect(self.on_iqi_type_changed)
        grp_inputs_layout.addRow(self.lbl_iqi_type, self.cmb_iqi_type)

        scroll_layout_1.addWidget(grp_inputs)
        self.left_scroll_1.setWidget(scroll_widget_1)

        # Scroll area 2: Exposure Settings
        self.left_scroll_2 = QScrollArea()
        self.left_scroll_2.setWidgetResizable(True)
        self.left_scroll_2.setMinimumHeight(100)
        scroll_widget_2 = QWidget()
        scroll_layout_2 = QVBoxLayout(scroll_widget_2)
        scroll_layout_2.setContentsMargins(5, 5, 5, 5)
        scroll_layout_2.setSpacing(0)

        self.grp_exposure = QGroupBox(self.trans.get("applied_exposure_section"))
        grp_exposure_layout = QFormLayout_custom()
        self.grp_exposure.setLayout(grp_exposure_layout)

        # Applied SFD
        self.lbl_app_sfd = QLabel(self.trans.get("applied_sfd"))
        self.txt_app_sfd = QLineEdit("600.0")
        self.txt_app_sfd.setValidator(QDoubleValidator(10.0, 5000.0, 1))
        self.txt_app_sfd.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_sfd, self.txt_app_sfd)

        # Base exposure multiplier (field adjustment for model/conditions deviation)
        self.lbl_base_multiplier = QLabel(self.trans.get("base_multiplier"))
        self.txt_base_multiplier = QLineEdit("1.0")
        self.txt_base_multiplier.setValidator(QDoubleValidator(0.01, 100.0, 2))
        self.txt_base_multiplier.setToolTip(self.trans.get("tt_base_multiplier"))
        self.txt_base_multiplier.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_base_multiplier, self.txt_base_multiplier)

        # Tube Amperage (mA) - visible for X-ray
        self.lbl_output = QLabel(self.trans.get("amperage"))
        self.txt_output = QLineEdit("5.0")
        self.txt_output.setValidator(QDoubleValidator(0.01, 1000.0, 2))
        self.txt_output.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_output, self.txt_output)

        # Applied Tube Voltage (kV) - visible for X-ray
        self.lbl_app_kv = QLabel(self.trans.get("applied_kv"))
        self.txt_app_kv = QLineEdit("120.0")
        self.txt_app_kv.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.txt_app_kv.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_kv, self.txt_app_kv)

        # Applied Activity (Ci / GBq) - visible for Isotopes
        self.lbl_app_activity = QLabel(self.trans.get("applied_activity"))
        self.act_widget = QWidget()
        act_layout = QHBoxLayout(self.act_widget)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(4)
        self.txt_app_activity = QLineEdit("40.0")
        self.txt_app_activity.setValidator(QDoubleValidator(0.01, 100000.0, 2))
        self.txt_app_activity.textChanged.connect(self.update_calculations)
        self.cmb_activity_unit = QComboBox()
        self.cmb_activity_unit.addItems(["Ci", "GBq"])
        self.cmb_activity_unit.currentIndexChanged.connect(self.on_activity_unit_changed)
        act_layout.addWidget(self.txt_app_activity)
        act_layout.addWidget(self.cmb_activity_unit)
        grp_exposure_layout.addRow(self.lbl_app_activity, self.act_widget)

        # Base factor E
        self.lbl_base_e = QLabel(self.trans.get("base_factor"))
        self.txt_base_e = QLineEdit("3.0")
        self.txt_base_e.setValidator(QDoubleValidator(0.0001, 2000.0, 4))
        self.txt_base_e.setToolTip(self.trans.get("tt_base_factor"))
        self.txt_base_e.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_base_e, self.txt_base_e)

        # Collimator / shielding (barrier distance) - isotopes only
        self.lbl_collimator = QLabel(self.trans.get("collimator"))
        self.cmb_collimator = QComboBox()
        self.cmb_collimator.addItem(self.trans.get("collimator_none"), 0)
        self.cmb_collimator.addItem("1 HVL", 1)
        self.cmb_collimator.addItem("2 HVL", 2)
        self.cmb_collimator.addItem("4 HVL", 4)
        self.cmb_collimator.setToolTip(self.trans.get("tt_collimator"))
        self.cmb_collimator.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_collimator, self.cmb_collimator)

        # Controlled-area dose limit
        self.lbl_barrier_limit = QLabel(self.trans.get("barrier_limit_label"))
        self.txt_barrier_limit = QLineEdit("20.0")
        self.txt_barrier_limit.setValidator(QDoubleValidator(0.1, 1000.0, 1))
        self.txt_barrier_limit.setToolTip(self.trans.get("tt_barrier_distance"))
        self.txt_barrier_limit.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_barrier_limit, self.txt_barrier_limit)

        # Gamma dose-rate convention (R vs mSv) for the barrier calculation
        self.lbl_gamma_convention = QLabel(self.trans.get("gamma_convention"))
        self.cmb_gamma_convention = QComboBox()
        self.cmb_gamma_convention.addItem(self.trans.get("gamma_conv_r"), "r")
        self.cmb_gamma_convention.addItem(self.trans.get("gamma_conv_msv"), "msv")
        self.cmb_gamma_convention.setToolTip(self.trans.get("tt_gamma_convention"))
        self.cmb_gamma_convention.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_gamma_convention, self.cmb_gamma_convention)

        # Isotope decay tool (auto-fills current activity)
        self.btn_decay = QPushButton(self.trans.get("decay_dialog"))
        self.btn_decay.clicked.connect(self.open_decay_dialog)
        self.btn_decay.setObjectName("ExportBtn")
        grp_exposure_layout.addRow(self.btn_decay)

        # ASME/ASTM IQI sensitivity (T-276) - visible when ASME standard
        self.lbl_asme_sensitivity = QLabel(self.trans.get("asme_sensitivity"))
        self.cmb_asme_sensitivity = QComboBox()
        self.cmb_asme_sensitivity.addItem(self.trans.get("sens_2_2t"), "2-2T")
        self.cmb_asme_sensitivity.addItem(self.trans.get("sens_2_1t"), "2-1T")
        self.cmb_asme_sensitivity.addItem(self.trans.get("sens_1_2t"), "1-2T")
        self.cmb_asme_sensitivity.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_asme_sensitivity, self.cmb_asme_sensitivity)

        # Chart Source
        self.cmb_chart_source = QComboBox()
        self.cmb_chart_source.addItem(self.trans.get("chart_model"), "model")
        self.cmb_chart_source.addItem("AA400 (C5)", "AA400")
        self.cmb_chart_source.addItem("MX125 (C3)", "MX125")
        self.cmb_chart_source.addItem("T200 (C4)", "T200")
        self.cmb_chart_source.addItem("HS800 (C6)", "HS800")
        self.cmb_chart_source.addItem("M100 (C2)", "M100")
        self.cmb_chart_source.addItem(self.trans.get("chart_type_x"), "type_x")
        self.cmb_chart_source.currentIndexChanged.connect(self.on_chart_source_changed)
        grp_exposure_layout.addRow(self.trans.get("chart_source"), self.cmb_chart_source)

        # Film class in use
        self.lbl_film_class_used = QLabel(self.trans.get("film_class_used"))
        self.cmb_film_class_used = QComboBox()
        self.cmb_film_class_used.addItems(["C1", "C2", "C3", "C4", "C5", "C6"])
        self.cmb_film_class_used.setCurrentIndex(4)
        self.cmb_film_class_used.setMinimumWidth(100)
        self.cmb_film_class_used.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_film_class_used, self.cmb_film_class_used)

        # Applied Film Overlap
        self.lbl_app_overlap = QLabel(self.trans.get("applied_overlap"))
        self.txt_app_overlap = QLineEdit("10.0")
        self.txt_app_overlap.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_app_overlap.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_overlap, self.txt_app_overlap)

        # Applied Exposure Time
        self.lbl_app_time = QLabel(self.trans.get("applied_time"))
        self.txt_app_time = QLineEdit("120.0")
        self.txt_app_time.setValidator(QDoubleValidator(0.1, 100000.0, 1))
        self.txt_app_time.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_time, self.txt_app_time)

        # Detector type
        self.lbl_detector_type = QLabel(self.trans.get("detector_type"))
        self.cmb_detector_type = QComboBox()
        self._det_keys = ["cr_standard", "cr_highres", "dda_si", "dda_se", "dda_gdos"]
        self._det_trans_keys = ["detector_cr_std", "detector_cr_hires",
                                "detector_dda_si", "detector_dda_se", "detector_dda_gdos"]
        for key, tkey in zip(self._det_keys, self._det_trans_keys):
            self.cmb_detector_type.addItem(self.trans.get(tkey), key)
        self.cmb_detector_type.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_detector_type, self.cmb_detector_type)

        # Applied Panel SRb
        self.lbl_app_srb = QLabel(self.trans.get("applied_srb"))
        self.txt_app_srb = QLineEdit("80.0")
        self.txt_app_srb.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.txt_app_srb.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_srb, self.txt_app_srb)

        # SNR Measurement Location
        self.lbl_snr_location = QLabel(self.trans.get("snr_location"))
        self.cmb_snr_location = QComboBox()
        self.cmb_snr_location.addItem(self.trans.get("snr_location_weld"), "weld")
        self.cmb_snr_location.addItem(self.trans.get("snr_location_adjacent"), "adjacent")
        self.cmb_snr_location.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_snr_location, self.cmb_snr_location)

        # Applied Duplex IQI
        self.lbl_app_duplex = QLabel(self.trans.get("applied_duplex"))
        self.cmb_app_duplex = QComboBox()
        for d in range(1, 14):
            self.cmb_app_duplex.addItem(str(d), d)
        self.cmb_app_duplex.setCurrentIndex(5)
        self.cmb_app_duplex.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_duplex, self.cmb_app_duplex)

        # Applied IQI (Wire / Step Hole)
        self.lbl_app_wire = QLabel(self.trans.get("applied_wire"))
        self.cmb_app_wire = QComboBox()
        self.cmb_app_wire.setMinimumWidth(160)
        # Populated dynamically in on_iqi_type_changed
        self.cmb_app_wire.currentIndexChanged.connect(self.update_calculations)
        # Initial population (block signals to avoid premature update_calculations)
        self.cmb_app_wire.blockSignals(True)
        for w_no in sorted(self.calc.wire_diameters.keys()):
            self.cmb_app_wire.addItem(f"W {w_no} ({self.calc.wire_diameters[w_no]:.3f} mm)", w_no)
        self.cmb_app_wire.setCurrentIndex(9)
        self.cmb_app_wire.blockSignals(False)
        grp_exposure_layout.addRow(self.lbl_app_wire, self.cmb_app_wire)

        # Applied Quality (SNR_N for digital / Optical Density for analog)
        self.lbl_app_quality = QLabel(self.trans.get("applied_quality"))
        self.txt_app_quality = QLineEdit("140")
        self.txt_app_quality.setValidator(QDoubleValidator(0.1, 1000.0, 1))
        self.txt_app_quality.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_quality, self.txt_app_quality)

        # Panel Active Width (digital only)
        self.lbl_panel_width = QLabel(self.trans.get("panel_width"))
        self.txt_panel_width = QLineEdit("200.0")
        self.txt_panel_width.setValidator(QDoubleValidator(10.0, 2000.0, 1))
        self.txt_panel_width.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_panel_width, self.txt_panel_width)

        # Panel Active Height (digital only)
        self.lbl_panel_height = QLabel(self.trans.get("panel_height"))
        self.txt_panel_height = QLineEdit("200.0")
        self.txt_panel_height.setValidator(QDoubleValidator(10.0, 2000.0, 1))
        self.txt_panel_height.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_panel_height, self.txt_panel_height)

        # Digital Image Overlap % (digital only, blank -> 10% fallback)
        self.lbl_panel_overlap = QLabel(self.trans.get("panel_overlap"))
        self.txt_panel_overlap = QLineEdit("")
        self.txt_panel_overlap.setValidator(QDoubleValidator(0.0, 50.0, 1))
        self.txt_panel_overlap.setPlaceholderText("10.0")
        self.txt_panel_overlap.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_panel_overlap, self.txt_panel_overlap)

        # Applied Exposures (digital only)
        self.lbl_app_exposures = QLabel(self.trans.get("applied_exposures"))
        self.txt_app_exposures = QLineEdit("6")
        self.txt_app_exposures.setValidator(QIntValidator(1, 100))
        self.txt_app_exposures.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_exposures, self.txt_app_exposures)

        # Applied Overlap Length for analog
        # (note: this is a duplicate concept from txt_app_overlap above — kept for clarity)

        scroll_layout_2.addWidget(self.grp_exposure)

        # Report / Procedure information group
        self.grp_report_info = QGroupBox(self.trans.get("report_info_section"))
        grp_report_layout = QFormLayout_custom()
        self.grp_report_info.setLayout(grp_report_layout)
        self._report_fields = [
            ("txt_report_no", "report_no", ""),
            ("txt_report_rev", "report_rev", ""),
            ("txt_project", "project", ""),
            ("txt_welder_id", "welder_id", ""),
            ("txt_joint_id", "joint_id", ""),
            ("txt_wps_pqr", "wps_pqr", ""),
            ("txt_procedure_no", "procedure_no", ""),
            ("txt_device_serial", "device_serial", ""),
            ("txt_calibration_date", "calibration_date", ""),
            ("txt_personnel", "personnel", ""),
            ("txt_lvl2_name", "lvl2_name", ""),
            ("txt_lvl2_cert", "lvl2_cert", ""),
            ("txt_lvl3_name", "lvl3_name", ""),
            ("txt_lvl3_cert", "lvl3_cert", ""),
        ]
        self._report_labels = {}
        for attr, key, default in self._report_fields:
            lbl = QLabel(self.trans.get(key))
            edit = QLineEdit(default)
            edit.textChanged.connect(self.update_calculations)
            grp_report_layout.addRow(lbl, edit)
            setattr(self, attr, edit)
            self._report_labels[attr] = lbl
        scroll_layout_2.addWidget(self.grp_report_info)
        self.left_scroll_2.setWidget(scroll_widget_2)

        self.left_splitter.addWidget(self.left_scroll_1)
        self.left_splitter.addWidget(self.left_scroll_2)
        self.left_splitter.setSizes([300, 300])

        main_splitter.addWidget(self.left_splitter)

        # ══════════════ COLUMN 2: Calculation Results (25%) ════════════════
        self.outputs_panel = QWidget()
        self.outputs_panel.setObjectName("OutputsPanel")
        outputs_layout = QVBoxLayout(self.outputs_panel)
        outputs_layout.setContentsMargins(5, 5, 5, 5)
        outputs_layout.setSpacing(4)

        grp_outputs = QGroupBox(self.trans.get("outputs"))
        grp_outputs.setObjectName("OutputsBox")
        grp_outputs_layout = QVBoxLayout(grp_outputs)
        grp_outputs_layout.setSpacing(6)
        grp_outputs.setLayout(grp_outputs_layout)

        self.out_labels = {}
        self.out_rows = {}
        self.info_buttons = {}
        out_fields = [
            "w_nom", "w_eff", "u_max", "f_min", "f_min_asme", "sfd_min",
            "ug", "req_exposures", "exposures_panel", "exposures_applied", "exposures_check",
            "single_wire_iqi", "duplex_iqi",
            "asme_iqi", "quality_target", "calc_time", "detector_quality",
            "barrier_distance", "filter_recommendation"
        ]

        for name in out_fields:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(6)

            lbl = QLabel(self.trans.get(name))
            lbl.setMinimumWidth(100)

            info_btn = QPushButton("?")
            info_btn.setFixedSize(14, 14)
            info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            info_btn.setObjectName("InfoBtn")
            info_btn.setStyleSheet("""
                QPushButton#InfoBtn {
                    border: 1px solid #89b4fa;
                    border-radius: 7px;
                    color: #89b4fa;
                    font-size: 8px;
                    font-weight: bold;
                    background-color: transparent;
                }
                QPushButton#InfoBtn:hover {
                    background-color: #89b4fa;
                    color: #1e1e2e;
                }
            """)
            info_btn.setToolTip(self.trans.get("tt_" + name))
            self.info_buttons[name] = info_btn

            val = QLabel("-")
            val.setObjectName("OutputValue")
            val.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            val.setStyleSheet("color: #a6e3a1;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            row_layout.addWidget(lbl)
            row_layout.addWidget(info_btn)
            row_layout.addStretch()
            row_layout.addWidget(val)

            grp_outputs_layout.addWidget(row_widget)

            self.out_labels[name] = (lbl, val)
            self.out_rows[name] = row_widget

        grp_outputs_layout.addStretch()
        outputs_layout.addWidget(grp_outputs)

        # Procedure Compliance (below outputs)
        self._init_compliance_panel()
        outputs_layout.addWidget(self.grp_compliance)

        main_splitter.addWidget(self.outputs_panel)

        # ══════════════ COLUMN 3: Sketch + Procedure/Defects (50%) ═════════
        right_panel = QSplitter(Qt.Orientation.Vertical)
        right_panel.setObjectName("right_panel")
        right_panel.setChildrenCollapsible(False)
        right_panel.setHandleWidth(8)

        # ── Top: Sketch (square, 50% of right panel) ──
        self.sketch_box = QGroupBox(self.trans.get("sketch_title"))
        self.sketch_box.setObjectName("SketchBox")
        sketch_layout = QVBoxLayout(self.sketch_box)
        sketch_layout.setContentsMargins(5, 5, 5, 5)

        self.tab_sketch = QTabWidget()
        self.tab_sketch.setObjectName("SketchTabs")

        tab_dynamic_widget = QWidget()
        tab_dynamic_layout = QVBoxLayout(tab_dynamic_widget)
        tab_dynamic_layout.setContentsMargins(2, 2, 2, 2)
        self.canvas = WeldSketchCanvas(tab_dynamic_widget, width=5, height=3, dpi=100)
        tab_dynamic_layout.addWidget(self.canvas)

        self.lbl_dynamic_standard_ref = QLabel("")
        self.lbl_dynamic_standard_ref.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dynamic_standard_ref.setStyleSheet("color: #89b4fa; font-size: 11px; font-weight: bold; padding: 4px;")
        tab_dynamic_layout.addWidget(self.lbl_dynamic_standard_ref)

        self.tab_sketch.addTab(tab_dynamic_widget, self.trans.get("tab_dynamic"))

        tab_std_widget = QWidget()
        tab_std_layout = QVBoxLayout(tab_std_widget)
        tab_std_layout.setContentsMargins(2, 2, 2, 2)
        self.std_canvas = StandardSchematicCanvas(tab_std_widget, width=5, height=3, dpi=100)
        tab_std_layout.addWidget(self.std_canvas)
        self.cmb_std_figure_tab = QComboBox()
        self.cmb_std_figure_tab.currentIndexChanged.connect(self.on_std_figure_tab_changed)
        tab_std_layout.addWidget(self.cmb_std_figure_tab)
        self.tab_sketch.addTab(tab_std_widget, self.trans.get("tab_standard"))

        sketch_layout.addWidget(self.tab_sketch)

        right_panel.addWidget(self.sketch_box)

        # ── Bottom: Warnings + API 1104 Defects ──
        right_sub_splitter = QSplitter(Qt.Orientation.Vertical)
        right_sub_splitter.setObjectName("right_sub_splitter")
        right_sub_splitter.setChildrenCollapsible(False)
        right_sub_splitter.setHandleWidth(8)

        self._init_warnings_panel()
        self._init_defect_panel()

        right_sub_splitter.addWidget(self.grp_warnings)
        right_sub_splitter.addWidget(self.tab_extra)
        right_sub_splitter.setSizes([150, 250])

        right_panel.addWidget(right_sub_splitter)
        right_panel.setSizes([400, 400])

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([250, 250, 500])

        main_layout.addWidget(main_splitter)

        # Setup initial state for fields
        self.on_tech_changed()
        self.on_source_changed()

        # Unblock signals and populate standard dimensions
        self.cmb_od.blockSignals(False)
        self.cmb_t.blockSignals(False)
        self.populate_standard_thicknesses()
        idx_4in = self.cmb_od.findData("4\" (NPS 4)")
        if idx_4in >= 0:
            self.cmb_od.setCurrentIndex(idx_4in)

        self._setup_input_validation()

        # Auto-check for updates on startup (silent). A member QTimer parented
        # to this window is destroyed with it, so a pending timeout can never
        # fire on a deleted widget (avoids a Qt abort during shutdown/tests).
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(lambda: self.check_for_updates(silent=True))
        self._update_timer.start(2000)

    def on_activity_unit_changed(self):
        unit = self.cmb_activity_unit.currentText()
        try:
            val = float(self.txt_app_activity.text().replace(",", "."))
            if unit == "GBq":
                # Changed from Ci to GBq (1 Ci = 37 GBq)
                self.txt_app_activity.blockSignals(True)
                self.txt_app_activity.setText(f"{val * 37.0:.1f}")
                self.txt_app_activity.blockSignals(False)
            else:
                # Changed from GBq to Ci
                self.txt_app_activity.blockSignals(True)
        except ValueError:
            pass
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

        # Figure list depends on technology and detector shape
        self.update_std_figure_list()
        
        # Also update procedure compliance label and default value
        if is_digital:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (SNR_N):")
            try:
                val = float(self.txt_app_quality.text().replace(",", "."))
                if val < 5.0:
                    self.txt_app_quality.setText("140")
            except ValueError:
                self.txt_app_quality.setText("140")
        else:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (D):")
            try:
                val = float(self.txt_app_quality.text().replace(",", "."))
                if val >= 5.0:
                    self.txt_app_quality.setText("2.5")
            except ValueError:
                self.txt_app_quality.setText("2.5")

        self._update_output_visibility()
        self.update_calculations()

    def _update_base_e(self):
        """Refreshes the exposure chart constant (E) label, tooltip and visibility.

        E is only used by the physics model; when a manufacturer chart is
        selected the field is hidden because the chart path ignores E.
        """
        unit = "mA·min/m²" if self.cmb_source.currentIndex() == 0 else "Ci·min/m²"
        self.lbl_base_e.setText(f"{self.trans.get('base_factor')} ({unit}):")
        self.txt_base_e.setToolTip(self.trans.get("tt_base_factor"))
        chart = self.cmb_chart_source.currentData()
        visible = (chart == "model")
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

        self.update_calculations()

    def on_chart_source_changed(self):
        chart_source = self.cmb_chart_source.currentData()
        if chart_source == "type_x":
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

        if is_digital:
            if geometry == "swsi":
                if is_planar:
                    add("fig2b_title", "fig2b")
                    add("fig5b_title", "fig5b")
                    add("fig8b_title", "fig8b")
                    add("fig9b_title", "fig9b")
                    add("fig10b_title", "fig10b")
                else:
                    add("fig5a_title", "fig5a")
                    add("fig6a_title", "fig6a")
                    add("fig7a_title", "fig7a")
                    add("fig8a_title", "fig8a")
                    add("fig9a_title", "fig9a")
                    add("fig10a_title", "fig10a")
            elif geometry in ["dwdi_elliptic", "dwdi_super"]:
                add("fig11_title", "fig11")
                add("fig12_title", "fig12")
            else:  # dwsi
                if is_planar:
                    add("fig13b_title", "fig13b")
                    add("fig14b_title", "fig14b")
                else:
                    add("fig13a_title", "fig13a")
        else:  # analog - ISO 17636-1 film arrangements
            if geometry == "swsi":
                add("fig5_title", "fig5")
                add("fig6_title", "fig6")
                add("fig7_title", "fig7")
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

    def retranslate_ui(self):
        # Update Window title
        self.setWindowTitle(self.trans.get("app_title"))
        self.lbl_title.setText(self.trans.get("app_title"))
        self.btn_lang.setText(self.trans.get("lang_switch"))
        self.btn_lvl3.setText(self.trans.get("level3_section"))
        self.btn_export.setText(self.trans.get("export_pdf"))
        self.btn_theme.setText(self.trans.get("theme_light") if self.is_dark_theme else self.trans.get("theme_dark"))

        # Re-populate dropdowns with current language text
        material_idx = self.cmb_material.currentIndex()
        self.cmb_material.clear()
        for key in ("steel", "aluminum", "titanium", "copper_nickel"):
            self.cmb_material.addItem(self.trans.get(key), key)
        self.cmb_material.setCurrentIndex(material_idx)

        source_idx = self.cmb_source.currentIndex()
        self.cmb_source.clear()
        for key in ("x_ray", "isotope_ir192", "isotope_se75", "isotope_co60",
                    "isotope_yb169", "isotope_tm170"):
            self.cmb_source.addItem(self.trans.get(key), key)
        self.cmb_source.setCurrentIndex(source_idx)

        class_idx = self.cmb_class.currentIndex()
        self.cmb_class.clear()
        for key in ("class_b", "class_a"):
            self.cmb_class.addItem(self.trans.get(key), key)
        self.cmb_class.setCurrentIndex(class_idx)

        geom_idx = self.cmb_geometry.currentIndex()
        self.cmb_geometry.blockSignals(True)
        self.cmb_geometry.clear()
        for key in ("dwsi", "swsi", "dwdi_elliptic", "dwdi_super"):
            self.cmb_geometry.addItem(self.trans.get(key), key)
        self.cmb_geometry.setCurrentIndex(geom_idx)
        self.cmb_geometry.blockSignals(False)

        # Update input labels & text boxes labels
        self.lbl_std_od.setText(self.trans.get("std_pipe_od"))
        self.lbl_custom_od.setText(self.trans.get("custom_pipe_od"))
        self.lbl_std_t.setText(self.trans.get("std_nominal_t"))
        self.lbl_custom_t.setText(self.trans.get("custom_nominal_t"))
        self.txt_custom_od.setPlaceholderText(self.trans.get("custom_od_placeholder"))
        self.txt_custom_t.setPlaceholderText(self.trans.get("custom_t_placeholder"))

        self.rad_analog.setText(self.trans.get("analog_film"))
        self.rad_digital.setText(self.trans.get("digital_cr_dda"))
        self.lbl_film_class_used.setText(self.trans.get("film_class_used"))
        self.lbl_detector_type.setText(self.trans.get("detector_type"))
        # Refresh detector type combobox labels
        for i, tkey in enumerate(self._det_trans_keys):
            self.cmb_detector_type.setItemText(i, self.trans.get(tkey))
        self._retranslate_input_panel()
        self._retranslate_warnings_panel()
        self._retranslate_compliance_panel()
        self.sketch_box.setTitle(self.trans.get("sketch_title"))
        self.chk_source_side_iqi.setText(self.trans.get("source_side_iqi"))

        # Re-translate IQI type & SNR location comboboxes
        self.lbl_iqi_type.setText(self.trans.get("iqi_type"))
        iqi_idx = self.cmb_iqi_type.currentIndex()
        self.cmb_iqi_type.blockSignals(True)
        self.cmb_iqi_type.clear()
        self.cmb_iqi_type.addItem(self.trans.get("iqi_type_wire"), "wire")
        self.cmb_iqi_type.addItem(self.trans.get("iqi_type_step_hole"), "step_hole")
        self.cmb_iqi_type.setCurrentIndex(iqi_idx)
        self.cmb_iqi_type.blockSignals(False)

        self.lbl_snr_location.setText(self.trans.get("snr_location"))
        snr_idx = self.cmb_snr_location.currentIndex()
        self.cmb_snr_location.blockSignals(True)
        self.cmb_snr_location.clear()
        self.cmb_snr_location.addItem(self.trans.get("snr_location_weld"), "weld")
        self.cmb_snr_location.addItem(self.trans.get("snr_location_adjacent"), "adjacent")
        self.cmb_snr_location.setCurrentIndex(snr_idx)
        self.cmb_snr_location.blockSignals(False)

        # Obsolete inputs deleted

        # Re-translate Output Labels & Tooltips
        for name, (lbl, val) in self.out_labels.items():
            if name == "quality_target":
                target_name = "target_snr" if self.rad_digital.isChecked() else "optical_density"
                lbl.setText(self.trans.get(target_name))
            elif name == "single_wire_iqi":
                if self.cmb_iqi_type.currentData() == "step_hole":
                    lbl.setText(self.trans.get("single_step_hole_iqi"))
                else:
                    lbl.setText(self.trans.get("single_wire_iqi"))
            elif name == "sfd_min":
                lbl.setText(self.trans.get(
                    "sfd_min" if self.rad_digital.isChecked() else "sfd_min_analog"))
            else:
                lbl.setText(self.trans.get(name))
            
            # Update info button tooltip
            if name in self.info_buttons:
                self.info_buttons[name].setToolTip(self.trans.get("tt_" + name))

        # Re-translate defect evaluation UI
        self._retranslate_defect_panel()

        # Update tab titles
        self.tab_sketch.setTabText(0, self.trans.get("tab_dynamic"))
        self.tab_sketch.setTabText(1, self.trans.get("tab_standard"))

        # Update QGroupBox titles for exposure section
        self.grp_exposure.setTitle(self.trans.get("applied_exposure_section"))
        self.grp_compliance.setTitle(self.trans.get("procedure_section"))
        if hasattr(self, "grp_report_info"):
            self.grp_report_info.setTitle(self.trans.get("report_info_section"))
            for attr, key, _ in self._report_fields:
                self._report_labels[attr].setText(self.trans.get(key))

        self.lbl_app_sfd.setText(self.trans.get(
            "applied_sdd" if self.rad_digital.isChecked() else "applied_sfd"))
        self.lbl_app_time.setText(self.trans.get("applied_time"))
        self.lbl_app_kv.setText(self.trans.get("applied_kv"))
        self.lbl_app_activity.setText(self.trans.get("applied_activity"))
        self.lbl_base_multiplier.setText(self.trans.get("base_multiplier"))
        self.txt_base_multiplier.setToolTip(self.trans.get("tt_base_multiplier"))
        self._update_base_e()

        # Standard selector retranslation
        if hasattr(self, "cmb_standard"):
            std_idx = self.cmb_standard.currentIndex()
            self.cmb_standard.blockSignals(True)
            self.cmb_standard.clear()
            self.cmb_standard.addItem(self.trans.get("standard_iso"), "iso")
            self.cmb_standard.addItem(self.trans.get("standard_asme"), "asme")
            self.cmb_standard.setCurrentIndex(std_idx)
            self.cmb_standard.blockSignals(False)

        # ASME IQI sensitivity retranslation
        if hasattr(self, "cmb_asme_sensitivity"):
            s_idx = self.cmb_asme_sensitivity.currentIndex()
            self.lbl_asme_sensitivity.setText(self.trans.get("asme_sensitivity"))
            self.cmb_asme_sensitivity.blockSignals(True)
            self.cmb_asme_sensitivity.clear()
            self.cmb_asme_sensitivity.addItem(self.trans.get("sens_2_2t"), "2-2T")
            self.cmb_asme_sensitivity.addItem(self.trans.get("sens_2_1t"), "2-1T")
            self.cmb_asme_sensitivity.addItem(self.trans.get("sens_1_2t"), "1-2T")
            self.cmb_asme_sensitivity.setCurrentIndex(s_idx)
            self.cmb_asme_sensitivity.blockSignals(False)

        # Collimator / barrier limit labels
        if hasattr(self, "lbl_collimator"):
            self.lbl_collimator.setText(self.trans.get("collimator"))
            self.lbl_barrier_limit.setText(self.trans.get("barrier_limit_label"))
            self.lbl_gamma_convention.setText(self.trans.get("gamma_convention"))
            self.cmb_gamma_convention.setToolTip(self.trans.get("tt_gamma_convention"))
            g_idx = self.cmb_gamma_convention.currentIndex()
            self.cmb_gamma_convention.blockSignals(True)
            self.cmb_gamma_convention.clear()
            self.cmb_gamma_convention.addItem(self.trans.get("gamma_conv_r"), "r")
            self.cmb_gamma_convention.addItem(self.trans.get("gamma_conv_msv"), "msv")
            self.cmb_gamma_convention.setCurrentIndex(g_idx)
            self.cmb_gamma_convention.blockSignals(False)
            self.btn_decay.setText(self.trans.get("decay_dialog"))

        if self.cmb_iqi_type.currentData() == "step_hole":
            self.lbl_app_wire.setText(self.trans.get("applied_step_hole"))
        else:
            self.lbl_app_wire.setText(self.trans.get("applied_wire"))

        self.lbl_app_duplex.setText(self.trans.get("applied_duplex"))
        self.lbl_app_srb.setText(self.trans.get("applied_srb"))
        self.lbl_app_overlap.setText(self.trans.get("applied_overlap"))

        # Panel coverage inputs (digital only)
        self.lbl_panel_width.setText(self.trans.get("panel_width"))
        self.lbl_panel_height.setText(self.trans.get("panel_height"))
        self.lbl_panel_overlap.setText(self.trans.get("panel_overlap"))
        self.lbl_app_exposures.setText(self.trans.get("applied_exposures"))

        is_digital = self.rad_digital.isChecked()
        if is_digital:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (SNR_N):")
        else:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (D):")

        # Re-populate standard figure dropdown
        self.update_std_figure_list()

        # Update dynamic standard figure text
        self.lbl_dynamic_standard_ref.setText(f"{self.trans.get('standard_fig')} {self.cmb_std_figure.currentText()}")

        # Redraw
        self.update_calculations()

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
            (self.txt_app_activity, 0.01, 1000.0),
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
            (self.txt_app_quality, 0.01, 10000.0),
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

    def get_form_values(self):
        """
        Parses form text inputs safely.
        """
        # Outer Diameter (OD) fallback logic
        custom_od_str = self.txt_custom_od.text().strip().replace(",", ".")
        od = None
        od_from_custom = False
        if custom_od_str:
            try:
                val = float(custom_od_str)
                if val > 0:
                    od = val
                    od_from_custom = True
            except ValueError:
                pass

        if od is None:
            key = self.cmb_od.currentData()
            od = ASME_B36_10_PIPES.get(key, (114.3, []))[0]

        # Wall Thickness (t) fallback logic
        custom_t_str = self.txt_custom_t.text().strip().replace(",", ".")
        t = None
        t_from_custom = False
        if custom_t_str:
            try:
                val = float(custom_t_str)
                if val > 0:
                    t = val
                    t_from_custom = True
            except ValueError:
                pass

        if t is None:
            t = self.cmb_t.currentData()
            if t is None:
                t = 8.56

        try:
            cap = float(self.txt_cap.text().replace(",", "."))
        except ValueError:
            cap = 3.0

        try:
            weld_width = float(self.txt_weld_width.text().replace(",", "."))
        except ValueError:
            weld_width = 8.0

        try:
            d = float(self.txt_d.text().replace(",", "."))
        except ValueError:
            d = 2.0

        try:
            sfd = float(self.txt_app_sfd.text().replace(",", "."))
        except ValueError:
            sfd = 600.0

        source_idx = self.cmb_source.currentIndex()
        if source_idx == 0:  # X-Ray
            try:
                output_val = float(self.txt_output.text().replace(",", "."))
            except ValueError:
                output_val = 5.0
        else:  # Isotopes
            try:
                raw_act = float(self.txt_app_activity.text().replace(",", "."))
                unit = self.cmb_activity_unit.currentText() if hasattr(self, 'cmb_activity_unit') else "Ci"
                if unit == "GBq":
                    output_val = raw_act / 37.0
                else:
                    output_val = raw_act
            except ValueError:
                output_val = 40.0

        try:
            base_e = float(self.txt_base_e.text().replace(",", "."))
        except ValueError:
            base_e = 0.005

        # Detector type (digital) or film class (analog)
        detector_type = self._det_keys[self.cmb_detector_type.currentIndex()]
        film_class_used = self.cmb_film_class_used.currentText() or "C5"

        # Chart source
        chart_source = self.cmb_chart_source.currentData() if hasattr(self, 'cmb_chart_source') else "model"

        # Apply unit conversion only for custom-entered values (od/t from text fields)
        # Standard pipe combo values are already in mm and must NOT be double-converted
        return (self._to_mm(od) if od_from_custom else od,
                self._to_mm(t) if t_from_custom else t,
                self._to_mm(cap), self._to_mm(weld_width),
                self._to_mm(d), self._to_mm(sfd), output_val, base_e,
                detector_type, film_class_used, chart_source)

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
        "txt_barrier_limit", "txt_report_no", "txt_project", "txt_welder_id",
        "txt_wps_pqr", "txt_procedure_no", "txt_device_serial",
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
            if w is not None:
                state[attr] = w.text()
        return state

    def apply_form_state(self, state):
        """Restores widget values from a collected state dict."""
        if not isinstance(state, dict):
            return
        if "language" in state and state["language"] in ("tr", "en"):
            self.trans.set_language(state["language"])
        for attr in self._PRESET_COMBOS:
            w = getattr(self, attr, None)
            val = state.get(attr)
            if w is None or val is None:
                continue
            if isinstance(val, int):
                idx = val
            elif isinstance(val, str):
                try:
                    idx = int(val)
                except ValueError:
                    idx = w.findData(val)
            else:
                idx = w.findData(val)
            if 0 <= idx < w.count():
                w.blockSignals(True)
                w.setCurrentIndex(idx)
                w.blockSignals(False)
        for attr in self._PRESET_EDITS:
            w = getattr(self, attr, None)
            if w is not None and attr in state:
                w.setText(str(state[attr]))
        for attr, widget in (("rad_analog", self.rad_analog),
                             ("rad_detector_flat", self.rad_detector_flat),
                             ("rad_detector_curved", self.rad_detector_curved),
                             ("chk_source_side_iqi", self.chk_source_side_iqi)):
            if attr in state:
                v = state[attr]
                if isinstance(v, str):
                    v = v.lower() in ("1", "true", "yes", "checked")
                widget.setChecked(bool(v))
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
        """
        Shared geometric calculation block used by update_calculations and
        export_pdf_report so the UI and the PDF always agree.

        Detector model — ISO 17636-2:2022 Clause 7.6:
          * Planar/rigid detector (Figures 2 b), 8 b), 13 b), 14 b)):
              b = b_ed + b_gap + k·t (Formulae 8/9, k = 1.2 Class A / 1.1 Class B)
              f_min* = f_min(b=t) · (b/t)^(1/3) when b/t > 1.2 (Formula 13).
              For the central projection (Figure 5 b)): b = b_ed + b_gap + t.
          * Flexible detector wrapped on the pipe (Figures 2 a), 8 a), 13 a), ...):
              b = t (SWSI/DWSI) or De (DWDI, Clause 6.7.2);
              f_min = C · d · b_eff^(2/3) (Formulae 2/3).

        Ug is evaluated with f = SDD − b (ASME Sec V Art 2 T-274.2; ISO 3.21/3.22).

        Level 3 reductions (ISO 17636-2 Clause 7.6) and the DWSI physical SFD
        floor (source outside the pipe) are applied HERE so that the screen,
        the compliance checker and the PDF all consume the same values.

        Returns dict: b_dist, b_eff, b_rule_applied, f_min (governing, after
        L3), f_min_iso, f_min_asme, sfd_min, sdd_min, dwsi_physical_min,
        lvl3_dw, lvl3_central, ug, f_min_star, ci_factor, is_planar, ...
        """
        if standard is None:
            standard = self.cmb_standard.currentData() if hasattr(self, "cmb_standard") else "iso"
        if lvl3_settings is None:
            lvl3_settings = getattr(self, "lvl3_settings", {}) or {}

        # "flat" = planar/rigid detector; "curved" = flexible detector wrapped
        # on the pipe. The planar-detector Formulae (8)/(9)/(13) exist only in
        # ISO 17636-2 (digital); analog film always uses the film model.
        is_digital = self.rad_digital.isChecked() if hasattr(self, "rad_digital") else True
        is_planar = is_digital and (
            self.rad_detector_flat.isChecked() if hasattr(self, "rad_detector_flat") else True)
        std_figure = self.cmb_std_figure.currentData() if hasattr(self, 'cmb_std_figure') else None
        try:
            bed = self._to_mm(float(self.txt_bed.text().replace(",", ".")))
        except ValueError:
            bed = 0.0

        # Planar detector edge lift b_ed (ISO 17636-2 Formula 10). For DWSI the
        # value can be derived from the number of exposures N (alpha = pi/N,
        # Figure 23); it is used automatically when the bed field is left at 0.
        bed_user = bed
        bed_auto = False
        bed_auto_suggested = None
        if is_planar and geometry == "dwsi" and od > 0.0:
            try:
                n_exposures = self.calc.calculate_dwsi_exposures(od, t, sfd, testing_class)
            except Exception:
                n_exposures = 3
            bed_auto_suggested = self.calc.calculate_b_ed(od / 2.0, n_exposures)
            if bed <= 0.0:
                bed = bed_auto_suggested
                bed_auto = True
        try:
            bgap = self._to_mm(float(self.txt_bgap.text().replace(",", ".")))
        except ValueError:
            bgap = 5.0

        f_min_star = None
        ci_factor = None
        if geometry in ["dwdi_elliptic", "dwdi_super"]:
            # ISO 17636-2:2022 Clause 7.6: for DWDI (Figures 11/12) b is always
            # replaced by the external diameter De, whatever the detector type.
            b_dist = od
            f_min_iso_base = self.calc.calculate_f_min(d, b_dist, testing_class, t)
        elif is_planar:
            if self.calc.is_central_projection(geometry, std_figure):
                b_dist = self.calc.calculate_b_panoramic(bed, bgap, t)
            else:
                b_dist = self.calc.calculate_b_curved(bed, bgap, t, testing_class)
            # Formula (13): f_min* governs planar detectors. If b/t <= 1.2 the
            # plain f_min(b=t) applies (Formulae 2/3 with b replaced by t).
            f_min_star, ci_factor = self.calc.calculate_f_min_star(d, b_dist, t, testing_class)
            if f_min_star is not None:
                f_min_iso_base = f_min_star
            else:
                f_min_iso_base = self.calc.calculate_f_min(d, t, testing_class, t)
        else:
            b_dist = t
            f_min_iso_base = self.calc.calculate_f_min(d, b_dist, testing_class, t)
        b_eff, b_rule_applied = self.calc.get_effective_b(b_dist, t)

        # ASME Sec V Art 2 T-274.2: f_min is derived from the allowed Ug limit
        f_min_asme_base = None
        if standard == "asme":
            f_min_asme_base = self.calc.calculate_asme_f_min(d, b_dist, t)

        # Receptor diagonal for the coverage constraint:
        #   digital -> dd = diagonal of the panel active area (ISO 17636-2 F7)
        #   analog  -> df = diagonal of the film sheet      (ISO 17636-1 F4)
        if is_digital:
            try:
                panel_w, panel_h, _panel_ov, _panel_app = self.get_panel_inputs()
            except Exception:
                panel_w, panel_h = 200.0, 200.0
            receptor_w, receptor_h = panel_w, panel_h
            dd = self.calc.calculate_diagonal(panel_w, panel_h)
            df = None
        else:
            receptor_w, receptor_h, df = self.get_film_inputs()
            dd = None
        receptor_size = dd if is_digital else df
        coverage_min = self.calc.calculate_coverage_min(receptor_size)

        # Physical floor for DWSI: source outside, detector across the pipe
        dwsi_physical_min = 0.0
        if geometry == "dwsi" and od > 0.0:
            dwsi_physical_min = od + max(0.0, bgap)

        # Level 3 reductions (ISO 17636-2:2022 Clause 7.6)
        lvl3_dw = bool(lvl3_settings.get("dw_reduction")) and self.calc.is_double_wall_technique(geometry)
        lvl3_central = bool(lvl3_settings.get("central_proj_reduction")) and self.calc.is_central_projection(geometry, std_figure)
        l3_factor = (0.8 if lvl3_dw else 1.0) * (0.5 if lvl3_central else 1.0)

        f_min_iso = f_min_iso_base * l3_factor
        f_min_asme = f_min_asme_base * l3_factor if f_min_asme_base is not None else None
        f_min = f_min_asme if standard == "asme" else f_min_iso

        sfd_min = f_min + b_dist
        if coverage_min > sfd_min:
            sfd_min = coverage_min
        if dwsi_physical_min > sfd_min:
            sfd_min = dwsi_physical_min

        # Ug = d·b/f with f = SDD − b (never SDD itself)
        ug = self.calc.calculate_geometric_unsharpness_from_sfd(d, b_dist, sfd)

        return {
            "b_dist": b_dist,
            "b_eff": b_eff,
            "b_rule_applied": b_rule_applied,
            "f_min": f_min,
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme,
            "f_min_iso_base": f_min_iso_base,
            "f_min_asme_base": f_min_asme_base,
            "sfd_min": sfd_min,
            "sdd_min": coverage_min,
            "coverage_min": coverage_min,
            "receptor_w": receptor_w,
            "receptor_h": receptor_h,
            "receptor_size": receptor_size,
            "df": df,
            "dd": dd,
            "is_digital": is_digital,
            "dwsi_physical_min": dwsi_physical_min,
            "lvl3_dw": lvl3_dw,
            "lvl3_central": lvl3_central,
            "ug": ug,
            "f_min_star": f_min_star,
            "ci_factor": ci_factor,
            "is_planar": is_planar,
            "is_curved": not is_planar,
            "std_figure": std_figure,
            "standard": standard,
            "bed": bed,
            "bed_user": bed_user,
            "bed_auto": bed_auto,
            "bed_auto_suggested": bed_auto_suggested,
            "bgap": bgap,
        }

    def update_calculations(self):
        # 1. Fetch values
        od, t, cap, weld_width, d, sfd, output_val, base_e, detector_type, film_class_used, chart_source = self.get_form_values()
        
        material_keys = ["steel", "aluminum", "titanium", "copper_nickel"]
        material = material_keys[self.cmb_material.currentIndex()]

        tech = "digital" if self.rad_digital.isChecked() else "analog"
        
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60", "isotope_yb169", "isotope_tm170"]
        source = source_keys[self.cmb_source.currentIndex()]

        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"

        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]

        # 2. Geometry Constraints
        # Disable/Enable geometry combinations
        # DWDI is only active if OD <= 100 mm
        user_geometry = geometry
        self._update_weld_width_visibility(geometry)
        if od > 100.0:
            if geometry in ["dwdi_elliptic", "dwdi_super"]:
                # Force to DWSI if user has selected a DWDI but diameter is too large
                self.cmb_geometry.setCurrentIndex(0)
                geometry = "dwsi"
        
        # 3. Dynamic calculations
        warnings = []
        w_nom, w_eff = self.calc.calculate_thicknesses(t, cap, geometry)
        
        # Tube Voltage kV
        u_max = self.calc.calculate_u_max(w_nom, material)

        # Inspection standard (ISO 17636 / ASME Sec V Art 2)
        standard = self.cmb_standard.currentData() if hasattr(self, "cmb_standard") else "iso"

        # Shared geometry block (b, f_min, sfd_min, sdd_min, ug, f_min*)
        # Level 3 reductions and the DWSI physical floor are applied inside.
        geo = self._compute_geometry(od, t, d, sfd, geometry, testing_class,
                                     standard=standard, lvl3_settings=self.lvl3_settings)
        b_dist = geo["b_dist"]
        b_eff = geo["b_eff"]
        b_rule_applied = geo["b_rule_applied"]
        f_min = geo["f_min"]
        f_min_iso = geo["f_min_iso"]
        f_min_asme = geo["f_min_asme"]
        sfd_min = geo["sfd_min"]
        sdd_min = geo["sdd_min"]
        coverage_min = geo["coverage_min"]
        ug = geo["ug"]
        f_min_star = geo["f_min_star"]
        ci_factor = geo["ci_factor"]
        std_figure = geo["std_figure"]
        bgap = geo["bgap"]
        dd = geo["dd"]
        df = geo["df"]
        receptor_size = geo["receptor_size"]
        is_digital = geo["is_digital"]

        # ASME/ASTM IQI sensitivity selector visibility (ASME only)
        if hasattr(self, "cmb_asme_sensitivity"):
            self.lbl_asme_sensitivity.setVisible(standard == "asme")
            self.cmb_asme_sensitivity.setVisible(standard == "asme")

        # ASME Sec V Art 2 geometric unsharpness (Ug) limit check
        ug_ok, ug_limit = self.calc.check_ug_compliance(ug, t, standard)
        if standard == "asme" and not ug_ok:
            if self.trans.language == "tr":
                warnings.append(f"UYARI (ASME Sec V Art 2): Ug ({ug:.3f} mm) izin verilen limiti ({ug_limit:.2f} mm) aşıyor. Kaynak-nesne mesafesi (f) artırılmalı.")
            else:
                warnings.append(f"WARNING (ASME Sec V Art 2): Ug ({ug:.3f} mm) exceeds the allowed limit ({ug_limit:.2f} mm). Increase source-to-object distance (f).")

        # Exposures
        if geometry == "swsi":
            exposures = 1
        elif geometry == "dwdi_elliptic":
            exposures = self.calc.get_dwdi_elliptical_exposures(od, t)
        elif geometry == "dwdi_super":
            exposures = 3
        else: # DWSI
            exposures = self.calc.calculate_dwsi_exposures(od, t, sfd, testing_class)

        # Panel-coverage minimum exposures (ISO 17636-2:2022 Clauses 7.6/7.8, digital only)
        n_panel = None
        n_applied = self.get_applied_exposures()
        n_required = exposures
        exposures_ok = None
        if tech == "digital":
            panel_width, panel_height, overlap_pct, _ = self.get_panel_inputs()
            f_override, b_override = self.get_geometry_override_inputs()
            panel_res = self.calc.calculate_panel_exposures(
                od, t, geometry, testing_class, panel_width,
                panel_height=panel_height, cap=cap, sfd=sfd, bgap=bgap,
                overlap_percent=overlap_pct, focal_size=d, std_figure=std_figure,
                b_object=b_override, f_source=f_override,
            )
            if f_override is not None and b_override is not None:
                sum_dist = f_override + b_override
                if abs(sum_dist - sfd) > 5.0:
                    if self.trans.language == "tr":
                        warnings.append(f"UYARI: Ölçülen geometri (f+b={sum_dist:.1f} mm) uygulanan SFD'den ({sfd:.1f} mm) farklı.")
                    else:
                        warnings.append(f"WARNING: Measured geometry (f+b={sum_dist:.1f} mm) differs from applied SFD ({sfd:.1f} mm).")
            if b_override is not None and b_override < t:
                if self.trans.language == "tr":
                    warnings.append(f"UYARI: b ({b_override:.1f} mm) et kalınlığından (t={t:.1f} mm) küçük — ölçümü kontrol edin.")
                else:
                    warnings.append(f"WARNING: b ({b_override:.1f} mm) is smaller than the wall thickness (t={t:.1f} mm) — check the measurement.")
            if f_override is not None and f_override < panel_res["f_min_applied"]:
                if self.trans.language == "tr":
                    warnings.append(f"UYARI: f ({f_override:.1f} mm) ISO 17636-2 Madde 7.6 geometrik sınırı olan f_min ({panel_res['f_min_applied']:.1f} mm) altında — f_min kullanıldı.")
                else:
                    warnings.append(f"WARNING: f ({f_override:.1f} mm) is below the Clause 7.6 geometric limit f_min ({panel_res['f_min_applied']:.1f} mm) — f_min applied.")
            n_panel = panel_res["n_panel"]
            cmp_res = self.calc.evaluate_exposure_comparison(exposures, n_panel, n_applied if n_applied > 0 else max(exposures, n_panel))
            n_required = cmp_res["n_required"]
            if n_applied > 0:
                exposures_ok = (n_applied >= n_required)
            if panel_res["limiting_factor"] == "panel":
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ: Panel aktif genişliği ({panel_width:.0f} mm) poz sayısını sınırlıyor (θ={panel_res['theta_panel_deg']:.1f}°).")
                else:
                    warnings.append(f"NOTE: Panel active width ({panel_width:.0f} mm) limits exposure count (θ={panel_res['theta_panel_deg']:.1f}°).")
            if not panel_res["panel_height_ok"]:
                if self.trans.language == "tr":
                    warnings.append(f"UYARI: Panel aktif yüksekliği ({panel_height:.0f} mm) WAE genişliğini ({panel_res['wae_width_mm']:.1f} mm) karşılamıyor.")
                else:
                    warnings.append(f"WARNING: Panel active height ({panel_height:.0f} mm) is smaller than WAE width ({panel_res['wae_width_mm']:.1f} mm).")
            if n_applied > 0 and not exposures_ok:
                if self.trans.language == "tr":
                    warnings.append(f"UYARI: Uygulanan poz sayısı ({n_applied}) gerekli minimumu ({n_required}) karşılamıyor.")
                else:
                    warnings.append(f"WARNING: Applied exposures ({n_applied}) do not meet the required minimum ({n_required}).")
        else:
            # Analog mode
            n_required = exposures
            if n_applied > 0:
                exposures_ok = (n_applied >= n_required)
                if not exposures_ok:
                    if self.trans.language == "tr":
                        warnings.append(f"UYARI: Uygulanan poz sayısı ({n_applied}) standartın gerektirdiği asgari poz sayısını ({n_required}) karşılamıyor.")
                    else:
                        warnings.append(f"WARNING: Applied exposures ({n_applied}) do not meet the required minimum ({n_required}).")

        # Parse kV input for X-ray early
        if source == "x_ray":
            try:
                input_kv = float(self.txt_app_kv.text().replace(",", "."))
            except ValueError:
                input_kv = 120.0
        else:
            input_kv = None

        # IQI Type Selection
        iqi_type = self.cmb_iqi_type.currentData()
        film_side = not self.chk_source_side_iqi.isChecked()
        
        # Update label dynamically
        label_key = "single_step_hole_iqi" if iqi_type == "step_hole" else "single_wire_iqi"
        self.out_labels["single_wire_iqi"][0].setText(self.trans.get(label_key))
        
        if iqi_type == "step_hole":
            wire_str, wire_no = self.calc.get_step_hole_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=self.trans.language)
        else:
            wire_str, wire_no = self.calc.get_single_wire_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=self.trans.language)

        # Digital-only quality values are not computed in analog mode (and vice
        # versa) so that no cross-mode value leaks into the UI or the report.
        if tech == "digital":
            duplex_str, duplex_no = self.calc.get_duplex_iqi(w_nom, testing_class, geometry, lang=self.trans.language)
        else:
            duplex_str, duplex_no = "N/A", None

        # Step 7: Detector Quality
        if tech == "analog":
            film_class_req = self.calc.get_required_film_class(w_nom, testing_class, material, source)
            max_srb_req = None
        else:
            film_class_req = None
            max_srb_req = self.calc.get_max_srb(w_nom, testing_class, geometry)
        if tech == "analog":
            detector_quality_str = f"{film_class_req} Film"
        else:
            detector_quality_str = f"Max {max_srb_req} µm"

        # Quality Targets & Level 3 Compensation
        target_quality = ""
        sfd_comp_target = None
        
        if tech == "analog":
            # For analog, target is Optical Density
            # Class A: OD >= 2.0. Class B: OD >= 2.3
            # Clause 6.9 exception: Se-75 w_nom < 12mm Class B steel/copper-nickel -> OD >= 3.0
            if material in ["steel", "copper_nickel"] and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b":
                required_density = 3.0
            else:
                required_density = 2.3 if testing_class == "class_b" else 2.0
            
            target_quality = f">= {required_density:.1f} (Max 4.0)"
            target_snr_val = 130.0 if testing_class == "class_b" else 70.0 # fallback for last_calculated
            time_multiplier = 1.0
        else: # Digital
            # Base SNR_N target: dynamic lookup
            base_snr, table_name, desc = self.calc.get_target_snr(material, source, input_kv, w_nom, testing_class, lang=self.trans.language)
            
            # Location check: if adjacent to weld and cap > 0.0, multiply base_snr by 1.4
            snr_location = self.cmb_snr_location.currentData()
            is_flush = (cap == 0.0)
            
            # Se-75 w_nom < 12mm Class B steel/copper-nickel -> also 1.4x factor (base SNR_N is 100, target SNR_N = 100 * 1.4 = 140)
            se75_thin_class_b = (material in ["steel", "copper_nickel"] and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b")
            
            # Determine if 1.4x multiplier applies:
            apply_multiplier = False
            if snr_location == "adjacent" and not is_flush:
                apply_multiplier = True
            if se75_thin_class_b:
                apply_multiplier = True
                
            if apply_multiplier:
                target_snr_val = base_snr * 1.4
                if snr_location == "adjacent" and not is_flush:
                    # Append system info message
                    warnings.append(self.trans.get("warn_snr_adjacent_factor"))
            else:
                target_snr_val = base_snr
                
            # Distance Compensation Check
            if sfd < sfd_min and self.lvl3_settings["sfd_comp"]:
                k_factor = sfd_min / max(10.0, sfd)
                sfd_comp_target = target_snr_val * k_factor
                target_quality = f"{target_snr_val:.1f} -> {sfd_comp_target:.1f} (Lvl 3 Comp) [{table_name}]"
                time_multiplier = k_factor ** 2
            else:
                target_quality = f">= {int(target_snr_val)} [{table_name}]"
                time_multiplier = 1.0

        # Calculated Exposure Time
        # Scaled by time_multiplier from Level 3 compensation if active
        resolved_film = film_class_used if chart_source == "model" else chart_source
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            sfd, w_eff, source, output_val, base_e, tech,
            testing_class=testing_class,
            film_class=film_class_used,
            detector_type=detector_type,
            kv=input_kv,
            material=material,
            chart_source=chart_source if chart_source != "model" else None,
            chart_db=self.chart_db,
        )
        
        if sfd_comp_target is not None:
            # apply compensation multiplier
            raw_time = raw_time * time_multiplier
            min_calc = int(raw_time // 60)
            sec_calc = int(raw_time % 60)

        # Base exposure multiplier: scales the model time for field conditions
        base_multiplier = self.get_base_multiplier()
        try:
            raw_mult = float(self.txt_base_multiplier.text().strip().replace(",", "."))
        except ValueError:
            raw_mult = 1.0
        if raw_mult <= 0.0:
            if self.trans.language == "tr":
                warnings.append("UYARI: Saha Düzeltme Çarpanı (F) geçersiz/pozitif değil; 1.0 olarak uygulandı.")
            else:
                warnings.append("WARNING: Field Correction Factor (F) is invalid/non-positive; 1.0 applied.")
        elif base_multiplier < 0.5 or base_multiplier > 2.0:
            if self.trans.language == "tr":
                warnings.append(f"UYARI: Saha Düzeltme Çarpanı (F={base_multiplier:.2f}) olağan aralığın (0.5–2.0) dışında; değer teknik/ekipman doğrulama kaydıyla desteklenmelidir.")
            else:
                warnings.append(f"WARNING: Field Correction Factor (F={base_multiplier:.2f}) is outside the usual range (0.5–2.0); the value should be supported by a technique/equipment qualification record.")
        if base_multiplier != 1.0:
            raw_time = raw_time * base_multiplier
            min_calc = int(raw_time // 60)
            sec_calc = int(raw_time % 60)

        # 4. Warnings Generation
        # Sınıf A warning
        if testing_class == "class_a":
            warnings.append(self.trans.get("warn_class_a"))

        # DWDI geometry validation (ISO 17636-1:2022 Clauses 7.1.6 / 7.1.7)
        if user_geometry in ["dwdi_elliptic", "dwdi_super"]:
            if user_geometry != geometry:
                # user_geometry was DWDI but geometry was forced to DWSI (OD > 100)
                warnings.append(self.trans.get("info_dwdi_forced_swsi"))
            dwdi_res = self.calc.validate_dwdi(user_geometry, od, t, weld_width)
            if not dwdi_res["od_ok"]:
                warnings.append(self.trans.get("warn_dwdi_limit"))
            if user_geometry == "dwdi_elliptic":
                if not dwdi_res["t_ok"]:
                    warnings.append(self.trans.get("warn_dwdi_t_limit"))
                if not dwdi_res["weld_width_ok"]:
                    warnings.append(self.trans.get("warn_dwdi_weld_width", weld_width, od / 4.0))
                if dwdi_res["needs_three"]:
                    warnings.append(self.trans.get("info_dwdi_elliptic_3"))
                else:
                    warnings.append(self.trans.get("info_dwdi_elliptic_2"))
            else:
                warnings.append(self.trans.get("info_dwdi_super_exposures"))

        # Isotope on light metal check
        if source != "x_ray" and material in ["aluminum", "titanium"]:
            warnings.append(self.trans.get("warn_isotope_light_metal"))

        # Radiographic equivalence factor (informational, non-steel materials)
        if material != "steel":
            ref = self.calc.get_ref_factor(material)
            t_steel = self.calc.equivalent_steel_thickness(w_nom, material)
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (REF): {self.trans.get(material)} radyografik eşdeğerlik faktörü REF={ref:.2f}; eşdeğer çelik kalınlığı ≈ {t_steel:.2f} mm.")
            else:
                warnings.append(f"INFO (REF): {self.trans.get(material)} radiographic equivalence factor REF={ref:.2f}; equivalent steel thickness ≈ {t_steel:.2f} mm.")

        # b < 1.2t rule: warn when effective b is adjusted
        if b_rule_applied:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): b ({b_dist:.1f} mm) < 1.2×t ({1.2*t:.1f} mm) olduğundan b = t ({t:.1f} mm) kullanıldı.")
            else:
                warnings.append(f"NOTE (Clause 7.6): b ({b_dist:.1f} mm) < 1.2×t ({1.2*t:.1f} mm), using b = t ({t:.1f} mm).")

        # Planar detector edge lift b_ed (Formula 10) provenance
        if geo["bed_auto"]:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Planar dedektör kenar yüksekliği (bed) girilmedi; Formül (10) ile b_ed = {geo['bed']:.1f} mm otomatik kullanıldı (N poz, α=π/N).")
            else:
                warnings.append(f"NOTE (Clause 7.6): Planar detector edge lift (bed) not provided; b_ed = {geo['bed']:.1f} mm computed automatically with Formula (10) (N exposures, alpha=pi/N).")
        elif geo["is_planar"] and geometry == "swsi" and geo["bed_user"] <= 0.0:
            if self.trans.language == "tr":
                warnings.append("UYARI (Madde 7.6): Planar dedektörde bed=0; kenar yüksekliğini Şekil 23 / ölçekli çizimden girin (b_ed = (1−cos α)·r_e).")
            else:
                warnings.append("WARNING (Clause 7.6): Planar detector with bed=0; enter the edge lift from Figure 23 / a scaled drawing (b_ed = (1-cos alpha)*r_e).")
        elif (geo["bed_auto_suggested"] is not None and 0.0 < geo["bed_user"] < geo["bed_auto_suggested"]):
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Girilen bed ({geo['bed_user']:.1f} mm) Formül (10) değerinden ({geo['bed_auto_suggested']:.1f} mm) küçük — kontrol edin.")
            else:
                warnings.append(f"NOTE (Clause 7.6): Entered bed ({geo['bed_user']:.1f} mm) is smaller than the Formula (10) value ({geo['bed_auto_suggested']:.1f} mm) - please verify.")

        # Coverage rule: warn when the receptor diagonal raises the minimum
        # distance (ISO 17636-1 Formula 4 for film / ISO 17636-2 Formula 7 for
        # digital detectors).
        if coverage_min > f_min + b_dist:
            if is_digital:
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Dedektör boyutu (dd={receptor_size:.0f} mm) SDD_min'i {coverage_min:.0f} mm'ye yükseltti.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Detector size (dd={receptor_size:.0f} mm) raises SDD_min to {coverage_min:.0f} mm.")
            else:
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Film köşegeni (df={receptor_size:.0f} mm) SFD_min'i {coverage_min:.0f} mm'ye yükseltti.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Film diagonal (df={receptor_size:.0f} mm) raises SFD_min to {coverage_min:.0f} mm.")
        elif (not is_digital) and coverage_min <= 0.0:
            if self.trans.language == "tr":
                warnings.append("BİLGİ: Film köşegeni (df) girilmedi; SFD ≥ 1,4·df kontrolü yapılamadı (örn. 300×400 mm film → df=500 mm).")
            else:
                warnings.append("NOTE: Film diagonal (df) not provided; the SFD >= 1.4*df check could not be performed (e.g. 300x400 mm film -> df=500 mm).")

        # Annex F IQI compensation check (ISO 17636-2, digital only):
        # Ug/SRb > 2 -> needs compensation
        if is_digital:
            annex_f_needed, annex_f_ratio = self.calc.check_annex_f_compensation(ug, max_srb_req)
            if annex_f_needed:
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Annex F): Ug/SRb ({annex_f_ratio:.1f}) > 2. IQI görünürlüğü için f_min artırılmalı veya SNR yükseltilmelidir.")
                else:
                    warnings.append(f"NOTE (Annex F): Ug/SRb ({annex_f_ratio:.1f}) > 2. Increase f_min or SNR for IQI visibility.")

        # DWSI physical SFD floor: source outside the pipe, detector across it
        if geo["dwsi_physical_min"] > 0.0:
            if sfd < geo["dwsi_physical_min"]:
                if self.trans.language == "tr":
                    warnings.append(f"UYARI (Madde 7.6): DWSI'de uygulanan SFD ({sfd:.1f} mm) fiziksel asgari mesafenin (OD+bgap = {geo['dwsi_physical_min']:.1f} mm) altında. Kaynak boru dışında olamaz.")
                else:
                    warnings.append(f"WARNING (Clause 7.6): Applied SFD ({sfd:.1f} mm) is below the physical minimum for DWSI (OD+bgap = {geo['dwsi_physical_min']:.1f} mm). The source cannot be inside the pipe.")
            elif geo["dwsi_physical_min"] > geo["f_min"] + b_dist:
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): DWSI fiziksel tabanı SFD_min'i {geo['dwsi_physical_min']:.1f} mm'ye (OD+bgap) yükseltti; f_min yalnızca et kalınlığına göre belirlenir.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): The DWSI physical floor raised SFD_min to {geo['dwsi_physical_min']:.1f} mm (OD+bgap); f_min itself is determined only by wall thickness.")

        # Double-wall technique: up to 20% f_min reduction allowed per Clause 7.6
        if self.calc.is_double_wall_technique(geometry):
            if geo["lvl3_dw"]:
                if self.trans.language == "tr":
                    warnings.append(f"Level 3: Çift duvar tekniğinde f_min %20 düşürüldü ({f_min:.1f} mm).")
                else:
                    warnings.append(f"Level 3: Double-wall technique f_min reduced 20% to {f_min:.1f} mm.")
            else:
                f_min_80 = f_min * 0.8
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Çift duvar tekniğinde f_min %20 düşürülebilir ({f_min_80:.1f} mm). IQI şartları sağlanmalıdır.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Double-wall technique allows 20% f_min reduction (to {f_min_80:.1f} mm). IQI requirements must be met.")

        # Central projection (Fig 5): up to 50% f_min reduction allowed
        if self.calc.is_central_projection(geometry, std_figure):
            if geo["lvl3_central"]:
                if self.trans.language == "tr":
                    warnings.append(f"Level 3: Merkezi projeksiyonda f_min %50 düşürüldü ({f_min:.1f} mm).")
                else:
                    warnings.append(f"Level 3: Central projection f_min reduced 50% to {f_min:.1f} mm.")
                # Duplex/SRb tolerance also applies
                if self.trans.language == "tr":
                    warnings.append("BİLGİ (Madde 7.6): Merkezi projeksiyonda 1 duplex adım veya 1 SRb toleransı uygulanır.")
                else:
                    warnings.append("NOTE (Clause 7.6): Central projection allows 1 duplex step or 1 SRb tolerance.")
            else:
                f_min_50 = f_min * 0.5
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Merkezi projeksiyonda f_min %50 düşürülebilir ({f_min_50:.1f} mm). Level 3 onayı gerekiyor.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Central projection allows 50% f_min reduction (to {f_min_50:.1f} mm). Requires Level 3 approval.")

        # f_min* magnification rule: planar detectors use Formula (13) as the
        # governing value when b/t > 1.2
        if f_min_star is not None and ci_factor is not None:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Planar dedektör, b/t = {b_dist/t:.2f} > 1.2 → f_min* = f_min(b=t) × Ci (Ci = {ci_factor:.3f}) geçerlidir.")
            else:
                warnings.append(f"NOTE (Clause 7.6): Planar detector, b/t = {b_dist/t:.2f} > 1.2 → f_min* = f_min(b=t) × Ci (Ci = {ci_factor:.3f}) governs.")

        # ISO 17636-2:2022 Table 2 — Source-thickness compliance
        is_valid, min_lim, max_lim, table2_msg = self.calc.validate_source_thickness(
            source, w_nom, testing_class, material, input_kv
        )
        if not is_valid:
            if self.lvl3_settings["source_flex"]:
                warnings.append(f"Level 3 Approved Exception: {table2_msg}")
            else:
                warnings.append(f"UYARI: {table2_msg}" if self.trans.language == "tr" else f"WARNING: {table2_msg}")
        elif table2_msg:
            warnings.append(table2_msg)

        # Clause 6.9 Isotope Exception Warning
        if material in ["steel", "copper_nickel"]:
            w_pen = w_nom
            active_6_9 = False
            offset_val = 0
            if geometry in ["dwdi_elliptic", "dwdi_super"]:
                if source == "isotope_ir192" and 10.0 < w_pen <= 25.0:
                    active_6_9 = True
                    offset_val = 1
                elif source == "isotope_se75" and w_pen <= 12.0:
                    active_6_9 = True
                    offset_val = 1
            elif geometry in ["swsi", "dwsi"]:
                if testing_class == "class_a":
                    if source == "isotope_ir192":
                        if 10.0 < w_pen <= 24.0:
                            active_6_9 = True
                            offset_val = 2
                        elif 24.0 < w_pen <= 30.0:
                            active_6_9 = True
                            offset_val = 1
                    elif source == "isotope_se75" and w_pen <= 24.0:
                        active_6_9 = True
                        offset_val = 1
                else: # Class B
                    if source == "isotope_ir192" and 10.0 < w_pen <= 40.0:
                        active_6_9 = True
                        offset_val = 1
                    elif source == "isotope_se75" and w_pen <= 20.0:
                        active_6_9 = True
                        offset_val = 1
                        
            if active_6_9:
                if self.trans.language == "tr":
                    warnings.append(f"İSTİSNA (Madde 6.9): {source.split('_')[-1].upper()} kaynağı için asgari IQI değeri {offset_val} tel/delik azaltılabilir.")
                else:
                    warnings.append(f"EXCEPTION (Clause 6.9): For {source.split('_')[-1].upper()} source, minimum IQI value may be reduced by {offset_val} wire/hole.")

        # Se-75 Class B w < 12mm exception warning
        if material in ["steel", "copper_nickel"] and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b":
            if tech == "analog":
                if self.trans.language == "tr":
                    warnings.append("İSTİSNA (Madde 6.9): Se-75 kaynağı w < 12mm Class B için optik yoğunluk asgari 3.0 olmalı ve film sınıfı 1 derece iyileştirilmiştir.")
                else:
                    warnings.append("EXCEPTION (Clause 6.9): For Se-75 source with w < 12mm Class B, min optical density is 3.0 and film class is upgraded by 1 level.")
            else:
                if self.trans.language == "tr":
                    warnings.append("İSTİSNA (Madde 6.9): Se-75 kaynağı w < 12mm Class B için hedef SNR_N 1.4 kat arttırılmıştır (100 -> 140).")
                else:
                    warnings.append("EXCEPTION (Clause 6.9): For Se-75 source with w < 12mm Class B, target SNR_N is increased by 1.4x (100 -> 140).")

        # X-Ray kV warning
        if source == "x_ray":
            if tech == "analog":
                warnings.append(self.trans.get("warn_analog_kv_limit"))
                if input_kv > u_max:
                    if self.lvl3_settings["voltage_override"]:
                        warnings.append("Level 3 Exception Active: Tube Voltage limit check is bypassed by client approval.")
                    else:
                        warnings.append(self.trans.get("warn_input_kv_limit", input_kv, u_max))
            else: # digital
                opt_kv = u_max * 0.85
                warnings.append(self.trans.get("warn_digital_kv_opt", f"{opt_kv:.1f}"))
                warnings.append(self.trans.get("warn_digital_kv_snr"))
                if input_kv > u_max:
                    if self.lvl3_settings["voltage_override"]:
                        warnings.append("Level 3 Exception Active: Tube Voltage limit check is bypassed by client approval.")
                    else:
                        warnings.append(self.trans.get("warn_input_kv_limit", input_kv, u_max))

        # Film class compliance check (Analog only)
        if tech == "analog":
            film_comp, film_msg = self.calc.check_film_class_compliance(film_class_used, testing_class, w_nom, material, source)
            if not film_comp:
                if self.trans.language == "tr":
                    warnings.append(f"UYARI: Kullanılan film sınıfı ({film_class_used}) standart gereksinimini karşılamıyor! Asgari gereken: {film_class_req}")
                else:
                    warnings.append(f"WARNING: Used film class ({film_class_used}) does not meet standard requirement! Required minimum: {film_class_req}")

        # Film Overlap warning
        if tech == "analog":
            try:
                overlap = self._to_mm(float(self.txt_app_overlap.text().replace(",", ".")))
            except ValueError:
                overlap = 10.0
            if overlap < 10.0:
                warnings.append(self.trans.get("warn_overlap_limit", overlap))

        # SFD actual distance check
        if sfd < sfd_min:
            if self.lvl3_settings["sfd_comp"]:
                warnings.append(f"Level 3 Compensation Active: Actual SFD ({sfd:.1f} mm) is smaller than SFD_min ({sfd_min:.1f} mm). Target SNR_N increased.")
            else:
                warnings.append(self.trans.get("warn_f_min_failed", f"{sfd:.1f}", f"{sfd_min:.1f}"))

        # 5. Update GUI output labels
        self.out_labels["w_nom"][1].setText(f"{w_nom:.2f} mm")
        self.out_labels["w_eff"][1].setText(f"{w_eff:.2f} mm")
        
        if source == "x_ray":
            self.out_labels["u_max"][1].setText(f"{u_max:.1f} kV")
        else:
            self.out_labels["u_max"][1].setText("N/A")

        self.out_labels["f_min"][1].setText(f"{f_min_iso:.1f} mm")
        if standard == "asme" and f_min_asme is not None:
            self.out_labels["f_min_asme"][1].setText(f"{f_min_asme:.1f} mm")
        else:
            self.out_labels["f_min_asme"][1].setText("N/A")
        self.out_labels["sfd_min"][1].setText(f"{sfd_min:.1f} mm")
        self.out_labels["ug"][1].setText(f"{ug:.3f} mm")
        self.out_labels["req_exposures"][1].setText(f"{exposures}")

        if n_panel is not None:
            self.out_labels["exposures_panel"][1].setText(f"{n_panel}")
        else:
            self.out_labels["exposures_panel"][1].setText("N/A")

        if n_applied > 0:
            self.out_labels["exposures_applied"][1].setText(f"{n_applied}")
            if exposures_ok:
                check_str = f"UYGUN (≥ {n_required})" if self.trans.language == "tr" else f"OK (≥ {n_required})"
            else:
                check_str = f"UYGUN DEĞİL (< {n_required})" if self.trans.language == "tr" else f"NOT OK (< {n_required})"
            self.out_labels["exposures_check"][1].setText(check_str)
        else:
            self.out_labels["exposures_applied"][1].setText("-")
            self.out_labels["exposures_check"][1].setText(f"≥ {n_required}")

        self.out_labels["single_wire_iqi"][1].setText(wire_str)
        
        if tech == "digital":
            self.out_labels["duplex_iqi"][1].setText(duplex_str)
        else:
            self.out_labels["duplex_iqi"][1].setText("N/A")

        self.out_labels["quality_target"][1].setText(target_quality)
        chart_label = ""
        if chart_source != "model":
            if chart_source == "type_x":
                chart_label = " [Type X]"
            else:
                chart_label = f" [{chart_source}]"
        self.out_labels["calc_time"][1].setText(f"{min_calc} min {sec_calc} sec{chart_label}")
        self.out_labels["detector_quality"][1].setText(detector_quality_str)

        # ASME/ASTM IQI output (ASME Sec V Art 2 only)
        if standard == "asme":
            if iqi_type == "step_hole":
                sensitivity = self.cmb_asme_sensitivity.currentData() if hasattr(self, "cmb_asme_sensitivity") else "2-2T"
                hole = self.calc.get_astm_iqi_hole(t, sensitivity)
                asme_iqi_str = f"{hole['designator']} (T={hole['iqi_t_mm']:.2f} mm, delik ∅={hole['hole_dia_mm']:.2f} mm) [ASTM E1025]"
            else:
                wire = self.calc.get_astm_iqi_wire(w_nom)
                asme_iqi_str = f"Set {wire['set']} W{wire['wire_no']} ({wire['wire_dia_mm']:.3f} mm) [ASTM E747]"
        else:
            asme_iqi_str = "N/A"
        self.out_labels["asme_iqi"][1].setText(asme_iqi_str)

        # Radiation barrier distance (isotopes only)
        if source != "x_ray":
            hvl_layers = float(self.cmb_collimator.currentData() or 0.0)
            try:
                limit_usvh = float(self.txt_barrier_limit.text().replace(",", "."))
            except ValueError:
                limit_usvh = 20.0
            convention = self.cmb_gamma_convention.currentData() if hasattr(self, "cmb_gamma_convention") else "r"
            r_controlled, dose_1m, reduction = self.calc.calculate_barrier_distance(
                source, output_val, limit_usvh=limit_usvh, hvl_layers=hvl_layers,
                convention=convention,
            )
            r_supervised, _, _ = self.calc.calculate_barrier_distance(
                source, output_val, limit_usvh=7.5, hvl_layers=hvl_layers,
                convention=convention,
            )
            if self.trans.language == "tr":
                barrier_str = f"Kontrollü ({limit_usvh:.0f} µSv/h): {r_controlled:.1f} m | Gözetimli (7.5): {r_supervised:.1f} m"
            else:
                barrier_str = f"Controlled ({limit_usvh:.0f} µSv/h): {r_controlled:.1f} m | Supervised (7.5): {r_supervised:.1f} m"
        else:
            barrier_str = "N/A"
            hvl_layers = 0.0
            limit_usvh = 20.0
            convention = "r"
        self.out_labels["barrier_distance"][1].setText(barrier_str)

        self._update_output_visibility()

        # Filter recommendation output
        filter_recs = self.calc.get_filter_recommendations(source, material, input_kv, testing_class)
        # Localize the language-neutral structural data in the UI/i18n layer
        from src.core.translation import format_filter_recommendation
        filter_str = format_filter_recommendation(filter_recs, self.trans.language)

        self.out_labels["filter_recommendation"][1].setText(filter_str)

        # Store calculated results for compliance checker
        self.last_calculated = {
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max,
            "sfd_min": sfd_min,
            "sdd_min": sdd_min,
            "ug": ug,
            "ug_limit": ug_limit,
            "standard": standard,
            "asme_iqi": asme_iqi_str,
            "barrier_distance": barrier_str,
            "barrier_radius_m": r_controlled if source != "x_ray" else 0.0,
            "gamma_convention": convention,
            "collimator_hvl": hvl_layers,
            "barrier_limit_usvh": limit_usvh,
            "f_min": f_min,
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme,
            "is_planar": geo["is_planar"],
            "is_digital": is_digital,
            "lvl3_dw": geo["lvl3_dw"],
            "lvl3_central": geo["lvl3_central"],
            "dwsi_physical_min": geo["dwsi_physical_min"],
            "b_dist": b_dist,
            "b_eff": b_eff,
            "df": df,
            "dd": dd,
            "receptor_size": receptor_size,
            "coverage_min": coverage_min,
            "bed_used": geo["bed"],
            "bed_auto": geo["bed_auto"],
            "required_wire_no": wire_no,
            "required_duplex_no": duplex_no,
            "calc_time_raw": raw_time,
            "required_film_class": film_class_req,
            "max_srb": max_srb_req,
            "filter_recommendation": filter_str
        }
        self.last_calculated["exposures_graph"] = exposures
        self.last_calculated["exposures_panel"] = n_panel
        self.last_calculated["exposures_applied"] = n_applied
        self.last_calculated["required_exposures"] = n_required
        self.last_calculated["exposures_ok"] = exposures_ok
        self.last_calculated["base_multiplier"] = base_multiplier
        if tech == "digital":
            self.last_calculated["required_snr"] = target_snr_val
            self.last_calculated["sfd_comp_target"] = sfd_comp_target
        else:
            self.last_calculated["required_density"] = required_density

        # Update warnings label
        if warnings:
            self.txt_warnings.setText("\n".join(warnings))
        else:
            self.txt_warnings.setText("No active warnings.")

        # Update dynamic standard figure text
        if hasattr(self, 'lbl_dynamic_standard_ref') and hasattr(self, 'cmb_std_figure'):
            self.lbl_dynamic_standard_ref.setText(f"{self.trans.get('standard_fig')} {self.cmb_std_figure.currentText()}")

        # Update weld sketch canvas
        safety_r = r_controlled if source != "x_ray" else None
        if tech == "digital":
            panel_w, panel_h, overlap_pct, _ = self.get_panel_inputs()
            self.canvas.draw_setup(od, t, cap, geometry, sfd, self.trans, self.is_dark_theme,
                                   panel_width=panel_w, panel_height=panel_h,
                                   overlap_pct=overlap_pct, n_panel=n_panel,
                                   safety_radius_m=safety_r)
        else:
            self.canvas.draw_setup(od, t, cap, geometry, sfd, self.trans, self.is_dark_theme,
                                   safety_radius_m=safety_r)

        # Automatically check compliance
        self.check_procedure_compliance()

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
        # 1. Gather inputs
        try:
            applied_kv = float(self.txt_app_kv.text().replace(",", "."))
        except ValueError:
            applied_kv = 0.0
            
        try:
            raw_act = float(self.txt_app_activity.text().replace(",", "."))
            unit = self.cmb_activity_unit.currentText() if hasattr(self, 'cmb_activity_unit') else "Ci"
            applied_activity = raw_act / 37.0 if unit == "GBq" else raw_act
        except ValueError:
            applied_activity = 0.0

        try:
            applied_sfd = float(self.txt_app_sfd.text().replace(",", "."))
        except ValueError:
            applied_sfd = 0.0

        try:
            applied_time = float(self.txt_app_time.text().replace(",", "."))
        except ValueError:
            applied_time = 0.0

        try:
            applied_quality = float(self.txt_app_quality.text().replace(",", "."))
        except ValueError:
            applied_quality = 0.0

        applied_wire = self.cmb_app_wire.currentData()
        applied_duplex = self.cmb_app_duplex.currentData()

        applied_film_class = self.cmb_film_class_used.currentText()

        try:
            applied_overlap = self._to_mm(float(self.txt_app_overlap.text().replace(",", ".")))
        except ValueError:
            applied_overlap = 0.0

        try:
            applied_srb = float(self.txt_app_srb.text().replace(",", "."))
        except ValueError:
            applied_srb = 0.0

        # Build dictionaries for checker
        tech = "digital" if self.rad_digital.isChecked() else "analog"
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60", "isotope_yb169", "isotope_tm170"]
        source = source_keys[self.cmb_source.currentIndex()]
        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"
        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]
        film_side = not self.chk_source_side_iqi.isChecked()
        material_keys = ["steel", "aluminum", "titanium", "copper_nickel"]
        material = material_keys[self.cmb_material.currentIndex()]
        t_wall = self.get_form_values()[1]

        inputs = {
            "tech": tech,
            "source": source,
            "class": testing_class,
            "geometry": geometry,
            "film_side": film_side,
            "iqi_type": self.cmb_iqi_type.currentData(),
            "snr_location": self.cmb_snr_location.currentData(),
            "material": material,
            "t": t_wall
        }

        # If self.last_calculated is empty, run update_calculations first
        if not self.last_calculated:
            self.update_calculations()

        applied = {
            "applied_kv": applied_kv,
            "applied_activity": applied_activity,
            "applied_sfd": applied_sfd,
            "applied_time": applied_time,
            "applied_wire": applied_wire,
            "applied_duplex": applied_duplex,
            "applied_quality": applied_quality,
            "applied_srb": applied_srb,
            "applied_film_class": applied_film_class,
            "applied_overlap": applied_overlap,
            "applied_exposures": self.get_applied_exposures()
        }

        # Call procedure checker
        res = self.proc_checker.check_compliance(
            inputs, self.last_calculated, applied, self.lvl3_settings, self.trans.language
        )

        # 2. Update UI
        is_compliant = res["is_compliant"]
        if is_compliant:
            self.lbl_compliance_result.setText(self.trans.get("compliant"))
            self.lbl_compliance_result.setStyleSheet("color: #a6e3a1; font-weight: bold; background-color: #2e7d32; padding: 6px; border-radius: 4px;")
        else:
            self.lbl_compliance_result.setText(self.trans.get("non_compliant"))
            self.lbl_compliance_result.setStyleSheet("color: #f38ba8; font-weight: bold; background-color: #c62828; padding: 6px; border-radius: 4px;")

        # Render list of checks in details area
        details_lines = []
        for chk in res["checks"]:
            symbol = "✓" if chk["status"] else "✗"
            color_style = "color: #a6e3a1;" if chk["status"] else "color: #f38ba8;"
            details_lines.append(f"<span style='{color_style}'>{symbol} {chk['details']}</span>")

        # Source Activity Check for isotopes
        if source != "x_ray":
            calc_activity = self.get_form_values()[6] # output_val entered in inputs
            diff_act = abs(applied_activity - calc_activity) / max(0.1, calc_activity)
            if diff_act > 0.15:
                symbol = "⚠"
                color_style = "color: #f9e2af;" # yellow warning
                if self.trans.language == "tr":
                    details_act = f"KAYNAK AKTİVİTE UYARISI: Hesaplama girdisi {calc_activity:.1f} Ci iken uygulanan {applied_activity:.1f} Ci'dir (%{diff_act*100:.0f} fark). Bu durum poz süresini etkiler."
                else:
                    details_act = f"SOURCE ACTIVITY WARNING: Calculation base is {calc_activity:.1f} Ci but applied is {applied_activity:.1f} Ci ({diff_act*100:.0f}% diff). This affects exposure time."
                details_lines.append(f"<span style='{color_style}'>{symbol} {details_act}</span>")

        self.lbl_compliance_details.setText("<br>".join(details_lines))

    def export_pdf_report(self):
        # 1. Ask where to save
        file_filter = "PDF Files (*.pdf)"
        now_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"RT_Inspection_Report_{now_date}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Report", filename, file_filter)
        
        if not filepath:
            return

        # 2. Gather values for report
        od, t, cap, weld_width, d, sfd, output_val, base_e, detector_type, film_class_used, _chart_source = self.get_form_values()
        material_keys = ["steel", "aluminum", "titanium", "copper_nickel"]
        material = material_keys[self.cmb_material.currentIndex()]
        tech = "digital" if self.rad_digital.isChecked() else "analog"
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60", "isotope_yb169", "isotope_tm170"]
        source = source_keys[self.cmb_source.currentIndex()]
        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"
        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]

        # Mirror the DWDI -> DWSI forcing applied by update_calculations so the
        # report always describes the same technique as the screen.
        if od > 100.0 and geometry in ["dwdi_elliptic", "dwdi_super"]:
            geometry = "dwsi"

        standard = self.cmb_standard.currentData() if hasattr(self, "cmb_standard") else "iso"

        try:
            input_kv = float(self.txt_app_kv.text().replace(",", "."))
        except ValueError:
            input_kv = 120.0

        try:
            overlap = self._to_mm(float(self.txt_app_overlap.text().replace(",", ".")))
        except ValueError:
            overlap = 10.0

        inputs = {
            "material_text": self.trans.get(material),
            "class_text": self.trans.get(testing_class),
            "od": od,
            "t": t,
            "cap": cap,
            "weld_width": weld_width,
            "d": d,
            "sfd": sfd,
            "output_val": output_val,
            "base_e": base_e,
            "speed": film_class_used if tech == "analog" else detector_type,
            "tech": tech,
            "tech_text": self.trans.get("analog_film" if tech == "analog" else "digital_cr_dda"),
            "source": source,
            "source_text": self.trans.get(source),
            "geometry": geometry,
            "geometry_text": self.trans.get(geometry),
            "standard": standard,
            "report_info": self.get_report_info(),
            "input_kv": input_kv,
            "overlap": overlap,
            "iqi_type": self.cmb_iqi_type.currentData(),
            "snr_location": self.cmb_snr_location.currentData()
        }

        # Gather outputs — use the same shared geometry block as the screen
        # (Level 3 reductions and the DWSI physical floor included), so the PDF
        # can never disagree with the UI.
        w_nom, w_eff = self.calc.calculate_thicknesses(t, cap, geometry)
        u_max = self.calc.calculate_u_max(w_nom, material)
        geo = self._compute_geometry(od, t, d, sfd, geometry, testing_class,
                                     standard=standard, lvl3_settings=self.lvl3_settings)
        f_min_iso = geo["f_min_iso"]
        f_min_asme = geo["f_min_asme"]
        sfd_min = geo["sfd_min"]
        ug = geo["ug"]

        if geometry == "swsi":
            exposures = 1
        elif geometry == "dwdi_elliptic":
            exposures = self.calc.get_dwdi_elliptical_exposures(od, t)
        elif geometry == "dwdi_super":
            exposures = 3
        else:
            exposures = self.calc.calculate_dwsi_exposures(od, t, sfd, testing_class)
        exposures = self.last_calculated.get("exposures_graph", exposures)

        film_side = not self.chk_source_side_iqi.isChecked()
        iqi_type = self.cmb_iqi_type.currentData()
        if iqi_type == "step_hole":
            wire_str, _ = self.calc.get_step_hole_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=self.trans.language)
        else:
            wire_str, _ = self.calc.get_single_wire_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=self.trans.language)
            
        duplex_str, _ = self.calc.get_duplex_iqi(w_nom, testing_class, geometry, lang=self.trans.language)
        
        target_quality = self.out_labels["quality_target"][1].text()
        calc_time = self.out_labels["calc_time"][1].text()

        outputs = {
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max if source == "x_ray" else None,
            "f_min": f_min_iso,
            "f_min_asme": f_min_asme,
            "sfd_min": sfd_min,
            "ug": ug,
            "exposures": exposures,
            "exposures_panel": self.last_calculated.get("exposures_panel"),
            "exposures_applied": self.last_calculated.get("exposures_applied"),
            "exposures_check": self.last_calculated.get("exposures_ok"),
            "single_wire_iqi": wire_str,
            "duplex_iqi": duplex_str if tech == "digital" else "N/A",
            "asme_iqi": self.last_calculated.get("asme_iqi", "N/A"),
            "barrier_distance": self.last_calculated.get("barrier_distance", "N/A"),
            "quality_target": target_quality,
            "calc_time": calc_time,
            "base_multiplier": self.last_calculated.get("base_multiplier", 1.0),
            "detector_quality": self.out_labels["detector_quality"][1].text(),
            "filter_recommendation": self.out_labels["filter_recommendation"][1].text()
        }

        # Gather defect details if evaluated
        defect_eval = None
        defect_text = self.lbl_defect_result.text()
        if defect_text:
            defect_types = ["defect_ip", "defect_if", "defect_ic", "defect_porosity", "defect_crack", "defect_slag", "defect_undercut", "defect_burn_through"]
            defect_type = defect_types[self.cmb_defect_type.currentIndex()]
            
            try:
                def_len = float(self.txt_defect_length.text().replace(",", "."))
            except ValueError:
                def_len = 0.0
            
            try:
                def_width = float(self.txt_defect_width.text().replace(",", "."))
            except ValueError:
                def_width = 0.0
            
            try:
                def_accum = float(self.txt_defect_accum.text().replace(",", "."))
            except ValueError:
                def_accum = 0.0

            # evaluate again to get full details through the active standard
            is_accepted, reason = self.api_eval.evaluate(defect_type, t, def_len, def_width, def_accum, self.trans.language)
            defect_standard = self.cmb_defect_standard.currentData()
            approx = False
            if defect_standard == "iso5817":
                from src.core.iso5817 import ISO5817Evaluator
                is_accepted, reason = ISO5817Evaluator().evaluate(
                    defect_type, t, def_len, def_width, def_accum,
                    level=self.cmb_quality_level.currentText(), lang=self.trans.language
                )
                approx = True
            elif defect_standard == "b31_3":
                from src.core.asme_b31_3 import ASMEB31_3Evaluator
                is_accepted, reason = ASMEB31_3Evaluator().evaluate(
                    defect_type, t, def_len, def_width, def_accum,
                    service=self.cmb_b31_service.currentData(), lang=self.trans.language
                )
                approx = True
            elif defect_standard == "viii":
                from src.core.asme_viii import ASMEVIIIEvaluator
                is_accepted, reason = ASMEVIIIEvaluator().evaluate(
                    defect_type, t, def_len, def_width, def_accum,
                    mode=self.cmb_viii_mode.currentData(), lang=self.trans.language
                )
                approx = True
            if approx:
                reason = f"{reason}\n\n{self.trans.get('defect_approx_note')}"

            defect_eval = {
                "active": True,
                "type_text": self.trans.get(defect_type),
                "len": def_len,
                "width": def_width,
                "accum": def_accum,
                "status": is_accepted,
                "reason": reason
            }

        # Warnings list
        warnings_text = self.txt_warnings.text()
        warnings_list = warnings_text.split("\n") if warnings_text != "No active warnings." else []

        # Distance-compensation target SNR: reuse the value computed for the
        # screen (dynamic Table 3/4 base, 1.4x HAZ factor, final sfd_min).
        sfd_comp_val = self.last_calculated.get("sfd_comp_target")
        if sfd_comp_val is None and self.lvl3_settings.get("sfd_comp") and sfd < sfd_min:
            base_snr = self.last_calculated.get("required_snr")
            if base_snr is None:
                base_snr = 130.0 if testing_class == "class_b" else 70.0
            sfd_comp_val = base_snr * (sfd_min / max(10.0, sfd))

        lvl3_active = any(self.lvl3_settings.get(k) for k in (
            "sfd_comp", "voltage_override", "isotope_flex",
            "source_flex", "central_proj_reduction", "dw_reduction",
        ))

        # Save sketch images to temporary files for PDF embedding
        tmp_dynamic = None
        tmp_standard = None
        dynamic_img_path = None
        standard_img_path = None
        try:
            tmp_dynamic = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_dynamic.close()
            self.canvas.save_figure(tmp_dynamic.name)
            dynamic_img_path = tmp_dynamic.name
        except Exception:
            logger.exception("Failed to save dynamic sketch for PDF")
            dynamic_img_path = None

        try:
            tmp_standard = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_standard.close()
            self.std_canvas.save_figure(tmp_standard.name)
            standard_img_path = tmp_standard.name
        except Exception:
            logger.exception("Failed to save standard sketch for PDF")
            standard_img_path = None

        success = self.pdf_gen.generate_report(
            filepath, inputs, outputs, warnings_list, defect_eval, 
            lvl3_active,
            sfd_comp_val, self.trans,
            dynamic_img_path=dynamic_img_path,
            standard_img_path=standard_img_path
        )

        # Clean up temporary image files
        for p in [dynamic_img_path, standard_img_path]:
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    logger.exception("Failed to remove temp sketch file %s", p)

        if success:
            QMessageBox.information(self, self.trans.get("success"), self.trans.get("report_saved", filepath))
        else:
            QMessageBox.critical(self, self.trans.get("error"), "Could not save PDF report.")

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
        about_action = QAction(f"About Radiography v{CURRENT_VERSION}", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About Radiography",
            f"Radiographic Testing (RT) Exposure Calculator\n"
            f"Version: {CURRENT_VERSION}\n"
            f"ISO 17636 / API 1104 Compliant\n\n"
            f"{self.trans.get('app_owner')}\n\n"
            f"{self.trans.get('disclaimer')}\n\n"
            f"{self.trans.get('contact_title')}:\n"
            f"{self.trans.get('contact_github')}\n"
            f"{self.trans.get('contact_email')}",
        )

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
                reply = QMessageBox.question(
                    self, "Update Available",
                    f"A new version ({version}) is available.\n\n"
                    f"{notes}\n\n"
                    f"Download and install now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._download_and_install(result)
            elif result.get("error"):
                if not silent:
                    QMessageBox.warning(self, "Update Check Failed",
                                        f"Could not check for updates:\n{result['error']}")
            else:
                if not silent:
                    QMessageBox.information(self, "No Updates",
                                            f"You are running the latest version ({CURRENT_VERSION}).")
        except Exception:
            logger.exception("Update check result handling failed")

    def _download_and_install(self, release_data):
        checker = UpdateChecker()
        url = checker.get_download_url(release_data)
        if not url:
            QMessageBox.warning(self, "Download Error",
                                "No compatible download found for your platform.")
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
                        progress_callback=lambda pct: self.progress.emit(int(pct * 100))
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
                    margin-top: 12px;
                    padding-top: 12px;
                    color: #fab387;
                    font-weight: bold;
                    font-size: 12px;
                    background-color: #181825;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 3px;
                    left: 10px;
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
                    margin-top: 12px;
                    padding-top: 12px;
                    color: #0d47a1;
                    font-weight: bold;
                    font-size: 12px;
                    background-color: #fafafa;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 3px;
                    left: 10px;
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
