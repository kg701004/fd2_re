# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十三:ai_item_action(0x15055)在圓形換色之後的流程 —— DOSBox-X 實機(只對原版 FD2.EXE,只改模擬器記憶體裡的單位資料)。

用法(instance 由環境變數 LC_INST 指定,預設 lc123):
  python lc123.py units                     # 停住、印單位,恢復
  python lc123.py arm ITEM T_HP [S_HP]      # 停住:敵 #11 slot2 = ITEM;索爾 HP = S_HP(預設不動);#1 HP = T_HP;
                                            #   #1..#4 設已行動、索爾清已行動;設斷點;恢復
  python lc123.py rec TAG [秒]              # 等斷點,逐站記錄;走到 ai_item_action 返回前清掉流程斷點、恢復
  python lc123.py watch TAG [秒]            # 只等戰敗路徑的兩個斷點(0x22e5c、0x25ebb),停了就記錄後恢復
  python lc123.py bpdel | resume
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live  # noqa: E402

INST = os.environ.get("LC_INST", "lc123")
OUT = Path(__file__).resolve().parent / "cl" / f"{INST}_live"
L = Live(INST, OUT)
VGA, VGA_N = 0xA0000, 64000

BP_ENTRY = 0x15055      # ai_item_action 入口
BP_CAND = 0x150F6       # build_target_candidates 返回(add esp 之前)
BP_CIRCLE = 0x151A7     # lut_circle_ramp_at_unit 返回
BP_DELAY = 0x151B7      # delay(200) 之後
BP_PAL = 0x151CE        # palette_delta_ramp(0, 255, ebx) 返回之後
BP_PALEND = 0x151DD     # 調色盤迴圈結束
BP_CAM = 0x1528C        # camera_step_to 返回
BP_PHASE = 0x152BA      # redraw(1) + wait_ticks(1) 之後(ebx = 這一圈的 [0x53c1f])
BP_PRE = 0x152E5        # item_effect_dispatch 之前
BP_DISP = 0x20C6F       # item_effect_dispatch 入口
BP_POST = 0x152F5       # item_effect_dispatch 返回
BP_RET = 0x152FD        # reset_pose 返回之後(0x15309 是別的函式也會跳進來的共用結尾,不能用)
FLOW = (BP_ENTRY, BP_CAND, BP_CIRCLE, BP_DELAY, BP_PAL, BP_PALEND, BP_CAM, BP_PHASE, BP_PRE, BP_DISP, BP_POST, BP_RET)
BP_LOSE = 0x22E5C       # 戰敗畫面(FDOTHER #79;續七十三)
BP_TITLE = 0x25EBB      # title_menu_dispatch 入口
LOSE = (BP_LOSE, BP_TITLE)
G = {"target_x": 0x53C37, "target_y": 0x53C3B, "slot": 0x53C3F, "phase": 0x53C1F, "step_sel": 0x51A83,
     "cursor_x": 0x53AB1, "cursor_y": 0x53AB5, "scroll_x": 0x53AA9, "scroll_y": 0x53AAD,
     "map_w": 0x53AC1, "map_h": 0x53AC5, "result": 0x53ECC}


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def globs() -> dict[str, int]:
    return {k: s32(L.d32(a + DELTA)) for k, a in G.items()}


def unit_rows() -> list[dict]:
    n = L.d32(0x53BEB + DELTA) & 0xFF
    b = L.units("units", n)
    rows = []
    for i in range(n):
        r = b[i * 80:(i + 1) * 80]
        hp, mhp, mp, mmp = struct.unpack_from("<hhhh", r, 0x40)
        rows.append({"i": i, "x": r[0], "y": r[1], "face": r[3], "f5": r[5], "camp": r[6], "hp": hp, "mhp": mhp,
                     "inv": r[0xA:0x1A].hex()})
    return rows


def show() -> None:
    print("ubase", hex(L.ubase), globs())
    for r in unit_rows():
        print(f"#{r['i']:2d} x={r['x']:2d} y={r['y']:2d} +5={r['f5']:02x} +6={r['camp']:02x} hp={r['hp']}/{r['mhp']} inv={r['inv']}")


def palette(name: str) -> bytes:
    return L.dump(L.d32(0x53A65 + DELTA), 768, name)


