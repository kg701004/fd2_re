"""印出升級測試前後的攻方與盜賊欄位。用法:lvl_print.py <標籤> <攻方序號>"""
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
import struct
import sys

tag, idx = sys.argv[1], int(sys.argv[2])
d = r"C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/"
for ph in ("pre", "post"):
    b = open(d + f"{ph}_{tag}.bin", "rb").read()
    r = b[idx * 80:(idx + 1) * 80]
    w = lambda o: struct.unpack_from("<H", r, o)[0]
    print(ph, idx, "lv", r[0x21], "EX", r[0x3C], "base AP/DP/DX", w(0x37), w(0x39), w(0x3E), "HP", w(0x40), w(0x42),
          "MP", w(0x44), w(0x46), "derived AP DP HIT EV", w(0x48), w(0x4A), w(0x4C), w(0x4E), "bits", r[0x1A:0x1F].hex(), "f5", hex(r[5]))
    r = b[11 * 80:12 * 80]
    print(ph, 11, "lv", r[0x21], "HP", struct.unpack_from("<H", r, 0x40)[0], "f5", hex(r[5]))
