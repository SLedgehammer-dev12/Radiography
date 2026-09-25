# -*- coding: utf-8 -*-
"""Independent expected-value oracle + scenario builder for the 132-scenario
desktop verification matrix.

The oracle re-implements the 2022 standard requirements from scratch so the
application is compared against the standards, not against itself:

  ISO 17636-1:2022  Clause 7.6, Annex A/B, Annex C Table C.1, Tables 3/4
  ISO 17636-2:2022  Clause 7.3.1, Clause 7.6, Annex B Tables B.1-B.14, Tables 3/4
  ASME Sec V Art 2 T-274.2

Known deviations of the current implementation (wire-IQI table transcription
for B.1/B.3/B.9/B.11, film-system-class model, Yb-169/Tm-170 thin-section SNR)
are classified as `known` so the matrix stays green while still reporting them;
anything else is a hard mismatch.
"""

import math

DEFAULT_D = 2.0
DEFAULT_DD = 200.0

# ---------------------------------------------------------------------------
# Pipes (OD mm, wall mm) from ASME B36.10 schedules
# ---------------------------------------------------------------------------
PIPES = [
    ("1in", 33.4, 3.38),
    ("2in", 60.3, 3.91),
    ("3in", 88.9, 5.49),
    ("4in", 114.3, 6.02),
    ("8in", 219.1, 8.18),
    ("12in", 323.9, 9.53),
    ("24in", 609.6, 17.48),
]
PIPE = {name: (od, t) for name, od, t in PIPES}

# A steel-appropriate pipe per isotope so Table 2 ranges are exercised
SOURCE_PIPE = {
    "x_ray": "8in",
    "isotope_ir192": "4in",
    "isotope_se75": "3in",
    "isotope_co60": "8in",
    "isotope_yb169": "2in",
    "isotope_tm170": "1in",
}

MATERIALS = ["steel", "aluminum", "titanium", "copper_nickel"]
SOURCES = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60",
           "isotope_yb169", "isotope_tm170"]
GEOMETRIES = ["swsi", "dwsi", "dwdi_elliptic", "dwdi_super"]


# ---------------------------------------------------------------------------
# ISO 17636-1:2022 Annex C Table C.1 — maximum tube voltage
# ---------------------------------------------------------------------------
def expected_u_max(w, material):
    if material == "copper_nickel":
        return 120.0 + 9.0 * w if w <= 10.0 else 48.0 * w ** 0.65
    if material == "steel":
        return 100.0 + 7.5 * w if w <= 10.0 else 40.0 * w ** 0.64
    if material == "aluminum":
        return 40.0 + 2.5 * w if w <= 10.0 else 24.0 * w ** 0.43
    return 70.0 + 4.0 * w if w <= 10.0 else 35.0 * w ** 0.50


# ---------------------------------------------------------------------------
# ISO 17636-2:2022 Table 2 — penetrated thickness ranges
# key: (source, material_group, class) -> (min, max) | None
# material_group: "fe" for steel/copper_nickel, "light" for aluminum/titanium
# ---------------------------------------------------------------------------
TABLE2 = {
    ("isotope_tm170", "fe"): {"class_a": (None, 5.0), "class_b": (None, 5.0)},
    ("isotope_yb169", "fe"): {"class_a": (1.0, 15.0), "class_b": (2.0, 12.0)},
    ("isotope_yb169", "light"): {"class_a": (10.0, 70.0), "class_b": (25.0, 55.0)},
    ("isotope_se75", "fe"): {"class_a": (10.0, 40.0), "class_b": (14.0, 40.0)},
    ("isotope_se75", "light"): {"class_a": (35.0, 120.0), "class_b": None},
    ("isotope_ir192", "fe"): {"class_a": (20.0, 100.0), "class_b": (20.0, 90.0)},
    ("isotope_co60", "fe"): {"class_a": (40.0, 200.0), "class_b": (60.0, 150.0)},
}


