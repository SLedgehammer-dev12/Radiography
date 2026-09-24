# -*- coding: utf-8 -*-
"""Mobile / desktop parity scenarios — Phase 1 critical fixes (Group J).

Covers: get_target_snr tuple unpacking (digital compliance crashed before),
applied-SFD wiring, applied_* plumbing / exposure-count check, source-side IQI
semantics, required optical density and the Ug denominator.
"""

import pytest


@pytest.fixture
def state():
    from src.mobile.lib.app_state import AppState
    AppState._instance = None
    s = AppState()
    yield s
    AppState._instance = None


def test_digital_compliance_has_no_tuple_type_error(state):
    state.tech = "digital"
    state.source = "x_ray"
    state.geometry = "swsi"
    r = state.run_calculations()
    assert "error" not in state.compliance
    assert isinstance(r["target_snr"], (int, float))
    assert isinstance(r["required_quality"], (int, float))


def test_snr_target_is_float_in_compliance_dict(state):
    state.tech = "digital"
    state.run_calculations()
    snr_checks = [c for c in state.compliance["checks"] if c["name"] == "quality"]
    assert snr_checks, "SNR quality check missing"
    assert snr_checks[0]["status"] in (True, False)


def test_applied_sfd_drives_ug_and_exposure_time(state):
    state.geometry = "swsi"
    state.app_sfd = 600.0
    r600 = state.run_calculations()
    state.app_sfd = 300.0
    r300 = state.run_calculations()
    assert r300["ug"] > r600["ug"]
    assert r300["calc_time"] != r600["calc_time"]


def test_ug_uses_f_equals_sfd_minus_b(state):
    state.geometry = "swsi"
    state.pipe_wall = 6.02
    state.d = 2.0
    state.app_sfd = 600.0
    r = state.run_calculations()
    expected = 2.0 * 6.02 / (600.0 - 6.02)
    assert r["ug"] == pytest.approx(expected)


def test_source_side_iqi_semantics(state):
    state.geometry = "swsi"
    state.testing_class = "class_a"
    state.source_side_iqi = True  # IQI on source side -> Table B.1
    r = state.run_calculations()
    assert "Tablo B.1" in r["single_wire_iqi"][0]

    state.source_side_iqi = False  # IQI on film/detector side -> Table B.9
    r = state.run_calculations()
    assert "Tablo B.9" in r["single_wire_iqi"][0]


def test_required_density_by_class(state):
    state.tech = "analog"
    state.testing_class = "class_b"
    r = state.run_calculations()
    assert r["required_density"] == pytest.approx(2.3)

    state.testing_class = "class_a"
    r = state.run_calculations()
    assert r["required_density"] == pytest.approx(2.0)


def test_required_density_se75_thin_class_b(state):
    state.tech = "analog"
    state.material = "steel"
    state.source = "isotope_se75"
    state.testing_class = "class_b"
    state.pipe_wall = 6.0
    r = state.run_calculations()
    assert r["required_density"] == pytest.approx(3.0)


def test_exposure_count_check_runs_when_applied_set(state):
    state.geometry = "swsi"
    state.app_exposures = 1
    state.run_calculations()
    exp_checks = [c for c in state.compliance["checks"] if c["name"] == "exposures"]
    assert exp_checks, "exposure count check was skipped"
    assert exp_checks[0]["status"] is True

    state.app_exposures = 0
    state.run_calculations()
    exp_checks = [c for c in state.compliance["checks"] if c["name"] == "exposures"]
    assert not exp_checks


def test_dwsi_uses_applied_sfd_not_sfd_min(state):
    from src.core.calculator import RTCalculator
    calc = RTCalculator()
    state.geometry = "dwsi"
    state.pipe_od = 508.0
    state.pipe_wall = 8.0
    state.testing_class = "class_a"
    state.app_sfd = 1000.0
    r = state.run_calculations()
    expected = calc.calculate_dwsi_exposures(508.0, 8.0, 1000.0, "class_a")
    assert r["req_exposures"] == expected


def test_dwsi_impossible_sfd_clamped(state):
    state.geometry = "dwsi"
    state.pipe_od = 508.0
    state.pipe_wall = 8.0
    state.testing_class = "class_a"
    state.app_sfd = 100.0  # physically impossible
    r_impossible = state.run_calculations()
    state.app_sfd = 508.0  # source on the pipe surface
    r_physical = state.run_calculations()
    assert r_impossible["req_exposures"] == r_physical["req_exposures"]


def test_adjacent_snr_location_applies_1_4x(state):
    state.tech = "digital"
    state.source = "x_ray"
    state.kv = 120.0
    state.cap = 3.0
    state.snr_location = "weld"
    base = state.run_calculations()["target_snr"]
    state.snr_location = "adjacent"
    target = state.run_calculations()["target_snr"]
    assert target == pytest.approx(base * 1.4)


def test_dwsi_source_side_iqi_flagged(state):
    state.geometry = "dwsi"
    state.pipe_od = 114.3
    state.pipe_wall = 6.02
    state.source_side_iqi = True
    state.run_calculations()
    placement = [c for c in state.compliance["checks"] if c["name"] == "iqi_placement"]
    assert placement and placement[0]["status"] is False

    state.source_side_iqi = False
    state.run_calculations()
    placement = [c for c in state.compliance["checks"] if c["name"] == "iqi_placement"]
    assert not placement


def test_defect_evaluation_returns_normalized_dict(state):
    """The screens/PDF helper call .get() on the result; tuples used to crash."""
    r = state.evaluate_defect("defect_crack", 5.0, 1.0, 0.0)
    assert isinstance(r, dict)
    assert "status" in r and "result" in r


@pytest.mark.parametrize("standard", ["api1104", "iso5817", "b31_3", "viii"])
def test_defect_evaluation_all_standards_normalized(state, standard):
    state.defect_standard = standard
    r = state.evaluate_defect("defect_porosity", 2.0, 1.0, 0.0)
    assert isinstance(r, dict)
    assert isinstance(r.get("status"), bool)
