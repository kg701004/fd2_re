"""ev_ai_physical_candidate.py 的變異測試:每個變異把 pa_analyze.py 的一條規則換成對照規則(或拿掉一步),
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

PA = "pa_analyze.py"
MUTANTS = [
    ("地形閘門與實戰同極性",
     'gate = uses_row19 if variant != "terrain_like_attack" else (lambda r: not uses_row19(r))',
     "gate = (lambda r: not uses_row19(r))", PA),
    ("0x1debe 取攻方", 'cg = counter_gate(units, actor if variant == "debe_actor" else tgt, x, y)',
     "cg = counter_gate(units, actor, x, y)", PA),
    ("×3/2 取 floor", 's = (s * 3) // 2 if variant == "floor_x15" else tdiv(s * 3, 2)', "s = (s * 3) // 2", PA),
    ("同分取後者", '(s >= bs if variant == "ties_last" else s > bs)', "(s >= bs)", PA),
    ("原始 <= 2 也給優先級 8", "pr = 8 if s > 2 else 0", "pr = 8", PA),
    ("擊殺不 ×2", "s, pr = s * 2, 0x12", "s, pr = s, 0x12", PA),
    # 判準本身:對照規則與重算完全相同時,「至少一組不同」的 assert 必須擋下
    ("floor 對照規則退化成與重算相同", 's = (s * 3) // 2 if variant == "floor_x15" else tdiv(s * 3, 2)',
     "s = tdiv(s * 3, 2)", PA),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_ai_physical_candidate", MUTANTS))
