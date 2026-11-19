"""lc287d:正常結束回合直到回合事件 17(不寫記憶體)。每個指令都經 lc287b.py(所以有截圖判讀與 CALLLOG 計數)。

敵方階段只在「dialog 入口的 E 筆數比上次送鍵時多、而且畫面讀得到字」時送 Return;事件 17 一進入就停,等演出(act E 筆數)結束後讀單位 1。
用法:python turns287.py NAME MAX_TURNS
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def lc(*a: str, timeout: int = 300) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(HERE / "lc287b.py"), *a], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def calls(name: str) -> dict:
    return json.loads(lc("calls", name)[1].splitlines()[-1])


def main(name: str, max_turns: int) -> int:
    start_round = eval(lc("unit", name, "t_start", "1")[1].splitlines()[-1])["round"]
    print("start round", start_round)
    for t in range(max_turns):
        base = calls(name)
        for k in range(6 if not (t == 0 and WAIT_FIRST) else 0):                        # 游標在單位上就往上移,最多 6 次
            rc, out = lc("endturn", name, f"t{t}_{k}")
            print(out.splitlines()[-1][:160])
            if rc == 0:
                break
            if "游標格有單位" not in out:
                print("endturn 失敗,停")
                return 1
            lc("key", name, f"t{t}_mv{k}", "0.8", "Up")
        else:
            if not (t == 0 and WAIT_FIRST):
                return 1
        last_dlg = base["dialog"]
        prev_c, idle = None, 0                    # 計數 3 次沒變而畫面有字 = 對白在等鍵(dialog 筆數不一定再增加)
        t0 = time.time()
        while True:
            time.sleep(5)
            c = calls(name)
            if c["ev17"] > base["ev17"]:
                print(f"turn {t}: ev17 entered", c)
                return 0
            if c["input_loop"] > base["input_loop"] and time.time() - t0 > 8:
                # 輸入迴圈在敵方階段也會進入:以回合計數 [0x53bef] 變大(我方階段開始時 +1)判定新的我方階段
                rc, out = lc("unit", name, f"t{t}_rd{int(time.time())}", "1")
                try:
                    rnd = eval(out.splitlines()[-1])["round"]
                except Exception:  # noqa: BLE001
                    rnd = None
                if rnd is not None and rnd > start_round:
                    print(f"turn {t}: round {rnd}", c)
                    start_round = rnd
                    break
            idle = idle + 1 if c == prev_c else 0
            prev_c = c
            if c["dialog"] > last_dlg or idle >= 3:
                idle = 0
                rc, out = lc("text", name, f"t{t}_d{c['dialog']}")
                if "lines=[]" not in out and "讀不了" not in out:
                    lc("key", name, f"t{t}_r{c['dialog']}", "1.0", "Return")
                    last_dlg = c["dialog"]
            if time.time() - t0 > 900:
                print(f"turn {t}: 15 分鐘沒有回到我方階段,停", c)
                return 1
    return 2


WAIT_FIRST = "--wait-first" in sys.argv    # 從敵方 / 友方階段中途接手:第一輪不結束回合,先等回合數變大

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2])))
