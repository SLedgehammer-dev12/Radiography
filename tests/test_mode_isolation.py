# -*- coding: utf-8 -*-
"""Analog/digital mode isolation scenarios.

Digital-only values (SRb, duplex, SNR, Annex F, panel exposures) must not be
computed or exposed in analog mode, and analog-only values (film class, optical
density, film overlap) must not leak into digital mode.
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


def _run(win, tech, geometry="swsi", t=6.02, od=219.1, cls="class_b"):
    win.rad_digital.setChecked(tech == "digital")
    win.rad_analog.setChecked(tech == "analog")
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData(geometry))
    win.cmb_class.setCurrentIndex(win.cmb_class.findData(cls))
    win.txt_custom_od.setText(str(od))
    win.txt_custom_t.setText(str(t))
    win.update_calculations()
    win.check_procedure_compliance()
    return win.last_calculated


def test_analog_has_no_digital_only_values(win):
    lc = _run(win, "analog")
    assert lc.get("max_srb") is None
    assert lc.get("required_duplex_no") is None
    assert "required_snr" not in lc
    assert lc.get("exposures_panel") is None


def test_digital_has_no_analog_only_values(win):
    lc = _run(win, "digital")
    assert lc.get("required_film_class") is None
    assert "required_density" not in lc
    assert lc.get("max_srb") is not None
    assert lc.get("required_duplex_no") is not None


def test_annex_f_check_is_digital_only(win):
    _run(win, "analog", t=60.0, od=600.0)
    assert "annex_f" not in win.lbl_compliance_details.text().lower()
    _run(win, "digital", t=60.0, od=600.0)
    # The check may pass or fail but must be present in digital mode
    assert "annex" in win.lbl_compliance_details.text().lower() or \
        "srb" in win.lbl_compliance_details.text().lower()


def test_digital_only_output_rows_hidden_in_analog(win):
    win.rad_analog.setChecked(True)
    assert win.out_rows["duplex_iqi"].isHidden()
    assert win.out_rows["exposures_panel"].isHidden()
    win.rad_digital.setChecked(True)
    assert not win.out_rows["duplex_iqi"].isHidden()
    assert not win.out_rows["exposures_panel"].isHidden()


def test_wire_iqi_display_carries_active_standard(win):
    _run(win, "analog")
    assert "ISO 17636-1" in win.out_labels["single_wire_iqi"][1].text()
    _run(win, "digital")
    assert "ISO 17636-2" in win.out_labels["single_wire_iqi"][1].text()
