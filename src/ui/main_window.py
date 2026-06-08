# -*- coding: utf-8 -*-

import os
import tempfile
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QComboBox, QLineEdit, QRadioButton, QButtonGroup, 
                             QCheckBox, QPushButton, QGroupBox, QScrollArea, QFileDialog, 
                             QMessageBox, QFormLayout, QTabWidget, QDialog, QProgressDialog,
                             QMenuBar, QSplitter)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QDoubleValidator, QAction

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
ASME_B36_10_PIPES = {
    # NPS: (OD_mm, [(wall_thickness_mm, "SCHEDULE_LABEL"), ...]) based on ASME B36.10
    "1/8\" (NPS 1/8)": (10.3, [(1.24, "SCH 10"), (1.45, "SCH 30"), (1.73, "SCH 40 / STD"), (2.41, "SCH 80 / XS")]),
    "1/4\" (NPS 1/4)": (13.7, [(1.65, "SCH 10"), (1.85, "SCH 30"), (2.24, "SCH 40 / STD"), (3.02, "SCH 80 / XS")]),
    "3/8\" (NPS 3/8)": (17.1, [(1.65, "SCH 10"), (1.85, "SCH 30"), (2.31, "SCH 40 / STD"), (3.20, "SCH 80 / XS")]),
    "1/2\" (NPS 1/2)": (21.3, [(1.65, "SCH 5S"), (2.11, "SCH 10"), (2.41, "SCH 30"), (2.77, "SCH 40 / STD"), (3.73, "SCH 80 / XS"), (4.78, "SCH 160"), (7.47, "XXS")]),
    "3/4\" (NPS 3/4)": (26.7, [(1.65, "SCH 5S"), (2.11, "SCH 10"), (2.41, "SCH 30"), (2.87, "SCH 40 / STD"), (3.91, "SCH 80 / XS"), (5.56, "SCH 160"), (7.82, "XXS")]),
    "1\" (NPS 1)": (33.4, [(1.65, "SCH 5S"), (2.77, "SCH 10"), (2.90, "SCH 30"), (3.38, "SCH 40 / STD"), (4.55, "SCH 80 / XS"), (6.35, "SCH 160"), (9.09, "XXS")]),
    "1 1/4\" (NPS 1 1/4)": (42.2, [(1.65, "SCH 5S"), (2.77, "SCH 10"), (2.97, "SCH 30"), (3.56, "SCH 40 / STD"), (4.85, "SCH 80 / XS"), (6.35, "SCH 160"), (9.70, "XXS")]),
    "1 1/2\" (NPS 1 1/2)": (48.3, [(1.65, "SCH 5S"), (2.77, "SCH 10"), (3.18, "SCH 30"), (3.68, "SCH 40 / STD"), (5.08, "SCH 80 / XS"), (7.14, "SCH 160"), (10.15, "XXS")]),
    "2\" (NPS 2)": (60.3, [(1.65, "SCH 5S"), (2.77, "SCH 10"), (3.18, "SCH 30"), (3.91, "SCH 40 / STD"), (5.54, "SCH 80 / XS"), (8.74, "SCH 160"), (11.07, "XXS")]),
    "2 1/2\" (NPS 2 1/2)": (73.0, [(2.11, "SCH 5S"), (3.05, "SCH 10"), (4.78, "SCH 30"), (5.16, "SCH 40 / STD"), (7.01, "SCH 80 / XS"), (9.53, "SCH 160"), (14.02, "XXS")]),
    "3\" (NPS 3)": (88.9, [(2.11, "SCH 5S"), (3.05, "SCH 10"), (4.78, "SCH 30"), (5.49, "SCH 40 / STD"), (7.62, "SCH 80 / XS"), (11.13, "SCH 160"), (15.24, "XXS")]),
    "3 1/2\" (NPS 3 1/2)": (101.6, [(2.11, "SCH 5S"), (3.05, "SCH 10"), (4.78, "SCH 30"), (5.74, "SCH 40 / STD"), (8.08, "SCH 80 / XS")]),
    "4\" (NPS 4)": (114.3, [(2.11, "SCH 5S"), (3.05, "SCH 10"), (4.78, "SCH 30"), (6.02, "SCH 40 / STD"), (8.56, "SCH 80 / XS"), (11.13, "SCH 120"), (13.49, "SCH 160"), (17.12, "XXS")]),
    "5\" (NPS 5)": (141.3, [(2.77, "SCH 5S"), (3.40, "SCH 10"), (6.55, "SCH 40 / STD"), (9.53, "SCH 80 / XS"), (12.70, "SCH 120"), (15.88, "SCH 160"), (19.05, "XXS")]),
    "6\" (NPS 6)": (168.3, [(2.77, "SCH 5S"), (3.40, "SCH 10"), (7.11, "SCH 40 / STD"), (10.97, "SCH 80 / XS"), (14.27, "SCH 120"), (18.26, "SCH 160"), (21.95, "XXS")]),
    "8\" (NPS 8)": (219.1, [(2.77, "SCH 5S"), (3.76, "SCH 10"), (6.35, "SCH 20"), (7.04, "SCH 30"), (8.18, "SCH 40 / STD"), (10.31, "SCH 60"), (12.70, "SCH 80 / XS"), (15.09, "SCH 100"), (18.26, "SCH 120"), (20.62, "SCH 140"), (22.23, "XXS"), (23.01, "SCH 160")]),
    "10\" (NPS 10)": (273.0, [(3.40, "SCH 5S"), (4.19, "SCH 10"), (6.35, "SCH 20"), (7.80, "SCH 30"), (9.27, "SCH 40 / STD"), (12.70, "SCH 60 / XS"), (15.09, "SCH 80"), (18.26, "SCH 100"), (21.44, "SCH 120"), (25.40, "SCH 140 / XXS"), (28.58, "SCH 160")]),
    "12\" (NPS 12)": (323.9, [(3.96, "SCH 5S"), (4.57, "SCH 10"), (6.35, "SCH 20"), (8.38, "SCH 30"), (9.53, "STD"), (10.31, "SCH 40"), (12.70, "XS"), (14.27, "SCH 60"), (17.48, "SCH 80"), (21.44, "SCH 100"), (25.40, "SCH 120 / XXS"), (28.58, "SCH 140"), (33.32, "SCH 160")]),
    "14\" (NPS 14)": (355.6, [(6.35, "SCH 10"), (7.92, "SCH 20"), (9.53, "SCH 30 / STD"), (11.13, "SCH 40"), (12.70, "XS"), (15.09, "SCH 60"), (19.05, "SCH 80"), (23.83, "SCH 100"), (27.79, "SCH 120"), (31.75, "SCH 140"), (35.71, "SCH 160")]),
    "16\" (NPS 16)": (406.4, [(6.35, "SCH 10"), (7.92, "SCH 20"), (9.53, "SCH 30 / STD"), (12.70, "SCH 40 / XS"), (16.66, "SCH 60"), (21.44, "SCH 80"), (26.19, "SCH 100"), (30.96, "SCH 120"), (36.53, "SCH 140"), (40.49, "SCH 160")]),
    "18\" (NPS 18)": (457.0, [(6.35, "SCH 10"), (7.92, "SCH 20"), (9.53, "STD"), (11.13, "SCH 30"), (12.70, "XS"), (14.27, "SCH 40"), (19.05, "SCH 60"), (23.83, "SCH 80"), (29.36, "SCH 100"), (34.93, "SCH 120"), (39.67, "SCH 140"), (45.24, "SCH 160")]),
    "20\" (NPS 20)": (508.0, [(6.35, "SCH 10"), (9.53, "SCH 20 / STD"), (12.70, "SCH 30 / XS"), (15.09, "SCH 40"), (20.62, "SCH 60"), (26.19, "SCH 80"), (32.54, "SCH 100"), (38.10, "SCH 120"), (44.45, "SCH 140"), (50.01, "SCH 160")]),
    "22\" (NPS 22)": (559.0, [(6.35, "SCH 10"), (9.53, "SCH 20 / STD"), (12.70, "SCH 30 / XS"), (22.23, "SCH 60"), (28.56, "SCH 80"), (34.93, "SCH 100"), (41.28, "SCH 120"), (47.63, "SCH 140"), (53.98, "SCH 160")]),
    "24\" (NPS 24)": (610.0, [(6.35, "SCH 10"), (9.53, "SCH 20 / STD"), (12.70, "XS"), (14.27, "SCH 30"), (17.48, "SCH 40"), (24.61, "SCH 60"), (30.96, "SCH 80"), (38.89, "SCH 100"), (46.02, "SCH 120"), (52.37, "SCH 140"), (59.54, "SCH 160")]),
    "26\" (NPS 26)": (660.0, [(7.92, "SCH 10"), (9.53, "STD"), (12.70, "XS / SCH 20")]),
    "28\" (NPS 28)": (711.0, [(7.92, "SCH 10"), (9.53, "STD"), (12.70, "XS / SCH 20"), (15.88, "SCH 30")]),
    "30\" (NPS 30)": (762.0, [(7.92, "SCH 10"), (9.53, "STD"), (12.70, "XS / SCH 20"), (15.88, "SCH 30")]),
    "32\" (NPS 32)": (813.0, [(7.92, "SCH 10"), (9.53, "STD"), (12.70, "XS / SCH 20"), (15.88, "SCH 30"), (17.48, "SCH 40")]),
    "34\" (NPS 34)": (864.0, [(7.92, "SCH 10"), (9.53, "STD"), (12.70, "XS / SCH 20"), (15.88, "SCH 30"), (17.48, "SCH 40")]),
    "36\" (NPS 36)": (914.0, [(7.92, "SCH 10"), (9.53, "STD"), (12.70, "XS / SCH 20"), (15.88, "SCH 30"), (19.05, "SCH 40")]),
    "38\" (NPS 38)": (965.0, [(9.53, "STD"), (12.70, "XS")]),
    "40\" (NPS 40)": (1016.0, [(9.53, "STD"), (12.70, "XS")]),
    "42\" (NPS 42)": (1067.0, [(9.53, "STD"), (12.70, "XS")]),
    "44\" (NPS 44)": (1118.0, [(9.53, "STD"), (12.70, "XS")]),
    "46\" (NPS 46)": (1168.0, [(9.53, "STD"), (12.70, "XS")]),
    "48\" (NPS 48)": (1219.0, [(9.53, "STD"), (12.70, "XS")]),
    "52\" (NPS 52)": (1321.0, [(9.53, "STD"), (12.70, "XS")]),
    "56\" (NPS 56)": (1422.0, [(9.53, "STD"), (12.70, "XS")]),
    "60\" (NPS 60)": (1524.0, [(9.53, "STD"), (12.70, "XS")])
}

