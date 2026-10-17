# -*- coding: utf-8 -*-


class TranslationMixin:
    """Mixin that re-applies the active language to every label and dropdown."""

    def retranslate_ui(self):
        # Update Window title
        self.setWindowTitle(self.trans.get("app_title"))
        self.lbl_title.setText(self.trans.get("app_title"))
        self.btn_lang.setText(self.trans.get("lang_switch"))
        self.btn_lvl3.setText(self.trans.get("level3_section"))
        self.btn_export.setText(self.trans.get("export_pdf"))
        self.btn_theme.setText(self.trans.get("theme_light") if self.is_dark_theme else self.trans.get("theme_dark"))

        # Re-populate dropdowns with current language text
        material_idx = self.cmb_material.currentIndex()
        self.cmb_material.clear()
        for key in ("steel", "aluminum", "titanium", "copper_nickel"):
            self.cmb_material.addItem(self.trans.get(key), key)
        self.cmb_material.setCurrentIndex(material_idx)

        source_idx = self.cmb_source.currentIndex()
        self.cmb_source.clear()
        for key in ("x_ray", "isotope_ir192", "isotope_se75", "isotope_co60",
                    "isotope_yb169", "isotope_tm170"):
            self.cmb_source.addItem(self.trans.get(key), key)
        self.cmb_source.setCurrentIndex(source_idx)

        class_idx = self.cmb_class.currentIndex()
        self.cmb_class.clear()
        for key in ("class_b", "class_a"):
            self.cmb_class.addItem(self.trans.get(key), key)
        self.cmb_class.setCurrentIndex(class_idx)

        geom_idx = self.cmb_geometry.currentIndex()
        self.cmb_geometry.blockSignals(True)
        self.cmb_geometry.clear()
        for key in ("dwsi", "swsi", "dwdi_elliptic", "dwdi_super"):
            self.cmb_geometry.addItem(self.trans.get(key), key)
        self.cmb_geometry.setCurrentIndex(geom_idx)
        self.cmb_geometry.blockSignals(False)

        # Update input labels & text boxes labels
        self.lbl_std_od.setText(self.trans.get("std_pipe_od"))
        self.lbl_custom_od.setText(self.trans.get("custom_pipe_od"))
        self.lbl_std_t.setText(self.trans.get("std_nominal_t"))
        self.lbl_custom_t.setText(self.trans.get("custom_nominal_t"))
        self.txt_custom_od.setPlaceholderText(self.trans.get("custom_od_placeholder"))
        self.txt_custom_t.setPlaceholderText(self.trans.get("custom_t_placeholder"))

        self.rad_analog.setText(self.trans.get("analog_film"))
        self.rad_digital.setText(self.trans.get("digital_cr_dda"))
        self.lbl_film_class_used.setText(self.trans.get("film_class_used"))
        self.lbl_detector_type.setText(self.trans.get("detector_type"))
        # Refresh detector type combobox labels and chart source options
        for i, tkey in enumerate(self._det_trans_keys):
            self.cmb_detector_type.setItemText(i, self.trans.get(tkey))
        self.update_chart_source_list()
        self._retranslate_input_panel()
        self._retranslate_warnings_panel()
        self._retranslate_compliance_panel()
        self.sketch_box.setTitle(self.trans.get("sketch_title"))
        self.chk_source_side_iqi.setText(self.trans.get("source_side_iqi"))

        # Re-translate IQI type & SNR location comboboxes
        self.lbl_iqi_type.setText(self.trans.get("iqi_type"))
        iqi_idx = self.cmb_iqi_type.currentIndex()
        self.cmb_iqi_type.blockSignals(True)
        self.cmb_iqi_type.clear()
        self.cmb_iqi_type.addItem(self.trans.get("iqi_type_wire"), "wire")
        self.cmb_iqi_type.addItem(self.trans.get("iqi_type_step_hole"), "step_hole")
        self.cmb_iqi_type.setCurrentIndex(iqi_idx)
        self.cmb_iqi_type.blockSignals(False)

        self.lbl_snr_location.setText(self.trans.get("snr_location"))
        snr_idx = self.cmb_snr_location.currentIndex()
        self.cmb_snr_location.blockSignals(True)
        self.cmb_snr_location.clear()
        self.cmb_snr_location.addItem(self.trans.get("snr_location_weld"), "weld")
        self.cmb_snr_location.addItem(self.trans.get("snr_location_adjacent"), "adjacent")
        self.cmb_snr_location.setCurrentIndex(snr_idx)
        self.cmb_snr_location.blockSignals(False)

        # Obsolete inputs deleted

        # Re-translate Output Labels & Tooltips
        for name, (lbl, val) in self.out_labels.items():
            if name == "quality_target":
                target_name = "target_snr" if self.rad_digital.isChecked() else "optical_density"
                lbl.setText(self.trans.get(target_name))
            elif name == "single_wire_iqi":
                if self.cmb_iqi_type.currentData() == "step_hole":
                    lbl.setText(self.trans.get("single_step_hole_iqi"))
                else:
                    lbl.setText(self.trans.get("single_wire_iqi"))
            elif name == "sfd_min":
                lbl.setText(self.trans.get(
                    "sfd_min" if self.rad_digital.isChecked() else "sfd_min_analog"))
            else:
                lbl.setText(self.trans.get(name))

            # Update info button tooltip
            if name in self.info_buttons:
                self.info_buttons[name].setToolTip(self.trans.get("tt_" + name))

        # Re-translate defect evaluation UI
        self._retranslate_defect_panel()

        # Update tab titles
        self.tab_sketch.setTabText(0, self.trans.get("tab_dynamic"))
        self.tab_sketch.setTabText(1, self.trans.get("tab_standard"))

        # Update QGroupBox titles
        if hasattr(self, "grp_inputs"):
            self.grp_inputs.setTitle(self.trans.get("inputs_section"))
        if hasattr(self, "grp_exposure"):
            self.grp_exposure.setTitle(self.trans.get("applied_exposure_section"))
        if hasattr(self, "grp_outputs"):
            self.grp_outputs.setTitle(self.trans.get("outputs"))
        if hasattr(self, "grp_compliance"):
            self.grp_compliance.setTitle(self.trans.get("procedure_section"))
        if hasattr(self, "sketch_box"):
            self.sketch_box.setTitle(self.trans.get("sketch_title"))
        if hasattr(self, "grp_warnings"):
            self.grp_warnings.setTitle(self.trans.get("warnings"))
        if hasattr(self, "grp_defect"):
            self.grp_defect.setTitle(self.trans.get("defect_section"))
        if hasattr(self, "grp_report_info"):
            self.grp_report_info.setTitle(self.trans.get("report_info_section"))
            for attr, key, _ in self._report_fields:
                self._report_labels[attr].setText(self.trans.get(key))

        self.lbl_app_sfd.setText(self.trans.get(
            "applied_sdd" if self.rad_digital.isChecked() else "applied_sfd"))
        self.lbl_app_time.setText(self.trans.get("applied_time"))
        self.lbl_app_kv.setText(self.trans.get("applied_kv"))
        self.lbl_app_activity.setText(self.trans.get("applied_activity"))
        self.lbl_base_multiplier.setText(self.trans.get("base_multiplier"))
        self.txt_base_multiplier.setToolTip(self.trans.get("tt_base_multiplier"))
        self._update_base_e()

        # Standard selector retranslation
        if hasattr(self, "cmb_standard"):
            std_idx = self.cmb_standard.currentIndex()
            self.cmb_standard.blockSignals(True)
            self.cmb_standard.clear()
            self.cmb_standard.addItem(self.trans.get("standard_iso"), "iso")
            self.cmb_standard.addItem(self.trans.get("standard_asme"), "asme")
            self.cmb_standard.setCurrentIndex(std_idx)
            self.cmb_standard.blockSignals(False)

        # ASME IQI sensitivity retranslation
        if hasattr(self, "cmb_asme_sensitivity"):
            s_idx = self.cmb_asme_sensitivity.currentIndex()
            self.lbl_asme_sensitivity.setText(self.trans.get("asme_sensitivity"))
            self.cmb_asme_sensitivity.blockSignals(True)
            self.cmb_asme_sensitivity.clear()
            self.cmb_asme_sensitivity.addItem(self.trans.get("sens_2_2t"), "2-2T")
            self.cmb_asme_sensitivity.addItem(self.trans.get("sens_2_1t"), "2-1T")
            self.cmb_asme_sensitivity.addItem(self.trans.get("sens_1_2t"), "1-2T")
            self.cmb_asme_sensitivity.setCurrentIndex(s_idx)
            self.cmb_asme_sensitivity.blockSignals(False)

        # Collimator / barrier limit labels
        if hasattr(self, "lbl_collimator"):
            self.lbl_collimator.setText(self.trans.get("collimator"))
            self.lbl_barrier_limit.setText(self.trans.get("barrier_limit_label"))
            self.lbl_gamma_convention.setText(self.trans.get("gamma_convention"))
            self.cmb_gamma_convention.setToolTip(self.trans.get("tt_gamma_convention"))
            g_idx = self.cmb_gamma_convention.currentIndex()
            self.cmb_gamma_convention.blockSignals(True)
            self.cmb_gamma_convention.clear()
            self.cmb_gamma_convention.addItem(self.trans.get("gamma_conv_r"), "r")
            self.cmb_gamma_convention.addItem(self.trans.get("gamma_conv_msv"), "msv")
            self.cmb_gamma_convention.setCurrentIndex(g_idx)
            self.cmb_gamma_convention.blockSignals(False)
            self.btn_decay.setText(self.trans.get("decay_dialog"))

        if self.cmb_iqi_type.currentData() == "step_hole":
            self.lbl_app_wire.setText(self.trans.get("applied_step_hole"))
        else:
            self.lbl_app_wire.setText(self.trans.get("applied_wire"))

        self.lbl_app_duplex.setText(self.trans.get("applied_duplex"))
        self.lbl_app_srb.setText(self.trans.get("applied_srb"))
        self.lbl_app_overlap.setText(self.trans.get("applied_overlap"))

        # Panel coverage inputs (digital only)
        self.lbl_panel_width.setText(self.trans.get("panel_width"))
        self.lbl_panel_height.setText(self.trans.get("panel_height"))
        self.lbl_panel_overlap.setText(self.trans.get("panel_overlap"))
        self.lbl_app_exposures.setText(self.trans.get("applied_exposures"))

        is_digital = self.rad_digital.isChecked()
        if is_digital:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (SNR_N):")
        else:
            self.lbl_app_quality.setText(self.trans.get("applied_quality") + " (D):")

        # Re-populate standard figure dropdown
        self.update_std_figure_list()

        # Update dynamic standard figure text
        self.lbl_dynamic_standard_ref.setText(f"{self.trans.get('standard_fig')} {self.cmb_std_figure.currentText()}")

        # Redraw
        self.update_calculations()
