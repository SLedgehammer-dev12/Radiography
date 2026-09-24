# -*- coding: utf-8 -*-
"""PDF report consistency scenarios (Group G).

The PDF must render the same f_min / sfd_min / Ug values as the screen, use the
2022 standard references, support both Translation objects and plain dicts
(mobile) and never raise (it returns False instead).
"""

import os
import tempfile
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def win(qapp):
    from PyQt6.QtCore import QSettings
    QSettings("Radiography", "Radiography").clear()
    from src.ui.main_window import MainWindow
    w = MainWindow()
    yield w
    try:
        w.canvas.figure.clf()
        w.std_canvas.figure.clf()
    except Exception:
        pass
    w.close()
    w.deleteLater()


def _export_and_extract(win):
    import pypdf
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    with patch.object(QFileDialog, "getSaveFileName", return_value=(tmp.name, "")), \
         patch.object(QMessageBox, "information", return_value=None), \
         patch.object(QMessageBox, "critical", return_value=None):
        win.export_pdf_report()
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(tmp.name).pages)
    os.unlink(tmp.name)
    return text


def _configure(win, planar=True, geometry="swsi", od=323.9, t=10.0, sfd=700.0,
               std_fig="fig6"):
    win.rad_detector_flat.setChecked(planar)
    win.rad_detector_curved.setChecked(not planar)
    win.txt_custom_od.setText(str(od))
    win.txt_custom_t.setText(str(t))
    win.txt_app_sfd.setText(str(sfd))
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData(geometry))
    idx = win.cmb_std_figure.findData(std_fig)
    if idx >= 0:
        win.cmb_std_figure.setCurrentIndex(idx)
    win.update_calculations()


def test_pdf_planar_matches_screen(win):
    _configure(win, planar=True)
    lc = win.last_calculated
    text = _export_and_extract(win)
    assert f"{lc['f_min_iso']:.1f} mm" in text
    assert f"{lc['sfd_min']:.1f} mm" in text
    assert f"{lc['ug']:.3f} mm" in text


def test_pdf_flexible_matches_screen(win):
    _configure(win, planar=False)
    lc = win.last_calculated
    text = _export_and_extract(win)
    assert f"{lc['f_min_iso']:.1f} mm" in text
    assert f"{lc['sfd_min']:.1f} mm" in text


def test_pdf_contains_ug_row(win):
    _configure(win)
    text = _export_and_extract(win)
    assert "Geometrik" in text or "Geometric" in text


# ---------------------------------------------------------------------------
# Direct generator: dict lang object (mobile path) and robustness
# ---------------------------------------------------------------------------
def _make_inputs():
    return {
        "material_text": "Steel", "class_text": "Class B", "od": 114.3, "t": 8.0,
        "cap": 3.0, "weld_width": 8.0, "d": 2.0, "sfd": 600.0,
        "output_val": 5.0, "base_e": 3.0, "speed": "C5", "tech": "analog",
        "tech_text": "Analog", "source": "x_ray", "source_text": "X-Ray",
        "geometry": "swsi", "geometry_text": "SWSI", "standard": "iso",
        "report_info": {}, "input_kv": 120.0, "overlap": 10.0,
        "iqi_type": "wire", "snr_location": "weld",
    }


def _make_outputs(**overrides):
    outputs = {
        "w_nom": 8.0, "w_eff": 11.0, "u_max": 160.0, "f_min": 100.0,
        "f_min_asme": None, "sfd_min": 110.0, "ug": 0.03,
        "exposures": 1, "exposures_panel": None, "exposures_applied": None,
        "exposures_check": True, "single_wire_iqi": "W 13 (0.200 mm)",
        "duplex_iqi": "N/A", "asme_iqi": "N/A", "barrier_distance": "N/A",
        "quality_target": ">= 2.3", "calc_time": "2 min 0 sec",
        "base_multiplier": 1.0, "detector_quality": "C4 Film",
        "filter_recommendation": "Pb 0.02-0.15 mm",
    }
    outputs.update(overrides)
    return outputs


@pytest.mark.parametrize("lang,expected", [("en", "NOT OK"), ("tr", "UYGUN DEĞİL")])
def test_dict_lang_object_renders_correct_language(lang, expected):
    import pypdf
    from src.core.report import PDFReportGenerator
    from src.core.translation import Translation

    trans = Translation()
    trans.set_language(lang)
    lang_dict = dict(trans.translations[lang])
    lang_dict["language"] = lang

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    ok = PDFReportGenerator().generate_report(
        tmp.name, _make_inputs(), _make_outputs(exposures_check=False),
        ["test warning"], None, False, None, lang_dict)
    assert ok is True
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(tmp.name).pages)
    os.unlink(tmp.name)
    assert expected in text


def test_report_never_raises_on_bad_numeric_values():
    from src.core.report import PDFReportGenerator
    from src.core.translation import Translation

    trans = Translation()
    lang_dict = dict(trans.translations["tr"])
    lang_dict["language"] = "tr"

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    ok = PDFReportGenerator().generate_report(
        tmp.name, _make_inputs(), _make_outputs(w_nom="not-a-number"),
        [], None, False, None, lang_dict)
    assert ok is False
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


def test_report_filters_blank_warnings():
    import pypdf
    from src.core.report import PDFReportGenerator
    from src.core.translation import Translation

    trans = Translation()
    lang_dict = dict(trans.translations["en"])
    lang_dict["language"] = "en"
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    ok = PDFReportGenerator().generate_report(
        tmp.name, _make_inputs(), _make_outputs(),
        ["", "  ", "real warning"], None, False, None, lang_dict)
    assert ok is True
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(tmp.name).pages)
    os.unlink(tmp.name)
    assert "real warning" in text
