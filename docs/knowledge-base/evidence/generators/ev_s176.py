"""續一百七十六證據:evidence/dig_fill_lengths_s176_20261031.json(續一百七十五仍留:DIG 填緩衝兩種長度差在哪、[drv+0x34] 指向哪裡)。

使用者 2026-10-31「請依照你的建議逐項進行處理」。沒有新實機:用 lc174a / lc174b(Y 區塊逐條)、lc173a 的 DOSBox-X 呼叫紀錄
與 FD2.EXE(分派表由 LE fixup 取)、SB16.DIG(16 位元)反組譯。
(A) 15191 條(有 R)那型 = 這次沒有任何樣本在放:0x404c0 只混 [+4] == 4 的樣本,一個都沒有就不叫 0x49690,
    [drv+0x64] = 0 讓 0x49891 的旗標少 0x40,輸出走分派表第 0 格 0x47d88(每樣本 7 條,不截幅)而不是第 0x40 格 0x4809b
    (每樣本 11 條,截幅)。由 Y 區塊逐條紀錄扣掉混音呼叫、換掉輸出迴圈、加上計數分支,預測 IF=0 區間 15163,
    加上前段 15 / 後段 13 = 15191,三份紀錄的眾數都正好是這個值;沒有 R 的那兩次直接量到 15163 / 15164。
(B) 15305 條那型 = 連續第 3 次沒樣本:[drv+0x58] 數到 2 就經 0x382e9 呼叫驅動功能 0x402(紀錄裡是一次 int 31h 進 SB16.DIG 137c),
    [drv+0x54] 清 0,之後的服務都走 0x404ff 的出口(50 條);每一次都是「混音 → 沒樣本 → 沒樣本 → 這型」。
    SB16.DIG 的 0x402(0xacc,派送到 iret 52 條)只把狀態 3 → 2,下一次 IRQ 7 才送 DSP 0xd0、[0x504] = 0xffff;
    那之前若有 0x401(狀態 2 → 3 的路徑 59 條)就取消、不停(三份紀錄各 3 停 + 1 取消)。
(C) 43928 條(Y 區塊)那型 = 一個樣本混滿整個緩衝(2048 個輸出樣本,混音器 0x49430 每樣本 10 條);
    混音型還有其他長度:樣本在緩衝中途放完時 = 43928 − 20481 + 10m + 16(m = 混到的樣本數),
    三份紀錄的 30133 / 31253 / 36793 三群眾數都落在整數 m(667 / 779 / 1333)。
(D) [drv+0x34] 指向 SB16.DIG 的 cs:0504(執行時 137c:0504):0x40d6d 呼叫驅動功能 0x301,SB16.DIG 0x7b9 回傳 dx:ax = cs:040c、
    cx:bx = cs:04fc,0x40dd1 [drv+0x34] = [drv+8] + 8;IRQ 處理 ds = cs、0x716 xor [0x504], 1。回傳字序與 DS 基底 0 是推的(INFERRED)。
前段 / 後段條數由靜態路徑算,先拿不填緩衝(57 條)與停播後(50 條)兩條路徑對照紀錄的眾數。任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import re

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, _META, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import ail_driver_disasm as ad  # noqa: E402
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("dig_fill_lengths_s176_20261031.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
GAME_CS = 0x170
DIG_CS = 0x137C                       # SB16.DIG 實模式段(續一百七十四 / 一百七十五)
RAW = {"lc174a": ROOT / ".wsl_build/lc174_live/lc174a_CALLLOG.TXT", "lc174b": ROOT / ".wsl_build/lc174_live/lc174b_CALLLOG.TXT",
       "lc173a": ROOT / ".wsl_build/lc173_live/lc173a_CALLLOG.TXT"}
LOG_MD5 = {"lc174a": "0aaee51798ec85a779a95aa78ed85cac", "lc174b": "9be49f776cc0ed2fbbc3d7e962503b14",
           "lc173a": "3a8bb8b852d99b3f6307a64306408efb"}
SERVE = 0x404C0
T_AFTER_INIT, T_SEGS_END = 3260.0, 24000.0   # 同 ev_s175:SB16.DIG 初始化之後、G 紀錄還在的範圍

assert hashlib.md5(_EXE).hexdigest() == MD5
LOG: dict[str, cs.Log] = {}
for _nm, _p in RAW.items():
    assert hashlib.md5(_p.read_bytes()).hexdigest() == LOG_MD5[_nm], _nm
    LOG[_nm] = cs._read(str(_p), calls=True)          # E / R 也由 calllog_segments 解(續一百七十七);寫到一半的末行已丟
    assert LOG[_nm].game_cs == GAME_CS


def rt(a: int) -> int:
    return a + DELTA


# ================= 靜態:路徑條數與分派表 =================
def lin(a: int, b: int) -> int:
    """a 起線性反組譯到 b(含)的條數;b 不是指令邊界就 AssertionError。"""
    n = 0
    for i in _MD.disasm(_CODE[a - _CBASE:b - _CBASE + 16], a):
        n += 1
        if i.address == b:
            return n
        assert i.address < b, (hex(a), hex(b))
    raise AssertionError((hex(a), hex(b)))


STATIC = {0x404FB: "cmp dword ptr [eax + 0x54], 0", 0x404FF: "jne 0x40517", 0x4052B: "jne 0x4054e",
          0x40580: "cmp dword ptr [eax + 4], 4", 0x40584: "jne 0x40595", 0x40586: "push eax", 0x4058D: "call 0x49690",
          0x40592: "add esp, 4", 0x405C3: "mov dword ptr [eax + 0x64], edi", 0x40627: "test eax, eax", 0x40629: "je 0x40634",
          0x40632: "jmp 0x40663", 0x4063D: "cmp eax, 2", 0x40640: "jne 0x40663", 0x4064C: "push 0x402",
          0x40654: "call 0x382e9", 0x4065C: "mov dword ptr [edi + 0x54], 0",
          0x498C0: "cmp dword ptr [ebx + 0x64], 0", 0x498C6: "or eax, 0x40", 0x49915: "call dword ptr [eax*4 + 0x37988]",
          0x497CC: "call dword ptr [ebp*4 + 0x37b88]", 0x497EA: "jb 0x49851", 0x4984F: "jne 0x49858",
          0x49841: "mov dword ptr [ecx + 4], 2", 0x49436: "jae 0x49456", 0x49456: "ret ",
          0x480B7: "jne 0x4809b", 0x47D96: "jne 0x47d88", 0x49454: "jb 0x49430",
          0x49946: "rep stosd dword ptr es:[edi], eax", 0x3F0BC: "sti ", 0x3F0BD: "pop ebp", 0x3F0C0: "ret ", 0x40683: "ret "}
for _a, _t in STATIC.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)

FIX = dl.build_fixups(_EXE, _META)
OUT_TBL, MIX_TBL = FIX[0x49918], FIX[0x497CF]          # 兩條 call [reg*4 + 表] 的位移欄
OUT_PLAIN, OUT_CLIP, MIXER = FIX[OUT_TBL], FIX[OUT_TBL + 4 * 0x40], FIX[MIX_TBL + 4 * 0x60]
assert (OUT_PLAIN, OUT_CLIP, MIXER) == (0x47D88, 0x4809B, 0x49430), (hex(OUT_PLAIN), hex(OUT_CLIP), hex(MIXER))
PER_PLAIN = lin(OUT_PLAIN, 0x47D96)                    # 每個輸出樣本:不截幅
PER_CLIP = lin(OUT_CLIP, 0x480B7)                      # 每個輸出樣本:截幅那支沒越界時
PER_MIX = lin(MIXER, 0x49454)                          # 每個輸出樣本:混音器(重取樣 + 音量表)
MIX_END = lin(MIXER, 0x49436) + 1                      # 來源放完:cmp / jae 跳到 ret
# 來源放完、[+0x30] == 1 的收尾:0x497ec .. 0x49803 → 0x49821 .. 0x4982c → 0x49841 .. 0x4984f(設狀態 2)
SRC_DONE = lin(0x497EC, 0x49803) + lin(0x49821, 0x4982C) + lin(0x49841, 0x4984F)
# 0x40627 之後:混過(0x4062b、0x40632)與沒混、計數 ≠ 2(0x40634 .. 0x40640)
CNT_DIFF = lin(0x40634, 0x40640) - lin(0x4062B, 0x40632)
# 前段:入口 .. 0x404ea call、0x382d6 jmp、0x3f0a8 .. 0x3f0aa cli;後段(填緩衝):0x3f0bd .. ret、0x382e5 .. ret、0x40671 .. ret
PRE = lin(SERVE, 0x404EA) + lin(0x382D6, 0x382D6) + lin(0x3F0A8, 0x3F0AA)
POST_FILL = lin(0x3F0BD, 0x3F0C0) + lin(0x382E5, 0x382E8) + lin(0x40671, 0x40683)
_RESTORE = lin(0x382DB, 0x382E0) + lin(0x3F0AC, 0x3F0BC) + lin(0x3F0BD, 0x3F0C0) + lin(0x382E5, 0x382E8)
# 對照路徑:不填緩衝(0x40534 出口)與停播後([+0x54] == 0,0x404ff 不跳)
G_NOFILL = PRE + lin(0x3F0AB, 0x3F0AB) + lin(0x404EF, 0x404FF) + lin(0x40517, 0x4052B) + lin(0x4052D, 0x40534) + _RESTORE \
    + lin(0x40539, 0x4054D)
G_STOPPED = PRE + lin(0x3F0AB, 0x3F0AB) + lin(0x404EF, 0x404FF) + lin(0x40501, 0x40502) + _RESTORE + lin(0x40507, 0x40512) \
    + lin(0x4067A, 0x40683)
assert (PER_PLAIN, PER_CLIP, PER_MIX, MIX_END, SRC_DONE, CNT_DIFF) == (7, 11, 10, 3, 13, 3)
assert (PRE, POST_FILL, G_NOFILL, G_STOPPED) == (15, 13, 57, 50)

# ================= (C) Y 區塊:一個樣本混滿整個緩衝 =================
BLOCKS = []
for nm in ("lc174a", "lc174b"):
    for t in LOG[nm].trigs:
        s = t.span()
        if not (t.kind == "if" and (s[0].cs, s[0].eip) == (GAME_CS, rt(0x3F0AB)) and (s[-1].cs, s[-1].eip) == (GAME_CS, rt(0x3F0BC))):
            continue
        e = [x.eip - DELTA for x in s]
        c = collections.Counter(e)
        out_clip = sum(v for a, v in c.items() if OUT_CLIP <= a < 0x480C8)
        mix = sum(v for a, v in c.items() if MIXER <= a < 0x49457)
        assert c[0x480BA] == c[0x480C1] == 0, (nm, t.seq)   # 沒有截幅
        n_out, r1 = divmod(out_clip - 1, PER_CLIP)
        n_mix, r2 = divmod(mix - 1, PER_MIX)
        assert r1 == r2 == 0 and n_out == n_mix, (nm, t.seq, out_clip, mix)
        assert c[0x4058D] == c[0x498C6] == c[0x4062B] == 1 and c[0x40634] == 0, (nm, t.seq)
        i0, i1 = e.index(0x40586), e.index(0x40592)
        BLOCKS.append({"log": nm, "seq": t.seq, "count": t.count, "n_out": n_out, "mix": mix, "stosd": c[0x49946],
                       "mix_call": i1 - i0 + 1, "out_clip": out_clip})
assert len(BLOCKS) == 14
N_OUT = BLOCKS[0]["n_out"]
assert all(b["n_out"] == N_OUT for b in BLOCKS)
# 區塊條數只差在 rep stosd 記了幾筆:扣掉之後全部相同
assert len({b["count"] - b["stosd"] for b in BLOCKS}) == 1, BLOCKS
FULL = collections.Counter(b["count"] for b in BLOCKS).most_common(1)[0][0]
_ref = next(b for b in BLOCKS if b["count"] == FULL)
# (A) 沒樣本:扣掉混音呼叫(0x40586 .. 0x40592 與其下)、0x498c6 or、截幅輸出換成不截幅,加上計數分支
OUT_TAIL = _ref["out_clip"] - PER_CLIP * N_OUT            # 最後一次 jne 不跳之後的 ret
OUT_PLAIN_N = PER_PLAIN * N_OUT + OUT_TAIL
U_PRED = FULL - _ref["mix_call"] - 1 - (_ref["out_clip"] - OUT_PLAIN_N) + CNT_DIFF
BASE0 = FULL - _ref["mix"]                             # 混音器 0 次迭代之外的部分


def partial_m(span: int) -> float:
    """樣本在緩衝中途放完時混到的輸出樣本數:span = BASE0 + PER_MIX * m + MIX_END + SRC_DONE。"""
    return (span - BASE0 - MIX_END - SRC_DONE) / PER_MIX


# ================= 每一次 DIG 服務 =================
def services(nm: str) -> list[dict]:
    """初始化之後每次 DIG 服務:g(有 R)或 IF=0 區間(沒有 R 時由結束在 0x3f0bd 的 G 推)、區間內 int 31h 與 137c 指令數。"""
    lg = LOG[nm]
    ce = [c for c in lg.calls if c.eip == rt(SERVE)]
    cr = [r for r in lg.rets.values() if r.kind == "R" and r.entry == rt(SERVE)]
    assert ce and all(x.ic for x in ce + cr), nm                         # 要有 FD2_CALLLOG_ICOUNT 的 i / n / t
    es = [(c.seq, *c.ic) for c in ce]                                    # (seq, i, n, t)
    rs = {r.seq: (r.seq, *r.ic) for r in cr}
    ends = [r for r in lg.runs if (r.m, r.cs, r.e1) == ("P", GAME_CS, rt(0x3F0BD))]
    end_n = [r.n_end for r in ends]
    q31 = [q.n for q in lg.irqs if q.num == 0x31]
    digr = [r for r in lg.runs if r.cs == DIG_CS]
    dig_n = [r.n_start for r in digr]
    ys = {t.n0: t.count for t in lg.trigs if t.kind == "if" and t.eip == rt(0x3F0AB)}
    out = []
    for seq, i, n, t in es:
        if not T_AFTER_INIT <= t < T_SEGS_END:
            continue
        r = rs.get(seq)
        if r is not None:
            g = r[1] - i
            row = {"t": t, "n": n, "r_n": r[2], "g": g, "span": None, "int31": None, "dig_insns": None}
            if g > 1000:
                row.update(span=g - PRE - POST_FILL, int31=bisect.bisect_left(q31, r[2]) - bisect.bisect_right(q31, n),
                           dig_insns=sum(x.count for x in digr[bisect.bisect_right(dig_n, n):bisect.bisect_left(dig_n, r[2])]))
            out.append(row)
            continue
        run = ends[bisect.bisect_right(end_n, n)]
        assert run.n_start < n, (nm, t)
        span = run.n_end - n - (PRE - 1) - 1              # E 的 n 已含入口那條;再扣 0x3f0bd pop ebp
        if n + PRE in ys:                                 # 有 Y 區塊的:兩條路徑要一致
            assert ys[n + PRE] == span, (nm, t, ys[n + PRE], span)
            Y_CHECKED.append((nm, t))
        out.append({"t": t, "n": n, "r_n": None, "g": None, "span": span, "int31": None, "dig_insns": None})
    return out


Y_CHECKED: list[tuple[str, float]] = []
SV = {nm: services(nm) for nm in RAW}
assert len(Y_CHECKED) == len(BLOCKS), Y_CHECKED

# 對照:不填緩衝的 g 眾數 = 靜態路徑 57;停播之後 = 50
_g = collections.Counter(s["g"] for v in SV.values() for s in v if s["g"] is not None and s["g"] <= 1000)
assert {g for g, _ in _g.most_common(2)} == {G_NOFILL, G_STOPPED} and _g[G_NOFILL] + _g[G_STOPPED] > 0.95 * sum(_g.values()), \
    _g.most_common(4)

# 分群:每個長度歸到 [代表 − 10, 代表 + 2]。Y 區塊同型的差異只在 rep stosd 記的筆數(_lo .. _hi);沒有逐條紀錄的
# 那幾次範圍略寬(−9 .. +2),推為同因(INFERRED)。各群代表相距都遠大於這個窗,窗放寬到 [−30, +30] 分群也不變(見下)。
_lo, _hi = min(b["stosd"] for b in BLOCKS) - _ref["stosd"], max(b["stosd"] for b in BLOCKS) - _ref["stosd"]
assert (_lo, _hi) == (-5, 1)
JIT = (-9, 2)
SPANS = collections.Counter(s["span"] for v in SV.values() for s in v if s["span"] is not None)
U_MODE = max((v for v in SPANS if abs(v - U_PRED) <= 20), key=SPANS.get)
X_MODE = max((v for v in SPANS if 100 < v - U_PRED < 200), key=SPANS.get)
assert U_MODE == U_PRED, (U_MODE, U_PRED)
X_EXTRA = X_MODE - U_MODE


def kind(span: int) -> str:
    """unmixed / stop / full / partial。"""
    if JIT[0] <= span - U_MODE <= JIT[1]:
        return "unmixed"
    if JIT[0] <= span - X_MODE <= JIT[1]:
        return "stop"
    if JIT[0] <= span - FULL <= JIT[1]:
        return "full"
    assert U_MODE + 200 < span < FULL, span
    return "partial"


FILLS = {nm: [dict(s, kind=kind(s["span"])) for s in v if s["span"] is not None] for nm, v in SV.items()}
_kinds = [f["kind"] for v in FILLS.values() for f in v]
_JIT0, JIT = JIT, (-30, 30)                            # 放寬窗重分一次,分群不變;之後還原
assert [kind(f["span"]) for v in FILLS.values() for f in v] == _kinds
JIT = _JIT0
# 窗是最緊的:沒樣本 / 停播 / 混滿三型對各自代表的差,最小與最大正好是窗的兩端
_dev = [f["span"] - {"unmixed": U_MODE, "stop": X_MODE, "full": FULL}[f["kind"]]
        for v in FILLS.values() for f in v if f["kind"] != "partial"]
assert (min(_dev), max(_dev)) == JIT, (min(_dev), max(_dev))

# (A) 有 R 的沒樣本型:g 眾數 = 前段 + 預測區間 + 後段;沒有 int 31h、沒進 137c
_ug = collections.Counter(f["g"] for v in FILLS.values() for f in v if f["kind"] == "unmixed" and f["g"] is not None)
U_G = _ug.most_common(1)[0][0]
assert U_G == PRE + U_PRED + POST_FILL, (U_G, U_PRED)
assert all(f["int31"] == 0 and f["dig_insns"] == 0 for v in FILLS.values() for f in v if f["kind"] == "unmixed" and f["g"] is not None)
U_NO_R = sorted(f["span"] for v in FILLS.values() for f in v if f["kind"] == "unmixed" and f["g"] is None)
assert U_NO_R and all(JIT[0] <= x - U_PRED <= JIT[1] for x in U_NO_R), U_NO_R

# (B) 停播型:每次都有一次 int 31h 並進 SB16.DIG 段;前面正好是「混音 → 沒樣本 → 沒樣本」
SEQ = {}
for nm, v in FILLS.items():
    ks = [f["kind"] for f in v]
    SEQ[nm] = "".join({"unmixed": "u", "stop": "X", "full": "F", "partial": "p"}[k] for k in ks)
    for i, f in enumerate(v):
        if f["kind"] == "stop":
            assert f["int31"] == 1 and f["dig_insns"] > 0, (nm, f)
            assert i >= 3 and ks[i - 2:i] == ["unmixed", "unmixed"] and ks[i - 3] in ("full", "partial"), (nm, i, ks[i - 3:i + 1])
    # 沒樣本最多連 2 次,第 3 次一定是停播型
    assert "uuu" not in SEQ[nm] and "uuX" in SEQ[nm], SEQ[nm]
    # 混滿的下一次一定還有樣本(樣本沒放完)
    assert all(ks[i + 1] in ("full", "partial") for i in range(len(ks) - 1) if ks[i] == "full"), nm
STOP_N = {nm: s.count("X") for nm, s in SEQ.items()}


def after_stop(nm: str) -> collections.Counter:
    """停播型之後、下一次填緩衝之前,不填緩衝那幾次服務的 g。"""
    c = collections.Counter()
    v = SV[nm]
    for s in v:
        if s["span"] is not None and kind(s["span"]) == "stop":
            nxt = min((s2["n"] for s2 in v if s2["span"] is not None and s2["n"] > s["n"]), default=None)
            c.update(s2["g"] for s2 in v if s2["n"] > s["n"] and (nxt is None or s2["n"] < nxt))
    return c


AFTER = {nm: after_stop(nm) for nm in RAW}
assert all(max(c, key=c.get) == G_STOPPED for c in AFTER.values()), AFTER

# ================= (B) 續:停播在下一次 IRQ 7 才生效(SB16.DIG) =================
# 功能 0x402(0xacc)把狀態 [0x578] 3 → 2;IRQ 處理看到 2 就送 DSP [0x546 + bx](8 位元 bx = 0 → 0xd0)並把 [0x504] 設 0xffff;
# 之間若有功能 0x401(0x9e4)而狀態是 2,就跳 0xab8 設回 3,不停。
DIG = (GAME / "SB16.DIG").read_bytes()


def insn16(a: int) -> str:
    """SB16.DIG 段內位移 a(= 檔案位移)那一條 16 位元指令的文字(ail_driver_disasm.insn_text)。"""
    try:
        return ad.insn_text(DIG, a)
    except ValueError as e:
        raise AssertionError(e) from e


def lin16(a: int, b: int) -> int:
    """SB16.DIG:a 起線性反組譯到 b(含)的條數(ail_driver_disasm.path_len);b 不是指令邊界就 AssertionError。"""
    try:
        return ad.path_len(DIG, a, b)
    except ValueError as e:
        raise AssertionError(e) from e


STATIC16 = {0x16A: "cmp ax, 0x300", 0x191: "mov word ptr [0x124], ax", 0x194: "mov word ptr [0x126], bx",
            0x198: "mov word ptr [0x128], cx", 0x19C: "mov word ptr [0x12a], dx", 0x1AE: "mov si, 0x10a", 0x1B9: "mov si, 0x118",
            0x1C8: "call word ptr [bx + si]", 0x1E9: "iret ", 0x6A4: "push cs", 0x6A5: "pop ds", 0x6AD: "cmp word ptr [0x578], 2",
            0x6C7: "mov al, byte ptr [bx + 0x546]", 0x6D8: "mov word ptr [0x504], 0xffff", 0x716: "xor word ptr [0x504], 1",
            0x7B9: "mov word ptr [0x12a], cs", 0x7BD: "mov word ptr [0x124], 0x40c", 0x7C3: "mov word ptr [0x128], cs",
            0x7C7: "mov word ptr [0x126], 0x4fc", 0x9E9: "jb 0x9ee", 0x9F9: "jne 0x9fe", 0xA03: "jne 0xa08", 0xA05: "jmp 0xab8",
            0xAB8: "mov word ptr [0x578], 3", 0xACC: "cmp word ptr [0x578], 3", 0xAD3: "mov word ptr [0x578], 2"}
for _a, _t in STATIC16.items():
    assert insn16(_a) == _t, (hex(_a), insn16(_a), _t)
# 功能表由分派段的 mov si / sub ax / cmp ax 讀出(ail_driver_disasm.function_table):0x3xx 在 0x10a、0x4xx 在 0x118
_KIND, _DISP_AT = ad.parse_header(DIG)
_FTBL, _FCALL = ad.function_table(DIG, _DISP_AT)
assert (_KIND, _DISP_AT, _FCALL) == ("DIG", 0x16A, 0x1C8), (_KIND, hex(_DISP_AT), _FCALL)
FN = {f.num: f for f in _FTBL}
assert (FN[0x301].slot, FN[0x401].slot) == (0x10A + 2, 0x118 + 2), (hex(FN[0x301].slot), hex(FN[0x401].slot))
F301, F401, F402 = FN[0x301].addr, FN[0x401].addr, FN[0x402].addr
assert (F301, F401, F402) == (0x7B9, 0x9E4, 0xACC), (hex(F301), hex(F401), hex(F402))
_DISP, _BACK = lin16(0x16A, 0x1C8), lin16(0x1CA, 0x1E9)          # 0x4xx 派送(全直線)、返回到 iret
P402 = _DISP + lin16(F402, 0xADF) + _BACK                         # 狀態 3 → 2
P401_CANCEL = _DISP + lin16(F401, 0x9E9) + lin16(0x9EE, 0x9F9) + lin16(0x9FE, 0xA05) + lin16(0xAB8, 0xAC4) + _BACK
assert (P402, P401_CANCEL) == (52, 59)
PAUSE = DIG[0x546]                                                 # bx = [0x56c] = 0(8 位元)
assert PAUSE == 0xD0


def stop_chain(nm: str) -> list[dict]:
    """每次停播型之後:這次服務裡的 137c 派送條數、到下一次 IRQ 7 之間的 0x401 取消、下一次 IRQ 7 有沒有送 0xd0。"""
    lg = LOG[nm]
    disp = [r for r in lg.runs if (r.cs, r.e0) == (DIG_CS, 0x16A)]
    q7 = [q for q in lg.irqs if q.num == 0x0F and q.type == 0]
    dsp = [x for x in lg.ios if x.op == "O" and x.port == 0x22C]
    out = []
    for f in FILLS[nm]:
        if f["kind"] != "stop":
            continue
        own = [r.count for r in disp if f["n"] < r.n_start < f["r_n"]]
        nq = next(q for q in q7 if q.n > f["r_n"])
        cancel = [r.count for r in disp if f["r_n"] < r.n_start < nq.n]
        d = next(x for x in dsp if x.n > f["r_n"])
        paused = d.value == PAUSE and nq.n < d.n and d.t - nq.t < 0.2
        out.append({"t": round(f["t"], ndigits=2), "own_dispatch": own, "next_irq7_t": round(nq.t, ndigits=2),
                    "dispatch_before_irq7": cancel, "paused_at_irq7": paused})
    return out


CHAIN = {nm: stop_chain(nm) for nm in RAW}
for nm, rows in CHAIN.items():
    for r in rows:
        assert r["own_dispatch"] == [P402], (nm, r)
        assert r["paused_at_irq7"] == (P401_CANCEL not in r["dispatch_before_irq7"]), (nm, r)
CHAIN_N = {nm: (sum(r["paused_at_irq7"] for r in rows), sum(not r["paused_at_irq7"] for r in rows)) for nm, rows in CHAIN.items()}
assert all(p > 0 and c > 0 for p, c in CHAIN_N.values()), CHAIN_N

# ================= (D) [drv+0x34] 指向 SB16.DIG 的 cs:0504 =================
# 0x40d61 起呼叫驅動功能 0x301,回傳的 4 個字(遊戲結構 esp+0x18 起;驅動存回 [0x124 + 2k],k = 0 .. 3 = ax / bx / cx / dx)
# 拼成兩個 seg:off:[drv+4] = 字 3:字 0、[drv+8] = 字 2:字 1;[drv+0x34] = [drv+8] + 8。
STATIC_D = {0x40D67: "push 0x301", 0x40D6D: "call 0x382e9", 0x40D83: "shl eax, 4", 0x40D86: "add eax, edx",
            0x40D8A: "mov dword ptr [edx + 4], eax", 0x40D98: "shl edx, 4", 0x40DA0: "add edx, eax",
            0x40DA4: "mov dword ptr [eax + 8], edx", 0x40DD1: "mov dword ptr [edx + 0x34], eax",
            0x40517: "mov edi, dword ptr [eax + 0x34]", 0x4051A: "movsx edi, word ptr [edi]"}
for _a, _t in STATIC_D.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)
_ws = operand(0x40D61, "lea edx, [esp + ", "]")                   # 回傳結構起點
_WIDX = {nm: (operand(a, f"mov {r}, word ptr [esp + ", "]") - _ws) // 2
      for nm, a, r in (("seg4", 0x40D79, "ax"), ("off4", 0x40D7E, "dx"), ("seg8", 0x40D8F, "ax"), ("off8", 0x40D9B, "ax"))}
_plus = operand(0x40DA7, "lea eax, [edx + ", "]")
# 驅動功能 0x301 寫回的字:[0x124 + 2k]
_ret = {}
for _a in range(F301, F301 + 0x14):
    _m = re.fullmatch(r"mov word ptr \[(0x12[468a])\], (cs|0x[0-9a-f]+)", insn16(_a)) if _a in (0x7B9, 0x7BD, 0x7C3, 0x7C7) else None
    if _m:
        _ret[(int(_m.group(1), 16) - 0x124) // 2] = _m.group(2)
assert sorted(_ret) == [0, 1, 2, 3], _ret
DRV34 = (_ret[_WIDX["seg8"]], int(_ret[_WIDX["off8"]], 16) + _plus)
DRV4 = (_ret[_WIDX["seg4"]], int(_ret[_WIDX["off4"]], 16))
assert DRV34 == ("cs", 0x504) and DRV4 == ("cs", 0x40C), (DRV34, DRV4)
# 執行時 SB16.DIG 在 137c 段:lc174a 的 IRQ 7 處理 r 137c:0682 起
assert any((r.m, r.cs, r.e0) == ("r", DIG_CS, 0x682) for r in LOG["lc174a"].runs)
DRV34_SEG, DRV34_OFF = DRV34
SEG_SHIFT = operand(0x40D83, "shl eax, ")              # seg:off 換線性的那一條
DRV34_LINEAR = (DIG_CS << SEG_SHIFT) + DRV34_OFF

# (C) 混音型的長度:眾數夠多的部分緩衝群落在整數 m
PART = collections.Counter(f["span"] for v in FILLS.values() for f in v if f["kind"] == "partial")
_groups: dict[int, list[int]] = {}
for _v in sorted(PART):
    _k = next((k for k in _groups if 0 <= _v - k <= JIT[1] - JIT[0]), _v)
    _groups.setdefault(_k, []).append(_v)
GROUPS = []
for _k, _vs in sorted(_groups.items()):
    _n = sum(PART[x] for x in _vs)
    _mode = max(_vs, key=lambda x: (PART[x], x))
    GROUPS.append({"values": {x: PART[x] for x in _vs}, "n": _n, "mode": _mode, "mode_n": PART[_mode],
                   "m": partial_m(_mode)})
STRONG = [gp for gp in GROUPS if gp["mode_n"] >= 3]
assert [gp["mode"] for gp in STRONG] == [30133, 31253, 36793], STRONG
assert all(gp["m"] == int(gp["m"]) and 0 < gp["m"] < N_OUT for gp in STRONG), STRONG
# 對照:同樣的分群若把收尾條數錯一,三群都不會是整數
assert not any(((gp["mode"] - BASE0 - MIX_END - SRC_DONE - 1) % PER_MIX == 0) for gp in STRONG)

ROWS = {nm: {"fills": len(v), "kinds": dict(sorted(collections.Counter(f["kind"] for f in v).items())), "sequence": SEQ[nm],
             "after_stop_g": dict(sorted(AFTER[nm].items()))} for nm, v in FILLS.items()}

CONC = {
    "unmixed": f"{PRE + U_PRED + POST_FILL} 條那型是這次沒有任何樣本在放:0x404c0 只混 [+4] == 4 的樣本,一個都沒有就不叫 0x49690,[drv+0x64] = 0,"
               f"0x49891 的旗標少 0x40,輸出走分派表第 0 格 {OUT_PLAIN:#x}(每樣本 {PER_PLAIN} 條)而不是第 0x40 格 {OUT_CLIP:#x}"
               f"(每樣本 {PER_CLIP} 條、截幅)。由 Y 區塊 {FULL} 條扣掉混音呼叫 {_ref['mix_call']} 條、0x498c6 一條、輸出差 "
               f"{_ref['out_clip'] - OUT_PLAIN_N} 條、加計數分支 {CNT_DIFF} 條,預測 IF=0 區間 {U_PRED};"
               f"加前段 {PRE} / 後段 {POST_FILL} = {PRE + U_PRED + POST_FILL},三份紀錄有 R 的眾數 {U_G};沒有 R 的 {len(U_NO_R)} 次直接量到 "
               f"{min(U_NO_R)} .. {max(U_NO_R)}。上下幾條:Y 區塊同型的差異是 rep stosd 記的筆數({_lo:+d} .. {_hi:+d}),"
               f"沒有逐條紀錄的這型推為同因(INFERRED)。",
    "stop": f"{PRE + X_MODE + POST_FILL} 條那型(區間 {X_MODE},多 {X_EXTRA} 條)是連續第 3 次沒有樣本:[drv+0x58] 數到 2 就經 0x382e9 呼叫驅動功能 0x402"
            f"(每次一個 int 31h 進 SB16.DIG {DIG_CS:#x} 段),[drv+0x54] 清 0,之後的服務走 0x404ff 的出口({G_STOPPED} 條)。"
            f"三份紀錄 {' / '.join(str(v) for v in STOP_N.values())} 次,每次前面都是「混音 → 沒樣本 → 沒樣本」。"
            f"停播在下一次 IRQ 7 才生效:SB16.DIG 功能 0x402({F402:#x},{P402} 條)只把狀態 [0x578] 3 → 2,IRQ 處理看到 2 才送 DSP {PAUSE:#x}"
            f"並把 [0x504] 設 0xffff;三份紀錄各 {' / '.join(str(p) for p, _ in CHAIN_N.values())} 次在下一次 IRQ 7 的 0.2 ms 內送出 {PAUSE:#x},"
            f"各 {' / '.join(str(c) for _, c in CHAIN_N.values())} 次在那之前有功能 0x401({F401:#x} 狀態 2 → 3 的路徑,{P401_CANCEL} 條)取消、沒有停。",
    "mixed": f"{FULL} 條(Y 區塊)那型是一個樣本混滿整個緩衝:{N_OUT} 個輸出樣本,混音器分派表第 0x60 格 {MIXER:#x}(每樣本 {PER_MIX} 條);"
             f"混音型還有樣本在緩衝中途放完的:區間 = {BASE0} + {PER_MIX}m + {MIX_END + SRC_DONE},"
             f"{' / '.join(str(gp['mode']) for gp in STRONG)} 三群眾數的 m = {' / '.join(str(int(gp['m'])) for gp in STRONG)}(整數;收尾錯一條就都不是)。",
    "drv34": f"[drv+0x34] 指向 SB16.DIG 的 {DRV34_SEG}:{DRV34_OFF:04x}(執行時 {DIG_CS:04x}:{DRV34_OFF:04x},線性 {DRV34_LINEAR:#x}):0x40d6d 呼叫驅動功能 0x301,"
             f"SB16.DIG 的 0x301({F301:#x})回傳 dx:ax = cs:{DRV4[1]:04x}、cx:bx = cs:{DRV34_OFF - _plus:04x};遊戲拼成 [drv+4] / [drv+8],"
             f"0x40dd1 [drv+0x34] = [drv+8] + {_plus}。IRQ 處理 0x6a4 push cs / pop ds 之後 0x716 xor [0x504], 1(換緩衝號)、0x6d8 停播時設 0xffff。"
             f"回傳結構的字序(ax / bx / cx / dx)由兩組 seg:off 都拼出同一個 cs 而定、遊戲的 DS 基底 0(DOS/4GW 平坦模式)沒有直接看到(INFERRED)。",
}
for _part, _key in (("預測 IF=0 區間 15163", "unmixed"), ("= 15191", "unmixed"), ("多 114 條", "stop"),
                    ("m = 667 / 779 / 1333", "mixed"), ("2048 個輸出樣本", "mixed"), ("功能 0x402(0xacc,52 條)", "stop"),
                    ("cs:0504(執行時 137c:0504", "drv34")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s176.py"),
    "exe_md5": MD5,
    "calllogs": {nm: {"path": rel(p), "md5": LOG_MD5[nm]} for nm, p in RAW.items()},
    "static": {"output_table": hex(OUT_TBL), "mixer_table": hex(MIX_TBL), "output_plain": hex(OUT_PLAIN), "output_clip": hex(OUT_CLIP),
               "mixer": hex(MIXER), "per_sample": {"plain": PER_PLAIN, "clip": PER_CLIP, "mix": PER_MIX},
               "mix_end": MIX_END, "src_done": SRC_DONE, "count_branch_diff": CNT_DIFF, "pre": PRE, "post_fill": POST_FILL,
               "g_nofill": G_NOFILL, "g_stopped": G_STOPPED},
    "y_blocks": [{k: b[k] for k in ("log", "seq", "count", "stosd", "mix_call", "out_clip", "mix")} for b in BLOCKS],
    "prediction": {"full": FULL, "unmixed_span": U_PRED, "unmixed_g": PRE + U_PRED + POST_FILL, "base0": BASE0,
                   "jitter_window": list(JIT)},
    "observed": {"nonfill_g_top": dict(_g.most_common(2)), "unmixed_g_mode": U_G, "unmixed_no_r": U_NO_R, "stop_span_mode": X_MODE,
                 "partial_groups": GROUPS, "per_log": ROWS, "stop_chain": CHAIN},
    "drv34": {"fn301": hex(F301), "fn401": hex(F401), "fn402": hex(F402), "path_402": P402, "path_401_cancel": P401_CANCEL,
              "word_index": _WIDX, "points_to": f"{DRV34_SEG}:{DRV34_OFF:04x}", "runtime_linear": hex(DRV34_LINEAR)},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, U_PRED, U_G, X_MODE, [(gp["mode"], gp["m"]) for gp in STRONG], STOP_N)
