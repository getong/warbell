"""The castle market (map-centre rework, phase 2) -> market.glb (src/market.rs).

Four trestle stalls under cloth awnings, each with its own trade laid out on the counter, plus a
hand-cart and a barrel/crate stack. Docs: docs/superpowers/specs/2026-10-11-centrum-mapy-design.md.

  market_bread   - loaves heaped on the counter, a basket of rolls, flour sacks behind.
  market_cloth   - bolts of dyed wool, a length draped over the front board.
  market_pots    - clay jugs, pots and bowls on the counter and the ground.
  market_veg     - baskets of apples and cabbages, a rack of drying fish on the side post.
  market_cart    - a two-wheeled hand-cart with sacks and a crate.
  market_barrels - three barrels and two crates.

Stall frame (shared by the four): 2.0u wide (x) x 1.1u deep (z), counter top y = 0.86, the
customer side is local +Z; the vendor stands behind it at local z ~ -0.85 (outside the model).
Built with the wayside_models.py toolkit, game coordinates (Y up), base at y = 0, posts sunk below.
Materials by name (the existing kit sets); vertex colour tints them (dyed awnings, crusts, glaze).

    blender -b --factory-startup --python tools/blender_forest/market.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
_src = (HERE / "wayside_models.py").read_text(encoding="utf-8")
exec(compile(_src[:_src.index("\nMODELS = {")], str(HERE / "wayside_models.py"), "exec"))

WOOD = (0.82, 0.74, 0.62)
CLAY = (0.86, 0.5, 0.32)
HESSIAN = (0.78, 0.66, 0.46)
# Muted vegetable dyes for the awnings (madder, woad, weld, walnut).
AWNINGS = {
    # (dyed stripe, natural-linen stripe): vertex colour multiplies the tan s_cloth weave.
    "market_bread": ((0.78, 0.3, 0.2), (1.05, 1.0, 0.92)),
    "market_cloth": ((0.32, 0.45, 0.72), (1.05, 1.0, 0.92)),
    "market_pots": ((0.85, 0.66, 0.3), (0.5, 0.34, 0.24)),
    "market_veg": ((0.45, 0.6, 0.34), (1.05, 1.0, 0.92)),
}


def lathe(g, base, axis, profile, sides, mat, col, tile=0.5, col_fn=None):
    a = Vector(axis).normalized()
    pts = [Vector(base) + a * h for h, _ in profile]
    tube(g, pts, [max(r, 0.003) for _, r in profile], sides, mat, col, tile=tile, col_fn=col_fn)


def stall_frame(g, rng, name):
    b_col, s_col = AWNINGS[name]
    w = weathered(WOOD, 0.62, 1.0)
    # Posts: front pair shorter so the awning sheds rain toward the customers.
    for x in (-0.95, 0.95):
        beam(g, [V(x, -0.2, 0.42), V(x, 1.95, 0.42)], 0.09, 0.09, mat=M_TIMBER, col_fn=w, rng=rng)
        beam(g, [V(x, -0.2, -0.5), V(x, 2.28, -0.5)], 0.09, 0.09, mat=M_TIMBER, col_fn=w, rng=rng)
        # Side rail carrying the counter, and the awning rafter.
        beam(g, [V(x, 0.8, 0.5), V(x, 0.8, -0.56)], 0.06, 0.07, mat=M_TIMBER, col=WOOD, rng=rng)
        beam(g, [V(x, 1.97, 0.5), V(x, 2.3, -0.58)], 0.06, 0.06, mat=M_TIMBER, col=WOOD, rng=rng)
    beam(g, [V(-1.02, 1.93, 0.42), V(1.02, 1.93, 0.42)], 0.07, 0.07, mat=M_TIMBER, col=WOOD, rng=rng)
    beam(g, [V(-1.02, 2.26, -0.5), V(1.02, 2.26, -0.5)], 0.07, 0.07, mat=M_TIMBER, col=WOOD, rng=rng)
    # Counter: two planks side by side, and the front skirt of three horizontal boards.
    for z, wd in ((0.3, 0.32), (-0.02, 0.32)):
        board(g, V(0, 0.86, z), (1, 0, 0), (0, 1, 0), 2.04, wd, 0.05, mat=M_PLANK, col=scale(WOOD, rng.uniform(0.9, 1.0)), rng=rng)
    for y in (0.2, 0.44, 0.68):
        board(g, V(0, y, 0.47), (1, 0, 0), (0, 0, 1), 1.96, 0.22, 0.03, mat=M_PLANK, col=scale(WOOD, rng.uniform(0.82, 0.95)), rng=rng)
    # Awning: striped cloth from the back beam over the front beam, sagging between the rafters,
    # with a scalloped valance hanging off the front.
    # Stripes are separate sheets (vertex colour can't hold a hard edge inside one sheet).
    ni, nj = 7, 17
    grid = []
    for i in range(ni):
        u = i / (ni - 1)
        row = []
        for j in range(nj):
            x = -1.1 + 2.2 * j / (nj - 1)
            sag = 0.07 * math.sin(math.pi * j / (nj - 1)) * math.sin(math.pi * min(u / 0.8, 1.0))
            if u <= 0.8:
                t = u / 0.8
                y, z = 2.33 - 0.37 * t - sag, -0.62 + 1.16 * t
            else:
                t = (u - 0.8) / 0.2
                drop = 0.24 + 0.05 * math.cos(j * math.pi / 2)  # scallops
                y, z = 1.96 - drop * t, 0.54 + 0.03 * t
            row.append((x, y, z))
        grid.append(row)
    for k in range(8):
        sub = [row[2 * k:2 * k + 3] for row in grid]
        c = b_col if k % 2 == 0 else s_col
        sheet(g, sub, M_CLOTH, lambda u, v, c=c: scale(c, 0.92 + 0.08 * math.sin(u * 5.0)), tile=0.7, double=True)


def bread(g, rng):
    crust = [(0.66, 0.42, 0.2), (0.58, 0.36, 0.17), (0.72, 0.5, 0.26)]
    for k in range(9):
        x = -0.75 + (k % 5) * 0.34 + rng.uniform(-0.05, 0.05)
        z = 0.24 if k < 5 else -0.02
        stone(g, (x, 0.93, z), (0.13, 0.065, 0.085), rng, mat=M_FRUIT, detail=1, rough=0.06, cuts=0,
              col_fn=lambda p, n, c=crust[k % 3]: scale(c, 0.85 + 0.25 * max(n.y, 0.0)), tile=0.4)
    # Basket of rolls on the counter end.
    lathe(g, (0.72, 0.88, 0.1), (0, 1, 0), [(0.0, 0.12), (0.06, 0.17), (0.13, 0.2)], 12, M_THATCH, (0.8, 0.66, 0.42), tile=0.3)
    for k in range(6):
        a = k * 1.05
        stone(g, (0.72 + math.cos(a) * 0.09, 1.02, 0.1 + math.sin(a) * 0.09), (0.055, 0.045, 0.055), rng, mat=M_FRUIT,
              detail=1, rough=0.05, cuts=0, col_fn=lambda p, n: (0.7, 0.47, 0.22), tile=0.3)
    sacks(g, rng, [(-0.6, -0.78), (-0.2, -0.86)])


def sacks(g, rng, spots):
    for x, z in spots:
        stone(g, (x, 0.24, z), (0.2, 0.27, 0.17), rng, mat=M_CLOTH, detail=2, rough=0.1, cuts=0, flat_y=0.86,
              col_fn=lambda p, n: scale(HESSIAN, 0.8 + 0.2 * max(n.y, 0.0)), tile=0.5)


def cloth(g, rng):
    dyes = [(0.55, 0.22, 0.18), (0.24, 0.32, 0.48), (0.45, 0.5, 0.3), (0.7, 0.58, 0.32), (0.4, 0.3, 0.42), (0.8, 0.76, 0.64)]
    for k in range(6):
        z = 0.27 if k < 3 else -0.03
        x0 = -0.85 + (k % 3) * 0.58
        tube(g, [V(x0, 0.95, z), V(x0 + 0.48, 0.95, z)], [0.075, 0.075], 9, M_CLOTH, dyes[k], tile=0.3)
    # A length of red wool draped over the counter edge and down the front board.
    grid = []
    for i in range(6):
        u = i / 5
        row = []
        for j in range(5):
            x = -0.4 + 0.5 * j / 4
            if u < 0.4:
                y, z = 0.885, 0.1 + 0.95 * u
            else:
                t = (u - 0.4) / 0.6
                y, z = 0.885 - 0.55 * t, 0.49 + 0.02 * math.sin(t * 3.0 + j)
            row.append((x, y, z))
        grid.append(row)
    sheet(g, grid, M_CLOTH, lambda u, v: (0.6, 0.24, 0.18), tile=0.4, double=True)
    stone(g, (0.6, 0.27, -0.82), (0.3, 0.27, 0.22), rng, mat=M_PLANK, detail=1, rough=0.02, cuts=0, flat_y=0.7,
          col_fn=lambda p, n: WOOD, tile=0.5)


def pots(g, rng):
    jug = [(0.0, 0.05), (0.04, 0.09), (0.12, 0.1), (0.2, 0.07), (0.26, 0.04), (0.3, 0.05)]
    pot = [(0.0, 0.07), (0.05, 0.12), (0.12, 0.13), (0.17, 0.11), (0.19, 0.12)]
    bowl = [(0.0, 0.05), (0.03, 0.1), (0.06, 0.13)]
    glazes = [CLAY, (0.6, 0.38, 0.24), (0.5, 0.46, 0.36), (0.78, 0.6, 0.42)]
    for k in range(7):
        x = -0.82 + k * 0.27
        z = 0.22 if k % 2 == 0 else 0.02
        prof = (jug, pot, bowl)[k % 3]
        c = glazes[k % 4]
        lathe(g, (x, 0.885, z), (0, 1, 0), prof, 10, M_EARTH, c, tile=0.4,
              col_fn=lambda t, c=c: scale(c, 0.75 + 0.35 * t))
    for k, (x, z) in enumerate([(-0.75, -0.8), (-0.4, -0.85), (0.5, 0.78), (0.82, 0.7)]):
        lathe(g, (x, 0.0, z), (0, 1, 0), [(h * 1.6, r * 1.6) for h, r in pot], 10, M_EARTH, glazes[k % 4], tile=0.4)


def veg(g, rng):
    basket = [(0.0, 0.13), (0.05, 0.17), (0.12, 0.2)]
    for bx, bz, kind in ((-0.62, 0.18, "apple"), (-0.12, 0.18, "cabbage"), (0.38, 0.18, "apple"), (0.72, -0.02, "turnip")):
        lathe(g, (bx, 0.885, bz), (0, 1, 0), basket, 12, M_THATCH, (0.78, 0.64, 0.42), tile=0.3)
        n = 4 if kind == "apple" else 3
        for k in range(n):
            a = k * 2.4 + rng.uniform(0, 0.4)
            r = 0.0 if k == 0 else (0.1 if kind != "apple" else 0.11)
            p = (bx + math.cos(a) * r, 1.03 + (0.03 if k == 0 else 0.0), bz + math.sin(a) * r)
            if kind == "apple":
                c = (0.62, 0.14, 0.1) if k % 3 else (0.7, 0.55, 0.18)
                stone(g, p, (0.045, 0.042, 0.045), rng, mat=M_FRUIT, detail=1, rough=0.04, cuts=0, col_fn=lambda q, nn, c=c: c, tile=0.3)
            elif kind == "cabbage":
                stone(g, p, (0.1, 0.085, 0.1), rng, mat=M_FRUIT, detail=1, rough=0.12, cuts=0,
                      col_fn=lambda q, nn: mix((0.42, 0.55, 0.28), (0.7, 0.78, 0.5), max(nn.y, 0.0)), tile=0.3)
            else:
                stone(g, p, (0.07, 0.06, 0.07), rng, mat=M_FRUIT, detail=1, rough=0.06, cuts=0,
                      col_fn=lambda q, nn: mix((0.78, 0.72, 0.62), (0.55, 0.3, 0.45), max(nn.y, 0.0)), tile=0.3)
    # Fish rack hung off the left post: a pole and five hanging fish.
    pole(g, V(-0.95, 1.62, 0.42), V(-1.45, 1.6, 0.4), 0.02, 0.018, rng, mat=M_TIMBER, col=WOOD, sides=5, segs=1)
    for k in range(4):
        x = -1.05 - k * 0.11
        tube(g, [V(x, 1.6, 0.41), V(x, 1.52, 0.41)], [0.004, 0.004], 3, M_HIDE, (0.6, 0.5, 0.36), tile=0.2, cap=False)
        stone(g, (x, 1.38, 0.41), (0.035, 0.15, 0.018), rng, mat=M_FRUIT, detail=1, rough=0.05, cuts=0,
              col_fn=lambda q, nn: mix((0.38, 0.4, 0.42), (0.72, 0.74, 0.72), 0.5 + 0.5 * nn.x), tile=0.3, rot=quat_y(0.0))
    sacks(g, rng, [(0.5, -0.82)])


def barrel(g, rng, base, s=1.0):
    prof = [(0.0, 0.2), (0.12, 0.235), (0.3, 0.255), (0.48, 0.235), (0.6, 0.2)]
    lathe(g, base, (0, 1, 0), [(h * s, r * s) for h, r in prof], 12, M_TIMBER, scale((0.62, 0.5, 0.38), rng.uniform(0.85, 1.0)), tile=0.6)
    for h in (0.07, 0.3, 0.53):
        r = (0.22 if h != 0.3 else 0.258) * s
        pts = [V(base[0], base[1] + h * s, base[2]), V(base[0], base[1] + (h + 0.03) * s, base[2])]
        tube(g, pts, [r + 0.006, r + 0.006], 12, M_IRON, (0.42, 0.4, 0.38), tile=0.4, cap=False)
    # Lid.
    lathe(g, (base[0], base[1] + 0.6 * s - 0.01, base[2]), (0, 1, 0), [(0.0, 0.2 * s), (0.015, 0.0)], 12, M_TIMBER, (0.55, 0.45, 0.35), tile=0.5)


def crate(g, rng, centre, size, yaw):
    lbox(g, centre, size, quat_y(yaw), M_PLANK, scale(WOOD, rng.uniform(0.8, 0.95)), tile=0.6)


def market_barrels(rng):
    b = Builder()
    g = G(b)
    barrel(g, rng, (0.0, 0.0, 0.0))
    barrel(g, rng, (0.52, 0.0, 0.1))
    barrel(g, rng, (0.25, 0.0, -0.45), 0.9)
    crate(g, rng, V(-0.55, 0.22, -0.05), (0.5, 0.44, 0.5), 0.3)
    crate(g, rng, V(-0.5, 0.6, -0.08), (0.4, 0.34, 0.4), 0.7)
    return b


def market_cart(rng):
    """Hand-cart, bed centred at the origin, handles toward +X (resting on the ground)."""
    b = Builder()
    g = G(b)
    tilt = math.radians(-9.0)  # bed tips forward onto the handles
    rot = quat_z(tilt)
    c = V(0.0, 0.58, 0.0)
    lbox(g, c, (1.3, 0.06, 0.82), rot, M_PLANK, WOOD, tile=0.6)
    for z in (-0.42, 0.42):
        lbox(g, c + rot @ V(0, 0.15, z), (1.3, 0.26, 0.04), rot, M_PLANK, scale(WOOD, 0.9), tile=0.6)
    for x in (-0.66, 0.66):
        lbox(g, c + rot @ V(x, 0.15, 0), (0.04, 0.26, 0.82), rot, M_PLANK, scale(WOOD, 0.88), tile=0.6)
    # Handles running down to the ground.
    for z in (-0.3, 0.3):
        beam(g, [c + rot @ V(-0.4, -0.05, z), V(1.45, 0.04, z)], 0.06, 0.06, mat=M_TIMBER, col=WOOD, rng=rng)
    # Axle + two spoked-look wheels (solid boards).
    tube(g, [V(-0.12, 0.38, -0.56), V(-0.12, 0.38, 0.56)], [0.035, 0.035], 6, M_IRON, (0.4, 0.38, 0.36), tile=0.4)
    for z in (-0.5, 0.5):
        tube(g, [V(-0.12, 0.38, z - 0.04), V(-0.12, 0.38, z + 0.04)], [0.4, 0.4], 14, M_PLANK, scale(WOOD, 0.85), tile=0.5)
        tube(g, [V(-0.12, 0.38, z - 0.045), V(-0.12, 0.38, z + 0.045)], [0.415, 0.415], 14, M_IRON, (0.35, 0.33, 0.31), tile=0.5, cap=False)
    # Load: two sacks and a small crate.
    for x, z in ((-0.3, -0.18), (0.05, 0.16)):
        stone(g, tuple(c + rot @ V(x, 0.2, z)), (0.24, 0.17, 0.2), rng, mat=M_CLOTH, detail=2, rough=0.1, cuts=0,
              col_fn=lambda p, n: scale(HESSIAN, 0.8 + 0.2 * max(n.y, 0.0)), tile=0.5)
    lbox(g, c + rot @ V(0.38, 0.2, -0.15), (0.34, 0.3, 0.34), rot @ quat_y(0.4), M_PLANK, scale(WOOD, 0.8), tile=0.6)
    return b


def make_stall(name, goods):
    def f(rng):
        b = Builder()
        g = G(b)
        stall_frame(g, rng, name)
        goods(g, rng)
        return b
    return f


def bounds(builder):
    v = np.array(builder.verts) if builder.verts else np.zeros((1, 3))
    gx, gy, gz = v[:, 0], v[:, 2], -v[:, 1]
    return {"tris": builder.tris(), "x": [round(float(gx.min()), 2), round(float(gx.max()), 2)],
            "z": [round(float(gz.min()), 2), round(float(gz.max()), 2)], "y": [round(float(gy.min()), 2), round(float(gy.max()), 2)]}


MODELS = {
    "market_bread": make_stall("market_bread", bread),
    "market_cloth": make_stall("market_cloth", cloth),
    "market_pots": make_stall("market_pots", pots),
    "market_veg": make_stall("market_veg", veg),
    "market_cart": market_cart,
    "market_barrels": market_barrels,
}

clear_scene()
objs = []
report = {}
for i, (name, fn) in enumerate(MODELS.items()):
    bld = fn(np.random.default_rng(5200 + i))
    report[name] = bounds(bld)
    objs.append(bld.build(name, MATS))
export_glb(OUT / "market.glb", objs)
(OUT / "market_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for k, v in report.items():
    print(f"{k}: {v}")
print("MARKET_DONE")
