"""ev_s193.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s193.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 靜態:出口與呼叫端
    ("取消出口 EDI = 1", '"jne 0x2b0b8", "mov edi, 0xffffffff"]', '"jne 0x2b0b8", "mov edi, 1"]'),
    ("迴圈還有第三個出口", "assert EDI_WRITES == [0x2B0B3, 0x2B0E7]", "assert EDI_WRITES == [0x2B0B3, 0x2B0E7, 0x2B1B1]"),
    ("寫入篩選把 test 算進去", '              and i.mnemonic not in ("cmp", "test")]', '              and i.mnemonic != "cmp"]'),
    ("Del 不等於 Esc", '"jne 0x2b73d", "mov byte ptr [0x3a8e], 1"]', '"jne 0x2b73d", "mov byte ptr [0x3a8e], 0x1c"]'),
    ("進入不清旗標", '"xor edi, edi", "push 0x1e", "push edi"', '"xor edi, edi", "push 0x1f", "push edi"'),
    ("呼叫端一取消就離開", '"call 0x2af28", "test eax, eax", "je 0x26347"]', '"call 0x2af28", "test eax, eax", "je 0x2637f"]'),
    ("呼叫端一有人數門檻", 'assert not any("0x3bfb" in t for t in CALLER1)', 'assert any("0x3bfb" in t for t in CALLER1)'),
    ("呼叫端二門檻 15", '"cmp dword ptr [0x3bfb], 0x10"', '"cmp dword ptr [0x3bfb], 0xf"'),
    ("呼叫端二取消再叫", '["call 0x2af28", "test eax, eax", "je 0x29867"]', '["call 0x2af28", "test eax, eax", "je 0x267e6"]'),
    ("只有一個呼叫端", "assert CALLERS == [0x26351, 0x267E6]", "assert CALLERS == [0x26351]"),
    ("旗標章節含 25", "assert FLAGGED == [22, 23, 24, 27, 28, 29]", "assert FLAGGED == [22, 23, 24, 25, 27, 28, 29]"),
    ("目標 19 從 byte 23 起", "TARGET = lambda ch: 19 if ch > 0x1A else 15", "TARGET = lambda ch: 19 if ch > 0x16 else 15"),
    # (B) 名冊人數
    ("入隊是 dec", '(0x1144C, "inc dword ptr [0x3bfb]")', '(0x1144C, "dec dword ptr [0x3bfb]")'),
    ("寫入篩選漏 mov", 'i.mnemonic not in ("cmp", "push", "test"))', 'i.mnemonic not in ("cmp", "push", "test", "mov"))'),
    ("讀檔取 +2", 'insn(0x2606C) == "movzx eax, byte ptr [ebx + 1]"', 'insn(0x2606C) == "movzx eax, byte ptr [ebx + 2]"'),
    ("入隊呼叫點 27", "assert len(JOIN_CALLS) == 28", "assert len(JOIN_CALLS) == 27"),
    ("巢狀入隊 3", "sum(h[3] for h in HANDLERS) == 2", "sum(h[3] for h in HANDLERS) == 3"),
    ("保守下界不扣條件", "    strict = sum(h[2] for h in HANDLERS if h[0] < ch - 1 and not h[4])",
     "    strict = sum(h[2] for h in HANDLERS if h[0] < ch - 1)"),
    ("下界算到本章", "if h[0] < ch - 1 and not h[4])", "if h[0] <= ch and not h[4])"),
    ("可選 = 名冊人數", "BOUNDS[ch][1] - 1 - TARGET(ch))", "BOUNDS[ch][1] - TARGET(ch))"),
    ("可選 = 名冊人數(dec edx 不在)", '"mov edx, dword ptr [0x3bfb]", "dec edx", "cmp eax, edx"]',
     '"mov edx, dword ptr [0x3bfb]", "cmp eax, edx"]'),
    # (C) lc192b
    ("呼叫紀錄 md5 錯", 'LC192B_MD5 = "25244d521dec6935e46e09964e4de388"', 'LC192B_MD5 = "25244d521dec6935e46e09964e4de389"'),
    ("取消時 EDI = 0", '("esc", 0, 0, 0),\n               ("out", 6, 0xFFFFFFFF, 0x13)', '("esc", 0, 0, 0),\n               ("out", 6, 0, 0x13)'),
    ("Esc 後只進一次", '("out", 6, 0xFFFFFFFF, 0x13), ("in", 5, 0, 0x13), ("in", 5, 0, 0x13),',
     '("out", 6, 0xFFFFFFFF, 0x13),'),
    ("暫存器讀成 esi", 'c.stack[1], c.regs["edi"], c.regs["ebp"]', 'c.stack[1], c.regs["esi"], c.regs["ebp"]'),
    ("不收 Esc 鍵", "if k.data in (0x01, 0x53):", "if k.data in (0x53,):"),
    ("再進之前有詢問", 'assert all(e[0] != "ask" for e in SEQ[I_OUT1:])', 'assert any(e[0] == "ask" for e in SEQ[I_OUT1:])'),
    ("詢問來自 town_hub_select", '[("ask", "0x262d5", 0, 0)', '[("ask", "0x267a5", 0, 0)'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s193", MUTANTS))
