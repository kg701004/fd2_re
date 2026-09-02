#!/usr/bin/env python3
"""FD2-ORIGINAL-VERIFY: declarative, parallel, layered verification against the
**original** DOS game under DOSBox-X.

WHY THIS EXISTS
---------------
The 2026-09-02/03 rounds (see docs/knowledge-base/58-remake-live-verification-log.md)
re-derived a batch of facts straight from the original after `remake/` was removed and
after 13 of 18 "original-vs-remake" figures turned out to be self-copies. Every one of
those rounds was driven by hand: launch an instance, patch a chapter byte, mash Enter,
eyeball a screenshot, repeat. That is slow, and -- more importantly -- it is exactly the
process that historically produced mislabelled evidence, because "which screen did I
actually reach" was decided by a human glance rather than by a recorded assertion.

This tool turns a verification round into **data**: a scenario lists the steps and the
assertions, the runner executes them, and the report says which assertion passed on which
captured frame. Re-running a scenario months later reproduces the same evidence, and a
scenario that silently lands on the wrong screen fails instead of being written up.

PARALLELISM -- and the one race that makes it non-trivial
---------------------------------------------------------
`tools/dosbox_harness.sh` gives every instance its own Xvfb TCP display, its own tmux
socket-session and its own copy of the game directory, so N scenarios can genuinely run at
once. (Historic precedent: doc91's UI-VIS-TOWN entry ran a `townE2` instance on `:299`
alongside a concurrent `loadE2` instance.)

**But `pick_display_port()` is not concurrency-safe**, and this was measured here, not
assumed: it picks a port by scanning the registry for a live conflicting instance and by
checking `ss -tln`, yet the winning port only becomes visible to other launchers once the
Xvfb is actually up and the .state file written. Two launches fired simultaneously both scan
before either records a claim, so both choose the same display -- observed directly, with
`--jobs 2` putting both scenarios on `127.0.0.1:199`, their keystrokes going to a single
window, and both failing to reach the title, while the identical scenario passes at
`--jobs 1`. This module therefore serialises just the launch phase behind LAUNCH_LOCK and
runs the long key-driving part fully in parallel. Fixing the race properly (a lock file or
an explicit port argument) belongs in dosbox_harness.sh itself.

Threads, not processes: every step is a `wsl.exe` subprocess call, so the work is I/O-bound
and the GIL is irrelevant.

LAYERS
------
Each assertion declares a layer, so a report can distinguish "we never got there" from
"we got there but it looked wrong":

  L1 reach    -- did we arrive at the expected screen at all?
                 (`assert_ref`: mean-abs-diff of a crop against a reference PNG)
  L2 content  -- does the screen show what it should?
                 (`assert_distinct` / `assert_changed` / `assert_unchanged`)
  L3 data     -- does the captured state agree with an independent, non-visual source?
                 (`assert_save_field`: read the same slot back through tools/fd2save.py)

An L1 failure short-circuits the rest of that scenario: continuing to press keys on an
unexpected screen is how you end up with confident-looking screenshots of the wrong thing.

ENCODED PITFALLS (each of these cost a round to learn -- see doc58 2026-09-03)
------------------------------------------------------------------------------
1. Never blind-mash Enter to get past the title: the number of Enters needed varies with
   boot timing, and one Enter too many starts a NEW GAME instead of reaching LOAD. `poll_title`
   presses one Enter at a time and re-checks against a title reference until it matches.
2. The title's LOAD entry must be *seen* highlighted before Enter is pressed; the marker dots
   are the only cue. `assert_ref` against a known LOAD-highlighted crop makes that a real gate.
3. Shop/church service icons have **no visible selection highlight at all** -- arrow keys change
   zero pixels. So a scenario must never claim "service N" from keypress counts; it identifies
   the service from the resulting screen's own text. `assert_distinct` over the captured frames
   is the cheap version of that check.
4. wsl.exe is an unreliable narrator of its own exit code (already noted in
   fd2_live_input_helper.py and dosbox_diff_harness.py), so success is judged from stdout
   content, never the return code alone.
5. Paths crossing the Windows/WSL boundary need MSYS_NO_PATHCONV=1 and real argv, never a
   joined shell string.

USAGE
-----
    python tools/fd2_original_verify.py --list
    python tools/fd2_original_verify.py --run town_variant0 --run secret_shop
    python tools/fd2_original_verify.py --all --jobs 3
    python tools/fd2_original_verify.py --all --keep      # leave instances up for inspection

Scenarios live in SCENARIOS below (data, not code paths). Report is written to
.wsl_build/original_verify/<timestamp>/report.json alongside every captured frame.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is present in this repo's tooling env
    print("ERROR: Pillow required (pip install pillow)", file=sys.stderr)
    raise

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "dosbox_harness.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
FD2SAVE_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "fd2save.py").replace("\\", "/").split(":", 1)[1].lstrip("/")
OUT_ROOT = REPO_ROOT / ".wsl_build" / "original_verify"
REF_DIR = REPO_ROOT / ".wsl_build" / "verify_refs"

# Serialises the launch phase across scenario threads -- see Runner.run() for the
# dosbox_harness.sh pick_display_port() race this exists to work around.
LAUNCH_LOCK = threading.Lock()

# The DOSBox-X window is a fixed 1024x768 capture; the game canvas sits in this box.
# Established by bounding-box scan of a real capture (doc58 2026-09-03).
GAME_BOX = (192, 205, 832, 595)
# Title-screen menu rows (START/LOAD/CONTINUE) -- the only place the selection marker shows.
TITLE_MENU_BOX = (440, 520, 600, 585)


# --------------------------------------------------------------------------
# WSL plumbing -- real argv only (see module docstring, pitfall 5)
# --------------------------------------------------------------------------

def wsl_argv(argv: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    return subprocess.run(["wsl", "-d", "Ubuntu"] + argv,
                          capture_output=True, text=True, timeout=timeout, env=env)


def harness(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return wsl_argv(["bash", HARNESS_WSL] + [str(a) for a in args], timeout=timeout)


def to_wsl_path(p: Path) -> str:
    s = str(p.resolve()).replace("\\", "/")
    drive, rest = s.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


# --------------------------------------------------------------------------
# Image helpers
# --------------------------------------------------------------------------

def crop_rgb(png: Path, box=GAME_BOX) -> Image.Image:
    return Image.open(png).convert("RGB").crop(box)


def md5_of(png: Path, box=GAME_BOX) -> str:
    return hashlib.md5(crop_rgb(png, box).tobytes()).hexdigest()


def mean_abs_diff(a_png: Path, b_png: Path, box=GAME_BOX, size=(160, 100)) -> float:
    a = crop_rgb(a_png, box).resize(size)
    b = crop_rgb(b_png, box).resize(size)
    ap, bp = a.load(), b.load()
    total = 0
    w, h = size
    for y in range(h):
        for x in range(w):
            pa, pb = ap[x, y], bp[x, y]
            total += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return total / (w * h * 3)


# --------------------------------------------------------------------------
# Scenario model
# --------------------------------------------------------------------------

@dataclass
class Assertion:
    layer: str
    name: str
    ok: bool
    detail: str


@dataclass
class RunResult:
    scenario: str
    instance: str
    ok: bool
    assertions: list[Assertion] = field(default_factory=list)
    shots: dict[str, str] = field(default_factory=dict)  # label -> md5
    error: str = ""


class Runner:
    """Executes one scenario in one isolated harness instance."""

    def __init__(self, scenario: dict, out_dir: Path, keep: bool = False):
        self.spec = scenario
        self.name = scenario["name"]
        self.instance = scenario.get("instance", f"vf_{self.name}")[:20]
        self.dir = out_dir / self.name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.keep = keep
        self.result = RunResult(scenario=self.name, instance=self.instance, ok=True)
        self.last_shot: Path | None = None

    # -- primitives ------------------------------------------------------
    def shot(self, label: str) -> Path:
        remote = f"/tmp/vf_{self.instance}.png"
        harness("screenshot", self.instance, remote, timeout=90)
        local = self.dir / f"{label}.png"
        wsl_argv(["bash", "-lc", f"cp {remote} {to_wsl_path(local)}"], timeout=60)
        if not local.exists():
            raise RuntimeError(f"screenshot '{label}' did not materialise at {local}")
        self.result.shots[label] = md5_of(local)
        self.last_shot = local
        return local

    def keys(self, keys: list[str], wait: float) -> None:
        for k in keys:
            harness("send-keys", self.instance, k, timeout=60)
            time.sleep(wait)

    def assert_(self, layer: str, name: str, ok: bool, detail: str) -> bool:
        self.result.assertions.append(Assertion(layer, name, bool(ok), detail))
        if not ok:
            self.result.ok = False
        return bool(ok)

    # -- steps -----------------------------------------------------------
    def step_patch_chapter(self, st: dict) -> None:
        save = f"~/fd2-run-harness-{self.instance}/FD2.SAV"
        cmd = (f"cd /mnt/c/Users/kg701/Desktop/GAME/fd2_re && python3 {FD2SAVE_WSL} "
               f"{save} --set-chapter 0:{st['value']} --out {save}")
        cp = wsl_argv(["bash", "-lc", cmd], timeout=120)
        self.assert_("L3", "patch_chapter",
                     "wrote" in (cp.stdout or ""),
                     f"chapter byte -> {st['value']}: {(cp.stdout or cp.stderr or '').strip().splitlines()[-1:]}")

    def step_poll_title(self, st: dict) -> None:
        """Pitfall 1: press Enter one at a time until the title matches, never blind-mash."""
        ref = REF_DIR / "title.png"
        if not ref.exists():
            self.assert_("L1", "poll_title", False, f"missing reference {ref}")
            return
        tries = st.get("max_tries", 20)
        for i in range(1, tries + 1):
            cur = self.shot("_poll")
            d = mean_abs_diff(cur, ref)
            if d < st.get("max_diff", 12):
                self.assert_("L1", "poll_title", True, f"title reached on try {i} (diff {d:.2f})")
                return
            self.keys(["Return"], st.get("wait", 0.8))
        self.assert_("L1", "poll_title", False, f"title not reached in {tries} tries")

    def step_keys(self, st: dict) -> None:
        self.keys(st["keys"], st.get("wait", 0.8))

    def step_shot(self, st: dict) -> None:
        self.shot(st["label"])

    def step_assert_ref(self, st: dict) -> None:
        """Pitfall 2: gate an irreversible keypress on actually seeing the expected state."""
        ref = REF_DIR / st["ref"]
        if not ref.exists():
            self.assert_(st.get("layer", "L1"), f"ref:{st['ref']}", False, f"missing reference {ref}")
            return
        cur = self.dir / f"{st['label']}.png"
        box = tuple(st["box"]) if "box" in st else GAME_BOX
        d = mean_abs_diff(cur, ref, box=box)
        self.assert_(st.get("layer", "L1"), f"ref:{st['ref']}",
                     d <= st.get("max_diff", 3.0),
                     f"{st['label']} vs {st['ref']} diff={d:.2f} (max {st.get('max_diff', 3.0)})")

    def step_assert_distinct(self, st: dict) -> None:
        """Pitfall 3: prove the frames really are different screens, not one screen re-saved."""
        labels = st["labels"]
        seen = {}
        dupes = []
        for lb in labels:
            m = self.result.shots.get(lb)
            if m is None:
                dupes.append(f"{lb}:MISSING")
                continue
            if m in seen:
                dupes.append(f"{lb}=={seen[m]}")
            seen[m] = lb
        self.assert_(st.get("layer", "L2"), "distinct_frames", not dupes,
                     "all distinct" if not dupes else "duplicates: " + ", ".join(dupes))

    def step_assert_save_field(self, st: dict) -> None:
        save = f"~/fd2-run-harness-{self.instance}/FD2.SAV"
        cmd = f"cd /mnt/c/Users/kg701/Desktop/GAME/fd2_re && python3 {FD2SAVE_WSL} {save}"
        cp = wsl_argv(["bash", "-lc", cmd], timeout=120)
        out = cp.stdout or ""
        self.assert_("L3", f"save_contains:{st['contains'][:40]}",
                     st["contains"] in out,
                     "found" if st["contains"] in out else "NOT found in fd2save output")

    STEPS = {
        "patch_chapter": step_patch_chapter,
        "poll_title": step_poll_title,
        "keys": step_keys,
        "shot": step_shot,
        "assert_ref": step_assert_ref,
        "assert_distinct": step_assert_distinct,
        "assert_save_field": step_assert_save_field,
    }

    # -- driver ----------------------------------------------------------
    def _launch_detached(self) -> subprocess.Popen:
        """`launch` ends in a long keepalive sleep and MUST stay alive for the
        instance to live (dosbox_harness.sh's own header says so, and doc48 §8.4
        records a whole round lost to the Xvfb/tmux/dosbox tree being reaped when
        the launcher died). So: Popen, never wait, never time it out. Running it
        under subprocess.run(timeout=...) kills the launcher at the timeout and
        silently takes the instance with it -- that mistake produced an all-black
        framebuffer and 20 failed title polls on this tool's first run."""
        env = dict(os.environ)
        env["MSYS_NO_PATHCONV"] = "1"
        return subprocess.Popen(
            ["wsl", "-d", "Ubuntu", "bash", HARNESS_WSL, "launch",
             self.instance, str(self.spec.get("keepalive", 2400))],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

    def _wait_until_rendering(self, timeout_s: int = 90) -> bool:
        """Registry 'alive' only means Xvfb+tmux are up; DOSBox may not have mapped
        or drawn yet. Require an actually non-black frame before sending any key."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            st = harness("status", timeout=60).stdout or ""
            alive = any(line.split()[:1] == [self.instance] and " yes " in line
                        for line in st.splitlines())
            if alive:
                try:
                    shot = self.shot("_boot")
                    im = crop_rgb(shot).resize((64, 40))
                    # extrema avoids getdata() (deprecated in Pillow 14) and is enough:
                    # a still-black framebuffer has every channel max at 0.
                    if sum(hi for _lo, hi in im.getextrema()) > 60:
                        return True
                except Exception:  # noqa: BLE001 - not up yet; keep waiting
                    pass
            time.sleep(3)
        return False

    def run(self) -> RunResult:
        # Serialise the launch phase only. dosbox_harness.sh's pick_display_port()
        # chooses a port by scanning the registry for live instances, but it writes
        # the winning port to its own .state file only *after* the Xvfb starts -- so
        # two launches started at the same moment both scan before either records a
        # claim and both pick the same display. Observed directly: with --jobs 2 both
        # scenarios landed on 127.0.0.1:199, their keystrokes went to one window and
        # both failed to reach the title, while the identical scenario passes at
        # --jobs 1. Holding this lock until the instance is up and registered makes
        # the claim visible to the next launcher; the long part of a scenario (driving
        # keys) still runs fully in parallel.
        with LAUNCH_LOCK:
            harness("teardown", self.instance, timeout=60)
            self._proc = self._launch_detached()
            up = self._wait_until_rendering()
        if not self.assert_("L1", "instance_up", up,
                            f"instance {self.instance} alive and drawing a non-black frame"):
            if not self.keep:
                harness("teardown", self.instance, timeout=60)
            return self.result

        try:
            for st in self.spec["steps"]:
                fn = self.STEPS.get(st["op"])
                if fn is None:
                    self.assert_("L1", f"op:{st['op']}", False, "unknown op")
                    break
                fn(self, st)
                if not self.result.ok and st.get("fatal", st["op"] in ("poll_title", "assert_ref")):
                    # An L1 miss means every later keypress lands on an unknown screen.
                    self.result.error = f"stopped after failed {st['op']}"
                    break
        except Exception as exc:  # noqa: BLE001 - report, never crash the pool
            self.result.ok = False
            self.result.error = f"{type(exc).__name__}: {exc}"
        finally:
            if not self.keep:
                harness("teardown", self.instance, timeout=60)
                wsl_argv(["bash", "-lc", f"rm -rf ~/fd2-run-harness-{self.instance}"], timeout=60)
                # teardown kills the instance tree; the launcher is then just a stranded
                # keepalive sleep, so reap it rather than leaving a wsl.exe per scenario.
                proc = getattr(self, "_proc", None)
                if proc is not None and proc.poll() is None:
                    proc.terminate()
        return self.result


# --------------------------------------------------------------------------
# Scenarios (data)
# --------------------------------------------------------------------------
# Chapter bytes are 0-based FDFIELD stage numbers: 0x01 -> "第二章 羅德鎮" (town variant0),
# 0x0B -> "第十二章 北山道" (variant1), 0x02 -> "第三章 往塞拉村途中" (variant2).
# Verified by reading the LOAD slot text before loading (doc58 2026-09-03).

def _town_scenario(name: str, chapter: int) -> dict:
    steps = [
        {"op": "patch_chapter", "value": chapter},
        {"op": "poll_title"},
        {"op": "keys", "keys": ["Down"], "wait": 1.0},
        {"op": "shot", "label": "title_menu"},
        {"op": "assert_ref", "label": "title_menu", "ref": "title_load_menu.png",
         "box": list(TITLE_MENU_BOX), "max_diff": 3.0, "layer": "L1"},
        {"op": "keys", "keys": ["Return"], "wait": 3.5},
        {"op": "shot", "label": "slots"},
        {"op": "keys", "keys": ["Return"], "wait": 5.0},
        {"op": "shot", "label": "sel0"},
    ]
    for i in range(1, 5):
        steps += [{"op": "keys", "keys": ["Left"], "wait": 0.9},
                  {"op": "shot", "label": f"sel{i}"}]
    steps.append({"op": "assert_distinct", "labels": [f"sel{i}" for i in range(5)]})
    return {"name": name, "chapter": chapter, "steps": steps}


SCENARIOS = {
    "town_variant0": _town_scenario("town_variant0", 1),
    "town_variant1": _town_scenario("town_variant1", 11),
    "town_variant2": _town_scenario("town_variant2", 2),
    "secret_shop": {
        "name": "secret_shop",
        "steps": [
            {"op": "patch_chapter", "value": 1},
            {"op": "poll_title"},
            {"op": "keys", "keys": ["Down"], "wait": 1.0},
            {"op": "shot", "label": "title_menu"},
            {"op": "assert_ref", "label": "title_menu", "ref": "title_load_menu.png",
             "box": list(TITLE_MENU_BOX), "max_diff": 3.0, "layer": "L1"},
            {"op": "keys", "keys": ["Return"], "wait": 3.5},
            {"op": "keys", "keys": ["Return"], "wait": 5.0},
            {"op": "shot", "label": "tavern"},
            # The in-game NPC hint states the real input: Shift+F1 while standing at
            # selection0 (酒店). doc91 had recorded Ctrl+F2 at selection1 and failed.
            {"op": "keys", "keys": ["shift+F1"], "wait": 1.5},
            {"op": "shot", "label": "revealed"},
            {"op": "assert_distinct", "labels": ["tavern", "revealed"]},
            {"op": "keys", "keys": ["Return"], "wait": 3.5},
            {"op": "shot", "label": "shop_interior"},
            {"op": "keys", "keys": ["Return"], "wait": 2.5},
            {"op": "shot", "label": "stock"},
            {"op": "assert_distinct", "labels": ["tavern", "revealed", "shop_interior", "stock"]},
            {"op": "assert_save_field", "contains": "roster_count=0x0d"},
        ],
    },
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list scenario names and exit")
    ap.add_argument("--run", action="append", default=[], metavar="NAME", help="run one scenario (repeatable)")
    ap.add_argument("--all", action="store_true", help="run every scenario")
    ap.add_argument("--jobs", type=int, default=2, help="how many scenarios to run concurrently (default 2)")
    ap.add_argument("--keep", action="store_true", help="do not tear instances down (for inspection)")
    args = ap.parse_args()

    if args.list:
        for k, v in SCENARIOS.items():
            print(f"{k:16s} {len(v['steps'])} steps")
        return 0

    names = list(SCENARIOS) if args.all else args.run
    if not names:
        ap.error("nothing to do: pass --run NAME, --all, or --list")
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        ap.error(f"unknown scenario(s): {', '.join(unknown)}")

    out_dir = OUT_ROOT / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[verify] {len(names)} scenario(s), jobs={args.jobs}, out={out_dir}")

    results: list[RunResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futs = {pool.submit(Runner(SCENARIOS[n], out_dir, args.keep).run): n for n in names}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results.append(r)
            mark = "PASS" if r.ok else "FAIL"
            print(f"[{mark}] {r.scenario} ({len(r.assertions)} assertions)"
                  + (f" -- {r.error}" if r.error else ""))
            for a in r.assertions:
                if not a.ok:
                    print(f"        {a.layer} {a.name}: {a.detail}")

    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scenarios": [
            {"name": r.scenario, "instance": r.instance, "ok": r.ok, "error": r.error,
             "shots": r.shots,
             "assertions": [{"layer": a.layer, "name": a.name, "ok": a.ok, "detail": a.detail}
                            for a in r.assertions]}
            for r in sorted(results, key=lambda x: x.scenario)
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[verify] report -> {out_dir / 'report.json'}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
