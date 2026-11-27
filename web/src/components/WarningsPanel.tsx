import { memo } from "react";
import { Group } from "../components";

interface WarningsPanelProps {
  t: (key: string, ...args: unknown[]) => string;
  warnings: string[];
}

export const WarningsPanel = memo(function WarningsPanel({
  t,
  warnings,
}: WarningsPanelProps) {
  const title =
    warnings.length > 0 ? `${t("warnings")} (${warnings.length})` : t("warnings");
  return (
    <Group
      key={warnings.length > 0 ? "has-warnings" : "no-warnings"}
      title={title}
      className={warnings.length > 0 ? "warnings-active" : undefined}
      open={warnings.length > 0}
    >
      {warnings.length ? (
        <ul className="warning-list" role="alert">
          {warnings.map((warning, index) => (
            <li key={index}>{warning}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{t("no_warnings")}</p>
      )}
    </Group>
  );
});
