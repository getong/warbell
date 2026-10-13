//! **Film grade** — the final look pass, after every other post effect (`… → outline → dof →
//! filmgrade`). Bevy's `ColorGrading` gives per-range contrast/saturation but no *hue* per range, and
//! the warm-highlight / cool-shadow split is the heart of the painterly "western" look we're after
//! (RDR2-style: golden, sun-warmed highlights; teal-blue shade; rich but never neon greens; soft,
//! slightly lifted blacks; crisp detail). One cheap fullscreen pass on the tonemapped image:
//!
//! 1. **Split-tone** — shadows lean `shadow_tint`, highlights lean `highlight_tint`, luminance kept.
//! 2. **Vibrance** — saturation boost weighted toward *dull* colours (lifts grass/sky/cloth without
//!    pushing already-strong reds/skin into neon), plus a gentle global `saturation`.
//! 3. **Filmic S-curve** around a mid pivot in display space + a tinted **toe lift** (soft blacks).
//! 4. **Unsharp mask** (4 taps) — RDR2's crispness; restores the edge bite SMAA/DoF soften.
//!
//! The tints are driven per frame from the sun's elevation by [`drive_film_grade`] (day / golden
//! hour / night palettes), so the grade follows the time-of-day mood the sky already sets.
//! `FOREST_GRADE=0` disables the pass (A/B); `FOREST_GRADE=<0..2>` scales its strength.

use bevy::{
    core_pipeline::{Core3d, Core3dSystems, FullscreenShader},
    prelude::*,
    render::{
        extract_component::{
            ComponentUniforms, DynamicUniformIndex, ExtractComponent, ExtractComponentPlugin,
            UniformComponentPlugin,
        },
        render_resource::{
            binding_types::{sampler, texture_2d, uniform_buffer},
            *,
        },
        renderer::{RenderContext, RenderDevice, ViewQuery},
        view::ViewTarget,
        RenderApp, RenderStartup,
    },
};

use crate::scene::Sun;

const SHADER_ASSET_PATH: &str = "shaders/filmgrade.wesl";

/// Per-camera grade (also the shader uniform — field order must match `filmgrade.wesl`).
#[derive(Component, Clone, Copy, ExtractComponent, ShaderType)]
#[extract_app(RenderApp)]
pub struct FilmGrade {
    /// Multiplicative tint pulled into the shadows (luminance-normalised in the shader).
    pub shadow_tint: Vec3,
    /// Master 0..1 strength (0 = passthrough).
    pub strength: f32,
    /// Multiplicative tint pulled into the highlights.
    pub highlight_tint: Vec3,
    /// How far the split-tone pulls (0..1).
    pub split: f32,
    /// Tint of the lifted black floor.
    pub toe_tint: Vec3,
    /// Black-floor lift in display space (0.0–0.04).
    pub toe: f32,
    /// Saturation boost weighted toward low-saturation colours.
    pub vibrance: f32,
    /// Flat global saturation multiplier (1 = unchanged).
    pub saturation: f32,
    /// S-curve contrast (1 = linear).
    pub contrast: f32,
    /// Unsharp-mask amount (0 = off).
    pub sharpen: f32,
}

impl Default for FilmGrade {
    fn default() -> Self {
        Self {
            shadow_tint: Vec3::new(0.90, 0.99, 1.10),
            strength: 1.0,
            highlight_tint: Vec3::new(1.08, 1.00, 0.88),
            split: 0.55,
            toe_tint: Vec3::new(0.80, 0.90, 1.10),
            toe: 0.018,
            vibrance: 0.32,
            saturation: 1.04,
            contrast: 1.12,
            sharpen: 0.28,
        }
    }
}

/// The camera component with the `FOREST_GRADE` override applied; `None` = pass disabled.
pub fn default_film_grade() -> Option<FilmGrade> {
    let mut g = FilmGrade::default();
    if let Ok(v) = std::env::var("FOREST_GRADE") {
        let s = v.trim().parse::<f32>().unwrap_or(1.0);
        if s <= 0.0 {
            return None;
        }
        g.strength = s.min(2.0);
    }
    Some(g)
}

pub struct FilmGradePlugin;

impl Plugin for FilmGradePlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins((
            ExtractComponentPlugin::<FilmGrade>::default(),
            UniformComponentPlugin::<FilmGrade>::default(),
        ))
        .add_systems(Update, drive_film_grade);

        let Some(render_app) = app.get_sub_app_mut(RenderApp) else {
            return;
        };
        render_app.add_systems(RenderStartup, init_pipeline);
        // Last in the ping-pong chain: tonemapping → smaa/cas → atmospherics → godrays → outline →
        // dof → filmgrade. Grading the final composite means haze, rays and bokeh all share the look.
        render_app.add_systems(
            Core3d,
            film_grade_pass
                .in_set(Core3dSystems::PostProcess)
                .after(bevy::anti_alias::smaa::smaa)
                .after(bevy::anti_alias::contrast_adaptive_sharpening::cas)
                .after(crate::atmospherics::atmospherics_pass)
                .after(crate::godrays::godrays_pass)
                .after(crate::outline::outline_pass)
                .after(crate::dof::dof_pass),
        );
    }
}

