# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十一:續七十的四個未驗證項目。用法:python t_v9.py <inst> <out_dir> <tag> <mode> <keys逗號> [idle=4]

mode(可用 + 組合):
  dlg    —— 對白播放器:0x15f84 入口(引數、[0x53a79] 等全域,第一次見到的文字表傾印 0x8000 bytes)、
            各控制碼分支(記 ESI 與檔內位移、開框碼的運算元)、0x16188 / 0x16272(0x12c60 的回傳與 [0x53c1b])、
            0x165ac 入口(x, y, 旗標)、0x165db(camera_step_to 返回)
  offspk —— 在 0x34531(事件 0 入口)把單位 #16 搬到地圖外 (40, 10);另斷 0x12cea 入口
  full   —— 在 0x112a5 入口把名冊人數 [0x53bfb] 改成 32;入口與返回點 0x34543 都傾印名冊尾端 + 0x150 bytes
  wb     —— 戰後寫回 0x11506 入口、0x11572(複製:EBP = 單位索引、ESI = 名冊索引)、0x112a5(戰後 JOIN)
一律斷:事件分派 0x1d890 / 0x1d95c / 0x1d9ec、0x34531、0x112a5、0x34543。
"""
from __future__ import annotations

import struct
import sys

from drv import run, stack
from live import DELTA, ROOT, Live

inst, out, tag, mode, keys = sys.argv[1], sys.argv[2], sys.argv[3], set(sys.argv[4].split("+")), sys.argv[5].split(",")
opts = dict(a.split("=", 1) for a in sys.argv[6:])
L = Live(inst, ROOT / out)
assert L.halt()

G = lambda a: L.d32(a + DELTA)  # noqa: E731 —— obj2 全域
seen_tables: set[int] = set()
tstack: list[int] = []
CTL = {0x15FCD: "page", 0x16055: "nested_53ad9", 0x1608B: "nested_53add", 0x160AE: "number_53ae1",
       0x16149: "open_char_top", 0x16233: "open_char_bottom", 0x1636C: "open_unit_top", 0x163E8: "open_unit_bottom",
       0x16322: "newline", 0x164AC: "end"}
TAIL = 0x150


def roster(name: str) -> dict:
    n, p = G(0x53BFB), G(0x53BF7)
    b = L.dump(p, min(n, 40) * 0x50, name) if 0 < n <= 64 else b""
    return {"count": n, "ptr": hex(p), "dump": name, "char_ids_+8": [b[i * 0x50 + 8] for i in range(len(b) // 0x50)],
            "portraits_+7": [b[i * 0x50 + 7] for i in range(len(b) // 0x50)]}


def h_disp(L, rec, n):
    e = rec["eax"]
    rec["event_id"] = e
    rec["handler"] = hex(G(0x51B91 + 4 * e) - DELTA) if 0 <= e < 200 else None


def h_ev0(L, rec, n):
    rec["roster"] = roster(f"{tag}_{n}_roster_before")
    if "offspk" in mode:
        a = L.ua(16, 0)
        rec["u16_before"] = list(L.dump(a, 2, f"{tag}_{n}_u16"))
        L.sm(a, bytes([40, 10]))
        rec["u16_after"] = list(L.dump(a, 2, f"{tag}_{n}_u16b"))


def h_join(L, rec, n):
    a = stack(L, rec, 2, f"{tag}_{n}_args")
    rec["ret"], rec["join_id"] = hex(a[0] - DELTA), a[1]
    rec["count"] = G(0x53BFB)
    p = G(0x53BF7)
    if "full" in mode and rec["ret"] == "0x34543":
        # 名冊填滿:把最後一筆複製到 count..31,再把人數設成 32(等同重複觸發事件 0 到 32 人)
        c = rec["count"]
        last = L.dump(p + (c - 1) * 0x50, 0x50, f"{tag}_{n}_last")
        for i in range(c, 32):
            L.sm(p + i * 0x50, last)
        rec["filled"] = [c, 31]
        rec["tail_before"] = L.dump(p + 0xA00 - 0x50, TAIL, f"{tag}_{n}_tail_before").hex()
        rec["full_roster_ids"] = list(L.dump(p, 0xA00, f"{tag}_{n}_roster_full")[8::0x50])
        L.sm(0x53BFB + DELTA, struct.pack("<I", 32))
        rec["count_forced"] = G(0x53BFB)


def h_after(L, rec, n):
    r = roster(f"{tag}_{n}_roster_after")
    rec["roster"] = r
    p = int(r["ptr"], 16)
    if r["count"] and r["count"] <= 33:
        rec["new_record"] = L.dump(p + (r["count"] - 1) * 0x50, 0x50, f"{tag}_{n}_new_record").hex()
    if "full" in mode:
        rec["tail_after"] = L.dump(p + 0xA00 - 0x50, TAIL, f"{tag}_{n}_tail_after").hex()


def h_dlg(L, rec, n):
    a = stack(L, rec, 10, f"{tag}_{n}_args")
    rec["ret"], rec["table"], rec["idx"], rec["rest"] = hex(a[0] - DELTA), hex(a[1]), a[2], a[3:]
    for k in (0x53A79, 0x53A7D, 0x53C67, 0x53C1B, 0x53AE1, 0x53AD9, 0x53ADD):
        rec[hex(k)] = hex(G(k))
    tstack.append(a[1])
    if a[1] not in seen_tables:
        seen_tables.add(a[1])
        L.dump(a[1], 0x8000, f"{tag}_txt_{a[1]:x}")
        rec["txt_dump"] = f"{tag}_txt_{a[1]:x}.bin"


def h_ctl(L, rec, n):
    eip = int(rec["eip"], 16)
    rec["kind"] = CTL[eip]
    t = tstack[-1] if tstack else 0
    rec["table"] = hex(t)
    rec["off"] = rec["esi"] - t
    rec["code4"] = L.dump(rec["esi"], 4, f"{tag}_{n}_code").hex()
    if eip == 0x164AC and tstack:
        tstack.pop()


def h_spk(L, rec, n):
    rec["lookup_ret"] = rec["eax"] if rec["eax"] < 0x80000000 else rec["eax"] - (1 << 32)
    rec["c1b"] = hex(G(0x53C1B))


def h_box(L, rec, n):
    a = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["ret"], rec["x"], rec["y"], rec["flag"] = hex(a[0] - DELTA), a[1], a[2], a[3]


def cur() -> dict:
    sx, sy, cx, cy = struct.unpack("<4i", L.dump(0x53AA9 + DELTA, 16, "cur"))
    return {"scroll": [sx, sy], "cursor": [cx, cy]}


def h_cam(L, rec, n):
    a = stack(L, rec, 3, f"{tag}_{n}_args")
    rec["ret"], rec["xy"] = hex(a[0] - DELTA), a[1:]
    rec.update(cur())


def h_camret(L, rec, n):
    rec.update(cur())


def h_wb(L, rec, n):
    rec["roster"] = roster(f"{tag}_{n}_roster_wb_entry")
    rec["unit_count"] = G(0x53BEB) & 0xFF


def h_wbcopy(L, rec, n):
    rec["unit_idx"], rec["roster_idx"] = rec["ebp"], rec["esi"]
    rec["unit_+7_+8"] = list(L.dump(rec["edi"] + 7, 2, f"{tag}_{n}_u78"))
    # 名冊緩衝區(0xa00)之後的 4 bytes:下一個堆積區塊(調色盤快取 [0x53a65])的標頭
    rec["hdr_after_roster"] = L.dump(G(0x53BF7) + 0xA00, 4, f"{tag}_{n}_hdr").hex()


trig_done: list[int] = []


def h_trig(L, rec, n):
    """玩家移動後的分派檢查(0x1198a / 0x1711b):第一次停下時把待處理事件 [0x51a8f] 改成 0。"""
    rec["pending_before"] = hex(G(0x51A8F))
    if not trig_done:
        L.sm(0x51A8F + DELTA, struct.pack("<I", 0))
        trig_done.append(n)
        rec["pending_after"] = hex(G(0x51A8F))


H = {0x1D890: h_disp, 0x1D95C: h_disp, 0x1D9EC: h_disp, 0x34531: h_ev0, 0x112A5: h_join, 0x34543: h_after}
if "dlglite" in mode:
    # 不斷 0x15f84 / 0x164ac:玩家回合閒置時狀態框每一格都呼叫一次(返回 0x18d84),驅動會永遠等不到閒置
    H.update({0x1636C: h_ctl, 0x163E8: h_ctl, 0x16149: h_ctl, 0x16233: h_ctl,
              0x16188: h_spk, 0x16272: h_spk, 0x165AC: h_box, 0x165DB: h_camret})
TU = int(opts.get("tu", "48"))


def h_etrig(L, rec, n):
    """敵方 / 友軍回合的分派檢查(0x1d87e / 0x1d94a / 0x1d9da,ESI = 單位索引):輪到單位 TU 時把 [0x51a8f] 改成 0。"""
    rec["unit"] = rec["esi"]
    rec["pending_before"] = hex(G(0x51A8F))
    if not trig_done and rec["esi"] == TU:
        L.sm(0x51A8F + DELTA, struct.pack("<I", 0))
        trig_done.append(n)
        rec["pending_after"] = hex(G(0x51A8F))
        rec["unit_xy"] = list(L.dump(L.ua(TU), 2, f"{tag}_{n}_tuxy"))
        rec.update(cur())


if "etrig" in mode:
    H.update({0x1D87E: h_etrig, 0x1D94A: h_etrig, 0x1D9DA: h_etrig})
elif "trig" in mode:
    H.update({0x1198A: h_trig, 0x1711B: h_trig})
if "cam" in mode:
    H[0x12CEA] = h_cam
if "dlg" in mode:
    H.update({0x15F84: h_dlg, 0x16188: h_spk, 0x16272: h_spk, 0x165AC: h_box, 0x165DB: h_camret})
    H.update({k: h_ctl for k in CTL})
if "offspk" in mode:
    H[0x12CEA] = h_cam
if "wb" in mode:
    H.update({0x11506: h_wb, 0x11572: h_wbcopy, 0x24DF2: h_wb})
run(L, tag, keys, sorted(H), H, idle_n=int(opts.get("idle", "4")))
assert L.halt()
L.cmd("BPDEL *")
L.resume()
print("done", flush=True)
