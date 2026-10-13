"""Warbell town film: game kit buildings + Poly Haven props + MPFB cast animated with UAL clips.
blender -b npc_cast.blend --python town_film.py -- OUTDIR START END [RES_PCT] [SAMPLES]
"""
import bpy, sys, os, math, random
from mathutils import Vector, Matrix, Euler

S = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:]
OUT = argv[0]; FR = [int(x) for x in argv[1].split(',')] if ',' in argv[1] else list(range(int(argv[1]), int(argv[2]) + 1))
RES = int(argv[3]) if len(argv) > 3 else 100
SAMPLES = int(argv[4]) if len(argv) > 4 else 16
GAME = "C:/Users/skibi/Documents/Codex/warbell/assets/forest_pbr/"
GT = S + "/gametex/"
PHM = "C:/Users/skibi/Documents/Codex/polyhaven_src/models/"
PHT = "C:/Users/skibi/Documents/Codex/polyhaven_src/textures/"
HUMAN_SCALE = 0.72   # 1.7 m person -> 1.22 game units (hero is ~1.17u)

scene = bpy.context.scene
random.seed(7)

# ------------------------------------------------------------------ cast + animation actions
cast = {o['npc']: o for o in bpy.data.objects if o.type == 'ARMATURE' and 'npc' in o}
with bpy.data.libraries.load(S + "/npc_anims.blend") as (src, dst):
    dst.actions = [a for a in src.actions if a.startswith('NPC_')]
ACT = {a.name[4:]: a for a in bpy.data.actions if a.name.startswith('NPC_')}
for o in list(bpy.data.objects):
    if o.name.startswith('Cube'): bpy.data.objects.remove(o)
for rig in cast.values():
    for pb in rig.pose.bones: pb.rotation_mode = 'QUATERNION'
    for c in rig.children_recursive: c.hide_render = False

def actor_clip(name, clip, offset=0, loop=True):
    rig = cast[name]
    base = ACT[clip]
    act = base.copy(); act.name = f"{name}:{clip}"
    n = int(base['frames'])
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.co.x += offset; kp.handle_left.x += offset; kp.handle_right.x += offset
        if loop:
            m = fc.modifiers.new('CYCLES')
    rig.animation_data_create()
    rig.animation_data.action = act
    return n

# ------------------------------------------------------------------ materials for the game kit
def img(path, nc=False):
    i = bpy.data.images.load(path, check_existing=True)
    if nc: i.colorspace_settings.name = 'Non-Color'
    return i

def pbr(mat, setname, folder, alb, nor=None, orm=None, uvscale=None, vcol=True):
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    uv = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    if uvscale: mp.inputs['Scale'].default_value = (uvscale,) * 3
    nt.links.new(uv.outputs['UV'], mp.inputs[0])
    a = nt.nodes.new('ShaderNodeTexImage'); a.image = img(folder + alb); nt.links.new(mp.outputs[0], a.inputs[0])
    if vcol:
        vc = nt.nodes.new('ShaderNodeVertexColor'); mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1.0
        nt.links.new(a.outputs[0], mix.inputs[6]); nt.links.new(vc.outputs[0], mix.inputs[7])
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    else:
        nt.links.new(a.outputs[0], b.inputs['Base Color'])
    if nor:
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = img(folder + nor, True); nt.links.new(mp.outputs[0], n.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(n.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    if orm:
        o = nt.nodes.new('ShaderNodeTexImage'); o.image = img(folder + orm, True); nt.links.new(mp.outputs[0], o.inputs[0])
        sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(o.outputs[0], sp.inputs[0]); nt.links.new(sp.outputs[1], b.inputs['Roughness'])
    return b

def bind_kit(objs):
    done = {}
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if not m or m.name in done: continue
            base = m.name.split('.')[0]; done[m.name] = 1
            if os.path.exists(f"{GT}{base}_albedo.png"):
                pbr(m, base, GT, f"{base}_albedo.png", f"{base}_normal.png", f"{base}_ormh.png")
            elif os.path.exists(f"{GAME}{base}_albedo.png"):
                pbr(m, base, GAME, f"{base}_albedo.png", f"{base}_normal.png", f"{base}_ormh.png")
            else:   # 'fruit' & friends: vertex colour only
                m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
                out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
                b.inputs['Roughness'].default_value = 0.8; b.inputs['Base Color'].default_value = (0.30, 0.34, 0.09, 1)
                nt.links.new(b.outputs[0], out.inputs[0])

kit_objs = {}
for g in ("town_kit", "market", "bridges_kit", "meadow_kit"):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f"{GAME}{g}.glb")
    new = [o for o in set(bpy.data.objects) - before if o.type == 'MESH']
    bind_kit(new)
    for o in new:
        kit_objs[o.name] = o
        o.hide_render = True; o.hide_viewport = True   # templates

def place(name, x, y, face=(0, -1), scale=1.0, z=0.0):
    """instance a template; 'face' = world direction the piece's front (glTF +Z = Blender -Y) should point."""
    src = kit_objs[name]
    o = src.copy(); o.data = src.data
    scene.collection.objects.link(o)
    o.hide_render = False; o.hide_viewport = False
    ang = math.atan2(face[1], face[0]) + math.pi / 2
    o.rotation_euler = (0, 0, ang); o.location = (x, y, z); o.scale = (scale,) * 3
    return o

_PH = {}
def ph(model, x, y, rot=0.0, scale=1.0, z=0.0):
    if model not in _PH:
        files = [f for f in os.listdir(PHM + model) if f.endswith('.gltf')]
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=PHM + model + "/" + files[0])
        new = set(bpy.data.objects) - before
        _PH[model] = [o for o in new if o.parent is None][0]
        for o in new: o.hide_render = True; o.hide_viewport = True
    tmpl = _PH[model]
    def clone(o, parent):
        c = o.copy(); 
        if o.data is not None: c.data = o.data
        scene.collection.objects.link(c); c.parent = parent
        c.hide_render = False; c.hide_viewport = False
        for ch in o.children: clone(ch, c)
        return c
    root = clone(tmpl, None)
    root.location = (x, y, z); root.rotation_euler = (tmpl.rotation_euler.x, tmpl.rotation_euler.y, rot); root.scale = (scale,) * 3
    return root

