"""Bake a `jaw_open` morph target into an exported townsfolk GLB (in place), for talking.

    blender -b npc_cast.blend --python add_mouth_morph.py -- <npc> <npc_<npc>.glb> <mpfb rigs/standard dir> [angle_rad]

The game's `game_engine` rig has no jaw bone, so a speaker's mouth is a morph target instead: the lower
face swung down about the jaw hinge, weighted by MakeHuman's own `default`-rig jaw weights
(`weights.default.json`, base-mesh vertex indices) and hinged at its `joint-mouth` joint cube. The cast
blend still holds each look's full base mesh, so the weights are read there and carried onto the
exported (decimated, re-atlased) GLB vertices by nearest surface point in the rest pose. Only the GLB's
JSON + an appended buffer view change, so the committed textures / UVs stay valid. `src/npc_skin.rs`
drives the weight while the person speaks.
"""
import bpy, sys, os, json, struct
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
NPC, GLB, RIGS = argv[0], argv[1], argv[2]
ANGLE = float(argv[3]) if len(argv) > 3 else 0.2
NAME = "jaw_open"


def log(*a):
    print("[mouth]", *a, flush=True)


# ---------------------------------------------------------------- the look's full body, rest pose
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.get("npc") == NPC)
arm.location = (0.0, 0.0, 0.0)
arm.rotation_euler = (0.0, 0.0, 0.0)
arm.data.pose_position = 'REST'
kids = [c for c in bpy.data.objects if c.parent == arm and c.type == 'MESH']
body = next(o for o in kids if o.name == NPC or any(m and "body" in m.name.lower() for m in o.data.materials))
for m in body.modifiers:
    if m.type != 'ARMATURE':
        m.show_viewport = False
bpy.context.view_layer.update()
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
me = ev.to_mesh()
mw = body.matrix_world
co = [mw @ v.co for v in me.vertices]
polys = [tuple(p.vertices) for p in me.polygons]
log(f"{NPC}: body {body.name} verts {len(co)}")

wdoc = json.load(open(os.path.join(RIGS, "weights.default.json")))
jaw = np.zeros(len(co))
for i, w in wdoc["weights"]["jaw"]:
    if i < len(co):
        jaw[i] = w
def group_pts(name):
    gi = body.vertex_groups[name].index
    return [v.index for v in body.data.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)]


# MakeHuman's jaw weights stop under the lower lip (its default rig moves the lips with the jaw only
# partly), so opening it would just stretch a closed mouth. The lower lip is added here: every `lips`
# vertex below the lip seam rides the jaw. The seam height comes from two fixed base-mesh landmarks,
# the innermost lip-lining rows just under (571) and over (588) the mouth slit on the midline.
seam = (co[571].z + co[588].z) * 0.5
lips = set(group_pts("lips"))
for i in lips:
    s = min(max((seam + 0.0012 - co[i].z) / 0.003, 0.0), 1.0)
    jaw[i] = max(jaw[i], s * s * (3.0 - 2.0 * s))
# ...then relax the skin round them (cheeks, mouth corners) so the lip's edge doesn't tear off the cheek:
# a few averaging passes over the mesh graph with the lips themselves held, never lowering a weight
nb = [[] for _ in co]
for e in me.edges:
    a, b = e.vertices
    nb[a].append(b); nb[b].append(a)
for _ in range(10):
    nxt = jaw.copy()
    for i, ns in enumerate(nb):
        if i not in lips and ns:
            nxt[i] = max(jaw[i], (jaw[i] + sum(jaw[j] for j in ns)) / (len(ns) + 1))
    jaw = nxt
# hinge: MakeHuman's mouth joint (the jaw bone's head: behind the upper lip, about nose height) --`n# its `joint-jaw` cube is the CHIN end of that bone
pts = [co[i] for i in group_pts("joint-mouth")]
pivot = sum(pts, Vector()) / len(pts)
log(f"jaw verts {int((jaw > 0.05).sum())}, seam z {seam:.4f}, pivot {tuple(round(x, 4) for x in pivot)}")
bvh = BVHTree.FromPolygons(co, polys)
R = Matrix.Rotation(ANGLE, 3, 'X')   # MakeHuman faces -Y: +X rotation swings the chin down and back

