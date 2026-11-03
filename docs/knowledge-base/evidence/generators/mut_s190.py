"""ev_s190.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s190.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 靜態
    ("0xb 週期 8", "== (6, 6, 4, 9, 0xA, 9, 0xB)", "== (6, 6, 4, 8, 0xA, 9, 0xB)"),
    ("週期 9 的職業少一個", "assert PERIOD9_CLASSES == [3, 11, 15, 19]", "assert PERIOD9_CLASSES == [3, 11, 15]"),
    ("職業表 28 位元組", '"mov ecx, ") + 1))', '"mov ecx, ") + 0))'),
    ("計數器另有寫入端", "0x322E1 + 3, 0x3230F + 2]", "0x322E1 + 3, 0x3230F + 2, 0x3230F + 3]"),
    ("計數器在實體頁內", '<= COUNTER, _OBJ', '> COUNTER, _OBJ'),
    # 模型
    ("row19 只認種族 4", "rec[0x1F] in (4, 5)):", "rec[0x1F] in (4,)):"),
    ("餘數 1 才放", "return ix if ctr % per == 0 else None", "return ix if ctr % per == 1 else None"),
    ("計數器每次 +2", "ctr[k] = (ctr[k] + 1) & 0xFF", "ctr[k] = (ctr[k] + 2) & 0xFF"),
    ("單位表取最早那張", "        return hit[-1]", "        return hit[0]"),
    # 紀錄讀法
    ("載入差錯一頁", "DELTA = 0x19C000", "DELTA = 0x19D000"),
    ("返回位址 +1", "STEP_PLAY_RET = 0x3230C", "STEP_PLAY_RET = 0x3230D"),
    ("優先度 2", "assert c.stack[2] == 1, (log, c.seq)", "assert c.stack[2] == 2, (log, c.seq)"),
    ("入口上限 600", "assert 0 < n_step < cap, (log, n_step, cap)", "assert 0 < n_step < 600, (log, n_step, cap)"),
    ("m06 傾印不同", '"339839c877922c1b20bdff23fb6d06c5"', '"339839c877922c1b20bdff23fb6d06c6"'),
    # 結論
    ("lc184a 起始值兩個", 'assert A["n_start_values_fitting"] == 1 and', 'assert A["n_start_values_fitting"] == 2 and'),
    ("對照有一個全中", "assert all(v > 0 for v in A[", "assert any(v == 0 for v in A["),
    ("0xb 7 次", 'assert A["plays"].get(hex(IX_G23)) == 6 and', 'assert A["plays"].get(hex(IX_G23)) == 7 and'),
    ("0xb 也有索爾", "== {(4, 3)}, PLAYS_0XB", "== {(4, 3), (0, 1)}, PLAYS_0XB"),
    ("0xb 只在第 32 張圖", "== [31, 32]", "== [32]"),
    ("角色 4 是鐵諾", 'assert CHAR_NAME["4"] == "亞雷斯"', 'assert CHAR_NAME["4"] == "鐵諾"'),
    ("lc184b 起始值唯一", 'assert B["n_start_values_fitting"] > 1 and', 'assert B["n_start_values_fitting"] == 1 and'),
    ("lc184b 也有 0xb", "and hex(IX_G23) not in B[\"plays\"]", "and hex(IX_G23) in B[\"plays\"]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s190", MUTANTS))
