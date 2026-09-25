# -*- coding: utf-8 -*-
"""ISO 17636-1/2:2022 Annex A exposure-count lookup.

The minimum number of exposures for a circumferential butt weld is read from
the digitized Figures A.1-A.4:

    A.1  single-wall penetration, source outside, film/detector INSIDE
         (Figure 2 arrangement), Class B (dt/t = 10 %)  ->  t/De and De/f
    A.2  off-centre source inside + double-wall penetration, film/detector
         OUTSIDE (Figures 8 and 13), Class B            ->  t/De and De/SFD
    A.3  as A.1 for Class A (dt/t = 20 %)
    A.4  as A.2 for Class A

Tables are produced by ``tools/digitize_annex_a.py`` from the standard PDFs
(vector curve extraction + axis-label calibration + visual overlay check).
"""

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data",
                          "annex_a_iso17636_1.json")

_CACHE = None


def _load():
    global _CACHE
    if _CACHE is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as handle:
            _CACHE = json.load(handle)
    return _CACHE


def figure_for(testing_class, film_inside):
    """Returns the Annex A figure key for the quality class and film side.

    ``film_inside`` is True for the Figure 2 arrangement (source outside,
    film/detector inside) and False for the off-centre/double-wall
    arrangements (Figures 8/13, film/detector outside).
    """
    if film_inside:
        return "A3" if testing_class == "class_a" else "A1"
    return "A4" if testing_class == "class_a" else "A2"


def _interpolate(x_values, curve_values, x):
    """Linear interpolation along one digitized curve (None outside range)."""
    points = [(xv, cv) for xv, cv in zip(x_values, curve_values) if cv is not None]
    if not points:
        return None
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-9:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return points[-1][1]


def lookup_detail(t, de, distance, testing_class="class_b",
                  film_inside=False, figure=None):
    """Like :func:`minimum_exposures` but also returns the chart context.

    Returns ``None`` when the query is outside the digitized charts, otherwise
    a dict with the figure key, the N value, the query coordinates, all curve
    boundaries at that t/De and the next stricter curve (which N and which
    distance would be required).
    """
    try:
        t = float(t)
        de = float(de)
        distance = float(distance)
    except (TypeError, ValueError):
        return None
    if de <= 0.0 or distance <= 0.0 or t < 0.0:
        return None

    key = figure or figure_for(testing_class, film_inside)
    data = _load().get(key)
    if not data:
        return None

    x = t / de
    y = de / distance
    if x > data["x_max"] or y > data["y_max"]:
        return None

    n = minimum_exposures(t, de, distance, testing_class, film_inside, key)
    if n is None:
        return None

    x_values = data["x"]
    curves = data["curves"]
    boundaries = []
    for m in sorted(int(value) for value in curves):
        curve_y = _interpolate(x_values, curves[str(m)], x)
        if curve_y is None or curve_y <= 1e-9:
            continue
        boundaries.append({
            "n": m,
            "ratio": round(curve_y, 4),
            "distance_mm": round(de / curve_y, 1),
        })

    next_boundary = next((b for b in boundaries if b["n"] == n + 1), None)
    return {
        "figure": key,
        "y_axis": data["y_axis"],
        "n": n,
        "t_over_de": round(x, 4),
        "ratio_name": "De/f" if data["y_axis"] == "De_f" else "De/SFD",
        "ratio": round(y, 4),
        "distance_mm": round(distance, 1),
        "boundaries": boundaries,
        "next_n": next_boundary["n"] if next_boundary else None,
        "next_ratio": next_boundary["ratio"] if next_boundary else None,
        "next_distance_mm": next_boundary["distance_mm"] if next_boundary else None,
        # For A.2/A.4 the stricter N needs ratio <= boundary; for A.1/A.3 it
        # needs ratio >= boundary.
        "next_op": "le" if data["y_axis"] == "De_SFD" else "ge",
    }


def minimum_exposures(t, de, distance, testing_class="class_b",
                      film_inside=False, figure=None):
    """Annex A minimum number of exposures.

    Parameters
    ----------
    t : wall thickness (mm)
    de : pipe outside diameter (mm)
    distance : f (source-to-object) for A.1/A.3, SFD/SDD for A.2/A.4 (mm)
    testing_class : "class_a" | "class_b"
    film_inside : film/detector inside the pipe (Figure 2 arrangement)
    figure : explicit figure override ("A1".."A4")

    Returns the smallest N whose curve lies at or below the query point, i.e.
    the region between curve N and curve N-1 requires N exposures. Returns
    ``None`` when the inputs are outside the digitized chart range.
    """
    try:
        t = float(t)
        de = float(de)
        distance = float(distance)
    except (TypeError, ValueError):
        return None
    if de <= 0.0 or distance <= 0.0 or t < 0.0:
        return None

    key = figure or figure_for(testing_class, film_inside)
    data = _load().get(key)
    if not data:
        return None

    x = t / de
    if data["y_axis"] == "De_f":
        y = de / distance
    else:
        y = de / distance
    if x > data["x_max"] or y > data["y_max"]:
        return None

    x_values = data["x"]
    curves = data["curves"]
    n_values = sorted(int(n) for n in curves)

    # Each curve is the boundary where its N becomes the minimum number of
    # exposures; the region between two neighbouring curves is labelled with
    # the curve at or above the query point (i.e. the smallest sufficient N):
    #   A.1/A.3 (film inside):  N grows with De/f   -> take the LOWEST such N
    #   A.2/A.4 (film outside): N grows as De/SFD falls -> take the HIGHEST
    candidates = []
    present = []
    for n in n_values:
        curve_y = _interpolate(x_values, curves[str(n)], x)
        if curve_y is None:
            continue
        present.append(n)
        if curve_y >= y:
            candidates.append(n)

    if candidates:
        return min(candidates) if data["y_axis"] == "De_f" else max(candidates)
    if not present:
        return None
    # Above every curve of the figure -> the chart cap (A.1/A.3).
    return max(present) if data["y_axis"] == "De_f" else None
