"""ev_s188.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s188.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 字串號 / 金額
    ("問句記成隱藏格的", "STR_ASK_VIS, STR_GOLD_VIS, STR_GOLD_HID = 0x1A5, 0x1AA, 0x1AE",
     "STR_ASK_VIS, STR_GOLD_VIS, STR_GOLD_HID = 0x1AC, 0x1AA, 0x1AE"),
    ("可見 / 隱藏金額句對調", "STR_ASK_VIS, STR_GOLD_VIS, STR_GOLD_HID = 0x1A5, 0x1AA, 0x1AE",
     "STR_ASK_VIS, STR_GOLD_VIS, STR_GOLD_HID = 0x1A5, 0x1AE, 0x1AA"),
    ("金額記成 3000", "OPENED_GOLD = 5000", "OPENED_GOLD = 3000"),
    ("FDTXT 只有 34 份", "assert len(STRS) == 35", "assert len(STRS) == 34"),
    # (A) ev_s138 對照
    ("ev_s138 對白在下一列", "ln[\"y\"] == Y138 and", "ln[\"y\"] == Y138 + 1 and"),
    ("ev_s138 對白錯一格", "assert cells[k:k + len(G138)] == [[g] for g in G138], cells",
     "assert cells[k + 1:k + 1 + len(G138)] == [[g] for g in G138], cells"),
    ("ev_s138 對白在第 3 行", "[(w[0], w[1], 4) for w in", "[(w[0], w[1], 3) for w in"),
    ("對照圖上還有別的字", "== len(cells) == k + len(G138), (r[\"hits\"]", "== len(cells) == k + len(G138) + 1, (r[\"hits\"]"),
    # (B) 開箱序列
    ("序列 30 張", "assert len(SEQ) == 29,", "assert len(SEQ) == 30,"),
    ("讀不了的圖算沒字", "NOTEXT = sorted(n for n, r in SHOT.items() if r[\"readable\"] and r[\"hits\"] == 0)",
     "NOTEXT = sorted(n for n, r in SHOT.items() if not r[\"readable\"] or r[\"hits\"] == 0)"),
    ("金額畫面少一張", 'assert GOLD == sorted(S187["screens"]["after_yes"]["files"]), GOLD',
     'assert GOLD == sorted(S187["screens"]["after_yes"]["files"])[1:], GOLD'),
    ("9 張是兩種畫面", "assert len({md5(SHOTS / n) for n in GOLD}) == 1", "assert len({md5(SHOTS / n) for n in GOLD}) == 2"),
    ("問句第一次在 52", 'min(ASK) == "51_wait_confirmed.png"', 'min(ASK) == "52_poll_0.png"'),
    ("沒有讀不了的圖", 'assert UNREADABLE == ["40_selected.png"], UNREADABLE', "assert UNREADABLE == [], UNREADABLE"),
    ("按鍵後畫面還有字", 'assert "70_clear0.png" in NOTEXT and', 'assert "70_clear0.png" not in NOTEXT and'),
    ("第一行也對上隱藏句", "assert L1 == [(FD0, STR_GOLD_VIS, 0)], L1", "assert L1 == [(FD0, STR_GOLD_VIS, 0), (FD0, STR_GOLD_HID, 0)], L1"),
    ("第二行只對上可見句", "assert L2 == [(FD0, STR_GOLD_VIS, 1, [OPENED_GOLD]), (FD0, STR_GOLD_HID, 1, [OPENED_GOLD])], L2",
     "assert L2 == [(FD0, STR_GOLD_VIS, 1, [OPENED_GOLD])], L2"),
    ("隱藏句也完整", 'assert not any(b["string"] == STR_GOLD_HID and b["complete"] for b in G0["boxes"])',
     'assert any(b["string"] == STR_GOLD_HID and b["complete"] for b in G0["boxes"])'),
    ("金額畫面 24 個字", 'assert G0["hits"] == n_cells(G0) == 23', 'assert G0["hits"] == n_cells(G0) == 24'),
    # (C) 按鍵之後
    ("清對話按了兩次", '"  LOG: battle HUD recovered after 1 clear-Return(s)"', '"  LOG: battle HUD recovered after 2 clear-Return(s)"'),
    ("有第二張清對話圖", '== ["70_clear0.png"]', '== ["70_clear0.png", "70_clear1.png"]'),
    ("清對話在 99 之前", 'assert T["99_recovery.png"] < T["70_clear0.png"] <', 'assert T["70_clear0.png"] < T["99_recovery.png"] <'),
    ("按鍵後有讀旗標", "assert not READ_AFTER", "assert READ_AFTER"),
    ("recover_state 有送鍵", 'and "send_keys" not in REC', 'and "send_keys" in REC'),
    ("遊戲有存檔", "assert md5(SAV0) == md5(SAV1)", "assert md5(SAV0) != md5(SAV1)"),
    # (E) 實機 lc188a
    ("EXE 不是原版", 'MD5_EXE = "33464c81e6a364fd0660141139aa8e6e"', 'MD5_EXE = "72e36e47"'),
    ("等鍵回返位址 +6", "RET = GOLD_WAIT_CALL + 5", "RET = GOLD_WAIT_CALL + 6"),
    ("開的是 slot 10", "OPENED_PTR, SLOT, UNIT, START_XY, CHEST_XY = 0x1F6C5C, 9,", "OPENED_PTR, SLOT, UNIT, START_XY, CHEST_XY = 0x1F6C5C, 10,"),
    ("單位 11 起點 (3,8)", "START_XY, CHEST_XY = 0x1F6C5C, 9, 11, [2, 10], [3, 8]", "START_XY, CHEST_XY = 0x1F6C5C, 9, 11, [3, 8], [3, 8]"),
    ("YES 後旗標已寫", 'assert S2["flags"] == S1["flags"] and', 'assert S2["flags"] != S1["flags"] and'),
    ("YES 後錢已加", 'S2["money"] == S1["money"] and S2["amount"]', 'S2["money"] == S1["money"] + OPENED_GOLD and S2["amount"]'),
    ("按鍵後旗標仍 0", 'assert S3["flags"][SLOT] == 1 and', 'assert S3["flags"][SLOT] == 0 and'),
    ("按鍵後錢加 3000", 'assert S3["money"] - S2["money"] == OPENED_GOLD and', 'assert S3["money"] - S2["money"] == 3000 and'),
    ("兩次讀之間按了兩鍵", '"s02->s03": ["Return"]}, KB', '"s02->s03": ["Return", "Return"]}, KB'),
    ("YES 前多按一鍵", '"s0r->s01": ["Down", "Return"]', '"s0r->s01": ["Down", "Return", "Return"]'),
    ("按鍵後畫面還有字", 'assert TX["t03"]["readable"] and TX["t03"]["hits"] == 0', 'assert TX["t03"]["readable"] and TX["t03"]["hits"] > 0'),
    ("YES 後是隱藏句", "assert complete(TX[\"t02\"]) == complete(TX[\"t02b\"]) == [(FD0, STR_ASK_VIS, []), (FD0, STR_GOLD_VIS, [OPENED_GOLD])]",
     "assert complete(TX[\"t02\"]) == complete(TX[\"t02b\"]) == [(FD0, STR_ASK_VIS, []), (FD0, STR_GOLD_HID, [OPENED_GOLD])]"),
    ("等鍵進來兩次", "assert len(GOLD_E) == 1, [(c.seq", "assert len(GOLD_E) == 2, [(c.seq"),
    ("等鍵回傳 Esc", "SC_RETURN, SC_ALT = 0x1C, 0x38", "SC_RETURN, SC_ALT = 0x01, 0x38"),
    ("金額在 esi", 'assert (CALL.regs["ebx"], CALL.regs["edi"])', 'assert (CALL.regs["esi"], CALL.regs["edi"])'),
    ("槽號在 ebp", 'assert (CALL.regs["ebx"], CALL.regs["edi"])', 'assert (CALL.regs["ebx"], CALL.regs["ebp"])'),
    ("紀錄沒有截斷", "assert LG.calls_parsed and LG.tail_cut", "assert LG.calls_parsed and not LG.tail_cut"),
    ("中間沒有除錯器 Alt", "set(MAKES[:-1]) <= {SC_ALT}", "set(MAKES[:-1]) == set()"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s188", MUTANTS))
