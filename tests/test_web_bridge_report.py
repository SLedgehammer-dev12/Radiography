# -*- coding: utf-8 -*-
"""Web (Pyodide) bridge report-output construction.

Regression: the bridge always passed a numeric ``u_max``, so isotope reports
printed a fabricated tube voltage instead of "N/A (Isotope)".
"""

import importlib.util
import pathlib

BRIDGE = pathlib.Path(__file__).resolve().parents[1] / "web" / "python" / "bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("web_bridge", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_u_max_is_none_for_isotopes():
    bridge = _load_bridge()
    calculated = {"u_max": 300.0, "w_nom": 10.0}

    xray = bridge._build_report_outputs(calculated, {}, source="x_ray")
    assert xray["u_max"] == 300.0

    isotope = bridge._build_report_outputs(calculated, {}, source="isotope_co60")
    assert isotope["u_max"] is None

    # Default source is x-ray (backwards compatible).
    assert bridge._build_report_outputs(calculated, {})["u_max"] == 300.0
