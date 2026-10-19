"""ev_dispatch_index_bounds_table_split.py 的變異測試:每個變異改產生器或 lc128_analyze.py 裡一個判準 / 預測,
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。lc128_mut_image.py / lc128_mut_tool.py 是另一層,結果由產生器寫進證據。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

A = "lc128_analyze.py"
MUTANTS = [
    ("指令表預期 30 格", 'check("指令表(第一段)28 格", cmd_len == 28,', 'check("指令表(第一段)28 格", cmd_len == 30,', A),
    ("玩家上限放寬到 28", 'check("玩家可進表的索引 <= 27", shape and (max(player, default=-1) <= 27),',
     'check("玩家可進表的索引 <= 27", shape and (max(player, default=-1) <= 26),', A),
    ("玩家不排除 0x18", "player = set() if skip_all else {i for i in range(N_SPELLS) if lo <= i <= hi and i != x}",
     "player = set() if skip_all else {i for i in range(N_SPELLS) if lo <= i <= hi}", A),
    # 「AI 不算 0x1a」是等價突變:0x1a = 26 在玩家那一側本來就進得了表,上限與「到不了的只有 24」都不變(續一百三十四曾列入,存活)。
    ("AI 可得分範圍多兩格", "scored = set(range(0, imms[0x15D30] + 1)) | {imms[0x15D71], imms[0x15D7E]}",
     "scored = set(range(0, imms[0x15D30] + 3)) | {imms[0x15D71], imms[0x15D7E]}", A),
    ("寫入端預期 0x15b13", 'writers == ["0x15b12"]', 'writers == ["0x15b13"]', A),
    ("到不了的預期 23", "check(\"兩處都到不了的格只有 24(0x18)\", unreached == [24],", "check(\"兩處都到不了的格只有 24(0x18)\", unreached == [23],", A),
    ("對照用 28 個 bit", "N_SPELLS = 40 ", "N_SPELLS = 28 ", A),
    ("預測預期 8 項", "== [True] * 9 and", "== [True] * 8 and"),
    ("手寫最大索引 26", '"max_index": 27, "command_table_len": 28,', '"max_index": 26, "command_table_len": 28,'),
    ("手寫到不了 [16]", '"unreached_by_both": [24],', '"unreached_by_both": [16],'),
    ("工具突變預期漏 1", '"突變 13 個,抓到 13,漏掉 0")', '"突變 13 個,抓到 12,漏掉 1")'),
    ("分段預期戰後表 28 格", '("0x51d71", 30), ("0x51de9", 30)]', '("0x51d71", 30), ("0x51de9", 28)]'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_dispatch_index_bounds_table_split", MUTANTS))
