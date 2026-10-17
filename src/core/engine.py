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


def format_sfd_provenance(prov, trans):
    """Localized breakdown of SFD_min candidates, governing criterion, and distance compensation."""
    if not prov:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    def label(candidate):
        key = candidate.get("key")
        if key == "f_min_plus_b":
            return trans.get("sfd_prov_f_min") if hasattr(trans, "get") else "f_min + b"
        if key == "coverage":
            is_dd = (candidate.get("receptor") == "dd")
            if hasattr(trans, "get"):
                return trans.get("sfd_prov_coverage_panel" if is_dd else "sfd_prov_coverage_film")
            return "1.4·dd" if is_dd else "1.4·df"
        return trans.get("sfd_prov_dwsi_floor") if hasattr(trans, "get") else "DWSI floor"

    lines = []
    lines.append("Asgari Mesafe Adayları (SFD/SDD):" if tr else "Minimum Distance Candidates (SFD/SDD):")
    active_key = prov.get("active")
    for candidate in prov.get("candidates", []):
        key = candidate.get("key")
        val = candidate.get("value", 0.0)
        f_key = candidate.get("formula_key", "")
        f_lbl = trans.get(f_key) if hasattr(trans, "get") and f_key else f_key

        if key == "f_min_plus_b" and "f_min" in candidate and "b" in candidate:
            detail = f"{candidate['f_min']:.1f} + {candidate['b']:.1f} = {val:.1f} mm"
        elif key == "coverage" and "size" in candidate:
            detail = f"1.4 × {candidate['size']:.1f} = {val:.1f} mm"
        else:
            detail = f"{val:.1f} mm"

        text = f"  • {label(candidate)}: {detail} [{f_lbl}]"
        if key == active_key:
            l3_note = ""
            if candidate.get("l3_dw") or candidate.get("l3_central"):
                l3_note = " — " + (trans.get("sfd_prov_l3") if hasattr(trans, "get") else "L3")
            gov_tag = " ★ [KISITLAYICI / GOVERNING]" if tr else " ★ [GOVERNING]"
            text += f"{l3_note}{gov_tag}"
        lines.append(text)

    if prov.get("is_panoramic"):
        lines.append(
            "  (Panoramik / merkezi projeksiyonda ışın 360° radyal olduğundan 1,4·df düzlemsel kapsaması uygulanmaz)"
            if tr else
            "  (In panoramic / central projection, 360° radial radiation exempts planar 1.4·df coverage)"
        )

    # Comparison with applied SFD & distance compensation
    sfd_app = prov.get("sfd_applied")
    sfd_min = prov.get("sfd_min")
    if sfd_app is not None and sfd_min is not None:
        lines.append("")
        if sfd_app < sfd_min - 0.05:
            if prov.get("lvl3_sfd_comp"):
                k_snr = sfd_min / max(10.0, sfd_app)
                raw_tm = prov.get("time_multiplier", 1.0) or 1.0
                t_mult = raw_tm if raw_tm > 1.001 else (k_snr ** 2)
                if tr:
                    lines.append(
                        f"Mesafe Telafisi (Level 3 Distance Compensation) AKTİF:\n"
                        f"  Uygulanan SFD ({sfd_app:.1f} mm) < SFD_min ({sfd_min:.1f} mm).\n"
                        f"  Dedektör çözünürlük kaybı telafisi: SNR_N hedefi ×{k_snr:.2f} ((SFD_min/SFD)), "
                        f"Pozlama süresi ×{t_mult:.2f} ((SFD_min/SFD)²) artırılmıştır."
                    )
                else:
                    lines.append(
                        f"Distance Compensation (Level 3 Distance Compensation) ACTIVE:\n"
                        f"  Applied SFD ({sfd_app:.1f} mm) < SFD_min ({sfd_min:.1f} mm).\n"
                        f"  Resolution loss compensation: Target SNR_N ×{k_snr:.2f} ((SFD_min/SFD)), "
                        f"Exposure time ×{t_mult:.2f} ((SFD_min/SFD)²) increased."
                    )
            else:
                if tr:
                    lines.append(
                        f"DURUM: Uygulanan SFD ({sfd_app:.1f} mm) < SFD_min ({sfd_min:.1f} mm).\n"
                        f"  Standart geometrik şartı karşılanmıyor! Seviye 3 yetkisiyle Mesafe Telafisi (Distance Compensation) açılabilir."
                    )
                else:
                    lines.append(
                        f"STATUS: Applied SFD ({sfd_app:.1f} mm) < SFD_min ({sfd_min:.1f} mm).\n"
                        f"  Standard geometric requirement not met! Distance Compensation can be enabled with Level 3 approval."
                    )
        else:
            if tr:
                lines.append(f"DURUM: Uygulanan SFD ({sfd_app:.1f} mm) ≥ SFD_min ({sfd_min:.1f} mm) (Geometrik mesafe şartı sağlanıyor).")
            else:
                lines.append(f"STATUS: Applied SFD ({sfd_app:.1f} mm) >= SFD_min ({sfd_min:.1f} mm) (Geometric distance requirement is met).")

    return "\n".join(lines)


def format_f_min_provenance(prov, trans):
    """Localized step-by-step formula, variables, exceptions and reductions for f_min."""
    if not prov:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    standard = prov.get("standard", "iso")
    d = prov.get("d", 2.0)
    b = prov.get("b", 0.0)
    t = prov.get("t", 0.0)
    testing_class = prov.get("testing_class", "class_b")
    f_base = prov.get("base", 0.0)
    f_final = prov.get("value", 0.0)
    f_iso = prov.get("f_min_iso", f_base)
    f_asme = prov.get("f_min_asme", f_base)
    f_iso_base = prov.get("f_min_iso_base", f_iso)
    f_asme_base = prov.get("f_min_asme_base", f_asme)
    b_rule = prov.get("b_rule_applied", False)
    f_star = prov.get("f_min_star")
    ci = prov.get("ci_factor")
    formula_key = prov.get("formula_key", "")
    formula_lbl = trans.get(formula_key) if hasattr(trans, "get") and formula_key else formula_key
    ug_limit = prov.get("ug_limit_asme") or (0.51 if t <= 50.8 else (0.76 if t <= 76.2 else (1.02 if t <= 101.6 else 1.78)))

    lines = []
    base_label = f"Temel f_min = {f_base:.1f} mm [{formula_lbl}]" if tr else f"Base f_min = {f_base:.1f} mm [{formula_lbl}]"
    lines.append(base_label)

    # Dynamic summary of both calculated values
    if tr:
        lines.append(f"Dinamik Hesaplanan Değerler: ISO = {f_iso:.1f} mm | ASME = {f_asme:.1f} mm")
    else:
        lines.append(f"Dynamically Calculated Values: ISO = {f_iso:.1f} mm | ASME = {f_asme:.1f} mm")

    # 1. ISO 17636 Breakdown
    c_val = 7.5 if testing_class == "class_a" else 15.0
    cls_lbl = ("Sınıf A" if testing_class == "class_a" else "Sınıf B") if tr else ("Class A" if testing_class == "class_a" else "Class B")
    std_num = "2" if prov.get("is_digital") else "1"

    if f_star is not None and ci is not None:
        if tr:
            lines.append(f"1) Formül: ISO 17636-2 Formül (13) Planar Dedektör [f_min* = f_min(b=t) · Ci]")
            lines.append(f"   • Değişkenler: C = {c_val:.1f} ({cls_lbl}), d = {d:.1f} mm, b = {b:.1f} mm, t = {t:.1f} mm (b/t > 1.2), Ci = {ci:.3f}")
            lines.append(f"   • Hesaplama: [{c_val:.1f} × {d:.1f} × ({t:.1f})^(2/3)] × {ci:.3f} = {f_iso_base:.1f} mm")
        else:
            lines.append(f"1) Formula: ISO 17636-2 Formula (13) Planar Detector [f_min* = f_min(b=t) · Ci]")
            lines.append(f"   • Variables: C = {c_val:.1f} ({cls_lbl}), d = {d:.1f} mm, b = {b:.1f} mm, t = {t:.1f} mm (b/t > 1.2), Ci = {ci:.3f}")
            lines.append(f"   • Calculation: [{c_val:.1f} × {d:.1f} × ({t:.1f})^(2/3)] × {ci:.3f} = {f_iso_base:.1f} mm")
    else:
        b_note = (" (b < 1.2t kuralı: b = t)" if b_rule else "") if tr else (" (b < 1.2t rule: b = t)" if b_rule else "")
        if tr:
            lines.append(f"1) Formül: ISO 17636-{std_num} Formül (2) [f_min = C · d · b^(2/3)]")
            lines.append(f"   • Değişkenler: C = {c_val:.1f} ({cls_lbl}), d = {d:.1f} mm, b = {b:.1f} mm{b_note}")
            lines.append(f"   • Hesaplama: {c_val:.1f} × {d:.1f} × ({b:.1f})^(2/3) = {f_iso_base:.1f} mm")
        else:
            lines.append(f"1) Formula: ISO 17636-{std_num} Formula (2) [f_min = C · d · b^(2/3)]")
            lines.append(f"   • Variables: C = {c_val:.1f} ({cls_lbl}), d = {d:.1f} mm, b = {b:.1f} mm{b_note}")
            lines.append(f"   • Calculation: {c_val:.1f} × {d:.1f} × ({b:.1f})^(2/3) = {f_iso_base:.1f} mm")

    # 2. ASME Sec V Breakdown
    if tr:
        lines.append(f"2) Formül: ASME Sec V Art 2 T-274.2 [f_min = d · b / Ug_limit]")
        lines.append(f"   • Değişkenler: d = {d:.1f} mm, b = {b:.1f} mm, Ug_limit = {ug_limit:.2f} mm (t = {t:.1f} mm)")
        lines.append(f"   • Hesaplama: {d:.1f} × {b:.1f} / {ug_limit:.2f} = {f_asme_base:.1f} mm")
    else:
        lines.append(f"2) Formula: ASME Sec V Art 2 T-274.2 [f_min = d · b / Ug_limit]")
        lines.append(f"   • Variables: d = {d:.1f} mm, b = {b:.1f} mm, Ug_limit = {ug_limit:.2f} mm (t = {t:.1f} mm)")
        lines.append(f"   • Calculation: {d:.1f} × {b:.1f} / {ug_limit:.2f} = {f_asme_base:.1f} mm")

    # Exceptions & Reductions
    reductions = []
    if prov.get("l3_dw"):
        reductions.append("Level 3 Çift Duvar İndirimi (%20: ×0.80)" if tr else "Level 3 Double-Wall Reduction (20%: ×0.80)")
    if prov.get("l3_central"):
        reductions.append("Level 3 Merkezi Projeksiyon İndirimi (%50: ×0.50)" if tr else "Level 3 Central Projection Reduction (50%: ×0.50)")
    if reductions:
        lines.append(("Uygulanan İstisnalar: " if tr else "Applied Exceptions: ") + " + ".join(reductions))

    # Annex F detector unsharpness compensation
    if prov.get("annex_f_compensated"):
        af_req = prov.get("annex_f_req", 0.0)
        srb_val = prov.get("annex_f_srb", 0.0)
        if tr:
            lines.append(f"Annex F Telafisi: Dedektör bulanıklığı (SRb = {srb_val:.0f} µm) nedeniyle f_min {af_req:.1f} mm değerine yükseltildi.")
        else:
            lines.append(f"Annex F Compensation: f_min increased to {af_req:.1f} mm to compensate detector unsharpness (SRb = {srb_val:.0f} µm).")

    std_lbl = "ASME Sec V" if standard == "asme" else f"ISO 17636-{std_num}"
    lines.append(f"Sonuç: Seçili Standart ({std_lbl}) uyarınca Geçerli f_min = {f_final:.1f} mm" if tr else f"Result: Governing f_min per selected standard ({std_lbl}) = {f_final:.1f} mm")
    return "\n".join(lines)


