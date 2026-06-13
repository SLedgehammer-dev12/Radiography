# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import (QGroupBox, QComboBox, QLineEdit, QLabel,
                             QRadioButton, QButtonGroup, QVBoxLayout,
                             QHBoxLayout, QWidget, QFormLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator


class QFormLayout_custom(QFormLayout):
    def __init__(self):
        super().__init__()
        self.setContentsMargins(10, 5, 10, 10)
        self.setSpacing(8)
        self.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)


ASME_B36_10_PIPES = {
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


class InputPanelMixin:
    """Mixin that creates the input form widgets and related methods."""

    def _init_input_panel(self, grp_inputs_layout):
        # Material
        self.cmb_material = QComboBox()
        self.cmb_material.addItems([
            self.trans.get("steel"),
            self.trans.get("aluminum"),
            self.trans.get("titanium"),
            self.trans.get("copper_nickel")
        ])
        self.cmb_material.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("material_type"), self.cmb_material)

        # Standard OD
        self.lbl_std_od = QLabel(self.trans.get("std_pipe_od"))
        self.cmb_od = QComboBox()
        self.cmb_od.blockSignals(True)
        for key in ASME_B36_10_PIPES.keys():
            self.cmb_od.addItem(key, key)
        self.cmb_od.currentIndexChanged.connect(self.on_od_changed)
        grp_inputs_layout.addRow(self.lbl_std_od, self.cmb_od)

        # Custom OD
        self.lbl_custom_od = QLabel(self.trans.get("custom_pipe_od"))
        self.txt_custom_od = QLineEdit()
        self.txt_custom_od.setValidator(QDoubleValidator(1.0, 5000.0, 2))
        self.txt_custom_od.setPlaceholderText(self.trans.get("custom_od_placeholder"))
        self.txt_custom_od.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_custom_od, self.txt_custom_od)

        # Standard wall thickness
        self.lbl_std_t = QLabel(self.trans.get("std_nominal_t"))
        self.cmb_t = QComboBox()
        self.cmb_t.blockSignals(True)
        self.cmb_t.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_std_t, self.cmb_t)

        # Custom wall thickness
        self.lbl_custom_t = QLabel(self.trans.get("custom_nominal_t"))
        self.txt_custom_t = QLineEdit()
        self.txt_custom_t.setValidator(QDoubleValidator(0.1, 500.0, 2))
        self.txt_custom_t.setPlaceholderText(self.trans.get("custom_t_placeholder"))
        self.txt_custom_t.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_custom_t, self.txt_custom_t)

        # Cap height
        self.txt_cap = QLineEdit("3.0")
        self.txt_cap.setValidator(QDoubleValidator(0.0, 50.0, 2))
        self.txt_cap.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("cap_height"), self.txt_cap)

        # Analog/Digital toggle
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
        tech_layout.setContentsMargins(0, 0, 0, 0)
        tech_layout.addWidget(self.rad_analog)
        tech_layout.addWidget(self.rad_digital)
        grp_inputs_layout.addRow(self.trans.get("rt_tech"), tech_widget)

        # Source
        self.cmb_source = QComboBox()
        self.cmb_source.addItems([
            self.trans.get("x_ray"),
            self.trans.get("isotope_ir192"),
            self.trans.get("isotope_se75"),
            self.trans.get("isotope_co60")
        ])
        self.cmb_source.currentIndexChanged.connect(self.on_source_changed)
        grp_inputs_layout.addRow(self.trans.get("rad_source"), self.cmb_source)

        # Focal size
        self.txt_d = QLineEdit("2.0")
        self.txt_d.setValidator(QDoubleValidator(0.01, 20.0, 2))
        self.txt_d.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("focal_size"), self.txt_d)

        # Detector size
        self.txt_dd = QLineEdit("200.0")
        self.txt_dd.setValidator(QDoubleValidator(1.0, 1000.0, 1))
        self.txt_dd.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("detector_size"), self.txt_dd)

        # Testing class
        self.cmb_class = QComboBox()
        self.cmb_class.addItems([
            self.trans.get("class_b"),
            self.trans.get("class_a")
        ])
        self.cmb_class.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("testing_class"), self.cmb_class)

        # Geometry
        self.cmb_geometry = QComboBox()
        self.cmb_geometry.addItems([
            self.trans.get("dwsi"),
            self.trans.get("swsi"),
            self.trans.get("dwdi_elliptic"),
            self.trans.get("dwdi_super")
        ])
        self.cmb_geometry.currentIndexChanged.connect(self.on_geometry_changed)
        grp_inputs_layout.addRow(self.trans.get("geometry"), self.cmb_geometry)

        # Standard figure reference
        self.cmb_std_figure = QComboBox()
        self.cmb_std_figure.currentIndexChanged.connect(self.on_std_figure_changed)
        grp_inputs_layout.addRow(self.trans.get("standard_fig"), self.cmb_std_figure)

        # Detector shape (flat/curved)
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

        # Bed & gap
        self.txt_bed = QLineEdit("0.0")
        self.txt_bed.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_bed.textChanged.connect(self.update_calculations)
        self.lbl_bed = grp_inputs_layout.addRow(self.trans.get("bed"), self.txt_bed)

        self.txt_bgap = QLineEdit("5.0")
        self.txt_bgap.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_bgap.textChanged.connect(self.update_calculations)
        self.lbl_bgap = grp_inputs_layout.addRow(self.trans.get("bgap"), self.txt_bgap)

    def _retranslate_input_panel(self):
        labels = {
            "lbl_std_od": "std_pipe_od",
            "lbl_custom_od": "custom_pipe_od",
            "lbl_std_t": "std_nominal_t",
            "lbl_custom_t": "custom_nominal_t",
        }
        for attr, key in labels.items():
            getattr(self, attr).setText(self.trans.get(key))
