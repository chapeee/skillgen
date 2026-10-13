type Point = { x: number; y: number };
type Context = CanvasRenderingContext2D;

export const PIPELINE_CYCLE = 18;
export const PIPELINE_STILL = 13.5;
const MONO = '"Geist Mono Variable", Consolas, monospace';
const WHITE = '#edf3ff';
const SILVER = '#b8c6da';
const clamp = (v: number) => Math.max(0, Math.min(1, v));
const smooth = (v: number) => { const t = clamp(v); return t * t * (3 - 2 * t); };
const random = (n: number) => { const v = Math.sin(n * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
const at = (x: number, y: number): Point => ({ x, y });

export function createPipelineGlow(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  const glow = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  glow.addColorStop(0, 'rgba(237,246,255,1)');
  glow.addColorStop(0.12, 'rgba(205,224,255,.65)');
  glow.addColorStop(0.45, 'rgba(174,206,255,.15)');
  glow.addColorStop(1, 'rgba(174,206,255,0)');
  ctx.fillStyle = glow; ctx.fillRect(0, 0, 64, 64);
  return canvas;
}

function bezier(a: Point, b: Point, t: number): Point {
  const u = 1 - t;
  const bend = (b.x - a.x) * 0.55;
  return at(u ** 3 * a.x + 3 * u * u * t * (a.x + bend) + 3 * u * t * t * (b.x - bend) + t ** 3 * b.x,
    u ** 3 * a.y + 3 * u * u * t * a.y + 3 * u * t * t * b.y + t ** 3 * b.y);
}

/** All geometry is in a 640 × 500 design space; one clock coordinates every stage. */
function painter(ctx: Context, sprite: HTMLCanvasElement, alpha: number) {
  const text = (value: string, x: number, y: number, size = 11, opacity = 1, color = WHITE) => {
    ctx.globalAlpha = alpha * opacity; ctx.fillStyle = color;
    ctx.font = `${size}px ${MONO}`; ctx.fillText(value, x, y);
  };
  const rect = (x: number, y: number, w: number, h: number, color: string, opacity = 1, radius = 0) => {
    ctx.globalAlpha = alpha * opacity; ctx.fillStyle = color;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, radius); ctx.fill();
  };
  const dot = (p: Point, r = 1.2, opacity = 1, halo = 0) => {
    ctx.globalAlpha = alpha * opacity;
    if (halo) ctx.drawImage(sprite, p.x - halo, p.y - halo, halo * 2, halo * 2);
    ctx.fillStyle = WHITE; ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
  };
  const panel = (x: number, y: number, w: number, h: number, light = 0) => {
    const fill = ctx.createLinearGradient(x, y, x + w, y + h);
    fill.addColorStop(0, '#1b202a'); fill.addColorStop(1, '#0e1219');
    ctx.globalAlpha = alpha; ctx.fillStyle = fill;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 7); ctx.fill();
    ctx.strokeStyle = `rgba(213,229,255,${0.24 + light * 0.6})`; ctx.lineWidth = 0.9; ctx.stroke();
    if (light > 0) rect(x + 1, y + 1, w - 2, h - 2, '#c5dbff', light * 0.045, 6);
  };
  const path = (a: Point, b: Point, light = 0) => {
    ctx.globalAlpha = alpha * (0.24 + light * 0.55); ctx.strokeStyle = SILVER; ctx.lineWidth = 0.9 + light * 0.4;
    const bend = (b.x - a.x) * 0.55;
    ctx.beginPath(); ctx.moveTo(a.x, a.y);
    ctx.bezierCurveTo(a.x + bend, a.y, b.x - bend, b.y, b.x, b.y); ctx.stroke();
  };
  const stream = (a: Point, b: Point, t: number, start: number, duration = 2.5) => {
    const active = smooth((t - start) / 0.4) * (1 - smooth((t - start - duration) / 0.6));
    path(a, b, active * 0.55);
    if (!active) return;
    for (let i = 0; i < 16; i++) {
      const position = ((t - start) * 0.75 + i / 16) % 1;
      if (position < 0) continue;
      const brightness = Math.sin(position * Math.PI) * active;
      for (let tail = 3; tail >= 0; tail--) {
        dot(bezier(a, b, Math.max(0, position - tail * 0.017)), tail ? 0.75 : 1.5,
          brightness * (1 - tail / 5), tail ? 0 : 8);
      }
    }
  };
  const hub = (p: Point, t: number, label: string, light: number) => {
    [20, 28].forEach((r, i) => {
      ctx.globalAlpha = alpha * (0.3 + light * 0.35); ctx.strokeStyle = SILVER; ctx.lineWidth = 0.8;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.stroke();
      const angle = t * Math.PI * 2 / 3 * (i ? -1 : 1);
      dot(at(p.x + Math.cos(angle) * r, p.y + Math.sin(angle) * r), 1.6, light, 7);
    });
    ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(Math.PI / 4);
    panel(-8, -8, 16, 16, light); ctx.restore();
    dot(p, 2, 0.9, 20 + light * 10);
    text(label, p.x - label.length * 2.7, p.y + 48, 9, 0.85);
  };
  const check = (x: number, y: number, opacity = 1) => {
    ctx.globalAlpha = alpha * opacity; ctx.strokeStyle = WHITE; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 3, y + 3); ctx.lineTo(x + 9, y - 4); ctx.stroke();
  };
  const typed = (value: string, x: number, y: number, t: number, start: number, size = 11, duration = 1) => {
    const progress = clamp((t - start) / duration);
    const fragment = value.slice(0, Math.floor(progress * value.length));
    text(fragment, x, y, size);
    if (progress > 0 && progress < 1) rect(x + ctx.measureText(fragment).width + 2, y - size + 1, 2, size, WHITE);
  };
  return { text, rect, dot, panel, path, stream, hub, check, typed };
}
type Painter = ReturnType<typeof painter>;

