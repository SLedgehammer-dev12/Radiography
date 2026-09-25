# -*- coding: utf-8 -*-
"""Standard-figure mapping (technology x detector shape x geometry) and the
planar detector edge-lift (b_ed) automation scenarios."""

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


def _set(win, tech, planar, geometry):
    win.rad_digital.setChecked(tech == "digital")
    win.rad_analog.setChecked(tech == "analog")
    win.rad_detector_flat.setChecked(planar)
    win.rad_detector_curved.setChecked(not planar)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData(geometry))
    win.update_std_figure_list()


def _keys(win):
    return {win.cmb_std_figure.itemData(i) for i in range(win.cmb_std_figure.count())}


@pytest.mark.parametrize("tech,planar,geometry,expected", [
    ("digital", True, "swsi", {"fig2b", "fig5b", "fig8b"}),
    ("digital", False, "swsi", {"fig2a", "fig5a", "fig8a"}),
    ("digital", True, "dwsi", {"fig13b", "fig14b"}),
    ("digital", False, "dwsi", {"fig13a", "fig14a"}),
    ("digital", True, "dwdi_elliptic", {"fig11", "fig12"}),
    ("digital", False, "dwdi_super", {"fig11", "fig12"}),
    ("analog", True, "swsi", {"fig2", "fig5", "fig8"}),
    ("analog", False, "swsi", {"fig2", "fig5", "fig8"}),
    ("analog", True, "dwsi", {"fig13", "fig14"}),
    ("analog", True, "dwdi_elliptic", {"fig11", "fig12"}),
])
def test_figure_list_by_tech_panel_geometry(win, tech, planar, geometry, expected):
    _set(win, tech, planar, geometry)
    assert _keys(win) == expected


def test_figure_14b_is_dwsi_not_dwdi(win):
    _set(win, "digital", True, "dwsi")
    assert "fig14b" in _keys(win)
    _set(win, "digital", True, "dwdi_elliptic")
    assert "fig14b" not in _keys(win)


def test_swsi_figures_are_not_offered_for_dwsi(win):
    _set(win, "digital", True, "swsi")
    assert "fig2b" in _keys(win) and "fig8b" in _keys(win)
    _set(win, "digital", True, "dwsi")
    assert "fig2b" not in _keys(win)
    assert "fig8b" not in _keys(win)


def test_corner_weld_figures_are_excluded(win):
    """Figures 6/7 (and 9/10) are set-in/set-on corner welds, not butt welds."""
    _set(win, "analog", True, "swsi")
    assert _keys(win).isdisjoint({"fig6", "fig7", "fig9", "fig10"})
    _set(win, "digital", False, "swsi")
    assert _keys(win).isdisjoint(
        {"fig6a", "fig7a", "fig9a", "fig10a"})
    _set(win, "digital", True, "swsi")
    assert _keys(win).isdisjoint({"fig9b", "fig10b"})


def test_preset_roundtrip_keeps_std_figure(win):
    _set(win, "digital", True, "swsi")
    win.cmb_std_figure.setCurrentIndex(win.cmb_std_figure.findData("fig8b"))
    state = win.collect_form_state()
    assert state["cmb_std_figure"] == "fig8b"
    win.cmb_std_figure.setCurrentIndex(win.cmb_std_figure.findData("fig2b"))
    win.apply_form_state(state)
    assert win.cmb_std_figure.currentData() == "fig8b"


# ---------------------------------------------------------------------------
# b_ed automation
# ---------------------------------------------------------------------------
def _configure_dwsi(win, bed="0.0", t=6.02, od=219.1, planar=True):
    win.rad_digital.setChecked(True)
    win.rad_detector_flat.setChecked(planar)
    win.rad_detector_curved.setChecked(not planar)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("dwsi"))
    win.cmb_class.setCurrentIndex(win.cmb_class.findData("class_b"))
    win.txt_custom_od.setText(str(od))
    win.txt_custom_t.setText(str(t))
    win.txt_bed.setText(bed)
    win.txt_bgap.setText("5.0")
    win.update_calculations()


def test_bed_auto_used_when_zero(win):
    _configure_dwsi(win, bed="0.0")
    lc = win.last_calculated
    assert lc["bed_auto"] is True
    n = win.calc.calculate_dwsi_exposures(219.1, 6.02, float(win.txt_app_sfd.text()), "class_b")
    expected_bed = win.calc.calculate_b_ed(219.1 / 2.0, n)
    assert lc["bed_used"] == pytest.approx(expected_bed)
    assert lc["b_dist"] == pytest.approx(expected_bed + 5.0 + 1.1 * 6.02)
    assert "Formül (10)" in win.txt_warnings.text()


def test_bed_user_value_respected(win):
    _configure_dwsi(win, bed="127.0")
    lc = win.last_calculated
    assert lc["bed_auto"] is False
    assert lc["bed_used"] == pytest.approx(127.0)
    assert lc["b_dist"] == pytest.approx(127.0 + 5.0 + 1.1 * 6.02)


def test_bed_smaller_than_formula_note(win):
    _configure_dwsi(win, bed="10.0")
    assert "küçük" in win.txt_warnings.text() or "smaller" in win.txt_warnings.text()


def test_swsi_planar_zero_bed_warns_without_auto(win):
    win.rad_digital.setChecked(True)
    win.rad_detector_flat.setChecked(True)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("swsi"))
    win.txt_custom_t.setText("10.0")
    win.txt_bed.setText("0.0")
    win.update_calculations()
    lc = win.last_calculated
    assert lc["bed_auto"] is False
    assert lc["bed_used"] == 0.0
    assert "bed=0" in win.txt_warnings.text() or "bed" in win.txt_warnings.text()


def test_analog_bed_zero_no_planar_warning(win):
    win.rad_analog.setChecked(True)
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("dwsi"))
    win.txt_custom_t.setText("6.02")
    win.txt_bed.setText("0.0")
    win.update_calculations()
    assert win.last_calculated["bed_auto"] is False
    assert "Şekil 23" not in win.txt_warnings.text()
