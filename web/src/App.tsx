import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  CheckField,
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
import { StandardFigureSvg, WeldSetupSvg } from "./components/SketchView";
import { makeTranslator } from "./i18n";
import { pyClient } from "./pyodide/client";
import {
  NAMED_PRESETS,
  desktopStateToForm,
  downloadCsv,
  downloadJson,
  formToDesktopState,
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
const DETECTOR_KEYS = ["cr_standard", "cr_hires", "dda_si", "dda_se", "dda_gdos"];
const DETECTOR_TKEYS = [
  "detector_cr_std",
  "detector_cr_hires",
  "detector_dda_si",
  "detector_dda_se",
  "detector_dda_gdos",
];
const CHART_OPTIONS = [
  { value: "model", labelKey: "chart_model" },
  { value: "AA400", label: "AA400 (C5)" },
  { value: "MX125", label: "MX125 (C3)" },
  { value: "T200", label: "T200 (C4)" },
  { value: "HS800", label: "HS800 (C6)" },
  { value: "M100", label: "M100 (C2)" },
  { value: "type_x", labelKey: "chart_type_x" },
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
    return raw ? (JSON.parse(raw) as PersistedState) : {};
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
  const [sketchTab, setSketchTab] = useState<"dynamic" | "figure">("dynamic");
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

  const materialOptions = MATERIALS.map((value) => ({
    value,
    label: t(value),
  }));
  const sourceOptions = SOURCES.map((value) => ({ value, label: t(value) }));
  const odOptions = useMemo(() => {
    if (!pipeData) return [{ value: "114.3", label: '4" (NPS 4) — 114.3 mm' }];
    return Object.entries(pipeData.b36_10).map(([key, entry]) => ({
      value: key,
      label: `${key} — ${entry.od} mm`,
    }));
  }, [pipeData]);
  const scheduleOptions = useMemo(() => {
    if (!pipeData) return [];
    const entry = pipeData.b36_10[selectedOdKey(form.od, pipeData)];
    if (!entry) return [];
    return entry.schedules.map(([wall, label]) => ({
      value: String(wall),
      label: `${label} — ${wall} mm`,
    }));
  }, [pipeData, form.od]);

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
              if (preset) setForm((previous) => ({ ...previous, ...preset }));
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
                value={selectedOdKey(form.od, pipeData)}
                options={odOptions}
                onChange={(value) => {
                  const entry = pipeData?.b36_10[value];
                  if (entry) patch("od", entry.od);
                }}
              />
              <LengthField
                label={t("custom_pipe_od")}
                value={form.od}
                min={1}
                max={5000}
                onChange={(value) => patch("od", value ?? form.od)}
              />
              <SelectField
                label={t("std_nominal_t")}
                value={String(form.t)}
                options={
                  scheduleOptions.length
                    ? scheduleOptions
                    : [{ value: String(form.t), label: `${form.t} mm` }]
                }
                onChange={(value) => patch("t", Number(value))}
              />
              <LengthField
                label={t("custom_nominal_t")}
                value={form.t}
                min={0.1}
                max={500}
                onChange={(value) => patch("t", value ?? form.t)}
              />
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
                  onChange={(value) => patch("weld_width", value ?? 0)}
                />
              )}
              <RadioGroup
                label={t("rt_tech")}
                value={form.tech}
                options={[
                  { value: "analog", label: t("analog_film") },
                  { value: "digital", label: t("digital_cr_dda") },
                ]}
                onChange={(value) => {
                  const tech = value as FormState["tech"];
                  patch("tech", tech);
                  patch("app_quality", tech === "digital" ? 140 : 2.5);
                }}
              />
              <SelectField
                label={t("rad_source")}
                value={form.source}
                options={sourceOptions}
                onChange={(value) => patch("source", value)}
              />
              <LengthField
                label={xray ? t("focal_size") : t("source_size_d")}
                value={form.d}
                min={0.01}
                max={20}
                onChange={(value) => patch("d", value ?? 2)}
              />
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
                    <>
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
                    </>
                  )}
                </>
              )}
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
                <>
                  <LengthField
                    label={t("bed")}
                    value={form.bed}
                    min={0}
                    max={500}
                    onChange={(value) => patch("bed", value ?? 0)}
                  />
                  <LengthField
                    label={t("bgap")}
                    value={form.bgap}
                    min={0}
                    max={100}
                    onChange={(value) => patch("bgap", value ?? 0)}
                  />
                </>
              )}
              {digital && (
                <>
                  <LengthField
                    label={t("source_dist")}
                    value={form.f_source}
                    min={1}
                    max={5000}
                    placeholder={t("auto_calc")}
                    onChange={(value) => patch("f_source", value)}
                  />
                  <LengthField
                    label={t("object_dist")}
                    value={form.b_object}
                    min={0}
                    max={5000}
                    placeholder={t("auto_calc")}
                    onChange={(value) => patch("b_object", value)}
                  />
                </>
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

            <Group title={t("applied_exposure_section")}>
              <LengthSliderField
                label={t(digital ? "applied_sdd" : "applied_sfd")}
                value={form.sfd}
                min={10}
                max={5000}
                step={5}
                sliderMin={100}
                sliderMax={3000}
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
                    onChange={(value) => patch("app_kv", value ?? 120)}
                  />
                </>
              ) : (
                <SliderField
                  label={t("activity")}
                  value={form.output_val}
                  min={0.01}
                  max={1000}
                  step={1}
                  sliderMin={1}
                  sliderMax={150}
                  onChange={(value) => {
                    patch("output_val", value ?? 40);
                    patch("app_activity", value ?? 40);
                  }}
                />
              )}
              {xray && (
                <NumberField
                  label={t("base_factor")}
                  value={form.base_e}
                  min={0.0001}
                  max={2000}
                  disabled={form.chart_source !== "model"}
                  onChange={(value) => patch("base_e", value ?? 3)}
                />
              )}
              {!xray && (
                <>
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
                label={t("chart_source")}
                value={form.chart_source}
                options={CHART_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.labelKey ? t(option.labelKey) : option.label!,
                }))}
                onChange={(value) => patch("chart_source", value)}
              />
              {analog && (
                <>
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
                </>
              )}
              <SliderField
                label={t("applied_time")}
                value={form.app_time}
                min={0.1}
                max={100000}
                step={5}
                sliderMin={5}
                sliderMax={1800}
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
                    onChange={(value) => patch("detector_type", value)}
                  />
                  <NumberField
                    label={t("applied_srb")}
                    value={form.app_srb}
                    min={1}
                    max={1000}
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
                  <SelectField
                    label={t("applied_duplex")}
                    value={String(form.app_duplex)}
                    options={Array.from({ length: 13 }, (_, index) => ({
                      value: String(index + 1),
                      label: String(index + 1),
                    }))}
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
                onChange={(value) => patch("app_exposures", Math.round(value ?? 0))}
              />
              {digital && (
                <>
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

            <Group title={t("report_info_section")}>
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
            </Group>
          </div>

          <div className="column outputs">
            <div className="hero-grid">
              <div className="hero-card">
                <div className="hero-label">{t("calc_time")}</div>
                <div className="hero-value">
                  {result?.display.calc_time ?? "-"}
                </div>
              </div>
              <div className="hero-card">
                <div className="hero-label">
                  {t(digital ? "sfd_min" : "sfd_min_analog")}
                </div>
                <div className="hero-value">
                  {result?.display.sfd_min ?? "-"}
                </div>
                {provenanceSummary && (
                  <div className="hero-sub" title={provenanceText}>
                    {provenanceSummary}
                  </div>
                )}
              </div>
              <div className="hero-card">
                <div className="hero-label">{t("f_min")}</div>
                <div className="hero-value">
                  {result?.display.f_min ?? "-"}
                </div>
                {fMinProvenanceText && (
                  <div className="hero-sub">{fMinProvenanceText}</div>
                )}
              </div>
              <div className="hero-card">
                <div className="hero-label">{t("ug")}</div>
                <div className="hero-value">{result?.display.ug ?? "-"}</div>
              </div>
              <div className="hero-card">
                <div className="hero-label">{t("req_exposures")}</div>
                <div className="hero-value">
                  {result?.display.req_exposures ?? "-"}
                </div>
                {exposuresProvenanceText && (
                  <div className="hero-sub">{exposuresProvenanceText}</div>
                )}
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
            <div className="tabs">
              <button
                className={sketchTab === "dynamic" ? "tab active" : "tab"}
                onClick={() => setSketchTab("dynamic")}
              >
                {lang === "tr" ? "Çekim Şeması" : "Setup Sketch"}
              </button>
              <button
                className={sketchTab === "figure" ? "tab active" : "tab"}
                onClick={() => setSketchTab("figure")}
              >
                {lang === "tr" ? "ISO Figürü" : "ISO Figure"}
              </button>
            </div>
            <div style={{ display: sketchTab === "dynamic" ? "block" : "none" }}>
            <Group title={t("sketch_title")}>
              {result ? (
                <div id="dynamic-sketch">
                <WeldSetupSvg
                  od={result.values.od}
                  t={result.values.t}
                  cap={result.values.cap}
                  geometry={result.values.geometry}
                  sfd={result.values.sfd}
                  panelWidth={form.tech === "digital" ? result.values.panel_width : null}
                  overlapPct={result.values.panel_overlap}
                  safetyRadiusM={result.values.safety_radius_m}
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
            <Group title={t("defect_section")}>
              <SelectField
                label={t("defect_standard")}
                value={defect.standard}
                options={DEFECT_STANDARDS.map((option) => ({
                  value: option.value,
                  label: t(option.labelKey),
                }))}
                onChange={(value) =>
                  setDefect((previous) => ({
                    ...previous,
                    standard: value as DefectInput["standard"],
                  }))
                }
              />
              <SelectField
                label={t("defect_type")}
                value={defect.type}
                options={DEFECT_TYPES.map((value) => ({
                  value,
                  label: t(value),
                }))}
                onChange={(value) =>
                  setDefect((previous) => ({ ...previous, type: value }))
                }
              />
              {defect.standard === "iso5817" && (
                <SelectField
                  label={t("quality_level")}
                  value={defect.level ?? "C"}
                  options={[
                    { value: "B", label: "B" },
                    { value: "C", label: "C" },
                    { value: "D", label: "D" },
                  ]}
                  onChange={(value) =>
                    setDefect((previous) => ({ ...previous, level: value }))
                  }
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
                  onChange={(value) =>
                    setDefect((previous) => ({ ...previous, service: value }))
                  }
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
                  onChange={(value) =>
                    setDefect((previous) => ({ ...previous, mode: value }))
                  }
                />
              )}
              <LengthField
                label={t("defect_length") || "Length (mm)"}
                value={defect.length}
                min={0}
                max={1000}
                onChange={(value) =>
                  setDefect((previous) => ({ ...previous, length: value ?? 0 }))
                }
              />
              <LengthField
                label={t("defect_width") || "Width/Depth (mm)"}
                value={defect.width}
                min={0}
                max={100}
                onChange={(value) =>
                  setDefect((previous) => ({ ...previous, width: value ?? 0 }))
                }
              />
              <LengthField
                label={t("accumulated_12in")}
                value={defect.accumulated}
                min={0}
                max={300}
                onChange={(value) =>
                  setDefect((previous) => ({
                    ...previous,
                    accumulated: value ?? 0,
                  }))
                }
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

function selectedOdKey(od: number, pipeData: PipeData | null): string {
  if (!pipeData) return "4\" (NPS 4)";
  let best = "";
  let bestDelta = Infinity;
  for (const [key, entry] of Object.entries(pipeData.b36_10)) {
    const delta = Math.abs(entry.od - od);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = key;
    }
  }
  return best;
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
