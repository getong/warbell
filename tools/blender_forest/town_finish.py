"""The last procedural town pieces, rebuilt from real parts (exec'd by town_kit.py after
yard_props.py, so the whole toolkit is in scope). Every piece: pivot on the ground at the centre of
its footprint, front toward +Z unless noted.

  meadow_fence        3.0 bay of split-rail paddock fence along local X: split posts at x -1.5 / 0,
                      three riven rails through mortises (pegged), reaching to x +1.55 where the
                      next bay's post stands. meadow_fence_post closes a run.
  castle_lantern      squared post in a stone-wedged footing, bracket arm (+X) with a brace, an iron
                      cage lantern hanging at (0.3, 1.36, 0) — the glowing pane is added by the game
                      (castle_decor.rs, the shared window-glow material).
  castle_ballista     torsion ballista on a timber sled, FIRES TOWARD -Z: capital frame with two
                      roped skein bundles + iron washers, bow arms, a drawn bowstring on the claw,
                      a loaded bolt in the groove (muzzle y ~0.8), windlass at the back. ~1.4 x 1.8.
  town_plot           build plot (half 1.55): sill beams lap-jointed on pad stones, corner survey
                      stakes with a string line + rag, a sign board, pegs, mallet.
  town_house_site     a half-raised dwelling frame 2.4 x 1.9 on a fieldstone footing: sills, posts,
                      braces, plates, king posts + ridge, the lumber stack (+Z), a ladder, sawhorse.
  town_rubble         a collapsed trade building at WORLD scale (~5.3 x 3.6): broken mortared
                      footing (-X), charred beams, slumped burnt roof, ash, scattered stones.
  decor_armory / decor_armory_veteran / decor_axe_display / decor_sword_display / decor_grindstone /
  decor_tax_booth / decor_shrine / decor_bounty_board / decor_scaffold (wall along +Z at x 0, deck
  at -X) / decor_stone_pile / decor_guild_banner / decor_guild_goods / decor_laundry
                      the castle upgrade set-pieces, same local layouts as castle_decor.rs.
  gate_leaf           plank gate leaf hinged at x 0 spanning +X (1.38 x 2.6, 0.14 thick):
                      vertical boards, ledges + a brace on -Z, two iron strap hinges, clench nails.
  gate_barricade      overturned hay-wain wedged across the gap (local X along the wall, 2.76):
                      bed on its side, two wheels at -Z, sharpened stakes leaning out at +Z.
"""

GREYW = (1.05, 1.0, 0.9)      # sun-greyed fence wood
OAKD = (0.9, 0.74, 0.56)       # oiled castle timber
IRN = (0.46, 0.44, 0.42)
HEMP = (0.9, 0.78, 0.56)


def nail_row(g, pts, n, s=0.018):
    """Clench-nail heads on a face with normal n."""
    n = Vector(n)
    for p in pts:
        lbox(g, Vector(p) + n * 0.004, (s, s, s), quat_y(0.0), M_IRON, (0.22, 0.21, 0.2), tile=0.2)


def strap(g, c, ldir, n, L, w=0.06, t=0.012, nails=3):
    """Flat iron strap along ldir lying on a face with normal n, nailed."""
    c, ldir, n = Vector(c), Vector(ldir).normalized(), Vector(n).normalized()
    beam(g, [c - ldir * L / 2, c + ldir * L / 2], w, t, up=tuple(n), mat=M_IRON, col=IRN, chamfer=0.2, mode="plank")
    nail_row(g, [c + ldir * (L * (k / max(1, nails - 1) - 0.5) * 0.85) + n * t / 2 for k in range(nails)], n)


def helix(g, a, b, r, turns, rr, col, sides=4):
    a, b = Vector(a), Vector(b)
    ax = (b - a)
    u = ax.normalized().orthogonal().normalized()
    v = ax.normalized().cross(u)
    k = int(turns * 10)
    pts = [a + ax * (i / k) + (u * math.cos(2 * math.pi * turns * i / k) + v * math.sin(2 * math.pi * turns * i / k)) * r
           for i in range(k + 1)]
    tube(g, pts, [rr] * len(pts), sides, M_CLOTH, col, tile=0.2, cap=False)


def grass_foot(g, rng, c, r=0.18):
    mound(g, (c[0], -0.02, c[2]), r, r * 0.9, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.55, 0.5, 0.4), rings=2,
          seg=10, rough=0.2)


# ─────────────────────────────────────────────────────────────── meadow fence
def _fence_post(g, rng, x):
    h = rng.uniform(1.0, 1.08)
    tint = scale(GREYW, rng.uniform(0.85, 1.02))
    beam(g, [V(x, -0.35, 0), V(x + rng.uniform(-0.02, 0.02), h, rng.uniform(-0.02, 0.02))], 0.14, 0.1, up=(0, 0, 1),
         mat=M_PLANK, chamfer=0.3, rough=0.1, jag=(0, 0.04), rng=rng, col_fn=weathered(tint, 0.78))
    grass_foot(g, rng, (x, 0, 0))
    for y in (0.3, 0.56, 0.82):
        tube(g, [V(x + 0.02, y + 0.07, -0.08), V(x + 0.02, y + 0.07, 0.08)], [0.012, 0.012], 5, M_PLANK,
             (0.66, 0.58, 0.48), tile=0.3)


def meadow_fence(rng):
    b = Builder()
    g = G(b)
    for x in (-1.5, 0.0):
        _fence_post(g, rng, x)
    for y in (0.3, 0.56, 0.82):
        for x0, x1, dz in ((-1.6, 0.1, 0.014), (-0.08, 1.58, -0.014)):
            mid = (x0 + x1) / 2
            tint = scale((0.74, 0.7, 0.62), rng.uniform(0.82, 1.02))
            pts = [V(x0, y + rng.uniform(-0.012, 0.012), dz), V(mid, y - rng.uniform(0.005, 0.025), dz),
                   V(x1, y + rng.uniform(-0.012, 0.012), dz)]
            # Riven (split) rails: a half-round section — flat split face and the bark-free back.
            beam(g, pts, 0.06, 0.085, mat=M_PLANK, chamfer=0.4, rough=0.22, rng=rng, col=tint)
    # A clump of long grass and a nettle tuft under the bottom rail.
    for k in range(5):
        x = rng.uniform(-1.3, 1.3)
        mound(g, (x, -0.02, rng.uniform(-0.1, 0.1)), 0.14, 0.1, 0.05, rng, mat=M_THATCH,
              col_fn=lambda p, n: (0.62, 0.66, 0.4), rings=2, seg=8, rough=0.35)
    return b


def meadow_fence_post(rng):
    b = Builder()
    g = G(b)
    _fence_post(g, rng, 0.0)
    return b


# ─────────────────────────────────────────────────────────────── lantern post
def castle_lantern(rng):
    b = Builder()
    g = G(b)
    beam(g, [V(0, -0.4, 0), V(0, 1.72, 0)], 0.12, 0.12, up=(0, 0, 1), mat=M_PLANK, chamfer=0.22, rough=0.05, rng=rng,
         col_fn=weathered(OAKD, 0.6))
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.2, 0.2)
        stone(g, V(math.cos(a) * 0.15, 0.0, math.sin(a) * 0.15), (0.09, 0.06, 0.08), rng, detail=1, rough=0.15,
              col_fn=rock_col((0.74, 0.72, 0.68), moss=0.2), tile=0.5)
    mound(g, (0, -0.02, 0), 0.32, 0.3, 0.05, rng, mat=M_EARTH, col_fn=lambda p, n: (0.56, 0.5, 0.42), rings=2, seg=10)
    # Arm through the post + brace, iron cap on the post top.
    beam(g, [V(-0.06, 1.62, 0), V(0.4, 1.62, 0)], 0.08, 0.08, mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(OAKD, 0.9))
    beam(g, [V(0.02, 1.32, 0), V(0.24, 1.6, 0)], 0.055, 0.05, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng,
         col=scale(OAKD, 0.85))
    lbox(g, V(0, 1.735, 0), (0.15, 0.025, 0.15), quat_y(0.0), M_IRON, IRN, tile=0.2)
    strap(g, V(0.2, 1.665, 0), (1, 0, 0), (0, 1, 0), 0.3, w=0.05, nails=2)
    # Hook + chain, then the lantern cage: top / bottom frames, four corner bars, pyramid hood, ring.
    tube(g, [V(0.3, 1.58, 0), V(0.3, 1.52, 0)], [0.01, 0.01], 4, M_IRON, IRN, tile=0.2)
    cx, cy = 0.3, 1.36
    hw, hh = 0.085, 0.11
    for y in (cy - hh, cy + hh):
        sq = [V(cx + sx * hw, y, sz * hw) for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))]
        tube(g, sq, [0.008] * 5, 4, M_IRON, IRN, tile=0.2, cap=False)
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        tube(g, [V(cx + sx * hw, cy - hh - 0.02, sz * hw), V(cx + sx * hw, cy + hh, sz * hw)], [0.009, 0.009], 4, M_IRON,
             IRN, tile=0.2)
    lathe(g, (cx, cy + hh, 0), (0, 1, 0), [(0.0, 0.12), (0.03, 0.1), (0.08, 0.02), (0.09, 0.0)], 4, M_IRON, IRN, tile=0.2)
    lbox(g, V(cx, cy - hh - 0.005, 0), (0.17, 0.012, 0.17), quat_y(0.0), M_IRON, IRN, tile=0.2)
    helix(g, V(cx, cy + hh + 0.09, 0), V(cx, cy + hh + 0.16, 0), 0.02, 1.2, 0.006, IRN)
    return b