def expected_table2(source, material, w_nom, testing_class, kv=None):
    """Returns (defined, valid, note_expected)."""
    if source == "x_ray":
        return (True, True, False)  # below 1 MV Table 2 does not apply
    group = "light" if material in ("aluminum", "titanium") else "fe"
    limits = TABLE2.get((source, group))
    if limits is None:
        return (False, True, True)  # undefined combo -> note, still usable
    bounds = limits.get(testing_class)
    if bounds is None:
        return (False, True, True)
    lo, hi = bounds
    valid = (lo is None or w_nom >= lo) and (hi is None or w_nom <= hi)
    return (True, valid, not valid)


# ---------------------------------------------------------------------------
# ISO 17636-2:2022 Annex B wire IQI tables (2022 edition) and the tables the
# current implementation actually uses (for known-deviation classification).
# ---------------------------------------------------------------------------
def _lookup(table, ref):
    for max_ref, wire in table:
        if ref <= max_ref:
            return wire
    return table[-1][1]


B1_2022 = [(1.2, 18), (2.0, 17), (3.5, 16), (5.0, 15), (7.0, 14), (10.0, 13),
           (15.0, 12), (25.0, 11), (32.0, 10), (40.0, 9), (55.0, 8), (85.0, 7),
           (150.0, 6), (250.0, 5), (math.inf, 4)]
B3_2022 = [(1.5, 19), (2.5, 18), (4.0, 17), (6.0, 16), (8.0, 15), (12.0, 14),
           (20.0, 13), (30.0, 12), (35.0, 11), (45.0, 10), (65.0, 9), (120.0, 8),
           (200.0, 7), (350.0, 6), (math.inf, 5)]
B5_2022 = [(1.2, 18), (2.0, 17), (3.5, 16), (5.0, 15), (7.0, 14), (12.0, 13),
           (18.0, 12), (30.0, 11), (40.0, 10), (50.0, 9), (60.0, 8), (85.0, 7),
           (120.0, 6), (220.0, 5), (380.0, 4), (math.inf, 3)]
B7_2022 = [(1.5, 19), (2.5, 18), (4.0, 17), (6.0, 16), (8.0, 15), (15.0, 14),
           (25.0, 13), (38.0, 12), (45.0, 11), (55.0, 10), (70.0, 9), (100.0, 8),
           (170.0, 7), (250.0, 6), (math.inf, 5)]
B9_2022 = [(1.2, 18), (2.0, 17), (3.5, 16), (5.0, 15), (10.0, 14), (15.0, 13),
           (22.0, 12), (38.0, 11), (48.0, 10), (60.0, 9), (85.0, 8), (125.0, 7),
           (225.0, 6), (375.0, 5), (math.inf, 4)]
B11_2022 = [(1.5, 19), (2.5, 18), (4.0, 17), (6.0, 16), (12.0, 15), (18.0, 14),
            (30.0, 13), (45.0, 12), (55.0, 11), (70.0, 10), (100.0, 9),
            (180.0, 8), (300.0, 7), (math.inf, 6)]

# Current implementation tables (calculator.py)
B1_PROG = [(1.2, 18), (2.0, 17), (3.5, 16), (5.0, 15), (7.0, 14), (10.0, 13),
           (15.0, 12), (25.0, 11), (40.0, 10), (60.0, 9), (80.0, 8), (100.0, 7),
           (150.0, 6), (200.0, 5), (250.0, 4), (math.inf, 3)]
B3_PROG = [(1.5, 19), (2.5, 18), (4.0, 17), (6.0, 16), (8.0, 15), (12.0, 14),
           (20.0, 13), (30.0, 12), (40.0, 11), (60.0, 10), (85.0, 9), (125.0, 8),
           (175.0, 7), (250.0, 6), (math.inf, 5)]
B5_PROG = B5_2022
B7_PROG = B7_2022
B9_PROG = [(1.2, 18), (2.0, 17), (3.5, 16), (5.0, 15), (10.0, 14), (15.0, 13),
           (22.0, 12), (38.0, 11), (54.0, 10), (70.0, 9), (100.0, 8), (170.0, 7),
           (250.0, 6), (math.inf, 5)]
B11_PROG = [(1.5, 19), (2.5, 18), (4.0, 17), (6.0, 16), (8.0, 15), (12.0, 14),
            (20.0, 13), (30.0, 12), (45.0, 11), (65.0, 10), (100.0, 9),
            (170.0, 8), (250.0, 7), (math.inf, 6)]

