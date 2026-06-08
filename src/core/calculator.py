import math
import os
import logging

logger = logging.getLogger(__name__)

try:
    from src.core.exposure_charts import ExposureChartDatabase, resource_path
except ImportError:
    ExposureChartDatabase = None
    resource_path = lambda p: p

class RTCalculator:
    # -----------------------------------------------------------------------
    # Film Speed Factors — ISO 11699-1 film system classification
    # Reference: C1 as baseline (factor = 1.0, slowest, finest grain, e.g. DR50).
    # Faster films (C4-C6) need LESS exposure; slower films (C1-C2) need MORE.
    # Relative sensitivity approximately doubles per class step.
    # Source: Carestream NDT R-Factor data & ISO 11699-1.
    # -----------------------------------------------------------------------
    FILM_SPEED_FACTORS = {
        "C1": 1.0,    # slowest, finest grain (reference baseline, e.g. DR50)
        "C2": 2.0,    # e.g. M100
        "C3": 4.0,    # e.g. MX125
        "C4": 8.0,    # e.g. T200
        "C5": 16.0,   # e.g. AA400
        "C6": 32.0,   # fastest, coarsest grain (e.g. HS800)
    }

    # -----------------------------------------------------------------------
    # Optical Density (OD) Target Correction
    # Class A: OD >= 2.0  →  factor 1.0 (reference)
    # Class B: OD >= 2.3  →  exposure factor ~ exp(0.3 / G̅) where G̅≈3.0
    #          → (2.3-2.0)/3.0 × ln(10) ≈ 0.23 → factor ≈ 1.25
    # Source: ISO 17636-1 Clause 5.3, ASTM E94 Commentary.
    # -----------------------------------------------------------------------
    OD_CORRECTION = {
        "class_a": 1.00,   # target OD >= 2.0
        "class_b": 1.25,   # target OD >= 2.3  (+25% exposure)
    }

    # ISO 17636-2:2022 Table 2 — Penetrated thickness ranges per source
    # (min, max) in mm, None = no limit for that bound.
    # Source key -> material key -> { "class_a": (min, max), "class_b": (min, max) | None }
    TABLE_2_LIMITS = {
        "isotope_tm170": {
            "steel":          {"class_a": (None, 5),   "class_b": (None, 5)},
            "copper_nickel":  {"class_a": (None, 5),   "class_b": (None, 5)},
        },
        "isotope_yb169": {
            "steel":          {"class_a": (1, 15),     "class_b": (2, 12)},
            "copper_nickel":  {"class_a": (1, 15),     "class_b": (2, 12)},
            "aluminum":       {"class_a": (10, 70),    "class_b": (25, 55)},
            "titanium":       {"class_a": (10, 70),    "class_b": (25, 55)},
        },
        "isotope_se75": {
            "steel":          {"class_a": (10, 40),    "class_b": (14, 40)},
            "copper_nickel":  {"class_a": (10, 40),    "class_b": (14, 40)},
            "aluminum":       {"class_a": (35, 120),   "class_b": None},
            "titanium":       {"class_a": (35, 120),   "class_b": None},
        },
        "isotope_ir192": {
            "steel":          {"class_a": (20, 100),   "class_b": (20, 90)},
            "copper_nickel":  {"class_a": (20, 100),   "class_b": (20, 90)},
        },
        "isotope_co60": {
            "steel":          {"class_a": (40, 200),   "class_b": (60, 150)},
            "copper_nickel":  {"class_a": (40, 200),   "class_b": (60, 150)},
        },
    }

    # X-ray voltage bands for Table 2 (only applies when kv > 1000)
    # (min_w, max_w, kv_min, kv_max) for each band
    XRAY_TABLE2_BANDS = {
        "class_a": [
            (30, 200, 1000, 4000),    # 1 MV < U <= 4 MV
            (50, None, 4000, 12000),  # 4 MV < U <= 12 MV
            (80, None, 12000, None),  # U > 12 MV
        ],
        "class_b": [
            (50, 180, 1000, 4000),
            (80, None, 4000, 12000),
            (100, None, 12000, None),
        ],
    }

    # -----------------------------------------------------------------------
    # Digital Detector Type Factors — relative to CR Standard = 1.0
    # Based on typical Detective Quantum Efficiency (DQE) values:
    #   CR Standard  (BaFBr phosphor plate): DQE ~ 20% → factor 1.0 (ref)
    #   CR High-Res  (fine-grain plate):     DQE ~ 15% → factor 0.75 (slower)
    #   DDA FP Si    (a-Si flat panel):      DQE ~ 60% → factor 4.0
    #   DDA FP Se    (a-Se flat panel):      DQE ~ 50% → factor 3.5
    #   DDA GdOS     (GdOS scintillator DDA):DQE ~ 45% → factor 3.0
    # Source: ISO 17636-2 Annex A, ASTM E2698, manufacturer DQE specs.
    # -----------------------------------------------------------------------
    DETECTOR_TYPE_FACTORS = {
        "cr_standard": 1.0,    # CR standard phosphor plate (Class A/B baseline)
        "cr_highres":  0.75,   # CR high-resolution plate (slower, finer)
        "dda_si":      4.0,    # Flat Panel amorphous silicon (a-Si)
        "dda_se":      3.5,    # Flat Panel amorphous selenium (a-Se)
        "dda_gdos":    3.0,    # DDA with GdOS (Gadolinium Oxysulfide) scintillator
    }

    # -----------------------------------------------------------------------
    # SNR_N Target Correction (Digital) — proportional to √(dose)
    # Class A: SNR_N >= 70   → factor 1.0 (reference)
    # Class B: SNR_N >= 130  → factor (130/70)² ≈ 3.45
    # Source: ISO 17636-2 Clause 7.4.
    # -----------------------------------------------------------------------
    SNR_CORRECTION = {
        "class_a": 1.00,   # SNR_N >= 70
        "class_b": 3.45,   # SNR_N >= 130  (~3.45× more dose)
    }

    def __init__(self):
        # IQI Wire Diameter Tables (ISO 19232-1)
        # Wire number -> diameter in mm
        self.wire_diameters = {
            1: 3.20, 2: 2.50, 3: 2.00, 4: 1.60, 5: 1.25,
            6: 1.00, 7: 0.80, 8: 0.63, 9: 0.50, 10: 0.40,
            11: 0.32, 12: 0.25, 13: 0.20, 14: 0.16, 15: 0.125,
            16: 0.10, 17: 0.08, 18: 0.063, 19: 0.05
        }
        # Step and Hole IQI designations (ISO 19232-2)
        # Hole number -> step thickness / hole diameter in mm
        self.step_hole_dias = {
            1: 0.125, 2: 0.160, 3: 0.200, 4: 0.250, 5: 0.320,
            6: 0.400, 7: 0.500, 8: 0.630, 9: 0.800, 10: 1.000,
            11: 1.250, 12: 1.600, 13: 2.000, 14: 2.500, 15: 3.200,
            16: 4.000, 17: 5.000, 18: 6.300
        }


    def calculate_thicknesses(self, t, cap, geometry):
        """
        Calculates nominal and effective penetrated thicknesses (Step 4)
        """
        if geometry in ["swsi"]:
            w_nom = t
            w_eff = t + cap
        else:  # dwsi, dwdi_elliptic, dwdi_super
            w_nom = 2 * t
            w_eff = 2 * t + cap
        return w_nom, w_eff

    def calculate_u_max(self, w_nom, material):
        """
        Calculates maximum tube voltage (U_max) in kV (Step 5)
        Ref: ISO 17636-1 Annex C Table C.1 - dual-range approximation formulas.
        For SWSI: w_nom = t (single wall). For DWSI/DWDI: w_nom = 2t.
        """
        w = w_nom
        if material == "steel":
            if w <= 10.0:
                return 100.0 + 7.5 * w
            else:
                return 40.0 * (w ** 0.64)
        elif material == "aluminum":
            if w <= 10.0:
                return 40.0 + 2.5 * w
            else:
                return 24.0 * (w ** 0.43)
        elif material == "titanium":
            if w <= 10.0:
                return 70.0 + 4.0 * w
            else:
                return 35.0 * (w ** 0.50)
        elif material == "copper_nickel":
            if w <= 10.0:
                return 120.0 + 9.0 * w
            else:
                return 48.0 * (w ** 0.65)
        else:
            # Default: steel
            if w <= 10.0:
                return 100.0 + 7.5 * w
            else:
                return 40.0 * (w ** 0.64)

    def calculate_f_min(self, d, b, testing_class, t=None):
        """
        Calculates minimum source-to-object distance (f_min) in mm (Step 6)
        Formula: f >= C * d * b^(2/3)
        Class A: C = 7.5
        Class B: C = 15
        Per ISO 17636-2:2022 Clause 7.6: If b < 1.2t, b is replaced by t.
        """
        if testing_class == "class_a":
            c = 7.5
        else:
            c = 15.0

        b_eff = b
        # Per Clause 7.6: if b < 1.2t, use b = t instead
        if t is not None and b < 1.2 * t:
            b_eff = t

        f_min = c * d * (b_eff ** (2/3))
        return f_min

    def get_effective_b(self, b, t):
        """
        Returns (b_eff, applied) per ISO 17636-2:2022 Clause 7.6.
        If b < 1.2t, returns b_eff = t with applied = True.
        Otherwise returns b_eff = b with applied = False.
        """
        if t is not None and b < 1.2 * t:
            return t, True
        return b, False

    def calculate_geometric_unsharpness(self, d, b, f):
        """
        Calculates geometric unsharpness (Ug) in mm.
        Formula: Ug = d * b / f
        ISO 17636-2:2022 Clause 7.6 (implied by geometric requirements).
        """
        if f <= 0:
            return 0.0
        return d * b / f

    def calculate_f_min_star(self, d, b, t, testing_class):
        """
        Calculates f_min* for planar/curved detectors per ISO 17636-2:2022 Clause 7.6.
        Formula (13): f_min* = f_min(b=t) × (b/t)^(1/3) when b/t > 1.2.
        Returns (f_min_star, ci_factor) where ci_factor = (b/t)^(1/3).
        If b/t <= 1.2, returns (None, None) — magnification rule does not apply.
        """
        if b <= 1.2 * t:
            return None, None

        # f_min computed with b = t (per Clause 7.6 b<1.2t rule)
        ci = (b / t) ** (1.0 / 3.0)
        f_min_at_t = self.calculate_f_min(d, t, testing_class, t)  # t ensures b_eff = t
        f_min_star = f_min_at_t * ci
        return f_min_star, ci

    def calculate_sdd_min(self, dd):
        """
        Calculates minimum Source-to-Detector Distance (SDD_min) per ISO 17636-2:2022 Clause 7.6.
        Simplified Formula (7): for 2beta = 40° (typical NDT tube opening angle), SDD >= 1.4 * dd.
        If dd is None or <= 0, returns 0 (no constraint).
        """
        if dd is None or dd <= 0:
            return 0.0
        return 1.4 * dd

    def is_central_projection(self, geometry, std_figure):
        """
        Returns True if the setup is central projection (Figure 5):
        SWSI + standard figure = fig5 (panoramic central source).
        """
        return geometry == "swsi" and std_figure == "fig5"

    def is_double_wall_technique(self, geometry):
        """
        Returns True for double-wall techniques (DWSI, DWDI).
        Per Clause 7.6, these allow up to 20% f_min reduction.
        """
        return geometry in ["dwsi", "dwdi_elliptic", "dwdi_super"]

    def calculate_b_curved(self, bed, bgap, t, testing_class):
        """
        Calculates object-to-detector distance b for curved/planar detectors.
        Formula (8) Class A: b = bed + bgap + 1.2 * t
        Formula (9) Class B: b = bed + bgap + 1.1 * t
        ISO 17636-2:2022 Clause 7.6, Figures 2b, 8b, 13b, 14b.
        """
        k = 1.2 if testing_class == "class_a" else 1.1
        return bed + bgap + k * t

    def calculate_b_panoramic(self, bed, bgap, t):
        """
        Calculates object-to-detector distance b for panoramic central projection.
        Formula (11): b = bed + bgap + t
        ISO 17636-2:2022 Clause 7.6, Figure 5b.
        """
        return bed + bgap + t

    def check_annex_f_compensation(self, ug, max_srb):
        """
        Checks if Annex F IQI visibility compensation is needed.
        Ug / SRb_detector <= 2 -> no compensation needed.
        Ug / SRb_detector > 2 -> compensation needed (increase f_min or SNR).
        Returns (needs_compensation, ratio).
        """
        if max_srb <= 0:
            return False, 0.0
        ratio = ug / (max_srb / 1000.0)  # max_srb in µm -> mm
        return ratio > 2.0, ratio

    def get_single_wire_iqi(self, t, cap, testing_class, geometry, tech="digital", film_side=False, lang="tr"):
        """
        Determines target single wire IQI number (Step 8)
        Based on ISO 17636-1 Annex B for Analog, ISO 17636-2 Annex B for Digital.
        """
        # Cap ratio control
        ratio = cap / t if t > 0 else 0.0
        include_cap = ratio > 0.20

        # Reference thickness calculation (ref_thickness)
        if geometry == "dwsi":
            # DWSI: ref = 2 * t (+ cap if ratio > 0.20)
            # Both analog and digital use double-wall thickness for single wire IQI
            ref_thickness = 2 * t + cap if include_cap else 2 * t
        elif geometry in ["dwdi_elliptic", "dwdi_super"]:
            # DWDI: ref = 2 * t (+ cap if ratio > 0.20)
            ref_thickness = 2 * t + cap if include_cap else 2 * t
        else:
            # SWSI: ref = t (+ cap if ratio > 0.20)
            ref_thickness = t + cap if include_cap else t

        if film_side:
            # Film-side (detector-side) tables: Table B.9 (Class A) / Table B.11 (Class B)
            if testing_class == "class_a":
                # Table B.9 — Class A, film side
                if ref_thickness <= 1.2:
                    wire = 18
                elif ref_thickness <= 2.0:
                    wire = 17
                elif ref_thickness <= 3.5:
                    wire = 16
                elif ref_thickness <= 5.0:
                    wire = 15
                elif ref_thickness <= 10.0:
                    wire = 14
                elif ref_thickness <= 15.0:
                    wire = 13
                elif ref_thickness <= 22.0:
                    wire = 12
                elif ref_thickness <= 38.0:
                    wire = 11
                elif ref_thickness <= 54.0:
                    wire = 10
                elif ref_thickness <= 70.0:
                    wire = 9
                elif ref_thickness <= 100.0:
                    wire = 8
                elif ref_thickness <= 170.0:
                    wire = 7
                elif ref_thickness <= 250.0:
                    wire = 6
                else:
                    wire = 5
            else:
                # Table B.11 — Class B, film side
                if ref_thickness <= 1.5:
                    wire = 19
                elif ref_thickness <= 2.5:
                    wire = 18
                elif ref_thickness <= 4.0:
                    wire = 17
                elif ref_thickness <= 6.0:
                    wire = 16
                elif ref_thickness <= 8.0:
                    wire = 15
                elif ref_thickness <= 12.0:
                    wire = 14
                elif ref_thickness <= 20.0:
                    wire = 13
                elif ref_thickness <= 30.0:
                    wire = 12
                elif ref_thickness <= 45.0:
                    wire = 11
                elif ref_thickness <= 65.0:
                    wire = 10
                elif ref_thickness <= 100.0:
                    wire = 9
                elif ref_thickness <= 170.0:
                    wire = 8
                elif ref_thickness <= 250.0:
                    wire = 7
                else:
                    wire = 6
        else:
            # Source-side tables:
            # SWSI or DWSI: Tables B.1 (Class A) / B.3 (Class B)
            # DWDI: Tables B.5 (Class A) / B.7 (Class B)
            if testing_class == "class_a":
                if geometry in ["swsi", "dwsi"]:
                    # Table B.1 — Class A, source side
                    if ref_thickness <= 1.2:
                        wire = 18
                    elif ref_thickness <= 2.0:
                        wire = 17
                    elif ref_thickness <= 3.5:
                        wire = 16
                    elif ref_thickness <= 5.0:
                        wire = 15
                    elif ref_thickness <= 7.0:
                        wire = 14
                    elif ref_thickness <= 10.0:
                        wire = 13
                    elif ref_thickness <= 15.0:
                        wire = 12
                    elif ref_thickness <= 25.0:
                        wire = 11
                    elif ref_thickness <= 40.0:
                        wire = 10
                    elif ref_thickness <= 60.0:
                        wire = 9
                    elif ref_thickness <= 80.0:
                        wire = 8
                    elif ref_thickness <= 100.0:
                        wire = 7
                    elif ref_thickness <= 150.0:
                        wire = 6
                    elif ref_thickness <= 200.0:
                        wire = 5
                    elif ref_thickness <= 250.0:
                        wire = 4
                    else:
                        wire = 3
                else:
                    # Table B.5 — Class A, source side, DWDI
                    if ref_thickness <= 1.2:
                        wire = 18
                    elif ref_thickness <= 2.0:
                        wire = 17
                    elif ref_thickness <= 3.5:
                        wire = 16
                    elif ref_thickness <= 5.0:
                        wire = 15
                    elif ref_thickness <= 7.0:
                        wire = 14
                    elif ref_thickness <= 12.0:
                        wire = 13
                    elif ref_thickness <= 18.0:
                        wire = 12
                    elif ref_thickness <= 30.0:
                        wire = 11
                    elif ref_thickness <= 40.0:
                        wire = 10
                    elif ref_thickness <= 50.0:
                        wire = 9
                    elif ref_thickness <= 60.0:
                        wire = 8
                    elif ref_thickness <= 85.0:
                        wire = 7
                    elif ref_thickness <= 120.0:
                        wire = 6
                    elif ref_thickness <= 220.0:
                        wire = 5
                    elif ref_thickness <= 380.0:
                        wire = 4
                    else:
                        wire = 3
            else:
                if geometry in ["swsi", "dwsi"]:
                    # Table B.3 — Class B, source side
                    if ref_thickness <= 1.5:
                        wire = 19
                    elif ref_thickness <= 2.5:
                        wire = 18
                    elif ref_thickness <= 4.0:
                        wire = 17
                    elif ref_thickness <= 6.0:
                        wire = 16
                    elif ref_thickness <= 8.0:
                        wire = 15
                    elif ref_thickness <= 12.0:
                        wire = 14
                    elif ref_thickness <= 20.0:
                        wire = 13
                    elif ref_thickness <= 30.0:
                        wire = 12
                    elif ref_thickness <= 40.0:
                        wire = 11
                    elif ref_thickness <= 60.0:
                        wire = 10
                    elif ref_thickness <= 85.0:
                        wire = 9
                    elif ref_thickness <= 125.0:
                        wire = 8
                    elif ref_thickness <= 175.0:
                        wire = 7
                    elif ref_thickness <= 250.0:
                        wire = 6
                    else:
                        wire = 5
                else:
                    # Table B.7 — Class B, source side, DWDI
                    if ref_thickness <= 1.5:
                        wire = 19
                    elif ref_thickness <= 2.5:
                        wire = 18
                    elif ref_thickness <= 4.0:
                        wire = 17
                    elif ref_thickness <= 6.0:
                        wire = 16
                    elif ref_thickness <= 8.0:
                        wire = 15
                    elif ref_thickness <= 15.0:
                        wire = 14
                    elif ref_thickness <= 25.0:
                        wire = 13
                    elif ref_thickness <= 38.0:
                        wire = 12
                    elif ref_thickness <= 45.0:
                        wire = 11
                    elif ref_thickness <= 55.0:
                        wire = 10
                    elif ref_thickness <= 70.0:
                        wire = 9
                    elif ref_thickness <= 100.0:
                        wire = 8
                    elif ref_thickness <= 170.0:
                        wire = 7
                    elif ref_thickness <= 250.0:
                        wire = 6
                    else:
                        wire = 5

        # Determine table name and thickness description
        if film_side:
            if testing_class == "class_a":
                table_name = "Table B.9" if lang == "en" else "Tablo B.9"
            else:
                table_name = "Table B.11" if lang == "en" else "Tablo B.11"
        else: # source side
            if testing_class == "class_a":
                if geometry in ["swsi", "dwsi"]:
                    table_name = "Table B.1" if lang == "en" else "Tablo B.1"
                else:
                    table_name = "Table B.5" if lang == "en" else "Tablo B.5"
            else: # class B
                if geometry in ["swsi", "dwsi"]:
                    table_name = "Table B.3" if lang == "en" else "Tablo B.3"
                else:
                    table_name = "Table B.7" if lang == "en" else "Tablo B.7"

        # Reference thickness text
        if geometry == "dwsi":
            t_label = "2 * t"
        elif geometry in ["dwdi_elliptic", "dwdi_super"]:
            t_label = "2 * t"
        else:
            t_label = "t"

        thickness_desc = f"{t_label} = {ref_thickness:.2f} mm"

        dia = self.wire_diameters.get(wire, 0.0)
        display_str = f"W {wire} ({dia:.3f} mm) [{table_name}, {thickness_desc}]"
        return display_str, wire

    def get_step_hole_iqi(self, t, cap, testing_class, geometry, tech="digital", film_side=False, lang="tr"):
        """
        Determines target step-and-hole IQI number (designator H1-H18)
        Based on ISO 17636-1/2 Annex B tables B.2, B.4, B.6, B.8, B.10, B.12.
        """
        # Cap ratio control
        ratio = cap / t if t > 0 else 0.0
        include_cap = ratio > 0.20

        # Reference thickness calculation (ref_thickness)
        if geometry == "dwsi":
            # DWSI: ref = 2 * t (+ cap if ratio > 0.20)
            # Both analog and digital use double-wall thickness for single IQI
            ref_thickness = 2 * t + cap if include_cap else 2 * t
        elif geometry in ["dwdi_elliptic", "dwdi_super"]:
            ref_thickness = 2 * t + cap if include_cap else 2 * t
        else:
            ref_thickness = t + cap if include_cap else t

        if film_side:
            # Film-side (detector-side) tables: Table B.10 (Class A) / Table B.12 (Class B)
            if testing_class == "class_a":
                # Table B.10 — Class A, film/detector side
                if ref_thickness <= 2.0:
                    hole = 3
                elif ref_thickness <= 5.0:
                    hole = 4
                elif ref_thickness <= 9.0:
                    hole = 5
                elif ref_thickness <= 14.0:
                    hole = 6
                elif ref_thickness <= 22.0:
                    hole = 7
                elif ref_thickness <= 36.0:
                    hole = 8
                elif ref_thickness <= 50.0:
                    hole = 9
                else:
                    hole = 10
            else:
                # Table B.12 — Class B, film/detector side
                if ref_thickness <= 2.5:
                    hole = 2
                elif ref_thickness <= 5.5:
                    hole = 3
                elif ref_thickness <= 9.5:
                    hole = 4
                elif ref_thickness <= 15.0:
                    hole = 5
                elif ref_thickness <= 24.0:
                    hole = 6
                elif ref_thickness <= 40.0:
                    hole = 7
                elif ref_thickness <= 60.0:
                    hole = 8
                else:
                    hole = 9
        else:
            # Source-side tables:
            # SWSI or DWSI: Tables B.2 (Class A) / B.4 (Class B)
            # DWDI: Tables B.6 (Class A) / B.8 (Class B)
            if testing_class == "class_a":
                if geometry in ["swsi", "dwsi"]:
                    # Table B.2 — Class A, source side
                    if ref_thickness <= 2.0:
                        hole = 3
                    elif ref_thickness <= 3.5:
                        hole = 4
                    elif ref_thickness <= 6.0:
                        hole = 5
                    elif ref_thickness <= 10.0:
                        hole = 6
                    elif ref_thickness <= 15.0:
                        hole = 7
                    elif ref_thickness <= 24.0:
                        hole = 8
                    elif ref_thickness <= 30.0:
                        hole = 9
                    elif ref_thickness <= 40.0:
                        hole = 10
                    elif ref_thickness <= 60.0:
                        hole = 11
                    elif ref_thickness <= 100.0:
                        hole = 12
                    elif ref_thickness <= 150.0:
                        hole = 13
                    elif ref_thickness <= 200.0:
                        hole = 14
                    elif ref_thickness <= 250.0:
                        hole = 15
                    elif ref_thickness <= 320.0:
                        hole = 16
                    elif ref_thickness <= 400.0:
                        hole = 17
                    else:
                        hole = 18
                else:
                    # Table B.6 — Class A, source side, DWDI
                    if ref_thickness <= 1.0:
                        hole = 3
                    elif ref_thickness <= 2.0:
                        hole = 4
                    elif ref_thickness <= 3.5:
                        hole = 5
                    elif ref_thickness <= 5.5:
                        hole = 6
                    elif ref_thickness <= 10.0:
                        hole = 7
                    elif ref_thickness <= 19.0:
                        hole = 8
                    else:
                        hole = 9
            else:
                if geometry in ["swsi", "dwsi"]:
                    # Table B.4 — Class B, source side
                    if ref_thickness <= 2.5:
                        hole = 2
                    elif ref_thickness <= 4.0:
                        hole = 3
                    elif ref_thickness <= 8.0:
                        hole = 4
                    elif ref_thickness <= 12.0:
                        hole = 5
                    elif ref_thickness <= 20.0:
                        hole = 6
                    elif ref_thickness <= 30.0:
                        hole = 7
                    elif ref_thickness <= 40.0:
                        hole = 8
                    elif ref_thickness <= 60.0:
                        hole = 9
                    elif ref_thickness <= 80.0:
                        hole = 10
                    elif ref_thickness <= 100.0:
                        hole = 11
                    elif ref_thickness <= 150.0:
                        hole = 12
                    elif ref_thickness <= 200.0:
                        hole = 13
                    else:
                        hole = 14
                else:
                    # Table B.8 — Class B, source side, DWDI
                    if ref_thickness <= 1.0:
                        hole = 2
                    elif ref_thickness <= 2.5:
                        hole = 3
                    elif ref_thickness <= 4.0:
                        hole = 4
                    elif ref_thickness <= 6.0:
                        hole = 5
                    elif ref_thickness <= 11.0:
                        hole = 6
                    elif ref_thickness <= 20.0:
                        hole = 7
                    else:
                        hole = 8

        # Determine table name and thickness description
        if film_side:
            if testing_class == "class_a":
                table_name = "Table B.10" if lang == "en" else "Tablo B.10"
            else:
                table_name = "Table B.12" if lang == "en" else "Tablo B.12"
        else: # source side
            if testing_class == "class_a":
                if geometry in ["swsi", "dwsi"]:
                    table_name = "Table B.2" if lang == "en" else "Tablo B.2"
                else:
                    table_name = "Table B.6" if lang == "en" else "Tablo B.6"
            else: # class B
                if geometry in ["swsi", "dwsi"]:
                    table_name = "Table B.4" if lang == "en" else "Tablo B.4"
                else:
                    table_name = "Table B.8" if lang == "en" else "Tablo B.8"

        # Reference thickness text
        if geometry == "dwsi":
            t_label = "2 * t"
        elif geometry in ["dwdi_elliptic", "dwdi_super"]:
            t_label = "2 * t"
        else:
            t_label = "t"

        thickness_desc = f"{t_label} = {ref_thickness:.2f} mm"

        dia = self.step_hole_dias.get(hole, 0.0)
        display_str = f"H {hole} ({dia:.3f} mm) [{table_name}, {thickness_desc}]"
        return display_str, hole

    def get_target_snr(self, material, source, kv, w_nom, testing_class, lang="tr"):
        """
        Determines target baseline SNR_N based on ISO 17636-2 Table 3 and Table 4.
        Returns: (target_snr, table_name, selection_desc)
        """
        table_3_title = "Table 3" if lang == "en" else "Tablo 3"
        table_4_title = "Table 4" if lang == "en" else "Tablo 4"

        # Clamping defaults for parameters
        if kv is None:
            kv = 120.0

        if material in ["steel", "copper_nickel"]:
            table_name = f"ISO 17636-2 {table_3_title}"
            # Table 3 Selection
            if source == "x_ray":
                if kv <= 50.0:
                    base_snr = 100 if testing_class == "class_a" else 150
                    desc = f"X-Ray (U <= 50 kV)"
                elif kv <= 150.0:
                    base_snr = 70 if testing_class == "class_a" else 120
                    desc = f"X-Ray (50 kV < U <= 150 kV)"
                elif kv <= 250.0:
                    base_snr = 70 if testing_class == "class_a" else 100
                    desc = f"X-Ray (150 kV < U <= 250 kV)"
                elif kv <= 1000.0:
                    if w_nom <= 50.0:
                        base_snr = 70 if testing_class == "class_a" else 100
                        desc = f"X-Ray (250 kV < U <= 1000 kV, w <= 50 mm)"
                    else:
                        base_snr = 70 if testing_class == "class_a" else 70
                        desc = f"X-Ray (250 kV < U <= 1000 kV, w > 50 mm)"
                else: # > 1000 kV
                    if w_nom <= 100.0:
                        base_snr = 70 if testing_class == "class_a" else 100
                        desc = f"X-Ray (U > 1000 kV, w <= 100 mm)"
                    else:
                        base_snr = 70 if testing_class == "class_a" else 70
                        desc = f"X-Ray (U > 1000 kV, w > 100 mm)"
            elif source == "isotope_se75" or source == "isotope_ir192":
                if w_nom <= 50.0:
                    base_snr = 70 if testing_class == "class_a" else 100
                    src_name = "Se-75" if source == "isotope_se75" else "Ir-192"
                    desc = f"{src_name} (w <= 50 mm)"
                else:
                    base_snr = 70 if testing_class == "class_a" else 70
                    src_name = "Se-75" if source == "isotope_se75" else "Ir-192"
                    desc = f"{src_name} (w > 50 mm)"
            elif source == "isotope_co60":
                if w_nom <= 100.0:
                    base_snr = 70 if testing_class == "class_a" else 100
                    desc = f"Co-60 (w <= 100 mm)"
                else:
                    base_snr = 70 if testing_class == "class_a" else 70
                    desc = f"Co-60 (w > 100 mm)"
            else: # generic fallback
                base_snr = 70 if testing_class == "class_a" else 100
                desc = f"{source}"
        else: # aluminum, titanium
            table_name = f"ISO 17636-2 {table_4_title}"
            # Table 4 Selection
            if source == "x_ray":
                if kv <= 150.0:
                    base_snr = 70 if testing_class == "class_a" else 120
                    desc = f"X-Ray (U <= 150 kV)"
                else:
                    base_snr = 70 if testing_class == "class_a" else 100
                    desc = f"X-Ray (150 kV < U <= 500 kV)"
            elif source == "isotope_se75":
                base_snr = 70 if testing_class == "class_a" else 100
                desc = f"Se-75"
            elif source in ["isotope_ir192", "isotope_co60"]:
                base_snr = 70 if testing_class == "class_a" else 100
                src_name = "Ir-192" if source == "isotope_ir192" else "Co-60"
                desc = f"{src_name} (limited applicability on light metals)"
            else: # generic fallback
                base_snr = 70 if testing_class == "class_a" else 100
                desc = f"{source}"

        return base_snr, table_name, desc

    def get_duplex_iqi(self, w_nom, testing_class, geometry="swsi", lang="tr"):
        """
        Determines target duplex wire IQI D-number (Step 8, Digital ONLY)
        Reference: ISO 17636-2:2022 Annex B Tables B.13 (Class A) and B.14 (Class B).
        Per footnote a: For DWSI (double-wall single-image), the nominal thickness t
        shall be used instead of the penetrated thickness w.
        - SWSI: single wall, ref = w_nom = t
        - DWSI: single wall per footnote a, ref = w_nom / 2 = t
        - DWDI: double wall, ref = w_nom = 2t
        D-wire diameters per ISO 19232-5:
          D14=0.040mm, D13=0.050mm, D12=0.063mm, D11=0.080mm, D10=0.100mm,
          D9=0.125mm, D8=0.160mm, D7=0.200mm, D6=0.250mm, D5=0.320mm
        Returns tuple of (display_string, integer_number)
        """
        # Select reference thickness per ISO footnote a
        if geometry == "dwsi":
            ref = w_nom / 2.0  # single wall thickness t
        else:
            ref = w_nom

        # D-wire diameters per ISO 19232-5
        d_wire_diameters = {
            14: 0.040, 13: 0.050, 12: 0.063, 11: 0.080, 10: 0.100,
            9: 0.125, 8: 0.160, 7: 0.200, 6: 0.250, 5: 0.320
        }

        if testing_class == "class_a":
            # Table B.13 — Class A (ISO 17636-2:2022)
            table_name = "ISO 17636-2 Table B.13" if lang == "en" else "ISO 17636-2 Tablo B.13"
            if ref <= 1.0:
                d_val, d_num = "D 13", 13
            elif ref <= 1.5:
                d_val, d_num = "D 12", 12
            elif ref <= 2.0:
                d_val, d_num = "D 11", 11
            elif ref <= 5.0:
                d_val, d_num = "D 10", 10
            elif ref <= 10.0:
                d_val, d_num = "D 9", 9
            elif ref <= 25.0:
                d_val, d_num = "D 8", 8
            elif ref <= 55.0:
                d_val, d_num = "D 7", 7
            elif ref <= 150.0:
                d_val, d_num = "D 6", 6
            elif ref <= 250.0:
                d_val, d_num = "D 5", 5
            else:
                d_val, d_num = "D 4", 4
        else:  # Class B
            # Table B.14 — Class B (ISO 17636-2:2022)
            table_name = "ISO 17636-2 Table B.14" if lang == "en" else "ISO 17636-2 Tablo B.14"
            if ref <= 1.5:
                d_val, d_num = "D 14", 14
            elif ref <= 4.0:
                d_val, d_num = "D 13", 13
            elif ref <= 8.0:
                d_val, d_num = "D 12", 12
            elif ref <= 12.0:
                d_val, d_num = "D 11", 11
            elif ref <= 40.0:
                d_val, d_num = "D 10", 10
            elif ref <= 120.0:
                d_val, d_num = "D 9", 9
            elif ref <= 200.0:
                d_val, d_num = "D 8", 8
            else:
                d_val, d_num = "D 7", 7
        dia = d_wire_diameters.get(d_num, 0.0)

        if geometry == "dwsi":
            if lang == "en":
                thickness_desc = f"single wall t = {ref:.2f} mm"
            else:
                thickness_desc = f"tek cidar t = {ref:.2f} mm"
        else:
            if lang == "en":
                thickness_desc = f"penetrated w = {ref:.2f} mm"
            else:
                thickness_desc = f"ışınlanan w = {ref:.2f} mm"

        d_str = f"{d_val} ({dia:.3f} mm) [{table_name}, {thickness_desc}]"
        return d_str, d_num

    def calculate_dwsi_exposures(self, OD, t, sfd, testing_class):
        """
        Calculates the required minimum number of exposures for DWSI geometry (Step 3/4)
        Based on limiting the increase of penetrated thickness at the edge of the
        diagnostic length to:
        - Class A: +20% (tolerance = 0.20)
        - Class B: +10% (tolerance = 0.10)
        """
        R = OD / 2.0
        Ri = R - t
        y_s = sfd - R  # Source y-coordinate, assuming detector center is at (0, -R) and source at (0, sfd-R)

        tolerance = 0.20 if testing_class == "class_a" else 0.10
        limit_thickness = t * (1.0 + tolerance)

        # We need to find theta (in radians) such that the ray from S(0, y_s) to P(R*sin(theta), -R*cos(theta))
        # has a penetrated thickness equal to limit_thickness.
        # We can use binary search to solve for theta.
        low = 0.0
        high = math.pi / 2.0  # Max search angle is 90 degrees
        max_theta = 0.0

        for _ in range(50):  # 50 iterations is more than enough for precision
            mid = (low + high) / 2.0
            
            # Point P on outer circle
            px = R * math.sin(mid)
            py = -R * math.cos(mid)

            # Ray parameters
            # A = px^2 + (py - y_s)^2
            # B = 2 * py * (py - y_s) + 2 * px * px ? No, let's write it standard:
            # Let line be S + u * (P - S)
            # S = (0, y_s), P = (px, py)
            # x(u) = u * px
            # y(u) = y_s + u * (py - y_s)
            # x^2 + y^2 = Ri^2 -> u^2 * px^2 + (y_s + u*(py - y_s))^2 = Ri^2
            # u^2 * (px^2 + (py - y_s)^2) + 2 * u * y_s * (py - y_s) + y_s^2 - Ri^2 = 0
            # A_eq * u^2 + B_eq * u + C_eq = 0
            A_eq = px**2 + (py - y_s)**2
            B_eq = 2 * y_s * (py - y_s)
            C_eq = y_s**2 - Ri**2

            disc = B_eq**2 - 4 * A_eq * C_eq
            if disc < 0:
                # Ray doesn't intersect inner circle, which means it missed the inner pipe core completely
                # (very extreme angle, thicker than limit).
                high = mid
                continue

            # We solve for u. Since the intersection point is close to P (u=1), we take the larger u
            u1 = (-B_eq + math.sqrt(disc)) / (2 * A_eq)
            u2 = (-B_eq - math.sqrt(disc)) / (2 * A_eq)
            
            # The root we want is the one closest to 1 (usually the larger one u < 1)
            u = max(u1, u2)
            
            # Intersection point
            # ix = u * px
            # iy = y_s + u * (py - y_s)
            # Distance from I to P
            w_theta = (1.0 - u) * math.sqrt(A_eq)

            if w_theta <= limit_thickness:
                max_theta = mid
                low = mid  # Try to find a larger angle
            else:
                high = mid  # The thickness is too large, search smaller angles

        # If max_theta is 0, default to 3 exposures
        if max_theta <= 0.001:
            return 3

        # Number of exposures N >= pi / max_theta
        N = math.pi / max_theta
        return max(3, int(math.ceil(N)))  # Minimum 3 exposures for DWSI in pipeline codes

    def calculate_exposure_time(self, sfd, w_eff, source, output_val, base_factor,
                                 tech, testing_class="class_b",
                                 film_class="C5", detector_type="cr_standard",
                                 kv=None, material="steel",
                                 chart_source=None, chart_db=None,
                                 film_model=None, density=2.0):
        """
        Calculates exposure time in minutes and seconds (Step 10).

        ── CHART-BASED ROUTING ────────────────────────────────────────────────
        When chart_source is specified, calculation routes through manufacturer
        exposure chart data instead of the physics model:

          chart_source = "AA400" (or other film key)
              → SCRATA slide rule formula using Carestream R-Factor tables:
                t = 60 × R × 10^((D-2)/2) × (SFD/1000)² × 2^(w/HVL) / (A × Γ)

          chart_source = "type_x"
              → Type X exposure chart data (from physics model or real chart)

          chart_source = None (default)
              → Physics model (backward compatible)

        ── PHYSICS MODEL ──────────────────────────────────────────────────────
        Base formula (Inverse Square Law + material attenuation):

            H_required [mA·min/m²  or  Ci·min/m²]
                = base_factor × exp(mu × w_eff)

            t [min] = H_required × (SFD_m)² / output_val

        where:
          base_factor   — source-specific exposure chart constant
                          (calibrated to SNR_N=70 with CR Standard or OD=2.0 with C6 film, at 1 m)
                          X-Ray: 3.0 mA·min/m²  |  Ir-192: 30.0 Ci·min/m²
                          Se-75: 40.0 Ci·min/m² |  Co-60:  20.0 Ci·min/m²
          mu            — linear attenuation coefficient [mm⁻¹], source/material dependent
          SFD_m         — source-to-detector distance in metres  (sfd / 1000)
          output_val    — tube current [mA] for X-ray; source activity [Ci] for isotopes

        ── ANALOG FILM CORRECTION ─────────────────────────────────────────────
        t_analog = t_base × OD_correction / film_speed_factor

          film_speed_factor  — from FILM_SPEED_FACTORS[film_class]  (ISO 11699-1)
                               C1 = 1.0 (slowest), C2 = 2.0, C3 = 4.0,
                               C4 = 8.0, C5 = 16.0, C6 = 32.0 (fastest)
          OD_correction      — from OD_CORRECTION[testing_class]
                               Class A (OD ≥ 2.0) = 1.00
                               Class B (OD ≥ 2.3) = 1.25  (25% more exposure for deeper OD)

        ── DIGITAL DETECTOR CORRECTION ────────────────────────────────────────
        t_digital = t_base × SNR_correction / detector_type_factor

          detector_type_factor — from DETECTOR_TYPE_FACTORS[detector_type]  (ISO 17636-2 + DQE)
                                 CR Standard  (DQE ~20%) = 1.0 (baseline)
                                 CR High-Res  (DQE ~15%) = 0.75
                                 DDA a-Si     (DQE ~60%) = 4.0
                                 DDA a-Se     (DQE ~50%) = 3.5
                                 DDA GdOS     (DQE ~45%) = 3.0
          SNR_correction       — from SNR_CORRECTION[testing_class]
                                 Class A (SNR_N ≥ 70)  = 1.00
                                 Class B (SNR_N ≥ 130) = 3.45  (∝ (130/70)²)

        ── kVp⁵ SANITY CHECK (X-ray only) ─────────────────────────────────────
        When kv is specified with source="x_ray", the result is compared against
        the kVp⁵ rule: t_ratio ≈ (kV_ref / kV_new)⁵. A warning is logged if
        the deviation exceeds 30%.

        ── REFERENCES ─────────────────────────────────────────────────────────
          ISO 17636-1:2013 Clause 8   (Analog film)
          ISO 17636-2:2013 Clause 8   (Digital)
          ISO 11699-1:2008             (Film classification & speed)
          ISO 17636-2:2013 Annex A    (DQE data for CR/DDA)
          ASTM E94-17                  (Exposure chart methodology)
          SCRATA Slide Rule            (R-Factor + gamma constants)
        """
        # ── Chart-based routing ───────────────────────────────────────────────
        if chart_source is not None and chart_source != "model":
            if chart_db is None:
                if ExposureChartDatabase is not None:
                    json_path = resource_path("exposure_chart_dataset.json")
                    if os.path.exists(json_path):
                        chart_db = ExposureChartDatabase(json_path)
                    else:
                        chart_db = ExposureChartDatabase()
                else:
                    raise ImportError("ExposureChartDatabase not available; cannot use chart_source")

            resolved_film = self._resolve_chart_film(chart_source, film_model, film_class)

            # Type X chart path
            if chart_source == "type_x":
                if source != "x_ray":
                    logger.warning("Type X chart is for X-ray only; falling back to physics model")
                else:
                    result = self._calc_from_type_x(chart_db, kv, w_eff, output_val, sfd)
                    if result is not None and result > 0:
                        time_seconds = min(864000.0, result * 60.0)
                        minutes = int(time_seconds // 60)
                        seconds = int(time_seconds % 60)
                        return minutes, seconds, time_seconds

            # R-Factor (film) chart path
            elif resolved_film is not None:
                r_factor = chart_db.lookup_r_factor(resolved_film, source)
                if r_factor is not None:
                    result = self._calc_from_rfactor(
                        chart_db, resolved_film, source, sfd, w_eff, output_val, density
                    )
                    if result is not None and result > 0:
                        time_seconds = min(864000.0, result * 60.0)
                        minutes = int(time_seconds // 60)
                        seconds = int(time_seconds % 60)
                        return minutes, seconds, time_seconds
                else:
                    logger.warning(
                        "Film %s has no R-Factor data for source %s; falling back to physics model",
                        resolved_film, source
                    )
            else:
                logger.warning(
                    "chart_source=%s not recognized; falling back to physics model",
                    chart_source
                )

        # ── Attenuation coefficient per source (on steel, energy-weighted or kV-dependent)
        if source == "x_ray":
            if kv is None:
                kv = 120.0
            mu = self.get_mu_from_kv(kv, material)
        else:
            MU = {
                "isotope_ir192": 0.035,   # Iridium-192  (0.37 MeV avg)
                "isotope_se75":  0.055,   # Selenium-75  (0.27 MeV avg)
                "isotope_co60":  0.022,   # Cobalt-60    (1.25 MeV avg)
            }
            mu = MU.get(source, 0.035)

        try:
            exponent = min(700.0, mu * w_eff)
            attenuation = math.exp(exponent)
        except OverflowError:
            attenuation = 1e300

        # ── Base exposure time (source + geometry + material only)
        sfd_m = sfd / 1000.0   # mm → m
        t_base = (base_factor * (sfd_m ** 2) * attenuation) / max(0.01, output_val)

        if tech == "analog":
            # ── Film speed: faster film → shorter exposure
            film_speed = self.FILM_SPEED_FACTORS.get(film_class, 2.0)   # default C5
            # ── OD target: Class B requires higher density → more exposure
            od_factor = self.OD_CORRECTION.get(testing_class, 1.0)
            time_minutes = t_base * od_factor / film_speed

        else:  # digital
            # ── Detector DQE: better detector → shorter exposure
            det_factor = self.DETECTOR_TYPE_FACTORS.get(detector_type, 1.0)
            # ── SNR target: Class B requires higher SNR_N → more dose (∝ dose²)
            snr_factor = self.SNR_CORRECTION.get(testing_class, 1.0)
            time_minutes = t_base * snr_factor / det_factor

        # ── kVp⁵ sanity check (X-ray only) ──────────────────────────────────
        if source == "x_ray" and kv is not None and time_minutes > 0:
            self._check_kvp5(kv, time_minutes, material, tech, film_class, testing_class)

        # ── Convert to seconds and cap at 10 days
        time_seconds = min(864000.0, time_minutes * 60.0)

        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        return minutes, seconds, time_seconds

    def _resolve_chart_film(self, chart_source, film_model, film_class):
        if film_model is not None:
            return film_model
        if chart_source in ("AA400", "MX125", "T200", "HS800", "M100"):
            return chart_source
        if ExposureChartDatabase is not None:
            rev_map = {v: k for k, v in ExposureChartDatabase.FILM_TO_CHART_KEY.items()}
            if film_class in rev_map:
                return rev_map[film_class]
        return None

    def _calc_from_rfactor(self, chart_db, film_key, source, sfd, w, activity, density):
        if source not in chart_db.HVL:
            return None
        t_min = chart_db.calculate_exposure_time_rfactor(
            sfd=sfd, w=w, source=source, activity=activity,
            film_key=film_key, density=density
        )
        return t_min

    def _calc_from_type_x(self, chart_db, kv, thickness, ma, sfd):
        kv = kv if kv is not None else 120.0
        kv_int = int(round(kv / 20) * 20)
        exposure_mamin = chart_db.get_type_x_exposure(kv_int, thickness)
        if exposure_mamin is None or exposure_mamin <= 0:
            return None
        sfd_ref = 700.0
        sfd_correction = (sfd / sfd_ref) ** 2
        adjusted_exposure = exposure_mamin * sfd_correction
        t_min = adjusted_exposure / max(0.01, ma)
        if t_min <= 0:
            return None
        return t_min

    def _check_kvp5(self, kv, time_minutes, material, tech, film_class, testing_class):
        kv_ref = 200.0
        if abs(kv - kv_ref) / kv_ref < 0.05:
            return
        mu_ref = self.get_mu_from_kv(kv_ref, material)
        mu_cur = self.get_mu_from_kv(kv, material)
        ratio_simple = (kv_ref / kv) ** 5
        ratio_model = mu_cur / mu_ref if mu_ref > 0 else 1.0
        deviation = abs(ratio_simple - ratio_model) / max(ratio_simple, 1e-10)
        if deviation > 0.30:
            logger.info(
                "kVp⁵ check: kV changed from %.0f to %.0f, "
                "kVp⁵ rule predicts %.2f× time change, "
                "model gives %.2f× attenuation change (deviation %.0f%%)",
                kv_ref, kv, ratio_simple, ratio_model, deviation * 100
            )


    def get_required_film_class(self, w_nom, testing_class, material, source=None):
        """
        Determines the minimum required ISO 11699-1 film system class (Step 7)
        Based on ISO 17636-1 Table 2
        """
        if material in ["steel", "copper_nickel"]:
            if testing_class == "class_a":
                # For Class A steel, minimum is C5 for all thicknesses
                base_film = "C5"
            else: # class_b
                # For Class B steel: C4 for w_nom <= 50mm, C3 for w_nom > 50mm
                if w_nom <= 50.0:
                    base_film = "C4"
                else:
                    base_film = "C3"
            
            # Clause 6.9 exception: Se-75 source with w_nom < 12mm Class B on steel/copper_nickel
            # requires upgrading the film class by one level (e.g. C4 to C3).
            if source == "isotope_se75" and w_nom < 12.0 and testing_class == "class_b":
                upgrade_map = {"C5": "C4", "C4": "C3", "C3": "C2", "C2": "C1", "C1": "C1"}
                return upgrade_map.get(base_film, base_film)
            return base_film
        else:
            # Aluminum, Titanium
            if testing_class == "class_a":
                return "C5"
            else:
                return "C4"

    def get_max_srb(self, w_nom, testing_class, geometry="swsi"):
        """
        Determines the maximum allowed basic spatial resolution (SR_b^max) of the detector in µm (Step 7)
        Based on ISO 17636-2:2022 Tables B.13 (Class A) and B.14 (Class B).
        Per footnote a: For DWSI (double-wall single-image), the nominal thickness t
        shall be used instead of the penetrated thickness w.
        - SWSI: ref = w_nom = t
        - DWSI: ref = w_nom / 2 = t
        - DWDI: ref = w_nom = 2t
        """
        if geometry == "dwsi":
            ref = w_nom / 2.0
        else:
            ref = w_nom

        if testing_class == "class_a":
            # Table B.13 — Class A SRb_detector column
            if ref <= 1.0:
                return 50
            elif ref <= 1.5:
                return 63
            elif ref <= 2.0:
                return 80
            elif ref <= 5.0:
                return 100
            elif ref <= 10.0:
                return 130
            elif ref <= 25.0:
                return 160
            elif ref <= 55.0:
                return 200
            elif ref <= 150.0:
                return 250
            elif ref <= 250.0:
                return 320
            else:
                return 400
        else:  # class_b
            # Table B.14 — Class B SRb_detector column
            if ref <= 1.5:
                return 40
            elif ref <= 4.0:
                return 50
            elif ref <= 8.0:
                return 63
            elif ref <= 12.0:
                return 80
            elif ref <= 40.0:
                return 100
            elif ref <= 120.0:
                return 130
            elif ref <= 200.0:
                return 160
            else:
                return 200

    def get_mu_from_kv(self, kv, material):
        """
        Determines linear attenuation coefficient (mu) using log-log interpolation based on
        kV and material type (Steel, Aluminum, Titanium, Copper/Nickel).
        Clamps values outside the range of [80, 400] kV.
        """
        data = {
            "steel": [
                (80, 0.090), (100, 0.072), (120, 0.058), (150, 0.045),
                (200, 0.032), (250, 0.026), (300, 0.022), (400, 0.016)
            ],
            "aluminum": [
                (80, 0.028), (100, 0.022), (120, 0.018), (150, 0.014),
                (200, 0.010), (250, 0.008), (300, 0.007), (400, 0.005)
            ],
            "titanium": [
                (80, 0.055), (100, 0.044), (120, 0.036), (150, 0.028),
                (200, 0.020), (250, 0.016), (300, 0.014), (400, 0.011)
            ],
            "copper_nickel": [
                (80, 0.110), (100, 0.090), (120, 0.073), (150, 0.058),
                (200, 0.042), (250, 0.034), (300, 0.028), (400, 0.021)
            ]
        }
        pts = data.get(material, data["steel"])
        
        # Clamp kv
        if kv <= pts[0][0]:
            return pts[0][1]
        if kv >= pts[-1][0]:
            return pts[-1][1]
            
        # Log-log interpolation
        for i in range(len(pts) - 1):
            kv1, mu1 = pts[i]
            kv2, mu2 = pts[i+1]
            if kv1 <= kv <= kv2:
                ln_kv = math.log(kv)
                ln_kv1 = math.log(kv1)
                ln_kv2 = math.log(kv2)
                ln_mu1 = math.log(mu1)
                ln_mu2 = math.log(mu2)
                
                ln_mu = ln_mu1 + (ln_kv - ln_kv1) * (ln_mu2 - ln_mu1) / (ln_kv2 - ln_kv1)
                return math.exp(ln_mu)
        return pts[0][1]

    def check_film_class_compliance(self, film_class_used, testing_class, w_nom, material, source=None):
        """
        Verifies if the film class meets the minimum requirements of ISO 17636-1 Table 2.
        Returns (is_compliant, message)
        """
        req_film = self.get_required_film_class(w_nom, testing_class, material, source)
        ranks = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5, "C6": 6}
        app_rank = ranks.get(film_class_used, 5)
        req_rank = ranks.get(req_film, 5)
        if app_rank <= req_rank:
            return True, f"Film class {film_class_used} is compliant (Required minimum: {req_film})"
        else:
            return False, f"Film class {film_class_used} is insufficient! Required minimum is {req_film}"

    def get_filter_recommendations(self, source, material, kv, testing_class):
        """
        Determines recommended lead screen thickness and metal filter based on ISO 17636-1 rules.
        """
        pb_screen = ""
        metal_filter = ""
        
        if source == "x_ray":
            if kv is None:
                kv = 120.0
            
            # Pb Screen
            if kv <= 150.0:
                pb_screen = "0.02-0.10 mm Pb (Front) / None (Back)"
            elif kv <= 250.0:
                pb_screen = "0.02-0.10 mm Pb (Front) / 0.02-0.10 mm Pb (Back)"
            else:
                pb_screen = "0.02-0.10 mm Pb (Front) / 0.02-0.10 mm Pb (Back)"
                
            # Metal Filter
            if kv < 120.0:
                metal_filter = "None or 0.1 mm Al"
            elif kv <= 150.0:
                metal_filter = "0.5 mm Cu or 1.0 mm Al"
            elif kv <= 250.0:
                metal_filter = "1.0 mm Cu"
            else:
                metal_filter = "1.0-2.0 mm Cu"
        else:
            # Isotopes
            if source == "isotope_se75":
                pb_screen = "0.02-0.10 mm Pb (Front & Back)"
                metal_filter = "0.5 mm Cu"
            elif source == "isotope_ir192":
                pb_screen = "0.02-0.10 mm Pb (Front & Back)"
                metal_filter = "1.0 mm Cu or 1.0 mm Pb"
            elif source == "isotope_co60":
                pb_screen = "0.05-0.15 mm Pb (Front & Back)"
                metal_filter = "1.0-2.0 mm Pb"
            else:
                pb_screen = "None"
                metal_filter = "None"
                
        return {
            "pb_screen": pb_screen,
            "metal_filter": metal_filter
        }

    def get_source_thickness_limits(self, source, material):
        """
        Returns (min_w, max_w) for Class A and Class B per ISO 17636-2:2022 Table 2.
        Returns: dict with keys "class_a" and "class_b", each value is (min, max) or None.
        """
        source_limits = self.TABLE_2_LIMITS.get(source, None)
        if source_limits is None:
            return {"class_a": None, "class_b": None}
        return source_limits.get(material, None)

    def validate_source_thickness(self, source, w_nom, testing_class, material, kv=None):
        """
        Validates source vs penetrated thickness per ISO 17636-2:2022 Table 2.
        Returns: (is_valid, min_limit, max_limit, message)
        - is_valid: True if within limits
        - min_limit / max_limit: bounding values (None if no bound)
        - message: warning/info string (empty string if valid with no notes)
        """
        msg = ""

        if source == "x_ray":
            # X-ray > 1 MV has Table 2 bands; below 1 MV no Table 2 limit
            if kv is not None and kv > 1000:
                bands = self.XRAY_TABLE2_BANDS.get(testing_class, [])
                for min_w, max_w, kv_min, kv_max in bands:
                    if (kv_min is None or kv > kv_min) and (kv_max is None or kv <= kv_max):
                        if (min_w is None or w_nom >= min_w) and (max_w is None or w_nom <= max_w):
                            return True, min_w, max_w, ""
                        else:
                            limit_str = f"w ≥ {min_w}" if max_w is None else \
                                        f"w ≤ {max_w}" if min_w is None else \
                                        f"{min_w} ≤ w ≤ {max_w}"
                            msg = f"X-ray ({kv} kV) requires {limit_str} for {testing_class.replace('_', ' ').title()}"
                            return False, min_w, max_w, msg
                return True, None, None, ""
            return True, None, None, ""

        # Isotope check
        material_limits = self.get_source_thickness_limits(source, material)
        if material_limits is None:
            return True, None, None, ""

        class_limits = material_limits.get(testing_class, None)
        if class_limits is None:
            # Source+material+class combination not defined in Table 2
            return True, None, None, ""

        min_w, max_w = class_limits
        is_valid = True
        if min_w is not None and w_nom < min_w:
            is_valid = False
        if max_w is not None and w_nom > max_w:
            is_valid = False

        if not is_valid:
            if min_w is not None and max_w is not None:
                limit_str = f"{min_w} ≤ w ≤ {max_w}"
            elif min_w is not None:
                limit_str = f"w ≥ {min_w}"
            else:
                limit_str = f"w ≤ {max_w}"
            source_name = source.replace("isotope_", "").upper()
            msg = f"{source_name} requires {limit_str} mm for {testing_class.replace('_', ' ').title()}"
        else:
            # Append info notes for contractual flexibilities
            notes = []
            if source == "isotope_ir192" and w_nom < 20.0:
                notes.append("Ir-192 may be reduced to w ≥ 10 mm per contracting party agreement")
            if source == "isotope_se75" and w_nom < 10.0:
                notes.append("Se-75 with w < 10 mm: higher SNR_N than Table 3/4 values is recommended")
            if source == "isotope_se75" and w_nom <= 14.0 and testing_class == "class_b":
                notes.append("Se-75 limits may be relaxed per contracting party agreement")
            if notes:
                msg = "; ".join(notes)

        return is_valid, min_w, max_w, msg
