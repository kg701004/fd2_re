# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十二:lut_circle_ramp_at_unit(0x2189a)在畫面上的樣子 —— DOSBox-X 實機(只對原版 FD2.EXE,只改模擬器記憶體裡的單位資料)。

用法(instance 固定 lc122):
  python lc122.py units                 # 停住、印單位,恢復
  python lc122.py setup SPELL [X Y]     # 停住:索爾 #0 已學法術只留 SPELL、+5 清 0、MP 805、游標放回索爾;
                                        #   有 X Y 時把盜賊 #11 搬到 (X, Y)、HP 9999;設 3 個斷點;傾印基準畫面與調色盤;恢復
  python lc122.py rec TAG [秒]          # 等斷點:入口讀引數,每幀貼完畫面後傾印 VGA 記憶體,迴圈結束後清斷點、恢復
  python lc122.py png TAG               # 把 TAG 的傾印轉成 PNG(用 setup 當時傾印的調色盤)
  python lc122.py bpdel | resume
斷點(native 位址):0x2189a 入口、0x2198e 一幀貼完畫面之後(EBX = 幀序號、ESI = 這一幀的半徑)、0x21998 迴圈結束。
"""
from __future__ import annotations

import json
import struct
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live  # noqa: E402

INST = "lc122"
OUT = Path(__file__).resolve().parent / "cl" / f"{INST}_live"
L = Live(INST, OUT)
BP_ENTRY, BP_FRAME, BP_END, BP_AFTER, BP_AIITEM = 0x2189A, 0x2198E, 0x21998, 0x219A8, 0x15055
BPS = (BP_ENTRY, BP_FRAME, BP_END, BP_AFTER, BP_AIITEM)
VGA, VGA_N = 0xA0000, 64000


def bits40(ids: tuple[int, ...]) -> bytes:
    v = 0
    for i in ids:
        v |= 1 << i
    return v.to_bytes(5, "little")


def show() -> None:
    n = L.d32(0x53BEB + DELTA) & 0xFF
    b = L.units("units", n)
    print("ubase", hex(L.ubase), "count", n, "cursor", L.cursor(),
          "scroll", struct.unpack("<ii", L.dump(0x53AA9 + DELTA, 8, "scroll")))
    for i in range(n):
        r = b[i * 80:(i + 1) * 80]
        sp = int.from_bytes(r[0x1A:0x1F], "little")
        ids = [k for k in range(40) if sp >> k & 1]
        hp, mhp, mp, mmp = struct.unpack_from("<hhhh", r, 0x40)
        print(f"#{i:2d} x={r[0]:2d} y={r[1]:2d} +5={r[5]:02x} +6={r[6]:02x} hp={hp}/{mhp} mp={mp}/{mmp} spells={ids}")


def palette(name: str) -> bytes:
    p = L.d32(0x53A65 + DELTA)
    return L.dump(p, 768, name)


def setup(spell: int, xy: tuple[int, int] | None) -> None:
    L.sm(L.ua(0, 0x1A), bits40((spell,)))
    L.sm(L.ua(0, 5), b"\x00")
    L.sm(L.ua(0, 0x44), struct.pack("<hh", 805, 805))
    if xy:
        L.sm(L.ua(11, 0), bytes(xy))
        L.sm(L.ua(11, 0x40), struct.pack("<hh", 9999, 9999))
    u0 = L.dump(L.ua(0, 0), 2, "u0xy")
    L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
    for a in BPS:
        L.cmd(f"BP 0170:{a + DELTA:x}")
    time.sleep(0.5)
    show()
    palette("pal_setup")
    L.dump(VGA, VGA_N, "vga_setup")
    print(L.cmd("BPLIST")[-300:])


def rec(tag: str, max_s: float) -> int:
    log: dict = {"tag": tag, "frames": []}
    t0 = time.time()
    while time.time() - t0 < max_s:
        r = L.wait_stop(max_s - (time.time() - t0), poll=0.7)
        if r is None:
            print("沒有停(逾時)")
            break
        nat = r.get("EIP", 0) - DELTA
        if nat == BP_ENTRY:
            st = struct.unpack("<4I", L.dump(r["ESP"], 16, "stk"))
            arg3 = st[3] - (1 << 32) if st[3] & 0x80000000 else st[3]
            log["entry"] = {"ret": hex(st[0] - DELTA), "unit": st[1], "radius0": st[2], "step": arg3}
            u = L.dump(L.ua(st[1], 0), 2, "uxy")
            sc = struct.unpack("<ii", L.dump(0x53AA9 + DELTA, 8, "scroll"))
            log["entry"].update(unit_xy=list(u), scroll=list(sc),
                                centre=[(u[0] - sc[0]) * 24 + 12, (u[1] - sc[1]) * 24 + 0x12])
            palette(f"{tag}_pal")
            L.dump(VGA, VGA_N, f"{tag}_entry")
            print("入口", log["entry"])
        elif nat == BP_FRAME:
            i, rad = r["EBX"], r["ESI"]
            L.dump(VGA, VGA_N, f"{tag}_f{i:02d}")
            log["frames"].append({"i": i, "radius": rad})
            print(f"幀 {i} 半徑 {rad}")
        elif nat == BP_AIITEM:
            st = struct.unpack("<3I", L.dump(r["ESP"], 12, "stk"))
            log["ai_item_action"] = {"ret": hex(st[0] - DELTA), "unit": st[1], "camp": st[2]}
            print("ai_item_action 入口", log["ai_item_action"])
        elif nat == BP_END:
            log["loop_end"] = True
            print("迴圈結束")
        elif nat == BP_AFTER:
            log["end"] = True
            L.dump(VGA, VGA_N, f"{tag}_ref")
            for a in BPS:
                L.cmd(f"BPDEL 0170:{a + DELTA:x}")
            print("redraw(0) 之後傾印基準畫面,斷點已清", L.cmd("BPLIST")[-120:].strip())
            L.resume()
            break
        else:
            print("停在不是設的斷點", hex(nat))
            log["unexpected"] = hex(nat)
            break
        L.resume()
    (OUT / f"{tag}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("frames", len(log["frames"]), "end", log.get("end"))
    return 0 if log.get("end") and len(log["frames"]) == 10 else 1


def to_png(tag: str) -> None:
    from PIL import Image
    for f in sorted(OUT.glob(f"{tag}_f*.bin")) + [OUT / "vga_setup.bin"]:
        palf = OUT / (f"{tag}_pal.bin" if f.name != "vga_setup.bin" else "pal_setup.bin")
        pal = bytes(min(255, (v & 0x3F) * 255 // 63) for v in palf.read_bytes())
        im = Image.frombytes("P", (320, 200), f.read_bytes())
        im.putpalette(pal)
        dst = f.with_suffix(".png")
        im.convert("RGB").save(dst)
        print(dst.name)


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        L.resume()
    elif cmd == "bpdel":
        for a in BPS:
            print(L.cmd(f"BPDEL 0170:{a + DELTA:x}")[-80:].strip())
    elif cmd == "rec":
        L.ubase = L.ubase or int((OUT / "ubase.txt").read_text())
        return rec(argv[1], float(argv[2]) if len(argv) > 2 else 240)
    elif cmd == "png":
        to_png(argv[1])
    elif cmd in ("units", "setup"):
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        (OUT / "ubase.txt").write_text(str(L.ubase))
        try:
            if cmd == "units":
                show()
            else:
                setup(int(argv[1]), (int(argv[2]), int(argv[3])) if len(argv) > 3 else None)
        finally:
            L.resume()
    elif cmd == "aiitem":
        # 敵 #11 的 slot2 放道具 38(攻擊道具,距離 2),索爾 HP 100 當目標;我方 #1..#4 設已行動,索爾清已行動(由他待機結束回合)
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        try:
            L.sm(L.ua(11, 0xE), bytes([0x00, int(argv[1]) if len(argv) > 1 else 38]))
            L.sm(L.ua(0, 0x40), struct.pack("<h", int(argv[2]) if len(argv) > 2 else 100))
            L.sm(L.ua(0, 5), bytes([0]))
            for i in (1, 2, 3, 4):
                L.sm(L.ua(i, 5), bytes([0x80]))
            u0 = L.dump(L.ua(0, 0), 2, "u0xy")
            L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
            for a in BPS:
                L.cmd(f"BP 0170:{a + DELTA:x}")
            time.sleep(0.5)
            show()
            b = L.dump(L.ua(11, 0xA), 16, "inv")
            print("#11 inv", " ".join(f"{b[k]:02x}:{b[k + 1]:02x}" for k in range(0, 16, 2)))
            print(L.cmd("BPLIST")[-200:])
        finally:
            L.resume()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
