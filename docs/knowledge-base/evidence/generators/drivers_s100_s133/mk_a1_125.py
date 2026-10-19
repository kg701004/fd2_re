# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十五:round A 的錄製腳本在第一條台詞後當掉,沒有寫出 a1.json。把它印在 stdout 的每一站(Python dict 字面值)轉成 a1.json。

印出的內容本來就略過了 units / codes / row 三個欄位,所以 a1.json 也沒有;這一點寫進檔案的 source 欄位。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
src = HERE / "lc125_rec_a1_part1.txt"
stops = []
for ln in src.read_text(encoding="utf-8").splitlines():
    if ln.startswith("{'at'"):
        stops.append(ast.literal_eval(ln))
out = {"tag": "a1", "source": "lc125_rec_a1_part1.txt 的 stdout(錄製腳本在 0x1ac2b 之後執行中傾印 VGA 失敗而結束;"
                              "印出時略過 units / codes / row 欄位)", "stops": stops}
dst = HERE / "cl" / "lc125_live" / "a1.json"
assert not dst.exists()
dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(len(stops), [s["at"] for s in stops])