def format_single_wire_iqi_provenance(values, trans):
    """Localized breakdown of single wire IQI table, reference thickness, and Clause 6.9 exception."""
    if not values:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    standard = values.get("standard", "iso")
    tech = values.get("tech", "digital")
    geometry = values.get("geometry", "dwsi")
    testing_class = values.get("testing_class", "class_b")
    film_side = values.get("film_side", False)
    material = values.get("material", "steel")
    source = values.get("source", "x_ray")
    t = values.get("t", 0.0)
    w_nom = values.get("w_nom", t)
    wire_no = values.get("wire_no")
    wire_str = values.get("wire_str", "")
    iqi_type = values.get("iqi_type", "wire")

    if standard == "asme":
        asme_str = values.get("asme_iqi_str", "")
        return (
            f"Standart: ASME Sec V Art 2 / ASTM E747 | Belirlenen IQI: {asme_str}"
            if tr else
            f"Standard: ASME Sec V Art 2 / ASTM E747 | Determined IQI: {asme_str}"
        )

    lines = []
    std_part = "1" if tech == "analog" else "2"
    if film_side:
        tbl = "Tablo B.10" if (iqi_type == "step_hole" and testing_class == "class_a") else (
            "Tablo B.12" if iqi_type == "step_hole" else (
                "Tablo B.9" if testing_class == "class_a" else "Tablo B.11"
            )
        )
    else:
        if geometry in ["dwdi_elliptic", "dwdi_super"]:
            tbl = "Tablo B.6" if (iqi_type == "step_hole" and testing_class == "class_a") else (
                "Tablo B.8" if iqi_type == "step_hole" else (
                    "Tablo B.5" if testing_class == "class_a" else "Tablo B.7"
                )
            )
        else:
            tbl = "Tablo B.2" if (iqi_type == "step_hole" and testing_class == "class_a") else (
                "Tablo B.4" if iqi_type == "step_hole" else (
                    "Tablo B.1" if testing_class == "class_a" else "Tablo B.3"
                )
            )
    tbl_en = tbl.replace("Tablo", "Table")

    loc_tr = "Dedektör/Film Tarafı" if film_side else "Kaynak Tarafı"
    loc_en = "Detector/Film Side" if film_side else "Source Side"
    t_rule_tr = "w = 2·t (çift cidar, kaynak dikiş yüksekliği kep/kök hariç)" if geometry in ("dwsi", "dwdi_elliptic", "dwdi_super") else "w = t (tek cidar, kaynak dikiş yüksekliği kep/kök hariç)"
    t_rule_en = "w = 2·t (double wall, weld reinforcement excluded)" if geometry in ("dwsi", "dwdi_elliptic", "dwdi_super") else "w = t (single wall, weld reinforcement excluded)"

    if tr:
        lines.append(f"Standart: ISO 17636-{std_part} {tbl} ({'Sınıf A' if testing_class == 'class_a' else 'Sınıf B'}, {loc_tr})")
        lines.append(f"Referans Kalınlık: {t_rule_tr} = {w_nom:.2f} mm")
        lines.append(f"Tablo Gereksinimi: {wire_str}")
    else:
        lines.append(f"Standard: ISO 17636-{std_part} {tbl_en} ({'Class A' if testing_class == 'class_a' else 'Class B'}, {loc_en})")
        lines.append(f"Reference Thickness: {t_rule_en} = {w_nom:.2f} mm")
        lines.append(f"Table Requirement: {wire_str}")

    # Clause 6.9 Isotope Exception
    allowed_offset = 0
    w_pen = 2 * t if geometry in ("dwsi", "dwdi_elliptic", "dwdi_super") else t
    if material in ("steel", "copper_nickel"):
        if geometry in ("dwdi_elliptic", "dwdi_super"):
            if source == "isotope_ir192" and 10.0 < w_pen <= 25.0:
                allowed_offset = 1
            elif source == "isotope_se75" and w_pen <= 12.0:
                allowed_offset = 1
        else:
            if testing_class == "class_a":
                if source == "isotope_ir192":
                    if 10.0 < w_pen <= 24.0:
                        allowed_offset = 2
                    elif 24.0 < w_pen <= 30.0:
                        allowed_offset = 1
                elif source == "isotope_se75" and w_pen <= 24.0:
                    allowed_offset = 1
            else:
                if source == "isotope_ir192" and 10.0 < w_pen <= 40.0:
                    allowed_offset = 1
                elif source == "isotope_se75" and w_pen <= 20.0:
                    allowed_offset = 1

    if allowed_offset > 0 and wire_no is not None:
        src_lbl = "Ir-192" if source == "isotope_ir192" else "Se-75"
        adj_wire = wire_no - allowed_offset if iqi_type == "wire" else wire_no + allowed_offset
        prefix = "W" if iqi_type == "wire" else "H"
        if tr:
            lines.append(
                f"Madde 6.9 İzotop İstisnası: {src_lbl} kaynağı ve {material} için Madde 6.9 "
                f"uyarınca şartname/anlaşma ile {allowed_offset} basamak daha kalın tel "
                f"({prefix} {adj_wire}) kabul edilebilir."
            )
        else:
            lines.append(
                f"Clause 6.9 Isotope Exception: For {src_lbl} source and {material}, "
                f"Clause 6.9 allows {allowed_offset} step(s) coarser IQI value "
                f"({prefix} {adj_wire}) subject to contractual agreement."
            )

    return "\n".join(lines)


def format_duplex_iqi_provenance(values, trans):
    """Localized breakdown of duplex wire IQI and panoramic tolerance."""
    if not values:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    tech = values.get("tech", "digital")
    if tech != "digital":
        return trans.get("na", "N/A") if hasattr(trans, "get") else "N/A"

    duplex_str = values.get("duplex_str", "")
    duplex_no = values.get("duplex_no")
    w_nom = values.get("w_nom", 0.0)
    geometry = values.get("geometry", "dwsi")
    std_figure = values.get("std_figure")
    testing_class = values.get("testing_class", "class_b")

    lines = []
    tbl = "Tablo B.13 (Sınıf A)" if testing_class == "class_a" else "Tablo B.14 (Sınıf B)"
    if not tr:
        tbl = tbl.replace("Tablo", "Table").replace("Sınıf", "Class")

    if tr:
        lines.append(f"Standart: ISO 17636-2 {tbl} | Penetrasyon Kalınlığı: w_nom = {w_nom:.2f} mm")
        lines.append(f"Gereken İkili Tel: {duplex_str}")
    else:
        lines.append(f"Standard: ISO 17636-2 {tbl} | Penetrated Thickness: w_nom = {w_nom:.2f} mm")
        lines.append(f"Required Duplex Wire: {duplex_str}")

    if geometry == "swsi" and std_figure in ("fig5", "fig5a", "fig5b"):
        adj_d = max(1, duplex_no - 1) if duplex_no else None
        if tr:
            lines.append(
                f"Madde 6.9 / 7.6 İstisnası: SWSI panoramik (merkezi izdüşüm - Şekil 5) çekimde "
                f"1 duplex adım toleransı (D {adj_d}) kabul edilebilir."
            )
        else:
            lines.append(
                f"Clause 6.9 / 7.6 Exception: In SWSI panoramic (central projection - Figure 5), "
                f"1 duplex wire step tolerance (D {adj_d}) is permitted."
            )

    return "\n".join(lines)


