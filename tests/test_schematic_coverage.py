# -*- coding: utf-8 -*-
"""Schematic coverage: every standard-figure key offered by the UI must draw
without error and carry a non-empty title, in both themes."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIGURES = [
    # ISO 17636-1 (analog)
    "fig5", "fig6", "fig7", "fig11", "fig12", "fig13", "fig14",
    # ISO 17636-2 digital, flexible (a) and planar (b)
    "fig5a", "fig6a", "fig7a", "fig8a", "fig9a", "fig10a",
    "fig2b", "fig5b", "fig8b", "fig9b", "fig10b", "fig13a", "fig13b", "fig14b",
]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def canvas(qapp):
    from src.ui.sketch import StandardSchematicCanvas
    from src.core.translation import Translation
    c = StandardSchematicCanvas()
    yield c, Translation()
    try:
        c.fig.clf()
    except Exception:
        pass


@pytest.mark.parametrize("figure", FIGURES)
@pytest.mark.parametrize("dark", [True, False])
def test_draw_figure(canvas, figure, dark):
    c, trans = canvas
    c.draw_figure(figure, trans, is_dark=dark)
    assert c.axes.get_title(), f"{figure} produced an empty title"


def test_figure_keys_cover_ui_lists():
    """All keys offered by update_std_figure_list must be drawable."""
    import inspect
    from src.ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.update_std_figure_list)
    offered = set()
    for token in src.split('add("')[1:]:
        offered.add(token.split('"')[0].replace("_title", ""))
    missing = {k for k in offered if k not in FIGURES}
    assert not missing, f"undrawable figure keys: {sorted(missing)}"
