"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

續六十九:0x12cea 目標在地圖外時是否不終止。用法:python t_hang.py <inst> <tag>
送 Return(索爾待機 → 敵方回合),停點 0x14121 / 0x141b5 / 0x141cd / 0x12cea / 0x12dab。
0x12cea 的目標 x >= W 或 y >= H 時:清掉斷點、恢復,之後每 6 秒停一次讀 EIP、游標、捲動、畫面相對位置,共 6 次。
"""
import json
import struct
import sys
import time

from drv import regs_rec, stack
from live import DELTA, ROOT, Live

inst, tag = sys.argv[1], sys.argv[2]
L = Live(inst, ROOT / ".wsl_build/ctr/v7/ch25")
assert L.halt()
W = L.d32(0x53AC1 + DELTA)
H = L.d32(0x53AC5 + DELTA)


def cur() -> dict:
    sx, sy, cx, cy, rx, ry = struct.unpack("<6i", L.dump(0x53AA9 + DELTA, 0x18, "cur"))
    return {"scroll": [sx, sy], "cursor": [cx, cy], "screen": [rx, ry]}


L.cmd("BPDEL *")
for a in (0x14121, 0x141B5, 0x141CD, 0x12CEA, 0x12DAB):
    L.cmd(f"BP 0170:{a + DELTA:x}")
L.resume()
L.key("Return", 1.0)
log: list[dict] = []
hang = None
idle = 0
t0 = time.time()
while time.time() - t0 < 900 and idle < 40:
    time.sleep(1.2)
    if L.running():
        idle += 1
        continue
    idle = 0
    rec = regs_rec(L)
    e = rec["eip"]
    if e == "0x14121":
        a = stack(L, rec, 3, f"{tag}_args")
        rec["ret"], rec["unit"], rec["a2"] = hex(a[0] - DELTA), a[1], a[2]
        rec["unit_xy"] = list(L.dump(L.ua(a[1]), 2, f"{tag}_uxy"))
    elif e == "0x12cea":
        a = stack(L, rec, 3, f"{tag}_args")
        rec["ret"], rec["xy"] = hex(a[0] - DELTA), a[1:]
        rec.update(cur())
        rec["a83"] = L.d32(0x51A83 + DELTA)
        if a[1] >= W or a[2] >= H:
            hang = rec
    elif e == "0x12dab":
        a = stack(L, rec, 2, f"{tag}_args")
        rec["ret"], rec["unit"] = hex(a[0] - DELTA), a[1]
        rec.update(cur())
    print(json.dumps(rec, ensure_ascii=False)[:300], flush=True)
    log.append(rec)
    if hang:
        break
    L.resume()
samples = []
if hang:
    L.cmd("BPDEL *")
    L.resume()
    time.sleep(20)
    for i in range(6):
        assert L.halt()
        r = regs_rec(L)
        s = {"eip": r["eip"], **cur(), "a83": L.d32(0x51A83 + DELTA)}
        samples.append(s)
        print("sample", s, flush=True)
        L.resume()
        L.shot(f"{tag}_hang{i}")
        time.sleep(6)
else:
    assert L.halt()
    L.cmd("BPDEL *")
    L.resume()
(L.out / f"{tag}.json").write_text(json.dumps({"W": W, "H": H, "stops": log, "hang_entry": hang,
                                                "samples": samples}, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
print("done hang" if hang else "done no-hang")
