"""Build the cast (or a subset) into one .blend.

    blender -b --python build_cast_blend.py -- <out.blend> [name,name,...]

With no names: the whole cast() list. Each armature gets `npc` = name and `npc_export` = the spec's
`export` dict as JSON (export_game.py reads it; empty = the stock export).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import npc_cast
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
only = set(argv[1].split(',')) if len(argv) > 1 and argv[1] else None
specs = [s for s in npc_cast.cast() if only is None or s['name'] in only]
if only and len(specs) != len(only):
    raise SystemExit(f"unknown cast names: {sorted(only - {s['name'] for s in specs})}")
for i, s in enumerate(specs):
    hm, rig, parts = npc_cast.make(s)
    rig.location.x = i * 1.5
    rig['npc'] = s['name']
    rig['npc_export'] = json.dumps(s.get('export', {}))
    for o in [hm] + parts: o['npc'] = s['name']
for o in list(bpy.data.objects):
    if o.name.startswith('Cube'): bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("P saved")
