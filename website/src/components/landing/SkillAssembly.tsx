import React, { useEffect, useRef, useState } from 'react';

type Point = { x: number; y: number };
type OutputFile = { name: string; kind: string; x: number; y: number; start: number; lines: string[] };

const WIDTH = 640;
const HEIGHT = 500;
const CYCLE = 20;
const WRITE_TIME = 3.6;
const DISSOLVE = 15.5;
const MONO = '"Geist Mono Variable", "SFMono-Regular", Consolas, monospace';
const CORE = { x: 211, y: 250 };
const FILES: OutputFile[] = [
  { name: 'SKILL.md', kind: 'MD', x: 278, y: 53, start: 2, lines: ['---', 'name: fill-profile', 'description: Update a', '  user profile safely.', '---', '## Instructions', 'Read references/fill.md'] },
  { name: 'fill.md', kind: 'MD', x: 456, y: 53, start: 3.8, lines: ['## Fill the form', '1. Read current values', '2. Validate the inputs', '3. Apply field changes', '4. Review before save', '', 'Use scripts/fill.js'] },
  { name: 'fill.js', kind: 'JS', x: 278, y: 198, start: 5, lines: ['async function fill(', '  page, values', ') {', '  await page', "    .getByLabel('Name')", '    .fill(values.name);', '}'] },
  { name: 'locators.md', kind: 'MD', x: 456, y: 198, start: 6.6, lines: ['## Form locators', '', 'name → label: Name', 'email → label: Email', 'save → role: button', '       name: Save', 'scope: profile form'] },
  { name: 'manual-steps.md', kind: 'MD', x: 278, y: 343, start: 8, lines: ['## Review & submit', '1. Open your profile', '2. Fill required fields', '3. Review all changes', '4. Select Save', '5. Confirm success', '   before continuing'] },
  { name: 'evals.json', kind: 'JSON', x: 456, y: 343, start: 9.4, lines: ['{', '  "evals": [{', '    "id": 1,', '    "prompt":', '      "Fill profile",', '    "expect": "saved"', '  }]', '}'] },
];