# ------------------------------------------------------------------ ground + sky + lights
bpy.ops.mesh.primitive_plane_add(size=240, location=(0, 0, 0))
ground = bpy.context.active_object
gm = bpy.data.materials.new('ground'); gm.use_nodes = True
nt = gm.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled'); nt.links.new(b.outputs[0], out.inputs[0])
tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (30, 30, 30)
nt.links.new(tc.outputs['UV'], mp.inputs[0])
def gtex(f, nc=False):
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(GAME + f, nc); nt.links.new(mp.outputs[0], t.inputs[0]); return t
moss, path = gtex('ground_moss_albedo.png'), gtex('ground_path_albedo.png')
mn, pn = gtex('ground_moss_normal.png', True), gtex('ground_path_normal.png', True)
# path mask: radial around square + noise
pos = nt.nodes.new('ShaderNodeTexCoord')
sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(pos.outputs['Object'], sep.inputs[0])
ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; nt.links.new(pos.outputs['Object'], ln.inputs[0])
noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 0.35; noise.inputs['Detail'].default_value = 4
nt.links.new(pos.outputs['Object'], noise.inputs['Vector'])
sub = nt.nodes.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; nt.links.new(ln.outputs['Value'], sub.inputs[0]); sub.inputs[1].default_value = 11
nz = nt.nodes.new('ShaderNodeMath'); nz.operation = 'MULTIPLY'; nt.links.new(noise.outputs['Fac'], nz.inputs[0]); nz.inputs[1].default_value = 9
add = nt.nodes.new('ShaderNodeMath'); add.operation = 'SUBTRACT'; nt.links.new(sub.outputs[0], add.inputs[0]); nt.links.new(nz.outputs[0], add.inputs[1])
ramp = nt.nodes.new('ShaderNodeMapRange'); ramp.inputs[1].default_value = -4; ramp.inputs[2].default_value = 6; ramp.inputs[3].default_value = 1; ramp.inputs[4].default_value = 0
nt.links.new(add.outputs[0], ramp.inputs[0])
cmix = nt.nodes.new('ShaderNodeMix'); cmix.data_type = 'RGBA'
nt.links.new(ramp.outputs[0], cmix.inputs[0]); nt.links.new(moss.outputs[0], cmix.inputs[6]); nt.links.new(path.outputs[0], cmix.inputs[7])
nmix = nt.nodes.new('ShaderNodeMix'); nmix.data_type = 'RGBA'
nt.links.new(ramp.outputs[0], nmix.inputs[0]); nt.links.new(mn.outputs[0], nmix.inputs[6]); nt.links.new(pn.outputs[0], nmix.inputs[7])
nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(nmix.outputs[2], nm.inputs['Color'])
nt.links.new(cmix.outputs[2], b.inputs['Base Color']); nt.links.new(nm.outputs[0], b.inputs['Normal']); b.inputs['Roughness'].default_value = 0.9
ground.data.materials.append(gm)