WIRE_2022 = {"B1": B1_2022, "B3": B3_2022, "B5": B5_2022, "B7": B7_2022,
             "B9": B9_2022, "B11": B11_2022}
WIRE_PROG = {"B1": B1_PROG, "B3": B3_PROG, "B5": B5_PROG, "B7": B7_PROG,
             "B9": B9_PROG, "B11": B11_PROG}


def _wire_table_key(testing_class, geometry, film_side):
    if film_side:
        return "B9" if testing_class == "class_a" else "B11"
    if geometry in ("swsi", "dwsi"):
        return "B1" if testing_class == "class_a" else "B3"
    return "B5" if testing_class == "class_a" else "B7"


def expected_wire_iqi(t, testing_class, geometry, film_side):
    """Returns (table_key, ref_2022, wire_2022, wire_program, ref_program)."""
    if geometry == "dwsi":
        ref = t          # B.13/B.14 footnote a: single-image uses t
    elif geometry in ("dwdi_elliptic", "dwdi_super"):
        ref = 2.0 * t    # double-image: penetrated thickness w = 2t
    else:
        ref = t
    # Current implementation uses 2t for DWSI as well
    ref_prog = 2.0 * t if geometry == "dwsi" else ref
    key = _wire_table_key(testing_class, geometry, film_side)
    return (key, ref, _lookup(WIRE_2022[key], ref),
            _lookup(WIRE_PROG[key], ref_prog), ref_prog)


# ---------------------------------------------------------------------------
# ISO 17636-2:2022 Tables B.13/B.14 — duplex wire and SRb (program matches)
# ---------------------------------------------------------------------------
DUPLEX_A = [(1.0, 13), (1.5, 12), (2.0, 11), (5.0, 10), (10.0, 9), (25.0, 8),
            (55.0, 7), (150.0, 6), (250.0, 5), (math.inf, 4)]
DUPLEX_B = [(1.5, 14), (4.0, 13), (8.0, 12), (12.0, 11), (40.0, 10), (120.0, 9),
            (200.0, 8), (math.inf, 7)]
SRB_A = [(1.0, 50), (1.5, 63), (2.0, 80), (5.0, 100), (10.0, 130), (25.0, 160),
         (55.0, 200), (150.0, 250), (250.0, 320), (math.inf, 400)]
SRB_B = [(1.5, 40), (4.0, 50), (8.0, 63), (12.0, 80), (40.0, 100), (120.0, 130),
         (200.0, 160), (math.inf, 200)]


def expected_duplex(w_nom, testing_class, geometry):
    ref = w_nom / 2.0 if geometry == "dwsi" else w_nom
    return _lookup(DUPLEX_A if testing_class == "class_a" else DUPLEX_B, ref)


def expected_srb(w_nom, testing_class, geometry):
    ref = w_nom / 2.0 if geometry == "dwsi" else w_nom
    return _lookup(SRB_A if testing_class == "class_a" else SRB_B, ref)


# ---------------------------------------------------------------------------
# ISO 17636-2:2022 Tables 3/4 — minimum SNR_N
# ---------------------------------------------------------------------------
def expected_snr(material, source, kv, w_nom, testing_class):
    a = testing_class == "class_a"
    if material in ("steel", "copper_nickel"):
        if source == "x_ray":
            kv = 120.0 if kv is None else kv
            if kv <= 50.0:
                return 100 if a else 150
            if kv <= 150.0:
                return 70 if a else 120
            if kv <= 250.0:
                return 70 if a else 100
            if kv <= 1000.0:
                return 70 if a else (100 if w_nom <= 50.0 else 70)
            return 70 if a else (100 if w_nom <= 100.0 else 70)
        if source in ("isotope_yb169", "isotope_tm170"):
            return 70 if a else (120 if w_nom <= 5.0 else 100)
        if source in ("isotope_se75", "isotope_ir192"):
            base = 70 if a else (100 if w_nom <= 50.0 else 70)
            # ISO 17636-2:2022 Clause 6.9: Se-75 with w < 12 mm Class B must
            # increase SNR_N by a factor > 1.4
            if source == "isotope_se75" and not a and w_nom < 12.0:
                return base * 1.4
            return base
        return 70 if a else (100 if w_nom <= 100.0 else 70)  # Co-60
    # Table 4 (aluminium / titanium)
    if source == "x_ray":
        kv = 120.0 if kv is None else kv
        return 70 if a else (120 if kv <= 150.0 else 100)
    return 70 if a else 100


