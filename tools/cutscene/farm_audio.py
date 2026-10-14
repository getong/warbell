#!/usr/bin/env python3
"""Ch.2 cutscene ("Bless you for the protection") audio: the cue list + the offline soundtrack mix.

TEST-ONLY experiment: never integrated into the game (reachable only via FOREST_SCENE=farm).

    python tools/cutscene/farm_audio.py gen                 # write assets/cutscene/farm_morning.cues
    python tools/cutscene/farm_audio.py mix in.mp4 out.mp4  # mux a soundtrack onto a captured clip

The game plays the cue file live (`scenes.rs::drive_farm_audio`, skipping `video`-flagged lines — in
game the footsteps / ambience come from the audio systems). The `FOREST_CLIP` capture has no audio, so
`mix` builds the video's soundtrack from the SAME file (all lines, `video` ones included) with ffmpeg.

Cue line: `time  path-under-assets  volume  [video] [loop]`. Missing files are skipped, so lines that
are not recorded yet (the ElevenLabs prompts) simply stay silent until the .ogg lands. Only EXISTING
repo audio is used (plus the supplied music bed) — nothing is synthesised or re-pitched.

The timings below mirror `scenes.rs` (T_ARRIVE, T_LEAVE, the farmer/hauler schedules, shot cuts) —
keep them in step when the scene is re-cut.
"""
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
CUES = ASSETS / "cutscene" / "farm_morning.cues"
END = 29.5

# ── scene constants mirrored from scenes.rs ───────────────────────────────────────────
WAT_SPEED = 1.4
WAT_ARRIVE = 9.503 / WAT_SPEED         # (|WAT_TO - WAT_FROM| / SPEED) ≈ 6.8
HAUL_LEG1 = (8.0 + 2.6) / 1.2          # lane walk
HAUL_ARRIVE = HAUL_LEG1 + 2.2 / 1.2    # at the fence
HAUL_FIX_FROM = HAUL_ARRIVE + 2.6      # after setting the planks down
# kneeler hammering windows (farmer_clip): everything except the pick-up / crouch / talk beats
FARMER_FIX = [(0.0, 3.4), (5.9, 16.0), (21.2, 25.0), (27.4, END)]
# shots where each source is close to the lens (loud) — see farm_shot()
CLOSE_FARMER = [(9.2, 15.8), (18.4, 21.8)]
TRACK_WAT = [(3.8, 6.8)]
FINALE = (25.2, END)

VO = [
    (9.4, "audio/vo/npc/screaming.ogg", 1.0, 6.2),                 # Farmer: "Bless you for the protection…"
    (16.1, "audio/cutscene/wat_youre_welcome.ogg", 1.0, 1.6),       # Wat: "You're welcome."
    (18.8, "audio/cutscene/farmer_wasnt_thanking_you.ogg", 1.0, 1.8),  # Farmer: "Wasn't thanking you."
    (22.4, "audio/cutscene/wat_i_know.ogg", 1.0, 1.2),              # Wat: "I know."
]


def inside(t, spans):
    return any(a <= t < b for a, b in spans)


