import React, { useEffect, useRef } from 'react';

type Props = {
  className?: string;
  label: string;
};

type Point = {
  x: number;
  y: number;
  z: number;
};

type FileNode = {
  name: string;
  x: number;
  y: number;
  z: number;
  source: number;
  seed: number;
  content: string;
  start: number;
  duration: number;
};

type Workstation = {
  x: number;
  y: number;
  z: number;
  seed: number;
};

const FILES: FileNode[] = [
  { name: 'SKILL.md', x: 0.61, y: 0.2, z: 0.68, source: 0, seed: 2, content: 'namefillform', start: 2.2, duration: 2.55 },
  { name: 'fill.md', x: 0.84, y: 0.2, z: 0.42, source: 0, seed: 5, content: 'fillpageform', start: 5.85, duration: 2.55 },
  { name: 'fill.js', x: 0.61, y: 0.5, z: 0.38, source: 1, seed: 8, content: '(){}fill();0', start: 2.45, duration: 2.55 },
  { name: 'locators.md', x: 0.84, y: 0.5, z: 0.72, source: 1, seed: 11, content: 'id01nameform', start: 6.1, duration: 2.55 },
  { name: 'manual-steps.md', x: 0.61, y: 0.8, z: 0.52, source: 2, seed: 14, content: 'step01step02', start: 2.7, duration: 2.55 },
  { name: 'evals.json', x: 0.84, y: 0.8, z: 0.3, source: 2, seed: 17, content: '{id:01};{}01', start: 6.35, duration: 2.55 },
];

const WORKSTATIONS: Workstation[] = [
  { x: 0.13, y: 0.2, z: 0.3, seed: 3 },
  { x: 0.13, y: 0.5, z: 0.7, seed: 8 },
  { x: 0.13, y: 0.8, z: 0.48, seed: 13 },
];

const CYCLE_SECONDS = 12.8;
const COMPLETE_HOLD_SECONDS = 0.42;
const FADE_SECONDS = 0.62;
const FLIGHT_SECONDS = 1.35;
const MAX_DPR = 2;
const BLUE = '#2f46f2';
const BRIGHT_BLUE = '#4462ff';
const GREY = '#687084';
const DARK = '#080a12';
const STILL_TIME = 9.4;
const PACKET_CHARACTERS = ['0', '1', '{', '}', 'f', 'j', 'S'];

const GLYPHS: Record<string, string[]> = {
  A: ['010', '101', '111', '101', '101'],
  C: ['111', '100', '100', '100', '111'],
  D: ['110', '101', '101', '101', '110'],
  E: ['111', '100', '110', '100', '111'],
  F: ['111', '100', '110', '100', '100'],
  I: ['111', '010', '010', '010', '111'],
  J: ['011', '001', '001', '101', '010'],
  K: ['101', '110', '100', '110', '101'],
  L: ['100', '100', '100', '100', '111'],
  M: ['10001', '11011', '10101', '10001', '10001'],
  N: ['1001', '1101', '1011', '1001', '1001'],
  O: ['111', '101', '101', '101', '111'],
  P: ['110', '101', '110', '100', '100'],
  R: ['110', '101', '110', '101', '101'],
  S: ['111', '100', '111', '001', '111'],
  T: ['111', '010', '010', '010', '010'],
  U: ['101', '101', '101', '101', '111'],
  V: ['101', '101', '101', '101', '010'],
  a: ['000', '011', '101', '111', '101'],
  c: ['000', '011', '100', '100', '011'],
  d: ['001', '011', '101', '101', '011'],
  e: ['000', '010', '101', '110', '011'],
  f: ['011', '100', '110', '100', '100'],
  g: ['000', '011', '101', '011', '001'],
  i: ['010', '000', '110', '010', '111'],
  j: ['001', '000', '001', '101', '010'],
  k: ['100', '101', '110', '101', '101'],
  l: ['110', '010', '010', '010', '111'],
  m: ['000', '110', '101', '101', '101'],
  n: ['000', '110', '101', '101', '101'],
  o: ['000', '010', '101', '101', '010'],
  p: ['000', '110', '101', '110', '100'],
  r: ['000', '101', '110', '100', '100'],
  s: ['000', '011', '100', '010', '110'],
  t: ['010', '111', '010', '010', '001'],
  u: ['000', '101', '101', '101', '011'],
  v: ['000', '101', '101', '101', '010'],
  '.': ['000', '000', '000', '000', '010'],
  '-': ['000', '000', '111', '000', '000'],
  '{': ['011', '010', '100', '010', '011'],
  '}': ['110', '010', '001', '010', '110'],
  '(': ['001', '010', '010', '010', '001'],
  ')': ['100', '010', '010', '010', '100'],
  ':': ['000', '010', '000', '010', '000'],
  ';': ['000', '010', '000', '010', '100'],
  '0': ['111', '101', '101', '101', '111'],
  '1': ['010', '110', '010', '010', '111'],
  '2': ['110', '001', '010', '100', '111'],
  '3': ['110', '001', '010', '001', '110'],
  '4': ['101', '101', '111', '001', '001'],
  '5': ['111', '100', '110', '001', '110'],
  '6': ['011', '100', '111', '101', '111'],
  '7': ['111', '001', '010', '010', '010'],
  '8': ['111', '101', '111', '101', '111'],
  '9': ['111', '101', '111', '001', '110'],
};

