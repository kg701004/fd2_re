"""續六十九:e2 的 field_event_lookup 停點逐筆重算。
規則(0x13a44 靜態):cell = grid + 4 + 4*(y*W + x);tile = u16 & 0x3ff;slot = byte2 & 0x1f;
terrain byte0 = TT[tile*4];(byte0 & 0x60) == 0 且 slot != 0 且 表[slot-1] = (id, sel) 的 id != 0xff 且 sel == 參數 → 寫 [0x51a8f] = id。
比對:預測的寫入 vs 實際 0x13a95 停點(緊接在該筆 0x13a44 之後)。
"""
import json
import sys
from pathlib import Path

from _evpaths import ROOT  # noqa: E402

D = ROOT / ".wsl_build/ctr/v7/ch25"
tag = sys.argv[1] if len(sys.argv) > 1 else "e2"
steps = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
stops = [s for st in steps for s in st["stops"]]
TT = (D / "e2_tt4k.bin").read_bytes()
W, H = 25, 53
GN = 4 + 4 * W * H
evtbl = None
rows = []
for i, s in enumerate(stops):
    if s["eip"] != "0x13a44":
        continue
    if "event_tbl" in s:
        evtbl = s["event_tbl"]
    nxt = stops[i + 1] if i + 1 < len(stops) else {}
    wrote = nxt.get("eip") == "0x13a95"
    c = s["cell"]
    tile = (c[0] | c[1] << 8) & 0x3FF
    slot = c[2] & 0x1F
    tb0 = TT[tile * 4] if tile * 4 < len(TT) else None
    pred = None
    if tb0 is not None:
        pred = False
        if (tb0 & 0x60) == 0 and slot != 0:
            assert evtbl is not None or s["in_grid"]
            tbl = evtbl if evtbl is not None else None
            if tbl is not None and 2 * (slot - 1) + 1 < len(tbl):
                eid, sel = tbl[2 * (slot - 1)], tbl[2 * (slot - 1) + 1]
                pred = eid != 0xFF and sel == s["sel"]
            elif tbl is None:
                pred = None
    rows.append({"x": s["x"], "y": s["y"], "sel": s["sel"], "ret": s["ret"], "in_grid": s["in_grid"],
                 "cell": c, "tile": tile, "slot": slot, "tt_b0": tb0, "pred_write": pred, "wrote": wrote,
                 "event_id": nxt.get("event_id") if wrote else None})
off = [r for r in rows if not r["in_grid"]]
mism = [r for r in rows if r["pred_write"] is not None and r["pred_write"] != r["wrote"]]
unk = [r for r in rows if r["pred_write"] is None]
print("lookups", len(rows), "off-grid", len(off), "writes", sum(r["wrote"] for r in rows),
      "pred-mismatch", len(mism), "unpredictable", len(unk))
for r in rows:
    if r["wrote"] or (not r["in_grid"] and r["slot"]):
        print(r)
first_off = off[0] if off else None
print("first off-grid", first_off and (first_off["x"], first_off["y"], (first_off["y"] * W + first_off["x"])))
print("in-grid x>=W", sum(1 for r in rows if r["in_grid"] and r["x"] >= W))
(D / f"{tag}_lookup_rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
