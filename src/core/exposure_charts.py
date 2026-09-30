import csv
import io
import json
import math
import os
import sys


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ExposureChartDatabase:
    # Carestream R-Factor table (R values at D=2.0)
    R_FACTOR_TABLE = {
        "M100": {
            "isotope_ir192": 0.36,
            "isotope_se75": 0.20,
            "isotope_co60": 0.07,
            "isotope_yb169": 0.12,
            "isotope_tm170": 0.08,
        },
        "MX125": {
            "isotope_ir192": 0.40,
            "isotope_se75": 0.23,
            "isotope_co60": 0.08,
            "isotope_yb169": 0.14,
            "isotope_tm170": 0.09,
        },
        "T200": {
            "isotope_ir192": 0.43,
            "isotope_se75": 0.27,
            "isotope_co60": 0.10,
            "isotope_yb169": 0.16,
            "isotope_tm170": 0.105,
        },
        "AA400": {
            "isotope_ir192": 0.46,
            "isotope_se75": 0.30,
            "isotope_co60": 0.13,
            "isotope_yb169": 0.18,
            "isotope_tm170": 0.12,
        },
        "HS800": {
            "isotope_ir192": 0.49,
            "isotope_se75": 0.34,
            "isotope_co60": 0.15,
            "isotope_yb169": 0.20,
            "isotope_tm170": 0.135,
        },
    }

    # Film model to R-Factor film key mapping
    FILM_TO_CHART_KEY = {
        "C2": "M100",
        "C3": "MX125",
        "C4": "T200",
        "C5": "AA400",
        "C6": "HS800",
    }

    # ISO 11699-1 relative film speed normalized to AA400 (C5 = 1.0).
    # Slower films (M100/MX125/T200) require more dose; faster (HS800) less.
    FILM_RELATIVE_SPEED = {
        "M100": 0.125,   # C2 (speed 2 / 16) -> 8x exposure vs AA400
        "MX125": 0.25,   # C3 (speed 4 / 16) -> 4x exposure vs AA400
        "T200": 0.50,    # C4 (speed 8 / 16) -> 2x exposure vs AA400
        "AA400": 1.00,   # C5 (speed 16 / 16) -> 1x baseline
        "HS800": 2.00,   # C6 (speed 32 / 16) -> 0.5x exposure vs AA400
    }

    # SCRATA slide rule constants (broad-beam effective HVL, mm steel)
    # Source: NDTCalc.com slide rule documentation
    HVL = {
        "isotope_ir192": 13.2,
        "isotope_se75": 10.3,
        "isotope_co60": 21.0,
        # Approximate broad-beam effective HVL for low-energy sources
        "isotope_yb169": 6.0,
        "isotope_tm170": 1.5,
    }

    # Gamma constants (R-m-Ci-h)
    GAMMA = {
        "isotope_ir192": 0.48,
        "isotope_se75": 0.20,
        "isotope_co60": 1.30,
        "isotope_yb169": 0.125,
        "isotope_tm170": 0.003,
    }

    TYPE_X_KV_VALUES = [80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 320, 350]

    # ISO 16371-1 / EN 14784-1 CR Phosphor Imaging Plate R-Factor table
    # (Reference detector dose in Roentgen for normalized SNR_N = 70 at native SR_b)
    CR_IPS_TABLE = {
        "cr_standard": {  # IPS-2 / IPS-3 Standard BaFBr:Eu plate (SR_b,ref = 100 µm)
            "ips_class": "IPS-2 / Standart IP",
            "srb_ref_um": 100.0,
            "r_factors": {
                "isotope_ir192": 0.18,
                "isotope_se75": 0.11,
                "isotope_co60": 0.07,
                "isotope_yb169": 0.06,
                "isotope_tm170": 0.04,
            },
        },
        "cr_highres": {  # IPS-1 High-Resolution HD-IP plate (SR_b,ref = 50 µm)
            "ips_class": "IPS-1 / HD Yüksek Çözünürlük IP",
            "srb_ref_um": 50.0,
            "r_factors": {
                "isotope_ir192": 0.26,
                "isotope_se75": 0.16,
                "isotope_co60": 0.10,
                "isotope_yb169": 0.09,
                "isotope_tm170": 0.06,
            },
        },
    }
    CR_IPS_TABLE["cr_hires"] = CR_IPS_TABLE["cr_highres"]

    # ASTM E2698 / E2736 DDA Flat Panel Detector Chart & Frame Integration Specs
    DDA_PANEL_TABLE = {
        "dda_si": {  # Amorphous Silicon (a-Si) + CsI:Tl Needle Scintillator
            "panel_class": "a-Si + CsI:Tl Düz Panel",
            "srb_ref_um": 130.0,
            "frame_target_dose_ugy": 12.0,
            "single_frame_snr_ref": 45.0,
            "target_gray_pct": 65.0,
            "r_factors": {
                "isotope_ir192": 0.045,
                "isotope_se75": 0.028,
                "isotope_co60": 0.025,
                "isotope_yb169": 0.016,
                "isotope_tm170": 0.012,
            },
        },
        "dda_se": {  # Amorphous Selenium (a-Se) Direct Conversion Photoconductor
            "panel_class": "a-Se Doğrudan Dönüşüm Panel",
            "srb_ref_um": 85.0,
            "frame_target_dose_ugy": 18.0,
            "single_frame_snr_ref": 42.0,
            "target_gray_pct": 65.0,
            "r_factors": {
                "isotope_ir192": 0.085,
                "isotope_se75": 0.042,
                "isotope_co60": 0.055,
                "isotope_yb169": 0.018,
                "isotope_tm170": 0.011,
            },
        },
        "dda_gdos": {  # Amorphous Silicon + Gd2O2S:Tb Scintillator
            "panel_class": "Gd₂O₂S:Tb Sintilatör DDA Panel",
            "srb_ref_um": 160.0,
            "frame_target_dose_ugy": 16.0,
            "single_frame_snr_ref": 40.0,
            "target_gray_pct": 65.0,
            "r_factors": {
                "isotope_ir192": 0.052,
                "isotope_se75": 0.032,
                "isotope_co60": 0.028,
                "isotope_yb169": 0.020,
                "isotope_tm170": 0.015,
            },
        },
    }

    def __init__(self, json_path=None):
        self.R_FACTOR_TABLE = {
            k: dict(v) for k, v in self.__class__.R_FACTOR_TABLE.items()
        }
        self.HVL = dict(self.__class__.HVL)
        self.GAMMA = dict(self.__class__.GAMMA)
        self.TYPE_X_CHART = {}
        if json_path is not None:
            if os.path.exists(json_path):
                self.load_from_json(json_path)

    def lookup_r_factor(self, film_key, source):
        if film_key not in self.R_FACTOR_TABLE:
            return None
        return self.R_FACTOR_TABLE[film_key].get(source, None)

    def lookup_digital_r_factor(self, detector_type, source):
        """Returns (r_factor_ref, spec_dict) for CR IP or DDA flat panel."""
        if detector_type in self.CR_IPS_TABLE:
            spec = self.CR_IPS_TABLE[detector_type]
            return spec["r_factors"].get(source, None), spec
        if detector_type in self.DDA_PANEL_TABLE:
            spec = self.DDA_PANEL_TABLE[detector_type]
            return spec["r_factors"].get(source, None), spec
        return None, None

    def calculate_exposure_time_digital_rfactor(
        self, sdd, w, source, activity, detector_type,
        target_snr=70.0, srb_factor=1.0, ref_factor=1.0,
    ):
        """
        Calculates digital CR / DDA exposure time (in minutes) using the
        calibrated CR IPS (ISO 16371-1) or DDA Panel (ASTM E2698) R-Factor
        table at reference SNR_N = 70, scaled by quantum statistics:
            T[min] = 60 * [R_dig * (SNR_target / 70)^2 * k_SRb * (SDD/1000)^2 * 2^(w_eq/HVL)] / (A * Gamma)
        """
        r_dig, spec = self.lookup_digital_r_factor(detector_type, source)
        if r_dig is None:
            return None
        hvl = self.HVL.get(source, 13.2)
        gamma = self.GAMMA.get(source, 0.48)
        if gamma <= 0 or activity <= 0:
            return None
        snr_val = max(10.0, float(target_snr if target_snr else 70.0))
        snr_corr = (snr_val / 70.0) ** 2
        sdd_m = float(sdd) / 1000.0
        w_eq = float(w) * float(ref_factor if ref_factor and ref_factor > 0 else 1.0)
        attenuation = 2.0 ** (w_eq / hvl)
        k_srb = max(0.25, min(4.0, float(srb_factor if srb_factor else 1.0)))

        t_hours = (r_dig * snr_corr * k_srb * (sdd_m ** 2) * attenuation) / (activity * gamma)
        return t_hours * 60.0

    def get_available_films(self):
        return list(self.R_FACTOR_TABLE.keys())

    def get_available_sources_for_film(self, film_key):
        if film_key not in self.R_FACTOR_TABLE:
            return []
        return list(self.R_FACTOR_TABLE[film_key].keys())

    def calculate_exposure_time_rfactor(self, sfd, w, source, activity, film_key,
                                        density=2.0, ref_factor=1.0, gradient=2.0):
        r_factor = self.lookup_r_factor(film_key, source)
        if r_factor is None:
            return None
        hvl = self.HVL.get(source, 13.2)
        gamma = self.GAMMA.get(source, 0.48)
        if gamma <= 0 or activity <= 0:
            return None

        # Effective dose factor: normalized so AA400 (C5) uses its exact R-factor,
        # while slower/faster films scale inversely with ISO 11699-1 film speed.
        rel_speed = self.FILM_RELATIVE_SPEED.get(film_key, 1.0)
        r_aa400 = self.lookup_r_factor("AA400", source)
        if r_aa400 is not None and rel_speed > 0 and film_key != "AA400":
            effective_r = r_aa400 / rel_speed
        else:
            effective_r = r_factor

        g_val = gradient if (gradient is not None and gradient > 0) else 2.0
        density_correction = 10 ** ((density - 2.0) / g_val)
        sfd_m = sfd / 1000.0
        w_eq = float(w) * float(ref_factor if ref_factor and ref_factor > 0 else 1.0)
        attenuation = 2 ** (w_eq / hvl)

        t_hours = (effective_r * density_correction * (sfd_m ** 2) * attenuation) / (activity * gamma)
        t_minutes = t_hours * 60.0
        return t_minutes

    def set_type_x_data(self, data):
        self.TYPE_X_CHART.clear()
        self.TYPE_X_CHART.update(data)

    def generate_type_x_chart(self, calculator, base_factor=3.0, film_speed=16.0):
        """
        Generates the Type X (X-ray) exposure chart for the physics model.
        base_factor: source exposure chart constant (mA·min/m² at 1 m, SNR 70).
        film_speed:  ISO 11699-1 film speed factor of the reference film
                     (default 16.0 == C5, matching the physics model default).
        """
        self.TYPE_X_CHART = {}
        for kv in self.TYPE_X_KV_VALUES:
            kv_data = {}
            for t_mm in range(5, 71, 5):
                mu = calculator.get_mu_from_kv(float(kv), "steel")
                attenuation = math.exp(min(700.0, mu * t_mm))
                sfd_m = 700.0 / 1000.0
                od_factor = 1.0
                exposure_mamin = base_factor * (sfd_m ** 2) * attenuation * od_factor / film_speed
                kv_data[t_mm] = exposure_mamin
            self.TYPE_X_CHART[kv] = kv_data

    def _interp_thickness(self, kv_data, thickness):
        """Log-linear interpolation of exposure (mA·min) along thickness (mm)."""
        if not kv_data:
            return None
        t_keys = sorted(kv_data.keys())
        t_val = float(thickness)
        if t_val <= t_keys[0]:
            if len(t_keys) >= 2 and kv_data[t_keys[0]] > 0 and kv_data[t_keys[1]] > 0:
                slope = math.log(kv_data[t_keys[1]] / kv_data[t_keys[0]]) / (t_keys[1] - t_keys[0])
                return kv_data[t_keys[0]] * math.exp(slope * (t_val - t_keys[0]))
            return kv_data[t_keys[0]]
        if t_val >= t_keys[-1]:
            if len(t_keys) >= 2 and kv_data[t_keys[-2]] > 0 and kv_data[t_keys[-1]] > 0:
                slope = math.log(kv_data[t_keys[-1]] / kv_data[t_keys[-2]]) / (t_keys[-1] - t_keys[-2])
                return kv_data[t_keys[-1]] * math.exp(slope * min(100.0, t_val - t_keys[-1]))
            return kv_data[t_keys[-1]]
        for i in range(len(t_keys) - 1):
            t1, t2 = t_keys[i], t_keys[i + 1]
            if t1 <= t_val <= t2:
                if abs(t_val - t1) < 1e-9:
                    return kv_data[t1]
                if abs(t_val - t2) < 1e-9:
                    return kv_data[t2]
                v1, v2 = kv_data[t1], kv_data[t2]
                if v1 > 0 and v2 > 0:
                    frac = (t_val - t1) / (t2 - t1)
                    return math.exp(math.log(v1) + frac * (math.log(v2) - math.log(v1)))
                return v1 + ((t_val - t1) / (t2 - t1)) * (v2 - v1)
        return kv_data[t_keys[0]]

    def get_type_x_exposure(self, kv, thickness, interpolate=True):
        if not self.TYPE_X_CHART:
            return None
        kv_f = float(kv)
        t_f = float(thickness)
        kv_keys = sorted(self.TYPE_X_CHART.keys())
        if not interpolate or len(kv_keys) == 1:
            nearest_kv = min(kv_keys, key=lambda k: abs(k - kv_f))
            kv_data = self.TYPE_X_CHART[nearest_kv]
            if not kv_data:
                return None
            nearest_t = min(kv_data.keys(), key=lambda t: abs(t - t_f))
            return kv_data[nearest_t]

        # Exact grid match fast path
        kv_int = int(round(kv_f))
        t_int = int(round(t_f))
        if abs(kv_f - kv_int) < 1e-9 and abs(t_f - t_int) < 1e-9:
            if kv_int in self.TYPE_X_CHART and t_int in self.TYPE_X_CHART[kv_int]:
                return self.TYPE_X_CHART[kv_int][t_int]

        if kv_f <= kv_keys[0]:
            return self._interp_thickness(self.TYPE_X_CHART[kv_keys[0]], t_f)
        if kv_f >= kv_keys[-1]:
            return self._interp_thickness(self.TYPE_X_CHART[kv_keys[-1]], t_f)

        for i in range(len(kv_keys) - 1):
            k1, k2 = kv_keys[i], kv_keys[i + 1]
            if k1 <= kv_f <= k2:
                if abs(kv_f - k1) < 1e-9:
                    return self._interp_thickness(self.TYPE_X_CHART[k1], t_f)
                if abs(kv_f - k2) < 1e-9:
                    return self._interp_thickness(self.TYPE_X_CHART[k2], t_f)
                e1 = self._interp_thickness(self.TYPE_X_CHART[k1], t_f)
                e2 = self._interp_thickness(self.TYPE_X_CHART[k2], t_f)
                if e1 is None or e2 is None:
                    return e1 if e1 is not None else e2
                if e1 > 0 and e2 > 0 and k1 > 0 and k2 > 0:
                    frac = (math.log(kv_f) - math.log(k1)) / (math.log(k2) - math.log(k1))
                    return math.exp(math.log(e1) + frac * (math.log(e2) - math.log(e1)))
                return e1 + ((kv_f - k1) / (k2 - k1)) * (e2 - e1)
        return None

    def save_to_csv(self, filepath="exposure_chart_dataset.csv"):
        rows = []

        rows.append("[R_FACTOR]")
        rows.append("film,source,density,r_factor")
        for film, sources in sorted(self.R_FACTOR_TABLE.items()):
            for source, r_val in sorted(sources.items()):
                rows.append(f"{film},{source},2.0,{r_val}")

        rows.append("")
        rows.append("[HVL]")
        rows.append("source,hvl_mm")
        for source, hvl in sorted(self.HVL.items()):
            rows.append(f"{source},{hvl}")

        rows.append("")
        rows.append("[GAMMA]")
        rows.append("source,gamma_value")
        for source, gamma in sorted(self.GAMMA.items()):
            rows.append(f"{source},{gamma}")

        rows.append("")
        rows.append("[TYPE_X]")
        rows.append("kv,thickness_mm,exposure_mamin")
        for kv in sorted(self.TYPE_X_CHART.keys()):
            for t_mm in sorted(self.TYPE_X_CHART[kv].keys()):
                rows.append(f"{kv},{t_mm},{self.TYPE_X_CHART[kv][t_mm]}")

        with open(filepath, "w", newline="") as f:
            f.write("\n".join(rows) + "\n")

    def load_from_csv(self, filepath="exposure_chart_dataset.csv"):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"CSV file not found: {filepath}")

        section = None
        headers = None
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    headers = None
                    continue
                if section == "R_FACTOR":
                    if headers is None:
                        headers = line
                        continue
                    parts = line.split(",")
                    if len(parts) >= 4:
                        film, source, density, r_val = parts[0], parts[1], parts[2], parts[3]
                        try:
                            r_factor = float(r_val)
                            if film not in self.R_FACTOR_TABLE:
                                self.R_FACTOR_TABLE[film] = {}
                            self.R_FACTOR_TABLE[film][source] = r_factor
                        except ValueError:
                            continue
                elif section == "HVL":
                    if headers is None:
                        headers = line
                        continue
                    parts = line.split(",")
                    if len(parts) >= 2:
                        self.HVL[parts[0]] = float(parts[1])
                elif section == "GAMMA":
                    if headers is None:
                        headers = line
                        continue
                    parts = line.split(",")
                    if len(parts) >= 2:
                        self.GAMMA[parts[0]] = float(parts[1])
                elif section == "TYPE_X":
                    if headers is None:
                        headers = line
                        continue
                    parts = line.split(",")
                    if len(parts) >= 3:
                        kv = int(parts[0])
                        t_mm = int(float(parts[1]))
                        exposure = float(parts[2])
                        if kv not in self.TYPE_X_CHART:
                            self.TYPE_X_CHART[kv] = {}
                        self.TYPE_X_CHART[kv][t_mm] = exposure

    def save_to_json(self, filepath="exposure_chart_dataset.json"):
        data = {
            "r_factor_table": self.R_FACTOR_TABLE,
            "hvl": self.HVL,
            "gamma": self.GAMMA,
            "type_x_chart": {str(k): v for k, v in self.TYPE_X_CHART.items()},
            "film_to_chart_key": self.FILM_TO_CHART_KEY,
        }
        # Convert integer keys in type_x_chart values back to strings for JSON
        type_x_serialized = {}
        for kv, kv_data in self.TYPE_X_CHART.items():
            type_x_serialized[str(kv)] = {str(t): v for t, v in kv_data.items()}
        data["type_x_chart"] = type_x_serialized

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, filepath="exposure_chart_dataset.json"):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"JSON file not found: {filepath}")

        with open(filepath, "r") as f:
            data = json.load(f)

        if "r_factor_table" in data:
            self.R_FACTOR_TABLE.clear()
            for film, sources in data["r_factor_table"].items():
                self.R_FACTOR_TABLE[film] = dict(sources)

        if "hvl" in data:
            self.HVL.clear()
            self.HVL.update({str(k): float(v) for k, v in data["hvl"].items()})

        if "gamma" in data:
            self.GAMMA.clear()
            self.GAMMA.update({str(k): float(v) for k, v in data["gamma"].items()})

        if "type_x_chart" in data:
            self.TYPE_X_CHART.clear()
            for kv_str, kv_data in data["type_x_chart"].items():
                kv = int(kv_str)
                self.TYPE_X_CHART[kv] = {int(t_str): float(v) for t_str, v in kv_data.items()}

        if "film_to_chart_key" in data:
            self.FILM_TO_CHART_KEY.clear()
            self.FILM_TO_CHART_KEY.update(data["film_to_chart_key"])
