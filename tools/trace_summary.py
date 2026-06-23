#!/usr/bin/env python3
"""Summarise a Bevy `trace_chrome` capture into an exact CPU-time-per-system breakdown.

Build with the profiling feature, run a short capture, then point this at the JSON it writes:

    cargo run --features profiling   # (set FOREST_PERFTEST + the scene env you want to profile)
    python tools/trace_summary.py trace-<timestamp>.json [--frames N]

Each Bevy system/stage becomes a span; this aggregates total + per-call time so you can see WHERE
the CPU frame goes (pair it with the GPU per-pass timings the PERF/F2 logs already print). Span time
sums across worker threads, so `total_ms` can exceed wall-clock — `us/call` is the per-frame cost of
a once-per-frame system. Stdlib only.
"""
import collections
import json
import sys


def iter_events(path):
    """Stream the chrome trace (tracing-chrome writes one JSON object per line inside a `[ ... ]`),
    so a multi-GB capture parses in constant memory."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line in ("[", "]"):
                continue
            if line.endswith(","):
                line = line[:-1]
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def aggregate(events, after_us=0.0):
    dur = collections.defaultdict(float)  # name -> total microseconds
    cnt = collections.defaultdict(int)
    stacks = collections.defaultdict(list)  # tid -> [(name, ts)]  (begin/end pairing per thread)
    for e in events:
        # Skip the startup window (e.g. the chunked world build) so the breakdown is STEADY-STATE.
        if after_us and e.get("ts", 0.0) < after_us:
            continue
        ph = e.get("ph")
        name = e.get("name", "?")
        if ph == "X":  # complete event with its own duration
            dur[name] += e.get("dur", 0.0)
            cnt[name] += 1
        elif ph == "B":
            stacks[e.get("tid")].append((name, e.get("ts", 0.0)))
        elif ph == "E":
            st = stacks.get(e.get("tid"))
            if st:
                n0, ts0 = st.pop()
                dur[n0] += e.get("ts", 0.0) - ts0
                cnt[n0] += 1
    return dur, cnt


def main():
    if len(sys.argv) < 2:
        print("usage: trace_summary.py <trace.json> [--frames N] [--top N]")
        return
    path = sys.argv[1]
    frames = None
    top = 45
    after_us = 0.0
    for i, a in enumerate(sys.argv):
        if a == "--frames" and i + 1 < len(sys.argv):
            frames = int(sys.argv[i + 1])
        if a == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])
        if a == "--after" and i + 1 < len(sys.argv):
            after_us = float(sys.argv[i + 1]) * 1_000_000.0  # seconds → microseconds

    dur, cnt = aggregate(iter_events(path), after_us)
    rows = sorted(dur.items(), key=lambda kv: -kv[1])
    grand = sum(dur.values()) / 1000.0

    # Estimate frame count from the most-frequent once-per-frame-looking span if not given.
    if frames is None and cnt:
        frames = max(cnt.values())

    print(f"\n{'system / span':52} {'total_ms':>10} {'calls':>8} {'us/call':>9} {'ms/frame':>9}")
    print("-" * 92)
    for name, d in rows[:top]:
        c = cnt[name]
        per_call = d / max(c, 1)
        per_frame = (d / 1000.0) / frames if frames else 0.0
        print(f"{name[:52]:52} {d / 1000:>10.1f} {c:>8} {per_call:>9.1f} {per_frame:>9.3f}")
    print("-" * 92)
    print(f"{'TOTAL span-ms (sums across threads)':52} {grand:>10.1f}  est. frames={frames}")


if __name__ == "__main__":
    main()
