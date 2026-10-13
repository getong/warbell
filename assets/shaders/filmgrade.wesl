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

@fragment
fn fragment(in: FullscreenVertexOutput) -> @location(0) vec4<f32> {
    let src = textureSample(screen_texture, texture_sampler, in.uv);
    if grade.strength <= 0.001 {
        return src;
    }
    var lin = max(src.rgb, vec3<f32>(0.0));

    // ── Unsharp mask (linear, 4-tap cross) — luma-only so it never adds colour fringing. ──
    if grade.sharpen > 0.001 {
        let px = 1.0 / vec2<f32>(textureDimensions(screen_texture));
        let n = textureSample(screen_texture, texture_sampler, in.uv + vec2<f32>(0.0, -px.y)).rgb;
        let s = textureSample(screen_texture, texture_sampler, in.uv + vec2<f32>(0.0, px.y)).rgb;
        let e = textureSample(screen_texture, texture_sampler, in.uv + vec2<f32>(px.x, 0.0)).rgb;
        let w = textureSample(screen_texture, texture_sampler, in.uv + vec2<f32>(-px.x, 0.0)).rgb;
        let blur = luma(n + s + e + w) * 0.25;
        let l0 = luma(lin);
        // Clamp the detail term so high-contrast silhouettes (sky vs. trunk) don't ring.
        let detail = clamp(l0 - blur, -0.06, 0.06);
        let l1 = max(l0 + detail * grade.sharpen * 2.0, 0.0);
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

    // ── Filmic S-curve ── pivot just under mid-grey; a smooth blend toward a contrasted line,
    // shoulder/toe rolled by smoothstep so nothing clips harshly.
    let pivot = 0.42;
    let k = grade.contrast;
    let lin_c = clamp((c - vec3<f32>(pivot)) * k + vec3<f32>(pivot), vec3<f32>(0.0), vec3<f32>(1.0));
    let s_c = smoothstep(vec3<f32>(0.0), vec3<f32>(1.0), lin_c);
    c = mix(lin_c, s_c, 0.2);

    // ── Toe ── lift the floor into a faint cool tint (never pure #000 — soft film blacks).
    c = c * (1.0 - grade.toe) + grade.toe * grade.toe_tint;

    c = clamp(c, vec3<f32>(0.0), vec3<f32>(1.0));
    c = mix(graded_in, c, clamp(grade.strength, 0.0, 2.0));
    let out_lin = pow(max(c, vec3<f32>(0.0)), vec3<f32>(2.2));
    return vec4<f32>(out_lin, src.a);
}
