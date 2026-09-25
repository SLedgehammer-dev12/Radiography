#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Digitizes the ISO 17636 Annex A exposure-count figures (A.1-A.4).

The figures are vector graphics inside the standard PDFs. This tool extracts
the curve polylines, calibrates them against the plot axes and writes JSON
tables consumed by ``src/core/annex_a.py``.

Usage (repository root, standards PDFs present)::

    python3 tools/digitize_annex_a.py            # writes src/core/data/*.json
    python3 tools/digitize_annex_a.py --overlay  # + visual validation PNGs
"""

import argparse
import json
import math
import os
import sys

import fitz

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Axis reference lines in PDF points (calibration uses the tick marks on them).
X_AXIS_PT = 86.8    # vertical axis (t/De = 0 line)
Y_AXIS_PT = 592.4   # horizontal axis (De/f or De/SFD = 0 line)
PLOT_RIGHT_PT = 371.7  # right edge of the grid (t/De = 0.25)

FIGURES = {
    "A1": {
        "pdf": "ISO 17636-1-2022.pdf", "page": 30,
        "x_max": 0.25, "y_max": 4.0, "y_axis": "De_f", "y_label_count": 9, "slope_min": 0.05, "slope_max": 1.6, "n_increases_up": True,
        "n_min": 8, "n_max": 24, "has_n1_line": False,
    },
    "A2": {
        "pdf": "ISO 17636-1-2022.pdf", "page": 31,
        "x_max": 0.25, "y_max": 2.0, "y_axis": "De_SFD", "y_label_count": 11, "slope_min": -1.0, "slope_max": -0.04, "n_increases_up": False,
        "n_min": 2, "n_max": 10, "has_n1_line": True,
    },
    "A3": {
        "pdf": "ISO 17636-1-2022.pdf", "page": 32,
        "x_max": 0.25, "y_max": 4.0, "y_axis": "De_f", "y_label_count": 9, "slope_min": 0.05, "slope_max": 1.6, "n_increases_up": True,
        "n_min": 6, "n_max": 18, "has_n1_line": False,
    },
    "A4": {
        "pdf": "ISO 17636-1-2022.pdf", "page": 33,
        "x_max": 0.25, "y_max": 2.0, "y_axis": "De_SFD", "y_label_count": 11, "slope_min": -1.0, "slope_max": -0.04, "n_increases_up": False,
        "n_min": 2, "n_max": 8, "has_n1_line": True,
    },
}

X_SAMPLES = [round(0.0025 * i, 4) for i in range(0, 101)]  # 0 .. 0.25


def collect_segments(page):
    segments = []
    for drawing in page.get_drawings():
        if drawing.get("type") != "s":
            continue
        for item in drawing.get("items", []):
            op = item[0]
            if op == "l":
                p1, p2 = item[1], item[2]
            elif op == "c":
                p1, p2 = item[1], item[4]
            else:
                continue
            segments.append((p1.x, p1.y, p2.x, p2.y))
    return segments


def diagonal_segments(segments, min_dx=1.0):
    out = []
    for x1, y1, x2, y2 in segments:
        if x2 < x1:
            x1, y1, x2, y2 = x2, y2, x1, y1
        dx = x2 - x1
        dy = y2 - y1
        if dx < min_dx or abs(dy) < 0.8:
            continue
        out.append((x1, y1, x2, y2))
    return out


def cluster_curves(segments, slope_tol=0.12, intercept_tol=4.0):
    """Groups collinear segments (curve strokes, dashes, double lines).

    Works better than endpoint chaining for the Annex A figures: the curves
    are near-straight, dashes have gaps and hatching is a different slope.
    """
    items = []
    for x1, y1, x2, y2 in segments:
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1
        items.append((slope, intercept, (x1, y1, x2, y2)))
    items.sort(key=lambda item: item[1])

    clusters = []
    for slope, intercept, segment in items:
        placed = False
        for cluster in clusters:
            if (abs(cluster["slope"] - slope) <= slope_tol and
                    abs(cluster["intercept"] - intercept) <= intercept_tol):
                cluster["segments"].append(segment)
                cluster["slope"] = 0.5 * (cluster["slope"] + slope)
                cluster["intercept"] = 0.5 * (cluster["intercept"] + intercept)
                placed = True
                break
        if not placed:
            clusters.append({
                "slope": slope,
                "intercept": intercept,
                "segments": [segment],
            })
    return [sorted(cluster["segments"], key=lambda seg: seg[0]) for cluster in clusters]


def _segment_slope(seg):
    return (seg[3] - seg[1]) / max(seg[2] - seg[0], 1e-6)


def build_chains(segments, tolerance=1.2, slope_tol=0.5):
    """Endpoint chaining that refuses to join segments of different slope.

    This keeps curve strokes from being connected to hatching lines that touch
    them inside the Annex A hatched (physically invalid) regions.
    """
    chains = []
    for seg in segments:
        x1, y1, x2, y2 = seg
        slope = _segment_slope(seg)
        attached = False
        for chain in chains:
            if abs(_segment_slope(chain[-1]) - slope) > slope_tol:
                continue
            lx, ly = chain[-1][2], chain[-1][3]
            if abs(lx - x1) <= tolerance and abs(ly - y1) <= tolerance:
                chain.append(seg)
                attached = True
                break
            if abs(_segment_slope(chain[0]) - slope) > slope_tol:
                continue
            fx, fy = chain[0][0], chain[0][1]
            if abs(fx - x2) <= tolerance and abs(fy - y2) <= tolerance:
                chain.insert(0, seg)
                attached = True
                break
        if not attached:
            chains.append([seg])
    return chains


def chain_extent(chain):
    xs = [chain[0][0]] + [s[2] for s in chain]
    return min(xs), max(xs)


def detect_labels(page, x0, x1, y0, y1, y_max):
    """Small filled glyph clusters inside the plot = N curve labels."""
    points = []
    for drawing in page.get_drawings():
        if drawing.get("type") != "f":
            continue
        rect = drawing["rect"]
        if not (0.5 < rect.width < 22 and 3 < rect.height < 20):
            continue
        cx = (rect.x0 + rect.x1) / 2.0
        cy = (rect.y0 + rect.y1) / 2.0
        if not (x0 < cx < x1 and y1 < cy < y0):
            continue
        points.append((cx, cy))
    # group glyphs of the same label (e.g. "1" and "0" of "10")
    groups = []
    for cx, cy in sorted(points, key=lambda point: (point[1], point[0])):
        placed = False
        for group in groups:
            gx = sum(point[0] for point in group) / len(group)
            gy = sum(point[1] for point in group) / len(group)
            if abs(cy - gy) <= 12 and abs(cx - gx) <= 30:
                group.append((cx, cy))
                placed = True
                break
        if not placed:
            groups.append([(cx, cy)])
    labels = []
    for group in groups:
        cy = sum(point[1] for point in group) / len(group)
        cx = sum(point[0] for point in group) / len(group)
        value = (y0 - cy) / ((y0 - y1) / y_max)
        if value > y_max - 0.04:  # "N = 1" caption
            continue
        labels.append((round(value, 4), round(cx, 1)))
    return labels


def chain_monotonic_ratio(chain):
    """|dy| travelled / |net dy|; hatching zigzags score much higher than 1."""
    ordered = _sort_chain(chain)
    travelled = sum(abs(seg[3] - seg[1]) for seg in ordered)
    net = abs(ordered[-1][3] - ordered[0][1])
    return travelled / max(net, 0.5)


def _sort_chain(chain):
    return sorted(chain, key=lambda s: s[0])


def chain_line(chain):
    ordered = _sort_chain(chain)
    x1, y1 = ordered[0][0], ordered[0][1]
    x2, y2 = ordered[-1][2], ordered[-1][3]
    if abs(x2 - x1) < 1e-6:
        return None
    slope = (y2 - y1) / (x2 - x1)
    return slope, y1 - slope * x1


def merge_curves(chains, gap=16.0, intercept_tol=2.0, slope_tol=0.25):
    """Joins dashed pieces and double stroke lines belonging to one curve."""
    merged = [_sort_chain(list(chain)) for chain in chains]
    for _ in range(4):
        result = []
        for chain in merged:
            xa, xb = chain_extent(chain)
            line_a = chain_line(chain)
            placed = False
            for target in result:
                ta, tb = chain_extent(target)
                line_b = chain_line(target)
                if line_a is None or line_b is None:
                    continue
                gap_ok = xa <= tb + gap and ta <= xb + gap
                if not gap_ok:
                    continue
                if (abs(line_a[0] - line_b[0]) <= slope_tol and
                        abs(line_a[1] - line_b[1]) <= intercept_tol):
                    overlap = min(xb, tb) - max(xa, ta)
                    shorter = max(1e-6, min(xb - xa, tb - ta))
                    if overlap > 0.5 * shorter:
                        # Duplicate stroke of the same curve: keep the longer one.
                        if xb - xa > tb - ta:
                            target.clear()
                            target.extend(chain)
                            target.sort(key=lambda s: s[0])
                    else:
                        target.extend(chain)
                        target.sort(key=lambda s: s[0])
                    placed = True
                    break
            if not placed:
                result.append(chain)
        merged = result
    return merged


def merge_collinear(chains, y_tolerance=5.0):
    """Merges dashed sub-chains and the double stroke lines of one curve."""
    merged = [_sort_chain(list(chain)) for chain in chains]
    for _ in range(3):  # repeat until stable
        result = []
        for chain in merged:
            x_min, x_max = chain_extent(chain)
            placed = False
            for target in result:
                tx_min, tx_max = chain_extent(target)
                if x_max < tx_min - 2 or x_min > tx_max + 2:
                    continue
                ref_x = max(x_min, tx_min)
                y_a = chain_y_at(chain, ref_x)
                y_b = chain_y_at(target, ref_x)
                if y_a is not None and y_b is not None and abs(y_a - y_b) <= y_tolerance:
                    target.extend(chain)
                    target.sort(key=lambda s: s[0])
                    placed = True
                    break
            if not placed:
                result.append(chain)
        merged = result
    return merged


def chain_y_at(chain, x):
    for x1, y1, x2, y2 in chain:
        if x1 - 0.01 <= x <= x2 + 0.01:
            if abs(x2 - x1) < 1e-6:
                return y1
            t = (x - x1) / (x2 - x1)
            return y1 + t * (y2 - y1)
    return None


def resample_chain(chain, x0, x_scale, y_to_value):
    samples = []
    for x_data in X_SAMPLES:
        x_pt = x0 + x_data * x_scale
        y_pt = chain_y_at(chain, x_pt)
        if y_pt is None:
            samples.append(None)
        else:
            samples.append(round(y_to_value(y_pt), 4))
    return samples


def axis_calibration(page, x_max, y_max, y_label_count):
    """Calibrates the axes from the y-axis label glyph clusters.

    The numeric labels (vector outlines) sit left of the vertical axis; their
    vertical centres are evenly spaced between the y_max and 0 grid lines.
    X limits come from the long vertical grid lines.
    """
    # Vertical grid lines first: the leftmost is the t/De = 0 axis, so the
    # numeric y labels can be restricted to the left margin only.
    v_lines = []
    for drawing in page.get_drawings():
        if drawing.get("type") != "s":
            continue
        for item in drawing.get("items", []):
            if item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            if abs(p1.x - p2.x) < 0.4 and abs(p2.y - p1.y) > 400:
                v_lines.append((p1.x + p2.x) / 2.0)
    v_lines = sorted(set(round(x, 1) for x in v_lines))
    if len(v_lines) < 3:
        raise RuntimeError(f"x grid detection failed: {v_lines}")
    axis_x = min(v_lines)

    clusters = []
    for drawing in page.get_drawings():
        if drawing.get("type") != "f":
            continue
        rect = drawing["rect"]
        if 0.5 < rect.width < 28 and 2 < rect.height < 20:
            if 40 < rect.x0 and rect.x1 < axis_x - 1:
                clusters.append((rect.y0 + rect.y1) / 2.0)
    clusters.sort()
    groups = []
    for y in clusters:
        if groups and y - groups[-1][-1] <= 8:
            groups[-1].append(y)
        else:
            groups.append([y])
    centres = [sum(group) / len(group) for group in groups]
    # Drop the axis title cluster (topmost) and keep the numeric labels.
    if len(centres) > y_label_count:
        centres = centres[-y_label_count:]
    if len(centres) != y_label_count:
        raise RuntimeError(f"y label detection failed: {centres}")

    y0 = max(centres)   # value 0
    y1 = min(centres)   # value y_max
    x0 = min(v_lines)   # value 0
    x1 = max(v_lines)   # value x_max
    return x0, x1, y0, y1, centres, v_lines


def digitize(figure, overlay=False):
    config = FIGURES[figure]
    pdf_path = os.path.join(ROOT, config["pdf"])
    doc = fitz.open(pdf_path)
    page = doc[config["page"] - 1]

    x0, x1, y0, y1, y_labels, v_lines = axis_calibration(
        page, config["x_max"], config["y_max"], config["y_label_count"])
    x_scale = (x1 - x0) / config["x_max"]
    y_scale = (y0 - y1) / config["y_max"]
    print(f"  calibration x=[{x0},{x1}] y=[{y0},{y1}] labels={len(y_labels)} vgrid={len(v_lines)}")

    def y_to_value(y_pt):
        return (y0 - y_pt) / y_scale

    # Keep only segments inside the plot area (excludes the schematic drawing
    # and its leader/dimension lines on the right-hand side).
    def in_plot(seg):
        return (seg[0] >= x0 - 3 and seg[2] <= x1 + 3 and
                seg[1] >= y1 - 3 and seg[3] <= y0 + 3)

    segments = [s for s in diagonal_segments(collect_segments(page)) if in_plot(s)]
    chains = build_chains(segments)
    # Drop hatching (steep opposite slope in A.2/A.4) and stray marks.
    def slope_ok(chain):
        line = chain_line(chain)
        if line is None:
            return False
        return config["slope_min"] <= line[0] <= config["slope_max"]

    chains = [c for c in chains if slope_ok(c)]
    chains = [c for c in chains if chain_extent(c)[1] - chain_extent(c)[0] > 25.0]
    chains = merge_curves(chains)
    chains = [c for c in chains if slope_ok(c)]
    chains = [c for c in chains if chain_monotonic_ratio(c) < 1.3]
    chains = [c for c in chains if chain_extent(c)[1] - chain_extent(c)[0] > 60.0]

    # Sort top-down by the y value at the left edge.
    def left_y(chain):
        value = chain_y_at(chain, x0 + 2.0)
        if value is None:
            value = chain_y_at(chain, chain_extent(chain)[0])
        return value

    chains.sort(key=left_y)

    # Curve labels (small filled glyphs) are placed above their curves; their
    # y-order matches the N sequence, which gives an unambiguous assignment.
    label_points = detect_labels(page, x0, x1, y0, y1, config["y_max"])
    label_points.sort(key=lambda item: item[0], reverse=True)
    if config["n_increases_up"]:
        label_ns = list(range(config["n_max"], config["n_min"] - 1, -1))
    else:
        label_ns = list(range(config["n_min"], config["n_max"] + 1))
    labels = []
    for (value, x_pt), n in zip(label_points, label_ns):
        labels.append({"n": n, "value": value, "x": x_pt})
    if len(labels) != len(label_ns):
        print(f"  WARNING {figure}: detected {len(labels)} labels, expected {len(label_ns)}")

    curves = {}
    if config["has_n1_line"]:
        curves["1"] = [round(config["y_max"], 4)] * len(X_SAMPLES)

    assigned = {}
    synthetic = set()
    for chain in chains:
        best = None
        for label in labels:
            y_curve = chain_y_at(chain, label["x"])
            if y_curve is None:
                continue
            distance = abs(y_curve - (y0 - label["value"] * y_scale))
            if best is None or distance < best[0]:
                best = (distance, label["n"])
        if best is None:
            continue
        n = best[1]
        if n in assigned:
            # Duplicate stroke of the same curve: keep the closer one.
            if best[0] >= assigned[n][0]:
                continue
        assigned[n] = (best[0], chain)

    missing = [n for n in label_ns if n not in assigned]

    # Labels are drawn a roughly constant distance above their curve. For a
    # label whose stroke was not captured (heavily dashed/hatched curves) the
    # curve is reconstructed as a line through the offset label point using the
    # slope of the nearest assigned neighbour (marked "synthetic" in the JSON).
    if assigned:
        offsets = []
        for label in labels:
            if label["n"] in assigned:
                chain = assigned[label["n"]][1]
                y_curve = chain_y_at(chain, label["x"])
                if y_curve is not None:
                    offsets.append(y_curve - (y0 - label["value"] * y_scale))
        offset = sum(offsets) / len(offsets) if offsets else 0.0
        synthetic = set()
        for label in labels:
            if label["n"] in assigned:
                continue
            neighbours = [n for n in assigned if abs(n - label["n"]) <= 3]
            if not neighbours:
                neighbours = list(assigned)
            reference = min(neighbours, key=lambda n: abs(n - label["n"]))
            slope, _intercept = chain_line(assigned[reference][1])
            anchor_y = y0 - label["value"] * y_scale - offset
            anchor_x = label["x"]
            segments = []
            for x_data in X_SAMPLES:
                x_pt = x0 + x_data * x_scale
                y_pt = anchor_y + slope * (x_pt - anchor_x)
                value = (y0 - y_pt) / y_scale
                if -0.02 <= value <= config["y_max"] + 0.02:
                    segments.append((x_pt, y_pt, x_pt + 0.01, y_pt + 0.01 * slope))
            if segments:
                assigned[label["n"]] = (999.0, segments)
                synthetic.add(label["n"])
        missing = [n for n in label_ns if n not in assigned]
        if missing:
            print(f"  WARNING {figure}: no curve for N={missing}")
        if synthetic:
            print(f"  note {figure}: reconstructed N={sorted(synthetic)} from labels")

    for n, (_distance, chain) in assigned.items():
        curves[str(n)] = resample_chain(chain, x0, x_scale, y_to_value)

    # Enforce the physical ordering per x column (extraction noise can make
    # neighbouring near-parallel curves cross by a few thousandths).
    n_ascending = sorted(int(n) for n in curves)
    for index in range(len(X_SAMPLES)):
        present = [
            (n, curves[str(n)][index])
            for n in n_ascending
            if curves[str(n)][index] is not None
        ]
        values = sorted(value for _, value in present)
        if not config["n_increases_up"]:
            values = list(reversed(values))
        for (n, _old), value in zip(present, values):
            curves[str(n)][index] = round(value, 4)

    result = {
        "figure": figure,
        "source": f"{config['pdf']} p.{config['page']}",
        "x_axis": "t/De",
        "y_axis": config["y_axis"],
        "x_max": config["x_max"],
        "y_max": config["y_max"],
        "x": X_SAMPLES,
        "curves": curves,
        "synthetic": sorted(synthetic) if assigned else [],
    }

    if overlay:
        for chain in chains:
            shape = page.new_shape()
            shape.draw_polyline([fitz.Point(s[0], s[1]) for s in chain])
            shape.finish(color=(1, 0, 0), width=0.8)
            shape.commit()
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=fitz.Rect(55, 55, 545, 650))
        out = os.path.join(ROOT, "tools", f"annex_a_overlay_{figure}.png")
        pix.save(out)
        print(f"  overlay: {out}")

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", action="store_true")
    parser.add_argument("--figure", default=None, choices=sorted(FIGURES))
    args = parser.parse_args()

    data_dir = os.path.join(ROOT, "src", "core", "data")
    os.makedirs(data_dir, exist_ok=True)

    figures = [args.figure] if args.figure else sorted(FIGURES)
    combined = {}
    for figure in figures:
        print(f"Digitizing {figure} ...")
        result = digitize(figure, overlay=args.overlay)
        combined[figure] = result
        counts = {k: sum(1 for v in vals if v is not None) for k, vals in result["curves"].items()}
        print(f"  curves: {sorted(result['curves'], key=int)} samples: {counts}")

    out_path = os.path.join(data_dir, "annex_a_iso17636_1.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(combined, handle, ensure_ascii=False, indent=1)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
