# -*- coding: utf-8 -*-
"""Level 3 consistency scenarios (Group F).

The Level 3 reductions of ISO 17636-2:2022 Clause 7.6 (double-wall -20 %,
central projection -50 %) must update f_min AND sfd_min in the UI, in
last_calculated, in the compliance checker and in the PDF report.
"""

import os
import tempfile

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


def _configure(win, geometry="dwdi_elliptic", od=100.0, t=8.0, sfd=680.0,
               cls_index=0, std_fig=None):
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


def _unreduced_geo(win, geometry, od, t, cls, std_figure):
    return win._compute_geometry(
        od, t, float(win.txt_d.text()), float(win.txt_app_sfd.text()),
        geometry, cls, standard="iso", lvl3_settings={})


# ---------------------------------------------------------------------------
# Double-wall 20 % reduction
# ---------------------------------------------------------------------------
def test_dw_reduction_reduces_f_min_by_20_percent(win):
    _configure(win)
    win.lvl3_settings["dw_reduction"] = False
    win.update_calculations()
    base = win.last_calculated["f_min"]

    win.lvl3_settings["dw_reduction"] = True
    win.update_calculations()
    reduced = win.last_calculated["f_min"]

    assert reduced == pytest.approx(base * 0.8)
    assert win.last_calculated["lvl3_dw"] is True


def test_dw_reduction_recomputes_sfd_min(win):
    _configure(win)
    win.lvl3_settings["dw_reduction"] = True
    win.update_calculations()
    lc = win.last_calculated
    expected = max(
        lc["f_min"] + lc["b_dist"],
        lc["sdd_min"],
        lc["dwsi_physical_min"],
    )
    assert lc["sfd_min"] == pytest.approx(expected)
    # The screen label must show the same (reduced) value
    assert win.out_labels["sfd_min"][1].text() == f"{lc['sfd_min']:.1f} mm"
    assert win.out_labels["f_min"][1].text() == f"{lc['f_min_iso']:.1f} mm"


def test_dw_reduction_sfd_min_is_smaller_than_unreduced(win):
    _configure(win)
    win.lvl3_settings["dw_reduction"] = False
    win.update_calculations()
    before = win.last_calculated["sfd_min"]
    win.lvl3_settings["dw_reduction"] = True
    win.update_calculations()
    after = win.last_calculated["sfd_min"]
    assert after < before


def test_dw_reduction_makes_borderline_sfd_compliant(win):
    """Applied SFD between reduced and unreduced sfd_min: FAIL without the
    reduction, PASS with it (this was the reported claim #4)."""
    _configure(win, sfd=680.0)
    win.lvl3_settings["dw_reduction"] = False
    win.update_calculations()
    sfd_min_off = win.last_calculated["sfd_min"]

    win.lvl3_settings["dw_reduction"] = True
    win.update_calculations()
    sfd_min_on = win.last_calculated["sfd_min"]

    assert sfd_min_on < 680.0 < sfd_min_off

    win.txt_app_sfd.setText("680")
    win.update_calculations()
    win.check_procedure_compliance()
    details_on = win.lbl_compliance_details.text()
    assert "ÇEKİM MESAFESİ UYGUN DEĞİL" not in details_on

    win.lvl3_settings["dw_reduction"] = False
    win.update_calculations()
    win.check_procedure_compliance()
    details_off = win.lbl_compliance_details.text()
    assert "ÇEKİM MESAFESİ UYGUN DEĞİL" in details_off


def test_dw_reduction_label_warning_present(win):
    _configure(win)
    win.lvl3_settings["dw_reduction"] = True
    win.update_calculations()
    assert "düşürüldü" in win.txt_warnings.text()


# ---------------------------------------------------------------------------
# Central projection 50 % reduction
# ---------------------------------------------------------------------------
def test_central_projection_reduces_f_min_by_50_percent(win):
    _configure(win, geometry="swsi", od=323.9, t=10.0, sfd=600.0, std_fig="fig5")
    win.lvl3_settings["central_proj_reduction"] = False
    win.update_calculations()
    base = win.last_calculated["f_min"]
    win.lvl3_settings["central_proj_reduction"] = True
    win.update_calculations()
    assert win.last_calculated["f_min"] == pytest.approx(base * 0.5)
    assert win.last_calculated["lvl3_central"] is True


def test_central_projection_recomputes_sfd_min(win):
    _configure(win, geometry="swsi", od=323.9, t=10.0, sfd=600.0, std_fig="fig5")
    win.lvl3_settings["central_proj_reduction"] = True
    win.update_calculations()
    lc = win.last_calculated
    assert lc["sfd_min"] == pytest.approx(max(
        lc["f_min"] + lc["b_dist"], lc["sdd_min"]))
    assert win.out_labels["sfd_min"][1].text() == f"{lc['sfd_min']:.1f} mm"


# ---------------------------------------------------------------------------
# Distance compensation (sfd_comp) uses the final values
# ---------------------------------------------------------------------------
def test_sfd_comp_target_uses_dynamic_snr_and_final_sfd_min(win):
    _configure(win, geometry="swsi", od=323.9, t=10.0, sfd=150.0)
    win.lvl3_settings["sfd_comp"] = True
    win.update_calculations()
    lc = win.last_calculated
    assert lc["sfd_comp_target"] is not None
    expected = lc["required_snr"] * (lc["sfd_min"] / max(10.0, 150.0))
    assert lc["sfd_comp_target"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# PDF must match the screen (claim #5)
# ---------------------------------------------------------------------------
def _export_and_extract(win):
    import pypdf
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    from unittest.mock import patch

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    with patch.object(QFileDialog, "getSaveFileName", return_value=(tmp.name, "")), \
         patch.object(QMessageBox, "information", return_value=None), \
         patch.object(QMessageBox, "critical", return_value=None):
        win.export_pdf_report()
    reader = pypdf.PdfReader(tmp.name)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    os.unlink(tmp.name)
    return text


def test_pdf_matches_screen_with_dw_reduction(win):
    _configure(win, sfd=680.0)
    win.lvl3_settings["dw_reduction"] = True
    win.update_calculations()
    lc = win.last_calculated
    text = _export_and_extract(win)
    assert f"{lc['f_min_iso']:.1f} mm" in text
    assert f"{lc['sfd_min']:.1f} mm" in text


def test_pdf_contains_corrected_references(win):
    _configure(win, geometry="swsi", od=323.9, t=10.0, sfd=600.0)
    text = _export_and_extract(win)
    assert "7.6" in text
    assert "Formula (1)" in text or "Formül (1)" in text
    assert "Clause 6.3" not in text
    assert "Madde 6.3" not in text
