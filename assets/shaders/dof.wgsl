// Custom circle-of-confusion (CoC) **background bokeh depth-of-field** — the player-focused,
// cinematic DoF the old game had. The focal plane (driven onto the hero) and EVERYTHING in
// front of it stay perfectly sharp; only the *distant background* melts into soft bokeh the
// farther it is past the focus band. This is FAR-ONLY on purpose: in this tilted near-top-down
// camera the bottom of the screen is always the nearest ground, so blurring the foreground
// (a GTA-style near field) just smears the ground at your feet and looks bad — Stronghold /
// RTS DoF blurs the distance, not what's under the camera.
//
// Single fullscreen post pass. Real **scatter-as-gather** bokeh (not a flat blur):
//   * each tap is weighted by COVERAGE — does that tap's own blur disc actually reach this
//     pixel? — instead of a plain average, so distance defocuses cleanly;
//   * a sharp subject REJECTS background taps (taps in front, and via the sharp→blur blend),
//     so the blurred distance never haloes onto the hero's silhouette;
//   * bright taps are emphasised so highlights bloom into round bokeh discs, not grey mush.
// Bevy has no built-in DoF in 0.18, so this is the whole effect.

#import bevy_core_pipeline::fullscreen_vertex_shader::FullscreenVertexOutput

@group(0) @binding(0) var screen_texture: texture_2d<f32>;
@group(0) @binding(1) var texture_sampler: sampler;
@group(0) @binding(2) var depth_texture: texture_depth_2d;

struct Settings {
    focal: f32,       // focus distance (tiles) — driven onto the player each frame
    range: f32,       // half-width of the fully-sharp focus band (tiles)
    far_ramp: f32,    // tiles over which FAR blur ramps to max (large = gradual)
    max_radius: f32,  // maximum blur radius (px)
    near: f32,        // camera near plane (reverse-z depth → distance)
    debug_view: f32,  // >0.5 → output CoC as grayscale (debug), don't blur
}
@group(0) @binding(3) var<uniform> settings: Settings;

const TAPS: i32 = 32;           // background bokeh gather
const GOLDEN_ANGLE: f32 = 2.39996323;
const BOKEH_PUNCH: f32 = 3.0;   // how hard bright taps bloom into bokeh discs

// Eye-forward distance from reverse-z prepass depth. Sky / cleared depth → very far.
fn dist_at(coord: vec2<i32>) -> f32 {
    let d = textureLoad(depth_texture, coord, 0);
    if d <= 0.0 {
        return 1.0e5;
    }
    return settings.near / d;
}

// FAR circle of confusion, in PIXELS. 0 everywhere up to and inside the sharp band
// [focal ± range] — so the subject AND everything in front of it stay sharp. Past the band it
// ramps GRADUALLY over `far_ramp` tiles (distance keeps getting blurrier, never clamps flat).
fn coc_far_px(dist: f32) -> f32 {
    let beyond = (dist - settings.focal) - settings.range;
    if beyond <= 0.0 {
        return 0.0;
    }
    return clamp(beyond / max(settings.far_ramp, 0.001), 0.0, 1.0) * settings.max_radius;
}

fn luma(c: vec3<f32>) -> f32 {
    return dot(c, vec3<f32>(0.299, 0.587, 0.114));
}

@fragment
fn fragment(in: FullscreenVertexOutput) -> @location(0) vec4<f32> {
    let dims = vec2<f32>(textureDimensions(screen_texture));
    let texel = 1.0 / dims;
    let coord = vec2<i32>(in.position.xy);
    let max_c = vec2<i32>(dims) - vec2<i32>(1, 1);

    let center = textureSample(screen_texture, texture_sampler, in.uv);
    let dist_c = dist_at(coord);
    let far_c = coc_far_px(dist_c);     // this pixel's own background blur radius (px)
    let far01 = clamp(far_c / max(settings.max_radius, 0.001), 0.0, 1.0);

    if settings.debug_view > 0.5 {
        return vec4<f32>(far01, far01, far01, 1.0); // white = background (blurred), black = sharp
    }

    // Sharp subject / foreground → return untouched (the common case: the whole near half of
    // the frame). Cheap early-out keeps the gather cost only on the distant background.
    if far_c < 0.5 {
        return center;
    }

    // Disc gather sized to THIS pixel's blur. Each tap is weighted by whether its own blur disc
    // is wide enough to reach the centre (coverage) — "scatter as you gather" — and bright taps
    // are emphasised so highlights form round bokeh discs.
    var acc = center.rgb;               // centre seeds with weight 1
    var total = 1.0;
    for (var i = 0; i < TAPS; i = i + 1) {
        let fi = f32(i) + 0.5;
        let ang = fi * GOLDEN_ANGLE;
        let rad = sqrt(fi / f32(TAPS)) * far_c;                // px
        let off = vec2<f32>(cos(ang), sin(ang)) * rad;
        let tcoord = clamp(coord + vec2<i32>(off), vec2<i32>(0, 0), max_c);
        let tcol = textureSample(screen_texture, texture_sampler, in.uv + off * texel).rgb;
        let tdist = dist_at(tcoord);
        let tfar = coc_far_px(tdist);
        // coverage: does the tap's blur disc reach the centre? soft 1px edge.
        let cov = clamp(tfar - rad + 1.0, 0.0, 1.0);
        // reject taps clearly IN FRONT of the centre — a sharp foreground must never bleed into
        // the background blur (it stays crisp).
        let front = step(tdist, dist_c - 1.0);
        // brighter taps bloom harder → bokeh balls instead of a flat smear.
        let w = cov * (1.0 - front) * (1.0 + luma(tcol) * BOKEH_PUNCH);
        acc += tcol * w;
        total += w;
    }
    let far_blur = acc / total;

    // The deeper past the focus band, the more this pixel becomes the bokeh blur. A pixel right
    // at the band edge (far01 → 0) keeps its own colour, so the transition is seamless and the
    // subject's silhouette stays crisp.
    return vec4<f32>(mix(center.rgb, far_blur, far01), center.a);
}
