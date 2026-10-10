"""UAL2 skeleton FK over an animation clip (glTF, Y up)."""
import numpy as np
from glb import Glb

import os
UAL = os.environ.get('UAL2_GLB', 'UAL2_Standard.glb')


def qmul(a, b):
    w1, x1, y1, z1 = a[..., 3], a[..., 0], a[..., 1], a[..., 2]
    w2, x2, y2, z2 = b[..., 3], b[..., 0], b[..., 1], b[..., 2]
    return np.stack([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                     w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2], -1)


def qrot(q, v):
    """rotate v by quaternion q (x,y,z,w)."""
    u = q[..., :3]
    w = q[..., 3:4]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def slerp(q0, q1, t):
    d = np.sum(q0 * q1, -1, keepdims=True)
    q1 = np.where(d < 0, -q1, q1)
    d = np.abs(d)
    om = np.arccos(np.clip(d, -1, 1))
    so = np.sin(om)
    a = np.where(so > 1e-6, np.sin((1 - t) * om) / np.where(so > 1e-6, so, 1), 1 - t)
    b = np.where(so > 1e-6, np.sin(t * om) / np.where(so > 1e-6, so, 1), t)
    return a * q0 + b * q1


class Rig:
    def __init__(self, path=UAL):
        self.g = Glb(path)
        j = self.g.j
        self.nodes = j['nodes']
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                self.parent[c] = i
        self.name = {n.get('name', str(i)): i for i, n in enumerate(self.nodes)}
        # topo order of all nodes reachable from scene roots
        roots = j['scenes'][j.get('scene', 0)]['nodes']
        self.order = []
        st = list(roots)
        while st:
            i = st.pop(0)
            self.order.append(i)
            st[:0] = self.nodes[i].get('children', [])

    def rest_local(self, i):
        n = self.nodes[i]
        return (np.array(n.get('translation', [0, 0, 0]), float),
                np.array(n.get('rotation', [0, 0, 0, 1]), float),
                np.array(n.get('scale', [1, 1, 1]), float))

    def sample(self, anim, fps=60.0):
        """-> times, {name: (pos[N,3], rot[N,4])} global."""
        a = self.g.anim(anim)
        T = max(max(v[0][-1] for v in d.values()) for d in a.values())
        ts = np.arange(0, T + 1e-6, 1.0 / fps)
        N = len(ts)
        loc = {}
        for i in self.order:
            t0, r0, s0 = self.rest_local(i)
            T_ = np.tile(t0, (N, 1)); R_ = np.tile(r0, (N, 1)); S_ = np.tile(s0, (N, 1))
            ch = a.get(i, {})
            if 'translation' in ch:
                tt, vv = ch['translation']
                T_ = np.stack([np.interp(ts, tt, vv[:, k]) for k in range(3)], -1)
            if 'rotation' in ch:
                tt, vv = ch['rotation']
                idx = np.clip(np.searchsorted(tt, ts) - 1, 0, len(tt) - 1)
                nx = np.clip(idx + 1, 0, len(tt) - 1)
                span = np.where(tt[nx] > tt[idx], tt[nx] - tt[idx], 1.0)
                f = np.clip((ts - tt[idx]) / span, 0, 1)[:, None]
                R_ = slerp(vv[idx], vv[nx], f)
                R_ /= np.linalg.norm(R_, axis=1, keepdims=True)
            if 'scale' in ch:
                tt, vv = ch['scale']
                S_ = np.stack([np.interp(ts, tt, vv[:, k]) for k in range(3)], -1)
            loc[i] = (T_, R_, S_)
        glob = {}
        for i in self.order:
            T_, R_, S_ = loc[i]
            p = self.parent.get(i)
            if p is None:
                glob[i] = (T_, R_, S_)
            else:
                pt, pr, ps = glob[p]
                glob[i] = (pt + qrot(pr, ps * T_), qmul(pr, R_), ps * S_)
        out = {self.nodes[i].get('name', str(i)): (glob[i][0], glob[i][1]) for i in self.order}
        return ts, out
