import { useCallback, useEffect, useState } from "react";

import type { EngineResult, FormState } from "../types";

export interface CalculationHistoryEntry {
  id: string;
  timestamp: number;
  form: FormState;
  summary: {
    od: number;
    t: number;
    material: string;
    source: string;
    tech: string;
    geometry: string;
    sfd: number;
    exposures: number;
    exposureTimeSec: number;
    fMin: number;
    governingStd: string;
  };
}

const STORAGE_KEY = "radiography_calc_history_v1";
const MAX_ENTRIES = 5;

function loadHistory(): CalculationHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed
        .filter(
          (item): item is CalculationHistoryEntry =>
            Boolean(
              item &&
                typeof item === "object" &&
                item.id &&
                item.form &&
                typeof item.form === "object" &&
                item.summary &&
                typeof item.summary === "object",
            ),
        )
        .slice(0, MAX_ENTRIES);
    }
  } catch {
    /* ignore corrupted storage */
  }
  return [];
}

export function useCalculationHistory(
  form: FormState,
  result: EngineResult | null,
  busy: boolean,
) {
  const [history, setHistory] = useState<CalculationHistoryEntry[]>(loadHistory);

  useEffect(() => {
    if (!result || busy || !result.calculated) return;

    const values = result.values;
    const fMin = Number(values?.f_min ?? 0);
    const exposures = Number(values?.n_required ?? 1);
    const exposureTimeSec = Number(values?.calc_time ?? 0);
    const governingStd = String(values?.standard ?? form.standard ?? "ISO").toUpperCase();

    const timer = setTimeout(() => {
      setHistory((previous) => {
        const latest = previous[0];
        const isSameForm =
          latest &&
          (Object.keys(form) as (keyof FormState)[]).every(
            (k) => form[k] === latest.form[k],
          );
        if (isSameForm) return previous;

        const src = form.source ?? "x_ray";
        const sourceLabel =
          src === "x_ray"
            ? `${form.app_kv || 120} kV`
            : `${src.replace("isotope_", "")} (${form.app_activity || 40} Ci)`;

        const entry: CalculationHistoryEntry = {
          id: `${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
          timestamp: Date.now(),
          form: { ...form },
          summary: {
            od: form.od,
            t: form.t,
            material: form.material ?? "steel",
            source: sourceLabel,
            tech: form.tech,
            geometry: form.geometry,
            sfd: form.sfd,
            exposures,
            exposureTimeSec,
            fMin,
            governingStd,
          },
        };

        const updated = [
          entry,
          ...previous.filter(
            (item) =>
              item.id !== entry.id &&
              !(Object.keys(form) as (keyof FormState)[]).every(
                (k) => item.form[k] === form[k],
              ),
          ),
        ].slice(0, MAX_ENTRIES);

        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        } catch {
          /* storage full or unavailable */
        }
        return updated;
      });
    }, 60);

    return () => clearTimeout(timer);
  }, [result, busy, form]);

  const clearHistory = useCallback(() => {
    setHistory([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  return {
    history,
    clearHistory,
    historyCount: history.length,
  };
}
