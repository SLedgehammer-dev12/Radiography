import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  CheckField,
  DurationSliderField,
  Group,
  LengthField,
  LengthSliderField,
  NumberField,
  OutputRow,
  PageScrollbar,
  RadioGroup,
  SelectField,
  SliderField,
  UnitContext,
} from "./components";
import {
  AnnexAChartSvg,
  DefectStripSvg,
  StandardFigureSvg,
  WeldSetupSvg,
} from "./components/SketchView";
import { WeldSetup3D } from "./components/WeldSetup3D";
import { makeTranslator } from "./i18n";
import { pyClient } from "./pyodide/client";
import {
  DEFAULT_BASE_E_BY_SOURCE,
  NAMED_PRESETS,
  desktopStateToForm,
  downloadCsv,
  downloadJson,
  formToDesktopState,
  getActiveChartKeys,
  parseCsv,
} from "./state/presets";
import { useEngine } from "./state/useEngine";
import {
  DEFAULT_FORM,
  DEFAULT_LVL3,
  type DefectInput,
  type DefectResult,
  type FormState,
  type Lvl3Settings,
  type PipeData,
} from "./types";
import "./App.css";

const DEFECT_TYPES = [
  "defect_ip",
  "defect_if",
  "defect_ic",
  "defect_porosity",
  "defect_crack",
  "defect_slag",
  "defect_undercut",
  "defect_burn_through",
];
const DEFECT_STANDARDS = [
  { value: "api1104", labelKey: "defect_std_api1104" },
  { value: "iso5817", labelKey: "defect_std_iso5817" },
  { value: "b31_3", labelKey: "defect_std_b31_3" },
  { value: "viii", labelKey: "defect_std_viii" },
];

const MATERIALS = ["steel", "aluminum", "titanium", "copper_nickel"];
const SOURCES = [
  "x_ray",
  "isotope_ir192",
  "isotope_se75",
  "isotope_co60",
  "isotope_yb169",
  "isotope_tm170",
];
const GEOMETRIES = ["dwsi", "swsi", "dwdi_elliptic", "dwdi_super"];
const DETECTOR_KEYS = ["cr_standard", "cr_highres", "dda_si", "dda_se", "dda_gdos"];
const DETECTOR_TKEYS = [
  "detector_cr_std",
  "detector_cr_hires",
  "detector_dda_si",
  "detector_dda_se",
  "detector_dda_gdos",
];
const ANALOG_CHART_OPTIONS: { value: string; labelKey?: string; label?: string }[] = [
  { value: "model", labelKey: "chart_model" },
  { value: "AA400", label: "AA400 (C5)" },
  { value: "MX125", label: "MX125 (C3)" },
  { value: "T200", label: "T200 (C4)" },
  { value: "HS800", label: "HS800 (C6)" },
  { value: "M100", label: "M100 (C2)" },
  { value: "type_x", labelKey: "chart_type_x" },
];
const DIGITAL_CR_CHART_OPTIONS: { value: string; labelKey?: string; label?: string }[] = [
  { value: "model", labelKey: "chart_digital_model" },
  { value: "cr_ips_chart", labelKey: "chart_cr_ips" },
  { value: "digital_xray_chart", labelKey: "chart_digital_xray" },
];
const DIGITAL_DDA_CHART_OPTIONS: { value: string; labelKey?: string; label?: string }[] = [
  { value: "model", labelKey: "chart_digital_model" },
  { value: "dda_frame_method", labelKey: "chart_dda_frame" },
  { value: "dda_panel_chart", labelKey: "chart_dda_panel" },
  { value: "digital_xray_chart", labelKey: "chart_digital_xray" },
];
const OUTPUT_KEYS = [
  "w_nom",
  "w_eff",
  "u_max",
  "f_min",
  "f_min_asme",
  "sfd_min",
  "ug",
  "req_exposures",
  "exposures_panel",
  "exposures_applied",
  "exposures_check",
  "single_wire_iqi",
  "duplex_iqi",
  "asme_iqi",
  "quality_target",
  "calc_time",
  "detector_quality",
  "barrier_distance",
  "filter_recommendation",
];
const REPORT_FIELDS: [string, string][] = [
  ["report_no", "report_no"],
  ["report_rev", "report_rev"],
  ["project", "project"],
  ["welder_id", "welder_id"],
  ["joint_id", "joint_id"],
  ["wps_pqr", "wps_pqr"],
  ["procedure_no", "procedure_no"],
  ["device_serial", "device_serial"],
  ["calibration_date", "calibration_date"],
  ["personnel", "personnel"],
  ["lvl2_name", "lvl2_name"],
  ["lvl2_cert", "lvl2_cert"],
  ["lvl3_name", "lvl3_name"],
  ["lvl3_cert", "lvl3_cert"],
];
const FILM_PRESETS: Record<string, [number, number]> = {
  "80x300": [80, 300],
  "100x400": [100, 400],
  "300x400": [300, 400],
  "100x500": [100, 500],
};
const STORAGE_KEY = "radiography_web_state_v1";

interface PersistedState {
  form?: FormState;
  lvl3?: Lvl3Settings;
  lang?: string;
  theme?: "dark" | "light";
  reportInfo?: Record<string, string>;
}

function loadPersisted(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as PersistedState;
    if (parsed.form) {
      if (parsed.form.detector_type === "cr_hires") {
        parsed.form.detector_type = "cr_highres";
      }
      if (
        parsed.form.source &&
        parsed.form.source !== "x_ray" &&
        parsed.form.base_e === 3.0
      ) {
        parsed.form.base_e =
          DEFAULT_BASE_E_BY_SOURCE[parsed.form.source] ?? 30.0;
      }
      if (parsed.form.tech === "analog") {
        parsed.form.b_object = null;
        parsed.form.f_source = null;
      } else if (
        parsed.form.b_object != null &&
        parsed.form.b_object <= (parsed.form.t ?? 6.02) + (parsed.form.cap ?? 0)
      ) {
        parsed.form.b_object = null;
      }
      if (
        parsed.form.geometry === "swsi" &&
        parsed.form.std_figure &&
        ["fig2", "fig2a", "fig2b"].includes(parsed.form.std_figure)
      ) {
        parsed.form.std_figure = null;
      }
      const validCharts = getActiveChartKeys(
        parsed.form.tech ?? "analog",
        parsed.form.detector_type ?? "cr_standard",
      );
      if (parsed.form.chart_source && !validCharts.includes(parsed.form.chart_source)) {
        parsed.form.chart_source = "model";
      }
    }
    return parsed;
  } catch {
    return {};
  }
}

