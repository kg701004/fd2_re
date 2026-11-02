"""續一百八十四證據:evidence/live_checks_s184_20261102.json(實機 lc184a / lc184b;預測 drivers_s184/pred184.txt)。

使用者 2026-11-02「請全部實機執行進行確認」:續一百八十一 .. 一百八十三的三項仍留。
lc184a 開新遊戲,逐鍵推進開場(第 32 張圖 → 第 31 張圖)到第 0 張圖可操作;lc184b 測試存檔 slot 0 章節改 1 → 城鎮 → 第 1 張圖戰場。
呼叫紀錄入口全部 1356 個(CAP 3000、DUMP 32),加觸發擷取 ng:375,ng:302-303;單位表在當下以 debugger 讀出(不改記憶體)。
Q1 b1 48 / 66 / 75:當下單位表 +8 = FDFIELD b1;draw_unit_panel 畫出的單位(子函式承接的 esi 定基底)與畫名字的字串。
Q2 375:同 ev_s181b 的 P1 / P2 / P4。
Q3 index 1 / 8 / 5 / 6 / 0xc:每次播放落在哪個函式、前一個按鍵、同一次呼叫裡的其他結果(unit_list_bits_1a、yes_no_prompt)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("live_checks_s184_20261102.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
RAW = ROOT / ".wsl_build/lc184_live"
DRV = GEN_DIR / "drivers_s184"
PRED = DRV / "pred184.txt"
NAMES = ROOT / "docs/data/function_names.json"
FLD_DIR = ROOT / "extracted/raw/FDFIELD"
FDTXT0 = ROOT / "extracted/raw/FDTXT/FDTXT_000.bin"
S181 = json.loads((EVIDENCE / "sfx_ui_semantics_s181_20261101.json").read_text(encoding="utf-8"))
S183 = json.loads((EVIDENCE / "unit_name_key_s183_20261101.json").read_text(encoding="utf-8"))
# teardown 之後的指紋(lc184.py down 印出)
LOG_MD5 = {"lc184a": "dcbf7cf1a6f579616cb5a709493019f6", "lc184b": "2fa8a9e680dfc234af04af430f181213"}
TRIG = "ng:375,ng:302-303"
CAP = 3000
MDI_FROM, MDI_BACK = (0x80, 0xED6), 0x3F1A4
PLAY_A, PLAY_B = 0x25A96, 0x25B45
PANEL, DLG, NAME_RET = 0x18C6D, 0x15F84, 0x18D84
ESI_SET, PANEL_END = 0x18C96, 0x18D8C
STRIDE = 0x50
UNIT_ARG = 2                                   # draw_unit_panel (dst, stride, unit):第 3 個參數(續一百八十三)
KEY_RETURN = 0x1C                              # K 紀錄:Return 按下的掃描碼
# 當下讀出的記憶體(lc184.py mem;0170:0x1efa40 起 0x200 位元組 = 0x53a40 起的全域、單位表)與按鍵截圖
DUMPS = {("lc184a", "m01_globals"): "de6ec79aa667a19a0518cfefed5ac4d5", ("lc184a", "m02_units"): "cc2db2c6dbb01c5ab36a1df2dd824e3a",
         ("lc184a", "m05_globals"): "6a1ae6aa4cc4c474a2aaef58683fe988", ("lc184a", "m06_units"): "339839c877922c1b20bdff23fb6d06c5",
         ("lc184a", "m07_globals"): "5b82eba2a83021df2d13c3d4bf839175", ("lc184a", "m08_units"): "7b8b5f961d853048cba9c736f5b0c3c5",
         ("lc184b", "m01_globals"): "bf8a49266f939927d622763b9caf3fea", ("lc184b", "m02_units"): "41bf6f5a4e7428bd3bd9f180f19be9df"}
SHOTS = {("lc184a", "a01_start"): "335c7f327744e72cac5913c35e18645a", ("lc184a", "d01_ring_open"): "95d76b9eb8216d1b49b6375b5dc346df",
         ("lc184a", "d02_ring_close"): "957d951de6e40ba61e175ef1f4ebde38", ("lc184a", "e02_card_open"): "76915ecb30a7d94a758f904b5d8d3ea8",
         ("lc184a", "e03_card_key"): "91ead557f4dfb3558967bccea6b10094", ("lc184b", "g01_town_ret"): "d30e43802167160f758a7c974dde6a80",
         ("lc184b", "g03_wait"): "0b87f5a49bb4f7588ab8a5c5b1e8ac8a", ("lc184b", "n02_rest"): "e3d720f8e79fa3fc8c39ee7282df2b20",
         ("lc184b", "n03_yes"): "2a78a39ec6b0378145cc3d8a1ef44296"}
GLOBALS_LIN = 0x53A40
PTR_UNITS, CNT_UNITS = 0x53A45, 0x53BEB        # [0x53a45] 單位表指標、[0x53beb] 單位數

assert hashlib.md5(_EXE).hexdigest() == MD5
assert f"TRIG={TRIG}" in PRED.read_text(encoding="utf-8") and f'TRIG = "{TRIG}"' in (DRV / "lc184.py").read_text(encoding="utf-8")
assert f'"FD2_HARNESS_CALLLOG_CAP"] = "{CAP}"' in (DRV / "lc184.py").read_text(encoding="utf-8")
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_BY = {v: k for k, v in _NM.items()}
assert _NM[PANEL] == "draw_unit_panel" and insn(NAME_RET - 5) == f"call {DLG:#x}" and insn(ESI_SET) == "add esi, eax"


def blob(log: str, label: str, table: dict, ext: str) -> bytes:
    b = (RAW / "cl" / log / f"{label}.{ext}").read_bytes()
    assert hashlib.md5(b).hexdigest() == table[(log, label)], (log, label)
    return b


SHOT_MD5 = {f"{lg}/{lb}": hashlib.md5(blob(lg, lb, SHOTS, "png")).hexdigest() for lg, lb in SHOTS}

# ================= FDFIELD 出場記錄(與 ev_s183 同一讀法) =================
_FLD = sorted(FLD_DIR.glob("FDFIELD_*.bin"))
REC0 = 3 + 16 * 3 + 16 * 2 + 16 * 3
REC_LEN = 26
CTL = {m: _FLD[m * 3 + 1].read_bytes() for m in (0, 1, 31, 32)}


def rec_b1(m: int, i: int) -> int:
    return CTL[m][REC0 + i * REC_LEN + 1]


# ================= Q1 當下單位表 =================
def live_table(log: str, g: str, u: str) -> tuple[int, int, bytes]:
    gb = blob(log, g, DUMPS, "bin")
    ptr = int.from_bytes(gb[PTR_UNITS - GLOBALS_LIN:PTR_UNITS - GLOBALS_LIN + 4], "little")
    return ptr, gb[CNT_UNITS - GLOBALS_LIN], blob(log, u, DUMPS, "bin")


def plus8(units: bytes, i: int) -> tuple[int, int, int]:
    """(+6 陣營, +7, +8)"""
    r = units[i * STRIDE:(i + 1) * STRIDE]
    return r[6], r[7], r[8]


TABLES = {}
# 第 32 張圖(開場王座廳 → 原野)、第 31 張圖(森林)、第 0 張圖(第一場可操作的戰鬥)、第 1 張圖(第 1 章)
for log, g, u, m in (("lc184a", "m01_globals", "m02_units", 32), ("lc184a", "m05_globals", "m06_units", 31),
                     ("lc184a", "m07_globals", "m08_units", 0), ("lc184b", "m01_globals", "m02_units", 1)):
    ptr, n, units = live_table(log, g, u)
    own = CTL[m][1]                            # 控制段 byte 1 = 己方出場數:記錄 i 是單位 own + i
    assert own + 1 <= n <= own + CTL[m][2] and len(units) >= n * STRIDE, (log, m, own, n)
    for i in range(own, n):
        side, p7, p8 = plus8(units, i)
        assert p7 == p8 == rec_b1(m, i - own), (log, m, i, p7, p8, rec_b1(m, i - own))
        # 建構函式把記錄 byte 0(陣營)抄到 +6(parse_field.py 的 0x10ec1 / 0x10ef5)
        assert side == CTL[m][REC0 + (i - own) * REC_LEN], (log, m, i, side)
    TABLES[(log, m)] = {"unit_base": ptr, "units": n, "own_deploy": own, "units_bytes": units}
assert TABLES[("lc184a", 32)]["unit_base"] != TABLES[("lc184a", 31)]["unit_base"]
# 空字串的三個 b1(續一百八十三)只出現在第 32 / 31 張圖,本輪當下都在表上
BLANK = {x["b1"]: x["maps"] for x in S183["blank_name_b1"]}
assert BLANK == {48: [32], 66: [32], 75: [31]}, BLANK
STR183 = {x["b1"]: x["string"] for x in S183["b1_table"]}  # 續一百八十三:面板取 FDTXT_000 第 b1 + 1 句
BLANK_UNITS = []
for b1, (m,) in BLANK.items():
    t = TABLES[("lc184a", m)]
    hit = [i for i in range(t["units"]) if plus8(t["units_bytes"], i)[2] == b1]
    assert len(hit) == 1, (b1, hit)
    side = plus8(t["units_bytes"], hit[0])[0]
    assert side == CTL[m][REC0 + (hit[0] - t["own_deploy"]) * REC_LEN], (b1, side)
    BLANK_UNITS.append({"b1": b1, "map": m, "unit": hit[0], "side_plus6": side,
                        "unit_base": hex(t["unit_base"]), "name_string": STR183[b1]})
BLANK_S2 = {x["name_string"] for x in BLANK_UNITS}
PROLOGUE_BASES = {TABLES[("lc184a", 32)]["unit_base"], TABLES[("lc184a", 31)]["unit_base"]}
PLAY_BASES = {"lc184a": TABLES[("lc184a", 0)]["unit_base"], "lc184b": TABLES[("lc184b", 1)]["unit_base"]}
FDTXT_HEAD = FDTXT0.read_bytes()[:32]

# ================= Q3 播放點(續一百八十一的靜態位置;返回位址 = call + 5) =================
_SITES = S181["panel"]["sites"]
R_OPEN, R_CLOSE = int(_SITES["open"], 16) + 5, int(_SITES["close"], 16) + 5
R_SWAP, R_LIST = int(_SITES["swap_to_spells"], 16) + 5, int(_SITES["spell_list_open"], 16) + 5
_CTX = S181["context"]
(R_TOWN,) = [int(x["call"], 16) + 5 for x in _CTX["1"] if x["func"] == "town_hub_main"]
R_RING = {x["func"]: int(x["call"], 16) + 5 for x in _CTX["8"]}
(R_CHEST,) = [int(x["call"], 16) + 5 for x in _CTX["0xc"] if x["func"] == "field_cell_treasure_check"]
assert set(R_RING) == {"action_ring_open", "action_ring_close"}
NO_SPELL = [R_OPEN] * len(S181["panel"]["open_frames"]) + [R_CLOSE] * len(S181["panel"]["close_frames"])
assert R_SWAP not in NO_SPELL and R_LIST not in NO_SPELL


_ENT = sorted(_NM)


def func_of(a: int) -> int:
    """位址所在的登錄函式入口。"""
    return _ENT[bisect.bisect_right(_ENT, a) - 1]


def inside(lg: cs.Log, c: cs.Call) -> tuple[int, int]:
    """這次呼叫 E 行到 R 行之間(檔案行號)。"""
    r = lg.rets[c.seq]
    assert r.kind == "R", c.seq
    return c.line, r.line


def key_before(lg: cs.Log, line: int) -> int:
    """這一行之前最後一個按下(make code,< 0x80;放開是 | 0x80、方向鍵另有 0xe0 前綴)的 K 紀錄位元組。"""
    ks = [k for k in lg.keys if k.line < line and k.data < 0x80]
    return ks[-1].data


RUNS = {}
Q1_PANELS = {}
Q3 = collections.defaultdict(list)
for nm, m5 in LOG_MD5.items():
    p = RAW / f"{nm}_CALLLOG.TXT"
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, nm
    head = p.open(encoding="ascii").readline()
    assert head.startswith("H fd2calllog 1 ") and " entries=1356 " in head and f" cap={CAP} " in head and " dump=32 " in head, head
    assert f" trig={TRIG} " in head and " trigcap=40" in head and " segs=" not in head and " kbd=1" in head, head
    lg = cs._read(str(p), calls=True)
    # ---------- Q2(同 ev_s181b)----------
    tc = lg.trig_counts
    assert set(tc) == {0, 1} and tc[0][0] == tc[1][0] == "ng", tc
    by_rule = collections.Counter(t.rule for t in lg.trigs)
    assert all(t.complete for t in lg.trigs) and not [q for t in lg.trigs for q in cs.trig_problems(t, lg.game_cs)], nm
    assert all(by_rule[r] == tc[r][2] <= tc[r][1] for r in tc), (nm, by_rule, tc)
    assert all(t.count == 375 for t in lg.trigs if t.rule == 0) and all(t.count in (302, 303) for t in lg.trigs if t.rule == 1)
    cls = collections.Counter()
    for t in (t for t in lg.trigs if t.rule == 1):
        back = [x for x in t.insns if x.n == t.n1 + 1]
        assert len(back) == 1, (nm, t.seq)
        hw = [q for q in t.irqs if t.n0 <= q.n <= t.n1 and q.type == 0]
        mdi = (t.cs, t.eip) == MDI_FROM and back[0].cs == lg.game_cs and back[0].eip - DELTA == MDI_BACK
        if mdi:
            assert not hw, (nm, t.seq, hw)
        cls[("mdi" if mdi else f"{t.cs:04x}:{t.eip:x}->{back[0].cs:04x}:{back[0].eip:x}", t.count, len(hw))] += 1
    assert sum(cls.values()) == by_rule[1] == tc[1][2], (nm, cls, by_rule)
    p375 = []
    for t in (t for t in lg.trigs if t.rule == 0):
        back = [x for x in t.insns if x.n == t.n1 + 1]
        iq = [(q.num, q.type, q.m, q.cs, q.eip) for q in t.irqs if t.n0 <= q.n <= t.n1]
        drv = [x for x in t.span() if x.cs == 0x137C]
        ok = ((t.cs, t.eip) == MDI_FROM and len(back) == 1 and back[0].eip - DELTA == MDI_BACK
              and iq == [(0x0F, 0, "r", 0x0C5C, 0x1FAD)] and len(drv) == 375 - 302 and (drv[0].eip, drv[-1].eip) == (0x682, 0x729))
        p375.append({"t_ms": round(t.t0, ndigits=1), "mdi_irq7_73": ok})
    assert all(x["mdi_irq7_73"] for x in p375), (nm, p375)
    (_k0, m375, w375), (_k1, m302, w302) = tc[0], tc[1]
    assert (w375, w302) == (by_rule[0], by_rule[1])

    # ---------- Q1 面板 ----------
    n_dlg0 = 0
    blank_drawn = []
    cur = None
    panels = collections.Counter()               # (基底, 單位, 名字字串)
    no_inner = 0
    inner = []
    for c in lg.calls:
        e = c.eip - DELTA
        if e == PANEL:
            cur, inner = c.stack[UNIT_ARG], []
        elif e == DLG and c.mem["s1"] is not None and bytes(c.mem["s1"][:32]) == FDTXT_HEAD:
            n_dlg0 += 1
            if c.stack[1] in BLANK_S2:
                blank_drawn.append(c.seq)
            if c.ret - DELTA == NAME_RET:
                assert cur is not None, (nm, c.seq)
                bases = {v - STRIDE * cur for v in inner}
                assert len(bases) <= 1, (nm, c.seq, bases)
                b = bases.pop() if bases else None
                no_inner += b is None
                panels[(b, cur, c.stack[1])] += 1
                cur = None
        elif cur is not None and ESI_SET < c.ret - DELTA < PANEL_END:
            inner.append(c.regs["esi"])
    n_dlg_all = sum(1 for c in lg.calls if c.eip - DELTA == DLG)
    n_panel = sum(1 for c in lg.calls if c.eip - DELTA == PANEL)
    # 「沒有畫」要在記錄沒有記滿的前提下才成立(記滿之後看不到)
    assert n_dlg_all < CAP and n_panel < CAP, (nm, n_dlg_all, n_panel)
    assert not blank_drawn, (nm, blank_drawn)
    known = {b for b, _u, _s in panels if b is not None}
    assert known == {PLAY_BASES[nm]} and not known & PROLOGUE_BASES, (nm, known)
    assert no_inner < sum(panels.values()) // 2, (nm, no_inner)
    # 每次 draw_unit_panel 都畫一次名字;名字字串 = 當下單位表該單位 +8 + 1(續一百八十三的規則,另一條讀法)
    assert n_panel == sum(panels.values()), (nm, n_panel, panels)
    _play_units = TABLES[(nm, 0 if nm == "lc184a" else 1)]["units_bytes"]
    assert all(s == STR183[_play_units[u * STRIDE + 8]] for _b, u, s in panels), (nm, panels)
    # FDTXT_000 的字串呼叫:以傾印開頭認的次數 = 以面板用的那個文字表指標(s1 值)認的次數
    _ptr0 = {c.stack[0] for c in lg.calls if c.eip - DELTA == DLG and c.ret - DELTA == NAME_RET}
    assert len(_ptr0) == 1 and n_dlg0 == sum(1 for c in lg.calls if c.eip - DELTA == DLG and c.stack[0] in _ptr0), (nm, n_dlg0)
    Q1_PANELS[nm] = {"draw_unit_panel_calls": n_panel, "panel_name_calls": sum(panels.values()),
                     "by_base_unit_string": {f"{hex(b) if b is not None else '子函式未記到'} 單位 {u} 字串 {s}": v
                                             for (b, u, s), v in sorted(panels.items(), key=lambda kv: str(kv[0]))},
                     "fdtxt000_string_calls": n_dlg0, "blank_string_calls": len(blank_drawn)}

    # ---------- Q3 ----------
    plays = [c for c in lg.calls if c.eip - DELTA in (PLAY_A, PLAY_B)]
    assert len(plays) < CAP * 2
    for fn in ("action_ring_open", "action_ring_close"):
        for c in (c for c in lg.calls if c.eip - DELTA == _BY[fn]):
            lo, hi = inside(lg, c)
            got = [(q.eip - DELTA, q.stack[1], q.ret - DELTA) for q in plays if lo < q.line < hi]
            assert got == [(PLAY_A, 8, R_RING[fn])], (nm, fn, c.seq, got)
            Q3["8"].append({"log": nm, "func": fn, "seq": c.seq, "ret": hex(R_RING[fn])})
    for c in (c for c in lg.calls if c.eip - DELTA == _BY["unit_info_cards"]):
        lo, hi = inside(lg, c)
        bits = [q for q in lg.calls if lo < q.line < hi and q.eip - DELTA == _BY["unit_list_bits_1a"]]
        assert len(bits) == 1 and bits[0].stack[0] == c.stack[0], (nm, c.seq)
        has = lg.rets[bits[0].seq].eax != 0
        got = [q.ret - DELTA for q in plays if lo < q.line < hi and q.stack[1] in (5, 6)]
        Q3["5/6"].append({"log": nm, "unit": c.stack[0], "unit_list_bits_1a": lg.rets[bits[0].seq].eax,
                          "plays": [hex(x) for x in got]})
        if not has:
            assert got == NO_SPELL, (nm, c.seq, [hex(x) for x in got])
    for q in plays:
        if q.ret - DELTA == R_TOWN:
            assert q.eip - DELTA == PLAY_A and q.stack[1] == 1 and key_before(lg, q.line) == KEY_RETURN, (nm, q.seq)
            nxt = [c for c in lg.calls if c.line > q.line and c.eip - DELTA == _BY["town_hub_select"]]
            assert nxt and not [k for k in lg.keys if q.line < k.line < nxt[0].line], (nm, q.seq)
            Q3["1"].append({"log": nm, "seq": q.seq, "key_before": hex(KEY_RETURN), "then": "town_hub_select"})
    for c in (c for c in lg.calls if c.eip - DELTA == _BY["field_cell_treasure_check"]):
        lo, hi = inside(lg, c)
        yn = [q for q in lg.calls if lo < q.line < hi and q.eip - DELTA == _BY["yes_no_prompt"]]
        # 只看這個函式自己放的音(對話框裡的打字音 index 2 是 typewriter_tick 放的)
        got = [(q.eip - DELTA, q.stack[1], q.ret - DELTA) for q in plays if lo < q.line < hi and func_of(q.ret - DELTA) == c.eip - DELTA]
        assert len(yn) == 1 and lg.rets[yn[0].seq].eax == 1, (nm, c.seq)
        assert got == [(PLAY_B, 0xC, R_CHEST)] and key_before(lg, lg.rets[yn[0].seq].line) == KEY_RETURN, (nm, c.seq, got)
        Q3["0xc"].append({"log": nm, "seq": c.seq, "yes_no_prompt": lg.rets[yn[0].seq].eax, "ret": hex(R_CHEST)})
    RUNS[nm] = {"calllog": rel(p), "md5": m5, "tail_cut": lg.tail_cut, "keys": len(lg.keys),
                "yc": {"ng_375": {"matched": m375, "written": w375}, "ng_302_303": {"matched": m302, "written": w302}},
                "yn": dict(sorted(lg.trig_spans.items())), "blocks_375": p375,
                "blocks_302_303": {f"{k} {n} hw_irq={h}": v for (k, n, h), v in sorted(cls.items())}}

# 每一項至少有一次實例(沒有就不能寫 PASS)
NO_SPELL_CARDS = [x for x in Q3["5/6"] if x["unit_list_bits_1a"] == 0]
assert len(Q3["1"]) == 1 and len(Q3["0xc"]) == 1 and NO_SPELL_CARDS and Q3["8"], {k: len(v) for k, v in Q3.items()}
_n8 = collections.Counter((x["log"], x["func"]) for x in Q3["8"])
assert _n8 == {("lc184a", "action_ring_open"): 5, ("lc184a", "action_ring_close"): 5,
               ("lc184b", "action_ring_open"): 3, ("lc184b", "action_ring_close"): 3}, _n8
# 沒有法術那張卡:lc184a 單位 11(第 0 張圖的盜賊,敵方;+0x1a .. +0x1e 已習得法術位元全 0)
_u = NO_SPELL_CARDS[0]["unit"]
_r = TABLES[("lc184a", 0)]["units_bytes"][_u * STRIDE:(_u + 1) * STRIDE]
assert _r[6] == 0 and not any(_r[0x1A:0x1F]), (_u, _r[:0x20].hex())
N375 = sum(len(r["blocks_375"]) for r in RUNS.values())
VERDICT = {"Q1_P1a": "PASS", "Q1_P1b": "NOT TESTED", "Q1_P1c": "PASS", "Q2_P2": "NOT TESTED" if N375 == 0 else "PASS",
           "Q2_P2prime": "PASS", "Q3_P3a": "PASS", "Q3_P3b": "PASS", "Q3_P3c": "PASS", "Q3_P3d": "PASS"}
assert (VERDICT["Q2_P2"] == "PASS") == (N375 > 0)
OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s184.py"), "exe_md5": MD5, "prediction": rel(PRED), "driver": rel(DRV / "lc184.py"),
    "approval": "使用者 2026-11-02「請全部實機執行進行確認」;兩次實機都正常結束",
    "trig": TRIG, "runs": RUNS,
    "live_tables": {f"{lg}/map{m}": {"unit_base": hex(t["unit_base"]), "units": t["units"], "own_deploy": t["own_deploy"]}
                    for (lg, m), t in TABLES.items()},
    "blank_name_units": BLANK_UNITS, "panels": Q1_PANELS, "q3": dict(Q3), "screenshots_md5": SHOT_MD5, "verdict": VERDICT,
    "conclusion": "b1 48 / 66 / 75 的單位當下在表上(第 32 張圖單位 0 / 1、第 31 張圖單位 2,+8 = b1),但兩張圖都是開場劇情,"
                  "draw_unit_panel 只畫過可操作戰場的單位、FDTXT_000 第 49 / 67 / 76 句一次都沒畫(記錄沒記滿):空白名字不會被顯示,"
                  f"面板上空白與否無從看到(P1b NOT TESTED)。375 區塊 {N375} 個全是 MDI 型夾一次 IRQ 7(P2 PASS)。"
                  "index 1 = 城鎮按 Return 選設施、8 = 行動環開 / 收、5 / 6 沒有法術那一支 = 5, 5, 6, 6、0xc = 寶箱 YES 之後,都在預測的函式與按鍵之後。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, VERDICT)