def gen():
    rnd = random.Random(2)
    rows = []  # (t, path, vol, flags)
    rows.append((0.0, "audio/cutscene/farm_dawn_music.ogg", 0.9, ""))
    for t, p, v, _ in VO:
        rows.append((t, p, v, ""))

    # Hammer taps (the clip's rhythm isn't known to the tool: loose, human timing).
    def taps(start, end, gap, base, windows, pan=0.0):
        t = start
        while t < end:
            if inside(t, windows):
                vol = base
                if inside(t, CLOSE_FARMER):
                    vol = base * 2.2
                elif t >= FINALE[0]:
                    vol = base * 1.4
                rows.append((round(t, 2), "audio/sfx/life/life_sfx_hammer.ogg", round(min(vol, 0.7), 2), f"pan={pan}"))
            t += gap * rnd.uniform(0.75, 1.3)

    taps(1.0, END, 2.0, 0.22, FARMER_FIX, pan=0.0)
    taps(HAUL_FIX_FROM, END, 2.7, 0.14, [(HAUL_FIX_FROM, END)], pan=-0.45)

    # Footsteps (video only — the game's own systems step the hero and villagers).
    steps = [f"audio/footstep-dirt-{i}.ogg" for i in (1, 2, 3)]
    t = 0.3
    while t < END:
        walking = t < WAT_ARRIVE
        if walking:
            vol = 0.5 if inside(t, TRACK_WAT) else 0.16
            rows.append((round(t, 2), rnd.choice(steps), round(vol * rnd.uniform(0.85, 1.1), 2), "video"))
        t += 0.53
    t = 0.6
    while t < HAUL_ARRIVE:
        vol = 0.3 if inside(t, TRACK_WAT) else 0.11
        rows.append((round(t, 2), rnd.choice(steps), round(vol * rnd.uniform(0.8, 1.1), 2), "video"))
        t += 0.8

    # Air: meadow bed + wind under everything, a couple of distant dog barks, a rake in the ash.
    rows.append((0.0, "audio/meadow-ambient.ogg", 0.42, "video loop"))
    rows.append((0.0, "audio/wind.ogg", 0.12, "video loop"))
    rows.append((0.0, "audio/forest-ambient.ogg", 0.22, "video loop"))
    rows.append((6.4, "audio/dog-2.ogg", 0.14, "video"))
    rows.append((24.2, "audio/dog-4.ogg", 0.10, "video"))
    t = 3.0
    while t < END - 2:
        rows.append((round(t, 2), "audio/forage.ogg", 0.10, "video"))
        t += rnd.uniform(5.0, 8.0)

    # Far-off things (all existing repo SFX — nothing is generated): a bell across the fields, goats up the hill, kids in the village, embers crackling.
    rows.append((1.2, "audio/war-bell.ogg", 0.05, "pan=0.5"))
    rows.append((27.6, "audio/war-bell.ogg", 0.04, "pan=0.5"))
    rows.append((7.0, "audio/goat-1.ogg", 0.10, "video pan=-0.6"))
    rows.append((26.0, "audio/goat-2.ogg", 0.09, "video pan=0.6"))
    rows.append((0.0, "audio/campfire-loop.ogg", 0.05, "video loop"))
    rows.append((0.0, "audio/kids-play.ogg", 0.03, "video loop"))
    # Wood: a plank dropped on the pile, the creak as the farmer reaches for another (twice).
    rows.append((round(HAUL_ARRIVE + 1.1, 2), "audio/chop-wood-1.ogg", 0.26, "pan=-0.3"))
    for t in (4.4, 25.6):
        rows.append((t, "audio/wood-crack.ogg", 0.14, "pan=0.0"))

    rows.sort(key=lambda r: r[0])
    out = [
        "# Ch.2 'Bless you for the protection' audio cues — GENERATED by tools/cutscene/farm_audio.py gen.",
        "# TEST-ONLY experiment — never integrated into the game (FOREST_SCENE=farm only).",
        "# time  path(under assets/)  volume  [video] [loop]      (video = only for the offline video mix)",
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
        rows.append((float(f[0]), f[1], float(f[2]), set(f[3:])))
    return rows


def mix(video, out):
    rows = [r for r in read_cues() if (ASSETS / r[1]).exists()]
    missing = {r[1] for r in read_cues() if not (ASSETS / r[1]).exists()}
    for m in sorted(missing):
        print("skip (missing):", m)
    inputs, filters, labels = [], [], []
    vo_spans = [(t, t + d) for t, p, _, d in VO if (ASSETS / p).exists()]
    for i, (t, path, vol, flags) in enumerate(rows):
        if "loop" in flags:
            inputs += ["-stream_loop", "-1"]
        inputs += ["-i", str(ASSETS / path)]
        f = f"[{i + 1}:a]"
        if "loop" in flags:
            f += f"atrim=0:{END},"
        pan = next((float(x[4:]) for x in flags if x.startswith("pan=")), None)
        if pan is None:
            f += "aformat=sample_rates=48000:channel_layouts=stereo"
        else:  # a point source: fold to mono, then equal-power pan
            import math
            a = (pan + 1) * math.pi / 4
            f += f"aformat=sample_rates=48000:channel_layouts=mono,pan=stereo|c0={math.cos(a):.3f}*c0|c1={math.sin(a):.3f}*c0"
        gain = f"volume={vol}"
        if path.endswith("farm_dawn_music.ogg"):
            # duck the music a few dB under each spoken line (soft edges)
            for a, b in vo_spans:
                gain += f",volume=enable='between(t,{a - 0.3:.2f},{b + 0.5:.2f})':volume=0.62"
        delay = int(t * 1000)
        filters.append(f"{f},{gain},adelay={delay}|{delay}[a{i}]")
        labels.append(f"[a{i}]")
    chain = ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
    chain += f"alimiter=limit=0.95,atrim=0:{END},afade=t=out:st={END - 1.2}:d=1.2[mix]"
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
