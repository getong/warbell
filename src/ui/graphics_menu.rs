//! **Graphics Settings page** — the full, CS2-style settings panel: High / Ultra / Low preset chips
//! (plus a read-only **Custom** chip lit the moment any single control is hand-tweaked) over a list
//! of every meaningful graphic setting as its own control.
//!
//! Built on Bevy 0.19's **native headless widgets** (`bevy_ui_widgets`): a [`Slider`] for render
//! scale and [`Checkbox`]es for the on/off passes — the widgets own the drag/toggle/keyboard logic
//! and emit [`ValueChange`] events; we supply the themed visual tree and read the values back into
//! the [`GraphicsSettings`] / [`WindowSettings`] resources. The multi-choice rows (shadows, AA, AO,
//! terrain, resolution, display mode) use the game's own segmented-button look — a horizontal strip
//! reads better there than a vertical native radio group, and it matches the start-screen selectors.
//!
//! Opened from the pause menu (and the start screen); `Esc` or the ✕ closes it. Closing persists the
//! whole config to disk ([`quality::save_graphics_config`]).
//!
//! The panel does NOT freeze the world itself — it's only ever opened over an already-frozen screen
//! (Paused / StartScreen), so it needs no `Modal` sub-state. Its systems are ungated.

use bevy::prelude::*;
use bevy::ui::Checked;
use bevy::ui_widgets::{
    slider_self_update, Checkbox, Slider, SliderRange, SliderStep, SliderThumb, SliderValue,
    ValueChange,
};

use crate::quality::{
    save_graphics_config, AaLevel, AoLevel, GraphicsQuality, GraphicsSettings, ShadowLevel,
    TerrainDetail, WindowSettings,
};

use super::fonts::{label, UiFonts};
use super::theme::*;
use super::widgets::{self, border};

/// Open/closed flag for the Settings page. Flipped true by the pause-menu / start-screen buttons,
/// false by `Esc` or the ✕. The overlay is reconciled from this each frame.
#[derive(Resource, Default)]
pub struct GraphicsMenuOpen(pub bool);

pub struct GraphicsMenuPlugin;

impl Plugin for GraphicsMenuPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<GraphicsMenuOpen>()
            // Headless-widget value plumbing (global observers — only our widgets emit these events).
            .add_observer(slider_self_update) // keep SliderValue tracking the drag
            .add_observer(on_slider_change)
            .add_observer(on_toggle_change)
            .add_systems(Startup, stage_open) // FOREST_GFXMENU=1 opens the page at boot (shot harness)
            .add_systems(
                Update,
                (
                    sync_overlay, // spawn / despawn the panel from GraphicsMenuOpen
                    (menu_buttons, menu_keys, sync_segments, sync_controls, sync_slider_visual)
                        .run_if(menu_is_open),
                ),
            );
    }
}

fn menu_is_open(open: Res<GraphicsMenuOpen>) -> bool {
    open.0
}

/// `FOREST_GFXMENU=1`: open the Settings page at boot so the screenshot harness can frame it.
fn stage_open(mut open: ResMut<GraphicsMenuOpen>) {
    if std::env::var("FOREST_GFXMENU").is_ok() {
        open.0 = true;
    }
}

// ── Markers ────────────────────────────────────────────────────────────────────────────────────

#[derive(Component)]
struct GfxMenuRoot;
#[derive(Component)]
struct GfxCloseBtn;

/// A boolean (Checkbox) setting — identifies which field the toggle drives.
#[derive(Component, Clone, Copy, PartialEq)]
enum ToggleId {
    Bloom,
    Dof,
    Outline,
    GodRays,
    Vsync,
}
/// Tags the inner "fill" node of a checkbox so we can show/hide the check tick.
#[derive(Component)]
struct CheckFill;
/// The render-scale slider (the only slider on the page).
#[derive(Component)]
struct RenderScaleSlider;
/// Live numeric readout next to the render-scale slider (e.g. "60%").
#[derive(Component)]
struct RenderScaleLabel;

/// One segmented-button choice. The active value is highlighted by [`sync_segments`]; a click sets
/// the corresponding setting (and flips the preset to `Custom` for render-pipeline settings).
#[derive(Component, Clone, Copy, PartialEq)]
enum Seg {
    Preset(GraphicsQuality),
    Shadows(ShadowLevel),
    Aa(AaLevel),
    Ao(AoLevel),
    Terrain(TerrainDetail),
    Resolution(Option<[u32; 2]>),
    Fullscreen(bool),
}

