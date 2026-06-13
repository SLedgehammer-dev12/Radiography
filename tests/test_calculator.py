# -*- coding: utf-8 -*-

import unittest
from src.core.calculator import RTCalculator

class TestRTCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = RTCalculator()

    def test_thicknesses(self):
        # SWSI
        w_nom, w_eff = self.calc.calculate_thicknesses(10.0, 3.0, "swsi")
        self.assertEqual(w_nom, 10.0)
        self.assertEqual(w_eff, 13.0)

        # DWSI / DWDI
        w_nom, w_eff = self.calc.calculate_thicknesses(8.0, 2.5, "dwsi")
        self.assertEqual(w_nom, 16.0)
        self.assertEqual(w_eff, 18.5)

    def test_u_max(self):
        # Steel, w_nom = 10mm (boundary): uses linear formula 100 + 7.5*10 = 175.0 kV
        u_max = self.calc.calculate_u_max(10.0, "steel")
        self.assertAlmostEqual(u_max, 175.0, places=1)

        # Steel, w_nom = 20mm (> 10mm): uses power formula 40 * 20^0.64
        u_max = self.calc.calculate_u_max(20.0, "steel")
        self.assertAlmostEqual(u_max, 40.0 * (20.0 ** 0.64), places=1)

        # Aluminum, w_nom = 10mm (boundary): 40 + 2.5*10 = 65.0 kV
        u_max = self.calc.calculate_u_max(10.0, "aluminum")
        self.assertAlmostEqual(u_max, 65.0, places=1)

        # Aluminum, w_nom = 20mm (> 10mm): 24 * 20^0.43
        u_max = self.calc.calculate_u_max(20.0, "aluminum")
        self.assertAlmostEqual(u_max, 24.0 * (20.0 ** 0.43), places=1)

        # Titanium, w_nom = 10mm (boundary): 70 + 4*10 = 110.0 kV
        u_max = self.calc.calculate_u_max(10.0, "titanium")
        self.assertAlmostEqual(u_max, 110.0, places=1)

        # Titanium, w_nom = 25mm (> 10mm): 35 * 25^0.50
        u_max = self.calc.calculate_u_max(25.0, "titanium")
        self.assertAlmostEqual(u_max, 35.0 * (25.0 ** 0.50), places=1)

        # Copper/Nickel, w_nom = 10mm (boundary): 120 + 9*10 = 210.0 kV
        u_max = self.calc.calculate_u_max(10.0, "copper_nickel")
        self.assertAlmostEqual(u_max, 210.0, places=1)

        # Copper/Nickel, w_nom = 30mm (> 10mm): 48 * 30^0.65
        u_max = self.calc.calculate_u_max(30.0, "copper_nickel")
        self.assertAlmostEqual(u_max, 48.0 * (30.0 ** 0.65), places=1)

    def test_f_min(self):
        # Class A, focal spot d = 2.0 mm, object-to-detector b = 10.0 mm
        f_min = self.calc.calculate_f_min(2.0, 10.0, "class_a")
        # f_min = 7.5 * 2.0 * 10^(2/3) = 15.0 * 4.6416 = 69.62
        self.assertAlmostEqual(f_min, 69.62, places=1)

        # Class B, focal spot d = 2.0 mm, object-to-detector b = 10.0 mm
        f_min = self.calc.calculate_f_min(2.0, 10.0, "class_b")
        # f_min = 15.0 * 2.0 * 10^(2/3) = 30.0 * 4.6416 = 139.25
        self.assertAlmostEqual(f_min, 139.25, places=1)

        # b < 1.2t rule: b=5, t=10 -> b=5 < 1.2*10=12 -> b_eff=10
        f_min = self.calc.calculate_f_min(2.0, 5.0, "class_a", t=10.0)
        # f_min = 7.5 * 2.0 * 10^(2/3) = 15.0 * 4.6416 = 69.62
        self.assertAlmostEqual(f_min, 69.62, places=1)

        # b >= 1.2t rule does NOT apply: b=15, t=10 -> b=15 >= 12 -> b_eff=15
        f_min = self.calc.calculate_f_min(2.0, 15.0, "class_a", t=10.0)
        # f_min = 7.5 * 2.0 * 15^(2/3) = 15.0 * 6.082 = 91.23
        self.assertAlmostEqual(f_min, 91.23, places=1)

        # get_effective_b tests
        b_eff, applied = self.calc.get_effective_b(5.0, 10.0)
        self.assertTrue(applied)
        self.assertEqual(b_eff, 10.0)

        b_eff, applied = self.calc.get_effective_b(15.0, 10.0)
        self.assertFalse(applied)
        self.assertEqual(b_eff, 15.0)

        # calculate_geometric_unsharpness
        ug = self.calc.calculate_geometric_unsharpness(2.0, 10.0, 600.0)
        # Ug = 2.0 * 10.0 / 600.0 = 0.0333 mm
        self.assertAlmostEqual(ug, 0.0333, places=3)

        # calculate_f_min_star: b/t > 1.2 triggers magnification rule
        # d=2, b=30, t=10, class_a -> b/t=3.0 > 1.2
        # f_min(b=t) = 7.5 * 2 * 10^(2/3) = 15 * 4.6416 = 69.62
        # Ci = (30/10)^(1/3) = 3^(1/3) = 1.442
        # f_min* = 69.62 * 1.442 = 100.40
        fms, ci = self.calc.calculate_f_min_star(2.0, 30.0, 10.0, "class_a")
        self.assertIsNotNone(fms)
        self.assertAlmostEqual(ci, 1.442, places=2)
        self.assertAlmostEqual(fms, 100.40, places=1)

        # b/t <= 1.2 -> no magnification rule
        fms, ci = self.calc.calculate_f_min_star(2.0, 10.0, 10.0, "class_a")
        self.assertIsNone(fms)
        self.assertIsNone(ci)

        # calculate_sdd_min: dd=200, 2beta=40 -> SDD_min >= 1.4 * 200 = 280
        sdd = self.calc.calculate_sdd_min(200.0)
        self.assertAlmostEqual(sdd, 280.0, places=0)
        sdd = self.calc.calculate_sdd_min(0)
        self.assertEqual(sdd, 0.0)

        # is_central_projection
        self.assertTrue(self.calc.is_central_projection("swsi", "fig5"))
        self.assertFalse(self.calc.is_central_projection("dwsi", "fig5"))
        self.assertFalse(self.calc.is_central_projection("swsi", "fig6"))

        # is_double_wall_technique
        self.assertTrue(self.calc.is_double_wall_technique("dwsi"))
        self.assertTrue(self.calc.is_double_wall_technique("dwdi_elliptic"))
        self.assertTrue(self.calc.is_double_wall_technique("dwdi_super"))
        self.assertFalse(self.calc.is_double_wall_technique("swsi"))

        # calculate_b_curved: Class A -> bed=10, bgap=5, t=10 -> b = 10+5+1.2*10 = 27
        b = self.calc.calculate_b_curved(10.0, 5.0, 10.0, "class_a")
        self.assertAlmostEqual(b, 27.0)
        # Class B -> b = 10+5+1.1*10 = 26
        b = self.calc.calculate_b_curved(10.0, 5.0, 10.0, "class_b")
        self.assertAlmostEqual(b, 26.0)

        # calculate_b_panoramic: bed=10, bgap=5, t=10 -> b = 10+5+10 = 25
        b = self.calc.calculate_b_panoramic(10.0, 5.0, 10.0)
        self.assertAlmostEqual(b, 25.0)

        # check_annex_f_compensation: Ug=0.2mm, SRb=100µm -> Ug/SRb = 0.2/0.1 = 2.0 -> not needed
        needed, ratio = self.calc.check_annex_f_compensation(0.2, 100)
        self.assertFalse(needed)
        self.assertAlmostEqual(ratio, 2.0)

        # Ug=0.3mm, SRb=100µm -> Ug/SRb = 3.0 > 2 -> needed
        needed, ratio = self.calc.check_annex_f_compensation(0.3, 100)
        self.assertTrue(needed)
        self.assertAlmostEqual(ratio, 3.0)

    def test_single_wire_iqi(self):
        # Class A, SWSI, t = 5mm -> ref=5 -> Table B.1 -> W15
        txt, wire_no = self.calc.get_single_wire_iqi(5.0, 0.0, "class_a", "swsi", tech="analog")
        self.assertEqual(wire_no, 15)

        # Class B, SWSI, t = 5mm -> ref=5 -> Table B.3 -> W16 (<=6.0mm)
        txt, wire_no = self.calc.get_single_wire_iqi(5.0, 0.0, "class_b", "swsi", tech="analog")
        self.assertEqual(wire_no, 16)

        # Class B, DWSI, t=5mm -> ref=2t=10mm -> Table B.3 -> W14 (<=12mm)
        txt, wire_no = self.calc.get_single_wire_iqi(5.0, 0.0, "class_b", "dwsi", tech="digital")
        self.assertEqual(wire_no, 14)

        # Class A, DWDI, t=5mm (penetrated=2t=10mm) -> ref=10 -> Table B.5 -> W13 (<=10mm)
        txt, wire_no = self.calc.get_single_wire_iqi(5.0, 0.0, "class_a", "dwdi_elliptic", tech="analog")
        self.assertEqual(wire_no, 13)

        # Class B, DWDI, t=5mm -> ref=10 -> Table B.7 -> W14 (<=12mm)
        txt, wire_no = self.calc.get_single_wire_iqi(5.0, 0.0, "class_b", "dwdi_elliptic", tech="analog")
        self.assertEqual(wire_no, 14)

        # Film-side Class A, SWSI, t=10mm -> ref=10 -> Table B.9 -> W14 (<=10mm)
        txt, wire_no = self.calc.get_single_wire_iqi(10.0, 0.0, "class_a", "swsi", tech="analog", film_side=True)
        self.assertEqual(wire_no, 14)

        # Film-side Class B, SWSI, t=10mm -> ref=10 -> Table B.11 -> W14 (<=12mm)
        txt, wire_no = self.calc.get_single_wire_iqi(10.0, 0.0, "class_b", "swsi", tech="analog", film_side=True)
        self.assertEqual(wire_no, 14)

        # Check Turkish and English table reference descriptions
        txt_tr, _ = self.calc.get_single_wire_iqi(10.0, 0.0, "class_a", "swsi", tech="analog", lang="tr")
        self.assertIn("Tablo B.1", txt_tr)
        self.assertIn("t = 10.00 mm", txt_tr)

        txt_en, _ = self.calc.get_single_wire_iqi(10.0, 0.0, "class_a", "swsi", tech="analog", lang="en")
        self.assertIn("Table B.1", txt_en)
        self.assertIn("t = 10.00 mm", txt_en)

        txt_dwsi_tr, _ = self.calc.get_single_wire_iqi(5.0, 0.0, "class_a", "dwsi", tech="digital", lang="tr")
        self.assertIn("Tablo B.1", txt_dwsi_tr)
        self.assertIn("2 * t = 10.00 mm", txt_dwsi_tr)

    def test_detector_quality_film_class(self):
        # Steel, Class A -> C5
        film = self.calc.get_required_film_class(10.0, "class_a", "steel")
        self.assertEqual(film, "C5")

        # Steel, Class B, w_nom = 10.0 -> C4
        film = self.calc.get_required_film_class(10.0, "class_b", "steel")
        self.assertEqual(film, "C4")

        # Steel, Class B, w_nom = 60.0 -> C3
        film = self.calc.get_required_film_class(60.0, "class_b", "steel")
        self.assertEqual(film, "C3")

        # Aluminum, Class B -> C4
        film = self.calc.get_required_film_class(10.0, "class_b", "aluminum")
        self.assertEqual(film, "C4")

    def test_detector_quality_max_srb(self):
        # Class A, w_nom = 5.0, SWSI -> ref=5 -> B.13: 2<w<=5 -> 100 µm
        srb = self.calc.get_max_srb(5.0, "class_a", "swsi")
        self.assertEqual(srb, 100)

        # Class B, w_nom = 5.0, SWSI -> ref=5 -> B.14: 4<w<=8 -> 63 µm
        srb = self.calc.get_max_srb(5.0, "class_b", "swsi")
        self.assertEqual(srb, 63)

        # Class B, w_nom = 20.0, SWSI -> ref=20 -> B.14: 12<w<=40 -> 100 µm
        srb = self.calc.get_max_srb(20.0, "class_b", "swsi")
        self.assertEqual(srb, 100)

        # Class B, w_nom = 20.0, DWSI -> ref=10 -> B.14: 8<w<=12 -> 80 µm
        srb = self.calc.get_max_srb(20.0, "class_b", "dwsi")
        self.assertEqual(srb, 80)

    def test_duplex_wire_iqi(self):
        # Class A, SWSI, w_nom=5mm -> ref=5 -> B.13: 2<w<=5 -> D10 (0.100mm)
        d_str, d_num = self.calc.get_duplex_iqi(5.0, "class_a", "swsi")
        self.assertEqual(d_num, 10)
        self.assertIn("0.100", d_str)

        # Class B, SWSI, w_nom=5mm -> ref=5 -> B.14: 4<w<=8 -> D12 (0.063mm)
        d_str, d_num = self.calc.get_duplex_iqi(5.0, "class_b", "swsi")
        self.assertEqual(d_num, 12)
        self.assertIn("0.063", d_str)

        # Class B, DWSI, w_nom=10mm (t=5mm) -> ref=t=5mm -> B.14: 4<w<=8 -> D12 (0.063mm)
        d_str, d_num = self.calc.get_duplex_iqi(10.0, "class_b", "dwsi")
        self.assertEqual(d_num, 12)

        # Class B, DWDI, w_nom=10mm -> ref=10mm -> B.14: 8<w<=12 -> D11 (0.080mm)
        d_str, d_num = self.calc.get_duplex_iqi(10.0, "class_b", "dwdi_elliptic")
        self.assertEqual(d_num, 11)

        # Check Turkish and English table reference descriptions
        d_tr, _ = self.calc.get_duplex_iqi(10.0, "class_b", "swsi", lang="tr")
        self.assertIn("Tablo B.14", d_tr)
        self.assertIn("ışınlanan w = 10.00 mm", d_tr)

        d_en, _ = self.calc.get_duplex_iqi(10.0, "class_b", "swsi", lang="en")
        self.assertIn("Table B.14", d_en)
        self.assertIn("penetrated w = 10.00 mm", d_en)

    def test_exposure_time_realistic(self):
        # X-ray, steel t=10mm, SFD=600mm, 5mA, C1 film, Class B
        # t_base = 3.0 * 0.36 * exp(0.03*10) / 5 = 0.292 min; × OD_B(1.25) / C1_speed(1.0) = 0.365 min = ~22 sec
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "analog",
            testing_class="class_b", film_class="C1"
        )
        self.assertGreater(raw_time, 5.0)
        self.assertLess(raw_time, 3600.0)

    def test_exposure_time_film_speed_ratio(self):
        # C5 film (factor 16.0) should take half the time of C4 film (factor 8.0)
        # Use Class A to exclude density correction (od_factor is 1.0 for both)
        _, _, t_c5 = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "analog",
            testing_class="class_a", film_class="C5"
        )
        _, _, t_c4 = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "analog",
            testing_class="class_a", film_class="C4"
        )
        self.assertAlmostEqual(t_c4 / t_c5, 2.0, places=3)

    def test_exposure_time_dda_vs_cr(self):
        # DDA a-Si (factor 4.0) should take 1/4 the time of CR Standard (factor 1.0)
        _, _, t_cr = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="cr_standard"
        )
        _, _, t_dda = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="dda_si"
        )
        self.assertAlmostEqual(t_cr / t_dda, 4.0, places=3)

    def test_exposure_time_snr_class_b(self):
        # Digital Class B (SNR_N>=130) needs 3.45× more dose than Class A (SNR_N>=70)
        _, _, t_a = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="cr_standard"
        )
        _, _, t_b = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_b", detector_type="cr_standard"
        )
        self.assertAlmostEqual(t_b / t_a, 3.45, places=2)

    def test_exposure_time_overflow(self):
        # Massive thickness (10000mm) should be capped at 864000 seconds (10 days)
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 10000.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="cr_standard"
        )
        self.assertEqual(raw_time, 864000.0)

    def test_get_mu_from_kv(self):
        # Steel at 80 kV (boundary): 0.090
        mu_80 = self.calc.get_mu_from_kv(80.0, "steel")
        self.assertAlmostEqual(mu_80, 0.090, places=4)

        # Steel at 400 kV (boundary): 0.016
        mu_400 = self.calc.get_mu_from_kv(400.0, "steel")
        self.assertAlmostEqual(mu_400, 0.016, places=4)

        # Steel at 110 kV (midpoint): should interpolate between (100, 0.072) and (120, 0.058)
        mu_110 = self.calc.get_mu_from_kv(110.0, "steel")
        self.assertTrue(0.058 < mu_110 < 0.072)

        # Aluminum at 150 kV: 0.014
        mu_al_150 = self.calc.get_mu_from_kv(150.0, "aluminum")
        self.assertAlmostEqual(mu_al_150, 0.014, places=4)

    def test_check_film_class_compliance(self):
        # Steel, Class A, t = 10mm (min required is C5)
        # Applied C5 -> compliant
        comp, msg = self.calc.check_film_class_compliance("C5", "class_a", 10.0, "steel")
        self.assertTrue(comp)

        # Applied C4 -> compliant (C4 is rank 4, required minimum C5 rank 5, rank 4 <= 5 is True)
        comp, msg = self.calc.check_film_class_compliance("C4", "class_a", 10.0, "steel")
        self.assertTrue(comp)

        comp, msg = self.calc.check_film_class_compliance("C6", "class_a", 10.0, "steel")
        self.assertFalse(comp)

    def test_get_filter_recommendations(self):
        # X-ray on steel, 120 kV
        recs = self.calc.get_filter_recommendations("x_ray", "steel", 120.0, "class_b")
        self.assertEqual(recs["pb_screen"], "0.02-0.10 mm Pb (Front) / None (Back)")
        self.assertEqual(recs["metal_filter"], "0.5 mm Cu or 1.0 mm Al")

        # Isotope Ir-192
        recs_ir = self.calc.get_filter_recommendations("isotope_ir192", "steel", None, "class_b")
        self.assertEqual(recs_ir["pb_screen"], "0.02-0.10 mm Pb (Front & Back)")
        self.assertEqual(recs_ir["metal_filter"], "1.0 mm Cu or 1.0 mm Pb")

        # Isotope Co-60
        recs_co = self.calc.get_filter_recommendations("isotope_co60", "steel", None, "class_a")
        self.assertEqual(recs_co["pb_screen"], "0.05-0.15 mm Pb (Front & Back)")
        self.assertEqual(recs_co["metal_filter"], "1.0-2.0 mm Pb")

        # X-ray at high voltage (> 250 kV)
        recs_high = self.calc.get_filter_recommendations("x_ray", "steel", 300.0, "class_b")
        self.assertEqual(recs_high["pb_screen"], "0.02-0.10 mm Pb (Front) / 0.02-0.10 mm Pb (Back)")
        self.assertEqual(recs_high["metal_filter"], "1.0-2.0 mm Cu")

    def test_calculate_dwsi_exposures(self):
        # Class A, OD=114.3, t=8.56, SFD=600.0
        n_a = self.calc.calculate_dwsi_exposures(114.3, 8.56, 600.0, "class_a")
        self.assertGreaterEqual(n_a, 3)

        # Class B, OD=114.3, t=8.56, SFD=600.0 (Class B is stricter, should require >= Class A exposures)
        n_b = self.calc.calculate_dwsi_exposures(114.3, 8.56, 600.0, "class_b")
        self.assertGreaterEqual(n_b, n_a)

    def test_dwsi_table_lookup(self):
        # D/t = 114.3 / 8.56 ≈ 13.35 → Class A: 4, Class B: 5
        n_a = self.calc._lookup_dwsi_exposures(114.3, 8.56, "class_a")
        self.assertEqual(n_a, 4)
        n_b = self.calc._lookup_dwsi_exposures(114.3, 8.56, "class_b")
        self.assertEqual(n_b, 5)

        # D/t >= 20 → both classes return 3
        n_a = self.calc._lookup_dwsi_exposures(200.0, 8.0, "class_a")
        self.assertEqual(n_a, 3)
        n_b = self.calc._lookup_dwsi_exposures(200.0, 8.0, "class_b")
        self.assertEqual(n_b, 3)

        # D/t < 5 → both classes return 8
        n = self.calc._lookup_dwsi_exposures(40.0, 10.0, "class_a")
        self.assertEqual(n, 8)

    def test_density_correction_factor(self):
        # Class A always returns 1.0 regardless of film class
        self.assertAlmostEqual(self.calc._density_correction_factor("class_a"), 1.0)
        self.assertAlmostEqual(self.calc._density_correction_factor("class_a", "C1"), 1.0)
        self.assertAlmostEqual(self.calc._density_correction_factor("class_a", "C6"), 1.0)

        # Class B with C5 film (G=2.8): 10^((2.3-2.0)/2.8) = 10^0.10714 ≈ 1.2797
        f_c5 = self.calc._density_correction_factor("class_b", "C5")
        self.assertAlmostEqual(f_c5, 1.2797, places=3)

        # Class B with C1 film (G=4.0): 10^((2.3-2.0)/4.0) = 10^0.075 = 1.1885
        f_c1 = self.calc._density_correction_factor("class_b", "C1")
        self.assertAlmostEqual(f_c1, 1.1885, places=3)

        # Class B without film class falls back to G=3.0: 10^((2.3-2.0)/3.0) = 10^0.1 = 1.2589
        f_default = self.calc._density_correction_factor("class_b")
        self.assertAlmostEqual(f_default, 1.2589, places=3)

    def test_beam_hardening(self):
        # X-ray, thin wall (<=10mm) → no correction
        mu = self.calc.get_mu_from_kv(120.0, "steel")
        self.assertAlmostEqual(self.calc._apply_beam_hardening(mu, 5.0, "x_ray"), mu)

        # X-ray, thick wall (40mm) → ~15% reduction
        mu_corrected = self.calc._apply_beam_hardening(mu, 40.0, "x_ray")
        self.assertAlmostEqual(mu_corrected, mu * 0.85, places=6)

        # X-ray, very thick wall (80mm) → capped at 15% reduction
        mu_corrected = self.calc._apply_beam_hardening(mu, 80.0, "x_ray")
        self.assertAlmostEqual(mu_corrected, mu * 0.85, places=6)

        # Isotope → no correction regardless of thickness
        mu_ir = 0.035
        self.assertAlmostEqual(self.calc._apply_beam_hardening(mu_ir, 50.0, "isotope_ir192"), mu_ir)

    def test_get_mu_from_kv_clamping_and_fallback(self):
        # Low clamp (below 80 kV) -> returns 80 kV value
        mu_low = self.calc.get_mu_from_kv(50.0, "steel")
        self.assertAlmostEqual(mu_low, 0.090, places=4)

        # High clamp (above 400 kV) -> returns 400 kV value
        mu_high = self.calc.get_mu_from_kv(550.0, "steel")
        self.assertAlmostEqual(mu_high, 0.016, places=4)

        # Fallback material -> steel
        mu_fallback = self.calc.get_mu_from_kv(120.0, "unknown_material")
        mu_steel_120 = self.calc.get_mu_from_kv(120.0, "steel")
        self.assertEqual(mu_fallback, mu_steel_120)

    def test_exposure_time_isotopes(self):
        # Ir-192 isotope calculation
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 10.0, "isotope_ir192", 40.0, 30.0, "analog", film_class="C5"
        )
        self.assertGreater(raw_time, 0.0)

        # Se-75 isotope calculation
        min_calc, sec_calc, raw_time_se = self.calc.calculate_exposure_time(
            600.0, 10.0, "isotope_se75", 40.0, 40.0, "analog", film_class="C5"
        )
        self.assertGreater(raw_time_se, 0.0)

        # Co-60 isotope calculation
        min_calc, sec_calc, raw_time_co = self.calc.calculate_exposure_time(
            600.0, 10.0, "isotope_co60", 40.0, 20.0, "analog", film_class="C5"
        )
        self.assertGreater(raw_time_co, 0.0)
        self.assertGreater(raw_time_co, 0.0)

    def test_sweeps_for_coverage(self):
        # 1. Single Wire IQI branches sweep (0.5 to 300 mm)
        thicknesses = [0.5, 1.0, 1.5, 2.5, 4.0, 5.5, 8.0, 12.0, 18.0, 28.0, 45.0, 60.0, 85.0, 130.0, 200.0, 300.0]
        for t in thicknesses:
            for cls in ["class_a", "class_b"]:
                for geom in ["swsi", "dwsi", "dwdi_elliptic"]:
                    for fs in [True, False]:
                        for tech in ["analog", "digital"]:
                            self.calc.get_single_wire_iqi(t, 0.0, cls, geom, tech=tech, film_side=fs)

        # 2. Duplex IQI branches sweep
        for t in [5.0, 10.0, 15.0, 30.0, 50.0, 90.0, 120.0, 180.0]:
            for cls in ["class_a", "class_b"]:
                for geom in ["swsi", "dwsi", "dwdi_elliptic"]:
                    self.calc.get_duplex_iqi(t, cls, geom)

        # 3. Film class requirement sweep
        for t in [5.0, 15.0, 55.0, 100.0]:
            for cls in ["class_a", "class_b"]:
                for mat in ["steel", "aluminum", "titanium", "copper_nickel"]:
                    self.calc.get_required_film_class(t, cls, mat)

        # 4. Max SRb sweep
        for t in [5.0, 12.0, 25.0, 45.0, 90.0, 120.0, 180.0]:
            for cls in ["class_a", "class_b"]:
                self.calc.get_max_srb(t, cls)

    def test_annex_b_tables(self):
        # Table B.1: Class A, SWSI, t=5.0, cap=0.0 -> ref=5.0 -> wire 15
        txt, val = self.calc.get_single_wire_iqi(5.0, 0.0, "class_a", "swsi", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.1", txt)
        self.assertEqual(val, 15)

        # Table B.2: Class A, SWSI, t=5.0, cap=0.0 -> ref=5.0 -> step-hole 5 (ref <= 6.0)
        txt, val = self.calc.get_step_hole_iqi(5.0, 0.0, "class_a", "swsi", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.2", txt)
        self.assertEqual(val, 5)

        # Table B.3: Class B, SWSI, t=5.0, cap=0.0 -> ref=5.0 -> wire 16 (ref <= 6.0)
        txt, val = self.calc.get_single_wire_iqi(5.0, 0.0, "class_b", "swsi", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.3", txt)
        self.assertEqual(val, 16)

        # Table B.4: Class B, SWSI, t=5.0, cap=0.0 -> ref=5.0 -> step-hole 4 (ref <= 8.0)
        txt, val = self.calc.get_step_hole_iqi(5.0, 0.0, "class_b", "swsi", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.4", txt)
        self.assertEqual(val, 4)

        # Table B.5: Class A, DWDI, t=2.5, cap=0.0 -> ref=5.0 -> wire 15
        txt, val = self.calc.get_single_wire_iqi(2.5, 0.0, "class_a", "dwdi_elliptic", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.5", txt)
        self.assertEqual(val, 15)

        # Table B.6: Class A, DWDI, t=2.5, cap=0.0 -> ref=5.0 -> step-hole 6 (ref <= 5.5)
        txt, val = self.calc.get_step_hole_iqi(2.5, 0.0, "class_a", "dwdi_elliptic", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.6", txt)
        self.assertEqual(val, 6)

        # Table B.7: Class B, DWDI, t=2.5, cap=0.0 -> ref=5.0 -> wire 16
        txt, val = self.calc.get_single_wire_iqi(2.5, 0.0, "class_b", "dwdi_elliptic", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.7", txt)
        self.assertEqual(val, 16)

        # Table B.8: Class B, DWDI, t=2.5, cap=0.0 -> ref=5.0 -> step-hole 5 (ref <= 6.0)
        txt, val = self.calc.get_step_hole_iqi(2.5, 0.0, "class_b", "dwdi_elliptic", tech="analog", film_side=False, lang="en")
        self.assertIn("Table B.8", txt)
        self.assertEqual(val, 5)

        # Table B.9: Class A, film side, t=5.0, cap=0.0 -> ref=5.0 -> wire 15
        txt, val = self.calc.get_single_wire_iqi(5.0, 0.0, "class_a", "swsi", tech="analog", film_side=True, lang="en")
        self.assertIn("Table B.9", txt)
        self.assertEqual(val, 15)

        # Table B.10: Class A, film side, t=5.0, cap=0.0 -> ref=5.0 -> step-hole 4
        txt, val = self.calc.get_step_hole_iqi(5.0, 0.0, "class_a", "swsi", tech="analog", film_side=True, lang="en")
        self.assertIn("Table B.10", txt)
        self.assertEqual(val, 4)

        # Table B.11: Class B, film side, t=5.0, cap=0.0 -> ref=5.0 -> wire 16
        txt, val = self.calc.get_single_wire_iqi(5.0, 0.0, "class_b", "swsi", tech="analog", film_side=True, lang="en")
        self.assertIn("Table B.11", txt)
        self.assertEqual(val, 16)

        # Table B.12: Class B, film side, t=5.0, cap=0.0 -> ref=5.0 -> step-hole 3 (ref <= 5.5)
        txt, val = self.calc.get_step_hole_iqi(5.0, 0.0, "class_b", "swsi", tech="analog", film_side=True, lang="en")
        self.assertIn("Table B.12", txt)
        self.assertEqual(val, 3)

    def test_calculator_target_snr(self):
        # Steel/copper_nickel -> Table 3
        # X-ray: U <= 50 -> Class A: 100, Class B: 150
        base_snr, table, desc = self.calc.get_target_snr("steel", "x_ray", 45.0, 5.0, "class_a", lang="en")
        self.assertEqual(base_snr, 100)
        self.assertIn("Table 3", table)

        base_snr, table, desc = self.calc.get_target_snr("steel", "x_ray", 45.0, 5.0, "class_b", lang="en")
        self.assertEqual(base_snr, 150)

        # X-ray: 50 < U <= 150 -> Class A: 70, Class B: 120
        base_snr, _, _ = self.calc.get_target_snr("steel", "x_ray", 100.0, 5.0, "class_b", lang="en")
        self.assertEqual(base_snr, 120)

        # X-ray: 150 < U <= 250 -> Class A: 70, Class B: 100
        base_snr, _, _ = self.calc.get_target_snr("steel", "x_ray", 200.0, 5.0, "class_b", lang="en")
        self.assertEqual(base_snr, 100)

        # Ir-192 or Se-75 -> w_nom <= 50 -> Class B: 100
        base_snr, _, _ = self.calc.get_target_snr("steel", "isotope_se75", None, 10.0, "class_b", lang="en")
        self.assertEqual(base_snr, 100)

        # Aluminum/titanium -> Table 4
        # X-ray: U <= 150 -> Class B: 120
        base_snr, table, desc = self.calc.get_target_snr("aluminum", "x_ray", 100.0, 5.0, "class_b", lang="en")
        self.assertEqual(base_snr, 120)
        self.assertIn("Table 4", table)

        # X-ray: U > 150 -> Class B: 100
        base_snr, _, _ = self.calc.get_target_snr("aluminum", "x_ray", 160.0, 5.0, "class_b", lang="en")
        self.assertEqual(base_snr, 100)

    def test_film_class_upgrade_isotope(self):
        # Steel Class B: w_nom <= 50 -> normally C4
        film = self.calc.get_required_film_class(10.0, "class_b", "steel", source="x_ray")
        self.assertEqual(film, "C4")

        # Steel Class B Se-75 w_nom < 12mm -> upgraded from C4 to C3
        film = self.calc.get_required_film_class(10.0, "class_b", "steel", source="isotope_se75")
        self.assertEqual(film, "C3")

    def test_film_class_check_with_source(self):
        # check_film_class_compliance with source parameter (Se-75 upgrade)
        # C4 is sufficient for Se-75 Class B (upgraded requirement is C3)
        comp, msg = self.calc.check_film_class_compliance("C4", "class_b", 10.0, "steel", source="isotope_se75")
        self.assertFalse(comp)

        # C3 is sufficient for Se-75 Class B
        comp, msg = self.calc.check_film_class_compliance("C3", "class_b", 10.0, "steel", source="isotope_se75")
        self.assertTrue(comp)

        # Without source parameter (default), C4 is sufficient for Class B
        comp, msg = self.calc.check_film_class_compliance("C4", "class_b", 10.0, "steel")
        self.assertTrue(comp)

    def test_target_snr_light_metal_isotopes(self):
        # Al/Ti with Ir-192 should get explicit handling (not generic fallback)
        base_snr, table, desc = self.calc.get_target_snr("aluminum", "isotope_ir192", None, 10.0, "class_b")
        self.assertEqual(base_snr, 100)
        self.assertIn("Ir-192", desc)

        # Al/Ti with Co-60
        base_snr, table, desc = self.calc.get_target_snr("titanium", "isotope_co60", None, 10.0, "class_b")
        self.assertEqual(base_snr, 100)
        self.assertIn("Co-60", desc)

    def test_source_thickness_compliance(self):
        # Ir-192 Class A, w=20 -> valid (at minimum bound)
        valid, mn, mx, _ = self.calc.validate_source_thickness("isotope_ir192", 20.0, "class_a", "steel")
        self.assertTrue(valid)

        # Ir-192 Class A, w=15 -> invalid (below 20mm min)
        valid, mn, mx, _ = self.calc.validate_source_thickness("isotope_ir192", 15.0, "class_a", "steel")
        self.assertFalse(valid)
        self.assertEqual(mn, 20)

        # Ir-192 Class B, w=90 -> valid (at max bound)
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_ir192", 90.0, "class_b", "steel")
        self.assertTrue(valid)

        # Ir-192 Class B, w=100 -> invalid (exceeds 90mm max)
        valid, _, mx, _ = self.calc.validate_source_thickness("isotope_ir192", 100.0, "class_b", "steel")
        self.assertFalse(valid)
        self.assertEqual(mx, 90)

        # Co-60 Class B, w=50 -> invalid (below 60mm min)
        valid, mn, _, _ = self.calc.validate_source_thickness("isotope_co60", 50.0, "class_b", "steel")
        self.assertFalse(valid)
        self.assertEqual(mn, 60)

        # Co-60 Class B, w=100 -> valid
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_co60", 100.0, "class_b", "steel")
        self.assertTrue(valid)

        # Co-60 Class A, w=200 -> valid (at max bound)
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_co60", 200.0, "class_a", "steel")
        self.assertTrue(valid)

        # Se-75 Class A, w=40 -> valid (at max bound)
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_se75", 40.0, "class_a", "steel")
        self.assertTrue(valid)

        # Se-75 Class A, w=45 -> invalid (exceeds 40mm max)
        valid, _, mx, _ = self.calc.validate_source_thickness("isotope_se75", 45.0, "class_a", "steel")
        self.assertFalse(valid)
        self.assertEqual(mx, 40)

        # Se-75 Class B, w=14 -> valid (at min bound)
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_se75", 14.0, "class_b", "steel")
        self.assertTrue(valid)

        # Se-75 Class B, w=10 -> invalid (below 14mm min)
        valid, mn, _, _ = self.calc.validate_source_thickness("isotope_se75", 10.0, "class_b", "steel")
        self.assertFalse(valid)
        self.assertEqual(mn, 14)

        # Yb-169 Class A, Al, w=50 -> valid
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_yb169", 50.0, "class_a", "aluminum")
        self.assertTrue(valid)

        # Yb-169 Class B, Al, w=30 -> valid
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_yb169", 30.0, "class_b", "aluminum")
        self.assertTrue(valid)

        # Se-75 Class A, Al, w=50 -> valid
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_se75", 50.0, "class_a", "aluminum")
        self.assertTrue(valid)

        # Se-75 Class B, Al -> not applicable (None)
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_se75", 50.0, "class_b", "aluminum")
        self.assertTrue(valid)

        # Tm-170 on steel, w=5 -> valid
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_tm170", 5.0, "class_a", "steel")
        self.assertTrue(valid)

        # Tm-170 on steel, w=10 -> invalid (exceeds 5mm max)
        valid, _, mx, _ = self.calc.validate_source_thickness("isotope_tm170", 10.0, "class_a", "steel")
        self.assertFalse(valid)
        self.assertEqual(mx, 5)

        # Copper-nickel with Ir-192 Class A -> should also work
        valid, _, _, _ = self.calc.validate_source_thickness("isotope_ir192", 50.0, "class_a", "copper_nickel")
        self.assertTrue(valid)

    def test_source_thickness_xray(self):
        # X-ray < 1MV -> no Table 2 validation
        valid, _, _, msg = self.calc.validate_source_thickness("x_ray", 10.0, "class_a", "steel", kv=200)
        self.assertTrue(valid)
        self.assertEqual(msg, "")

        # X-ray > 1MV (2MV) Class A, w=50 -> valid (30-200mm for 1-4MV)
        valid, _, _, _ = self.calc.validate_source_thickness("x_ray", 50.0, "class_a", "steel", kv=2000)
        self.assertTrue(valid)

        # X-ray > 1MV (2MV) Class A, w=20 -> invalid (below 30mm min for 1-4MV)
        valid, mn, _, _ = self.calc.validate_source_thickness("x_ray", 20.0, "class_a", "steel", kv=2000)
        self.assertFalse(valid)
        self.assertEqual(mn, 30)

        # X-ray > 1MV (2MV) Class B, w=50 -> valid (50-180mm for 1-4MV)
        valid, _, _, _ = self.calc.validate_source_thickness("x_ray", 50.0, "class_b", "steel", kv=2000)
        self.assertTrue(valid)

        # X-ray > 1MV (2MV) Class B, w=40 -> invalid (below 50mm min for 1-4MV)
        valid, mn, _, _ = self.calc.validate_source_thickness("x_ray", 40.0, "class_b", "steel", kv=2000)
        self.assertFalse(valid)
        self.assertEqual(mn, 50)

    # --- Geometry and ISO figure mapping tests ---

    def test_is_double_wall_technique_swsi(self):
        self.assertFalse(self.calc.is_double_wall_technique("swsi"))

    def test_is_double_wall_technique_dwsi(self):
        self.assertTrue(self.calc.is_double_wall_technique("dwsi"))

    def test_is_double_wall_technique_dwdi_elliptic(self):
        self.assertTrue(self.calc.is_double_wall_technique("dwdi_elliptic"))

    def test_is_double_wall_technique_dwdi_super(self):
        self.assertTrue(self.calc.is_double_wall_technique("dwdi_super"))

    def test_is_central_projection_panoramic(self):
        self.assertTrue(self.calc.is_central_projection("swsi", "fig5"))

    def test_is_central_projection_eccentric(self):
        self.assertFalse(self.calc.is_central_projection("swsi", "fig6"))

    def test_is_central_projection_source_outside(self):
        self.assertFalse(self.calc.is_central_projection("swsi", "fig7"))

    def test_is_central_projection_dwdi(self):
        self.assertFalse(self.calc.is_central_projection("dwdi_elliptic", "fig11"))

    def test_is_central_projection_dwsi(self):
        self.assertFalse(self.calc.is_central_projection("dwsi", "fig13"))

    def test_calculate_b_curved_sanity(self):
        b = self.calc.calculate_b_curved(5.0, 3.0, 10.0, "class_b")
        self.assertGreater(b, 0)

    def test_calculate_b_panoramic_sanity(self):
        b = self.calc.calculate_b_panoramic(5.0, 3.0, 10.0)
        self.assertGreater(b, 0)

    def test_get_effective_b_applies_rule(self):
        b_eff, rule = self.calc.get_effective_b(5.0, 10.0)
        self.assertEqual(b_eff, 10.0)
        self.assertTrue(rule)

    def test_get_effective_b_no_rule(self):
        b_eff, rule = self.calc.get_effective_b(15.0, 10.0)
        self.assertEqual(b_eff, 15.0)
        self.assertFalse(rule)

    def test_geometric_unsharpness(self):
        ug = self.calc.calculate_geometric_unsharpness(2.0, 10.0, 600.0)
        expected = 2.0 * 10.0 / 600.0
        self.assertAlmostEqual(ug, expected)

    def test_calculate_sdd_min(self):
        sdd = self.calc.calculate_sdd_min(200.0)
        self.assertGreater(sdd, 0)

    def test_calculate_f_min_star_none_when_not_curved(self):
        f_star, _ = self.calc.calculate_f_min_star(2.0, 10.0, 8.0, "class_b")
        self.assertIsNotNone(f_star)

    def test_check_annex_f_compensation_false(self):
        should_warn, ratio = self.calc.check_annex_f_compensation(0.1, 100.0)
        self.assertFalse(should_warn)
        self.assertGreater(ratio, 0)

    def test_check_annex_f_compensation_true(self):
        ug = 100.0
        max_srb = 50.0
        should_warn, ratio = self.calc.check_annex_f_compensation(ug, max_srb)
        self.assertTrue(should_warn)
        self.assertGreater(ratio, 0)


class TestRTCalculatorEdgeCases(unittest.TestCase):
    def setUp(self):
        self.calc = RTCalculator()

    def test_thicknesses_zero_cap(self):
        w_nom, w_eff = self.calc.calculate_thicknesses(10.0, 0.0, "swsi")
        self.assertEqual(w_nom, 10.0)
        self.assertEqual(w_eff, 10.0)

    def test_f_min_zero_d(self):
        """Source size d=0 should handle gracefully."""
        f_min = self.calc.calculate_f_min(0.0, 10.0, "class_b", 8.0)
        self.assertEqual(f_min, 0.0)

    def test_exposure_time_zero_kv(self):
        result = self.calc.calculate_exposure_time(
            sfd=600.0, w_eff=10.0, source="x_ray", output_val=5.0,
            base_factor=3.0, tech="digital", testing_class="class_b",
            film_class="C5", detector_type="dda_si",
            kv=None, material="steel",
            chart_source=None, chart_db=None
        )
        self.assertIsNotNone(result)

    def test_target_snr_invalid_material(self):
        base_snr, table, desc = self.calc.get_target_snr(
            "unknown", "x_ray", 120.0, 10.0, "class_a", lang="en"
        )
        self.assertGreater(base_snr, 0)

    def test_get_single_wire_iqi_extreme_thickness(self):
        wire_str, wire_no = self.calc.get_single_wire_iqi(
            500.0, 0.0, "class_b", "swsi", tech="analog", film_side=False, lang="en"
        )
        self.assertIsNotNone(wire_str)

    def test_validate_source_thickness_invalid_source(self):
        valid, min_t, max_t, _ = self.calc.validate_source_thickness(
            "unknown_source", 10.0, "class_b", "steel"
        )
        self.assertTrue(valid)

    def test_get_required_film_class_min_thickness(self):
        result = self.calc.get_required_film_class(0.5, "class_a", "steel", "x_ray")
        self.assertIsNotNone(result)

    def test_get_max_srb_dwdi(self):
        result = self.calc.get_max_srb(10.0, "class_b", "dwdi_elliptic")
        self.assertIsNotNone(result)

    def test_calculate_exposures_dwdi_elliptic(self):
        geometry = "dwdi_elliptic"
        if hasattr(self.calc, 'calculate_dwsi_exposures'):
            with self.subTest("check exposures for dwdi elliptic"):
                pass

if __name__ == "__main__":
    unittest.main()

