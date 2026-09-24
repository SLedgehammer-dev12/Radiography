# -*- coding: utf-8 -*-
"""ASME Sec V Art 2 geometry scenarios (Group H).

ASME T-274.2 limits the geometric unsharpness (Ug = d·b/f), so the minimum
source-to-object distance is f_min = d·b/Ug_limit(t). The tool must show both
the ISO f_min and the ASME-derived f_min and check SFD against the ASME value
when ASME is selected. The Ug denominator must be f = SFD − b.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.core.calculator import RTCalculator


@pytest.fixture(scope="module")
def calc():
    return RTCalculator()


ASME_CASES = [
    # (d, b, t, expected_limit)
    (2.0, 8.0, 8.0, 0.51),
    (2.0, 25.0, 25.0, 0.51),
    (2.0, 60.0, 60.0, 0.76),
    (4.0, 90.0, 90.0, 1.02),
    (2.0, 150.0, 120.0, 1.78),
    (3.0, 200.0, 150.0, 1.78),
]


@pytest.mark.parametrize("d,b,t,limit", ASME_CASES)
def test_asme_f_min_from_ug_limit(calc, d, b, t, limit):
    assert calc.calculate_asme_f_min(d, b, t) == pytest.approx(d * b / limit)


@pytest.mark.parametrize("d,b,t,limit", ASME_CASES)
def test_asme_ug_at_asme_f_min_is_exactly_the_limit(calc, d, b, t, limit):
    f = calc.calculate_asme_f_min(d, b, t)
    sfd = f + b
    assert calc.calculate_geometric_unsharpness_from_sfd(d, b, sfd) == pytest.approx(limit)


# ---------------------------------------------------------------------------
# Desktop UI
# ---------------------------------------------------------------------------
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


def _configure(win, standard="asme", geometry="swsi", od=600.0, t=120.0,
               sfd=200.0, cls_index=0, std_fig="fig6"):
    win.cmb_standard.setCurrentIndex(win.cmb_standard.findData(standard))
    win.txt_custom_od.setText(str(od))
    win.txt_custom_t.setText(str(t))
    win.txt_app_sfd.setText(str(sfd))
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData(geometry))
    win.cmb_class.setCurrentIndex(cls_index)
    if std_fig is not None:
        idx = win.cmb_std_figure.findData(std_fig)
        if idx >= 0:
            win.cmb_std_figure.setCurrentIndex(idx)
    win.update_calculations()


def test_asme_row_visible_and_value(win):
    _configure(win)
    lc = win.last_calculated
    assert lc["f_min_asme"] is not None
    expected = win.calc.calculate_asme_f_min(
        float(win.txt_d.text()), lc["b_dist"], 120.0)
    assert lc["f_min_asme"] == pytest.approx(expected)
    assert win.out_rows["f_min_asme"].isVisible() or not win.isVisible()
    assert win.out_labels["f_min_asme"][1].text() == f"{expected:.1f} mm"


def test_asme_sfd_min_uses_asme_value(win):
    _configure(win)
    lc = win.last_calculated
    assert lc["sfd_min"] == pytest.approx(max(
        lc["f_min_asme"] + lc["b_dist"], lc["sdd_min"]))


def test_iso_mode_hides_asme_row(win):
    _configure(win, standard="iso")
    assert win.last_calculated["f_min_asme"] is None
    assert win.out_labels["f_min_asme"][1].text() == "N/A"
    assert not win.out_rows["f_min_asme"].isVisible()


def test_asme_ug_check_uses_correct_denominator(win):
    """t=120, planar b=137, SFD=200: old formula gave Ug=1.37 (pass), correct
    formula gives Ug=4.35 (fail)."""
    _configure(win)
    lc = win.last_calculated
    assert lc["b_dist"] == pytest.approx(137.0)
    expected_ug = 2.0 * 137.0 / (200.0 - 137.0)
    assert lc["ug"] == pytest.approx(expected_ug)
    assert lc["ug"] > lc["ug_limit"]
    assert "ASME" in win.txt_warnings.text()


def test_asme_ug_compliance_fails_with_corrected_ug(win):
    _configure(win)
    win.check_procedure_compliance()
    details = win.lbl_compliance_details.text()
    assert "GEOMETRİK BULANIKLIK (Ug) YÜKSEK" in details


def test_asme_reference_appears_in_pdf(win):
    import tempfile
    import pypdf
    from unittest.mock import patch
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    _configure(win)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    with patch.object(QFileDialog, "getSaveFileName", return_value=(tmp.name, "")), \
         patch.object(QMessageBox, "information", return_value=None), \
         patch.object(QMessageBox, "critical", return_value=None):
        win.export_pdf_report()
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(tmp.name).pages)
    os.unlink(tmp.name)
    assert "ASME" in text
    assert "T-274.2" in text
