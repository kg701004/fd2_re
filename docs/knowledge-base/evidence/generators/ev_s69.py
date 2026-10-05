"""續六十九證據:evidence/offmap_unit_event_camera_trace_20261001.json。
A. 0x12d7b / 0x12cea 是游標(鏡頭)對焦:每次 0x12d7b(unit) 返回時游標 = 單位座標(e2、h1)。
B. 落到地圖外的單位觸發事件 0:逐步移動的收尾 0x1317a 以游標座標呼叫 field_event_lookup(x, y, 0),
   地圖外的格子讀到地圖陣列之後的記憶體;e2 的每一次查詢以格子 + 地形表 + 事件表重算,與 0x13a95 的寫入逐筆比對。
C. 0x12cea 的目標在地圖外時不終止(h1、h1_loop)。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
S = GEN_DIR
D = ROOT / ".wsl_build/ctr/v7/ch25"
OUT = out_path("offmap_unit_event_camera_trace_20261001.json")

subprocess.run([sys.executable, "-X", "utf8", str(S / "an_ev.py"), "e2"], check=True, cwd=S, capture_output=True)
rows = json.loads((D / "e2_lookup_rows.json").read_text(encoding="utf-8"))
e2 = [s for st in json.loads((D / "e2.json").read_text(encoding="utf-8")) for s in st["stops"]]
h1 = json.loads((D / "h1.json").read_text(encoding="utf-8"))
loop = json.loads((D / "h1_loop.json").read_text(encoding="utf-8"))
pre = (D / "s1_pre_units.bin").read_bytes()
post = (D / "e2_after_units.bin").read_bytes()

# ---------------- A. 游標對焦 ----------------
focus = []
for stops in (e2, h1["stops"]):
    last_cea = None
    for s in stops:
        if s["eip"] == "0x12cea":
            last_cea = s
        elif s["eip"] == "0x12dab" and last_cea is not None:
            u = s["unit"]
            uxy = s.get("unit_xy") or None
            focus.append({"unit": u, "target_xy": last_cea["xy"], "cursor_before": last_cea["cursor"],
                          "cursor_after": s["cursor"], "scroll_before": last_cea["scroll"],
                          "scroll_after": s["scroll"], "a83": last_cea["a83"], "caller_ret": s["ret"],
                          **({"unit_xy": uxy} if uxy else {})})
            last_cea = None
for f in focus:
    assert f["cursor_after"] == f["target_xy"], f
    if "unit_xy" in f:
        assert f["unit_xy"] == f["target_xy"], f
# h1 的單位座標在 0x14121 入口讀到
h1_uxy = {s["unit"]: s["unit_xy"] for s in h1["stops"] if s["eip"] == "0x14121"}
for f in focus:
    if f["unit"] in h1_uxy and "unit_xy" not in f:
        f["unit_xy"] = h1_uxy[f["unit"]]
        assert f["unit_xy"] == f["target_xy"], f
A = {"note": "0x12cea(x, y) 入口讀游標 [0x53ab1]/[0x53ab5]、捲動 [0x53aa9]/[0x53aad]、[0x51a83];0x12d7b 的 ret(0x12dab)讀游標。"
             "每一筆 cursor_after == target_xy == 單位座標。",
     "calls": focus}

# ---------------- B. 地圖外事件 ----------------
off = [r for r in rows if not r["in_grid"]]
writes = [r for r in rows if r["wrote"]]
mism = [r for r in rows if r["pred_write"] != r["wrote"]]
assert not mism and all(r["pred_write"] is not None for r in rows)
assert all(not r["in_grid"] for r in writes) and {r["event_id"] for r in writes} == {0}
disp = [s for s in e2 if s["eip"] in ("0x1d95c", "0x1d9ec", "0x1d890")]
assert [(d["eip"], d["event_id"], d["handler"], d["unit"]) for d in disp] == [("0x1d9ec", 0, "0x34531", 53)]
evtbl = next(s["event_tbl"] for s in e2 if "event_tbl" in s)
diff = []
for i in range(len(pre) // 80):
    a, b = pre[i * 80:(i + 1) * 80], post[i * 80:(i + 1) * 80]
    d = [k for k in range(80) if a[k] != b[k] and k != 0x26]
    if d:
        diff.append({"unit": i, "side": b[6], "xy_before": [a[0], a[1]], "xy_after": [b[0], b[1]],
                     "changed_offsets": d})
B = {
    "map": {"W": 25, "H": 53, "grid_bytes": 4 + 4 * 25 * 53},
    "rule": "0x1317a(逐步移動共用收尾 0x1314f)以游標 [0x53ab1]/[0x53ab5] 呼叫 field_event_lookup(x, y, 0);"
            "格子位址 grid + 4 + 4*(y*W + x) 不檢查邊界。寫入條件:地形表 [tile*4] & 0x60 == 0、slot = byte2 & 0x1f != 0、"
            "事件表 [0x53a55] + 0x33 + (slot-1)*2 的 (id, sel) 中 id != 0xff 且 sel == 參數。",
    "event_table_slots_1_32": [[evtbl[2 * i], evtbl[2 * i + 1]] for i in range(32)],
    "lookups_logged": len(rows), "off_grid": len(off), "in_grid_x_ge_W": sum(1 for r in rows if r["in_grid"] and r["x"] >= 25),
    "first_off_grid": [off[0]["x"], off[0]["y"]],
    "writes": [{k: r[k] for k in ("x", "y", "sel", "cell", "tile", "slot", "tt_b0", "event_id")} for r in writes],
    "prediction_mismatches": 0,
    "dispatch": disp,
    "units_changed_excluding_0x26": diff,
    "unit_count_before_after": [len(pre) // 80, len(post) // 80],
    "terrain_table_dump_sha256": hashlib.sha256((D / "e2_tt4k.bin").read_bytes()).hexdigest(),
    "screenshot": ".wsl_build/ctr/v7/ch25/e2_now.png",
    "note": "e1(同一個敵方回合的前半段)因驅動腳本逾時被終止,停點紀錄沒寫出;e2 從同一次走路的 (39,25) 接續記錄到落地。",
}

# ---------------- C. 不終止 ----------------
he = h1["hang_entry"]
assert he and he["xy"] == [178, 49]
assert all(s["cursor"] == [24, 20] and s["scroll"] == h1["samples"][0]["scroll"] for s in h1["samples"])
assert [x["eip"] for x in loop] == ["0x12d3b"] * 5 and all(x["cursor"] == [24, 20] and x["esi_target_x"] == 178 for x in loop)
C = {"entry": {k: he[k] for k in ("ret", "xy", "cursor", "scroll", "a83")},
     "samples_every_6s_after_20s": h1["samples"],
     "bp_0x12d3b_0x12d42_0x12dab": loop,
     "note": "x 迴圈每圈都停在 0x12d3b(ESI = 178),游標 x 停在 W−1 = 24,0x12d42(y 迴圈)與 0x12dab(返回)沒有停點。"
             "0x11bfa 在游標 x == W−1 時不遞增,所以目標 x >= W 時迴圈不結束。"}

ev = {"note": "DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;第 25 章戰場 = map 24,來源存檔 source_ch27.SAV 經 "
              "prepare_chapter_save;與續六十八同一個設定(v5_setup 的複本 v7_setup)。斷點位址為 Ghidra 位址,執行期 +0x19c000。",
      "A_camera_focus": A, "B_offmap_field_event": B, "C_offmap_focus_never_returns": C}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("A", len(focus), "B lookups", len(rows), "off", len(off), "writes", len(writes), "diff", diff, "C ok")
