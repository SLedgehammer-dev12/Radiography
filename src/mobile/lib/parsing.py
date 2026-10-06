# -*- coding: utf-8 -*-
"""Locale-tolerant numeric parsing for the mobile input screens.

The app defaults to Turkish, where the decimal separator is a comma. Kivy text
inputs deliver the raw string, so "6,02" must be accepted alongside "6.02".
Returns ``None`` for invalid/empty input so callers can keep the previous value
instead of raising.
"""


def parse_number(text):
    """Parses ``text`` as a float, accepting ',' as the decimal separator.

    Returns the float value, or ``None`` when the input is not a valid number.
    """
    if text is None:
        return None
    cleaned = str(text).strip().replace(",", ".")
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None
