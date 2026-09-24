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
        for key in ("steel", "aluminum", "titanium", "copper_nickel"):
            self.cmb_material.addItem(self.trans.get(key), key)
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

        # Weld width (used for the DWDI elliptical weld width <= De/4 check)
        self.lbl_weld_width = QLabel(self.trans.get("weld_width"))
        self.txt_weld_width = QLineEdit("8.0")
        self.txt_weld_width.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_weld_width.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_weld_width, self.txt_weld_width)

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
        for key in ("x_ray", "isotope_ir192", "isotope_se75", "isotope_co60",
                    "isotope_yb169", "isotope_tm170"):
            self.cmb_source.addItem(self.trans.get(key), key)
        self.cmb_source.currentIndexChanged.connect(self.on_source_changed)
        grp_inputs_layout.addRow(self.trans.get("rad_source"), self.cmb_source)

        # Focal / Source size
        self.lbl_focal_size = QLabel(self.trans.get("focal_size"))
        self.txt_d = QLineEdit("2.0")
        self.txt_d.setValidator(QDoubleValidator(0.01, 20.0, 2))
        self.txt_d.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_focal_size, self.txt_d)

        # Film sheet dimensions (analog only) - used to derive df for the
        # SFD >= 1.4*df coverage check (ISO 17636-1:2022 Formula 4).
        self.lbl_film_size = QLabel(self.trans.get("film_size"))
        self.cmb_film_size = QComboBox()
        self._film_size_presets = {
            "80x300": (80.0, 300.0),
            "100x400": (100.0, 400.0),
            "300x400": (300.0, 400.0),
            "100x500": (100.0, 500.0),
        }
        for key in ("80x300", "100x400", "300x400", "100x500", "custom"):
            self.cmb_film_size.addItem(self.trans.get(f"film_size_{key}"), key)
        self.cmb_film_size.setCurrentIndex(1)  # default 100 x 400 mm
        self.cmb_film_size.currentIndexChanged.connect(self.on_film_size_changed)
        grp_inputs_layout.addRow(self.lbl_film_size, self.cmb_film_size)

        self.lbl_film_width = QLabel(self.trans.get("film_width"))
        self.txt_film_width = QLineEdit("100.0")
        self.txt_film_width.setValidator(QDoubleValidator(1.0, 2000.0, 1))
        self.txt_film_width.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_film_width, self.txt_film_width)

        self.lbl_film_height = QLabel(self.trans.get("film_height"))
        self.txt_film_height = QLineEdit("400.0")
        self.txt_film_height.setValidator(QDoubleValidator(1.0, 2000.0, 1))
        self.txt_film_height.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_film_height, self.txt_film_height)

        # Testing class
        self.cmb_class = QComboBox()
        for key in ("class_b", "class_a"):
            self.cmb_class.addItem(self.trans.get(key), key)
        self.cmb_class.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("testing_class"), self.cmb_class)

        # Inspection standard
        self.cmb_standard = QComboBox()
        self.cmb_standard.addItem(self.trans.get("standard_iso"), "iso")
        self.cmb_standard.addItem(self.trans.get("standard_asme"), "asme")
        self.cmb_standard.currentIndexChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.trans.get("standard"), self.cmb_standard)

        # Geometry
        self.cmb_geometry = QComboBox()
        for key in ("dwsi", "swsi", "dwdi_elliptic", "dwdi_super"):
            self.cmb_geometry.addItem(self.trans.get(key), key)
        self.cmb_geometry.currentIndexChanged.connect(self.on_geometry_changed)
        grp_inputs_layout.addRow(self.trans.get("geometry"), self.cmb_geometry)

        # Standard figure reference
        self.cmb_std_figure = QComboBox()
        self.cmb_std_figure.currentIndexChanged.connect(self.on_std_figure_changed)
        grp_inputs_layout.addRow(self.trans.get("standard_fig"), self.cmb_std_figure)

        # Detector shape: planar/rigid panel vs flexible (wrapped) CR/IP
        self.lbl_det_shape = QLabel(self.trans.get("detector_type"))
        self.rad_detector_flat = QRadioButton(self.trans.get("detector_planar"))
        self.rad_detector_curved = QRadioButton(self.trans.get("detector_flexible"))
        self.rad_detector_flat.setToolTip(self.trans.get("tt_detector_planar"))
        self.rad_detector_curved.setToolTip(self.trans.get("tt_detector_flexible"))
        self.rad_detector_flat.setChecked(True)
        self.det_type_widget = QWidget()
        det_type_layout = QHBoxLayout(self.det_type_widget)
        det_type_layout.setContentsMargins(0, 0, 0, 0)
        det_type_layout.addWidget(self.rad_detector_flat)
        det_type_layout.addWidget(self.rad_detector_curved)
        self.rad_detector_flat.toggled.connect(self.on_detector_type_changed)
        self.rad_detector_curved.toggled.connect(self.on_detector_type_changed)
        grp_inputs_layout.addRow(self.lbl_det_shape, self.det_type_widget)

        # Bed & gap (digital curved only)
        self.lbl_bed = QLabel(self.trans.get("bed"))
        self.txt_bed = QLineEdit("0.0")
        self.txt_bed.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_bed.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_bed, self.txt_bed)

        self.lbl_bgap = QLabel(self.trans.get("bgap"))
        self.txt_bgap = QLineEdit("5.0")
        self.txt_bgap.setValidator(QDoubleValidator(0.0, 500.0, 1))
        self.txt_bgap.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_bgap, self.txt_bgap)

        # User-provided geometry overrides (digital, blank = auto)
        self.lbl_f_source = QLabel(self.trans.get("source_dist"))
        self.txt_f_source = QLineEdit()
        self.txt_f_source.setValidator(QDoubleValidator(1.0, 5000.0, 1))
        self.txt_f_source.setPlaceholderText(self.trans.get("auto_calc"))
        self.txt_f_source.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_f_source, self.txt_f_source)

        self.lbl_b_object = QLabel(self.trans.get("object_dist"))
        self.txt_b_object = QLineEdit()
        self.txt_b_object.setValidator(QDoubleValidator(0.0, 5000.0, 1))
        self.txt_b_object.setPlaceholderText(self.trans.get("auto_calc"))
        self.txt_b_object.textChanged.connect(self.update_calculations)
        grp_inputs_layout.addRow(self.lbl_b_object, self.txt_b_object)

    def _retranslate_input_panel(self):
        labels = {
            "lbl_std_od": "std_pipe_od",
            "lbl_custom_od": "custom_pipe_od",
            "lbl_std_t": "std_nominal_t",
            "lbl_custom_t": "custom_nominal_t",
            "lbl_f_source": "source_dist",
            "lbl_b_object": "object_dist",
            "lbl_weld_width": "weld_width",
            "lbl_bed": "bed",
            "lbl_bgap": "bgap",
            "lbl_film_size": "film_size",
            "lbl_film_width": "film_width",
            "lbl_film_height": "film_height",
        }
        for attr, key in labels.items():
            getattr(self, attr).setText(self.trans.get(key))
        self.txt_f_source.setPlaceholderText(self.trans.get("auto_calc"))
        self.txt_b_object.setPlaceholderText(self.trans.get("auto_calc"))
        # Detector model radio labels / tooltips
        self.rad_detector_flat.setText(self.trans.get("detector_planar"))
        self.rad_detector_curved.setText(self.trans.get("detector_flexible"))
        self.rad_detector_flat.setToolTip(self.trans.get("tt_detector_planar"))
        self.rad_detector_curved.setToolTip(self.trans.get("tt_detector_flexible"))
        # Film size combo labels
        for i in range(self.cmb_film_size.count()):
            key = self.cmb_film_size.itemData(i)
            self.cmb_film_size.setItemText(i, self.trans.get(f"film_size_{key}"))

    def on_film_size_changed(self):
        """Applies a preset film size or enables the custom width/height fields."""
        key = self.cmb_film_size.currentData()
        is_custom = key == "custom"
        self.txt_film_width.setEnabled(is_custom)
        self.txt_film_height.setEnabled(is_custom)
        preset = self._film_size_presets.get(key)
        if preset is not None:
            w, h = preset
            for widget, value in ((self.txt_film_width, w), (self.txt_film_height, h)):
                widget.blockSignals(True)
                widget.setText(f"{value:.0f}")
                widget.blockSignals(False)
        self.update_calculations()
