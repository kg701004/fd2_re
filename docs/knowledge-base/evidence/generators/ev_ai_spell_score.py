"""AI 法術評分(0x1598a / 0x15b77)動態驗證:由傾印離線重算每次評分、候選清單與最終選擇,寫出證據 JSON。

輸入(.wsl_build/ctr):sc_units_<run>.bin(0x1598a 入口的單位表)、sc_call_<run>_<n>.bin(0x15add 的 0x70 bytes 堆疊)、
sc_best_<run>_<n>.bin([0x53c23..0x53c2f])、R6 的 sc_pre_r6/sc_post_r6 與 [0x53ec8] 讀值。
EAX(分數)只出現在終端輸出:由當時 sc_log.sh 與 R6 讀值迴圈的終端輸出(原始紀錄,見 _console.py)解析,
並逐停點核對終端印出的法術 / 目標 / 施放點 / best 與同一停點的傾印相同。
"""
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
D = ROOT / ".wsl_build" / "ctr"
EVI = out_path("ai_spell_score_20260930.json")

# 法術列 0x619fd + id*7(靜態 disasm_le data 619fd):+0 value、+3 施放距離、+4 範圍、+5 MP、+6 選擇子
SPELL = {8: {"value": 440, "cast": 8, "area": 0, "mp": 24, "sel": 0, "row": "b8 01 64 08 00 18 00"},
         12: {"value": 340, "cast": 0, "area": 9, "mp": 80, "sel": 0, "row": "54 01 5a 00 09 50 00"}}

CASTER = 11
# 當時 sc_log.sh 的終端輸出(原始紀錄,見 _console.py),每輪一個工具呼叫。R3 是在對話框間反覆呼叫
# sc_log.sh(標籤 r3_1..r3_10),只有 r3_10 那次有停點;實際標籤由輸出裡的單位表檔名取得。
CONSOLE = {"r1": "20260929T164028_toolu_01RtUp9tpz3L1ZiUjFnLXfQ6", "r2": "20260929T164512_toolu_015fgwkNScrtrG6r6mnb3idB",
           "r3": "20260929T165016_toolu_01AxqLhzTR2TCjPeVn2uRH8T", "r4": "20260929T165722_toolu_01X9fQ37RgiYSDPLeRLSo5Di"}
R6_CONSOLE = "20260929T170343_toolu_019bDp4oAd1hjRSUQvgsrdf8"  # R6 在 0x1546a / 0x15474 讀 [0x53ec8] 的迴圈輸出


def sc_log(stem: str) -> list[dict]:
    """解析 sc_log.sh 的終端輸出(依停點序);每行格式見該腳本的 echo。

    Args:
        stem: 原始紀錄 `<UTC 時間>_<tool_use_id>`。

    Returns:
        [{"n": 停點, "kind": "entry" | "score" | "exit" | "execute", ...}]。
    """
    _, text = _console.load(stem)
    eax = {s["n"]: s["EAX"] for s in _console.stops(text) if "EAX" in s}
    ev: list[dict] = []
    for line in text.splitlines():
        m = re.fullmatch(r"  units -> (sc_units_(.+)_(\d+))\.bin", line)
        if m:  # 入口停點傾印的單位表 = sc_units_<標籤>_<停點>(sc_call / sc_best 用同一個標籤)
            assert ev[-1]["kind"] == "entry" and int(m[3]) == ev[-1]["n"], line
            ev[-1]["units"], ev[-1]["tag"] = m[1], m[2]
            continue
        if not line.startswith("stop "):
            continue
        n, body = line[5:].split(": ", 1)
        e: dict = {"n": int(n)}
        if m := re.fullmatch(r"entry 0x1598a ret=(0x[0-9a-f]+) unit=(\d+) mode=(\d+)", body):
            e |= {"kind": "entry", "ret": int(m[1], 16), "unit": int(m[2])}
        elif m := re.fullmatch(r"score EAX=[0-9A-F]+ spell=(\d+) count=(\d+) ptr_ok=True targets=\[([\d, ]*)\] "
                               r"cast=\((\d+),(\d+)\)", body):
            e |= {"kind": "score", "eax": eax[e["n"]], "spell": int(m[1]),
                  "targets": [int(t) for t in m[3].split(", ") if t], "cast": (int(m[4]), int(m[5]))}
            assert len(e["targets"]) == int(m[2]), line
        elif m := re.fullmatch(r"exit 0x1598a unit=(\d+) best\(score,x,y,spell\)=\((-?\d+), (-?\d+), (-?\d+), (-?\d+)\)", body):
            e |= {"kind": "exit", "unit": int(m[1]), "best": tuple(int(m[k]) for k in range(2, 6))}
        elif m := re.fullmatch(r"ai_spell_execute ret=(0x[0-9a-f]+) unit=(\d+) a2=(\d+)", body):
            e |= {"kind": "execute", "unit": int(m[2])}
        else:
            raise AssertionError(f"{stem} 無法解析:{line}")
        ev.append(e)
    # 停點序號嚴格遞增 = 整段輸出來自同一次 sc_log.sh 迴圈(不會把兩次呼叫的停點混在一起)
    assert [e["n"] for e in ev] == sorted({e["n"] for e in ev}), stem
    return ev