const clamp = (n: number) => Math.max(0, Math.min(1, n));
const smooth = (n: number) => { const t = clamp(n); return t * t * (3 - 2 * t); };
const seed = (n: number) => { const v = Math.sin(n * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const NODES: Point[] = [
  { x: 49, y: 178 }, { x: 92, y: 125 }, { x: 143, y: 159 },
  { x: 66, y: 254 }, { x: 132, y: 234 }, { x: 104, y: 318 },
  { x: 46, y: 352 }, { x: 166, y: 345 }, { x: 174, y: 286 },
];
const LINKS = [[0, 1], [0, 3], [1, 2], [2, 4], [3, 4], [3, 5], [4, 5], [4, 8], [5, 6], [5, 7], [7, 8], [2, 8]];

function curve(a: Point, b: Point, t: number): Point {
  const u = 1 - t;
  const bend = Math.max(35, (b.x - a.x) * 0.55);
  return {
    x: u ** 3 * a.x + 3 * u * u * t * (a.x + bend) + 3 * u * t * t * (b.x - bend) + t ** 3 * b.x,
    y: u ** 3 * a.y + 3 * u * u * t * a.y + 3 * u * t * t * b.y + t ** 3 * b.y,
  };
}

function makeGlow(): HTMLCanvasElement {
  const sprite = document.createElement('canvas');
  sprite.width = sprite.height = 64;
  const ctx = sprite.getContext('2d')!;
  const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, 'rgba(239,246,255,0.9)');
  gradient.addColorStop(0.12, 'rgba(213,231,255,0.55)');
  gradient.addColorStop(0.4, 'rgba(173,201,235,0.12)');
  gradient.addColorStop(1, 'rgba(173,201,235,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 64, 64);
  return sprite;
}

function drawScene(ctx: CanvasRenderingContext2D, glow: HTMLCanvasElement, width: number, height: number, time: number) {
  // Own the backdrop: this scene must remain legible even before theme CSS loads.
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#090b10';
  ctx.fillRect(0, 0, width, height);
  const scale = Math.min(width / WIDTH, height / HEIGHT);
  ctx.save();
  ctx.translate((width - WIDTH * scale) / 2, (height - HEIGHT * scale) / 2);
  ctx.scale(scale, scale);
  const t = time % CYCLE;
  const angle = t / CYCLE * Math.PI * 2;
  const formed = smooth(t / 2.2) * (1 - smooth((t - 18) / 2));
  const ink = 1 - smooth((t - DISSOLVE) / 0.85);

  const text = (value: string, x: number, y: number, size = 9, alpha = 1, color = '#d9dce2') => {
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.font = `${size}px ${MONO}`;
    ctx.fillText(value, x, y);
  };
  const dot = (x: number, y: number, radius: number, alpha: number, halo = 0) => {
    ctx.globalAlpha = alpha;
    if (halo) ctx.drawImage(glow, x - halo, y - halo, halo * 2, halo * 2);
    ctx.fillStyle = '#e6efff';
    ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill();
  };
  const line = (a: Point, b: Point, alpha: number) => {
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = '#c7d6eb'; ctx.lineWidth = 0.85;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
  };

  // A restrained luminous field gives the tiny particles depth without bloom overload.
  ctx.globalAlpha = 0.16;
  ctx.drawImage(glow, -60, 20, 460, 460);
  for (let i = 0; i < 100; i++) {
    dot(18 + seed(i + 40) * 605, 38 + seed(i + 240) * 430, 0.45,
      0.04 + 0.1 * (0.5 + 0.5 * Math.sin(angle + i)));
  }
  text('CODE INTELLIGENCE', 27, 29, 10, 0.8);
  text('AGENT SKILL / OUTPUT', 278, 29, 10, 0.8);
  line({ x: 27, y: 40 }, { x: 242, y: 40 }, 0.12);
  line({ x: 278, y: 40 }, { x: 618, y: 40 }, 0.12);

  LINKS.forEach(([a, b], index) => {
    line(NODES[a], NODES[b], 0.12 + formed * 0.2);
    const travel = (t / 3 + index * 0.27) % 1;
    dot(mix(NODES[a].x, NODES[b].x, travel), mix(NODES[a].y, NODES[b].y, travel), 0.75,
      formed * Math.sin(travel * Math.PI) * 0.7, 5);
  });
  [2, 4, 8].forEach((index) => line(NODES[index], CORE, 0.14 + formed * 0.22));

  // Seeded particles coalesce around a fixed graph, then return to the same cloud.
  for (let i = 0; i < 340; i++) {
    const node = NODES[i % NODES.length];
    const orbit = angle * (i % 2 ? 1 : -1) + seed(i + 15) * Math.PI * 2;
    const radius = 3 + seed(i + 180) * 23;
    const cloudX = 26 + seed(i + 400) * 191;
    const cloudY = 86 + seed(i + 600) * 310;
    const x = mix(cloudX, node.x + Math.cos(orbit) * radius, formed * 0.86);
    const y = mix(cloudY, node.y + Math.sin(orbit) * radius * 0.7, formed * 0.86);
    const alpha = 0.24 + seed(i + 70) * 0.58;
    if (i % 13 === 0) text(i % 2 ? '1' : '0', x, y, 7.5, alpha * 0.95);
    else dot(x, y, 0.6 + seed(i) * 0.65, alpha);
  }
  NODES.forEach((node, i) => {
    const pulse = (0.5 + 0.5 * Math.cos(angle * 4 - i * 0.7)) ** 4 * formed;
    dot(node.x, node.y, 1.8 + pulse, 0.6 + pulse * 0.4, 12 + pulse * 13);
  });

  // Draw both branches before the cards so paths never cut through file content.
  FILES.forEach((file, index) => {
    const end = { x: file.x, y: file.y + 64 };
    const bend = Math.max(35, (end.x - CORE.x) * 0.55);
    ctx.globalAlpha = 0.3;
    ctx.strokeStyle = '#aabbd0'; ctx.lineWidth = 0.9;
    ctx.beginPath(); ctx.moveTo(CORE.x, CORE.y);
    ctx.bezierCurveTo(CORE.x + bend, CORE.y, end.x - bend, end.y, end.x, end.y);
    ctx.stroke();
    for (let p = 0; p < 28; p++) {
      const departure = file.start - 1.15 + p * WRITE_TIME / 28;
      const flight = (t - departure) / 1.15;
      if (flight <= 0 || flight >= 1) continue;
      const brightness = Math.sin(Math.PI * flight) ** 0.4;
      for (let tail = 5; tail >= 0; tail--) {
        const at = curve(CORE, end, Math.max(0, flight - tail * 0.012));
        dot(at.x, at.y, tail ? 0.85 : 1.65, brightness * (1 - tail / 7), tail ? 0 : 10);
      }
      if (p % 7 === 0) {
        const at = curve(CORE, end, flight);
        text((p + index) % 2 ? '1' : '0', at.x - 2, at.y - 5, 6, brightness * 0.6);
      }
    }
  });

  const working = FILES.some((f) => t > f.start - 1.15 && t < f.start + WRITE_TIME);
  ctx.globalAlpha = 0.2 + formed * 0.25;
  ctx.strokeStyle = '#cbd9ee'; ctx.lineWidth = 0.6;
  [15, 22].forEach((radius) => {
    ctx.beginPath(); ctx.arc(CORE.x, CORE.y, radius, 0, Math.PI * 2); ctx.stroke();
  });
  ctx.save(); ctx.translate(CORE.x, CORE.y); ctx.rotate(Math.PI / 4);
  ctx.globalAlpha = 0.95; ctx.fillStyle = '#10141b'; ctx.fillRect(-7, -7, 14, 14);
  ctx.strokeStyle = '#dce7f7'; ctx.strokeRect(-7, -7, 14, 14); ctx.restore();
  dot(CORE.x, CORE.y, 1.7, 0.65, working ? 25 : 12);
  text('PAGE MODEL', 178, 289, 9, 0.75);
  text('understand → compose', 33, 415, 9.5, 0.7);

  FILES.forEach((file, index) => {
    const progress = clamp((t - file.start) / WRITE_TIME);
    const writing = progress > 0 && progress < 1;
    const completed = progress === 1;
    const flash = completed ? (1 - smooth((t - file.start - WRITE_TIME) / 0.9)) * ink : 0;
    const strength = 0.1 + (writing ? 0.42 : completed ? 0.2 : 0) * ink;
    const { x, y } = file;
    const w = 164; const h = 127;
    ctx.globalAlpha = 1;
    const surface = ctx.createLinearGradient(x, y, x + w, y + h);
    surface.addColorStop(0, '#1c2028'); surface.addColorStop(1, '#10131a');
    ctx.fillStyle = surface;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 6); ctx.fill();
    ctx.strokeStyle = `rgba(206,222,244,${0.13 + strength + flash * 0.4})`;
    ctx.lineWidth = 0.75; ctx.stroke();
    if (flash > 0) {
      ctx.globalAlpha = flash * 0.09; ctx.fillStyle = '#d5e6ff'; ctx.fill();
      ctx.globalAlpha = flash * 0.55; ctx.drawImage(glow, x - 26, y + 38, 52, 52);
    }
    line({ x: x + 1, y: y + 28 }, { x: x + w - 1, y: y + 28 }, 0.12);
    text(file.kind === 'JS' ? 'ƒ' : file.kind === 'JSON' ? '{}' : '≡', x + 10, y + 18, 11, 0.8);
    text(file.name, x + 27, y + 18, file.name.length > 12 ? 10.5 : 12, 1, '#f0f3f9');
    if (completed && ink > 0) {
      ctx.globalAlpha = ink * 0.8; ctx.strokeStyle = '#dce8f5'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x + w - 15, y + 14); ctx.lineTo(x + w - 12, y + 17);
      ctx.lineTo(x + w - 7, y + 11); ctx.stroke();
    } else dot(x + w - 12, y + 14, 1.5, writing ? 0.8 : 0.2, writing ? 6 : 0);

    // Type complete, meaningful source lines in order; pace each line by its length.
    const total = file.lines.reduce((sum, value) => sum + value.length + 4, 0);
    let budget = Math.floor(progress * total);
    file.lines.forEach((value, row) => {
      const count = Math.min(value.length, Math.max(0, budget));
      const baseline = y + 42 + row * 10.1;
      text(String(row + 1).padStart(2, '0'), x + 8, baseline, 6.5, 0.45);
      const color = value.startsWith('#') || value.includes('function') || value.includes('await') ? '#e2edff' : '#d4d9e2';
      text(value.slice(0, count), x + 23, baseline, 9.2, ink, color);
      if (writing && budget >= 0 && budget < value.length + 4) {
        ctx.globalAlpha = ink * 0.8; ctx.fillStyle = '#e3edfc';
        ctx.fillRect(x + 23 + ctx.measureText(value.slice(0, count)).width + 1, baseline - 6, 2, 7);
      }
      budget -= value.length + 4;
    });
    ctx.globalAlpha = 0.08; ctx.fillStyle = '#cbd9ec'; ctx.fillRect(x + 10, y + h - 9, w - 20, 1);
    ctx.globalAlpha = ink * 0.6; ctx.fillRect(x + 10, y + h - 9, (w - 20) * progress, 1);

    // Code breaks into ordered motes and arcs back toward its source, then fades.
    if (t > DISSOLVE) {
      for (let p = 0; p < 48; p++) {
        const delay = seed(p + index * 71) * 0.32;
        const travel = smooth((t - DISSOLVE - delay) / 3.8);
        const source = { x: x + 24 + seed(p + 91) * 110, y: y + 40 + seed(p + 172) * 63 };
        const target = NODES[p % NODES.length];
        const at = curve(source, target, travel);
        const alpha = smooth((t - DISSOLVE - delay) / 0.35) * (1 - smooth((t - 18.5) / 1.3));
        dot(at.x, at.y - Math.sin(travel * Math.PI) * (25 + index * 4), 0.55, alpha * 0.65, p % 12 === 0 ? 5 : 0);
      }
    }
  });

  const count = FILES.filter((file) => t >= file.start + WRITE_TIME).length;
  const status = t < 1.7 ? 'Understanding the page' : t < 13 ? 'Composing skill files' : t < DISSOLVE ? 'Skill ready for your agent' : 'Recomposing intelligence';
  dot(29, 483, 2, 0.65, working ? 8 : 4);
  text(status, 39, 486, 9, 0.85 * smooth(t / 0.4) * (1 - smooth((t - 19.6) / 0.4)));
  text(`${String(t >= DISSOLVE ? 0 : count).padStart(2, '0')} / 06 FILES`, 294, 486, 9, 0.75);
  ctx.restore();
}

