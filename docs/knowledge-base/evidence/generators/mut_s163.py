"""ev_s163.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s163.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 原始紀錄
    ("表頭要有閘門", "\"icount=1\" in HDR and \"gate=\" not in HDR", "\"icount=1\" in HDR and \"gate=\" in HDR"),
    ("入口 18 個", "assert len(NATIVE) == 19", "assert len(NATIVE) == 18"),
    ("最後一行有換行", "and not _text.endswith(\"\\n\")", "and _text.endswith(\"\\n\")"),
    ("截斷的不是最後一筆", "UNTIMED[0] is REC[-1]", "UNTIMED[0] is REC[0]"),
    # (B) 中斷時間軸
    ("18.2 Hz 期判準 60 ms", "for x in _dt[:W0] if x > 20],", "for x in _dt[:W0] if x > 60],"),
    ("視窗從 MDI 起", "W0 = max(i for i, t in enumerate(ISR_T) if t <= DIG0)",
     "W0 = max(i for i, t in enumerate(ISR_T) if t <= MDI0)"),
    ("相位不置中", "round((t - T0 + P / 2) % P - P / 2, 2)", "round((t - T0) % P, 2)"),
    ("週期用 120 Hz", "P = DIVISOR / PIT_HZ * 1000 ", "P = DIVISOR * 5 / 3 / PIT_HZ * 1000 "),
    ("重入配對 0.0001 ms", "t - ISR_T[j] < 0.05", "t - ISR_T[j] < 0.0001"),
    ("晚到門檻 1.5 ms", "LATE_TH = 0.3", "LATE_TH = 1.5"),
    ("合併不算損失", "LOST = len(RE_T) + len(EMPTY)", "LOST = len(RE_T)"),
    ("tick 平均乘回去", "/ (1 - LOST / N_SLOTS), 2)", "* (1 - LOST / N_SLOTS), 2)"),
    # (C) 重入的成因
    ("回呼名稱對調", "\"+\".join(nm for a, nm in ((DIG, \"DIG\"), (MDI, \"MDI\"))",
     "\"+\".join(nm for a, nm in ((DIG, \"MDI\"), (MDI, \"DIG\"))"),
    ("回呼區間不看結束", "if any(s < t < e for s, e in SPANS[a])", "if any(s < t for s, e in SPANS[a])"),
    ("正常進入不扣重入", "if t >= ISR_T[W0]) - len(RE_T)", "if t >= ISR_T[W0])"),
    # (D) 校準
    ("計數改 dec", "\"inc esi\")", "\"dec esi\")"),
    ("edx 取成 eax", "EDX = int(CAL_R[\"f\"][1], 16)", "EDX = int(CAL_R[\"f\"][0], 16)"),
    ("每 tick 10.98 cs", "CS_PER_TICK = 100 / (PIT_HZ / 65536)", "CS_PER_TICK = 200 / (PIT_HZ / 65536)"),
    ("上一秒的邊界 -99", "if u - CS_PER_TICK * (m + 1) < -100 <=", "if u - CS_PER_TICK * (m + 1) < -99 <="),
    ("一秒算 18 tick", "COUNT_MS = round(max(TICKS_IN_SECOND) * TICK_MS, 2)", "COUNT_MS = round(18 * TICK_MS, 2)"),
    ("delay 每圈 5 條", "assert (di - 3) % 6 == 0, di", "assert (di - 3) % 5 == 0, di"),
    ("圈數公式不加 500", "math.ceil((1000 * it - 500) / ms)", "math.ceil((1000 * it) / ms)"),
    ("沒中斷的判斷反了", "if j < len(ISR_T) and ISR_T[j] < _iR[q][\"t\"]:", "if j < len(ISR_T) and ISR_T[j] > _iR[q][\"t\"]:"),
    # 預測判定
    ("P3 主要假說只看合併", "verdict(len(RE_T) == 0 and len(EMPTY) > 0)", "verdict(len(EMPTY) > 0)"),
    ("P3 替代假說門檻 0", "RE_PHASE.get(\"blink\", 0) > len(RE_T) / 2)", "RE_PHASE.get(\"blink\", 0) > 0)"),
    ("P2 門檻 0.95", "verdict(P2_SHARE >= 0.9)", "verdict(P2_SHARE >= 0.95)"),
    ("回呼三項全要求才 PARTIAL", "\"PARTIAL\" if any(_cb) else", "\"PARTIAL\" if all(_cb[:2]) and _cb[2] else"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s163", MUTANTS))
