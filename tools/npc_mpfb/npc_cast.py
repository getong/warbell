"""Medieval NPC cast built with MPFB (MakeHuman): bodies + retextured garments. Use inside Blender."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mpfb_cast import build, mh
from bl_ext.user_default.mpfb.services.humanservice import HumanService

PH = "C:/Users/skibi/Documents/Codex/polyhaven_src/textures/"
FABRIC = {  # kind -> (folder, diffuse, normal, rough, uv scale, base roughness)
    'linen':   ('rough_linen', 'rough_linen_diff_2k.png', 'rough_linen_nor_gl_2k.png', 'rough_linen_rough_2k.png', 5.0),
    'wool':    ('poly_wool_herringbone', 'poly_wool_herringbone_diff_2k.png', 'poly_wool_herringbone_nor_gl_2k.png', 'poly_wool_herringbone_rough_2k.png', 5.0),
    'hessian': ('hessian_230', 'hessian_230_diff_2k.png', 'hessian_230_nor_gl_2k.png', 'hessian_230_rough_2k.png', 4.0),
    'leather': ('brown_leather', 'brown_leather_albedo_2k.png', 'brown_leather_nor_gl_2k.png', 'brown_leather_rough_2k.png', 3.0),
}

def img(path, nc=False):
    i = bpy.data.images.load(path, check_existing=True)
    if nc: i.colorspace_settings.name = 'Non-Color'
    return i

# '<kind>_n' = the same fabric with its albedo NEUTRALISED (luminance only, re-brightened), so the tint is
# the real dye colour: Poly Haven's rough_linen diffuse is distinctly blue (mean sRGB 145/171/206), which
# turns a 'cream' linen tint into pale blue.
NEUTRAL_GAIN = 2.0


def neutral_lum(nt, color_socket, gain=NEUTRAL_GAIN):
    """texture colour -> grey luminance * gain (output socket)"""
    bw = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(color_socket, bw.inputs[0])
    g = nt.nodes.new('ShaderNodeMath'); g.operation = 'MULTIPLY'; g.inputs[1].default_value = gain
    nt.links.new(bw.outputs[0], g.inputs[0])
    return g.outputs[0]


def tint_hair(o, tint, gain):
    """Re-dye a MakeHuman hair material: its diffuse texture's luminance * gain * tint (keeps the strand
    detail + alpha, drops the stock colour) -- e.g. a blonde bun -> a matron's grey."""
    for m in o.data.materials:
        nt = m.node_tree
        for t in [n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.name == 'diffuseTexture']:
            dests = [l.to_socket for l in t.outputs['Color'].links]
            mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
            mix.inputs[0].default_value = 1.0; mix.inputs[7].default_value = tint
            nt.links.new(neutral_lum(nt, t.outputs['Color'], gain), mix.inputs[6])
            for d in dests:
                nt.links.new(mix.outputs[2], d)


def fabric_mat(name, kind, tint, dirt=0.0):
    neutral = kind.endswith('_n')
    kind = kind[:-2] if neutral else kind
    folder, d, n, r, sc = FABRIC[kind]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    uv = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (sc, sc, sc)
    nt.links.new(uv.outputs['UV'], mp.inputs[0])
    def tex(file, nc=False):
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(PH + folder + "/" + file, nc); t.interpolation = 'Smart'
        nt.links.new(mp.outputs[0], t.inputs[0]); return t
    a = tex(d); nrm = tex(n, True); ro = tex(r, True)
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1.0; mix.inputs[7].default_value = tint
    # fabric albedo is bright/neutral: boost low-saturation textures toward the tint
    if neutral:
        nt.links.new(neutral_lum(nt, a.outputs[0]), mix.inputs[6])
    else:
        nt.links.new(a.outputs[0], mix.inputs[6])
    nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 0.9
    nt.links.new(nrm.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], b.inputs['Normal'])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs[3].default_value = 0.85; mr.inputs[4].default_value = 1.0
    nt.links.new(ro.outputs[0], mr.inputs[0]); nt.links.new(mr.outputs[0], b.inputs['Roughness'])
    b.inputs['Specular IOR Level'].default_value = 0.12
    if kind == 'wool' or kind == 'linen':
        b.inputs['Sheen Weight'].default_value = 0.15
    return m

