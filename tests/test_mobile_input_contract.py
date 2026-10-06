# -*- coding: utf-8 -*-
"""Static contract checks for the mobile input screens.

The Kivy screens cannot be imported without a display, so these checks parse the
source with ``ast`` to lock two wiring invariants that previously broke:

* The "Teknik" selector wrote ``state.technique`` while the engine reads
  ``state.geometry``, so the control silently had no effect on the calculation.
* The exposure screen reset the detector button label to the first detector on
  every entry, hiding the selected detector.
"""

import ast
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
TECHNIQUE = BASE / "src" / "mobile" / "screens" / "step_technique.py"
EXPOSURE = BASE / "src" / "mobile" / "screens" / "step_exposure.py"


def _method(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _state_set_targets(method):
    """Returns the string keys passed to `self.state.set(...)` in a method."""
    targets = []
    for node in ast.walk(method):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "set"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            targets.append(node.args[0].value)
    return targets


def test_select_technique_drives_the_calculation_input():
    targets = _state_set_targets(_method(TECHNIQUE, "_select_technique"))
    assert "technique" in targets
    assert "geometry" in targets, (
        "_select_technique must also set `geometry` (the key the engine reads)"
    )


def test_select_geometry_keeps_technique_in_sync():
    targets = _state_set_targets(_method(TECHNIQUE, "_select_geometry"))
    assert "geometry" in targets
    assert "technique" in targets


def test_exposure_detector_label_is_not_hardcoded():
    source = EXPOSURE.read_text(encoding="utf-8")
    assert "DETECTOR_TYPES[0][1]" not in source, (
        "the detector button label must reflect the selected detector, not DETECTOR_TYPES[0]"
    )
    attrs = {
        node.attr
        for node in ast.walk(_method(EXPOSURE, "_update_ui"))
        if isinstance(node, ast.Attribute)
    }
    assert "detector_type" in attrs
