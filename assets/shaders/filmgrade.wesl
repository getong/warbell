// **Film grade** — final look pass (see `src/filmgrade.rs`): unsharp mask → split-tone → vibrance
// → filmic S-curve + tinted toe. Input is the tonemapped, linear-light frame in [0,1]; the tonal
// work happens in a gamma-2.2 display space (where "midtone" and "shadow" mean what the eye thinks
// they mean), then converts back to linear for the rest of Bevy's chain (upscale → swapchain sRGB).

import bevy_core_pipeline::fullscreen_vertex_shader::FullscreenVertexOutput;

@group(0) @binding(0) var screen_texture: texture_2d<f32>;
@group(0) @binding(1) var texture_sampler: sampler;

struct FilmGrade {
    shadow_tint: vec3<f32>,
    strength: f32,
    highlight_tint: vec3<f32>,
    split: f32,
    toe_tint: vec3<f32>,
    toe: f32,
    vibrance: f32,
    saturation: f32,
    contrast: f32,
    sharpen: f32,
    grain: f32,
    vignette: f32,
    aberration: f32,
    time: f32,
    halation: f32,
    streak: f32,
    weave: f32,
    olive: f32, // pull pure greens toward olive / straw (0 = off)
    clarity: f32, // mid-radius local contrast (0 = off)
}
@group(0) @binding(2) var<uniform> grade: FilmGrade;

const LUMA: vec3<f32> = vec3<f32>(0.2126, 0.7152, 0.0722);

fn luma(c: vec3<f32>) -> f32 {
    return dot(c, LUMA);
}

// Multiply by a tint, then restore the original luminance — a pure hue/chroma shift.
fn tint_keep_luma(c: vec3<f32>, tint: vec3<f32>) -> vec3<f32> {
    let t = c * tint;
    return t * (luma(c) / max(luma(t), 1e-4));
}

fn hash1(x: f32) -> f32 {
    return fract(sin(x * 91.3458) * 47453.5453);
}

// The part of a sample above `knee` (how much "light" spills into a glow).
fn hot(c: vec3<f32>, knee: f32) -> vec3<f32> {
    return c * (max(luma(c) - knee, 0.0) / max(luma(c), 1e-4));
}

