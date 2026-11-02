"""ev_s184.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s184.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # Q1 當下單位表
    ("單位表指標偏一位元組", "gb[PTR_UNITS - GLOBALS_LIN:PTR_UNITS - GLOBALS_LIN + 4]",
     "gb[PTR_UNITS - GLOBALS_LIN + 1:PTR_UNITS - GLOBALS_LIN + 5]"),
    ("單位數取前一位元組", "gb[CNT_UNITS - GLOBALS_LIN]", "gb[CNT_UNITS - GLOBALS_LIN - 1]"),
    ("記錄序號不扣己方出場數", "assert p7 == p8 == rec_b1(m, i - own), (log, m, i, p7, p8, rec_b1(m, i - own))",
     "assert p7 == p8 == rec_b1(m, i), (log, m, i, p7, p8, rec_b1(m, i))"),
    ("+8 取 +9", "    return r[6], r[7], r[8]", "    return r[6], r[7], r[9]"),
    # Q1 面板
    ("面板子函式基底差一格", "bases = {v - STRIDE * cur for v in inner}", "bases = {v - STRIDE * (cur + 1) for v in inner}"),
    ("面板單位取第 2 個參數", "UNIT_ARG = 2 ", "UNIT_ARG = 1 "),
    ("空字串集合混入索爾的字串(正對照)", 'BLANK_S2 = {x["name_string"] for x in BLANK_UNITS}',
     'BLANK_S2 = {x["name_string"] for x in BLANK_UNITS} | {1}'),
    ("記錄上限記成 200", "CAP = 3000", "CAP = 200"),
    # Q2
    ("375 的中斷換成 IRQ 5", '[(0x0F, 0, "r", 0x0C5C, 0x1FAD)]', '[(0x0D, 0, "r", 0x0C5C, 0x1FAD)]'),
    ("375 驅動條數多 1", "len(drv) == 375 - 302", "len(drv) == 375 - 301"),
    ("MDI 型要有硬體中斷", "        if mdi:\n            assert not hw, (nm, t.seq, hw)", "        if mdi:\n            assert hw, (nm, t.seq, hw)"),
    ("P2 判定反向", '"NOT TESTED" if N375 == 0 else "PASS"', '"PASS" if N375 == 0 else "NOT TESTED"'),
    # Q3
    ("返回位址不加 5", 'R_RING = {x["func"]: int(x["call"], 16) + 5 for x in _CTX["8"]}',
     'R_RING = {x["func"]: int(x["call"], 16) for x in _CTX["8"]}'),
    ("沒有法術也算換頁", '[R_CLOSE] * len(S181["panel"]["close_frames"])', '[R_SWAP] + [R_CLOSE] * len(S181["panel"]["close_frames"])'),
    ("收起少一格", '[R_CLOSE] * len(S181["panel"]["close_frames"])', '[R_CLOSE] * (len(S181["panel"]["close_frames"]) - 1)'),
    ("前一鍵當 Escape", "KEY_RETURN = 0x1C", "KEY_RETURN = 0x01"),
    ("按鍵含放開碼", "ks = [k for k in lg.keys if k.line < line and k.data < 0x80]", "ks = [k for k in lg.keys if k.line < line]"),
    ("寶箱算進對話框的打字音", "for q in plays if lo < q.line < hi and func_of(q.ret - DELTA) == c.eip - DELTA]",
     "for q in plays if lo < q.line < hi]"),
    ("yes_no 回 0 才算", "lg.rets[yn[0].seq].eax == 1", "lg.rets[yn[0].seq].eax == 0"),
    ("盜賊卡要有法術", "assert _r[6] == 0 and not any(_r[0x1A:0x1F])", "assert _r[6] == 0 and any(_r[0x1A:0x1F])"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s184", MUTANTS))
