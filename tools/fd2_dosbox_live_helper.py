#!/usr/bin/env python3
"""FD2-DOSBOX-LIVE-HELPER: a thin Python CLI over tools/dosbox_harness.sh
(the existing N-way parallel dosbox-x/heavy-debugger harness, see
docs/knowledge-base/98-tooling-infrastructure.md's "N-way 平行 dosbox-x
live-verification harness" section) -- it does NOT reimplement any of that
harness's launch/teardown/registry core, it wraps it and adds the specific
conveniences identified as missing while doing live DOSBox-X verification
work this session: settle-confirmed key delivery, screenshot resize/
window-bounds-crop, a push-button live-memory-read command, and a canonical-
file integrity check.

ARCHITECTURE -- why there are TWO files (this one + fd2_dosbox_live_helper.sh)
--------------------------------------------------------------------
ALL WSL-side logic (dosbox_harness.sh invocations, xdotool/tmux/convert/
md5sum calls, reading dosbox_harness.sh's own per-instance state file) lives
in the companion tools/fd2_dosbox_live_helper.sh, invoked here as real argv
(`wsl -d Ubuntu bash <script.sh> <subcommand> <arg1> <arg2> ...`), NEVER as a
Python-built multi-statement `bash -c "stmt1; stmt2"` string. This exact
architecture was forced by a genuine, reproducible bug found building the
sibling remake-side tool (tools/fd2_live_input_helper.py/.sh, 2026-09-01,
full repro in that tool's own module docstring and in doc98's dated
2026-09-01 section): a multi-statement script passed as a single `bash -c
"..."` STRING argument through wsl.exe silently drops shell variable state
between statements, even though the assignment itself demonstrably succeeds
inside that same `-c` string (`declare -p` proves it) -- only the later USE
of the variable is lost. A real `.sh` file invoked with plain positional
argv does not have this problem (same pattern tools/dosbox_harness.sh and
tools/dosbox_diff_harness.sh already used, incidentally, before it was ever
written up). This module's sh()/wsl_argv_run() always use that real-argv
form for exactly that reason -- do not "simplify" a future change back into
an inline -c string.

WHAT'S NEW HERE vs. calling tools/dosbox_harness.sh directly
--------------------------------------------------------------------
1. Screenshot resize/window-bounds-crop (`screenshot --autocrop`/`--resize`):
   dosbox_harness.sh's own screenshot is `import -window root` -- the WHOLE
   Xvfb virtual screen, not just the dosbox-x window, so the raw capture
   legitimately includes real desktop background outside the game window.
   `--autocrop` here is a two-step process (exact window-bounds crop via a
   fresh xdotool geometry query, then an optional best-effort fuzzy trim for
   dosbox-x's own persistent GUI menu bar) -- deliberately DIFFERENT from
   the remake-side template's single fuzzy -trim, because this project's
   empirical testing (2026-09-02, see the .sh companion's cmd_screenshot
   docstring and docs/knowledge-base/98-tooling-infrastructure.md's dated
   section) found a bare -trim on this tool's raw capture can eat a few
   real (if content-free) pixels of the dosbox-x window's own edge, since
   the surrounding Xvfb desktop background happens to be the same pure
   black (#000000) as much of the game's own UI. `raw` is ALWAYS the
   untouched capture, exactly as fd2_live_input_helper.py's screenshot()
   guarantees, after a real bug in an early version of THAT tool overwrote
   the raw file in place (doc98's 續四).
2. Settle-confirmed key delivery (`key --wait`/`--settle`): same pattern as
   fd2_live_input_helper.py's `key` -- a MITIGATION for, not a fix to, this
   project's known, 9-round-investigated Xvfb/xdotool/DOSBox-X input-
   reliability problem (docs/knowledge-base/58-remake-live-verification-
   log.md 續七十~續七十七, search "xtrace"/"掉鍵"; doc58's own conclusion is
   "已重新定界的環境限制" -- a re-scoped environment limitation, NOT solved
   here or anywhere else in this project so far). Do not oversell what
   --settle proves: it confirms the screen stopped visibly changing, not
   that any specific keystroke was received.
3. `mem dump` / `mem read-unit-record`: packages the already-proven byte-
   signature + MEMDUMPBIN live-memory-extraction technique (docs/knowledge-
   base/48-dosbox-x-debugger-build.md, the many MEMDUMPBIN rounds in
   58-remake-live-verification-log.md, and this project's own
   fd2-dosbox-live-memory-extraction memory reference) into a reusable
   command, with the two sharpest documented footguns baked in as hard/soft
   guards in the .sh companion: a zero/empty selector is refused outright
   (doc58: silently returns garbage, not an error -- selectors this project
   has seen for FD2.EXE are 0170/0178, but per doc58 續四十 do NOT assume
   stability across a fresh boot), and a missing output file after the
   debugger reported success is surfaced as the KNOWN DOSBox-X upstream bug
   it almost certainly is (GitHub issue #3629), not swallowed as a generic
   failure. This does not solve any NEW RE question -- it makes the
   EXISTING proven technique push-button.
4. `verify-canonical`: read-only md5 check of $HOME/fd2-run/FD2.EXE (and its
   .pristine_bak) against the known-pristine hash. Exists because
   ~/fd2-run/FD2.EXE was found silently contaminated earlier this project
   (a leftover, never-reverted debug patch from an unrelated 2026-08-19
   investigation zeroed enemy growth-table bytes for raw_unit_key 76-127,
   docs/knowledge-base/92-m5-normal-playthrough-log.md 續八/續九) and cost
   real wasted effort before being caught. NEVER writes/restores anything --
   the contaminated state is CURRENTLY a deliberate, still-in-use state for
   a separate, unrelated, active investigation thread; this command's whole
   job is making that visible, not "fixing" it. `launch` also runs this
   check and prints a one-line, non-blocking warning (never a hard failure)
   if the canonical dir's FD2.EXE doesn't match pristine.

USAGE
-----
Session lifecycle (`launch` is long-lived foreground, same as
dosbox_harness.sh's own launch -- background this call yourself, e.g. via
your tool's own run_in_background option; do not add another layer of `&`
around it, see dosbox_harness.sh's header comment for why that gets the
whole process tree reaped):
    python tools/fd2_dosbox_live_helper.py launch --instance myrun
    python tools/fd2_dosbox_live_helper.py status
    python tools/fd2_dosbox_live_helper.py teardown --instance myrun

Key delivery + screenshot:
    python tools/fd2_dosbox_live_helper.py key --instance myrun Return --wait 1.0
    python tools/fd2_dosbox_live_helper.py key --instance myrun Escape --settle
    python tools/fd2_dosbox_live_helper.py screenshot --instance myrun --label title --autocrop

Live memory read (debugger must already be entered -- see debugger-status;
use `resume`, not a second `enter-debugger`, to reliably exit -- Alt+Pause's
"exit" direction has been observed to fail silently, see module docstring
section 5):
    python tools/fd2_dosbox_live_helper.py enter-debugger --instance myrun
    python tools/fd2_dosbox_live_helper.py debugger-status --instance myrun
    python tools/fd2_dosbox_live_helper.py mem dump --instance myrun --selector 0170 --linear 26DF88 --bytecount 32
    python tools/fd2_dosbox_live_helper.py mem read-unit-record --instance myrun --selector 0170 --linear 26DF88
    python tools/fd2_dosbox_live_helper.py resume --instance myrun --verify

Delta calibration + the ring-entry-gate dynamic unit array (see module
docstring section 5 -- `read-unit-array` bakes in a proven-reproducible
recipe as a one-shot; `find-signature`/`resolve-ptr` are generic building
blocks for any future pointer-chase need):
    python tools/fd2_dosbox_live_helper.py mem read-unit-array --instance myrun --selector 0170
    python tools/fd2_dosbox_live_helper.py mem find-signature --instance myrun --selector 0170 --linear 100000 --bytecount 200000 --hex-sig "83fa02750e..." --ghidra-addr 11912
    python tools/fd2_dosbox_live_helper.py mem resolve-ptr --instance myrun --selector 0170 --live-addr 1ad8e2

Canonical-file integrity:
    python tools/fd2_dosbox_live_helper.py verify-canonical
    python tools/fd2_dosbox_live_helper.py verify-canonical --path /some/other/copy

See docs/knowledge-base/98-tooling-infrastructure.md for the full design
writeup (dated 2026-09-02 section) and docs/knowledge-base/58-remake-live-
verification-log.md / 48-dosbox-x-debugger-build.md for the live-
verification rounds this tool packages proven techniques from.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
SH_SCRIPT_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "fd2_dosbox_live_helper.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
DEFAULT_SHOT_DIR = REPO_ROOT / ".wsl_build" / "dosbox_live_helper"
DEFAULT_WAIT_S = 0.5  # doc48 §8.3's measured-safe general floor for a single confirmed keypress
DEFAULT_UNIT_RECORD_SIZE_HEX = "32"  # 50 bytes -- the size doc58 續四十 dumped and validated a full battle-unit record at


# --------------------------------------------------------------------------
# WSL plumbing -- always real argv, never a multi-statement -c string
# (see module docstring's ARCHITECTURE section for why).
# --------------------------------------------------------------------------

def to_wsl_path(windows_path: Path) -> str:
    p = str(windows_path.resolve()).replace("\\", "/")
    drive, rest = p.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


def wsl_argv_run(argv: list[str], timeout: int = 60, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Run `wsl -d Ubuntu <argv...>` as a real argument list (never a joined
    shell string -- see module docstring). Does not raise on nonzero exit:
    wsl.exe itself has been observed elsewhere in this project's tooling to
    be an unreliable narrator of its own exit code; callers verify success
    from stdout/stderr content."""
    import os
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    if env_extra:
        env.update(env_extra)
    full = ["wsl", "-d", "Ubuntu"] + argv
    # encoding="utf-8" is NOT optional here: WSL's stdout is UTF-8, but
    # subprocess.run(text=True) without an explicit encoding falls back to
    # locale.getpreferredencoding() -- on Windows that is normally an ANSI
    # codepage, not UTF-8, and silently mangles any non-ASCII byte sequence
    # (found live 2026-09-02: fd2_dosbox_live_helper.sh's own "§4.1"
    # section-mark character came back as a mojibake CJK character with
    # errors="strict" absent -- errors="replace" would have hidden this
    # instead of surfacing it during testing, so it is deliberately not used).
    return subprocess.run(full, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)


