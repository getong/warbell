"""One-frame timeline from a Bevy trace_chrome JSON: for a schedule run (default Update) near
--at <secs>, list every system span inside it (start offset, duration, thread) and the stretches
where only ONE thread was busy (the critical path the multithreaded executor can't parallelise).
    python tools/prof/frame_timeline.py trace.json [--at 25] [--sched Update]"""
import json, sys, collections
path = sys.argv[1]
at = float(sys.argv[sys.argv.index("--at") + 1]) * 1e6 if "--at" in sys.argv else 25e6
sched = sys.argv[sys.argv.index("--sched") + 1] if "--sched" in sys.argv else "Update"
want = f"schedule: name={sched}"
spans = []  # (name, tid, start, end)
stacks = collections.defaultdict(list)
target = None
with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip().rstrip(",")
        if not line or line in "[]":
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        ts = e.get("ts", 0.0)
        if ts < at - 2e6:
            continue
        if ts > at + 2e6 and target and ts > target[1] + 1e5:
            break
        ph, nm, tid = e.get("ph"), e.get("name", "?"), e.get("tid")
        if ph == "B":
            stacks[tid].append((nm, ts))
        elif ph == "E" and stacks[tid]:
            n0, t0 = stacks[tid].pop()
            if n0 == want and target is None and t0 >= at:
                target = (t0, ts)
            spans.append((n0, tid, t0, ts))
t0, t1 = target
print(f"{want}: {(t1 - t0) / 1000:.2f} ms")
sys_spans = [s for s in spans if s[0].startswith("system: name=") and s[2] >= t0 and s[3] <= t1]
sys_spans.sort(key=lambda s: s[2])
# busy-thread count over time (1 µs resolution buckets of 20 µs)
B = 20.0
nb = int((t1 - t0) / B) + 1
busy = [set() for _ in range(nb)]
for n, tid, a, b in sys_spans:
    for i in range(int((a - t0) / B), min(nb, int((b - t0) / B) + 1)):
        busy[i].add(tid)
one = sum(1 for s in busy if len(s) == 1) * B / 1000
zero = sum(1 for s in busy if len(s) == 0) * B / 1000
print(f"single-thread time {one:.2f} ms, no-system time {zero:.2f} ms")
print("longest systems:")
for n, tid, a, b in sorted(sys_spans, key=lambda s: -(s[3] - s[2]))[:25]:
    print(f"  {(a - t0) / 1000:7.2f} +{(b - a) / 1000:6.2f} ms  tid{tid}  {n[13:][:120]}")
print("timeline of systems >= 0.15 ms:")
for n, tid, a, b in sys_spans:
    if b - a >= 150:
        print(f"  {(a - t0) / 1000:7.2f} .. {(b - t0) / 1000:7.2f}  tid{tid}  {n[13:][:110]}")