function clamp(value: number, minimum = 0, maximum = 1): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function fract(value: number): number {
  return value - Math.floor(value);
}

function easeOut(value: number): number {
  const clamped = clamp(value);
  return 1 - Math.pow(1 - clamped, 3);
}

function smooth(value: number): number {
  const bounded = clamp(value);
  return bounded * bounded * (3 - 2 * bounded);
}

type FilePhase = {
  progress: number;
  completion: number;
  typing: number;
  nextIndex: number;
  local: number;
};

function cycleTime(time: number): number {
  return ((time % CYCLE_SECONDS) + CYCLE_SECONDS) % CYCLE_SECONDS;
}

function filePhase(file: FileNode, time: number): FilePhase {
  const local = cycleTime(time) - file.start;
  const fadeStart = CYCLE_SECONDS - file.start - 1.1;
  const fadeEnd = fadeStart + FADE_SECONDS;
  let progress = 0;
  let completion = 0;
  let typing = 0;

  if (local >= 0 && local < file.duration) {
    const interval = (file.duration - FLIGHT_SECONDS) / (file.content.length - 1);
    const arrived = local < FLIGHT_SECONDS ? 0 : Math.floor((local - FLIGHT_SECONDS) / interval) + 1;
    progress = clamp(arrived / file.content.length);
    typing = Math.sin(local * 18) * 0.2 + 0.8;
  } else if (local >= file.duration && local < fadeStart) {
    progress = 1;
    completion = Math.sin(clamp((local - file.duration) / COMPLETE_HOLD_SECONDS) * Math.PI);
  } else if (local >= fadeStart && local < fadeEnd) {
    const fade = smooth((local - fadeStart) / FADE_SECONDS);
    progress = 1 - fade;
    completion = 0;
  }

  const nextIndex = Math.min(file.content.length - 1, Math.floor(progress * file.content.length));
  return { progress, completion, typing, nextIndex, local };
}

function seeded(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return fract(value);
}

function project(point: Point, width: number, height: number): { x: number; y: number; scale: number } {
  const depth = point.z - 0.5;
  return {
    x: point.x * width + depth * width * 0.012,
    y: point.y * height - depth * height * 0.018,
    scale: 0.78 + point.z * 0.42,
  };
}

function bezier(start: Point, control: Point, end: Point, progress: number): Point {
  const inverse = 1 - progress;
  return {
    x: inverse * inverse * start.x + 2 * inverse * progress * control.x + progress * progress * end.x,
    y: inverse * inverse * start.y + 2 * inverse * progress * control.y + progress * progress * end.y,
    z: start.z + (end.z - start.z) * progress + Math.sin(progress * Math.PI) * 0.12,
  };
}

