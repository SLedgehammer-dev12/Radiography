# -*- coding: utf-8 -*-

import unittest
from src.core.api1104 import API1104Evaluator

class TestAPI1104Evaluator(unittest.TestCase):
    def setUp(self):
        self.eval = API1104Evaluator()

    def test_crack(self):
        # Cracks are always rejected
        accepted, reason = self.eval.evaluate("defect_crack", 10.0, 1.0, 0.5, 1.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Cracks are unacceptable", reason)

    def test_ip(self):
        # IP individual length <= 25.4 mm (1 in) is acceptable
        accepted, reason = self.eval.evaluate("defect_ip", 10.0, 15.0, 1.0, 15.0, "en")
        self.assertTrue(accepted)

        # IP individual length > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_ip", 10.0, 30.0, 1.0, 30.0, "en")
        self.assertFalse(accepted)
        self.assertIn("exceeds the 25.4 mm", reason)

        # IP accumulated length > 25.4 mm in 300 mm is rejected
        accepted, reason = self.eval.evaluate("defect_ip", 10.0, 15.0, 1.0, 30.0, "en")
        self.assertFalse(accepted)
        self.assertIn("accumulated length in 300 mm exceeds", reason)

    def test_porosity(self):
        # Porosity size limit is min(3.2 mm, 0.25 * t)
        # For t = 10.0 mm: limit is min(3.2, 2.5) = 2.5 mm
        # Size = 2.0 mm -> Acceptable
        accepted, reason = self.eval.evaluate("defect_porosity", 10.0, 2.0, 2.0, 5.0, "en")
        self.assertTrue(accepted)

        # Size = 3.0 mm -> Rejected (exceeds 2.5 mm)
        accepted, reason = self.eval.evaluate("defect_porosity", 10.0, 3.0, 2.0, 5.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Individual pore size exceeds", reason)

        # Accumulated limit is 12.7 mm
        accepted, reason = self.eval.evaluate("defect_porosity", 10.0, 2.0, 2.0, 15.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Porosity accumulated length in 300 mm exceeds", reason)

    def test_incomplete_fusion_if(self):
        # IF length <= 25.4 mm is acceptable
        accepted, reason = self.eval.evaluate("defect_if", 10.0, 15.0, 1.0, 15.0, "en")
        self.assertTrue(accepted)

        # IF length > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_if", 10.0, 30.0, 1.0, 30.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Incomplete Fusion (IF) individual length exceeds", reason)

        # IF accumulated > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_if", 10.0, 10.0, 1.0, 30.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Incomplete Fusion (IF) accumulated length in 300 mm exceeds", reason)

    def test_incomplete_penetration_root_ic(self):
        # IC length <= 50.8 mm is acceptable
        accepted, reason = self.eval.evaluate("defect_ic", 10.0, 30.0, 1.0, 30.0, "en")
        self.assertTrue(accepted)

        # IC length > 50.8 mm is rejected
        accepted, reason = self.eval.evaluate("defect_ic", 10.0, 60.0, 1.0, 60.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Incomplete Penetration of Weld Root (IC) individual length exceeds", reason)

        # IC accumulated > 50.8 mm is rejected
        accepted, reason = self.eval.evaluate("defect_ic", 10.0, 20.0, 1.0, 60.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Incomplete Penetration of Weld Root (IC) accumulated length in 300 mm exceeds", reason)

    def test_slag(self):
        # Slag with t <= 12.7 mm: width limit = 1.6 mm, length = 15.0 -> Acceptable
        accepted, reason = self.eval.evaluate("defect_slag", 10.0, 15.0, 1.0, 10.0, "en")
        self.assertTrue(accepted)

        # Slag width > 1.6 mm (for t <= 12.7) is rejected
        accepted, reason = self.eval.evaluate("defect_slag", 10.0, 15.0, 2.5, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("width exceeds the limit", reason)

        # Slag with t > 12.7 mm: width limit = 3.2 mm
        accepted, reason = self.eval.evaluate("defect_slag", 20.0, 15.0, 3.0, 10.0, "en")
        self.assertTrue(accepted)

        # Slag width > 3.2 mm (for t > 12.7) is rejected
        accepted, reason = self.eval.evaluate("defect_slag", 20.0, 15.0, 4.0, 10.0, "en")
        self.assertFalse(accepted)

        # Slag length > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_slag", 10.0, 30.0, 1.0, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("individual length exceeds the 25.4 mm", reason)

        # Slag accumulated > 12.7 mm is rejected
        accepted, reason = self.eval.evaluate("defect_slag", 10.0, 15.0, 1.0, 20.0, "en")
        self.assertFalse(accepted)
        self.assertIn("accumulated length in 300 mm exceeds the 12.7 mm", reason)

    def test_undercut(self):
        # Undercut with t <= 12.7 mm: depth limit = 0.4 mm
        accepted, reason = self.eval.evaluate("defect_undercut", 10.0, 15.0, 0.3, 10.0, "en")
        self.assertTrue(accepted)

        # Undercut depth > 0.4 mm (for t <= 12.7) is rejected
        accepted, reason = self.eval.evaluate("defect_undercut", 10.0, 15.0, 0.7, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("depth exceeds the limit", reason)

        # Undercut with t > 12.7 mm: depth limit = 0.8 mm
        accepted, reason = self.eval.evaluate("defect_undercut", 20.0, 15.0, 0.5, 10.0, "en")
        self.assertTrue(accepted)

        # Undercut depth > 0.8 mm (for t > 12.7) is rejected
        accepted, reason = self.eval.evaluate("defect_undercut", 20.0, 15.0, 1.2, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("depth exceeds the limit", reason)

        # Undercut length > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_undercut", 10.0, 30.0, 0.3, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("individual length exceeds the 25.4 mm", reason)

        # Undercut accumulated > 50.8 mm is rejected
        accepted, reason = self.eval.evaluate("defect_undercut", 10.0, 15.0, 0.3, 60.0, "en")
        self.assertFalse(accepted)
        self.assertIn("accumulated length in 300 mm exceeds the 50.8 mm", reason)

    def test_burn_through(self):
        # Burn-Through width <= 6.4 mm, length <= 25.4 mm -> Acceptable
        accepted, reason = self.eval.evaluate("defect_burn_through", 10.0, 15.0, 4.0, 10.0, "en")
        self.assertTrue(accepted)

        # Burn-Through width > 6.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_burn_through", 10.0, 15.0, 8.0, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("Burn-Through width exceeds the 6.4 mm", reason)

        # Burn-Through length > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_burn_through", 10.0, 30.0, 4.0, 10.0, "en")
        self.assertFalse(accepted)
        self.assertIn("individual length exceeds the 25.4 mm", reason)

        # Burn-Through accumulated > 25.4 mm is rejected
        accepted, reason = self.eval.evaluate("defect_burn_through", 10.0, 15.0, 4.0, 30.0, "en")
        self.assertFalse(accepted)
        self.assertIn("accumulated length in 300 mm exceeds the 25.4 mm", reason)

    def test_evaluate_accumulation_pass(self):
        defects = [("defect_ip", 10.0), ("defect_if", 8.0)]
        accepted, reason = self.eval.evaluate_accumulation(defects, 300.0, "en")
        self.assertTrue(accepted)

    def test_evaluate_accumulation_fail(self):
        defects = [("defect_ip", 20.0), ("defect_if", 15.0)]
        accepted, reason = self.eval.evaluate_accumulation(defects, 300.0, "en")
        self.assertFalse(accepted)
        self.assertIn("exceeds 8% of weld length", reason)

    def test_turkish_language(self):
        accepted, reason = self.eval.evaluate("defect_slag", 10.0, 15.0, 1.0, 10.0, "tr")
        self.assertTrue(accepted)

        accepted, reason = self.eval.evaluate("defect_crack", 10.0, 1.0, 0.5, 1.0, "tr")
        self.assertFalse(accepted)
        self.assertIn("REDDEDİLİR", reason)

if __name__ == "__main__":
    unittest.main()
