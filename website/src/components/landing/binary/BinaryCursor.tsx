import { useEffect } from 'react';

type Bit = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  life: number;
  size: number;
  glyph: string;
  tone: number;
};

const MAX_BITS = 280;
const SPAWN_DISTANCE = 6;
const FONT_FAMILY = '"Geist Mono Variable", "Geist Mono", ui-monospace, monospace';

/**
 * As the mouse moves, 0s and 1s spill out around it and drift outward, like
 * data answering the pointer. One fixed canvas that never takes pointer
 * events and only animates while bits are alive. Off for touch, for reduced
 * motion, and over the hero, which has a ripple of its own.
 */
export default function BinaryCursor(): null {
  useEffect(() => {
    const isFinePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!isFinePointer) return undefined;

    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.cssText =
      'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:45;mix-blend-mode:difference;';
    document.body.appendChild(canvas);
    const context = canvas.getContext('2d');
    if (!context) {
      canvas.remove();
      return undefined;
    }

    const bits: Bit[] = [];
    let width = 0;
    let height = 0;
    let dpr = 1;
    let frame = 0;
    let last = 0;
    let lastX = -1;
    let lastY = -1;
    let carry = 0;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    };
    resize();

    const isOverHero = (x: number, y: number): boolean => {
      const hero = document.getElementById('hero');
      if (!hero) return false;
      const rect = hero.getBoundingClientRect();
      return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
    };

    const spawn = (x: number, y: number, intensity: number) => {
      const angle = Math.random() * Math.PI * 2;
      const speed = 18 + Math.random() * 46 * intensity;
      const offset = 4 + Math.random() * 10;
      bits.push({
        x: x + Math.cos(angle) * offset,
        y: y + Math.sin(angle) * offset,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        age: 0,
        life: 0.7 + Math.random() * 0.7,
        size: 5 + Math.random() * 2,
        glyph: Math.random() < 0.5 ? '0' : '1',
        tone: 170 + Math.floor(Math.random() * 85),
      });
      if (bits.length > MAX_BITS) bits.shift();
    };

    const draw = (now: number) => {
      const delta = last ? Math.min((now - last) / 1000, 1 / 20) : 0;
      last = now;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);
      context.textAlign = 'center';
      context.textBaseline = 'middle';
      for (let index = bits.length - 1; index >= 0; index--) {
        const bit = bits[index];
        bit.age += delta;
        if (bit.age >= bit.life) {
          bits.splice(index, 1);
          continue;
        }
        // Bits ease out as they spread, and now and then rewrite themselves.
        bit.vx *= 0.94;
        bit.vy *= 0.94;
        bit.x += bit.vx * delta;
        bit.y += bit.vy * delta;
        if (Math.random() < 0.06) bit.glyph = bit.glyph === '0' ? '1' : '0';
        const progress = bit.age / bit.life;
        const fadeIn = Math.min(1, progress * 6);
        context.globalAlpha = 0.5 * fadeIn * (1 - progress) * (1 - progress);
        context.fillStyle = `rgb(${bit.tone},${bit.tone},${bit.tone})`;
        context.font = `700 ${bit.size}px ${FONT_FAMILY}`;
        context.fillText(bit.glyph, bit.x, bit.y);
      }
      context.globalAlpha = 1;
      frame = bits.length > 0 ? requestAnimationFrame(draw) : 0;
      if (!frame) last = 0;
    };

    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse' || reduced.matches) return;
      const { clientX: x, clientY: y } = event;
      if (lastX < 0) {
        lastX = x;
        lastY = y;
        return;
      }
      const moved = Math.hypot(x - lastX, y - lastY);
      lastX = x;
      lastY = y;
      if (isOverHero(x, y)) return;
      // Near links and buttons the data answers a little more eagerly.
      const target = event.target instanceof Element ? event.target : null;
      const isInteractive = Boolean(target?.closest('a, button, [role="tab"], input, label'));
      carry += moved * (isInteractive ? 1.5 : 1);
      let count = 0;
      while (carry >= SPAWN_DISTANCE && count < 7) {
        carry -= SPAWN_DISTANCE;
        spawn(x, y, isInteractive ? 1.3 : 1);
        count++;
      }
      if (count > 0 && !frame) frame = requestAnimationFrame(draw);
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('resize', resize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('resize', resize);
      canvas.remove();
    };
  }, []);

  return null;
}