function drawDot(
  context: CanvasRenderingContext2D,
  point: Point,
  width: number,
  height: number,
  radius: number,
  colour: string,
  alpha: number,
  glow = false,
): void {
  const projected = project(point, width, height);
  const size = Math.max(0.45, radius * projected.scale);
  context.globalAlpha = clamp(alpha) * (0.72 + projected.scale * 0.22);
  context.fillStyle = colour;
  // Small concentric dots give a halo without a blur filter on every particle.
  if (glow) {
    context.globalAlpha *= 0.1;
    context.beginPath();
    context.arc(projected.x, projected.y, size * 3.8, 0, Math.PI * 2);
    context.fill();
    context.globalAlpha *= 10;
  }
  context.beginPath();
  context.arc(projected.x, projected.y, size, 0, Math.PI * 2);
  context.fill();
}

function drawDottedLine(
  context: CanvasRenderingContext2D,
  start: Point,
  end: Point,
  width: number,
  height: number,
  spacing: number,
  radius: number,
  colour: string,
  alpha: number,
): void {
  const distance = Math.hypot(end.x - start.x, end.y - start.y);
  const count = Math.max(2, Math.ceil(distance / spacing));
  for (let index = 0; index <= count; index += 1) {
    const progress = index / count;
    drawDot(
      context,
      {
        x: start.x + (end.x - start.x) * progress,
        y: start.y + (end.y - start.y) * progress,
        z: start.z + (end.z - start.z) * progress,
      },
      width,
      height,
      radius,
      colour,
      alpha,
    );
  }
}

type DotGlyph = { width: number; dots: { x: number; y: number }[] };

// Glyph geometry is shared by labels, file content and airborne characters.
const DOT_GLYPHS: Record<string, DotGlyph> = Object.fromEntries(
  Object.entries(GLYPHS).map(([character, rows]) => [character, {
    width: Math.max(...rows.map((row) => row.length)),
    dots: rows.flatMap((row, y) => Array.from(row).flatMap((pixel, x) => pixel === '1' ? [{ x, y }] : [])),
  }]),
);

function drawGlyph(
  context: CanvasRenderingContext2D,
  glyph: DotGlyph,
  centre: Point,
  step: number,
  width: number,
  height: number,
  colour: string,
  alpha: number,
  glow = false,
): void {
  glyph.dots.forEach((dot) => {
    drawDot(context, {
      x: centre.x + (dot.x - (glyph.width - 1) / 2) * step / width,
      y: centre.y + (dot.y - 2) * step / height,
      z: centre.z,
    }, width, height, step * 0.3, colour, alpha, glow);
  });
}

function drawDotText(
  context: CanvasRenderingContext2D,
  text: string,
  centreX: number,
  topY: number,
  maxWidth: number,
  width: number,
  height: number,
  z: number,
  progress: number,
  colour: string,
): void {
  const glyphs = Array.from(text).map((character) => DOT_GLYPHS[character]);
  const units = glyphs.reduce((total, glyph) => total + glyph.width, 0) + Math.max(0, glyphs.length - 1);
  const step = Math.min(2.05, maxWidth / Math.max(1, units));
  let cursor = centreX * width - (units * step) / 2;
  glyphs.forEach((glyph, characterIndex) => {
    const characterProgress = clamp(progress * glyphs.length - characterIndex);
    drawGlyph(context, glyph, {
      x: (cursor + (glyph.width - 1) * step / 2) / width,
      y: topY + 2 * step / height,
      z,
    }, step, width, height, colour, characterProgress * 0.85);
    cursor += (glyph.width + 1) * step;
  });
}

function drawFileContent(
  context: CanvasRenderingContext2D,
  file: FileNode,
  width: number,
  height: number,
  progress: number,
): void {
  Array.from(file.content).forEach((character, index) => {
    const characterProgress = clamp(progress * file.content.length - index);
    if (characterProgress <= 0) return;
    const glyph = DOT_GLYPHS[character] ?? DOT_GLYPHS['-'];
    drawGlyph(
      context,
      glyph,
      fileCharacterPoint(file, index),
      Math.min(1.1, width * 0.0028),
      width,
      height,
      characterProgress > 0.82 ? BRIGHT_BLUE : GREY,
      0.12 + characterProgress * 0.48,
      characterProgress > 0.9,
    );
  });
}

