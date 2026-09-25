# -*- coding: utf-8 -*-
"""Geometry / physics consistency scenarios (Groups A, B, C, E, L).

These tests assert the CORRECT standard behaviour, independently derived from
ISO 17636-1:2022 Clause 7.6 / ISO 17636-2:2022 Clause 7.6 and
ASME Sec V Art 2 T-274.2, not from the implementation itself.

Scenario groups:
  A. Geometric unsharpness Ug = d*b/(SFD-b)
  B. f_min / f_min* (Formulae 2/3/13)
  C. b distance helpers (Formulae 8/9/10/11)
  E. Exposure counts (Annex A / Clauses 7.1.6-7.1.7)
  L. Edge cases / guards
"""

import math

import pytest

from src.core.calculator import RTCalculator


@pytest.fixture(scope="module")
def calc():
    return RTCalculator()


# ---------------------------------------------------------------------------
# Group A — geometric unsharpness
# ---------------------------------------------------------------------------
UG_CASES = [
    (1.0, 8.0, 400.0),
    (2.0, 8.0, 600.0),
    (4.0, 8.0, 1500.0),
    (2.0, 25.0, 600.0),
    (2.0, 60.0, 700.0),
    (2.0, 100.0, 700.0),
    (2.0, 13.8, 600.0),
    (1.5, 50.0, 800.0),
    (3.0, 200.0, 1200.0),
    (2.0, 4.0, 300.0),
]


@pytest.mark.parametrize("d,b,sfd", UG_CASES)
def test_ug_uses_source_object_distance(calc, d, b, sfd):
    """Ug must use f = SFD - b, never SFD itself."""
    expected = d * b / (sfd - b)
    assert calc.calculate_geometric_unsharpness_from_sfd(d, b, sfd) == pytest.approx(expected)


@pytest.mark.parametrize("d,b,sfd", UG_CASES)
def test_ug_from_sfd_is_strictly_larger_than_the_old_wrong_value(calc, d, b, sfd):
    """Using SFD in place of f understates Ug; the corrected value must be larger."""
    wrong = calc.calculate_geometric_unsharpness(d, b, sfd)
    right = calc.calculate_geometric_unsharpness_from_sfd(d, b, sfd)
    assert right > wrong


def test_ug_understatement_reaches_double_digit_percent_for_large_b(calc):
    """DWDI b=OD=100, SFD=700: the old formula understates Ug by ~14%."""
    wrong = calc.calculate_geometric_unsharpness(2.0, 100.0, 700.0)
    right = calc.calculate_geometric_unsharpness_from_sfd(2.0, 100.0, 700.0)
    assert (1.0 - wrong / right) == pytest.approx(1.0 - 600.0 / 700.0, rel=1e-6)
    assert (1.0 - wrong / right) > 0.10


def test_ug_contact_detector_is_zero(calc):
    assert calc.calculate_geometric_unsharpness_from_sfd(2.0, 0.0, 600.0) == 0.0


def test_ug_invalid_geometry_returns_inf(calc):
    """Detector at/beyond the source: geometry is impossible."""
    assert math.isinf(calc.calculate_geometric_unsharpness_from_sfd(2.0, 600.0, 600.0))
    assert math.isinf(calc.calculate_geometric_unsharpness_from_sfd(2.0, 700.0, 600.0))


# ---------------------------------------------------------------------------
# Group B — f_min and f_min* (Formula 13)
# ---------------------------------------------------------------------------
FMIN_STAR_CASES = [
    # (d, t, class, b_over_t)
    (2.0, 8.0, "class_a", 0.5),
    (2.0, 8.0, "class_a", 1.0),
    (2.0, 8.0, "class_a", 1.19),
    (2.0, 8.0, "class_a", 1.21),
    (2.0, 8.0, "class_a", 2.0),
    (2.0, 8.0, "class_a", 5.0),
    (2.0, 8.0, "class_a", 17.7),
    (2.0, 8.0, "class_b", 0.5),
    (2.0, 8.0, "class_b", 1.0),
    (2.0, 8.0, "class_b", 1.19),
    (2.0, 8.0, "class_b", 1.21),
    (2.0, 8.0, "class_b", 2.0),
    (2.0, 8.0, "class_b", 5.0),
    (2.0, 8.0, "class_b", 17.7),
]


