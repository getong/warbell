"""Launch the village perf scene from a symbol build and sample it with sample.py.
    python tools/prof/run_village.py <exe> <out.txt> [warmup_s] [secs] [KEY=VAL ...]"""
import os, subprocess, sys, time
exe, out = sys.argv[1], sys.argv[2]
warm = float(sys.argv[3]) if len(sys.argv) > 3 else 35
secs = sys.argv[4] if len(sys.argv) > 4 else "20"
env = dict(os.environ, BEVY_ASSET_ROOT=os.getcwd(), FOREST_PERFTEST="200", FOREST_PERFFOCUS="1",
           FOREST_NOVSYNC="1", FOREST_TPS="1", FOREST_IMMORTAL="1", FOREST_DEMO="work")
for kv in sys.argv[5:]:
    k, v = kv.split("=", 1); env[k] = v
p = subprocess.Popen([os.path.abspath(exe)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(warm)
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sample.py"), str(p.pid), "--secs", secs, "--out", out, "--symdir", os.path.dirname(os.path.abspath(exe))])
p.kill()
