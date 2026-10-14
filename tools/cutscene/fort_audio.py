#!/usr/bin/env python3
"""P.3 "The bell in the tower" (FortArrival) audio: the cue list + the offline soundtrack mix.

VIDEO rig only: the scene exists to be filmed (FOREST_SCENE=fort + FOREST_CLIP), never triggered in game.

    python tools/cutscene/fort_audio.py gen                 # write assets/cutscene/fort_arrival.cues
    python tools/cutscene/fort_audio.py mix in.mp4 out.mp4  # mux the soundtrack onto a captured clip

Cue line: `time  path-under-assets  volume  [video] [loop] [pan=x] [fadein=s] [fadeout=t,s] [trim=a,b]`.
Only repo audio is used (recorded Act I VO, the supplied music, repo SFX + the softened cutscene
cuts of it in audio/sfx/cutscene/, and the owner-supplied crow flush). Timings mirror
`scenes.rs` (fort_pip / fort_maud routes, FORT_LINES, the shot list) — keep them in step.
"""
import math
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
CUES = ASSETS / "cutscene" / "fort_arrival.cues"
END = 41.95
BLACK = 36.35  # fade-to-black done; the act card sits on wind alone

# Recorded Act I lines (docs/audio/elevenlabs-akt-1.md) at their scene times — FORT_LINES in scenes.rs.
# (scene time, clip, volume, (from, to) seconds of the clip). Pip's a1_pip_05 is ONE take of all his
# lines (ElevenLabs v3, Omar J): "[excited, out of breath] There's a well! [amazed, a little
# breathless] And that... [sad breath] that was a chapel! [gasps, excited] There's a bell! Up there!
# [softly, in awe] It's whole. [eager, hopeful] Can I—". Split at its pauses (ffmpeg silencedetect
# -38 dB: well 0.1–1.36 | and that 1.89–2.90, breath, that was a chapel 3.96–5.24 | gasp 5.72, there's
# a bell 6.26–7.02, up there 7.35–8.00 | it's whole 8.82–9.78 | can I 11.13–11.61) so each discovery
# gets its phrase and every cut lands in a pause.
PIP05 = "audio/vo/campaign/a1_pip_05.ogg"
VO = [
    (11.45, PIP05, 1.0, (0.0, 1.1)),     # Pip: "There's a well!"
    (13.5, PIP05, 1.0, (1.8, 5.3)),      # Pip: "And that... that was a chapel!"
    (17.15, PIP05, 1.0, (5.65, 8.1)),    # Pip: (gasp) "There's a bell! Up there!"
    (19.72, PIP05, 1.0, (8.7, 9.88)),    # Pip: "It's whole."
    (21.25, "audio/vo/campaign/a1_maud_14.ogg", 1.0, (0.0, 2.62)),  # Maud: "The well's whole too. Start with the well."
    (24.5, PIP05, 1.0, (11.05, 11.75)),  # Pip: "Can I—"
    (25.3, "audio/vo/campaign/a1_maud_15.ogg", 1.0, (0.0, 2.54)),  # Maud: "At dusk. King's orders, one of them."
    (28.65, "audio/vo/campaign/a1_maud_16.ogg", 1.0, (0.0, 4.91)), # Maud: "God help us. A well, a bell, and a wall and a half."
]
# Pip's run segments (scenes.rs fort_pip): (start, end, speed)
PIP_RUNS = [(0.3, 10.9, 3.6), (12.1, 13.6, 2.6), (28.95, 35.05, 1.0)]
# Which shot is on, for distance-based loudness (scenes.rs fort_shot)
SHOTS = [(0.0, 7.0, "outside"), (7.0, 11.1, "yard"), (11.1, 13.45, "well"), (13.45, 17.05, "chapel"),
         (17.05, 19.6, "bell"), (19.6, 21.1, "insert"), (21.1, 24.35, "maud"), (24.35, 25.3, "ots"),
         (25.3, 28.15, "pip"), (28.15, END, "crane")]


