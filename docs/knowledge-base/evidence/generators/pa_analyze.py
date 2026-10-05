"""0x14237 物理攻擊候選評分:由 DOSBox-X 傾印離線重算每組 (候選格, 目標) 的分數/優先級與最終選擇。

輸入:.wsl_build/ctr/pa/ 下的 <tag>_NNN_<EIP>.{regs,stack.bin,units.bin,list.bin,glob.bin} 與 map0.bin / tt.bin。
規則(本輪由反組譯 0x14237..0x145cc 讀出,待傾印驗證):
  地形:0x1f183(unit) 回 1 才套(與 scene_attack_resolve 相反);攻方用候選格、目標用自己的格;pct 截斷向零。
  原始 = 攻方 AP' - 目標 DP';> 2 → 優先級 8,否則 0;原始 > 目標目前 HP → ×2、優先級 0x12。
  0x1debe(目標, 格) 回 1(目標 +0x26 == 0、曼哈頓距離 1、目標裝備 kind0 武器列 +0xb <= 1)→ 加 攻方 DP' - 目標 AP'。
  目標 +8 == 0 → ×3/2(截斷向零)。先比優先級、再比分數,嚴格較大才換。
對照規則:doc11 舊述「<= 2 略過」、地形閘門同實戰極性、0x1debe 取攻方、×3/2 取 floor、同分取後者。
"""
import glob
import json
import os
import re
import struct
import sys

from _evpaths import GAME_S, ROOT_S, TOOLS  # noqa: E402

D = ROOT_S + "/.wsl_build/ctr/pa"
EXE = GAME_S + "/FD2.EXE"
W = 27
MAP = open(os.path.join(D, "map0.bin"), "rb").read()
TT = open(os.path.join(D, "tt.bin"), "rb").read()
AP_PCT = [5, 0, -5, -5, -5, 0]
DP_PCT = [0, 0, 10, 10, -5, 0]

# 道具列:obj3 檔案位置由 LE 表頭換算(與 disasm_le.py 相同的逐 object 公式)
sys.path.insert(0, str(TOOLS))
import disasm_le  # noqa: E402

_exe = open(EXE, "rb").read()
_meta = disasm_le.parse_le(_exe)


def item_row(item: int) -> bytes:
    """回傳道具 item 的 23-byte 效果列(0x602ad + item*0x17)。"""
    lin = 0x602AD + item * 0x17
    return bytes(disasm_le.object_bytes(_exe, _meta, lin, 0x17))


def ttype(x: int, y: int) -> int:
    tile = struct.unpack_from("<H", MAP, 4 + 4 * (y * W + x))[0] & 0x3FF
    return TT[tile * 4 + 1]


def rec(units: bytes, i: int) -> bytes:
    return units[i * 80:(i + 1) * 80]


def w(r: bytes, o: int) -> int:
    return struct.unpack_from("<H", r, o)[0]


def uses_row19(r: bytes) -> bool:
    """0x1f183:+7 == 0x1c 回 0;職業 0x13 或種族 4/5 回 1。"""
    if r[7] == 0x1C:
        return False
    return r[0x20] == 0x13 or r[0x1F] in (4, 5)


