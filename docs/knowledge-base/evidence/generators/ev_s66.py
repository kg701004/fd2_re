"""續六十六證據:evidence/ai_mode8_move_confirm_boss_20261001.json。
A. map 28 事件 76 放出的頭目 #76(地形 5)被攻擊與反擊:場景路徑(玩家攻擊)與地圖路徑(敵方回合);
B. AI 模式(+0x34 低四位)8:分派函式直接跳到結尾,同一單位改模式 2 作對照;
C. 瞬移(SM 改 +0/+1)後的單位確認移動,與沒瞬移的悠妮對照。
預測值由 EXE 的地形修正表與傾印的單位數值獨立計算,再與斷點讀值比對。
"""
import json
import struct
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

V = ROOT / ".wsl_build/ctr/v3"
OUT = out_path("ai_mode8_move_confirm_boss_20261001.json")
EXE = GAME / "FD2.EXE"
exe = EXE.read_bytes()
meta = dl.parse_le(exe)
tab = dl.object_bytes(exe, meta, 0x51A12, 48)
AP_PCT = list(struct.unpack("<6i", tab[:24]))
DP_PCT = list(struct.unpack("<6i", tab[24:]))


def cdiv(a: int, b: int) -> tuple[int, int]:
    """C 的有號整數除法(向零截斷),回傳 (商, 餘數)。"""
    q = abs(a) // abs(b) * (1 if (a >= 0) == (b >= 0) else -1)
    return q, a - q * b


def mod(stat: int, t: int, tbl: list[int]) -> list[int]:
    return list(cdiv(stat * tbl[t], 100))


def rec(path: Path, i: int) -> dict:
    u = path.read_bytes()[i * 80:(i + 1) * 80]
    hp, mhp = struct.unpack_from("<2H", u, 0x40)
    ap, dp, hit, ev = struct.unpack_from("<4H", u, 0x48)
    return {"xy": [u[0], u[1]], "f5": u[5], "side": u[6], "key_0x7": u[7], "race": u[0x1F], "class": u[0x20],
            "mv": u[0x3B], "b34": u[0x34], "hp": hp, "maxhp": mhp, "ap": ap, "dp": dp, "hit": hit, "ev": ev}


# ---------------- A. map 28 頭目 ----------------
C29 = V / "ch29"
g = (C29 / "b2_grid.bin").read_bytes()
tt = (C29 / "b2_tt.bin").read_bytes()
W = g[0]


def ter(x: int, y: int) -> int:
    return tt[(struct.unpack_from("<H", g, 4 + 4 * (y * W + x))[0] & 0x3FF) * 4 + 1]


def ad5_ctl(tag: str) -> dict:
    a = (C29 / f"{tag}_ad5.bin").read_bytes()
    c = (C29 / f"{tag}_ctl.bin").read_bytes()
    return {"ad5_0x11": a[0x11], "ad5_0x15": a[0x15],
            "rows_turn_event_camp": [[c[3 + 3 * k], c[4 + 3 * k], c[5 + 3 * k]] for k in range(3)]}


spawned = []
for i in (76, 77, 78):
    r = rec(C29 / "b2_units.bin", i)
    r["terrain"] = ter(*r["xy"])
    spawned.append({"unit": i, **{k: r[k] for k in ("xy", "terrain", "key_0x7", "race", "class", "mv", "b34", "hp")}})
assert [s["xy"] for s in spawned] == [[13, 12], [15, 12], [17, 12]] and all(s["terrain"] == 5 for s in spawned)
assert all(s["b34"] & 0xF == 2 for s in spawned)

sol = rec(C29 / "c0_pre_units.bin", 0)
drg = rec(C29 / "c0_pre_units.bin", 76)
t_sol, t_drg = ter(*sol["xy"]), ter(*drg["xy"])
assert t_drg == 5 and sol["race"] == 5 and drg["race"] == 10