def clip_len(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(ASSETS / path)], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def shot(t):
    return next((n for a, b, n in SHOTS if a <= t < b), "crane")


def gen():
    rnd = random.Random(3)
    rows = []  # (t, path, vol, flags)
    # Music: steals in under the run through the gate (a long fade, no step up), sits well under the
    # voices (ducked smoothly in `mix`), swells a little with the crane, gone on the black.
    rows.append((6.5, "audio/cutscene/quiet_council.ogg", 0.3, f"video fadein=7.0 fadeout={BLACK - 1.6:.1f},1.6"))
    for t, p, v, (a, b) in VO:
        rows.append((t, p, v, f"trim={a},{b}" if a > 0 or b < clip_len(p) - 0.05 else ""))

    # Air: wind over the ruin the whole way (alone on the black), meadow + distant birds under it.
    rows.append((0.0, "audio/wind.ogg", 0.34, "video loop"))
    rows.append((0.0, "audio/meadow-ambient.ogg", 0.30, f"video loop fadeout={BLACK - 1.4:.1f},1.4"))
    rows.append((0.0, "audio/forest-ambient.ogg", 0.16, f"video loop fadeout={BLACK - 1.4:.1f},1.4"))
    rows.append((0.0, "audio/castle-ambient.ogg", 0.10, f"video loop fadeout={BLACK - 1.4:.1f},1.4"))

    # Footsteps: soft cuts of the dirt step (sfx/cutscene/cs_step_*: compressed, high-passed, the
    # boy's pitched up) — the raw game steps peak at 0 dBFS and read as a marching ork. Pip's light
    # run (nearer the lens, a little louder), Maud's walk, the knight.
    steps = [f"audio/sfx/cutscene/cs_step_child_{i}.ogg" for i in (1, 2, 3)]
    adult = [f"audio/sfx/cutscene/cs_step_adult_{i}.ogg" for i in (1, 2, 3)]
    for a, b, v in PIP_RUNS:
        gap = 0.26 if v > 3 else (0.32 if v > 2 else 0.55)
        t = a + 0.05
        while t < b:
            s = shot(t)
            # the yard shot: he runs from the gate straight at the lens — steps swell as he comes
            vol = {"outside": 0.3 if t < 3.0 else 0.14, "yard": 0.08 + 0.3 * min(max((t - 7.0) / 3.9, 0), 1),
                   "well": 0.3, "chapel": 0.28, "crane": 0.16 - 0.1 * min((t - 28.95) / 6.0, 1)}.get(s, 0.18)
            rows.append((round(t, 2), rnd.choice(steps), round(vol * rnd.uniform(0.8, 1.1), 2), "video"))
            t += gap * rnd.uniform(0.9, 1.1)
    t = 0.2
    while t < 18.8:  # Maud walks in to her mark
        vol = {"outside": 0.22, "bell": 0.16, "insert": 0.05}.get(shot(t), 0.09)
        rows.append((round(t, 2), rnd.choice(adult), round(vol * rnd.uniform(0.8, 1.05), 2), "video"))
        t += 0.62
    t = 0.1
    while t < 6.2:  # the knight, heavier
        rows.append((round(t, 2), rnd.choice(adult), round(0.2 * rnd.uniform(0.85, 1.1), 2), "video"))
        t += 0.55

    # The flock flushed by the boy at the gate: wings + caws (two takes, spread), a scuff of grass.
    rows.append((6.95, "audio/sfx/cutscene/cs_crows_flush_1.ogg", 0.8, "video"))
    rows.append((7.2, "audio/sfx/cutscene/cs_crows_flush_2.ogg", 0.5, "video pan=0.35"))
    rows.append((7.0, "audio/forage.ogg", 0.16, "video pan=-0.1"))
    # "It's whole." — the bronze just singing in the wind as the lens pushes in on it.
    rows.append((19.55, "audio/sfx/cutscene/cs_bell_hum.ogg", 0.5, "video"))

    rows.sort(key=lambda r: r[0])
    out = [
        "# P.3 'The bell in the tower' (FortArrival) audio cues — GENERATED by tools/cutscene/fort_audio.py gen.",
        "# VIDEO rig only — never triggered in game (FOREST_SCENE=fort). `#` lines are skipped by scenes.rs::parse_cues.",
        "# time  path(under assets/)  volume  [video] [loop] [pan=] [fadein=] [fadeout=t,s]   (video = offline mix only)",
    ]
    out += [f"{t:6.2f}  {p}  {v}  {f}".rstrip() for t, p, v, f in rows]
    CUES.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {CUES} ({len(rows)} cues)")


