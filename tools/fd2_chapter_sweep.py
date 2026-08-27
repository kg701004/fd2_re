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
REAL_BATTLE_MIN_ENEMIES = 2        # 2026-08-27 "winverify" round: the troop-selection screen that precedes
                                    # the real battle already has a plausible battle-array pointer with a
                                    # transient 1-record placeholder -- attempt_camp_exit() must not mistake
                                    # that for the real battle (see its docstring). No FD2 battle in this
                                    # project's records has ever had only 1 enemy, so >=2 is the threshold.


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


def confirm_end_turn(name: str, shots_dir: Path, log: list[str], enemy_addrs: list[int] | None = None) -> Path:
    """Doc58 續六十二's proven End-Turn->YES shortcut: move the cursor to an
    empty tile, Enter opens the command ring, Down selects END, Enter
    confirms END, Enter confirms the Yes/No 'end this turn?' prompt (Yes is
    the default highlight).

    2026-08-27 "winverify" fix #1: 續六十二's own writeup explicitly redoes
    the 47-slot death-signature write a SECOND time while sitting at the
    "end this turn?" Yes/No prompt, immediately before confirming YES ("在
    這個確認框停留的當下先進debugger補做一次kill_all.sh確保47格死亡signature
    仍全部有效"). This tool's first version only wrote the signature once
    (mass_kill_enemies(), before the ring was even opened) and never
    reproduced 續六十二's positive result even after the camp-exit/dialogue
    fix above got a genuine full-roster battle (ch27 live-verified: 50
    enemy records mass-killed, End Turn confirmed, chapter byte still did
    NOT advance -- .wsl_build/chapter_sweep_v3/ch27/result.json).

    2026-08-27 "winverify" fix #2, found AFTER fix #1 still didn't work:
    this function was missing 續六十二's FIRST step entirely -- "移動游標到
    空地格" (move the cursor to an empty tile) BEFORE opening the ring. The
    cursor defaults onto a party unit on this screen, and pressing Return
    there does something else (its HP changed 823->990 in one live test,
    i.e. it interacted with/selected a different unit) instead of opening
    the system ring. Confirmed live (instance 'probe4', ch27): a single
    `Up` reliably lands on empty ground one tile above the party cluster --
    the HUD box goes blank (only "A+05 D+00" terrain bonus, no character
    portrait/HP), matching doc58's documented empty-tile signal exactly --
    and Enter from there opens the real 4-direction system ring. This is
    genuinely chapter/deployment-layout-specific (a single `Up` happened to
    work for ch27's specific unit cluster), but it is far closer to correct
    than never moving the cursor at all, which guaranteed failure every
    time. Also confirmed live: the ring does NOT default to END highlighted
    (contradicts an earlier, less-careful doc58 round) -- Enter alone from
    the freshly-opened ring opens the "UP" (system menu) suboption instead;
    Down really is required first, exactly as 續六十二 documented.

    2026-08-27 "branchcheck" round -- IMPORTANT, read before suspecting save
    contamination again: a dispatch this round hypothesized that ch02/ch12
    landing on "the same 悠妮 character-card infinite loop" as ch27 (as
    prepare_chapter_save() reused a single ch27-flavored source save for
    every chapter) meant table_post[] dispatch was being routed with leaked
    ch26/29-specific state. This was checked two ways and REFUTED both times:
      1. Static: docs/data/fd2_native_chapter_slot_restore_ida.txt's "0x25EBB
         的章節槽載入分支" section (already-proven IDA disassembly) shows LOAD
         copying metadata+0 -- i.e. exactly the byte set_slot_chapter()
         writes -- into `[0x53C03]`, and doc35 §9.11 already proved
         `[0x53C03]` is the exact index into `table_post` (native 0x51de9,
         32 4-byte handler pointers) that determines which postbattle
         handler (including ch26/29's Yuni-card dead end) runs. There is no
         separate "current chapter" global fed from anywhere else in this
         path.
      2. Live: a fresh dosbox_harness.sh instance per chapter (NOT reusing
         one running instance across LOADs -- an earlier attempt this round
         that reused one instance produced bogus stale-memory readings,
         see docs/knowledge-base/99-chapter-sweep-results.md's "branchcheck"
         section), LOAD immediately followed by a debugger read of live
         0x1EFC03 (=native 0x53C03), for ch02/ch12/ch27's
         prepare_chapter_save() output: readback was 1/11/26 respectively --
         an EXACT match to the patched raw chapter byte every time. No
         leakage.
    So `[0x53C03]`/table_post dispatch is clean. The actual, DIFFERENT
    explanation for why ch02/ch12 looked "stuck" in a prior round: inspecting
    chapter_sweep_v7's actual post_end_turn.png screenshots shows ch02 and
    ch12 did NOT reach the same screen as each other or as ch27 at all --
    ch12's shows an ordinary mid-battle NPC-rescue dialogue box (still
    in-battle, not even a win transition), ch02's shows an unrelated walkable
    camp/town scene, and only ch27 actually reached the documented "13-person
    party circle" victory scene. In other words, ch02/ch12 most likely never
    reached a genuine win via this function at all -- the single hardcoded
    `Up` below is, by this docstring's own admission two paragraphs up, only
    confirmed for ch27's specific unit cluster (very possibly compounded by
    the roster-size-mismatch caveat in doc99: ch02/ch12's synthetic saves
    keep the full late-game 13-person roster, which changes the deployment
    cluster's shape from what a real ch02/ch12 save would have). This is a
    real, still-open generalization gap in THIS function, not a save-
    construction bug -- see doc99's "branchcheck" section for the full
    writeup and suggested next steps (an adaptive multi-direction empty-tile
    probe instead of a hardcoded `Up`).
    """
    send_keys(name, "Up")  # move cursor off the unit cluster onto empty ground (fix #2 above)
    time.sleep(0.5)
    send_keys(name, "Return")  # open the command ring
    time.sleep(0.6)
    send_keys(name, "Down")
    time.sleep(0.4)
    send_keys(name, "Return")  # confirms END, opens the "end this turn?" Yes/No prompt
    time.sleep(0.6)
    if enemy_addrs:
        enter_debugger(name)
        time.sleep(0.3)
        rewritten = mass_kill_enemies(name, enemy_addrs, log)
        debugger_cmd(name, "RUN")
        time.sleep(0.3)
        log.append(f"confirm_end_turn: re-wrote death signature to {rewritten} slot(s) while the 'end this turn?' "
                   f"prompt was up, per doc58 續六十二's exact sequence, before confirming YES")
    send_keys(name, "Return")  # confirms YES
    time.sleep(2.0)
    log.append("confirm_end_turn: sent Up(empty tile)->Enter(open ring)->Down(END)->Enter(confirm)->"
               "[re-kill]->Enter(YES)")
    return screenshot(name, shots_dir / "post_end_turn.png")


