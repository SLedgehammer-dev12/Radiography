import { useEffect, useMemo, useRef, useState } from "react";

import {
  CheckField,
  DurationSliderField,
  Group,
  InfoTip,
  LengthField,
  LengthSliderField,
  NumberField,
  PageScrollbar,
  RadioGroup,
  SelectField,
  SliderField,
  UnitContext,
} from "./components";
import { DefectPanel } from "./components/DefectPanel";
import { OutputsPanel } from "./components/OutputsPanel";
import { CompliancePanel } from "./components/CompliancePanel";
import { WarningsPanel } from "./components/WarningsPanel";
import { ReportInfoPanel } from "./components/ReportInfoPanel";
import { SketchTabsPanel } from "./components/SketchTabsPanel";
import {
  AboutModal,
  DecayDialog,
  FALLBACK_VERSION,
  Lvl3Dialog,
  UpdateModal,
} from "./components/Modals";
import { makeTranslator } from "./i18n";
import { downloadBase64, svgToPngBase64 } from "./lib/sketchExport";
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
  selectedOdKey,
} from "./state/presets";
import { useEngine } from "./state/useEngine";
import { useDefect } from "./state/useDefect";
import { usePersistedAppState } from "./state/usePersistedAppState";
import {
  type FormState,
  type ExposuresProvenance,
  type Lvl3Settings,
  type PipeData,
} from "./types";
import "./App.css";

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
const CHART_OPTION_META: Record<string, { labelKey?: string; label?: string }> = {
  model: { labelKey: "chart_model" },
  AA400: { label: "AA400 (C5)" },
  MX125: { label: "MX125 (C3)" },
  T200: { label: "T200 (C4)" },
  HS800: { label: "HS800 (C6)" },
  M100: { label: "M100 (C2)" },
  type_x: { labelKey: "chart_type_x" },
  cr_ips_chart: { labelKey: "chart_cr_ips" },
  dda_frame_method: { labelKey: "chart_dda_frame" },
  dda_panel_chart: { labelKey: "chart_dda_panel" },
  digital_xray_chart: { labelKey: "chart_digital_xray" },
};
const FILM_PRESETS: Record<string, [number, number]> = {
  "80x300": [80, 300],
  "100x400": [100, 400],
  "300x400": [300, 400],
  "100x500": [100, 500],
};
export default function App() {
  const {
    form,
    setForm,
    patch,
    lvl3,
    setLvl3,
    lang,
    setLang,
    theme,
    setTheme,
    reportInfo,
    setReportInfo,
  } = usePersistedAppState();
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
  const [showLvl3, setShowLvl3] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [showUpdates, setShowUpdates] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [sketchTab, setSketchTab] = useState<
    "3d" | "dynamic" | "figure" | "annex_a"
  >("3d");
  const [filmSizeMode, setFilmSizeMode] = useState<string>("100x400");
  const [showDecay, setShowDecay] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const presetInput = useRef<HTMLInputElement>(null);
  const projectInput = useRef<HTMLInputElement>(null);
  const csvInput = useRef<HTMLInputElement>(null);
  const [openMenu, setOpenMenu] = useState<
    "file" | "settings" | "level3" | "view" | "help" | null
  >(null);
  const menuContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!openMenu) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuContainerRef.current &&
        !menuContainerRef.current.contains(event.target as Node)
      ) {
        setOpenMenu(null);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenMenu(null);
      }
    };
    window.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [openMenu]);

  const { result, compliance, error, busy, ready } = useEngine(form, lvl3, lang);
  const t = useMemo(() => makeTranslator(strings), [strings]);

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

  // Defect-evaluation tab state + reactive re-evaluation (see useDefect).
  const {
    defect,
    setDefect,
    defectResult,
    setDefectActive,
    runDefect,
  } = useDefect({ form, lang, ready, onError: setNotice });

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
  hiddenOutputs.add("calc_time"); // Prominently displayed in the Hero Card directly above
  if (!xray) hiddenOutputs.add("u_max");
  if (analog) {
    hiddenOutputs.add("duplex_iqi");
    hiddenOutputs.add("exposures_panel");
  }
  if (!isAsme) {
    hiddenOutputs.add("asme_iqi");
    hiddenOutputs.add("f_min_asme");
  }
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
    | ExposuresProvenance
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
    if (prov.method === "out_of_chart") {
      return t("exp_prov_out_of_chart", prov.n);
    }
    return t("exp_prov_fallback", prov.n);
  })();

  const exposureTimeProvenanceText =
    (result?.values?.exposure_time_provenance_text as string | undefined) ?? "";
  const expProv = result?.values?.exposure_time_provenance as
    | Record<string, any>
    | undefined;
  const ddaFrame = expProv?.dda_frame as
    | {
        n_frames: number;
        t_frame_sec: number;
        t_frame_ms?: number;
        fps?: number;
        total_acq_sec: number;
        target_gray_pct: number;
        target_adu_16bit: number;
        total_dose_ugy?: number;
        dose_rate_ugy_s?: number;
        snr_1frame: number;
        panel_class?: string;
      }
    | undefined;

  const isLvl3Active = (
    [
      "sfd_comp",
      "voltage_override",
      "isotope_flex",
      "source_flex",
      "central_proj_reduction",
      "dw_reduction",
    ] as (keyof Lvl3Settings)[]
  ).some((key) => Boolean(lvl3[key]));

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
      version: pyClient.version ?? FALLBACK_VERSION,
      state: formToDesktopState(form, reportInfo, pipeData, lang),
    });

  const exportProject = () =>
    downloadJson("rt_project.json", {
      type: "radiography_project",
      version: pyClient.version ?? FALLBACK_VERSION,
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
        lvl3,
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
        <div className="toolbar menubar" ref={menuContainerRef}>
          {/* 1. Dosya Menüsü */}
          <div className="menu-container">
            <button
              type="button"
              className={`menu-trigger-btn ${openMenu === "file" ? "active" : ""}`}
              onClick={() =>
                setOpenMenu((prev) => (prev === "file" ? null : "file"))
              }
              aria-haspopup="true"
              aria-expanded={openMenu === "file"}
            >
              <span>{t("menu_file")}</span>
              <span className="dropdown-arrow">{openMenu === "file" ? "▲" : "▼"}</span>
            </button>
            {openMenu === "file" && (
              <div className="dropdown-menu" role="menu">
                <button
                  type="button"
                  className="dropdown-item primary-action"
                  onClick={() => {
                    exportPdf();
                    setOpenMenu(null);
                  }}
                  disabled={pdfBusy}
                >
                  <span className="item-icon">📄</span>
                  <span>{pdfBusy ? "…" : t("export_pdf")}</span>
                </button>

                <div className="dropdown-divider" />
                <div className="menu-section-header">
                  {t("section_presets")}
                </div>
                <div className="menu-select-wrapper">
                  <select
                    className="menu-select"
                    value=""
                    onChange={(event) => {
                      const preset = NAMED_PRESETS[event.target.value];
                      if (preset) {
                        setForm((previous) => {
                          const nextSource = preset.source ?? previous.source;
                          const nextTech = preset.tech ?? previous.tech;
                          const nextDetector =
                            preset.detector_type ?? previous.detector_type;
                          const next = {
                            ...previous,
                            ...preset,
                            base_e:
                              preset.base_e ??
                              DEFAULT_BASE_E_BY_SOURCE[nextSource] ??
                              previous.base_e,
                          };
                          // A preset may change tech/source/detector without
                          // changing chart_source; re-validate so an incompatible
                          // chart is never sent to the engine.
                          const validCharts = getActiveChartKeys(
                            nextTech,
                            nextDetector,
                            nextSource,
                          );
                          if (!validCharts.includes(next.chart_source)) {
                            next.chart_source =
                              nextTech !== "digital"
                                ? nextSource === "x_ray"
                                  ? "type_x"
                                  : "AA400"
                                : validCharts[0] ?? "model";
                          }
                          return next;
                        });
                        setNotice(
                          lang === "tr"
                            ? `"${event.target.value}" şablonu uygulandı.`
                            : `Applied "${event.target.value}" preset.`,
                        );
                      }
                      event.target.value = "";
                      setOpenMenu(null);
                    }}
                  >
                    <option value="">
                      {t("preset_select_prompt")}
                    </option>
                    {Object.keys(NAMED_PRESETS).map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    exportPreset();
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">💾</span>
                  <span>{t("save_preset")}</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    presetInput.current?.click();
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">📂</span>
                  <span>{t("load_preset")}</span>
                </button>

                <div className="dropdown-divider" />
                <div className="menu-section-header">
                  {t("section_project")}
                </div>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    exportProject();
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">📤</span>
                  <span>{t("export_project_json")}</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    projectInput.current?.click();
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">📥</span>
                  <span>{t("import_project_json")}</span>
                </button>

                <div className="dropdown-divider" />
                <div className="menu-section-header">
                  {t("section_csv")}
                </div>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    exportProjectCsv();
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">📊</span>
                  <span>{t("export_csv")}</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    csvInput.current?.click();
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">📑</span>
                  <span>{t("import_csv")}</span>
                </button>
              </div>
            )}
          </div>

          {/* 2. Ayarlar Menüsü */}
          <div className="menu-container">
            <button
              type="button"
              className={`menu-trigger-btn ${openMenu === "settings" ? "active" : ""}`}
              onClick={() =>
                setOpenMenu((prev) => (prev === "settings" ? null : "settings"))
              }
              aria-haspopup="true"
              aria-expanded={openMenu === "settings"}
            >
              <span>{t("menu_settings")}</span>
              <span className="dropdown-arrow">{openMenu === "settings" ? "▲" : "▼"}</span>
            </button>
            {openMenu === "settings" && (
              <div className="dropdown-menu" role="menu">
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setLang(lang === "tr" ? "en" : "tr");
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">🌐</span>
                  <span>
                    {lang === "tr"
                      ? "Dil: Türkçe (English'e Geç)"
                      : "Language: English (Türkçe'ye Geç)"}
                  </span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setTheme(theme === "dark" ? "light" : "dark");
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">🌓</span>
                  <span>
                    {theme === "dark"
                      ? (lang === "tr" ? "Tema: Karanlık (Aydınlığa Geç)" : "Theme: Dark (Switch to Light)")
                      : (lang === "tr" ? "Tema: Aydınlık (Karanlığa Geç)" : "Theme: Light (Switch to Dark)")}
                  </span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setUnitInch((value) => !value);
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">📏</span>
                  <span>
                    {unitInch
                      ? (lang === "tr" ? "Ölçü Birimi: inç (mm'ye Geç)" : "Unit: inch (Switch to mm)")
                      : (lang === "tr" ? "Ölçü Birimi: mm (inç'e Geç)" : "Unit: mm (Switch to inch)")}
                  </span>
                </button>
              </div>
            )}
          </div>

          {/* 3. Yetki Menüsü */}
          <div className="menu-container">
            <button
              type="button"
              className={`menu-trigger-btn ${isLvl3Active ? "danger-accent" : ""} ${openMenu === "level3" ? "active" : ""}`}
              onClick={() =>
                setOpenMenu((prev) => (prev === "level3" ? null : "level3"))
              }
              aria-haspopup="true"
              aria-expanded={openMenu === "level3"}
            >
              <span>{t("menu_authority")}</span>
              {isLvl3Active && <span className="menu-pill-danger">L3</span>}
              <span className="dropdown-arrow">{openMenu === "level3" ? "▲" : "▼"}</span>
            </button>
            {openMenu === "level3" && (
              <div className="dropdown-menu" role="menu">
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setShowLvl3(true);
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">🛡️</span>
                  <span>{t("open_level3_panel")}</span>
                </button>
              </div>
            )}
          </div>

          {/* 4. Görünüm Menüsü */}
          <div className="menu-container">
            <button
              type="button"
              className={`menu-trigger-btn ${openMenu === "view" ? "active" : ""}`}
              onClick={() =>
                setOpenMenu((prev) => (prev === "view" ? null : "view"))
              }
              aria-haspopup="true"
              aria-expanded={openMenu === "view"}
            >
              <span>{t("menu_view")}</span>
              <span className="dropdown-arrow">{openMenu === "view" ? "▲" : "▼"}</span>
            </button>
            {openMenu === "view" && (
              <div className="dropdown-menu" role="menu">
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    document
                      .querySelectorAll<HTMLDetailsElement>("details.group")
                      .forEach((element) => {
                        element.open = true;
                      });
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">🔽</span>
                  <span>{t("expand_all")}</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    document
                      .querySelectorAll<HTMLDetailsElement>("details.group")
                      .forEach((element) => {
                        element.open = false;
                      });
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">🔼</span>
                  <span>{t("collapse_all")}</span>
                </button>
              </div>
            )}
          </div>

          {/* 5. Yardım Menüsü */}
          <div className="menu-container">
            <button
              type="button"
              className={`menu-trigger-btn ${openMenu === "help" ? "active" : ""}`}
              onClick={() =>
                setOpenMenu((prev) => (prev === "help" ? null : "help"))
              }
              aria-haspopup="true"
              aria-expanded={openMenu === "help"}
            >
              <span>{t("menu_help")}</span>
              <span className="dropdown-arrow">{openMenu === "help" ? "▲" : "▼"}</span>
            </button>
            {openMenu === "help" && (
              <div className="dropdown-menu" role="menu">
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setShowAbout(true);
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">ℹ️</span>
                  <span>{t("open_about_panel")}</span>
                </button>
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    setShowUpdates(true);
                    setOpenMenu(null);
                  }}
                >
                  <span className="item-icon">🔄</span>
                  <span>{t("check_updates_btn")}</span>
                </button>
                <div className="dropdown-divider" />
                <a
                  className="dropdown-item"
                  href="https://github.com/SLedgehammer-dev12/Radiography/issues"
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => setOpenMenu(null)}
                >
                  <span className="item-icon">🐞</span>
                  <span>{t("report_issue")}</span>
                </a>
                <a
                  className="dropdown-item"
                  href="mailto:omer.erbas@botas.gov.tr"
                  onClick={() => setOpenMenu(null)}
                >
                  <span className="item-icon">✉️</span>
                  <span>{t("contact_email_action")}</span>
                </a>
              </div>
            )}
          </div>
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
                  const validCharts = getActiveChartKeys(tech, form.detector_type, form.source);
                  patch("tech", tech);
                  patch("app_quality", tech === "digital" ? 140 : 2.5);
                  if (!validCharts.includes(form.chart_source)) {
                    patch("chart_source", validCharts[0] ?? "model");
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
                    const newSource = value as FormState["source"];
                    const validCharts = getActiveChartKeys(form.tech, form.detector_type, newSource);
                    setForm((previous) => {
                      let nextChart = previous.chart_source;
                      if (!validCharts.includes(nextChart)) {
                        if (previous.tech !== "digital") {
                          nextChart = newSource === "x_ray" ? "type_x" : "AA400";
                        } else {
                          nextChart = validCharts[0] ?? "model";
                        }
                      }
                      return {
                        ...previous,
                        source: newSource,
                        chart_source: nextChart,
                        base_e:
                          DEFAULT_BASE_E_BY_SOURCE[newSource] ?? previous.base_e,
                        output_val:
                          newSource === "x_ray"
                            ? previous.source === "x_ray"
                              ? previous.output_val
                              : 5.0
                            : previous.app_activity || 40.0,
                      };
                    });
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
                  label={`${t("activity")} (${activityUnit}):`}
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
                options={getActiveChartKeys(
                  form.tech,
                  form.detector_type,
                  form.source,
                ).map((key) => {
                  if (key === "model" && digital) {
                    return { value: key, label: t("chart_digital_model") };
                  }
                  const meta = CHART_OPTION_META[key];
                  return {
                    value: key,
                    label: meta?.labelKey ? t(meta.labelKey) : (meta?.label ?? key),
                  };
                })}
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
                      const validCharts = getActiveChartKeys(form.tech, value, form.source);
                      patch("detector_type", value);
                      if (!validCharts.includes(form.chart_source)) {
                        patch("chart_source", validCharts[0] ?? "model");
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
                    options={Array.from({ length: 14 }, (_, index) => ({
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
                label={t("applied_quality") + (digital ? " (SNR_N)" : " (D)")}
                value={form.app_quality}
                min={digital ? 1 : 0.5}
                max={digital ? 1000 : 5.0}
                step={digital ? 1 : 0.05}
                sliderMin={digital ? 10 : 1.5}
                sliderMax={digital ? 300 : 4.5}
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

            <ReportInfoPanel
              t={t}
              reportInfo={reportInfo}
              patchReport={patchReport}
            />
          </div>

          <div className="column outputs">
            <div className="hero-grid">
              <div className="hero-card">
                <div className="hero-main">
                  <div
                    className="hero-label"
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    <span>{t("calc_time").replace(/:\s*$/, "")}</span>
                    {exposureTimeProvenanceText && (
                      <InfoTip
                        text={exposureTimeProvenanceText}
                        title={t("calc_time").replace(/:\s*$/, "")}
                      />
                    )}
                  </div>
                  {result && (
                    <div className="hero-sub">
                      {ddaFrame ? (
                        lang === "tr" ? (
                          <>
                            <span className="hero-frame-highlight">
                              <strong>{ddaFrame.n_frames}</strong> kare ×{" "}
                              <strong>{ddaFrame.t_frame_sec.toFixed(2)} sn</strong>
                              {ddaFrame.fps ? ` (${ddaFrame.fps.toFixed(1)} fps)` : ""}
                            </span>
                            {" • "}w_eff = {result.display.w_eff} •{" "}
                            {digital ? "SDD" : "SFD"} = {form.sfd} mm
                          </>
                        ) : (
                          <>
                            <span className="hero-frame-highlight">
                              <strong>{ddaFrame.n_frames}</strong> frames ×{" "}
                              <strong>{ddaFrame.t_frame_sec.toFixed(2)} s</strong>
                              {ddaFrame.fps ? ` (${ddaFrame.fps.toFixed(1)} fps)` : ""}
                            </span>
                            {" • "}w_eff = {result.display.w_eff} •{" "}
                            {digital ? "SDD" : "SFD"} = {form.sfd} mm
                          </>
                        )
                      ) : (
                        `w_eff = ${result.display.w_eff} • ${digital ? "SDD" : "SFD"} = ${form.sfd} mm • F = ${form.base_multiplier}×`
                      )}
                      {result.display.total_joint_time && (
                        ` • ⏱️ ${t("total_joint_time").replace(/:\s*$/, "")}: ${result.display.total_joint_time}`
                      )}
                    </div>
                  )}
                </div>
                <div className="hero-right">
                  <div className="hero-value" data-testid="output-calc_time">
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
            {digital && ddaFrame && (
              <div className="dda-integration-card" data-testid="dda-integration-card">
                <div className="dda-card-header">
                  <span className="dda-card-title">
                    🎞️ {lang === "tr" ? "DDA Kare & Doz Entegrasyonu (ASTM E2698 / ISO 17636-2)" : "DDA Frame & Dose Integration (ASTM E2698 / ISO 17636-2)"}
                  </span>
                  {ddaFrame.panel_class && (
                    <span className="dda-panel-badge">{ddaFrame.panel_class}</span>
                  )}
                </div>
                <div className="dda-metrics-grid">
                  <div className="dda-metric-box">
                    <span className="dda-metric-label">{lang === "tr" ? "Kare Sayısı" : "Frame Count"}</span>
                    <span className="dda-metric-value">{ddaFrame.n_frames}</span>
                    <span className="dda-metric-sub">{lang === "tr" ? "kare (ortalamalı)" : "frames (averaged)"}</span>
                  </div>
                  <div className="dda-metric-box">
                    <span className="dda-metric-label">{lang === "tr" ? "Kare Süresi" : "Frame Time"}</span>
                    <span className="dda-metric-value">{ddaFrame.t_frame_sec.toFixed(2)} sn</span>
                    <span className="dda-metric-sub">{(ddaFrame.t_frame_ms ?? (ddaFrame.t_frame_sec * 1000)).toFixed(0)} ms</span>
                  </div>
                  <div className="dda-metric-box">
                    <span className="dda-metric-label">{lang === "tr" ? "Çekim Hızı" : "Frame Rate"}</span>
                    <span className="dda-metric-value">{(ddaFrame.fps ?? (1 / ddaFrame.t_frame_sec)).toFixed(1)}</span>
                    <span className="dda-metric-sub">fps (Hz)</span>
                  </div>
                  <div className="dda-metric-box">
                    <span className="dda-metric-label">{lang === "tr" ? "Hedef ADC Doyumu" : "Target ADC Level"}</span>
                    <span className="dda-metric-value">%{ddaFrame.target_gray_pct}</span>
                    <span className="dda-metric-sub">~{ddaFrame.target_adu_16bit.toLocaleString()} ADU</span>
                  </div>
                  {ddaFrame.total_dose_ugy !== undefined && (
                    <div className="dda-metric-box">
                      <span className="dda-metric-label">{lang === "tr" ? "Dedektör Dozu" : "Detector Dose"}</span>
                      <span className="dda-metric-value">
                        {ddaFrame.total_dose_ugy >= 1000
                          ? `${(ddaFrame.total_dose_ugy / 1000).toFixed(2)} mGy`
                          : `${ddaFrame.total_dose_ugy.toFixed(1)} µGy`}
                      </span>
                      <span className="dda-metric-sub">{ddaFrame.dose_rate_ugy_s ? `${ddaFrame.dose_rate_ugy_s.toFixed(1)} µGy/s` : ""}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            <OutputsPanel
              t={t}
              result={result}
              strings={strings}
              digital={digital}
              hiddenOutputs={hiddenOutputs}
            />
            <CompliancePanel t={t} error={error} compliance={compliance} />
          </div>

          <div className="column warnings">
            <SketchTabsPanel
              sketchTab={sketchTab}
              setSketchTab={setSketchTab}
              result={result}
              form={form}
              digital={digital}
              theme={theme}
              lang={lang}
              t={t}
              exposuresProvenance={exposuresProvenance}
              exposuresProvenanceText={exposuresProvenanceText}
            />

            <WarningsPanel t={t} warnings={result?.warnings ?? []} />

            <DefectPanel
              t={t}
              defect={defect}
              setDefect={setDefect}
              setDefectActive={setDefectActive}
              defectResult={defectResult}
              runDefect={runDefect}
              wallT={form.t}
              lang={lang}
            />
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
        {showAbout && (
          <AboutModal
            t={t}
            currentVersion={pyClient.version ?? FALLBACK_VERSION}
            onClose={() => setShowAbout(false)}
          />
        )}
        {showUpdates && (
          <UpdateModal
            t={t}
            currentVersion={pyClient.version ?? FALLBACK_VERSION}
            onClose={() => setShowUpdates(false)}
          />
        )}
        <PageScrollbar />
      </div>
    </UnitContext.Provider>
  );
}

