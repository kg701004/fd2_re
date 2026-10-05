"""列出單位記錄傾印(80 bytes/筆)的評分相關欄位。用法:units_print.py <bin>"""
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
import struct
import sys

b = open(sys.argv[1], "rb").read()
for i in range(len(b) // 80):
    r = b[i * 80:(i + 1) * 80]
    w = lambda o: struct.unpack_from("<H", r, o)[0]
    if not any(r):
        continue
    print(f"#{i:2d} xy=({r[0]:2d},{r[1]:2d}) f5={r[5]:#04x} side={r[6]} +7={r[7]:#04x} +8={r[8]:#04x} "
          f"race={r[0x1f]} cls={r[0x20]:#04x} lv={r[0x21]} +26={r[0x26]} +27={r[0x27]} "
          f"spells={r[0x1a:0x1f].hex()} slot0={r[0xa]:#04x} HP={w(0x40)}/{w(0x42)} MP={w(0x44)}/{w(0x46)}")
