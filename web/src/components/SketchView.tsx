import type { ReactNode } from "react";

const W = 420;
const H = 420;

interface Transform {
  X: (x: number) => number;
  Y: (y: number) => number;
  scale: number;
}

function makeTransform(minX: number, maxX: number, minY: number, maxY: number): Transform {
  const width = Math.max(maxX - minX, 1e-6);
  const height = Math.max(maxY - minY, 1e-6);
  const scale = Math.min((W * 0.82) / width, (H * 0.82) / height);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  return {
    X: (x: number) => W / 2 + (x - cx) * scale,
    Y: (y: number) => H / 2 - (y - cy) * scale,
    scale,
  };
}

function arcPath(transform: Transform, r: number, t1: number, t2: number): string {
  const point = (angle: number) => {
    const rad = (angle * Math.PI) / 180;
    return `${transform.X(r * Math.cos(rad))},${transform.Y(r * Math.sin(rad))}`;
  };
  const large = Math.abs(t2 - t1) > 180 ? 1 : 0;
  const sweep = t2 > t1 ? 0 : 1;
  return `M ${point(t1)} A ${r * transform.scale} ${r * transform.scale} 0 ${large} ${sweep} ${point(t2)}`;
}

function WeldBump({
  transform,
  x,
  y,
  weldWidth,
  weldHeight,
  inward,
}: {
  transform: Transform;
  x: number;
  y: number;
  weldWidth: number;
  weldHeight: number;
  inward: boolean;
}) {
  const half = weldWidth / 2;
  const peak = inward ? y - weldHeight : y + weldHeight;
  return (
    <path
      d={`M ${transform.X(x - half)},${transform.Y(y)} Q ${transform.X(x)},${transform.Y(peak)} ${transform.X(x + half)},${transform.Y(y)}`}
      fill="none"
      stroke="var(--sketch-weld)"
      strokeWidth={2}
    />
  );
}

function SourceMarker({
  transform,
  kind,
  x,
  y,
}: {
  transform: Transform;
  kind: "star" | "dot";
  x: number;
  y: number;
}) {
  const sx = transform.X(x);
  const sy = transform.Y(y);
  if (kind === "star") {
    const outer = 9;
    const inner = 3.6;
    const points: string[] = [];
    for (let index = 0; index < 10; index += 1) {
      const radius = index % 2 === 0 ? outer : inner;
      const angle = (Math.PI / 5) * index - Math.PI / 2;
      points.push(`${sx + radius * Math.cos(angle)},${sy + radius * Math.sin(angle)}`);
    }
    return <polygon points={points.join(" ")} fill="var(--sketch-source)" />;
  }
  return <circle cx={sx} cy={sy} r={7} fill="var(--sketch-source)" />;
}

function Labels({
  transform,
  labels,
}: {
  transform: Transform;
  labels: {
    text: string;
    x: number;
    y: number;
    size?: number;
    anchor?: "middle" | "start" | "end";
    fill?: string;
  }[];
}) {
  return (
    <>
      {labels.map((label, index) => (
        <text
          key={index}
          x={transform.X(label.x)}
          y={transform.Y(label.y)}
          fontSize={label.size ?? 11}
          fill={label.fill ?? "var(--sketch-text)"}
          textAnchor={label.anchor ?? "middle"}
        >
          {label.text}
        </text>
      ))}
    </>
  );
}

export interface WeldSetupProps {
  od: number;
  t: number;
  cap: number;
  geometry: string;
  sfd: number;
  fMin?: number;
  bDist?: number;
  bed?: number;
  bgap?: number;
  ug?: number;
  filmSide?: boolean;
  isPlanar?: boolean;
  nRequired?: number;
  nApplied?: number;
  panelWidth?: number | null;
  panelHeight?: number | null;
  overlapPct?: number;
  safetyRadiusM?: number | null;
  supervisedRadiusM?: number | null;
  labels: {
    pipe: string;
    source: string;
    detector: string;
    dda: string;
    overlap: string;
    safety: string;
    sourceOffset: string;
    beamAngle: string;
  };
}

