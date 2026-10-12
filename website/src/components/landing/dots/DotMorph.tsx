import React, { useEffect, useRef } from 'react';
import { DotPoint, SHAPE_BUILDERS, fitPoints, makeRandom } from './shapes';

type Props = {
  /** Which shape to show; changing it morphs the cloud. */
  shape: number;
  className?: string;
  label: string;
};

const MORPH_SECONDS = 1.35;
const MAX_STAGGER = 0.45;
const WHITE: [number, number, number] = [30, 34, 48];
const BLUE: [number, number, number] = [47, 70, 242];

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/** Per-shape life: the line being read, the field being filled. */
function applyEffect(shape: number, target: DotPoint, time: number): { accent: number; alpha: number } {
  if (shape === 2 && target.group > 0) {
    const reading = (Math.floor(time * 2.4) % 17) + 1;
    if (target.group === reading) return { accent: 1, alpha: 1 };
    if (target.group < reading) return { accent: 0.25, alpha: 0.85 };
    return { accent: 0, alpha: 0.45 };
  }
  if (shape === 4 && target.group > 0) {
    const cycle = time % 6.4;
    const filled = Math.floor(cycle / 0.75);
    if (target.group > 10 && target.group < 20) {
      const field = target.group - 10;
      return field <= filled ? { accent: 1, alpha: 1 } : { accent: 0, alpha: 0 };
    }
    if (target.group === filled + 1 && target.group < 20) return { accent: 1, alpha: 1 };
    if (target.group === 20) return { accent: filled >= 6 ? 1 : 0, alpha: target.alpha };
  }
  return { accent: target.accent, alpha: target.alpha };
}

/**
 * A cloud of dots that morphs between the pipeline's shapes, in the hero's
 * monochrome language with galaxy blue marking what matters in each step.
 */
export default function DotMorph({ shape, className, label }: Props): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const shapeRef = useRef(shape);
  const morphRef = useRef<{ setShape: (next: number) => void } | null>(null);

  useEffect(() => {
    shapeRef.current = shape;
    morphRef.current?.setShape(shape);
  }, [shape]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return undefined;

    const isNarrow = window.innerWidth < 768;
    const count = isNarrow ? 700 : 1100;
    const random = makeRandom(4242);
    const targets = SHAPE_BUILDERS.map((build, index) => fitPoints(build(makeRandom(100 + index)), count, random));
    const delays = Array.from({ length: count }, () => random() * MAX_STAGGER);
    const jitter = Array.from({ length: count }, () => random() * Math.PI * 2);

    let currentShape = shapeRef.current;
    let previousShape = currentShape;
    let morphStart = -10;
    const from = targets[currentShape].map((p) => ({ ...p }));
    const position = targets[currentShape].map((p) => ({ x: p.x, y: p.y, z: p.z }));

    let width = 1;
    let height = 1;
    let dpr = 1;
    let time = 0;
    let last = 0;
    let frame = 0;
    let isRunning = false;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    };

    const draw = () => {
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);
      const scale = Math.min(width, height) * 0.44;
      const cx = width / 2;
      const cy = height / 2;
      const yaw = reduced ? 0.25 : Math.sin(time * 0.22) * 0.38;
      const pitch = reduced ? 0.12 : 0.12 + Math.sin(time * 0.17) * 0.06;
      const cosY = Math.cos(yaw);
      const sinY = Math.sin(yaw);
      const cosX = Math.cos(pitch);
      const sinX = Math.sin(pitch);
      const morphT = time - morphStart;
      const target = targets[currentShape];
      const source = targets[previousShape];

      for (let index = 0; index < count; index++) {
        const local = Math.min(1, Math.max(0, (morphT - delays[index]) / MORPH_SECONDS));
        const eased = easeInOutCubic(local);
        const goal = target[index];
        const start = from[index];
        // A slight lift mid-flight gives the morph volume instead of a flat slide.
        const lift = Math.sin(eased * Math.PI) * 0.18;
        let x = start.x + (goal.x - start.x) * eased;
        let y = start.y + (goal.y - start.y) * eased;
        let z = start.z + (goal.z - start.z) * eased + lift * Math.sin(jitter[index]);
        if (!reduced && local >= 1) {
          x += Math.sin(time * 0.8 + jitter[index]) * 0.004;
          y += Math.cos(time * 0.7 + jitter[index]) * 0.004;
        }
        position[index].x = x;
        position[index].y = y;
        position[index].z = z;

        const effectNow = applyEffect(currentShape, goal, time);
        const effectBefore = applyEffect(previousShape, source[index], time);
        const accent = effectBefore.accent + (effectNow.accent - effectBefore.accent) * eased;
        const alpha = effectBefore.alpha + (effectNow.alpha - effectBefore.alpha) * eased;
        if (alpha < 0.02) continue;

        const rx = x * cosY + z * sinY;
        const rz = -x * sinY + z * cosY;
        const ry = y * cosX - rz * sinX;
        const depth = y * sinX + rz * cosX;
        const perspective = 2.6 / (2.6 + depth);
        const sx = cx + rx * scale * perspective;
        const sy = cy + ry * scale * perspective;
        const size = (accent > 0.5 ? 1.55 : 1.25) * perspective;
        const shade = 0.55 + 0.45 * Math.max(0, Math.min(1, 1 - depth * 0.6));
        const r = Math.round(WHITE[0] + (BLUE[0] - WHITE[0]) * accent);
        const g = Math.round(WHITE[1] + (BLUE[1] - WHITE[1]) * accent);
        const b = Math.round(WHITE[2] + (BLUE[2] - WHITE[2]) * accent);
        context.globalAlpha = alpha * shade * (0.55 + 0.45 * perspective);
        context.fillStyle = `rgb(${r},${g},${b})`;
        context.beginPath();
        context.arc(sx, sy, size, 0, Math.PI * 2);
        context.fill();
      }
      context.globalAlpha = 1;
    };

    const loop = (now: number) => {
      const delta = last ? Math.min((now - last) / 1000, 1 / 20) : 0;
      last = now;
      time += delta;
      draw();
      if (isRunning) frame = requestAnimationFrame(loop);
    };

    const start = () => {
      if (isRunning || reduced) return;
      isRunning = true;
      last = 0;
      frame = requestAnimationFrame(loop);
    };
    const stop = () => {
      isRunning = false;
      cancelAnimationFrame(frame);
    };

    morphRef.current = {
      setShape(next: number) {
        if (next === currentShape) return;
        for (let index = 0; index < count; index++) {
          from[index].x = position[index].x;
          from[index].y = position[index].y;
          from[index].z = position[index].z;
        }
        // Colour and opacity start from what each point showed a moment ago.
        previousShape = currentShape;
        currentShape = next;
        morphStart = time;
        if (reduced) {
          morphStart = time - MORPH_SECONDS - MAX_STAGGER;
          draw();
        }
      },
    };

    resize();
    draw();
    const resizeObserver = new ResizeObserver(() => {
      resize();
      draw();
    });
    resizeObserver.observe(canvas);
    let isInView = false;
    const intersection = new IntersectionObserver(([entry]) => {
      isInView = entry.isIntersecting;
      if (isInView && document.visibilityState === 'visible') start();
      else stop();
    });
    intersection.observe(canvas);
    const onVisibility = () => {
      if (document.visibilityState === 'visible' && isInView) start();
      else stop();
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      resizeObserver.disconnect();
      intersection.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      morphRef.current = null;
    };
  }, []);

  return <canvas ref={canvasRef} className={className} role="img" aria-label={label} />;
}
