# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百一十四 cl10:城鎮 -> 出擊選人,錄 sortie_required_member_check / roster_move_member_to_slot1(只對原版 FD2.EXE)。

用法:
  python s10.py peek                 # 停住、印章節 / 名冊 / [0x53a45],恢復
  python s10.py pad                  # 名冊補到 17 人(複製第 1 / 3 / 4 / 6 筆到第 13..16 格)
  python s10.py rd ADDR N            # 讀 native 位址 ADDR 起 N bytes
  python s10.py wr ADDR HEX          # 寫 native 位址 ADDR
  python s10.py wl LIN HEX           # 寫線性位址
  python s10.py rl LIN N             # 讀線性位址
  python s10.py bp LIN | bpdel       # 設 / 清斷點(線性位址)
  python s10.py wait [秒]            # 等斷點停下,印暫存器
  python s10.py resume
"""
from __future__ import annotations

import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live, run  # noqa: E402

import os
INST = os.environ.get("S_INST", "cl10")
L = Live(INST, Path(__file__).resolve().parent / "cl" / f"{INST}_live")


def halt_town() -> tuple[int, int] | None:
    """原始 enter-debugger(城鎮裡 [0x53a45] 是 0,不能用 Live.halt);名冊指標合理才算停在遊戲裡。"""
    for _ in range(6):
        run(["enter-debugger", "--instance", INST])
        time.sleep(3)
        p = L.d32(0x53BF7 + DELTA)
        n = L.d32(0x53BFB + DELTA)
        if 0x100000 < p < 0x1000000 and 0 < n < 40:
            return p, n
        run(["resume", "--instance", INST])
        time.sleep(2)
    return None


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "resume":
        run(["resume", "--instance", INST])
        return 0
    if cmd == "wait":
        print(L.wait_stop(float(argv[1]) if len(argv) > 1 else 30))
        return 0
    if cmd in ("rl", "wl", "bp", "bpdel", "rd", "wr") and "--halted" in argv:
        argv = [a for a in argv if a != "--halted"]
        got = (0, 0)
    else:
        got = halt_town()
        if got is None:
            print("no game context")
            return 1
    stay = False
    try:
        p, n = got
        if cmd == "peek":
            b = L.dump(p, n * 80, "roster")
            print("roster", hex(p), "count", n, "chapter", hex(L.d32(0x53C03 + DELTA)), "[0x53a45]", hex(L.d32(0x53A45 + DELTA)),
                  "regs", {k: hex(v) for k, v in L.regs().items() if k in ("EIP", "EBP", "ESP")})
            for i in range(n):
                r = b[i * 80:(i + 1) * 80]
                hp, mhp = struct.unpack_from("<hh", r, 0x40)
                print(f"#{i:2d} +5={r[5]:02x} +7={r[7]:02x} +8={r[8]:02x} cls={r[0x20]:02x} lv={r[0x21]} hp={hp}/{mhp}")
        elif cmd == "pad":
            b = L.dump(p, n * 80, "roster")
            for k, src in enumerate((1, 3, 4, 6), 13):
                rec = bytearray(b[src * 80:(src + 1) * 80])
                rec[5] = 0
                for off in range(0, 80, 16):
                    L.sm(p + k * 80 + off, bytes(rec[off:off + 16]))
            L.sm(0x53BFB + DELTA, (17).to_bytes(4, "little"))
            print("count ->", L.d32(0x53BFB + DELTA))
        elif cmd == "rd":
            a, k = int(argv[1], 0), int(argv[2], 0)
            print(L.dump(a + DELTA, k, "rd").hex(" "))
        elif cmd == "wr":
            a = int(argv[1], 0)
            L.sm(a + DELTA, bytes.fromhex(argv[2]))
            print(L.dump(a + DELTA, len(bytes.fromhex(argv[2])), "wr").hex(" "))
        elif cmd == "rl":
            print(L.dump(int(argv[1], 0), int(argv[2], 0), "rl").hex(" "))
        elif cmd == "wl":
            L.sm(int(argv[1], 0), bytes.fromhex(argv[2]))
            print(L.dump(int(argv[1], 0), len(bytes.fromhex(argv[2])), "wl").hex(" "))
        elif cmd == "bp":
            print(L.cmd(f"BP 0170:{int(argv[1], 0):x}")[-200:])
        elif cmd == "bpdel":
            print(L.cmd("BPDEL *")[-200:])
        if "--stay" in argv:
            stay = True
    finally:
        if not stay:
            run(["resume", "--instance", INST])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