def sh(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Invoke tools/fd2_dosbox_live_helper.sh <args...> over WSL as real argv."""
    argv = ["bash", SH_SCRIPT_WSL] + [str(a) for a in args]
    return wsl_argv_run(argv, timeout=timeout)


def sh_checked(*args: str, timeout: int = 30) -> str:
    """Like sh(), but raises with full stdout+stderr if the call produced no
    stdout or the .sh script's own die() fired (stderr starts with
    'ERROR:'). Use for any primitive that must never fail silently."""
    r = sh(*args, timeout=timeout)
    out = r.stdout.strip()
    if not out or "ERROR:" in r.stderr:
        raise RuntimeError(
            f"fd2_dosbox_live_helper.sh {' '.join(args)} failed "
            f"(rc={r.returncode})\nSTDOUT: {out!r}\nSTDERR: {r.stderr.strip()!r}"
        )
    return out


# --------------------------------------------------------------------------
# 1. Session lifecycle -- thin passthroughs to dosbox_harness.sh
# --------------------------------------------------------------------------

def launch(instance: str, keepalive: int | None, on_line=None) -> int:
    """launch is long-lived foreground (dosbox_harness.sh's own launch ends
    in `exec sleep $keepalive`, and per doc48 §8.4 the WSL connection that
    started it must stay open for the WHOLE keepalive period or WSLg reaps
    the entire Xvfb/tmux/dosbox-x process tree within 15-60s) -- caller must
    background this ENTIRE CALL (the whole python invocation), exactly like
    dosbox_harness.sh's own launch requires.

    Deliberately uses Popen + line streaming, NOT sh()/subprocess.run: a
    plain subprocess.run(capture_output=True) fully buffers stdout and only
    returns it once the child process EXITS -- for a multi-hour keepalive
    that means the launch confirmation banner (port/window id/OK-or-
    window_not_found) would be invisible for the entire session, not just
    delayed (found live 2026-09-02 testing this exact command). Streaming
    line-by-line via on_line() (default: print) preserves the same "must
    stay connected the whole time" blocking requirement -- this function
    still does not return until the child exits or the keepalive elapses --
    it just makes what's happening observable as it happens instead of only
    at the very end."""
    import os
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    args = ["launch", instance] + ([str(keepalive)] if keepalive else [])
    argv = ["wsl", "-d", "Ubuntu", "bash", SH_SCRIPT_WSL] + args
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", bufsize=1, env=env)
    emit = on_line or print
    assert proc.stdout is not None
    for line in proc.stdout:
        emit(line.rstrip("\n"))
    return proc.wait()


def status(stale_after: int | None = None) -> str:
    args = ["status"] + ([str(stale_after)] if stale_after is not None else [])
    return sh(*args, timeout=15).stdout.strip()


def teardown(instance: str) -> str:
    return sh_checked("teardown", instance, timeout=30)


def teardown_all() -> str:
    return sh_checked("teardown-all", timeout=60)


def enter_debugger(instance: str) -> str:
    return sh_checked("enter-debugger", instance, timeout=15)


def debugger_cmd(instance: str, text: str) -> str:
    return sh_checked("debugger-cmd", instance, text, timeout=15)


def debugger_status(instance: str, baseline: Path | None = None) -> str:
    args = ["debugger-status", instance] + ([to_wsl_path(baseline)] if baseline is not None else [])
    return sh_checked(*args, timeout=15)


def resume(instance: str) -> str:
    """Reliably resume from the debugger via its own RUN console command --
    see fd2_dosbox_live_helper.sh's cmd_resume docstring for why this exists
    (Alt+Pause's "exit debugger" direction was found live to fail silently
    several times in a row, 2026-09-02)."""
    return sh_checked("resume", instance, timeout=15)


# --------------------------------------------------------------------------
# 2. Settle-confirmed key delivery
# --------------------------------------------------------------------------

KEY_ALIASES = {
    "confirm": "Return", "enter": "Return", "return": "Return",
    "cancel": "Escape", "esc": "Escape", "escape": "Escape",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "tab": "Tab", "space": "space",
}


def resolve_key(token: str) -> str:
    return KEY_ALIASES.get(token.lower(), token)


def send_keys(instance: str, keys: list[str]) -> str:
    return sh_checked("key", instance, *keys, timeout=15)


def wait_for_settle(instance: str, timeout: float = 10.0, interval: float = 0.25,
                     tmp_prefix: Path | None = None,
                     baseline: Path | None = None) -> tuple[bool, str, bool | None]:
    """See fd2_dosbox_live_helper.sh's wait-settle: polls via repeated
    dosbox_harness.sh screenshot calls, stops when 2 CONSECUTIVE shots
    md5-match. MITIGATION for, not a fix to, the project's known input-
    reliability problem -- see module docstring.

    If `baseline` (a screenshot taken BEFORE the key was sent) is given, the
    .sh side compares it against the final settled frame and appends a
    `response=NO_RESPONSE`/`response=CHANGED` tag, parsed here into the
    third return value (None if no baseline was given). NO_RESPONSE means
    "the screen looked identical before and after this key send" -- a
    best-effort signal worth logging/flagging, NOT proof the key was
    dropped (some keys legitimately produce no visible change)."""
    prefix = tmp_prefix or (DEFAULT_SHOT_DIR / instance / f"settle_{int(time.time() * 1000)}")
    max_tries = max(2, int(round(timeout / interval)))
    args = ["wait-settle", instance, to_wsl_path(prefix), str(max_tries), str(interval)]
    if baseline is not None:
        args.append(to_wsl_path(baseline))
    r = sh(*args, timeout=int(timeout) + 20)
    out = r.stdout.strip()
    if not out.startswith("SETTLED") and r.stderr.strip():
        out = f"{out} STDERR: {r.stderr.strip()}" if out else r.stderr.strip()
    no_response = None
    if "response=NO_RESPONSE" in out:
        no_response = True
    elif "response=CHANGED" in out:
        no_response = False
    return out.startswith("SETTLED"), out, no_response


# --------------------------------------------------------------------------
# 3. Screenshot capture
# --------------------------------------------------------------------------

class ScreenshotResult:
    __slots__ = ("raw", "view")

    def __init__(self, raw: Path, view: Path | None):
        self.raw = raw
        self.view = view


def screenshot(instance: str, out: Path, resize: str | None = None,
               autocrop: bool = False, view_out: Path | None = None) -> ScreenshotResult:
    """`out` is ALWAYS the raw, unmodified `dosbox_harness.sh screenshot`
    capture (import -window root -- the whole Xvfb screen). If resize/
    autocrop is requested, the processed image goes to a SEPARATE file
    (view_out, auto-derived as `<out stem>_view<out suffix>` if not given) --
    `out` itself is never touched past the initial capture. See module
    docstring point 1 for why --autocrop here is a two-step (window-bounds
    crop + optional fuzzy trim) rather than the remake template's single
    fuzzy trim, and why --resize has no forced default on this tool."""
    out.parent.mkdir(parents=True, exist_ok=True)
    wants_view = bool(resize) or autocrop
    view_path = None
    args = ["screenshot", instance, to_wsl_path(out), resize or "", "1" if autocrop else "0"]
    if wants_view:
        view_path = view_out or out.with_name(f"{out.stem}_view{out.suffix}")
        view_path.parent.mkdir(parents=True, exist_ok=True)
        args.append(to_wsl_path(view_path))
    sh_checked(*args, timeout=25)
    return ScreenshotResult(raw=out, view=view_path)


def default_screenshot_path(instance: str, label: str | None) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    tag = f"_{label}" if label else ""
    return DEFAULT_SHOT_DIR / instance / f"{ts}{tag}.png"


# --------------------------------------------------------------------------
# 4. Live-memory-extraction convenience
# --------------------------------------------------------------------------

# Fields validated live against real record bytes, docs/knowledge-base/
# 58-remake-live-verification-log.md 續四十 (MEMDUMPBIN 178 26DF88 50):
# offset -> (label, expected/meaning). This is NOT a complete struct layout
# -- only the 5 fields that transcript actually cross-checked field-by-field
# against the game's own entry-gate logic. Treat anything outside this list
# as raw, undecoded bytes.
KNOWN_UNIT_RECORD_FIELDS = {
    0x05: "Acted flag (bit7) -- entry gate 2; 0x00 (bit7 clear) = not yet acted",
    0x06: "camp/gate1 byte -- entry gate 1; compared via `CMP EDX,0x2` at 0x11912",
    0x07: "pre-check byte -- must not equal 0x79 ('y') for the pre-check to pass",
    0x1f: "pre-check byte -- must not equal 0x0a ('\\n') for the pre-check to pass",
    0x26: "transient/gate3 byte -- entry gate 3; expect 0x00",
    # +0x40..+0x4f added 2026-09-02 (92-m5-normal-playthrough-log.md 續四):
    # live-verified via a 2MB MEMDUMPBIN + byte-signature search for an
    # 8-byte HP/MP pattern, cross-checked field-by-field against the
    # in-game character status card (all 8 matched exactly, e.g. Sol's
    # displayed HP042/MP000/AP016/DP012/HIT097/DX002). Values are u16 LE.
    0x40: "HPmax (u16 LE)",
    0x42: "HPcur (u16 LE)",
    0x44: "MPmax (u16 LE)",
    0x46: "MPcur (u16 LE)",
    0x48: "AP (u16 LE, base value before weapon bonus)",
    0x4a: "DP (u16 LE)",
    0x4c: "HIT (u16 LE)",
    0x4e: "DX (u16 LE)",
}


def mem_dump(instance: str, selector: str, linear: str, bytecount: str, out: Path) -> tuple[Path, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = sh_checked("mem-dump", instance, selector, linear, bytecount, to_wsl_path(out), timeout=30).splitlines()
    size = None
    for line in lines:
        if line.startswith("SIZE="):
            size = int(line.split("=", 1)[1])
    if size is None:
        raise RuntimeError(f"mem-dump did not report a SIZE= line; raw output: {lines!r}")
    return out, size


def format_hexdump(data: bytes, bytes_per_line: int = 16) -> str:
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i + bytes_per_line]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        asciipart = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  +0x{i:02x}  {hexpart:<{bytes_per_line * 3}}  {asciipart}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 5. Delta calibration + dynamic-array pointer chase
# --------------------------------------------------------------------------
# Packages the byte-signature/delta technique from
# docs/knowledge-base/reference (memory `fd2-dosbox-live-memory-extraction`)
# and doc58's 續十三 pointer-dereference refinement into reusable, generic
# commands, plus one domain-specific one-shot command for the specific
# ring-entry-gate array this project has repeatedly needed. Built 2026-09-02
# after manually repeating this exact multi-step recipe (dump, search,
# compute delta, resolve a load-time-patched disp32, dereference, dump
# records) across ~15 separate tool calls in one investigation round --
# see docs/knowledge-base/92-m5-normal-playthrough-log.md's 續十四/續十六.
#
# `find-signature` and `resolve-ptr` are GENERIC: they take a hex signature/
# ghidra address, or a live address/disp offset, as arguments -- they do not
# know anything about unit records and can be reused for any future
# delta-calibration need in this game, not just this one.
#
# `read-unit-array` is the DOMAIN-SPECIFIC one-shot: it bakes in the
# specific signature/addresses for the ring-entry-gate array (proven
# reproducible across 2 independent fresh boots 2026-09-02, see doc92
# 續十四) as a starting point, and chains find-signature -> resolve-ptr ->
# a final array dump + per-record decode into one call. If the baked-in
# constants ever stop matching (0 or >1 signature hits, or decoded HP
# fields don't match any known living unit), that means the recipe needs
# recalibrating for a changed environment -- fall back to the generic
# find-signature/resolve-ptr commands with a fresh signature, don't assume
# the constants are eternal (doc58's own standing warning still applies in
# principle, even though this project has now seen the SAME delta/pointer/
# array-base values reproduce across 3 independent sessions total, spanning
# weeks -- see doc92 續十四 for the full reproducibility discussion).

# Ghidra-static-address anchor for the already-documented 34-byte
# ring-entry-gate signature (docs/knowledge-base/13-battle-menu-system.md's
# `0x117e7`/`0x11912` section; independently re-derived byte-for-byte via a
# Ghidra headless probe 2026-09-02, see doc92 續十四). This is the START of
# the CMP EDX,0x2 / gate-check sequence inside FUN_000117e7.
GATE_CHECK_SIGNATURE_HEX = (
    "83fa02750ef64005807508"       # CMP EDX,0x2; JNZ; TEST [EAX+5],0x80; JNZ
    "0fb64026"                      # MOVZX EAX,byte ptr [EAX+0x26]
    "85c0740b56e8c26100" "0083c404eb1f6a016a07"  # TEST EAX,EAX; JZ; ...; CALL 0x17aed; ...
)
GATE_CHECK_GHIDRA_ADDR = 0x11912
# The nearer of the two `MOV EDX,[0x53a45]` sites found inside the same
# function (ghidra 0x1182a and 0x118e2 both work equally well since both
# are well within the same signature-matched code block/page; 0x118e2 is
# used here because it sits immediately before the signature's own start).
UNIT_ARRAY_PTR_INSTR_GHIDRA_ADDR = 0x118e2
# `MOV EDX, dword ptr [imm32]` is opcode `8B 15` (2 bytes) then a 4-byte
# little-endian disp32 -- the disp32 is what the loader may have patched
# and what we need to read LIVE, not trust from the static file.
MOV_ABS_DISP32_OFFSET = 2
UNIT_RECORD_STRIDE = 0x50


def mem_find_signature(instance: str, selector: str, linear: str, bytecount: str,
                        hex_sig: str, ghidra_addr: int, out: Path) -> tuple[list[int], int | None]:
    """Dump <bytecount> bytes at <selector>:<linear> and search for hex_sig
    (a hex string, spaces ignored). Returns (list_of_live_hit_addresses,
    delta) where delta = hit_address - ghidra_addr, only computed (non-None)
    when exactly one hit was found -- a signature that hits 0 or >1 times
    cannot yield a trustworthy delta, the caller must treat that as a
    failed calibration attempt, not silently pick the first hit."""
    path, _size = mem_dump(instance, selector, linear, bytecount, out)
    data = path.read_bytes()
    sig = bytes.fromhex(hex_sig.replace(" ", ""))
    base = int(linear, 16)
    hits: list[int] = []
    idx = 0
    while True:
        idx = data.find(sig, idx)
        if idx == -1:
            break
        hits.append(base + idx)
        idx += 1
    delta = (hits[0] - ghidra_addr) if len(hits) == 1 else None
    return hits, delta


def mem_resolve_ptr(instance: str, selector: str, live_addr: int, disp_offset: int,
                     out: Path) -> tuple[int, int]:
    """Read the instruction bytes at live_addr, extract its little-endian
    disp32 operand at +disp_offset (the LIVE, possibly load-time-patched
    value -- never trust the static file's own disp32 for this), then read
    and return the 4-byte value stored AT that disp32 address (one pointer
    dereference). Returns (disp32_address, pointed_value)."""
    instr_path, _sz = mem_dump(instance, selector, f"{live_addr:x}", "10", out)
    instr_bytes = instr_path.read_bytes()
    if len(instr_bytes) < disp_offset + 4:
        raise RuntimeError(f"only read {len(instr_bytes)} bytes at {live_addr:#x}, need at least {disp_offset + 4} to extract disp32")
    disp32 = int.from_bytes(instr_bytes[disp_offset:disp_offset + 4], "little")
    ptr_out = out.with_name(f"{out.stem}_ptrval{out.suffix}")
    ptr_path, _sz2 = mem_dump(instance, selector, f"{disp32:x}", "4", ptr_out)
    ptr_bytes = ptr_path.read_bytes()
    value = int.from_bytes(ptr_bytes[:4], "little")
    return disp32, value


def mem_read_unit_array(instance: str, selector: str, out_dir: Path,
                         num_records: int = 20, dump_linear: str = "100000",
                         dump_bytecount: str = "200000") -> dict:
    """One-shot: run the full baked-in ring-entry-gate delta-calibration
    recipe and return a dict with every intermediate value plus the decoded
    records, so a caller can inspect where a failed calibration broke down
    rather than just getting an opaque error. See module docstring section
    5 for the full citation trail and the "constants may need recalibrating"
    caveat."""
    out_dir.mkdir(parents=True, exist_ok=True)
    code_dump = out_dir / "code_dump.bin"
    hits, delta = mem_find_signature(instance, selector, dump_linear, dump_bytecount,
                                      GATE_CHECK_SIGNATURE_HEX, GATE_CHECK_GHIDRA_ADDR, code_dump)
    # Cap this the same way cmd_mem_find_signature's own printer does (see
    # its comment) -- the baked-in 34-byte signature makes a huge hit count
    # very unlikely in practice, but the failure mode (flooding the caller's
    # output) is the same shape if it ever happens, so guard it here too
    # rather than assume it can't.
    HIT_LIST_CAP = 20
    hits_shown = [hex(h) for h in hits[:HIT_LIST_CAP]]
    if len(hits) > HIT_LIST_CAP:
        hits_shown.append(f"... and {len(hits) - HIT_LIST_CAP} more")
    result: dict = {"signature_hits": hits_shown, "delta": hex(delta) if delta is not None else None}
    if delta is None:
        result["error"] = (f"signature search found {len(hits)} hits (need exactly 1) -- "
                            f"cannot compute a trustworthy delta; the baked-in signature/constants "
                            f"may need recalibrating for this environment, see module docstring section 5")
        return result

    mov_live = UNIT_ARRAY_PTR_INSTR_GHIDRA_ADDR + delta
    result["mov_edx_live_addr"] = hex(mov_live)
    instr_dump = out_dir / "instr_dump.bin"
    disp32, array_base = mem_resolve_ptr(instance, selector, mov_live, MOV_ABS_DISP32_OFFSET, instr_dump)
    result["ptr_variable_addr"] = hex(disp32)
    result["array_base"] = hex(array_base)

    array_dump = out_dir / "array_dump.bin"
    array_path, array_size = mem_dump(instance, selector, f"{array_base:x}",
                                       f"{num_records * UNIT_RECORD_STRIDE:x}", array_dump)
    data = array_path.read_bytes()
    records = []
    for i in range(num_records):
        rec = data[i * UNIT_RECORD_STRIDE:(i + 1) * UNIT_RECORD_STRIDE]
        if len(rec) < UNIT_RECORD_STRIDE:
            break
        records.append({
            "index": i,
            "acted": rec[0x05],
            "camp": rec[0x06],
            "gate3": rec[0x26],
            "hp_cur": int.from_bytes(rec[0x42:0x44], "little"),
            "hp_max": int.from_bytes(rec[0x40:0x42], "little"),
            "mp_cur": int.from_bytes(rec[0x46:0x48], "little"),
            "mp_max": int.from_bytes(rec[0x44:0x46], "little"),
            "ap": int.from_bytes(rec[0x48:0x4a], "little"),
            "dp": int.from_bytes(rec[0x4a:0x4c], "little"),
            "hit": int.from_bytes(rec[0x4c:0x4e], "little"),
            "dx": int.from_bytes(rec[0x4e:0x50], "little"),
            "raw_hex": rec.hex(),
        })
    result["records"] = records
    return result


# --------------------------------------------------------------------------
# 6. Canonical-file integrity
# --------------------------------------------------------------------------

def verify_canonical(path: str | None) -> tuple[str, int]:
    # path=None -> pass "" through so fd2_dosbox_live_helper.sh resolves its
    # own $HOME/fd2-run default BASH-SIDE (same reasoning as the template's
    # fdother/fdtxt/dato defaulting: a literal "$HOME/fd2-run" string handed
    # in from Python as an already-assigned positional argument would not
    # get re-expanded by bash). A given path is treated as a WINDOWS path
    # (this CLI's normal caller) and translated via to_wsl_path() -- passing
    # a WSL-style "/mnt/c/..." string through as-is also still works since
    # to_wsl_path()/Path.resolve() round-trips it unchanged as long as it
    # exists, but a Windows path is the expected common case here (unlike
    # screenshot()'s Path args, which are always constructed Windows-side).
    if not path:
        wsl_path = ""
    elif path.startswith("/"):
        wsl_path = path  # already WSL-side (e.g. "/mnt/c/..." or "/home/..."), pass through verbatim
    else:
        wsl_path = to_wsl_path(Path(path))
    r = sh("verify-canonical", wsl_path, timeout=15)
    out = r.stdout.strip()
    # verify-canonical uses plain sh() (not sh_checked()) because a nonzero
    # exit is an EXPECTED, meaningful outcome here (MISMATCH), not a tool
    # failure -- but if the .sh script's own die() fired instead (e.g. path
    # not a directory), that message lands on stderr and stdout is empty;
    # fold it in rather than silently reporting a bare nonzero exit code
    # with no explanation (found live 2026-09-02: an argv path mangled by
    # the calling shell before this tool ever saw it produced exactly that
    # silent-failure symptom during testing).
    if not out and r.stderr.strip():
        out = r.stderr.strip()
    return out, r.returncode


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def cmd_launch(args):
    print(f"launching '{args.instance}' -- this call blocks for the WHOLE session (does not return until "
          f"teardown/timeout) -- background this entire invocation yourself, same as dosbox_harness.sh's "
          f"own launch requires", file=sys.stderr)
    rc = launch(args.instance, args.keepalive)
    if rc != 0:
        raise SystemExit(rc)


def cmd_status(args):
    print(status(args.stale_after))


def cmd_teardown(args):
    print(teardown(args.instance))


def cmd_teardown_all(args):
    print(teardown_all())


def cmd_enter_debugger(args):
    print(enter_debugger(args.instance))


def cmd_debugger_cmd(args):
    print(debugger_cmd(args.instance, " ".join(args.text)))


def cmd_debugger_status(args):
    baseline = Path(args.baseline) if args.baseline else None
    print(debugger_status(args.instance, baseline))


def cmd_resume(args):
    print(resume(args.instance))
    if not args.verify:
        return
    import hashlib
    # Retry loop, not just a one-shot warning: live 2026-09-02 testing hit a
    # case where the debugger console's RUN command silently failed to take
    # (this project's long-documented tmux/xdotool key-delivery flakiness,
    # doc58 續七十~續七十七 -- not specific to this command), leaving
    # execution genuinely still paused. A screenshot-diff warning alone just
    # tells the caller "something might be wrong" and makes them redo the
    # work by hand; retrying (re-send resume, re-check) is cheap and turns
    # a transient flake into a non-event most of the time.
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        baseline = DEFAULT_SHOT_DIR / args.instance / f"resume_before_{int(time.time() * 1000)}.png"
        screenshot(args.instance, baseline)
        time.sleep(args.verify_wait)
        after = DEFAULT_SHOT_DIR / args.instance / f"resume_after_{int(time.time() * 1000)}.png"
        screenshot(args.instance, after)
        b_hash = hashlib.md5(baseline.read_bytes()).hexdigest()
        a_hash = hashlib.md5(after.read_bytes()).hexdigest()
        if b_hash != a_hash:
            print(f"OK: screen changed within {args.verify_wait:.1f}s after resume -- execution is genuinely "
                  f"running (attempt {attempt}/{max_attempts})", file=sys.stderr)
            return
        if attempt < max_attempts:
            print(f"screen unchanged on attempt {attempt}/{max_attempts} -- retrying resume "
                  f"(best-effort signal, not proof; a genuinely static screen with no idle animation would "
                  f"also look unchanged -- see module docstring)", file=sys.stderr)
            print(resume(args.instance))
    print(f"WARNING: screen still unchanged after {max_attempts} resume attempts ({args.verify_wait:.1f}s apart) "
          f"-- may genuinely still be paused, or this is a static screen with no idle animation (not proof "
          f"either way on its own, same caveat as wait-settle/debugger-status --baseline)", file=sys.stderr)


def cmd_key(args):
    keys = [resolve_key(k) for k in args.keys]
    if not keys:
        raise SystemExit("no keys given")

    if args.flag_no_response and not args.settle:
        print("WARNING: --flag-no-response has no effect without --settle (there is no settled "
              "'after' frame to compare against a baseline) -- ignoring.", file=sys.stderr)

    baseline = None
    if args.settle and args.flag_no_response:
        baseline = DEFAULT_SHOT_DIR / args.instance / f"baseline_{int(time.time() * 1000)}.png"
        screenshot(args.instance, baseline)

    print(send_keys(args.instance, keys))

    if args.settle:
        settled, raw, no_response = wait_for_settle(args.instance, timeout=args.settle_timeout,
                                                      interval=args.settle_interval, baseline=baseline)
        print(f"settle: {'OK' if settled else 'TIMEOUT'} ({raw})")
        if no_response:
            print("FLAG: NO_RESPONSE -- screen looked identical before and after this key send. "
                  "Best-effort signal, not proof (some keys legitimately produce no visible change) "
                  "-- worth a second look, don't auto-treat as failure.", file=sys.stderr)
        if not settled:
            raise SystemExit(2)
    else:
        wait = args.wait
        if wait is None:
            wait = DEFAULT_WAIT_S
        if wait <= 0:
            print(f"WARNING: --wait {wait} with no --settle sends the next action with "
                  f"effectively zero confirmation the emulator processed this key -- this project's "
                  f"9-round input-reliability investigation (doc58 續七十~續七十七) found exactly this "
                  f"condition can silently drop input.", file=sys.stderr)
        time.sleep(max(wait, 0.0))
        print(f"waited {wait:.2f}s (fixed wall-clock)")


def cmd_screenshot(args):
    out = Path(args.out) if args.out else default_screenshot_path(args.instance, args.label)
    view_out = Path(args.view_out) if args.view_out else None
    result = screenshot(args.instance, out, resize=args.resize, autocrop=args.autocrop, view_out=view_out)
    print(f"raw: {result.raw}")
    if result.view:
        print(f"view: {result.view}")


def cmd_wait_settle(args):
    baseline = Path(args.baseline) if args.baseline else None
    settled, raw, no_response = wait_for_settle(args.instance, timeout=args.timeout,
                                                 interval=args.interval, baseline=baseline)
    print(f"{'SETTLED' if settled else 'TIMEOUT'}: {raw}")
    if no_response:
        print("FLAG: NO_RESPONSE -- screen looked identical before and after (vs --baseline). "
              "Best-effort signal, not proof.", file=sys.stderr)
    if not settled:
        raise SystemExit(2)


def cmd_mem_dump(args):
    out = Path(args.out) if args.out else (DEFAULT_SHOT_DIR / args.instance / f"memdump_{int(time.time())}.bin")
    path, size = mem_dump(args.instance, args.selector, args.linear, args.bytecount, out)
    print(f"out: {path}")
    print(f"size: {size} bytes")
    data = path.read_bytes()
    print(format_hexdump(data))


def cmd_mem_read_unit_record(args):
    size_hex = args.size or DEFAULT_UNIT_RECORD_SIZE_HEX
    out = Path(args.out) if args.out else (DEFAULT_SHOT_DIR / args.instance / f"unitrecord_{args.linear}_{int(time.time())}.bin")
    path, size = mem_dump(args.instance, args.selector, args.linear, size_hex, out)
    data = path.read_bytes()
    print(f"out: {path}")
    print(f"size: {size} bytes (requested 0x{size_hex} = {int(size_hex, 16)})")
    print(format_hexdump(data))
    print()
    print(f"known fields (NOT a complete struct -- only the offsets doc58 續四十 cross-checked "
          f"field-by-field against 0x11912's entry-gate logic; see this module's "
          f"KNOWN_UNIT_RECORD_FIELDS docstring):")
    for offset, label in sorted(KNOWN_UNIT_RECORD_FIELDS.items()):
        if offset < len(data):
            print(f"  +0x{offset:02x} = 0x{data[offset]:02x}  -- {label}")
        else:
            print(f"  +0x{offset:02x} = <out of range, dump only covers 0x{len(data):x} bytes>  -- {label}")


def cmd_mem_find_signature(args):
    out = Path(args.out) if args.out else (DEFAULT_SHOT_DIR / args.instance / f"sigsearch_{int(time.time())}.bin")
    hits, delta = mem_find_signature(args.instance, args.selector, args.linear, args.bytecount,
                                      args.hex_sig, int(args.ghidra_addr, 16), out)
    print(f"dump: {out}")
    print(f"hits: {len(hits)}")
    # Cap printed addresses -- a short/common signature (found live 2026-09-02
    # testing with a 2-byte pattern: 65529 hits in a 10000-byte dump) can
    # otherwise flood the caller's output with tens of thousands of lines.
    # This does not affect correctness: delta is None for any count != 1
    # regardless of how many addresses are shown.
    HIT_PRINT_CAP = 20
    for h in hits[:HIT_PRINT_CAP]:
        print(f"  {h:#x}")
    if len(hits) > HIT_PRINT_CAP:
        print(f"  ... and {len(hits) - HIT_PRINT_CAP} more (use a longer/more distinctive --hex-sig to narrow this down)")
    if delta is not None:
        print(f"delta: {delta:#x}  (= hit_addr - ghidra_addr, only trustworthy because exactly 1 hit)")
    else:
        print(f"delta: N/A -- need exactly 1 hit to compute a trustworthy delta, got {len(hits)}", file=sys.stderr)
        raise SystemExit(2)


def cmd_mem_resolve_ptr(args):
    out = Path(args.out) if args.out else (DEFAULT_SHOT_DIR / args.instance / f"resolveptr_{int(time.time())}.bin")
    live_addr = int(args.live_addr, 16)
    disp_offset = int(args.disp_offset, 16)
    disp32, value = mem_resolve_ptr(args.instance, args.selector, live_addr, disp_offset, out)
    print(f"instruction live addr: {live_addr:#x}")
    print(f"disp32 (pointer variable addr): {disp32:#x}")
    print(f"value at that address (dereferenced): {value:#x}")


def mem_read_global(instance: str, selector: str, ghidra_addr: int, bytecount: int,
                    out_dir: Path, delta: int | None = None) -> dict:
    """Read any documented global by its Ghidra address, via signature delta.

    The executable is flat, so code and data share one load-time delta: calibrate it
    once with the already-proven ring-entry-gate signature, then any global documented
    as a Ghidra/linear address is readable at `ghidra_addr + delta`. That turns every
    address the docs already record into something a live run can check, instead of
    each one needing its own bespoke pointer chase.

    Motivating case (2026-09-03): doc12 disassembled `play_bgm` (0x25977) and proved
    `[0x51a11]` holds the currently-playing track. Reading it live answers "which track
    plays on this screen" as a measurement -- a question doc12 itself flags as unsafe
    to answer by ear ("曲號→場景必須溯源到呼叫點，不能憑曲風印象"), having twice
    recorded a wrong scene label that came from a listening impression.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if delta is None:
        # Calibrate: dumps 200KB through the paused debugger TUI, which is by far the
        # slowest part of this call (minutes, and it gets slower with instances running
        # in parallel).
        code_dump = out_dir / "code_dump.bin"
        hits, delta = mem_find_signature(instance, selector, "100000", "200000",
                                         GATE_CHECK_SIGNATURE_HEX, GATE_CHECK_GHIDRA_ADDR, code_dump)
        result: dict = {"signature_hits": [hex(h) for h in hits[:20]],
                        "delta": hex(delta) if delta is not None else None,
                        "delta_source": "calibrated"}
        if delta is None:
            result["error"] = (f"signature search found {len(hits)} hits (need exactly 1); "
                               f"cannot compute a trustworthy delta")
            return result
    else:
        # Caller supplied a previously calibrated delta, so this reads only `bytecount`
        # bytes. That is the difference between a multi-minute call and a quick one, and
        # it is what makes reading a global at many screens practical.
        #
        # A pinned delta is an ASSUMPTION (that every instance of this binary loads at
        # the same address), so a caller using it MUST include a control whose correct
        # value is already known independently -- e.g. read the BGM track on the title
        # screen, where doc12 proves it is 18. A wrong delta yields garbage, not 18, so
        # the control fails loudly instead of the batch quietly reporting wrong numbers.
        result = {"delta": hex(delta), "delta_source": "pinned"}
    live = ghidra_addr + delta
    result["ghidra_addr"] = hex(ghidra_addr)
    result["live_addr"] = hex(live)
    path, _ = mem_dump(instance, selector, f"{live:x}", f"{bytecount:x}",
                       out_dir / "global_dump.bin")
    raw = path.read_bytes()[:bytecount]
    result["raw_hex"] = raw.hex()
    result["u8"] = raw[0] if raw else None
    if len(raw) >= 4:
        result["u32"] = int.from_bytes(raw[:4], "little")
    return result


def cmd_mem_read_global(args):
    out_dir = Path(args.out_dir) if args.out_dir else (
        DEFAULT_SHOT_DIR / args.instance / f"global_{int(time.time())}")
    r = mem_read_global(args.instance, args.selector, int(args.ghidra_addr, 16),
                        args.bytecount, out_dir,
                        delta=int(args.delta, 16) if args.delta else None)
    if "signature_hits" in r:
        print(f"signature hits: {r['signature_hits']}")
    print(f"delta: {r['delta']} ({r['delta_source']})")
    if "error" in r:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        raise SystemExit(2)
    print(f"ghidra {r['ghidra_addr']} -> live {r['live_addr']}")
    print(f"raw: {r['raw_hex']}")
    print(f"u8={r['u8']}" + (f"  u32={r['u32']}" if "u32" in r else ""))


def cmd_mem_read_unit_array(args):
    out_dir = Path(args.out_dir) if args.out_dir else (DEFAULT_SHOT_DIR / args.instance / f"unitarray_{int(time.time())}")
    result = mem_read_unit_array(args.instance, args.selector, out_dir, num_records=args.num_records)
    print(f"signature hits: {result['signature_hits']}")
    print(f"delta: {result['delta']}")
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        raise SystemExit(2)
    print(f"MOV EDX,[...] live addr: {result['mov_edx_live_addr']}")
    print(f"pointer variable addr: {result['ptr_variable_addr']}")
    print(f"array base: {result['array_base']}")
    print()
    print(f"{'idx':>3}  {'camp':>4}  {'acted':>5}  {'gate3':>5}  {'HP':>9}  {'MP':>9}  {'AP':>4}  {'DP':>4}  {'HIT':>4}  {'DX':>4}")
    for rec in result["records"]:
        hp = f"{rec['hp_cur']}/{rec['hp_max']}"
        mp = f"{rec['mp_cur']}/{rec['mp_max']}"
        print(f"{rec['index']:>3}  {rec['camp']:#04x}  {rec['acted']:#05x}  {rec['gate3']:#05x}  "
              f"{hp:>9}  {mp:>9}  {rec['ap']:>4}  {rec['dp']:>4}  {rec['hit']:>4}  {rec['dx']:>4}")
    print()
    print(f"raw dump dir: {out_dir}")


def cmd_verify_canonical(args):
    out, rc = verify_canonical(args.path)
    print(out)
    raise SystemExit(rc)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("launch", help="launch an isolated dosbox-x instance (wraps dosbox_harness.sh launch; long-lived foreground, background it yourself)")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--keepalive", type=int, default=None, help="seconds to hold the instance alive (default: dosbox_harness.sh's own default, 3600)")
    sp.set_defaults(func=cmd_launch)

    sp = sub.add_parser("status", help="list all dosbox_harness.sh instances, flagging stale-uptime ones")
    sp.add_argument("--stale-after", type=int, default=None,
                     help="seconds; flag instances at/above this uptime as STALE (default: dosbox_harness.sh's "
                          "own KEEPALIVE_DEFAULT, 3600s) -- advisory only, never auto-tears-down anything")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("teardown", help="kill one instance (passthrough to dosbox_harness.sh)")
    sp.add_argument("--instance", required=True)
    sp.set_defaults(func=cmd_teardown)

    sp = sub.add_parser("teardown-all", help="kill every dosbox_harness.sh instance")
    sp.set_defaults(func=cmd_teardown_all)

    sp = sub.add_parser("enter-debugger", help="send Alt+Pause to toggle the ncurses debugger TUI (passthrough)")
    sp.add_argument("--instance", required=True)
    sp.set_defaults(func=cmd_enter_debugger)

    sp = sub.add_parser("debugger-cmd", help="type a debugger console command + Enter (passthrough)")
    sp.add_argument("--instance", required=True)
    sp.add_argument("text", nargs="+")
    sp.set_defaults(func=cmd_debugger_cmd)

    sp = sub.add_parser("debugger-status", help="best-effort check of whether the debugger TUI is currently showing")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--baseline", default=None,
                     help="path to a screenshot taken at a known moment (e.g. when the debugger was entered); "
                          "if given, adds a SCREEN_CHECK cross-check for the documented stale-pane blind spot")
    sp.set_defaults(func=cmd_debugger_status)

    sp = sub.add_parser("resume", help="reliably resume from the debugger via its own RUN console command "
                                        "(fixes Alt+Pause's flaky 'exit' direction, see module docstring section 5); "
                                        "no-op if the pane doesn't currently look paused")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--verify", action="store_true",
                     help="take 2 screenshots --verify-wait apart after resuming; if pixel-identical, "
                          "automatically RETRY resume (up to 3 attempts total) before warning on stderr -- "
                          "best-effort signal, not proof (a genuinely static screen with no idle animation "
                          "will also look unchanged, and would exhaust all retries without ever being 'wrong')")
    sp.add_argument("--verify-wait", type=float, default=1.5)
    sp.set_defaults(func=cmd_resume)

    sp = sub.add_parser("key", help="send one or more keys, confirmed by a wait or a settle-poll -- never blind")
    sp.add_argument("--instance", required=True)
    sp.add_argument("keys", nargs="+", help="xdotool key name(s), or an alias: confirm/cancel/up/down/left/right/tab/space")
    sp.add_argument("--wait", type=float, default=None,
                     help=f"fixed wall-clock seconds to wait after sending (default {DEFAULT_WAIT_S}s)")
    sp.add_argument("--settle", action="store_true",
                     help="instead of a fixed wait, poll screenshots after sending until 2 consecutive match")
    sp.add_argument("--settle-timeout", type=float, default=10.0)
    sp.add_argument("--settle-interval", type=float, default=0.25)
    sp.add_argument("--flag-no-response", action="store_true",
                     help="requires --settle: capture a baseline screenshot before sending, and flag "
                          "(stderr + exit unaffected) if the settled 'after' frame is pixel-identical "
                          "to it -- a best-effort 'this key produced no visible change' signal, not "
                          "proof the key was dropped (costs one extra screenshot per call)")
    sp.set_defaults(func=cmd_key)

    sp = sub.add_parser("screenshot", help="save a raw PNG (default under .wsl_build/, not docs/figures/); "
                                            "--out is always the untouched raw capture")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--out", default=None, help="explicit RAW output path; default: .wsl_build/dosbox_live_helper/<instance>/<timestamp>[_label].png")
    sp.add_argument("--label", default=None)
    sp.add_argument("--resize", default=None,
                     help="convert -resize geometry for a SEPARATE view copy (fits-within/preserves aspect); "
                          "no forced default on this tool -- see module docstring point 1 for why")
    sp.add_argument("--autocrop", action="store_true",
                     help="two-step: (1) exact crop to the real dosbox-x window bounds via a fresh xdotool "
                          "geometry query (always safe, verified 2026-09-02), then (2) an optional best-effort "
                          "fuzzy trim on top for dosbox-x's own persistent GUI menu bar -- only verified on 3 "
                          "screen types so far (pre-title cutscene, title menu, load-save list), see module "
                          "docstring point 1")
    sp.add_argument("--view-out", default=None,
                     help="explicit path for the processed view copy; default: <out stem>_view<out suffix>")
    sp.set_defaults(func=cmd_screenshot)

    sp = sub.add_parser("wait-settle", help="standalone: poll until 2 consecutive screenshots match, or time out "
                                             "(mitigation, not a fix, for known input-reliability issue)")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--timeout", type=float, default=10.0)
    sp.add_argument("--interval", type=float, default=0.25)
    sp.add_argument("--baseline", default=None,
                     help="path to a screenshot taken before the key send; if given, flags "
                          "response=NO_RESPONSE when the settled frame matches it exactly")
    sp.set_defaults(func=cmd_wait_settle)

    mem = sub.add_parser("mem", help="live-memory-read primitives -- wraps the debugger's MEMDUMPBIN, "
                                      "requires the debugger TUI already entered (see enter-debugger/debugger-status)")
    msub = mem.add_subparsers(dest="mem_cmd", required=True)

    sp = msub.add_parser("dump", help="raw MEMDUMPBIN wrapper -- dumps <bytecount> bytes at <selector>:<linear> and hexdumps them")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--selector", required=True, help="flat selector, hex, NO leading 0x (e.g. 0170) -- "
                                                        "read this from the debugger's Register Overview/GDT; "
                                                        "0/empty is refused (known garbage-not-error footgun, see module docstring point 3)")
    sp.add_argument("--linear", required=True, help="linear address, hex, no leading 0x")
    sp.add_argument("--bytecount", required=True, help="byte count, hex, no leading 0x")
    sp.add_argument("--out", default=None, help="output .bin path; default under .wsl_build/dosbox_live_helper/<instance>/")
    sp.set_defaults(func=cmd_mem_dump)

    sp = msub.add_parser("read-unit-record", help="convenience wrapper: dumps a battle-unit record (default 0x32=50 bytes, "
                                                    "doc58 續四十's validated size) and decodes the known entry-gate fields")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--selector", required=True, help="see `mem dump --selector`")
    sp.add_argument("--linear", required=True, help="linear address of the record start, hex, no leading 0x")
    sp.add_argument("--size", default=None, help=f"record size, hex, no leading 0x (default {DEFAULT_UNIT_RECORD_SIZE_HEX} = 50 bytes)")
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_mem_read_unit_record)

    sp = msub.add_parser("find-signature", help="generic delta calibration: dump a region, search for a hex "
                                                  "byte signature, compute delta = hit_addr - ghidra_addr (only "
                                                  "if exactly 1 hit) -- reusable for any future signature/delta "
                                                  "need, not specific to the unit array")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--selector", required=True, help="see `mem dump --selector`")
    sp.add_argument("--linear", required=True, help="start of the region to dump, hex, no leading 0x")
    sp.add_argument("--bytecount", required=True, help="how much to dump, hex, no leading 0x (e.g. 200000 for 2MB)")
    sp.add_argument("--hex-sig", required=True, help="signature bytes as a hex string, spaces allowed, e.g. \"83fa02 750e\"")
    sp.add_argument("--ghidra-addr", required=True, help="the signature's known static Ghidra address, hex, no leading 0x")
    sp.add_argument("--out", default=None, help="output .bin path for the raw dump; default under .wsl_build/dosbox_live_helper/<instance>/")
    sp.set_defaults(func=cmd_mem_find_signature)

    sp = msub.add_parser("resolve-ptr", help="generic pointer chase: read an instruction's LIVE (load-time-"
                                               "patched) disp32 operand and dereference it once -- reusable for "
                                               "any future 'find the real base of a pointer-indirected structure' "
                                               "need, not specific to the unit array")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--selector", required=True, help="see `mem dump --selector`")
    sp.add_argument("--live-addr", required=True, help="live address of the instruction (e.g. computed via "
                                                         "find-signature's delta + a known Ghidra address), hex, no leading 0x")
    sp.add_argument("--disp-offset", default="2", help="byte offset from --live-addr to the 4-byte little-endian "
                                                         "disp32 operand, hex, no leading 0x (default 2 = opcode "
                                                         "`8B 15` for MOV r32,[imm32])")
    sp.add_argument("--out", default=None)
    sp.set_defaults(func=cmd_mem_resolve_ptr)

    sp = msub.add_parser("read-global", help="read any documented global by its Ghidra address: calibrates the "
                                              "load-time delta with the proven ring-entry-gate signature, then "
                                              "dumps <bytecount> bytes at ghidra_addr+delta. Turns every address "
                                              "the docs already record into something a live run can check, e.g. "
                                              "doc12's [0x51a11] = currently-playing BGM track")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--selector", required=True, help="see `mem dump --selector`")
    sp.add_argument("--ghidra-addr", required=True, help="hex, e.g. 51a11")
    sp.add_argument("--bytecount", type=int, default=4)
    sp.add_argument("--delta", default=None,
                    help="hex load-time delta from a previous calibration; skips the 200KB "
                         "signature dump, turning a multi-minute call into a quick one. It is "
                         "an ASSUMPTION that instances share a load address, so any batch using "
                         "it must include a control read whose correct value is known "
                         "independently (e.g. BGM track on the title screen is 18, doc12)")
    sp.add_argument("--out-dir", default=None)
    sp.set_defaults(func=cmd_mem_read_global)

    sp = msub.add_parser("read-unit-array", help="domain-specific one-shot: runs the full baked-in ring-entry-"
                                                   "gate delta-calibration recipe (find-signature -> resolve-ptr "
                                                   "-> dump+decode N records) in a single call -- see module "
                                                   "docstring section 5 for the citation trail and the "
                                                   "'constants may need recalibrating' caveat")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--selector", required=True, help="see `mem dump --selector`")
    sp.add_argument("--num-records", type=int, default=20, help="how many 0x50-byte records to dump+decode from the array base (default 20)")
    sp.add_argument("--out-dir", default=None, help="directory for the raw dump files; default under .wsl_build/dosbox_live_helper/<instance>/")
    sp.set_defaults(func=cmd_mem_read_unit_array)

    sp = sub.add_parser("verify-canonical", help="read-only md5 check of FD2.EXE (+.pristine_bak) vs the known-pristine "
                                                  "hash -- NEVER writes/restores anything")
    sp.add_argument("--path", default=None, help="default: $HOME/fd2-run on the WSL side; accepts either a "
                                                   "Windows path (converted automatically) or a WSL-side path "
                                                   "starting with '/' (passed through verbatim)")
    sp.set_defaults(func=cmd_verify_canonical)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    # RuntimeError from sh_checked()/mem_dump() etc. already carries a full,
    # specific explanation (the .sh script's own die() message, or an
    # unexpected-empty-output diagnosis) -- print just that message and exit
    # nonzero, instead of a raw Python traceback (found live 2026-09-02
    # during a full tool audit: every error path DID surface the right
    # information, just buried under traceback noise a caller has to scroll
    # past). SystemExit is deliberately NOT caught here -- cmd_* functions
    # that raise SystemExit directly (e.g. `key --settle` on TIMEOUT) already
    # produce their own intentional message + exit code and must pass through
    # unchanged.
    try:
        args.func(args)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
