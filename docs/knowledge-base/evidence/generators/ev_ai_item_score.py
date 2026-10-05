"""AI 道具評分(0x1567e / 0x15880)與道具分支的動態驗證:離線重算、證據 JSON、登錄表更新(doc98 續五十八)。

評分停點(0x157fd)的道具、目標、施放點、slot 與決策點(0x14f62)的 P/S/I/d 直接由傾印讀出;EAX、單位、bit 與執行函式由當時 it_log.sh 的終端輸出(原始紀錄,見 _console.py)解析,
並逐停點核對終端印出的道具 / 目標 / 施放點 / slot 與 P/S/I/d 等於同一停點的傾印。
"""
# 移植說明:原腳本後段是一次性更新 docs/data/function_names.json 的補丁(已套用並提交),不屬於證據重算,移植時刪除。
import json
import re
import struct
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402,F401
require_inputs(__file__)
import _console  # noqa: E402
D = ROOT / ".wsl_build" / "ctr"
EVI = out_path("ai_item_score_20260930.json")
# 道具列(0x602ad + id*0x17,靜態 disasm_le data):+0xd type、+0xe word、+0x10 距離、+0x11 選擇子旗標、+0x12 範圍
ITEM = {
    58: {"type": 0x0D, "e": 300, "range": 2, "sel11": 1, "area": 0, "row": "06 b4 00 5a 00 00 00 00 00 00 00 01 01 0d 2c 01 02 01 00 10 27 01 00"},
    38: {"type": 0x15, "e": 1, "range": 2, "sel11": 0, "area": 1, "row": "04 b4 00 64 00 00 00 00 00 00 00 01 01 15 01 00 02 00 01 d4 30 00 00"},
}
SPELL_VALUE = {1: 120}  # 法術列 0x619fd + 1*7 = 78 00 5a 05 00 06 00
# 斷點讀值由當時 it_log.sh 的終端輸出(原始紀錄,見 _console.py)解析;每行格式見該腳本的 echo
CONSOLE = "20260930T032134_toolu_01519RpeB7CB8YBCE2fah1WV"
EXEC = {"physical 0x1548e": "physical", "spell 0x15311": "spell", "item 0x15055": "item"}


def it_log(stem: str) -> tuple[dict, dict, list, dict, dict]:
    """解析 it_log.sh 的輸出。

    評分停點(0x157fd)歸給其後第一個決策停點(0x14f62)的單位;決策停點的下一行若是執行函式停點
    (0x1548e / 0x15311 / 0x15055)即為勝者,否則為 "none"(沒有執行函式停下)。

    Returns:
        (SCORE {停點: EAX}, ACTOR {評分停點: 單位}, DECIDE [(停點, 單位, bit40, 執行函式)],
         CON_CALL {評分停點: (道具, 目標數, 目標, 施放點, slot)}, CON_DECIDE {決策停點: (P, S, I, x, y, slot, ptarget, d)})。
    """
    _, text = _console.load(stem)
    eax = {s["n"]: s["EAX"] for s in _console.stops(text) if "EAX" in s}
    ev = [(int(m[1]), m[2]) for m in re.finditer(r"(?m)^stop (\d+): (.*)$", text)]
    # 停點序號嚴格遞增 = 整段輸出來自同一次 it_log.sh 迴圈
    assert [n for n, _ in ev] == sorted({n for n, _ in ev}), stem
    score, actor, decide, con_call, con_decide, pending = {}, {}, [], {}, {}, []
    for k, (n, body) in enumerate(ev):
        if m := re.fullmatch(r"item-score EAX=[0-9A-F]+ item=(\d+) count=(\d+) ptr_ok=True targets=\[([\d, ]*)\] "
                             r"cast=\((\d+),(\d+)\) slot=(\d+)", body):
            score[n] = eax[n]
            con_call[n] = (int(m[1]), int(m[2]), [int(x) for x in m[3].split(", ") if x], (int(m[4]), int(m[5])), int(m[6]))
            pending.append(n)
        elif m := re.fullmatch(r"decide unit=(\d+) bit40=(\d+) P=(-?\d+) S=(-?\d+) I=(-?\d+) item_best=\((-?\d+),(-?\d+)\) "
                               r"slot=(-?\d+) ptarget=(-?\d+) d=(-?\d+)", body):
            actor |= {s: int(m[1]) for s in pending}
            pending = []
            nxt = ev[k + 1][1] if k + 1 < len(ev) else ""
            decide.append((n, int(m[1]), int(m[2]), EXEC[nxt[3:]] if nxt.startswith("-> ") else "none"))
            con_decide[n] = tuple(int(m[j]) for j in range(3, 11))
        else:
            # 執行函式停點只能緊接在決策停點之後
            assert body.startswith("-> ") and body[3:] in EXEC and ev[k - 1][1].startswith("decide "), body
    assert not pending, pending
    return score, actor, decide, con_call, con_decide


