# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百一十一 cl5:第 1 章戰場,給悠妮 8 個法術與 MP,逐一施放,讓修補版 dosbox-x 記下法術效果函式的呼叫。

用法:
  python cl5.py units            # 停住、印單位(序號、x、y、HP、MP、+5、法術欄),恢復
  python cl5.py setup            # 停住、悠妮法術欄 = SPELLS、MP 999/999、讀回,恢復
  python cl5.py act IDX          # 停住、清掉單位 IDX 的 +5 bit7(可再行動),恢復
  python cl5.py tp IDX X Y       # 停住、把單位 IDX 移到 (X, Y),恢復
  python cl5.py ring             # 讀 [0x53c57](環形選單目前項)
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live  # noqa: E402

OUT = Path(__file__).resolve().parent / "cl" / "cl6_live"
SPELLS = (4, 10, 13, 17, 18, 19, 20, 22)


def bits40(ids) -> bytes:
    v = 0
    for i in ids:
        v |= 1 << i
    return v.to_bytes(5, "little")


def show(L: Live) -> None:
    n = L.d32(0x53BEB + DELTA) & 0xFF
    b = L.units("units", n)
    print("ubase", hex(L.ubase), "count", n)
    for i in range(n):
        r = b[i * 80:(i + 1) * 80]
        sp = int.from_bytes(r[0x1A:0x1F], "little")
        ids = [k for k in range(40) if sp >> k & 1]
        hp, mhp, mp, mmp = struct.unpack_from("<hhhh", r, 0x40)[0:2] + struct.unpack_from("<hh", r, 0x44)
        print(f"#{i:2d} x={r[0]:2d} y={r[1]:2d} +5={r[5]:02x} +7={r[7]:02x} hp={hp}/{mhp} mp={mp}/{mmp} "
              f"cls={r[0x20]:02x} lv={r[0x21]} spells={ids}")


def main(argv: list[str]) -> int:
    L = Live("cl6", OUT)
    cmd = argv[0]
    if cmd == "ring":
        assert L.halt()
        print("ring", L.dump(0x53C57 + DELTA, 1, "ring")[0])
        L.resume()
        return 0
    assert L.halt(), "halt failed"
    try:
        if cmd == "units":
            show(L)
        elif cmd == "setup":
            L.sm(L.ua(1, 0x1A), bits40(SPELLS))
            L.sm(L.ua(1, 0x44), struct.pack("<hh", 999, 999))
            L.sm(L.ua(11, 0), bytes([23, 17]))
            L.sm(L.ua(11, 0x40), struct.pack("<hh", 999, 999))
            show(L)
            print("cursor", L.cursor())
        elif cmd == "act":
            i = int(argv[1])
            r = L.dump(L.ua(i, 5), 1, "u5")[0]
            L.sm(L.ua(i, 5), bytes([r & 0x7F]))
            print("+5", hex(r), "->", hex(L.dump(L.ua(i, 5), 1, "u5")[0]), "cursor", L.cursor())
        elif cmd == "poke":
            i, off, val = int(argv[1]), int(argv[2], 0), int(argv[3], 0)
            L.sm(L.ua(i, off), bytes([val]))
            print(f"#{i} +{off:#x} ->", hex(L.dump(L.ua(i, off), 1, "pk")[0]))
        elif cmd == "inv":
            i = int(argv[1])
            if len(argv) > 2:
                L.sm(L.ua(i, 0xA), bytes.fromhex(argv[2]))
            b = L.dump(L.ua(i, 0xA), 16, "inv")
            print(f"#{i} inv", " ".join(f"{b[k]:02x}:{b[k + 1]:02x}" for k in range(0, 16, 2)))
        elif cmd == "aicast":
            L.sm(L.ua(11, 0x1A), bits40(tuple(int(x) for x in argv[1:]) or (0, 4)))
            L.sm(L.ua(11, 0x44), struct.pack("<hh", 999, 999))
            inv = L.dump(L.ua(11, 0xA), 2, "w")
            L.sm(L.ua(11, 0xA), bytes([0]))
            L.sm(0x53AF9 + DELTA, bytes([1]))
            print("weapon slot0 was", inv.hex(), "now", L.dump(L.ua(11, 0xA), 2, "w").hex(),
                  "[0x53af9]", L.dump(0x53AF9 + DELTA, 1, "p")[0])
            show(L)
        elif cmd == "aiatk":
            L.sm(L.ua(11, 0x1A), bits40(()))
            L.sm(L.ua(11, 0xA), bytes([0x40]))
            L.sm(0x53AF9 + DELTA, bytes([1]))
            print("weapon", L.dump(L.ua(11, 0xA), 2, "w").hex(), "[0x53af9]", L.dump(0x53AF9 + DELTA, 1, "p")[0],
                  "cursor", L.cursor())
            show(L)
        elif cmd == "tp":
            i, x, y = map(int, argv[1:4])
            L.sm(L.ua(i, 0), bytes([x, y]))
            print("xy ->", tuple(L.dump(L.ua(i, 0), 2, "xy")))
    finally:
        L.resume()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
