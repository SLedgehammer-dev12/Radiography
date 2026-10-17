import { InfoTip } from "../components";
import { formatExposuresProvenance, type Translator } from "../i18n";
import type {
  ComplianceResult,
  EngineResult,
  ExposuresProvenance,
  FormState,
} from "../types";

interface HeroSummaryPanelProps {
  result: EngineResult | null;
  compliance: ComplianceResult | null;
  form: FormState;
  lang: string;
  t: Translator;
  onNotify?: (message: string, kind?: "info" | "success" | "error") => void;
}

export function HeroSummaryPanel({
  result,
  compliance,
  form,
  lang,
  t,
  onNotify,
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
  const fMinDetail =
    (result?.values?.f_min_provenance_text as string | undefined) || "";
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
  const dwdiDetail = (result?.values?.dwdi_coverage_detail as string) || "";
  const dwdiCoverage = result?.values?.dwdi_coverage as
    | { is_sufficient: boolean; w_min_req: number; available_across: number }
    | undefined;

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

  const copyToClipboard = (text: string, label: string) => {
    if (!text || text === "-") return;
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(
        () => onNotify?.(`${label}: "${text}"`, "success"),
        () => undefined,
      );
    }
  };

  const copySummary = () => {
    if (!result) return;
    const distLabel = digital ? "SDD" : "SFD";
    const iqiLabel = isAsme
      ? (result.display.asme_iqi ?? "-")
      : (result.display.single_wire_iqi ?? "-");
    const summary = [
      `RT Muayene Özeti:`,
      `• Geometri: ${form.geometry.toUpperCase()} (${form.od} mm OD × ${form.t} mm t)`,
      `• Kaynak: ${form.source.toUpperCase()} ${
        form.source === "x_ray"
          ? `(${form.app_kv} kV, ${form.output_val} mA)`
          : `(${form.output_val} Ci)`
      }`,
      `• Teknik: ${
        digital
          ? `Dijital (${form.detector_type})`
          : `Analog Film (${form.film_class_used})`
      }`,
      `• Mesafe (${distLabel}): Min ${result.display.sfd_min ?? "-"} mm | Uygulanan: ${form.sfd} mm`,
      `• Poz Süresi: Min ${result.display.calc_time ?? "-"} | Uygulanan: ${form.app_time} sn`,
      `• Poz Sayısı: Min ${result.display.req_exposures ?? "-"} | Uygulanan: ${form.app_exposures}`,
      `• IQI Şartı: ${iqiLabel}`,
      `• Uygunluk: ${
        compliance != null
          ? compliance.is_compliant
            ? (lang === "tr" ? "UYGUN (COMPLIANT)" : "COMPLIANT")
            : (lang === "tr" ? "UYGUN DEĞİL (NON-COMPLIANT)" : "NON-COMPLIANT")
          : "-"
      }`,
    ].join("\n");
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(summary).then(
        () =>
          onNotify?.(
            lang === "tr"
              ? "Hesaplama özeti panoya kopyalandı."
              : "Inspection summary copied to clipboard.",
            "success",
          ),
        () => undefined,
      );
    }
  };

  return (
    <>
      <div className="hero-toolbar">
        <span className="hero-toolbar-title">
          ⚡ {lang === "tr" ? "Hesaplanan Temel Değerler" : "Key Calculated Metrics"}
        </span>
        {result && (
          <button
            type="button"
            className="copy-summary-btn"
            onClick={copySummary}
            title={
              lang === "tr"
                ? "Tüm muayene parametrelerini panoya kopyala"
                : "Copy inspection summary to clipboard"
            }
          >
            📋 {lang === "tr" ? "Özeti Kopyala" : "Copy Summary"}
          </button>
        )}
      </div>
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
            <div
              className="hero-value"
              data-testid="output-calc_time"
              onClick={() =>
                copyToClipboard(
                  result?.display.calc_time ?? "",
                  lang === "tr" ? "Hesaplanan süre" : "Calculated time",
                )
              }
              title={lang === "tr" ? "Kopyalamak için tıklayın" : "Click to copy"}
            >
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
            <div
              className="hero-value"
              onClick={() =>
                copyToClipboard(
                  result?.display.sfd_min ?? "",
                  lang === "tr" ? "Minimum mesafe" : "Minimum distance",
                )
              }
              title={lang === "tr" ? "Kopyalamak için tıklayın" : "Click to copy"}
            >
              {result?.display.sfd_min ?? "-"}
            </div>
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
            <div className="hero-label">
              <span>{t("f_min").replace(/:\s*$/, "")}</span>
              {fMinDetail && (
                <InfoTip
                  text={fMinDetail}
                  title={t("f_min").replace(/:\s*$/, "")}
                />
              )}
            </div>
            <div className="hero-sub">
              {fMinProvenanceText}
              {result &&
              result.values?.f_min_iso != null &&
              result.values?.f_min_asme != null ? (
                <>
                  {" • "}
                  <span
                    title={
                      lang === "tr"
                        ? "ISO 17636-1/2 asgari odak-nesne mesafesi"
                        : "ISO 17636-1/2 minimum source-to-object distance"
                    }
                  >
                    ISO: <strong>{Number(result.values.f_min_iso).toFixed(1)} mm</strong>
                  </span>
                  {" | "}
                  <span
                    title={
                      lang === "tr"
                        ? "ASME Sec V Art 2 T-274.2 asgari mesafesi"
                        : "ASME Sec V Art 2 T-274.2 minimum distance"
                    }
                  >
                    ASME: <strong>{Number(result.values.f_min_asme).toFixed(1)} mm</strong>
                  </span>
                  {` • b = ${Number(result.values.b_dist ?? 0).toFixed(1)} mm`}
                </>
              ) : (
                result
                  ? ` • b = ${Number(result.values?.b_dist ?? 0).toFixed(1)} mm`
                  : ""
              )}
            </div>
          </div>
          <div className="hero-right">
            <div
              className="hero-value"
              onClick={() =>
                copyToClipboard(
                  result?.display.f_min ?? "",
                  "f_min",
                )
              }
              title={lang === "tr" ? "Kopyalamak için tıklayın" : "Click to copy"}
            >
              {result?.display.f_min ?? "-"}
            </div>
            {result && (
              <span className="hero-status ok">
                {isAsme ? "ASME" : "ISO"} ✓
              </span>
            )}
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
            <div
              className="hero-value"
              onClick={() =>
                copyToClipboard(
                  result?.display.ug ?? "",
                  "Ug",
                )
              }
              title={lang === "tr" ? "Kopyalamak için tıklayın" : "Click to copy"}
            >
              {result?.display.ug ?? "-"}
            </div>
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
              <span>{t("req_exposures").replace(/:\s*$/, "")}</span>
              {dwdiDetail && (
                <InfoTip
                  text={dwdiDetail}
                  title={
                    lang === "tr"
                      ? "DWDI Poz Sayısı ve Boyut Kapsaması"
                      : "DWDI Exposures & Size Coverage"
                  }
                />
              )}
            </div>
            {exposuresProvenanceText && (
              <div className="hero-sub">{exposuresProvenanceText}</div>
            )}
            {dwdiCoverage &&
              dwdiCoverage.available_across > 0 &&
              !dwdiCoverage.is_sufficient && (
                <div
                  className="hero-alert-banner"
                  style={{
                    color: "var(--color-warn, #d97706)",
                    fontWeight: 600,
                    fontSize: "0.82rem",
                    marginTop: "6px",
                    lineHeight: 1.3,
                  }}
                >
                  {lang === "tr"
                    ? `⚠ Boyut Yetersiz: Boru izdüşümü (${dwdiCoverage.w_min_req.toFixed(1)} mm) seçilen kaset/panel boyutunu (${dwdiCoverage.available_across.toFixed(0)} mm) aşıyor! En az ${dwdiCoverage.w_min_req.toFixed(1)} mm gerekir.`
                    : `⚠ Size Insufficient: Pipe projection (${dwdiCoverage.w_min_req.toFixed(1)} mm) exceeds receptor size (${dwdiCoverage.available_across.toFixed(0)} mm)! Minimum ${dwdiCoverage.w_min_req.toFixed(1)} mm required.`}
                </div>
              )}
          </div>
          <div className="hero-right">
            <div
              className="hero-value"
              onClick={() =>
                copyToClipboard(
                  String(result?.display.req_exposures ?? ""),
                  lang === "tr" ? "Gerekli poz sayısı" : "Required exposures",
                )
              }
              title={lang === "tr" ? "Kopyalamak için tıklayın" : "Click to copy"}
            >
              {result?.display.req_exposures ?? "-"}
            </div>
            {result && (
              <span
                className={`hero-status ${
                  (form.app_exposures === 0 ||
                    Boolean(result.values.exposures_ok)) &&
                  (!dwdiCoverage ||
                    dwdiCoverage.available_across === 0 ||
                    dwdiCoverage.is_sufficient)
                    ? "ok"
                    : "warn"
                }`}
              >
                {dwdiCoverage &&
                dwdiCoverage.available_across > 0 &&
                !dwdiCoverage.is_sufficient
                  ? lang === "tr"
                    ? "Boyut Yetersiz ⚠"
                    : "Size Insufficient ⚠"
                  : result.display.exposures_check}
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
