"""ev_s180b.py 的變異測試:每個變異改一個判準 / 推導,必須讓 ev_s180b.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 靜態前提
    ("typewriter 放的是 index 3", '["push 1", "push 2", "call 0x25a96"]', '["push 1", "push 3", "call 0x25a96"]'),
    ("單位索引在 [esp + 0x2c]", 'insn(0x3224E) == "push dword ptr [esp + 0x30]"', 'insn(0x3224E) == "push dword ptr [esp + 0x2c]"'),
    ("typewriter 呼叫端有 3 處", "assert len(TW_SITES) == 2 and", "assert len(TW_SITES) == 3 and"),
    # (W)
    ("包住的 dialog 可以有兩層", "assert len(enc) == 1, (nm", "assert len(enc) == 2, (nm"),
    ("字串索引取第 3 個參數", "idx = d.stack[1] ", "idx = d.stack[2] "),
    ("記錄上限當成 100", "CAP = 200 ", "CAP = 100 "),
    ("返回位址減 4", "assert {c.ret - DELTA - 5 for c in tws} <= TW_SITES", "assert {c.ret - DELTA - 4 for c in tws} <= TW_SITES"),
    ("歸不到的不必在最後一次返回之後", "assert len(dlg) == CAP and c.line > last", "assert len(dlg) == CAP and c.line < last"),
    ("全部都歸得到", "assert N_ATT == sum(TW.values()) and 0 < N_ATT < N_TW", "assert N_ATT == sum(TW.values()) and N_ATT == N_TW"),
    # (U)
    ("單位索引取暫存器 eax", "STEPS[(func_of(c.ret - DELTA), c.stack[0])] += 1", 'STEPS[(func_of(c.ret - DELTA), c.regs["eax"])] += 1'),
    ("單位索引上限 8", "all(0 <= u < 0x40 for _f, u in STEPS)", "all(0 <= u < 8 for _f, u in STEPS)"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s180b", MUTANTS))
