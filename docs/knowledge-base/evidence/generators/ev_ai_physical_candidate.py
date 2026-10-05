"""把 pa_analyze.py 的結果整理成 docs/knowledge-base/evidence/ai_physical_candidate_20260930.json。"""
import json

from _evpaths import out_path, require_inputs  # noqa: E402
require_inputs(__file__)
from pa_analyze import analyze  # noqa: E402
DST = str(out_path("ai_physical_candidate_20260930.json"))

# 原本讀分析腳本寫進 .wsl_build 的 analyze.json;改為直接從傾印重算(經 JSON 來回,與當時寫檔再讀回相同)
a = json.loads(json.dumps({t: analyze(t) for t in ("r1", "r2")}, ensure_ascii=False))
runs = {}
for tag, rs in a.items():
    runs[tag] = []
    for r in rs:
        runs[tag].append({
            "actor": r["actor"], "a2": r["a2"], "return_address": r["ret"],
            "weapon_item": r["weapon"], "weapon_row_0xb_0xc": r["weapon_row_b_c"],
            "candidate_cells": r["candidates"],
            "pairs_enumeration_matches_row_major_x_unit_index": r["pairs_enumeration_match"],
            "pairs": [{k: p[k] for k in ("cell", "target", "live", "recomputed", "counter", "target_ap_live", "match",
                                         "rival_doc_skip_le2", "rival_terrain_like_attack", "rival_debe_actor",
                                         "rival_floor_x15")} for p in r["pairs"]],
            "all_pairs_match": r["all_pairs_match"],
            "global_after_every_comparison_matches": r["step_glob_match"],
            "globals_at_entry_c43_c47_c4b_c4f": r["start_glob"],
            "globals_at_loop_end": r["end_glob"], "predicted_globals": r["predicted_best"],
            "rival_globals": r["rival_best"], "ai_attack_execute_called": r["attack_called"],
        })

# 判準(移植時補上;原腳本只整理不檢查):每次呼叫的列舉、逐組分數、每次比較後的全域、迴圈結束值都要與重算相符
for tag, rs in a.items():
    for r in rs:
        assert r["pairs_enumeration_match"] and r["all_pairs_match"] and r["step_glob_match"], (tag, r["actor"])
        assert r["end_glob"] == (r["predicted_best"] if r["predicted_best"] is not None else r["start_glob"]), (tag, r["actor"])
# 對照規則至少要在一組上與重算不同,否則「相符」分不出規則
for k in ("rival_doc_skip_le2", "rival_terrain_like_attack", "rival_debe_actor", "rival_floor_x15"):
    assert any(p[k] != p["recomputed"] for rs in a.values() for r in rs for p in r["pairs"]), k

out = {
    "note": ("DOSBox-X 斷點與記憶體傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。0x14237 內 4 個斷點(執行期 +0x19c000):"
             "入口 0x14237(參數、單位表)、0x14368(0x14b16 候選格清單)、0x144c5(每組 (格, 目標) 比較前:ESI 分數、EDI 優先級、"
             "EBP 目標 AP'、[ESP+0x3c]/[0x38] 攻方 AP'/DP'、[ESP+0x44]/[0x48] 格、[ESP+0x50] 目標,另讀 [0x53c43..0x53c4f])、"
             "0x1459f(迴圈結束);另在 ai_attack_execute 0x1548e 入口停下。r1 = 第 1 回合、r2 = 第 2 回合(敵方回合 3 個攻方)。"
             "重算規則:地形只在 0x1f183 回 1 時套(攻方用候選格、目標用自己的格,百分比截斷向零);原始 = 攻方 AP' - 目標 DP',"
             "> 2 優先級 8 否則 0;原始 > 目標目前 HP → ×2、優先級 0x12;0x1debe(目標, 格) 回 1(目標 +0x26 == 0、曼哈頓 1、"
             "目標裝備 kind0 武器列 +0xb <= 1)→ 加 攻方 DP' - 目標 AP';目標 +8 == 0 → ×3/2 截斷向零;先比優先級再比分數,"
             "嚴格較大才換。rival_* 為對照規則:doc11 舊述「<= 2 略過」、地形閘門與實戰同極性、0x1debe 取攻方、×3/2 取 floor、同分取後者。"),
    "runs": runs,
    "tie_run_12_no_attack_recheck": {
        "source": "續六十二第 2 回合 tie 場景的 0x14b78 入口傾印(.wsl_build/ctr/sl/tie_002_001B0B78.units.bin),本輪沒有在該場景下斷 0x14237",
        "actor_12": {"xy": [3, 0], "ap": 24},
        "adjacent_opponents": {"sol_0": {"xy": [2, 0], "dp": 724}, "unit_4": {"xy": [3, 1], "dp": 671}},
        "npcs_boxed_in": {"unit_5": [0, 0], "unit_6": [1, 0], "blocked_by": "四鄰全是對手格(0x40 不可進入)"},
        "conclusion": "可達配對的原始分數全部為負 → 優先級 0 且不大於 0,不記錄 → P = 0 → 0x14121 / 0x13e9c 備援(以本輪規則重算,推論)",
    },
}
json.dump(out, open(DST, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
open(DST, "a", encoding="utf-8", newline="\n").write("\n")
print("wrote", DST)
