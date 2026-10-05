"""續七十四:離線走一份堆積傾印的空閒串列(描述 0x527b0 +0x24 首節點,沿 +8 到回到假頭 0x527cc),
回報節點數、是否含指定區塊、反向連結是否一致、描述的 numfree(+0x18)與實際節點數的差。

用法:python walk_after.py <heap.bin> <desc.bin> [blk_hex ...]
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

R0, R1 = 0x1E0000, 0x320000
heap = Path(sys.argv[1]).read_bytes()
assert len(heap) == R1 - R0, len(heap)
desc = struct.unpack("<16I", Path(sys.argv[2]).read_bytes())
want = [int(x, 16) for x in sys.argv[3:]]
HEAD = 0x527B0 + 0x19C000 + 0x1C


def u32(a: int) -> int | None:
    if R0 <= a and a + 4 <= R1:
        return struct.unpack_from("<I", heap, a - R0)[0]
    return None


nodes, bad_back, p, seen = [], [], desc[0x24 // 4], set()
while p != HEAD:
    if p in seen or u32(p) is None:
        nodes.append({"stop": hex(p), "why": "loop" if p in seen else "outside_dump"})
        break
    seen.add(p)
    nxt = u32(p + 8)
    nodes.append({"addr": hex(p), "hdr": hex(u32(p)), "prev": hex(u32(p + 4)), "next": hex(nxt)})
    if nxt != HEAD and u32(nxt + 4) != p:
        bad_back.append(hex(p))
    p = nxt
res = {"nodes": len([n for n in nodes if "addr" in n]), "numfree_desc_18": desc[6], "numalloc_desc_14": desc[5],
       "rover_8": hex(desc[2]), "desc_c": hex(desc[3]), "desc_10": hex(desc[4]), "closed": p == HEAD,
       "bad_back_links": bad_back, "contains": {hex(w): any(n.get("addr") == hex(w) for n in nodes) for w in want},
       "tail_20": hex(desc[8]), "first_24": hex(desc[9])}
for w in want:
    res[f"hdr_{w:x}"] = hex(u32(w)) if u32(w) is not None else None
print(json.dumps(res, indent=1))
