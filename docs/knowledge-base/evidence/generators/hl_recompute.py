"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

AI 恢復術評分(ai_spell_target_score 法術 13..16 分支)與 [0x53c23] >= 6 施法門檻的動態驗證:離線重算並寫出證據 JSON。

輸入(.wsl_build/ctr):sc_units_<run>.bin、sc_call_<run>_<n>.bin、sc_best_<run>_<n>.bin、hl_pre/hl_post 傾印。EAX 依停點序抄錄自終端輸出。
"""
import json
import struct
from pathlib import Path

ROOT = Path(r"C:\Users\kg701\Desktop\GAME\fd2_re")
D = ROOT / ".wsl_build" / "ctr"
EVI = ROOT / "docs" / "knowledge-base" / "evidence" / "ai_heal_score_20260930.json"
SPELL13 = {"value": 70, "cast": 4, "area": 0, "mp": 3, "sel": 1, "row": "46 00 00 04 00 03 01"}
CASTER = 11
STOPS = [(6, 7, 8, 9, 10, 11), (14, 15, 16, 17, 18, 19)]
RUNS = [
    ("h1", "h1", ["sc_units_h1_5", "sc_units_h1_13"], [[8, 3, 0, 3, 6, 0]] * 2, [STOPS[0], STOPS[1]], [12, 20]),
    ("h2", "h2", ["sc_units_h2_5", "sc_units_h2_13"], [[3, 0, 0, 6, 3, 0]] * 2, [STOPS[0], STOPS[1]], [12, 20]),
    ("h3", "h3_11", ["sc_units_h3_11_1", "sc_units_h3_11_33"], [[3, 0, 0, 3, 3, 0]] * 2,
     [(2, 3, 4, 5, 6, 7), (34, 35, 36, 37, 38, 39)], [8, 40]),
]
# 0x1598a 入口(unit 欄)與 ai_spell_execute 的出現順序,抄錄自終端輸出(pass1 = 返回位址 0x1d91f、pass2 = 0x14f1a)
ORDER = {
    "h1": ["pass1:11", "pass2:11", "ai_spell_execute:11", "pass1:12..17", "pass2:12..17"],
    "h2": ["pass1:11", "pass2:11", "ai_spell_execute:11"],
    "h3": ["pass1:11", "pass1:12..17,21..26", "pass2:11", "pass2:12..17,21..26", "(沒有 ai_spell_execute)"],
}


def units(name: str) -> list[dict]:
    b = (D / f"{name}.bin").read_bytes()
    out = []
    for i in range(len(b) // 80):
        r = b[i * 80:(i + 1) * 80]
        w = lambda o: struct.unpack_from("<H", r, o)[0]
        out.append({"i": i, "x": r[0], "y": r[1], "f5": r[5], "side": r[6], "hp": w(0x40), "maxhp": w(0x42),
                    "b34": r[0x34], "mp": w(0x44)})
    return out


def score(targets: list[int], us: list[dict]) -> int:
    """0x15b77 法術 13..16 分支:HP < MaxHP/3(整數)得 8,否則 HP < MaxHP/2 得 3,否則 0;+0x34 bit0 時 × 2。"""
    t = 0
    for i in targets:
        u = us[i]
        s = 8 if u["maxhp"] // 3 > u["hp"] else (3 if u["maxhp"] // 2 > u["hp"] else 0)
        if u["b34"] & 1:
            s *= 2
        t += s
    return t


mism, runs_out = [], []
for run, ftag, unames, eaxs, stopsets, exits in RUNS:
    for uname, eax_list, stops, ex in zip(unames, eaxs, stopsets, exits):
        us = units(uname)
        c = us[CASTER]
        calls = []
        for n, eax in zip(stops, eax_list):
            b = (D / f"sc_call_{ftag}_{n}.bin").read_bytes()
            sp, cnt, _ = struct.unpack_from("<III", b, 0)
            tg = list(b[0xC:0xC + cnt])
            pred = score(tg, us)
            calls.append({"stop": n, "spell": sp, "cast_point": [b[0x60], b[0x58]], "targets": tg, "score_eax": eax,
                          "score_recomputed": pred,
                          "target_state": [{"unit": i, "hp": us[i]["hp"], "maxhp": us[i]["maxhp"], "b34": us[i]["b34"]} for i in tg]})
            if pred != eax:
                mism.append((run, n, eax, pred))
        # 候選清單:距施法者 <= 4 的格上有 +6 == 0、+5 bit0 清除的單位(範圍 0),依 y 再 x
        occ = {(u["x"], u["y"]): u["i"] for u in us if u["side"] == 0 and not (u["f5"] & 1)}
        pred_list = [(13, (x, y), [occ[(x, y)]]) for y in range(21) for x in range(27)
                     if abs(x - c["x"]) + abs(y - c["y"]) <= SPELL13["cast"] and (x, y) in occ]
        obs_list = [(g["spell"], tuple(g["cast_point"]), g["targets"]) for g in calls]
        if obs_list != pred_list:
            mism.append((run, "candidate list", obs_list, pred_list))
        best, sel = 0, None
        for g in calls:
            if g["score_eax"] > best:
                best, sel = g["score_eax"], (g["score_eax"], g["cast_point"][0], g["cast_point"][1], 13)
        bb = struct.unpack("<iiii", (D / f"sc_best_{ftag}_{ex}.bin").read_bytes()[:16])
        if sel != bb:
            mism.append((run, "selection", bb, sel))
        runs_out.append({"run": run, "units_dump": uname, "caster": {"xy": [c["x"], c["y"]], "mp": c["mp"]}, "calls": calls,
                         "best_53c23_27_2b_2f": list(bb), "casts_predicted": bb[0] >= 6})

# 施法結果:H1 補 #13(8 -> 28)、H2 補 #14(13 -> 28),MP 各扣 3;H3 沒有施法
heal = {}
for run, t in (("h1", 13), ("h2", 14)):
    pre, post = units(f"hl_pre_{run}"), units(f"hl_post_{run}")
    heal[run] = {"target": t, "hp": [pre[t]["hp"], post[t]["hp"]], "maxhp": pre[t]["maxhp"],
                 "caster_mp": [pre[CASTER]["mp"], post[CASTER]["mp"]]}
    assert post[t]["hp"] == pre[t]["maxhp"] and pre[CASTER]["mp"] - post[CASTER]["mp"] == 3, heal[run]

print("calls", sum(len(r["calls"]) for r in runs_out), "mismatches", mism)
assert not mism
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點(0x1598a 入口、0x15add 評分回傳 EAX、0x15b6d 出口)與單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "盜賊 #11 只會法術 13(回復)、拿掉武器;其他盜賊 MaxHP 28,HP 夾在 28/3 = 9、28/2 = 14 兩個整數邊界上,部分設 +0x34 bit0。"
            "單位表只傾印 0..20 號;第 3 回合增援 21..26 沒有進入候選清單(觀察到的清單與只用 0..20 號重算的清單相同)。",
    "spell_row_13": SPELL13, "runs": runs_out, "entry_order": ORDER, "heal_results": heal,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("written", EVI.name)