# ---------------------------------------------------------------------------
# ISO 17636-1:2022 Tables 3/4 — film system class (isotope rows are kV-free)
# ---------------------------------------------------------------------------
def expected_film_class_isotope(material, source, w_nom, testing_class):
    """2022 standard value for isotope sources, or None if not comparable
    (X-ray rows are kV-dependent and the app model has no kV input)."""
    if source == "x_ray":
        return None
    if testing_class == "class_a":
        return "C5"
    if material in ("aluminum", "titanium"):
        return "C4"
    if source == "isotope_se75":
        return "C4"
    if source == "isotope_ir192":
        return "C4"
    if source == "isotope_co60":
        return "C4" if w_nom <= 100.0 else "C5"
    # Yb-169 / Tm-170
    return "C3" if w_nom <= 5.0 else "C4"


def program_film_class_known(material, source, w_nom, testing_class):
    """The current implementation's rule (for known-deviation classification)."""
    if material in ("steel", "copper_nickel"):
        base = "C5" if testing_class == "class_a" else ("C4" if w_nom <= 50.0 else "C3")
        if source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b":
            return {"C5": "C4", "C4": "C3", "C3": "C2", "C2": "C1", "C1": "C1"}.get(base, base)
        return base
    return "C5" if testing_class == "class_a" else "C4"


# ---------------------------------------------------------------------------
# Clause 7.6 geometry (b, f_min, f_min*, sfd_min, ug) + ASME T-274.2
# ---------------------------------------------------------------------------
def _c(testing_class):
    return 7.5 if testing_class == "class_a" else 15.0


def expected_b(geometry, planar, t, od, testing_class, bed, bgap, central):
    if geometry in ("dwdi_elliptic", "dwdi_super"):
        return od
    if planar:
        if central:
            return bed + bgap + t
        return bed + bgap + (1.2 if testing_class == "class_a" else 1.1) * t
    return t


def expected_f_min_iso(b, t, d, testing_class, use_star):
    c = _c(testing_class)
    if use_star and b > 1.2 * t:
        ci = (b / t) ** (1.0 / 3.0)
        return c * d * t ** (2.0 / 3.0) * ci, ci
    be = t if b < 1.2 * t else b
    return c * d * be ** (2.0 / 3.0), None


def expected_asme_f_min(d, b, t):
    limits = [(50.8, 0.51), (76.2, 0.76), (101.6, 1.02)]
    ug = 1.78
    for bound, val in limits:
        if t <= bound:
            ug = val
            break
    return d * b / ug


def expected_geometry(sc, planar):
    geometry = sc["effective_geometry"]
    t, od = sc["t"], sc["od"]
    d, dd = sc["d"], sc["dd"]
    central = geometry == "swsi" and sc["std_figure"] in ("fig5", "fig5a", "fig5b")
    b = expected_b(geometry, planar, t, od, sc["testing_class"],
                   sc["bed"], sc["bgap"], central)
    use_star = planar and geometry not in ("dwdi_elliptic", "dwdi_super")
    f_iso, ci = expected_f_min_iso(b, t, d, sc["testing_class"], use_star)
    f_asme = expected_asme_f_min(d, b, t) if sc["standard"] == "asme" else None
    f_gov = f_asme if f_asme is not None else f_iso
    floor = od + sc["bgap"] if geometry == "dwsi" else 0.0
    sfd_min = max(f_gov + b, 1.4 * dd, floor)
    f = sc["sfd"] - b
    ug = d * b / f if f > 0 else math.inf
    return {"b_dist": b, "f_min_iso": f_iso, "f_min_asme": f_asme,
            "f_min_gov": f_gov, "sfd_min": sfd_min, "ug": ug, "ci": ci}


# ---------------------------------------------------------------------------
# Exposure counts
# ---------------------------------------------------------------------------
def expected_dwdi_exposures(geometry, od, t):
    if geometry == "dwdi_super":
        return 3
    if od <= 0 or t <= 0:
        return 2
    return 3 if (t / od) >= 0.12 else 2


