# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續七十四 v18b:假節點插入後(調色盤緩衝前 4 bytes = 0x1fa6b8),下一次 0x11d40(把 [0x53a65] 送進 DAC)時畫面的第 0 / 1 色。

用法:python t_v18b.py <inst> <out_dir> <tag> <keys逗號> [teleport]
- teleport:把敵兵 22 搬到索爾右邊 (8, 44),讓索爾能普通攻擊(戰鬥場景)。
- 斷點 0x11d40(引數 [esp+4] 起點、[esp+8] 終點、[esp+0xc] 減暗量):記前 3 次,之後拿掉斷點讓淡入淡出跑完。
  每次記 [0x53a65] 前 8 bytes(預測 b8a61f00 3f..)。每個鍵截圖。
"""
from __future__ import annotations

import json
import sys
import time

from drv import regs_rec, stack
from live import DELTA, ROOT, Live
from live import run as hrun

inst, out, tag, keys = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
L = Live(inst, ROOT / out)
assert L.halt()
pre = {"pal_ptr": hex(L.d32(0x53A65 + DELTA))}
pre["pal8"] = L.dump(L.d32(0x53A65 + DELTA), 8, f"{tag}_pal8").hex()
tp = [x for x in sys.argv[5:] if x.startswith("teleport")]
if tp:  # teleport 或 teleport=x:y
    xy = [int(v) for v in tp[0].split("=")[1].split(":")] if "=" in tp[0] else [8, 44]
    L.sm(L.ua(22, 0), bytes(xy))
    pre["u22"] = L.dump(L.ua(22, 0), 2, f"{tag}_u22").hex()
print("pre", json.dumps(pre), flush=True)
L.cmd("BPDEL *")
L.cmd(f"BP 0170:{0x11D40 + DELTA:x}")
L.resume()
log, hits = [], 0
for i, k in enumerate(keys):
    if k != "-":
        L.key(k, 1.0)
    idle = 0
    while idle < 3:
        time.sleep(1.2)
        if L.running():
            idle += 1
            continue
        idle = 0
        rec = regs_rec(L)
        rec["key_i"] = i
        a = stack(L, rec, 4, f"{tag}_{hits}_a")
        rec["ret"], rec["first"], rec["last"], rec["darken"] = hex(a[0] - DELTA), a[1], a[2], a[3]
        p = L.d32(0x53A65 + DELTA)
        rec["pal_ptr"], rec["pal8"] = hex(p), L.dump(p, 8, f"{tag}_{hits}_p8").hex()
        hits += 1
        if hits >= 3:
            L.cmd("BPDEL *")
        log.append(rec)
        print(json.dumps(rec)[:300], flush=True)
        L.shot(f"{tag}_hit{hits}")
        L.resume()
    L.shot(f"{tag}_{i:02d}_{k}")
(L.out / f"{tag}.json").write_text(json.dumps({"pre": pre, "stops": log}, indent=1), encoding="utf-8")
hrun(["enter-debugger", "--instance", inst])
time.sleep(3)
L.cmd("BPDEL *")
L.resume()
print("done", hits, flush=True)