fn smoothstep(e0: f32, e1: f32, x: f32) -> f32 {
    let t = ((x - e0) / (e1 - e0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// Time-of-day palettes, blended on the sun's elevation:
/// - **day**: warm-gold highlights over teal shade — the sun-baked western afternoon.
/// - **golden hour** (sun low): amber/orange highlights, deeper violet-blue shade, a touch more
///   contrast — the light the whole look is built around.
/// - **night**: moonlit — cool silver highlights, deep blue shadows, less vibrance (night colour
///   should read muted, not neon).
fn drive_film_grade(sun: Query<&GlobalTransform, With<Sun>>, mut cams: Query<&mut FilmGrade>) {
    let Ok(sun_tf) = sun.single() else {
        return;
    };
    let y = sun_tf.translation().normalize_or_zero().y;
    let day = smoothstep(-0.06, 0.18, y);
    let golden = smoothstep(-0.10, 0.04, y) * (1.0 - smoothstep(0.10, 0.34, y));
    let night = 1.0 - day;

    let mix3 = |a: Vec3, b: Vec3, t: f32| a.lerp(b, t.clamp(0.0, 1.0));
    let hi_day = Vec3::new(1.07, 1.00, 0.89);
    let hi_gold = Vec3::new(1.15, 0.98, 0.78);
    let hi_night = Vec3::new(0.94, 0.99, 1.08);
    let sh_day = Vec3::new(0.90, 0.99, 1.10);
    let sh_gold = Vec3::new(0.88, 0.92, 1.16);
    let sh_night = Vec3::new(0.84, 0.94, 1.18);

    for mut g in &mut cams {
        let hi = mix3(mix3(hi_day, hi_night, night), hi_gold, golden);
        let sh = mix3(mix3(sh_day, sh_night, night), sh_gold, golden);
        let changed = g.highlight_tint.distance_squared(hi) > 1e-8 || g.shadow_tint.distance_squared(sh) > 1e-8;
        if changed {
            g.highlight_tint = hi;
            g.shadow_tint = sh;
            g.vibrance = 0.32 - 0.14 * night + 0.06 * golden;
            g.contrast = 1.12 + 0.05 * golden - 0.04 * night;
            g.split = 0.55 + 0.15 * golden;
        }
    }
}

pub(crate) fn film_grade_pass(
    view: ViewQuery<(&ViewTarget, &FilmGrade, &DynamicUniformIndex<FilmGrade>)>,
    pipeline_res: Res<FilmGradePipeline>,
    pipeline_cache: Res<PipelineCache>,
    uniforms: Res<ComponentUniforms<FilmGrade>>,
    mut ctx: RenderContext,
) {
    let (view_target, _settings, settings_index) = view.into_inner();
    let Some(pipeline) = pipeline_cache.get_render_pipeline(pipeline_res.pipeline_id) else {
        return;
    };
    let Some(settings_binding) = uniforms.uniforms().binding() else {
        return;
    };

    let post_process = view_target.post_process_write();
    let bind_group = ctx.render_device().create_bind_group(
        "film_grade_bind_group",
        &pipeline_cache.get_bind_group_layout(&pipeline_res.layout),
        &BindGroupEntries::sequential((post_process.source, &pipeline_res.sampler, settings_binding.clone())),
    );

    let mut render_pass = ctx.command_encoder().begin_render_pass(&RenderPassDescriptor {
        label: Some("film_grade_pass"),
        color_attachments: &[Some(RenderPassColorAttachment {
            view: post_process.destination,
            depth_slice: None,
            resolve_target: None,
            ops: Operations::default(),
        })],
        ..default()
    });
    render_pass.set_pipeline(pipeline);
    render_pass.set_bind_group(0, &bind_group, &[settings_index.index()]);
    render_pass.draw(0..3, 0..1);
}

#[derive(Resource)]
pub(crate) struct FilmGradePipeline {
    layout: BindGroupLayoutDescriptor,
    sampler: Sampler,
    pipeline_id: CachedRenderPipelineId,
}

fn init_pipeline(
    mut commands: Commands,
    render_device: Res<RenderDevice>,
    asset_server: Res<AssetServer>,
    fullscreen_shader: Res<FullscreenShader>,
    pipeline_cache: Res<PipelineCache>,
) {
    let layout = BindGroupLayoutDescriptor::new(
        "film_grade_bind_group_layout",
        &BindGroupLayoutEntries::sequential(
            ShaderStages::FRAGMENT,
            (
                texture_2d(TextureSampleType::Float { filterable: true }),
                sampler(SamplerBindingType::Filtering),
                uniform_buffer::<FilmGrade>(true),
            ),
        ),
    );
    let sampler = render_device.create_sampler(&SamplerDescriptor::default());
    let shader = asset_server.load(SHADER_ASSET_PATH);
    let pipeline_id = pipeline_cache.queue_render_pipeline(RenderPipelineDescriptor {
        label: Some("film_grade_pipeline".into()),
        layout: vec![layout.clone()],
        vertex: fullscreen_shader.to_vertex_state(),
        fragment: Some(FragmentState {
            shader,
            targets: vec![Some(ColorTargetState {
                format: TextureFormat::Rgba16Float,
                blend: None,
                write_mask: ColorWrites::ALL,
            })],
            ..default()
        }),
        ..default()
    });
    commands.insert_resource(FilmGradePipeline { layout, sampler, pipeline_id });
}
