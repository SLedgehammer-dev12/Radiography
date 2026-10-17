import type { Dispatch, SetStateAction } from "react";

import { Group, LengthField, SelectField } from "../components";
import type { DefectInput, DefectResult } from "../types";
import { DefectStripSvg } from "./SketchView";

const DEFECT_TYPES = [
  "defect_ip",
  "defect_if",
  "defect_ic",
  "defect_porosity",
  "defect_crack",
  "defect_slag",
  "defect_undercut",
  "defect_burn_through",
];
const DEFECT_STANDARDS = [
  { value: "api1104", labelKey: "defect_std_api1104" },
  { value: "iso5817", labelKey: "defect_std_iso5817" },
  { value: "b31_3", labelKey: "defect_std_b31_3" },
  { value: "viii", labelKey: "defect_std_viii" },
];

interface DefectPanelProps {
  t: (key: string, ...args: unknown[]) => string;
  defect: DefectInput;
  setDefect: Dispatch<SetStateAction<DefectInput>>;
  setDefectActive: Dispatch<SetStateAction<boolean>>;
  defectResult: DefectResult | null;
  runDefect: () => void;
  wallT: number;
  lang: string;
}

export function DefectPanel({
  t,
  defect,
  setDefect,
  setDefectActive,
  defectResult,
  runDefect,
  wallT,
  lang,
}: DefectPanelProps) {
  return (
    <Group title={t("defect_section")}>
      <div className="field-row-2">
        <SelectField
          label={t("defect_standard")}
          value={defect.standard}
          options={DEFECT_STANDARDS.map((option) => ({
            value: option.value,
            label: t(option.labelKey),
          }))}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({
              ...previous,
              standard: value as DefectInput["standard"],
            }));
          }}
        />
        <SelectField
          label={t("defect_type")}
          value={defect.type}
          options={DEFECT_TYPES.map((value) => ({
            value,
            label: t(value),
          }))}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({ ...previous, type: value }));
          }}
        />
      </div>
      {defect.standard === "iso5817" && (
        <SelectField
          label={t("quality_level")}
          value={defect.level ?? "C"}
          options={[
            { value: "B", label: "B" },
            { value: "C", label: "C" },
            { value: "D", label: "D" },
          ]}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({ ...previous, level: value }));
          }}
        />
      )}
      {defect.standard === "b31_3" && (
        <SelectField
          label={t("b31_service")}
          value={defect.service ?? "normal"}
          options={[
            { value: "normal", label: t("service_normal") },
            { value: "severe", label: t("service_severe") },
          ]}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({ ...previous, service: value }));
          }}
        />
      )}
      {defect.standard === "viii" && (
        <SelectField
          label={t("viii_mode")}
          value={defect.mode ?? "UW-51"}
          options={[
            { value: "UW-51", label: t("mode_uw51") },
            { value: "UW-52", label: t("mode_uw52") },
          ]}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({ ...previous, mode: value }));
          }}
        />
      )}
      <div className="field-row-2">
        <LengthField
          label={t("defect_length") || "Length (mm)"}
          value={defect.length}
          min={0}
          max={1000}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({ ...previous, length: value ?? 0 }));
          }}
        />
        <LengthField
          label={t("defect_width") || "Width/Depth (mm)"}
          value={defect.width}
          min={0}
          max={100}
          onChange={(value) => {
            setDefectActive(true);
            setDefect((previous) => ({ ...previous, width: value ?? 0 }));
          }}
        />
      </div>
      <LengthField
        label={t("accumulated_12in")}
        value={defect.accumulated}
        min={0}
        max={300}
        onChange={(value) => {
          setDefectActive(true);
          setDefect((previous) => ({
            ...previous,
            accumulated: value ?? 0,
          }));
        }}
      />
      <DefectStripSvg
        defectType={defect.type}
        lengthMm={defect.length}
        widthMm={defect.width}
        accumulatedMm={defect.accumulated}
        wallT={wallT}
        accepted={defectResult ? defectResult.status : null}
        lang={lang}
      />
      <button type="button" className="primary" onClick={runDefect}>
        {t("evaluate_defect") || "Evaluate"}
      </button>
      {defectResult && (
        <div
          className={
            defectResult.status
              ? "badge compliant"
              : "badge non-compliant"
          }
        >
          {defectResult.status ? t("result_accept") : t("result_reject")}
        </div>
      )}
      {defectResult && (
        <p className="muted defect-reason">{defectResult.result}</p>
      )}
    </Group>
  );
}
