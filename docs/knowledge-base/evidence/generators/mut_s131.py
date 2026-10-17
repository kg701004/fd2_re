"""ev_s131.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s131.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("停點不是 draw_terrain_layer 入口", "DTL = 0x11EEE", "DTL = 0x11EEF"),
    ("格子原點錯一列", "ORIGIN, STRIDE, CELL = 0x8088, 456, 24", "ORIGIN, STRIDE, CELL = 0x8088 + 456, 456, 24"),
    ("斷點清單不檢查空", 'assert tail[-3:-1] == ["Breakpoint list:", "-" * 73], (t, tail)',
     'assert tail[-3:-1] == ["Breakpoint list:"], (t, tail)'),
    ("索爾 MV 預期 30", "(20, 14, 3, 0)", "(20, 14, 30, 0)"),
    ("菱形半徑 4", "if abs(x - 20) + abs(y - 14) <= 3}", "if abs(x - 20) + abs(y - 14) <= 4}"),
    ("不扣我方單位格", "assert marks == {k: v for k, v in diamond.items() if k not in allies}", "assert marks == diamond"),
    ("扣除的我方格預期空", "assert blocked == {(22, 13), (23, 14)}, blocked", "assert blocked == set(), blocked"),
    ("換色表位移 0x76", "assert off == 0x66 + lv * 0x100", "assert off == 0x76 + lv * 0x100"),
    ("解釋用同一張表", "ra, rb = tables[la], tables[lb]", "ra, rb = tables[la], tables[la]"),
    ("標記格只要一半變動", 'c["marked_changed"] == c["marked"]', 'c["marked_changed"] == c["marked"] // 2'),
    ("不貼單位的格不必不變", "c[\"plain\"] > 0 and not c[\"plain_changed_not_near8\"]",
     "c[\"plain\"] > 0 and not [r for r in c[\"plain_changed\"]]"),
    ("錯位對照改成 0", "for s in (-1, 1)}", "for s in (0,)}"),
    ("錯階對照包含真階", "for lv in range(11) if lv != c[\"levels\"][1]}", "for lv in range(11)}"),
    ("實測階對調", "== [[8, 4], [8, 0], [4, 0]]", "== [[8, 0], [8, 4], [4, 0]]"),
    ("D-E 預期有沒標記格變動", 'assert pairs["D-E"]["compare"]["plain_changed"] == []',
     'assert pairs["D-E"]["compare"]["plain_changed"] != []'),
    ("(10, 20) 預期 54 像素", "== [[10, 20, 53]]", "== [[10, 20, 54]]"),
    ("可見標記格預期 21", 'pairs[k]["compare"]["marked"] == 17', 'pairs[k]["compare"]["marked"] == 21'),
    ("三角表預期 0..10 不回頭", "list(range(11)) + list(range(9, 0, -1))", "list(range(20))"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s131", MUTANTS))