/** A single clock keeps the network, writing, completion and dissolve in sync. */
export default function SkillAssembly({ className }: { className?: string }): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pausedRef = useRef(false);
  const updateRef = useRef<() => void>(() => {});
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return undefined;
    const glow = makeGlow();
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let width = 1; let height = 1; let time = 0;
    let frame = 0; let last = 0; let visible = false;
    const draw = () => drawScene(ctx, glow, width, height, motion.matches ? 14.5 : time);
    const stop = () => { cancelAnimationFrame(frame); frame = 0; last = 0; };
    const loop = (now: number) => {
      time += last ? Math.min((now - last) / 1000, 0.05) : 0;
      last = now; draw(); frame = requestAnimationFrame(loop);
    };
    const update = () => {
      stop(); draw();
      if (visible && !document.hidden && !motion.matches && !pausedRef.current) frame = requestAnimationFrame(loop);
    };
    updateRef.current = update;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width); height = Math.max(1, rect.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); draw();
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; update(); });
    const resizer = new ResizeObserver(resize);
    observer.observe(canvas); resizer.observe(canvas); resize();
    document.addEventListener('visibilitychange', update);
    motion.addEventListener('change', update);
    return () => {
      stop(); observer.disconnect(); resizer.disconnect(); updateRef.current = () => {};
      document.removeEventListener('visibilitychange', update); motion.removeEventListener('change', update);
    };
  }, []);

  return (
    <div className={className}>
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" role="img"
        aria-label="Code intelligence flows through a neural network and writes six Agent Skill files: SKILL.md, fill.md, fill.js, locators.md, manual-steps.md and evals.json. The completed code dissolves into particles and the sequence repeats." />
      <button type="button" className="absolute bottom-0 right-4 flex h-6 w-6 items-center justify-center rounded border border-white/10 bg-black/40 text-white/50 transition-colors hover:border-white/30 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white motion-reduce:hidden"
        aria-label={paused ? 'Resume file generation animation' : 'Pause file generation animation'} aria-pressed={paused}
        onClick={() => { pausedRef.current = !pausedRef.current; setPaused(pausedRef.current); updateRef.current(); }}>
        {paused ? <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1 9 5 2 9Z" fill="currentColor" /></svg>
          : <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1V9M7 1V9" stroke="currentColor" strokeWidth="2" /></svg>}
      </button>
    </div>
  );
}
