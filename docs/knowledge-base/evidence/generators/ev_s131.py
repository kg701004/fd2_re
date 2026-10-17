"""續一百三十一證據:evidence/move_range_remap_buffer_20261017.json。

移動範圍的明暗是不是 draw_terrain_layer 的換色段(0x12106 起:[0x51a93] == -1 時依 [0x53c1f] 取三角表 0x51a97 的階,
地圖格 byte3 != 0xff 的格用 blit_tile24_rle_remap 畫)。第 1 章戰場,索爾 MV 改成 3 後選取(進入移動模式),
三次在 draw_terrain_layer 入口(0x11eee)停住 —— 這時地圖緩衝裡是上一幀畫完的畫面,[0x53c1f] 是上一幀用的值 ——
傾印全域、地圖格、地圖緩衝、換色表與單位表(DOSBox-X 除錯器;斷點只用來停住,不量時間)。
全部從 .wsl_build/lc131a_moverange/{D,E,F}/ 重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
from itertools import combinations
from pathlib import Path

from _evpaths import ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)

RAW = ROOT / ".wsl_build" / "lc131a_moverange"
TAGS = ("D", "E", "F")
OUT = out_path("move_range_remap_buffer_20261017.json")
DELTA = 0x19C000                 # 原生 linear + DELTA = 執行期位址
DTL = 0x11EEE                    # draw_terrain_layer 入口
ORIGIN, STRIDE, CELL = 0x8088, 456, 24   # redraw 傳給 draw_terrain_layer 的 dst = 緩衝 + 0x8088、stride 456、每格 24 px
FILES = ("g.json", "map.bin", "buf.bin", "remap_res.bin", "tri.bin", "units.bin")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(tag: str) -> dict:
    d = RAW / tag
    g = json.loads((d / "g.json").read_text(encoding="utf-8"))
    for f in FILES[1:]:
        g["raw_" + f.split(".")[0]] = (d / f).read_bytes()
    return g


S = {t: load(t) for t in TAGS}

# ---- 每次停住的狀態 ----
for t, g in S.items():
    assert g["regs"]["EIP"] == DTL + DELTA, (t, hex(g["regs"]["EIP"]))
    assert g["regs"]["EAX"] == g["buf"] + ORIGIN, (t, "dst 參數不是緩衝 + 0x8088")
    assert g["sel_51a93"] == -1, t
    tail = g["bplist_tail"]
    assert tail[-3:-1] == ["Breakpoint list:", "-" * 73], (t, tail)    # 傾印時斷點清單是空的
    assert len(g["raw_buf"]) == 0x25680 and len(g["raw_tri"]) == 20, t
    assert struct.unpack_from("<HH", g["raw_map"], 0) == (g["map_w"], g["map_h"]) == (27, 21), t
D, E, F = (S[t] for t in TAGS)
assert len({g["raw_buf"] for g in S.values()}) == 3, "三份緩衝有相同的(不是三次各自的傾印)"
assert all(g["raw_map"] == D["raw_map"] for g in S.values()), "停住之間地圖格變了"
assert all((g["scroll_x"], g["scroll_y"], g["view_w"], g["view_h"]) == (9, 13, 13, 8) for g in S.values())
assert all(g["raw_tri"] == D["raw_tri"] for g in S.values()) and list(D["raw_tri"]) == list(range(11)) + list(range(9, 0, -1))
assert all(g["raw_remap_res"] == D["raw_remap_res"] for g in S.values())
W, H = 27, 21

# ---- 單位:索爾(#0)MV 3、在 (20, 14) ----
units: set[tuple[int, int]] = set()
for g in S.values():
    ub = g["raw_units"]
    for i in range(len(ub) // 80):
        u = ub[i * 80:(i + 1) * 80]
        if not (u[5] & 1):
            units.add((u[0], u[1]))
u0 = D["raw_units"][:80]
assert (u0[0], u0[1], u0[0x3B], u0[5]) == (20, 14, 3, 0), (u0[0], u0[1], u0[0x3B], u0[5])
cursor = {(g["cursor_x"], g["cursor_y"]) for g in S.values()}
assert cursor == {(20, 14)}
occupied = units | cursor
near_v = {(x, y + d) for x, y in occupied for d in (-1, 1)} - occupied          # 單位圖比一格高,蓋到上下格
near_8 = {(x + dx, y + dy) for x, y in occupied for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - occupied

# ---- 地圖格 byte3:預測 = 以 (20, 14) 為中心、MV 3 的菱形,值 3 − 曼哈頓距離(這一帶每格成本 1)----
marks = {(x, y): D["raw_map"][4 + (y * W + x) * 4 + 3] for y in range(H) for x in range(W)
         if D["raw_map"][4 + (y * W + x) * 4 + 3] != 0xFF}
diamond = {(x, y): 3 - abs(x - 20) - abs(y - 14) for y in range(H) for x in range(W) if abs(x - 20) + abs(y - 14) <= 3}
# 量之前的預測只寫了菱形,沒有扣掉同陣營單位站的格;實測那兩格(#2、#3)是 0xff,
# 與 map_block_cells_of_side「同陣營單位所在格設 0xff」相同。判準改成扣掉其他存活的我方(陣營 2)單位所在格。
allies = set()
for i in range(1, len(D["raw_units"]) // 80):
    u = D["raw_units"][i * 80:(i + 1) * 80]
    if not (u[5] & 1) and u[6] == 2:
        allies.add((u[0], u[1]))
blocked = allies & set(diamond)
assert blocked == {(22, 13), (23, 14)}, blocked          # 扣除不是空集合
assert marks == {k: v for k, v in diamond.items() if k not in allies}, sorted(set(marks.items()) ^ set(diamond.items()))

# ---- 換色表 ----
res = D["raw_remap_res"]
tables = []
for lv in range(11):
    off = struct.unpack_from("<I", res, 6 + lv * 4)[0]
    assert off == 0x66 + lv * 0x100, (lv, hex(off))
    tables.append(res[off:off + 256])
assert len(set(tables)) == 11


def block(g: dict, vx: int, vy: int) -> bytes:
    b = bytearray()
    for r in range(CELL):
        o = ORIGIN + (vy * CELL + r) * STRIDE + vx * CELL
        b += g["raw_buf"][o:o + CELL]
    return bytes(b)


def explained(pairs: set[tuple[int, int]], la: int, lb: int) -> bool:
    ra, rb = tables[la], tables[lb]
    return all(any(ra[c] == p and rb[c] == q for c in range(256)) for p, q in pairs)


def compare(A: dict, B: dict, shift: int = 0, lv_override: int | None = None) -> dict:
    """比較兩幀;shift 把格座標錯開(對照),lv_override 把 B 的階換掉(對照)。"""
    la, lb = A["raw_tri"][A["phase"]], B["raw_tri"][B["phase"]]
    if lv_override is not None:
        lb = lv_override
    rows = []
    for vy in range(8):
        for vx in range(13):
            x, y = 9 + vx + shift, 13 + vy
            if not (0 <= x < W and 0 <= y < H):
                continue
            pa, pb = block(A, vx, vy), block(B, vx, vy)
            diff = {(p, q) for p, q in zip(pa, pb) if p != q}
            rows.append({"xy": (x, y), "marked": (x, y) in marks, "occ": (x, y) in occupied, "near_v": (x, y) in near_v,
                         "near_8": (x, y) in near_8, "ndiff": sum(p != q for p, q in zip(pa, pb)),
                         "expl": explained(diff, la, lb)})
    marked = [r for r in rows if r["marked"]]
    clean = [r for r in marked if not r["occ"] and not r["near_v"]]
    plain = [r for r in rows if not r["marked"] and not r["occ"] and not r["near_v"]]
    return {"levels": [la, lb], "visible": len(rows), "marked": len(marked),
            "marked_changed": sum(r["ndiff"] > 0 for r in marked), "marked_clean": len(clean),
            "clean_unexplained": [list(r["xy"]) for r in clean if not r["expl"]],
            "plain": len(plain), "plain_changed": [[*r["xy"], r["ndiff"]] for r in plain if r["ndiff"]],
            "plain_changed_not_near8": [list(r["xy"]) for r in plain if r["ndiff"] and not r["near_8"]],
            "unit_cells_changed": [[*r["xy"], r["ndiff"]] for r in rows if r["occ"] and r["ndiff"]]}


def judge(c: dict) -> dict[str, bool]:
    j = {}
    j["兩幀的階不同"] = c["levels"][0] != c["levels"][1]
    j["可見的標記格全部變動"] = c["marked"] > 0 and c["marked_changed"] == c["marked"]
    j["不貼單位的標記格都能用換色表解釋"] = c["marked_clean"] > 0 and not c["clean_unexplained"]
    j["沒標記、不貼單位的格:變動只出現在單位換幀時,且都與單位相鄰(8 方向)"] = (
        c["plain"] > 0 and not c["plain_changed_not_near8"]
        and (not c["plain_changed"] or any(xy[:2] != [20, 14] for xy in c["unit_cells_changed"])))
    return j


pairs = {}
for a, b in combinations(TAGS, 2):
    c = compare(S[a], S[b])
    j = judge(c)
    assert all(j.values()), (a, b, c, j)
    # 對照 1:格座標錯開一格 —— 沒標記的格會整格變動
    ctl_shift = {s: judge(compare(S[a], S[b], shift=s)) for s in (-1, 1)}
    assert all(not all(v.values()) for v in ctl_shift.values()), (a, b, ctl_shift)
    # 對照 2:B 換成其他每一階 —— 換色表解釋不了
    wrong = {lv: len(compare(S[a], S[b], lv_override=lv)["clean_unexplained"]) for lv in range(11) if lv != c["levels"][1]}
    assert all(n > 0 for n in wrong.values()), (a, b, wrong)
    pairs[f"{a}-{b}"] = {"compare": c, "checks": j, "control_shift": ctl_shift, "control_wrong_level_unexplained": wrong}

# 實測值(量之前的預測:標記格全變、沒標記的格不變;沒有預測的是 (10, 20) 那一格,見 status)
assert [pairs[k]["compare"]["levels"] for k in pairs] == [[8, 4], [8, 0], [4, 0]]
assert pairs["D-E"]["compare"]["plain_changed"] == []
assert pairs["D-F"]["compare"]["plain_changed"] == pairs["E-F"]["compare"]["plain_changed"] == [[10, 20, 53]]
assert all(pairs[k]["compare"]["marked"] == 17 and pairs[k]["compare"]["plain"] == 70 for k in pairs)

ev = {
    "_meta": {"topic": "續一百三十一:移動範圍的明暗 = draw_terrain_layer 換色段(byte3 != 0xff 的格以三角表的階換色)",
              "raw": {f"{t}/{f}": sha(RAW / t / f) for t in TAGS for f in FILES},
              "generator": "evidence/generators/ev_s131.py(變異測試 mut_s131.py)",
              "harness": "DOSBox-X(tools/dosbox_harness.sh 預設 cycles 5000);原版 FD2.EXE;第 1 章戰場,"
                         "索爾 MV(+0x3b)由 30 改成 3 後選取;只改模擬器記憶體"},
    "snaps": {t: {k: S[t][k] for k in ("phase", "last_adv", "scroll_x", "scroll_y", "cursor_x", "cursor_y", "sel_51a93")}
              | {"level": S[t]["raw_tri"][S[t]["phase"]]} for t in TAGS},
    "marks": {f"{x},{y}": v for (x, y), v in sorted(marks.items())},
    "allies_in_diamond": sorted(map(list, blocked)),
    "pairs": pairs,
    "status": {
        "marks": "LOG CONFIRMED:選取索爾(MV 3)後,地圖格 byte3 != 0xff 的是以 (20, 14) 為中心的菱形(值 3 − 距離)扣掉我方 #2、#3 站的"
                 "兩格;預測沒有扣這兩格,實測後才改判準",
        "remap": "LOG CONFIRMED:三對幀(階 8/4、8/0、4/0)中,可見的 17 個標記格全部變動;不貼單位的 14 格,每個變動像素都"
                 "能用兩幀各自的換色表解釋,換成其他任何一階就解釋不了",
        "plain": "LOG CONFIRMED:70 個沒標記、不貼單位的格在 D-E(單位沒換幀)完全相同;D-F、E-F 只有 (10, 20) 左緣 53 個像素"
                 "不同,這兩對單位都換了幀,(10, 20) 與 (9, 19)、(11, 19) 的單位斜向相鄰;單位圖蓋過去是推論(INFERRED)",
        "scope": "只量了第 1 章、一個單位、MV 3;其他地圖或敵方單位的移動範圍沒有量"},
}


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
