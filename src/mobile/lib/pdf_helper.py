import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


FONTS = [
    ("NotoSans", os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "NotoSans-Regular.ttf")),
    ("NotoSans-Bold", os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "NotoSans-Bold.ttf")),
    ("NotoSans-Italic", os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "NotoSans-Italic.ttf")),
]


def _register_noto():
    registered = False
    for name, path in FONTS:
        if os.path.exists(path):
            try:
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                pdfmetrics.registerFont(TTFont(name, path))
                registered = True
            except Exception:
                pass
    return registered


def generate_mobile_pdf(filepath, state, results, compliance, defect_eval, sketch_path=None):
    from core.report import PDFReportGenerator
    from core.translation import Translation

    _register_noto()
    trans = Translation()
    lang = state.get("language", "tr")
    trans.set_language(lang)
    lang_obj = trans.translations.get(lang, {})
    vals = state.get_form_values()

    inputs = {
        "material_text": state.get_text(state.material),
        "class_text": state.get_text(state.testing_class),
        "od": vals["od"],
        "t": vals["t"],
        "cap": vals["cap"],
        "sfd": vals.get("app_sfd", vals.get("sfd", 600)),
        "d": 2.0,
        "tech_text": state.get_text(state.geometry),
        "source_text": state.get_text(state.source),
        "geometry_text": state.get_text(state.geometry),
        "source": vals["source"],
        "tech": vals["tech"],
        "input_kv": vals["kv"],
        "output_val": vals["output_val"],
        "overlap": vals.get("app_overlap", 10),
        "iqi_type": vals["iqi_type"],
        "snr_location": vals.get("snr_location", "weld"),
        "geometry": vals["geometry"],
    }

    single_iqi = results.get("single_wire_iqi", ("", ""))
    duplex_iqi = results.get("duplex_iqi", ("", ""))
    calc_time = results.get("calc_time", 0)

    filter_rec = results.get("filter_recommendation", "")
    if isinstance(filter_rec, dict):
        parts = []
        for k, v in filter_rec.items():
            parts.append(f"{k}: {v}")
        filter_rec = "; ".join(parts)
    elif not isinstance(filter_rec, str):
        filter_rec = str(filter_rec)

    outputs = {
        "w_nom": results.get("w_nom", 0),
        "w_eff": results.get("w_eff", 0),
        "u_max": results.get("u_max", 0),
        "f_min": results.get("f_min", 0),
        "sfd_min": results.get("sfd_min", 0),
        "exposures": results.get("req_exposures", 0),
        "single_wire_iqi": single_iqi[0] if isinstance(single_iqi, tuple) else "",
        "duplex_iqi": duplex_iqi[0] if isinstance(duplex_iqi, tuple) else "",
        "calc_time": f"{calc_time:.1f} sn" if isinstance(calc_time, (int, float)) else str(calc_time),
        "detector_quality": "",
        "filter_recommendation": filter_rec,
        "quality_target": str(results.get("target_snr", "")),
    }

    defect_eval_data = {}
    if defect_eval and defect_eval.get("status") is not None:
        defect_eval_data = {
            "active": True,
            "status": defect_eval.get("status"),
            "type_text": state.get_text(state.get("defect_type", "crack")),
            "len": state.get("defect_length", 0),
            "width": state.get("defect_width", 0),
            "accum": state.get("defect_accum", 0),
            "reason": defect_eval.get("result", ""),
        }

    warnings = state.get("warnings", [])

    generator = PDFReportGenerator()
    return generator.generate_report(
        filepath, inputs, outputs, warnings, defect_eval_data,
        False, 0.0, lang_obj,
        dynamic_img_path=sketch_path,
    )


def get_pdf_path():
    directory = tempfile.gettempdir()
    from kivy.utils import platform
    if platform == "android":
        from android.storage import app_storage_path
        directory = app_storage_path()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"RT_Raporu_{timestamp}.pdf")


def share_pdf(filepath):
    from kivy.utils import platform
    if platform == "android":
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            File = autoclass("java.io.File")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            file = File(filepath)
            uri = Uri.fromFile(file)
            intent = Intent(Intent.ACTION_SEND)
            intent.setType("application/pdf")
            intent.putExtra(Intent.EXTRA_STREAM, uri)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            current_activity = PythonActivity.mActivity
            current_activity.startActivity(Intent.createChooser(intent, "Paylaş PDF"))
            return True
        except Exception:
            return False
    else:
        import subprocess
        try:
            subprocess.Popen(["open", filepath])
            return True
        except Exception:
            return False
