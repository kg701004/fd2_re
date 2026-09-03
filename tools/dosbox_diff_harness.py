#!/usr/bin/env python3
"""UI-VIS-DIFF-HARNESS: one-command DOSBox-X-vs-remake 320x200 pixel diff.

Closes docs/knowledge-base/91-worklist.md's UI-VIS-DIFF-HARNESS item:
"固定同一FD2.SAV／roster／camera／cursor／tick，輸出DOSBox與remake 320×200
pair及pixel diff". Every prior round hand-rolled its own screenshot/crop/
diff logic for a single comparison; this tool is the reusable version.

WHAT THIS TOOL ACTUALLY GUARANTEES (read before trusting a result)
--------------------------------------------------------------------
1. The DOSBox-X-side capture is BYTE-EXACT: `tools/dosbox_diff_harness.sh`
   launches plain `dosbox` (not dosbox-x -- see that script's comment block
   for why) with `[sdl] output=surface` + `[render] scaler=none aspect=false`,
   which pins the SDL window to the emulated video mode's native resolution
   with no scaler/aspect chrome. `raw-screenshot` FAILS CLOSED if the window
   is not exactly 320x200 -- it never silently crops or resizes. Verified
   2026-08-26 against the existing UI-01 title-screen oracle
   (docs/figures/title-original-dosbox.png): this tool's capture reproduced
   an IDENTICAL raw-RGB MD5 (d05b5e19806e5dc3d3e78d199eb74168) to that
   already-closed baseline, which was captured under the (now-removed, see
   memory project_docker_desktop_af_unix_broken) Docker pipeline -- i.e. this
   WSL2-native replacement is provably equivalent to the tool that produced
   the project's only prior byte-exact evidence.
2. The remake-side capture is a *lossless* downsample, not a resize: the
   remake's screenshot hook (FD2_SHOT/FD2_SHOT_FRAME, see
   remake/cmd/fd2/main.go's captureShot) always saves the full 640x400
   logical canvas (logicalW/H = 320x200 native x2, hi-res canvas, see
   main.go). This tool reduces it by taking pixel (2x,2y) of every 2x2
   block -- since the renderer draws each native pixel as a solid 2x2 block,
   this recovers the exact native-resolution image with no interpolation.
   No PIL resize/resample call is used anywhere in this path.
3. The diff itself (mean-abs-diff, exact-pixel-match %, MD5) is over those
   two true-320x200 arrays -- nothing is scaled to match the other first.
4. The remake side is driven with a real FD2_SHOT_PARTY_BINDING (see
   default_party_binding_for_chapter()), not just FD2_CAMP_NODE. Scenes
   gated on a leader/roster identity -- town hub's selector icon
   (remake/cmd/fd2/native_town_ui.go's nativeTownLeaderKey, added
   2026-08-26's task_4845f230), shop/church recipient lists, etc -- fail
   closed with no captured frame if FD2_CAMP_NODE is set alone (correct
   remake-side behavior, but useless for a diff). `town` derives this
   automatically from --chapter-byte; `remake-shot` takes it as an
   explicit --party-binding flag since it composes arbitrary nodes.

WHAT THIS TOOL DOES NOT GUARANTEE
--------------------------------------------------------------------
- It does not know how to reach an arbitrary game screen. `reach_town_hub()`
  below is a fully worked, tested example (title -> LOAD -> chapter-jumped
  save -> town hub); every other scene needs its own step sequence, same as
  every prior E2 round in docs/knowledge-base/58-remake-live-verification-log.md
  has always needed its own key sequence. The reusable parts are the
  low-level primitives (raw_screenshot, remake_shot, diff_frames) and the
  orchestration pattern (launch -> navigate -> capture pair -> diff) --
  compose your own navigate step for a new scene, don't expect one function
  to teleport there.
- A 100% pixel match is NOT guaranteed and should not be assumed to indicate
  a bug in this tool if absent: real-time idle/pulse animation phases can
  differ between the DOSBox-X moment captured and the remake's deterministic
  FD2_SHOT_TOWN_STATE override, and the remake's own compositor may have
  real, still-open discrepancies (this tool is partly *for* finding those).
  Report the statistics; do not round 99.x% up to "byte-exact" in writeups.
- The DOSBox-X-side capture ITSELF is not run-to-run deterministic by
  default, independent of anything on the remake/Go side: repeating
  `reach_town_hub` -> `raw_screenshot` on 5 separately-launched instances
  against the byte-identical patched FD2.SAV produced 4 identical
  `rgb_md5` and 1 different one (2026-08-26 measurement). Diffing the
  outlier showed only 362/64000 pixels differing (0.57%), all inside a
  tight 24x24 bbox over the party leader's standing sprite -- a genuine
  in-game idle-animation frame (visually confirmed: same pose, one frame
  later in a breathing/bob cycle), not a torn/garbled capture or a wrong
  screen. Root cause: nothing pins WHEN in that real-time animation loop
  the screenshot lands. `lock_pulse_phase()`/`reach_town_hub`'s
  `pulse_lock` param (wired into `town` via `KNOWN_PULSE_LOCKS`, on by
  default, `--no-pulse-lock` to disable) mitigates this by polling a
  single scene-specific pixel via the existing `wait-pixel` primitive
  until it matches a known color before capturing -- verified 2026-08-26
  to produce 5/5 identical `rgb_md5` across 5 fresh instances for
  town_ch02/selection 0 (previously 4/5). This is a per-scene pixel/color
  pair, not a universal fix: only `("town_ch02", 0)` has one today: a new
  scene needs its own discriminating pixel picked the same way (diff two
  outlier captures, find a coordinate whose color flips between them).
  Scenes without an entry in `KNOWN_PULSE_LOCKS` fall back to the old
  unlocked behavior and may still show this same class of small,
  animation-region-confined variance.

Usage
-----
    # Chapter-jump-patch a copy of a real FD2.SAV so slot 0's chapter byte
    # points at a given town node, print the round-tripped chapter byte:
    python tools/dosbox_diff_harness.py patch-sav \\
        --src FD2.SAV --dst patched.SAV --slot 0 --chapter-byte 0x01

    # Full town-hub scenario: launch/reuse a diffharness instance, navigate
    # Title -> LOAD -> (patched save) -> town hub, capture both sides,
    # diff, write a side-by-side PNG + JSON report. Automatically supplies
    # FD2_SHOT_PARTY_BINDING (derived from --chapter-byte) and, for
    # (node, selection) pairs in KNOWN_PULSE_LOCKS, locks DOSBox-X capture
    # timing onto a known idle-animation phase for run-to-run determinism:
    python tools/dosbox_diff_harness.py town \\
        --instance diffharness --chapter-byte 0x01 --node town_ch02 \\
        --selection 0 --pulses 0,1,2,3 \\
        --out-prefix .wsl_build/diffharness/report_town_ch02_sel0

    # Low-level primitives (compose your own navigation for a new scene).
    # --party-binding is required for any scene gated on a leader/roster
    # identity (town/shop/church/...) -- see default_party_binding_for_chapter()
    # for how `town` derives it automatically from --chapter-byte:
    python tools/dosbox_diff_harness.py raw-shot --instance diffharness --out out.png
    python tools/dosbox_diff_harness.py remake-shot --node town_ch02 \\
        --town-state 0,0 --party-binding assets/cutscenes/bindings/ch01_pre.json \\
        --out out.png
    python tools/dosbox_diff_harness.py diff --a orig.png --b remake.png \\
        --out-prefix report

See docs/knowledge-base/98-tooling-infrastructure.md for the full design
writeup and docs/knowledge-base/48-dosbox-x-debugger-build.md §11 for a
pointer from the DOSBox-X operating doc.

> **2026-09-03 全工具驗證:待淘汰(deprecated),但保留。**
> 它的比對對象 remake 已於 2026-09-02 移除,所以「DOSBox-X vs remake」這個主要用途沒有對象了。
> 保留的理由是原版側那一半仍然可用且被 doc98 前面幾節引用:raw 320×200 擷取、
> `wait-pixel`、`lock_pulse_phase`(待機動畫相位鎖定)。
> **新工作請改用 `tools/fd2_original_verify.py` ＋ `tools/dosbox_harness.sh`**,它們已取代本檔。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fd2save  # noqa: E402  (local module, see tools/fd2save.py)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
SH_SCRIPT_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "dosbox_diff_harness.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
DIFF_DIR = REPO_ROOT / ".wsl_build" / "diffharness"

# Native-resolution chapter label used throughout docs/knowledge-base/91-worklist.md:
# a slot's chapter byte N displays as "ch(N+1)" (chapter_byte 0x01 -> town_ch02,
# chapter_byte 0x0B -> town_ch12, etc; verified against the LOAD slot-list text
# "第 二 章" for chapter_byte=0x01 during this tool's own validation run).


def default_party_binding_for_chapter(chapter_byte: int) -> str:
    """Map a slot0 chapter byte to the handler binding that carries the
    matching FD2_SHOT_PARTY_BINDING party JOIN state.

    Not a guess: this is the exact chapter_byte->binding pairing
    docs/knowledge-base/58-remake-live-verification-log.md's 2026-08-16
    ch02/ch03/ch04 rounds used by hand (`town_ch03` with
    `FD2_SHOT_PARTY_BINDING=ch02_pre.json`, `town_ch04` with
    `ch03_pre.json`, etc) -- the binding whose own `loadch.chapter` field
    equals chapter_byte is named `ch{chapter_byte:02d}_pre.json` (verified:
    ch01_pre.json has "chapter": 1 and party_order [0,9,4,30,1], which is
    "the party about to enter ch02 battle", i.e. the party actually
    standing in the ch02 town hub -- same reasoning applies for any N).
    Only ch00/ch01/ch02 currently carry a party_order in their `_pre`
    binding (checked 2026-08-26: `grep party_order` on every
    remake/assets/cutscenes/bindings/ch*_pre.json), so this only resolves
    for chapter_byte 0..2 today; later chapters need their own binding
    authored first (remake-side error message says so explicitly if this
    guess is wrong -- it fails closed, not silently).
    """
    return f"assets/cutscenes/bindings/ch{chapter_byte:02d}_pre.json"


def wsl_run(cmd: str, timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess:
    """Run a command string inside `wsl -d Ubuntu bash -c '<cmd>'`.

    check defaults to False: `wsl.exe` itself has been observed (2026-08-26,
    this tool's own development) to intermittently return a nonzero exit
    code even for a trivially-successful bash command (e.g. `... ; true`),
    which is a wrapper-level flakiness unrelated to whether the actual
    remote command succeeded. Callers that care about success verify it
    themselves (parsing stdout, or an explicit follow-up probe like
    ensure_remake_xvfb's xdotool re-check) rather than trusting the process
    return code alone.
    """
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    full = ["wsl", "-d", "Ubuntu", "bash", "-c", cmd]
    return subprocess.run(full, capture_output=True, text=True, timeout=timeout, env=env, check=check)


def sh(args: str, timeout: int = 30) -> str:
    """Invoke tools/dosbox_diff_harness.sh <args> over WSL, return stdout."""
    r = wsl_run(f"bash {SH_SCRIPT_WSL} {args}", timeout=timeout)
    return r.stdout.strip()


# --------------------------------------------------------------------------
# FD2.SAV chapter-jump patching (thin wrapper over tools/fd2save.py)
# --------------------------------------------------------------------------

def patch_sav_chapter(src: Path, dst: Path, slot: int, chapter_byte: int) -> int:
    """Patch one slot's chapter byte in a copy of a real FD2.SAV.

    Returns the round-tripped chapter byte read back from the freshly
    encoded file (fail loudly, not silently, if it doesn't match).
    """
    plain = bytearray(fd2save.decode(src.read_bytes()))
    start, _end = fd2save.slot_bounds(slot)
    meta_off = start + fd2save.ROSTER_SIZE
    plain[meta_off] = chapter_byte
    encoded = fd2save.encode(bytes(plain))
    dst.write_bytes(encoded)
    roundtrip = fd2save.decode(dst.read_bytes())[meta_off]
    if roundtrip != chapter_byte:
        raise RuntimeError(f"chapter byte round-trip mismatch: wrote {chapter_byte:#04x}, read back {roundtrip:#04x}")
    return roundtrip


def to_wsl_path(windows_path: Path) -> str:
    p = str(windows_path.resolve()).replace("\\", "/")
    drive, rest = p.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


# --------------------------------------------------------------------------
# DOSBox-X-side: launch / navigate / raw-capture
# --------------------------------------------------------------------------

def launch_instance(instance: str, sav_file: Path | None, keepalive: int = 3595) -> None:
    """Launch a diffharness instance in the background (WSLg keepalive
    convention, see tools/dosbox_diff_harness.sh header). Caller is
    responsible for giving the process time to boot before navigating."""
    sav_arg = f" {to_wsl_path(sav_file)}" if sav_file else ""
    cmd = f"wsl -d Ubuntu bash {SH_SCRIPT_WSL} launch {instance} {keepalive}{sav_arg}"
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    subprocess.Popen(cmd, shell=True, env=env,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def geometry(instance: str) -> tuple[int, int]:
    w, h, _x, _y = full_geometry(instance)
    return w, h


def full_geometry(instance: str) -> tuple[int, int, int, int]:
    """Returns (width, height, x, y): x/y are the window's ROOT-window
    origin (xdotool getwindowgeometry --shell's X=/Y=), needed because
    wait-pixel (see lock_pulse_phase) probes with `import -window root`,
    not window-relative coordinates like raw-screenshot's `-window $win`."""
    out = sh(f"geometry {instance}")
    w = h = x = y = None
    for line in out.splitlines():
        if line.startswith("WIDTH="):
            w = int(line.split("=", 1)[1])
        elif line.startswith("HEIGHT="):
            h = int(line.split("=", 1)[1])
        elif line.startswith("X="):
            x = int(line.split("=", 1)[1])
        elif line.startswith("Y="):
            y = int(line.split("=", 1)[1])
    if w is None or h is None or x is None or y is None:
        raise RuntimeError(f"could not parse geometry output: {out!r}")
    return w, h, x, y


def send_keys(instance: str, *keys: str) -> None:
    sh(f"send-keys {instance} " + " ".join(keys))


def wait_for_native_geometry(instance: str, max_tries: int = 40, delay: float = 0.5) -> None:
    """Poll until the DOSBox-X window reports exactly 320x200 (the native
    VGA mode-13h resolution this game's gameplay screens run at -- the
    opening cutscene and some transitions run at a higher SVGA mode and
    will not match)."""
    for _ in range(max_tries):
        try:
            if geometry(instance) == (320, 200):
                return
        except RuntimeError:
            pass
        time.sleep(delay)
    raise RuntimeError(f"instance {instance} never reached native 320x200 geometry within {max_tries * delay:.0f}s")


def raw_screenshot(instance: str, out: Path) -> str:
    """Byte-exact 320x200 capture. Returns the raw-RGB MD5 the shell script
    reports (content-only hash, ignores PNG container metadata)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    result = sh(f"raw-screenshot {instance} {to_wsl_path(out)}")
    # "<path> rgb_md5=<hex>"
    for tok in result.split():
        if tok.startswith("rgb_md5="):
            return tok.split("=", 1)[1]
    raise RuntimeError(f"unexpected raw-screenshot output: {result!r}")


def lock_pulse_phase(instance: str, window_xy: tuple[int, int], rgb: tuple[int, int, int],
                      delay: float = 0.15, max_tries: int = 60) -> bool:
    """Poll a single native-320x200-window-relative pixel (window_xy) via
    the root-window `wait-pixel` primitive until it matches rgb, to settle
    DOSBox-X capture timing onto a known idle-animation phase before
    raw_screenshot(). Returns True if it locked, False if it timed out
    (caller decides whether that's fatal -- see cmd_town's --pulse-lock).

    WHY THIS EXISTS (2026-08-26, problem 2 of task_... town-hub diff-harness
    follow-up): repeating `reach_town_hub` -> `raw_screenshot` back-to-back
    on 5 independently-launched instances against the identical patched
    FD2.SAV produced 4 identical rgb_md5 and 1 different one; diffing the
    outlier against the majority showed only 362/64000 pixels differing
    (0.57%), every one of them inside a tight 24x24 bbox exactly over the
    party leader's standing sprite -- a real, in-game idle-animation frame
    (visually confirmed: same character, same pose, one frame later in a
    breathing/bob cycle), not a torn/garbled capture. Root cause: nothing
    in this tool pins WHEN in that real-time animation loop the screenshot
    lands -- `wait_for_native_geometry`'s polling loop and the fixed fade
    sleeps in `reach_town_hub` bound roughly when the town hub becomes
    visible, not which of its (at least 2, empirically) idle-sprite frames
    is showing at that instant. This targets one pixel inside that same
    bbox that was observed to flip between the two outcomes (RGB
    (142,0,0), a chunk of the sprite's red neckerchief only visible in one
    of the two frames) and waits for it, so every call settles on the same
    phase instead of a coin flip.

    LIMITS (2026-08-26, honest): (1) this pixel/color pair was picked by
    inspecting exactly one node/selection/save (town_ch02, ch01_pre.json
    party, selection 0) -- a different scene, party leader sprite, or town
    layout will very likely need its own pixel/color, this is not a
    universal fix; (2) it locks onto whichever phase this specific color
    is present in, not necessarily "the" canonical phase -- if the real
    animation loop has more than 2 frames this only proves the 2 observed
    here are covered, not that every possible frame is enumerable this way;
    (3) `import -window root` full-Xvfb-screen capture, called max_tries
    times at delay-second intervals, is not free -- keep max_tries*delay
    bounded (default 60*0.15s=9s) rather than assuming it always locks
    quickly.
    """
    w, h, x, y = full_geometry(instance)
    if (w, h) != (320, 200):
        raise RuntimeError(f"lock_pulse_phase requires a settled native 320x200 window, got {w}x{h}")
    rx, ry = x + window_xy[0], y + window_xy[1]
    # sh()/wsl_run() do not raise on the shell script's own nonzero exit
    # (see wsl_run's docstring -- wsl.exe's return code is not trustworthy),
    # so success/failure here is read from stdout content, not an exception:
    # cmd_wait_pixel only ever writes to stdout on its "matched" path: the
    # `die` timeout path writes solely to stderr, which sh() discards.
    out = sh(f"wait-pixel {instance} {rx},{ry},{rgb[0]},{rgb[1]},{rgb[2]} {delay} {max_tries}",
             timeout=int(delay * max_tries) + 20)
    return "matched" in out


def reach_town_hub(instance: str, sav_file: Path, escape_taps: int = 30,
                    pulse_lock: tuple[tuple[int, int], tuple[int, int, int]] | None = None) -> bool:
    """Worked example navigate sequence: Title (after skipping the opening
    cutscene) -> Down -> Enter (selects LOAD) -> Enter (loads the only
    populated save slot) -> town hub. `sav_file` must already have its
    chapter byte patched (see patch_sav_chapter) so the LOAD lands on the
    desired town_chNN node -- this is the same chapter-jump technique
    documented for UI-VIS-TOWN variant1/variant2 in
    docs/knowledge-base/91-worklist.md, just automated end to end.

    Sequenced with `wait_for_native_geometry` polling instead of fixed
    sleeps precisely because the opening cutscene's length is not perfectly
    deterministic wall-clock time (doc48 §8.3) -- polling window geometry
    is a cheap, robust proxy for "a mode-13h screen is now showing" that
    doesn't require guessing a sleep duration.

    pulse_lock, when given, is ((x, y), (r, g, b)) in the native 320x200
    frame: after the town hub becomes visible this blocks on
    lock_pulse_phase() before returning, to settle DOSBox-X's real-time
    idle-animation onto a known phase (see that function's docstring for
    why this exists and its scene-specific limits). Returns whether the
    lock succeeded (True if pulse_lock was None -- nothing to lock);
    callers that need the guarantee should check this rather than assume.
    """
    launch_instance(instance, sav_file)
    # Give the instance's own 30s window-search loop room to find the window
    # before we start polling geometry.
    time.sleep(10)

    # Escape-skip the opening logo/cutscene sequence. Escape is a no-op once
    # the title screen's own input loop owns the keyboard, so over-tapping is
    # safe (same tactic as the existing UI-01 title-screen oracle).
    for _ in range(escape_taps):
        send_keys(instance, "Escape")
        time.sleep(0.3)

    wait_for_native_geometry(instance)
    # Title screen defaults to START selected; one Down selects LOAD.
    send_keys(instance, "Down")
    time.sleep(0.5)
    send_keys(instance, "Return")
    time.sleep(2.0)  # fade transition into the save-slot list
    send_keys(instance, "Return")  # confirm slot 1 (cursor default)
    time.sleep(2.0)  # fade transition into the town hub
    wait_for_native_geometry(instance)
    if pulse_lock is None:
        return True
    return lock_pulse_phase(instance, pulse_lock[0], pulse_lock[1])


# --------------------------------------------------------------------------
# remake-side capture
# --------------------------------------------------------------------------

def remake_shot(node: str, town_state: str | None, out: Path, frame: int = 30,
                 xvfb_display: int = 898, extra_env: dict[str, str] | None = None,
                 timeout: int = 75, party_binding: str | None = None) -> None:
    """Run the pre-built remake/fd2-linux-verify binary under a throwaway
    Xvfb display and capture a deterministic frame via FD2_SHOT/FD2_SHOT_FRAME.

    fd2-linux-verify is the same 2026-08-15 Linux build the UI-VIS-TOWN
    variant1/variant2 rounds used (built while Docker was still available;
    Docker itself is gone, see memory project_docker_desktop_af_unix_broken,
    but the already-built binary runs fine directly under WSL2-native Xvfb
    -- no rebuild is needed for pure screenshot capture). It self-terminates
    after saving its shot (see main.go's captureShot), so this call is
    naturally bounded.

    party_binding, when given, sets FD2_SHOT_PARTY_BINDING to a
    remake/assets/cutscenes/bindings/*.json path (relative to the remake/
    dir this call cd's into) so g.partyJoinOrder/g.partyRoster are
    populated the same way production reaches them. Scenes gated on a
    leader/roster identity -- e.g. the town hub's selector icon, see
    remake/cmd/fd2/native_town_ui.go's nativeTownLeaderKey -- fail closed
    (composeNativeTownFrame returns ok=false, FD2_SHOT saves nothing) if
    this is unset, per 2026-08-26's task_4845f230. Pass party_binding=""
    explicitly to opt out (e.g. for scenes that intentionally have no
    party, like the title screen) rather than omitting it.
    """
    remake_dir = to_wsl_path(REPO_ROOT / "remake")
    out_wsl = to_wsl_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    env_lines = [
        f"export DISPLAY=127.0.0.1:{xvfb_display}",
        "export FD2_CAMPAIGN=assets/scenarios/campaign_full.json",
        "export FD2_MUTE=1",
        f"export FD2_SHOT={out_wsl}",
        f"export FD2_SHOT_FRAME={frame}",
        f"export FD2_CAMP_NODE={node}",
    ]
    if town_state:
        env_lines.append(f"export FD2_SHOT_TOWN_STATE={town_state}")
    if party_binding:
        env_lines.append(f"export FD2_SHOT_PARTY_BINDING={party_binding}")
    if extra_env:
        env_lines += [f"export {k}={v}" for k, v in extra_env.items()]
    else:
        # Native FDOTHER/FDTXT/DATO assets are required for the native-UI
        # compositor (town hub, shop, church, ...) to activate at all --
        # without them FD2_SHOT_TOWN_STATE's own "on a native town node"
        # check fails closed (confirmed live 2026-08-26). These are
        # copyrighted game assets, never bundled in the repo; this default
        # points at the canonical WSL2 fd2-run copy that every live-
        # verification round in this project already relies on.
        env_lines += [
            "export FD2_ORIGINAL_FDOTHER=$HOME/fd2-run/FDOTHER.DAT",
            "export FD2_ORIGINAL_FDTXT=$HOME/fd2-run/FDTXT.DAT",
            "export FD2_ORIGINAL_DATO=$HOME/fd2-run/DATO.DAT",
        ]

    # IMPORTANT (found the hard way, 2026-08-26): do NOT background a fresh
    # Xvfb + `kill` it again inside the same `wsl bash -c` call every time
    # this function runs. pkill-then-immediately-restart-on-the-same-display
    # races the socket teardown and intermittently makes Xvfb fail to bind,
    # which leaves fd2-linux-verify's X11 connection hanging until something
    # upstream reaps the whole `wsl.exe` call (empty stdout/stderr, no PNG,
    # no clean error). ensure_remake_xvfb() instead starts the display AT
    # MOST once per process lifetime and leaves it running; this function
    # only ever assumes it is already up.
    ensure_remake_xvfb(xvfb_display)
    script = f"cd {remake_dir} && " + " && ".join(env_lines) + " && ./fd2-linux-verify"
    r = wsl_run(script, timeout=timeout, check=False)
    if not out.exists():
        raise RuntimeError(
            f"remake_shot produced no file at {out}; stdout={r.stdout!r} stderr={r.stderr!r}"
        )


_remake_xvfb_ready: set[int] = set()


def ensure_remake_xvfb(xvfb_display: int) -> None:
    """Idempotently make sure an Xvfb is listening on :xvfb_display, started
    detached (bounded keepalive so it doesn't outlive the WSL distro
    indefinitely if something goes wrong) rather than restarted per-call.

    Verifies with `xdotool getdisplaygeometry` (an actual X11 connection
    attempt), not just `pgrep` (found the hard way,
    2026-08-26: a stale/half-dead Xvfb process from an earlier crashed
    attempt can still match `pgrep`'s pattern while no longer accepting
    connections, which then makes fd2-linux-verify fail with
    "X11: Failed to open display" -- an actual connection probe is the only
    check that can't be fooled by a zombie process).
    """
    if xvfb_display in _remake_xvfb_ready:
        return
    probe = f"DISPLAY=127.0.0.1:{xvfb_display} xdotool getdisplaygeometry >/dev/null 2>&1 && echo yes || echo no"
    alive = wsl_run(probe, timeout=10).stdout.strip()
    if alive != "yes":
        wsl_run(f"pkill -9 -f 'Xvfb :{xvfb_display} ' 2>/dev/null; true", timeout=10)
        wsl_run(
            f"nohup Xvfb :{xvfb_display} -screen 0 1024x768x24 -ac -nolisten local -listen tcp "
            f">/tmp/diffharness_remake_xvfb_{xvfb_display}.log 2>&1 </dev/null & disown; sleep 2; true",
            timeout=15,
        )
        alive = wsl_run(probe, timeout=10).stdout.strip()
        if alive != "yes":
            raise RuntimeError(f"could not bring up a working Xvfb on :{xvfb_display}")
    _remake_xvfb_ready.add(xvfb_display)


def downsample_2x_exact(png_path: Path) -> "list":
    """Load a 640x400 remake shot and losslessly reduce to 320x200 by
    sampling pixel (2x,2y) of every 2x2 block (see module docstring #2).
    Returns a numpy array; raises if the input isn't exactly 640x400."""
    from PIL import Image
    import numpy as np
    im = Image.open(png_path).convert("RGB")
    if im.size != (640, 400):
        raise RuntimeError(f"expected a 640x400 remake shot (logicalW/H x1), got {im.size} from {png_path}")
    arr = np.array(im)
    return arr[0::2, 0::2, :]


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

def diff_frames(orig_png: Path, remake_png: Path, out_prefix: Path,
                 remake_is_2x: bool = True) -> dict:
    from PIL import Image
    import numpy as np

    orig_im = Image.open(orig_png).convert("RGB")
    if orig_im.size != (320, 200):
        raise RuntimeError(f"expected a 320x200 raw DOSBox-X capture, got {orig_im.size} from {orig_png}")
    orig = np.array(orig_im)

    remake = downsample_2x_exact(remake_png) if remake_is_2x else np.array(Image.open(remake_png).convert("RGB"))
    if remake.shape != orig.shape:
        raise RuntimeError(f"shape mismatch after normalization: orig={orig.shape} remake={remake.shape}")

    diff = np.abs(orig.astype(np.int32) - remake.astype(np.int32))
    per_pixel = diff.sum(axis=2)
    mean_abs_diff = float(diff.mean())
    exact_pixel_pct = float((per_pixel == 0).mean() * 100.0)

    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    # Side-by-side (orig | remake | 8x-boosted diff heat), each panel
    # nearest-neighbor upscaled 2x for readability -- upscale is display-only,
    # every statistic above is computed on the untouched 320x200 arrays.
    heat = np.clip(per_pixel * 8, 0, 255).astype(np.uint8)
    heat_rgb = np.stack([heat, np.zeros_like(heat), np.zeros_like(heat)], axis=2)
    panel = np.concatenate([orig, remake, heat_rgb], axis=1)
    side_by_side = Image.fromarray(panel).resize((panel.shape[1] * 2, panel.shape[0] * 2), Image.NEAREST)
    side_by_side_path = out_prefix.with_suffix(".sidebyside.png")
    side_by_side.save(side_by_side_path)

    report = {
        "orig_png": str(orig_png),
        "remake_png": str(remake_png),
        "orig_rgb_md5": hashlib.md5(orig.tobytes()).hexdigest(),
        "remake_native_rgb_md5": hashlib.md5(remake.tobytes()).hexdigest(),
        "mean_abs_diff": mean_abs_diff,
        "exact_pixel_pct": exact_pixel_pct,
        "differing_pixel_count": int((per_pixel != 0).sum()),
        "side_by_side_png": str(side_by_side_path),
    }
    report_path = out_prefix.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_json"] = str(report_path)
    return report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def cmd_patch_sav(args):
    roundtrip = patch_sav_chapter(Path(args.src), Path(args.dst), args.slot, args.chapter_byte)
    print(f"wrote {args.dst}, slot {args.slot} chapter byte = {roundtrip:#04x} (round-trip verified)")


def cmd_raw_shot(args):
    md5 = raw_screenshot(args.instance, Path(args.out))
    print(f"{args.out} rgb_md5={md5}")


def cmd_remake_shot(args):
    remake_shot(args.node, args.town_state, Path(args.out), frame=args.frame,
                party_binding=args.party_binding)
    print(f"wrote {args.out}")


def cmd_diff(args):
    report = diff_frames(Path(args.a), Path(args.b), Path(args.out_prefix), remake_is_2x=not args.no_2x)
    print(json.dumps(report, indent=2))


# Known (node, selection) -> ((x,y), (r,g,b)) pulse-lock pixels, for
# lock_pulse_phase(). Populated empirically (see that function's docstring):
# 2026-08-26 found (40,57)=(142,0,0) -- a fragment of the party leader's red
# neckerchief only visible in one of >=2 idle-sprite frames -- distinguishes
# the two outcomes actually observed across 5 repeated town_ch02/selection0
# captures. Not derived for any other scene yet; cmd_town falls back to no
# lock (old best-effort behavior) for anything not in this table.
KNOWN_PULSE_LOCKS: dict[tuple[str, int], tuple[tuple[int, int], tuple[int, int, int]]] = {
    ("town_ch02", 0): ((40, 57), (142, 0, 0)),
}


def cmd_town(args):
    chapter_byte = int(args.chapter_byte, 0)
    diff_dir = DIFF_DIR
    diff_dir.mkdir(parents=True, exist_ok=True)

    src_sav = Path(args.sav_source) if args.sav_source else None
    if src_sav is None:
        # Pull the canonical fd2-run FD2.SAV over from WSL.
        src_sav = diff_dir / "FD2.SAV.source"
        wsl_run(f"cp $HOME/fd2-run/FD2.SAV {to_wsl_path(src_sav)}")
    patched_sav = diff_dir / f"FD2_chapter{chapter_byte:#04x}.SAV"
    patch_sav_chapter(src_sav, patched_sav, slot=0, chapter_byte=chapter_byte)
    print(f"patched save -> {patched_sav} (slot0 chapter byte {chapter_byte:#04x})")

    pulse_lock = None
    if not args.no_pulse_lock:
        pulse_lock = KNOWN_PULSE_LOCKS.get((args.node, args.selection))
    locked = reach_town_hub(args.instance, patched_sav, pulse_lock=pulse_lock)
    if pulse_lock is not None:
        print(f"DOSBox-X pulse-lock {'succeeded' if locked else 'TIMED OUT (capture may be phase-inconsistent)'} "
              f"-- target {pulse_lock}")
    elif not args.no_pulse_lock:
        print(f"no known pulse-lock pixel for ({args.node!r}, {args.selection}); "
              f"capture may vary run-to-run by a small idle-animation phase (see doc98)")
    orig_png = diff_dir / f"{args.node}_sel{args.selection}_orig.png"
    md5 = raw_screenshot(args.instance, orig_png)
    print(f"DOSBox-X capture -> {orig_png} rgb_md5={md5}")

    party_binding = args.party_binding
    if party_binding is None:
        party_binding = default_party_binding_for_chapter(chapter_byte)
    if party_binding:
        print(f"remake party binding -> {party_binding} "
              f"(pass --party-binding \"\" to opt out)")

    pulses = [int(p) for p in args.pulses.split(",")]
    best = None
    for pulse in pulses:
        remake_png = diff_dir / f"{args.node}_sel{args.selection}_pulse{pulse}_remake.png"
        try:
            remake_shot(args.node, f"{args.selection},{pulse}", remake_png,
                        party_binding=party_binding)
        except Exception as e:
            # A single slow/flaky capture (WSL invocation hiccup, see
            # wsl_run's docstring) should not sink the whole report --
            # print it and move on to the remaining pulses.
            print(f"pulse={pulse}: remake_shot FAILED ({e}); skipping")
            continue
        out_prefix = Path(args.out_prefix + f"_pulse{pulse}") if args.out_prefix else diff_dir / f"{args.node}_sel{args.selection}_pulse{pulse}"
        report = diff_frames(orig_png, remake_png, out_prefix)
        report["pulse"] = pulse
        print(f"pulse={pulse}: mean_abs_diff={report['mean_abs_diff']:.4f} exact_pixel_pct={report['exact_pixel_pct']:.4f}")
        if best is None or report["exact_pixel_pct"] > best["exact_pixel_pct"]:
            best = report
    if best is None:
        raise RuntimeError("every pulse capture failed; no diff report produced")
    print("\nbest match:")
    print(json.dumps(best, indent=2))


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("patch-sav", help="chapter-jump-patch a copy of a real FD2.SAV")
    sp.add_argument("--src", required=True)
    sp.add_argument("--dst", required=True)
    sp.add_argument("--slot", type=int, default=0)
    sp.add_argument("--chapter-byte", required=True, help="hex or decimal, e.g. 0x01")
    sp.set_defaults(func=lambda a: cmd_patch_sav(argparse.Namespace(
        src=a.src, dst=a.dst, slot=a.slot, chapter_byte=int(a.chapter_byte, 0))))

    sp = sub.add_parser("raw-shot", help="byte-exact 320x200 DOSBox-X capture")
    sp.add_argument("--instance", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_raw_shot)

    sp = sub.add_parser("remake-shot", help="deterministic remake capture (downsample yourself, or use `diff`)")
    sp.add_argument("--node", required=True)
    sp.add_argument("--town-state", default=None, help="selection,pulse")
    sp.add_argument("--frame", type=int, default=30)
    sp.add_argument("--party-binding", default=None,
                     help="FD2_SHOT_PARTY_BINDING path (relative to remake/), e.g. "
                          "assets/cutscenes/bindings/ch01_pre.json; required for any "
                          "scene gated on a leader/roster identity (town hub, shop, "
                          "church, ...) or the remake fails closed with no frame; "
                          "omit for scenes that need no party (e.g. title)")
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_remake_shot)

    sp = sub.add_parser("diff", help="diff a raw DOSBox-X PNG against a remake PNG")
    sp.add_argument("--a", required=True, help="320x200 DOSBox-X raw capture")
    sp.add_argument("--b", required=True, help="remake capture (640x400 unless --no-2x)")
    sp.add_argument("--no-2x", action="store_true", help="treat --b as already 320x200")
    sp.add_argument("--out-prefix", required=True)
    sp.set_defaults(func=cmd_diff)

    sp = sub.add_parser("town", help="end-to-end: chapter-jump -> LOAD -> town hub -> capture both sides -> diff")
    sp.add_argument("--instance", default="diffharness")
    sp.add_argument("--chapter-byte", default="0x01", help="slot0 chapter byte to patch in (chapter_byte+1 = chNN)")
    sp.add_argument("--node", default="town_ch02", help="FD2_CAMP_NODE for the remake side")
    sp.add_argument("--selection", type=int, default=0, help="town hub selection 0..5")
    sp.add_argument("--pulses", default="0,1,2,3", help="comma-separated pulse values to try on the remake side")
    sp.add_argument("--sav-source", default=None, help="real FD2.SAV to patch (default: pull from WSL fd2-run)")
    sp.add_argument("--party-binding", default=None,
                     help="override FD2_SHOT_PARTY_BINDING (default: derived from "
                          "--chapter-byte via default_party_binding_for_chapter(); "
                          "pass \"\" to opt out and let the remake fail closed instead)")
    sp.add_argument("--no-pulse-lock", action="store_true",
                     help="skip the DOSBox-X-side idle-animation pulse lock (see "
                          "KNOWN_PULSE_LOCKS/lock_pulse_phase) even if this "
                          "(node, selection) has a known lock pixel; capture may "
                          "then vary run-to-run by a small idle-animation phase")
    sp.add_argument("--out-prefix", default=None)
    sp.set_defaults(func=cmd_town)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
