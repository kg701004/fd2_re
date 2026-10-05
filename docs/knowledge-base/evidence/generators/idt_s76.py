# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十六:從事前傾印解 IDT(0x18a110)閘與其指向的 GDT 描述子;事後 GDT 對照。"""
import struct
import sys
from pathlib import Path

CTR = Path(r"C:\Users\kg701\Desktop\GAME\fd2_re\.wsl_build\ctr")
EXT = 0x100000
IDT = 0x18A110
GDT = 0x170010


def desc(b: bytes) -> dict:
    lo, hi = struct.unpack("<II", b)
    acc = (hi >> 8) & 0xFF
    return {"raw": b.hex(), "acc": acc, "p": acc >> 7, "dpl": (acc >> 5) & 3, "type5": acc & 0x1F,
            "base": (lo >> 16) | ((hi & 0xFF) << 16) | (hi & 0xFF000000)}


for run in sys.argv[1:]:
    d = CTR / run / "ch25"
    pre = (d / "r1_pre_ext1m.bin").read_bytes()
    post = (d / "r1_post0_gdt.bin").read_bytes() if (d / "r1_post0_gdt.bin").exists() else None
    print("==", run, "post gdt len", None if post is None else len(post))
    for v in list(range(0, 0x20)) :
        g = pre[IDT - EXT + v * 8: IDT - EXT + v * 8 + 8]
        off = struct.unpack_from("<H", g, 0)[0] | (struct.unpack_from("<H", g, 6)[0] << 16)
        sel = struct.unpack_from("<H", g, 2)[0]
        gacc = g[5]
        cs = pre[GDT - EXT + (sel & ~7): GDT - EXT + (sel & ~7) + 8]
        line = f"vec {v:02x} gate acc {gacc:02x} sel {sel:04x} off {off:08x} | cs pre {desc(cs)}"
        if post is not None and GDT - 0x170000 + (sel & ~7) + 8 <= len(post):
            line += f" | post {desc(post[GDT - 0x170000 + (sel & ~7):GDT - 0x170000 + (sel & ~7) + 8])}"
        print(line)
