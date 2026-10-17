import { Group, OutputRow } from "../components";
import type { EngineResult } from "../types";

const OUTPUT_KEYS = [
  "w_nom",
  "w_eff",
  "u_max",
  "f_min",
  "f_min_asme",
  "sfd_min",
  "ug",
  "req_exposures",
  "exposures_panel",
  "exposures_applied",
  "exposures_check",
  "single_wire_iqi",
  "duplex_iqi",
  "asme_iqi",
  "quality_target",
  "calc_time",
  "total_joint_time",
  "detector_quality",
  "barrier_distance",
  "filter_recommendation",
];

interface OutputsPanelProps {
  t: (key: string, ...args: unknown[]) => string;
  result: EngineResult | null;
  strings: Record<string, string>;
  digital: boolean;
  hiddenOutputs: Set<string>;
}

export function OutputsPanel({
  t,
  result,
  strings,
  digital,
  hiddenOutputs,
}: OutputsPanelProps) {
  const outputLabel = (key: string): string => {
    if (key === "sfd_min") return t(digital ? "sfd_min" : "sfd_min_analog");
    if (key === "exposures_panel") {
      return t(digital ? "exposures_panel" : "exposures_film");
    }
    if (key === "quality_target") {
      return t(digital ? "target_snr" : "optical_density");
    }
    if (key === "detector_quality") {
      return t(digital ? "detector_quality" : "film_class_req");
    }
    return t(key);
  };

  return (
    <Group title={t("outputs")}>
      {result ? (
        OUTPUT_KEYS.filter((key) => !hiddenOutputs.has(key)).map((key) => (
          <OutputRow
            key={key}
            testId={`output-${key}`}
            label={outputLabel(key)}
            value={result?.display[key] ?? "-"}
            tooltip={(() => {
              const dynamicProv = result?.values?.[`${key}_provenance_text`] as
                | string
                | undefined;
              if (dynamicProv) {
                const base = strings[`tt_${key}`] ?? "";
                return `${base}\n\n${dynamicProv}`.trim();
              }
              if (key === "exposures_panel") {
                return (
                  strings[digital ? "tt_exposures_panel" : "tt_exposures_film"] ?? ""
                );
              }
              return strings[`tt_${key}`];
            })()}
          />
        ))
      ) : (
        <p className="muted">Hesaplanıyor… / Calculating…</p>
      )}
    </Group>
  );
}
