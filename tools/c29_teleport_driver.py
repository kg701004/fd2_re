#!/usr/bin/env python
"""One-off live driver for the 2026-08-29 "ch29tp" round: teleport Yuni
(char id 9) directly into the ch29 upper "control center" field-event zone
(native_field_event_slots x=17..27,y=0..15 -> event_id 80, see
docs/knowledge-base/25-battle-event-system.md's event table) instead of
building general escort-navigation automation, per explicit user instruction.

Reuses tools/fd2_chapter_sweep.py's harness/debugger primitives and record
layout constants (UNIT_STRIDE/UNIT_CAMP_OFFSET/etc, plus the char-id offset
+0x07 confirmed against remake/internal/campaign/native_join_constructor.go's
MaterializePersistentUnit: record[7]=byte(id); record[8]=byte(id)).

MUST be run with Windows Python (see doc99 "ch29live" gotcha) -- REPO_ROOT
derivation in fd2_chapter_sweep.py assumes a C:\\... style path.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_chapter_sweep as S  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NAME = "c29tp"
CHAPTER = 29
REPO_ROOT = S.REPO_ROOT
RESULTS_DIR = REPO_ROOT / ".wsl_build" / "chapter_sweep"
CH_DIR = RESULTS_DIR / "ch29tp"
SHOTS = CH_DIR / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)
STATE_FILE = CH_DIR / "state.json"

CHAR_ID_OFFSET = 0x07
YUNI_ID = 9
SOL_ID = 0
TARGET_X, TARGET_Y = 22, 8  # inside native_field_event_slots' ch29 zone (17-27,0-15), on the cost==1 corridor
BUFF_HP = 999


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"phase": "start", "log": []}


def save_state(st):
    STATE_FILE.write_text(json.dumps(st, indent=2))


def log(st, msg):
    print(msg)
    st["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
    save_state(st)


def read_word(name, addr):
    raw = S.read_mem(name, addr, min_bytes=2)
    if raw is None:
        return None
    return raw[0] | (raw[1] << 8)


def write_word(name, addr, value):
    S.write_byte(name, addr, value & 0xFF)
    S.write_byte(name, addr + 1, (value >> 8) & 0xFF)


def scan_all_records(name, base, log_list, max_slots=96):
    """Read camp(+6)/charid(+7)/X(+0)/Y(+1) for every plausible record
    (both camps), not just camp==0 like scan_enemy_slots(). Returns list of
    dicts."""
    out = []
    for k in range(max_slots):
        addr = base + k * S.UNIT_STRIDE
        raw = S.read_mem(name, addr, min_bytes=16)
        if raw is None:
            log_list.append(f"scan_all_records: read failed at slot{k} addr={addr:#x}, stopping")
            break
        if all(b == 0 for b in raw[:8]):
            continue
        out.append({
            "slot": k, "addr": addr, "x": raw[0], "y": raw[1],
            "acted": raw[5], "camp": raw[6], "charid": raw[7],
        })
    return out


def main():
    st = load_state()
    phase = st["phase"]

    if phase == "start":
        log(st, f"=== ch29tp round starting, instance={NAME} ===")
        patched_sav = CH_DIR / "patched.SAV"
        reuse = RESULTS_DIR / "ch29" / "patched.SAV"
        prep_log = []
        S.prepare_chapter_save(RESULTS_DIR / "FD2_source.SAV", CHAPTER, patched_sav, 0, prep_log,
                                pad_roster=True, roster_mode="complete")
        for line in prep_log:
            log(st, "prep: " + line)
        roster_count = len(S.complete_roster_ids(CHAPTER))
        log(st, f"complete_roster_ids(29) count={roster_count}")
        st["roster_count"] = roster_count
        st["phase"] = "launch"
        save_state(st)
        return 0

    if st["phase"] == "launch":
        log(st, f"launching harness instance '{NAME}' (background, keepalive 3600s)")
        S.launch_instance(NAME, keepalive=3600)
        time.sleep(14)
        S.overwrite_save(NAME, CH_DIR / "patched.SAV")
        log(st, "overwrote workdir FD2.SAV with patched save")
        st["phase"] = "boot"
        save_state(st)
        return 0

    if st["phase"] == "boot":
        for _ in range(30):
            S.send_keys(NAME, "Escape")
            time.sleep(0.3)
        S.screenshot(NAME, SHOTS / "01_title.png")
        S.send_keys(NAME, "Down")
        time.sleep(0.5)
        S.send_keys(NAME, "Return")
        time.sleep(2.0)
        S.send_keys(NAME, "Return")
        time.sleep(2.5)
        S.screenshot(NAME, SHOTS / "02_post_load.png")
        log(st, "boot/title/LOAD sequence done")
        st["phase"] = "campexit"
        save_state(st)
        return 0

    if st["phase"] == "campexit":
        camp_log = []
        adv = S.attempt_camp_exit(NAME, SHOTS, camp_log, dialogue_steps=S.CAMP_EXIT_DIALOGUE_STEPS.get(CHAPTER, 480),
                                   chapter_n=CHAPTER, roster_count=st["roster_count"])
        for line in camp_log:
            log(st, "campexit: " + line)
        base = adv["battle_base"] if adv else None
        if base is None:
            log(st, "attempt_camp_exit FAILED to find battle -- aborting phase, manual intervention needed")
            st["phase"] = "campexit_failed"
            save_state(st)
            return 1
        st["base_raw"] = base
        log(st, f"battle confirmed, base={base:#x}")
        st["phase"] = "settle"
        save_state(st)
        return 0

    if st["phase"] == "settle":
        settle_log = []
        best_base, best_enemies = st["base_raw"], []
        for i in range(6):
            time.sleep(2.5)
            S.enter_debugger(NAME)
            time.sleep(0.4)
            cur_base = S.read_battle_array_base(NAME)
            cur_enemies = S.scan_enemy_slots(NAME, cur_base, settle_log) if cur_base is not None else []
            S.debugger_cmd(NAME, "RUN")
            time.sleep(0.2)
            log(st, f"settle round {i+1}/6: base={cur_base}, enemies={len(cur_enemies)}")
            if len(cur_enemies) >= len(best_enemies):
                best_base, best_enemies = cur_base, cur_enemies
        st["base"] = best_base
        st["enemy_addrs"] = best_enemies
        log(st, f"settle done: base={best_base:#x}, enemies={len(best_enemies)}")
        st["phase"] = "survey"
        save_state(st)
        return 0

    if st["phase"] == "survey":
        S.enter_debugger(NAME)
        time.sleep(0.4)
        recs = scan_all_records(NAME, st["base"], st["log"], max_slots=96)
        S.debugger_cmd(NAME, "RUN")
        time.sleep(0.3)
        st["records"] = recs
        allies = [r for r in recs if r["camp"] == 2]
        enemies = [r for r in recs if r["camp"] == 0]
        log(st, f"survey: {len(recs)} total records, {len(allies)} allies(camp==2), {len(enemies)} enemies(camp==0)")
        for r in allies:
            log(st, f"  ally slot{r['slot']} addr={r['addr']:#x} charid={r['charid']} xy=({r['x']},{r['y']}) acted={r['acted']:#x}")
        yuni = [r for r in allies if r["charid"] == YUNI_ID]
        sol = [r for r in allies if r["charid"] == SOL_ID]
        if not yuni:
            log(st, "WARNING: no ally record with charid==9 (Yuni) found! Dumping full ally list above for manual review.")
        if not sol:
            log(st, "WARNING: no ally record with charid==0 (Sol) found!")
        st["yuni_addr"] = yuni[0]["addr"] if yuni else None
        st["sol_addr"] = sol[0]["addr"] if sol else None
        S.screenshot(NAME, SHOTS / "03_battle_map.png")
        st["phase"] = "buff_and_teleport"
        save_state(st)
        return 0

    if st["phase"] == "buff_and_teleport":
        S.enter_debugger(NAME)
        time.sleep(0.4)
        allies = [r for r in st["records"] if r["camp"] == 2]
        for r in allies:
            addr = r["addr"]
            write_word(NAME, addr + 0x40, BUFF_HP)
            write_word(NAME, addr + 0x42, BUFF_HP)
            log(st, f"buffed ally slot{r['slot']} charid={r['charid']} HP->{BUFF_HP}/{BUFF_HP}")
        if st.get("yuni_addr"):
            ya = st["yuni_addr"]
            before_x = S.read_mem(NAME, ya, min_bytes=2)
            S.write_byte(NAME, ya + 0x00, TARGET_X)
            S.write_byte(NAME, ya + 0x01, TARGET_Y)
            after = S.read_mem(NAME, ya, min_bytes=2)
            log(st, f"Yuni teleport: before=({before_x[0]},{before_x[1]}) -> wrote ({TARGET_X},{TARGET_Y}), "
                     f"readback=({after[0] if after else '?'},{after[1] if after else '?'})")
        else:
            log(st, "SKIPPED Yuni teleport -- no Yuni record found in survey phase")
        S.debugger_cmd(NAME, "RUN")
        time.sleep(0.3)
        S.screenshot(NAME, SHOTS / "04_post_teleport.png")
        st["phase"] = "masskill"
        save_state(st)
        return 0

    if st["phase"] == "masskill":
        kill_log = []
        S.enter_debugger(NAME)
        time.sleep(0.4)
        written = S.mass_kill_enemies(NAME, st["enemy_addrs"], kill_log)
        for line in kill_log:
            log(st, "masskill: " + line)
        log(st, f"mass_kill_enemies wrote death sig to {written} slots")
        S.debugger_cmd(NAME, "RUN")
        time.sleep(0.3)
        st["phase"] = "endturn1"
        save_state(st)
        return 0

    if st["phase"] == "endturn1":
        et_log = []
        res = S.confirm_end_turn(NAME, SHOTS, et_log, enemy_addrs=st["enemy_addrs"])
        for line in et_log:
            log(st, "endturn: " + line)
        log(st, f"confirm_end_turn result: {res}")
        st["phase"] = "poll_win_1"
        save_state(st)

    if st["phase"] == "poll_win_1":
        S.enter_debugger(NAME)
        time.sleep(0.4)
        t0 = time.time()
        code = None
        while time.time() - t0 < 20:
            code = S.read_pending_result_code(NAME)
            chap = S.read_chapter_index_live(NAME)
            log(st, f"poll t={time.time()-t0:.1f}s pending_result_code={code} chapter_index={chap}")
            if code == 2:
                break
            time.sleep(2)
        S.debugger_cmd(NAME, "RUN")
        time.sleep(0.3)
        st["engine_win_after_teleport_and_masskill"] = (code == 2)
        S.screenshot(NAME, SHOTS / "05_after_first_endturn.png")
        st["phase"] = "checkpoint1_done"
        save_state(st)
        log(st, f"=== CHECKPOINT 1 done: engine_win={code==2} (code={code}) === stopping for review")

    print("DONE phase:", st["phase"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
