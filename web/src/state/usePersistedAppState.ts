import { useCallback, useEffect, useState } from "react";

import {
  DEFAULT_FORM,
  DEFAULT_LVL3,
  type FormState,
  type Lvl3Settings,
} from "../types";
import { DEFAULT_BASE_E_BY_SOURCE, getActiveChartKeys } from "./presets";

const STORAGE_KEY = "radiography_web_state_v1";

export type AppTheme = "dark" | "light" | "outdoor";

interface PersistedState {
  form?: FormState;
  lvl3?: Lvl3Settings;
  lang?: string;
  theme?: AppTheme;
  reportInfo?: Record<string, string>;
}

const NULLABLE_NUMBER_KEYS = new Set<keyof FormState>([
  "b_object",
  "f_source",
  "panel_width",
  "panel_height",
  "app_time",
]);

const NULLABLE_STRING_KEYS = new Set<keyof FormState>(["std_figure", "user_geometry"]);

function parseUrlSetup(): Partial<FormState> | undefined {
  try {
    const raw = new URLSearchParams(window.location.search).get("setup");
    if (!raw || raw.length > 4096) return undefined;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return undefined;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(DEFAULT_FORM) as (keyof FormState)[]) {
      if (!Object.prototype.hasOwnProperty.call(parsed, key)) continue;
      const val = (parsed as Record<string, unknown>)[key];
      const defVal = DEFAULT_FORM[key];
      if (val === null && (NULLABLE_NUMBER_KEYS.has(key) || NULLABLE_STRING_KEYS.has(key))) {
        out[key] = null;
      } else if (typeof defVal === "number" || NULLABLE_NUMBER_KEYS.has(key)) {
        if (typeof val === "number" && Number.isFinite(val)) out[key] = val;
      } else if (typeof defVal === "boolean" && typeof val === "boolean") {
        out[key] = val;
      } else if (
        (typeof defVal === "string" || NULLABLE_STRING_KEYS.has(key)) &&
        typeof val === "string" &&
        val.length <= 64
      ) {
        out[key] = val;
      }
    }
    window.history.replaceState({}, "", window.location.pathname);
    return out as Partial<FormState>;
  } catch {
    return undefined;
  }
}

export function buildShareUrl(form: FormState): string {
  const delta: Record<string, unknown> = {};
  for (const key of Object.keys(DEFAULT_FORM) as (keyof FormState)[]) {
    if (form[key] !== DEFAULT_FORM[key]) {
      delta[key] = form[key];
    }
  }
  const url = new URL(window.location.origin + window.location.pathname);
  url.searchParams.set("setup", JSON.stringify(delta));
  return url.toString();
}

function loadPersisted(): PersistedState {
  const urlSetup = parseUrlSetup();
  let parsed: PersistedState = {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const candidate = JSON.parse(raw);
      if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) {
        parsed = candidate as PersistedState;
      }
    }
  } catch {
    parsed = {};
  }
  if (urlSetup) {
    parsed.form = { ...DEFAULT_FORM, ...urlSetup };
  }
  try {
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
      const validCharts = getActiveChartKeys(
        parsed.form.tech ?? "analog",
        parsed.form.detector_type ?? "cr_standard",
        parsed.form.source ?? "x_ray",
      );
      if (parsed.form.chart_source && !validCharts.includes(parsed.form.chart_source)) {
        parsed.form.chart_source = validCharts[0] ?? "model";
      }
    }
    if (parsed.theme && !["dark", "light", "outdoor"].includes(parsed.theme)) {
      parsed.theme = "dark";
    }
    return parsed;
  } catch {
    return urlSetup ? { form: { ...DEFAULT_FORM, ...urlSetup } } : {};
  }
}

/** Owns the persisted app state (form/lvl3/lang/theme/reportInfo) + localStorage. */
export function usePersistedAppState() {
  const [persisted] = useState(loadPersisted);
  const [form, setForm] = useState<FormState>({
    ...DEFAULT_FORM,
    ...(persisted.form ?? {}),
  });
  const [lvl3, setLvl3] = useState<Lvl3Settings>(persisted.lvl3 ?? DEFAULT_LVL3);
  const [lang, setLang] = useState<string>(persisted.lang ?? "tr");
  const [theme, setTheme] = useState<AppTheme>(persisted.theme ?? "dark");
  const [reportInfo, setReportInfo] = useState<Record<string, string>>(
    persisted.reportInfo ?? {},
  );

  const patch = useCallback(
    <K extends keyof FormState>(key: K, value: FormState[K]) =>
      setForm((previous) => ({ ...previous, [key]: value })),
    [],
  );

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

  return {
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
  };
}
