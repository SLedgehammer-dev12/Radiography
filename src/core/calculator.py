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
    # Film gradient G̅ per ISO 11699-1 film class (average gradient over OD 1.5–3.5)
    # Slower films (C1) have higher contrast → steeper gradient → less extra
    # exposure needed for a given density increase.
    # Source: ISO 17636-1:2022 Clause 7.3, ISO 11699-1:2008 Annex A.
    # -----------------------------------------------------------------------
    FILM_GRADIENT = {
        "C1": 4.0,   # slowest, finest grain — highest contrast (e.g. DR50)
        "C2": 3.5,   # (e.g. M100)
        "C3": 3.2,   # (e.g. MX125)
        "C4": 3.0,   # (e.g. T200)
        "C5": 2.8,   # (e.g. AA400)
        "C6": 2.5,   # fastest, coarsest grain — lowest contrast (e.g. HS800)
    }

    # -----------------------------------------------------------------------
    # Optical Density (OD) Target Correction (analog film)
    # The OD-based exposure correction is computed in `_density_correction_factor`
    # using the film-class-aware gradient (see FILM_GRADIENT) rather than a
    # fixed OD_CORRECTION table. A static dict is intentionally NOT kept here
    # to avoid a second, divergent source of truth.
    # -----------------------------------------------------------------------

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
    # Class A: reference target 70        → factor 1.0
    # Class B: legacy 2013 target 130     → factor (130/70)² ≈ 3.45
    # NOTE: ISO 17636-2:2022 Tables 3/4 use dynamic Class B targets
    # (100/120/150 depending on source and kV, 70 for thick sections).
    # Source: ISO 17636-2:2022 Clause 7.3.1 (SNR_N) / Tables 3-4.
    # -----------------------------------------------------------------------
    SNR_CORRECTION = {
        "class_a": 1.00,   # reference target
        "class_b": 3.45,   # ~3.45× more dose (legacy 130 target)
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
        Formula: Ug = d * b / f where f is the SOURCE-TO-OBJECT distance.
        ISO 17636-2:2022 Clause 3.22 / ASME Sec V Art 2 T-274.2.
        Callers that only know SDD must pass f = SDD - b, or use
        calculate_geometric_unsharpness_from_sfd().
        """
        if f <= 0:
            return 0.0
        return d * b / f

    def calculate_geometric_unsharpness_from_sfd(self, d, b, sfd):
        """
        Geometric unsharpness from the source-to-detector distance (SDD/SFD).

        Ug = d * b / f with f = SDD - b (source-to-object distance), per
        ASME Sec V Art 2 T-274.2 and ISO 17636-2:2022 Clause 3.21/3.22
        (SDD = f + b). Using SDD directly in place of f understates Ug.

        Returns inf when the geometry is invalid (detector at/beyond source).
        """
        if b <= 0.0 or d <= 0.0:
            return 0.0
        f = sfd - b
        if f <= 0.0:
            return float("inf")
        return d * b / f

    def calculate_f_min_star(self, d, b, t, testing_class):
        """
        Calculates f_min* for PLANAR (rigid) detectors on curved objects per
        ISO 17636-2:2022 Clause 7.6, Formula (13):
            f_min* = f_min(b=t) × Ci,  Ci = (b/t)^(1/3)   for b/t > 1.2
        This value GOVERNS for the planar-detector geometries of Figures
        2 b), 5 b), 8 b), 13 b) and 14 b); it must not be max()-ed against
        the plain Formula (2)/(3) value f_min(b) (which is always larger).
        If b/t <= 1.2 the plain f_min(b=t) applies and (None, None) is returned.
        """
        if t is None or t <= 0.0 or b is None or b <= 0.0 or b <= 1.2 * t:
            return None, None

        # f_min computed with b = t (per Clause 7.6 b<1.2t rule)
        ci = (b / t) ** (1.0 / 3.0)
        f_min_at_t = self.calculate_f_min(d, t, testing_class, t)  # t ensures b_eff = t
        f_min_star = f_min_at_t * ci
        return f_min_star, ci

    def calculate_asme_f_min(self, d, b, t):
        """
        Minimum source-to-object distance per ASME Sec V Art 2 T-274.2.
        ASME limits the geometric unsharpness (Ug = d·b/f <= Ug_limit), so:
            f_min,ASME = d · b / Ug_limit(t)
        """
        limit = self.get_asme_ug_limit(t)
        if limit <= 0.0 or d <= 0.0 or b <= 0.0:
            return 0.0
        return d * b / limit

    def calculate_b_ed(self, re, n_exposures):
        """
        Distance from the object surface to the edge of a PLANAR detector
        (sagitta), ISO 17636-2:2022 Clause 7.6 Formula (10):
            b_ed = (1 - cos α) · r_e,   α = π / N
        Used for Figures 2 b), 8 b), 13 b), 14 b) and 22.
        Returns 0.0 for invalid input.
        """
        try:
            re = float(re)
            n = max(1, int(n_exposures))
        except (TypeError, ValueError):
            return 0.0
        if re <= 0.0:
            return 0.0
        alpha = math.pi / n
        return (1.0 - math.cos(alpha)) * re

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
        Object-to-detector distance b for PLANAR (rigid) detectors on curved
        objects (Figures 2 b), 8 b), 13 b), 14 b)).
        Formula (8) Class A: b = bed + bgap + 1.2 * t
        Formula (9) Class B: b = bed + bgap + 1.1 * t
        ISO 17636-2:2022 Clause 7.6. For flexible/wrapped detectors b = t.
        """
        k = 1.2 if testing_class == "class_a" else 1.1
        return bed + bgap + k * t

    def calculate_b_panoramic(self, bed, bgap, t):
        """
        Object-to-detector distance b for panoramic central projection with a
        PLANAR detector (Figure 5 b)).
        Formula (11): b = bed + bgap + t
        ISO 17636-2:2022 Clause 7.6.
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

    def _density_correction_factor(self, testing_class, film_class=None, ref_density=2.0):
        target_density = 2.3 if testing_class == "class_b" else 2.0
        if target_density == ref_density:
            return 1.0
        gradient = self.FILM_GRADIENT.get(film_class, 3.0)
        return 10.0 ** ((target_density - ref_density) / gradient)

    # -----------------------------------------------------------------------
    # Beam-hardening correction (X-ray only)
    # As penetrated thickness increases the effective spectrum hardens, so the
    # effective linear attenuation coefficient decreases. This is a simplified
    # engineering model: the reduction ramps in from 10 mm and is capped at
    # BEAM_HARDENING_MAX_REDUCTION (15 %). Values are empirical.
    # -----------------------------------------------------------------------
    BEAM_HARDENING_MAX_REDUCTION = 0.15   # 15% relative reduction (empirical)
    BEAM_HARDENING_RAMP_THICKNESS = 30.0  # mm over which reduction ramps in

    def _apply_beam_hardening(self, mu, w, source, kv=None, material="steel"):
        if source != "x_ray":
            return mu
        if w <= 10.0:
            return mu
        reduction = self.BEAM_HARDENING_MAX_REDUCTION * min(
            1.0, (w - 10.0) / self.BEAM_HARDENING_RAMP_THICKNESS
        )
        return mu * (1.0 - reduction)

    def _lookup_dwsi_exposures(self, OD, t, testing_class):
        dt_ratio = OD / t if t > 0 else 999.0
        # Simplified D/t lookup mirroring the spirit of ISO 17636-1:2022
        # Annex A (minimum exposures for circumferential coverage). The exact
        # thresholds here are engineering approximations of the Annex A charts,
        # not a verbatim reproduction of a specific table row; the geometric
        # solver in calculate_dwsi_exposures() provides the governing value and
        # the stricter of the two is returned.
        table = {
            "class_a": [
                (20.0, 3), (15.0, 3), (10.0, 4), (7.0, 5), (5.0, 6), (0.0, 8),
            ],
            "class_b": [
                (20.0, 3), (15.0, 4), (10.0, 5), (7.0, 6), (5.0, 7), (0.0, 8),
            ],
        }
        rows = table.get(testing_class, table["class_a"])
        for threshold, n in rows:
            if dt_ratio >= threshold:
                return n
        return 8

    def calculate_dwsi_exposures(self, OD, t, sfd, testing_class):
        """
        Calculates the required minimum number of exposures for DWSI geometry.

        Uses ISO 17636-1:2022 Annex C Table C.1 as primary lookup (based on D/t ratio),
        backed by geometric binary search for edge cases.

        - Class A: +20% thickness tolerance
        - Class B: +10% thickness tolerance

        Physical guard: for DWSI the source is outside the pipe and the detector
        on the opposite side, so the source-to-detector distance can never be
        smaller than the outside diameter (De). Applied SFD values below De are
        clamped to De before solving the geometry (otherwise y_s = sfd - R <= 0
        puts the source inside the pipe and the angle search degenerates).
        """
        try:
            OD = float(OD)
            t = float(t)
            sfd = float(sfd)
        except (TypeError, ValueError):
            return max(3, self._lookup_dwsi_exposures(114.3, 8.56, testing_class))

        # ISO table minimum
        iso_min = self._lookup_dwsi_exposures(OD, t, testing_class)

        R = OD / 2.0
        Ri = R - t
        if R <= 0.0 or Ri <= 0.0 or t <= 0.0:
            # Degenerate "pipe" (no inner cavity); no geometric DWSI coverage model.
            return max(3, iso_min)

        # Physical floor: source outside the pipe (Figure 14 - source on surface)
        sfd_eff = max(sfd, OD)
        y_s = sfd_eff - R

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
        geo_n = max(3, int(math.ceil(N)))

        # Return the stricter of geometric calculation vs ISO table
        return max(geo_n, iso_min)

    def get_dwdi_elliptical_exposures(self, od, t):
        """
        Minimum number of images for the DWDI elliptical technique.

        ISO 17636-1:2022 Clause 7.1.6 (Figure 11): two 90° displaced images are
        sufficient if t/De < 0.12; otherwise three elliptical images are needed.
        The same technique is referenced by ISO 17636-2:2022 Clause 7.1.6.
        """
        try:
            if od <= 0.0 or t <= 0.0:
                return 2
            return 3 if (t / od) >= 0.12 else 2
        except (TypeError, ZeroDivisionError):
            return 2

    def validate_dwdi(self, geometry, od, t, weld_width=None):
        """
        Validates DWDI geometry limits per ISO 17636-1:2022 Clauses 7.1.6/7.1.7
        (and the equivalent digital clauses in ISO 17636-2:2022).

        Elliptical (Figure 11): De <= 100 mm, t <= 8 mm, weld width <= De/4.
        Perpendicular/superimposed (Figure 12): De <= 100 mm, 3 exposures.

        Returns a structured dict (booleans + exposures) so the caller can build
        localized warning messages.
        """
        od_ok = od is not None and 0.0 < od <= 100.0
        exposures = 3 if geometry == "dwdi_super" else self.get_dwdi_elliptical_exposures(od, t)
        needs_three = False
        t_ok = True
        weld_width_ok = True
        if geometry == "dwdi_elliptic":
            t_ok = t is not None and t <= 8.0
            if weld_width is not None:
                weld_width_ok = weld_width <= (od / 4.0)
            if od is not None and od > 0.0 and t is not None and t > 0.0:
                needs_three = (t / od) >= 0.12
        return {
            "valid": od_ok and t_ok and weld_width_ok,
            "od_ok": od_ok,
            "t_ok": t_ok,
            "weld_width_ok": weld_width_ok,
            "exposures": exposures,
            "needs_three": needs_three,
        }

    # -----------------------------------------------------------------------
    # Flat-panel (DDA) coverage-based minimum exposures (ISO 17636-2 Annex A)
    # -----------------------------------------------------------------------
    THICKNESS_TOLERANCE = {
        "class_a": 0.20,
        "class_b": 0.10,
    }

    def _penetrated_path_length(self, theta, re, ri, f):
        """
        Returns the penetrated path length (mm) through the far wall for a ray
        from source S(0, -(re+f)) to point P on the far outer wall at half-angle
        theta. Used for the Δt/t thickness-variation limit (Clause 7.8 / Annex A).
        At theta = 0 the path length equals the wall thickness t = re - ri.
        Returns None if the ray misses the inner wall.
        """
        a = re * math.sin(theta)
        c = re * (1.0 + math.cos(theta)) + f
        A = a * a + c * c
        if A <= 0:
            return None
        B = -2.0 * c * (re + f)
        C = (re + f) ** 2 - ri * ri
        disc = B * B - 4.0 * A * C
        if disc < 0:
            return None
        u_far = (-B + math.sqrt(disc)) / (2.0 * A)
        return (1.0 - u_far) * math.sqrt(A)

    def _ray_panel_offset(self, theta, re, f, sdd):
        """
        Lateral offset (mm) of the ray to the far-wall point P(theta) measured at
        the detector plane located at distance SDD from the source.
        """
        denom = re * (1.0 + math.cos(theta)) + f
        if denom <= 0:
            return float("inf")
        tan_delta = re * math.sin(theta) / denom
        return sdd * tan_delta

    def _thickness_half_angle(self, re, t, f, k_tol, max_iter=50):
        """
        Binary search for the maximum half-angle (rad) at which the penetrated
        far-wall path length equals k_tol * t (the Δt/t limit). If even the
        tangent ray does not reach the limit, returns pi/2 (not thickness limited).
        """
        if re <= 0 or t <= 0 or f <= 0 or k_tol <= 1.0:
            return 0.0
        ri = re - t
        if ri <= 0:
            return 0.0
        target = k_tol * t
        path_hi = self._penetrated_path_length(math.pi / 2.0, re, ri, f)
        if path_hi is not None and path_hi < target:
            return math.pi / 2.0
        low, high = 0.0, math.pi / 2.0
        best = 0.0
        for _ in range(max_iter):
            mid = (low + high) / 2.0
            path = self._penetrated_path_length(mid, re, ri, f)
            if path is None:
                high = mid
                continue
            if path <= target:
                best = mid
                low = mid
            else:
                high = mid
        return best

    def _panel_half_angle(self, re, f, sdd, panel_half_width, max_iter=50):
        """
        Binary search for the maximum half-angle (rad) at which the ray to the
        far-wall point P(theta) hits the detector plane within panel_half_width
        of the central ray.
        """
        if re <= 0 or sdd <= 0 or panel_half_width <= 0:
            return 0.0
        low, high = 0.0, math.pi / 2.0
        best = 0.0
        for _ in range(max_iter):
            mid = (low + high) / 2.0
            offset = self._ray_panel_offset(mid, re, f, sdd)
            if offset <= panel_half_width:
                best = mid
                low = mid
            else:
                high = mid
        return best

    def estimate_wae_width(self, cap, t):
        """
        Heuristic estimate of the weld area to evaluate (WAE) width along the pipe
        axis: weld bead plus heat-affected zones on both sides.
        weld_width ~ max(t, 2*cap); HAZ ~ 10 mm each side.
        Used only for the informational panel-height check.
        """
        weld_width = max(float(t), 2.0 * float(cap))
        return weld_width + 2.0 * 10.0

    def _panel_result_fixed(self, n, od, t, cap, reason, panel_height=None):
        wae_width = self.estimate_wae_width(cap, t)
        panel_height_ok = True if panel_height is None else (panel_height >= wae_width - 1e-9)
        return {
            "n_panel": int(n),
            "theta_deg": 0.0,
            "theta_dt_deg": 0.0,
            "theta_panel_deg": 0.0,
            "bed": 0.0,
            "b": 0.0,
            "f": 0.0,
            "sdd": 0.0,
            "arc_mm": 0.0,
            "limiting_factor": reason,
            "iterations": 0,
            "panel_height_ok": panel_height_ok,
            "wae_width_mm": wae_width,
            "f_min_applied": 0.0,
        }

    def calculate_panel_exposures(self, od, t, geometry, testing_class, panel_width,
                                  panel_height=None, cap=0.0, sfd=600.0, bgap=5.0,
                                  overlap_percent=10.0, focal_size=2.0,
                                  std_figure=None, max_iterations=6,
                                  b_object=None, f_source=None):
        """
        Calculates the minimum number of exposures required so that a flat-panel
        DDA covers the whole circumference within the evaluable area limits
        (ISO 17636-2:2022 Clauses 7.6, 7.8 and Annex A).

        Fixed-geometry cases:
          - Panoramic central projection (Fig 5): N = 1
          - DWDI elliptic: N = 2, DWDI superimposed: N = 3

        For SWSI (source outside) and DWSI the geometric coverage model applies:
          - θ = min(θ_Δt, θ_panel) is the maximum half-angle per exposure
            (θ_Δt  -> penetrated thickness increase limited to Δt/t;
             θ_panel -> flat-panel active width coverage at the detector plane)
          - N = ceil(π / (θ · (1 - overlap_percent/100))), min N = 3 for DWSI
          - b = bed + bgap + k·t with bed = (1 - cos α)·re, α = π/N (iterated
            until N converges, max max_iterations passes)

        User-provided geometry overrides the derived values:
          - b_object: measured material-to-detector distance (mm). When given,
            b is fixed (no bed iteration).
          - f_source: measured source-to-material distance (mm). When given,
            it is used directly; otherwise f = max(sfd - b, 1.0).
        The resulting source-to-object distance is never allowed to fall below
        the ISO 17636-2 Clause 7.6 geometric limit f_min (focal-size based).

        Returns a dict with n_panel and the intermediate geometry values.
        """
        # Fixed-geometry cases
        if self.is_central_projection(geometry, std_figure):
            return self._panel_result_fixed(1, od, t, cap, "panoramic", panel_height)
        if geometry == "dwdi_elliptic":
            return self._panel_result_fixed(
                self.get_dwdi_elliptical_exposures(od, t), od, t, cap,
                "dwdi_elliptic", panel_height
            )
        if geometry == "dwdi_super":
            return self._panel_result_fixed(3, od, t, cap, "dwdi_super", panel_height)

        re = od / 2.0
        t_wall = max(float(t), 0.1)
        ri = re - t_wall
        if re <= 0 or ri <= 0:
            return self._panel_result_fixed(3, od, t, cap, "invalid_geometry", panel_height)

        dt_t = self.THICKNESS_TOLERANCE.get(testing_class, 0.10)
        k_tol = 1.0 + dt_t
        k = 1.2 if testing_class == "class_a" else 1.1
        overlap = max(0.0, min(float(overlap_percent), 90.0)) / 100.0
        min_n = 3 if geometry == "dwsi" else 1

        # User-provided geometry overrides derived values when valid
        b_user = b_object if (b_object is not None and b_object > 0.0) else None
        f_user = f_source if (f_source is not None and f_source > 0.0) else None

        def _geometry(alpha_guess):
            """Returns (bed, b_dist, f_dist, sdd) for the current angular guess."""
            if b_user is not None:
                beds = 0.0
                bd = b_user
            else:
                beds = (1.0 - math.cos(alpha_guess)) * re
                bd = beds + bgap + k * t_wall
            if f_user is not None:
                fd = f_user
            else:
                fd = max(sfd - bd, 1.0)
            fd = max(fd, self.calculate_f_min(focal_size, bd, testing_class, t_wall))
            return beds, bd, fd, fd + bd

        # Initial guess from the standard/graph minimum
        try:
            n_init = max(min_n, self.calculate_dwsi_exposures(od, t_wall, sfd, testing_class))
        except Exception:
            n_init = max(min_n, 3)
        n_prev = n_init
        theta_guess = math.pi / float(max(1, n_prev))

        iterations = 0
        for iterations in range(1, max_iterations + 1):
            alpha = theta_guess
            bed, b_dist, f_dist, sdd = _geometry(alpha)
            theta_dt = self._thickness_half_angle(re, t_wall, f_dist, k_tol)
            theta_panel = self._panel_half_angle(re, f_dist, sdd, panel_width / 2.0)
            theta = max(min(theta_dt, theta_panel), 1e-6)
            n_new = max(min_n, int(math.ceil(math.pi / (theta * (1.0 - overlap)))))
            if n_new == n_prev:
                break
            n_prev = n_new
            theta_guess = math.pi / float(n_new)

        # Final pass with the converged angle
        alpha = theta_guess
        bed, b_dist, f_dist, sdd = _geometry(alpha)
        theta_dt = self._thickness_half_angle(re, t_wall, f_dist, k_tol)
        theta_panel = self._panel_half_angle(re, f_dist, sdd, panel_width / 2.0)
        theta = max(min(theta_dt, theta_panel), 1e-6)
        n_final = max(min_n, int(math.ceil(math.pi / (theta * (1.0 - overlap)))))

        limiting = "thickness" if theta_dt <= theta_panel else "panel"

        wae_width = self.estimate_wae_width(cap, t_wall)
        panel_height_ok = True if panel_height is None else (panel_height >= wae_width - 1e-9)
        f_min_applied = self.calculate_f_min(focal_size, b_dist, testing_class, t_wall)

        return {
            "n_panel": n_final,
            "theta_deg": math.degrees(theta),
            "theta_dt_deg": math.degrees(theta_dt),
            "theta_panel_deg": math.degrees(theta_panel),
            "bed": bed,
            "b": b_dist,
            "f": f_dist,
            "sdd": sdd,
            "arc_mm": od * theta,
            "limiting_factor": limiting,
            "iterations": iterations,
            "panel_height_ok": panel_height_ok,
            "wae_width_mm": wae_width,
            "f_min_applied": f_min_applied,
        }

    def evaluate_exposure_comparison(self, n_graph, n_panel, n_applied):
        """
        Compares the standard/graph-based minimum exposures (n_graph), the
        panel-coverage minimum exposures (n_panel) and the user's applied
        exposures (n_applied). The governing required value is max(n_graph,
        n_panel); the applied value is sufficient when it is >= that.
        """
        n_graph_i = max(1, int(n_graph))
        n_panel_i = max(1, int(n_panel))
        n_applied_i = max(0, int(n_applied))
        n_required = max(n_graph_i, n_panel_i)
        return {
            "n_graph": n_graph_i,
            "n_panel": n_panel_i,
            "n_applied": n_applied_i,
            "n_required": n_required,
            "is_sufficient": n_applied_i >= n_required,
        }

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
          OD_correction      — from _density_correction_factor(testing_class, film_class)
                               (film-class-aware gradient; see FILM_GRADIENT)
                               Class A (OD ≥ 2.0) = 1.00
                               Class B (OD ≥ 2.3) = 10^((2.3-2.0)/G̅)

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
          ISO 17636-1:2022 Clause 7    (Recommended techniques — analog film)
          ISO 17636-2:2022 Clause 7    (Recommended techniques — digital)
          ISO 11699-1:2008             (Film classification & speed)
          ISO 17636-2:2022 Clause 7.3  (Detector systems / DQE literature)
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

        # ── Attenuation coefficient per source, with beam hardening correction
        if source == "x_ray":
            if kv is None:
                kv = 120.0
            mu = self.get_mu_from_kv(kv, material)
            mu = self._apply_beam_hardening(mu, w_eff, source, kv, material)
        else:
            MU = {
                "isotope_ir192": 0.035,   # Iridium-192  (0.37 MeV avg)
                "isotope_se75":  0.055,   # Selenium-75  (0.27 MeV avg)
                "isotope_co60":  0.022,   # Cobalt-60    (1.25 MeV avg)
                # Low-energy isotopes (approximate broad-beam effective values):
                "isotope_yb169": 0.115,   # Ytterbium-169 (0.13 MeV avg)
                "isotope_tm170": 0.30,    # Thulium-170   (0.084 MeV avg)
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
            film_speed = self.FILM_SPEED_FACTORS.get(film_class, 16.0)   # default C5
            # ── OD target: film-class-aware gradient density correction
            od_factor = self._density_correction_factor(testing_class, film_class)
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

        Reference data: mass/narrow-beam attenuation coefficients from NIST
        XCOM / NISTIR 5632 and ICRU Report 44 (compiled into the tables below).
        Values are engineering approximations for a typical broad-beam NDT setup
        and are intended for exposure-time estimation, not metrology.
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
        Determines recommended lead screen thickness and metal filter based on
        ISO 17636-1:2022 Clause 7.3 (lead screens) and metal filters.

        Returns LANGUAGE-NEUTRAL structural data only (no formatted strings):
            {
              "screen_table": {
                  "front_mm": str,          # lead range, e.g. "0.02-0.15", "<=0.15"
                  "back_mm": str,
                  "front_optional": bool,   # front lead screen may be omitted
                  "back_optional": bool,    # back lead screen may be omitted
                  "back_absent": bool,      # back lead screen may be absent entirely
                  "front_is_filter": bool,  # front is a metal filter, not Pb (high kV)
              },
              "metal_filter": {
                  "options": [              # ordered alternatives; material None => no filter
                      {"material": "cu"|"pb"|"al"|None, "thickness": str|None},
                      ...
                  ],
              },
            }
        Localization/formatting is the responsibility of the UI/i18n layer
        (see src/core/translation.py::format_filter_recommendation).
        """
        front = ""
        back = ""
        front_optional = False
        back_optional = False
        back_absent = False
        front_is_filter = False
        options = [{"material": None, "thickness": None}]

        if source == "x_ray":
            if kv is None:
                kv = 120.0
            # ISO 17636-1:2022 Clause 7.3.2 — lead screen thickness (mm)
            if kv <= 120.0:
                front = "<=0.15"
                back = "<=0.15"
                front_optional = True
                back_optional = True
                back_absent = True
                if kv < 120.0:
                    options = [
                        {"material": None, "thickness": None},
                        {"material": "al", "thickness": "0.1"},
                    ]
                else:
                    options = [
                        {"material": "cu", "thickness": "0.5"},
                        {"material": "al", "thickness": "1.0"},
                    ]
            elif kv <= 250.0:
                front = "0.02-0.15"
                back = "0.02-0.15"
                options = [
                    {"material": "cu", "thickness": "0.5"},
                    {"material": "al", "thickness": "1.0"},
                ]
            elif kv <= 450.0:
                front = "0.05-0.15"
                back = "0.05-0.15"
                options = [{"material": "cu", "thickness": "1.0"}]
            elif kv <= 1000.0:
                front = "0.10-0.30"
                back = "0.10-0.30"
                options = [{"material": "cu", "thickness": "1.0-2.0"}]
            else:
                front = "1-2"
                front_is_filter = True   # front screen is copper, not lead
                back = "0.10-0.30"
                options = [{"material": "cu", "thickness": "1.0-2.0"}]
        else:
            # Isotopes
            if source == "isotope_se75":
                front, back = "0.02-0.20", "0.02-0.20"
                options = [{"material": "cu", "thickness": "0.5"}]
            elif source == "isotope_ir192":
                front, back = "0.05-0.20", "0.05-0.20"
                options = [
                    {"material": "cu", "thickness": "1.0"},
                    {"material": "pb", "thickness": "1.0"},
                ]
            elif source == "isotope_co60":
                front, back = "0.10-0.30", "0.10-0.30"
                options = [{"material": "pb", "thickness": "1.0-2.0"}]
            elif source in ("isotope_yb169", "isotope_tm170"):
                front, back = "0.02-0.20", "0.02-0.20"
                options = [{"material": "cu", "thickness": "0.5"}]
            else:
                front, back = "0.02-0.15", "0.02-0.15"
                options = [{"material": None, "thickness": None}]

        return {
            "screen_table": {
                "front_mm": front,
                "back_mm": back,
                "front_optional": front_optional,
                "back_optional": back_optional,
                "back_absent": back_absent,
                "front_is_filter": front_is_filter,
            },
            "metal_filter": {
                "options": options,
            },
        }

    # -----------------------------------------------------------------------
    # ASME Section V Article 2 / ASTM — geometric unsharpness (Ug) limits
    # ASME V Art.2, Table T-274 (max Ug vs material thickness):
    #   t < 50 mm        -> Ug <= 0.51 mm
    #   50 <= t <= 75 mm -> Ug <= 0.76 mm
    #   75 < t <= 100 mm -> Ug <= 1.02 mm
    #   t > 100 mm       -> Ug <= 1.78 mm
    # -----------------------------------------------------------------------
    def get_asme_ug_limit(self, t):
        """Returns the maximum allowed geometric unsharpness (mm) for a material
        thickness t (mm) per ASME Section V Article 2, T-274.2 (inch-based):
        t <= 2 in (50.8 mm) -> 0.51 mm; <= 3 in (76.2 mm) -> 0.76 mm;
        <= 4 in (101.6 mm) -> 1.02 mm; > 4 in -> 1.78 mm."""
        if t is None or t <= 0.0:
            return 0.51
        if t <= 50.8:
            return 0.51
        if t <= 76.2:
            return 0.76
        if t <= 101.6:
            return 1.02
        return 1.78

    def check_ug_compliance(self, ug, t, standard="iso"):
        """
        Checks geometric unsharpness against the active standard.
        - ISO (default): simplified 0.5 mm threshold (existing behaviour).
        - ASME Sec V Art 2: thickness-based Ug limits.
        Returns (is_ok, max_ug_mm).
        """
        if standard == "asme":
            limit = self.get_asme_ug_limit(t)
        else:
            limit = 0.5
        return (ug <= limit), limit

    # -----------------------------------------------------------------------
    # Radiographic Equivalence Factors (REF) relative to steel
    # ISO 17636-1 Annex E / ASTM E94. Equivalent steel thickness:
    #   t_steel_equiv = t_material * REF
    # The program's physics model uses material-specific attenuation (mu),
    # so REF here is informational / for reporting & cross-referencing.
    # -----------------------------------------------------------------------
    REF_FACTORS = {
        "steel": 1.0,
        "copper_nickel": 1.4,   # copper / copper-nickel
        "titanium": 0.54,
        "aluminum": 0.18,
    }

    def get_ref_factor(self, material):
        return self.REF_FACTORS.get(material, 1.0)

    def equivalent_steel_thickness(self, t, material):
        """Returns the steel-equivalent penetrated thickness t*REF (mm)."""
        return float(t) * self.get_ref_factor(material)

    # -----------------------------------------------------------------------
    # ASTM IQI determination (ASME Sec V Art 2 / ASTM E1025, E747)
    # Approximations: 2-2T hole-type sensitivity and 2 % wire sensitivity,
    # used when the ASME standard is selected.
    # -----------------------------------------------------------------------
    def get_astm_iqi_hole(self, t, sensitivity="2-2T"):
        """
        ASTM E1025 hole-type IQI requirement with selectable sensitivity
        (ASME Sec V Art. 2, Table T-276):
          - 2-2T : IQI thickness T = t/2, essential hole 2T (hole dia = t)
          - 2-1T : T = t,              essential hole 2T (hole dia = 2t)
          - 1-2T : T = t/2,            essential hole 1T (hole dia = t/2)
        Returns dict with designator, plate thickness (mm) and hole diameter.
        """
        t = max(float(t), 0.1)
        sensitivity = (sensitivity or "2-2T").upper()
        if sensitivity == "2-1T":
            iqi_t = t
            hole_dia = 2.0 * iqi_t
        elif sensitivity == "1-2T":
            iqi_t = t / 2.0
            hole_dia = 1.0 * iqi_t
        else:  # 2-2T default
            iqi_t = t / 2.0
            hole_dia = 2.0 * iqi_t
        return {
            "designator": sensitivity,
            "iqi_t_mm": iqi_t,
            "hole_dia_mm": hole_dia,
        }

    # ASTM E747 wire-type IQI: wire number -> nominal diameter (mm) and set.
    # Diameters per ASTM E747 (approximate nominal); set = wire-number range.
    E747_WIRE_DIA_MM = {
        1: 3.20, 2: 2.54, 3: 2.03, 4: 1.60, 5: 1.27, 6: 1.02,     # Set A
        7: 0.81, 8: 0.64, 9: 0.51, 10: 0.41, 11: 0.33, 12: 0.25,   # Set B
        13: 0.20, 14: 0.16, 15: 0.13, 16: 0.10, 17: 0.08, 18: 0.064,  # Set C
        19: 0.051, 20: 0.041, 21: 0.033,                           # Set D
    }
    E747_SETS = {"A": (1, 6), "B": (7, 12), "C": (13, 18), "D": (19, 21)}

    def get_astm_iqi_wire(self, t):
        """
        ASTM E747 wire-type IQI requirement (2 % sensitivity).
        Required wire diameter ~ 2 % of penetrated thickness; the wire number
        determines the set (A/B/C/D). Returns dict with set, wire number, diameter.
        """
        t = max(float(t), 0.1)
        req_dia = 0.02 * t
        # Finest wire that still meets the 2% requirement: highest wire number
        # (thinnest) whose diameter is >= required.
        wire = max(
            (n for n, d in self.E747_WIRE_DIA_MM.items() if d >= req_dia),
            default=21,
        )
        wset = next((s for s, (lo, hi) in self.E747_SETS.items() if lo <= wire <= hi), "D")
        return {
            "set": wset,
            "wire_no": wire,
            "wire_dia_mm": self.E747_WIRE_DIA_MM.get(wire, 0.0),
        }

    # -----------------------------------------------------------------------
    # Radiation safety — controlled / supervised area barrier distance
    # Dose-rate model:  D(R) = (Gamma * A) / R^2   [mSv/h when Gamma in
    # (mSv*m^2)/(h*GBq)-equivalent; here we use the classic gamma constants in
    # R*m^2/(h*Ci) and convert to dose rate at R metres].
    # Reference dose limits (common NDT practice):
    #   Controlled area  : 20 µSv/h (and 2.5 µSv/h for some regulations)
    #   Supervised area  : 7.5 µSv/h
    # Collimator attenuation applied as a number of half-value layers (HVL).
    # -----------------------------------------------------------------------
    # Gamma constants [R*m^2/(h*Ci)] — used for barrier distance.
    GAMMA_RM2_H_CI = {
        "isotope_ir192": 0.48,
        "isotope_se75": 0.203,
        "isotope_co60": 1.30,
        "isotope_yb169": 0.125,
        "isotope_tm170": 0.003,
    }
    # Gamma constants [mSv*m^2/(h*Ci)] — alternative common convention
    # (1 R/h ~ 0.0087 Sv/h; the rounded 1 R ~ 10 mSv approximation is used here
    # for the mSv convention, matching field slide-rule practice).
    GAMMA_MSV_M2_H_CI = {
        "isotope_ir192": 4.8,
        "isotope_se75": 2.03,
        "isotope_co60": 13.0,
        "isotope_yb169": 1.25,
        "isotope_tm170": 0.03,
    }
    # Half-lives in days for the isotope decay engine.
    ISOTOPE_HALF_LIVES = {
        "isotope_ir192": 73.83,
        "isotope_se75": 119.78,
        "isotope_co60": 1925.5,   # 5.271 y
        "isotope_yb169": 32.02,
        "isotope_tm170": 128.6,
    }
    # Approximate effective half-value layers [mm of lead] for collimator/shield.
    COLLIMATOR_HVL_MM_LEAD = {
        "isotope_ir192": 2.8,
        "isotope_se75": 1.2,
        "isotope_co60": 12.0,
        "isotope_yb169": 0.5,
        "isotope_tm170": 0.08,
    }

    def decay_days_since(self, calib_date, inspection_date=None):
        """Whole days between the calibration date and the inspection date
        (defaults to today). Accepts date/datetime objects or strings in
        common formats: YYYY-MM-DD, YYYY/MM/DD, DD.MM.YYYY, DD/MM/YYYY,
        DD-MM-YYYY. Returns 0.0 for unparseable dates instead of raising."""
        from datetime import date, datetime

        _DATE_FORMATS = (
            "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y",
        )

        def _to_date(d):
            if isinstance(d, datetime):
                return d.date()
            if isinstance(d, date):
                return d
            if isinstance(d, str):
                s = d.strip()
                if not s:
                    return None
                for fmt in _DATE_FORMATS:
                    try:
                        return datetime.strptime(s, fmt).date()
                    except ValueError:
                        continue
            return None

        c = _to_date(calib_date)
        if c is None:
            return 0.0
        t = _to_date(inspection_date) if inspection_date is not None else date.today()
        if t is None:
            return 0.0
        return (t - c).days

    def calculate_decayed_activity(self, initial_ci, calib_date, inspection_date=None,
                                   isotope="isotope_ir192"):
        """
        Current activity A(t) = A0 * 2^(-(t-t0)/T1/2) using the isotope half-life.
        Returns 0.0 if inputs are invalid.
        """
        try:
            a0 = float(initial_ci)
        except (TypeError, ValueError):
            return 0.0
        if a0 <= 0.0:
            return 0.0
        half_life = self.ISOTOPE_HALF_LIVES.get(isotope)
        if not half_life or half_life <= 0.0:
            return a0
        try:
            days = self.decay_days_since(calib_date, inspection_date)
        except Exception:
            # Never crash on a bad calibration/inspection date; report
            # undecayed activity so the caller can show a meaningful error.
            return a0
        if days <= 0.0:
            return a0
        return a0 * (2.0 ** (-days / half_life))

    def calculate_barrier_distance(self, source, activity_ci, limit_usvh=20.0,
                                   hvl_layers=0.0, hvls_per_cm=None, convention="r"):
        """
        Calculates the safe barrier distance R (m) such that the dose rate at R
        does not exceed `limit_usvh` µSv/h.

        Dose-rate at R metres (no shield):
          convention="r"  :  D[µSv/h] = (Gamma_R * A[Ci] / R^2) * 8697  (1 R/h = 8697 µSv/h)
          convention="msv":  D[µSv/h] = (Gamma_mSv * A[Ci] / R^2) * 1000 (1 mSv = 1000 µSv)

        With a collimator providing `hvl_layers` half-value layers of attenuation,
        the dose rate is divided by 2^layers.

        Returns (distance_m, dose_rate_at_1m_usvh, shielding_reduction).
        """
        if convention == "msv":
            gamma = self.GAMMA_MSV_M2_H_CI.get(source, 4.8)
            base = gamma * float(activity_ci) * 1000.0  # µSv/h at 1 m, unshielded
        else:
            gamma = self.GAMMA_RM2_H_CI.get(source, 0.48)
            base = gamma * float(activity_ci) * 8697.0  # µSv/h at 1 m, unshielded
        if activity_ci is None or activity_ci <= 0.0:
            return 0.0, 0.0, 1.0
        reduction = 2.0 ** hvl_layers
        shielded = base / reduction
        if shielded <= 0.0:
            return 0.0, 0.0, reduction
        r = (shielded / limit_usvh) ** 0.5
        return r, base, reduction

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
            # Source + material combination not covered by Table 2 at all
            source_name = source.replace("isotope_", "").upper()
            return True, None, None, (
                f"{source_name} + {material} is not defined in ISO 17636-2 Table 2; "
                "applicability should be confirmed with the contracting parties."
            )

        class_limits = material_limits.get(testing_class, None)
        if class_limits is None:
            # Source + material defined, but not for this testing class
            source_name = source.replace("isotope_", "").upper()
            return True, None, None, (
                f"{source_name} + {material} is not defined for "
                f"{testing_class.replace('_', ' ').title()} in ISO 17636-2 Table 2; "
                "applicability should be confirmed with the contracting parties."
            )

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
