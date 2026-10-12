import React, { useEffect, useRef } from 'react';
import { STAR_FRAGMENT, STAR_VERTEX, WAVE_FRAGMENT, WAVE_VERTEX } from './shaders';

type Props = {
  className?: string;
};

// The hero background colour; the canvas is opaque so it composites cheaply.
const BACKGROUND = [10 / 255, 10 / 255, 12 / 255] as const;
// Tiny glyphs need real pixels on high-density screens to stay crisp.
const MAX_DPR = 2;
// A tab switch can deliver one huge frame delta; clamping it means the waves
// continue from where they paused instead of leaping ahead.
const MAX_STEP_SECONDS = 1 / 20;
const STILL_FRAME_TIME = 18;

type Grid = { data: Float32Array; count: number; columns: number };

function makeRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// About 210k very small glyphs on a wide desktop, about 20k on a phone: a
// dense, fine-grained field of 0s and 1s, like a sky full of stars.
function chooseColumns(width: number, quality: number): number {
  return Math.round(Math.min(600, Math.max(180, width / 2.2)) * quality);
}

const GLYPH_FONT =
  '800 60px "Geist Mono Variable", "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace';

/** A 128x64 atlas: "0" on the left half, "1" on the right. */
function drawGlyphAtlas(): HTMLCanvasElement {
  const atlas = document.createElement('canvas');
  atlas.width = 128;
  atlas.height = 64;
  const context = atlas.getContext('2d');
  if (context) {
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.font = GLYPH_FONT;
    context.fillText('0', 32, 35);
    context.fillText('1', 96, 35);
  }
  return atlas;
}

/** Builds the particle lattice, far rows first so painter's order gives depth. */
function buildGrid(columns: number): Grid {
  const rows = Math.round(columns * 0.62);
  const random = makeRandom(columns * 7919);
  const data = new Float32Array(columns * rows * 4);
  let offset = 0;
  for (let row = rows - 1; row >= 0; row--) {
    for (let column = 0; column < columns; column++) {
      const jitterX = (random() - 0.5) * 0.8;
      const jitterZ = (random() - 0.5) * 0.8;
      data[offset++] = ((column + 0.5 + jitterX) / columns) * 2 - 1;
      data[offset++] = Math.min(1, Math.max(0, (row + 0.5 + jitterZ) / rows));
      data[offset++] = random();
      data[offset++] = random();
    }
  }
  return { data, count: columns * rows, columns };
}

function buildStars(): Float32Array {
  const random = makeRandom(20261012);
  const sparkles = 13;
  const dust = 70;
  const data = new Float32Array((sparkles + dust) * 4);
  let offset = 0;
  for (let index = 0; index < sparkles + dust; index++) {
    const isSparkle = index < sparkles;
    data[offset++] = random() * 1.9 - 0.95;
    // Sparkles sit mostly in the upper two thirds, over the swell.
    data[offset++] = isSparkle ? random() * 1.25 - 0.35 : random() * 1.9 - 0.95;
    data[offset++] = isSparkle ? 16 + random() * 18 : 2.5 + random() * 3.5;
    data[offset++] = random();
  }
  return data;
}

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error('createShader failed');
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`shader compile failed: ${log}`);
  }
  return shader;
}

function link(gl: WebGLRenderingContext, vertex: string, fragment: string): WebGLProgram {
  const program = gl.createProgram();
  if (!program) throw new Error('createProgram failed');
  gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, vertex));
  gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fragment));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`program link failed: ${gl.getProgramInfoLog(program)}`);
  }
  return program;
}

type Mouse = { x: number; y: number; active: number };

type Scene = {
  resize(width: number, height: number, dpr: number, quality: number): void;
  draw(time: number, pointerX: number, pointerY: number, mouse: Mouse): void;
  refreshGlyphs(): void;
  dispose(): void;
};