export default function App() {
  const persisted = useMemo(loadPersisted, []);
  const [form, setForm] = useState<FormState>({
    ...DEFAULT_FORM,
    ...(persisted.form ?? {}),
  });
  const [lvl3, setLvl3] = useState<Lvl3Settings>(persisted.lvl3 ?? DEFAULT_LVL3);
  const [lang, setLang] = useState<string>(persisted.lang ?? "tr");
  const [theme, setTheme] = useState<"dark" | "light">(persisted.theme ?? "dark");
  const [unitInch, setUnitInch] = useState(false);
  const [pipeStd, setPipeStd] = useState<"b36_10" | "b36_19">("b36_10");
  const [activityUnit, setActivityUnit] = useState<"Ci" | "GBq">("Ci");
  const [strings, setStrings] = useState<Record<string, string>>({});
  const [pipeData, setPipeData] = useState<PipeData | null>(null);
  const [figures, setFigures] = useState<string[]>([]);
  const [iqiOptions, setIqiOptions] = useState<{
    wire: Record<string, number>;
    step_hole: Record<string, number>;
  } | null>(null);
  const [reportInfo, setReportInfo] = useState<Record<string, string>>(
    persisted.reportInfo ?? {},
  );
  const [showLvl3, setShowLvl3] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [sketchTab, setSketchTab] = useState<
    "3d" | "dynamic" | "figure" | "annex_a"
  >("3d");
  const [filmSizeMode, setFilmSizeMode] = useState<string>("100x400");
  const [defect, setDefect] = useState<DefectInput>({
    standard: "api1104",
    type: "defect_porosity",
    length: 10,
    width: 1.5,
    accumulated: 15,
    level: "C",
    service: "normal",
    mode: "UW-51",
  });
  const [defectResult, setDefectResult] = useState<DefectResult | null>(null);
  const [defectActive, setDefectActive] = useState(false);
  const [showDecay, setShowDecay] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const presetInput = useRef<HTMLInputElement>(null);
  const projectInput = useRef<HTMLInputElement>(null);
  const csvInput = useRef<HTMLInputElement>(null);

  const { result, compliance, error, busy, ready } = useEngine(form, lvl3, lang);
  const t = useMemo(() => makeTranslator(strings), [strings]);

  const patch = useCallback(
    <K extends keyof FormState>(key: K, value: FormState[K]) =>
      setForm((previous) => ({ ...previous, [key]: value })),
    [],
  );

  useEffect(() => {
    return pyClient.onStatus((stage, detail) => {
      if (stage === "error") setBootError(detail ?? "Boot error");
    });
  }, []);

  useEffect(() => {
    if (!ready) return;
    pyClient
      .request<{ strings: Record<string, string> }>("translations", { lang })
      .then((data) => setStrings(data.strings))
      .catch((caught) => setBootError(String(caught)));
    pyClient
      .request<PipeData>("pipe_data")
      .then(setPipeData)
      .catch(() => undefined);
    pyClient
      .request<{
        wire: Record<string, number>;
        step_hole: Record<string, number>;
      }>("iqi_options")
      .then(setIqiOptions)
      .catch(() => undefined);
  }, [ready, lang]);

  useEffect(() => {
    if (!ready) return;
    pyClient
      .request<{ figures: string[] }>("standard_figures", {
        tech: form.tech,
        geometry: form.geometry,
        detector_curved: form.detector_curved,
      })
      .then((data) => {
        setFigures(data.figures);
        setForm((previous) => {
          if (previous.std_figure && data.figures.includes(previous.std_figure)) {
            return previous;
          }
          return { ...previous, std_figure: data.figures[0] ?? null };
        });
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, form.tech, form.geometry, form.detector_curved]);

  useEffect(() => {
    const handle = setTimeout(() => {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ form, lvl3, lang, theme, reportInfo }),
        );
      } catch {
        /* storage may be unavailable */
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [form, lvl3, lang, theme, reportInfo]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Keeps the film-size selector in sync when dimensions change externally
  // (preset/project import, unit conversion).
  useEffect(() => {
    const match = Object.entries(FILM_PRESETS).find(
      ([, [width, height]]) =>
        Math.abs(width - form.film_width) < 0.01 &&
        Math.abs(height - form.film_height) < 0.01,
    );
    if (match) setFilmSizeMode(match[0]);
  }, [form.film_width, form.film_height]);

  // Reactive defect evaluation once defect module is activated by user
  useEffect(() => {
    if (!ready || !defectActive) return;
    const timer = setTimeout(() => {
      pyClient
        .request<DefectResult>("defect", { form, defect, lang })
        .then(setDefectResult)
        .catch(() => undefined);
    }, 150);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, defectActive, form.t, defect, lang]);

  const digital = form.tech === "digital";
  const analog = !digital;
  const xray = form.source === "x_ray";
  const planar = digital && !form.detector_curved;
  const isAsme = form.standard === "asme";
  const dwdi = form.geometry === "dwdi_elliptic" || form.geometry === "dwdi_super";

  // Desktop-parity output visibility (see _update_output_visibility):
  // u_max is X-ray only; duplex/panel counts and ASME rows are mode/standard
  // specific. SFD_min/SDD_min and quality labels switch with the technology.
  const hiddenOutputs = new Set<string>();
  if (!xray) hiddenOutputs.add("u_max");
  if (analog) {
    hiddenOutputs.add("duplex_iqi");
    hiddenOutputs.add("exposures_panel");
  }
  if (!isAsme) {
    hiddenOutputs.add("asme_iqi");
    hiddenOutputs.add("f_min_asme");
  }
  const outputLabel = (key: string): string => {
    if (key === "sfd_min") return t(digital ? "sfd_min" : "sfd_min_analog");
    if (key === "quality_target") {
      return t(digital ? "target_snr" : "optical_density");
    }
    if (key === "detector_quality") {
      return t(digital ? "detector_quality" : "film_class_req");
    }
    return t(key);
  };

  // SFD_min / SDD_min provenance: which candidate (f_min+b, receptor
  // coverage or the DWSI physical floor) governs the value.
  const provenance = result?.values?.sfd_min_provenance as
    | {
        active: string;
        candidates: {
          key: string;
          value: number;
          formula_key: string;
          receptor?: "df" | "dd";
          f_min?: number;
          b?: number;
          l3_dw?: boolean;
          l3_central?: boolean;
        }[];
      }
    | undefined;
  const candidateLabel = (candidate: {
    key: string;
    receptor?: "df" | "dd";
  }): string => {
    if (candidate.key === "f_min_plus_b") return t("sfd_prov_f_min");
    if (candidate.key === "coverage") {
      return candidate.receptor === "dd"
        ? t("sfd_prov_coverage_panel")
        : t("sfd_prov_coverage_film");
    }
    return t("sfd_prov_dwsi_floor");
  };
  const provenanceText = provenance
    ? provenance.candidates
        .map(
          (candidate) =>
            `${candidateLabel(candidate)} = ${candidate.value.toFixed(1)} mm [${t(candidate.formula_key)}]`,
        )
        .join(" | ")
    : "";
  const provenanceSummary = provenance
    ? (() => {
        const active = provenance.candidates.find(
          (candidate) => candidate.key === provenance.active,
        );
        if (!active) return "";
        const level3 =
          active.l3_dw || active.l3_central ? ` — ${t("sfd_prov_l3")}` : "";
        return `${t("sfd_prov_active", candidateLabel(active))} ${active.value.toFixed(1)} mm [${t(active.formula_key)}]${level3}`;
      })()
    : "";

  // Required-exposure-count provenance (Annex A figure / rule and boundaries).
  const exposuresProvenance = result?.values?.exposures_provenance as
    | {
        method: string;
        n: number;
        figure?: string;
        t_over_de?: number;
        ratio_name?: string;
        ratio?: number;
        next_n?: number | null;
        next_ratio?: number | null;
        next_distance_mm?: number | null;
        next_op?: "le" | "ge";
        l3_dw?: boolean;
        boundaries?: [number, number][];
      }
    | undefined;
  const fMinProvenance = result?.values?.f_min_provenance as
    | {
        base: number;
        value: number;
        formula_key: string;
        l3_dw?: boolean;
        l3_central?: boolean;
      }
    | undefined;
  const fMinProvenanceText = (() => {
    if (!fMinProvenance) return "";
    let text = t("fmin_prov_base", fMinProvenance.base, t(fMinProvenance.formula_key));
    const reduced = fMinProvenance.l3_dw || fMinProvenance.l3_central;
    if (fMinProvenance.l3_dw) text += ` \u2192 ${t("fmin_prov_dw")}`;
    if (fMinProvenance.l3_central) text += ` \u2192 ${t("fmin_prov_central")}`;
    if (reduced) text += ` \u2192 ${t("fmin_prov_final", fMinProvenance.value)}`;
    return text;
  })();

  const exposuresProvenanceText = (() => {
    if (!exposuresProvenance) return "";
    const prov = exposuresProvenance;
    if (prov.method === "annex_a") {
      let text = t(
        "exp_prov_annex_a",
        prov.figure,
        prov.t_over_de,
        prov.ratio_name,
        prov.ratio,
        prov.n,
      );
      if (
        prov.next_n != null &&
        prov.next_ratio != null &&
        prov.next_distance_mm != null
      ) {
        text += ` — ${t(
          prov.next_op === "ge" ? "exp_prov_next_ge" : "exp_prov_next_le",
          prov.next_n,
          prov.ratio_name,
          prov.next_ratio,
          prov.next_distance_mm,
        )}`;
      }
      if (prov.l3_dw) text += ` — ${t("exp_prov_l3")}`;
      return text;
    }
    if (prov.method === "panoramic") return t("exp_prov_panoramic");
    if (prov.method === "dwdi_rule") {
      return t("exp_prov_dwdi", prov.ratio, prov.n);
    }
    return t("exp_prov_fallback", prov.n);
  })();

  const exposureTimeProvenanceText =
    (result?.values?.exposure_time_provenance_text as string | undefined) ?? "";
  const exposureTimeProvenanceLines = exposureTimeProvenanceText
    ? exposureTimeProvenanceText.split("\n").filter((line) => line.trim())
    : [];

  const materialOptions = MATERIALS.map((value) => ({
    value,
    label: t(value),
  }));
  const sourceOptions = SOURCES.map((value) => ({ value, label: t(value) }));
  const activePipeTable = useMemo(() => {
    if (!pipeData) return null;
    return pipeStd === "b36_19" && pipeData.b36_19
      ? pipeData.b36_19
      : pipeData.b36_10;
  }, [pipeData, pipeStd]);

  const currentOdKey = useMemo(
    () => selectedOdKey(form.od, activePipeTable),
    [form.od, activePipeTable],
  );

  const odOptions = useMemo(() => {
    if (!activePipeTable) {
      return [{ value: "114.3", label: '4" (NPS 4) — 114.3 mm' }];
    }
    const items = Object.entries(activePipeTable).map(([key, entry]) => ({
      value: key,
      label: `${key} — ${entry.od} mm`,
    }));
    if (currentOdKey === "__custom__") {
      items.unshift({
        value: "__custom__",
        label:
          lang === "tr"
            ? `Özel Çap (${form.od} mm)`
            : `Custom OD (${form.od} mm)`,
      });
    }
    return items;
  }, [activePipeTable, currentOdKey, form.od, lang]);

  const scheduleOptions = useMemo(() => {
    if (!activePipeTable || currentOdKey === "__custom__") return [];
    const entry = activePipeTable[currentOdKey];
    if (!entry) return [];
    return entry.schedules.map(([wall, label]) => ({
      value: String(wall),
      label: `${label} — ${wall} mm`,
    }));
  }, [activePipeTable, currentOdKey]);

  const patchReport = (key: string, value: string) =>
    setReportInfo((previous) => ({ ...previous, [key]: value }));

  const applyDesktopState = (state: Record<string, unknown>) => {
    const { form: partial, reportInfo: info } = desktopStateToForm(
      state,
      pipeData,
    );
    setForm((previous) => ({ ...previous, ...partial }));
    setReportInfo((previous) => ({ ...previous, ...info }));
  };

  const syncAllCalculated = () => {
    if (!result) return;
    const v = result.values;
    setForm((prev) => ({
      ...prev,
      sfd: Math.max(prev.sfd, Math.ceil(v.sfd_min ?? prev.sfd)),
      app_time: Math.max(1, Math.round(v.calc_time ?? prev.app_time)),
      app_exposures: v.n_required ?? prev.app_exposures,
      app_wire: (v.wire_no as number | undefined) ?? prev.app_wire,
      app_duplex: (v.duplex_no as number | undefined) ?? prev.app_duplex,
      app_kv:
        prev.source === "x_ray" && v.u_max && prev.app_kv > v.u_max
          ? Math.floor(v.u_max * 0.85)
          : prev.app_kv,
      app_srb:
        prev.tech === "digital" && (v.max_srb as number | undefined)
          ? Number(v.max_srb)
          : prev.app_srb,
    }));
    setNotice(
      lang === "tr"
        ? "Hesaplanan hedef değerler uygulanan pozlama alanlarına aktarıldı."
        : "Calculated target values synced to applied exposure fields.",
    );
  };

  const exportPreset = () =>
    downloadJson("rt_preset.json", {
      type: "radiography_preset",
      version: pyClient.version ?? "1.8.3",
      state: formToDesktopState(form, reportInfo, pipeData, lang),
    });

  const exportProject = () =>
    downloadJson("rt_project.json", {
      type: "radiography_project",
      version: pyClient.version ?? "1.8.3",
      state: formToDesktopState(form, reportInfo, pipeData, lang),
      calculated: result?.calculated ?? {},
      warnings: (result?.warnings ?? []).join("\n"),
    });

  const exportProjectCsv = () => {
    const state = formToDesktopState(form, reportInfo, pipeData, lang);
    downloadCsv("rt_project.csv", [
      ...Object.entries(state),
      ...Object.entries(result?.calculated ?? {}),
    ]);
  };

  const readFile = async (file: File | undefined) => {
    if (!file) return "";
    return file.text();
  };

  const runDefect = async () => {
    setDefectActive(true);
    try {
      const evaluated = await pyClient.request<DefectResult>("defect", {
        form,
        defect,
        lang,
      });
      setDefectResult(evaluated);
    } catch (caught) {
      setNotice(String(caught));
    }
  };

  const exportPdf = async () => {
    if (!result) {
      setNotice("Hesaplama hazır değil / Calculation not ready");
      return;
    }
    setPdfBusy(true);
    setNotice(null);
    try {
      await pyClient.request("pdf:prepare");
      const calculated = result.calculated as Record<string, unknown>;
      const lvl3Active = (
        [
          "sfd_comp",
          "voltage_override",
          "isotope_flex",
          "source_flex",
          "central_proj_reduction",
          "dw_reduction",
        ] as (keyof Lvl3Settings)[]
      ).some((key) => Boolean(lvl3[key]));
      const defectPayload = defectResult
        ? {
            active: true,
            status: defectResult.status,
            type_text: t(defect.type),
            len: defect.length,
            width: defect.width,
            accum: defect.accumulated,
            reason: defectResult.result,
          }
        : null;
      const stamp = new Date()
        .toISOString()
        .replace(/[-:T]/g, "")
        .slice(0, 14);
      const [sketchPng, standardPng] = await Promise.all([
        svgToPngBase64("dynamic-sketch"),
        svgToPngBase64("standard-sketch"),
      ]);
      const data = await pyClient.request<{
        pdf_base64: string;
        filename: string;
      }>("generate_pdf", {
        form,
        calculated,
        display: result.display,
        warnings: result.warnings,
        defect: defectPayload,
        lvl3_active: lvl3Active,
        sfd_comp_val: calculated.sfd_comp_target ?? null,
        lang,
        report_info: reportInfo,
        sketch_png_base64: sketchPng,
        standard_png_base64: standardPng,
        filename: `RT_Inspection_Report_${stamp}.pdf`,
      });
      downloadBase64(data.pdf_base64, data.filename);
      setNotice(t("report_saved", data.filename));
    } catch (caught) {
      setNotice(String(caught));
    } finally {
      setPdfBusy(false);
    }
  };

  if (!ready) {
    return (
      <div className="boot-screen">
        <h1>Radiography</h1>
        <p>{t("app_title")}</p>
        <div className="spinner" />
        <p className="boot-note">
          {bootError
            ? `Hata / Error: ${bootError}`
            : "Python çekirdeği (Pyodide) yükleniyor… / Loading the Python core…"}
        </p>
      </div>
    );
  }

  const baseEUnit = xray ? "mA·min/m²" : "Ci·min/m²";
  const activityFactor = activityUnit === "GBq" ? 37 : 1;
  const bedSuggested = result?.values?.bed_auto_suggested as number | undefined;
  const wireTargetNo = result?.values?.wire_no as number | undefined;
  const duplexTargetNo = result?.values?.duplex_no as number | undefined;

  return (
    <UnitContext.Provider value={{ inch: unitInch }}>
      <div className="app">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark">RT</div>
            <h1 className="title">{t("app_title")}</h1>
          </div>
          <div className="topbar-actions">
            <button onClick={() => setLang(lang === "tr" ? "en" : "tr")}>
              {t("lang_switch")}
            </button>
            <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? t("theme_light") : t("theme_dark")}
            </button>
            <button onClick={() => setUnitInch((value) => !value)}>
              {unitInch ? "inç" : "mm"}
            </button>
            <button className="danger" onClick={() => setShowLvl3(true)}>
              {t("level3_section")}
            </button>
            <button className="primary" onClick={exportPdf} disabled={pdfBusy}>
              {pdfBusy ? "…" : t("export_pdf")}
            </button>
            <span className={busy ? "status busy" : "status"}>
              {busy ? "…" : error ? "!" : "OK"}
            </span>
          </div>
        </header>
        {notice && (
          <div className="toast" onClick={() => setNotice(null)} role="status">
            {notice}
          </div>
        )}
        <div className="toolbar">
          <select
            value=""
            onChange={(event) => {
              const preset = NAMED_PRESETS[event.target.value];
              if (preset) {
                setForm((previous) => {
                  const nextSource = preset.source ?? previous.source;
                  return {
                    ...previous,
                    ...preset,
                    base_e:
                      preset.base_e ??
                      DEFAULT_BASE_E_BY_SOURCE[nextSource] ??
                      previous.base_e,
                  };
                });
              }
              event.target.value = "";
            }}
          >
            <option value="">
              {lang === "tr" ? "Hazır Şablonlar" : "Built-in Templates"}
            </option>
            {Object.keys(NAMED_PRESETS).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button onClick={exportPreset}>
            {lang === "tr" ? "Şablon Kaydet" : "Save Preset"}
          </button>
          <button onClick={() => presetInput.current?.click()}>
            {lang === "tr" ? "Şablon Yükle" : "Load Preset"}
          </button>
          <button onClick={exportProject}>
            {lang === "tr" ? "Proje Dışa (JSON)" : "Export Project (JSON)"}
          </button>
          <button onClick={() => projectInput.current?.click()}>
            {lang === "tr" ? "Proje İçe (JSON)" : "Import Project (JSON)"}
          </button>
          <button onClick={exportProjectCsv}>
            {lang === "tr" ? "CSV Dışa" : "Export CSV"}
          </button>
          <button onClick={() => csvInput.current?.click()}>
            {lang === "tr" ? "CSV İçe" : "Import CSV"}
          </button>
          <button
            onClick={() =>
              document
                .querySelectorAll<HTMLDetailsElement>("details.group")
                .forEach((element) => {
                  element.open = true;
                })
            }
          >
            {lang === "tr" ? "Tümünü Aç" : "Expand All"}
          </button>
          <button
            onClick={() =>
              document
                .querySelectorAll<HTMLDetailsElement>("details.group")
                .forEach((element) => {
                  element.open = false;
                })
            }
          >
            {lang === "tr" ? "Tümünü Kapat" : "Collapse All"}
          </button>
          <input
            ref={presetInput}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={async (event) => {
              try {
                const data = JSON.parse(await readFile(event.target.files?.[0]));
                if (data.type !== "radiography_preset") {
                  throw new Error("Not a valid Radiography preset file.");
                }
                applyDesktopState(data.state ?? {});
                setNotice(lang === "tr" ? "Şablon yüklendi." : "Preset loaded.");
              } catch (caught) {
                setNotice(String(caught));
              }
              event.target.value = "";
            }}
          />
          <input
            ref={projectInput}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={async (event) => {
              try {
                const data = JSON.parse(await readFile(event.target.files?.[0]));
                if (data.type !== "radiography_project") {
                  throw new Error("Not a valid Radiography project file.");
                }
                applyDesktopState(data.state ?? {});
                setNotice(lang === "tr" ? "Proje içe aktarıldı." : "Project imported.");
              } catch (caught) {
                setNotice(String(caught));
              }
              event.target.value = "";
            }}
          />
          <input
            ref={csvInput}
            type="file"
            accept="text/csv,.csv"
            hidden
            onChange={async (event) => {
              try {
                applyDesktopState(parseCsv(await readFile(event.target.files?.[0])));
                setNotice(lang === "tr" ? "CSV içe aktarıldı." : "CSV imported.");
              } catch (caught) {
                setNotice(String(caught));
              }
              event.target.value = "";
            }}
          />
        </div>

        <main className="layout">
          <div className="column inputs">
            <Group title={t("inputs_section")}>
              <SelectField
                label={t("material_type")}
                value={form.material}
                options={materialOptions}
                onChange={(value) => patch("material", value)}
              />
              <SelectField
                label={t("std_pipe_od")}
                value={currentOdKey}
                options={odOptions}
                action={
                  <button
                    type="button"
                    className="sync-btn"
                    onClick={() =>
                      setPipeStd((prev) =>
                        prev === "b36_10" ? "b36_19" : "b36_10",
                      )
                    }
                    title={
                      lang === "tr"
                        ? "ASME B36.10 (Karbon Çelik) / B36.19 (Paslanmaz Çelik) tablosunu değiştir"
                        : "Toggle ASME B36.10 (Carbon) / B36.19 (Stainless) pipe schedule table"
                    }
                  >
                    {pipeStd === "b36_10" ? "ASME B36.10" : "ASME B36.19"}
                  </button>
                }
                onChange={(value) => {
                  const entry = activePipeTable?.[value];
                  if (entry) {
                    setForm((prev) => ({
                      ...prev,
                      od: entry.od,
                      t: entry.schedules[0]?.[0] ?? prev.t,
                    }));
                  }
                }}
              />
              <div className="field-row-2">
                <LengthField
                  label={t("custom_pipe_od")}
                  value={form.od}
                  min={1}
                  max={5000}
                  onChange={(value) => patch("od", value ?? form.od)}
                />
                <LengthField
                  label={t("custom_nominal_t")}
                  value={form.t}
                  min={0.1}
                  max={500}
                  onChange={(value) => patch("t", value ?? form.t)}
                />
              </div>
              <SelectField
                label={t("std_nominal_t")}
                value={String(form.t)}
                options={
                  scheduleOptions.length
                    ? scheduleOptions
                    : [
                        {
                          value: String(form.t),
                          label: `${form.t} mm (${lang === "tr" ? "Özel" : "Custom"})`,
                        },
                      ]
                }
                onChange={(value) => patch("t", Number(value))}
              />
              <div className={dwdi ? "field-row-2" : undefined}>
                <LengthField
                  label={t("cap_height")}
                  value={form.cap}
                  min={0}
                  max={50}
                  onChange={(value) => patch("cap", value ?? 0)}
                />
                {dwdi && (
                  <LengthField
                    label={t("weld_width")}
                    value={form.weld_width}
                    min={0}
                    max={500}
                    tooltip={
                      lang === "tr"
                        ? `Eliptik çekimde kaynak genişliği ≤ De/4 (${(form.od / 4).toFixed(1)} mm) olmalıdır.`
                        : `In elliptical DWDI, weld width should be ≤ De/4 (${(form.od / 4).toFixed(1)} mm).`
                    }
                    onChange={(value) => patch("weld_width", value ?? 0)}
                  />
                )}
              </div>
              <RadioGroup
                label={t("rt_tech")}
                value={form.tech}
                options={[
                  { value: "analog", label: t("analog_film") },
                  { value: "digital", label: t("digital_cr_dda") },
                ]}
                onChange={(value) => {
                  const tech = value as FormState["tech"];
                  const validCharts = getActiveChartKeys(tech, form.detector_type);
                  patch("tech", tech);
                  patch("app_quality", tech === "digital" ? 140 : 2.5);
                  if (!validCharts.includes(form.chart_source)) {
                    patch("chart_source", "model");
                  }
                  if (tech === "analog") {
                    patch("f_source", null);
                    patch("b_object", null);
                  }
                }}
              />
              <div className="field-row-2">
                <SelectField
                  label={t("rad_source")}
                  value={form.source}
                  options={sourceOptions}
                  onChange={(value) => {
                    setForm((previous) => ({
                      ...previous,
                      source: value,
                      base_e:
                        DEFAULT_BASE_E_BY_SOURCE[value] ?? previous.base_e,
                      output_val:
                        value === "x_ray"
                          ? previous.source === "x_ray"
                            ? previous.output_val
                            : 5.0
                          : previous.app_activity || 40.0,
                    }));
                  }}
                />
                <LengthField
                  label={xray ? t("focal_size") : t("source_size_d")}
                  value={form.d}
                  min={0.01}
                  max={20}
                  onChange={(value) => patch("d", value ?? 2)}
                />
              </div>
              {analog && (
                <>
                  <SelectField
                    label={t("film_size")}
                    value={filmSizeMode}
                    options={[
                      { value: "80x300", label: "80 x 300 mm" },
                      { value: "100x400", label: "100 x 400 mm" },
                      { value: "300x400", label: "300 x 400 mm" },
                      { value: "100x500", label: "100 x 500 mm" },
                      { value: "custom", label: t("film_size_custom") },
                    ]}
                    onChange={(value) => {
                      setFilmSizeMode(value);
                      const preset = FILM_PRESETS[value];
                      if (preset) {
                        patch("film_width", preset[0]);
                        patch("film_height", preset[1]);
                      }
                    }}
                  />
                  {filmSizeMode === "custom" && (
                    <div className="field-row-2">
                      <LengthField
                        label={t("film_width")}
                        value={form.film_width}
                        min={1}
                        max={2000}
                        onChange={(value) =>
                          patch("film_width", value ?? form.film_width)
                        }
                      />
                      <LengthField
                        label={t("film_height")}
                        value={form.film_height}
                        min={1}
                        max={2000}
                        onChange={(value) =>
                          patch("film_height", value ?? form.film_height)
                        }
                      />
                    </div>
                  )}
                </>
              )}
              <div className="field-row-2">
                <SelectField
                  label={t("testing_class")}
                  value={form.testing_class}
                  options={[
                    { value: "class_b", label: t("class_b") },
                    { value: "class_a", label: t("class_a") },
                  ]}
                  onChange={(value) =>
                    patch("testing_class", value as FormState["testing_class"])
                  }
                />
                <SelectField
                  label={t("standard")}
                  value={form.standard}
                  options={[
                    { value: "iso", label: t("standard_iso") },
                    { value: "asme", label: t("standard_asme") },
                  ]}
                  onChange={(value) =>
                    patch("standard", value as FormState["standard"])
                  }
                />
              </div>
              <SelectField
                label={t("geometry")}
                value={form.geometry}
                options={GEOMETRIES.map((value) => ({
                  value,
                  label: t(value),
                }))}
                onChange={(value) =>
                  patch("geometry", value as FormState["geometry"])
                }
              />
              {dwdi && form.od > 100 && (
                <div className="inline-alert" role="status">
                  <span>
                    {lang === "tr"
                      ? `⚠ ISO 17636 gereği DWDI (Eliptik / Süperpoze) yalnızca OD ≤ 100 mm borularda uygulanır (mevcut OD = ${form.od} mm). Hesaplama motoru otomatik olarak DWSI kullanıyor.`
                      : `⚠ Per ISO 17636, DWDI is only valid for OD ≤ 100 mm (current OD = ${form.od} mm). Engine automatically calculates as DWSI.`}
                  </span>
                  <div className="inline-alert-actions">
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() => {
                        setForm((prev) => ({ ...prev, od: 88.9, t: 5.49 }));
                      }}
                    >
                      {lang === "tr"
                        ? '3" Boru Yap (88.9 mm)'
                        : 'Set 3" Pipe (88.9 mm)'}
                    </button>
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() => patch("geometry", "dwsi")}
                    >
                      {lang === "tr" ? "DWSI Seç" : "Switch to DWSI"}
                    </button>
                  </div>
                </div>
              )}
              <SelectField
                label={t("standard_fig")}
                value={form.std_figure ?? ""}
                options={figures.map((figure) => ({
                  value: figure,
                  label: t(`${figure}_title`),
                }))}
                onChange={(value) => patch("std_figure", value || null)}
              />
              {digital && (
                <RadioGroup
                  label={t("detector_type")}
                  value={form.detector_curved ? "curved" : "flat"}
                  options={[
                    { value: "flat", label: t("detector_planar") },
                    { value: "curved", label: t("detector_flexible") },
                  ]}
                  onChange={(value) => patch("detector_curved", value === "curved")}
                />
              )}
              {planar && (
                <div className="field-row-2">
                  <LengthField
                    label={t("bed")}
                    value={form.bed}
                    min={0}
                    max={500}
                    tooltip={t("tt_bed")}
                    action={
                      bedSuggested != null && bedSuggested > 0 ? (
                        <button
                          type="button"
                          className="sync-btn"
                          onClick={() =>
                            patch("bed", Number(bedSuggested.toFixed(1)))
                          }
                        >
                          ← {bedSuggested.toFixed(1)}
                        </button>
                      ) : undefined
                    }
                    onChange={(value) => patch("bed", value ?? 0)}
                  />
                  <LengthField
                    label={t("bgap")}
                    value={form.bgap}
                    min={0}
                    max={100}
                    tooltip={t("tt_bgap")}
                    onChange={(value) => patch("bgap", value ?? 0)}
                  />
                </div>
              )}
              {digital && (
                <div className="field-row-2">
                  <LengthField
                    label={t("source_dist")}
                    value={form.f_source}
                    min={1}
                    max={5000}
                    placeholder={t("auto_calc")}
                    tooltip={t("tt_f_source")}
                    action={
                      form.f_source != null ? (
                        <button
                          type="button"
                          className="sync-btn"
                          onClick={() => patch("f_source", null)}
                        >
                          {lang === "tr" ? "↺ Otomatik" : "↺ Auto"}
                        </button>
                      ) : undefined
                    }
                    onChange={(value) => patch("f_source", value)}
                  />
                  <LengthField
                    label={t("object_dist")}
                    value={form.b_object}
                    min={0}
                    max={5000}
                    placeholder={t("auto_calc")}
                    tooltip={t("tt_b_object")}
                    action={
                      form.b_object != null ? (
                        <button
                          type="button"
                          className="sync-btn"
                          onClick={() => patch("b_object", null)}
                        >
                          {lang === "tr" ? "↺ Otomatik" : "↺ Auto"}
                        </button>
                      ) : undefined
                    }
                    onChange={(value) => patch("b_object", value)}
                  />
                </div>
              )}
              <CheckField
                label={t("source_side_iqi")}
                checked={!form.film_side}
                onChange={(checked) => patch("film_side", !checked)}
              />
              <SelectField
                label={t("iqi_type")}
                value={form.iqi_type}
                options={[
                  { value: "wire", label: t("iqi_type_wire") },
                  { value: "step_hole", label: t("iqi_type_step_hole") },
                ]}
                onChange={(value) => {
                  patch("iqi_type", value as FormState["iqi_type"]);
                  patch("app_wire", 10);
                }}
              />
            </Group>

            <Group
              title={t("applied_exposure_section")}
              headerAction={
                <button
                  type="button"
                  className="sync-btn"
                  onClick={syncAllCalculated}
                  title={
                    lang === "tr"
                      ? "Hesaplanan SFD_min, Poz Süresi, Poz Sayısı ve IQI hedeflerini tek tıkla uygula"
                      : "Sync calculated SFD_min, exposure time, exposure count, and IQI targets"
                  }
                >
                  {lang === "tr" ? "⚡ Hesaplananları Aktar" : "⚡ Sync Calculated"}
                </button>
              }
            >
              <LengthSliderField
                label={t(digital ? "applied_sdd" : "applied_sfd")}
                value={form.sfd}
                min={10}
                max={5000}
                step={5}
                sliderMin={100}
                sliderMax={3000}
                action={
                  result?.values.sfd_min ? (
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() =>
                        patch("sfd", Math.ceil(result.values.sfd_min))
                      }
                    >
                      ← Min {Math.ceil(result.values.sfd_min)} mm
                    </button>
                  ) : undefined
                }
                onChange={(value) => patch("sfd", value ?? 600)}
              />
              <SliderField
                label={t("base_multiplier")}
                value={form.base_multiplier}
                min={0.01}
                max={100}
                step={0.05}
                sliderMin={0.1}
                sliderMax={3}
                tooltip={t("tt_base_multiplier")}
                onChange={(value) => {
                  patch("base_multiplier", value ?? 1);
                  patch("base_multiplier_raw", value ?? 1);
                }}
              />
              {xray ? (
                <>
                  <SliderField
                    label={t("amperage")}
                    value={form.output_val}
                    min={0.01}
                    max={1000}
                    step={0.1}
                    sliderMin={0.5}
                    sliderMax={30}
                    onChange={(value) => patch("output_val", value ?? 5)}
                  />
                  <SliderField
                    label={t("applied_kv")}
                    value={form.app_kv}
                    min={1}
                    max={1000}
                    step={1}
                    sliderMin={20}
                    sliderMax={400}
                    action={
                      result?.values.u_max ? (
                        <button
                          type="button"
                          className="sync-btn"
                          onClick={() =>
                            patch(
                              "app_kv",
                              Math.floor(result.values.u_max * 0.85),
                            )
                          }
                        >
                          ← ≤{Math.floor(result.values.u_max)} kV
                        </button>
                      ) : undefined
                    }
                    onChange={(value) => patch("app_kv", value ?? 120)}
                  />
                </>
              ) : (
                <SliderField
                  label={`${t("activity")} (${activityUnit})`}
                  value={Number((form.output_val * activityFactor).toFixed(2))}
                  min={0.01}
                  max={37000}
                  step={activityUnit === "GBq" ? 10 : 1}
                  sliderMin={activityUnit === "GBq" ? 37 : 1}
                  sliderMax={activityUnit === "GBq" ? 5550 : 150}
                  action={
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() =>
                        setActivityUnit((u) => (u === "Ci" ? "GBq" : "Ci"))
                      }
                      title="1 Ci = 37 GBq"
                    >
                      {activityUnit === "Ci" ? "Ci → GBq" : "GBq → Ci"}
                    </button>
                  }
                  onChange={(value) => {
                    const ciVal = (value ?? 40 * activityFactor) / activityFactor;
                    patch("output_val", ciVal);
                    patch("app_activity", ciVal);
                  }}
                />
              )}
              <NumberField
                label={`${t("base_factor")} (${baseEUnit})`}
                value={form.base_e}
                min={0.0001}
                max={2000}
                tooltip={t("tt_base_factor")}
                disabled={
                  form.chart_source !== "model" &&
                  form.chart_source !== "dda_frame_method"
                }
                action={
                  form.base_e !==
                  (DEFAULT_BASE_E_BY_SOURCE[form.source] ?? 3.0) ? (
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() =>
                        patch(
                          "base_e",
                          DEFAULT_BASE_E_BY_SOURCE[form.source] ?? 3.0,
                        )
                      }
                    >
                      ← {DEFAULT_BASE_E_BY_SOURCE[form.source] ?? 3.0}
                    </button>
                  ) : undefined
                }
                onChange={(value) =>
                  patch(
                    "base_e",
                    value ?? (DEFAULT_BASE_E_BY_SOURCE[form.source] ?? 3),
                  )
                }
              />
              {!xray && (
                <>
                  <div className="field-row-2">
                    <SelectField
                      label={t("collimator")}
                      value={String(form.collimator_hvl)}
                      options={[
                        { value: "0", label: t("collimator_none") },
                        { value: "1", label: "1 HVL" },
                        { value: "2", label: "2 HVL" },
                        { value: "4", label: "4 HVL" },
                      ]}
                      onChange={(value) => patch("collimator_hvl", Number(value))}
                    />
                    <NumberField
                      label={t("barrier_limit_label")}
                      value={form.barrier_limit_usvh}
                      min={0.1}
                      max={1000}
                      onChange={(value) => patch("barrier_limit_usvh", value ?? 20)}
                    />
                  </div>
                  <SelectField
                    label={t("gamma_convention")}
                    value={form.gamma_convention}
                    options={[
                      { value: "r", label: t("gamma_conv_r") },
                      { value: "msv", label: t("gamma_conv_msv") },
                    ]}
                    onChange={(value) =>
                      patch("gamma_convention", value as FormState["gamma_convention"])
                    }
                  />
                  <button type="button" onClick={() => setShowDecay(true)}>
                    {t("decay_dialog")}
                  </button>
                </>
              )}
              {isAsme && (
                <SelectField
                  label={t("asme_sensitivity")}
                  value={form.asme_sensitivity}
                  options={[
                    { value: "2-2T", label: t("sens_2_2t") },
                    { value: "2-1T", label: t("sens_2_1t") },
                    { value: "1-2T", label: t("sens_1_2t") },
                  ]}
                  onChange={(value) => patch("asme_sensitivity", value)}
                />
              )}
              <SelectField
                label={t(digital ? "chart_source_digital" : "chart_source")}
                value={form.chart_source}
                options={(
                  digital
                    ? form.detector_type.startsWith("dda_")
                      ? DIGITAL_DDA_CHART_OPTIONS
                      : DIGITAL_CR_CHART_OPTIONS
                    : ANALOG_CHART_OPTIONS
                ).map((option) => ({
                  value: option.value,
                  label: option.labelKey ? t(option.labelKey) : option.label!,
                }))}
                onChange={(value) => patch("chart_source", value)}
              />
              {analog && (
                <div className="field-row-2">
                  <SelectField
                    label={t("film_class_used")}
                    value={form.film_class_used}
                    options={["C1", "C2", "C3", "C4", "C5", "C6"].map((value) => ({
                      value,
                      label: value,
                    }))}
                    onChange={(value) => patch("film_class_used", value)}
                  />
                  <LengthField
                    label={t("applied_overlap")}
                    value={form.app_overlap}
                    min={0}
                    max={500}
                    onChange={(value) => {
                      patch("app_overlap", value ?? 0);
                      patch("app_overlap_warn", value ?? 10);
                    }}
                  />
                </div>
              )}
              <DurationSliderField
                label={t("applied_time")}
                value={form.app_time}
                lang={lang}
                action={
                  result?.values.calc_time ? (
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() =>
                        patch(
                          "app_time",
                          Math.max(1, Math.round(result.values.calc_time)),
                        )
                      }
                    >
                      ← {result.display.calc_time}
                    </button>
                  ) : undefined
                }
                onChange={(value) => patch("app_time", value ?? 120)}
              />
              {digital && (
                <>
                  <SelectField
                    label={t("detector_type")}
                    value={form.detector_type}
                    options={DETECTOR_KEYS.map((value, index) => ({
                      value,
                      label: t(DETECTOR_TKEYS[index]),
                    }))}
                    onChange={(value) => {
                      const validCharts = getActiveChartKeys(form.tech, value);
                      patch("detector_type", value);
                      if (!validCharts.includes(form.chart_source)) {
                        patch("chart_source", "model");
                      }
                    }}
                  />
                  <div className="field-row-2">
                    <NumberField
                      label={t("applied_srb")}
                      value={form.app_srb}
                      min={1}
                      max={1000}
                      action={
                        result?.values.max_srb ? (
                          <button
                            type="button"
                            className="sync-btn"
                            onClick={() =>
                              patch("app_srb", Number(result.values.max_srb))
                            }
                          >
                            ← ≤{String(result.values.max_srb)}
                          </button>
                        ) : undefined
                      }
                      onChange={(value) => patch("app_srb", value ?? 80)}
                    />
                    <SelectField
                      label={t("snr_location")}
                      value={form.snr_location}
                      options={[
                        { value: "weld", label: t("snr_location_weld") },
                        { value: "adjacent", label: t("snr_location_adjacent") },
                      ]}
                      onChange={(value) =>
                        patch("snr_location", value as FormState["snr_location"])
                      }
                    />
                  </div>
                  <SelectField
                    label={t("applied_duplex")}
                    value={String(form.app_duplex)}
                    options={Array.from({ length: 13 }, (_, index) => ({
                      value: String(index + 1),
                      label: `D${index + 1}`,
                    }))}
                    action={
                      duplexTargetNo ? (
                        <button
                          type="button"
                          className="sync-btn"
                          onClick={() => patch("app_duplex", duplexTargetNo)}
                        >
                          ← D{duplexTargetNo}
                        </button>
                      ) : undefined
                    }
                    onChange={(value) => patch("app_duplex", Number(value))}
                  />
                </>
              )}
              <SelectField
                label={form.iqi_type === "step_hole" ? t("applied_step_hole") : t("applied_wire")}
                value={String(form.app_wire)}
                options={Object.entries(
                  (form.iqi_type === "step_hole"
                    ? iqiOptions?.step_hole
                    : iqiOptions?.wire) ?? {},
                )
                  .sort((a, b) => Number(a[0]) - Number(b[0]))
                  .map(([number, diameter]) => ({
                    value: number,
                    label: `${form.iqi_type === "step_hole" ? "H" : "W"} ${number} (${diameter.toFixed(3)} mm)`,
                  }))}
                action={
                  wireTargetNo ? (
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() => patch("app_wire", wireTargetNo)}
                    >
                      ← {form.iqi_type === "step_hole" ? "H" : "W"}
                      {wireTargetNo}
                    </button>
                  ) : undefined
                }
                onChange={(value) => patch("app_wire", Number(value))}
              />
              <SliderField
                label={t("applied_quality")}
                value={form.app_quality}
                min={0.01}
                max={10000}
                step={1}
                sliderMin={1}
                sliderMax={300}
                onChange={(value) => patch("app_quality", value ?? 0)}
              />
              {/* Applied exposure count: used by the compliance check in BOTH
                  analog and digital mode (desktop parity). */}
              <NumberField
                label={t("applied_exposures")}
                value={form.app_exposures}
                min={0}
                max={100}
                step={1}
                action={
                  result?.values.n_required ? (
                    <button
                      type="button"
                      className="sync-btn"
                      onClick={() =>
                        patch("app_exposures", result.values.n_required)
                      }
                    >
                      ← Min {result.values.n_required}
                    </button>
                  ) : undefined
                }
                onChange={(value) => patch("app_exposures", Math.round(value ?? 0))}
              />
              {digital && (
                <>
                  <div className="field-row-2">
                    <LengthField
                      label={t("panel_width")}
                      value={form.panel_width}
                      min={10}
                      max={2000}
                      onChange={(value) => patch("panel_width", value ?? 200)}
                    />
                    <LengthField
                      label={t("panel_height")}
                      value={form.panel_height}
                      min={10}
                      max={2000}
                      onChange={(value) => patch("panel_height", value ?? 200)}
                    />
                  </div>
                  <NumberField
                    label={t("panel_overlap")}
                    value={form.panel_overlap}
                    min={0}
                    max={50}
                    onChange={(value) => patch("panel_overlap", value ?? 10)}
                  />
                </>
              )}
            </Group>

            <Group title={t("report_info_section")} open={false}>
              <div className="field-row-2">
                {REPORT_FIELDS.map(([key, labelKey]) => (
                  <label className="field" key={key}>
                    <span className="field-label">{t(labelKey)}</span>
                    <input
                      className="field-input"
                      type="text"
                      value={reportInfo[key] ?? ""}
                      onChange={(event) => patchReport(key, event.target.value)}
                    />
                  </label>
                ))}
              </div>
            </Group>
          </div>

          <div className="column outputs">
            <div className="hero-grid">
              <div className="hero-card">
                <div className="hero-main">
                  <div className="hero-label">
                    {t("calc_time").replace(/:\s*$/, "")}
                  </div>
                  {exposureTimeProvenanceLines.length > 0 ? (
                    <div
                      className="hero-formula-list"
                      title={exposureTimeProvenanceText}
                    >
                      {exposureTimeProvenanceLines.map((line, idx) => {
                        const colonIdx = line.indexOf(":");
                        if (colonIdx > 0) {
                          const head = line.slice(0, colonIdx);
                          const tail = line.slice(colonIdx + 1).trim();
                          const isFormula =
                            head === "Formül" || head === "Formula";
                          return (
                            <div key={idx} className="hero-formula-line">
                              <strong>{head}:</strong>{" "}
                              {isFormula ? (
                                <span className="hero-formula-eq">{tail}</span>
                              ) : (
                                tail
                              )}
                            </div>
                          );
                        }
                        return (
                          <div key={idx} className="hero-formula-line">
                            {line}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    result && (
                      <div className="hero-sub">
                        {`w_eff = ${result.display.w_eff} • ${digital ? "SDD" : "SFD"} = ${form.sfd} mm • F = ${form.base_multiplier}×`}
                      </div>
                    )
                  )}
                </div>
                <div className="hero-right">
                  <div className="hero-value">
                    {result?.display.calc_time ?? "-"}
                  </div>
                  {result && (
                    <span
                      className={`hero-status ${
                        form.app_time >= Math.floor(result.values.calc_time)
                          ? "ok"
                          : "warn"
                      }`}
                    >
                      {lang === "tr" ? "Uygulanan" : "Applied"}:{" "}
                      {Math.floor(form.app_time / 60)}m{" "}
                      {Math.round(form.app_time % 60)}s
                    </span>
                  )}
                </div>
              </div>
              <div className="hero-card">
                <div className="hero-main">
                  <div className="hero-label">
                    {t(digital ? "sfd_min" : "sfd_min_analog").replace(
                      /:\s*$/,
                      "",
                    )}
                  </div>
                  {provenanceSummary && (
                    <div className="hero-sub" title={provenanceText}>
                      {provenanceSummary}
                    </div>
                  )}
                </div>
                <div className="hero-right">
                  <div className="hero-value">
                    {result?.display.sfd_min ?? "-"}
                  </div>
                  {result && (
                    <span
                      className={`hero-status ${
                        form.sfd >= result.values.sfd_min ? "ok" : "warn"
                      }`}
                    >
                      {lang === "tr" ? "Uygulanan" : "Applied"}: {form.sfd} mm{" "}
                      {form.sfd >= result.values.sfd_min ? "✓" : "⚠"}
                    </span>
                  )}
                </div>
              </div>
              <div className="hero-card">
                <div className="hero-main">
                  <div className="hero-label">
                    {t("f_min").replace(/:\s*$/, "")}
                  </div>
                  {fMinProvenanceText && (
                    <div className="hero-sub">
                      {fMinProvenanceText}
                      {result
                        ? ` • b = ${result.values.b_dist.toFixed(1)} mm (b_eff = ${result.values.b_eff.toFixed(1)} mm)`
                        : ""}
                    </div>
                  )}
                </div>
                <div className="hero-right">
                  <div className="hero-value">
                    {result?.display.f_min ?? "-"}
                  </div>
                </div>
              </div>
              <div className="hero-card">
                <div className="hero-main">
                  <div className="hero-label">
                    {t("ug").replace(/:\s*$/, "")}
                  </div>
                  {result && (
                    <div className="hero-sub">
                      {`Ug = d·b / f (d = ${form.d} mm, b = ${(
                        result.values.f_min_provenance?.b ??
                        (!result.values.is_planar && result.values.b_rule_applied
                          ? result.values.b_eff
                          : result.values.b_dist)
                      ).toFixed(1)} mm)`}
                      {isAsme
                        ? ` • ASME Limit ≤ ${result.values.ug_limit.toFixed(2)} mm`
                        : ""}
                    </div>
                  )}
                </div>
                <div className="hero-right">
                  <div className="hero-value">{result?.display.ug ?? "-"}</div>
                  {result && isAsme && (
                    <span
                      className={`hero-status ${
                        result.values.ug_ok ? "ok" : "warn"
                      }`}
                    >
                      {result.values.ug_ok ? "ASME ✓" : "ASME ⚠"}
                    </span>
                  )}
                </div>
              </div>
              <div className="hero-card">
                <div className="hero-main">
                  <div className="hero-label">
                    {t("req_exposures").replace(/:\s*$/, "")}
                  </div>
                  {exposuresProvenanceText && (
                    <div className="hero-sub">{exposuresProvenanceText}</div>
                  )}
                </div>
                <div className="hero-right">
                  <div className="hero-value">
                    {result?.display.req_exposures ?? "-"}
                  </div>
                  {result && (
                    <span
                      className={`hero-status ${
                        form.app_exposures === 0 ||
                        Boolean(result.values.exposures_ok)
                          ? "ok"
                          : "warn"
                      }`}
                    >
                      {result.display.exposures_check}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <Group title={t("outputs")}>
              {OUTPUT_KEYS.filter((key) => !hiddenOutputs.has(key)).map((key) => (
                <OutputRow
                  key={key}
                  testId={`output-${key}`}
                  label={outputLabel(key)}
                  value={result?.display[key] ?? "-"}
                  tooltip={
                    key === "sfd_min" && provenanceText
                      ? `${strings[`tt_${key}`] ?? ""} ${provenanceText}`.trim()
                      : key === "f_min" && fMinProvenanceText
                        ? `${strings[`tt_${key}`] ?? ""} ${fMinProvenanceText}`.trim()
                        : key === "req_exposures" && exposuresProvenanceText
                          ? `${strings[`tt_${key}`] ?? ""} ${exposuresProvenanceText}`.trim()
                          : key === "calc_time" && exposureTimeProvenanceText
                            ? `${strings[`tt_${key}`] ?? ""}\n${exposureTimeProvenanceText}`.trim()
                            : strings[`tt_${key}`]
                  }
                />
              ))}
            </Group>
            <Group title={t("procedure_section")}>
              <div
                className={
                  compliance?.is_compliant
                    ? "badge compliant"
                    : "badge non-compliant"
                }
              >
                {compliance?.is_compliant ? t("compliant") : t("non_compliant")}
              </div>
              <ul className="check-list">
                {compliance?.checks.map((check) => (
                  <li key={check.name} className={check.status ? "ok" : "fail"}>
                    {check.status ? "✓" : "✗"} {check.details}
                  </li>
                ))}
                {compliance?.activity_warning && (
                  <li className="warn">⚠ {compliance.activity_warning}</li>
                )}
              </ul>
            </Group>
          </div>

          <div className="column warnings">
            <div className="tabs">
              <button
                type="button"
                className={sketchTab === "3d" ? "tab active" : "tab"}
                onClick={() => setSketchTab("3d")}
              >
                {lang === "tr" ? "3D Kurulum" : "3D Setup"}
              </button>
              <button
                type="button"
                className={sketchTab === "dynamic" ? "tab active" : "tab"}
                onClick={() => setSketchTab("dynamic")}
              >
                {lang === "tr" ? "2D Kesit" : "2D Sketch"}
              </button>
              <button
                type="button"
                className={sketchTab === "figure" ? "tab active" : "tab"}
                onClick={() => setSketchTab("figure")}
              >
                {lang === "tr" ? "ISO Figürü" : "ISO Figure"}
              </button>
              <button
                type="button"
                className={sketchTab === "annex_a" ? "tab active" : "tab"}
                onClick={() => setSketchTab("annex_a")}
              >
                Annex A
              </button>
            </div>

            {sketchTab === "3d" && (
              <Group
                title={
                  lang === "tr"
                    ? "3D Çekim Geometrisi ve İzdüşüm Sahnesi"
                    : "3D Shooting Geometry & Projection Scene"
                }
              >
                {result ? (
                  <WeldSetup3D
                    od={result.values.od}
                    t={result.values.t}
                    cap={result.values.cap}
                    weldWidth={form.weld_width}
                    d={form.d}
                    geometry={result.values.geometry}
                    userGeometry={form.geometry}
                    geometryForced={Boolean(result.values.geometry_forced)}
                    sfd={result.values.sfd}
                    fMin={result.values.f_min}
                    bDist={result.values.b_dist}
                    bed={Number(result.values.bed ?? 0)}
                    bgap={form.bgap}
                    ug={result.values.ug}
                    isPlanar={Boolean(result.values.is_planar)}
                    isDigital={digital}
                    filmSide={form.film_side}
                    panelWidth={form.panel_width}
                    panelHeight={form.panel_height}
                    filmWidth={form.film_width}
                    filmHeight={form.film_height}
                    overlapPct={
                      digital ? result.values.panel_overlap : form.app_overlap
                    }
                    nRequired={result.values.n_required}
                    nApplied={form.app_exposures}
                    wireStr={String(result.values.wire_str ?? "W10")}
                    duplexStr={String(result.values.duplex_str ?? "D6")}
                    safetyRadiusM={result.values.safety_radius_m}
                    supervisedRadiusM={
                      (result.values.r_supervised as number | undefined) ?? null
                    }
                    theme={theme}
                    lang={lang}
                  />
                ) : (
                  <p className="muted">…</p>
                )}
              </Group>
            )}

            <div style={{ display: sketchTab === "dynamic" ? "block" : "none" }}>
              <Group title={t("sketch_title")}>
                {result ? (
                  <div id="dynamic-sketch">
                    <WeldSetupSvg
                      od={result.values.od}
                      t={result.values.t}
                      cap={result.values.cap}
                      geometry={
                        result.values.geometry_forced
                          ? form.geometry
                          : result.values.geometry
                      }
                      sfd={result.values.sfd}
                      fMin={result.values.f_min}
                      bDist={result.values.b_dist}
                      bed={Number(result.values.bed ?? 0)}
                      bgap={form.bgap}
                      ug={result.values.ug}
                      filmSide={form.film_side}
                      isPlanar={Boolean(result.values.is_planar)}
                      nRequired={result.values.n_required}
                      nApplied={form.app_exposures}
                      panelWidth={
                        form.tech === "digital" ? result.values.panel_width : null
                      }
                      overlapPct={result.values.panel_overlap}
                      safetyRadiusM={result.values.safety_radius_m}
                      supervisedRadiusM={
                        (result.values.r_supervised as number | undefined) ?? null
                      }
                      labels={{
                        pipe: t("pipe_wall"),
                        source: t("source"),
                        detector: t("detector"),
                        dda: t("dda_label"),
                        overlap: t("overlap_short"),
                        safety: t("safety_ring"),
                        sourceOffset: t("source_offset"),
                        beamAngle: t("beam_angle"),
                      }}
                    />
                  </div>
                ) : (
                  <p className="muted">…</p>
                )}
              </Group>
            </div>

            <div style={{ display: sketchTab === "figure" ? "block" : "none" }}>
              <Group title={t("standard_fig")}>
                {form.std_figure ? (
                  <div id="standard-sketch">
                    <StandardFigureSvg
                      figure={form.std_figure}
                      title={t(`${form.std_figure}_title`)}
                    />
                  </div>
                ) : (
                  <p className="muted">-</p>
                )}
              </Group>
            </div>

            {sketchTab === "annex_a" && (
              <Group
                title={
                  lang === "tr"
                    ? "ISO 17636 Annex A Çalışma Noktası Grafiği"
                    : "ISO 17636 Annex A Operating Point Chart"
                }
              >
                {exposuresProvenance && exposuresProvenance.method === "annex_a" ? (
                  <AnnexAChartSvg
                    figure={exposuresProvenance.figure}
                    tOverDe={exposuresProvenance.t_over_de}
                    ratioName={exposuresProvenance.ratio_name}
                    ratio={exposuresProvenance.ratio}
                    n={exposuresProvenance.n}
                    nextN={exposuresProvenance.next_n}
                    nextRatio={exposuresProvenance.next_ratio}
                    nextDistanceMm={exposuresProvenance.next_distance_mm}
                    boundaries={exposuresProvenance.boundaries}
                    lang={lang}
                  />
                ) : (
                  <p className="muted">
                    {exposuresProvenanceText ||
                      (lang === "tr"
                        ? "Mevcut teknik (Panoramik / DWDI) Annex A eğrisi yerine doğrudan kural kullanıyor."
                        : "Current technique (Panoramic / DWDI) uses direct rule instead of Annex A curve.")}
                  </p>
                )}
              </Group>
            )}

            <Group title={t("warnings")}>
              {result?.warnings.length ? (
                <ul className="warning-list">
                  {result.warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No active warnings.</p>
              )}
            </Group>

            <Group title={t("defect_section")}>
              <div className="field-row-2">
                <SelectField
                  label={t("defect_standard")}
                  value={defect.standard}
                  options={DEFECT_STANDARDS.map((option) => ({
                    value: option.value,
                    label: t(option.labelKey),
                  }))}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({
                      ...previous,
                      standard: value as DefectInput["standard"],
                    }));
                  }}
                />
                <SelectField
                  label={t("defect_type")}
                  value={defect.type}
                  options={DEFECT_TYPES.map((value) => ({
                    value,
                    label: t(value),
                  }))}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({ ...previous, type: value }));
                  }}
                />
              </div>
              {defect.standard === "iso5817" && (
                <SelectField
                  label={t("quality_level")}
                  value={defect.level ?? "C"}
                  options={[
                    { value: "B", label: "B" },
                    { value: "C", label: "C" },
                    { value: "D", label: "D" },
                  ]}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({ ...previous, level: value }));
                  }}
                />
              )}
              {defect.standard === "b31_3" && (
                <SelectField
                  label={t("b31_service")}
                  value={defect.service ?? "normal"}
                  options={[
                    { value: "normal", label: t("service_normal") },
                    { value: "severe", label: t("service_severe") },
                  ]}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({ ...previous, service: value }));
                  }}
                />
              )}
              {defect.standard === "viii" && (
                <SelectField
                  label={t("viii_mode")}
                  value={defect.mode ?? "UW-51"}
                  options={[
                    { value: "UW-51", label: t("mode_uw51") },
                    { value: "UW-52", label: t("mode_uw52") },
                  ]}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({ ...previous, mode: value }));
                  }}
                />
              )}
              <div className="field-row-2">
                <LengthField
                  label={t("defect_length") || "Length (mm)"}
                  value={defect.length}
                  min={0}
                  max={1000}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({ ...previous, length: value ?? 0 }));
                  }}
                />
                <LengthField
                  label={t("defect_width") || "Width/Depth (mm)"}
                  value={defect.width}
                  min={0}
                  max={100}
                  onChange={(value) => {
                    setDefectActive(true);
                    setDefect((previous) => ({ ...previous, width: value ?? 0 }));
                  }}
                />
              </div>
              <LengthField
                label={t("accumulated_12in")}
                value={defect.accumulated}
                min={0}
                max={300}
                onChange={(value) => {
                  setDefectActive(true);
                  setDefect((previous) => ({
                    ...previous,
                    accumulated: value ?? 0,
                  }));
                }}
              />
              <DefectStripSvg
                defectType={defect.type}
                lengthMm={defect.length}
                widthMm={defect.width}
                accumulatedMm={defect.accumulated}
                wallT={form.t}
                accepted={defectResult ? defectResult.status : null}
                lang={lang}
              />
              <button type="button" className="primary" onClick={runDefect}>
                {t("evaluate_defect") || "Evaluate"}
              </button>
              {defectResult && (
                <div
                  className={
                    defectResult.status
                      ? "badge compliant"
                      : "badge non-compliant"
                  }
                >
                  {defectResult.status ? t("result_accept") : t("result_reject")}
                </div>
              )}
              {defectResult && (
                <p className="muted defect-reason">{defectResult.result}</p>
              )}
            </Group>
          </div>
        </main>

        {showLvl3 && (
          <Lvl3Dialog
            lvl3={lvl3}
            t={t}
            onChange={setLvl3}
            onClose={() => setShowLvl3(false)}
          />
        )}
        {showDecay && (
          <DecayDialog
            t={t}
            source={form.source}
            onApply={(activity) => {
              patch("output_val", activity);
              patch("app_activity", activity);
            }}
            onClose={() => setShowDecay(false)}
          />
        )}
        <PageScrollbar />
      </div>
    </UnitContext.Provider>
  );
}

