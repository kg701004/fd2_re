# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十四 v17:「離開戰場」YES 之後到回 DOS 為止的每一次 free —— 函式庫 / AIL_shutdown 會不會釋放 0x1f7014 / 0x1fa6b8。

用法:python t_v17.py <inst> <out_dir> <tag> <keys逗號> [corrupt]
前提:畫面已停在「要離開戰場嗎?」(YES / NO),keys 通常是 Left,Return,-,-,...
- pre:名冊 / 調色盤 / H(= 名冊 + 0xa00)、堆積描述 0x527b0、整段堆積 0x1e0000..0x320000(離線找 H 之前同段的使用中區塊)。
- corrupt:H 的標頭寫成 0x00042b10(續七十一 v9b 戰後寫回實測值)。
- 斷點:0x3d670(free 入口,EAX = 指標)、0x3d6f5(往後走訪開始)、0x3d72e(EDI = 選定節點)、0x3d737 / 0x3d739(讀節點的前一節點)、
  0x37ed8(AIL_shutdown 入口)、0x25e97(main 呼叫 AIL_shutdown 處)、0x1a301(YES 回 −1)、0x3da31 / 0x4d021(函式庫的兩個 free 呼叫點)。
- 每次停點記暫存器;0x3d670 另記被釋放區塊的標頭與它是哪一塊(AIL 0x1f7018、緩衝 0x1fa6bc、名冊、調色盤)。
- 模擬器結束(面板出現 E_Exit 或沒有 EIP=)就存面板並停止。
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
L = Live(inst, ROOT / out)
assert L.halt(), "halt"


def G(a: int) -> int:
    return L.d32(a + DELTA)


def u32(a: int) -> int:
    return struct.unpack("<I", L.dump(a, 4, f"{tag}_u32"))[0]


roster, pal = G(0x53BF7), G(0x53A65)
H = roster + 0xA00
assert H == pal - 4, (hex(H), hex(pal))
L.dump(0x527B0 + DELTA, 0x40, f"{tag}_desc")
L.dump(0x1E0000, 0x140000, f"{tag}_heap")
L.dump(0x53A00 + DELTA, 0x600, f"{tag}_globals")
pre = {"roster": hex(roster), "pal": hex(pal), "H": hex(H), "H_hdr": hex(u32(H)), "pal_first4": hex(u32(pal)),
       "ail_seq_53ed0": hex(G(0x53ED0)), "lib_buf_538ac": hex(G(0x538AC)), "corrupt": corrupt}
KNOWN = {G(0x53ED0): "ail_seq_53ed0", G(0x538AC): "lib_buf_538ac", roster: "roster", pal: "palette"}
pre["known_hdrs"] = {name: hex(u32(p - 4)) for p, name in KNOWN.items() if p}
if corrupt:
    L.sm(H, struct.pack("<I", 0x00042B10))
pre["H_hdr_after_sm"] = hex(u32(H))
print("pre", json.dumps(pre), flush=True)

BPS = [0x3D670, 0x3D6F5, 0x3D72E, 0x3D737, 0x3D739, 0x37ED8, 0x25E97, 0x1A301, 0x3DA31, 0x4D021]
L.cmd("BPDEL *")
for a in BPS:
    L.cmd(f"BP 0170:{a + DELTA:x}")
L.resume()
log: list[dict] = []
st = {"frees": 0, "known_freed": [], "emulator_gone": False}


def handle(rec: dict, n: int) -> None:
    eip = int(rec["eip"], 16)
    if eip == 0x3D670:
        p = rec["eax"]
        rec["ptr"] = hex(p)
        st["frees"] += 1
        if p:
            rec["hdr"] = hex(u32(p - 4))
            # 入口時 [esp] = 0x37799(回 0x3777e),[esp+4] ebp、[esp+8] ebx(0x3777e 推的),[esp+0xc] = 0x3777e 的呼叫端;
            # 經 free 包裝 0x3776e 時 [esp+0xc] = 0x37779,[esp+0x14] 包裝的 ebp,[esp+0x18] = 遊戲的呼叫端
            s = stack(L, rec, 7, f"{tag}_{n}_stk")
            rec["ret_core"] = hex(s[3] - DELTA)
            if s[3] - DELTA == 0x37779:
                rec["ret_game"] = hex(s[6] - DELTA)
        if p in KNOWN:
            rec["known"] = KNOWN[p]
            st["known_freed"].append([n, KNOWN[p]])
    elif eip in (0x3D6F5, 0x3D72E, 0x3D737, 0x3D739):
        rec["esi_h"], rec["edi_h"], rec["eax_h"] = hex(rec["esi"]), hex(rec["edi"]), hex(rec["eax"])
        if eip == 0x3D72E:
            rec["node_is_H"] = rec["edi"] == H
    elif eip in (0x37ED8, 0x25E97, 0x1A301, 0x3DA31, 0x4D021):
        rec["ret0"] = hex(stack(L, rec, 1, f"{tag}_{n}_r")[0] - DELTA)


def save() -> None:
    (L.out / f"{tag}.json").write_text(json.dumps({"pre": pre, "state": st, "stops": log}, indent=1),
                                       encoding="utf-8")


n = 0
for i, k in enumerate(keys):
    if st["emulator_gone"]:
        break
    if k != "-":
        L.key(k, 1.0)
    idle = 0
    while idle < 4:
        time.sleep(1.2)
        pane = L.pane()
        lines = [x for x in pane.splitlines() if x.strip()]
        if "E_Exit" in pane or not lines:
            (L.out / f"{tag}_crash_pane.txt").write_text(pane, encoding="utf-8")
            st["emulator_gone"] = True
            print("EMULATOR GONE", pane[-600:], flush=True)
            break
        if "Running" in lines[-1]:
            idle += 1
            continue
        idle = 0
        rec = regs_rec(L)
        rec["n"], rec["key_i"] = n, i
        handle(rec, n)
        log.append(rec)
        print(json.dumps(rec)[:300], flush=True)
        n += 1
        save()
        L.resume()
    if not st["emulator_gone"]:
        L.shot(f"{tag}_{i:02d}_{k}")
    save()
if not st["emulator_gone"]:
    hrun(["enter-debugger", "--instance", inst])
    time.sleep(3)
    L.cmd("BPDEL *")
    L.resume()
save()
print("done", json.dumps(st), flush=True)