export function WeldSetupSvg({
  od,
  t,
  cap,
  geometry,
  sfd,
  fMin = 0,
  bDist = 0,
  bed = 0,
  bgap = 0,
  ug = 0,
  filmSide = true,
  isPlanar = false,
  nRequired = 1,
  nApplied = 0,
  panelWidth,
  overlapPct = 10,
  safetyRadiusM,
  supervisedRadiusM,
  labels,
}: WeldSetupProps) {
  const R = Math.max(od / 2, 1);
  const Ri = Math.max(R - t, R * 0.05);
  const ringR =
    safetyRadiusM && safetyRadiusM > 0
      ? Math.max(R * 1.8, Math.min(safetyRadiusM * 0.05, R * 4))
      : 0;

  let extent = Math.max(R * 1.55, ringR * 1.05);
  if (panelWidth) extent = Math.max(extent, (panelWidth / 2) * 1.15);
  let top = Math.max(R * 1.55, ringR * 1.05);
  let bottom = -Math.max(R * 1.55, ringR * 1.05);
  if (geometry !== "swsi") top = Math.max(top, sfd - R + R * 0.55);
  if (panelWidth) bottom = Math.min(bottom, -R - R * 0.65);
  const transform = makeTransform(-extent, extent, bottom, top);

  const weldHeight = cap > 0 ? Math.min(cap, R * 0.3) : R * 0.08;
  const weldWidth = cap > 0 ? Math.min(2.5 * cap, R * 0.45) : R * 0.18;

  const beamColor = "var(--sketch-beam)";
  const detColor = "var(--sketch-det)";
  const elements: ReactNode[] = [];
  const labelItems: {
    text: string;
    x: number;
    y: number;
    size?: number;
    anchor?: "middle" | "start" | "end";
    fill?: string;
  }[] = [];

  // Circumferential N-station division ticks around pipe
  const totalStations = Math.max(1, nApplied > 0 ? nApplied : nRequired);
  if (totalStations > 1) {
    for (let st = 0; st < totalStations; st += 1) {
      const deg = -90 + (st * 360) / totalStations;
      const rad = (deg * Math.PI) / 180;
      const pIn = [R * 1.02 * Math.cos(rad), R * 1.02 * Math.sin(rad)];
      const pOut = [R * 1.13 * Math.cos(rad), R * 1.13 * Math.sin(rad)];
      elements.push(
        <line
          key={`st-tick-${st}`}
          x1={transform.X(pIn[0])}
          y1={transform.Y(pIn[1])}
          x2={transform.X(pOut[0])}
          y2={transform.Y(pOut[1])}
          stroke="var(--sketch-det)"
          strokeWidth={1.3}
          opacity={0.55}
        />,
      );
    }
  }

  // Highlight uninspected dead arc in red if nApplied > 0 && nApplied < nRequired
  if (nApplied > 0 && nApplied < nRequired) {
    const coveredDeg = (nApplied / nRequired) * 360;
    elements.push(
      <path
        key="dead-arc"
        d={arcPath(transform, R * 1.08, coveredDeg - 90, 270)}
        fill="none"
        stroke="#ef4444"
        strokeWidth={3}
        strokeDasharray="4 3"
      />,
    );
  }

  let ySourceCoord = 0;
  let xSourceCoord = 0;

  const renderBeamCone = (
    sx: number,
    sy: number,
    cxShift: number,
    t1: number,
    t2: number,
  ) => {
    const rDet = R * 1.04;
    const rad1 = (t1 * Math.PI) / 180;
    const rad2 = (t2 * Math.PI) / 180;
    let p1: [number, number] = [
      cxShift + rDet * Math.cos(rad1),
      rDet * Math.sin(rad1),
    ];
    let p2: [number, number] = [
      cxShift + rDet * Math.cos(rad2),
      rDet * Math.sin(rad2),
    ];
    let conePath: string;
    let midTarget: [number, number] = [cxShift, -rDet];

    if (panelWidth) {
      const yPanel = -R - R * 0.15;
      const halfPanel = (panelWidth / 2) * 0.92;
      const projectX = (px: number, py: number) => {
        const dy = py - sy;
        if (Math.abs(dy) < 1e-6) return px;
        const xAtPanel = sx + ((px - sx) * (yPanel - sy)) / dy;
        return Math.max(-halfPanel, Math.min(halfPanel, xAtPanel));
      };
      p1 = [projectX(p1[0], p1[1]), yPanel];
      p2 = [projectX(p2[0], p2[1]), yPanel];
      midTarget = [(p1[0] + p2[0]) / 2, yPanel];
      conePath = `M ${transform.X(sx)},${transform.Y(sy)} L ${transform.X(p1[0])},${transform.Y(p1[1])} L ${transform.X(p2[0])},${transform.Y(p2[1])} Z`;
    } else {
      const large = Math.abs(t2 - t1) > 180 ? 1 : 0;
      const sweep = t2 > t1 ? 0 : 1;
      const rScaled = rDet * transform.scale;
      conePath = `M ${transform.X(sx)},${transform.Y(sy)} L ${transform.X(p1[0])},${transform.Y(p1[1])} A ${rScaled} ${rScaled} 0 ${large} ${sweep} ${transform.X(p2[0])},${transform.Y(p2[1])} Z`;
    }

    return (
      <g key="beam-group">
        <path d={conePath} fill={beamColor} opacity={0.16} />
        <path d={conePath} fill="url(#beam-hatch-2d)" opacity={0.65} />
        <line
          x1={transform.X(sx)}
          y1={transform.Y(sy)}
          x2={transform.X(p1[0])}
          y2={transform.Y(p1[1])}
          stroke={beamColor}
          strokeWidth={1.5}
          strokeDasharray="5 3"
          opacity={0.85}
        />
        <line
          x1={transform.X(sx)}
          y1={transform.Y(sy)}
          x2={transform.X(p2[0])}
          y2={transform.Y(p2[1])}
          stroke={beamColor}
          strokeWidth={1.5}
          strokeDasharray="5 3"
          opacity={0.85}
        />
        <line
          x1={transform.X(sx)}
          y1={transform.Y(sy)}
          x2={transform.X(midTarget[0])}
          y2={transform.Y(midTarget[1])}
          stroke={beamColor}
          strokeWidth={1}
          strokeDasharray="3 3"
          opacity={0.45}
        />
      </g>
    );
  };

  if (geometry === "swsi") {
    elements.push(<SourceMarker key="s" transform={transform} kind="star" x={0} y={0} />);
    if (!panelWidth) {
      elements.push(
        <path
          key="det"
          d={arcPath(transform, R * 1.04, 180, 360)}
          fill="none"
          stroke={detColor}
          strokeWidth={4}
        />,
      );
    }
    elements.push(renderBeamCone(0, 0, 0, 225, 315));
    labelItems.push({ text: labels.source, x: 0, y: R * 1.35 });
  } else {
    const offset =
      geometry === "dwdi_elliptic"
        ? Math.min(sfd * Math.tan((15 * Math.PI) / 180), R * 0.9)
        : 0;
    const ySource = geometry === "dwsi" ? Math.max(R * 1.04, sfd - R) : sfd - R;
    xSourceCoord = offset;
    ySourceCoord = ySource;
    elements.push(
      <SourceMarker key="s" transform={transform} kind="dot" x={offset} y={ySource} />,
    );
    const arc: [number, number] =
      geometry === "dwsi"
        ? [220, 320]
        : geometry === "dwdi_elliptic"
          ? [200, 340]
          : [210, 330];
    const cx = geometry === "dwdi_elliptic" ? -offset * 0.5 : 0;
    if (!panelWidth) {
      elements.push(
        <path
          key="det"
          d={arcPath(transform, R * 1.04, arc[0], arc[1])}
          fill="none"
          stroke={detColor}
          strokeWidth={4}
          transform={`translate(${transform.X(cx) - transform.X(0)}, 0)`}
        />,
      );
    }
    elements.push(renderBeamCone(offset, ySource, cx, arc[0], arc[1]));
    labelItems.push({ text: labels.source, x: offset, y: ySource + R * 0.22 });
    if (geometry === "dwdi_elliptic") {
      // Source offset dimension arrow
      elements.push(
        <line
          key="offset-line"
          x1={transform.X(0)}
          y1={transform.Y(ySource)}
          x2={transform.X(offset)}
          y2={transform.Y(ySource)}
          stroke="var(--sketch-source)"
          strokeWidth={1.3}
          strokeDasharray="3 2"
        />,
      );
      labelItems.push({
        text: `${labels.sourceOffset}: ${offset.toFixed(0)} mm (Z-ekseni)`,
        x: offset / 2,
        y: ySource + R * 0.45,
        size: 9,
      });
      labelItems.push({
        text: `${labels.beamAngle} α ≈ 15°`,
        x: offset + R * 0.45,
        y: ySource - R * 0.18,
        size: 9,
      });
    }
  }

  elements.push(
    <WeldBump
      key="wt"
      transform={transform}
      x={0}
      y={R}
      weldWidth={weldWidth}
      weldHeight={weldHeight}
      inward={false}
    />,
  );
  elements.push(
    <WeldBump
      key="wti"
      transform={transform}
      x={0}
      y={Ri}
      weldWidth={weldWidth}
      weldHeight={weldHeight}
      inward={true}
    />,
  );
  elements.push(
    <WeldBump
      key="wb"
      transform={transform}
      x={0}
      y={-R}
      weldWidth={weldWidth}
      weldHeight={weldHeight}
      inward={true}
    />,
  );
  elements.push(
    <WeldBump
      key="wbi"
      transform={transform}
      x={0}
      y={-Ri}
      weldWidth={weldWidth}
      weldHeight={weldHeight}
      inward={false}
    />,
  );

  // IQI Placement marker on 2D cross-section
  const yIqi = filmSide
    ? -R * 1.04
    : geometry === "swsi"
      ? -Ri * 0.96
      : R * 1.06;
  elements.push(
    <g key="iqi-marker">
      <rect
        x={transform.X(R * 0.16) - 12}
        y={transform.Y(yIqi) - 6}
        width={24}
        height={12}
        rx={3}
        fill={geometry === "dwsi" && !filmSide ? "#ef4444" : "#0284c7"}
      />
      <text
        x={transform.X(R * 0.16)}
        y={transform.Y(yIqi) + 3}
        fontSize={8}
        fontWeight={700}
        fill="#ffffff"
        textAnchor="middle"
      >
        IQI
      </text>
    </g>,
  );

  // Dimension line for SFD / SDD on left side
  const dimX = -R * 1.28;
  const detBottomY = panelWidth ? -R - R * 0.15 : -R * 1.04;
  elements.push(
    <g key="sfd-dim" opacity={0.82}>
      <line
        x1={transform.X(dimX)}
        y1={transform.Y(ySourceCoord)}
        x2={transform.X(dimX)}
        y2={transform.Y(detBottomY)}
        stroke="var(--sketch-text)"
        strokeWidth={1}
        strokeDasharray="3 2"
      />
      <line
        x1={transform.X(dimX) - 4}
        y1={transform.Y(ySourceCoord)}
        x2={transform.X(xSourceCoord)}
        y2={transform.Y(ySourceCoord)}
        stroke="var(--sketch-text)"
        strokeWidth={0.7}
        strokeDasharray="2 3"
        opacity={0.5}
      />
      <line
        x1={transform.X(dimX) - 4}
        y1={transform.Y(detBottomY)}
        x2={transform.X(0)}
        y2={transform.Y(detBottomY)}
        stroke="var(--sketch-text)"
        strokeWidth={0.7}
        strokeDasharray="2 3"
        opacity={0.5}
      />
    </g>,
  );
  labelItems.push({
    text: `SFD=${sfd.toFixed(0)} mm`,
    x: dimX - R * 0.05,
    y: (ySourceCoord + detBottomY) / 2,
    size: 9,
    anchor: "end",
  });
  if (bDist > 0) {
    labelItems.push({
      text: `b=${bDist.toFixed(1)} mm${isPlanar && (bed > 0 || bgap > 0) ? ` (bed=${bed.toFixed(1)}, bgap=${bgap.toFixed(1)})` : ""}`,
      x: R * 1.12,
      y: -R * 0.85,
      size: 8.5,
      anchor: "start",
    });
  }
  if (fMin > 0 || ug > 0) {
    labelItems.push({
      text: `OD=${od.toFixed(1)} | t=${t.toFixed(2)} mm | N=${nApplied > 0 ? `${nApplied}/${nRequired}` : nRequired}`,
      x: 0,
      y: bottom + (top - bottom) * 0.04,
      size: 9.5,
    });
  }

  if (panelWidth) {
    const half = panelWidth / 2;
    const yPanel = -R - R * 0.15;
    const overlap = Math.max(10, (overlapPct / 100) * panelWidth);
    elements.push(
      <line
        key="panel"
        x1={transform.X(-half)}
        y1={transform.Y(yPanel)}
        x2={transform.X(half)}
        y2={transform.Y(yPanel)}
        stroke={detColor}
        strokeWidth={7}
      />,
    );
    elements.push(
      <line
        key="overlap"
        x1={transform.X(half - overlap)}
        y1={transform.Y(yPanel)}
        x2={transform.X(half)}
        y2={transform.Y(yPanel)}
        stroke="var(--sketch-weld)"
        strokeWidth={7}
      />,
    );
    // Show sagitta (b_ed) gap between pipe outer curve and flat panel edge
    const edgeX = Math.min(half * 0.85, R * 0.92);
    const pipeEdgeY = -Math.sqrt(Math.max(0, R * R - edgeX * edgeX));
    elements.push(
      <line
        key="bed-indicator"
        x1={transform.X(-edgeX)}
        y1={transform.Y(pipeEdgeY)}
        x2={transform.X(-edgeX)}
        y2={transform.Y(yPanel)}
        stroke="var(--sketch-weld)"
        strokeWidth={1.3}
        strokeDasharray="2 2"
      />,
    );
    labelItems.push({
      text: `${labels.overlap} ${overlap.toFixed(0)} mm`,
      x: half - overlap / 2,
      y: yPanel + R * 0.28,
      size: 9,
    });
    labelItems.push({
      text: `${labels.dda} ${panelWidth.toFixed(0)} mm`,
      x: 0,
      y: yPanel - R * 0.25,
      size: 9,
    });
  }

  if (ringR > 0) {
    elements.push(
      <circle
        key="ring"
        cx={transform.X(0)}
        cy={transform.Y(0)}
        r={ringR * transform.scale}
        fill="none"
        stroke="var(--sketch-weld)"
        strokeWidth={1.5}
        strokeDasharray="6 5"
        opacity={0.75}
      />,
    );
    labelItems.push({
      text: `${labels.safety}: R≈${(safetyRadiusM ?? 0).toFixed(0)} m`,
      x: ringR * 0.5,
      y: ringR * 0.5,
      size: 9,
    });
  }

  // True Metre-Scale Radiation Perimeter Inset (top-right corner, matching desktop sketch.py)
  const showBarrierInset = Boolean(safetyRadiusM && safetyRadiusM > 0);
  const rCtrl = safetyRadiusM ?? 0;
  const rSup = supervisedRadiusM && supervisedRadiusM > rCtrl ? supervisedRadiusM : rCtrl * 1.63;
  const insetCx = W - 64;
  const insetCy = 60;
  const insetMaxR = 42;
  const ctrlR = rSup > 0 ? Math.max(8, (rCtrl / rSup) * insetMaxR) : insetMaxR;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="sketch-svg" role="img" aria-label={labels.pipe}>
      <defs>
        <pattern
          id="beam-hatch-2d"
          width="7"
          height="7"
          patternTransform="rotate(45 0 0)"
          patternUnits="userSpaceOnUse"
        >
          <line
            x1="0"
            y1="0"
            x2="0"
            y2="7"
            stroke={beamColor}
            strokeWidth="1.2"
            opacity="0.55"
          />
        </pattern>
      </defs>
      <circle
        cx={transform.X(0)}
        cy={transform.Y(0)}
        r={R * transform.scale}
        fill="none"
        stroke="var(--sketch-pipe)"
        strokeWidth={2}
      />
      <circle
        cx={transform.X(0)}
        cy={transform.Y(0)}
        r={Ri * transform.scale}
        fill="none"
        stroke="var(--sketch-pipe)"
        strokeWidth={1.5}
        strokeDasharray="7 5"
      />
      {elements}
      <Labels transform={transform} labels={labelItems} />

      {showBarrierInset && (
        <g className="barrier-inset">
          <rect
            x={W - 122}
            y={8}
            width={114}
            height={106}
            rx={6}
            fill="var(--bg-alt)"
            stroke="var(--border)"
            strokeWidth={1}
            opacity={0.92}
          />
          <text
            x={insetCx}
            y={20}
            fontSize={8.5}
            fontWeight={700}
            fill="var(--sketch-text)"
            textAnchor="middle"
          >
            Barikat Haritası (m)
          </text>
          <circle
            cx={insetCx}
            cy={insetCy + 6}
            r={insetMaxR}
            fill="rgba(245, 158, 11, 0.08)"
            stroke="#f59e0b"
            strokeWidth={1.2}
            strokeDasharray="3 2"
          />
          <circle
            cx={insetCx}
            cy={insetCy + 6}
            r={ctrlR}
            fill="rgba(239, 68, 68, 0.14)"
            stroke="#ef4444"
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
          <circle cx={insetCx} cy={insetCy + 6} r={2.5} fill="#ef4444" />
          <text
            x={insetCx}
            y={insetCy + 6 - ctrlR + 9}
            fontSize={7.5}
            fill="#ef4444"
            textAnchor="middle"
          >
            {rCtrl.toFixed(1)}m
          </text>
          <text
            x={insetCx}
            y={insetCy + 6 + insetMaxR - 3}
            fontSize={7.5}
            fill="#f59e0b"
            textAnchor="middle"
          >
            {rSup.toFixed(1)}m (7.5 µSv/h)
          </text>
        </g>
      )}
    </svg>
  );
}

