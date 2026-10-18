import type { Dispatch, SetStateAction } from "react";

import { Group } from "../components";
import { formatExposuresProvenance } from "../i18n";
import type { EngineResult, ExposuresProvenance, FormState } from "../types";
import type { AppTheme } from "../state/usePersistedAppState";
import { AnnexAChartSvg, StandardFigureSvg, WeldSetupSvg } from "./SketchView";
import { WeldSetup3D } from "./WeldSetup3D";

type SketchTab = "3d" | "dynamic" | "figure" | "annex_a";

interface SketchTabsPanelProps {
  sketchTab: SketchTab;
  setSketchTab: Dispatch<SetStateAction<SketchTab>>;
  result: EngineResult | null;
  form: FormState;
  digital: boolean;
  theme: AppTheme;
  lang: string;
  t: (key: string, ...args: unknown[]) => string;
}

export function SketchTabsPanel({
  sketchTab,
  setSketchTab,
  result,
  form,
  digital,
  theme,
  lang,
  t,
}: SketchTabsPanelProps) {
  const exposuresProvenance = result?.values?.exposures_provenance as
    | ExposuresProvenance
    | undefined;
  const exposuresProvenanceText = formatExposuresProvenance(
    exposuresProvenance,
    t,
  );
  return (
    <>
      <div className="tabs">
        <button
          type="button"
          className={sketchTab === "3d" ? "tab active" : "tab"}
          onClick={() => setSketchTab("3d")}
        >
          {lang === "tr" ? "3D Kurulum" : "3D Setup"}
        </button>
        <button
          type="button"
          className={sketchTab === "dynamic" ? "tab active" : "tab"}
          onClick={() => setSketchTab("dynamic")}
        >
          {lang === "tr" ? "2D Kesit" : "2D Sketch"}
        </button>
        <button
          type="button"
          className={sketchTab === "figure" ? "tab active" : "tab"}
          onClick={() => setSketchTab("figure")}
        >
          {lang === "tr" ? "ISO Figürü" : "ISO Figure"}
        </button>
        <button
          type="button"
          className={sketchTab === "annex_a" ? "tab active" : "tab"}
          onClick={() => setSketchTab("annex_a")}
        >
          Annex A
        </button>
      </div>

      {sketchTab === "3d" && (
        <Group
          title={
            lang === "tr"
              ? "5. 3D Çekim Geometrisi ve İzdüşüm Sahnesi"
              : "5. 3D Shooting Geometry & Projection Scene"
          }
        >
          {result ? (
            <WeldSetup3D
              od={result.values.od}
              t={result.values.t}
              cap={result.values.cap}
              weldWidth={form.weld_width}
              d={form.d}
              geometry={result.values.geometry}
              userGeometry={form.geometry}
              geometryForced={Boolean(result.values.geometry_forced)}
              sfd={result.values.sfd}
              fMin={result.values.f_min}
              bDist={result.values.b_dist}
              bed={Number(result.values.bed ?? 0)}
              bgap={form.bgap}
              ug={result.values.ug}
              isPlanar={Boolean(result.values.is_planar)}
              isDigital={digital}
              filmSide={form.film_side}
              panelWidth={form.panel_width}
              panelHeight={form.panel_height}
              filmWidth={form.film_width}
              filmHeight={form.film_height}
              overlapPct={
                digital ? result.values.panel_overlap : form.app_overlap
              }
              nRequired={result.values.n_required}
              nApplied={form.app_exposures}
              wireStr={String(result.values.wire_str ?? "W10")}
              duplexStr={String(result.values.duplex_str ?? "D6")}
              safetyRadiusM={result.values.safety_radius_m}
              supervisedRadiusM={
                (result.values.r_supervised as number | undefined) ?? null
              }
              theme={theme}
              lang={lang}
            />
          ) : (
            <p className="muted">…</p>
          )}
        </Group>
      )}

      <div style={{ display: sketchTab === "dynamic" ? "block" : "none" }}>
        <Group
          title={
            lang === "tr"
              ? "5. Dinamik Çekim Düzeni (2D Çizim)"
              : "5. Dynamic Weld Setup (2D Sketch)"
          }
        >
          {result ? (
            <div id="dynamic-sketch">
              <WeldSetupSvg
                od={result.values.od}
                t={result.values.t}
                cap={result.values.cap}
                geometry={
                  result.values.geometry_forced
                    ? form.geometry
                    : result.values.geometry
                }
                sfd={result.values.sfd}
                fMin={result.values.f_min}
                bDist={result.values.b_dist}
                bed={Number(result.values.bed ?? 0)}
                bgap={form.bgap}
                ug={result.values.ug}
                filmSide={form.film_side}
                isPlanar={Boolean(result.values.is_planar)}
                nRequired={result.values.n_required}
                nApplied={form.app_exposures}
                panelWidth={
                  form.tech === "digital" ? result.values.panel_width : null
                }
                overlapPct={result.values.panel_overlap}
                safetyRadiusM={result.values.safety_radius_m}
                supervisedRadiusM={
                  (result.values.r_supervised as number | undefined) ?? null
                }
                labels={{
                  pipe: t("pipe_wall"),
                  source: t("source"),
                  detector: t("detector"),
                  dda: t("dda_label"),
                  overlap: t("overlap_short"),
                  safety: t("safety_ring"),
                  sourceOffset: t("source_offset"),
                  beamAngle: t("beam_angle"),
                }}
              />
            </div>
          ) : (
            <p className="muted">…</p>
          )}
        </Group>
      </div>

      <div style={{ display: sketchTab === "figure" ? "block" : "none" }}>
        <Group
          title={
            lang === "tr"
              ? "5. Standart Çekim Düzeni Figürü (ISO 17636)"
              : "5. Standard Arrangement Figure (ISO 17636)"
          }
        >
          {form.std_figure ? (
            <div id="standard-sketch">
              <StandardFigureSvg
                figure={form.std_figure}
                title={t(`${form.std_figure}_title`)}
              />
            </div>
          ) : (
            <p className="muted">-</p>
          )}
        </Group>
      </div>

      {sketchTab === "annex_a" && (
        <Group
          title={
            lang === "tr"
              ? "5. ISO 17636 Annex A Çalışma Noktası Grafiği"
              : "5. ISO 17636 Annex A Operating Point Chart"
          }
        >
          {exposuresProvenance && exposuresProvenance.method === "annex_a" ? (
            <AnnexAChartSvg
              figure={exposuresProvenance.figure}
              tOverDe={exposuresProvenance.t_over_de}
              ratioName={exposuresProvenance.ratio_name}
              ratio={exposuresProvenance.ratio}
              n={exposuresProvenance.n}
              nextN={exposuresProvenance.next_n}
              nextRatio={exposuresProvenance.next_ratio}
              nextDistanceMm={exposuresProvenance.next_distance_mm}
              boundaries={exposuresProvenance.boundaries}
              lang={lang}
            />
          ) : (
            <p className="muted">
              {exposuresProvenanceText ||
                (lang === "tr"
                  ? "Mevcut teknik (Panoramik / DWDI) Annex A eğrisi yerine doğrudan kural kullanıyor."
                  : "Current technique (Panoramic / DWDI) uses direct rule instead of Annex A curve.")}
            </p>
          )}
        </Group>
      )}
    </>
  );
}
