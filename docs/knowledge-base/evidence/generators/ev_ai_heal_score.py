"""AI 恢復術評分(ai_spell_target_score 法術 13..16 分支)與 [0x53c23] >= 6 施法門檻的動態驗證:離線重算並寫出證據 JSON。

輸入(.wsl_build/ctr):sc_units_<run>.bin、sc_call_<run>_<n>.bin、sc_best_<run>_<n>.bin、hl_pre/hl_post 傾印。EAX、停點序號、單位表檔名與 0x1598a 入口順序由當時 sc_log.sh 的終端輸出
(原始紀錄,見 _console.py)解析,並逐停點核對終端印出的法術 / 目標 / 施放點 / best 與同一停點的傾印相同。
"""
import json
import re
import struct
import sys
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402
D = ROOT / ".wsl_build" / "ctr"
EVI = out_path("ai_heal_score_20260930.json")
_EXE = (GAME / "FD2.EXE").read_bytes()
_META = dl.parse_le(_EXE)


def spell_row(sid: int) -> dict:
    """由 FD2.EXE 讀法術列(linear 0x619fd + id*7,經 disasm_le 換算檔案位置)並解碼。

    Args:
        sid: 法術編號。

    Returns:
        {"value": +0 u16, "cast": +3 施放距離, "area": +4 範圍, "mp": +5, "sel": +6 選擇子, "row": 7 bytes 十六進位}。
    """
    r = bytes(dl.object_bytes(_EXE, _META, 0x619FD + sid * 7, 7))
    return {"value": struct.unpack_from("<H", r, 0)[0], "cast": r[3], "area": r[4], "mp": r[5], "sel": r[6], "row": r.hex(" ")}


SPELL_ID = 13  # 盜賊 #11 只會法術 13(下面以每次入口傾印的已學法術位元欄核對)
SPELL13 = spell_row(SPELL_ID)
CASTER = 11
# 當時 sc_log.sh 的終端輸出(原始紀錄,見 _console.py),每輪一個工具呼叫。H2 當時以 grep 濾掉 unit 12..17 的行;
# H3 在對話框間反覆呼叫 sc_log.sh(標籤 h3_1..h3_14),只有 h3_11 那次有停點;實際標籤由輸出裡的單位表檔名取得。
CONSOLE = {"h1": "20260930T015808_toolu_01MqTS9FHCfawt1zGxqYQnff", "h2": "20260930T020330_toolu_0117Yr6PyLfUEYZwxgBnY7oK",
           "h3": "20260930T021153_toolu_01KRBWL8xU4UU4asUKxBXC3a"}


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


def entry_order(ev: list[dict]) -> list[str]:
    """0x1598a 入口與 ai_spell_execute 的出現順序(pass1 = 返回位址 0x1d91f、pass2 = 0x14f1a)。

    相鄰、同種、且同為(或同非)施法者 #11 的事件併成一項,單位以 a..b 區間表示;
    整段沒有 ai_spell_execute 時在最後註明。
    """
    groups: list[tuple[tuple[str, bool], list[int]]] = []
    for e in ev:
        if e["kind"] == "entry":
            kind = {0x1D91F: "pass1", 0x14F1A: "pass2"}[e["ret"]]
        elif e["kind"] == "execute":
            kind = "ai_spell_execute"
        else:
            continue
        key = (kind, e["unit"] == CASTER)
        if groups and groups[-1][0] == key:
            groups[-1][1].append(e["unit"])
        else:
            groups.append((key, [e["unit"]]))
    out = []
    for (kind, _), us in groups:
        spans: list[list[int]] = []
        for u in us:
            if spans and u == spans[-1][1] + 1:
                spans[-1][1] = u
            else:
                spans.append([u, u])
        out.append(kind + ":" + ",".join(f"{a}" if a == b else f"{a}..{b}" for a, b in spans))
    if not any(e["kind"] == "execute" for e in ev):
        out.append("(沒有 ai_spell_execute)")
    return out


# (標籤, 傾印標籤, [單位傾印], [[EAX]], [(評分停點)], [出口停點]) — 每輪兩次 0x1598a,由終端輸出解析
# CON[(傾印標籤, 停點)] = 終端印出的 (法術, 目標, 施放點)(評分停點)或 best(出口停點),供下面與傾印核對
RUNS, CON, ORDER = [], {}, {}
for _run, _stem in CONSOLE.items():
    _ev = sc_log(_stem)
    _ps = caster_passes(_ev)
    _tags = {e["tag"] for e, _, _ in _ps}
    assert len(_tags) == 1, _tags
    RUNS.append((_run, _tags.pop(), [e["units"] for e, _, _ in _ps], [[s["eax"] for s in sc] for _, sc, _ in _ps],
                 [tuple(s["n"] for s in sc) for _, sc, _ in _ps], [x["n"] for _, _, x in _ps]))
    for _e, _sc, _x in _ps:
        CON |= {(_e["tag"], s["n"]): (s["spell"], s["targets"], s["cast"]) for s in _sc}
        CON[(_e["tag"], _x["n"])] = _x["best"]
    ORDER[_run] = entry_order(_ev)


