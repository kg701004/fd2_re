"""ev_s191b.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s191b.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A)
    ("58 入口錯一格", "ENTRY[58] == 0x35854", "ENTRY[58] == 0x35898"),
    ("表只有 7 處引用", "0x1D890, 0x1D95C, 0x1D9EC]", "0x1D890, 0x1D95C]"),
    ("85 不是空的", '0x36438: "ret ",', '0x36438: "call 0x35b78",'),
    ("格子事件不看地形", "        if word & 0x1F and terr[(tile & 0x3FF) * 4] & 0x60 == 0:", "        if word & 0x1F:"),
    ("回合列漏掉休眠列 82", "TURN_IDS == [63, 65, 66, 68, 70, 74, 76, 79, 82]", "TURN_IDS == [63, 65, 66, 68, 70, 74, 76, 79]"),
    ("寶箱不排除 type 0 / 1", "                       if ctrl[0x53 + 3 * s] not in (0, 1)})", "                       if True})"),
    ("map29 第 0 列是 81", "PER_MAP[29][\"turn_row0\"] == [0xFF, 82, 0]", "PER_MAP[29][\"turn_row0\"] == [0xFF, 81, 0]"),
    # (B)
    ("metadata 在槽開頭", "META_OFF = 0xA00 ", "META_OFF = 0 "),
    ("checksum 不重疊", "assert SLOT0 + 3 * SLOT_SIZE + META_OFF + 36 == CHECKSUM", "assert SLOT0 + 3 * SLOT_SIZE + META_OFF + 32 == CHECKSUM"),
    ("掃描只看 +10 .. +35", "for i in range(4) for off in range(10, META)}", "for i in range(4) for off in range(10, META - 4)}"),
    ("Delete 改成 Enter", '0x29D0A: "mov byte ptr [0x3a8e], 1"', '0x29D0A: "mov byte ptr [0x3a8e], 0x1c"'),
    ("0x180e6 不是畫面寬", 'insn(0x180E1) == "push 0x140"', 'insn(0x180E1) == "push 0x28"'),
    # (C)
    ("+8 名字讀 +9", '0x18D73: "movzx eax, byte ptr [esi + 8]"', '0x18D73: "movzx eax, byte ptr [esi + 9]"'),
    ("法術欄 4 bytes", '0x1C29E: "cmp dword ptr [esp], 5"', '0x1C29E: "cmp dword ptr [esp], 4"'),
    ("對照組不計", "assert V_OK == 0 and all(v > 0 for v in V_NULL.values())", "assert V_OK == 0 and any(v == 0 for v in V_NULL.values())"),
    # (D)
    ("handler 表 9 格", "SPELL_HANDLERS = [_FX[0x524C6 + 4 * i] for i in range(10)]", "SPELL_HANDLERS = [_FX[0x524C6 + 4 * i] for i in range(9)]"),
    ("法術 0 用 #81", "assert SPELL_POOL == [82, 82, 83", "assert SPELL_POOL == [81, 82, 83"),
    ("[0x5411f] 有引用", '"0x5411f": 0, "0x54117": 0', '"0x5411f": 1, "0x54117": 0'),
    ("揮空放 +5", '0x2EFEC: "push 0",', '0x2EFEC: "push 5",'),
    ("會心改 sfx", '0x2F9DA: "mov dword ptr [esi + 4], 1"', '0x2F9DA: "mov dword ptr [esi], 1"'),
    ("攻擊池 #47 起", "assert ATTACK_POOLS == [48, 49, 50, 51, 52, 53]", "assert ATTACK_POOLS == [47, 48, 49, 50, 51, 52]"),
    ("子樣本表從 +2 起", '    a0, a1 = struct.unpack_from("<II", c, 6)', '    a0, a1 = struct.unpack_from("<II", c, 2)'),
    ("sub 0 各池不同", "assert len(set(SUB0.values())) == 1, SUB0", "assert len(set(SUB0.values())) == 6, SUB0"),
    # (E)
    ("0x2bce5 有呼叫端", 'CALLERS == {"0x2bce5": [],', 'CALLERS == {"0x2bce5": ["0x2545d"],'),
    ("0x2fb2c 由結局呼叫", '"0x2fb2c": ["0x2abcc"]', '"0x2fb2c": ["0x2545d"]'),
    ("load_res 113 處", "assert N_LOAD_RES == 132", "assert N_LOAD_RES == 113"),
    # (G)
    ("範圍格比 0", '0x121FE: "cmp edx, 0xff"', '0x121FE: "cmp edx, 0"'),
    ("選目標模式 4 不接受", '0x11719: "cmp edi, 5"', '0x11719: "cmp edi, 4"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s191b", MUTANTS))
