"""ev_s137.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s137.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) lc131a
    ("勝負表第 1 格當成預設", "assert FX[0x51B19 + 4] == 0x206C5", "assert FX[0x51B19 + 4] == 0x205B4"),
    ("預設判定的碼 1 改成 2", '"0x206b9: mov dword ptr [0x3ecc], 1", "0x206c3: pop ebx"',
     '"0x206b9: mov dword ptr [0x3ecc], 2", "0x206c3: pop ebx"'),
    ("main 回標題的跳躍反向", '"0x25e8f: test edi, edi", "0x25e91: je 0x25db1"', '"0x25e8f: test edi, edi", "0x25e91: jne 0x25db1"'),
    ("走得到走位的入口預期是戰前第 1 格", '== ["open[0]"], reach_step', '== ["open[1]"], reach_step'),
    ("走位只有 walk_path 呼叫", "assert sorted(callers[STEP]) == [0x13488, 0x3231B]", "assert sorted(callers[STEP]) == [0x13488]"),
    ("開場第 0 格建場景的深度預期 4", 'assert d_ctor == {"open[0]": [8],', 'assert d_ctor == {"open[0]": [4],'),
    ("讀檔分支深度預期 8", "assert d_title == {0x25F10: 12, 0x260F5: 12}", "assert d_title == {0x25F10: 12, 0x260F5: 8}"),
    ("main 呼叫戰後表的深度預期 8", "assert d_main == {0x25DBD: 12, 0x25E23: 12,", "assert d_main == {0x25DBD: 12, 0x25E23: 8,"),
    ("ESP 推算不算返回位址", "return -sum(d + 4 for d in chain)", "return -sum(d for d in chain)"),
    ("呼叫紀錄的位移錯一頁", "RELOC = 0x19C000 ", "RELOC = 0x19D000 "),
    ("tick 取成 EBX", "tick = [(k, int(p[6], 16) & 0xFFFF)", "tick = [(k, int(p[7], 16) & 0xFFFF)"),
    ("ESP 取成返回值欄", "esp = lambda p: int(p[4], 16)", "esp = lambda p: int(p[3], 16)"),
    ("死亡演出用重畫的呼叫者判定", "if c is not None and func_of(c) == DEATH]", "if c is not None and func_of(c) == 0x11CAC]"),
    ("b、d 之後只容許 2 幀", 'assert LOG[n]["records_after_death"] <= 6 and', 'assert LOG[n]["records_after_death"] <= 2 and'),
    ("走位幀數預期 209", "and len(k_step) == 210 and", "and len(k_step) == 209 and"),
    ("戰場內走位 ESP 預期與死亡後相同", "assert step_in_battle == [0x1F1538]", "assert step_in_battle == [0x1F15FC]"),
    ("D 那一幀敵方 11 個", "and ENEMY_D == 10 and", "and ENEMY_D == 11 and"),
    # (B) [0x51a93]
    ("立即值也當記憶體位移", 'if m == "lea" or shown not in inner:', 'if m == "lea" or "[" not in op:'),
    ("檔名預期 DATA.DAT", '"FDSHAP.DAT", "DATO.DAT", "FDMUS.DAT"]', '"FDSHAP.DAT", "DATA.DAT", "FDMUS.DAT"]'),
    ("第 1 個引數的槽錯 4", "if k - d == 4:", "if k - d == 8:"),
    ("第 3 處預期交給 fopen", 'assert ARG1_TO == ["fopen", "printf", "printf"]', 'assert ARG1_TO == ["fopen", "printf", "fopen"]'),
    ("實機預期有一份不是 -1", "assert live_gate == [-1, -1, -1]", "assert live_gate == [-1, -1, 0]"),
    ("正對照的寫入數少 1", 'assert len(c53["direct_write"]) == 32 and', 'assert len(c53["direct_write"]) == 31 and'),
    # (C) 第 1、2、5、7 格
    ("法術位元錯一位", "if mask >> s & 1:", "if mask >> (s + 1) & 1:"),
    ("法術 7 預期沒有敵方會", "== [24, 35, 46, 14], SPELL", "== [24, 35, 46, 0], SPELL"),
    # (D) 防拷
    ("0x118aa 的位元組預期是 jne", '"803d443a000000" "eb07"', '"803d443a000000" "7507"'),
    ("條件跳躍不算讀旗標", 'FLAG_READERS = ("j", "set",', 'FLAG_READERS = ("set",'),
    ("反事實不改位元組", "    pc[site - BASE] = orig\n", "    pc[site - BASE] = 0xEB\n"),
    ("防拷函式預期有兩個呼叫點", "assert e8_sites(0x33FAF) == [0x118AC]", "assert e8_sites(0x33FAF) == [0x118AC, 0x34233]"),
    # (E) 地圖 25 截圖
    ("截圖原點用 y 200", "blk = arr[201:601, 192:832]", "blk = arr[200:600, 192:832]"),
    ("圖塊 38 預期 6 格", "and len(CELLS38) == 7", "and len(CELLS38) == 6"),
    ("視窗 12 欄", "CELL, VW, VH = 24, 13, 8\nimg", "CELL, VW, VH = 24, 12, 8\nimg"),
    # (E2) 地形的模式 1
    ("模式 1 改成先寫再跳過", "wr = all(scr[p + 2 * j + 1] == c for j in range(k))", "wr = all(scr[p + 2 * j] == c for j in range(k))"),
    ("模式 1 的 run 少算一格", "                m1.append((pos, k, b[i]))\n                i += 1\n                pos += 2 * k",
     "                m1.append((pos, k, b[i]))\n                i += 1\n                pos += 2 * k - 1"),
    ("地圖 29 用地圖 28 的圖塊組", "M29 = mode1_on_screen(F29, 29)", "M29 = mode1_on_screen(F29, 28)"),
    ("地圖 29 預期沒有長度 2", 'assert M29["runs"] == 16 and M29["k_hist"] == {"1": 15, "2": 1}', 'assert M29["runs"] == 16 and M29["k_hist"] == {"1": 16}'),
    ("格子比對門檻 600(比 576 大,沒有格能比)","        if mk.sum() < 300:\n            return False\n        a, b = px[mk]",
     "        if mk.sum() < 600:\n            return False\n        a, b = px[mk]"),
    ("修補位置預期在程式碼物件", "assert obj_of_patch == [0x60000] and", "assert obj_of_patch == [0x10000] and"),
    ("修補位移錯成程式碼裡", "PATCH_OFF, PATCH_LEN = 502624, 252", "PATCH_OFF, PATCH_LEN = 0x7402A, 252"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s137", MUTANTS))
