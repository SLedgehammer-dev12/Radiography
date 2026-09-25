# -*- coding: utf-8 -*-
"""Shared calculation engine for the desktop, mobile and web front-ends.

This module contains the single source of truth for the calculation
orchestration that used to live in ``src/ui/main_window.py`` (desktop) and
``src/mobile/lib/app_state.py`` (mobile). Both front-ends now feed a plain
form-state dict into :class:`CalculationEngine` and render the returned
result. The web build (Pyodide) uses exactly the same code path.

Form-state schema (all lengths in mm, activity in Ci, exposure time in s)::

    od, t, cap, weld_width, d, sfd, output_val, base_e,
    detector_type, film_class_used, chart_source,
    tech, material, source, testing_class, geometry, standard,
    iqi_type, film_side, snr_location, std_figure,
    panel_width, panel_height, panel_overlap, app_exposures,
    film_width, film_height, f_source, b_object, bed, bgap,
    app_kv, app_activity, app_time, app_quality, app_overlap, app_srb,
    app_wire, app_duplex, barrier_limit_usvh, collimator_hvl,
    gamma_convention, asme_sensitivity,
    base_multiplier, base_multiplier_raw

``calculate()`` returns::

    {
        "calculated": {...},   # same keys the desktop stored in last_calculated
        "warnings": [...],     # localized warning strings, in display order
        "display": {...},      # formatted strings for the output rows
        "values": {...},       # extra raw values for UI/sketch use
    }
"""

import logging

from src.core import annex_a
from src.core.calculator import RTCalculator
from src.core.procedure_check import ProcedureComplianceChecker
from src.core.translation import Translation, format_filter_recommendation

logger = logging.getLogger("radiography.core.engine")


def format_sfd_provenance(provenance, trans):
    """Localized text listing the SFD_min/SDD_min candidates and the active one."""
    if not provenance:
        return ""
    def label(candidate):
        key = candidate.get("key")
        if key == "f_min_plus_b":
            return trans.get("sfd_prov_f_min")
        if key == "coverage":
            return trans.get(
                "sfd_prov_coverage_panel" if candidate.get("receptor") == "dd"
                else "sfd_prov_coverage_film")
        return trans.get("sfd_prov_dwsi_floor")

    lines = []
    active_key = provenance.get("active")
    for candidate in provenance.get("candidates", []):
        text = (f"{label(candidate)} = {candidate.get('value', 0.0):.1f} mm "
                f"[{trans.get(candidate.get('formula_key', ''))}]")
        if candidate.get("key") == active_key:
            if candidate.get("l3_dw") or candidate.get("l3_central"):
                text += " — " + trans.get("sfd_prov_l3")
            text = trans.get("sfd_prov_active", text)
        lines.append(text)
    return "\n".join(lines)


def format_f_min_provenance(prov, trans):
    """Localized f_min explanation: base value, formula and Level 3 reductions."""
    if not prov:
        return ""
    text = trans.get(
        "fmin_prov_base", prov.get("base", 0.0),
        trans.get(prov.get("formula_key", "")))
    reduced = bool(prov.get("l3_dw") or prov.get("l3_central"))
    if prov.get("l3_dw"):
        text += " → " + trans.get("fmin_prov_dw")
    if prov.get("l3_central"):
        text += " → " + trans.get("fmin_prov_central")
    if reduced:
        text += " → " + trans.get("fmin_prov_final", prov.get("value", 0.0))
    return text


def format_exposures_provenance(prov, trans):
    """Localized explanation of how the required exposure count was found."""
    if not prov:
        return ""
    method = prov.get("method")
    if method == "annex_a":
        text = trans.get(
            "exp_prov_annex_a", prov.get("figure"), prov.get("t_over_de"),
            prov.get("ratio_name"), prov.get("ratio"), prov.get("n"))
        if prov.get("next_n") is not None:
            key = ("exp_prov_next_ge" if prov.get("next_op") == "ge"
                   else "exp_prov_next_le")
            text += " — " + trans.get(
                key, prov.get("next_n"), prov.get("ratio_name"),
                prov.get("next_ratio"), prov.get("next_distance_mm"))
        if prov.get("l3_dw"):
            text += " — " + trans.get("exp_prov_l3")
        return text
    if method == "panoramic":
        return trans.get("exp_prov_panoramic")
    if method == "dwdi_rule":
        return trans.get("exp_prov_dwdi", prov.get("ratio"), prov.get("n"))
    return trans.get("exp_prov_fallback", prov.get("n"))


MATERIAL_KEYS = ["steel", "aluminum", "titanium", "copper_nickel"]
SOURCE_KEYS = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60",
               "isotope_yb169", "isotope_tm170"]
GEOMETRY_KEYS = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]

DEFAULT_FORM = {
    "od": 114.3,
    "t": 6.02,
    "cap": 3.0,
    "weld_width": 8.0,
    "d": 2.0,
    "sfd": 600.0,
    "output_val": 5.0,
    "base_e": 3.0,
    "detector_type": "cr_standard",
    "film_class_used": "C5",
    "chart_source": "model",
    "tech": "digital",
    "material": "steel",
    "source": "x_ray",
    "testing_class": "class_b",
    "geometry": "dwsi",
    "standard": "iso",
    "iqi_type": "wire",
    "film_side": False,
    "snr_location": "weld",
    "std_figure": None,
    "panel_width": 200.0,
    "panel_height": 200.0,
    "panel_overlap": 10.0,
    "app_exposures": 0,
    "film_width": 0.0,
    "film_height": 0.0,
    "f_source": None,
    "b_object": None,
    "bed": 0.0,
    "bgap": 5.0,
    "app_kv": 120.0,
    "app_activity": 40.0,
    "app_time": 120.0,
    "app_quality": 140.0,
    "app_overlap": 10.0,
    "app_srb": 80.0,
    "app_wire": 10,
    "app_duplex": 6,
    "barrier_limit_usvh": 20.0,
    "collimator_hvl": 0.0,
    "gamma_convention": "r",
    "asme_sensitivity": "2-2T",
    "base_multiplier": 1.0,
    "base_multiplier_raw": 1.0,
    "user_geometry": None,
    "app_overlap_warn": 10.0,
}


def _as_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if not value:
                return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if not value:
                return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_form(form):
    """Fills missing keys with defaults and coerces numeric fields."""
    f = dict(DEFAULT_FORM)
    if form:
        f.update({k: v for k, v in form.items() if v is not None or k in ("f_source", "b_object", "std_figure")})

    float_keys = [
        "od", "t", "cap", "weld_width", "d", "sfd", "output_val", "base_e",
        "panel_width", "panel_height", "panel_overlap", "bed", "bgap",
        "app_kv", "app_activity", "app_time", "app_quality", "app_overlap",
        "app_srb", "barrier_limit_usvh", "collimator_hvl",
        "base_multiplier", "base_multiplier_raw", "film_width", "film_height",
        "app_overlap_warn",
    ]
    for key in float_keys:
        f[key] = _as_float(f.get(key), DEFAULT_FORM[key])

    f["app_wire"] = _as_int(f.get("app_wire"), 10)
    f["app_duplex"] = _as_int(f.get("app_duplex"), 6)
    f["app_exposures"] = max(0, _as_int(f.get("app_exposures"), 0))

    if f.get("f_source") is not None:
        f["f_source"] = _as_float(f["f_source"], 0.0) or None
    if f.get("b_object") is not None:
        f["b_object"] = _as_float(f["b_object"], 0.0) or None

    if f.get("tech") not in ("analog", "digital"):
        f["tech"] = "digital"
    if f.get("material") not in MATERIAL_KEYS:
        f["material"] = "steel"
    if f.get("source") not in SOURCE_KEYS:
        f["source"] = "x_ray"
    if f.get("testing_class") not in ("class_a", "class_b"):
        f["testing_class"] = "class_b"
    if f.get("geometry") not in GEOMETRY_KEYS:
        f["geometry"] = "dwsi"
    if f.get("standard") not in ("iso", "asme"):
        f["standard"] = "iso"
    if f.get("iqi_type") not in ("wire", "step_hole"):
        f["iqi_type"] = "wire"
    if f.get("snr_location") not in ("weld", "adjacent"):
        f["snr_location"] = "weld"
    if f.get("gamma_convention") not in ("r", "msv"):
        f["gamma_convention"] = "r"
    f["film_side"] = bool(f.get("film_side", False))
    return f


