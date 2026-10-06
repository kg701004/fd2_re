"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

由傾印算每格的地形類型(map_cell_info 的 out[5] = 地形表 [0x53a69] 第 tile 列的 byte 1)。
用法:terrain_map.py <map.bin> <ttable.bin> <units.bin> <mods.bin>
"""
import struct
import sys

W, H = 27, 21
cells = open(sys.argv[1], "rb").read()
tt = open(sys.argv[2], "rb").read()
units = open(sys.argv[3], "rb").read()
mods = open(sys.argv[4], "rb").read()
A = [struct.unpack_from("<i", mods, 4 * k)[0] for k in range(6)]
B = [struct.unpack_from("<i", mods, 0x18 + 4 * k)[0] for k in range(6)]
print("AP table", A, "DP table", B)


def ttype(x: int, y: int) -> int:
    tile = struct.unpack_from("<H", cells, 4 + 4 * (y * W + x))[0] & 0x3FF
    return tt[tile * 4 + 1]


occ = {}
for i in range(21):
    r = units[i * 80:(i + 1) * 80]
    occ[(r[0], r[1])] = i
print("    " + " ".join("%2d" % x for x in range(W)))
for y in range(H):
    row = []
    for x in range(W):
        t = ttype(x, y)
        row.append(("%d" % t if t < 10 else "?") + ("*" if (x, y) in occ else " "))
    print("%2d  " % y + " ".join(row))
for i in (0, 1, 2, 3, 4):
    r = units[i * 80:(i + 1) * 80]
    x, y = r[0], r[1]
    nb = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    print("unit", i, (x, y), "type", ttype(x, y), "race", r[0x1F], "class", r[0x20], "neighbours",
          [(p, ttype(*p), occ.get(p)) for p in nb if 0 <= p[0] < W and 0 <= p[1] < H])
