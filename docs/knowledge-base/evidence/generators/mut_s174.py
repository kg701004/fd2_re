"""ev_s174.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s174.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) P1 / P2 / P4 / P5 / P6
    ("DIG 型最後一條取 pop ebp", "(last.cs, last.eip) == (GAME_CS, rt(0x3F0BC))\n", "(last.cs, last.eip) == (GAME_CS, rt(0x3F0BD))\n"),
    ("G 條數多算一", "g[\"g_count\"] == g[\"pre\"] + g[\"span\"] + 1 for g in G_ROWS", "g[\"g_count\"] == g[\"pre\"] + g[\"span\"] + 2 for g in G_ROWS"),
    ("寫出數要嚴格小於符合數", "w == _nb.get(r, 0) and w <= m for", "w == _nb.get(r, 0) and w < m for"),
    ("時間窗下限改 9600", "assert min(t.t1 for t in LB.trigs) >= 9500", "assert min(t.t1 for t in LB.trigs) >= 9600"),
    ("START 之後只看 1 ms", "and _tb < t.t1 < _tb + 10]\n_p6_ng", "and _tb < t.t1 < _tb + 1]\n_p6_ng"),
    # (B) MDI 375
    ("MDI 型只容許 302", "<= {69, 70} and set(cl[(\"p 0080:ed6\", \"0x3f1a4\", ())]) <= {302, 303}",
     "<= {69, 70} and set(cl[(\"p 0080:ed6\", \"0x3f1a4\", ())]) <= {302}"),
    ("派送迴圈的回到點改 0x3eb46", "(\"p 0080:ed6\", \"0x3eb49\", ()): {69: 1}}", "(\"p 0080:ed6\", \"0x3eb46\", ()): {69: 1}}"),
    ("375 減錯基準", "assert len(_drv) == 375 - 302 == 73", "assert len(_drv) == 375 - 303 == 73"),
    ("驅動碼位元組錯一格", "all(DIG_FILE[e:e + len(b)] == b[:len(DIG_FILE[e:e + len(b)])] for e, b in _cb.items())",
     "all(DIG_FILE[e + 1:e + 1 + len(b)] == b[:len(DIG_FILE[e + 1:e + 1 + len(b)])] for e, b in _cb.items())"),
    ("IRQ 7 換成 IRQ 0", "== [(0x0F, 0, \"r\", 0x0C5C, 0x1FAD)], _iq", "== [(0x08, 0, \"r\", 0x0C5C, 0x1FAD)], _iq"),
    # (C) DOS/4GW 轉送
    ("DOS/4GW 檔內位置錯一", "D4G = 0x9AE0 ", "D4G = 0x9AE1 "),
    ("分派表索引不加一", "_EXE, D4G + 0x66A + (ah + 1) * 2)[0]", "_EXE, D4G + 0x66A + ah * 2)[0]"),
    ("塊大小改 8000", "TMP_LEN, CHUNK = 0x32A00, 8192", "TMP_LEN, CHUNK = 0x32A00, 8000"),
    ("popf 之後收的 IRQ 0 改 6 次", "assert w[\"hw_irqs\"][\"08 r 0c5c:10b5\"] == 7", "assert w[\"hw_irqs\"][\"08 r 0c5c:10b5\"] == 6"),
    ("甲型結尾不是 popf", "assert at(last) == (\"r\", 0x0C5C, 0x10B4) and a.iff == 1", "assert at(last) == (\"r\", 0x0C5C, 0x10B5) and a.iff == 1"),
    ("popf 之後的差改 2", "assert max(w[\"after_popf\"] for w in b_) - min(w[\"after_popf\"] for w in b_) <= 4",
     "assert max(w[\"after_popf\"] for w in b_) - min(w[\"after_popf\"] for w in b_) <= 2"),
    ("滿塊門檻改 1120", "== 25 == sum(1 for c in WRITE[\"lc174b\"][\"chunks\"] if c >= 1000)",
     "== 25 == sum(1 for c in WRITE[\"lc174b\"][\"chunks\"] if c >= 1120)"),
    ("讀檔拷貝段包含 sti 之後一條", "if 0xE39 <= e <= 0xE6A)", "if 0xE39 <= e <= 0xE6C)"),
    ("讀檔來源取前一次 int 21h", "gi[bisect.bisect_left(gn, r.n_end) - 1].eip", "gi[bisect.bisect_left(gn, r.n_end) - 2].eip"),
    ("9262 那段條數改 1071", "assert _r9262.count == 1070 and", "assert _r9262.count == 1071 and"),
    # (D) 0080:0084 型
    ("反射後條數改 230", "max(s[\"post_one_irq\"], key=s[\"post_one_irq\"].get) == 237", "max(s[\"post_one_irq\"], key=s[\"post_one_irq\"].get) == 230"),
    ("600 .. 604 範圍放寬到 500", "\"in_600_604\": sum(NG_LO <= r[\"count\"] <= NG_HI for r in rows)",
     "\"in_600_604\": sum(500 <= r[\"count\"] <= NG_HI for r in rows)"),
    ("Y 區塊的反射條數改 236", "and t.n1 - hw[0].n + 1 == 237, (nm, t.seq)", "and t.n1 - hw[0].n + 1 == 236, (nm, t.seq)"),
    # 解讀層:結論文字
    ("結論的符合數拿寫出數", "(規則 3 符合 {YC_B['3']['matched']}", "(規則 3 符合 {YC_B['3']['written']}"),
    ("結論的乙型數拿區塊數", "f\"兩份紀錄各 {WRITE['lc174a']['hw_irqs']['08 r 0c5c:10b5']} / 26", "f\"兩份紀錄各 {len(Y_WR['lc174a'])} / 26"),
    ("結論的塊數拿滿塊", "一次 write 分 {len(WRITE['lc174a']['chunks'])} 塊", "一次 write 分 {FULL_N} 塊"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s174", MUTANTS))