function routes(p: Painter, t: number) {
  p.text('REPOSITORY', 26, 35, 10, 0.8);
  p.text('DISCOVERED ROUTES', 388, 35, 10, 0.8);
  const filenames = ['app/', '  page.tsx', '  signup/page.tsx', '  profile/page.tsx', '  orders/[id]/page.tsx', 'components/', '  Button.tsx', '  Field.tsx'];
  const pages = ['/', '/signup', '/profile', '/orders/:id'];
  const starts = [1.2, 3.1, 5, 6.9];
  const hub = at(323, 245);
  starts.forEach((start, i) => {
    p.stream(at(252, 169 + i * 29), hub, t, start, 1.8);
    p.stream(hub, at(388, 125 + i * 79), t, start + 0.7, 1.8);
  });
  p.panel(25, 79, 227, 327);
  p.text('~/my-app', 42, 103, 12);
  p.rect(26, 117, 225, 1, SILVER, 0.2);
  filenames.forEach((name, i) => {
    const start = starts[i - 1];
    const scanning = start !== undefined ? smooth((t - start) / 0.3) * (1 - smooth((t - start - 1.6) / 0.4)) : 0;
    p.rect(33, 125 + i * 29, 210, 25, '#d2e4ff', scanning * 0.1, 3);
    p.text(name, 42, 142 + i * 29, 10.7, i < 5 ? 0.95 : 0.46);
    if (i > 0 && i < 5 && t > start + 1.6) p.check(228, 139 + i * 29);
  });
  p.text('conventions · AST · graph', 39, 387, 9.3, 0.65);
  pages.forEach((name, i) => {
    const y = 91 + i * 79;
    const progress = smooth((t - starts[i] - 1.4) / 0.6);
    p.panel(388, y, 227, 65, progress * 0.6);
    p.text(String(i + 1).padStart(2, '0'), 400, y + 23, 9, 0.55);
    p.typed(name, 425, y + 25, t, starts[i] + 1.4, 14, 0.8);
    p.text(progress ? 'page entry resolved' : 'awaiting discovery', 402, y + 48, 10, progress ? 0.8 : 0.42);
    if (progress === 1) p.check(592, y + 21);
  });
  p.hub(hub, t, 'RESOLVE', t > 1 && t < 10 ? 1 : 0.35);
  p.text('Source files become addressable pages.', 26, 447, 11, 0.85);
  return t < 1.2 ? 'Indexing the repository' : t < 10 ? 'Resolving page entry points' : '04 routes discovered';
}

