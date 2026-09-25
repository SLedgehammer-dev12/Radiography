import { DEFAULT_FORM, type FormState, type PipeData } from "../types";

const MATERIALS = ["steel", "aluminum", "titanium", "copper_nickel"];
const SOURCES = [
  "x_ray",
  "isotope_ir192",
  "isotope_se75",
  "isotope_co60",
  "isotope_yb169",
  "isotope_tm170",
];
const CLASSES = ["class_b", "class_a"];
const GEOMETRIES = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"];
const STANDARDS = ["iso", "asme"];
const DETECTORS = ["cr_standard", "cr_hires", "dda_si", "dda_se", "dda_gdos"];
const CHARTS = ["model", "AA400", "MX125", "T200", "HS800", "M100", "type_x"];
const COLLIMATORS = [0, 1, 2, 4];
const FILM_SIZES: Record<string, [number, number]> = {
  "80x300": [80, 300],
  "100x400": [100, 400],
  "300x400": [300, 400],
  "100x500": [100, 500],
};

export const NAMED_PRESETS: Record<string, Partial<FormState>> = {
  "4 inç SCH40 DWDI X-Ray Atölye": {
    source: "x_ray",
    geometry: "dwdi_elliptic",
    od: 114.3,
    output_val: 5.0,
    app_kv: 200.0,
  },
  "16 inç DWSI Ir-192 Saha": {
    source: "isotope_ir192",
    geometry: "dwsi",
    od: 406.4,
    output_val: 40.0,
    app_activity: 40.0,
  },
  "2 inç DDA Dijital RT": {
    tech: "digital",
    detector_curved: false,
    geometry: "dwsi",
    od: 60.3,
  },
  "ASME VIII 25 mm SWSI Co-60": {
    source: "isotope_co60",
    geometry: "swsi",
    standard: "asme",
    od: 500.0,
    t: 25.0,
    output_val: 20.0,
    app_activity: 20.0,
  },
};

export interface ReportInfo {
  [key: string]: string;
}

export interface PresetPayload {
  type: string;
  version: string;
  state: Record<string, unknown>;
  calculated?: Record<string, unknown>;
  warnings?: string;
}

const indexOf = (list: (string | number)[], value: unknown): number => {
  const index = list.findIndex((item) => String(item) === String(value));
  return index >= 0 ? index : 0;
};

const asBool = (value: unknown, fallback = false): boolean => {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    return ["1", "true", "yes", "checked"].includes(value.toLowerCase());
  }
  return fallback;
};

