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
        "cr_hires":    0.75,   # Web legacy alias for cr_highres
        "dda_si":      4.0,    # Flat Panel amorphous silicon (a-Si)
        "dda_se":      3.5,    # Flat Panel amorphous selenium (a-Se)
        "dda_gdos":    3.0,    # DDA with GdOS (Gadolinium Oxysulfide) scintillator
    }

    # Native basic spatial resolution SR_b,ref (µm) per detector family
    # (ISO 17636-2 Annex F / ISO 16371-1 / ASTM E2698)
    DETECTOR_NATIVE_SRB = {
        "cr_standard": 100.0,
        "cr_highres":  50.0,
        "cr_hires":    50.0,
        "dda_si":      130.0,
        "dda_se":      85.0,
        "dda_gdos":    160.0,
    }

    # Energy-dependent relative DQE(kV) curves for X-Ray sources (normalized at 120 kV)
    # Models Ba K-edge (37.4 keV) in CR, low-Z stopping drop in a-Se (Z=34) above 150 kV,
    # and Gd K-edge (50.2 keV, Z=64) high-energy retention in Gd2O2S.
    DETECTOR_XRAY_DQE_CURVES = {
        "cr_standard": [(60, 1.18), (100, 1.06), (120, 1.00), (160, 0.94), (220, 0.88), (300, 0.82), (400, 0.76)],
        "cr_highres":  [(60, 0.88), (100, 0.80), (120, 0.75), (160, 0.70), (220, 0.65), (300, 0.60), (400, 0.56)],
        "dda_si":      [(60, 4.30), (100, 4.10), (120, 4.00), (160, 3.80), (220, 3.50), (300, 3.20), (400, 2.90)],
        "dda_se":      [(60, 4.60), (100, 3.90), (120, 3.50), (150, 2.90), (200, 2.15), (300, 1.45), (400, 1.10)],
        "dda_gdos":    [(60, 2.75), (100, 2.92), (120, 3.00), (160, 3.15), (220, 3.20), (300, 2.95), (400, 2.65)],
    }
    DETECTOR_XRAY_DQE_CURVES["cr_hires"] = DETECTOR_XRAY_DQE_CURVES["cr_highres"]

    # Isotope-specific effective DQE factors by gamma photon energy
    DETECTOR_ISOTOPE_DQE = {
        "cr_standard": {
            "isotope_tm170": 1.12, "isotope_yb169": 1.04,
            "isotope_se75": 0.95,  "isotope_ir192": 0.86, "isotope_co60": 0.68,
        },
        "cr_highres": {
            "isotope_tm170": 0.84, "isotope_yb169": 0.78,
            "isotope_se75": 0.71,  "isotope_ir192": 0.64, "isotope_co60": 0.51,
        },
        "dda_si": {
            "isotope_tm170": 4.15, "isotope_yb169": 3.95,
            "isotope_se75": 3.65,  "isotope_ir192": 3.15, "isotope_co60": 2.25,
        },
        "dda_se": {
            "isotope_tm170": 4.10, "isotope_yb169": 3.40,
            "isotope_se75": 2.20,  "isotope_ir192": 1.40, "isotope_co60": 0.80,
        },
        "dda_gdos": {
            "isotope_tm170": 2.85, "isotope_yb169": 3.05,
            "isotope_se75": 3.25,  "isotope_ir192": 2.90, "isotope_co60": 2.10,
        },
    }
    DETECTOR_ISOTOPE_DQE["cr_hires"] = DETECTOR_ISOTOPE_DQE["cr_highres"]

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

    def calculate_f_min(self, d, b, testing_class, t=None, cap=0.0):
        """
        Calculates minimum source-to-object distance (f_min) in mm (Step 6)
        Formula: f >= C * d * b^(2/3)
        Class A: C = 7.5
        Class B: C = 15
        Per ISO 17636-1/2:2022 Clause 7.6:
        - If total weld thickness (t + cap) >= 1.2 * t, the b = t simplification
          does NOT apply and b_eff is at least (t + cap).
        - Otherwise, if b < 1.2 * t, b is replaced by t.
        """
        if testing_class == "class_a":
            c = 7.5
        else:
            c = 15.0

        b_eff, _ = self.get_effective_b(b, t, cap=cap)
        f_min = c * d * (b_eff ** (2/3))
        return f_min

    def get_effective_b(self, b, t, cap=0.0):
        """
        Returns (b_eff, applied) per ISO 17636-1/2:2022 Clause 7.6.
        - If t is provided and (t + cap) >= 1.2 * t:
          The b = t simplification does NOT apply because total weld thickness
          (t + cap) already meets or exceeds 1.2 * t; returns (max(b, t + cap), False).
        - Otherwise, if t is provided and b < 1.2 * t:
          Returns (t, True).
        - Otherwise returns (b, False).
        """
        if t is not None:
            w_weld = t + max(0.0, float(cap or 0.0))
            if w_weld >= 1.2 * t - 1e-9:
                return max(b, w_weld), False
            if b < 1.2 * t:
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

    def calculate_diagonal(self, width, height):
        """
        Diagonal of a rectangular receptor (film sheet or panel active area):
            diagonal = sqrt(width^2 + height^2)
        ISO 17636-1:2022 symbol df = "value of the diagonal extension of the
        film"; ISO 17636-2:2022 Formula (6) uses the detector size (dd).
        Returns 0.0 for invalid (non-positive) input.
        """
        try:
            w = float(width)
            h = float(height)
        except (TypeError, ValueError):
            return 0.0
        if w <= 0.0 or h <= 0.0:
            return 0.0
        return math.hypot(w, h)

    def calculate_coverage_min(self, receptor_size):
        """
        Minimum source-to-receptor distance so that the tube opening angle
        (2beta) covers the whole receptor.

        ISO 17636-1:2022 Formula (3)/(4) for film:
            SFD >= 0.5 * df / tan(beta), simplified to SFD >= 1.4 * df
            for the typical NDT opening angle 2beta = 40 deg.
        ISO 17636-2:2022 Formula (6)/(7) for digital detectors:
            SDD >= 0.5 * dd / tan(beta), simplified to SDD >= 1.4 * dd.

        `receptor_size` is the receptor diagonal (df or dd) in mm.
        Returns 0.0 (no constraint) for missing/invalid input.
        """
        try:
            size = float(receptor_size)
        except (TypeError, ValueError):
            return 0.0
        if size <= 0.0:
            return 0.0
        return 1.4 * size

    def calculate_sdd_min(self, dd):
        """
        Backwards-compatible alias of calculate_coverage_min for the digital
        detector size dd (ISO 17636-2:2022 Formula 7: SDD >= 1.4 * dd).
        """
        return self.calculate_coverage_min(dd)

    def is_central_projection(self, geometry, std_figure):
        """
        Returns True if the setup is central projection (panoramic source at
        the pipe centre): SWSI + Figure 5, in any of its variants:
          fig5  -> ISO 17636-1 (film)
          fig5a -> ISO 17636-2 (flexible detector)
          fig5b -> ISO 17636-2 (planar detector)
        """
        return geometry == "swsi" and std_figure in ("fig5", "fig5a", "fig5b")

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

    def calculate_annex_f_fmin(self, d, b, srb_um, testing_class="class_b"):
        """
        ISO 17636-2:2022 Annex F (informative), Formulae (F.4)/(F.5): the
        source-to-object distance f_min required so that the total unsharpness
        (geometric + inherent detector u_d = 2·SRb_detector) stays equivalent
        to film radiography:

            f_min = d · sqrt( b² / ( b^(2/3)/C² − (2·SRb_detector)² ) )

        with C = 7.5 for class A and 15 for class B. Returns the required f_min
        in mm, or ``None`` when the detector unsharpness cannot be compensated
        at this object-to-detector distance b (b below the b_min of Formulae
        F.2/F.3, i.e. the denominator is non-positive).
        """
        c = 7.5 if testing_class == "class_a" else 15.0
        try:
            d = float(d)
            b = float(b)
            srb = max(0.0, float(srb_um)) / 1000.0  # µm -> mm
        except (TypeError, ValueError):
            return None
        if d <= 0.0 or b <= 0.0:
            return None
        denom = (b ** (2.0 / 3.0)) / (c * c) - (2.0 * srb) ** 2
        if denom <= 0.0:
            return None
        return d * math.sqrt((b * b) / denom)

    def check_annex_f_compensation(self, d, b, srb_um, f_min_base, testing_class="class_b"):
        """
        ISO 17636-2:2022 Annex F (informative): is the Clause 7.6 f_min still
        sufficient once the inherent detector unsharpness u_d = 2·SRb_detector
        is included? Returns (needs_compensation, ratio) where
        ratio = required f_min / base f_min (inf when not compensable).
        """
        required = self.calculate_annex_f_fmin(d, b, srb_um, testing_class)
        if required is None:
            return True, float("inf")
        try:
            base = float(f_min_base)
        except (TypeError, ValueError):
            base = 0.0
        if base <= 0.0:
            return required > 0.0, float("inf")
        return required > base + 1e-9, required / base

    def get_single_wire_iqi(self, t, cap, testing_class, geometry, tech="digital", film_side=False, lang="tr"):
        """
        Determines target single wire IQI number (Step 8)
        Based on ISO 17636-1 Annex B for Analog, ISO 17636-2 Annex B for Digital.
        """
        # ISO 17636-1/2:2022 Annex B tables are indexed by the nominal wall
        # thickness t (single-wall) or the penetrated thickness w = 2t
        # (double-wall). Definitions 3.1/3.3 exclude weld reinforcement (cap),
        # so the cap is not added to the IQI reference thickness.
        if geometry in ["dwsi", "dwdi_elliptic", "dwdi_super"]:
            ref_thickness = 2 * t
        else:
            ref_thickness = t

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
                elif ref_thickness <= 48.0:
                    wire = 10
                elif ref_thickness <= 60.0:
                    wire = 9
                elif ref_thickness <= 85.0:
                    wire = 8
                elif ref_thickness <= 125.0:
                    wire = 7
                elif ref_thickness <= 225.0:
                    wire = 6
                elif ref_thickness <= 375.0:
                    wire = 5
                else:
                    wire = 4
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
                elif ref_thickness <= 12.0:
                    wire = 15
                elif ref_thickness <= 18.0:
                    wire = 14
                elif ref_thickness <= 30.0:
                    wire = 13
                elif ref_thickness <= 45.0:
                    wire = 12
                elif ref_thickness <= 55.0:
                    wire = 11
                elif ref_thickness <= 70.0:
                    wire = 10
                elif ref_thickness <= 100.0:
                    wire = 9
                elif ref_thickness <= 180.0:
                    wire = 8
                elif ref_thickness <= 300.0:
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
                    elif ref_thickness <= 32.0:
                        wire = 10
                    elif ref_thickness <= 40.0:
                        wire = 9
                    elif ref_thickness <= 55.0:
                        wire = 8
                    elif ref_thickness <= 85.0:
                        wire = 7
                    elif ref_thickness <= 150.0:
                        wire = 6
                    elif ref_thickness <= 250.0:
                        wire = 5
                    else:
                        wire = 4
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
                    elif ref_thickness <= 35.0:
                        wire = 11
                    elif ref_thickness <= 45.0:
                        wire = 10
                    elif ref_thickness <= 65.0:
                        wire = 9
                    elif ref_thickness <= 120.0:
                        wire = 8
                    elif ref_thickness <= 200.0:
                        wire = 7
                    elif ref_thickness <= 350.0:
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

        # Prefix the active standard (analog ISO 17636-1 / digital ISO 17636-2)
        table_name = f"ISO 17636-{1 if tech == 'analog' else 2} {table_name}"

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
        # ISO 17636-1/2:2022 Annex B tables are indexed by the nominal wall
        # thickness t (single-wall) or the penetrated thickness w = 2t
        # (double-wall). Definitions 3.1/3.3 exclude weld reinforcement (cap),
        # so the cap is not added to the IQI reference thickness.
        if geometry in ["dwsi", "dwdi_elliptic", "dwdi_super"]:
            ref_thickness = 2 * t
        else:
            ref_thickness = t

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

        # Prefix the active standard (analog ISO 17636-1 / digital ISO 17636-2)
        table_name = f"ISO 17636-{1 if tech == 'analog' else 2} {table_name}"

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
            elif source in ("isotope_yb169", "isotope_tm170"):
                # ISO 17636-2:2022 Table 3: Yb-169/Tm-170, w <= 5 mm -> Class B = 120
                src_name = "Yb-169" if source == "isotope_yb169" else "Tm-170"
                if w_nom <= 5.0:
                    base_snr = 70 if testing_class == "class_a" else 120
                    desc = f"{src_name} (w <= 5 mm)"
                else:
                    base_snr = 70 if testing_class == "class_a" else 100
                    desc = f"{src_name} (w > 5 mm)"
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
          D9=0.125mm, D8=0.160mm, D7=0.200mm, D6=0.250mm, D5=0.320mm, D4=0.400mm
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
            9: 0.125, 8: 0.160, 7: 0.200, 6: 0.250, 5: 0.320, 4: 0.400
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
        if d_num == 14:
            # Table B.14 note d: D 13+ (D 13 resolved with a >20 % dip) is
            # equivalent to D 14.
            d_str += (" — or D 13+ (dip > 20 %)" if lang == "en"
                      else " — veya D13+ (çukur > %20)")
        return d_str, d_num

    def _density_correction_factor(self, testing_class, film_class=None, ref_density=2.0, target_density=None):
        if target_density is None or target_density <= 0.0:
            target_density = 2.3 if testing_class == "class_b" else 2.0
        if abs(target_density - ref_density) < 1e-9:
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

    def annex_a_exposures(self, t, OD, distance, testing_class="class_b",
                          film_inside=False):
        """ISO 17636-1/2:2022 Annex A minimum exposures (digitized charts).

        ``distance`` is f (source-to-object) for the film/detector-inside
        arrangement (Figures 2/A.1/A.3) and SFD/SDD for the film/detector-
        outside arrangements (Figures 8/13, A.2/A.4). Returns ``None`` when the
        query falls outside the digitized chart range.
        """
        from src.core.annex_a import minimum_exposures
        return minimum_exposures(
            t=t, de=OD, distance=distance,
            testing_class=testing_class, film_inside=film_inside,
        )

    def calculate_dwsi_exposures(self, OD, t, sfd, testing_class):
        """
        Required minimum number of exposures for DWSI geometry.

        ISO 17636-1/2:2022 Annex A, Figures A.2 (class B) / A.4 (class A):
        the film/detector is outside, so the chart is a function of t/De and
        De/SFD. For DWSI the source is outside the pipe, so SFD is clamped to
        the outside diameter (source on the surface) before the lookup.

        Falls back to the geometric ray-tracing solver when the query is
        outside the digitized chart range.
        """
        try:
            OD = float(OD)
            t = float(t)
            sfd = float(sfd)
        except (TypeError, ValueError):
            return 3

        sfd_eff = max(sfd, OD)
        annex_n = self.annex_a_exposures(
            t, OD, sfd_eff, testing_class, film_inside=False)
        if annex_n is not None:
            return max(3, int(annex_n))

        # Legacy geometric fallback (only for out-of-chart inputs).
        R = OD / 2.0
        Ri = R - t
        if R <= 0.0 or Ri <= 0.0 or t <= 0.0:
            # Degenerate "pipe" (no inner cavity); no geometric DWSI coverage model.
            return 3

        # Physical floor: source outside the pipe (Figure 14 - source on surface)
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

        return geo_n

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

        # A non-positive panel width makes the coverage angle zero, which would
        # otherwise yield an absurd exposure count (ceil(pi / 1e-6)). Treat it
        # as invalid input so the graph-based count governs instead.
        try:
            panel_width = float(panel_width)
        except (TypeError, ValueError):
            panel_width = 0.0
        if panel_width <= 0.0:
            return self._panel_result_fixed(
                1, od, t, cap, "invalid_panel_geometry", panel_height)

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

    def get_detector_effective_dqe(self, detector_type, source="x_ray", kv=None):
        """
        Returns the effective relative Detective Quantum Efficiency factor η_DQE(E)
        for the given digital detector type and radiation energy/source.
        Normalized so X-Ray at 120 kV equals DETECTOR_TYPE_FACTORS[detector_type].
        """
        base_dqe = self.DETECTOR_TYPE_FACTORS.get(detector_type, 1.0)
        if source == "x_ray":
            if kv is None:
                return base_dqe
            kv_f = float(kv)
            pts = self.DETECTOR_XRAY_DQE_CURVES.get(detector_type)
            if not pts:
                return base_dqe
            if kv_f <= pts[0][0]:
                return pts[0][1]
            if kv_f >= pts[-1][0]:
                return pts[-1][1]
            for i in range(len(pts) - 1):
                k1, d1 = pts[i]
                k2, d2 = pts[i + 1]
                if k1 <= kv_f <= k2:
                    frac = (kv_f - k1) / (k2 - k1) if k2 != k1 else 0.0
                    return d1 + frac * (d2 - d1)
            return base_dqe
        else:
            iso_map = self.DETECTOR_ISOTOPE_DQE.get(detector_type)
            if iso_map and source in iso_map:
                return iso_map[source]
            return base_dqe

    def get_srb_dose_factor(self, detector_type, app_srb=None):
        """
        Calculates the spatial resolution quantum dose correction factor k_SRb
        per ISO 17636-2 Annex F & Rose photon statistics:
            k_SRb = clamp((SR_b,ref / SR_b,applied)^2, 0.25, 4.0)
        When app_srb is None (not specified), returns (1.0, srb_ref).
        """
        srb_ref = self.DETECTOR_NATIVE_SRB.get(detector_type, 100.0)
        if app_srb is None or float(app_srb) <= 0.0:
            return 1.0, srb_ref
        srb_val = max(10.0, float(app_srb))
        k_srb = max(0.25, min(4.0, (srb_ref / srb_val) ** 2))
        return k_srb, srb_ref

    def calculate_dda_frame_integration(
        self, base_time_sec, sdd, w_eff, source, output_val,
        detector_type, target_snr, kv=None, material="steel",
        srb_factor=1.0, dqe_factor=3.5, testing_class="class_b",
    ):
        """
        Computes DDA Flat Panel frame integration parameters (t_frame × N_frames)
        per ASTM E2698 / ISO 17636-2 Clause 7.4 to prevent 14/16-bit ADC saturation
        while achieving target normalized SNR_N by frame averaging (SNR_N ∝ √N_frames).
        Ensures standards-compliant frame averaging floors (Class A >= 16, Class B >= 32)
        and realistic industrial integration times (0.10s - 2.0s) & generator limits (>= 2.0s).
        """
        spec = (
            ExposureChartDatabase.DDA_PANEL_TABLE.get(detector_type)
            if ExposureChartDatabase is not None and detector_type in ExposureChartDatabase.DDA_PANEL_TABLE
            else {
                "panel_class": "DDA Düz Panel",
                "srb_ref_um": self.DETECTOR_NATIVE_SRB.get(detector_type, 130.0),
                "frame_target_dose_ugy": 15.0,
                "single_frame_snr_ref": 42.0,
                "target_gray_pct": 65.0,
            }
        )
        frame_dose_target = spec.get("frame_target_dose_ugy", 15.0)
        snr_1frame_ref = spec.get("single_frame_snr_ref", 42.0)
        target_gray_pct = spec.get("target_gray_pct", 65.0)
        target_adu_16bit = int(round(65535 * (target_gray_pct / 100.0)))

        # Required number of frames from single-frame quantum SNR at 65% saturation
        snr_req = max(20.0, float(target_snr if target_snr else 100.0))
        dqe_norm = max(0.3, dqe_factor / 3.5)
        snr_1frame_eff = snr_1frame_ref * math.sqrt(dqe_norm / max(0.25, srb_factor))

        # Standard-compliant frame averaging floor per ISO 17636-2 / ASTM E2698:
        # Minimum averaging: Class A >= 16 frames, Class B >= 32 frames to suppress fixed-pattern noise
        is_class_b = str(testing_class).lower() == "class_b"
        min_frames = 32 if is_class_b else 16
        n_frames_snr = max(min_frames, int(math.ceil((snr_req / max(5.0, snr_1frame_eff)) ** 2)))

        # Derive single-frame integration time from total dose time & frame bounds [0.10s, 2.0s]
        t_raw = max(0.10, float(base_time_sec))
        t_frame_ideal = t_raw / float(n_frames_snr)

        if t_frame_ideal < 0.10:
            t_frame_sec = 0.10
            n_frames = n_frames_snr
        elif t_frame_ideal > 2.0:
            # Cap single frame at 2.0 s to avoid dark-current thermal saturation on uncooled panels
            t_frame_sec = 2.0
            n_frames = max(n_frames_snr, int(math.ceil(t_raw / t_frame_sec)))
        else:
            t_frame_sec = round(t_frame_ideal, 2)
            if t_frame_sec < 0.10:
                t_frame_sec = 0.10
            n_frames = n_frames_snr

        # Industrial X-ray generator physical exposure floor (ramp-up & preheating >= 2.0 s)
        total_acq_sec = float(n_frames) * float(t_frame_sec)
        if source == "x_ray" and total_acq_sec < 2.0:
            t_frame_candidate = round(2.0 / float(n_frames), 2)
            if t_frame_candidate >= 0.10:
                t_frame_sec = max(t_frame_sec, t_frame_candidate)
            else:
                n_frames = max(n_frames, int(math.ceil(2.0 / t_frame_sec)))
            total_acq_sec = float(n_frames) * float(t_frame_sec)

        fps = round(1.0 / max(0.01, t_frame_sec), 2)
        t_frame_ms = round(t_frame_sec * 1000.0, 1)
        dose_rate_ugy_s = frame_dose_target / max(0.05, t_frame_sec)
        total_dose_ugy = dose_rate_ugy_s * total_acq_sec

        return {
            "t_frame_sec": t_frame_sec,
            "t_frame_ms": t_frame_ms,
            "fps": fps,
            "n_frames": n_frames,
            "total_acq_sec": round(total_acq_sec, 2),
            "frame_target_dose_ugy": frame_dose_target,
            "total_dose_ugy": round(total_dose_ugy, 1),
            "dose_rate_ugy_s": round(dose_rate_ugy_s, 2),
            "snr_1frame": round(snr_1frame_eff, 1),
            "target_gray_pct": target_gray_pct,
            "target_adu_16bit": target_adu_16bit,
            "panel_class": spec.get("panel_class", "DDA Düz Panel"),
        }

    def calculate_exposure_time(self, sfd, w_eff, source, output_val, base_factor,
                                 tech, testing_class="class_b",
                                 film_class="C5", detector_type="cr_standard",
                                 kv=None, material="steel",
                                 chart_source=None, chart_db=None,
                                 film_model=None, density=None,
                                 target_snr=None, app_srb=None):
        """
        Calculates exposure time in minutes and seconds (Step 10).
        Delegates to `calculate_exposure_time_details` and returns
        `(minutes, seconds, time_seconds)`.
        """
        details = self.calculate_exposure_time_details(
            sfd=sfd, w_eff=w_eff, source=source, output_val=output_val,
            base_factor=base_factor, tech=tech, testing_class=testing_class,
            film_class=film_class, detector_type=detector_type, kv=kv,
            material=material, chart_source=chart_source, chart_db=chart_db,
            film_model=film_model, density=density, target_snr=target_snr,
            app_srb=app_srb,
        )
        return details["minutes"], details["seconds"], details["time_seconds"]

    def calculate_exposure_time_details(self, sfd, w_eff, source, output_val, base_factor,
                                        tech, testing_class="class_b",
                                        film_class="C5", detector_type="cr_standard",
                                        kv=None, material="steel",
                                        chart_source=None, chart_db=None,
                                        film_model=None, density=None,
                                        target_snr=None, app_srb=None):
        """
        Full exposure-time calculation returning both timing values and a
        structured `provenance` dictionary explaining the active method,
        equations, material attenuation/REF parameters, and receptor corrections.
        """
        sfd = float(sfd)
        w_eff = float(w_eff)
        output_safe = max(0.01, float(output_val))
        base_factor = float(base_factor)
        ref_factor = self.get_ref_factor(material)
        w_eq_steel = w_eff * ref_factor

        # Target OD & film parameters (analog)
        target_od = float(density) if (density is not None and float(density) > 0.0) else (
            2.3 if testing_class == "class_b" else 2.0
        )
        film_speed = self.FILM_SPEED_FACTORS.get(film_class, 16.0)
        gradient = self.FILM_GRADIENT.get(film_class, 3.0)
        od_factor = self._density_correction_factor(
            testing_class, film_class, ref_density=2.0, target_density=target_od
        )

        # Target SNR_N, energy-dependent DQE(E), and SR_b quantum dose parameters (digital)
        det_factor_static = self.DETECTOR_TYPE_FACTORS.get(detector_type, 1.0)
        det_factor = self.get_detector_effective_dqe(detector_type, source=source, kv=kv)
        srb_factor, srb_ref = self.get_srb_dose_factor(detector_type, app_srb=app_srb)
        is_dda = detector_type in ("dda_si", "dda_se", "dda_gdos")

        if target_snr is not None and float(target_snr) > 0.0:
            snr_target_used = float(target_snr)
            snr_factor = (snr_target_used / 70.0) ** 2
            snr_is_dynamic = True
        else:
            snr_target_used = 130.0 if testing_class == "class_b" else 70.0
            snr_factor = self.SNR_CORRECTION.get(testing_class, 1.0)
            snr_is_dynamic = False

        requested_method = chart_source if (chart_source and chart_source != "model") else "model"
        active_method = "model"
        fallback_reason = None

        # ── Chart-based routing ───────────────────────────────────────────────
        if requested_method != "model":
            if chart_db is None:
                if ExposureChartDatabase is not None:
                    json_path = resource_path("exposure_chart_dataset.json")
                    if os.path.exists(json_path):
                        chart_db = ExposureChartDatabase(json_path)
                    else:
                        chart_db = ExposureChartDatabase()
                        chart_db.generate_type_x_chart(self)
                else:
                    raise ImportError("ExposureChartDatabase not available; cannot use chart_source")
            elif not getattr(chart_db, "TYPE_X_CHART", None):
                chart_db.generate_type_x_chart(self)

            # If in digital mode and an analog film chart was passed, redirect to digital chart
            eff_chart = chart_source
            if tech == "digital" and chart_source in ("AA400", "MX125", "T200", "HS800", "M100", "rfactor"):
                eff_chart = "dda_panel_chart" if is_dda else "cr_ips_chart"

            # 1) Digital CR IPS (ISO 16371-1) or DDA Panel (ASTM E2698) Chart Path
            if eff_chart in ("cr_ips_chart", "dda_panel_chart"):
                det_for_chart = detector_type
                if eff_chart == "cr_ips_chart" and is_dda:
                    det_for_chart = "cr_standard"
                elif eff_chart == "dda_panel_chart" and not is_dda:
                    det_for_chart = "dda_si"

                if source != "x_ray":
                    t_min = chart_db.calculate_exposure_time_digital_rfactor(
                        sdd=sfd, w=w_eff, source=source, activity=output_safe,
                        detector_type=det_for_chart, target_snr=snr_target_used,
                        srb_factor=srb_factor, ref_factor=ref_factor,
                    )
                    r_dig, spec = chart_db.lookup_digital_r_factor(det_for_chart, source)
                    if t_min is not None and t_min > 0 and r_dig is not None:
                        active_method = eff_chart
                        hvl = chart_db.HVL.get(source, 13.2)
                        gamma = chart_db.GAMMA.get(source, 0.48)
                        attenuation = 2.0 ** (w_eq_steel / hvl)
                        time_seconds = min(864000.0, t_min * 60.0)
                        dda_frame = (
                            self.calculate_dda_frame_integration(
                                time_seconds, sfd, w_eff, source, output_safe,
                                det_for_chart, snr_target_used, kv=kv,
                                material=material, srb_factor=srb_factor, dqe_factor=det_factor,
                            )
                            if (is_dda or eff_chart == "dda_panel_chart") else None
                        )
                        minutes = int(time_seconds // 60)
                        seconds = int(time_seconds % 60)
                        prov = {
                            "method": active_method,
                            "requested_method": requested_method,
                            "fallback_reason": None,
                            "tech": tech,
                            "source": source,
                            "material": material,
                            "ref_factor": ref_factor,
                            "w_eff": w_eff,
                            "w_eq_steel": w_eq_steel,
                            "sfd": sfd,
                            "output_val": output_safe,
                            "detector_type": det_for_chart,
                            "detector_class_label": spec.get("ips_class") or spec.get("panel_class", det_for_chart),
                            "r_factor_digital": r_dig,
                            "hvl": hvl,
                            "gamma": gamma,
                            "attenuation": attenuation,
                            "det_factor": det_factor,
                            "target_snr": snr_target_used,
                            "snr_factor": snr_factor,
                            "srb_factor": srb_factor,
                            "srb_ref": srb_ref,
                            "app_srb": app_srb,
                            "dda_frame": dda_frame,
                            "t_minutes_base": t_min,
                            "time_seconds": time_seconds,
                        }
                        return {
                            "minutes": minutes,
                            "seconds": seconds,
                            "time_seconds": time_seconds,
                            "provenance": prov,
                        }
                else:
                    # X-Ray source with CR IPS or DDA Panel chart -> use digital X-Ray table
                    eff_chart = "digital_xray_chart"

            # 2) Digital X-Ray Chart / Type X Chart Path
            if eff_chart in ("type_x", "digital_xray_chart"):
                if source != "x_ray":
                    if tech == "digital":
                        # Route isotope to CR/DDA digital R-factor table seamlessly
                        alt_chart = "dda_panel_chart" if is_dda else "cr_ips_chart"
                        t_min = chart_db.calculate_exposure_time_digital_rfactor(
                            sdd=sfd, w=w_eff, source=source, activity=output_safe,
                            detector_type=detector_type, target_snr=snr_target_used,
                            srb_factor=srb_factor, ref_factor=ref_factor,
                        )
                        r_dig, spec = chart_db.lookup_digital_r_factor(detector_type, source)
                        if t_min is not None and t_min > 0 and r_dig is not None:
                            active_method = alt_chart
                            hvl = chart_db.HVL.get(source, 13.2)
                            gamma = chart_db.GAMMA.get(source, 0.48)
                            attenuation = 2.0 ** (w_eq_steel / hvl)
                            time_seconds = min(864000.0, t_min * 60.0)
                            dda_frame = (
                                self.calculate_dda_frame_integration(
                                    time_seconds, sfd, w_eff, source, output_safe,
                                    detector_type, snr_target_used, kv=kv,
                                    material=material, srb_factor=srb_factor, dqe_factor=det_factor,
                                    testing_class=testing_class,
                                )
                                if is_dda else None
                            )
                            if is_dda and dda_frame:
                                time_seconds = max(time_seconds, dda_frame["total_acq_sec"])
                            minutes = int(time_seconds // 60)
                            seconds = int(time_seconds % 60)
                            prov = {
                                "method": active_method,
                                "requested_method": requested_method,
                                "fallback_reason": None,
                                "tech": tech,
                                "source": source,
                                "material": material,
                                "ref_factor": ref_factor,
                                "w_eff": w_eff,
                                "w_eq_steel": w_eq_steel,
                                "sfd": sfd,
                                "output_val": output_safe,
                                "detector_type": detector_type,
                                "detector_class_label": spec.get("ips_class") or spec.get("panel_class", detector_type),
                                "r_factor_digital": r_dig,
                                "hvl": hvl,
                                "gamma": gamma,
                                "attenuation": attenuation,
                                "det_factor": det_factor,
                                "target_snr": snr_target_used,
                                "snr_factor": snr_factor,
                                "srb_factor": srb_factor,
                                "srb_ref": srb_ref,
                                "app_srb": app_srb,
                                "dda_frame": dda_frame,
                                "t_minutes_base": t_min,
                                "time_seconds": time_seconds,
                            }
                            return {
                                "minutes": minutes,
                                "seconds": seconds,
                                "time_seconds": time_seconds,
                                "provenance": prov,
                            }
                    logger.warning("Type X chart is for X-ray only; falling back to physics model")
                    fallback_reason = "type_x_requires_xray"
                else:
                    kv_eff = float(kv) if kv is not None else 120.0
                    exposure_mamin = chart_db.get_type_x_exposure(kv_eff, w_eq_steel, interpolate=True)
                    if exposure_mamin is not None and exposure_mamin > 0:
                        sfd_ref = 700.0
                        sfd_correction = (sfd / sfd_ref) ** 2
                        if tech == "analog":
                            receptor_mod = od_factor * (16.0 / film_speed)
                        else:
                            receptor_mod = (snr_factor * srb_factor) / det_factor
                        t_min = (exposure_mamin * sfd_correction * receptor_mod) / output_safe
                        if t_min > 0:
                            active_method = "digital_xray_chart" if (tech == "digital" and chart_source == "digital_xray_chart") else "type_x"
                            time_seconds = min(864000.0, t_min * 60.0)
                            dda_frame = (
                                self.calculate_dda_frame_integration(
                                    time_seconds, sfd, w_eff, source, output_safe,
                                    detector_type, snr_target_used, kv=kv_eff,
                                    material=material, srb_factor=srb_factor, dqe_factor=det_factor,
                                    testing_class=testing_class,
                                )
                                if (tech == "digital" and is_dda) else None
                            )
                            if tech == "digital" and is_dda and dda_frame:
                                time_seconds = max(time_seconds, dda_frame["total_acq_sec"])
                            minutes = int(time_seconds // 60)
                            seconds = int(time_seconds % 60)
                            prov = {
                                "method": active_method,
                                "requested_method": requested_method,
                                "fallback_reason": None,
                                "tech": tech,
                                "source": source,
                                "material": material,
                                "ref_factor": ref_factor,
                                "w_eff": w_eff,
                                "w_eq_steel": w_eq_steel,
                                "kv": kv_eff,
                                "sfd": sfd,
                                "sfd_ref": sfd_ref,
                                "sfd_correction": sfd_correction,
                                "output_val": output_safe,
                                "exposure_mamin_chart": exposure_mamin,
                                "receptor_mod": receptor_mod,
                                "film_class": film_class if tech == "analog" else None,
                                "film_speed": film_speed if tech == "analog" else None,
                                "gradient": gradient if tech == "analog" else None,
                                "target_od": target_od if tech == "analog" else None,
                                "od_factor": od_factor if tech == "analog" else None,
                                "detector_type": detector_type if tech == "digital" else None,
                                "det_factor": det_factor if tech == "digital" else None,
                                "target_snr": snr_target_used if tech == "digital" else None,
                                "snr_factor": snr_factor if tech == "digital" else None,
                                "srb_factor": srb_factor if tech == "digital" else None,
                                "srb_ref": srb_ref if tech == "digital" else None,
                                "app_srb": app_srb if tech == "digital" else None,
                                "dda_frame": dda_frame,
                                "t_minutes_base": t_min,
                                "time_seconds": time_seconds,
                            }
                            return {
                                "minutes": minutes,
                                "seconds": seconds,
                                "time_seconds": time_seconds,
                                "provenance": prov,
                            }
                    fallback_reason = "type_x_out_of_range"

            # 3) Analog R-Factor (film / SCRATA slide rule) chart path
            elif eff_chart not in ("dda_frame_method",):
                resolved_film = self._resolve_chart_film(chart_source, film_model, film_class)
                if resolved_film is not None:
                    r_factor = chart_db.lookup_r_factor(resolved_film, source)
                    if r_factor is not None and source in chart_db.HVL:
                        od_for_rfactor = float(density) if (density is not None and float(density) > 0.0) else (
                            2.0 if density == 2.0 else target_od
                        )
                        result = self._calc_from_rfactor(
                            chart_db, resolved_film, source, sfd, w_eff, output_safe,
                            od_for_rfactor, ref_factor=ref_factor,
                        )
                        if result is not None and result > 0:
                            active_method = "rfactor"
                            hvl = chart_db.HVL.get(source, 13.2)
                            gamma = chart_db.GAMMA.get(source, 0.48)
                            rel_speed = chart_db.FILM_RELATIVE_SPEED.get(resolved_film, 1.0)
                            r_aa400 = chart_db.lookup_r_factor("AA400", source)
                            effective_r = (
                                (r_aa400 / rel_speed)
                                if (r_aa400 is not None and rel_speed > 0 and resolved_film != "AA400")
                                else r_factor
                            )
                            attenuation = 2.0 ** (w_eq_steel / hvl)
                            density_corr = 10.0 ** ((od_for_rfactor - 2.0) / 2.0)
                            time_seconds = min(864000.0, result * 60.0)
                            minutes = int(time_seconds // 60)
                            seconds = int(time_seconds % 60)
                            prov = {
                                "method": "rfactor",
                                "requested_method": requested_method,
                                "fallback_reason": None,
                                "tech": tech,
                                "source": source,
                                "material": material,
                                "ref_factor": ref_factor,
                                "w_eff": w_eff,
                                "w_eq_steel": w_eq_steel,
                                "sfd": sfd,
                                "output_val": output_safe,
                                "film_key": resolved_film,
                                "film_class": film_class,
                                "r_factor_raw": r_factor,
                                "r_factor_eff": effective_r,
                                "rel_speed": rel_speed,
                                "hvl": hvl,
                                "gamma": gamma,
                                "attenuation": attenuation,
                                "target_od": od_for_rfactor,
                                "od_factor": density_corr,
                                "t_minutes_base": result,
                                "time_seconds": time_seconds,
                            }
                            return {
                                "minutes": minutes,
                                "seconds": seconds,
                                "time_seconds": time_seconds,
                                "provenance": prov,
                            }
                    else:
                        logger.warning(
                            "Film %s has no R-Factor data for source %s; falling back to physics model",
                            resolved_film, source
                        )
                        fallback_reason = "rfactor_source_unavailable"
                else:
                    logger.warning(
                        "chart_source=%s not recognized; falling back to physics model",
                        chart_source
                    )
                    fallback_reason = "chart_unrecognized"

        # ── Physics Model & ASTM E2698 DDA Frame Method ───────────────────────
        kv_eff = None
        mu_steel_base = None
        if source == "x_ray":
            kv_eff = float(kv) if kv is not None else 120.0
            mu_raw = self.get_mu_from_kv(kv_eff, material)
            mu = self._apply_beam_hardening(mu_raw, w_eff, source, kv_eff, material)
            beam_hardening_pct = (1.0 - mu / mu_raw) * 100.0 if mu_raw > 0 else 0.0
        else:
            MU = {
                "isotope_ir192": 0.035,   # Iridium-192  (0.37 MeV avg)
                "isotope_se75":  0.055,   # Selenium-75  (0.27 MeV avg)
                "isotope_co60":  0.022,   # Cobalt-60    (1.25 MeV avg)
                "isotope_yb169": 0.115,   # Ytterbium-169 (0.13 MeV avg)
                "isotope_tm170": 0.30,    # Thulium-170   (0.084 MeV avg)
            }
            mu_steel_base = MU.get(source, 0.035)
            # Scale isotope linear attenuation coefficient by material REF
            mu_raw = mu_steel_base * ref_factor
            mu = mu_raw
            beam_hardening_pct = 0.0

        try:
            exponent = min(700.0, mu * w_eff)
            attenuation = math.exp(exponent)
        except OverflowError:
            exponent = 700.0
            attenuation = 1e300

        # ── Base exposure time (source + geometry + material only)
        sfd_m = sfd / 1000.0   # mm → m
        t_base = (base_factor * (sfd_m ** 2) * attenuation) / output_safe

        if tech == "analog":
            time_minutes = t_base * od_factor / film_speed
        else:  # digital
            time_minutes = t_base * (snr_factor * srb_factor) / det_factor

        # ── kVp⁵ sanity check (X-ray only) ──────────────────────────────────
        if source == "x_ray" and kv_eff is not None and time_minutes > 0:
            self._check_kvp5(kv_eff, time_minutes, material, tech, film_class, testing_class)

        # ── Convert to seconds and cap at 10 days
        time_seconds = min(864000.0, time_minutes * 60.0)

        # ── DDA Frame Integration (ASTM E2698: N_frames × t_frame) ──────────
        dda_frame = None
        if tech == "digital" and (is_dda or requested_method == "dda_frame_method"):
            det_for_dda = detector_type if is_dda else "dda_si"
            dda_frame = self.calculate_dda_frame_integration(
                time_seconds, sfd, w_eff, source, output_safe,
                det_for_dda, snr_target_used, kv=kv_eff,
                material=material, srb_factor=srb_factor, dqe_factor=det_factor,
                testing_class=testing_class,
            )
            if requested_method == "dda_frame_method":
                active_method = "dda_frame_method"
                fallback_reason = None
                time_seconds = min(864000.0, dda_frame["total_acq_sec"])
                time_minutes = time_seconds / 60.0
            elif is_dda and dda_frame:
                time_seconds = max(time_seconds, dda_frame["total_acq_sec"])
                time_minutes = time_seconds / 60.0

        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)

        prov = {
            "method": active_method,
            "requested_method": requested_method,
            "fallback_reason": fallback_reason,
            "tech": tech,
            "source": source,
            "material": material,
            "ref_factor": ref_factor,
            "w_eff": w_eff,
            "w_eq_steel": w_eq_steel,
            "kv": kv_eff,
            "mu_steel_base": mu_steel_base,
            "mu_raw": mu_raw,
            "mu_eff": mu,
            "beam_hardening_pct": beam_hardening_pct,
            "exponent": exponent,
            "attenuation": attenuation,
            "base_factor": base_factor,
            "sfd": sfd,
            "sfd_m": sfd_m,
            "output_val": output_safe,
            "t_base_min": t_base,
            "film_class": film_class if tech == "analog" else None,
            "film_speed": film_speed if tech == "analog" else None,
            "gradient": gradient if tech == "analog" else None,
            "target_od": target_od if tech == "analog" else None,
            "od_factor": od_factor if tech == "analog" else None,
            "detector_type": detector_type if tech == "digital" else None,
            "det_factor": det_factor if tech == "digital" else None,
            "det_factor_static": det_factor_static if tech == "digital" else None,
            "target_snr": snr_target_used if tech == "digital" else None,
            "snr_factor": snr_factor if tech == "digital" else None,
            "snr_is_dynamic": snr_is_dynamic if tech == "digital" else None,
            "srb_factor": srb_factor if tech == "digital" else None,
            "srb_ref": srb_ref if tech == "digital" else None,
            "app_srb": app_srb if tech == "digital" else None,
            "dda_frame": dda_frame,
            "t_minutes_base": time_minutes,
            "time_seconds": time_seconds,
        }
        return {
            "minutes": minutes,
            "seconds": seconds,
            "time_seconds": time_seconds,
            "provenance": prov,
        }

    def calculate_trial_shot_correction(self, tech, t1_sec, sfd1, sfd2,
                                        measured_quality, target_quality,
                                        film_class="C5"):
        """
        Calculates the corrected exposure time t2 (seconds) and field factor
        from a known trial exposure (t1_sec at sfd1 yielding measured_quality).
          - Analog:  t2 = t1 × 10^((D_target - D_measured) / G̅) × (SFD2 / SFD1)²
          - Digital: t2 = t1 × (SNR_target / SNR_measured)² × (SDD2 / SDD1)²
        """
        t1 = max(0.1, float(t1_sec))
        d1 = max(10.0, float(sfd1))
        d2 = max(10.0, float(sfd2))
        q_meas = max(0.01, float(measured_quality))
        q_targ = max(0.01, float(target_quality))
        dist_ratio = (d2 / d1) ** 2
        if tech == "analog":
            gradient = self.FILM_GRADIENT.get(film_class, 3.0)
            qual_ratio = 10.0 ** ((q_targ - q_meas) / gradient)
        else:
            qual_ratio = (q_targ / q_meas) ** 2
        t2 = t1 * qual_ratio * dist_ratio
        return {
            "t2_sec": t2,
            "quality_ratio": qual_ratio,
            "distance_ratio": dist_ratio,
            "total_ratio": qual_ratio * dist_ratio,
        }

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

    def _calc_from_rfactor(self, chart_db, film_key, source, sfd, w, activity,
                           density=2.0, ref_factor=1.0):
        if source not in chart_db.HVL:
            return None
        t_min = chart_db.calculate_exposure_time_rfactor(
            sfd=sfd, w=w, source=source, activity=activity,
            film_key=film_key, density=density if density is not None else 2.0,
            ref_factor=ref_factor,
        )
        return t_min

    def _calc_from_type_x(self, chart_db, kv, thickness, ma, sfd, ref_factor=1.0):
        kv_f = float(kv) if kv is not None else 120.0
        w_eq = float(thickness) * float(ref_factor if ref_factor and ref_factor > 0 else 1.0)
        exposure_mamin = chart_db.get_type_x_exposure(kv_f, w_eq, interpolate=True)
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
        if kv <= 0.0:
            return
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


    # ISO 17636-1:2022 Clause 6.9 — one film system class better (Se-75, w < 12 mm)
    _SE75_FILM_UPGRADE = {
        "C6": "C5", "C5": "C4", "C4": "C3", "C3": "C2", "C2": "C1", "C1": "C1",
    }

    def get_required_film_class(self, w_nom, testing_class, material, source=None, kv=None):
        """
        Determines the minimum required ISO 11699-1 film system class (Step 7)
        based on ISO 17636-1:2022 Table 3 (steel/copper/nickel-based alloys) and
        Table 4 (aluminium/titanium), plus the Clause 6.9 Se-75 thin-section rule.
        """
        if material in ["steel", "copper_nickel"]:
            if testing_class == "class_a":
                # Table 3: testing class A is C5 for every supported (<= 1 MV) source
                return "C5"
            # Table 3: testing class B (source- and kV-dependent)
            if source == "x_ray":
                kv_eff = float(kv) if kv is not None else 120.0
                if kv_eff <= 150.0:
                    base_film = "C3"
                elif kv_eff <= 250.0:
                    base_film = "C4"
                elif kv_eff <= 500.0:
                    base_film = "C4" if w_nom <= 50.0 else "C5"
                else:
                    # 500 kV < U <= 1 000 kV (app has no > 1 MV rows)
                    base_film = "C4" if w_nom <= 75.0 else "C5"
            elif source in ("isotope_yb169", "isotope_tm170"):
                base_film = "C3" if w_nom <= 5.0 else "C4"
            elif source == "isotope_co60":
                base_film = "C4" if w_nom <= 100.0 else "C5"
            else:
                # Se-75, Ir-192 and any other isotope
                base_film = "C4"

            # Clause 6.9 exception: Se-75 with w_nom < 12 mm Class B requires
            # at least one film system class better than Table 3.
            if source == "isotope_se75" and w_nom < 12.0:
                return self._SE75_FILM_UPGRADE.get(base_film, base_film)
            return base_film
        else:
            # Aluminium / titanium — Table 4: class A C5, class B C3
            return "C5" if testing_class == "class_a" else "C3"

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

    def check_film_class_compliance(self, film_class_used, testing_class, w_nom, material, source=None, kv=None):
        """
        Verifies if the film class meets the minimum requirements of ISO 17636-1:2022
        Tables 3/4. Returns (is_compliant, message)
        """
        req_film = self.get_required_film_class(w_nom, testing_class, material, source, kv=kv)
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
        """Maximum allowed geometric unsharpness (mm) for material thickness
        t (mm) per ASME Sec V Art 2, Table T-274.2. The table's metric column
        uses 50/75/100 mm boundaries:
          t < 50          -> 0.51 mm  (less than 2 in.)
          50 <= t <= 75   -> 0.76 mm  (2 through 3 in.)
          75 < t <= 100   -> 1.02 mm  (over 3 through 4 in.)
          t > 100         -> 1.78 mm  (over 4 in.)"""
        if t is None or t <= 0.0:
            return 0.51
        if t < 50.0:
            return 0.51
        if t <= 75.0:
            return 0.76
        if t <= 100.0:
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
