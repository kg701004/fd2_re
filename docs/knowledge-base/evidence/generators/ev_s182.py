"""續一百八十二證據:evidence/step_unit_identity_s182_20261101.json(續一百八十一仍留:play_step_sfx 的單位索引對到哪個角色)。

使用者 2026-11-01「依照你的建議自動繼續進行處理」。沒有新實機:FD2.EXE 反組譯、FDFIELD.DAT,與續一百零七的 cl1 .. cl14 呼叫紀錄、
續一百三十一 / 續一百五十七 / 傷害測試存下的單位表。
續一百八十一寫「cl 紀錄裡找不到以單位記錄指標為參數的呼叫」是只看了腳步函式;其他函式(recalc_equipped_stats、draw_stat_bar ……)
的暫存器常指著單位記錄,32 位元組傾印含 +7 / +8 / +0x1f。
(A) 靜態:recalc_equipped_stats 第 1 個參數是單位索引(記錄 = [0x53a45] + 索引 × 0x50);play_step_sfx 以 unit_uses_move_cost_row19
    (+7 ≠ 0x1c 且(+0x20 = 0x13 或 +0x1f 為 4 / 5))選 0xa,否則依職業表 0x52725 選 9 或 0xb。
(B) 每份紀錄:
    建構 —— recalc_equipped_stats 的 esi 傾印恰等於 FDFIELD 某張圖某筆出場記錄(26 位元組 + 下一筆前 6 位元組,全部唯一),
    同一組裡「單位索引 − 記錄序號」是常數且等於該圖的己方出場數(控制段 byte 1),edx − 0x50 × 索引也是常數(= 單位表基底)。
    身分 —— 每個有腳步音的單位,在單位表基底 + 0x50 × 索引那個指標的所有傾印裡,(+7, +8, +0x1f) 有一個主導值(≥ 九成)。
    建構出來的單位 +7 = +8 = FDFIELD b1(建構函式把 b1 抄到 +7 / +8)。
    腳步音 —— 種族 4 / 5 且 +7 ≠ 0x1c 的單位只放 0xa;其他單位只放 9 / 0xb(+0x20 不在 32 位元組內,0x13 那一支另記)。
(C) 第 1 章戰場那條路線(LOAD → 城鎮 → 戰場)另有 6 份實機單位表(續一百三十一 3 份、續一百五十七 2 份、傷害測試 1 份):
    單位 0 .. 20 的 (+7, +8, +0x1f) 與 cl3 由傾印讀到的相同,單位 5 .. 20 的 +8 依序等於 FDFIELD 第 1 張記錄 0 .. 15 的 b1。
(D) 名稱:+8 < 32 是角色編號,名稱 = FDTXT_000 第 +8 + 1 句(fdtxt000_name_table 已由三個寫入端確立);
    +8 ≥ 32 套同一規則取兵種名(INFERRED,與 doc98 cl2 / cl4 記的「村民」「盜賊 #12」一致)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, _META, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("step_unit_identity_s182_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S178 = json.loads((EVIDENCE / "dig_word_order_sfx_s178_20261101.json").read_text(encoding="utf-8"))
CL = {nm: (ROOT / v["path"], v["md5"]) for nm, v in S178["calllogs"].items()}
NAMES = ROOT / "docs/data/function_names.json"
NAME_TABLE = ROOT / "docs/data/fdtxt000_name_table.json"
FLD_DIR = ROOT / "extracted/raw/FDFIELD"
STEP, PLAY_A, RECALC, ROW19 = 0x32230, 0x25A96, 0x1B750, 0x1F183
STEP_PLAY_RET = 0x3230C                     # play_step_sfx 裡 call play_sfx_a 的下一條
STRIDE = 0x50
UNIT_REGS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp")
DOMINANT = 0.9
LEADER = 0                                  # 角色 0 = 索爾(doc58 存檔名冊 record0,固定隊長)
# 第 1 章戰場路線的實機單位表(每筆 80 位元組,依索引排)
LIVE_TABLES = [".wsl_build/lc131a_moverange/D/units.bin", ".wsl_build/lc131a_moverange/E/units.bin",
               ".wsl_build/lc131a_moverange/F/units.bin", ".wsl_build/lc157_live/grey1_units.bin",
               ".wsl_build/lc157_live/grey2_units.bin", ".wsl_build/dmg/units_before.bin"]

assert hashlib.md5(_EXE).hexdigest() == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_ENT = sorted(_NM)


def func_of(a: int) -> str:
    return _NM[_ENT[bisect.bisect_right(_ENT, a) - 1]]


assert (_NM[STEP], _NM[RECALC], _NM[ROW19]) == ("play_step_sfx", "recalc_equipped_stats", "unit_uses_move_cost_row19")

# ================= (A) 靜態 =================
# recalc_equipped_stats:push ebx / esi / edi + sub esp, 0x10 之後 [esp + 0x20] = 第 1 個參數;× 0x50 加 [0x53a45]
assert [insn(a) for a in (0x1B75A, 0x1B75B, 0x1B75C, 0x1B75D, 0x1B760, 0x1B766, 0x1B76B, 0x1B76E, 0x1B774)] == [
    "push ebx", "push esi", "push edi", "sub esp, 0x10", "mov edx, dword ptr [esp + 0x20]", "shl eax, 2", "shl eax, 4",
    "mov edi, dword ptr [0x3a45]", "add edi, eax"]
# unit_uses_move_cost_row19:+7 = 0x1c 回 0;+0x20 = 0x13 或 +0x1f 為 4 / 5 回 1
assert [insn(a) for a in (0x1F1A3, 0x1F1A7, 0x1F1AA, 0x1F1AC, 0x1F1B0, 0x1F1B3, 0x1F1B5, 0x1F1B9, 0x1F1BC, 0x1F1BE, 0x1F1C1,
                          0x1F1C3, 0x1F1C9)] == [
    "movzx edx, byte ptr [eax + 7]", "cmp edx, 0x1c", "je 0x1f1c9", "movzx edx, byte ptr [eax + 0x20]", "cmp edx, 0x13",
    "je 0x1f1c3", "movzx eax, byte ptr [eax + 0x1f]", "cmp eax, 4", "je 0x1f1c3", "cmp eax, 5", "jne 0x1f1c9",
    "mov eax, 1", "xor eax, eax"]
# play_step_sfx:row19 為真 → 0xa;否則職業表 0 / 1 → 9、其餘 → 0xb(各有自己的節拍閘門)
assert [insn(a) for a in (0x3224E, 0x32252, 0x3225A, 0x3225C, 0x32280, 0x3229B, 0x322A0, 0x322A7, 0x322C7, 0x322CB,
                          0x322CE, 0x322DF, 0x322FF, 0x32307)] == [
    "push dword ptr [esp + 0x30]", "call 0x1f183", "test eax, eax", "je 0x32287", "push 0xa",
    "movzx eax, byte ptr [edx + eax + 0x20]", "movzx eax, byte ptr [esp + eax - 1]", "jne 0x322cb", "push 9",
    "cmp eax, 1", "jne 0x322e1", "jmp 0x322b8", "push 0xb", "call 0x25a96"]
# 職業表:rep movsd(ecx 個 dword)+ movsb 從 esi 抄到堆疊;esi 的立即值經 fixup 指到資料段
MOVSB = 0x3224D                                          # rep movsd 之後那一條
assert insn(0x3224B).startswith("rep movsd") and insn(MOVSB).startswith("movsb")
_FX = dl.build_fixups(_EXE, _META)
CLASS_TAB = bytes(dl.object_bytes(_EXE, _META, _FX[0x32247],
                                  4 * operand(0x3223F, "mov ecx, ") + insn(MOVSB).startswith("movsb byte")))
assert insn(0x32246) == f"mov esi, {_FX[0x32247] & 0xFFFF:#x}"
assert set(CLASS_TAB) == {0, 1, 2, 3}                    # 0 / 1 → 9,2 / 3 → 0xb(0x322a7 / 0x322cb)

# ================= FDFIELD 出場記錄 =================
_FLD = sorted(FLD_DIR.glob("FDFIELD_*.bin"))
N_MAPS = 33                                             # 每 3 個資源一張圖(parse_field.py);最後多 1 個資源
assert len(_FLD) == 3 * N_MAPS + 1, len(_FLD)
REC0 = 3 + 16 * 3 + 16 * 2 + 16 * 3                     # 控制段:3 + 回合事件 + 格子事件 + 寶箱
REC_LEN = 26
CTL = [_FLD[m * 3 + 1].read_bytes() for m in range(N_MAPS)]
REC_AT = collections.defaultdict(list)                  # 32 位元組 → [(圖, 記錄序號)]
for _m, _c in enumerate(CTL):
    for _i in range(_c[2]):
        _o = REC0 + _i * REC_LEN
        if _o + 32 <= len(_c):
            REC_AT[_c[_o:_o + 32]].append((_m, _i))


def rec_b1(m: int, i: int) -> int:
    return CTL[m][REC0 + i * REC_LEN + 1]


# ================= 名稱 =================
_NT = json.loads(NAME_TABLE.read_text(encoding="utf-8"))
assert "id + 1" in _NT["_how_it_is_used"]["index_convention"]


def name_of(key: int, constructed: bool) -> tuple[str, str]:
    """(名稱, 依據):讀檔帶進來的單位 +8 < 32 是角色編號(revival 等三個寫入端確立的規則);
    FDFIELD 建構的單位 +8 = b1,b1 當角色編號 / 兵種名都是 INFERRED(parse_field.py:b1 的身分語意未封閉)。"""
    if key < 32:
        assert str(key) in _NT["character_names_by_id"], key
        return _NT["character_names_by_id"][str(key)], ("INFERRED(FDFIELD b1 當角色編號)" if constructed
                                                        else "character id")
    assert str(key + 1) in _NT["unit_types_by_index"], key
    return _NT["unit_types_by_index"][str(key + 1)], "INFERRED(兵種名,同一規則)"


# ================= (B) 每份紀錄 =================
ROWS = []
LOGS = {}
all_plays = collections.Counter()                       # 全部 12 份裡 play_step_sfx 放的 index(含配不到單位的)
unpaired = collections.Counter()                        # 其中 play_step_sfx 已記滿、配不到單位的
for nm, (p, m5) in CL.items():
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, nm
    lg = cs._read(str(p), calls=True)
    step_calls = []                                     # (seq, 索引)
    plays = []                                          # (所屬 play_step_sfx 的 seq, 索引, 放的 index)
    cons = collections.defaultdict(list)                 # (圖, 基底) → [(索引, 記錄序號, seq)]
    step_base = collections.Counter()
    any_rec = []                                        # (基底, 索引, seq):esi 傾印是任一張圖的出場記錄
    cur = None
    for c in lg.calls:
        e = c.eip - DELTA
        if e == STEP:
            cur = (c.seq, c.stack[0])
            step_calls.append(cur)
            step_base[c.regs["esi"] - STRIDE * c.stack[0]] += 1
        elif e == PLAY_A and c.ret - DELTA == STEP_PLAY_RET:
            all_plays[c.stack[1]] += 1
            if cur is not None:                         # play_step_sfx 記滿之後的播放沒有單位可配
                plays.append((*cur, c.stack[1]))
            else:
                unpaired[c.stack[1]] += 1
            cur = None
        elif e == RECALC and c.mem.get("esi") is not None:
            hit = REC_AT.get(bytes(c.mem["esi"][:32]), [])
            if hit:                                     # 相同內容的記錄(同圖連續的同種敵兵)只用來定建構時刻
                any_rec.append((c.regs["edx"] - STRIDE * c.stack[0], c.stack[0], c.seq))
            if len(hit) == 1:
                (m, i), = hit
                cons[(m, c.regs["edx"] - STRIDE * c.stack[0])].append((c.stack[0], i, c.seq))
    steps = collections.Counter(u for _s, u in step_calls)
    assert steps, nm
    # 建構組:索引 − 記錄序號 = 常數 = 該圖己方出場數
    groups = []
    for (m, base), v in sorted(cons.items()):
        ks = {u - i for u, i, _s in v}
        assert len(ks) == 1, (nm, m, hex(base), ks)
        k = ks.pop()
        assert k == CTL[m][1], (nm, m, k, CTL[m][1])
        groups.append({"map": m, "unit_base": base, "own_deploy": k, "records": sorted({i for _u, i, _s in v}),
                       "seq": [min(s for *_x, s in v), max(s for *_x, s in v)]})
    # 每個基底的有效區間:從上一個基底換過來(第一個從 0)到下一個不同基底開始建構。
    # 己方單位在讀檔時就在表裡(城鎮走路也用同一張表),FDFIELD 單位另從自己那次建構起算(born)。
    first = {}
    for g in groups:
        first[g["unit_base"]] = min(first.get(g["unit_base"], g["seq"][0]), g["seq"][0])
    order = sorted(first, key=first.get)
    win = {b: (first[b] if k else 0, first[order[k + 1]] if k + 1 < len(order) else float("inf"))
           for k, b in enumerate(order)}
    # 沒有建構的紀錄(cl1 = CONTINUE 讀進戰場):基底取 play_step_sfx 呼叫端 esi − 0x50 × 索引,須九成以上一致,區間 = 整份
    (sb, sn), = step_base.most_common(1)
    if not win:
        assert sn >= DOMINANT * sum(steps.values()), (nm, hex(sb), sn)
        win = {sb: (0, float("inf"))}
    bases = set(win)

    def base_at(seq: int, _nm: str = nm, _win: dict = win) -> int:
        """seq 落在哪個單位表基底的有效區間(恰一個)。"""
        hit = [b for b, (lo, hi) in _win.items() if lo <= seq < hi]
        assert len(hit) == 1, (_nm, seq, hit)
        return hit[0]

    def phase(seq: int, b: int, _first: dict = first) -> str:
        """建構那張圖之前(讀檔後的城鎮)或之後(戰場)。"""
        return "battle" if seq >= _first.get(b, 0) else "before_construction"

    by_bu = collections.Counter((base_at(s), u) for s, u in step_calls)
    by_phase = collections.Counter((base_at(s), u, phase(s, base_at(s))) for s, u in step_calls)
    played = collections.defaultdict(collections.Counter)
    for s, u, ix in plays:
        played[(base_at(s), u)][ix] += 1
    want = {b + STRIDE * u: (b, u) for b, u in by_bu}
    # 第 0 格:讀檔帶進來的表必須是固定隊長;只看建構之後(CONTINUE 從第一次腳步起),之前那塊記憶體可能還是開機 / 標題的資料
    lead_lo = {b: first.get(b, min((s for s, _u in step_calls if base_at(s) == b), default=0)) for b in bases}
    lead = collections.defaultdict(collections.Counter)
    # 由 FDFIELD 建構的單位從它自己那次建構起算(之前那一格還沒寫)
    born = {}
    for b, u, s in any_rec:
        if b in win:
            born.setdefault((b, u), s)
    tup = collections.defaultdict(collections.Counter)  # (基底, 索引) → (+7, +8, +0x1f) 次數
    for c in lg.calls:
        for r in UNIT_REGS:
            b = c.mem.get(r)
            if c.regs[r] in lead_lo and b is not None and len(b) >= 32 \
                    and lead_lo[c.regs[r]] <= c.seq < win[c.regs[r]][1]:
                lead[c.regs[r]][(b[7], b[8], b[0x1F])] += 1
            hit = want.get(c.regs[r])
            if hit and b is not None and len(b) >= 32 \
                    and max(win[hit[0]][0], born.get(hit, 0)) <= c.seq < win[hit[0]][1]:
                tup[hit][(b[7], b[8], b[0x1F])] += 1
    # doc58:存檔名冊 record0 = 索爾(角色 0,固定隊長);己方由讀檔帶進來的表(己方出場數 > 0 或 CONTINUE),第 0 格 +8 = 0
    for b in bases:
        if not any(g["unit_base"] == b and g["own_deploy"] == 0 for g in groups):
            (_t0, n0), = lead[b].most_common(1)
            assert _t0[1] == LEADER and n0 >= DOMINANT * sum(lead[b].values()), (nm, hex(b), lead[b].most_common(3))
    for (b, u), n_calls in sorted(by_bu.items()):
        obs = tup.get((b, u), collections.Counter())
        assert obs, (nm, hex(b), u)
        (t7, t8, race), n = obs.most_common(1)[0]
        assert n >= DOMINANT * sum(obs.values()), (nm, hex(b), u, obs.most_common(3))
        # 同一基底的建構組:索引 ≥ 己方出場數的是 FDFIELD 第 索引 − 己方數 筆(含內容重複、沒能唯一比對的那些)
        src = sorted({(g["map"], u - g["own_deploy"]) for g in groups if g["unit_base"] == b
                      and 0 <= u - g["own_deploy"] < CTL[g["map"]][2]})
        assert len(src) <= 1, (nm, u, src)
        # 同基底有建構組、索引落在己方之後:一定是某筆 FDFIELD 記錄
        assert bool(src) == any(g["unit_base"] == b and u >= g["own_deploy"] for g in groups), (nm, hex(b), u, src)
        for m, i in src:                               # 建構出來的:+7 = +8 = FDFIELD b1
            assert t7 == t8 == rec_b1(m, i), (nm, u, m, i, t7, t8, rec_b1(m, i))
            assert (b, u) in born, (nm, hex(b), u)
        idx = played.get((b, u), collections.Counter())
        row19 = t7 != 0x1C and race in (4, 5)
        if row19:
            assert set(idx) <= {0xA}, (nm, u, idx)
        else:
            assert set(idx) <= {9, 0xB, 0xA}, (nm, u, idx)
            assert 0xA not in idx, (nm, u, idx, "+0x20 = 0x13 那一支,本資料沒有")
        nmx, conf = name_of(t8, bool(src))
        scene = ",".join(sorted({f"map{g['map']}" for g in groups if g["unit_base"] == b})) or "continue"
        _ph = {p: k for (b2, u2, p), k in by_phase.items() if (b2, u2) == (b, u)}
        assert sum(_ph.values()) == n_calls
        ROWS.append({"log": nm, "scene": scene, "unit_base": hex(b), "unit": u, "step_calls": n_calls,
                     "step_calls_by_phase": dict(sorted(_ph.items())),
                     "played": {hex(k): v for k, v in sorted(idx.items())},
                     "plus7": t7, "plus8": t8, "race": race, "dominant_share": round(n / sum(obs.values()), ndigits=4),
                     "fdfield": [{"map": m, "record": i} for m, i in src], "name": nmx, "name_basis": conf,
                     "row19": row19})
    LOGS[nm] = {"calllog": rel(p), "md5": m5, "unit_bases": sorted(hex(b) for b in bases), "construction": groups,
                "step_units": dict(sorted(steps.items()))}
    LOGS[nm]["construction"] = [{**g, "unit_base": hex(g["unit_base"])} for g in groups]

N_STEP = sum(sum(v["step_units"].values()) for v in LOGS.values())
assert N_STEP == sum(r["step_calls"] for r in ROWS)
# 與續一百八十的獨立讀法對照:每個單位索引的呼叫次數(ev_s180b)、每個 index 的放音次數(ev_s180 cl_plays)
_S180B = json.loads((EVIDENCE / "sfx_dialogue_step_s180b_20261101.json").read_text(encoding="utf-8"))
_by_u = collections.Counter()
for _r in _S180B["step"]["rows"]:
    _by_u[_r["unit"]] += _r["calls"]
_mine = collections.Counter()
for _v in LOGS.values():
    _mine.update(_v["step_units"])
assert _mine == _by_u, (_mine, _by_u)
_S180 = json.loads((EVIDENCE / "sfx_ui_pool_table_s180_20261101.json").read_text(encoding="utf-8"))
assert {ix: _S180["ui_pool"][str(ix) if ix < 10 else hex(ix)].get("cl_plays", 0) for ix in (9, 0xA, 0xB)} == \
    {ix: all_plays[ix] for ix in (9, 0xA, 0xB)} and set(all_plays) <= {9, 0xA, 0xB}, all_plays
_paired = collections.Counter()
for _r in ROWS:
    _paired.update({int(k, 16): v for k, v in _r["played"].items()})
assert _paired + unpaired == all_plays, (_paired, unpaired, all_plays)
N_PLAYED = sum(sum(r["played"].values()) for r in ROWS)
assert N_PLAYED > 0 and any(r["row19"] and r["played"] for r in ROWS) and any(not r["row19"] and r["played"] for r in ROWS)

# ================= (C) 第 1 章戰場路線的實機單位表 =================
_ch1 = collections.defaultdict(set)
for r in ROWS:
    if r["scene"] == "map1":
        _ch1[r["unit"]].add((r["plus7"], r["plus8"], r["race"]))
assert _ch1 and all(len(v) == 1 for v in _ch1.values()), _ch1
CH1 = {u: next(iter(v)) for u, v in _ch1.items()}
LIVE = {}
for f in LIVE_TABLES:
    b = (ROOT / f).read_bytes()
    assert len(b) % STRIDE == 0 and len(b) // STRIDE >= 21, f
    t = [(b[u * STRIDE + 7], b[u * STRIDE + 8], b[u * STRIDE + 0x1F]) for u in range(21)]
    assert all(t[u] == CH1[u] for u in CH1), (f, [(u, t[u], CH1[u]) for u in CH1 if t[u] != CH1[u]])
    assert [x[1] for x in t[5:21]] == [rec_b1(1, i) for i in range(16)], f
    LIVE[f] = {"md5": hashlib.md5(b).hexdigest(), "plus8_0_20": [x[1] for x in t]}
assert len({tuple(v["plus8_0_20"]) for v in LIVE.values()}) == 1
OWN1 = CTL[1][1]
assert OWN1 == len(LIVE[LIVE_TABLES[0]]["plus8_0_20"]) - 16
# 名稱規則的獨立對照:doc98 cl4 那列(續一百零八,當時看畫面寫的)「索爾物理攻擊盜賊 #12」
_CL4 = next(ln for ln in (ROOT / "docs/knowledge-base/98-tooling-infrastructure.md").read_text(encoding="utf-8").splitlines()
            if ln.startswith("| cl4 |"))
assert "索爾物理攻擊盜賊 #12" in _CL4
assert name_of(LIVE[LIVE_TABLES[0]]["plus8_0_20"][12], True)[0] == "盜賊"
assert name_of(LIVE[LIVE_TABLES[0]]["plus8_0_20"][0], False)[0] == "索爾"

# ================= 彙整:同一場景同一索引 = 同一角色 =================
BY_UNIT = collections.defaultdict(set)
for r in ROWS:
    BY_UNIT[(r["scene"], r["unit"])].add((r["plus8"], r["name"], r["name_basis"]))
assert all(len(v) == 1 for v in BY_UNIT.values()), {k: v for k, v in BY_UNIT.items() if len(v) != 1}
SUMMARY = [{"scene": s, "unit": u, "plus8": next(iter(v))[0], "name": next(iter(v))[1], "name_basis": next(iter(v))[2],
            "logs": sorted({r["log"] for r in ROWS if (r["scene"], r["unit"]) == (s, u)}),
            "step_calls": sum(r["step_calls"] for r in ROWS if (r["scene"], r["unit"]) == (s, u))}
           for (s, u), v in sorted(BY_UNIT.items())]
assert sum(x["step_calls"] for x in SUMMARY) == N_STEP
assert all((r["plus8"], r["name"]) == (x["plus8"], x["name"]) for x in SUMMARY for r in ROWS
           if (r["scene"], r["unit"]) == (x["scene"], x["unit"]))

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s182.py"), "exe_md5": MD5,
    "class_step_sfx_table_0x52725": CLASS_TAB.hex(),
    "logs": LOGS, "rows": ROWS, "summary": SUMMARY, "live_tables_ch1": LIVE,
    "conclusion": f"cl1 .. cl14 的 {N_STEP} 次 play_step_sfx 全部由紀錄本身的單位記錄傾印對到角色({len(SUMMARY)} 個「場景 × 索引」),"
                  f"其中 {N_PLAYED} 次放音的 index 都符合 unit_uses_move_cost_row19 與職業表的預測;建構出來的單位 +7 = +8 = FDFIELD b1,"
                  "第 1 章戰場另與 6 份實機單位表逐筆相同。續一百八十一「cl 紀錄裡沒有單位記錄指標」是只看腳步函式的錯誤。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, len(ROWS), N_STEP, N_PLAYED)
for x in SUMMARY:
    print(x)