def read_cues():
    rows = []
    for line in CUES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        rows.append((float(f[0]), f[1], float(f[2]), f[3:]))
    return rows


def flag(flags, name):
    return next((x[len(name) + 1:] for x in flags if x.startswith(name + "=")), None)


def mix(video, out):
    rows = [r for r in read_cues() if (ASSETS / r[1]).exists()]
    for m in sorted({r[1] for r in read_cues() if not (ASSETS / r[1]).exists()}):
        print("skip (missing):", m)
    inputs, filters, labels = [], [], []
    vo_spans = [(t, t + b - a) for t, p, _, (a, b) in VO if (ASSETS / p).exists()]
    for i, (t, path, vol, flags) in enumerate(rows):
        loop = "loop" in flags
        if loop:
            inputs += ["-stream_loop", "-1"]
        inputs += ["-i", str(ASSETS / path)]
        f = f"[{i + 1}:a]"
        if loop:
            f += f"atrim=0:{END},"
        trim = flag(flags, "trim")
        if trim:  # one phrase of a longer take, 15 ms edge fades so the cut never clicks
            a, b = (float(x) for x in trim.split(","))
            f += f"atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:st={b - a - 0.015:.3f}:d=0.015,"
        pan = flag(flags, "pan")
        if pan is None:
            f += "aformat=sample_rates=48000:channel_layouts=stereo"
        else:  # a point source: fold to mono, then equal-power pan
            a = (float(pan) + 1) * math.pi / 4
            f += f"aformat=sample_rates=48000:channel_layouts=mono,pan=stereo|c0={math.cos(a):.3f}*c0|c1={math.sin(a):.3f}*c0"
        gain = f"volume={vol}"
        fi = flag(flags, "fadein")
        if fi:
            gain += f",afade=t=in:st=0:d={fi}"
        fo = flag(flags, "fadeout")
        if fo:  # absolute scene time → the clip's own timeline
            st, d = (float(x) for x in fo.split(","))
            gain += f",afade=t=out:st={max(st - t, 0):.2f}:d={d}"
        if path.endswith("quiet_council.ogg"):
            # duck the music under the spoken lines on ONE smooth envelope (clip-relative times):
            # 0.5 s down, 1.2 s back up, and gaps between lines shorter than the ramps never pop up
            env = "0"
            for a, b in vo_spans:
                g = f"clip((t-{a - 0.5 - t:.2f})/0.5,0,1)*clip(({b + 1.2 - t:.2f}-t)/1.2,0,1)"
                env = f"max({env},{g})"
            gain += f",volume='1-0.45*{env}':eval=frame"
        delay = int(t * 1000)
        filters.append(f"{f},{gain},adelay={delay}|{delay}[a{i}]")
        labels.append(f"[a{i}]")
    chain = ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
    chain += f"alimiter=limit=0.95,atrim=0:{END},afade=t=out:st={END - 1.0}:d=1.0[mix]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video] + inputs + [
        "-filter_complex", chain, "-map", "0:v", "-map", "[mix]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out,
    ]
    subprocess.run(cmd, check=True)
    print("wrote", out)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "gen":
        gen()
    elif len(sys.argv) == 4 and sys.argv[1] == "mix":
        mix(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