function createWebGLScene(canvas: HTMLCanvasElement): Scene | null {
  const gl = canvas.getContext('webgl', {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: false,
    preserveDrawingBuffer: false,
    powerPreference: 'high-performance',
  });
  if (!gl) return null;

  let waveProgram: WebGLProgram;
  let starProgram: WebGLProgram;
  try {
    waveProgram = link(gl, WAVE_VERTEX, WAVE_FRAGMENT);
    starProgram = link(gl, STAR_VERTEX, STAR_FRAGMENT);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[hero] WebGL unavailable, using the 2D fallback.', error);
    return null;
  }

  const wave = {
    position: gl.getAttribLocation(waveProgram, 'aPos'),
    time: gl.getUniformLocation(waveProgram, 'uTime'),
    aspect: gl.getUniformLocation(waveProgram, 'uAspect'),
    dpr: gl.getUniformLocation(waveProgram, 'uDpr'),
    size: gl.getUniformLocation(waveProgram, 'uSize'),
    pointer: gl.getUniformLocation(waveProgram, 'uPointer'),
    mouse: gl.getUniformLocation(waveProgram, 'uMouse'),
    mouseActive: gl.getUniformLocation(waveProgram, 'uMouseActive'),
    glyphs: gl.getUniformLocation(waveProgram, 'uGlyphs'),
  };
  const star = {
    position: gl.getAttribLocation(starProgram, 'aStar'),
    time: gl.getUniformLocation(starProgram, 'uTime'),
    dpr: gl.getUniformLocation(starProgram, 'uDpr'),
  };

  const glyphTexture = gl.createTexture();
  const uploadGlyphs = () => {
    gl.bindTexture(gl.TEXTURE_2D, glyphTexture);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, drawGlyphAtlas());
    // Mipmaps keep far, tiny glyphs soft instead of shimmering.
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  };
  uploadGlyphs();

  const waveBuffer = gl.createBuffer();
  const starBuffer = gl.createBuffer();
  const stars = buildStars();
  gl.bindBuffer(gl.ARRAY_BUFFER, starBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, stars, gl.STATIC_DRAW);

  let grid: Grid | null = null;
  let dpr = 1;
  let aspect = 1;
  let pointSize = 1.6;

  gl.disable(gl.DEPTH_TEST);
  gl.enable(gl.BLEND);
  gl.clearColor(BACKGROUND[0], BACKGROUND[1], BACKGROUND[2], 1);

  return {
    resize(width, height, nextDpr, quality) {
      dpr = nextDpr;
      aspect = width / Math.max(1, height);
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
      // Narrow screens get fewer, slightly larger dots: same look, less work.
      pointSize = width < 640 ? 2.5 : 2.2;
      const columns = chooseColumns(width, quality);
      if (!grid || Math.abs(grid.columns - columns) / grid.columns > 0.08) {
        grid = buildGrid(columns);
        gl.bindBuffer(gl.ARRAY_BUFFER, waveBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, grid.data, gl.STATIC_DRAW);
      }
    },
    draw(time, pointerX, pointerY, mouse) {
      if (!grid) return;
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.useProgram(waveProgram);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, glyphTexture);
      gl.uniform1i(wave.glyphs, 0);
      gl.uniform2f(wave.mouse, mouse.x, mouse.y);
      gl.uniform1f(wave.mouseActive, mouse.active);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.bindBuffer(gl.ARRAY_BUFFER, waveBuffer);
      gl.enableVertexAttribArray(wave.position);
      gl.vertexAttribPointer(wave.position, 4, gl.FLOAT, false, 0, 0);
      gl.uniform1f(wave.time, time);
      gl.uniform1f(wave.aspect, aspect);
      gl.uniform1f(wave.dpr, dpr);
      gl.uniform1f(wave.size, pointSize);
      gl.uniform2f(wave.pointer, pointerX, pointerY);
      gl.drawArrays(gl.POINTS, 0, grid.count);
      gl.disableVertexAttribArray(wave.position);

      gl.useProgram(starProgram);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      gl.bindBuffer(gl.ARRAY_BUFFER, starBuffer);
      gl.enableVertexAttribArray(star.position);
      gl.vertexAttribPointer(star.position, 4, gl.FLOAT, false, 0, 0);
      gl.uniform1f(star.time, time);
      gl.uniform1f(star.dpr, dpr);
      gl.drawArrays(gl.POINTS, 0, stars.length / 4);
      gl.disableVertexAttribArray(star.position);
    },
    refreshGlyphs: uploadGlyphs,
    dispose() {
      gl.deleteTexture(glyphTexture);
      gl.deleteBuffer(waveBuffer);
      gl.deleteBuffer(starBuffer);
      gl.deleteProgram(waveProgram);
      gl.deleteProgram(starProgram);
    },
  };
}

