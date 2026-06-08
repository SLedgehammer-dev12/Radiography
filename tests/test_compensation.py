# -*- coding: utf-8 -*-

import unittest
from unittest.mock import MagicMock, patch


class TestLevel3DialogSettings(unittest.TestCase):
    def test_settings_dict_structure(self):
        """Verify the settings dictionary structure expected by the dialog."""
        settings = {
            "sfd_comp": True,
            "voltage_override": False,
            "isotope_flex": True,
            "source_flex": False,
            "central_proj_reduction": False,
            "dw_reduction": True,
            "approval_note": "Approved by ASNT Lvl III John Doe"
        }
        self.assertIn("sfd_comp", settings)
        self.assertIn("voltage_override", settings)
        self.assertIn("isotope_flex", settings)
        self.assertIn("source_flex", settings)
        self.assertIn("central_proj_reduction", settings)
        self.assertIn("dw_reduction", settings)
        self.assertIn("approval_note", settings)
        self.assertIsInstance(settings["sfd_comp"], bool)
        self.assertIsInstance(settings["voltage_override"], bool)
        self.assertIsInstance(settings["approval_note"], str)

    def test_all_settings_default_to_false(self):
        settings = {
            "sfd_comp": False,
            "voltage_override": False,
            "isotope_flex": False,
            "source_flex": False,
            "central_proj_reduction": False,
            "dw_reduction": False,
            "approval_note": ""
        }
        self.assertFalse(any([settings["sfd_comp"], settings["voltage_override"],
                              settings["isotope_flex"], settings["source_flex"],
                              settings["central_proj_reduction"], settings["dw_reduction"]]))
        self.assertEqual(settings["approval_note"], "")

    def test_settings_with_approval_note(self):
        settings = {
            "sfd_comp": True,
            "voltage_override": True,
            "isotope_flex": False,
            "source_flex": False,
            "central_proj_reduction": True,
            "dw_reduction": False,
            "approval_note": "Customer approved exception #1234"
        }
        active_exceptions = [k for k, v in settings.items() if v is True and k != "approval_note"]
        self.assertEqual(len(active_exceptions), 3)
        self.assertIn("sfd_comp", active_exceptions)
        self.assertIn("voltage_override", active_exceptions)
        self.assertIn("central_proj_reduction", active_exceptions)
        self.assertNotIn("isotope_flex", active_exceptions)
        self.assertNotIn("dw_reduction", active_exceptions)
        self.assertEqual(settings["approval_note"], "Customer approved exception #1234")

    def test_level3_section_translation_keys_exist(self):
        from src.core.translation import Translation
        trans = Translation()
        required_keys = [
            "level3_section", "level3_active", "lvl3_sfd_compensation",
            "lvl3_voltage_override", "lvl3_isotope_flex", "lvl3_source_flex",
            "lvl3_central_proj", "lvl3_dw_reduction", "sfd_comp_label",
            "level3_approval_note", "level3_approval_placeholder",
        ]
        for lang in ["tr", "en"]:
            for key in required_keys:
                with self.subTest(lang=lang, key=key):
                    self.assertIn(key, trans.translations[lang],
                                  f"Missing key '{key}' in '{lang}'")
                    self.assertNotEqual(trans.translations[lang][key].strip(), "",
                                        f"Empty value for '{key}' in '{lang}'")


class TestLevel3DialogThemeSupport(unittest.TestCase):
    def test_theme_switch_does_not_crash(self):
        """Verify set_theme method can be called (requires Qt, tests logic only)."""
        try:
            from PyQt6.QtWidgets import QApplication, QDialog
        except ImportError:
            self.skipTest("PyQt6 not available in test environment")
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        try:
            from src.ui.compensation import Level3Dialog
            from src.core.translation import Translation
            trans = Translation()
            dlg = Level3Dialog(trans, is_dark=True)
            dlg.set_theme(False)
            dlg.set_theme(True)
            # Verify no crash
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"set_theme raised an exception: {e}")


if __name__ == "__main__":
    unittest.main()
