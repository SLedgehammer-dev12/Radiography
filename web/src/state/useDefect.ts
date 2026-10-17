import { useEffect, useState } from "react";

import { pyClient } from "../pyodide/client";
import type { DefectInput, DefectResult, FormState } from "../types";

const DEFAULT_DEFECT: DefectInput = {
  standard: "api1104",
  type: "defect_porosity",
  length: 10,
  width: 1.5,
  accumulated: 15,
  level: "C",
  service: "normal",
  mode: "UW-51",
};

interface UseDefectArgs {
  form: FormState;
  lang: string;
  ready: boolean;
  onError: (message: string) => void;
}

/** Owns the defect-evaluation tab state and its reactive re-evaluation. */
export function useDefect({ form, lang, ready, onError }: UseDefectArgs) {
  const [defect, setDefect] = useState<DefectInput>(DEFAULT_DEFECT);
  const [defectResult, setDefectResult] = useState<DefectResult | null>(null);
  const [defectActive, setDefectActive] = useState(false);

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
      onError(String(caught));
    }
  };

  return {
    defect,
    setDefect,
    defectResult,
    setDefectResult,
    defectActive,
    setDefectActive,
    runDefect,
  };
}
