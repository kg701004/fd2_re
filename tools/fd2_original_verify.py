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

PARALLELISM
-----------
`tools/dosbox_harness.sh` gives every instance its own Xvfb TCP display, its own tmux
socket-session and its own copy of the game directory, so N scenarios can genuinely run at
once. (Historic precedent: doc91's UI-VIS-TOWN entry ran a `townE2` instance on `:299`
alongside a concurrent `loadE2` instance.)

This used to require serialising the launch phase here, because the harness's old
`pick_display_port()` was not concurrency-safe: it chose a port but only published that
choice ~5-10s later when the .state file was finally written, so simultaneous launches both
picked the same display -- measured here, with `--jobs 2` putting both scenarios on
`127.0.0.1:199` while `--jobs 1` passed. **Fixed at the source on 2026-09-03**: the harness
now chooses and publishes a reservation atomically under an flock
(`reserve_display_port`), covered by `tools/test_dosbox_harness_ports.sh` and confirmed
live with three genuinely concurrent launches landing on :199/:299/:399. Launches
therefore run in parallel by default; `--serial-launch` restores the old one-at-a-time
behaviour if a host ever needs it.

Threads, not processes: every step is a `wsl.exe` subprocess call, so the work is I/O-bound
and the GIL is irrelevant.

LAYERS
------
Each assertion declares a layer, so a report can distinguish "we never got there" from
"we got there but it looked wrong":

  L1 reach    -- did we arrive at the expected screen at all?
                 (`assert_ref`: mean-abs-diff of a crop against a reference PNG)
  L2 content  -- does the screen show what it should?
                 (`assert_distinct`; `assert_ref_differs` for "this must NOT be the old
                 state"; `measure_change` records an open question without judging it)
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
import contextlib
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

try:
    import numpy as _np
except ImportError:  # optional: only accelerates mean_abs_diff, never changes its result
    _np = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "dosbox_harness.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
FD2SAVE_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "fd2save.py").replace("\\", "/").split(":", 1)[1].lstrip("/")
OUT_ROOT = REPO_ROOT / ".wsl_build" / "original_verify"
# Reference frames are FIXTURES, not build output, so they live under tools/ and are
# tracked. They used to sit in .wsl_build/, which .gitignore excludes -- meaning every
# scenario's assert_ref pointed at a file that was never committed, and --selftest would
# fail on a fresh clone. Found while adding the equip references (2026-09-03).
REF_DIR = REPO_ROOT / "tools" / "verify_refs"

# Launch-phase gate. The harness allocates displays atomically as of 2026-09-03, so this
# is a no-op by default and launches run in parallel; --serial-launch swaps in a real Lock
# as an escape hatch (see the PARALLELISM section of the module docstring).
LAUNCH_GATE: "contextlib.AbstractContextManager" = contextlib.nullcontext()


def set_serial_launch(enabled: bool) -> None:
    global LAUNCH_GATE
    LAUNCH_GATE = threading.Lock() if enabled else contextlib.nullcontext()

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
    """Mean absolute per-channel difference of two crops, 0..255.

    Vectorised via numpy when available: this runs on every poll_title
    iteration, and the original pure-Python double loop cost ~48k interpreted
    operations per comparison. The fallback keeps the tool usable in a bare
    environment; both paths are exercised by --selftest, which asserts they
    agree, so the fast path can never silently drift from the reference one.
    """
    a = crop_rgb(a_png, box).resize(size)
    b = crop_rgb(b_png, box).resize(size)
    return _mad_fast(a, b) if _np is not None else _mad_reference(a, b)


def _mad_reference(a: Image.Image, b: Image.Image) -> float:
    """Dependency-free reference implementation; --selftest pins the fast path to it.

    Works on the raw RGB byte stream rather than getdata() -- same arithmetic (both
    are a mean over every channel value), but avoids materialising a tuple per pixel
    and avoids getdata(), which Pillow 14 removes.
    """
    ab, bb = a.tobytes(), b.tobytes()
    return sum(abs(x - y) for x, y in zip(ab, bb)) / len(ab)


