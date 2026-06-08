//! Live debug-tuning panel — an egui window (toggle with **F1**) for tweaking the look at
//! runtime instead of editing constants / env vars and restarting. Mirrors the TS game's
//! `leva` panel. Hidden by default so it never shows in screenshots or normal viewing.
//!
//! Each frame (when open) it reads the current values straight off the live
//! components/resources, renders sliders, and writes any changes back the same frame — no
//! separate state to keep in sync. Nothing is persisted; values reset on restart.
//!
//! Self-contained: the only thing it needs from elsewhere is read/write access to existing
//! components ([`DistanceFog`], [`DepthBlur`](crate::depth_blur::DepthBlur), [`Bloom`]) and
//! resources ([`SkyClock`](crate::scene::SkyClock), [`GlobalAmbientLight`],
//! [`AudioConfig`](crate::audio::AudioConfig), [`GlobalVolume`]).

use bevy::anti_alias::contrast_adaptive_sharpening::ContrastAdaptiveSharpening;
use bevy::audio::{GlobalVolume, Volume};
use bevy::camera::Exposure;
use bevy::light::{FogVolume, VolumetricFog};
use bevy::pbr::{DistanceFog, FogFalloff};
use bevy::post_process::bloom::Bloom;
use bevy::prelude::*;
use bevy::render::view::ColorGrading;
use bevy_egui::{egui, EguiContexts, EguiPlugin, EguiPrimaryContextPass};

use crate::audio::AudioConfig;
use crate::depth_blur::DepthBlur;
use crate::scene::{SkyClock, Sun};
use crate::visual::VisualSettings;

/// Whether the panel window is currently shown (hidden by default; F1 toggles).
#[derive(Resource, Default)]
struct DebugPanel {
    open: bool,
}

/// Set true (during the egui pass) whenever egui wants the pointer — i.e. the cursor is
/// over the panel or dragging a widget. The camera controllers read this and skip their
/// cursor-grab / mouse-look so dragging a slider never rotates the world. Updated one frame
/// behind the camera systems, which is fine: you've hovered the panel before you click it.
#[derive(Resource, Default)]
pub struct EguiWantsPointer(pub bool);

/// When `enabled`, the panel's sun/ambient sliders override the day-night cycle's computed
/// values (applied after `advance_sky`). When off, the cycle drives them as normal.
#[derive(Resource)]
struct LightOverride {
    enabled: bool,
    illuminance: f32,
    ambient: f32,
}

impl Default for LightOverride {
    fn default() -> Self {
        Self { enabled: false, illuminance: 10_000.0, ambient: 120.0 }
    }
}

pub struct DebugPanelPlugin;

impl Plugin for DebugPanelPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins(EguiPlugin::default())
            // Opens on launch if `FOREST_PANEL` is set (handy for screenshots); else F1.
            .insert_resource(DebugPanel { open: std::env::var("FOREST_PANEL").is_ok() })
            .init_resource::<LightOverride>()
            .init_resource::<EguiWantsPointer>()
            .add_systems(Update, toggle_panel)
            // The egui pass runs after `Update`, so the lighting override here lands after
            // `advance_sky` has set the cycle values — letting the panel win when enabled.
            .add_systems(EguiPrimaryContextPass, panel_ui);
    }
}

fn toggle_panel(keys: Res<ButtonInput<KeyCode>>, mut panel: ResMut<DebugPanel>) {
    if keys.just_pressed(KeyCode::F1) {
        panel.open = !panel.open;
    }
}