# ─────────────────────────────────────────────────────────────── ballista
def castle_ballista(rng):
    b = Builder()
    g = G(b)
    W = scale(OAKD, 1.05)
    # Sled: two runners on stones, three transoms, iron-strapped joints.
    for sx in (-0.45, 0.45):
        beam(g, [V(sx, 0.1, 0.9), V(sx, 0.1, -0.8)], 0.14, 0.16, mat=M_PLANK, chamfer=0.2, rough=0.05, rng=rng,
             col=scale(W, 0.85))
        for z in (-0.6, 0.65):
            stone(g, V(sx, -0.02, z), (0.12, 0.06, 0.1), rng, detail=1, rough=0.12,
                  col_fn=rock_col((0.74, 0.72, 0.68), moss=0.15), tile=0.5)
    for z in (-0.55, 0.05, 0.62):
        beam(g, [V(-0.6, 0.24, z), V(0.6, 0.24, z)], 0.12, 0.12, mat=M_PLANK, chamfer=0.2, rng=rng, col=W)
        for sx in (-0.45, 0.45):
            strap(g, V(sx, 0.3, z), (0, 0, 1), (0, 1, 0), 0.26, w=0.05, nails=2)
    # Trestle: two raked legs each side up to the stock.
    for sx in (-0.16, 0.16):
        beam(g, [V(sx * 2.2, 0.28, 0.45), V(sx, 0.7, 0.05)], 0.08, 0.08, mat=M_PLANK, chamfer=0.2, rng=rng, col=W)
        beam(g, [V(sx * 2.2, 0.28, -0.4), V(sx, 0.7, 0.05)], 0.08, 0.08, mat=M_PLANK, chamfer=0.2, rng=rng, col=W)
    lbox(g, V(0, 0.71, 0.05), (0.4, 0.06, 0.14), quat_y(0.0), M_TIMBER, scale(W, 0.8), tile=0.3)
    # Stock (case) with the bolt groove, slightly nose-down; slider rails.
    q = quat_x(-0.04)
    S = V(0, 0.78, 0.05)
    for sx in (-0.065, 0.065):
        beam(g, [S + q @ V(sx, 0, 0.82), S + q @ V(sx, 0, -0.95)], 0.07, 0.11, mat=M_PLANK, chamfer=0.15, rng=rng, col=W)
    lbox(g, S + q @ V(0, -0.04, -0.06), (0.06, 0.03, 1.7), q, M_TIMBER, scale(W, 0.7), tile=0.3)
    for z in (-0.75, -0.2, 0.4):
        strap(g, S + q @ V(0, 0.058, z), (1, 0, 0), (0, 1, 0), 0.2, w=0.04, nails=2)
    # Capital frame at the front: two horizontal beams, four uprights, the skein bundles in it.
    F = S + q @ V(0, 0.0, -0.62)
    for dy in (-0.22, 0.22):
        beam(g, [F + V(-0.48, dy, 0), F + V(0.48, dy, 0)], 0.12, 0.1, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=scale(W, 0.9))
    for sx in (-0.44, -0.12, 0.12, 0.44):
        beam(g, [F + V(sx, -0.22, 0), F + V(sx, 0.22, 0)], 0.07, 0.1, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=scale(W, 0.85))
    for sx in (-1, 1):
        x = sx * 0.28
        lathe(g, F + V(x, -0.08, 0), (0, 1, 0), [(0.0, 0.085), (0.16, 0.085)], 10, M_CLOTH, scale(HEMP, 0.85), tile=0.2)
        helix(g, F + V(x, -0.08, 0), F + V(x, 0.08, 0), 0.088, 6, 0.012, HEMP)
        for dy in (-0.3, 0.3):
            lathe(g, F + V(x, dy - 0.02, 0), (0, 1, 0), [(0.0, 0.1), (0.04, 0.1), (0.04, 0.0)], 10, M_IRON, IRN, tile=0.2)
            lbox(g, F + V(x, dy + 0.03, 0), (0.22, 0.03, 0.04), quat_y(0.0), M_IRON, IRN, tile=0.2)
        # Bow arm swept back from the skein, a horn nock at the tip.
        tip = F + V(sx * 0.78, 0.0, 0.38)
        beam(g, [F + V(x, 0, 0), F + V(sx * 0.55, 0.0, 0.14), tip], 0.07, 0.06, mat=M_PLANK, chamfer=0.25, rng=rng,
             col=scale(W, 0.75))
        lathe(g, tip, (sx * 0.8, 0, 0.6), [(0.0, 0.035), (0.06, 0.02), (0.08, 0.0)], 6, M_TIMBER, (0.9, 0.86, 0.74),
              tile=0.2)
        # Bowstring to the claw (drawn back, loaded).
        claw = S + q @ V(0, 0.08, 0.35)
        tube(g, [tip, claw], [0.009, 0.009], 4, M_CLOTH, (0.82, 0.72, 0.52), tile=0.2)
    # Claw / trigger block on the slider, the bolt in the groove (iron pyramid head, wooden vanes).
    lbox(g, S + q @ V(0, 0.08, 0.38), (0.1, 0.07, 0.12), q, M_IRON, IRN, tile=0.2)
    bolt_a = S + q @ V(0, 0.085, 0.32)
    bolt_b = S + q @ V(0, 0.085, -1.0)
    pole(g, bolt_a, bolt_b, 0.022, 0.024, rng, mat=M_TIMBER, col=(0.82, 0.7, 0.52), sides=6, wobble=0.0, segs=1)
    lathe(g, bolt_b, tuple(bolt_b - bolt_a), [(0.0, 0.035), (0.14, 0.0)], 4, M_IRON, (0.4, 0.38, 0.36), tile=0.2)
    for a in (0.0, math.pi / 2):
        lbox(g, bolt_a + (bolt_b - bolt_a).normalized() * 0.1, (0.11, 0.003, 0.14), q @ quat_z(a), M_HIDE,
             (0.86, 0.8, 0.7), tile=0.2)
    # Windlass at the back: axle between two cheeks, crossed handspikes, rope to the claw.
    Wd = S + q @ V(0, -0.02, 0.78)
    for sx in (-0.2, 0.2):
        beam(g, [Wd + V(sx, -0.12, 0), Wd + V(sx, 0.1, 0)], 0.05, 0.12, up=(1, 0, 0), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=W)
    pole(g, Wd + V(-0.3, 0, 0), Wd + V(0.3, 0, 0), 0.045, 0.045, rng, mat=M_TIMBER, col=scale(W, 0.8), sides=8,
         wobble=0.0, segs=1)
    helix(g, Wd + V(-0.1, 0, 0), Wd + V(0.1, 0, 0), 0.05, 5, 0.011, HEMP)
    for sx in (-0.3, 0.3):
        for a in (0.4, 0.4 + math.pi / 2):
            d = V(0, math.cos(a), math.sin(a)) * 0.22
            pole(g, Wd + V(sx, 0, 0) - d, Wd + V(sx, 0, 0) + d, 0.016, 0.016, rng, mat=M_TIMBER, col=W, sides=5,
                 wobble=0.0, segs=1)
    tube(g, [Wd + V(0, 0.05, 0), S + q @ V(0, 0.09, 0.42)], [0.01, 0.01], 4, M_CLOTH, HEMP, tile=0.2)
    # Spare bolts in a bundle on the sled, trampled earth.
    for k in range(3):
        p = V(0.35 + k * 0.05, 0.33, 0.3)
        pole(g, p + V(0, 0, 0.45), p + V(0, 0, -0.45), 0.018, 0.018, rng, mat=M_TIMBER, col=(0.8, 0.68, 0.5), sides=5,
             wobble=0.0, segs=1)
    mound(g, (0, -0.03, 0.05), 1.0, 1.15, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.58, 0.5, 0.42), rings=3,
          seg=16, rough=0.15)
    return b


