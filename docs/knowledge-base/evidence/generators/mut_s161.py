"""ev_s161.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s161.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (0) 工具對照
    ("續掃點 41 處", "len(_stops) == 42", "len(_stops) == 41"),
    ("錯位只有 7 條", "len(ONLY_BYTES) == 8", "len(ONLY_BYTES) == 7"),
    ("舊版掃到結尾", "OLD = {e for e in SWEEP if e[0] < _single_end}", "OLD = {e for e in SWEEP if e[0] <= 0x4EF29}"),
    # (A) AIL 計時通道
    ("pref[0] 預設 201", "assert (PREF[0], PREF[10]) == (200, 120)", "assert (PREF[0], PREF[10]) == (201, 120)"),
    ("登錄端少一個", "assert REG == [0x3FB1B, 0x411EF, 0x43F6A]", "assert REG == [0x3FB1B, 0x411EF]"),
    ("DIG 讀 pref[1]", "fx_imm(0x412A3) == PREF_BASE + 4 * 0", "fx_imm(0x412A3) == PREF_BASE + 4 * 1"),
    ("MDI 讀 pref[9]", "fx_imm(0x4414A) == PREF_BASE + 4 * 10", "fx_imm(0x4414A) == PREF_BASE + 4 * 9"),
    ("基底取最大週期", "BASE_US = min(CHANNELS.values())", "BASE_US = max(CHANNELS.values())"),
    ("週期換算 1e5", "US_PER_S = operand(0x3F3D8, \"mov eax, \")", "US_PER_S = operand(0x3F3D8, \"mov eax, \") // 10"),
    ("續一百五十八格點 2.5 ms", "set(GRID.values()) == {BASE_US / 1000}", "set(GRID.values()) == {BASE_US / 2000}"),
    ("MDI 鏈入口錯", "(0x25C06, 0x3AA72)", "(0x25C06, 0x3AB49)"),
    ("重入判斷改 jbe", "ISR[0x3EA96] == \"ja 0x3ebad\"", "ISR[0x3EA96] == \"jbe 0x3ebad\""),
    ("EOI 在回呼之後", "assert _eoi < _sti < _cb", "assert _cb < _eoi < _sti"),
    # (B) 校準在 AIL 之前
    ("XI 表從 0x539e0 起", "assert (XI_LO, XI_HI) == (0x539B0, 0x539E0)", "assert (XI_LO, XI_HI) == (0x539E0, 0x539E0)"),
    ("XI 一筆少 2 bytes", "operand(0x4610F, \"add esi, \")):", "operand(0x4610F, \"add esi, \") - 2):"),
    ("校準優先序 0x10", "(0x539B6, 0, 0x20, CAL_FN) in XI", "(0x539B6, 0, 0x10, CAL_FN) in XI"),
    ("校準有直接呼叫端", "assert callers(CAL_FN) == []", "assert callers(CAL_FN) != []"),
    ("main 呼叫端改 0x460e1", "assert callers(0x25BF4) == [0x460DC]", "assert callers(0x25BF4) == [0x460E1]"),
    # (C) 確認音效
    ("段與次數的 push 對調", "SFX_LOOP, SFX_IDX = operand(0x1FED3, \"push \"), operand(0x1FED5, \"push \")",
     "SFX_IDX, SFX_LOOP = operand(0x1FED3, \"push \") - 1, operand(0x1FED5, \"push \")"),
    ("FDOTHER #77 只讀 4 個位移", "for k in range(5)]", "for k in range(4)]"),
    ("取樣率 22050", "RATE = operand(0x4154E,", "RATE = 2 * operand(0x4154E,"),
    ("init_sample 格式 1", "assert (RATE, FORMAT) == (11025, 0)", "assert (RATE, FORMAT) == (11025, 1)"),
    ("設取樣率的呼叫端可達", "assert RATE_REACHED == [] and", "assert RATE_REACHED != [] and"),
    # (D) delay 拆解
    ("校準值 9058", "assert CAL == 9057", "assert CAL == 9058"),
    ("每圈 5 條遊戲指令", "GAME_PER_ITER, OVERHEAD = 6, 3", "GAME_PER_ITER, OVERHEAD = 5, 3"),
    ("每次固定開銷 2", "GAME_PER_ITER, OVERHEAD = 6, 3", "GAME_PER_ITER, OVERHEAD = 6, 2"),
    ("閃爍改 delay(90)", "(r for r in ROWS if r[\"ms\"] == 80)", "(r for r in ROWS if r[\"ms\"] == 90)"),
    ("前段只算 3 次", "\"blink_1_4\": pool(BLINK[:4])", "\"blink_1_4\": pool(BLINK[:3])"),
    ("選單高於閃爍後段", "assert max(PRE_EPI) < min(EPI[5:]) and", "assert max(PRE_EPI) > min(EPI[5:]) and"),
    ("前後段間隙 40", "min(EPI[:4]) - max(EPI[5:]) > 30", "min(EPI[:4]) - max(EPI[5:]) > 40"),
    ("音效結束在第 5 次之後", "assert BLINK[3][\"t0\"] < SFX_END < BLINK[4][\"t0\"]",
     "assert BLINK[4][\"t0\"] < SFX_END < BLINK[5][\"t0\"]"),
    ("音效長度多算 10%", "SFX_END = CONF + SFX_S * 1000", "SFX_END = CONF + SFX_S * 1100"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s161", MUTANTS))
