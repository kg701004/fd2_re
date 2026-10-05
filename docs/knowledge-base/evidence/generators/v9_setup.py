# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十一(複製 v8_setup,輸出目錄改由第 3 個引數指定)第 25 章(map 24)受控設定:0x14121 mode 2 之後的流程。用法:python v9_setup.py <inst> <tag> <out_dir(相對 fd2_re)>
- 測試單位(未麻痺,清法術/MP/第二格道具):
  A = #48 留在 (10,10)、MV 原樣 —— 找得到對手,0x14b78 會移動
  B = #45 留在 (21,31)、MV 0 —— 找得到對手,但 0x14b78 走不動
  C = #53 搬到 (0,0) —— 對手都在預算 28 外,起點就是 mode 2 的目標 (0,0)
  D = #54 搬到 (0,2) —— 對照:同樣沒有對手可達,但不在 (0,0)
- 友軍 #17 從 (10,0) 搬到 (24,52)(否則 C/D 預算內有對手)
- 其他所有單位(索爾除外)麻痺 9
"""
import struct
import sys

from live import DELTA, ROOT, Live

inst, tag = sys.argv[1], sys.argv[2]
L = Live(inst, ROOT / sys.argv[3])
assert L.halt(), "halt"
n = L.d32(0x53BEB + DELTA) & 0xFF
u = L.units(f"{tag}_pre0_units", n)
TEST = {48: (10, 10), 45: (21, 31), 53: (0, 0), 54: (0, 2)}
for i, pos in TEST.items():
    if pos is not None:
        L.sm(L.ua(i, 0), bytes(pos))
    L.sm(L.ua(i, 0x26), b"\x00")
    L.sm(L.ua(i, 0x1A), b"\x00" * 5)
    L.sm(L.ua(i, 0x44), b"\x00\x00")
    L.sm(L.ua(i, 0xC), bytes([0x80, 0xFF]))
L.sm(L.ua(45, 0x3B), b"\x00")
L.sm(L.ua(17, 0), bytes([24, 52]))
for i in range(1, n):
    if i in TEST or u[i * 80 + 5] & 1:
        continue
    L.sm(L.ua(i, 0x26), b"\x09")
u2 = L.units(f"{tag}_pre_units", n)
for i in [0, 17, *TEST]:
    r = u2[i * 80:(i + 1) * 80]
    print(i, (r[0], r[1]), "side", r[6], "par", r[0x26], "mode", r[0x34] & 15, "mv", r[0x3B], "slots", list(r[0xA:0xE]),
          "spells", list(r[0x1A:0x1F]), "mp", struct.unpack_from("<H", r, 0x44)[0])
print("units", n, "paralysed", sum(1 for i in range(n) if u2[i * 80 + 0x26] == 9),
      "unparalysed", [i for i in range(n) if u2[i * 80 + 0x26] == 0 and not u2[i * 80 + 5] & 1])
L.resume()