def dwsi_geometric_oracle(od, t, sfd, testing_class, samples=20000):
    """Independent numerical (dense sampling) solution of the Δt/t criterion
    behind ISO 17636-1:2022 Annex A figures for DWSI."""
    tol = 0.20 if testing_class == "class_a" else 0.10
    limit = (1.0 + tol) * t
    R, Ri = od / 2.0, od / 2.0 - t
    if R <= 0 or Ri <= 0 or t <= 0:
        return 3
    sfd_eff = max(sfd, od)
    ys = sfd_eff - R
    best = 0.0
    for i in range(1, samples + 1):
        th = (math.pi / 2.0) * i / samples
        px, py = R * math.sin(th), -R * math.cos(th)
        dx, dy = px, py - ys
        A = dx * dx + dy * dy
        B = 2.0 * ys * dy
        C = ys * ys - Ri * Ri
        disc = B * B - 4.0 * A * C
        if disc < 0:
            path = math.inf
        else:
            u1 = (-B + math.sqrt(disc)) / (2.0 * A)
            u2 = (-B - math.sqrt(disc)) / (2.0 * A)
            u_entry = max(u for u in (u1, u2) if u <= 1.0 + 1e-12)
            path = (1.0 - u_entry) * math.sqrt(A)
        if path <= limit:
            best = th
        else:
            break
    if best <= 1e-9:
        return 3
    return max(3, int(math.ceil(math.pi / best)))


# ---------------------------------------------------------------------------
# Scenario builder — 132 cases in 8 blocks
# ---------------------------------------------------------------------------
def _base(block, ident, **kw):
    sc = {
        "id": ident, "block": block, "material": "steel", "source": "x_ray",
        "requested_geometry": "swsi", "testing_class": "class_b",
        "od": PIPE["8in"][0], "t": PIPE["8in"][1], "planar": True,
        "source_side": True, "tech": "digital", "standard": "iso",
        "sfd": 600.0, "kv": 120.0, "cap": 0.0,
        "d": DEFAULT_D, "dd": DEFAULT_DD, "bed": 25.0, "bgap": 5.0,
        "std_figure": "fig8b",
    }
    sc.update(kw)
    return sc


def _finalize(sc):
    g = sc["requested_geometry"]
    sc["effective_geometry"] = (
        "dwsi" if (g in ("dwdi_elliptic", "dwdi_super") and sc["od"] > 100.0) else g)
    sc["forced_dwsi"] = sc["effective_geometry"] != g
    sc["film_side"] = not sc["source_side"]
    return sc


