"""把 tr_analyze.py 的結果整理成 docs/knowledge-base/evidence/ai_physical_untested_branches_20261001.json(doc98 續六十四)。"""
import collections
import json
import struct
import sys

from _evpaths import GAME_S, ROOT_S, TOOLS, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(TOOLS))
import disasm_le  # noqa: E402
from _terrain import AP_PCT, DP_PCT  # noqa: E402
from sim_path import Grid  # noqa: E402
import re  # noqa: E402

ROOT = ROOT_S
import tr_analyze  # noqa: E402
from tr_analyze import analyze  # noqa: E402
DST = str(out_path("ai_physical_untested_branches_20261001.json"))
EXE = GAME_S + "/FD2.EXE"

# 原本讀分析腳本寫進 .wsl_build 的 analyze.json;改為直接從傾印重算(經 JSON 來回,與當時寫檔再讀回相同)
a = json.loads(json.dumps({t: analyze(t) for t in ("r1", "r2", "r3")}, ensure_ascii=False))
exe = open(EXE, "rb").read()
meta = disasm_le.parse_le(exe)

runs, totals = {}, collections.Counter()
rival_pairs = collections.Counter()
rival_final = collections.Counter()
gate_obs = collections.Counter()
for tag, rs in a.items():
    runs[tag] = []
    for r in rs:
        if "note" in r:
            runs[tag].append({"actor": r["actor"], "candidate_count": r["candidates"], "pair_count": r["pairs"],
                              "note": "第 3 回合劇情援軍;單位記錄在 21 筆傾印之外,0 組所以不影響重算"})
            continue
        totals["calls"] += 1
        totals["pairs"] += len(r["pairs"])
        totals["pairs_match"] += sum(p["match"] for p in r["pairs"])
        for k, v in r["rival_pairs_differing"].items():
            rival_pairs[k] += v
            rival_final[k] += r["rival_best"][k] != r["predicted_best"]
        for k, v in r["pairs_rival"].items():
            rival_pairs["targets_" + k] += sum(p not in r["pairs_live"] for p in v["pairs"]) + sum(
                p not in v["pairs"] for p in r["pairs_live"])
        gate_obs.update((p["gate_reason"], p["live"][5]) for p in r["pairs"])
        runs[tag].append({
            "actor": r["actor"], "a2": r["a2"], "actor_cell": r["actor_cell"], "mv": r["mv"],
            "move_cost_row": r["cost_row"], "weapon_item": r["weapon"], "weapon_row_0xb_0xc": r["weapon_row_b_c"],
            "item77_row_at_entry": r["item77_row"], "item77_row_after_restore": r["item77_restored"],
            "reach_cells_live": r["reach_live"], "reach_matches_recompute_with_live_cost_rows": r["reach_match"],
            "reach_matches_recompute_with_json_cost_rows": r["reach_json_match"],
            "candidate_cells": r["candidates"], "pairs_live": r["pairs_live"],
            "pairs_enumeration_matches": r["pairs_enumeration_match"],
            "pairs_rival_enumeration": r["pairs_rival"],
            "pairs": r["pairs"], "all_pairs_match": r["all_pairs_match"],
            "global_after_every_comparison_matches": r["step_glob_match"],
            "globals_at_loop_end": r["end_glob"], "predicted_globals": r["predicted_best"],
            "rival_globals": r["rival_best"], "ai_attack_execute_called": r["attack_called"],
        })

# 計數 = 不是 note 的呼叫數
assert totals["calls"] == sum("note" not in r for rs in a.values() for r in rs), totals
W_KEY = "weapon_rows_0_to_0x7f"
rows = [bytes(disasm_le.object_bytes(exe, meta, 0x602AD + i * 0x17, 0x17)) for i in range(0x80)]
# 與 tools/dump_exe_tables.py 另外抽的道具列相同;列數 = 鍵名的範圍
assert rows == [bytes.fromhex(r["raw"]) for r in json.load(open(ROOT + "/docs/data/exe_tables/native_item_effect_rows.json",
                                                                 encoding="utf-8"))][:len(rows)]
