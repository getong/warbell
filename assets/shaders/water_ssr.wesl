// **Water screen-space reflections** — see `src/water_ssr.rs`. Every water surface on the island
// is ONE plane at `sea_y`, so a water pixel is found straight from depth (its unprojected world Y
// sits on the plane) — no mask, no extra target. From there the view ray is mirrored about a
// gently rippled normal and marched in world space, projected back to the screen each step and
// tested against the prepass depth; a hit mirrors the already-lit scene (banks, trees, buildings,
// ships) into the water with a Fresnel weight. Misses keep the water shader's own sky reflection.

import bevy_core_pipeline::fullscreen_vertex_shader::FullscreenVertexOutput;
import bevy_render::view::View;

@group(0) @binding(0) var screen_texture: texture_2d<f32>;
@group(0) @binding(1) var texture_sampler: sampler;
@group(0) @binding(2) var depth_texture: texture_depth_2d;

struct Settings {
    sea_y: f32,
    time: f32,
    strength: f32,   // 0 = off; scales the Fresnel blend
    ripple: f32,     // normal tilt of the reflection ripples
    max_dist: f32,   // longest reflected ray (world units)
}
@group(0) @binding(3) var<uniform> settings: Settings;
// This frame's render-world camera (jittered like the depth it unprojects) — see `src/water_ssr.rs`.
@group(0) @binding(4) var<uniform> view: View;

const STEPS: i32 = 48;
const REFINE: i32 = 6;
// What the mirrored light passes through: tannin / silt water dims and warms it — a murky river,
// not a glass mirror (the first cut read as glowing chrome).
const MURK: vec3<f32> = vec3<f32>(0.72, 0.68, 0.56);

fn depth_at(uv: vec2<f32>) -> f32 {
    let dsize = vec2<f32>(textureDimensions(depth_texture));
    let p = clamp(vec2<i32>(uv * dsize), vec2<i32>(0), vec2<i32>(dsize) - vec2<i32>(1));
    return textureLoad(depth_texture, p, 0);
}

fn unproject(uv: vec2<f32>, d: f32) -> vec3<f32> {
    let ws = view.world_from_clip * vec4<f32>(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0, d, 1.0);
    return ws.xyz / ws.w;
}

// World point → (uv, ok). `ok` false behind the camera.
fn project(p: vec3<f32>) -> vec3<f32> {
    let c = view.clip_from_world * vec4<f32>(p, 1.0);
    if c.w <= 0.0001 {
        return vec3<f32>(0.0, 0.0, -1.0);
    }
    let n = c.xy / c.w;
    return vec3<f32>(n.x * 0.5 + 0.5, 0.5 - n.y * 0.5, 1.0);
}

fn hash2(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.5453);
}

fn vnoise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2<f32>(1.0, 0.0)), u.x),
               mix(hash2(i + vec2<f32>(0.0, 1.0)), hash2(i + vec2<f32>(1.0, 1.0)), u.x), u.y);
}

// Wind ripples: a small spectrum of directional wavelets fanned around a fixed breeze (sum of
// sines, analytic slope — smooth and round, no value-noise grid), with a gentle low-frequency domain
// warp so the crests wander instead of tiling. Returns the surface slope (d/dx, d/dz).
fn wind_ripples(p: vec2<f32>, t: f32) -> vec2<f32> {
    let warp = vec2<f32>(vnoise(p * 0.21 + vec2<f32>(t * 0.05, 0.0)), vnoise(p * 0.21 + vec2<f32>(7.3, t * 0.04))) - 0.5;
    let q = p + warp * 2.2;
    var g = vec2<f32>(0.0);
    // (angle off the wind, wavelength in units, amplitude) — longer waves carry more slope.
    let angles = array<f32, 6>(0.0, 0.42, -0.37, 0.95, -0.88, 0.18);
    let lens = array<f32, 6>(1.9, 1.3, 1.1, 0.75, 0.62, 0.48);
    let amps = array<f32, 6>(0.11, 0.08, 0.08, 0.05, 0.05, 0.035);
    for (var i = 0; i < 6; i++) {
        let a = 0.64 + angles[i]; // breeze heading (rad)
        let dir = vec2<f32>(cos(a), sin(a));
        let k = 6.2831853 / lens[i];
        let speed = sqrt(9.8 / k) * 0.35; // short waves crawl, longer ones roll faster
        let phase = dot(q, dir) * k - t * speed * k + f32(i) * 1.7;
        g += dir * (cos(phase) * amps[i] * k);
    }
    return g;
}

