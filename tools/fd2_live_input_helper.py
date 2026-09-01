#!/usr/bin/env python3
"""FD2-LIVE-INPUT-HELPER: thin, mechanical primitives for driving the
remake's own `fd2-linux-verify` binary via genuine xdotool keyboard input,
under Xvfb, with NO debug env-var hooks -- for M5 Phase 4 "normal
playthrough" live-verification rounds (docs/knowledge-base/92-m5-normal-
playthrough-log.md).

WHAT THIS IS -- AND, IMPORTANTLY, WHAT IT IS NOT
--------------------------------------------------------------------
This is a "how do I reliably do X" toolbox, not an autoplayer. It never
decides WHICH unit to move, WHO to attack, or WHEN to retreat -- it only
makes the mechanical parts of live-driving the game cheap and repeatable:
launching/tearing down an isolated instance, finding the right window to
send keys to, sending a key with a real wait/confirmation instead of
firing blind, taking a screenshot, and doing tile-distance/weapon-range
ARITHMETIC (not target selection) against real map/unit JSON. If you find
yourself wanting this tool to also decide what move is good, that decision
belongs in the calling session/human, not here -- see the task description
this tool was built from for the explicit scope line.

Every primitive here directly codifies a documented pitfall from
docs/knowledge-base/98-tooling-infrastructure.md's "remake 側(fd2-linux-
verify, Ebiten/GLFW)在無 WM 的 Xvfb 下的 xdotool 合成鍵盤輸入可靠性" section
and docs/knowledge-base/92-m5-normal-playthrough-log.md:
  1. window id must be re-queried fresh every time (a stale id silently
     swallows input -- no error, no effect. window_id()/`window-id`).
  2. a key must never be sent and immediately trusted -- either wait a real
     wall-clock duration, or poll screenshots until the UI visibly settles
     (send_key()/`key`, wait_for_settle()/`wait-settle`).
  3. "visually adjacent" on this diamond/brick-tile art style is not the
     same as logically in weapon range -- AtkMin/AtkMax is real per-unit
     data (remake/internal/battle/move.go's InAttackRange), not a fixed
     "4 neighbours" rule (in_attack_range()/`grid range`).

ARCHITECTURE -- why there are TWO files (this one + fd2_live_input_helper.sh)
--------------------------------------------------------------------
All WSL-side logic (Xvfb/process lifecycle, xwininfo/xdotool/import calls,
the registry of running instances) lives in the companion
tools/fd2_live_input_helper.sh, invoked here as real argv (`wsl -d Ubuntu
bash <script.sh> <subcommand> <arg1> <arg2> ...`), NEVER as a Python-built
multi-statement `bash -c "stmt1; stmt2"` string. This split exists because
of a genuine, reproducible gotcha found while building this tool (2026-09-
01, see fd2_live_input_helper.sh's header comment for the full repro): a
multi-statement script passed as a single `-c` STRING argument through
wsl.exe silently loses shell variable state between statements (`bash -c
'x=hello; echo got:$x'` -- invoked via a real Python subprocess.run argv
list, not a shell string, ruling out any Windows/MSYS quoting cause --
prints `got:`, empty; `declare -p x` in the very same `-c` string DOES show
`x` correctly assigned, so the assignment itself works, only the later
*use* of it is lost). Piping the identical script to a bare `wsl -d Ubuntu
bash` via stdin, or -- the pattern used throughout this project's existing
tools (tools/dosbox_harness.sh, tools/dosbox_diff_harness.sh) and now made
explicit here -- writing it to a real `.sh` file invoked with plain argv,
both work correctly, including real positional-argument passing. This is a
new addition to doc98 (see that file's dated section for the write-up);
every WSL-side call in this module goes through wsl_argv_run()/sh() below,
which always uses the real-argv form for exactly this reason.

USAGE
-----
Session lifecycle (one instance = one Xvfb display + one fd2-linux-verify
process, isolated from any other instance including another agent's
canonical `:99`/`dbg`/`diffharness`/etc session -- see `pick-port`):
    python tools/fd2_live_input_helper.py launch --instance myrun
    python tools/fd2_live_input_helper.py status
    python tools/fd2_live_input_helper.py teardown --instance myrun

Window targeting + key delivery (always fresh, always confirmed):
    python tools/fd2_live_input_helper.py window-id --instance myrun
    python tools/fd2_live_input_helper.py key --instance myrun confirm --wait 0.5
    python tools/fd2_live_input_helper.py key --instance myrun Down Down --settle

Screenshot:
    python tools/fd2_live_input_helper.py screenshot --instance myrun --label title

Grid/range arithmetic (no live instance needed -- pure data lookup):
    python tools/fd2_live_input_helper.py grid distance --a 7,20 --b 10,21
    python tools/fd2_live_input_helper.py grid range \\
        --map-units-json remake/assets/maps/map0/map0_units.json \\
        --unit-index 0 --target-x 2 --target-y 3
    python tools/fd2_live_input_helper.py grid dump-map \\
        --map-units-json remake/assets/maps/map0/map0_units.json

See docs/knowledge-base/98-tooling-infrastructure.md for the full design
writeup and docs/knowledge-base/92-m5-normal-playthrough-log.md for the
playthrough round this tool exists to make repeatable.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
SH_SCRIPT_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "fd2_live_input_helper.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
DEFAULT_REMAKE_DIR = REPO_ROOT / "remake"
DEFAULT_SHOT_DIR = REPO_ROOT / ".wsl_build" / "live_input_helper"
DEFAULT_WAIT_S = 0.3  # doc92's general per-key gap floor; command-ring cases want 0.4-0.6s (caller's call, via --wait)
DEFAULT_KEY_GAP_S = 0.15  # doc92: 0.15-0.3s between keys in a batch
DEFAULT_SCREENSHOT_RESIZE = "640x400"  # the game's own logical canvas size (main.go's defaultWindowSize) --
# the captured window is usually a 2x/3x upscale of this with zero added information, so shrinking back
# down to native size cuts vision-token cost for whoever reads the PNG without losing any real detail.
# Pass --resize "" to get the raw, un-shrunk capture (e.g. for a higher-fidelity doc/commit screenshot).


# --------------------------------------------------------------------------
# WSL plumbing -- always real argv, never a multi-statement -c string
# (see module docstring's ARCHITECTURE section for why).
# --------------------------------------------------------------------------

def to_wsl_path(windows_path: Path) -> str:
    p = str(windows_path.resolve()).replace("\\", "/")
    drive, rest = p.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


def wsl_argv_run(argv: list[str], timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess:
    """Run `wsl -d Ubuntu <argv...>` as a real argument list (never a joined
    shell string -- see module docstring). check defaults to False: wsl.exe
    itself has been observed (both here and in tools/dosbox_diff_harness.py)
    to be an unreliable narrator of its own exit code; callers verify
    success from stdout content, not the return code alone."""
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    full = ["wsl", "-d", "Ubuntu"] + argv
    return subprocess.run(full, capture_output=True, text=True, timeout=timeout, env=env, check=check)


def sh(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Invoke tools/fd2_live_input_helper.sh <args...> over WSL as real argv."""
    argv = ["bash", SH_SCRIPT_WSL] + [str(a) for a in args]
    return wsl_argv_run(argv, timeout=timeout)


