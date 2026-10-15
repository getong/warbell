"""Minimal user-mode sampling profiler for Windows (no admin, no install): periodically suspends every
thread of a running process, walks its stack with dbghelp `StackWalk64`, and resumes it; after the
run it symbolises the addresses through the process's PDBs and prints, per thread, the hottest
functions by SELF and INCLUSIVE samples.

    python tools/prof/sample.py <pid> [--secs 20] [--hz 400] [--out report.txt] [--top 70]

Build the game with symbols for the crates you care about first (the default dev profile has
`debug = 0`, so there is no PDB at all) — e.g. line tables for the Bevy crates only, which keeps the
PDB under MSVC's size cap:

    CARGO_TARGET_DIR=target_sym cargo build --config "profile.dev.package.bevy_ecs.debug='line-tables-only'" ...

Idle samples (thread blocked in a kernel wait) are dropped, so percentages are of BUSY time.
"""
import ctypes
import ctypes.wintypes as wt
import collections
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
dbg = ctypes.WinDLL("dbghelp", use_last_error=True)

PROCESS_ALL = 0x1F0FFF
THREAD_ALL = 0x1F03FF
TH32CS_SNAPTHREAD = 0x4
CONTEXT_AMD64 = 0x100000
CONTEXT_CONTROL_INT = CONTEXT_AMD64 | 0x1 | 0x2
IMAGE_FILE_MACHINE_AMD64 = 0x8664
AddrModeFlat = 3


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", ctypes.c_long),
                ("tpDeltaPri", ctypes.c_long), ("dwFlags", wt.DWORD)]


class ADDRESS64(ctypes.Structure):
    _fields_ = [("Offset", ctypes.c_uint64), ("Segment", ctypes.c_uint16), ("Mode", ctypes.c_int)]


class STACKFRAME64(ctypes.Structure):
    _fields_ = [("AddrPC", ADDRESS64), ("AddrReturn", ADDRESS64), ("AddrFrame", ADDRESS64),
                ("AddrStack", ADDRESS64), ("AddrBStore", ADDRESS64), ("FuncTableEntry", ctypes.c_void_p),
                ("Params", ctypes.c_uint64 * 4), ("Far", wt.BOOL), ("Virtual", wt.BOOL),
                ("Reserved", ctypes.c_uint64 * 3), ("KdHelp", ctypes.c_byte * 512)]


class SYMBOL_INFOW(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wt.ULONG), ("TypeIndex", wt.ULONG), ("Reserved", ctypes.c_uint64 * 2),
                ("Index", wt.ULONG), ("Size", wt.ULONG), ("ModBase", ctypes.c_uint64), ("Flags", wt.ULONG),
                ("Value", ctypes.c_uint64), ("Address", ctypes.c_uint64), ("Register", wt.ULONG),
                ("Scope", wt.ULONG), ("Tag", wt.ULONG), ("NameLen", wt.ULONG), ("MaxNameLen", wt.ULONG),
                ("Name", ctypes.c_wchar * 1024)]


