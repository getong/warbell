//! Minimal combat HUD — an HP bar over a thinner block-stamina bar, bottom-left. Plain
//! `bevy_ui` rectangles bound to the hero's `HeroHealth`; no text, no chrome.

use bevy::prelude::*;
use tileworld_core::buff_store::BuffKind;
use tileworld_core::inventory::{item_def, QuickSlot};

use crate::icons::IconAtlas;
use crate::inventory::{Buffs, Inventory, Toasts};
use crate::player::{HeroHealth, PlayerRes};

#[derive(Component)]
struct HpFill;
#[derive(Component)]
struct StaminaFill;
#[derive(Component)]
struct XpFill;
#[derive(Component)]
struct ResourceText;

/// Which derived quick-slot a node belongs to.
#[derive(Clone, Copy, PartialEq)]
enum SlotKind {
    Food,
    Resist,
    Power,
    Haste,
}
impl SlotKind {
    fn key(self) -> char {
        match self {
            SlotKind::Food => 'Q',
            SlotKind::Resist => 'Z',
            SlotKind::Power => 'X',
            SlotKind::Haste => 'C',
        }
    }
}
/// A quick-slot's icon (its `ImageNode` handle + display are swapped each frame).
#[derive(Component)]
struct QuickSlotIcon(SlotKind);
/// A quick-slot's key/count label.
#[derive(Component)]
struct QuickSlotText(SlotKind);
/// The active-buff timers line under the quick-bar.
#[derive(Component)]
struct BuffLineText;
/// The toast column container (rows are cleared + respawned each frame).
#[derive(Component)]
struct ToastRoot;
/// One toast row (despawned + rebuilt each frame).
#[derive(Component)]
struct ToastRow;

pub struct HudPlugin;

impl Plugin for HudPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(Startup, (setup_hud, setup_inv_hud))
            .add_systems(Update, (update_hud, update_inv_hud));
    }
}

fn setup_hud(mut commands: Commands) {
    let track_bg = Color::srgba(0.0, 0.0, 0.0, 0.55);
    commands
        .spawn(Node {
            position_type: PositionType::Absolute,
            left: Val::Px(18.0),
            bottom: Val::Px(18.0),
            width: Val::Px(240.0),
            flex_direction: FlexDirection::Column,
            row_gap: Val::Px(6.0),
            ..default()
        })
        .with_children(|root| {
            // Level + gold + stone readout (numeric).
            root.spawn((
                Text::new("Lv 1   Gold 30   Stone 0"),
                TextFont { font_size: 18.0, ..default() },
                TextColor(Color::srgb(0.96, 0.86, 0.45)),
                ResourceText,
            ));
            // HP track + fill.
            root.spawn((
                Node {
                    width: Val::Percent(100.0),
                    height: Val::Px(16.0),
                    padding: UiRect::all(Val::Px(2.0)),
                    ..default()
                },
                BackgroundColor(track_bg),
            ))
            .with_children(|t| {
                t.spawn((
                    Node { width: Val::Percent(100.0), height: Val::Percent(100.0), ..default() },
                    BackgroundColor(Color::srgb(0.85, 0.22, 0.22)),
                    HpFill,
                ));
            });
            // Block-stamina track + fill (thinner).
            root.spawn((
                Node {
                    width: Val::Percent(100.0),
                    height: Val::Px(9.0),
                    padding: UiRect::all(Val::Px(2.0)),
                    ..default()
                },
                BackgroundColor(track_bg),
            ))
            .with_children(|t| {
                t.spawn((
                    Node { width: Val::Percent(100.0), height: Val::Percent(100.0), ..default() },
                    BackgroundColor(Color::srgb(0.92, 0.78, 0.30)),
                    StaminaFill,
                ));
            });
            // XP track + fill (thin, blue — fills toward the next level).
            root.spawn((
                Node {
                    width: Val::Percent(100.0),
                    height: Val::Px(7.0),
                    padding: UiRect::all(Val::Px(2.0)),
                    ..default()
                },
                BackgroundColor(track_bg),
            ))
            .with_children(|t| {
                t.spawn((
                    Node { width: Val::Percent(0.0), height: Val::Percent(100.0), ..default() },
                    BackgroundColor(Color::srgb(0.42, 0.7, 1.0)),
                    XpFill,
                ));
            });
        });
}