@fragment
fn fragment(in: FullscreenVertexOutput) -> @location(0) vec4<f32> {
    let scene = textureSample(screen_texture, texture_sampler, in.uv);
    if settings.strength <= 0.001 {
        return scene;
    }
    let d = depth_at(in.uv);
    if d <= 0.0 {
        return scene; // sky
    }
    let pos = unproject(in.uv, d);
    if abs(pos.y - settings.sea_y) > 0.02 {
        return scene; // not the water plane
    }

    let to_p = pos - view.world_position;
    let dist = length(to_p);
    let v = to_p / dist;
    // Wind ripples tilt the mirror normal (smooth sum-of-sines slope — continuous across pixels, so
    // the mirrored image bends in waves instead of tearing into slices), fading out far away where
    // they'd only alias: distant water is a calmer mirror.
    let wr = wind_ripples(pos.xz, settings.time) * (1.0 - smoothstep(30.0, 110.0, dist));
    let s = wr * settings.ripple;
    let n = normalize(vec3<f32>(-s.x, 1.0, -s.y));
    var r = reflect(v, n);
    r.y = max(r.y, 0.02); // always leave the plane
    // Crests tilted toward the sky read lighter, troughs darker.
    let band = clamp(1.0 + dot(wr, -normalize(v.xz + vec2<f32>(1e-4))) * 0.30, 0.55, 1.45);

    // The ripples shade the surface itself too (seen from above the mirror is weak, and the
    // water would otherwise read as a flat painted sheet).
    let base = scene.rgb * (1.0 + (band - 1.0) * 0.55);

    // Schlick Fresnel, water F0 0.02.
    let cos_t = clamp(-v.y, 0.0, 1.0);
    let fres = 0.02 + 0.98 * pow(1.0 - cos_t, 5.0);

    // March: geometric steps (fine near the surface, long far out).
    var step = 0.25 + dist * 0.012;
    var t = step;
    var prev_t = 0.0;
    var hit = false;
    var hit_uv = vec2<f32>(0.0);
    var hit_t = 0.0;
    var conf = 1.0;
    // Last on-screen sample that was open SKY: a ray that escapes through it mirrors the real drawn
    // sky (the env map the water shader reflects is ~2x dimmer than the Atmosphere sky above).
    var sky_uv = vec2<f32>(-1.0);
    for (var i = 0; i < STEPS; i++) {
        if t > settings.max_dist {
            break;
        }
        let p = pos + r * t;
        let pr = project(p);
        if pr.z < 0.0 || any(pr.xy < vec2<f32>(0.0)) || any(pr.xy > vec2<f32>(1.0)) {
            break; // left the screen — nothing to mirror
        }
        let sd = depth_at(pr.xy);
        if sd <= 0.0 {
            sky_uv = pr.xy;
        } else {
            let sp = unproject(pr.xy, sd);
            let d_scene = length(sp - view.world_position);
            let d_ray = length(p - view.world_position);
            let thick = max(0.8, d_ray * 0.035);
            if d_ray > d_scene && d_ray - d_scene < thick {
                // Refine between the last miss and this step.
                var lo = prev_t;
                var hi = t;
                for (var j = 0; j < REFINE; j++) {
                    let m = 0.5 * (lo + hi);
                    let pm = pos + r * m;
                    let prm = project(pm);
                    let sdm = depth_at(prm.xy);
                    let in_front = sdm <= 0.0 || length(pm - view.world_position) <= length(unproject(prm.xy, sdm) - view.world_position);
                    if in_front { lo = m; } else { hi = m; }
                }
                let ph = project(pos + r * hi);
                let sdh = depth_at(ph.xy);
                // A ray that lands on other water (or sky) isn't a real mirror image.
                if sdh > 0.0 && abs(unproject(ph.xy, sdh).y - settings.sea_y) > 0.05 {
                    hit = true;
                    hit_uv = ph.xy;
                    hit_t = hi;
                    // Rays that only graze the back of a thin object (a trunk, a leg) are the
                    // streaky ones: trust a hit less the deeper behind the surface it landed.
                    let ph_w = pos + r * hi;
                    let behind = length(ph_w - view.world_position) - length(unproject(ph.xy, sdh) - view.world_position);
                    conf = 1.0 - smoothstep(0.35, 1.0, behind / thick);
                }
                break;
            }
        }
        prev_t = t;
        step *= 1.09;
        t += step;
    }
    // Artistic Fresnel: water F0 is 0.02, but calm swamp/river water reads as a mirror in games
    // well before grazing — lift the floor so a 45° view still shows the banks in it.
    let cos_w = (fres * 1.3 + 0.20) * settings.strength;
    if !hit {
        if sky_uv.x < 0.0 {
            // The ray left the screen (usually off the top) before crossing drawn sky: borrow the sky
            // straight above this column, so neighbouring pixels don't flip between bright sky and
            // the bare dark water.
            let top = vec2<f32>(in.uv.x, 0.03);
            if depth_at(top) > 0.0 {
                return vec4<f32>(base, scene.a);
            }
            sky_uv = top;
        }
        // Sky mirror: weaker than a scene hit (the water shader already carries some sky).
        let sky = textureSampleLevel(screen_texture, texture_sampler, clamp(sky_uv, vec2<f32>(0.0), vec2<f32>(1.0)), 0.0).rgb * MURK;
        let ws = clamp(cos_w * 0.5 * band, 0.0, 0.5);
        return vec4<f32>(mix(base, sky, ws), scene.a);
    }

    // Fade toward the screen edges (the mirrored content runs out there) and with ray length.
    let edge = min(min(hit_uv.x, 1.0 - hit_uv.x), min(hit_uv.y, 1.0 - hit_uv.y));
    let fade = smoothstep(0.0, 0.06, edge) * (1.0 - smoothstep(0.7, 1.0, length(hit_uv - in.uv) / 0.9));
    // Rough-mirror blur: real water never mirrors razor-sharp — the image smears along the view
    // (mostly vertically on screen) and more the farther the reflected object stands from the
    // surface. Five taps in a short vertical cross, widened with the ray length.
    let px = 1.0 / vec2<f32>(textureDimensions(screen_texture));
    let rad = clamp(1.5 + hit_t * 0.25, 1.5, 9.0) * px;
    var refl = textureSampleLevel(screen_texture, texture_sampler, clamp(hit_uv, vec2<f32>(0.0), vec2<f32>(1.0)), 0.0).rgb * 0.28;
    refl += textureSampleLevel(screen_texture, texture_sampler, clamp(hit_uv + vec2<f32>(0.0, rad.y), vec2<f32>(0.0), vec2<f32>(1.0)), 0.0).rgb * 0.2;
    refl += textureSampleLevel(screen_texture, texture_sampler, clamp(hit_uv - vec2<f32>(0.0, rad.y), vec2<f32>(0.0), vec2<f32>(1.0)), 0.0).rgb * 0.2;
    refl += textureSampleLevel(screen_texture, texture_sampler, clamp(hit_uv + vec2<f32>(rad.x * 0.6, rad.y * 2.0), vec2<f32>(0.0), vec2<f32>(1.0)), 0.0).rgb * 0.16;
    refl += textureSampleLevel(screen_texture, texture_sampler, clamp(hit_uv - vec2<f32>(rad.x * 0.6, rad.y * 2.0), vec2<f32>(0.0), vec2<f32>(1.0)), 0.0).rgb * 0.16;
    refl *= MURK;
    // The water shader already reflects the SKY at Fresnel strength; a hit replaces that sky with
    // the mirrored scene, so blend at (a lifted) Fresnel — calm water near grazing is a mirror.
    let w = clamp(cos_w * band, 0.0, 0.85) * fade * conf;
    return vec4<f32>(mix(base, refl, w), scene.a);
}
