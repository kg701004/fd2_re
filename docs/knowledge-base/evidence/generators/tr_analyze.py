"""續六十四:0x14237 未驗證三項的離線重算(地形 3..5、0x1debe 的 +0xb>1 / 無武器分支、射程 byte >= 0x10)。

輸入:.wsl_build/ctr/tr/ 下 r1/r2/r3 的 <tag>_NNN_<EIP>.{regs,stack.bin,units.bin,list.bin,map.bin,glob.bin,item77.bin},
      post_tt.bin(改值後的地形表)、mods.bin(0x51a12 AP%/0x51a2a DP%)、costrows_live.bin(0x61646 起 29×20 移動成本列)。
重算規則(反組譯 0x14237 / 0x14818 / 0x1debe / 0x4e390 / 0x4e4be 讀出):
  候選格:0x4e390 以成本列 [0x1f183 ? 0x13 : 職業] 從攻方格展開,剩餘步數 -= 列[地形表 +1];0x40 格不可進入,0x80 格進入後歸零。
  目標:mode = 武器列 +0xc。mode < 0x10 → 以成本列 0 從候選格展開 mode 步(此時格旗標已被 0x4df4c 清掉),
        曼哈頓 < +0xb 的格排除;mode >= 0x10 → 十字:同列 |dx| <= mode-0x10 或同欄 |dy| <= mode-0x10,不排除內圈、不看阻擋。
        之後依單位序號收 +5 bit0 = 0、遮罩 != 0xff、陣營過濾(a2 == 0 → 旗標 1 → +6 != 0)。
  分數:同續六十三(地形在 0x1f183 回 1 時才套,截斷向零;0x1debe(目標, 格) 依序檢查 +0x26、曼哈頓 1、裝備 kind0 武器、列 +0xb <= 1)。
"""
import glob
import json
import os
import re
import struct
import sys

from _evpaths import GAME_S, ROOT_S, TOOLS, git_blob  # noqa: E402

D = ROOT_S + "/.wsl_build/ctr/tr"
EXE = GAME_S + "/FD2.EXE"
W, HGT = 27, 21
TT = open(os.path.join(D, "post_tt.bin"), "rb").read()
_mods = open(os.path.join(D, "mods.bin"), "rb").read()
AP_PCT = [struct.unpack_from("<i", _mods, 4 * i)[0] for i in range(6)]
DP_PCT = [struct.unpack_from("<i", _mods, 0x18 + 4 * i)[0] for i in range(6)]
COST = open(os.path.join(D, "costrows_live.bin"), "rb").read()

sys.path.insert(0, str(TOOLS))
import disasm_le  # noqa: E402

_exe = open(EXE, "rb").read()
_meta = disasm_le.parse_le(_exe)
# 當時(2026-10-01)的 native_movement_cost_rows.json:每列錯一個 byte,ae1ff0f3 才修正。
# 證據記錄的是當時那份檔案的狀態,所以以 blob sha 讀舊版,不讀目前的工作樹。
COST_ROWS_JSON = "docs/data/exe_tables/native_movement_cost_rows.json"
COST_ROWS_BLOB = "3c40a608d4a17a28ecf6d68c2da0fdd2de2aab50"  # git rev-parse ae1ff0f3^:<COST_ROWS_JSON>
JSON_ROWS = json.loads(git_blob(COST_ROWS_BLOB, COST_ROWS_JSON).decode("utf-8"))


def static_item_row(item: int) -> bytes:
    return bytes(disasm_le.object_bytes(_exe, _meta, 0x602AD + item * 0x17, 0x17))


def cost_row(sel: int, source: str = "live") -> bytes:
    if source == "json":
        return bytes.fromhex(JSON_ROWS[sel]["raw"])
    return COST[sel * 20:(sel + 1) * 20]


def rec(units: bytes, i: int) -> bytes:
    return units[i * 80:(i + 1) * 80]