const SLICE_NODES = [
  { x: 86, y: 248, name: 'profile/page.tsx', kind: 'PAGE', hop: 0 },
  { x: 244, y: 174, name: 'ProfileForm.tsx', kind: 'COMPONENT', hop: 1 },
  { x: 244, y: 325, name: 'useProfile.ts', kind: 'HOOK', hop: 1 },
  { x: 397, y: 116, name: 'Field.tsx', kind: 'COMPONENT', hop: 2 },
  { x: 397, y: 248, name: 'schema.ts', kind: 'VALIDATION', hop: 2 },
  { x: 397, y: 373, name: 'api.ts', kind: 'CLIENT', hop: 2 },
  { x: 554, y: 174, name: 'Input.tsx', kind: 'PRIMITIVE', hop: 3 },
  { x: 554, y: 325, name: 'types.ts', kind: 'TYPES', hop: 3 },
];
const SLICE_EDGES = [[0, 1], [0, 2], [1, 3], [1, 4], [2, 4], [2, 5], [3, 6], [4, 7], [5, 7]];

function slice(p: Painter, t: number) {
  [86, 244, 397, 554].forEach((x, i) => {
    p.text(i ? `HOP ${i}` : 'THIS PAGE', x - 30, 35, 10, 0.85);
    p.rect(x, 52, 1, 350, SILVER, 0.09);
  });
  const excluded = 1 - smooth((t - 4) / 2) * 0.6;
  p.path(at(86, 96), at(244, 75));
  p.path(at(86, 248), at(86, 96));
  p.text('settings/page.tsx', 28, 84, 10, excluded * 0.55);
  p.text('sibling excluded', 28, 101, 8.5, excluded * 0.55);
  p.text('billing/page.tsx', 28, 370, 10, excluded * 0.55);
  p.text('sibling excluded', 28, 387, 8.5, excluded * 0.55);
  SLICE_EDGES.forEach(([a, b]) => {
    const source = SLICE_NODES[a]; const target = SLICE_NODES[b];
    p.stream(at(source.x + 61, source.y), at(target.x - 61, target.y), t, target.hop * 2 - 0.5, 2.4);
  });
  SLICE_NODES.forEach((node) => {
    const strength = smooth((t - node.hop * 2) / 1.1);
    p.panel(node.x - 61, node.y - 26, 122, 52, strength * 0.8);
    p.dot(at(node.x - 48, node.y - 11), 2, 0.3 + strength * 0.7, strength * 10);
    p.text(node.kind, node.x - 40, node.y - 8, 7.5, 0.7);
    p.text(node.name, node.x - 52, node.y + 13, 9.4, 0.65 + strength * 0.35);
  });
  const count = SLICE_NODES.filter((n) => t >= n.hop * 2 + 1.1).length;
  p.panel(25, 427, 590, 32, 0.2);
  p.text(`${String(count).padStart(2, '0')} files in this example`, 39, 448, 10.5);
  p.text('LIMIT 40 FILES / ~60K TOKENS', 377, 448, 10, 0.7);
  return t < 2 ? 'Starting at the page component' : t < 8 ? 'Following imports, three hops deep' : 'Page context isolated · siblings excluded';
}

