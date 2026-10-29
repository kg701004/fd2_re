"""ev_s165.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s165.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 原始紀錄
    ("記錄數不比對續一百六十四", "assert len(REC) == S164[\"source_run\"][\"records\"]", "assert len(REC) == S164[\"source_run\"][\"records\"] + 1"),
    # (A) 路徑長度
    ("通道格 15 個", "NSLOT = 16", "NSLOT = 15"),
    ("啟用通道 2 個", "K = 3", "K = 2"),
    ("鎖住結尾不算 A 那條", "len(AFTER_SCAN) + len(LOCKED_END) + 1\n", "len(AFTER_SCAN) + len(LOCKED_END)\n"),
    ("第一個回呼不算 mov edi", "len(AFTER_SCAN) + 1\n            + slot", "len(AFTER_SCAN)\n            + slot"),
    ("同一格再叫算 mov esp", "len(walk(CB_RET, 0x3EB46)) - 1 + len(CALL_SEQ) + 1", "len(walk(CB_RET, 0x3EB46)) + len(CALL_SEQ) + 1"),
    ("鎖住時不看鎖", "\"cmp dword ptr [0x2bea], 0\", \"jg 0x3eb4e\"]", "\"cmp dword ptr [0x2bea], 0\", \"jle 0x3eb4e\"]"),
    ("溢位只有 inc", "OVERFLOW = walk(0x3EAF7, 0x3EB03)", "OVERFLOW = walk(0x3EAFD, 0x3EB03)"),
    # (A) 3665 ms
    ("補叫順序 DIG 先", "== [\"MDI\", \"MDI\", \"DIG\", \"DIG\", \"DIG\"], CATCHUP", "== [\"DIG\", \"DIG\", \"DIG\", \"MDI\", \"MDI\"], CATCHUP"),
    ("前兩次有回呼", "x[\"callbacks\"] == 0 and", "x[\"callbacks\"] > 0 and"),
    ("溢位數 1 / 1 / 2", "assert _j == [1, 2, 2], _j", "assert _j == [1, 1, 2], _j"),
    ("MDI 待辦不扣 DIG", "\"MDI\": sum(_j) - len(_j)}", "\"MDI\": sum(_j)}"),
    ("3665 接的是 DIG", "_rest + _mdi_tail + 1 + SAME_SLOT_AGAIN\n", "_rest + _mdi_tail + 1 + 14\n"),
    ("MDI 型 14 次", "MDI_TYPE_TOTAL = S164[\"interrupt_off\"][\"reentry_classes\"][\"mdi_driver_return\"] + 1",
     "MDI_TYPE_TOTAL = S164[\"interrupt_off\"][\"reentry_classes\"][\"mdi_driver_return\"]"),
    # (B) 驅動
    ("驅動是 SBPRO1", "[[\"DRIVER\", \"SBPRO2.MDI\"]], _drv_line", "[[\"DRIVER\", \"SBPRO1.MDI\"]], _drv_line"),
    ("入口取 +0x32", "struct.unpack_from(\"<H\", DRV, 0x34)[0]", "struct.unpack_from(\"<H\", DRV, 0x32)[0]"),
    ("分派器有 sti", "s in (\"sti\", \"popf\", \"pushf\")] == []", "s in (\"sti\", \"popf\", \"pushf\")] != []"),
    ("功能 0x503", "FN = 0x502", "FN = 0x503"),
    ("不跟 loop", "or m.startswith(\"loop\")", "or m == \"loop\" and False"),
    ("十進位目標當間接", "if i.op_str.isdigit() or i.op_str.startswith(\"0x\"):", "if i.op_str.startswith(\"0x\"):"),
    ("0x502 有 sti", "for m in (\"cli\", \"sti\", \"popf\", \"pushf\", \"iret\", \"int\")) and", "for m in (\"cli\", \"popf\", \"pushf\", \"iret\", \"int\")) and KINDS[\"sti\"] != [] and"),
    ("旗標不是 pushf", "== [\"pushf\", \"pop ax\", \"mov word ptr [ebp - 0x1a], ax\"]", "== [\"pushfd\", \"pop ax\", \"mov word ptr [ebp - 0x1a], ax\"]"),
    ("MDI 型只看前一筆是 DIG", "and prev[\"k\"] == \"E\" and prev[\"eip\"] == MDI:", "and prev[\"k\"] == \"E\" and prev[\"eip\"] == DIG:"),
    ("MDI 之前是定值", "PRE_RANGE[\"MDI\"][1] - PRE_RANGE[\"MDI\"][0] > 5000", "PRE_RANGE[\"MDI\"][1] - PRE_RANGE[\"MDI\"][0] < 5000"),
    ("收中斷後多算 DIG", "AFTER_ACCEPT = POST_MODE[\"MDI\"] - POST_MODE[\"DIG\"]", "AFTER_ACCEPT = POST_MODE[\"MDI\"]"),
    # (C) 校準
    ("delay 不扣 ISR", "for e, r in _d2 if clean(e, r))", "for e, r in _d2 if True)"),
    ("clean 多看一格", "return bisect.bisect_right(_isr_e, e[\"t\"]) ==", "return bisect.bisect_right(_isr_e, e[\"t\"]) + 1 =="),
    ("離群門檻 1000", "if x - _med > 100]", "if x - _med > 1000]"),
    ("時段空檔 5000 ms", "assert _ts[_gap_i] - _ts[_gap_i - 1] > 3000", "assert _ts[_gap_i] - _ts[_gap_i - 1] > 5000"),
    ("校準比最小值", "CAL_ABOVE = round(NG_CAL[0] - PER_INT21_RANGE[1], 2)", "CAL_ABOVE = round(NG_CAL[0] - PER_INT21_RANGE[0], 2)"),
    ("tick 不加樣本", "round(_ex[0] * _x[1] / _nt + _tk)", "round(_ex[0] * _x[1] / _nt)"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s165", MUTANTS))