def _mad_fast(a: Image.Image, b: Image.Image) -> float:
    return float(abs(_np.asarray(a, dtype=_np.int16) - _np.asarray(b, dtype=_np.int16)).mean())


# A frame whose cross-run difference is at most this fraction of pixels, and whose
# differing pixels all fit inside a box this size, is the party leader's unlocked
# idle-animation phase rather than a real change. Both numbers come from measuring
# this capture geometry (0.54-0.57% of pixels, always a single 48x48 box = the 24x24
# FDICON sprite at 2x scale), and agree with doc58's independently recorded 0.57%.
# They are deliberately just above the measured values, not round guesses.
ANIM_MAX_PIXEL_FRACTION = 0.01
ANIM_MAX_BOX = 64


def classify_instability(paths: list[Path], box=GAME_BOX) -> tuple[str, str]:
    """Decide whether frames that differ across runs differ only by animation phase.

    Returns ("animation"|"structural"|"unknown", human-readable detail). Comparisons
    are made against the first frame, and the worst case decides -- one structural
    difference in a set is enough to disqualify the whole label.
    """
    if len(paths) < 2:
        return "unknown", "fewer than two frames to compare"
    if _np is None:
        return "unknown", "numpy unavailable; cannot localise the difference"
    ref = _np.asarray(crop_rgb(paths[0], box), dtype=_np.int16)
    worst_frac, worst_dims, verdict = 0.0, (0, 0), "animation"
    for p in paths[1:]:
        cur = _np.asarray(crop_rgb(p, box), dtype=_np.int16)
        if cur.shape != ref.shape:
            return "structural", f"frame size changed: {ref.shape} vs {cur.shape}"
        mask = abs(cur - ref).sum(axis=2) > 30
        n = int(mask.sum())
        if n == 0:
            continue
        frac = n / mask.size
        ys, xs = _np.nonzero(mask)
        w, h = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        if frac > worst_frac:
            worst_frac, worst_dims = frac, (w, h)
        if frac > ANIM_MAX_PIXEL_FRACTION or w > ANIM_MAX_BOX or h > ANIM_MAX_BOX:
            verdict = "structural"
    if worst_frac == 0.0:
        return "animation", "no pixel differed by more than the noise threshold"
    return verdict, (f"max {worst_frac * 100:.2f}% of pixels differ, "
                     f"confined to {worst_dims[0]}x{worst_dims[1]}px")


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
    # Open-question measurements: recorded, never pass/fail. See step_measure_change.
    measurements: list[dict] = field(default_factory=list)
    error: str = ""
    duration_s: float = 0.0


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
    def shot(self, label: str, attempts: int = 3) -> Path:
        """Capture one frame straight into the run directory.

        The harness's `screenshot` subcommand takes the destination path, so it
        can write to the /mnt/c view of the run directory directly -- the earlier
        version wrote to /tmp and then shelled out a second time to copy it,
        doubling the wsl.exe round-trips on the hottest primitive in the tool
        (poll_title captures a frame per iteration).

        Retries: `import` occasionally loses a race with a mode switch and yields
        nothing. That is transient, so a failed capture is retried rather than
        failing a scenario for an infrastructure hiccup -- but it never fabricates
        a frame: if every attempt fails the caller gets an exception.

        Labels starting with '_' are internal (boot/poll probes) and are kept out
        of the report's frame list so a later assert_distinct or a cross-repeat
        stability comparison only ever sees frames a scenario deliberately named.
        """
        local = self.dir / f"{label}.png"
        last_err = ""
        for i in range(1, attempts + 1):
            if local.exists():
                local.unlink()
            cp = harness("screenshot", self.instance, to_wsl_path(local), timeout=90)
            if local.exists() and local.stat().st_size > 0:
                if not label.startswith("_"):
                    self.result.shots[label] = md5_of(local)
                self.last_shot = local
                return local
            last_err = (cp.stderr or cp.stdout or "").strip()[-160:]
            time.sleep(1.0 * i)
        raise RuntimeError(f"screenshot '{label}' failed after {attempts} attempts: {last_err}")

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

    def step_assert_same_as(self, st: dict) -> None:
        """Assert two captured frames are the same screen, tolerating idle animation.

        Used to re-establish a known state mid-scenario: after probing one branch and
        escaping back, confirm we really are back on the expected menu before probing
        the next one. Without this, one wrong Escape depth silently shifts every later
        probe onto a different screen -- the exact way a mapping gets recorded wrong.

        Animation tolerance reuses classify_instability, so the leader/shopkeeper idle
        sprite (measured at 0.54-0.57% of pixels in a <=48x48 box) does not count as a
        difference, while a genuinely different screen does.
        """
        a, b = self.dir / f"{st['a']}.png", self.dir / f"{st['b']}.png"
        if not (a.exists() and b.exists()):
            self.assert_(st.get("layer", "L1"), f"same:{st['a']}~{st['b']}", False, "missing frame")
            return
        kind, info = classify_instability([a, b])
        self.assert_(st.get("layer", "L1"), f"same:{st['a']}~{st['b']}",
                     kind in ("animation", "unknown"), info)

    def step_assert_ref_differs(self, st: dict) -> None:
        """The mirror of assert_ref: this frame must NOT be the reference state.

        Exists because "matches the expected after-state" is only half an argument. If
        the two reference images ever became the same file -- the exact defect this
        project found in 13 of 18 comparison figures -- an equality-only check would
        keep passing while proving nothing. Pairing the two makes that unfalsifiable
        combination impossible.
        """
        ref = REF_DIR / st["ref"]
        if not ref.exists():
            self.assert_(st.get("layer", "L2"), f"differs:{st['ref']}", False,
                         f"missing reference {ref}")
            return
        cur = self.dir / f"{st['label']}.png"
        box = tuple(st["box"]) if "box" in st else GAME_BOX
        d = mean_abs_diff(cur, ref, box=box)
        floor = st.get("min_diff", 1.0)
        self.assert_(st.get("layer", "L2"), f"differs:{st['ref']}", d > floor,
                     f"{st['label']} vs {st['ref']} diff={d:.2f} (must exceed {floor})")

    def step_measure_change(self, st: dict) -> None:
        """Record whether two frames are structurally different -- WITHOUT asserting it.

        For an open question ("does Shift+F1 do anything in this chapter?") both answers
        are legitimate findings, so gating on one would turn a real result into a tool
        failure. The L1 steps still gate that we actually reached the screen; this only
        reports what happened once we were there.

        Uses classify_instability rather than assert_distinct's MD5 equality on purpose:
        MD5 cannot answer this question at all. Any screen carrying an idle-animation
        sprite differs run to run (measured 0.54-0.57% of pixels in a <=48x48 box), so
        "nothing happened" would come back as "the frames are distinct" -- exactly the
        kind of evidence that cannot tell the two outcomes apart.
        """
        a, b = self.dir / f"{st['a']}.png", self.dir / f"{st['b']}.png"
        if not (a.exists() and b.exists()):
            self.result.measurements.append(
                {"name": st["name"], "result": "missing_frame", "detail": f"{st['a']} / {st['b']}"})
            return
        kind, info = classify_instability([a, b])
        # structural => the screen genuinely changed; animation => it did not. "unknown"
        # means classify_instability could not localise the difference at all (no numpy),
        # which must NOT be reported as "unchanged" -- that would be an unmeasured claim.
        result = {"structural": "changed", "animation": "unchanged"}.get(kind, "indeterminate")
        self.result.measurements.append(
            {"name": st["name"], "a": st["a"], "b": st["b"],
             "result": result, "kind": kind, "detail": info})

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
        "assert_same_as": step_assert_same_as,
        "assert_ref_differs": step_assert_ref_differs,
        "measure_change": step_measure_change,
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
        started = time.time()
        try:
            return self._run()
        finally:
            self.result.duration_s = time.time() - started

    def _run(self) -> RunResult:
        # LAUNCH_GATE is a nullcontext unless --serial-launch was passed: the harness
        # now reserves its display port atomically, so concurrent launches are safe.
        with LAUNCH_GATE:
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
            # Same measurement the two other chapters take, so ch02 acts as the positive
            # control for them: if this one ever reports "unchanged", the probe itself is
            # broken and the other chapters' results mean nothing.
            {"op": "measure_change", "name": "shift_f1_at_tavern", "a": "tavern", "b": "revealed"},
            {"op": "assert_save_field", "contains": "roster_count=0x0d"},
        ],
    },
}