def sh_checked(*args: str, timeout: int = 30) -> str:
    """Like sh(), but raises with full stdout+stderr if the call produced no
    stdout or the .sh script's own `die()` fired (stderr starts with
    'ERROR:'). Use this for any primitive that must never fail silently
    (window lookup, key send, launch, teardown) -- exactly the class of
    "silent no-op" failure doc98 documents for a stale window id."""
    r = sh(*args, timeout=timeout)
    out = r.stdout.strip()
    if not out or "ERROR:" in r.stderr:
        raise RuntimeError(
            f"fd2_live_input_helper.sh {' '.join(args)} failed "
            f"(rc={r.returncode})\nSTDOUT: {out!r}\nSTDERR: {r.stderr.strip()!r}"
        )
    return out


# --------------------------------------------------------------------------
# 1. Session lifecycle
# --------------------------------------------------------------------------

def launch(instance: str, remake_dir: Path, campaign: str, mute: bool,
           fdother: str | None, fdtxt: str | None, dato: str | None,
           extra_env: list[str]) -> str:
    """Launch an isolated Xvfb + fd2-linux-verify instance. No FD2_SHOT_*/
    FD2_CAMP_* debug hooks are set unless the caller explicitly passes them
    via extra_env -- this is the whole point of the M5 Phase 4 exercise.

    fdother/fdtxt/dato: None -> resolve to the canonical $HOME/fd2-run/*.DAT
    on the WSL side (bash-side default, see fd2_live_input_helper.sh's
    cmd_launch -- NOT resolved here, because a literal "$HOME" string
    handed to bash as an already-assigned positional parameter would not
    get re-expanded); "-" -> omit that env var entirely; any other string
    -> used verbatim as the path.
    """
    args = [
        "launch", instance, to_wsl_path(remake_dir), campaign, "1" if mute else "0",
        "-" if fdother == "-" else (fdother or ""),
        "-" if fdtxt == "-" else (fdtxt or ""),
        "-" if dato == "-" else (dato or ""),
    ] + list(extra_env)
    return sh_checked(*args, timeout=60)