function fileCharacterPoint(file: FileNode, index: number): Point {
  return {
    x: file.x - 0.073 + (index % 6) * 0.027,
    y: file.y + 0.035 + Math.floor(index / 6) * 0.032,
    z: file.z + 0.025,
  };
}

function drawFile(
  context: CanvasRenderingContext2D,
  file: FileNode,
  width: number,
  height: number,
  progress: number,
  completion: number,
): void {
  const fileWidth = 0.205;
  const fileHeight = 0.19;
  const left = file.x - fileWidth / 2;
  const right = file.x + fileWidth / 2;
  const top = file.y - fileHeight / 2;
  const bottom = file.y + fileHeight / 2;
  const borderAlpha = 0.2 + progress * 0.42;
  const corners: Point[] = [
    { x: left, y: top, z: file.z },
    { x: right, y: top, z: file.z },
    { x: right, y: bottom, z: file.z },
    { x: left, y: bottom, z: file.z },
  ];
  corners.forEach((corner, index) => {
    drawDottedLine(context, corner, corners[(index + 1) % corners.length], width, height, 0.018, 0.8, GREY, borderAlpha);
  });
  drawDottedLine(
    context,
    { x: left + 0.018, y: top + 0.042, z: file.z },
    { x: right - 0.018, y: top + 0.042, z: file.z },
    width,
    height,
    0.019,
    0.7,
    GREY,
    borderAlpha * 0.7,
  );
  drawDottedLine(
    context,
    { x: left + 0.025, y: top + 0.018, z: file.z },
    { x: left + 0.058, y: top + 0.018, z: file.z },
    width,
    height,
    0.016,
    0.85,
    BRIGHT_BLUE,
    0.35 + progress * 0.45,
  );
  for (let index = 0; index < 3; index += 1) {
    drawDot(
      context,
      { x: right - 0.058 + index * 0.014, y: top + 0.018, z: file.z + 0.015 },
      width,
      height,
      0.75,
      index === 0 && progress > 0.02 ? BRIGHT_BLUE : GREY,
      index === 0 ? 0.32 + progress * 0.48 : 0.2,
      index === 0 && progress > 0.78,
    );
  }
  drawDotText(context, file.name, file.x, top + 0.058, fileWidth * width * 0.88, width, height, file.z, progress, BRIGHT_BLUE);
  drawFileContent(context, file, width, height, progress);

  const rows = [0.11, 0.14, 0.17];
  rows.forEach((row, index) => {
    const rowProgress = clamp(progress * 3 - index - 0.8);
    const rowStart = left + 0.025;
    const rowEnd = left + 0.04 + (right - left - 0.065) * (0.6 + seeded(file.seed + index) * 0.35);
    drawDottedLine(context, { x: rowStart, y: top + row, z: file.z }, { x: rowEnd, y: top + row, z: file.z }, width, height, 0.016, 0.65, GREY, 0.12);
    if (rowProgress > 0) {
      drawDottedLine(context, { x: rowStart, y: top + row, z: file.z + 0.02 }, { x: rowStart + (rowEnd - rowStart) * easeOut(rowProgress), y: top + row, z: file.z + 0.02 }, width, height, 0.016, 0.85, BRIGHT_BLUE, 0.34 + rowProgress * 0.42);
    }
  });
  drawDottedLine(
    context,
    { x: left + 0.025, y: bottom - 0.018, z: file.z + 0.02 },
    { x: left + 0.025 + (right - left - 0.05) * progress, y: bottom - 0.018, z: file.z + 0.02 },
    width,
    height,
    0.016,
    0.72,
    BRIGHT_BLUE,
    0.3 + progress * 0.42,
  );
  if (completion > 0) {
    const ringRadius = 0.072 + completion * 0.05;
    for (let index = 0; index < 10; index += 1) {
      const angle = (index / 10) * Math.PI * 2;
      drawDot(
        context,
        { x: file.x + Math.cos(angle) * ringRadius, y: file.y + Math.sin(angle) * ringRadius, z: file.z + 0.08 },
        width,
        height,
        1.05,
        BRIGHT_BLUE,
        completion * (1 - index * 0.03),
        true,
      );
    }
  }
}

