# -*- coding: utf-8 -*-

class ProcedureComplianceChecker:
    def __init__(self):
        pass

    def check_compliance(self, inputs, calculated, applied, lvl3_settings, lang="tr"):
        """
        Compares user's applied values against standard/calculated targets.
        Returns: {
            "is_compliant": bool,
            "checks": [ { "name": str, "status": bool, "details": str } ]
        }
        """
        checks = []
        is_compliant = True

        tech = inputs.get("tech", "digital")
        source = inputs.get("source", "x_ray")
        testing_class = inputs.get("class", "class_b")

        # Translation dictionary
        trans = {
            "tr": {
                "voltage_pass": "Tüp Voltajı Uygun: {:.1f} kV <= Maksimum {:.1f} kV limit.",
                "voltage_fail": "TÜP VOLTAJI UYGUN DEĞİL! Uygulanan: {:.1f} kV > Limit: {:.1f} kV.",
                "voltage_lvl3": "Tüp Voltajı Limiti Aşımı Seviye 3 Yetkisi ile onaylanmıştır ({:.1f} kV).",
                
                "sfd_pass": "Çekim Mesafesi Uygun: {:.1f} mm >= Önerilen Min. {:.1f} mm.",
                "sfd_fail": "ÇEKİM MESAFESİ UYGUN DEĞİL! Uygulanan: {:.1f} mm < Önerilen Min: {:.1f} mm.",
                "sfd_lvl3": "Çekim Mesafesi Yetersizliği Seviye 3 Mesafe Telafisi ile onaylanmıştır.",
                
                "wire_pass": "Single Wire IQI Uygun: Çözülen W {} >= Gereken W {}.",
                "wire_fail": "IQI HASSASİYETİ YETERSİZ! Çözülen W {} < Gereken W {}. İnce detaylar ayırt edilemiyor.",
                "hole_pass": "Step & Hole IQI Uygun: Çözülen H {} <= Gereken H {}.",
                "hole_fail": "IQI HASSASİYETİ YETERSİZ! Çözülen H {} > Gereken H {}. Delik ayırt edilemiyor.",
                "dwsi_placement_fail": "IQI KONUMLANDIRMA HATASI! DWSI geometrisinde IQI kaynak tarafına yerleştirilemez (film tarafında olmalıdır).",
                
                "duplex_pass": "Duplex IQI Uygun: Çözülen D {} >= Gereken D {}.",
                "duplex_fail": "DUBLEX IQI ÇÖZÜNÜRLÜĞÜ YETERSİZ! Çözülen D {} < Gereken D {}.",
                
                "density_pass": "Optik Yoğunluk Uygun: {:.2f} >= Standart Min. {:.2f}.",
                "density_fail": "OPTİK YOĞUNLUK YETERSİZ! Uygulanan: {:.2f} < Standart Min: {:.2f}.",
                
                "snr_pass": "SNR_N Değeri Uygun: {:.1f} >= Standart Min. {:.1f}.",
                "snr_fail": "SNR_N DEĞERİ YETERSİZ! Uygulanan: {:.1f} < Standart Min: {:.1f}.",
                
                "ug_pass": "Geometrik Bulanıklık (Ug) Uygun: {:.3f} mm (kabul edilebilir seviye).",
                "ug_fail": "GEOMETRİK BULANIKLIK (Ug) YÜKSEK! Ug={:.3f} mm. f_min artırılmalı.",
                "annex_f_pass": "Annex F: Ug/SRb oranı uygun ({:.1f} <= 2.0).",
                "annex_f_fail": "Annex F UYARISI: Ug/SRb ({:.1f}) > 2.0! f_min artırılmalı veya SNR yükseltilmeli.",
                "time_pass": "Poz Süresi Uygun: Önerilen süreye yakın ({:d} dk {:d} sn).",
                "time_diff": "POZ SÜRESİ FARKLILIĞI! Önerilen: {:d} dk {:d} sn, Uygulanan: {:d} dk {:d} sn (%{:.0f} fark).",
                "film_class_pass": "Film Sınıfı Uygun: {} (Gereken asgari: {})",
                "film_class_fail": "FİLM SINIFI YETERSİZ! Uygulanan: {} < Gereken asgari: {}",
                "srb_pass": "SRb Çözünürlüğü Uygun: {} µm <= Maksimum {} µm limit.",
                "srb_fail": "SRb ÇÖZÜNÜRLÜĞÜ YETERSİZ! Uygulanan: {} µm > Maksimum Limit: {} µm.",
                "overlap_pass": "Film Bindirme Uygun: {:.1f} mm >= Asgari 10.0 mm.",
                "overlap_fail": "FİLM BİNDİRME MESAFESİ YETERSİZ! Uygulanan: {:.1f} mm < Asgari: 10.0 mm.",
            },
            "en": {
                "voltage_pass": "Tube Voltage Compliant: {:.1f} kV <= Max {:.1f} kV limit.",
                "voltage_fail": "TUBE VOLTAGE NON-COMPLIANT! Applied: {:.1f} kV > Limit: {:.1f} kV.",
                "voltage_lvl3": "Tube Voltage Limit Override approved by Level 3 authority ({:.1f} kV).",
                
                "sfd_pass": "Shooting Distance Compliant: {:.1f} mm >= Recommended Min. {:.1f} mm.",
                "sfd_fail": "SHOOTING DISTANCE NON-COMPLIANT! Applied: {:.1f} mm < Recommended Min: {:.1f} mm.",
                "sfd_lvl3": "Insufficient SFD approved under Level 3 Distance Compensation.",
                
                "wire_pass": "Single Wire IQI Compliant: Resolved W {} >= Required W {}.",
                "wire_fail": "IQI SENSITIVITY INSUFFICIENT! Resolved W {} < Required W {}. Fine details cannot be discerned.",
                "hole_pass": "Step & Hole IQI Compliant: Resolved H {} <= Required H {}.",
                "hole_fail": "IQI SENSITIVITY INSUFFICIENT! Resolved H {} > Required H {}. Hole cannot be discerned.",
                "dwsi_placement_fail": "IQI PLACEMENT ERROR! In DWSI geometry, the IQI cannot be placed on the source side (must be on film side).",
                
                "duplex_pass": "Duplex IQI Compliant: Resolved D {} >= Required D {}.",
                "duplex_fail": "DUPLEX RESOLUTION INSUFFICIENT! Resolved D {} < Required D {}.",
                
                "density_pass": "Optical Density Compliant: {:.2f} >= Standard Min. {:.2f}.",
                "density_fail": "OPTICAL DENSITY INSUFFICIENT! Applied: {:.2f} < Standard Min: {:.2f}.",
                
                "snr_pass": "SNR_N Compliant: {:.1f} >= Standard Min. {:.1f}.",
                "snr_fail": "SNR_N INSUFFICIENT! Applied: {:.1f} < Standard Min: {:.1f}.",
                
                "time_pass": "Exposure Time Compliant: Close to calculated value ({:d} min {:d} sec).",
                "time_diff": "EXPOSURE TIME DISCREPANCY! Calculated: {:d} min {:d} sec, Applied: {:d} min {:d} sec ({:.0f}% diff).",
                "ug_pass": "Geometric Unsharpness (Ug) OK: {:.3f} mm (acceptable level).",
                "ug_fail": "GEOMETRIC UNSHARPNESS (Ug) HIGH! Ug={:.3f} mm. Increase f_min.",
                "annex_f_pass": "Annex F: Ug/SRb ratio OK ({:.1f} <= 2.0).",
                "annex_f_fail": "Annex F WARNING: Ug/SRb ({:.1f}) > 2.0! Increase f_min or SNR.",
                "film_class_pass": "Film Class Compliant: {} (Required minimum: {})",
                "film_class_fail": "FILM CLASS INSUFFICIENT! Applied: {} < Required minimum: {}",
                "srb_pass": "SRb Resolution Compliant: {} µm <= Maximum {} µm limit.",
                "srb_fail": "SRb RESOLUTION INSUFFICIENT! Applied: {} µm > Max Limit: {} µm.",
                "overlap_pass": "Film Overlap Compliant: {:.1f} mm >= Min 10.0 mm.",
                "overlap_fail": "FILM OVERLAP INSUFFICIENT! Applied: {:.1f} mm < Min: 10.0 mm.",
            }
        }

        l_msgs = trans.get(lang, trans["tr"])

        # 1. Voltage Check (For X-Ray only)
        if source == "x_ray":
            applied_kv = applied.get("applied_kv", 0.0)
            u_max = calculated.get("u_max", 0.0)
            
            if applied_kv <= u_max:
                checks.append({"name": "voltage", "status": True, "details": l_msgs["voltage_pass"].format(applied_kv, u_max)})
            else:
                if lvl3_settings.get("voltage_override", False):
                    checks.append({"name": "voltage", "status": True, "details": l_msgs["voltage_lvl3"].format(applied_kv)})
                else:
                    is_compliant = False
                    checks.append({"name": "voltage", "status": False, "details": l_msgs["voltage_fail"].format(applied_kv, u_max)})

        # 2. SFD Check
        applied_sfd = applied.get("applied_sfd", 0.0)
        sfd_min = calculated.get("sfd_min", 0.0)
        if applied_sfd >= sfd_min:
            checks.append({"name": "sfd", "status": True, "details": l_msgs["sfd_pass"].format(applied_sfd, sfd_min)})
        else:
            if lvl3_settings.get("sfd_comp", False) and tech == "digital":
                checks.append({"name": "sfd", "status": True, "details": l_msgs["sfd_lvl3"]})
            else:
                is_compliant = False
                checks.append({"name": "sfd", "status": False, "details": l_msgs["sfd_fail"].format(applied_sfd, sfd_min)})

        # 3. Single Wire / Step and Hole IQI Check
        iqi_type = inputs.get("iqi_type", "wire")
        geometry = inputs.get("geometry", "swsi")
        film_side = inputs.get("film_side", False)
        material = inputs.get("material", "steel")
        t_wall = inputs.get("t", 0.0)

        # DWSI Placement constraint: IQI cannot be on source side
        if geometry == "dwsi" and not film_side:
            is_compliant = False
            checks.append({"name": "iqi_placement", "status": False, "details": l_msgs["dwsi_placement_fail"]})

        applied_wire = applied.get("applied_wire", 0)
        req_wire = calculated.get("required_wire_no", 0)

        # Determine the allowed poorer IQI limit under Clause 6.9 exceptions
        allowed_wire_offset = 0 # subtracted from required wire number
        allowed_hole_offset = 0 # added to required hole number (H-No)

        if geometry == "swsi":
            w_pen = t_wall
        else:
            w_pen = 2 * t_wall

        if material in ["steel", "copper_nickel"]:
            if geometry in ["dwdi_elliptic", "dwdi_super"]: # DWDI
                if source == "isotope_ir192" and 10.0 < w_pen <= 25.0:
                    allowed_wire_offset = 1
                    allowed_hole_offset = 1
                elif source == "isotope_se75" and w_pen <= 12.0:
                    allowed_wire_offset = 1
                    allowed_hole_offset = 1
            elif geometry in ["swsi", "dwsi"]: # single-image
                if testing_class == "class_a":
                    if source == "isotope_ir192":
                        if 10.0 < w_pen <= 24.0:
                            allowed_wire_offset = 2
                            allowed_hole_offset = 2
                        elif 24.0 < w_pen <= 30.0:
                            allowed_wire_offset = 1
                            allowed_hole_offset = 1
                    elif source == "isotope_se75" and w_pen <= 24.0:
                        allowed_wire_offset = 1
                        allowed_hole_offset = 1
                else: # class B
                    if source == "isotope_ir192" and 10.0 < w_pen <= 40.0:
                        allowed_wire_offset = 1
                        allowed_hole_offset = 1
                    elif source == "isotope_se75" and w_pen <= 20.0:
                        allowed_wire_offset = 1
                        allowed_hole_offset = 1

        if iqi_type == "wire":
            adjusted_req = req_wire - allowed_wire_offset
            if applied_wire >= adjusted_req:
                if allowed_wire_offset > 0 and applied_wire < req_wire:
                    if lang == "en":
                        details = f"Single Wire IQI Compliant: Resolved W {applied_wire} >= Adjusted req W {adjusted_req} (Clause 6.9 Isotope Exception, Table req: W {req_wire})."
                    else:
                        details = f"Single Wire IQI Uygun: Çözülen W {applied_wire} >= Düzeltilmiş W {adjusted_req} (Madde 6.9 İstisnası, Tablo gereksinimi: W {req_wire})."
                else:
                    details = l_msgs["wire_pass"].format(applied_wire, req_wire)
                checks.append({"name": "wire", "status": True, "details": details})
            else:
                is_compliant = False
                checks.append({"name": "wire", "status": False, "details": l_msgs["wire_fail"].format(applied_wire, req_wire)})
        else: # step_hole
            adjusted_req = req_wire + allowed_hole_offset
            if applied_wire <= adjusted_req:
                if allowed_hole_offset > 0 and applied_wire > req_wire:
                    if lang == "en":
                        details = f"Step & Hole IQI Compliant: Resolved H {applied_wire} <= Adjusted req H {adjusted_req} (Clause 6.9 Isotope Exception, Table req: H {req_wire})."
                    else:
                        details = f"Step & Hole IQI Uygun: Çözülen H {applied_wire} <= Düzeltilmiş H {adjusted_req} (Madde 6.9 İstisnası, Tablo gereksinimi: H {req_wire})."
                else:
                    details = l_msgs["hole_pass"].format(applied_wire, req_wire)
                checks.append({"name": "wire", "status": True, "details": details})
            else:
                is_compliant = False
                checks.append({"name": "wire", "status": False, "details": l_msgs["hole_fail"].format(applied_wire, req_wire)})

        # 4. Duplex IQI Check (Digital only)
        if tech == "digital":
            applied_duplex = applied.get("applied_duplex", 0)
            req_duplex = calculated.get("required_duplex_no", 0)
            if applied_duplex >= req_duplex:
                checks.append({"name": "duplex", "status": True, "details": l_msgs["duplex_pass"].format(applied_duplex, req_duplex)})
            else:
                is_compliant = False
                checks.append({"name": "duplex", "status": False, "details": l_msgs["duplex_fail"].format(applied_duplex, req_duplex)})

        # 5. Film Class Compliance Check (Analog only)
        if tech == "analog":
            applied_film = applied.get("applied_film_class", "")
            req_film = calculated.get("required_film_class", "")
            if applied_film and req_film:
                film_order = ["C1", "C2", "C3", "C4", "C5", "C6"]
                app_idx = film_order.index(applied_film) if applied_film in film_order else 99
                req_idx = film_order.index(req_film) if req_film in film_order else 99
                if app_idx <= req_idx:
                    checks.append({"name": "film_class", "status": True, "details": l_msgs["film_class_pass"].format(applied_film, req_film)})
                else:
                    is_compliant = False
                    checks.append({"name": "film_class", "status": False, "details": l_msgs["film_class_fail"].format(applied_film, req_film)})

        # 6. Film Overlap Check (Analog only)
        if tech == "analog":
            applied_overlap = applied.get("applied_overlap", 0.0)
            if applied_overlap >= 10.0:
                checks.append({"name": "overlap", "status": True, "details": l_msgs["overlap_pass"].format(applied_overlap)})
            else:
                is_compliant = False
                checks.append({"name": "overlap", "status": False, "details": l_msgs["overlap_fail"].format(applied_overlap)})

        # 7. Quality Target Check (Optical Density or SNR)
        applied_quality = applied.get("applied_quality", 0.0)
        if tech == "analog":
            req_density = calculated.get("required_density", 2.3 if testing_class == "class_b" else 2.0)
            if applied_quality >= req_density:
                checks.append({"name": "quality", "status": True, "details": l_msgs["density_pass"].format(applied_quality, req_density)})
            else:
                is_compliant = False
                checks.append({"name": "quality", "status": False, "details": l_msgs["density_fail"].format(applied_quality, req_density)})
        else: # digital
            base_snr = calculated.get("required_snr", 130.0 if testing_class == "class_b" else 70.0)
            if lvl3_settings.get("sfd_comp", False) and applied_sfd < sfd_min:
                req_snr = base_snr * (sfd_min / max(10.0, applied_sfd))
            else:
                req_snr = base_snr

            if applied_quality >= req_snr:
                checks.append({"name": "quality", "status": True, "details": l_msgs["snr_pass"].format(applied_quality, req_snr)})
            else:
                is_compliant = False
                checks.append({"name": "quality", "status": False, "details": l_msgs["snr_fail"].format(applied_quality, req_snr)})

        # 8. Geometric Unsharpness Check
        ug = calculated.get("ug", 0.0)
        if ug > 0.0:
            # Simple threshold: Ug > 0.5mm is considered excessive
            max_ug = 0.5
            if ug <= max_ug:
                checks.append({"name": "ug", "status": True, "details": l_msgs["ug_pass"].format(ug)})
            else:
                is_compliant = False
                checks.append({"name": "ug", "status": False, "details": l_msgs["ug_fail"].format(ug)})

        # 9. SRb Resolution Check (Digital only)
        if tech == "digital":
            applied_srb = applied.get("applied_srb", 0.0)
            max_srb = calculated.get("max_srb", 0)
            if max_srb > 0:
                if applied_srb <= max_srb:
                    checks.append({"name": "srb", "status": True, "details": l_msgs["srb_pass"].format(applied_srb, max_srb)})
                else:
                    is_compliant = False
                    checks.append({"name": "srb", "status": False, "details": l_msgs["srb_fail"].format(applied_srb, max_srb)})

        # 10. Annex F Ug/SRb Check
        max_srb = calculated.get("max_srb", 0)
        if ug > 0 and max_srb > 0:
            ratio = ug / (max_srb / 1000.0)
            if ratio <= 2.0:
                checks.append({"name": "annex_f", "status": True, "details": l_msgs["annex_f_pass"].format(ratio)})
            else:
                is_compliant = False
                checks.append({"name": "annex_f", "status": False, "details": l_msgs["annex_f_fail"].format(ratio)})

        # 11. Exposure Time Check (Warning warning if difference > 25%)
        applied_time = applied.get("applied_time", 0.0) # in seconds
        calc_time_raw = calculated.get("calc_time_raw", 1.0) # in seconds
        
        calc_min = int(calc_time_raw // 60)
        calc_sec = int(calc_time_raw % 60)
        app_min = int(applied_time // 60)
        app_sec = int(applied_time % 60)

        diff = abs(applied_time - calc_time_raw) / max(1.0, calc_time_raw)
        if diff <= 0.25:
            checks.append({"name": "time", "status": True, "details": l_msgs["time_pass"].format(calc_min, calc_sec)})
        else:
            # Generate a warning (time is not critical for compliance in standard directly but good checkpoint)
            # We don't mark is_compliant as False because time deviation is warning-only
            checks.append({"name": "time", "status": True, "details": l_msgs["time_diff"].format(calc_min, calc_sec, app_min, app_sec, diff*100)})

        return {
            "is_compliant": is_compliant,
            "checks": checks
        }