def status() -> str:
    r = sh("status", timeout=15)
    return r.stdout.strip()


def teardown(instance: str) -> str:
    return sh_checked("teardown", instance, timeout=30)


def teardown_all() -> str:
    return sh_checked("teardown-all", timeout=60)


# --------------------------------------------------------------------------
# 2. Reliable window targeting -- ALWAYS a fresh query, never cached
# --------------------------------------------------------------------------

def window_id(instance: str) -> str:
    """Fresh xwininfo -root -tree query every call (doc98: a stale id from
    an earlier call, or from a since-restarted window, silently swallows
    every keystroke sent to it -- no error, no visible effect). Raises if
    no window is currently found, rather than returning a stale/guessed id."""
    return sh_checked("window-id", instance, timeout=15)


# --------------------------------------------------------------------------
# 3. Reliable key delivery -- never blind, always waited/confirmed
# --------------------------------------------------------------------------

KEY_ALIASES = {
    "confirm": "Return", "enter": "Return", "return": "Return",
    "cancel": "Escape", "esc": "Escape", "escape": "Escape",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "tab": "Tab", "space": "space",
}


def resolve_key(token: str) -> str:
    return KEY_ALIASES.get(token.lower(), token)


def send_key(instance: str, key: str) -> None:
    """Send exactly one key. Always does its own fresh window-id lookup
    (via fd2_live_input_helper.sh's find_window_id, called inside send-key)
    and raises loudly if no window is found or xdotool itself fails --
    this function is the single choke point that makes "never send a key
    blind with zero confirmation of reaching a real window" true; callers
    still need send_key_confirmed()/`key` for the wait/settle half of that
    guarantee (window existing != the UI having processed the key)."""
    sh_checked("send-key", instance, key, timeout=15)


