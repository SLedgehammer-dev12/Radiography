# -*- coding: utf-8 -*-
"""Static contract checks for the mobile weld-sketch canvas.

Kivy's ``Line.circle`` vertex instruction accepts only 3, 5 or 6 values
``(cx, cy, radius[, angle_start, angle_end[, segments]])`` and has no ``radius``
property. Passing a 2-tuple crashed ``_draw_t_joint`` with a GraphicException and
left the T-joint tab blank.

The check parses the source with ``ast`` so it runs headless (importing
``kivy.graphics`` requires a window and is unreliable in CI).
"""

import ast
import pathlib

SKETCH_SOURCE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "src" / "mobile" / "screens" / "step_sketch.py"
)
VALID_CIRCLE_ARITY = (3, 5, 6)


def _line_circle_calls():
    tree = ast.parse(SKETCH_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "Line"):
            continue
        for keyword in node.keywords:
            if keyword.arg == "circle":
                yield node, keyword


def test_line_circle_calls_use_valid_arity():
    calls = list(_line_circle_calls())
    assert calls, "expected at least one Line(circle=...) call in step_sketch.py"
    for node, keyword in calls:
        assert isinstance(keyword.value, ast.Tuple), (
            f"Line(circle=...) at line {node.lineno} must be an inline tuple"
        )
        arity = len(keyword.value.elts)
        assert arity in VALID_CIRCLE_ARITY, (
            f"Line(circle=...) at line {node.lineno} has {arity} values; "
            f"Kivy requires one of {VALID_CIRCLE_ARITY}"
        )


def test_line_circle_does_not_pass_radius_keyword():
    for node, _keyword in _line_circle_calls():
        radius_kwargs = [kw for kw in node.keywords if kw.arg == "radius"]
        assert not radius_kwargs, (
            f"Line(circle=...) at line {node.lineno} passes radius=; "
            "the radius must be the third element of the circle tuple"
        )