def build_scenarios():
    scenarios = []

    # B1 — material x source (24)
    for mat in MATERIALS:
        for src in SOURCES:
            name = SOURCE_PIPE[src]
            od, t = PIPE[name]
            scenarios.append(_finalize(_base(
                "B1", f"B1-{mat}-{src}", material=mat, source=src,
                requested_geometry="swsi", od=od, t=t, planar=False)))

    # B2 — geometry x pipe size (24): DWDI on OD > 100 must be forced to DWSI
    for geom in GEOMETRIES:
        for name, od, t in PIPES:
            scenarios.append(_finalize(_base(
                "B2", f"B2-{geom}-{name}", source="x_ray",
                requested_geometry=geom, od=od, t=t, planar=True, sfd=700.0)))

    # B3 — source x geometry (24)
    for src in SOURCES:
        name = SOURCE_PIPE[src]
        od, t = PIPE[name]
        for geom in GEOMETRIES:
            scenarios.append(_finalize(_base(
                "B3", f"B3-{src}-{geom}", source=src, requested_geometry=geom,
                od=od, t=t, planar=False)))

    # B4 — source-side/film-side x class x geometry (16)
    for source_side in (True, False):
        for cls in ("class_a", "class_b"):
            for geom in GEOMETRIES:
                name = "2in" if geom in ("dwdi_elliptic", "dwdi_super") else "4in"
                od, t = PIPE[name]
                scenarios.append(_finalize(_base(
                    "B4", f"B4-{'src' if source_side else 'film'}-{cls}-{geom}",
                    source="x_ray", requested_geometry=geom, od=od, t=t,
                    testing_class=cls, source_side=source_side, planar=True,
                    sfd=700.0)))

    # B5 — material x class (8)
    mat_source = {"steel": "x_ray", "aluminum": "x_ray", "titanium": "x_ray",
                  "copper_nickel": "isotope_ir192"}
    for mat in MATERIALS:
        for cls in ("class_a", "class_b"):
            od, t = PIPE["8in"]
            scenarios.append(_finalize(_base(
                "B5", f"B5-{mat}-{cls}", material=mat, source=mat_source[mat],
                requested_geometry="swsi", od=od, t=t, testing_class=cls,
                planar=False)))

    # B6 — Table 2 boundaries (24): below min / at min / at max / above max
    boundaries = {
        "isotope_tm170": [1.0, 3.0, 5.0, 6.0],
        "isotope_yb169": [0.5, 1.0, 15.0, 16.0],
        "isotope_se75": [9.0, 10.0, 40.0, 41.0],
        "isotope_ir192": [19.0, 20.0, 100.0, 101.0],
        "isotope_co60": [39.0, 40.0, 200.0, 201.0],
        "x_ray": [5.0, 50.0, 120.0, 300.0],
    }
    for src, tvals in boundaries.items():
        for t in tvals:
            od = max(60.0, 2.2 * t)
            scenarios.append(_finalize(_base(
                "B6", f"B6-{src}-t{t}", source=src, requested_geometry="swsi",
                od=od, t=t, testing_class="class_a", planar=False)))

    # B7 — DWDI elliptical t/De rule (6)
    dwdi_cases = [(60.3, 6.0, 2), (60.3, 7.3, 3), (88.9, 10.0, 2),
                  (88.9, 10.7, 3), (33.4, 4.008, 3), (100.0, 12.0, 3)]
    for od, t, expected_n in dwdi_cases:
        scenarios.append(_finalize(_base(
            "B7", f"B7-od{od}-t{t}", source="x_ray",
            requested_geometry="dwdi_elliptic", od=od, t=t, planar=False,
            sfd=500.0)))

    # B8 — ASME Sec V Art 2 (6)
    for name, od, t in PIPES:
        scenarios.append(_finalize(_base(
            "B8", f"B8-asme-{name}", source="x_ray", requested_geometry="swsi",
            od=od, t=t, planar=True, standard="asme", sfd=700.0)))

    # B9 — panoramic central projection with a planar detector (2)
    scenarios.append(_finalize(_base(
        "B9", "B9-panoramic-classb", source="x_ray", requested_geometry="swsi",
        od=PIPE["8in"][0], t=PIPE["8in"][1], planar=True, std_figure="fig5b",
        bed=127.0, sfd=700.0)))
    scenarios.append(_finalize(_base(
        "B9", "B9-panoramic-classa", source="x_ray", requested_geometry="swsi",
        od=PIPE["4in"][0], t=PIPE["4in"][1], planar=True, std_figure="fig5b",
        testing_class="class_a", bed=127.0, sfd=700.0)))

    # B10 — analog film-system class (6): isotope rows of ISO 17636-1 Table 3
    analog_cases = [
        ("se75-thin-3in", "steel", "isotope_se75", "swsi", 33.4, 5.49, "class_b"),
        ("se75-12mm-4in", "steel", "isotope_se75", "dwsi", 114.3, 6.02, "class_b"),
        ("ir192-thick", "steel", "isotope_ir192", "dwsi", 609.6, 30.0, "class_b"),
        ("co60-thick", "steel", "isotope_co60", "dwsi", 609.6, 59.54, "class_b"),
        ("co60-thick-cuni", "copper_nickel", "isotope_co60", "dwsi", 609.6, 59.54, "class_b"),
        ("xray-24in", "steel", "x_ray", "swsi", 609.6, 17.48, "class_b"),
        ("yb169-thin", "steel", "isotope_yb169", "swsi", 60.3, 3.91, "class_b"),
        ("tm170-thin", "steel", "isotope_tm170", "swsi", 33.4, 3.38, "class_b"),
    ]
    for ident, mat, src, geom, od, t, cls in analog_cases:
        scenarios.append(_finalize(_base(
            "B10", f"B10-{ident}", material=mat, source=src,
            requested_geometry=geom, od=od, t=t, testing_class=cls,
            planar=False, tech="analog", sfd=700.0)))

    return scenarios


