"""ev_s164.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s164.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 原始紀錄
    ("不扣截斷那一筆", "== len(REC) + 1   #", "== len(REC)   #"),
    # (B) 程式碼
    ("EOI 後是 cli", "at(0x3EB15) == \"sti\"", "at(0x3EB15) == \"cli\""),
    ("重入分支多算 push", "REENTRY_REST == [\"mov al, 0x20\"", "REENTRY_REST == [\"push eax\", \"mov al, 0x20\""),
    ("DIG 只有一處 cli", "SITES[\"dig\"][\"cli\"] == [\"0x3f0aa\", \"0x3f0b9\"]", "SITES[\"dig\"][\"cli\"] == [\"0x3f0aa\"]"),
    ("MDI 有 cli", "SITES[\"mdi\"][\"cli\"] == []", "SITES[\"mdi\"][\"cli\"] != []"),
    ("DPMI 0301h", "at(0x3F190) == \"mov eax, 0x300\"", "at(0x3F190) == \"mov eax, 0x301\""),
    # (B) 紀錄
    ("轉接結尾少一條", "NORMAL_TAIL[EPI_CHAIN] == NORMAL_TAIL[EPI] + 1", "NORMAL_TAIL[EPI] == NORMAL_TAIL[EPI_CHAIN] + 1"),
    ("STI 不延遲", "DIG_TAIL = walk(0x3F0BE,", "DIG_TAIL = walk(0x3F0BD,"),
    ("MDI 從 int 31h 本身算", "MDI_TAIL = (walk(0x3F1A4, 0x3F1AC)", "MDI_TAIL = (walk(0x3F1A2, 0x3F1AC)"),
    ("DIG 預測不算 R 那條", "+ len(DIG_TAIL) + 1 + NORMAL_TAIL[EPI],", "+ len(DIG_TAIL) + NORMAL_TAIL[EPI],"),
    ("MDI 預測少一條", "+ len(MDI_TAIL) + 1 + MDI_TO_DIG}", "+ len(MDI_TAIL) + MDI_TO_DIG}"),
    ("晚到門檻 0.5", "LATE_TH = 0.3", "LATE_TH = 0.5"),
    ("週期當 5 ms 整", "P = S161[\"timer_channels\"][\"pit_divisor\"] / 1193182 * 1000", "P = 5.0"),
    ("MDI 非遊戲門檻 0.9", "MDI_LONG_NONGAME > 0.7", "MDI_LONG_NONGAME > 0.9"),
    # (C) 校準
    ("等待迴圈 5 條", "== (7, 6, 2, 5, 4)", "== (7, 5, 2, 5, 4)"),
    ("int 21h 次數不加 1", "_x = [w + c + 1 for c", "_x = [w + c for c"),
    ("delay 固定指令多算 inc", "DELAY_FIXED = len(_dl) - 1 +", "DELAY_FIXED = len(_dl) +"),
    ("delay 圈數 17", "NG_DELAY = round((DELAY_DN - (DELAY_FIXED + 5 * 18)) / 18, 2)",
     "NG_DELAY = round((DELAY_DN - (DELAY_FIXED + 5 * 18)) / 17, 2)"),
    ("tick 不進位", "_tick_per_call = [round(-(-TICKS_CAL // 1) *", "_tick_per_call = [round((TICKS_CAL // 1) *"),
    ("tick 樣本門檻 1000", "if x - base > 100]", "if x - base > 1000]"),
    ("每條時間比反過來", "TIME_PER_INSN_RATIO = round(NMS[\"delay_clean\"] / NMS[\"calibration\"], 4)",
     "TIME_PER_INSN_RATIO = round(NMS[\"calibration\"] / NMS[\"delay_clean\"], 4)"),
    ("非遊戲不扣遊戲指令", "NG_CAL = [round((CAL_DN - CAL_DI) / x, 2)", "NG_CAL = [round(CAL_DN / x, 2)"),
    # (D) AIL_DEBUG
    ("字串是 AIL_SYS_DEBUG", "== b\"AIL_DEBUG\\0\"", "== b\"AIL_SYS_DE\""),
    ("沒設才登錄", "\"jne 0x37d74\", \"call 0x3fca9\"", "\"je 0x37d74\", \"call 0x3fca9\""),
    ("0x37c30 有兩處參照", "assert _refs == [0x37E77]", "assert _refs == [0x37E77, 0x37E7B]"),
    ("驅動有設環境", "assert \"DOS_SET\" not in _drv", "assert \"DOS_SET\" in _drv"),
    ("AIL 後第一格 10 ms", "assert _bios[0] > 50", "assert _bios[0] < 10"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s164", MUTANTS))