#[allow(clippy::too_many_arguments)]
fn panel_ui(
    mut contexts: EguiContexts,
    panel: Res<DebugPanel>,
    mut cam: Query<
        (
            &mut DistanceFog,
            &mut DepthBlur,
            &mut Bloom,
            &mut ColorGrading,
            &mut Exposure,
            &mut ContrastAdaptiveSharpening,
            &mut VolumetricFog,
        ),
        With<Camera3d>,
    >,
    mut fog_vol: Query<&mut FogVolume>,
    mut visual: ResMut<VisualSettings>,
    mut clock: ResMut<SkyClock>,
    mut audio_cfg: ResMut<AudioConfig>,
    mut global_vol: ResMut<GlobalVolume>,
    mut light_override: ResMut<LightOverride>,
    mut sun: Query<&mut DirectionalLight, With<Sun>>,
    mut ambient: ResMut<GlobalAmbientLight>,
    mut egui_wants: ResMut<EguiWantsPointer>,
) -> Result {
    let ctx = contexts.ctx_mut()?;
    // Tell the camera controllers whether egui owns the pointer this frame (cursor over the
    // panel or dragging a widget) so they don't grab the cursor / rotate the view.
    egui_wants.0 = ctx.wants_pointer_input() || ctx.is_pointer_over_area();
    if !panel.open {
        return Ok(());
    }

    egui::Window::new("Debug")
        .default_width(280.0)
        .show(ctx, |ui| {
            ui.label("F1 toggles this panel");

            if let Ok((mut fog, mut blur, mut bloom, mut grading, mut exposure, mut cas, mut vfog)) =
                cam.single_mut()
            {
                egui::CollapsingHeader::new("Fog").default_open(true).show(ui, |ui| {
                    // Fog uses a Linear falloff (clear within `start`, full by `end`).
                    let (mut start, mut end) = match fog.falloff {
                        FogFalloff::Linear { start, end } => (start, end),
                        _ => (70.0, 160.0),
                    };
                    let mut changed = ui.add(egui::Slider::new(&mut start, 0.0..=300.0).text("clear")).changed();
                    changed |= ui.add(egui::Slider::new(&mut end, 10.0..=600.0).text("full")).changed();
                    if changed {
                        fog.falloff = FogFalloff::Linear { start, end: end.max(start + 1.0) };
                    }
                });

                egui::CollapsingHeader::new("Blur + Bloom").show(ui, |ui| {
                    ui.add(egui::Slider::new(&mut blur.clear, 0.0..=300.0).text("blur clear"));
                    ui.add(egui::Slider::new(&mut blur.full, 0.0..=600.0).text("blur full"));
                    ui.add(egui::Slider::new(&mut blur.radius, 0.0..=12.0).text("blur radius"));
                    ui.add(egui::Slider::new(&mut blur.near, 0.0..=60.0).text("blur near"));
                    ui.add(egui::Slider::new(&mut bloom.intensity, 0.0..=1.0).text("bloom"));
                });

                egui::CollapsingHeader::new("Render").default_open(true).show(ui, |ui| {
                    ui.label("Exposure / colour grade");
                    ui.add(egui::Slider::new(&mut exposure.ev100, 7.0..=13.0).text("exposure ev100"));
                    ui.add(egui::Slider::new(&mut grading.global.post_saturation, 0.5..=2.0).text("saturation"));
                    ui.add(egui::Slider::new(&mut grading.shadows.contrast, 0.5..=1.5).text("shadow contrast"));
                    ui.add(egui::Slider::new(&mut grading.midtones.contrast, 0.5..=1.5).text("mid contrast"));
                    ui.add(egui::Slider::new(&mut grading.highlights.contrast, 0.5..=1.5).text("high contrast"));

                    ui.separator();
                    ui.label("Sharpening (CAS)");
                    ui.checkbox(&mut cas.enabled, "CAS enabled");
                    ui.add(egui::Slider::new(&mut cas.sharpening_strength, 0.0..=1.0).text("sharpen"));

                    ui.separator();
                    ui.label("Volumetric god-rays");
                    ui.add(egui::Slider::new(&mut vfog.ambient_intensity, 0.0..=1.0).text("vol ambient"));
                    ui.add(egui::Slider::new(&mut vfog.step_count, 8u32..=128).text("vol steps"));
                    if let Ok(mut fv) = fog_vol.single_mut() {
                        ui.add(egui::Slider::new(&mut fv.density_factor, 0.0..=0.04).text("vol density"));
                        ui.add(egui::Slider::new(&mut fv.scattering, 0.0..=1.5).text("vol scattering"));
                        ui.add(egui::Slider::new(&mut fv.absorption, 0.0..=1.5).text("vol absorption"));
                        ui.add(egui::Slider::new(&mut fv.scattering_asymmetry, 0.0..=0.97).text("vol asymmetry"));
                        ui.add(egui::Slider::new(&mut fv.light_intensity, 0.0..=4.0).text("vol light"));
                    }

                    ui.separator();
                    ui.label("Pollen + prop specular");
                    // Temp-then-write so the resource is only marked changed on an actual edit
                    // (the apply system iterates materials, so we don't want per-frame churn).
                    let mut glow = visual.pollen_glow;
                    if ui.add(egui::Slider::new(&mut glow, 0.0..=8.0).text("pollen glow")).changed() {
                        visual.pollen_glow = glow;
                    }
                    let mut pspeed = visual.pollen_speed;
                    if ui.add(egui::Slider::new(&mut pspeed, 0.0..=3.0).text("pollen speed")).changed() {
                        visual.pollen_speed = pspeed;
                    }
                    let mut rough = visual.prop_roughness;
                    if ui.add(egui::Slider::new(&mut rough, 0.0..=1.0).text("prop roughness")).changed() {
                        visual.prop_roughness = rough;
                    }
                    let mut refl = visual.prop_reflectance;
                    if ui.add(egui::Slider::new(&mut refl, 0.0..=1.0).text("prop reflectance")).changed() {
                        visual.prop_reflectance = refl;
                    }
                });
            }

            egui::CollapsingHeader::new("Time / Sun").show(ui, |ui| {
                ui.add(egui::Slider::new(&mut clock.t, 0.0..=1.0).text("time (0=dawn)"));
                ui.checkbox(&mut clock.paused, "pause cycle");
                ui.add(egui::Slider::new(&mut clock.day_secs, 5.0..=600.0).text("cycle secs"));
                ui.separator();
                ui.checkbox(&mut light_override.enabled, "override lighting");
                if light_override.enabled {
                    ui.add(egui::Slider::new(&mut light_override.illuminance, 0.0..=20_000.0).text("sun lux"));
                    ui.add(egui::Slider::new(&mut light_override.ambient, 0.0..=400.0).text("ambient"));
                }
            });

            egui::CollapsingHeader::new("Audio").show(ui, |ui| {
                let mut master = if let Volume::Linear(l) = global_vol.volume { l } else { 1.0 };
                if ui.add(egui::Slider::new(&mut master, 0.0..=2.0).text("master")).changed() {
                    global_vol.volume = Volume::Linear(master);
                }
                ui.add(egui::Slider::new(&mut audio_cfg.ambience_vol, 0.0..=1.0).text("ambience"));
                ui.add(egui::Slider::new(&mut audio_cfg.audible_range, 5.0..=80.0).text("call range"));
                ui.add(egui::Slider::new(&mut audio_cfg.call_min, 2.0..=120.0).text("call min s"));
                ui.add(egui::Slider::new(&mut audio_cfg.call_max, 5.0..=200.0).text("call max s"));
                ui.separator();
                ui.add(egui::Slider::new(&mut audio_cfg.sfx_vol, 0.0..=1.5).text("sfx"));
                ui.add(egui::Slider::new(&mut audio_cfg.voice_vol, 0.0..=1.5).text("voice"));
                ui.add(egui::Slider::new(&mut audio_cfg.music_vol, 0.0..=1.0).text("music"));
                ui.add(egui::Slider::new(&mut audio_cfg.narration_vol, 0.0..=1.5).text("narration"));
                ui.add(egui::Slider::new(&mut audio_cfg.combat_music, 0.0..=2.0).text("combat music"));
            });
        });

    // Apply the lighting override after the day-night cycle (this pass runs post-`Update`).
    if light_override.enabled {
        if let Ok(mut light) = sun.single_mut() {
            light.illuminance = light_override.illuminance;
        }
        ambient.brightness = light_override.ambient;
    }

    Ok(())
}
