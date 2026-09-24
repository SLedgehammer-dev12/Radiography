import sys
import os
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.calculator import RTCalculator
from core.api1104 import API1104Evaluator
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
        vals = self.get_form_values()

        # 1. Thicknesses (calculate_thicknesses returns tuple (w_nom, w_eff))
        try:
            w_nom, w_eff = self.calc.calculate_thicknesses(vals["t"], vals["cap"], vals["geometry"])
        except Exception:
            logger.exception("calculate_thicknesses failed")
            w_nom = vals["t"]
            w_eff = vals["t"]

        # 2. Tube voltage limit
        try:
            u_max = self.calc.calculate_u_max(w_nom, vals["material"])
        except Exception:
            logger.exception("calculate_u_max failed")
            u_max = 0.0

        # 3. Object-to-detector distance (b) - mirrors desktop logic
        geometry = vals["geometry"]
        t = vals["t"]
        od = vals["od"]
        is_curved = vals.get("detector_curved", False)
        std_figure = None  # mobile doesn't have std_figure selector
        testing_class = vals["testing_class"]

        try:
            bed = float(vals.get("bed", 0.0))
        except (TypeError, ValueError):
            bed = 0.0
        try:
            bgap = float(vals.get("bgap", 5.0))
        except (TypeError, ValueError):
            bgap = 5.0

        if is_curved and self.calc.is_central_projection(geometry, std_figure):
            b_dist = self.calc.calculate_b_panoramic(bed, bgap, t)
        elif is_curved:
            b_dist = self.calc.calculate_b_curved(bed, bgap, t, testing_class)
        else:
            b_dist = t if geometry in ["swsi", "dwsi"] else od
        b_eff, b_rule_applied = self.calc.get_effective_b(b_dist, t)

        # 4. Minimum source-to-object distance (f_min)
        try:
            d = float(vals.get("focal_size", 2.0))
        except (TypeError, ValueError):
            d = 2.0
        try:
            f_min = self.calc.calculate_f_min(d, b_dist, testing_class, t)
        except Exception:
            logger.exception("calculate_f_min failed")
            f_min = 0.0

        # 5. Source-to-detector distance minimum (sfd_min)
        sfd_min = f_min + b_dist
        # Detector size constraint
        try:
            dd = float(vals.get("detector_size", 200.0))
        except (TypeError, ValueError):
            dd = 200.0
        sdd_min = self.calc.calculate_sdd_min(dd)
        if sdd_min > sfd_min:
            sfd_min = sdd_min

        # 6. Geometric unsharpness (Ug) - use applied SFD, f = SFD - b
        try:
            sfd = float(vals.get("app_sfd", vals.get("sfd", 600.0)))
        except (TypeError, ValueError):
            sfd = 600.0
        try:
            ug = self.calc.calculate_geometric_unsharpness_from_sfd(d, b_dist, sfd)
        except Exception:
            logger.exception("calculate_geometric_unsharpness failed")
            ug = 0.0

        # 7. IQI targets (single wire / duplex) - these return (display_str, wire_no) tuples
        #    film_side is the inverse of "IQI on source side" (desktop parity)
        film_side = not bool(vals.get("film_side", False))
        try:
            single_wire_iqi = self.calc.get_single_wire_iqi(
                vals["t"], vals["cap"], vals["testing_class"],
                vals["geometry"], vals["tech"], film_side,
                self.language
            )
        except Exception:
            logger.exception("get_single_wire_iqi failed")
            single_wire_iqi = ("-", 0)
        try:
            duplex_iqi = self.calc.get_duplex_iqi(w_nom, vals["testing_class"], vals["geometry"], self.language)
        except Exception:
            logger.exception("get_duplex_iqi failed")
            duplex_iqi = ("-", 0)

        # 8. Exposure time
        try:
            base_e = 3.0 if vals["source"] == "x_ray" else \
                (30.0 if vals["source"] == "isotope_ir192" else
                 (40.0 if vals["source"] == "isotope_se75" else
                  (20.0 if vals["source"] == "isotope_co60" else
                   (150.0 if vals["source"] == "isotope_yb169" else 500.0))))
            _min, _sec, calc_time = self.calc.calculate_exposure_time(
                sfd=sfd,
                w_eff=w_eff,
                source=vals["source"],
                output_val=vals["output_val"],
                base_factor=base_e,
                tech=vals["tech"],
                testing_class=vals["testing_class"],
                film_class=vals["film_class_used"],
                detector_type=vals["detector_type"],
                kv=vals["kv"] if vals["source"] == "x_ray" else None,
                material=vals["material"],
            )
        except Exception:
            logger.exception("calculate_exposure_time failed")
            calc_time = 0.0
        # Field correction factor (F)
        try:
            f_mult = float(self.base_multiplier)
        except (TypeError, ValueError):
            f_mult = 1.0
        if f_mult <= 0.0:
            f_mult = 1.0
        calc_time = calc_time * f_mult

        # 9. Quality targets
        # get_target_snr returns (base_snr, table_name, description)
        try:
            base_snr, snr_table, _snr_desc = self.calc.get_target_snr(
                vals["material"], vals["source"], vals["kv"],
                w_nom, vals["testing_class"], self.language
            )
        except Exception:
            logger.exception("get_target_snr failed")
            base_snr, snr_table = 70.0, ""
        # 1.4x SNR_N target for adjacent (HAZ) measurement on a non-flush weld
        # and for Se-75 w < 12 mm Class B (ISO 17636-2:2022 Clauses 7.3.1/6.9)
        is_flush = (vals["cap"] == 0.0)
        se75_thin_class_b = (
            vals["material"] in ("steel", "copper_nickel")
            and vals["source"] == "isotope_se75"
            and w_nom < 12.0
            and vals["testing_class"] == "class_b"
        )
        target_snr = base_snr
        if (vals.get("snr_location") == "adjacent" and not is_flush) or se75_thin_class_b:
            target_snr = base_snr * 1.4
        # Required optical density (analog)
        if (
            vals["material"] in ("steel", "copper_nickel")
            and vals["source"] == "isotope_se75"
            and w_nom < 12.0
            and vals["testing_class"] == "class_b"
        ):
            required_density = 3.0
        else:
            required_density = 2.3 if vals["testing_class"] == "class_b" else 2.0
        try:
            req_film = self.calc.get_required_film_class(w_nom, vals["testing_class"], vals["material"], vals["source"])
        except Exception:
            logger.exception("get_required_film_class failed")
            req_film = ""
        try:
            filter_rec = self.calc.get_filter_recommendations(vals["source"], vals["material"], vals["kv"], vals["testing_class"])
        except Exception:
            logger.exception("get_filter_recommendations failed")
            filter_rec = ""

        # 10. Exposure count
        try:
            if geometry == "swsi":
                exposures = 1
            elif geometry == "dwdi_elliptic":
                exposures = self.calc.get_dwdi_elliptical_exposures(vals["od"], vals["t"])
            elif geometry == "dwdi_super":
                exposures = 3
            else:  # dwsi
                exposures = self.calc.calculate_dwsi_exposures(vals["od"], vals["t"], sfd, testing_class)
        except Exception:
            logger.exception("exposure count calculation failed")
            exposures = 0

        # 11. DWDI geometry warnings (localized)
        dwdi_warnings = []
        if vals["geometry"] in ("dwdi_elliptic", "dwdi_super"):
            dwdi_res = self.calc.validate_dwdi(
                vals["geometry"], vals["od"], vals["t"], vals.get("weld_width")
            )
            tr = self.language == "tr"
            if not dwdi_res["od_ok"]:
                dwdi_warnings.append("DWDI only valid for OD <= 100 mm" if not tr else "DWDI sadece OD <= 100 mm için geçerlidir")
            if vals["geometry"] == "dwdi_elliptic":
                if not dwdi_res["t_ok"]:
                    dwdi_warnings.append("DWDI elliptical: t must be <= 8 mm (ISO 17636-1 7.1.6)" if not tr else "DWDI eliptik: t <= 8 mm olmalı (ISO 17636-1 7.1.6)")
                if not dwdi_res["weld_width_ok"]:
                    dwdi_warnings.append(f"Weld width must be <= De/4 = {vals['od'] / 4.0:.1f} mm" if not tr else f"Kaynak genişliği De/4 = {vals['od'] / 4.0:.1f} mm'den küçük olmalı")
                dwdi_warnings.append(
                    "t/De >= 0.12 -> 3 images (ISO 17636-1 7.1.6)" if not tr else "t/De >= 0.12 -> 3 poz (ISO 17636-1 7.1.6)"
                    if dwdi_res["needs_three"] else
                    "t/De < 0.12 -> 2 images (ISO 17636-1 7.1.6)" if not tr else "t/De < 0.12 -> 2 poz (ISO 17636-1 7.1.6)"
                )
            else:
                dwdi_warnings.append("DWDI super: 3 exposures (120°/60°) (ISO 17636-1 7.1.7)" if not tr else "DWDI üstüste: 3 poz (120°/60°) (ISO 17636-1 7.1.7)")
        self.warnings = dwdi_warnings

        # 12. Radiation barrier distance (isotopes)
        barrier_str = ""
        if vals["source"] != "x_ray":
            try:
                act_ci = float(vals.get("output_val", 0) or 0)
            except (TypeError, ValueError):
                act_ci = 0.0
            r_c, _, _ = self.calc.calculate_barrier_distance(vals["source"], act_ci, limit_usvh=20.0, hvl_layers=0.0, convention="r")
            r_s, _, _ = self.calc.calculate_barrier_distance(vals["source"], act_ci, limit_usvh=7.5, hvl_layers=0.0, convention="r")
            if self.language == "tr":
                barrier_str = f"Kontrollü (20 µSv/h): {r_c:.1f} m | Gözetimli (7.5): {r_s:.1f} m"
            else:
                barrier_str = f"Controlled (20 µSv/h): {r_c:.1f} m | Supervised (7.5): {r_s:.1f} m"

        # 13. Store results (keep tuples as-is for UI; store wire/duplex numbers separately)
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
            "base_multiplier": self.base_multiplier,
            "target_snr": target_snr,
            "req_exposures": exposures,
            "warnings": self.warnings,
            "barrier_distance": barrier_str,
            "required_film_class": req_film,
            "filter_recommendation": filter_rec,
            "required_quality": target_snr if vals["tech"] == "digital" else required_density,
            "required_density": required_density,
            "snr_table": snr_table,
        }

        # 14. Procedure compliance check
        try:
            wire_no = single_wire_iqi[1] if isinstance(single_wire_iqi, tuple) else 0
            duplex_no = duplex_iqi[1] if isinstance(duplex_iqi, tuple) else 0
            max_srb = self.calc.get_max_srb(w_nom, testing_class, geometry)

            calced = {
                "u_max": u_max,
                "sfd_min": sfd_min,
                "required_wire_no": wire_no,
                "required_duplex_no": duplex_no,
                "required_film_class": req_film,
                "required_density": required_density,
                "required_snr": target_snr,
                "ug": ug,
                "calc_time_raw": calc_time,
                "max_srb": max_srb,
                "required_exposures": exposures,
                "exposures_graph": exposures,
                "exposures_panel": None,
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
                "applied_exposures": vals.get("app_exposures", 0),
            }
            inputs = {
                "tech": vals["tech"],
                "source": vals["source"],
                "class": vals["testing_class"],
                "geometry": vals["geometry"],
                "material": vals["material"],
                "t": vals["t"],
                "iqi_type": vals["iqi_type"],
                "film_side": film_side,
            }
            self.compliance = self.proc_checker.check_compliance(
                inputs, calced, applied, {}, self.language
            )
        except Exception as e:
            logger.exception("procedure compliance check failed")
            self.compliance = {"is_compliant": False, "checks": [], "error": str(e)}

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
