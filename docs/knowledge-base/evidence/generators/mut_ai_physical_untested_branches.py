"""ev_ai_physical_untested_branches.py 的變異測試:每個變異把 tr_analyze.py 的一條規則換成對照規則,
或破壞產生器的一個判準,必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,
不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

TR = "tr_analyze.py"
MUTANTS = [
    ("地形 3..5 視為 0%", 'if variant == "terrain_ge3_zero" and ty >= 3:', "if ty >= 3:", TR),
    ("地形 3..5 當成地形 2", 'if variant == "terrain_ge3_as2" and ty >= 3:', "if ty >= 3:", TR),
    ("地形百分比取 floor", 'fl = variant == "terrain_floor"', "fl = True", TR),
    ("0x1debe 不看武器列 +0xb", 'if item_row(wpn)[0xB] > 1 and variant != "debe_ignores_b":', "if False:", TR),
    ("0x1debe 無武器也通過", 'return 1 if variant == "debe_unarmed_passes" else -1', "return 1", TR),
    ("射程 byte >= 0x10 當曼哈頓", 'if mode < 0x10 or variant == "cross_as_manhattan":', "if True:", TR),
    ("十字分支也套內圈排除", 'if variant == "cross_with_inner":', "if True:", TR),
    ("擊殺不 ×2", "s, pr = s * 2, 0x12", "s, pr = s, 0x12", TR),
    # 成本列 JSON 讀目前(已修正)的版本:note 的「當時 JSON 錯一個 byte」必須擋下
    ("成本列 JSON 讀工作樹而非當時的 blob",
     'JSON_ROWS = json.loads(git_blob(COST_ROWS_BLOB, COST_ROWS_JSON).decode("utf-8"))',
     'JSON_ROWS = json.load(open(ROOT_S + "/" + COST_ROWS_JSON, encoding="utf-8"))', TR),
    # 產生器本身的判準
    ("活地圖改比 FDFIELD_006", '"<H", open(ROOT + "/extracted/raw/FDFIELD/FDFIELD_003.bin"',
     '"<H", open(ROOT + "/extracted/raw/FDFIELD/FDFIELD_006.bin"'),
    ("成本列比對錯位一個 byte", "meta, 0x61646, len(cost_live)", "meta, 0x61647, len(cost_live)"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_ai_physical_untested_branches", MUTANTS))