def w(r: bytes, o: int) -> int:
    return struct.unpack_from("<H", r, o)[0]


def tile(grid: bytes, x: int, y: int) -> int:
    return struct.unpack_from("<H", grid, 4 + 4 * (y * W + x))[0] & 0x3FF


def ttype(grid: bytes, x: int, y: int) -> int:
    return TT[tile(grid, x, y) * 4 + 1]


def uses_row19(r: bytes) -> bool:
    if r[7] == 0x1C:
        return False
    return r[0x20] == 0x13 or r[0x1F] in (4, 5)


def tdiv(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def equipped_weapon(r: bytes):
    """find_equipped_slot(unit, 0) 0x1b83d:第一個旗標含 0x40 且 id < 0x80 的欄位。"""
    for k in range(8):
        f, i = r[0xA + 2 * k], r[0xB + 2 * k]
        if f & 0x40 and i < 0x80:
            return i
    return None


def flood(grid: bytes, sx: int, sy: int, budget: int, row: bytes, use_flags: bool) -> dict:
    """0x4e390 / 0x4e4be:回傳 {(x, y): 剩餘步數}。結果與展開順序無關(只在嚴格較大時覆寫)。"""
    mask = {(sx, sy): budget}
    todo = [(sx, sy)]
    while todo:
        x, y = todo.pop()
        cl0 = mask[(x, y)]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < W and 0 <= ny < HGT):
                continue
            cl = cl0 - row[ttype(grid, nx, ny)]
            if cl < 0 or cl <= mask.get((nx, ny), -1):
                continue
            if use_flags:
                fl = grid[4 + 4 * (ny * W + nx) + 2]
                if fl & 0x40:
                    continue
                if fl & 0x80:
                    cl = 0
            mask[(nx, ny)] = cl
            todo.append((nx, ny))
    return mask


