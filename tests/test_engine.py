# -*- coding: utf-8 -*-
"""Contract tests for the shared CalculationEngine (src/core/engine.py).

The engine is the single calculation path used by the desktop UI, the mobile
AppState and the web (Pyodide) front-end. These tests lock its public shape and
a few standard-derived values so a regression in the engine cannot be hidden by
the UI adapters.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.core.engine import CalculationEngine, normalize_form


@pytest.fixture
def engine():
    return CalculationEngine()


def test_result_contract(engine):
    result = engine.calculate({})
    for key in ("calculated", "warnings", "display", "values", "form"):
        assert key in result
    assert isinstance(result["warnings"], list)
    for key in (
        "w_nom", "w_eff", "u_max", "f_min", "sfd_min", "ug", "req_exposures",
        "single_wire_iqi", "duplex_iqi", "quality_target", "calc_time",
        "detector_quality", "asme_iqi", "barrier_distance", "filter_recommendation",
        "exposures_panel", "exposures_applied", "exposures_check",
    ):
        assert key in result["display"], key
    for key in (
        "w_nom", "w_eff", "u_max", "sfd_min", "ug", "f_min", "f_min_iso",
        "b_dist", "b_eff", "required_wire_no", "calc_time_raw",
    ):
        assert key in result["calculated"], key


def test_swsi_thicknesses(engine):
    result = engine.calculate({"geometry": "swsi", "t": 6.02, "cap": 3.0})
    assert result["values"]["w_nom"] == pytest.approx(6.02)
    assert result["values"]["w_eff"] == pytest.approx(9.02)


def test_sfd_min_is_governing_max(engine):
    result = engine.calculate({"geometry": "dwsi", "od": 508.0, "t": 8.0, "bgap": 5.0})
    values = result["values"]
    assert values["sfd_min"] >= values["f_min"] + values["b_dist"] - 1e-9
    assert values["sfd_min"] >= values["dwsi_physical_min"] - 1e-9
    assert values["sfd_min"] >= values["coverage_min"] - 1e-9


def test_ug_uses_sfd_minus_b(engine):
    # Analog film model (flush weld cap=0): b = t for SWSI, so Ug = d·t/(SFD - t)
    result = engine.calculate({
        "geometry": "swsi", "tech": "analog", "t": 6.02, "cap": 0.0, "d": 2.0, "sfd": 600.0,
    })
    values = result["values"]
    assert values["b_dist"] == pytest.approx(6.02)
    assert values["ug"] == pytest.approx(2.0 * 6.02 / (600.0 - 6.02))


def test_clause_7_6_cap_rule(engine):
    # When t=6.0 and cap=1.0 -> total thickness b=7.0 < 1.2*t (7.2) -> b_eff = t = 6.0
    res_small_cap = engine.calculate({
        "geometry": "swsi", "tech": "analog", "t": 6.0, "cap": 1.0, "d": 2.0, "sfd": 600.0,
    })
    v1 = res_small_cap["values"]
    assert v1["b_dist"] == pytest.approx(7.0)
    assert v1["b_eff"] == pytest.approx(6.0)
    assert v1["b_rule_applied"] is True
    assert any("b (7.0 mm) < 1.2×t (7.2 mm)" in w for w in res_small_cap["warnings"])

    # When t=6.0 and cap=2.0 -> total thickness b=8.0 >= 1.2*t (7.2) -> b_eff = 8.0 (rule NOT applied)
    res_large_cap = engine.calculate({
        "geometry": "swsi", "tech": "analog", "t": 6.0, "cap": 2.0, "d": 2.0, "sfd": 600.0,
    })
    v2 = res_large_cap["values"]
    assert v2["b_dist"] == pytest.approx(8.0)
    assert v2["b_eff"] == pytest.approx(8.0)
    assert v2["b_rule_applied"] is False
    assert v2["f_min_iso"] == pytest.approx(15.0 * 2.0 * (8.0 ** (2.0 / 3.0)))
    assert any("≥ 1.2×t (7.2 mm)" in w for w in res_large_cap["warnings"])

    # Regression (user case): t=5.2, cap=2.0, d=3.0 (even if stale b_object=5.0 is passed)
    # Total thickness t+cap = 7.2 mm >= 1.2*5.2 (6.24 mm) -> b_dist = 7.2, b_eff = 7.2, Ug uses b = 7.2
    res_user_case = engine.calculate({
        "geometry": "dwsi", "tech": "analog", "t": 5.2, "cap": 2.0, "d": 3.0,
        "sfd": 600.0, "b_object": 5.0,
    })
    v3 = res_user_case["values"]
    assert v3["b_dist"] == pytest.approx(7.2)
    assert v3["b_eff"] == pytest.approx(7.2)
    assert v3["b_rule_applied"] is False
    assert v3["f_min_iso"] == pytest.approx(15.0 * 3.0 * (7.2 ** (2.0 / 3.0)))
    assert v3["ug"] == pytest.approx(3.0 * 7.2 / (600.0 - 7.2))


def test_swsi_panoramic_excludes_film_diagonal_coverage(engine):
    # SWSI Panoramic (fig5): 80x300 mm film (df = 310.48 mm, 1.4*df = 434.68 mm)
    # should NOT override SFD_min = f_min + b
    res_pano = engine.calculate({
        "geometry": "swsi", "std_figure": "fig5", "tech": "analog",
        "od": 406.4, "t": 5.2, "cap": 2.0, "d": 3.0, "sfd": 203.2,
        "film_width": 80.0, "film_height": 300.0,
    })
    vp = res_pano["values"]
    assert vp["coverage_min"] == 0.0
    assert vp["sfd_min"] == pytest.approx(vp["f_min"] + vp["b_dist"])
    assert vp["sfd_min_provenance"]["active"] == "f_min_plus_b"

    # SWSI Directional (fig2): 80x300 mm film -> 1.4*df (~434.7 mm) DOES govern
    res_dir = engine.calculate({
        "geometry": "swsi", "std_figure": "fig2", "tech": "analog",
        "od": 406.4, "t": 5.2, "cap": 2.0, "d": 3.0, "sfd": 600.0,
        "film_width": 80.0, "film_height": 300.0,
    })
    vd = res_dir["values"]
    assert vd["coverage_min"] == pytest.approx(1.4 * ((80.0 ** 2 + 300.0 ** 2) ** 0.5))
    assert vd["sfd_min"] == pytest.approx(vd["coverage_min"])
    assert vd["sfd_min_provenance"]["active"] == "coverage"


def test_dwdi_forced_to_dwsi_over_100mm(engine):
    result = engine.calculate({
        "geometry": "dwdi_elliptic", "od": 200.0, "t": 6.0,
        "user_geometry": "dwdi_elliptic",
    })
    assert result["values"]["geometry"] == "dwsi"
    assert result["values"]["geometry_forced"] is True
    assert any("DWSI" in w for w in result["warnings"])


def test_level3_reductions_applied_to_geometry(engine):
    base = engine.calculate({"geometry": "dwsi", "od": 114.3, "t": 6.02})
    reduced = engine.calculate(
        {"geometry": "dwsi", "od": 114.3, "t": 6.02},
        {"dw_reduction": True},
    )
    assert reduced["values"]["f_min"] == pytest.approx(base["values"]["f_min"] * 0.8)
    assert reduced["calculated"]["lvl3_dw"] is True


def test_compliance_contract(engine):
    result = engine.calculate({})
    comp = engine.check_compliance(result["form"], result["calculated"])
    assert "is_compliant" in comp
    assert isinstance(comp["checks"], list)
    assert "activity_warning" in comp


def test_activity_warning_for_isotopes(engine):
    result = engine.calculate({
        "source": "isotope_ir192", "output_val": 40.0, "app_activity": 20.0,
    })
    comp = engine.check_compliance(result["form"], result["calculated"])
    assert comp["activity_warning"]


def test_defect_evaluation_contract(engine):
    result = engine.evaluate_defect(
        {"t": 10.0},
        {"standard": "iso5817", "type": "defect_crack", "length": 5.0, "width": 1.0},
    )
    assert result["status"] is False
    assert isinstance(result["result"], str)
    assert result["approx"] is True


def test_normalize_form_coerces_strings():
    form = normalize_form({"od": "114,3", "app_wire": "12", "app_exposures": ""})
    assert form["od"] == pytest.approx(114.3)
    assert form["app_wire"] == 12
    assert form["app_exposures"] == 0


def test_sfd_min_provenance_candidates(engine):
    result = engine.calculate({})
    prov = result["values"]["sfd_min_provenance"]
    assert [c["key"] for c in prov["candidates"]] == [
        "f_min_plus_b", "coverage", "dwsi_floor"]
    assert prov["candidates"][1]["receptor"] == "dd"
    assert prov["candidates"][1]["formula_key"] == "sfd_prov_formula_f7"


def test_sfd_min_provenance_coverage_governs(engine):
    result = engine.calculate({})
    prov = result["values"]["sfd_min_provenance"]
    assert prov["active"] == "coverage"
    assert result["values"]["sfd_min"] == pytest.approx(
        prov["candidates"][1]["value"])


def test_sfd_min_provenance_f_min_plus_b_governs(engine):
    result = engine.calculate({"panel_width": 10.0, "panel_height": 10.0})
    prov = result["values"]["sfd_min_provenance"]
    assert prov["active"] == "f_min_plus_b"


def test_sfd_min_provenance_dwsi_floor_governs(engine):
    result = engine.calculate({"od": 500.0, "t": 8.0, "bgap": 5.0})
    prov = result["values"]["sfd_min_provenance"]
    assert prov["active"] == "dwsi_floor"
    assert result["values"]["sfd_min"] == pytest.approx(505.0)


def test_sfd_min_provenance_analog_uses_film_formula(engine):
    result = engine.calculate({"tech": "analog"})
    prov = result["values"]["sfd_min_provenance"]
    coverage = prov["candidates"][1]
    assert coverage["receptor"] == "df"
    assert coverage["formula_key"] == "sfd_prov_formula_f4"


def test_exposures_provenance_dwsi_user_case(engine):
    result = engine.calculate({
        "od": 114.3, "t": 6.0, "cap": 0.0, "tech": "analog", "testing_class": "class_b",
        "geometry": "dwsi", "std_figure": "fig13", "sfd": 155.0, "d": 3.0,
        "film_width": 80.0, "film_height": 50.0, "film_class_used": "C3",
    })
    prov = result["values"]["exposures_provenance"]
    assert prov["method"] == "annex_a"
    assert prov["figure"] == "A2"
    assert prov["n"] == 5
    assert prov["t_over_de"] == pytest.approx(0.0525, abs=1e-4)
    assert prov["ratio_name"] == "De/SFD"
    assert prov["ratio"] == pytest.approx(0.7374, abs=1e-3)
    assert prov["next_n"] == 6
    assert prov["next_distance_mm"] == pytest.approx(158.3, abs=0.5)
    assert result["values"]["sfd_min"] == pytest.approx(154.6, abs=0.1)


def test_exposures_provenance_swsi_fig2_uses_annex_a1(engine):
    result = engine.calculate({
        "geometry": "swsi", "std_figure": "fig2", "tech": "analog",
        "od": 114.3, "t": 6.0, "cap": 0.0, "sfd": 600.0,
    })
    prov = result["values"]["exposures_provenance"]
    assert prov["method"] == "annex_a"
    assert prov["figure"] == "A1"
    assert prov["ratio_name"] == "De/f"
    assert prov["n"] >= 8


def test_exposures_provenance_panoramic_and_dwdi(engine):
    panoramic = engine.calculate({"geometry": "swsi", "std_figure": "fig5"})
    assert panoramic["values"]["exposures_provenance"]["method"] == "panoramic"
    assert panoramic["values"]["exposures"] == 1

    dwdi = engine.calculate({"geometry": "dwdi_elliptic", "od": 60.0, "t": 8.0})
    prov = dwdi["values"]["exposures_provenance"]
    assert prov["method"] == "dwdi_rule"
    assert prov["ratio_name"] == "t/De"


def test_exposures_provenance_text_mentions_next_boundary(engine):
    from src.core.engine import format_exposures_provenance
    from src.core.translation import Translation

    result = engine.calculate({
        "od": 114.3, "t": 6.0, "cap": 0.0, "tech": "analog", "testing_class": "class_b",
        "geometry": "dwsi", "std_figure": "fig13", "sfd": 155.0, "d": 3.0,
    })
    text = format_exposures_provenance(
        result["calculated"]["exposures_provenance"], Translation())
    assert "N=5" in text
    assert "158.3" in text
    assert "A2" in text


def test_f_min_provenance_base_and_level3_reduction(engine):
    from src.core.engine import format_f_min_provenance
    from src.core.translation import Translation

    form = {
        "od": 114.3, "t": 6.0, "cap": 0.0, "tech": "analog", "testing_class": "class_b",
        "geometry": "dwsi", "std_figure": "fig13", "sfd": 155.0, "d": 3.0,
    }
    base = engine.calculate(form, {}, "tr")
    prov = base["values"]["f_min_provenance"]
    assert prov["base"] == pytest.approx(148.59, abs=0.05)
    assert prov["value"] == pytest.approx(148.59, abs=0.05)
    assert prov["formula_key"] == "sfd_prov_formula_f2"
    assert prov["l3_dw"] is False

    reduced = engine.calculate(form, {"dw_reduction": True}, "tr")
    prov_r = reduced["values"]["f_min_provenance"]
    assert prov_r["base"] == pytest.approx(148.59, abs=0.05)
    assert prov_r["value"] == pytest.approx(118.87, abs=0.05)
    assert prov_r["l3_dw"] is True
    assert reduced["display"]["f_min"] == "118.9 mm"
    text = format_f_min_provenance(prov_r, Translation())
    assert "148.6" in text and "118.9" in text and "Level 3" in text


def test_digital_exposure_methods_and_dda_frame_display(engine):
    # 1. DDA Frame Integration method displays (N×t_frame) and provenance
    res_dda = engine.calculate({
        "tech": "digital", "detector_type": "dda_si", "source": "x_ray",
        "chart_source": "dda_frame_method", "app_kv": 160.0, "output_val": 5.0,
        "od": 114.3, "t": 6.02, "sfd": 600.0, "app_srb": 100.0,
    }, {}, "tr")
    assert res_dda["values"]["exposure_time_provenance"]["method"] == "dda_frame_method"
    assert "×" in res_dda["display"]["calc_time"]
    assert "ASTM E2698" in res_dda["values"]["exposure_time_provenance_text"]

    # 2. CR IPS Chart (ISO 16371-1)
    res_cr = engine.calculate({
        "tech": "digital", "detector_type": "cr_standard", "source": "isotope_ir192",
        "chart_source": "cr_ips_chart", "output_val": 40.0,
        "od": 114.3, "t": 8.0, "sfd": 600.0, "app_srb": 100.0,
    }, {}, "tr")
    assert res_cr["values"]["exposure_time_provenance"]["method"] == "cr_ips_chart"
    assert "[ISO 16371-1 CR IP]" in res_cr["display"]["calc_time"]
    assert "ISO 16371-1" in res_cr["values"]["exposure_time_provenance_text"]

    # 3. Finer SRb requires higher dose (longer exposure time)
    res_srb_100 = engine.calculate({
        "tech": "digital", "detector_type": "cr_standard", "source": "x_ray",
        "chart_source": "model", "app_kv": 150.0, "output_val": 5.0,
        "od": 114.3, "t": 6.02, "sfd": 600.0, "app_srb": 100.0,
    })
    res_srb_50 = engine.calculate({
        "tech": "digital", "detector_type": "cr_standard", "source": "x_ray",
        "chart_source": "model", "app_kv": 150.0, "output_val": 5.0,
        "od": 114.3, "t": 6.02, "sfd": 600.0, "app_srb": 50.0,
    })
    assert res_srb_50["values"]["calc_time"] > res_srb_100["values"]["calc_time"]


def test_out_of_chart_film_inside_uses_conservative_cap(engine):
    """Regression: an operating point outside the Annex A chart returned N=1
    (film inside) / N=3 (film outside), grossly under-counting exposures. It
    must fall back to the chart cap and warn."""
    result = engine.calculate({
        "source": "x_ray", "tech": "analog", "geometry": "swsi",
        "std_figure": "fig2", "testing_class": "class_b",
        "od": 323.9, "t": 8.56, "sfd": 600.0, "f_source": 80.0,
        "app_kv": 120.0, "app_time": 1.0,
    })
    assert result["calculated"]["exposures_graph"] == 24
    prov = result["calculated"]["exposures_provenance"]
    assert prov["method"] == "out_of_chart"
    assert any("Annex A" in w for w in result["warnings"])


def test_zero_panel_width_is_flagged_not_exploded(engine):
    """Regression: panel_width=0 floored the coverage angle at 1e-6 and produced
    ~3.5 million required exposures."""
    result = engine.calculate({
        "tech": "digital", "geometry": "dwsi", "panel_width": 0.0,
        "t": 6.02, "od": 114.3, "sfd": 600.0, "app_kv": 150.0,
    }, {}, "en")
    assert result["calculated"]["exposures_graph"] < 100
    assert any("invalid" in w.lower() for w in result["warnings"]), result["warnings"]


@pytest.mark.parametrize("bad_kv", [0.0, -50.0])
def test_invalid_xray_kv_does_not_crash_and_warns(engine, bad_kv):
    """Regression: app_kv <= 0 divided by zero in the kVp^5 sanity check,
    crashing the shared engine (web showed stale results, mobile errored)."""
    result = engine.calculate({
        "source": "x_ray", "tech": "analog", "app_kv": bad_kv, "app_time": 1.0,
    })
    assert result["calculated"]["calc_time_raw"] > 0
    assert any("120" in w for w in result["warnings"]), result["warnings"]


def test_film_exposures_coverage_and_suggestions(engine):
    """Tests that film dimension coverage is computed, updates N_required when it
    exceeds the Annex A graph, provides optimization suggestions, and calculates
    total joint exposure time."""
    result = engine.calculate({
        "od": 323.9, "t": 8.0, "cap": 1.5, "tech": "analog", "geometry": "dwsi",
        "film_width": 80.0, "film_height": 120.0, "film_overlap": 10.0,
        "sfd": 600.0, "source": "x_ray", "app_kv": 120.0, "app_time": 60.0,
    }, {}, "tr")

    calc = result["calculated"]
    assert calc["exposures_film"] is not None
    assert calc["exposures_film"] >= 10  # 1017.56 / 110 = ~9.25 -> 10
    assert calc["required_exposures"] >= calc["exposures_film"]
    assert calc["total_joint_time_seconds"] == pytest.approx(
        calc["required_exposures"] * calc["calc_time_raw"], rel=1e-3
    )
    assert result["display"]["total_joint_time"]
    assert len(calc["suggestions"]["messages"]) > 0
    assert any("Kaset boyu" in s or "POZ OPTİMİZASYONU" in s for s in calc["suggestions"]["messages"])


def test_dynamic_film_overlap_in_engine(engine):
    """Verifies that user-entered overlap is dynamically taken into account
    when calculating film exposure count."""
    # 12" pipe (OD = 323.9 mm) -> C = ~1017.56 mm
    # 400 mm film with 10 mm overlap -> usable 390 -> 3 exposures
    res_10 = engine.calculate({
        "od": 323.9, "t": 8.0, "tech": "analog", "geometry": "dwsi",
        "film_width": 100.0, "film_height": 400.0, "app_overlap": 10.0,
    })
    assert res_10["calculated"]["exposures_film"] == 3
    assert res_10["calculated"]["film_overlap"] == 10.0

    # Increase overlap to 70 mm -> usable 330 -> 4 exposures
    res_70 = engine.calculate({
        "od": 323.9, "t": 8.0, "tech": "analog", "geometry": "dwsi",
        "film_width": 100.0, "film_height": 400.0, "app_overlap": 70.0,
    })
    assert res_70["calculated"]["exposures_film"] == 4
    assert res_70["calculated"]["film_overlap"] == 70.0

    # Increase overlap to 150 mm -> usable 250 -> 5 exposures
    res_150 = engine.calculate({
        "od": 323.9, "t": 8.0, "tech": "analog", "geometry": "dwsi",
        "film_width": 100.0, "film_height": 400.0, "app_overlap": 150.0,
    })
    assert res_150["calculated"]["exposures_film"] == 5
    assert res_150["calculated"]["film_overlap"] == 150.0


def test_analog_max_density_warning(engine):
    """Verifies that exceeding the 4.0 optical density limit generates a warning."""
    # Within limit (D = 2.5) -> No density warning
    res_ok = engine.calculate({
        "od": 323.9, "t": 8.0, "tech": "analog", "geometry": "dwsi",
        "app_quality": 2.5,
    })
    assert not any("optik yoğunluk" in w.lower() for w in res_ok["warnings"])

    # Exceeding limit (D = 4.4) -> Warning generated
    res_high = engine.calculate({
        "od": 323.9, "t": 8.0, "tech": "analog", "geometry": "dwsi",
        "app_quality": 4.4,
    })
    assert any("optik yoğunluk" in w.lower() and "4.00" in w for w in res_high["warnings"])


def test_dynamic_provenance_and_exceptions_info(engine):
    """Verifies that exceptions and compensations are dynamically formatted into provenance info."""
    # Scenario: 7.9 mm steel, DWSI, Class B, analog film, Ir-192 isotope, SFD < SFD_min
    res = engine.calculate({
        "od": 114.3, "t": 7.9, "cap": 2.5, "tech": "analog", "testing_class": "class_b",
        "geometry": "dwsi", "source": "isotope_ir192", "sfd": 100.0, "d": 2.0,
    }, {"dw_reduction": True, "sfd_comp": True}, "tr")

    v = res["values"]

    # 1. f_min dynamic provenance
    fmin_txt = v["f_min_provenance_text"]
    assert "Formül" in fmin_txt
    assert "Temel f_min" in fmin_txt
    assert "Level 3 Çift Duvar İndirimi" in fmin_txt
    assert "Geçerli f_min" in fmin_txt

    # 2. sfd_min dynamic provenance & distance compensation
    sfd_txt = v["sfd_min_provenance_text"]
    assert "Asgari Mesafe Adayları" in sfd_txt
    assert "f_min + b" in sfd_txt
    assert "DWSI fiziksel tabanı" in sfd_txt
    assert "Mesafe Telafisi (Level 3 Distance Compensation) AKTİF" in sfd_txt

    # 3. single_wire_iqi dynamic provenance (Clause 6.9 exception for Ir-192 with w=15.8mm)
    wire_txt = v["single_wire_iqi_provenance_text"]
    assert "ISO 17636-1 Tablo B.3" in wire_txt
    assert "w = 2·t" in wire_txt
    assert "Madde 6.9 İzotop İstisnası" in wire_txt
    assert "Ir-192" in wire_txt

    # 4. Se-75 Clause 6.9 exception (w < 12mm Class B optical density >= 3.0 & film upgrade)
    res_se75 = engine.calculate({
        "od": 88.9, "t": 5.0, "cap": 1.0, "tech": "analog", "testing_class": "class_b",
        "geometry": "dwsi", "source": "isotope_se75", "sfd": 600.0,
    }, {}, "tr")
    se75_qual_txt = res_se75["values"]["quality_target_provenance_text"]
    assert "Madde 6.9 İstisnası" in se75_qual_txt
    assert "D ≥ 3.0" in se75_qual_txt

    se75_det_txt = res_se75["values"]["detector_quality_provenance_text"]
    assert "Madde 6.9 İstisnası" in se75_det_txt
    assert "C3" in se75_det_txt

    # 5. Digital distance compensation & ug provenance
    res_dig = engine.calculate({
        "od": 114.3, "t": 6.0, "cap": 1.5, "tech": "digital", "testing_class": "class_b",
        "geometry": "dwsi", "source": "x_ray", "sfd": 400.0, "d": 2.0, "app_srb": 80.0,
    }, {"sfd_comp": True}, "tr")
    ug_txt = res_dig["values"]["ug_provenance_text"]
    assert "Formül: Ug = d · b / f" in ug_txt
    assert "Hesaplanan Değer: Ug =" in ug_txt


def test_dda_high_dose_rate_saturation_advisory(engine):
    # Thin section + high tube current -> t_frame_ideal < 0.08 s advises
    # reducing mA or increasing SFD (single-frame saturation risk).
    thin = engine.calculate({
        "tech": "digital", "detector_type": "dda_si", "source": "x_ray",
        "chart_source": "dda_frame_method", "app_kv": 100.0, "output_val": 30.0,
        "od": 60.3, "t": 1.0, "sfd": 400.0, "app_srb": 100.0, "material": "aluminum",
    }, {}, "tr")
    ideal = thin["values"]["exposure_time_provenance"]["dda_frame"]["t_frame_ideal"]
    assert ideal < 0.08
    assert any("doyum" in w for w in thin["warnings"])
    # Normal case stays silent (no false positive).
    normal = engine.calculate({
        "tech": "digital", "detector_type": "dda_si", "source": "x_ray",
        "chart_source": "dda_frame_method", "app_kv": 160.0, "output_val": 5.0,
        "od": 114.3, "t": 6.02, "sfd": 600.0, "app_srb": 100.0,
    }, {}, "en")
    assert not any("saturation" in w for w in normal["warnings"])