def clear(bps: tuple[int, ...]) -> None:
    """BPDEL 只收序號或 *:全部清掉,再把不在 bps 裡的補回去。"""
    keep = [a for a in FLOW + LOSE if a not in bps]
    L.cmd("BPDEL *")
    for a in keep:
        L.cmd(f"BP 0170:{a + DELTA:x}")


def rec(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "stops": [], "pal": [], "phase": []}
    t0 = time.time()
    done = False
    while time.time() - t0 < max_s:
        r = L.wait_stop(max_s - (time.time() - t0), poll=0.5)
        if r is None:
            print("沒有停(逾時)")
            break
        nat = r.get("EIP", 0) - DELTA
        ts = round(time.time() - t0, 1)
        if nat in FLOW and nat != BP_ENTRY and not log["stops"]:
            log.setdefault("stray", []).append(hex(nat))
            print("入口之前的停(略過)", hex(nat))
            L.resume()
            continue
        if nat == BP_PAL:
            log["pal"].append(r["EBX"])
            if r["EBX"] in (64, 48, 32, 16, 0):
                L.shot(f"{tag}_pal{r['EBX']:02d}")
            L.resume()
            continue
        ent: dict = {"at": hex(nat), "t": ts}
        if nat == BP_ENTRY:
            st = struct.unpack("<3I", L.dump(r["ESP"], 12, "stk"))
            ent.update(name="ai_item_action 入口", ret=hex(st[0] - DELTA), unit=st[1], camp=st[2], g=globs(), units=unit_rows())
        elif nat == BP_CAND:
            st = struct.unpack("<7I", L.dump(r["ESP"], 28, "stk"))
            out = L.dump(st[2], 16, "cand_out")
            row = L.dump(r["ESI"], 0x17, "item_row")
            ent.update(name="build_target_candidates 返回", args=[s32(v) for v in st[:2]] + [hex(st[2])] + [s32(v) for v in st[3:]],
                       eax=r["EAX"], out=out.hex(), item_row=row.hex(), row_0d=row[0xD], row_10=row[0x10], row_12=row[0x12])
        elif nat in (BP_CIRCLE, BP_DELAY, BP_PALEND, BP_CAM, BP_PRE, BP_RET):
            name = {BP_CIRCLE: "圓形換色返回", BP_DELAY: "delay(200) 之後", BP_PALEND: "調色盤迴圈結束",
                    BP_CAM: "camera_step_to 返回", BP_PRE: "item_effect_dispatch 之前", BP_RET: "返回前"}[nat]
            ent.update(name=name, g=globs(), ebx=r["EBX"], edi=r["EDI"])
            L.dump(VGA, VGA_N, f"{tag}_{nat:x}")
            palette(f"{tag}_{nat:x}_pal")
            if nat == BP_PRE:
                ent["targets"] = L.dump(r["ESP"], 16, "pre_targets").hex()
            if nat in (BP_PALEND, BP_CAM, BP_RET):
                L.shot(f"{tag}_{nat:x}")
        elif nat == BP_PHASE:
            k = r["EBX"]
            L.dump(VGA, VGA_N, f"{tag}_ph{k}")
            ent.update(name="相位幀", ebx=k, phase=s32(L.d32(0x53C1F + DELTA)))
            log["phase"].append(k)
        elif nat == BP_DISP:
            st = struct.unpack("<5I", L.dump(r["ESP"], 20, "stk"))
            tg = L.dump(st[4], 16, "disp_targets")
            ent.update(name="item_effect_dispatch 入口", ret=hex(st[0] - DELTA), user=st[1], slot=st[2], count=st[3],
                       targets_ptr=hex(st[4]), targets=tg.hex(), units=unit_rows())
        elif nat == BP_POST:
            ent.update(name="item_effect_dispatch 返回", eax=r["EAX"], g=globs(), units=unit_rows())
            L.dump(VGA, VGA_N, f"{tag}_{nat:x}")
            palette(f"{tag}_{nat:x}_pal")
            L.shot(f"{tag}_{nat:x}")
        elif nat in LOSE:
            st = struct.unpack("<2I", L.dump(r["ESP"], 8, "stk"))
            ent.update(name="戰敗畫面 0x22e5c" if nat == BP_LOSE else "title_menu_dispatch 入口", ret=hex(st[0] - DELTA), g=globs())
        else:
            ent.update(name="不是設的斷點")
            log["stops"].append(ent)
            print(ent)
            break
        log["stops"].append(ent)
        print({k: v for k, v in ent.items() if k != "units"})
        if nat == BP_RET:
            clear(FLOW)
            done = True
            print("流程斷點已清", L.cmd("BPLIST")[-160:].strip())
            L.resume()
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("stops", len(log["stops"]), "pal", len(log["pal"]), log["pal"][:3], log["pal"][-3:], "phase", log["phase"], "done", done)
    return 0 if done else 1


