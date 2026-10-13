import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import npc_cast
out=sys.argv[sys.argv.index('--')+1]
for i,s in enumerate(npc_cast.cast()):
    hm,rig,parts=npc_cast.make(s)
    rig.location.x=i*1.5
    rig['npc']=s['name']
    for o in [hm]+parts: o['npc']=s['name']
for o in list(bpy.data.objects):
    if o.name.startswith('Cube'): bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("P saved")
