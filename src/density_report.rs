//! **Density audit** (spec 2026-10-13 "Żywa wyspa" §1 / Krok 0): lays a 40u grid over the island,
//! counts every *planned* site from all world planners per cell, and prints the grid, the empty
//! land cells and a tally for the five "empty areas" named in the spec. Test-only; it asserts
//! nothing beyond "the planners ran" yet — the content packages turn its output into the
//! acceptance check (every §1 area gets at least one interactive point).
//!
//! Run: `cargo test --release density_report -- --nocapture`.

use bevy::prelude::*;

/// Grid cell edge (world units).
const CELL: f32 = 40.0;
/// Grid extent: the island (±277 × ±207) plus the Blight south of it (Hold at z≈230).
const X0: f32 = -280.0;
const X1: f32 = 280.0;
const Z0: f32 = -220.0;
const Z1: f32 = 260.0;

/// One planned site: which planner, where, and whether it *does* something (vs a silent diorama).
struct Site {
    src: &'static str,
    pos: Vec2,
    interactive: bool,
}

/// Run every planner in world-build order (`worldmap` phase 4) and gather their sites.
fn collect_sites() -> Vec<Site> {
    use crate::biome::Biome;
    crate::blockers::reset();
    crate::poi::plan_clearings();
    crate::stories_warm::plan();
    crate::vignettes::plan();
    crate::wayside::plan();
    crate::stories_cold::plan();
    crate::sites_warm::plan();
    crate::wild_sites::plan();
    crate::castaway::plan();
    crate::stashes::plan();

    let mut out = Vec::new();
    let mut push = |src: &'static str, pos: Vec2, interactive: bool| out.push(Site { src, pos, interactive });
    for c in crate::camps::plan() {
        push("camp", c.centre, true);
    }
    for l in crate::ruins::landmark_sites() {
        push("landmark", l.pos, true);
    }
    for b in [Biome::Forest, Biome::Snow, Biome::Rocky, Biome::Desert, Biome::Swamp] {
        push("warden", crate::boss::region_center(b), true);
    }
    push("rival_fort", crate::rival::RIVAL_CENTRE, true);
    push("hold", crate::ork_fortress::CENTRE, true);
    for p in crate::poi::planned_story_sites() {
        push("poi", p, false);
    }
    for (p, _) in crate::wayside::planned_footprints() {
        push("wayside", p, false);
    }
    if let Some((p, _)) = crate::vignettes::planned_footprint() {
        push("vignette", p, false);
    }
    for (p, _) in crate::stories_warm::planned_footprints() {
        push("stories_warm", p, false);
    }
    for (p, _) in crate::stories_cold::planned_footprints() {
        push("stories_cold", p, false);
    }
    for (p, _) in crate::sites_warm::planned_footprints() {
        push("sites_warm", p, false);
    }
    for (p, _) in crate::wild_sites::planned_footprints() {
        push("wild_sites", p, false);
    }
    for p in crate::stashes::planned_sites() {
        push("stashes", p, true);
    }
    for (p, _) in crate::castaway::planned_footprints() {
        push("castaway", p, true);
    }
    out
}

fn reset_all() {
    crate::blockers::reset();
    crate::poi::reset_plan();
    crate::stories_warm::reset_plan();
    crate::vignettes::reset_plan();
    crate::wayside::reset_plan();
    crate::stories_cold::reset_plan();
    crate::sites_warm::reset_plan();
    crate::wild_sites::reset_plan();
    crate::castaway::reset_plan();
    crate::stashes::reset_plan();
}

/// Fraction of a cell that is land (5×5 samples).
fn land_frac(x: f32, z: f32) -> f32 {
    let mut n = 0;
    for i in 0..5 {
        for j in 0..5 {
            let (sx, sz) = (x + (i as f32 + 0.5) * CELL / 5.0, z + (j as f32 + 0.5) * CELL / 5.0);
            if crate::worldmap::is_land_tile_world(sx, sz) {
                n += 1;
            }
        }
    }
    n as f32 / 25.0
}

