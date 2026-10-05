"""續六十五:collect_targets_in_range(0x14818)selector 2..3 的離線重算。

輸入:.wsl_build/ctr/sel/<tag>_{stack,map,units,out}.bin(返回點 0x1b09f0 的傾印)、costrows_live.bin、tt.bin。
重算(反組譯 0x14818..0x149f0):
  記號:rangeByte < 0x10 → 0x4e390 以成本列 0、budget = range 從原點展開(格旗標 0x40 不可進入、0x80 進入後歸零);
        extraThreshold != 0 時曼哈頓距離 < threshold 的格改成 0xff。
  收單位:依序號,+5 bit0 = 0、所站格記號 != 0xff、陣營:0 → +6 == 0、1 → != 0、2 → == 1、3 → == 2、其他值一律不收。
記號格與傾印逐格比較(不是拿傾印的記號去推清單),清單再與 outBuf / 回傳筆數比較。
"""
import json
import struct
import sys

from _evpaths import ROOT_S  # noqa: E402

D = ROOT_S + "/.wsl_build/ctr/sel"
W, H, N = 27, 21, 21
DELTA = 0x19C000
COST = open(D + "/costrows_live.bin", "rb").read()
TT = open(D + "/tt.bin", "rb").read()
TAGS = ["a1", "a2", "b1", "b2", "c1", "c2", "r1", "i1", "i2", "i3", "r2", "i4"]
CALLER = {0x1d1ce: "player_spell_select 0x1d1c9(法術 23 特例:range +3、thr 1、sel +6)",
          0x1d216: "player_spell_select 0x1d211(range +4、thr 0、sel +6,原點 = 游標)",
          0x18e2a: "player_action_ring 0x18e25(開指令環:range 1、thr 1、sel 0)",
          0x1bc41: "道具指令 0x1bc3c(開啟時計數:range 1、thr 1、sel 3 寫死,outBuf NULL)",
          0x1bed4: "道具指令 0x1becf(交給的對象清單:range 1、thr 1、sel 3 寫死)"}

SIDE_RULES = {
    "code": lambda sel, s: {0: s == 0, 1: s != 0, 2: s == 1, 3: s == 2}.get(sel, False),
    "sel_ge2_as_1": lambda sel, s: {0: s == 0}.get(sel, s != 0),           # 2、3 也當「非敵方」
    "sel3_eq3": lambda sel, s: {0: s == 0, 1: s != 0, 2: s == 1}.get(sel, s == sel),  # 3 取 +6 == 3
    "sel_ge4_as_3": lambda sel, s: {0: s == 0, 1: s != 0, 2: s == 1}.get(sel, s == 2),  # 4 以上落到 3 的判斷
}


def flood(cells: bytes, sx: int, sy: int, budget: int, row: bytes) -> dict:
    mark = {(sx, sy): budget}
    todo = [(sx, sy)]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            o = 4 + 4 * (ny * W + nx)
            tile = struct.unpack_from("<H", cells, o)[0] & 0x3FF
            cl = mark[(x, y)] - row[TT[tile * 4 + 1]]
            if cl < 0 or cl <= mark.get((nx, ny), -1):
                continue
            if cells[o + 2] & 0x40:
                continue
            if cells[o + 2] & 0x80:
                cl = 0
            mark[(nx, ny)] = cl
            todo.append((nx, ny))
    return mark


def analyse(tag: str) -> dict:
    st = open(f"{D}/{tag}_stack.bin", "rb").read()
    cells = open(f"{D}/{tag}_map.bin", "rb").read()
    units = open(f"{D}/{tag}_units.bin", "rb").read()
    count, = struct.unpack_from("<I", st, 0)
    ret, ox, oy, out, rng, thr, sel = struct.unpack_from("<7I", st, 0x14)
    assert rng < 0x10
    m = flood(cells, ox, oy, rng, COST[0:20])
    pred_mark = {}
    for (x, y), v in m.items():
        pred_mark[(x, y)] = 0xFF if abs(x - ox) + abs(y - oy) < thr else v
    live_mark = {(x, y): cells[7 + 4 * (y * W + x)] for y in range(H) for x in range(W)}
    mark_diff = [(x, y) for (x, y), v in live_mark.items() if pred_mark.get((x, y), 0xFF) != v]
    res = {}
    for name, rule in SIDE_RULES.items():
        lst = []
        for i in range(N):
            r = units[i * 80:(i + 1) * 80]
            if r[5] & 1 or pred_mark.get((r[0], r[1]), 0xFF) == 0xFF:
                continue
            if rule(sel, r[6]):
                lst.append(i)
        res[name] = lst
    no_thr = [i for i in range(N) if not units[i * 80 + 5] & 1 and (units[i * 80], units[i * 80 + 1]) in m
              and SIDE_RULES["code"](sel, units[i * 80 + 6])]
    actual = list(open(f"{D}/{tag}_out.bin", "rb").read()[:count]) if out else None
    near = []
    for i in range(N):
        r = units[i * 80:(i + 1) * 80]
        dd = abs(r[0] - ox) + abs(r[1] - oy)
        if dd <= max(rng, 1) + 1:
            near.append({"unit": i, "xy": [r[0], r[1]], "side_0x6": r[6], "f5": r[5], "dist": dd,
                         "mark_live": live_mark[(r[0], r[1])]})
    return {
        "tag": tag, "ret_static": hex(ret - DELTA), "caller": CALLER.get(ret - DELTA, "?"),
        "origin": [ox, oy], "range": rng, "extra_threshold": thr, "selector": sel,
        "count_live": count, "outbuf_live": actual,
        "predicted": res["code"], "count_match": count == len(res["code"]),
        "list_match": actual is None or actual == res["code"],
        "marks_match_recompute": not mark_diff, "mark_cells_differing": len(mark_diff),
        "marked_cells": sum(1 for v in pred_mark.values() if v != 0xFF),
        "rival_predictions": {k: v for k, v in res.items() if k != "code"} | {"ignore_extra_threshold": no_thr},
        "units_near_origin": near,
    }


if __name__ == "__main__":
    rows = [analyse(t) for t in TAGS]
    for r in rows:
        print(r["tag"], r["ret_static"], "origin", r["origin"], "rng", r["range"], "thr", r["extra_threshold"], "sel", r["selector"],
              "| live", r["count_live"], r["outbuf_live"], "| pred", r["predicted"],
              "| ok" if r["count_match"] and r["list_match"] and r["marks_match_recompute"] else "| MISMATCH",
              "marks", r["marked_cells"], "diff", r["mark_cell_differing"] if False else r["mark_cells_differing"])
        for k, v in r["rival_predictions"].items():
            if v != r["predicted"]:
                print("    rival", k, v)
    json.dump(rows, open(D + "/analyze.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(0 if all(r["count_match"] and r["list_match"] and r["marks_match_recompute"] for r in rows) else 1)
