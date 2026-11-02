"""ev_s187.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s187.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 玩家開寶箱的順序
    ("金錢先寫旗標再等鍵", "assert _ITEM_FLAG < _ITEM_WAIT and _GOLD_WAIT < _GOLD_ADD < _GOLD_FLAG",
     "assert _ITEM_FLAG < _ITEM_WAIT and _GOLD_FLAG < _GOLD_WAIT"),
    ("道具也是先等鍵", "assert _ITEM_FLAG < _ITEM_WAIT and _GOLD_WAIT < _GOLD_ADD < _GOLD_FLAG",
     "assert _ITEM_WAIT < _ITEM_FLAG and _GOLD_WAIT < _GOLD_ADD < _GOLD_FLAG"),
    ("等鍵記成顯示那一條", '(0x194D6, f"call {WAIT_KEY:#x}", "等鍵")', '(0x194C2, f"call {WAIT_KEY:#x}", "等鍵")'),
    ("旗標用 esi 索引", '(0x194F3, "mov byte ptr [edi + eax], 1"', '(0x194F3, "mov byte ptr [esi + eax], 1"'),
    ("等鍵到寫旗標中間有跳", 'not any(i.mnemonic.startswith(("j", "ret")) for i in _STRAIGHT)',
     'any(i.mnemonic.startswith(("j", "ret")) for i in _STRAIGHT)'),
    ("等鍵函式不等鍵", '"等到 BIOS 鍵盤緩衝區有鍵為止" in', '"不等鍵" in'),
    ("金錢種類記成 0", "GOLD = 1\n", "GOLD = 0\n"),
    ("可見 / 隱藏對調", "CHEST_MASK, CHEST_VISIBLE, CHEST_HIDDEN = 0x60, 0x20, 0x40", "CHEST_MASK, CHEST_VISIBLE, CHEST_HIDDEN = 0x60, 0x40, 0x20"),
    ("問句字串對調", "STR_ASK_VIS, STR_ASK_HID, STR_GOLD_VIS, STR_GOLD_HID = 0x1A5, 0x1AC, 0x1AA, 0x1AE",
     "STR_ASK_VIS, STR_ASK_HID, STR_GOLD_VIS, STR_GOLD_HID = 0x1AC, 0x1A5, 0x1AA, 0x1AE"),
    # (C) 第 10 張圖
    ("金額記成 3000", "OPENED_GOLD = 5000", "OPENED_GOLD = 3000"),
    ("槽號取 byte 3", "_comp[o + 2] & 0x1F", "_comp[o + 3] & 0x1F"),
    ("doc25 槽號記成 9", "DOC25_SLOT = 10", "DOC25_SLOT = 9"),
    ("窗口 8 格", "WINDOW = 12", "WINDOW = 8"),
    # (B) 讀值與畫面
    ("YES 之後畫面有變", "assert len(H_AFTER) == 1 and", "assert len(H_AFTER) == 2 and"),
    ("問句畫面也算 YES 之後", 'SHOT_AFTER = ["60_after_yes.png"]', 'SHOT_AFTER = ["53_final.png", "60_after_yes.png"]'),
    ("指標再加 DELTA", "OPENED_PTR = 0x1F6C5C ", "OPENED_PTR = 0x1F6C5C + 0x19C000 "),
    ("讀值不是全 0", "f == [0] * WINDOW for _, _, p, f in READS", "f != [0] * WINDOW for _, _, p, f in READS"),
    ("stdout 順序換", '["recover_state.py", "continue_from_ring.py", "confirm_open_chest.py", "recover_state.py"]',
     '["continue_from_ring.py", "recover_state.py", "confirm_open_chest.py", "recover_state.py"]'),
    ("YES 之後讀三次", "assert N_AFTER_YES == 2 and", "assert N_AFTER_YES == 3 and"),
    ("confirm 之後還送鍵", 'assert KEYS == {"confirm_open_chest.py": ["Return"],', 'assert KEYS == {"confirm_open_chest.py": ["Return", "Return"],'),
    ("舊讀法有加 DELTA", r'r"S\.read_mem\(NAME, (ptr|chest_ptr), min_bytes=16\)"',
     r'r"S\.read_mem\(NAME, (ptr|chest_ptr) \+ S\.NATIVE_LIVE_DELTA, min_bytes=16\)"'),
    # (D) real_open1 .. 5
    ("有單位站上目標格", 'assert not any(v["ally_on_target"] for v in RO.values()), RO', 'assert any(v["ally_on_target"] for v in RO.values()), RO'),
    ("real_open5 有結果檔", 'assert not (SWEEP / "real_open5/result.json").exists()', 'assert (SWEEP / "real_open5/result.json").exists()'),
    ("5c 當在寫檔之後", "assert L_CAMP < L_AFTER_READ < L_CRASH_C < L_WRITE", "assert L_CAMP < L_AFTER_READ < L_WRITE < L_CRASH_C"),
    ("5b 當在開箱之後", '"real_open5b.log": {"main_line": L_CAMP,', '"real_open5b.log": {"main_line": L_CRASH_C,'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s187", MUTANTS))
