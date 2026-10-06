"""續六十五(第二段)證據:evidence/terrain_events_map_attack_20261001.json。
A. map 24:地形 5 上的 NPC #17 與敵 #57 經 map_attack_resolve 交手;
B. map 28:悠妮在 (15,21) 結束行動 → 事件 75 → 事件 76 逐回合計數 → spawn_group(1) 把 3 個頭目放在地形 5;
C. map 19 / map 18:map_attack_resolve 在地形 4 / 3 上的攻擊與反擊(含 map 19 的中毒扣血、map 18 #26 的 AI 模式 0x8 不出手)。
"""
import json
import os
import struct

from _evpaths import ROOT_S, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
from _terrain import terrain_type  # noqa: E402
ROOT = ROOT_S
T = ROOT + "/.wsl_build/ctr/terr2/"
OUT = str(out_path("terrain_events_map_attack_20261001.json"))


def stops(path):
    out = []
    for line in open(path, encoding="utf-8"):
        p = dict(kv.split("=") for kv in line.split()[1:] if "=" in kv)
        s = lambda k: struct.unpack("<i", bytes.fromhex(p[k].rjust(8, "0"))[::-1])[0]
        out.append({"eip": p["EIP"], "eax": s("EAX"), "edx": s("EDX"), "esi": p["ESI"], "edi": p["EDI"]})
    return out


def hp(path, i):
    u = open(path, "rb").read()
    return {"hp": struct.unpack_from("<H", u, i * 80 + 0x40)[0], "xy": [u[i * 80], u[i * 80 + 1]],
            "poison_0x25": u[i * 80 + 0x25]}


def exchange(d, tag, base, e, p, pred):
    st = stops(f"{T}{d}/{tag}_stops.txt")
    idx = lambda h: (int(h, 16) - base) // 80
    mods = [{"site": "0x1edbf AP" if s["eip"] == "001BADBF" else "0x1ee04 DP", "attacker": idx(s["edi"]),
             "defender": idx(s["esi"]), "quotient": s["eax"], "remainder": s["edx"]}
            for s in st if s["eip"] in ("001BADBF", "001BAE04")]
    hpw = [{"defender": idx(s["esi"]), "new_hp": s["eax"]} for s in st if s["eip"] == "001BAFCE"]
    ex = [s for s in st if s["eip"] == "001B148E"]
    r = {"ai_attack_execute_actor": ex[0]["esi"] and int(ex[0]["esi"], 16) if ex else None,
         "modifier_stops": mods, "hp_write_stops": hpw,
         "pre": {str(e): hp(f"{T}{d}/{tag}_pre_units.bin", e), str(p): hp(f"{T}{d}/{tag}_pre_units.bin", p)},
         "post": {str(e): hp(f"{T}{d}/{tag}_post_units.bin", e), str(p): hp(f"{T}{d}/{tag}_post_units.bin", p)},
         "predicted": pred}
    got = [(m["quotient"], m["remainder"]) for m in mods]
    r["modifiers_match"] = got == [tuple(x) for x in pred["mods"]]
    return r


# A. map 24
a = exchange("ch25", "x", 0x26EA0C, 57, 17, {
    "mods": [[6, 0], [0, 0], [0, 0], [0, 0]],
    "note": "#57(地形 0)攻 #17(地形 5):AP 120 → +6、#17 DP 110 → 0;#17 反擊:AP 120 → 0、#57 DP 105 → 0;傷害 14 / 13",
    "rival_type5_as_4": "#17 DP 修正 -5、反擊 AP 修正 -6"})
a["hp_change"] = {"17": a["pre"]["17"]["hp"] - a["post"]["17"]["hp"], "57": a["pre"]["57"]["hp"] - a["post"]["57"]["hp"]}
assert a["modifiers_match"] and a["hp_change"] == {"17": 14, "57": 13}

