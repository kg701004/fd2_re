"""續一百七十五證據:evidence/audio_followups_s175_20261031.json(續一百七十 / 一百七十三仍留的三項)。

使用者 2026-10-31「還沒做的事 請逐項進行處理」。沒有新實機:用 lc174a / lc174b(觸發式擷取的 Y 區塊,逐條帶 IF)、
lc173a、lc167a 的 DOSBox-X 呼叫紀錄與 FD2.EXE 反組譯。
(A) DIG 服務長的那幾次 = 填緩衝:Y 區塊裡那 43928 條是 0x4054e → ail_mix_clear_build_buffer(0x49923)→ 混音 → 輸出,
    結尾在 0x4066c 恢復 IF(不是續一百七十三寫的 0x40534,那是沒填緩衝的出口);填不填看 IRQ 7:兩次服務之間收過 IRQ 7
    (SB16.DIG 實模式處理在 137c:0716 xor 緩衝號)下一次服務就填,例外只在 DSP 0xc6 / 0xd4(開始 / 繼續,沒 IRQ 也填)與 0xd0(暫停,有 IRQ 也不填)。
(B) 續一百七十的 4 次「短驅動呼叫」不是驅動呼叫:在遊戲程式碼收一次 IRQ 1 的非遊戲指令是 532 / 533、IRQ 7 是 558 .. 560(lc174a / lc173a);
    lc167a 那 3 次 558 之後 0.2 ms 的 DIG 服務都是填緩衝(IRQ 7 的特徵),532 那次不是。
(C) 敵方回合結束時讓序列停一次服務的呼叫:lc167a 564129.3 ms 那次 MDI 服務只跑 12 條遊戲指令(整份唯一),是 0x4327e 看到
    驅動結構 [+0x14] ≠ 0 的提早返回;前一筆 ISR 進入時的暫存器正好是 ail_impl_set_sequence_volume 在 0x44a3f idiv 之後的值
    (4000000 / 127 = 0x7b08 餘 8,ebx = 4000 ms × 1000),[+0x14] 在 0x449f0 加一、0x44a5a 才減回;4000 ms 只有 play_bgm(-1) 的
    0x259a3 push 0xfa0。所以是敵方回合結束後 play_bgm(-1) 開始淡出的那一次 AIL_set_sequence_volume,不是續一百七十三推的「序列狀態 ≠ 4」。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import re

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("audio_followups_s175_20261031.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
GAME_CS = 0x170
RAW = {"lc174a": ROOT / ".wsl_build/lc174_live/lc174a_CALLLOG.TXT", "lc174b": ROOT / ".wsl_build/lc174_live/lc174b_CALLLOG.TXT",
       "lc173a": ROOT / ".wsl_build/lc173_live/lc173a_CALLLOG.TXT", "lc167a": ROOT / ".wsl_build/lc167_live/lc167a_CALLLOG.TXT"}
LOG_MD5 = {"lc174a": "0aaee51798ec85a779a95aa78ed85cac", "lc174b": "9be49f776cc0ed2fbbc3d7e962503b14",
           "lc173a": "3a8bb8b852d99b3f6307a64306408efb", "lc167a": "ac9401da607102caa569be467c178b92"}
SERVE, MDI_SERVE, ISR = 0x404C0, 0x43270, 0x3EA8E
ENEMY_PHASE = 0x1D8BA
T_AFTER_INIT = 3260.0                  # SB16.DIG 初始化(單一樣本 DMA,續一百七十三 (D))之後才算
T_SEGS_END = 24000.0                   # SEGS 3250-24000:之後沒有 G / I 紀錄(E / R 還有),IRQ 7 數不到
INVENTORY = ROOT / "docs/data/function_inventory.json"

assert hashlib.md5(_EXE).hexdigest() == MD5
TEXT: dict[str, list[str]] = {}
LOG: dict[str, cs.Log] = {}
for _nm, _p in RAW.items():
    _b = _p.read_bytes()
    assert hashlib.md5(_b).hexdigest() == LOG_MD5[_nm], _nm
    _lines = _b.decode("ascii").split("\n")
    TEXT[_nm] = _lines[:-1]            # 最後一段:空字串(檔尾換行)或寫到一半的那一行,都不算
    if _nm != "lc167a":                # lc167a 只有 E / R / A,不用 G 解析
        LOG[_nm] = cs._read(str(_p))
        assert LOG[_nm].game_cs == GAME_CS
DIG_FILE = (GAME / "SB16.DIG").read_bytes()
ENTRIES = sorted(int(e["addr"], 16) for e in json.loads(INVENTORY.read_text(encoding="utf-8"))["entries"])


def rt(a: int) -> int:
    return a + DELTA


_RX = re.compile(r"^([ERA]) (\d+) ([0-9a-f]{8}) (.*?) ?i=(\d+) n=(\d+) t=([0-9.]+)")


def era(nm: str) -> list[tuple]:
    """E / R / A 紀錄:(種類, 序號, eip, 其餘欄位, i 遊戲指令累計, n 全部指令累計, t)。"""
    out = []
    for ln in TEXT[nm]:
        if ln[:2] in ("E ", "R ", "A "):
            m = _RX.match(ln)
            assert m, ln[:120]
            out.append((m.group(1), int(m.group(2)), int(m.group(3), 16), m.group(4), int(m.group(5)), int(m.group(6)),
                        float(m.group(7))))
    return out


ERA = {nm: era(nm) for nm in RAW}


def services(nm: str, entry: int) -> list[dict]:
    """某個入口的每一次呼叫:E 的 n / t / i,配對到的 R(沒有就 None;長的 DIG 服務被重入蓋掉,沒有 R)。"""
    es = [r for r in ERA[nm] if r[0] == "E" and r[2] == rt(entry)]
    rs = {r[1]: r for r in ERA[nm] if r[0] == "R" and r[2] == rt(entry)}
    out = []
    for e in es:
        r = rs.get(e[1])
        out.append({"n": e[5], "t": e[6], "g": None if r is None else r[4] - e[4],
                    "ng": None if r is None else (r[5] - e[5]) - (r[4] - e[4])})
    return out


# ================= (A) DIG 服務長的那幾次 = 填緩衝 =================
STATIC_A = {0x4051A: "movsx edi, word ptr [edi]", 0x40528: "cmp edi, dword ptr [eax + 0x38]", 0x4052B: "jne 0x4054e",
            0x40534: "call 0x382db", 0x4054F: "mov dword ptr [eax + 0x38], edi", 0x40552: "call 0x49923",
            0x4058D: "call 0x49690", 0x405D2: "call 0x49891", 0x4066C: "call 0x382db", 0x49931: "mov edi, dword ptr [ebx + 0x50]",
            0x49934: "mov ecx, dword ptr [ebx + 0x4c]", 0x49940: "rep stosb byte ptr es:[edi], al", 0x382E0: "call 0x3f0ac",
            0x3F0BC: "sti ", 0x3F0AA: "cli "}
for _a, _t in STATIC_A.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)


def dig_type(t: cs.Trig) -> bool:
    s = t.span()
    return t.kind == "if" and (s[0].cs, s[0].eip) == (GAME_CS, rt(0x3F0AB)) and (s[-1].cs, s[-1].eip) == (GAME_CS, rt(0x3F0BC))


def func_of(a: int) -> int:
    return ENTRIES[bisect.bisect_right(ENTRIES, a) - 1]


FILL_BLOCKS = {}
for nm in ("lc174a", "lc174b"):
    rows = []
    for t in LOG[nm].trigs:
        if not dig_type(t):
            continue
        eips = [x.eip - DELTA for x in t.span()]
        assert all(x.cs == GAME_CS for x in t.span())
        seen = set(eips)
        # 走填緩衝那條:0x4054e .. 0x40552 呼叫 0x49923、0x4058d 呼叫混音、0x405d2 輸出,結尾 0x4066c;沒填緩衝的出口 0x40534 沒走
        assert {0x4054E, 0x40552, 0x49923, 0x49940, 0x4058D, 0x405D2, 0x4066C} <= seen and 0x40534 not in seen, (nm, t.seq)
        rows.append({"seq": t.seq, "count": t.count, "per_function": collections.Counter(hex(func_of(a)) for a in eips)})
    FILL_BLOCKS[nm] = rows
assert len(FILL_BLOCKS["lc174a"]) == 7 and len(FILL_BLOCKS["lc174b"]) == 7
_pf = [r["per_function"] for rows in FILL_BLOCKS.values() for r in rows]
# 每個區塊的函式分布幾乎一樣:混音(0x49430)與輸出(0x4809b)佔九成以上;清緩衝(0x49923)五百多條
assert all(set(p) == set(_pf[0]) for p in _pf), _pf
assert all((p["0x49430"] + p["0x4809b"]) / sum(p.values()) > 0.9 and 500 < p["0x49923"] < 600 for p in _pf), _pf
PER_FUNCTION = {k: sorted({p[k] for p in _pf}) for k in sorted(_pf[0], key=lambda k: -_pf[0][k])}
# SB16.DIG 的實模式中斷處理每次 xor 緩衝號(137c:0716 xor word ptr [0x504], 1):Y 區塊碼位元組與檔案同一位移
_y375 = next(t for t in LOG["lc174a"].trigs if t.kind == "ng" and t.count == 375)
assert _y375.code[("r", 0x137C, 0x716)][:5] == DIG_FILE[0x716:0x71B] == bytes.fromhex("8336040501")


def fill_vs_irq7(nm: str) -> dict:
    """每一次 DIG 服務(初始化之後):有沒有填緩衝(沒有 R、或遊戲指令 > 1000)× 與上一次服務之間收過幾次 IRQ 7。"""
    sv = services(nm, SERVE)
    q7 = [q.n for q in LOG[nm].irqs if q.num == 0x0F and q.type == 0]
    dsp = [(x.n, x.value) for x in LOG[nm].ios if x.op == "O" and x.port == 0x22C]
    dn = [d[0] for d in dsp]
    tab = collections.Counter()
    odd = []
    for a, b in zip(sv, sv[1:]):
        if not T_AFTER_INIT <= b["t"] < T_SEGS_END:
            continue
        fill = b["g"] is None or b["g"] > 1000
        k = bisect.bisect_left(q7, b["n"]) - bisect.bisect_left(q7, a["n"])
        tab[f"{'fill' if fill else 'short'} irq7={min(k, 2)}"] += 1
        if fill != (k > 0):
            # 上一次服務到這次之間(含)寫到 DSP 的位元組
            w = [v for n, v in dsp[bisect.bisect_left(dn, a["n"]):bisect.bisect_left(dn, b["n"])]]
            odd.append({"t": round(b["t"], ndigits=2), "fill": fill, "irq7": k, "dsp": [hex(v) for v in w]})
    _in = [s for s in sv if T_AFTER_INIT <= s["t"] < T_SEGS_END]
    lens = collections.Counter(s["g"] for s in _in if s["g"] is not None and s["g"] > 1000)
    return {"table": dict(sorted(tab.items())), "odd": odd, "short_fill_lengths": dict(sorted(lens.items())),
            "fills_without_r": sum(s["g"] is None for s in _in)}


FILL = {nm: fill_vs_irq7(nm) for nm in ("lc174a", "lc174b", "lc173a")}
ODD_N = {}
for nm, f in FILL.items():
    tb = f["table"]
    assert tb["fill irq7=1"] > 100 and tb.get("fill irq7=2", 0) == 0 and tb["short irq7=0"] > 3000, (nm, tb)
    odd_fill = [o for o in f["odd"] if o["fill"]]
    odd_irq = [o for o in f["odd"] if not o["fill"]]
    # 例外:沒 IRQ 7 也填的 3 次,前面寫過 DSP 0xc6(開始放音)或 0xd4(繼續);有 IRQ 7 沒填的 3 次,前面寫過 0xd0(暫停)
    assert len(odd_fill) == 3 and all({"0xc6", "0xd4"} & set(o["dsp"]) for o in odd_fill), (nm, odd_fill)
    assert len(odd_irq) == 3 and all("0xd0" in o["dsp"] for o in odd_irq), (nm, odd_irq)
    assert tb["fill irq7=0"] == 3 and tb["short irq7=1"] == 3, (nm, tb)
    ODD_N[nm] = (len(odd_fill), len(odd_irq))
assert len(set(ODD_N.values())) == 1
# 填緩衝的長度不只一種:43928 那型(Y 區塊,沒有 R),另有有 R 的 15183 .. 15305 條這種
assert all(f["fills_without_r"] >= 50 and min(f["short_fill_lengths"]) > 15000 for f in FILL.values()), FILL


# ================= (B) 4 次「短驅動呼叫」是硬體中斷 =================
def irq_cost(nm: str) -> dict:
    """在遊戲程式碼收一次硬體中斷、回到同一個 eip:中間的非遊戲指令數,依中斷號分。"""
    lg = LOG[nm]
    R = lg.runs
    ns = [q.n for q in lg.irqs]
    out: dict = collections.defaultdict(collections.Counter)
    hits = []
    for i in range(1, len(R)):
        if R[i].cs == GAME_CS or R[i - 1].cs != GAME_CS:
            continue
        j = i
        while j < len(R) and R[j].cs != GAME_CS:
            j += 1
        if j == len(R):
            break
        n0, n1 = R[i].n_end - R[i].count + 1, R[j - 1].n_end
        cnt = sum(r.count for r in R[i:j])
        assert cnt == n1 - n0 + 1, (nm, i, j)
        qs = lg.irqs[bisect.bisect_left(ns, n0 - 1):bisect.bisect_right(ns, n1)]
        hw = [q for q in qs if q.type == 0]
        if len(hw) == 1 and hw[0].m == "P" and R[j].e0 == hw[0].eip:
            out[f"{hw[0].num:02x}"].update([cnt])
            hits.append(i)
    # 每一段只算進一次:各中斷號的次數總和 = 符合的段數
    assert sum(sum(v.values()) for v in out.values()) == len(hits), (nm, len(hits))
    return {k: dict(sorted(v.items())) for k, v in out.items()}


COST = {nm: irq_cost(nm) for nm in ("lc174a", "lc173a")}
for nm, c in COST.items():
    k9 = collections.Counter(c["09"])
    kf = collections.Counter(c["0f"])
    assert set(k9) <= {532, 533} and max(kf, key=kf.get) == 558 and sum(v for k, v in kf.items() if 558 <= k <= 560) > 0.95 * sum(kf.values()), (nm, c)
MDI167 = services("lc167a", MDI_SERVE)
# 續一百七十(ev_s170 的證據檔)列的 4 次:diag 多叫 1 次、EN 漸變相位以外 3 次
S170 = json.loads((EVIDENCE / "followups_s170_20261030.json").read_text(encoding="utf-8"))["enemy_mdi"]
S170_SHORT = [tuple(x) for x in S170["diag"]["extra"] + S170["en_extra"]["others"]]
assert S170_SHORT == [(119237.6, 532), (540499.0, 558), (542774.0, 558), (542959.0, 558)], S170_SHORT
SHORT = [next(s for s in MDI167 if round(s["t"], 1) == t) for t, _ng in S170_SHORT]
assert [s["ng"] for s in SHORT] == [ng for _t, ng in S170_SHORT]
DIG167 = services("lc167a", SERVE)
_dn = [s["n"] for s in DIG167]


def next_dig(s: dict) -> dict:
    d = DIG167[bisect.bisect_left(_dn, s["n"])]
    return {"dt_ms": round(d["t"] - s["t"], ndigits=3), "fill": d["g"] is None or d["g"] > 1000}


SHORT_ROWS = [{"t": round(s["t"], ndigits=1), "nongame": s["ng"], "next_dig": next_dig(s)} for s in SHORT]
assert [r["next_dig"]["fill"] for r in SHORT_ROWS] == [False, True, True, True] and all(r["next_dig"]["dt_ms"] < 1 for r in SHORT_ROWS)
_base = [d for d in DIG167 if 530000 <= d["t"] < 545000]
BASE_RATE = round(sum(d["g"] is None or d["g"] > 1000 for d in _base) / len(_base), ndigits=4)
assert BASE_RATE < 0.05, BASE_RATE

# ================= (C) 敵方回合結束時停一次的 MDI 服務 =================
_g = collections.Counter(s["g"] for s in MDI167 if s["g"] is not None)
SKIP = [s for s in MDI167 if s["g"] == 12]
_G_NEXT = min(g for g in _g if g != min(_g))   # 次小的遊戲指令數
assert len(SKIP) == 1 and min(_g) == 12 and _G_NEXT > 100, sorted(_g)[:3]
SK = SKIP[0]
STATIC_C = {0x43270: "push esi", 0x43271: "push edi", 0x43272: "push ebp", 0x43273: "sub esp, 0x10",
            0x43276: "mov ebp, dword ptr [esp + 0x20]", 0x4327A: "cmp dword ptr [ebp + 0x14], 0", 0x4327E: "jne 0x4398f",
            0x4398F: "add esp, 0x10", 0x43992: "pop ebp", 0x43993: "pop edi", 0x43994: "pop esi", 0x43995: "ret ",
            0x449EE: "mov eax, dword ptr [esi]", 0x449F0: "inc dword ptr [eax + 0x14]", 0x44A15: "mov eax, ebx",
            0x44A17: "shl eax, 5", 0x44A1A: "sub eax, ebx", 0x44A1C: "lea eax, [eax*4]", 0x44A23: "add ebx, eax",
            0x44A2A: "lea ebx, [ebx*8]", 0x44A36: "mov ecx, eax", 0x44A3F: "idiv ecx", 0x44A56: "dec ebp",
            0x44A5A: "mov dword ptr [eax + 0x14], ebp", 0x3B19C: "call 0x449e0",
            0x259A3: "push 0xfa0", 0x259A8: "push 0", 0x259B0: "call 0x3b124", 0x1737A: "push 0x3e8", 0x17386: "call 0x3b124",
            0x25A63: "push 0x7d0", 0x25A7A: "call 0x3b124", 0x25A51: "push 0", 0x25A5B: "call 0x3b124",
            0x1A5C3: "push 0", 0x1A5C5: "push -1", 0x1A5C7: "call 0x25977"}
for _a, _t in STATIC_C.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)
# 0x43270 .. 0x4327e 7 條 + 0x4398f .. 0x43995 5 條 = 12(另一個提早返回 [0x53718] 要 9 + 5 = 14)
assert sum(1 for a in STATIC_C if 0x43270 <= a <= 0x4327E) + sum(1 for a in STATIC_C if 0x4398F <= a <= 0x43995) == 12
# 那一次服務之前最近的 ISR 進入:暫存器(E 紀錄:eip ret esp ss eax ebx ecx edx esi edi ebp)
_isr = [r for r in ERA["lc167a"] if r[0] == "E" and r[2] == rt(ISR) and r[5] < SK["n"]][-1]
_f = _isr[3].split()
assert _f[0] == "00000ed6" and len(_f) >= 9, _f
REGS = dict(zip(("ret", "esp", "ss", "eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"), (int(x, 16) for x in _f[:10])))
MS = 0xFA0
assert REGS["ebx"] == MS * 1000 and REGS["ecx"] == 127 and (REGS["eax"], REGS["edx"]) == divmod(MS * 1000, 127), REGS
assert 0 < SK["t"] - _isr[6] < 0.1
# 4000 ms 的呼叫端只有 play_bgm(-1):其他三處是 1000 / 2000 / 0
_ep = [r for r in ERA["lc167a"] if r[0] == "R" and r[2] == rt(ENEMY_PHASE) and r[5] < _isr[5]][-1]
assert 0 < _isr[6] - _ep[6] < 0.2, (_isr[6], _ep[6])
_i = MDI167.index(SK)
_win = MDI167[_i - 3:_i + 4]
assert len(_win) == 7 and _win[3] is SK, len(_win)
SKIP_ROW = {"t": round(SK["t"], ndigits=1), "game_insns": SK["g"], "isr_t": round(_isr[6], ndigits=4),
            "isr_regs": {k: hex(v) for k, v in REGS.items() if k in ("eax", "ebx", "ecx", "edx", "esi")},
            "enemy_phase_return_t": round(_ep[6], 4), "neighbours_g": [s["g"] for s in _win],
            "game_insn_hist_low": {g: _g[g] for g in (min(_g), _G_NEXT)}}

CONC = {
    "dig_fill": f"DIG 服務長的那幾次是填緩衝:lc174a / lc174b 各 {len(FILL_BLOCKS['lc174a'])} 個 Y 區塊都走 0x4054e → 0x49923 清建構緩衝 "
                f"({min(PER_FUNCTION['0x49923'])} .. {max(PER_FUNCTION['0x49923'])} 條)→ 0x49690 混音 → 0x49891 輸出,結尾在 0x4066c 恢復 IF,沒走 0x40534"
                f"(續一百七十三寫的 0x40534 是不填緩衝的出口,更正)。三份紀錄填不填與兩次服務之間收過 IRQ 7 一一對應"
                f"(lc174a 有 IRQ 7 而填 {FILL['lc174a']['table']['fill irq7=1']} 次),例外各 {ODD_N['lc174a'][0]} + {ODD_N['lc174a'][1]} 次:DSP 0xc6 / 0xd4 之後沒 IRQ 也填、0xd0 之後有 IRQ 也不填。"
                f"SB16.DIG 的 IRQ 處理在 137c:0716 xor 緩衝號;遊戲讀的 [drv+0x34] 是不是就是這個字沒有直接看到(INFERRED)。",
    "short_calls": f"續一百七十的 4 次短驅動呼叫是 MDI 服務期間收到的硬體中斷:在遊戲程式碼收一次 IRQ 1 是 532 / 533 條非遊戲指令、IRQ 7 是 558 .. 560"
                   f"(lc174a / lc173a);lc167a 那 3 次 558 之後 1 ms 內的 DIG 服務都是填緩衝(同時段填緩衝比例 {BASE_RATE}),532 那次不是。"
                   f"lc167a 沒有 I 紀錄,中斷號是由條數與 DIG 填緩衝推的(INFERRED)。",
    "enemy_end_skip": f"敵方回合結束時停一次的是 {SKIP_ROW['t']} ms 那次 MDI 服務:只跑 {SK['g']} 條遊戲指令(整份唯一),0x4327e 看到驅動結構 [+0x14] ≠ 0 提早返回。"
                      f"前一筆 ISR 進入時 eax {SKIP_ROW['isr_regs']['eax']}、ebx {SKIP_ROW['isr_regs']['ebx']}、ecx {SKIP_ROW['isr_regs']['ecx']}、"
                      f"edx {SKIP_ROW['isr_regs']['edx']} = ail_impl_set_sequence_volume 在 0x44a3f idiv 之後(4000 ms × 1000 / 127),[+0x14] 在 0x449f0 加一、"
                      f"0x44a5a 才減回;4000 ms 只有 play_bgm(-1) 的 0x259a3。敵方回合 0x1d8ba 在前 {round(_isr[6] - _ep[6], 4)} ms 返回。"
                      f"續一百七十三推的「序列狀態 ≠ 4」更正為整次服務被 AIL 的忙碌計數擋掉。",
}
for _part, _key in (("走 0x4054e → 0x49923", "dig_fill"), ("例外各 3 + 3 次", "dig_fill"), ("IRQ 1 是 532 / 533", "short_calls"),
                    ("只跑 12 條遊戲指令", "enemy_end_skip"), ("eax 0x7b08、ebx 0x3d0900、ecx 0x7f、edx 0x8", "enemy_end_skip")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s175.py"),
    "exe_md5": MD5,
    "calllogs": {nm: {"path": rel(p), "md5": LOG_MD5[nm]} for nm, p in RAW.items()},
    "a_dig_fill": {"y_blocks": {nm: [{"seq": r["seq"], "count": r["count"]} for r in rows] for nm, rows in FILL_BLOCKS.items()},
                   "per_function": PER_FUNCTION, "fill_vs_irq7": FILL},
    "b_short_calls": {"irq_cost_in_game_code": COST, "lc167a_short": SHORT_ROWS, "lc167a_fill_rate_530_545s": BASE_RATE},
    "c_enemy_end_skip": SKIP_ROW,
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, {nm: f["table"] for nm, f in FILL.items()}, SHORT_ROWS, SKIP_ROW["t"])
