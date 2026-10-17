# -*- coding: utf-8 -*-

from src.core.asme_b36 import ASME_B36_10_PIPES
from src.core.engine import MATERIAL_KEYS, SOURCE_KEYS, GEOMETRY_KEYS


class FormStateMixin:
    """Mixin that parses widgets into the shared engine form dict."""

    def get_form_values(self):
        """
        Parses form text inputs safely.
        """
        # Outer Diameter (OD) fallback logic
        custom_od_str = self.txt_custom_od.text().strip().replace(",", ".")
        od = None
        od_from_custom = False
        if custom_od_str:
            try:
                val = float(custom_od_str)
                if val > 0:
                    od = val
                    od_from_custom = True
            except ValueError:
                pass

        if od is None:
            key = self.cmb_od.currentData()
            od = ASME_B36_10_PIPES.get(key, (114.3, []))[0]

        # Wall Thickness (t) fallback logic
        custom_t_str = self.txt_custom_t.text().strip().replace(",", ".")
        t = None
        t_from_custom = False
        if custom_t_str:
            try:
                val = float(custom_t_str)
                if val > 0:
                    t = val
                    t_from_custom = True
            except ValueError:
                pass

        if t is None:
            t = self.cmb_t.currentData()
            if t is None:
                t = 8.56

        try:
            cap = float(self.txt_cap.text().replace(",", "."))
        except ValueError:
            cap = 3.0

        try:
            weld_width = float(self.txt_weld_width.text().replace(",", "."))
        except ValueError:
            weld_width = 8.0

        try:
            d = float(self.txt_d.text().replace(",", "."))
        except ValueError:
            d = 2.0

        try:
            sfd = float(self.txt_app_sfd.text().replace(",", "."))
        except ValueError:
            sfd = 600.0

        source_idx = self.cmb_source.currentIndex()
        if source_idx == 0:  # X-Ray
            try:
                output_val = float(self.txt_output.text().replace(",", "."))
            except ValueError:
                output_val = 5.0
        else:  # Isotopes
            try:
                raw_act = float(self.txt_app_activity.text().replace(",", "."))
                unit = self.cmb_activity_unit.currentText() if hasattr(self, 'cmb_activity_unit') else "Ci"
                if unit == "GBq":
                    output_val = raw_act / 37.0
                else:
                    output_val = raw_act
            except ValueError:
                output_val = 40.0

        # Default exposure-chart constant E per source (index order matches cmb_source).
        default_base_e = (3.0, 30.0, 40.0, 20.0, 150.0, 500.0)
        try:
            base_e = float(self.txt_base_e.text().replace(",", "."))
        except ValueError:
            base_e = 0.0
        if base_e <= 0.0:
            # Empty/invalid field: fall back to the per-source default E instead
            # of a tiny value that would massively under-expose.
            base_e = default_base_e[source_idx] if 0 <= source_idx < len(default_base_e) else 3.0

        # Detector type (digital) or film class (analog)
        detector_type = self._det_keys[self.cmb_detector_type.currentIndex()]
        film_class_used = self.cmb_film_class_used.currentText() or "C5"

        # Chart source
        chart_source = self.cmb_chart_source.currentData() if hasattr(self, 'cmb_chart_source') else "model"

        # Apply unit conversion only for custom-entered values (od/t from text fields)
        # Standard pipe combo values are already in mm and must NOT be double-converted
        return (self._to_mm(od) if od_from_custom else od,
                self._to_mm(t) if t_from_custom else t,
                self._to_mm(cap), self._to_mm(weld_width),
                self._to_mm(d), self._to_mm(sfd), output_val, base_e,
                detector_type, film_class_used, chart_source)

    def _collect_engine_form(self):
        """Collects the current widget state into the shared engine form dict.

        All lengths are converted to mm and activity to Ci so the engine (and
        the web/mobile front-ends) always receive consistent values.
        """
        (od, t, cap, weld_width, d, sfd, output_val, base_e,
         detector_type, film_class_used, chart_source) = self.get_form_values()

        material = MATERIAL_KEYS[self.cmb_material.currentIndex()]
        tech = "digital" if self.rad_digital.isChecked() else "analog"
        source = SOURCE_KEYS[self.cmb_source.currentIndex()]
        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"
        geometry = GEOMETRY_KEYS[self.cmb_geometry.currentIndex()]
        standard = self.cmb_standard.currentData() if hasattr(self, "cmb_standard") else "iso"
        iqi_type = self.cmb_iqi_type.currentData()
        film_side = not self.chk_source_side_iqi.isChecked()
        snr_location = self.cmb_snr_location.currentData()
        std_figure = self.cmb_std_figure.currentData() if hasattr(self, "cmb_std_figure") else None

        panel_width, panel_height, panel_overlap, _panel_app = self.get_panel_inputs()
        film_width, film_height, _df = self.get_film_inputs()
        f_source, b_object = self.get_geometry_override_inputs()

        def _float(widget, default):
            try:
                return float(widget.text().strip().replace(",", "."))
            except (ValueError, AttributeError):
                return default

        def _float_opt(widget):
            text = widget.text().strip().replace(",", ".")
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None

        bed = self._to_mm(_float(self.txt_bed, 0.0))
        bgap = self._to_mm(_float(self.txt_bgap, 5.0))
        app_kv = _float(self.txt_app_kv, 120.0)
        app_time = _float(self.txt_app_time, 0.0)
        app_quality = _float(self.txt_app_quality, 0.0)
        app_srb = _float(self.txt_app_srb, 0.0)
        raw_act = _float(self.txt_app_activity, 0.0)
        unit = self.cmb_activity_unit.currentText() if hasattr(self, "cmb_activity_unit") else "Ci"
        app_activity = raw_act / 37.0 if unit == "GBq" else raw_act

        raw_overlap = _float_opt(self.txt_app_overlap)
        app_overlap = self._to_mm(raw_overlap) if raw_overlap is not None else 10.0
        app_overlap_warn = self._to_mm(raw_overlap) if raw_overlap is not None else 10.0

        barrier_limit = _float(self.txt_barrier_limit, 20.0)
        collimator = float(self.cmb_collimator.currentData() or 0.0)
        gamma_convention = self.cmb_gamma_convention.currentData() if hasattr(self, "cmb_gamma_convention") else "r"
        asme_sensitivity = self.cmb_asme_sensitivity.currentData() if hasattr(self, "cmb_asme_sensitivity") else "2-2T"

        base_multiplier = self.get_base_multiplier()
        raw_mult = _float(self.txt_base_multiplier, 1.0)

        return {
            "od": od, "t": t, "cap": cap, "weld_width": weld_width, "d": d,
            "sfd": sfd, "output_val": output_val, "base_e": base_e,
            "detector_type": detector_type, "film_class_used": film_class_used,
            "chart_source": chart_source,
            "tech": tech, "material": material, "source": source,
            "testing_class": testing_class, "geometry": geometry,
            "standard": standard, "iqi_type": iqi_type, "film_side": film_side,
            "snr_location": snr_location, "std_figure": std_figure,
            "detector_curved": self.rad_detector_curved.isChecked(),
            "panel_width": panel_width, "panel_height": panel_height,
            "panel_overlap": panel_overlap,
            "app_exposures": self.get_applied_exposures(),
            "film_width": film_width, "film_height": film_height,
            "f_source": f_source, "b_object": b_object,
            "bed": bed, "bgap": bgap,
            "app_kv": app_kv, "app_activity": app_activity, "app_time": app_time,
            "app_quality": app_quality, "app_overlap": app_overlap,
            "film_overlap": app_overlap,
            "app_overlap_warn": app_overlap_warn, "app_srb": app_srb,
            "app_wire": self.cmb_app_wire.currentData(),
            "app_duplex": self.cmb_app_duplex.currentData(),
            "barrier_limit_usvh": barrier_limit, "collimator_hvl": collimator,
            "gamma_convention": gamma_convention,
            "asme_sensitivity": asme_sensitivity,
            "base_multiplier": base_multiplier, "base_multiplier_raw": raw_mult,
        }
