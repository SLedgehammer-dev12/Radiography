import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  CheckField,
  DurationSliderField,
  Group,
  LengthField,
  LengthSliderField,
  NumberField,
  PageScrollbar,
  RadioGroup,
  SelectField,
  SliderField,
} from "./components";
import { DefectPanel } from "./components/DefectPanel";
import { HeroSummaryPanel } from "./components/HeroSummaryPanel";
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
  CHART_TO_FILM_CLASS,
  DEFAULT_BASE_E_BY_SOURCE,
  DETECTORS as DETECTOR_KEYS,
  FILM_CHART_BRANDS,
  FILM_CLASS_LABELS,
  FILM_SIZES as FILM_PRESETS,
  GEOMETRIES,
  MATERIALS,
  NAMED_PRESETS,
  SOURCES,
  desktopStateToForm,
  downloadCsv,
  downloadJson,
  formToDesktopState,
  getActiveChartKeys,
  parseCsv,
  resolveFilmChartForClass,
  selectedOdKey,
} from "./state/presets";
import { useEngine } from "./state/useEngine";
import { useDefect } from "./state/useDefect";
import { usePersistedAppState } from "./state/usePersistedAppState";
import {
  DEFAULT_FORM,
  DEFAULT_LVL3,
  UnitContext,
  type FormState,
  type Lvl3Settings,
  type PipeData,
} from "./types";
import "./App.css";

