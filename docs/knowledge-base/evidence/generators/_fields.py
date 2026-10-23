"""證據欄位的鍵名位移核對:鍵名寫的位移(手寫在鍵上)與產生器讀值的位移(手寫在程式裡)分開寫,逐欄比對。

鍵名格式(位移一律十六進位,不帶 0x):
    "lv_+21"            單一欄位:值 = 該位移的欄位(預設 1 byte)
    "hp_+40_+42"        多個欄位:值 = 各位移的欄位依序組成的 list
    "+5..+9"            連續範圍(含兩端):值 = 該範圍 bytes 組成的 list
鍵名裡沒有 "+位移" 的欄位不核對;欄位寬度依鍵名前綴(第一個 "_" 之前)查 widths,沒有就是 1 byte。
"""
from __future__ import annotations

import re
import struct
from typing import Any

_OFF = re.compile(r"\+([0-9a-fA-F]+)")


def key_offsets(key: str) -> tuple[list[int], bool]:
    """回傳 (鍵名裡的位移, 是否為 a..b 範圍)。"""
    offs = [int(x, 16) for x in _OFF.findall(key)]
    return offs, ".." in key


def field_value(raw: bytes, key: str, widths: dict[str, str]) -> Any:
    """依鍵名從 raw 讀出值(與產生器的讀法無關)。鍵名沒有位移時回傳 None。"""
    offs, is_range = key_offsets(key)
    if not offs:
        return None
    if is_range:
        assert len(offs) == 2 and offs[0] <= offs[1], key
        return list(raw[offs[0]:offs[1] + 1])
    fmt = widths.get(key.split("_")[0], "<B")
    vals = [struct.unpack_from(fmt, raw, o)[0] for o in offs]
    return vals[0] if len(vals) == 1 else vals


def check_offset_keys(fields: dict[str, Any], raw: bytes, widths: dict[str, str]) -> int:
    """fields 裡每個帶位移的鍵,值都要等於依鍵名讀出的值;回傳核對的欄位數(至少 1)。

    Raises:
        AssertionError: 任一欄位不符,或沒有任何可核對的鍵。
    """
    n = 0
    for k, v in fields.items():
        want = field_value(raw, k, widths)
        if want is None:
            continue
        assert v == want, (k, v, want)
        n += 1
    assert n, list(fields)
    return n
