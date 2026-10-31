# -*- coding: utf-8 -*-
"""
Tests for ISO 10893-7:2019 implementation.
Covers:
- Table 1 (Class A) and Table 2 (Class B) single wire IQI
- Table 1 and Table 2 step/hole IQI
- Table 1 and Table 2 duplex wire IQI & SR_b limits
- Target normalized SNR_N (Clause 7.3: >= 70 for Class A, >= 100 for Class B)
- Clause 10 Defect evaluation (ISO10893Evaluator)
- DDA calibration U_max exception (Clause 6.10)
"""

import pytest
from src.core.calculator import RTCalculator
from src.core.engine import CalculationEngine, normalize_form
from src.core.iso10893 import ISO10893Evaluator
from src.core.procedure_check import ProcedureComplianceChecker


class TestISO10893Calculator:
    @pytest.fixture
    def calc(self):
        return RTCalculator()

    # -------------------------------------------------------------------------
    # 1. Single Wire IQI (ISO 10893-7 Table 1 & Table 2)
    # -------------------------------------------------------------------------
    def test_single_wire_class_a(self, calc):
        # Table 1: T <= 1.2 -> W18; 1.2 < T <= 2.0 -> W17; 2.0 < T <= 3.5 -> W16; 6.0 < T <= 10.0 -> W13
        w_str, wire_no = calc.get_single_wire_iqi(1.0, 0.0, "class_a", "swsi", standard="iso10893_7")
        assert wire_no == 18
        assert "Table 1" in w_str or "Tablo 1" in w_str

        _, wire_no = calc.get_single_wire_iqi(1.8, 0.0, "class_a", "swsi", standard="iso10893_7")
        assert wire_no == 17

        _, wire_no = calc.get_single_wire_iqi(3.0, 0.0, "class_a", "swsi", standard="iso10893_7")
        assert wire_no == 16

        _, wire_no = calc.get_single_wire_iqi(8.0, 0.0, "class_a", "swsi", standard="iso10893_7")
        assert wire_no == 13

        _, wire_no = calc.get_single_wire_iqi(60.0, 0.0, "class_a", "swsi", standard="iso10893_7")
        assert wire_no == 7

    def test_single_wire_class_b(self, calc):
        # Table 2: T <= 1.5 -> W19; 1.5 < T <= 2.5 -> W18; 2.5 < T <= 4.0 -> W17; 6.0 < T <= 8.0 -> W15
        w_str, wire_no = calc.get_single_wire_iqi(1.2, 0.0, "class_b", "swsi", standard="iso10893_7")
        assert wire_no == 19
        assert "Table 2" in w_str or "Tablo 2" in w_str

        _, wire_no = calc.get_single_wire_iqi(2.0, 0.0, "class_b", "swsi", standard="iso10893_7")
        assert wire_no == 18

        _, wire_no = calc.get_single_wire_iqi(3.5, 0.0, "class_b", "swsi", standard="iso10893_7")
        assert wire_no == 17

        _, wire_no = calc.get_single_wire_iqi(7.0, 0.0, "class_b", "swsi", standard="iso10893_7")
        assert wire_no == 15

        _, wire_no = calc.get_single_wire_iqi(10.0, 0.0, "class_b", "swsi", standard="iso10893_7")
        assert wire_no == 14

        _, wire_no = calc.get_single_wire_iqi(70.0, 0.0, "class_b", "swsi", standard="iso10893_7")
        assert wire_no == 8

    def test_single_wire_double_wall(self, calc):
        # Per Clause 7.4: for double wall technique, ref thickness is 2 * T
        # T = 3.0 mm -> 2T = 6.0 mm. For Class B: 4 < 2T <= 6 -> W16
        _, wire_no = calc.get_single_wire_iqi(3.0, 0.0, "class_b", "dwsi", standard="iso10893_7")
        assert wire_no == 16

    # -------------------------------------------------------------------------
    # 2. Duplex Wire IQI & SR_b (ISO 10893-7 Table 1 & Table 2)
    # -------------------------------------------------------------------------
    def test_duplex_wire_class_a(self, calc):
        # Table 1: T <= 2 -> D11; 2 < T <= 5 -> D10; 5 < T <= 10 -> D9; 10 < T <= 25 -> D8
        d_str, d_no = calc.get_duplex_iqi(1.5, "class_a", geometry="swsi", standard="iso10893_7")
        assert d_no == 11
        assert "Table 1" in d_str or "Tablo 1" in d_str

        _, d_no = calc.get_duplex_iqi(4.0, "class_a", geometry="swsi", standard="iso10893_7")
        assert d_no == 10

        _, d_no = calc.get_duplex_iqi(8.0, "class_a", geometry="swsi", standard="iso10893_7")
        assert d_no == 9

        _, d_no = calc.get_duplex_iqi(20.0, "class_a", geometry="swsi", standard="iso10893_7")
        assert d_no == 8

    def test_duplex_wire_class_b(self, calc):
        # Table 2: T <= 4 -> D13; 4 < T <= 8 -> D12; 8 < T <= 12 -> D11; 12 < T <= 40 -> D10; 40 < T -> D9
        d_str, d_no = calc.get_duplex_iqi(1.0, "class_b", geometry="swsi", standard="iso10893_7")
        assert d_no == 14
        assert "D 13+" in d_str or "D 14" in d_str
        assert "Table 2" in d_str or "Tablo 2" in d_str

        d_str, d_no = calc.get_duplex_iqi(3.0, "class_b", geometry="swsi", standard="iso10893_7")
        assert d_no == 13

        _, d_no = calc.get_duplex_iqi(6.0, "class_b", geometry="swsi", standard="iso10893_7")
        assert d_no == 12

        _, d_no = calc.get_duplex_iqi(10.0, "class_b", geometry="swsi", standard="iso10893_7")
        assert d_no == 11

        _, d_no = calc.get_duplex_iqi(25.0, "class_b", geometry="swsi", standard="iso10893_7")
        assert d_no == 10

        _, d_no = calc.get_duplex_iqi(50.0, "class_b", geometry="swsi", standard="iso10893_7")
        assert d_no == 9

    # -------------------------------------------------------------------------
    # 3. Target SNR_N (Clause 7.3)
    # -------------------------------------------------------------------------
    def test_target_snr_iso10893(self, calc):
        snr_a, tbl_a, _ = calc.get_target_snr("steel", "x_ray", 120.0, 8.0, "class_a", standard="iso10893_7")
        assert snr_a == 70
        assert "10893" in tbl_a

        snr_b, tbl_b, _ = calc.get_target_snr("steel", "x_ray", 120.0, 8.0, "class_b", standard="iso10893_7")
        assert snr_b == 100
        assert "10893" in tbl_b