world = bpy.data.worlds.new('sky'); scene.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links; wn.clear()
sky = wn.new('ShaderNodeTexSky'); sky.sky_type = 'NISHITA'; sky.sun_elevation = math.radians(24); sky.sun_rotation = math.radians(215)
sky.sun_size = math.radians(1.2); sky.sun_intensity = 0.0; sky.air_density = 0.55; sky.dust_density = 0.5
bg = wn.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.9
wo = wn.new('ShaderNodeOutputWorld'); wl.new(sky.outputs[0], bg.inputs[0]); wl.new(bg.outputs[0], wo.inputs[0])
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 4.2; sun.angle = math.radians(1.5); sun.color = (1.0, 0.9, 0.76)
so = bpy.data.objects.new('sun', sun); scene.collection.objects.link(so)
so.rotation_euler = (math.radians(66), 0, math.radians(215 - 90 + 180))  # low sun from the south-west

# ------------------------------------------------------------------ the village
# (Blender X east, Y north.  Kit front = glTF +Z -> 'face' is the direction the door looks.)
place('yard_well', 0, 0)
place('town_tavern', -15, 4, face=(1, 0))
place('town_smithy', 14, 4, face=(-1, 0))
place('town_house_a', -6, 17, face=(0, -1))
place('town_house_b', 6, 18, face=(0, -1))
place('town_house_c', 18, 15, face=(-0.6, -1))
place('town_maud_house', 12, -14, face=(-0.3, 1))
place('town_granary', -22, 14, face=(1, -0.5))
place('decor_notice_board', -4, 8, face=(0, -1))
place('market_veg', -7, -9, face=(0, 1))
place('market_bread', -2, -9, face=(0, 1))
place('market_cloth', 3, -9, face=(0, 1))
place('market_cart', 7.5, -8, face=(-0.5, 1))
place('market_barrels', -10, -7, face=(1, 0.6))
place('town_farm', 27, -7, face=(-1, 0))
place('town_garden', 20, -12, face=(-0.3, 1))
place('meadow_scarecrow', 24, -15, face=(-0.5, 1))
place('meadow_bale', 31, -14); place('meadow_bale', 29.5, -16.5, face=(1, 0.3)); place('yard_hay', 22.5, -4)
place('meadow_hay_cart', 30, -1, face=(-1, -0.2))
place('town_woodcutter', -26, -8, face=(1, 0.2))
place('town_woodpile', -20.5, -11, face=(0.4, 1)); place('yard_wood', -22, -5.5, face=(1, 0))
place('town_mine', 24, 24, face=(-0.4, -1))
h = place('miner_handcart', -4, 13, face=(0, -1))
place('town_firepit', -3, -2.5)
place('gate_brazier', -9, -1.5); place('decor_trough', 10, 8, face=(-1, 0))
place('training_dummy', 14, -3.5, face=(-1, 0.3))
place('town_fence_picket', 17, -2.0, face=(0, -1)); place('town_fence_picket', 20.1, -2.0, face=(0, -1))
place('castle_lantern', -8.2, 7.6); place('castle_lantern', 6.5, 9.2)
# Poly Haven replacements for the game's own benches / barrels / crates / buckets
ph('painted_wooden_bench', -8.55, 3.05, rot=math.radians(90), scale=0.9)
ph('painted_wooden_bench', 8.6, 5.2, rot=math.radians(-90), scale=0.9)
ph('wine_barrel_01', -9.4, 7.4, scale=0.9); ph('wooden_barrels_01', -10.5, 1.4, rot=0.6, scale=0.8)
ph('wooden_crate_01', -5.2, -7.2, scale=0.8); ph('wooden_crate_02', -4.6, -6.8, rot=0.5, scale=0.7)
ph('wooden_bucket_01', 1.3, -1.1, scale=0.8); ph('wooden_bucket_01', 19, -10, rot=1.0, scale=0.8)
ph('wooden_crate_01', 12.2, 2.0, rot=0.3, scale=0.8)
ph('tree_stump_01', -19.5, -6.0, scale=0.8)
for (x, y) in [(-34, -2), (-32, 14), (-12, 30), (4, 33), (24, 36), (40, 14), (42, -10), (36, -26), (8, -32), (-14, -30), (-36, -20)]:
    ph(random.choice(['tree_small_02', 'fir_sapling', 'tree_small_02']), x + random.uniform(-3, 3), y + random.uniform(-3, 3), rot=random.uniform(0, 6.28), scale=random.uniform(2.0, 3.4))