export interface AnnexAChartProps {
  figure?: string;
  tOverDe?: number;
  ratioName?: string;
  ratio?: number;
  n?: number;
  nextN?: number | null;
  nextRatio?: number | null;
  nextDistanceMm?: number | null;
  boundaries?: [number, number][];
  lang?: string;
}

/** Interactive Annex A Nomogram / Operating Point Chart */
export function AnnexAChartSvg({
  figure = "A.2",
  tOverDe = 0.05,
  ratioName = "De/SFD",
  ratio = 0.28,
  n = 4,
  nextN = null,
  nextRatio = null,
  nextDistanceMm = null,
  boundaries = [],
  lang = "tr",
}: AnnexAChartProps) {
  const tr = lang === "tr";
  const padL = 52;
  const padR = 24;
  const padT = 34;
  const padB = 44;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const maxX = Math.max(0.22, tOverDe * 1.3);
  const maxY = Math.max(1.0, ratio * 1.35, nextRatio ? nextRatio * 1.25 : 0.8);

  const toX = (val: number) => padL + Math.min(1, Math.max(0, val / maxX)) * plotW;
  const toY = (val: number) => padT + plotH - Math.min(1, Math.max(0, val / maxY)) * plotH;

  const opX = toX(tOverDe);
  const opY = toY(ratio);

  // Sort boundaries by threshold
  const sortedBounds = [...boundaries].sort((a, b) => a[0] - b[0]);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="annex-a-svg"
      role="img"
      aria-label={`ISO 17636 Annex A ${figure}`}
    >
      <rect
        x={padL}
        y={padT}
        width={plotW}
        height={plotH}
        fill="var(--bg)"
        stroke="var(--border)"
        strokeWidth={1.2}
      />

      {/* Horizontal zone bands from Annex A boundaries */}
      {sortedBounds.map(([boundVal, expCount], idx) => {
        const prevVal = idx === 0 ? 0 : sortedBounds[idx - 1][0];
        const yTop = toY(Math.min(maxY, boundVal));
        const yBot = toY(Math.min(maxY, prevVal));
        if (yBot <= yTop) return null;
        const isCurrentZone = expCount === n;
        return (
          <g key={`zone-${idx}`}>
            <rect
              x={padL}
              y={yTop}
              width={plotW}
              height={Math.max(0, yBot - yTop)}
              fill={
                isCurrentZone
                  ? "rgba(16, 185, 129, 0.16)"
                  : idx % 2 === 0
                    ? "rgba(148, 163, 184, 0.05)"
                    : "transparent"
              }
            />
            <line
              x1={padL}
              y1={yTop}
              x2={padL + plotW}
              y2={yTop}
              stroke={isCurrentZone ? "#10b981" : "var(--border)"}
              strokeWidth={isCurrentZone ? 1.5 : 1}
              strokeDasharray="4 3"
            />
            <text
              x={padL + plotW - 8}
              y={(yTop + yBot) / 2 + 4}
              fontSize={10}
              fontWeight={isCurrentZone ? 700 : 500}
              fill={isCurrentZone ? "#10b981" : "var(--sketch-text)"}
              textAnchor="end"
            >
              N = {expCount} {tr ? "Poz" : "Exp"} ({ratioName} ≤ {boundVal.toFixed(2)})
            </text>
          </g>
        );
      })}

      {/* Axes grid & ticks */}
      {[0, 0.05, 0.1, 0.15, 0.2].map((xv) => {
        if (xv > maxX) return null;
        const px = toX(xv);
        return (
          <g key={`xt-${xv}`}>
            <line
              x1={px}
              y1={padT}
              x2={px}
              y2={padT + plotH}
              stroke="var(--border)"
              strokeWidth={0.6}
              opacity={0.4}
            />
            <text
              x={px}
              y={padT + plotH + 15}
              fontSize={9.5}
              fill="var(--sketch-text)"
              textAnchor="middle"
            >
              {xv.toFixed(2)}
            </text>
          </g>
        );
      })}
      {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map((yv) => {
        if (yv > maxY) return null;
        const py = toY(yv);
        return (
          <g key={`yt-${yv}`}>
            <text
              x={padL - 6}
              y={py + 3}
              fontSize={9.5}
              fill="var(--sketch-text)"
              textAnchor="end"
            >
              {yv.toFixed(2)}
            </text>
          </g>
        );
      })}

      {/* Next exposure boundary target arrow */}
      {nextRatio != null && nextN != null && (
        <g>
          <line
            x1={opX}
            y1={opY}
            x2={opX}
            y2={toY(nextRatio)}
            stroke="#f59e0b"
            strokeWidth={2}
            strokeDasharray="3 2"
          />
          <circle cx={opX} cy={toY(nextRatio)} r={4} fill="#f59e0b" />
          <text
            x={Math.min(padL + plotW - 10, Math.max(padL + 10, opX + 10))}
            y={toY(nextRatio) - 6}
            fontSize={9.5}
            fontWeight={600}
            fill="#f59e0b"
            textAnchor={opX > W * 0.6 ? "end" : "start"}
          >
            {tr
              ? `N=${nextN} sınırı: ${ratioName}=${nextRatio.toFixed(3)}${nextDistanceMm ? ` (SFD ≥ ${nextDistanceMm.toFixed(0)} mm)` : ""}`
              : `N=${nextN} limit: ${ratioName}=${nextRatio.toFixed(3)}${nextDistanceMm ? ` (SFD ≥ ${nextDistanceMm.toFixed(0)} mm)` : ""}`}
          </text>
        </g>
      )}

      {/* Operating point crosshair & marker */}
      <line
        x1={opX}
        y1={padT}
        x2={opX}
        y2={padT + plotH}
        stroke="var(--sketch-source)"
        strokeWidth={1}
        strokeDasharray="3 3"
      />
      <line
        x1={padL}
        y1={opY}
        x2={padL + plotW}
        y2={opY}
        stroke="var(--sketch-source)"
        strokeWidth={1}
        strokeDasharray="3 3"
      />
      <circle
        cx={opX}
        cy={opY}
        r={11}
        fill="var(--sketch-source)"
        opacity={0.22}
      />
      <circle
        cx={opX}
        cy={opY}
        r={5.5}
        fill="var(--sketch-source)"
        stroke="#ffffff"
        strokeWidth={1.5}
      />
      <text
        x={opX > W * 0.65 ? opX - 10 : opX + 10}
        y={opY - 10}
        fontSize={10.5}
        fontWeight={700}
        fill="var(--sketch-text)"
        textAnchor={opX > W * 0.65 ? "end" : "start"}
      >
        {tr ? "Çalışma Noktası" : "Operating Point"} (N={n})
      </text>

      {/* Titles */}
      <text
        x={W / 2}
        y={20}
        fontSize={12}
        fontWeight={700}
        fill="var(--sketch-text)"
        textAnchor="middle"
      >
        ISO 17636 Annex A ({figure}) — t/De = {tOverDe.toFixed(4)} | {ratioName} ={" "}
        {ratio.toFixed(3)}
      </text>
      <text
        x={padL + plotW / 2}
        y={H - 10}
        fontSize={10.5}
        fontWeight={600}
        fill="var(--sketch-text)"
        textAnchor="middle"
      >
        t / De ({tr ? "Et Kalınlığı / Dış Çap Oranı" : "Wall Thickness / OD Ratio"})
      </text>
      <text
        x={14}
        y={padT + plotH / 2}
        fontSize={10.5}
        fontWeight={600}
        fill="var(--sketch-text)"
        textAnchor="middle"
        transform={`rotate(-90, 14, ${padT + plotH / 2})`}
      >
        {ratioName}
      </text>
    </svg>
  );
}

