# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from src.core.exposure_charts import ExposureChartDatabase
from src.core.calculator import RTCalculator

TMP = tempfile.gettempdir()


class TestExposureChartDatabase(unittest.TestCase):
    def setUp(self):
        self.db = ExposureChartDatabase()

    def test_lookup_r_factor(self):
        r = self.db.lookup_r_factor("AA400", "isotope_ir192")
        self.assertAlmostEqual(r, 0.46, places=2)

        r = self.db.lookup_r_factor("AA400", "isotope_co60")
        self.assertAlmostEqual(r, 0.13, places=2)

        r = self.db.lookup_r_factor("MX125", "isotope_se75")
        self.assertAlmostEqual(r, 0.23, places=2)

        r = self.db.lookup_r_factor("AA400", "isotope_tm170")
        self.assertAlmostEqual(r, 0.12, places=2)

        r = self.db.lookup_r_factor("M100", "isotope_yb169")
        self.assertAlmostEqual(r, 0.12, places=2)

        r = self.db.lookup_r_factor("MX125", "isotope_co60")
        self.assertAlmostEqual(r, 0.08, places=2)

    def test_lookup_missing(self):
        r = self.db.lookup_r_factor("AA400", "x_ray")
        self.assertIsNone(r)

        r = self.db.lookup_r_factor("UNKNOWN", "isotope_ir192")
        self.assertIsNone(r)

    def test_shipped_json_load_preserves_yb_tm_constants(self):
        # The shipped JSON only lists Ir-192 / Se-75 / Co-60; loading it must
        # not drop the built-in Yb-169 / Tm-170 HVL/gamma. Regression: the
        # digital R-factor path silently fell back to Ir-192 constants and was
        # up to ~9600x short for Tm-170.
        path = os.path.join(os.path.dirname(__file__), "..", "exposure_chart_dataset.json")
        db = ExposureChartDatabase(path)
        for src in ("isotope_yb169", "isotope_tm170"):
            self.assertIn(src, db.HVL)
            self.assertIn(src, db.GAMMA)

        ref = ExposureChartDatabase()  # built-in constants
        for src in ("isotope_yb169", "isotope_tm170"):
            t_loaded = db.calculate_exposure_time_digital_rfactor(
                700, 10, src, 40, "cr_standard", 70)
            t_ref = ref.calculate_exposure_time_digital_rfactor(
                700, 10, src, 40, "cr_standard", 70)
            self.assertIsNotNone(t_loaded)
            self.assertAlmostEqual(t_loaded, t_ref, places=6)
        # Tm-170 correct exposure is ~995 min, not the buggy ~0.1 min.
        self.assertGreater(db.calculate_exposure_time_digital_rfactor(
            700, 10, "isotope_tm170", 40, "cr_standard", 70), 100.0)

    def test_get_available_films(self):
        films = self.db.get_available_films()
        self.assertIn("AA400", films)
        self.assertIn("MX125", films)
        self.assertIn("T200", films)
        self.assertIn("HS800", films)
        self.assertIn("M100", films)

    def test_get_available_sources_for_film(self):
        sources = self.db.get_available_sources_for_film("AA400")
        self.assertIn("isotope_ir192", sources)
        self.assertIn("isotope_se75", sources)
        self.assertIn("isotope_co60", sources)
        self.assertIn("isotope_yb169", sources)
        self.assertIn("isotope_tm170", sources)
        self.assertNotIn("x_ray", sources)

        sources_m100 = self.db.get_available_sources_for_film("M100")
        self.assertIn("isotope_ir192", sources_m100)
        self.assertIn("isotope_se75", sources_m100)
        self.assertIn("isotope_co60", sources_m100)
        self.assertIn("isotope_yb169", sources_m100)
        self.assertIn("isotope_tm170", sources_m100)
        self.assertNotIn("x_ray", sources_m100)

    def test_calculate_exposure_time_rfactor_ir192(self):
        t_min = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=20.0, source="isotope_ir192",
            activity=40.0, film_key="AA400", density=2.0
        )
        self.assertIsNotNone(t_min)
        self.assertGreater(t_min, 0)

    def test_calculate_exposure_time_rfactor_density_correction(self):
        t_d20 = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=20.0, source="isotope_ir192",
            activity=40.0, film_key="AA400", density=2.0
        )
        t_d30 = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=20.0, source="isotope_ir192",
            activity=40.0, film_key="AA400", density=3.0
        )
        expected_ratio = 10 ** ((3.0 - 2.0) / 2.0)
        self.assertAlmostEqual(t_d30 / t_d20, expected_ratio, places=2)

    def test_calculate_exposure_time_rfactor_sfd_scaling(self):
        t_600 = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=20.0, source="isotope_ir192",
            activity=40.0, film_key="AA400", density=2.0
        )
        t_1200 = self.db.calculate_exposure_time_rfactor(
            sfd=1200.0, w=20.0, source="isotope_ir192",
            activity=40.0, film_key="AA400", density=2.0
        )
        expected_ratio = (1200.0 / 600.0) ** 2
        self.assertAlmostEqual(t_1200 / t_600, expected_ratio, places=2)

    def test_calculate_exposure_time_rfactor_missing_film(self):
        t_min = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=20.0, source="isotope_ir192",
            activity=40.0, film_key="UNKNOWN", density=2.0
        )
        self.assertIsNone(t_min)

    def test_calculate_exposure_time_rfactor_missing_source(self):
        t_min = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=20.0, source="x_ray",
            activity=40.0, film_key="AA400", density=2.0
        )
        self.assertIsNone(t_min)

    def test_calculate_exposure_time_rfactor_tm170_and_yb169(self):
        t_tm = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=5.0, source="isotope_tm170",
            activity=10.0, film_key="AA400", density=2.0
        )
        self.assertIsNotNone(t_tm)
        self.assertGreater(t_tm, 0)

        t_yb = self.db.calculate_exposure_time_rfactor(
            sfd=600.0, w=10.0, source="isotope_yb169",
            activity=20.0, film_key="MX125", density=2.0
        )
        self.assertIsNotNone(t_yb)
        self.assertGreater(t_yb, 0)

    def test_hvl_constants(self):
        self.assertAlmostEqual(self.db.HVL["isotope_ir192"], 13.2, places=1)
        self.assertAlmostEqual(self.db.HVL["isotope_co60"], 21.0, places=1)
        self.assertAlmostEqual(self.db.HVL["isotope_se75"], 10.3, places=1)

    def test_gamma_constants(self):
        self.assertAlmostEqual(self.db.GAMMA["isotope_ir192"], 0.48, places=2)
        self.assertAlmostEqual(self.db.GAMMA["isotope_co60"], 1.30, places=2)
        self.assertAlmostEqual(self.db.GAMMA["isotope_se75"], 0.20, places=2)