for i in range(60):
    a = random.uniform(0, 6.28); r = random.uniform(22, 55)
    ph(random.choice(['shrub_01', 'shrub_02', 'shrub_03', 'shrub_04', 'fern_02', 'grass_medium_01']), math.cos(a) * r * 1.2, math.sin(a) * r, rot=random.uniform(0, 6.28), scale=random.uniform(1.0, 2.2))

# ------------------------------------------------------------------ actors
def put(name, x, y, face_deg, scale=HUMAN_SCALE):
    rig = cast[name]
    rig.scale = (scale,) * 3
    rig.location = (x, y, 0); rig.rotation_euler = (0, 0, math.radians(face_deg))
    return rig

def walk(name, pts, speed, t0=1, face_off=0.0):
    """keyframe the rig along polyline pts at speed (units/frame), facing the heading. returns end frame."""
    rig = cast[name]; f = t0
    p0 = Vector(pts[0])
    rig.location = (p0.x, p0.y, 0)
    rig.keyframe_insert('location', frame=f)
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = Vector(a), Vector(b); d = b - a
        ang = math.atan2(d.y, d.x) + math.pi / 2 + face_off   # character front = -Y
        rig.rotation_euler = (0, 0, ang); rig.keyframe_insert('rotation_euler', frame=f)
        f += d.length / speed
        rig.location = (b.x, b.y, 0); rig.keyframe_insert('location', frame=f)
        rig.rotation_euler = (0, 0, ang); rig.keyframe_insert('rotation_euler', frame=f)
    return f

def facing_deg(dx, dy):  # world heading -> rig z rotation (front = -Y)
    return math.degrees(math.atan2(dy, dx)) + 90

# elders on the bench in front of the tavern, chatting
put('elder_m', -8.0, 2.65, facing_deg(1, 0.1)); actor_clip('elder_m', 'Sitting_Talking_Loop', 0)
put('elder_f', -8.0, 3.45, facing_deg(1, -0.2)); actor_clip('elder_f', 'Sitting_Idle_Loop', 7)
# guard + villager talking
put('guard', -2.8, 6.2, facing_deg(1, -0.1)); actor_clip('guard', 'Idle_Talking_Loop', 3)
put('villager_m', -1.4, 6.3, facing_deg(-1, 0.05)); actor_clip('villager_m', 'Idle_FoldArms_Loop', 9)
# priest by the notice board, blessing the passers-by
put('priest', -5.5, 9.4, facing_deg(0.7, -1)); actor_clip('priest', 'Interact', 0)
# merchant calling behind his stall
put('merchant', -2.0, -10.1, facing_deg(0, 1)); actor_clip('merchant', 'Idle_Rail_Call', 11)
# woman with a basket crossing the market
n = actor_clip('villager_f2', 'Walk_Carry_Loop', 0)
walk('villager_f2', [(-24, -4), (-6, -6.5), (8, -6.5), (18, -3)], 1.2 * HUMAN_SCALE / 30)
# farm: farmer sowing, woman watering the garden
put('farmer', 22.0, -9.0, facing_deg(0.4, -1)); actor_clip('farmer', 'Farm_PlantSeed', 0)
put('villager_f1', 20.2, -10.3, facing_deg(-0.2, 1)); actor_clip('villager_f1', 'Farm_Watering', 5)
# woodcutter
put('woodcutter', -21.4, -9.3, facing_deg(0.2, 1)); actor_clip('woodcutter', 'TreeChopping_Loop', 0)
# miner pushing the hand-cart along the road, cart rides ahead of him
actor_clip('miner', 'Push_Loop', 0)
mf = walk('miner', [(18, 24), (12, 14), (4, 12), (-8, 12), (-20, 12)], 0.9 * HUMAN_SCALE / 30)
cart = [o for o in scene.objects if o.type == 'MESH' and o.data == kit_objs['miner_handcart'].data and not o.hide_render][0]
cart.parent = cast['miner']; cart.matrix_parent_inverse = Matrix.Identity(4); cart.location = (0, -1.6 / HUMAN_SCALE, 0.0); cart.rotation_euler = (0, 0, math.pi); cart.scale = (1 / HUMAN_SCALE,) * 3
# archer on patrol
actor_clip('archer', 'Walk_Formal_Loop', 0)
walk('archer', [(12, 10), (12, 3), (12, -3), (12, 3), (12, 10)] * 12, 1.2 * HUMAN_SCALE / 30)
# kids running around the well + dancing girl
actor_clip('boy', 'Jog_Fwd_Loop', 0)
R = 4.2; pts = [(R * math.cos(t), R * math.sin(t)) for t in [i * math.pi / 8 for i in range(0, 8 * 16 + 1)]]
walk('boy', pts, 3.0 * HUMAN_SCALE / 30)
put('girl', 3.0, 3.2, facing_deg(-1, -0.5)); actor_clip('girl', 'Dance_Loop', 0)

