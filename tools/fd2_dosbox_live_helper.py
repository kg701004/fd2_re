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

Live memory read (debugger must already be entered -- see debugger-status):
    python tools/fd2_dosbox_live_helper.py enter-debugger --instance myrun
    python tools/fd2_dosbox_live_helper.py debugger-status --instance myrun
    python tools/fd2_dosbox_live_helper.py mem dump --instance myrun --selector 0170 --linear 26DF88 --bytecount 32
    python tools/fd2_dosbox_live_helper.py mem read-unit-record --instance myrun --selector 0170 --linear 26DF88

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


def status() -> str:
    return sh("status", timeout=15).stdout.strip()


def teardown(instance: str) -> str:
    return sh_checked("teardown", instance, timeout=30)


def teardown_all() -> str:
    return sh_checked("teardown-all", timeout=60)


def enter_debugger(instance: str) -> str:
    return sh_checked("enter-debugger", instance, timeout=15)


def debugger_cmd(instance: str, text: str) -> str:
    return sh_checked("debugger-cmd", instance, text, timeout=15)


def debugger_status(instance: str) -> str:
    return sh_checked("debugger-status", instance, timeout=15)


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
                     tmp_prefix: Path | None = None) -> tuple[bool, str]:
    """See fd2_dosbox_live_helper.sh's wait-settle: polls via repeated
    dosbox_harness.sh screenshot calls, stops when 2 CONSECUTIVE shots
    md5-match. MITIGATION for, not a fix to, the project's known input-
    reliability problem -- see module docstring."""
    prefix = tmp_prefix or (DEFAULT_SHOT_DIR / instance / f"settle_{int(time.time() * 1000)}")
    max_tries = max(2, int(round(timeout / interval)))
    r = sh("wait-settle", instance, to_wsl_path(prefix), str(max_tries), str(interval),
           timeout=int(timeout) + 20)
    out = r.stdout.strip()
    if not out.startswith("SETTLED") and r.stderr.strip():
        out = f"{out} STDERR: {r.stderr.strip()}" if out else r.stderr.strip()
    return out.startswith("SETTLED"), out


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
# 5. Canonical-file integrity
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
    print(status())


def cmd_teardown(args):
    print(teardown(args.instance))


def cmd_teardown_all(args):
    print(teardown_all())


def cmd_enter_debugger(args):
    print(enter_debugger(args.instance))


def cmd_debugger_cmd(args):
    print(debugger_cmd(args.instance, " ".join(args.text)))


def cmd_debugger_status(args):
    print(debugger_status(args.instance))


def cmd_key(args):
    keys = [resolve_key(k) for k in args.keys]
    if not keys:
        raise SystemExit("no keys given")
    print(send_keys(args.instance, keys))

    if args.settle:
        settled, raw = wait_for_settle(args.instance, timeout=args.settle_timeout, interval=args.settle_interval)
        print(f"settle: {'OK' if settled else 'TIMEOUT'} ({raw})")
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
    settled, raw = wait_for_settle(args.instance, timeout=args.timeout, interval=args.interval)
    print(f"{'SETTLED' if settled else 'TIMEOUT'}: {raw}")
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

    sp = sub.add_parser("status", help="list all dosbox_harness.sh instances")
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
    sp.set_defaults(func=cmd_debugger_status)

    sp = sub.add_parser("key", help="send one or more keys, confirmed by a wait or a settle-poll -- never blind")
    sp.add_argument("--instance", required=True)
    sp.add_argument("keys", nargs="+", help="xdotool key name(s), or an alias: confirm/cancel/up/down/left/right/tab/space")
    sp.add_argument("--wait", type=float, default=None,
                     help=f"fixed wall-clock seconds to wait after sending (default {DEFAULT_WAIT_S}s)")
    sp.add_argument("--settle", action="store_true",
                     help="instead of a fixed wait, poll screenshots after sending until 2 consecutive match")
    sp.add_argument("--settle-timeout", type=float, default=10.0)
    sp.add_argument("--settle-interval", type=float, default=0.25)
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

    sp = sub.add_parser("verify-canonical", help="read-only md5 check of FD2.EXE (+.pristine_bak) vs the known-pristine "
                                                  "hash -- NEVER writes/restores anything")
    sp.add_argument("--path", default=None, help="default: $HOME/fd2-run on the WSL side; accepts either a "
                                                   "Windows path (converted automatically) or a WSL-side path "
                                                   "starting with '/' (passed through verbatim)")
    sp.set_defaults(func=cmd_verify_canonical)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