@fragment
fn fragment(in: FullscreenVertexOutput) -> @location(0) vec4<f32> {
    let px = 1.0 / vec2<f32>(textureDimensions(screen_texture));
    // ── Gate weave ── the film frame settles a fraction of a pixel differently every frame (a
    // projector's gate never registers twice the same). Cutscenes only (0 in play).
    var uv = in.uv;
    if grade.weave > 0.0001 {
        uv = uv + (vec2<f32>(hash1(grade.time), hash1(grade.time + 3.7)) - 0.5) * px * grade.weave;
    }
    let src = textureSample(screen_texture, texture_sampler, uv);
    if grade.strength <= 0.001 {
        return src;
    }
    var lin = max(src.rgb, vec3<f32>(0.0));

    // ── Chromatic aberration ── red/blue split radially (zero at the centre, strongest at the
    // corners) — the cheap-lens fringe that sells "shot on glass". Off (0) in normal play.
    let to_c = uv - vec2<f32>(0.5);
    if grade.aberration > 0.00001 {
        let off = to_c * (dot(to_c, to_c) * 4.0) * grade.aberration;
        lin.r = textureSample(screen_texture, texture_sampler, uv + off).r;
        lin.b = textureSample(screen_texture, texture_sampler, uv - off).b;
    }

    // ── Halation ── light scattering back off the film base: a warm red-orange fringe that bleeds
    // around bright edges (sky behind a wall, a lit sleeve). Two rings of taps over the hot part.
    if grade.halation > 0.001 {
        var glow = vec3<f32>(0.0);
        for (var i = 0; i < 12; i++) {
            let a = f32(i) * 0.5236;
            let d = vec2<f32>(cos(a), sin(a));
            glow += hot(textureSample(screen_texture, texture_sampler, uv + d * px * 5.0).rgb, 0.55);
            glow += hot(textureSample(screen_texture, texture_sampler, uv + d * px * 12.0).rgb, 0.55) * 0.6;
        }
        glow = glow / 19.2;
        lin += luma(glow) * vec3<f32>(1.0, 0.36, 0.14) * grade.halation;
    }

    // ── Anamorphic streak ── a thin horizontal flare drawn out of the very brightest points (a
    // sun glint, a lantern), cool-tinted like a cylindrical lens.
    if grade.streak > 0.001 {
        var st = vec3<f32>(0.0);
        for (var i = 1; i <= 10; i++) {
            let o = f32(i) * f32(i) * 0.6 * px.x;
            let w = 1.0 - f32(i) / 11.0;
            st += (hot(textureSample(screen_texture, texture_sampler, uv + vec2<f32>(o, 0.0)).rgb, 0.85)
                + hot(textureSample(screen_texture, texture_sampler, uv - vec2<f32>(o, 0.0)).rgb, 0.85)) * w;
        }
        lin += luma(st) * 0.12 * vec3<f32>(0.55, 0.75, 1.0) * grade.streak;
    }

    // ── Unsharp mask (linear, 4-tap cross) — luma-only so it never adds colour fringing. ──
    if grade.sharpen > 0.001 {
        let n = textureSample(screen_texture, texture_sampler, uv + vec2<f32>(0.0, -px.y)).rgb;
        let s = textureSample(screen_texture, texture_sampler, uv + vec2<f32>(0.0, px.y)).rgb;
        let e = textureSample(screen_texture, texture_sampler, uv + vec2<f32>(px.x, 0.0)).rgb;
        let w = textureSample(screen_texture, texture_sampler, uv + vec2<f32>(-px.x, 0.0)).rgb;
        let blur = luma(n + s + e + w) * 0.25;
        let l0 = luma(lin);
        // Clamp the detail term so high-contrast silhouettes (sky vs. trunk) don't ring.
        let detail = clamp(l0 - blur, -0.06, 0.06);
        let l1 = max(l0 + detail * grade.sharpen * 2.0, 0.0);
        lin = lin * (l1 / max(l0, 1e-4));
    }

    // ── Clarity ── mid-radius local contrast (two 8-tap rings, ~4 and ~10 px): gives surfaces,
    // tufts and bark their modelling back without touching global contrast. Luma-only, clamped, and
    // weighted to the midtones so silhouettes against the sky don't halo.
    if grade.clarity > 0.001 {
        var acc = 0.0;
        for (var i = 0; i < 8; i++) {
            let a = f32(i) * 0.7853982 + 0.39;
            let d = vec2<f32>(cos(a), sin(a));
            acc += luma(textureSampleLevel(screen_texture, texture_sampler, uv + d * px * 4.0, 0.0).rgb);
            acc += luma(textureSampleLevel(screen_texture, texture_sampler, uv + d * px * 10.0, 0.0).rgb);
        }
        let wide = acc / 16.0;
        let l0 = luma(lin);
        let m = clamp(4.0 * l0 * (1.0 - l0) * 1.6, 0.0, 1.0);
        let detail = clamp(l0 - wide, -0.10, 0.10);
        let l1 = max(l0 + detail * grade.clarity * m, 0.0);
        lin = lin * (l1 / max(l0, 1e-4));
    }

    // Display space (gamma 2.2) for the tonal shaping.
    var c = pow(min(lin, vec3<f32>(1.0)), vec3<f32>(1.0 / 2.2));
    let graded_in = c;

    // ── Split-tone ── shadows → cool, highlights → warm; luminance preserved per step.
    let l = luma(c);
    let w_sh = (1.0 - smoothstep(0.05, 0.55, l)) * grade.split;
    let w_hi = smoothstep(0.40, 0.95, l) * grade.split;
    c = mix(c, tint_keep_luma(c, grade.shadow_tint), w_sh);
    c = mix(c, tint_keep_luma(c, grade.highlight_tint), w_hi);

    // ── Vibrance ── push saturation hardest where colour is weakest.
    let lv = luma(c);
    let sat = max(max(c.r, c.g), c.b) - min(min(c.r, c.g), c.b);
    let vib = 1.0 + grade.vibrance * (1.0 - smoothstep(0.0, 0.6, sat));
    c = mix(vec3<f32>(lv), c, vib * grade.saturation);
    // ── Olive ── a green that beats both red and blue gains red: lawn-green -> olive / straw, the
    // muted foliage palette of photo-real outdoor scenes (no effect on skin, sky, wood or stone).
    let greenness = max(c.g - max(c.r, c.b), 0.0);
    c = vec3<f32>(c.r + grade.olive * greenness * 0.55, c.g, c.b + grade.olive * greenness * 0.05);

    // ── Filmic S-curve ── pivot just under mid-grey; a smooth blend toward a contrasted line,
    // shoulder/toe rolled by smoothstep so nothing clips harshly.
    let pivot = 0.42;
    let k = grade.contrast;
    let lin_c = clamp((c - vec3<f32>(pivot)) * k + vec3<f32>(pivot), vec3<f32>(0.0), vec3<f32>(1.0));
    let s_c = smoothstep(vec3<f32>(0.0), vec3<f32>(1.0), lin_c);
    c = mix(lin_c, s_c, 0.2);

    // ── Toe ── lift the floor into a faint cool tint (never pure #000 — soft film blacks).
    c = c * (1.0 - grade.toe) + grade.toe * grade.toe_tint;

    // ── Vignette ── soft optical fall-off toward the corners (display space, so it reads as light
    // loss rather than a grey overlay).
    if grade.vignette > 0.001 {
        let r = length(to_c * vec2<f32>(1.0, 0.8)) * 1.45;
        c = c * (1.0 - grade.vignette * smoothstep(0.35, 1.0, r));
    }

    // ── Film grain ── per-pixel hash, re-seeded each frame, strongest in the mid-tones and
    // quiet in deep shadow / clipped highlights so it never lifts the blacks.
    if grade.grain > 0.001 {
        let p = in.position.xy + vec2<f32>(grade.time * 61.0, grade.time * 37.0);
        let n = fract(sin(dot(p, vec2<f32>(12.9898, 78.233))) * 43758.5453) - 0.5;
        let n2 = fract(sin(dot(p + 7.1, vec2<f32>(39.346, 11.135))) * 24634.6345) - 0.5;
        let lm = luma(c);
        let w = 4.0 * lm * (1.0 - lm) + 0.15;
        c = c + vec3<f32>(n + 0.35 * n2) * grade.grain * w;
    }

    c = clamp(c, vec3<f32>(0.0), vec3<f32>(1.0));
    c = mix(graded_in, c, clamp(grade.strength, 0.0, 2.0));
    let out_lin = pow(max(c, vec3<f32>(0.0)), vec3<f32>(2.2));
    return vec4<f32>(out_lin, src.a);
}
