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
sys.path.insert(0, str(GEN_DIR))
from _fields import check_offset_keys  # noqa: E402
from sim_path import Grid  # noqa: E402

EXE = GAME / "FD2.EXE"
V7 = ROOT / ".wsl_build/ctr/v7/ch25"
V8 = ROOT / ".wsl_build/ctr/v8/ch25"
RAW = ROOT / "extracted/raw"
OUT = out_path("offmap_event0_roster_heap_20261002.json")
W, H = 25, 53
GN = 4 + 4 * W * H
REC = 80  # 單位 / 名冊紀錄長度(0x50)
SIDE = 6  # 紀錄 +6 = 陣營(0x112a5 對新隊員寫 2,見 B)

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


DIFF_KEY = "changed_units_excluding_+5_+0x26"
NOISY = {int(x, 0) for x in DIFF_KEY.split("excluding_")[1].replace("+", "").split("_")}
noisy_seen: set[int] = set()


def unit_diff(pre: bytes, post: bytes) -> list[dict]:
    assert len(pre) == len(post) and len(pre) % REC == 0, (len(pre), len(post))
    recs = [(pre[i:i + REC], post[i:i + REC]) for i in range(0, len(pre), REC)]
    noisy_seen.update(k for a, b in recs for k in NOISY if a[k] != b[k])
    out = []
    for i, (a, b) in enumerate(recs):
        d = [k for k in range(REC) if a[k] != b[k] and k not in NOISY]
        assert set(d) <= {0, 1}, (i, d)  # 排除鍵名列的兩個欄位後,只剩座標 +0 / +1 會變
        if d:
            out.append({"unit": i, "side": b[SIDE], "xy_before": [a[0], a[1]], "xy_after": [b[0], b[1]], "changed": d})
    return out