const CODE = [
  'const profile = {', '  name: {', '    label: "Full name",', '    required: true', '  },',
  '  plan: ["free", "pro"],', '  seats: { min: 1 },', '  company: {', '    when: plan === "pro"', '  },',
  '  save: {', '    dialog: "Confirm"', '  }', '};',
];
const FACTS = [
  { name: 'name', value: 'required: true', row: 3 },
  { name: 'plan', value: 'options: free | pro', row: 5 },
  { name: 'seats', value: 'minimum: 1', row: 6 },
  { name: 'company', value: 'when: plan = pro', row: 8 },
  { name: 'save', value: 'dialog: Confirm', row: 11 },
];

function readCode(p: Painter, t: number) {
  p.text('READ-ONLY SOURCE', 26, 35, 10, 0.8);
  p.text('STRUCTURED UNDERSTANDING', 402, 35, 10, 0.8);
  const hub = at(356, 247);
  FACTS.forEach((fact, i) => {
    p.stream(at(298, 144 + fact.row * 17.5), hub, t, 1 + i * 1.8, 1.7);
    p.stream(hub, at(402, 119 + i * 65), t, 1.7 + i * 1.8, 1.7);
  });
  p.panel(25, 76, 273, 351);
  p.text('profile.schema.ts', 40, 102, 12);
  p.text('READ', 251, 102, 9, 0.6);
  p.rect(26, 115, 271, 1, SILVER, 0.18);
  CODE.forEach((value, row) => {
    const index = FACTS.findIndex((f) => f.row === row);
    const focus = index < 0 ? 0 : smooth((t - 1 - index * 1.8) / 0.3) * (1 - smooth((t - 2.6 - index * 1.8) / 0.4));
    p.rect(32, 132 + row * 17.5, 258, 17, '#c6ddff', focus * 0.13, 2);
    p.text(String(row + 1).padStart(2, '0'), 36, 144 + row * 17.5, 8, 0.45);
    p.text(value, 58, 144 + row * 17.5, 10.2, 0.9, value.includes(':') ? '#e3edff' : SILVER);
  });
  p.text('Read · Grep · Glob', 41, 408, 10, 0.7);
  FACTS.forEach((fact, i) => {
    const start = 2.1 + i * 1.8;
    const progress = smooth((t - start) / 0.7);
    const y = 88 + i * 65;
    p.panel(402, y, 213, 54, progress * 0.6);
    p.text(fact.name, 416, y + 19, 11.5, 0.7 + progress * 0.3);
    p.typed(fact.value, 416, y + 39, t, start, 10.7, 0.9);
    if (progress === 1) p.check(593, y + 17);
  });
  p.hub(hub, t, 'INFER', t > 1 && t < 11 ? 1 : 0.35);
  p.text('Code becomes fields, rules and hidden steps.', 26, 450, 11, 0.85);
  return t < 1 ? 'Opening the page slice' : t < 11 ? 'Reading meaning from source' : 'Analysis complete · JSON schema satisfied';
}

