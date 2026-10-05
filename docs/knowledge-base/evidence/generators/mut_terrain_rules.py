"""_terrain.py(地形修正規則)與兩個使用它的產生器的變異測試。

每條規則的變異至少要被一個產生器以 AssertionError 擋下:`ev_terrain_modifier` 以斷點讀值逐案比對(T1~T7),
`ev_attack_path_selection` 只有 M3 的 HP 實測對地形修正有鑑別力(AP 24 → +1),所以「跳過規則」類的變異
只在前者被擋下 —— 這正是後者證據裡 null 欄位只是規則套用、不是實測的原因。另外 M1~M3 出手與被打的單位
全都站在類型 0,所以「攻方修正改看守方的格子」這種變異在後者不可能被擋下(已試過:存活),不列入。變異版與輸出都在暫存目錄
(見 _mutrun.py),先跑未變異的對照。
"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

T = "_terrain.py"
MUTANTS_TERRAIN_MODIFIER = [
    ("種族 5 不跳過", "r[0x1F] in (4, 5)", "r[0x1F] in (4,)", T),
    ("+7 == 0x1C 的例外拿掉", "if r[7] == 0x1C:", "if False:", T),
    ("職業 0x13 不跳過", "return r[0x20] == 0x13 or ", "return ", T),
    ("百分比改取 floor", "return q if (a >= 0) == (b > 0) else -q", "return a // b", T),
    ("跳過規則不生效", "return None if gated(r) else tdiv", "return tdiv", T),
    ("地形表取 byte 0", "return tt[tile * 4 + 1]", "return tt[tile * 4]", T),
    ("地圖寬高對調", "w, h = map_size(cells)", "h, w = map_size(cells)", T),
]
MUTANTS_ATTACK_PATH = [
    ("一律跳過地形修正", "return None if gated(r) else tdiv", "return None if True else tdiv", T),
    ("攻方套 DP 修正表", "modifier(ap, AP_PCT, terr(a), ra)", "modifier(ap, DP_PCT, terr(a), ra)"),
    ("對照改成 M2 才有鑑別力", '(loss_no_terrain != measured) == (tag == "M3")', '(loss_no_terrain != measured) == (tag == "M2")'),
    ("印出的地形類型改比 (y, x)", "assert t == terrain_type(cells, tt, post[i * 80], post[i * 80 + 1])",
     "assert t == terrain_type(cells, tt, post[i * 80 + 1], post[i * 80])"),
]

if __name__ == "__main__":
    rc = run_mutants("ev_terrain_modifier", MUTANTS_TERRAIN_MODIFIER)
    rc |= run_mutants("ev_attack_path_selection", MUTANTS_ATTACK_PATH)
    sys.exit(rc)