type AgentFrame = {
  x: number;
  y: number;
  z: number;
  opacity: number;
  typing: number;
  pickup: number;
};

function agentFrame(station: Workstation, index: number, time: number): AgentFrame {
  const local = cycleTime(time - index * 0.18);
  const arrival = 1.3;
  const pickupEnd = 1.95;
  const exitStart = 10.35;
  const exitEnd = 11.65;
  const stationX = station.x + 0.035;
  let x = stationX;
  let opacity = 1;
  let typing = 0;
  let pickup = 0;

  if (local < arrival) {
    const progress = smooth(local / arrival);
    x = -0.08 + (stationX + 0.08) * progress;
    opacity = clamp(local / 0.35);
  } else if (local < pickupEnd) {
    pickup = smooth((local - arrival) / (pickupEnd - arrival));
  } else if (local < exitStart) {
    typing = 1;
  } else if (local < exitEnd) {
    const progress = smooth((local - exitStart) / (exitEnd - exitStart));
    x = stationX + (1.06 - stationX) * progress;
    opacity = 1 - progress;
  } else {
    x = 1.06;
    opacity = 0;
  }

  return { x, y: station.y - 0.045, z: station.z + 0.07, opacity, typing, pickup };
}

function drawKeyboard(
  context: CanvasRenderingContext2D,
  station: Workstation,
  frame: AgentFrame,
  width: number,
  height: number,
  time: number,
): void {
  const typingPulse = 0.5 + 0.5 * Math.sin(time * 7 + station.seed);
  const lift = Math.sin(frame.pickup * Math.PI) * 0.045;
  const keyboard: Point = { x: station.x + 0.11, y: station.y + 0.045 - lift, z: station.z + 0.04 + lift };
  drawDottedLine(
    context,
    { x: station.x - 0.045, y: station.y + 0.07, z: station.z },
    { x: station.x + 0.185, y: station.y + 0.07, z: station.z },
    width,
    height,
    0.017,
    0.8,
    GREY,
    0.28,
  );
  for (let index = 0; index < 12; index += 1) {
    const angle = (index / 12) * Math.PI * 2;
    drawDot(
      context,
      { x: station.x + 0.035 + Math.cos(angle) * 0.048, y: station.y + 0.078 + Math.sin(angle) * 0.016, z: station.z - 0.01 },
      width,
      height,
      0.55,
      frame.typing > 0 ? BRIGHT_BLUE : GREY,
      0.08 + frame.opacity * 0.1 + frame.typing * 0.16,
      frame.typing > 0.85 && index % 3 === 0,
    );
  }
  for (let row = 0; row < 2; row += 1) {
    for (let column = 0; column < 5; column += 1) {
      const keyLight = frame.typing
        ? 0.18 + 0.48 * (0.5 + 0.5 * Math.sin(time * 6 + station.seed + row * 2 + column)) * (0.72 + typingPulse * 0.28)
        : 0.16 + frame.pickup * 0.3;
      drawDot(
        context,
        { x: keyboard.x + column * 0.017, y: keyboard.y + row * 0.014, z: keyboard.z },
        width,
        height,
        1.05,
        column === 2 && row === 0 ? BRIGHT_BLUE : GREY,
        keyLight,
        column === 2 && row === 0 && (frame.typing > 0.72 || frame.pickup > 0.75),
      );
    }
  }
}