function weigh(p: Painter, t: number) {
  p.text('INDEPENDENT EVIDENCE', 26, 35, 10, 0.8);
  p.text('ONE PAGE MODEL', 379, 35, 10, 0.8);
  const merge = at(286, 204);
  const sources = [
    { y: 83, title: 'STATED IN CODE', value: 'email.required', score: '0.85', start: 1.2 },
    { y: 205, title: 'SEEN ON PAGE', value: 'email.required', score: '0.90', start: 3.2 },
    { y: 327, title: 'DEDUCED', value: 'phone.required?', score: '0.60', start: 6.6 },
  ];
  sources.forEach((source, i) => {
    const active = smooth((t - source.start) / 0.6);
    const end = i === 2 ? at(379, 352) : merge;
    p.stream(at(218, source.y + 36), end, t, source.start, 2.7);
    p.panel(25, source.y, 193, 78, active * 0.65);
    p.text(source.title, 39, source.y + 20, 9, 0.75);
    p.text(source.value, 39, source.y + 44, 11.5);
    p.rect(39, source.y + 59, 123, 3, SILVER, 0.16, 1);
    p.rect(39, source.y + 59, 123 * Number(source.score) * active, 3, '#d5e7ff', 0.9, 1);
    p.text(source.score, 173, source.y + 65, 10.5);
  });
  p.stream(merge, at(379, 153), t, 4.5, 3.1);
  p.hub(merge, t, 'COMBINE', t > 1 && t < 8 ? 1 : 0.35);
  const combined = smooth((t - 4.8) / 1.3);
  p.panel(379, 83, 236, 179, combined * 0.8);
  p.text('SUPPORTED FACT', 395, 106, 10, 0.85);
  p.text('email.required', 395, 133, 13);
  p.text(`${(98.5 * combined).toFixed(1)}%`, 395, 177, 30);
  if (combined === 1) p.check(591, 103);
  p.rect(395, 191, 202, 4, SILVER, 0.2, 2);
  p.rect(395, 191, 202 * 0.985 * combined, 4, '#d5e7ff', 1, 2);
  p.text('1 − (1 − .85)(1 − .90)', 395, 220, 10.3, 0.85);
  p.typed('required: true', 395, 244, t, 6, 11, 0.8);

  const uncertain = smooth((t - 7.2) / 0.7);
  p.panel(379, 307, 236, 115, uncertain * 0.5);
  p.text('?  NEEDS YOUR ANSWER', 395, 330, 10.5, 0.85);
  p.typed('Is phone required?', 395, 357, t, 7.3, 12, 1);
  p.text('0.60 < 0.70 threshold', 395, 385, 10.5, 0.8);
  p.text('Ask before instructing.', 395, 406, 10, 0.65);
  p.text('Agreement adds confidence. Uncertainty becomes a question.', 26, 454, 10.5, 0.85);
  return t < 4.5 ? 'Gathering independent evidence' : t < 8.5 ? 'Combining confidence · checking the threshold' : 'Supported facts retained · uncertainty surfaced';
}

const SCENES = [routes, slice, readCode, weigh];

export function drawPipelineScene(ctx: Context, sprite: HTMLCanvasElement, width: number, height: number, elapsed: number, step: number) {
  ctx.globalAlpha = 1; ctx.fillStyle = '#090b10'; ctx.fillRect(0, 0, width, height);
  ctx.save();
  const scale = Math.min(width / 640, height / 500);
  ctx.translate((width - 640 * scale) / 2, (height - 500 * scale) / 2); ctx.scale(scale, scale);
  const t = elapsed % PIPELINE_CYCLE;
  const angle = t / PIPELINE_CYCLE * Math.PI * 2;
  const fade = smooth(t / 0.65) * (1 - smooth((t - 16) / 2));
  const ambient = painter(ctx, sprite, 1);
  // Deterministic, periodic dust gives every stage the same living optical field.
  for (let i = 0; i < 180; i++) {
    const x = 20 + random(i + 13) * 600 + Math.cos(angle + i) * 3;
    const y = 60 + random(i + 811) * 365 + Math.sin(angle + i) * 3;
    ambient.dot(at(x, y), 0.45 + random(i + 60) * 0.4, 0.12 + random(i + 90) * 0.18);
  }
  const p = painter(ctx, sprite, fade);
  const status = SCENES[step](p, t);
  p.rect(25, 469, 590, 1, SILVER, 0.2);
  p.dot(at(29, 485), 2, 0.9, 8);
  p.text(status, 41, 489, 10, 0.85);
  // The completed diagram dissolves into motes before the same dust field returns.
  if (t > 16) {
    const progress = smooth((t - 16) / 2);
    for (let i = 0; i < 160; i++) {
      const x = 25 + random(i + 22) * 590;
      const y = 80 + random(i + 323) * 335;
      ambient.dot(at(x - progress * (15 + random(i + 99) * 50), y - progress * 20), 0.8,
        Math.sin(progress * Math.PI) * 0.7, i % 18 === 0 ? 8 : 0);
    }
  }
  ctx.restore();
}