@pytest.mark.parametrize("d,t,cls,b_over_t", FMIN_STAR_CASES)
def test_f_min_star_formula_13(calc, d, t, cls, b_over_t):
    b = b_over_t * t
    c = 7.5 if cls == "class_a" else 15.0
    f_star, ci = calc.calculate_f_min_star(d, b, t, cls)
    if b_over_t <= 1.2:
        assert f_star is None and ci is None
    else:
        expected_ci = (b / t) ** (1.0 / 3.0)
        expected = c * d * (t ** (2.0 / 3.0)) * expected_ci
        assert ci == pytest.approx(expected_ci)
        assert f_star == pytest.approx(expected)


@pytest.mark.parametrize("d,t,cls,b_over_t", FMIN_STAR_CASES)
def test_f_min_star_is_smaller_than_plain_f_min_for_b_gt_1_2t(calc, d, t, cls, b_over_t):
    """Formula (13) relaxes the plain Formula (2)/(3) value for planar detectors.

    The pre-fix code did max(f_min, f_min*) which silently discarded Formula (13).
    """
    if b_over_t <= 1.2:
        pytest.skip("magnification rule not applicable")
    b = b_over_t * t
    plain = calc.calculate_f_min(d, b, cls, t)
    f_star, _ = calc.calculate_f_min_star(d, b, t, cls)
    assert f_star < plain


@pytest.mark.parametrize("cls", ["class_a", "class_b"])
def test_f_min_star_continuity_at_1_2t(calc, cls):
    """f_min* approaches f_min(b=t) continuously at b = 1.2 t."""
    d, t = 2.0, 10.0
    f_star, _ = calc.calculate_f_min_star(d, 1.2 * t, t, cls)
    assert f_star is None  # boundary: rule not applied
    f_min_at_t = calc.calculate_f_min(d, t, cls, t)
    c = 7.5 if cls == "class_a" else 15.0
    assert f_min_at_t == pytest.approx(c * d * t ** (2.0 / 3.0))


# ---------------------------------------------------------------------------
# Group C — object-to-detector distance helpers
# ---------------------------------------------------------------------------
B_CURVED_CASES = [
    (0.0, 5.0, 8.0, "class_a", 0.0 + 5.0 + 1.2 * 8.0),
    (10.0, 5.0, 10.0, "class_a", 10.0 + 5.0 + 12.0),
    (127.0, 5.0, 8.0, "class_b", 127.0 + 5.0 + 1.1 * 8.0),
    (0.0, 0.0, 6.0, "class_b", 6.6),
    (20.0, 2.5, 25.0, "class_a", 20.0 + 2.5 + 30.0),
    (5.0, 1.0, 1.0, "class_b", 5.0 + 1.0 + 1.1),
]


@pytest.mark.parametrize("bed,bgap,t,cls,expected", B_CURVED_CASES)
def test_b_planar_formula_8_9(calc, bed, bgap, t, cls, expected):
    assert calc.calculate_b_curved(bed, bgap, t, cls) == pytest.approx(expected)


B_PANO_CASES = [
    (0.0, 5.0, 8.0, 13.0),
    (10.0, 5.0, 10.0, 25.0),
    (50.0, 0.0, 20.0, 70.0),
]


@pytest.mark.parametrize("bed,bgap,t,expected", B_PANO_CASES)
def test_b_panoramic_formula_11(calc, bed, bgap, t, expected):
    assert calc.calculate_b_panoramic(bed, bgap, t) == pytest.approx(expected)


B_ED_CASES = [
    (254.0, 3),
    (254.0, 4),
    (254.0, 6),
    (100.0, 10),
]


@pytest.mark.parametrize("re,n", B_ED_CASES)
def test_b_ed_formula_10(calc, re, n):
    expected = (1.0 - math.cos(math.pi / n)) * re
    assert calc.calculate_b_ed(re, n) == pytest.approx(expected)
    assert calc.calculate_b_ed(re, n) > 0.0


def test_b_ed_guard_invalid(calc):
    assert calc.calculate_b_ed(0.0, 4) == 0.0
    assert calc.calculate_b_ed(-10.0, 4) == 0.0
    assert calc.calculate_b_ed(254.0, 0) == pytest.approx((1.0 - math.cos(math.pi)) * 254.0)