# ─────────────────────────────────────────────────────────────── plots / house site / rubble
def town_plot(rng):
    b = Builder()
    g = G(b)
    r = 1.55
    # Pad stones under the corners and mid-sides, sunk.
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
        stone(g, V(sx * r, 0.0, sz * r), (0.17, 0.08, 0.15), rng, detail=1, rough=0.14, flat_y=0.6,
              col_fn=rock_col((0.76, 0.74, 0.7), moss=0.15), tile=0.5)
    # Sill beams, lap-jointed (ends run past each other), adze-squared.
    for sz in (-r, r):
        beam(g, [V(-r - 0.16, 0.13, sz), V(r + 0.16, 0.13, sz)], 0.16, 0.14, mat=M_PLANK, chamfer=0.18, rough=0.06,
             rng=rng, col=scale(OAKD, rng.uniform(0.95, 1.1)))
    for sx in (-r, r):
        beam(g, [V(sx, 0.2, -r - 0.16), V(sx, 0.2, r + 0.16)], 0.16, 0.14, mat=M_PLANK, chamfer=0.18, rough=0.06,
             rng=rng, col=scale(OAKD, rng.uniform(0.95, 1.1)))
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        tube(g, [V(sx * r, 0.3, sz * r), V(sx * r, 0.05, sz * r)], [0.018, 0.018], 6, M_TIMBER, (0.6, 0.5, 0.4), tile=0.2)
    # Survey stakes just outside the corners, a string line round them, a rag on one.
    stakes = []
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p = V(sx * (r + 0.28), 0, sz * (r + 0.28))
        top = p + V(sx * 0.03, 0.58, sz * 0.03)
        beam(g, [p + V(0, -0.2, 0), top], 0.05, 0.05, mat=M_PLANK, chamfer=0.2, point=0.0, rng=rng, col=(0.86, 0.76, 0.6))
        stakes.append(top - V(0, 0.08, 0))
    tube(g, stakes + [stakes[0]], [0.005] * 5, 3, M_CLOTH, (0.95, 0.88, 0.7), tile=0.2, cap=False)
    banner = stakes[0] + V(0, 0.06, 0)
    lbox(g, banner + V(0.08, -0.03, 0), (0.16, 0.1, 0.004), quat_y(0.6) @ quat_z(-0.2), M_CLOTH, (0.62, 0.12, 0.1),
         tile=0.2)
    # Sign: post + a board with a charcoal mark.
    px, pz = r - 0.2, -r - 0.45
    beam(g, [V(px, -0.3, pz), V(px, 0.95, pz)], 0.08, 0.08, mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(OAKD, 1.1))
    board(g, V(px, 0.78, pz + 0.05), (1, 0, 0), (0, 0, 1), 0.58, 0.3, 0.03, mat=M_PLANK, col=(0.78, 0.68, 0.54), rng=rng)
    lbox(g, V(px, 0.78, pz + 0.068), (0.24, 0.03, 0.002), quat_z(0.2), M_FRUIT, (0.08, 0.07, 0.06), tile=0.2)
    lbox(g, V(px, 0.78, pz + 0.068), (0.24, 0.03, 0.002), quat_z(-0.2), M_FRUIT, (0.08, 0.07, 0.06), tile=0.2)
    nail_row(g, [V(px - 0.22, 0.86, pz + 0.07), V(px + 0.22, 0.86, pz + 0.07)], (0, 0, 1))
    # A maul and a few spare pegs left on the sill; a spoil heap from the post holes.
    pole(g, V(-0.6, 0.23, r + 0.05), V(-0.1, 0.23, r + 0.25), 0.018, 0.018, rng, mat=M_TIMBER, col=(0.8, 0.7, 0.55),
         sides=5, wobble=0.0, segs=1)
    lathe(g, (-0.66, 0.23, r + 0.03), (-1, 0, -0.4), [(0.0, 0.07), (0.18, 0.07)], 8, M_BARK, (0.7, 0.62, 0.52), tile=0.3)
    mound(g, (r + 0.6, -0.02, 0.6), 0.4, 0.3, 0.14, rng, mat=M_EARTH, col_fn=lambda p, n: (0.58, 0.48, 0.38), rings=3,
          seg=12, rough=0.2)
    return b


def town_house_site(rng):
    b = Builder()
    g = G(b)
    w, d = 2.4, 1.9
    hx, hz = w / 2, d / 2
    T = OAKD
    mound(g, (0, -0.06, 0), hx + 0.35, hz + 0.35, 0.08, rng, mat=M_EARTH, col_fn=lambda p, n: (0.66, 0.58, 0.48),
          rings=3, seg=18, rough=0.08)
    # Fieldstone footing course under the sills, mortar-bedded.
    for sz in (-hz, hz):
        for k in range(9):
            x = -hx + k * w / 8
            stone(g, V(x, 0.06, sz), (0.15, 0.08, 0.12), rng, detail=1, rough=0.12, flat_y=0.7,
                  col_fn=rock_col((0.78, 0.76, 0.72), moss=0.05), tile=0.5)
    for sx in (-hx, hx):
        for k in range(1, 7):
            z = -hz + k * d / 7
            stone(g, V(sx, 0.06, z), (0.12, 0.08, 0.15), rng, detail=1, rough=0.12, flat_y=0.7,
                  col_fn=rock_col((0.78, 0.76, 0.72), moss=0.05), tile=0.5)
    for sz in (-hz, hz):
        lbox(g, V(0, 0.08, sz), (w + 0.1, 0.1, 0.18), quat_y(0.0), M_EARTH, (0.85, 0.82, 0.76), tile=0.5)
    for sx in (-hx, hx):
        lbox(g, V(sx, 0.08, 0), (0.18, 0.1, d + 0.1), quat_y(0.0), M_EARTH, (0.85, 0.82, 0.76), tile=0.5)
    sill_y, post_h = 0.2, 1.0
    plate_y = sill_y + post_h
    for sz in (-hz, hz):
        beam(g, [V(-hx - 0.12, sill_y, sz), V(hx + 0.12, sill_y, sz)], 0.15, 0.15, mat=M_PLANK, chamfer=0.15, rough=0.05,
             rng=rng, col=T)
        beam(g, [V(-hx - 0.12, plate_y, sz), V(hx + 0.12, plate_y, sz)], 0.13, 0.13, mat=M_PLANK, chamfer=0.15,
             rng=rng, col=T)
    for sx in (-hx, hx):
        beam(g, [V(sx, sill_y + 0.01, -hz - 0.12), V(sx, sill_y + 0.01, hz + 0.12)], 0.15, 0.15, mat=M_PLANK,
             chamfer=0.15, rough=0.05, rng=rng, col=T)
        beam(g, [V(sx, plate_y + 0.01, -hz - 0.1), V(sx, plate_y + 0.01, hz + 0.1)], 0.13, 0.13, mat=M_PLANK,
             chamfer=0.15, rng=rng, col=T)
        for sz in (-hz, hz):
            beam(g, [V(sx, sill_y, sz), V(sx, plate_y, sz)], 0.13, 0.13, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15,
                 rng=rng, col_fn=weathered(T, 0.85))
            # Corner brace.
            beam(g, [V(sx, sill_y + 0.45, sz), V(sx - math.copysign(0.42, sx), plate_y - 0.04, sz)], 0.08, 0.07,
                 up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng, col=scale(T, 0.9))
        # King post + ridge (along X).
        beam(g, [V(sx, plate_y, 0), V(sx, plate_y + 0.62, 0)], 0.1, 0.1, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15,
             rng=rng, col=T)
        for sz in (-hz, hz):
            beam(g, [V(sx, plate_y + 0.04, sz), V(sx, plate_y + 0.6, 0)], 0.09, 0.08, up=(1, 0, 0), mat=M_PLANK,
                 chamfer=0.15, rng=rng, col=scale(T, 0.95))
    beam(g, [V(-hx - 0.2, plate_y + 0.66, 0), V(hx + 0.2, plate_y + 0.66, 0)], 0.1, 0.1, mat=M_PLANK, chamfer=0.15,
         rng=rng, col=T)
    for sx in (-0.4, 0.4):
        beam(g, [V(sx, sill_y, -hz), V(sx, plate_y, -hz)], 0.1, 0.1, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15, rng=rng,
             col=scale(T, 1.05))
    # Lumber waiting at the front: squared beams on bearers, a ladder against the frame, sawhorse.
    lz = hz + 0.5
    for x in (-0.95, 0.15):
        pole(g, V(x - 0.3, 0.04, lz - 0.3), V(x - 0.3, 0.04, lz + 0.3), 0.05, 0.05, rng, col=(0.7, 0.62, 0.52), sides=6,
             wobble=0.0, segs=1)
    for (n, y) in ((3, 0.15), (2, 0.31)):
        for i in range(n):
            z = lz + (i - (n - 1) / 2) * 0.17
            beam(g, [V(-1.25, y, z), V(0.05 + rng.uniform(-0.05, 0.05), y, z)], 0.15, 0.15, mat=M_PLANK, chamfer=0.1,
                 rough=0.05, rng=rng, col=scale((0.86, 0.72, 0.56), rng.uniform(0.9, 1.05)))
    ladder(g, rng, V(hx + 0.5, 0.0, -0.3), V(hx + 0.04, plate_y + 0.25, -0.3), width=0.4)
    for sx in (0.75, 1.15):
        for sz in (-1, 1):
            pole(g, V(sx, 0.0, lz + sz * 0.2), V(sx, 0.48, lz), 0.025, 0.022, rng, col=(0.78, 0.68, 0.54), sides=5,
                 segs=1)
    pole(g, V(0.65, 0.5, lz), V(1.25, 0.5, lz), 0.05, 0.05, rng, mat=M_TIMBER, col=(0.82, 0.7, 0.54), sides=6,
         wobble=0.0, segs=1)
    # Woodchips under the sawhorse.
    mound(g, (0.95, -0.02, lz), 0.4, 0.3, 0.03, rng, mat=M_THATCH, col_fn=lambda p, n: (1.1, 0.92, 0.66), rings=2,
          seg=10, rough=0.3)
    return b


