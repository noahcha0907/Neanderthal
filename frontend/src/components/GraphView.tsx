import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import ForceGraph3D from '3d-force-graph';
import * as THREE from 'three';
import type { GraphNode, GraphState } from '../types/graph';
import { nodeColor } from '../utils/nodeStyle';

type GraphTheme = 'dark' | 'light' | 'earth' | 'blue';

const THEME_BG: Record<GraphTheme, string> = {
  dark:  '#141414',
  light: '#ffffff',
  earth: '#3d2410',
  blue:  '#0047FF',
};

interface Props {
  graphData: GraphState;
  onNodeClick?: (node: GraphNode) => void;
  onSettled?: () => void;      // fired when the force simulation stops
  onResimulating?: () => void; // fired when new data starts re-simulating
  heatMap?: Map<string, number>;
  pointerTool?: boolean; // when false (move mode) clicks do not select nodes
  graphTheme?: GraphTheme;
  onCameraChange?: (azimuth: number, elevation: number) => void;
}

export interface GraphViewHandle {
  pulseAll(durationMs: number): void;
  animateVoters(voterIds: string[], totalMs: number): void;
  focusNode(nodeId: string): void;
  setOrbitLock(enabled: boolean): void;
  resetView(): void;
}

// ── Shaders ───────────────────────────────────────────────────────────────────
// All nodes rendered in ONE draw call via THREE.Points.
// Per-point size (aSize) + per-point color (aColor) handled in the vertex shader.
// Fragment shader discards corners to produce circular points.

const VERT = `
attribute float aSize;
attribute vec3 aColor;
varying vec3 vColor;
void main() {
  vColor = aColor;
  vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = aSize * (500.0 / -mvPos.z);
  gl_Position = projectionMatrix * mvPos;
}
`;

const FRAG = `
precision mediump float;
varying vec3 vColor;
void main() {
  // Upward-pointing triangle via point-in-triangle edge test
  vec2 p = gl_PointCoord;
  vec2 a = vec2(0.5,  0.05); // apex (top center)
  vec2 b = vec2(0.05, 0.93); // bottom left
  vec2 c = vec2(0.95, 0.93); // bottom right
  float d1 = (p.x - b.x) * (a.y - b.y) - (a.x - b.x) * (p.y - b.y);
  float d2 = (p.x - c.x) * (b.y - c.y) - (b.x - c.x) * (p.y - c.y);
  float d3 = (p.x - a.x) * (c.y - a.y) - (c.x - a.x) * (p.y - a.y);
  bool has_neg = (d1 < 0.0) || (d2 < 0.0) || (d3 < 0.0);
  bool has_pos = (d1 > 0.0) || (d2 > 0.0) || (d3 > 0.0);
  if (has_neg && has_pos) discard;
  gl_FragColor = vec4(vColor, 1.0);
}
`;

// ── Data helpers ──────────────────────────────────────────────────────────────

function toForceGraphData(state: GraphState) {
  return {
    nodes: state.nodes.map(n => ({
      ...n,
      __baseSize: n.kind === 'concept' ? 50 : n.kind === 'artwork' ? 22 : 10,
      __color: '#' + nodeColor(n.kind, n.doc_type).toString(16).padStart(6, '0'),
    })),
    links: state.edges.map(e => ({
      source: e.source,
      target: e.target,
      __weight: e.weight,
      __kind: e.kind,
    })),
  };
}

// ── Heat helpers ──────────────────────────────────────────────────────────────

function heatNorm(count: number): number {
  return Math.min(count / 8, 1);
}

function heatScaleMult(count: number): number {
  return 1 + heatNorm(count) * 0.4;
}

const _white = new THREE.Color(0xffffff);
const _amber = new THREE.Color(0xfb923c);
function heatColor(count: number): THREE.Color {
  return new THREE.Color().lerpColors(_white, _amber, heatNorm(count) * 0.65);
}

// ── Node buffer ───────────────────────────────────────────────────────────────

interface NodeBuffers {
  points: THREE.Points;
  posAttr: THREE.BufferAttribute;
  colorAttr: THREE.BufferAttribute;
  sizeAttr: THREE.BufferAttribute;
  indexMap: Map<string, number>;   // nodeId → flat index
  reverseMap: Map<number, string>; // flat index → nodeId (for raycast hit lookup)
  baseColors: Float32Array;
  baseSizes: Float32Array;
}