/// Pickup toasts (top-right) + the quick-bar/buff line (bottom-centre).
fn setup_inv_hud(mut commands: Commands) {
    // Top-left controls legend (so the panels are discoverable).
    commands
        .spawn(Node {
            position_type: PositionType::Absolute,
            left: Val::Px(18.0),
            top: Val::Px(14.0),
            ..default()
        })
        .with_children(|p| {
            p.spawn((
                Text::new("U Upgrades   T Shop   I Bag   R Recruit   B/E War Bell   ` Free-cam"),
                TextFont { font_size: 14.0, ..default() },
                TextColor(Color::srgba(0.85, 0.86, 0.92, 0.65)),
            ));
        });
    // Top-right pickup-toast column (rows spawned dynamically into this container).
    commands.spawn((
        Node {
            position_type: PositionType::Absolute,
            right: Val::Px(18.0),
            top: Val::Px(18.0),
            flex_direction: FlexDirection::Column,
            align_items: AlignItems::End,
            row_gap: Val::Px(4.0),
            ..default()
        },
        ToastRoot,
    ));
    // Bottom-centre quick-bar: a row of 4 icon slots + a buff-timer line beneath.
    commands
        .spawn(Node {
            position_type: PositionType::Absolute,
            bottom: Val::Px(16.0),
            width: Val::Percent(100.0),
            flex_direction: FlexDirection::Column,
            align_items: AlignItems::Center,
            row_gap: Val::Px(4.0),
            ..default()
        })
        .with_children(|col| {
            col.spawn(Node { flex_direction: FlexDirection::Row, column_gap: Val::Px(14.0), ..default() })
                .with_children(|row| {
                    for kind in [SlotKind::Food, SlotKind::Resist, SlotKind::Power, SlotKind::Haste] {
                        row.spawn((
                            Node {
                                flex_direction: FlexDirection::Column,
                                align_items: AlignItems::Center,
                                padding: UiRect::all(Val::Px(4.0)),
                                ..default()
                            },
                            BackgroundColor(Color::srgba(0.0, 0.0, 0.0, 0.45)),
                        ))
                        .with_children(|slot| {
                            slot.spawn((
                                Node {
                                    width: Val::Px(28.0),
                                    height: Val::Px(28.0),
                                    display: Display::None, // shown once a real handle is assigned
                                    ..default()
                                },
                                ImageNode::new(Handle::default()),
                                QuickSlotIcon(kind),
                            ));
                            slot.spawn((
                                Text::new(format!("{} -", kind.key())),
                                TextFont { font_size: 14.0, ..default() },
                                TextColor(Color::srgb(0.88, 0.9, 0.95)),
                                QuickSlotText(kind),
                            ));
                        });
                    }
                });
            col.spawn((
                Text::new(""),
                TextFont { font_size: 14.0, ..default() },
                TextColor(Color::srgb(0.7, 0.85, 1.0)),
                BuffLineText,
            ));
        });
}

/// Resolve which bag item feeds a quick-slot.
fn slot_for(inv: &Inventory, kind: SlotKind) -> Option<QuickSlot> {
    match kind {
        SlotKind::Food => inv.0.food_slot(),
        SlotKind::Resist => inv.0.buff_slot(BuffKind::Resist),
        SlotKind::Power => inv.0.buff_slot(BuffKind::Power),
        SlotKind::Haste => inv.0.buff_slot(BuffKind::Haste),
    }
}

