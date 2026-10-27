"""ev_s158.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s158.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 鏡頭與單位位置
    ("地形索引取 ecx", '"ebx": int(t[7], 16)', '"ebx": int(t[8], 16)'),
    ("欄取 edi", '"ebp": int(t[12], 16)', '"ebp": int(t[11], 16)'),
    ("只搜第 0 張地圖", "for _n in range(33):", "for _n in range(1):"),
    ("視窗 stride 400", "CELL, PITCH, UNIT_UP = 24, 0x1C8, 6", "CELL, PITCH, UNIT_UP = 24, 0x190, 6"),
    ("單位圖不上移", "CELL, PITCH, UNIT_UP = 24, 0x1C8, 6", "CELL, PITCH, UNIT_UP = 24, 0x1C8, 0"),
    ("裁切 x 下界 sx + 6", "return sx - 1 <= xy[0] <= sx + VIEW_W", "return sx + 6 <= xy[0] <= sx + VIEW_W"),
    ("armC #11 讀成 (y, x)", "assert ARMC_XY == {11: (19, 14), 5: (8, 7), 10: (6, 9)}", "assert ARMC_XY == {11: (14, 19), 5: (8, 7), 10: (6, 9)}"),
    ("第一輪範圍外改範圍內", "assert not any(OUT1.values()), OUT1", "assert all(OUT1.values()), OUT1"),
    # (B) 地形層指令數
    ("貼圖數 96", "assert len(bl) == 104", "assert len(bl) == 96"),
    ("核心視窗 0", "CORE, ISR_MIN = 10, 250", "CORE, ISR_MIN = 0, 250"),
    ("離群門檻 1000", "CORE, ISR_MIN = 10, 250", "CORE, ISR_MIN = 10, 1000"),
    ("預測差門檻反向", "assert P_C == P_D and P_E - P_C > 4000", "assert P_C == P_D and P_E - P_C < 4000"),
    ("貼圖以外的差 < 1", "assert abs(_other[\"lc157e\"] - _other[\"lc157c\"]) < 500, _other",
     "assert abs(_other[\"lc157e\"] - _other[\"lc157c\"]) < 1, _other"),
    # (C) BIOS tick
    ("格點 4.999", "GRID_MS = 5.0", "GRID_MS = 4.999"),
    ("掃描從 6 ms 起", "for k in range(1000, 20001)), reverse=True)", "for k in range(6000, 20001)), reverse=True)"),
    ("平均判準反向", "assert per_tick > TICK_MS + 0.3, (nm, per_tick)", "assert per_tick < TICK_MS + 0.3, (nm, per_tick)"),
    ("格點數只容許 10 .. 12", "assert set(m) <= {10, 11, 12, 13, 14}, (nm, Counter(m))", "assert set(m) <= {10, 11, 12}, (nm, Counter(m))"),
    ("相位視窗 0.1 ms", "near = sum(abs(x) <= 0.6 for x in off)", "near = sum(abs(x) <= 0.1 for x in off)"),
    ("µs 換算常數 8381", "f7e1f7f350e8a5ffffff83c4045f5e5bc9c3", "f7e1f7f350e8a5ffffff83c4045f5e5bc9c4"),
    ("ISR 重入保護改 jb", "2e833de62b0000000f8711010000", "2e833de62b0000000f8211010000"),
    # (D) 第 5 項第 4 次
    ("閘門位址 + 1", 'f"gate={0x22E5C + DELTA:08x}" in _h', 'f"gate={0x22E5D + DELTA:08x}" in _h'),
    ("索爾 HP 預期 999", "assert SOL_AFTER == (200, 999) and MP11 == 6", "assert SOL_AFTER == (999, 999) and MP11 == 6"),
    ("圓形平均原點錯", "_mu = math.atan2(_s, _c) / (2 * math.pi) * GRID_MS", "_mu = math.atan2(_s, _c) / (3 * math.pi) * GRID_MS"),
    ("#12 .. #16 預期有施法", "assert _mp_others == [0, 0, 0, 0, 0]", "assert _mp_others == [20, 15, 60, 42, 30]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s158", MUTANTS))