function buildNodeBuffers(nodes: any[]): NodeBuffers {
  const n = nodes.length;
  const pos = new Float32Array(n * 3);
  const col = new Float32Array(n * 3);
  const sz = new Float32Array(n);
  const baseColors = new Float32Array(n * 3);
  const baseSizes = new Float32Array(n);
  const indexMap = new Map<string, number>();
  const reverseMap = new Map<number, string>();
  const tmpColor = new THREE.Color();

  nodes.forEach((node, i) => {
    indexMap.set(node.id, i);
    reverseMap.set(i, node.id);

    pos[i * 3] = node.x ?? 0;
    pos[i * 3 + 1] = node.y ?? 0;
    pos[i * 3 + 2] = node.z ?? 0;

    tmpColor.set(node.__color ?? '#ffffff');
    col[i * 3] = baseColors[i * 3] = tmpColor.r;
    col[i * 3 + 1] = baseColors[i * 3 + 1] = tmpColor.g;
    col[i * 3 + 2] = baseColors[i * 3 + 2] = tmpColor.b;

    const base = node.__baseSize ?? 8;
    sz[i] = baseSizes[i] = base;
  });

  const geo = new THREE.BufferGeometry();
  const posAttr = new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage);
  const colorAttr = new THREE.BufferAttribute(col, 3).setUsage(THREE.DynamicDrawUsage);
  const sizeAttr = new THREE.BufferAttribute(sz, 1).setUsage(THREE.DynamicDrawUsage);

  geo.setAttribute('position', posAttr);
  geo.setAttribute('aColor', colorAttr);
  geo.setAttribute('aSize', sizeAttr);

  const mat = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false; // prevent culling of points outside frustum bounds

  return { points, posAttr, colorAttr, sizeAttr, indexMap, reverseMap, baseColors, baseSizes };
}

// ── Component ─────────────────────────────────────────────────────────────────

