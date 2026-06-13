# -*- coding: utf-8 -*-

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestMainWindowInit(unittest.TestCase):
    """Smoke tests: verify MainWindow can be instantiated without crash."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            cls._app = QApplication(sys.argv)
        else:
            cls._app = app

    def setUp(self):
        from src.ui.main_window import MainWindow
        self.win = MainWindow()

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()

    def test_grp_compliance_exists(self):
        self.assertTrue(hasattr(self.win, "grp_compliance"))

    def test_tab_extra_exists(self):
        self.assertTrue(hasattr(self.win, "tab_extra"))

    def test_grp_warnings_exists(self):
        self.assertTrue(hasattr(self.win, "grp_warnings"))

    def test_defect_widgets_exist(self):
        self.assertTrue(hasattr(self.win, "cmb_defect_type"))
        self.assertTrue(hasattr(self.win, "txt_defect_length"))
        self.assertTrue(hasattr(self.win, "txt_defect_width"))
        self.assertTrue(hasattr(self.win, "txt_defect_accum"))
        self.assertTrue(hasattr(self.win, "btn_eval_defect"))
        self.assertTrue(hasattr(self.win, "lbl_defect_result"))

    def test_defect_type_has_all_types(self):
        items = [self.win.cmb_defect_type.itemText(i) for i in range(self.win.cmb_defect_type.count())]
        self.assertEqual(len(items), 8)

    def test_compliance_widgets_exist(self):
        self.assertTrue(hasattr(self.win, "lbl_compliance_result"))
        self.assertTrue(hasattr(self.win, "lbl_compliance_details"))

    def test_retranslate_ui_does_not_crash(self):
        try:
            self.win.retranslate_ui()
        except AttributeError:
            self.fail("retranslate_ui raised AttributeError")

    def test_splitter_sizes_match(self):
        from PyQt6.QtWidgets import QSplitter
        for child in self.win.findChildren(QSplitter):
            if child.count() == 3:
                sizes = child.sizes()
                self.assertEqual(len(sizes), 3)
                return
        self.fail("Vertical QSplitter with 3 widgets not found")