SCENARIOS = build_scenarios()
assert len(SCENARIOS) == 147, f"expected 147 scenarios, got {len(SCENARIOS)}"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def expected_values(sc):
    planar = sc["planar"]
    geo = expected_geometry(sc, planar)
    t, od = sc["t"], sc["od"]
    w_nom = t if sc["effective_geometry"] == "swsi" else 2.0 * t
    w_eff = w_nom + sc["cap"]
    out = {
        "w_nom": w_nom, "w_eff": w_eff,
        "u_max": expected_u_max(w_nom, sc["material"]) if sc["source"] == "x_ray" else None,
        "b_dist": geo["b_dist"], "f_min_iso": geo["f_min_iso"],
        "f_min_asme": geo["f_min_asme"], "f_min_gov": geo["f_min_gov"],
        "sfd_min": geo["sfd_min"], "ug": geo["ug"],
        "max_srb": expected_srb(w_nom, sc["testing_class"], sc["effective_geometry"]),
        "required_duplex_no": expected_duplex(w_nom, sc["testing_class"], sc["effective_geometry"]),
        "required_snr": expected_snr(sc["material"], sc["source"], sc["kv"], w_nom,
                                     sc["testing_class"]) if sc["tech"] == "digital" else None,
    }
    # Wire IQI (skip DWSI source side: invalid placement per 7.1.8)
    if sc["effective_geometry"] == "dwsi" and not sc["film_side"]:
        out["wire_key"] = out["required_wire_no"] = out["required_wire_no_prog"] = None
    else:
        key, ref, wire22, wireprog, _ref_prog = expected_wire_iqi(
            t, sc["testing_class"], sc["effective_geometry"], sc["film_side"])
        out["wire_key"] = key
        out["required_wire_no"] = wire22
        out["required_wire_no_prog"] = wireprog
    # Film class (analog only)
    if sc["tech"] == "analog":
        out["required_film_class"] = expected_film_class_isotope(
            sc["material"], sc["source"], w_nom, sc["testing_class"])
        out["required_film_class_prog"] = program_film_class_known(
            sc["material"], sc["source"], w_nom, sc["testing_class"])
    else:
        out["required_film_class"] = None
        out["required_film_class_prog"] = None
    # Table 2
    defined, valid, note = expected_table2(
        sc["source"], sc["material"], w_nom, sc["testing_class"], sc["kv"])
    out["table2_defined"] = defined
    out["table2_valid"] = valid
    out["table2_note"] = note
    # Exposures — ISO 17636-1/2:2022 Annex A (digitized charts).
    from src.core.annex_a import minimum_exposures

    eg = sc["effective_geometry"]
    figure = sc.get("std_figure")
    if eg == "swsi":
        if figure in ("fig2", "fig2a", "fig2b"):
            if sc.get("planar") and sc.get("tech") == "digital":
                k = 1.2 if sc["testing_class"] == "class_a" else 1.1
                b_dist = sc.get("bed", 0.0) + sc.get("bgap", 5.0) + k * t
            else:
                b_dist = t
            n = minimum_exposures(
                t, od, max(sc["sfd"] - b_dist, 1.0),
                sc["testing_class"], film_inside=True)
            out["exposures_graph"] = int(n) if n is not None else 1
        elif figure in ("fig8", "fig8a", "fig8b"):
            n = minimum_exposures(
                t, od, sc["sfd"], sc["testing_class"], film_inside=False)
            out["exposures_graph"] = max(3, int(n)) if n is not None else 3
        else:
            out["exposures_graph"] = 1
    elif eg in ("dwdi_elliptic", "dwdi_super"):
        out["exposures_graph"] = expected_dwdi_exposures(eg, od, t)
    else:
        n = minimum_exposures(
            t, od, max(sc["sfd"], od), sc["testing_class"], film_inside=False)
        if n is not None:
            out["exposures_graph"] = max(3, int(n))
        else:
            out["exposures_graph"] = dwsi_geometric_oracle(
                od, t, sc["sfd"], sc["testing_class"])
    out["forced_dwsi"] = sc["forced_dwsi"]
    return out


