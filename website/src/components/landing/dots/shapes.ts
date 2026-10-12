// Point clouds for the pipeline story. Every shape is a list of points in a
// -1..1 box; `accent` marks the points drawn in galaxy blue, `group` lets a
// shape animate a subset (the scanned line, the field being filled).

export type DotPoint = {
  x: number;
  y: number;
  z: number;
  accent: number;
  alpha: number;
  group: number;
};

type Random = () => number;

export function makeRandom(seed: number): Random {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function point(x: number, y: number, z = 0, accent = 0, alpha = 1, group = 0): DotPoint {
  return { x, y, z, accent, alpha, group };
}

function line(
  out: DotPoint[],
  ax: number,
  ay: number,
  bx: number,
  by: number,
  step: number,
  options: Partial<DotPoint> = {},
): void {
  const length = Math.hypot(bx - ax, by - ay);
  const count = Math.max(2, Math.round(length / step));
  for (let index = 0; index <= count; index++) {
    const t = index / count;
    out.push({ ...point(ax + (bx - ax) * t, ay + (by - ay) * t), ...options });
  }
}

function disc(out: DotPoint[], cx: number, cy: number, radius: number, count: number, random: Random, options: Partial<DotPoint> = {}): void {
  for (let index = 0; index < count; index++) {
    const angle = random() * Math.PI * 2;
    const r = Math.sqrt(random()) * radius;
    out.push({ ...point(cx + Math.cos(angle) * r, cy + Math.sin(angle) * r, (random() - 0.5) * radius), ...options });
  }
}

/** 01 Find routes: an app root branching into routes and their pages. */
function routeTree(random: Random): DotPoint[] {
  const out: DotPoint[] = [];
  disc(out, 0, -0.72, 0.07, 40, random, { accent: 1 });
  const routes = [-0.78, -0.47, -0.16, 0.16, 0.47, 0.78];
  routes.forEach((x, index) => {
    line(out, 0, -0.64, x, -0.12, 0.028, { alpha: 0.55 });
    disc(out, x, -0.06, 0.055, 26, random, { accent: index === 2 ? 1 : 0 });
    const leaves = index % 2 === 0 ? 2 : 3;
    for (let leaf = 0; leaf < leaves; leaf++) {
      const lx = x + (leaf - (leaves - 1) / 2) * 0.11;
      line(out, x, 0.0, lx, 0.42, 0.034, { alpha: 0.35 });
      disc(out, lx, 0.47, 0.03, 10, random, { alpha: 0.8 });
    }
  });
  return out;
}

/** 02 Slice: a code graph in clusters; the page's own slice glows blue. */
function codeGraph(random: Random): DotPoint[] {
  const out: DotPoint[] = [];
  const nodes: { x: number; y: number; z: number; isSlice: boolean }[] = [];
  const clusters = [
    { x: -0.5, y: -0.35, isSlice: false },
    { x: 0.45, y: -0.42, isSlice: false },
    { x: -0.55, y: 0.45, isSlice: false },
    { x: 0.5, y: 0.42, isSlice: false },
    { x: 0.0, y: 0.02, isSlice: true },
  ];
  clusters.forEach((cluster) => {
    const count = cluster.isSlice ? 9 : 7;
    for (let index = 0; index < count; index++) {
      const angle = (index / count) * Math.PI * 2 + random();
      const radius = 0.1 + random() * 0.17;
      nodes.push({
        x: cluster.x + Math.cos(angle) * radius,
        y: cluster.y + Math.sin(angle) * radius * 0.85,
        z: (random() - 0.5) * 0.6,
        isSlice: cluster.isSlice,
      });
    }
  });
  nodes.forEach((node) => disc(out, node.x, node.y, 0.022, 7, random, { accent: node.isSlice ? 1 : 0, z: node.z }));
  // Edges: inside clusters, plus a few bridges into the slice.
  for (let index = 0; index < nodes.length; index++) {
    const a = nodes[index];
    const b = nodes[(index + 3) % nodes.length];
    const isSliceEdge = a.isSlice && b.isSlice;
    const isBridge = a.isSlice !== b.isSlice;
    if (Math.hypot(a.x - b.x, a.y - b.y) > 0.75 && !isBridge) continue;
    line(out, a.x, a.y, b.x, b.y, 0.05, {
      accent: isSliceEdge ? 1 : 0,
      alpha: isSliceEdge ? 0.8 : isBridge ? 0.35 : 0.3,
    });
  }
  return out;
}

/** 03 Analyse: a page of code being read, line by line. */
function documentPage(random: Random): DotPoint[] {
  const out: DotPoint[] = [];
  const rows = 15;
  for (let row = 0; row < rows; row++) {
    const y = -0.72 + row * 0.103;
    const indent = [0, 0.08, 0.16, 0.08, 0.16, 0.24][Math.floor(random() * 6)];
    const length = 0.45 + random() * 0.9;
    const start = -0.72 + indent;
    line(out, start, y, Math.min(0.8, start + length), y, 0.026, { group: row + 1 });
  }
  // The answer schema, at the right edge: what the reading fills in.
  for (let row = 0; row < 6; row++) {
    const y = -0.5 + row * 0.2;
    line(out, 0.88, y, 0.98, y, 0.03, { accent: 1, alpha: 0.7 });
  }
  return out;
}

/** 04 Merge: facts as bars of confidence; only those over 0.7 go in. */
function confidenceBars(random: Random): DotPoint[] {
  const out: DotPoint[] = [];
  const bars = 13;
  const threshold = 0.7;
  for (let index = 0; index < bars; index++) {
    const confidence = [0.985, 0.85, 0.6, 0.9, 1, 0.5, 0.85, 0.96, 0.6, 1, 0.9, 0.55, 0.985][index];
    const x = -0.82 + index * (1.64 / (bars - 1));
    const height = confidence * 1.35;
    const isIn = confidence >= threshold;
    for (let y = 0; y < height; y += 0.045) {
      for (let column = 0; column < 2; column++) {
        out.push(point(x + column * 0.035 - 0.017, 0.68 - y, (random() - 0.5) * 0.1, isIn ? 1 : 0, isIn ? 1 : 0.32));
      }
    }
  }
  line(out, -0.92, 0.68 - threshold * 1.35, 0.92, 0.68 - threshold * 1.35, 0.03, { alpha: 0.75 });
  line(out, -0.92, 0.7, 0.92, 0.7, 0.03, { alpha: 0.35 });
  return out;
}

/** 05 Generate: the skill's form, its fields filling one after another. */
function formSkill(): DotPoint[] {
  const out: DotPoint[] = [];
  const fields = [
    [-0.8, -0.7, 0.75],
    [0.05, -0.7, 0.75],
    [-0.8, -0.38, 1.6],
    [-0.8, -0.06, 0.75],
    [0.05, -0.06, 0.75],
    [-0.8, 0.26, 1.6],
  ];
  fields.forEach(([x, y, width], index) => {
    const group = index + 1;
    line(out, x, y - 0.11, x + 0.22, y - 0.11, 0.035, { alpha: 0.55, group });
    line(out, x, y, x + width, y, 0.032, { group });
    line(out, x, y + 0.13, x + width, y + 0.13, 0.032, { group });
    line(out, x, y, x, y + 0.13, 0.032, { group });
    line(out, x + width, y, x + width, y + 0.13, 0.032, { group });
    line(out, x + 0.05, y + 0.065, x + width * 0.55, y + 0.065, 0.03, { group: group + 10 });
  });
  // The submit button, solid.
  for (let row = 0; row < 4; row++) {
    line(out, 0.38, 0.55 + row * 0.035, 0.8, 0.55 + row * 0.035, 0.032, { alpha: 0.9, group: 20 });
  }
  return out;
}

export const SHAPE_BUILDERS: ((random: Random) => DotPoint[])[] = [
  routeTree,
  codeGraph,
  documentPage,
  confidenceBars,
  () => formSkill(),
];

/** Resamples a shape to exactly `count` points, so any two shapes can morph. */
export function fitPoints(points: DotPoint[], count: number, random: Random): DotPoint[] {
  const result: DotPoint[] = [];
  for (let index = 0; index < count; index++) {
    if (index < points.length && points.length <= count) {
      result.push(points[index]);
    } else {
      const source = points[Math.floor(random() * points.length)];
      // Duplicates sit almost on their source, faint, so the shape keeps its weight.
      result.push({
        ...source,
        x: source.x + (random() - 0.5) * 0.012,
        y: source.y + (random() - 0.5) * 0.012,
        alpha: source.alpha * (points.length > count ? 1 : 0.4),
      });
    }
  }
  // Shuffle so morphs scatter organically instead of sliding in lines.
  for (let index = result.length - 1; index > 0; index--) {
    const swap = Math.floor(random() * (index + 1));
    [result[index], result[swap]] = [result[swap], result[index]];
  }
  return result;
}
