"""ev_s130.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s130.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("表頭不是只列 5 個 EIP", '"entries=5 "', '"entries=1356 "'),
    ("重定位差值錯", "RELOC = 0x1EC000", "RELOC = 0x1EB000"),
    ("碼位元組不套重定位(自比)", 'v = int.from_bytes(fb[o:o + 4], "little") + RELOC', 'v = int.from_bytes(fb[o:o + 4], "little") + 0'),
    ("0x12132 少一個位移位置", "(2, 8)", "(2,)"),
    ("錄到兩個迴圈", "assert len(loops) == 1", "assert len(loops) == 2"),
    ("畫的階只能是 k", 'd in (f["k"], f["k"] + 1) for d, f in zip(drawn, loop)', 'd in (f["k"],) for d, f in zip(drawn, loop)'),
    ("推進門檻 > 1", "((t - last > 2) or (t < last))", "((t - last > 1) or (t < last))"),
    ("第 1 圈不取迴圈外的上次推進", "ok, last = last0 is not None, last0", "ok, last = True, None"),
    ("推進至少隔 3 圈", "b - a >= 2", "b - a >= 3"),
    ("每圈只有 1 tick", '1 <= f["tick_after"] - f["ticks"][0] <= 2', '1 <= f["tick_after"] - f["ticks"][0] <= 1'),
    ("對照 1 改用實測值", 'ctl_k = judge([f["k"] for f in loop])', "ctl_k = judge(drawn)"),
    ("對照 2 不錯開", "drawn[(i + 1) % 8]", "drawn[i]"),
    ("實測階最後一圈是 9", "assert drawn == [2, 2, 4, 4, 5, 7, 7, 8], drawn", "assert drawn == [2, 2, 4, 4, 5, 7, 7, 9], drawn"),
    ("推進在第 1、4、6 圈", 'assert [f["adv"] for f in loop] == [1, 0, 1, 0, 0, 1, 0, 0]',
     'assert [f["adv"] for f in loop] == [1, 0, 0, 1, 0, 1, 0, 0]'),
    ("與續一百二十三第一輪不同", "assert runs123[0] == drawn, runs123", "assert runs123[0] != drawn, runs123"),
    ("與續一百二十三第二輪相同", "assert runs123[1] != drawn, runs123", "assert runs123[1] == drawn, runs123"),
    ("迴圈外有不走 -1 分支的重畫", 'assert out_cnt["tick"] == out_cnt["draw"] > 0, out_cnt',
     'assert out_cnt["tick"] < out_cnt["draw"], out_cnt'),
    ("迴圈外的階只有 0..10", "assert sorted(draw_vals) == list(range(20))", "assert sorted(draw_vals) == list(range(11))"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s130", MUTANTS))