def _secret_shop_probe(name: str, chapter: int) -> dict:
    """Does the ch02 secret-shop input generalise to the other two town variants?

    Deliberately makes NO assertion about the outcome -- "Shift+F1 does nothing here" is
    a perfectly good answer, and asserting either way would report a finding as a failure.
    The L1 title gate still fails loudly if we never reached the town at all, so an
    "unchanged" result cannot be confused with a scenario that went off the rails.
    """
    return {
        "name": name,
        "chapter": chapter,
        "steps": [
            {"op": "patch_chapter", "value": chapter},
            {"op": "poll_title"},
            {"op": "keys", "keys": ["Down"], "wait": 1.0},
            {"op": "shot", "label": "title_menu"},
            {"op": "assert_ref", "label": "title_menu", "ref": "title_load_menu.png",
             "box": list(TITLE_MENU_BOX), "max_diff": 3.0, "layer": "L1"},
            {"op": "keys", "keys": ["Return"], "wait": 3.5},
            {"op": "keys", "keys": ["Return"], "wait": 5.0},
            {"op": "shot", "label": "tavern"},
            {"op": "keys", "keys": ["shift+F1"], "wait": 1.5},
            {"op": "shot", "label": "revealed"},
            {"op": "measure_change", "name": "shift_f1_at_tavern", "a": "tavern", "b": "revealed"},
            # If it did open something, walking in should reach a shop interior; if it
            # did not, this Enter just enters the tavern. Both are captured, neither
            # asserted -- the frames themselves say which happened.
            {"op": "keys", "keys": ["Return"], "wait": 3.5},
            {"op": "shot", "label": "after_enter"},
            {"op": "measure_change", "name": "enter_after_shift_f1", "a": "revealed", "b": "after_enter"},
        ],
    }


