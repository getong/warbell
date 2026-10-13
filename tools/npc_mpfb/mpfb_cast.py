"""Build one MPFB (MakeHuman) character from a spec dict. Import inside Blender after enabling MPFB."""
import bpy, os, math
bpy.ops.preferences.addon_enable(module='bl_ext.user_default.mpfb')
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.locationservice import LocationService
from bl_ext.user_default.mpfb.services.targetservice import TargetService

U = LocationService.get_user_data()
def mh(p): return os.path.join(U, p)

def build(spec):
    """spec: gender(0 f..1 m) age(0..1; .5=25y, 1=90y) muscle weight height race{} skin eyes hair eyebrows eyelashes clothes[list] rig"""
    md = TargetService.get_default_macro_info_dict()
    for k in ('gender', 'age', 'muscle', 'weight', 'height', 'proportions', 'cupsize', 'firmness'):
        if k in spec: md[k] = spec[k]
    md['race'] = spec.get('race', {'asian': 0.0, 'caucasian': 1.0, 'african': 0.0})
    hm = HumanService.create_human(macro_detail_dict=md, scale=0.1, mask_helpers=True)
    rig = HumanService.add_builtin_rig(hm, spec.get('rig', 'game_engine'))
    HumanService.set_character_skin(mh(f"skins/{spec['skin']}/{spec['skin']}.mhmat"), hm, skin_type='ENHANCED_SSS')
    parts = []
    def add(path, typ):
        o = HumanService.add_mhclo_asset(mh(path), hm, asset_type=typ, material_type='MAKESKIN')
        parts.append(o); return o
    add('eyes/high-poly/high-poly.mhclo', 'Eyes')
    if spec.get('eyebrows'): add(f"eyebrows/{spec['eyebrows']}/{spec['eyebrows']}.mhclo", 'Eyebrows')
    if spec.get('eyelashes'): add(f"eyelashes/{spec['eyelashes']}/{spec['eyelashes']}.mhclo", 'Eyelashes')
    if spec.get('hair'): add(f"hair/{spec['hair']}/{spec['hair']}.mhclo", 'Hair')
    for c in spec.get('clothes', []):
        add(f"clothes/{c}/{c}.mhclo", 'Clothes')
    return hm, rig, parts