/// The resolutions offered in the dropdown (plus a "Native" = no override entry, prepended).
const RES_CHOICES: &[[u32; 2]] =
    &[[1280, 720], [1600, 900], [1920, 1080], [2560, 1440], [3840, 2160]];

// ── Overlay lifecycle ────────────────────────────────────────────────────────────────────────

/// Spawn the panel when the menu opens; despawn (and persist the config) when it closes.
fn sync_overlay(
    open: Res<GraphicsMenuOpen>,
    existing: Query<Entity, With<GfxMenuRoot>>,
    fonts: Res<UiFonts>,
    quality: Res<GraphicsQuality>,
    settings: Res<GraphicsSettings>,
    window: Res<WindowSettings>,
    mut commands: Commands,
) {
    let is_up = !existing.is_empty();
    if open.0 && !is_up {
        spawn_panel(&mut commands, &fonts, &quality, &settings, &window);
    } else if !open.0 && is_up {
        for e in &existing {
            commands.entity(e).despawn();
        }
        // Persist on close — a natural commit point (not every slider tick).
        save_graphics_config(&quality, &settings, &window);
    }
}

/// Esc (or the ✕, handled in `menu_buttons`) closes the page.
fn menu_keys(keys: Res<ButtonInput<KeyCode>>, mut open: ResMut<GraphicsMenuOpen>) {
    if keys.just_pressed(KeyCode::Escape) {
        open.0 = false;
    }
}

// ── Panel construction ───────────────────────────────────────────────────────────────────────

fn spawn_panel(
    commands: &mut Commands,
    fonts: &UiFonts,
    quality: &GraphicsQuality,
    settings: &GraphicsSettings,
    window: &WindowSettings,
) {
    commands
        .spawn((
            Node {
                position_type: PositionType::Absolute,
                width: Val::Percent(100.0),
                height: Val::Percent(100.0),
                align_items: AlignItems::Center,
                justify_content: JustifyContent::Center,
                ..default()
            },
            BackgroundColor(SCRIM),
            GlobalZIndex(120), // above the pause menu (50) and start screen
            GfxMenuRoot,
        ))
        .with_children(|root| {
            root.spawn((
                Node {
                    flex_direction: FlexDirection::Column,
                    align_items: AlignItems::Stretch,
                    width: Val::Px(520.0),
                    max_height: Val::Percent(88.0),
                    padding: UiRect::axes(Val::Px(28.0), Val::Px(22.0)),
                    border: border(2.0),
                    border_radius: radius(R_PANEL),
                    row_gap: Val::Px(4.0),
                    overflow: Overflow::scroll_y(),
                    ..default()
                },
                widgets::card_paint(),
            ))
            .with_children(|c| {
                // ── Header ──
                c.spawn(Node {
                    flex_direction: FlexDirection::Row,
                    justify_content: JustifyContent::SpaceBetween,
                    align_items: AlignItems::Center,
                    margin: UiRect::bottom(Val::Px(8.0)),
                    ..default()
                })
                .with_children(|h| {
                    h.spawn(label(&fonts.display, "GRAPHICS", 26.0, GOLD));
                    widgets::close_button(h, &fonts.bold, GfxCloseBtn, false);
                });

                // ── Preset chips: High / Ultra / Low / Custom ──
                seg_row(
                    c,
                    fonts,
                    "PRESET",
                    &[
                        ("Low", Seg::Preset(GraphicsQuality::Low)),
                        ("High", Seg::Preset(GraphicsQuality::High)),
                        ("Ultra", Seg::Preset(GraphicsQuality::Ultra)),
                        ("Custom", Seg::Preset(GraphicsQuality::Custom)),
                    ],
                    quality_seg_active(*quality),
                );

                divider(c);

                // ── Display group (window settings) ──
                seg_row(
                    c,
                    fonts,
                    "DISPLAY",
                    &[("Windowed", Seg::Fullscreen(false)), ("Fullscreen", Seg::Fullscreen(true))],
                    Seg::Fullscreen(window.fullscreen),
                );
                // Resolution: "Native" (no override) + the common modes.
                {
                    let mut opts: Vec<(String, Seg)> = vec![("Native".into(), Seg::Resolution(None))];
                    for r in RES_CHOICES {
                        opts.push((format!("{}×{}", r[0], r[1]), Seg::Resolution(Some(*r))));
                    }
                    let refs: Vec<(&str, Seg)> = opts.iter().map(|(s, v)| (s.as_str(), *v)).collect();
                    seg_row(c, fonts, "RESOLUTION", &refs, Seg::Resolution(window.resolution));
                }
                check_row(c, fonts, "VSync", ToggleId::Vsync, window.vsync);

                divider(c);

                // ── Render-pipeline group (GraphicsSettings) ──
                slider_row(c, fonts, "Render scale", settings.render_scale);
                seg_row(
                    c,
                    fonts,
                    "Shadows",
                    &[
                        ("Off", Seg::Shadows(ShadowLevel::Off)),
                        ("Low", Seg::Shadows(ShadowLevel::Low)),
                        ("Med", Seg::Shadows(ShadowLevel::Medium)),
                        ("High", Seg::Shadows(ShadowLevel::High)),
                    ],
                    Seg::Shadows(settings.shadows),
                );
                seg_row(
                    c,
                    fonts,
                    "Anti-aliasing",
                    &[
                        ("Off", Seg::Aa(AaLevel::Off)),
                        ("Low", Seg::Aa(AaLevel::Low)),
                        ("High", Seg::Aa(AaLevel::High)),
                        ("Ultra", Seg::Aa(AaLevel::Ultra)),
                    ],
                    Seg::Aa(settings.antialias),
                );
                seg_row(
                    c,
                    fonts,
                    "Ambient occlusion",
                    &[
                        ("Off", Seg::Ao(AoLevel::Off)),
                        ("Medium", Seg::Ao(AoLevel::Medium)),
                        ("Ultra", Seg::Ao(AoLevel::Ultra)),
                    ],
                    Seg::Ao(settings.ssao),
                );
                seg_row(
                    c,
                    fonts,
                    "Terrain detail",
                    &[
                        ("Low", Seg::Terrain(TerrainDetail::Low)),
                        ("High", Seg::Terrain(TerrainDetail::High)),
                        ("Ultra", Seg::Terrain(TerrainDetail::Ultra)),
                    ],
                    Seg::Terrain(settings.terrain),
                );
                check_row(c, fonts, "Bloom", ToggleId::Bloom, settings.bloom);
                check_row(c, fonts, "Depth of field", ToggleId::Dof, settings.depth_of_field);
                check_row(c, fonts, "Outline", ToggleId::Outline, settings.outline);
                check_row(c, fonts, "God rays", ToggleId::GodRays, settings.god_rays);

                c.spawn((
                    label(&fonts.regular, "Esc to close   ·   choices are saved", 12.0, GREY),
                    Node { margin: UiRect::top(Val::Px(10.0)), ..default() },
                ));
            });
        });
}

