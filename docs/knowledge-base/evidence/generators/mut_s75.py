"""ev_s75.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s75.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("逃逸點 = 第一次離開迴圈(第一次 IRQ 出差)", 'esc["escape"]["line"] == 7060958', 'esc["escape"]["line"] == 17635'),
    ("重置走關機碼 5 / 0A(EAX 0x2010000)", "assert all(a == b for a, b in lo_zero.values()), lo_zero",
     'assert escape["regs"]["EAX"] == 0x2010000'),
    ("重置框架少一個字(沒有 FLAGS)", "assert 0x9DB + 2 * 13 == 0x9F5", "assert 0x9DB + 2 * 12 == 0x9F5"),
    ("GDT base 在 0x170000", "GDT = 0x170180 - 0x170", "GDT = 0x170180 - 0x180"),
    ("IDT 也被寫到", "0x18A110 > 0x170657", "0x18A110 < 0x170657"),
    ("XMS 入口沒被改", 'xms_post[:8] == b"\\x4c" * 8', "xms_post[:8] == xms_pre[:8]"),
    ("blit 寫入不連續(每次 +2)", "assert prev is None or a == prev + 1", "assert prev is None or a == prev + 2"),
    ("完好標頭也洩漏(沒有 0x3d685)", '["0x3d67f", "0x3d685", "0x3d693", "0x3d72e", "0x111d5", writer]',
     '["0x3d67f", "0x111d5", writer]'),
    ("完好標頭時新調色盤配到別處", 'assert s[i + 6]["new_pal"] == s[0]["pal"]', 'assert s[i + 6]["new_pal"] != s[0]["pal"]'),
    ("v32 重現了 E_Exit", 'assert "Illegal Unhandled Interrupt Called 6" in pane and "E_Exit" not in pane',
     'assert "E_Exit" in pane'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s75", MUTANTS))