def tdiv(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def adj(stat: int, pct: int) -> int:
    return stat + tdiv(stat * pct, 100)


def equipped_weapon(r: bytes):
    for k in range(8):
        f, i = r[0xA + 2 * k], r[0xB + 2 * k]
        if f & 0x40 and i < 0x80:
            return i
    return None


def counter_gate(units: bytes, who: int, x: int, y: int) -> bool:
    r = rec(units, who)
    if r[0x26] != 0:
        return False
    if abs(x - r[0]) + abs(y - r[1]) != 1:
        return False
    wpn = equipped_weapon(r)
    return wpn is not None and item_row(wpn)[0xB] <= 1


def score(units, actor, tgt, x, y, variant="code"):
    a, t = rec(units, actor), rec(units, tgt)
    ap, dp = w(a, 0x48), w(a, 0x4A)
    tap, tdp = w(t, 0x48), w(t, 0x4A)
    gate = uses_row19 if variant != "terrain_like_attack" else (lambda r: not uses_row19(r))
    if gate(a):
        ty = ttype(x, y)
        ap, dp = adj(ap, AP_PCT[ty]), adj(dp, DP_PCT[ty])
    if gate(t):
        ty = ttype(t[0], t[1])
        tap, tdp = adj(tap, AP_PCT[ty]), adj(tdp, DP_PCT[ty])
    s = ap - tdp
    if variant == "doc_skip_le2" and s <= 2:
        return None
    pr = 8 if s > 2 else 0
    if s > w(t, 0x40):
        s, pr = s * 2, 0x12
    cg = counter_gate(units, actor if variant == "debe_actor" else tgt, x, y)
    if cg:
        s += dp - tap
    if t[8] == 0:
        s = (s * 3) // 2 if variant == "floor_x15" else tdiv(s * 3, 2)
    return {"prio": pr, "score": s, "tgt_ap": tap, "actor_ap": ap, "actor_dp": dp, "counter": cg}


def select(seq, variant="code"):
    best = None  # (prio, score, x, y, tgt)
    bp, bs = 0, 0
    for p in seq:
        if p is None:
            continue
        pr, s = p["prio"], p["score"]
        take = pr > bp or (pr == bp and (s >= bs if variant == "ties_last" else s > bs))
        if take:
            bp, bs, best = pr, s, (p["x"], p["y"], p["tgt"], pr)
    return best


def load(tag):
    stops = []
    for f in sorted(glob.glob(os.path.join(D, f"{tag}_*.regs"))):
        n, eip = re.search(r"_(\d{3})_([0-9A-F]{8})\.regs$", f).groups()
        R = {k: int(v, 16) for k, v in re.findall(r"(E[A-Z]{2})=([0-9A-F]{8})", open(f).read())}
        st = open(f.replace(".regs", ".stack.bin"), "rb").read()
        stops.append((int(n), eip, R, st, f.replace(".regs", "")))
    return stops


def s32(v):
    return v - (1 << 32) if v >= 1 << 31 else v


def analyze(tag):
    out = []
    cur = None
    for n, eip, R, st, base in load(tag):
        d = lambda o: struct.unpack_from("<i", st, o)[0]  # noqa: E731
        if eip == "001B0237":
            cur = {"actor": d(4), "a2": d(8), "ret": hex(d(0)), "units": open(base + ".units.bin", "rb").read(),
                   "pairs": [], "cands": None}
            out.append(cur)
        elif eip == "001B0368":
            L = open(base + ".list.bin", "rb").read()
            cur["cands"] = [(L[2 * i], L[2 * i + 1]) for i in range(R["EAX"])]
        elif eip == "001B04C5":
            g = open(base + ".glob.bin", "rb").read()
            cur["pairs"].append({"x": d(0x44), "y": d(0x48), "tgt": d(0x50), "live_score": s32(R["ESI"]),
                                 "live_prio": R["EDI"], "live_tgt_ap": s32(R["EBP"]), "live_actor_ap": d(0x3C),
                                 "live_actor_dp": d(0x38), "glob_before": list(struct.unpack_from("<4i", g))})
        elif eip == "001B059F":
            g = open(base + ".glob.bin", "rb").read()
            cur["end_glob"] = list(struct.unpack_from("<4i", g))
        elif eip == "001B148E":
            cur["attack"] = {"unit": d(4), "a2": d(8)}
    res = []
    for c in out:
        u, act = c["units"], c["actor"]
        wpn = equipped_weapon(rec(u, act))
        row = item_row(wpn)
        rng, thr = row[0xC], row[0xB]
        # 目標枚舉(0x14818 selector 1、range = 列 +0xc、內圈 < 列 +0xb 排除);本場景地形成本以曼哈頓近似,與實測比對
        exp_pairs = []
        for (x, y) in c["cands"] or []:
            for t in range(21):
                r = rec(u, t)
                if r[5] & 1 or r[6] == 0:
                    continue
                dd = abs(r[0] - x) + abs(r[1] - y)
                if thr <= dd <= rng:
                    exp_pairs.append((x, y, t))
        live_pairs = [(p["x"], p["y"], p["tgt"]) for p in c["pairs"]]
        pair_rows = []
        ok = True
        for p in c["pairs"]:
            e = score(u, act, p["tgt"], p["x"], p["y"])
            match = (e["prio"], e["score"], e["tgt_ap"], e["actor_ap"], e["actor_dp"]) == (
                p["live_prio"], p["live_score"], p["live_tgt_ap"], p["live_actor_ap"], p["live_actor_dp"])
            ok &= match
            row_ = {"cell": [p["x"], p["y"]], "target": p["tgt"], "live": [p["live_prio"], p["live_score"]],
                    "recomputed": [e["prio"], e["score"]], "counter": e["counter"], "target_ap_live": p["live_tgt_ap"],
                    "match": match}
            for v in ("doc_skip_le2", "terrain_like_attack", "debe_actor", "floor_x15"):
                ev = score(u, act, p["tgt"], p["x"], p["y"], v)
                row_["rival_" + v] = None if ev is None else [ev["prio"], ev["score"]]
            pair_rows.append(row_)
        seq = []
        for p in c["pairs"]:
            e = score(u, act, p["tgt"], p["x"], p["y"])
            seq.append(dict(e, x=p["x"], y=p["y"], tgt=p["tgt"]))
        pred = select(seq)
        # 逐步:每組比較後的全域值應等於下一個停點的 glob_before
        step_ok = True
        bp, bs, gl = 0, 0, c["pairs"][0]["glob_before"][:3] + [0] if c["pairs"] else None
        for i, p in enumerate(seq):
            if p["prio"] > bp or (p["prio"] == bp and p["score"] > bs):
                bp, bs, gl = p["prio"], p["score"], [p["x"], p["y"], p["tgt"], p["prio"]]
            nxt = c["pairs"][i + 1]["glob_before"] if i + 1 < len(seq) else c.get("end_glob")
            step_ok &= (nxt == gl)
        rivals = {}
        for v in ("doc_skip_le2", "terrain_like_attack", "debe_actor", "floor_x15"):
            rs = []
            for p in c["pairs"]:
                e = score(u, act, p["tgt"], p["x"], p["y"], v)
                rs.append(None if e is None else dict(e, x=p["x"], y=p["y"], tgt=p["tgt"]))
            rivals[v] = select(rs)
        rivals["ties_last"] = select(seq, "ties_last")
        start_glob = c["pairs"][0]["glob_before"] if c["pairs"] else None
        res.append({
            "actor": act, "a2": c["a2"], "ret": c["ret"], "weapon": wpn, "weapon_row_b_c": [thr, rng],
            "candidates": c["cands"], "pairs_live": live_pairs, "pairs_expected_manhattan": exp_pairs,
            "pairs_enumeration_match": live_pairs == exp_pairs, "pairs": pair_rows, "all_pairs_match": ok,
            "step_glob_match": step_ok, "end_glob": c.get("end_glob"), "start_glob": start_glob,
            "predicted_best": list(pred) if pred else None,
            "rival_best": {k: (list(v) if v else None) for k, v in rivals.items()},
            "attack_called": c.get("attack"),
        })
    return res


if __name__ == "__main__":
    allres = {t: analyze(t) for t in sys.argv[1:]}
    for t, rs in allres.items():
        for r in rs:
            print(t, "actor", r["actor"], "cands", len(r["candidates"] or []), "pairs", len(r["pairs"]),
                  "enum", r["pairs_enumeration_match"], "pairs_ok", r["all_pairs_match"], "steps_ok", r["step_glob_match"],
                  "end", r["end_glob"], "pred", r["predicted_best"], "attack", r["attack_called"])
            print("    rivals", r["rival_best"])
            for p in r["pairs"]:
                print("     ", p["cell"], p["target"], "live", p["live"], "re", p["recomputed"], "ctr", p["counter"],
                      "skip", p["rival_doc_skip_le2"], "terr", p["rival_terrain_like_attack"],
                      "debeA", p["rival_debe_actor"], "floor", p["rival_floor_x15"])
    json.dump(allres, open(os.path.join(D, "analyze.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
