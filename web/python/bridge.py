# -*- coding: utf-8 -*-
"""Pyodide bridge: JSON-in / JSON-out RPC for the Radiography web front-end.

The browser worker writes the Python core (src/core) and this module into the
Pyodide virtual filesystem, then calls ``handle(request_json)``. Keeping the
bridge this thin means the web build runs exactly the same calculation code as
the desktop and mobile apps.
"""

import base64
import json
import math
import os

from src.core.engine import (  # noqa: F401
    CalculationEngine,
    format_exposures_provenance,
    format_f_min_provenance,
    format_sfd_provenance,
    normalize_form,
)
from src.core.translation import Translation
from src.core.version import __version__

_engine = CalculationEngine()
_trans = Translation()
_chart_loaded = False


def _ensure_chart_db():
    """Loads the exposure chart dataset from the virtual FS when present."""
    global _chart_loaded
    if _chart_loaded:
        return
    _chart_loaded = True
    path = "/python/exposure_chart_dataset.json"
    if os.path.exists(path):
        try:
            from src.core.exposure_charts import ExposureChartDatabase
            _engine.set_chart_db(ExposureChartDatabase(path))
        except Exception:
            pass


def _clean(value):
    """Converts NaN/Infinity to None so the result is valid JSON for JS."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _dumps(payload):
    return json.dumps(_clean(payload), ensure_ascii=False)


def _build_report_inputs(form, calculated, display, lang, report_info):
    tech = form.get("tech", "digital")
    source = form.get("source", "x_ray")
    geometry = form.get("geometry", "dwsi")
    return {
        "material_text": _trans.get(form.get("material", "steel")),
        "class_text": _trans.get(form.get("testing_class", "class_b")),
        "od": form.get("od"),
        "t": form.get("t"),
        "cap": form.get("cap"),
        "weld_width": form.get("weld_width"),
        "d": form.get("d"),
        "sfd": form.get("sfd"),
        "output_val": form.get("output_val"),
        "base_e": form.get("base_e"),
        "speed": form.get("film_class_used") if tech == "analog" else form.get("detector_type"),
        "tech": tech,
        "tech_text": _trans.get("digital_cr_dda" if tech == "digital" else "analog_film"),
        "source": source,
        "source_text": _trans.get(source),
        "geometry": geometry,
        "geometry_text": _trans.get(geometry),
        "standard": form.get("standard", "iso"),
        "report_info": report_info or {},
        "input_kv": form.get("app_kv") if source == "x_ray" else None,
        "overlap": form.get("app_overlap"),
        "iqi_type": form.get("iqi_type", "wire"),
        "snr_location": form.get("snr_location", "weld"),
    }


def _build_report_outputs(calculated, display):
    return {
        "w_nom": calculated.get("w_nom"),
        "w_eff": calculated.get("w_eff"),
        "u_max": calculated.get("u_max"),
        "f_min": calculated.get("f_min_iso"),
        "f_min_asme": calculated.get("f_min_asme"),
        "sfd_min": calculated.get("sfd_min"),
        "ug": calculated.get("ug"),
        "exposures": calculated.get("exposures_graph"),
        "exposures_panel": calculated.get("exposures_panel"),
        "exposures_applied": calculated.get("exposures_applied"),
        "exposures_check": calculated.get("exposures_ok"),
        "single_wire_iqi": display.get("single_wire_iqi"),
        "duplex_iqi": display.get("duplex_iqi"),
        "asme_iqi": display.get("asme_iqi"),
        "barrier_distance": display.get("barrier_distance"),
        "quality_target": display.get("quality_target"),
        "calc_time": display.get("calc_time"),
        "base_multiplier": calculated.get("base_multiplier"),
        "detector_quality": display.get("detector_quality"),
        "filter_recommendation": display.get("filter_recommendation"),
        "f_min_provenance_text": format_f_min_provenance(
            calculated.get("f_min_provenance"), _trans),
        "sfd_min_provenance_text": format_sfd_provenance(
            calculated.get("sfd_min_provenance"), _trans),
        "exposures_provenance_text": format_exposures_provenance(
            calculated.get("exposures_provenance"), _trans),
    }


def handle(request_json):
    request = json.loads(request_json)
    action = request.get("action")
    payload = request.get("payload") or {}
    lang = payload.get("lang", "tr")
    _ensure_chart_db()

    if action == "ping":
        return _dumps({"version": __version__})

    if action == "translations":
        if lang not in _trans.translations:
            lang = "tr"
        return _dumps({"language": lang, "strings": _trans.translations[lang]})

    if action == "pipe_data":
        from src.core.asme_b36 import ASME_B36_10_PIPES, ASME_B36_19_PIPES
        return _dumps({
            "b36_10": {k: {"od": v[0], "schedules": v[1]} for k, v in ASME_B36_10_PIPES.items()},
            "b36_19": {k: {"od": v[0], "schedules": v[1]} for k, v in ASME_B36_19_PIPES.items()},
        })

    if action == "calculate":
        result = _engine.calculate(
            payload.get("form") or {},
            payload.get("lvl3") or {},
            lang,
        )
        return _dumps(result)

    if action == "geometry":
        result = _engine.compute_geometry(payload.get("form") or {}, payload.get("lvl3") or {})
        return _dumps(result)

    if action == "compliance":
        result = _engine.check_compliance(
            payload.get("form") or {},
            payload.get("calculated") or {},
            payload.get("lvl3") or {},
            lang,
        )
        return _dumps(result)

    if action == "defect":
        result = _engine.evaluate_defect(
            payload.get("form") or {},
            payload.get("defect") or {},
            lang,
        )
        return _dumps(result)

    if action == "decay":
        calc = _engine.calc
        days = calc.decay_days_since(
            payload.get("calib_date", ""), payload.get("inspection_date"))
        current = calc.calculate_decayed_activity(
            float(payload.get("activity", 0.0) or 0.0),
            payload.get("calib_date", ""),
            payload.get("inspection_date"),
            payload.get("isotope", "isotope_ir192"),
        )
        return _dumps({"days": days, "current_activity": current})

    if action == "standard_figures":
        # Figure catalogue filtered by technology, detector shape and geometry,
        # mirroring the desktop update_std_figure_list() rule exactly.
        tech = payload.get("tech", "digital")
        geometry = payload.get("geometry", "dwsi")
        curved = bool(payload.get("detector_curved", False))
        # Butt-weld arrangements only: Figures 6/7/9/10 (and digital a/b
        # equivalents) are set-in/set-on corner welds and are excluded.
        if tech == "digital":
            if geometry == "swsi":
                if curved:
                    figures = ["fig2a", "fig5a", "fig8a"]
                else:
                    figures = ["fig2b", "fig5b", "fig8b"]
            elif geometry in ("dwdi_elliptic", "dwdi_super"):
                figures = ["fig11", "fig12"]
            else:  # dwsi
                figures = ["fig13a", "fig14a"] if curved else ["fig13b", "fig14b"]
        else:
            if geometry == "swsi":
                figures = ["fig2", "fig5", "fig8"]
            elif geometry in ("dwdi_elliptic", "dwdi_super"):
                figures = ["fig11", "fig12"]
            else:  # dwsi
                figures = ["fig13", "fig14"]
        return _dumps({"figures": figures})

    if action == "iqi_options":
        return _dumps({
            "wire": {str(k): v for k, v in _engine.calc.wire_diameters.items()},
            "step_hole": {str(k): v for k, v in _engine.calc.step_hole_dias.items()},
        })

    if action == "generate_pdf":
        from src.core.report import PDFReportGenerator

        if lang not in _trans.translations:
            lang = "tr"
        _trans.set_language(lang)
        form = payload.get("form") or {}
        calculated = payload.get("calculated") or {}
        display = payload.get("display") or {}

        inputs = _build_report_inputs(form, calculated, display, lang, payload.get("report_info"))
        outputs = _build_report_outputs(calculated, display)

        defect = payload.get("defect")
        if not defect:
            defect = None

        os.makedirs("/tmp", exist_ok=True)
        path = "/tmp/rt_report.pdf"

        image_paths = []
        for key, filename in (
            ("sketch_png_base64", "/tmp/sketch_dynamic.png"),
            ("standard_png_base64", "/tmp/sketch_standard.png"),
        ):
            encoded = payload.get(key)
            if not encoded:
                image_paths.append(None)
                continue
            try:
                if encoded.startswith("data:"):
                    encoded = encoded.split(",", 1)[1]
                with open(filename, "wb") as image_file:
                    image_file.write(base64.b64decode(encoded))
                image_paths.append(filename)
            except Exception:
                image_paths.append(None)

        ok = PDFReportGenerator().generate_report(
            path,
            inputs,
            outputs,
            payload.get("warnings") or [],
            defect,
            bool(payload.get("lvl3_active")),
            payload.get("sfd_comp_val"),
            _trans,
            dynamic_img_path=image_paths[0],
            standard_img_path=image_paths[1],
        )
        for filename in image_paths:
            if filename and os.path.exists(filename):
                try:
                    os.remove(filename)
                except OSError:
                    pass
        if not ok:
            raise RuntimeError("PDF generation failed")
        with open(path, "rb") as handle_file:
            data = handle_file.read()
        return _dumps({
            "pdf_base64": base64.b64encode(data).decode("ascii"),
            "filename": payload.get("filename") or "RT_Inspection_Report.pdf",
        })

    if action == "filter_recommendation":
        recs = _engine.calc.get_filter_recommendations(
            payload.get("source", "x_ray"),
            payload.get("material", "steel"),
            payload.get("kv"),
            payload.get("testing_class", "class_b"),
        )
        from src.core.translation import format_filter_recommendation
        return _dumps({
            "raw": recs,
            "formatted": format_filter_recommendation(recs, lang),
        })

    raise ValueError("Unknown action: %s" % action)
