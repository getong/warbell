//! **Chrome textures** — tiny tiling noise images generated once at startup (no art assets),
//! laid over panels at a few percent alpha so large fills don't read as flat plastic.
//! [`widgets::chrome_layers`](super::widgets::chrome_layers) and the parchment board stretch
//! them via `NodeImageMode::Tiled`. Deterministic (core `Mulberry32`), like world scatter.

use bevy::asset::RenderAssetUsages;
use bevy::prelude::*;
use bevy::render::render_resource::{Extent3d, TextureDimension, TextureFormat};
use tileworld_core::rng::Mulberry32;

/// Handles to the generated tiling textures.
#[derive(Resource)]
pub struct UiTextures {
    /// Brighten-only white speckle with faint row striation — linen weave for dark panels.
    pub linen: Handle<Image>,
    /// Brown ink speckle + sparse fibers — grain for parchment boards.
    pub parchment: Handle<Image>,
}

const T: usize = 64; // tile edge in px

fn image(buf: Vec<u8>) -> Image {
    Image::new(
        Extent3d { width: T as u32, height: T as u32, depth_or_array_layers: 1 },
        TextureDimension::D2,
        buf,
        TextureFormat::Rgba8UnormSrgb,
        RenderAssetUsages::default(),
    )
}

fn linen() -> Image {
    let mut rng = Mulberry32::new(0xCAFE);
    // Per-row brightness wobble fakes a weave; per-pixel speckle breaks the rows up.
    let rows: Vec<f64> = (0..T).map(|_| rng.next()).collect();
    let mut buf = vec![0u8; T * T * 4];
    for y in 0..T {
        for x in 0..T {
            let a = (rng.next() * 7.0 + rows[y] * 5.0) as u8;
            let i = (y * T + x) * 4;
            buf[i..i + 4].copy_from_slice(&[255, 244, 224, a]);
        }
    }
    image(buf)
}

fn parchment() -> Image {
    let mut rng = Mulberry32::new(0xF00D);
    let mut buf = vec![0u8; T * T * 4];
    for y in 0..T {
        for x in 0..T {
            let a = (rng.next() * 11.0) as u8;
            let i = (y * T + x) * 4;
            buf[i..i + 4].copy_from_slice(&[90, 69, 36, a]);
        }
    }
    // Sparse short horizontal fibers.
    for _ in 0..26 {
        let x0 = (rng.next() * (T - 8) as f64) as usize;
        let y = (rng.next() * T as f64) as usize;
        let len = 3 + (rng.next() * 5.0) as usize;
        let a = 14 + (rng.next() * 10.0) as u8;
        for x in x0..(x0 + len).min(T) {
            let i = (y * T + x) * 4;
            buf[i..i + 4].copy_from_slice(&[90, 69, 36, a]);
        }
    }
    image(buf)
}

pub struct UiTexturePlugin;

impl Plugin for UiTexturePlugin {
    fn build(&self, app: &mut App) {
        let mut images = app.world_mut().resource_mut::<Assets<Image>>();
        let tex = UiTextures { linen: images.add(linen()), parchment: images.add(parchment()) };
        app.insert_resource(tex);
    }
}
