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

    def test_lookup_missing(self):
        r = self.db.lookup_r_factor("AA400", "isotope_tm170")
        self.assertIsNone(r)

        r = self.db.lookup_r_factor("UNKNOWN", "isotope_ir192")
        self.assertIsNone(r)

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

        sources_m100 = self.db.get_available_sources_for_film("M100")
        self.assertIn("isotope_ir192", sources_m100)
        self.assertNotIn("isotope_se75", sources_m100)

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
            sfd=600.0, w=20.0, source="isotope_tm170",
            activity=40.0, film_key="AA400", density=2.0
        )
        self.assertIsNone(t_min)

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


if __name__ == "__main__":
    unittest.main()