# ch02 = raw 1 (already covered above), ch12 = raw 11, ch03 = raw 2.
SCENARIOS["secret_shop_v1"] = _secret_shop_probe("secret_shop_v1", 11)
SCENARIOS["secret_shop_v2"] = _secret_shop_probe("secret_shop_v2", 2)




# Probing the hidden service selector: one index per scenario/instance.
#
# The first attempt probed all four indices inside one instance, escaping back to the
# service menu between probes. The assert_same_as gate caught that Escape x3 does not
# return to the service menu at all -- it leaves the venue entirely for the town map
# (97% of pixels differ), so every probe after the first was on a drifting screen, and
# two probes duly captured identical frames. Rather than tune an Escape depth that has
# no reason to be stable across venues and depths, each index now gets a fresh instance
# and a fresh navigation. Costs nothing but wall-clock, which the thread pool absorbs.

_TO_TOWN = [
    {"op": "patch_chapter", "value": 1},
    {"op": "poll_title"},
    {"op": "keys", "keys": ["Down"], "wait": 1.0},
    {"op": "shot", "label": "title_menu"},
    {"op": "assert_ref", "label": "title_menu", "ref": "title_load_menu.png",
     "box": list(TITLE_MENU_BOX), "max_diff": 3.0, "layer": "L1"},
    {"op": "keys", "keys": ["Return"], "wait": 3.5},
    {"op": "keys", "keys": ["Return"], "wait": 5.0},
]

# Reaching each venue's service menu from the town's landing selection (sel0 酒店).
_ENTER_SHOP = [
    {"op": "keys", "keys": ["Left"], "wait": 0.9},        # sel0 -> sel1 武器店
    {"op": "keys", "keys": ["Return"], "wait": 3.5},      # shopkeeper
    {"op": "keys", "keys": ["Return"], "wait": 2.5},      # first service screen
    {"op": "keys", "keys": ["Escape"], "wait": 1.5},      # -> service menu
]
_ENTER_CHURCH = [
    {"op": "keys", "keys": ["Left", "Left", "Left", "Left"], "wait": 0.8},  # sel0 -> sel4 教會
    {"op": "keys", "keys": ["Return"], "wait": 3.5},      # greeting / service menu
]


