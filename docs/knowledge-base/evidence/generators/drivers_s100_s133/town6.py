# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""cl6 城鎮:原始 enter-debugger(不檢查單位表指標)讀名冊、把一名成員設成陣亡(+5 |= 1),再恢復。

用法: python town6.py peek | python town6.py kill IDX
"""
from __future__ import annotations

import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live import DELTA, Live, run  # noqa: E402

L = Live("cl6", Path(__file__).resolve().parent / "cl" / "cl6_live")


def main(argv: list[str]) -> int:
    for _ in range(6):
        run(["enter-debugger", "--instance", "cl6"])
        time.sleep(3)
        p = L.d32(0x53BF7 + DELTA)
        n = L.d32(0x53BFB + DELTA)
        print("ptr", hex(p), "roster count", n)
        if 0x100000 < p < 0x1000000 and 0 < n < 40:
            break
        run(["resume", "--instance", "cl6"])
        time.sleep(2)
    else:
        print("no game context")
        return 1
    try:
        b = L.dump(p, n * 80, "roster")
        for i in range(n):
            r = b[i * 80:(i + 1) * 80]
            hp, mhp = struct.unpack_from("<hh", r, 0x40)
            print(f"#{i:2d} +5={r[5]:02x} +7={r[7]:02x} cls={r[0x20]:02x} lv={r[0x21]} hp={hp}/{mhp}")
        if argv and argv[0] == "kill":
            i = int(argv[1])
            L.sm(p + i * 80 + 5, bytes([b[i * 80 + 5] | 1]))
            print("+5 ->", hex(L.dump(p + i * 80 + 5, 1, "k")[0]))
        if argv and argv[0] == "pad":
            for k, src in enumerate((1, 3, 4, 6), 13):
                rec = bytearray(b[src * 80:(src + 1) * 80])
                rec[5] = 0
                for off in range(0, 80, 16):
                    L.sm(p + k * 80 + off, bytes(rec[off:off + 16]))
            L.sm(0x53BFB + DELTA, (17).to_bytes(4, "little"))
            print("count ->", L.d32(0x53BFB + DELTA), "rec13 eq", L.dump(p + 13 * 80, 80, "r13") == bytes(
                b[80:85]) + bytes(1) + b[86:160])
    finally:
        run(["resume", "--instance", "cl6"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
