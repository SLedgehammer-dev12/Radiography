# -*- coding: utf-8 -*-

import unittest
from src.core.asme_b31_3 import ASMEB31_3Evaluator
from src.core.asme_viii import ASMEVIIIEvaluator


class TestASMEB31_3(unittest.TestCase):
    def setUp(self):
        self.eval = ASMEB31_3Evaluator()

    def test_crack_rejected(self):
        for svc in ("normal", "severe"):
            ok, _ = self.eval.evaluate("defect_crack", 10.0, 5.0, 1.0, 5.0, service=svc)
            self.assertFalse(ok)

    def test_ip_if_rejected(self):
        for dt in ("defect_ip", "defect_if", "defect_ic"):
            ok, _ = self.eval.evaluate(dt, 10.0, 2.0, 1.0, 2.0, service="normal")
            self.assertFalse(ok)

    def test_porosity_normal_vs_severe(self):
        # 2.0 mm pore: acceptable for normal, rejected for severe (limit 1.6)
        ok_n, _ = self.eval.evaluate("defect_porosity", 10.0, 2.0, 2.0, 5.0, service="normal")
        ok_s, _ = self.eval.evaluate("defect_porosity", 10.0, 2.0, 2.0, 5.0, service="severe")
        self.assertTrue(ok_n)
        self.assertFalse(ok_s)

    def test_undercut_severe_tighter(self):
        ok_n, _ = self.eval.evaluate("defect_undercut", 10.0, 10.0, 0.6, 5.0, service="normal")
        ok_s, _ = self.eval.evaluate("defect_undercut", 10.0, 10.0, 0.6, 5.0, service="severe")
        self.assertTrue(ok_n)
        self.assertFalse(ok_s)


class TestASMEVIII(unittest.TestCase):
    def setUp(self):
        self.eval = ASMEVIIIEvaluator()

    def test_uw51_rejects_critical(self):
        for dt in ("defect_crack", "defect_if", "defect_ic", "defect_ip"):
            ok, _ = self.eval.evaluate(dt, 10.0, 2.0, 1.0, 2.0, mode="UW-51")
            self.assertFalse(ok)

    def test_uw51_porosity_tight(self):
        ok, _ = self.eval.evaluate("defect_porosity", 10.0, 1.5, 1.5, 4.0, mode="UW-51")
        self.assertFalse(ok)  # UW-51 max pore 1.0 mm

    def test_uw52_allows_limited_porosity(self):
        ok, _ = self.eval.evaluate("defect_porosity", 10.0, 2.0, 2.0, 4.0, mode="UW-52")
        self.assertTrue(ok)    # UW-52 max pore 3.0 mm

    def test_accept_message(self):
        ok, reason = self.eval.evaluate("defect_slag", 10.0, 5.0, 0.5, 2.0, mode="UW-52", lang="en")
        self.assertTrue(ok)
        self.assertIn("UW-52", reason)

    def test_messages_have_no_double_uw_prefix_and_are_localized(self):
        # Regression: templates contained "UW-{}" while the mode already had the
        # "UW-" prefix -> "UW-UW-51"; and the reject labels were Turkish-only.
        _, en_crack = self.eval.evaluate("defect_crack", 10.0, 2.0, 1.0, 0.0, mode="UW-51", lang="en")
        self.assertIn("UW-51", en_crack)
        self.assertNotIn("UW-UW", en_crack)
        self.assertIn("Crack", en_crack)

        _, en_por = self.eval.evaluate("defect_porosity", 10.0, 5.0, 5.0, 0.0, mode="UW-52", lang="en")
        self.assertIn("UW-52", en_por)
        self.assertNotIn("UW-UW", en_por)

        _, tr_crack = self.eval.evaluate("defect_crack", 10.0, 2.0, 1.0, 0.0, mode="UW-51", lang="tr")
        self.assertIn("UW-51", tr_crack)
        self.assertNotIn("UW-UW", tr_crack)
        self.assertIn("Çatlak", tr_crack)


if __name__ == "__main__":
    unittest.main()