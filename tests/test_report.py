# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from src.core.report import PDFReportGenerator
from src.core.translation import Translation


class TestPDFReportGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = PDFReportGenerator()
        self.lang = Translation()
        self.lang.set_language("en")
        self.tmpdir = tempfile.mkdtemp()

    def _make_inputs(self, **overrides):
        defaults = {
            "material_text": "Steel",
            "class_text": "Class B (Improved - API 1104 Preferred)",
            "od": 114.3,
            "t": 8.56,
            "cap": 3.0,
            "d": 2.0,
            "sfd": 600.0,
            "output_val": 5.0,
            "base_e": 3.0,
            "speed": "C5",
            "tech": "digital",
            "tech_text": "Digital (CR/DDA - ISO 17636-2)",
            "source": "x_ray",
            "source_text": "X-Ray Tube",
            "geometry_text": "DWSI (Double Wall Single Image)",
            "input_kv": 120.0,
            "overlap": 10.0,
            "iqi_type": "wire",
            "snr_location": "weld",
        }
        defaults.update(overrides)
        return defaults

    def _make_outputs(self, **overrides):
        defaults = {
            "w_nom": 8.56,
            "w_eff": 11.56,
            "u_max": 130.0,
            "f_min": 215.0,
            "sfd_min": 223.56,
            "exposures": 4,
            "single_wire_iqi": "W10 (0.40 mm)",
            "duplex_iqi": "D10 (0.100 mm)",
            "quality_target": ">= 130 (Max)",
            "calc_time": "180 s",
            "detector_quality": "Max 100 µm",
            "filter_recommendation": "None",
        }
        defaults.update(overrides)
        return defaults

    def test_generate_report_returns_true(self):
        filepath = os.path.join(self.tmpdir, "test_report.pdf")
        result = self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            [], None, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_creates_file(self):
        filepath = os.path.join(self.tmpdir, "test_report.pdf")
        self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            [], None, False, None, self.lang
        )
        self.assertTrue(os.path.exists(filepath))
        self.assertGreater(os.path.getsize(filepath), 1000)

    def test_generate_report_with_warnings(self):
        filepath = os.path.join(self.tmpdir, "test_warn.pdf")
        warnings = ["Warning 1: Test warning message", "Warning 2: Another warning"]
        result = self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            warnings, None, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_with_defect_eval_accept(self):
        filepath = os.path.join(self.tmpdir, "test_defect_accept.pdf")
        defect_eval = {
            "active": True,
            "type_text": "Incomplete Penetration (IP)",
            "len": 15.0,
            "width": 1.0,
            "accum": 20.0,
            "status": True,
            "reason": "IP length 15.0mm ≤ 25.4mm limit. Compliant."
        }
        result = self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            [], defect_eval, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_with_defect_eval_reject(self):
        filepath = os.path.join(self.tmpdir, "test_defect_reject.pdf")
        defect_eval = {
            "active": True,
            "type_text": "Crack",
            "len": 30.0,
            "width": 2.0,
            "accum": 50.0,
            "status": False,
            "reason": "Cracks are unacceptable per API 1104."
        }
        result = self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            [], defect_eval, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_with_level3(self):
        filepath = os.path.join(self.tmpdir, "test_lvl3.pdf")
        result = self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            [], None, True, 150.0, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_with_images(self):
        """Test that report with image paths works (files may not exist)."""
        filepath = os.path.join(self.tmpdir, "test_images.pdf")
        result = self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            [], None, False, None, self.lang,
            dynamic_img_path=None,
            standard_img_path=None
        )
        self.assertTrue(result)

    def test_generate_report_with_analog_inputs(self):
        filepath = os.path.join(self.tmpdir, "test_analog.pdf")
        inputs = self._make_inputs(
            tech="analog",
            tech_text="Analog Film (ISO 17636-1)",
            source="isotope_ir192",
            source_text="Isotope (Ir-192)",
        )
        outputs = self._make_outputs(u_max=None, duplex_iqi="N/A (Analog Film)")
        result = self.gen.generate_report(
            filepath, inputs, outputs,
            [], None, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_turkish(self):
        self.lang.set_language("tr")
        filepath = os.path.join(self.tmpdir, "test_turkish.pdf")
        inputs = self._make_inputs(
            material_text="Çelik",
            class_text="Sınıf B (Gelişmiş - API 1104 Tercihi)",
            tech_text="Analog Film (ISO 17636-1)",
            source_text="İzotop (Ir-192)",
            geometry_text="DWSI (Çift Cidar Tek Görüntü)",
        )
        result = self.gen.generate_report(
            filepath, inputs, self._make_outputs(duplex_iqi="N/A (Analog Film)"),
            [], None, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_with_errors_handled(self):
        """Test that invalid inputs don't crash the report."""
        filepath = os.path.join(self.tmpdir, "test_edge.pdf")
        inputs = self._make_inputs(od=0.0, t=0.0)
        outputs = self._make_outputs(w_nom=0.0, w_eff=0.0)
        result = self.gen.generate_report(
            filepath, inputs, outputs,
            ["Edge case warning"], None, False, None, self.lang
        )
        self.assertTrue(result)

    def test_generate_report_pdf_has_correct_structure(self):
        """Verify PDF content contains expected text."""
        filepath = os.path.join(self.tmpdir, "test_structure.pdf")
        self.gen.generate_report(
            filepath, self._make_inputs(), self._make_outputs(),
            ["Test warning message"], None, False, None, self.lang
        )
        self.assertTrue(os.path.exists(filepath))
        size = os.path.getsize(filepath)
        self.assertGreater(size, 2000, f"PDF too small: {size} bytes")
        # Check it's a valid PDF
        with open(filepath, "rb") as f:
            header = f.read(5)
        self.assertEqual(header, b"%PDF-", "File does not start with PDF header")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