def units(name: str) -> list[dict]:
    b = (D / f"{name}.bin").read_bytes()
    out = []
    for i in range(len(b) // 80):
        r = b[i * 80:(i + 1) * 80]
        w = lambda o: struct.unpack_from("<H", r, o)[0]
        out.append({"i": i, "x": r[0], "y": r[1], "f5": r[5], "side": r[6], "hp": w(0x40), "maxhp": w(0x42),
                    "b34": r[0x34], "mp": w(0x44),
                    # 已學法術位元欄 +0x1a..+0x1e(bit k = 法術 k,低位元在前)
                    "spells": [k for k in range(40) if r[0x1A + k // 8] >> (k % 8) & 1]})
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
        # 施法者只學會 SPELL_ID(入口傾印的法術位元欄),所以候選清單只會出現這一個法術
        assert c["spells"] == [SPELL_ID], (run, uname, c["spells"])
        calls = []
        for n, eax in zip(stops, eax_list):
            b = (D / f"sc_call_{ftag}_{n}.bin").read_bytes()
            sp, cnt, _ = struct.unpack_from("<III", b, 0)
            tg = list(b[0xC:0xC + cnt])
            # 終端印出的法術、目標、施放點必須等於同一停點的堆疊傾印(證明這段輸出與傾印是同一次執行、停點對應無誤)
            assert CON[(ftag, n)] == (sp, tg, (b[0x60], b[0x58])), (run, n, CON[(ftag, n)])
            pred = score(tg, us)
            calls.append({"stop": n, "spell": sp, "cast_point": [b[0x60], b[0x58]], "targets": tg, "score_eax": eax,
                          "score_recomputed": pred,
                          "target_state": [{"unit": i, "hp": us[i]["hp"], "maxhp": us[i]["maxhp"], "b34": us[i]["b34"]} for i in tg]})
            if pred != eax:
                mism.append((run, n, eax, pred))
        # 候選清單:距施法者 <= 列 +3 的格,目標 = 距該格 <= 列 +4、+5 bit0 清除、選擇子相符的單位(序號序),依 y 再 x。
        # 列 +6 非 0 → 選擇子 0(+6 == 0,同陣營);0 → 選擇子 1(+6 != 0)
        camp0 = SPELL13["sel"] != 0
        pred_list = []
        for y in range(21):
            for x in range(27):
                if abs(x - c["x"]) + abs(y - c["y"]) > SPELL13["cast"]:
                    continue
                tg = [u["i"] for u in us if (u["side"] == 0) == camp0 and not (u["f5"] & 1)
                      and abs(u["x"] - x) + abs(u["y"] - y) <= SPELL13["area"]]
                if tg:
                    pred_list.append((SPELL_ID, (x, y), tg))
        obs_list = [(g["spell"], tuple(g["cast_point"]), g["targets"]) for g in calls]
        if obs_list != pred_list:
            mism.append((run, "candidate list", obs_list, pred_list))
        best, sel = 0, None
        for g in calls:
            if g["score_eax"] > best:
                best, sel = g["score_eax"], (g["score_eax"], g["cast_point"][0], g["cast_point"][1], SPELL_ID)
        bb = struct.unpack("<iiii", (D / f"sc_best_{ftag}_{ex}.bin").read_bytes()[:16])
        assert CON[(ftag, ex)] == bb, (run, ex, CON[(ftag, ex)])  # 終端印出的 best = 出口傾印
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
    # MP 消耗 = 法術列 +5(由 EXE 讀出,與實測的扣點互相核對)
    assert post[t]["hp"] == pre[t]["maxhp"] and pre[CASTER]["mp"] - post[CASTER]["mp"] == SPELL13["mp"], heal[run]

print("calls", sum(len(r["calls"]) for r in runs_out), "mismatches", mism)
assert not mism
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點(0x1598a 入口、0x15add 評分回傳 EAX、0x15b6d 出口)與單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。"
            "盜賊 #11 只會法術 13(回復)、拿掉武器;其他盜賊 MaxHP 28,HP 夾在 28/3 = 9、28/2 = 14 兩個整數邊界上,部分設 +0x34 bit0。"
            "單位表只傾印 0..20 號;第 3 回合增援 21..26 沒有進入候選清單(觀察到的清單與只用 0..20 號重算的清單相同)。",
    "spell_row_13": SPELL13, "runs": runs_out, "entry_order": ORDER, "heal_results": heal,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("written", EVI.name)