SCORE, ACTOR, DECIDE, CON_CALL, CON_DECIDE = it_log(CONSOLE)

pre = (D / "it_pre.bin").read_bytes()
us = []
for i in range(len(pre) // 80):
    r = pre[i * 80:(i + 1) * 80]
    w = lambda o: struct.unpack_from("<H", r, o)[0]
    us.append({"i": i, "x": r[0], "y": r[1], "f5": r[5], "side": r[6], "b34": r[0x34], "hp": w(0x40), "maxhp": w(0x42)})


def score(item: int, targets: list[int]) -> int:
    """0x15880:type 5/0xd 用 HP <= MaxHP/3 → 8、<= MaxHP/2 → 3、否則 0,+0x34 bit7 × 3;type 0x14/0x15 以法術列 +0 當數值,0x18 用 +0xe,數值 >= HP → 0x12、否則 8。"""
    it, total = ITEM[item], 0
    for t in targets:
        u = us[t]
        if it["type"] in (5, 0xD):
            s = 8 if u["hp"] <= u["maxhp"] // 3 else (3 if u["hp"] <= u["maxhp"] // 2 else 0)
            if u["b34"] & 0x80:
                s *= 3
        else:
            v = it["e"] if it["type"] == 0x18 else SPELL_VALUE[it["e"]]
            s = 0x12 if v >= u["hp"] else 8
        total += s
    return total


def candidates(actor: int, item: int) -> list[tuple]:
    """施放點 = 距施法者 <= 列 +0x10 的格(依 y 再 x);目標 = 距施放點 <= 列 +0x12、+5 bit0 清除、選擇子相符的單位(序號序)。"""
    it, a = ITEM[item], us[actor]
    sel_camp0 = it["sel11"] != 0  # mode 0:列 +0x11 為 0 → 選擇子 1(+6 != 0),否則 0(+6 == 0)
    out = []
    for y in range(21):
        for x in range(27):
            if abs(x - a["x"]) + abs(y - a["y"]) > it["range"]:
                continue
            tg = [u["i"] for u in us if not (u["f5"] & 1) and ((u["side"] == 0) == sel_camp0)
                  and abs(u["x"] - x) + abs(u["y"] - y) <= it["area"]]
            if tg:
                out.append(((x, y), tg))
    return out


mism, calls = [], []
for n in sorted(SCORE):
    b = (D / f"it_c_i1_{n}.bin").read_bytes()
    item, cnt, _ = struct.unpack_from("<III", b, 0)
    tg, pt, slot = list(b[0xC:0xC + cnt]), (b[0x4C], b[0x50]), b[0x48]
    # 終端印出的道具、目標、施放點、slot 必須等於同一停點的堆疊傾印(證明輸出與傾印是同一次執行、停點對應無誤)
    assert CON_CALL[n] == (item, cnt, tg, pt, slot), (n, CON_CALL[n])
    pred = score(item, tg)
    if pred != SCORE[n]:
        mism.append((n, SCORE[n], pred))
    calls.append({"stop": n, "actor": ACTOR[n], "item": item, "slot": slot, "cast_point": list(pt), "targets": tg,
                  "target_state": [{"unit": t, "hp": us[t]["hp"], "maxhp": us[t]["maxhp"], "b34": us[t]["b34"]} for t in tg],
                  "score_eax": SCORE[n], "score_recomputed": pred})
# 候選清單:每個施法者兩次呼叫(第一遍掃描、ai_choose_action)各自與重算相同
for actor, item in ((11, 58), (17, 38), (18, 38), (19, 38)):
    exp = [(pt, tg) for pt, tg in candidates(actor, item)]
    seq = [((c["cast_point"][0], c["cast_point"][1]), c["targets"]) for c in calls if c["actor"] == actor]
    if seq != exp + exp:
        mism.append((actor, "candidates", seq, exp))


def decide(p: int, s: int, i: int, d: int, bit: int) -> str:
    """ai_choose_action 的規則(本場景 S 都是 0)。"""
    if p < 6 and s < 6 and i < 6:
        return "none"
    if p > s and p > i:
        return "physical"
    if p == i and p > s:
        return "physical" if bit else "item"
    if s > p and s >= i:
        return "spell"
    if i > p and i > s:
        return "item"
    return "none"


decisions = []
for n, unit, bit, got in DECIDE:
    g = (D / f"it_g_i1_{n}.bin").read_bytes()
    d = struct.unpack("<i", (D / f"it_d_i1_{n}.bin").read_bytes()[:4])[0]
    v = lambda o: struct.unpack_from("<i", g, o - 0x23)[0]
    p, s, i = v(0x4F), v(0x23), v(0x33)
    # 終端印出的 P/S/I、道具勝者 (x, y, slot)、ptarget、d 必須等於同一停點的 [0x53c23..] 與堆疊傾印
    assert CON_DECIDE[n] == (p, s, i, v(0x37), v(0x3B), v(0x3F), v(0x4B), d), (n, CON_DECIDE[n])
    pred = decide(p, s, i, d, bit)
    if pred != got:
        mism.append((unit, "decide", pred, got))
    best = [c for c in calls if c["actor"] == unit]
    exp_best = None
    if best:
        top = max(c["score_eax"] for c in best)
        first = next(c for c in best if c["score_eax"] == top)  # 嚴格大於才換 → 第一個最高分
        exp_best = [top, first["cast_point"][0], first["cast_point"][1], first["slot"]]
        if exp_best != [i, v(0x37), v(0x3B), v(0x3F)]:
            mism.append((unit, "best", exp_best, [i, v(0x37), v(0x3B), v(0x3F)]))
    decisions.append({"stop": n, "unit": unit, "P": p, "S": s, "I": i, "item_best_xy_slot": [v(0x37), v(0x3B), v(0x3F)],
                      "d": d, "bit40": bit, "predicted": pred, "executor_observed": got, "item_best_predicted": exp_best})

print("calls", len(calls), "decisions", len(decisions), "mismatches", mism)
assert not mism
post = (D / "it_post.bin").read_bytes()
hp = lambda b, i: struct.unpack_from("<H", b, i * 80 + 0x40)[0]
effects = {str(i): [hp(pre, i), hp(post, i)] for i in (2, 3, 4, 13, 14, 15, 16, 18)}
EVI.write_bytes((json.dumps({
    "note": "DOSBox-X 斷點停點與單位表傾印;FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e。每個施法者的 0x1567e 被呼叫兩次(第一遍掃描與 ai_choose_action),"
            "兩次候選與分數相同。HP 效果:#16 被道具 58 補滿(10 -> 28);#2、#3 被道具 38 打掉 98、93(base 108、96,亂數沒讀);#18 的物理被 #4 反擊致死。"
            "觀察(未追):#13..#15 在敵方回合後各 +5 HP(評分當下仍是 9/14/15);敵人的道具沒有被消耗。",
    "items": ITEM, "calls": calls, "decisions": decisions, "hp_pre_post": effects,
}, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("evidence ok")
