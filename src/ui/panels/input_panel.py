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


from src.core.asme_b36 import ASME_B36_10_PIPES


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