export const GraphView = forwardRef<GraphViewHandle, Props>(function GraphView(
  { graphData, onNodeClick, onSettled, onResimulating, heatMap, pointerTool = true, graphTheme = 'dark', onCameraChange },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const buffersRef = useRef<NodeBuffers | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const syncRafRef = useRef<number | null>(null);
  const pointerToolRef = useRef(pointerTool);
  const simRunningRef = useRef(true);
  const heatRef = useRef<Map<string, number>>(new Map());
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const onSettledRef = useRef(onSettled);
  useEffect(() => { onSettledRef.current = onSettled; }, [onSettled]);
  const onResimulatingRef = useRef(onResimulating);
  useEffect(() => { onResimulatingRef.current = onResimulating; }, [onResimulating]);
  const graphThemeRef = useRef(graphTheme);
  useEffect(() => { graphThemeRef.current = graphTheme; }, [graphTheme]);
  const onCameraChangeRef = useRef(onCameraChange);
  useEffect(() => { onCameraChangeRef.current = onCameraChange; }, [onCameraChange]);
  const controlsRef = useRef<any>(null);
  const initialCamRef = useRef<{ x: number; y: number; z: number } | null>(null);
  const orbitActiveRef = useRef(false);
  const orbitLastTimeRef = useRef<number | null>(null);
  const orbitRafRef = useRef<number | null>(null);

  // ── Tool switch: toggle OrbitControls and cursor ──────────────────────────
  useEffect(() => {
    pointerToolRef.current = pointerTool;
    if (!graphRef.current || !containerRef.current) return;
    const controls = graphRef.current.controls();
    controls.enabled = !pointerTool;
    containerRef.current.style.cursor = pointerTool ? 'default' : 'grab';
  }, [pointerTool]);

  // ── Position sync ─────────────────────────────────────────────────────────
  // Copies force-simulation node positions into the Points geometry buffer each frame.
  // Runs as long as simRunningRef is true (set false by onEngineStop).

  function startSyncLoop() {
    if (syncRafRef.current) cancelAnimationFrame(syncRafRef.current);
    simRunningRef.current = true;

    const step = () => {
      const b = buffersRef.current;
      const g = graphRef.current;
      if (!b || !g) return;
      const nodes: any[] = g.graphData().nodes;
      for (const node of nodes) {
        const idx = b.indexMap.get(node.id);
        if (idx === undefined) continue;
        b.posAttr.array[idx * 3] = node.x ?? 0;
        b.posAttr.array[idx * 3 + 1] = node.y ?? 0;
        b.posAttr.array[idx * 3 + 2] = node.z ?? 0;
      }
      b.posAttr.needsUpdate = true;
      if (simRunningRef.current) syncRafRef.current = requestAnimationFrame(step);
    };
    syncRafRef.current = requestAnimationFrame(step);
  }

  // ── Heat ──────────────────────────────────────────────────────────────────

  function applyHeatToBuffers(heat: Map<string, number>) {
    const buf = buffersRef.current;
    if (!buf) return;
    const { indexMap, colorAttr, sizeAttr, baseColors, baseSizes } = buf;
    const tc = new THREE.Color();
    for (const [id, idx] of indexMap) {
      const count = heat.get(id) ?? 0;
      if (count > 0) {
        tc.copy(heatColor(count));
        colorAttr.array[idx * 3]     = tc.r;
        colorAttr.array[idx * 3 + 1] = tc.g;
        colorAttr.array[idx * 3 + 2] = tc.b;
        sizeAttr.array[idx] = baseSizes[idx] * heatScaleMult(count);
      } else {
        // No heat — restore the node's base color and size
        colorAttr.array[idx * 3]     = baseColors[idx * 3];
        colorAttr.array[idx * 3 + 1] = baseColors[idx * 3 + 1];
        colorAttr.array[idx * 3 + 2] = baseColors[idx * 3 + 2];
        sizeAttr.array[idx] = baseSizes[idx];
      }
    }
    colorAttr.needsUpdate = true;
    sizeAttr.needsUpdate = true;
  }

  // ── Imperative animation API ──────────────────────────────────────────────

  useImperativeHandle(ref, () => ({
    pulseAll(_durationMs: number) {
      // Waves radiate from a random node. Color mode is chosen randomly each call.
      if (!graphRef.current) return;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

      const COLOR_MODES = ['lightblue', 'green', 'red', 'white', 'black', 'rainbow'] as const;
      const colorMode = COLOR_MODES[Math.floor(Math.random() * COLOR_MODES.length)];

      const gd = graphRef.current.graphData();
      const nodePos = new Map<string, { x: number; y: number; z: number }>();
      for (const n of gd.nodes as any[]) nodePos.set(n.id, { x: n.x ?? 0, y: n.y ?? 0, z: n.z ?? 0 });

      // Random node — wave origin
      const allNodes = gd.nodes as any[];
      const originNode = allNodes[Math.floor(Math.random() * allNodes.length)];
      const cx = originNode?.x ?? 0;
      const cy = originNode?.y ?? 0;
      const cz = originNode?.z ?? 0;

      // Normalised distance (0–1) for each edge's midpoint from centroid
      let maxDist = 0;
      const edgeDist = new Map<string, number>();
      for (const link of gd.links as any[]) {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source;
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
        const sp = nodePos.get(srcId) ?? { x: cx, y: cy, z: cz };
        const tp = nodePos.get(tgtId) ?? { x: cx, y: cy, z: cz };
        const d = Math.sqrt(
          ((sp.x + tp.x) / 2 - cx) ** 2 +
          ((sp.y + tp.y) / 2 - cy) ** 2 +
          ((sp.z + tp.z) / 2 - cz) ** 2,
        );
        edgeDist.set(`${srcId}→${tgtId}`, d);
        if (d > maxDist) maxDist = d;
      }
      if (maxDist === 0) maxDist = 1;

      // Each wave is fixed at 1 second regardless of the generation budget.
      const numWaves = 5;
      const waveMs  = 1500;
      const sweepMs = waveMs * 0.65;
      const glowMs  = waveMs * 0.35;

      const originalLinkColor = (link: any): string => {
        if (graphThemeRef.current === 'blue') {
          if (link.__kind === 'influence') return 'rgba(0,0,0,0.85)';
          return 'rgba(255,255,255,0.75)';
        }
        if (graphThemeRef.current === 'light') {
          if (link.__kind === 'influence') return 'rgba(251,191,36,0.8)';
          return 'rgba(37,99,235,0.55)';
        }
        if (link.__kind === 'influence') return 'rgba(251,191,36,0.8)';
        if (link.__kind === 'concept') return 'rgba(59,130,246,0.6)';
        return 'rgba(148,163,184,0.25)';
      };

      const start = performance.now();
      const tick = () => {
        const elapsed = performance.now() - start;
        graphRef.current.linkColor((link: any) => {
          const srcId = typeof link.source === 'object' ? link.source.id : link.source;
          const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
          const edgeDelay = (edgeDist.get(`${srcId}→${tgtId}`) ?? 0) / maxDist * sweepMs;

          for (let w = 0; w < numWaves; w++) {
            const local = elapsed - w * waveMs - edgeDelay;
            if (local > 0 && local < glowMs) {
              const env = Math.sin((local / glowMs) * Math.PI) * 0.85;
              switch (colorMode) {
                case 'lightblue': return `rgba(120,200,255,${env.toFixed(2)})`;
                case 'green':     return `rgba(0,255,136,${env.toFixed(2)})`;
                case 'red':       return `rgba(255,60,60,${env.toFixed(2)})`;
                case 'white':     return `rgba(255,255,255,${env.toFixed(2)})`;
                case 'black':     return `rgba(0,0,0,${env.toFixed(2)})`;
                case 'rainbow': {
                  // Hue determined by edge's distance from origin → full spectrum across the wave
                  const hue = ((edgeDist.get(`${srcId}→${tgtId}`) ?? 0) / maxDist * 360) % 360;
                  return `hsla(${hue.toFixed(0)},100%,65%,${env.toFixed(2)})`;
                }
              }
            }
          }
          return originalLinkColor(link);
        });
        if (elapsed < numWaves * waveMs) {
          animFrameRef.current = requestAnimationFrame(tick);
        } else {
          graphRef.current?.linkColor(originalLinkColor);
        }
      };
      animFrameRef.current = requestAnimationFrame(tick);
    },

    animateVoters(_voterIds: string[], _totalMs: number) {
      // Generation is visualised by pulseAll alone — no voter-specific animation.
    },

    focusNode(nodeId: string) {
      if (!graphRef.current) return;
      const node = (graphRef.current.graphData().nodes as any[]).find(n => n.id === nodeId);
      if (!node) return;
      // Fly toward the node from the current camera direction, stop at distance 120
      const cam = graphRef.current.camera() as THREE.PerspectiveCamera;
      const nx = node.x ?? 0, ny = node.y ?? 0, nz = node.z ?? 0;
      const dx = cam.position.x - nx;
      const dy = cam.position.y - ny;
      const dz = cam.position.z - nz;
      const len = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
      graphRef.current.cameraPosition(
        { x: nx + (dx / len) * 120, y: ny + (dy / len) * 120, z: nz + (dz / len) * 120 },
        { x: nx, y: ny, z: nz },
        800,
      );
    },

    setOrbitLock(enabled: boolean) {
      orbitActiveRef.current = enabled;
      if (orbitRafRef.current !== null) {
        cancelAnimationFrame(orbitRafRef.current);
        orbitRafRef.current = null;
      }
      orbitLastTimeRef.current = null;
      if (!enabled) return;

      const tick = (timestamp: number) => {
        if (!orbitActiveRef.current || !graphRef.current) return;
        const dt = orbitLastTimeRef.current !== null
          ? Math.min((timestamp - orbitLastTimeRef.current) / 1000, 0.05)
          : 0;
        orbitLastTimeRef.current = timestamp;

        if (dt > 0) {
          const cam = graphRef.current.camera() as THREE.PerspectiveCamera;
          const controls = controlsRef.current;
          const tx = controls?.target?.x ?? 0;
          const ty = controls?.target?.y ?? 0;
          const tz = controls?.target?.z ?? 0;
          const angle = 0.7 * dt; // 0.7 rad/s ≈ 40°/s, frame-rate independent
          const dx = cam.position.x - tx;
          const dz = cam.position.z - tz;
          const cos = Math.cos(angle);
          const sin = Math.sin(angle);
          const nx = tx + dx * cos + dz * sin;
          const nz = tz - dx * sin + dz * cos;
          const azimuth = Math.atan2(nx - tx, nz - tz);
          const radius = Math.sqrt(dx * dx + dz * dz);
          cam.position.x = nx;
          cam.position.z = nz;
          cam.position.y = ty + Math.sin(azimuth) * radius * 0.12;
          cam.lookAt(tx, ty, tz);
        }
        orbitRafRef.current = requestAnimationFrame(tick);
      };
      orbitRafRef.current = requestAnimationFrame(tick);
    },

    resetView() {
      if (!graphRef.current || !initialCamRef.current) return;
      graphRef.current.cameraPosition(initialCamRef.current, { x: 0, y: 0, z: 0 }, 800);
    },
  }));

  // ── Graph mount ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (!containerRef.current) return;

    // Tooltip DOM element — positioned at cursor on hover
    const tooltip = document.createElement('div');
    tooltip.style.cssText = [
      'position:fixed',
      'background:rgba(0,0,0,0.72)',
      'color:#e2e8f0',
      'padding:4px 8px',
      'border-radius:4px',
      'font-size:11px',
      'font-family:ui-monospace,monospace',
      'pointer-events:none',
      'display:none',
      'z-index:9999',
      'max-width:280px',
      'word-break:break-word',
    ].join(';');
    document.body.appendChild(tooltip);
    tooltipRef.current = tooltip;

    const Graph = (ForceGraph3D as any)()(containerRef.current)
      .backgroundColor('#141414')
      // Invisible Object3D per node — only used by the force simulation for
      // position tracking. All visible rendering is handled by our Points object.
      .nodeThreeObject(() => { const o = new THREE.Object3D(); o.visible = false; return o; })
      .nodeThreeObjectExtend(false)
      .linkWidth((link: any) => {
        const isBlue = graphThemeRef.current === 'blue';
        if (link.__kind === 'influence') return isBlue ? 5 : 3;
        if (link.__kind === 'concept') return 1.8;
        return Math.max(0.6, (link.__weight ?? 0) * 3);
      })
      .linkColor((link: any) => {
        if (link.__kind === 'influence') return 'rgba(251,191,36,0.8)';
        if (link.__kind === 'concept') return 'rgba(59,130,246,0.6)';
        return 'rgba(148,163,184,0.25)';
      })
      // Links and particles hidden during simulation — eliminates their draw calls
      // while nodes are spreading, then fades them in once positions have settled.
      .linkVisibility(false)
      .linkDirectionalParticles(0)
      .linkDirectionalParticleSpeed(0.004)
      .cooldownTicks(200)
      .d3AlphaDecay(0.04)
      .d3VelocityDecay(0.4)
      .onEngineStop(() => {
        simRunningRef.current = false;
        Graph.linkVisibility(true);
        Graph.linkDirectionalParticles((link: any) => link.__kind === 'influence' ? 2 : 0);
        onSettledRef.current?.();
      })
      .graphData(toForceGraphData(graphData));

    graphRef.current = Graph;

    // ── OrbitControls setup ────────────────────────────────────────────────
    // The library's render loop calls controls.update() every frame, so
    // damping works without any custom RAF. We just configure it and let it run.
    const controls = Graph.controls();
    controlsRef.current = controls;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;   // lower = more inertia / smoother coast
    controls.rotateSpeed = 0.6;
    controls.panSpeed = 0.8;
    controls.zoomSpeed = 1.0;
    // Start in the correct state for the current tool
    controls.enabled = !pointerToolRef.current;

    // Fire camera polar coordinates on every orbit move
    const onControlsChange = () => {
      const cam = Graph.camera() as THREE.PerspectiveCamera;
      const { x, y, z } = cam.position;
      const azimuth   = ((Math.atan2(x, z) * 180 / Math.PI) + 360) % 360;
      const elevation = Math.atan2(y, Math.sqrt(x * x + z * z)) * 180 / Math.PI;
      onCameraChangeRef.current?.(Math.round(azimuth), Math.round(elevation));
    };
    controls.addEventListener('change', onControlsChange);

    // ── Build Points geometry and inject into the force-graph scene ────────
    const buf = buildNodeBuffers(Graph.graphData().nodes);
    buffersRef.current = buf;
    Graph.scene().add(buf.points);

    // Start syncing simulation positions → buffer each frame
    startSyncLoop();

    // ── Custom raycasting for click + hover ───────────────────────────────
    // nodeThreeObject returns invisible objects so 3d-force-graph's built-in
    // raycasting can't detect nodes. We handle both via our own Points raycast.

    let lastHoverId: string | null = null;
    let lastHoverTime = 0;

    // Pre-allocated vectors to avoid per-call heap churn in the hit-test loop
    const _projVec = new THREE.Vector3();
    const _viewVec = new THREE.Vector3();

    // Screen-space hit test — exact match of the vertex shader formula:
    //   gl_PointSize = aSize * (500 / viewDepth)
    // Projects each node to screen pixels and checks whether the cursor lands
    // inside the rendered circle. Picks the closest match so overlapping nodes
    // resolve to the one on top visually.
    const getHitNode = (e: MouseEvent): any | null => {
      const g = graphRef.current;
      if (!g) return null;
      const container = containerRef.current!;
      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const W = rect.width;
      const H = rect.height;
      const cam = g.camera();

      let bestNode: any = null;
      let bestDist = Infinity;

      for (const node of g.graphData().nodes as any[]) {
        // View-space depth (positive = in front of camera)
        _viewVec.set(node.x ?? 0, node.y ?? 0, node.z ?? 0)
          .applyMatrix4(cam.matrixWorldInverse);
        const viewDepth = -_viewVec.z;
        if (viewDepth <= 0) continue;

        // Screen-space position in pixels
        _projVec.set(node.x ?? 0, node.y ?? 0, node.z ?? 0).project(cam);
        const sx = (_projVec.x + 1) / 2 * W;
        const sy = (1 - _projVec.y) / 2 * H;

        const distPx = Math.sqrt((mouseX - sx) ** 2 + (mouseY - sy) ** 2);
        // Pixel radius from shader: gl_PointSize = aSize * (500 / viewDepth)
        const pixelRadius = (node.__baseSize ?? 10) * 500 / viewDepth / 2;

        if (distPx <= pixelRadius && distPx < bestDist) {
          bestDist = distPx;
          bestNode = node;
        }
      }
      return bestNode;
    };

    // Grab cursor feedback in move mode
    const onMouseDown = () => {
      if (!pointerToolRef.current) containerRef.current!.style.cursor = 'grabbing';
    };
    const onMouseUp = () => {
      if (!pointerToolRef.current) containerRef.current!.style.cursor = 'grab';
    };

    // Pointer mode: throttled hover + tooltip
    const onMouseMove = (e: MouseEvent) => {
      if (!pointerToolRef.current) return;

      const now = performance.now();
      if (now - lastHoverTime < 32) return;
      lastHoverTime = now;

      const node = getHitNode(e);
      if (node) {
        containerRef.current!.style.cursor = 'pointer';
        if (node.id !== lastHoverId) {
          lastHoverId = node.id;
          if (node.kind === 'source') tooltip.textContent = `${node.title ?? ''} · ${node.doc_type ?? ''}`;
          else if (node.kind === 'concept') tooltip.textContent = node.label ?? node.id;
          else if (node.kind === 'artwork') tooltip.textContent = `Artwork ${node.artwork_id ?? ''}`;
          else tooltip.textContent = node.id;
        }
        tooltip.style.display = 'block';
        tooltip.style.left = (e.clientX + 14) + 'px';
        tooltip.style.top = (e.clientY - 4) + 'px';
      } else {
        containerRef.current!.style.cursor = 'default';
        tooltip.style.display = 'none';
        lastHoverId = null;
      }
    };

    const onClickHandler = (e: MouseEvent) => {
      if (!pointerToolRef.current) return;
      const node = getHitNode(e);
      if (node) onNodeClick?.(node as GraphNode);
    };

    containerRef.current.addEventListener('mousedown', onMouseDown);
    containerRef.current.addEventListener('mouseup', onMouseUp);
    containerRef.current.addEventListener('mousemove', onMouseMove);
    containerRef.current.addEventListener('click', onClickHandler);

    return () => {
      Graph._destructor?.();
      if (syncRafRef.current)   cancelAnimationFrame(syncRafRef.current);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      orbitActiveRef.current = false;
      if (orbitRafRef.current !== null) cancelAnimationFrame(orbitRafRef.current);
      controls.removeEventListener('change', onControlsChange);
      tooltip.remove();
      containerRef.current?.removeEventListener('mousedown', onMouseDown);
      containerRef.current?.removeEventListener('mouseup', onMouseUp);
      containerRef.current?.removeEventListener('mousemove', onMouseMove);
      containerRef.current?.removeEventListener('click', onClickHandler);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Graph data refresh (SSE-driven updates) ───────────────────────────────
  // Same optimisation as initial load: hide links during re-simulation so only
  // the Points geometry animates, then restore them once positions settle.

  useEffect(() => {
    if (!graphRef.current) return;
    const Graph = graphRef.current;
    const fgData = toForceGraphData(graphData);

    onResimulatingRef.current?.();
    Graph.linkVisibility(false);
    Graph.linkDirectionalParticles(0);
    simRunningRef.current = true;

    Graph.graphData(fgData);

    // Rebuild Points for the updated node set
    const scene = Graph.scene();
    if (buffersRef.current) scene.remove(buffersRef.current.points);
    const buf = buildNodeBuffers(fgData.nodes);
    buffersRef.current = buf;
    scene.add(buf.points);

    startSyncLoop();

    Graph.onEngineStop(() => {
      simRunningRef.current = false;
      Graph.linkVisibility(true);
      Graph.linkDirectionalParticles((link: any) => link.__kind === 'influence' ? 2 : 0);
      // Capture initial camera position once so resetView can return here
      if (!initialCamRef.current) {
        const cam = Graph.camera() as THREE.PerspectiveCamera;
        initialCamRef.current = { x: cam.position.x, y: cam.position.y, z: cam.position.z };
      }
      onSettledRef.current?.();
    });
  }, [graphData]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Heat map ──────────────────────────────────────────────────────────────

  useEffect(() => {
    const heat = heatMap ?? new Map<string, number>();
    heatRef.current = heat;
    applyHeatToBuffers(heat);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heatMap]);

  // ── Theme ──────────────────────────────────────────────────────────────────
  // In the blue theme: all nodes scale 2×, and blue-toned nodes (literary,
  // philosophy, user_upload) are recolored black so they read against the
  // bright blue background. All other themes restore the original values.

  const BLUE_NODE_COLORS   = new Set(['#93c5fd', '#bfdbfe', '#06b6d4']);
  const YELLOW_NODE_COLORS = new Set(['#fef08a', '#f59e0b']);

  useEffect(() => {
    graphRef.current?.backgroundColor(THEME_BG[graphTheme]);

    const buf = buffersRef.current;
    const g   = graphRef.current;
    if (!buf || !g) return;

    const nodes: any[] = g.graphData().nodes;
    const tmpColor = new THREE.Color();

    for (const node of nodes) {
      const idx = buf.indexMap.get(node.id);
      if (idx === undefined) continue;

      // Size — 2× in blue theme, otherwise back to the value baked at build time
      const trueSize = node.__baseSize ?? 8;
      buf.baseSizes[idx] = (graphTheme === 'blue' || graphTheme === 'light') ? trueSize * 2.3 : trueSize;
      buf.sizeAttr.array[idx] = buf.baseSizes[idx];

      // Color — remap per-theme overrides
      const trueColor: string = node.__color ?? '#ffffff';
      const effectiveColor = graphTheme === 'blue'
        ? BLUE_NODE_COLORS.has(trueColor)   ? '#ffffff'
          : YELLOW_NODE_COLORS.has(trueColor) ? '#000000'
          : trueColor
        : graphTheme === 'light' && node.kind === 'source'
        ? '#ef4444'
        : trueColor;
      tmpColor.set(effectiveColor);
      buf.baseColors[idx * 3]     = tmpColor.r;
      buf.baseColors[idx * 3 + 1] = tmpColor.g;
      buf.baseColors[idx * 3 + 2] = tmpColor.b;
      buf.colorAttr.array[idx * 3]     = tmpColor.r;
      buf.colorAttr.array[idx * 3 + 1] = tmpColor.g;
      buf.colorAttr.array[idx * 3 + 2] = tmpColor.b;
    }

    buf.sizeAttr.needsUpdate  = true;
    buf.colorAttr.needsUpdate = true;

    // Re-apply any active heat map on top of the updated base values
    if (heatRef.current.size > 0) applyHeatToBuffers(heatRef.current);

    // Link colors — per-theme overrides, then defaults
    g.linkColor((link: any) => {
      if (graphTheme === 'blue') {
        if (link.__kind === 'influence') return 'rgba(0,0,0,0.85)';
        return 'rgba(255,255,255,0.75)';
      }
      if (graphTheme === 'light') {
        if (link.__kind === 'influence') return 'rgba(251,191,36,0.8)';
        return 'rgba(37,99,235,0.55)';
      }
      if (link.__kind === 'influence') return 'rgba(251,191,36,0.8)';
      if (link.__kind === 'concept')   return 'rgba(59,130,246,0.6)';
      return 'rgba(148,163,184,0.25)';
    });
  }, [graphTheme]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {graphTheme === 'blue' && (
        <div style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,20,0.18) 3px, rgba(0,0,20,0.18) 4px)',
          pointerEvents: 'none',
        }} />
      )}
    </div>
  );
});
