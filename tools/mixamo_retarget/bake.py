"""Bake the Mixamo walk / dive-roll clips into src/player/anim/mixamo_clips.rs.

    python -P tools/mixamo_retarget/bake.py <dir with Walking.fbx "Dive Roll.fbx"> \
        src/player/anim/mixamo_clips.rs

Frame layout: see tools/ual_retarget/bake.py (53 floats: pelvis, chest, head, arms, boots, in leg
lengths / world deltas from the Mixamo T-pose, mirrored onto our body frame).

- WALK / JOG: one in-place loop, rotated so frame 0 is the LEFT heel strike (the game keys footstep
  sfx / dust on the gait phase crossing 0 and 0.5), plus the speed the stance boot sweeps back at
  (leg lengths / s) — the player plays the loop at ground speed / that, so the boots never skate.
- ROLL: the dive-roll's body shape in the pelvis's own frame (the pelvis turn + travel removed): the
  game's root does the somersault, the clip supplies the folding limbs.

Needs numpy + ufbx (pip install ufbx). NB iterating ufbx scene lists twice crashes: see mx.py.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mx

src_dir, out_path = sys.argv[1], sys.argv[2]


def load(name):
    c = mx.Clip(os.path.join(src_dir, name + '.fbx'))
    b = mx.Baker(c)
    ts, P = c.sample()
    return b, b.frames(ts, P)


def qrot(q, v):
    u = q[..., :3]
    w = q[..., 3:4]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def stance_runs(y, thr):
    """Cyclic contiguous runs of frames below `thr`: [(start, length)]."""
    n = len(y)
    low = y < thr
    runs = []
    for i in range(n):
        if low[i] and not low[i - 1]:
            L = 0
            while low[(i + L) % n] and L < n:
                L += 1
            runs.append((i, L))
    return runs


def cycle(F):
    """Drop the duplicated end frame, rotate to the left heel strike; -> frames, native speed (legs/s)."""
    F = F[:-1]
    n = len(F)
    yl, yr = F[:, 34], F[:, 44]
    thr = min(yl.min(), yr.min()) + 0.035
    s0, ln = max(stance_runs(yl, thr), key=lambda r: r[1])
    F = np.roll(F, -s0, axis=0)
    sp = [stance_speed(F, c, thr) for c in (35, 45)]
    print(f'  cycle {n} frames, left stance {ln}, stance sweep speed L/R {sp[0]:.2f}/{sp[1]:.2f} legs/s')
    return F, float(np.mean(sp)), sp[0]


def stance_speed(F, col, thr):
    """Speed (legs/s) the planted boot (ankle z column `col`) sweeps back at."""
    n = len(F)
    s, L = max(stance_runs(F[:, col - 1], thr), key=lambda r: r[1])
    idx = (s + np.arange(L)) % n
    return float(-np.polyfit(np.arange(L) / mx.FPS, F[idx, col], 1)[0])


def mirror_rows(F):
    """Left <-> right: swap the limb slots and mirror across X (positions / directions x -> -x,
    rotations (x, y, z, w) -> (x, -y, -z, w))."""
    M = F.copy()
    q = np.array([1, -1, -1, 1.0])
    v = np.array([-1.0, 1.0, 1.0])
    M[:, 0:3] = F[:, 0:3] * v
    for s in (3, 7, 11):
        M[:, s:s + 4] = F[:, s:s + 4] * q
    for a, b in ((15, 27), (18, 30), (33, 43), (36, 46)):  # right <-> left (dirs / ankles / poles)
        M[:, a:a + 3] = F[:, b:b + 3] * v
        M[:, b:b + 3] = F[:, a:a + 3] * v
    M[:, 21:24] = F[:, 21:24] * v
    M[:, 24:27] = F[:, 24:27] * v
    M[:, 39:43] = F[:, 49:53] * q
    M[:, 49:53] = F[:, 39:43] * q
    return M


def symmetric(F):
    """A loop whose second step is the mirror of its first (the clip's two legs differ a little, which
    would show as skating on the weaker side): left strike .. right strike, then that mirrored."""
    h = len(F) // 2
    return np.concatenate([F[:h], mirror_rows(F[:h])])


def tame_run(F, lift=0.5, arms_in=0.45):
    """The raw Mixamo run lifts the feet very high and throws the arms wide: halve the swing foot's
    lift above the contact height and pull the arms' sideways spread toward the body."""
    F = F.copy()
    for col in (34, 44):
        c = F[:, col].min()
        F[:, col] = c + (F[:, col] - c) * lift
    for c in (15, 18, 27, 30):
        F[:, c] *= arms_in            # x (sideways) component
        n = np.linalg.norm(F[:, c:c + 3], axis=1, keepdims=True)
        F[:, c:c + 3] /= n
    return F


