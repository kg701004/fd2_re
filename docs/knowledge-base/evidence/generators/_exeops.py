"""FD2.EXE 的指令運算元:產生器裡手寫的欄位位移 / 常數,改由遊戲程式裡讀寫那個欄位的那一條指令取(獨立來源)。

用法:
    operand(0x2FA79, "movzx edx, byte ptr [ebp + ", "]")   # → 8(攻擊經驗值讀攻方 +8)

指令文字是 capstone 的 Intel 寫法(10 以上的數字寫成 0x 十六進位);前後綴不符就 AssertionError,
所以位址或前後綴被改到時是判準擋下,不是剛好跑不下去。
"""
from __future__ import annotations

import re
import sys

from _evpaths import GAME, ROOT

sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

_EXE = (GAME / "FD2.EXE").read_bytes()
_META = dl.parse_le(_EXE)
_CODE, _CBASE = dl.load_code(_EXE, _META)
_MD = dl._capstone()
_NUM = re.compile(r"0x[0-9a-f]+|[0-9]")


def insn(addr: int) -> str:
    """靜態線性位址 addr 那一條指令的文字(助憶符 + 運算元)。

    Raises:
        AssertionError: 該位址解不出指令。
    """
    i = next(_MD.disasm(_CODE[addr - _CBASE:addr - _CBASE + 16], addr, 1), None)
    assert i is not None, hex(addr)
    return f"{i.mnemonic} {i.op_str}"


def operand(addr: int, before: str, after: str = "") -> int:
    """addr 那一條指令的文字必須正好是 before + 數字 + after,回傳那個數字。

    Raises:
        AssertionError: 前後綴不符,或中間不是一個數字。
    """
    text = insn(addr)
    mid = text[len(before):len(text) - len(after)] if text.startswith(before) and text.endswith(after) else ""
    assert _NUM.fullmatch(mid), (hex(addr), text, before, after)
    return int(mid, 0)
