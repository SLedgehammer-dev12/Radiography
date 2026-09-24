# -*- coding: utf-8 -*-
"""SFD_min / SDD_min receptor-dimension scenarios.

Analog (ISO 17636-1 Formula 4): SFD >= 1.4 * df, df = film sheet diagonal.
Digital (ISO 17636-2 Formula 7): SDD >= 1.4 * dd, dd = panel active-area
diagonal.
"""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.core.calculator import RTCalculator


@pytest.fixture(scope="module")
def calc():
    return RTCalculator()


DIAGONAL_CASES = [
    (300.0, 400.0),
    (80.0, 300.0),
    (100.0, 400.0),
    (200.0, 200.0),
]


@pytest.mark.parametrize("w,h", DIAGONAL_CASES)
def test_diagonal(calc, w, h):
    assert calc.calculate_diagonal(w, h) == pytest.approx(math.hypot(w, h))


@pytest.mark.parametrize("w,h", [(0.0, 100.0), (100.0, 0.0), (-1.0, 100.0),
                                 (None, 100.0), ("x", 100.0)])
def test_diagonal_guard(calc, w, h):
    assert calc.calculate_diagonal(w, h) == 0.0


@pytest.mark.parametrize("w,h", DIAGONAL_CASES)
def test_coverage_min_is_1_4_diagonal(calc, w, h):
    df = math.hypot(w, h)
    assert calc.calculate_coverage_min(df) == pytest.approx(1.4 * df)
    assert calc.calculate_sdd_min(df) == pytest.approx(1.4 * df)  # alias


def test_coverage_min_guard(calc):
    assert calc.calculate_coverage_min(0.0) == 0.0
    assert calc.calculate_coverage_min(None) == 0.0
    assert calc.calculate_coverage_min(-5.0) == 0.0


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


def test_analog_sfd_min_uses_film_diagonal(win):
    win.rad_analog.setChecked(True)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("swsi"))
    win.txt_custom_od.setText("323.9")
    win.txt_custom_t.setText("10.0")
    win.txt_app_sfd.setText("600")
    # 300 x 400 mm film -> df = 500 -> coverage 700
    win.cmb_film_size.setCurrentIndex(win.cmb_film_size.findData("300x400"))
    win.update_calculations()
    lc = win.last_calculated
    assert lc["df"] == pytest.approx(500.0)
    assert lc["coverage_min"] == pytest.approx(700.0)
    assert lc["sfd_min"] == pytest.approx(700.0)
    assert win.out_labels["sfd_min"][0].text().startswith("Minimum Odak-Film")


def test_analog_custom_film_size(win):
    win.rad_analog.setChecked(True)
    win.cmb_film_size.setCurrentIndex(win.cmb_film_size.findData("custom"))
    win.txt_film_width.setText("100")
    win.txt_film_height.setText("500")
    win.txt_custom_t.setText("10.0")
    win.txt_app_sfd.setText("600")
    win.update_calculations()
    lc = win.last_calculated
    assert lc["df"] == pytest.approx((100 ** 2 + 500 ** 2) ** 0.5)
    assert lc["coverage_min"] == pytest.approx(1.4 * lc["df"])


def test_digital_sdd_min_uses_panel_diagonal(win):
    win.rad_digital.setChecked(True)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("swsi"))
    win.txt_custom_t.setText("10.0")
    win.txt_app_sfd.setText("600")
    win.txt_panel_width.setText("300")
    win.txt_panel_height.setText("400")
    win.update_calculations()
    lc = win.last_calculated
    assert lc["dd"] == pytest.approx(500.0)
    assert lc["coverage_min"] == pytest.approx(700.0)
    assert lc["sfd_min"] == pytest.approx(700.0)
    assert win.out_labels["sfd_min"][0].text().startswith("Minimum Odak-Dedektör")


def test_analog_missing_df_warns(win):
    win.rad_analog.setChecked(True)
    win.cmb_film_size.setCurrentIndex(win.cmb_film_size.findData("custom"))
    win.txt_film_width.setText("0")
    win.txt_film_height.setText("0")
    win.update_calculations()
    assert win.last_calculated["coverage_min"] == 0.0
    assert "df" in win.txt_warnings.text()


def test_applied_distance_label_is_mode_aware(win):
    win.rad_analog.setChecked(True)
    assert "SFD" in win.lbl_app_sfd.text()
    win.rad_digital.setChecked(True)
    assert "SDD" in win.lbl_app_sfd.text()
