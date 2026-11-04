"""ev_s191f.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s191f.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 文件預測
    ("§1 少一句對白", '("txt", 8), ("act", 0x61), ("txt", 9), ("act", 0x62)]', '("txt", 8), ("act", 0x61), ("act", 0x62)]'),
    ("索爾出場 (20,46)", "DOC_ROSTER = {0: (0, 19, 46, 1)", "DOC_ROSTER = {0: (0, 20, 46, 1)"),
    ("0x62 亞雷斯起點照文件", '"doc": [9, 44], "model": [8, 45]}]', '"doc": [9, 44], "model": [9, 44]}]'),
    # 模型
    ("每格 5 次 step", "            for j in range(1, 7):", "            for j in range(1, 6):"),
    ("左右方向互換", "DIRS = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}", "DIRS = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}"),
    ("special frame 也走格", '        if fr.get("special"):\n            for s, p in units:\n                st[s][2] = p\n            cur.append(copy.deepcopy(st))\n            continue\n', ""),
    ("step 參數取最後一個 slot", "                args.append(units[0][0])", "                args.append(units[-1][0])"),
    # 紀錄讀法
    ("載入差錯一頁", "DELTA = 0x19C000", "DELTA = 0x19D000"),
    ("step 返回位址 +1", "STEP_RET_IN_ACT = 0x13923 ", "STEP_RET_IN_ACT = 0x13924 "),
    # 判準
    ("step 次數 6 × beats + 1", "assert all(STEP_COUNTS[k] == 6 * NORMAL_BEATS[k] for k in STEP_COUNTS)",
     "assert all(STEP_COUNTS[k] == 6 * NORMAL_BEATS[k] + 1 for k in STEP_COUNTS)"),
    ("0x60 有走", "[36, 12, 6, 48, 6, 6, 0, 12, 54]", "[36, 12, 6, 48, 6, 6, 6, 12, 54]"),
    ("容許 1 筆不一致", 'assert VERDICTS["MISMATCH"] == 0 and', 'assert VERDICTS["MISMATCH"] == 1 and'),
    ("對照有一個不鑑別", "assert all(v > 0 for v in NULLS.values()), NULLS", "assert any(v == 0 for v in NULLS.values()), NULLS"),
    ("間隔傾印是 (9,44)", "assert GAP and all(p == [8, 45] for p in GAP)", "assert GAP and all(p == [9, 44] for p in GAP)"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s191f", MUTANTS))
