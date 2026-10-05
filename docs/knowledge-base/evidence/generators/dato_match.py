"""頭像緩衝區傾印 ↔ DATO.DAT 條目逐 byte 比對。用法:python dato_match.py <bin> [<bin> ...]

DATO.DAT:6 bytes 檔頭 + dword 偏移表(第 i 條 = [6+4i] .. [6+4(i+1)]),共 136 條。
0x111ba(0x51a70, old, i) 依這張表讀出第 i 條整段放進 malloc 的緩衝區,所以緩衝區開頭應與某一條完全相同。
自我檢查:先拿第 5 條本身當輸入,必須只比中第 5 條(工具能說不)。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from _evpaths import GAME  # noqa: E402

DATO = (GAME / "DATO.DAT").read_bytes()


def entries() -> list[bytes]:
    offs: list[int] = []
    i = 0
    while True:
        o = struct.unpack_from("<I", DATO, 6 + 4 * i)[0]
        offs.append(o)
        if o >= len(DATO):
            break
        i += 1
    return [DATO[offs[j]:offs[j + 1]] for j in range(len(offs) - 1)]


def match(buf: bytes, ents: list[bytes]) -> list[int]:
    return [i for i, e in enumerate(ents) if e and len(buf) >= len(e) and buf[:len(e)] == e]


def match_prefix(buf: bytes, ents: list[bytes]) -> list[int]:
    """傾印比條目短時:條目的前 len(buf) bytes 與傾印相同(傾印長度不足以涵蓋整條時用)。"""
    return [i for i, e in enumerate(ents) if e and e[:len(buf)] == buf[:len(e)] and min(len(e), len(buf)) >= 1024]


ENTS = entries()
assert match_prefix(ENTS[32][:0x4000], ENTS) == [32, 50], "selftest prefix dup"
assert match_prefix(ENTS[0][:0x4000], ENTS) == [0], "selftest prefix"
assert match_prefix(bytes(0x4000), ENTS) == [], "selftest prefix null"
assert match(ENTS[0] + b"\0" * 64, ENTS) == [0], "selftest"
assert match(ENTS[5] + b"\0" * 64, ENTS) == [5, 55], "selftest dup(第 5、55 條內容相同)"
assert match(ENTS[0][:-1], ENTS) == [], "selftest truncated"
assert match(b"\0" * 0x4000, ENTS) == [], "selftest null"
if __name__ == "__main__":
    print("entries", len(ENTS))
    for f in sys.argv[1:]:
        b = Path(f).read_bytes()
        print(Path(f).name, "full", match(b, ENTS), "prefix", match_prefix(b, ENTS))
