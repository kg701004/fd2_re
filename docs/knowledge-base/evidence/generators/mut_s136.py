"""ev_s136.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s136.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("寫入判準看成讀", 'write = i.op_str.startswith("dword ptr [0x3a6d],")', 'write = i.op_str.startswith("dword ptr [0x3a6d]")'),
    ("載入位元組改第 4 項", '"6a03" "ff356d3a0000"', '"6a04" "ff356d3a0000"'),
    ("只跑一次的鏈不檢查回跳", "if a > site and e <= t <= site:", "if a > site and e <= t < e:"),
    ("回跳判準放寬到函式外", "if a > site and e <= t <= site:", "if a > site and t <= site:"),
    ("換色條件初值預期 0", "assert gate_init == -1", "assert gate_init == 0"),
    ("第 25 章指標錯開 4 byte", "ch25_res = heap[ch25_ptr - HEAP_BASE:", "ch25_res = heap[ch25_ptr - HEAP_BASE + 4:"),
    ("heap 起點錯一頁", "HEAP_BASE, GLOBALS_BASE = 0x1E0000, 0x53A00", "HEAP_BASE, GLOBALS_BASE = 0x1E1000, 0x53A00"),
    ("全域傾印起點錯 4", "HEAP_BASE, GLOBALS_BASE = 0x1E0000, 0x53A00", "HEAP_BASE, GLOBALS_BASE = 0x1E0000, 0x53A04"),
    ("三角表預期改成 19 為頂", "assert TRI == [min(i, 20 - i) for i in range(20)], TRI", "assert TRI == [min(i, 19 - i) for i in range(20)], TRI"),
    ("redraw 取成下一個 call(wait_ticks)", "_rc = insn(0x152A8)", "_rc = insn(0x152B2)"),
    ("目錄的檔長偏移錯 1", "== len(f3) and OFFS[0] == 6 + 4 * (N_ENT + 1)", "== len(f3) + 1 and OFFS[0] == 6 + 4 * (N_ENT + 1)"),
    ("換色表只有 16 項", "struct.unpack_from(\"<H\", f3, 4)[0] == 0x17", "struct.unpack_from(\"<H\", f3, 4)[0] == 0x16"),
    ("不在清除處停", "w = walk(s + 5, True)", "w = walk(s + 5, False)"),
    ("重畫改成不是函式入口的位址", "DRAWS = {0x11EEE} ", "DRAWS = {0x12106} "),
    ("回跳偵測正對照預期沒有", 'and ["0x1194d", "0x11942"] in LOOP_CONTROL', 'and ["0x1194d", "0x11942"] not in LOOP_CONTROL'),
    ("堆疊檢查不列白名單", "NO_DRAW = {0x3702F}", "NO_DRAW = set()"),
    ("不遞移", "        r = draws(t, True, stack + (f,))", "        r = draws(t, False, stack + (f,))"),
    ("條件跳只走一路", "                    todo.append(int(i.op_str, 16))\n                a = nxt\n            elif m in",
     "                    pass\n                a = nxt\n            elif m in"),
    ("0x14818 歸到 AI", "AI_FUNCS = {0x14121:", "AI_FUNCS = {0x14818: \"collect_targets_in_range\", 0x14121:"),
    ("ai_item_action 歸到玩家", "0x15055: \"ai_item_action\", ", ""),
    ("玩家重畫點少一個", '"0x1d2bf", "0x1d38e"]', '"0x1d2bf"]'),
    ("正對照換成 0x189f8", 'if x["site"] == "0x1894d")["draw_before_clear"]', 'if x["site"] == "0x189f8")["draw_before_clear"]'),
    ("對照預期 AI 端沒有一個", "assert len(rival_ai_ignore_clear) >= 1", "assert len(rival_ai_ignore_clear) == 0"),
    ("跳表槽多算一個", "dispatch = [FX.get(0x51B91 + 4 * i) for i in range(90)]", "dispatch = [FX.get(0x51B91 + 4 * i) for i in range(91)]"),
    ("fixup 原始值不扣物件基底", "!= v - obj_base(v)]", "!= v]"),
    ("地圖指標收件者少 0x4e4f6", '"0x4e4f6": 5, ', ""),
    ("Enter 閘門改成 +6 == 1", '"0fb65006|83fa02750e', '"0fb65006|83fa01750e'),
    ("資訊卡遞移裡預期有 0x14818", "assert writers_in_info == [] and", "assert writers_in_info == [\"0x14818\"] and"),
    ("byte3 入口少 0x4e4f6", "BYTE3_ENTRIES = (0x4E390, 0x4E4F6, 0x14818)", "BYTE3_ENTRIES = (0x4E390, 0x14818)"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s136", MUTANTS))
