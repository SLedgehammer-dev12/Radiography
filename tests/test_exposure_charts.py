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
