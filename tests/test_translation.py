# -*- coding: utf-8 -*-

import unittest
from src.core.translation import Translation


class TestTranslationStructure(unittest.TestCase):
    def setUp(self):
        self.trans = Translation()

    def test_both_languages_present(self):
        self.assertIn("tr", self.trans.translations)
        self.assertIn("en", self.trans.translations)

    def test_same_keys_in_both_languages(self):
        tr_keys = set(self.trans.translations["tr"].keys())
        en_keys = set(self.trans.translations["en"].keys())
        missing_in_en = tr_keys - en_keys
        missing_in_tr = en_keys - tr_keys
        self.assertEqual(
            missing_in_en, set(),
            f"Keys in Turkish but missing in English: {missing_in_en}"
        )
        self.assertEqual(
            missing_in_tr, set(),
            f"Keys in English but missing in Turkish: {missing_in_tr}"
        )

    def test_english_contains_no_turkish_words(self):
        en = self.trans.translations["en"]
        turkish_patterns = ["Uyum", "UYGUN", "DEĞİL", "Şekil", "Çekim"]
        for key, value in en.items():
            for pattern in turkish_patterns:
                self.assertNotIn(
                    pattern, str(value),
                    f"English key '{key}' contains Turkish word '{pattern}': '{value}'"
                )

    def test_turkish_contains_expected_characters(self):
        tr = self.trans.translations["tr"]
        sample = tr.get("app_title", "")
        self.assertIn("Ğ", sample, "Turkish title should contain Turkish characters")
        self.assertIn("Ç", sample, "Turkish title should contain Turkish characters")

    def test_new_translation_keys_exist(self):
        required_keys = [
            "level3_approval_note",
            "level3_approval_placeholder",
            "dialog_ok",
            "dialog_cancel",
        ]
        for key in required_keys:
            tr_val = self.trans.translations["tr"].get(key)
            en_val = self.trans.translations["en"].get(key)
            self.assertIsNotNone(tr_val, f"Missing Turkish translation for '{key}'")
            self.assertIsNotNone(en_val, f"Missing English translation for '{key}'")
            self.assertNotEqual(tr_val, "", f"Empty Turkish translation for '{key}'")
            self.assertNotEqual(en_val, "", f"Empty English translation for '{key}'")

    def test_compliance_keys_are_clean_english(self):
        en = self.trans.translations["en"]
        self.assertEqual(en.get("compliance_result"), "Procedure Compliance Report:")
        self.assertEqual(en.get("compliant"), "COMPLIANT")
        self.assertEqual(en.get("non_compliant"), "NON-COMPLIANT")


class TestTranslationGet(unittest.TestCase):
    def setUp(self):
        self.trans = Translation()

    def test_default_language_turkish(self):
        self.assertEqual(self.trans.language, "tr")

    def test_get_returns_turkish_by_default(self):
        self.assertEqual(self.trans.get("app_title"),
                         "DOĞAL GAZ BORU HATLARI DİNAMİK RT ÇEKİM HESAPLAYICI (ISO 17636 / API 1104)")

    def test_get_returns_english_when_set(self):
        self.trans.set_language("en")
        self.assertEqual(self.trans.get("app_title"),
                         "NATURAL GAS PIPELINE DYNAMIC RT SHOT CALCULATOR (ISO 17636 / API 1104)")

    def test_get_returns_key_as_fallback(self):
        result = self.trans.get("nonexistent_key_xyz")
        self.assertEqual(result, "nonexistent_key_xyz")

    def test_get_with_args(self):
        template = self.trans.translations["tr"].get("report_saved")
        self.trans.set_language("tr")
        result = self.trans.get("report_saved", "/path/to/report.pdf")
        expected = template.format("/path/to/report.pdf")
        self.assertEqual(result, expected)

    def test_set_language_ignores_invalid(self):
        self.trans.set_language("invalid")
        self.assertEqual(self.trans.language, "tr")

    def test_set_language_english(self):
        self.trans.set_language("en")
        self.assertEqual(self.trans.language, "en")

    def test_switch_back_and_forth(self):
        self.trans.set_language("en")
        self.assertEqual(self.trans.get("steel"), "Steel")
        self.trans.set_language("tr")
        self.assertEqual(self.trans.get("steel"), "Çelik")


class TestTranslationContent(unittest.TestCase):
    def setUp(self):
        self.trans = Translation()

    def test_key_count_minimum(self):
        tr_count = len(self.trans.translations["tr"])
        en_count = len(self.trans.translations["en"])
        self.assertGreaterEqual(tr_count, 175,
                                f"Turkish has only {tr_count} keys, expected >= 175")
        self.assertGreaterEqual(en_count, 175,
                                f"English has only {en_count} keys, expected >= 175")

    def test_no_empty_values(self):
        for lang in ["tr", "en"]:
            for key, value in self.trans.translations[lang].items():
                with self.subTest(lang=lang, key=key):
                    self.assertNotEqual(value.strip() if isinstance(value, str) else value,
                                        "", f"Empty value for {lang}.{key}")

    def test_critical_geometry_keys_exist(self):
        required = ["swsi", "dwsi", "dwdi_elliptic", "dwdi_super"]
        for lang in ["tr", "en"]:
            for key in required:
                self.assertIn(key, self.trans.translations[lang],
                              f"Missing geometry key '{key}' in '{lang}'")

    def test_tab_sketch_keys_exist(self):
        required = ["tab_dynamic", "tab_standard"]
        for lang in ["tr", "en"]:
            for key in required:
                self.assertIn(key, self.trans.translations[lang],
                              f"Missing sketch tab key '{key}' in '{lang}'")


if __name__ == "__main__":
    unittest.main()
