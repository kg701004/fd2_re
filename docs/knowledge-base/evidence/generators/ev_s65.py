"""續六十五的證據檔:
  evidence/collect_targets_selector_20261001.json — collect_targets_in_range 的 selector 2/3/5(12 個停點逐一重算)與 17 個呼叫點的 selector 來源;
  evidence/terrain_shipped_maps_20261001.json — 出貨地圖 18/19/24/25/28 的活地圖、活地形表比對、開場站在地形 3..5 的單位、3 次受控攻擊。
"""
import collections
import json
import struct
import sys

from _evpaths import GAME_S, ROOT_S, TOOLS, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(TOOLS))
import disasm_le  # noqa: E402
import parse_field  # noqa: E402

ROOT = ROOT_S
EV = out_path("").as_posix() + "/"
EXE = GAME_S + "/FD2.EXE"
exe = open(EXE, "rb").read()
meta = disasm_le.parse_le(exe)
ob = lambda a, n: bytes(disasm_le.object_bytes(exe, meta, a, n))

# ---------- selector ----------
sel_rows = json.load(open(ROOT + "/.wsl_build/ctr/sel/analyze.json", encoding="utf-8"))
assert all(r["count_match"] and r["list_match"] and r["marks_match_recompute"] for r in sel_rows)
spells = [ob(0x619FD + i * 7, 7) for i in range(36)]
items = [ob(0x602AD + i * 0x17, 0x17) for i in range(215)]
rival_diff = collections.Counter()
for r in sel_rows:
    for k, v in r["rival_predictions"].items():
        rival_diff[k] += v != r["predicted"]