function drawAgent(
  context: CanvasRenderingContext2D,
  station: Workstation,
  frame: AgentFrame,
  width: number,
  height: number,
  time: number,
): void {
  if (frame.opacity <= 0) return;
  const agentY = frame.y + Math.sin(time * 12 + station.seed) * 0.003 * frame.typing;
  const agentColour = station.seed % 3 === 0 ? DARK : station.seed % 2 === 0 ? GREY : BRIGHT_BLUE;
  for (let index = 0; index < 11; index += 1) {
    const angle = (index / 11) * Math.PI * 2;
    const wobble = 0.003 * Math.sin(time * 2.4 + index + station.seed);
    drawDot(
      context,
      { x: frame.x + Math.cos(angle) * 0.027 + wobble, y: agentY + Math.sin(angle) * 0.034, z: frame.z + index * 0.003 },
      width,
      height,
      index % 3 === 0 ? 1.5 : 1.05,
      index % 4 === 0 ? BRIGHT_BLUE : agentColour,
      frame.opacity * (0.45 + frame.typing * 0.38),
      index % 4 === 0 && frame.typing > 0.65,
    );
  }
  drawDot(context, { x: frame.x, y: agentY, z: frame.z + 0.05 }, width, height, 1.5, DARK, frame.opacity * 0.9);
  drawDot(context, { x: frame.x - 0.01, y: agentY - 0.008, z: frame.z + 0.06 }, width, height, 0.85, BRIGHT_BLUE, frame.opacity * 0.9, true);
  drawDot(context, { x: frame.x + 0.01, y: agentY - 0.008, z: frame.z + 0.06 }, width, height, 0.85, BRIGHT_BLUE, frame.opacity * 0.9, true);
  drawDottedLine(
    context,
    { x: frame.x, y: agentY - 0.036, z: frame.z + 0.02 },
    { x: frame.x, y: agentY - 0.06, z: frame.z + 0.01 },
    width,
    height,
    0.012,
    0.65,
    BRIGHT_BLUE,
    frame.opacity * 0.55,
  );
  if (frame.typing > 0) {
    const handBounce = Math.sin(time * 16 + station.seed) * 0.006;
    drawDottedLine(
      context,
      { x: frame.x + 0.017, y: agentY + 0.024, z: frame.z - 0.01 },
      { x: station.x + 0.098, y: station.y + 0.038 + handBounce, z: station.z + 0.07 },
      width,
      height,
      0.014,
      0.72,
      GREY,
      frame.opacity * 0.62,
    );
    drawDottedLine(
      context,
      { x: frame.x - 0.017, y: agentY + 0.024, z: frame.z - 0.01 },
      { x: station.x + 0.14, y: station.y + 0.038 - handBounce, z: station.z + 0.07 },
      width,
      height,
      0.014,
      0.72,
      GREY,
      frame.opacity * 0.62,
    );
  }
}

function drawWorkstation(
  context: CanvasRenderingContext2D,
  station: Workstation,
  index: number,
  width: number,
  height: number,
  time: number,
): void {
  const frame = agentFrame(station, index, time);
  drawKeyboard(context, station, frame, width, height, time);
  drawAgent(context, station, frame, width, height, time);
}

function drawPacket(
  context: CanvasRenderingContext2D,
  path: { start: Point; control: Point; end: Point },
  progress: number,
  width: number,
  height: number,
  seed: number,
  alpha: number,
  character: string,
): void {
  for (let trail = 4; trail >= 0; trail -= 1) {
    const trailProgress = progress - trail * 0.042;
    if (trailProgress < 0) continue;
    const point = bezier(path.start, path.control, path.end, trailProgress);
    const trailAlpha = alpha * (1 - trail / 6);
    if (trail > 0) {
      drawDot(context, point, width, height, 0.65, BLUE, trailAlpha * 0.3);
      continue;
    }
    drawGlyph(
      context,
      DOT_GLYPHS[character] ?? DOT_GLYPHS[PACKET_CHARACTERS[Math.floor(seed) % PACKET_CHARACTERS.length]],
      point,
      Math.min(1.65, width * 0.0035) * (1 - smooth(progress) * 0.33),
      width,
      height,
      trail === 0 ? BRIGHT_BLUE : BLUE,
      trailAlpha,
      trail === 0,
    );
    drawDot(context, point, width, height, 0.6, BRIGHT_BLUE, trailAlpha, trail === 0);
  }
}

