"""River bridges + swamp boardwalks as Blender models -> bridges_kit.glb (src/bridges.rs).

The decks used to be stacks of flat-shaded tinted cuboids. Now each crossing is assembled from
modular bays of real timber (the town kit's toolkit: s_planks decking with its nails, s_timber
stringers / rails, s_stone footings, s_iron spikes, s_earth ramps), vertex colour carrying the
weathering (sun-greyed rails, damp dark undersides, moss creeping over the planks).

Local frame: the deck runs along X, deck top at y = 0.05 (the game parks the root at bank + 0.2,
so the walked surface stays at bank + 0.25), width along Z.

  bridge_bay_a/b/c   1.0 x 2.4 bay: three stringers on a cross needle, two planks, a railed post
                     with an outrigger knee brace on each side at x = -0.5 (the next bay's post
                     closes it). The game stretches bays along X (0.8 .. 1.25) to fill a span.
  bridge_end         the bank end of a bridge at x = 0, LAND toward +X: heavy capped end posts,
                     a dry-stone abutment under the last metre of deck, an earth ramp + loose stones.
  boardwalk_bay_a/b  1.0 x 1.8 bay of narrow mossy planks on two side stringers, a pair of round
                     stilts at x = -0.5 dropping 1.4 into the bog with a cross tie.
  boardwalk_end      mooring posts lashed at the deck end (x = 0, land toward +X) + a trodden mound.
  miner_handcart     the quarry carters' handcart (src/miner.rs): plank bed 0.6 x 0.84 (top y ~0.43)
                     with side boards, two spoked iron-tyred wheels (r 0.2, axle along X at y 0.2),
                     a heap of quarried stone. No shafts (the game hangs miner_cart_shaft pieces).
  miner_cart_shaft   one round ash shaft, 1.0 long along +Z centred on the origin (scaled to fit).
  hen_a / hen_b      courtyard hens (src/castle.rs), facing +X, ~0.32 tall: smooth feathered body
                     (red-brown / speckled white), folded wings, fanned tail, comb + wattle, beak,
                     scaly legs and toes. Untextured ("fruit" = vertex colour only).

    blender -b --factory-startup --python tools/blender_forest/bridges_kit.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
_tk = (HERE / "town_kit.py").read_text(encoding="utf-8")
exec(compile(_tk[:_tk.index("\nMODELS = {")], str(HERE / "town_kit.py"), "exec"))

DECK = (0.86, 0.76, 0.64)      # weathered oak decking
DAMP = (0.5, 0.44, 0.37)       # wet underside / stringers
RAILC = (1.08, 1.0, 0.9)       # sun-greyed rail
MOSSC = (0.55, 0.62, 0.36)
TOP = 0.05


def _plank_col(rng, moss):
    c = scale(DECK, rng.uniform(0.72, 1.05))
    if rng.uniform() < 0.2:
        c = scale((0.95, 0.93, 0.9), rng.uniform(0.75, 0.95))  # silver-grey replacement plank
    m = min(1.0, moss * rng.uniform(0.3, 1.2))
    return tuple(a * (1 - m) + b * m for a, b in zip(c, MOSSC))


def _deck_planks(g, rng, half_z, thick, moss, n=2, gap=0.035):
    w = 1.0 / n
    for k in range(n):
        x = -0.5 + (k + 0.5) * w + rng.uniform(-0.01, 0.01)
        hz = half_z + rng.uniform(-0.04, 0.05)
        sag = rng.uniform(-0.008, 0.006)
        board(g, V(x, TOP - thick / 2 + sag, rng.uniform(-0.03, 0.03)), (rng.uniform(-0.03, 0.03), 0, 1), (0, 1, 0),
              hz * 2, w - gap, thick, mat=M_PLANK, col=_plank_col(rng, moss), rng=rng, rough=0.04,
              jag=(0.0, 0.03 if rng.uniform() < 0.3 else 0.0))
        for sz in (-half_z * 0.78, 0.0, half_z * 0.78):
            nail_row(g, [V(x + d, TOP + sag, sz) for d in (-0.1, 0.1)], (0, 1, 0), s=0.02)


def bridge_bay(seed_moss):
    def build(rng):
        b = Builder()
        g = G(b)
        hz = 1.2
        # Cross needle under the post line, poking out past the deck to carry the knee braces.
        beam(g, [V(-0.5, -0.2, -1.42), V(-0.5, -0.2, 1.42)], 0.16, 0.18, mat=M_TIMBER, col=DAMP, chamfer=0.2, rng=rng,
             rough=0.05)
        # Three stringers along the span (overlap the neighbours a touch so no gap shows when stretched).
        for z in (-0.92, 0.0, 0.92):
            beam(g, [V(-0.53, -0.07, z), V(0.53, -0.07 + rng.uniform(-0.01, 0.01), z)], 0.15, 0.17, up=(0, 1, 0),
                 mat=M_TIMBER, col=scale(DAMP, rng.uniform(0.85, 1.1)), chamfer=0.2, rng=rng, rough=0.05)
        _deck_planks(g, rng, hz, 0.075, seed_moss)
        # Railing: post + knee brace each side at x -0.5; top and mid rails along the bay.
        for sz in (-1.0, 1.0):
            z = sz * 1.14
            beam(g, [V(-0.5, -0.28, z), V(-0.5 + rng.uniform(-0.01, 0.01), 0.82, z + rng.uniform(-0.01, 0.01))], 0.12, 0.12,
                 mat=M_TIMBER, col_fn=weathered(RAILC, 0.62), chamfer=0.22, rng=rng, rough=0.06)
            beam(g, [V(-0.5, -0.2, sz * 1.4), V(-0.5, 0.42, sz * 1.2)], 0.08, 0.08, up=(1, 0, 0), mat=M_TIMBER,
                 col=scale(RAILC, 0.72), chamfer=0.2, rng=rng)
            beam(g, [V(-0.56, 0.76, z), V(0.56, 0.76 + rng.uniform(-0.012, 0.012), z)], 0.085, 0.075, mat=M_TIMBER,
                 col=scale(RAILC, rng.uniform(0.85, 1.0)), chamfer=0.3, rng=rng, rough=0.04)
            beam(g, [V(-0.54, 0.4, z * 0.99), V(0.54, 0.4 + rng.uniform(-0.02, 0.02), z * 0.99)], 0.06, 0.06,
                 mat=M_TIMBER, col=scale(RAILC, rng.uniform(0.75, 0.9)), chamfer=0.3, rng=rng, rough=0.05)
            # Iron dog spike + a strap where the rail meets the post.
            nail_row(g, [V(-0.5, 0.76, z + sz * 0.045), V(-0.5, 0.4, z + sz * 0.035)], (0, 0, sz), s=0.024)
        return b
    return build


def bridge_end(rng):
    b = Builder()
    g = G(b)
    # Heavy capped end posts.
    for sz in (-1.0, 1.0):
        z = sz * 1.14
        beam(g, [V(0.0, -0.6, z), V(0.0, 1.0, z)], 0.18, 0.18, mat=M_TIMBER, col_fn=weathered(RAILC, 0.55),
             chamfer=0.22, rng=rng, rough=0.05)
        board(g, V(0.0, 1.02, z), (1, 0, 0), (0, 1, 0), 0.26, 0.26, 0.05, mat=M_TIMBER, col=scale(RAILC, 0.7), rng=rng)
        strap(g, V(0.092, 0.7, z), (0, 1, 0), (1, 0, 0), 0.3, w=0.05, nails=2)
    # Dry-stone abutment under the last of the deck: courses of fieldstones, bedded in the bank.
    for row, y in enumerate((-0.95, -0.62, -0.32)):
        n = 7 - row
        for k in range(n):
            z = -1.3 + (k + 0.5) * 2.6 / n + rng.uniform(-0.05, 0.05)
            for x in (-0.75, -0.3, 0.12):
                r = rng.uniform(0.17, 0.24)
                stone(g, (x + rng.uniform(-0.06, 0.06), y, z), (r * 1.3, r * 0.75, r), rng, mat=M_STONE,
                      col_fn=lambda p, n_: (0.78, 0.76, 0.7) if p[1] < -0.6 else (0.88, 0.86, 0.8), detail=1, rough=0.18)
    # Earth ramp up onto the deck on the land side + scattered stones in the grass.
    mound(g, (0.55, -0.2, 0.0), 1.1, 1.55, 0.2, rng, mat=M_EARTH, col_fn=lambda p, n_: (0.4, 0.36, 0.3), rings=4,
          seg=18, rough=0.15)
    for _ in range(6):
        r = rng.uniform(0.07, 0.15)
        stone(g, (rng.uniform(0.2, 1.3), -0.04, rng.uniform(-1.6, 1.6)), (r, r * 0.6, r * 0.9), rng, mat=M_STONE,
              detail=1, rough=0.2)
    return b


def boardwalk_bay(moss):
    def build(rng):
        b = Builder()
        g = G(b)
        hz = 0.9
        for z in (-0.68, 0.68):
            beam(g, [V(-0.53, -0.06, z), V(0.53, -0.06 + rng.uniform(-0.015, 0.015), z)], 0.12, 0.13, mat=M_TIMBER,
                 col=scale(DAMP, rng.uniform(0.75, 0.95)), chamfer=0.25, rng=rng, rough=0.08)
        _deck_planks(g, rng, hz, 0.06, moss)
        # Round stilts driven into the muck + a cross tie.
        for sz in (-0.8, 0.8):
            pole(g, V(-0.5, -1.45, sz), V(-0.5 + rng.uniform(-0.03, 0.03), 0.06, sz + rng.uniform(-0.03, 0.03)), 0.075,
                 0.065, rng, mat=M_BARK, col=(0.5, 0.46, 0.4), sides=8, segs=3,
                 col_fn=lambda t: (0.3, 0.32, 0.22) if t < 0.55 else (0.66, 0.6, 0.5))
        beam(g, [V(-0.5, -0.22, -0.88), V(-0.5, -0.22, 0.88)], 0.09, 0.1, mat=M_TIMBER, col=scale(DAMP, 0.8), chamfer=0.25,
             rng=rng, rough=0.06)
        return b
    return build


def boardwalk_end(rng):
    b = Builder()
    g = G(b)
    for sz in (-0.8, 0.8):
        pole(g, V(-0.06, -1.3, sz), V(-0.06, 0.5, sz), 0.085, 0.07, rng, mat=M_BARK, col=(0.62, 0.56, 0.48), sides=8,
             segs=3, col_fn=lambda t: (0.32, 0.34, 0.24) if t < 0.5 else (0.7, 0.64, 0.54))
        lashing(g, V(-0.06, 0.36, sz), (0, 1, 0), 0.09, rng, turns=3)
    mound(g, (0.45, -0.17, 0.0), 0.9, 1.15, 0.16, rng, mat=M_EARTH, col_fn=lambda p, n_: (0.34, 0.33, 0.27), rings=3,
          seg=16, rough=0.18)
    return b


def miner_handcart(rng):
    b = Builder()
    g = G(b)
    # Bed: two side rails, cross ledges, deck boards along Z, low side boards.
    for x in (-0.27, 0.27):
        beam(g, [V(x, 0.3, -0.44), V(x, 0.3, 0.44)], 0.06, 0.07, mat=M_TIMBER, col=scale(DECK, 0.8), chamfer=0.25, rng=rng)
    for z in (-0.36, 0.0, 0.36):
        beam(g, [V(-0.31, 0.27, z), V(0.31, 0.27, z)], 0.05, 0.05, mat=M_TIMBER, col=scale(DAMP, 1.1), chamfer=0.25, rng=rng)
    for k in range(4):
        x = -0.225 + k * 0.15
        board(g, V(x, 0.355, rng.uniform(-0.01, 0.01)), (0, 0, 1), (0, 1, 0), 0.86, 0.14, 0.03, mat=M_PLANK,
              col=_plank_col(rng, 0.0), rng=rng)
    for sx in (-1, 1):
        board(g, V(sx * 0.3, 0.43, 0.0), (0, 0, 1), (sx, 0, 0), 0.86, 0.13, 0.025, mat=M_PLANK, col=_plank_col(rng, 0.0),
              rng=rng)
        for z in (-0.4, 0.4):
            beam(g, [V(sx * 0.3, 0.3, z), V(sx * 0.3, 0.5, z)], 0.04, 0.04, mat=M_TIMBER, col=scale(DECK, 0.75), rng=rng)
    for sz in (-1, 1):
        board(g, V(0.0, 0.43, sz * 0.43), (1, 0, 0), (0, 0, sz), 0.6, 0.13, 0.025, mat=M_PLANK, col=_plank_col(rng, 0.0),
              rng=rng)
    # Axle + wheels.
    pole(g, V(-0.42, 0.2, 0.0), V(0.42, 0.2, 0.0), 0.025, 0.025, rng, mat=M_IRON, col=(0.35, 0.33, 0.32), sides=6, segs=1,
         wobble=0.0)
    for sx in (-1, 1):
        cart_wheel(g, rng, V(sx * 0.38, 0.2, 0.0), (1, 0, 0), r=0.2, col=(0.78, 0.6, 0.44))
    # Load: quarried blocks with a few chips.
    for (x, y, z, r) in ((0.0, 0.5, 0.0, 0.13), (-0.13, 0.52, -0.17, 0.1), (0.12, 0.51, 0.16, 0.11), (0.1, 0.6, -0.08, 0.08),
                         (-0.12, 0.5, 0.18, 0.09)):
        stone(g, (x, y, z), (r * 1.2, r * 0.8, r), rng, mat=M_STONE, detail=1, rough=0.12, cuts=3)
    return b


def miner_cart_shaft(rng):
    b = Builder()
    g = G(b)
    pole(g, V(0, 0, -0.5), V(0, 0, 0.5), 0.024, 0.021, rng, mat=M_TIMBER, col=scale(DECK, 0.85), sides=7, segs=2, wobble=0.003)
    return b


def hen(body, wing, tail):
    def build(rng):
        b = Builder()
        g = G(b)
        mot = Noise(rng, 3, 9.0)

        def feathers(base):
            return lambda p, n: scale(base, 0.86 + 0.28 * mot(p * 6.0))
        stone(g, (0.0, 0.15, 0.0), (0.15, 0.105, 0.1), rng, mat=M_FRUIT, col_fn=feathers(body), detail=3, rough=0.05,
              cuts=0, rot=quat_z(-0.22))
        stone(g, (0.075, 0.2, 0.0), (0.07, 0.085, 0.065), rng, mat=M_FRUIT, col_fn=feathers(body), detail=2, rough=0.04,
              cuts=0, rot=quat_z(0.5))
        stone(g, (0.135, 0.275, 0.0), (0.05, 0.055, 0.043), rng, mat=M_FRUIT, col_fn=feathers(body), detail=2, rough=0.03,
              cuts=0)
        for sz in (-1, 1):
            stone(g, (-0.01, 0.16, sz * 0.078), (0.11, 0.055, 0.03), rng, mat=M_FRUIT, col_fn=feathers(wing), detail=2,
                  rough=0.05, cuts=0, rot=quat_z(-0.3))
            stone(g, (0.165, 0.287, sz * 0.03), (0.006, 0.006, 0.004), rng, mat=M_FRUIT, col_fn=lambda p, n: (0.03, 0.025, 0.02),
                  detail=1, rough=0.0, cuts=0)
        # Fanned tail: curved feather blades sweeping up and back.
        for k in range(5):
            a = (k - 2) * 0.16
            base = V(-0.12, 0.2, a * 0.25)
            tip = V(-0.2, 0.36 - abs(a) * 0.2, a * 0.6)
            beam(g, [base, base.lerp(tip, 0.55) + V(-0.015, 0.02, 0), tip], 0.05, 0.012, up=(1, 0.4, 0), mat=M_FRUIT,
                 col=scale(tail, rng.uniform(0.8, 1.05)), chamfer=0.4, mode="plank", rng=rng)
        lathe(g, (0.175, 0.272, 0.0), (1, -0.35, 0), [(0.0, 0.014), (0.02, 0.009), (0.034, 0.0)], 6, M_FRUIT,
              (0.85, 0.62, 0.22))
        for k in range(4):
            stone(g, (0.105 + k * 0.018, 0.325 - abs(k - 1.5) * 0.008, 0.0), (0.012, 0.022, 0.006), rng, mat=M_FRUIT,
                  col_fn=lambda p, n: (0.62, 0.05, 0.04), detail=1, rough=0.1, cuts=0)
        stone(g, (0.17, 0.235, 0.0), (0.012, 0.022, 0.009), rng, mat=M_FRUIT, col_fn=lambda p, n: (0.58, 0.05, 0.04),
              detail=1, rough=0.1, cuts=0)
        for sz in (-1, 1):
            z = sz * 0.035
            pole(g, V(0.0, 0.08, z), V(0.012, 0.005, z), 0.011, 0.008, rng, mat=M_FRUIT, col=(0.8, 0.62, 0.25), sides=5,
                 segs=1, wobble=0.0)
            for t in (-0.5, 0.0, 0.5):
                pole(g, V(0.012, 0.005, z), V(0.012 + 0.045 * math.cos(t), 0.0, z + 0.045 * math.sin(t)), 0.005, 0.003, rng,
                     mat=M_FRUIT, col=(0.78, 0.6, 0.24), sides=4, segs=1, wobble=0.0)
        return b
    return build

MODELS = {
    "bridge_bay_a": bridge_bay(0.05),
    "bridge_bay_b": bridge_bay(0.18),
    "bridge_bay_c": bridge_bay(0.35),
    "bridge_end": bridge_end,
    "boardwalk_bay_a": boardwalk_bay(0.35),
    "boardwalk_bay_b": boardwalk_bay(0.55),
    "boardwalk_end": boardwalk_end,
    "miner_handcart": miner_handcart,
    "miner_cart_shaft": miner_cart_shaft,
    "hen_a": hen((0.5, 0.26, 0.12), (0.4, 0.2, 0.09), (0.12, 0.1, 0.08)),
    "hen_b": hen((0.86, 0.83, 0.76), (0.78, 0.75, 0.68), (0.66, 0.64, 0.6)),
}

clear_scene()
objs = []
report = {}
for i, (name, fn) in enumerate(MODELS.items()):
    bld = fn(np.random.default_rng(9100 + i))
    report[name] = bounds(bld)
    objs.append(bld.build(name, MATS))
export_glb(OUT / "bridges_kit.glb", objs)
for k, v in report.items():
    print(f"{k}: {v}")
print("BRIDGES_KIT_DONE", sum(v["tris"] for v in report.values()))
