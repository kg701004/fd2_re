# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百三十一:(1) 移動範圍的明暗是不是 draw_terrain_layer 的換色段 (2) 續一百二十三第二輪的擺法在沒有斷點時畫哪幾階。
只對原版 FD2.EXE(WSL -d Ubuntu);只改模擬器記憶體裡的單位資料與游標。

用法(launch / hud / endturn 沿用 lc130,入口檔同為續一百三十的 5 個 EIP):
  python lc131.py select NAME          # 停住、游標移到索爾、恢復、Return 選單位、截一張圖
  python lc131.py snap NAME TAG        # 下斷點 draw_terrain_layer 入口(上一幀已畫完),停住後傾印全域、地圖格、地圖緩衝、換色表
  python lc131.py armB NAME            # lc130 arm 的擺法 + #5、#10 設為已倒下(第二輪的目標是 #0)
"""
from __future__ import annotations

import json
import struct
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live import DELTA, Live  # noqa: E402

DTL = 0x11EEE            # draw_terrain_layer 入口
G32 = {"phase": 0x53C1F, "last_adv": 0x539F4, "scroll_x": 0x53AA9, "scroll_y": 0x53AAD, "map": 0x53A51,
       "map_w": 0x53AC1, "map_h": 0x53AC5, "buf": 0x53A49, "remap_res": 0x53A6D, "sel_51a93": 0x51A93,
       "view_w": 0x51A87, "view_h": 0x51A8B, "cursor_x": 0x53AB1, "cursor_y": 0x53AB5}


def live(name: str) -> Live:
    return Live(name, (HERE / "cl" / f"{name}_live").resolve())


def snap(name: str, tag: str) -> int:
    L = live(name)
    out = L.out / f"snap_{tag}"
    out.mkdir(parents=True, exist_ok=True)
    L.out = out
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    L.cmd("BPDEL *")
    L.cmd(f"BP 0170:{DTL + DELTA:x}")
    L.resume()
    r = L.wait_stop(30, poll=0.5)
    L.cmd("BPDEL *")
    if not r or r.get("EIP") != DTL + DELTA:
        print("沒有停在 draw_terrain_layer 入口", r)
        L.resume()
        return 1
    try:
        g = {k: struct.unpack("<i", L.dump(a + DELTA, 4, "g"))[0] for k, a in G32.items()}
        g["regs"] = r
        w, h = g["map_w"], g["map_h"]
        L.dump(g["map"], 4 + w * h * 4, "map")
        L.dump(g["buf"], 0x25680, "buf")
        L.dump(g["remap_res"], 0x1000, "remap_res")
        L.dump(0x51A97 + DELTA, 20, "tri")
        L.units("units")
        L.cmd("BPLIST")
        time.sleep(0.5)
        g["bplist_tail"] = L.pane().splitlines()[-4:]
        (out / "g.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        print(tag, {k: g[k] for k in ("phase", "scroll_x", "scroll_y", "map_w", "map_h", "sel_51a93", "cursor_x", "cursor_y")})
    finally:
        L.resume()
    return 0


def main(argv: list[str]) -> int:
    cmd, name = argv[0], argv[1]
    if cmd == "snap":
        return snap(name, argv[2])
    L = live(name)
    if cmd == "select":
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        try:
            u0 = L.dump(L.ua(0, 0), 2, "u0xy")
            L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
            print("索爾", tuple(u0))
        finally:
            L.resume()
        time.sleep(7)
        L.key("Return", 1.0)
        time.sleep(7)
        print(L.shot("selected"))
        return 0
    if cmd in ("armB", "armC"):
        import lc130  # noqa: E402
        rc = lc130.main(["arm", name])
        if rc:
            return rc
        time.sleep(7)
        if not L.halt():
            print("停不進遊戲內容")
            return 1
        try:
            if cmd == "armB":
                # lc131a / lc131b:設成倒下後戰鬥在 #11 行動前就結束(城堡劇情 / 標題),改用 armC
                for i in (5, 10):
                    f5 = L.dump(L.ua(i, 5), 1, "f5")[0]
                    L.sm(L.ua(i, 5), bytes([f5 | 1]))
                    L.sm(L.ua(i, 0x40), struct.pack("<h", 0))
            else:
                # armC:#5、#10 不倒下,搬到遠處(其他 NPC 旁),#11 身邊只剩索爾
                L.sm(L.ua(5, 0), bytes([8, 7]))
                L.sm(L.ua(10, 0), bytes([6, 9]))
            L.sm(L.ua(0, 0x40), struct.pack("<h", 167))      # 第二輪開始時索爾 HP 167
            L.sm(L.ua(0, 0x3B), bytes([30]))                 # 還原 (1) 改的 MV
            print("#5/#10", [tuple(L.dump(L.ua(i, 0), 0x42, f"u{i}")[i2] for i2 in (0, 1, 5)) for i in (5, 10)])
        finally:
            L.resume()
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