runs = {}
for tag, pre, post in (("v7", V7 / "s1_pre_units.bin", V7 / "e2_after_units.bin"),
                       ("v8", V8 / "s1_pre_units.bin", V8 / "j1_after_units.bin")):
    a, b = pre.read_bytes(), post.read_bytes()
    diff = unit_diff(a, b)
    for s, (dx, dy) in pred.items():
        r = next(x for x in diff if x["unit"] == s)
        assert [r["xy_after"][0] - r["xy_before"][0], r["xy_after"][1] - r["xy_before"][1]] == [dx, dy], (tag, r)
    # ACT7 / ACT8 搬的是隊員(陣營 2)
    assert all(next(x for x in diff if x["unit"] == s)["side"] == 2 for s in pred), (tag, diff)
    runs[tag] = {"unit_count": [len(a) // REC, len(b) // REC], DIFF_KEY: diff}
assert noisy_seen == NOISY, noisy_seen  # 排除的兩個欄位在這兩次實測裡都真的變過(+0x26 計時、+5 旗標)
fd24 = pf.parse_map(str(RAW), 24)
# map 24 的構成段 = 這個戰場(W × H 相同);開場單位 = 出場人數 + group 0 的單位(spawn_group 3 / 7 沒有單位)
assert (fd24["w"], fd24["h"]) == (W, H), (fd24["w"], fd24["h"])
assert all(r["unit_count"] == [fd24["own_deploy"] + sum(u["group"] == 0 for u in fd24["units"])] * 2 for r in runs.values()), runs
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


hano = [i for i in range(len(r_end) // REC) if r_end[i * REC + 8] == 1]
assert hano == [4, 16], hano
h_old, h_new = (r_end[i * REC:(i + 1) * REC] for i in hano)
assert list(h_new) == after["new_record"]
# 0x112a5:+5 = 0、+6 = 2、+7 = +8 = id
assert list(h_new[5:9]) == [0, 2, 1, 1] and h_new[SIDE] == 2, list(h_new[:10])
B = {
    "static": "0x112a5:位址 = [0x53bf7] + [0x53bfb]*0x50,寫 +5 = 0、+6 = 2、+7 = +8 = id …,呼叫 0x1145a,最後 inc [0x53bfb];"
              "本體沒有比對既有 +8,也沒有和容量比較。+0..+4、+0x17、+0x19 不寫(新記錄這幾個 byte 是殘值)。",
    "dispatch": disp,
    "roster_count_at_handler_entry": ev0["roster"]["count"],
    "join_call": {"ret": join["ret"], "join_id": join["join_id"], "count_before": join["count"]},
    "roster_count_after_join": after["roster"]["count"],
    "char_ids_before": ev0["roster"]["char_ids_+8"], "char_ids_after": after["roster"]["char_ids_+8"],
    "hano_records": {"index_4_existing": rec(h_old), "index_16_appended": rec(h_new)},
    "screenshot": ".wsl_build/ctr/v8/ch25/j1_dlg_a.png",
}

# 鍵名標的位移(+xx、+xx..+yy、+xx_+yy)與讀取的位移分開寫,逐欄核對
for k, r in zip(("index_4_existing", "index_16_appended"), (h_old, h_new)):
    check_offset_keys(B["hano_records"][k], r, {"ap": "<h", "dp": "<h", "dx": "<h", "hp": "<H", "mp": "<H"})
f73 = (RAW / "FDOTHER/FDOTHER_073.bin").read_bytes()
pg = sorted(V7.glob("e2_*_past_grid.bin"), key=lambda p: p.stat().st_size)[-1].read_bytes()
F73 = 8660  # 地圖陣列之後的記憶體對應 FDOTHER_073 的起點
HDR = max(i for i in range(len(pg)) if pg[i] != f73[F73 + i]) + 1
assert HDR == 3 * 4 and pg[HDR:] == f73[F73 + HDR:F73 + len(pg)], HDR  # 三個 u32 的標頭
n_eq = sum(x == y for x, y in zip(pg[HDR:], f73[F73 + HDR:]))
f73_w, f73_h = struct.unpack_from("<HH", f73, 0)
assert 0 < f73_w <= 320 and 0 < f73_h <= 200, (f73_w, f73_h)  # mode 13h 畫面內的圖
e2rows = json.loads((V7 / "e2_lookup_rows.json").read_text(encoding="utf-8"))
wr = []
for r in e2rows:
    if r["wrote"]:
        off = 4 + 4 * (r["y"] * W + r["x"]) - GN
        assert off >= HDR and r["cell"] == list(f73[F73 + off:F73 + off + 4])
        wr.append({"x": r["x"], "y": r["y"], "past_grid_offset": off, "fdother73_offset": F73 + off, "cell": r["cell"]})
C = {
    "grid": "0x23a1b0(執行期),大小 4 + 4*25*53 = 5304",
    "past_grid_bytes_dumped": len(pg),
    "header_12_bytes_u32": [hex(x) for x in struct.unpack("<3I", pg[:HDR])],
    "rest_equals": "FDOTHER_073.bin[%d : %d + dump 長度],%d/%d byte 相同" % (F73 + HDR, F73, n_eq, len(pg) - HDR),
    "fdother73_header": {"w": f73_w, "h": f73_h, "size": len(f73)},
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
w1_first, *_, w1_last = walk1
e2_first, *_ = e2rows
D = {
    "e1_lookups": len(e1), "e1_rets": dict(Counter(r["ret"] for r in e1)),
    "e1_unit53_walk_first_last": [[w1_first["x"], w1_first["y"]], [w1_last["x"], w1_last["y"]]],
    "e1_in_grid": sum(r["in_grid"] for r in e1), "e1_nonzero_slot": sum(bool(r["slot"]) for r in e1),
    "e1_predicted_writes": sum(bool(r["pred_write"]) for r in e1),
    "e2_first": [e2_first["x"], e2_first["y"]],
    "in_grid_live_cells_e1_e2": len(ing),
    "bytes_0_2_equal_FDFIELD_072": len(ing),
    "byte3_live": byte3_live[0], "byte3_static": sorted({sc(r["x"], r["y"])[3] for r in ing}),
    "map24_static_cells_with_slot": [[x, y, sc(x, y)[2] & 0x1F] for y in range(H) for x in range(W) if sc(x, y)[2] & 0x1F],
}
# 構成段每格第二個 word 的低 5 bit = 寶箱 slot(parse_field):有 slot 的格子正好用到控制段列出的每一個寶箱
assert sorted({s for *_, s in D["map24_static_cells_with_slot"]}) == sorted(c["slot"] for c in fd24["chests"]), fd24["chests"]

# ---------------- E ----------------
E_KEY = "terrain_type_at_0_0"
OX, OY = map(int, E_KEY.split("_at_")[1].split("_"))  # 問的格子 = 鍵名的座標
E_maps = []
_ch = json.loads((ROOT / "docs/data/per_chapter_handler_tables.json").read_text(encoding="utf-8"))
N_MAPS = len(_ch["pre_town_handlers_0x51de9"])
assert N_MAPS == len(_ch["post_town_handlers_0x51d71"]), N_MAPS
for m in range(N_MAPS):
    i = pf.parse_map(str(RAW), m)
    ctl = (RAW / f"FDFIELD/FDFIELD_{3 * m + 1:03d}.bin").read_bytes()
    cm = (RAW / f"FDFIELD/FDFIELD_{3 * m:03d}.bin").read_bytes()
    lib = 2 * ctl[0]  # FDSHAP 偶數號 = 24×24 圖塊庫,下一號(奇數)= 它的地形控制表(續一百三十九)
    tt = (RAW / f"FDSHAP/FDSHAP_{lib + 1:03d}.bin").read_bytes()
    assert struct.unpack_from("<HH", (RAW / f"FDSHAP/FDSHAP_{lib:03d}.bin").read_bytes(), 0) == (24, 24) \
        and struct.unpack_from("<HH", tt, 0) != (24, 24), (m, lib)
    zero = [k for k, q in enumerate(i["positions"][:len(i["units"])]) if (q[0], q[1]) == (OX, OY)]
    E_maps.append({"map": m, E_KEY: Grid(cm, tt, bytes(range(256))).enter_cost(OX, OY),
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