class QFormLayout_custom(QFormLayout):
    def __init__(self):
        super().__init__()
        self.setContentsMargins(10, 5, 10, 10)
        self.setSpacing(8)
        self.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

class MainWindow(QMainWindow):
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
        self.lvl3_settings = {
            "sfd_comp": False,
            "voltage_override": False,
            "isotope_flex": False,
            "source_flex": False,
            "central_proj_reduction": False,
            "dw_reduction": False,
            "approval_note": ""
        }

        # Set Window Title and size
        self.setWindowTitle(self.trans.get("app_title"))
        self.setMinimumSize(1200, 800)
        
        # Init layout
        self.init_ui()
        self._setup_menu_bar()
        self.apply_theme()
        
        # Initialize standard figure list
        self.update_std_figure_list()
        
        # Start with flat detector (hide bed/bgap)
        self.txt_bed.setVisible(False)
        self.txt_bgap.setVisible(False)

        # Trigger initial calculations
        self.update_calculations()

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
        top_bar.addWidget(self.btn_lvl3)
        top_bar.addWidget(self.btn_export)
        main_layout.addLayout(top_bar)

        # --- LEFT PANEL: Inputs (split into resizable sections) ---
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)

        # Group 1: Shooting Parameters and Inputs (wrapped in scroll area)
        self.left_scroll_1 = QScrollArea()
        self.left_scroll_1.setWidgetResizable(True)
        self.left_scroll_1.setMinimumHeight(150)
        scroll_widget_1 = QWidget()
        scroll_layout_1 = QVBoxLayout(scroll_widget_1)
        scroll_layout_1.setContentsMargins(5, 5, 5, 5)
        scroll_layout_1.setSpacing(0)

        grp_inputs = QGroupBox(self.trans.get("inputs_section"))
        grp_inputs_layout = QFormLayout_custom()
        grp_inputs.setLayout(grp_inputs_layout)

        self.cmb_material = QComboBox()
        self.cmb_material.addItems([
            self.trans.get("steel"),
            self.trans.get("aluminum"),
            self.trans.get("titanium"),
            self.trans.get("copper_nickel")
        ])
        self.cmb_material.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("material_type"), self.cmb_material)

        self.lbl_std_od = QLabel(self.trans.get("std_pipe_od"))
        self.cmb_od = QComboBox()
        self.cmb_od.blockSignals(True)
        for key in ASME_B36_10_PIPES.keys():
            self.cmb_od.addItem(key, key)
        self.cmb_od.currentIndexChanged.connect(self.on_od_changed)
        grp_inputs_layout.addRow(self.lbl_std_od, self.cmb_od)

        self.lbl_custom_od = QLabel(self.trans.get("custom_pipe_od"))
        self.txt_custom_od = QLineEdit()
        self.txt_custom_od.setValidator(QDoubleValidator(1.0, 5000.0, 2))
        self.txt_custom_od.setPlaceholderText(self.trans.get("custom_od_placeholder"))
        self.txt_custom_od.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_custom_od, self.txt_custom_od)

        self.lbl_std_t = QLabel(self.trans.get("std_nominal_t"))
        self.cmb_t = QComboBox()
        self.cmb_t.blockSignals(True)
        self.cmb_t.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_std_t, self.cmb_t)

        self.lbl_custom_t = QLabel(self.trans.get("custom_nominal_t"))
        self.txt_custom_t = QLineEdit()
        self.txt_custom_t.setValidator(QDoubleValidator(0.1, 500.0, 2))
        self.txt_custom_t.setPlaceholderText(self.trans.get("custom_t_placeholder"))
        self.txt_custom_t.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_custom_t, self.txt_custom_t)

        self.txt_cap = QLineEdit("3.0")
        self.txt_cap.setValidator(QDoubleValidator(0.0, 50.0, 2))
        self.txt_cap.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("cap_height"), self.txt_cap)

        self.bg_tech = QButtonGroup(self)
        self.rad_analog = QRadioButton(self.trans.get("analog_film"))
        self.rad_digital = QRadioButton(self.trans.get("digital_cr_dda"))
        self.rad_digital.setChecked(True)
        self.bg_tech.addButton(self.rad_analog, 0)
        self.bg_tech.addButton(self.rad_digital, 1)
        self.rad_analog.toggled.connect(self.on_tech_changed)
        self.rad_digital.toggled.connect(self.on_tech_changed)
        
        tech_widget = QWidget()
        tech_layout = QVBoxLayout(tech_widget)
        tech_layout.setContentsMargins(0,0,0,0)
        tech_layout.addWidget(self.rad_analog)
        tech_layout.addWidget(self.rad_digital)
        grp_inputs_layout.addRow(self.trans.get("rt_tech"), tech_widget)

        self.cmb_source = QComboBox()
        self.cmb_source.addItems([
            self.trans.get("x_ray"),
            self.trans.get("isotope_ir192"),
            self.trans.get("isotope_se75"),
            self.trans.get("isotope_co60")
        ])
        self.cmb_source.currentIndexChanged.connect(self.on_source_changed)
        grp_inputs_layout.addRow(self.trans.get("rad_source"), self.cmb_source)

        self.txt_d = QLineEdit("2.0")
        self.txt_d.setValidator(QDoubleValidator(0.01, 20.0, 2))
        self.txt_d.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("focal_size"), self.txt_d)

        self.txt_dd = QLineEdit("200.0")
        self.txt_dd.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.txt_dd.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("detector_size"), self.txt_dd)

        self.cmb_class = QComboBox()
        self.cmb_class.addItems([
            self.trans.get("class_b"),
            self.trans.get("class_a")
        ])
        self.cmb_class.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("testing_class"), self.cmb_class)

        self.cmb_geometry = QComboBox()
        self.cmb_geometry.addItems([
            self.trans.get("dwsi"),
            self.trans.get("swsi"),
            self.trans.get("dwdi_elliptic"),
            self.trans.get("dwdi_super")
        ])
        self.cmb_geometry.currentIndexChanged.connect(self.on_geometry_changed)
        grp_inputs_layout.addRow(self.trans.get("geometry"), self.cmb_geometry)

        self.cmb_std_figure = QComboBox()
        self.cmb_std_figure.currentIndexChanged.connect(self.on_std_figure_changed)
        grp_inputs_layout.addRow(self.trans.get("standard_fig"), self.cmb_std_figure)

        self.rad_detector_flat = QRadioButton(self.trans.get("detector_flat"))
        self.rad_detector_curved = QRadioButton(self.trans.get("detector_curved"))
        self.rad_detector_flat.setChecked(True)
        det_type_widget = QWidget()
        det_type_layout = QHBoxLayout(det_type_widget)
        det_type_layout.setContentsMargins(0, 0, 0, 0)
        det_type_layout.addWidget(self.rad_detector_flat)
        det_type_layout.addWidget(self.rad_detector_curved)
        self.rad_detector_flat.toggled.connect(self.on_detector_type_changed)
        self.rad_detector_curved.toggled.connect(self.on_detector_type_changed)
        grp_inputs_layout.addRow(self.trans.get("detector_type"), det_type_widget)

        self.txt_bed = QLineEdit("0.0")
        self.txt_bed.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_bed.textChanged.connect(self.update_calculations)
        self.lbl_bed = grp_inputs_layout.addRow(self.trans.get("bed"), self.txt_bed)

        self.txt_bgap = QLineEdit("5.0")
        self.txt_bgap.setValidator(QDoubleValidator(0.0, 100.0, 1))
        self.txt_bgap.textChanged.connect(self.update_calculations)
        self.lbl_bgap = grp_inputs_layout.addRow(self.trans.get("bgap"), self.txt_bgap)

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

        # Group 2: Applied Exposure and Geometry Settings (wrapped in scroll area)
        self.left_scroll_2 = QScrollArea()
        self.left_scroll_2.setWidgetResizable(True)
        self.left_scroll_2.setMinimumHeight(150)
        scroll_widget_2 = QWidget()
        scroll_layout_2 = QVBoxLayout(scroll_widget_2)
        scroll_layout_2.setContentsMargins(5, 5, 5, 5)
        scroll_layout_2.setSpacing(0)

        self.grp_exposure = QGroupBox(self.trans.get("applied_exposure_section"))
        grp_exposure_layout = QFormLayout_custom()
        self.grp_exposure.setLayout(grp_exposure_layout)

        # 1. Applied SFD
        self.lbl_app_sfd = QLabel(self.trans.get("applied_sfd"))
        self.txt_app_sfd = QLineEdit("600.0")
        self.txt_app_sfd.setValidator(QDoubleValidator(10.0, 5000.0, 1))
        self.txt_app_sfd.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_sfd, self.txt_app_sfd)

        # 2. Tube Amperage (mA) - visible for X-ray
        self.lbl_output = QLabel(self.trans.get("amperage"))
        self.txt_output = QLineEdit("5.0")
        self.txt_output.setValidator(QDoubleValidator(0.01, 1000.0, 2))
        self.txt_output.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_output, self.txt_output)

        # 3. Applied Tube Voltage (kV) - visible for X-ray
        self.lbl_app_kv = QLabel(self.trans.get("applied_kv"))
        self.txt_app_kv = QLineEdit("120.0")
        self.txt_app_kv.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.txt_app_kv.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_kv, self.txt_app_kv)

        # 4. Applied Activity (Ci) - visible for Isotopes
        self.lbl_app_activity = QLabel(self.trans.get("applied_activity"))
        self.txt_app_activity = QLineEdit("40.0")
        self.txt_app_activity.setValidator(QDoubleValidator(0.01, 1000.0, 2))
        self.txt_app_activity.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_activity, self.txt_app_activity)

        # 5. Base factor E
        self.txt_base_e = QLineEdit("3.0")
        self.txt_base_e.setValidator(QDoubleValidator(0.0001, 100.0, 4))
        self.txt_base_e.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.trans.get("base_factor"), self.txt_base_e)

        # 6. Chart Source (exposure chart database routing)
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

        # 7. Film class in use (analog only) — ISO 11699-1
        self.lbl_film_class_used = QLabel(self.trans.get("film_class_used"))
        self.cmb_film_class_used = QComboBox()
        self.cmb_film_class_used.addItems(["C1", "C2", "C3", "C4", "C5", "C6"])
        self.cmb_film_class_used.setCurrentIndex(4)   # default C5
        self.cmb_film_class_used.setMinimumWidth(100)
        self.cmb_film_class_used.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_film_class_used, self.cmb_film_class_used)

        # 7. Applied Film Overlap (mm) - visible for analog
        self.lbl_app_overlap = QLabel(self.trans.get("applied_overlap"))
        self.txt_app_overlap = QLineEdit("10.0")
        self.txt_app_overlap.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_app_overlap.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_overlap, self.txt_app_overlap)

        # 8. Detector type (digital only) — ISO 17636-2 / DQE
        self.lbl_detector_type = QLabel(self.trans.get("detector_type"))
        self.cmb_detector_type = QComboBox()
        self._det_keys = ["cr_standard", "cr_highres", "dda_si", "dda_se", "dda_gdos"]
        self._det_trans_keys = ["detector_cr_std", "detector_cr_hires",
                                "detector_dda_si", "detector_dda_se", "detector_dda_gdos"]
        for key, tkey in zip(self._det_keys, self._det_trans_keys):
            self.cmb_detector_type.addItem(self.trans.get(tkey), key)
        self.cmb_detector_type.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_detector_type, self.cmb_detector_type)

        # 9. Applied Panel SRb (µm) - visible for digital
        self.lbl_app_srb = QLabel(self.trans.get("applied_srb"))
        self.txt_app_srb = QLineEdit("80.0")
        self.txt_app_srb.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.txt_app_srb.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_srb, self.txt_app_srb)

        # SNR Measurement Location (visible for digital)
        self.lbl_snr_location = QLabel(self.trans.get("snr_location"))
        self.cmb_snr_location = QComboBox()
        self.cmb_snr_location.addItem(self.trans.get("snr_location_weld"), "weld")
        self.cmb_snr_location.addItem(self.trans.get("snr_location_adjacent"), "adjacent")
        self.cmb_snr_location.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_snr_location, self.cmb_snr_location)

        # 10. Applied Wire (W-No)
        self.lbl_app_wire = QLabel(self.trans.get("applied_wire"))
        self.cmb_app_wire = QComboBox()
        wire_dias = {
            1: 3.20, 2: 2.50, 3: 2.00, 4: 1.60, 5: 1.25,
            6: 1.00, 7: 0.80, 8: 0.63, 9: 0.50, 10: 0.40,
            11: 0.32, 12: 0.25, 13: 0.20, 14: 0.16, 15: 0.125,
            16: 0.10, 17: 0.08, 18: 0.063, 19: 0.05
        }
        for w_no in sorted(wire_dias.keys()):
            self.cmb_app_wire.addItem(f"W {w_no} ({wire_dias[w_no]:.3f} mm)", w_no)
        self.cmb_app_wire.setCurrentIndex(9) # default W10
        self.cmb_app_wire.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_wire, self.cmb_app_wire)

        # 11. Applied Duplex (D-No) - visible for digital
        self.lbl_app_duplex = QLabel(self.trans.get("applied_duplex"))
        self.cmb_app_duplex = QComboBox()
        duplex_dias = {
            5: 0.320, 6: 0.250, 7: 0.200, 8: 0.160, 9: 0.125,
            10: 0.100, 11: 0.080, 12: 0.063, 13: 0.050
        }
        for d_no in sorted(duplex_dias.keys()):
            self.cmb_app_duplex.addItem(f"D {d_no} ({duplex_dias[d_no]:.3f} mm)", d_no)
        self.cmb_app_duplex.setCurrentIndex(5) # default D10
        self.cmb_app_duplex.currentIndexChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_duplex, self.cmb_app_duplex)

        # 12. Applied Quality Target (OD / SNR_N)
        self.lbl_app_quality = QLabel(self.trans.get("applied_quality"))
        self.txt_app_quality = QLineEdit("2.5")
        self.txt_app_quality.setValidator(QDoubleValidator(0.01, 10000.0, 2))
        self.txt_app_quality.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_quality, self.txt_app_quality)

        # 13. Applied Exposure Time (sec)
        self.lbl_app_time = QLabel(self.trans.get("applied_time"))
        self.txt_app_time = QLineEdit("180.0")
        self.txt_app_time.setValidator(QDoubleValidator(0.1, 100000.0, 1))
        self.txt_app_time.textChanged.connect(self.update_calculations)
        grp_exposure_layout.addRow(self.lbl_app_time, self.txt_app_time)

        scroll_layout_2.addWidget(self.grp_exposure)
        self.left_scroll_2.setWidget(scroll_widget_2)

        # Assemble left panel vertical splitter
        self.left_splitter.addWidget(self.left_scroll_1)
        self.left_splitter.addWidget(self.left_scroll_2)
        self.left_splitter.setSizes([400, 400])

        # Top Right: Weld Sketch Tabbed View inside Box
        self.sketch_box = QGroupBox(self.trans.get("sketch_title"))
        self.sketch_box.setObjectName("SketchBox")
        sketch_layout = QVBoxLayout(self.sketch_box)
        sketch_layout.setContentsMargins(5,5,5,5)

        self.tab_sketch = QTabWidget()
        self.tab_sketch.setObjectName("SketchTabs")
        
        # Tab 1: Dynamic Sketch Canvas
        tab_dynamic_widget = QWidget()
        tab_dynamic_layout = QVBoxLayout(tab_dynamic_widget)
        tab_dynamic_layout.setContentsMargins(2,2,2,2)
        self.canvas = WeldSketchCanvas(tab_dynamic_widget, width=5, height=3, dpi=100)
        tab_dynamic_layout.addWidget(self.canvas)
        
        # Under the dynamic canvas, show which standard figure corresponds to the setup
        self.lbl_dynamic_standard_ref = QLabel("")
        self.lbl_dynamic_standard_ref.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dynamic_standard_ref.setStyleSheet("color: #89b4fa; font-size: 11px; font-weight: bold; padding: 4px;")
        tab_dynamic_layout.addWidget(self.lbl_dynamic_standard_ref)
        
        self.tab_sketch.addTab(tab_dynamic_widget, self.trans.get("tab_dynamic"))

        # Tab 2: Standard Schematic
        tab_std_widget = QWidget()
        tab_std_layout = QVBoxLayout(tab_std_widget)
        tab_std_layout.setContentsMargins(2,2,2,2)
        self.std_canvas = StandardSchematicCanvas(tab_std_widget, width=5, height=3, dpi=100)
        tab_std_layout.addWidget(self.std_canvas)
        self.tab_sketch.addTab(tab_std_widget, self.trans.get("tab_standard"))

        sketch_layout.addWidget(self.tab_sketch)

        # Vertical Splitter: sketch (top) | bottom section (bottom)
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setChildrenCollapsible(False)

        # Horizontal Splitter: outputs (left) | warnings/defects (right)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setChildrenCollapsible(False)

        right_splitter.addWidget(self.sketch_box)
        right_splitter.addWidget(bottom_splitter)
        right_splitter.setSizes([300, 400])

        # Middle splitter: left inputs panel | right panel
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)
        middle_splitter.addWidget(self.left_splitter)
        middle_splitter.addWidget(right_splitter)
        middle_splitter.setSizes([400, 800])
        middle_splitter.setChildrenCollapsible(False)
        main_layout.addWidget(middle_splitter)

        # Bottom Left: Outputs
        grp_outputs = QGroupBox(self.trans.get("outputs"))
        grp_outputs.setObjectName("OutputsBox")
        grp_outputs_layout = QGridLayout(grp_outputs)
        grp_outputs.setLayout(grp_outputs_layout)

        # Labels & values for calculations
        self.out_labels = {}
        self.info_buttons = {}
        out_fields = [
            ("w_nom", 0, 0), ("w_eff", 1, 0), ("u_max", 2, 0), ("f_min", 3, 0), ("sfd_min", 4, 0),
            ("ug", 5, 0),
            ("req_exposures", 0, 2), ("single_wire_iqi", 1, 2), ("duplex_iqi", 2, 2),
            ("quality_target", 3, 2), ("calc_time", 4, 2), ("detector_quality", 5, 2),
            ("filter_recommendation", 6, 0)
        ]

        # For quality_target, it dynamically holds Optical Density (analog) or SNR_N (digital)
        # For calc_time, it holds the exposure time.

        for name, r, c in out_fields:
            # Create a widget to group label and info button
            lbl_widget = QWidget()
            lbl_layout = QHBoxLayout(lbl_widget)
            lbl_layout.setContentsMargins(0, 0, 0, 0)
            lbl_layout.setSpacing(4)

            lbl = QLabel(self.trans.get(name))
            lbl_layout.addWidget(lbl)

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
            lbl_layout.addWidget(info_btn)
            self.info_buttons[name] = info_btn

            val = QLabel("-")
            val.setObjectName("OutputValue")
            val.setFont(QFont("Helvetica", 10, QFont.Weight.Bold))
            val.setStyleSheet("color: #a6e3a1;") # light green
            
            grp_outputs_layout.addWidget(lbl_widget, r, c)
            grp_outputs_layout.addWidget(val, r, c+1)
            self.out_labels[name] = (lbl, val)

        bottom_splitter.addWidget(grp_outputs)

        # Bottom Right: Warnings and API 1104 Defect Module
        right_sub_container = QWidget()
        right_sub_layout = QVBoxLayout(right_sub_container)
        right_sub_layout.setContentsMargins(0, 0, 0, 0)
        right_sub_layout.setSpacing(10)
        bottom_splitter.addWidget(right_sub_container)
        bottom_splitter.setSizes([400, 400])

        # Warnings Panel
        self.grp_warnings = QGroupBox(self.trans.get("warnings"))
        self.grp_warnings.setObjectName("WarningsBox")
        warnings_layout = QVBoxLayout(self.grp_warnings)
        self.txt_warnings = QLabel("")
        self.txt_warnings.setWordWrap(True)
        self.txt_warnings.setStyleSheet("color: #f38ba8; font-size: 10px; font-weight: bold;")
        warnings_layout.addWidget(self.txt_warnings)
        # Right sub-panel: vertical splitter for warnings, compliance, defects
        right_sub_splitter = QSplitter(Qt.Orientation.Vertical)
        right_sub_splitter.setChildrenCollapsible(False)
        right_sub_splitter.addWidget(self.grp_warnings)
        right_sub_splitter.addWidget(self.grp_compliance)
        right_sub_splitter.addWidget(self.tab_extra)
        right_sub_splitter.setSizes([150, 200, 200])
        right_sub_layout.addWidget(right_sub_splitter)

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

        # Auto-check for updates on startup (silent)
        QTimer.singleShot(2000, lambda: self.check_for_updates(silent=True))

    def on_detector_type_changed(self):
        is_curved = self.rad_detector_curved.isChecked()
        self.txt_bed.setVisible(is_curved)
        self.txt_bgap.setVisible(is_curved)
        self.update_calculations()

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
        
        # update target label name
        target_name = "target_snr" if is_digital else "optical_density"
        self.out_labels["quality_target"][0].setText(self.trans.get(target_name))
        
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

        self.update_calculations()

    def on_source_changed(self):
        source_idx = self.cmb_source.currentIndex()
        if source_idx == 0:  # X-Ray
            self.lbl_output.setText(self.trans.get("amperage"))
            if not self.txt_output.text():
                self.txt_output.setText("5.0")
            self.txt_base_e.setText("3.0")
            
            # Show Tube Amperage & Voltage, Hide Activity
            self.lbl_output.setVisible(True)
            self.txt_output.setVisible(True)
            self.lbl_app_kv.setVisible(True)
            self.txt_app_kv.setVisible(True)
            self.lbl_app_activity.setVisible(False)
            self.txt_app_activity.setVisible(False)
        else: # Isotopes
            # Hide Amperage & Voltage, Show Activity
            self.lbl_output.setVisible(False)
            self.txt_output.setVisible(False)
            self.lbl_app_kv.setVisible(False)
            self.txt_app_kv.setVisible(False)
            self.lbl_app_activity.setVisible(True)
            self.txt_app_activity.setVisible(True)

            if not self.txt_app_activity.text():
                self.txt_app_activity.setText("40.0")

            # Set base factor default per isotope
            if source_idx == 1:   # Ir-192
                self.txt_base_e.setText("30.0")
            elif source_idx == 2:  # Se-75
                self.txt_base_e.setText("40.0")
            else:                  # Co-60
                self.txt_base_e.setText("20.0")

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

    def update_std_figure_list(self):
        # Prevent recursion by temporarily disconnecting the signal
        self.cmb_std_figure.blockSignals(True)
        
        # Get selected geometry
        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]
        
        # Save previous selection
        prev_data = self.cmb_std_figure.currentData()

        self.cmb_std_figure.clear()
        
        if geometry == "swsi":
            self.cmb_std_figure.addItem(self.trans.get("fig5_title"), "fig5")
            self.cmb_std_figure.addItem(self.trans.get("fig6_title"), "fig6")
            self.cmb_std_figure.addItem(self.trans.get("fig7_title"), "fig7")
        elif geometry in ["dwdi_elliptic", "dwdi_super"]:
            self.cmb_std_figure.addItem(self.trans.get("fig11_title"), "fig11")
            self.cmb_std_figure.addItem(self.trans.get("fig12_title"), "fig12")
        else: # dwsi
            self.cmb_std_figure.addItem(self.trans.get("fig13_title"), "fig13")
            
        # Try to restore previous selection
        found = False
        for i in range(self.cmb_std_figure.count()):
            if self.cmb_std_figure.itemData(i) == prev_data:
                self.cmb_std_figure.setCurrentIndex(i)
                found = True
                break
        if not found:
            self.cmb_std_figure.setCurrentIndex(0)
            
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
        self.cmb_material.addItems([
            self.trans.get("steel"),
            self.trans.get("aluminum"),
            self.trans.get("titanium"),
            self.trans.get("copper_nickel")
        ])
        self.cmb_material.setCurrentIndex(material_idx)

        source_idx = self.cmb_source.currentIndex()
        self.cmb_source.clear()
        self.cmb_source.addItems([
            self.trans.get("x_ray"),
            self.trans.get("isotope_ir192"),
            self.trans.get("isotope_se75"),
            self.trans.get("isotope_co60")
        ])
        self.cmb_source.setCurrentIndex(source_idx)

        class_idx = self.cmb_class.currentIndex()
        self.cmb_class.clear()
        self.cmb_class.addItems([
            self.trans.get("class_b"),
            self.trans.get("class_a")
        ])
        self.cmb_class.setCurrentIndex(class_idx)

        geom_idx = self.cmb_geometry.currentIndex()
        self.cmb_geometry.clear()
        self.cmb_geometry.addItems([
            self.trans.get("dwsi"),
            self.trans.get("swsi"),
            self.trans.get("dwdi_elliptic"),
            self.trans.get("dwdi_super")
        ])
        self.cmb_geometry.setCurrentIndex(geom_idx)

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
        self.grp_warnings.setTitle(self.trans.get("warnings"))
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
            else:
                lbl.setText(self.trans.get(name))
            
            # Update info button tooltip
            if name in self.info_buttons:
                self.info_buttons[name].setToolTip(self.trans.get("tt_" + name))

        # Re-translate defect evaluation UI
        defect_idx = self.cmb_defect_type.currentIndex()
        self.cmb_defect_type.clear()
        self.cmb_defect_type.addItems([
            self.trans.get("defect_ip"),
            self.trans.get("defect_if"),
            self.trans.get("defect_ic"),
            self.trans.get("defect_porosity"),
            self.trans.get("defect_crack")
        ])
        self.cmb_defect_type.setCurrentIndex(defect_idx)
        self.btn_eval_defect.setText(self.trans.get("evaluate_defect"))

        # Update tab titles
        self.tab_sketch.setTabText(0, self.trans.get("tab_dynamic"))
        self.tab_sketch.setTabText(1, self.trans.get("tab_standard"))

        self.tab_extra.setTabText(0, self.trans.get("defect_section"))

        # Update QGroupBox titles for exposure section
        self.grp_exposure.setTitle(self.trans.get("applied_exposure_section"))
        self.grp_compliance.setTitle(self.trans.get("procedure_section"))

        self.lbl_app_sfd.setText(self.trans.get("applied_sfd"))
        self.lbl_app_time.setText(self.trans.get("applied_time"))
        self.lbl_app_kv.setText(self.trans.get("applied_kv"))
        self.lbl_app_activity.setText(self.trans.get("applied_activity"))

        if self.cmb_iqi_type.currentData() == "step_hole":
            self.lbl_app_wire.setText(self.trans.get("applied_step_hole"))
        else:
            self.lbl_app_wire.setText(self.trans.get("applied_wire"))

        self.lbl_app_duplex.setText(self.trans.get("applied_duplex"))
        self.lbl_app_srb.setText(self.trans.get("applied_srb"))
        self.lbl_app_overlap.setText(self.trans.get("applied_overlap"))

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
            (self.txt_output, 0.01, 1000.0),
            (self.txt_app_time, 0.1, 100000.0),
            (self.txt_base_e, 0.0001, 100.0),
            (self.txt_app_overlap, 0.0, 500.0),
            (self.txt_app_srb, 1.0, 1000.0),
            (self.txt_app_quality, 0.01, 10000.0),
            (self.txt_dd, 1.0, 1000.0),
            (self.txt_bed, 0.0, 500.0),
            (self.txt_bgap, 0.0, 100.0),
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
        if custom_od_str:
            try:
                val = float(custom_od_str)
                if val > 0:
                    od = val
            except ValueError:
                pass

        if od is None:
            key = self.cmb_od.currentData()
            od = ASME_B36_10_PIPES.get(key, (114.3, []))[0]

        # Wall Thickness (t) fallback logic
        custom_t_str = self.txt_custom_t.text().strip().replace(",", ".")
        t = None
        if custom_t_str:
            try:
                val = float(custom_t_str)
                if val > 0:
                    t = val
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
                output_val = float(self.txt_app_activity.text().replace(",", "."))
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

        return od, t, cap, d, sfd, output_val, base_e, detector_type, film_class_used, chart_source

    def update_calculations(self):
        # 1. Fetch values
        od, t, cap, d, sfd, output_val, base_e, detector_type, film_class_used, chart_source = self.get_form_values()
        
        material_keys = ["steel", "aluminum", "titanium", "copper_nickel"]
        material = material_keys[self.cmb_material.currentIndex()]

        tech = "digital" if self.rad_digital.isChecked() else "analog"
        
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60"]
        source = source_keys[self.cmb_source.currentIndex()]

        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"

        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]

        # 2. Geometry Constraints
        # Disable/Enable geometry combinations
        # DWDI is only active if OD <= 100 mm
        if od > 100.0:
            if geometry in ["dwdi_elliptic", "dwdi_super"]:
                # Force to DWSI if user has selected a DWDI but diameter is too large
                self.cmb_geometry.setCurrentIndex(0)
                geometry = "dwsi"
        
        # 3. Dynamic calculations
        w_nom, w_eff = self.calc.calculate_thicknesses(t, cap, geometry)
        
        # Tube Voltage kV
        u_max = self.calc.calculate_u_max(w_nom, material)

        # Minimum Source-to-Object distance (f_min)
        # In ISO 17636, object-to-detector distance b:
        # SWSI and DWSI -> b = t
        # DWDI -> b = OD
        # Curved/planar detectors -> b = bed + bgap + K*t (Formulae 8-12)
        is_curved = self.rad_detector_curved.isChecked()
        std_figure = self.cmb_std_figure.currentData() if hasattr(self, 'cmb_std_figure') else None
        try:
            bed = float(self.txt_bed.text().replace(",", "."))
        except ValueError:
            bed = 0.0
        try:
            bgap = float(self.txt_bgap.text().replace(",", "."))
        except ValueError:
            bgap = 5.0

        if is_curved and self.calc.is_central_projection(geometry, std_figure):
            b_dist = self.calc.calculate_b_panoramic(bed, bgap, t)
        elif is_curved:
            b_dist = self.calc.calculate_b_curved(bed, bgap, t, testing_class)
        else:
            b_dist = t if geometry in ["swsi", "dwsi"] else od
        b_eff, b_rule_applied = self.calc.get_effective_b(b_dist, t)
        f_min = self.calc.calculate_f_min(d, b_dist, testing_class, t)

        # Min Source-to-Detector Distance (SFD_min)
        # SFD = f + b. So SFD_min = f_min + b_dist
        sfd_min = f_min + b_dist

        # SDD formula (6)/(7): ensure detector coverage
        try:
            dd = float(self.txt_dd.text().replace(",", "."))
        except ValueError:
            dd = 200.0
        sdd_min = self.calc.calculate_sdd_min(dd)
        if sdd_min > sfd_min:
            sfd_min = sdd_min

        # Geometric Unsharpness (moved here for early use in warnings)
        ug = self.calc.calculate_geometric_unsharpness(d, b_dist, sfd)
        f_min_star, ci_factor = self.calc.calculate_f_min_star(d, b_dist, t, testing_class)
        if f_min_star is not None and f_min_star > f_min:
            f_min = f_min_star

        # Exposures
        if geometry == "swsi":
            exposures = 1
        elif geometry == "dwdi_elliptic":
            exposures = 2
        elif geometry == "dwdi_super":
            exposures = 3
        else: # DWSI
            exposures = self.calc.calculate_dwsi_exposures(od, t, sfd, testing_class)

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
            
        duplex_str, duplex_no = self.calc.get_duplex_iqi(w_nom, testing_class, geometry, lang=self.trans.language)

        # Step 7: Detector Quality
        film_class_req = self.calc.get_required_film_class(w_nom, testing_class, material, source)
        max_srb_req = self.calc.get_max_srb(w_nom, testing_class, geometry)
        if tech == "analog":
            detector_quality_str = f"{film_class_req} Film"
        else:
            detector_quality_str = f"Max {max_srb_req} µm"

        # Quality Targets & Level 3 Compensation
        warnings = []
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

        # 4. Warnings Generation
        # Sınıf A warning
        if testing_class == "class_a":
            warnings.append(self.trans.get("warn_class_a"))

        # DWDI diameter check
        if od > 100.0 and geometry in ["dwdi_elliptic", "dwdi_super"]:
            warnings.append(self.trans.get("warn_dwdi_limit"))

        # Isotope on light metal check
        if source != "x_ray" and material in ["aluminum", "titanium"]:
            warnings.append(self.trans.get("warn_isotope_light_metal"))

        # b < 1.2t rule: warn when effective b is adjusted
        if b_rule_applied:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): b ({b_dist:.1f} mm) < 1.2×t ({1.2*t:.1f} mm) olduğundan b = t ({t:.1f} mm) kullanıldı.")
            else:
                warnings.append(f"NOTE (Clause 7.6): b ({b_dist:.1f} mm) < 1.2×t ({1.2*t:.1f} mm), using b = t ({t:.1f} mm).")

        # SDD rule: warn when detector size limits SFD
        if sdd_min > f_min + b_dist:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Dedektör boyutu (dd={dd:.0f} mm) SFD_min'i {sdd_min:.0f} mm'ye yükseltti.")
            else:
                warnings.append(f"NOTE (Clause 7.6): Detector size (dd={dd:.0f} mm) raises SFD_min to {sdd_min:.0f} mm.")

        # Annex F IQI compensation check: Ug/SRb > 2 -> needs compensation
        annex_f_needed, annex_f_ratio = self.calc.check_annex_f_compensation(ug, max_srb_req)
        if annex_f_needed:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Annex F): Ug/SRb ({annex_f_ratio:.1f}) > 2. IQI görünürlüğü için f_min artırılmalı veya SNR yükseltilmelidir.")
            else:
                warnings.append(f"NOTE (Annex F): Ug/SRb ({annex_f_ratio:.1f}) > 2. Increase f_min or SNR for IQI visibility.")

        # Double-wall technique: up to 20% f_min reduction allowed per Clause 7.6
        if self.calc.is_double_wall_technique(geometry):
            f_min_80 = f_min * 0.8
            if self.lvl3_settings.get("dw_reduction", False):
                f_min = f_min_80
                if self.trans.language == "tr":
                    warnings.append(f"Level 3: Çift duvar tekniğinde f_min %20 düşürüldü ({f_min_80:.1f} mm).")
                else:
                    warnings.append(f"Level 3: Double-wall technique f_min reduced 20% to {f_min_80:.1f} mm.")
            else:
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Çift duvar tekniğinde f_min %20 düşürülebilir ({f_min_80:.1f} mm). IQI şartları sağlanmalıdır.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Double-wall technique allows 20% f_min reduction (to {f_min_80:.1f} mm). IQI requirements must be met.")

        # Central projection (Fig 5): up to 50% f_min reduction allowed
        std_figure = self.cmb_std_figure.currentData() if hasattr(self, 'cmb_std_figure') else None
        is_central = self.calc.is_central_projection(geometry, std_figure)
        if is_central:
            f_min_50 = f_min * 0.5
            if self.lvl3_settings.get("central_proj_reduction", False):
                f_min = f_min_50
                if self.trans.language == "tr":
                    warnings.append(f"Level 3: Merkezi projeksiyonda f_min %%50 düşürüldü ({f_min_50:.1f} mm).")
                else:
                    warnings.append(f"Level 3: Central projection f_min reduced 50% to {f_min_50:.1f} mm.")
                # Duplex/SRb tolerance also applies
                if self.trans.language == "tr":
                    warnings.append("BİLGİ (Madde 7.6): Merkezi projeksiyonda 1 duplex adım veya 1 SRb toleransı uygulanır.")
                else:
                    warnings.append("NOTE (Clause 7.6): Central projection allows 1 duplex step or 1 SRb tolerance.")
            else:
                if self.trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Merkezi projeksiyonda f_min %%50 düşürülebilir ({f_min_50:.1f} mm). Level 3 onayı gerekiyor.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Central projection allows 50%% f_min reduction (to {f_min_50:.1f} mm). Requires Level 3 approval.")

        # f_min* magnification rule: warn when b/t > 1.2 triggers Ci factor
        if f_min_star is not None and ci_factor is not None:
            if self.trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): b/t = {b_dist/t:.2f} > 1.2 olduğundan f_min* = f_min × Ci (Ci = {ci_factor:.3f}) uygulandı.")
            else:
                warnings.append(f"NOTE (Clause 7.6): b/t = {b_dist/t:.2f} > 1.2, applying f_min* = f_min × Ci (Ci = {ci_factor:.3f}).")

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
                overlap = float(self.txt_app_overlap.text().replace(",", "."))
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

        self.out_labels["f_min"][1].setText(f"{f_min:.1f} mm")
        self.out_labels["sfd_min"][1].setText(f"{sfd_min:.1f} mm")
        self.out_labels["ug"][1].setText(f"{ug:.3f} mm")
        self.out_labels["req_exposures"][1].setText(f"{exposures}")
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

        # Filter recommendation output
        filter_recs = self.calc.get_filter_recommendations(source, material, input_kv, testing_class)
        # Format string based on language
        if self.trans.language == "tr":
            pb = filter_recs["pb_screen"]
            pb = pb.replace("Front", "Ön").replace("Back", "Arka").replace("None", "Yok").replace("Front & Back", "Ön & Arka")
            filt = filter_recs["metal_filter"]
            filt = filt.replace("None", "Yok").replace("or", "veya")
            filter_str = f"{pb} | Filtre: {filt}"
        else:
            filter_str = f"{filter_recs['pb_screen']} | Filter: {filter_recs['metal_filter']}"
            
        self.out_labels["filter_recommendation"][1].setText(filter_str)

        # Store calculated results for compliance checker
        self.last_calculated = {
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max,
            "sfd_min": sfd_min,
            "sdd_min": sdd_min,
            "ug": ug,
            "f_min": f_min,
            "b_dist": b_dist,
            "b_eff": b_eff,
            "required_wire_no": wire_no,
            "required_duplex_no": duplex_no,
            "calc_time_raw": raw_time,
            "required_film_class": film_class_req,
            "max_srb": max_srb_req,
            "filter_recommendation": filter_str
        }
        if tech == "digital":
            self.last_calculated["required_snr"] = target_snr_val
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
        self.canvas.draw_setup(od, t, cap, geometry, sfd, self.trans)

        # Automatically check compliance
        self.check_procedure_compliance()

    def evaluate_defect(self):
        # Read inputs
        t = self.get_form_values()[1] # get wall thickness
        
        defect_types = ["defect_ip", "defect_if", "defect_ic", "defect_porosity", "defect_crack"]
        defect_type = defect_types[self.cmb_defect_type.currentIndex()]

        try:
            length = float(self.txt_defect_length.text().replace(",", "."))
        except ValueError:
            length = 0.0

        try:
            width = float(self.txt_defect_width.text().replace(",", "."))
        except ValueError:
            width = 0.0

        try:
            accum = float(self.txt_defect_accum.text().replace(",", "."))
        except ValueError:
            accum = 0.0

        is_accepted, reason = self.api_eval.evaluate(defect_type, t, length, width, accum, self.trans.language)

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
            applied_activity = float(self.txt_app_activity.text().replace(",", "."))
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
            applied_overlap = float(self.txt_app_overlap.text().replace(",", "."))
        except ValueError:
            applied_overlap = 0.0

        try:
            applied_srb = float(self.txt_app_srb.text().replace(",", "."))
        except ValueError:
            applied_srb = 0.0

        # Build dictionaries for checker
        tech = "digital" if self.rad_digital.isChecked() else "analog"
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60"]
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
            "applied_overlap": applied_overlap
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
            calc_activity = self.get_form_values()[5] # output_val entered in inputs
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
        od, t, cap, d, sfd, output_val, base_e, detector_type, film_class_used, _chart_source = self.get_form_values()
        material_keys = ["steel", "aluminum", "titanium", "copper_nickel"]
        material = material_keys[self.cmb_material.currentIndex()]
        tech = "digital" if self.rad_digital.isChecked() else "analog"
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60"]
        source = source_keys[self.cmb_source.currentIndex()]
        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"
        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]

        try:
            input_kv = float(self.txt_app_kv.text().replace(",", "."))
        except ValueError:
            input_kv = 120.0

        try:
            overlap = float(self.txt_app_overlap.text().replace(",", "."))
        except ValueError:
            overlap = 10.0

        inputs = {
            "material_text": self.trans.get(material),
            "class_text": self.trans.get(testing_class),
            "od": od,
            "t": t,
            "cap": cap,
            "d": d,
            "sfd": sfd,
            "output_val": output_val,
            "base_e": base_e,
            "speed": film_class_used if tech == "analog" else detector_type,
            "tech": tech,
            "tech_text": self.trans.get("analog_film" if tech == "analog" else "digital_cr_dda"),
            "source": source,
            "source_text": self.trans.get(source),
            "geometry_text": self.trans.get(geometry),
            "input_kv": input_kv,
            "overlap": overlap,
            "iqi_type": self.cmb_iqi_type.currentData(),
            "snr_location": self.cmb_snr_location.currentData()
        }

        # Gather outputs
        w_nom, w_eff = self.calc.calculate_thicknesses(t, cap, geometry)
        u_max = self.calc.calculate_u_max(w_nom, material)
        is_curved = self.rad_detector_curved.isChecked()
        std_figure = self.cmb_std_figure.currentData() if hasattr(self, 'cmb_std_figure') else None
        try:
            bed = float(self.txt_bed.text().replace(",", "."))
        except ValueError:
            bed = 0.0
        try:
            bgap = float(self.txt_bgap.text().replace(",", "."))
        except ValueError:
            bgap = 5.0
        if is_curved and self.calc.is_central_projection(geometry, std_figure):
            b_dist = self.calc.calculate_b_panoramic(bed, bgap, t)
        elif is_curved:
            b_dist = self.calc.calculate_b_curved(bed, bgap, t, testing_class)
        else:
            b_dist = t if geometry in ["swsi", "dwsi"] else od
        f_min = self.calc.calculate_f_min(d, b_dist, testing_class, t)
        sfd_min = f_min + b_dist
        try:
            dd = float(self.txt_dd.text().replace(",", "."))
        except ValueError:
            dd = 200.0
        sdd_min = self.calc.calculate_sdd_min(dd)
        if sdd_min > sfd_min:
            sfd_min = sdd_min
        
        if geometry == "swsi":
            exposures = 1
        elif geometry == "dwdi_elliptic":
            exposures = 2
        elif geometry == "dwdi_super":
            exposures = 3
        else:
            exposures = self.calc.calculate_dwsi_exposures(od, t, sfd, testing_class)

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
            "f_min": f_min,
            "sfd_min": sfd_min,
            "exposures": exposures,
            "single_wire_iqi": wire_str,
            "duplex_iqi": duplex_str if tech == "digital" else "N/A",
            "quality_target": target_quality,
            "calc_time": calc_time,
            "detector_quality": self.out_labels["detector_quality"][1].text(),
            "filter_recommendation": self.out_labels["filter_recommendation"][1].text()
        }

        # Gather defect details if evaluated
        defect_eval = None
        defect_text = self.lbl_defect_result.text()
        if defect_text:
            defect_types = ["defect_ip", "defect_if", "defect_ic", "defect_porosity", "defect_crack"]
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

            # evaluate again to get full details
            is_accepted, reason = self.api_eval.evaluate(defect_type, t, def_len, def_width, def_accum, self.trans.language)

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

        sfd_comp_val = None
        if self.lvl3_settings["sfd_comp"] and sfd < sfd_min:
            base_snr = 130.0 if testing_class == "class_b" else 70.0
            sfd_comp_val = base_snr * (sfd_min / max(10.0, sfd))

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
            dynamic_img_path = None

        try:
            tmp_standard = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_standard.close()
            self.std_canvas.save_figure(tmp_standard.name)
            standard_img_path = tmp_standard.name
        except Exception:
            standard_img_path = None

        success = self.pdf_gen.generate_report(
            filepath, inputs, outputs, warnings_list, defect_eval, 
            self.lvl3_settings["sfd_comp"] or self.lvl3_settings["voltage_override"] or self.lvl3_settings["isotope_flex"],
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
                    pass

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

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction(f"About Radiography v{CURRENT_VERSION}", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        QMessageBox.about(self, "About Radiography",
                          f"Radiographic Testing (RT) Exposure Calculator\n"
                          f"Version: {CURRENT_VERSION}\n"
                          f"ISO 17636 / API 1104 Compliant\n\n"
                          f"© 2026 Radiography")

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
        self.check_update_action.setEnabled(True)
        self.check_update_action.setText("Check for Updates")

        if result.get("available"):
            reply = QMessageBox.question(
                self, "Update Available",
                f"A new version ({result['version']}) is available.\n\n"
                f"{result.get('release_notes', '')[:500]}\n\n"
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

            def run(self):
                try:
                    filepath = checker.download_update(
                        url,
                        progress_callback=lambda pct: self.progress.setValue(int(pct * 100))
                    )
                    self.finished.emit(filepath)
                except Exception as e:
                    self.finished.emit(e)

        self._download_thread = DownloadThread()
        self._download_thread.finished.connect(lambda fp: self._on_download_finished(fp, checker))
        self._download_thread.start()

    def _on_download_finished(self, filepath, checker):
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

    def apply_theme(self):
        """
        Applies styling to PyQt UI (main window + application-wide for dialogs)
        """
        if self.is_dark_theme:
            # Dark Theme Colors: Mocha styled
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.setStyleSheet("""
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
                """)
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
                    border-radius: 4px;
                    color: #cdd6f4;
                    padding: 5px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #fab387;
                }
                QComboBox {
                    background-color: #313244;
                    border: 1px solid #45475a;
                    border-radius: 4px;
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
            """)
        else:
            # Light Theme Colors: Professional slate light
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.setStyleSheet("""
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
                """)
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
                    border-radius: 4px;
                    color: #212121;
                    padding: 5px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #0d47a1;
                }
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #b0bec5;
                    border-radius: 4px;
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