def caster_passes(ev: list[dict]) -> list[tuple[dict, list[dict], dict]]:
    """施法者 #11 的每次 0x1598a:(入口停點, 其間的評分停點, 出口停點)。"""
    out = []
    for k, e in enumerate(ev):
        if e["kind"] == "entry" and e["unit"] == CASTER:
            j = next(j for j in range(k + 1, len(ev)) if ev[j]["kind"] != "score")
            assert ev[j]["kind"] == "exit" and ev[j]["unit"] == CASTER, ev[j]
            out.append((e, ev[k + 1:j], ev[j]))
    # 每輪 0x1598a 被呼叫兩次:返回位址 0x1d91f(第一遍掃描)與 0x14f1a(ai_choose_action)
    assert [p[0]["ret"] for p in out] == [0x1D91F, 0x14F1A], [p[0]["ret"] for p in out]
    return out


# (標籤, 單位傾印, [(評分停點, EAX)], 出口停點, 傾印標籤) — 由終端輸出解析,每輪 0x1598a 被呼叫兩次
# CON[(傾印標籤, 停點)] = 終端印出的 (法術, 目標, 施放點)(評分停點)或 best(出口停點),供下面與傾印核對
RUNS, CON = [], {}
for _run, _stem in CONSOLE.items():
    for _e, _sc, _x in caster_passes(sc_log(_stem)):
        RUNS.append((_run, _e["units"], [(s["n"], s["eax"]) for s in _sc], _x["n"], _e["tag"]))
        CON |= {(_e["tag"], s["n"]): (s["spell"], s["targets"], s["cast"]) for s in _sc}
        CON[(_e["tag"], _x["n"])] = _x["best"]


