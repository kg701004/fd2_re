"""ev_s158.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s158.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 鏡頭與單位位置
    ("地形索引取 ecx", '"ebx": c.regs["ebx"]', '"ebx": c.regs["ecx"]'),
    ("欄取 edi", '"ebp": c.regs["ebp"]', '"ebp": c.regs["edi"]'),
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
    ("掃描從 6 ms 起", "SCAN_LO, SCAN_HI = 1000, 20000", "SCAN_LO, SCAN_HI = 6000, 20000"),
    ("平均判準反向", "assert per_tick > TICK_MS + 0.3, (nm, per_tick)", "assert per_tick < TICK_MS + 0.3, (nm, per_tick)"),
    ("格點數只容許 10 .. 12", "assert set(m) <= {10, 11, 12, 13, 14}, (nm, Counter(m))", "assert set(m) <= {10, 11, 12}, (nm, Counter(m))"),
    ("相位視窗取第 ⌈0.85 n⌉ − 1 個", "* len(OFFS[nm])) - 1] for nm in RUNS}", "* len(OFFS[nm])) - 2] for nm in RUNS}"),
    ("相位視窗三份取最小", "PHASE_WIN = max(_kth.values())", "PHASE_WIN = min(_kth.values())"),
    ("最小視窗前提用 ≤", "assert sum(abs(x) < PHASE_WIN for x in OFFS[nm])", "assert sum(abs(x) <= PHASE_WIN for x in OFFS[nm])"),
    ("非諧波判斷反向", "if not any(abs(p - h) < 1e-9 for h in HARMONICS)", "if any(abs(p - h) < 1e-9 for h in HARMONICS)"),
    ("諧波段長度 + 1", "and top == len(HARMONICS), (nm", "and top == len(HARMONICS) + 1, (nm"),
    ("第一個非諧波取諧波段最後一個", "nh_r, nh_p = scan[top]", "nh_r, nh_p = scan[top - 1]"),
    ("最遠偏移上限 1/4 格", "assert _far < GRID_MS / 2, _far", "assert _far < GRID_MS / 4, _far"),
    ("µs 換算常數 8381", "f7e1f7f350e8a5ffffff83c4045f5e5bc9c3", "f7e1f7f350e8a5ffffff83c4045f5e5bc9c4"),
    ("ISR 重入保護改 jb", "2e833de62b0000000f8711010000", "2e833de62b0000000f8211010000"),
    # (D) 第 5 項第 4 次
    ("閘門位址 + 1", 'f"gate={0x22E5C + DELTA:08x}" in _h', 'f"gate={0x22E5D + DELTA:08x}" in _h'),
    ("索爾 HP 預期 999", "assert SOL_AFTER == (200, 999) and MP11 == 6", "assert SOL_AFTER == (999, 999) and MP11 == 6"),
    ("圓形平均原點錯", "_mu = math.atan2(_s, _c) / (2 * math.pi) * GRID_MS", "_mu = math.atan2(_s, _c) / (3 * math.pi) * GRID_MS"),
    ("#12 .. #16 預期有施法", "assert _mp_others == [0, 0, 0, 0, 0]", "assert _mp_others == [20, 15, 60, 42, 30]"),
    # 續一百七十九:E / R 改由 calllog_segments 解析
    ("E / R 的 i / n 對調", 'return {} if ic is None else {k: float(v) for k, v in zip("int", ic)}',
     'return {} if ic is None else {k: float(v) for k, v in zip("nit", ic)}'),
    ("E / R 的 i / t 對調",'return {} if ic is None else {k: float(v) for k, v in zip("int", ic)}',
     'return {} if ic is None else {k: float(v) for k, v in zip("tni", ic)}'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s158", MUTANTS))