def town_rubble(rng):
    """World-scale ruin of a trade building (attached under the plot's WORLD_BUMP root with the
    inverse scale). Breached mortared footing on the -X half, charred beams, slumped burnt roof."""
    b = Builder()
    g = G(b)
    cx = -1.28
    hw, hd = 1.3, 1.1
    mound(g, (0, -0.05, 0), 2.7, 1.85, 0.06, rng, mat=M_EARTH, col_fn=lambda p, n: (0.62, 0.56, 0.48), rings=4, seg=22,
          rough=0.1)
    mound(g, (cx, -0.02, 0), 1.25, 1.0, 0.12, rng, mat=M_EARTH, col_fn=lambda p, n: (0.4, 0.36, 0.33), rings=4,
          seg=18, rough=0.25)
    # Footing walls: courses of stones, broken down to stumps unevenly, mortar between.
    walls = [((cx - hw, -hd), (cx + hw, -hd)), ((cx + hw, -hd), (cx + hw, hd)), ((cx + hw, hd), (cx - hw, hd)),
             ((cx - hw, hd), (cx - hw, -hd))]
    for (x0, z0), (x1, z1) in walls:
        L = math.hypot(x1 - x0, z1 - z0)
        n = int(L / 0.26)
        for k in range(n):
            f = (k + 0.5) / n
            x, z = x0 + (x1 - x0) * f, z0 + (z1 - z0) * f
            h_courses = max(0, int(2.6 * (0.5 + 0.5 * math.sin(f * 7.0 + x * 2.0)) + rng.uniform(-0.6, 0.6)))
            for c in range(h_courses + 1):
                stone(g, V(x + rng.uniform(-0.03, 0.03), 0.07 + c * 0.14, z + rng.uniform(-0.03, 0.03)),
                      (0.14, 0.075, 0.12), rng, detail=1, rough=0.12, flat_y=0.7,
                      col_fn=rock_col((0.62, 0.6, 0.56), moss=0.05, ground=0.3), tile=0.5)
            if h_courses > 0:
                lbox(g, V(x, 0.06 + h_courses * 0.07, z), (0.24 if x0 != x1 else 0.2, h_courses * 0.14, 0.2 if x0 != x1 else 0.24),
                     quat_y(0.0), M_EARTH, (0.7, 0.68, 0.62), tile=0.5)
    # Tumbled stones outside the line.
    for k in range(14):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(1.0, 1.7)
        stone(g, V(cx + math.cos(a) * rr * 1.1, 0.04, math.sin(a) * rr * 0.9), (0.13, 0.08, 0.11), rng, detail=1,
              rough=0.15, col_fn=rock_col((0.6, 0.58, 0.54), moss=0.1, ground=0.3), tile=0.5)
    # Charred beams, fallen across and propped on the footing; one post still standing, burnt off.
    for (x, z, L, ya, pitch) in ((cx, 0.1, 2.4, 0.4, 0.06), (cx + 0.5, -0.3, 1.6, -0.65, 0.12), (cx - 0.3, 0.8, 1.8, -0.3, 0.0),
                                  (0.5, 0.25, 1.1, 0.95, -0.15), (cx - 0.7, -0.5, 1.3, 1.3, 0.2)):
        d = V(math.cos(ya), math.sin(pitch), -math.sin(ya)) * (L / 2)
        c = V(x, 0.18, z)
        beam(g, [c - d, c + d], 0.16, 0.15, mat=M_BARK, mode="bark", chamfer=0.25, rough=0.12, jag=(0.08, 0.1), rng=rng,
             col=charred(rng))
    beam(g, [V(cx + hw, 0.1, hd), V(cx + hw + 0.04, 1.05, hd + 0.03)], 0.16, 0.16, up=(0, 0, 1), mat=M_BARK, mode="bark",
         chamfer=0.25, rough=0.1, jag=(0, 0.18), rng=rng, col=charred(rng))
    beam(g, [V(cx - hw, 0.1, -hd), V(cx - hw - 0.03, 0.62, -hd)], 0.16, 0.16, up=(0, 0, 1), mat=M_BARK, mode="bark",
         chamfer=0.25, rough=0.1, jag=(0, 0.14), rng=rng, col=charred(rng))
    # The slumped roof: burnt thatch mats and a few blackened rafters.
    for (x, z, ya, rx, rz) in ((cx - 0.25, 0.0, 0.3, 0.9, 0.7), (cx + 0.6, 0.45, -0.4, 0.6, 0.5)):
        slab(g, V(x, 0.2, z), (rx * 2, 0.18, rz * 2), quat_y(ya) @ quat_x(0.08), rng, mat=M_THATCH, res=(4, 2, 4),
             round_r=0.08, rough=0.25, col_fn=lambda p, n: (0.2, 0.17, 0.14) if n.y > 0.3 else (0.12, 0.1, 0.09), tile=0.5)
    for k in range(5):
        a = rng.uniform(-0.6, 0.6)
        p0 = V(cx - 0.8 + k * 0.4, 0.15, -0.6)
        pole(g, p0, p0 + V(math.sin(a) * 0.9, 0.25, 1.0), 0.04, 0.035, rng, col=charred(rng), sides=5, segs=1)
    # A scorched barrel staved in and a cart wheel lying in the yard (+X).
    for k in range(7):
        a = 2 * math.pi * k / 7
        lbox(g, V(1.4 + math.cos(a) * 0.2, 0.05 + 0.12 * (k % 2), -0.6 + math.sin(a) * 0.2), (0.07, 0.03, 0.45),
             quat_y(a) @ quat_x(0.3), M_TIMBER, scale((0.5, 0.4, 0.32), rng.uniform(0.5, 0.9)), tile=0.4)
    cart_wheel(g, rng, V(1.5, 0.05, 0.7), (0.15, 1, 0.1), r=0.42, col=(0.45, 0.38, 0.3))
    # Ash drifts.
    for k in range(4):
        mound(g, (cx + rng.uniform(-0.8, 0.8), 0.04, rng.uniform(-0.6, 0.6)), 0.4, 0.3, 0.05, rng, mat=M_EARTH,
              col_fn=lambda p, n: (0.5, 0.48, 0.46), rings=2, seg=10, rough=0.3)
    return b


# ─────────────────────────────────────────────────────────────── castle upgrade set-pieces
def _post(g, rng, x, z, h, w=0.1, col=OAKD, foot=True):
    beam(g, [V(x, -0.3, z), V(x, h, z)], w, w, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rough=0.04, rng=rng,
         col_fn=weathered(col, 0.8))
    if foot:
        grass_foot(g, rng, (x, 0, z), 0.13)


def _spear(g, rng, foot, top):
    foot, top = Vector(foot), Vector(top)
    pole(g, foot, top, 0.018, 0.016, rng, mat=M_TIMBER, col=(0.82, 0.68, 0.5), sides=6, wobble=0.0, segs=1)
    d = (top - foot).normalized()
    lathe(g, top - d * 0.02, tuple(d), [(0.0, 0.025), (0.06, 0.04), (0.2, 0.0)], 4, M_IRON, (0.92, 0.92, 0.95),
          tile=0.2)


def _armor_stand(g, rng, x, steel=False):
    _post(g, rng, x, 0.0, 1.05, w=0.08)
    beam(g, [V(x - 0.33, 0.82, 0), V(x + 0.33, 0.82, 0)], 0.07, 0.07, mat=M_PLANK, chamfer=0.2, rng=rng, col=OAKD)
    for sz in (-1, 1):
        pole(g, V(x, 0.0, sz * 0.32), V(x, 0.3, 0), 0.025, 0.025, rng, mat=M_TIMBER, col=OAKD, sides=5, segs=1)
    if steel:
        lathe(g, (x, 0.5, 0), (0, 1, 0), [(0.0, 0.2), (0.2, 0.24), (0.36, 0.25), (0.48, 0.22), (0.52, 0.1)], 10, M_IRON,
              (0.95, 0.95, 0.98), tile=0.4)
        for sx in (-1, 1):
            lathe(g, (x + sx * 0.26, 0.92, 0), (sx, 0.3, 0), [(0.0, 0.11), (0.08, 0.1), (0.12, 0.0)], 8, M_IRON,
                  (0.92, 0.92, 0.95), tile=0.3)
        lathe(g, (x, 1.04, 0), (0, 1, 0), [(0.0, 0.12), (0.12, 0.125), (0.2, 0.09), (0.25, 0.0)], 10, M_IRON,
              (0.9, 0.9, 0.93), tile=0.3)
        lbox(g, V(x, 1.31, 0), (0.025, 0.1, 0.2), quat_y(0.0), M_CLOTH, CRIMSON, tile=0.2)
    else:
        lathe(g, (x, 0.48, 0), (0, 1, 0), [(0.0, 0.19), (0.22, 0.23), (0.4, 0.24), (0.52, 0.2), (0.55, 0.1)], 10, M_HIDE,
              (0.62, 0.46, 0.32), tile=0.3)
        for y in (0.62, 0.78, 0.9):
            tube(g, [V(x + 0.24 * math.cos(a), y, 0.24 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 13)],
                 [0.008] * 13, 3, M_HIDE, (0.4, 0.3, 0.22), tile=0.2, cap=False)
        kettle_helm(g, rng, (x, 1.06, 0), s=0.8)


