# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十三 v12:調色盤區塊標頭被改壞後,經「離開戰場 → 標題 0x25ebb → 新遊戲」那條路徑重新載入調色盤時 free 怎麼走。

用法:python t_v12.py <inst> <out_dir> <tag> <keys逗號> [corrupt] [soldead]
- corrupt:先把 [0x53a65] - 4(調色盤區塊標頭)寫成 0x00042b10(續七十一 v9b 戰後寫回實測值、v10b 同值)。
- 常駐斷點:0x111ba 入口(記 ret/file/old/idx)、0x25ebb、0x1f894、[0x53a65] 的 13 個寫入點(EAX = 新調色盤)。
- 0x111ba 入口若 file = FDOTHER(0x51a4d)且 old == 目前 [0x53a65](釋放的就是調色盤),且還沒看滿 6 次:
  臨時加 0x3d67f(ESI = 標頭位址)、0x3d685(真的釋放)、0x3d693 / 0x3d72e(合併 / 空閒串列節點)、0x111d5(free 返回),
  到 0x111d5 時拿掉。這樣只記調色盤那一次 free,不會被其他上百次 free 淹沒。
"""
from __future__ import annotations

import json
import struct
import sys
import time

from drv import regs_rec, stack
from live import DELTA, ROOT, Live
from live import run as hrun

inst, out, tag, keys = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
corrupt = "corrupt" in sys.argv[5:]
soldead = "soldead" in sys.argv[5:]  # 先把索爾(單位 0)+5 設 bit0,下一個玩家行動後判定戰敗 → 回標題 0x25ebb
L = Live(inst, ROOT / out)

PAL_W = [0x1013E, 0x1F77A, 0x1F7DE, 0x1F85A, 0x1F912, 0x1F985, 0x1F9E7, 0x1FB27, 0x1FBEE, 0x1FC24, 0x1FCE4,
         0x25EF5, 0x25F7C]
BASE = [0x111BA, 0x25EBB, 0x1F894] + PAL_W
HEAP = [0x3D67F, 0x3D685, 0x3D693, 0x3D72E, 0x111D5]
st = {"watch": None, "watched": 0, "armed": False}


def raw_halt() -> None:
    hrun(["enter-debugger", "--instance", inst])
    time.sleep(3)


def G(a: int) -> int:
    return L.d32(a + DELTA)


def set_bps(bps: list[int]) -> None:
    L.cmd("BPDEL *")
    for a in bps:
        L.cmd(f"BP 0170:{a + DELTA:x}")


assert L.halt(), "halt"  # 戰場內:確認不是停在 DOS 呼叫裡
pal0 = G(0x53A65)
pre = {"pal": hex(pal0), "pal_hdr": L.dump(pal0 - 4, 4, f"{tag}_pal_hdr0").hex(), "roster": hex(G(0x53BF7)),
       "units_ptr": hex(G(0x53A45)), "chapter": G(0x53C03)}
if corrupt:
    L.sm(pal0 - 4, struct.pack("<I", 0x00042B10))
pre["pal_hdr_after_sm"] = L.dump(pal0 - 4, 4, f"{tag}_pal_hdr1").hex()
if soldead:
    ub = G(0x53A45)
    b5 = L.dump(ub + 5, 1, f"{tag}_u0_5")[0]
    L.sm(ub + 5, bytes([b5 | 1]))
    pre["sol_plus5"] = [b5, L.dump(ub + 5, 1, f"{tag}_u0_5b")[0]]
print("pre", json.dumps(pre), flush=True)
set_bps(BASE)
L.resume()
log: list[dict] = []
n = 0


def handle(rec: dict) -> None:
    eip = int(rec["eip"], 16)
    if eip == 0x111BA:
        a = stack(L, rec, 4, f"{tag}_{n}_args")
        rec["ret"], rec["file"], rec["old"], rec["res_idx"] = hex(a[0] - DELTA), hex(a[1] - DELTA), hex(a[2]), a[3]
        cur = G(0x53A65)
        rec["cur_pal"] = hex(cur)
        if a[1] - DELTA == 0x51A4D and a[2] == cur and cur and st["watched"] < 6:
            rec["old_hdr"] = L.dump(cur - 4, 4, f"{tag}_{n}_oh").hex()
            st["watch"], st["armed"] = cur, True
            set_bps(BASE + HEAP)
            rec["armed"] = True
    elif eip in PAL_W:
        rec["new_pal"] = hex(rec["eax"])
        rec["new_pal_hdr"] = L.dump(rec["eax"] - 4, 4, f"{tag}_{n}_nph").hex() if rec["eax"] else None
    elif eip in (0x3D67F, 0x3D685):
        rec["blk"] = hex(rec["esi"])
        rec["hdr"] = L.dump(rec["esi"], 4, f"{tag}_{n}_h").hex()
        rec["is_watch"] = st["watch"] is not None and rec["esi"] + 4 == st["watch"]
    elif eip in (0x3D693, 0x3D72E):
        rec["node"] = hex(rec["edi"])
        rec["node_4_12"] = L.dump(rec["edi"], 12, f"{tag}_{n}_node").hex()
        rec["freed_blk"] = hex(rec["esi"])
    elif eip == 0x111D5:
        rec["watch"] = hex(st["watch"]) if st["watch"] else None
        rec["watch_hdr_after_free"] = L.dump(st["watch"] - 4, 4, f"{tag}_{n}_wh").hex() if st["watch"] else None
        st["watched"] += 1
        st["armed"] = False
        set_bps(BASE)
    elif eip == 0x25EBB:
        rec["ret"] = hex(stack(L, rec, 1, f"{tag}_{n}_r")[0] - DELTA)
        rec["pal"] = hex(G(0x53A65))


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
    (L.out / f"{tag}.json").write_text(json.dumps({"pre": pre, "corrupt": corrupt, "state": st, "stops": log},
                                                  indent=1), encoding="utf-8")
raw_halt()
L.cmd("BPDEL *")
L.resume()
print("done", flush=True)
