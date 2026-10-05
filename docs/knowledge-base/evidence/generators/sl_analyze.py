"""0x14b78 落點選擇:由 sl_log.sh 的傾印逐段離線重算。用法:sl_analyze.py <標籤> [--json out]

每次呼叫(以 0x14b78 入口停點分段)檢查:
 (a) mode 1 取得方向陣列時,T' = 沿方向陣列走、最後一個泛洪標記 != 0xff 的格(0=下 y+1、1=左 x-1、2=上 y-1、其他=右 x+1);
 (b) 落點清單 = 0x146d1 之後地圖標記 != 0xff 的格,依 y 外層、x 內層;
 (c) 選擇 = 清單中曼哈頓距離 T' 最小,同距時 abs(|dx|-|dy|) 嚴格較小才換,完全同分保留先出現者。
對照規則:只看曼哈頓、同距取清單第一個(rival_first)。
"""
import glob
import json
import struct
import sys
from pathlib import Path

from _evpaths import ROOT  # noqa: E402

D = ROOT / ".wsl_build/ctr/sl"
W, HGT = 27, 21
tag = sys.argv[1]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def marks(p: Path) -> dict:
    b = p.read_bytes()
    return {(x, y): b[7 + 4 * (y * W + x)] for y in range(HGT) for x in range(W)}


def choose(cands: list, t: tuple, tie: bool) -> tuple:
    best, bd, bt = None, 0xFF, 0xFF
    for (x, y) in cands:
        dx, dy = x - t[0], y - t[1]
        d, a = abs(dx) + abs(dy), abs(abs(dx) - abs(dy))
        if d < bd or (tie and d == bd and a < bt):
            best, bd, bt = (x, y), d, a
    return best


stops = sorted(glob.glob(str(D / f"{tag}_*.regs")))
calls, cur = [], None
for r in stops:
    base = r[:-5]
    eip = int(Path(r).read_text().split()[0].split("=")[1], 16) - 0x19C000
    eax = int(Path(r).read_text().split()[1].split("=")[1], 16)
    st = Path(base + ".stack.bin").read_bytes()
    if eip == 0x14B78:
        us = Path(base + ".units.bin").read_bytes()
        unit = u32(st, 0xC)
        cur = {"stop": Path(r).name, "args": [u32(st, 4), u32(st, 8), unit, u32(st, 0x10)], "ret": hex(u32(st, 0) - 0x19C000),
               "actor_xy": [us[unit * 80], us[unit * 80 + 1]], "mv": us[unit * 80 + 0x3B]}
        calls.append(cur)
    elif eip == 0x14C42:
        cur["mode0"] = eax
    elif eip == 0x14C85:
        cur["mode1"] = eax
        if eax != 0xFF:
            cur["dirs"] = list(Path(base + ".dirs.bin").read_bytes()[:eax])
    elif eip == 0x14CCF:
        cur["_flood"] = marks(Path(base + ".map.bin"))
    elif eip == 0x14D37:
        cur["t_prime_live"] = [u32(st, 0x28), u32(st, 0x2C)]
    elif eip == 0x14D95:
        cur["_land"] = marks(Path(base + ".map.bin"))
    elif eip == 0x14DA1:
        lb = Path(base + ".list.bin").read_bytes()
        cur["list_live"] = [(lb[2 * i], lb[2 * i + 1]) for i in range(eax)]
    elif eip == 0x14E5B:
        cur["chosen_live"] = [u32(st, 0x28), u32(st, 0x2C)]
        cur["t_prime_at_select"] = [u32(st, 0x48), u32(st, 0x4C)]

ok = True
out = []
for c in calls:
    tx, ty = c["args"][0], c["args"][1]
    # (a) T'
    t = (tx, ty)
    if "dirs" in c:
        x, y = c["actor_xy"]
        for dcode in c["dirs"]:
            if dcode == 0:
                y += 1
            elif dcode == 1:
                x -= 1
            elif dcode == 2:
                y -= 1
            else:
                x += 1
            if c["_flood"][(x, y)] != 0xFF:
                t = (x, y)
        a_ok = list(t) == c["t_prime_live"]
    else:
        a_ok = True
    t_sel = tuple(c["t_prime_at_select"])
    # (b) 清單
    lst = [(x, y) for y in range(HGT) for x in range(W) if c["_land"][(x, y)] != 0xFF]
    b_ok = lst == c["list_live"]
    # (c) 選擇
    code = choose(c["list_live"], t_sel, tie=True)
    rival = choose(c["list_live"], t_sel, tie=False)
    c_ok = list(code) == c["chosen_live"]
    ok &= a_ok and b_ok and c_ok and t == t_sel
    near = sorted(c["list_live"], key=lambda p: abs(p[0] - t_sel[0]) + abs(p[1] - t_sel[1]))[:6]
    print(f"{c['stop']}: unit {c['args'][2]} {tuple(c['actor_xy'])} -> target ({tx},{ty}) a2={c['args'][3]} ret {c['ret']} mv {c['mv']} "
          f"mode0={c.get('mode0')} mode1={c.get('mode1')} dirs={c.get('dirs')}")
    print(f"   T' live {c.get('t_prime_live')} recompute {t} [{a_ok}] | list {len(lst)} [{b_ok}] | chosen live {c['chosen_live']} "
          f"rule {code} [{c_ok}] rival_first {rival} | nearest {near}")
    out.append({k: v for k, v in c.items() if not k.startswith("_")} | {
        "t_prime_recomputed": list(t), "list_matches_map": b_ok, "chosen_rule": list(code), "chosen_rival_first": list(rival),
        "nearest_candidates": [list(p) for p in near]})
print("ALL OK" if ok else "MISMATCH")
if "--json" in sys.argv:
    Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, ensure_ascii=False, default=list), encoding="utf-8")