def wait_for_settle(instance: str, timeout: float = 10.0, interval: float = 0.25,
                     tmp_prefix: Path | None = None) -> tuple[bool, str]:
    """Generic "wait for the UI to stop animating" primitive: repeatedly
    screenshots and stops as soon as two CONSECUTIVE shots are pixel-
    identical (or times out). Deliberately scene-agnostic -- doesn't
    hardcode which screens are throttled (doc98 continuation: church
    menu/roster transitions are frame-throttled at Draw() level; doc92:
    the battle command ring is too) -- it just detects "stopped changing"
    in general. Returns (settled: bool, raw_sh_output: str).

    TRADEOFF vs a fixed --wait duration (see `key`'s docstring): this is
    more robust when you don't know the exact settle time for a screen you
    haven't characterized yet, but costs one full screenshot round-trip per
    poll (interval-bounded, not free) and can time out on any effectively-
    endless animation loop -- a fixed wait floor derived from doc92's
    empirical 0.4-0.6s command-ring / 0.15-0.3s general-key numbers is
    cheaper once a screen's timing is already known. Neither is "more
    correct" in general; pick per call."""
    prefix = tmp_prefix or (DEFAULT_SHOT_DIR / instance / f"settle_{int(time.time() * 1000)}")
    max_tries = max(2, int(round(timeout / interval)))
    r = sh("wait-settle", instance, to_wsl_path(prefix), str(max_tries), str(interval),
           timeout=int(timeout) + 20)
    out = r.stdout.strip()
    return out.startswith("SETTLED"), out


# --------------------------------------------------------------------------
# 4. Screenshot capture
# --------------------------------------------------------------------------

def screenshot(instance: str, out: Path, resize: str | None = DEFAULT_SCREENSHOT_RESIZE,
               autocrop: bool = False) -> Path:
    """Fresh window-id lookup + `import -window <id>`, saved to a caller-
    specified path (default: a scratch dir under .wsl_build/, NOT
    docs/figures/ -- ad-hoc test-run screenshots shouldn't land in
    committed documentation by default; pass --out explicitly to promote
    one into docs/figures/ once it's actually worth keeping).

    resize: geometry string passed to `convert -resize` (fits within,
    preserves aspect -- not a crop), default DEFAULT_SCREENSHOT_RESIZE
    (the game's native 640x400 logical canvas). Pass None/"" for the raw,
    un-shrunk capture -- worth doing for a screenshot going into docs/a
    commit as evidence, not for a routine in-the-loop decision check.

    autocrop: `convert -fuzz 3% -trim +repage` after resize -- removes a
    uniform-color (in practice: black) border, a safe no-op on a screen
    that already fills the frame. CONFIRMED correct so far only for the
    battle/map screen (2026-09-01: it genuinely renders into just ~79%
    width x ~50% height of its own canvas, cross-checked at two capture
    resolutions) -- NOT verified across every screen type (menus/shop/
    dialogue), so default False; turn on deliberately once you know the
    screen you're capturing has this margin, not as a blanket default."""
    out.parent.mkdir(parents=True, exist_ok=True)
    sh_checked("screenshot", instance, to_wsl_path(out), resize or "", "1" if autocrop else "0", timeout=20)
    return out


def default_screenshot_path(instance: str, label: str | None) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    tag = f"_{label}" if label else ""
    return DEFAULT_SHOT_DIR / instance / f"{ts}{tag}.png"


# --------------------------------------------------------------------------
# 5. Grid/coordinate helpers -- pure data lookup + arithmetic, no live
#    instance needed, and NO tactical decision-making (see module docstring)
# --------------------------------------------------------------------------

def manhattan(ax: int, ay: int, bx: int, by: int) -> int:
    return abs(ax - bx) + abs(ay - by)


def in_attack_range(ux: int, uy: int, tx: int, ty: int,
                     atk_min: int, atk_max: int) -> tuple[int, bool]:
    """Mirrors remake/internal/battle/move.go's InAttackRange exactly:
    Manhattan distance must fall in [AtkMin, AtkMax]; AtkMin/AtkMax of 0
    (unset in the source data) each default to 1, i.e. "adjacent only" --
    same rule the Go code uses, not a guess. Returns (distance, in_range).
    This ANSWERS "is X in range of Y" -- it deliberately does not choose a
    target; that choice stays with the caller."""
    d = manhattan(ux, uy, tx, ty)
    amin = atk_min or 1
    amax = atk_max or 1
    return d, (amin <= d <= amax)