/** 300 mm (12 inch) Weld Strip Defect Visualizer */
export function DefectStripSvg({
  defectType,
  lengthMm,
  widthMm,
  accumulatedMm,
  wallT,
  accepted,
  lang = "tr",
}: {
  defectType: string;
  lengthMm: number;
  widthMm: number;
  accumulatedMm: number;
  wallT: number;
  accepted: boolean | null;
  lang?: string;
}) {
  const tr = lang === "tr";
  const stripLenMm = 300;
  const svgW = 400;
  const svgH = 115;
  const padX = 24;
  const stripW = svgW - padX * 2;
  const stripY = 26;
  const stripH = 34;

  const pxPerMm = stripW / stripLenMm;
  const singleW = Math.min(stripW, Math.max(4, lengthMm * pxPerMm));
  const singleH = Math.min(stripH - 6, Math.max(4, (widthMm / Math.max(wallT, 4)) * stripH));
  const accumW = Math.min(stripW, Math.max(0, accumulatedMm * pxPerMm));

  const statusColor =
    accepted === null ? "#f59e0b" : accepted ? "#10b981" : "#ef4444";

  return (
    <svg
      viewBox={`0 0 ${svgW} ${svgH}`}
      className="defect-strip-svg"
      role="img"
      aria-label={tr ? "300 mm Kaynak Şeridi Kusur Haritası" : "300 mm Weld Strip Defect Map"}
    >
      <text
        x={padX}
        y={16}
        fontSize={10}
        fontWeight={600}
        fill="var(--sketch-text)"
      >
        {tr
          ? `300 mm (12") Kaynak Değerlendirme Şeridi — t = ${wallT.toFixed(2)} mm`
          : `300 mm (12") Weld Evaluation Strip — t = ${wallT.toFixed(2)} mm`}
      </text>

      {/* Weld seam background */}
      <rect
        x={padX}
        y={stripY}
        width={stripW}
        height={stripH}
        rx={4}
        fill="var(--bg)"
        stroke="var(--border)"
        strokeWidth={1.2}
      />
      {/* Weld centerline */}
      <line
        x1={padX}
        y1={stripY + stripH / 2}
        x2={padX + stripW}
        y2={stripY + stripH / 2}
        stroke="var(--border)"
        strokeWidth={0.8}
        strokeDasharray="4 3"
      />

      {/* Primary defect shape */}
      {defectType === "defect_porosity" ? (
        <g>
          <circle
            cx={padX + 45}
            cy={stripY + stripH / 2}
            r={Math.max(3, singleH / 2)}
            fill={statusColor}
          />
          <circle
            cx={padX + 45 + Math.min(25, singleW * 0.5)}
            cy={stripY + stripH / 2 - 4}
            r={Math.max(2.5, singleH * 0.38)}
            fill={statusColor}
            opacity={0.8}
          />
          <circle
            cx={padX + 45 + Math.min(45, singleW * 0.85)}
            cy={stripY + stripH / 2 + 3}
            r={Math.max(2, singleH * 0.32)}
            fill={statusColor}
            opacity={0.7}
          />
        </g>
      ) : (
        <rect
          x={padX + 28}
          y={stripY + (stripH - singleH) / 2}
          width={singleW}
          height={singleH}
          rx={defectType === "defect_crack" ? 0.5 : 2.5}
          fill={statusColor}
          opacity={0.88}
        />
      )}

      <text
        x={padX + 32 + singleW + 6}
        y={stripY + stripH / 2 + 3}
        fontSize={9.5}
        fontWeight={600}
        fill={statusColor}
      >
        L={lengthMm} mm × W={widthMm} mm
      </text>

      {/* Accumulated defect length gauge along 300 mm reference */}
      <text
        x={padX}
        y={80}
        fontSize={9.5}
        fill="var(--sketch-text)"
      >
        {tr
          ? `12" (300 mm) Birikimli Kusur: ${accumulatedMm} / 300 mm`
          : `12" (300 mm) Accumulated: ${accumulatedMm} / 300 mm`}
      </text>
      <rect
        x={padX}
        y={86}
        width={stripW}
        height={10}
        rx={5}
        fill="var(--bg)"
        stroke="var(--border)"
        strokeWidth={1}
      />
      <rect
        x={padX}
        y={86}
        width={accumW}
        height={10}
        rx={5}
        fill={statusColor}
      />
      {/* 25 mm (1 in) API 1104 reference limit tick */}
      <line
        x1={padX + 25 * pxPerMm}
        y1={83}
        x2={padX + 25 * pxPerMm}
        y2={100}
        stroke="#f59e0b"
        strokeWidth={1.5}
      />
      <text
        x={padX + 25 * pxPerMm + 4}
        y={109}
        fontSize={8.5}
        fill="#f59e0b"
      >
        25 mm (1&quot;) ref
      </text>
    </svg>
  );
}

