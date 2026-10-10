#!/usr/bin/env python3
"""Build the caged captives' MUFFLED voice clips (`assets/audio/vo/npc/captive/*.ogg`).

There is no TTS in this pipeline and nothing is downloaded: every clip is cut from the game's own
recorded villager lines (`assets/audio/vo/npc/*.ogg`, transcripts in `src/audio/lines.rs`) and
re-processed with ffmpeg so it reads as a prisoner heard through the bars from a few strides off:

  cut  ->  (pitch / tempo / vibrato per variant)  ->  splice with gaps  ->  band-limit
       ->  low-pass (two 2-pole stages at `cutoff`)  ->  a short damp echo  ->  quiet level

* **Words** are only ever cut at real word boundaries. The boundaries below were found by forced
  alignment of the KNOWN transcript (Windows' built-in `System.Speech` recogniser with a one-sentence
  grammar) and then nudged onto the energy dips / stop closures of a 10 ms frame analysis, so every
  word in a subtitle is a word that is actually audible in the clip (e.g. "help" is the last word of
  `taxes.ogg`, "That'll help.", cut after the `'ll`).
* **Non-verbal sounds** (sobbing, a cough, a groan, a whimper) are built from vocal material
  that is not a word: the falling "Oh," of `greet.ogg`, the long falling "Ooh," of `pa_shiny.ogg`,
  the audible inhales of `siege_fear.ogg` / `screaming.ogg`, and consonant noise (the /s/ of
  "house", the /k/ burst of "came"). Their subtitles name the sound (`*muffled sobbing*`), never
  invented words.
* **Level**: every clip is normalised to a fixed overall RMS (`rms_db`) about 10-13 dB under the
  median NPC line (~-19 dBFS), so a captive is noticeably quieter than a townsperson at the same
  distance; the spatial attenuation does the rest (louder as the hero walks up).
* **Clarity**: the ambient murmurs are low-passed hardest (~1.3 kHz); the close-range pleas, which
  only play when the hero is right at the cage, are a little clearer (~2.2 kHz).

Usage (from the repo root):

    python tools/make_captive_vo.py            # (re)build every clip, then print the report
    python tools/make_captive_vo.py --report   # only analyse what is on disk

The report lists duration, overall RMS, peak and the energy above 2.5 kHz relative to the whole
clip, next to the same numbers for the source NPC lines — the objective check that the clips are
quieter and low-passed (they cannot be listen-tested in CI).

Keep `RECIPES` in sync with the `Speaker::Captive` lines in `src/audio/lines.rs` (same ids, same
subtitle text).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import statistics
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "audio" / "vo" / "npc"
OUT = SRC / "captive"
RATE = 44100
# Final encode: mono Vorbis. The clips are low-passed to <= ~2.2 kHz, so 22.05 kHz loses nothing.
OUT_RATE = 22050
OUT_BITRATE = "48k"

# ── Building blocks ─────────────────────────────────────────────────────────────────────────


def cut(src: str, t0: float, t1: float, *, pitch: float = 1.0, tempo: float = 1.0, speed: float = 1.0,
        vibrato: tuple[float, float] | None = None, tremolo: tuple[float, float] | None = None,
        gain: float = 0.0, fade_in: float = 0.012, fade_out: float = 0.04, reverse: bool = False) -> dict:
    """One fragment of a source clip (`src` = stem under `assets/audio/vo/npc`, times in seconds).

    `pitch`/`tempo` go through rubberband (independent); `speed` resamples (pitch AND tempo, like
    a tape); `vibrato`/`tremolo` = (Hz, depth); `gain` in dB; fades are in seconds."""
    return dict(kind="cut", src=src, t0=t0, t1=t1, pitch=pitch, tempo=tempo, speed=speed, vibrato=vibrato,
                tremolo=tremolo, gain=gain, fade_in=fade_in, fade_out=fade_out, reverse=reverse)


def gap(secs: float) -> dict:
    """Silence between fragments."""
    return dict(kind="gap", secs=secs)


def mix(*parts: dict) -> dict:
    """Layer fragments on top of each other (all start together), e.g. a noise burst over a grunt."""
    return dict(kind="mix", parts=parts)


# Muffle profiles: (low-pass cutoff Hz, overall RMS target dBFS).
MURMUR = (1300.0, -32.0)  # ambient: sobs, coughs, whispered despair — heard from a distance
COUGH = (950.0, -32.0)  # the cough's noise bursts are all highs — damp them harder than a voice
FEAR = (1500.0, -31.0)  # a frightened word / whimper when an ork looms or blades ring nearby
PLEA = (2200.0, -29.0)  # close range, hero right at the bars: a touch clearer and louder

# ── The clips ───────────────────────────────────────────────────────────────────────────────
# id -> (subtitle text == `lines.rs`, profile, sequence). Source timings are documented per piece.

# A stuttering, hitching inhale (the sob "catch"): the long audible inhale between "coming." and
# "Inside," in siege_fear.ogg (1.06-1.47 s), chopped into short gasps.
def catch(n: int, start: float = 1.10, piece: float = 0.075, step: float = 0.11, gaps: float = 0.045,
          pitch: float = 1.08, gain: float = 6.0) -> list[dict]:
    seq: list[dict] = []
    for i in range(n):
        t = start + i * step
        seq.append(cut("siege_fear", t, t + piece, pitch=pitch + 0.03 * i, gain=gain, fade_in=0.008, fade_out=0.02))
        if i + 1 < n:
            seq.append(gap(gaps))
    return seq


RECIPES: dict[str, tuple[str, tuple[float, float], list[dict]]] = {
    # ── Ambient sounds (Concept::CaptiveSob): the far-off, wordless layer ──
    # Hitching inhales + the falling "Oh," of greet.ogg (0.14-0.44 s, f0 296 -> 100 Hz) raised and
    # wavered (vibrato + tremolo = a breaking, crying voice), then a long falling "Ooh" from
    # pa_shiny.ogg (0.55-0.98 s) and a reversed inhale as the shaky exhale.
    "captive_sob_a": ("*muffled sobbing*", MURMUR, [
        *catch(3),
        gap(0.03),
        cut("greet", 0.135, 0.42, pitch=1.14, vibrato=(7.0, 0.35), tremolo=(9.0, 0.45), fade_out=0.08),
        gap(0.16),
        cut("greet", 0.15, 0.36, pitch=1.24, vibrato=(8.0, 0.4), tremolo=(10.0, 0.5), gain=-2.0, fade_out=0.06),
        gap(0.12),
        *catch(2, start=1.16, pitch=1.12),
        gap(0.04),
        cut("pa_shiny", 0.55, 0.98, pitch=1.06, tempo=0.9, vibrato=(6.5, 0.3), tremolo=(8.0, 0.4), fade_out=0.15),
        gap(0.25),
        cut("siege_fear", 1.08, 1.40, pitch=0.95, reverse=True, gain=3.0, fade_in=0.05, fade_out=0.12),
    ]),
    # Quieter weeping: softer, lower, fewer catches; the inhale of screaming.ogg (2.62-2.96 s).
    "captive_sob_b": ("*quiet weeping*", MURMUR, [
        cut("screaming", 2.62, 2.96, pitch=1.05, gain=8.0, fade_in=0.08, fade_out=0.05),
        gap(0.05),
        cut("pa_shiny", 0.62, 1.05, pitch=1.0, tempo=0.85, vibrato=(5.5, 0.28), tremolo=(7.0, 0.35), gain=-3.0, fade_in=0.04, fade_out=0.18),
        gap(0.35),
        *catch(2, start=1.14, pitch=1.04, gain=4.0),
        gap(0.05),
        cut("greet", 0.16, 0.44, pitch=1.02, tempo=0.85, vibrato=(6.0, 0.3), tremolo=(8.0, 0.4), gain=-4.0, fade_out=0.12),
        gap(0.3),
        cut("screaming", 2.66, 2.94, pitch=0.9, reverse=True, gain=7.0, fade_in=0.04, fade_out=0.1),
    ]),
    # Three dry coughs, the last one weaker: each is the /s/ of "house," (need_house_a.ogg 6.505-
    # 6.655 s) dropped ~an octave into a dark breathy burst, layered over the /k/ release + vowel
    # onset of "came" (rescued.ogg 0.625-0.75 s) dropped a fifth for the voiced bark of the cough.
    "captive_cough": ("*coughing*", COUGH, [
        mix(cut("need_house_a", 6.505, 6.655, speed=0.55, gain=4.0, fade_in=0.004, fade_out=0.12),
            cut("rescued", 0.625, 0.75, speed=0.68, gain=-4.0, fade_in=0.003, fade_out=0.08)),
        gap(0.17),
        mix(cut("need_house_a", 6.52, 6.65, speed=0.6, gain=3.0, fade_in=0.004, fade_out=0.1),
            cut("rescued", 0.625, 0.74, speed=0.72, gain=-5.0, fade_in=0.003, fade_out=0.07)),
        gap(0.26),
        mix(cut("need_house_a", 6.53, 6.64, speed=0.62, gain=-1.0, fade_in=0.005, fade_out=0.09),
            cut("rescued", 0.63, 0.73, speed=0.75, gain=-8.0, fade_in=0.004, fade_out=0.06)),
        gap(0.2),
        cut("siege_fear", 1.12, 1.38, pitch=0.85, gain=2.0, fade_in=0.05, fade_out=0.1),
    ]),
    # A low moan: the 0.86 s falling "Ooh" of pa_shiny.ogg (0.33-1.19 s) taken down ~4 semitones and
    # slowed, after a slow inhale (siege_fear.ogg 1.08-1.46 s, lowered).
    "captive_groan": ("*a low groan*", MURMUR, [
        cut("siege_fear", 1.08, 1.46, pitch=0.82, tempo=0.85, gain=2.0, fade_in=0.08, fade_out=0.08),
        gap(0.06),
        cut("pa_shiny", 0.33, 1.19, pitch=0.78, tempo=0.8, vibrato=(3.5, 0.12), fade_in=0.1, fade_out=0.35),
    ]),
    # ── Ambient murmurs (Concept::CaptiveMurmur): a few words, once the hero is within ~13 u ──
    # born_a.ogg "...Gods help the little one." -> "Gods" (3.93-4.385 s: /g/ burst, vowel, /dz/)
    # and "help" (4.385-4.625 s, cut in the /p/ closure before "the"), pulled apart into a prayer.
    "captive_gods_help": ("Gods… help…", MURMUR, [
        cut("born_a", 3.93, 4.385, tempo=0.92, fade_out=0.03),
        gap(0.34),
        cut("born_a", 4.385, 4.625, tempo=0.88, fade_in=0.02, fade_out=0.06),
    ]),
    # trailer_cage.ogg "Three weeks I was in there..." -> "Three weeks" (0.0-0.725 s, ends on the /s/
    # just before "I").
    "captive_three_weeks": ("Three weeks…", MURMUR, [
        cut("trailer_cage", 0.0, 0.725, tempo=0.9, pitch=0.97, fade_out=0.03),
    ]),
    # pop_lost.ogg "Buried another last night. Fewer of us..." -> the first sentence (0.0-1.64 s).
    "captive_buried": ("Buried another last night…", MURMUR, [
        cut("pop_lost", 0.0, 1.64, tempo=0.94, pitch=0.97, fade_out=0.08),
    ]),
    # ── Fear (Concept::CaptiveFear): an ork right at the bars, or a fight close by ──
    # siege_fear.ogg "They're coming. Inside, inside..." -> the gasp + "They're coming." (0.38-1.07 s).
    "captive_coming": ("They're coming…", FEAR, [
        cut("siege_fear", 0.38, 1.07, tempo=0.95, fade_in=0.02, fade_out=0.05),
    ]),
    # vill_behind.ogg — the whole (already hushed) line, "He's right behind me, isn't he?" (0.10-2.64 s).
    "captive_behind": ("He's right behind me, isn't he?", FEAR, [
        cut("vill_behind", 0.10, 2.64, fade_out=0.08),
    ]),
    # A sharp gasp (siege_fear.ogg 0.39-0.53 s, the inhale before "They're") into a high, shaking
    # "oh" (greet.ogg 0.14-0.40 s raised ~4 semitones).
    "captive_whimper": ("*a frightened whimper*", FEAR, [
        cut("siege_fear", 0.39, 0.53, pitch=1.15, gain=6.0, fade_in=0.01, fade_out=0.02),
        gap(0.03),
        cut("greet", 0.14, 0.40, pitch=1.28, vibrato=(9.0, 0.45), tremolo=(11.0, 0.5), fade_out=0.08),
        gap(0.12),
        cut("greet", 0.16, 0.34, pitch=1.36, vibrato=(10.0, 0.5), tremolo=(12.0, 0.5), gain=-4.0, fade_out=0.07),
    ]),
    # ── Pleas (Concept::CaptivePlea): hero at the bars, no jailer near ──
    # need_house_a.ogg "Eight of us to one cot, m'lord. ... Build a house, I beg you." ->
    # "m'lord." (1.715-2.45 s) + "I beg you." (6.79-7.86 s) — the same speaker, one take.
    "captive_beg": ("M'lord… I beg you.", PLEA, [
        cut("need_house_a", 1.715, 2.45, tempo=0.93, fade_in=0.02, fade_out=0.06),
        gap(0.38),
        cut("need_house_a", 6.79, 7.86, tempo=0.93, fade_in=0.01, fade_out=0.08),
    ]),
    # rescued.ogg "You came for me? Gods bless you..." -> "You came for me?" (0.345-1.52 s) and the
    # breath after it (to 1.98 s, before "Gods").
    "captive_came": ("You came for me?", PLEA, [
        cut("rescued", 0.345, 1.98, fade_out=0.12),
    ]),
    # taxes.ogg "...But sure, ring the bell. That'll help." -> "help" (7.655-8.30 s, after the 'll),
    # twice: the second take a touch higher and slower, as a weaker repeat.
    "captive_help": ("Help… help.", PLEA, [
        cut("taxes", 7.655, 8.30, fade_in=0.015, fade_out=0.06),
        gap(0.42),
        cut("taxes", 7.655, 8.30, pitch=1.05, tempo=0.9, gain=-3.0, fade_in=0.015, fade_out=0.08),
    ]),
}

# ── ffmpeg plumbing ─────────────────────────────────────────────────────────────────────────


def ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", *args], capture_output=True, text=True, check=True)


def piece_chain(p: dict, label: str) -> str:
    """Filter chain turning one input stream into a processed fragment `[label]`."""
    f = [f"atrim=start={p['t0']}:end={p['t1']}", "asetpts=PTS-STARTPTS",
         f"aformat=sample_fmts=fltp:sample_rates={RATE}:channel_layouts=mono"]
    # Modulation FIRST, on the plain trimmed frames: ffmpeg 7.1's `vibrato` intermittently emitted
    # a NaN sample when fed the re-chunked output of atempo/rubberband (one NaN then poisons every
    # IIR filter downstream into a full-scale DC wall).
    if p["vibrato"]:
        f.append(f"vibrato=f={p['vibrato'][0]}:d={p['vibrato'][1]}")
    if p["tremolo"]:
        f.append(f"tremolo=f={p['tremolo'][0]}:d={p['tremolo'][1]}")
    if p["reverse"]:
        f.append("areverse")
    if p["speed"] != 1.0:
        f += [f"asetrate={RATE * p['speed']:.0f}", f"aresample={RATE}"]
    if p["pitch"] != 1.0 or p["tempo"] != 1.0:
        f.append(f"rubberband=pitch={p['pitch']}:tempo={p['tempo']}:formant=preserved")
    if p["gain"]:
        f.append(f"volume={p['gain']}dB")
    # Fade in, then fade out via a reverse sandwich (no need to know the processed length), and a
    # belt-and-braces scrub of any non-finite sample.
    f += [f"afade=t=in:st=0:d={p['fade_in']}:curve=qsin", "areverse",
          f"afade=t=in:st=0:d={p['fade_out']}:curve=qsin", "areverse",
          "aeval=exprs='if(isnan(val(0))+isinf(val(0)),0,val(0))':channel_layout=mono"]
    return ",".join(f) + f"[{label}]"


def render(seq: list[dict], cutoff: float, wav: pathlib.Path) -> None:
    """Splice `seq`, muffle it, and write an un-normalised float WAV."""
    inputs: list[str] = []
    chains: list[str] = []
    order: list[str] = []

    def add_cut(p: dict) -> str:
        idx = len(inputs) // 2
        inputs.extend(["-i", str(SRC / f"{p['src']}.ogg")])
        label = f"c{idx}"
        chains.append(f"[{idx}:a]" + piece_chain(p, label))
        return label

    for k, item in enumerate(seq):
        if item["kind"] == "cut":
            order.append(add_cut(item))
        elif item["kind"] == "gap":
            label = f"g{k}"
            chains.append(f"anullsrc=r={RATE}:cl=mono,atrim=duration={item['secs']}[{label}]")
            order.append(label)
        else:  # mix
            labels = [add_cut(p) for p in item["parts"]]
            label = f"m{k}"
            chains.append("".join(f"[{l}]" for l in labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest[{label}]")
            order.append(label)
    chains.append("".join(f"[{l}]" for l in order) + f"concat=n={len(order)}:v=0:a=1[out]")
    spliced = wav.with_name(wav.stem + "_dry.wav")
    ffmpeg([*inputs, "-filter_complex", ";".join(chains), "-map", "[out]", "-ac", "1", "-ar", str(RATE),
            "-c:a", "pcm_f32le", str(spliced)])
    # Muffle, as a SEPARATE pass over the spliced WAV: trim the rumble, two 2-pole low-pass stages
    # (~24 dB/oct past `cutoff`), a short damp echo (two early reflections, like the slatted cage +
    # the ground) with a tail for it. (Run inside the splicing graph, ffmpeg 7.1's biquads
    # intermittently blew up to +200 dBFS on concat's ragged frames; over a plain file they're stable.)
    ffmpeg(["-i", str(spliced), "-af", f"highpass=f=110,lowpass=f={cutoff},lowpass=f={cutoff},apad=pad_dur=0.25,"
            "aecho=0.85:0.6:37|79:0.22|0.1", "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_f32le", str(wav)])
    st = stats(wav)
    if not (-60.0 < st["rms"] < -3.0 and st["peak"] <= 0.0):
        raise RuntimeError(f"{wav.name}: implausible render (rms {st['rms']:.1f}, peak {st['peak']:.1f} dBFS)")


def stats(path: pathlib.Path, pre: str = "") -> dict[str, float]:
    """Overall RMS / peak (dBFS) and duration of `path`, optionally after a filter `pre`."""
    af = (pre + "," if pre else "") + "astats=measure_perchannel=none:measure_overall=RMS_level+Peak_level"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    def grab(key: str) -> float:
        m = re.findall(rf"{key}: (-?[\d.]+|-inf)", r.stderr)
        return float(m[-1]) if m and m[-1] != "-inf" else -120.0
    dur = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    h, mi, s = dur[-1] if dur else ("0", "0", "0")
    return {"rms": grab("RMS level dB"), "peak": grab("Peak level dB"), "dur": int(h) * 3600 + int(mi) * 60 + float(s)}


def hi_band_db(path: pathlib.Path) -> float:
    """Energy above 2.5 kHz relative to the whole clip (dB; more negative = more muffled)."""
    full = stats(path)["rms"]
    hi = stats(path, "highpass=f=2500,highpass=f=2500")["rms"]
    return hi - full


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for cid, (text, (cutoff, rms_db), seq) in RECIPES.items():
            wav = pathlib.Path(tmp) / f"{cid}.wav"
            render(seq, cutoff, wav)
            st = stats(wav)
            gain = rms_db - st["rms"]
            # Never let the peak pass -3 dBFS after the gain (the limiter only guards outliers).
            ogg = OUT / f"{cid}.ogg"
            ffmpeg(["-i", str(wav), "-af", f"volume={gain:.2f}dB,alimiter=limit=0.7:level=false",
                    "-ac", "1", "-ar", str(OUT_RATE), "-c:a", "libvorbis", "-b:a", OUT_BITRATE,
                    "-map_metadata", "-1", str(ogg)])
            print(f"built {ogg.relative_to(ROOT)}  ({text})")


def report() -> None:
    ref = [stats(p) | {"hi": hi_band_db(p)} for p in sorted(SRC.glob("*.ogg"))]
    print(f"\nreference: {len(ref)} NPC lines — median RMS {statistics.median(r['rms'] for r in ref):.1f} dBFS, "
          f"median >2.5 kHz {statistics.median(r['hi'] for r in ref):.1f} dB")
    print(f"{'clip':22s} {'dur':>5s} {'rms':>7s} {'peak':>7s} {'>2.5k':>7s} {'KB':>5s}  subtitle")
    for cid, (text, _, _) in RECIPES.items():
        p = OUT / f"{cid}.ogg"
        if not p.exists():
            print(f"{cid:22s} MISSING")
            continue
        s = stats(p)
        print(f"{cid:22s} {s['dur']:5.2f} {s['rms']:7.1f} {s['peak']:7.1f} {hi_band_db(p):7.1f} {p.stat().st_size / 1024:5.1f}  {text}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--report", action="store_true", help="only analyse the clips on disk")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # the subtitles carry ellipses
    if not a.report:
        build()
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