def load_map_units(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_unit(data: dict, index: int | None, fig: int | None) -> dict:
    units = data["units"]
    if index is not None:
        if not (0 <= index < len(units)):
            raise IndexError(f"--unit-index {index} out of range (units has {len(units)} entries)")
        return units[index]
    if fig is not None:
        for u in units:
            if u.get("fig") == fig:
                return u
        raise KeyError(f"no unit in units[] with fig={fig}")
    raise ValueError("need --unit-index or --unit-fig (or --unit-x/--unit-y for a manual/own-party unit)")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _parse_xy(s: str) -> tuple[int, int]:
    x, y = s.split(",")
    return int(x), int(y)


def cmd_launch(args):
    out = launch(args.instance, Path(args.remake_dir), args.campaign, not args.no_mute,
                 args.fdother, args.fdtxt, args.dato, args.extra_env or [])
    print(out)


def cmd_status(args):
    print(status())


def cmd_teardown(args):
    print(teardown(args.instance))


def cmd_teardown_all(args):
    print(teardown_all())


def cmd_window_id(args):
    print(window_id(args.instance))


def cmd_key(args):
    keys = [resolve_key(k) for k in args.keys]
    if not keys:
        raise SystemExit("no keys given")
    for i, k in enumerate(keys):
        send_key(args.instance, k)
        print(f"sent: {k}")
        if i < len(keys) - 1:
            time.sleep(args.gap)

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
                  f"effectively zero confirmation the UI processed this key -- doc92/doc98 "
                  f"both document silently-dropped input under exactly this condition.",
                  file=sys.stderr)
        time.sleep(max(wait, 0.0))
        print(f"waited {wait:.2f}s (fixed wall-clock)")


def cmd_screenshot(args):
    out = Path(args.out) if args.out else default_screenshot_path(args.instance, args.label)
    screenshot(args.instance, out, resize=args.resize, autocrop=args.autocrop)
    print(str(out))


def cmd_wait_settle(args):
    settled, raw = wait_for_settle(args.instance, timeout=args.timeout, interval=args.interval)
    print(f"{'SETTLED' if settled else 'TIMEOUT'}: {raw}")
    if not settled:
        raise SystemExit(2)


def cmd_grid_distance(args):
    ax, ay = _parse_xy(args.a)
    bx, by = _parse_xy(args.b)
    d = manhattan(ax, ay, bx, by)
    print(json.dumps({"a": [ax, ay], "b": [bx, by], "manhattan_distance": d}, indent=2))


def cmd_grid_range(args):
    if args.unit_x is not None and args.unit_y is not None:
        ux, uy = args.unit_x, args.unit_y
        atk_min = args.atk_min or 0
        atk_max = args.atk_max or 0
        source = "manual (--unit-x/--unit-y, atk_min/atk_max from flags, 0 defaults to 1)"
    else:
        if not args.map_units_json:
            raise SystemExit("need --map-units-json (with --unit-index/--unit-fig/--own-deploy-index), "
                              "or --unit-x/--unit-y for a manual/own-party unit")
        data = load_map_units(Path(args.map_units_json))
        if args.own_deploy_index is not None:
            rec = data["own_deploy"][args.own_deploy_index]
            ux, uy = rec["x"], rec["y"]
            atk_min = args.atk_min if args.atk_min is not None else 0
            atk_max = args.atk_max if args.atk_max is not None else 0
            source = (f"own_deploy[{args.own_deploy_index}] -- own_deploy carries no weapon stats, "
                      f"atk_min/atk_max must come from --atk-min/--atk-max (0 defaults to 1 if omitted)")
        else:
            rec = find_unit(data, args.unit_index, args.unit_fig)
            ux, uy = rec["x"], rec["y"]
            atk_min = args.atk_min if args.atk_min is not None else rec.get("atk_min", 0)
            atk_max = args.atk_max if args.atk_max is not None else rec.get("atk_max", 0)
            source = f"units[] fig={rec.get('fig')} camp={rec.get('camp')} cls_name={rec.get('cls_name')!r}"

    d, in_range = in_attack_range(ux, uy, args.target_x, args.target_y, atk_min, atk_max)
    print(json.dumps({
        "unit_xy": [ux, uy],
        "target_xy": [args.target_x, args.target_y],
        "atk_min_raw": atk_min, "atk_max_raw": atk_max,
        "atk_min_effective": atk_min or 1, "atk_max_effective": atk_max or 1,
        "manhattan_distance": d,
        "in_range": in_range,
        "source": source,
    }, indent=2))


