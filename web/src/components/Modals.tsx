import { useEffect, useState } from "react";

import { NumberField } from "../components";
import { pyClient } from "../pyodide/client";
import type { Lvl3Settings } from "../types";

export const FALLBACK_VERSION = "2.0.3";

function useEscapeClose(onClose: () => void) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
}

interface DecayDialogProps {
  t: (key: string, ...args: unknown[]) => string;
  source: string;
  onApply: (activity: number) => void;
  onClose: () => void;
}

function DecayDialog({ t, source, onApply, onClose }: DecayDialogProps) {
  useEscapeClose(onClose);
  const [initial, setInitial] = useState(40);
  const [calibDate, setCalibDate] = useState("");
  const [current, setCurrent] = useState<number | null>(null);
  const displayCurrent = calibDate ? current : null;

  useEffect(() => {
    if (!calibDate) return;
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
        setCurrent(data.current_activity);
      } catch {
        setCurrent(null);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [initial, calibDate, source]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <h2>{t("decay_dialog")}</h2>
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
        <p>
          {t("decay_current")}{" "}
          <strong>
            {displayCurrent === null ? "-" : `${displayCurrent.toFixed(1)} Ci`}
          </strong>
        </p>
        <div className="modal-actions">
          <button onClick={onClose}>{t("dialog_cancel")}</button>
          <button
            className="primary"
            disabled={displayCurrent === null}
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
  useEscapeClose(onClose);
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
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <h2>{t("level3_section")}</h2>
        {options.map(([key, labelKey]) => (
          <label className="field field-inline" key={key}>
            <input
              type="checkbox"
              checked={Boolean(lvl3[key])}
              onChange={(event) =>
                onChange({ ...lvl3, [key]: event.target.checked })
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
            value={lvl3.approval_note}
            onChange={(event) =>
              onChange({ ...lvl3, approval_note: event.target.value })
            }
          />
        </label>
        <div className="modal-actions">
          <button onClick={onClose}>{t("dialog_cancel")}</button>
          <button className="primary" onClick={onClose}>
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
  useEscapeClose(onClose);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal about-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="about-header">
          <div className="about-title-block">
            <h2>
              <span>{t("app_title").split("(")[0]?.trim() || "Radiography"}</span>
              <span className="about-version-badge">v{currentVersion}</span>
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
          <button className="primary" onClick={onClose}>
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}

interface UpdateModalProps {
  t: (key: string, ...args: unknown[]) => string;
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

function UpdateModal({ t, onClose, currentVersion = FALLBACK_VERSION }: UpdateModalProps) {
  useEscapeClose(onClose);
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
        className="modal update-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="about-header">
          <div className="about-title-block">
            <h2>
              <span>🔄 {t("check_updates_btn")}</span>
            </h2>
            <p className="about-owner">
              Mevcut Yüklü Sürüm: <strong>v{currentVersion}</strong>
            </p>
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
                title="Tekrar Kontrol Et"
              >
                🔄 Yenile
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
            <div
              className="about-update-status available"
              style={{ borderColor: "#f38ba8", color: "#f38ba8" }}
            >
              <span>
                ⚠️ {updateState.errorMessage || "Kontrol başarısız oldu."}
              </span>
              <button
                type="button"
                className="about-btn"
                style={{ padding: "4px 10px", fontSize: "11px" }}
                onClick={() => {
                  void handleCheckUpdates();
                }}
              >
                Yeniden Dene
              </button>
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button className="primary" onClick={onClose}>
            {t("dialog_ok")}
          </button>
        </div>
      </div>
    </div>
  );
}


export { AboutModal, DecayDialog, Lvl3Dialog, UpdateModal };