# 2026-08-27 "winverify" round, §3 of doc58 續六十二: confirming YES on a
# genuine win does NOT autosave immediately -- it opens a long postbattle
# montage (party-circle dialogue -> 2 full-screen CG scenes -> scrolling
# poem text -> one full-screen "character card" per roster member, in
# recruitment order) that has to be clicked through with further Returns
# before the chapter actually advances. Confirmed live (instance 'probe4',
# ch27, --no-roster-pad real save): the win transition, party-circle scene,
# CG islands, poem text, and 萊汀's card all appeared right on schedule
# with plain Return taps, genuinely reproducing 續六十二 step for step --
# but 悠妮's card (the second one, same as 續六十二 hit) cycles between
# exactly 2 text panels forever regardless of input. This round re-tried
# it with Return/Space/Escape/Right/Down/Up/Left/Tab and a 20s real-time
# no-input wait -- all unsuccessful, matching 續六十二's own exhausted
# 60+-attempt result exactly. This is a separate, already-documented,
# still-unsolved RE puzzle (doc58 續六十二 §3's "唯一尚未解開的小尾巴"), not
# a sweep-tool bug -- POSTBATTLE_MONTAGE_TAPS below is a bounded, honest
# best-effort attempt to click through it (works for any chapter/roster
# ordering that doesn't hit an equivalent stuck card), not a claim that the
# stuck-card puzzle itself is solved.
POSTBATTLE_MONTAGE_TAPS = 70


def advance_postbattle_montage(name: str, shots_dir: Path, log: list[str],
                                taps: int = POSTBATTLE_MONTAGE_TAPS) -> None:
    """Best-effort bounded Return-mashing through the postbattle dialogue/
    CG/poem/character-card montage after a genuine win, so the chapter's
    real autosave (whenever in this sequence it actually happens -- not
    determined by this project as of this round) has the best available
    chance to fire before sweep_chapter() reads the save back. See the
    module comment above this function for why this is honestly a best-
    effort, not a guaranteed unblock -- doc58 續六十二 already spent 60+
    live attempts stuck on one specific character card and did not solve
    it either."""
    for i in range(taps):
        send_keys(name, "Return")
        time.sleep(0.5)
    screenshot(name, shots_dir / "post_montage_advance.png")
    log.append(f"advance_postbattle_montage: sent {taps} additional Return taps trying to clear the postbattle "
               f"dialogue/CG/poem/character-card montage (doc58 續六十二 §3 -- known-unresolved stuck-card risk, "
               f"see module comment)")


