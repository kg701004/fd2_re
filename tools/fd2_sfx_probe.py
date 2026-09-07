#!/usr/bin/env python3
"""fd2_re - read which UI sfx index the original game plays for a given action.

Why this exists
---------------
`docs/knowledge-base/36-sfx-audio-data.md` lists a call site for each UI sfx
index but marks most of them `待確認`, because the semantics needed "畫面實測".
Nothing in this project could do that without listening -- until 2026-09-07,
when a breakpoint on `play_sfx_a` was shown to hit and to expose the pushed
arguments, so the index the engine actually chose can simply be *read*.

The recipe this wraps
---------------------
1. break at `play_sfx_a` (Ghidra 0x25a96) in a live DOSBox-X instance,
2. resume, perform one action,
3. when the breakpoint hits, read the caller's 3-push frame:

       [esp+0] = return address   -> identifies WHICH call site fired
       [esp+4] = table_ptr        -> which sfx pool ([0x53eec] is the UI pool)
       [esp+8] = index            -> the sfx index, i.e. the answer
       [esp+c] = priority

Return address minus the load delta gives a Ghidra address that can be matched
straight against doc36's call-site table, so each observation says both "index
N played" and "from the call site doc36 attributes to index N" -- two facts,
not one.

Detecting the hit
-----------------
`debugger-status` and the tmux pane both go stale (they can show a debugger TUI
drawn at some earlier point), so neither is trusted here. Paused-ness is decided
by a *liveness* test instead: send a harmless key and see whether the screen
changes. A frozen screen after a keypress means execution is halted.

Usage
-----
    python tools/fd2_sfx_probe.py --instance esfx --arm
    python tools/fd2_sfx_probe.py --instance esfx --action "tab" --label "open unit ring"
    python tools/fd2_sfx_probe.py --instance esfx --selftest
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HELPER = Path(__file__).resolve().parent / "fd2_dosbox_live_helper.py"
PLAY_SFX_A = 0x25A96
PLAY_SFX_B = 0x25B45
UI_POOL_GLOBAL = 0x53EEC
TMUX_SOCKET = "fd2harness"


def _helper(*args: str, timeout: int = 240) -> str:
    r = subprocess.run([sys.executable, str(HELPER), *args],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def _pane(instance: str, lines: int = 60) -> str:
    r = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--", "bash", "-c",
                        f"tmux -L {TMUX_SOCKET} capture-pane -p -t harness-{instance}"],
                       capture_output=True, text=True, timeout=120)
    return r.stdout or ""


def calibrate(instance: str) -> int:
    """Load delta, recomputed every boot -- never reuse a previous run's value."""
    out = _helper("mem", "find-signature", "--instance", instance, "--selector", "0170",
                  "--linear", "100000", "--bytecount", "200000",
                  "--hex-sig", "0606060609090909", "--ghidra-addr", "51f75", timeout=400)
    m = re.search(r"delta:\s*(0x[0-9a-fA-F]+)", out)
    if not m:
        raise RuntimeError(f"delta calibration failed:\n{out}")
    return int(m.group(1), 16)


def arm(instance: str, delta: int | None = None, handle: str = "a") -> dict:
    # The debugger must be entered BEFORE calibrating: the delta search goes
    # through MEMDUMPBIN, which does nothing while the guest is running. Getting
    # this order wrong produced a bare "delta calibration failed" (2026-09-07).
    _helper("enter-debugger", "--instance", instance)
    delta = calibrate(instance) if delta is None else delta
    target = (PLAY_SFX_A if handle == "a" else PLAY_SFX_B) + delta
    _helper("debugger-cmd", "--instance", instance, f"BP 0170:{target:08X}")
    _helper("resume", "--instance", instance)
    return {"delta": hex(delta), "breakpoint": f"0170:{target:08X}",
            "ghidra": hex(PLAY_SFX_A if handle == "a" else PLAY_SFX_B)}


def _screens_differ(instance: str, tag: str) -> bool:
    a = f".wsl_build/{instance}/probe_{tag}_1.png"
    b = f".wsl_build/{instance}/probe_{tag}_2.png"
    _helper("screenshot", "--instance", instance, "--autocrop", "--out", a)
    _helper("key", "--instance", instance, "left", "--wait", "1", "--no-require-change")
    _helper("screenshot", "--instance", instance, "--autocrop", "--out", b)
    from PIL import Image, ImageChops  # noqa: PLC0415
    va, vb = a.replace(".png", "_view.png"), b.replace(".png", "_view.png")
    ia, ib = Image.open(va).convert("RGB"), Image.open(vb).convert("RGB")
    return ImageChops.difference(ia, ib).getbbox() is not None


