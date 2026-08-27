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
- 2026-08-27 "ch12diag" round update: the battle-detection pointer
  (0x1EFA45), enemy-scan/death-signature constants (stride 0x50, +5/+6), and
  the mass-kill+End-Turn win-check shortcut ARE now cross-chapter validated
  -- a live sweep of ch02-ch16 (15 chapters) found 9/15 (ch05/06/08/09/10/
  12/13/14/16) reach a directly-confirmed ENGINE-LEVEL win ([0x53ecc]
  reading 2 via a debugger read, not a screenshot guess -- see
  read_pending_result_code()/CHAPTER_INDEX_LIVE's module comment and
  confirm_end_turn()'s docstring). This generalizes well beyond the
  ch27-only evidence this paragraph used to describe. HOWEVER: even for
  those 9 chapters, the ON-DISK FD2.SAV chapter byte has NEVER been
  observed to advance (verdict "anomaly_engine_win_no_disk_write", not
  "pass") -- see docs/knowledge-base/25-battle-event-system.md §9.1's own
  multi-round (saveE2/savewriter/camproute/writerfire) investigation into
  when/whether the native SAV writer gate actually fires for a battle-win
  path; this is a genuinely open, project-wide question, not a bug in this
  tool. The remaining 6/15 chapters (ch02/03/04/07/11/15; ch20 joined this
  club in a later sweep round) never reached the engine-level win at first
  for a still-undiagnosed reason (ruled out so far for ch02: an enemy-array
  scan gap, and a misread of unit5-10's override condition -- see
  docs/knowledge-base/99-chapter-sweep-results.md's "ch12diag" section for
  the full writeup and next-round suggestions).
  **2026-08-27 "ch19banor"/"ch2killgen" rounds update**: this "stuck at 0"
  club is now understood to be, for MOST of its members, a plain
  TIMING/turn-count issue rather than a structural win-check mismatch --
  KNOWN_MIN_TURNS_BEFORE_KILL (below) waits N real turns (via the same
  End-Turn->YES shortcut, no mass-kill, no stat hacks) before the first
  mass-kill, and this alone flipped [0x53ecc] to a confirmed engine win on
  the very FIRST kill-cycle for ch19 (wait 6), ch03 (wait 3), ch04 (wait 4,
  despite ch04's walkthrough-documented "kill one, others flee" mechanic --
  see KNOWN_MIN_TURNS_BEFORE_KILL's module comment for why this tool's
  direct-memory-write kill method is predicted to sidestep that AI-only
  behavior), ch15 (wait 9, spanning two documented reinforcement waves), and
  ch20 (wait 4, with NO swamp-monster exclusion or elf-protection logic
  needed despite ch20's "victory excludes swamp monsters" / "elves must
  survive" walkthrough text -- see sweep_chapter()'s ch20-specific comment
  for why killing everything including swamp monsters was predicted to
  still be safe, and was), and -- somewhat surprisingly, since its
  walkthrough-described trigger is positional, not turn-count-shaped --
  ch07 (wait 3, once a battle-detection flake on the first attempt was
  ruled out with a clean re-run). ch02 (separate village-protection
  investigation track, out of scope for this round) remains open on its
  own track. ch11 is the one chapter this round's turn-wait test was
  cleanly, reproducibly negative for: 25 enemies found, all confirmed via
  a post-kill rescan to persistently carry the death signature (no revival,
  no new wave), yet [0x53ecc] never left 0 -- ch11's blocker is something
  this tool does not yet identify; see doc99's "ch2killgen" section, ch11
  sub-section, for the live evidence and next-round suggestion (decompile
  ch11's own 0x51b19-table win-check handler rather than guess further).
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
- 2026-08-27 "cursorlive" round -- ROOT CAUSE FOUND for the "新卡點A" prep-
  select wall (ch21/22/26 + suspected ch23/24/25/28/29/30, see doc99's "r2"
  section): it is NOT the passive "synthetic member renders as an
  unselectable grey silhouette" eligibility gate that round's screenshot
  read implied. Careful single-step live re-testing (individual Return
  presses + a screenshot after each, replacing the blind 120-tap
  attempt_camp_exit() spam that produced the original "stuck at 12" evidence)
  on a fresh ch21 synthetic save proved every grid cell -- real AND
  synthetic -- renders GREY by default (unselected) and turns to full color
  the instant Return selects it; synthetic (append_roster_members-built)
  members are exactly as selectable, one at a time, as real ones. The
  original "12 colored fixed / rest permanently grey" screenshot is instead
  an artifact of attempt_camp_exit()'s blind Return-spam: Return both
  selects-and-advances AND (per doc58 續九) toggles via XOR, so hundreds of
  blind taps cycling through an N-follower grid leave an unpredictable
  even/odd selected/unselected split, not a real "these are unselectable"
  signal.
  The REAL wall, found by completing a careful full 15-of-15 selection by
  hand: at the final confirm step (0 remaining), the native game validates
  that chapter N's specific story-mandated "guard" character(s) --
  docs/knowledge-base/28-chapter-objectives-and-recruits.md's 額外護衛
  column, e.g. ch21(raw20)=羅蘭(id23)/希爾法(id24) -- are present in the
  SELECTED roster. If not, it rejects with the on-screen message "本章約定
  必須出場！" ("this chapter's contracted/mandated [units] must be
  deployed!") and bounces the player straight back to the camp map. This was
  live-verified TWICE on ch21: once with arbitrary ascending-id padding
  (neither 23 nor 24 present -> rejected), and once with padding explicitly
  constructed to include ids 23/24 AND with both of them deliberately
  selected during the manual walkthrough (confirmed colored/selected via
  screenshot, cursor showing their real names/stats "羅蘭"/"希爾法" at
  selection time) -- STILL rejected with the identical message. This proves
  the gate needs more than "the right character id is present in the roster
  array and toggled selected"; a save-file-only append_roster_members()
  record does not satisfy whatever additional native state the check reads
  (candidates not yet isolated: the equip-recalc tail/equip-stat block this
  bullet's paragraph above already flags as absent from synthetic records,
  or an entirely separate persistent flag outside the roster array that only
  a real in-game JOIN story event sets -- disassembling the "必須出場" check
  itself is the next step, not done this round).
  This also RECONCILES the apparent ch27-vs-ch21/22/26 contradiction that
  motivated this round: ch27(raw26)'s own doc28 guard character is 悠妮
  (id9) -- who is already a REAL member of every base save used by this
  project's rostertest/sweep rounds (record index1, e.g. HP782/MP817 in
  both the original 2026-08-26 rostertest screenshots and this round's ch21
  saves). The 2026-08-26 rostertest round's reported "selected 19/19
  cleanly, no rejection" success never actually exercised a SYNTHETIC guard
  character at all -- it's not counter-evidence that synthetic records can
  satisfy this gate, it's simply a case where the gate was already satisfied
  by a real record before any padding happened.
  Cross-referencing doc28's 額外護衛 column against the base save's real
  roster ids ([0,9,4,30,1,8,2,10,13,12,5,11,6] -- only id9/悠妮 overlaps any
  chapter's guard list) gives a HIGH-CONFIDENCE, not-yet-individually-
  verified prediction for the other flagged chapters: ch22(希爾法/24),
  ch23(希爾法/24+卡里斯/22+羅德曼/19), ch25(聖寇拉斯/26), and
  ch26(悠妮/9 real + 亞奇梅吉/29 NOT real, so still blocked because BOTH are
  required) should all hit this same wall; ch24 (no guard character listed)
  and ch28/29/30 (guard=悠妮/9, already real) should NOT be blocked by this
  specific mechanism and their continued "needs_manual_followup" status
  likely has a different cause (e.g. the ch27-style dual-ending/character-
  card montage already documented for the late chapters). No chapter's
  verdict changed to `pass` this round -- this is a genuine, live-verified
  structural limitation of the synthetic-roster-padding technique itself,
  not a chapter_sweep.py invocation bug (prepare_chapter_save()'s call to
  fd2save.append_roster_members() was checked byte-for-byte against the
  proven rostertest method and is correct). See docs/knowledge-base/99-
  chapter-sweep-results.md's "cursorlive" section for the full screenshot
  evidence trail.

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
# 2026-08-27 "ch12diag" round: the native+0x19C000 delta established elsewhere in this
# project (doc58's repeated "續" derivations, and this module's own BATTLE_ARRAY_PTR_LIVE
# above -- 0x53a45+0x19C000=0x1EFA45) also gives DIRECT, ground-truth debugger access to
# the two globals doc25 §4/§6 document as the actual win-check state machine, instead of
# guessing from screenshots alone:
#   - [0x53ecc] (live 0x1EFECC): the "pending result code" 0x205be/the per-chapter
#     0x51b19[] handler writes -- 0=still fighting, 1=mid-battle scripted event (NOT a
#     win -- see doc25 §6's "==1 -> 固定0x22e5c資源#79呈現->清0"), 2=win (unconditionally
#     dispatches the postbattle table 0x51de9[chapter], doc58 續二十八's fully-disassembled
#     FUN_00025bf4 campaign loop).
#   - [0x53c03] (live 0x1EFC03): the current chapter index (0-based) -- doc58 續二十八
#     proved byte-for-byte that EVERY postbattle handler in the 0x51de9 table (ch24's
#     0x24c1e was the fully-disassembled example) unconditionally INCs this exact global
#     near its own end, and that native chapter-raw 23->24 was observed advancing on the
#     REAL DISK FD2.SAV in an earlier live round of this project -- i.e. this in-memory
#     advance is the SAME general mechanism that DOES eventually reach disk for at least
#     one chapter, not a dead end invented by this tool.
# Directly polling these two globals after End Turn is confirmed is a strictly stronger
# ground-truth signal than this module's existing screenshot heuristics
# (screen_shows_battle_hud/screen_looks_like_dialogue) for the specific question "did the
# win-check actually fire" -- see confirm_end_turn()'s "2026-08-27 ch12diag" docstring
# section for the live derivation (ch12, a genuinely different, non-default per-chapter
# handler 0x2073d, confirmed reaching pending_code==2 and chapter_index 11->12 live for
# the first time this project, generalizing beyond ch27's default/L-handler case).
NATIVE_LIVE_DELTA = 0x19C000
PENDING_RESULT_CODE_LIVE = 0x53ecc + NATIVE_LIVE_DELTA
CHAPTER_INDEX_LIVE = 0x53c03 + NATIVE_LIVE_DELTA
ENGINE_WIN_CODE = 2
ENGINE_EVENT_CODE = 1
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


def read_pending_result_code(name: str) -> int | None:
    """Read [0x53ecc] (live PENDING_RESULT_CODE_LIVE) -- see the module-level
    comment above PENDING_RESULT_CODE_LIVE for provenance. 0=still fighting,
    1=mid-battle scripted event (NOT a win), 2=win (ENGINE_WIN_CODE). Callers
    MUST be inside an open debugger console (enter_debugger already called) --
    same discipline as read_battle_array_base."""
    raw = read_mem(name, PENDING_RESULT_CODE_LIVE, min_bytes=4)
    if raw is None:
        return None
    return raw[0] | (raw[1] << 8) | (raw[2] << 16) | (raw[3] << 24)


def read_chapter_index_live(name: str) -> int | None:
    """Read [0x53c03] (live CHAPTER_INDEX_LIVE), the 0-based chapter index --
    see the module-level comment above CHAPTER_INDEX_LIVE. Callers MUST be
    inside an open debugger console, same discipline as read_battle_array_base."""
    raw = read_mem(name, CHAPTER_INDEX_LIVE, min_bytes=1)
    if raw is None:
        return None
    return raw[0]


def scan_enemy_slots(name: str, base: int, log: list[str]) -> list[int]:
    """Sequentially read each candidate unit record's camp byte (+6) and
    return the linear addresses of every record classified as enemy
    (camp==0). Ally records (camp==2) are read but never written.

    2026-08-27 "ch12diag" round follow-up (ch02 live cross-check): this used
    to stop early once CONSECUTIVE_ZERO_STOP consecutive fully-zero records
    were seen after >=1 enemy had already been found. Live testing on ch02
    (handler 0x206c5, doc25 §5) found the engine-level win-check
    ([0x53ecc]) staying stuck at 0 through 4 full mass-kill/End-Turn retry
    cycles (60s of direct debugger polling each cycle -- not a screenshot
    guess) even though every camp==0 record this scan found (10 of them)
    was correctly written with the death signature and confirmed via
    read-back. The native win-check (0x205be) scans the FULL unit array
    (0..[0x53beb], ch12 diag confirmed this bound live at 25, but it is not
    assumed constant per chapter) with no early-exit of its own -- if this
    tool's own scan stopped early past a >=4-zero-record gap and missed a
    second, non-adjacent cluster of camp==0 records, mass_kill_enemies()
    would never touch them and 0x205be would correctly, forever, keep seeing
    a live enemy and never reach code 2. ch12's own array happened to have
    no such gap (record[14] was non-zero, camp=1, so it never tripped the
    zero-streak counter), which is why this generalization gap was invisible
    there and only surfaced on ch02. FIX: always scan the full
    MAX_ENEMY_SCAN_SLOTS range unconditionally -- no early exit. This costs
    more debugger reads per call (worst case ~30-40s at MAX_ENEMY_SCAN_SLOTS
    =96), but correctness matters far more than speed for a scan whose
    entire purpose is "did we find every enemy record" -- a false-early-stop
    here silently and permanently blocks the win-check for any chapter whose
    live layout has a gap, which is a much worse failure mode than a slower
    scan. CONSECUTIVE_ZERO_STOP is kept defined (used nowhere now) only so a
    future round has the identifier available if a bounded variant is ever
    reintroduced deliberately, with a documented trade-off."""
    enemies: list[int] = []
    for k in range(MAX_ENEMY_SCAN_SLOTS):
        rec_addr = base + k * UNIT_STRIDE
        raw = read_mem(name, rec_addr, min_bytes=8)
        if raw is None:
            log.append(f"scan slot{k}: read failed at {rec_addr:#x}, stopping scan")
            break
        camp = raw[UNIT_CAMP_OFFSET]
        if all(b == 0 for b in raw[:8]):
            continue
        if camp == 0:
            enemies.append(rec_addr)
    log.append(f"scan_enemy_slots: base={base:#x} scanned<= {MAX_ENEMY_SCAN_SLOTS} slots (unconditional, no "
               f"early exit), enemies_found={len(enemies)}")
    return enemies


def mass_kill_enemies(name: str, enemy_addrs: list[int], log: list[str]) -> int:
    written = 0
    for addr in enemy_addrs:
        write_byte(name, addr + UNIT_ACTED_OFFSET, ENEMY_DEATH_VALUE)
        written += 1
    log.append(f"mass_kill_enemies: wrote death signature to {written} slot(s)")
    return written


ENGINE_WIN_POLL_MAX_S = 15.0  # 2026-08-27 "ch12diag": ch12 needed ~8s; leave headroom above that.
POST_WIN_DISK_POLL_MAX_S = 60.0  # 2026-08-27 "ch12diag": bounded patience for the on-disk save write
                                   # after an engine-level win is confirmed -- see sweep_chapter()'s comment.
MAX_KILL_CYCLES = 4  # 2026-08-27 "ch12diag" follow-up: bounded mass-kill/End-Turn retry budget to absorb
                      # reinforcement waves (turn-end- or kill-triggered per doc25 §6.1's turn_events
                      # mechanism, cross-confirmed against an external strategy guide for ch12's specific
                      # 2-wave pattern) -- see sweep_chapter()'s comment for the full derivation.


def confirm_end_turn(name: str, shots_dir: Path, log: list[str], enemy_addrs: list[int] | None = None) -> dict:
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
    `Up` used at the time was, by this docstring's own admission two
    paragraphs up, only confirmed for ch27's specific unit cluster (very
    possibly compounded by the roster-size-mismatch caveat in doc99: ch02/
    ch12's synthetic saves keep the full late-game 13-person roster, which
    changes the deployment cluster's shape from what a real ch02/ch12 save
    would have). This was a real, still-open generalization gap in THIS
    function, not a save-construction bug -- see doc99's "branchcheck"
    section for the full writeup.

    2026-08-27 "endturngen" round -- GENERALIZED, closing the gap flagged
    directly above: the hardcoded `Up` is replaced with
    find_empty_adjacent_tile() (see its own docstring), which checks the
    live HUD thumbnail (doc58's actual documented empty-tile signal -- a
    plain terrain thumbnail with no character portrait/HP digits, not a
    guess) and tries Up/Down/Left/Right in turn, undoing each failed
    attempt before trying the next, until it finds a tile the game itself
    confirms is empty -- or honestly reports failure if none of the 4
    adjacent tiles qualify, rather than blindly pressing Enter into a
    probably-occupied tile the way the old code did for every chapter but
    ch27. See docs/knowledge-base/99-chapter-sweep-results.md's
    "endturngen" section for the live cross-chapter validation results.

    2026-08-27 "ch12diag" round: after confirming YES, this function used to
    just sleep(2.0) and take one screenshot, trusting the caller to notice a
    visual win transition later. Live testing on ch12 (whose per-chapter
    win-check handler 0x2073d is a genuinely DIFFERENT function from ch27's
    default-plus-L path -- doc25 §3's handler table, table_idx 11, not a
    screenshot-detection gap) found the engine's own pending-result-code
    global ([0x53ecc], see PENDING_RESULT_CODE_LIVE's module comment) does
    NOT flip 0->2 until ~8s after the YES keypress lands (repeated polling:
    t=1.3s..6.3s still read 0, t=8.0s read 2, stayed 2 afterward) -- almost
    4x longer than the old flat sleep(2.0) gave it. This function now polls
    [0x53ecc] directly (ground truth, not a screenshot heuristic) for up to
    ENGINE_WIN_POLL_MAX_S seconds after confirming YES, logging the exact
    second it flips. This is a REAL, general fix (not a ch12-only hack): the
    same live round also confirmed [0x53c03] (chapter index) advancing
    11->12 in lockstep with [0x53ecc] hitting 2, which doc58 續二十八's full
    disassembly of the campaign loop (FUN_00025bf4) already proved is the
    SAME unconditional every-postbattle-handler behavior used for ch24
    (whose raw 23->24 transition was separately observed reaching the real
    on-disk FD2.SAV in an earlier round of this project) -- i.e. this
    generalizes to any chapter using the 0x51b19/0x51de9 dispatch tables,
    which per doc25 §3 is EVERY chapter, not just ch27.

    2026-08-27 "ch12diag" round -- honest caveat: the SAME live session found
    that after the engine-level win fires, further blind Return-tapping can
    wander into an unrelated, genuinely stuck submenu (observed: a character
    status/spell-list screen that stopped responding to ANY input, including
    Escape, for 60+ taps and 24s of pure passive waiting) if
    find_empty_adjacent_tile() failed to confirm an empty tile first (this
    round hit exactly that fallback). This function's own ring-opening
    fallback (log a WARNING and press on anyway) is UNCHANGED here -- the
    fix below only makes win DETECTION reliable, it does not make the
    ring-opening sequence itself immune to landing on a dead-end submenu for
    every chapter's deployment layout. That remains an honest, unresolved
    per-chapter risk -- see docs/knowledge-base/99-chapter-sweep-results.md's
    "ch12diag" section.
    """
    found_empty, _ = find_empty_adjacent_tile(name, shots_dir, log)
    if not found_empty:
        log.append("confirm_end_turn: WARNING -- find_empty_adjacent_tile did not confirm an empty tile "
                    "within one step in any of the 4 directions; opening the ring anyway at the cursor's "
                    "(likely still-occupied) position as a last-resort best-effort fallback -- this will "
                    "probably select/act on a unit instead of opening the system ring, and is EXPECTED to "
                    "fail honestly for this chapter's deployment layout rather than silently claim success")
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
    enter_debugger(name)
    time.sleep(0.3)
    chapter_before = read_chapter_index_live(name)
    debugger_cmd(name, "RUN")
    time.sleep(0.2)

    send_keys(name, "Return")  # confirms YES
    # 2026-08-27 "ch12diag" fix: poll [0x53ecc] directly (ground truth) instead
    # of a flat sleep(2.0) -- see this function's docstring for the live
    # derivation (ch12 needed ~8s, not 2s, for the code to flip).
    t_start = time.time()
    engine_code = None
    while time.time() - t_start < ENGINE_WIN_POLL_MAX_S:
        time.sleep(0.7)
        enter_debugger(name)
        time.sleep(0.25)
        engine_code = read_pending_result_code(name)
        debugger_cmd(name, "RUN")
        time.sleep(0.15)
        if engine_code in (ENGINE_WIN_CODE, ENGINE_EVENT_CODE):
            break
    elapsed = time.time() - t_start
    engine_win = engine_code == ENGINE_WIN_CODE
    if engine_win:
        log.append(f"confirm_end_turn: ENGINE-LEVEL WIN CONFIRMED -- [0x53ecc] flipped to "
                    f"{ENGINE_WIN_CODE} (win) after {elapsed:.1f}s of polling (ground truth via "
                    f"debugger read, not a screenshot guess)")
    elif engine_code == ENGINE_EVENT_CODE:
        log.append(f"confirm_end_turn: [0x53ecc] flipped to {ENGINE_EVENT_CODE} (mid-battle scripted "
                    f"event, NOT a win -- doc25 §6) after {elapsed:.1f}s -- battle continues, this is "
                    f"not the win-check firing")
    else:
        log.append(f"confirm_end_turn: [0x53ecc] never reached a resolved code ({ENGINE_WIN_CODE}=win/"
                    f"{ENGINE_EVENT_CODE}=event) within {ENGINE_WIN_POLL_MAX_S:.0f}s of polling "
                    f"(last read: {engine_code!r}) -- honestly inconclusive, not assumed to be a win")
    enter_debugger(name)
    time.sleep(0.3)
    chapter_after = read_chapter_index_live(name)
    debugger_cmd(name, "RUN")
    time.sleep(0.2)
    if chapter_after is not None and chapter_before is not None and chapter_after != chapter_before:
        log.append(f"confirm_end_turn: [0x53c03] (chapter index) advanced live {chapter_before}->{chapter_after} "
                    f"-- matches doc58 續二十八's proven every-postbattle-handler INC behavior")
    log.append(f"confirm_end_turn: find_empty_adjacent_tile(found={found_empty})->Enter(open ring)->"
               f"Down(END)->Enter(confirm)->[re-kill]->Enter(YES)->poll[0x53ecc]")
    shot = screenshot(name, shots_dir / "post_end_turn.png")
    return {
        "screenshot": shot,
        "engine_win": engine_win,
        "engine_code": engine_code,
        "chapter_index_before": chapter_before,
        "chapter_index_after": chapter_after,
    }


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
# exactly 2 text panels under repeated Return taps.
#
# 2026-08-27 "slowplay" round + USER-CONFIRMED GAME-DESIGN FACT (do not
# re-litigate this in a future round without new evidence): FD2's dual-
# ending mechanism means reaching EITHER ending (good or bad) terminates
# that playthrough -- there is no "next chapter" for ch27's no-Sky-Key
# bad-ending branch (悠妮 leaves without the Sky Key, doc58 續六十二 §4's
# "缺鑰臂") to advance to. The 悠妮-card "loop" is this branch's designed
# termination sequence, not a bug to be unblocked -- so no amount of input
# timing on THIS save will ever produce a chapter-byte advance here, and
# that was never a defect.
#
# What live testing this round (instance 'slowplay', ch27's real unpadded
# save) DID establish, purely observationally: continuing to tap Return on
# the 悠妮 card reproduces the same 2-panel alternation every prior round
# saw (confirmed even with slow, human-scale 6s-apart taps -- pacing alone
# does not change the outcome). But a subsequent ~30s window of sending
# NO input at all was followed by the screen moving on by itself: a new
# animated cutscene, the ending credits roll ("美術編輯 ART EDIT"), then a
# static "THE END" screen -- with FD2.SAV's md5 completely unchanged
# throughout (no autosave fires on this branch, consistent with it being a
# genuine game-ending terminus, not a mid-run save point). Whether that
# EB FE self-loop disassembly-proven elsewhere in this project (doc35
# §9.11.6) is the exact same instruction this observation passed through,
# or a separate interrupt/timer-driven wait state that also happens to
# alternate 2 dialogue panels, was NOT resolved this round -- not claiming
# to have overturned that static finding, only reporting what was directly
# observed on screen.
#
# Practical upshot for THIS function: continuing to tap Return during an
# alternating 2-state screen is at best useless and at worst actively
# holds the montage in that state, so back off to passive polling when
# that pattern is detected -- see STUCK_CYCLE_PASSIVE_POLL_* below. This
# does NOT mean ch27's real save can ever reach a chapter-advance `pass`
# (it structurally cannot, per the design fact above) -- validating
# whether the mass-kill+End-Turn shortcut correctly advances the chapter
# byte on an ORDINARY, non-terminal chapter (one whose win does not route
# into a character-card montage at all) is a separate, NOT-yet-confirmed
# question for a future round to target directly, not something this fix
# resolves.
POSTBATTLE_MONTAGE_TAPS = 70
STUCK_CYCLE_PASSIVE_POLL_INTERVAL_S = 4.0
STUCK_CYCLE_PASSIVE_POLL_MAX_S = 45.0


def advance_postbattle_montage(name: str, shots_dir: Path, log: list[str],
                                taps: int = POSTBATTLE_MONTAGE_TAPS) -> None:
    """Bounded Return-tapping through the postbattle dialogue/CG/poem/
    character-card montage after a genuine win, so the chapter's real
    autosave (whenever in this sequence it actually happens) has the best
    available chance to fire before sweep_chapter() reads the save back.

    2026-08-27 "slowplay" fix: if a 2-state alternation is detected (the
    live-proven signature of the 悠妮-card-style timer-gated auto-advance,
    see the long module comment above), STOP tapping Return -- every tap
    resets the idle timer that gates the real auto-advance -- and instead
    poll passively (screenshot only, no keypress) every
    STUCK_CYCLE_PASSIVE_POLL_INTERVAL_S seconds for up to
    STUCK_CYCLE_PASSIVE_POLL_MAX_S seconds total, watching for the screen
    to change to a third state. If it does, resume normal tapping for the
    remaining tap budget (there may be further dialogue after whatever
    that new scene is). If the passive window times out with no change,
    give up honestly and fall through to the old best-effort tap loop for
    whatever budget remains -- this is a live-proven fix for the specific
    2-state-cycle failure mode, not a guarantee every stuck screen is this
    same mechanism."""
    hashes: list[str] = []
    i = 0
    while i < taps:
        send_keys(name, "Return")
        time.sleep(0.5)
        shot = screenshot(name, shots_dir / f"montage_{i:03d}.png")
        h = file_md5(shot)
        hashes.append(h)
        i += 1
        if len(hashes) >= 3 and hashes[-1] == hashes[-3] and hashes[-1] != hashes[-2]:
            log.append(f"advance_postbattle_montage: detected a 2-state alternation after {i} taps "
                        f"(hash repeats every other tap) -- this is the live-proven 悠妮-card-style "
                        f"timer-gated auto-advance signature (doc99 'slowplay' round); switching to "
                        f"PASSIVE polling (no more keypresses) for up to {STUCK_CYCLE_PASSIVE_POLL_MAX_S:.0f}s")
            waited = 0.0
            stuck_hash = hashes[-1]
            broke_free = False
            while waited < STUCK_CYCLE_PASSIVE_POLL_MAX_S:
                time.sleep(STUCK_CYCLE_PASSIVE_POLL_INTERVAL_S)
                waited += STUCK_CYCLE_PASSIVE_POLL_INTERVAL_S
                shot = screenshot(name, shots_dir / f"montage_passive_{int(waited):03d}s.png")
                h = file_md5(shot)
                if h != stuck_hash:
                    log.append(f"advance_postbattle_montage: screen changed after {waited:.0f}s of pure idle "
                                f"(no keypress) -- the auto-advance fired, resuming normal tapping")
                    broke_free = True
                    hashes = [h]
                    break
            if not broke_free:
                log.append(f"advance_postbattle_montage: still no change after {STUCK_CYCLE_PASSIVE_POLL_MAX_S:.0f}s "
                            f"of passive polling -- giving up on the passive strategy for this screen, falling "
                            f"back to plain tapping for the remaining budget (honest failure, not a guess)")
                hashes = []
    screenshot(name, shots_dir / "post_montage_advance.png")
    log.append(f"advance_postbattle_montage: sent up to {taps} Return taps (with passive-poll detour if a "
               f"2-state cycle was seen) trying to clear the postbattle dialogue/CG/poem/character-card montage")


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

# 2026-08-27 "endturngen" round: a THIRD false positive, found live via this
# round's own find_empty_adjacent_tile() sanity checks on ch02 and ch27 --
# a full-screen story/flashback dialogue box (e.g. ch02's throne-room
# succession-dispute scene, and ch27's "這裡就是遺跡了嗎" ruins line) that
# includes a large character portrait defeats BOTH existing checks at once:
# the portrait's varied pixels push screen_looks_like_dialogue()'s strip
# variance just over its 9000 threshold (14000+ measured), and the panel's
# flat theme-blue background still reads as "HUD blue" inside
# BATTLE_HUD_BOX_REGION -- so screen_shows_battle_hud() returned True for a
# screen that was not remotely a real battle. THE FIX: the genuine HUD box
# is small (~140x78) and floats over the map with visible terrain just past
# its right edge; a full-screen dialogue panel keeps going well past that
# edge. Sampling a strip just to the right of the box
# (BATTLE_HUD_RIGHT_STRIP_REGION) and requiring it NOT be mostly the same
# theme-blue distinguishes the two cleanly: live samples read 0.000-0.050
# "blue" just right of a genuine HUD box (map terrain there) vs 0.906-0.930
# for both flashback-dialogue false positives (panel still blue that far
# right). Verified against all 6 samples collected so far (4 genuine
# HUD-box screenshots across empty/occupied tiles, 2 flashback-dialogue
# false positives) with zero misclassifications after this fix, vs 2/6
# misclassified before it.
BATTLE_HUD_RIGHT_STRIP_REGION = (350, 520, 420, 598)
BATTLE_HUD_RIGHT_STRIP_MAX_BLUE_FRAC = 0.3

# 2026-08-27 "ch19diag" round: ch19's live screenshots (docs/knowledge-base/
# 99-chapter-sweep-results.md's "新卡點 B") show this SAME small HUD box
# rendered in the screen's BOTTOM-RIGHT corner instead of bottom-left --
# confirmed both visually (dozens of already-captured attempt_camp_exit()
# screenshots from a prior round's ch19 run, campexit_*_dialogueNN.png in
# .wsl_build/chapter_sweep_r2/ch19/shots/, show a real, populated battle map
# with a movable cursor and even the command ring opening, from as early as
# tap ~20-35 of the existing 120-tap budget -- i.e. NOT a timing/budget
# problem, the battle is ready well within budget) and quantitatively (a
# sliding blue-fraction scan across those screenshots' bottom band peaks at
# x0=680, frac~0.44 -- matching ch27's own left-side calibration reading of
# ~0.48 almost exactly). This mirrored region is the screen-width mirror of
# BATTLE_HUD_BOX_REGION/BATTLE_HUD_RIGHT_STRIP_REGION (harness screenshots
# are a FIXED 1024x768 per SCREENSHOT_DIALOGUE_STRIP_Y's module comment,
# mirror_x(x) = 1024 - x): mirror(205)=819, mirror(345)=679, which reproduces
# the empirically-found x0=679 to within a pixel -- strong corroborating
# evidence this really is a literal left/right mirror of the same UI element
# (most likely because the info box renders on whichever side of the screen
# the browsing cursor is currently NOT on, to avoid overlapping it -- ch27's
# calibration screenshots happened to have the party/cursor on the right
# half of the map, ch19's on the left half), not a coincidence or a
# ch19-specific different UI element.
BATTLE_HUD_BOX_REGION_R = (679, 520, 819, 598)
BATTLE_HUD_LEFT_STRIP_REGION_R = (604, 520, 674, 598)


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
    tried live this round (12/12 in the validation sweep that caught this).

    2026-08-27 "endturngen" round -- THIRD guard added (see
    BATTLE_HUD_RIGHT_STRIP_REGION's module comment above): also require
    that the strip just past the box's right edge is NOT still the same
    theme-blue, which rules out full-screen story/flashback dialogue boxes
    with a large character portrait (they defeated both earlier checks at
    once -- portrait pixels push the dialogue-variance check over threshold,
    and the panel's flat blue reads as "HUD blue" too).

    2026-08-27 "ch19diag" round -- DROPPED the screen_looks_like_dialogue()
    pre-gate, ADDED a mirrored bottom-right box/strip pair (see
    BATTLE_HUD_BOX_REGION_R's module comment): ch19 turned out to defeat
    BOTH of this function's existing guards independently, neither of which
    was a timing problem --
      1. screen_looks_like_dialogue() false-POSITIVE (misread ch19's real,
         fully-populated battle-map frames as "still a flat dialogue panel")
         because ch19's terrain art is measurably lower-contrast at the
         sampled row than every chapter this heuristic was calibrated
         against: live variance readings of 2200-11000 across ch19's
         confirmed-real battle screenshots vs ch27's 17870-20908 on its own
         confirmed-real battle screenshot and even the ORIGINAL false-
         positive dialogue panel this check was built to catch (25994) --
         i.e. this single-row variance heuristic does not reliably separate
         "real battle terrain" from "flat dialogue panel" at all once a
         second chapter's art style is in the sample set (the panel's own
         variance can exceed the battle screen's), it was never a principled
         fix, just one that happened to work for the specific chapters
         tested so far. Confirmed this is not what actually matters for
         correctness: every call site that consumes this function's result
         (attempt_camp_exit()'s tap loop, sweep_chapter()'s post-load check)
         ALSO requires >=REAL_BATTLE_MIN_ENEMIES live enemy records before
         treating a "hud visible" reading as real, so a false positive here
         only costs one wasted debugger poll, never a wrong verdict -- only
         false NEGATIVES (missing the real battle) are actually dangerous,
         which is what dropping this over-tight gate fixes.
      2. The HUD box itself renders bottom-RIGHT for ch19 instead of
         bottom-left (BATTLE_HUD_BOX_REGION_R's module comment) -- the
         original code had no way to find it there at all, regardless of
         the dialogue-gate.
    Verified against a small regression set (ch27's own confirmed real-
    battle frame, the 莎拉 exit-confirm portrait dialogue, ch21/22/26's
    troop-selection roster screens, ch19's confirmed real-battle frames):
    dropping the dialogue-gate and checking box+strip on both sides still
    correctly rejects all the known historical false positives (their
    matched-side strip reads 0.15-0.93, well above the reject threshold --
    the strip check alone was already sufficient to reject them, the
    variance gate was redundant for these specific cases and simply never
    tested against a lower-contrast chapter until now) while now correctly
    detecting ch19's real battle within its existing tap budget."""
    try:
        from PIL import Image
    except ImportError:
        return False  # fail closed here -- callers should keep waiting/advancing
    im = Image.open(png_path).convert("RGB")
    return _find_hud_box_side(im) is not None


def _box_and_strip_pass(im, box_region: tuple[int, int, int, int],
                         strip_region: tuple[int, int, int, int]) -> bool:
    pixels = list(im.crop(box_region).getdata())
    frac = sum(1 for p in pixels if _is_hud_blue(p)) / len(pixels)
    if not (frac > BATTLE_HUD_BLUE_FRAC_THRESHOLD):
        return False
    strip_pixels = list(im.crop(strip_region).getdata())
    strip_frac = sum(1 for p in strip_pixels if _is_hud_blue(p)) / len(strip_pixels)
    return strip_frac < BATTLE_HUD_RIGHT_STRIP_MAX_BLUE_FRAC


def _find_hud_box_side(im) -> str | None:
    """Returns "L" if the battle HUD box is showing in its original
    bottom-left calibrated position (BATTLE_HUD_BOX_REGION), "R" if it's
    showing in the ch19diag-round mirrored bottom-right position
    (BATTLE_HUD_BOX_REGION_R), or None if neither matches. Shared by
    screen_shows_battle_hud() and cursor_tile_is_empty()/
    BATTLE_HUD_THUMBNAIL_REGION so the thumbnail sub-crop (see that
    region's module comment) is read from the SAME side the box itself was
    actually found on -- reading a hardcoded left-only thumbnail crop while
    the real box sits on the right (or vice versa) would silently always
    read "plain terrain, no portrait" regardless of what's really under the
    cursor, since the wrong-side crop is never anything but background
    map art. This was caught live during the ch19diag round before it could
    bite confirm_end_turn()'s cursor-placement logic for ch19."""
    if _box_and_strip_pass(im, BATTLE_HUD_BOX_REGION, BATTLE_HUD_RIGHT_STRIP_REGION):
        return "L"
    if _box_and_strip_pass(im, BATTLE_HUD_BOX_REGION_R, BATTLE_HUD_LEFT_STRIP_REGION_R):
        return "R"
    return None


# 2026-08-27 "endturngen" round: a SECOND, finer-grained HUD read, used to
# replace confirm_end_turn()'s old hardcoded single `Up` cursor move (see
# that function's docstring history) with a chapter-general empty-tile
# search. doc58's "續" log (e.g. the live screenshots behind aiE2_findempty*
# vs aiE2_cursor2/3/s18_openground -- see docs/knowledge-base/99-chapter-
# sweep-results.md's "endturngen" section for the calibration writeup) shows
# the SAME small HUD box has a "thumbnail" sub-region in its top-left corner
# that renders two distinct ways depending on what the browsing cursor is
# currently over:
#   - on a unit: a colorful character face PORTRAIT, with a bright white/
#     light-blue HP NUMBER overlaid across its bottom (e.g. "860", "751").
#   - on empty ground: a plain, muted terrain-tile texture (grass green /
#     rock brown-gray) with NO overlaid digits at all -- only the "A+XX
#     D+XX" terrain-bonus text to the box's right (present in BOTH cases,
#     so it cannot be used to tell them apart; the thumbnail is the only
#     distinguishing region).
# This is a strictly finer signal than screen_shows_battle_hud() (which only
# proves "a movable battle cursor exists right now", true in both cases) --
# it answers "is the tile UNDER the cursor empty", the actual precondition
# doc58 續六十二 established for Enter to open the system ring instead of
# acting on a unit. Calibrated against 4 live screenshots this round (2
# occupied thumbnails with real HP digits "860"/"751", 2 empty thumbnails):
# occupied reads 0.030-0.044 bright-pixel fraction in the thumbnail crop,
# empty reads 0.0013 both times -- better than a 20x gap, threshold set
# well inside it.
BATTLE_HUD_THUMBNAIL_REGION = (
    BATTLE_HUD_BOX_REGION[0] + 3, BATTLE_HUD_BOX_REGION[1] + 3,
    BATTLE_HUD_BOX_REGION[0] + 58, BATTLE_HUD_BOX_REGION[1] + 58,
)
# 2026-08-27 "ch19diag" round: mirror of the region above, for when
# _find_hud_box_side() reports "R" (see BATTLE_HUD_BOX_REGION_R's module
# comment) -- the thumbnail sub-region sits in the SAME corner of the box
# relative to the box itself regardless of which side of the screen the box
# is on (box's own left edge + a fixed inset), so this is BATTLE_HUD_BOX_
# REGION_R's left edge (679) + the same +3/+58 insets, NOT a full screen-
# width mirror of BATTLE_HUD_THUMBNAIL_REGION's coordinates.
BATTLE_HUD_THUMBNAIL_REGION_R = (
    BATTLE_HUD_BOX_REGION_R[0] + 3, BATTLE_HUD_BOX_REGION_R[1] + 3,
    BATTLE_HUD_BOX_REGION_R[0] + 58, BATTLE_HUD_BOX_REGION_R[1] + 58,
)
HUD_THUMBNAIL_BRIGHT_FRAC_THRESHOLD = 0.01


def _is_hp_digit_bright(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r > 180 and g > 190 and b > 200


def cursor_tile_is_empty(png_path: Path) -> bool | None:
    """True if the HUD box's thumbnail sub-region shows a plain terrain
    tile (no portrait, no HP digits) -- i.e. the browsing cursor currently
    sits on empty ground and Enter will open the system ring rather than
    select/act on whatever unit is there. False if a portrait+HP-number
    thumbnail is showing (cursor is on a unit). None if the battle HUD box
    itself isn't visible at all (screen_shows_battle_hud() false) -- callers
    must not treat None as either True or False, it means "can't tell".

    2026-08-27 "ch19diag" round: reads the thumbnail from whichever side
    _find_hud_box_side() actually found the box on (left or ch19-style
    mirrored right), not unconditionally from the left -- see
    BATTLE_HUD_THUMBNAIL_REGION_R's module comment for why reading the
    wrong side would have silently always reported "empty"."""
    try:
        from PIL import Image
    except ImportError:
        return None  # fail to "can't tell", same posture as screen_shows_battle_hud's ImportError path
    im = Image.open(png_path).convert("RGB")
    side = _find_hud_box_side(im)
    if side is None:
        return None
    thumbnail_region = BATTLE_HUD_THUMBNAIL_REGION if side == "L" else BATTLE_HUD_THUMBNAIL_REGION_R
    pixels = list(im.crop(thumbnail_region).getdata())
    frac = sum(1 for p in pixels if _is_hp_digit_bright(p)) / len(pixels)
    return frac < HUD_THUMBNAIL_BRIGHT_FRAC_THRESHOLD


_OPPOSITE_DIRECTION = {"Up": "Down", "Down": "Up", "Left": "Right", "Right": "Left"}
EMPTY_TILE_SEARCH_ORDER = ["Up", "Down", "Left", "Right"]

# 2026-08-27 "endturngen" round: bounded Return-tap budget for
# find_empty_adjacent_tile()'s leading dialogue-clear step (see that
# function's docstring for why it exists -- a lingering scripted dialogue
# beat surviving the settle loop, reproduced 3/3 live chapters). Kept modest
# (not POSTBATTLE_MONTAGE_TAPS-sized) because this runs BEFORE End Turn is
# even attempted; a long-running scripted sequence here more likely means a
# genuinely unusual chapter that should honestly fall through to
# find_empty_adjacent_tile()'s own "found=False" reporting than that more
# taps would have gotten through it.
DIALOGUE_CLEAR_MAX_TAPS = 20


def find_empty_adjacent_tile(name: str, shots_dir: Path, log: list[str]) -> tuple[bool, Path]:
    """Generalized replacement for confirm_end_turn()'s old hardcoded
    single `Up` tap (2026-08-27 "endturngen" round -- closes the gap
    docs/knowledge-base/99-chapter-sweep-results.md's "branchcheck" section
    flagged: a single ch27-calibrated `Up` does not generalize to other
    chapters' deployment layouts, and ch02/ch12 never actually reached a
    real win because of it).

    Checks the CURRENT tile first via cursor_tile_is_empty() -- no keypress
    needed if the cursor already happens to be over empty ground. Otherwise
    tries each of EMPTY_TILE_SEARCH_ORDER (Up, Down, Left, Right) in turn:
    tap the direction, screenshot, check cursor_tile_is_empty() against the
    real doc58-documented signal (HUD thumbnail = plain terrain, not a
    portrait) -- not a guess based on tap count or a fixed direction. If
    that direction's tile is NOT confirmed empty, tap the OPPOSITE direction
    to undo the move before trying the next candidate, so the cursor always
    returns to its starting unit before each new attempt -- this keeps the
    search local/adjacent to the selected unit's cluster (matching doc58's
    own "移動游標到空地格" wording -- move ONE step to an empty tile -- not
    an unbounded walk that might wander into scripted terrain/triggers).

    Returns (found, last_screenshot_path). If found is True, the cursor is
    left sitting on the confirmed-empty tile (net zero or one step from
    wherever it started). If found is False, none of the 4 adjacent tiles
    were confirmed empty and the cursor has been walked back to its
    starting position -- callers must treat this as an honest, reportable
    generalization gap for that chapter's specific deployment layout (e.g.
    a fully boxed-in unit with no empty neighbor within one step), not
    silently press on as if a tile had been found.

    2026-08-27 "endturngen" round -- leading dialogue-clear step added after
    live testing across ch02/ch12/ch27 (post BATTLE_HUD_RIGHT_STRIP_REGION
    fix) hit the SAME pattern 3/3 times: sweep_chapter()'s settle-round loop
    (6 rounds x 2.5s passive sleep, no keypresses, run to let the enemy
    array finish populating -- see sweep_chapter()'s own long comment) is
    also enough idle real time for an ordinary SCRIPTED DIALOGUE BEAT that
    was already playing to keep going, so by the time this function's first
    check runs, cursor_tile_is_empty() reads None (not True/False) --
    genuinely can't tell, because the screen is mid-dialogue, not because
    the tile classification is wrong. This was reproduced with three
    completely different dialogue contents (ch27's 悠妮 flashback scene,
    ch02's pirate/robot cutscene, ch12's forest-travel dialogue), so it is
    chapter-general, not a single chapter's quirk -- and it is the SAME
    underlying "cutscene can outlive the settle window" hazard doc99's
    winverify round first flagged for ch27's boss intro specifically, now
    confirmed to generalize. This function cannot fix that hazard (it is
    sweep_chapter()'s settle loop that needs the real, deeper fix -- out of
    this task's cursor-generalization scope), but it CAN stop wasting its
    directional search on a screen it already knows isn't readable: if the
    starting check is None, spend a bounded number of plain `Return` taps
    (DIALOGUE_CLEAR_MAX_TAPS) trying to reach a readable state first, same
    "keep tapping Return, it's always safe to advance dialogue with" logic
    this module already relies on elsewhere (attempt_camp_exit,
    advance_postbattle_montage) -- then run the normal search either way."""
    shot = screenshot(name, shots_dir / "findempty_000_start.png")
    state = cursor_tile_is_empty(shot)
    log.append(f"find_empty_adjacent_tile: starting tile cursor_tile_is_empty={state}")
    if state is True:
        log.append("find_empty_adjacent_tile: cursor already on an empty tile, no movement needed")
        return True, shot
    if state is None:
        for clear_tap in range(1, DIALOGUE_CLEAR_MAX_TAPS + 1):
            send_keys(name, "Return")
            time.sleep(0.6)
            shot = screenshot(name, shots_dir / f"findempty_clear_{clear_tap:03d}.png")
            state = cursor_tile_is_empty(shot)
            if state is not None:
                log.append(f"find_empty_adjacent_tile: cleared lingering dialogue/cutscene after "
                           f"{clear_tap} Return tap(s), cursor_tile_is_empty={state}")
                break
        else:
            log.append(f"find_empty_adjacent_tile: still no readable battle HUD after "
                       f"{DIALOGUE_CLEAR_MAX_TAPS} dialogue-clear Return taps -- proceeding to the "
                       f"directional search anyway, it will honestly report failure rather than guess")
        if state is True:
            log.append("find_empty_adjacent_tile: cursor on an empty tile after dialogue-clear, no movement needed")
            return True, shot
    step = 1
    for direction in EMPTY_TILE_SEARCH_ORDER:
        send_keys(name, direction)
        time.sleep(0.5)
        shot = screenshot(name, shots_dir / f"findempty_{step:03d}_{direction}.png")
        state = cursor_tile_is_empty(shot)
        log.append(f"find_empty_adjacent_tile: tried {direction}, cursor_tile_is_empty={state}")
        step += 1
        if state is True:
            log.append(f"find_empty_adjacent_tile: found empty tile via {direction}")
            return True, shot
        # Not confirmed empty (occupied, or HUD unreadable) -- undo before
        # trying the next direction so every attempt starts from the same
        # origin tile.
        opposite = _OPPOSITE_DIRECTION[direction]
        send_keys(name, opposite)
        time.sleep(0.5)
        shot = screenshot(name, shots_dir / f"findempty_{step:03d}_undo_{opposite}.png")
        step += 1
    log.append("find_empty_adjacent_tile: none of Up/Down/Left/Right landed on a confirmed-empty tile -- "
                "cursor walked back to its starting position; this is an honest generalization gap for this "
                "chapter's deployment layout, not a bug to paper over")
    return False, shot


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

# Chapter-specific "wait this many real turns before the FIRST mass-kill"
# override. 2026-08-27 "ch19banor" round: ch19 was previously one of an
# 8-chapter club whose engine-level win-check ([0x53ecc]) never left 0 even
# with every scan-found camp==0 enemy record correctly, persistently marked
# dead (see docs/knowledge-base/99-chapter-sweep-results.md's "ch19diag"
# section). A WebFetch of an external walkthrough (chiuinan.github.io fd2
# walkthrough) gave ch19's specific mechanic: an ally, 巴拿羅西亞/Banoroshia,
# joins "第六回合己方結束後" (after ally turn 6 concludes), and "若巴拿羅西亞
# 尚未出現便消滅完敵人，則巴拿羅西亞不會加入" (killing all enemies before she
# appears means she never joins). The prior ch19diag round's mass-kill fired
# within seconds of battle detection -- almost certainly turn 1. A live
# no-buff probe this round (passing 6 real turns via confirm_end_turn(...,
# enemy_addrs=None) with NO mass-kill and NO stat hacks, then mass-killing
# and running End-Turn exactly once) got [0x53ecc]==2 (ENGINE_WIN_CODE) on
# the very first kill-cycle -- the FIRST time ch19 has ever reached a
# confirmed engine-level win. IMPORTANT HONEST CAVEAT: the probe's own record
# dump (camp+status byte on every slot, every turn) found NO new ally record
# and NO non-{0,2} camp value ever appeared across all 6 turns -- i.e.
# Banoroshia's literal roster join was NOT directly observed, so this is NOT
# proof the win-check specifically requires her presence; an equally
# consistent alternative is a plain turn-count gate in the win-check itself,
# unrelated to any specific unit. What IS directly, reproducibly established
# is the practical fix: for ch19, waiting turns before the first mass-kill
# (instead of killing immediately) is necessary. See doc99's "ch19banor"
# section for the full writeup, screenshots, and the not-yet-ruled-out
# possibility that she joins via an in-place reactivation of an
# already-allocated ally slot (this tool only tracks camp+status byte, not
# a character-id field, so that specific case would not have been caught).
# This does NOT change the separate, still-open "engine win confirmed but
# on-disk FD2.SAV chapter byte never advances" question (doc25 §9.1) -- ch19
# hit that exact same wall this round (chapter byte stayed 18, did not
# advance to 19) despite the win-check itself resolving.
#
# 2026-08-27 "ch2killgen" round: testing whether the ch19 turn-count-gate
# fix generalizes to the rest of the 7-chapter "stuck at 0" club
# (ch02/03/04/07/11/15/20; ch02 has its own separate village-protection
# investigation track and is out of scope this round). An external
# walkthrough (chiuinan.github.io fd2, WebFetched) gives each remaining
# chapter's specific reinforcement-wave timing:
#   ch03: turn-3-START trigger ("第三回合開始時...出現") -- a turn-START
#     trigger is a different shape than ch19's turn-END trigger, so this is
#     an extrapolation, not a proven-identical mechanism. Guess: wait 3.
#   ch04: turn-4-END trigger (4 beasts at 4 corners) PLUS a "kill one, other
#     three flee" mechanic. Guess: wait 4. (mass_kill_enemies() writes the
#     death signature directly via debugger, bypassing normal combat/AI
#     resolution entirely -- it does not "kill one at a time" through the
#     game's own turn loop, so there is no in-game moment where the flee
#     mechanic's AI trigger condition should even fire; this is a reasoned,
#     UNVERIFIED prediction that the flee mechanic is simply inapplicable to
#     this tool's kill method, not a live-confirmed finding.)
#   ch15: two waves, turn-7-END and turn-9-END. Guess: wait 9 (through both).
#   ch20: turn-4-END trigger for the first (only unconditionally-described)
#     wave. Guess: wait 4. ch20 also has a "沼澤怪物之外的敵人全滅" (all
#     enemies EXCEPT swamp monsters) victory condition and a "精靈全滅"
#     (all elves die) fail condition -- see sweep_chapter()'s ch20-specific
#     comment for why this tool does not need bespoke swamp-monster/elf
#     handling to test the turn-count-gate hypothesis itself.
#   ch07 and ch11 have NO turn-count trigger in the walkthrough text (ch07 is
#     a position/movement trigger past a specific map location; ch11's
#     blocker is undiagnosed) -- so a turn-count wait was not expected to fix
#     either on mechanism grounds.
#
# RESULT: ch03/ch04/ch15/ch20 all confirmed on the FIRST post-wait
# kill-cycle, same as ch19 -- see doc99's "ch2killgen" section for the full
# per-chapter writeup (enemy counts, screenshots, honest caveats on what was
# and wasn't directly observed for the ch04 flee/ch20 swamp-monster
# predictions). ch07 was ALSO tested (despite the mechanism-based
# expectation it wouldn't help) as a cheap experiment and, once a battle-
# detection flake on the first attempt was ruled out with a clean re-run,
# ALSO confirmed on the first post-wait kill-cycle with a guessed 3-turn
# wait -- so this dict entry should not be read as "this chapter's
# walkthrough-documented trigger is turn-count-shaped", only as "waiting
# turns before the first mass-kill empirically unblocks this chapter's
# win-check". ch11 is the one chapter where this round's turn-wait test
# was run cleanly (25 enemies found, all confirmed to persistently carry
# the death signature after a rescan) and STILL did not unblock
# [0x53ecc] -- ch11 is NOT in this dict; its blocker is something this
# tool does not yet identify (see doc99's "ch2killgen" section, ch11
# sub-section, for the live evidence and next-round suggestion).
#
# 2026-08-28 "ch11diag" round follow-up: ch11's win-check handler
# (0x51b19 table_idx10) was confirmed, via direct table-byte read +
# disasm, to be the LITERAL SAME shared default routine (0x205b4/0x205be)
# as ch03/ch04/ch07 -- all three confirmed working with this exact
# mass-kill+turn-wait mechanism -- so the handler itself is not the
# problem. A dedicated live probe (.wsl_build/chapter_sweep_ch11diag/
# probe_ch11_diag.py) then directly read the two "one level up"
# candidates instead of guessing: live [0x53c03] (chapter index) == 10,
# exactly matching this table slot, so dispatch is routing correctly; and
# live [0x53beb] (the native win-check loop's own upper bound) == 38,
# EXACTLY matching the true record array (13 allies at k=0..12 + 25
# enemies at k=13..37, byte-verified -- everything from k=38 onward is
# unstructured non-unit memory, not additional hidden records). An
# unconditional 160-slot scan (bypassing this module's own
# all-zero-skip heuristic) found zero legitimate extra camp==0 records;
# the two raw hits it did turn up (k=96, k=148) sit well past the true
# array bound and read as garbage/text data, not units -- confirmed false
# positives, not a heuristic bug. Re-running the full turn-wait+mass-kill
# (all 25 real enemies dead, plus the 2 garbage addresses for good
# measure) still left [0x53ecc]==0 after a fresh 15s poll. All four
# hypotheses this tool could test live (handler differs / missed enemy
# record / loop-bound mismatch / wrong dispatch index) are therefore
# RULED OUT with direct memory evidence, not just re-confirmed anomalous
# -- ch11's real blocker is still unknown and is likely one level further
# up than this tool can currently observe (e.g. the per-unit turn-state
# machine at 0x117e7 may simply never reach the branch that calls the
# 0x51b19 table at all for this chapter's specific turn state -- see
# doc25 §3.2 for the full writeup and the suggested next step, a live
# breakpoint at native 0x1C05BE with a known-working chapter as a
# control).
KNOWN_MIN_TURNS_BEFORE_KILL: dict[int, int] = {19: 6, 3: 3, 4: 4, 7: 3, 15: 9, 20: 4}

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
                       confirm_retries: int = 4, dialogue_steps: int = 120) -> dict | None:
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

    2026-08-27 "endturngen" round -- dialogue_steps raised again, 60->120:
    fixing screen_shows_battle_hud()'s flashback-dialogue false positive
    (see BATTLE_HUD_RIGHT_STRIP_REGION's module comment) removed an
    unintended early exit that this function had been relying on without
    anyone realizing it -- a dialogue frame with a large character portrait
    was being misread as "real battle HUD visible", which combined with the
    battle array often already holding >=2 records well before real player
    control (documented above) let earlier rounds' ch27/ch02 runs report
    "battle confirmed" after as few as 10-34 taps even though the player
    did not actually have a movable cursor yet. With that false positive
    closed, two independent live re-runs of ch27 this round both
    genuinely exhausted the old 60-tap budget while still deep in ordinary
    pre-battle dialogue (one of them visibly the same "回憶錄戰鬥"-style
    extended flashback/side-dialogue doc58 續四十六 already flagged as a
    real, separate hazard of advancing dialogue too eagerly) -- i.e. 60 was
    only ever "enough" because of the bug, not because it was a correct
    estimate of real dialogue length. doc58's own live rounds recorded
    needing up to ~80-105 Return taps in some sessions even under manual,
    careful play; 120 gives comfortable headroom above that documented
    range now that the count has to be earned honestly.

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

            # 2026-08-27 "ch19banor" round: some chapters' win-check does not
            # resolve if every enemy is killed too early (see
            # KNOWN_MIN_TURNS_BEFORE_KILL's module comment for the live
            # derivation on ch19). If this chapter has an override, pass that
            # many real turns FIRST -- no kill, no stat hacks, just the plain
            # End-Turn->YES shortcut with enemy_addrs=None -- before the
            # normal mass-kill sequence below runs at all. Re-scan for enemies
            # afterward since the array can grow (reinforcement waves) during
            # the wait.
            #
            # ch20-specific note ("ch2killgen" round): the walkthrough gives
            # ch20's victory condition as "沼澤怪物之外的敵人全滅" (all
            # enemies EXCEPT swamp monsters) and a fail condition including
            # "精靈全滅" (all elves die). This tool deliberately does NOT
            # exclude any camp==0 record from mass_kill_enemies() below --
            # the reasoning is that an "except swamp monsters" victory
            # phrasing describes what is NOT REQUIRED to win, not something
            # that is FORBIDDEN to kill; killing every camp==0 record
            # (swamp monsters included) is expected to still satisfy "every
            # non-swamp-monster enemy is dead" and should not itself trip
            # the elf/Sol fail conditions, since mass_kill_enemies() only
            # ever writes to camp==0 records and elves (if they are
            # camp==1 NPC-allies or camp==2 roster members, matching this
            # project's only two live-verified camp values for "not a
            # plain enemy") would never be touched. This is a REASONED
            # PREDICTION carried into the live test below, not a
            # pre-verified fact -- if ch20 comes back with anything other
            # than a clean engine win, check the result log/screenshots for
            # evidence this assumption was wrong (e.g. an elf ally record
            # showing camp==0) before assuming the turn-count-gate
            # hypothesis itself failed.
            min_turns = KNOWN_MIN_TURNS_BEFORE_KILL.get(chapter_n, 0)
            if min_turns:
                log.append(f"chapter {chapter_n} has a KNOWN_MIN_TURNS_BEFORE_KILL override "
                           f"({min_turns} turns) -- passing turns with no mass-kill first")
                for turn_i in range(1, min_turns + 1):
                    wait_etr = confirm_end_turn(name, shots_dir, log, enemy_addrs=None)
                    log.append(f"pre-kill wait turn {turn_i}/{min_turns}: engine_code="
                               f"{wait_etr.get('engine_code')!r} engine_win={wait_etr.get('engine_win')}")
                    if wait_etr.get("engine_win"):
                        log.append("pre-kill wait: engine win fired WITHOUT any kill by this tool -- "
                                   "unexpected, stopping the wait loop early")
                        break
                enter_debugger(name)
                time.sleep(0.4)
                rescan_base = read_battle_array_base(name)
                rescan_enemies = scan_enemy_slots(name, rescan_base, log) if rescan_base is not None else []
                debugger_cmd(name, "RUN")
                time.sleep(0.2)
                if rescan_base is not None:
                    base = rescan_base
                if rescan_enemies:
                    enemy_addrs = rescan_enemies
                log.append(f"post-wait rescan: base={base}, enemy_addrs={len(enemy_addrs)}")

            enter_debugger(name)
            time.sleep(0.5)
            if enemy_addrs:
                mass_kill_enemies(name, enemy_addrs, log)
            debugger_cmd(name, "RUN")
            time.sleep(0.5)
            screenshot(name, shots_dir / "03_pre_end_turn.png")
            engine_win = False
            if enemy_addrs:
                # 2026-08-27 "ch12diag" round follow-up (external strategy-guide
                # cross-check, chiuinan.github.io fd2 walkthrough): several
                # chapters (ch12 confirmed directly -- guide text: "第一回合己方
                # 結束時,敵方第一波援軍出現在右上洞口"/turn-1-end wave, PLUS
                # "獸人隊長陣亡時,敵方第二波援軍立即出現"/a kill-triggered second
                # wave) script reinforcement waves via the SEPARATE FDFIELD
                # turn_events/0x51b91 data-driven event table (doc25 §6.1) --
                # NOT part of the compiled per-chapter win-check handler
                # (0x51b19/0x205be) this tool's mass-kill/engine-win-poll logic
                # already targets. A single mass-kill snapshot taken before the
                # first End Turn cannot see a wave that only spawns AT that
                # end-turn boundary or on a specific unit's death. Retry: if
                # confirm_end_turn() does not confirm an engine-level win,
                # re-scan the live enemy array for any newly-arrived camp==0
                # records (a wave) and, if found, mass-kill and try End Turn
                # again, up to MAX_KILL_CYCLES times. Bounded, not unbounded --
                # a chapter needing more waves than this is expected to come
                # back honestly reported as still-anomaly, not hang the sweep.
                cycle = 0
                end_turn_result = {"engine_win": False, "engine_code": None}
                while cycle < MAX_KILL_CYCLES:
                    cycle += 1
                    end_turn_result = confirm_end_turn(name, shots_dir, log, enemy_addrs=enemy_addrs)
                    engine_win = bool(end_turn_result.get("engine_win"))
                    if engine_win:
                        log.append(f"sweep_chapter: engine win confirmed on kill-cycle {cycle}/{MAX_KILL_CYCLES}")
                        break
                    enter_debugger(name)
                    time.sleep(0.4)
                    rescan_base = read_battle_array_base(name)
                    rescan_enemies_all = scan_enemy_slots(name, rescan_base, log) if rescan_base is not None else []
                    # 2026-08-27 "ch12diag" round follow-up: scan_enemy_slots classifies
                    # by camp byte only (camp==0), NOT death status -- re-scanning after a
                    # mass-kill will always re-find the SAME already-dead records (their
                    # camp byte doesn't change when they die). Only records whose death bit
                    # is STILL 0 are worth another kill+End-Turn cycle; re-"killing" already
                    # -dead records wastes a full retry cycle (~15-20s) without changing
                    # anything, and its log message would misleadingly look like a
                    # reinforcement wave was found when it's really the same corpses.
                    rescan_enemies = []
                    for addr in rescan_enemies_all:
                        b5 = read_mem(name, addr + UNIT_ACTED_OFFSET, min_bytes=1)
                        if b5 is not None and (b5[0] & 1) == 0:
                            rescan_enemies.append(addr)
                    debugger_cmd(name, "RUN")
                    time.sleep(0.2)
                    if not rescan_enemies:
                        log.append(f"sweep_chapter: kill-cycle {cycle}/{MAX_KILL_CYCLES} -- engine win not yet "
                                   f"confirmed (code={end_turn_result.get('engine_code')!r}), re-scan found "
                                   f"{len(rescan_enemies_all)} camp==0 record(s) but ALL already carry the death "
                                   f"signature (no genuinely-alive enemy left to blame) -- stopping the retry "
                                   f"loop honestly; this chapter's win-check is not simply gated on this array's "
                                   f"enemies being dead (see doc25/26's per-chapter handler table for other "
                                   f"possibilities)")
                        break
                    log.append(f"sweep_chapter: kill-cycle {cycle}/{MAX_KILL_CYCLES} -- engine win not yet "
                               f"confirmed (code={end_turn_result.get('engine_code')!r}), re-scan found "
                               f"{len(rescan_enemies)} live enemy record(s) (possible reinforcement wave per "
                               f"doc25 §6.1's turn_events mechanism) -- mass-killing and retrying End Turn")
                    enemy_addrs = rescan_enemies
                    enter_debugger(name)
                    time.sleep(0.3)
                    mass_kill_enemies(name, enemy_addrs, log)
                    debugger_cmd(name, "RUN")
                    time.sleep(0.2)
                # 2026-08-27 "winverify": a genuine win does not autosave
                # immediately -- see advance_postbattle_montage()'s module
                # comment. Best-effort attempt to clear the montage before
                # reading the save back below.
                advance_postbattle_montage(name, shots_dir, log)
                # 2026-08-27 "ch12diag" round: confirm_end_turn() now proves
                # the engine-level win via [0x53ecc]/[0x53c03] directly (see
                # its docstring) -- when that fired, give the on-disk save
                # writer (doc25 §9.1's gated 0x1cff0/0x15311 chain, or
                # whatever path ch24's confirmed 23->24 disk transition used)
                # a much more patient window than the old flat post-montage
                # sleep(1.5) ever gave it, instead of silently giving up. This
                # keeps tapping Return (safe -- established elsewhere in this
                # module) and re-pulls the save periodically, stopping early
                # the moment the disk byte actually advances. This does NOT
                # guarantee a disk write (doc25 §9.1's own multi-round
                # investigation never fully closed out when/whether the write
                # gate opens for a battle-win path outside ch24's specific
                # grind-verified case) -- it just gives it a fair, honestly
                # bounded chance instead of the old ~1.5s.
                if engine_win:
                    log.append("sweep_chapter: engine-level win confirmed -- patiently polling the on-disk "
                               f"save for up to {POST_WIN_DISK_POLL_MAX_S:.0f}s while continuing to tap Return")
                    poll_t0 = time.time()
                    poll_i = 0
                    while time.time() - poll_t0 < POST_WIN_DISK_POLL_MAX_S:
                        send_keys(name, "Return")
                        time.sleep(0.8)
                        poll_i += 1
                        if poll_i % 5 == 0:
                            probe_sav = pull_save(name, chapter_dir / "probe.SAV")
                            probe_ch = read_slot_chapter(probe_sav, slot)
                            if probe_ch is not None and probe_ch > (chapter_n - 1):
                                log.append(f"sweep_chapter: on-disk save advanced to raw {probe_ch:#04x} after "
                                           f"{time.time() - poll_t0:.1f}s of post-win polling ({poll_i} taps)")
                                break
                    else:
                        log.append(f"sweep_chapter: on-disk save still not advanced after "
                                   f"{POST_WIN_DISK_POLL_MAX_S:.0f}s of post-win polling ({poll_i} taps) -- "
                                   f"giving up honestly, not assuming a write will eventually happen")
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
        elif base is not None and enemy_addrs and engine_win:
            verdict = "anomaly_engine_win_no_disk_write"
            detail = ("battle detected, enemies mass-killed, End Turn confirmed, [0x53ecc]/[0x53c03] directly "
                      "confirmed the engine-level win+chapter-advance fired (ground truth, not a screenshot "
                      "guess), but the on-disk FD2.SAV chapter byte still did not advance within this run's "
                      "patient polling window -- see doc25 §9.1's own open question about when the SAV writer "
                      "gate (0x1cff0/0x15311) actually fires for a battle-win path")
        elif base is not None and enemy_addrs:
            verdict = "anomaly"
            detail = "battle detected, enemies mass-killed, End Turn confirmed, but the engine-level win check ([0x53ecc]) never reached code 2 within the poll window, and chapter byte did not advance -- this chapter's win condition may genuinely differ from a plain full-roster kill (e.g. a specific must-survive/must-die unit check on top of the generic scan, per doc25/26's per-chapter handler table)"
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