# ---------------------------------------------------------------- the GLB
raw = open(GLB, "rb").read()
off, js, bin_ = 12, None, b""
while off < len(raw):
    ln, typ = struct.unpack_from("<II", raw, off)
    chunk = raw[off + 8: off + 8 + ln]
    if typ == 0x4E4F534A:
        js = json.loads(chunk)
    else:
        bin_ = bytearray(chunk)
    off += 8 + ln


def read_vec3(i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0) or 12
    out = np.empty((a["count"], 3), np.float32)
    for k in range(a["count"]):
        out[k] = struct.unpack_from("<3f", bin_, start + k * stride)
    return out


mesh = next(m for m in js["meshes"] if any("JOINTS_0" in p["attributes"] for p in m["primitives"]))
if NAME in mesh.get("extras", {}).get("targetNames", []):
    raise SystemExit(f"{GLB} already has {NAME}")
moved = 0
# The exported skin doesn't sit exactly on the cast blend's body (the export re-roots / re-rests the rig):
# register the two by the head joint (the skin's bind pose vs the cast armature's rest).
skin = js["skins"][0]
ia = js["accessors"][skin["inverseBindMatrices"]]
ibv = js["bufferViews"][ia["bufferView"]]
hi = [js["nodes"][j]["name"] for j in skin["joints"]].index("head")
ibm = np.array(struct.unpack_from("<16f", bin_, ibv.get("byteOffset", 0) + ia.get("byteOffset", 0) + hi * 64)).reshape(4, 4).T
hg = np.linalg.inv(ibm)[:3, 3]
hb = arm.matrix_world @ arm.data.bones["head"].head_local
shift = hb - Vector((hg[0], -hg[2], hg[1]))
log(f"glb -> blend shift {tuple(round(v, 4) for v in shift)}")
for p in mesh["primitives"]:
    P = read_vec3(p["attributes"]["POSITION"])
    D = np.zeros_like(P)
    for k, (x, y, z) in enumerate(P):
        b = Vector((x, -z, y)) + shift            # glTF Y-up -> Blender Z-up, onto the cast body
        loc, _n, fi, dist = bvh.find_nearest(b, 0.03)
        if loc is None:
            continue
        f = polys[fi]
        ws = [1.0 / max((co[j] - loc).length, 1e-5) for j in f]
        w = sum(wj * jaw[j] for wj, j in zip(ws, f)) / sum(ws)
        # MakeHuman splits the lower lip between jaw and head; push it onto the jaw so the lips PART
        # (a soft weight just bends the chin), keeping the falloff into cheeks / throat smooth
        w = min(max((w - 0.08) / 0.42, 0.0), 1.0)
        w = w * w * (3.0 - 2.0 * w)
        if w <= 1e-3:
            continue
        d = ((R @ (b - pivot)) + pivot - b) * w   # (both in the blend frame: a pure offset, same delta)
        D[k] = (d.x, d.z, -d.y)                   # back to glTF
        moved += 1
    # append the displacement accessor (POSITION morph targets need min/max)
    while len(bin_) % 4:
        bin_.append(0)
    start = len(bin_)
    bin_ += D.astype("<f4").tobytes()
    js["bufferViews"].append({"buffer": 0, "byteOffset": start, "byteLength": D.nbytes})
    js["accessors"].append({"bufferView": len(js["bufferViews"]) - 1, "componentType": 5126, "count": len(D),
                            "type": "VEC3", "min": D.min(0).tolist(), "max": D.max(0).tolist()})
    p["targets"] = [{"POSITION": len(js["accessors"]) - 1}]
mesh["weights"] = [0.0]
mesh.setdefault("extras", {})["targetNames"] = [NAME]
js["buffers"][0]["byteLength"] = len(bin_)

jb = json.dumps(js, separators=(",", ":")).encode()
jb += b" " * (-len(jb) % 4)
while len(bin_) % 4:
    bin_.append(0)
out = bytearray(b"glTF") + struct.pack("<II", 2, 12 + 8 + len(jb) + 8 + len(bin_))
out += struct.pack("<II", len(jb), 0x4E4F534A) + jb + struct.pack("<II", len(bin_), 0x004E4942) + bin_
open(GLB, "wb").write(out)
log(f"DONE {GLB}: {moved} verts move, angle {ANGLE}")
