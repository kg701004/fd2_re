"""ev_s191.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s191.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 靜態
    ("只有左步到共用尾端", '"inc dword ptr [0x3ab1]", "jmp 0x1314f", "dec dword ptr [0x3ab1]"]',
     '"inc dword ptr [0x3ab1]", "jmp 0x13167", "dec dword ptr [0x3ab1]"]'),
    ("返回位址 +1", "assert STEP_TAIL_RET == 0x13175 + 5", "assert STEP_TAIL_RET == 0x13175 + 6"),
    ("event63 第一輪 (3,26)", "== ((3, 27, 1), (15, 27, 2)), (STAGE1, STAGE2)", "== ((3, 26, 1), (15, 27, 2)), (STAGE1, STAGE2)"),
    ("延遲 300 / 200 / 300", "assert (D_SPAWN, D_WHITE, D_TAIL) == (300, 200, 400)", "assert (D_SPAWN, D_WHITE, D_TAIL) == (300, 200, 300)"),
    ("觸發列 y = 38", "EV62_CELLS == [(x, 39) for x in range(W)]", "EV62_CELLS == [(x, 38) for x in range(W)]"),
    ("寶箱格也算格子事件", "    if slot == 1 and TERR[(tile & 0x3FF) * 4] & 0x60 == 0:", "    if slot == 1:"),
    # (B) lc191a
    ("每步參數用舊座標", "    pos = (pos[0] + DIR[d][0], pos[1] + DIR[d][1])\n    assert",
     "    assert"),
    ("上下語意互換", '"down": (0, 1), "left": (-1, 0), "up": (0, -1)', '"down": (0, -1), "left": (-1, 0), "up": (0, 1)'),
    ("有向左步", '"down": 0, "left": 0, "up": 16, "right": 12}', '"down": 0, "left": 1, "up": 16, "right": 11}'),
    ("y = 39 走過兩格", "assert [p for p in walk if p[1] == 39] == [(26, 39)]", "assert [p for p in walk if p[1] == 39] == [(25, 39), (26, 39)]"),
    ("event62 前 row0 已是 2", '(("s01", 0, 0xFF), ("s02", 1, 2))', '(("s01", 0, 2), ("s02", 1, 2))'),
    ("第 1 回合就有 event63", "[p[\"ev63_inside\"] for p in phases[:2]] == [False, True]", "[p[\"ev63_inside\"] for p in phases[:2]] == [True, True]"),
    ("event63 參數 1", "assert rt(E63) == 0x1A85A + 7 and E63.stack[0] == 0", "assert rt(E63) == 0x1A85A + 7 and E63.stack[0] == 1"),
    ("白閃後恢復成 255", "(PALETTE, 0x35BDC, (0, 0xFF, 0)),", "(PALETTE, 0x35BDC, (0, 0xFF, 0xFF)),"),
    ("沒有尾端 400 ms", "               (DELAY, 0x3572C, (D_TAIL,))]", "               ]"),
    ("容許 10 ms", "TOL_MS = 60 ", "TOL_MS = 10 "),
    ("單位數 63 → 69", "assert (S04[\"round\"], S04[\"unit_count\"], S06[\"unit_count\"]) == (2, 63, 75)",
     "assert (S04[\"round\"], S04[\"unit_count\"], S06[\"unit_count\"]) == (2, 63, 69)"),
    ("出場在鏡頭座標", "assert (3, 27) not in SPAWN_XY.values()", "assert (3, 27) in SPAWN_XY.values()"),
    # (C) town gate
    ("ch03 是 Ctrl+F1", "assert ROW(2)[1:] == bytes([1, 0x5F])", "assert ROW(2)[1:] == bytes([1, 0x5E])"),
    ("ctrl+F2 有 F2", "0x4B, 0x1D, 0x1D, 0x3C, 0x1D], [hex(x) for x in MB]", "0x4B, 0x1D, 0x3C, 0x1D, 0x1D, 0x3C, 0x1D], [hex(x) for x in MB]"),
    ("ctrl+F2 後 sel 5", "(2, 0x4B, 1), (2, 0x4B, 1), (2, 0x4B, 1), (2, 0x3C, 1)", "(2, 0x4B, 1), (2, 0x5F, 5), (2, 0x4B, 1), (2, 0x3C, 1)"),
    ("mapper 版有 K", "assert LC.keys == [] and", "assert LC.keys != [] and"),
    ("注入後 sel 不變", "[(2, 0x4B, 1), (2, 0x5F, 5), (2, 0x62, 5)]", "[(2, 0x4B, 1), (2, 0x5F, 1), (2, 0x62, 5)]"),
    ("ch06 sel 0 也揭示", "(5, 0x1C, 0), (5, 0x62, 0), (5, 0x4D, 4), (5, 0x62, 5)]", "(5, 0x1C, 0), (5, 0x62, 5), (5, 0x4D, 4), (5, 0x62, 5)]"),
    ("揭示後標籤是武器店", 'label_box("lc191d", "d04_after_inject") == ["0x1f4"]', 'label_box("lc191d", "d04_after_inject") == ["0x1f0"]'),
    ("呼叫紀錄 md5 錯", '"lc191a": "f5e060d46ba0598d6912c7472eb8fc82"', '"lc191a": "f5e060d46ba0598d6912c7472eb8fc83"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s191", MUTANTS))
