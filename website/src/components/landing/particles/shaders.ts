// GLSL for the hero's particle field. Plain WebGL 1 so it runs on every
// browser that has WebGL at all; no libraries.

// 3D simplex noise, Ashima Arts / Stefan Gustavson (MIT).
const SIMPLEX_NOISE = /* glsl */ `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(
            i.z + vec4(0.0, i1.z, i2.z, 1.0))
          + i.y + vec4(0.0, i1.y, i2.y, 1.0))
          + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}
`;

/*
 * Each particle is one vertex, drawn as a 0 or a 1: aPos = (column -1..1, depth 0..1, seed, seed2).
 * The surface height comes from two travelling swells plus two octaves of
 * drifting simplex noise. Nothing is periodic, so the motion never visibly
 * loops or resets.
 */
export const WAVE_VERTEX = /* glsl */ `
precision highp float;

attribute vec4 aPos;

uniform float uTime;
uniform float uAspect;
uniform float uDpr;
uniform float uSize;
uniform vec2 uPointer;
// The cursor in this canvas's clip space, and how present it is (0..1).
uniform vec2 uMouse;
uniform float uMouseActive;

varying float vShade;
varying float vAlpha;
varying float vOcclusion;
varying float vGlyph;

${SIMPLEX_NOISE}

const float NEAR_Z = 0.9;
const float FAR_Z = 19.0;
const float CAMERA_Y = 4.0;
const float FOCAL = 1.9;

// The broad swell: two travelling waves and one octave of drifting noise.
float swell(vec2 p, float t) {
  float h = sin(p.x * 0.30 + p.y * 0.17 + t * 0.40 + 1.7 * sin(p.y * 0.11 - t * 0.15)) * 0.55;
  h += sin(p.y * 0.50 - t * 0.58 + 0.8 * sin(p.x * 0.21 + t * 0.19)) * 0.30;
  h += snoise(vec3(p * 0.15 + vec2(t * 0.034, -t * 0.05), t * 0.055)) * 0.90;
  return h;
}

// Fine ripples ride on the swell but do not change how it is lit.
float ripple(vec2 p, float t) {
  return snoise(vec3(p * 0.41 - vec2(t * 0.06, 0.0), t * 0.10 + 7.0)) * 0.22;
}

void main() {
  float t = uTime;
  float seed = aPos.z;
  float seed2 = aPos.w;

  float depth = aPos.y;
  // Rows bunch toward the viewer so the near swell stays dense on screen.
  float z = mix(NEAR_Z, FAR_Z, pow(depth, 1.3));
  float spread = 0.7 + (1.6 + z * 0.42) * max(uAspect, 0.85);
  float x = aPos.x * spread;

  // A small private drift per particle keeps the lattice from reading as a grid.
  x += sin(t * 0.31 + seed * 6.2831) * 0.05 * (1.0 + z * 0.04);
  z += cos(t * 0.27 + seed2 * 6.2831) * 0.05;

  // Sampled a little denser than world space so several bands cross the frame.
  vec2 p = vec2(x, z) * 1.45;
  float base = swell(p, t);
  float h = base + ripple(p, t);
  float e = 0.22;
  float hx = swell(p + vec2(e, 0.0), t);
  float hz = swell(p + vec2(0.0, e), t);
  vec3 normal = normalize(vec3(-(hx - base) / e, 1.0, -(hz - base) / e));
  vec3 lightDir = normalize(vec3(-0.35, 0.85, -0.5));
  float diffuse = clamp(dot(normal, lightDir), 0.0, 1.0);

  float amplitude = 1.1;
  vec3 world = vec3(x, h * amplitude, z);

  // Steep enough that the swell fills the frame, like a flow seen from above.
  float pitch = 0.75 + uPointer.y * 0.02;
  float c = cos(pitch);
  float s = sin(pitch);
  float cy = world.y - CAMERA_Y;
  vec3 view = vec3(world.x - uPointer.x * 0.55, cy * c + world.z * s, world.z * c - cy * s);

  if (view.z < 0.2) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    gl_PointSize = 0.0;
    vShade = 0.0;
    vAlpha = 0.0;
    vOcclusion = 0.0;
    vGlyph = 0.0;
    return;
  }

  vec4 clip = vec4(view.x * FOCAL / uAspect, view.y * FOCAL, 0.0, view.z);
  vec2 ndc = clip.xy / clip.w;

  // Around the cursor the data wakes up: rings spread outward from it and the
  // glyphs are pushed aside, measured in screen space so it follows the mouse.
  vec2 toPoint = (ndc - uMouse) * vec2(uAspect, 1.0);
  float distanceToMouse = length(toPoint);
  float influence = exp(-distanceToMouse * distanceToMouse * 7.0) * uMouseActive;
  vec2 away = distanceToMouse > 0.0001 ? toPoint / distanceToMouse : vec2(0.0);
  float rings = sin(distanceToMouse * 26.0 - t * 7.5);
  vec2 push = away * (influence * 0.045 + rings * influence * 0.016);
  ndc += push / vec2(uAspect, 1.0);
  gl_Position = vec4(ndc * clip.w, clip.z, clip.w);

  // A soft key light drifts across the field, like the luminous core of the reference.
  vec2 core = vec2(0.14 * sin(t * 0.06) + 0.02, 0.05 + 0.09 * sin(t * 0.045 + 1.3));
  vec2 dc = ndc - core;
  float key = exp(-(dc.x * dc.x * 0.55 + dc.y * dc.y * 1.15));

  // Light follows the swell: crests and lit slopes glow, troughs fall away to
  // near black, so the bands of dots read as waves rather than speckle.
  float crest = smoothstep(-0.35, 1.35, h);
  float tone = pow(clamp(crest * 0.62 + diffuse * 0.38, 0.0, 1.0), 1.9);
  float shade = mix(0.04, 1.0, tone) * (0.22 + 0.78 * key);

  // Low-frequency noise thins and thickens the cloud for organic density.
  float density = 0.45 + 0.55 * smoothstep(-0.55, 0.65, snoise(vec3(p * 0.065, t * 0.02 + 3.0)));

  float nearFade = smoothstep(0.0, 0.1, depth);
  float farFade = 1.0 - smoothstep(0.55, 1.0, depth);
  // Atmospheric falloff: rows bunch up toward the horizon, so distant light is
  // thinned or it would pile up into a hard bright ridge.
  float haze = exp(-view.z * 0.06);
  // Troughs thin out almost to nothing, so the dots gather into flowing bands.
  float band = mix(0.08, 1.0, smoothstep(-0.05, 0.7, crest));
  // Many glyphs overlap at this density, so each one adds only a little light.
  float alpha = nearFade * farFade * haze * 0.62 * band * density * (0.8 + 0.2 * seed2) * (0.55 + 0.45 * key);
  // Bright dots mostly add light, so dense crests glow like the reference's core.
  float occlusion = 0.3;

  // About one particle in twelve is a dark mote: drawn near over bright far
  // crests, it reads as depth instead of disappearing into the background.
  if (seed < 0.08) {
    shade *= 0.08;
    alpha = nearFade * farFade * (0.6 + 0.3 * key);
    occlusion = 1.0;
  }

  // Near the cursor the glyphs brighten and swell a little.
  shade = mix(shade, 1.0, influence * 0.55 * (0.6 + 0.4 * max(rings, 0.0)));
  alpha = min(1.0, alpha + influence * 0.45);

  float size = uSize * (0.7 + seed * 0.6) * (7.5 / view.z) * (0.6 + crest * 0.9) * (1.0 + influence * 0.35);
  size *= uDpr;
  float minSize = 1.2 * uDpr;
  if (size < minSize) {
    alpha *= size / minSize;
    size = minSize;
  }
  gl_PointSize = min(size, 8.0 * uDpr);

  // Each glyph is a 0 or a 1 that flips now and then; near the cursor it
  // flips fast, like data being rewritten under the pointer.
  float flipRate = 0.12 + seed2 * 0.25 + influence * 9.0;
  vGlyph = mod(floor(seed * 7.0 + t * flipRate + seed2 * 13.0), 2.0);

  vShade = shade;
  vAlpha = clamp(alpha, 0.0, 1.0);
  vOcclusion = occlusion;
}
`;

