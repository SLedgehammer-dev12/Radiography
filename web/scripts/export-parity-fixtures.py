#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exports the 147 matrix scenarios and their shared-engine results as a JSON
fixture consumed by the Playwright parity test (web Pyodide vs desktop core).

Usage (from the repository root)::

    python3 web/scripts/export-parity-fixtures.py
"""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from matrix_oracle import SCENARIOS  # noqa: E402

from src.core.engine import CalculationEngine  # noqa: E402

EXPECTED_KEYS = [
    "w_nom",
    "w_eff",
    "u_max",
    "f_min",
    "f_min_iso",
    "f_min_asme",
    "sfd_min",
    "sdd_min",
    "ug",
    "b_dist",
    "b_eff",
    "exposures_graph",
    "exposures_panel",
    "required_exposures",
    "required_wire_no",
    "required_duplex_no",
    "required_snr",
    "required_density",
    "calc_time_raw",
]


def scenario_to_form(scenario):
    is_xray = scenario["source"] == "x_ray"
    dd = float(scenario.get("dd") or 200.0)
    return {
        "od": scenario["od"],
        "t": scenario["t"],
        "cap": scenario.get("cap", 0.0),
        "d": scenario.get("d", 2.0),
        "sfd": scenario.get("sfd", 600.0),
        "tech": scenario.get("tech", "digital"),
        "material": scenario.get("material", "steel"),
        "source": scenario["source"],
        "testing_class": scenario.get("testing_class", "class_b"),
        "geometry": scenario.get("requested_geometry", "dwsi"),
        "standard": scenario.get("standard", "iso"),
        "std_figure": scenario.get("std_figure"),
        "film_side": not scenario.get("source_side", True),
        "detector_curved": not scenario.get("planar", False),
        "bed": scenario.get("bed", 0.0),
        "bgap": scenario.get("bgap", 5.0),
        "panel_width": dd,
        "panel_height": dd,
        "app_kv": scenario.get("kv", 120.0),
        "output_val": 5.0 if is_xray else 40.0,
        "app_activity": 5.0 if is_xray else 40.0,
    }


def main():
    engine = CalculationEngine()
    fixtures = []
    for scenario in SCENARIOS:
        form = scenario_to_form(scenario)
        result = engine.calculate(form, {}, "tr")
        expected = {
            key: result["calculated"].get(key) for key in EXPECTED_KEYS
        }
        fixtures.append({"id": scenario["id"], "form": form, "expected": expected})

    out_path = os.path.join(
        ROOT, "web", "tests", "e2e", "parity-fixtures.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(fixtures, handle, ensure_ascii=False, indent=1)
    print(f"Wrote {len(fixtures)} parity fixtures to {out_path}")


if __name__ == "__main__":
    main()
