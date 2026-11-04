"""ev_s192.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s192.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 靜態
    ("0x13a44 有清除分支", '"mov dword ptr [0x1a8f], edx", "add esp, 8"]', '"mov dword ptr [0x1a8f], edx", "mov dword ptr [0x1a8f], 0xff"]'),
    ("會心索引 = 職業", '"mov dword ptr [esi], 1", "movzx eax, byte ptr [ebp + 0x20]", "dec eax",',
     '"mov dword ptr [esi], 1", "movzx eax, byte ptr [ebp + 0x20]", "inc eax",'),
    ("亞雷斯會心率 12", "assert (CT[10], CT[11], CT[24]) == (3, 12, 0)", "assert (CT[10], CT[11], CT[24]) == (12, 12, 0)"),
    ("出擊目標 15", '"jle 0x2af60", "mov ebp, 0x13"', '"jle 0x2af60", "mov ebp, 0xf"'),
    ("章節 byte 19 = Ctrl+F10", "bytes([4, 0x62]), bytes([3, 0x5C]),", "bytes([4, 0x62]), bytes([4, 0x67]),"),
    ("魔神獎勵 event 80", "(0x7D, 2, 0x51), (0x7C, 2, 0x51)", "(0x7D, 2, 0x50), (0x7C, 2, 0x51)"),
    # (B) mapper
    ("mapper md5 錯", '"passthrough.map": "4591f38c365e72a9bde1e4edebd67b33"', '"passthrough.map": "4591f38c365e72a9bde1e4edebd67b34"'),
    ("沒拿掉 paste", '("hand_paste", "key 63 mod1"),\n', "\n"),
    ("修飾鍵族順序錯", "('mod3', 'mod1', 'mod2')[fam]", "('mod1', 'mod3', 'mod2')[fam]"),
    ("預設只撞兩個", '("0x63", "hand_paste"),\n                           ("0x67", "hand_capmouse")]',
     '\n                           ]'),
    ("ch03 sel 0 也揭示", '("m3", 2, 0x5F, 0)', '("m3", 2, 0x5F, 5)'),
    ("Ctrl+F2 沒進 guest", "[0x50, 0x1C, 0x1C, 0x1D, 0x3C, 0x4B, 0x1D, 0x3C]", "[0x50, 0x1C, 0x1C, 0x1D, 0x4B, 0x1D]"),
    ("揭示 4 次", "and len(REVEALS) == 5, REVEALS", "and len(REVEALS) == 4, REVEALS"),
    ("錯鍵也算揭示", "assert all(ROW(ch)[1:] != bytes([s0, ah]) for ch, s0, ah in NON)",
     "assert all(ROW(ch)[1:] == bytes([s0, ah]) for ch, s0, ah in NON)"),
    # (C) R6
    ("玩家 event62 只 2 次", '[hex(rt(c)) for c in E62].count("0x119a3") == 3', '[hex(rt(c)) for c in E62].count("0x119a3") == 2'),
    ("event63 在第 3 回合", "PA[E63[0].seq] == (2, \"enemy\")", "PA[E63[0].seq] == (3, \"enemy\")"),
    ("回合從 camp 1 算", "            elif camp == 2:\n", "            elif camp == 1:\n"),
    ("event62 之後 row0 改 4", "assert all(r[1] == (2, 63, 0) and r[2] == 1 for r in ROW0[i02:])",
     "assert all(r[1] == (4, 63, 0) and r[2] == 1 for r in ROW0[i02:])"),
    ("之後有增援", "and all(r[4] == 75 for r in ROW0 if r[3] >= 3)", "and all(r[4] == 87 for r in ROW0 if r[3] >= 3)"),
    ("只算終點在 y = 39", "    if stp[-1][1] != 39:\n        PASS_THROUGH", "    if stp[-1][1] == 39:\n        PASS_THROUGH"),
    ("重讀第 3 次才成功", '("read_ok", r["label"], r["try"] + 1)', '("read_ok", r["label"], r["try"] + 2)'),
    ("lc192a 重讀 4 次", 'assert RETRY == {"lc192a": 5,', 'assert RETRY == {"lc192a": 4,'),
    # (D) 物理攻擊音效
    ("一般幀放 sub 0", "assert f4 == 0 and e[1] == f5 != 0, (n", "assert f4 == 0 and e[1] == 0, (n"),
    ("未命中放幀 +5", "assert f4 != 0 and f5 != 0 and e[1] == 0, (n", "assert f4 != 0 and f5 != 0 and e[1] == f5, (n"),
    ("命中探針在未命中輪", 'assert ("hit" in kinds) <= (miss == 0) and ("miss" in kinds) <= (miss == 1)',
     'assert ("hit" in kinds) <= (miss == 1) and ("miss" in kinds) <= (miss == 0)'),
    ("會心有額外 sfx", 'SHAPE(r) == [("hit", 1, 2), ("sfx", 2, 1)] for _n, r in ARES)',
     'SHAPE(r) == [("hit", 1, 2), ("sfx", 2, 1)] for _n, r in ARES if r["res"][1] == 0)\nassert all(SHAPE(r) != [("hit", 1, 2), ("sfx", 2, 1)] for _n, r in ARES if r["res"][1] == 1)'),
    ("命中 27 輪", "== (36, 28, 8, 2), STATS", "== (36, 27, 9, 2), STATS"),
    ("sfx 數不等於探針數", 'assert STATS["sfx"] == sum(PROBE_E.values())', 'assert STATS["sfx"] == sum(PROBE_E.values()) + 1'),
    ("改 [11] 就會心", '[(r["att"], r["res"][0], r["res"][1]) for r in IN11 if r["att"] == 2] == [(2, 0, 0)]',
     '[(r["att"], r["res"][0], r["res"][1]) for r in IN11 if r["att"] == 2] == [(2, 0, 1)]'),
    ("窗起點 9", '{"p01_crit": 8, "p02_restore": 10', '{"p01_crit": 9, "p02_restore": 10'),
    ("會心傷害較小", "assert max(NONCRIT_ARES_DMG) < min(c[5] for c in CRITS)", "assert max(NONCRIT_ARES_DMG) > min(c[5] for c in CRITS)"),
    ("HP 不歸零下限", "all(h2 == max(0, h1 - d) for _a, _b, _t, h1, d, h2 in HP_CHECK)",
     "all(h2 == h1 - d for _a, _b, _t, h1, d, h2 in HP_CHECK)"),
    ("未命中也扣血", 'dmg = sum(r["res"][5] for r in mid if r["tgt"] == t and r["res"][0] == 0)',
     'dmg = sum(r["res"][5] + r["res"][0] for r in mid if r["tgt"] == t)'),
    # (E) event 82
    ("目標本來就 12", '\\\n    and BP["bpreg_hit"]["regs"]["EBP"] == "0x13"', '\\\n    and BP["bpreg_hit"]["regs"]["EBP"] == "0xc"'),
    ("擊殺在第 2 回合", 'KILL[0]["phase"] == (1, "player")', 'KILL[0]["phase"] == (2, "player")'),
    ("event 82 同回合派送", '(hex(EV82), (2, "enemy"))], [(hex(st(c))', '(hex(EV82), (1, "enemy"))], [(hex(st(c))'),
    ("row0 = 目前回合", "== (1, (2, 82, 0), 1)", "== (1, (1, 82, 0), 1)"),
    ("對話參數 2", "assert [c.stack[1] for c in D82] == [3]", "assert [c.stack[1] for c in D82] == [2]"),
    ("增援 group 0", "and [c.stack[0] for c in SP82] == [1]", "and [c.stack[0] for c in SP82] == [0]"),
    ("event 82 在 AI 之後", "inside.seq < C82.seq < ai_after.seq", "ai_after.seq < C82.seq"),
    ("event 82 兩次", "sum(1 for c in EB if st(c) == EV82) == 1", "sum(1 for c in EB if st(c) == EV82) == 2"),
    ("呼叫紀錄 md5 錯", '"lc192b": "25244d521dec6935e46e09964e4de388"', '"lc192b": "25244d521dec6935e46e09964e4de389"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s192", MUTANTS))
