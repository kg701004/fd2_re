# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十四 v19b / v20:標題選 CONTINUE / LOAD 之後,第一次重載調色盤時,舊區塊標頭若被改壞,free 怎麼走。

用法:python t_v19b.py <inst> <out_dir> <tag> <keys逗號> [nocorrupt]
前提:畫面停在標題選單(START / LOAD / CONTINUE)。
- 標題動畫每一輪都以 0x111ba 重載調色盤(i = 101 / 102 交替)並 free 舊區塊,所以在標題上改壞標頭會先被動畫那次 free 吃掉;
  因此只下 0x25ecd(標題序列 0x1f894 返回,EAX = 選項)斷點,停在那裡才把當下 [0x53a65] - 4 寫成 0x00042b10。
- 之後下:0x111ba 入口(free 的是目前調色盤時,臨時加 0x3d67f / 0x3d685 / 0x3d693 / 0x3d72e / 0x111d5),
  [0x53a65] 寫入點 0x25f7c(LOAD)/ 0x1013e(CONTINUE 經 0x10010)、0x26130、0x10010、0x29bcb。
  那次 free 結束(0x111d5)就只留寫入點與 0x29bcb / 0x10010,不再記其他 0x111ba。
- nocorrupt:對照組(標頭不改)。
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
corrupt = "nocorrupt" not in sys.argv[5:]
L = Live(inst, ROOT / out)


def raw_halt() -> None:
    hrun(["enter-debugger", "--instance", inst])
    time.sleep(3)


def G(a: int) -> int:
    return L.d32(a + DELTA)


def set_bps(bps: list[int]) -> None:
    L.cmd("BPDEL *")
    for a in bps:
        L.cmd(f"BP 0170:{a + DELTA:x}")


WRITERS = [0x25EF5, 0x25F7C, 0x1013E]
MARK = [0x26130, 0x10010, 0x29BCB]
HEAP = [0x3D67F, 0x3D685, 0x3D693, 0x3D72E, 0x111D5]
if "prearmed" in sys.argv[5:]:
    # 0x25ecd 斷點已在戰場內(可靠停住時)下好;標題畫面上不再 enter-debugger ——
    # 續七十四 v20:標題上停住失敗後 resume 送出的「RUN + Enter」被遊戲當成按鍵,選了 START
    pre = {"prearmed": True, "corrupt": corrupt}
else:
    for _try in range(6):
        raw_halt()
        d = struct.unpack("<16I", L.dump(0x527B0 + DELTA, 0x40, f"{tag}_desc_chk"))
        if 0x100000 < d[2] < 0x400000 and 0x100000 < d[9] < 0x400000:
            break
        L.resume()
        time.sleep(2)
    else:
        raise SystemExit("halt: descriptor not readable")
    pre = {"pal": hex(G(0x53A65)), "corrupt": corrupt}
    set_bps([0x25ECD])
    L.resume()
st = {"phase": "title", "watch": None, "done_free": False, "emulator_gone": False}
log: list[dict] = []


def handle(rec: dict, n: int) -> None:
    eip = int(rec["eip"], 16)
    if eip == 0x25ECD:
        rec["choice_eax"] = rec["eax"]
        cur = G(0x53A65)
        rec["pal"], rec["pal_hdr_before"] = hex(cur), L.dump(cur - 4, 4, f"{tag}_{n}_ph0").hex()
        if corrupt:
            L.sm(cur - 4, struct.pack("<I", 0x00042B10))
        rec["pal_hdr_after"] = L.dump(cur - 4, 4, f"{tag}_{n}_ph1").hex()
        st["phase"] = "dispatch"
        set_bps([0x111BA] + WRITERS + MARK)
    elif eip == 0x111BA:
        a = stack(L, rec, 4, f"{tag}_{n}_args")
        rec["ret"], rec["file"], rec["old"], rec["res_idx"] = hex(a[0] - DELTA), hex(a[1] - DELTA), hex(a[2]), a[3]
        cur = G(0x53A65)
        if a[1] - DELTA == 0x51A4D and a[2] == cur and cur and not st["done_free"]:
            rec["old_hdr"] = L.dump(cur - 4, 4, f"{tag}_{n}_oh").hex()
            st["watch"] = cur
            set_bps([0x111BA] + WRITERS + MARK + HEAP)
            rec["armed"] = True
    elif eip in (0x3D67F, 0x3D685):
        rec["blk"], rec["hdr"] = hex(rec["esi"]), L.dump(rec["esi"], 4, f"{tag}_{n}_h").hex()
        rec["is_watch"] = st["watch"] is not None and rec["esi"] + 4 == st["watch"]
    elif eip in (0x3D693, 0x3D72E):
        rec["node"], rec["freed_blk"] = hex(rec["edi"]), hex(rec["esi"])
    elif eip == 0x111D5:
        rec["watch_hdr_after"] = L.dump(st["watch"] - 4, 4, f"{tag}_{n}_wh").hex()
        st["done_free"] = True
        set_bps(WRITERS + MARK)
    elif eip in WRITERS:
        rec["new_pal"] = hex(rec["eax"])
        rec["new_pal_hdr"] = L.dump(rec["eax"] - 4, 4, f"{tag}_{n}_nph").hex() if rec["eax"] else None
        if st["watch"]:
            rec["old_blk_hdr_now"] = L.dump(st["watch"] - 4, 4, f"{tag}_{n}_owh").hex()
    elif eip in MARK:
        rec["ret"] = hex(stack(L, rec, 1, f"{tag}_{n}_r")[0] - DELTA)
        rec["pal"] = hex(G(0x53A65))


def save() -> None:
    (L.out / f"{tag}.json").write_text(json.dumps({"pre": pre, "state": st, "stops": log}, indent=1),
                                       encoding="utf-8")


n = 0
for i, k in enumerate(keys):
    if k != "-":
        L.key(k, 1.0)
    idle = 0
    while idle < 4:
        time.sleep(1.2)
        pane = L.pane()
        lines = [x for x in pane.splitlines() if x.strip()]
        if "E_Exit" in pane or not lines:
            st["emulator_gone"] = True
            (L.out / f"{tag}_crash_pane.txt").write_text(pane, encoding="utf-8")
            break
        if "Running" in lines[-1]:
            idle += 1
            continue
        idle = 0
        rec = regs_rec(L)
        rec["n"], rec["key_i"] = n, i
        handle(rec, n)
        log.append(rec)
        print(json.dumps(rec)[:320], flush=True)
        n += 1
        save()
        L.resume()
    if st["emulator_gone"]:
        break
    L.shot(f"{tag}_{i:02d}_{k}")
    save()
if not st["emulator_gone"]:
    raw_halt()
    L.cmd("BPDEL *")
    L.resume()
save()
print("done", json.dumps(st), flush=True)
