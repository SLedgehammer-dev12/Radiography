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
        },
        "MX125": {
            "isotope_ir192": 0.40,
            "isotope_se75": 0.23,
        },
        "T200": {
            "isotope_ir192": 0.43,
            "isotope_se75": 0.27,
            "isotope_co60": 0.10,
        },
        "AA400": {
            "isotope_ir192": 0.46,
            "isotope_se75": 0.30,
            "isotope_co60": 0.13,
        },
        "HS800": {
            "isotope_ir192": 0.49,
            "isotope_se75": 0.34,
            "isotope_co60": 0.15,
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

    # SCRATA slide rule constants (broad-beam effective HVL, mm steel)
    # Source: NDTCalc.com slide rule documentation
    HVL = {
        "isotope_ir192": 13.2,
        "isotope_se75": 10.3,
        "isotope_co60": 21.0,
    }

    # Gamma constants (R-m-Ci-h)
    GAMMA = {
        "isotope_ir192": 0.48,
        "isotope_se75": 0.20,
        "isotope_co60": 1.30,
    }

    TYPE_X_KV_VALUES = [80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 320, 350]

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

    def get_available_films(self):
        return list(self.R_FACTOR_TABLE.keys())

    def get_available_sources_for_film(self, film_key):
        if film_key not in self.R_FACTOR_TABLE:
            return []
        return list(self.R_FACTOR_TABLE[film_key].keys())

    def calculate_exposure_time_rfactor(self, sfd, w, source, activity, film_key, density=2.0):
        r_factor = self.lookup_r_factor(film_key, source)
        if r_factor is None:
            return None
        hvl = self.HVL.get(source, 13.2)
        gamma = self.GAMMA.get(source, 0.48)
        if gamma <= 0:
            return None

        density_correction = 10 ** ((density - 2.0) / 2.0)
        sfd_m = sfd / 1000.0
        attenuation = 2 ** (w / hvl)

        t_hours = (r_factor * density_correction * (sfd_m ** 2) * attenuation) / (activity * gamma)
        t_minutes = t_hours * 60.0
        return t_minutes

    def set_type_x_data(self, data):
        self.TYPE_X_CHART.clear()
        self.TYPE_X_CHART.update(data)

    def generate_type_x_chart(self, calculator):
        self.TYPE_X_CHART = {}
        for kv in self.TYPE_X_KV_VALUES:
            kv_data = {}
            for t_mm in range(5, 71, 5):
                mu = calculator.get_mu_from_kv(float(kv), "steel")
                attenuation = math.exp(min(700.0, mu * t_mm))
                sfd_m = 700.0 / 1000.0
                base_factor = 3.0
                film_speed = 16.0
                od_factor = 1.0
                exposure_mamin = base_factor * (sfd_m ** 2) * attenuation * od_factor / film_speed
                kv_data[t_mm] = exposure_mamin
            self.TYPE_X_CHART[kv] = kv_data

    def get_type_x_exposure(self, kv, thickness):
        if not self.TYPE_X_CHART:
            return None
        kv = int(kv)
        nearest_kv = min(self.TYPE_X_CHART.keys(), key=lambda k: abs(k - kv))
        kv_data = self.TYPE_X_CHART[nearest_kv]
        if not kv_data:
            return None
        nearest_t = min(kv_data.keys(), key=lambda t: abs(t - thickness))
        return kv_data[nearest_t]

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