def format_quality_target_provenance(values, trans):
    """Localized breakdown of optical density / SNR_N target, Se-75 rule and distance compensation."""
    if not values:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    tech = values.get("tech", "digital")
    testing_class = values.get("testing_class", "class_b")
    material = values.get("material", "steel")
    source = values.get("source", "x_ray")
    w_nom = values.get("w_nom", 0.0)
    cap = values.get("cap", 0.0)
    sfd = values.get("sfd", 600.0)
    sfd_min = values.get("sfd_min", 600.0)
    sfd_comp_target = values.get("sfd_comp_target")
    snr_location = values.get("snr_location", "weld")
    target_quality = values.get("target_quality", "")

    lines = []
    if tech == "analog":
        req_d = values.get("required_density", 2.3 if testing_class == "class_b" else 2.0)
        se75_thin = (material in ("steel", "copper_nickel") and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b")
        if tr:
            lines.append("Standart: ISO 17636-1 Madde 7.8 & Tablo 5 (Optik Yoğunluk Sınırları)")
            lines.append(f"Hedef Yoğunluk: D ≥ {req_d:.1f} (İzin verilen maksimum: 4.0)")
            if se75_thin:
                lines.append(
                    "Madde 6.9 İstisnası: Se-75 kaynağı ve w < 12 mm Sınıf B için asgari "
                    "optik yoğunluk D ≥ 3.0'a yükseltilmiştir (standart Sınıf B tabanı: 2.3)."
                )
        else:
            lines.append("Standard: ISO 17636-1 Clause 7.8 & Table 5 (Optical Density Limits)")
            lines.append(f"Target Density: D >= {req_d:.1f} (Maximum permitted: 4.0)")
            if se75_thin:
                lines.append(
                    "Clause 6.9 Exception: For Se-75 source with w < 12 mm Class B, minimum "
                    "optical density is raised to D >= 3.0 (standard Class B baseline: 2.3)."
                )
    else:
        table_name = values.get("table_name", "Tablo 3/4")
        se75_thin = (material in ("steel", "copper_nickel") and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b")
        adj_loc = (snr_location == "adjacent" and cap > 0.0)

        if tr:
            lines.append(f"Standart: ISO 17636-2 Madde 7.3.1 [{table_name}] (Normalize SNR_N)")
            lines.append(f"Geçerli SNR_N Hedefi: {target_quality}")
            if se75_thin:
                lines.append(
                    "Madde 6.9 İstisnası: Se-75 kaynağı ve w < 12 mm Sınıf B için hedef "
                    "SNR_N değeri 1.4× artırılmıştır."
                )
            if adj_loc:
                lines.append(
                    "Madde 7.3.1 Kuralı: SNR_N ana malzemede (kaynak dikişi bitişiğinde) "
                    "ölçüldüğünden hedef SNR_N 1.4× artırılmıştır."
                )
            if sfd_comp_target is not None and sfd < sfd_min:
                k_val = sfd_min / max(10.0, sfd)
                lines.append(
                    f"Seviye 3 Mesafe Telafisi (Distance Compensation): SFD ({sfd:.1f} mm) < "
                    f"SFD_min ({sfd_min:.1f} mm) nedeniyle SNR_N hedefi ×{k_val:.2f} ((SFD_min/SFD)) "
                    f"artırılarak {sfd_comp_target:.1f} değerine telafi edilmiştir."
                )
        else:
            lines.append(f"Standard: ISO 17636-2 Clause 7.3.1 [{table_name}] (Normalized SNR_N)")
            lines.append(f"Current SNR_N Target: {target_quality}")
            if se75_thin:
                lines.append(
                    "Clause 6.9 Exception: For Se-75 source with w < 12 mm Class B, target "
                    "SNR_N is increased by 1.4x."
                )
            if adj_loc:
                lines.append(
                    "Clause 7.3.1 Rule: Target SNR_N is multiplied by 1.4x because SNR_N is "
                    "measured in the parent metal adjacent to the weld."
                )
            if sfd_comp_target is not None and sfd < sfd_min:
                k_val = sfd_min / max(10.0, sfd)
                lines.append(
                    f"Level 3 Distance Compensation: Because SFD ({sfd:.1f} mm) < "
                    f"SFD_min ({sfd_min:.1f} mm), SNR_N target is compensated ×{k_val:.2f} ((SFD_min/SFD)) "
                    f"to {sfd_comp_target:.1f}."
                )

    return "\n".join(lines)


def format_detector_quality_provenance(values, trans):
    """Localized breakdown of film class / max SRb and Annex F compensation status."""
    if not values:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    tech = values.get("tech", "digital")
    testing_class = values.get("testing_class", "class_b")
    material = values.get("material", "steel")
    source = values.get("source", "x_ray")
    w_nom = values.get("w_nom", 0.0)

    lines = []
    if tech == "analog":
        req_film = values.get("film_class_req", "C5")
        se75_thin = (material in ("steel", "copper_nickel") and source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b")
        if tr:
            lines.append("Standart: ISO 17636-1:2022 Madde 7.3 & Tablo 3/4 (ISO 11699-1 Film Sistemi Sınıfı)")
            lines.append(f"Asgari Gereken Film Sınıfı: {req_film}")
            if se75_thin:
                lines.append(
                    "Madde 6.9 İstisnası: Se-75 kaynağı ve w < 12 mm Sınıf B için bir üst film "
                    "sistemi sınıfı zorunludur (C4 yerine C3 olarak belirlendi)."
                )
        else:
            lines.append("Standard: ISO 17636-1:2022 Clause 7.3 & Table 3/4 (ISO 11699-1 Film System Class)")
            lines.append(f"Minimum Required Film Class: {req_film}")
            if se75_thin:
                lines.append(
                    "Clause 6.9 Exception: For Se-75 source with w < 12 mm Class B, a film system "
                    "class one grade better is mandatory (upgraded from C4 to C3)."
                )
    else:
        max_srb = values.get("max_srb", 100.0)
        ug_val = values.get("ug", 0.0)
        tbl = "Tablo B.13 (Sınıf A)" if testing_class == "class_a" else "Tablo B.14 (Sınıf B)"
        if not tr:
            tbl = tbl.replace("Tablo", "Table").replace("Sınıf", "Class")

        ratio = (ug_val * 1000.0) / max(1.0, float(max_srb)) if max_srb else 1.0
        if tr:
            lines.append(f"Standart: ISO 17636-2:2022 {tbl} (Temel Uzaysal Çözünürlük)")
            lines.append(f"Asgari Çözünürlük: Azami SRb = {max_srb:.0f} µm (u_d = 2·SRb = {2*float(max_srb):.0f} µm)")
            if ratio <= 2.0:
                lines.append(f"Annex F Kontrolü: Ug / SRb = {ratio:.2f} ≤ 2.0 (Dedektör ve geometrik bulanıklık dengeli)")
            else:
                lines.append(f"Annex F Telafisi: Ug / SRb = {ratio:.2f} > 2.0 (Dedektör bulanıklığını telafi etmek için f_min artırılması önerilir)")
        else:
            lines.append(f"Standard: ISO 17636-2:2022 {tbl} (Basic Spatial Resolution)")
            lines.append(f"Minimum Resolution: Maximum SRb = {max_srb:.0f} µm (u_d = 2·SRb = {2*float(max_srb):.0f} µm)")
            if ratio <= 2.0:
                lines.append(f"Annex F Check: Ug / SRb = {ratio:.2f} <= 2.0 (Detector and geometric unsharpness balanced)")
            else:
                lines.append(f"Annex F Compensation: Ug / SRb = {ratio:.2f} > 2.0 (Increasing f_min recommended to compensate detector unsharpness)")

    return "\n".join(lines)


def format_u_max_provenance(values, trans):
    """Localized breakdown of maximum tube voltage and Level 3 override note."""
    if not values:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    source = values.get("source", "x_ray")
    if source != "x_ray":
        return trans.get("na", "N/A") if hasattr(trans, "get") else "N/A"

    u_max = values.get("u_max")
    input_kv = values.get("input_kv")
    material = values.get("material", "steel")
    w_nom = values.get("w_nom", 0.0)
    lvl3 = values.get("lvl3") or {}
    voltage_override = lvl3.get("voltage_override", False)

    lines = []
    if tr:
        lines.append(f"Standart: ISO 17636-1:2022 Şekil 1 / Çizelge 1 & Ek C ({material}, w_nom={w_nom:.1f} mm)")
        if u_max is not None:
            lines.append(f"Azami İzin Verilen Gerilim: U_max = {u_max:.0f} kV")
        if input_kv is not None and u_max is not None:
            if input_kv > u_max:
                if voltage_override:
                    lines.append(f"Seviye 3 Onayı (Voltage Override): Uygulanan {input_kv:.0f} kV > {u_max:.0f} kV (Seviye 3 onayı ile izin verildi).")
                else:
                    lines.append(f"DURUM: Uygulanan voltaj ({input_kv:.0f} kV) U_max sınırını ({u_max:.0f} kV) aşıyor!")
            else:
                lines.append(f"DURUM: Uygulanan voltaj ({input_kv:.0f} kV) ≤ U_max ({u_max:.0f} kV) (Standart sınırı içinde).")
    else:
        lines.append(f"Standard: ISO 17636-1:2022 Figure 1 / Table 1 & Annex C ({material}, w_nom={w_nom:.1f} mm)")
        if u_max is not None:
            lines.append(f"Maximum Allowed Voltage: U_max = {u_max:.0f} kV")
        if input_kv is not None and u_max is not None:
            if input_kv > u_max:
                if voltage_override:
                    lines.append(f"Level 3 Approval (Voltage Override): Applied {input_kv:.0f} kV > {u_max:.0f} kV (Approved by Level 3 authority).")
                else:
                    lines.append(f"STATUS: Applied voltage ({input_kv:.0f} kV) exceeds U_max limit ({u_max:.0f} kV)!")
            else:
                lines.append(f"STATUS: Applied voltage ({input_kv:.0f} kV) <= U_max ({u_max:.0f} kV) (Within standard limit).")

    return "\n".join(lines)


def format_ug_provenance(values, trans):
    """Localized breakdown of geometric unsharpness formula, limit, and Annex F ratio."""
    if not values:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    d = values.get("d", 2.0)
    b = values.get("b_dist", 0.0)
    sfd = values.get("sfd", 600.0)
    ug = values.get("ug", 0.0)
    ug_limit = values.get("ug_limit")
    ug_ok = values.get("ug_ok")
    standard = values.get("standard", "iso")
    f_source = max(1.0, sfd - b)

    lines = []
    if tr:
        lines.append(f"Formül: Ug = d · b / f = d · b / (SFD − b)")
        lines.append(f"Değişkenler: d = {d:.1f} mm, b = {b:.1f} mm, f = {f_source:.1f} mm (SFD = {sfd:.0f} mm)")
        lines.append(f"Hesaplanan Değer: Ug = {d:.1f} × {b:.1f} / {f_source:.1f} = {ug:.3f} mm")
        if ug_limit is not None:
            std_name = "ASME Sec V Art 2 T-274.2" if standard == "asme" else "ISO 17636"
            lines.append(f"Limit ({std_name}): Ug,azami = {ug_limit:.2f} mm")
            status_txt = "UYGUN (Ug <= Ug,azami)" if ug_ok else "UYGUN DEĞİL (Ug > Ug,azami)"
            lines.append(f"Değerlendirme: {status_txt}")
    else:
        lines.append(f"Formula: Ug = d · b / f = d · b / (SFD - b)")
        lines.append(f"Variables: d = {d:.1f} mm, b = {b:.1f} mm, f = {f_source:.1f} mm (SFD = {sfd:.0f} mm)")
        lines.append(f"Calculated Value: Ug = {d:.1f} × {b:.1f} / {f_source:.1f} = {ug:.3f} mm")
        if ug_limit is not None:
            std_name = "ASME Sec V Art 2 T-274.2" if standard == "asme" else "ISO 17636"
            lines.append(f"Limit ({std_name}): Ug,max = {ug_limit:.2f} mm")
            status_txt = "COMPLIANT (Ug <= Ug,max)" if ug_ok else "NON-COMPLIANT (Ug > Ug,max)"
            lines.append(f"Evaluation: {status_txt}")

    return "\n".join(lines)



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
        if prov.get("film_coverage_n"):
            n_film = prov.get("film_coverage_n")
            if prov.get("governing_factor") == "film_size":
                film_ov = prov.get("film_overlap_mm")
                ov_str_tr = f", bindirme: {film_ov:.0f} mm" if film_ov is not None else ""
                ov_str_en = f", overlap: {film_ov:.0f} mm" if film_ov is not None else ""
                if getattr(trans, "language", "tr") == "tr":
                    text += f" | Kaset Kapsaması: {n_film} poz (Kısıtlayan: Film Boyutu{ov_str_tr})"
                else:
                    text += f" | Film Coverage: {n_film} exp (Governing: Film Length{ov_str_en})"
        return text
    if method == "panoramic":
        return trans.get("exp_prov_panoramic")
    if method == "dwdi_rule":
        text = trans.get("exp_prov_dwdi", prov.get("ratio"), prov.get("n"))
        dwdi_cov = prov.get("dwdi_coverage")
        if dwdi_cov and dwdi_cov.get("available_across", 0.0) > 0.0:
            w_req = dwdi_cov.get("w_min_req", 0.0)
            avail = dwdi_cov.get("available_across", 0.0)
            is_suff = dwdi_cov.get("is_sufficient", True)
            if getattr(trans, "language", "tr") == "tr":
                tag = "Kurtarıyor ✓" if is_suff else f"Kurtarmıyor ⚠ (Min. {w_req:.1f} mm)"
                text += f" | Kapsama: Min. {w_req:.1f} mm / Girilen: {avail:.0f} mm ({tag})"
            else:
                tag = "Sufficient ✓" if is_suff else f"Insufficient ⚠ (Min. {w_req:.1f} mm)"
                text += f" | Coverage: Min {w_req:.1f} mm / Entered: {avail:.0f} mm ({tag})"
        return text
    if method == "out_of_chart":
        return trans.get("exp_prov_out_of_chart", prov.get("n"))
    return trans.get("exp_prov_fallback", prov.get("n"))


def format_dwdi_coverage_detail(cov, trans, od, t, sfd, geometry):
    """Localized step-by-step arithmetic and coverage breakdown for DWDI exposures."""
    if not cov:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    is_super = (geometry == "dwdi_super")
    tech_name = ("DWDI Çakışık (Şekil 12)" if is_super else "DWDI Eliptik (Şekil 11)") if tr else (
        "DWDI Superimposed (Figure 12)" if is_super else "DWDI Elliptical (Figure 11)"
    )

    ratio = (t / od) if od > 0 else 0.0
    n_exp = 3 if is_super else (3 if ratio >= 0.12 else 2)
    m = cov.get("magnification", 1.0)
    w_proj = cov.get("w_proj", 0.0)
    w_min = cov.get("w_min_req", 0.0)
    h_proj = cov.get("h_proj", 0.0)
    f_dist = cov.get("f_dist", 0.0)
    b_dist = cov.get("b_dist", 0.0)
    rw = cov.get("available_w", 0.0)
    rh = cov.get("available_h", 0.0)
    avail = cov.get("available_across", 0.0)
    margin = cov.get("margin_mm", 10.0)
    is_suff = cov.get("is_sufficient", True)

    lines = []
    if tr:
        lines.append("DWDI POZ SAYISI VE FİLM / PANEL BOYUT KAPSAMA DÖKÜMÜ:")
        lines.append("=" * 60)
        lines.append("1. Normatif Çekim Geometrisi ve Poz Sayısı (ISO 17636-1/2 Madde 7.1.6/7.1.7):")
        lines.append(f"   • Düzenek: {tech_name}")
        lines.append(f"   • Boru Dış Çapı (OD): {od:.1f} mm, Et Kalınlığı (t): {t:.1f} mm")
        lines.append(f"   • t / De Oranı: {ratio:.4f} (Eşik: 0.12)")
        if is_super:
            lines.append("   • Çakışık teknikte dikişin tamamını kapsamak için 3 poz (60° veya 120° arayla) gereklidir.")
        elif ratio >= 0.12:
            lines.append("   • t/De >= 0.12 olduğundan eliptik teknikte 3 poz (60° veya 120° arayla) gereklidir.")
        else:
            lines.append("   • t/De < 0.12 olduğundan eliptik teknikte 2 poz (90° arayla) yeterlidir.")
        lines.append(f"   • GEREKEN ASGARİ POZ SAYISI: {n_exp} poz")
        lines.append("")
        lines.append("2. Projeksiyon Büyütmesi ve İzdüşüm Hesabı:")
        lines.append(f"   • Uygulanan Odak Mesafesi (SFD): {sfd:.1f} mm")
        lines.append(f"   • Nesne-Dedektör Mesafesi (b = OD + bgap): {b_dist:.1f} mm")
        lines.append(f"   • Odak-Nesne Mesafesi (f = SFD - b): {f_dist:.1f} mm")
        lines.append(f"   • Geometrik Büyütme (M = SFD / f): ×{m:.3f}")
        lines.append(f"   • Büyütülmüş Boru Çapı (W_proj = OD × M): {w_proj:.1f} mm")
        lines.append(f"   • Standart IQI ve İşaretçi Kenar Marjı: +{margin:.1f} mm")
        lines.append(f"   ★ GEREKLİ ASGARİ FİLM/PANEL GENİŞLİĞİ: {w_min:.1f} mm")
        if h_proj > 0:
            lines.append(f"   • Projeksiyon Boyuna Açılma (WAE / Elips): {h_proj:.1f} mm")
        lines.append("")
        lines.append("3. Boyut Yeterlilik (Kurtarma) Durumu:")
        lines.append(f"   • Girilen Film/Panel Boyutu: {rw:.0f} × {rh:.0f} mm (Kullanılabilir: {avail:.0f} mm)")
        if avail <= 0.0:
            lines.append("   ℹ Bilgi: Özel film/panel boyutu girilmedi; kontrol için boyut giriniz.")
        elif is_suff:
            lines.append(f"   ✓ DURUM: KURTARIYOR! Girilen boyut ({avail:.0f} mm) >= Gerekli min. ({w_min:.1f} mm).")
            lines.append(f"     Boru ve kaynak görüntüsü kesilmeden {n_exp} poz ile tüm dikiş tamamlanabilir.")
        else:
            lines.append(f"   ✗ DURUM: KURTARMIYOR! Girilen boyut ({avail:.0f} mm) < Gerekli min. ({w_min:.1f} mm).")
            lines.append("     Boru görüntüsü film/panel sınırlarından taşacak ve kenarlardan kesilecektir!")
            lines.append(f"     Çözüm: En az {w_min:.1f} mm genişliğinde film/panel kullanınız.")
    else:
        lines.append("DWDI EXPOSURE COUNT & FILM / PANEL COVERAGE BREAKDOWN:")
        lines.append("=" * 60)
        lines.append("1. Normative Technique & Exposures (ISO 17636-1/2 Clauses 7.1.6/7.1.7):")
        lines.append(f"   • Arrangement: {tech_name}")
        lines.append(f"   • Pipe OD: {od:.1f} mm, Wall Thickness (t): {t:.1f} mm")
        lines.append(f"   • t / De Ratio: {ratio:.4f} (Threshold: 0.12)")
        if is_super:
            lines.append("   • Superimposed technique requires 3 exposures (at 60°/120°) to cover the circumference.")
        elif ratio >= 0.12:
            lines.append("   • t/De >= 0.12 requires 3 elliptical exposures (at 60°/120°).")
        else:
            lines.append("   • t/De < 0.12 requires 2 elliptical exposures (at 90° offset).")
        lines.append(f"   • REQUIRED MINIMUM EXPOSURES: {n_exp} exposures")
        lines.append("")
        lines.append("2. Projection Magnification & Shadow Sizing:")
        lines.append(f"   • Applied Distance (SFD): {sfd:.1f} mm")
        lines.append(f"   • Object-to-Detector Distance (b = OD + bgap): {b_dist:.1f} mm")
        lines.append(f"   • Source-to-Object Distance (f = SFD - b): {f_dist:.1f} mm")
        lines.append(f"   • Geometric Magnification (M = SFD / f): x{m:.3f}")
        lines.append(f"   • Projected Pipe Diameter (W_proj = OD x M): {w_proj:.1f} mm")
        lines.append(f"   • IQI & Marker Edge Margin: +{margin:.1f} mm")
        lines.append(f"   * REQUIRED MINIMUM FILM/PANEL WIDTH: {w_min:.1f} mm")
        if h_proj > 0:
            lines.append(f"   • Longitudinal Projection (WAE / Ellipse): {h_proj:.1f} mm")
        lines.append("")
        lines.append("3. Size Coverage Sufficiency Status:")
        lines.append(f"   • Entered Film/Panel Size: {rw:.0f} x {rh:.0f} mm (Available: {avail:.0f} mm)")
        if avail <= 0.0:
            lines.append("   ℹ Note: Custom film/panel dimensions not entered.")
        elif is_suff:
            lines.append(f"   ✓ STATUS: SUFFICIENT! Entered size ({avail:.0f} mm) >= Required min ({w_min:.1f} mm).")
            lines.append(f"     Full weld circumference can be completed in {n_exp} exposures without cutoff.")
        else:
            lines.append(f"   ✗ STATUS: INSUFFICIENT! Entered size ({avail:.0f} mm) < Required min ({w_min:.1f} mm).")
            lines.append("     Pipe image will be clipped off the detector/film edge!")
            lines.append(f"     Remedy: Use a detector/film with at least {w_min:.1f} mm width.")

    return "\n".join(lines)



def format_exposure_time_provenance(prov, trans):
    """Localized step-by-step formula and parameter breakdown for exposure time."""
    if not prov:
        return ""
    lang = getattr(trans, "language", "tr") if not isinstance(trans, dict) else trans.get("language", "tr")
    tr = (lang == "tr")

    method = prov.get("method", "model")
    tech = prov.get("tech", "digital")
    source = prov.get("source", "x_ray")
    material = prov.get("material", "steel")
    mat_label = trans.get(material) if hasattr(trans, "get") else material
    ref_factor = prov.get("ref_factor", 1.0) or 1.0
    w_eff = prov.get("w_eff", 0.0) or 0.0
    w_eq = prov.get("w_eq_steel", w_eff) or w_eff
    sfd = prov.get("sfd", 600.0) or 600.0
    output_val = prov.get("output_val", 1.0) or 1.0
    dist_lbl = "SDD" if tech == "digital" else "SFD"
    out_unit = "mA" if source == "x_ray" else "Ci"

    parts = []

    if method == "rfactor":
        film_key = prov.get("film_key", "AA400")
        film_brand = prov.get("film_brand", "Carestream")
        chart_film_class = prov.get("chart_film_class", "")
        cls_tag = f", {chart_film_class}" if chart_film_class else ""
        r_raw = prov.get("r_factor_raw", 0.46)
        r_eff = prov.get("r_factor_eff", r_raw)
        hvl = prov.get("hvl", 13.2)
        gamma = prov.get("gamma", 0.48)
        target_od = prov.get("target_od", 2.0)
        od_factor = prov.get("od_factor", 1.0)
        grad = prov.get("gradient", 2.0) or 2.0
        if tr:
            parts.append(
                f"Yöntem: {film_brand} R-Faktör / SCRATA Cetveli ({film_key}{cls_tag}) | "
                f"Formül: T[dk] = 60 × [R_eff × 10^((D−2)/G̅) × (SFD/1000)² × 2^(w_eq/HVL)] / (A × Γ)"
            )
            ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
            parts.append(
                f"Parametreler: Malzeme={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                f"R_eff={r_eff:.3f} (tablo R={r_raw:.2f}), HVL={hvl:.1f} mm, Γ={gamma:.3f} R·m²/(Ci·h), "
                f"Hedef D={target_od:.1f} (G̅={grad:.1f}, k_OD={od_factor:.2f}×), SFD={sfd:.0f} mm, A={output_val:.1f} Ci"
            )
        else:
            parts.append(
                f"Method: {film_brand} R-Factor / SCRATA Slide Rule ({film_key}{cls_tag}) | "
                f"Formula: T[min] = 60 × [R_eff × 10^((D−2)/G̅) × (SFD/1000)² × 2^(w_eq/HVL)] / (A × Γ)"
            )
            ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
            parts.append(
                f"Parameters: Material={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                f"R_eff={r_eff:.3f} (table R={r_raw:.2f}), HVL={hvl:.1f} mm, Γ={gamma:.3f} R·m²/(Ci·h), "
                f"Target D={target_od:.1f} (G̅={grad:.1f}, k_OD={od_factor:.2f}×), SFD={sfd:.0f} mm, A={output_val:.1f} Ci"
            )
    elif method in ("cr_ips_chart", "dda_panel_chart"):
        det_lbl = prov.get("detector_class_label", prov.get("detector_type", "CR/DDA"))
        r_dig = prov.get("r_factor_digital", 0.18) or 0.18
        hvl = prov.get("hvl", 13.2) or 13.2
        gamma = prov.get("gamma", 0.48) or 0.48
        target_snr = prov.get("target_snr", 100.0) or 100.0
        snr_factor = prov.get("snr_factor", 1.0) or 1.0
        srb_factor = prov.get("srb_factor", 1.0) or 1.0
        srb_ref = prov.get("srb_ref", 100.0) or 100.0
        app_srb = prov.get("app_srb")
        std_tag = "ISO 16371-1 CR IP R-Faktör Tablosu" if method == "cr_ips_chart" else "ASTM E2698 DDA Panel Doz-SNR Tablosu"
        std_tag_en = "ISO 16371-1 CR IP R-Factor Chart" if method == "cr_ips_chart" else "ASTM E2698 DDA Panel Dose-SNR Chart"
        srb_txt = (
            f", k_SRb=({srb_ref:.0f}/{float(app_srb):.0f})²={srb_factor:.2f}×"
            if (app_srb and abs(srb_factor - 1.0) > 1e-3) else ""
        )
        if tr:
            parts.append(
                f"Yöntem: {std_tag} ({det_lbl}) | "
                f"Formül: T[dk] = 60 × [R_dig × (SNR_hedef/70)² × k_SRb × (SDD/1000)² × 2^(w_eq/HVL)] / (A × Γ)"
            )
            ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
            parts.append(
                f"Parametreler: Malzeme={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                f"R_dig={r_dig:.3f} R (@SNR_N=70), HVL={hvl:.1f} mm, Γ={gamma:.3f} R·m²/(Ci·h), "
                f"Hedef SNR_N={target_snr:.0f} (k_SNR={snr_factor:.2f}×{srb_txt}), SDD={sfd:.0f} mm, A={output_val:.1f} Ci"
            )
        else:
            parts.append(
                f"Method: {std_tag_en} ({det_lbl}) | "
                f"Formula: T[min] = 60 × [R_dig × (SNR_target/70)² × k_SRb × (SDD/1000)² × 2^(w_eq/HVL)] / (A × Γ)"
            )
            ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
            parts.append(
                f"Parameters: Material={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                f"R_dig={r_dig:.3f} R (@SNR_N=70), HVL={hvl:.1f} mm, Γ={gamma:.3f} R·m²/(Ci·h), "
                f"Target SNR_N={target_snr:.0f} (k_SNR={snr_factor:.2f}×{srb_txt}), SDD={sfd:.0f} mm, A={output_val:.1f} Ci"
            )
    elif method in ("type_x", "digital_xray_chart"):
        kv = prov.get("kv", 120.0) or 120.0
        exp_chart = prov.get("exposure_mamin_chart", 0.0) or 0.0
        sfd_ref = prov.get("sfd_ref", 700.0) or 700.0
        rec_mod = prov.get("receptor_mod", 1.0) or 1.0
        det_factor = prov.get("det_factor", 1.0) or 1.0
        target_snr = prov.get("target_snr", 100.0) or 100.0
        srb_factor = prov.get("srb_factor", 1.0) or 1.0
        if tech == "digital":
            if tr:
                parts.append(
                    f"Yöntem: Dijital X-Işını Pozlama Abağı (kV–mA·dk–SNR_N 2B Log-İnterpolasyon) | "
                    f"Formül: T[dk] = [E_tablo(kV, w_eq) × (SDD/{sfd_ref:.0f})² × (SNR_hedef/70)² × k_SRb / η_DQE(E)] / I"
                )
                ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
                parts.append(
                    f"Parametreler: Malzeme={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                    f"U={kv:.0f} kV → E_tablo={exp_chart:.3f} mA·dk (@700 mm, SNR_N=70), "
                    f"η_DQE(E)={det_factor:.2f}×, Hedef SNR_N={target_snr:.0f}, k_SRb={srb_factor:.2f}× → k_alıcı={rec_mod:.2f}×, "
                    f"SDD={sfd:.0f} mm, I={output_val:.1f} mA"
                )
            else:
                parts.append(
                    f"Method: Digital X-Ray Exposure Chart (kV–mA·min–SNR_N 2D Log-Interpolation) | "
                    f"Formula: T[min] = [E_chart(kV, w_eq) × (SDD/{sfd_ref:.0f})² × (SNR_target/70)² × k_SRb / η_DQE(E)] / I"
                )
                ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
                parts.append(
                    f"Parameters: Material={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                    f"U={kv:.0f} kV → E_chart={exp_chart:.3f} mA·min (@700 mm, SNR_N=70), "
                    f"η_DQE(E)={det_factor:.2f}×, Target SNR_N={target_snr:.0f}, k_SRb={srb_factor:.2f}× → k_receptor={rec_mod:.2f}×, "
                    f"SDD={sfd:.0f} mm, I={output_val:.1f} mA"
                )
        else:
            if tr:
                parts.append(
                    f"Yöntem: Type X (X-Ray Poz Diyagramı, 2B Log-İnterpolasyon) | "
                    f"Formül: T[dk] = [E_tablo(kV, w_eq) × ({dist_lbl}/{sfd_ref:.0f})² × k_alıcı] / I"
                )
                ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
                parts.append(
                    f"Parametreler: Malzeme={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                    f"U={kv:.0f} kV → E_tablo={exp_chart:.3f} mA·dk (@700 mm, C5, D=2.0), "
                    f"k_alıcı={rec_mod:.2f}×, {dist_lbl}={sfd:.0f} mm, I={output_val:.1f} mA"
                )
            else:
                parts.append(
                    f"Method: Type X (X-Ray Exposure Chart, 2D Log-Interpolation) | "
                    f"Formula: T[min] = [E_chart(kV, w_eq) × ({dist_lbl}/{sfd_ref:.0f})² × k_receptor] / I"
                )
                ref_txt = f", REF={ref_factor:.2f} → w_eq={w_eq:.2f} mm" if abs(ref_factor - 1.0) > 1e-3 else ""
                parts.append(
                    f"Parameters: Material={mat_label} (w_eff={w_eff:.2f} mm{ref_txt}), "
                    f"U={kv:.0f} kV → E_chart={exp_chart:.3f} mA·min (@700 mm, C5, D=2.0), "
                    f"k_receptor={rec_mod:.2f}×, {dist_lbl}={sfd:.0f} mm, I={output_val:.1f} mA"
                )
    else:
        # Physics model (Beer-Lambert + Inverse Square Law) or ASTM E2698 DDA Frame Method
        base_e = prov.get("base_factor", 3.0) or 3.0
        mu_raw = prov.get("mu_raw", 0.035) or 0.035
        mu_eff = prov.get("mu_eff", mu_raw) or mu_raw
        bh_pct = prov.get("beam_hardening_pct", 0.0) or 0.0
        atten = prov.get("attenuation", 1.0) or 1.0
        e_unit = "mA·dk/m²" if (source == "x_ray" and tr) else ("mA·min/m²" if source == "x_ray" else ("Ci·dk/m²" if tr else "Ci·min/m²"))

        if tech == "analog":
            film_cls = prov.get("film_class", "C5")
            film_spd = prov.get("film_speed", 16.0) or 16.0
            grad = prov.get("gradient", 3.0) or 3.0
            target_od = prov.get("target_od", 2.3) or 2.3
            od_factor = prov.get("od_factor", 1.0) or 1.0
            if tr:
                parts.append(
                    f"Yöntem: Analitik Fizik Modeli (Beer-Lambert + Ters Kare + ISO 11699-1 Sensitometri) | "
                    f"Formül: T[dk] = [E_baz × (SFD/1000)² × e^(μ_eff·w_eff) / P] × [10^((D_hedef−2.0)/G̅) / S_film]"
                )
            else:
                parts.append(
                    f"Method: Analytical Physics Model (Beer-Lambert + Inverse Square + ISO 11699-1 Sensitometry) | "
                    f"Formula: T[min] = [E_base × (SFD/1000)² × e^(μ_eff·w_eff) / P] × [10^((D_target−2.0)/G̅) / S_film]"
                )
            qual_str = (
                f"Film={film_cls} (S_film={film_spd:.0f}, G̅={grad:.1f}), Hedef D={target_od:.1f} → k_OD={od_factor:.2f}×"
                if tr else
                f"Film={film_cls} (S_film={film_spd:.0f}, G̅={grad:.1f}), Target D={target_od:.1f} → k_OD={od_factor:.2f}×"
            )
        else:
            det_type = prov.get("detector_type", "cr_standard")
            det_factor = prov.get("det_factor", 1.0) or 1.0
            target_snr = prov.get("target_snr", 100.0) or 100.0
            snr_factor = prov.get("snr_factor", 1.0) or 1.0
            srb_factor = prov.get("srb_factor", 1.0) or 1.0
            srb_ref = prov.get("srb_ref", 100.0) or 100.0
            app_srb = prov.get("app_srb")
            srb_str = (
                f", k_SRb=({srb_ref:.0f}/{float(app_srb):.0f})²={srb_factor:.2f}×"
                if (app_srb and abs(srb_factor - 1.0) > 1e-3) else ""
            )
            if method == "dda_frame_method":
                if tr:
                    parts.append(
                        f"Yöntem: ASTM E2698 DDA Kare Entegrasyon & Doygunluk Yöntemi (T = N_kare × t_kare) | "
                        f"Formül: t_kare = D_hedef(%65 ADC)/Ḋ_det, N_kare = ⌈(SNR_hedef / SNR_1kare)² × k_SRb⌉"
                    )
                else:
                    parts.append(
                        f"Method: ASTM E2698 DDA Frame Integration & Saturation Method (T = N_frames × t_frame) | "
                        f"Formula: t_frame = D_target(65% ADC)/Ḋ_det, N_frames = ⌈(SNR_target / SNR_1frame)² × k_SRb⌉"
                    )
            else:
                if tr:
                    parts.append(
                        f"Yöntem: ISO 17636-2 Analitik Kuantum DQE(E) & SNR Modeli | "
                        f"Formül: T[dk] = [E_baz × (SDD/1000)² × e^(μ_eff·w_eff) / P] × [(SNR_hedef/70)² × k_SRb / η_DQE(E)]"
                    )
                else:
                    parts.append(
                        f"Method: ISO 17636-2 Analytical Quantum DQE(E) & SNR Model | "
                        f"Formula: T[min] = [E_base × (SDD/1000)² × e^(μ_eff·w_eff) / P] × [(SNR_target/70)² × k_SRb / η_DQE(E)]"
                    )
            qual_str = (
                f"Dedektör={det_type} (η_DQE(E)={det_factor:.2f}×), Hedef SNR_N={target_snr:.0f} → k_SNR=({target_snr:.0f}/70)²={snr_factor:.2f}×{srb_str}"
                if tr else
                f"Detector={det_type} (η_DQE(E)={det_factor:.2f}×), Target SNR_N={target_snr:.0f} → k_SNR=({target_snr:.0f}/70)²={snr_factor:.2f}×{srb_str}"
            )

        if source == "x_ray":
            kv = prov.get("kv", 120.0) or 120.0
            bh_note = f" (−%{bh_pct:.1f} demet sertleşmesi)" if (bh_pct > 0.05 and tr) else (
                f" (−{bh_pct:.1f}% beam hardening)" if bh_pct > 0.05 else ""
            )
            mu_str = f"U={kv:.0f} kV → μ_eff={mu_eff:.4f} mm⁻¹{bh_note}"
        else:
            mu_st = prov.get("mu_steel_base", mu_raw) or mu_raw
            if abs(ref_factor - 1.0) > 1e-3:
                mu_str = f"μ_çelik={mu_st:.3f} × REF({ref_factor:.2f}) → μ_eff={mu_eff:.4f} mm⁻¹" if tr else f"μ_steel={mu_st:.3f} × REF({ref_factor:.2f}) → μ_eff={mu_eff:.4f} mm⁻¹"
            else:
                mu_str = f"μ_eff={mu_eff:.4f} mm⁻¹"

        if tr:
            parts.append(
                f"Parametreler: Malzeme={mat_label} (w_eff={w_eff:.2f} mm), {mu_str}, "
                f"e^(μ·w)={atten:.2f}×, E_baz={base_e:.2f} {e_unit}, {dist_lbl}={sfd:.0f} mm, P={output_val:.1f} {out_unit} | {qual_str}"
            )
        else:
            parts.append(
                f"Parameters: Material={mat_label} (w_eff={w_eff:.2f} mm), {mu_str}, "
                f"e^(μ·w)={atten:.2f}×, E_base={base_e:.2f} {e_unit}, {dist_lbl}={sfd:.0f} mm, P={output_val:.1f} {out_unit} | {qual_str}"
            )

    # DDA Frame Integration breakdown (when DDA flat panel is active)
    dda_frame = prov.get("dda_frame")
    if dda_frame and tech == "digital":
        n_fr = dda_frame.get("n_frames", 1)
        t_fr = dda_frame.get("t_frame_sec", 1.0)
        t_fr_ms = dda_frame.get("t_frame_ms", round(t_fr * 1000.0, 1))
        fps = dda_frame.get("fps", round(1.0 / max(0.01, t_fr), 2))
        tot_acq = dda_frame.get("total_acq_sec", float(n_fr) * float(t_fr))
        gray_pct = dda_frame.get("target_gray_pct", 65.0)
        adu = dda_frame.get("target_adu_16bit", 42600)
        snr_1 = dda_frame.get("snr_1frame", 42.0)
        tot_dose = dda_frame.get("total_dose_ugy", 0.0)
        p_class = dda_frame.get("panel_class", "DDA")
        if tr:
            parts.append(
                f"DDA Kare & Doz Entegrasyonu (ASTM E2698 / ISO 17636-2): "
                f"Kare Sayısı: N = {n_fr} adet (Averaging) • "
                f"Kare Süresi: t_kare = {t_fr:.2f} sn ({t_fr_ms:.0f} ms) • "
                f"Kare Hızı: {fps:.1f} FPS • "
                f"Toplam Poz: T = {tot_acq:.2f} sn • "
                f"Hedef ADC: %{gray_pct:.0f} (~{adu} ADU / 16-bit) • "
                f"Dedektör Dozu: {tot_dose:.1f} µGy • "
                f"Tek Kare SNR_1kare ≈ {snr_1:.1f} [{p_class}]"
            )
        else:
            parts.append(
                f"DDA Frame & Dose Integration (ASTM E2698 / ISO 17636-2): "
                f"Frame Count: N = {n_fr} (Averaging) • "
                f"Frame Time: t_frame = {t_fr:.2f} s ({t_fr_ms:.0f} ms) • "
                f"Frame Rate: {fps:.1f} FPS • "
                f"Total Acquisition: T = {tot_acq:.2f} s • "
                f"Target ADC: {gray_pct:.0f}% (~{adu} ADU / 16-bit) • "
                f"Detector Dose: {tot_dose:.1f} µGy • "
                f"Single Frame SNR_1frame ≈ {snr_1:.1f} [{p_class}]"
            )

    # Extra multipliers (Level 3 SFD compensation & Field factor F)
    extras = []
    time_mult = prov.get("time_multiplier", 1.0) or 1.0
    if prov.get("lvl3_sfd_comp") and abs(time_mult - 1.0) > 1e-3:
        extras.append(
            f"Seviye 3 Mesafe Telafisi: ×{time_mult:.2f} ((SFD_min/SFD)²)"
            if tr else
            f"Level 3 Distance Compensation: ×{time_mult:.2f} ((SFD_min/SFD)²)"
        )
    base_mult = prov.get("base_multiplier", 1.0) or 1.0
    if abs(base_mult - 1.0) > 1e-3:
        extras.append(
            f"Saha Düzeltme Çarpanı (F): ×{base_mult:.2f}"
            if tr else
            f"Field Correction Factor (F): ×{base_mult:.2f}"
        )
    if extras:
        parts.append(" | ".join(extras))

    return " — ".join(parts)


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
    if form and "detector_width" in form and "panel_width" not in form:
        f["panel_width"] = form["detector_width"]
    if form and "detector_height" in form and "panel_height" not in form:
        f["panel_height"] = form["detector_height"]
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
        cap = max(0.0, f["cap"])
        b_override = f.get("b_object")

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
        cap_for_b = cap if geometry in ("swsi", "dwsi") else 0.0
        w_weld = t + cap_for_b
        cap_exceeds_rule = w_weld >= 1.2 * t - 1e-9
        if geometry in ("dwdi_elliptic", "dwdi_super"):
            b_dist = b_override if (b_override is not None and b_override > 0.0) else od
            f_min_iso_base = calc.calculate_f_min(d, b_dist, testing_class, t, cap=0.0)
        elif is_planar:
            if b_override is not None and b_override > 0.0:
                b_dist = b_override
            elif calc.is_central_projection(geometry, std_figure):
                b_dist = calc.calculate_b_panoramic(bed, bgap, t)
                if b_dist < 1.2 * t and (bed + bgap + t + cap) > b_dist:
                    b_dist = bed + bgap + t + cap
            else:
                b_dist = calc.calculate_b_curved(bed, bgap, t, testing_class)
                if b_dist < 1.2 * t and (bed + bgap + t + cap) > b_dist:
                    b_dist = bed + bgap + t + cap
            f_min_star, ci_factor = calc.calculate_f_min_star(d, b_dist, t, testing_class)
            if f_min_star is not None:
                f_min_iso_base = f_min_star
            else:
                f_min_iso_base = calc.calculate_f_min(d, b_dist, testing_class, t, cap=cap_for_b)
        else:
            b_raw = b_override if (b_override is not None and b_override > 0.0) else w_weld
            b_dist = max(b_raw, w_weld) if cap_exceeds_rule else b_raw
            f_min_iso_base = calc.calculate_f_min(d, b_dist, testing_class, t, cap=cap_for_b)
        b_eff, b_rule_applied = calc.get_effective_b(b_dist, t, cap=cap_for_b)
        b_geom = b_dist if is_planar else (b_eff if (b_rule_applied or b_eff > b_dist) else max(b_dist, b_eff if cap_exceeds_rule else b_dist))

        f_min_asme_base = calc.calculate_asme_f_min(d, b_geom, t)

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
        is_panoramic = calc.is_central_projection(geometry, std_figure)
        coverage_min = 0.0 if is_panoramic else calc.calculate_coverage_min(receptor_size)

        dwsi_physical_min = 0.0
        if geometry == "dwsi" and od > 0.0:
            dwsi_physical_min = od + max(0.0, bgap)

        lvl3_dw = bool(lvl3.get("dw_reduction")) and calc.is_double_wall_technique(geometry)
        lvl3_central = bool(lvl3.get("central_proj_reduction")) and is_panoramic
        l3_factor = (0.8 if lvl3_dw else 1.0) * (0.5 if lvl3_central else 1.0)

        f_min_iso = f_min_iso_base * l3_factor
        f_min_asme_calc = f_min_asme_base * l3_factor
        f_min_asme = f_min_asme_calc if standard == "asme" else None
        f_min = f_min_asme_calc if standard == "asme" else f_min_iso

        sfd_min_iso_b = f_min + b_geom
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
        candidates = [
            {
                "key": "f_min_plus_b",
                "value": sfd_min_iso_b,
                "f_min": f_min,
                "b": b_geom,
                "formula_key": f_formula,
                "l3_dw": lvl3_dw,
                "l3_central": lvl3_central,
            },
        ]
        if not is_panoramic:
            candidates.append(
                {
                    "key": "coverage",
                    "value": coverage_min,
                    "receptor": "dd" if is_digital else "df",
                    "size": receptor_size,
                    "factor": 1.4,
                    "formula_key": ("sfd_prov_formula_f7" if is_digital
                                    else "sfd_prov_formula_f4"),
                }
            )
        candidates.append(
            {
                "key": "dwsi_floor",
                "value": dwsi_physical_min,
                "formula_key": "sfd_prov_formula_dwsi_floor",
            }
        )
        provenance = {
            "active": active_source,
            "is_panoramic": is_panoramic,
            "candidates": candidates,
            "sfd_applied": sfd,
            "sfd_min": sfd_min,
            "b": b_geom,
            "f_min": f_min,
            "dwsi_physical_min": dwsi_physical_min,
            "coverage_min": coverage_min,
            "is_digital": is_digital,
            "receptor_size": receptor_size,
            "lvl3_sfd_comp": bool(lvl3.get("sfd_comp")) if lvl3 else False,
        }

        ug = calc.calculate_geometric_unsharpness_from_sfd(d, b_geom, sfd)

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
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme_calc,
            "f_min_iso_base": f_min_iso_base,
            "f_min_asme_base": f_min_asme_base,
            "ug_limit_asme": calc.get_asme_ug_limit(t),
            "formula_key": f_min_formula,
            "standard": standard,
            "l3_dw": lvl3_dw,
            "l3_central": lvl3_central,
            "factor": l3_factor,
            "b": b_geom,
            "d": d,
            "t": t,
            "b_rule_applied": b_rule_applied,
            "f_min_star": f_min_star,
            "ci_factor": ci_factor,
            "testing_class": testing_class,
            "geometry": geometry,
            "is_planar": is_planar,
            "is_digital": is_digital,
        }

        return {
            "b_dist": b_dist,
            "b_eff": b_eff,
            "b_rule_applied": b_rule_applied,
            "f_min": f_min,
            "f_min_iso": f_min_iso,
            "f_min_asme": f_min_asme,
            "f_min_asme_calc": f_min_asme_calc,
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
            # Outside the digitized Annex A chart. Returning 1 (the old
            # behaviour) grossly under-counts the required exposures, so use
            # the chart cap (highest N curve) as a conservative minimum.
            cap = annex_a.chart_cap(testing_class, film_inside=True) or 1
            return int(cap), {"method": "out_of_chart", "n": int(cap),
                              "film_inside": True}
        if figure in self.FILM_OUTSIDE_FIGURES:
            detail = annex_a.lookup_detail(
                t, od, sfd, testing_class, film_inside=False)
            if detail is not None:
                return max(3, int(detail["n"])), self._annex_provenance(
                    detail, figure, l3_dw=geo["lvl3_dw"])
            cap = annex_a.chart_cap(testing_class, film_inside=False) or 3
            cap = max(3, int(cap))
            return cap, {"method": "out_of_chart", "n": cap,
                         "film_inside": False}
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
        receptor_w = geo["receptor_w"]
        receptor_h = geo["receptor_h"]
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

        if exposures_prov.get("method") == "out_of_chart":
            warnings.append(trans.get("warn_exposures_out_of_chart",
                                      exposures_prov.get("n")))

        n_panel = None
        n_applied = f["app_exposures"]
        n_required = exposures
        exposures_ok = None
        panel_width = f["panel_width"]
        panel_height = f["panel_height"]
        panel_res = None
        n_film = None
        user_overlap = None
        for ov_key in ("film_overlap", "app_overlap", "overlap"):
            if f.get(ov_key) is not None:
                try:
                    user_overlap = float(f[ov_key])
                    break
                except (ValueError, TypeError):
                    pass
        overlap_mm = user_overlap if user_overlap is not None else 10.0
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
            if panel_res["limiting_factor"] == "invalid_panel_geometry":
                if trans.language == "tr":
                    warnings.append("UYARI: Dedektör panel aktif genişliği geçersiz (<= 0). Poz sayısı panel modeli yerine standart grafiğe göre belirlendi.")
                else:
                    warnings.append("WARNING: Detector panel active width is invalid (<= 0). The exposure count was determined from the standard graph instead of the panel model.")
            elif panel_res["limiting_factor"] == "panel":
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
            # Analog film coverage calculation
            n_film = None
            film_res = None
            raw_len = max(float(f.get("film_height") or 0.0), float(f.get("film_width") or 0.0))
            if raw_len > 0.0 and od > 0.0 and not calc.is_central_projection(geometry, std_figure):
                film_res = calc.calculate_film_exposures(od, raw_len, overlap_mm, geometry, t)
                n_film = film_res["n_film"]
            cmp_res = calc.evaluate_exposure_comparison(
                exposures, n_panel=None, n_applied=n_applied, n_film=n_film
            )
            n_required = cmp_res["n_required"]
            if n_applied > 0:
                exposures_ok = (n_applied >= n_required)
                if not exposures_ok:
                    if trans.language == "tr":
                        warnings.append(f"UYARI: Uygulanan poz sayısı ({n_applied}) standartın ve film kapsamasının gerektirdiği asgari poz sayısını ({n_required}) karşılamıyor.")
                    else:
                        warnings.append(f"WARNING: Applied exposures ({n_applied}) do not meet the required minimum ({n_required}).")
            if cmp_res.get("limiting_factor") == "film_size":
                exposures_prov["film_coverage_n"] = n_film
                exposures_prov["governing_factor"] = "film_size"
                exposures_prov["film_length_mm"] = raw_len
                exposures_prov["film_overlap_mm"] = overlap_mm
                if trans.language == "tr":
                    warnings.append(f"BİLGİ: Kaset boyutu ({raw_len:.0f} mm, bindirme: {overlap_mm:.0f} mm) poz sayısını belirliyor ({n_film} poz, Annex A tabanı: {exposures} poz).")
                else:
                    warnings.append(f"NOTE: Film length ({raw_len:.0f} mm, overlap: {overlap_mm:.0f} mm) limits exposure count ({n_film} exposures, Annex A baseline: {exposures}).")

        # DWDI Film/Panel physical projection coverage check (Figures 11 & 12)
        dwdi_coverage = None
        dwdi_coverage_detail = ""
        if geometry in ("dwdi_elliptic", "dwdi_super"):
            is_super = (geometry == "dwdi_super")
            dwdi_coverage = calc.calculate_dwdi_coverage(
                od, t, sfd, bgap=bgap, cap=cap,
                receptor_w=receptor_w, receptor_h=receptor_h,
                is_digital=is_digital, is_super=is_super,
            )
            exposures_prov["dwdi_coverage"] = dwdi_coverage
            dwdi_coverage_detail = format_dwdi_coverage_detail(
                dwdi_coverage, trans, od, t, sfd, geometry
            )
            if receptor_size > 0.0 and not dwdi_coverage["is_sufficient"]:
                avail = dwdi_coverage["available_across"] or max(receptor_w, receptor_h)
                w_min_req = dwdi_coverage["w_min_req"]
                if trans.language == "tr":
                    warnings.append(
                        f"GEOMETRİ/BOYUT UYARISI: DWDI çekimde girilen film/panel boyutu ({avail:.0f} mm), "
                        f"borunun büyütülmüş izdüşümünü ({w_min_req:.1f} mm) kurtarmıyor! "
                        f"Boru ve kaynak görüntüsünün kesilmemesi için en az {w_min_req:.1f} mm genişlik gereklidir."
                    )
                else:
                    warnings.append(
                        f"GEOMETRY/DIMENSION WARNING: In DWDI, the film/panel size ({avail:.0f} mm) "
                        f"does not cover the projected pipe image ({w_min_req:.1f} mm)! "
                        f"A minimum width of {w_min_req:.1f} mm is required to prevent image cutoff."
                    )

        # 6. kV input (X-ray only)
        if source == "x_ray":
            input_kv = f["app_kv"]
            if input_kv <= 0.0:
                # Non-positive kV is invalid input; it otherwise divides by zero
                # in the kVp^5 sanity check. Fall back to the default and warn.
                if trans.language == "tr":
                    warnings.append(
                        f"UYARI: Girilen tüp voltajı ({input_kv:g} kV) geçersizdir "
                        f"(0'dan büyük olmalıdır); hesaplamada varsayılan 120.0 kV kullanıldı."
                    )
                else:
                    warnings.append(
                        f"WARNING: Entered tube voltage ({input_kv:g} kV) is invalid "
                        f"(must be > 0); defaulting to 120.0 kV for the calculation."
                    )
                input_kv = 120.0
                f["app_kv"] = 120.0
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
            film_class_req = calc.get_required_film_class(w_nom, testing_class, material, source, kv=input_kv)
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
            snr_mult = 1.0
            if se75_thin_class_b:
                snr_mult *= 1.4
            if snr_location == "adjacent" and not is_flush:
                snr_mult *= 1.4
                warnings.append(trans.get("warn_snr_adjacent_factor"))
            target_snr_val = base_snr * snr_mult

            if sfd < sfd_min and lvl3.get("sfd_comp"):
                k_factor = sfd_min / max(10.0, sfd)
                sfd_comp_target = target_snr_val * k_factor
                target_quality = f"{target_snr_val:.1f} -> {sfd_comp_target:.1f} (Lvl 3 Comp) [{table_name}]"
                time_multiplier = k_factor ** 2
            else:
                target_quality = f">= {int(round(target_snr_val))} [{table_name}]"

        # 10. Field correction factor & calculated exposure time + formula provenance
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

        extra_multiplier = time_multiplier * base_multiplier
        exp_details = calc.calculate_exposure_time_details(
            sfd, w_eff, source, output_val, base_e, tech,
            testing_class=testing_class,
            film_class=film_class_used,
            detector_type=detector_type,
            kv=input_kv,
            material=material,
            chart_source=chart_source if chart_source != "model" else None,
            chart_db=self.chart_db,
            density=required_density,
            target_snr=target_snr_val if tech == "digital" else None,
            app_srb=f.get("app_srb") if tech == "digital" else None,
            extra_multiplier=extra_multiplier,
        )
        min_calc = exp_details["minutes"]
        sec_calc = exp_details["seconds"]
        raw_time = exp_details["time_seconds"]
        exposure_time_prov = dict(exp_details["provenance"])

        # Keep DDA frame integration in sync if Level 3 SFD comp increased the required SNR_N target
        if tech == "digital" and exposure_time_prov.get("dda_frame") and sfd_comp_target is not None:
            det_for_dda = detector_type if str(detector_type).startswith("dda_") else "dda_si"
            exposure_time_prov["dda_frame"] = calc.calculate_dda_frame_integration(
                raw_time, sfd, w_eff, source, output_val,
                det_for_dda, sfd_comp_target, kv=input_kv,
                material=material,
                srb_factor=exposure_time_prov.get("srb_factor", 1.0),
                dqe_factor=exposure_time_prov.get("det_factor", 3.5),
                testing_class=testing_class,
            )
            if chart_source == "dda_frame_method":
                raw_time = min(864000.0, exposure_time_prov["dda_frame"]["total_acq_sec"])
            else:
                min_acq_floor = max(
                    2.0 if source == "x_ray" else 0.0,
                    float(exposure_time_prov["dda_frame"]["n_frames"]) * 0.10,
                )
                raw_time = max(raw_time, min_acq_floor)
            min_calc = int(raw_time // 60)
            sec_calc = int(raw_time % 60)

        exposure_time_prov["lvl3_sfd_comp"] = (sfd_comp_target is not None)
        exposure_time_prov["time_multiplier"] = time_multiplier
        exposure_time_prov["base_multiplier"] = base_multiplier
        exposure_time_prov["final_seconds"] = raw_time
        exposure_time_prov["final_min"] = min_calc
        exposure_time_prov["final_sec"] = sec_calc
        exposure_time_prov_text = format_exposure_time_provenance(exposure_time_prov, trans)

        # 11b. Joint total exposure time & optimization recommendations
        effective_joint_exposures = n_applied if n_applied > 0 else n_required
        joint_time_res = calc.calculate_joint_total_time(raw_time, effective_joint_exposures)
        total_joint_sec = joint_time_res["total_seconds"]
        total_joint_min = joint_time_res["minutes"]
        total_joint_sec_rem = joint_time_res["seconds"]
        time_unit_min = "dk" if trans.language == "tr" else "min"
        time_unit_sec = "sn" if trans.language == "tr" else "sec"
        total_joint_str = f"{total_joint_min} {time_unit_min} {total_joint_sec_rem:02d} {time_unit_sec}"

        suggestion_msgs = []
        suggestions = {
            "film_rec": None,
            "fmin_rec": None,
            "time_saved_step_str": None,
            "messages": suggestion_msgs,
        }
        if tech == "analog" and od > 0.0 and n_required > exposures:
            film_rec = calc.recommend_film_size(od, n_required, exposures, overlap_mm=overlap_mm)
            if film_rec and film_rec["can_reduce"]:
                step_diff = n_required - film_rec["target_n_step"]
                if step_diff > 0 and raw_time > 0:
                    saved_sec = step_diff * raw_time
                    s_min = int(saved_sec // 60)
                    s_sec = int(saved_sec % 60)
                    time_saved_str = f"{s_min} {time_unit_min} {s_sec:02d} {time_unit_sec}"
                    suggestions["time_saved_step_str"] = time_saved_str
                    msg_step = trans.get("opt_film_step", film_rec["req_length_step_mm"], film_rec["target_n_step"], time_saved_str)
                    warnings.append(msg_step)
                    suggestion_msgs.append(msg_step)
                msg_ideal = trans.get("opt_film_ideal", film_rec["req_length_ideal_mm"], film_rec["target_n_ideal"])
                warnings.append(msg_ideal)
                suggestion_msgs.append(msg_ideal)
                suggestions["film_rec"] = film_rec

        # f_min geometry optimization recommendation
        f_current = f.get("f_source") if f.get("f_source") else max(sfd - b_dist, 1.0)
        fmin_rec = calc.recommend_detector_size_for_fmin(od, t, d, f_current, testing_class=testing_class)
        if fmin_rec and fmin_rec["can_optimize"]:
            suggestions["fmin_rec"] = fmin_rec
            msg_fmin = trans.get("opt_fmin_detector", fmin_rec["f_min_geo"], fmin_rec["recommended_detector_width_mm"])
            warnings.append(msg_fmin)
            suggestion_msgs.append(msg_fmin)

        # WAE circumferential assumption note (when film coverage governs)
        if tech == "analog" and cmp_res.get("limiting_factor") == "film_size":
            warnings.append(trans.get("info_wae_circumference_assumed"))

        if exposure_time_prov.get("fallback_reason"):
            fb = exposure_time_prov["fallback_reason"]
            if fb == "type_x_requires_xray":
                if trans.language == "tr":
                    warnings.append("BİLGİ (Poz Diyagramı): Type X diyagramı yalnızca X-Ray kaynağı için geçerlidir; analitik fizik modeline geçildi.")
                else:
                    warnings.append("NOTE (Exposure Chart): Type X chart is only valid for X-Ray sources; fell back to analytical physics model.")
            elif fb == "rfactor_source_unavailable":
                if trans.language == "tr":
                    warnings.append(f"BİLGİ (Poz Diyagramı): Seçilen R-Faktör diyagramı ({chart_source}) bu kaynak ({source}) için tanımlı değil; analitik fizik modeline geçildi.")
                else:
                    warnings.append(f"NOTE (Exposure Chart): Selected R-Factor chart ({chart_source}) has no data for source ({source}); fell back to analytical physics model.")

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
        elif geometry in ("swsi", "dwsi") and ((not geo["is_planar"] and b_dist >= 1.2 * t) or (cap > 0.0 and (t + cap) >= 1.2 * t - 1e-9)):
            w_weld_disp = t + cap
            if trans.language == "tr":
                warnings.append(
                    f"BİLGİ (Madde 7.6): Toplam kalınlık b = t + kep/kök ({w_weld_disp:.1f} mm) ≥ 1.2×t ({1.2*t:.1f} mm) olduğundan b = t basitleştirmesi uygulanmadı; b = {b_dist:.1f} mm kullanıldı."
                )
            else:
                warnings.append(
                    f"NOTE (Clause 7.6): Total thickness b = t + cap/root ({w_weld_disp:.1f} mm) ≥ 1.2×t ({1.2*t:.1f} mm); b = t simplification not applied, using b = {b_dist:.1f} mm."
                )

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

        if calc.is_central_projection(geometry, std_figure):
            if trans.language == "tr":
                warnings.append(
                    f"BİLGİ (Madde 7.6): SWSI panoramik (merkezi izdüşüm - Şekil 5) çekimde kaynak boru merkezinde (360° radyal) olduğundan düzlemsel köşegen kapsaması (1,4·df / Formül 4) uygulanmaz; SFD_min = f_min + b ({sfd_min:.1f} mm) geçerlidir."
                )
            else:
                warnings.append(
                    f"NOTE (Clause 7.6): In SWSI panoramic (central projection - Figure 5) exposure, the source is at the pipe centre (360° radial), so planar diagonal coverage (1.4*df / Formula 4) does not apply; SFD_min = f_min + b ({sfd_min:.1f} mm) governs."
                )
        elif coverage_min > f_min + b_dist:
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
            srb_for_annex_f = f.get("app_srb") or max_srb_req or 0.0
            annex_f_req = calc.calculate_annex_f_fmin(
                d, geo["b_dist"], srb_for_annex_f, testing_class)
            geo["f_min_provenance"]["annex_f_req"] = annex_f_req
            geo["f_min_provenance"]["annex_f_srb"] = srb_for_annex_f
            geo["f_min_provenance"]["annex_f_compensated"] = bool(annex_f_req and annex_f_req > f_min + 1e-9)
            if annex_f_req is None:
                if trans.language == "tr":
                    warnings.append(
                        "BİLGİ (Annex F): Dedektör bulanıklığı bu nesne-dedektör mesafesinde (b) telafi edilemez; "
                        "b artırılmalıdır (bkz. ISO 17636-2 Tablo F.1).")
                else:
                    warnings.append(
                        "NOTE (Annex F): Detector unsharpness cannot be compensated at this "
                        "object-to-detector distance (b); increase b (see ISO 17636-2 Table F.1).")
            elif annex_f_req > f_min + 1e-9:
                if trans.language == "tr":
                    warnings.append(
                        f"BİLGİ (Annex F): Dedektör bulanıklığını telafi için f_min {f_min:.1f} mm → "
                        f"{annex_f_req:.1f} mm değerine yükseltilmelidir (SRb={srb_for_annex_f:.0f} µm).")
                else:
                    warnings.append(
                        f"NOTE (Annex F): To compensate detector unsharpness, increase f_min from "
                        f"{f_min:.1f} mm to {annex_f_req:.1f} mm (SRb={srb_for_annex_f:.0f} µm).")

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

        if geometry == "dwsi" and std_figure in ("fig14", "fig14a", "fig14b"):
            f_min_val = geo.get("f_min", 0.0)
            if od > 0.0 and f_min_val > od:
                is_dig = geo.get("is_digital", False)
                fig13_name = ("Şekil 13a" if std_figure == "fig14a" else "Şekil 13b") if is_dig else "Şekil 13"
                fig13_name_en = ("Figure 13a" if std_figure == "fig14a" else "Figure 13b") if is_dig else "Figure 13"
                if trans.language == "tr":
                    warnings.append(
                        f"GEOMETRİ/ŞEKİL UYARISI (ISO 17636 Madde 7.6): DWSI Odak Yüzeyde ({std_figure}) tekniğinde "
                        f"gereken asgari odak mesafesi (f_min = {f_min_val:.1f} mm), boru dış çapından (OD = {od:.1f} mm) büyüktür! "
                        f"Kaynak boru yüzeyine konulduğunda geometrik bulanıklık (Ug) standardı aşar. "
                        f"Seçilen şekil ({std_figure}) uygun DEĞİLDİR; kaynak borudan geri çekilerek {fig13_name} kullanılmalıdır."
                    )
                else:
                    warnings.append(
                        f"GEOMETRY/FIGURE WARNING (ISO 17636 Clause 7.6): In DWSI Source-on-Surface ({std_figure}), "
                        f"required minimum distance (f_min = {f_min_val:.1f} mm) exceeds pipe outer diameter (OD = {od:.1f} mm)! "
                        f"Placing source on surface violates geometric unsharpness (Ug) limits. "
                        f"Selected figure ({std_figure}) is INVALID; move source back and use {fig13_name_en}."
                    )

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

        if tech == "analog" and f.get("app_quality") is not None:
            try:
                app_d = float(f["app_quality"])
                if app_d > 4.0:
                    if trans.language == "tr":
                        warnings.append(f"UYARI: Uygulanan optik yoğunluk ({app_d:.2f}) standart azami limitini (4.00) aşıyor! Film aşırı koyulaşmış ve detaylar değerlendirilemeyebilir.")
                    else:
                        warnings.append(f"WARNING: Applied optical density ({app_d:.2f}) exceeds the standard maximum limit (4.00)! Film may be too dark and unreadable.")
            except (ValueError, TypeError):
                pass

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
            film_comp, film_msg = calc.check_film_class_compliance(film_class_used, testing_class, w_nom, material, source, kv=input_kv)
            if not film_comp:
                if trans.language == "tr":
                    warnings.append(f"UYARI: Kullanılan film sınıfı ({film_class_used}) standart gereksinimini karşılamıyor! Asgari gereken: {film_class_req}")
                else:
                    warnings.append(f"WARNING: Used film class ({film_class_used}) does not meet standard requirement! Required minimum: {film_class_req}")
            chart_film_cls = getattr(self.chart_db, "FILM_CLASS_BY_MODEL", {}).get(chart_source)
            if chart_film_cls and chart_film_cls != film_class_used:
                if trans.language == "tr":
                    warnings.append(
                        f"BİLGİ: Seçilen R-Faktör diyagramı ({chart_source} → {chart_film_cls}) ile kullanılan film sınıfı ({film_class_used}) farklıdır; poz süresi {chart_source} diyagramına göre hesaplandı."
                    )
                else:
                    warnings.append(
                        f"NOTE: Selected R-Factor chart ({chart_source} → {chart_film_cls}) differs from used film class ({film_class_used}); exposure time was calculated using the {chart_source} chart."
                    )

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

        filter_recs = calc.get_filter_recommendations(
            source, material, input_kv, testing_class, w_nom)
        filter_str = format_filter_recommendation(filter_recs, trans.language)

        # 15. Chart tag + display strings
        dda_frame_info = exposure_time_prov.get("dda_frame") if tech == "digital" else None
        if dda_frame_info:
            n_fr = dda_frame_info.get("n_frames", 1)
            t_fr = dda_frame_info.get("t_frame_sec", 1.0)
            if trans.language == "tr":
                dda_tag = f" ({n_fr} kare × {t_fr:.2f} sn)"
            else:
                dda_tag = f" ({n_fr} frames × {t_fr:.2f} s)"
        else:
            dda_tag = ""
        if dda_frame_info and dda_frame_info.get("t_frame_ideal", 1.0) < 0.08:
            if trans.language == "tr":
                warnings.append("UYARI (DDA): Tek kare dozu yüksek — dedektör doyumuna yaklaşılabilir. Tüp akımını (mA) düşürün veya SFD mesafesini artırın.")
            else:
                warnings.append("WARNING (DDA): Single-frame dose is high — detector saturation possible. Reduce tube current (mA) or increase SFD.")
        chart_label = ""
        if chart_source != "model":
            chart_tag_map = {
                "type_x": "Type X",
                "cr_ips_chart": "ISO 16371-1 CR IP",
                "dda_frame_method": "ASTM E2698 N×t",
                "dda_panel_chart": "DDA Panel Chart",
                "digital_xray_chart": "Dijital X-Ray" if trans.language == "tr" else "Digital X-Ray",
            }
            chart_label = f" [{chart_tag_map.get(chart_source, chart_source)}]"

        if raw_time < 60.0:
            if raw_time < 10.0:
                time_display_val = f"{raw_time:.2f} sn" if trans.language == "tr" else f"{raw_time:.2f} s"
            else:
                time_display_val = f"{raw_time:.1f} sn" if trans.language == "tr" else f"{raw_time:.1f} s"
        else:
            time_display_val = f"{min_calc} dk {sec_calc} sn" if trans.language == "tr" else f"{min_calc} min {sec_calc} sec"

        display = {
            "w_nom": f"{w_nom:.2f} mm",
            "w_eff": f"{w_eff:.2f} mm",
            "u_max": f"{u_max:.1f} kV" if source == "x_ray" else "N/A",
            "f_min": f"{f_min:.1f} mm",
            "f_min_asme": f"{f_min_asme:.1f} mm" if (standard == "asme" and f_min_asme is not None) else "N/A",
            "sfd_min": f"{sfd_min:.1f} mm",
            "ug": f"{ug:.3f} mm",
            "req_exposures": f"{n_required}",
            "exposures_panel": f"{n_panel}" if (tech == "digital" and n_panel is not None) else (f"{n_film}" if n_film is not None else "N/A"),
            "exposures_film": f"{n_film}" if n_film is not None else "N/A",
            "exposures_applied": f"{n_applied}" if n_applied > 0 else "-",
            "single_wire_iqi": wire_str,
            "duplex_iqi": duplex_str if tech == "digital" else "N/A",
            "quality_target": target_quality,
            "calc_time": f"{time_display_val}{dda_tag}{chart_label}",
            "total_joint_time": total_joint_str,
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
            "exposures_film": n_film,
            "film_overlap": overlap_mm,
            "exposures_applied": n_applied,
            "required_exposures": n_required,
            "exposures_ok": exposures_ok,
            "base_multiplier": base_multiplier,
            "total_joint_time_seconds": total_joint_sec,
            "total_joint_time_str": total_joint_str,
            "suggestions": suggestions,
            "dwdi_coverage": dwdi_coverage,
            "dwdi_coverage_detail": dwdi_coverage_detail,
        }
        if tech == "digital":
            calculated["required_snr"] = target_snr_val
            calculated["sfd_comp_target"] = sfd_comp_target
        else:
            calculated["required_density"] = required_density
            calculated["max_density"] = 4.0

        geo["sfd_min_provenance"]["sfd_applied"] = sfd
        geo["sfd_min_provenance"]["sfd_min"] = sfd_min
        geo["sfd_min_provenance"]["sfd_comp_target"] = sfd_comp_target
        geo["sfd_min_provenance"]["time_multiplier"] = time_multiplier
        geo["sfd_min_provenance"]["lvl3_sfd_comp"] = bool(lvl3.get("sfd_comp")) if lvl3 else False

        # Provenance for the PDF/screen explanations.
        calculated["sfd_min_provenance"] = geo["sfd_min_provenance"]
        calculated["exposures_provenance"] = exposures_prov
        calculated["f_min_provenance"] = geo["f_min_provenance"]
        calculated["exposure_time_provenance"] = exposure_time_prov
        calculated["exposure_time_provenance_text"] = exposure_time_prov_text

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
            "f_min_asme": geo.get("f_min_asme_calc", f_min_asme or 0.0),
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
            "max_density": 4.0,
            "sfd_comp_target": sfd_comp_target,
            "table_name": table_name,
            "calc_time": raw_time,
            "min_calc": min_calc,
            "sec_calc": sec_calc,
            "base_multiplier": base_multiplier,
            "raw_time": raw_time,
            "r_controlled": r_controlled,
            "r_supervised": r_supervised if source != "x_ray" else 0.0,
            "barrier_str": barrier_str,
            "filter_recs": filter_recs,
            "filter_str": filter_str,
            "asme_iqi_str": asme_iqi_str,
            "chart_label": chart_label,
            "safety_radius_m": r_controlled if source != "x_ray" else None,
            "sfd_min_provenance": geo["sfd_min_provenance"],
            "f_min_provenance": geo["f_min_provenance"],
            "exposure_time_provenance": exposure_time_prov,
            "exposure_time_provenance_text": exposure_time_prov_text,
            "total_joint_time_seconds": total_joint_sec,
            "total_joint_time_str": total_joint_str,
            "exposures_film": n_film,
            "film_overlap": overlap_mm,
            "suggestions": suggestions,
            "dwdi_coverage": dwdi_coverage,
            "dwdi_coverage_detail": dwdi_coverage_detail,
        }

        values["lvl3"] = lvl3
        values["table_name"] = table_name

        f_min_prov_text = format_f_min_provenance(geo["f_min_provenance"], trans)
        sfd_min_prov_text = format_sfd_provenance(geo["sfd_min_provenance"], trans)
        single_wire_prov_text = format_single_wire_iqi_provenance(values, trans)
        duplex_prov_text = format_duplex_iqi_provenance(values, trans)
        quality_target_prov_text = format_quality_target_provenance(values, trans)
        detector_quality_prov_text = format_detector_quality_provenance(values, trans)
        u_max_prov_text = format_u_max_provenance(values, trans)
        ug_prov_text = format_ug_provenance(values, trans)
        exposures_prov_text = format_exposures_provenance(exposures_prov, trans)

        values["f_min_provenance_text"] = f_min_prov_text
        values["sfd_min_provenance_text"] = sfd_min_prov_text
        values["single_wire_iqi_provenance_text"] = single_wire_prov_text
        values["duplex_iqi_provenance_text"] = duplex_prov_text
        values["quality_target_provenance_text"] = quality_target_prov_text
        values["detector_quality_provenance_text"] = detector_quality_prov_text
        values["u_max_provenance_text"] = u_max_prov_text
        values["ug_provenance_text"] = ug_prov_text
        values["req_exposures_provenance_text"] = exposures_prov_text
        values["calc_time_provenance_text"] = exposure_time_prov_text

        calculated["f_min_provenance_text"] = f_min_prov_text
        calculated["sfd_min_provenance_text"] = sfd_min_prov_text
        calculated["single_wire_iqi_provenance_text"] = single_wire_prov_text
        calculated["duplex_iqi_provenance_text"] = duplex_prov_text
        calculated["quality_target_provenance_text"] = quality_target_prov_text
        calculated["detector_quality_provenance_text"] = detector_quality_prov_text
        calculated["u_max_provenance_text"] = u_max_prov_text
        calculated["ug_provenance_text"] = ug_prov_text
        calculated["req_exposures_provenance_text"] = exposures_prov_text
        calculated["calc_time_provenance_text"] = exposure_time_prov_text

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
            "od": f["od"],
            "std_figure": f.get("std_figure"),
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