export const WAVE_FRAGMENT = /* glsl */ `
precision mediump float;

uniform sampler2D uGlyphs;

varying float vShade;
varying float vAlpha;
varying float vOcclusion;
varying float vGlyph;

// The atlas holds "0" on its left half and "1" on its right. Output is
// premultiplied (blend ONE, ONE_MINUS_SRC_ALPHA): colour is light added,
// alpha is how much of what lies behind the glyph it hides.
void main() {
  vec2 uv = vec2((gl_PointCoord.x + vGlyph) * 0.5, gl_PointCoord.y);
  // A sharper mip level keeps tiny glyphs reading as strokes, not smudges.
  float a = texture2D(uGlyphs, uv, -0.9).a * vAlpha;
  if (a < 0.004) discard;
  gl_FragColor = vec4(vec3(vShade) * a, a * vOcclusion);
}
`;

// Sparkles: aStar = (x, y in clip space, size in CSS px, seed).
export const STAR_VERTEX = /* glsl */ `
precision highp float;

attribute vec4 aStar;

uniform float uTime;
uniform float uDpr;

varying float vGlow;
varying float vFlare;

void main() {
  float seed = aStar.w;
  float twinkle = 0.5 + 0.5 * sin(uTime * (0.45 + seed * 1.1) + seed * 40.0);
  vec2 drift = vec2(sin(uTime * 0.045 + seed * 9.0), cos(uTime * 0.038 + seed * 7.0)) * 0.012;
  gl_Position = vec4(aStar.xy + drift, 0.0, 1.0);
  gl_PointSize = aStar.z * uDpr * (0.78 + 0.3 * twinkle);
  vGlow = 0.22 + 0.78 * twinkle * twinkle;
  vFlare = step(14.0, aStar.z);
}
`;

export const STAR_FRAGMENT = /* glsl */ `
precision mediump float;

varying float vGlow;
varying float vFlare;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  float core = smoothstep(0.09, 0.0, d);
  float halo = exp(-d * d * 30.0) * 0.5;
  float flare = (exp(-abs(c.x) * 70.0) * exp(-abs(c.y) * 7.0)
               + exp(-abs(c.y) * 70.0) * exp(-abs(c.x) * 7.0)) * 0.32 * vFlare;
  float a = (core + halo + flare) * vGlow * smoothstep(0.5, 0.42, d);
  gl_FragColor = vec4(vec3(1.0), a);
}
`;