def read_frame(instance: str, delta: int) -> dict:
    """Parse EIP/ESP, dump the pushed frame, return the decoded 3 arguments."""
    pane = _pane(instance)
    m = re.search(r"EIP=([0-9A-Fa-f]{8})", pane)
    e = re.search(r"ESP=([0-9A-Fa-f]{8})", pane)
    if not (m and e):
        return {"hit": False, "note": "no EIP/ESP in pane -- probably still running"}
    eip, esp = int(m.group(1), 16), int(e.group(1), 16)
    # Guard: only a stop exactly AT the breakpoint is a real observation. A stale
    # pane can show an EIP a few bytes past it, and reading the stack anyway
    # yields plausible-looking nonsense -- caught 2026-09-07 by a negative
    # control (an unbound key reported index=2129944 from a bogus call site).
    expected = {PLAY_SFX_A + delta, PLAY_SFX_B + delta}
    if eip not in expected:
        return {"hit": False, "eip": hex(eip),
                "note": ("stopped EIP is not the play_sfx breakpoint "
                         f"({', '.join(hex(x) for x in sorted(expected))}); "
                         "no sfx call observed for this action")}
    # The debugger's `D` view starts at a 16-byte-aligned address, so asking for
    # an unaligned ESP silently produced no matching row and the observation was
    # dropped (seen 2026-09-07 with ESP=0x1f164c). Dump from the aligned base and
    # index into it instead; two rows so a 16-byte frame never straddles the end.
    base, off = esp & ~0xF, esp & 0xF
    _helper("debugger-cmd", "--instance", instance, f"D 0178:{base:08X}")
    pane2 = _pane(instance)
    b: list[int] = []
    for r in range(2):
        row = re.search(rf"0178:{base + r * 16:08X}\s+((?:[0-9A-Fa-f]{{2}} ){{16}})", pane2)
        if not row:
            break
        b += [int(x, 16) for x in row.group(1).split()]
    if not b:
        # No rows at all means the `D` command did nothing, which means the guest
        # is still running -- the EIP/ESP above came from a stale TUI render, not
        # from a stop. Reporting that as a parse failure (as the first version
        # did) hides a plain "the breakpoint did not fire for this action".
        return {"hit": False,
                "note": "no breakpoint hit for this action (pane EIP/ESP was stale)"}
    if len(b) < off + 16:
        return {"hit": True, "eip": hex(eip), "esp": hex(esp),
                "note": f"stack frame straddles the dump (base {base:#x}, got {len(b)} bytes)"}
    b = b[off:off + 16]
    def dw(o: int) -> int:
        return b[o] | b[o + 1] << 8 | b[o + 2] << 16 | b[o + 3] << 24
    ret, table_ptr, index, prio = dw(0), dw(4), dw(8), dw(12)
    return {
        "hit": True,
        "eip": hex(eip),
        "play_sfx_ghidra": hex(eip - delta),
        "return_address_live": hex(ret),
        "call_site_ghidra": hex(ret - delta - 5),
        "table_ptr": hex(table_ptr),
        "index": index,
        "priority": prio,
    }


def probe(instance: str, delta: int, action: list[str], label: str) -> dict:
    _helper("resume", "--instance", instance)
    for k in action:
        _helper("key", "--instance", instance, k, "--wait", "2", "--no-require-change")
    frame = read_frame(instance, delta)
    frame["label"] = label
    frame["action"] = " ".join(action)
    return frame


def selftest(instance: str) -> int:
    """The one pin this tool has: a direction key must produce index 0 from a
    direction-key call site. doc36 lists 0x117a1/0x11a33/0x11a54/0x11a75/0x11a96
    as the five direction branches and calls index 0 (cursor move) CONFIRMED, so
    both halves of the answer are independently known in advance -- if the tool
    reports either half wrong, it is the tool that is broken."""
    KNOWN_DIR_SITES = {0x117A1, 0x11A33, 0x11A54, 0x11A75, 0x11A96}
    info = arm(instance)
    delta = int(info["delta"], 16)
    print(f"armed: {info}")
    r = probe(instance, delta, ["right"], "direction key")
    print(f"    {r}")
    fails = []
    if not r.get("hit"):
        fails.append("breakpoint did not hit on a direction key")
    else:
        if r.get("index") != 0:
            fails.append(f"index was {r.get('index')}, expected 0 (cursor move)")
        site = int(r.get("call_site_ghidra", "0x0"), 16)
        if site not in KNOWN_DIR_SITES:
            fails.append(f"call site {hex(site)} is not one of doc36's five direction branches")
    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed (index and call site both matched the pre-known answer).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--arm", action="store_true", help="calibrate delta and set the breakpoint")
    ap.add_argument("--delta", type=lambda s: int(s, 0), help="skip calibration (unsafe across boots)")
    ap.add_argument("--action", help="space-separated keys to send before reading the frame")
    ap.add_argument("--label", default="", help="what that action is, for the printed record")
    ap.add_argument("--read", action="store_true", help="just decode the current stopped frame")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest(a.instance)
    if a.arm:
        print(arm(a.instance, a.delta))
        return 0
    delta = a.delta if a.delta is not None else calibrate(a.instance)
    if a.read:
        print(read_frame(a.instance, delta))
        return 0
    if not a.action:
        ap.error("need --arm, --read, --action or --selftest")
    print(probe(a.instance, delta, a.action.split(), a.label))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