class TestISO10893DefectEvaluator:
    @pytest.fixture
    def evaluator(self):
        return ISO10893Evaluator()

    def test_crack_and_lack_of_fusion_rejected(self, evaluator):
        # Clause 10.2: Cracks, IP, LOF are not acceptable
        ok, _ = evaluator.evaluate("defect_crack", 10.0, 2.0, 0.5, 2.0)
        assert not ok

        ok, _ = evaluator.evaluate("defect_ip", 10.0, 1.0, 0.5, 1.0)
        assert not ok

        ok, _ = evaluator.evaluate("defect_if", 10.0, 1.0, 0.5, 1.0)
        assert not ok

    def test_circular_porosity_limits(self, evaluator):
        # Clause 10.3: individual diameter <= min(3.0, T/3). For T = 6.0 mm, max = 2.0 mm
        ok, _ = evaluator.evaluate("defect_porosity", 6.0, 1.8, 1.8, 1.8)
        assert ok

        ok, _ = evaluator.evaluate("defect_porosity", 6.0, 2.5, 2.5, 2.5)
        assert not ok

    def test_elongated_slag_limits(self, evaluator):
        # Clause 10.4: individual length <= min(12.0, T), width <= 1.5 mm. For T = 8.0 mm, max L = 8.0 mm
        ok, _ = evaluator.evaluate("defect_slag", 8.0, 7.0, 1.2, 7.0)
        assert ok

        # Exceeding width limit (1.5 mm)
        ok, _ = evaluator.evaluate("defect_slag", 8.0, 7.0, 1.8, 7.0)
        assert not ok

        # Exceeding length limit (8.0 mm)
        ok, _ = evaluator.evaluate("defect_slag", 8.0, 9.0, 1.0, 9.0)
        assert not ok

    def test_undercut_limits(self, evaluator):
        # Clause 10.5: individual undercuts with depth <= 0.4 mm acceptable
        ok, _ = evaluator.evaluate("defect_undercut", 10.0, 15.0, 0.35, 15.0)
        assert ok

        # Depth > 0.5 mm -> reject
        ok, _ = evaluator.evaluate("defect_undercut", 10.0, 3.0, 0.6, 3.0)
        assert not ok


class TestISO10893EngineIntegration:
    @pytest.fixture
    def engine(self):
        return CalculationEngine()

    def test_engine_normalizes_standard(self, engine):
        form = {"standard": "iso10893_7", "od": 114.3, "t": 6.02}
        normalized = normalize_form(form)
        assert normalized["standard"] == "iso10893_7"

    def test_engine_calculates_iso10893(self, engine):
        form = {
            "standard": "iso10893_7",
            "tech": "digital",
            "detector_type": "dda_si",
            "source": "x_ray",
            "material": "steel",
            "testing_class": "class_b",
            "geometry": "swsi",
            "od": 114.3,
            "t": 6.02,
            "cap": 2.0,
            "sfd": 600.0,
            "output_val": 5.0,
            "base_e": 3.0,
            "d": 2.0,
        }
        res = engine.calculate(form)
        assert res is not None
        assert res["display"]["single_wire_iqi"] is not None
        assert "10893-7" in res["display"]["single_wire_iqi"]
        assert "10893-7" in res["display"]["duplex_iqi"]
        # T = 6.02 mm Class B -> W15 per Table 2
        assert res["values"]["wire_no"] == 15
        assert res["values"]["duplex_no"] == 12  # 4 < T <= 8 -> D12 per Table 2
        assert res["values"]["target_snr"] == 100

    def test_procedure_check_dda_voltage_exception(self, engine):
        checker = ProcedureComplianceChecker()
        inputs = {
            "tech": "digital",
            "source": "x_ray",
            "standard": "iso10893_7",
            "detector_type": "dda_si",
            "class": "class_b",
        }
        calculated = {
            "u_max": 145.0,
            "wire_no": 15,
            "duplex_no": 12,
            "target_snr": 100,
        }
        # Applied kV is 160 kV > U_max (145 kV), but DDA with compliant IQI/SNR
        applied = {
            "applied_kv": 160.0,
            "applied_wire": 15,
            "applied_duplex": 12,
            "applied_quality": 120.0,
            "applied_sfd": 600.0,
        }
        res = checker.check_compliance(inputs, calculated, applied, {}, lang="tr")
        # Voltage check should pass due to Clause 6.10 exception
        v_check = next((c for c in res["checks"] if c["name"] == "voltage"), None)
        assert v_check is not None
        assert v_check["status"] is True
        assert "6.10" in v_check["details"]
