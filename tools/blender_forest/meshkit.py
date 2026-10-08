"""Per-corner mesh builder shared by the procedural forest scripts."""
import bpy
from mathutils import Vector

from common import name_material


class Builder:
    """Accumulates per-corner geometry: every face corner carries its own uv/normal/colour."""

    def __init__(self):
        self.verts = []
        self.faces = []  # (vert idx tuple, uvs, normals, colours, material slot)

    def v(self, p):
        self.verts.append(tuple(p))
        return len(self.verts) - 1

    def face(self, idx, uvs, nrms, cols, mat):
        self.faces.append((tuple(idx), uvs, nrms, cols, mat))

    def tris(self):
        return sum(len(f[0]) - 2 for f in self.faces)

    def build(self, name, materials):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], [f[0] for f in self.faces])
        for m in materials:
            me.materials.append(name_material(m))
        # Create BOTH layers before touching either: adding a layer reallocates the loop
        # CustomData and leaves earlier Python layer references writing into stale memory.
        me.uv_layers.new(name="UVMap")
        me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        uvs, cols, loop_n, mats = [], [], [], []
        for f in self.faces:
            mats.append(f[4])
            for k in range(len(f[0])):
                uvs.extend(f[1][k])
                c = f[3][k]
                cols.extend((c[0], c[1], c[2], 1.0))
                loop_n.append(tuple(Vector(f[2][k]).normalized()))
        me.polygons.foreach_set("material_index", mats)
        me.polygons.foreach_set("use_smooth", [True] * len(mats))
        me.uv_layers["UVMap"].data.foreach_set("uv", uvs)
        me.color_attributes["Col"].data.foreach_set("color", cols)
        me.normals_split_custom_set(loop_n)
        me.color_attributes.active_color = me.color_attributes["Col"]

        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob
