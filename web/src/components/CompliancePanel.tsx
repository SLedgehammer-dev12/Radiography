import { memo } from "react";
import { Group } from "../components";
import type { ComplianceResult } from "../types";

interface CompliancePanelProps {
  t: (key: string, ...args: unknown[]) => string;
  error: string | null;
  compliance: ComplianceResult | null;
  isLvl3Active?: boolean;
  lang?: string;
}

export const CompliancePanel = memo(function CompliancePanel({
  t,
  error,
  compliance,
  isLvl3Active = false,
  lang = "tr",
}: CompliancePanelProps) {
  return (
    <Group title={t("procedure_section")}>
      {isLvl3Active && (
        <div className="lvl3-audit-banner" role="status">
          <strong>L3</strong>
          <span>
            {lang === "tr"
              ? "Level 3 standart sapma yetkisi aktif — PDF raporuna işlenecek."
              : "Level 3 standard deviation active — will be recorded on PDF report."}
          </span>
        </div>
      )}
      {error ? (
        <div className="badge non-compliant" role="alert">
          ⚠ {error}
        </div>
      ) : !compliance ? (
        <p className="muted">Hesaplanıyor… / Calculating…</p>
      ) : (
        <>
          <div
            className={
              compliance.is_compliant
                ? "badge compliant"
                : "badge non-compliant"
            }
          >
            {compliance.is_compliant ? t("compliant") : t("non_compliant")}
          </div>
          <ul className="check-list">
            {compliance.checks.map((check) => (
              <li key={check.name} className={check.status ? "ok" : "fail"}>
                {check.status ? "✓" : "✗"} {check.details}
              </li>
            ))}
            {compliance.activity_warning && (
              <li className="warn">⚠ {compliance.activity_warning}</li>
            )}
          </ul>
        </>
      )}
    </Group>
  );
});
