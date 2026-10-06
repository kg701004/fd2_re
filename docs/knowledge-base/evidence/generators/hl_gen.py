"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
由 hl_setup.sh 呼叫。

產生 AI 恢復術評分測試的 SM 指令(每行一條)。
用法:hl_gen.py <單位傾印.bin> <規格...>,規格 = 序號:x:y:HP:bit0(bit0 為 1 則設 +0x34 bit0,0 則清),MaxHP 不動。
"""
import struct
import sys

b = open(sys.argv[1], "rb").read()
for spec in sys.argv[2:]:
    i, x, y, hp, bit = (int(v) for v in spec.split(":"))
    base = 0x26BDC8 + i * 0x50
    r = b[i * 80:(i + 1) * 80]
    m34 = (r[0x34] | 1) if bit else (r[0x34] & 0xFE)
    print(f"SM 0170:{base:x} {x:02x} {y:02x}")
    print(f"SM 0170:{base + 5:x} 00")
    print(f"SM 0170:{base + 0x34:x} {m34:02x}")
    print(f"SM 0170:{base + 0x40:x} {hp & 0xff:02x} {hp >> 8:02x}")
