import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, math
import npc_cast
argv=sys.argv[sys.argv.index('--')+1:]; out=argv[0]; only=argv[1:]
specs=[s for s in npc_cast.cast() if not only or s['name'] in only]
N=len(specs); per=7 if N>7 else N; SP=1.15
for i,s in enumerate(specs):
    hm,rig,parts=npc_cast.make(s)
    rig.location=((i%per-(per-1)/2)*SP, -(i//per)*0.0, 0)
    rig.location.z += 0
    if i//per: rig.location.x+=0; rig.location.y=0; rig.location.z=-2.4
sc=bpy.context.scene
sc.render.engine='BLENDER_EEVEE_NEXT'
rows=(N+per-1)//per
sc.render.resolution_x=2400; sc.render.resolution_y=int(2400*(rows*2.4)/(per*SP))
sc.view_settings.view_transform='AgX'
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs[0].default_value=(.32,.34,.37,1)
l=bpy.data.lights.new('s','SUN'); l.energy=3.0; o=bpy.data.objects.new('s',l); sc.collection.objects.link(o); o.rotation_euler=(math.radians(55),0,math.radians(-20))
l2=bpy.data.lights.new('f','SUN'); l2.energy=1.2; o2=bpy.data.objects.new('f',l2); sc.collection.objects.link(o2); o2.rotation_euler=(math.radians(70),0,math.radians(150))
c=bpy.data.cameras.new('c'); c.type='ORTHO'; c.ortho_scale=per*SP; co=bpy.data.objects.new('c',c); sc.collection.objects.link(co); sc.camera=co
co.location=(0,-10,0.95-(rows-1)*1.2); co.rotation_euler=(math.radians(90),0,0)
c.ortho_scale=max(per*SP, rows*2.4*2400/ (2400) *  (2400/ sc.render.resolution_y) * 0 + per*SP)
sc.render.filepath=out; bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=out.replace('.png','.blend'))
