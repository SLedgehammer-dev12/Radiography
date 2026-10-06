# -*- coding: utf-8 -*-
"""Locale-tolerant numeric parsing for the mobile input screens.

The app defaults to Turkish (comma decimal separator). The exposure screen used
``float(text)`` directly, so "6,02" raised ValueError and the entered value was
silently discarded, leaving the previous/default value in the calculation.
"""

import pathlib

import pytest

from src.mobile.lib.parsing import parse_number

EXPOSURE = pathlib.Path(__file__).resolve().parents[1] / "src" / "mobile" / "screens" / "step_exposure.py"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("6,02", 6.02),
        ("6.02", 6.02),
        ("120", 120.0),
        (" 40,5 ", 40.5),
        ("-50", -50.0),
        ("", None),
        ("   ", None),
        ("abc", None),
        ("1,2,3", None),
        (None, None),
    ],
)
def test_parse_number_accepts_comma_decimals(raw, expected):
    result = parse_number(raw)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_exposure_screen_uses_the_locale_parser():
    source = EXPOSURE.read_text(encoding="utf-8")
    assert "parse_number" in source
    # No direct float(text) parsing remains (that is the bug being guarded).
    assert "float(text)" not in source