class TestExposureChartCSVJSON(unittest.TestCase):
    def setUp(self):
        self.db = ExposureChartDatabase()
        self.calc = RTCalculator()
        self.db.generate_type_x_chart(self.calc)

    def tearDown(self):
        for f in [TMP + "/test_chart.csv", TMP + "/test_chart.json"]:
            if os.path.exists(f):
                os.remove(f)

    def test_save_and_load_csv(self):
        csv_path = TMP + "/test_chart.csv"
        self.db.save_to_csv(csv_path)
        self.assertTrue(os.path.exists(csv_path))

        db2 = ExposureChartDatabase()
        db2.R_FACTOR_TABLE.clear()
        db2.HVL.clear()
        db2.GAMMA.clear()
        db2.load_from_csv(csv_path)

        self.assertAlmostEqual(db2.lookup_r_factor("AA400", "isotope_ir192"), 0.46, places=2)
        self.assertAlmostEqual(db2.HVL["isotope_ir192"], 13.2, places=1)
        self.assertAlmostEqual(db2.GAMMA["isotope_co60"], 1.30, places=2)

    def test_save_and_load_json(self):
        json_path = TMP + "/test_chart.json"
        self.db.save_to_json(json_path)
        self.assertTrue(os.path.exists(json_path))

        db2 = ExposureChartDatabase()
        db2.load_from_json(json_path)

        self.assertAlmostEqual(db2.lookup_r_factor("AA400", "isotope_ir192"), 0.46, places=2)
        self.assertAlmostEqual(db2.HVL["isotope_ir192"], 13.2, places=1)
        self.assertAlmostEqual(db2.GAMMA["isotope_co60"], 1.30, places=2)

        exp = db2.get_type_x_exposure(200, 20)
        self.assertIsNotNone(exp)
        self.assertGreater(exp, 0)

    def test_csv_roundtrip_rfactor(self):
        csv_path = TMP + "/test_chart.csv"
        self.db.save_to_csv(csv_path)

        db2 = ExposureChartDatabase()
        db2.R_FACTOR_TABLE.clear()
        db2.load_from_csv(csv_path)

        for film in self.db.get_available_films():
            for source in self.db.get_available_sources_for_film(film):
                r1 = self.db.lookup_r_factor(film, source)
                r2 = db2.lookup_r_factor(film, source)
                self.assertAlmostEqual(r1, r2, places=4)

    def test_json_roundtrip_type_x(self):
        json_path = TMP + "/test_chart.json"
        self.db.save_to_json(json_path)

        db2 = ExposureChartDatabase()
        db2.load_from_json(json_path)

        for kv in [80, 200, 350]:
            for t_mm in [5, 20, 50]:
                e1 = self.db.get_type_x_exposure(kv, t_mm)
                e2 = db2.get_type_x_exposure(kv, t_mm)
                self.assertAlmostEqual(e1, e2, places=6)

    def test_load_csv_missing_file(self):
        db2 = ExposureChartDatabase()
        with self.assertRaises(FileNotFoundError):
            db2.load_from_csv(TMP + "/nonexistent.csv")

    def test_load_json_missing_file(self):
        db2 = ExposureChartDatabase()
        with self.assertRaises(FileNotFoundError):
            db2.load_from_json(TMP + "/nonexistent.json")