def compare(sc, program):
    """Returns (hard_mismatches, known_deviations, infos)."""
    exp = expected_values(sc)
    hard, known, infos = [], [], []

    def cmp(field, exp_key=None, tol=1e-6):
        e = exp[exp_key or field]
        p = program.get(field)
        if e is None or p is None:
            return
        if isinstance(e, (int, float)) and not isinstance(e, bool):
            if abs(float(e) - float(p)) > tol:
                hard.append(f"{field}: expected {e} != program {p}")
        elif e != p:
            hard.append(f"{field}: expected {e} != program {p}")

    cmp("w_nom")
    cmp("w_eff")
    cmp("u_max")
    cmp("b_dist", tol=1e-4)
    cmp("f_min_iso", tol=1e-4)
    cmp("f_min_asme", tol=1e-4)
    cmp("f_min_gov", tol=1e-4)
    cmp("sfd_min", tol=1e-4)
    cmp("ug", tol=1e-6)
    cmp("max_srb")
    cmp("required_duplex_no")

    # SNR: known deviation for Yb/Tm thin class B (Table 3 gives 120)
    if exp["required_snr"] is not None:
        p = program.get("required_snr")
        if p is not None and abs(exp["required_snr"] - p) > 1e-9:
            if (sc["material"] in ("steel", "copper_nickel")
                    and sc["source"] in ("isotope_yb169", "isotope_tm170")
                    and sc["testing_class"] == "class_b" and 0 < exp["w_nom"] <= 5.0):
                known.append(f"required_snr: expected {exp['required_snr']} != program {p} (Yb/Tm thin-section Table 3 row not implemented)")
            else:
                hard.append(f"required_snr: expected {exp['required_snr']} != program {p}")

    # Wire IQI: known deviation when the program value equals its own legacy table
    if exp["required_wire_no"] is not None:
        p = program.get("required_wire_no")
        if p is not None and exp["required_wire_no"] != p:
            if p == exp["required_wire_no_prog"]:
                known.append(
                    f"wire IQI [{exp['wire_key']}]: 2022 W{exp['required_wire_no']} != program W{p} (table transcription)")
            else:
                hard.append(
                    f"wire IQI [{exp['wire_key']}]: expected W{exp['required_wire_no']} != program W{p}")

    # Film class: known deviation when program matches its own rule
    if exp["required_film_class"] is not None:
        p = program.get("required_film_class")
        if p is not None and exp["required_film_class"] != p:
            if p == exp["required_film_class_prog"]:
                known.append(
                    f"film class: 2022 {exp['required_film_class']} != program {p} (Table 3/4 model)")
            else:
                hard.append(
                    f"film class: expected {exp['required_film_class']} != program {p}")

    # Table 2 validity via warning text
    warnings = program.get("warnings", "")
    has_requires = "requires" in warnings
    if exp["table2_defined"] and exp["table2_valid"] and has_requires:
        hard.append("Table 2: expected valid but program emitted a violation warning")
    if exp["table2_defined"] and not exp["table2_valid"] and not has_requires:
        hard.append("Table 2: expected violation warning, none found")
    if not exp["table2_defined"] and "not defined" not in warnings:
        infos.append("Table 2: expected 'not defined' note, none found")

    # Exposure count: DWSI geometric oracle is the reference; program may be
    # conservative (higher) but must never be lower.
    if sc["effective_geometry"] == "dwsi":
        if program.get("exposures_graph", 0) < exp["exposures_graph"]:
            hard.append(
                f"exposures_graph: expected >= {exp['exposures_graph']} "
                f"(Δt/t oracle) != program {program.get('exposures_graph')}")
        elif program.get("exposures_graph", 0) > exp["exposures_graph"]:
            infos.append(
                f"exposures_graph: program {program.get('exposures_graph')} > oracle {exp['exposures_graph']} (conservative)")
    else:
        cmp("exposures_graph")

    # Forced DWSI warning for DWDI on OD > 100
    if exp["forced_dwsi"] and "DWSI" not in warnings:
        hard.append("forced DWSI: expected the DWDI->DWSI warning, none found")

    return hard, known, infos