/// A labelled row whose right side is a horizontal segmented control. `active` is the value to
/// highlight at spawn (kept in sync afterwards by [`sync_segments`]).
fn seg_row(
    p: &mut bevy::ecs::relationship::RelatedSpawnerCommands<ChildOf>,
    fonts: &UiFonts,
    title: &str,
    options: &[(&str, Seg)],
    active: Seg,
) {
    p.spawn(row_node()).with_children(|r| {
        r.spawn(label(&fonts.semibold, title, 14.0, TEXT));
        r.spawn((
            Node {
                flex_direction: FlexDirection::Row,
                padding: UiRect::all(Val::Px(3.0)),
                column_gap: Val::Px(2.0),
                border: border(1.0),
                border_radius: radius(8.0),
                ..default()
            },
            BackgroundColor(rgba(24, 19, 13, 0.72)),
            BorderColor::all(BORDER_SOFT),
        ))
        .with_children(|seg| {
            for (txt, val) in options {
                let on = *val == active;
                seg.spawn((
                    Button,
                    Interaction::default(),
                    Node {
                        padding: UiRect::axes(Val::Px(11.0), Val::Px(5.0)),
                        align_items: AlignItems::Center,
                        justify_content: JustifyContent::Center,
                        border_radius: radius(6.0),
                        ..default()
                    },
                    BackgroundColor(if on { GOLD_DEEP } else { Color::NONE }),
                    *val,
                ))
                .with_children(|b| {
                    b.spawn((
                        label(&fonts.semibold, *txt, 12.5, if on { INK } else { TEXT_FAINT }),
                        SegLabel,
                    ));
                });
            }
        });
    });
}

/// Tags a segment button's text so [`sync_segments`] can recolour it with the button.
#[derive(Component)]
struct SegLabel;