def decor_armory(rng):
    b = Builder()
    g = G(b)
    for sx in (-0.58, 0.58):
        _post(g, rng, sx, 0.0, 1.12)
    beam(g, [V(-0.7, 1.05, 0), V(0.7, 1.05, 0)], 0.09, 0.08, mat=M_PLANK, chamfer=0.2, rng=rng, col=OAKD)
    beam(g, [V(-0.7, 0.3, 0.07), V(0.7, 0.3, 0.07)], 0.08, 0.07, mat=M_PLANK, chamfer=0.2, rng=rng, col=OAKD)
    for k in range(5):
        x = -0.44 + k * 0.22
        lbox(g, V(x, 1.05, 0.05), (0.04, 0.05, 0.06), quat_y(0.0), M_TIMBER, scale(OAKD, 0.8), tile=0.2)
        _spear(g, rng, V(x + rng.uniform(-0.03, 0.03), 0.02, 0.1), V(x + rng.uniform(-0.08, 0.08), 1.62, -0.03))
    for sx, tilt in ((-0.4, 0.25), (0.36, -0.15)):
        round_shield(g, V(sx, 0.3, 0.32), (0, math.sin(0.35), math.cos(0.35)), 0.27, (0.7, 0.58, 0.44),
                     (0.55, 0.12, 0.1) if sx < 0 else (0.85, 0.8, 0.7))
    _armor_stand(g, rng, 1.15)
    mound(g, (0.3, -0.03, 0.05), 1.3, 0.55, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.6, 0.52, 0.42), rings=2,
          seg=14)
    return b


def decor_armory_veteran(rng):
    b = Builder()
    g = G(b)
    for sx in (-0.52, 0.52):
        _post(g, rng, sx, 0.0, 0.86)
    beam(g, [V(-0.62, 0.82, 0), V(0.62, 0.82, 0)], 0.12, 0.09, mat=M_PLANK, chamfer=0.2, rng=rng, col=OAKD)
    beam(g, [V(-0.62, 0.18, 0), V(0.62, 0.18, 0)], 0.12, 0.07, mat=M_PLANK, chamfer=0.2, rng=rng, col=OAKD)
    for k in range(4):
        x = -0.33 + k * 0.22
        # Blade (fullered), cross-guard, leather grip, pommel; point down in the bottom rail.
        lbox(g, V(x, 0.5, 0), (0.05, 0.62, 0.012), quat_y(0.0), M_IRON, (1.05, 1.06, 1.1), tile=0.3)
        lbox(g, V(x, 0.84, 0), (0.17, 0.03, 0.035), quat_y(0.0), M_IRON, (0.4, 0.36, 0.3), tile=0.2)
        pole(g, V(x, 0.85, 0), V(x, 0.98, 0), 0.02, 0.018, rng, mat=M_HIDE, col=(0.4, 0.28, 0.2), sides=6, wobble=0.0,
             segs=1)
        lathe(g, (x, 0.98, 0), (0, 1, 0), [(0.0, 0.03), (0.03, 0.03), (0.05, 0.0)], 6, M_IRON, (0.4, 0.36, 0.3), tile=0.2)
    _armor_stand(g, rng, 1.05, steel=True)
    for k, sx in enumerate((-0.35, 0.05, 0.42)):
        round_shield(g, V(sx, 0.28, -0.25), (0, math.sin(0.3), -math.cos(0.3)), 0.25, (0.7, 0.66, 0.6),
                     (0.92, 0.92, 0.95))
    return b


def decor_axe_display(rng):
    b = Builder()
    g = G(b)
    slab(g, V(0, 0.07, 0), (0.56, 0.14, 0.42), quat_y(0.0), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.03, rough=0.03,
         col_fn=lambda p, n: (0.6, 0.58, 0.56), tile=0.5)
    _post(g, rng, 0.0, -0.08, 1.0, w=0.1, foot=False)
    for y in (0.55, 0.85):
        tube(g, [V(-0.12, y, -0.02), V(0.12, y, -0.02)], [0.015, 0.015], 5, M_TIMBER, scale(OAKD, 0.8), tile=0.2)
    q = quat_z(0.5)
    o = V(0.0, 0.18, 0.04)
    pole(g, o + q @ V(0, 0.0, 0), o + q @ V(0, 1.1, 0), 0.025, 0.022, rng, mat=M_TIMBER, col=(0.78, 0.62, 0.44), sides=6,
         wobble=0.0, segs=1)
    # Bearded axe head: a wedge with a curved beard, socket round the haft.
    h = o + q @ V(0, 0.98, 0)
    pts = [h + q @ V(0.0, 0.08, 0), h + q @ V(-0.3, 0.12, 0), h + q @ V(-0.34, -0.05, 0), h + q @ V(-0.18, -0.16, 0),
           h + q @ V(0.0, -0.06, 0)]
    face(g, [p + V(0, 0, 0.012) for p in pts], V(0, 0, 1), M_IRON, (0.5, 0.5, 0.52), tile=0.3)
    face(g, [p - V(0, 0, 0.012) for p in pts], V(0, 0, -1), M_IRON, (0.5, 0.5, 0.52), tile=0.3)
    for i in range(len(pts)):
        a_, b_ = pts[i], pts[(i + 1) % len(pts)]
        face(g, [a_ + V(0, 0, 0.012), b_ + V(0, 0, 0.012), b_ - V(0, 0, 0.012), a_ - V(0, 0, 0.012)],
             (b_ - a_).cross(V(0, 0, 1)), M_IRON, (0.95, 0.95, 0.98), tile=0.3)
    lathe(g, h - q @ V(0, 0.08, 0), tuple(q @ V(0, 1, 0)), [(0.0, 0.04), (0.16, 0.04)], 6, M_IRON, (0.4, 0.4, 0.42),
          tile=0.2)
    return b


def decor_sword_display(rng):
    b = Builder()
    g = G(b)
    slab(g, V(0, 0.07, 0), (0.5, 0.14, 0.4), quat_y(0.0), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.03, rough=0.03,
         col_fn=lambda p, n: (0.58, 0.56, 0.54), tile=0.5)
    slab(g, V(0, 0.19, 0), (0.3, 0.1, 0.3), quat_y(0.0), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.02, rough=0.02,
         col_fn=lambda p, n: (0.85, 0.82, 0.76), tile=0.5)
    # Upright gilded blade, point up, the grip sunk in the socket.
    lbox(g, V(0, 0.72, 0), (0.07, 0.85, 0.014), quat_y(0.0), M_IRON, (1.25, 0.95, 0.45), tile=0.3)
    lathe(g, (0, 1.145, 0), (0, 1, 0), [(0.0, 0.035), (0.06, 0.0)], 4, M_IRON, (1.25, 0.95, 0.45), tile=0.2)
    beam(g, [V(-0.15, 0.31, 0), V(0.15, 0.31, 0)], 0.05, 0.04, mat=M_IRON, col=(1.1, 0.82, 0.4), chamfer=0.3,
         mode="plank")
    pole(g, V(0, 0.23, 0), V(0, 0.3, 0), 0.022, 0.022, rng, mat=M_HIDE, col=(0.45, 0.12, 0.1), sides=6, wobble=0.0,
         segs=1)
    return b


def decor_grindstone(rng):
    b = Builder()
    g = G(b)
    # A-frame trestles each side (along Z), axle across, the wheel in a water trough.
    for sz in (-0.24, 0.24):
        for sx in (-1, 1):
            beam(g, [V(sx * 0.32, 0.0, sz), V(sx * 0.04, 0.62, sz)], 0.07, 0.07, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2,
                 rng=rng, col=OAKD)
        beam(g, [V(-0.24, 0.22, sz), V(0.24, 0.22, sz)], 0.06, 0.05, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=OAKD)
    lathe(g, (0, 0.55, -0.065), (0, 0, 1), [(0.0, 0.33), (0.02, 0.345), (0.11, 0.345), (0.13, 0.33), (0.13, 0.0)], 18,
          M_ROCK, (0.82, 0.78, 0.7), tile=0.5)
    pole(g, V(0, 0.55, -0.34), V(0, 0.55, 0.34), 0.03, 0.03, rng, mat=M_IRON, col=IRN, sides=6, wobble=0.0, segs=1)
    tube(g, [V(0, 0.55, 0.34), V(0, 0.75, 0.36), V(0.05, 0.75, 0.5)], [0.015] * 3, 5, M_IRON, IRN, tile=0.2)
    lbox(g, V(0, 0.2, 0), (0.62, 0.16, 0.3), quat_y(0.0), M_TIMBER, scale(OAKD, 0.85), tile=0.4)
    lbox(g, V(0, 0.27, 0), (0.56, 0.02, 0.24), quat_y(0.0), M_EARTH, (0.06, 0.07, 0.07), tile=0.4)
    board(g, V(0.0, 0.62, 0.28), (1, 0, 0), (0, 1, 0), 0.32, 0.09, 0.04, mat=M_PLANK, col=OAKD, rng=rng)
    lathe(g, (0.52, 0.0, 0.2), (0, 1, 0), [(0.0, 0.12), (0.24, 0.15)], 10, M_TIMBER, (0.7, 0.58, 0.44), tile=0.3)
    for y in (0.05, 0.19):
        tube(g, [V(0.52 + (0.125 + y * 0.12) * math.cos(a), y, 0.2 + (0.125 + y * 0.12) * math.sin(a))
                 for a in np.linspace(0, 2 * math.pi, 11)], [0.008] * 11, 3, M_IRON, IRN, tile=0.2, cap=False)
    mound(g, (0.1, -0.03, 0.05), 0.75, 0.5, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.4, 0.36, 0.32), rings=2,
          seg=12)
    return b


