"""ev_s176.py 的變異測試:每個變異改一個判準 / 預測 / 解讀,必須讓 ev_s176.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 靜態:分派表與路徑條數
    ("輸出表取第 1 格", "OUT_PLAIN, OUT_CLIP, MIXER = FIX[OUT_TBL], ", "OUT_PLAIN, OUT_CLIP, MIXER = FIX[OUT_TBL + 4], "),
    ("混音器取第 0x40 格", "FIX[MIX_TBL + 4 * 0x60]", "FIX[MIX_TBL + 4 * 0x40]"),
    ("前段少算 0x382d6 jmp", "PRE = lin(SERVE, 0x404EA) + lin(0x382D6, 0x382D6) + ", "PRE = lin(SERVE, 0x404EA) + "),
    # (C) Y 區塊
    ("Y 區塊不要求沒截幅", "assert c[0x480BA] == c[0x480C1] == 0, (nm, t.seq)", "assert c[0x480BA] == c[0x480C1] == 1, (nm, t.seq)"),
    ("Y 區塊要走沒混的計數分支", "== 1 and c[0x40634] == 0, (nm, t.seq)", "== 1 and c[0x40634] == 1, (nm, t.seq)"),
    ("基準取最短的 Y 區塊", "FULL = collections.Counter(b[\"count\"] for b in BLOCKS).most_common(1)[0][0]",
     "FULL = min(b[\"count\"] for b in BLOCKS)"),
    # (A) 沒樣本型的預測
    ("預測忘了計數分支", "OUT_PLAIN_N) + CNT_DIFF\n", "OUT_PLAIN_N)\n"),
    ("預測忘了 0x498c6", "U_PRED = FULL - _ref[\"mix_call\"] - 1 - ", "U_PRED = FULL - _ref[\"mix_call\"] - "),
    ("有 R 的不扣後段", "row.update(span=g - PRE - POST_FILL,", "row.update(span=g - PRE,"),
    ("沒 R 的不扣 pop ebp", "span = run.n_end - n - (PRE - 1) - 1 ", "span = run.n_end - n - (PRE - 1) "),
    ("Y 區塊對不到", "        if n + PRE in ys:", "        if n + PRE - 1 in ys:"),
    ("對照:不填緩衝改 58", "{g for g, _ in _g.most_common(2)} == {G_NOFILL, G_STOPPED}", "{g for g, _ in _g.most_common(2)} == {G_NOFILL + 1, G_STOPPED}"),
    ("雜訊窗上限改 1", "JIT = (-9, 2)\nSPANS", "JIT = (-9, 1)\nSPANS"),
    ("雜訊窗下限放寬", "JIT = (-9, 2)\nSPANS", "JIT = (-12, 2)\nSPANS"),
    ("沒樣本型要有 int 31h", "assert all(f[\"int31\"] == 0 and f[\"dig_insns\"] == 0", "assert all(f[\"int31\"] == 1 and f[\"dig_insns\"] == 0"),
    # (B) 停播型
    ("停播型不要 int 31h", "assert f[\"int31\"] == 1 and f[\"dig_insns\"] > 0, (nm, f)", "assert f[\"int31\"] == 0 and f[\"dig_insns\"] > 0, (nm, f)"),
    ("停播型前面要 3 次沒樣本", "ks[i - 2:i] == [\"unmixed\", \"unmixed\"] and ks[i - 3] in", "ks[i - 3:i] == [\"unmixed\"] * 3 and ks[i - 3] in"),
    ("沒樣本最多連 1 次", "assert \"uuu\" not in SEQ[nm]", "assert \"uu\" not in SEQ[nm]"),
    ("混滿之後只准混滿", "ks[i + 1] in (\"full\", \"partial\") for i", "ks[i + 1] in (\"full\",) for i"),
    ("停播後是不填緩衝的 57", "max(c, key=c.get) == G_STOPPED for c in AFTER.values()", "max(c, key=c.get) == G_NOFILL for c in AFTER.values()"),
    ("SB16.DIG 段錯一", "DIG_CS = 0x137C ", "DIG_CS = 0x137D "),
    # (B) 續:停播在下一次 IRQ 7 才生效
    ("停播型自己的派送當成 0x401", "assert r[\"own_dispatch\"] == [P402], (nm, r)", "assert r[\"own_dispatch\"] == [P401_CANCEL], (nm, r)"),
    ("取消判準反過來", "== (P401_CANCEL not in r[\"dispatch_before_irq7\"])", "== (P401_CANCEL in r[\"dispatch_before_irq7\"])"),
    ("IRQ 之後的窗改 0.01 ms", "and d.t - nq.t < 0.2", "and d.t - nq.t < 0.01"),
    ("下一次中斷取 IRQ 0", "q7 = [q for q in lg.irqs if q.num == 0x0F and q.type == 0]", "q7 = [q for q in lg.irqs if q.num == 0x08 and q.type == 0]"),
    ("每次都要停", "assert all(p > 0 and c > 0 for p, c in CHAIN_N.values())", "assert all(p > 0 and c == 0 for p, c in CHAIN_N.values())"),
    ("暫停命令取下一格", "PAUSE = DIG[0x546] ", "PAUSE = DIG[0x547] "),
    # (D) [drv+0x34]
    ("[drv+0x34] 取 [drv+4] 那組", "int(_ret[_WIDX[\"off8\"]], 16) + _plus)", "int(_ret[_WIDX[\"off4\"]], 16) + _plus)"),
    ("執行時段取 0c5c", "(\"r\", DIG_CS, 0x682) for r in LOG", "(\"r\", 0x0C5C, 0x682) for r in LOG"),
    # (C) 部分緩衝
    ("收尾少算 MIX_END", "return (span - BASE0 - MIX_END - SRC_DONE) / PER_MIX", "return (span - BASE0 - SRC_DONE) / PER_MIX"),
    ("強群門檻改 1", "if gp[\"mode_n\"] >= 3]", "if gp[\"mode_n\"] >= 1]"),
    # 解讀層:結論文字
    ("結論的預測拿眾數", "預測 IF=0 區間 {U_PRED};", "預測 IF=0 區間 {U_G};"),
    ("結論的 m 拿眾數", "三群眾數的 m = {' / '.join(str(int(gp['m'])) for gp in STRONG)}",
     "三群眾數的 m = {' / '.join(str(gp['mode']) for gp in STRONG)}"),
    ("結論多出的條數拿區間", "多 {X_EXTRA} 條", "多 {X_MODE} 條"),
    ("結論 0x402 條數拿 0x401", "SB16.DIG 功能 0x402({F402:#x},{P402} 條)", "SB16.DIG 功能 0x402({F402:#x},{P401_CANCEL} 條)"),
    ("結論的執行時位址拿 [drv+4]", "(執行時 {DIG_CS:04x}:{DRV34_OFF:04x},", "(執行時 {DIG_CS:04x}:{DRV4[1]:04x},"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s176", MUTANTS))