/** A lighter CPU version of the same surface for browsers without WebGL. */
function createCanvasScene(canvas: HTMLCanvasElement): Scene | null {
  const context = canvas.getContext('2d', { alpha: false });
  if (!context) return null;
  let width = 1;
  let height = 1;
  let dpr = 1;
  let grid: Grid | null = null;

  return {
    resize(nextWidth, nextHeight, nextDpr) {
      width = nextWidth;
      height = nextHeight;
      dpr = Math.min(nextDpr, 1.5);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      grid = buildGrid(Math.round(Math.min(90, Math.max(50, width / 16))));
      context.textAlign = 'center';
      context.textBaseline = 'middle';
    },
    refreshGlyphs() {},
    draw(time, pointerX, _pointerY, mouse) {
      if (!grid) return;
      const background = `rgb(${BACKGROUND.map((value) => Math.round(value * 255)).join(',')})`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.fillStyle = background;
      context.fillRect(0, 0, width, height);
      const aspect = width / height;
      const pitch = 0.42;
      const cos = Math.cos(pitch);
      const sin = Math.sin(pitch);
      const data = grid.data;
      for (let index = 0; index < grid.count; index++) {
        const base = index * 4;
        const depth = data[base + 1];
        const seed = data[base + 2];
        const z = 1.6 + 28.4 * Math.pow(depth, 1.3);
        const x = data[base] * (0.9 + z * 0.62 * Math.max(aspect, 0.85));
        const h =
          Math.sin(x * 0.3 + z * 0.17 + time * 0.4 + 1.7 * Math.sin(z * 0.11 - time * 0.15)) * 0.55 +
          Math.sin(z * 0.5 - time * 0.58 + 0.8 * Math.sin(x * 0.21 + time * 0.19)) * 0.3 +
          Math.sin(x * 0.13 - time * 0.21) * Math.cos(z * 0.19 + time * 0.13) * 0.7;
        const cy = h * 1.1 - 3.1;
        const viewY = cy * cos + z * sin;
        const viewZ = z * cos - cy * sin;
        if (viewZ < 0.2) continue;
        const sx = (((x - pointerX * 0.55) * 1.9) / aspect / viewZ) * 0.5 + 0.5;
        const sy = 0.5 - ((viewY * 1.9) / viewZ) * 0.5;
        if (sx < -0.02 || sx > 1.02 || sy < -0.02 || sy > 1.02) continue;
        const crest = Math.min(1, Math.max(0, (h + 1.25) / 2.8));
        const fade = Math.min(1, depth * 10) * (1 - Math.max(0, (depth - 0.62) / 0.38));
        const tone = Math.round(18 + 237 * Math.pow(crest, 1.4));
        const dx = (sx - (mouse.x + 1) / 2) * aspect;
        const dy = sy - (1 - mouse.y) / 2;
        const near = Math.exp(-(dx * dx + dy * dy) * 40) * mouse.active;
        const size = Math.max(4, Math.min(16, 3.6 * (0.5 + seed) * (6 / viewZ))) * (1 + near * 0.4);
        const glyph = Math.floor(seed * 7 + time * (0.15 + near * 8) + data[base + 3] * 13) % 2;
        context.globalAlpha = Math.min(1, fade * (0.35 + 0.6 * data[base + 3]) + near * 0.4);
        context.fillStyle = `rgb(${tone},${tone},${tone})`;
        context.font = `600 ${Math.round(size)}px ui-monospace, monospace`;
        context.fillText(glyph ? '1' : '0', sx * width, sy * height);
      }
      context.globalAlpha = 1;
    },
    dispose() {},
  };
}

/**
 * The hero's monochrome binary swell. The 0s and 1s themselves form the
 * waves: every glyph sits on a moving surface and takes its size, brightness
 * and opacity from depth, crest height and a drifting key light. Around the
 * cursor the glyphs flip fast and ripple outward.
 */
