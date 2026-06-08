# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QLineEdit, QPushButton, QGroupBox
from PyQt6.QtCore import Qt

class Level3Dialog(QDialog):
    def __init__(self, current_lang_obj, parent=None, is_dark=True):
        super().__init__(parent)
        self.lang = current_lang_obj
        self.is_dark = is_dark
        self.setWindowTitle(self.lang.get("level3_section"))
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Exceptions Group
        group = QGroupBox(self.lang.get("level3_section"))
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)

        self.chk_sfd_comp = QCheckBox(self.lang.get("lvl3_sfd_compensation"))
        self.chk_voltage_override = QCheckBox(self.lang.get("lvl3_voltage_override"))
        self.chk_isotope_flex = QCheckBox(self.lang.get("lvl3_isotope_flex"))
        self.chk_source_flex = QCheckBox(self.lang.get("lvl3_source_flex"))
        self.chk_central_proj = QCheckBox(self.lang.get("lvl3_central_proj"))
        self.chk_dw_reduction = QCheckBox(self.lang.get("lvl3_dw_reduction"))

        group_layout.addWidget(self.chk_sfd_comp)
        group_layout.addWidget(self.chk_voltage_override)
        group_layout.addWidget(self.chk_isotope_flex)
        group_layout.addWidget(self.chk_source_flex)
        group_layout.addWidget(self.chk_central_proj)
        group_layout.addWidget(self.chk_dw_reduction)
        
        layout.addWidget(group)

        # Metadata Layout
        meta_layout = QHBoxLayout()
        self.lbl_approval = QLabel(self.lang.get("level3_approval_note"))
        self.txt_approval = QLineEdit()
        self.txt_approval.setPlaceholderText(self.lang.get("level3_approval_placeholder"))
        meta_layout.addWidget(self.lbl_approval)
        meta_layout.addWidget(self.txt_approval)
        layout.addLayout(meta_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton(self.lang.get("dialog_ok"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(self.lang.get("dialog_cancel"))
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def apply_theme(self):
        if self.is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1e1e2e;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 2px solid #313244;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                    color: #fab387;
                    font-weight: bold;
                }
                QCheckBox {
                    color: #cdd6f4;
                    spacing: 8px;
                    font-size: 11px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
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
                    padding: 4px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #fab387;
                }
                QPushButton {
                    background-color: #45475a;
                    color: #cdd6f4;
                    border: 1px solid #585b70;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #585b70;
                    color: #ffffff;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                    color: #212121;
                }
                QGroupBox {
                    border: 2px solid #cfd8dc;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                    color: #0d47a1;
                    font-weight: bold;
                }
                QCheckBox {
                    color: #212121;
                    spacing: 8px;
                    font-size: 11px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
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
                    padding: 4px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #0d47a1;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: #212121;
                    border: 1px solid #b0bec5;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #b0bec5;
                    color: #000000;
                }
            """)

    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.apply_theme()

    def get_settings(self):
        """
        Returns a dictionary of the Level 3 settings
        """
        return {
            "sfd_comp": self.chk_sfd_comp.isChecked(),
            "voltage_override": self.chk_voltage_override.isChecked(),
            "isotope_flex": self.chk_isotope_flex.isChecked(),
            "source_flex": self.chk_source_flex.isChecked(),
            "central_proj_reduction": self.chk_central_proj.isChecked(),
            "dw_reduction": self.chk_dw_reduction.isChecked(),
            "approval_note": self.txt_approval.text()
        }

    def set_settings(self, settings):
        """
        Restores state of settings
        """
        self.chk_sfd_comp.setChecked(settings.get("sfd_comp", False))
        self.chk_voltage_override.setChecked(settings.get("voltage_override", False))
        self.chk_isotope_flex.setChecked(settings.get("isotope_flex", False))
        self.chk_source_flex.setChecked(settings.get("source_flex", False))
        self.chk_central_proj.setChecked(settings.get("central_proj_reduction", False))
        self.chk_dw_reduction.setChecked(settings.get("dw_reduction", False))
        self.txt_approval.setText(settings.get("approval_note", ""))