def base(ap: int, dp: int) -> int:
    return max(0, (ap - dp) * 9 // 10)


pred = {
    "dragon_dp_mod": mod(drg["dp"], 5, DP_PCT), "dragon_ap_mod": mod(drg["ap"], 5, AP_PCT),
    "sol_terrain_mods": "種族 5,unit_uses_move_cost_row19 為真,不修正(不應有索爾的修正停點)",
    "base_sol_to_dragon": base(sol["ap"], drg["dp"]), "base_dragon_to_sol": base(drg["ap"], sol["dp"]),
}
rivals = {}
for name, t in (("terrain5_as_4", 4), ("terrain5_as_3", 3)):
    dpm = mod(drg["dp"], t, DP_PCT)[0]
    apm = mod(drg["ap"], t, AP_PCT)[0]
    rivals[name] = {"dragon_dp_mod": dpm, "dragon_ap_mod": apm,
                    "base_sol_to_dragon": base(sol["ap"], drg["dp"] + dpm), "base_dragon_to_sol": base(drg["ap"] + apm, sol["dp"])}

steps = json.loads((C29 / "c3.json").read_text(encoding="utf-8"))
scene = steps[0]["stops"]
mapst = steps[2]["stops"]
assert [s["eip"] for s in scene] == ["0x2f921", "0x2f9fc", "0x2f8dc", "0x2f9fc"]
assert scene[0]["ebp_unit"] == 0 and scene[0]["edi_unit"] == 76 and [scene[0]["eax"], scene[0]["edx"]] == pred["dragon_dp_mod"]
assert scene[1]["eax"] == pred["base_sol_to_dragon"]
assert scene[2]["ebp_unit"] == 76 and scene[2]["edi_unit"] == 0 and [scene[2]["eax"], scene[2]["edx"]] == pred["dragon_ap_mod"]
assert scene[3]["eax"] == pred["base_dragon_to_sol"]
assert [s["eip"] for s in mapst] == ["0x1edbf", "0x1efce", "0x1ee04", "0x1efce", "0x1ee04", "0x1efce"]
assert mapst[0]["edi_unit"] == 76 and [mapst[0]["eax"], mapst[0]["edx"]] == pred["dragon_ap_mod"]
assert all(s["esi_unit"] == 76 and [s["eax"], s["edx"]] == pred["dragon_dp_mod"] for s in (mapst[2], mapst[4]))


def rng(b: int) -> list[int]:
    return [b, b + max(b // 9, 1) - 1]


hp_writes = [{"defender": s["esi_unit"], "new_hp": s["eax"], "ebp_damage": s["ebp"]} for s in mapst if s["eip"] == "0x1efce"]
# EBP 是這一擊的傷害:新 HP + 傷害 = 前一個 HP,串起來推回場景攻擊後的 HP
sol_before_map = hp_writes[0]["new_hp"] + hp_writes[0]["ebp_damage"]
drg_before_map = hp_writes[1]["new_hp"] + hp_writes[1]["ebp_damage"]
assert hp_writes[1]["new_hp"] - hp_writes[2]["ebp_damage"] == hp_writes[2]["new_hp"]
derived = {"scene_damage_to_dragon": drg["hp"] - drg_before_map, "scene_counter_damage_to_sol": sol["hp"] - sol_before_map,
           "map_damage_to_sol": hp_writes[0]["ebp_damage"], "map_counters_to_dragon": [h["ebp_damage"] for h in hp_writes[1:]]}
lo, hi = rng(pred["base_sol_to_dragon"])
assert lo <= derived["scene_damage_to_dragon"] <= hi and all(lo <= d <= hi for d in derived["map_counters_to_dragon"])
lo2, hi2 = rng(pred["base_dragon_to_sol"])
assert lo2 <= derived["scene_counter_damage_to_sol"] <= hi2 and lo2 <= derived["map_damage_to_sol"] <= hi2
post = {str(i): rec(C29 / "c3_post_units.bin", i)["hp"] for i in (0, 76)}
assert post == {"0": hp_writes[0]["new_hp"], "76": hp_writes[2]["new_hp"]}

A = {
    "setup": ("ch29 戰場(map 28)第 1 回合以 SM 設 [0x53ad5]+0x11 = 4、控制段列 1(事件 76、陣營 2)回合 = 2,不經悠妮與事件 75;"
              "其他敵人麻痺 9,索爾休息結束回合。第 2 回合事件 76 走 == 4 分支放出頭目。"),
    "armed": ad5_ctl("b1"), "after_turn2_event76": ad5_ctl("b2"), "unit_count_after": 79, "spawned_group1": spawned,
    "note_shortcut": "事件 76(0x360b6)只讀 +0x11:!= 4 時 unit_set_flag5_bit7(1)、+0x11 加 1、列 1 回合 = 目前回合 + 1;== 4 時對話、spawn(1)、+0x15 = 單位數 - 3、列 2 = 目前回合",
    "exchange_setup": ("第 2..3 回合清事件 79 對話時多按的 Return 讓回合前進(那段沒有斷點,不採計)。第 4 回合:索爾 #0 已在 (13,13)(地形 %d)、火龍 #76 在 (13,12)(地形 5);"
                       "SM 設索爾 HP 999、AP 700、DP 900、HIT 250、EV 0,火龍 HP 999、AP 950、DP 560、HIT 250、EV 0,第二格道具移除、法術與 MP 清 0;"
                       "[0x53af9] = 1。索爾在原地開指令環攻擊火龍;我方其他隊員仍麻痺,玩家回合隨即結束,敵方回合火龍攻擊索爾。") % t_sol,
    "terrain_pct_table_exe_0x51a12": {"ap": AP_PCT, "dp": DP_PCT},
    "pre": {"sol_0": sol, "dragon_76": drg},
    "predicted": pred, "rivals": rivals,
    "scene_player_attack_stops": scene, "map_enemy_phase_stops": mapst,
    "hp_write_stops": hp_writes, "derived_damage": derived,
    "damage_ranges": {"sol_to_dragon": [lo, hi], "dragon_to_sol": [lo2, hi2]},
    "post_hp": post,
    "observations": ["索爾(種族 5)的 AP/DP 修正停點一次都沒有出現,與 unit_uses_move_cost_row19 閘門一致",
                     "敵方回合火龍攻擊一次後,索爾反擊兩次(0x1ee04 + 0x1efce 各兩組,守方都是 #76);兩次反擊的原因未查"],
}

# ---------------- B. AI 模式 8 ----------------
C19 = V / "ch19"


def m8(tag: str) -> dict:
    stops = []
    for line in (C19 / f"{tag}_stops.txt").read_text(encoding="utf-8").splitlines():
        p = dict(kv.split("=") for kv in line.split()[1:])
        n = int(line.split()[0])
        st = (C19 / f"{tag}_{n:03d}_{p['EIP']}.stack.bin").read_bytes()
        dw = struct.unpack("<16I", st)
        eip = int(p["EIP"], 16) - 0x19C000
        s = {"eip": hex(eip), "eax": int(p["EAX"], 16), "esi": int(p["ESI"], 16)}
        if eip == 0x13AEF:
            s["unit"] = s["esi"]
            s["mode"] = s["eax"]
            s["caller_ret"] = hex(dw[7] - 0x19C000)
        elif eip in (0x14EF0, 0x13512, 0x15055, 0x1548E, 0x15311):
            s["caller_ret"] = hex(dw[0] - 0x19C000)
            s["arg0"] = dw[1]
        elif eip == 0x13E5A:
            s["unit"] = s["esi"]
        stops.append(s)
    pre = C19 / f"{tag}_pre_units.bin"
    postp = C19 / f"{tag}_post_units.bin"
    u26 = rec(pre, 26)
    return {"b34": u26["b34"], "unit26_pre": {k: u26[k] for k in ("xy", "hp", "f5")},
            "spells_mp_cleared": tag in ("m8c", "m8d"),
            "unit26_post_hp": rec(postp, 26)["hp"], "sol_hp": [rec(pre, 0)["hp"], rec(postp, 0)["hp"]],
            "stops": stops}


runs = {t: m8(t) for t in ("m8a", "m8b", "m8c", "m8d")}
for t in ("m8a", "m8c"):
    s26 = [s for s in runs[t]["stops"] if s.get("unit") == 26 or s.get("arg0") == 26]
    assert [s["eip"] for s in s26] == ["0x13aef", "0x13aef"] and all(s["mode"] == 8 for s in s26)
    assert [s["caller_ret"] for s in s26] == ["0x1d947", "0x1d9d7"]
    assert runs[t]["sol_hp"][0] == runs[t]["sol_hp"][1]
for t, ex in (("m8b", None), ("m8d", "0x15055")):
    s26 = [s for s in runs[t]["stops"] if s.get("unit") == 26 or s.get("arg0") == 26]
    eips = [s["eip"] for s in s26]
    assert eips[0] == "0x13aef" and s26[0]["mode"] == 2 and "0x14ef0" in eips and "0x13e5a" in eips and "0x13512" in eips
    assert "0x13aef" not in eips[1:]
    if ex:
        assert ex in eips
assert runs["m8d"]["sol_hp"] == [823, 776]
B = {
    "static": {
        "dispatch_0x13a9f": ["0x13aca test byte ptr [ebx + 5], 5 / jne 結尾", "0x13ad4 mov al, byte ptr [ebx + 0x34]; and al, 0xf",
                             "0x13d97 cmp eax, 8 / 0x13d9a je 0x1317d(共用的 add esp,0xc; pop; ret 結尾)",
                             "其他模式做完後到 0x13e5a:field_event_lookup(x, y, 1)、unit_set_flag5_bit7(unit)、0x134e4、0x11cac(0)"],
        "enemy_phase_0x1d8ba": ["第 1 趟:+6 == 0、+5 & 0x81 == 0、+0x26 == 0 的單位先算 ai_spell_candidate_select 與 ai_item_candidate_select,"
                                "[0x53c23] >= 6 或 [0x53c33] >= 6 才呼叫 0x13a9f(返回 0x1d947)",
                                "第 2 趟:同樣條件的單位全部呼叫 0x13a9f(返回 0x1d9d7);第 1 趟已行動的單位 +5 bit7 已設,不會再進"],
        "doc11_correction": "doc11 原表寫模式 8「進入共用完成路徑」;實際是直接跳到結尾,不走 0x13e5a 的共用收尾,所以也不設 +5 bit7",
    },
    "setup": ("ch19 戰場(map 18)。#26(FDFIELD b17 = 8,種族 1、職業 13、武器 item 56)SM 搬到 (10,32),正下方 (10,33) 是瞬移過去的索爾;"
              "其他敵人麻痺 9、[0x53af9] = 1;我方除悠妮外設已行動,悠妮移一格休息結束回合。同一單位、同一格,依序跑 4 個敵方回合。"),
    "runs": runs,
    "result": ("模式 8 的兩次(含 / 不含法術)#26 都在兩趟各進分派一次(EAX = 8,返回 0x1d947 與 0x1d9d7),之後沒有 ai_choose_action、執行函式、共用收尾或 "
               "unit_set_flag5_bit7 的停點,索爾 HP 不變。改模式 2 的兩次都進 ai_choose_action 與共用收尾、設 +5 bit7,第 2 趟不再進分派;"
               "清掉法術後走道具分支 0x15055(返回 0x1503e,EDX = AP − 目標 DP = −464),索爾 HP 823 → 776。"),
}

# ---------------- C. 瞬移後確認移動 ----------------
tpb = json.loads((C19 / "tpB.json").read_text(encoding="utf-8"))
assert tpb["teleport_to"] == [10, 33] and [s["regs"]["EIP"] for s in tpb["stops"]] == ["0x1b4890", "0x1b4986", "0x1b49fd"]
assert tpb["stops"][1]["regs"]["EAX"] == "0x1" and tpb["stops"][2]["regs"]["EAX"] == "0x1" and tpb["xy_after_confirm"] == [11, 33]


def steps_of(tag: str) -> list:
    return json.loads((C19 / f"{tag}.json").read_text(encoding="utf-8"))["steps"]


tpd, tpe, tpf = steps_of("tpD"), steps_of("tpE"), steps_of("tpF")
assert tpd[4]["xy"] == [11, 33] and [s["eax"] for s in tpd[4]["stops"]] == ["0x1", "0x1"]
assert tpe[1]["xy"] == [10, 33] and [s["eax"] for s in tpe[1]["stops"]] == ["0x1", "0x0"]
assert tpf[8]["xy"] == [12, 36] and [s["eax"] for s in tpf[8]["stops"]] == ["0x1", "0x0"]
assert tpf[11]["xy"] == [13, 36] and [s["eax"] for s in tpf[11]["stops"]] == ["0x1", "0x1"]
C = {
    "static": [
        "選單位:0x117e7 的 Enter 呼叫 0x12c0d,逐一比對單位記錄 +0/+1 與游標 [0x53ab1]/[0x53ab5](略過 0x34894 為真者),不讀地圖格的佔用",
        "0x18890:可達範圍 flood_fill_reach_grid 從游標格展開(預算 = MV +0x3b),map_block_cells_of_side(unit, 1) 把其他非敵方單位的格子標 0xff;"
        "target_cursor_loop(4, 0, 0) 在確認鍵時只拒絕記號 0xff 的格子",
        "接著 0x4e4f6 從選取時的游標格找到目的格的路徑:回 0(同一格)直接在原地開指令環(0x18b24 → 0x18d8c(unit, &, 0)),"
        "回 0xff 不開環就返回,其他值由 0x13488 走過去再開環;指令環按 Escape 時把 +0/+1 還原成選取時的游標格",
    ],
    "runs": {
        "tpA": "第一次:劇情對話還在,按鍵全被對話吃掉(0x18890 沒停),截圖可見對話框 —— 不採計",
        "tpB_teleported_sol_free_cell": {"teleport": "(10,36) → (10,33)", "stops": tpb["stops"], "xy_after_confirm": tpb["xy_after_confirm"],
                                         "xy_after_ring_escape": tpb["xy_after_escape"]},
        "tpD_teleported_sol_enemy_adjacent": {"enemy": "#26 SM 到 (10,32)", "steps": tpd},
        "tpE_teleported_sol_own_cell": {"steps": tpe},
        "tpF_native_yuni_control": {"steps": tpf},
    },
    "result": ("瞬移後的索爾:空地上往右一格 target_cursor_loop 回 1、路徑回 1、+0/+1 變 (11,33)、指令環開;敵人 #26 在正上方時同樣回 1/1、移到 (11,33)。"
               "在原地按確認:target_cursor_loop 回 1、路徑回 0,不移動、直接在原地開指令環。沒瞬移的悠妮兩種情況讀值完全相同(原地 1/0、移一格 1/1)。"
               "續六十五記的「瞬移後連相鄰格都確認不了」與「原地按 Return 只是切換移動範圍」都沒有重現;"
               "本輪第一次(tpA)按鍵被仍在進行的劇情對話吃掉,是與當時症狀一致的解釋(推論,當時沒有斷點紀錄)。"),
}

out = {
    "note": ("DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;來源存檔 ~/fd2-run/FD2.SAV(md5 e6d9a357…)經 prepare_chapter_save 改章節 byte。"
             "斷點位址為 Ghidra 位址,執行期 +0x19c000;每個斷點位址下斷前都先比對過活記憶體位元組與檔案。"),
    "A_map28_boss_on_terrain5": A,
    "B_ai_mode8": B,
    "C_teleport_move_confirm": C,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ok", OUT)
print("pred", pred)
print("rivals", rivals)
print("derived", derived, "ranges", [lo, hi], [lo2, hi2])
