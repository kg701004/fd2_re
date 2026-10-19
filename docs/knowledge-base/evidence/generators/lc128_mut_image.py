"""續一百二十八:lc128_analyze.py(原 an128.py)的突變測試(改記憶體裡的 FD2.EXE 副本;原暫存 mut_an128.py,續一百三十四移進倉庫)。
由 ev_dispatch_index_bounds_table_split.py 以子行程執行,輸出原樣寫進證據。

會讓上限超過 27 的突變:an128 必須以 FAIL 結束,FAIL 行含指定的檢查,沒有 Traceback。
不影響上限的突變:上限的兩項必須仍符合(證明檢查看的是上限,不是位元組有沒有變)。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent

WANT = {
    "player_upper_1c": "玩家可進表的索引 <= 27",
    "ai_guard_0": "AI 可進表的索引 <= 27",
    "score_last_1c": "AI 可進表的索引 <= 27",
    "score_16_to_1d": "AI 可進表的索引 <= 27",
    "writer_extra": "[0x53c2f] 只有一個寫入端 0x15b12",
    "player_lower_0": None,
    # je -> jmp:玩家端一格都進不了表 -> 「到不了的只有 24」不符合;上限檢查仍須符合
    "player_skip_18_off": "兩處都到不了的格只有 24(0x18)",
}
MUST_NOT = {"player_skip_18_off": ("玩家可進表的索引 <= 27", "兩處都不會讀到戰前章節表")}


def main() -> int:
    caught = 0
    for name, want in WANT.items():
        r = subprocess.run([sys.executable, str(HERE / "lc128_analyze.py"), name], capture_output=True, text=True, encoding="utf-8")
        tb = "Traceback (most recent" in r.stdout + r.stderr
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        if want is None:
            ok = r.returncode == 0 and last.startswith("PASS") and not tb
        else:
            ok = (r.returncode == 1 and last.startswith("FAIL") and want in last and not tb
                  and not any(x in last for x in MUST_NOT.get(name, ())))
        caught += ok
        print(f"{'符合預期' if ok else '不符預期'} {name}: rc={r.returncode} Traceback={tb} {last[:150]}")
    print(f"突變 {len(WANT)} 個,符合預期 {caught},不符預期 {len(WANT) - caught}")
    return 0 if caught == len(WANT) else 1


if __name__ == "__main__":
    sys.exit(main())
