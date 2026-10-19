# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十六:lut_circle_ramp_at_unit(0x2189a)每幀停留多久 —— DOSBox-X 實機,讀 BIOS tick(線性 0x46c)。

只對原版 FD2.EXE;只改模擬器記憶體裡的單位資料(索爾已學法術、+5、MP),程式碼不動。
停在除錯器時模擬器不跑,所以 tick 是模擬時間(cycles 固定 5000,core=normal)。

用法(instance 由 LC_INST 指定,預設 lc126c):
  python lc126t.py setup SPELL FRAMES   # 停住:索爾只留 SPELL、+5 清 0、MP 805;FRAMES=1 時連每幀斷點一起下;恢復
  python lc126t.py rec TAG [秒]         # 入口、(每幀)、迴圈結束、函式返回各讀 tick;結束後清斷點、把索爾 +5 清 0
  python lc126t.py bpdel | resume
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

INST = os.environ.get("LC_INST", "lc126c")
OUT = Path(__file__).resolve().parent / "cl" / f"{INST}_live"
L = Live(INST, OUT)
TICK = 0x46C
BP_ENTRY, BP_FRAME, BP_END = 0x2189A, 0x2198E, 0x21998   # 入口;每幀 copy_rect 之後;迴圈結束(heap_free 之前)
BP_AFTER = 0x219A8                                        # redraw(0) 之後、jmp 共用收尾


def bp(addrs: tuple[int, ...]) -> None:
    for a in addrs:
        L.cmd(f"BP 0170:{a + DELTA:x}")


def s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def rec(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "stops": []}
    t0 = time.time()
    done = False
    while time.time() - t0 < max_s:
        r = L.wait_stop(10, poll=0.5)
        if r is None:
            continue
        if not r:
            log["stops"].append({"at": "exit", "pane": [x for x in L.pane().splitlines() if x.strip()][-3:]})
            break
        nat = r.get("EIP", 0) - DELTA
        ent: dict = {"at": hex(nat), "t": round(time.time() - t0, 1), "tick": L.d32(TICK)}
        if nat == BP_ENTRY:
            st = struct.unpack("<4I", L.dump(r["ESP"], 16, "stk"))
            ent.update(name="入口", ret=hex(st[0] - DELTA), args=[s32(v) for v in st[1:]])
        elif nat == BP_FRAME:
            ent.update(name="幀", frame=r["EBX"], radius=s32(r["ESI"]))
        elif nat == BP_END:
            ent.update(name="迴圈結束", ebx=r["EBX"])
        elif nat == BP_AFTER:
            ent.update(name="redraw(0) 之後")
        else:
            ent.update(name="不是設的斷點", regs={k: hex(v) for k, v in r.items()})
            log["stops"].append(ent)
            print(ent)
            break
        log["stops"].append(ent)
        print(ent)
        (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        if nat == BP_AFTER:
            L.cmd("BPDEL *")
            L.ubase = L.ubase or int((OUT / "ubase.txt").read_text())
            L.sm(L.ua(0, 5), bytes([0]))     # 讓索爾同一回合可以再施放一次
            done = True
            L.resume()
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("stops", len(log["stops"]), "done", done)
    return 0 if done else 1


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "bpdel":
        L.cmd("BPDEL *")
    elif cmd == "place":
        # 盜賊 #11 搬到 (X, Y)、HP 9999(續一百二十二同一做法:法術範圍內要有目標才施放得了)
        x, y = int(argv[1]), int(argv[2])
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        try:
            L.sm(L.ua(11, 0), bytes([x, y]))
            L.sm(L.ua(11, 0x40), struct.pack("<hh", 9999, 9999))
            u = L.dump(L.ua(11, 0), 80, "u11")
            print("u11", u[0], u[1], struct.unpack_from("<hh", u, 0x40), "camp", u[6])
        finally:
            L.resume()
    elif cmd == "rec":
        return rec(argv[1], float(argv[2]) if len(argv) > 2 else 600)
    elif cmd == "setup":
        spell, frames = int(argv[1]), argv[2] == "1"
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        (OUT / "ubase.txt").write_text(str(L.ubase))
        try:
            u = L.dump(L.ua(0, 0), 80, "u0")
            print("u0 +5", u[5], "MP", struct.unpack_from("<hh", u, 0x44), "spells", u[0x1A:0x1F].hex())
            # 已學法術是 +0x1a 起 40 位元的位元組(續一百二十二 lc122.py 同一寫法):只留 SPELL
            L.sm(L.ua(0, 0x1A), (1 << spell).to_bytes(5, "little"))
            L.sm(L.ua(0, 5), bytes([0]))
            L.sm(L.ua(0, 0x44), struct.pack("<hh", 805, 805))
            u0 = L.dump(L.ua(0, 0), 2, "u0xy")
            L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))   # 游標放回索爾
            u = L.dump(L.ua(0, 0), 80, "u0")
            print("after +5", u[5], "MP", struct.unpack_from("<hh", u, 0x44), "spells", u[0x1A:0x1F].hex())
            L.cmd("BPDEL *")
            bp((BP_ENTRY, BP_END, BP_AFTER) + ((BP_FRAME,) if frames else ()))
            time.sleep(0.5)
        finally:
            L.resume()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
