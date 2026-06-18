import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.calculator import RTCalculator
from core.api1104 import API1104Evaluator
from core.procedure_check import ProcedureComplianceChecker
from core.translation import Translation


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
        self.custom_od = None
        self.custom_wall = None
        self.use_standard = True
        self.cap = 3.0

        self.kv = 120.0
        self.ma = 5.0
        self.exposure_time = 120.0
        self.sfd = 600.0
        self.film_class = "C5"
        self.detector_type = "cr_standard"
        self.detector_curved = False
        self.bed = 10.0
        self.bgap = 5.0

        self.app_sfd = 600.0
        self.app_kv = 120.0
        self.app_activity = 40.0
        self.app_time = 120.0
        self.app_quality = 140.0
        self.app_overlap = 10.0
        self.app_srb = 80.0
        self.app_wire = 10
        self.app_duplex = 6
        self.film_class_used = "C5"
        self.snr_location = "weld"
        self.iqi_type = "wire"

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
        return {
            "od": od,
            "t": wall,
            "cap": self.cap,
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
            "output_val": self.ma,
            "app_sfd": self.app_sfd,
            "app_kv": self.app_kv,
            "app_activity": self.app_activity,
            "app_time": self.app_time,
            "app_quality": self.app_quality,
            "app_overlap": self.app_overlap,
            "app_srb": self.app_srb,
            "app_wire": self.app_wire,
            "app_duplex": self.app_duplex,
            "film_class_used": self.film_class_used,
            "film_class": self.film_class,
            "snr_location": self.snr_location,
            "iqi_type": self.iqi_type,
        }

    def run_calculations(self):
        vals = self.get_form_values()

        try:
            thicknesses = self.calc.calculate_thicknesses(vals["t"], vals["cap"], vals["geometry"])
            w_nom = thicknesses.get("w_nom", vals["t"])
            w_eff = thicknesses.get("w_eff", vals["t"])
        except Exception:
            w_nom = vals["t"]
            w_eff = vals["t"]

        try:
            u_max = self.calc.calculate_u_max(w_nom, vals["material"])
        except Exception:
            u_max = 0.0
        try:
            f_min = self.calc.calculate_f_min(0, 0, vals["testing_class"], w_nom)
        except Exception:
            f_min = 0.0
        try:
            sdd_min = self.calc.calculate_sdd_min(vals.get("detector_size", 0))
        except Exception:
            sdd_min = 0.0
        try:
            ug = self.calc.calculate_geometric_unsharpness(vals.get("focal_size", 2), 0, 0)
        except Exception:
            ug = 0.0
        try:
            single_wire_iqi = self.calc.get_single_wire_iqi(
                vals["t"], vals["cap"], vals["testing_class"],
                vals["geometry"], vals["tech"], vals["film_side"],
                self.language
            )
        except Exception:
            single_wire_iqi = {"w_no": 0, "label": "-"}
        try:
            duplex_iqi = self.calc.get_duplex_iqi(w_nom, vals["testing_class"], vals["geometry"], self.language)
        except Exception:
            duplex_iqi = {"d_no": 0, "label": "-"}
        try:
            sfd_min = self.calc.calculate_sfd_min(0, 0, vals["testing_class"], w_nom)
        except Exception:
            sfd_min = 0.0
        try:
            calc_time = self.calc.calculate_exposure_time(
                vals["app_sfd"], w_eff, vals["source"],
                vals["output_val"], 3.0, vals["film_class"],
                vals["material"], vals["kv"], None, vals["tech"],
                vals["testing_class"], vals["app_kv"], vals["app_activity"],
            )
        except Exception:
            calc_time = 0.0
        try:
            target_snr = self.calc.get_target_snr(
                vals["material"], vals["source"], vals["kv"],
                w_nom, vals["testing_class"], self.language
            )
        except Exception:
            target_snr = 0
        try:
            req_film = self.calc.get_required_film_class(w_nom, vals["testing_class"], vals["material"], vals["source"])
        except Exception:
            req_film = ""
        try:
            filter_rec = self.calc.get_filter_recommendations(vals["source"], vals["material"], vals["kv"], vals["testing_class"])
        except Exception:
            filter_rec = ""
        try:
            exposures = self.calc.calculate_dwsi_exposures(vals["od"], vals["t"], sfd_min)
        except Exception:
            exposures = 0

        self.results = {
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max,
            "f_min": f_min,
            "sfd_min": sfd_min,
            "sdd_min": sdd_min,
            "ug": ug,
            "single_wire_iqi": single_wire_iqi,
            "duplex_iqi": duplex_iqi,
            "calc_time": calc_time,
            "target_snr": target_snr,
            "req_exposures": exposures,
            "required_film_class": req_film,
            "filter_recommendation": filter_rec,
            "required_quality": target_snr if vals["tech"] == "digital" else 2.0,
        }

        try:
            calced = {
                "u_max": u_max,
                "sfd_min": sfd_min,
                "required_wire_no": single_wire_iqi.get("w_no", 0),
                "required_duplex_no": duplex_iqi.get("d_no", 0),
                "required_film_class": req_film,
                "required_density": 2.0,
                "required_snr": target_snr,
                "ug": ug,
                "calc_time_raw": calc_time,
                "max_srb": 100.0,
            }
            applied = {
                "applied_kv": vals["app_kv"],
                "applied_sfd": vals["app_sfd"],
                "applied_wire": vals["app_wire"],
                "applied_duplex": vals["app_duplex"],
                "applied_film_class": vals["film_class_used"],
                "applied_overlap": vals["app_overlap"],
                "applied_quality": vals["app_quality"],
                "applied_srb": vals["app_srb"],
                "applied_time": vals["app_time"],
                "applied_activity": vals["app_activity"],
            }
            inputs = {
                "tech": vals["tech"],
                "source": vals["source"],
                "class": vals["testing_class"],
                "geometry": vals["geometry"],
                "material": vals["material"],
                "t": vals["t"],
                "iqi_type": vals["iqi_type"],
                "film_side": vals["film_side"],
            }
            self.compliance = self.proc_checker.check_compliance(
                inputs, calced, applied, {}, self.language
            )
        except Exception as e:
            self.compliance = {"is_compliant": False, "checks": [], "error": str(e)}

        self._calc_dirty = False
        return self.results

    def evaluate_defect(self, defect_type, length, width, accumulated):
        try:
            vals = self.get_form_values()
            self.defect_eval = self.api1104.evaluate(
                defect_type, vals["t"], length, width, accumulated, self.language
            )
        except Exception as e:
            self.defect_eval = {"status": False, "result": "error", "details": str(e)}
        return self.defect_eval

    def get_text(self, key):
        return self.trans.get(key)