const asNumber = (value: unknown, fallback: number): number => {
  const parsed = Number(String(value ?? "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : fallback;
};

/** Converts the web form to the desktop preset/project state schema. */
export function formToDesktopState(
  form: FormState,
  reportInfo: ReportInfo,
  pipeData: PipeData | null,
  language: string,
): Record<string, unknown> {
  const pipeKeys = pipeData ? Object.keys(pipeData.b36_10) : [];
  let odIndex = 0;
  let best = Infinity;
  pipeKeys.forEach((key, index) => {
    const delta = Math.abs((pipeData?.b36_10[key].od ?? 0) - form.od);
    if (delta < best) {
      best = delta;
      odIndex = index;
    }
  });
  const schedules = pipeData?.b36_10[pipeKeys[odIndex]]?.schedules ?? [];
  let tIndex = 0;
  schedules.forEach(([wall], index) => {
    if (Math.abs(wall - form.t) < Math.abs((schedules[tIndex]?.[0] ?? 0) - form.t)) {
      tIndex = index;
    }
  });

  const filmKey =
    Object.entries(FILM_SIZES).find(
      ([, [width, height]]) =>
        Math.abs(width - form.film_width) < 0.01 &&
        Math.abs(height - form.film_height) < 0.01,
    )?.[0] ?? "custom";

  const state: Record<string, unknown> = {
    language,
    rad_analog: form.tech === "analog",
    rad_digital: form.tech === "digital",
    rad_detector_flat: !form.detector_curved,
    rad_detector_curved: form.detector_curved,
    chk_source_side_iqi: !form.film_side,
    cmb_material: indexOf(MATERIALS, form.material),
    cmb_source: indexOf(SOURCES, form.source),
    cmb_class: indexOf(CLASSES, form.testing_class),
    cmb_od: odIndex,
    cmb_t: tIndex,
    cmb_geometry: indexOf(GEOMETRIES, form.geometry),
    cmb_film_class_used: indexOf(["C1", "C2", "C3", "C4", "C5", "C6"], form.film_class_used),
    cmb_detector_type: indexOf(DETECTORS, form.detector_type),
    cmb_chart_source: indexOf(CHARTS, form.chart_source),
    cmb_standard: indexOf(STANDARDS, form.standard),
    cmb_collimator: indexOf(COLLIMATORS, form.collimator_hvl),
    cmb_iqi_type: indexOf(["wire", "step_hole"], form.iqi_type),
    cmb_snr_location: indexOf(["weld", "adjacent"], form.snr_location),
    cmb_app_duplex: form.app_duplex - 1,
    cmb_app_wire: form.app_wire - 1,
    cmb_activity_unit: 0,
    cmb_std_figure: form.std_figure ?? "",
    cmb_film_size: indexOf(["80x300", "100x400", "300x400", "100x500", "custom"], filmKey),
    txt_custom_od: String(form.od),
    txt_custom_t: String(form.t),
    txt_cap: String(form.cap),
    txt_weld_width: String(form.weld_width),
    txt_d: String(form.d),
    txt_app_sfd: String(form.sfd),
    txt_output: String(form.output_val),
    txt_app_activity: String(form.app_activity),
    txt_base_e: String(form.base_e),
    txt_barrier_limit: String(form.barrier_limit_usvh),
    txt_app_kv: String(form.app_kv),
    txt_app_time: String(form.app_time),
    txt_app_overlap: String(form.app_overlap),
    txt_app_srb: String(form.app_srb),
    txt_app_quality: String(form.app_quality),
    txt_panel_width: String(form.panel_width),
    txt_panel_height: String(form.panel_height),
    txt_panel_overlap: String(form.panel_overlap),
    txt_app_exposures: String(form.app_exposures),
    txt_base_multiplier: String(form.base_multiplier),
    txt_f_source: form.f_source === null ? "" : String(form.f_source),
    txt_b_object: form.b_object === null ? "" : String(form.b_object),
    txt_film_width: String(form.film_width),
    txt_film_height: String(form.film_height),
    txt_bed: String(form.bed),
    txt_bgap: String(form.bgap),
  };
  for (const [key, value] of Object.entries(reportInfo)) {
    state[`txt_${key}`] = value;
  }
  return state;
}

/** Converts a desktop preset/project state dict back into a web form. */
export function desktopStateToForm(
  state: Record<string, unknown>,
  pipeData: PipeData | null,
): { form: Partial<FormState>; reportInfo: ReportInfo } {
  const form: Partial<FormState> = {};
  const reportInfo: ReportInfo = {};

  const digital = asBool(state.rad_digital, true);
  if ("rad_analog" in state || "rad_digital" in state) {
    form.tech = digital ? "digital" : "analog";
  }
  if ("rad_detector_curved" in state || "rad_detector_flat" in state) {
    form.detector_curved = asBool(state.rad_detector_curved, false);
  }
  if ("chk_source_side_iqi" in state) {
    form.film_side = !asBool(state.chk_source_side_iqi, true);
  }

  const combo = (key: string): unknown => state[key];
  if (combo("cmb_material") !== undefined) {
    form.material = MATERIALS[asNumber(combo("cmb_material"), 0)] ?? "steel";
  }
  if (combo("cmb_source") !== undefined) {
    form.source = SOURCES[asNumber(combo("cmb_source"), 0)] ?? "x_ray";
  }
  if (combo("cmb_class") !== undefined) {
    form.testing_class = (CLASSES[asNumber(combo("cmb_class"), 0)] ?? "class_b") as FormState["testing_class"];
  }
  if (combo("cmb_geometry") !== undefined) {
    form.geometry = (GEOMETRIES[asNumber(combo("cmb_geometry"), 0)] ?? "dwsi") as FormState["geometry"];
  }
  if (combo("cmb_standard") !== undefined) {
    form.standard = (STANDARDS[asNumber(combo("cmb_standard"), 0)] ?? "iso") as FormState["standard"];
  }
  if (combo("cmb_film_class_used") !== undefined) {
    form.film_class_used =
      ["C1", "C2", "C3", "C4", "C5", "C6"][asNumber(combo("cmb_film_class_used"), 4)] ?? "C5";
  }
  if (combo("cmb_detector_type") !== undefined) {
    form.detector_type = DETECTORS[asNumber(combo("cmb_detector_type"), 0)] ?? "cr_standard";
  }
  if (combo("cmb_chart_source") !== undefined) {
    form.chart_source = CHARTS[asNumber(combo("cmb_chart_source"), 0)] ?? "model";
  }
  if (combo("cmb_collimator") !== undefined) {
    form.collimator_hvl = COLLIMATORS[asNumber(combo("cmb_collimator"), 0)] ?? 0;
  }
  if (combo("cmb_iqi_type") !== undefined) {
    form.iqi_type = (["wire", "step_hole"][asNumber(combo("cmb_iqi_type"), 0)] ?? "wire") as FormState["iqi_type"];
  }
  if (combo("cmb_snr_location") !== undefined) {
    form.snr_location = (["weld", "adjacent"][asNumber(combo("cmb_snr_location"), 0)] ?? "weld") as FormState["snr_location"];
  }
  if (combo("cmb_app_duplex") !== undefined) {
    form.app_duplex = asNumber(combo("cmb_app_duplex"), 5) + 1;
  }
  if (combo("cmb_app_wire") !== undefined) {
    form.app_wire = asNumber(combo("cmb_app_wire"), 9) + 1;
  }
  if (typeof combo("cmb_std_figure") === "string" && combo("cmb_std_figure")) {
    form.std_figure = String(combo("cmb_std_figure"));
  }
  if (combo("cmb_film_size") !== undefined) {
    const key = ["80x300", "100x400", "300x400", "100x500", "custom"][
      asNumber(combo("cmb_film_size"), 1)
    ];
    const preset = FILM_SIZES[key ?? "100x400"];
    if (preset) {
      form.film_width = preset[0];
      form.film_height = preset[1];
    }
  }

  if (pipeData) {
    const pipeKeys = Object.keys(pipeData.b36_10);
    const odIndex = asNumber(combo("cmb_od"), -1);
    if (odIndex >= 0 && pipeKeys[odIndex]) {
      form.od = pipeData.b36_10[pipeKeys[odIndex]].od;
      const schedules = pipeData.b36_10[pipeKeys[odIndex]].schedules;
      const tIndex = asNumber(combo("cmb_t"), 0);
      if (schedules[tIndex]) form.t = schedules[tIndex][0];
    }
  }

  const num = (key: string, target: keyof FormState) => {
    if (state[key] !== undefined && state[key] !== "") {
      (form as Record<string, unknown>)[target] = asNumber(state[key], DEFAULT_FORM[target] as number);
    }
  };
  num("txt_custom_od", "od");
  num("txt_custom_t", "t");
  num("txt_cap", "cap");
  num("txt_weld_width", "weld_width");
  num("txt_d", "d");
  num("txt_app_sfd", "sfd");
  num("txt_app_kv", "app_kv");
  num("txt_app_time", "app_time");
  num("txt_app_overlap", "app_overlap");
  num("txt_app_srb", "app_srb");
  num("txt_app_quality", "app_quality");
  num("txt_panel_width", "panel_width");
  num("txt_panel_height", "panel_height");
  num("txt_panel_overlap", "panel_overlap");
  num("txt_app_exposures", "app_exposures");
  num("txt_base_multiplier", "base_multiplier");
  num("txt_base_multiplier", "base_multiplier_raw");
  num("txt_film_width", "film_width");
  num("txt_film_height", "film_height");
  num("txt_bed", "bed");
  num("txt_bgap", "bgap");

  if (state.txt_base_e !== undefined && state.txt_base_e !== "") {
    form.base_e = asNumber(state.txt_base_e, DEFAULT_FORM.base_e);
  }
  if (state.txt_barrier_limit !== undefined && state.txt_barrier_limit !== "") {
    form.barrier_limit_usvh = asNumber(state.txt_barrier_limit, 20);
  }
  if (state.txt_f_source !== undefined) {
    form.f_source = state.txt_f_source === "" ? null : asNumber(state.txt_f_source, 0) || null;
  }
  if (state.txt_b_object !== undefined) {
    form.b_object = state.txt_b_object === "" ? null : asNumber(state.txt_b_object, 0) || null;
  }

  const unitGbq = asNumber(combo("cmb_activity_unit"), 0) === 1;
  if (state.txt_app_activity !== undefined && state.txt_app_activity !== "") {
    const raw = asNumber(state.txt_app_activity, 40);
    const activity = unitGbq ? raw / 37 : raw;
    form.app_activity = activity;
    if (form.source && form.source !== "x_ray") form.output_val = activity;
  }
  if (state.txt_output !== undefined && state.txt_output !== "" && form.source === "x_ray") {
    form.output_val = asNumber(state.txt_output, 5);
  }

  for (const key of [
    "report_no",
    "report_rev",
    "project",
    "welder_id",
    "joint_id",
    "wps_pqr",
    "procedure_no",
    "device_serial",
    "calibration_date",
    "personnel",
    "lvl2_name",
    "lvl2_cert",
    "lvl3_name",
    "lvl3_cert",
  ]) {
    const value = state[`txt_${key}`];
    if (value !== undefined) reportInfo[key] = String(value);
  }

  return { form, reportInfo };
}

export function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function downloadCsv(filename: string, rows: [string, unknown][]) {
  const escape = (value: unknown) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = rows.map(([key, value]) => `${escape(key)},${escape(value)}`).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function parseCsv(text: string): Record<string, string> {
  const state: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const match = line.match(/^("(?:[^"]|"")*"|[^,]*),("(?:[^"]|"")*"|[^,]*)$/);
    if (!match) continue;
    const unquote = (value: string) =>
      value.startsWith('"') ? value.slice(1, -1).replace(/""/g, '"') : value;
    const key = unquote(match[1]);
    if (key && key !== "field") state[key] = unquote(match[2]);
  }
  return state;
}