# B. map 28 event chain
def state(tag):
    ad5 = open(f"{T}ch29/{tag}_ad5.bin", "rb").read()
    ctl = open(f"{T}ch29/{tag}_ctl.bin", "rb").read()
    return {"turn": open(f"{T}ch29/{tag}_turn.bin", "rb").read()[0], "ad5_0x10": ad5[0x10], "ad5_0x11": ad5[0x11],
            "ad5_0x15": ad5[0x15], "rows_turn_event_camp": [[ctl[3 + 3 * k], ctl[4 + 3 * k], ctl[5 + 3 * k]] for k in range(3)]}

chain = [{"when": w, **state(t)} for w, t in [
    ("開戰(未操作)", "s0"), ("悠妮在 (15,21) 休息、事件 75 對話結束後", "s3"), ("第 2 回合玩家回合", "t2s"),
    ("第 3 回合", "t3"), ("第 4 回合", "t4"), ("第 5 回合,事件 76 生成後", "sp")]]
u = open(f"{T}ch29/sp_units_all.bin", "rb").read()
cnt = open(f"{T}ch29/sp_cnt.bin", "rb").read()[0]
spawned = []
for i in range(cnt - 3, cnt):  # 生成的 3 個頭目是單位表的最後 3 筆(sp_cnt = 生成後的單位數)
    r = u[i * 80:(i + 1) * 80]
    spawned.append({"unit": i, "xy": [r[0], r[1]], "side_0x6": r[6], "raw_key_0x7": r[7], "race": r[0x1F], "class": r[0x20],
                    "mv": r[0x3B], "hp": struct.unpack_from("<H", r, 0x40)[0]})
# 觸發格的事件 slot = 地圖格 byte2 低 5 位(1-based),控制段 +0x33 起每 slot 2 bytes (event_id, selector);
# 生成格的地形類型由同一張地圖(map 28)的地圖格與地形表傾印算出
G29 = ROOT + "/.wsl_build/ctr/terr/ch29/"
grid29, tt29 = open(G29 + "d0_grid.bin", "rb").read(), open(G29 + "d0_tt.bin", "rb").read()
TRIG = (15, 21)
slot1 = grid29[4 + 4 * (TRIG[1] * struct.unpack_from("<H", grid29, 0)[0] + TRIG[0]) + 2] & 0x1F
ctl0 = open(f"{T}ch29/s0_ctl.bin", "rb").read()
ev_id, ev_sel = ctl0[0x33 + 2 * (slot1 - 1)], ctl0[0x34 + 2 * (slot1 - 1)]
assert (ev_id, ev_sel) == (75, 1), (slot1, ev_id, ev_sel)  # 事件 75、選擇子 1(玩家行動結束後呼叫)
spawn_types = {terrain_type(grid29, tt29, *s["xy"]) for s in spawned}
assert len(spawn_types) == 1, spawn_types
b = {"setup": "悠妮(+8 = 9)MV 改 45;除 #69..#72(麻痺 40)外的敵人 +5 bit0 並移到 (0,0);其餘不改",
     "trigger_cell": list(TRIG), "field_event_slot_1based": slot1,
     "field_event": {"slot": slot1 - 1, "event_id": ev_id, "selector": ev_sel},
     "dialogue_event75": "『就是這裡了!系統識別碼..』…『中樞撤銷最高級系統防護需要一些時間…』",
     "dialogue_event76_spawn": "『奇怪,終端竟然抗拒我的命令,有人對防衛系統動了手腳!』",
     "states": chain, "unit_count_after_spawn": cnt, "spawned_group1": spawned,
     "terrain_of_spawn_cells": next(iter(spawn_types))}
assert [c["ad5_0x11"] for c in chain] == [0, 1, 2, 3, 4, 4] and chain[-1]["ad5_0x15"] == cnt - 3
assert all(s["xy"] in ([13, 12], [15, 12], [17, 12]) for s in spawned)

# C. map 19 / 18
c19 = exchange("ch20", "x4b", 0x26D820, 24, 12, {
    "mods": [[-6, -50], [-5, -75], [-6, -50], [-5, -50]],
    "note": "#24(地形 4、MV 0)攻 #12(地形 4、DP 115):AP 130 → -6、DP → -5;#12 反擊:AP 130 → -6、#24 DP 110 → -5;傷害 12 / 17"})