def _service_scenario(venue: str, enter: list[dict], idx: int) -> dict:
    steps = _TO_TOWN + list(enter) + [{"op": "shot", "label": "service_menu"}]
    if idx:
        steps += [{"op": "keys", "keys": ["Right"] * idx, "wait": 0.7}]
    steps += [
        {"op": "keys", "keys": ["Return"], "wait": 3.0},
        {"op": "shot", "label": "opened"},
        {"op": "keys", "keys": ["Return"], "wait": 2.5},
        {"op": "shot", "label": "opened_next"},
        # The selector is invisible, so the only honest evidence that this index does
        # something distinct is that its screens differ from the menu we came from.
        {"op": "assert_distinct", "labels": ["service_menu", "opened"], "layer": "L2"},
    ]
    return {"name": f"{venue}_svc{idx}", "steps": steps}


for _i in range(4):
    SCENARIOS[f"shop_svc{_i}"] = _service_scenario("shop", _ENTER_SHOP, _i)
    SCENARIOS[f"church_svc{_i}"] = _service_scenario("church", _ENTER_CHURCH, _i)

# --------------------------------------------------------------------------
# Weapon-shop purchase + equip, executed for real (mutates the instance's save).
#
# The key sequence below is NOT assumed: it was mapped by a recon pass that captured a
# frame after every single keypress and asserted nothing, then read back which item and
# which recipient each step had actually selected from the screens' own text (the
# confirm prompt names the item, the status panel names the character). Only once the
# flow was known was it written down as an asserting scenario. Details in doc58
# 2026-09-03 續三.
#
# Purchase grid is 2x2 and, unlike the service selector, does draw a cursor:
#   (none)=布衣 $50 +DP2   Right=旅行裝 $500 +DP10
#   Down=皮甲 $300 +DP8    Right+Down=法師袍 $750 +DP12

_TO_SHOP_GRID = _TO_TOWN + [
    {"op": "keys", "keys": ["Left"], "wait": 0.9},      # sel0 -> sel1 武器店
    {"op": "keys", "keys": ["Return"], "wait": 3.5},    # shopkeeper
    {"op": "keys", "keys": ["Return"], "wait": 2.5},    # purchase grid
]

# Escape once from the grid returns to the service menu; service 2 = 裝備; the roster's
# second entry is 亞雷斯.
_TO_ARES_PANEL = [
    {"op": "keys", "keys": ["Escape"], "wait": 1.5},
    {"op": "keys", "keys": ["Right", "Right"], "wait": 0.8},
    {"op": "keys", "keys": ["Return"], "wait": 2.2},
    {"op": "keys", "keys": ["Down"], "wait": 0.8},
    {"op": "keys", "keys": ["Return"], "wait": 2.2},
    {"op": "shot", "label": "ares_panel"},
]

# Control: same walk, no purchase. Pins the pre-equip state so the executing scenario's
# result cannot be confused with "that is just what the panel always looked like".
SCENARIOS["equip_control"] = {
    "name": "equip_control",
    "steps": _TO_SHOP_GRID + _TO_ARES_PANEL + [
        {"op": "assert_ref", "label": "ares_panel", "ref": "ares_panel_before.png",
         "max_diff": 3.0, "layer": "L2"},
    ],
}