CALL_SITES = [
    ("0x14448", "ai_physical_candidate_select", "a2 == 0 ? 1 : 0", "武器列 +0xb", "武器列 +0xc"),
    ("0x15114", "0x15060(ai_choose_action 之後的道具執行段,未登錄)", "mode == 0 ? (道具列 +0x11 == 0 ? 1 : 0) : +0x11", "0", "道具列 +0x12"),
    ("0x15381", "ai_spell_execute", "mode == 0 ? (法術 +6 == 0 ? 1 : 0) : +6", "0", "法術 +4"),
    ("0x1575a", "ai_item_candidate_select", "0(寫死,outBuf NULL,只標施放點)", "列 +0x10 > 0xf", "列 +0x10"),
    ("0x157d4", "ai_item_candidate_select", "mode == 0 ? (道具列 +0x11 == 0 ? 1 : 0) : +0x11", "0", "道具列 +0x12"),
    ("0x15aaa", "ai_spell_candidate_select", "mode == 0 ? (法術 +6 == 0 ? 1 : 0) : +6", "0", "法術 +4"),
    ("0x18e25", "player_action_ring", "0(寫死,outBuf NULL)", "武器列 +0xb", "武器列 +0xc"),
    ("0x18f6a", "player_action_ring", "0(寫死)", "武器列 +0xb", "武器列 +0xc"),
    ("0x1bc3c", "player_item_action", "3(寫死,outBuf NULL)", "1", "1"),
    ("0x1bd43", "player_item_action", "道具列 +0x15", "道具列 +0xd == 0x17", "道具列 +0x10"),
    ("0x1bd93", "player_item_action", "道具列 +0x15", "0", "道具列 +0x12"),
    ("0x1becf", "player_item_action", "3(寫死)", "1", "1"),
    ("0x1d1c9", "player_spell_select(只有法術 0x17)", "法術 +6", "1", "法術 +3"),
    ("0x1d211", "player_spell_select(只有法術 0x17)", "法術 +6", "0", "法術 +4"),
    ("0x1d2bf", "player_spell_select", "法術 +6", "0", "法術 +3"),
    ("0x1d32a", "player_spell_select", "法術 +6", "0", "法術 +4"),
    ("0x1d38e", "player_spell_select(施法距離 0)", "0(寫死)", "0", "法術 +4"),
]
sel_out = {
    "note": ("DOSBox-X 斷點與記憶體傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;第 1 章戰場第 1 回合。"
             "斷點 collect_targets_in_range 返回點 0x149f0(執行期 0x1b09f0),每次停下傾印堆疊(筆數、返回位址、6 個參數)、"
             "地圖格陣列、21 個單位與 outBuf。記號格以活記憶體成本列 0 從原點重算 flood-fill(格旗標 0x40 不可進入、0x80 歸零)"
             "再套 extraThreshold,與傾印逐格比對;清單依 +5 bit0、記號、陣營規則重算後與 outBuf / 回傳筆數比對。"
             "擺位(距悠妮 (23,16)):我方 #3 (23,14) 2、#4 (24,15) 2、#2 (25,17) 3、索爾 (21,18) 4;NPC #5 (22,16) 1、#6 (23,18) 2、"
             "#7 (26,16) 3;敵 #11 (24,16) 1、#12 (21,16) 2。b*/c* 兩組是把法術 23 列 +6(執行期 0x1f3aa4)暫改成 2、5 後重選,之後改回 3。"
             "i* 為道具指令;i4 之前把 #3 從 (23,15) 移到 (23,13)。"),
    "selector_rule_static": "0x14992..0x149d2:0 → +6 == 0、1 → +6 != 0、2 → +6 == 1、3 → +6 == 2,其他值四個比較都不成立、不收",
    "shipped_selector_values": {
        "spell_0x6_over_36_spells": {str(k): v for k, v in sorted(collections.Counter(s[6] for s in spells).items())},
        "spells_with_0x6_3": [i for i, s in enumerate(spells) if s[6] == 3],
        "item_0x15_over_215_items": {str(k): v for k, v in sorted(collections.Counter(r[0x15] for r in items).items())},
        "item_0x11_equals_0x15_for_all": all(r[0x11] == r[0x15] for r in items),
        "items_with_use_effect_0xd_by_selector": {str(k): v for k, v in sorted(collections.Counter(r[0x15] for r in items if r[0xD]).items())},
        "conclusion": ("出貨資料沒有任何法術或道具帶 2;selector 3 只有法術 23(傳送術)與道具指令的兩個寫死呼叫;"
                       "帶 5 的 182 個道具 +0xd 都是 0(沒有使用效果),所以 selector 2 與 >= 4 只能由改值觸發。"),
    },
    "call_sites": [dict(zip(("call", "function", "selector", "extra_threshold", "range"), c)) for c in CALL_SITES],
    "summary": {
        "stops": len(sel_rows), "all_match": True,
        "by_selector": {str(k): v for k, v in sorted(collections.Counter(r["selector"] for r in sel_rows).items())},
        "rival_rules_stops_differing": dict(rival_diff),
        "rival_rules": {
            "sel_ge2_as_1": "selector 2、3(及其他非 0 值)都當 1:收 +6 != 0",
            "sel3_eq3": "selector 3 收 +6 == 3",
            "sel_ge4_as_3": "selector >= 4 落到 3 的判斷(收 +6 == 2)",
            "ignore_extra_threshold": "不套 extraThreshold(施法者 / 開道具者本身在清單內)",
        },
        "target_cursor_start": "a2/b2 的第二次呼叫原點是游標位置:取消時游標停在清單第一個單位(#2、#5);清單為空時留在施法者(c2)",
        "give_disabled_when_count_0": ("i4 計數 0 後同樣按 Left、Return,[0x53c57] 讀回 0(進到『使用』);i1 計數 1 時同一組按鍵走到 "
                                       "0x1becf(只有 [0x53c57] == 1 才會到)。也就是相鄰沒有我方時『交給』選不到。"),
    },
    "stops": sel_rows,
}
json.dump(sel_out, open(EV + "collect_targets_selector_20261001.json", "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
open(EV + "collect_targets_selector_20261001.json", "a", encoding="utf-8", newline="\n").write("\n")

# ---------- terrain on shipped maps ----------
terrain = json.load(open(ROOT + "/docs/data/exe_tables/terrain.json", encoding="utf-8"))
T = ROOT + "/.wsl_build/ctr/terr/"
RUNS = [(19, "ch19", "d0"), (20, "ch20", "d0"), (25, "ch25", "d0"), (26, "ch26", "d1"), (29, "ch29", "d0")]


def stops(path: str) -> list:
    out = []
    for line in open(path, encoding="utf-8"):
        p = dict(kv.split("=") for kv in line.split() if "=" in kv)
        s = lambda k: struct.unpack("<i", bytes.fromhex(p[k])[::-1])[0]
        out.append({"eip": p["EIP"], "eax": s("EAX"), "edx": s("EDX")})
    return out


maps = []
for chap, d, tag in RUNS:
    rd = lambda f: open(f"{T}{d}/{tag}_{f}.bin", "rb").read()
    grid, tt, units = rd("grid"), rd("tt"), rd("units")
    W, H = struct.unpack_from("<HH", grid, 0)
    m = chap - 1
    fb = open(ROOT + "/extracted/raw/FDFIELD/FDFIELD_%03d.bin" % (3 * m), "rb").read()
    live_t = [struct.unpack_from("<H", grid, 4 + 4 * i)[0] & 0x3FF for i in range(W * H)]
    stat_t = [struct.unpack_from("<H", fb, 4 + 4 * i)[0] & 0x3FF for i in range(W * H)]
    mc = {e["idx"]: e["move_code"] for e in terrain["tilesets"][m]["entries"]}
    used = sorted(set(live_t))
    ty = lambda x, y: tt[live_t[y * W + x] * 4 + 1]
    info = parse_field.parse_map(ROOT + "/extracted/raw", m)
    occ = {(units[i * 80], units[i * 80 + 1]): i for i in range(len(units) // 80) if not units[i * 80 + 5] & 1}
    hi_static = sorted({(x, y) for x, y, p in info["positions"] if ty(x, y) >= 3})
    pos_count = collections.Counter((x, y) for x, y, p in info["positions"])
    on_hi = []
    for (x, y), i in sorted(occ.items(), key=lambda k: k[1]):
        if ty(x, y) >= 3:
            r = units[i * 80:(i + 1) * 80]
            on_hi.append({"unit": i, "xy": [x, y], "type": ty(x, y), "side_0x6": r[6], "raw_key_0x7": r[7],
                          "race": r[0x1F], "class": r[0x20], "mv": r[0x3B]})
    maps.append({
        "save_chapter_shown": chap, "save_chapter_byte": chap - 1, "map": m, "W": W, "H": H,
        "tiles_equal_FDFIELD": sum(a == b for a, b in zip(live_t, stat_t)), "cells": W * H,
        "tiles_used": len(used), "live_type_byte_vs_terrain_json_differing": sum(tt[t * 4 + 1] != mc.get(t) for t in used),
        "live_type_counts": {str(k): v for k, v in sorted(collections.Counter(tt[t * 4 + 1] for t in live_t).items())},
        "units_live": len(units) // 80,
        "units_on_type_ge3_at_player_control": on_hi,
        "static_start_cells_type_ge3": [{"xy": list(c), "type": ty(*c), "entries": pos_count[c], "occupied_by": occ.get(c)}
                                        for c in hi_static],
    })

ATTACKS = [
    {"map": 18, "file": "ch19/t2", "attacker": 5, "attacker_cell": [16, 36], "attacker_type": 3, "attacker_race_class": [1, 6],
     "defender": 26, "defender_cell": [16, 35], "defender_type": 3, "defender_race_class": [1, 13],
     "defender_moved_by_SM": True, "AP": 125, "DP": 105,
     "predicted": {"ap_mod": -6, "ap_rem": -25, "dp_mod": 10, "dp_rem": 50, "damage": 3},
     "rival_floor": {"ap_mod": -7, "damage": 2}},
    {"map": 19, "file": "ch20/t3", "attacker": 12, "attacker_cell": [26, 34], "attacker_type": 4, "attacker_race_class": [1, 2],
     "defender": 24, "defender_cell": [25, 34], "defender_type": 4, "defender_race_class": [9, 28],
     "defender_moved_by_SM": True, "AP": 125, "DP": 110,
     "predicted": {"ap_mod": -6, "ap_rem": -25, "dp_mod": -5, "dp_rem": -50, "damage": 12},
     "rival_floor": {"ap_mod": -7, "dp_mod": -6}},
    {"map": 28, "file": "ch29/t4", "attacker": 13, "attacker_cell": [13, 57], "attacker_type": 0, "attacker_race_class": [1, 11],
     "defender": 45, "defender_cell": [13, 56], "defender_type": 5, "defender_race_class": [6, 25],
     "defender_moved_by_SM": True, "AP": 125, "DP": 115,
     "predicted": {"ap_mod": 6, "ap_rem": 25, "dp_mod": 0, "dp_rem": 0, "damage": 14},
     "rival_type5_as_4": {"dp_mod": -5, "damage": 18}, "rival_type5_as_3": {"dp_mod": 11, "damage": 4}},
]
for a in ATTACKS:
    d, t = a["file"].split("/")
    st = stops(f"{T}{d}/{t}_stops.txt")
    a["breakpoints"] = st
    a["live"] = {"ap_mod": st[0]["eax"], "ap_rem": st[0]["edx"], "dp_mod": st[1]["eax"], "dp_rem": st[1]["edx"], "damage": st[2]["eax"]}
    for ph in ("pre", "post"):
        u = open(f"{T}{d}/{t}_{ph}_units.bin", "rb").read()
        a[f"defender_hp_{ph}"] = struct.unpack_from("<H", u, a["defender"] * 80 + 0x40)[0]
    a["match"] = a["live"] == a["predicted"] and a["defender_hp_pre"] - a["defender_hp_post"] == a["predicted"]["damage"]
    del a["file"]
assert all(a["match"] for a in ATTACKS)

ter_out = {
    "note": ("DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。來源存檔 ~/fd2-run/FD2.SAV(md5 e6d9a35756cddfc2519969b10f039181)"
             "複製後以 fd2_chapter_sweep 的 prepare_chapter_save 改章節 byte(grid-pick 章節 roster_cap = 門檻 + 1),"
             "LOAD → attempt_camp_exit → ensure_battle_hud 進到可操作的戰場後傾印 [0x53a45] 單位陣列、[0x53a51] 地圖格、[0x53a69] 地形表。"
             "存檔章節 byte N 載入 map N(畫面顯示第 N+1 章)。受控攻擊的斷點:0x2f8dc(EAX = AP 修正、EDX = 餘數)、0x2f921(DP 修正)、"
             "0x2f9fc(傷害);攻方 AP 125、DP 0、HIT 250、EV 0,守方 HP 999、AP 19、HIT 250、EV 0、麻痺 1(不反擊)。"
             "攻方都用自己的移動走到格子上(以 SM 瞬移的攻方在 ch19 無法確認移動,改用正常移動);守方以 SM 搬到相鄰的同類地形格。"),
    "maps": maps,
    "attacks": ATTACKS,
    "terrain_modifier_tables_live": {"ap_pct_0x51a12": [5, 0, -5, -5, -5, 0], "dp_pct_0x51a2a": [0, 0, 10, 10, -5, 0],
                                     "read_at": "每個戰場各讀一次 0x1eda12(執行期),三章相同"},
    "hud_readout": "游標停在地形 3 / 4 / 5 格時左下角資訊框分別顯示 A-05 D+10、A-05 D-05、A+00 D+00(截圖 t1_cursor / t3_moved / t4_aim)",
    "terrain5_start_placement": ("map 24(第 25 章)開場時 #17(陣營 1、raw key 0x68、種族 10、職業 26、MV 0)站在地形 5 的 (10,0);"
                                 "同圖 (5,7) 的 15 筆重複出場座標開場時無人。map 25 的 (1,45)、map 28 的 4 格開場時都無人;"
                                 "map 28 的回合事件列都是休眠(回合 0xff),但會被事件 75/76 改寫啟用,事件 76 之後把 group 1 的三個頭目放到其中 3 格"
                                 "(見 terrain_events_map_attack_20261001.json)。parse_field 以索引配對的(出場座標, 單位)與活記憶體逐筆相符,只是活陣列先放我方。"),
}
json.dump(ter_out, open(EV + "terrain_shipped_maps_20261001.json", "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
open(EV + "terrain_shipped_maps_20261001.json", "a", encoding="utf-8", newline="\n").write("\n")
print(json.dumps(sel_out["summary"]["rival_rules_stops_differing"]), sel_out["shipped_selector_values"]["spell_0x6_over_36_spells"])
for mp in maps:
    print(mp["map"], mp["tiles_equal_FDFIELD"], "/", mp["cells"], "diff", mp["live_type_byte_vs_terrain_json_differing"], mp["live_type_counts"],
          "on>=3", len(mp["units_on_type_ge3_at_player_control"]), [(c["xy"], c["entries"], c["occupied_by"]) for c in mp["static_start_cells_type_ge3"]])
for a in ATTACKS:
    print(a["map"], a["live"], a["defender_hp_pre"], a["defender_hp_post"], a["match"])