k32.OpenProcess.restype = wt.HANDLE
k32.OpenThread.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.SuspendThread.argtypes = [wt.HANDLE]
k32.ResumeThread.argtypes = [wt.HANDLE]
k32.GetThreadContext.argtypes = [wt.HANDLE, ctypes.c_void_p]
dbg.StackWalk64.argtypes = [wt.DWORD, wt.HANDLE, wt.HANDLE, ctypes.POINTER(STACKFRAME64), ctypes.c_void_p,
                            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
dbg.SymInitializeW.argtypes = [wt.HANDLE, wt.LPCWSTR, wt.BOOL]
dbg.SymFromAddrW.argtypes = [wt.HANDLE, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(SYMBOL_INFOW)]
dbg.SymFunctionTableAccess64.argtypes = [wt.HANDLE, ctypes.c_uint64]
dbg.SymFunctionTableAccess64.restype = ctypes.c_void_p
dbg.SymGetModuleBase64.argtypes = [wt.HANDLE, ctypes.c_uint64]
dbg.SymGetModuleBase64.restype = ctypes.c_uint64
FTA = ctypes.cast(dbg.SymFunctionTableAccess64, ctypes.c_void_p).value
GMB = ctypes.cast(dbg.SymGetModuleBase64, ctypes.c_void_p).value


def threads_of(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32()
    te.dwSize = ctypes.sizeof(te)
    out = []
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            out.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    k32.CloseHandle(snap)
    return out


def thread_name(h):
    p = ctypes.c_wchar_p()
    try:
        if k32.GetThreadDescription(h, ctypes.byref(p)) >= 0 and p.value:
            n = p.value
            k32.LocalFree(p)
            return n
    except Exception:
        pass
    return ""


def main():
    a = sys.argv
    pid = int(a[1])
    secs = float(a[a.index("--secs") + 1]) if "--secs" in a else 20.0
    hz = float(a[a.index("--hz") + 1]) if "--hz" in a else 400.0
    out = a[a.index("--out") + 1] if "--out" in a else "prof_report.txt"
    top = int(a[a.index("--top") + 1]) if "--top" in a else 70
    hp = k32.OpenProcess(PROCESS_ALL, False, pid)
    dbg.SymSetOptions(0x2 | 0x10 | 0x40)  # UNDNAME | LOAD_LINES | LOAD_ANYTHING (the PDB never 'matches' remotely)
    exe_dir = a[a.index('--symdir') + 1] if '--symdir' in a else None
    dbg.SymInitializeW(hp, exe_dir, False)
    psapi = ctypes.WinDLL("psapi")
    psapi.EnumProcessModules.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
    psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
    dbg.SymLoadModuleExW.restype = ctypes.c_uint64
    dbg.SymLoadModuleExW.argtypes = [wt.HANDLE, wt.HANDLE, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_uint64, wt.DWORD, ctypes.c_void_p, wt.DWORD]

    def load_modules():
        mods = (ctypes.c_void_p * 1024)()
        need = wt.DWORD()
        psapi.EnumProcessModules(hp, mods, ctypes.sizeof(mods), ctypes.byref(need))
        path = ctypes.create_unicode_buffer(1024)
        for i in range(need.value // ctypes.sizeof(ctypes.c_void_p)):
            psapi.GetModuleFileNameExW(hp, mods[i], path, 1024)
            dbg.SymLoadModuleExW(hp, None, path.value, None, mods[i], 0, None, 0)
    load_modules()
    ctxbuf = ctypes.create_string_buffer(1232 + 16)
    ctx = (ctypes.addressof(ctxbuf) + 15) & ~15
    handles = {}
    SKIP = ("IO Task Pool", "gilrs", "ctrl-c", "Async Compute")
    names = {}
    stacks = collections.defaultdict(list)  # tid -> [tuple(addrs)]
    t_end = time.perf_counter() + secs
    period = 1.0 / hz
    n = 0
    while time.perf_counter() < t_end:
        t0 = time.perf_counter()
        for tid in threads_of(pid):
            h = handles.get(tid)
            if h is None:
                h = k32.OpenThread(THREAD_ALL, False, tid)
                if not h:
                    continue
                handles[tid] = h
                names[tid] = thread_name(h)
            if any(x in names[tid] for x in SKIP):
                continue
            if k32.SuspendThread(h) == 0xFFFFFFFF:
                continue
            try:
                ctypes.memset(ctx, 0, 1232)
                ctypes.c_uint32.from_address(ctx + 0x30).value = CONTEXT_CONTROL_INT
                if not k32.GetThreadContext(h, ctx):
                    continue
                sf = STACKFRAME64()
                sf.AddrPC.Offset = ctypes.c_uint64.from_address(ctx + 0xF8).value
                sf.AddrPC.Mode = AddrModeFlat
                sf.AddrStack.Offset = ctypes.c_uint64.from_address(ctx + 0x98).value
                sf.AddrStack.Mode = AddrModeFlat
                sf.AddrFrame.Offset = ctypes.c_uint64.from_address(ctx + 0xA0).value
                sf.AddrFrame.Mode = AddrModeFlat
                addrs = []
                while len(addrs) < 96 and dbg.StackWalk64(IMAGE_FILE_MACHINE_AMD64, hp, h, ctypes.byref(sf), ctx, None, FTA, GMB, None):
                    if sf.AddrPC.Offset == 0:
                        break
                    addrs.append(sf.AddrPC.Offset)
                stacks[tid].append(tuple(addrs))
            finally:
                k32.ResumeThread(h)
        n += 1
        dt = time.perf_counter() - t0
        if dt < period:
            time.sleep(period - dt)
    print(f"sampled {n} rounds", file=sys.stderr)

    # symbolise (modules loaded now, after the run, so late-loaded DLLs are included)
    load_modules()
    cache = {}
    si = SYMBOL_INFOW()

    def sym(addr):
        s = cache.get(addr)
        if s is None:
            si.SizeOfStruct = 88  # sizeof(SYMBOL_INFOW) with its 1-char Name
            si.MaxNameLen = 1023
            disp = ctypes.c_uint64()
            if dbg.SymFromAddrW(hp, addr, ctypes.byref(disp), ctypes.byref(si)):
                s = si.Name
            else:
                s = f"?{addr:#x}"
            cache[addr] = s
        return s

    IDLE = ("NtWaitFor", "NtDelayExecution", "NtRemoveIoCompletion", "ZwWaitFor", "NtUserMsgWaitFor",
            "NtWaitForAlertByThreadId", "NtWaitForWorkViaWorkerFactory", "NtUserGetMessage", "NtSignalAndWaitForSingleObject")
    with open(out, "w", encoding="utf-8") as f:
        groups = collections.defaultdict(list)
        for tid, st in stacks.items():
            groups[names.get(tid) or f"tid{tid}"].append(tid)
        rows = []
        for g, tids in groups.items():
            busy = []
            total = 0
            for tid in tids:
                for s in stacks[tid]:
                    total += 1
                    if s and not any(k in sym(s[0]) for k in IDLE):
                        busy.append(s)
            rows.append((len(busy), total, g, busy))
        rows.sort(key=lambda r: -r[0])
        for nb, total, g, busy in rows:
            if nb == 0:
                continue
            f.write(f"\n===== thread group '{g}': busy {nb}/{total} samples ({100.0 * nb / max(total, 1):.0f}% busy)\n")
            selfc = collections.Counter()
            incl = collections.Counter()
            for s in busy:
                selfc[sym(s[0])] += 1
                seen = set()
                for a in s:
                    nm = sym(a)
                    if nm not in seen:
                        seen.add(nm)
                        incl[nm] += 1
            f.write("-- inclusive\n")
            for nm, c in incl.most_common(top):
                f.write(f"{100.0 * c / nb:6.1f}%  {nm[:200]}\n")
            f.write("-- self\n")
            for nm, c in selfc.most_common(top // 2):
                f.write(f"{100.0 * c / nb:6.1f}%  {nm[:200]}\n")
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