/// A labelled row with a native [`Checkbox`] on the right.
fn check_row(
    p: &mut bevy::ecs::relationship::RelatedSpawnerCommands<ChildOf>,
    fonts: &UiFonts,
    title: &str,
    id: ToggleId,
    on: bool,
) {
    p.spawn(row_node()).with_children(|r| {
        r.spawn(label(&fonts.semibold, title, 14.0, TEXT));
        // The checkbox: a 22px box; the inner fill shows the tick when Checked. The widget receives
        // clicks via the UI picking system (Pointer<Click> bubbling), not Button/Interaction.
        let mut cb = r.spawn((
            Checkbox,
            id,
            Node {
                width: Val::Px(22.0),
                height: Val::Px(22.0),
                align_items: AlignItems::Center,
                justify_content: JustifyContent::Center,
                border: border(2.0),
                border_radius: radius(5.0),
                ..default()
            },
            BackgroundColor(rgba(24, 19, 13, 0.72)),
            BorderColor::all(if on { GOLD_NOTCH } else { BORDER_SOFT }),
        ));
        if on {
            cb.insert(Checked);
        }
        cb.with_children(|b| {
            b.spawn((
                Node { width: Val::Px(12.0), height: Val::Px(12.0), border_radius: radius(3.0), ..default() },
                BackgroundColor(if on { GREEN } else { Color::NONE }),
                CheckFill,
            ));
        });
    });
}

/// A labelled row with the native render-scale [`Slider`] + a live percentage readout.
fn slider_row(
    p: &mut bevy::ecs::relationship::RelatedSpawnerCommands<ChildOf>,
    fonts: &UiFonts,
    title: &str,
    value: f32,
) {
    p.spawn(row_node()).with_children(|r| {
        r.spawn(label(&fonts.semibold, title, 14.0, TEXT));
        r.spawn(Node {
            flex_direction: FlexDirection::Row,
            align_items: AlignItems::Center,
            column_gap: Val::Px(10.0),
            ..default()
        })
        .with_children(|right| {
            // Percentage readout.
            right.spawn((
                label(&fonts.bold, format!("{}%", (value * 100.0).round() as i32), 13.0, GOLD),
                RenderScaleLabel,
                Node { width: Val::Px(40.0), ..default() },
            ));
            // The slider track (its own width is the draggable extent).
            right
                .spawn((
                    Slider::default(),
                    SliderValue(value),
                    SliderRange::new(0.3, 1.0),
                    SliderStep(0.05), // 5% increments (default step is 1.0 → only the endpoints)
                    RenderScaleSlider,
                    Node {
                        width: Val::Px(170.0),
                        height: Val::Px(18.0),
                        align_items: AlignItems::Center,
                        ..default()
                    },
                ))
                .with_children(|s| {
                    // Rail.
                    s.spawn((
                        Node {
                            position_type: PositionType::Absolute,
                            left: Val::Px(0.0),
                            right: Val::Px(0.0),
                            top: Val::Px(7.0),
                            height: Val::Px(4.0),
                            border_radius: radius(2.0),
                            ..default()
                        },
                        BackgroundColor(rgba(24, 19, 13, 0.85)),
                    ));
                    // Thumb (positioned by sync_slider_visual).
                    s.spawn((
                        SliderThumb,
                        Node {
                            position_type: PositionType::Absolute,
                            width: Val::Px(14.0),
                            height: Val::Px(14.0),
                            top: Val::Px(2.0),
                            left: Val::Percent((value - 0.3) / 0.7 * 100.0),
                            margin: UiRect::left(Val::Px(-7.0)),
                            border_radius: radius(7.0),
                            ..default()
                        },
                        BackgroundColor(GOLD),
                    ));
                });
        });
    });
}

fn row_node() -> Node {
    Node {
        flex_direction: FlexDirection::Row,
        justify_content: JustifyContent::SpaceBetween,
        align_items: AlignItems::Center,
        min_height: Val::Px(34.0),
        column_gap: Val::Px(16.0),
        ..default()
    }
}

fn divider(p: &mut bevy::ecs::relationship::RelatedSpawnerCommands<ChildOf>) {
    p.spawn((
        Node { height: Val::Px(1.0), margin: UiRect::vertical(Val::Px(6.0)), ..default() },
        BackgroundColor(BORDER_SOFT),
    ));
}

/// Which preset chip is "active" for highlighting — maps the live quality onto a `Seg::Preset`.
fn quality_seg_active(q: GraphicsQuality) -> Seg {
    Seg::Preset(q)
}

