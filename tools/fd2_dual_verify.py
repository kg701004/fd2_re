#!/usr/bin/env python3
"""FD2-DUAL-VERIFY: side-by-side remake vs DOSBox-X original screenshot
comparison tool -- sends the SAME key to an already-running remake instance
(fd2_live_input_helper) and an already-running DOSBox-X instance
(fd2_dosbox_live_helper), screenshots both, and records a manifest entry, so
a live verification round can walk a scripted key sequence and get matched
screenshot pairs automatically instead of manually interleaving two separate
tool invocations by hand and hoping the two runs stayed in sync.

WHY THIS EXISTS
--------------------------------------------------------------------
This project has repeatedly lost real time to exactly the confusion this
tool is meant to shrink: a screenshot from one side was misjudged as ground
truth when the OTHER side (or the reference copy itself) was actually wrong
(the Sol/thief map-sprite misidentification, and separately the
~/fd2-run/FD2.EXE contamination that produced a false "remake HP is 14x
wrong" finding -- see docs/knowledge-base/92-m5-normal-playthrough-log.md
續五~續九 and this project's own fd2-re-m5-remake-bugs-confirmed memory).
Both mistakes trace back to the same root cause: the two sides' screenshots
were compared across separately-run, hand-interleaved rounds that could
drift in exact starting state, timing, or which save/chapter was actually
loaded. Walking both sides through an IDENTICAL key sequence and keeping
their screenshots paired by step number is meant to make that class of
mistake harder to make -- it does NOT auto-decide which side is "right"; a
human/agent still reads the paired PNGs.

WHAT THIS DOES NOT DO
--------------------------------------------------------------------
- Does NOT launch either instance -- both must already be running (at a
  comparable starting point the caller set up deliberately, e.g. both
  freshly booted to the ch01 title-confirm screen) via their own tools'
  `launch` subcommands. This tool only owns the "send a key to both,
  screenshot both, log it" step, not session lifecycle -- the two instances
  have very different launch semantics (remake: no debug hooks by design
  for M5 Phase 4; DOSBox-X: canonical game dir, keepalive) and forcing a
  single launch step here would just be a worse copy of each tool's own
  launch.
- Does NOT decide whether the two screenshots match. It records file paths
  side by side, nothing more -- comparing them is a reading/vision task for
  whoever is running the verification round, same as before this tool
  existed.
- Does NOT guarantee both sides interpret one key name identically. Both
  underlying tools alias the same tokens (confirm/cancel/up/down/left/right/
  tab/space) to the same xdotool key names, and this project's own prior
  verification rounds (M5 Phase 4, doc92 續七) already established that
  sending the same xdotool key name to both is the correct way to compare
  them -- but a key that is legitimately unbound on one side and bound on
  the other will still just look like a no-visible-response non-event on
  that side; that is a genuine finding, not a tool bug.

USAGE
-----
Both instances already launched and at a comparable starting screen:
    python tools/fd2_dual_verify.py step --remake-instance R --dosbox-instance D confirm --label title_confirm
    python tools/fd2_dual_verify.py run --remake-instance R --dosbox-instance D --script keys.txt --session ch01_intro

keys.txt format for `run` -- one key (or alias) per line, optional trailing
label after whitespace, blank lines and `#` comments ignored:
    confirm     title_confirm
    down
    down
    confirm     select_ch01

See docs/knowledge-base/98-tooling-infrastructure.md for the design writeup
and fd2_live_input_helper.py / fd2_dosbox_live_helper.py for the primitives
this tool composes (not reimplements).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import fd2_live_input_helper as remake_tool   # noqa: E402
import fd2_dosbox_live_helper as dosbox_tool  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = TOOLS_DIR.parent
DEFAULT_SESSION_ROOT = REPO_ROOT / ".wsl_build" / "dual_verify"


def resolve_key(token: str) -> str:
    # Both underlying tools' KEY_ALIASES dicts are identical by design
    # (same token set, same xdotool names) -- use either's, documented here
    # once rather than duplicated a third time.
    return remake_tool.KEY_ALIASES.get(token.lower(), token)


def default_session_dir(remake_instance: str, dosbox_instance: str) -> Path:
    return DEFAULT_SESSION_ROOT / f"{remake_instance}__{dosbox_instance}"


def step(remake_instance: str, dosbox_instance: str, key: str, label: str | None,
          session_dir: Path, index: int, settle: bool, wait: float,
          settle_timeout: float, settle_interval: float,
          flag_no_response: bool) -> dict:
    """Send `key` to both instances, screenshot both, append one manifest
    entry. Remake side always goes first (arbitrary but fixed ordering, so
    a caller reading two `step` calls' wall-clock gap knows which is which)."""
    resolved = resolve_key(key)
    tag = f"{index:03d}" + (f"_{label}" if label else "")
    session_dir.mkdir(parents=True, exist_ok=True)

    entry: dict = {"index": index, "label": label, "key": key, "resolved_key": resolved,
                    "ts": time.time()}

    # --- remake side ---
    remake_tool.send_key(remake_instance, resolved)
    if settle:
        r_settled, r_raw = remake_tool.wait_for_settle(remake_instance, timeout=settle_timeout,
                                                          interval=settle_interval)
        entry["remake_settled"] = r_settled
    else:
        time.sleep(wait)
        entry["remake_settled"] = None
    r_out = session_dir / f"{tag}_remake.png"
    r_result = remake_tool.screenshot(remake_instance, r_out)
    entry["remake_raw"] = str(r_result.raw)
    entry["remake_view"] = str(r_result.view) if r_result.view else None

    # --- dosbox-x side ---
    baseline = None
    if flag_no_response:
        baseline = session_dir / f"{tag}_dosbox_baseline.png"
        dosbox_tool.screenshot(dosbox_instance, baseline)
    dosbox_tool.send_keys(dosbox_instance, [resolved])
    if settle:
        d_settled, d_raw, no_response = dosbox_tool.wait_for_settle(
            dosbox_instance, timeout=settle_timeout, interval=settle_interval, baseline=baseline)
        entry["dosbox_settled"] = d_settled
        entry["dosbox_no_response"] = no_response
    else:
        time.sleep(wait)
        entry["dosbox_settled"] = None
        entry["dosbox_no_response"] = None
    d_out = session_dir / f"{tag}_dosbox.png"
    d_result = dosbox_tool.screenshot(dosbox_instance, d_out, autocrop=True)
    entry["dosbox_raw"] = str(d_result.raw)
    entry["dosbox_view"] = str(d_result.view) if d_result.view else None

    manifest = session_dir / "manifest.jsonl"
    with open(manifest, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--remake-instance", required=True, help="an instance name already launched via fd2_live_input_helper.py launch")
    sp.add_argument("--dosbox-instance", required=True, help="an instance name already launched via fd2_dosbox_live_helper.py launch")
    sp.add_argument("--settle", action="store_true", help="poll-settle both sides after each key instead of a fixed wait (recommended, costs extra screenshot round-trips per side)")
    sp.add_argument("--wait", type=float, default=0.5, help="fixed wall-clock seconds per side when --settle is not given")
    sp.add_argument("--settle-timeout", type=float, default=10.0)
    sp.add_argument("--settle-interval", type=float, default=0.25)
    sp.add_argument("--flag-no-response", action="store_true", help="on the DOSBox-X side, also flag response=NO_RESPONSE/CHANGED per step (see fd2_dosbox_live_helper.py); costs one extra screenshot per step")


def cmd_step(args):
    session_dir = Path(args.session_dir) if args.session_dir else default_session_dir(args.remake_instance, args.dosbox_instance)
    entry = step(args.remake_instance, args.dosbox_instance, args.key, args.label,
                 session_dir, args.index, args.settle, args.wait,
                 args.settle_timeout, args.settle_interval, args.flag_no_response)
    print(json.dumps(entry, ensure_ascii=False, indent=2))


def cmd_run(args):
    session_dir = Path(args.session_dir) if args.session_dir else default_session_dir(args.remake_instance, args.dosbox_instance)
    lines = Path(args.script).read_text(encoding="utf-8").splitlines()
    index = args.start_index
    ran = 0
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        key = parts[0]
        label = parts[1].strip() if len(parts) > 1 else None
        entry = step(args.remake_instance, args.dosbox_instance, key, label,
                     session_dir, index, args.settle, args.wait,
                     args.settle_timeout, args.settle_interval, args.flag_no_response)
        print(f"[{index:03d}] key={key!r} label={label!r} "
              f"remake_view={entry.get('remake_view')} dosbox_view={entry.get('dosbox_view')} "
              f"remake_settled={entry.get('remake_settled')} dosbox_settled={entry.get('dosbox_settled')} "
              f"dosbox_no_response={entry.get('dosbox_no_response')}")
        ran += 1
        if args.settle and (entry.get("remake_settled") is False or entry.get("dosbox_settled") is False):
            print(f"STOPPING at step {index}: at least one side did not settle within timeout "
                  f"(remake_settled={entry.get('remake_settled')}, dosbox_settled={entry.get('dosbox_settled')})",
                  file=sys.stderr)
            if not args.continue_on_error:
                raise SystemExit(2)
        index += 1
    print(f"done: {ran} step(s), manifest at {session_dir / 'manifest.jsonl'}")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("step", help="send one key to both instances, screenshot both, log one manifest entry")
    _add_common(sp)
    sp.add_argument("key", help="xdotool key name or an alias: confirm/cancel/up/down/left/right/tab/space")
    sp.add_argument("--label", default=None)
    sp.add_argument("--index", type=int, default=0, help="step index used in output filenames/manifest (default 0)")
    sp.add_argument("--session-dir", default=None, help="default: .wsl_build/dual_verify/<remake-instance>__<dosbox-instance>")
    sp.set_defaults(func=cmd_step)

    sp = sub.add_parser("run", help="walk a script file of keys through both instances, one step() per line")
    _add_common(sp)
    sp.add_argument("--script", required=True, help="path to a keys-file, see module docstring for format")
    sp.add_argument("--session-dir", default=None, help="default: .wsl_build/dual_verify/<remake-instance>__<dosbox-instance>")
    sp.add_argument("--start-index", type=int, default=0)
    sp.add_argument("--continue-on-error", action="store_true", help="keep going past a settle timeout on either side instead of stopping")
    sp.set_defaults(func=cmd_run)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
