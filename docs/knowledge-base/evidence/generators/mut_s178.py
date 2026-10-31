"""ev_s178.py 的變異測試:每個變異改一個判準 / 預測 / 解讀,必須讓 ev_s178.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (D1) 靜態字序
    ("DPMI 結構 ebx / edx 對調", '0x10: "ebx", 0x14: "edx"', '0x10: "edx", 0x14: "ebx"'),
    ("DPMI 結構 ecx / eax 對調", '0x18: "ecx", 0x1C: "eax"', '0x18: "eax", 0x1C: "ecx"'),
    ("字 0 讀成字 1", '("off4", 0x40D7E, "dx")', '("off4", 0x40D9B, "ax")'),
    ("派送少讀回一格", "for a in (0x1CA, 0x1CD, 0x1D1, 0x1D5)", "for a in (0x1CA, 0x1CD, 0x1D1)"),
    ("[drv+0x34] 由 [drv+4] 那組加", "OFF34 = OFF8 + PLUS34", "OFF34 = OFF4 + PLUS34"),
    ("功能 0x300 不經 0x1ff", "INIT_W = writes([0x1FF, 0x205, 0x209]) | ", "INIT_W = writes([0x205, 0x209]) | "),
    # (D) 紀錄
    ("映像段錯一", "seg, _rem = divmod(img, 1 << SEG_SHIFT)", "seg, _rem = divmod(img + 0x10, 1 << SEG_SHIFT)"),
    ("之前 / 之後對調", 'when = "before" if c.line < l0 else ("after" if c.line > l1 else None)',
     'when = "after" if c.line < l0 else ("before" if c.line > l1 else None)'),
    ("初始化取 MDI 那一次", "c.eip == rt(DRVCALL) and c.stack[0] == d0]", "c.eip == rt(DRVCALL) and c.stack[0] != d0]"),
    ("初始化取 0x301", "init = [c for c in digcalls if c.stack[1] == INIT_FN]", "init = [c for c in digcalls if c.stack[1] == INIT_FN + 1]"),
    ("部分緩衝少算一個", 'row["kinds"]["partial"]\n', 'row["kinds"]["partial"] - 1\n'),
    ("之前不准有剛配置的 0xcc", "set(cnt) <= {filew, FRESH}", "set(cnt) <= {filew}"),
    ("[drv+0x34] 不加 8", 'assert r["d34"] == r["d8"] + PLUS34 ==', 'assert r["d34"] == r["d8"] =='),
    ("混音器的驅動取描述", 'assert r["mix_drv"] == [r["drv"]]', 'assert r["mix_drv"] == [r["desc"]]'),
    ("字序對照只准 1 種", "assert STATIC_ORDER in FIT and len(FIT) == 2", "assert STATIC_ORDER in FIT and len(FIT) == 1"),
    ("只要一個載入段", "assert len(SEGS) >= 2, SEGS", "assert len(SEGS) >= 3, SEGS"),
    # (M) 兩群各 3 筆
    ("雜訊窗方向反了", "lo, hi = max(vals) - JIT[1], min(vals) - JIT[0]", "lo, hi = max(vals) + JIT[0], min(vals) + JIT[1]"),
    ("收尾多算一條", "q, r = divmod(t - BASE0 - END, PER_MIX)", "q, r = divmod(t - BASE0 - END - 1, PER_MIX)"),
    # (S) 混音器模型與音效
    ("累加器從 0 起算", 'ACC0 = operand(0x497C0, "mov ecx, ")', 'ACC0 = 0 * operand(0x497C0, "mov ecx, ")'),
    ("步長不除輸出率", "STEP = (RATE << 16) // HW_RATE", "STEP = (RATE << 16) // RATE"),
    ("一次填一半", "N_OUT = N_OUT.popitem()[0]", "N_OUT = N_OUT.popitem()[0] // 2"),
    ("混滿多數一次", "            k += 1\n", "            k += 2\n"),
    ("m 要偶數", "m is not None and m % 2 == 1 for _k, m in SOUNDS", "m is not None and m % 2 == 0 for _k, m in SOUNDS"),
    ("只掃頂層資源", "_sub = ud.parse_directory(_blob)", "_sub = ud.parse_directory(_blob)[:0]"),
    ("對照也用 0x80000000", "_pred0[play(_L, 0)].append(_L)", "_pred0[play(_L)].append(_L)"),
    # 解讀層:結論文字
    ("結論的 m 拿真值", "讓 m 為整數(m = {w['m']})", "讓 m 為整數(m = {w['true']})"),
    ("結論長度拿 m", "= {r['length']} 位元組", "= {m_of(t)} 位元組"),
    ("結論的字拿檔案值", "當時那個字 = {INIT_W[OFF34]:#06x}", "當時那個字 = {int.from_bytes(DIG[OFF34:OFF34 + 2], 'little'):#06x}"),
    ("結論的寫入拿 0x301", "for o, v in sorted(INIT_W.items()))", "for o, v in sorted(RET301.items()))"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s178", MUTANTS))