def hexc(h):  # sRGB hex -> linear rgba
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c]
    return (*lin, 1.0)

def make(spec):
    for o in list(bpy.data.objects):
        if o.name.startswith('Cube'): bpy.data.objects.remove(o)
    hm, rig, parts = build(spec)
    hm.name = rig.name = spec['name']
    for layer, g in enumerate(spec.get('garments', [])):
        asset, kind, tint = g[:3]
        sub = 'hair' if asset in spec.get('_hairs', ()) else 'clothes'
        o = HumanService.add_mhclo_asset(mh(f"clothes/{asset}/{asset}.mhclo"), hm, asset_type='Clothes', material_type='MAKESKIN')
        if kind != 'hair':
            o.data.materials.clear()
            o.data.materials.append(fabric_mat(f"{spec['name']}_{asset}", kind, hexc(tint) if isinstance(tint, str) else tint))
        for p in o.data.polygons: p.use_smooth = True
        # garment stacking order = list order (inner first); export_game.py's layer pass uses it
        o['layer'] = layer
        parts.append(o)
    if spec.get('hair_tint') and spec.get('hair'):
        for o in parts:
            if spec['hair'] in o.name:
                tint_hair(o, hexc(spec['hair_tint']), spec.get('hair_gain', 2.0))
    return hm, rig, parts

# ---- the cast ---------------------------------------------------------------------------------
LIN = {'cream': '#e9dfc6', 'ochre': '#c9a560', 'grey': '#b3ab9a', 'blue': '#6f8197', 'green': '#80905f', 'red': '#a85d4a', 'white': '#f2eee2'}
WOOL = {'brown': '#6b4b32', 'dkbrown': '#4a3523', 'grey': '#7a766d', 'green': '#4f5a38', 'blue': '#3b5273', 'black': '#2d2b29', 'rust': '#8a4a2c', 'wine': '#6e3030'}

