import sys
import os
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.calculator import RTCalculator
from core.api1104 import API1104Evaluator
from core.engine import CalculationEngine
from core.procedure_check import ProcedureComplianceChecker
from core.translation import Translation

logger = logging.getLogger("radiography.mobile.app_state")


class AppState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.calc = RTCalculator()
        self.api1104 = API1104Evaluator()
        self.proc_checker = ProcedureComplianceChecker()
        self.trans = Translation()
        self.engine = CalculationEngine(calc=self.calc, proc_checker=self.proc_checker)

        self.tech = "analog"
        self.technique = "swsi"
        self.material = "steel"
        self.testing_class = "class_a"
        self.source = "x_ray"
        self.geometry = "swsi"
        self.source_side_iqi = False

        self.pipe_od_std = '4" (NPS 4)'
        self.pipe_od = 114.3
        self.pipe_wall = 6.02
        self.pipe_schedule = "SCH 40 / STD"
        self.custom_od = None
        self.custom_wall = None
        self.use_standard = True
        self.cap = 3.0
        self.weld_width = 8.0

        self.kv = 120.0
        self.ma = 5.0
        self.exposure_time = 120.0
        self.base_multiplier = 1.0
        self.sfd = 600.0
        self.film_class = "C5"
        self.detector_type = "cr_standard"
        self.detector_curved = False
        self.bed = 10.0
        self.bgap = 5.0
        self.d = 2.0
        self.dd = 200.0

        self.app_sfd = 600.0
        self.app_kv = 120.0
        self.app_activity = 40.0
        self.app_time = 120.0
        self.app_quality = 140.0
        self.app_overlap = 10.0
        self.app_srb = 80.0
        self.app_wire = 10
        self.app_duplex = 6
        self.app_exposures = 0
        self.film_class_used = "C5"
        self.snr_location = "weld"
        self.iqi_type = "wire"
        self.defect_standard = "api1104"
        self.defect_level = "C"
        self.b31_service = "normal"
        self.viii_mode = "UW-51"

        self.results = {}
        self.compliance = {}
        self.defect_eval = None
        self.warnings = []

        self.current_step = 0
        self.is_dark_theme = True
        self.language = "tr"
        self._calc_dirty = True

    def get(self, key, default=None):
        return getattr(self, key, default)

    def set(self, key, value):
        setattr(self, key, value)
        self._calc_dirty = True

    def get_form_values(self):
        od = self.pipe_od
        wall = self.pipe_wall
        output_val = self.ma if self.source == "x_ray" else self.app_activity
        return {
            "od": od,
            "t": wall,
            "cap": self.cap,
            "weld_width": self.weld_width,
            "tech": self.tech,
            "source": self.source,
            "material": self.material,
            "testing_class": self.testing_class,
            "geometry": self.geometry,
            "film_side": self.source_side_iqi,
            "detector_type": self.detector_type,
            "detector_curved": self.detector_curved,
            "bed": self.bed,
            "bgap": self.bgap,
            "kv": self.kv,
            "output_val": output_val,
            "base_multiplier": self.base_multiplier,
            "sfd": self.sfd,
            "app_sfd": self.app_sfd,
            "app_kv": self.app_kv,
            "app_activity": self.app_activity,
            "app_time": self.app_time,
            "app_quality": self.app_quality,
            "app_overlap": self.app_overlap,
            "app_srb": self.app_srb,
            "app_wire": self.app_wire,
            "app_duplex": self.app_duplex,
            "app_exposures": self.app_exposures,
            "film_class_used": self.film_class_used,
            "film_class": self.film_class,
            "snr_location": self.snr_location,
            "iqi_type": self.iqi_type,
            "focal_size": getattr(self, "d", 2.0),
            "detector_size": getattr(self, "dd", 200.0),
        }

    def run_calculations(self):
        """Runs the shared calculation engine and maps the result to the
        mobile result dict shape (kept stable for the Kivy screens and the
        mobile PDF helper)."""
        vals = self.get_form_values()

        base_e = 3.0 if vals["source"] == "x_ray" else (
            30.0 if vals["source"] == "isotope_ir192" else (
                40.0 if vals["source"] == "isotope_se75" else (
                    20.0 if vals["source"] == "isotope_co60" else (
                        150.0 if vals["source"] == "isotope_yb169" else 500.0))))

        form = {
            "od": vals["od"],
            "t": vals["t"],
            "cap": vals["cap"],
            "weld_width": vals["weld_width"],
            "d": vals["focal_size"],
            "sfd": vals["app_sfd"],
            "output_val": vals["output_val"],
            "base_e": base_e,
            "detector_type": vals["detector_type"],
            "film_class_used": vals["film_class_used"],
            "chart_source": "model",
            "tech": vals["tech"],
            "material": vals["material"],
            "source": vals["source"],
            "testing_class": vals["testing_class"],
            "geometry": vals["geometry"],
            "standard": "iso",
            "iqi_type": vals["iqi_type"],
            "film_side": not bool(vals["film_side"]),
            "snr_location": vals["snr_location"],
            "std_figure": None,
            "panel_width": 200.0,
            "panel_height": 200.0,
            "panel_overlap": 10.0,
            "app_exposures": vals.get("app_exposures", 0),
            "film_width": 0.0,
            "film_height": 0.0,
            "f_source": None,
            "b_object": None,
            "bed": vals.get("bed", 0.0),
            "bgap": vals.get("bgap", 5.0),
            "app_kv": vals["app_kv"],
            "app_activity": vals["app_activity"],
            "app_time": vals["app_time"],
            "app_quality": vals["app_quality"],
            "app_overlap": vals["app_overlap"],
            "app_srb": vals["app_srb"],
            "app_wire": vals["app_wire"],
            "app_duplex": vals["app_duplex"],
            "barrier_limit_usvh": 20.0,
            "collimator_hvl": 0.0,
            "gamma_convention": "r",
            "base_multiplier": self.base_multiplier,
            "base_multiplier_raw": self.base_multiplier,
        }

        result = self.engine.calculate(form, {}, self.language)
        values = result["values"]
        calculated = result["calculated"]

        self.warnings = list(result["warnings"])
        self.results = {
            "w_nom": values["w_nom"],
            "w_eff": values["w_eff"],
            "u_max": values["u_max"],
            "f_min": values["f_min"],
            "sfd_min": values["sfd_min"],
            "sdd_min": values["sdd_min"],
            "ug": values["ug"],
            "single_wire_iqi": (values["wire_str"], values["wire_no"]),
            "duplex_iqi": (values["duplex_str"], values["duplex_no"]),
            "calc_time": values["calc_time"],
            "base_multiplier": values["base_multiplier"],
            "target_snr": values["target_snr"],
            "req_exposures": values["exposures"],
            "warnings": self.warnings,
            "barrier_distance": values["barrier_str"],
            "required_film_class": values["film_class_req"],
            "filter_recommendation": values["filter_recs"],
            "required_quality": values["target_snr"] if vals["tech"] == "digital" else values["required_density"],
            "required_density": values["required_density"],
            "snr_table": values["table_name"],
            "sfd_min_provenance": values.get("sfd_min_provenance"),
            "exposures_provenance": values.get("exposures_provenance"),
            "f_min_provenance": values.get("f_min_provenance"),
        }

        self.compliance = self.engine.check_compliance(form, calculated, {}, self.language)
        self._calc_dirty = False
        return self.results

    def evaluate_defect(self, defect_type, length, width, accumulated):
        try:
            vals = self.get_form_values()
            approx = False
            if self.defect_standard == "iso5817":
                from core.iso5817 import ISO5817Evaluator
                self.defect_eval = ISO5817Evaluator().evaluate(
                    defect_type, vals["t"], length, width, accumulated,
                    level=self.defect_level, lang=self.language
                )
                approx = True
            elif self.defect_standard == "b31_3":
                from core.asme_b31_3 import ASMEB31_3Evaluator
                self.defect_eval = ASMEB31_3Evaluator().evaluate(
                    defect_type, vals["t"], length, width, accumulated,
                    service=self.b31_service, lang=self.language
                )
                approx = True
            elif self.defect_standard == "viii":
                from core.asme_viii import ASMEVIIIEvaluator
                self.defect_eval = ASMEVIIIEvaluator().evaluate(
                    defect_type, vals["t"], length, width, accumulated,
                    mode=self.viii_mode, lang=self.language
                )
                approx = True
            else:
                self.defect_eval = self.api1104.evaluate(
                    defect_type, vals["t"], length, width, accumulated, self.language
                )
            if approx and isinstance(self.defect_eval, tuple):
                is_ok, result = self.defect_eval
                note = self.get_text("defect_approx_note")
                self.defect_eval = (is_ok, f"{result}\n\n{note}")
            self.defect_eval = self._normalize_defect_result(self.defect_eval)
        except Exception as e:
            logger.exception("evaluate_defect failed")
            self.defect_eval = {"status": False, "result": "error", "details": str(e)}
        return self.defect_eval

    @staticmethod
    def _normalize_defect_result(result):
        """Normalizes (is_accepted, message) tuples / dicts into one dict shape
        so the Kivy screens and the mobile PDF helper can always use .get()."""
        if isinstance(result, tuple) and len(result) == 2:
            ok, msg = result
            return {"status": bool(ok), "result": str(msg), "details": str(msg)}
        if isinstance(result, dict):
            return result
        return {"status": False, "result": str(result), "details": str(result)}

    def get_text(self, key):
        return self.trans.get(key)

    def check_updates(self, callback=None):
        """Asynchronously checks for updates and invokes callback with result dict."""
        import threading
        from core.updater import UpdateChecker

        def _worker():
            checker = UpdateChecker()
            res = checker.check()
            if callback:
                callback(res)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
