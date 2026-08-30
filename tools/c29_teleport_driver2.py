#!/usr/bin/env python
"""Follow-up to c29_teleport_driver.py: after checkpoint1 (1 End-Turn cycle,
no engine win), verify Yuni's position stuck and try a few more End-Turn
cycles in case the field-event/escort trigger needs more than one turn to
resolve, or needs to be re-checked after the enemy-phase/turn-counter
actually advances."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_chapter_sweep as S  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NAME = "c29tp"
CH_DIR = S.REPO_ROOT / ".wsl_build" / "chapter_sweep" / "ch29tp"
SHOTS = CH_DIR / "shots"
STATE_FILE = CH_DIR / "state.json"
st = json.loads(STATE_FILE.read_text())


def log(msg):
    print(msg)
    st["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
    STATE_FILE.write_text(json.dumps(st, indent=2))


def main():
    yuni_addr = st["yuni_addr"]
    S.enter_debugger(NAME)
    time.sleep(0.4)
    raw = S.read_mem(NAME, yuni_addr, min_bytes=8)
    log(f"post-endturn1 Yuni record readback: x={raw[0]}, y={raw[1]}, acted={raw[5]:#x}, camp={raw[6]}")
    S.debugger_cmd(NAME, "RUN")
    time.sleep(0.3)

    for i in range(2, 5):
        et_log = []
        res = S.confirm_end_turn(NAME, SHOTS, et_log, enemy_addrs=st["enemy_addrs"])
        for line in et_log:
            log(f"endturn{i}: {line}")
        log(f"confirm_end_turn #{i} result: {res}")
        S.enter_debugger(NAME)
        time.sleep(0.4)
        code = S.read_pending_result_code(NAME)
        chap = S.read_chapter_index_live(NAME)
        S.debugger_cmd(NAME, "RUN")
        time.sleep(0.3)
        log(f"after endturn #{i}: pending_result_code={code}, chapter_index={chap}")
        S.screenshot(NAME, SHOTS / f"06_after_endturn{i}.png")
        if code == 2:
            log(f"ENGINE WIN reached after endturn #{i}!")
            st["engine_win_final"] = True
            st["win_after_n_endturns"] = i
            STATE_FILE.write_text(json.dumps(st, indent=2))
            return 0

    log("No engine win after 4 total End-Turn cycles. Stopping this probe.")
    st["engine_win_final"] = False
    STATE_FILE.write_text(json.dumps(st, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
