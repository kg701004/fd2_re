"""ev_lut_ch22_post_cycles2500_chapter_tables.py 的變異測試:每個變異改產生器或 lc127_analyze.py 裡一個判準 / 預測,
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。lc127_mut.py 是另一層(把紀錄改錯,要求分析判不符合),結果由產生器寫進證據。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

A = "lc127_analyze.py"
MUTANTS = [
    ("戰後表預期 0x244b6", 'check(g, "戰後表第 22 格 = 0x24754", A.HANDLER == 0x24754', 'check(g, "戰後表第 22 格 = 0x24754", A.HANDLER == 0x244B6', A),
    ("戰後表呼叫點索引戰前表", "(0x25E23, 0x1DE9)", "(0x25E23, 0x1D71)", A),
    ("dialog 14 之前預期 22", 'dlg is not None and dlg["g"]["chap"] == 23 and dlg["dialog_idx"] == 14,\n          f"chap',
     'dlg is not None and dlg["g"]["chap"] == 22 and dlg["dialog_idx"] == 14,\n          f"chap', A),
    ("lut #1 半徑少加", "want_r = [lut1[1] + lut1[2] * k for k in range(10)]", "want_r = [lut1[1] + (lut1[2] - 1) * k for k in range(10)]", A),
    ("倍數下限 2.7", "all(1.6 <= x / y <= 2.6 for x in a25 for y in a50)", "all(2.7 <= x / y <= 3.6 for x in a25 for y in a50)", A),
    ("回掃對照容許 9 tick", "rival = None not in a25 + a50 and all(abs(x - y) <= 1 for x in a25 for y in a50)",
     "rival = None not in a25 + a50 and all(abs(x - y) <= 9 for x in a25 for y in a50)", A),
    ("88 格少讀一格", "    for i in range(n_all):\n", "    for i in range(n_all - 1):\n"),
    ("指令表 30 格", 'tbl, ch = ("cmd", i) if i < n_cmd else (("pre", i - n_cmd)', 'tbl, ch = ("cmd", i) if i < n_cmd + 2 else (("pre", i - n_cmd - 2)'),
    ("表格不加 obj1 基底", 'return struct.unpack("<I", an127.A.sbytes(base + 4 * i, 4))[0] + 0x10000', 'return struct.unpack("<I", an127.A.sbytes(base + 4 * i, 4))[0]'),
    ("命令處理器名稱預期 59 格", 'startswith("command_handler_")) == 60', 'startswith("command_handler_")) == 59'),
    ("檢查數預期 22", "== (21, 2), a", "== (22, 2), a"),
    ("突變預期漏 1", '== "突變 20 個,抓到 20,漏掉 0"', '== "突變 20 個,抓到 19,漏掉 1"'),
    ("包裝腳本預期換成 5000", 'a="config -set cycles=2500"\' in out', 'a="config -set cycles=5000"\' in out'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_lut_ch22_post_cycles2500_chapter_tables", MUTANTS))