/** Rasterises an inline SVG (by container id) to a PNG base64 string. */
async function svgToPngBase64(containerId: string): Promise<string | null> {
  const container = document.getElementById(containerId);
  const svg = container?.querySelector("svg");
  if (!svg) return null;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const styles = getComputedStyle(document.documentElement);
  const resolve = (value: string | null) => {
    if (!value || !value.includes("var(")) return value;
    return value.replace(/var\((--[^)]+)\)/g, (_, name: string) => {
      const resolved = styles.getPropertyValue(name).trim();
      return resolved || "#000000";
    });
  };
  clone.querySelectorAll("*").forEach((element) => {
    for (const attribute of ["fill", "stroke"]) {
      const value = resolve(element.getAttribute(attribute));
      if (value) element.setAttribute(attribute, value);
    }
  });
  clone.setAttribute("width", "900");
  clone.setAttribute("height", "900");
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const serialized = new XMLSerializer().serializeToString(clone);
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(serialized)}`;
  const image = new Image();
  await new Promise<void>((resolvePromise, rejectPromise) => {
    image.onload = () => resolvePromise();
    image.onerror = () => rejectPromise(new Error("SVG rasterisation failed"));
    image.src = url;
  });
  const canvas = document.createElement("canvas");
  canvas.width = 900;
  canvas.height = 900;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.fillStyle =
    styles.getPropertyValue("--bg-alt").trim() || "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png").split(",", 1)[0] === "data:image/png"
    ? canvas.toDataURL("image/png").split(",", 2)[1]
    : null;
}

function downloadBase64(base64: string, filename: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const blob = new Blob([bytes], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

interface DecayDialogProps {
  t: (key: string, ...args: unknown[]) => string;
  source: string;
  onApply: (activity: number) => void;
  onClose: () => void;
}

function DecayDialog({ t, source, onApply, onClose }: DecayDialogProps) {
  const [initial, setInitial] = useState(40);
  const [calibDate, setCalibDate] = useState("");
  const [current, setCurrent] = useState<number | null>(null);

  useEffect(() => {
    if (!calibDate) {
      setCurrent(null);
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const data = await pyClient.request<{
          current_activity: number;
          days: number;
        }>("decay", {
          activity: initial,
          calib_date: calibDate,
          isotope: source,
        });
        setCurrent(data.current_activity);
      } catch {
        setCurrent(null);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [initial, calibDate, source]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <h2>{t("decay_dialog")}</h2>
        <NumberField
          label={t("decay_initial")}
          value={initial}
          min={0.01}
          max={1000}
          onChange={(value) => setInitial(value ?? 40)}
        />
        <label className="field">
          <span className="field-label">{t("decay_calib_date")}</span>
          <input
            className="field-input"
            type="date"
            value={calibDate}
            onChange={(event) => setCalibDate(event.target.value)}
          />
        </label>
        <p>
          {t("decay_current")}{" "}
          <strong>{current === null ? "-" : `${current.toFixed(1)} Ci`}</strong>
        </p>
        <div className="modal-actions">
          <button onClick={onClose}>{t("dialog_cancel")}</button>
          <button
            className="primary"
            disabled={current === null}
            onClick={() => {
              if (current !== null) onApply(current);
              onClose();
            }}
          >
            {t("decay_apply")}
          </button>
        </div>
      </div>
    </div>
  );
}

function selectedOdKey(
  od: number,
  pipeTable: Record<string, { od: number; schedules: [number, string][] }> | null,
): string {
  if (!pipeTable) return '4" (NPS 4)';
  for (const [key, entry] of Object.entries(pipeTable)) {
    if (Math.abs(entry.od - od) < 0.15) {
      return key;
    }
  }
  return "__custom__";
}

interface Lvl3DialogProps {
  lvl3: Lvl3Settings;
  t: (key: string, ...args: unknown[]) => string;
  onChange: (lvl3: Lvl3Settings) => void;
  onClose: () => void;
}

function Lvl3Dialog({ lvl3, t, onChange, onClose }: Lvl3DialogProps) {
  const options: [keyof Lvl3Settings, string][] = [
    ["sfd_comp", "lvl3_sfd_compensation"],
    ["voltage_override", "lvl3_voltage_override"],
    ["isotope_flex", "lvl3_isotope_flex"],
    ["source_flex", "lvl3_source_flex"],
    ["central_proj_reduction", "lvl3_central_proj"],
    ["dw_reduction", "lvl3_dw_reduction"],
  ];
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <h2>{t("level3_section")}</h2>
        {options.map(([key, labelKey]) => (
          <label className="field field-inline" key={key}>
            <input
              type="checkbox"
              checked={Boolean(lvl3[key])}
              onChange={(event) =>
                onChange({ ...lvl3, [key]: event.target.checked })
              }
            />
            <span>{t(labelKey)}</span>
          </label>
        ))}
        <label className="field">
          <span className="field-label">{t("level3_approval_note")}</span>
          <textarea
            className="field-input"
            rows={3}
            placeholder={t("level3_approval_placeholder")}
            value={lvl3.approval_note}
            onChange={(event) =>
              onChange({ ...lvl3, approval_note: event.target.value })
            }
          />
        </label>
        <div className="modal-actions">
          <button onClick={onClose}>{t("dialog_cancel")}</button>
          <button className="primary" onClick={onClose}>
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}