interface FigureSpec {
  alias?: string;
  source: { kind: "star" | "dot"; x: number; y: number; label?: string };
  detector: {
    kind: "outer" | "inner" | "circle" | "flat";
    t1?: number;
    t2?: number;
    x1?: number;
    x2?: number;
    y?: number;
  };
  beams?: { from: [number, number]; angles: [number, number]; radius: number }[];
  welds?: [number, number][];
  labels?: { text: string; x: number; y: number; size?: number }[];
}

const FIGURES: Record<string, FigureSpec> = {
  fig5: {
    source: { kind: "star", x: 0, y: 0, label: "S (Panoramic)" },
    detector: { kind: "circle" },
    beams: [
      { from: [0, 0], angles: [0, 90], radius: 1 },
      { from: [0, 0], angles: [180, 270], radius: 1 },
    ],
    labels: [{ text: "f = R\nb = t", x: 0.2, y: -0.5, size: 10 }],
  },
  fig6: {
    source: { kind: "star", x: 0, y: 0.5, label: "S" },
    detector: { kind: "outer", t1: 220, t2: 320 },
    beams: [{ from: [0, 0.5], angles: [220, 320], radius: 1 }],
    labels: [{ text: "f", x: -0.25, y: -0.3, size: 11 }],
  },
  fig7: {
    source: { kind: "dot", x: 0, y: 1.8, label: "S" },
    detector: { kind: "inner", t1: 220, t2: 320 },
    beams: [{ from: [0, 1.8], angles: [215, 325], radius: 0.8 }],
    labels: [
      { text: "f", x: -0.25, y: 0.2, size: 11 },
      { text: "b = t", x: -0.25, y: -0.9, size: 11 },
    ],
  },
  fig11: {
    source: { kind: "dot", x: 0.4, y: 1.8, label: "S" },
    detector: { kind: "flat", x1: -1.2, x2: 1.2, y: -1.2 },
    beams: [{ from: [0.4, 1.8], angles: [200, 340], radius: 1.2 }],
    welds: [
      [0.2, 1],
      [-0.2, -1],
    ],
    labels: [
      { text: "b = OD", x: -0.5, y: 0, size: 10 },
      { text: "f", x: 0.6, y: 0.8, size: 10 },
      { text: "Film / Detector", x: 0, y: -1.4, size: 9 },
    ],
  },
  fig12: {
    source: { kind: "dot", x: 0, y: 1.8, label: "S" },
    detector: { kind: "flat", x1: -1.2, x2: 1.2, y: -1.2 },
    beams: [{ from: [0, 1.8], angles: [215, 325], radius: 1.2 }],
    welds: [
      [0, 1],
      [0, -1],
    ],
  },
  fig13: {
    source: { kind: "dot", x: 0, y: 1.8, label: "S" },
    detector: { kind: "outer", t1: 220, t2: 320 },
    beams: [{ from: [0, 1.8], angles: [220, 320], radius: 1 }],
    labels: [
      { text: "f = SFD - t", x: -0.55, y: 0.3, size: 10 },
      { text: "b = t", x: -0.5, y: -0.9, size: 10 },
    ],
  },
  fig14: {
    source: { kind: "dot", x: 0, y: 1, label: "S" },
    detector: { kind: "outer", t1: 220, t2: 320 },
    beams: [{ from: [0, 1], angles: [220, 320], radius: 1 }],
    labels: [
      { text: "f'", x: -0.55, y: 0.35, size: 10 },
      { text: "b = t", x: -0.5, y: -0.95, size: 10 },
    ],
  },
  fig8b: {
    source: { kind: "star", x: 0, y: 0, label: "S (Panoramic)" },
    detector: { kind: "circle" },
    beams: [
      { from: [0, 0], angles: [0, 90], radius: 1 },
      { from: [0, 0], angles: [180, 270], radius: 1 },
    ],
    labels: [{ text: "f = R\nb = t", x: 0.2, y: -0.5, size: 10 }],
  },
  fig9b: {
    source: { kind: "star", x: 0, y: 0.5, label: "S" },
    detector: { kind: "inner", t1: 220, t2: 320 },
    beams: [{ from: [0, 0.5], angles: [220, 320], radius: 0.8 }],
    labels: [{ text: "f", x: -0.25, y: -0.3, size: 11 }],
  },
  fig10b: {
    source: { kind: "dot", x: 0, y: 1.8, label: "S" },
    detector: { kind: "outer", t1: 220, t2: 320 },
    beams: [{ from: [0, 1.8], angles: [220, 320], radius: 1 }],
    labels: [
      { text: "f = SFD - t", x: -0.55, y: 0.3, size: 10 },
      { text: "b = t", x: -0.5, y: -0.9, size: 10 },
    ],
  },
  fig14b: {
    source: { kind: "dot", x: 0.4, y: 1.8, label: "S" },
    detector: { kind: "outer", t1: 200, t2: 340 },
    beams: [{ from: [0.4, 1.8], angles: [200, 340], radius: 1.2 }],
    welds: [
      [0.2, 1],
      [-0.2, -1],
    ],
    labels: [
      { text: "b = OD", x: -0.5, y: 0, size: 10 },
      { text: "f", x: 0.6, y: 0.8, size: 10 },
    ],
  },
  fig2b: {
    source: { kind: "dot", x: 0, y: 1.8, label: "S" },
    detector: { kind: "flat", x1: -0.9, x2: 0.9, y: -1.15 },
    beams: [{ from: [0, 1.8], angles: [230, 310], radius: 1.15 }],
    welds: [[0, 1]],
    labels: [
      { text: "f", x: -0.6, y: 0.4, size: 10 },
      { text: "b = b_ed + b_gap + k·t", x: 0, y: -1.35, size: 9 },
    ],
  },
  fig5b: {
    source: { kind: "star", x: 0, y: 0, label: "S (Panoramic)" },
    detector: { kind: "flat", x1: -0.9, x2: 0.9, y: -1.25 },
    beams: [{ from: [0, 0], angles: [230, 310], radius: 1.25 }],
    labels: [{ text: "f = R\nb = b_ed + b_gap + t", x: 0.15, y: -0.55, size: 9 }],
  },
  fig8a: {
    source: { kind: "star", x: 0, y: 0.5, label: "S" },
    detector: { kind: "outer", t1: 220, t2: 320 },
    beams: [{ from: [0, 0.5], angles: [220, 320], radius: 1 }],
    labels: [
      { text: "f", x: -0.6, y: -0.2, size: 10 },
      { text: "b = t", x: -0.5, y: -1, size: 10 },
    ],
  },
  fig9a: {
    source: { kind: "star", x: 0, y: 0.75, label: "S" },
    detector: { kind: "inner", t1: 220, t2: 320 },
    beams: [{ from: [0, 0.75], angles: [220, 320], radius: 0.8 }],
    labels: [
      { text: "f", x: -0.5, y: -0.1, size: 10 },
      { text: "b = t", x: -0.4, y: -0.8, size: 10 },
    ],
  },
  fig10a: {
    source: { kind: "star", x: 0, y: 0.2, label: "S" },
    detector: { kind: "outer", t1: 230, t2: 310 },
    beams: [{ from: [0, 0.2], angles: [215, 325], radius: 1 }],
    labels: [
      { text: "f", x: -0.5, y: -0.3, size: 10 },
      { text: "b = t", x: -0.4, y: -1, size: 10 },
    ],
  },
  fig13b: {
    source: { kind: "dot", x: 0, y: 1.8, label: "S" },
    detector: { kind: "flat", x1: -0.9, x2: 0.9, y: -1.15 },
    beams: [{ from: [0, 1.8], angles: [230, 310], radius: 1.15 }],
    welds: [[-0.2, -1]],
    labels: [
      { text: "f'", x: -0.7, y: 0.3, size: 10 },
      { text: "b = b_ed + b_gap + k·t", x: 0, y: -1.35, size: 9 },
    ],
  },
};