// ── Interaction ────────────────────────────────────────────────────────────────────────────────

/// Segmented-button clicks + the ✕ close button.
#[allow(clippy::type_complexity, clippy::too_many_arguments)]
fn menu_buttons(
    segs: Query<(&Interaction, &Seg), Changed<Interaction>>,
    close: Query<&Interaction, (Changed<Interaction>, With<GfxCloseBtn>)>,
    mut open: ResMut<GraphicsMenuOpen>,
    mut quality: ResMut<GraphicsQuality>,
    mut settings: ResMut<GraphicsSettings>,
    mut window: ResMut<WindowSettings>,
) {
    for i in &close {
        if *i == Interaction::Pressed {
            open.0 = false;
        }
    }
    for (i, seg) in &segs {
        if *i != Interaction::Pressed {
            continue;
        }
        match *seg {
            // Named preset chips drive the quality resource (fill + apply happen in quality.rs);
            // the read-only Custom chip does nothing on click.
            Seg::Preset(GraphicsQuality::Custom) => {}
            Seg::Preset(q) => *quality = q,
            Seg::Shadows(l) => set_custom(&mut quality, || settings.shadows = l),
            Seg::Aa(l) => set_custom(&mut quality, || settings.antialias = l),
            Seg::Ao(l) => set_custom(&mut quality, || settings.ssao = l),
            Seg::Terrain(l) => set_custom(&mut quality, || settings.terrain = l),
            // Window settings are independent of the render preset (presets don't define them).
            Seg::Resolution(r) => window.resolution = r,
            Seg::Fullscreen(fs) => window.fullscreen = fs,
        }
    }
}

/// Apply a render-setting mutation and flip the active preset to `Custom`.
fn set_custom(quality: &mut GraphicsQuality, mutate: impl FnOnce()) {
    mutate();
    *quality = GraphicsQuality::Custom;
}

/// Native checkbox value changed → write the field, flip the check tick, and (for render settings)
/// flip the preset to `Custom`. Global observer; ignores non-graphics checkboxes.
fn on_toggle_change(
    ev: On<ValueChange<bool>>,
    q: Query<&ToggleId>,
    children: Query<&Children>,
    mut fills: Query<&mut BackgroundColor, With<CheckFill>>,
    mut borders: Query<&mut BorderColor>,
    mut commands: Commands,
    mut settings: ResMut<GraphicsSettings>,
    mut window: ResMut<WindowSettings>,
    mut quality: ResMut<GraphicsQuality>,
) {
    let src = ev.source;
    let Ok(id) = q.get(src) else { return };
    let on = ev.value;

    // Drive the widget's Checked state + the tick + box border.
    if on {
        commands.entity(src).insert(Checked);
    } else {
        commands.entity(src).remove::<Checked>();
    }
    if let Ok(mut bd) = borders.get_mut(src) {
        *bd = BorderColor::all(if on { GOLD_NOTCH } else { BORDER_SOFT });
    }
    for d in children.iter_descendants(src) {
        if let Ok(mut bg) = fills.get_mut(d) {
            bg.0 = if on { GREEN } else { Color::NONE };
        }
    }

    match *id {
        ToggleId::Bloom => set_custom(&mut quality, || settings.bloom = on),
        ToggleId::Dof => set_custom(&mut quality, || settings.depth_of_field = on),
        ToggleId::Outline => set_custom(&mut quality, || settings.outline = on),
        ToggleId::GodRays => set_custom(&mut quality, || settings.god_rays = on),
        ToggleId::Vsync => window.vsync = on, // window setting — independent of the render preset
    }
}

/// Native render-scale slider committed (drag released / arrow key) → write `render_scale`. Only on
/// `is_final` so a drag doesn't reallocate the render target every frame (mid-drag we just move the
/// thumb + readout). Global observer; ignores other sliders.
fn on_slider_change(
    ev: On<ValueChange<f32>>,
    q: Query<(), With<RenderScaleSlider>>,
    mut settings: ResMut<GraphicsSettings>,
    mut quality: ResMut<GraphicsQuality>,
) {
    if q.get(ev.source).is_err() || !ev.is_final {
        return;
    }
    let v = (ev.value * 100.0).round() / 100.0; // snap to whole-percent steps
    if (settings.render_scale - v).abs() > f32::EPSILON {
        set_custom(&mut quality, || settings.render_scale = v);
    }
}