# Executes the purchase and the equip, then reads the real status panel. The reference
# frame encodes the verified outcome: DP 642->350, EV 186->166, 龍神鎧甲 +DP300 dropping
# to unequipped (orange) while 皮甲 +DP008 becomes equipped (red).
SCENARIOS["equip_execute"] = {
    "name": "equip_execute",
    "steps": _TO_SHOP_GRID + [
        {"op": "keys", "keys": ["Down"], "wait": 0.8},        # 皮甲
        {"op": "keys", "keys": ["Return"], "wait": 2.0},
        {"op": "shot", "label": "confirm_item"},
        {"op": "keys", "keys": ["Return"], "wait": 2.5},      # YES -> recipient list
        {"op": "keys", "keys": ["Down"], "wait": 0.8},        # 亞雷斯
        {"op": "shot", "label": "recipient_preview"},
        {"op": "keys", "keys": ["Return"], "wait": 2.0},
        {"op": "shot", "label": "equip_prompt"},
        {"op": "keys", "keys": ["Return"], "wait": 2.5},      # YES -> equip
        {"op": "shot", "label": "money_after"},
        {"op": "assert_distinct",
         "labels": ["confirm_item", "recipient_preview", "equip_prompt", "money_after"]},
    ] + _TO_ARES_PANEL + [
        {"op": "assert_ref", "label": "ares_panel", "ref": "ares_panel_after_leather.png",
         "max_diff": 3.0, "layer": "L2"},
        # The whole point: the panel must NOT still look like the pre-equip one. Without
        # this, a scenario that silently failed to equip anything would still pass its
        # equality check if the two references were ever accidentally the same file.
        {"op": "assert_ref_differs", "label": "ares_panel", "ref": "ares_panel_before.png",
         "min_diff": 1.0, "layer": "L2"},
    ],
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def selftest() -> int:
    """Validate the tool's own image/assertion logic without launching anything.

    This exists because every other check in this file depends on mean_abs_diff
    and md5_of being right; if the fast (numpy) path silently disagreed with the
    reference path, every L1 gate in every scenario would be quietly wrong.
    """
    import tempfile
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'ok ' if ok else 'FAIL'}] {name}{(' -- ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        black = Image.new("RGB", (900, 700), (0, 0, 0))
        white = Image.new("RGB", (900, 700), (255, 255, 255))
        grey = Image.new("RGB", (900, 700), (10, 10, 10))
        pb, pw, pg = tmp / "b.png", tmp / "w.png", tmp / "g.png"
        black.save(pb); white.save(pw); grey.save(pg)

        check("identical frames -> diff 0", mean_abs_diff(pb, pb) == 0.0)
        check("black vs white -> diff 255", abs(mean_abs_diff(pb, pw) - 255.0) < 0.01,
              f"got {mean_abs_diff(pb, pw)}")
        check("near-black diff is small", mean_abs_diff(pb, pg) < 12.0)
        check("md5 stable for same image", md5_of(pb) == md5_of(pb))
        check("md5 differs for different images", md5_of(pb) != md5_of(pw))

        if _np is not None:
            # The whole point of having two implementations: they must agree, or every
            # L1 gate in every scenario is silently running on unvalidated arithmetic.
            for name, (x, y) in {"black/grey": (pb, pg), "black/white": (pb, pw)}.items():
                ia = crop_rgb(x).resize((160, 100))
                ib = crop_rgb(y).resize((160, 100))
                fast, slow = _mad_fast(ia, ib), _mad_reference(ia, ib)
                check(f"numpy path == reference path ({name})", abs(fast - slow) < 1e-9,
                      f"{fast} vs {slow}")
        else:
            print("  [skip] numpy not installed; only the reference path is in use")

        # The blackness gate that decides "the game is actually drawing".
        check("black frame fails the rendering gate",
              sum(hi for _lo, hi in crop_rgb(pb).getextrema()) <= 60)
        check("bright frame passes the rendering gate",
              sum(hi for _lo, hi in crop_rgb(pw).getextrema()) > 60)

        # Scenario specs must only use implemented ops, or a typo silently no-ops.
        known = set(Runner.STEPS)
        for sname, spec in SCENARIOS.items():
            bad = [s["op"] for s in spec["steps"] if s["op"] not in known]
            check(f"scenario '{sname}' ops implemented", not bad, f"unknown: {bad}")
            labels = {s["label"] for s in spec["steps"] if s["op"] == "shot"}
            refs = [s for s in spec["steps"] if s["op"] == "assert_ref"]
            missing = [s["label"] for s in refs if s["label"] not in labels]
            check(f"scenario '{sname}' assert_ref targets a captured frame", not missing,
                  f"no shot for: {missing}")
            dis = [s for s in spec["steps"] if s["op"] == "assert_distinct"]
            missing2 = sorted({lb for s in dis for lb in s["labels"] if lb not in labels})
            check(f"scenario '{sname}' assert_distinct targets captured frames", not missing2,
                  f"no shot for: {missing2}")
            meas = [s for s in spec["steps"] if s["op"] == "measure_change"]
            missing3 = sorted({s[k] for s in meas for k in ("a", "b") if s[k] not in labels})
            check(f"scenario '{sname}' measure_change targets captured frames", not missing3,
                  f"no shot for: {missing3}")

        ref_ops = ("assert_ref", "assert_ref_differs")
        # title.png is referenced by step_poll_title rather than by a scenario step, so
        # the scan below would miss it -- and without it every scenario fails at L1.
        needed = {"title.png"}
        needed |= {s["ref"] for sp in SCENARIOS.values() for s in sp["steps"] if s["op"] in ref_ops}
        for ref in needed:
            check(f"reference image present: {ref}", (REF_DIR / ref).exists(), str(REF_DIR / ref))

        # Any pair of references used as "must match" / "must differ" on the same label
        # must actually be different images, or the pair proves nothing (the 13-of-18
        # self-copy defect, encoded as a check).
        for sname, spec in SCENARIOS.items():
            want = {s["label"]: s["ref"] for s in spec["steps"] if s["op"] == "assert_ref"}
            notw = {s["label"]: s["ref"] for s in spec["steps"] if s["op"] == "assert_ref_differs"}
            for lb in set(want) & set(notw):
                a, b = REF_DIR / want[lb], REF_DIR / notw[lb]
                same = a.exists() and b.exists() and md5_of(a) == md5_of(b)
                check(f"scenario '{sname}' ref pair for '{lb}' are different images", not same,
                      f"{want[lb]} and {notw[lb]} are the same image")

        # The launch gate must actually switch, and must be re-entrant-safe as a
        # nullcontext -- a broken gate would either serialise everything silently
        # or deadlock the pool.
        set_serial_launch(False)
        check("default launch gate does not serialise", isinstance(LAUNCH_GATE, contextlib.nullcontext))
        set_serial_launch(True)
        check("--serial-launch installs a real lock", isinstance(LAUNCH_GATE, type(threading.Lock())))
        set_serial_launch(False)

    print(f"\nselftest: {'PASS' if not failures else 'FAIL -- ' + ', '.join(failures)}")
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list scenario names and exit")
    ap.add_argument("--selftest", action="store_true",
                    help="validate the tool's own logic offline (no DOSBox), then exit")
    ap.add_argument("--run", action="append", default=[], metavar="NAME", help="run one scenario (repeatable)")
    ap.add_argument("--all", action="store_true", help="run every scenario")
    ap.add_argument("--jobs", type=int, default=2, help="how many scenarios to run concurrently (default 2)")
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="run the whole set N times and report per-frame hash stability across runs "
                         "(a scenario that passes but renders differently each time is a real finding)")
    ap.add_argument("--keep", action="store_true", help="do not tear instances down (for inspection)")
    ap.add_argument("--serial-launch", action="store_true",
                    help="launch one instance at a time (pre-2026-09-03 workaround for the "
                         "harness display-port race; only needed if that fix is unavailable)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

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

    set_serial_launch(args.serial_launch)

    base_dir = OUT_ROOT / time.strftime("%Y%m%d-%H%M%S")
    base_dir.mkdir(parents=True, exist_ok=True)
    print(f"[verify] {len(names)} scenario(s) x{args.repeat}, jobs={args.jobs}, "
          f"launch={'serial' if args.serial_launch else 'parallel'}, out={base_dir}")

    passes: list[list[RunResult]] = []
    for rep in range(1, max(1, args.repeat) + 1):
        out_dir = base_dir if args.repeat == 1 else base_dir / f"run{rep}"
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.repeat > 1:
            print(f"--- run {rep}/{args.repeat} ---")
        results: list[RunResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            futs = {pool.submit(Runner(SCENARIOS[n], out_dir, args.keep).run): n for n in names}
            for fut in concurrent.futures.as_completed(futs):
                r = fut.result()
                results.append(r)
                mark = "PASS" if r.ok else "FAIL"
                print(f"[{mark}] {r.scenario} ({len(r.assertions)} assertions, {r.duration_s:.0f}s)"
                      + (f" -- {r.error}" if r.error else ""))
                for a in r.assertions:
                    if not a.ok:
                        print(f"        {a.layer} {a.name}: {a.detail}")
                # Measurements are the answer to an open question, not a pass/fail --
                # print them on PASS runs too or the result would be invisible.
                for m in r.measurements:
                    print(f"        MEASURED {m['name']}: {m['result']} ({m.get('detail', '')})")
        passes.append(results)

    # Cross-run stability: the same scenario replayed from the same save should
    # render the same frames. A scenario that passes every time but hashes
    # differently is not automatically "fine" -- it can mean the captured state is
    # nondeterministic, which is the class of thing that made earlier rounds'
    # screenshots disagree with each other.
    #
    # But one source of frame-hash churn here is known, measured and benign: the
    # party leader's idle animation is not phase-locked at capture time, so a frame
    # containing that sprite can legitimately land on a different animation frame.
    # Measured on this exact capture geometry, that difference is 0.54-0.57% of
    # pixels confined to a single 48x48 box (the 24x24 FDICON sprite at 2x capture
    # scale) -- matching what doc58's UI-VIS-TOWN entry independently recorded
    # (362/64000 px = 0.57%, all inside the leader sprite) before adding
    # lock_pulse_phase() to dosbox_diff_harness.py.
    #
    # So instability is classified rather than flattened: differences that fit the
    # animation profile are reported as ANIMATION and do not fail the run; anything
    # larger or spread wider is STRUCTURAL and does.
    stability: dict[str, dict[str, object]] = {}
    if len(passes) > 1:
        print("\n[stability] frame hashes across runs:")
        for name in names:
            per_label: dict[str, set[str]] = {}
            for results in passes:
                r = next((x for x in results if x.scenario == name), None)
                if r is None:
                    continue
                for lb, h in r.shots.items():
                    per_label.setdefault(lb, set()).add(h)
            unstable = sorted(lb for lb, hs in per_label.items() if len(hs) > 1)
            animation, structural, detail = [], [], {}
            for lb in unstable:
                paths = [base_dir / f"run{i}" / name / f"{lb}.png" for i in range(1, len(passes) + 1)]
                paths = [p for p in paths if p.exists()]
                kind, info = classify_instability(paths)
                detail[lb] = info
                (animation if kind == "animation" else structural).append(lb)
            stability[name] = {"labels": len(per_label), "unstable": unstable,
                               "animation": animation, "structural": structural,
                               "detail": detail}
            if not unstable:
                print(f"  {name:16s} {len(per_label)} frames, all identical across runs")
            else:
                bits = []
                if animation:
                    bits.append(f"ANIMATION(ok): {', '.join(animation)}")
                if structural:
                    bits.append(f"STRUCTURAL: {', '.join(structural)}")
                print(f"  {name:16s} {len(per_label)} frames, " + " | ".join(bits))
                for lb in unstable:
                    print(f"      {lb}: {detail[lb]}")

    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "repeat": args.repeat,
        "jobs": args.jobs,
        "runs": [
            [{"name": r.scenario, "instance": r.instance, "ok": r.ok, "error": r.error,
              "duration_s": round(r.duration_s, 1), "shots": r.shots,
              "measurements": r.measurements,
              "assertions": [{"layer": a.layer, "name": a.name, "ok": a.ok, "detail": a.detail}
                             for a in r.assertions]}
             for r in sorted(results, key=lambda x: x.scenario)]
            for results in passes
        ],
        "stability": stability,
    }
    (base_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[verify] report -> {base_dir / 'report.json'}")
    all_ok = all(r.ok for results in passes for r in results)
    # Only STRUCTURAL instability is a failure; measured animation-phase churn is not.
    unstable_any = any(v["structural"] for v in stability.values())
    return 0 if (all_ok and not unstable_any) else 1


if __name__ == "__main__":
    sys.exit(main())
