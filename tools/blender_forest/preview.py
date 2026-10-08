"""Studio preview of the forest kit: imports the exported GLBs, binds the PBR sets by material
name (the same mapping the game uses) and renders a lineup with Eevee.

    blender -b --factory-startup --python tools/blender_forest/preview.py -- <out.png> [glb ...]
"""
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from common import OUT, REPO, clear_scene  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out_png = Path(argv[0]).resolve() if argv else REPO / "shots" / "realforest" / "blender_preview.png"
glbs = argv[1:] or ["trees.glb"]

clear_scene()
scene = bpy.context.scene
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        pass
scene.render.resolution_x, scene.render.resolution_y = 1600, 800
scene.view_settings.view_transform = "AgX"


def tex(nt, name, non_color=False):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(str(OUT / name), check_existing=True)
    if non_color:
        n.image.colorspace_settings.name = "Non-Color"
    return n


def pbr_material(mat, set_name, cutout=False):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs[0], outn.inputs[0])
    alb = tex(nt, f"{set_name}_albedo.png")
    vc = nt.nodes.new("ShaderNodeVertexColor")
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    nt.links.new(alb.outputs[0], mul.inputs[6])
    nt.links.new(vc.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    nm = tex(nt, f"{set_name}_normal.png", True)
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nm.outputs[0], nmap.inputs[1])
    nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
    if cutout:
        nt.links.new(alb.outputs[1], bsdf.inputs["Alpha"])
        mat.blend_method = "CLIP" if hasattr(mat, "blend_method") else mat.blend_method
        try:
            mat.surface_render_method = "DITHERED"
        except AttributeError:
            pass
        bsdf.inputs["Roughness"].default_value = 0.7
        bsdf.inputs["Subsurface Weight"].default_value = 0.0
        try:
            bsdf.inputs["Transmission Weight"].default_value = 0.0
        except KeyError:
            pass
    else:
        arh = tex(nt, f"{set_name}_ormh.png", True)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(arh.outputs[0], sep.inputs[0])
        nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])


SETS = {"canopy": ("canopy", True), "undergrowth": ("undergrowth", True)}
for g in glbs:
    bpy.ops.import_scene.gltf(filepath=str(OUT / g))
for mat in bpy.data.materials:
    base = mat.name.split(".")[0]
    set_name, cut = SETS.get(base, (base, False))
    if (OUT / f"{set_name}_albedo.png").exists():
        pbr_material(mat, set_name, cut)

# Lay out lod0 objects in a row (lod1 behind them).
objs = sorted([o for o in scene.objects if o.type == "MESH"], key=lambda o: o.name)
x = 0.0
for o in objs:
    lod1 = o.name.endswith("lod1")
    o.location = (x if not lod1 else x, 0 if not lod1 else 9, 0)
    o.rotation_euler = (math.radians(90), 0, 0)  # glTF import already Y-up->Z-up; keep upright
    o.rotation_euler = (0, 0, 0)
    if not lod1:
        x += 4.2
for o in objs:
    if o.name.endswith("lod1"):
        twin = scene.objects.get(o.name.replace("lod1", "lod0"))
        if twin:
            o.location = (twin.location.x, 9, 0)

# Ground plane with the litter layer.
bpy.ops.mesh.primitive_plane_add(size=200, location=(x / 2, 0, 0))
plane = bpy.context.object
gm = bpy.data.materials.new("ground_litter")
pbr_material(gm, "ground_litter")
mapping = gm.node_tree.nodes.new("ShaderNodeMapping")
mapping.inputs["Scale"].default_value = (70, 70, 70)
coord = gm.node_tree.nodes.new("ShaderNodeTexCoord")
gm.node_tree.links.new(coord.outputs["UV"], mapping.inputs[0])
for n in gm.node_tree.nodes:
    if n.type == "TEX_IMAGE":
        gm.node_tree.links.new(mapping.outputs[0], n.inputs[0])
plane.data.materials.append(gm)
plane.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
for c in plane.data.color_attributes[0].data:
    c.color = (1, 1, 1, 1)

sun = bpy.data.lights.new("sun", "SUN")
sun.energy = 4.0
sun.angle = math.radians(3)
so = bpy.data.objects.new("sun", sun)
so.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
scene.collection.objects.link(so)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.65, 0.8, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
scene.world = world

cam = bpy.data.cameras.new("cam")
cam.lens = 35
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
target = Vector((x / 2 - 2.1, 3, 2.4))
co.location = target + Vector((0, -26, 4))
co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = co
scene.render.filepath = str(out_png)
bpy.ops.render.render(write_still=True)
print("PREVIEW_DONE", out_png)
