"""ev_s186.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s186.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 全域與單位表
    ("旗標指標再加 DELTA", 'g32(GL["m00_globals"], PTR_OPENED), \\', 'g32(GL["m00_globals"], PTR_OPENED) + DELTA, \\'),
    ("章節值記成 11", "assert gb[CHAPTER - GLOBALS_LIN] == MAP ", "assert gb[CHAPTER - GLOBALS_LIN] == MAP + 1 "),
    ("單位對記錄不減 1", "    r = i - OWN + 1", "    r = i - OWN"),
    ("記錄 0 當 group 0", '(REC[0]["group"], REC[0]["native_record_byte6"]) == (1, 1)',
     '(REC[0]["group"], REC[0]["native_record_byte6"]) == (0, 1)'),
    ("表尾 +6 記成 0", '(1, REC[0]["raw_unit_key"], REC[0]["raw_unit_key"])', '(0, REC[0]["raw_unit_key"], REC[0]["raw_unit_key"])'),
    # (B) 0xc 播放點
    ("返回位址記成 +4", 'R_AI, R_CHEST = _P0C["ai_mode_dispatch"] + 5,', 'R_AI, R_CHEST = _P0C["ai_mode_dispatch"] + 4,'),
    ("index 記成 0xb", "P0C = [q for q in plays if q.stack[1] == 0xC]", "P0C = [q for q in plays if q.stack[1] == 0xB]"),
    ("記成 handle A", "assert q.eip - DELTA == PLAY_B and", "assert q.eip - DELTA == PLAY_A and"),
    ("事件號讀 ebx", '(q.regs["eax"], q.regs["ebp"], q.regs["ebx"])', '(q.regs["eax"], q.regs["ebx"], q.regs["ebp"])'),
    # (C) 三道關的模型
    ("每回合少一個盜賊", 'assert sorted(c.regs["esi"] for c in disp) == sorted(REC_OF), t',
     'assert sorted(c.regs["esi"] for c in disp) == sorted(REC_OF)[1:], t'),
    ("搶過的仍算模式 5", "        if i in grabbed:", "        if i in ():"),
    ("旗標已開仍找格子", "if lg.rets[ch.seq].eax != 0 or ev in opened:", "if lg.rets[ch.seq].eax != 0:"),
    ("find 參數比單位序號", "finds[0].stack[0] == ev", "finds[0].stack[0] == i"),
    ("find 回 1 才算找到", "assert lg.rets[finds[0].seq].eax == 0", "assert lg.rets[finds[0].seq].eax == 1"),
    ("順序沒有 move", "assert seq == [CHOOSE, FIND, MOVE] +", "assert seq == [CHOOSE, FIND] +"),
    ("金錢也加道具", "([ADD_ITEM] if kind == 0 else [])", "([ADD_ITEM] if kind <= 1 else [])"),
    # (D) 搶到之後的記憶體
    ("旗標讀出記成第 1 回合後", '"f02_flags": 2,', '"f02_flags": 1,'),
    ("+0x34 記成 5", "assert p34 == 7 and", "assert p34 == 5 and"),
    ("+0x32 取高位元組", 'g["chest_value"] & 0xFF]', 'g["chest_value"] >> 8]'),
    ("沒搶的 +0x31 記成 0", "assert u[0x34] == 5 and u[0x31] == 0xFF", "assert u[0x34] == 5 and u[0x31] == 0"),
    ("搶到那回合不在寶箱格", 'assert xy == g["cell"], (k, i)', 'assert xy != g["cell"], (k, i)'),
    ("隱藏格算有人指定", "if s not in set(EV.values()))", "if s in set(EV.values()))"),
    ("P2d 只要物品", '{g["chest_kind"] for g in GRABS} == {0, 1}', '{g["chest_kind"] for g in GRABS} == {0}'),
    # (E) 對照
    ("最先搶的不是最近那個", '(S185["map10_nearest"]["record"], S185["map10_nearest"]["target"])',
     '(S185["map10_nearest"]["record"] + 1, S185["map10_nearest"]["target"])'),
    ("舊驅動當成有加 DELTA", '"raw = S.read_mem(NAME, chest_ptr, min_bytes=16)"',
     '"raw = S.read_mem(NAME, chest_ptr + S.NATIVE_LIVE_DELTA, min_bytes=16)"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s186", MUTANTS))