export default function ParticleField({ className }: Props): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let scene = createWebGLScene(canvas) ?? createCanvasScene(canvas);
    if (!scene) return undefined;

    let frame = 0;
    let lastTimestamp = 0;
    // Density adapts once: if early frames are slow, the field rebuilds sparser.
    let quality = 1;
    let sampledFrames = 0;
    let sampledTime = 0;
    let elapsed = STILL_FRAME_TIME;
    let isVisible = true;
    let isPageVisible = document.visibilityState === 'visible';
    let isRunning = false;
    let cssWidth = 1;
    let cssHeight = 1;
    const pointer = { x: 0, y: 0, targetX: 0, targetY: 0 };
    const mouse: Mouse = { x: 0, y: 0, active: 0 };
    const mouseTarget = { x: 0, y: 0, isInside: false };

    const render = (timestamp: number) => {
      frame = 0;
      const delta = lastTimestamp ? Math.min((timestamp - lastTimestamp) / 1000, MAX_STEP_SECONDS) : 0;
      lastTimestamp = timestamp;
      elapsed += delta;
      if (delta > 0 && sampledFrames < 120 && document.visibilityState === 'visible') {
        sampledFrames++;
        sampledTime += delta;
        if (sampledFrames === 120 && sampledTime / sampledFrames > 1 / 45 && quality > 0.5) {
          quality = 0.62;
          scene?.resize(cssWidth, cssHeight, Math.min(window.devicePixelRatio || 1, MAX_DPR), quality);
        }
      }
      // Critically damped easing keeps the parallax cinematic, never twitchy.
      pointer.x += (pointer.targetX - pointer.x) * 0.035;
      pointer.y += (pointer.targetY - pointer.y) * 0.035;
      // The ripple follows the cursor closely and fades in and out gently.
      mouse.x += (mouseTarget.x - mouse.x) * 0.22;
      mouse.y += (mouseTarget.y - mouse.y) * 0.22;
      mouse.active += ((mouseTarget.isInside ? 1 : 0) - mouse.active) * 0.06;
      scene?.draw(elapsed, pointer.x, pointer.y, mouse);
      if (isRunning) frame = requestAnimationFrame(render);
    };

    const drawStill = () => scene?.draw(elapsed, 0, 0, { x: 0, y: 0, active: 0 });

    const updateLoop = () => {
      const shouldRun = isVisible && isPageVisible && !reducedMotion.matches;
      if (shouldRun && !isRunning) {
        isRunning = true;
        lastTimestamp = 0;
        frame = requestAnimationFrame(render);
      } else if (!shouldRun && isRunning) {
        isRunning = false;
        cancelAnimationFrame(frame);
        frame = 0;
      }
      if (reducedMotion.matches) drawStill();
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      cssWidth = Math.max(1, rect.width);
      cssHeight = Math.max(1, rect.height);
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      scene?.resize(cssWidth, cssHeight, dpr, quality);
      if (!isRunning) drawStill();
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    resize();

    const intersectionObserver = new IntersectionObserver(
      ([entry]) => {
        isVisible = entry.isIntersecting;
        updateLoop();
      },
      { threshold: 0 },
    );
    intersectionObserver.observe(canvas);

    const onVisibility = () => {
      isPageVisible = document.visibilityState === 'visible';
      updateLoop();
    };
    const onPointer = (event: PointerEvent) => {
      if (event.pointerType === 'touch') return;
      pointer.targetX = (event.clientX / window.innerWidth) * 2 - 1;
      pointer.targetY = (event.clientY / window.innerHeight) * 2 - 1;
      const rect = canvas.getBoundingClientRect();
      mouseTarget.isInside =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;
      if (mouseTarget.isInside) {
        mouseTarget.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouseTarget.y = 1 - ((event.clientY - rect.top) / rect.height) * 2;
        // Jump straight there when the cursor first arrives, then follow.
        if (mouse.active < 0.02) {
          mouse.x = mouseTarget.x;
          mouse.y = mouseTarget.y;
        }
      }
    };
    const onPointerLeave = () => {
      mouseTarget.isInside = false;
    };
    // The monospace face may still be loading; redraw the glyphs once it is in.
    document.fonts?.ready.then(
      () => scene?.refreshGlyphs(),
      () => undefined,
    );
    const onContextLost = (event: Event) => {
      event.preventDefault();
      isRunning = false;
      cancelAnimationFrame(frame);
    };
    const onContextRestored = () => {
      scene = createWebGLScene(canvas) ?? createCanvasScene(canvas);
      resize();
      updateLoop();
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pointermove', onPointer, { passive: true });
    document.documentElement.addEventListener('pointerleave', onPointerLeave);
    reducedMotion.addEventListener('change', updateLoop);
    canvas.addEventListener('webglcontextlost', onContextLost);
    canvas.addEventListener('webglcontextrestored', onContextRestored);
    updateLoop();

    return () => {
      isRunning = false;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pointermove', onPointer);
      document.documentElement.removeEventListener('pointerleave', onPointerLeave);
      reducedMotion.removeEventListener('change', updateLoop);
      canvas.removeEventListener('webglcontextlost', onContextLost);
      canvas.removeEventListener('webglcontextrestored', onContextRestored);
      scene?.dispose();
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
