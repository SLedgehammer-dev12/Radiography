# -*- coding: utf-8 -*-
"""Standards reference scenarios (Group I).

The 2022 editions renumbered the clauses. These tests guard against the old
2013 references creeping back into the UI tooltips, the PDF appendix or the
calculation comments.
"""

import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")


def _src_text():
    chunks = []
    for root, _dirs, files in os.walk(SRC):
        for name in files:
            if name.endswith(".py"):
                with open(os.path.join(root, name), "r", encoding="utf-8") as f:
                    chunks.append(f.read())
    return "\n".join(chunks)


FORBIDDEN = [
    "Clause 6.3",
    "Madde 6.3",
    "Clause 6.4",
    "Madde 6.4",
    "Clause 5.3",
    "Madde 5.3",
    "Clause 6.8",
    "Madde 6.8",
    "Table B.1/B.2",
    "Tablo B.1/B.2",
    "Annex D",
    "Ek D",
    "ISO 17636-1:2013",
    "ISO 17636-2:2013",
    "SNR_N >= 130",
    "SNR_N: >=130",
    "Table 2 (Required minimum film system class)",
    "Clause 6.6 Table 3",
    "Madde 6.6 Tablo 3",
]


@pytest.mark.parametrize("needle", FORBIDDEN)
def test_stale_reference_absent(needle):
    text = _src_text()
    assert needle not in text, f"stale reference still present: {needle}"


REQUIRED = [
    "7.6",
    "Formula (1)",
    "7.3.1",
    "B.13",
    "B.14",
    "6.7.2",
    "7.8",
    "Annex A",
    "6.6",
    "T-274.2",
]


@pytest.mark.parametrize("needle", REQUIRED)
def test_new_reference_present(needle):
    text = _src_text()
    assert needle in text, f"expected 2022 reference missing: {needle}"


def test_translation_new_keys_present_in_both_languages():
    from src.core.translation import Translation
    t = Translation()
    for lang in ("tr", "en"):
        d = t.translations[lang]
        for key in ("detector_planar", "detector_flexible", "tt_detector_planar",
                    "tt_detector_flexible", "f_min_asme", "tt_f_min_asme",
                    "tt_ug", "tt_req_exposures", "tt_single_wire_iqi",
                    "tt_duplex_iqi"):
            assert key in d, f"{key} missing in {lang}"
            assert str(d[key]).strip(), f"{key} empty in {lang}"


def test_f_min_tooltip_references_2022_clause_7_6():
    from src.core.translation import Translation
    t = Translation()
    for lang in ("tr", "en"):
        tip = t.translations[lang]["tt_f_min"]
        assert "7.6" in tip
        assert "6.3" not in tip


def test_snr_tooltip_no_longer_hardcodes_130():
    from src.core.translation import Translation
    t = Translation()
    for lang in ("tr", "en"):
        tip = t.translations[lang]["tt_quality_target"]
        assert "130" not in tip
        assert "7.3.1" in tip


def test_report_reference_table_has_no_old_equations():
    path = os.path.join(SRC, "core", "report.py")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert "Clause 6.3, Equation (2)" not in text
    assert "ISO 17636-1:2022 Clause 7.6" in text
    assert "Tables B.13" in text
