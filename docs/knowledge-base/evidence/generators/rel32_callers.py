# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""位元組層級找 E8 / E9 rel32 指向目標的位置(不靠線性反組譯,不會因資料夾在碼段中而漏掉)。

用法:python rel32_callers.py <target_hex> [...]
每個命中再以「從命中處反組譯 1 條」確認是 call/jmp 且目標相符;自我檢查用已知呼叫點:
0x1a251 call 0x10010、0x26130 call 0x10010、0x25dbd call 0x25ebb 必須都找到。
"""
from __future__ import annotations

import struct
import sys

sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
import disasm_le as D  # noqa: E402

EXE = r"C:/Users/kg701/Desktop/GAME/FD2/FD2.EXE"
d = open(EXE, "rb").read()
meta = D.parse_le(d)
code, base = D.load_code(d, meta)
md = D._capstone()


def callers(tgt: int) -> list[tuple[int, str]]:
    out = []
    for i in range(len(code) - 5):
        op = code[i]
        if op not in (0xE8, 0xE9):
            continue
        rel = struct.unpack_from("<i", code, i + 1)[0]
        if base + i + 5 + rel != tgt:
            continue
        ins = next(md.disasm(code[i:i + 5], base + i), None)
        if ins and ins.mnemonic in ("call", "jmp") and int(ins.op_str, 16) == tgt:
            out.append((base + i, ins.mnemonic))
    return out


got = {a for a, _ in callers(0x10010)} | {a for a, _ in callers(0x25EBB)}
assert {0x1A251, 0x26130, 0x25DBD} <= got, sorted(hex(x) for x in got)
assert callers(0x10011) == [] or all(a not in (0x1A251, 0x26130) for a, _ in callers(0x10011)), "非恆真"
for t in sys.argv[1:]:
    tv = int(t, 16)
    print(hex(tv), [(hex(a), m) for a, m in callers(tv)])
