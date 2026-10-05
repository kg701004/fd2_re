# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十三 v12f:heap_free_block 的往後走訪,碰到「最低位 0 的假標頭」時會把它當空閒串列節點(強制、可撤銷)。

用法:python t_v12f.py <inst> <out_dir> <tag> <S_hex> <mode>    mode = control | corrupt
- 先確認 S(使用中)→ 名冊區塊 → H(= 名冊 + 0xa00 = 調色盤 - 4)實體相鄰,且 H 後一塊是真正的空閒區塊 N。
- corrupt:把 H 的標頭寫成 0x00042b10(續七十一 v9b 戰後寫回實測值),結束時還原成原值。
- 在下一次自然的 heap_free_block 入口(0x3d670)把 EAX 換成 S + 4(那一次原本要釋放的區塊因此不釋放,只是洩漏)。
- 停點:0x3d6f5(走訪開始)、0x3d70d(走訪沒找到 → 改查串列)、0x3d72e(EDI = 選定的節點)、0x3d68b(合併檢查)。
- 預測:control → 0x3d72e 的 EDI = N;corrupt → EDI = H。
- 撤銷:在 0x3d72e 把 S 的標頭寫回原值(使用中),EIP 設成 0x3d776(pop ds/ecx/edi/esi; ret),跳過插入;
  走訪路徑在 0x3d6b2 之後沒有額外 push,rover / 空閒數也還沒改(它們在 0x3d72e 之後才寫),所以堆積回到原狀。
"""
from __future__ import annotations

import json
import re
import struct
import sys
import time

from live import DELTA, ROOT, Live

inst, out, tag, S, mode = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4], 16), sys.argv[5]
NUDGE = sys.argv[6].split(",") if len(sys.argv) > 6 else ["Return", "Down", "Return"]
L = Live(inst, ROOT / out)
assert L.halt(), "halt"


def G(a: int) -> int:
    return L.d32(a + DELTA)


def u32(a: int) -> int:
    return struct.unpack("<I", L.dump(a, 4, "f_u32"))[0]


def pane_regs() -> dict:
    return L.regs()


def wait_stop(max_s: float, nudge: list[str] | None = None) -> dict | None:
    t0, nudged = time.time(), 0
    while time.time() - t0 < max_s:
        time.sleep(1.2)
        if not L.running():
            return L.regs()
        if nudge and time.time() - t0 > 15 * (nudged + 1) and nudged < len(nudge):
            L.key(nudge[nudged], 0.8)
            nudged += 1
    return None


roster, pal = G(0x53BF7), G(0x53A65)
H = roster + 0xA00
assert H == pal - 4
hS, hR, hH = u32(S), u32(roster - 4), u32(H)
N = H + (hH & ~1)
hN = u32(N)
geo = {"S": hex(S), "S_hdr": hex(hS), "roster_blk": hex(roster - 4), "roster_hdr": hex(hR), "H": hex(H),
       "H_hdr": hex(hH), "N": hex(N), "N_hdr": hex(hN)}
assert hS & 1 and S + (hS & ~1) == roster - 4, geo
assert hR == 0xA05 and hH & 1 and hN & 1 == 0, geo
desc = struct.unpack("<16I", L.dump(0x527B0 + DELTA, 0x40, f"{tag}_desc"))
geo["rover"], geo["rover_prev"], geo["numalloc_14"], geo["numfree_18"] = (hex(desc[2]), hex(u32(desc[2] + 4)),
                                                                          desc[5], desc[6])
if mode == "corrupt":
    L.sm(H, struct.pack("<I", 0x00042B10))
geo["H_hdr_set"] = hex(u32(H))
print("geo", json.dumps(geo), flush=True)
rec: dict = {"mode": mode, "geo": geo, "stops": []}

L.cmd("BPDEL *")
L.cmd(f"BP 0170:{0x3D670 + DELTA:x}")
L.resume()
r = wait_stop(120, NUDGE)
assert r and r["EIP"] - DELTA == 0x3D670, r
rec["natural_eax"] = hex(r["EAX"])
L.cmd(f"SR EAX {S + 4:x}")
r2 = L.regs()
rec["eax_after_sr"] = hex(r2["EAX"])
assert r2["EAX"] == S + 4, r2
L.cmd("BPDEL *")
for a in (0x3D68B, 0x3D6F5, 0x3D70D, 0x3D72E):
    L.cmd(f"BP 0170:{a + DELTA:x}")
L.resume()
for _ in range(6):
    r = wait_stop(30)
    assert r, "no stop"
    eip = r["EIP"] - DELTA
    s = {"eip": hex(eip), "esi": hex(r["ESI"]), "edi": hex(r["EDI"]), "eax": hex(r["EAX"])}
    rec["stops"].append(s)
    print(json.dumps(s), flush=True)
    if eip == 0x3D72E:
        s["edi_is"] = "H" if r["EDI"] == H else ("N" if r["EDI"] == N else "other")
        s["S_hdr_at_stop"] = hex(u32(S))
        L.sm(S, struct.pack("<I", hS))
        L.cmd(f"SR EIP {0x3D776 + DELTA:x}")
        r3 = L.regs()
        s["eip_after_sr"] = hex(r3["EIP"] - DELTA)
        s["S_hdr_restored"] = hex(u32(S))
        assert r3["EIP"] - DELTA == 0x3D776, r3
        break
    L.resume()
L.cmd("BPDEL *")
if mode == "corrupt":
    L.sm(H, struct.pack("<I", hH))
rec["H_hdr_final"] = hex(u32(H))
rec["S_hdr_final"] = hex(u32(S))
desc2 = struct.unpack("<16I", L.dump(0x527B0 + DELTA, 0x40, f"{tag}_desc2"))
rec["desc_unchanged"] = desc2 == desc
L.resume()
time.sleep(3)
L.shot(f"{tag}_after")
(L.out / f"{tag}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
print(json.dumps({k: rec[k] for k in rec if k != "stops"}), flush=True)
print("done", flush=True)
