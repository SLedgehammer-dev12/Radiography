# -*- coding: utf-8 -*-
"""ISO 17636-1 (analog) film model scenarios.

Analog radiography has no planar-detector Formulae (8)/(9)/(13) - those exist
only in ISO 17636-2 (digital). Regardless of the (hidden) detector-shape radio
state, analog must use:
    b = t  (SWSI/DWSI),  b = De (DWDI)
    f_min = C * d * b_eff^(2/3)   (C = 7.5 class A / 15 class B)
"""

import os

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


def _configure_analog(win, geometry="dwsi", od=219.1, t=6.02, cls_index=0,
                      sfd=600.0, planar=None):
    if planar is not None:
        win.rad_detector_flat.setChecked(planar)
        win.rad_detector_curved.setChecked(not planar)
    win.rad_analog.setChecked(True)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData(geometry))
    win.cmb_class.setCurrentIndex(cls_index)
    win.txt_custom_od.setText(str(od))
    win.txt_custom_t.setText(str(t))
    win.txt_app_sfd.setText(str(sfd))
    win.update_calculations()


def _expected_film_f_min(t, cls, d=2.0):
    c = 7.5 if cls == "class_a" else 15.0
    return c * d * t ** (2.0 / 3.0)


def test_analog_dwsi_uses_film_model_by_default(win):
    """Default (hidden) radio is 'Planar' but analog must still use b = t."""
    assert win.rad_detector_flat.isChecked()
    _configure_analog(win, geometry="dwsi", t=6.02, cls_index=0)
    lc = win.last_calculated
    assert lc["is_digital"] is False
    assert lc["is_planar"] is False
    assert lc["b_dist"] == pytest.approx(6.02)
    assert lc["f_min_iso"] == pytest.approx(_expected_film_f_min(6.02, "class_b"))
    assert lc.get("f_min_star") is None


def test_analog_swsi_uses_film_model(win):
    _configure_analog(win, geometry="swsi", od=323.9, t=10.0, cls_index=1)
    lc = win.last_calculated
    assert lc["b_dist"] == pytest.approx(10.0)
    assert lc["f_min_iso"] == pytest.approx(_expected_film_f_min(10.0, "class_a"))


def test_analog_result_independent_of_detector_radio(win):
    _configure_analog(win, geometry="dwsi", t=6.02, cls_index=0, planar=True)
    planar_result = (win.last_calculated["b_dist"], win.last_calculated["f_min_iso"])
    _configure_analog(win, geometry="dwsi", t=6.02, cls_index=0, planar=False)
    flex_result = (win.last_calculated["b_dist"], win.last_calculated["f_min_iso"])
    assert planar_result == flex_result


def test_analog_dwdi_uses_external_diameter(win):
    _configure_analog(win, geometry="dwdi_elliptic", od=60.3, t=3.91, cls_index=0)
    lc = win.last_calculated
    assert lc["b_dist"] == pytest.approx(60.3)
    assert lc["f_min_iso"] == pytest.approx(_expected_film_f_min(60.3, "class_b"))


def test_digital_planar_still_uses_formula_13(win):
    """Regression guard: the analog gating must not affect digital."""
    win.rad_digital.setChecked(True)
    win.rad_detector_flat.setChecked(True)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("dwsi"))
    win.cmb_class.setCurrentIndex(win.cmb_class.findData("class_b"))
    win.txt_custom_od.setText("219.1")
    win.txt_custom_t.setText("6.02")
    win.txt_bed.setText("127.0")
    win.txt_bgap.setText("5.0")
    win.update_calculations()
    lc = win.last_calculated
    assert lc["is_planar"] is True
    expected_b = 127.0 + 5.0 + 1.1 * 6.02
    assert lc["b_dist"] == pytest.approx(expected_b)
    # Formula (13) governs: f_min* > f_min(b=t)
    plain_f_min = 15.0 * 2.0 * 6.02 ** (2.0 / 3.0)
    assert lc["f_min_iso"] > plain_f_min


def test_analog_pdf_matches_screen(win):
    import tempfile
    import pypdf
    from unittest.mock import patch
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    _configure_analog(win, geometry="dwsi", t=6.02)
    lc = win.last_calculated
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    with patch.object(QFileDialog, "getSaveFileName", return_value=(tmp.name, "")), \
         patch.object(QMessageBox, "information", return_value=None), \
         patch.object(QMessageBox, "critical", return_value=None):
        win.export_pdf_report()
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(tmp.name).pages)
    os.unlink(tmp.name)
    assert f"{lc['f_min_iso']:.1f} mm" in text
    assert f"{lc['sfd_min']:.1f} mm" in text