assert len(rows) == int(W_KEY.rsplit("_to_", 1)[1], 16) + 1, len(rows)
mods = open(ROOT + "/.wsl_build/ctr/tr/mods.bin", "rb").read()
cost_live = open(ROOT + "/.wsl_build/ctr/tr/costrows_live.bin", "rb").read()
cost_json = tr_analyze.JSON_ROWS  # 當時的舊版(以 blob sha 鎖定,見 tr_analyze.py)
CROW = 20  # 成本表每列 20 byte(0x61646)
assert len(cost_live) == CROW * len(cost_json), (len(cost_live), len(cost_json))
crow = lambda k: cost_live[k * CROW:(k + 1) * CROW]
# note 的主張:當時 JSON 的每一列都比活記憶體早一個 byte(file_base 0x7A659,正確 0x7A65A)
assert all(bytes.fromhex(j["raw"])[1:] == crow(k)[:-1] for k, j in enumerate(cost_json)), "成本列錯位不是一個 byte"
used_rows = sorted({r["cost_row"] for rs in a.values() for r in rs if "note" not in r})  # 攻方實際用到的成本列
same_rows = [k for k, j in enumerate(cost_json) if j["raw"] == crow(k).hex()]  # 錯位也看不出來的列(整列相同值)
assert used_rows and all(cost_json[k]["raw"] != crow(k).hex() for k in used_rows), used_rows
terrain = json.load(open(ROOT + "/docs/data/exe_tables/terrain.json", encoding="utf-8"))
live_grid = open(ROOT + "/.wsl_build/ctr/tr/pre_map.bin", "rb").read()
M_KEY = "shipped_maps_with_move_code_3_to_5"
MC_LO, MC_HI = map(int, M_KEY.removeprefix("shipped_maps_with_move_code_").split("_to_"))
maps = {}
for n in range(33):
    b = open(ROOT + "/extracted/raw/FDFIELD/FDFIELD_%03d.bin" % (3 * n), "rb").read()
    W, H = struct.unpack_from("<HH", b, 0)
    mc = {e["idx"]: e["move_code"] for e in terrain["tilesets"][n]["entries"]}
    # 圖塊 → 移動碼:用 sim_path 的格子讀法(與實機路徑搜尋逐格相同),地形表換成「圖塊 k 的 byte 1 = 移動碼」
    _tt = b"".join(bytes([mc.get(t, 0)]) * 4 for t in range(max(mc) + 1))  # 每列 4 byte 都填移動碼
    _g = Grid(b, bytes(_tt), bytes(range(256)))
    cnt = collections.Counter(_g.enter_cost(i % W, i // W) for i in range(W * H))
    # 兩種讀法(圖塊 = u16 & 0x3ff 直接查表、經 Grid)逐圖相同
    assert cnt == collections.Counter(mc.get(struct.unpack_from("<H", b, 4 + 4 * i)[0] & 0x3FF) for i in range(W * H)), n
    assert None not in cnt and max(cnt) <= MC_HI, (n, cnt)  # 每格的圖塊都在 terrain.json 裡;移動碼最大 5
    codes = {str(k): v for k, v in sorted(cnt.items()) if MC_LO <= k <= MC_HI}
    if codes:
        maps["map%d" % n] = codes
same = all(struct.unpack_from("<H", live_grid, 4 + 4 * i)[0] == struct.unpack_from(
    "<H", open(ROOT + "/extracted/raw/FDFIELD/FDFIELD_003.bin", "rb").read(), 4 + 4 * i)[0] for i in range(27 * 21))

# 判準(移植時補上;原腳本只整理不檢查)
for tag, rs in a.items():
    for r in rs:
        if "note" in r:
            assert r["pairs"] == 0, (tag, r["actor"])
            continue
        assert r["reach_match"] and r["pairs_enumeration_match"] and r["all_pairs_match"] and r["step_glob_match"], (tag, r["actor"])
        assert r["end_glob"] == r["predicted_best"], (tag, r["actor"])
assert totals["pairs"] == totals["pairs_match"] > 0, totals
# 7 條對照規則都至少在一組上與重算不同
assert len(rival_pairs) == 7 and min(rival_pairs.values()) > 0, rival_pairs
assert same, "活記憶體的第 1 章地圖格與 FDFIELD_003 不同"
# 原本寫死 True 的欄位:活記憶體的成本列(0x1f3646)必須等於 LE object 的靜態 bytes(0x61646)
assert bytes(disasm_le.object_bytes(exe, meta, 0x61646, len(cost_live))) == cost_live

# 武器列的欄位與比較值取自鍵名(鍵名是唯一的寫法)
K_B, K_C, K_B2, K_C10 = "count_by_0xb", "count_by_0xc", "items_with_0xb_2", "items_with_0xc_ge_0x10"
OFF_B, OFF_C = (int(re.search(r"0x([0-9a-f]+)", k)[1], 16) for k in (K_B, K_C))
B2 = int(K_B2.rsplit("_", 1)[1])
C10 = int(K_C10.rsplit("_ge_", 1)[1], 16)
assert (K_B2.split("_")[2], K_C10.split("_")[2]) == (f"0x{OFF_B:x}", f"0x{OFF_C:x}"), (K_B2, K_C10)
live_ap = [struct.unpack_from("<i", mods, 4 * i)[0] for i in range(6)]
live_dp = [struct.unpack_from("<i", mods, 0x18 + 4 * i)[0] for i in range(6)]
assert (live_ap, live_dp) == (AP_PCT, DP_PCT), (live_ap, live_dp)  # 與 _terrain(三個戰場的活記憶體)相同
out = {
    "note": ("DOSBox-X 斷點與記憶體傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;第 1 章戰場,3 個敵方回合。"
             "斷點(執行期 +0x19c000):0x14237 入口、0x14368 候選格清單(另傾印地圖格陣列)、0x1449e(0x1debe 回傳 EAX)、"
             "0x144c5(每組比較前)、0x1459f(迴圈結束)、0x1548e(ai_attack_execute 入口,保護被選中的目標)。"
             "S1(攻方 #12,種族 5、MV 1、item 31):地形表 tile 2/3/6 的 byte 1 改成 3/4/5,地圖格 (6,8)/(4,7)/(5,10) 改指這三個 tile;"
             "目標 #1 裝弓 item 44(+0xb 2)、#2/#3 裝 item 31,全部未麻痺、AP 50、DP 60。"
             "S2(攻方 #13,種族 1、MV 1、item 77):第 1、2 回合把 item 77 列 +0xc 從 6 改成 0x13(射程 byte >= 0x10,十字半徑 3),"
             "在該攻方的 0x1459f 改回 6;第 3 回合不改(對照)。#4 卸下全部武器(0x1debe 無武器分支)。"
             "第 1 回合 #13 站在屋頂(地形 1,row 7 成本 20)走不動,第 2 回合移到平地。"),
    "summary": {
        "calls_recomputed": totals["calls"], "pairs": totals["pairs"], "pairs_match": totals["pairs_match"],
        "rival_rules_pairs_differing": dict(rival_pairs),
        "rival_rules_final_choice_differing_calls": dict(rival_final),
        "rival_rules": {
            "terrain_ge3_zero": "地形 3..5 視為 0%(只有 0..2 有修正)",
            "terrain_ge3_as2": "地形 3..5 當成地形 2",
            "terrain_floor": "地形百分比取 floor 而非截斷向零",
            "debe_ignores_b": "0x1debe 不看武器列 +0xb(弓也能反擊)",
            "debe_unarmed_passes": "0x1debe 不要求裝備 kind0 武器",
            "targets_cross_as_manhattan": "射程 byte >= 0x10 當曼哈頓(半徑 = byte - 0x10,含內圈排除與地形展開)",
            "targets_cross_with_inner": "十字分支也套內圈排除(+0xb)",
        },
        "counter_gate_live_eax_by_first_failing_check": {"%s|%s" % k: v for k, v in sorted(gate_obs.items(), key=str)},
    },
    "terrain_modifier_tables_live": {
        "ap_pct_0x51a12": live_ap, "dp_pct_0x51a2a": live_dp,
    },
    M_KEY: maps,
    "live_ch1_grid_equals_FDFIELD_003_map1": same,
    W_KEY: {
        K_B: {str(k): v for k, v in sorted(collections.Counter(r[OFF_B] for r in rows).items())},
        K_C: {str(k): v for k, v in sorted(collections.Counter(r[OFF_C] for r in rows).items())},
        K_B2: [i for i, r in enumerate(rows) if r[OFF_B] == B2],
        K_C10: [i for i, r in enumerate(rows) if r[OFF_C] >= C10],
    },
    "movement_cost_rows_live_vs_json": {
        "live_0x1f3646_equals_static_object_bytes_0x61646": True,
        **{kv: v for k in used_rows for kv, v in ((f"row{k}_live", crow(k).hex()), (f"row{k}_json_raw", cost_json[k]["raw"]))},
        **{f"row{k}_live": crow(k).hex() for k in same_rows},
        "note": ("docs/data/exe_tables/native_movement_cost_rows.json 每列錯一個位元組(產生器 file_base 0x7A659,"
                 "正確是 0x7A65A);本輪重算一律用活記憶體的成本列。另開任務修正,本輪不改。"),
    },
    "runs": runs,
}
json.dump(out, open(DST, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
open(DST, "a", encoding="utf-8", newline="\n").write("\n")
print("wrote", DST)
print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
print(out["shipped_maps_with_move_code_3_to_5"], out["live_ch1_grid_equals_FDFIELD_003_map1"])