def units(name: str) -> list[dict]:
    b = (D / f"{name}.bin").read_bytes()
    out = []
    for i in range(len(b) // 80):
        r = b[i * 80:(i + 1) * 80]
        w = lambda o: struct.unpack_from("<H", r, o)[0]
        out.append({"i": i, "x": r[0], "y": r[1], "f5": r[5], "side": r[6], "p7": r[7], "p8": r[8], "race": r[0x1F],
                    "cls": r[0x20], "hp": w(0x40), "mp": w(0x44)})
    return out


def gate_1f183(u: dict) -> bool:
    """unit_uses_move_cost_row19:+7 == 0x1c 回 0;職業 0x13 或種族 4/5 回 1。"""
    if u["p7"] == 0x1C:
        return False
    return u["cls"] == 0x13 or u["race"] in (4, 5)


def score(spell: int, targets: list[int], us: list[dict]) -> int:
    """0x15b77 的法術 < 13 分支。"""
    v, total = SPELL[spell]["value"], 0
    for t in targets:
        u = us[t]
        if spell >= 10 and gate_1f183(u):
            continue
        s = 8 if u["hp"] >= v else 0x18
        if u["p8"] == 0:
            s = s * 3 // 2  # FPU × 1.5 後 frndint;8、24 都是整數結果
        total += s
    return total


def eligible(us: list[dict], x: int, y: int, rng: int) -> list[int]:
    """collect_targets_in_range 選擇子 1(+6 != 0)、+5 bit0 清除、曼哈頓距離 <= rng。"""
    return [u["i"] for u in us if u["side"] != 0 and not (u["f5"] & 1) and abs(u["x"] - x) + abs(u["y"] - y) <= rng]


result, mismatches = [], []
for run, uname, calls, exit_stop, ftag in RUNS:
    us = units(uname)
    c = us[CASTER]
    cx, cy, mp = c["x"], c["y"], c["mp"]
    got_calls, pred_calls = [], []
    for n, eax in calls:
        b = (D / f"sc_call_{ftag}_{n}.bin").read_bytes()
        sp, cnt, _ = struct.unpack_from("<III", b, 0)
        tg = list(b[0xC:0xC + cnt])
        pt = (b[0x60], b[0x58])
        # 終端印出的法術、目標、施放點必須等於同一停點的堆疊傾印(證明這段輸出與傾印是同一次執行、停點對應無誤)
        assert CON[(ftag, n)] == (sp, tg, pt), (run, n, CON[(ftag, n)])
        pred = score(sp, tg, us)
        got_calls.append({"stop": n, "spell": sp, "cast_point": pt, "targets": tg, "score_eax": eax, "score_recomputed": pred})
        if pred != eax:
            mismatches.append((run, n, eax, pred))
    # 候選清單重算:MP 足夠的法術依序;施放點 = 距施法者 <= cast 且有目標的格,依 y 再 x 排序(map_collect_cells_byte3_set 的掃描序)
    for sp in sorted(SPELL):
        s = SPELL[sp]
        if s["mp"] > mp:
            continue
        cells = [(x, y) for y in range(21) for x in range(27) if abs(x - cx) + abs(y - cy) <= s["cast"]]
        for (x, y) in cells:
            tg = eligible(us, x, y, s["area"])
            if tg:
                pred_calls.append((sp, (x, y), sorted(tg)))
    obs = [(g["spell"], tuple(g["cast_point"]), sorted(g["targets"])) for g in got_calls]
    if obs != pred_calls:
        mismatches.append((run, "candidate list", obs, pred_calls))
    # 最終選擇:分數嚴格較大才換;同分時法術列 +0 較大才換
    best, bval, sel = 0, 0, None
    for g in got_calls:
        v = SPELL[g["spell"]]["value"]
        if g["score_eax"] > best or (g["score_eax"] == best and v > bval):
            best, bval, sel = g["score_eax"], v, (g["score_eax"], g["cast_point"][0], g["cast_point"][1], g["spell"])
    bb = struct.unpack("<iiii", (D / f"sc_best_{ftag}_{exit_stop}.bin").read_bytes()[:16])
    assert CON[(ftag, exit_stop)] == bb, (run, exit_stop, CON[(ftag, exit_stop)])  # 終端印出的 best = 出口傾印
    if sel != bb:
        mismatches.append((run, "selection", bb, sel))
    result.append({"run": run, "units_dump": uname, "caster": {"xy": [cx, cy], "mp": mp},
                   "targets_state": {str(u["i"]): {"xy": [u["x"], u["y"]], "hp": u["hp"], "+8": u["p8"], "race": u["race"],
                                                   "class": u["cls"], "+7": u["p7"]}
                                     for u in us if u["side"] != 0 and not (u["f5"] & 1)},
                   "calls": got_calls, "best_53c23_27_2b_2f": list(bb), "best_predicted": list(sel)})

# R6:AI 施法打 NPC(+7 = 0x85 >= 0x44,擊殺)→ [0x53ec8] 應為 high_class_row10_ptr(0x41)+9 (=1,靜態 0x61d8c) × 等級 3
pre, post = units("sc_pre_r6"), units("sc_post_r6")
killed = [u["i"] for u in pre if u["hp"] and not post[u["i"]]["hp"]]
assert killed == [6] and post[6]["f5"] & 1, killed
# [0x53ec8] 讀值由 R6 迴圈的終端輸出解析(執行期 EIP = 靜態 + 0x19c000)
r6_obs = {}
for m in re.finditer(r"(?m)^iter (\d+): EIP=([0-9A-F]+) \[0x53ec8\]=(-?\d+)$", _console.load(R6_CONSOLE)[1]):
    r6_obs[int(m[2], 16) - 0x19C000] = int(m[3])
    # 同一停點傾印的 [0x53ec8](sc_ec8_r6_<iter>.bin)必須等於終端印出的值
    assert struct.unpack("<i", (D / f"sc_ec8_r6_{m[1]}.bin").read_bytes()[:4])[0] == int(m[3]), m[0]
assert sorted(r6_obs) == [0x1546A, 0x15474], r6_obs
r6 = {"target": 6, "target_+7": pre[6]["p7"], "target_level": 3, "row_0x61d83": "01 1b 0c 00 00 01 03 01 04 01",
      "predicted_53ec8": 1 * 3, "observed_at_0x1546a": r6_obs[0x1546A], "observed_at_0x15474": r6_obs[0x15474],
      "caster_ex_before": 0, "caster_ex_after": (D / "sc_post_r6.bin").read_bytes()[11 * 80 + 0x3C],
      "caster_mp": [pre[11]["mp"], post[11]["mp"]]}
assert r6["caster_ex_after"] == 0 and r6["caster_mp"] == [79, 55]

print("calls checked", sum(len(r["calls"]) for r in result), "mismatches", mismatches)
assert not mismatches
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點(0x1598a 入口、0x15add 評分回傳 EAX、0x15b6d 出口的 [0x53c23..0x53c2f])與單位表傾印;"
            "FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。盜賊 #11 只會法術 8、12,拿掉武器。score_recomputed 依 0x15b77:"
            "HP >= 法術列 +0 得 8、否則 24,+8 == 0 再 × 1.5,法術 10..12 跳過 unit_uses_move_cost_row19 為真的目標,逐目標加總。"
            "每輪 0x1598a 被呼叫兩次(返回位址 0x1d91f 與 0x14f1a),兩次結果相同。",
    "spell_rows": SPELL, "runs": result, "r6_exp_reset": r6,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("written", EVI.name)
