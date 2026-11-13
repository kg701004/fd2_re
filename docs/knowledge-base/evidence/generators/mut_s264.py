"""ev_s264.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s264.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 0x5417c
    ("呼叫端寫到別段", "assert fixups_in(0x37DE7) == [AIL_BUF]", "assert fixups_in(0x37DE7) == [AIL_BUF + 1]"),
    ("strcpy 不寫 NUL", '"mov cl, byte ptr [edx]", "mov byte ptr [eax], cl", "cmp cl, 0", "je 0x400f2"',
     '"mov cl, byte ptr [edx]", "cmp cl, 0", "je 0x400f2", "mov byte ptr [eax], cl"'),
    ("localtime 只叫一次 __brktime", '"push eax", "push esi", "push 0x63df", "call 0x47525", "add esp, 0x10", "mov eax, ebx"',
     '"push eax", "push esi", "push 0x63df", "call 0x4768d", "add esp, 0x10", "mov eax, ebx"'),
    ("時區調整是有號除法", '"add ebx, 0x15180", "mov esi, 0x15180", "sub ebx, eax", "xor edx, edx", "mov eax, ebx", "div esi"',
     '"add ebx, 0x15180", "mov esi, 0x15180", "sub ebx, eax", "xor edx, edx", "mov eax, ebx", "idiv esi"'),
    ("路徑一的 days 少扣到 −400", "DAYS_LO, DAYS_HI = DAYS0 - 1,", "DAYS_LO, DAYS_HI = DAYS0 - 400,"),
    ("time_t 當 33 位元", "DAYS0 + (2**32 - 1) // 86400", "DAYS0 + (2**33 - 1) // 86400"),
    ("月份比較少等號", "    if r >= tab[m + 1]:", "    if r > tab[m + 1]:"),
    ("日不加 1", "return y, m, r - tab[m] + 1, (days + 1) % 7", "return y, m, r - tab[m], (days + 1) % 7"),
    ("年迴圈不扣", "        y += 1\n        r -= lim", "        y += 1\n        r -= lim - 1"),
    ("閏年表第 3 格 59", "CUM[True] == [0, 31, 60,", "CUM[True] == [0, 31, 59,"),
    ("isdst 寫入篩選漏 mov", 'WRITERS = ("mov", "add",', 'WRITERS = ("add",'),
    ("isdst 寫 tm+0x10", '"dword ptr [ebp - 8]", "dword ptr [ebx + 0x20]"]', '"dword ptr [ebp - 8]", "dword ptr [ebx + 0x10]"]'),
    ("tm 推給 isleap", 'all(ISDST[k + 1].op_str == "0x47922"', 'all(ISDST[k + 1].op_str == "0x4768d"'),
    ("比較函式會寫", '"mov eax, dword ptr [eax]", "cmp eax, dword ptr [edx]"', '"mov dword ptr [eax], edx", "cmp eax, dword ptr [edx]"'),
    ("名稱表範圍多 1 byte", "image(0x51804, 0x5183D - 0x51804)", "image(0x51804, 0x5183E - 0x51804)"),
    ("asctime +0x18 是 NUL", "(0x18, 0x0A), (0x19, 0)", "(0x18, 0), (0x19, 0)"),
    ("下限不含 NUL", "STRCPY_WRITES = (AIL_BUF, AIL_BUF + FIRST_NUL + 1)", "STRCPY_WRITES = (AIL_BUF, AIL_BUF + FIRST_NUL)"),
    ("十位數不加 '0'", "return (0x30 + q) & 0xFF, (0x30 + r) & 0xFF", "return q & 0xFF, (0x30 + r) & 0xFF"),
    # (B) 0x52387
    ("第 6 byte 不是 0x84", "bytes((0x81, 0x80, 0x00, 0x82, 0x83, 0x84))", "bytes((0x81, 0x80, 0x00, 0x82, 0x83, 0x85))"),
    ("選項寫入篩選漏 mov", 'and i.mnemonic not in ("cmp", "push", "test")', 'and i.mnemonic not in ("cmp", "push", "test", "mov")'),
    ("5 也可由 inc 回繞", '"cmp dword ptr [0x3f4a], 4", "jle 0x2657c"]', '"cmp dword ptr [0x3f4a], 5", "jle 0x2657c"]'),
    ("入口比對 +2 是選項", '"movzx eax, byte ptr [eax + 1]", "cmp eax, dword ptr [0x3f4a]"',
     '"movzx eax, byte ptr [eax + 2]", "cmp eax, dword ptr [0x3f4a]"'),
    ("讀取的索引不是 0x53f4a", "assert fixups_in(0x27A4E) == [SEL]", "assert fixups_in(0x27A4E) == [SEL + 4]"),
    ("實機紀錄標題錯", "秘密商店（selection5）成功開啟", "秘密商店（selection4）成功開啟"),
    ("實機鍵位 Ctrl+F2", '"酒店前按 Shift+F1"', '"酒店前按 Ctrl+F2"'),
    ("截圖被換", 'FIG_SHA256 = "7d751ab8', 'FIG_SHA256 = "7d751ab9'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s264", MUTANTS))
