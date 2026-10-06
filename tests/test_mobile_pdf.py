# -*- coding: utf-8 -*-
"""Mobile PDF report fields (parity with desktop/web).

Regression: the mobile helper passed the raw SNR value as the analog optical
density target, omitted ``base_multiplier`` (so the Field-Factor note never
showed), and left ``detector_quality`` blank.
"""

import os
import tempfile

import pypdf

from src.mobile.lib.pdf_helper import generate_mobile_pdf
from src.mobile.lib.app_state import AppState


def _render(state):
    results = state.run_calculations()
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        ok = generate_mobile_pdf(tmp.name, state, results, state.compliance, None)
        assert ok
        text = "\n".join(
            (page.extract_text() or "") for page in pypdf.PdfReader(tmp.name).pages
        )
    finally:
        os.unlink(tmp.name)
    return text


def _fresh_state():
    AppState._instance = None
    return AppState()


def test_mobile_pdf_analog_quality_and_detector_fields():
    state = _fresh_state()
    state.tech = "analog"
    state.source = "x_ray"
    state.geometry = "swsi"
    state.testing_class = "class_b"
    state.film_class_used = "C4"
    state.base_multiplier = 1.5

    text = _render(state)

    # Analog target is an optical density (>= 2.3), not the raw SNR_N value.
    assert "2.3" in text
    # Detector quality row shows the required film class (was blank before).
    # X-ray 120 kV Class B -> C3 per ISO 17636-1:2022 Table 3.
    assert "C3 Film" in text
    # Field Correction Factor is passed through (was hard-coded 1.00 before).
    assert "1.50" in text


def test_mobile_pdf_digital_quality_target():
    state = _fresh_state()
    state.tech = "digital"
    state.source = "x_ray"
    state.geometry = "swsi"
    state.testing_class = "class_b"

    text = _render(state)

    # Digital target is an SNR_N value with its table reference.
    assert "SNR" in text or "Tablo" in text