// ── Live visual sync ─────────────────────────────────────────────────────────────────────────

/// Recolour the segmented buttons so the active value (per the live resources) is highlighted —
/// keeps the preset chips (incl. the Custom chip) and the multi-choice rows correct after a chip
/// click, an F10 cycle, or any cross-control change.
fn sync_segments(
    quality: Res<GraphicsQuality>,
    settings: Res<GraphicsSettings>,
    window: Res<WindowSettings>,
    mut segs: Query<(&Seg, &mut BackgroundColor, &Children)>,
    mut labels: Query<&mut TextColor, With<SegLabel>>,
) {
    for (seg, mut bg, kids) in &mut segs {
        let on = match *seg {
            Seg::Preset(q) => *quality == q,
            Seg::Shadows(l) => settings.shadows == l,
            Seg::Aa(l) => settings.antialias == l,
            Seg::Ao(l) => settings.ssao == l,
            Seg::Terrain(l) => settings.terrain == l,
            Seg::Resolution(r) => window.resolution == r,
            Seg::Fullscreen(fs) => window.fullscreen == fs,
        };
        let want = if on { GOLD_DEEP } else { Color::NONE };
        if bg.0 != want {
            bg.0 = want;
        }
        for k in kids {
            if let Ok(mut tc) = labels.get_mut(*k) {
                tc.0 = if on { INK } else { TEXT_FAINT };
            }
        }
    }
}

/// When the settings change underneath the open panel (a preset chip filled them, or a cross-control
/// edit), push the new values into the native widgets so the slider + checkboxes follow. Gated on a
/// resource change so it never fights an in-progress drag (which only commits on release).
#[allow(clippy::type_complexity)]
fn sync_controls(
    settings: Res<GraphicsSettings>,
    window: Res<WindowSettings>,
    mut commands: Commands,
    slider: Query<(Entity, &SliderValue), With<RenderScaleSlider>>,
    toggles: Query<(Entity, &ToggleId, Has<Checked>, &Children)>,
    mut fills: Query<&mut BackgroundColor, With<CheckFill>>,
    mut borders: Query<&mut BorderColor>,
    children: Query<&Children>,
) {
    if !settings.is_changed() && !window.is_changed() {
        return;
    }
    // Slider: re-seat its value (immutable component → insert). The visual system reacts to the change.
    if let Ok((e, cur)) = slider.single() {
        if (cur.0 - settings.render_scale).abs() > f32::EPSILON {
            commands.entity(e).insert(SliderValue(settings.render_scale));
        }
    }
    // Checkboxes: reconcile Checked + the tick/border to the model.
    for (e, id, checked, _) in &toggles {
        let want = match *id {
            ToggleId::Bloom => settings.bloom,
            ToggleId::Dof => settings.depth_of_field,
            ToggleId::Outline => settings.outline,
            ToggleId::GodRays => settings.god_rays,
            ToggleId::Vsync => window.vsync,
        };
        if want != checked {
            if want {
                commands.entity(e).insert(Checked);
            } else {
                commands.entity(e).remove::<Checked>();
            }
        }
        if let Ok(mut bd) = borders.get_mut(e) {
            *bd = BorderColor::all(if want { GOLD_NOTCH } else { BORDER_SOFT });
        }
        for d in children.iter_descendants(e) {
            if let Ok(mut bg) = fills.get_mut(d) {
                bg.0 = if want { GREEN } else { Color::NONE };
            }
        }
    }
}

/// Move the slider thumb + update the percentage readout whenever the slider value changes (drag,
/// keyboard, or a programmatic re-seat from [`sync_controls`]). There's only the one render-scale
/// slider; its `SliderThumb` is a direct child.
fn sync_slider_visual(
    sliders: Query<(&SliderValue, &SliderRange, &Children), (With<RenderScaleSlider>, Changed<SliderValue>)>,
    mut thumbs: Query<&mut Node, With<SliderThumb>>,
    mut readout: Query<&mut Text, With<RenderScaleLabel>>,
) {
    for (val, range, kids) in &sliders {
        let pos = range.thumb_position(val.0).clamp(0.0, 1.0);
        for k in kids {
            if let Ok(mut node) = thumbs.get_mut(*k) {
                node.left = Val::Percent(pos * 100.0);
            }
        }
        if let Ok(mut t) = readout.single_mut() {
            **t = format!("{}%", (val.0 * 100.0).round() as i32);
        }
    }
}
