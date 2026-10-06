"""續六十八證據:evidence/ai_seek_opponent_rand_trace_20261001.json。
A. 0x14121(mode 2 找對手後的流程與起點 (0,0) 的未初始化 outBuf):由 .wsl_build/ctr/v5/ch25 的停點紀錄與傾印整理,
   mode 2 搜尋以入口地圖逐指令重算。
B. rand(0x4ebe3)在敵方回合的完整呼叫鏈(r1、r2):每次回傳 = nxt(前一次),從敵方回合入口讀到的種子起算。
C. 續六十六反擊的下數亂數:以 B 驗證過的呼叫順序列舉 65536 個起始狀態;先在 r1(真值已知)上做正對照。
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
S = GEN_DIR
sys.path.insert(0, str(S))
import rng  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

D = ROOT / ".wsl_build/ctr/v5/ch25"
OUT = out_path("ai_seek_opponent_rand_trace_20261001.json")
UB = 0x26EA0C

# ---------------- A. 0x14121 ----------------
subprocess.run([sys.executable, "-X", "utf8", str(S / "an_f.py"), "f3", "f3d", "f5"], check=True, cwd=S,
               capture_output=True)
calls = json.loads((D / "f_calls.json").read_text(encoding="utf-8"))
for c in calls:
    for it in c["seq"]:
        if it["eip"] == "0x14203":  # 呼叫 0x12d7b 前,[ESP] 是壓入的單位索引(an_f 的 unit_arg 取錯欄位)
            it.pop("unit_arg", None)
f3c = json.loads((D / "f3c_1421d.json").read_text(encoding="utf-8"))
u_after = (D / "f3c_units.bin").read_bytes()
u_t1 = (D / "s2_pre0_units.bin").read_bytes()
f3_stops = [s for st in json.loads((D / "f3.json").read_text(encoding="utf-8")) for s in st["stops"]]
push_unit = [s["ret"] for s in f3_stops if s["eip"] == "0x14203"]
f5_inj = [s for st in json.loads((D / "f5.json").read_text(encoding="utf-8")) for s in st["stops"]
          if "injected_local" in s]
labels = {45: "B:MV 0,找得到對手", 48: "A:找得到對手", 53: "C:站在 (0,0)", 54: "D:站在 (0,2)"}
# 標籤是設定說明;被呼叫的單位必須正好是這四個
assert {c["unit"] for c in calls if c["tag"] != "f5"} == set(labels), sorted({c["unit"] for c in calls})
A = {
    "setup": "map 24(第 25 章)第 2 回合:A = #48 (10,10)、B = #45 (21,31) MV 0、C = #53 (0,0)、D = #54 (0,2),四者未麻痺、"
             "清法術/MP/第二格道具;友軍 #17 從 (10,0) 搬到 (24,52),其他單位麻痺 9。第 5 回合只留 C 在 (0,0),"
             "在 0x14132 把未初始化的 [esp+4..5] 改成 (0,0)。",
    "calls": [dict(c, label=("C2:同 C,注入 (0,0)" if c["tag"] == "f5" else labels.get(c["unit"]))) for c in calls],
    "push_before_0x12d7b_raw": push_unit,
    "C_0x14b78_return": {"eip": f3c["eip"], "eax": f3c["eax"]},
    "C_final_xy": [u_after[53 * 80], u_after[53 * 80 + 1]],
    "C_turn1_unlogged_xy": [u_t1[53 * 80], u_t1[53 * 80 + 1]],
    "grid_wh": list(struct.unpack_from("<HH", (D / "f3_4_pre.bin").read_bytes(), 0)),
    "injection": [{"before": s["local"], "after": s["injected_local"]} for s in f5_inj],
}
for c in A["calls"]:
    for it in c["seq"]:
        if it["eip"] == "0x141b5":
            assert it["grid_diff"] == 0 and it["sim_res"] == it["eax"], c
assert A["C_final_xy"] == [172, 53] and A["C_turn1_unlogged_xy"] == [172, 53]

# ---------------- B. rand 鏈 ----------------
B = {}
for tag in ("r1", "r2"):
    d = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    prev = d["seed_at_phase_entry"]
    seq = []
    for s in d["stops"]:
        if s["eip"] == "0x4ebfe":
            ok = s["val"] == rng.nxt(prev)
            seq.append({"site": s["ret"], "val": s["val"], "mod100": s["val"] % 100, "chain": ok})
            prev = s["val"]
        elif s["eip"] == "0x1e856":
            seq.append({"map_attack_sequence": s["args"][:2]})
        elif s["eip"] == "0x1e8cf":
            seq.append({"roll_edx": s["edx"], **({"forced_to": s["edx_after"]} if "forced_from" in s else {})})
        elif s["eip"] == "0x1efce":
            seq.append({"dmg": s["ebp"], "rem": s["edx"], "new_hp": s["eax"]})
    assert all(x["chain"] for x in seq if "site" in x)
    B[tag] = {"seed_at_enemy_phase_entry": hex(d["seed_at_phase_entry"]), "seq": seq}
sites = [x["site"] for x in B["r2"]["seq"] if "site" in x]
assert sites == ["0x1e8c3", "0x1eec1", "0x1eee9", "0x1efac"] + ["0x1e8c3"] + ["0x1eec1", "0x1eee9", "0x1efac"] * 2

# ---------------- C. 反推 ----------------
H = lambda v: True  # noqa: E731  HIT - EV = 250,命中判定恆真(仍消耗一次 rand)
m = lambda k, r: (lambda v: v % k == r)  # noqa: E731


def hit(crit_thr: int, k: int, rem: int) -> list:
    return [("hit", H), ("crit", lambda v: v % 100 >= crit_thr), ("dmg", m(k, rem))]


# 正對照 r1:E(#19,職業 5,會心門檻 0x524a8[4] = 3)打索爾 1 下(基礎 90,k 10,餘 3),索爾(職業 9,門檻 5)反擊 1 下(餘 4)
r1_model = [("e_roll", lambda v: v % 100 >= 3)] + hit(3, 10, 3) + [("s_roll", lambda v: v % 100 >= 3)] + hit(5, 10, 4)
c1 = rng.enumerate_states(r1_model)
truth = int(B["r1"]["seed_at_enemy_phase_entry"], 16)
C_control = {"model": "E 下數(>=3)、命中、會心(>=3)、傷害 %10 == 3;索爾下數(>=3)、命中、會心(>=5)、傷害 %10 == 4",
             "candidates": len(c1), "true_state_in_candidates": any(x["s0"] == truth for x in c1)}
assert C_control["true_state_in_candidates"]

# 續六十六:火龍(職業 26,門檻 0)基礎 45、k 5、餘 2,1 下;索爾(職業 9,門檻 5)基礎 126、k 14、餘 1 與 4
ev66 = json.loads((ROOT / "docs/knowledge-base/evidence/ai_mode8_move_confirm_boss_20261001.json").read_text(
    encoding="utf-8"))["A_map28_boss_on_terrain5"]
hp = [s for s in ev66["map_enemy_phase_stops"] if s["eip"] == "0x1efce"]
rems = [s["edx"] for s in hp]
assert rems == [2, 1, 4] and [s["ebp"] for s in hp] == [47, 127, 130]
# 會心門檻 0x524a8[職業 - 1] 與武器類型(道具列 +9)由 EXE 讀;雙方職業與武器由續六十六交手前的單位傾印讀
# (火龍 #76、索爾 #0)。職業 26 讀到的 [25] = 0 落在門檻表尾端的 0 區,表的實際長度未確認(語意照舊)。
exe = (GAME / "FD2.EXE").read_bytes()
meta = dl.parse_le(exe)
CRIT = bytes(dl.object_bytes(exe, meta, 0x524A8, 30))
c0u = (ROOT / ".wsl_build/ctr/v3/ch29/c0_pre_units.bin").read_bytes()
DRAGON, SOL = 76, 0
cls = {u: c0u[u * 80 + 0x20] for u in (DRAGON, SOL)}
wpn = {u: c0u[u * 80 + 0xB] for u in (DRAGON, SOL)}
wtype = {u: bytes(dl.object_bytes(exe, meta, 0x602AD + wpn[u] * 0x17, 0x17))[9] for u in (DRAGON, SOL)}
assert (cls[DRAGON], cls[SOL], wpn[DRAGON], wpn[SOL]) == (26, 9, 103, 31), (cls, wpn)
assert 3 not in wtype.values()  # 武器類型 3 才會多打一下;兩邊都不是
thr = {u: CRIT[cls[u] - 1] for u in (DRAGON, SOL)}
kd, ks = ev66["predicted"]["base_dragon_to_sol"] // 9, ev66["predicted"]["base_sol_to_dragon"] // 9
dragon = [("d_roll", lambda v: v % 100 >= 3)] + hit(thr[DRAGON], kd, rems[0])
modelA = dragon + [("s_roll", None)] + hit(thr[SOL], ks, rems[1]) + hit(thr[SOL], ks, rems[2])
cA = rng.enumerate_states(modelA)
two = [x for x in cA if x["vals"][4] % 100 < 3]
modelB = dragon + [("a_roll", lambda v: v % 100 >= 3)] + hit(thr[SOL], ks, rems[1]) + \
    [("b_roll", lambda v: v % 100 >= 3)] + hit(thr[SOL], ks, rems[2])
cB = rng.enumerate_states(modelB)
C = {
    "inputs_from_s66": {"damage": [s["ebp"] for s in hp], "rem": rems, "k": [kd, ks, ks],
                        "crit_threshold_0x524a8": {f"dragon_class{cls[DRAGON]}": thr[DRAGON], f"sol_class{cls[SOL]}": thr[SOL]},
                        "weapon_types": {str(wpn[u]): wtype[u] for u in (DRAGON, SOL)}},
    "control_r1": C_control,
    "modelA_one_counter_two_hits": {"candidates": len(cA), "with_roll_lt3": len(two),
                                    "roll_values": sorted({x["vals"][4] % 100 for x in two}),
                                    "states": [{"s0": hex(x["s0"]), "roll_rand": x["vals"][4]} for x in two]},
    "modelB_two_counters_one_hit_each": {"candidates": len(cB),
                                         "note": "傷害資料本身排除不了;排除靠反擊只有一個呼叫點(0x1560e)與續六十七的實測"},
    "expected_random_count": round(65536 / (5 * 14 * 14), 1),
}
assert C["modelA_one_counter_two_hits"]["roll_values"] == [0]
ev = {"note": "DOSBox-X;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;第 25 章戰場 = map 24,來源存檔 source_ch27.SAV 經 "
              "prepare_chapter_save;斷點位址為 Ghidra 位址,執行期 +0x19c000;rand 種子 0x627b8 在 obj3,執行期 +0x192000。",
      "A_0x14121_after_mode2": A, "B_rand_chain": B, "C_s66_counter_roll": C}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("A calls", len(A["calls"]), "C", C["control_r1"], C["modelA_one_counter_two_hits"]["candidates"],
      C["modelA_one_counter_two_hits"]["roll_values"], len(cB))
