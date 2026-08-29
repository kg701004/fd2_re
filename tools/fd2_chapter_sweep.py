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
  ruled out with a clean re-run). ch11 was this round's one cleanly,
  reproducibly negative turn-wait result (25 enemies found, all confirmed
  via a post-kill rescan to persistently carry the death signature, yet
  [0x53ecc] never left 0) -- LATER RESOLVED (see below) once the real
  blocker (a separate cursor/gate② dependency, not a turn-count issue at
  all) was identified. ch02 was deliberately excluded from this round
  pending its own dedicated village-protection check -- ALSO LATER
  RESOLVED, see below.
  2026-08-28 "ch11r8flag"+"ch02final" rounds: both ch11 and ch02's true
  blocker turned out to be the SAME structural gate, not a turn-count issue
  -- `0x117e7`'s Enter/Space dispatch only calls the real per-chapter
  win-check table (`0x51b19[]`) when the cursor sits on a still-alive unit
  (gate②, `FUN_00012c0d()`), but confirm_end_turn()'s own automation
  deliberately parks the cursor on an EMPTY tile before opening the ring --
  so the plain mass-kill+End-Turn recipe alone can structurally never
  satisfy this gate for a chapter whose win-check depends on it, no matter
  how many kill-cycles are retried. `ensure_one_ally_acts()` (defined below)
  is the generalized fix: select any not-yet-acted ally, move it one step,
  confirm Wait, BEFORE any turn-wait/mass-kill. Both ch11 (25 enemies) and
  ch02 (10 enemies) reached a confirmed [0x53ecc]->2 engine win once this
  was combined with their respective KNOWN_MIN_TURNS_BEFORE_KILL waits --
  see KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL and KNOWN_MIN_TURNS_BEFORE_KILL's
  own module comments for the full derivation of each.
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
- 2026-08-29 CORRECTION (see doc99's "map-native guard" and subsequent
  "8 個 DAT_00053a45 WRITE xref" rounds): the "本章XX必須出場" check's actual
  guard character id is NOT reliably doc28's 額外護衛 column -- that column
  matches ch26 (id9 悠妮 + id29 亞奇梅吉, verified byte-for-byte against the
  disassembled push args) but is WRONG for ch21 (doc28 says 羅蘭/id23 +
  希爾法/id24; disassembling FUN_0002af28's actual `PUSH`es before its
  `CALL 0x2b439` proves it checks id21/約拿 instead -- 23/24 are ch21's map-
  template "own"-camp units, a completely different mechanism, see doc99).
  The cursorlive round's "even with the doc28 ids present+selected, still
  rejected" conclusion is now understood to be an artifact of testing the
  wrong id (its padding was [23,24,3,7,14,15], never containing 21) -- a
  fresh append_roster_members()-built roster containing id21, taken through
  the same LOAD -> camp-exit -> prep-select flow via tools/dosbox_harness.sh,
  reached a live battle command-ring screen for ch21 without ever being
  bounced back to camp. append_roster_members() itself needed NO fix -- it
  already targets DAT_00053bf7, the exact persistent-roster global
  FUN_0002af28 temporarily aliases DAT_00053a45 to during roster-select
  (independently corroborated against this module's own SLOT_SIZE/
  SLOT_OFFSET constants inside FUN_00025ebb's disassembly). Disassembly-
  verified guard ids so far (do not use doc28's 額外護衛 column for this
  purpose): ch21(raw20)=[21], ch22(raw21)=[24], ch23(raw22)=[24],
  ch26(raw25)=[9, 29] (both required, in that order). ch24/28/29/30's
  needs_manual_followup status likely has an unrelated cause (no guard
  check is even invoked for them, per FUN_0002af28's chapter dispatch).
  This round did not modify prepare_chapter_save()/estimate_roster_size()
  to special-case these ids -- only ch21 has a live-verified pass; wiring
  the other three chapters' ids in without re-verifying each live risks a
  false-positive `pass` classification. See doc99's "2026-08-29 續輪:8 個
  DAT_00053a45 WRITE xref 逐一查明" section for the full disassembly +
  live-verification writeup.

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


def ensure_battle_hud(name: str, shots_dir: Path, log: list[str], tag: str, max_clears: int = 40) -> tuple[bool, int]:
    """Screenshot; if screen_shows_battle_hud() is False, send Return +
    screenshot repeatedly (up to max_clears) until it is True (or budget
    exhausted). Returns (ok, n_clears_used).

    2026-08-28 "ch11chest" round (doc25 §3.2.4): promoted here from a
    per-script local helper first written that round. This map (and
    possibly others) keeps firing full-screen story dialogue even AFTER
    attempt_camp_exit() has already declared "battle found" (its own
    HUD-detection only needs the HUD box to have appeared ONCE + >=2 enemy
    records, it does not guarantee no further dialogue afterward) -- blind
    Escape/arrow-key presses sent while such a dialogue box is still up get
    consumed as "advance dialogue text", not "move the map cursor",
    producing erratic/oversized cursor-position reads that look like a
    cursor-tracking bug but are actually a dialogue-vs-cursor-input
    confusion. The fix is to treat screen_shows_battle_hud() as a gate
    before EVERY cursor-trusting read or cursor-moving keypress, not just
    once at the start of a movement sequence -- the same discipline
    attempt_camp_exit() already applies to its own opening sequence,
    applied continuously.
    """
    shot = shots_dir / f"hudcheck_{tag}.png"
    screenshot(name, shot)
    if screen_shows_battle_hud(shot):
        return True, 0
    log.append(f"[{tag}] no battle HUD visible -- clearing dialogue")
    for i in range(max_clears):
        send_keys(name, "Return")
        time.sleep(0.9)
        shot_i = shots_dir / f"hudcheck_{tag}_clear{i}.png"
        screenshot(name, shot_i)
        if screen_shows_battle_hud(shot_i):
            log.append(f"[{tag}] battle HUD recovered after {i + 1} clear-Return(s)")
            return True, i + 1
    log.append(f"[{tag}] battle HUD NOT recovered after {max_clears} clear-Returns")
    return False, max_clears


def _read_cursor_xy(name: str) -> tuple[int | None, int | None]:
    enter_debugger(name)
    time.sleep(0.35)
    raw = read_mem(name, 0x53ab1 + NATIVE_LIVE_DELTA, min_bytes=1)
    cx = raw[0] if raw else None
    raw = read_mem(name, 0x53ab5 + NATIVE_LIVE_DELTA, min_bytes=1)
    cy = raw[0] if raw else None
    debugger_cmd(name, "RUN")
    time.sleep(0.2)
    return cx, cy


def ensure_one_ally_acts(name: str, shots_dir: Path, log: list[str]) -> bool:
    """Select the first cycle-reachable, not-yet-acted ally, move it ONE
    step to any adjacent tile the game accepts, and confirm "Wait" there.

    2026-08-28 "ch11r8flag" round (doc25 §3.2.5, doc99's matching entry):
    this is the generalized, chest-agnostic fix for the pattern round 7
    ("ch11chest") first found and round 8 then re-attributed correctly.
    `0x117e7`'s Enter/Space key-dispatch branch only calls the actual
    per-chapter win-check table (`0x51b19[chapter_index]`) when
    FUN_00012c0d() finds a still-alive unit sitting exactly under the
    cursor -- but confirm_end_turn()'s own End-Turn sequence deliberately
    parks the cursor on an EMPTY tile (find_empty_adjacent_tile()) before
    opening the system ring, specifically so it does NOT interact with any
    unit. That means the standard mass-kill+End-Turn recipe alone, no
    matter how many times it is retried, can structurally never satisfy
    that gate for a chapter whose win-check happens to depend on it having
    been satisfied at least once. Round 7 stumbled into satisfying it as a
    side effect of a real chest-open (select ally -> move onto the chest
    tile -> confirm); round 8's `move_only_test.py` proved live that the
    CHEST was never the active ingredient -- moving the SAME ally to an
    ordinary adjacent non-chest tile and confirming "Wait" there ALSO
    produced an engine-level win ([0x53ecc] -> 2), with the chest-opened
    flag block ([0x53AD5]) provably untouched throughout. This function
    packages that minimal, chest-free recipe: it does not attempt to reach
    any specific tile, just ANY adjacent tile the game accepts, because the
    live evidence is that "a unit was validly selected and acted on" is the
    load-bearing event, not the destination.

    Must be called with the battle HUD already confirmed visible (e.g.
    right after the caller's own settle loop) -- this function HUD-gates
    every step via ensure_battle_hud() but does not establish the initial
    battle state itself. Returns True if a unit was successfully selected,
    moved, and had its "Wait" confirmed; False (logged, non-fatal to the
    caller) if any step could not be completed within its budget -- callers
    should treat False as "this chapter still gets the plain mass-kill/
    End-Turn attempt, just without this extra step", not as a hard failure.
    """
    ok, _ = ensure_battle_hud(name, shots_dir, log, "allyact_pre", max_clears=60)
    if not ok:
        log.append("ensure_one_ally_acts: battle HUD never recovered, aborting")
        return False

    # Cycle (Esc/Z/Numpad5 round-robin, doc25 §3.2.3) to the first
    # not-yet-acted live ally and select it.
    settled = False
    for i in range(15):
        send_keys(name, "Escape")
        time.sleep(0.8)
        ok, _ = ensure_battle_hud(name, shots_dir, log, f"allyact_cycle{i}", max_clears=20)
        if not ok:
            continue
        cx, cy = _read_cursor_xy(name)
        log.append(f"ensure_one_ally_acts: cycle[{i}] cursor=({cx},{cy})")
        if cx is not None:
            settled = True
            break
    if not settled:
        log.append("ensure_one_ally_acts: could not settle on any ally via Escape-cycle")
        return False

    send_keys(name, "Return")  # select the unit
    time.sleep(1.0)
    ok, _ = ensure_battle_hud(name, shots_dir, log, "allyact_selected", max_clears=20)
    start_xy = _read_cursor_xy(name)

    landed = False
    for key in ("Up", "Left", "Right", "Down"):
        send_keys(name, key)
        time.sleep(0.8)
        ok, _ = ensure_battle_hud(name, shots_dir, log, f"allyact_move_{key}", max_clears=20)
        new_xy = _read_cursor_xy(name) if ok else start_xy
        moved = new_xy != start_xy and new_xy[0] is not None
        log.append(f"ensure_one_ally_acts: tried {key}: {start_xy} -> {new_xy} moved={moved}")
        if moved:
            landed = True
            break
    if not landed:
        log.append("ensure_one_ally_acts: unit did not move in any of 4 directions, giving up")
        return False

    send_keys(name, "Return")  # confirm the move onto the new tile
    time.sleep(1.5)
    screenshot(name, shots_dir / "allyact_after_move_confirm.png")
    send_keys(name, "Down")  # select "Wait" in the ring (doc58's proven mapping)
    time.sleep(1.0)
    send_keys(name, "Return")  # confirm Wait
    time.sleep(1.5)
    screenshot(name, shots_dir / "allyact_after_wait_confirm.png")
    ok, _ = ensure_battle_hud(name, shots_dir, log, "allyact_final", max_clears=30)
    log.append(f"ensure_one_ally_acts: completed select->move->Wait, final HUD ok={ok}")
    return True


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


# --- Roster deploy-selection ("剩餘人數") pick-grid helpers ---
# (2026-08-29 "picklock" round, see docs/knowledge-base/99-chapter-sweep-
# results.md matching entry). WHY THIS EXISTS: attempt_camp_exit()'s
# dialogue_steps budget (raised 120->220->420->480 across two prior rounds
# for ch23/ch28, see CAMP_EXIT_DIALOGUE_STEPS's module comment) never
# converged no matter how large, because the underlying assumption --
# "budget is being spent on pre-battle STORY dialogue" -- was wrong for
# these two chapters. Live pixel-forensics on an already-completed 420-tap
# ch23 run (.wsl_build/round0829b/ch23/shots/campexit_*.png) proved the
# roster pick/deploy grid ("出戰人數 X15 / 剩餘人數 XNN" + a portrait grid,
# same panel screen_shows_battle_hud()'s docstring already independently
# flagged as sharing the HUD box's (56,85,154) theme blue) is reached
# IMMEDIATELY -- as early as the very FIRST post-exit-confirm tap, not after
# any dialogue at all -- and Enter both TOGGLES the highlighted candidate's
# picked state AND advances the cursor (doc58 續九/續十一's disasm:
# `XOR byte[cursor],1` at 0x2b0cf, cursor-advance reuses the same code path
# as a bare Right keypress). Blindly spamming Return past the point where
# every candidate is picked does NOT stop or auto-confirm -- it keeps
# toggling, so the cursor wraps around and starts UN-picking already-picked
# candidates. Pixel-sampling the portrait grid across the whole 420-tap run
# showed remaining-count oscillating (colored/picked count seen as low as
# 13/14 and as high as 0/14 at different taps, never stably resting at
# "all picked") for the ENTIRE budget -- i.e. this was a pure random walk,
# and no fixed tap count (however large) converges it by construction. The
# fix is not "more taps", it's WATCHING the grid after every single tap and
# stopping the instant every candidate is picked.
ROSTER_PICK_GRID_XS = [262, 318, 374, 430, 486, 542, 598, 654, 710, 766]
ROSTER_PICK_GRID_ROW_YS = [425, 491]  # row1 (up to 10 candidates), row2 (remainder)
ROSTER_PICK_PANEL_PROBE_PX = [(220, 230), (220, 300)]  # inside the "出戰人數"/
# "剩餘人數" boxes -- both read the exact same (56, 85, 154) fill color
# whenever this panel is on screen (live-sampled, .wsl_build/round0829b/
# ch23/shots/campexit_003_exit_confirm_attempt1.png and 15+ other frames
# across the same run, zero false negatives/positives observed against the
# title/camp-map/plain-story-dialogue frames from the same run).
ROSTER_PICK_PANEL_COLOR = (56, 85, 154)
ROSTER_PICK_PANEL_COLOR_TOLERANCE = 10
ROSTER_PICK_PORTRAIT_VARIANCE_THRESHOLD = 15  # avg per-pixel (max-min) channel
# spread within a small patch centered on a grid slot -- live-calibrated
# against campexit_356_dialogue351.png (known ground truth: 1 gray/unpicked
# slot read 0.0, all 13 picked slots read 31.0-83.2, see doc99 for the full
# per-slot dump), kept well clear of both clusters.


def screen_shows_roster_pick_grid(png_path: Path) -> bool:
    """True if the screenshot shows the deploy roster pick/toggle panel
    ("出戰人數"/"剩餘人數" counters + a portrait grid below). See the
    module comment above ROSTER_PICK_GRID_XS for how this was derived and
    why it matters. Checks both probe pixels so a single stray theme-blue
    pixel elsewhere on screen can't false-positive."""
    try:
        from PIL import Image
    except ImportError:
        return False
    im = Image.open(png_path).convert("RGB")
    for (x, y) in ROSTER_PICK_PANEL_PROBE_PX:
        r, g, b = im.getpixel((x, y))
        tr, tg, tb = ROSTER_PICK_PANEL_COLOR
        if not (abs(r - tr) <= ROSTER_PICK_PANEL_COLOR_TOLERANCE
                and abs(g - tg) <= ROSTER_PICK_PANEL_COLOR_TOLERANCE
                and abs(b - tb) <= ROSTER_PICK_PANEL_COLOR_TOLERANCE):
            return False
    return True


def count_picked_candidates(png_path: Path, n_candidates: int) -> int:
    """Count how many of the first n_candidates portrait-grid slots
    (row-major, ROSTER_PICK_GRID_XS x ROSTER_PICK_GRID_ROW_YS, up to 10 per
    row) currently show a picked (full-color) portrait rather than an
    unpicked (flat gray silhouette) one, via average per-pixel channel
    spread in a small patch centered on each slot -- see
    ROSTER_PICK_PORTRAIT_VARIANCE_THRESHOLD's module comment for
    calibration. n_candidates should be guard_selection_threshold(chapter_n)
    - 1 (the fixed leader, record0, is never shown as a toggleable grid
    slot -- live-confirmed: ch23's cap=15 threshold pairs with exactly 14
    grid slots, 10+4)."""
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    picked = 0
    remaining = n_candidates
    for row_y in ROSTER_PICK_GRID_ROW_YS:
        n_this_row = min(10, remaining)
        if n_this_row <= 0:
            break
        for i in range(n_this_row):
            x = ROSTER_PICK_GRID_XS[i]
            patch = []
            for dx in range(-6, 7, 3):
                for dy in range(-6, 7, 3):
                    patch.append(im.getpixel((x + dx, row_y + dy)))
            avg_spread = sum((max(p) - min(p)) for p in patch) / len(patch)
            if avg_spread > ROSTER_PICK_PORTRAIT_VARIANCE_THRESHOLD:
                picked += 1
        remaining -= n_this_row
    return picked


def adaptive_pick_roster(name: str, shots_dir: Path, log: list[str], n_candidates: int,
                          max_taps: int | None = None) -> bool:
    """Tap Return one at a time, checking the pick-grid after EVERY tap, and
    STOP the instant all n_candidates slots read picked -- see the module
    comment above ROSTER_PICK_GRID_XS for why a blind fixed-budget loop
    (the old approach) can never converge here (Enter both picks AND
    advances the cursor with no stop condition, so overshoot un-picks
    already-picked slots and the count randomly walks forever). Returns
    True if every slot got picked within budget, False otherwise (caller
    should treat False honestly -- do not assume the roster is complete).

    max_taps defaults to n_candidates * 3 + 10: generous enough to absorb
    a few wasted taps if the cursor's starting position isn't slot 0 (not
    yet observed live, but cheap insurance), while still being a small
    fraction of the old 420-480 fixed budgets this replaces for the
    chapters that actually have this pick screen."""
    if max_taps is None:
        max_taps = n_candidates * 3 + 10
    for tap in range(max_taps):
        shot = screenshot(name, shots_dir / f"pick_{tap:03d}.png")
        picked = count_picked_candidates(shot, n_candidates)
        if picked >= n_candidates:
            log.append(f"adaptive_pick_roster: all {n_candidates} candidate(s) picked after {tap} tap(s)")
            return True
        send_keys(name, "Return")
        time.sleep(0.5)
    final_shot = screenshot(name, shots_dir / f"pick_{max_taps:03d}_final.png")
    final_picked = count_picked_candidates(final_shot, n_candidates)
    log.append(f"adaptive_pick_roster: gave up after {max_taps} taps, only {final_picked}/{n_candidates} picked "
               f"(oscillating toggle -- see this function's docstring)")
    return False


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
#
# ch01 is NOT in this dict, and should not be given a naive hint -- 2026-08-28
# "ch01final" round (docs/knowledge-base/99-chapter-sweep-results.md, same
# date heading) found this chapter's post-LOAD screen is not a dialogue/
# navigation problem this dict's mechanism (a key sequence) can fix. LOADing
# any save with slot0's raw chapter byte patched to 0 produces a solid-black
# screen that is provably NOT frozen (the emulator's EIP keeps moving inside
# a ~0x58-byte loop at 0x1EA9E3-0x1EAA4A across repeated debugger
# pause/resume samples) but also provably never changes a single pixel
# across 60s of untouched passive waiting AND 15 extra Return taps -- ruling
# out both "just needs more patience" and "just needs more/different
# keypresses". A live A/B test (13-member roster vs. a manually truncated
# 1-member roster, otherwise identical save) produced byte-identical
# behavior, which also rules out the older 2026-08-27 "late-game roster
# patched onto ch01" caveat as the (sole) cause. Current best-supported,
# UNVERIFIED hypothesis: docs/knowledge-base/46-ch1-opening-timeline.md's
# ~6-minute native New-Game opening (throne room -> meadow -> forest -> march
# montage -> island) is chapter-index-driven via cutscene handler 0x3231b
# (see doc91's "新遊戲→開場對話→自動進戰場" entry) and LOAD-into-chapter-0
# may try to re-enter that same dispatch WITHOUT the New-Game-only setup
# (e.g. actor waypoint/camera-path tables) it expects, leaving it spinning in
# a wait it can never satisfy. If true, ch01 is the one chapter where the
# chapter-jump-via-fd2save approach this whole tool is built on does not
# apply structurally (consistent with doc91's "no player can ever save with
# chapter byte 0 -- saving only exists once the ch02 camp-map/tavern is
# reached" observation: a raw_chapter=0 save is not just roster-mismatched,
# it has no legitimate native origin at all). NOT confirmed -- see doc99's
# "ch01final" round for the full writeup and next-round suggestions
# (disassemble the loop's caller, or try a real New-Game boot as a control).
# KNOWN_MIN_TURNS_BEFORE_KILL[1]=6 and adding 1 to
# KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL are plausible follow-up values (ch01 is
# a "D=default" 0x205be chapter like ch02/03/04/07/11/15/19/20, and the
# walkthrough describes 4 reinforcement waves through turn 6) but are NOT
# added below -- they are unverified guesses this round never got to test,
# since battle was never even reached.
# 2026-08-29 guard-chapter sweep round: ch22 (and, by the identical
# symptom, ch25) do NOT land on the ordinary camp-map town hub after LOAD
# -- attempt_camp_exit()'s opening "Right x3" cycle followed by its
# exit_confirm Return produced ZERO visible screen change across all 4
# retries for both chapters (see docs/knowledge-base/99-chapter-sweep-
# results.md's matching entry), then generic key cycling (which mixes in
# Down/Right/Escape) stalled or, in one ch22 run, ended up bounced all the
# way back to the TITLE SCREEN. A standalone diagnostic driver
# (.wsl_build/ch22diag.py, throwaway/not committed) that sent PLAIN Return
# only -- no Right, no Escape, no debugger polling in between -- instead
# made real progress (reached a character equipment/status screen by tap
# 40, no title bounce). This suggests ch22/25's post-load screen reacts
# badly specifically to "Right" (plausibly bound to some kind of "skip"
# action that jumps somewhere unintended when LOADed via a chapter-jump
# patch rather than reached through normal play), not that there is no
# navigable sequence at all. NOT yet proven to reach a real battle -- the
# diagnostic only ran 40 taps and stopped at a non-battle screen; this
# hint is a follow-up bet on "more plain Return", not a confirmed fix.
# 2026-08-29 "picklock" round: the ["Return"]*300 hint above (removed this
# round) was an UNVERIFIED bet from the guard-sweep round, based on a
# one-off .wsl_build/ch22diag.py throwaway script that sent plain Return
# only and "made real progress" for ~40 taps -- it was never actually
# confirmed to reach a real battle, and this round's full sweep run
# (instance rb2222) proved it does NOT: 300 plain Returns from the post-load
# camp map walk the player INTO the tavern's character/equipment browser
# (see .wsl_build/round0829b/ch22/shots/advance_050.png,
# advance_100.png -- a roster list, then individual character stat/spell
# pages), never anywhere near the exit. A careful, slowly-paced (1.2s/key)
# re-test of the ORIGINAL doc91 Right-cycle sequence this hint had replaced
# (instance diag22, .wsl_build/round0829b/diag22_shots/02_right_0{1,2,3}.png)
# found it working perfectly and exactly as documented: Right x1 ->教會,
# x2->道具店, x3->出口 (character sprite visibly walks to the gate). This
# directly contradicts the guard-sweep round's claim that "Right x3
# produced ZERO visible change / one run bounced to title" -- that symptom
# was not reproduced here and its cause remains unexplained (possibly a
# stale/leftover instance state or a race in that round's test, not a
# structural property of ch22/25's camp map). Do not re-add a hint here
# without a fresh live counter-example; the standard attempt_camp_exit()
# path (used when this dict has no entry for a chapter) is what ch22/25
# should go through now.
KNOWN_NAVIGATE_HINTS: dict[int, list[str]] = {}

# 2026-08-29 guard-chapter sweep round: attempt_camp_exit()'s default
# dialogue_steps=120 was tuned against ch02/ch12/ch27's observed pre-battle
# dialogue length (doc58's up to ~80-105 taps). A first live run of ch21
# (instance guard21_21, this round) exhausted the full 120-tap budget
# still mid-dialogue (see docs/knowledge-base/99-chapter-sweep-results.md's
# matching entry for screenshots) -- ch21's own pre-battle sequence is
# longer, consistent with the "jonah21" round's own description of "a much
# longer than expected pre-battle cutscene interleaving two scenes". Only
# add a chapter here after it has actually been observed exhausting the
# default budget short of battle -- do not pre-emptively pad every chapter.
# ch23/ch28 added same round: both showed the identical "exit_confirm and
# yes_confirm both register cleanly, but 120 taps runs out still mid pre-
# battle dialogue/selection" symptom as ch21's first attempt (as opposed to
# ch22/ch25's DIFFERENT "exit_confirm never registers at all" symptom,
# which this budget bump does not address -- see this round's
# docs/knowledge-base/99-chapter-sweep-results.md entry). ch28's roster is
# also padded to 19 (guard_selection_threshold's raw>0x1a branch) instead
# of 15, so its picking phase alone plausibly needs more taps than the
# other chapters here.
# Live-observed follow-up (same round): 220 got ch23/ch28 all the way to
# the troop-selection screen (confirmed via screenshot -- "出戰人數
# X15/剩餘人數 X12" for ch23, "X19/X14" for ch28) but ran out of budget
# mid-picking (each Return both picks one candidate and advances the
# cursor, one pick per tap -- doc91/attempt_camp_exit's docstring). ch23
# needs ~218 dialogue taps + 15 picks; ch28's larger 19-person roster
# (guard_selection_threshold's raw>0x1a branch) needs even more. Raised
# with generous margin for the remaining picks plus any post-pick popup/
# dialogue this round did not get to see.
# Second live follow-up (same round): 260 got ch23 to "剩餘人數 X06" (only
# 6 of 15 left to pick) but the pick rate had visibly slowed to ~6-7 taps
# per pick near the end of the list (vs. ~1 tap/pick early on -- screenshot
# comparison at tap 221 (12 remaining) vs tap 261 (6 remaining), 40 taps
# for 6 picks) instead of the 1:1 rate doc91/ch27 established -- possibly a
# scroll/second-row navigation cost this tool has not previously had to
# pay with a 13-person unpadded roster. NOT diagnosed further this round;
# raised with a large margin as a blunt mitigation, not a fix -- a future
# round should look at the actual mid-picking screenshots
# (.wsl_build/guardsweep9/ch23/shots/campexit_2*.png) to understand the
# slowdown properly instead of just paying for more taps.
CAMP_EXIT_DIALOGUE_STEPS: dict[int, int] = {21: 220, 23: 420, 28: 480}

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
# 2026-08-28 "ch11bp" round (doc25 §3.2.1, doc99's matching section): NOTE
# the address above (0x1C05BE) is a TYPO carried over from an earlier
# round -- 0x205be + NATIVE_LIVE_DELTA actually equals 0x1BC5BE (verified
# both by hand and by cross-checking the same delta formula against the
# already-confirmed 0x53c03+NATIVE_LIVE_DELTA=0x1EFC03 live read). Using
# the corrected address, a bare BPM breakpoint there turned out to be an
# unreliable/self-triggering channel (fired identically for ch03 and
# ch11), but a from-before-the-ring LOGC full-instruction execution trace
# gave the first direct (non-polling) ground truth: native 0x205be
# executes exactly once for ch03 (control) and ZERO times for ch11 across
# an equivalent ~42M-instruction window covering the whole End-Turn->YES
# sequence -- i.e. the dispatch genuinely is never reached for ch11, not
# just "reached but overwritten". Decompiling the actual caller (0x117e7)
# found the call is nested inside THREE conditions (phase==0x39||0x1c,
# then FUN_00012c0d()!=-1 -- "is there a still-alive unit at the CURSOR's
# current [0x53ab1]/[0x53ab5] grid position", then a per-unit unit[+7]/
# unit[+0x1f] check) -- which of these three is where ch03/ch11 diverge is
# still unverified. A coordinator-proposed "does ch11 need the map's
# Star's Eye (星之眼) chest opened too, not just all enemies dead" side
# hypothesis was also tested directly this round (SMV-writing all 12 of
# map10's known chest-opened flags at the [0x53AD5]-pointed heap block,
# verified via readback and confirmed to survive the full turn-wait) and
# came back negative -- still stuck at [0x53ecc]==0 either way. See doc25
# §3.2.1 for the full writeup; no code fix was found this round, so
# KNOWN_MIN_TURNS_BEFORE_KILL below is unchanged (ch11 deliberately has no
# entry -- turn-wait alone was never the fix for this chapter).
#
# 2026-08-28 "ch11chest" round (doc25 §3.2.4, doc99's matching entry) SOLVED
# ch11 and PARTIALLY RETRACTS the "Star's Eye" negative result directly
# above: that test wrote 0x01 into all 12 known map10 chest-opened flags at
# the [0x53AD5]-pointed heap block -- a *memory write*, not a real UI
# interaction (same class of shortcut this project already knew can miss
# event-chain side effects a real action triggers, per doc58's ch27
# captain-hunt precedent). Redone via REAL movement (select ally -> move
# onto a chest tile -> confirm -> ring opens -> "Wait" -> "found a chest,
# open it?" YES/NO dialogue -> YES -> "opened the chest, found 5000 gold!",
# all screenshot-verified) on map10 chest slot 10 ((16,15), hidden=true --
# NOT the Star's Eye slot0 the earlier round focused on): the SAME
# [0x53AD5] flag block still read all-zero afterward (round4's write target
# was likely inert/wrong, not "set correctly but ignored"), but
# [0x53ecc] flipped to 2 (WIN) 3.9s into the very next mass-kill+End-Turn
# kill-cycle -- the first engine-level win this project has ever gotten for
# ch11 across 7 rounds of dedicated diagnosis. Only ONE chest was opened
# (not all 12), so the precise minimum requirement (any one chest? a
# specific one? more than one?) is NOT yet nailed down, and no matched
# "don't open a chest" control was rerun in the same session -- this is
# strong (0/7+ prior identical attempts failed) but not airtight (N=1)
# causal evidence. No generalized "walk to a chest" helper is added here
# yet: the live movement sequence needed a real-time screenshot-gated
# dialogue-clear loop at EVERY step (this map keeps firing story dialogue
# even after attempt_camp_exit() already declared "battle found", which
# silently ate blind arrow-key/Escape presses in 4 independent earlier
# attempts this same round -- see doc25 §3.2.4 for the full trap writeup)
# that is not yet packaged as a reusable function; treat any future
# chest-walking code as needing the same HUD-gate discipline
# attempt_camp_exit() itself already uses, not just a one-off tap budget.
# ch11 itself does NOT need a KNOWN_MIN_TURNS_BEFORE_KILL entry to reach
# this win -- the existing default (no wait) plus a real chest-open was
# sufficient; the 3-turn wait used this round matched the recipe already
# established for the other "stuck at 0" chapters out of consistency, not
# because it was proven necessary for ch11 specifically.
# 2026-08-28 "ch11r8flag" round: ch11 (11: 3) added here alongside
# KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL below. A live smoke-test of
# sweep_chapter() found ensure_one_ally_acts() ALONE (with no turn-wait
# before mass-kill, since ch11 was not yet in this dict) still left ch11
# stuck ("anomaly", [0x53ecc] never left 0) -- even though the standalone
# move_only_test.py script that first validated the ally-action fix always
# ran a 3-turn wait AFTER the ally-action and BEFORE mass-kill (inherited,
# unexamined, from every earlier ch11 round's recipe). ch11 apparently
# needs BOTH steps, in the order [ally-action] -> [3-turn wait] ->
# [mass-kill + End-Turn], not the ally-action alone; sweep_chapter() now
# runs ensure_one_ally_acts() before this dict's wait loop for exactly that
# reason. The turn count (3) is carried over unexamined from the earlier
# rounds' convention, same honest caveat as the other entries below -- it
# was never isolated to confirm 3 is the true minimum vs. simply "enough".
#
# 2026-08-28 "ch02final" round (doc99's matching entry) CONFIRMED: ch02
# (2: 3), combined with KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL below, is
# LIVE-VERIFIED via a full end-to-end `sweep_chapter()` run (not a one-off
# script) -- [0x53ecc] flipped to 2 (WIN) 2.0s into the very FIRST
# mass-kill+End-Turn kill-cycle, 871.4s total, verdict
# `anomaly_engine_win_no_disk_write` (same class as all other confirmed
# chapters). ch02's "diag2" round (2026-08-27) had already found the
# identical symptom ch11 had (all camp==0 enemy records mass-killed with a
# persistent death signature, camp==1 records at idx5-10 -- the villagers
# per the walkthrough's fail condition -- confirmed never touched, yet
# [0x53ecc] stayed 0), and doc25 §5's disassembly of ch02's own special
# postbattle handler (`0x206c5`, table_idx1) independently corroborates this:
# it calls the shared `0x205be` base rule FIRST, then only OVERWRITES
# [0x53ecc] to code1 if ALL of units 5-10 are dead (never blocks a code2 win
# while any villager survives) -- i.e. ch02 depends on the exact same
# gate②-gated `0x205be` dispatch ch11 needed, just wrapped in one extra
# villager-survival check that is a no-op when the villagers are alive
# (which mass_kill_enemies() never touches, confirmed both in "diag2" and
# this round's own log). ch02 was deliberately EXCLUDED from the earlier
# "ch2killgen" turn-wait generalization round pending its own dedicated
# check; the walkthrough's ch02 reinforcement wave (6 bandit reinforcements
# arrive from above at Turn 3 completion) independently motivated the same
# turn count ch11 used, though this round's post-wait rescan still found
# only the original 10 enemies (no observed array growth, same pattern
# ch03/04/07/15/20 showed -- the reinforcements were most likely already
# present in the initial array, not a live spawn this tool's rescan would
# catch). Full log: `.wsl_build/chapter_sweep/ch02/result.json`.
# 2026-08-29 guard-chapter sweep round: ch21 tried ensure_one_ally_acts()
# alone first (KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL) -- ally-action itself
# completed cleanly (HUD ok=True) but [0x53ecc] still stayed at 0. The
# external strategy guide (chiuinan.github.io) gives ch21 four corner-demon
# reinforcement waves at turns 2/4/6/8 and a "second wave" starting turn 3;
# this tool's initial mass-kill happens on turn 1 (immediately after
# battle is confirmed), well before any of those waves exist in the array,
# so a single kill-cycle can never touch them. 9 (one past the last known
# wave at turn 8) mirrors ch15's existing precedent value for the same
# "wait past the last known wave, then kill everything at once" pattern.
# NOT YET live-confirmed for ch21 specifically (added together with this
# round's ensure_one_ally_acts() entry, on the same "try the established
# precedent, then verify" basis) -- see this dict's other per-chapter
# comments above for the general derivation method.
# 2026-08-29 "picklock" round: ch22's own live sweep (instance pl2222, this
# round -- see doc99) reached real battle cleanly (the navigate-hint fix
# above), mass-killed all 51 scanned enemies, and ran confirm_end_turn(),
# but [0x53ecc] never left 0 -- an "anomaly" verdict, the same pattern
# ch19/ch21 showed before their KNOWN_MIN_TURNS_BEFORE_KILL entries were
# added. WebFetch of the external walkthrough (chiuinan.github.io) gives
# ch22 two demon reinforcement waves, turn 3 and turn 7 (plus an ally,
# 莎拉/Shara, joining turn 5) -- mirroring ch21's own turn-2/4/6/8 wave
# pattern that KNOWN_MIN_TURNS_BEFORE_KILL[21]=9 (one past the last known
# wave) was based on. 8 = one past ch22's last known wave (turn 7). NOT YET
# live-confirmed -- added on the same "try the established precedent, then
# verify" basis as ch21's entry, not yet re-run against the new value.
KNOWN_MIN_TURNS_BEFORE_KILL: dict[int, int] = {19: 6, 3: 3, 4: 4, 7: 3, 15: 9, 20: 4, 11: 3, 2: 3, 21: 9, 22: 8}

# 2026-08-28 "ch11r8ctrl"+"ch11r8flag" round (doc25 §3.2.5, doc99's matching
# entry) FINAL WORD on ch11 (superseding the "ch11chest" note above): a
# strict same-recipe "don't open any chest" control run reproduced round
# 1-7's 0/N failure rate cleanly ([0x53ecc] stayed 0 after all 25 enemies
# were mass-killed), confirming round 7's win was NOT just "better
# automation". But a follow-up live test (move_only_test.py) then proved
# round 7's own causal attribution ("opening a chest is what did it") was
# ITSELF wrong: repeating round 7's exact select->move->confirm-Wait UI
# chain but redirecting the move to an ORDINARY ADJACENT NON-CHEST tile
# (confirmed via the [0x53AD5] flag block staying all-zero throughout) ALSO
# produced an engine-level win. The real necessary condition, per doc25
# §3.2.1's already-disassembled 0x117e7 gate structure, is almost certainly
# that FUN_00012c0d() (gate②: cursor position == some still-alive unit's
# position) must succeed at least once before the 0x51b19 win-check table
# can ever be dispatched -- and confirm_end_turn()'s own End-Turn sequence
# deliberately parks the cursor on an EMPTY tile before opening the ring,
# so the plain mass-kill+End-Turn recipe alone can structurally never
# satisfy this gate no matter how many retries. ensure_one_ally_acts()
# (defined above, near confirm_end_turn()) packages the minimal fix: select
# any not-yet-acted ally, move it one step to ANY adjacent tile, confirm
# Wait -- no chest-specific logic needed. ch11 is the first chapter this was
# live-verified necessary for; do not pre-emptively add chapters here
# without their own live confirmation, per this project's culture of not
# overclaiming a fix beyond what was actually tested.
#
# 2026-08-28 "ch02final" round: ch02 added as the SECOND chapter live-
# verified to need this -- see KNOWN_MIN_TURNS_BEFORE_KILL's matching
# comment above for the full derivation and end-to-end confirmation
# (871.4s run, [0x53ecc] -> 2 on kill-cycle 1/4, `ensure_one_ally_acts()`
# itself needed zero retries -- cycle[0] immediately landed on a live ally,
# a single `Up` tap moved it, select->move->Wait completed cleanly).
# 2026-08-29 guard-chapter sweep round: ch21 (instance g21b_21, dialogue
# budget bumped to 220 via CAMP_EXIT_DIALOGUE_STEPS to actually reach
# battle -- see that dict's comment) reproduced the EXACT ch02/ch11
# symptom signature: real battle confirmed (50 enemy records), all 50
# mass-killed and confirmed via read-back, End-Turn's Yes/No prompt
# confirmed, yet [0x53ecc] stayed at 0 through the full retry budget (the
# kill-cycle loop then honestly gave up early because every camp==0 record
# already carried the death signature -- no genuinely-alive enemy left to
# blame). confirm_end_turn()'s find_empty_adjacent_tile() by construction
# parks the cursor on an EMPTY tile before opening the ring, so per gate②'s
# already-disassembled 0x117e7 structure (see the long comment above this
# dict) this chapter's win-check most likely needs the same fix. NOT YET
# live-confirmed to be the actual fix for ch21 (a rerun with this entry
# added was queued but not observed to complete before this round's time
# budget ran out) -- added on the strength of the ch02/ch11 precedent
# rather than a fresh independent confirmation; a future round should
# verify this claim against the actual rerun result before treating ch21
# as understood.
# ch23 added 2026-08-29 "ch23retest" round -- LIVE-CONFIRMED, not a
# precedent-only guess like ch21's original entry above: a mass-kill (24
# enemies) + End Turn with NO prior ally action left [0x53ecc] at 0 for a
# full 15s poll (ground-truth debugger read); calling ensure_one_ally_acts()
# immediately after (same battle, same instance, no re-kill needed since
# every enemy already carried the death signature) flipped [0x53ecc] to 2
# within the same debugger session, and advance_postbattle_montage() +
# patient disk polling then confirmed the on-disk save advanced raw
# 0x16->0x17 (a literal `pass`, not just anomaly_engine_win_no_disk_write).
# See docs/knowledge-base/99-chapter-sweep-results.md's "ch23retest" round.
KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL: set[int] = {11, 2, 21, 23}

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
                       confirm_retries: int = 4, dialogue_steps: int = 120,
                       chapter_n: int | None = None, roster_count: int | None = None) -> dict | None:
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

    # 2026-08-29 "picklock" round: for chapters that show the deploy roster
    # pick/toggle grid (live-confirmed ch23/ch28, see doc99's guard-id-table
    # comment listing which chapters render this screen at all), it appears
    # IMMEDIATELY after exit_confirm -- there is no separate "要進入戰場嗎?"
    # Y/N popup first. The old code's very next step, a blind
    # `_confirm_with_retry("yes_confirm")`, was unknowingly firing the FIRST
    # pick-grid toggle (live-verified: campexit_003_exit_confirm_attempt1.png
    # shows the grid already on screen at 剩餘人數=cap/0 picked;
    # campexit_004_yes_confirm_attempt1.png shows slot0 picked, cursor
    # advanced to slot1) -- it "worked" (registered a visible change) for the
    # wrong reason, then the plain dialogue_steps loop below took over and
    # blindly kept mashing Return with no stop condition, randomly walking
    # the toggle state for the entire budget (see ROSTER_PICK_GRID_XS's
    # module comment for the full forensic writeup). Detect the grid here
    # and, if present, hand off to adaptive_pick_roster() -- which watches
    # the grid after every tap and stops the instant everyone is picked --
    # INSTEAD of the blind yes_confirm call. Only takes effect when the
    # caller passes chapter_n (sweep_chapter() does); with chapter_n=None
    # this falls back to the pre-existing yes_confirm behavior unchanged,
    # so any other caller/diagnostic script keeps working as before.
    post_exit_shot = shots_dir / f"campexit_{step:03d}_post_exit_confirm_check.png"
    screenshot(name, post_exit_shot)
    if chapter_n is not None and screen_shows_roster_pick_grid(post_exit_shot):
        # 2026-08-29 "ch23retest" round: n_candidates MUST come from the
        # ACTUAL deployed save's roster_count (roster_count - 1, leader
        # excluded), not from guard_selection_threshold(chapter_n) -- those
        # two numbers are only the same when the save happens to have been
        # padded to exactly the threshold, which is off by one for the
        # engine's real win condition (see prepare_chapter_save()'s
        # roster_cap docstring). Using the wrong (threshold-based) count
        # here made adaptive_pick_roster() stop ONE SLOT SHORT of a
        # genuinely-completable grid when the caller had already built a
        # roster_cap=threshold+1 save specifically to fix that gap -- this
        # silently discarded the fix. Falls back to the old threshold-based
        # estimate only when the caller doesn't know the real count.
        n_candidates = (roster_count - 1) if roster_count is not None else guard_selection_threshold(chapter_n) - 1
        log.append(f"attempt_camp_exit: roster pick grid detected immediately after exit_confirm "
                    f"(roster_count={roster_count}, {n_candidates} toggleable candidate(s), "
                    f"source={'live save' if roster_count is not None else 'guard_selection_threshold fallback'}) "
                    f"-- switching to adaptive_pick_roster() instead of the blind yes_confirm call")
        if not adaptive_pick_roster(name, shots_dir, log, n_candidates):
            log.append("attempt_camp_exit: adaptive_pick_roster did not converge, giving up")
            return None
        step += 1

        if n_candidates == guard_selection_threshold(chapter_n):
            # 2026-08-29 "ch23retest" round: when the caller passed the
            # TRUE roster_count (via roster_cap=threshold+1 at save-build
            # time), n_candidates now equals the engine's EBP target
            # exactly -- the CMP EAX,EBP check (0x2b0e3, doc58 2026-08-17
            # 續九) should be satisfied for real, no Escape workaround
            # needed. Confirm the grid actually closed on its own and, if
            # a "確定要進入戰場嗎?" popup follows, take it with a plain
            # Return -- the same _confirm_with_retry() semantics as the
            # non-grid chapters use below.
            log.append("attempt_camp_exit: picked-count matches guard_selection_threshold(chapter_n) exactly "
                        "(roster built with roster_cap=threshold+1) -- expecting the grid to close naturally "
                        "via the engine's own CMP EAX,EBP check, NOT sending the old off-by-one Escape workaround")
            post_pick_shot = screenshot(name, shots_dir / f"campexit_{step:03d}_post_pick_natural.png")
            step += 1
            if screen_shows_roster_pick_grid(post_pick_shot):
                log.append("attempt_camp_exit: WARNING grid still visible after reaching the exact threshold "
                            "count (expected it to auto-close) -- sending one more Return, honestly logging this "
                            "as an open discrepancy rather than assuming success")
                if not _confirm_with_retry("post_exact_pick_retry"):
                    return None
            elif not _confirm_with_retry("battle_entry_confirm"):
                return None
            need_fallback_escape = False
        else:
            need_fallback_escape = True
        # 2026-08-29 "picklock" round, part 2 -- HONEST, UNRESOLVED,
        # CONTRADICTORY EVIDENCE, do not trust this Escape call without
        # re-verifying: the on-screen "剩餘人數" counter reads 1 (not 0)
        # even once every rendered grid slot (10+4 for ch23's 14-candidate
        # grid) is picked, and more Return at that point immediately starts
        # UN-picking slot0 (confirmed via diag_ch23_onemore.py) -- the same
        # forward-wraparound-toggle behavior seen mid-run, not a "one more
        # real candidate exists" signal. A standalone diagnostic
        # (diag_ch23_escape.py, instance diag23esc) tried Escape instead
        # (matching doc91/doc58's "選滿才能離開" -- "can only LEAVE once
        # fully selected" wording) immediately after reaching 14/14, and
        # read a live, non-trivial battle-array pointer (6 enemy records)
        # right after with screen_shows_roster_pick_grid() reading False --
        # looked like a real fix. BUT the very next full sweep_chapter()
        # run using this exact code path (instance pl23c23, same round)
        # instead showed the grid RESET to 0/14 picked (剩餘人數 back to
        # X15) after the same Escape
        # (.wsl_build/round0829b/ch23/shots/campexit_005_post_pick_escape.png)
        # -- the opposite outcome from the same input on the same save.
        # Neither run was re-confirmed a third time, so it's unknown
        # whether Escape's effect depends on exact cursor position/timing
        # (plausible -- the diagnostic script's timing differed slightly
        # from sweep_chapter()'s), or whether the "6 enemies" reading in
        # the diagnostic was itself a stale/transient false positive (this
        # project has documented that exact failure mode elsewhere, see
        # attempt_camp_exit()'s own "winverify" docstring section). Kept
        # here because it is no worse than the pre-existing behavior (both
        # paths currently end in needs_manual_followup for ch23) and gives
        # the next round a concrete, reproducible A/B disagreement to
        # resolve rather than silently reverting to the blind-Return
        # oscillation -- but DO NOT report ch23/ch25/ch28 as fixed on the
        # strength of this block alone.
        if need_fallback_escape:
            send_keys(name, "Escape")
            time.sleep(1.0)
            screenshot(name, shots_dir / f"campexit_{step:03d}_post_pick_escape.png")
            step += 1
            log.append("attempt_camp_exit: sent Escape to leave the fully-picked roster grid "
                        "(displayed remaining-count off-by-one is cosmetic, not a real unmet requirement -- "
                        "see this block's comment)")
    elif not _confirm_with_retry("yes_confirm"):
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

# 2026-08-29 "guard-character id table" -- roster-selection gate for
# ch21-26/28 ("本章[X]必須出場！"). FUN_0002af28 (0x2af28..0x2b438) dispatches
# on the raw (0-based) chapter byte [0x53c03] and pushes a specific
# character id before calling the guard-check FUN_0002b439 (0x2b439); the
# id is NOT the same as 28-chapter-objectives-and-recruits.md's "額外護衛"
# column (confirmed to disagree for ch21: that doc column names Roland/
# Sylph, but the actual disasm push is id21/約拿 Jonah -- see
# docs/knowledge-base/99-chapter-sweep-results.md's 2026-08-29 rounds).
# ch21's id was live-verified (instance `jonah21`) to clear the gate and
# reach the real battle command-ring screen. ch22/23/26 were independently
# re-derived this round via Ghidra's own disassembler (not manual byte
# math) reading 0x2b2d0..0x2b352 end to end, matching the prior round's
# results exactly (including ch26's literal match against doc28's "額外護衛"
# column, which is a coincidence for that one chapter, not a validation of
# the column as a general method). ch24/ch25 (raw 0x17/0x18) never hit any
# CMP that matches in this chain -- confirmed again by this round's own
# disasm, matching the 08-28 round's decompile-based finding.
#
# ch28 (raw 0x1b=27) is a NEW finding this round, not previously live-
# tested: it falls into the same "raw chapter > 0x19" fallthrough bucket as
# ch27/29/30 (0x2b2eb's CMP+JLE, taken only for raw<=0x19; not taken falls
# straight into PUSH 0x9/id9 Yuni with no further CMP), which is exactly
# why ch27's real 13-person roster (which already contains id9) was never
# seen to be blocked by this gate in earlier rounds -- it always silently
# already satisfied it.
GUARD_CHARACTER_IDS: dict[int, list[int]] = {
    21: [21],       # raw 0x14 -- 約拿 Jonah (live-verified, instance jonah21)
    22: [24],       # raw 0x15 -- 希爾法 Sylph
    23: [24],       # raw 0x16 -- 希爾法 Sylph
    26: [9, 29],    # raw 0x19 -- 悠妮 Yuni, then 亞奇梅吉 Archmage (both required, in this order)
    28: [9],        # raw 0x1b -- falls into the raw>0x19 catch-all -- 悠妮 Yuni
}

# 2026-08-17 doc58 續九 DAT_000523e7 flag table (ground truth, live debugger
# reads across raw index 0-30): these chapters render the TOGGLEABLE
# PORTRAIT-GRID roster-selection screen before battle (FUN_0002af28's main
# loop, 出戰人數/剩餘人數 counters + a portrait grid) -- as opposed to
# ch21/ch26's completely different guard mechanism (a silent DAT_00053a45
# array scan via FUN_0002b439, no grid, no player interaction at all).
# CRITICAL for complete_roster_ids()/build_complete_roster_save(): on this
# grid screen the fixed leader (record0) is NEVER a toggleable slot, so a
# roster of exactly guard_selection_threshold(chapter_n) TOTAL members
# (leader included) only ever yields threshold-1 toggleable candidates --
# one short of ever satisfying the engine's CMP EAX,EBP win condition
# (EBP=threshold). Chapters in this set need roster_cap=threshold+1.
# ch23 raw 0x16 is LIVE-VERIFIED (2026-08-29 "ch23retest" round, see doc99
# -- roster_cap=16 [leader+15 real distinct non-leader recruits] converged
# adaptive_pick_roster() in exactly 15 taps with zero oscillation, the grid
# closed via a genuine "確定" popup with no Escape workaround needed, and
# [0x53ecc]==2 + on-disk chapter-byte advance (raw 0x16->0x17) both
# confirmed a literal `pass`). ch24/25/28/29/30(/31) are wired here by the
# SAME disassembled flag + EBP/toggle-array mechanism but are NOT yet
# live-tested with roster_cap=threshold+1 -- do not report them fixed
# without actually running the sweep.
ROSTER_PICK_GRID_CHAPTERS: set[int] = {23, 24, 25, 28, 29, 30}


def guard_selection_threshold(chapter_n: int) -> int:
    """The roster-selection screen's deploy-count parameter (EBP, passed as
    param_1 into the guard-check FUN_0002b439) is 0xf(15) normally, but
    0x13(19) once the raw chapter exceeds 0x1a -- see 0x2af52's
    `CMP [0x53c03],0x1a; JLE +.. ; MOV EBP,0x13` in FUN_0002af28. Padding a
    slot's roster_count to land EXACTLY on this threshold forces "select
    everyone, no free choice" at that screen, sidestepping the need for
    per-character cursor navigation there -- this is the same trick the
    ch21 `jonah21` round used (roster_count padded to exactly 15), verified
    live to work; generalized here with the correct per-chapter value."""
    raw_chapter = chapter_n - 1
    return 0x13 if raw_chapter > 0x1a else 0xf


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


# --- "Complete natural roster" helper (2026-08-29 "fullroster21" round) ---
#
# Every prior chapter-sweep round's roster padding (the `guard_ids`/`else`
# branches below) only ever added the bare-minimum synthetic ids needed to
# satisfy a threshold or a guard check -- e.g. ch21's 4 separate win-check
# attempts all used the SAME 15-member roster (13 real early-game members
# frozen around ch09-12 + guard id21 + one arbitrary ascending-id filler,
# id3), never anything resembling a genuine "reached ch21 by playing
# through ch01-20" roster. This round tested the hypothesis that this
# roster INCOMPLETENESS (not just the guard id) was blocking ch21's
# win-check ([0x53ecc] never reaching 2) -- see docs/knowledge-base/99-
# chapter-sweep-results.md's "2026-08-29 'full-roster' round" section for
# the full writeup. Result: a 15-member roster built by
# `complete_roster_ids()`/`build_complete_roster_save()` below --
# CORE_STARTER_IDS + the guard id + the chronologically-CLOSEST-to-ch21
# story recruits (recency-first, since not everyone who joined by ch19 fits
# in a 15-slot deploy quota) -- got ENGINE-LEVEL WIN CONFIRMED
# ([0x53ecc]==2, ground-truth debugger read) on the very first live run,
# reproducing the exact same ensure_one_ally_acts()+KNOWN_MIN_TURNS_BEFORE_
# KILL=9 code path that had failed 2 prior times with the old sparse
# roster. This is the first time this project got signal that composition
# (not just count/threshold) matters for a guard-gated chapter's win-check.
#
# UPDATE (2026-08-29 "picklock"/"ch23retest" rounds): ch22 also got a
# live-verified, literal `pass` (disk write included) with this method,
# and ch23 -- the chapter this comment originally flagged as untested --
# is now ALSO live-verified, but needed one additional fix beyond plain
# complete_roster_ids(): ch23 is a ROSTER_PICK_GRID_CHAPTERS chapter (shows
# the toggleable portrait-grid screen, unlike ch21/22's silent guard-array
# scan), so its roster needed cap=guard_selection_threshold(23)+1=16 (not
# 15) -- the leader is never a toggleable grid slot, so a 15-total roster
# only ever produces 14 real candidates, one short of the engine's
# CMP EAX,EBP(15) check. complete_roster_ids() now defaults to this +1
# automatically for any chapter in ROSTER_PICK_GRID_CHAPTERS -- see that
# set's module comment for the full mechanism and which other chapters
# (25/28/29/30) are wired the same way but NOT yet live-tested. ch23 also
# needed KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL (added this round). ch25/28
# remain untested with either fix -- do not upgrade their verdicts without
# actually running the sweep against them.

CORE_STARTER_IDS = [0, 1, 4, 9, 30]  # Sol/Hanaux/Ares/Yuni/Gaia -- present from
# record index 0-4 in EVERY real FD2.SAV this project has examined
# (.wsl_build/chapter_sweep/FD2_source.SAV and others cited in
# tools/fd2save.py's module docstring), i.e. these never show up as a `join`
# beat because they are already in the party before ch01 -- see doc28 row 1
# ("哈諾(出現前勿滅完)") and doc49 for identity. id0 (Sol) is always kept
# separately as the fixed leader record, never dropped even under a tight cap.


def _walk_join_beats(beats: list[dict], out: list[int]) -> None:
    """Recursively collect `join` beat character ids (handles both the
    `{"args": [id]}` and `{"char_id": id}` shapes seen across
    docs/data/chapter_beats/ch*_post.json -- see the ch06_post.json
    "join"/"char_id" outlier found while compiling this round's roster)."""
    for b in beats:
        if b.get("op") == "join":
            cid = None
            args = b.get("args")
            if args:
                cid = args[0]
            elif "char_id" in b:
                cid = b["char_id"]
            if cid is not None:
                out.append(cid)
        for k in ("then", "else"):
            if k in b:
                _walk_join_beats(b[k], out)


def natural_join_order(chapter_n: int) -> list[int]:
    """Chronological (earliest-first), de-duplicated list of character ids
    that joined via a scripted `join` beat in ch00_post.json..ch(N-2)_post.json
    -- i.e. everyone who story-recruited before chapter_n opens.

    IMPORTANT, found while building this (2026-08-29 "fullroster21" round):
    docs/data/chapter_beats/ch{NN}_post.json is indexed by RAW chapter number
    (0-based) -- ch00_post.json is raw chapter 0 = game ch01's own
    post-battle, ch20_post.json is raw chapter 20 = game ch21's OWN
    post-battle (confirmed both by cross-checking ch17_post.json's join ids
    [21, 7] against the disassembly-proven ch21 guard id 21/約拿 joining in
    raw17=game ch18, and by ch20_post.json containing join ids [23, 24] --
    exactly the 羅蘭/希爾法 pair independently proven to be ch21's own
    map-native "own"-camp units in the "map-native guard" round, not
    pre-ch21 recruits). estimate_roster_size() above uses `range(1,
    chapter_n)` reading ch{ch:02d}_post.json, which for chapter_n=21 reads
    ch01_post.json..ch20_post.json -- that INCLUDES the target chapter's own
    post-battle file. This is harmless for estimate_roster_size() (it only
    ever produces a bare synthetic-filler COUNT, not specific ids), but
    would be a real correctness bug here if copied verbatim: it would fold
    a chapter's own new-this-chapter map-native joins into what's supposed
    to be a "roster as it existed BEFORE this chapter's battle" snapshot.
    Deliberately uses `range(0, chapter_n - 1)` instead -- do not "fix" this
    to match estimate_roster_size()'s range without re-deriving which one is
    actually wrong."""
    ids: list[int] = []
    seen: set[int] = set()
    for ch in range(0, chapter_n - 1):
        path = CHAPTER_BEATS_DIR / f"ch{ch:02d}_post.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        found: list[int] = []
        _walk_join_beats(data.get("beats", []), found)
        for cid in found:
            if cid not in seen:
                seen.add(cid)
                ids.append(cid)
    return ids


def complete_roster_ids(chapter_n: int, cap: int | None = None) -> list[int]:
    """Build the most complete "naturally reached chapter_n by playing
    ch01..chapter_n-1" roster that fits within `cap`.

    `cap` defaults to guard_selection_threshold(chapter_n) -- EXCEPT for
    chapters in ROSTER_PICK_GRID_CHAPTERS, which default to
    guard_selection_threshold(chapter_n)+1. See ROSTER_PICK_GRID_CHAPTERS'
    module comment for why: on the toggleable portrait-grid selection
    screen, the leader is never a toggleable slot, so a roster of exactly
    `threshold` total members only yields threshold-1 real candidates --
    one short of the engine's CMP EAX,EBP win condition. Chapters that use
    the OTHER guard mechanism (silent DAT_00053a45 array scan, e.g. ch21/
    ch26 -- not in ROSTER_PICK_GRID_CHAPTERS) have no such screen and no
    off-by-one, so `threshold` alone is correct for them (live-verified,
    ch21). ch23 is live-verified for the +1 case too (2026-08-29
    "ch23retest" round, see doc99); the other ROSTER_PICK_GRID_CHAPTERS
    entries are wired by the same mechanism but not yet live-tested this
    way.

    Priority order when not everyone fits (id0/leader and the guard id(s)
    are never dropped): id0 (fixed leader) -> this chapter's required guard
    id(s) (GUARD_CHARACTER_IDS) -> CORE_STARTER_IDS -> natural_join_order()
    recruits taken MOST-RECENT-FIRST (i.e. closest chronologically to
    chapter_n). Recency-first, not chronological/ascending order, was a
    deliberate choice this round: the previously-tested ch21 roster already
    over-represented the EARLIEST recruits (they came for free in the fixed
    13-member real base save) and had never tried the LATE recruits at all
    -- recency-first maximizes new, previously-untested composition per
    slot spent. See this function's call site for the live-verified ch21
    result."""
    if cap is None:
        cap = guard_selection_threshold(chapter_n)
        if chapter_n in ROSTER_PICK_GRID_CHAPTERS:
            cap += 1
    required_ids = GUARD_CHARACTER_IDS.get(chapter_n, [])
    recruits_recent_first = list(reversed(natural_join_order(chapter_n)))
    ordered: list[int] = [0]
    for cid in required_ids:
        if cid not in ordered:
            ordered.append(cid)
    for cid in CORE_STARTER_IDS:
        if cid not in ordered:
            ordered.append(cid)
    for cid in recruits_recent_first:
        if cid not in ordered:
            ordered.append(cid)
    return ordered[:cap]


def build_complete_roster_save(source_sav: Path, chapter_n: int, slot: int, log: list[str],
                                cap: int | None = None) -> bytes:
    """Return a new plaintext buffer whose slot's roster is complete_roster_ids()
    (see above), preferring the source save's REAL, engine-produced record
    bytes for any id it already has (byte-for-byte, not rebuilt) and only
    falling back to fd2save.build_join_record()'s constructor-formula
    synthetic records for ids the source save doesn't have. This is the
    same technique the manual 2026-08-29 "fullroster21" round used by hand
    (keep record indices 0-4 -- the real ids [0,9,4,30,1] -- from
    .wsl_build/chapter_sweep/FD2_source.SAV untouched, append 10 synthetic
    records for the rest), generalized to any source save/chapter."""
    plain = fd2save.decode(source_sav.read_bytes())
    plain = fd2save.set_slot_chapter(plain, slot, chapter_n - 1)
    start, _ = fd2save.slot_bounds(slot)
    meta_start = start + fd2save.ROSTER_SIZE
    current_count = plain[meta_start + 1]
    target_ids = complete_roster_ids(chapter_n, cap=cap)
    target_set = set(target_ids)
    source_ids = fd2save.roster_character_ids(plain, slot, current_count)

    plain = bytearray(plain)
    kept_ids: list[int] = []
    write_at = 0
    for i, cid in enumerate(source_ids):
        if cid in target_set and cid not in kept_ids:
            record = bytes(plain[start + i * fd2save.UNIT_SIZE: start + (i + 1) * fd2save.UNIT_SIZE])
            plain[start + write_at * fd2save.UNIT_SIZE: start + (write_at + 1) * fd2save.UNIT_SIZE] = record
            kept_ids.append(cid)
            write_at += 1
    plain[meta_start + 1] = write_at
    log.append(f"build_complete_roster_save: kept {write_at} real record(s) from source ({kept_ids})")
    plain = bytes(plain)

    missing_ids = [cid for cid in target_ids if cid not in kept_ids]
    if missing_ids:
        plain = fd2save.append_roster_members(plain, slot, missing_ids)
        log.append(f"build_complete_roster_save: appended {len(missing_ids)} synthetic record(s) ({missing_ids})")
    log.append(f"build_complete_roster_save: final roster={target_ids} (cap={cap or guard_selection_threshold(chapter_n)})")
    return plain


def prepare_chapter_save(source_sav: Path, chapter_n: int, out_sav: Path, slot: int, log: list[str],
                          pad_roster: bool = True, roster_mode: str = "complete",
                          roster_cap: int | None = None) -> Path:
    if roster_mode == "complete":
        # roster_cap defaults to None -> build_complete_roster_save() falls
        # back to guard_selection_threshold(chapter_n) (the TOTAL roster
        # size, leader included). 2026-08-29 "ch23retest" round: for any
        # chapter whose roster-selection screen is the toggleable
        # portrait-grid kind (not the map-native/DAT_00053a45 guard-scan
        # kind -- see attempt_camp_exit()'s roster_count param docstring),
        # this default is ONE TOO FEW -- the leader (record0) is never a
        # toggleable grid slot, so a roster of exactly
        # guard_selection_threshold(chapter_n) total members only ever
        # yields threshold-1 toggleable candidates, which can never
        # satisfy the engine's CMP EAX,EBP (EBP=threshold) win condition
        # (ground-truth disasm, docs/knowledge-base/58-remake-live-
        # verification-log.md 2026-08-17 續九/續十). Pass
        # roster_cap=guard_selection_threshold(chapter_n)+1 explicitly for
        # those chapters (ch23 live-confirmed, see doc99's "ch23retest"
        # section) to get a full-quota-satisfying roster.
        plain = build_complete_roster_save(source_sav, chapter_n, slot, log, cap=roster_cap)
        stored = fd2save.encode(plain)
        fd2save.decode(stored)
        out_sav.parent.mkdir(parents=True, exist_ok=True)
        out_sav.write_bytes(stored)
        return out_sav

    plain = fd2save.decode(source_sav.read_bytes())
    raw_chapter = chapter_n - 1
    plain = fd2save.set_slot_chapter(plain, slot, raw_chapter)

    start, _ = fd2save.slot_bounds(slot)
    meta_start = start + fd2save.ROSTER_SIZE
    current_count = plain[meta_start + 1]
    guard_ids = GUARD_CHARACTER_IDS.get(chapter_n)
    if not pad_roster:
        wanted = estimate_roster_size(chapter_n)
        log.append(f"prepare_chapter_save: --no-roster-pad, keeping source roster_count={current_count} unchanged "
                    f"(estimate_roster_size({chapter_n})={wanted})")
    elif guard_ids:
        # This chapter has a live-verified/disasm-verified "本章[X]必須出場！"
        # roster-selection gate (GUARD_CHARACTER_IDS above) -- pad to the
        # chapter's exact selection threshold (guard_selection_threshold())
        # instead of estimate_roster_size()'s join-beat count, and make sure
        # the required guard id(s) are part of the padding (or already
        # present in the source roster, in which case nothing needs adding
        # for them specifically).
        wanted = guard_selection_threshold(chapter_n)
        existing_ids = set(fd2save.roster_character_ids(plain, slot, current_count))
        required_ids = [cid for cid in guard_ids if cid not in existing_ids]
        already_present = [cid for cid in guard_ids if cid in existing_ids]
        filler_needed = max(0, wanted - current_count - len(required_ids))
        filler_ids = [cid for cid in range(32) if cid not in existing_ids and cid not in required_ids][:filler_needed]
        pad_ids = required_ids + filler_ids
        if current_count + len(pad_ids) > wanted:
            log.append(f"prepare_chapter_save: WARNING source roster_count={current_count} + required guard "
                        f"id(s) {required_ids} already exceeds selection threshold {wanted} for chapter {chapter_n} "
                        f"-- padding anyway so the guard id(s) are present, selection screen may allow free choice")
        if pad_ids:
            try:
                plain = fd2save.append_roster_members(plain, slot, pad_ids)
                log.append(f"prepare_chapter_save: guard-gated chapter {chapter_n} -- padded roster "
                            f"{current_count}->{current_count + len(pad_ids)} with ids {pad_ids} "
                            f"(required guard ids {guard_ids}, already present {already_present}, "
                            f"selection threshold {wanted})")
            except ValueError as e:
                log.append(f"prepare_chapter_save: roster padding skipped ({e})")
        else:
            log.append(f"prepare_chapter_save: guard-gated chapter {chapter_n} -- guard id(s) {guard_ids} already "
                        f"all present ({already_present}), roster_count={current_count} already >= threshold "
                        f"{wanted}, no padding needed")
    else:
        wanted = estimate_roster_size(chapter_n)
        if wanted > current_count:
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
                   pad_roster: bool = True, use_navigate_hints: bool = True,
                   roster_mode: str = "complete", roster_cap: int | None = None) -> dict:
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
        prepare_chapter_save(source_sav, chapter_n, patched_sav, slot, log, pad_roster=pad_roster,
                              roster_mode=roster_mode, roster_cap=roster_cap)
        actual_roster_count = None
        if roster_mode == "complete":
            actual_roster_count = len(complete_roster_ids(chapter_n, cap=roster_cap))
            log.append(f"sweep_chapter: complete-roster build has actual roster_count={actual_roster_count} "
                        f"(roster_cap={roster_cap}, guard_selection_threshold={guard_selection_threshold(chapter_n)})")

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
                # max_steps must cover the whole hint list -- advance_generic's
                # default (48) silently truncates a longer hint otherwise (a
                # latent bug noticed this round; KNOWN_NAVIGATE_HINTS had never
                # been given an entry longer than 48 before, so it was never
                # observed in practice).
                adv = advance_generic(name, shots_dir, log, max_steps=max(48, len(hint)), hint_keys=hint)
                base = adv["battle_base"]
            else:
                log.append("trying attempt_camp_exit (doc91 town-hub Right x3 -> 出口 -> YES -> dialogue-advance sequence) first")
                camp_exit_steps = CAMP_EXIT_DIALOGUE_STEPS.get(chapter_n, 120)
                adv = attempt_camp_exit(name, shots_dir, log, dialogue_steps=camp_exit_steps,
                                         chapter_n=chapter_n,
                                         roster_count=actual_roster_count) if use_navigate_hints else None
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
            # 2026-08-28 "ch11r8flag" round (doc25 §3.2.5): some chapters'
            # win-check dispatch gate (0x117e7's cursor-on-a-live-unit gate,
            # see ensure_one_ally_acts()'s docstring) never gets satisfied
            # by the plain mass-kill+End-Turn recipe alone, no matter how
            # many kill-cycles are retried, because confirm_end_turn()
            # deliberately keeps the cursor off every unit. If this chapter
            # is known to need it, do one real select->move->confirm-Wait
            # unit action FIRST -- chest-agnostic, does not target any
            # specific tile. Non-fatal if it fails (logged, falls through to
            # the normal mass-kill attempt regardless). MUST run before any
            # KNOWN_MIN_TURNS_BEFORE_KILL wait below, not after -- a live
            # smoke-test this round (ch11, sweep_chapter() end to end) found
            # that running it AFTER an (absent, for ch11) turn-wait and
            # going straight to mass-kill produced "anomaly" (stuck at
            # [0x53ecc]==0), even though the standalone move_only_test.py
            # script (ally-action -> 3-turn wait -> mass-kill+End-Turn, in
            # that order) reliably won -- ch11 apparently needs BOTH the
            # ally-action AND the turn-wait, in that order, not just the
            # ally-action alone. See KNOWN_MIN_TURNS_BEFORE_KILL's {11: 3}
            # entry below, added together with this reordering.
            if chapter_n in KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL:
                log.append(f"chapter {chapter_n} has a KNOWN_NEEDS_ALLY_ACTION_BEFORE_KILL override -- "
                           f"running ensure_one_ally_acts() before any turn-wait/mass-kill")
                acted = ensure_one_ally_acts(name, shots_dir, log)
                log.append(f"ensure_one_ally_acts() returned {acted}")
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
                log.append(f"post-ally-action rescan: base={base}, enemy_addrs={len(enemy_addrs)}")

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
                                use_navigate_hints=not args.no_navigate_hints,
                                roster_mode="pad" if args.no_complete_roster else "complete",
                                roster_cap=args.roster_cap)
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
    sp.add_argument("--no-complete-roster", action="store_true",
                     help="use the old minimal guard/threshold padding instead of the DEFAULT "
                          "complete_roster_ids()/build_complete_roster_save() chronologically-complete-as-fits "
                          "'naturally reached this chapter' roster (CORE_STARTER_IDS + guard id(s) + most-recent "
                          "story recruits first). 'complete' has been the default since the 2026-08-29 "
                          "'ch23retest' round (live-verified for ch21/ch22/ch23, see doc99) -- this flag is an "
                          "escape hatch for a chapter you specifically want the old minimal-padding behavior for.")
    sp.add_argument("--roster-cap", type=int, default=None,
                     help="override complete_roster_ids()'s cap (default guard_selection_threshold(chapter_n)). "
                          "IMPORTANT for any chapter whose roster-selection screen is the toggleable portrait-grid "
                          "kind (ch23/24/25/28/29/30 -- see attempt_camp_exit()'s roster_count docstring): the "
                          "leader is never a toggleable slot, so pass guard_selection_threshold(chapter_n)+1 here "
                          "to get a roster whose non-leader count actually matches the engine's EBP target "
                          "(ch23 live-confirmed 2026-08-29 'ch23retest' round, see doc99).")
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
