import { useCallback, useEffect, useRef, useState } from "react";

export interface WeldSetup3DProps {
  od: number;
  t: number;
  cap: number;
  weldWidth: number;
  d: number;
  geometry: string;
  userGeometry?: string;
  geometryForced?: boolean;
  sfd: number;
  fMin?: number;
  bDist?: number;
  bed?: number;
  bgap?: number;
  ug?: number;
  isPlanar?: boolean;
  isDigital?: boolean;
  filmSide?: boolean;
  panelWidth?: number | null;
  panelHeight?: number | null;
  filmWidth?: number;
  filmHeight?: number;
  overlapPct?: number;
  nRequired?: number;
  nApplied?: number;
  wireStr?: string;
  duplexStr?: string;
  safetyRadiusM?: number | null;
  supervisedRadiusM?: number | null;
  theme?: "dark" | "light";
  lang?: string;
}

interface Vec3 {
  x: number;
  y: number;
  z: number;
}

interface ProjectedPoint {
  x: number;
  y: number;
  depth: number;
  scale: number;
}

type CameraPreset = "iso" | "cross" | "longitudinal" | "beam";

export function WeldSetup3D({
  od,
  t,
  cap,
  weldWidth,
  d,
  geometry,
  userGeometry,
  geometryForced = false,
  sfd,
  fMin = 0,
  bDist = 0,
  bed = 0,
  bgap = 0,
  ug = 0,
  isPlanar = true,
  isDigital = true,
  filmSide = true,
  panelWidth = 200,
  panelHeight = 200,
  filmWidth = 100,
  filmHeight = 400,
  overlapPct = 10,
  nRequired = 1,
  nApplied = 0,
  wireStr = "W10",
  duplexStr = "D6",
  safetyRadiusM = null,
  supervisedRadiusM = null,
  theme = "dark",
  lang = "tr",
}: WeldSetup3DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Camera state
  const [yaw, setYaw] = useState<number>(0.68); // ~39 deg
  const [pitch, setPitch] = useState<number>(0.42); // ~24 deg
  const [zoom, setZoom] = useState<number>(1.05);
  const [panX, setPanX] = useState<number>(0);
  const [panY, setPanY] = useState<number>(15);

  // Interactive 3D inspection controls
  const [cutaway, setCutaway] = useState<boolean>(true);
  const [pipeOpacity, setPipeOpacity] = useState<number>(0.62);
  const [showAllStations, setShowAllStations] = useState<boolean>(false);
  const [activeStation, setActiveStation] = useState<number>(0);
  const [playing, setPlaying] = useState<boolean>(false);
  const [showDimensions, setShowDimensions] = useState<boolean>(true);
  const [showProjection, setShowProjection] = useState<boolean>(true);
  const [previewUserGeo, setPreviewUserGeo] = useState<boolean>(true);

  const dragRef = useRef<{
    active: boolean;
    shift: boolean;
    startX: number;
    startY: number;
    startYaw: number;
    startPitch: number;
    startPanX: number;
    startPanY: number;
  }>({
    active: false,
    shift: false,
    startX: 0,
    startY: 0,
    startYaw: 0,
    startPitch: 0,
    startPanX: 0,
    startPanY: 0,
  });

  // Effective geometry to visualize (allow user to preview their selected DWDI even when OD > 100 forces engine to DWSI)
  const activeGeo =
    geometryForced && previewUserGeo && userGeometry ? userGeometry : geometry;

  const totalStations = Math.max(1, nApplied > 0 ? nApplied : nRequired);
  const safeStation = activeStation >= totalStations ? 0 : activeStation;
  const stationStepRad =
    activeGeo === "dwdi_elliptic" && totalStations === 2
      ? Math.PI / 2
      : (2 * Math.PI) / totalStations;

  useEffect(() => {
    if (!playing || totalStations <= 1) return;
    const timer = window.setInterval(() => {
      setActiveStation((prev) => (prev + 1) % totalStations);
    }, 1100);
    return () => window.clearInterval(timer);
  }, [playing, totalStations]);

  const applyCameraPreset = useCallback((preset: CameraPreset) => {
    setPanX(0);
    if (preset === "iso") {
      setYaw(0.68);
      setPitch(0.42);
      setZoom(1.05);
      setPanY(15);
    } else if (preset === "cross") {
      // Looking straight down Z axis (X-Y cross-section)
      setYaw(0.0);
      setPitch(0.0);
      setZoom(1.1);
      setPanY(18);
    } else if (preset === "longitudinal") {
      // Side view (Y-Z plane) showing elliptical tilt along pipe axis
      setYaw(Math.PI / 2);
      setPitch(0.08);
      setZoom(1.05);
      setPanY(18);
    } else if (preset === "beam") {
      // Beam's-eye view from source down toward detector
      setYaw(0.0);
      setPitch(Math.PI / 2 - 0.05);
      setZoom(1.15);
      setPanY(0);
    }
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = 520;
    const height = 430;
    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }
    ctx.save();
    ctx.scale(dpr, dpr);

    const isDark = theme === "dark";
    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    if (isDark) {
      bgGrad.addColorStop(0, "#141821");
      bgGrad.addColorStop(1, "#0d1017");
    } else {
      bgGrad.addColorStop(0, "#f4f6fa");
      bgGrad.addColorStop(1, "#e6ebf2");
    }
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // Physical dimensions (normalized to scene units)
    const R = Math.max(od / 2, 5);
    const wallT = Math.min(Math.max(t, R * 0.04), R * 0.85);
    const Ri = Math.max(R - wallT, R * 0.12);
    const wHalf = Math.max(weldWidth / 2, R * 0.07);
    const wCap = Math.max(cap, R * 0.05);
    const pipeLen = Math.max(R * 3.4, (weldWidth || R * 0.25) * 4.8);
    const halfLen = pipeLen / 2;
    const detY = -R - Math.max(bgap, R * 0.08);

    // Clamp visual source height so pipe & weld remain clearly legible while preserving SFD proportions
    const rawYSrc = Math.max(sfd - R, R * 1.25);
    const ySourceBase =
      activeGeo === "swsi"
        ? 0
        : activeGeo === "dwsi"
          ? Math.min(rawYSrc, R * 2.6)
          : Math.min(Math.max(rawYSrc, R * 1.8), R * 3.2);

    // Axial Z-offset of the source:
    // - swsi:          z = 0 (inside pipe center)
    // - dwdi_super:    z = 0 (directly over weld plane -> top & bottom welds superimpose at z = 0)
    // - dwsi:          z > 0 (offset beside top weld cap so beam enters upper parent metal & hits ONLY bottom weld at z = 0)
    // - dwdi_elliptic: z > 0 (offset so beam covers BOTH top & bottom welds and separates them into an ellipse on detector)
    const dwsiEntryZ = Math.max(wHalf * 2.5, R * 0.42);
    const zSourceBase =
      activeGeo === "dwsi"
        ? Math.min(
            halfLen * 0.78,
            dwsiEntryZ * ((ySourceBase + R) / Math.max(2 * R, 1)),
          )
        : activeGeo === "dwdi_elliptic"
          ? Math.min(
              halfLen * 0.78,
              Math.max((ySourceBase + R) * Math.tan((16 * Math.PI) / 180), R * 0.65),
            )
          : 0;

    // Where the upper weld (0, +R, 0) and lower weld (0, -R, 0) project onto y = detY
    const tRayTop =
      ySourceBase > R + 1e-3 ? (detY - ySourceBase) / (R - ySourceBase) : 2.0;
    const tRayBot =
      ySourceBase > -R + 1e-3 ? (detY - ySourceBase) / (-R - ySourceBase) : 1.0;
    const zTopWeldHit =
      activeGeo === "dwdi_elliptic" ? zSourceBase * (1 - tRayTop) : 0;
    const zBotWeldHit =
      activeGeo === "dwdi_elliptic" ? zSourceBase * (1 - tRayBot) : 0;

    // Detector center along Z: shifted to catch both arcs in dwdi_elliptic, centered at z = 0 otherwise
    const detCenterZ =
      activeGeo === "dwdi_elliptic" ? (zTopWeldHit + zBotWeldHit) / 2 : 0;

    // Scene bounding scale
    const maxExtent = Math.max(
      R * 2.5,
      ySourceBase + R * 1.35,
      pipeLen * 0.85,
      (isDigital ? (panelWidth ?? 200) : filmHeight) * 0.75,
    );
    const baseScale = (Math.min(width, height) * 0.68 * zoom) / maxExtent;

    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);

    const centerYOffset = activeGeo === "swsi" ? 0 : (ySourceBase - R) * 0.28;

    const project = (pt: Vec3): ProjectedPoint => {
      const px = pt.x;
      const py = pt.y - centerYOffset;
      const pz = pt.z;

      // Rotate around Y (yaw)
      const x1 = px * cosY + pz * sinY;
      const z1 = -px * sinY + pz * cosY;

      // Rotate around X (pitch)
      const y2 = py * cosP - z1 * sinP;
      const z2 = py * sinP + z1 * cosP;

      // Slight perspective
      const camDist = maxExtent * 3.6;
      const persp = camDist / Math.max(camDist - z2, maxExtent * 0.4);
      const s = baseScale * persp;

      return {
        x: width / 2 + panX + x1 * s,
        y: height / 2 + panY - y2 * s,
        depth: z2,
        scale: s,
      };
    };

    // Rotate point around Z axis by station angle
    const rotZ = (pt: Vec3, angleRad: number): Vec3 => {
      if (Math.abs(angleRad) < 1e-6) return pt;
      const c = Math.cos(angleRad);
      const s = Math.sin(angleRad);
      return {
        x: pt.x * c - pt.y * s,
        y: pt.x * s + pt.y * c,
        z: pt.z,
      };
    };

    // 1. Draw subtle 3D floor reference grid at y = -R - bgap - bed - R*0.25
    const gridY = -R - Math.max(bgap + bed, R * 0.18);
    const gridExtent = maxExtent * 0.65;
    const gridSteps = 6;
    ctx.strokeStyle = isDark ? "rgba(255,255,255,0.05)" : "rgba(15,23,42,0.06)";
    ctx.lineWidth = 1;
    for (let i = -gridSteps; i <= gridSteps; i += 1) {
      const pos = (i / gridSteps) * gridExtent;
      const a1 = project({ x: -gridExtent, y: gridY, z: pos });
      const a2 = project({ x: gridExtent, y: gridY, z: pos });
      ctx.beginPath();
      ctx.moveTo(a1.x, a1.y);
      ctx.lineTo(a2.x, a2.y);
      ctx.stroke();

      const b1 = project({ x: pos, y: gridY, z: -gridExtent });
      const b2 = project({ x: pos, y: gridY, z: gridExtent });
      ctx.beginPath();
      ctx.moveTo(b1.x, b1.y);
      ctx.lineTo(b2.x, b2.y);
      ctx.stroke();
    }

    // 2. Build 3D Pipe & Weld Mesh Quads (painter's algorithm sorted by depth)
    interface Quad {
      pts: ProjectedPoint[];
      fill: string;
      stroke?: string;
      lineWidth?: number;
      avgDepth: number;
    }
    const quads: Quad[] = [];

    const nSegTheta = 36;
    const nSegZ = 10;
    const isCutawayAngle = (deg: number) => {
      if (!cutaway) return false;
      // Cut out front-right quadrant (305° to 55°) on positive Z half so interior wall & root weld are visible
      const norm = ((deg % 360) + 360) % 360;
      return norm >= 315 || norm <= 45;
    };

    for (let iz = 0; iz < nSegZ; iz += 1) {
      const z0 = -halfLen + (iz / nSegZ) * pipeLen;
      const z1 = -halfLen + ((iz + 1) / nSegZ) * pipeLen;
      const zMid = (z0 + z1) / 2;

      for (let it = 0; it < nSegTheta; it += 1) {
        const deg0 = (it / nSegTheta) * 360;
        const deg1 = ((it + 1) / nSegTheta) * 360;
        const degMid = (deg0 + deg1) / 2;

        // Cutaway on the front half (z >= 0) for the cutout angular sector
        if (zMid >= 0 && isCutawayAngle(degMid)) continue;

        const r0 = (deg0 * Math.PI) / 180;
        const r1 = (deg1 * Math.PI) / 180;
        const rMid = (degMid * Math.PI) / 180;

        // Outer cylinder quad
        const p00 = project({ x: R * Math.cos(r0), y: R * Math.sin(r0), z: z0 });
        const p10 = project({ x: R * Math.cos(r1), y: R * Math.sin(r1), z: z0 });
        const p11 = project({ x: R * Math.cos(r1), y: R * Math.sin(r1), z: z1 });
        const p01 = project({ x: R * Math.cos(r0), y: R * Math.sin(r0), z: z1 });

        const light = 0.55 + 0.45 * Math.sin(rMid + 0.5);
        const baseR = isDark ? Math.round(52 * light) : Math.round(145 + 65 * light);
        const baseG = isDark ? Math.round(78 * light) : Math.round(165 + 60 * light);
        const baseB = isDark ? Math.round(112 * light) : Math.round(190 + 50 * light);

        quads.push({
          pts: [p00, p10, p11, p01],
          fill: `rgba(${baseR}, ${baseG}, ${baseB}, ${pipeOpacity.toFixed(2)})`,
          stroke: isDark
            ? `rgba(148, 184, 232, ${(0.22 * pipeOpacity).toFixed(2)})`
            : `rgba(51, 85, 130, ${(0.24 * pipeOpacity).toFixed(2)})`,
          lineWidth: 0.6,
          avgDepth: (p00.depth + p10.depth + p11.depth + p01.depth) / 4,
        });

        // Inner cylinder quad (darker gunmetal steel so wall thickness contrasts strongly)
        const i00 = project({ x: Ri * Math.cos(r0), y: Ri * Math.sin(r0), z: z0 });
        const i10 = project({ x: Ri * Math.cos(r1), y: Ri * Math.sin(r1), z: z0 });
        const i11 = project({ x: Ri * Math.cos(r1), y: Ri * Math.sin(r1), z: z1 });
        const i01 = project({ x: Ri * Math.cos(r0), y: Ri * Math.sin(r0), z: z1 });

        const innerAlpha = Math.min(0.95, pipeOpacity * 1.18).toFixed(2);
        quads.push({
          pts: [i00, i10, i11, i01],
          fill: isDark
            ? `rgba(12, 18, 30, ${innerAlpha})`
            : `rgba(45, 58, 78, ${innerAlpha})`,
          stroke: isDark ? "rgba(71, 85, 105, 0.22)" : "rgba(30, 41, 59, 0.22)",
          lineWidth: 0.5,
          avgDepth: (i00.depth + i10.depth + i11.depth + i01.depth) / 4 - 0.1,
        });
      }
    }

    // 2b. Dark Pipe End Wall-Thickness Annulus Quads (at z = -halfLen and z = +halfLen, plus cutaway z = 0 transverse wall face)
    const wallFaceAlpha = Math.max(0.82, pipeOpacity).toFixed(2);
    const wallFaceFill = isDark
      ? `rgba(15, 23, 38, ${wallFaceAlpha})`
      : `rgba(30, 41, 59, ${wallFaceAlpha})`;
    const wallFaceStroke = isDark ? "rgba(100, 116, 139, 0.55)" : "rgba(15, 23, 42, 0.65)";

    for (const zEnd of [-halfLen, halfLen]) {
      for (let it = 0; it < nSegTheta; it += 1) {
        const deg0 = (it / nSegTheta) * 360;
        const deg1 = ((it + 1) / nSegTheta) * 360;
        const degMid = (deg0 + deg1) / 2;
        if (zEnd > 0 && isCutawayAngle(degMid)) continue;
        const r0 = (deg0 * Math.PI) / 180;
        const r1 = (deg1 * Math.PI) / 180;
        const e0 = project({ x: R * Math.cos(r0), y: R * Math.sin(r0), z: zEnd });
        const e1 = project({ x: R * Math.cos(r1), y: R * Math.sin(r1), z: zEnd });
        const e2 = project({ x: Ri * Math.cos(r1), y: Ri * Math.sin(r1), z: zEnd });
        const e3 = project({ x: Ri * Math.cos(r0), y: Ri * Math.sin(r0), z: zEnd });
        quads.push({
          pts: [e0, e1, e2, e3],
          fill: wallFaceFill,
          stroke: wallFaceStroke,
          lineWidth: 0.6,
          avgDepth: (e0.depth + e1.depth + e2.depth + e3.depth) / 4 + 0.05,
        });
      }
    }

    // Transverse cutaway wall thickness face at z = 0 for the cutout angular sector
    if (cutaway) {
      for (let it = 0; it < nSegTheta; it += 1) {
        const deg0 = (it / nSegTheta) * 360;
        const deg1 = ((it + 1) / nSegTheta) * 360;
        const degMid = (deg0 + deg1) / 2;
        if (!isCutawayAngle(degMid)) continue;
        const r0 = (deg0 * Math.PI) / 180;
        const r1 = (deg1 * Math.PI) / 180;
        const e0 = project({ x: R * Math.cos(r0), y: R * Math.sin(r0), z: 0 });
        const e1 = project({ x: R * Math.cos(r1), y: R * Math.sin(r1), z: 0 });
        const e2 = project({ x: Ri * Math.cos(r1), y: Ri * Math.sin(r1), z: 0 });
        const e3 = project({ x: Ri * Math.cos(r0), y: Ri * Math.sin(r0), z: 0 });
        quads.push({
          pts: [e0, e1, e2, e3],
          fill: wallFaceFill,
          stroke: wallFaceStroke,
          lineWidth: 0.7,
          avgDepth: (e0.depth + e1.depth + e2.depth + e3.depth) / 4 + 0.15,
        });
      }
    }

    // 3. 3D Girth Weld Crown & Root Pass at Z = 0 + Circumferential Measuring Tape (Şerit Metre)
    const rWeldCrown = R + wCap;
    const rWeldRoot = Math.max(Ri - wCap * 0.6, Ri * 0.85);
    const rTape = R + Math.max(R * 0.018, 0.8);
    const tapeGap = Math.max(wHalf * 0.35, R * 0.04);
    const tapeWidth = Math.max(wHalf * 0.95, R * 0.13);
    const zTape0 = -wHalf - tapeGap - tapeWidth;
    const zTape1 = -wHalf - tapeGap;

    for (let it = 0; it < nSegTheta; it += 1) {
      const deg0 = (it / nSegTheta) * 360;
      const deg1 = ((it + 1) / nSegTheta) * 360;
      const degMid = (deg0 + deg1) / 2;

      const r0 = (deg0 * Math.PI) / 180;
      const r1 = (deg1 * Math.PI) / 180;
      const shade = 0.65 + 0.35 * Math.sin(((degMid + 35) * Math.PI) / 180);

      // Circumferential Measuring Tape (Şerit Metre) wrapped right beside the girth weld (z < 0 side)
      const tp00 = project({ x: rTape * Math.cos(r0), y: rTape * Math.sin(r0), z: zTape0 });
      const tp10 = project({ x: rTape * Math.cos(r1), y: rTape * Math.sin(r1), z: zTape0 });
      const tp11 = project({ x: rTape * Math.cos(r1), y: rTape * Math.sin(r1), z: zTape1 });
      const tp01 = project({ x: rTape * Math.cos(r0), y: rTape * Math.sin(r0), z: zTape1 });
      const trR = Math.round(250 * (0.72 + 0.28 * shade));
      const trG = Math.round(204 * (0.72 + 0.28 * shade));
      const trB = Math.round(21 * (0.72 + 0.28 * shade));
      quads.push({
        pts: [tp00, tp10, tp11, tp01],
        fill: `rgba(${trR}, ${trG}, ${trB}, ${Math.min(0.95, pipeOpacity + 0.25).toFixed(2)})`,
        stroke: "rgba(113, 63, 18, 0.55)",
        lineWidth: 0.6,
        avgDepth: (tp00.depth + tp10.depth + tp11.depth + tp01.depth) / 4 + 0.18,
      });

      if (isCutawayAngle(degMid)) continue;

      // Outer weld cap band
      const w00 = project({ x: rWeldCrown * Math.cos(r0), y: rWeldCrown * Math.sin(r0), z: -wHalf });
      const w10 = project({ x: rWeldCrown * Math.cos(r1), y: rWeldCrown * Math.sin(r1), z: -wHalf });
      const w11 = project({ x: rWeldCrown * Math.cos(r1), y: rWeldCrown * Math.sin(r1), z: wHalf });
      const w01 = project({ x: rWeldCrown * Math.cos(r0), y: rWeldCrown * Math.sin(r0), z: wHalf });

      const wr = Math.round(235 * shade);
      const wg = Math.round(145 * shade);
      const wb = Math.round(45 * shade);
      quads.push({
        pts: [w00, w10, w11, w01],
        fill: `rgba(${wr}, ${wg}, ${wb}, 0.88)`,
        stroke: isDark ? "rgba(255, 200, 110, 0.45)" : "rgba(160, 80, 10, 0.45)",
        lineWidth: 0.8,
        avgDepth: (w00.depth + w10.depth + w11.depth + w01.depth) / 4 + 0.2,
      });

      // Inner root pass band
      const rt00 = project({ x: rWeldRoot * Math.cos(r0), y: rWeldRoot * Math.sin(r0), z: -wHalf * 0.65 });
      const rt10 = project({ x: rWeldRoot * Math.cos(r1), y: rWeldRoot * Math.sin(r1), z: -wHalf * 0.65 });
      const rt11 = project({ x: rWeldRoot * Math.cos(r1), y: rWeldRoot * Math.sin(r1), z: wHalf * 0.65 });
      const rt01 = project({ x: rWeldRoot * Math.cos(r0), y: rWeldRoot * Math.sin(r0), z: wHalf * 0.65 });

      quads.push({
        pts: [rt00, rt10, rt11, rt01],
        fill: `rgba(${wr}, ${Math.round(wg * 0.85)}, ${wb}, 0.78)`,
        avgDepth: (rt00.depth + rt10.depth + rt11.depth + rt01.depth) / 4 + 0.1,
      });
    }

    // Sort and draw pipe + weld + tape quads back-to-front
    quads.sort((a, b) => a.avgDepth - b.avgDepth);
    for (const q of quads) {
      ctx.beginPath();
      ctx.moveTo(q.pts[0].x, q.pts[0].y);
      for (let i = 1; i < q.pts.length; i += 1) {
        ctx.lineTo(q.pts[i].x, q.pts[i].y);
      }
      ctx.closePath();
      ctx.fillStyle = q.fill;
      ctx.fill();
      if (q.stroke) {
        ctx.strokeStyle = q.stroke;
        ctx.lineWidth = q.lineWidth ?? 0.6;
        ctx.stroke();
      }
    }

    // 3b. Draw 3D Graduation Ticks & Centimeter Numbers on Circumferential Measuring Tape (Şerit Metre)
    const circumCm = Math.max(5, (Math.PI * od) / 10);
    const zTapeMid = (zTape0 + zTape1) / 2;
    for (let deg = 0; deg < 360; deg += 5) {
      const rad = (deg * Math.PI) / 180;
      const nx = Math.cos(rad);
      const ny = Math.sin(rad);
      // Camera-space Z normal check so ticks/numbers are drawn only on camera-facing half of the pipe
      const nz1 = -nx * sinY;
      const nzCam = ny * sinP + nz1 * cosP;
      if (nzCam < -0.05) continue;

      const isMajor = deg % 30 === 0;
      const zTickEnd = isMajor ? zTape0 + tapeWidth * 0.15 : zTape1 - tapeWidth * 0.45;
      const tStart = project({ x: (rTape + 0.2) * nx, y: (rTape + 0.2) * ny, z: zTape1 });
      const tEnd = project({ x: (rTape + 0.2) * nx, y: (rTape + 0.2) * ny, z: zTickEnd });
      ctx.beginPath();
      ctx.moveTo(tStart.x, tStart.y);
      ctx.lineTo(tEnd.x, tEnd.y);
      ctx.strokeStyle = isMajor ? "#1c1917" : "rgba(28, 25, 23, 0.7)";
      ctx.lineWidth = isMajor ? 1.4 : 0.8;
      ctx.stroke();

      if (isMajor && nzCam > 0.12) {
        // Clockwise from 12 o'clock (90 deg) in cm
        const clockwiseDeg = ((90 - deg) % 360 + 360) % 360;
        const cmVal = Math.round((clockwiseDeg / 360) * circumCm);
        const numPt = project({
          x: (rTape + 0.4) * nx,
          y: (rTape + 0.4) * ny,
          z: zTapeMid - tapeWidth * 0.12,
        });
        ctx.fillStyle = "#1c1917";
        ctx.font = "800 8px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`${cmVal}`, numPt.x, numPt.y);
      }
    }
    if (showDimensions) {
      const tapeCalloutPt = project({
        x: -rTape * Math.cos((35 * Math.PI) / 180),
        y: rTape * Math.sin((35 * Math.PI) / 180),
        z: zTape0,
      });
      ctx.font = "600 9px system-ui, sans-serif";
      ctx.fillStyle = isDark ? "#fde047" : "#854d0e";
      ctx.textAlign = "right";
      ctx.fillText(
        lang === "tr" ? "Şerit Metre (cm)" : "Measuring Tape (cm)",
        tapeCalloutPt.x - 6,
        tapeCalloutPt.y - 4,
      );
    }

    // Draw pipe end rings (at z = -halfLen and z = +halfLen)
    for (const zEnd of [-halfLen, halfLen]) {
      for (const radius of [R, Ri]) {
        ctx.beginPath();
        let started = false;
        for (let deg = 0; deg <= 360; deg += 5) {
          if (zEnd > 0 && isCutawayAngle(deg)) {
            started = false;
            continue;
          }
          const rad = (deg * Math.PI) / 180;
          const pt = project({
            x: radius * Math.cos(rad),
            y: radius * Math.sin(rad),
            z: zEnd,
          });
          if (!started) {
            ctx.moveTo(pt.x, pt.y);
            started = true;
          } else {
            ctx.lineTo(pt.x, pt.y);
          }
        }
        ctx.strokeStyle =
          radius === R
            ? isDark
              ? "#6ea8fe"
              : "#1d4ed8"
            : isDark
              ? "#475569"
              : "#1e293b";
        ctx.lineWidth = radius === R ? 1.8 : 1.3;
        ctx.stroke();
      }
    }

    // If cutaway is active, highlight the exposed longitudinal wall thickness faces at z >= 0 with dark gunmetal steel + cross-hatching
    if (cutaway) {
      for (const cutDeg of [315, 45]) {
        const rad = (cutDeg * Math.PI) / 180;
        const c0 = project({ x: Ri * Math.cos(rad), y: Ri * Math.sin(rad), z: 0 });
        const c1 = project({ x: R * Math.cos(rad), y: R * Math.sin(rad), z: 0 });
        const c2 = project({ x: R * Math.cos(rad), y: R * Math.sin(rad), z: halfLen });
        const c3 = project({ x: Ri * Math.cos(rad), y: Ri * Math.sin(rad), z: halfLen });
        ctx.beginPath();
        ctx.moveTo(c0.x, c0.y);
        ctx.lineTo(c1.x, c1.y);
        ctx.lineTo(c2.x, c2.y);
        ctx.lineTo(c3.x, c3.y);
        ctx.closePath();
        ctx.fillStyle = isDark ? "rgba(15, 23, 42, 0.92)" : "rgba(30, 41, 59, 0.88)";
        ctx.strokeStyle = isDark ? "#94a3b8" : "#0f172a";
        ctx.lineWidth = 1.4;
        ctx.fill();
        ctx.stroke();

        // Metallographic section hatch lines across the wall thickness face
        const nHatch = 8;
        ctx.strokeStyle = isDark ? "rgba(148, 163, 184, 0.45)" : "rgba(203, 213, 225, 0.55)";
        ctx.lineWidth = 0.9;
        for (let ih = 1; ih < nHatch; ih += 1) {
          const zH0 = ((ih - 0.35) / nHatch) * halfLen;
          const zH1 = ((ih + 0.35) / nHatch) * halfLen;
          const hIn = project({ x: Ri * Math.cos(rad), y: Ri * Math.sin(rad), z: zH0 });
          const hOut = project({ x: R * Math.cos(rad), y: R * Math.sin(rad), z: zH1 });
          ctx.beginPath();
          ctx.moveTo(hIn.x, hIn.y);
          ctx.lineTo(hOut.x, hOut.y);
          ctx.stroke();
        }
      }
    }

    // 4. Multi-Station Circumferential Array & Active Station Geometry
    const detW = Math.min(
      isDigital ? (panelWidth ?? R * 1.4) : filmHeight,
      R * 2.4,
    );
    const ellipSpanZ = Math.abs(zBotWeldHit - zTopWeldHit) + wHalf * 3.8;
    const detH = Math.min(
      Math.max(
        isDigital ? (panelHeight ?? R * 1.1) : filmWidth,
        activeGeo === "dwdi_elliptic" ? ellipSpanZ : R * 0.65,
      ),
      pipeLen * 0.85,
    );

    // Draw ghost stations when showAllStations is enabled (or always show subtle station arcs if totalStations > 1)
    const stationsToDraw = showAllStations
      ? Array.from({ length: totalStations }, (_, i) => i)
      : [safeStation];

    // If nApplied > 0 and nApplied < nRequired, highlight uninspected angular dead-zone on weld ring
    if (nApplied > 0 && nApplied < nRequired) {
      const deadStartDeg = (nApplied / nRequired) * 360;
      ctx.beginPath();
      for (let deg = deadStartDeg; deg <= 360; deg += 4) {
        const rad = (deg * Math.PI) / 180;
        const p = project({
          x: (R + wCap * 1.5) * Math.cos(rad),
          y: (R + wCap * 1.5) * Math.sin(rad),
          z: 0,
        });
        if (deg === deadStartDeg) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 4;
      ctx.setLineDash([5, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    for (const stIdx of stationsToDraw) {
      const isCurrent = stIdx === safeStation;
      const stAngle = stIdx * stationStepRad;
      const zMinDet = detCenterZ - detH / 2;
      const zMaxDet = detCenterZ + detH / 2;

      // Detector corners or curved strip in station local coords
      if ((isPlanar && isDigital) || activeGeo === "dwdi_elliptic" || activeGeo === "dwdi_super") {
        const hw = detW / 2;
        const cornersLocal: Vec3[] = [
          { x: -hw, y: detY, z: zMinDet },
          { x: hw, y: detY, z: zMinDet },
          { x: hw, y: detY, z: zMaxDet },
          { x: -hw, y: detY, z: zMaxDet },
        ];
        const corners = cornersLocal.map((c) => project(rotZ(c, stAngle)));

        ctx.beginPath();
        ctx.moveTo(corners[0].x, corners[0].y);
        corners.slice(1).forEach((c) => ctx.lineTo(c.x, c.y));
        ctx.closePath();
        ctx.fillStyle = isCurrent
          ? isDark
            ? "rgba(16, 185, 129, 0.34)"
            : "rgba(5, 150, 105, 0.28)"
          : isDark
            ? "rgba(16, 185, 129, 0.10)"
            : "rgba(5, 150, 105, 0.09)";
        ctx.strokeStyle = isCurrent
          ? isDark
            ? "#34d399"
            : "#059669"
          : isDark
            ? "rgba(52, 211, 153, 0.35)"
            : "rgba(5, 150, 105, 0.35)";
        ctx.lineWidth = isCurrent ? 2.2 : 1;
        ctx.fill();
        ctx.stroke();

        // Highlight overlap region at right edge of active flat panel
        if (isCurrent && overlapPct > 0) {
          const ovW = Math.max(detW * (overlapPct / 100), detW * 0.08);
          const ovCorners = [
            { x: hw - ovW, y: detY, z: zMinDet },
            { x: hw, y: detY, z: zMinDet },
            { x: hw, y: detY, z: zMaxDet },
            { x: hw - ovW, y: detY, z: zMaxDet },
          ].map((c) => project(rotZ(c, stAngle)));
          ctx.beginPath();
          ctx.moveTo(ovCorners[0].x, ovCorners[0].y);
          ovCorners.slice(1).forEach((c) => ctx.lineTo(c.x, c.y));
          ctx.closePath();
          ctx.fillStyle = "rgba(245, 158, 11, 0.48)";
          ctx.fill();
        }
      } else {
        // Curved flexible film / CR wrapped along bottom arc
        const rFilm = R + Math.max(bgap, R * 0.06);
        const spanDeg = Math.min(130, Math.max(65, 360 / totalStations + 18));
        const aStart = 270 - spanDeg / 2;
        const aEnd = 270 + spanDeg / 2;
        const frontArc: ProjectedPoint[] = [];
        const backArc: ProjectedPoint[] = [];
        for (let a = aStart; a <= aEnd; a += 6) {
          const rad = (a * Math.PI) / 180;
          frontArc.push(
            project(
              rotZ(
                { x: rFilm * Math.cos(rad), y: rFilm * Math.sin(rad), z: zMaxDet },
                stAngle,
              ),
            ),
          );
          backArc.push(
            project(
              rotZ(
                { x: rFilm * Math.cos(rad), y: rFilm * Math.sin(rad), z: zMinDet },
                stAngle,
              ),
            ),
          );
        }
        ctx.beginPath();
        frontArc.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
        for (let i = backArc.length - 1; i >= 0; i -= 1) {
          ctx.lineTo(backArc[i].x, backArc[i].y);
        }
        ctx.closePath();
        ctx.fillStyle = isCurrent
          ? "rgba(16, 185, 129, 0.34)"
          : "rgba(16, 185, 129, 0.10)";
        ctx.strokeStyle = isCurrent ? "#34d399" : "rgba(52, 211, 153, 0.35)";
        ctx.lineWidth = isCurrent ? 2 : 1;
        ctx.fill();
        ctx.stroke();
      }

      // Station index badge
      if (totalStations > 1) {
        const badgePt = project(
          rotZ({ x: 0, y: detY - R * 0.16, z: detCenterZ }, stAngle),
        );
        ctx.beginPath();
        ctx.arc(badgePt.x, badgePt.y, isCurrent ? 10 : 8, 0, Math.PI * 2);
        ctx.fillStyle = isCurrent ? "#10b981" : isDark ? "#1e293b" : "#cbd5e1";
        ctx.fill();
        ctx.fillStyle = isCurrent ? "#ffffff" : isDark ? "#94a3b8" : "#334155";
        ctx.font = `${isCurrent ? "700" : "600"} 10px system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(`#${stIdx + 1}`, badgePt.x, badgePt.y);
      }
    }

    // 5. Active Station Source Position, Radiation Cone & Wall Penetration Indicators
    const activeAngle = safeStation * stationStepRad;
    const srcLocal: Vec3 = {
      x: 0,
      y: ySourceBase,
      z: zSourceBase,
    };
    const srcWorld = rotZ(srcLocal, activeAngle);
    const srcProj = project(srcWorld);

    // Target footprint corners on the detector for the volumetric radiation cone:
    // - dwdi_elliptic: covers BOTH projected top weld (zTopWeldHit) and bottom weld (zBotWeldHit)
    // - dwsi:          narrower Z cone centered on bottom weld (z = 0) so beam enters upper parent metal beside top weld
    // - dwdi_super:    centered at z = 0, passing straight through both top weld & bottom weld
    const coneHalfW =
      activeGeo === "dwdi_elliptic" || activeGeo === "dwdi_super"
        ? Math.min(detW * 0.48, R * 1.15)
        : Math.min(detW * 0.42, R * 0.92);
    const coneZMin =
      activeGeo === "dwdi_elliptic"
        ? Math.max(detCenterZ - detH * 0.46, zTopWeldHit - wHalf * 1.3)
        : -Math.min(detH * 0.34, wHalf * 2.1);
    const coneZMax =
      activeGeo === "dwdi_elliptic"
        ? Math.min(detCenterZ + detH * 0.46, zBotWeldHit + wHalf * 1.3)
        : Math.min(detH * 0.34, wHalf * 2.1);

    const coneTargetsLocal: Vec3[] = [
      { x: -coneHalfW, y: detY, z: coneZMin },
      { x: coneHalfW, y: detY, z: coneZMin },
      { x: coneHalfW, y: detY, z: coneZMax },
      { x: -coneHalfW, y: detY, z: coneZMax },
    ];
    const coneTargets = coneTargetsLocal.map((c) => project(rotZ(c, activeAngle)));

    // Draw volumetric radiation cone faces
    for (let i = 0; i < 4; i += 1) {
      const c1 = coneTargets[i];
      const c2 = coneTargets[(i + 1) % 4];
      ctx.beginPath();
      ctx.moveTo(srcProj.x, srcProj.y);
      ctx.lineTo(c1.x, c1.y);
      ctx.lineTo(c2.x, c2.y);
      ctx.closePath();
      ctx.fillStyle = isDark
        ? "rgba(250, 204, 21, 0.11)"
        : "rgba(234, 88, 12, 0.11)";
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(srcProj.x, srcProj.y);
      ctx.lineTo(c1.x, c1.y);
      ctx.strokeStyle = isDark
        ? "rgba(250, 204, 21, 0.55)"
        : "rgba(234, 88, 12, 0.55)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Central beam axis (and dual weld rays for DWDI Elliptic)
    const detCenterWorld = rotZ({ x: 0, y: detY, z: detCenterZ }, activeAngle);
    const detCenterProj = project(detCenterWorld);

    if (activeGeo === "dwdi_elliptic") {
      // Draw two distinct rays: (1) Source -> Top Weld (0,+R,0) -> Detector Front Arc, (2) Source -> Bottom Weld (0,-R,0) -> Detector Back Arc
      const topHitProj = project(rotZ({ x: 0, y: detY, z: zTopWeldHit }, activeAngle));
      const botHitProj = project(rotZ({ x: 0, y: detY, z: zBotWeldHit }, activeAngle));
      const topWeldPtProj = project(rotZ({ x: 0, y: R, z: 0 }, activeAngle));
      const botWeldPtProj = project(rotZ({ x: 0, y: -R, z: 0 }, activeAngle));

      // Ray 1 (through Upper Weld)
      ctx.beginPath();
      ctx.moveTo(srcProj.x, srcProj.y);
      ctx.lineTo(topHitProj.x, topHitProj.y);
      ctx.strokeStyle = "#f97316";
      ctx.lineWidth = 1.8;
      ctx.setLineDash([5, 3]);
      ctx.stroke();

      // Ray 2 (through Lower Weld)
      ctx.beginPath();
      ctx.moveTo(srcProj.x, srcProj.y);
      ctx.lineTo(botHitProj.x, botHitProj.y);
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 1.8;
      ctx.setLineDash([5, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Highlight both weld intersections
      for (const [pt, col] of [
        [topWeldPtProj, "#f97316"],
        [botWeldPtProj, "#facc15"],
      ] as const) {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = col;
        ctx.fill();
      }
    } else {
      ctx.beginPath();
      ctx.moveTo(srcProj.x, srcProj.y);
      ctx.lineTo(detCenterProj.x, detCenterProj.y);
      ctx.strokeStyle = isDark ? "#facc15" : "#ea580c";
      ctx.lineWidth = 1.8;
      ctx.setLineDash([6, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      if (activeGeo === "dwsi") {
        // Highlight where the DWSI central ray enters the UPPER pipe base metal (beside the upper weld)
        const upperEntryProj = project(
          rotZ({ x: 0, y: R, z: dwsiEntryZ }, activeAngle),
        );
        const lowerWeldProj = project(rotZ({ x: 0, y: -R, z: 0 }, activeAngle));

        ctx.beginPath();
        ctx.arc(upperEntryProj.x, upperEntryProj.y, 5.5, 0, Math.PI * 2);
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(lowerWeldProj.x, lowerWeldProj.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = "#facc15";
        ctx.fill();

        if (showDimensions) {
          ctx.font = "600 9.5px system-ui, sans-serif";
          ctx.fillStyle = isDark ? "#7dd3fc" : "#0369a1";
          ctx.textAlign = "left";
          ctx.fillText(
            lang === "tr"
              ? "Üst Cidar Girişi (Ana Metal — Kaynak Dışı)"
              : "Upper Wall Entry (Base Metal — Off-Weld)",
            upperEntryProj.x + 9,
            upperEntryProj.y - 4,
          );
        }
      } else if (activeGeo === "dwdi_super") {
        // Highlight BOTH upper weld and lower weld intersections along the vertical z = 0 ray
        const topWeldProj = project(rotZ({ x: 0, y: R, z: 0 }, activeAngle));
        const botWeldProj = project(rotZ({ x: 0, y: -R, z: 0 }, activeAngle));
        for (const [pt, col] of [
          [topWeldProj, "#f97316"],
          [botWeldProj, "#facc15"],
        ] as const) {
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2);
          ctx.fillStyle = col;
          ctx.fill();
        }
        if (showDimensions) {
          ctx.font = "600 9.5px system-ui, sans-serif";
          ctx.fillStyle = "#fb923c";
          ctx.textAlign = "left";
          ctx.fillText(
            lang === "tr"
              ? "1. Cidar: Üst Kaynak (Çakışır)"
              : "1st Wall: Top Weld (Superimposed)",
            topWeldProj.x + 9,
            topWeldProj.y - 4,
          );
        }
      }
    }

    // 6. Real-Time Ray-Cast Weld Shadow Projection on Detector Plane!
    if (showProjection) {
      const zMinClamp = detCenterZ - detH * 0.47;
      const zMaxClamp = detCenterZ + detH * 0.47;
      const rayCastToDetector = (weldPtLocal: Vec3): ProjectedPoint | null => {
        const dy = weldPtLocal.y - srcLocal.y;
        if (Math.abs(dy) < 1e-4) return null;
        const tRay = (detY - srcLocal.y) / dy;
        if (tRay <= 0) return null;
        const hitX = srcLocal.x + tRay * (weldPtLocal.x - srcLocal.x);
        const hitZ = srcLocal.z + tRay * (weldPtLocal.z - srcLocal.z);
        return project(
          rotZ(
            {
              x: Math.max(-detW * 0.47, Math.min(detW * 0.47, hitX)),
              y: detY + 0.5,
              z: Math.max(zMinClamp, Math.min(zMaxClamp, hitZ)),
            },
            activeAngle,
          ),
        );
      };

      if (activeGeo === "dwdi_elliptic") {
        // Project full 360° girth weld ring (upper arc + lower arc) onto detector plane -> forms a separated 2-arc ellipse!
        // Upper weld half-ring (0°..180°, orange)
        ctx.beginPath();
        let startedTop = false;
        for (let deg = 15; deg <= 165; deg += 5) {
          const rad = (deg * Math.PI) / 180;
          const hit = rayCastToDetector({
            x: R * 0.68 * Math.cos(rad),
            y: R * Math.sin(rad),
            z: 0,
          });
          if (!hit) continue;
          if (!startedTop) {
            ctx.moveTo(hit.x, hit.y);
            startedTop = true;
          } else {
            ctx.lineTo(hit.x, hit.y);
          }
        }
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2.8;
        ctx.stroke();

        // Lower weld half-ring (195°..345°, gold)
        ctx.beginPath();
        let startedBot = false;
        for (let deg = 195; deg <= 345; deg += 5) {
          const rad = (deg * Math.PI) / 180;
          const hit = rayCastToDetector({
            x: R * 0.68 * Math.cos(rad),
            y: R * Math.sin(rad),
            z: 0,
          });
          if (!hit) continue;
          if (!startedBot) {
            ctx.moveTo(hit.x, hit.y);
            startedBot = true;
          } else {
            ctx.lineTo(hit.x, hit.y);
          }
        }
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 3.0;
        ctx.stroke();
      } else if (activeGeo === "dwdi_super") {
        // DWDI Superimposed: BOTH upper weld (wider magnified orange band) and lower weld (sharp gold band) overlap at z = 0!
        ctx.beginPath();
        let startedSup = false;
        for (let deg = 210; deg <= 330; deg += 5) {
          const rad = (deg * Math.PI) / 180;
          const hit = rayCastToDetector({
            x: R * 0.82 * Math.cos(rad),
            y: -R,
            z: 0,
          });
          if (!hit) continue;
          if (!startedSup) {
            ctx.moveTo(hit.x, hit.y);
            startedSup = true;
          } else {
            ctx.lineTo(hit.x, hit.y);
          }
        }
        // Outer magnified top-weld shadow
        ctx.strokeStyle = "rgba(249, 115, 22, 0.75)";
        ctx.lineWidth = 7.0;
        ctx.stroke();
        // Inner bottom-weld shadow superimposed on top
        ctx.strokeStyle = "#fde047";
        ctx.lineWidth = 2.5;
        ctx.stroke();
      } else {
        // SWSI or DWSI: SINGLE bottom weld shadow at z = 0 (upper weld is avoided in DWSI!)
        ctx.beginPath();
        let started = false;
        for (let deg = 225; deg <= 315; deg += 5) {
          const rad = (deg * Math.PI) / 180;
          const hit = project(
            rotZ(
              {
                x: Math.max(-detW * 0.45, Math.min(detW * 0.45, R * Math.cos(rad))),
                y: detY + 0.5,
                z: 0,
              },
              activeAngle,
            ),
          );
          if (!started) {
            ctx.moveTo(hit.x, hit.y);
            started = true;
          } else {
            ctx.lineTo(hit.x, hit.y);
          }
        }
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 3.4;
        ctx.stroke();
      }
    }

    // 7. Realistic 3D IQI Model (ISO 19232-1 Wire Pouch / ISO 19232-2 Step-Hole Plaque)
    const iqiYLocal = filmSide
      ? -R - wCap - Math.max(bgap * 0.22, R * 0.025) // Film side: outer bottom wall over weld
      : activeGeo === "swsi"
        ? -Ri + Math.max(0.8, R * 0.03) // SWSI source side: inner bottom surface over weld
        : R + wCap + Math.max(0.8, R * 0.03); // DWSI/DWDI source side: top outer wall over weld
    const iqiCenterX = R * 0.22;
    const iqiHalfW = Math.max(wHalf * 1.15, R * 0.16); // Circumferential half-width (across 6 wires)
    const iqiHalfZ = Math.max(wHalf * 1.65, R * 0.22); // Longitudinal half-length (wires crossing weld)
    const iqiWarn = activeGeo === "dwsi" && !filmSide;
    const isStepHoleIqi = /hole|step|kademe|delik|\bH\d/i.test(wireStr);

    const iqiPt = (dx: number, dz: number) => {
      // Follow pipe curvature slightly along x
      const xClamped = Math.max(-R * 0.85, Math.min(R * 0.85, iqiCenterX + dx));
      const ySign = iqiYLocal >= 0 ? 1 : -1;
      const rLocal = Math.abs(iqiYLocal);
      const yCurved =
        ySign * Math.sqrt(Math.max(rLocal * rLocal - xClamped * xClamped, rLocal * rLocal * 0.25));
      return project(rotZ({ x: xClamped, y: yCurved, z: dz }, activeAngle));
    };

    // Draw outer transparent protective PVC pouch / plaque base
    const pTL = iqiPt(-iqiHalfW, -iqiHalfZ);
    const pTR = iqiPt(iqiHalfW, -iqiHalfZ);
    const pBR = iqiPt(iqiHalfW, iqiHalfZ);
    const pBL = iqiPt(-iqiHalfW, iqiHalfZ);

    ctx.beginPath();
    ctx.moveTo(pTL.x, pTL.y);
    ctx.lineTo(pTR.x, pTR.y);
    ctx.lineTo(pBR.x, pBR.y);
    ctx.lineTo(pBL.x, pBL.y);
    ctx.closePath();
    ctx.fillStyle = iqiWarn
      ? "rgba(239, 68, 68, 0.28)"
      : isStepHoleIqi
        ? "rgba(148, 163, 184, 0.65)"
        : "rgba(56, 189, 248, 0.24)";
    ctx.fill();
    ctx.strokeStyle = iqiWarn ? "#ef4444" : "#38bdf8";
    ctx.lineWidth = 1.6;
    ctx.stroke();

    if (!isStepHoleIqi) {
      // Top & bottom lead identification strips inside the IQI pouch
      const drawLeadStrip = (zStart: number, zEnd: number) => {
        const s1 = iqiPt(-iqiHalfW * 0.88, zStart);
        const s2 = iqiPt(iqiHalfW * 0.88, zStart);
        const s3 = iqiPt(iqiHalfW * 0.88, zEnd);
        const s4 = iqiPt(-iqiHalfW * 0.88, zEnd);
        ctx.beginPath();
        ctx.moveTo(s1.x, s1.y);
        ctx.lineTo(s2.x, s2.y);
        ctx.lineTo(s3.x, s3.y);
        ctx.lineTo(s4.x, s4.y);
        ctx.closePath();
        ctx.fillStyle = "rgba(15, 23, 42, 0.86)";
        ctx.fill();
        ctx.strokeStyle = "rgba(250, 204, 21, 0.75)";
        ctx.lineWidth = 0.8;
        ctx.stroke();
      };
      drawLeadStrip(-iqiHalfZ * 0.92, -iqiHalfZ * 0.72);
      drawLeadStrip(iqiHalfZ * 0.72, iqiHalfZ * 0.92);

      // 6 parallel graded metallic wires straddling the girth weld (thick -> thin)
      for (let wIdx = 0; wIdx < 6; wIdx++) {
        const frac = -0.74 + (wIdx / 5) * 1.48;
        const wStart = iqiPt(iqiHalfW * frac, -iqiHalfZ * 0.7);
        const wEnd = iqiPt(iqiHalfW * frac, iqiHalfZ * 0.7);
        // Dark contrast halo under each wire
        ctx.beginPath();
        ctx.moveTo(wStart.x, wStart.y);
        ctx.lineTo(wEnd.x, wEnd.y);
        ctx.strokeStyle = "rgba(15, 23, 42, 0.75)";
        ctx.lineWidth = Math.max(1.2, 3.0 - wIdx * 0.34);
        ctx.stroke();
        // Metallic wire core
        ctx.beginPath();
        ctx.moveTo(wStart.x, wStart.y);
        ctx.lineTo(wEnd.x, wEnd.y);
        ctx.strokeStyle = iqiWarn ? "#fecaca" : "#f8fafc";
        ctx.lineWidth = Math.max(0.65, 2.2 - wIdx * 0.3);
        ctx.stroke();
      }
    } else {
      // Step-Hole IQI: 6 stepped pads with micro-holes
      for (let sIdx = 0; sIdx < 6; sIdx++) {
        const z0 = -iqiHalfZ * 0.85 + (sIdx / 6) * (iqiHalfZ * 1.7);
        const z1 = z0 + (iqiHalfZ * 1.7) / 6;
        const holeCenter = iqiPt(0, (z0 + z1) * 0.5);
        ctx.beginPath();
        ctx.arc(holeCenter.x, holeCenter.y, Math.max(1.2, 2.6 - sIdx * 0.25), 0, Math.PI * 2);
        ctx.fillStyle = "#0f172a";
        ctx.fill();
      }
    }

    // Floating IQI designation tag with leader line to the 3D IQI pouch
    const iqiAnchor = iqiPt(iqiHalfW, 0);
    const iqiLabelX = iqiAnchor.x + 22;
    const iqiLabelY = iqiAnchor.y - 10;
    const iqiShortCode = wireStr.split(" ")[0] || "IQI";
    const iqiTagText = `IQI (${iqiShortCode})`;
    ctx.beginPath();
    ctx.moveTo(iqiAnchor.x, iqiAnchor.y);
    ctx.lineTo(iqiLabelX - 4, iqiLabelY);
    ctx.strokeStyle = iqiWarn ? "#ef4444" : "#38bdf8";
    ctx.lineWidth = 1.3;
    ctx.stroke();

    ctx.font = "700 9.5px system-ui, sans-serif";
    const iqiTagW = Math.max(46, ctx.measureText(iqiTagText).width + 12);
    ctx.fillStyle = iqiWarn ? "#ef4444" : "#0284c7";
    ctx.strokeStyle = isDark ? "#0f172a" : "#ffffff";
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.roundRect(iqiLabelX - 4, iqiLabelY - 9, iqiTagW, 18, 4);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(iqiTagText, iqiLabelX - 4 + iqiTagW / 2, iqiLabelY);

    // 8. Draw Glowing 3D Radiation Source Sphere + Focal Spot Ring
    const srcGlow = ctx.createRadialGradient(
      srcProj.x,
      srcProj.y,
      2,
      srcProj.x,
      srcProj.y,
      20,
    );
    srcGlow.addColorStop(0, "rgba(239, 68, 68, 0.95)");
    srcGlow.addColorStop(0.45, "rgba(249, 115, 22, 0.55)");
    srcGlow.addColorStop(1, "rgba(249, 115, 22, 0)");
    ctx.fillStyle = srcGlow;
    ctx.beginPath();
    ctx.arc(srcProj.x, srcProj.y, 20, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#ef4444";
    ctx.strokeStyle = "#fef08a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(srcProj.x, srcProj.y, 6.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // 9. 3D Engineering Callouts & Dimension Overlay
    if (showDimensions) {
      ctx.font = "600 11px system-ui, sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";

      // Source label with technique-specific Z-offset explanation
      ctx.fillStyle = isDark ? "#fef08a" : "#9a3412";
      const srcOffsetNote =
        activeGeo === "dwsi"
          ? lang === "tr"
            ? ` • Z-Ofset (Üst Kaynak Dışı): ${zSourceBase.toFixed(0)} mm`
            : ` • Z-Offset (Avoids Top Weld): ${zSourceBase.toFixed(0)} mm`
          : activeGeo === "dwdi_elliptic"
            ? lang === "tr"
              ? ` • Eliptik Z-Ofset: ${zSourceBase.toFixed(0)} mm (16°)`
              : ` • Elliptical Z-Offset: ${zSourceBase.toFixed(0)} mm (16°)`
            : activeGeo === "dwdi_super"
              ? lang === "tr"
                ? " • Z=0 (Dik / Üst+Alt Çakışık)"
                : " • Z=0 (Perpendicular / Superimposed)"
              : "";
      ctx.fillText(
        `S (d=${Number(d || 0).toFixed(1)} mm)${srcOffsetNote}`,
        srcProj.x + 12,
        srcProj.y - 6,
      );

      // SFD / SDD label along central beam
      const midBeam = {
        x: (srcProj.x + detCenterProj.x) / 2,
        y: (srcProj.y + detCenterProj.y) / 2,
      };
      const sfdSafe = Number(sfd || 0);
      const fMinSafe = Number(fMin || 0);
      const sfdTag = `${isDigital ? "SDD" : "SFD"} = ${sfdSafe.toFixed(0)} mm${fMinSafe > 0 ? ` (f_min=${fMinSafe.toFixed(0)})` : ""}`;
      ctx.fillStyle = isDark ? "rgba(15, 23, 42, 0.82)" : "rgba(255, 255, 255, 0.88)";
      const tagW = ctx.measureText(sfdTag).width + 12;
      ctx.beginPath();
      ctx.roundRect(midBeam.x + 8, midBeam.y - 10, tagW, 20, 4);
      ctx.fill();
      ctx.strokeStyle = isDark ? "rgba(250, 204, 21, 0.5)" : "rgba(234, 88, 12, 0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = isDark ? "#fde047" : "#c2410c";
      ctx.fillText(sfdTag, midBeam.x + 14, midBeam.y);

      // Detector & projected image mode callout
      const projModeTag =
        activeGeo === "dwsi"
          ? lang === "tr"
            ? "Tek Görüntü (Sadece Alt Kaynak)"
            : "Single Image (Bottom Weld Only)"
          : activeGeo === "dwdi_elliptic"
            ? lang === "tr"
              ? "Çift Görüntü (Eliptik: Üst + Alt Kaynak Ayrı)"
              : "Double Image (Elliptical: Top + Bottom Separated)"
            : activeGeo === "dwdi_super"
              ? lang === "tr"
                ? "Çift Görüntü (Üst + Alt Kaynak Üst Üste Çakışık)"
                : "Double Image (Top + Bottom Weld Superimposed)"
              : lang === "tr"
                ? "Tek Cidar Tek Görüntü (Alt Kaynak)"
                : "Single Wall Single Image";
      const bSafe = Number(bDist || 0);
      const detTag = isDigital
        ? `${isPlanar ? "DDA Panel" : "Esnek CR"} • b=${bSafe.toFixed(1)} mm • ${projModeTag}`
        : `Film • b=${bSafe.toFixed(1)} mm • ${projModeTag}`;
      ctx.fillStyle = isDark ? "#6ee7b7" : "#047857";
      ctx.textAlign = "center";
      ctx.fillText(detTag, detCenterProj.x, detCenterProj.y + 22);

      // Pipe OD & t badge at left end of pipe
      const pipeEndProj = project({ x: -R, y: 0, z: -halfLen });
      ctx.textAlign = "left";
      ctx.fillStyle = isDark ? "#93c5fd" : "#1e40af";
      ctx.fillText(
        `Ø${Number(od || 0).toFixed(1)} × ${Number(t || 0).toFixed(2)} mm`,
        Math.max(12, pipeEndProj.x - 20),
        Math.max(24, pipeEndProj.y - 14),
      );
    }

    // 10. Top-Left 3D Orientation Gizmo (X / Y / Z Axes)
    const gizmoCx = 42;
    const gizmoCy = 46;
    const gizmoLen = 22;
    const axes: { label: string; vec: Vec3; color: string }[] = [
      { label: "X", vec: { x: 1, y: 0, z: 0 }, color: "#ef4444" },
      { label: "Y", vec: { x: 0, y: 1, z: 0 }, color: "#22c55e" },
      { label: "Z (Boru)", vec: { x: 0, y: 0, z: 1 }, color: "#3b82f6" },
    ];
    ctx.beginPath();
    ctx.arc(gizmoCx, gizmoCy, 30, 0, Math.PI * 2);
    ctx.fillStyle = isDark ? "rgba(15, 23, 42, 0.72)" : "rgba(255, 255, 255, 0.78)";
    ctx.fill();
    for (const ax of axes) {
      const x1 = ax.vec.x * cosY + ax.vec.z * sinY;
      const z1 = -ax.vec.x * sinY + ax.vec.z * cosY;
      const y2 = ax.vec.y * cosP - z1 * sinP;
      const ex = gizmoCx + x1 * gizmoLen;
      const ey = gizmoCy - y2 * gizmoLen;
      ctx.beginPath();
      ctx.moveTo(gizmoCx, gizmoCy);
      ctx.lineTo(ex, ey);
      ctx.strokeStyle = ax.color;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = ax.color;
      ctx.font = "700 9px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(ax.label, gizmoCx + x1 * (gizmoLen + 9), gizmoCy - y2 * (gizmoLen + 9));
    }

    // 11. Top-Right HUD Summary Pill (Technique, Ug, IQI, Safety)
    const hudLines = [
      `${activeGeo.toUpperCase()} • N=${nApplied > 0 ? `${nApplied}/${nRequired}` : nRequired} Poz`,
      `Ug = ${Number(ug || 0).toFixed(3)} mm • IQI: ${wireStr.split(" ")[0] || wireStr}${isDigital && duplexStr !== "N/A" ? ` / ${duplexStr.split(" ")[0]}` : ""} (${filmSide ? (lang === "tr" ? "Film Tarafı" : "Film Side") : lang === "tr" ? "Kaynak Tarafı" : "Source Side"})`,
    ];
    if (safetyRadiusM && safetyRadiusM > 0) {
      hudLines.push(
        lang === "tr"
          ? `Barikat: Kontrollü ${safetyRadiusM.toFixed(1)}m${supervisedRadiusM ? ` | Gözetimli ${supervisedRadiusM.toFixed(1)}m` : ""}`
          : `Barrier: Ctrl ${safetyRadiusM.toFixed(1)}m${supervisedRadiusM ? ` | Sup ${supervisedRadiusM.toFixed(1)}m` : ""}`,
      );
    }
    ctx.font = "600 10px system-ui, sans-serif";
    const boxW =
      Math.max(...hudLines.map((l) => ctx.measureText(l).width)) + 18;
    const boxH = hudLines.length * 16 + 10;
    ctx.fillStyle = isDark ? "rgba(15, 23, 42, 0.82)" : "rgba(255, 255, 255, 0.88)";
    ctx.strokeStyle = isDark ? "rgba(148, 163, 184, 0.25)" : "rgba(100, 116, 139, 0.25)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(width - boxW - 10, 10, boxW, boxH, 6);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = isDark ? "#e2e8f0" : "#1e293b";
    ctx.textAlign = "left";
    hudLines.forEach((line, idx) => {
      ctx.fillText(line, width - boxW - 1, 22 + idx * 16);
    });

    ctx.restore();
  }, [
    od,
    t,
    cap,
    weldWidth,
    d,
    activeGeo,
    sfd,
    fMin,
    bDist,
    bed,
    bgap,
    ug,
    isPlanar,
    isDigital,
    filmSide,
    panelWidth,
    panelHeight,
    filmWidth,
    filmHeight,
    overlapPct,
    nRequired,
    nApplied,
    wireStr,
    duplexStr,
    safetyRadiusM,
    supervisedRadiusM,
    theme,
    lang,
    yaw,
    pitch,
    zoom,
    panX,
    panY,
    cutaway,
    pipeOpacity,
    showAllStations,
    safeStation,
    stationStepRad,
    showDimensions,
    showProjection,
    totalStations,
  ]);

  const tr = lang === "tr";

  return (
    <div className="sketch-3d-wrapper">
      {geometryForced && userGeometry && (
        <div className="sketch-3d-notice">
          <span>
            {tr
              ? `Not: OD (${od} mm) > 100 mm olduğu için motor DWSI hesapladı.`
              : `Note: OD (${od} mm) > 100 mm forced engine calculation to DWSI.`}
          </span>
          <button
            type="button"
            className="sketch-mini-btn"
            onClick={() => setPreviewUserGeo((v) => !v)}
          >
            {previewUserGeo
              ? tr
                ? `Şu an: ${userGeometry.toUpperCase()} Önizleme (DWSI Göster)`
                : `Showing: ${userGeometry.toUpperCase()} Preview (Show DWSI)`
              : tr
                ? `Şu an: DWSI (Seçilen ${userGeometry.toUpperCase()} Göster)`
                : `Showing: DWSI (Preview ${userGeometry.toUpperCase()})`}
          </button>
        </div>
      )}

      <div className="sketch-3d-toolbar">
        <div className="sketch-btn-group">
          <button
            type="button"
            className="sketch-mini-btn"
            onClick={() => applyCameraPreset("iso")}
            title={tr ? "İzometrik 3D Kamera" : "Isometric 3D Camera"}
          >
            {tr ? "3D İzometrik" : "3D Iso"}
          </button>
          <button
            type="button"
            className="sketch-mini-btn"
            onClick={() => applyCameraPreset("cross")}
            title={tr ? "Boru Ekseninden Enine Kesit (X-Y)" : "Cross-Section (X-Y)"}
          >
            {tr ? "Enine Kesit" : "Cross-Section"}
          </button>
          <button
            type="button"
            className="sketch-mini-btn"
            onClick={() => applyCameraPreset("longitudinal")}
            title={
              tr
                ? "Boyuna Görünüm (Eliptik Açıyı ve Z Ekseni Ofsetini Gösterir)"
                : "Longitudinal Side View (Shows Z-axis Elliptical Tilt)"
            }
          >
            {tr ? "Boyuna (Eliptik)" : "Side (Elliptic)"}
          </button>
          <button
            type="button"
            className="sketch-mini-btn"
            onClick={() => applyCameraPreset("beam")}
            title={
              tr
                ? "Kaynaktan Dedektöre Bakış (Radyografik İzdüşüm)"
                : "Beam's-Eye View (Radiographic Projection)"
            }
          >
            {tr ? "Işın Gözü" : "Beam's-Eye"}
          </button>
        </div>

        <div className="sketch-btn-group">
          <button
            type="button"
            className={`sketch-mini-btn ${cutaway ? "active" : ""}`}
            onClick={() => setCutaway((v) => !v)}
          >
            {tr ? "Kesit" : "Cutaway"}
          </button>
          <button
            type="button"
            className={`sketch-mini-btn ${showProjection ? "active" : ""}`}
            onClick={() => setShowProjection((v) => !v)}
          >
            {tr ? "Kaynak İzdüşümü" : "Weld Shadow"}
          </button>
          <button
            type="button"
            className={`sketch-mini-btn ${showDimensions ? "active" : ""}`}
            onClick={() => setShowDimensions((v) => !v)}
          >
            {tr ? "Ölçüler" : "Dimensions"}
          </button>
        </div>
      </div>

      <canvas
        ref={canvasRef}
        className="sketch-3d-canvas"
        style={{ width: "100%", height: "auto", aspectRatio: "520 / 430" }}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          dragRef.current = {
            active: true,
            shift: event.shiftKey,
            startX: event.clientX,
            startY: event.clientY,
            startYaw: yaw,
            startPitch: pitch,
            startPanX: panX,
            startPanY: panY,
          };
        }}
        onPointerMove={(event) => {
          if (!dragRef.current.active) return;
          const dx = event.clientX - dragRef.current.startX;
          const dy = event.clientY - dragRef.current.startY;
          if (dragRef.current.shift) {
            setPanX(dragRef.current.startPanX + dx);
            setPanY(dragRef.current.startPanY + dy);
          } else {
            setYaw(dragRef.current.startYaw + dx * 0.01);
            setPitch(
              Math.max(
                -Math.PI / 2 + 0.05,
                Math.min(Math.PI / 2 - 0.05, dragRef.current.startPitch + dy * 0.01),
              ),
            );
          }
        }}
        onPointerUp={(event) => {
          dragRef.current.active = false;
          if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
          }
        }}
        onWheel={(event) => {
          event.preventDefault();
          const factor = event.deltaY < 0 ? 1.1 : 0.9;
          setZoom((z) => Math.max(0.45, Math.min(3.0, z * factor)));
        }}
      />

      <div className="sketch-3d-footer">
        <div className="sketch-station-bar">
          <label
            className="sketch-station-label"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, marginRight: 8 }}
            title={
              tr
                ? "Boru dış yüzeyinin saydamlık (opaklık) oranını ayarlar; et kalınlığı kesitleri koyu kalır"
                : "Adjusts pipe outer surface opacity while keeping wall thickness sections dark"
            }
          >
            <span>{tr ? "Boru Opaklığı:" : "Pipe Opacity:"}</span>
            <input
              type="range"
              min={0.15}
              max={1.0}
              step={0.05}
              value={pipeOpacity}
              onChange={(event) => setPipeOpacity(Number(event.target.value))}
              style={{ width: 76 }}
              aria-label={tr ? "Boru Opaklığı" : "Pipe Opacity"}
            />
            <span style={{ minWidth: 32 }}>{Math.round(pipeOpacity * 100)}%</span>
          </label>
          <button
            type="button"
            className={`sketch-mini-btn ${showAllStations ? "active" : ""}`}
            onClick={() => setShowAllStations((v) => !v)}
          >
            {tr
              ? `Tüm İstasyonlar (${totalStations})`
              : `All Stations (${totalStations})`}
          </button>
          {totalStations > 1 && (
            <>
              <button
                type="button"
                className={`sketch-mini-btn ${playing ? "active" : ""}`}
                onClick={() => setPlaying((v) => !v)}
              >
                {playing ? (tr ? "⏸ Durdur" : "⏸ Pause") : tr ? "▶ Poz Döndür" : "▶ Rotate"}
              </button>
              <input
                type="range"
                min={0}
                max={totalStations - 1}
                step={1}
                value={safeStation}
                onChange={(event) => {
                  setPlaying(false);
                  setActiveStation(Number(event.target.value));
                }}
                aria-label={tr ? "Poz İstasyonu" : "Exposure Station"}
              />
              <span className="sketch-station-label">
                {tr
                  ? `İstasyon #${safeStation + 1}/${totalStations} (${Math.round((safeStation * stationStepRad * 180) / Math.PI)}°)`
                  : `Station #${safeStation + 1}/${totalStations} (${Math.round((safeStation * stationStepRad * 180) / Math.PI)}°)`}
              </span>
            </>
          )}
        </div>
        <span className="sketch-3d-hint">
          {tr
            ? "Sürükle: 3D Döndür • Shift+Sürükle: Kaydır • Tekerlek: Yakınlaştır"
            : "Drag: 3D Orbit • Shift+Drag: Pan • Wheel: Zoom"}
        </span>
      </div>
    </div>
  );
}