class TestExposureChartDatabaseTypeX(unittest.TestCase):
    def setUp(self):
        self.db = ExposureChartDatabase()
        self.calc = RTCalculator()

    def test_generate_type_x_chart(self):
        self.db.generate_type_x_chart(self.calc)
        self.assertTrue(len(self.db.TYPE_X_CHART) > 0)
        for kv in [80, 200, 350]:
            self.assertIn(kv, self.db.TYPE_X_CHART)
            kv_data = self.db.TYPE_X_CHART[kv]
            self.assertTrue(len(kv_data) > 0)
            for t in [5, 20, 50]:
                self.assertIn(t, kv_data)
                self.assertGreater(kv_data[t], 0)

    def test_get_type_x_exposure(self):
        self.db.generate_type_x_chart(self.calc)
        exp = self.db.get_type_x_exposure(200, 20)
        self.assertIsNotNone(exp)
        self.assertGreater(exp, 0)

    def test_get_type_x_exposure_empty(self):
        exp = self.db.get_type_x_exposure(200, 20)
        self.assertIsNone(exp)

    def test_set_type_x_data(self):
        test_data = {150: {10: 50.0, 20: 200.0}}
        self.db.set_type_x_data(test_data)
        self.assertEqual(self.db.TYPE_X_CHART, test_data)
        exp = self.db.get_type_x_exposure(150, 10)
        self.assertAlmostEqual(exp, 50.0)
        self.db.TYPE_X_CHART = {}