# ---------------------------------------------------------------------------
# Group E — exposure counts
# ---------------------------------------------------------------------------
DWDI_CASES = [
    (50.0, 8.0, 3),
    (100.0, 5.0, 2),
    (100.0, 12.0, 3),
    (100.0, 12.0001, 3),
    (0.0, 5.0, 2),
    (-1.0, 5.0, 2),
]


@pytest.mark.parametrize("od,t,expected", DWDI_CASES)
def test_dwdi_elliptical_exposures(calc, od, t, expected):
    assert calc.get_dwdi_elliptical_exposures(od, t) == expected


DWSI_CASES = [
    (114.3, 8.56, 600.0, "class_a"),
    (114.3, 8.56, 600.0, "class_b"),
    (200.0, 8.0, 700.0, "class_a"),
    (40.0, 10.0, 500.0, "class_a"),
]


@pytest.mark.parametrize("od,t,sfd,cls", DWSI_CASES)
def test_dwsi_exposures_follow_annex_a(calc, od, t, sfd, cls):
    from src.core.annex_a import minimum_exposures

    n = calc.calculate_dwsi_exposures(od, t, sfd, cls)
    assert isinstance(n, int)
    assert n >= 3
    expected = minimum_exposures(
        t, od, max(sfd, od), cls, film_inside=False)
    if expected is not None:
        assert n == max(3, int(expected))


def test_exposure_comparison_governing_value(calc):
    r = calc.evaluate_exposure_comparison(3, 5, 4)
    assert r["n_required"] == 5 and not r["is_sufficient"]
    r = calc.evaluate_exposure_comparison(3, 5, 6)
    assert r["n_required"] == 5 and r["is_sufficient"]
    r = calc.evaluate_exposure_comparison(1, 1, 0)
    assert not r["is_sufficient"]


# ---------------------------------------------------------------------------
# Group L — edge cases / guards
# ---------------------------------------------------------------------------
def test_asme_ug_limit_boundaries(calc):
    assert calc.get_asme_ug_limit(10.0) == 0.51
    assert calc.get_asme_ug_limit(50.8) == 0.51
    assert calc.get_asme_ug_limit(50.81) == 0.76
    assert calc.get_asme_ug_limit(76.2) == 0.76
    assert calc.get_asme_ug_limit(76.21) == 1.02
    assert calc.get_asme_ug_limit(101.6) == 1.02
    assert calc.get_asme_ug_limit(101.61) == 1.78
    assert calc.get_asme_ug_limit(0.0) == 0.51
    assert calc.get_asme_ug_limit(None) == 0.51


def test_asme_f_min_derivation(calc):
    # f_min = d*b/Ug_limit(t)
    assert calc.calculate_asme_f_min(2.0, 8.0, 8.0) == pytest.approx(2.0 * 8.0 / 0.51)
    assert calc.calculate_asme_f_min(2.0, 60.0, 60.0) == pytest.approx(2.0 * 60.0 / 0.76)
    assert calc.calculate_asme_f_min(4.0, 100.0, 120.0) == pytest.approx(4.0 * 100.0 / 1.78)
    assert calc.calculate_asme_f_min(0.0, 8.0, 8.0) == 0.0
    assert calc.calculate_asme_f_min(2.0, 0.0, 8.0) == 0.0


def test_sdd_min_guard(calc):
    assert calc.calculate_sdd_min(None) == 0.0
    assert calc.calculate_sdd_min(0.0) == 0.0
    assert calc.calculate_sdd_min(200.0) == pytest.approx(280.0)


def test_effective_b_rule(calc):
    b_eff, applied = calc.get_effective_b(5.0, 8.0)  # 5 < 9.6
    assert applied and b_eff == 8.0
    b_eff, applied = calc.get_effective_b(12.0, 8.0)  # 12 > 9.6
    assert not applied and b_eff == 12.0


def test_f_min_zero_thickness_does_not_crash(calc):
    assert calc.calculate_f_min(2.0, 8.0, "class_b", 0.0) >= 0.0
    assert calc.calculate_f_min_star(2.0, 8.0, 0.0, "class_b") == (None, None)
