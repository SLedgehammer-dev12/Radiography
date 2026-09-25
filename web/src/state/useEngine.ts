import { useEffect, useRef, useState } from "react";

import { pyClient } from "../pyodide/client";
import type {
  ComplianceResult,
  EngineResult,
  FormState,
  Lvl3Settings,
} from "../types";

export interface EngineState {
  result: EngineResult | null;
  compliance: ComplianceResult | null;
  error: string | null;
  busy: boolean;
  ready: boolean;
}

export function useEngine(
  form: FormState,
  lvl3: Lvl3Settings,
  lang: string,
): EngineState {
  const [result, setResult] = useState<EngineResult | null>(null);
  const [compliance, setCompliance] = useState<ComplianceResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(pyClient.version !== null);
  const sequence = useRef(0);

  useEffect(() => {
    const unsubscribe = pyClient.onStatus((stage) => setReady(stage === "ready"));
    return () => {
      unsubscribe();
    };
  }, []);

  const formKey = JSON.stringify(form);
  const lvl3Key = JSON.stringify(lvl3);

  useEffect(() => {
    if (!ready) return;
    const current = ++sequence.current;
    setBusy(true);
    const timer = setTimeout(async () => {
      try {
        const calculated = await pyClient.request<EngineResult>("calculate", {
          form,
          lvl3,
          lang,
        });
        if (sequence.current !== current) return;
        setResult(calculated);
        const complianceResult = await pyClient.request<ComplianceResult>(
          "compliance",
          { form, calculated: calculated.calculated, lvl3, lang },
        );
        if (sequence.current !== current) return;
        setCompliance(complianceResult);
        setError(null);
      } catch (caught) {
        if (sequence.current === current) setError(String(caught));
      } finally {
        if (sequence.current === current) setBusy(false);
      }
    }, 80);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, formKey, lvl3Key, lang]);

  return { result, compliance, error, busy, ready };
}
