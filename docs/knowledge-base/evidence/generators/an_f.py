"""續六十八 t_f.py 紀錄的逐呼叫整理:每次 0x14121 從入口到返回的停點序列,mode 2 搜尋以入口地圖重算。
用法:python an_f.py <tag> [tag...]
"""
import json
import sys

from live import ROOT
from sim_path import Grid, search

D = ROOT / ".wsl_build/ctr/v5/ch25"
tt = (D / "tt.bin").read_bytes()
calls = []
for tag in sys.argv[1:]:
    log = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    stops = [(n, s) for n, s in enumerate(x for st in log for x in st["stops"])]
    cur = None
    for n, s in stops:
        e = s["eip"]
        if e == "0x14121":
            u = (D / f"{s['dump']}.bin").read_bytes()
            r = u[s["unit"] * 80:(s["unit"] + 1) * 80]
            cur = {"tag": tag, "unit": s["unit"], "a2": s["a2"], "caller_ret": s["ret"], "pos": [r[0], r[1]],
                   "mode_b34": r[0x34] & 15, "mv": r[0x3B], "seq": []}
            calls.append(cur)
        if cur is None:
            continue
        item = {"eip": e}
        if e in ("0x14132", "0x141e2"):
            item["local"] = s["local"]
        elif e == "0x141b0":
            a = s["args"]
            item["args"] = {"start": a[1:3], "budget": a[3], "target": a[5:7], "mode": a[7]}
            g = Grid((D / f"{s['dump']}.bin").read_bytes(), tt, bytes(s["cost"]))
            res, _ = search(g, a[1], a[2], a[3], a[5], a[6], a[7])
            st = search.last
            cur["_sim"] = (g, res, st)
        elif e == "0x141b5":
            g, res, st = cur.pop("_sim")
            post = (D / f"{s['dump']}.bin").read_bytes()
            diff = sum(1 for i in range(len(post)) if g.b[i] != post[i])
            item.update({"eax": s["eax"], "outbuf2": s["outbuf"][:2], "sim_res": res,
                         "sim_buf": [st["buf"].get(0), st["buf"].get(1)], "sim_hits": st["hits"][:3] + (
                             ["..."] if len(st["hits"]) > 3 else []), "n_hits": len(st["hits"]), "grid_diff": diff})
        elif e in ("0x14203",):
            item["unit_arg"] = s["args"][0]
        elif e == "0x14215":
            item["args"] = s["args"][:4]
            item["a83"] = s["a83"]
        elif e in ("0x1421d", "0x14230", "0x141cd"):
            item["eax"] = s["eax"]
            if "a83" in s:
                item["a83"] = s["a83"]
        elif e in ("0x13e9c", "0x13fd4"):
            item["args"] = s["args"]
            item["ret"] = s["ret"]
        elif e == "0x13aef":
            item["eax"] = s["eax"]
        cur["seq"].append(item)
        if e == "0x13aef" and len(cur["seq"]) > 1:
            cur = None
for c in calls:
    print(json.dumps(c, ensure_ascii=False))
(D / "f_calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=1), encoding="utf-8")
