#!/usr/bin/env python3
"""全章節結構性掃描 (structural full-chapter sweep), targeting
docs/knowledge-base/91-worklist.md's M5 "正常玩法可達性驗證" item.

WHAT THIS TOOL DOES
--------------------------------------------------------------------
For a given chapter N (1-based, matching the LOAD-screen "第 N 章" label),
this tool automates a best-effort structural pass/fail check:

  1. Chapter-jump-patches a COPY of a real FD2.SAV (tools/fd2save.py
     set_slot_chapter) so slot 0 lands on chapter N, optionally padding the
     roster with synthetic-but-constructor-accurate members
     (append_roster_members) when docs/data/chapter_beats/ch*_post.json's
     cumulative `join` beat count for chapters before N exceeds what the
     source save's roster already has (same method a prior round used by
     hand to derive the ch11-22/23-29 roster-growth breakdown -- see
     estimate_roster_size()).
  2. Boots an ISOLATED tools/dosbox_harness.sh instance (never touches the
     doc48 §8.4 canonical `dbg`/:99 session or another agent's harness
     instance), overwrites its workdir's FD2.SAV with the patched save.
  3. Skips the opening cutscene/logo (Escape taps), LOADs the patched save.
  4. Repeatedly probes a verified live global -- the battle unit-record
     array pointer, DAT_00053a45, live linear address 0x1EFA45 under the
     DS-like flat selector 0178 (see docs/knowledge-base/58-remake-live-
     verification-log.md "續" entries around 2026-08-21/24 for the
     native+0x19C000=live delta derivation and repeated cross-session
     confirmation of this address) -- to distinguish "currently inside a
     battle" (pointer holds a plausible heap address) from "story/town/other
     node" (pointer reads 0 or an implausible value). This is an ENGINE-
     LEVEL structural signal, not a screenshot heuristic -- matching this
     task's brief that the sweep should check structural integrity, not
     emulate human judgement of what's on screen.
  5. If in battle: scans the unit-record array (stride 0x50, camp byte at
     +6 -- 2=ally/0=enemy, confirmed in doc58 "續六十二"/"續六十三") to find
     the enemy slots, writes the enemy-death signature (+5=0x01, ALSO
     confirmed in the same rounds -- NOT the same value as the ally
     "Acted" flag 0x80, so this tool never touches ally records) to every
     enemy slot found, then plays the documented End-Turn->YES shortcut
     (Enter opens the command ring, Down selects END, Enter confirms END,
     Enter confirms the "end this turn?" Yes/No prompt) that doc58 "續六十
     二" first proved triggers the real win-condition scan (native 0x205be)
     for ch27. This is a REUSE of an already-live-verified technique, not a
     new invention -- but it has only ever been proven for ch27; every other
     chapter is genuinely unverified territory (see Honesty section below).
  6. If not in battle: falls back to a generic bounded "advance" loop
     (alternating single Enter/Escape taps with screenshots, watching for a
     battle to appear or for the screen to stall) -- there is no established,
     chapter-general "reach the battle" input sequence in this project's
     knowledge base (every documented navigate sequence, e.g.
     reach_town_hub() in tools/dosbox_diff_harness.py, is scene-specific),
     so this is deliberately the weakest, most heuristic part of the tool.
  7. THE PRIMARY PASS SIGNAL is read back from disk, not inferred from
     pixels: after the sequence, this tool copies the harness workdir's
     FD2.SAV back out, decodes it, and checks whether slot 0's raw chapter
     byte advanced past what was patched in. A native autosave firing with
     a higher chapter byte is the same ground-truth signal this project's
     own live-verification rounds have used throughout (e.g. doc58 "續
     二十三/二十四": "存檔位1標題...變成...火焰的審判...確認FD2.SAV已被原生
     代碼autosave覆寫成ch25"). This is far more reliable than trying to OCR
     or pixel-match an unknown chapter's transition screen.
  8. Always screenshots at each major step and tears its own harness
     instance down before returning, regardless of verdict.

HONESTY / KNOWN LIMITS (read before trusting a "pass")
--------------------------------------------------------------------
- The battle-detection pointer (0x1EFA45) and the enemy-scan/death-signature
  constants (stride 0x50, +5/+6) were derived and validated ONLY against
  ch27 across many prior live rounds. This tool assumes -- UNVERIFIED for
  any chapter but ch27 -- that the same global/layout is reused by every
  chapter's battle. If a chapter's battle uses a different array or record
  layout, the scan will most likely just find 0 enemy slots (visible in the
  log as enemies_found=0) rather than corrupting anything, because writes
  only happen to slots this tool itself classified camp==0 from a live read
  -- but this has not been cross-checked against a second chapter's real
  battle memory layout, only inferred to generalize.
- The generic advance-loop (step 6) has NO chapter-specific knowledge. Many
  chapters will very likely not fit it (unique scripted events, chapters
  that need specific items/state, chapters requiring more real roster
  members than the synthetic padding can safely emulate, boss mechanics
  that don't share the ch27 win-condition path, etc). Such chapters are
  expected to come back "needs_manual_followup", not a false pass.
- A `pass` verdict means "chapter-jump landed, battle-or-not was resolved
  by this tool's mechanism, and the save's chapter byte advanced" -- it is
  NOT a claim that the chapter's actual story/battle content was exercised
  the way a human player would experience it. This is a structural sweep,
  matching the task brief, not a playthrough.
- Synthetic roster padding (append_roster_members) does not run the Go
  equipment-recalc tail (see tools/fd2save.py module docstring) -- padded
  units' equipped combat stats are inaccurate. This has not been observed
  to break anything in this tool's own validation (ch27 uses a real,
  unpadded save), but is untested for a genuinely padded chapter.

USAGE
--------------------------------------------------------------------
    # Single chapter:
    python tools/fd2_chapter_sweep.py sweep --chapter 27 \\
        --source-sav .wsl_build/chapter_sweep/FD2_source.SAV

    # Range (sequential; use --parallel-with to run two chapters at once
    # against two independent harness instances from two separate CLI calls):
    python tools/fd2_chapter_sweep.py sweep --from 1 --to 10 \\
        --source-sav .wsl_build/chapter_sweep/FD2_source.SAV

Results are appended to a JSON log (--results, default
.wsl_build/chapter_sweep/results.json) and printed as a one-line summary
per chapter. See docs/knowledge-base/99-chapter-sweep-results.md for the
human-readable writeup this tool's output feeds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
SH_SCRIPT_WSL = "/mnt/c/" + str(REPO_ROOT / "tools" / "dosbox_harness.sh").replace("\\", "/").split(":", 1)[1].lstrip("/")
SWEEP_DIR = REPO_ROOT / ".wsl_build" / "chapter_sweep"
CHAPTER_BEATS_DIR = REPO_ROOT / "docs" / "data" / "chapter_beats"

# --- Verified live addresses / layout constants (see module docstring for
# provenance -- all from docs/knowledge-base/58-remake-live-verification-log.md
# "續六十二"/"續六十三" and the surrounding 0x19C000 delta-derivation rounds) ---
DATA_SELECTOR = "0178"
BATTLE_ARRAY_PTR_LIVE = 0x1EFA45   # DAT_00053a45: pointer to the current battle unit-record array (0/garbage outside battle)
UNIT_STRIDE = 0x50
UNIT_ACTED_OFFSET = 0x05           # enemy death signature: write 0x01 here
UNIT_CAMP_OFFSET = 0x06            # 2 = ally, 0 = enemy (doc58 續六十二 §2)
ALLY_ACTED_VALUE = 0x80            # NOT written by this tool -- listed only so nobody confuses it with 0x01
ENEMY_DEATH_VALUE = 0x01
PLAUSIBLE_PTR_MIN = 0x10000
PLAUSIBLE_PTR_MAX = 0xFFFFFF
MAX_ENEMY_SCAN_SLOTS = 96          # ch27 needed 63 (16..62 inclusive); generous headroom
CONSECUTIVE_ZERO_STOP = 4          # stop scanning after this many all-zero records once >=1 enemy found


def wsl_run(cmd: str, timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess:
    """See tools/dosbox_diff_harness.py's wsl_run docstring: wsl.exe's own
    return code is not trustworthy, callers check stdout content instead."""
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    full = ["wsl", "-d", "Ubuntu", "bash", "-c", cmd]
    return subprocess.run(full, capture_output=True, text=True, timeout=timeout, env=env, check=check)


def sh(args: str, timeout: int = 30) -> str:
    r = wsl_run(f"bash {SH_SCRIPT_WSL} {args}", timeout=timeout)
    return r.stdout.strip()


def to_wsl_path(windows_path: Path) -> str:
    p = str(windows_path.resolve()).replace("\\", "/")
    drive, rest = p.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


# --------------------------------------------------------------------------
# harness primitives (thin wrappers over tools/dosbox_harness.sh)
# --------------------------------------------------------------------------

def launch_instance(name: str, keepalive: int = 3600) -> None:
    cmd = f"wsl -d Ubuntu bash {SH_SCRIPT_WSL} launch {name} {keepalive}"
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    subprocess.Popen(cmd, shell=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def teardown(name: str) -> str:
    return sh(f"teardown {name}", timeout=30)


def status() -> str:
    return sh("status", timeout=20)


def screenshot(name: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    sh(f"screenshot {name} {to_wsl_path(out)}", timeout=20)
    return out


def send_keys(name: str, *keys: str) -> None:
    sh(f"send-keys {name} " + " ".join(keys), timeout=20)


def enter_debugger(name: str) -> None:
    sh(f"enter-debugger {name}", timeout=20)


def debugger_cmd(name: str, text: str) -> None:
    sh(f"debugger-cmd {name} {text}", timeout=20)


def capture_pane(name: str, session_prefix: str = "harness-", history: int = 0) -> str:
    """Raw tmux capture-pane text for a harness instance's session, on the
    harness's own private socket (fd2harness) -- never the canonical `dbg`
    session's default-socket pane."""
    session = f"{session_prefix}{name}"
    extra = f"-S -{history}" if history else ""
    r = wsl_run(f"tmux -L fd2harness capture-pane -t {session} -p {extra}", timeout=15)
    return r.stdout


