"""續七十證據:evidence/offmap_event0_roster_heap_20261002.json。
A. 事件 0(0x34531)的呼叫序列(靜態)與 ACT7 / ACT8 解碼 → 預測 #12 / #13 的位移,和 v7(續六十九)、v8(本輪)兩次單位表差異比對。
B. join(1) = 0x112a5:v8 名冊人數 16 → 17,新增一筆 char_id 1(第二個哈諾),與原有哈諾記錄的欄位比較。
C. 地圖外格子讀到的記憶體:地圖陣列結尾之後 = 12 byte 區塊標頭 + FDOTHER_073.bin 自 8660 起的位元組。
D. e1(續六十九驅動逾時)的停點傾印重算;全部在陣列內的格子與 FDFIELD 構成段比對。
E. (0,0) 在 30 張戰場:出場位置與地形類型。
"""
import json
import struct
import sys
from collections import Counter
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import export_acting_resources as ea  # noqa: E402
import parse_field as pf  # noqa: E402

EXE = GAME / "FD2.EXE"
V7 = ROOT / ".wsl_build/ctr/v7/ch25"
V8 = ROOT / ".wsl_build/ctr/v8/ch25"
RAW = ROOT / "extracted/raw"
OUT = out_path("offmap_event0_roster_heap_20261002.json")
W, H = 25, 53
GN = 4 + 4 * W * H

# ---------------- A ----------------
acts = ea.export_resources(EXE)
POSE = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}


def predict(act: list[dict]) -> dict[int, tuple[int, int]]:
    mv: dict[int, list[int]] = {}
    for fr in act:
        if fr.get("special"):
            continue
        for u in fr["units"]:
            dx, dy = POSE[u["pose"]]
            m = mv.setdefault(u["slot"], [0, 0])
            m[0] += dx * fr["beats"]
            m[1] += dy * fr["beats"]
    return {k: tuple(v) for k, v in mv.items()}


pred = {**predict(acts["7"]), **predict(acts["8"])}
assert pred == {12: (0, 2), 13: (0, 1)}, pred


