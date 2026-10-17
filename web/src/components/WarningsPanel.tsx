import { Group } from "../components";

interface WarningsPanelProps {
  t: (key: string, ...args: unknown[]) => string;
  warnings: string[];
}

export function WarningsPanel({ t, warnings }: WarningsPanelProps) {
  return (
    <Group title={t("warnings")}>
      {warnings.length ? (
        <ul className="warning-list">
          {warnings.map((warning, index) => (
            <li key={index}>{warning}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">No active warnings.</p>
      )}
    </Group>
  );
}
