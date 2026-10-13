import React, { useEffect, useRef, useState } from 'react';
import { createPipelineGlow, drawPipelineScene, PIPELINE_STILL } from './pipelineScenes';

const DESCRIPTIONS = [
  'A repository scan resolves four page entry points into routes: home, signup, profile and order details.',
  'Imports light up across three hops from the profile page. Eight relevant files form the page slice while sibling pages stay excluded.',
  'A read-only code scan extracts required fields, options, minimum values, conditions and confirmation dialogs into structured analysis.',
  'Code evidence at 0.85 and page evidence at 0.90 combine into 98.5 percent confidence. A deduced fact at 0.60 falls below the 0.70 threshold and becomes a question.',
];

export default function PipelineVisual({ step, className }: { step: number; className?: string }): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pausedRef = useRef(false);
  const updateRef = useRef<() => void>(() => {});
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return undefined;
    const sprite = createPipelineGlow();
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let width = 1; let height = 1; let time = 0;
    let frame = 0; let last = 0; let visible = false;
    const draw = () => drawPipelineScene(ctx, sprite, width, height, motion.matches ? PIPELINE_STILL : time, step);
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
    const intersection = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; update(); });
    const resizer = new ResizeObserver(resize);
    intersection.observe(canvas); resizer.observe(canvas); resize();
    document.addEventListener('visibilitychange', update); motion.addEventListener('change', update);
    return () => {
      stop(); intersection.disconnect(); resizer.disconnect(); updateRef.current = () => {};
      document.removeEventListener('visibilitychange', update); motion.removeEventListener('change', update);
    };
  }, [step]);

  return (
    <div className={className}>
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" role="img" aria-label={DESCRIPTIONS[step]} />
      <button type="button" className="absolute bottom-0 right-4 flex h-6 w-6 items-center justify-center rounded border border-white/20 bg-black/40 text-white/80 transition-colors hover:border-white/50 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-white motion-reduce:hidden"
        aria-label={paused ? 'Resume pipeline animation' : 'Pause pipeline animation'} aria-pressed={paused}
        onClick={() => { pausedRef.current = !pausedRef.current; setPaused(pausedRef.current); updateRef.current(); }}>
        {paused ? <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1 9 5 2 9Z" fill="currentColor" /></svg>
          : <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1V9M7 1V9" stroke="currentColor" strokeWidth="2" /></svg>}
      </button>
    </div>
  );
}
