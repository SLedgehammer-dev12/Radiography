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
        # Deterministic tests: start from a clean, empty persisted state.
        from PyQt6.QtCore import QSettings
        QSettings("Radiography", "Radiography").clear()
        from src.ui.main_window import MainWindow
        self.win = MainWindow()

    def tearDown(self):
        import gc
        try:
            self.win.canvas.figure.clf()
            self.win.std_canvas.figure.clf()
        except Exception:
            pass
        self.win.close()
        self.win.deleteLater()
        gc.collect()

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

    def test_std_figure_input_combo_populated(self):
        # The input-panel "Standart ISO Şekli" combo must be populated and in
        # sync with the standard sketch tab combo.
        combo = self.win.cmb_std_figure
        tab = self.win.cmb_std_figure_tab
        self.assertGreater(combo.count(), 0, "Input panel std figure combo is empty")
        self.assertGreater(tab.count(), 0, "Standard tab std figure combo is empty")
        self.assertEqual(combo.count(), tab.count())
        for i in range(combo.count()):
            self.assertEqual(combo.itemText(i), tab.itemText(i))
            self.assertEqual(combo.itemData(i), tab.itemData(i))
        self.assertEqual(combo.currentData(), tab.currentData())

    def test_std_figure_sync_on_geometry_change(self):
        # Changing geometry in the input panel must update the tab combo too.
        combo = self.win.cmb_std_figure
        tab = self.win.cmb_std_figure_tab
        # Switch to SWSI geometry (index 1)
        idx_swsi = self.win.cmb_geometry.findText("SWSI")
        if idx_swsi < 0:
            idx_swsi = 1
        self.win.cmb_geometry.setCurrentIndex(idx_swsi)
        self.win.update_std_figure_list()
        self.assertGreater(combo.count(), 0)
        self.assertEqual(combo.count(), tab.count())
        self.assertEqual(combo.currentData(), tab.currentData())

    def test_geometry_override_fields_exist(self):
        self.assertTrue(hasattr(self.win, "txt_f_source"))
        self.assertTrue(hasattr(self.win, "txt_b_object"))
        self.assertTrue(hasattr(self.win, "lbl_f_source"))
        self.assertTrue(hasattr(self.win, "lbl_b_object"))

    def test_base_multiplier_default_is_one(self):
        self.assertEqual(self.win.get_base_multiplier(), 1.0)
        self.win.txt_base_multiplier.setText("1.5")
        self.assertEqual(self.win.get_base_multiplier(), 1.5)
        self.win.txt_base_multiplier.setText("0")
        self.assertEqual(self.win.get_base_multiplier(), 1.0)
        self.win.txt_base_multiplier.setText("250.0")
        self.assertEqual(self.win.get_base_multiplier(), 100.0)
        self.win.txt_base_multiplier.setText("")
        self.assertEqual(self.win.get_base_multiplier(), 1.0)
        self.win.txt_base_multiplier.setText("1.0")

    def test_base_e_label_updates_with_source(self):
        # X-Ray -> mA·min/m²
        self.win.cmb_source.setCurrentIndex(0)
        self.win.on_source_changed()
        self.assertIn("mA·min/m²", self.win.lbl_base_e.text())
        self.assertIn("Pozlama Tablosu Sabiti", self.win.lbl_base_e.text())
        # Ir-192 -> Ci·min/m²
        self.win.cmb_source.setCurrentIndex(1)
        self.win.on_source_changed()
        self.assertIn("Ci·min/m²", self.win.lbl_base_e.text())

    def test_base_e_hidden_when_chart_selected(self):
        # Physics model -> E visible
        self.win.cmb_chart_source.setCurrentIndex(0)
        self.win.on_chart_source_changed()
        self.assertFalse(self.win.txt_base_e.isHidden())
        # Chart selected -> E hidden (chart path ignores E)
        chart_idx = self.win.cmb_chart_source.findData("AA400")
        if chart_idx >= 0:
            self.win.cmb_chart_source.setCurrentIndex(chart_idx)
            self.win.on_chart_source_changed()
            self.assertTrue(self.win.txt_base_e.isHidden())
        # Back to model -> E visible again
        self.win.cmb_chart_source.setCurrentIndex(0)
        self.win.on_chart_source_changed()
        self.assertFalse(self.win.txt_base_e.isHidden())

    def test_base_multiplier_label_renamed(self):
        self.assertEqual(self.win.lbl_base_multiplier.text(), "Saha Düzeltme Çarpanı (F):")

    def test_weld_width_field_exists(self):
        self.assertTrue(hasattr(self.win, "txt_weld_width"))
        self.assertTrue(hasattr(self.win, "lbl_weld_width"))
        self.assertEqual(self.win.lbl_weld_width.text(), "Kaynak Genişliği (mm):")

    def test_weld_width_visibility_dwdi_only(self):
        # force dwsi explicitly (restored settings may carry another geometry)
        self.win.cmb_geometry.setCurrentIndex(0)  # dwsi
        self.win.update_calculations()
        self.assertTrue(self.win.txt_weld_width.isHidden())
        # dwdi_elliptic with small pipe -> visible
        self.win.txt_custom_od.setText("60")
        self.win.cmb_geometry.setCurrentIndex(2)  # dwdi_elliptic
        self.win.update_calculations()
        self.assertFalse(self.win.txt_weld_width.isHidden())
        # swsi -> hidden again
        self.win.cmb_geometry.setCurrentIndex(1)  # swsi
        self.win.update_calculations()
        self.assertTrue(self.win.txt_weld_width.isHidden())

    def test_dwdi_elliptical_exposures_dynamic(self):
        self.win.txt_custom_od.setText("60")   # small -> avoids OD>100 DWDI force
        self.win.cmb_geometry.setCurrentIndex(2)  # dwdi_elliptic
        # t/De < 0.12 -> 2 exposures
        self.win.txt_custom_od.setText("100")
        self.win.txt_custom_t.setText("8")
        self.win.update_calculations()
        self.assertEqual(self.win.out_labels["req_exposures"][1].text(), "2")
        # t/De >= 0.12 -> 3 exposures
        self.win.txt_custom_od.setText("50")
        self.win.txt_custom_t.setText("8")
        self.win.update_calculations()
        self.assertEqual(self.win.out_labels["req_exposures"][1].text(), "3")

    def test_dwdi_warnings(self):
        self.win.cmb_geometry.setCurrentIndex(2)  # dwdi_elliptic
        self.win.txt_custom_od.setText("60")
        self.win.txt_custom_t.setText("10")
        self.win.txt_weld_width.setText("20")
        self.win.update_calculations()
        text = self.win.txt_warnings.text()
        self.assertIn("t <= 8", text)          # t > 8 warning
        self.assertIn("De/4", text)            # weld width > De/4 warning
        self.assertIn("3 görüntü", text)       # t/De >= 0.12 info (t/De = 0.167)

    def test_standard_selector_and_asme_iqi(self):
        self.assertTrue(hasattr(self.win, "cmb_standard"))
        # ASME Sec V Art 2 -> ASTM E747 wire IQI output (default IQI type = wire)
        self.win.cmb_standard.setCurrentIndex(1)
        self.win.update_calculations()
        text = self.win.out_labels["asme_iqi"][1].text()
        self.assertNotEqual(text, "N/A")
        self.assertIn("E747", text)
        # back to ISO -> N/A
        self.win.cmb_standard.setCurrentIndex(0)
        self.win.update_calculations()
        self.assertEqual(self.win.out_labels["asme_iqi"][1].text(), "N/A")

    def test_barrier_distance_output(self):
        self.win.cmb_source.setCurrentIndex(1)  # Ir-192
        self.win.txt_app_activity.setText("40.0")
        self.win.update_calculations()
        text = self.win.out_labels["barrier_distance"][1].text()
        self.assertIn("Kontrollü", text)
        self.assertIn("Gözetimli", text)
        # X-Ray -> N/A (no gamma barrier)
        self.win.cmb_source.setCurrentIndex(0)
        self.win.update_calculations()
        self.assertEqual(self.win.out_labels["barrier_distance"][1].text(), "N/A")

    def test_preset_roundtrip(self):
        self.win.txt_custom_od.setText("60.0")
        self.win.cmb_geometry.setCurrentIndex(2)  # dwdi_elliptic
        self.win.txt_report_no.setText("RT-2026-001")
        state = self.win.collect_form_state()
        self.win.txt_custom_od.setText("114.3")
        self.win.apply_form_state(state)
        self.assertEqual(self.win.txt_custom_od.text(), "60.0")
        self.assertEqual(self.win.txt_report_no.text(), "RT-2026-001")

    def test_units_toggle(self):
        self.win.txt_custom_od.setText("114.3")
        self.assertAlmostEqual(self.win.get_form_values()[0], 114.3)
        self.win.toggle_units()  # -> inch
        self.assertEqual(self.win.btn_units.text(), "inç")
        self.assertAlmostEqual(float(self.win.txt_custom_od.text()), 114.3 / 25.4, places=2)
        self.assertAlmostEqual(self.win.get_form_values()[0], 114.3)  # internal value in mm
        self.win.toggle_units()  # -> back to mm
        self.assertEqual(self.win.btn_units.text(), "mm")
        self.assertAlmostEqual(float(self.win.txt_custom_od.text()), 114.3, places=2)
        self.assertAlmostEqual(self.win.get_form_values()[0], 114.3)

    def test_named_preset_application(self):
        self.win.apply_named_preset("ASME VIII 25 mm SWSI Co-60")
        self.win.update_calculations()
        vals = self.win.get_form_values()
        self.assertAlmostEqual(vals[1], 25.0)            # wall thickness
        self.assertEqual(self.win.cmb_standard.currentData(), "asme")
        self.assertEqual(self.win.cmb_geometry.currentData(), "swsi")
        self.assertEqual(self.win.cmb_source.currentData(), "isotope_co60")

    def test_defect_standard_selector_present(self):
        self.assertTrue(hasattr(self.win, "cmb_defect_standard"))
        self.assertTrue(hasattr(self.win, "cmb_b31_service"))
        self.assertTrue(hasattr(self.win, "cmb_viii_mode"))
        # ASME B31.3 selected -> service combo visible
        idx = self.win.cmb_defect_standard.findData("b31_3")
        self.assertGreaterEqual(idx, 0)
        self.win.cmb_defect_standard.setCurrentIndex(idx)
        self.win._on_defect_standard_changed()
        self.assertFalse(self.win.cmb_b31_service.isHidden())
        self.assertTrue(self.win.cmb_quality_level.isHidden())

    def test_geometry_override_parsing(self):
        f, b = self.win.get_geometry_override_inputs()
        self.assertIsNone(f)
        self.assertIsNone(b)
        self.win.txt_f_source.setText("700")
        self.win.txt_b_object.setText("20")
        f, b = self.win.get_geometry_override_inputs()
        self.assertEqual(f, 700.0)
        self.assertEqual(b, 20.0)
        self.win.txt_f_source.setText("0")
        f, b = self.win.get_geometry_override_inputs()
        self.assertIsNone(f)
        self.win.txt_f_source.setText("")
        self.win.txt_b_object.setText("")

    def test_draw_setup_respects_light_theme(self):
        # draw_setup must honour the theme instead of forcing dark colours
        self.win.rad_digital.setChecked(True)
        self.win.is_dark_theme = False
        self.win.canvas.draw_setup(50.0, 5.0, 3.0, "dwsi", 600.0, self.win.trans, is_dark=False)
        bg = self.win.canvas.axes.get_facecolor()
        self.assertGreater(sum(bg[:3]), 2.0, f"Expected light background, got {bg}")

    def test_inch_mode_standard_pipe_no_double_conversion(self):
        # Regression: standard ASME pipe values are mm; toggling inch mode must
        # NOT multiply them by 25.4 again (was 114.3 -> 2903 mm).
        idx = self.win.cmb_od.findData('4" (NPS 4)')
        self.assertGreaterEqual(idx, 0)
        self.win.cmb_od.setCurrentIndex(idx)
        self.win.populate_standard_thicknesses()
        # Select the SCH 40 / STD wall (6.02 mm) for 4" NPS
        t_idx = None
        for i in range(self.win.cmb_t.count()):
            if self.win.cmb_t.itemData(i) == 6.02:
                t_idx = i
                break
        self.assertIsNotNone(t_idx)
        self.win.cmb_t.setCurrentIndex(t_idx)

        # Activate inch mode (no custom entries => combo values are authoritative)
        if not self.win.use_inch:
            self.win.toggle_units()
        self.assertTrue(self.win.use_inch)
        od, t, cap, *_ = self.win.get_form_values()
        self.assertAlmostEqual(od, 114.3, places=2)
        self.assertAlmostEqual(t, 6.02, places=2)
        self.win.toggle_units()  # restore mm

    def test_inch_mode_custom_values_are_converted(self):
        # Custom entries are typed in the current display unit; in inch mode a
        # 4.5" OD / 0.25" wall must be converted to mm by get_form_values.
        self.win.toggle_units()  # -> inch
        self.win.txt_custom_od.setText("4.5")
        self.win.txt_custom_t.setText("0.25")
        od, t, *_ = self.win.get_form_values()
        self.assertAlmostEqual(od, 4.5 * 25.4, places=1)
        self.assertAlmostEqual(t, 0.25 * 25.4, places=1)
        self.win.toggle_units()  # restore mm
        self.win.txt_custom_od.setText("")
        self.win.txt_custom_t.setText("")

    def test_defect_fields_participate_in_unit_toggle(self):
        # Defect length/width/accum must be converted to mm in inch mode so a
        # 1.0" indication is NOT evaluated as 1.0 mm.
        self.assertIn("txt_defect_length", self.win._MM_FIELDS)
        self.assertIn("txt_defect_width", self.win._MM_FIELDS)
        self.assertIn("txt_defect_accum", self.win._MM_FIELDS)
        self.win.toggle_units()  # -> inch
        self.assertAlmostEqual(self.win._to_mm(1.0), 25.4, places=2)
        self.win.toggle_units()  # restore

    def test_open_decay_dialog_does_not_crash_on_empty_date(self):
        # Regression: opening the isotope decay tool with an empty calibration
        # date previously raised in the slot and aborted the app (PyQt6 qFatal).
        # We open the modal dialog and auto-close it via a timer.
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication

        idx = self.win.cmb_source.findData("isotope_ir192")
        self.assertGreaterEqual(idx, 0)
        self.win.cmb_source.setCurrentIndex(idx)

        def _close():
            mw = QApplication.activeModalWidget()
            if mw is not None:
                mw.reject()

        QTimer.singleShot(100, _close)
        self.win.open_decay_dialog()  # must return (no abort)
        self.assertTrue(True)

    def test_export_pdf_with_special_chars_in_report_fields(self):
        # Regression: ReportLab Paragraph parses XML-like markup, so unescaped
        # '&', '<', '>' in user report fields crashed PDF export (ValueError ->
        # PyQt6 slot abort). Escaping must make it save successfully.
        import tempfile, os
        from unittest import mock

        tmp = os.path.join(tempfile.gettempdir(), "rt_test_special.pdf")
        if os.path.exists(tmp):
            os.remove(tmp)

        from src.ui.main_window import QFileDialog, QMessageBox
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               return_value=(tmp, "PDF Files (*.pdf)")):
            with mock.patch.object(QMessageBox, "information"):
                with mock.patch.object(QMessageBox, "critical"):
                    self.win.txt_report_no.setText('No & <b>123')
                    self.win.txt_project.setText('Ğü & <x>')
                    self.win.txt_lvl2_name.setText('Seviye <b>II')
                    self.win.export_pdf_report()
        try:
            self.assertTrue(os.path.exists(tmp), "PDF must be generated")
            self.assertGreater(os.path.getsize(tmp), 0)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def test_update_check_handles_null_release_notes(self):
        # Regression: GitHub API can return release_notes = None; slicing it
        # (result.get(...)[:500]) previously raised TypeError inside the slot
        # and aborted the app. Must not raise.
        from unittest import mock
        from src.ui.main_window import QMessageBox

        result = {"available": True, "version": "9.9.9",
                  "release_notes": None, "assets": []}
        with mock.patch.object(QMessageBox, "question",
                               return_value=QMessageBox.StandardButton.No):
            self.win._on_update_check_result(result, silent=False)

        result_err = {"available": False, "error": "certificate verify failed", "data": None}
        with mock.patch.object(QMessageBox, "warning"):
            self.win._on_update_check_result(result_err, silent=False)
        self.win.canvas.draw_setup(50.0, 5.0, 3.0, "dwsi", 600.0, self.win.trans, is_dark=True)
        bg = self.win.canvas.axes.get_facecolor()
        self.assertLess(sum(bg[:3]), 1.0, f"Expected dark background, got {bg}")

    def test_toggle_theme_changes_setup_canvas(self):
        self.win.is_dark_theme = True
        self.win.toggle_theme()
        self.assertFalse(self.win.is_dark_theme)
        bg = self.win.canvas.axes.get_facecolor()
        self.assertGreater(sum(bg[:3]), 2.0, f"Light theme should yield light background, got {bg}")
        self.win.toggle_theme()
        self.assertTrue(self.win.is_dark_theme)

    def test_dynamic_visibility_analog_vs_digital(self):
        # Select Analog
        self.win.rad_analog.setChecked(True)
        self.assertFalse(self.win.lbl_film_class_used.isHidden())
        self.assertFalse(self.win.cmb_film_class_used.isHidden())
        self.assertTrue(self.win.lbl_detector_type.isHidden())
        self.assertTrue(self.win.cmb_detector_type.isHidden())
        self.assertTrue(self.win.lbl_app_srb.isHidden())
        self.assertTrue(self.win.lbl_app_duplex.isHidden())
        self.assertFalse(self.win.lbl_film_size.isHidden())
        self.assertFalse(self.win.cmb_film_size.isHidden())
        self.assertTrue(self.win.lbl_panel_width.isHidden())

        # Select Digital
        self.win.rad_digital.setChecked(True)
        self.assertTrue(self.win.lbl_film_class_used.isHidden())
        self.assertTrue(self.win.cmb_film_class_used.isHidden())
        self.assertFalse(self.win.lbl_detector_type.isHidden())
        self.assertFalse(self.win.cmb_detector_type.isHidden())
        self.assertFalse(self.win.lbl_app_srb.isHidden())
        self.assertFalse(self.win.lbl_app_duplex.isHidden())
        self.assertTrue(self.win.lbl_film_size.isHidden())
        self.assertTrue(self.win.cmb_film_size.isHidden())
        self.assertFalse(self.win.lbl_panel_width.isHidden())

    def test_dynamic_visibility_xray_vs_isotope(self):
        # Select X-Ray (index 0)
        self.win.cmb_source.setCurrentIndex(0)
        self.assertFalse(self.win.lbl_output.isHidden())
        self.assertFalse(self.win.txt_output.isHidden())
        self.assertFalse(self.win.lbl_app_kv.isHidden())
        self.assertFalse(self.win.txt_app_kv.isHidden())
        self.assertTrue(self.win.lbl_app_activity.isHidden())
        self.assertTrue(self.win.act_widget.isHidden())

        # Select Isotope Ir-192 (index 1)
        self.win.cmb_source.setCurrentIndex(1)
        self.assertTrue(self.win.lbl_output.isHidden())
        self.assertTrue(self.win.txt_output.isHidden())
        self.assertTrue(self.win.lbl_app_kv.isHidden())
        self.assertTrue(self.win.txt_app_kv.isHidden())
        self.assertFalse(self.win.lbl_app_activity.isHidden())
        self.assertFalse(self.win.act_widget.isHidden())

    def test_activity_unit_conversion(self):
        self.win.cmb_source.setCurrentIndex(1) # Isotope
        self.win.txt_app_activity.setText("40.0")
        self.win.cmb_activity_unit.setCurrentText("Ci")
        vals = self.win.get_form_values()
        # output_val should be 40.0 in Ci
        self.assertAlmostEqual(vals[6], 40.0, places=2)

        # Switch to GBq
        self.win.cmb_activity_unit.setCurrentIndex(1) # GBq
        self.assertAlmostEqual(float(self.win.txt_app_activity.text()), 1480.0, delta=1.0)
        vals_gbq = self.win.get_form_values()
        # output_val converted back to Ci for internal calculation
        self.assertAlmostEqual(vals_gbq[6], 40.0, places=2)

    def test_dynamic_output_visibility_analog_vs_digital(self):
        # Select Analog
        self.win.rad_analog.setChecked(True)
        self.assertTrue(self.win.out_rows["duplex_iqi"].isHidden())
        self.assertTrue(self.win.out_rows["exposures_panel"].isHidden())
        self.assertFalse(self.win.out_rows["exposures_applied"].isHidden())
        self.assertFalse(self.win.out_rows["exposures_check"].isHidden())

        # Select Digital
        self.win.rad_digital.setChecked(True)
        self.assertFalse(self.win.out_rows["duplex_iqi"].isHidden())
        self.assertFalse(self.win.out_rows["exposures_panel"].isHidden())
        self.assertFalse(self.win.out_rows["exposures_applied"].isHidden())
        self.assertFalse(self.win.out_rows["exposures_check"].isHidden())

    def test_dynamic_output_visibility_xray_vs_isotope(self):
        # Select X-Ray
        self.win.cmb_source.setCurrentIndex(0)
        self.assertFalse(self.win.out_rows["u_max"].isHidden())

        # Select Isotope
        self.win.cmb_source.setCurrentIndex(1)
        self.assertTrue(self.win.out_rows["u_max"].isHidden())

    def test_analog_applied_exposures_procedure_check(self):
        # Set up analog DWSI
        self.win.rad_analog.setChecked(True)
        self.win.cmb_source.setCurrentIndex(0) # X-Ray
        self.win.cmb_geometry.setCurrentIndex(0) # DWSI

        # Set applied exposures to 1 (which is less than required for DWSI)
        self.win.txt_app_exposures.setText("1")
        self.win.check_procedure_compliance()
        self.assertIn("DEĞİL", self.win.lbl_compliance_result.text())

        # Set applied exposures to 12 (which is >= required 10)
        self.win.txt_app_exposures.setText("12")
        self.win.check_procedure_compliance()
        # Exposure check should pass
        res_text = self.win.lbl_compliance_details.text()
        self.assertIn("Poz Sayısı Uygun", res_text)