def watch(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "stops": []}
    t0 = time.time()
    while time.time() - t0 < max_s:
        r = L.wait_stop(max_s - (time.time() - t0), poll=0.7)
        if r is None:
            print("沒有停(逾時)")
            break
        nat = r.get("EIP", 0) - DELTA
        st = struct.unpack("<2I", L.dump(r["ESP"], 8, "stk"))
        ent = {"at": hex(nat), "t": round(time.time() - t0, 1), "ret": hex(st[0] - DELTA), "g": globs()}
        if nat in LOSE:
            ent["units"] = [u for u in unit_rows() if u["i"] in (0, 1, 11)] if nat == BP_LOSE else []
            L.shot(f"{tag}_{nat:x}")
        log["stops"].append(ent)
        print(ent)
        if nat == BP_TITLE or nat not in LOSE:
            clear(LOSE)
            L.resume()
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return 0 if any(s["at"] == hex(BP_TITLE) for s in log["stops"]) else 1


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "bpdel":
        clear(FLOW + LOSE)
        print(L.cmd("BPLIST")[-200:].strip())
    elif cmd == "rebp":
        # 已停住時用:全部清掉、照目前的清單重設、印清單、恢復
        L.cmd("BPDEL *")
        for a in FLOW + LOSE:
            L.cmd(f"BP 0170:{a + DELTA:x}")
        time.sleep(0.5)
        L.cmd("BPLIST")
        time.sleep(0.5)
        print("\n".join(L.pane().splitlines()[-18:]))
        L.resume()
    elif cmd == "probe":
        # 等任何一次停下:印暫存器與堆疊(不恢復,讓呼叫端決定)
        r = L.wait_stop(float(argv[1]) if len(argv) > 1 else 30, poll=0.5)
        if r is None:
            print("沒有停")
            return 1
        print({k: hex(v) for k, v in r.items()}, "native EIP", hex(r["EIP"] - DELTA))
        st = struct.unpack("<32I", L.dump(r["ESP"], 128, "probe_stk"))
        print("stack:", " ".join(f"{v:08x}" for v in st))
        print("code-range words (native):", [hex(v - DELTA) for v in st if 0x1AC010 <= v <= 0x1EAEE1])
    elif cmd in ("rec", "watch"):
        L.ubase = L.ubase or int((OUT / "ubase.txt").read_text())
        fn = rec if cmd == "rec" else watch
        return fn(argv[1], float(argv[2]) if len(argv) > 2 else 420)
    elif cmd in ("units", "arm"):
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        (OUT / "ubase.txt").write_text(str(L.ubase))
        try:
            if cmd == "arm":
                L.sm(L.ua(11, 0xE), bytes([0x00, int(argv[1])]))
                L.sm(L.ua(1, 0x40), struct.pack("<h", int(argv[2])))
                if len(argv) > 3:
                    L.sm(L.ua(0, 0x40), struct.pack("<h", int(argv[3])))
                if len(argv) > 5:
                    L.sm(L.ua(11, 0), bytes([int(argv[4]), int(argv[5])]))
                L.sm(L.ua(0, 5), bytes([0]))
                for i in (1, 2, 3, 4):
                    L.sm(L.ua(i, 5), bytes([0x80]))
                u0 = L.dump(L.ua(0, 0), 2, "u0xy")
                L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
                for a in FLOW + LOSE:
                    L.cmd(f"BP 0170:{a + DELTA:x}")
                time.sleep(0.5)
            show()
            if cmd == "arm":
                print(L.cmd("BPLIST")[-400:])
        finally:
            L.resume()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
