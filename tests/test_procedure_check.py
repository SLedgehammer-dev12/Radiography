# -*- coding: utf-8 -*-

import unittest
from src.core.procedure_check import ProcedureComplianceChecker

class TestProcedureComplianceChecker(unittest.TestCase):
    def setUp(self):
        self.checker = ProcedureComplianceChecker()

    def test_xray_voltage_compliance(self):
        # Case 1: Voltage is within limit
        inputs = {"tech": "digital", "source": "x_ray", "class": "class_b"}
        calculated = {"u_max": 150.0, "sfd_min": 500.0, "required_wire_no": 12, "required_duplex_no": 10}
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 13,
            "applied_duplex": 11,
            "applied_quality": 150.0,
            "applied_time": 60.0
        }
        lvl3 = {"sfd_comp": False, "voltage_override": False}

        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

        # Case 2: Voltage exceeds limit without override
        applied["applied_kv"] = 160.0
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

        # Case 3: Voltage exceeds limit with Level 3 override
        lvl3["voltage_override"] = True
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

    def test_sfd_compliance(self):
        inputs = {"tech": "digital", "source": "x_ray", "class": "class_b"}
        calculated = {"u_max": 150.0, "sfd_min": 600.0, "required_wire_no": 12, "required_duplex_no": 10}
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 500.0, # Less than 600.0 mm
            "applied_wire": 13,
            "applied_duplex": 11,
            "applied_quality": 150.0,
            "applied_time": 60.0
        }
        lvl3 = {"sfd_comp": False, "voltage_override": False}

        # Case 1: Insufficient distance, no compensation
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

        # Case 2: Insufficient distance, with Level 3 distance compensation
        lvl3["sfd_comp"] = True
        # Check requires higher SNR_N (130 * 600/500 = 156.0). Since applied quality (150.0) < 156.0, it should fail
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

        # Case 3: Higher applied SNR_N makes it compliant
        applied["applied_quality"] = 160.0
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

    def test_analog_quality_density(self):
        inputs = {"tech": "analog", "source": "isotope_ir192", "class": "class_b"}
        calculated = {"sfd_min": 400.0, "required_wire_no": 12}
        applied = {
            "applied_sfd": 450.0,
            "applied_wire": 13,
            "applied_quality": 2.2, # Class B analog density limit is 2.3
            "applied_time": 120.0,
            "applied_overlap": 10.0
        }
        lvl3 = {}

        # Case 1: Density below Class B limit (2.3)
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

        # Case 2: Density above Class B limit
        applied["applied_quality"] = 2.4
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

    def test_detector_quality_compliance(self):
        # Case 1: Analog film class check (applied is C4, required is C4 -> pass)
        inputs = {"tech": "analog", "source": "x_ray", "class": "class_b"}
        calculated = {"sfd_min": 400.0, "required_wire_no": 12, "required_film_class": "C4"}
        applied = {
            "applied_sfd": 450.0,
            "applied_wire": 13,
            "applied_quality": 2.5,
            "applied_time": 120.0,
            "applied_film_class": "C4",
            "applied_overlap": 10.0
        }
        lvl3 = {}
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

        # Case 2: Applied film class is higher quality (C3) -> pass
        applied["applied_film_class"] = "C3"
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

        # Case 3: Applied film class is lower quality (C5) -> fail
        applied["applied_film_class"] = "C5"
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

        # Case 4: Digital SRb check (applied is 80 µm, max allowed is 100 µm -> pass)
        inputs = {"tech": "digital", "source": "x_ray", "class": "class_b"}
        calculated = {"u_max": 150.0, "sfd_min": 500.0, "required_wire_no": 12, "required_duplex_no": 10, "max_srb": 100.0}
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 13,
            "applied_duplex": 11,
            "applied_quality": 150.0,
            "applied_time": 60.0,
            "applied_srb": 80.0
        }
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])

        # Case 5: Applied SRb is insufficient (120 µm > 100 µm -> fail)
        applied["applied_srb"] = 120.0
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

    def test_film_overlap_compliance(self):
        inputs = {"tech": "analog", "source": "x_ray", "class": "class_b"}
        calculated = {"u_max": 150.0, "sfd_min": 500.0, "required_wire_no": 12, "required_film_class": "C4"}
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 13,
            "applied_quality": 2.5,
            "applied_time": 120.0,
            "applied_film_class": "C4",
            "applied_overlap": 12.0 # 12mm overlap >= 10.0mm (pass)
        }
        lvl3 = {}
        
        # Case 1: Overlap is compliant
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertTrue(res["is_compliant"])
        
        # Case 2: Overlap is insufficient (8mm < 10mm -> fail)
        applied["applied_overlap"] = 8.0
        res = self.checker.check_compliance(inputs, calculated, applied, lvl3, "en")
        self.assertFalse(res["is_compliant"])

    def test_wire_duplex_failures(self):
        inputs = {"tech": "digital", "source": "x_ray", "class": "class_b"}
        calculated = {"u_max": 150.0, "sfd_min": 500.0, "required_wire_no": 12, "required_duplex_no": 10}
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 11, # Fail: 11 < 12
            "applied_duplex": 11,
            "applied_quality": 150.0,
            "applied_time": 60.0
        }
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertFalse(res["is_compliant"])

        # Case 2: Duplex failure (applied D9 < required D10)
        applied["applied_wire"] = 12
        applied["applied_duplex"] = 9
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertFalse(res["is_compliant"])

    def test_time_compliance(self):
        inputs = {"tech": "digital", "source": "x_ray", "class": "class_b"}
        calculated = {"u_max": 150.0, "sfd_min": 500.0, "required_wire_no": 12, "required_duplex_no": 10, "calc_time_raw": 100.0}
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 12,
            "applied_duplex": 10,
            "applied_quality": 150.0,
            "applied_time": 105.0 # within 25% (compliant)
        }
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertTrue(res["is_compliant"])
        time_check = [c for c in res["checks"] if c["name"] == "time"][0]
        self.assertTrue(time_check["status"])

        # Applied time is outside 25%
        applied["applied_time"] = 200.0
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertTrue(res["is_compliant"]) # remains compliant as time check is a warning only
        time_check = [c for c in res["checks"] if c["name"] == "time"][0]
        self.assertTrue(time_check["status"])

    def test_dwsi_source_side_placement_failure(self):
        inputs = {
            "tech": "digital",
            "source": "x_ray",
            "class": "class_b",
            "geometry": "dwsi",
            "film_side": False, # Source side placement is invalid for DWSI
            "iqi_type": "wire"
        }
        calculated = {
            "u_max": 150.0,
            "sfd_min": 500.0,
            "required_wire_no": 12,
            "required_duplex_no": 10,
            "required_snr": 130.0
        }
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 13,
            "applied_duplex": 11,
            "applied_quality": 150.0,
            "applied_time": 60.0
        }
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertFalse(res["is_compliant"])
        # Verify dwsi_placement_fail warning was appended
        messages = [c["details"] for c in res["checks"] if c["name"] == "iqi_placement"]
        self.assertTrue(len(messages) > 0)
        self.assertIn("placement", messages[0].lower())

    def test_step_hole_compliance_rules(self):
        # Applied step-hole must satisfy: applied_wire <= req_wire (lower number is more sensitive/better)
        inputs = {
            "tech": "digital",
            "source": "x_ray",
            "class": "class_b",
            "geometry": "swsi",
            "film_side": True,
            "iqi_type": "step_hole"
        }
        calculated = {
            "u_max": 150.0,
            "sfd_min": 500.0,
            "required_wire_no": 8, # for step-hole, this holds the required hole number (H-No)
            "required_duplex_no": 10,
            "required_snr": 120.0
        }
        
        # Case 1: Applied is H7 (7 <= 8) -> Compliant
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 7, # applied H-No
            "applied_duplex": 11,
            "applied_quality": 130.0,
            "applied_time": 60.0
        }
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertTrue(res["is_compliant"])

        # Case 2: Applied is H9 (9 > 8) -> Non-compliant
        applied["applied_wire"] = 9
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertFalse(res["is_compliant"])

    def test_adjacent_measurement_snr_target(self):
        # Location is adjacent.
        inputs = {
            "tech": "digital",
            "source": "x_ray",
            "class": "class_b",
            "geometry": "swsi",
            "film_side": True,
            "iqi_type": "wire",
            "snr_location": "adjacent"
        }
        calculated = {
            "u_max": 150.0,
            "sfd_min": 500.0,
            "required_wire_no": 12,
            "required_duplex_no": 10,
            # Target is already increased by 1.4x in calculated
            "required_snr": 168.0  # 120.0 * 1.4 = 168.0
        }
        
        # Case 1: Applied SNR is 170.0 (>= 168.0) -> Compliant
        applied = {
            "applied_kv": 140.0,
            "applied_sfd": 550.0,
            "applied_wire": 13,
            "applied_duplex": 11,
            "applied_quality": 170.0,
            "applied_time": 60.0
        }
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertTrue(res["is_compliant"])

        # Case 2: Applied SNR is 150.0 (< 168.0) -> Non-compliant
        applied["applied_quality"] = 150.0
        res = self.checker.check_compliance(inputs, calculated, applied, {}, "en")
        self.assertFalse(res["is_compliant"])

if __name__ == "__main__":
    unittest.main()
