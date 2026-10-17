import { Group } from "../components";

const REPORT_FIELDS: [string, string][] = [
  ["report_no", "report_no"],
  ["report_rev", "report_rev"],
  ["project", "project"],
  ["welder_id", "welder_id"],
  ["joint_id", "joint_id"],
  ["wps_pqr", "wps_pqr"],
  ["procedure_no", "procedure_no"],
  ["device_serial", "device_serial"],
  ["calibration_date", "calibration_date"],
  ["personnel", "personnel"],
  ["lvl2_name", "lvl2_name"],
  ["lvl2_cert", "lvl2_cert"],
  ["lvl3_name", "lvl3_name"],
  ["lvl3_cert", "lvl3_cert"],
];

interface ReportInfoPanelProps {
  t: (key: string, ...args: unknown[]) => string;
  reportInfo: Record<string, string>;
  patchReport: (key: string, value: string) => void;
}

export function ReportInfoPanel({
  t,
  reportInfo,
  patchReport,
}: ReportInfoPanelProps) {
  return (
    <Group title={t("report_info_section")} open={false}>
      <div className="field-row-2">
        {REPORT_FIELDS.map(([key, labelKey]) => (
          <label className="field" key={key}>
            <span className="field-label">{t(labelKey)}</span>
            <input
              className="field-input"
              type="text"
              value={reportInfo[key] ?? ""}
              onChange={(event) => patchReport(key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </Group>
  );
}
