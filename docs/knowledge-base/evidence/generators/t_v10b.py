# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十二 v10b:調色盤快取 [0x53a65] 的區塊標頭被改壞之後,釋放 / 重新配置時會怎樣(項目 2)。

用法:
  python t_v10b.py <inst> <out_dir> info <tag>
  python t_v10b.py <inst> <out_dir> keys <tag> <keys逗號>                 —— 只送鍵、每鍵截圖(不下斷點)
  python t_v10b.py <inst> <out_dir> trace <tag> <keys逗號> [corrupt]     —— 下斷點後送鍵
trace 斷點:0x111ba 入口(載入資源)、0x1013e(新調色盤指標 = EAX)、nfree 核心 0x3d67f(ESI = 區塊標頭位址)、
0x3d685(使用中 → 真的釋放)、0x3d693(與下一塊合併:EDI = 下一塊)、0x3d72e(找到的空閒串列節點:EDI)。
corrupt:先把名冊後面那塊的標頭(名冊 + 0xa00)改成 0x00042b10(續七十一 v9b 戰後寫回實測的值)。
"""
from __future__ import annotations

import json
import struct
import sys
import time

from drv import regs_rec, stack
from live import DELTA, ROOT, Live
from live import run as hrun

inst, out, mode, tag = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
L = Live(inst, ROOT / out)


def raw_halt() -> None:
    """不檢查單位表指標(讀取戰況途中不一定在戰場)。"""
    hrun(["enter-debugger", "--instance", inst])
    time.sleep(3)


def G(a: int) -> int:
    return L.d32(a + DELTA)


def heap_state(name: str) -> dict:
    p = G(0x53BF7)
    pal = G(0x53A65)
    pre = L.dump(p - 4, 4, f"{name}_hdr_roster")
    h = L.dump(p + 0xA00, 0x60, f"{name}_after_roster")
    return {"roster": hex(p), "roster_hdr": pre.hex(), "count": G(0x53BFB), "pal": hex(pal),
            "pal_minus_roster": pal - p, "hdr_after_roster": h[:4].hex(), "after_roster_hex": h.hex(),
            "pal_hdr": L.dump(pal - 4, 4, f"{name}_pal_hdr").hex(), "units_ptr": hex(G(0x53A45))}


if mode == "info":
    raw_halt()
    print(json.dumps(heap_state(tag), ensure_ascii=False))
    L.resume()
    sys.exit(0)

keys = sys.argv[5].split(",")
if mode == "keys":
    for i, k in enumerate(keys):
        L.key(k, 1.0)
        time.sleep(1.5)
        L.shot(f"{tag}_{i:02d}_{k}")
    print("done")
    sys.exit(0)

corrupt = len(sys.argv) > 6 and sys.argv[6] == "corrupt"
raw_halt()
s0 = heap_state(f"{tag}_pre")
P, PAL0 = int(s0["roster"], 16), int(s0["pal"], 16)
HDR = P + 0xA00
if corrupt:
    L.sm(HDR, struct.pack("<I", 0x00042B10))
s1 = heap_state(f"{tag}_pre2")
print("pre", json.dumps(s0), "\nafter_sm", json.dumps(s1), flush=True)
BPS = [0x111BA, 0x1013E, 0x3D67F, 0x3D685, 0x3D693, 0x3D72E]
L.cmd("BPDEL *")
for a in BPS:
    L.cmd(f"BP 0170:{a + DELTA:x}")
L.resume()
log: list[dict] = []
n = 0


def handle(rec: dict) -> None:
    eip = int(rec["eip"], 16)
    if eip == 0x111BA:
        a = stack(L, rec, 4, f"{tag}_{n}_args")
        rec["ret"], rec["file"], rec["old"], rec["res_idx"] = hex(a[0] - DELTA), hex(a[1] - DELTA), hex(a[2]), a[3]
    elif eip == 0x1013E:
        rec["new_pal"] = hex(rec["eax"])
        rec["new_pal_hdr"] = L.dump(rec["eax"] - 4, 4, f"{tag}_{n}_nph").hex()
    elif eip in (0x3D67F, 0x3D685):
        rec["blk"] = hex(rec["esi"])
        rec["hdr"] = L.dump(rec["esi"], 4, f"{tag}_{n}_h").hex()
        rec["is_pal"] = rec["esi"] + 4 == PAL0
        rec["is_after_roster"] = rec["esi"] == HDR
    elif eip in (0x3D693, 0x3D72E):
        rec["node"] = hex(rec["edi"])
        rec["node_is_after_roster"] = rec["edi"] == HDR
        rec["node_4_12"] = L.dump(rec["edi"], 12, f"{tag}_{n}_node").hex()
        rec["freed_blk"] = hex(rec["esi"])


for i, k in enumerate(keys):
    if k != "-":
        L.key(k, 1.0)
    idle = 0
    while idle < 4:
        time.sleep(1.2)
        if L.running():
            idle += 1
            continue
        idle = 0
        rec = regs_rec(L)
        rec["n"], rec["key_i"] = n, i
        handle(rec)
        log.append(rec)
        print(json.dumps(rec)[:400], flush=True)
        n += 1
        L.resume()
    L.shot(f"{tag}_{i:02d}_{k}")
raw_halt()
s2 = heap_state(f"{tag}_post")
L.cmd("BPDEL *")
L.resume()
(L.out / f"{tag}.json").write_text(json.dumps({"pre": s0, "after_sm": s1, "post": s2, "corrupt": corrupt,
                                               "stops": log}, indent=1), encoding="utf-8")
print("post", json.dumps(s2), flush=True)
print("done", flush=True)
