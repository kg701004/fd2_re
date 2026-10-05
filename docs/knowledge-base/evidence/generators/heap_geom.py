# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十三:調色盤區塊(名冊 + 0xa00)之前的堆積排列 —— 界定 heap_free_block 往後走訪會不會碰到假的空閒標頭。

用法:python heap_geom.py <inst> <out_dir> <tag>
1. 讀堆積描述 0x527b0(free 包裝 0x3777e 固定傳這個 ebx):+8 rover、+0x18 空閒數、+0x1c 假頭節點(+0x20 尾、+0x24 首)。
2. 從首節點沿 +8 走空閒串列到回到假頭,得到所有真正的空閒區塊。
3. H = 名冊 [0x53bf7] + 0xa00(調色盤區塊標頭,斷言 = [0x53a65] - 4)。F = 位址 < H 的最後一個空閒區塊。
4. 從 F 沿「標頭 & ~1」實體往後走,必須剛好走到 H;途中每個使用中區塊就是「被釋放時往後走訪可能走到 H」的候選。
5. 每個候選以 obj2 全域(0x53a00..0x54000)中等於「區塊 + 4」的 dword 標出擁有者。
"""
from __future__ import annotations

import json
import struct
import sys
import time

from live import DELTA, ROOT, Live
from live import run as hrun

inst, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
L = Live(inst, ROOT / out)
# 必須用 halt():raw enter-debugger 可能停在 DOS 呼叫裡,selector 0170 不是遊戲的(第一次 geo0 讀到全 0 描述)
assert L.halt(), "halt"


def G(a: int) -> int:
    return L.d32(a + DELTA)


D = 0x527B0 + DELTA
desc = L.dump(D, 0x40, f"{tag}_desc")
dw = struct.unpack("<16I", desc)
head = D + 0x1C
assert dw[2] != 0 and 0x100000 < dw[0x24 // 4] < 0x400000, ("descriptor looks invalid", [hex(x) for x in dw])
# 一次傾印整段堆積,離線走串列(逐節點讀太慢)
R0, R1 = 0x1E0000, 0x320000
heap = L.dump(R0, R1 - R0, f"{tag}_heap")


def rd(addr: int, n: int) -> bytes:
    if R0 <= addr and addr + n <= R1:
        return heap[addr - R0:addr - R0 + n]
    return L.dump(addr, n, "hg_node")


nodes = []
p = dw[0x24 // 4]
for _ in range(20000):
    if p == head:
        break
    sz, prv, nxt = struct.unpack("<3I", rd(p, 12))
    nodes.append({"addr": p, "hdr": sz, "prev": prv, "next": nxt})
    p = nxt
else:
    raise SystemExit("free list did not close")
assert all(n["hdr"] & 1 == 0 for n in nodes), "free node with in-use bit"
roster, pal = G(0x53BF7), G(0x53A65)
H = roster + 0xA00
assert H == pal - 4, (hex(H), hex(pal))
before = [n for n in nodes if n["addr"] < H]
F = max(before, key=lambda n: n["addr"]) if before else None
gl = L.dump(0x53A00 + DELTA, 0x600, f"{tag}_globals")
gptr = {}
for i in range(0, 0x600, 4):
    v = struct.unpack_from("<I", gl, i)[0]
    gptr.setdefault(v, []).append(hex(0x53A00 + i))
chain = []
if F is not None:
    span = H + 0x10 - F["addr"]
    assert span < 0x200000, span
    mem = rd(F["addr"], span)
    off = 0
    while F["addr"] + off < H:
        h = struct.unpack_from("<I", mem, off)[0]
        size = h & ~1
        assert size > 0, (hex(F["addr"] + off), hex(h))
        blk = F["addr"] + off
        chain.append({"blk": hex(blk), "hdr": hex(h), "size": size, "in_use": bool(h & 1),
                      "owners": gptr.get(blk + 4, []), "is_free_node": any(n["addr"] == blk for n in nodes)})
        off += size
    assert F["addr"] + off == H, ("walk overshot", hex(F["addr"] + off), hex(H))
res = {"heap_dump": f"{tag}_heap.bin", "heap_range": [hex(R0), hex(R1)], "desc_dwords": [hex(x) for x in dw], "rover": hex(dw[2]), "numfree_+0x18": dw[6], "free_nodes": len(nodes),
       "H_pal_hdr": hex(H), "H_hdr_value": L.dump(H, 4, f"{tag}_H").hex(), "roster": hex(roster), "pal": hex(pal),
       "F": {k: hex(v) for k, v in F.items()} if F else None,
       "free_nodes_before_H": len(before), "free_nodes_after_H": len(nodes) - len(before),
       "chain_F_to_H": chain,
       "candidates_in_use": [c for c in chain if c["in_use"]]}
(L.out / f"{tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: res[k] for k in res if k not in ("chain_F_to_H", "desc_dwords")}, ensure_ascii=False)[:3000])
L.resume()