# ------------------------------------------------------------------ camera
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 32; cam_d.dof.use_dof = False
cam = bpy.data.objects.new('cam', cam_d); scene.collection.objects.link(cam); scene.camera = cam
tgt = bpy.data.objects.new('tgt', None); scene.collection.objects.link(tgt)
tr = cam.constraints.new('TRACK_TO'); tr.target = tgt; tr.track_axis = 'TRACK_NEGATIVE_Z'; tr.up_axis = 'UP_Y'

def pos(name, frame, dz=0.0):
    scene.frame_set(frame)
    t = cast[name].matrix_world.translation
    return (t.x, t.y, t.z + dz)

def add(a, b): return tuple(x + y for x, y in zip(a, b))

TL = [210, 170, 150, 170, 190, 150, 170, 190]
ST = [1]
for n in TL[:-1]: ST.append(ST[-1] + n)
E = [a + n - 1 for a, n in zip(ST, TL)]
SHOTS = [  # (frames, cam0, cam1, tgt0, tgt1, lens)
    (TL[0], (-30, -36, 9.0), (-18, -30, 6.0), (0, 2, 1.5), (0, 2, 1.5), 30),
    (TL[1], (-1.5, -2.0, 1.1), (-3.5, -0.5, 1.1), (-8.0, 3.1, 0.8), (-8.0, 3.1, 0.8), 40),
    (TL[2], (-5.5, 3.2, 1.25), (-4.2, 2.6, 1.25), (-2.1, 6.2, 1.0), (-2.1, 6.2, 1.0), 45),
    (TL[3], (-4.5, -3.6, 1.3), (-1.5, -3.8, 1.3), (-2.0, -9.8, 1.0), (-2.4, -9.8, 1.0), 40),
    (TL[4], (14.5, -4.0, 1.6), (17.5, -6.5, 1.5), (21.5, -10.0, 0.9), (21.5, -10.0, 0.9), 38),
    (TL[5], (-15.5, -14.0, 1.4), (-17.5, -13.5, 1.4), (-21.4, -9.3, 1.0), (-21.4, -9.3, 1.0), 40),
    (TL[6], add(pos('miner', ST[6]), (5.0, -3.2, 0.5)), add(pos('miner', E[6]), (5.0, -3.2, 0.5)), pos('miner', ST[6], 0.7), pos('miner', E[6], 0.7), 35),
    (TL[7], (3.0, -6.5, 1.6), (6.5, -5.8, 1.6), (0, 1, 1.0), (0.5, 1.5, 1.0), 30),
]
f = 1
for (n, c0, c1, t0, t1, lens) in SHOTS:
    for (frm, c, t) in ((f, c0, t0), (f + n - 1, c1, t1)):
        cam.location = c; cam.keyframe_insert('location', frame=frm)
        tgt.location = t; tgt.keyframe_insert('location', frame=frm)
        cam_d.lens = lens; cam_d.keyframe_insert('lens', frame=frm)
    # hold the cut: key the previous shot's end just before this start so interpolation does not blend shots
    f += n
for ob in (cam, tgt, cam_d):
    ad = ob.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
TOTAL = f - 1
print("P total frames", TOTAL)

# ------------------------------------------------------------------ render
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
scene.render.resolution_percentage = RES
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
scene.eevee.taa_render_samples = SAMPLES
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, TOTAL
os.makedirs(OUT, exist_ok=True)
for fr in [x for x in FR if x <= TOTAL]:
    scene.frame_set(fr)
    scene.render.filepath = f"{OUT}/f_{fr:05d}.png"
    bpy.ops.render.render(write_still=True)
print("P DONE")