def air(F, lo, hi):
    """Frames lo..=hi with the clip's own pelvis rise taken off (pelvis + both ankles)."""
    F = F[lo:hi + 1].copy()
    rise = F[:, 1] - F[0, 1]
    for c in (1, 34, 44):
        F[:, c] -= rise
    return F


def body_frame(F, tp_pelvis_y):
    """Express every frame in its own pelvis frame (pelvis upright at the T-pose height)."""
    F = F.copy()
    out = np.zeros_like(F)
    for i, r in enumerate(F):
        qp = r[3:7]
        qi = mx.qinv(qp)
        pel = r[0:3]
        out[i, 0:3] = np.array([0.0, tp_pelvis_y, 0.0])
        out[i, 3:7] = [0, 0, 0, 1]
        for s in (7, 11, 39, 49):  # chest, head, boots: world delta -> delta in the pelvis frame
            out[i, s:s + 4] = mx.qmul(qi, r[s:s + 4])
        for s in (15, 18, 21, 24, 27, 30, 36, 46):  # directions
            out[i, s:s + 3] = qrot(qi, r[s:s + 3])
        for s in (33, 43):  # ankles, relative to the pelvis
            out[i, s:s + 3] = qrot(qi, r[s:s + 3] - pel) + np.array([0.0, tp_pelvis_y, 0.0])
    return out


def fmt(F):
    return '\n'.join('    [' + ', '.join(f'{v:.4f}' for v in row) + '],' for row in F)


lines = [
    "//! Generated by tools/mixamo_retarget/bake.py from Mixamo's Walking / Dive Roll",
    "//! (X Bot, in place, 30 fps; free for use in games under Adobe's Mixamo terms). Layout: see",
    "//! `swordplay::Frame`. Do not edit by hand.",
    '',
    '#![allow(clippy::excessive_precision)]',
    '',
    'pub(super) const FPS: f32 = 30.0;',
]

b, W = load('Walking')
lines.append('/// The Mixamo T-pose (the reference the clips are measured from).')
lines.append('pub(super) const TPOSE: [f32; 53] = [' + ', '.join(f'{v:.4f}' for v in b.tpose_frame()) + '];')
lines.append('')
print('Walking')
Wc, wsp, _ = cycle(W)
lines += [f'/// One walk loop ({len(Wc)} frames), frame 0 = left heel strike.',
          f'pub(super) const WALK_SPEED: f32 = {wsp:.4f}; // legs / s',
          f'pub(super) const WALK: [[f32; 53]; {len(Wc)}] = [', fmt(Wc), '];', '']
b, R = load('Slow Run')
print('Slow Run')
Rc, _, rsp = cycle(R)  # the left boot's speed: the loop is rebuilt symmetric from its left half
Rc = symmetric(Rc)
print('  ankle y max (legs)', Rc[:, 34].max().round(2), Rc[:, 44].max().round(2), ' hand spread max x', np.abs(Rc[:, [15, 27]]).max().round(2))
lines += [f'/// One jog loop ({len(Rc)} frames), frame 0 = left heel strike.',
          f'pub(super) const JOG_SPEED: f32 = {rsp:.4f}; // legs / s',
          f'pub(super) const JOG: [[f32; 53]; {len(Rc)}] = [', fmt(Rc), '];', '']
b, R2 = load('Running')
print('Running (tamed)')
Qc, _, qsp = cycle(R2)
Qc = tame_run(Qc)
Qc = symmetric(Qc)
lines += [f'/// One run loop ({len(Qc)} frames, tamed: feet lift ~half, arms drawn in), frame 0 = left heel strike.',
          f'pub(super) const RUN_SPEED: f32 = {qsp:.4f}; // legs / s',
          f'pub(super) const RUN: [[f32; 53]; {len(Qc)}] = [', fmt(Qc), '];', '']
b, D = load('Dive Roll')
DB = body_frame(D, b.tp_pelvis_y)[33:73]
lines += [f'/// The dive-roll\'s body shape ({len(DB)} frames: the dive, the tuck, the landing), in the pelvis frame.',
          f'pub(super) const ROLL: [[f32; 53]; {len(DB)}] = [', fmt(DB), '];', '']
open(out_path, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
print('wrote', out_path)