def calculate_diagonal(width, height):
    return RTCalculator().calculate_diagonal(width, height)


class CalculationEngine:
    """Runs the full RT calculation chain for a form-state dict."""

    def __init__(self, calc=None, proc_checker=None, chart_db=None, trans=None):
        self.calc = calc or RTCalculator()
        self.proc_checker = proc_checker or ProcedureComplianceChecker()
        self.trans = trans or Translation()
        self._chart_db = chart_db

    # ------------------------------------------------------------------
    # Exposure chart database (lazy, so web builds can inject their own)
    # ------------------------------------------------------------------
    @property
    def chart_db(self):
        if self._chart_db is None:
            self._chart_db = self._load_chart_db()
        return self._chart_db

    def _load_chart_db(self):
        import os
        try:
            from src.core.exposure_charts import ExposureChartDatabase, resource_path
        except ImportError:  # pragma: no cover - fallback for stripped builds
            return None
        json_path = resource_path("exposure_chart_dataset.json")
        if os.path.exists(json_path):
            return ExposureChartDatabase(json_path)
        db = ExposureChartDatabase()
        db.generate_type_x_chart(self.calc)
        return db

    def set_chart_db(self, chart_db):
        self._chart_db = chart_db

    # ------------------------------------------------------------------
    # Geometry (shared by the screen and the PDF report)
    # ------------------------------------------------------------------
    def compute_geometry(self, form, lvl3=None):
        f = normalize_form(form)
        calc = self.calc
        lvl3 = lvl3 or {}

        is_digital = f["tech"] == "digital"
        is_planar = is_digital and not bool(f.get("detector_curved", False))
        std_figure = f.get("std_figure")
        geometry = f["geometry"]
        od = f["od"]
        t = f["t"]
        sfd = f["sfd"]
        d = f["d"]
        testing_class = f["testing_class"]
        standard = f["standard"]

        bed = f["bed"]
        bgap = f["bgap"]

        bed_user = bed
        bed_auto = False
        bed_auto_suggested = None
        if is_planar and geometry == "dwsi" and od > 0.0:
            try:
                n_exposures = calc.calculate_dwsi_exposures(od, t, sfd, testing_class)
            except Exception:
                n_exposures = 3
            bed_auto_suggested = calc.calculate_b_ed(od / 2.0, n_exposures)
            if bed <= 0.0:
                bed = bed_auto_suggested
                bed_auto = True

        f_min_star = None
        ci_factor = None
        if geometry in ("dwdi_elliptic", "dwdi_super"):
            b_dist = od
            f_min_iso_base = calc.calculate_f_min(d, b_dist, testing_class, t)
        elif is_planar:
            if calc.is_central_projection(geometry, std_figure):
                b_dist = calc.calculate_b_panoramic(bed, bgap, t)
            else:
                b_dist = calc.calculate_b_curved(bed, bgap, t, testing_class)
            f_min_star, ci_factor = calc.calculate_f_min_star(d, b_dist, t, testing_class)
            if f_min_star is not None:
                f_min_iso_base = f_min_star
            else:
                f_min_iso_base = calc.calculate_f_min(d, t, testing_class, t)
        else:
            b_dist = t
            f_min_iso_base = calc.calculate_f_min(d, b_dist, testing_class, t)
        b_eff, b_rule_applied = calc.get_effective_b(b_dist, t)

        f_min_asme_base = None
        if standard == "asme":
            f_min_asme_base = calc.calculate_asme_f_min(d, b_dist, t)

        if is_digital:
            panel_w = f["panel_width"]
            panel_h = f["panel_height"]
            receptor_w, receptor_h = panel_w, panel_h
            dd = calc.calculate_diagonal(panel_w, panel_h)
            df = None
        else:
            receptor_w = f["film_width"]
            receptor_h = f["film_height"]
            df = calc.calculate_diagonal(receptor_w, receptor_h)
            dd = None
        receptor_size = dd if is_digital else df
        coverage_min = calc.calculate_coverage_min(receptor_size)

        dwsi_physical_min = 0.0
        if geometry == "dwsi" and od > 0.0:
            dwsi_physical_min = od + max(0.0, bgap)

        lvl3_dw = bool(lvl3.get("dw_reduction")) and calc.is_double_wall_technique(geometry)
        lvl3_central = bool(lvl3.get("central_proj_reduction")) and calc.is_central_projection(geometry, std_figure)
        l3_factor = (0.8 if lvl3_dw else 1.0) * (0.5 if lvl3_central else 1.0)

        f_min_iso = f_min_iso_base * l3_factor
        f_min_asme = f_min_asme_base * l3_factor if f_min_asme_base is not None else None
        f_min = f_min_asme if standard == "asme" else f_min_iso

        sfd_min_iso_b = f_min + b_dist
        sfd_min = sfd_min_iso_b
        active_source = "f_min_plus_b"
        if coverage_min > sfd_min:
            sfd_min = coverage_min
            active_source = "coverage"
        if dwsi_physical_min > sfd_min:
            sfd_min = dwsi_physical_min
            active_source = "dwsi_floor"

        if standard == "asme":
            f_formula = "sfd_prov_formula_asme"
        elif f_min_star is not None:
            f_formula = "sfd_prov_formula_f13"
        else:
            f_formula = "sfd_prov_formula_f2"
        provenance = {
            "active": active_source,
            "candidates": [
                {
                    "key": "f_min_plus_b",
                    "value": sfd_min_iso_b,
                    "f_min": f_min,
                    "b": b_dist,
                    "formula_key": f_formula,
                    "l3_dw": lvl3_dw,
                    "l3_central": lvl3_central,
                },
                {
                    "key": "coverage",
                    "value": coverage_min,
                    "receptor": "dd" if is_digital else "df",
                    "size": receptor_size,
                    "factor": 1.4,
                    "formula_key": ("sfd_prov_formula_f7" if is_digital
                                    else "sfd_prov_formula_f4"),
                },
                {
                    "key": "dwsi_floor",
                    "value": dwsi_physical_min,
                    "formula_key": "sfd_prov_formula_dwsi_floor",
                },
            ],
        }

        ug = calc.calculate_geometric_unsharpness_from_sfd(d, b_dist, sfd)

        if standard == "asme":
            f_min_base = f_min_asme_base
            f_min_formula = "sfd_prov_formula_asme"
        elif f_min_star is not None:
            f_min_base = f_min_iso_base
            f_min_formula = "sfd_prov_formula_f13"
        else:
            f_min_base = f_min_iso_base
            f_min_formula = "sfd_prov_formula_f2"
        f_min_provenance = {
            "base": f_min_base,
            "value": f_min,
            "formula_key": f_min_formula,
            "standard": standard,
            "l3_dw": lvl3_dw,
            "l3_central": lvl3_central,
            "factor": l3_factor,
            "b": b_dist,
            "d": d,
            "is_planar": is_planar,
        }

        return {
            "b_dist": b_dist,
            "b_eff": b_eff,
            "b_rule_applied": b_rule_applied,
            "f_min": f_min,
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme,
            "f_min_iso_base": f_min_iso_base,
            "f_min_asme_base": f_min_asme_base,
            "sfd_min": sfd_min,
            "sdd_min": coverage_min,
            "coverage_min": coverage_min,
            "receptor_w": receptor_w,
            "receptor_h": receptor_h,
            "receptor_size": receptor_size,
            "df": df,
            "dd": dd,
            "is_digital": is_digital,
            "dwsi_physical_min": dwsi_physical_min,
            "lvl3_dw": lvl3_dw,
            "lvl3_central": lvl3_central,
            "ug": ug,
            "f_min_star": f_min_star,
            "ci_factor": ci_factor,
            "is_planar": is_planar,
            "is_curved": not is_planar,
            "std_figure": std_figure,
            "standard": standard,
            "bed": bed,
            "bed_user": bed_user,
            "bed_auto": bed_auto,
            "bed_auto_suggested": bed_auto_suggested,
            "bgap": bgap,
            "sfd_min_provenance": provenance,
            "f_min_provenance": f_min_provenance,
        }

    # ------------------------------------------------------------------
    # SWSI exposure count by technique figure (Annex A)
    # ------------------------------------------------------------------
    PANORAMIC_FIGURES = ("fig5", "fig5a", "fig5b")
    FILM_INSIDE_FIGURES = ("fig2", "fig2a", "fig2b")
    FILM_OUTSIDE_FIGURES = ("fig8", "fig8a", "fig8b")

    @staticmethod
    def _annex_provenance(detail, std_figure, clamped=False, l3_dw=False):
        """Structured provenance for an Annex A exposure-count lookup."""
        return {
            "method": "annex_a",
            "figure": detail["figure"],
            "std_figure": std_figure,
            "n": detail["n"],
            "t_over_de": detail["t_over_de"],
            "ratio_name": detail["ratio_name"],
            "ratio": detail["ratio"],
            "distance_mm": detail["distance_mm"],
            "next_n": detail["next_n"],
            "next_ratio": detail["next_ratio"],
            "next_distance_mm": detail["next_distance_mm"],
            "next_op": detail["next_op"],
            "clamped": clamped,
            "l3_dw": l3_dw,
        }

    def _swsi_exposures(self, form, geo, calc):
        """Minimum exposures for SWSI, by standard figure (ISO 17636 Annex A).

        Figure 2 (source outside, film/detector inside) uses Figures A.1/A.3
        as a function of t/De and De/f; Figure 8 (off-centre source inside,
        film/detector outside) uses A.2/A.4 (De/SFD); the panoramic Figure 5
        needs a single exposure. Returns ``(n, provenance)``.
        """
        figure = form.get("std_figure")
        t = form["t"]
        od = form["od"]
        sfd = form["sfd"]
        testing_class = form["testing_class"]

        if figure in self.FILM_INSIDE_FIGURES:
            f_override = form.get("f_source")
            f_distance = f_override if f_override else max(sfd - geo["b_dist"], 1.0)
            detail = annex_a.lookup_detail(
                t, od, f_distance, testing_class, film_inside=True)
            if detail is not None:
                return int(detail["n"]), self._annex_provenance(
                    detail, figure, l3_dw=geo["lvl3_dw"])
            n = calc.annex_a_exposures(
                t, od, f_distance, testing_class, film_inside=True)
            n = int(n) if n is not None else 1
            return n, {"method": "geometric_fallback", "n": n}
        if figure in self.FILM_OUTSIDE_FIGURES:
            detail = annex_a.lookup_detail(
                t, od, sfd, testing_class, film_inside=False)
            if detail is not None:
                return max(3, int(detail["n"])), self._annex_provenance(
                    detail, figure, l3_dw=geo["lvl3_dw"])
            n = calc.annex_a_exposures(
                t, od, sfd, testing_class, film_inside=False)
            n = max(3, int(n)) if n is not None else 3
            return n, {"method": "geometric_fallback", "n": n}
        return 1, {"method": "panoramic", "n": 1}

    # ------------------------------------------------------------------
    # Full calculation chain
    # ------------------------------------------------------------------
    def calculate(self, form, lvl3=None, lang="tr"):
        f = normalize_form(form)
        lvl3 = lvl3 or {}
        if self.trans.language != lang:
            self.trans.set_language(lang)
        trans = self.trans
        calc = self.calc

        od = f["od"]
        t = f["t"]
        cap = f["cap"]
        weld_width = f["weld_width"]
        d = f["d"]
        sfd = f["sfd"]
        output_val = f["output_val"]
        base_e = f["base_e"]
        detector_type = f["detector_type"]
        film_class_used = f["film_class_used"]
        chart_source = f["chart_source"]
        material = f["material"]
        tech = f["tech"]
        source = f["source"]
        testing_class = f["testing_class"]
        geometry = f["geometry"]
        standard = f["standard"]
        iqi_type = f["iqi_type"]
        film_side = bool(f["film_side"])
        snr_location = f["snr_location"]
        std_figure = f.get("std_figure")

        # 1. Geometry constraints (DWDI is only valid for OD <= 100 mm)
        user_geometry = f.get("user_geometry") or geometry
        if od > 100.0 and geometry in ("dwdi_elliptic", "dwdi_super"):
            geometry = "dwsi"

        warnings = []

        # 2. Thicknesses and tube voltage limit
        w_nom, w_eff = calc.calculate_thicknesses(t, cap, geometry)
        u_max = calc.calculate_u_max(w_nom, material)

        # 3. Shared geometry block
        geo_form = dict(f)
        geo_form["geometry"] = geometry
        geo = self.compute_geometry(geo_form, lvl3)
        b_dist = geo["b_dist"]
        b_eff = geo["b_eff"]
        b_rule_applied = geo["b_rule_applied"]
        f_min = geo["f_min"]
        f_min_iso = geo["f_min_iso"]
        f_min_asme = geo["f_min_asme"]
        sfd_min = geo["sfd_min"]
        sdd_min = geo["sdd_min"]
        coverage_min = geo["coverage_min"]
        ug = geo["ug"]
        f_min_star = geo["f_min_star"]
        ci_factor = geo["ci_factor"]
        bgap = geo["bgap"]
        dd = geo["dd"]
        df = geo["df"]
        receptor_size = geo["receptor_size"]
        is_digital = geo["is_digital"]

        # 4. ASME Sec V Art 2 geometric unsharpness (Ug) limit check
        ug_ok, ug_limit = calc.check_ug_compliance(ug, t, standard)
        if standard == "asme" and not ug_ok:
            if trans.language == "tr":
                warnings.append(f"UYARI (ASME Sec V Art 2): Ug ({ug:.3f} mm) izin verilen limiti ({ug_limit:.2f} mm) aşıyor. Kaynak-nesne mesafesi (f) artırılmalı.")
            else:
                warnings.append(f"WARNING (ASME Sec V Art 2): Ug ({ug:.3f} mm) exceeds the allowed limit ({ug_limit:.2f} mm). Increase source-to-object distance (f).")

        # 5. Exposure counts (+ provenance: which rule/figure produced them)
        if geometry == "swsi":
            exposures, exposures_prov = self._swsi_exposures(f, geo, calc)
        elif geometry == "dwdi_elliptic":
            exposures = calc.get_dwdi_elliptical_exposures(od, t)
            exposures_prov = {
                "method": "dwdi_rule",
                "n": exposures,
                "ratio_name": "t/De",
                "ratio": round(t / od, 4) if od > 0 else 0.0,
                "threshold": 0.12,
            }
        elif geometry == "dwdi_super":
            exposures = 3
            exposures_prov = {
                "method": "dwdi_rule",
                "n": 3,
                "ratio_name": "t/De",
                "ratio": round(t / od, 4) if od > 0 else 0.0,
                "threshold": 0.12,
            }
        else:  # DWSI
            exposures = calc.calculate_dwsi_exposures(od, t, sfd, testing_class)
            sfd_eff = max(sfd, od)
            detail = annex_a.lookup_detail(
                t, od, sfd_eff, testing_class, film_inside=False)
            if detail is not None:
                exposures_prov = self._annex_provenance(
                    detail, f.get("std_figure"),
                    clamped=sfd < od, l3_dw=geo["lvl3_dw"])
            else:
                exposures_prov = {"method": "geometric_fallback", "n": exposures}

        n_panel = None
        n_applied = f["app_exposures"]
        n_required = exposures
        exposures_ok = None
        panel_width = f["panel_width"]
        panel_height = f["panel_height"]
        panel_res = None
        if tech == "digital":
            overlap_pct = f["panel_overlap"]
            f_override = f.get("f_source")
            b_override = f.get("b_object")
            panel_res = calc.calculate_panel_exposures(
                od, t, geometry, testing_class, panel_width,
                panel_height=panel_height, cap=cap, sfd=sfd, bgap=bgap,
                overlap_percent=overlap_pct, focal_size=d, std_figure=std_figure,
                b_object=b_override, f_source=f_override,
            )
            if f_override is not None and b_override is not None:
                sum_dist = f_override + b_override
                if abs(sum_dist - sfd) > 5.0:
                    if trans.language == "tr":
                        warnings.append(f"UYARI: Ölçülen geometri (f+b={sum_dist:.1f} mm) uygulanan SFD'den ({sfd:.1f} mm) farklı.")
                    else:
                        warnings.append(f"WARNING: Measured geometry (f+b={sum_dist:.1f} mm) differs from applied SFD ({sfd:.1f} mm).")
            if b_override is not None and b_override < t:
                if trans.language == "tr":
                    warnings.append(f"UYARI: b ({b_override:.1f} mm) et kalınlığından (t={t:.1f} mm) küçük — ölçümü kontrol edin.")
                else:
                    warnings.append(f"WARNING: b ({b_override:.1f} mm) is smaller than the wall thickness (t={t:.1f} mm) — check the measurement.")
            if f_override is not None and f_override < panel_res["f_min_applied"]:
                if trans.language == "tr":
                    warnings.append(f"UYARI: f ({f_override:.1f} mm) ISO 17636-2 Madde 7.6 geometrik sınırı olan f_min ({panel_res['f_min_applied']:.1f} mm) altında — f_min kullanıldı.")
                else:
                    warnings.append(f"WARNING: f ({f_override:.1f} mm) is below the Clause 7.6 geometric limit f_min ({panel_res['f_min_applied']:.1f} mm) — f_min applied.")
            n_panel = panel_res["n_panel"]
            cmp_res = calc.evaluate_exposure_comparison(exposures, n_panel, n_applied if n_applied > 0 else max(exposures, n_panel))
            n_required = cmp_res["n_required"]
            if n_applied > 0:
                exposures_ok = (n_applied >= n_required)
            if panel_res["limiting_factor"] == "panel":
                if trans.language == "tr":
                    warnings.append(f"BİLGİ: Panel aktif genişliği ({panel_width:.0f} mm) poz sayısını sınırlıyor (θ={panel_res['theta_panel_deg']:.1f}°).")
                else:
                    warnings.append(f"NOTE: Panel active width ({panel_width:.0f} mm) limits exposure count (θ={panel_res['theta_panel_deg']:.1f}°).")
            if not panel_res["panel_height_ok"]:
                if trans.language == "tr":
                    warnings.append(f"UYARI: Panel aktif yüksekliği ({panel_height:.0f} mm) WAE genişliğini ({panel_res['wae_width_mm']:.1f} mm) karşılamıyor.")
                else:
                    warnings.append(f"WARNING: Panel active height ({panel_height:.0f} mm) is smaller than WAE width ({panel_res['wae_width_mm']:.1f} mm).")
            if n_applied > 0 and not exposures_ok:
                if trans.language == "tr":
                    warnings.append(f"UYARI: Uygulanan poz sayısı ({n_applied}) gerekli minimumu ({n_required}) karşılamıyor.")
                else:
                    warnings.append(f"WARNING: Applied exposures ({n_applied}) do not meet the required minimum ({n_required}).")
        else:
            n_required = exposures
            if n_applied > 0:
                exposures_ok = (n_applied >= n_required)
                if not exposures_ok:
                    if trans.language == "tr":
                        warnings.append(f"UYARI: Uygulanan poz sayısı ({n_applied}) standartın gerektirdiği asgari poz sayısını ({n_required}) karşılamıyor.")
                    else:
                        warnings.append(f"WARNING: Applied exposures ({n_applied}) do not meet the required minimum ({n_required}).")

        # 6. kV input (X-ray only)
        if source == "x_ray":
            input_kv = f["app_kv"]
        else:
            input_kv = None

        # 7. IQI targets
        if iqi_type == "step_hole":
            wire_str, wire_no = calc.get_step_hole_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=trans.language)
        else:
            wire_str, wire_no = calc.get_single_wire_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=trans.language)

        if tech == "digital":
            duplex_str, duplex_no = calc.get_duplex_iqi(w_nom, testing_class, geometry, lang=trans.language)
        else:
            duplex_str, duplex_no = "N/A", None

        # 8. Detector quality
        if tech == "analog":
            film_class_req = calc.get_required_film_class(w_nom, testing_class, material, source)
            max_srb_req = None
            detector_quality_str = f"{film_class_req} Film"
        else:
            film_class_req = None
            max_srb_req = calc.get_max_srb(w_nom, testing_class, geometry)
            detector_quality_str = f"Max {max_srb_req} µm"

        # 9. Quality targets and Level 3 distance compensation
        target_quality = ""
        sfd_comp_target = None
        required_density = None
        target_snr_val = None
        table_name = ""
        time_multiplier = 1.0

        if tech == "analog":
            if material in ("steel", "copper_nickel") and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b":
                required_density = 3.0
            else:
                required_density = 2.3 if testing_class == "class_b" else 2.0
            target_quality = f">= {required_density:.1f} (Max 4.0)"
            target_snr_val = 130.0 if testing_class == "class_b" else 70.0
        else:
            base_snr, table_name, _desc = calc.get_target_snr(material, source, input_kv, w_nom, testing_class, lang=trans.language)
            is_flush = (cap == 0.0)
            se75_thin_class_b = (material in ("steel", "copper_nickel") and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b")
            apply_multiplier = False
            if snr_location == "adjacent" and not is_flush:
                apply_multiplier = True
            if se75_thin_class_b:
                apply_multiplier = True
            if apply_multiplier:
                target_snr_val = base_snr * 1.4
                if snr_location == "adjacent" and not is_flush:
                    warnings.append(trans.get("warn_snr_adjacent_factor"))
            else:
                target_snr_val = base_snr

            if sfd < sfd_min and lvl3.get("sfd_comp"):
                k_factor = sfd_min / max(10.0, sfd)
                sfd_comp_target = target_snr_val * k_factor
                target_quality = f"{target_snr_val:.1f} -> {sfd_comp_target:.1f} (Lvl 3 Comp) [{table_name}]"
                time_multiplier = k_factor ** 2
            else:
                target_quality = f">= {int(target_snr_val)} [{table_name}]"

        # 10. Calculated exposure time
        min_calc, sec_calc, raw_time = calc.calculate_exposure_time(
            sfd, w_eff, source, output_val, base_e, tech,
            testing_class=testing_class,
            film_class=film_class_used,
            detector_type=detector_type,
            kv=input_kv,
            material=material,
            chart_source=chart_source if chart_source != "model" else None,
            chart_db=self.chart_db,
        )

        if sfd_comp_target is not None:
            raw_time = raw_time * time_multiplier
            min_calc = int(raw_time // 60)
            sec_calc = int(raw_time % 60)

        # 11. Field correction factor
        base_multiplier = f["base_multiplier"]
        if base_multiplier <= 0.0:
            base_multiplier = 1.0
        base_multiplier = min(base_multiplier, 100.0)
        raw_mult = f["base_multiplier_raw"]
        if raw_mult <= 0.0:
            if trans.language == "tr":
                warnings.append("UYARI: Saha Düzeltme Çarpanı (F) geçersiz/pozitif değil; 1.0 olarak uygulandı.")
            else:
                warnings.append("WARNING: Field Correction Factor (F) is invalid/non-positive; 1.0 applied.")
        elif base_multiplier < 0.5 or base_multiplier > 2.0:
            if trans.language == "tr":
                warnings.append(f"UYARI: Saha Düzeltme Çarpanı (F={base_multiplier:.2f}) olağan aralığın (0.5–2.0) dışında; değer teknik/ekipman doğrulama kaydıyla desteklenmelidir.")
            else:
                warnings.append(f"WARNING: Field Correction Factor (F={base_multiplier:.2f}) is outside the usual range (0.5–2.0); the value should be supported by a technique/equipment qualification record.")
        if base_multiplier != 1.0:
            raw_time = raw_time * base_multiplier
            min_calc = int(raw_time // 60)
            sec_calc = int(raw_time % 60)

        # 12. Warnings: class A, DWDI geometry, materials, geometry provenance
        if testing_class == "class_a":
            warnings.append(trans.get("warn_class_a"))

        if user_geometry in ("dwdi_elliptic", "dwdi_super"):
            if user_geometry != geometry:
                warnings.append(trans.get("info_dwdi_forced_swsi"))
            dwdi_res = calc.validate_dwdi(user_geometry, od, t, weld_width)
            if not dwdi_res["od_ok"]:
                warnings.append(trans.get("warn_dwdi_limit"))
            if user_geometry == "dwdi_elliptic":
                if not dwdi_res["t_ok"]:
                    warnings.append(trans.get("warn_dwdi_t_limit"))
                if not dwdi_res["weld_width_ok"]:
                    warnings.append(trans.get("warn_dwdi_weld_width", weld_width, od / 4.0))
                if dwdi_res["needs_three"]:
                    warnings.append(trans.get("info_dwdi_elliptic_3"))
                else:
                    warnings.append(trans.get("info_dwdi_elliptic_2"))
            else:
                warnings.append(trans.get("info_dwdi_super_exposures"))

        if geometry == "swsi" and f.get("std_figure") not in (
                self.PANORAMIC_FIGURES + self.FILM_INSIDE_FIGURES + self.FILM_OUTSIDE_FIGURES):
            warnings.append(trans.get("warn_swsi_figure"))

        if source != "x_ray" and material in ("aluminum", "titanium"):
            warnings.append(trans.get("warn_isotope_light_metal"))

        if material != "steel":
            ref = calc.get_ref_factor(material)
            t_steel = calc.equivalent_steel_thickness(w_nom, material)
            if trans.language == "tr":
                warnings.append(f"BİLGİ (REF): {trans.get(material)} radyografik eşdeğerlik faktörü REF={ref:.2f}; eşdeğer çelik kalınlığı ≈ {t_steel:.2f} mm.")
            else:
                warnings.append(f"INFO (REF): {trans.get(material)} radiographic equivalence factor REF={ref:.2f}; equivalent steel thickness ≈ {t_steel:.2f} mm.")

        if b_rule_applied:
            if trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): b ({b_dist:.1f} mm) < 1.2×t ({1.2*t:.1f} mm) olduğundan b = t ({t:.1f} mm) kullanıldı.")
            else:
                warnings.append(f"NOTE (Clause 7.6): b ({b_dist:.1f} mm) < 1.2×t ({1.2*t:.1f} mm), using b = t ({t:.1f} mm).")

        if geo["bed_auto"]:
            if trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Planar dedektör kenar yüksekliği (bed) girilmedi; Formül (10) ile b_ed = {geo['bed']:.1f} mm otomatik kullanıldı (N poz, α=π/N).")
            else:
                warnings.append(f"NOTE (Clause 7.6): Planar detector edge lift (bed) not provided; b_ed = {geo['bed']:.1f} mm computed automatically with Formula (10) (N exposures, alpha=pi/N).")
        elif geo["is_planar"] and geometry == "swsi" and geo["bed_user"] <= 0.0:
            if trans.language == "tr":
                warnings.append("UYARI (Madde 7.6): Planar dedektörde bed=0; kenar yüksekliğini Şekil 23 / ölçekli çizimden girin (b_ed = (1−cos α)·r_e).")
            else:
                warnings.append("WARNING (Clause 7.6): Planar detector with bed=0; enter the edge lift from Figure 23 / a scaled drawing (b_ed = (1-cos alpha)*r_e).")
        elif (geo["bed_auto_suggested"] is not None and 0.0 < geo["bed_user"] < geo["bed_auto_suggested"]):
            if trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Girilen bed ({geo['bed_user']:.1f} mm) Formül (10) değerinden ({geo['bed_auto_suggested']:.1f} mm) küçük — kontrol edin.")
            else:
                warnings.append(f"NOTE (Clause 7.6): Entered bed ({geo['bed_user']:.1f} mm) is smaller than the Formula (10) value ({geo['bed_auto_suggested']:.1f} mm) - please verify.")

        if coverage_min > f_min + b_dist:
            if is_digital:
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Dedektör boyutu (dd={receptor_size:.0f} mm) SDD_min'i {coverage_min:.0f} mm'ye yükseltti.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Detector size (dd={receptor_size:.0f} mm) raises SDD_min to {coverage_min:.0f} mm.")
            else:
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Film köşegeni (df={receptor_size:.0f} mm) SFD_min'i {coverage_min:.0f} mm'ye yükseltti.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Film diagonal (df={receptor_size:.0f} mm) raises SFD_min to {coverage_min:.0f} mm.")
        elif (not is_digital) and coverage_min <= 0.0:
            if trans.language == "tr":
                warnings.append("BİLGİ: Film köşegeni (df) girilmedi; SFD ≥ 1,4·df kontrolü yapılamadı (örn. 300×400 mm film → df=500 mm).")
            else:
                warnings.append("NOTE: Film diagonal (df) not provided; the SFD >= 1.4*df check could not be performed (e.g. 300x400 mm film -> df=500 mm).")

        if is_digital:
            annex_f_needed, annex_f_ratio = calc.check_annex_f_compensation(ug, max_srb_req)
            if annex_f_needed:
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Annex F): Ug/SRb ({annex_f_ratio:.1f}) > 2. IQI görünürlüğü için f_min artırılmalı veya SNR yükseltilmelidir.")
                else:
                    warnings.append(f"NOTE (Annex F): Ug/SRb ({annex_f_ratio:.1f}) > 2. Increase f_min or SNR for IQI visibility.")

        if geo["dwsi_physical_min"] > 0.0:
            if sfd < geo["dwsi_physical_min"]:
                if trans.language == "tr":
                    warnings.append(f"UYARI (Madde 7.6): DWSI'de uygulanan SFD ({sfd:.1f} mm) fiziksel asgari mesafenin (OD+bgap = {geo['dwsi_physical_min']:.1f} mm) altında. Kaynak boru dışında olamaz.")
                else:
                    warnings.append(f"WARNING (Clause 7.6): Applied SFD ({sfd:.1f} mm) is below the physical minimum for DWSI (OD+bgap = {geo['dwsi_physical_min']:.1f} mm). The source cannot be inside the pipe.")
            elif geo["dwsi_physical_min"] > geo["f_min"] + b_dist:
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): DWSI fiziksel tabanı SFD_min'i {geo['dwsi_physical_min']:.1f} mm'ye (OD+bgap) yükseltti; f_min yalnızca et kalınlığına göre belirlenir.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): The DWSI physical floor raised SFD_min to {geo['dwsi_physical_min']:.1f} mm (OD+bgap); f_min itself is determined only by wall thickness.")

        if calc.is_double_wall_technique(geometry):
            if geo["lvl3_dw"]:
                if trans.language == "tr":
                    warnings.append(f"Level 3: Çift duvar tekniğinde f_min %20 düşürüldü ({f_min:.1f} mm).")
                else:
                    warnings.append(f"Level 3: Double-wall technique f_min reduced 20% to {f_min:.1f} mm.")
            else:
                f_min_80 = f_min * 0.8
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Çift duvar tekniğinde f_min %20 düşürülebilir ({f_min_80:.1f} mm). IQI şartları sağlanmalıdır.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Double-wall technique allows 20% f_min reduction (to {f_min_80:.1f} mm). IQI requirements must be met.")

        if calc.is_central_projection(geometry, std_figure):
            if geo["lvl3_central"]:
                if trans.language == "tr":
                    warnings.append(f"Level 3: Merkezi projeksiyonda f_min %50 düşürüldü ({f_min:.1f} mm).")
                else:
                    warnings.append(f"Level 3: Central projection f_min reduced 50% to {f_min:.1f} mm.")
                if trans.language == "tr":
                    warnings.append("BİLGİ (Madde 7.6): Merkezi projeksiyonda 1 duplex adım veya 1 SRb toleransı uygulanır.")
                else:
                    warnings.append("NOTE (Clause 7.6): Central projection allows 1 duplex step or 1 SRb tolerance.")
            else:
                f_min_50 = f_min * 0.5
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Madde 7.6): Merkezi projeksiyonda f_min %50 düşürülebilir ({f_min_50:.1f} mm). Level 3 onayı gerekiyor.")
                else:
                    warnings.append(f"NOTE (Clause 7.6): Central projection allows 50% f_min reduction (to {f_min_50:.1f} mm). Requires Level 3 approval.")

        if f_min_star is not None and ci_factor is not None:
            if trans.language == "tr":
                warnings.append(f"BİLGİ (Madde 7.6): Planar dedektör, b/t = {b_dist/t:.2f} > 1.2 → f_min* = f_min(b=t) × Ci (Ci = {ci_factor:.3f}) geçerlidir.")
            else:
                warnings.append(f"NOTE (Clause 7.6): Planar detector, b/t = {b_dist/t:.2f} > 1.2 → f_min* = f_min(b=t) × Ci (Ci = {ci_factor:.3f}) governs.")

        is_valid, min_lim, max_lim, table2_msg = calc.validate_source_thickness(
            source, w_nom, testing_class, material, input_kv
        )
        if not is_valid:
            if lvl3.get("source_flex"):
                warnings.append(f"Level 3 Approved Exception: {table2_msg}")
            else:
                warnings.append(f"UYARI: {table2_msg}" if trans.language == "tr" else f"WARNING: {table2_msg}")
        elif table2_msg:
            warnings.append(table2_msg)

        if material in ("steel", "copper_nickel"):
            w_pen = w_nom
            active_6_9 = False
            offset_val = 0
            if geometry in ("dwdi_elliptic", "dwdi_super"):
                if source == "isotope_ir192" and 10.0 < w_pen <= 25.0:
                    active_6_9 = True
                    offset_val = 1
                elif source == "isotope_se75" and w_pen <= 12.0:
                    active_6_9 = True
                    offset_val = 1
            elif geometry in ("swsi", "dwsi"):
                if testing_class == "class_a":
                    if source == "isotope_ir192":
                        if 10.0 < w_pen <= 24.0:
                            active_6_9 = True
                            offset_val = 2
                        elif 24.0 < w_pen <= 30.0:
                            active_6_9 = True
                            offset_val = 1
                    elif source == "isotope_se75" and w_pen <= 24.0:
                        active_6_9 = True
                        offset_val = 1
                else:
                    if source == "isotope_ir192" and 10.0 < w_pen <= 40.0:
                        active_6_9 = True
                        offset_val = 1
                    elif source == "isotope_se75" and w_pen <= 20.0:
                        active_6_9 = True
                        offset_val = 1
            if active_6_9:
                if trans.language == "tr":
                    warnings.append(f"İSTİSNA (Madde 6.9): {source.split('_')[-1].upper()} kaynağı için asgari IQI değeri {offset_val} tel/delik azaltılabilir.")
                else:
                    warnings.append(f"EXCEPTION (Clause 6.9): For {source.split('_')[-1].upper()} source, minimum IQI value may be reduced by {offset_val} wire/hole.")

        if material in ("steel", "copper_nickel") and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b":
            if tech == "analog":
                if trans.language == "tr":
                    warnings.append("İSTİSNA (Madde 6.9): Se-75 kaynağı w < 12mm Class B için optik yoğunluk asgari 3.0 olmalı ve film sınıfı 1 derece iyileştirilmiştir.")
                else:
                    warnings.append("EXCEPTION (Clause 6.9): For Se-75 source with w < 12mm Class B, min optical density is 3.0 and film class is upgraded by 1 level.")
            else:
                if trans.language == "tr":
                    warnings.append("İSTİSNA (Madde 6.9): Se-75 kaynağı w < 12mm Class B için hedef SNR_N 1.4 kat arttırılmıştır (100 -> 140).")
                else:
                    warnings.append("EXCEPTION (Clause 6.9): For Se-75 source with w < 12mm Class B, target SNR_N is increased by 1.4x (100 -> 140).")

        if source == "x_ray":
            if tech == "analog":
                warnings.append(trans.get("warn_analog_kv_limit"))
                if input_kv > u_max:
                    if lvl3.get("voltage_override"):
                        warnings.append("Level 3 Exception Active: Tube Voltage limit check is bypassed by client approval.")
                    else:
                        warnings.append(trans.get("warn_input_kv_limit", input_kv, u_max))
            else:
                opt_kv = u_max * 0.85
                warnings.append(trans.get("warn_digital_kv_opt", f"{opt_kv:.1f}"))
                warnings.append(trans.get("warn_digital_kv_snr"))
                if input_kv > u_max:
                    if lvl3.get("voltage_override"):
                        warnings.append("Level 3 Exception Active: Tube Voltage limit check is bypassed by client approval.")
                    else:
                        warnings.append(trans.get("warn_input_kv_limit", input_kv, u_max))

        if tech == "analog":
            film_comp, film_msg = calc.check_film_class_compliance(film_class_used, testing_class, w_nom, material, source)
            if not film_comp:
                if trans.language == "tr":
                    warnings.append(f"UYARI: Kullanılan film sınıfı ({film_class_used}) standart gereksinimini karşılamıyor! Asgari gereken: {film_class_req}")
                else:
                    warnings.append(f"WARNING: Used film class ({film_class_used}) does not meet standard requirement! Required minimum: {film_class_req}")

        if tech == "analog":
            overlap = f.get("app_overlap_warn", f["app_overlap"])
            if overlap < 10.0:
                warnings.append(trans.get("warn_overlap_limit", overlap))

        if sfd < sfd_min:
            if lvl3.get("sfd_comp"):
                warnings.append(f"Level 3 Compensation Active: Actual SFD ({sfd:.1f} mm) is smaller than SFD_min ({sfd_min:.1f} mm). Target SNR_N increased.")
            else:
                warnings.append(trans.get("warn_f_min_failed", f"{sfd:.1f}", f"{sfd_min:.1f}"))

        # 13. ASME/ASTM IQI output
        if standard == "asme":
            if iqi_type == "step_hole":
                sensitivity = f.get("asme_sensitivity") or "2-2T"
                hole = calc.get_astm_iqi_hole(t, sensitivity)
                hole_word = "delik" if trans.language == "tr" else "hole"
                asme_iqi_str = f"{hole['designator']} (T={hole['iqi_t_mm']:.2f} mm, {hole_word} ∅={hole['hole_dia_mm']:.2f} mm) [ASTM E1025]"
            else:
                wire = calc.get_astm_iqi_wire(w_nom)
                asme_iqi_str = f"Set {wire['set']} W{wire['wire_no']} ({wire['wire_dia_mm']:.3f} mm) [ASTM E747]"
        else:
            asme_iqi_str = "N/A"

        # 14. Radiation barrier distance (isotopes only)
        if source != "x_ray":
            hvl_layers = f["collimator_hvl"]
            limit_usvh = f["barrier_limit_usvh"]
            convention = f["gamma_convention"]
            r_controlled, dose_1m, reduction = calc.calculate_barrier_distance(
                source, output_val, limit_usvh=limit_usvh, hvl_layers=hvl_layers,
                convention=convention,
            )
            r_supervised, _, _ = calc.calculate_barrier_distance(
                source, output_val, limit_usvh=7.5, hvl_layers=hvl_layers,
                convention=convention,
            )
            if trans.language == "tr":
                barrier_str = f"Kontrollü ({limit_usvh:.0f} µSv/h): {r_controlled:.1f} m | Gözetimli (7.5): {r_supervised:.1f} m"
            else:
                barrier_str = f"Controlled ({limit_usvh:.0f} µSv/h): {r_controlled:.1f} m | Supervised (7.5): {r_supervised:.1f} m"
        else:
            barrier_str = "N/A"
            hvl_layers = 0.0
            limit_usvh = 20.0
            convention = "r"
            r_controlled = 0.0

        filter_recs = calc.get_filter_recommendations(source, material, input_kv, testing_class)
        filter_str = format_filter_recommendation(filter_recs, trans.language)

        # 15. Chart tag + display strings
        chart_label = ""
        if chart_source != "model":
            chart_label = " [Type X]" if chart_source == "type_x" else f" [{chart_source}]"

        display = {
            "w_nom": f"{w_nom:.2f} mm",
            "w_eff": f"{w_eff:.2f} mm",
            "u_max": f"{u_max:.1f} kV" if source == "x_ray" else "N/A",
            "f_min": f"{f_min_iso:.1f} mm",
            "f_min_asme": f"{f_min_asme:.1f} mm" if (standard == "asme" and f_min_asme is not None) else "N/A",
            "sfd_min": f"{sfd_min:.1f} mm",
            "ug": f"{ug:.3f} mm",
            "req_exposures": f"{exposures}",
            "exposures_panel": f"{n_panel}" if n_panel is not None else "N/A",
            "exposures_applied": f"{n_applied}" if n_applied > 0 else "-",
            "single_wire_iqi": wire_str,
            "duplex_iqi": duplex_str if tech == "digital" else "N/A",
            "quality_target": target_quality,
            "calc_time": f"{min_calc} min {sec_calc} sec{chart_label}",
            "detector_quality": detector_quality_str,
            "asme_iqi": asme_iqi_str,
            "barrier_distance": barrier_str,
            "filter_recommendation": filter_str,
        }
        if n_applied > 0:
            if exposures_ok:
                display["exposures_check"] = f"UYGUN (≥ {n_required})" if trans.language == "tr" else f"OK (≥ {n_required})"
            else:
                display["exposures_check"] = f"UYGUN DEĞİL (< {n_required})" if trans.language == "tr" else f"NOT OK (< {n_required})"
        else:
            display["exposures_check"] = f"≥ {n_required}"

        # 16. last_calculated equivalent
        calculated = {
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max,
            "sfd_min": sfd_min,
            "sdd_min": sdd_min,
            "ug": ug,
            "ug_limit": ug_limit,
            "standard": standard,
            "asme_iqi": asme_iqi_str,
            "barrier_distance": barrier_str,
            "barrier_radius_m": r_controlled if source != "x_ray" else 0.0,
            "gamma_convention": convention,
            "collimator_hvl": hvl_layers,
            "barrier_limit_usvh": limit_usvh,
            "f_min": f_min,
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme,
            "is_planar": geo["is_planar"],
            "is_digital": is_digital,
            "lvl3_dw": geo["lvl3_dw"],
            "lvl3_central": geo["lvl3_central"],
            "dwsi_physical_min": geo["dwsi_physical_min"],
            "b_dist": b_dist,
            "b_eff": b_eff,
            "df": df,
            "dd": dd,
            "receptor_size": receptor_size,
            "coverage_min": coverage_min,
            "bed_used": geo["bed"],
            "bed_auto": geo["bed_auto"],
            "required_wire_no": wire_no,
            "required_duplex_no": duplex_no,
            "calc_time_raw": raw_time,
            "required_film_class": film_class_req,
            "max_srb": max_srb_req,
            "filter_recommendation": filter_str,
            "exposures_graph": exposures,
            "exposures_panel": n_panel,
            "exposures_applied": n_applied,
            "required_exposures": n_required,
            "exposures_ok": exposures_ok,
            "base_multiplier": base_multiplier,
        }
        if tech == "digital":
            calculated["required_snr"] = target_snr_val
            calculated["sfd_comp_target"] = sfd_comp_target
        else:
            calculated["required_density"] = required_density

        # Provenance for the PDF/screen explanations.
        calculated["sfd_min_provenance"] = geo["sfd_min_provenance"]
        calculated["exposures_provenance"] = exposures_prov
        calculated["f_min_provenance"] = geo["f_min_provenance"]

        values = {
            "od": od,
            "t": t,
            "cap": cap,
            "weld_width": weld_width,
            "d": d,
            "sfd": sfd,
            "output_val": output_val,
            "base_e": base_e,
            "detector_type": detector_type,
            "film_class_used": film_class_used,
            "chart_source": chart_source,
            "material": material,
            "tech": tech,
            "source": source,
            "testing_class": testing_class,
            "geometry": geometry,
            "user_geometry": user_geometry,
            "geometry_forced": user_geometry != geometry,
            "standard": standard,
            "iqi_type": iqi_type,
            "film_side": film_side,
            "snr_location": snr_location,
            "std_figure": std_figure,
            "input_kv": input_kv,
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max,
            "f_min": f_min,
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme,
            "sfd_min": sfd_min,
            "sdd_min": sdd_min,
            "coverage_min": coverage_min,
            "ug": ug,
            "ug_limit": ug_limit,
            "ug_ok": ug_ok,
            "b_dist": b_dist,
            "b_eff": b_eff,
            "b_rule_applied": b_rule_applied,
            "bed": geo["bed"],
            "bed_user": geo["bed_user"],
            "bed_auto": geo["bed_auto"],
            "bed_auto_suggested": geo["bed_auto_suggested"],
            "bgap": bgap,
            "df": df,
            "dd": dd,
            "receptor_size": receptor_size,
            "is_planar": geo["is_planar"],
            "is_digital": is_digital,
            "dwsi_physical_min": geo["dwsi_physical_min"],
            "lvl3_dw": geo["lvl3_dw"],
            "lvl3_central": geo["lvl3_central"],
            "f_min_star": f_min_star,
            "ci_factor": ci_factor,
            "panel_width": panel_width,
            "panel_height": panel_height,
            "panel_overlap": f["panel_overlap"],
            "panel_result": panel_res,
            "n_panel": n_panel,
            "n_applied": n_applied,
            "n_required": n_required,
            "exposures": exposures,
            "exposures_ok": exposures_ok,
            "exposures_provenance": exposures_prov,
            "wire_str": wire_str,
            "wire_no": wire_no,
            "duplex_str": duplex_str,
            "duplex_no": duplex_no,
            "film_class_req": film_class_req,
            "max_srb": max_srb_req,
            "detector_quality_str": detector_quality_str,
            "target_quality": target_quality,
            "target_snr": target_snr_val,
            "required_density": required_density,
            "sfd_comp_target": sfd_comp_target,
            "table_name": table_name,
            "calc_time": raw_time,
            "min_calc": min_calc,
            "sec_calc": sec_calc,
            "base_multiplier": base_multiplier,
            "raw_time": raw_time,
            "r_controlled": r_controlled,
            "barrier_str": barrier_str,
            "filter_recs": filter_recs,
            "filter_str": filter_str,
            "asme_iqi_str": asme_iqi_str,
            "chart_label": chart_label,
            "safety_radius_m": r_controlled if source != "x_ray" else None,
            "sfd_min_provenance": geo["sfd_min_provenance"],
            "f_min_provenance": geo["f_min_provenance"],
        }

        return {
            "calculated": calculated,
            "warnings": warnings,
            "display": display,
            "values": values,
            "form": f,
        }

    # ------------------------------------------------------------------
    # Applied vs required compliance check
    # ------------------------------------------------------------------
    def check_compliance(self, form, calculated, lvl3=None, lang="tr"):
        f = normalize_form(form)
        lvl3 = lvl3 or {}
        if self.trans.language != lang:
            self.trans.set_language(lang)

        inputs = {
            "tech": f["tech"],
            "source": f["source"],
            "class": f["testing_class"],
            "geometry": f["geometry"],
            "film_side": bool(f["film_side"]),
            "iqi_type": f["iqi_type"],
            "snr_location": f["snr_location"],
            "material": f["material"],
            "t": f["t"],
        }
        applied = {
            "applied_kv": f["app_kv"],
            "applied_activity": f["app_activity"],
            "applied_sfd": f["sfd"],
            "applied_time": f["app_time"],
            "applied_wire": f["app_wire"],
            "applied_duplex": f["app_duplex"],
            "applied_quality": f["app_quality"],
            "applied_srb": f["app_srb"],
            "applied_film_class": f["film_class_used"],
            "applied_overlap": f["app_overlap"],
            "applied_exposures": f["app_exposures"],
        }
        res = self.proc_checker.check_compliance(inputs, calculated, applied, lvl3, lang)

        activity_warning = None
        activity_diff = 0.0
        if f["source"] != "x_ray":
            calc_activity = f["output_val"]
            applied_activity = f["app_activity"]
            activity_diff = abs(applied_activity - calc_activity) / max(0.1, calc_activity)
            if activity_diff > 0.15:
                if self.trans.language == "tr":
                    activity_warning = (f"KAYNAK AKTİVİTE UYARISI: Hesaplama girdisi {calc_activity:.1f} Ci iken "
                                        f"uygulanan {applied_activity:.1f} Ci'dir (%{activity_diff*100:.0f} fark). "
                                        "Bu durum poz süresini etkiler.")
                else:
                    activity_warning = (f"SOURCE ACTIVITY WARNING: Calculation base is {calc_activity:.1f} Ci but applied "
                                        f"is {applied_activity:.1f} Ci ({activity_diff*100:.0f}% diff). This affects exposure time.")
        res = dict(res)
        res["activity_warning"] = activity_warning
        res["activity_diff"] = activity_diff
        return res

    # ------------------------------------------------------------------
    # Defect evaluation (shared by desktop, mobile and web)
    # ------------------------------------------------------------------
    def evaluate_defect(self, form, defect, lang="tr"):
        """Evaluates a defect record against the selected standard.

        ``defect`` keys: standard (api1104/iso5817/b31_3/viii), type,
        length, width, accumulated, level (ISO 5817), service (B31.3),
        mode (ASME VIII). Returns ``{"status", "result", "details"}``.
        """
        from src.core.iso5817 import ISO5817Evaluator
        from src.core.asme_b31_3 import ASMEB31_3Evaluator
        from src.core.asme_viii import ASMEVIIIEvaluator
        from src.core.api1104 import API1104Evaluator

        f = normalize_form(form)
        if self.trans.language != lang:
            self.trans.set_language(lang)

        defect = defect or {}
        standard = defect.get("standard", "api1104")
        defect_type = defect.get("type", "defect_porosity")
        t = f["t"]
        length = _as_float(defect.get("length"), 0.0)
        width = _as_float(defect.get("width"), 0.0)
        accumulated = _as_float(defect.get("accumulated"), 0.0)

        approx = False
        try:
            if standard == "iso5817":
                is_ok, reason = ISO5817Evaluator().evaluate(
                    defect_type, t, length, width, accumulated,
                    level=defect.get("level", "C"), lang=lang)
                approx = True
            elif standard == "b31_3":
                is_ok, reason = ASMEB31_3Evaluator().evaluate(
                    defect_type, t, length, width, accumulated,
                    service=defect.get("service", "normal"), lang=lang)
                approx = True
            elif standard == "viii":
                is_ok, reason = ASMEVIIIEvaluator().evaluate(
                    defect_type, t, length, width, accumulated,
                    mode=defect.get("mode", "UW-51"), lang=lang)
                approx = True
            else:
                is_ok, reason = API1104Evaluator().evaluate(
                    defect_type, t, length, width, accumulated, lang)
        except Exception as exc:  # never crash the UI
            logger.exception("evaluate_defect failed")
            return {"status": False, "result": str(exc), "details": str(exc), "approx": False}

        if approx:
            note = self.trans.get("defect_approx_note")
            reason = f"{reason}\n\n{note}"

        return {
            "status": bool(is_ok),
            "result": str(reason),
            "details": str(reason),
            "approx": approx,
            "standard": standard,
            "type": defect_type,
            "length": length,
            "width": width,
            "accumulated": accumulated,
        }