function drawPaths(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  time: number,
): void {
  FILES.forEach((file, fileIndex) => {
    const station = WORKSTATIONS[file.source];
    const start = { x: station.x + 0.13, y: station.y + 0.045, z: station.z + 0.08 };
    const phase = filePhase(file, time);
    const targetIndex = Math.max(0, phase.nextIndex);
    const end = fileCharacterPoint(file, targetIndex);
    const bend = fileIndex % 2 === 0 ? -0.045 : 0.045;
    const control = { x: 0.4 + (fileIndex % 2) * 0.035, y: (start.y + end.y) / 2 + bend, z: 0.55 };
    for (let index = 0; index < 22; index += 1) {
      const progress = index / 21;
      const point = bezier(start, control, end, progress);
      drawDot(context, point, width, height, 0.65, BLUE, phase.typing > 0 ? 0.1 + 0.08 * (1 - progress) : 0.035);
    }
    if (phase.typing <= 0) return;
    const interval = (file.duration - FLIGHT_SECONDS) / (file.content.length - 1);
    for (let packetIndex = 0; packetIndex < file.content.length; packetIndex += 1) {
      const packetProgress = (phase.local - packetIndex * interval) / FLIGHT_SECONDS;
      if (packetProgress < 0 || packetProgress >= 1) continue;
      const packetEnd = fileCharacterPoint(file, packetIndex);
      const packetControl = { x: control.x, y: (start.y + packetEnd.y) / 2 + bend, z: control.z };
      drawPacket(
        context,
        { start, control: packetControl, end: packetEnd },
        packetProgress,
        width,
        height,
        file.seed + packetIndex,
        0.62 * smooth(packetProgress / 0.08),
        file.content[packetIndex],
      );
    }
  });
}

function drawDust(context: CanvasRenderingContext2D, width: number, height: number, time: number): void {
  for (let index = 0; index < 54; index += 1) {
    const x = 0.03 + seeded(index + 30) * 0.92;
    const y = 0.04 + seeded(index + 70) * 0.92;
    const z = seeded(index + 110);
    const drift = Math.sin(time * 0.12 + index) * 0.002;
    drawDot(context, { x: x + drift, y, z }, width, height, z > 0.65 ? 0.8 : 0.55, z > 0.72 ? GREY : BLUE, 0.06 + z * 0.08);
  }
}

function drawScene(context: CanvasRenderingContext2D, width: number, height: number, time: number): void {
  context.clearRect(0, 0, width, height);
  drawDust(context, width, height, time);
  drawPaths(context, width, height, time);
  WORKSTATIONS.forEach((station, index) => drawWorkstation(context, station, index, width, height, time));
  FILES.forEach((file) => {
    const phase = filePhase(file, time);
    drawFile(context, file, width, height, phase.progress, phase.completion);
  });
  context.globalAlpha = 1;
  context.shadowBlur = 0;
}

/**
 * A dots-only miniature of the skill-writing workspace: agents type, packet
 * clusters travel into files, and each file is progressively assembled.
 */
export default function AiWorkspaceDots({ className, label }: Props): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return undefined;

    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let width = 1;
    let height = 1;
    let running = false;
    let visible = false;
    let frame = 0;
    let last = 0;
    let time = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawScene(context, width, height, motionQuery.matches ? STILL_TIME : time);
    };

    const stop = () => {
      running = false;
      cancelAnimationFrame(frame);
      frame = 0;
    };

    const loop = (timestamp: number) => {
      if (!running) return;
      const delta = last ? Math.min((timestamp - last) / 1000, 1 / 20) : 0;
      last = timestamp;
      time += delta;
      drawScene(context, width, height, time);
      frame = requestAnimationFrame(loop);
    };

    const update = () => {
      if (motionQuery.matches) {
        stop();
        drawScene(context, width, height, STILL_TIME);
        return;
      }
      if (visible && document.visibilityState === 'visible' && !running) {
        running = true;
        last = 0;
        frame = requestAnimationFrame(loop);
      }
    };

    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) update();
      else stop();
    });
    const onVisibility = () => {
      if (document.visibilityState === 'visible') update();
      else stop();
    };

    resizeObserver.observe(canvas);
    intersectionObserver.observe(canvas);
    document.addEventListener('visibilitychange', onVisibility);
    motionQuery.addEventListener('change', update);
    resize();

    return () => {
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      motionQuery.removeEventListener('change', update);
    };
  }, []);

  return <canvas ref={canvasRef} className={className} role="img" aria-label={label} />;
}
