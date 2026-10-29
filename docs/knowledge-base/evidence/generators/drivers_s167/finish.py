# 存檔:原 scratchpad 驅動腳本(續一百六十七),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""lc167a 後半:在「要結束本回合的行動嗎?」按 YES → 等 enemy_phase_dispatch 的 R(只 grep 檔案)→ 閒置 25 秒(P2)。
不進除錯器。結果寫 cl/NAME/finish.json。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fd2_chapter_sweep as sw  # noqa: E402
from lc167 import DELTA, ENEMY_PHASE, ENEMY_WAIT_S, IDLE_P2_S, last_t, wsl  # noqa: E402

name = sys.argv[1]
wd = f"/home/kg701004/fd2-run-harness-{name}"
d = HERE / "cl" / name / "finish"
d.mkdir(parents=True, exist_ok=True)
res: dict = {"t_host": {}, "marks": {}}
res["marks"]["yes"] = last_t(wd)
sw.send_keys(name, "Return")
res["t_host"]["yes"] = time.time()
pat = f"^R [0-9]+ {ENEMY_PHASE + DELTA:08x} "
t0, n, got = time.time(), 0, ""
while time.time() - t0 < ENEMY_WAIT_S:
    time.sleep(5.0)
    n += 1
    sw.screenshot(name, d / f"wait_{n:02d}.png")
    got = wsl(f"grep -c -E '{pat}' {wd}/CALLLOG.TXT").strip()
    if got not in ("", "0"):
        break
res["t_host"]["enemy_done"] = time.time()
res["enemy_wait"] = {"grep": got, "shots": n}
ok = got not in ("", "0")
if ok:
    time.sleep(3.0)
    res["marks"]["P2_c"] = last_t(wd)
    time.sleep(IDLE_P2_S)
    res["marks"]["P2_d"] = last_t(wd)
    sw.screenshot(name, d / "p2_idle_end.png")
res["ok"] = ok
(d / "finish.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
sys.exit(0 if ok else 1)