assert [h["defender"] for h in c19["hp_write_stops"]] == [12, 24]  # 先寫 #12(P)、再寫 #24(E)
c19["hp_write"] = {"P_new_hp": c19["hp_write_stops"][0]["new_hp"], "E_new_hp": c19["hp_write_stops"][1]["new_hp"]}
c19["extra_poison"] = "攻方攻擊種類讓 #12 中毒(+0x25 = 3),下一個我方回合開始扣 MaxHP/10 = 99;第一次跑的 -111 = 12 + 99"
assert c19["modifiers_match"] and [h["new_hp"] for h in c19["hp_write_stops"]] == [987, 982]
c18 = exchange("ch19", "x3b", 0x26BFC0, 23, 5, {
    "mods": [[-6, -50], [10, 50], [-6, -50], [11, 0]],
    "note": "#23(SM 搬到地形 3 的 (15,4)、MV 0)攻 #5(地形 3、DP 105):AP 130 → -6、DP → +10;#5 反擊:AP → -6、#23 DP 110 → +11;傷害 8 / 2"})
assert c18["modifiers_match"] and [h["new_hp"] for h in c18["hp_write_stops"]] == [991, 997]
c18["first_try"] = "原本用站在地形 3 的 #26(+0x34 = 0x8,武器 item 56 射程 1):整個敵方回合沒有任何 ai_attack_execute 停點,改用 +0x34 = 0x2 的 #23"

out = {
    "note": ("DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;來源存檔 ~/fd2-run/FD2.SAV(md5 e6d9a357…)經 prepare_chapter_save 改章節 byte。"
             "map_attack_resolve 斷點(執行期 +0x19c000):0x1edbf(AP 修正後,EAX 商 EDX 餘數,EDI 攻方記錄、ESI 守方記錄)、0x1ee04(DP 修正)、"
             "0x1efce(寫守方 HP,EAX = 新 HP);ai_attack_execute 0x1548e;[0x53af9] 設 1(地圖呈現)。"),
    "A_map24_npc17_on_terrain5": a,
    "B_map28_event_chain": b,
    "C_map19_terrain4": c19,
    "C_map18_terrain3": c18,
    "static": {
        "turn_event_dispatch_0x1a813": "列 k 在 [0x53a55] + 3k:+3 回合、+4 event_id、+5 陣營;回合 = [0x53bef] 且陣營相符才呼叫 [0x51b91 + id*4]",
        "dormant_rows_armed_by_handlers": "事件 75 寫列 1(+6)= 回合+1、列 0(+3)= 回合;事件 76 寫列 1 = 回合+1 或列 2(+9)= 回合;事件 74 寫列 0 = 回合+1",
        "field_event_lookup_0x13a44": "格子 event word 低 5 位(1-based slot)查 [0x53a55]+0x33 的 (event_id, selector),寶箱格(旗標 0x60)不查;玩家行動結束後以 selector 1 呼叫(0x18aef/0x18b0c)",
        "spawn_group_0x10b4e": "掃 FDFIELD 控制段單位(+0x83 起 26 bytes/筆)的 +0x15(波次)等於參數者逐一呼叫 0x10c50 建構",
        "map28": "ch28_pre(0x33dba)spawn group 8(開場 56 敵)、ch28_post(0x2548c)spawn group 9((15,3) 地形 5,戰後演出)、事件 76 spawn group 1(三個頭目,地形 5)",
    },
}
json.dump(out, open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
open(OUT, "a", encoding="utf-8", newline="\n").write("\n")
print("ok", OUT)
for k in ("A_map24_npc17_on_terrain5", "C_map19_terrain4", "C_map18_terrain3"):
    print(k, [(m["site"], m["attacker"], m["defender"], m["quotient"], m["remainder"]) for m in out[k]["modifier_stops"]], out[k]["hp_write_stops"])
print([(c["when"], c["ad5_0x11"], c["rows_turn_event_camp"]) for c in chain])