def decor_tax_booth(rng):
    b = Builder()
    g = G(b)
    for sx, sz in ((-0.65, -0.35), (0.65, -0.35), (-0.65, 0.35), (0.65, 0.35)):
        _post(g, rng, sx, sz, 1.5)
        stone(g, V(sx, 0.02, sz), (0.1, 0.06, 0.1), rng, detail=1, rough=0.12, col_fn=rock_col((0.75, 0.73, 0.7)),
              tile=0.5)
    for sz in (-0.35, 0.35):
        beam(g, [V(-0.8, 1.5, sz), V(0.8, 1.5, sz)], 0.1, 0.1, mat=M_PLANK, chamfer=0.2, rng=rng, col=OAKD)
    # Shingle roof, ridge along X.
    # Overlapping split boards down each slope (ridge y 1.9 at z 0 to the eave y 1.5 at z +-0.62).
    for sz in (-1, 1):
        R, E = V(0, 1.92, 0), V(0, 1.5, sz * 0.62)
        d = E - R
        n_ = d.cross(V(1, 0, 0)).normalized()
        if n_.y < 0:
            n_ = -n_
        for k in range(6):
            c = R + d * ((k + 0.5) / 6) + n_ * (0.02 + 0.012 * (k % 2))
            board(g, c, (1, 0, 0), n_, 1.86, d.length / 6 * 1.45, 0.025, mat=M_PLANK,
                  col=scale((0.8, 0.7, 0.56), rng.uniform(0.8, 1.0)), rng=rng)
    beam(g, [V(-0.95, 1.95, 0), V(0.95, 1.95, 0)], 0.08, 0.06, mat=M_PLANK, chamfer=0.3, rng=rng, col=(0.5, 0.42, 0.34))
    # Counter: plank front + oak top; strongbox with straps; coin stacks; ledger; coin sign.
    for k in range(4):
        board(g, V(0, 0.08 + k * 0.13, 0.52), (1, 0, 0), (0, 0, 1), 1.4, 0.13, 0.03, mat=M_PLANK,
              col=scale((0.72, 0.6, 0.46), rng.uniform(0.85, 1.0)), rng=rng)
    board(g, V(0, 0.585, 0.3), (1, 0, 0), (0, 1, 0), 1.48, 0.52, 0.06, mat=M_PLANK, col=(0.62, 0.5, 0.38), rng=rng)
    for sx in (-0.68, 0.68):
        beam(g, [V(sx, 0.0, 0.5), V(sx, 0.56, 0.5)], 0.06, 0.06, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=OAKD)
    crate_box(g, rng, V(-0.42, 0.75, 0.28), (0.36, 0.26, 0.26), 0.0, col=(0.7, 0.52, 0.36))
    for dx in (-0.12, 0.12):
        strap(g, V(-0.42 + dx, 0.885, 0.28), (0, 0, 1), (0, 1, 0), 0.27, w=0.04, nails=3)
    lbox(g, V(-0.42, 0.8, 0.42), (0.07, 0.08, 0.02), quat_y(0.0), M_IRON, (1.1, 0.82, 0.38), tile=0.2)
    for k, (x, z, n) in enumerate(((0.55, 0.26, 5), (0.63, 0.36, 3), (0.48, 0.38, 2))):
        for i in range(n):
            lathe(g, (x + rng.uniform(-0.004, 0.004), 0.615 + i * 0.013, z), (0, 1, 0), [(0.0, 0.03), (0.012, 0.03)], 8,
                  M_IRON, (1.15, 0.86, 0.4), tile=0.2)
    lbox(g, V(0.2, 0.635, 0.3), (0.28, 0.04, 0.22), quat_y(0.1), M_HIDE, (0.42, 0.18, 0.12), tile=0.2)
    lbox(g, V(0.2, 0.658, 0.3), (0.26, 0.006, 0.2), quat_y(0.1), M_CLOTH, PAPER, tile=0.2)
    tube(g, [V(0.55, 1.45, 0.5), V(0.55, 1.22, 0.5)], [0.006, 0.006], 3, M_IRON, IRN, tile=0.2)
    board(g, V(0.55, 1.08, 0.5), (1, 0, 0), (0, 0, 1), 0.3, 0.26, 0.03, mat=M_PLANK, col=(0.66, 0.54, 0.42), rng=rng)
    lathe(g, (0.55, 1.08, 0.517), (0, 0, 1), [(0.0, 0.08), (0.012, 0.075), (0.014, 0.0)], 12, M_IRON, (1.15, 0.86, 0.4),
          tile=0.2)
    mound(g, (0, -0.03, 0), 1.0, 0.7, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.6, 0.52, 0.42), rings=2, seg=14)
    return b


def decor_shrine(rng):
    b = Builder()
    g = G(b)
    LS = lambda p, n: (1.3, 1.25, 1.15)  # noqa: E731
    slab(g, V(0, 0.09, 0), (0.95, 0.18, 0.75), quat_y(0.0), rng, mat=M_STONE, res=(4, 2, 3), round_r=0.03, rough=0.03,
         col_fn=LS, tile=0.6)
    slab(g, V(0, 0.26, -0.02), (0.7, 0.16, 0.52), quat_y(0.0), rng, mat=M_STONE, res=(4, 2, 3), round_r=0.03,
         rough=0.03, col_fn=LS, tile=0.6)
    # Niched pillar from three dressed blocks, a gabled cap stone.
    for k, h in enumerate((0.22, 0.22, 0.22)):
        y = 0.34 + h / 2 + k * h
        if k == 1:
            for sx in (-1, 1):
                slab(g, V(sx * 0.16, y, -0.04), (0.12, h - 0.01, 0.36), quat_y(0.0), rng, mat=M_STONE, res=(2, 2, 3),
                     round_r=0.02, rough=0.03, col_fn=LS, tile=0.6)
            slab(g, V(0, y, -0.16), (0.2, h - 0.01, 0.1), quat_y(0.0), rng, mat=M_STONE, res=(2, 2, 2), round_r=0.02,
                 rough=0.03, col_fn=lambda p, n: (0.5, 0.48, 0.45), tile=0.6)
        else:
            slab(g, V(0, y, -0.04), (0.44, h - 0.01, 0.36), quat_y(0.0), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.02,
                 rough=0.03, col_fn=LS, tile=0.6)
    for sz in (-1, 1):
        q = quat_x(-sz * 0.6)
        slab(g, V(0, 1.08, -0.04 + sz * 0.11), (0.6, 0.06, 0.28), q, rng, mat=M_STONE, res=(3, 1, 2), round_r=0.02,
             rough=0.03, col_fn=lambda p, n: (1.05, 1.0, 0.94), tile=0.6)
    # Gilt icon in the niche, wax drips, three candles (flames added by the game), a posy.
    lbox(g, V(0, 0.68, -0.1), (0.12, 0.18, 0.02), quat_y(0.0), M_IRON, (1.2, 0.92, 0.42), tile=0.2)
    for (cx, cz, ch) in ((-0.32, 0.26, 0.1), (-0.18, 0.32, 0.16), (0.3, 0.28, 0.12)):
        lathe(g, (cx, 0.18, cz), (0, 1, 0), [(0.0, 0.035), (ch, 0.032), (ch + 0.01, 0.0)], 8, M_PLASTER, (1.0, 0.95, 0.82),
              tile=0.2)
        tube(g, [V(cx, 0.18 + ch + 0.01, cz), V(cx, 0.18 + ch + 0.03, cz)], [0.004, 0.003], 3, M_FRUIT, CHAR, tile=0.1)
        mound(g, (cx, 0.175, cz), 0.06, 0.06, 0.008, rng, mat=M_PLASTER, col_fn=lambda p, n: (1.0, 0.95, 0.82), rings=1,
              seg=8)
    for k in range(5):
        a = rng.uniform(-0.4, 0.4)
        tube(g, [V(0.12, 0.35, 0.18), V(0.12 + math.sin(a) * 0.1, 0.42, 0.24)], [0.006, 0.004], 3, M_FRUIT,
             (0.3, 0.45, 0.2), tile=0.1)
        stone(g, V(0.12 + math.sin(a) * 0.1, 0.43, 0.24), (0.02, 0.015, 0.02), rng, mat=M_FRUIT, detail=0, cuts=0,
              col_fn=lambda p, n: (0.9, 0.85, 0.3) if k % 2 else (0.75, 0.3, 0.45), tile=0.1)
    mound(g, (0, -0.03, 0), 0.75, 0.6, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.58, 0.52, 0.42), rings=2, seg=12)
    return b


