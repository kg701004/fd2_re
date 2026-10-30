"""ev_s173.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s173.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 紀錄本身
    ("k 要求嚴格遞增", "\"k_nondecreasing\": all(a[0] <= b[0] for a, b in zip(seq, seq[1:]))",
     "\"k_nondecreasing\": all(a[0] < b[0] for a, b in zip(seq, seq[1:]))"),
    # (B) P1:O / N 的 eip
    ("O / N 的 eip 當成下一條", "if s == (x.m, x.cs, x.eip) and code is not None:", "if s == (x.m, x.cs, x.eip + 1) and code is not None:"),
    ("in / out 方向對調", "return (\"N\" if op in _IN else \"O\"), imm, width", "return (\"O\" if op in _IN else \"N\"), imm, width"),
    ("byte 寬度當 2", "width = 1 if op in (0xE4, 0xE6, 0xEC, 0xEE) else (2 if pre else 4)",
     "width = 2 if op in (0xE4, 0xE6, 0xEC, 0xEE) else (2 if pre else 4)"),
    ("callback 之後的位移改 2", "and x.eip == s[2] + 4:", "and x.eip == s[2] + 2:"),
    # (C) P2:工具 A 對實機
    ("立即埠比成不等", "\"imm_port_same\": sum(1 for e, p in imm if static[e].port == p)",
     "\"imm_port_same\": sum(1 for e, p in imm if static[e].port != p)"),
    ("對照改用自己的檔", "P2_CONTROL = {\"SBPRO2.MDI_vs_SB16.DIG\": p2_one(\"SBPRO2.MDI\", \"SB16.DIG\")",
     "P2_CONTROL = {\"SBPRO2.MDI_vs_SB16.DIG\": p2_one(\"SBPRO2.MDI\", \"SBPRO2.MDI\")"),
    ("碼位元組錯一格", "e < len(fb) and fb[e:e + 16] == c[:len(fb[e:e + 16])]", "e < len(fb) and fb[e + 1:e + 17] == c[:len(fb[e + 1:e + 17])]"),
    ("超出檔案的 eip 算相符", "e < len(fb) and fb[e:e + 16] == c[:len(fb[e:e + 16])]", "fb[e:e + 16] == c[:len(fb[e:e + 16])]"),
    ("DMA 表格錯一格", "DIG[t + bx] == x.port for t, x in zip(tabs, g)", "DIG[t + bx + 1] == x.port for t, x in zip(tabs, g)"),
    ("兩個驅動段對調", "DIG_CS, MDI_CS = 0x137C, 0x0F71", "DIG_CS, MDI_CS = 0x0F71, 0x137C"),
    ("計數高位元組不移位", "\"count_reg\": cnt[0] | (cnt[1] << 8)", "\"count_reg\": cnt[0] | cnt[1]"),
    # (D) P3:單一樣本 DMA
    ("一個樣本不算立體聲", "return (2 if aliased else 1) * (2 if b[\"stereo\"] else 1)", "return (2 if aliased else 1)"),
    ("aliased 判斷反了", "aliased = b[\"bits\"] == 16 and channel < 4", "aliased = b[\"bits\"] == 16 and channel >= 4"),
    ("DSP 長度不加一", "\"length\": 1 + lo + (hi << 8)}", "\"length\": lo + (hi << 8)}"),
    ("0x41 只帶一個參數", "_NARGS = {0x41: 2,", "_NARGS = {0x41: 1,"),
    ("DAC 開始時間從格頭算", "DAC[\"start_ms_est\"] = round(DAC[\"first_bucket\"] + 100 - DAC[\"first_count\"] / 22.05, 2)",
     "DAC[\"start_ms_est\"] = round(DAC[\"first_bucket\"] + DAC[\"first_count\"] / 22.05, 2)"),
    ("預測句的比較放寬成 <=", "\"wording_holds\": SINGLE[\"init\"][\"basecnt\"] + 1 < SINGLE[\"init\"][\"one_sample\"]",
     "\"wording_holds\": SINGLE[\"init\"][\"basecnt\"] + 1 <= SINGLE[\"init\"][\"one_sample\"]"),
    # (E) P4:鍵盤
    ("KEYDELAY 下限改 0.31", "assert all(r[\"delay_ms\"] >= 0.3 for r in KROWS)", "assert all(r[\"delay_ms\"] >= 0.31 for r in KROWS)"),
    ("TransferBuffer 當成 CPU 收的時刻", "_tb = collections.Counter(int((y.t + 0.3) // 100) * 100", "_tb = collections.Counter(int((y.t + 5.6) // 100) * 100"),
    ("sti 後的 IRQ 0 / 進服務的 IRQ 0 取錯", "qa, qb = HW[q9i - 1], HW[q9i - 2]", "qa, qb = HW[q9i - 2], HW[q9i - 3]"),
    ("sti 之後不多做一條", "(0x08, \"P\", GAME_CS, rt(0x3F0BE)) and qb.num == 0x08", "(0x08, \"P\", GAME_CS, rt(0x3F0BD)) and qb.num == 0x08"),
    ("0xd4 的前一個命令取錯", "_prev = DSP[DSP.index(_d4[0]) - 1]", "_prev = DSP[DSP.index(_d4[0]) - 2]"),
    ("0xd4 之後的窗只看 0.5 ms", "STI_WIN[\"d4_followed\"] = [any(0 < a - t < 5.5", "STI_WIN[\"d4_followed\"] = [any(0 < a - t < 0.5"),
    ("長空窗門檻改 9.9 ms", "if b.t - a.t > 5.5 and a.t > LOG_T0)", "if b.t - a.t > 9.9 and a.t > LOG_T0)"),
    ("重入離群表把 602 當正常", "if _v not in (69, 70, 302, 303):", "if _v not in (69, 70, 302, 303, 602):"),
    ("晚收的 run 取最短", "lr = max((x for x in LOG.runs if y.n < x.n_end <= q9.n), key=lambda x: x.count)",
     "lr = max((x for x in LOG.runs if y.n < x.n_end <= q9.n), key=lambda x: -x.count)"),
    ("在 K 之前開始改看結尾", "\"started_before_key\": lr.n_start < y.n", "\"started_before_key\": lr.n_end < y.n"),
    ("MDI 分派段拿 DIG 的", "== (\"r\", MDI_CS, ad.parse_header(MDI)[1])", "== (\"r\", MDI_CS, ad.parse_header(DIG)[1])"),
    ("ISR sti 之後不多做一條", "_l2[\"irq1_eip\"] == rt(0x3EB1D)", "_l2[\"irq1_eip\"] == rt(0x3EB16)"),
    # 解讀層:結論文字
    ("結論的延遲拿按下的", "(晚 {START['delay_ms']} ms)", "(晚 {KROWS[-2]['delay_ms']} ms)"),
    ("結論的 0xd4 時刻拿 0xd0 的", "送 DSP 0xd4({TRIGGER['dsp_d4_ms']} ms", "送 DSP 0xd4({TRIGGER['previous_dsp'][1]} ms"),
    ("結論的通道拿放音那次", "DMA 通道 {SINGLE['init']['channel']} 計數暫存器 {SINGLE['init']['basecnt']}",
     "DMA 通道 {SINGLE['init']['channel']} 計數暫存器 {SINGLE['play']['basecnt']}"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s173", MUTANTS))
