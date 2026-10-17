"""ev_s132.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s132.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("wait_ticks 位元組改一個", '"8b542404b86c0400000fbf00a32c3a0000', '"8b542408b86c0400000fbf00a32c3a0000'),
    ("HUD 起始列 0x9e", "HUD_ROW, HUD_DY, HUD_DX = 0x9D, 5, 6", "HUD_ROW, HUD_DY, HUD_DX = 0x9E, 5, 6"),
    ("HUD 橫向 +8", "HUD_ROW, HUD_DY, HUD_DX = 0x9D, 5, 6", "HUD_ROW, HUD_DY, HUD_DX = 0x9D, 5, 8"),
    ("[0x51a0c] 預期 0xf2", "assert HUD_X0 == 1, HUD_X0", "assert HUD_X0 == 0xF2, HUD_X0"),
    ("推進門檻 > 1", "if ((t - last > 2) or (t < last))", "if ((t - last > 1) or (t < last))"),
    ("對照『畫的是 k』拿實測", 'ctl_k = judge(loop, c["last0"], [f["k"] for f in loop])', 'ctl_k = judge(loop, c["last0"], drawn)'),
    ("舊查詢預期數到 8", '{"old_pattern_1b12a0": 0, "padded_001b12a0": 8}', '{"old_pattern_1b12a0": 8, "padded_001b12a0": 8}'),
    ("第二輪預期等於第一輪", 'assert runs["lc131b"]["drawn"] == runs["lc131d"]["drawn"] == RUN_B',
     'assert runs["lc131b"]["drawn"] == runs["lc131d"]["drawn"] == RUN_A'),
    ("lc131a 預期同第二輪", "assert runs[\"lc131a\"][\"drawn\"] == [1, 3, 3, 5, 5, 6, 8, 8]",
     "assert runs[\"lc131a\"][\"drawn\"] == RUN_B"),
    ("斷點對照反向", "assert all(runs[n][\"drawn\"] != RUN_A for n in LOGS)", "assert any(runs[n][\"drawn\"] == RUN_A for n in LOGS)"),
    ("兩圈至少 4 tick", 'assert all(min(two[n]) >= 3 for n in ("lc131b", "lc131d")), two',
     'assert all(min(two[n]) >= 4 for n in ("lc131b", "lc131d")), two'),
    ("第一輪也要兩圈 3 tick", 'assert min(two["lc130a"]) < 3, two', 'assert min(two["lc130a"]) >= 3, two'),
    ("跨 tick 不減 1", 'return [f["tick_after"] - 1 - f["ticks"][0] for f in loop]', 'return [f["tick_after"] - f["ticks"][0] for f in loop]'),
    ("迴圈前一般畫面預期 2 tick", "== [1] * 7 for r in runs.values()", "== [2] * 7 for r in runs.values()"),
    ("(10, 20) 預期 54 像素", 'assert h["in_cell_10_20"] == 53, h', 'assert h["in_cell_10_20"] == 54, h'),
    ("差異塊列預期從 163 起", "and (y0, y1) == (icon[2], icon[3]), (h, icon)", "and (y0, y1) == (icon[2] + 1, icon[3]), (h, icon)"),
    ("容許框外差異 1 個", 'assert h["band_outside_icon"] == 0, h', 'assert h["band_outside_icon"] == 1, h'),
    ("單位圖對照位移 ±8", 'assert not (vx - 4 <= hud["D-F"]["bbox"][0] and hud["D-F"]["bbox"][1] <= vx + CELL - 1 + 4), cx',
     'assert not (vx - 8 <= hud["D-F"]["bbox"][0] and hud["D-F"]["bbox"][1] <= vx + CELL - 1 + 8), cx'),
    ("D-E 預期有差異", 'assert hud["D-E"] == {"in_cell_10_20": 0,', 'assert hud["D-E"] != {"in_cell_10_20": 0,'),
    ("(10, 20) 預期有單位", 'assert (9, 20) not in pos and (10, 20) not in pos', 'assert (9, 20) in pos or (10, 20) in pos'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s132", MUTANTS))