/// The spec's §1 empty areas (x0, x1, z0, z1).
const SPEC_AREAS: [(&str, [f32; 4]); 5] = [
    ("1 S seam castle-bog", [-50.0, 30.0, 47.0, 95.0]),
    ("2 meadow round walls", [-54.0, 54.0, -47.0, 47.0]),
    ("3 SE coast bog-rocks", [40.0, 110.0, 120.0, 200.0]),
    ("4 NE dune sea", [150.0, 250.0, -190.0, -110.0]),
    ("5 N coast snow/desert", [-60.0, 20.0, -205.0, -185.0]),
];

#[test]
fn density_report() {
    let _g = crate::blockers::TEST_LOCK.lock().unwrap();
    let sites = collect_sites();
    reset_all();
    assert!(!sites.is_empty(), "planners produced no sites");

    let cols = ((X1 - X0) / CELL).ceil() as usize;
    let rows = ((Z1 - Z0) / CELL).ceil() as usize;
    let mut grid = vec![vec![(0u32, 0u32); cols]; rows]; // (all, interactive)
    for s in &sites {
        let (c, r) = (((s.pos.x - X0) / CELL).floor(), ((s.pos.y - Z0) / CELL).floor());
        if c >= 0.0 && r >= 0.0 && (c as usize) < cols && (r as usize) < rows {
            let cell = &mut grid[r as usize][c as usize];
            cell.0 += 1;
            cell.1 += s.interactive as u32;
        }
    }

    let mut by_src: Vec<(&str, usize)> = Vec::new();
    for s in &sites {
        match by_src.iter_mut().find(|(k, _)| *k == s.src) {
            Some(e) => e.1 += 1,
            None => by_src.push((s.src, 1)),
        }
    }
    eprintln!("density_report: {} planned sites ({} interactive)", sites.len(), sites.iter().filter(|s| s.interactive).count());
    eprintln!("  by planner: {by_src:?}");
    eprintln!("  grid {CELL}u, x {X0}..{X1} (cols), z {Z0}..{Z1} (rows); `~` sea, `.` empty land, n = sites (`*` = has interactive)");
    let mut empty: Vec<String> = Vec::new();
    let mut land_cells = 0;
    for (r, row) in grid.iter().enumerate() {
        let z = Z0 + r as f32 * CELL;
        let mut line = format!("  z{:>5} ", z as i32);
        for (c, &(n, ia)) in row.iter().enumerate() {
            let x = X0 + c as f32 * CELL;
            let land = land_frac(x, z) >= 0.3;
            land_cells += land as usize;
            let cell = match (land, n) {
                (false, 0) => " ~ ".to_string(),
                (true, 0) => {
                    let b = crate::worldmap::biome_at_world(x + CELL / 2.0, z + CELL / 2.0);
                    empty.push(format!("({:.0},{:.0}) {b:?}", x + CELL / 2.0, z + CELL / 2.0));
                    " . ".to_string()
                }
                _ => format!("{n:>2}{}", if ia > 0 { '*' } else { ' ' }),
            };
            line.push_str(&cell);
        }
        eprintln!("{line}");
    }
    eprintln!("  {} empty land cells of {land_cells} (centres): {}", empty.len(), empty.join(", "));
    for (name, [x0, x1, z0, z1]) in SPEC_AREAS {
        let inside: Vec<&Site> =
            sites.iter().filter(|s| s.pos.x >= x0 && s.pos.x <= x1 && s.pos.y >= z0 && s.pos.y <= z1).collect();
        let ia = inside.iter().filter(|s| s.interactive).count();
        let srcs: Vec<&str> = inside.iter().map(|s| s.src).collect();
        eprintln!("  area {name}: {} sites, {ia} interactive {srcs:?}", inside.len());
    }
}