def decor_bounty_board(rng):
    b = Builder()
    g = G(b)
    for sx in (-0.66, 0.66):
        _post(g, rng, sx, 0.0, 1.62, w=0.12)
    for k in range(5):
        board(g, V(0, 0.76 + k * 0.165, 0.07), (1, 0, 0), (0, 0, 1), 1.55, 0.16, 0.035, mat=M_PLANK,
              col=scale((0.56, 0.48, 0.38), rng.uniform(0.85, 1.0)), rng=rng)
    for sz in (-1, 1):
        q = quat_x(sz * 0.7)
        board(g, V(0, 1.66, 0.07 + sz * 0.12), (1, 0, 0), q @ V(0, 1, 0), 1.75, 0.32, 0.03, mat=M_PLANK,
              col=(0.46, 0.42, 0.38), rng=rng)
    for (px, py, w, h, a) in ((-0.5, 1.12, 0.26, 0.34, 0.04), (-0.12, 1.05, 0.3, 0.4, -0.03), (0.28, 1.16, 0.24, 0.3, 0.06),
                              (0.55, 1.0, 0.2, 0.26, -0.05)):
        lbox(g, V(px, py, 0.093), (w, h, 0.004), quat_z(a), M_CLOTH, scale(PAPER, rng.uniform(0.82, 0.95)), tile=0.3)
        # A crude charcoal ork head on each notice, a nail at the top.
        lathe(g, (px, py + 0.04, 0.096), (0, 0, 1), [(0.0, w * 0.22), (0.002, 0.0)], 8, M_FRUIT, (0.12, 0.11, 0.1),
              tile=0.2)
        lbox(g, V(px, py - h * 0.28, 0.096), (w * 0.6, 0.012, 0.002), quat_y(0.0), M_FRUIT, (0.15, 0.13, 0.12), tile=0.2)
        lbox(g, V(px, py + h / 2 - 0.03, 0.1), (0.018, 0.018, 0.012), quat_y(0.0), M_IRON, IRN, tile=0.2)
    lbox(g, V(-0.12, 0.93, 0.1), (0.06, 0.15, 0.004), quat_z(0.1), M_CLOTH, CRIMSON, tile=0.2)
    stone(g, V(0.5, 0.8, 0.13), (0.06, 0.09, 0.05), rng, mat=M_HIDE, detail=1, cuts=0, rough=0.1,
          col_fn=lambda p, n: (0.55, 0.4, 0.28), tile=0.3)
    tube(g, [V(0.5, 0.88, 0.13), V(0.5, 0.95, 0.1)], [0.006, 0.006], 3, M_CLOTH, ROPE, tile=0.2)
    return b


def decor_scaffold(rng):
    """Mason's scaffold, wall along +Z at x ~0, the deck out at -X: lashed poles, ledgers, putlogs,
    a plank deck at 1.84 with a stone block waiting, a ladder up."""
    b = Builder()
    g = G(b)
    PC = (0.86, 0.8, 0.7)
    for pz in (-1.6, 0.0, 1.6):
        for x in (-0.05, -0.75):
            pole(g, V(x, -0.2, pz), V(x + rng.uniform(-0.02, 0.02), 2.35, pz + rng.uniform(-0.02, 0.02)), 0.05, 0.04, rng,
                 col=PC, sides=7, segs=3)
            grass_foot(g, rng, (x, 0, pz), 0.12)
    for ly in (0.9, 1.78):
        for x in (-0.05, -0.75):
            pole(g, V(x - 0.06 if x < -0.5 else x + 0.06, ly, -1.75), V(x - 0.06 if x < -0.5 else x + 0.06, ly, 1.75),
                 0.035, 0.033, rng, col=scale(PC, 0.95), sides=6, segs=2)
            for pz in (-1.6, 0.0, 1.6):
                lashing(g, V(x, ly, pz), (0, 1, 0), 0.07, rng, turns=3)
        for pz in (-1.6, -0.8, 0.0, 0.8, 1.6):
            pole(g, V(0.05, ly + 0.05, pz), V(-0.85, ly + 0.05, pz), 0.03, 0.03, rng, col=scale(PC, 0.9), sides=6, segs=1)
    for k in range(4):
        z = -1.4 + k * 0.94
        board(g, V(-0.4, 1.87, z), (0, 0, 1), (0, 1, 0), 0.95, 0.24, 0.04, mat=M_PLANK,
              col=scale((0.78, 0.68, 0.54), rng.uniform(0.8, 1.0)), rng=rng)
        board(g, V(-0.4, 1.87, z), (0, 0, 1), (0, 1, 0), 0.95, 0.24, 0.04, mat=M_PLANK, col=(0.78, 0.68, 0.54), rng=rng)
    for k in range(3):
        board(g, V(-0.18 - k * 0.22, 1.87, 0.0), (0, 0, 1), (0, 1, 0), 3.3, 0.2, 0.04, mat=M_PLANK,
              col=scale((0.74, 0.64, 0.5), rng.uniform(0.85, 1.0)), rng=rng)
    slab(g, V(-0.38, 2.0, -0.6), (0.3, 0.22, 0.34), quat_y(0.2), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.02,
         rough=0.03, col_fn=lambda p, n: (0.82, 0.8, 0.75), tile=0.5)
    # Diagonal brace + ladder + a bucket of mortar.
    pole(g, V(-0.75, 0.1, -1.6), V(-0.75, 1.75, 0.0), 0.03, 0.03, rng, col=PC, sides=6, segs=2)
    ladder(g, rng, V(-1.3, 0.0, 0.8), V(-0.85, 2.3, 0.8), width=0.4)
    lathe(g, (-1.0, 0.0, -0.9), (0, 1, 0), [(0.0, 0.13), (0.25, 0.15)], 10, M_TIMBER, (0.7, 0.58, 0.44), tile=0.3)
    lbox(g, V(-1.0, 0.24, -0.9), (0.2, 0.02, 0.2), quat_y(0.3), M_EARTH, (0.85, 0.83, 0.78), tile=0.3)
    mound(g, (-0.6, -0.02, 0.0), 0.8, 1.9, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.72, 0.7, 0.64), rings=2,
          seg=14, rough=0.2)
    return b


def decor_stone_pile(rng):
    b = Builder()
    g = G(b)
    for (x, y, z, sx, sy, sz, a) in ((0, 0.16, 0, 0.5, 0.32, 0.4, 0.05), (0.1, 0.16, 0.45, 0.46, 0.3, 0.38, -0.1),
                                      (0.05, 0.47, 0.2, 0.42, 0.28, 0.36, 0.2), (-0.05, 0.16, -0.46, 0.44, 0.3, 0.4, 0.1)):
        slab(g, V(x, y, z), (sx, sy, sz), quat_y(a), rng, mat=M_STONE, res=(3, 2, 3), round_r=0.025, rough=0.04,
             col_fn=lambda p, n: (0.84, 0.82, 0.76) if n.y > 0.5 else (0.74, 0.72, 0.68), tile=0.5)
    for k in range(10):
        stone(g, V(rng.uniform(-0.5, 0.5), 0.01, rng.uniform(-0.7, 0.7)), (0.04, 0.02, 0.035), rng, detail=0, rough=0.2,
              col_fn=lambda p, n: (0.85, 0.83, 0.78), tile=0.3)
    pole(g, V(0.38, 0.0, -0.2), V(0.4, 0.0, 0.5), 0.04, 0.04, rng, col=(0.75, 0.68, 0.58), sides=6, wobble=0.0, segs=1)
    mound(g, (0, -0.03, 0), 0.6, 0.85, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.78, 0.76, 0.7), rings=2, seg=12,
          rough=0.25)
    return b


def decor_guild_banner(rng):
    b = Builder()
    g = G(b)
    pole(g, V(0, -0.3, 0), V(0, 2.32, 0), 0.05, 0.04, rng, mat=M_TIMBER, col=OAKD, sides=8, segs=2)
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.3
        beam(g, [V(math.cos(a) * 0.05, 0.25, math.sin(a) * 0.05), V(math.cos(a) * 0.3, -0.05, math.sin(a) * 0.3)], 0.05,
             0.04, mat=M_PLANK, chamfer=0.3, rng=rng, col=scale(OAKD, 0.9))
    pole(g, V(-0.02, 2.22, 0), V(0.55, 2.22, 0), 0.025, 0.022, rng, mat=M_TIMBER, col=OAKD, sides=6, wobble=0.0, segs=1)
    lashing(g, V(0, 2.22, 0), (0, 1, 0), 0.05, rng, turns=3)
    banner_sheet(g, rng, V(0.06, 2.2, 0.0), V(0.5, 2.2, 0.0), 0.95, folds=0.04, swallow=True, crest=True, stripe=True)
    lathe(g, (0, 2.32, 0), (0, 1, 0), [(0.0, 0.05), (0.07, 0.06), (0.14, 0.0)], 8, M_IRON, (1.1, 0.82, 0.38), tile=0.2)
    grass_foot(g, rng, (0, 0, 0), 0.3)
    return b


def decor_guild_goods(rng):
    b = Builder()
    g = G(b)
    crate_box(g, rng, V(-0.2, 0.22, -0.05), (0.55, 0.44, 0.45), 0.1)
    crate_box(g, rng, V(-0.15, 0.62, -0.05), (0.42, 0.36, 0.38), -0.2, col=(0.85, 0.66, 0.46))
    barrel(g, rng, (0.38, 0.0, 0.1), s=0.95)
    sack(g, rng, V(0.15, 0.2, 0.42))
    sack(g, rng, V(-0.45, 0.17, 0.4), lying=True)
    # A bolt of dyed cloth on the crate and a coil of rope.
    pole(g, V(-0.35, 0.87, 0.05), V(0.05, 0.87, -0.05), 0.07, 0.07, rng, mat=M_CLOTH, col=(0.25, 0.32, 0.6), sides=10,
         wobble=0.0, segs=1)
    for k in range(3):
        tube(g, [V(0.45 + 0.13 * math.cos(a), 0.62 + k * 0.025, 0.1 + 0.13 * math.sin(a))
                 for a in np.linspace(0, 2 * math.pi, 13)], [0.018] * 13, 4, M_CLOTH, ROPE, tile=0.2, cap=False)
    mound(g, (0, -0.03, 0.1), 0.85, 0.65, 0.03, rng, mat=M_EARTH, col_fn=lambda p, n: (0.6, 0.52, 0.42), rings=2, seg=12)
    return b


