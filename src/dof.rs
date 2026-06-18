//! Custom **CoC bokeh depth-of-field** post pass — the player-focused DoF the old game had.
//! Bevy's built-in `DepthOfField` silently no-ops in this pipeline (verified: even f/1.0 with
//! SSAO removed produces no blur), so this is a fullscreen pass that reads the prepass depth
//! and blurs by a circle-of-confusion around a focal plane (driven onto the player by
//! `scene::drive_dof_focus`). Same RenderStartup/ViewNode pattern as the other post passes.

// Bevy 0.19 replaced the render-graph (`ViewNode` + graph nodes/edges) with the render *schedule*:
// a post pass is now a plain system added to the `Core3d` schedule, ordered by `Core3dSystems`
// sets, taking the current view via `ViewQuery` and recording into a `RenderContext` SystemParam.
use bevy::{
    core_pipeline::{
        prepass::ViewPrepassTextures, tonemapping::tonemapping, Core3d, Core3dSystems,
        FullscreenShader,
    },
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
        view::ViewTarget,
        RenderApp, RenderStartup,
    },
};

const SHADER_ASSET_PATH: &str = "shaders/dof.wgsl";
const NEAR: f32 = 0.1;

/// Per-camera bokeh-DoF settings (also the shader uniform). `focal` is overwritten each frame
/// by `scene::drive_dof_focus` (camera→player distance / a fixed mid-ground plane in free-cam).
#[derive(Component, Default, Clone, Copy, ExtractComponent, ShaderType)]
pub struct Dof {
    /// Focus distance (tiles).
    pub focal: f32,
    /// Half-width of the fully-sharp focus band (tiles).
    pub range: f32,
    /// Distance (tiles) over which the FAR blur ramps from sharp to max — large = gradual
    /// (the farther a thing is, the blurrier it gets, instead of clamping to a flat max).
    pub far_ramp: f32,
    /// Maximum blur radius (pixels).
    pub max_radius: f32,
    /// Camera near plane (depth → distance).
    pub near: f32,
    /// Debug: >0.5 paints the raw CoC (blur factor) as grayscale instead of blurring — white
    /// = "DoF thinks this is fully out of focus". Lets you see if a washed-out region is DoF.
    pub debug_view: f32,
}

/// A tasteful default; tunable live in the Debug panel.
pub fn default_dof() -> Dof {
    Dof { focal: 28.0, range: 16.0, far_ramp: 120.0, max_radius: 18.0, near: NEAR, debug_view: 0.0 }
}

pub struct DofPlugin;

impl Plugin for DofPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins((
            ExtractComponentPlugin::<Dof>::default(),
            UniformComponentPlugin::<Dof>::default(),
        ));

        let Some(render_app) = app.get_sub_app_mut(RenderApp) else {
            return;
        };
        render_app.add_systems(RenderStartup, init_pipeline);
        // Was a render-graph node `Tonemapping → Dof → EndMainPassPostProcessing`. In Bevy 0.19
        // it's a system in the `PostProcess` set, after `tonemapping`; the outline pass orders
        // itself `.before(dof_pass)` so its darkened edges are written before the DoF reads them.
        render_app.add_systems(
            Core3d,
            dof_pass.in_set(Core3dSystems::PostProcess).after(tonemapping),
        );
    }
}

/// The CoC bokeh DoF post pass, now a system in the `Core3d` render schedule. `ViewQuery`
/// resolves the camera currently being rendered and auto-skips (via SystemParam validation) for
/// any view that lacks a `Dof` component — e.g. a UI/capture camera — so no manual guard needed.
pub(crate) fn dof_pass(
    view: ViewQuery<(
        &ViewTarget,
        &ViewPrepassTextures,
        &Dof,
        &DynamicUniformIndex<Dof>,
    )>,
    pipeline_res: Res<DofPipeline>,
    pipeline_cache: Res<PipelineCache>,
    uniforms: Res<ComponentUniforms<Dof>>,
    mut ctx: RenderContext,
) {
    let (view_target, prepass, _settings, settings_index) = view.into_inner();
    let Some(pipeline) = pipeline_cache.get_render_pipeline(pipeline_res.pipeline_id) else {
        return;
    };
    let Some(settings_binding) = uniforms.uniforms().binding() else {
        return;
    };
    let Some(depth_view) = prepass.depth_view() else {
        return;
    };

    let post_process = view_target.post_process_write();
    let bind_group = ctx.render_device().create_bind_group(
        "dof_bind_group",
        &pipeline_cache.get_bind_group_layout(&pipeline_res.layout),
        &BindGroupEntries::sequential((
            post_process.source,
            &pipeline_res.sampler,
            depth_view,
            settings_binding.clone(),
        )),
    );

    let mut render_pass = ctx.begin_tracked_render_pass(RenderPassDescriptor {
        label: Some("dof_pass"),
        color_attachments: &[Some(RenderPassColorAttachment {
            view: post_process.destination,
            depth_slice: None,
            resolve_target: None,
            ops: Operations::default(),
        })],
        depth_stencil_attachment: None,
        timestamp_writes: None,
        occlusion_query_set: None,
        multiview_mask: None,
    });

    render_pass.set_render_pipeline(pipeline);
    render_pass.set_bind_group(0, &bind_group, &[settings_index.index()]);
    render_pass.draw(0..3, 0..1);
}

#[derive(Resource)]
pub(crate) struct DofPipeline {
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
        "dof_bind_group_layout",
        &BindGroupLayoutEntries::sequential(
            ShaderStages::FRAGMENT,
            (
                texture_2d(TextureSampleType::Float { filterable: true }),
                sampler(SamplerBindingType::Filtering),
                texture_depth_2d(),
                uniform_buffer::<Dof>(true),
            ),
        ),
    );
    let sampler = render_device.create_sampler(&SamplerDescriptor::default());
    let shader = asset_server.load(SHADER_ASSET_PATH);
    let vertex_state = fullscreen_shader.to_vertex_state();
    let pipeline_id = pipeline_cache.queue_render_pipeline(RenderPipelineDescriptor {
        label: Some("dof_pipeline".into()),
        layout: vec![layout.clone()],
        vertex: vertex_state,
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
    commands.insert_resource(DofPipeline { layout, sampler, pipeline_id });
}