def targets(units: bytes, grid: bytes, x: int, y: int, wrow: bytes, a2: int, variant: str = "code") -> list:
    mode, inner = wrow[0xC], wrow[0xB]
    if mode < 0x10 or variant == "cross_as_manhattan":
        rad = mode if mode < 0x10 else mode - 0x10
        reach = set(flood(grid, x, y, rad, cost_row(0), False))
        reach = {c for c in reach if abs(c[0] - x) + abs(c[1] - y) >= inner}
    else:
        r = mode - 0x10
        reach = {(cx, y) for cx in range(W) if abs(cx - x) <= r} | {(x, cy) for cy in range(HGT) if abs(cy - y) <= r}
        if variant == "cross_with_inner":
            reach = {c for c in reach if abs(c[0] - x) + abs(c[1] - y) >= inner}
    out = []
    for t in range(len(units) // 80):
        r = rec(units, t)
        if r[5] & 1 or (r[0], r[1]) not in reach:
            continue
        flag = 1 if a2 == 0 else 0  # 0x14237 傳 a2 == 0 ? 1 : 0;0x14818 旗標 0 收 +6 == 0、旗標 1 收 +6 != 0
        if (flag == 0 and r[6] == 0) or (flag == 1 and r[6] != 0):
            out.append(t)
    return out


def adj(stat: int, pct: int, floor: bool = False) -> int:
    return stat + ((stat * pct) // 100 if floor else tdiv(stat * pct, 100))


def pct_of(ty: int, variant: str):
    if variant == "terrain_ge3_zero" and ty >= 3:
        return 0, 0
    if variant == "terrain_ge3_as2" and ty >= 3:
        return AP_PCT[2], DP_PCT[2]
    return AP_PCT[ty], DP_PCT[ty]


def counter_gate(units: bytes, tgt: int, x: int, y: int, item_row, variant: str = "code") -> int:
    r = rec(units, tgt)
    if r[0x26] != 0:
        return -1
    if abs(x - r[0]) + abs(y - r[1]) != 1:
        return -1
    wpn = equipped_weapon(r)
    if wpn is None:
        return 1 if variant == "debe_unarmed_passes" else -1
    if item_row(wpn)[0xB] > 1 and variant != "debe_ignores_b":
        return -1
    return 1


def gate_reason(units: bytes, tgt: int, x: int, y: int, item_row) -> str:
    """0x1debe 依序檢查的第一個不成立條件(全部成立回 pass)。"""
    r = rec(units, tgt)
    if r[0x26] != 0:
        return "paralysed"
    if abs(x - r[0]) + abs(y - r[1]) != 1:
        return "distance_not_1"
    wpn = equipped_weapon(r)
    if wpn is None:
        return "no_kind0_weapon"
    if item_row(wpn)[0xB] > 1:
        return "weapon_row_0xb_gt_1"
    return "pass"


def score(units, grid, actor, tgt, x, y, item_row, variant="code"):
    a, t = rec(units, actor), rec(units, tgt)
    ap, dp = w(a, 0x48), w(a, 0x4A)
    tap, tdp = w(t, 0x48), w(t, 0x4A)
    fl = variant == "terrain_floor"
    if uses_row19(a):
        pa, pd = pct_of(ttype(grid, x, y), variant)
        ap, dp = adj(ap, pa, fl), adj(dp, pd, fl)
    if uses_row19(t):
        pa, pd = pct_of(ttype(grid, t[0], t[1]), variant)
        tap, tdp = adj(tap, pa, fl), adj(tdp, pd, fl)
    s = ap - tdp
    pr = 8 if s > 2 else 0
    if s > w(t, 0x40):
        s, pr = s * 2, 0x12
    cg = counter_gate(units, tgt, x, y, item_row, variant)
    if cg == 1:
        s += dp - tap
    if t[8] == 0:
        s = tdiv(s * 3, 2)
    return {"prio": pr, "score": s, "tgt_ap": tap, "actor_ap": ap, "actor_dp": dp, "gate": cg}


def select(seq):
    best, bp, bs = None, 0, 0
    for p in seq:
        if p["prio"] > bp or (p["prio"] == bp and p["score"] > bs):
            bp, bs, best = p["prio"], p["score"], [p["x"], p["y"], p["tgt"], p["prio"]]
    return best


def s32(v: int) -> int:
    return v - (1 << 32) if v >= 1 << 31 else v


def load(tag):
    stops = []
    for f in sorted(glob.glob(os.path.join(D, f"{tag}_*.regs"))):
        n, eip = re.search(r"_(\d{3})_([0-9A-F]{8})\.regs$", f).groups()
        R = {k: int(v, 16) for k, v in re.findall(r"(E[A-Z]{2})=([0-9A-F]{8})", open(f).read())}
        st = open(f.replace(".regs", ".stack.bin"), "rb").read()
        stops.append((int(n), eip, R, st, f.replace(".regs", "")))
    return stops


SCORE_RIVALS = ("terrain_ge3_zero", "terrain_ge3_as2", "terrain_floor", "debe_ignores_b", "debe_unarmed_passes")
TARGET_RIVALS = ("cross_as_manhattan", "cross_with_inner")


def analyze(tag):
    calls, cur, gate_eax = [], None, None
    for n, eip, R, st, base in load(tag):
        d = lambda o: struct.unpack_from("<i", st, o)[0]  # noqa: E731
        if eip == "001B0237":
            i77 = open(base + ".item77.bin", "rb").read()
            cur = {"actor": d(4), "a2": d(8), "units": open(base + ".units.bin", "rb").read(), "item77": i77,
                   "pairs": [], "cands": None, "grid": None}
            calls.append(cur)
        elif eip == "001B0368":
            L = open(base + ".list.bin", "rb").read()
            cur["cands"] = [(L[2 * i], L[2 * i + 1]) for i in range(R["EAX"])]
            cur["grid"] = open(base + ".map.bin", "rb").read()
        elif eip == "001B049E":
            gate_eax = s32(R["EAX"])
        elif eip == "001B04C5":
            g = open(base + ".glob.bin", "rb").read()
            cur["pairs"].append({"x": d(0x44), "y": d(0x48), "tgt": d(0x50), "live_score": s32(R["ESI"]),
                                 "live_prio": R["EDI"], "live_tgt_ap": s32(R["EBP"]), "live_actor_ap": d(0x3C),
                                 "live_actor_dp": d(0x38), "live_gate": gate_eax,
                                 "glob_before": list(struct.unpack_from("<4i", g))})
            gate_eax = None
        elif eip == "001B059F":
            cur["end_glob"] = list(struct.unpack_from("<4i", open(base + ".glob.bin", "rb").read()))
            if os.path.exists(base + ".item77_restored.bin"):
                cur["item77_restored"] = open(base + ".item77_restored.bin", "rb").read().hex()
        elif eip == "001B148E":
            cur["attack"] = {"unit": d(4)}
    res = []
    for c in calls:
        u, act, grid = c["units"], c["actor"], c["grid"]
        if act * 80 + 80 > len(u):  # 援軍(序號 > 20)不在 21 筆傾印內:只記候選數與組數
            res.append({"actor": act, "candidates": len(c["cands"] or []), "pairs": len(c["pairs"]),
                        "note": "援軍,單位記錄未傾印;0 組才可略過"})
            continue
        item_row = lambda i: c["item77"] if i == 77 else static_item_row(i)  # noqa: E731
        a = rec(u, act)
        wpn = equipped_weapon(a)
        wrow = item_row(wpn)
        sel = 0x13 if uses_row19(a) else a[0x20]
        # 候選格:用 0x1b0368 傾印的格旗標重算 0x4e390 的可達集合(live 成本列 vs json 成本列)
        live_reach = sorted((x, y) for y in range(HGT) for x in range(W) if grid[4 + 4 * (y * W + x) + 3] != 0xFF)
        rec_reach = sorted(flood(grid, a[0], a[1], a[0x3B], cost_row(sel), True))
        json_reach = sorted(flood(grid, a[0], a[1], a[0x3B], cost_row(sel, "json"), True))
        # 目標清單:依候選格順序 × 單位序號
        exp, riv = [], {k: [] for k in TARGET_RIVALS}
        for (x, y) in c["cands"] or []:
            exp += [(x, y, t) for t in targets(u, grid, x, y, wrow, c["a2"])]
            for k in TARGET_RIVALS:
                riv[k] += [(x, y, t) for t in targets(u, grid, x, y, wrow, c["a2"], k)]
        live_pairs = [(p["x"], p["y"], p["tgt"]) for p in c["pairs"]]
        rows, ok, seq = [], True, []
        rseq = {k: [] for k in SCORE_RIVALS}
        for p in c["pairs"]:
            e = score(u, grid, act, p["tgt"], p["x"], p["y"], item_row)
            m = (e["prio"], e["score"], e["tgt_ap"], e["actor_ap"], e["actor_dp"], e["gate"]) == (
                p["live_prio"], p["live_score"], p["live_tgt_ap"], p["live_actor_ap"], p["live_actor_dp"], p["live_gate"])
            ok &= m
            t = rec(u, p["tgt"])
            row_ = {"cell": [p["x"], p["y"]], "cell_type": ttype(grid, p["x"], p["y"]), "target": p["tgt"],
                    "target_cell_type": ttype(grid, t[0], t[1]), "target_weapon": equipped_weapon(t),
                    "gate_reason": gate_reason(u, p["tgt"], p["x"], p["y"], item_row),
                    "live": [p["live_prio"], p["live_score"], p["live_actor_ap"], p["live_actor_dp"], p["live_tgt_ap"],
                             p["live_gate"]],
                    "recomputed": [e["prio"], e["score"], e["actor_ap"], e["actor_dp"], e["tgt_ap"], e["gate"]],
                    "match": m}
            for k in SCORE_RIVALS:
                ev = score(u, grid, act, p["tgt"], p["x"], p["y"], item_row, k)
                row_["rival_" + k] = [ev["prio"], ev["score"], ev["actor_ap"], ev["actor_dp"], ev["tgt_ap"], ev["gate"]]
                rseq[k].append(dict(ev, x=p["x"], y=p["y"], tgt=p["tgt"]))
            rows.append(row_)
            seq.append(dict(e, x=p["x"], y=p["y"], tgt=p["tgt"]))
        step_ok, bp, bs = True, 0, 0
        gl = c["pairs"][0]["glob_before"] if c["pairs"] else None
        for i, p in enumerate(seq):
            if p["prio"] > bp or (p["prio"] == bp and p["score"] > bs):
                bp, bs, gl = p["prio"], p["score"], [p["x"], p["y"], p["tgt"], p["prio"]]
            nxt = c["pairs"][i + 1]["glob_before"] if i + 1 < len(seq) else c.get("end_glob")
            step_ok &= (nxt == gl)
        res.append({
            "actor": act, "a2": c["a2"], "actor_cell": [a[0], a[1]], "mv": a[0x3B], "cost_row": sel,
            "weapon": wpn, "weapon_row_b_c": [wrow[0xB], wrow[0xC]], "item77_row": c["item77"].hex(),
            "item77_restored": c.get("item77_restored"),
            "reach_live": live_reach, "reach_recomputed_live_costrow": rec_reach,
            "reach_recomputed_json_costrow": json_reach, "reach_match": live_reach == rec_reach,
            "reach_json_match": live_reach == json_reach, "candidates": c["cands"],
            "pairs_live": live_pairs, "pairs_expected": exp, "pairs_enumeration_match": live_pairs == exp,
            "pairs_rival": {k: {"pairs": v, "match": v == live_pairs} for k, v in riv.items()},
            "pairs": rows, "all_pairs_match": ok, "step_glob_match": step_ok, "end_glob": c.get("end_glob"),
            "predicted_best": select(seq), "rival_best": {k: select(v) for k, v in rseq.items()},
            "rival_pairs_differing": {k: sum(1 for r in rows if r["rival_" + k] != r["recomputed"]) for k in SCORE_RIVALS},
            "attack_called": c.get("attack"),
        })
    return res


if __name__ == "__main__":
    allres = {t: analyze(t) for t in sys.argv[1:]}
    for t, rs in allres.items():
        for r in rs:
            if "note" in r:
                print(t, "actor", r["actor"], "cands", r["candidates"], "pairs", r["pairs"], r["note"])
                continue
            print(t, "actor", r["actor"], "cell", r["actor_cell"], "row", r["cost_row"], "wpn", r["weapon"],
                  r["weapon_row_b_c"], "cands", len(r["candidates"] or []), "reach_ok", r["reach_match"],
                  "reach_json_ok", r["reach_json_match"], "enum", r["pairs_enumeration_match"],
                  {k: v["match"] for k, v in r["pairs_rival"].items()}, "pairs_ok", r["all_pairs_match"],
                  "steps_ok", r["step_glob_match"], "end", r["end_glob"], "pred", r["predicted_best"],
                  "attack", r["attack_called"], "restored", r["item77_restored"])
            print("    rival_best", r["rival_best"], "rival_diff", r["rival_pairs_differing"])
            for p in r["pairs"]:
                print("     ", p["cell"], "t", p["cell_type"], "tgt", p["target"], "tt", p["target_cell_type"], "w",
                      p["target_weapon"], "live", p["live"], "re", p["recomputed"], "ok" if p["match"] else "MISMATCH")
    json.dump(allres, open(os.path.join(D, "analyze.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
