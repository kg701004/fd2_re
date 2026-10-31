"""ev_s175.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s175.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) DIG 服務填緩衝
    ("填緩衝的路徑改成短出口", "0x4066C} <= seen and 0x40534 not in seen", "0x40534} <= seen and 0x4066C not in seen"),
    ("清緩衝條數上限改 540", "and 500 < p[\"0x49923\"] < 600 for p in _pf)", "and 500 < p[\"0x49923\"] < 540 for p in _pf)"),
    ("緩衝號 xor 的位移錯一", "DIG_FILE[0x716:0x71B] == bytes.fromhex(\"8336040501\")", "DIG_FILE[0x717:0x71C] == bytes.fromhex(\"8336040501\")"),
    ("填緩衝門檻改 20000", "        fill = b[\"g\"] is None or b[\"g\"] > 1000\n", "        fill = b[\"g\"] is None or b[\"g\"] > 20000\n"),
    ("數 IRQ 0 而不是 IRQ 7", "q7 = [q.n for q in LOG[nm].irqs if q.num == 0x0F and q.type == 0]",
     "q7 = [q.n for q in LOG[nm].irqs if q.num == 0x08 and q.type == 0]"),
    ("沒 IRQ 也填的只認 0xd4", "all({\"0xc6\", \"0xd4\"} & set(o[\"dsp\"]) for o in odd_fill)", "all({\"0xd4\"} & set(o[\"dsp\"]) for o in odd_fill)"),
    ("有 IRQ 不填的認 0xd4", "all(\"0xd0\" in o[\"dsp\"] for o in odd_irq)", "all(\"0xd4\" in o[\"dsp\"] for o in odd_irq)"),
    ("看到 SEGS 窗外", "if not T_AFTER_INIT <= b[\"t\"] < T_SEGS_END:", "if not T_AFTER_INIT <= b[\"t\"]:"),
    # (B) 短驅動呼叫 = 硬體中斷
    ("IRQ 1 只容許 532", "assert set(k9) <= {532, 533} and", "assert set(k9) <= {532} and"),
    ("IRQ 7 最常見改 559", "max(kf, key=kf.get) == 558 and", "max(kf, key=kf.get) == 559 and"),
    ("看下下一次 DIG 服務", "d = DIG167[bisect.bisect_left(_dn, s[\"n\"])]", "d = DIG167[bisect.bisect_left(_dn, s[\"n\"]) + 1]"),
    ("填緩衝基準比例上限改 0.02", "assert BASE_RATE < 0.05, BASE_RATE", "assert BASE_RATE < 0.02, BASE_RATE"),
    # (C) 敵方回合結束停一次的服務
    ("提早返回改 14 條", "SKIP = [s for s in MDI167 if s[\"g\"] == 12]", "SKIP = [s for s in MDI167 if s[\"g\"] == 14]"),
    ("淡出時間改 2000 ms", "MS = 0xFA0\n", "MS = 0x7D0\n"),
    ("音量差改 126", "and REGS[\"ecx\"] == 127 and", "and REGS[\"ecx\"] == 126 and"),
    ("取更早一次 ISR", "and r[5] < SK[\"n\"]][-1]", "and r[5] < SK[\"n\"]][-2]"),
    ("敵方回合返回窗改 0.05 ms", "assert 0 < _isr[6] - _ep[6] < 0.2", "assert 0 < _isr[6] - _ep[6] < 0.05"),
    # 解讀層:結論文字
    ("結論的條數拿時刻", "只跑 {SK['g']} 條遊戲指令", "只跑 {SKIP_ROW['game_insn_hist_low']} 條遊戲指令"),
    ("結論的例外數拿表格", "例外各 {ODD_N['lc174a'][0]} + {ODD_N['lc174a'][1]} 次", "例外各 {FILL['lc174a']['table']['fill irq7=1']} + {ODD_N['lc174a'][1]} 次"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s175", MUTANTS))