def cmd_grid_dump_map(args):
    data = load_map_units(Path(args.map_units_json))
    print(f"map={data.get('map')} size={data.get('w')}x{data.get('h')}")
    print("own_deploy (party spawn tiles, no stats):")
    for i, rec in enumerate(data.get("own_deploy", [])):
        print(f"  [{i}] x={rec['x']} y={rec['y']}")
    print("units:")
    for i, u in enumerate(data.get("units", [])):
        print(f"  [{i}] camp={u.get('camp'):<6} fig={u.get('fig'):<4} x={u.get('x'):<3} y={u.get('y'):<3} "
              f"hp={u.get('hp'):<4} atk_min={u.get('atk_min', 0)} atk_max={u.get('atk_max', 0)} "
              f"cls_name={u.get('cls_name')!r}")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("launch", help="launch an isolated Xvfb + fd2-linux-verify instance, no debug hooks by default")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--remake-dir", default=str(DEFAULT_REMAKE_DIR))
    sp.add_argument("--campaign", default="assets/scenarios/campaign_full.json")
    sp.add_argument("--no-mute", action="store_true", help="omit FD2_MUTE=1 (default: muted, matches doc92/doc98 convention)")
    sp.add_argument("--fdother", default=None, help="FD2_ORIGINAL_FDOTHER path; omit for the canonical $HOME/fd2-run default; pass '-' to opt out entirely")
    sp.add_argument("--fdtxt", default=None, help="FD2_ORIGINAL_FDTXT path; same defaulting rule as --fdother")
    sp.add_argument("--dato", default=None, help="FD2_ORIGINAL_DATO path; same defaulting rule as --fdother")
    sp.add_argument("--extra-env", action="append", metavar="KEY=VAL",
                     help="additional env var for the game process (repeatable); NOT set by default -- "
                          "pass FD2_SHOT_*/FD2_CAMP_* explicitly here only if you deliberately want a "
                          "debug-hook shortcut for something other than a normal-playthrough round")
    sp.set_defaults(func=cmd_launch)

    sp = sub.add_parser("status", help="list all fd2-live-input-helper instances")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("teardown", help="kill one instance (PID+process-name verified, never a blanket pkill)")
    sp.add_argument("--instance", required=True)
    sp.set_defaults(func=cmd_teardown)

    sp = sub.add_parser("teardown-all", help="kill every fd2-live-input-helper instance")
    sp.set_defaults(func=cmd_teardown_all)

    sp = sub.add_parser("window-id", help="fresh xwininfo query for the instance's GLFW window id")
    sp.add_argument("--instance", required=True)
    sp.set_defaults(func=cmd_window_id)

    sp = sub.add_parser("key", help="send one or more keys, each confirmed by a wait or a settle-poll -- never blind")
    sp.add_argument("--instance", required=True)
    sp.add_argument("keys", nargs="+", help="xdotool key name(s), or an alias: confirm/cancel/up/down/left/right/tab/space")
    sp.add_argument("--wait", type=float, default=None,
                     help=f"fixed wall-clock seconds to wait after the last key (default {DEFAULT_WAIT_S}s; "
                          f"doc92 measured 0.4-0.6s needed for the battle command ring specifically)")
    sp.add_argument("--settle", action="store_true",
                     help="instead of a fixed wait, poll screenshots after the last key until 2 consecutive match")
    sp.add_argument("--settle-timeout", type=float, default=10.0)
    sp.add_argument("--settle-interval", type=float, default=0.25)
    sp.add_argument("--gap", type=float, default=DEFAULT_KEY_GAP_S, help="seconds between keys within this same call (doc92: 0.15-0.3s)")
    sp.set_defaults(func=cmd_key)

    sp = sub.add_parser("screenshot", help="save a timestamped/labeled PNG (default under .wsl_build/, not docs/figures/)")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--out", default=None, help="explicit output path (any dir); default: .wsl_build/live_input_helper/<instance>/<timestamp>[_label].png")
    sp.add_argument("--label", default=None)
    sp.add_argument("--resize", default=DEFAULT_SCREENSHOT_RESIZE,
                     help=f"convert -resize geometry, fits-within/preserves aspect (default {DEFAULT_SCREENSHOT_RESIZE}, "
                          f"the game's own logical canvas -- cuts vision-token cost with no real detail lost since the "
                          f"window is normally an upscaled multiple of this); pass --resize '' for the raw full-res capture")
    sp.add_argument("--autocrop", action="store_true",
                     help="convert -fuzz 3%% -trim +repage after resize -- removes a uniform (black) border; "
                          "safe no-op if the screen already fills the frame, but only CONFIRMED correct for the "
                          "battle/map screen so far (~79%%w x ~50%%h content ratio, 2026-09-01) -- opt in "
                          "deliberately per screen type, not as a blanket default")
    sp.set_defaults(func=cmd_screenshot)

    sp = sub.add_parser("wait-settle", help="standalone: poll until 2 consecutive screenshots match, or time out")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--timeout", type=float, default=10.0)
    sp.add_argument("--interval", type=float, default=0.25)
    sp.set_defaults(func=cmd_wait_settle)

    grid = sub.add_parser("grid", help="pure tile-coordinate arithmetic -- no live instance needed")
    gsub = grid.add_subparsers(dest="grid_cmd", required=True)

    sp = gsub.add_parser("distance", help="Manhattan distance between two logical tile coords")
    sp.add_argument("--a", required=True, metavar="X,Y")
    sp.add_argument("--b", required=True, metavar="X,Y")
    sp.set_defaults(func=cmd_grid_distance)

    sp = gsub.add_parser("range", help="is a target tile within a unit's real AtkMin/AtkMax weapon range?")
    sp.add_argument("--map-units-json", default=None, help="e.g. remake/assets/maps/map0/map0_units.json")
    sp.add_argument("--unit-index", type=int, default=None, help="index into the JSON's units[] array")
    sp.add_argument("--unit-fig", type=int, default=None, help="find the unit in units[] by its fig id")
    sp.add_argument("--own-deploy-index", type=int, default=None,
                     help="index into own_deploy[] instead (party spawn tile; carries no weapon stats, supply --atk-min/--atk-max)")
    sp.add_argument("--unit-x", type=int, default=None, help="manual mode: skip the JSON, give the unit's tile x directly")
    sp.add_argument("--unit-y", type=int, default=None, help="manual mode: skip the JSON, give the unit's tile y directly")
    sp.add_argument("--atk-min", type=int, default=None, help="override/supply AtkMin (0 or omitted defaults to 1, matching move.go)")
    sp.add_argument("--atk-max", type=int, default=None, help="override/supply AtkMax (0 or omitted defaults to 1, matching move.go)")
    sp.add_argument("--target-x", type=int, required=True)
    sp.add_argument("--target-y", type=int, required=True)
    sp.set_defaults(func=cmd_grid_range)

    sp = gsub.add_parser("dump-map", help="print own_deploy + units[] (coords/stats) for quick reference, no guessing from screen art")
    sp.add_argument("--map-units-json", required=True)
    sp.set_defaults(func=cmd_grid_dump_map)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