/// Drive the quick-bar icons/counts + buff line + the pickup-toast rows (with item icons).
#[allow(clippy::type_complexity, clippy::too_many_arguments)]
fn update_inv_hud(
    time: Res<Time>,
    inv: Res<Inventory>,
    buffs: Res<Buffs>,
    atlas: Res<IconAtlas>,
    mut toasts: ResMut<Toasts>,
    mut commands: Commands,
    mut icon_q: Query<(&QuickSlotIcon, &mut Node, &mut ImageNode)>,
    mut count_q: Query<(&QuickSlotText, &mut Text), With<QuickSlotText>>,
    mut buffline_q: Query<&mut Text, (With<BuffLineText>, Without<QuickSlotText>)>,
    toast_root_q: Query<Entity, With<ToastRoot>>,
    rows_q: Query<Entity, With<ToastRow>>,
) {
    let now = time.elapsed_secs() as f64;

    // ── Quick-slot icons: swap the handle + show/hide the slot. ──
    for (slot, mut node, mut img) in &mut icon_q {
        match slot_for(&inv, slot.0).and_then(|s| atlas.get(&s.item_id)) {
            Some(handle) => {
                img.image = handle;
                node.display = Display::Flex;
            }
            None => node.display = Display::None,
        }
    }
    // ── Quick-slot labels: "Q x3" or "Q -". ──
    for (slot, mut text) in &mut count_q {
        **text = match slot_for(&inv, slot.0) {
            Some(s) => format!("{} x{}", slot.0.key(), s.count),
            None => format!("{} -", slot.0.key()),
        };
    }
    // ── Active-buff timers. ──
    if let Ok(mut line) = buffline_q.single_mut() {
        **line = buffs
            .0
            .active_buffs(now)
            .iter()
            .map(|a| format!("{} {:.0}s", a.kind.label(), a.remain))
            .collect::<Vec<_>>()
            .join("    ");
    }

    // ── Toasts: dismiss the stale, then rebuild one [icon + text] row per live toast. ──
    let expired: Vec<i64> =
        toasts.0.toasts().iter().filter(|t| now - t.born >= 4.0).map(|t| t.id).collect();
    for id in expired {
        toasts.0.remove(id);
    }
    for e in &rows_q {
        commands.entity(e).despawn(); // clear last frame's rows (children go with them)
    }
    if let Ok(root) = toast_root_q.single() {
        commands.entity(root).with_children(|col| {
            for tt in toasts.0.toasts() {
                let name = item_def(&tt.item_id).map(|d| d.name).unwrap_or(tt.item_id.as_str());
                col.spawn((
                    Node {
                        flex_direction: FlexDirection::Row,
                        align_items: AlignItems::Center,
                        column_gap: Val::Px(6.0),
                        ..default()
                    },
                    ToastRow,
                ))
                .with_children(|row| {
                    if let Some(h) = atlas.get(&tt.item_id) {
                        row.spawn((
                            Node { width: Val::Px(22.0), height: Val::Px(22.0), ..default() },
                            ImageNode::new(h),
                        ));
                    }
                    row.spawn((
                        Text::new(format!("+{} {}", tt.count, name)),
                        TextFont { font_size: 18.0, ..default() },
                        TextColor(Color::srgb(0.95, 0.86, 0.5)),
                    ));
                });
            }
        });
    }
}

#[allow(clippy::type_complexity)]
fn update_hud(
    player: Res<PlayerRes>,
    bank: Res<crate::economy::Bank>,
    lives: Res<crate::succession::Lives>,
    hero_q: Query<&HeroHealth>,
    mut hp_q: Query<&mut Node, (With<HpFill>, Without<StaminaFill>, Without<XpFill>)>,
    mut st_q: Query<&mut Node, (With<StaminaFill>, Without<HpFill>, Without<XpFill>)>,
    mut xp_q: Query<&mut Node, (With<XpFill>, Without<HpFill>, Without<StaminaFill>)>,
    mut txt_q: Query<&mut Text, With<ResourceText>>,
) {
    let Ok(hh) = hero_q.single() else { return };
    let p = &player.0;
    let hp = (p.hp / p.max_hp * 100.0).clamp(0.0, 100.0) as f32;
    let st = (hh.stamina / hh.stamina_max * 100.0).clamp(0.0, 100.0);
    let xp = if p.xp_to_next > 0 {
        (p.xp as f32 / p.xp_to_next as f32 * 100.0).clamp(0.0, 100.0)
    } else {
        0.0
    };
    if let Ok(mut n) = hp_q.single_mut() {
        n.width = Val::Percent(hp);
    }
    if let Ok(mut n) = st_q.single_mut() {
        n.width = Val::Percent(st);
    }
    if let Ok(mut n) = xp_q.single_mut() {
        n.width = Val::Percent(xp);
    }
    if let Ok(mut t) = txt_q.single_mut() {
        **t = format!(
            "Lv {}   Gold {}   Stone {}   Heirs {}",
            p.level,
            p.gold,
            bank.0.stone() as i64,
            lives.heirs
        );
    }
}
