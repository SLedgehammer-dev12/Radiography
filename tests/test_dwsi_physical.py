# -*- coding: utf-8 -*-
"""DWSI physical constraint scenarios (Group D).

ISO 17636-1:2022 Clause 7.6 / ISO 17636-2:2022 Clause 7.6 state that for DWSI
the minimum source-to-object distance is determined only by the wall thickness
(b = t), NOT by the pipe diameter. The source, however, is physically outside
the pipe and the detector on the opposite side, so the applied SFD can never be
smaller than about De + bgap. The tool enforces that physical floor and guards
the geometric exposure solver against impossible SFD values.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.core.calculator import RTCalculator


@pytest.fixture(scope="module")
def calc():
    return RTCalculator()


# ---------------------------------------------------------------------------
# Core solver guard
# ---------------------------------------------------------------------------
DWSI_ODS = [
    (114.3, 6.02),
    (219.1, 8.18),
    (323.9, 10.31),
    (508.0, 8.0),
]


@pytest.mark.parametrize("od,t", DWSI_ODS)
def test_dwsi_solver_never_places_source_inside_pipe(calc, od, t):
    """SFD below De is clamped to De; the result must match the SFD=De case."""
    n_at_od = calc.calculate_dwsi_exposures(od, t, od, "class_b")
    for sfd in (1.0, 10.0, od / 4.0, od / 2.0, od - 1.0):
        n = calc.calculate_dwsi_exposures(od, t, sfd, "class_b")
        assert n == n_at_od


@pytest.mark.parametrize("od,t", DWSI_ODS)
def test_dwsi_solver_returns_sane_counts(calc, od, t):
    for sfd in (od, od + 100.0, 600.0, 1500.0):
        n = calc.calculate_dwsi_exposures(od, t, sfd, "class_b")
        assert isinstance(n, int)
        assert 3 <= n <= 12


def test_dwsi_solver_degenerate_solid_pipe(calc):
    """t >= De/2 (no inner cavity) must not crash or return garbage."""
    assert calc.calculate_dwsi_exposures(50.0, 30.0, 600.0, "class_b") >= 3
    assert calc.calculate_dwsi_exposures(10.0, 10.0, 600.0, "class_a") >= 3


def test_dwsi_solver_invalid_inputs(calc):
    assert calc.calculate_dwsi_exposures(None, 8.0, 600.0, "class_a") >= 3
    assert calc.calculate_dwsi_exposures(114.3, 0.0, 600.0, "class_a") >= 3


# ---------------------------------------------------------------------------
# Desktop UI: physical floor and warnings
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


def _configure_dwsi(win, od=508.0, t=8.0, sfd=600.0, cls_index=0):
    win.txt_custom_od.setText(str(od))
    win.txt_custom_t.setText(str(t))
    win.txt_app_sfd.setText(str(sfd))
    win.cmb_geometry.setCurrentIndex(win.cmb_geometry.findData("dwsi"))
    win.cmb_class.setCurrentIndex(cls_index)
    win.update_calculations()


def test_dwsi_sfd_min_respects_physical_floor(win):
    _configure_dwsi(win, od=508.0, t=8.0, sfd=600.0)
    sfd_min = win.last_calculated["sfd_min"]
    assert sfd_min >= 508.0  # >= De
    assert sfd_min >= 508.0 + 5.0  # >= De + bgap


def test_dwsi_sfd_min_label_matches_calculation(win):
    _configure_dwsi(win, od=508.0, t=8.0, sfd=600.0)
    label = win.out_labels["sfd_min"][1].text()
    assert label == f"{win.last_calculated['sfd_min']:.1f} mm"


def test_dwsi_below_physical_floor_warns(win):
    _configure_dwsi(win, od=508.0, t=8.0, sfd=100.0)
    txt = win.txt_warnings.text()
    assert "fiziksel asgari" in txt.lower() or "physical minimum" in txt.lower()


def test_dwsi_above_floor_no_physical_warning(win):
    _configure_dwsi(win, od=508.0, t=8.0, sfd=1500.0)
    txt = win.txt_warnings.text().lower()
    assert "fiziksel asgari" not in txt
    assert "physical minimum" not in txt


def test_dwsi_floor_note_when_governing(win):
    """When OD+bgap governs over f_min+b, an informational note must appear."""
    _configure_dwsi(win, od=508.0, t=8.0, sfd=1500.0)
    assert win.last_calculated["dwsi_physical_min"] > (
        win.last_calculated["f_min"] + win.last_calculated["b_dist"])
    assert "fiziksel taban" in win.txt_warnings.text().lower()


def test_dwsi_impossible_sfd_does_not_corrupt_exposure_count(win):
    _configure_dwsi(win, od=508.0, t=8.0, sfd=100.0)
    n_impossible = win.last_calculated["exposures_graph"]
    _configure_dwsi(win, od=508.0, t=8.0, sfd=508.0)
    n_physical = win.last_calculated["exposures_graph"]
    assert n_impossible == n_physical


def test_dwsi_applied_sfd_above_floor_passes_sfd_check(win):
    _configure_dwsi(win, od=508.0, t=8.0, sfd=520.0)
    win.txt_app_sfd.setText("520")
    win.update_calculations()
    checks = {c["name"]: c for c in win.proc_checker.check_compliance(
        {
            "tech": "digital", "source": "x_ray", "class": "class_b",
            "geometry": "dwsi", "film_side": False, "iqi_type": "wire",
            "snr_location": "weld", "material": "steel", "t": 8.0,
        },
        win.last_calculated,
        {
            "applied_kv": 120.0, "applied_activity": 0.0, "applied_sfd": 520.0,
            "applied_time": win.last_calculated["calc_time_raw"],
            "applied_wire": win.last_calculated["required_wire_no"],
            "applied_duplex": win.last_calculated["required_duplex_no"],
            "applied_quality": win.last_calculated.get("required_snr", 70.0),
            "applied_srb": 80.0, "applied_film_class": "C5",
            "applied_overlap": 10.0,
            "applied_exposures": win.last_calculated["required_exposures"],
        },
        {}, "tr")["checks"]}
    assert checks["sfd"]["status"] is True