def workdir_for(name: str) -> str:
    return f"$HOME/fd2-run-harness-{name}"


def overwrite_save(name: str, patched_sav: Path) -> None:
    """Copy a Windows-side patched FD2.SAV into a launched instance's
    workdir. Safe to do any time before the player selects LOAD (the game
    only reads FD2.SAV off disk at that moment)."""
    wsl_run(f"cp {to_wsl_path(patched_sav)} {workdir_for(name)}/FD2.SAV", timeout=20)


def pull_save(name: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    wsl_run(f"cp {workdir_for(name)}/FD2.SAV {to_wsl_path(out)}", timeout=20)
    return out


# --------------------------------------------------------------------------
# debugger memory read/write
# --------------------------------------------------------------------------

_HEX_LINE_RE = re.compile(
    r"^(?P<sel>[0-9A-Fa-f]{4}):(?P<addr>[0-9A-Fa-f]{8})\s+(?P<bytes>(?:[0-9A-Fa-f]{2}\s+){1,16})",
    re.MULTILINE,
)


def read_mem(name: str, addr: int, min_bytes: int = 16, retries: int = 2) -> bytes | None:
    """Read up to ~112 bytes starting at `addr` via the debugger's Data
    view panel. Returns None if the address never appeared in the captured
    pane text after retrying (debugger console stale-pane issue, see
    doc48 §8.4's known `tmux capture-pane` staleness gotcha) -- callers
    must treat None as "could not read", not as "zero bytes"."""
    for attempt in range(retries + 1):
        debugger_cmd(name, f"D {DATA_SELECTOR}:{addr:X}")
        time.sleep(0.3)
        text = capture_pane(name)
        collected: dict[int, int] = {}
        for m in _HEX_LINE_RE.finditer(text):
            line_addr = int(m.group("addr"), 16)
            byte_toks = m.group("bytes").split()
            for i, tok in enumerate(byte_toks):
                collected[line_addr + i] = int(tok, 16)
        if collected:
            lo = min(collected)
            hi = max(collected)
            if lo <= addr and (hi - addr + 1) >= min(min_bytes, hi - lo + 1):
                out = bytearray()
                ok = True
                for i in range(addr, addr + min_bytes):
                    if i not in collected:
                        ok = False
                        break
                    out.append(collected[i])
                if ok:
                    return bytes(out)
        time.sleep(0.4)
    return None


def write_byte(name: str, addr: int, value: int) -> None:
    debugger_cmd(name, f"SMV {addr:X} {value:02X}")
    time.sleep(0.1)


# --------------------------------------------------------------------------
# battle detection / enemy scan / mass-kill / end-turn
# --------------------------------------------------------------------------

def read_battle_array_base(name: str) -> int | None:
    """Read DAT_00053a45 (live 0x1EFA45) and return its value if it looks
    like a plausible heap pointer, else None (treated as "not in battle").
    This is a heuristic range check, not a proof -- see module docstring."""
    raw = read_mem(name, BATTLE_ARRAY_PTR_LIVE, min_bytes=4)
    if raw is None:
        return None
    val = raw[0] | (raw[1] << 8) | (raw[2] << 16) | (raw[3] << 24)
    if PLAUSIBLE_PTR_MIN <= val <= PLAUSIBLE_PTR_MAX:
        return val
    return None


def scan_enemy_slots(name: str, base: int, log: list[str]) -> list[int]:
    """Sequentially read each candidate unit record's camp byte (+6) and
    return the linear addresses of every record classified as enemy
    (camp==0). Ally records (camp==2) are read but never written. Stops
    early once CONSECUTIVE_ZERO_STOP fully-zero (unpopulated) records are
    seen in a row after at least one enemy has already been found."""
    enemies: list[int] = []
    zero_streak = 0
    for k in range(MAX_ENEMY_SCAN_SLOTS):
        rec_addr = base + k * UNIT_STRIDE
        raw = read_mem(name, rec_addr, min_bytes=8)
        if raw is None:
            log.append(f"scan slot{k}: read failed at {rec_addr:#x}, stopping scan")
            break
        camp = raw[UNIT_CAMP_OFFSET]
        if all(b == 0 for b in raw[:8]):
            zero_streak += 1
            if enemies and zero_streak >= CONSECUTIVE_ZERO_STOP:
                log.append(f"scan slot{k}: {CONSECUTIVE_ZERO_STOP} consecutive zero records, stopping")
                break
            continue
        zero_streak = 0
        if camp == 0:
            enemies.append(rec_addr)
    log.append(f"scan_enemy_slots: base={base:#x} scanned<= {MAX_ENEMY_SCAN_SLOTS} slots, enemies_found={len(enemies)}")
    return enemies


def mass_kill_enemies(name: str, enemy_addrs: list[int], log: list[str]) -> int:
    written = 0
    for addr in enemy_addrs:
        write_byte(name, addr + UNIT_ACTED_OFFSET, ENEMY_DEATH_VALUE)
        written += 1
    log.append(f"mass_kill_enemies: wrote death signature to {written} slot(s)")
    return written


def confirm_end_turn(name: str, shots_dir: Path, log: list[str]) -> Path:
    """Doc58 續六十二's proven End-Turn->YES shortcut: Enter opens the
    command ring, Down selects END, Enter confirms END, Enter confirms the
    Yes/No 'end this turn?' prompt (Yes is the default highlight)."""
    send_keys(name, "Return")
    time.sleep(0.6)
    send_keys(name, "Down")
    time.sleep(0.4)
    send_keys(name, "Return")
    time.sleep(0.6)
    send_keys(name, "Return")
    time.sleep(2.0)
    log.append("confirm_end_turn: sent Enter(open ring)->Down(END)->Enter(confirm)->Enter(YES)")
    return screenshot(name, shots_dir / "post_end_turn.png")


# --------------------------------------------------------------------------
# generic (non-battle) advance loop
# --------------------------------------------------------------------------

def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# A generic node this project has repeatedly found to be either a pure
# dialogue/menu screen (Enter/Escape advances it) OR a walkable town/camp
# map (see doc58 "續五十九": the SAME chapter's post-load node has been
# observed, across different session runs, as either a walkable map with
# tents/fence/NPCs or an icon-style menu -- this project has never found a
# single reliable discriminator). This key cycle deliberately mixes both
# vocabularies -- Enter/Escape for dialogue, arrow taps for walking toward
# roughly the middle/bottom/right of the visible map where prior live
# rounds have found exits/fence-gaps -- rather than committing to only one,
# since neither this tool nor any prior round has a reliable way to tell
# which kind of node it landed on ahead of time.
_ADVANCE_KEY_CYCLE = ["Return", "Down", "Right", "Return", "Escape", "Right", "Down", "Return"]

# Chapter-specific navigate hints: an explicit key list to try BEFORE
# falling back to _ADVANCE_KEY_CYCLE, for the handful of chapters this
# project has deep prior live-verification knowledge of. NOT a claim that
# this generalizes -- exactly the same caveat as
# tools/dosbox_diff_harness.py's reach_town_hub() (scene-specific, hand-
# composed). ch27's post-load node has been observed as a WALKABLE camp
# map (tents/fence, no text menu) in this tool's own 2026-08-27 validation
# run -- pure directional taps (no Enter) for the first stretch, to avoid
# what was observed to happen otherwise: an early Enter interacts with the
# tavern (酒店) NPC and drops into its roster/character-sheet browser
# instead of continuing toward the camp's exit gate.
KNOWN_NAVIGATE_HINTS: dict[int, list[str]] = {
    # doc58 續五十七/五十八/六十二's most-repeated working ch27 sequence for
    # the icon-style camp menu variant ("軍營Right×3→出口→YES"), tried
    # first; falls through to a walkable-map-style probe (several short
    # directional bursts in different directions, since this tool's own
    # 2026-08-27 validation runs observed the WALKABLE variant instead and
    # a single fixed direction just walks into whichever NPC tent is
    # nearest) if the icon sequence doesn't land in a battle.
    27: ["Right", "Right", "Right", "Return", "Return"]
        + ["Escape", "Down", "Down", "Right", "Right", "Return"]
        + ["Escape", "Right", "Right", "Right", "Down", "Return"]
        + ["Escape", "Down", "Down", "Down", "Return"],
}


def advance_generic(name: str, shots_dir: Path, log: list[str], max_steps: int = 48,
                     stall_limit: int = 10, hint_keys: list[str] | None = None) -> dict:
    """Bounded, chapter-agnostic advance loop: cycles _ADVANCE_KEY_CYCLE
    (single taps, never mashed -- per the established dialogue-skip
    technique), screenshotting and checking the battle-array pointer after
    every step. Returns as soon as a battle is detected. Flags a 'stall' if
    the screenshot hash repeats stall_limit times in a row (possible hang,
    or just a screen this tool's generic key cycle doesn't know how to
    advance -- honestly reported as ambiguous, not asserted as a crash)."""
    last_hash = None
    stall_count = 0
    max_stall_seen = 0
    if hint_keys:
        log.append(f"advance_generic: using a chapter-specific navigate hint ({len(hint_keys)} keys) before falling back to the generic cycle")
    for step in range(max_steps):
        base = read_battle_array_base(name)
        if base is not None:
            log.append(f"advance_generic: battle detected at step {step} (array base {base:#x})")
            return {"battle_base": base, "steps_used": step, "max_stall_seen": max_stall_seen}
        if hint_keys and step < len(hint_keys):
            key = hint_keys[step]
        else:
            key = _ADVANCE_KEY_CYCLE[step % len(_ADVANCE_KEY_CYCLE)]
        send_keys(name, key)
        time.sleep(1.0)
        shot = screenshot(name, shots_dir / f"advance_{step:03d}.png")
        h = file_md5(shot)
        if h == last_hash:
            stall_count += 1
        else:
            stall_count = 0
        max_stall_seen = max(max_stall_seen, stall_count)
        last_hash = h
        if stall_count >= stall_limit:
            log.append(f"advance_generic: screen stalled for {stall_count} consecutive steps at step {step}, stopping early")
            return {"battle_base": None, "steps_used": step + 1, "max_stall_seen": max_stall_seen, "stalled": True}
    log.append(f"advance_generic: exhausted {max_steps} steps without finding a battle")
    return {"battle_base": None, "steps_used": max_steps, "max_stall_seen": max_stall_seen, "stalled": False}


# --------------------------------------------------------------------------
# save preparation
# --------------------------------------------------------------------------

def estimate_roster_size(chapter_n: int) -> int:
    """Count cumulative `join` beats across ch01_post .. ch(N-1)_post, +1
    for the fixed leader (record0, never a join beat -- see
    tools/fd2save.py). Mirrors the method a prior round used by hand to
    derive the ch11-22/23-29 roster-growth breakdown (see
    docs/knowledge-base/91-worklist.md, 2026-08-26 UI-11 entry)."""
    count = 1
    for ch in range(1, chapter_n):
        path = CHAPTER_BEATS_DIR / f"ch{ch:02d}_post.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for beat in data.get("beats", []):
            if beat.get("op") == "join":
                count += 1
    return count


def prepare_chapter_save(source_sav: Path, chapter_n: int, out_sav: Path, slot: int, log: list[str],
                          pad_roster: bool = True) -> Path:
    plain = fd2save.decode(source_sav.read_bytes())
    raw_chapter = chapter_n - 1
    plain = fd2save.set_slot_chapter(plain, slot, raw_chapter)

    start, _ = fd2save.slot_bounds(slot)
    meta_start = start + fd2save.ROSTER_SIZE
    current_count = plain[meta_start + 1]
    wanted = estimate_roster_size(chapter_n)
    if not pad_roster:
        log.append(f"prepare_chapter_save: --no-roster-pad, keeping source roster_count={current_count} unchanged "
                    f"(estimate_roster_size({chapter_n})={wanted})")
    elif wanted > current_count:
        existing_ids = set(fd2save.roster_character_ids(plain, slot, current_count))
        pad_ids = [cid for cid in range(32) if cid not in existing_ids][: wanted - current_count]
        if pad_ids:
            try:
                plain = fd2save.append_roster_members(plain, slot, pad_ids)
                log.append(f"prepare_chapter_save: padded roster {current_count}->{current_count + len(pad_ids)} "
                            f"with synthetic ids {pad_ids} (estimate_roster_size({chapter_n})={wanted})")
            except ValueError as e:
                log.append(f"prepare_chapter_save: roster padding skipped ({e})")
        else:
            log.append(f"prepare_chapter_save: wanted {wanted} roster members but no unused char ids available to pad with")
    else:
        log.append(f"prepare_chapter_save: source roster_count={current_count} already >= estimate_roster_size({chapter_n})={wanted}, no padding")

    stored = fd2save.encode(plain)
    fd2save.decode(stored)  # round-trip self-check, same discipline as fd2save.py's own --out path
    out_sav.parent.mkdir(parents=True, exist_ok=True)
    out_sav.write_bytes(stored)
    return out_sav


def read_slot_chapter(sav_path: Path, slot: int) -> int | None:
    try:
        plain = fd2save.decode(sav_path.read_bytes())
    except (ValueError, OSError):
        return None
    start, _ = fd2save.slot_bounds(slot)
    return plain[start + fd2save.ROSTER_SIZE]


# --------------------------------------------------------------------------
# one chapter's sweep
# --------------------------------------------------------------------------

def sweep_chapter(chapter_n: int, source_sav: Path, results_dir: Path,
                   instance_prefix: str = "sweep", slot: int = 0,
                   boot_wait_s: int = 12, escape_taps: int = 30,
                   keepalive: int = 1200, teardown_after: bool = True,
                   pad_roster: bool = True, use_navigate_hints: bool = True) -> dict:
    name = f"{instance_prefix}{chapter_n:02d}"
    chapter_dir = results_dir / f"ch{chapter_n:02d}"
    shots_dir = chapter_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    t0 = time.time()
    verdict = "unknown"
    detail = ""

    try:
        patched_sav = chapter_dir / "patched.SAV"
        prepare_chapter_save(source_sav, chapter_n, patched_sav, slot, log, pad_roster=pad_roster)

        launch_instance(name, keepalive=keepalive)
        time.sleep(boot_wait_s)

        overwrite_save(name, patched_sav)
        log.append(f"launched instance '{name}', overwrote workdir FD2.SAV with patched save")

        for _ in range(escape_taps):
            send_keys(name, "Escape")
            time.sleep(0.3)
        screenshot(name, shots_dir / "01_title.png")

        send_keys(name, "Down")
        time.sleep(0.5)
        send_keys(name, "Return")  # select LOAD
        time.sleep(2.0)
        send_keys(name, "Return")  # confirm the save slot (cursor defaults to slot 0)
        time.sleep(2.5)
        screenshot(name, shots_dir / "02_post_load.png")

        enter_debugger(name)
        time.sleep(0.5)
        base = read_battle_array_base(name)
        # Leave the debugger console and resume the emulator loop before
        # doing anything else -- RUN, not just closing the TUI overlay, per
        # doc48 §8.4's "confirm (Running) before sending game keys again".
        debugger_cmd(name, "RUN")
        time.sleep(0.3)

        if base is None:
            log.append("post-load state: battle array pointer not plausible -> treating as story/town node, using generic advance loop")
            hint = KNOWN_NAVIGATE_HINTS.get(chapter_n) if use_navigate_hints else None
            adv = advance_generic(name, shots_dir, log, hint_keys=hint)
            base = adv["battle_base"]

        if base is not None:
            log.append(f"battle confirmed, array base={base:#x}")
            enter_debugger(name)
            time.sleep(0.5)
            enemy_addrs = scan_enemy_slots(name, base, log)
            if enemy_addrs:
                mass_kill_enemies(name, enemy_addrs, log)
            debugger_cmd(name, "RUN")
            time.sleep(0.5)
            screenshot(name, shots_dir / "03_pre_end_turn.png")
            if enemy_addrs:
                confirm_end_turn(name, shots_dir, log)
            else:
                log.append("no enemy slots found by scan -- skipping End Turn shortcut, flagging as anomaly")
        else:
            log.append("generic advance loop never detected a battle within its step budget")

        time.sleep(1.5)
        screenshot(name, shots_dir / "04_final.png")

        final_sav = pull_save(name, chapter_dir / "final.SAV")
        final_chapter_raw = read_slot_chapter(final_sav, slot)
        patched_chapter_raw = chapter_n - 1
        log.append(f"final slot{slot} raw chapter byte = {final_chapter_raw!r} (patched in as {patched_chapter_raw:#04x})")

        if final_chapter_raw is not None and final_chapter_raw > patched_chapter_raw:
            verdict = "pass"
            detail = f"chapter byte advanced {patched_chapter_raw:#04x} -> {final_chapter_raw:#04x} (native autosave confirmed clean transition)"
        elif base is not None and enemy_addrs:
            verdict = "anomaly"
            detail = "battle detected, enemies mass-killed, End Turn confirmed, but chapter byte did not advance (montage may not have autosaved within this run's window, or the win condition differs from ch27's)"
        elif base is not None:
            verdict = "anomaly"
            detail = "battle detected but the enemy scan found 0 enemy slots (unexpected record layout for this chapter?) -- needs manual follow-up"
        else:
            verdict = "needs_manual_followup"
            detail = "generic advance loop never found a battle and chapter byte did not advance; chapter may need a bespoke navigate sequence"

    except Exception as e:  # noqa: BLE001 - sweep must never crash the whole run
        verdict = "tool_error"
        detail = f"{type(e).__name__}: {e}"
        log.append(f"EXCEPTION: {detail}")
    finally:
        if teardown_after:
            try:
                teardown(name)
                log.append(f"tore down instance '{name}'")
            except Exception as e:  # noqa: BLE001
                log.append(f"teardown FAILED: {e}")

    result = {
        "chapter": chapter_n,
        "instance": name,
        "verdict": verdict,
        "detail": detail,
        "duration_s": round(time.time() - t0, 1),
        "log": log,
        "shots_dir": str(shots_dir),
    }
    (chapter_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def append_results(results_path: Path, result: dict) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    all_results = []
    if results_path.exists():
        try:
            all_results = json.loads(results_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            all_results = []
    all_results = [r for r in all_results if r.get("chapter") != result["chapter"]]
    all_results.append(result)
    all_results.sort(key=lambda r: r["chapter"])
    results_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_sweep(args):
    source_sav = Path(args.source_sav)
    results_dir = Path(args.results_dir)
    results_path = Path(args.results)

    chapters = [args.chapter] if args.chapter else list(range(args.from_, args.to + 1))
    for n in chapters:
        print(f"=== chapter {n:02d} ===")
        result = sweep_chapter(n, source_sav, results_dir, instance_prefix=args.instance_prefix,
                                keepalive=args.keepalive, teardown_after=not args.no_teardown,
                                pad_roster=not args.no_roster_pad,
                                use_navigate_hints=not args.no_navigate_hints)
        append_results(results_path, result)
        print(f"ch{n:02d}: {result['verdict']} ({result['duration_s']}s) -- {result['detail']}")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sweep", help="sweep one chapter or a range of chapters")
    sp.add_argument("--chapter", type=int, default=None, help="single chapter number (1-based)")
    sp.add_argument("--from", dest="from_", type=int, default=None)
    sp.add_argument("--to", type=int, default=None)
    sp.add_argument("--source-sav", required=True, help="real FD2.SAV to chapter-jump-patch a copy of")
    sp.add_argument("--results-dir", default=str(SWEEP_DIR), help="per-chapter shots/logs/result.json go under here")
    sp.add_argument("--results", default=str(SWEEP_DIR / "results.json"), help="aggregate JSON results file")
    sp.add_argument("--instance-prefix", default="sweep")
    sp.add_argument("--keepalive", type=int, default=1200)
    sp.add_argument("--no-teardown", action="store_true", help="leave the harness instance running after (debugging this tool itself)")
    sp.add_argument("--no-roster-pad", action="store_true",
                     help="keep the source save's roster as-is instead of padding with synthetic members "
                          "(use for a chapter whose real save already has a validated-working roster, e.g. ch27)")
    sp.add_argument("--no-navigate-hints", action="store_true",
                     help="skip KNOWN_NAVIGATE_HINTS even for chapters that have one, and go straight to the generic advance loop")
    sp.set_defaults(func=cmd_sweep)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "sweep" and args.chapter is None and (args.from_ is None or args.to is None):
        build_parser().error("sweep needs either --chapter N or both --from A --to B")
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
