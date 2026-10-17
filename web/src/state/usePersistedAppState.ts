import { useCallback, useEffect, useState } from "react";

import {
  DEFAULT_FORM,
  DEFAULT_LVL3,
  type FormState,
  type Lvl3Settings,
} from "../types";
import { DEFAULT_BASE_E_BY_SOURCE, getActiveChartKeys } from "./presets";

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
      const validCharts = getActiveChartKeys(
        parsed.form.tech ?? "analog",
        parsed.form.detector_type ?? "cr_standard",
        parsed.form.source ?? "x_ray",
      );
      if (parsed.form.chart_source && !validCharts.includes(parsed.form.chart_source)) {
        parsed.form.chart_source = validCharts[0] ?? "model";
      }
    }
    return parsed;
  } catch {
    return {};
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
  const [theme, setTheme] = useState<"dark" | "light">(persisted.theme ?? "dark");
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
