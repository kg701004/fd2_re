"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

續六十六 項目 3:逐鍵送出並記錄途中所有斷點停點(不假設狀態)。
用法:python tp_step.py <inst> <tag> <unit> <keys(逗號分隔)> [bp1,bp2,...](Ghidra 位址,預設 0x18890,0x18986,0x189fd)
每個鍵之後:等到 pane 連續 3 次 Running,期間每個停點記 EIP/EAX 與游標、單位 xy;最後截圖。
"""
import json
import sys
import time

from live import DELTA, ROOT, Live

inst, tag, unit, keys = sys.argv[1:5]
bps = [int(x, 16) for x in (sys.argv[5] if len(sys.argv) > 5 else "0x18890,0x18986,0x189fd").split(",")]
unit = int(unit)
L = Live(inst, ROOT / ".wsl_build/ctr/v3/ch19", 0x26BFC0)
out: dict = {"tag": tag, "unit": unit, "steps": []}
assert L.halt()
L.cmd("BPDEL *")
for a in bps:
    L.cmd(f"BP 0170:{a + DELTA:x}")
out["start"] = {"cursor": L.cursor(), "xy": list(L.dump(L.ua(unit), 2, "xy"))}
L.resume()
for n, k in enumerate(keys.split(",")):
    L.key(k, 1.0)
    stops = []
    idle = 0
    while idle < 3:
        time.sleep(1.2)
        if L.running():
            idle += 1
            continue
        idle = 0
        r = L.regs()
        stops.append({"eip": hex(r.get("EIP", 0) - DELTA), "eax": hex(r.get("EAX", 0)),
                      "cursor": L.cursor(), "xy": list(L.dump(L.ua(unit), 2, "xy"))})
        L.resume()
    assert L.halt()
    st = {"key": k, "stops": stops, "cursor": L.cursor(), "xy": list(L.dump(L.ua(unit), 2, "xy")),
          "f5": hex(L.dump(L.ua(unit, 5), 1, "f5")[0])}
    L.resume()
    L.shot(f"{tag}_{n}_{k}")
    out["steps"].append(st)
    print(json.dumps(st, ensure_ascii=False))
assert L.halt()
L.cmd("BPDEL *")
L.resume()
(L.out / f"{tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