# --------------------------------------------------------------------------
# generic (non-battle) advance loop
# --------------------------------------------------------------------------

def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# 2026-08-27 "winverify" round: doc58's dozens of "續" entries all describe
# the SAME reliable visual signal for "real, interactive battle has begun"
# -- a small HUD box in the screen's bottom-left corner showing the
# selected unit's HP and terrain bonus (e.g. "823 A+05 D+00" for 索爾 in
# ch27, reproduced live again this round). Every screen that is NOT yet
# real battle -- pre-battle dialogue, the troop-selection roster grid, the
# "end this turn?" Yes/No prompt, even a mid-battle boss-introduction
# cutscene playing OVER an already-populated unit array (the false-positive
# this round's live "winverify"/"probe3" instances both hit: the array can
# read >=2 enemy records well before the player has any control) -- instead
# shows a large, near-flat-colored dialogue/menu panel spanning most of the
# screen width. `screen_looks_like_dialogue()` distinguishes the two
# cheaply (no OCR) by sampling a horizontal strip through where that panel
# always sits (SCREENSHOT_DIALOGUE_STRIP_Y, in the harness's fixed 1024x768
# screenshot output) and checking its color variance: a flat dialogue/menu
# panel reads under ~6000 in every live sample this round, the actual
# terrain/unit battle-map view (or camp map) reads 16000-27000. The
# threshold is set well inside that gap for margin.
SCREENSHOT_DIALOGUE_STRIP_Y = 500
SCREENSHOT_DIALOGUE_STRIP_X_RANGE = (250, 800, 10)  # start, stop, step
DIALOGUE_VARIANCE_THRESHOLD = 9000


def screen_looks_like_dialogue(png_path: Path) -> bool:
    """True if the screenshot's bottom-strip looks like a flat dialogue/menu
    panel (still need to keep sending Return), False if it looks like an
    actual textured map/battle view (safe to stop advancing). See the
    module-level comment above this function for the live-verified basis."""
    try:
        from PIL import Image
    except ImportError:
        # Pillow not available -- fail open (treat as "still dialogue") so
        # callers keep advancing rather than declaring a false victory;
        # this only degrades to the old tap-budget-only behavior.
        return True
    im = Image.open(png_path).convert("RGB")
    x0, x1, step = SCREENSHOT_DIALOGUE_STRIP_X_RANGE
    y = SCREENSHOT_DIALOGUE_STRIP_Y
    pixels = [im.getpixel((x, y)) for x in range(x0, x1, step)]
    vals = [sum(p) for p in pixels]
    mean = sum(vals) / len(vals)
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    return variance < DIALOGUE_VARIANCE_THRESHOLD


# 2026-08-27 "winverify" round, follow-up to screen_looks_like_dialogue()
# above: that check alone turned out to be NOT specific enough. Two
# INDEPENDENT false positives were reproduced live in the same ch27
# boss-introduction cutscene (instance 'probe3', then reproduced again by
# sweep_chapter() itself via instance 'verify327' after the first fix
# landed): a bare "camera cuts to the marching party, no textbox" beat
# between two dialogue lines, and a second, different such beat later in
# the same cutscene, BOTH read as "not dialogue" by the variance check
# while the real battle (with player control) still hadn't started. So
# "absence of a dialogue panel" is not proof of "presence of real control".
#
# doc58's "續" log has an actually-specific, well-documented positive
# signal instead, reproduced across 40+ independent rounds (續四十四
# through 續八十): a small HUD box in the screen's bottom-left corner
# showing the selected unit's HP and terrain bonus, e.g. "823 A+05 D+00"
# for 索爾 in ch27 (823 = his HP, reproduced live again this round at the
# exact same value). That box only exists once the player has a movable
# battle cursor -- i.e. once real, interactive battle has actually begun.
# `screen_shows_battle_hud()` checks for it directly: crop the fixed
# bottom-left region (BATTLE_HUD_BOX_REGION, calibrated against this
# round's live screenshots) and measure what fraction of pixels are
# "HUD blue" (blue channel clearly dominant, not too light/dark -- the
# box's flat blue background, not the box's white/light digits or the
# portrait icon). Live samples this round: the genuine HUD screen reads
# ~0.48, every cutscene/dialogue/camp/troop-select frame tried reads
# 0.00-0.04. The threshold is set well inside that gap.
BATTLE_HUD_BOX_REGION = (205, 520, 345, 598)  # (left, top, right, bottom)
BATTLE_HUD_BLUE_FRAC_THRESHOLD = 0.15


