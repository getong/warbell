"""Per-draw GPU timing breakdown of a RenderDoc capture (run inside qrenderdoc's embedded Python):

    qrenderdoc.exe --python tools/rdoc/analyze.py   (reads RDOC_CAP / RDOC_OUT env vars)

Writes RDOC_OUT (default target/rdoc/report.txt): every action with its GPU duration, the enclosing
debug-marker path (wgpu pass labels), vertex / instance counts and the bound pipeline's shaders;
then totals per pass, per pipeline and the top draws. Exits without opening the UI.
"""
import os, sys, collections, traceback

import renderdoc as rd

CAP = os.environ.get("RDOC_CAP", "target/rdoc/village.rdc")
OUT = os.environ.get("RDOC_OUT", "target/rdoc/report.txt")
TOP = int(os.environ.get("RDOC_TOP", "60"))
MIN_MS = float(os.environ.get("RDOC_MIN", "0.02"))


def main():
    out = open(OUT, "w", encoding="utf-8")
    p = lambda *a: print(*a, file=out, flush=True)
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(CAP, "", None) != rd.ResultCode.Succeeded:
        p("cannot open", CAP)
        return
    res, ctl = cap.OpenCapture(rd.ReplayOptions(), None)
    if res != rd.ResultCode.Succeeded:
        p("cannot replay", res)
        return
    sf = ctl.GetStructuredFile()
    rname = {r.resourceId: r.name for r in ctl.GetResources()}

    # flatten actions with their marker path
    rows = []

    def walk(acts, path):
        for a in acts:
            name = a.GetName(sf)
            if a.children:
                walk(a.children, path + [name])
            else:
                rows.append((a, path, name))

    walk(ctl.GetRootActions(), [])
    p(f"actions: {len(rows)}")

    dur = {}
    try:
        for r in ctl.FetchCounters([rd.GPUCounter.EventGPUDuration]):
            dur[r.eventId] = r.value.d
    except Exception as e:
        p("counter fetch failed", e)

    # pipeline / shader per draw
    refl_seen = {}

    def shaders_for(eid):
        ctl.SetFrameEvent(eid, False)
        st = ctl.GetPipelineState()
        names = [rname.get(st.GetGraphicsPipelineObject(), "?")]
        for stage in (rd.ShaderStage.Vertex, rd.ShaderStage.Pixel):
            sid = st.GetShader(stage)
            if sid != rd.ResourceId.Null():
                key = str(sid)
                if key not in refl_seen:
                    try:
                        r = st.GetShaderReflection(stage)
                        tags = [c.name for c in r.constantBlocks] + [t.name for t in r.readOnlyResources]
                        refl_seen[key] = ",".join(t for t in tags if t)[:90]
                    except Exception as e:
                        refl_seen[key] = "?"
                names.append(f"{str(stage).split('.')[-1][0]}:{rname.get(sid, key)}")
        return " | ".join(names)

    per_pass = collections.defaultdict(float)
    per_pass_n = collections.Counter()
    per_pipe = collections.defaultdict(lambda: [0.0, 0, 0])
    detail = []
    want_pipe = os.environ.get("RDOC_PIPES", "1") != "0"
    for a, path, name in rows:
        d = dur.get(a.eventId, 0.0) * 1000.0
        pas = path[-1] if path else "(root)"
        top = " / ".join(path[:2]) if path else "(root)"
        per_pass[top] += d
        per_pass_n[top] += 1
        is_draw = bool(a.flags & rd.ActionFlags.Drawcall) or bool(a.flags & rd.ActionFlags.Dispatch)
        sh = shaders_for(a.eventId) if (want_pipe and is_draw and d > MIN_MS) else ""
        verts = a.numIndices * max(1, a.numInstances)
        if sh:
            pp = per_pipe[(top, sh)]
            pp[0] += d
            pp[1] += 1
            pp[2] += verts
        detail.append((d, a.eventId, " / ".join(path), name, a.numIndices, a.numInstances, sh))

    total = sum(per_pass.values())
    p(f"\nTOTAL GPU {total:.3f} ms\n\n== per pass (marker path, 2 levels) ==")
    for k, v in sorted(per_pass.items(), key=lambda kv: -kv[1]):
        if v > 0.01:
            p(f"{v:8.3f} ms  {per_pass_n[k]:6d} actions  {k}")
    p("\n== per pipeline (pass, shaders) ==")
    for (top, sh), (v, n, verts) in sorted(per_pipe.items(), key=lambda kv: -kv[1][0])[:TOP]:
        p(f"{v:8.3f} ms  {n:5d} draws  {verts/1e6:8.2f} Mverts  {top}  {sh}")
    p("\n== top actions ==")
    for d, eid, path, name, ni, ninst, sh in sorted(detail, key=lambda r: -r[0])[:TOP]:
        p(f"{d:7.3f} ms  eid {eid:6d}  idx {ni:8d} x{ninst:5d}  {path} :: {name}  {sh}")
    ctl.Shutdown()
    cap.Shutdown()
    rd.ShutdownReplay()


try:
    main()
except Exception:
    with open(OUT, "a", encoding="utf-8") as f:
        traceback.print_exc(file=f)
os._exit(0)