def decor_laundry(rng):
    b = Builder()
    g = G(b)
    for sx in (-1.3, 1.3):
        pole(g, V(sx, -0.3, 0), V(sx * 1.03, 1.45, 0), 0.04, 0.035, rng, col=(0.82, 0.76, 0.66), sides=6, segs=2)
        tube(g, [V(sx * 1.03, 1.42, 0), V(sx * 1.4, 0.0, 0.0)], [0.006, 0.006], 3, M_CLOTH, ROPE, tile=0.2)
        tube(g, [V(sx * 1.4, 0.05, 0), V(sx * 1.4, -0.15, 0)], [0.02, 0.015], 5, M_TIMBER, OAKD, tile=0.2)
        grass_foot(g, rng, (sx, 0, 0), 0.14)
    sag = lambda x: 1.38 - 0.08 * (1 - (x / 1.33) ** 2)  # noqa: E731
    xs = np.linspace(-1.33, 1.33, 9)
    tube(g, [V(float(x), sag(x), 0) for x in xs], [0.006] * 9, 3, M_CLOTH, ROPE, tile=0.2, cap=False)
    for (cx, w, h, col) in ((-0.8, 0.46, 0.55, LINEN), (-0.15, 0.38, 0.44, (0.62, 0.15, 0.12)),
                            (0.45, 0.42, 0.36, (0.75, 0.68, 0.5)), (0.95, 0.3, 0.5, LINEN)):
        ni, nj = 5, 5
        ph = rng.uniform(0, 3)
        grid = []
        for i in range(ni):
            row = []
            for j in range(nj):
                x = cx - w / 2 + w * j / (nj - 1)
                y = sag(x) - h * i / (ni - 1)
                z = 0.03 * math.sin(j * 1.7 + ph) * (i / (ni - 1)) + 0.015 * math.sin(i * 2.1 + ph)
                row.append(V(x, y, z))
            grid.append(row)
        sheet(g, grid, M_CLOTH, lambda p, n, c=col: c, tile=0.5, double=True)
        for x in (cx - w / 2 + 0.04, cx + w / 2 - 0.04):
            lbox(g, V(x, sag(x) + 0.01, 0), (0.015, 0.06, 0.02), quat_y(0.0), M_TIMBER, (0.85, 0.75, 0.6), tile=0.2)
    lathe(g, (0.2, 0.0, 0.5), (0, 1, 0), [(0.0, 0.26), (0.18, 0.3), (0.2, 0.0)], 12, M_THATCH, (0.95, 0.82, 0.6), tile=0.3)
    return b


# ─────────────────────────────────────────────────────────────── gate leaf / barricade
def gate_leaf(rng):
    """Hinged at x 0, spans +X to 1.38, 2.6 tall, faces +-Z (0.14 thick)."""
    b = Builder()
    g = G(b)
    W, H = 1.38, 2.6
    k = 6
    bw = W / k
    for i in range(k):
        x = bw * (i + 0.5)
        board(g, V(x, H / 2 + rng.uniform(-0.01, 0.01), 0.02), (0, 1, 0), (0, 0, 1), H - rng.uniform(0, 0.05),
              bw * 0.98, 0.06, mat=M_PLANK, col=scale((0.92, 0.76, 0.58), rng.uniform(0.82, 1.0)), rng=rng, chamfer=0.1)
    # Ledges + a Z brace on the -Z (yard) face.
    for y in (0.35, 1.3, 2.25):
        beam(g, [V(0.04, y, -0.05), V(W - 0.04, y, -0.05)], 0.16, 0.06, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15,
             rng=rng, col=(0.8, 0.66, 0.5))
    for (y0, y1) in ((0.42, 1.22), (1.38, 2.18)):
        beam(g, [V(0.14, y0, -0.05), V(W - 0.14, y1, -0.05)], 0.14, 0.055, up=(0, 0, 1), mat=M_PLANK, chamfer=0.15,
             rng=rng, col=(0.78, 0.64, 0.48))
    # Strap hinges on both faces (long, fish-tailed, nailed), a ring pull, clench nails in rows.
    for y in (0.5, 2.1):
        for zf in (1, -1):
            z = 0.055 * zf if zf > 0 else -0.085
            strap(g, V(W * 0.4, y, z), (1, 0, 0), (0, 0, zf), W * 0.8, w=0.08, t=0.014, nails=5)
        pole(g, V(-0.02, y - 0.12, 0.0), V(-0.02, y + 0.12, 0.0), 0.04, 0.04, rng, mat=M_IRON, col=IRN, sides=8,
             wobble=0.0, segs=1)
    for i in range(1, k):
        x = bw * i
        nail_row(g, [V(x - bw / 2, y, 0.05) for y in (0.95, 1.75)], (0, 0, 1))
    tube(g, [V(W - 0.2 + 0.07 * math.cos(a), 1.2 + 0.07 * math.sin(a), 0.07) for a in np.linspace(0, 2 * math.pi, 11)],
         [0.01] * 11, 4, M_IRON, IRN, tile=0.2, cap=False)
    return b


def gate_barricade(rng):
    """Overturned hay-wain across the gap (local X along the wall, ~2.9 wide)."""
    b = Builder()
    g = G(b)
    L = 2.9
    WC = (0.72, 0.58, 0.44)
    # The bed on its side: floor boards standing vertical (facing -Z), the side rails.
    for k in range(6):
        y = 0.18 + k * 0.2
        board(g, V(0, y, 0.15), (1, 0, 0), (0, 0, 1), L, 0.19, 0.04, mat=M_PLANK, col=scale(WC, rng.uniform(0.75, 0.95)),
              rng=rng)
    for y in (0.15, 1.3):
        beam(g, [V(-L / 2 - 0.1, y, 0.0), V(L / 2 + 0.1, y, 0.0)], 0.12, 0.12, mat=M_PLANK, chamfer=0.15, rng=rng, col=WC)
        for x in (-1.0, 0.0, 1.0):
            pole(g, V(x, y, 0.06), V(x, y, 0.75), 0.03, 0.028, rng, mat=M_TIMBER, col=scale(WC, 0.9), sides=5, segs=1)
    for x in (-1.2, -0.4, 0.4, 1.2):
        beam(g, [V(x, 0.05, 0.22), V(x, 1.35, 0.22)], 0.1, 0.06, up=(0, 0, 1), mat=M_PLANK, chamfer=0.2, rng=rng,
             col=scale(WC, 0.8))
        strap(g, V(x, 1.3, 0.26), (0, 1, 0), (0, 0, 1), 0.2, w=0.05, nails=2)
    # Axle + wheels up against the bed (yard side, -Z).
    pole(g, V(-1.25, 0.75, -0.35), V(1.25, 0.75, -0.35), 0.05, 0.05, rng, mat=M_TIMBER, col=scale(WC, 0.8), sides=8,
         wobble=0.0, segs=1)
    for sx in (-1, 1):
        cart_wheel(g, rng, V(sx * 1.15, 0.75, -0.45), (0.08, 0, 1), r=0.62, col=(0.82, 0.62, 0.44))
    # Sharpened stakes wedged in, leaning out over the field side (+Z), lashed to the rail.
    for k in range(7):
        x = -L / 2 + 0.25 + k * (L - 0.5) / 6
        foot = V(x + rng.uniform(-0.05, 0.05), -0.25, 0.3)
        tip = V(x + rng.uniform(-0.1, 0.1), 1.5 + rng.uniform(-0.1, 0.1), 1.05)
        beam(g, [foot, tip], 0.09, 0.09, up=(1, 0, 0), mat=M_PLANK, chamfer=0.3, rough=0.1, point=0.18, rng=rng,
             col=(0.78, 0.66, 0.52))
        lashing(g, foot.lerp(tip, 0.47), tuple(tip - foot), 0.07, rng, turns=2)
    # Sacks of earth packed at the foot, trampled ground.
    for k in range(5):
        sack(g, rng, V(-1.1 + k * 0.55, 0.15, -0.05 + rng.uniform(-0.05, 0.05)), lying=True)
    mound(g, (0, -0.03, 0.1), 1.8, 1.0, 0.04, rng, mat=M_EARTH, col_fn=lambda p, n: (0.5, 0.44, 0.36), rings=3, seg=16)
    return b


TOWN_FINISH = {
    "meadow_fence": meadow_fence,
    "meadow_fence_post": meadow_fence_post,
    "castle_lantern": castle_lantern,
    "castle_ballista": castle_ballista,
    "town_plot": town_plot,
    "town_house_site": town_house_site,
    "town_rubble": town_rubble,
    "decor_armory": decor_armory,
    "decor_armory_veteran": decor_armory_veteran,
    "decor_axe_display": decor_axe_display,
    "decor_sword_display": decor_sword_display,
    "decor_grindstone": decor_grindstone,
    "decor_tax_booth": decor_tax_booth,
    "decor_shrine": decor_shrine,
    "decor_bounty_board": decor_bounty_board,
    "decor_scaffold": decor_scaffold,
    "decor_stone_pile": decor_stone_pile,
    "decor_guild_banner": decor_guild_banner,
    "decor_guild_goods": decor_guild_goods,
    "decor_laundry": decor_laundry,
    "gate_leaf": gate_leaf,
    "gate_barricade": gate_barricade,
}
