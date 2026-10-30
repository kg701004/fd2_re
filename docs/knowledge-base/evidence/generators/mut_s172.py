"""ev_s172.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s172.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 紀錄本身
    ("k 要求嚴格遞增", "\"k_nondecreasing\": all(a[0] <= b[0] for a, b in zip(seq, seq[1:]))",
     "\"k_nondecreasing\": all(a[0] < b[0] for a, b in zip(seq, seq[1:]))"),
    # (B) P1:DH = 0
    ("短路門檻放寬到 41", "return \"short\" if 33 <= c <= 35 else", "return \"short\" if 33 <= c <= 41 else"),
    ("從 04f 起的長 run 也當迴圈", "return \"cf1_loop\" if r.count <= 5 else \"cf0_first\"",
     "return \"cf1_loop\" if r.count >= 5 else \"cf0_first\""),
    ("最後一次長路讀的 DH 當成自己讀的", "t_prev_last = allt[allt.index(t_last) - 1]", "t_prev_last = t_last"),
    ("秒數 0 少算 3 個 tick", "t_start = ticks[ie - SEC0_TICKS]", "t_start = ticks[ie - SEC0_TICKS + 3]"),
    ("PIT 速率錯", "PIT = 1193182\n", "PIT = 1193180\n"),
    # (C) P2:時間片
    ("rep 一次最多 3 次迭代", "return 0 <= x <= 4", "return 0 <= x <= 3"),
    ("mov / pop ss 不多給一條", "\"string1\": 1, \"ss\": -1}", "\"string1\": 1, \"ss\": 0}"),
    ("pop ss 不認", " or (mn == \"pop\" and ops == \"ss\"):", ":"),
    ("進了 ISR 的 delay 也算乾淨", "if bisect.bisect_right(isr_t, t0) != bisect.bisect_left(isr_t, t1):\n            continue",
     "if False:\n            continue"),
    ("有鍵盤中斷的 delay 也算乾淨", "        if inside:\n", "        if False:\n"),
    ("每 ms 時間片改用指令數", "\"slices_per_ms\": round(sum(g[3] for g in grp)", "\"slices_per_ms\": round(sum(g[2] for g in grp)"),
    ("nm 偏移的正負號反了", "BIAS = PICEV_REF - _ref", "BIAS = PICEV_REF + _ref"),
    ("DMA_DAC 時段改看 VGA", "if d.get(\"DMA_DAC_Event\"))", "if d.get(\"VGA_DrawSingleLine\"))"),
    ("DMA_DAC 開始時間從格頭算", "DAC[\"start_ms_est\"] = round(3200 - 224 / 22.05, 2)", "DAC[\"start_ms_est\"] = round(3100 + 224 / 22.05, 2)"),
    ("續一百六十五指令數差加錯號", "- (_ph[\"early\"][\"nongame_mean\"] - _ph[\"late\"][\"nongame_mean\"])",
     "+ (_ph[\"early\"][\"nongame_mean\"] - _ph[\"late\"][\"nongame_mean\"])"),
    # (D) P3:rep
    ("基準次數用無條件捨去", "base = -(-REP_N[f\"{key[1]:04x}:{key[2]:x}\"] // 4)", "base = REP_N[f\"{key[1]:04x}:{key[2]:x}\"] // 4"),
    ("rep 期間的 k 增加算成 0", "extra, dk_in = (j - i + 1) - base, SL[j][0] - SL[i][0]", "extra, dk_in = (j - i + 1) - base, SL[j][0] - SL[j][0]"),
    # (E) P4:137c
    ("驅動位元組錯一格", "DIG_MATCH = {k: {f: sum(b[e:e + 16] == c for e, c in v)", "DIG_MATCH = {k: {f: sum(b[e + 1:e + 17] == c for e, c in v)"),
    ("137c 的第一次改找第一次轉送", "i137 = next(i for i, (_t, s) in enumerate(kinds) if s.startswith(\"r 137c:\"))",
     "i137 = next(i for i, (_t, s) in enumerate(kinds) if s.startswith(\"r 137c:16a-1fa\"))"),
    # (F) P5:鍵盤
    ("巢狀中斷不排除", "        elif any(x.type == 0 and q.n < x.n < back.n_start for x in lg.irqs):", "        elif False:"),
    ("正常路徑找錯段", "== (\"p\", 0x80, 0xED6, 0x6D5))", "== (\"p\", 0x80, 0xED6, 0x6C9))"),
    ("MDI 型 303 當離群", "if v not in (69, 70, 302, 303):", "if v not in (69, 70, 302):"),
    # 解讀層:結論文字
    ("結論的長路次數拿短路的", "lc172a {DH0['lc172a']['table']['cf1_loop|long']} 次", "lc172a {DH0['lc172a']['table']['cf1_loop|short']} 次"),
    ("結論的鍵盤處理用整個 602", "中間 {SPLIT['lc172a']['kb_handling']} 條鍵盤處理", "中間 {SPLIT['lc172a']['post']} 條鍵盤處理"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s172", MUTANTS))
