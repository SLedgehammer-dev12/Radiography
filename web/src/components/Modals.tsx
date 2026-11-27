import { useEffect, useRef, useState, type RefObject } from "react";

import { NumberField } from "../components";
import { pyClient } from "../pyodide/client";
import type { CalculationHistoryEntry } from "../state/useCalculationHistory";
import type { Lvl3Settings } from "../types";

import { FALLBACK_VERSION } from "../version";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useModalFocusTrap(
  dialogRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  active = true,
) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!active) return;
    const prevFocus = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    if (dialog) {
      const first = dialog.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      (first ?? dialog).focus();
    }

    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const focusables = Array.from(
        dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );
      if (focusables.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      prevFocus?.focus?.();
    };
  }, [dialogRef, active]);
}

interface DecayDialogProps {
  t: (key: string, ...args: unknown[]) => string;
  lang?: string;
  source: string;
  initialActivity?: number;
  onApply: (activity: number) => void;
  onClose: () => void;
}

function DecayDialog({ t, lang = "tr", source, initialActivity, onApply, onClose }: DecayDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalFocusTrap(dialogRef, onClose);
  const [initial, setInitial] = useState(initialActivity ?? 40);
  const [calibDate, setCalibDate] = useState("");
  const [current, setCurrent] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const displayCurrent = calibDate ? current : null;

  useEffect(() => {
    if (!calibDate) {
      setLoading(false);
      setErrorMsg(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    const handle = setTimeout(async () => {
      try {
        const data = await pyClient.request<{
          current_activity: number;
          days: number;
        }>("decay", {
          activity: initial,
          calib_date: calibDate,
          isotope: source,
        });
        if (!cancelled) {
          setCurrent(data.current_activity);
          setErrorMsg(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setCurrent(null);
          setErrorMsg(
            err instanceof Error
              ? err.message
              : lang === "tr"
                ? "Bozunum hesabı yapılamadı."
                : "Decay calculation failed.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [initial, calibDate, source, lang]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="decay-dialog-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="decay-dialog-title">{t("decay_dialog")}</h2>
        <NumberField
          label={t("decay_initial")}
          value={initial}
          min={0.01}
          max={1000}
          onChange={(value) => setInitial(value ?? 40)}
        />
        <label className="field">
          <span className="field-label">{t("decay_calib_date")}</span>
          <input
            className="field-input"
            type="date"
            value={calibDate}
            onChange={(event) => setCalibDate(event.target.value)}
          />
        </label>
        <p aria-live="polite">
          {t("decay_current")}{" "}
          <strong>
            {loading
              ? (lang === "tr" ? "Hesaplanıyor…" : "Calculating…")
              : displayCurrent === null
                ? "-"
                : `${displayCurrent.toFixed(1)} Ci`}
          </strong>
        </p>
        {errorMsg && (
          <p className="field-error" role="alert">
            {errorMsg}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>{t("dialog_cancel")}</button>
          <button
            type="button"
            className="primary"
            disabled={loading || displayCurrent === null}
            onClick={() => {
              if (displayCurrent !== null) onApply(displayCurrent);
              onClose();
            }}
          >
            {t("decay_apply")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface Lvl3DialogProps {
  lvl3: Lvl3Settings;
  t: (key: string, ...args: unknown[]) => string;
  onChange: (lvl3: Lvl3Settings) => void;
  onClose: () => void;
}

function Lvl3Dialog({ lvl3, t, onChange, onClose }: Lvl3DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalFocusTrap(dialogRef, onClose);
  const [draft, setDraft] = useState<Lvl3Settings>(() => ({ ...lvl3 }));

  const options: [keyof Lvl3Settings, string][] = [
    ["sfd_comp", "lvl3_sfd_compensation"],
    ["voltage_override", "lvl3_voltage_override"],
    ["isotope_flex", "lvl3_isotope_flex"],
    ["source_flex", "lvl3_source_flex"],
    ["central_proj_reduction", "lvl3_central_proj"],
    ["dw_reduction", "lvl3_dw_reduction"],
  ];
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="lvl3-dialog-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="lvl3-dialog-title">{t("level3_section")}</h2>
        {options.map(([key, labelKey]) => (
          <label className="field field-inline" key={key}>
            <input
              type="checkbox"
              checked={Boolean(draft[key])}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, [key]: event.target.checked }))
              }
            />
            <span>{t(labelKey)}</span>
          </label>
        ))}
        <label className="field">
          <span className="field-label">{t("level3_approval_note")}</span>
          <textarea
            className="field-input"
            rows={3}
            placeholder={t("level3_approval_placeholder")}
            value={draft.approval_note}
            onChange={(event) =>
              setDraft((prev) => ({ ...prev, approval_note: event.target.value }))
            }
          />
        </label>
        <div className="modal-actions">
          <button type="button" onClick={onClose}>{t("dialog_cancel")}</button>
          <button
            type="button"
            className="primary"
            onClick={() => {
              onChange(draft);
              onClose();
            }}
          >
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface AboutModalProps {
  t: (key: string, ...args: unknown[]) => string;
  onClose: () => void;
  currentVersion?: string;
}

function AboutModal({ t, onClose, currentVersion = FALLBACK_VERSION }: AboutModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalFocusTrap(dialogRef, onClose);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal about-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="about-dialog-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="about-header">
          <div className="about-title-block">
            <h2 id="about-dialog-title">
              <span>{t("app_title").split("(")[0]?.trim() || "Radiography"}</span>
              <span className="about-version-badge">v{currentVersion.replace(/^v/, "")}</span>
            </h2>
            <p className="about-owner">{t("app_owner")}</p>
            <div className="about-standards-row">
              <span className="about-std-tag">ISO 17636-1 / ISO 17636-2</span>
              <span className="about-std-tag">ISO 19232 (IQI)</span>
              <span className="about-std-tag">API 1104</span>
              <span className="about-std-tag">ASME Sec. V / B31.3</span>
            </div>
          </div>
          <button
            type="button"
            className="info-modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Engineering Disclaimer */}
        <div className="about-disclaimer-box">
          <div className="about-disclaimer-title">
            ⚠️ {t("engineering_disclaimer_title")}
          </div>
          <div>{t("disclaimer")}</div>
        </div>

        {/* Support & Contact */}
        <div className="about-section">
          <span className="about-section-title">{t("contact_title")}</span>
          <div className="about-buttons-grid">
            <a
              href="https://github.com/SLedgehammer-dev12/Radiography/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="about-btn"
            >
              <span>🐞</span>
              <span>{t("report_issue")}</span>
            </a>
            <a href="mailto:omer.erbas@botas.gov.tr" className="about-btn">
              <span>✉️</span>
              <span>{t("contact_email_action")}</span>
            </a>
          </div>
        </div>

        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface UpdateModalProps {
  t: (key: string, ...args: unknown[]) => string;
  lang?: string;
  onClose: () => void;
  currentVersion?: string;
}

type UpdateStatus = {
  status: "checking" | "up_to_date" | "available" | "error";
  latestVersion?: string;
  releaseUrl?: string;
  errorMessage?: string;
};

async function fetchReleaseStatus(
  currentVersion: string,
  signal?: AbortSignal,
): Promise<UpdateStatus | null> {
  try {
    const res = await fetch(
      "https://api.github.com/repos/SLedgehammer-dev12/Radiography/releases/latest",
      { headers: { Accept: "application/vnd.github+json" }, signal },
    );
    if (!res.ok) {
      throw new Error(`GitHub API HTTP ${res.status}`);
    }
    const data = await res.json();
    const tagName: string = data.tag_name || "";

    const parseV = (v: string): [number, number, number] => {
      const match = v.match(/^v?(\d+)\.(\d+)\.(\d+)/);
      if (!match) return [0, 0, 0];
      return [parseInt(match[1], 10), parseInt(match[2], 10), parseInt(match[3], 10)];
    };
    const [maj1, min1, pat1] = parseV(tagName);
    const [maj0, min0, pat0] = parseV(currentVersion);

    const isNewer =
      maj1 > maj0 ||
      (maj1 === maj0 && min1 > min0) ||
      (maj1 === maj0 && min1 === min0 && pat1 > pat0);

    if (isNewer) {
      return {
        status: "available",
        latestVersion: tagName,
        releaseUrl:
          data.html_url ||
          "https://github.com/SLedgehammer-dev12/Radiography/releases",
      };
    }
    return {
      status: "up_to_date",
      latestVersion: tagName || `v${currentVersion}`,
    };
  } catch (err: unknown) {
    if (signal?.aborted) return null;
    return {
      status: "error",
      errorMessage: err instanceof Error ? err.message : String(err),
    };
  }
}

function UpdateModal({ t, lang = "tr", onClose, currentVersion = FALLBACK_VERSION }: UpdateModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalFocusTrap(dialogRef, onClose);
  const tr = lang === "tr";
  const [updateState, setUpdateState] = useState<UpdateStatus>({
    status: "checking",
  });

  const handleCheckUpdates = async () => {
    setUpdateState({ status: "checking" });
    const next = await fetchReleaseStatus(currentVersion);
    if (next) setUpdateState(next);
  };

  useEffect(() => {
    const controller = new AbortController();
    void fetchReleaseStatus(currentVersion, controller.signal).then((next) => {
      if (next) setUpdateState(next);
    });
    return () => controller.abort();
  }, [currentVersion]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal update-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="update-dialog-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="about-header">
          <div className="about-title-block">
            <h2 id="update-dialog-title">
              <span>🔄 {t("check_updates_btn")}</span>
            </h2>
            <p className="about-owner">
              {tr ? "Mevcut Yüklü Sürüm:" : "Installed Version:"}{" "}
              <strong>v{currentVersion.replace(/^v/, "")}</strong>
            </p>
          </div>
          <button
            type="button"
            className="info-modal-close"
            onClick={onClose}
            aria-label={tr ? "Kapat" : "Close"}
          >
            ✕
          </button>
        </div>

        <div className="update-modal-body" style={{ margin: "14px 0" }}>
          {updateState.status === "checking" && (
            <div className="about-update-status loading">
              <span>⏳ {t("checking_updates")}</span>
            </div>
          )}

          {updateState.status === "up_to_date" && (
            <div className="about-update-status success">
              <span>✅ {t("up_to_date", currentVersion)}</span>
              <button
                type="button"
                className="about-btn"
                style={{ padding: "4px 10px", fontSize: "11px" }}
                onClick={() => {
                  void handleCheckUpdates();
                }}
                title={tr ? "Tekrar Kontrol Et" : "Check Again"}
              >
                🔄 {tr ? "Yenile" : "Refresh"}
              </button>
            </div>
          )}

          {updateState.status === "available" && (
            <div className="about-update-status available">
              <span>🚀 {t("update_available", updateState.latestVersion)}</span>
              <a
                href={updateState.releaseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="about-btn primary-btn"
                style={{ padding: "5px 12px", fontSize: "12px" }}
              >
                {t("view_release")} ↗
              </a>
            </div>
          )}

          {updateState.status === "error" && (
            <div className="about-update-status error" role="alert">
              <span>
                ⚠️ {updateState.errorMessage || (tr ? "Kontrol başarısız oldu." : "Update check failed.")}
              </span>
              <button
                type="button"
                className="about-btn"
                style={{ padding: "4px 10px", fontSize: "11px" }}
                onClick={() => {
                  void handleCheckUpdates();
                }}
              >
                {tr ? "Yeniden Dene" : "Retry"}
              </button>
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button type="button" className="primary" onClick={onClose}>
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface CalculationHistoryModalProps {
  t: (key: string, ...args: unknown[]) => string;
  lang: string;
  history: CalculationHistoryEntry[];
  onRestore: (entry: CalculationHistoryEntry) => void;
  onClear: () => void;
  onClose: () => void;
}

function CalculationHistoryModal({
  t,
  lang,
  history,
  onRestore,
  onClear,
  onClose,
}: CalculationHistoryModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalFocusTrap(dialogRef, onClose);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={dialogRef}
        className="modal history-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="history-modal-title"
        data-testid="history-modal"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        style={{ maxWidth: 640 }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <h2 id="history-modal-title" style={{ margin: 0 }}>
            ⏱️ {t("recent_calculations") || (lang === "tr" ? "Son Hesaplamalar Geçmişi" : "Recent Calculations")}
          </h2>
          {history.length > 0 && (
            <button
              type="button"
              className="about-btn"
              data-testid="history-clear-btn"
              onClick={onClear}
              style={{ padding: "4px 10px", fontSize: "11px", color: "var(--red)" }}
            >
              🗑️ {lang === "tr" ? "Geçmişi Temizle" : "Clear History"}
            </button>
          )}
        </div>

        {history.length === 0 ? (
          <p style={{ color: "var(--text-muted)", padding: "20px 0", textAlign: "center" }}>
            {t("history_empty") || (lang === "tr" ? "Henüz kayıtlı bir hesaplama geçmişi bulunmuyor." : "No calculation history recorded yet.")}
          </p>
        ) : (
          <div className="history-list" style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "420px", overflowY: "auto" }}>
            {history.map((entry, index) => {
              const timeStr = new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
              const s = entry.summary;
              const geomLabel =
                s.geometry === "dwdi_elliptic"
                  ? (lang === "tr" ? "DWDI Eliptik" : "DWDI Elliptical")
                  : s.geometry === "dwdi_super"
                  ? (lang === "tr" ? "DWDI Çakışık" : "DWDI Superimposed")
                  : s.geometry?.toUpperCase?.() ?? "";
              const metricsLabel =
                lang === "tr"
                  ? `${s.source} • SFD: ${s.sfd} mm • Asgari: ${s.exposures} Poz • Süre: ${Math.round(s.exposureTimeSec)} sn`
                  : `${s.source} • SFD: ${s.sfd} mm • Min: ${s.exposures} Exposures • Duration: ${Math.round(s.exposureTimeSec)} s`;
              return (
                <div
                  key={entry.id || index}
                  className="history-card"
                  style={{
                    background: "var(--panel-2)",
                    border: "1px solid var(--panel-border)",
                    borderRadius: "8px",
                    padding: "12px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "12px",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
                      <span>🕒 {timeStr}</span>
                      <span className="badge" style={{ fontSize: "11px", padding: "1px 6px" }}>{s.governingStd}</span>
                      <span style={{ fontWeight: 600, color: "var(--text)" }}>{geomLabel}</span>
                    </div>
                    <div style={{ fontSize: "14px", fontWeight: 600 }}>
                      Ø {s.od} mm × {s.t} mm ({s.material})
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      {metricsLabel}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="primary"
                    data-testid="history-restore-btn"
                    style={{ padding: "6px 14px", fontSize: "12px", whiteSpace: "nowrap" }}
                    onClick={() => {
                      onRestore(entry);
                      onClose();
                    }}
                  >
                    ⚡ {lang === "tr" ? "Yükle" : "Restore"}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <div className="modal-actions" style={{ marginTop: "16px" }}>
          <button className="primary" data-testid="history-close-btn" onClick={onClose}>
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}

export { AboutModal, CalculationHistoryModal, DecayDialog, Lvl3Dialog, UpdateModal };
