// Cloud sky (`src/clouds.rs`) — a high stratocumulus / cumulus deck painted behind the world.
//
// Geometry: one unit sphere whose vertices the VERTEX stage re-centres on the camera every frame
// (`view.world_position + dir * 100`) and pins to the FAR plane (reverse-Z clip z = 0). Drawn in
// the transparent pass (after Bevy's `Atmosphere` sky), it depth-tests GreaterEqual against the
// cleared depth: it only ever lands on sky pixels and can never cover terrain, the town, a unit or
// a tower — whatever the camera height. No CPU transform update, no per-frame material writes.
//
// Shading: each fragment intersects its view ray with a virtual horizontal cloud deck at
// `params.shape.x` world units (far above any camera pose — the deck isn't geometry, so the 230u
// far plane doesn't clip it) and samples the baked Perlin-Worley texture there, drifted by
// `globals.time`. Lit by EVERY directional light in the view uniform (sun by day, moon by night —
// whatever `scene::advance_sky` set this frame) with a 2D self-shadow tap toward each light, a
// Henyey-Greenstein silver lining, a multiple-scatter floor, and the live ambient skylight. A sun
// just below the ground horizon still lights the deck from below (the pink/orange dusk underlight).
// Distance fades the deck out into the Atmosphere's own horizon haze.

#import bevy_pbr::mesh_view_bindings::{view, lights, globals}

struct CloudParams {
    // x deck height (world y) · y texture tile (world units) · z coverage 0..1 · w max opacity
    shape: vec4<f32>,
    // xy wind (world units / s) · z detail tile (world units) · w horizon fade distance
    wind: vec4<f32>,
};
@group(#{MATERIAL_BIND_GROUP}) @binding(0) var<uniform> params: CloudParams;
@group(#{MATERIAL_BIND_GROUP}) @binding(1) var noise_tex: texture_2d<f32>;
@group(#{MATERIAL_BIND_GROUP}) @binding(2) var noise_samp: sampler;

struct Vin {
    @location(0) position: vec3<f32>,
};
struct Vout {
    @builtin(position) clip: vec4<f32>,
    @location(0) dir: vec3<f32>,
};

@vertex
fn vertex(v: Vin) -> Vout {
    var o: Vout;
    let d = normalize(v.position);
    var c = view.clip_from_world * vec4<f32>(view.world_position + d * 100.0, 1.0);
    c.z = 0.0; // reverse-Z far plane: behind everything, only fills cleared (sky) depth
    o.clip = c;
    o.dir = d;
    return o;
}

const PI: f32 = 3.14159265;

fn hg(cos_t: f32, g: f32) -> f32 {
    let g2 = g * g;
    return (1.0 - g2) / (4.0 * PI * pow(max(1.0 + g2 - 2.0 * g * cos_t, 1e-4), 1.5));
}

// Cloud density at a deck position (world xz, already wind-shifted).
fn deck_density(p: vec2<f32>, detail_p: vec2<f32>) -> f32 {
    let tile = params.shape.y;
    let n = textureSample(noise_tex, noise_samp, p / tile);
    // Large-scale "weather": a slower, differently-scaled coverage field so banks of cloud and
    // open sky alternate over kilometres instead of repeating every tile.
    let w = textureSample(noise_tex, noise_samp, p / (tile * 3.7) + vec2<f32>(0.37, 0.11)).b;
    let coverage = clamp(params.shape.z + (w - 0.5) * 0.85, 0.0, 1.0);
    var d = clamp((n.r - (1.0 - coverage)) / max(coverage, 0.05), 0.0, 1.0);
    // Erode the edges with the Worley detail: wispy fringes and little satellite puffs.
    let det = textureSample(noise_tex, noise_samp, detail_p / params.wind.z).g;
    let ero = (1.0 - det) * 0.42;
    d = clamp((d - ero) / (1.0 - ero), 0.0, 1.0);
    return d;
}

@fragment
fn fragment(in: Vout) -> @location(0) vec4<f32> {
    let dir = normalize(in.dir);
    let cam = view.world_position;
    let height = params.shape.x;

    // Ray → deck. Rays below a few degrees are clamped (and faded out below) so the sample
    // position stays finite; everything here is branch-free so the texture taps stay in uniform
    // control flow (implicit-derivative mips).
    let up = max(dir.y, 0.012);
    let t = max(height - cam.y, 1.0) / up;
    let hit = cam.xz + dir.xz * t;
    let drift = params.wind.xy * globals.time;
    let p = hit + drift;
    let pd = hit + drift * 1.45 + vec2<f32>(91.0, -47.0); // detail shears a little faster

    let d = deck_density(p, pd);

    // ── Lighting ──
    var col = vec3<f32>(0.0);
    for (var i = 0u; i < lights.n_directional_lights; i = i + 1u) {
        let light = lights.directional_lights[i];
        let l = light.direction_to_light;
        // The deck is ~600u up: a sun a few degrees below the GROUND horizon still reaches it
        // (dusk underlight); deeper than that it's in the Earth's shadow.
        let vis = smoothstep(-0.12, 0.03, l.y);
        // Uniform per-light skip (moon by day, sun deep at night): keeps the taps in uniform
        // control flow while saving the shadow samples for lights that contribute nothing.
        if vis <= 0.0 || max(light.color.r, max(light.color.g, light.color.b)) < 1.0 {
            continue;
        }
        // 2D self-shadow: how much cloud lies between this point and the light along the deck.
        let reach = l.xz / max(abs(l.y), 0.2) * 70.0;
        let dl = deck_density(p + reach, pd + reach);
        let dl2 = deck_density(p + reach * 2.6, pd + reach * 2.6);
        let tau = d * 1.6 + dl * 1.5 + dl2 * 0.9;
        let trans = exp(-tau);
        let cos_t = dot(dir, l);
        // Forward lobe = the silver lining on thin edges toward the sun; back lobe keeps the
        // sun-opposite sky readable. Normalised so an isotropic cloud ≈ albedo·E/π.
        let phase = (0.55 * hg(cos_t, 0.65) + 0.45 * hg(cos_t, -0.15)) * 4.0 * PI;
        // Multiple scattering floor: thick cores go grey, never black.
        let ms = 0.28 * exp(-d * 0.9) + 0.10;
        let radiance = light.color.rgb / PI * vis * (trans * phase + ms);
        col = col + radiance;
    }
    // Skylight on the underside — the live ambient fill (cool by day, moonlit blue by night).
    col = col + lights.ambient_color.rgb * (1.9 - 0.9 * d);
    col = col * view.exposure;

    // ── Coverage → alpha, faded into the horizon haze ──
    var a = smoothstep(0.0, 0.32, d) * params.shape.w;
    let far_fade = exp(-t / params.wind.w) * (1.0 - smoothstep(params.wind.w * 2.2, params.wind.w * 4.0, t));
    let low_fade = smoothstep(0.015, 0.09, dir.y);
    // Deck fades away if a camera ever climbs to it (no camera pose does — belt and braces).
    let above = 1.0 - smoothstep(height * 0.75, height * 0.95, cam.y);
    a = a * far_fade * low_fade * above;
    // Far cloud also loses contrast (aerial perspective): lift it toward its own mean tone.
    let haze = 1.0 - far_fade;
    col = mix(col, col * 0.75 + vec3<f32>(dot(col, vec3<f32>(0.3333))) * 0.25, haze);
    return vec4<f32>(col, a);
}