def unit_diff(pre: bytes, post: bytes) -> list[dict]:
    out = []
    for i in range(len(pre) // 80):
        a, b = pre[i * 80:(i + 1) * 80], post[i * 80:(i + 1) * 80]
        d = [k for k in range(80) if a[k] != b[k] and k not in (0x26, 5)]
        if d:
            out.append({"unit": i, "side": b[6], "xy_before": [a[0], a[1]], "xy_after": [b[0], b[1]], "changed": d})
    return out


runs = {}
for tag, pre, post in (("v7", V7 / "s1_pre_units.bin", V7 / "e2_after_units.bin"),
                       ("v8", V8 / "s1_pre_units.bin", V8 / "j1_after_units.bin")):
    a, b = pre.read_bytes(), post.read_bytes()
    diff = unit_diff(a, b)
    for s, (dx, dy) in pred.items():
        r = next(x for x in diff if x["unit"] == s)
        assert [r["xy_after"][0] - r["xy_before"][0], r["xy_after"][1] - r["xy_before"][1]] == [dx, dy], (tag, r)
    runs[tag] = {"unit_count": [len(a) // 80, len(b) // 80], "changed_units_excluding_+5_+0x26": diff}
fd24 = pf.parse_map(str(RAW), 24)
A = {
    "handler_0x34531_calls": ["0x112a5(1) join", "0x10b4e(3) spawn_group", "0x135dd(5,8) pan", "0x11cac(1)", "0x3790a(100)",
                              "0x1366a(7) acting", "0x4e381()", "0x15f84([0x53a79], 0xb, ...) dialog", "[0x51a83]=0",
                              "0x10b4e(7) spawn_group", "0x11cac(1)", "0x3790a(100)", "0x1366a(8) acting", "0x4e381()",
                              "0x15f84([0x53a79], 3, ...) dialog", "0x134e4()"],
    "acting_7": acts["7"], "acting_8": acts["8"],
    "pose_rule": "正常 frame:pose 0:Y+1、1:X-1、2:Y-1、3:X+1,beats = 格數;special frame 不搬格子(doc50 §1.2)",
    "predicted_moves_by_slot": {str(k): list(v) for k, v in pred.items()},
    "map24_fdfield_groups": dict(Counter(u["group"] for u in fd24["units"])),
    "note_spawn_groups": "map 24 的 FDFIELD 沒有 group 3 / 7 的單位,spawn_group(3)、(7) 不新增單位;兩次實測單位數都是 62。",
    "runs": runs,
}

# ---------------- B ----------------
j1 = [s for st in json.loads((V8 / "j1.json").read_text(encoding="utf-8")) for s in st["stops"]]
disp = [s for s in j1 if s["eip"] in ("0x1d890", "0x1d95c", "0x1d9ec")]
ev0 = next(s for s in j1 if s["eip"] == "0x34531")
join = next(s for s in j1 if s["eip"] == "0x112a5")
after = next(s for s in j1 if s["eip"] == "0x34543")
assert [(d["eip"], d["event_id"], d["handler"], d["unit"]) for d in disp] == [("0x1d9ec", 0, "0x34531", 53)]
assert join["join_id"] == 1 and join["count"] == 16 and after["roster"]["count"] == 17
assert after["roster"]["char_ids_+8"] == ev0["roster"]["char_ids_+8"] + [1]
r_end = (V8 / "j1_roster_end.bin").read_bytes()


def rec(r: bytes) -> dict:
    return {"+5..+9": list(r[5:10]), "items_+0a..+19": list(r[0xA:0x1A]), "lv_+21": r[0x21], "ex_+3c": r[0x3C],
            "ap_+37": struct.unpack_from("<h", r, 0x37)[0], "dp_+39": struct.unpack_from("<h", r, 0x39)[0],
            "mv_+3b": r[0x3B], "dx_+3e": struct.unpack_from("<h", r, 0x3E)[0],
            "hp_+40_+42": list(struct.unpack_from("<HH", r, 0x40)), "mp_+44_+46": list(struct.unpack_from("<HH", r, 0x44)),
            "bytes_+0..+4_not_written_by_0x112a5": list(r[0:5])}


hano = [i for i in range(len(r_end) // 80) if r_end[i * 80 + 8] == 1]
assert hano == [4, 16], hano
assert list(r_end[16 * 80:17 * 80]) == after["new_record"]
B = {
    "static": "0x112a5:位址 = [0x53bf7] + [0x53bfb]*0x50,寫 +5 = 0、+6 = 2、+7 = +8 = id …,呼叫 0x1145a,最後 inc [0x53bfb];"
              "本體沒有比對既有 +8,也沒有和容量比較。+0..+4、+0x17、+0x19 不寫(新記錄這幾個 byte 是殘值)。",
    "dispatch": disp,
    "roster_count_at_handler_entry": ev0["roster"]["count"],
    "join_call": {"ret": join["ret"], "join_id": join["join_id"], "count_before": join["count"]},
    "roster_count_after_join": after["roster"]["count"],
    "char_ids_before": ev0["roster"]["char_ids_+8"], "char_ids_after": after["roster"]["char_ids_+8"],
    "hano_records": {"index_4_existing": rec(r_end[4 * 80:5 * 80]), "index_16_appended": rec(r_end[16 * 80:17 * 80])},
    "screenshot": ".wsl_build/ctr/v8/ch25/j1_dlg_a.png",
}

# ---------------- C ----------------
f73 = (RAW / "FDOTHER/FDOTHER_073.bin").read_bytes()
pg = sorted(V7.glob("e2_*_past_grid.bin"), key=lambda p: p.stat().st_size)[-1].read_bytes()
assert pg[12:] == f73[8660 + 12:8660 + len(pg)]
assert pg[:12] != f73[8660:8672]
e2rows = json.loads((V7 / "e2_lookup_rows.json").read_text(encoding="utf-8"))
wr = []
for r in e2rows:
    if r["wrote"]:
        off = 4 + 4 * (r["y"] * W + r["x"]) - GN
        assert off >= 12 and r["cell"] == list(f73[8660 + off:8660 + off + 4])
        wr.append({"x": r["x"], "y": r["y"], "past_grid_offset": off, "fdother73_offset": 8660 + off, "cell": r["cell"]})
C = {
    "grid": "0x23a1b0(執行期),大小 4 + 4*25*53 = 5304",
    "past_grid_bytes_dumped": len(pg),
    "header_12_bytes_u32": [hex(x) for x in struct.unpack("<3I", pg[:12])],
    "rest_equals": "FDOTHER_073.bin[8672 : 8660 + dump 長度],%d/%d byte 相同" % (len(pg) - 12, len(pg) - 12),
    "fdother73_header": {"w": struct.unpack_from("<H", f73, 0)[0], "h": struct.unpack_from("<H", f73, 2)[0], "size": len(f73)},
    "event0_cells": wr,
    "interpretation": "INFERRED:12 byte 標頭的形狀(長度 0x990 + 兩個指標)像 Watcom 堆積的空閒區塊;其後是先前載入、已不再使用的 FDOTHER #73 內容。"
                      "地圖外格子會寫出哪個事件,取決於這塊殘留,不是地圖外行走本身的固定結果。",
}

# ---------------- D ----------------
e1 = json.loads((V7 / "e1_lookup_rows.json").read_text(encoding="utf-8"))
comp = (RAW / "FDFIELD/FDFIELD_072.bin").read_bytes()


def sc(x: int, y: int) -> list[int]:
    o = 4 + 4 * (y * W + x)
    return list(comp[o:o + 4])


allrows = e1 + e2rows
ing = [r for r in allrows if r["in_grid"]]
assert all(sc(r["x"], r["y"])[:3] == r["cell"][:3] for r in ing)
byte3_live = sorted({r["cell"][3] for r in ing})
assert byte3_live == [255]
assert not any(r["pred_write"] for r in e1) and all(r["in_grid"] and r["slot"] == 0 for r in e1)
walk1 = [r for r in e1 if r["ret"] == "0x1317a"]
D = {
    "e1_lookups": len(e1), "e1_rets": dict(Counter(r["ret"] for r in e1)),
    "e1_unit53_walk_first_last": [[walk1[0]["x"], walk1[0]["y"]], [walk1[-1]["x"], walk1[-1]["y"]]],
    "e1_in_grid": sum(r["in_grid"] for r in e1), "e1_nonzero_slot": sum(r["slot"] != 0 for r in e1),
    "e1_predicted_writes": sum(bool(r["pred_write"]) for r in e1),
    "e2_first": [e2rows[0]["x"], e2rows[0]["y"]],
    "in_grid_live_cells_e1_e2": len(ing),
    "bytes_0_2_equal_FDFIELD_072": len(ing),
    "byte3_live": byte3_live[0], "byte3_static": sorted({sc(r["x"], r["y"])[3] for r in ing}),
    "map24_static_cells_with_slot": [[x, y, sc(x, y)[2] & 0x1F] for y in range(H) for x in range(W) if sc(x, y)[2] & 0x1F],
}

# ---------------- E ----------------
E_maps = []
for m in range(30):
    i = pf.parse_map(str(RAW), m)
    ctl = (RAW / f"FDFIELD/FDFIELD_{3 * m + 1:03d}.bin").read_bytes()
    cm = (RAW / f"FDFIELD/FDFIELD_{3 * m:03d}.bin").read_bytes()
    tt = (RAW / f"FDSHAP/FDSHAP_{2 * ctl[0] + 1:03d}.bin").read_bytes()
    tile = struct.unpack_from("<H", cm, 4)[0] & 0x3FF
    zero = [k for k, q in enumerate(i["positions"][:len(i["units"])]) if q[0] == 0 and q[1] == 0]
    E_maps.append({"map": m, "terrain_type_at_0_0": tt[tile * 4 + 1],
                   "units_placed_at_0_0": [{"unit": k, "group": i["units"][k]["group"], "camp": i["units"][k]["camp"]} for k in zero]})
types = Counter(x["terrain_type_at_0_0"] for x in E_maps)
z = [x for x in E_maps if x["units_placed_at_0_0"]]
assert [x["map"] for x in z] == [16] and {u["group"] for u in z[0]["units_placed_at_0_0"]} == {255}
groups = json.loads((ROOT / "docs/data/event_id_groups.json").read_text(encoding="utf-8"))
lit = sorted({s["group"] for k, v in groups.items() if k != "_source" for s in v["spawns"] if isinstance(s["group"], int)})
E = {
    "terrain_type_counts_at_0_0": dict(types),
    "maps_with_units_at_0_0": z,
    "literal_spawn_groups": lit,
    "dynamic_spawn_groups": {k: v["spawns"][0]["group"] for k, v in groups.items()
                             if k != "_source" and any(not isinstance(s["group"], int) for s in v["spawns"])},
    "per_map": E_maps,
    "note": "地形類型 = FDSHAP_{2*selector+1}[tile*4+1](map 24 與實機地形表相同,FDSHAP_049)。成本表 0x61646 每列 20 byte;"
            "類型 5 在全部列是 20(續六十五)。map 16 的 14 個 (0,0) 單位是 group 255,沒有字面 spawn_group(255);"
            "動態 group 是回合數、回合數/2 或 [[0x53ad5]+0x10](事件 31、82)。",
}

ev = {"note": "DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;第 25 章戰場 = map 24,來源存檔 source_ch27.SAV 經 prepare_chapter_save;"
              "v7 = 續六十九的原始紀錄,v8 = 本輪同一設定重做(v8_setup = v7_setup 的複本)。斷點位址為 Ghidra 位址,執行期 +0x19c000。",
      "A_event0_acting_moves": A, "B_event0_roster_append": B, "C_past_grid_memory": C,
      "D_e1_recovered_and_static_cells": D, "E_origin_cell_in_real_maps": E}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", pred, "roster", B["roster_count_at_handler_entry"], "->", B["roster_count_after_join"], "types", dict(types))
