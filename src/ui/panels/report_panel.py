# -*- coding: utf-8 -*-

import logging
import os
import tempfile
from datetime import datetime

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from src.core.engine import format_f_min_provenance


logger = logging.getLogger("radiography.ui.report_panel")


class ReportExportMixin:
    """Mixin that renders the in-memory calculation state to a PDF report."""

    def export_pdf_report(self):
        # 1. Ask where to save
        file_filter = "PDF Files (*.pdf)"
        now_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"RT_Inspection_Report_{now_date}.pdf"
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Report", filename, file_filter)

        if not filepath:
            return

        # 2. Gather values for report
        od, t, cap, weld_width, d, sfd, output_val, base_e, detector_type, film_class_used, _chart_source = self.get_form_values()
        material_keys = ["steel", "aluminum", "titanium", "copper_nickel"]
        material = material_keys[self.cmb_material.currentIndex()]
        tech = "digital" if self.rad_digital.isChecked() else "analog"
        source_keys = ["x_ray", "isotope_ir192", "isotope_se75", "isotope_co60", "isotope_yb169", "isotope_tm170"]
        source = source_keys[self.cmb_source.currentIndex()]
        testing_class = "class_b" if self.cmb_class.currentIndex() == 0 else "class_a"
        geom_keys = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"]
        geometry = geom_keys[self.cmb_geometry.currentIndex()]

        # Mirror the DWDI -> DWSI forcing applied by update_calculations so the
        # report always describes the same technique as the screen.
        if od > 100.0 and geometry in ["dwdi_elliptic", "dwdi_super"]:
            geometry = "dwsi"

        standard = self.cmb_standard.currentData() if hasattr(self, "cmb_standard") else "iso"

        try:
            input_kv = float(self.txt_app_kv.text().replace(",", "."))
        except ValueError:
            input_kv = 120.0

        try:
            overlap = self._to_mm(float(self.txt_app_overlap.text().replace(",", ".")))
        except ValueError:
            overlap = 10.0

        inputs = {
            "material_text": self.trans.get(material),
            "class_text": self.trans.get(testing_class),
            "od": od,
            "t": t,
            "cap": cap,
            "weld_width": weld_width,
            "d": d,
            "sfd": sfd,
            "output_val": output_val,
            "base_e": base_e,
            "speed": film_class_used if tech == "analog" else detector_type,
            "tech": tech,
            "tech_text": self.trans.get("analog_film" if tech == "analog" else "digital_cr_dda"),
            "source": source,
            "source_text": self.trans.get(source),
            "geometry": geometry,
            "geometry_text": self.trans.get(geometry),
            "standard": standard,
            "report_info": self.get_report_info(),
            "input_kv": input_kv,
            "overlap": overlap,
            "iqi_type": self.cmb_iqi_type.currentData(),
            "snr_location": self.cmb_snr_location.currentData(),
            "film_side": not self.chk_source_side_iqi.isChecked()
        }

        # Gather outputs — use the same shared geometry block as the screen
        # (Level 3 reductions and the DWSI physical floor included), so the PDF
        # can never disagree with the UI.
        w_nom, w_eff = self.calc.calculate_thicknesses(t, cap, geometry)
        u_max = self.calc.calculate_u_max(w_nom, material)
        geo = self._compute_geometry(od, t, d, sfd, geometry, testing_class,
                                     standard=standard, lvl3_settings=self.lvl3_settings)
        f_min_iso = geo["f_min_iso"]
        f_min_asme = geo["f_min_asme"]
        sfd_min = geo["sfd_min"]
        ug = geo["ug"]

        if geometry == "swsi":
            exposures = 1
        elif geometry == "dwdi_elliptic":
            exposures = self.calc.get_dwdi_elliptical_exposures(od, t)
        elif geometry == "dwdi_super":
            exposures = 3
        else:
            exposures = self.calc.calculate_dwsi_exposures(od, t, sfd, testing_class)
        exposures = self.last_calculated.get("exposures_graph", exposures)

        film_side = not self.chk_source_side_iqi.isChecked()
        iqi_type = self.cmb_iqi_type.currentData()
        if iqi_type == "step_hole":
            wire_str, _ = self.calc.get_step_hole_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=self.trans.language)
        else:
            wire_str, _ = self.calc.get_single_wire_iqi(t, cap, testing_class, geometry, tech=tech, film_side=film_side, lang=self.trans.language)

        duplex_str, _ = self.calc.get_duplex_iqi(w_nom, testing_class, geometry, lang=self.trans.language)

        target_quality = self.out_labels["quality_target"][1].text()
        calc_time = self.out_labels["calc_time"][1].text()

        outputs = {
            "w_nom": w_nom,
            "w_eff": w_eff,
            "u_max": u_max if source == "x_ray" else None,
            "f_min": f_min_iso,
            "f_min_asme": f_min_asme,
            "sfd_min": sfd_min,
            "ug": ug,
            "exposures": self.last_calculated.get("required_exposures", exposures),
            "exposures_panel": self.last_calculated.get("exposures_panel"),
            "exposures_film": self.last_calculated.get("exposures_film"),
            "exposures_applied": self.last_calculated.get("exposures_applied"),
            "exposures_check": self.last_calculated.get("exposures_ok"),
            "single_wire_iqi": wire_str,
            "duplex_iqi": duplex_str if tech == "digital" else "N/A",
            "asme_iqi": self.last_calculated.get("asme_iqi", "N/A"),
            "barrier_distance": self.last_calculated.get("barrier_distance", "N/A"),
            "quality_target": target_quality,
            "calc_time": calc_time,
            "total_joint_time": self.last_calculated.get("total_joint_time_str", "N/A"),
            "suggestions": self.last_calculated.get("suggestions", []),
            "base_multiplier": self.last_calculated.get("base_multiplier", 1.0),
            "detector_quality": self.out_labels["detector_quality"][1].text(),
            "filter_recommendation": self.out_labels["filter_recommendation"][1].text(),
            "f_min_provenance_text": format_f_min_provenance(
                self.last_calculated.get("f_min_provenance"), self.trans),
            "sfd_min_provenance_text": self._format_sfd_provenance(
                self.last_calculated.get("sfd_min_provenance")),
            "exposures_provenance_text": self._format_exposures_provenance(
                self.last_calculated.get("exposures_provenance")),
            "exposure_time_provenance_text": self.last_calculated.get(
                "exposure_time_provenance_text"
            ),
        }

        # Gather defect details if evaluated
        defect_eval = None
        defect_text = self.lbl_defect_result.text()
        if defect_text:
            defect_types = ["defect_ip", "defect_if", "defect_ic", "defect_porosity", "defect_crack", "defect_slag", "defect_undercut", "defect_burn_through"]
            defect_type = defect_types[self.cmb_defect_type.currentIndex()]

            # Defect dimensions must be converted to mm exactly like the
            # on-screen evaluation, otherwise inch mode makes the PDF verdict
            # contradict the screen.
            try:
                def_len = self._to_mm(float(self.txt_defect_length.text().replace(",", ".")))
            except ValueError:
                def_len = 0.0

            try:
                def_width = self._to_mm(float(self.txt_defect_width.text().replace(",", ".")))
            except ValueError:
                def_width = 0.0

            try:
                def_accum = self._to_mm(float(self.txt_defect_accum.text().replace(",", ".")))
            except ValueError:
                def_accum = 0.0

            # evaluate again to get full details through the active standard
            is_accepted, reason = self.api_eval.evaluate(defect_type, t, def_len, def_width, def_accum, self.trans.language)
            defect_standard = self.cmb_defect_standard.currentData()
            approx = False
            if defect_standard == "iso5817":
                from src.core.iso5817 import ISO5817Evaluator
                is_accepted, reason = ISO5817Evaluator().evaluate(
                    defect_type, t, def_len, def_width, def_accum,
                    level=self.cmb_quality_level.currentText(), lang=self.trans.language
                )
                approx = True
            elif defect_standard == "b31_3":
                from src.core.asme_b31_3 import ASMEB31_3Evaluator
                is_accepted, reason = ASMEB31_3Evaluator().evaluate(
                    defect_type, t, def_len, def_width, def_accum,
                    service=self.cmb_b31_service.currentData(), lang=self.trans.language
                )
                approx = True
            elif defect_standard == "viii":
                from src.core.asme_viii import ASMEVIIIEvaluator
                is_accepted, reason = ASMEVIIIEvaluator().evaluate(
                    defect_type, t, def_len, def_width, def_accum,
                    mode=self.cmb_viii_mode.currentData(), lang=self.trans.language
                )
                approx = True
            if approx:
                reason = f"{reason}\n\n{self.trans.get('defect_approx_note')}"

            defect_eval = {
                "active": True,
                "type_text": self.trans.get(defect_type),
                "len": def_len,
                "width": def_width,
                "accum": def_accum,
                "status": is_accepted,
                "reason": reason
            }

        # Warnings list
        warnings_text = self.txt_warnings.text()
        warnings_list = warnings_text.split("\n") if warnings_text != "No active warnings." else []

        # Distance-compensation target SNR: reuse the value computed for the
        # screen (dynamic Table 3/4 base, 1.4x HAZ factor, final sfd_min).
        sfd_comp_val = self.last_calculated.get("sfd_comp_target")
        if sfd_comp_val is None and self.lvl3_settings.get("sfd_comp") and sfd < sfd_min:
            base_snr = self.last_calculated.get("required_snr")
            if base_snr is None:
                base_snr = 130.0 if testing_class == "class_b" else 70.0
            sfd_comp_val = base_snr * (sfd_min / max(10.0, sfd))

        lvl3_active = any(self.lvl3_settings.get(k) for k in (
            "sfd_comp", "voltage_override", "isotope_flex",
            "source_flex", "central_proj_reduction", "dw_reduction",
        ))

        # Save sketch images to temporary files for PDF embedding
        tmp_dynamic = None
        tmp_standard = None
        dynamic_img_path = None
        standard_img_path = None
        try:
            tmp_dynamic = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_dynamic.close()
            self.canvas.save_figure(tmp_dynamic.name)
            dynamic_img_path = tmp_dynamic.name
        except Exception:
            logger.exception("Failed to save dynamic sketch for PDF")
            dynamic_img_path = None

        try:
            tmp_standard = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_standard.close()
            self.std_canvas.save_figure(tmp_standard.name)
            standard_img_path = tmp_standard.name
        except Exception:
            logger.exception("Failed to save standard sketch for PDF")
            standard_img_path = None

        success = self.pdf_gen.generate_report(
            filepath, inputs, outputs, warnings_list, defect_eval,
            lvl3_active,
            sfd_comp_val, self.trans,
            dynamic_img_path=dynamic_img_path,
            standard_img_path=standard_img_path,
            lvl3=getattr(self, "lvl3_settings", None),
        )

        # Clean up temporary image files
        for p in [dynamic_img_path, standard_img_path]:
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    logger.exception("Failed to remove temp sketch file %s", p)

        if success:
            QMessageBox.information(self, self.trans.get("success"), self.trans.get("report_saved", filepath))
        else:
            QMessageBox.critical(self, self.trans.get("error"), "Could not save PDF report.")
