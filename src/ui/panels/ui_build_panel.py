# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QScrollArea, QSplitter, QTabWidget,
                             QVBoxLayout, QWidget)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QDoubleValidator, QIntValidator

from src.ui.panels.input_panel import QFormLayout_custom
from src.ui.sketch import WeldSketchCanvas, StandardSchematicCanvas


class UIBuildMixin:
    """Mixin that builds the full widget tree (self.init_ui)."""

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

        self.grp_inputs = QGroupBox(self.trans.get("inputs_section"))
        grp_inputs = self.grp_inputs
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
        self._activity_unit = "Ci"  # tracks the currently displayed unit
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
        self.lbl_chart_source = QLabel(self.trans.get("chart_source"))
        self.cmb_chart_source = QComboBox()
        self.cmb_chart_source.addItem(self.trans.get("chart_model"), "model")
        self.cmb_chart_source.addItem("AA400 (C5)", "AA400")
        self.cmb_chart_source.addItem("MX125 (C3)", "MX125")
        self.cmb_chart_source.addItem("T200 (C4)", "T200")
        self.cmb_chart_source.addItem("HS800 (C6)", "HS800")
        self.cmb_chart_source.addItem("M100 (C2)", "M100")
        self.cmb_chart_source.addItem(self.trans.get("chart_type_x"), "type_x")
        self.cmb_chart_source.currentIndexChanged.connect(self.on_chart_source_changed)
        grp_exposure_layout.addRow(self.lbl_chart_source, self.cmb_chart_source)

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
        self.cmb_detector_type.currentIndexChanged.connect(self.on_detector_model_changed)
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
        for d in range(1, 15):
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

        self.grp_outputs = QGroupBox(self.trans.get("outputs"))
        grp_outputs = self.grp_outputs
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
            "asme_iqi", "quality_target", "calc_time", "total_joint_time", "detector_quality",
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
            info_btn.clicked.connect(lambda _, n=name: self._show_output_info(n))
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

