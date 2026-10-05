# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十四 v18:假標頭被當成空閒串列節點之後,讓插入真的執行(續七十三 v12f 在 0x3d72e 撤銷)。

用法:python t_v18.py <inst> <out_dir> <tag> [nudge逗號]
- 幾何同 v12f:S(使用中)→ 名冊區塊 → H(= 名冊 + 0xa00 = 調色盤 - 4)實體相鄰。H 標頭寫成 0x00042b10。
- 下一次自然的 heap_free_block 入口(0x3d670)把 EAX 換成 S + 4(那一次原本要釋放的區塊因此洩漏)。
- 靜態預測(0x3d72e 起):EDI = H;edx = [H+4] = 調色盤前 4 bytes(P);xchg 後 EDI = P,0x3d737 讀 [P];
  [P] + P ≠ S → 0x3d74d:[0x527c8]++、[S+8] = H、[S+4] = P、[P+8] = S、[H+4] = S;之後 0x3d75e..0x3d776 照常返回。
  P = 0x3f000000(v12 傾印:調色盤第 0 色 (0,0,0)、第 1 色 R = 0x3f)遠超 16 MB:讀 [P] 會不會出錯就是這次要看的。
- 斷點:0x3d6f5、0x3d72e、0x3d737、0x3d739、0x3d74d、0x3d756、0x3d75b、0x3d75e、0x3d776,每站記暫存器。
- 0x3d776 之後:傾印 S / H / 描述 / 整段堆積,再恢復執行並截圖。模擬器結束就存面板。
"""
from __future__ import annotations

import json
import struct
import sys
import time

from live import DELTA, ROOT, Live

inst, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
NUDGE = sys.argv[4].split(",") if len(sys.argv) > 4 else ["Return", "Down", "Return"]
L = Live(inst, ROOT / out)
assert L.halt(), "halt"


def G(a: int) -> int:
    return L.d32(a + DELTA)


def u32(a: int) -> int:
    return struct.unpack("<I", L.dump(a, 4, f"{tag}_u32"))[0]


def gone() -> bool:
    pane = L.pane()
    lines = [x for x in pane.splitlines() if x.strip()]
    if "E_Exit" in pane or not lines:
        (L.out / f"{tag}_crash_pane.txt").write_text(pane, encoding="utf-8")
        return True
    return False


def wait_stop(max_s: float, nudge: list[str] | None = None) -> dict | None:
    t0, nudged = time.time(), 0
    while time.time() - t0 < max_s:
        time.sleep(1.2)
        if gone():
            return {"gone": True}
        if not L.running():
            return L.regs()
        if nudge and time.time() - t0 > 15 * (nudged + 1) and nudged < len(nudge):
            L.key(nudge[nudged], 0.8)
            nudged += 1
    return None


roster, pal = G(0x53BF7), G(0x53A65)
H = roster + 0xA00
assert H == pal - 4
hR, hH = u32(roster - 4), u32(H)
# S = 名冊前一塊:從 AIL 序列區塊 [0x53ed0] - 4 實體往後走到名冊區塊
a = G(0x53ED0) - 4
chain = []
while a < roster - 4:
    h = u32(a)
    chain.append([hex(a), hex(h)])
    assert h & 1 and h & ~1, chain
    S, a = a, a + (h & ~1)
assert a == roster - 4, chain
hS = u32(S)
P = u32(pal)
geo = {"chain_from_53ed0": chain, "S": hex(S), "S_hdr": hex(hS), "roster_blk": hex(roster - 4), "roster_hdr": hex(hR),
       "H": hex(H), "H_hdr": hex(hH), "P_pal_first4": hex(P), "N": hex(H + (hH & ~1)), "N_hdr": hex(u32(H + (hH & ~1)))}
desc = struct.unpack("<16I", L.dump(0x527B0 + DELTA, 0x40, f"{tag}_desc"))
geo["desc"] = [hex(x) for x in desc]
L.sm(H, struct.pack("<I", 0x00042B10))
geo["H_hdr_set"] = hex(u32(H))
print("geo", json.dumps(geo), flush=True)
rec: dict = {"geo": geo, "stops": []}


def save() -> None:
    (L.out / f"{tag}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")


L.cmd("BPDEL *")
L.cmd(f"BP 0170:{0x3D670 + DELTA:x}")
L.resume()
r = wait_stop(120, NUDGE)
assert r and not r.get("gone") and r["EIP"] - DELTA == 0x3D670, r
rec["natural_eax"] = hex(r["EAX"])
rec["natural_hdr"] = hex(u32(r["EAX"] - 4)) if r["EAX"] else None
L.cmd(f"SR EAX {S + 4:x}")
r2 = L.regs()
assert r2["EAX"] == S + 4, r2
rec["eax_after_sr"] = hex(r2["EAX"])
L.cmd("BPDEL *")
STEPS = [0x3D6F5, 0x3D72E, 0x3D737, 0x3D739, 0x3D74D, 0x3D756, 0x3D75B, 0x3D75E, 0x3D776]
for x in STEPS:
    L.cmd(f"BP 0170:{x + DELTA:x}")
L.resume()
save()
for _ in range(12):
    r = wait_stop(30)
    if r is None:
        rec["stops"].append({"timeout": True})
        break
    if r.get("gone"):
        rec["emulator_gone"] = True
        print("EMULATOR GONE", flush=True)
        break
    eip = r["EIP"] - DELTA
    s = {"eip": hex(eip), **{k.lower(): hex(v) for k, v in r.items() if k != "EIP"}}
    rec["stops"].append(s)
    print(json.dumps(s), flush=True)
    save()
    if eip == 0x3D776:
        break
    L.resume()
if not rec.get("emulator_gone") and rec["stops"] and rec["stops"][-1].get("eip") == "0x3d776":
    L.cmd("BPDEL *")
    rec["after"] = {"S16": L.dump(S, 16, f"{tag}_S16").hex(), "H16": L.dump(H, 16, f"{tag}_H16").hex(),
                    "desc": [hex(x) for x in struct.unpack("<16I", L.dump(0x527B0 + DELTA, 0x40, f"{tag}_desc2"))],
                    "ivt_0_16": L.dump(0, 16, f"{tag}_ivt").hex()}
    L.dump(0x1E0000, 0x140000, f"{tag}_heap_after")
    save()
    L.resume()
    time.sleep(3)
    L.shot(f"{tag}_after")
save()
print("done", json.dumps({k: rec[k] for k in rec if k not in ("stops", "geo")}), flush=True)
