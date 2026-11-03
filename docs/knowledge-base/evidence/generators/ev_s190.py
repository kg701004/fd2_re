"""續一百九十證據:evidence/step_sfx_0xb_s190_20261104.json(91-worklist「UI 音效 index 2-0xb 語意畫面實測」剩下的 0xb)。

使用者 2026-11-04「依照你的建議自動繼續進行處理」。沒有新實機:FD2.EXE 反組譯、續一百八十四的 lc184a / lc184b 呼叫紀錄
與當下 debugger 讀出的單位表(drivers_s184)。
doc36 的 0xb 列一直是 STATIC ANALYSIS:cl1 .. cl14 沒有一次 0xb(續一百八十二:那些單位都不是步態 2 / 3 的職業)。
(A) 靜態:play_step_sfx 先問 unit_uses_move_cost_row19(真 → 0xa、每 6 步),否則以職業表 0x52725[+0x20 − 1] 分
    0 → 9 每 6 步、1 → 9 每 4 步、其他 → 0xb 每 9 步;「步」是全域計數器 [0x54132] 除以週期的餘數,每次呼叫結尾 +1。
    整個 image 引用 [0x54132] 的 fixup 恰 5 處(4 讀 1 加),沒有別的寫入端;它在 obj2 沒有實體頁的 zero-fill 尾段,開機為 0。
(B) lc184a(新遊戲開場 → 第 0 張圖):每次 play_step_sfx 歸到當時的單位表(recalc_equipped_stats 的 edx − 0x50 × 索引,
    與 debugger 讀出的三張表同基底),以那張表的單位記錄逐次預測放不放、放哪個 index:起始值 0 時 636 次全中,
    其他 255 個起始值都有錯,所以計數器真的從 0 起、沒有別人改。三個對照(不看職業表 / 0xb 那支放 9 / 每個單位各自計數)都不符。
    6 次 0xb 全是 +8 = 4(亞雷斯)、職業 3(騎士)的單位走路。
(C) lc184b(測試存檔 → 城鎮 → 第 1 張圖):90 次同一個模型也全中(含 0xa 那支),但只有 90 次、起始值不唯一,只算相容。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, _META, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("step_sfx_0xb_s190_20261104.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
RAW = ROOT / ".wsl_build/lc184_live"
S184 = json.loads((EVIDENCE / "live_checks_s184_20261102.json").read_text(encoding="utf-8"))
NAMES = ROOT / "docs/data/function_names.json"
NAME_TABLE = ROOT / "docs/data/fdtxt000_name_table.json"
STEP, PLAY_A, RECALC, ROW19 = 0x32230, 0x25A96, 0x1B750, 0x1F183
STEP_PLAY_RET = 0x3230C                     # play_step_sfx 裡 call play_sfx_a 的下一條
COUNTER = 0x54132
STRIDE = 0x50
GLOBALS_LIN, PTR_UNITS, CNT_UNITS = 0x53A40, 0x53A45, 0x53BEB
# 續一百八十四當下讀出的記憶體(與 ev_s184 的 DUMPS 同一批檔案):(全域, 單位表) → 第幾張圖
DUMPS = {("lc184a", "m01_globals"): "de6ec79aa667a19a0518cfefed5ac4d5", ("lc184a", "m02_units"): "cc2db2c6dbb01c5ab36a1df2dd824e3a",
         ("lc184a", "m05_globals"): "6a1ae6aa4cc4c474a2aaef58683fe988", ("lc184a", "m06_units"): "339839c877922c1b20bdff23fb6d06c5",
         ("lc184a", "m07_globals"): "5b82eba2a83021df2d13c3d4bf839175", ("lc184a", "m08_units"): "7b8b5f961d853048cba9c736f5b0c3c5",
         ("lc184b", "m01_globals"): "bf8a49266f939927d622763b9caf3fea", ("lc184b", "m02_units"): "41bf6f5a4e7428bd3bd9f180f19be9df"}
TABLE_DUMPS = {"lc184a": [("m01_globals", "m02_units", 32), ("m05_globals", "m06_units", 31), ("m07_globals", "m08_units", 0)],
               "lc184b": [("m01_globals", "m02_units", 1)]}
N_START = 256                               # [0x54132] 是 byte

assert hashlib.md5(_EXE).hexdigest() == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
assert (_NM[STEP], _NM[RECALC], _NM[ROW19]) == ("play_step_sfx", "recalc_equipped_stats", "unit_uses_move_cost_row19")

# ================= (A) 靜態 =================
# 分支:row19 → 0xa;否則職業表值 0 → 9、1 → 9(週期不同)、其他 → 0xb;三支都落到 0x32301 的共用尾端
assert [insn(a) for a in (0x32252, 0x3225A, 0x3225C, 0x3229B, 0x322A0, 0x322A5, 0x322A7, 0x322CB, 0x322CE, 0x322DF,
                          0x32282, 0x322C9, 0x32307, 0x3230F)] == [
    "call 0x1f183", "test eax, eax", "je 0x32287", "movzx eax, byte ptr [edx + eax + 0x20]",
    "movzx eax, byte ptr [esp + eax - 1]", "test eax, eax", "jne 0x322cb", "cmp eax, 1", "jne 0x322e1", "jmp 0x322b8",
    "jmp 0x32301", "jmp 0x32301", "call 0x25a96", "inc byte ptr [0x4132]"]
# 每一支:讀計數器 → 除以週期 → 餘數非 0 跳過放音(仍到 0x3230f 加 1)
for rd, skip in ((0x3225E, 0x32278), (0x322A9, 0x322C3), (0x322E1, 0x322FB)):
    assert insn(rd) == "movzx edx, byte ptr [0x4132]" and insn(skip) == "jne 0x3230f", hex(rd)
assert insn(0x322D0) == "movzx edx, byte ptr [0x4132]"
P_ROW19 = operand(0x32265, "mov dword ptr [esp + 0x20], ")
P_G0 = operand(0x322B0, "mov dword ptr [esp + 0x20], ")
P_G1 = operand(0x322D7, "mov dword ptr [esp + 0x20], ")
P_G23 = operand(0x322E8, "mov dword ptr [esp + 0x20], ")
IX_ROW19, IX_G01, IX_G23 = operand(0x32280, "push "), operand(0x322C7, "push "), operand(0x322FF, "push ")
assert (P_ROW19, P_G0, P_G1, P_G23, IX_ROW19, IX_G01, IX_G23) == (6, 6, 4, 9, 0xA, 9, 0xB)
# 職業表:rep movsd(ecx 個 dword)+ movsb 從 esi 抄到堆疊;esi 的立即值經 fixup 指到資料段(與 ev_s182 同一讀法)
_FX = dl.build_fixups(_EXE, _META)
assert insn(0x3224B).startswith("rep movsd") and insn(0x3224D).startswith("movsb byte")
CLASS_TAB = bytes(dl.object_bytes(_EXE, _META, _FX[0x32247], 4 * operand(0x3223F, "mov ecx, ") + 1))
assert insn(0x32246) == f"mov esi, {_FX[0x32247] & 0xFFFF:#x}" and len(CLASS_TAB) == 29
PERIOD9_CLASSES = [c for c in range(1, len(CLASS_TAB) + 1) if CLASS_TAB[c - 1] >= 2]
_CN = json.loads(NAME_TABLE.read_text(encoding="utf-8"))
assert "+ 0x96" in _CN["_class_name_index_convention"]["rule"]
CLASS_NAME = _CN["player_class_names_by_id"]
CHAR_NAME = _CN["character_names_by_id"]
assert PERIOD9_CLASSES == [3, 11, 15, 19], PERIOD9_CLASSES
# 計數器:整個 image 指到 0x54132 的 fixup 恰是上面 4 讀 1 加(movzx edx, [disp32] 的 disp 在 +3;inc byte [disp32] 在 +2)
COUNTER_SITES = sorted(a for a, t in _FX.items() if t == COUNTER)
assert COUNTER_SITES == [0x3225E + 3, 0x322A9 + 3, 0x322D0 + 3, 0x322E1 + 3, 0x3230F + 2], [hex(a) for a in COUNTER_SITES]
# 在 obj2 有實體頁的範圍之後、vsize 之內 = loader 補 0 的尾段 → 開機值 0
(_OBJ,) = [o for o in _META["objs"] if o["base"] <= COUNTER < o["base"] + o["vsize"]]
assert _OBJ["base"] + _OBJ["pages"] * _META["page_size"] <= COUNTER, _OBJ
C0_STATIC = 0


def predict(rec: bytes, ctr: int, tab: bytes = CLASS_TAB, ix23: int = IX_G23) -> int | None:
    """play_step_sfx 對單位記錄 rec、計數器值 ctr 會放的 index(不放回 None)。"""
    if rec[7] != 0x1C and (rec[0x20] == 0x13 or rec[0x1F] in (4, 5)):     # unit_uses_move_cost_row19
        ix, per = IX_ROW19, P_ROW19
    else:
        assert 1 <= rec[0x20] <= len(tab), rec[0x20]
        g = tab[rec[0x20] - 1]
        ix, per = (IX_G01, P_G0) if g == 0 else (IX_G01, P_G1) if g == 1 else (ix23, P_G23)
    return ix if ctr % per == 0 else None


def mismatches(calls: list, c0: int, per_unit: bool = False, **kw) -> int:
    """以起始值 c0 逐次模擬,預測與紀錄不同的次數;per_unit = 每個單位各自一個計數器(對照)。"""
    ctr = collections.defaultdict(lambda: c0)
    bad = 0
    for _s, key, rec, played in calls:
        k = key if per_unit else None
        bad += predict(rec, ctr[k], **kw) != played
        ctr[k] = (ctr[k] + 1) & 0xFF
    return bad


# ================= (B)(C) 每份紀錄 =================
def blob(log: str, label: str) -> bytes:
    b = (RAW / "cl" / log / f"{label}.bin").read_bytes()
    assert hashlib.md5(b).hexdigest() == DUMPS[(log, label)], (log, label)
    return b


LOGS = {}
PLAYS_0XB = []
for log, dumps in TABLE_DUMPS.items():
    run = S184["runs"][log]
    p = ROOT / run["calllog"]
    assert hashlib.md5(p.read_bytes()).hexdigest() == run["md5"], log
    with open(p, encoding="ascii") as f:
        head = f.readline().split()
    cap = int(next(x for x in head if x.startswith("cap=")).split("=")[1])
    tables = {}
    for g, u, m in dumps:
        gb, ub = blob(log, g), blob(log, u)
        base = int.from_bytes(gb[PTR_UNITS - GLOBALS_LIN:PTR_UNITS - GLOBALS_LIN + 4], "little")
        n = gb[CNT_UNITS - GLOBALS_LIN]
        _lt = S184["live_tables"][f"{log}/map{m}"]
        assert len(ub) >= n * STRIDE and (_lt["unit_base"], _lt["units"]) == (hex(base), n), (log, m)
        tables[base] = {"map": m, "units": n, "bytes": ub}
    lg = cs._read(str(p), calls=True)
    first = {}                                  # 基底 → 第一次 recalc_equipped_stats(建構那張圖)
    seqs = []                                   # (類, seq, 值):play_step_sfx 進入(單位索引)/ 它呼叫 play_sfx_a(index)
    for c in lg.calls:
        e = c.eip - DELTA
        if e == RECALC and c.regs["edx"] - STRIDE * c.stack[0] in tables:
            first.setdefault(c.regs["edx"] - STRIDE * c.stack[0], c.seq)
        if e == STEP:
            seqs.append(("step", c.seq, c.stack[0]))
        elif e == PLAY_A and not c.ret_bad and c.ret - DELTA == STEP_PLAY_RET:
            assert c.stack[2] == 1, (log, c.seq)                             # push 1(三支都一樣)
            seqs.append(("play", c.seq, c.stack[1]))
    n_step = sum(k == "step" for k, *_x in seqs)
    assert 0 < n_step < cap, (log, n_step, cap)                             # 入口沒記滿:每一次呼叫都在
    # 每次放音緊接在一次 play_step_sfx 進入之後(同一次呼叫裡)
    assert all(seqs[i - 1][0] == "step" for i, x in enumerate(seqs) if x[0] == "play") and seqs[0][0] == "step", log
    assert set(first) == set(tables), (log, [hex(b) for b in first])
    order = sorted(first, key=first.get)

    def base_at(seq: int, _order: list = order, _first: dict = first) -> int:
        """seq 那時的單位表:最近一次建構的那張;第一次建構之前(讀檔後的城鎮)只能是唯一那張表。"""
        hit = [b for b in _order if _first[b] <= seq]
        if not hit:
            assert len(_order) == 1, seq
            return _order[0]
        return hit[-1]

    calls = []                                  # (seq, (基底, 索引), 單位記錄, 放的 index 或 None)
    for i, (k, s, v) in enumerate(seqs):
        if k == "step":
            b = base_at(s)
            assert v < tables[b]["units"], (log, s, v)
            nxt = seqs[i + 1] if i + 1 < len(seqs) else None
            calls.append((s, (b, v), tables[b]["bytes"][v * STRIDE:(v + 1) * STRIDE],
                          nxt[2] if nxt and nxt[0] == "play" else None))
    before = sum(s < min(first.values()) for s, *_x in calls)
    fit = [c0 for c0 in range(N_START) if mismatches(calls, c0) == 0]
    assert C0_STATIC in fit, (log, fit[:8])
    # 對照:不看職業表(全當步態 1)、0xb 那支改放 9、每個單位各自計數 —— 都必須有錯
    nulls = {"no_class_table": mismatches(calls, C0_STATIC, tab=bytes([1]) * len(CLASS_TAB)),
             "period9_plays_9": mismatches(calls, C0_STATIC, ix23=IX_G01),
             "per_unit_counter": mismatches(calls, C0_STATIC, per_unit=True)}
    played = collections.Counter(p for *_x, p in calls if p is not None)
    by_unit = collections.defaultdict(collections.Counter)
    for _s, (b, u), rec, p in calls:
        by_unit[(b, u)]["steps"] += 1
        if p is not None:
            by_unit[(b, u)][hex(p)] += 1
    units = []
    for (b, u), cnt in sorted(by_unit.items(), key=lambda kv: (tables[kv[0][0]]["map"], kv[0][1])):
        rec = tables[b]["bytes"][u * STRIDE:(u + 1) * STRIDE]
        units.append({"map": tables[b]["map"], "unit_base": hex(b), "unit": u, "plus7": rec[7], "plus8": rec[8],
                      "race_plus1f": rec[0x1F], "class_plus20": rec[0x20], "class_tab": CLASS_TAB[rec[0x20] - 1],
                      "row19": predict(rec, 0) == IX_ROW19, **dict(cnt)})
    for s, (b, u), rec, p in calls:
        if p == IX_G23:
            PLAYS_0XB.append({"log": log, "seq": s, "map": tables[b]["map"], "unit": u, "plus8": rec[8],
                              "class_plus20": rec[0x20]})
    LOGS[log] = {"calllog": run["calllog"], "md5": run["md5"], "cap": cap, "step_calls": n_step,
                 "step_calls_before_first_construction": before, "plays": {hex(k): v for k, v in sorted(played.items())},
                 "start_values_fitting": fit if len(fit) <= 32 else f"{len(fit)} 個", "n_start_values_fitting": len(fit),
                 "nulls_mismatches_at_c0": nulls, "units": units,
                 "tables": {hex(b): {"map": t["map"], "units": t["units"], "first_recalc_seq": first[b]} for b, t in tables.items()}}

A, B = LOGS["lc184a"], LOGS["lc184b"]
# lc184a:起始值唯一 = 靜態的 0;三個對照都錯
assert A["n_start_values_fitting"] == 1 and A["start_values_fitting"] == [C0_STATIC], A["start_values_fitting"]
assert all(v > 0 for v in A["nulls_mismatches_at_c0"].values()), A["nulls_mismatches_at_c0"]
assert A["step_calls_before_first_construction"] == 0
# 0xb:lc184a 6 次,全是亞雷斯(角色 4)、騎士(職業 3);lc184b 沒有
assert A["plays"].get(hex(IX_G23)) == 6 and hex(IX_G23) not in B["plays"], (A["plays"], B["plays"])
assert A["nulls_mismatches_at_c0"]["period9_plays_9"] == 6
assert {(x["plus8"], x["class_plus20"]) for x in PLAYS_0XB} == {(4, 3)}, PLAYS_0XB
assert sorted({x["map"] for x in PLAYS_0XB}) == [31, 32]
assert CHAR_NAME["4"] == "亞雷斯" and CLASS_NAME["3"] == "騎士"
# lc184b:相容(起始值 0 全中、含 0xa),但起始值不唯一
assert B["n_start_values_fitting"] > 1 and B["plays"].get(hex(IX_ROW19), 0) > 0
assert {k for L in LOGS.values() for k in L["plays"]} == {hex(9), hex(0xA), hex(0xB)}

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s190.py"), "exe_md5": MD5,
    "static": {"periods": {"row19_0xa": P_ROW19, "class_tab_0_index9": P_G0, "class_tab_1_index9": P_G1,
                           "class_tab_2_3_index0xb": P_G23},
               "class_step_sfx_table_0x52725": CLASS_TAB.hex(),
               "period9_classes": {str(c): CLASS_NAME[str(c)] for c in PERIOD9_CLASSES},
               "counter": {"addr": hex(COUNTER), "fixup_sites": [hex(a) for a in COUNTER_SITES],
                           "zero_fill_tail_of_obj": hex(_OBJ["base"]), "boot_value": C0_STATIC}},
    "logs": LOGS, "plays_0xb": PLAYS_0XB,
    "conclusion": f"lc184a 的 {A['step_calls']} 次 play_step_sfx 以當時單位表逐次預測全中(起始值只有 0 成立,與 zero-fill 一致),"
                  f"6 次 0xb 全是亞雷斯(騎士)在第 32 / 31 張圖走路;0xb = 職業 3 / 11 / 15 / 19"
                  f"({' / '.join(CLASS_NAME[str(c)] for c in PERIOD9_CLASSES)})每 9 步的腳步音。lc184b 的 {B['step_calls']} 次也相容。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, A["step_calls"], A["plays"], A["nulls_mismatches_at_c0"], B["step_calls"], B["plays"], B["n_start_values_fitting"])
