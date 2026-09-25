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

function SourceMarker({ transform, kind, x, y }: { transform: Transform; kind: "star" | "dot"; x: number; y: number }) {
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
          fill="var(--sketch-text)"
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
  panelWidth?: number | null;
  panelHeight?: number | null;
  overlapPct?: number;
  safetyRadiusM?: number | null;
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
  panelWidth,
  overlapPct = 10,
  safetyRadiusM,
  labels,
}: WeldSetupProps) {
  const R = Math.max(od / 2, 1);
  const Ri = Math.max(R - t, R * 0.05);
  const ringR =
    safetyRadiusM && safetyRadiusM > 0
      ? Math.max(R * 1.8, Math.min(safetyRadiusM * 0.05, R * 4))
      : 0;

  let extent = Math.max(R * 1.5, ringR * 1.05);
  if (panelWidth) extent = Math.max(extent, (panelWidth / 2) * 1.1);
  let top = Math.max(R * 1.5, ringR * 1.05);
  let bottom = -Math.max(R * 1.5, ringR * 1.05);
  if (geometry !== "swsi") top = Math.max(top, sfd - R + R * 0.5);
  if (panelWidth) bottom = Math.min(bottom, -R - R * 0.6);
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
  }[] = [];

  if (geometry === "swsi") {
    elements.push(<SourceMarker key="s" transform={transform} kind="star" x={0} y={0} />);
    elements.push(
      <path key="det" d={arcPath(transform, R * 1.04, 180, 360)} fill="none" stroke={detColor} strokeWidth={4} />,
    );
    elements.push(
      <polygon
        key="beam"
        points={`${transform.X(0)},${transform.Y(0)} ${transform.X(-R * 0.2)},${transform.Y(-R)} ${transform.X(R * 0.2)},${transform.Y(-R)}`}
        fill={beamColor}
        opacity={0.15}
      />,
    );
    labelItems.push({ text: labels.source, x: 0, y: R * 1.35 });
  } else {
    const offset =
      geometry === "dwdi_elliptic" ? Math.min(sfd * Math.tan((15 * Math.PI) / 180), R * 0.9) : 0;
    const ySource = sfd - R;
    elements.push(
      <SourceMarker key="s" transform={transform} kind="dot" x={offset} y={ySource} />,
    );
    const arc = geometry === "dwsi" ? [220, 320] : geometry === "dwdi_elliptic" ? [200, 340] : [210, 330];
    const cx = geometry === "dwdi_elliptic" ? -offset * 0.5 : 0;
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
    const spread = geometry === "dwdi_elliptic" ? [-50, 30] : [-40, 40];
    const targets = spread.map((angle) => {
      const rad = (angle * Math.PI) / 180;
      return [cx + R * Math.cos(rad), R * Math.sin(rad)] as [number, number];
    });
    elements.push(
      <polygon
        key="beam"
        points={`${transform.X(offset)},${transform.Y(ySource)} ${transform.X(targets[0][0])},${transform.Y(targets[0][1])} ${transform.X(targets[1][0])},${transform.Y(targets[1][1])}`}
        fill={beamColor}
        opacity={0.15}
      />,
    );
    labelItems.push({ text: labels.source, x: offset, y: ySource + R * 0.22 });
    if (geometry === "dwdi_elliptic") {
      labelItems.push({ text: `${labels.sourceOffset}: ${offset.toFixed(0)} mm`, x: offset / 2, y: ySource + R * 0.5, size: 9 });
      labelItems.push({ text: `${labels.beamAngle} α ≈ 15°`, x: offset + R * 0.5, y: ySource - R * 0.2, size: 9 });
    }
  }

  elements.push(<WeldBump key="wt" transform={transform} x={0} y={R} weldWidth={weldWidth} weldHeight={weldHeight} inward={false} />);
  elements.push(<WeldBump key="wti" transform={transform} x={0} y={Ri} weldWidth={weldWidth} weldHeight={weldHeight} inward={true} />);
  elements.push(<WeldBump key="wb" transform={transform} x={0} y={-R} weldWidth={weldWidth} weldHeight={weldHeight} inward={true} />);
  elements.push(<WeldBump key="wbi" transform={transform} x={0} y={-Ri} weldWidth={weldWidth} weldHeight={weldHeight} inward={false} />);

  if (panelWidth) {
    const half = panelWidth / 2;
    const yPanel = -R - R * 0.15;
    const overlap = Math.max(10, (overlapPct / 100) * panelWidth);
    elements.push(
      <line key="panel" x1={transform.X(-half)} y1={transform.Y(yPanel)} x2={transform.X(half)} y2={transform.Y(yPanel)} stroke={detColor} strokeWidth={7} />,
    );
    elements.push(
      <line key="overlap" x1={transform.X(half - overlap)} y1={transform.Y(yPanel)} x2={transform.X(half)} y2={transform.Y(yPanel)} stroke="var(--sketch-weld)" strokeWidth={7} />,
    );
    labelItems.push({ text: `${labels.overlap} ${overlap.toFixed(0)} mm`, x: half - overlap / 2, y: yPanel + R * 0.28, size: 9 });
    labelItems.push({ text: `${labels.dda} ${panelWidth.toFixed(0)} mm`, x: 0, y: yPanel - R * 0.28, size: 9 });
  }

  if (ringR > 0) {
    elements.push(
      <circle key="ring" cx={transform.X(0)} cy={transform.Y(0)} r={ringR * transform.scale} fill="none" stroke="var(--sketch-weld)" strokeWidth={1.5} strokeDasharray="6 5" opacity={0.75} />,
    );
    labelItems.push({ text: `${labels.safety}: R≈${(safetyRadiusM ?? 0).toFixed(0)} m`, x: ringR * 0.5, y: ringR * 0.5, size: 9 });
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="sketch-svg" role="img" aria-label={labels.pipe}>
      <circle cx={transform.X(0)} cy={transform.Y(0)} r={R * transform.scale} fill="none" stroke="var(--sketch-pipe)" strokeWidth={2} />
      <circle cx={transform.X(0)} cy={transform.Y(0)} r={Ri * transform.scale} fill="none" stroke="var(--sketch-pipe)" strokeWidth={1.5} strokeDasharray="7 5" />
      {elements}
      <Labels transform={transform} labels={labelItems} />
    </svg>
  );
}