export function StandardFigureSvg({ figure, title }: { figure: string; title: string }) {
  const alias: Record<string, string> = {
    fig2: "fig2b",
    fig2a: "fig2b",
    fig5a: "fig5",
    fig6a: "fig6",
    fig7a: "fig7",
    fig13a: "fig13",
    fig14a: "fig14",
  };
  const spec = FIGURES[alias[figure] ?? figure] ?? FIGURES.fig13;
  const transform = makeTransform(-2, 2, -2, 2.5);
  const detColor = "var(--sketch-det)";
  const beamColor = "var(--sketch-beam)";

  const detectorPath = () => {
    const detector = spec.detector;
    if (detector.kind === "circle") {
      return (
        <circle
          cx={transform.X(0)}
          cy={transform.Y(0)}
          r={1.08 * transform.scale}
          fill="none"
          stroke={detColor}
          strokeWidth={3}
        />
      );
    }
    if (detector.kind === "flat") {
      return (
        <line
          x1={transform.X(detector.x1 ?? -1)}
          y1={transform.Y(detector.y ?? -1.2)}
          x2={transform.X(detector.x2 ?? 1)}
          y2={transform.Y(detector.y ?? -1.2)}
          stroke={detColor}
          strokeWidth={5}
        />
      );
    }
    const radius = detector.kind === "inner" ? 0.8 : 1.04;
    return (
      <path
        d={arcPath(transform, radius, detector.t1 ?? 220, detector.t2 ?? 320)}
        fill="none"
        stroke={detColor}
        strokeWidth={5}
      />
    );
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="sketch-svg" role="img" aria-label={title}>
      <defs>
        <pattern
          id="beam-hatch-std"
          width="7"
          height="7"
          patternTransform="rotate(45 0 0)"
          patternUnits="userSpaceOnUse"
        >
          <line
            x1="0"
            y1="0"
            x2="0"
            y2="7"
            stroke={beamColor}
            strokeWidth="1.2"
            opacity="0.5"
          />
        </pattern>
      </defs>
      <circle
        cx={transform.X(0)}
        cy={transform.Y(0)}
        r={1 * transform.scale}
        fill="none"
        stroke="var(--sketch-pipe)"
        strokeWidth={2}
      />
      <circle
        cx={transform.X(0)}
        cy={transform.Y(0)}
        r={0.8 * transform.scale}
        fill="none"
        stroke="var(--sketch-pipe)"
        strokeWidth={1.5}
        strokeDasharray="7 5"
      />
      {spec.beams?.map((beam, index) => {
        const [a1, a2] = beam.angles;
        let p1: [number, number] = [
          beam.radius * Math.cos((a1 * Math.PI) / 180),
          beam.radius * Math.sin((a1 * Math.PI) / 180),
        ];
        let p2: [number, number] = [
          beam.radius * Math.cos((a2 * Math.PI) / 180),
          beam.radius * Math.sin((a2 * Math.PI) / 180),
        ];
        let conePath: string;
        if (spec.detector.kind === "flat") {
          const yFlat = spec.detector.y ?? -1.2;
          const xMin = spec.detector.x1 ?? -1;
          const xMax = spec.detector.x2 ?? 1;
          const projX = (px: number, py: number) => {
            const dy = py - beam.from[1];
            if (Math.abs(dy) < 1e-6) return px;
            const xAt = beam.from[0] + ((px - beam.from[0]) * (yFlat - beam.from[1])) / dy;
            return Math.max(xMin, Math.min(xMax, xAt));
          };
          p1 = [projX(p1[0], p1[1]), yFlat];
          p2 = [projX(p2[0], p2[1]), yFlat];
          conePath = `M ${transform.X(beam.from[0])},${transform.Y(beam.from[1])} L ${transform.X(p1[0])},${transform.Y(p1[1])} L ${transform.X(p2[0])},${transform.Y(p2[1])} Z`;
        } else {
          const rArc =
            spec.detector.kind === "inner"
              ? 0.8
              : spec.detector.kind === "circle"
                ? 1.08
                : 1.04;
          p1 = [
            rArc * Math.cos((a1 * Math.PI) / 180),
            rArc * Math.sin((a1 * Math.PI) / 180),
          ];
          p2 = [
            rArc * Math.cos((a2 * Math.PI) / 180),
            rArc * Math.sin((a2 * Math.PI) / 180),
          ];
          const large = Math.abs(a2 - a1) > 180 ? 1 : 0;
          const sweep = a2 > a1 ? 0 : 1;
          const rScaled = rArc * transform.scale;
          conePath = `M ${transform.X(beam.from[0])},${transform.Y(beam.from[1])} L ${transform.X(p1[0])},${transform.Y(p1[1])} A ${rScaled} ${rScaled} 0 ${large} ${sweep} ${transform.X(p2[0])},${transform.Y(p2[1])} Z`;
        }
        return (
          <g key={index}>
            <path d={conePath} fill={beamColor} opacity={0.14} />
            <path d={conePath} fill="url(#beam-hatch-std)" opacity={0.55} />
            <line
              x1={transform.X(beam.from[0])}
              y1={transform.Y(beam.from[1])}
              x2={transform.X(p1[0])}
              y2={transform.Y(p1[1])}
              stroke={beamColor}
              strokeWidth={1.3}
              strokeDasharray="4 3"
            />
            <line
              x1={transform.X(beam.from[0])}
              y1={transform.Y(beam.from[1])}
              x2={transform.X(p2[0])}
              y2={transform.Y(p2[1])}
              stroke={beamColor}
              strokeWidth={1.3}
              strokeDasharray="4 3"
            />
          </g>
        );
      })}
      {detectorPath()}
      {spec.welds?.map(([x, y], index) => (
        <rect
          key={index}
          x={transform.X(x) - 5}
          y={transform.Y(y) - 5}
          width={10}
          height={10}
          fill="var(--sketch-weld)"
        />
      ))}
      <SourceMarker
        transform={transform}
        kind={spec.source.kind}
        x={spec.source.x}
        y={spec.source.y}
      />
      {spec.source.label && (
        <text
          x={transform.X(spec.source.x) + 12}
          y={transform.Y(spec.source.y) - 8}
          fontSize={11}
          fontWeight={700}
          fill="var(--sketch-text)"
        >
          {spec.source.label}
        </text>
      )}
      <Labels
        transform={transform}
        labels={(spec.labels ?? []).map((label) => ({ ...label, size: label.size }))}
      />
      <text
        x={W / 2}
        y={20}
        fontSize={12}
        fontWeight={600}
        fill="var(--sketch-text)"
        textAnchor="middle"
      >
        {title}
      </text>
    </svg>
  );
}
