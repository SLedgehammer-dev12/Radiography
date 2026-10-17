import { Group } from "../components";
import type { ComplianceResult } from "../types";

interface CompliancePanelProps {
  t: (key: string, ...args: unknown[]) => string;
  error: string | null;
  compliance: ComplianceResult | null;
}

export function CompliancePanel({ t, error, compliance }: CompliancePanelProps) {
  return (
    <Group title={t("procedure_section")}>
      {error ? (
        <div className="badge non-compliant" role="alert">
          ⚠ {error}
        </div>
      ) : (
        <>
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
        </>
      )}
    </Group>
  );
}
