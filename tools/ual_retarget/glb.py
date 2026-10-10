"""Minimal glTF-binary reader: nodes, skins, animations (numpy)."""
import json, struct, numpy as np

CT = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8, 5122: np.int16, 5120: np.int8}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class Glb:
    def __init__(self, path):
        b = open(path, 'rb').read()
        assert b[:4] == b'glTF'
        n = struct.unpack('<I', b[12:16])[0]
        self.j = json.loads(b[20:20 + n])
        off = 20 + n
        bl = struct.unpack('<I', b[off:off + 4])[0]
        self.bin = b[off + 8: off + 8 + bl]

    def acc(self, i):
        a = self.j['accessors'][i]
        bv = self.j['bufferViews'][a['bufferView']]
        dt = CT[a['componentType']]
        nc = NC[a['type']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        cnt = a['count']
        stride = bv.get('byteStride', 0)
        if stride and stride != nc * np.dtype(dt).itemsize:
            raw = np.frombuffer(self.bin, np.uint8, cnt * stride, start).reshape(cnt, stride)
            return raw[:, :nc * np.dtype(dt).itemsize].copy().view(dt).reshape(cnt, nc)
        return np.frombuffer(self.bin, dt, cnt * nc, start).reshape(cnt, nc).astype(np.float64)

    def anims(self):
        return [a['name'] for a in self.j.get('animations', [])]

    def anim(self, name):
        """{node_index: {'translation'|'rotation'|'scale': (times, values)}}"""
        a = next(x for x in self.j['animations'] if x['name'] == name)
        out = {}
        for ch in a['channels']:
            s = a['samplers'][ch['sampler']]
            t = self.acc(s['input'])[:, 0]
            v = self.acc(s['output'])
            out.setdefault(ch['target']['node'], {})[ch['target']['path']] = (t, v)
        return out
