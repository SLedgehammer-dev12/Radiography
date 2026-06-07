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

if __name__ == "__main__":
    unittest.main()
