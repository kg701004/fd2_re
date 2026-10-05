# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""離線分析 heap_geom 的傾印(<tag>_heap.bin = linear 0x1e0000..0x320000、<tag>_desc.bin、<tag>_globals.bin)。

用法:python heap_geom_off.py <dir> <tag> <H_hex> [--selftest]
- 空閒串列:從描述 +0x24 沿 +8 走到回到假頭(描述 + 0x1c)。
- 對每個位址 < H 的空閒節點(由高到低)實體往後走(標頭 & ~1),遇到 0xffffffff(miniheap 結尾)或越過 H 就換下一個;
  第一個剛好走到 H 的就是 F。F 與 H 之間的使用中區塊 = 被釋放時往後走訪會先碰到 H(假空閒)的候選。
- 也從 H 往後走,列出 H 之後到下一個真正空閒區塊之間的區塊(這些被釋放時不會碰到 H:走訪只往後)。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

d, tag, H = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3], 16)
R0, R1 = 0x1E0000, 0x320000
heap = (d / f"{tag}_heap.bin").read_bytes()
assert len(heap) == R1 - R0, len(heap)
desc = struct.unpack("<16I", (d / f"{tag}_desc.bin").read_bytes())
gl = (d / f"{tag}_globals.bin").read_bytes()
D = 0x527B0 + 0x19C000
head = D + 0x1C


def u32(a: int) -> int:
    return struct.unpack_from("<I", heap, a - R0)[0]


nodes = []
p = desc[0x24 // 4]
seen = set()
while p != head:
    assert p not in seen and R0 <= p < R1, hex(p)
    seen.add(p)
    nodes.append(p)
    p = u32(p + 8)
for a in nodes:
    assert u32(a) & 1 == 0, hex(a)
    assert u32(u32(a + 8) + 4) == a if u32(a + 8) != head else True, ("broken back link", hex(a))
gptr: dict[int, list[str]] = {}
for i in range(0, len(gl), 4):
    gptr.setdefault(struct.unpack_from("<I", gl, i)[0], []).append(hex(0x53A00 + i))


def walk(start: int, stop: int) -> tuple[str, list[dict]]:
    out, a = [], start
    while a < stop:
        h = u32(a)
        if h == 0xFFFFFFFF:
            return "end_marker", out
        out.append({"blk": hex(a), "hdr": hex(h), "size": h & ~1, "in_use": bool(h & 1),
                    "free_node": a in seen, "owners": gptr.get(a + 4, [])})
        if h & ~1 == 0:
            return "zero_size", out
        a += h & ~1
    return ("hit" if a == stop else "overshoot"), out


res = {"free_nodes": len(nodes), "H": hex(H), "H_hdr": hex(u32(H)), "tries": []}
F = None
for a in sorted((x for x in nodes if x < H), reverse=True):
    how, ch = walk(a, H)
    res["tries"].append({"from": hex(a), "result": how, "blocks": len(ch)})
    if how == "hit":
        F, chain = a, ch
        break
res["F"] = hex(F) if F else None
if F:
    res["chain_F_to_H"] = chain
    res["candidates_in_use"] = [c for c in chain[1:] if c["in_use"]]
    res["free_in_between"] = [c for c in chain[1:] if not c["in_use"]]
# H 之後(用真正的標頭大小 0x304 不行 —— H 被改壞前的值才是真的;這裡只列 H 本身的標頭)
out = d / f"{tag}_offline.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: res[k] for k in res if k not in ("chain_F_to_H",)}, ensure_ascii=False)[:4000])