def _is_hud_blue(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return b > r + 20 and 60 < b < 200 and r < 100


def screen_shows_battle_hud(png_path: Path) -> bool:
    """True if the screenshot shows doc58's "NNN A+XX D+XX" battle HUD box
    in the bottom-left corner -- the specific, well-documented signal for
    "the player has real control of a movable battle cursor right now", not
    just "some non-dialogue frame" (see the module comment above this
    function for why the weaker screen_looks_like_dialogue() check alone
    was proven insufficient, live, twice).

    2026-08-27 correction (same round): the HUD-blue color-fraction check
    alone ALSO false-positived, on two different screens this time -- the
    "要進入戰場嗎?" exit-confirm dialogue (莎拉's portrait includes a chunky
    blue collar/headband right in BATTLE_HUD_BOX_REGION) and the troop-
    selection roster screen (its "剩餘人數" side panel uses the EXACT same
    (56,85,154) theme blue as the real HUD box's background -- apparently a
    shared UI color, not a HUD-specific one). Both of those screens DO
    register as "looks like a dialogue/menu panel" under
    screen_looks_like_dialogue()'s variance check, though, and the genuine
    battle-map HUD screen does NOT (its terrain view has high variance) --
    so AND-ing the two checks together clears both false positives while
    still passing every true-positive and cutscene-false-positive case
    tried live this round (12/12 in the validation sweep that caught this)."""
    try:
        from PIL import Image
    except ImportError:
        return False  # fail closed here -- callers should keep waiting/advancing
    if screen_looks_like_dialogue(png_path):
        return False
    im = Image.open(png_path).convert("RGB")
    box = im.crop(BATTLE_HUD_BOX_REGION)
    pixels = list(box.getdata())
    frac = sum(1 for p in pixels if _is_hud_blue(p)) / len(pixels)
    return frac > BATTLE_HUD_BLUE_FRAC_THRESHOLD


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
# which kind of node it landed on ahead of time. Kept ONLY as the last-
# resort fallback after attempt_camp_exit() below has already failed --
# see the 2026-08-27 "campexit" diagnostic round (docs/knowledge-base/99-
# chapter-sweep-results.md) that found this fallback was doing ALL the
# work for 22/30 chapters when it should never have needed to.
_ADVANCE_KEY_CYCLE = ["Return", "Down", "Right", "Return", "Escape", "Right", "Down", "Return"]

# Chapter-specific navigate hints: an explicit key list that FULLY REPLACES
# both attempt_camp_exit() and _ADVANCE_KEY_CYCLE for a given chapter, for
# the rare case a chapter is known to need something genuinely different.
# Empty by default as of the 2026-08-27 fix -- attempt_camp_exit() below is
# now the general-purpose first attempt for every chapter (see that
# function's docstring for why a single hard-coded ch27-only hint was
# replaced instead of extended).
KNOWN_NAVIGATE_HINTS: dict[int, list[str]] = {}

# doc91 UI-VIS-TOWN / UI-08-TOWN-VARIANT0-SIX-SELECTION-E2's established
# town-hub hotspot order (5 selections, Left/Right cycles, wraps): index0
# 酒店(tavern), 1 武器店(weapon shop), 2 出口(EXIT), 3 道具店(item shop),
# 4 教會(church). The scene consistently loads with selection0 (酒店)
# highlighted (confirmed fresh in the 2026-08-27 "campexit" diagnostic
# round below, and matches every prior live round in doc91/doc58). Right
# cycles DOWN through the index (0->4->3->2->1->0, per doc91's
# "另實測Right 0→4"), so Right x3 from the default selection0 reaches
# selection2 (出口) -- this is doc91 UI-VIS-PREPARATION's 2026-08-25 prepE2
# round's exact, real-save-verified "Right×3 cycle到「出口」" sequence.
CAMP_EXIT_CYCLE_KEYS = ["Right", "Right", "Right"]


def attempt_camp_exit(name: str, shots_dir: Path, log: list[str],
                       confirm_retries: int = 4, dialogue_steps: int = 60) -> dict | None:
    """Try the doc91/doc58-established "town-hub camp -> exit -> battle"
    sequence: cycle to the 出口 (EXIT) hotspot, confirm it, confirm the
    resulting "要進入戰場嗎?" YES/NO prompt (YES is the default highlight),
    then Enter-advance through the troop-selection screen (Return both
    picks the highlighted roster member AND advances the cursor -- see
    the 2026-08-27 "winverify" round below) and however many lines of
    pre-battle dialogue the chapter has (this varies per chapter and is
    NOT bounded by any known constant, hence the bounded polling loop)
    until the engine-level battle-array pointer (read_battle_array_base)
    goes live AND holds more than one unit record.

    WHY THIS EXISTS (2026-08-27 fix): earlier rounds of this tool treated
    "no reliable camp-exit sequence" as an open RE puzzle and fell back to
    the generic, chapter-agnostic _ADVANCE_KEY_CYCLE for 22/30 chapters
    (99-chapter-sweep-results.md's first-round sweep), which never once
    found a battle. A direct diagnostic (instance 'campexit', ch12's
    already-validated patched.SAV, docs/knowledge-base/99-chapter-sweep-
    results.md's follow-up section) tested the ALREADY-DOCUMENTED doc91
    UI-VIS-PREPARATION sequence directly, bypassing this tool's generic
    loop entirely: it worked on the very FIRST attempt, both for the exit-
    confirm Return and the YES-confirm Return -- no input-drop retries were
    needed even once across a full run. So the dominant cause of the first
    round's 0/22 camp-map pass rate was that _ADVANCE_KEY_CYCLE never tried
    this sequence at all (it opens with a bare Return, which at the default
    selection0/酒店 immediately drops into the tavern's roster/character
    browser instead), NOT the documented Enter/Space input-drop bug (doc58
    續五十四..續七十七) -- that bug is real and still documented elsewhere
    in this project, just not what was biting this tool. The retries below
    are kept anyway as cheap insurance against that known, separately-
    confirmed flakiness, not because this round reproduced it.

    WHY THE STOPPING CONDITION CHANGED (2026-08-27 "winverify" follow-up,
    see doc99's "camp-exit vs ch27 63-enemy discrepancy" section): the
    original version of this loop stopped the instant
    read_battle_array_base() returned ANY plausible-looking pointer, BEFORE
    sending a single dialogue-advance Return. Live verification (instance
    'winverify', ch27's already-patched save) proved this pointer goes
    "plausible" the moment the "要進入戰場嗎?" YES confirm lands on the
    troop-selection screen ("出戰人數"/"剩餘人數" counters + a roster grid)
    -- it is a transient PLACEHOLDER array with exactly 1 record, not the
    real battle. The old code declared victory here and returned with
    "0 dialogue-advance taps" used, which is why sweep_chapter()'s
    (passive, sleep-only) settle loop downstream could never see more than
    1 "enemy": nothing had ever sent the ~15 Returns needed to fill the
    troop quota (each Return both PICKS the highlighted candidate --
    decrementing 剩餘人數 -- and advances the cursor; confirmed live, do
    NOT treat this as a toggle/deselect), the Return that confirms the
    resulting auto-popup "確定" dialog, or the further ~10-45 Returns
    (doc58 續六十二's number, also reproduced live this round) needed to
    click through pre-battle dialogue before the real, fully-populated
    battle array (47 enemy records for ch27, matching 續六十二 exactly)
    gets allocated. All of these screens accept plain Return, so the fix
    is NOT a new key sequence -- it is to stop declaring "battle confirmed"
    on a bare plausible pointer and instead require the enemy scan itself
    to find more than 1 record (a real battle; the specific 1-record
    placeholder pattern was reproduced twice now and is never how a real
    FD2 battle actually starts) before treating the pointer as trustworthy,
    so the loop keeps sending Returns through the intervening screens
    instead of stopping dead on the very first one. dialogue_steps was
    also raised 20->60 to give this longer real sequence enough budget.

    Returns the same shape as advance_generic()'s success dict
    ({"battle_base": int, "steps_used": int, "max_stall_seen": 0}) if a
    battle was confirmed via the engine pointer, else None (caller should
    fall back to the generic loop -- e.g. a prep-select chapter that skips
    the camp entirely, where this sequence is a mostly-harmless no-op that
    just wastes a handful of steps).
    """
    step = 0
    for key in CAMP_EXIT_CYCLE_KEYS:
        send_keys(name, key)
        time.sleep(0.6)
        screenshot(name, shots_dir / f"campexit_{step:03d}_cycle.png")
        step += 1
    log.append("attempt_camp_exit: sent Right x3 (default selection0/酒店 -> selection2/出口 per doc91)")

    def _confirm_with_retry(label: str) -> bool:
        nonlocal step
        pre_hash = file_md5(screenshot(name, shots_dir / f"campexit_{step:03d}_pre_{label}.png"))
        for attempt in range(1, confirm_retries + 1):
            send_keys(name, "Return")
            time.sleep(1.0)
            shot = screenshot(name, shots_dir / f"campexit_{step:03d}_{label}_attempt{attempt}.png")
            step += 1
            post_hash = file_md5(shot)
            if post_hash != pre_hash:
                log.append(f"attempt_camp_exit: {label} confirm registered on attempt {attempt}/{confirm_retries}")
                return True
            log.append(f"attempt_camp_exit: {label} confirm attempt {attempt}/{confirm_retries} produced no visible "
                        f"change, retrying (doc58 續五十四..續七十七 Enter/Space input-drop workaround)")
        log.append(f"attempt_camp_exit: {label} confirm never registered after {confirm_retries} attempts, giving up")
        return False

    if not _confirm_with_retry("exit_confirm"):
        return None
    if not _confirm_with_retry("yes_confirm"):
        return None

    def _check_real_battle() -> tuple[int | None, list[int]]:
        # read_battle_array_base's "D ..." debugger console command only
        # reaches the debugger TUI while it's open -- MUST bracket every
        # poll with enter_debugger (Alt+Pause open) / RUN (resume + close),
        # same discipline as sweep_chapter's own first check. The original
        # advance_generic loop polled without this bracketing (it relied on
        # a single enter_debugger/RUN pair done ONCE by its caller before
        # the loop started), which meant every poll after the first step
        # was reading a closed/stale debugger console and could never
        # observe a battle -- a second, independent bug from the missing
        # navigate sequence, fixed here for this new polling loop and left
        # documented for advance_generic below.
        #
        # ALSO scans for enemy records (not just the bare pointer) -- see
        # this function's 2026-08-27 "winverify" docstring section. A
        # merely-plausible pointer is NOT sufficient: the troop-selection
        # screen that comes BEFORE the real battle already has one live,
        # holding a transient 1-record placeholder. Only treat the pointer
        # as the real battle once it holds more than 1 record.
        enter_debugger(name)
        time.sleep(0.3)
        b = read_battle_array_base(name)
        enemies = scan_enemy_slots(name, b, log) if b is not None else []
        debugger_cmd(name, "RUN")
        time.sleep(0.2)
        return b, enemies

    def _check_screen(i: int) -> tuple[int | None, list[int], bool]:
        # 2026-08-27 "winverify" round: gate the expensive memory scan on
        # screen_shows_battle_hud() (doc58's "823 A+05 D+00"-style HUD box),
        # NOT screen_looks_like_dialogue(). The weaker "screen doesn't look
        # like a dialogue panel" check was tried first and produced two
        # INDEPENDENT false positives live in this exact ch27 boss-intro
        # cutscene (instance 'probe3', then again via sweep_chapter() as
        # instance 'verify327') -- bare "camera cuts to the marching party"
        # beats with no textbox that still aren't the real battle. The HUD
        # box only exists once the player has a movable battle cursor, so
        # it's the specific signal, not just an absence-of-dialogue guess.
        shot = screenshot(name, shots_dir / f"campexit_{step + i:03d}_dialogue{i:02d}.png")
        if not screen_shows_battle_hud(shot):
            return None, [], True
        base, enemies = _check_real_battle()
        return base, enemies, False

    for i in range(1, dialogue_steps + 1):
        base, enemies, no_hud = _check_screen(i)
        if not no_hud and base is not None and len(enemies) >= REAL_BATTLE_MIN_ENEMIES:
            log.append(f"attempt_camp_exit: real battle confirmed (battle HUD box visible + engine pointer + "
                       f"{len(enemies)} enemy record(s)) after {i} taps")
            return {"battle_base": base, "steps_used": step + i, "max_stall_seen": 0}
        if not no_hud:
            # HUD box visible but the array doesn't look like a real battle
            # yet -- shouldn't normally happen (the HUD box only appears
            # once units are on the field), but if it does, log it plainly
            # rather than silently retrying forever.
            log.append(f"attempt_camp_exit: tap {i}/{dialogue_steps} -- HUD box visible but only {len(enemies)} "
                       f"enemy record(s) (base={base}) -- continuing")
        send_keys(name, "Return")
        time.sleep(0.8)
    # One final check after the last tap, in case the battle state only
    # becomes readable a beat after the last screen transition.
    base, enemies, no_hud = _check_screen(dialogue_steps + 1)
    if not no_hud and base is not None and len(enemies) >= REAL_BATTLE_MIN_ENEMIES:
        log.append(f"attempt_camp_exit: real battle confirmed via engine pointer + {len(enemies)} enemy "
                   f"record(s) after final dialogue-advance tap")
        return {"battle_base": base, "steps_used": step + dialogue_steps, "max_stall_seen": 0}
    log.append(f"attempt_camp_exit: exit+YES confirmed but no real battle (HUD box + enemy records) detected "
               f"within {dialogue_steps} dialogue/selection-advance taps -- falling back to the generic loop "
               f"(last seen: base={base}, enemies={len(enemies)}, hud_visible={not no_hud})")
    return None


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
    cur_shot = screenshot(name, shots_dir / "advance_pre000.png")
    for step in range(max_steps):
        # See attempt_camp_exit()'s _check_battle() docstring comment: the
        # debugger console must be (re)opened before every poll and closed
        # (RUN) after, or this always reads a stale/closed console. Fixed
        # here 2026-08-27 alongside attempt_camp_exit -- this loop is now
        # only reached as a last-resort fallback, but should still report
        # a battle correctly if it stumbles into one.
        #
        # See attempt_camp_exit()'s docstring (2026-08-27 "winverify" round)
        # for why a plausible pointer with a couple of enemy records is
        # STILL not sufficient on its own -- it can be a placeholder or a
        # boss-intro cutscene playing over an already-populated array, and
        # "screen doesn't look like a dialogue panel" alone was tried and
        # proven insufficient too (two independent live false positives).
        # Gate the expensive scan on screen_shows_battle_hud() instead --
        # doc58's actual "823 A+05 D+00"-style battle HUD box, the specific
        # signal for "the player has a movable battle cursor right now".
        has_hud = screen_shows_battle_hud(cur_shot)
        base, enemies = None, []
        if has_hud:
            enter_debugger(name)
            time.sleep(0.3)
            base = read_battle_array_base(name)
            enemies = scan_enemy_slots(name, base, log) if base is not None else []
            debugger_cmd(name, "RUN")
            time.sleep(0.2)
        if has_hud and base is not None and len(enemies) >= REAL_BATTLE_MIN_ENEMIES:
            log.append(f"advance_generic: real battle detected at step {step} (array base {base:#x}, "
                       f"{len(enemies)} enemy records)")
            return {"battle_base": base, "steps_used": step, "max_stall_seen": max_stall_seen}
        if hint_keys and step < len(hint_keys):
            key = hint_keys[step]
        else:
            key = _ADVANCE_KEY_CYCLE[step % len(_ADVANCE_KEY_CYCLE)]
        send_keys(name, key)
        time.sleep(1.0)
        shot = screenshot(name, shots_dir / f"advance_{step:03d}.png")
        cur_shot = shot
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
        post_load_shot = screenshot(name, shots_dir / "02_post_load.png")

        enter_debugger(name)
        time.sleep(0.5)
        base = read_battle_array_base(name)
        # 2026-08-27 "winverify" fix: a merely-plausible pointer is NOT
        # sufficient proof of "already in battle" -- prep-select chapters
        # (ch23/24/25/28/29/30, doc99) land DIRECTLY on the troop-selection
        # screen after LOAD, which already has a plausible pointer holding a
        # transient 1-record placeholder, AND (a second, independently-
        # confirmed false positive, see attempt_camp_exit()'s docstring) a
        # boss-introduction cutscene can play OVER an already-populated,
        # >=2-enemy-record real battle array well before the player has any
        # control -- even a screen with no dialogue box visible can still be
        # a bare cutscene beat, not real control (screen_looks_like_dialogue
        # alone was tried and produced two independent false positives
        # live). Require BOTH >=2 enemy records AND doc58's actual "823
        # A+05 D+00"-style battle HUD box (screen_shows_battle_hud()) here
        # too, or this initial gate would wrongly skip straight to the
        # passive settle-loop below and never send the Returns needed to
        # actually pick troops / advance dialogue / clear the cutscene.
        post_load_enemies = scan_enemy_slots(name, base, log) if base is not None else []
        post_load_has_hud = screen_shows_battle_hud(post_load_shot)
        # Leave the debugger console and resume the emulator loop before
        # doing anything else -- RUN, not just closing the TUI overlay, per
        # doc48 §8.4's "confirm (Running) before sending game keys again".
        debugger_cmd(name, "RUN")
        time.sleep(0.3)

        if base is not None and (len(post_load_enemies) < REAL_BATTLE_MIN_ENEMIES or not post_load_has_hud):
            log.append(f"post-load state: pointer plausible but only {len(post_load_enemies)} enemy record(s) "
                       f"and/or no battle HUD box visible (hud={post_load_has_hud}) -- treating as story/town node")
            base = None

        if base is None:
            log.append("post-load state: battle array pointer not plausible -> treating as story/town node")
            hint = KNOWN_NAVIGATE_HINTS.get(chapter_n) if use_navigate_hints else None
            if hint:
                log.append(f"chapter {chapter_n} has an explicit KNOWN_NAVIGATE_HINTS override, skipping attempt_camp_exit")
                adv = advance_generic(name, shots_dir, log, hint_keys=hint)
                base = adv["battle_base"]
            else:
                log.append("trying attempt_camp_exit (doc91 town-hub Right x3 -> 出口 -> YES -> dialogue-advance sequence) first")
                adv = attempt_camp_exit(name, shots_dir, log) if use_navigate_hints else None
                base = adv["battle_base"] if adv else None
                if base is None:
                    log.append("attempt_camp_exit did not find a battle, falling back to the generic advance loop")
                    adv = advance_generic(name, shots_dir, log, hint_keys=None)
                    base = adv["battle_base"]

        if base is not None:
            log.append(f"battle confirmed, array base={base:#x}")
            # 2026-08-27 two-part finding (ch12/ch27 live runs through
            # attempt_camp_exit, then confirmed with a dedicated no-keypress
            # timing probe -- docs/knowledge-base/99-chapter-sweep-
            # results.md "campexit" section has the full writeup):
            #   1. The battle-array POINTER ITSELF gets reassigned partway
            #      through the walk-in/approach cutscene -- a transient
            #      early allocation (1 stale/placeholder record) is replaced
            #      by the real, fully-populated array a few seconds later
            #      (observed: pointer 0x1fc6c0 with 1 record at t=0s, a
            #      DIFFERENT pointer with 11 records by t=5s, stable through
            #      t=40s). An earlier version of this settle loop kept
            #      rescanning the ORIGINAL base and never re-fetched the
            #      pointer, so it always saw the same stale 1-record
            #      snapshot no matter how long it waited.
            #   2. This is a pure passive TIME gate, not an input gate -- a
            #      dedicated probe that sent zero extra keypresses after the
            #      YES confirm still saw the count grow 1->11 by t=5s and
            #      stay there through t=40s. No extra Enter taps needed.
            # Fix: re-fetch read_battle_array_base() (not just rescan the
            # old base) each settle round, and ALWAYS run the full settle
            # budget rather than stopping at the first apparent plateau --
            # an early-stop-on-2-matching-rounds version was tried and
            # broke too early for ch27 (whose transient 1-enemy base
            # stayed put for 2+ consecutive 2s rounds before the real
            # array showed up), while it happened to work for ch12 (whose
            # transient phase was shorter). Track the round with the most
            # enemies found across the WHOLE fixed budget instead of
            # guessing when it has "settled".
            best_base, best_enemies = base, []
            settle_rounds = 6
            for settle_round in range(settle_rounds):
                time.sleep(2.5)
                enter_debugger(name)
                time.sleep(0.4)
                cur_base = read_battle_array_base(name)
                cur_enemies = scan_enemy_slots(name, cur_base, log) if cur_base is not None else []
                debugger_cmd(name, "RUN")
                time.sleep(0.2)
                log.append(f"settle round {settle_round + 1}/{settle_rounds}: base={cur_base}, enemies={len(cur_enemies)} "
                            f"(best so far: base={best_base}, enemies={len(best_enemies)})")
                if len(cur_enemies) >= len(best_enemies):
                    best_base, best_enemies = cur_base, cur_enemies
            base, enemy_addrs = best_base, best_enemies
            enter_debugger(name)
            time.sleep(0.5)
            if enemy_addrs:
                mass_kill_enemies(name, enemy_addrs, log)
            debugger_cmd(name, "RUN")
            time.sleep(0.5)
            screenshot(name, shots_dir / "03_pre_end_turn.png")
            if enemy_addrs:
                confirm_end_turn(name, shots_dir, log, enemy_addrs=enemy_addrs)
                # 2026-08-27 "winverify": a genuine win does not autosave
                # immediately -- see advance_postbattle_montage()'s module
                # comment. Best-effort attempt to clear the montage before
                # reading the save back below.
                advance_postbattle_montage(name, shots_dir, log)
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
                     help="skip both KNOWN_NAVIGATE_HINTS overrides and attempt_camp_exit(), and go straight to the "
                          "chapter-agnostic generic advance loop (useful for re-measuring how much attempt_camp_exit "
                          "is actually contributing)")
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