class TestRTCalculatorWithCharts(unittest.TestCase):
    def setUp(self):
        self.calc = RTCalculator()
        self.db = ExposureChartDatabase()
        self.db.generate_type_x_chart(self.calc)

    def test_chart_source_rfactor(self):
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog",
            film_class="C5", chart_source="AA400", chart_db=self.db
        )
        self.assertGreater(raw_time, 0)

    def test_chart_source_type_x(self):
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            700.0, 20.0, "x_ray", 5.0, 3.0, "analog",
            film_class="C5", kv=200, chart_source="type_x", chart_db=self.db
        )
        self.assertGreater(raw_time, 0)

    def test_chart_source_fallback_on_missing(self):
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 20.0, "x_ray", 5.0, 3.0, "analog",
            film_class="C5", chart_source="AA400", chart_db=self.db
        )
        # AA400 + x_ray not in R-Factor table → falls back to physics model
        self.assertGreater(raw_time, 0)

    def test_chart_source_none_backward_compat(self):
        m1, s1, t1 = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "analog",
            testing_class="class_b", film_class="C1"
        )
        m2, s2, t2 = self.calc.calculate_exposure_time(
            600.0, 10.0, "x_ray", 5.0, 3.0, "analog",
            testing_class="class_b", film_class="C1",
            chart_source=None
        )
        self.assertEqual(m1, m2)
        self.assertEqual(t1, t2)

    def test_chart_source_rfactor_se75(self):
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 20.0, "isotope_se75", 40.0, 40.0, "analog",
            film_class="C5", chart_source="AA400", chart_db=self.db
        )
        self.assertGreater(raw_time, 0)

    def test_chart_source_rfactor_with_film_model(self):
        min_calc, sec_calc, raw_time = self.calc.calculate_exposure_time(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog",
            film_class="C5", chart_source="rfactor",
            film_model="AA400", chart_db=self.db
        )
        self.assertGreater(raw_time, 0)

    def test_rfactor_film_speed_monotonicity(self):
        """Slower films (M100, MX125, T200) must require longer exposure than faster films (AA400, HS800)."""
        times = {}
        for film in ["M100", "MX125", "T200", "AA400", "HS800"]:
            t_min = self.db.calculate_exposure_time_rfactor(
                sfd=600.0, w=20.0, source="isotope_ir192", activity=40.0,
                film_key=film, density=2.0
            )
            self.assertIsNotNone(t_min)
            times[film] = t_min
        self.assertGreater(times["M100"], times["MX125"])
        self.assertGreater(times["MX125"], times["T200"])
        self.assertGreater(times["T200"], times["AA400"])
        self.assertGreater(times["AA400"], times["HS800"])

    def test_type_x_2d_log_interpolation(self):
        """Non-grid (kv, thickness) should smoothly log-interpolate between grid points."""
        e_180_15 = self.db.get_type_x_exposure(180, 15)
        e_200_15 = self.db.get_type_x_exposure(200, 15)
        e_190_15 = self.db.get_type_x_exposure(190, 15)
        # Higher kV needs less mA*min for same thickness
        self.assertGreater(e_180_15, e_190_15)
        self.assertGreater(e_190_15, e_200_15)

        e_200_20 = self.db.get_type_x_exposure(200, 20)
        e_200_17_5 = self.db.get_type_x_exposure(200, 17.5)
        self.assertLess(e_200_15, e_200_17_5)
        self.assertLess(e_200_17_5, e_200_20)

    def test_isotope_material_ref_scaling(self):
        """Aluminum/Titanium (REF < 1) should need less exposure time than Steel, Copper/Nickel (REF > 1) more."""
        _, _, t_al = self.calc.calculate_exposure_time(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog", material="aluminum"
        )
        _, _, t_st = self.calc.calculate_exposure_time(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog", material="steel"
        )
        _, _, t_cu = self.calc.calculate_exposure_time(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog", material="copper_nickel"
        )
        self.assertLess(t_al, t_st)
        self.assertGreater(t_cu, t_st)

    def test_trial_shot_correction_analog_and_digital(self):
        analog_corr = self.calc.calculate_trial_shot_correction(
            tech="analog", t1_sec=60.0, sfd1=600.0, sfd2=600.0,
            measured_quality=1.8, target_quality=2.3, film_class="C5"
        )
        self.assertGreater(analog_corr["t2_sec"], 60.0)
        self.assertGreater(analog_corr["total_ratio"], 1.0)

        digital_corr = self.calc.calculate_trial_shot_correction(
            tech="digital", t1_sec=50.0, sfd1=600.0, sfd2=600.0,
            measured_quality=70.0, target_quality=140.0
        )
        self.assertAlmostEqual(digital_corr["total_ratio"], 4.0, places=3)
        self.assertAlmostEqual(digital_corr["t2_sec"], 200.0, places=2)

    def test_digital_cr_ips_and_dda_panel_rfactor_lookup(self):
        r_cr_std, _ = self.db.lookup_digital_r_factor("cr_standard", "isotope_ir192")
        r_cr_hi, _ = self.db.lookup_digital_r_factor("cr_highres", "isotope_ir192")
        r_dda_si, _ = self.db.lookup_digital_r_factor("dda_si", "isotope_ir192")
        r_dda_se, _ = self.db.lookup_digital_r_factor("dda_se", "isotope_ir192")
        self.assertIsNotNone(r_cr_std)
        self.assertIsNotNone(r_cr_hi)
        self.assertIsNotNone(r_dda_si)
        self.assertIsNotNone(r_dda_se)
        # High-res CR (IPS-1) requires more dose than standard CR (IPS-2/3), so larger R-factor (Ci·min/m²)
        self.assertGreater(r_cr_hi, r_cr_std)
        # DDA panels require less dose (faster) than CR plates, so smaller R-factor (Ci·min/m²)
        self.assertLess(r_dda_si, r_cr_std)

    def test_digital_chart_methods_in_calculator(self):
        # CR IPS Chart (ISO 16371-1)
        res_cr = self.calc.calculate_exposure_time_details(
            600.0, 15.0, "isotope_ir192", 40.0, 30.0, "digital",
            detector_type="cr_standard", chart_source="cr_ips_chart",
            chart_db=self.db, app_srb=100.0
        )
        self.assertEqual(res_cr["provenance"]["method"], "cr_ips_chart")
        self.assertGreater(res_cr["time_seconds"], 0.0)

        # DDA Frame Integration Method (ASTM E2698)
        res_dda_frame = self.calc.calculate_exposure_time_details(
            600.0, 15.0, "x_ray", 5.0, 3.0, "digital",
            detector_type="dda_si", kv=160.0, chart_source="dda_frame_method",
            chart_db=self.db, app_srb=100.0
        )
        self.assertEqual(res_dda_frame["provenance"]["method"], "dda_frame_method")
        self.assertIsNotNone(res_dda_frame["provenance"]["dda_frame"])
        self.assertGreaterEqual(res_dda_frame["provenance"]["dda_frame"]["n_frames"], 1)
        self.assertGreater(res_dda_frame["provenance"]["dda_frame"]["t_frame_sec"], 0.0)
        self.assertGreater(res_dda_frame["time_seconds"], 0.0)

        # Digital X-Ray Chart
        res_dx = self.calc.calculate_exposure_time_details(
            600.0, 15.0, "x_ray", 5.0, 3.0, "digital",
            detector_type="cr_highres", kv=160.0, chart_source="digital_xray_chart",
            chart_db=self.db, app_srb=63.0
        )
        self.assertEqual(res_dx["provenance"]["method"], "digital_xray_chart")
        self.assertGreater(res_dx["time_seconds"], 0.0)

    def test_digital_xray_chart_restores_c5_baseline_no_16x_underexposure(self):
        """TYPE_X_CHART is pre-divided by C5 film speed (16.0); digital_xray_chart must restore that 16x factor."""
        res_model = self.calc.calculate_exposure_time_details(
            700.0, 20.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="cr_standard",
            kv=200.0, chart_source="model", chart_db=self.db,
            target_snr=70.0, app_srb=100.0
        )
        res_chart = self.calc.calculate_exposure_time_details(
            700.0, 20.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="cr_standard",
            kv=200.0, chart_source="digital_xray_chart", chart_db=self.db,
            target_snr=70.0, app_srb=100.0
        )
        self.assertAlmostEqual(
            res_chart["time_seconds"], res_model["time_seconds"],
            delta=res_model["time_seconds"] * 0.05
        )
        # Selecting dda_panel_chart with x_ray must report digital_xray_chart, not analog type_x
        res_dda_x = self.calc.calculate_exposure_time_details(
            700.0, 20.0, "x_ray", 5.0, 3.0, "digital",
            testing_class="class_a", detector_type="dda_si",
            kv=200.0, chart_source="dda_panel_chart", chart_db=self.db,
            target_snr=70.0, app_srb=100.0
        )
        self.assertEqual(res_dda_x["provenance"]["method"], "digital_xray_chart")

    def test_xray_chart_material_equivalence_scaling(self):
        """type_x and digital_xray_chart must scale thickness by energy-dependent mu(kV, mat)/mu(kV, steel)."""
        _, _, t_al = self.calc.calculate_exposure_time(
            700.0, 20.0, "x_ray", 5.0, 3.0, "analog",
            film_class="C5", kv=200.0, chart_source="type_x",
            chart_db=self.db, material="aluminum"
        )
        _, _, t_st = self.calc.calculate_exposure_time(
            700.0, 20.0, "x_ray", 5.0, 3.0, "analog",
            film_class="C5", kv=200.0, chart_source="type_x",
            chart_db=self.db, material="steel"
        )
        _, _, t_cu = self.calc.calculate_exposure_time(
            700.0, 20.0, "x_ray", 5.0, 3.0, "analog",
            film_class="C5", kv=200.0, chart_source="type_x",
            chart_db=self.db, material="copper_nickel"
        )
        self.assertLess(t_al, t_st)
        self.assertGreater(t_cu, t_st)

    def test_dda_panel_chart_gamma_passes_testing_class_and_floor(self):
        """dda_panel_chart with isotope must pass testing_class to DDA frame integration (16 vs 32 frames) and enforce hardware floor."""
        res_a = self.calc.calculate_exposure_time_details(
            400.0, 6.0, "isotope_ir192", 80.0, 30.0, "digital",
            testing_class="class_a", detector_type="dda_si",
            chart_source="dda_panel_chart", chart_db=self.db, app_srb=100.0
        )
        res_b = self.calc.calculate_exposure_time_details(
            400.0, 6.0, "isotope_ir192", 80.0, 30.0, "digital",
            testing_class="class_b", detector_type="dda_si",
            chart_source="dda_panel_chart", chart_db=self.db, app_srb=100.0
        )
        self.assertEqual(res_a["provenance"]["dda_frame"]["n_frames"], 16)
        self.assertEqual(res_b["provenance"]["dda_frame"]["n_frames"], 32)
        self.assertGreaterEqual(res_a["time_seconds"], 16 * 0.10)
        self.assertGreaterEqual(res_b["time_seconds"], 32 * 0.10)

    def test_rfactor_chart_uses_film_specific_gradient(self):
        """calculate_exposure_time_details must use ISO 11699-1 film gradient G_D (3.5 for M100/C2, 2.5 for HS800/C6) in R-factor mode."""
        res_m100 = self.calc.calculate_exposure_time_details(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog",
            film_class="C2", chart_source="M100", chart_db=self.db, density=3.0
        )
        res_hs800 = self.calc.calculate_exposure_time_details(
            600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog",
            film_class="C6", chart_source="HS800", chart_db=self.db, density=3.0
        )
        self.assertAlmostEqual(
            res_m100["provenance"]["od_factor"], 10 ** ((3.0 - 2.0) / 3.5), places=4
        )
        self.assertAlmostEqual(
            res_hs800["provenance"]["od_factor"], 10 ** ((3.0 - 2.0) / 2.5), places=4
        )

    def test_extra_multiplier_scales_dda_frame_method(self):
        """extra_multiplier (e.g. Field Factor F or Level 3 SFD compensation) must scale dda_frame_method before hardware floor."""
        res_1x = self.calc.calculate_exposure_time_details(
            700.0, 25.0, "x_ray", 5.0, 3.0, "digital",
            detector_type="dda_si", kv=200.0, chart_source="dda_frame_method",
            chart_db=self.db, app_srb=100.0, extra_multiplier=1.0
        )
        res_2x = self.calc.calculate_exposure_time_details(
            700.0, 25.0, "x_ray", 5.0, 3.0, "digital",
            detector_type="dda_si", kv=200.0, chart_source="dda_frame_method",
            chart_db=self.db, app_srb=100.0, extra_multiplier=2.0
        )
        self.assertAlmostEqual(res_2x["time_seconds"] / res_1x["time_seconds"], 2.0, delta=0.02)

    def test_custom_rfactor_override_scales_non_aa400_film(self):
        """Custom R_FACTOR_TABLE overrides for non-AA400 films must scale calculate_exposure_time_rfactor proportionally."""
        db_custom = ExposureChartDatabase()
        t_default = db_custom.calculate_exposure_time_rfactor(
            600.0, 20.0, "isotope_ir192", 40.0, "MX125", density=2.0
        )
        db_custom.R_FACTOR_TABLE["MX125"]["isotope_ir192"] = (
            db_custom.R_FACTOR_TABLE["MX125"]["isotope_ir192"] * 1.5
        )
        t_custom = db_custom.calculate_exposure_time_rfactor(
            600.0, 20.0, "isotope_ir192", 40.0, "MX125", density=2.0
        )
        self.assertAlmostEqual(t_custom / t_default, 1.5, places=4)

    def test_multi_brand_film_catalog_and_monotonicity(self):
        """All 22 film models across Carestream, Agfa, Fujifilm, and Foma must resolve and maintain C1->C6 exposure monotonicity per brand."""
        brand_series = {
            "Carestream": ["DR50", "M100", "MX125", "T200", "AA400", "HS800"],
            "Agfa Structurix": ["D2", "D3", "D4", "D5", "D7", "D8"],
            "Fujifilm": ["IX25", "IX50", "IX80", "IX100", "IX150"],
            "Foma Fomadux": ["R2", "R4", "R5", "R7", "R8"],
        }
        for brand, models in brand_series.items():
            prev_time = None
            for film in models:
                cls = self.db.FILM_CLASS_BY_MODEL[film]
                res = self.calc.calculate_exposure_time_details(
                    600.0, 20.0, "isotope_ir192", 40.0, 30.0, "analog",
                    film_class=cls, chart_source=film, chart_db=self.db
                )
                self.assertEqual(res["provenance"]["method"], "rfactor")
                self.assertEqual(res["provenance"]["film_key"], film)
                self.assertEqual(res["provenance"]["film_brand"], brand)
                self.assertEqual(res["provenance"]["chart_film_class"], cls)
                self.assertGreater(res["time_seconds"], 0.0)
                if prev_time is not None:
                    self.assertLess(res["time_seconds"], prev_time)
                prev_time = res["time_seconds"]


if __name__ == "__main__":
    unittest.main()

