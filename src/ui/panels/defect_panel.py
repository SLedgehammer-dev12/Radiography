# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import (QWidget, QGridLayout, QLabel, QComboBox,
                             QLineEdit, QPushButton, QTabWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDoubleValidator


class DefectPanelMixin:
    """Mixin that creates API 1104 defect evaluation tab UI (self.tab_extra)."""

    def _init_defect_panel(self):
        self.tab_extra = QTabWidget()
        self.tab_extra.setObjectName("ExtraTabs")
        tab_defect = QWidget()
        defect_layout = QGridLayout(tab_defect)
        tab_defect.setLayout(defect_layout)
        defect_layout.addWidget(QLabel(self.trans.get("defect_type")), 0, 0)
        self.cmb_defect_type = QComboBox()
        self.cmb_defect_type.addItems([
            self.trans.get("defect_ip"),
            self.trans.get("defect_if"),
            self.trans.get("defect_ic"),
            self.trans.get("defect_porosity"),
            self.trans.get("defect_crack"),
            self.trans.get("defect_slag"),
            self.trans.get("defect_undercut"),
            self.trans.get("defect_burn_through"),
        ])
        defect_layout.addWidget(self.cmb_defect_type, 0, 1)

        defect_layout.addWidget(QLabel(self.trans.get("defect_length")), 1, 0)
        self.txt_defect_length = QLineEdit("10.0")
        self.txt_defect_length.setValidator(QDoubleValidator(0.0, 1000.0, 2))
        defect_layout.addWidget(self.txt_defect_length, 1, 1)
        defect_layout.addWidget(QLabel(self.trans.get("defect_width")), 2, 0)
        self.txt_defect_width = QLineEdit("1.5")
        self.txt_defect_width.setValidator(QDoubleValidator(0.0, 100.0, 2))
        defect_layout.addWidget(self.txt_defect_width, 2, 1)
        defect_layout.addWidget(QLabel(self.trans.get("accumulated_12in")), 3, 0)
        self.txt_defect_accum = QLineEdit("15.0")
        self.txt_defect_accum.setValidator(QDoubleValidator(0.0, 300.0, 2))
        defect_layout.addWidget(self.txt_defect_accum, 3, 1)
        self.btn_eval_defect = QPushButton(self.trans.get("evaluate_defect"))
        self.btn_eval_defect.clicked.connect(self.evaluate_defect)
        defect_layout.addWidget(self.btn_eval_defect, 4, 0, 1, 2)
        self.lbl_defect_result = QLabel("")
        self.lbl_defect_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_defect_result.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        defect_layout.addWidget(self.lbl_defect_result, 5, 0, 1, 2)
        self.tab_extra.addTab(tab_defect, self.trans.get("defect_section"))

    def _retranslate_defect_panel(self):
        defect_idx = self.cmb_defect_type.currentIndex()
        self.cmb_defect_type.clear()
        self.cmb_defect_type.addItems([
            self.trans.get("defect_ip"),
            self.trans.get("defect_if"),
            self.trans.get("defect_ic"),
            self.trans.get("defect_porosity"),
            self.trans.get("defect_crack"),
            self.trans.get("defect_slag"),
            self.trans.get("defect_undercut"),
            self.trans.get("defect_burn_through"),
        ])
        self.cmb_defect_type.setCurrentIndex(defect_idx)
        self.btn_eval_defect.setText(self.trans.get("evaluate_defect"))
        self.tab_extra.setTabText(0, self.trans.get("defect_section"))
