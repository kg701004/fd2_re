"""續一百五十八證據:evidence/followups_s158_20261027.json(續一百五十七留下的項目;使用者 2026-10-27「未確認的部分依建議逐項自動處理」)。

(A) 第 2 項的單位層:第二輪多貼圖的 6 個單位是不是在鏡頭裡。不重跑實機,用續一百五十七的三份呼叫紀錄(lc157c / d / e):
    地形層每格一次 0x4e22a(ebx = 地形索引、ebp = 欄、s[4] = 列),拿 13 × 8 裡 96 格的地形索引逐張比對 33 張 FDFIELD 構成資源,
    求地圖與捲動;單位層每個 draw_unit_sprite(0x127e0,s[1] = 單位號)之後的貼圖 dest 換成視窗格 + 捲動 = 單位座標。
(B) 第 2 項的地形層:第二輪多出的指令數。同一 (貼圖函式, 地形索引) 的指令數取全部紀錄的最小值(計時器中斷算進遊戲選擇子,只會多不會少),
    依每圈鏡頭裡的圖塊組合預測每圈總數;同鏡頭的 lc157c / lc157d 當對照。
(C) BIOS tick 間隔不固定:wait_ticks(0x17aa9)返回時 eax = [0x46c],緊密輪詢,返回時間 = tick 改變的時間。
    遊戲把 PIT 改快(0x3ebb4)、由 16 通道軟體計時器 ISR(0x3ea8e)以累加器分頻,BIOS 那一通道(0x3c)週期 54925 µs。
    tick 時間點對 1 .. 20 ms 的格點求相位集中度;間隔換成格點數。
(D) 第 5 項第 4 次(lc157f,序章戰場、敵 #11 .. #16 同第 4 項、索爾 HP 1):FAIL —— 結束回合後索爾 HP 200、只有 #11 施法,
    GAME OVER 沒出現(閘門 0x22e5c 沒開,呼叫紀錄沒有 E 記錄)。量之前的預測 P1 .. P5 都沒有可判的資料(NOT TESTED)。
全部從 FD2.EXE、extracted/raw/FDFIELD、.wsl_build/lc157_live/ 重算;任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import struct
import sys
from collections import Counter, defaultdict

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

EXE_P = GAME / "FD2.EXE"
RAW = ROOT / ".wsl_build" / "lc157_live"
FIELD = ROOT / "extracted" / "raw" / "FDFIELD"
DRV = GEN_DIR / "drivers_s158"
OUT = out_path("followups_s158_20261027.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000                 # 原生 linear + DELTA = 執行期 EIP
RUNS = ("lc157c", "lc157d", "lc157e")

_D = EXE_P.read_bytes()
assert hashlib.md5(_D).hexdigest() == MD5
META = dl.parse_le(_D)


def code(lin: int, n: int) -> bytes:
    return bytes(dl.object_bytes(_D, META, lin, n))


def d32(lin: int) -> int:
    return struct.unpack_from("<i", _D, dl.lin2file(META, lin))[0]


def sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# 靜態:位元組逐一釘住(FD2.EXE;資料區位址是未重定位值)
PIN = {
    # draw_unit_sprite 的視窗裁切:x ∈ [sx − 1, sx + [0x51a87]]、y ∈ [sy − 1, sy + [0x51a8b] + 1](同 ev_s157)
    0x1284E: "4a39d50f8cefe2ffff8b15a93a00000315871a000039d50f8fdbe2ffff8b15ad3a00004a39d30f8ccce2ffff8b15ad3a0000"
             "03158b1a00004239d30f8fb7e2ffff",
    # wait_ticks:記下 [0x46c],緊密輪詢到差 ≥ n,返回 eax = [0x46c]
    0x17AB3: "8b542404b86c0400000fbf00a32c3a0000b86c0400000fbf002b052c3a000085c07d05050000010039d07ce5b86c0400000fbf00"
             "a32c3a0000c3",
    # 計時器 ISR 入口:[0x52be6] > 0(上一次還沒結束)→ 0x3ebad 只送 EOI 就返回,這次中斷不算
    0x3EA8E: "2e833de62b0000000f8711010000",
    0x3EBAD: "50b020e62058cf",
    # 每次中斷:各通道累加器 += [0x52be2](基底週期 µs),≥ 該通道週期 [0x52b14] 就減掉、到期數 + 1
    0x3EAD3: "8b15e22b0000bf0000000083bf942a00000275228b87d42a000003c23b87142b0000720c2b87142b0000ff87542b00008987d42a0000",
    # PIT 通道 0 模式 3,寫 16 位元除數
    0x3EBB4: "558bec5356579cfab036e6438b4508a3de2b0000eb00e6408ac4eb00e640",
    # µs → 除數:≥ 54925 µs 時 0(= 65536),否則 µs × 10000 / 8380
    0x3EBE4: "558bec535657b800000000817d088dd6000073118b4508bbbc200000b910270000f7e1f7f350e8a5ffffff83c4045f5e5bc9c3",
    # 基底週期 = 啟用通道裡最小的週期;變了才重設 PIT
    0x3EC2D: "83bf942a000000740c8b87142b00003bc173028bc883c70483ff4072e33b0de22b00007420890de22b000051e886ffffff",
    # 安裝:int 8 → 0x3ea8e;通道 0x3c(第 15 個)設週期 54925 µs(BIOS tick)
    0x3ED29: "b808000000ba8eea0200668ccbb4251e668edbcd211fc705d02a000002000000688dd600006a3ce8459cffff",
}
for _a, _hx in PIN.items():
    assert code(_a, len(_hx) // 2).hex() == _hx, (hex(_a), code(_a, len(_hx) // 2).hex())
VIEW_W, VIEW_H = d32(0x51A87), d32(0x51A8B)
assert (VIEW_W, VIEW_H) == (13, 8)
BIOS_US = 0xD68D
assert BIOS_US == 54925


# 呼叫紀錄
E_LAP, E_LAP_END, E_TERRAIN, E_UNITS, E_SPRITE = (a + DELTA for a in (0x152A0, 0x152BA, 0x11EEE, 0x127A9, 0x127E0))
E_BLIT, E_GREY, E_REMAP, E_WAIT = (a + DELTA for a in (0x4E22A, 0x4E1A6, 0x4E016, 0x17AA9))
_KV = re.compile(r" (?P<k>[int])=(?P<v>[0-9.]+)")


def parse(path) -> tuple[list[dict], dict[int, dict]]:
    """E 記錄(依序)與 R / A 記錄(以 seq 索引)。E 欄位:seq eip ret esp ss eax ebx ecx edx esi edi ebp s= c= m= i= n= t=。"""
    E, R = [], {}
    for line in open(path, encoding="ascii", errors="replace"):
        t = line.split()
        if not t:
            continue
        kv = {m["k"]: float(m["v"]) for m in _KV.finditer(line)}
        if t[0] == "E":
            s = [int(v, 16) for v in next(x for x in t if x.startswith("s="))[2:].split(",")]
            E.append({"seq": int(t[1]), "eip": int(t[2], 16), "ebx": int(t[7], 16), "ebp": int(t[12], 16), "s": s, **kv})
        elif t[0] in ("R", "A"):
            R[int(t[1])] = {"kind": t[0], "eax": int(t[3], 16) if t[0] == "R" else None, **kv}
    return E, R


def laps(E: list[dict]) -> list[list[dict]]:
    out, cur = [], None
    for e in E:
        if e["eip"] == E_LAP:
            cur = [e]
        elif e["eip"] == E_LAP_END and cur is not None:
            out.append(cur)
            cur = None
        elif cur is not None:
            cur.append(e)
    return out


LOGS = {nm: parse(RAW / f"{nm}_redraw_icount.txt") for nm in RUNS}
LAPS = {nm: laps(LOGS[nm][0]) for nm in RUNS}
assert all(len(v) == 8 for v in LAPS.values())

# ---------------------------------------------------------------------------------------------------------------
# (A) 鏡頭與單位位置
MAPS = {}
for _n in range(33):                      # FDFIELD 每 3 個資源一張地圖,共 33 張(tools/extract_maps.py)
    _b = (FIELD / f"FDFIELD_{3 * _n:03d}.bin").read_bytes()
    _w, _h = struct.unpack_from("<HH", _b, 0)
    MAPS[_n] = (_w, _h, [struct.unpack_from("<H", _b, 4 + 4 * k)[0] for k in range(_w * _h)])
assert len(MAPS) == 33
CELL, PITCH, UNIT_UP = 24, 0x1C8, 6       # 24 × 24 格、視窗緩衝 stride 456、單位圖上移 6 列(ev_s157)


def solve(grid: dict[tuple[int, int], int]) -> list[tuple[int, int, int]]:
    """所有讓視窗內已知格的地形索引全部相符的 (地圖, sx, sy)。"""
    hits = []
    for n, (w, h, cells) in MAPS.items():
        for sy in range(h - VIEW_H + 1):
            for sx in range(w - VIEW_W + 1):
                if all(cells[(sy + r) * w + sx + c] == v for (c, r), v in grid.items()):
                    hits.append((n, sx, sy))
    return hits


def lap_view(lap: list[dict]) -> dict:
    iu = next(i for i, e in enumerate(lap) if e["eip"] == E_UNITS)
    grid, d0 = {}, None
    for e in lap[:iu]:
        if e["eip"] == E_BLIT:
            c, r = e["ebp"], e["s"][3]
            assert (c, r) not in grid and 0 <= c < VIEW_W and 0 <= r < VIEW_H
            grid[(c, r)] = e["ebx"]
            if (c, r) == (0, 0):
                d0 = e["s"][1]
            # 同一格的 dest 與 (0, 0) 的關係:欄 24、列 24 × stride
            assert d0 is None or e["s"][1] - d0 == CELL * c + CELL * PITCH * r
    remap = sum(e["eip"] == E_REMAP for e in lap[:iu])
    drawn, unit = [], None
    for e in lap[iu:]:
        if e["eip"] == E_SPRITE:
            unit = e["s"][0]
        elif e["eip"] in (E_BLIT, E_GREY) and unit is not None:
            y, x = divmod(e["s"][1] - d0 + UNIT_UP * PITCH, PITCH)
            assert x % CELL == 0 and y % CELL == 0, (unit, x, y)
            drawn.append((unit, x // CELL, y // CELL))
            unit = None
    return {"grid": grid, "remap_cells": remap, "hits": solve(grid), "drawn": drawn}


VIEWS = {nm: [lap_view(lp) for lp in LAPS[nm]] for nm in RUNS}
for nm in RUNS:
    for v in VIEWS[nm]:
        # 96 格走 0x4e22a、8 格走 0x4e016(remap 版);96 格在 33 張地圖裡只對到一處
        assert len(v["grid"]) + v["remap_cells"] == VIEW_W * VIEW_H and len(v["grid"]) == 96 and len(v["hits"]) == 1, (nm, len(v["grid"]), v["hits"])
SCROLL = {nm: {tuple(v["hits"][0]) for v in VIEWS[nm]} for nm in RUNS}
assert SCROLL == {"lc157c": {(1, 12, 0)}, "lc157d": {(1, 12, 0)}, "lc157e": {(1, 14, 8)}}, SCROLL
DRAWN = {nm: {tuple(v["drawn"]) for v in VIEWS[nm]} for nm in RUNS}
assert all(len(s) == 1 for s in DRAWN.values())
POS = {}
for nm in RUNS:
    _, sx, sy = next(iter(SCROLL[nm]))
    POS[nm] = {u: (sx + cx, sy + cy) for u, cx, cy in next(iter(DRAWN[nm]))}
assert POS["lc157c"] == POS["lc157d"] == {10: (19, 6)}
assert POS["lc157e"] == {0: (20, 14), 1: (23, 16), 2: (22, 13), 3: (23, 14), 4: (24, 15), 6: (19, 13), 11: (19, 14)}, POS
# 獨立來源:lc157e 的 armC 輸出(#0 讀回、#11 / #5 / #10 寫入後逐 byte 讀回)
_armc = (RAW / "lc157e_armC.out").read_text(encoding="utf-8")
assert re.search(r"#0 xy \(20, 14\)", _armc) and re.search(r"OK  #11 xy     want 130e got 130e", _armc)
_rb = {m[1]: bytes.fromhex(m[2]) for m in re.finditer(r"OK  #(\d+) xy\s+want (\w{4}) got \2", _armc)}
ARMC_XY = {int(k): (v[0], v[1]) for k, v in _rb.items()}
assert ARMC_XY == {11: (19, 14), 5: (8, 7), 10: (6, 9)}, ARMC_XY
assert POS["lc157e"][0] == (20, 14) and POS["lc157e"][11] == ARMC_XY[11]


def in_clip(xy: tuple[int, int], scroll: tuple[int, int, int]) -> bool:
    """draw_unit_sprite 的裁切(0x1284e):x ∈ [sx − 1, sx + W]、y ∈ [sy − 1, sy + H + 1]。"""
    _, sx, sy = scroll
    return sx - 1 <= xy[0] <= sx + VIEW_W and sy - 1 <= xy[1] <= sy + VIEW_H + 1


S1, S2 = next(iter(SCROLL["lc157c"])), next(iter(SCROLL["lc157e"]))
# 第二輪貼圖的單位都在第二輪的裁切範圍內;armC 搬走的 #5、#10 在範圍外(所以沒貼)
assert all(in_clip(xy, S2) for xy in POS["lc157e"].values())
assert not in_clip(ARMC_XY[5], S2) and not in_clip(ARMC_XY[10], S2)
# 第一輪:#10 在範圍內;第二輪那 7 個位置都在第一輪範圍外(y ≥ 13 > sy + H + 1 = 9)
assert in_clip(POS["lc157c"][10], S1)
OUT1 = {u: in_clip(xy, S1) for u, xy in POS["lc157e"].items()}
assert not any(OUT1.values()), OUT1
A = {"method": "地形層 0x4e22a 的 (ebp 欄, s[4] 列, ebx 地形索引) 對 33 張 FDFIELD 構成資源逐格比對;單位貼圖 dest − (0, 0) 格 dest + 6 × 456 → 視窗格",
     "maps_searched": len(MAPS), "cells_matched_per_lap": sorted({len(v["grid"]) for nm in RUNS for v in VIEWS[nm]}),
     "remap_cells_per_lap": sorted({v["remap_cells"] for nm in RUNS for v in VIEWS[nm]}),
     "map_scroll": {nm: list(next(iter(SCROLL[nm]))) for nm in RUNS},
     "unit_positions_from_blits": {nm: {str(u): list(xy) for u, xy in POS[nm].items()} for nm in RUNS},
     "armC_readback_xy": {str(u): list(xy) for u, xy in ARMC_XY.items()},
     "clip": {"x": "[sx - 1, sx + 13]", "y": "[sy - 1, sy + 9]"},
     "round2_units_inside_round1_clip": OUT1,
     "premise": "#1 .. #4 是已行動的我方(+5 = 0x80),敵方回合不動;lc130 arm 與 lc131 armC 都沒有寫它們的座標,所以兩輪位置相同。"
                "#6 在第一輪的位置沒有紀錄(敵方回合裡 #5 .. #10 先行動),只知道第一輪沒貼圖",
     "conclusion": "兩輪的鏡頭不同:第一輪地圖 1 捲動 (12, 0)(#10 在 (19, 6),光束打 #10),第二輪 (14, 8)。"
                   "第二輪貼圖的 7 個單位都在 (14, 8) 的裁切範圍內,那 7 個位置都在 (12, 0) 的範圍外。"}

# ---------------------------------------------------------------------------------------------------------------
# (B) 地形層指令數:圖塊組合
def terrain_rows(nm: str) -> list[dict]:
    E, R = LOGS[nm]
    rows = []
    for lp in LAPS[nm]:
        tr = next(e for e in lp if e["eip"] == E_TERRAIN)
        i0, i1 = tr["i"], R[tr["seq"]]["i"]
        bl = [(e["eip"], e["ebx"], R[e["seq"]]["i"] - e["i"]) for e in lp
              if e["eip"] in (E_BLIT, E_REMAP) and i0 <= e["i"] <= i1]
        assert len(bl) == 104
        rows.append({"terrain_insn": i1 - i0, "blits": bl})
    return rows


TR = {nm: terrain_rows(nm) for nm in RUNS}
_cost = defaultdict(list)
for nm in RUNS:
    for r in TR[nm]:
        for f, tile, n in r["blits"]:
            _cost[(f, tile)].append(n)
MINC = {k: min(v) for k, v in _cost.items()}
# 同一 (函式, 地形索引) 的指令數:九成以上落在最小值 + 10 之內;其餘多出的都是 250 以上(計時器中斷的量級),
# 沒有介於兩者之間的值
CORE, ISR_MIN = 10, 250
_ex = [n - MINC[k] for k, v in _cost.items() for n in v]
_core = sum(x <= CORE for x in _ex)
assert _core / len(_ex) >= 0.9 and all(x >= ISR_MIN for x in _ex if x > CORE), (_core, len(_ex))
for nm in RUNS:
    for r in TR[nm]:
        r["pred"] = sum(MINC[(f, t)] for f, t, _ in r["blits"])
        r["actual"] = sum(n for *_, n in r["blits"])
PRED = {nm: sorted({r["pred"] for r in TR[nm]}) for nm in RUNS}
assert all(len(v) == 1 for v in PRED.values())
P_C, P_D, P_E = (PRED[nm][0] for nm in RUNS)
MED = {nm: statistics.median(r["actual"] for r in TR[nm]) for nm in RUNS}
MED_T = {nm: statistics.median(r["terrain_insn"] for r in TR[nm]) for nm in RUNS}
RESID = {nm: statistics.median(r["actual"] - r["pred"] for r in TR[nm]) for nm in RUNS}
# 同鏡頭(c / d)預測差 0;第二輪預測多的與實際多的,差距小於「同鏡頭兩份的實際差」加一份裡殘差的起伏
assert P_C == P_D and P_E - P_C > 4000
_null = abs(MED["lc157d"] - MED["lc157c"])
_spread = max(max(r["actual"] - r["pred"] for r in TR[nm]) - min(r["actual"] - r["pred"] for r in TR[nm]) for nm in RUNS)
assert abs((MED["lc157e"] - MED["lc157c"]) - (P_E - P_C)) < _null + _spread, (MED, P_E - P_C, _null, _spread)
# 貼圖以外的地形層指令數兩輪相近:地形層的差距幾乎全在 104 次貼圖
_other = {nm: statistics.median(r["terrain_insn"] - r["actual"] for r in TR[nm]) for nm in RUNS}
assert abs(_other["lc157e"] - _other["lc157c"]) < 500, _other
B = {"method": "地形層期間 104 次貼圖(0x4e22a 96 + 0x4e016 8)的 R.i − E.i;每個 (函式, 地形索引) 取三份紀錄的最小值當不含中斷的成本",
     "keys": len(_cost), "blits": len(_ex), "blits_within_min_plus_10": _core,
     "excess_over_10_min_max_count": [min(x for x in _ex if x > CORE), max(_ex), sum(x > CORE for x in _ex)],
     "pred_per_lap": {nm: PRED[nm][0] for nm in RUNS}, "pred_diff_e_minus_c": P_E - P_C,
     "actual_blit_sum_median": MED, "actual_diff_e_minus_c": MED["lc157e"] - MED["lc157c"],
     "actual_diff_d_minus_c": MED["lc157d"] - MED["lc157c"], "residual_median": RESID, "residual_spread_max": _spread,
     "terrain_insn_median": MED_T, "terrain_minus_blits_median": _other,
     "conclusion": f"第二輪地形層多的指令數來自鏡頭裡的圖塊不同:依圖塊組合預測多 {P_E - P_C},實際中位數多 {MED['lc157e'] - MED['lc157c']};"
                   "同鏡頭的 lc157c / lc157d 預測相同;貼圖以外的地形層指令數兩輪相近。"}

# ---------------------------------------------------------------------------------------------------------------
# (C) BIOS tick:5 ms 格點
TICK_MS = 1000 * 65536 / 1193182
assert abs(TICK_MS - BIOS_US / 1000) < 0.001     # BIOS 通道週期就是名目 tick


def tick_times(nm: str) -> list[float]:
    E, R = LOGS[nm]
    first = {}
    for e in E:
        if e["eip"] == E_WAIT and e["seq"] in R and R[e["seq"]]["kind"] == "R":
            first.setdefault(R[e["seq"]]["eax"] & 0xFFFF, R[e["seq"]]["t"])
    tk = sorted(first.items(), key=lambda kv: kv[1])
    assert all(a[0] < b[0] for a, b in zip(tk, tk[1:])), "tick 值在紀錄期間回繞"
    return tk


def resultant(ts: list[float], p: float) -> float:
    c = sum(math.cos(2 * math.pi * t / p) for t in ts)
    s = sum(math.sin(2 * math.pi * t / p) for t in ts)
    return math.hypot(c, s) / len(ts)


GRID_MS = 5.0
C_RUNS = {}
for nm in RUNS:
    tk = tick_times(nm)
    ts = [t for _, t in tk]
    scan = sorted(((resultant(ts, k / 1000), k / 1000) for k in range(1000, 20001)), reverse=True)
    best_r, best_p = scan[0]
    # 最佳格點 5.000 ms;次佳只有它的約數(2.5、1.25、1.0)與 ±0.001 的鄰居
    assert best_p == GRID_MS and best_r >= 0.85, (nm, scan[:3])
    assert all(abs(GRID_MS / p - round(GRID_MS / p)) < 1e-9 or abs(p - GRID_MS) <= 0.0011 for _, p in scan[:6]), (nm, scan[:6])
    pairs = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(tk, tk[1:])]
    one = [dt for k, dt in pairs if k == 1]
    m = [round(dt / GRID_MS) for dt in one]
    resid = [dt - GRID_MS * q for dt, q in zip(one, m)]
    assert set(m) <= {10, 11, 12, 13, 14}, (nm, Counter(m))
    # 每個 tick 對格點的相位偏移(以圓形平均當 0):八成五以上在 ±0.6 ms 內
    _c = sum(math.cos(2 * math.pi * t / GRID_MS) for t in ts)
    _s = sum(math.sin(2 * math.pi * t / GRID_MS) for t in ts)
    _mu = math.atan2(_s, _c) / (2 * math.pi) * GRID_MS
    off = [((t - _mu + GRID_MS / 2) % GRID_MS) - GRID_MS / 2 for t in ts]
    near = sum(abs(x) <= 0.6 for x in off)
    # 偏移的圓形平均必須是 0(原點取對了)
    assert abs(math.atan2(sum(math.sin(2 * math.pi * x / GRID_MS) for x in off),
                          sum(math.cos(2 * math.pi * x / GRID_MS) for x in off))) < 1e-6, nm
    assert near / len(off) >= 0.85, (nm, near, len(off))
    per_tick = sum(dt for _, dt in pairs) / sum(k for k, _ in pairs)
    # 沒掉中斷時,累加器分頻的長期平均就是 54.925 ms;實測較長 → 有中斷沒算進去
    assert per_tick > TICK_MS + 0.3, (nm, per_tick)
    C_RUNS[nm] = {"ticks": len(tk), "best_period_ms": best_p, "best_resultant": round(best_r, 3),
                  "top6": [[round(r, 3), p] for r, p in scan[:6]], "one_tick_gaps": len(one),
                  "one_tick_gap_periods": dict(sorted(Counter(m).items())),
                  "one_tick_gap_resid_ms": [round(min(resid), 3), round(max(resid), 3)],
                  "ticks_within_0_6ms_of_grid": near, "phase_offset_ms_min_max": [round(min(off), 3), round(max(off), 3)],
                  "mean_ms_per_tick": round(per_tick, 3)}
# µs → 除數的換算(0x3ebe4:mov ebx, 8380;mov ecx, 10000;mul ecx;div ebx),常數從程式碼讀
_c3ebe4 = code(0x3EBE4, 0x3EC17 - 0x3EBE4)
_mul = struct.unpack_from("<I", _c3ebe4, _c3ebe4.index(bytes([0xB9])) + 1)[0]      # mov ecx, imm32
_dvs = struct.unpack_from("<I", _c3ebe4, _c3ebe4.index(bytes([0xBB])) + 1)[0]      # mov ebx, imm32
assert (_mul, _dvs) == (10000, 8380)
_div5 = round(GRID_MS * 1000) * _mul // _dvs
_pit_ms = 1000 * _div5 / 1193182
assert abs(_pit_ms - GRID_MS) < 0.001
C = {"method": "wait_ticks R 記錄(eax 低 16 位 = [0x46c]、t = PIC_FullIndex ms);每個 tick 值取第一次返回的時間;1 .. 20 ms 每 0.001 ms 求相位集中度",
     "runs": C_RUNS, "nominal_tick_ms": round(TICK_MS, 3), "bios_channel_us": BIOS_US,
     "divisor_for_5000us": _div5, "pit_period_ms_for_5000us": round(_pit_ms, 4),
     "static": "0x3ed29 把 int 8 指到 0x3ea8e、通道 0x3c 週期 54925 µs;0x3ec2d 取啟用通道的最小週期當基底,0x3ebe4 / 0x3ebb4 寫 PIT;"
               "0x3ead3 每次中斷各通道累加器加基底週期;0x3ea8e 在上一次 ISR 還沒結束時只送 EOI 就返回",
     "not_determined": "基底 5 ms 是哪一個通道設的(執行期才登錄);掉的中斷是 0x3ea8e 的重入保護丟的,還是中斷關著時 IRQ 疊在一起,紀錄分不出來",
     "conclusion": "BIOS tick 落在 5.000 ms 的格點上(PIT 被改成 200 Hz,BIOS tick 由軟體計時器每累積 54925 µs 鏈一次):"
                   "正常間隔 11 格 = 55 ms,偶爾 10 格;12 .. 14 格與平均大於 54.925 ms 表示有計時器中斷沒算進去。"
                   "八成五以上的 tick 離格點 0.6 ms 以內,少數偏到 2 ms。"}

# ---------------------------------------------------------------------------------------------------------------
# (D) 第 5 項第 4 次:FAIL
F_DIR = RAW / "lc157f"
_cl = (RAW / "lc157f_title_calllog.txt").read_text(encoding="ascii")
_h = _cl.splitlines()[0]
assert _h.startswith("H fd2calllog 1 ") and "icount=1" in _h and f"gate={0x22E5C + DELTA:08x}" in _h, _h
_cnt = {int(m[1], 16) - DELTA: int(m[2]) for m in re.finditer(r"^C ([0-9a-f]{8}) (\d+)$", _cl, re.M)}
assert 0x22E5C not in _cnt and _cnt.get(0x10620, 0) > 0, _cnt
assert len(re.findall(r"^E ", _cl, re.M)) == 0
_u = (F_DIR / "units_after_endturn.out").read_text(encoding="utf-8")
_hp0 = re.search(r"^# 0 x=20 y=14 .* hp=(\d+)/(\d+) ", _u, re.M)
_mp11 = re.search(r"^#11 .* mp=(\d+)/(\d+) .* spells=\[1\]", _u, re.M)
SOL_AFTER = (int(_hp0[1]), int(_hp0[2])) if _hp0 else None
MP11 = int(_mp11[2]) - int(_mp11[1]) if _mp11 else None
assert SOL_AFTER == (200, 999) and MP11 == 6
_mp_others = [int(m[2]) - int(m[1]) for m in re.finditer(r"^#1[2-6] .* mp=(\d+)/(\d+) ", _u, re.M)]
assert _mp_others == [0, 0, 0, 0, 0]
_sol1 = re.search(r"^Sol HP/max \((\d+), (\d+)\)$", (F_DIR / "sol1.out").read_text(encoding="utf-8"), re.M)
SOL_BEFORE = (int(_sol1[1]), int(_sol1[2])) if _sol1 else None
assert SOL_BEFORE == (1, 999)
_n_e = len(re.findall(r"^E ", _cl, re.M))
PRED5 = DRV / "pred157_item5.txt"
_plabels = re.findall(r"^(P\d) ", PRED5.read_text(encoding="utf-8"), re.M)
assert _plabels == [f"P{i}" for i in range(1, 6)], _plabels
Dd = {"result": "FAIL", "instance": "lc157f",
      "calllog": rel(RAW / "lc157f_title_calllog.txt"), "gate_opened": 0x22E5C in _cnt, "e_records": _n_e,
      "sol_hp_before_after": [list(SOL_BEFORE), list(SOL_AFTER)], "mp_spent_11_to_16": [MP11] + _mp_others,
      "predictions_file": rel(PRED5), "predictions_sha256": sha(PRED5), "predictions": {k: "NOT TESTED" for k in _plabels},
      "note": "第 1 次(lc157b)也是 HP 1 → 200;第 4 項成功走到 GAME OVER 的 lc157 是第 3 回合以後。HP 200 從哪裡來沒有找到"
              "(全 EXE 線性反組譯裡沒有把 200 寫進 +0x40 的指令;第 1 章勝負 handler 0x206c5 不碰 HP)。"}

out = {"date": "2026-10-27", "exe_md5": MD5, "inputs_dir": rel(RAW), "fdfield_dir": rel(FIELD), "drivers": rel(DRV),
       "approval": "(A) .. (C) 離線;(D) 使用者 2026-10-27「未確認的部分依建議逐項自動處理」後的第 5 項重跑一次,失敗即停",
       "item2_units_camera": A, "item2_terrain_insn": B, "bios_tick_interval": C, "item5_attempt4": Dd,
       "still_open": {"item5_new_game_return_18": "FAIL 4 次;HP 200 的來源未查到;再跑要重新核准",
                      "item6_copy_protection_patch_author": "BLOCKED:沒有未修改的版本可比"}}
OUT.write_bytes((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("wrote", OUT.name, "| A", {nm: list(next(iter(SCROLL[nm]))) for nm in RUNS}, "| B pred", P_E - P_C,
      "actual", MED["lc157e"] - MED["lc157c"], "| C", {nm: C_RUNS[nm]["one_tick_gap_periods"] for nm in RUNS})
