# -*- coding: utf-8 -*-
"""Annex A digitized exposure-count tables (ISO 17636-1/2:2022)."""

import json
import os

import pytest

from src.core import annex_a

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "src", "core", "data",
    "annex_a_iso17636_1.json",
)


def test_data_file_exists_and_complete():
    with open(FIXTURE, encoding="utf-8") as handle:
        data = json.load(handle)
    assert set(data) == {"A1", "A2", "A3", "A4"}
    expected = {
        "A1": list(range(8, 25)),
        "A2": list(range(1, 11)),
        "A3": list(range(6, 19)),
        "A4": list(range(1, 9)),
    }
    for key, n_values in expected.items():
        curves = data[key]["curves"]
        assert sorted(int(n) for n in curves) == n_values, key
        assert data[key]["x"][0] == 0.0
        assert data[key]["x"][-1] == 0.25


def test_figure_mapping():
    assert annex_a.figure_for("class_b", True) == "A1"
    assert annex_a.figure_for("class_b", False) == "A2"
    assert annex_a.figure_for("class_a", True) == "A3"
    assert annex_a.figure_for("class_a", False) == "A4"


def test_curves_are_monotonic_in_n():
    """For a fixed position, higher N must sit further from the origin."""
    with open(FIXTURE, encoding="utf-8") as handle:
        data = json.load(handle)
    for key, figure in data.items():
        x_values = figure["x"]
        curves = figure["curves"]
        increasing_up = key in ("A1", "A3")
        for index, x in enumerate(x_values):
            values = [
                (int(n), curves[n][index])
                for n in curves
                if curves[n][index] is not None
            ]
            values.sort()
            if len(values) < 2:
                continue
            ys = [value for _, value in values]
            # Small inversions (< 0.02) come from vector extraction noise
            # between neighbouring near-parallel curves.
            if increasing_up:
                assert all(b >= a - 0.02 for a, b in zip(ys, ys[1:])), (key, x)
            else:
                assert all(b <= a + 0.02 for a, b in zip(ys, ys[1:])), (key, x)


def test_class_b_starts_at_four_exposures_below_de_sfd_one():
    """User-verified reference: A.2, De/SFD just below 1, small t/De -> N=4."""
    result = annex_a.minimum_exposures(
        t=0.5, de=100.0, distance=101.0,
        testing_class="class_b", film_inside=False,
    )
    assert result == 4


def test_higher_inclination_needs_more_exposures():
    """Smaller De/SFD (source farther) increases the A.2 exposure count."""
    near = annex_a.minimum_exposures(
        4.0, 100.0, 101.0, "class_b", film_inside=False)
    far = annex_a.minimum_exposures(
        4.0, 100.0, 400.0, "class_b", film_inside=False)
    assert near is not None and far is not None
    assert far > near


def test_class_a_is_less_or_equal_to_class_b():
    for t, de, distance in [(4.0, 100.0, 105.0), (8.0, 200.0, 220.0)]:
        class_a = annex_a.minimum_exposures(
            t, de, distance, "class_a", film_inside=False)
        class_b = annex_a.minimum_exposures(
            t, de, distance, "class_b", film_inside=False)
        assert class_a is not None and class_b is not None
        assert class_a <= class_b


def test_panoramic_and_out_of_range():
    assert annex_a.minimum_exposures(5, 100, 100, "class_b", False) is not None
    assert annex_a.minimum_exposures(0, 0, 0) is None
    # Above the chart (source inside the pipe wall) -> not defined
    assert annex_a.minimum_exposures(5, 100, 40, "class_b", False) is None


def test_known_chart_floor():
    # A.1/A.3 (film inside) never go below 8/6 exposures in the charts.
    assert annex_a.minimum_exposures(
        2.0, 500.0, 5000.0, "class_b", film_inside=True) == 8
    assert annex_a.minimum_exposures(
        2.0, 500.0, 5000.0, "class_a", film_inside=True) == 6
