//! **Water screen-space reflections** — rivers, the lake, swamp pools and the sea mirror the
//! banks, trees, buildings and ships around them, not just the sky.
//!
//! The water material (`water.rs`) only reflects the environment map (a sky gradient) plus a faked
//! dark bank band, so every river read as a flat dark sheet. Bevy's own SSR needs deferred
//! rendering, which this forward renderer doesn't run. Every water surface is ONE plane at
//! `worldmap::SEA_Y`, though, so a fullscreen pass can find water pixels straight from the prepass
//! depth (unprojected Y on the plane), march the mirrored, gently rippled view ray against the same
//! depth, and blend the lit scene it hits in at a Fresnel weight (`water_ssr.wesl`).
//!
//! Same shape as [`crate::atmospherics`]: a `Core3d` PostProcess ping-pong pass, pinned
//! `.after(smaa).before(atmospherics_pass)` so the haze then lays over the reflections too. Rides
//! the High/Ultra "premium look" gate in `quality::apply_quality`. `FOREST_WATERSSR=<strength>`
//! overrides the blend (0 = off) for A/B shots.

use bevy::{
    anti_alias::smaa::smaa,
    core_pipeline::{prepass::ViewPrepassTextures, Core3d, Core3dSystems, FullscreenShader},
    prelude::*,
    render::{
        extract_component::{
            ComponentUniforms, DynamicUniformIndex, ExtractComponent, ExtractComponentPlugin,
            UniformComponentPlugin,
        },
        render_resource::{
            binding_types::{sampler, texture_2d, texture_depth_2d, uniform_buffer},
            *,
        },
        renderer::{RenderContext, RenderDevice, ViewQuery},
        view::{ViewTarget, ViewUniform, ViewUniformOffset, ViewUniforms},
        RenderApp, RenderStartup,
    },
};

const SHADER_ASSET_PATH: &str = "shaders/water_ssr.wesl";

/// Per-camera settings + shader uniform; field ORDER matches the WGSL `Settings` struct.
///
/// The camera matrices come from Bevy's own render-world `View` uniform, NOT from here: matrices
/// computed in the main world's `Update` were a frame stale (the follow-cam moves later, in
/// PostUpdate) and lacked the TAA jitter the depth was rendered with, so while the camera moved
/// the unprojected depth missed the water plane and the reflections blinked out / re-formed on
/// every camera motion.
#[derive(Component, Clone, Copy, ExtractComponent, ShaderType)]
#[extract_app(RenderApp)]
pub struct WaterSsr {
    pub sea_y: f32,
    pub time: f32,
    /// Fresnel blend scale (0 = off).
    pub strength: f32,
    /// Ripple normal tilt — how much the mirror image wobbles.
    pub ripple: f32,
    /// Longest reflected ray, world units.
    pub max_dist: f32,
}

pub fn default_water_ssr() -> WaterSsr {
    WaterSsr {
        sea_y: crate::worldmap::SEA_Y,
        time: 0.0,
        strength: std::env::var("FOREST_WATERSSR").ok().and_then(|v| v.trim().parse().ok()).unwrap_or(1.0),
        ripple: std::env::var("FOREST_WATERRIPPLE").ok().and_then(|v| v.trim().parse().ok()).unwrap_or(0.03),
        max_dist: 220.0,
    }
}

pub struct WaterSsrPlugin;

impl Plugin for WaterSsrPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins((
            ExtractComponentPlugin::<WaterSsr>::default(),
            UniformComponentPlugin::<WaterSsr>::default(),
        ))
        .add_systems(Update, drive_water_ssr);

        let Some(render_app) = app.get_sub_app_mut(RenderApp) else {
            return;
        };
        render_app.add_systems(RenderStartup, init_pipeline);
        render_app.add_systems(
            Core3d,
            water_ssr_pass
                .in_set(Core3dSystems::PostProcess)
                .after(smaa)
                .after(bevy::anti_alias::contrast_adaptive_sharpening::cas)
                .before(crate::atmospherics::atmospherics_pass),
        );
    }
}

fn drive_water_ssr(time: Res<Time>, mut cams: Query<&mut WaterSsr>) {
    for mut s in &mut cams {
        s.time = time.elapsed_secs();
    }
}

pub(crate) fn water_ssr_pass(
    view: ViewQuery<(&ViewTarget, &ViewPrepassTextures, &WaterSsr, &DynamicUniformIndex<WaterSsr>, &ViewUniformOffset)>,
    pipeline_res: Res<WaterSsrPipeline>,
    pipeline_cache: Res<PipelineCache>,
    uniforms: Res<ComponentUniforms<WaterSsr>>,
    view_uniforms: Res<ViewUniforms>,
    mut ctx: RenderContext,
) {
    let (view_target, prepass, _settings, settings_index, view_offset) = view.into_inner();
    let Some(view_binding) = view_uniforms.uniforms.binding() else {
        return;
    };
    let Some(pipeline) = pipeline_cache.get_render_pipeline(pipeline_res.pipeline_id) else {
        return;
    };
    let Some(settings_binding) = uniforms.uniforms().binding() else {
        return;
    };
    let Some(depth_view) = prepass.depth_only_view() else {
        return;
    };
    let post_process = view_target.post_process_write();
    let bind_group = ctx.render_device().create_bind_group(
        "water_ssr_bind_group",
        &pipeline_cache.get_bind_group_layout(&pipeline_res.layout),
        &BindGroupEntries::sequential((post_process.source, &pipeline_res.sampler, depth_view, settings_binding.clone(), view_binding)),
    );
    let mut pass = ctx.command_encoder().begin_render_pass(&RenderPassDescriptor {
        label: Some("water_ssr_pass"),
        color_attachments: &[Some(RenderPassColorAttachment {
            view: post_process.destination,
            depth_slice: None,
            resolve_target: None,
            ops: Operations::default(),
        })],
        ..default()
    });
    pass.set_pipeline(pipeline);
    pass.set_bind_group(0, &bind_group, &[settings_index.index(), view_offset.offset]);
    pass.draw(0..3, 0..1);
}

#[derive(Resource)]
pub(crate) struct WaterSsrPipeline {
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
        "water_ssr_bind_group_layout",
        &BindGroupLayoutEntries::sequential(
            ShaderStages::FRAGMENT,
            (
                texture_2d(TextureSampleType::Float { filterable: true }),
                sampler(SamplerBindingType::Filtering),
                texture_depth_2d(),
                uniform_buffer::<WaterSsr>(true),
                uniform_buffer::<ViewUniform>(true),
            ),
        ),
    );
    let sampler = render_device.create_sampler(&SamplerDescriptor {
        mag_filter: FilterMode::Linear,
        min_filter: FilterMode::Linear,
        ..default()
    });
    let pipeline_id = pipeline_cache.queue_render_pipeline(RenderPipelineDescriptor {
        label: Some("water_ssr_pipeline".into()),
        layout: vec![layout.clone()],
        vertex: fullscreen_shader.to_vertex_state(),
        fragment: Some(FragmentState {
            shader: asset_server.load(SHADER_ASSET_PATH),
            targets: vec![Some(ColorTargetState { format: TextureFormat::Rgba16Float, blend: None, write_mask: ColorWrites::ALL })],
            ..default()
        }),
        ..default()
    });
    commands.insert_resource(WaterSsrPipeline { layout, sampler, pipeline_id });
}
