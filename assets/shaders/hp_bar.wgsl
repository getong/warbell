// World-space enemy HP bar (`combat_fx.rs`) — the whole bar in ONE opaque, unlit quad: a hairline
// dark rim, a 1px bevelled iron frame, a near-black channel, a deep blood-red fill with a soft
// vertical gradient, and a pale-amber "damage trail" ghost that lingers where the last blow landed
// and then drains (the Souls read: you SEE how much a hit took).
//
// Per-bar state rides the instance's `MeshTag` (packed by `combat_fx::pack_bar_tag`), NOT a
// per-bar material: every bar shares one material + one quad, so the renderer instances the whole
// horde's bars into a single draw and a damage tick only touches one u32.
//   bits  0..11  hp fraction     (0..4095)
//   bits 12..23  trail fraction  (0..4095, >= hp)
//   bits 24..31  hit flash       (0..255, decays over ~0.3s after a blow)
//
// Opaque on purpose: the post stack (bokeh DoF, haze, outline) reads the PREPASS depth, which a
// blended quad never writes — a translucent bar over the sky would be bokeh-smeared and hazed like
// the horizon behind it. Opaque writes its own depth, so the bar stays pin-sharp at any range.
//
// All widths are in SCREEN PIXELS (from the uv derivatives), box-filtered over one pixel, so the
// rim/frame stay exactly 1px crisp whatever distance or size the CPU side gives the quad.

#import bevy_pbr::{
    forward_io::VertexOutput,
    mesh_functions,
}

struct HpBarStyle {
    fill_hi: vec4<f32>,  // fill colour at the channel's top edge (linear)
    fill_lo: vec4<f32>,  // fill colour at the bottom edge (linear)
    trail: vec4<f32>,    // damage-trail ghost (linear)
    frame: vec4<f32>,    // frame line, lit (top) edge (linear); the bottom edge is a darker cut of it
    empty: vec4<f32>,    // drained channel (linear)
};
@group(#{MATERIAL_BIND_GROUP}) @binding(0) var<uniform> style: HpBarStyle;

// Coverage of the pixel centred at `d` (1px wide) by the interval [a, b] — an exact box filter for
// an axis-aligned edge, so a sub-pixel bar position antialiases instead of popping a row on/off.
fn band(d: f32, a: f32, b: f32) -> f32 {
    return clamp(min(d + 0.5, b) - max(d - 0.5, a), 0.0, 1.0);
}

@fragment
fn fragment(in: VertexOutput) -> @location(0) vec4<f32> {
    let tag = mesh_functions::get_tag(in.instance_index);
    let hp = f32(tag & 0xfffu) / 4095.0;
    let trail = max(f32((tag >> 12u) & 0xfffu) / 4095.0, hp);
    let flash = f32((tag >> 24u) & 0xffu) / 255.0;

    // Pixel space: uv advances `duv` per screen pixel, so 1/duv is the quad's on-screen size.
    let duv = max(fwidth(in.uv), vec2<f32>(1.0e-5));
    let size = 1.0 / duv;
    let px = in.uv * size; // (0,0) = top-left corner, in pixels

    // Distance (px) in from the nearest outer edge, and from the top / bottom edges.
    let dx = min(px.x, size.x - px.x);
    let dy = min(px.y, size.y - px.y);
    let d = min(dx, dy);

    // ── Channel (everything inside rim + frame) ──
    let inset = 2.0;
    let ch_w = max(size.x - inset * 2.0, 1.0);
    let ch_h = max(size.y - inset * 2.0, 1.0);
    let cx = px.x - inset;              // px along the channel
    let cy = clamp((px.y - inset) / ch_h, 0.0, 1.0); // 0 top → 1 bottom

    // Drained channel: near-black, a breath lighter at the top so it reads as a recessed slot.
    var col = mix(style.empty.rgb * 1.6, style.empty.rgb, cy);

    // Trail (pale amber) from hp → trail; brightens on the hit frame, settles as it holds.
    let trail_px = trail * ch_w;
    let hp_px = hp * ch_w;
    let in_trail = clamp(trail_px - (cx - 0.5), 0.0, 1.0);
    let trail_col = mix(style.trail.rgb, style.trail.rgb * 1.55 + vec3<f32>(0.04), flash)
        * mix(1.0, 0.82, cy);
    col = mix(col, trail_col, in_trail);

    // Fill: deep blood red, a soft top→bottom gradient plus a faint lit top row (a rounded tube,
    // not a flat swatch). Lifted toward a hot red for a beat on a fresh hit.
    let in_fill = clamp(hp_px - (cx - 0.5), 0.0, 1.0);
    var fill_col = mix(style.fill_hi.rgb, style.fill_lo.rgb, smoothstep(0.0, 1.0, cy));
    let top_row = band(px.y - inset, 0.0, 1.0);
    fill_col = mix(fill_col, style.fill_hi.rgb * 1.45, top_row * 0.5);
    fill_col = mix(fill_col, style.fill_hi.rgb * 1.7 + vec3<f32>(0.03, 0.006, 0.004), flash * 0.45);
    col = mix(col, fill_col, in_fill);

    // A 1px darker seam at the fill's leading edge, so fill vs trail separate cleanly.
    let seam = band(cx, hp_px, hp_px + 1.0) * step(hp_px + 0.5, trail_px) * step(0.5, hp_px);
    col = mix(col, col * 0.45, seam);

    // ── Frame: 1px iron line, lit on top, cut darker along the bottom (a hint of bevel) ──
    let frame_w = band(d, 1.0, 2.0);
    let bottom = step(size.y * 0.5, px.y) * step(dy, dx); // the frame pixels on the bottom edge
    let frame_col = mix(style.frame.rgb, style.frame.rgb * 0.42, bottom);
    col = mix(col, frame_col, frame_w);

    // ── Rim: 1px near-black outer line — separates the bar from any background, day or night ──
    let rim_w = band(d, 0.0, 1.0);
    col = mix(col, style.empty.rgb * 0.35, rim_w);

    return vec4<f32>(col, 1.0);
}
