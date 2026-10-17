import { InfoTip } from "../components";
import { formatExposuresProvenance, type Translator } from "../i18n";
import type { EngineResult, ExposuresProvenance, FormState } from "../types";

interface HeroSummaryPanelProps {
  result: EngineResult | null;
  form: FormState;
  lang: string;
  t: Translator;
}

export function HeroSummaryPanel({
  result,
  form,
  lang,
  t,
}: HeroSummaryPanelProps) {
  const digital = form.tech === "digital";
  const isAsme = form.standard === "asme";

  // SFD_min / SDD_min provenance: which candidate (f_min+b, receptor
  // coverage or the DWSI physical floor) governs the value.
  const provenance = result?.values?.sfd_min_provenance as
    | {
        active: string;
        candidates: {
          key: string;
          value: number;
          formula_key: string;
          receptor?: "df" | "dd";
          f_min?: number;
          b?: number;
          l3_dw?: boolean;
          l3_central?: boolean;
        }[];
      }
    | undefined;
  const candidateLabel = (candidate: {
    key: string;
    receptor?: "df" | "dd";
  }): string => {
    if (candidate.key === "f_min_plus_b") return t("sfd_prov_f_min");
    if (candidate.key === "coverage") {
      return candidate.receptor === "dd"
        ? t("sfd_prov_coverage_panel")
        : t("sfd_prov_coverage_film");
    }
    return t("sfd_prov_dwsi_floor");
  };
  const provenanceText = provenance
    ? provenance.candidates
        .map(
          (candidate) =>
            `${candidateLabel(candidate)} = ${candidate.value.toFixed(1)} mm [${t(candidate.formula_key)}]`,
        )
        .join(" | ")
    : "";
  const provenanceSummary = provenance
    ? (() => {
        const active = provenance.candidates.find(
          (candidate) => candidate.key === provenance.active,
        );
        if (!active) return "";
        const level3 =
          active.l3_dw || active.l3_central ? ` — ${t("sfd_prov_l3")}` : "";
        return `${t("sfd_prov_active", candidateLabel(active))} ${active.value.toFixed(1)} mm [${t(active.formula_key)}]${level3}`;
      })()
    : "";

  const fMinProvenance = result?.values?.f_min_provenance as
    | {
        base: number;
        value: number;
        formula_key: string;
        l3_dw?: boolean;
        l3_central?: boolean;
      }
    | undefined;
  const fMinProvenanceText = (() => {
    if (!fMinProvenance) return "";
    let text = t("fmin_prov_base", fMinProvenance.base, t(fMinProvenance.formula_key));
    const reduced = fMinProvenance.l3_dw || fMinProvenance.l3_central;
    if (fMinProvenance.l3_dw) text += ` \u2192 ${t("fmin_prov_dw")}`;
    if (fMinProvenance.l3_central) text += ` \u2192 ${t("fmin_prov_central")}`;
    if (reduced) text += ` \u2192 ${t("fmin_prov_final", fMinProvenance.value)}`;
    return text;
  })();

  const exposuresProvenance = result?.values?.exposures_provenance as
    | ExposuresProvenance
    | undefined;
  const exposuresProvenanceText = formatExposuresProvenance(
    exposuresProvenance,
    t,
  );

  const exposureTimeProvenanceText =
    (result?.values?.exposure_time_provenance_text as string | undefined) ?? "";
  const expProv = result?.values?.exposure_time_provenance as
    | Record<string, unknown>
    | undefined;
  const ddaFrame = expProv?.dda_frame as
    | {
        n_frames: number;
        t_frame_sec: number;
        t_frame_ms?: number;
        fps?: number;
        total_acq_sec: number;
        target_gray_pct: number;
        target_adu_16bit: number;
        total_dose_ugy?: number;
        dose_rate_ugy_s?: number;
        snr_1frame: number;
        panel_class?: string;
      }
    | undefined;

  return (
    <>
      <div className="hero-grid">
        <div className="hero-card">
          <div className="hero-main">
            <div
              className="hero-label"
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <span>{t("calc_time").replace(/:\s*$/, "")}</span>
              {exposureTimeProvenanceText && (
                <InfoTip
                  text={exposureTimeProvenanceText}
                  title={t("calc_time").replace(/:\s*$/, "")}
                />
              )}
            </div>
            {result && (
              <div className="hero-sub">
                {ddaFrame ? (
                  lang === "tr" ? (
                    <>
                      <span className="hero-frame-highlight">
                        <strong>{ddaFrame.n_frames}</strong> kare ×{" "}
                        <strong>{ddaFrame.t_frame_sec.toFixed(2)} sn</strong>
                        {ddaFrame.fps ? ` (${ddaFrame.fps.toFixed(1)} fps)` : ""}
                      </span>
                      {" • "}w_eff = {result.display.w_eff} •{" "}
                      {digital ? "SDD" : "SFD"} = {form.sfd} mm
                    </>
                  ) : (
                    <>
                      <span className="hero-frame-highlight">
                        <strong>{ddaFrame.n_frames}</strong> frames ×{" "}
                        <strong>{ddaFrame.t_frame_sec.toFixed(2)} s</strong>
                        {ddaFrame.fps ? ` (${ddaFrame.fps.toFixed(1)} fps)` : ""}
                      </span>
                      {" • "}w_eff = {result.display.w_eff} •{" "}
                      {digital ? "SDD" : "SFD"} = {form.sfd} mm
                    </>
                  )
                ) : (
                  `w_eff = ${result.display.w_eff} • ${digital ? "SDD" : "SFD"} = ${form.sfd} mm • F = ${form.base_multiplier}×`
                )}
                {result.display.total_joint_time && (
                  ` • ⏱️ ${t("total_joint_time").replace(/:\s*$/, "")}: ${result.display.total_joint_time}`
                )}
              </div>
            )}
          </div>
          <div className="hero-right">
            <div className="hero-value" data-testid="output-calc_time">
              {result?.display.calc_time ?? "-"}
            </div>
            {result && (
              <span
                className={`hero-status ${
                  form.app_time >= Math.floor(result.values.calc_time)
                    ? "ok"
                    : "warn"
                }`}
              >
                {lang === "tr" ? "Uygulanan" : "Applied"}:{" "}
                {Math.floor(form.app_time / 60)}m{" "}
                {Math.round(form.app_time % 60)}s
              </span>
            )}
          </div>
        </div>
        <div className="hero-card">
          <div className="hero-main">
            <div className="hero-label">
              {t(digital ? "sfd_min" : "sfd_min_analog").replace(/:\s*$/, "")}
            </div>
            {provenanceSummary && (
              <div className="hero-sub" title={provenanceText}>
                {provenanceSummary}
              </div>
            )}
          </div>
          <div className="hero-right">
            <div className="hero-value">{result?.display.sfd_min ?? "-"}</div>
            {result && (
              <span
                className={`hero-status ${
                  form.sfd >= result.values.sfd_min ? "ok" : "warn"
                }`}
              >
                {lang === "tr" ? "Uygulanan" : "Applied"}: {form.sfd} mm{" "}
                {form.sfd >= result.values.sfd_min ? "✓" : "⚠"}
              </span>
            )}
          </div>
        </div>
        <div className="hero-card">
          <div className="hero-main">
            <div className="hero-label">{t("f_min").replace(/:\s*$/, "")}</div>
            {fMinProvenanceText && (
              <div className="hero-sub">
                {fMinProvenanceText}
                {result
                  ? ` • b = ${result.values.b_dist.toFixed(1)} mm (b_eff = ${result.values.b_eff.toFixed(1)} mm)`
                  : ""}
              </div>
            )}
          </div>
          <div className="hero-right">
            <div className="hero-value">{result?.display.f_min ?? "-"}</div>
          </div>
        </div>
        <div className="hero-card">
          <div className="hero-main">
            <div className="hero-label">{t("ug").replace(/:\s*$/, "")}</div>
            {result && (
              <div className="hero-sub">
                {`Ug = d·b / f (d = ${form.d} mm, b = ${(
                  result.values.f_min_provenance?.b ??
                  (!result.values.is_planar && result.values.b_rule_applied
                    ? result.values.b_eff
                    : result.values.b_dist)
                ).toFixed(1)} mm)`}
                {isAsme
                  ? ` • ASME Limit ≤ ${result.values.ug_limit.toFixed(2)} mm`
                  : ""}
              </div>
            )}
          </div>
          <div className="hero-right">
            <div className="hero-value">{result?.display.ug ?? "-"}</div>
            {result && isAsme && (
              <span
                className={`hero-status ${
                  result.values.ug_ok ? "ok" : "warn"
                }`}
              >
                {result.values.ug_ok ? "ASME ✓" : "ASME ⚠"}
              </span>
            )}
          </div>
        </div>
        <div className="hero-card">
          <div className="hero-main">
            <div className="hero-label">
              {t("req_exposures").replace(/:\s*$/, "")}
            </div>
            {exposuresProvenanceText && (
              <div className="hero-sub">{exposuresProvenanceText}</div>
            )}
          </div>
          <div className="hero-right">
            <div className="hero-value">
              {result?.display.req_exposures ?? "-"}
            </div>
            {result && (
              <span
                className={`hero-status ${
                  form.app_exposures === 0 ||
                  Boolean(result.values.exposures_ok)
                    ? "ok"
                    : "warn"
                }`}
              >
                {result.display.exposures_check}
              </span>
            )}
          </div>
        </div>
      </div>
      {digital && ddaFrame && (
        <div className="dda-integration-card" data-testid="dda-integration-card">
          <div className="dda-card-header">
            <span className="dda-card-title">
              🎞️{" "}
              {lang === "tr"
                ? "DDA Kare & Doz Entegrasyonu (ASTM E2698 / ISO 17636-2)"
                : "DDA Frame & Dose Integration (ASTM E2698 / ISO 17636-2)"}
            </span>
            {ddaFrame.panel_class && (
              <span className="dda-panel-badge">{ddaFrame.panel_class}</span>
            )}
          </div>
          <div className="dda-metrics-grid">
            <div className="dda-metric-box">
              <span className="dda-metric-label">
                {lang === "tr" ? "Kare Sayısı" : "Frame Count"}
              </span>
              <span className="dda-metric-value">{ddaFrame.n_frames}</span>
              <span className="dda-metric-sub">
                {lang === "tr" ? "kare (ortalamalı)" : "frames (averaged)"}
              </span>
            </div>
            <div className="dda-metric-box">
              <span className="dda-metric-label">
                {lang === "tr" ? "Kare Süresi" : "Frame Time"}
              </span>
              <span className="dda-metric-value">
                {ddaFrame.t_frame_sec.toFixed(2)} sn
              </span>
              <span className="dda-metric-sub">
                {(ddaFrame.t_frame_ms ?? ddaFrame.t_frame_sec * 1000).toFixed(0)}{" "}
                ms
              </span>
            </div>
            <div className="dda-metric-box">
              <span className="dda-metric-label">
                {lang === "tr" ? "Çekim Hızı" : "Frame Rate"}
              </span>
              <span className="dda-metric-value">
                {(ddaFrame.fps ?? 1 / ddaFrame.t_frame_sec).toFixed(1)}
              </span>
              <span className="dda-metric-sub">fps (Hz)</span>
            </div>
            <div className="dda-metric-box">
              <span className="dda-metric-label">
                {lang === "tr" ? "Hedef ADC Doyumu" : "Target ADC Level"}
              </span>
              <span className="dda-metric-value">
                %{ddaFrame.target_gray_pct}
              </span>
              <span className="dda-metric-sub">
                ~{ddaFrame.target_adu_16bit.toLocaleString()} ADU
              </span>
            </div>
            {ddaFrame.total_dose_ugy !== undefined && (
              <div className="dda-metric-box">
                <span className="dda-metric-label">
                  {lang === "tr" ? "Dedektör Dozu" : "Detector Dose"}
                </span>
                <span className="dda-metric-value">
                  {ddaFrame.total_dose_ugy >= 1000
                    ? `${(ddaFrame.total_dose_ugy / 1000).toFixed(2)} mGy`
                    : `${ddaFrame.total_dose_ugy.toFixed(1)} µGy`}
                </span>
                <span className="dda-metric-sub">
                  {ddaFrame.dose_rate_ugy_s
                    ? `${ddaFrame.dose_rate_ugy_s.toFixed(1)} µGy/s`
                    : ""}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
