# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class WarningsPanelMixin:
    """Mixin that creates the warnings panel (self.grp_warnings)."""

    def _init_warnings_panel(self):
        self.grp_warnings = QGroupBox(self.trans.get("warnings"))
        self.grp_warnings.setObjectName("WarningsBox")
        warnings_layout = QVBoxLayout(self.grp_warnings)
        self.txt_warnings = QLabel("")
        self.txt_warnings.setWordWrap(True)
        self.txt_warnings.setStyleSheet("color: #f38ba8; font-size: 10px; font-weight: bold;")
        warnings_layout.addWidget(self.txt_warnings)

    def _retranslate_warnings_panel(self):
        self.grp_warnings.setTitle(self.trans.get("warnings"))


class CompliancePanelMixin:
    """Mixin that creates the compliance panel (self.grp_compliance)."""

    def _init_compliance_panel(self):
        self.grp_compliance = QGroupBox(self.trans.get("procedure_section"))
        self.grp_compliance.setObjectName("ComplianceBox")
        compliance_layout = QVBoxLayout(self.grp_compliance)
        self.lbl_compliance_result = QLabel("")
        self.lbl_compliance_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_compliance_result.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        compliance_layout.addWidget(self.lbl_compliance_result)
        self.lbl_compliance_details = QLabel("")
        self.lbl_compliance_details.setWordWrap(True)
        self.lbl_compliance_details.setFont(QFont("Helvetica", 9))
        self.lbl_compliance_details.setStyleSheet("color: #cdd6f4;")
        self.lbl_compliance_details.setTextFormat(Qt.TextFormat.RichText)
        compliance_layout.addWidget(self.lbl_compliance_details)

    def _retranslate_compliance_panel(self):
        self.grp_compliance.setTitle(self.trans.get("procedure_section"))