interface FigureSpec {
  alias?: string;
  source: { kind: "star" | "dot"; x: number; y: number; label?: string };
  detector: { kind: "outer" | "inner" | "circle" | "flat"; t1?: number; t2?: number; x1?: number; x2?: number; y?: number };
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
        <circle cx={transform.X(0)} cy={transform.Y(0)} r={1.08 * transform.scale} fill="none" stroke={detColor} strokeWidth={3} />
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
      <circle cx={transform.X(0)} cy={transform.Y(0)} r={1 * transform.scale} fill="none" stroke="var(--sketch-pipe)" strokeWidth={2} />
      <circle cx={transform.X(0)} cy={transform.Y(0)} r={0.8 * transform.scale} fill="none" stroke="var(--sketch-pipe)" strokeWidth={1.5} strokeDasharray="7 5" />
      {spec.beams?.map((beam, index) => {
        const [a1, a2] = beam.angles;
        const p1 = [beam.radius * Math.cos((a1 * Math.PI) / 180), beam.radius * Math.sin((a1 * Math.PI) / 180)];
        const p2 = [beam.radius * Math.cos((a2 * Math.PI) / 180), beam.radius * Math.sin((a2 * Math.PI) / 180)];
        return (
          <g key={index}>
            <polygon
              points={`${transform.X(beam.from[0])},${transform.Y(beam.from[1])} ${transform.X(p1[0])},${transform.Y(p1[1])} ${transform.X(p2[0])},${transform.Y(p2[1])}`}
              fill={beamColor}
              opacity={0.12}
            />
            <line x1={transform.X(beam.from[0])} y1={transform.Y(beam.from[1])} x2={transform.X(p1[0])} y2={transform.Y(p1[1])} stroke={beamColor} strokeWidth={1.2} strokeDasharray="3 3" />
            <line x1={transform.X(beam.from[0])} y1={transform.Y(beam.from[1])} x2={transform.X(p2[0])} y2={transform.Y(p2[1])} stroke={beamColor} strokeWidth={1.2} strokeDasharray="3 3" />
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
      <SourceMarker transform={transform} kind={spec.source.kind} x={spec.source.x} y={spec.source.y} />
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
      <text x={W / 2} y={20} fontSize={12} fontWeight={600} fill="var(--sketch-text)" textAnchor="middle">
        {title}
      </text>
    </svg>
  );
}