def cast():
    boots_m = ('maciekg_leather_boots', 'leather', '#a9825c')
    boots_m2 = ('punkduck_medieval_boots', 'leather', '#8d6a49')
    boots_f = ('punkduck_female_half-boots', 'leather', '#8d6a49')
    return [
        dict(name='farmer', gender=1, age=.62, muscle=.55, weight=.5, height=.5, skin='middleage_caucasian_male', hair='short02', eyebrows='eyebrow003', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'linen', LIN['ochre']), ('toigo_wool_pants', 'wool', WOOL['dkbrown']), boots_m]),
        dict(name='woodcutter', gender=1, age=.58, muscle=.8, weight=.55, height=.58, skin='middleage_caucasian_male', hair='short04', eyebrows='eyebrow005', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'wool', WOOL['green']), ('toigo_wool_pants', 'wool', WOOL['brown']), boots_m2, ('rehmanpolanski_beard_viking', 'hair', '#4a3526')]),
        dict(name='miner', gender=1, age=.52, muscle=.7, weight=.45, height=.42, skin='young_caucasian_male', hair='short01', eyebrows='eyebrow007', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'hessian', '#7d7468'), ('mindfront_male_trousers_2', 'wool', WOOL['grey']), boots_m]),
        dict(name='guard', gender=1, age=.5, muscle=.85, weight=.5, height=.62, skin='young_caucasian_male2', hair='short03', eyebrows='eyebrow002', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'wool', WOOL['blue']), ('toigo_wool_pants', 'wool', WOOL['black']), ('punkduck_riding_boots', 'leather', '#5b4330')]),
        dict(name='archer', gender=1, age=.5, muscle=.5, weight=.38, height=.55, skin='young_caucasian_male', hair='short04', eyebrows='eyebrow004', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'wool', WOOL['green']), ('toigo_wool_pants', 'wool', '#5a5240'), ('culturalibre_male_boots', 'leather', '#6f5238')]),
        dict(name='villager_m', gender=1, age=.48, muscle=.4, weight=.5, height=.48, skin='young_caucasian_male2', hair='short01', eyebrows='eyebrow006', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'linen', LIN['cream']), ('mindfront_male_trousers_2', 'wool', WOOL['rust']), boots_m2]),
        dict(name='villager_f1', gender=0, age=.5, muscle=.3, weight=.5, height=.45, skin='young_caucasian_female', hair='ponytail01', eyebrows='eyebrow001', eyelashes='eyelashes01',
             garments=[('elvs_ruffle_sleeve_peasant_blouse_1', 'linen', LIN['white']), ('toigo_long_full_skirt', 'wool', WOOL['wine']), boots_f]),
        dict(name='villager_f2', gender=0, age=.58, muscle=.3, weight=.62, height=.42, skin='middleage_caucasian_female', hair='bob02', eyebrows='eyebrow008', eyelashes='eyelashes03',
             garments=[('punkduck_lace_up_blouse', 'linen', LIN['cream']), ('toigo_long_full_skirt', 'wool', WOOL['green']), boots_f]),
        dict(name='elder_m', gender=1, age=.93, muscle=.3, weight=.4, height=.42, skin='old_caucasian_male', hair='short04', eyebrows='eyebrow005', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'wool', WOOL['grey']), ('toigo_wool_pants', 'wool', WOOL['dkbrown']), boots_m2, ('grinsegold_full_beard', 'hair', '#cfcfcf')]),
        dict(name='elder_f', gender=0, age=.92, muscle=.2, weight=.45, height=.38, skin='old_caucasian_female', hair='bob01', eyebrows='eyebrow008', eyelashes='eyelashes01',
             garments=[('elvs_ruffle_sleeve_peasant_blouse_1', 'linen', LIN['grey']), ('toigo_long_full_skirt', 'wool', WOOL['black']), boots_f]),
        # Maud, the campaign's matron (60s): modest long-sleeved lace-up chemise worn over a long wool
        # kirtle skirt, a linen bib apron on top, hair up in a braided bun. Garments are listed INNER
        # FIRST (boots < skirt < blouse < apron); `export` turns on export_game.py's hidden-skin cull +
        # garment layer pass and a higher cloth budget (see export_game.py, "layer pass").
        dict(name='maud', gender=0, age=.8, muscle=.3, weight=.55, height=.4, skin='old_caucasian_female', hair='elvs_braid_bun', hair_tint='#b8b3aa', eyebrows='eyebrow008', eyelashes='eyelashes01',
             garments=[boots_f, ('toigo_long_full_skirt', 'wool', WOOL['blue']), ('punkduck_lace_up_blouse', 'linen_n', LIN['cream']), ('elvs_ladies_apron', 'linen_n', '#b9ab8c')],
             export=dict(budget={'body': 12000, 'cloth': 7000, 'boots': 1400, 'hair': 9000}, cloth_subsurf=1, cull_hidden=True, layer_gap=0.004, garment_gap=0.01,
                         inherit_weights=['punkduck_lace_up_blouse', 'elvs_ladies_apron'], drop_cornea=True)),
        dict(name='boy', gender=.5, age=.17, muscle=.3, weight=.4, height=.4, skin='young_caucasian_male', hair='short03', eyebrows='eyebrow002', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'linen', LIN['ochre']), ('toigo_wool_pants', 'wool', WOOL['brown'])]),
        dict(name='girl', gender=.4, age=.17, muscle=.3, weight=.4, height=.4, skin='young_caucasian_female', hair='braid01', eyebrows='eyebrow001', eyelashes='eyelashes01',
             garments=[('elvs_ruffle_sleeve_peasant_blouse_1', 'linen', LIN['cream']), ('toigo_long_full_skirt', 'wool', WOOL['blue'])]),
        dict(name='priest', gender=1, age=.7, muscle=.3, weight=.5, height=.5, skin='middleage_caucasian_male', hair='short02', eyebrows='eyebrow003', eyelashes='eyelashes02',
             garments=[('maciekg_wizard_robe', 'wool', WOOL['dkbrown']), ('maciekg_leather_boots', 'leather', '#6b4d33')]),
        dict(name='merchant', gender=1, age=.68, muscle=.35, weight=.75, height=.5, skin='middleage_caucasian_male', hair='short04', eyebrows='eyebrow006', eyelashes='eyelashes02',
             garments=[('elvs_male_boho_top1', 'wool', WOOL['wine']), ('toigo_wool_pants', 'wool', WOOL['black']), ('punkduck_riding_boots', 'leather', '#4d3a28'), ('wdg_scruffy_beard', 'hair', '#3b2a1e')]),
    ]
