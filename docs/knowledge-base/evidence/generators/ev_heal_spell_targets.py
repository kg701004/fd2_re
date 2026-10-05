"""治療法術各次 collect_targets_in_range 傾印與恢復量量測的證據 JSON(doc98 續四十七)。"""
import json
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
D = ROOT / ".wsl_build" / "ctr"
OUT = out_path("heal_spell_targets_20260929.json")
W, H, N = 27, 21, 21


def side_ok(sel: int, side: int) -> bool:
    return {0: side == 0, 1: side != 0, 2: side == 1, 3: side == 2}[sel]


rounds = {}
for tag in ("hA1", "hA2", "hB0", "hB1", "hB2"):
    stack = (D / f"{tag}_stack.bin").read_bytes()
    cells = (D / f"{tag}_map.bin").read_bytes()
    units = (D / f"{tag}_units.bin").read_bytes()
    count, = struct.unpack_from("<I", stack, 0)
    ret, ox, oy, outp, rng, thr, sel = struct.unpack_from("<7I", stack, 0x14)
    mark = lambda x, y: cells[7 + 4 * (y * W + x)]
    rows, pred = [], []
    for i in range(N):
        r = units[i * 80:(i + 1) * 80]
        x, y, f5, side = r[0], r[1], r[5], r[6]
        m = mark(x, y)
        inc = not (f5 & 1) and m != 0xFF and side_ok(sel, side)
        if m != 0xFF or inc:
            rows.append({"unit": i, "x": x, "y": y, "side": side, "flags5": f5, "cell_mark": m, "predicted_in": inc})
        if inc:
            pred.append(i)
    rec = {
        "return_address_static": hex(ret - 0x19C000), "origin": [ox, oy], "out_buf_live": hex(outp),
        "range": rng, "threshold": thr, "selector": sel, "returned_count": count, "predicted": pred,
        "units_on_marked_cells": rows,
        "marked_cells": {f"{x},{y}": mark(x, y) for y in range(H) for x in range(W) if mark(x, y) != 0xFF},
    }
    if outp:
        out = (D / f"{tag}_out.bin").read_bytes()
        rec["out_buf"] = list(out[:count])
        assert rec["out_buf"] == pred, tag
    else:
        rec["out_buf"] = None
        assert count == len(pred), tag
    rounds[tag] = rec

heals = [
    {"round": "hA", "spell": 14, "amount": 140, "target": 3, "roll": 44, "predicted": 132, "hp_before": 100, "hp_after": 232, "max_hp": 867},
    {"round": "hA", "spell": 14, "amount": 140, "target": 4, "roll": 31, "predicted": 130, "hp_before": 100, "hp_after": 230, "max_hp": 918},
    {"round": "hA", "spell": 14, "amount": 140, "target": 5, "roll": 75, "predicted": 136, "hp_before": 10, "hp_after": 42, "max_hp": 42},
    {"round": "hB", "spell": 13, "amount": 70, "target": 1, "roll": 36, "predicted": 65, "hp_before": 100, "hp_after": 165, "max_hp": 782},
]
for h in heals:
    p = h["amount"] * 9 // 10 + h["roll"] * h["amount"] // 1000
    assert p == h["predicted"] and min(h["hp_before"] + p, h["max_hp"]) == h["hp_after"], h
post = {t: (D / f"{t}.bin").read_bytes()[80:160][0x3C] for t in ("h0", "post_hA", "post_hB")}
exp = {
    "caster": 1, "caster_level": 2, "caster_class": 21, "divisor": 32,
    "ex_before": post["h0"], "ex_after_hA": post["post_hA"], "ex_after_hB": post["post_hB"],
    "hA_accumulated": 40 * 40 * 132 // 867 + 36 * 40 * 130 // 918, "hB_accumulated": 32 * 40 * 65 // 782,
}
assert exp["ex_after_hA"] - exp["ex_before"] == exp["hA_accumulated"] // 32
assert exp["ex_after_hB"] - exp["ex_after_hA"] == exp["hB_accumulated"] // 32
doc = {
    "note": "DOSBox-X 記憶體傾印與斷點讀值整理;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。collect 的 predicted 依"
            "『+5 bit0 未設、格子記號 != 0xff、陣營符合 selector』離線計算;heal 的 predicted = amount*9//10 + roll*amount//1000。",
    "collect_rounds": rounds, "heals": heals, "experience": exp,
}
OUT.write_bytes((json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", OUT.stat().st_size, exp)
