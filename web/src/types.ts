export type Tech = "analog" | "digital";
export type TestingClass = "class_a" | "class_b";
export type Geometry = "dwsi" | "swsi" | "dwdi_elliptic" | "dwdi_super";
export type Standard = "iso" | "asme";
export type IqiType = "wire" | "step_hole";

export interface FormState {
  od: number;
  t: number;
  cap: number;
  weld_width: number;
  d: number;
  sfd: number;
  output_val: number;
  base_e: number;
  detector_type: string;
  film_class_used: string;
  chart_source: string;
  tech: Tech;
  material: string;
  source: string;
  testing_class: TestingClass;
  geometry: Geometry;
  standard: Standard;
  iqi_type: IqiType;
  film_side: boolean;
  snr_location: "weld" | "adjacent";
  std_figure: string | null;
  detector_curved: boolean;
  panel_width: number;
  panel_height: number;
  panel_overlap: number;
  app_exposures: number;
  film_width: number;
  film_height: number;
  f_source: number | null;
  b_object: number | null;
  bed: number;
  bgap: number;
  app_kv: number;
  app_activity: number;
  app_time: number;
  app_quality: number;
  app_overlap: number;
  app_overlap_warn: number;
  app_srb: number;
  app_wire: number;
  app_duplex: number;
  barrier_limit_usvh: number;
  collimator_hvl: number;
  gamma_convention: "r" | "msv";
  asme_sensitivity: string;
  base_multiplier: number;
  base_multiplier_raw: number;
  user_geometry?: Geometry | null;
}

export interface Lvl3Settings {
  sfd_comp: boolean;
  voltage_override: boolean;
  isotope_flex: boolean;
  source_flex: boolean;
  central_proj_reduction: boolean;
  dw_reduction: boolean;
  approval_note: string;
}

export const DEFAULT_LVL3: Lvl3Settings = {
  sfd_comp: false,
  voltage_override: false,
  isotope_flex: false,
  source_flex: false,
  central_proj_reduction: false,
  dw_reduction: false,
  approval_note: "",
};

export const DEFAULT_FORM: FormState = {
  od: 114.3,
  t: 6.02,
  cap: 3.0,
  weld_width: 8.0,
  d: 2.0,
  sfd: 600.0,
  output_val: 5.0,
  base_e: 3.0,
  detector_type: "cr_standard",
  film_class_used: "C5",
  chart_source: "model",
  tech: "digital",
  material: "steel",
  source: "x_ray",
  testing_class: "class_b",
  geometry: "dwsi",
  standard: "iso",
  iqi_type: "wire",
  film_side: false,
  snr_location: "weld",
  std_figure: null,
  detector_curved: false,
  panel_width: 200.0,
  panel_height: 200.0,
  panel_overlap: 10.0,
  app_exposures: 6,
  film_width: 100.0,
  film_height: 400.0,
  f_source: null,
  b_object: null,
  bed: 0.0,
  bgap: 5.0,
  app_kv: 120.0,
  app_activity: 40.0,
  app_time: 120.0,
  app_quality: 140.0,
  app_overlap: 10.0,
  app_overlap_warn: 10.0,
  app_srb: 80.0,
  app_wire: 10,
  app_duplex: 6,
  barrier_limit_usvh: 20.0,
  collimator_hvl: 0.0,
  gamma_convention: "r",
  asme_sensitivity: "2-2T",
  base_multiplier: 1.0,
  base_multiplier_raw: 1.0,
  user_geometry: null,
};

export interface EngineResult {
  calculated: Record<string, unknown>;
  warnings: string[];
  display: Record<string, string>;
  values: Record<string, any>;
  form: FormState;
}

export interface ComplianceCheck {
  name: string;
  status: boolean;
  details: string;
}

export interface ComplianceResult {
  is_compliant: boolean;
  checks: ComplianceCheck[];
  activity_warning?: string | null;
  activity_diff?: number;
}

export interface Schedule {
  0: number;
  1: string;
}

export interface PipeEntry {
  od: number;
  schedules: [number, string][];
}

export interface PipeData {
  b36_10: Record<string, PipeEntry>;
  b36_19: Record<string, PipeEntry>;
}

export interface DefectInput {
  standard: "api1104" | "iso5817" | "b31_3" | "viii";
  type: string;
  length: number;
  width: number;
  accumulated: number;
  level?: string;
  service?: string;
  mode?: string;
}

export interface DefectResult {
  status: boolean;
  result: string;
  details: string;
  approx?: boolean;
}