const DETECTOR_TKEYS = [
  "detector_cr_std",
  "detector_cr_hires",
  "detector_dda_si",
  "detector_dda_se",
  "detector_dda_gdos",
  "detector_cr_ips1_uhd",
  "detector_cr_fast",
  "detector_dda_si_hires",
  "detector_dda_gdos_he",
  "detector_dda_cmos",
];
const CHART_OPTION_META: Record<string, { labelKey?: string; label?: string }> = {
  model: { labelKey: "chart_model" },
  // Carestream (Kodak Industrex)
  DR50: { label: "Carestream DR50 (C1)" },
  M100: { label: "Carestream M100 (C2)" },
  MX125: { label: "Carestream MX125 (C3)" },
  T200: { label: "Carestream T200 (C4)" },
  AA400: { label: "Carestream AA400 (C5)" },
  HS800: { label: "Carestream HS800 (C6)" },
  // Agfa Structurix (Waygate Technologies)
  D2: { label: "Agfa Structurix D2 (C1)" },
  D3: { label: "Agfa Structurix D3 (C2)" },
  D4: { label: "Agfa Structurix D4 (C3)" },
  D5: { label: "Agfa Structurix D5 (C4)" },
  D7: { label: "Agfa Structurix D7 (C5)" },
  D8: { label: "Agfa Structurix D8 (C6)" },
  // Fujifilm IX (Industrial X-Ray)
  IX25: { label: "Fujifilm IX25 (C1)" },
  IX50: { label: "Fujifilm IX50 (C2)" },
  IX80: { label: "Fujifilm IX80 (C3)" },
  IX100: { label: "Fujifilm IX100 (C4)" },
  IX150: { label: "Fujifilm IX150 (C5)" },
  // Foma Fomadux
  R2: { label: "Foma Fomadux R2 (C1)" },
  R4: { label: "Foma Fomadux R4 (C3)" },
  R5: { label: "Foma Fomadux R5 (C4)" },
  R7: { label: "Foma Fomadux R7 (C5)" },
  R8: { label: "Foma Fomadux R8 (C6)" },
  type_x: { labelKey: "chart_type_x" },
  cr_ips_chart: { labelKey: "chart_cr_ips" },
  dda_frame_method: { labelKey: "chart_dda_frame" },
  dda_panel_chart: { labelKey: "chart_dda_panel" },
  digital_xray_chart: { labelKey: "chart_digital_xray" },
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
  const [notice, setNotice] = useState<
    { text: string; kind: "info" | "success" | "error" } | null
  >(null);
  const notify = useCallback(
    (text: string, kind: "info" | "success" | "error" = "info") =>
      setNotice({ text, kind }),
    [],
  );
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

  // Auto-dismiss the toast: errors linger longer than success/info.
  useEffect(() => {
    if (!notice) return;
    const handle = setTimeout(
      () => setNotice(null),
      notice.kind === "error" ? 8000 : 4500,
    );
    return () => clearTimeout(handle);
  }, [notice]);

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
  } = useDefect({ form, lang, ready, onError: (message) => notify(message, "error") });

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
    notify(
      lang === "tr"
        ? "Hesaplanan hedef değerler uygulanan pozlama alanlarına aktarıldı."
        : "Calculated target values synced to applied exposure fields.",
      "success",
    );
  };

  const resetForm = () => {
    setForm({ ...DEFAULT_FORM });
    setLvl3(DEFAULT_LVL3);
    setReportInfo({});
    notify(
      lang === "tr" ? "Form varsayılana sıfırlandı." : "Form reset to defaults.",
      "success",
    );
  };

  const applyNamedPreset = useCallback(
    (name: string) => {
      const preset = NAMED_PRESETS[name];
      if (!preset) return;
      setForm((previous) => {
        const nextSource = preset.source ?? previous.source;
        const nextTech = preset.tech ?? previous.tech;
        const nextDetector = preset.detector_type ?? previous.detector_type;
        const next = {
          ...previous,
          ...preset,
          base_e:
            preset.base_e ??
            DEFAULT_BASE_E_BY_SOURCE[nextSource] ??
            previous.base_e,
        };
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
                : resolveFilmChartForClass(
                    next.film_class_used,
                    next.chart_source,
                  )
              : validCharts[0] ?? "model";
        }
        return next;
      });
      notify(
        lang === "tr"
          ? `"${name}" şablonu uygulandı.`
          : `Applied "${name}" preset.`,
        "success",
      );
    },
    [lang, notify, setForm],
  );

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
    if (pdfBusy) return;
    if (!result) {
      notify("Hesaplama hazır değil / Calculation not ready", "error");
      return;
    }
    setPdfBusy(true);
    setNotice(null);
    try {
      await pyClient.request("pdf:prepare");
      const calculated = result.calculated as Record<string, unknown>;
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
        lvl3_active: isLvl3Active,
        lvl3,
        sfd_comp_val: calculated.sfd_comp_target ?? null,
        lang,
        report_info: reportInfo,
        sketch_png_base64: sketchPng,
        standard_png_base64: standardPng,
        filename: `RT_Inspection_Report_${stamp}.pdf`,
      });
      downloadBase64(data.pdf_base64, data.filename);
      notify(t("report_saved", data.filename), "success");
    } catch (caught) {
      notify(String(caught), "error");
    } finally {
      setPdfBusy(false);
    }
  };

  // Keyboard shortcuts: Ctrl/Cmd+Enter exports the PDF, Ctrl/Cmd+S saves the
  // current form as a preset (preventDefault stops the browser save dialog).
  const shortcutRef = useRef({ exportPdf, exportPreset, ready });
  shortcutRef.current = { exportPdf, exportPreset, ready };
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.repeat) return;
      if (!shortcutRef.current.ready || document.querySelector(".modal-backdrop")) return;
      if (event.key === "Enter") {
        event.preventDefault();
        void shortcutRef.current.exportPdf();
      } else if (event.key.toLowerCase() === "s") {
        event.preventDefault();
        shortcutRef.current.exportPreset();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  if (!ready) {
    return (
      <div className="boot-screen">
        <h1>Radiography</h1>
        <p>{t("app_title")}</p>
        {!bootError && <div className="spinner" />}
        <p className="boot-note" role={bootError ? "alert" : undefined}>
          {bootError
            ? `Hata / Error: ${bootError}`
            : "Python çekirdeği (Pyodide) yükleniyor… / Loading the Python core…"}
        </p>
      </div>
    );
  }

  const working = busy || pdfBusy;
  const baseEUnit = xray ? "mA·min/m²" : "Ci·min/m²";
  const activityFactor = activityUnit === "GBq" ? 37 : 1;
  const bedSuggested = result?.values?.bed_auto_suggested as number | undefined;
  const wireTargetNo = result?.values?.wire_no as number | undefined;
  const duplexTargetNo = result?.values?.duplex_no as number | undefined;

  return (
    <UnitContext.Provider value={{ inch: unitInch }}>
      <div className="app">
        <div className="app-header">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark">RT</div>
            <h1 className="title">{t("app_title")}</h1>
          </div>
          <div className="topbar-actions">
            <span className={working ? "status busy" : "status"}>
              {working ? "…" : error ? "!" : "OK"}
            </span>
            <button
              type="button"
              className="topbar-action"
              data-testid="topbar-sync"
              onClick={syncAllCalculated}
              disabled={!result}
              title={
                lang === "tr"
                  ? "Hesaplanan asgari değerleri (SFD, poz sayısı, süre, tel) uygulanan alanlara aktar"
                  : "Sync calculated targets (SFD, exposures, time, wire) to applied fields"
              }
            >
              ⚡ {lang === "tr" ? "Uygula" : "Sync"}
            </button>
            <button
              type="button"
              className="topbar-action"
              onClick={resetForm}
              title={lang === "tr" ? "Formu sıfırla" : "Reset form"}
            >
              ⟲ {lang === "tr" ? "Sıfırla" : "Reset"}
            </button>
            <button
              type="button"
              className="topbar-action primary"
              onClick={exportPdf}
              disabled={pdfBusy || !result}
              title={`${t("export_pdf")} (Ctrl+Enter)`}
            >
              📄 {pdfBusy ? "…" : t("export_pdf")}
            </button>
          </div>
        </header>
        {notice && (
          <div
            className={`toast toast-${notice.kind}`}
            role={notice.kind === "error" ? "alert" : "status"}
          >
            <span className="toast-text">{notice.text}</span>
            <button
              type="button"
              className="toast-close"
              aria-label="Kapat / Close"
              onClick={() => setNotice(null)}
            >
              ✕
            </button>
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
                  disabled={pdfBusy || !result}
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
                      if (event.target.value) {
                        applyNamedPreset(event.target.value);
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
                notify(lang === "tr" ? "Şablon yüklendi." : "Preset loaded.", "success");
              } catch (caught) {
                notify(String(caught), "error");
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
                notify(lang === "tr" ? "Proje içe aktarıldı." : "Project imported.", "success");
              } catch (caught) {
                notify(String(caught), "error");
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
                notify(lang === "tr" ? "CSV içe aktarıldı." : "CSV imported.", "success");
              } catch (caught) {
                notify(String(caught), "error");
              }
              event.target.value = "";
            }}
          />
        </div>
        <div
          className={`app-progress${working ? " active" : ""}`}
          role="progressbar"
          aria-label="Hesaplanıyor / Calculating"
          aria-hidden={!working}
        />
        </div>

        <main className="layout">
          <div className="column inputs">
            <div
              className="preset-chips-bar"
              role="toolbar"
              aria-label={lang === "tr" ? "Hızlı Hazır Şablonlar" : "Quick Presets"}
            >
              <span className="preset-chips-label">
                ⚡ {lang === "tr" ? "Hazır Setuplar:" : "Presets:"}
              </span>
              {Object.keys(NAMED_PRESETS).map((name) => (
                <button
                  key={name}
                  type="button"
                  className="preset-chip"
                  onClick={() => applyNamedPreset(name)}
                  title={`${lang === "tr" ? "Şablonu yükle" : "Load preset"}: ${name}`}
                >
                  {name}
                </button>
              ))}
            </div>

            <Group title={t("pipe_geometry_section")}>
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
            </Group>

            <Group title={t("rad_tech_section")}>
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
                    setForm((previous) => {
                      const validCharts = getActiveChartKeys(
                        previous.tech,
                        previous.detector_type,
                        newSource,
                      );
                      let nextChart = previous.chart_source;
                      if (!validCharts.includes(nextChart)) {
                        if (previous.tech !== "digital") {
                          nextChart =
                            newSource === "x_ray"
                              ? "type_x"
                              : resolveFilmChartForClass(
                                  previous.film_class_used,
                                  previous.chart_source,
                                );
                        } else if (nextChart === "digital_xray_chart") {
                          nextChart = previous.detector_type.startsWith("dda_")
                            ? "dda_panel_chart"
                            : "cr_ips_chart";
                        } else if (nextChart === "cr_ips_chart") {
                          nextChart = "digital_xray_chart";
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
              {digital && (
                <div className="field-row-2">
                  <LengthField
                    label={t("panel_width")}
                    value={form.panel_width}
                    min={1}
                    max={2000}
                    onChange={(value) => patch("panel_width", value ?? 200)}
                  />
                  <LengthField
                    label={t("panel_height")}
                    value={form.panel_height}
                    min={1}
                    max={2000}
                    onChange={(value) => patch("panel_height", value ?? 200)}
                  />
                </div>
              )}
              {dwdi &&
                result?.values?.dwdi_coverage &&
                !result.values.dwdi_coverage.is_sufficient && (
                  <div
                    className="field-help warn"
                    style={{
                      color: "var(--color-warn, #d97706)",
                      fontWeight: 600,
                      marginTop: "6px",
                      padding: "6px 10px",
                      background: "rgba(217, 119, 6, 0.12)",
                      borderRadius: "4px",
                      border: "1px solid rgba(217, 119, 6, 0.3)",
                      lineHeight: 1.35,
                    }}
                  >
                    ⚠ {lang === "tr"
                      ? `Girilen ${analog ? "film" : "panel"} boyutu (${result.values.dwdi_coverage.available_across} mm), borunun büyütülmüş izdüşümünü (${result.values.dwdi_coverage.w_min_req.toFixed(1)} mm) kurtarmıyor! Kesilme olmaması için en az ${result.values.dwdi_coverage.w_min_req.toFixed(1)} mm gereklidir.`
                      : `Entered ${analog ? "film" : "panel"} size (${result.values.dwdi_coverage.available_across} mm) does not cover projected pipe image (${result.values.dwdi_coverage.w_min_req.toFixed(1)} mm)! Minimum ${result.values.dwdi_coverage.w_min_req.toFixed(1)} mm required.`}
                  </div>
                )}
            </Group>

            <Group title={t("standards_iqi_section")}>
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
                    return {
                      value: key,
                      label: t("chart_digital_model"),
                      group: lang === "tr" ? "Hesaplama Modeli" : "Calculation Model",
                    };
                  }
                  const meta = CHART_OPTION_META[key];
                  const label = meta?.labelKey ? t(meta.labelKey) : (meta?.label ?? key);
                  let group: string | undefined;
                  if (key in FILM_CHART_BRANDS) {
                    group = FILM_CHART_BRANDS[key];
                  } else if (key === "model" || key === "type_x" || key === "dda_frame_method") {
                    group = lang === "tr" ? "Hesaplama Modeli" : "Calculation Model";
                  } else if (
                    key === "cr_ips_chart" ||
                    key === "dda_panel_chart" ||
                    key === "digital_xray_chart"
                  ) {
                    group = lang === "tr" ? "Standart / Abak Yöntemi" : "Standard / Chart Method";
                  }
                  return { value: key, label, group };
                })}
                onChange={(value) => {
                  patch("chart_source", value);
                  const mappedClass = CHART_TO_FILM_CLASS[value];
                  if (analog && mappedClass) {
                    patch("film_class_used", mappedClass);
                  }
                }}
              />
              {analog && (
                <div className="field-row-2">
                  <SelectField
                    label={t("film_class_used")}
                    value={form.film_class_used}
                    options={["C1", "C2", "C3", "C4", "C5", "C6"].map((value) => ({
                      value,
                      label: FILM_CLASS_LABELS[value] ?? value,
                    }))}
                    onChange={(value) => {
                      patch("film_class_used", value);
                      if (
                        form.source !== "x_ray" &&
                        form.chart_source in CHART_TO_FILM_CLASS
                      ) {
                        patch(
                          "chart_source",
                          resolveFilmChartForClass(value, form.chart_source),
                        );
                      }
                    }}
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
                      group: value.startsWith("cr_")
                        ? (lang === "tr"
                            ? "CR — Fosfor Görüntüleme Plakaları (ISO 16371-1)"
                            : "CR — Phosphor Imaging Plates (ISO 16371-1)")
                        : (lang === "tr"
                            ? "DDA — Düz Panel Dedektörler (ASTM E2698 / E2736)"
                            : "DDA — Flat Panel Detectors (ASTM E2698 / E2736)"),
                    }))}
                    onChange={(value) => {
                      const validCharts = getActiveChartKeys(form.tech, value, form.source);
                      patch("detector_type", value);
                      if (!validCharts.includes(form.chart_source)) {
                        if (
                          form.chart_source === "cr_ips_chart" &&
                          validCharts.includes("dda_panel_chart")
                        ) {
                          patch("chart_source", "dda_panel_chart");
                        } else if (
                          form.chart_source === "dda_panel_chart" &&
                          validCharts.includes("cr_ips_chart")
                        ) {
                          patch("chart_source", "cr_ips_chart");
                        } else {
                          patch("chart_source", validCharts[0] ?? "model");
                        }
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
                      min={1}
                      max={2000}
                      onChange={(value) => patch("panel_width", value ?? 200)}
                    />
                    <LengthField
                      label={t("panel_height")}
                      value={form.panel_height}
                      min={1}
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
            <HeroSummaryPanel
              result={result}
              compliance={compliance}
              form={form}
              lang={lang}
              t={t}
              onNotify={notify}
            />
            <OutputsPanel
              t={t}
              result={result}
              error={error}
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

