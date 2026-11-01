"""ev_s181b.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s181b.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("標頭要有 segs", 'and " segs=" not in head, head', 'and " segs=" in head, head'),
    ("指紋取 lc181a 的給 lc181b", '"lc181b": "c676d94a047c56b78e275d1e6732f17d"', '"lc181b": "0dcee91e57df141a188fb805b407d469"'),
    ("寫出數小於區塊數", "assert all(by_rule[r] == tc[r][2] <= tc[r][1] for r in tc)", "assert all(by_rule[r] < tc[r][2] <= tc[r][1] for r in tc)"),
    ("規則 1 只容許 302", "t.count in (302, 303) for t in lg.trigs if t.rule == 1", "t.count in (302,) for t in lg.trigs if t.rule == 1"),
    ("MDI 型要有硬體中斷", "        if mdi:\n            assert not hw, (nm, t.seq, hw)", "        if mdi:\n            assert hw, (nm, t.seq, hw)"),
    ("回到點取 DIG 型 0x3f0be", "MDI_FROM, MDI_BACK = (0x80, 0xED6), 0x3F1A4", "MDI_FROM, MDI_BACK = (0x80, 0xED6), 0x3F0BE"),
    ("回到那一條取區間最後一條", "back = [x for x in t.insns if x.n == t.n1 + 1]", "back = [x for x in t.insns if x.n == t.n1]"),
    ("P1 判定反向", '"NOT TESTED" if N375 == 0 else "PASS"', '"PASS" if N375 == 0 else "NOT TESTED"'),
    ("預測檔的 TRIG 改寫", 'assert f"TRIG={TRIG}" in PRED.read_text', 'assert f"TRIG={TRIG},if:1-" in PRED.read_text'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s181b", MUTANTS))
