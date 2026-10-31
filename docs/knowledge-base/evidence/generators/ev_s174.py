"""續一百七十四證據:evidence/trig_capture_s174_20261031.json(觸發式擷取 FD2_CALLLOG_TRIG 的實機核對與 P3 三型的解讀)。

使用者 2026-10-31「先完善優化工具」→「還沒做的事 請逐項進行處理」。工具:tools/dosbox/fd2_calllog_patch.py 的 FD2_CALLLOG_TRIG
(ng = 非遊戲 selector 的連續指令、if = 開始執行時 IF = 0 的連續指令;條數符合規則才寫 Y .. YE);tools/calllog_segments.py trig。
實機 lc174a / lc174b(原版 FD2.EXE、WSL -d Ubuntu、開機 → 標題 → START → 16 秒;drivers_s174/lc174.py;預測 drivers_s174/pred174.txt)。
(A) P1 / P2 / P4 / P5 / P6(drivers_s174/check174.py 的判準,改成產生器):區塊完整、DIG 服務長關中斷 7 次與 G 一致、被砍掉後的統計、
    時間窗、START 那一下 DIG 關中斷 → DOS/4GW 返回段收 IRQ 1。
(B) P3 ng 375 = 續一百六十五的 MDI 375:重入 ISR 之後那段非遊戲指令,MDI 型(回到 0x3f1a4)沒有中斷時 302 / 303,
    中間收到一次 IRQ 7(實模式 0c5c:1fad,SB16.DIG 的實模式中斷處理 137c:0682 .. 0729 共 73 條)就是 375 = 302 + 73。
(C) P3 0070 起頭的 if 區間 = DOS/4GW 的 int 21h AH=40h 轉送:spawn_group(0x10b4e)把精靈快取 0x32a00 bytes 寫進 FD2.TMP,
    DOS/4GW(FD2.EXE 檔內 0x9ae0 + 0070 位移)在 0x0eb4 cli 後把每塊約 8 KB 拷到轉送緩衝、切實模式,到 0c5c:10b4 popf 才開中斷(甲型);
    IRQ 0 在這段裡到就積著,popf 一開就收,反射到遊戲 ISR、直到 0x3eb15 sti 都關著(乙型)。續一百七十三 9262 ms 那次是讀檔(AH=3Fh,0x0e02)
    回來後拷回使用者緩衝那段(0x0e6a sti 之前)。
(D) P3 ng 600 .. 604 的 0080:0084 型:delay(0x3e01d)的 int 21h AH=2Ch,IRQ 0 落在 DOS/4GW 保護模式的 int 21h 入口段,
    之後反射到遊戲 ISR 固定 237 條;600 .. 604 只是這一型連續分布(583 .. 14289)裡被規則選到的一段。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import re
import struct

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("trig_capture_s174_20261031.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DRV = GEN_DIR / "drivers_s174"
RAW = ROOT / ".wsl_build" / "lc174_live"
RAW173 = ROOT / ".wsl_build" / "lc173_live"
LOG_MD5 = {"lc174a": "0aaee51798ec85a779a95aa78ed85cac", "lc174b": "9be49f776cc0ed2fbbc3d7e962503b14",
           "lc173a": "3a8bb8b852d99b3f6307a64306408efb"}
DELTA = 0x19C000                       # 遊戲 selector 的執行期位址 = 靜態 + DELTA(同 ev_s173)
GAME_CS = 0x170
TRIG = "if:40000-,ng:600-604,ng:375,if:1000-2000@0070"
D4G = 0x9AE0                           # DOS/4GW 的 0070 selector 位移 X 在 FD2.EXE 檔內的位置 = D4G + X(由 Y 區塊的碼位元組定位)

assert hashlib.md5(_EXE).hexdigest() == MD5
_drv_src = (DRV / "lc174.py").read_text(encoding="utf-8")
assert f'TRIG = {{"lc174a": "{TRIG}", "lc174b": "{TRIG}"}}' in _drv_src and 'TRIGT = {"lc174b": "9500-24000"}' in _drv_src
assert 'TRIGCAP = {"lc174a": "8", "lc174b": "8"}' in _drv_src


def _load(name: str, path) -> cs.Log:
    """先比 md5(teardown 之後的指紋)再解析;檔尾寫到一半的那一行由 calllog_segments._read 丟掉。"""
    assert hashlib.md5(path.read_bytes()).hexdigest() == LOG_MD5[name], name
    return cs._read(str(path))


LA = _load("lc174a", RAW / "lc174a_CALLLOG.TXT")
LB = _load("lc174b", RAW / "lc174b_CALLLOG.TXT")
L3 = _load("lc173a", RAW173 / "lc173a_CALLLOG.TXT")
LOGS = {"lc174a": LA, "lc174b": LB, "lc173a": L3}
assert all(lg.game_cs == GAME_CS for lg in LOGS.values())
DIG_FILE = (GAME / "SB16.DIG").read_bytes()


def rt(a: int) -> int:
    return a + DELTA


def ends(t: cs.Trig) -> tuple[cs.Insn, cs.Insn, cs.Insn]:
    """區間第一條、最後一條、結束那一條。"""
    s = t.span()
    return s[0], s[-1], next(x for x in t.insns if x.n == t.n1 + 1)


def at(x) -> tuple[str, int, int]:
    return (x.m, x.cs, x.eip)


def dig_type(t: cs.Trig) -> bool:
    """DIG 服務的長關中斷:ret(0x3f0ab,0x3f0aa cli 之後).. sti(0x3f0bc),結束那一條 pop ebp(0x3f0bd,IF = 1)。"""
    f, last, a = ends(t)
    return (t.kind == "if" and (f.cs, f.eip) == (GAME_CS, rt(0x3F0AB)) and (last.cs, last.eip) == (GAME_CS, rt(0x3F0BC))
            and (a.cs, a.eip, a.iff) == (GAME_CS, rt(0x3F0BD), 1))


def irqs_in(lg: cs.Log, n0: int, n1: int) -> list[cs.Irq]:
    """n 在 [n0, n1] 的 I 紀錄(依檔案次序)。"""
    ns = [q.n for q in lg.irqs]
    return lg.irqs[bisect.bisect_left(ns, n0):bisect.bisect_right(ns, n1)]


# ================= (A) P1 / P2 / P4 / P5 / P6 =================
for _nm, _lg in (("lc174a", LA), ("lc174b", LB)):
    _h = (RAW / f"{_nm}_CALLLOG.TXT").open(encoding="ascii").readline().rstrip("\n")
    _m = re.fullmatch(r"H fd2calllog .* trig=" + re.escape(TRIG) + r" trigring=131072 trigpre=64 trigcap=8( trigt=9500-24000)?", _h)
    assert _m and bool(_m.group(1)) == (_nm == "lc174b"), _h
# P1:每個區塊都有 YE,解析端另寫的判準沒有問題
for _nm, _lg in (("lc174a", LA), ("lc174b", LB)):
    assert _lg.trigs and all(t.complete for t in _lg.trigs), _nm
    _bad = {t.seq: cs.trig_problems(t, _lg.game_cs) for t in _lg.trigs if cs.trig_problems(t, _lg.game_cs)}
    assert _bad == {}, (_nm, _bad)
# lc174a 用的是修正前的二進位:被砍掉 -> 沒有 YC / YN,最後一行寫到一半
assert LA.tail_cut and LA.trig_counts == {} and LA.trig_spans == {}
# P2:DIG 型 if 區塊,區間全在 cs 0170;同一份紀錄的 G 一筆涵蓋 ISR 進入 .. 結束那一條,條數 = 前段 + 區間 + 1
DIG_A = [t for t in LA.trigs if dig_type(t)]
assert collections.Counter(t.count for t in DIG_A) == collections.Counter({43928: 6, 43929: 1}), [(t.seq, t.count) for t in DIG_A]
G_ROWS = []
for t in DIG_A:
    assert all((x.m, x.cs) == ("P", GAME_CS) for x in t.span())
    ov = [r for r in LA.runs if r.n_end >= t.n0 and r.n_end - r.count < t.n1 + 1]
    assert len(ov) == 1 and (ov[0].m, ov[0].cs, ov[0].e1) == ("P", GAME_CS, rt(0x3F0BD)), t.seq
    r = ov[0]
    assert r.n_end - r.count + 1 < t.n0 and r.n_end == t.n1 + 1
    G_ROWS.append({"seq": t.seq, "g_count": r.count, "pre": t.n0 - (r.n_end - r.count + 1), "span": t.count, "g_e0": hex(r.e0 - DELTA)})
assert all(g["g_count"] == g["pre"] + g["span"] + 1 for g in G_ROWS) and min(g["g_count"] for g in G_ROWS) < 44077
assert collections.Counter(g["g_e0"] for g in G_ROWS) == collections.Counter({"0x3ea8e": 5, "0x3f1a4": 2}), G_ROWS
# P4:lc174b 被砍掉後仍有最後一組統計;寫出數 = 區塊數 <= 符合數
_nb = collections.Counter(t.rule for t in LB.trigs)
assert LB.tail_cut and set(LB.trig_counts) == {0, 1, 2, 3} and set(LB.trig_spans) == {"ng", "if"}
assert all(w == _nb.get(r, 0) and w <= m for r, (_k, m, w) in LB.trig_counts.items()), (LB.trig_counts, _nb)
YC_B = {str(r): {"kind": k, "matched": m, "written": w} for r, (k, m, w) in sorted(LB.trig_counts.items())}
# P5:TRIGT 9500-24000
assert min(t.t1 for t in LB.trigs) >= 9500
# P6:START 放開鍵之後 10 ms 內:DIG 型 if 區塊結束,接著 ng 600 .. 604(0080:0ed6 起、0x3f0be 結束、IRQ 1 在 0080:06ca)
_tb = [k.t for k in LB.keys if k.data == 0x09C][-1]
_p6_if = [t for t in LB.trigs if dig_type(t) and _tb < t.t1 < _tb + 10]
_p6_ng = [t for t in LB.trigs if t.kind == "ng" and 600 <= t.count <= 604 and _tb < t.t1 < _tb + 10
          and (ends(t)[0].cs, ends(t)[0].eip) == (0x80, 0xED6) and (ends(t)[2].cs, ends(t)[2].eip) == (GAME_CS, rt(0x3F0BE))
          and any((q.num, q.cs, q.eip) == (9, 0x80, 0x6CA) for q in t.irqs)]
assert len(_p6_if) == 1 and len(_p6_ng) == 1 and _p6_if[0].t1 <= _p6_ng[0].t0, (_p6_if, _p6_ng)
_irq1 = next(q for q in _p6_ng[0].irqs if q.num == 9)
_a_ng = [t for t in LA.trigs if t.kind == "ng" and (ends(t)[0].cs, ends(t)[0].eip) == (0x80, 0xED6)
         and any((q.num, q.cs, q.eip) == (9, 0x80, 0x6CA) for q in t.irqs)]
assert [(t.seq, t.count) for t in _a_ng] == [(13, 601)], _a_ng
P6 = {"break_ms": round(_tb, 4), "dig_if": {"seq": _p6_if[0].seq, "t0": round(_p6_if[0].t0, 4), "t1": round(_p6_if[0].t1, 4),
                                             "count": _p6_if[0].count},
      "ng": {"seq": _p6_ng[0].seq, "count": _p6_ng[0].count, "irq1_ms": round(_irq1.t, 4), "irq1_after_break_ms": round(_irq1.t - _tb, 4)},
      "lc174a_same_type": [_a_ng[0].seq, _a_ng[0].count]}


# ================= (B) P3:ng 375 = MDI 型重入 + IRQ 7 =================
def reentry_spans(lg: cs.Log) -> dict:
    """重入 ISR(G 一筆 0x3ea8e .. 0x3ebb3 共 7 條)之後那段非遊戲指令:依回到遊戲的位置與段內的中斷分類,值是條數的分布。"""
    out: dict = collections.defaultdict(collections.Counter)
    first: dict = {}
    R = lg.runs
    for i in range(1, len(R)):
        p = R[i - 1]
        if not ((p.m, p.cs, p.e0, p.e1, p.count) == ("P", GAME_CS, rt(0x3EA8E), rt(0x3EBB3), 7) and R[i].cs != GAME_CS):
            continue
        j = i
        while j < len(R) and R[j].cs != GAME_CS:
            j += 1
        if j == len(R):
            break
        n0, n1 = R[i].n_end - R[i].count + 1, R[j - 1].n_end
        key = (f"{R[i].m} {R[i].cs:04x}:{R[i].e0:x}", hex(R[j].e0 - DELTA),
               tuple(f"{q.num:02x} {q.m}" for q in irqs_in(lg, n0 - 1, n1)))
        out[key][n1 - n0 + 1] += 1
        first.setdefault((key, n1 - n0 + 1), n0)
    return {"classes": {k: dict(sorted(v.items())) for k, v in out.items()}, "n0": first}


REENT = {nm: reentry_spans(lg) for nm, lg in LOGS.items()}
for nm, rs in REENT.items():
    cl = rs["classes"]
    # 每一型都從 DOS/4GW 返回段 0080:0ed6 起;DIG 型(回到 sti 之後的 0x3f0be)69 / 70、MDI 型(回到 int 31h 之後的 0x3f1a4)302 / 303
    assert all(k[0] == "p 0080:ed6" for k in cl), (nm, cl)
    assert set(cl[("p 0080:ed6", "0x3f0be", ())]) <= {69, 70} and set(cl[("p 0080:ed6", "0x3f1a4", ())]) <= {302, 303}, (nm, cl)
    # DIG 型中間收到鍵盤 IRQ 1(保護模式 int 9 + 實模式 int 15h)就是 601 / 602(續一百七十二 / 一百七十三)
    assert set(cl[("p 0080:ed6", "0x3f0be", ("09 p", "15 r"))]) <= {601, 602}, (nm, cl)
# 第三種回到點:lc174a 一次回到 ISR 自己的派送迴圈(0x3eb46 add edi, 4 之後的 0x3eb49),條數同 DIG 型 69 —— 69 是回保護模式遊戲程式碼的共同返回段
_other = {nm: {k: v for k, v in rs["classes"].items() if k[1] not in ("0x3f0be", "0x3f1a4")} for nm, rs in REENT.items()}
assert _other == {"lc174a": {("p 0080:ed6", "0x3eb49", ()): {69: 1}}, "lc174b": {}, "lc173a": {}}, _other
assert insn(0x3EB46) == "add edi, 4" and insn(0x3EB49) == "cmp edi, 0x3c" and insn(0x3EB4C) == "jb 0x3eb24" and insn(0x3EB15) == "sti "
_c375 = {nm: {k: v for k, v in rs["classes"].items() if 375 in v} for nm, rs in REENT.items()}
assert _c375["lc174b"] == {} and _c375["lc173a"] == {}
assert _c375["lc174a"] == {("p 0080:ed6", "0x3f1a4", ("0f r",)): {375: 1}}, _c375
_n375 = REENT["lc174a"]["n0"][(("p 0080:ed6", "0x3f1a4", ("0f r",)), 375)]
Y375 = next(t for t in LA.trigs if t.kind == "ng" and t.count == 375)
assert Y375.n0 == _n375 and Y375.rule == 2
# 區塊裡:實模式 0c5c:1fad 收 IRQ 7(int 0fh),137c 段跑 73 條,最後一條 iret 回 0c5c:1fad
_iq = [q for q in Y375.irqs if Y375.n0 <= q.n <= Y375.n1]
assert [(q.num, q.type, q.m, q.cs, q.eip) for q in _iq] == [(0x0F, 0, "r", 0x0C5C, 0x1FAD)], _iq
_drv = [x for x in Y375.span() if x.cs == 0x137C]
assert len(_drv) == 375 - 302 == 73 and all(x.m == "r" for x in _drv)
_d_first, _d_last = _drv[0].eip, _drv[-1].eip
assert (_d_first, _d_last) == (0x682, 0x729) and Y375.code[("r", 0x137C, 0x729)][0] == 0xCF   # iret
# 碼位元組 = SB16.DIG 檔案同一位移(驅動以位移 0 載入,同 ev_s173 (C));對照:換成 0c5c 段的位移就對不上
_cb = {x.eip: Y375.code[("r", 0x137C, x.eip)] for x in _drv if Y375.code.get(("r", 0x137C, x.eip))}
assert _cb and all(DIG_FILE[e:e + len(b)] == b[:len(DIG_FILE[e:e + len(b)])] for e, b in _cb.items())
_after = [x for x in Y375.span() if x.n == _drv[-1].n + 1]
assert [at(x) for x in _after] == [("r", 0x0C5C, 0x1FAD)]
MDI375 = {"lc174a": {"seq": Y375.seq, "t0": round(Y375.t0, 4), "count": Y375.count, "irq": "0f r 0c5c:1fad",
                     "dig_handler": {"cs": "137c", "first": hex(_d_first), "last": hex(_d_last), "insns": len(_drv),
                                     "code_bytes_match_file": len(_cb)}},
          "classes": {nm: {f"{a} -> {b} {list(c)}": v for (a, b, c), v in rs["classes"].items()} for nm, rs in REENT.items()}}


# ================= (C) P3:0070 if 區間 = DOS/4GW int 21h 的轉送拷貝 =================
def d4g(x: int, n: int) -> bytes:
    return _EXE[D4G + x:D4G + x + n]


# 靜態(FD2.EXE 內的 DOS/4GW):int 21h 分派表 cs:[0x66a + (AH + 1) * 2](0x0ce6 inc ah .. 0x0cf7 jmp)
assert d4g(0xCE6, 2) == b"\xfe\xc4" and d4g(0xCF7, 5) == b"\x2e\xff\xa5\x6a\x06"
HANDLER = {ah: struct.unpack_from("<H", _EXE, D4G + 0x66A + (ah + 1) * 2)[0] for ah in (0x3F, 0x40)}
assert HANDLER == {0x3F: 0xE02, 0x40: 0xE7F}, HANDLER
H_READ, H_WRITE = HANDLER[0x3F], HANDLER[0x40]
assert (H_READ, H_WRITE) == (0xE02, 0xE7F)
# 寫(0x0e7f):0x0e92 sti … 0x0eb4 cli、rep movsw / movsb 拷到轉送緩衝、0x0ed9 call 0xd73(cli、pushaw、ljmp 0x18:0x1068 切實模式)
# 讀(0x0e02):0x0e1e sti … 0x0e36 call 0xd73(實模式讀)… 回來拷回使用者緩衝 0x0e64 rep movsw、0x0e68 rep movsb、0x0e6a sti
D4G_BYTES = {0xE92: b"\xfb", 0xEB4: b"\xfa", 0xED2: b"\xf3\xa5", 0xED6: b"\xf3\xa4", 0xED9: b"\xe8\x97\xfe",
             0xD7A: b"\xfa\x60\xea\x68\x10\x18\x00", 0xE1E: b"\xfb", 0xE36: b"\xe8\x3a\xff", 0xE64: b"\xf3\xa5", 0xE68: b"\xf3\xa4",
             0xE6A: b"\xfb", 0xE21: b"\x3b\x0e\x0e\x00", 0xE9C: b"\x3b\x0e\x0e\x00"}
for _a, _b in D4G_BYTES.items():
    assert d4g(_a, len(_b)) == _b, (hex(_a), d4g(_a, len(_b)).hex())
# 檔內位置的對照:Y 區塊帶的 0070 碼位元組在 int 21h 分派 / 轉送那一帶(0x0c9e .. 0x0ef4)逐一等於 FD2.EXE 的 D4G + 位移;
# 不同的只在 0x4000 之後(執行時才填的 IRQ 反射跳板);對照:錯一個位元組就全部對不上
_c70 = {k: v for t in LA.trigs for k, v in t.code.items() if k[1] == 0x70 and v}
_c70_int21 = {k: v for k, v in _c70.items() if 0xC9E <= k[2] <= 0xEF4}
assert len(_c70_int21) > 60 and all(d4g(k[2], len(v)) == v for k, v in _c70_int21.items())
_c70_diff = sorted(k[2] for k, v in _c70.items() if d4g(k[2], len(v)) != v)
assert _c70_diff and min(_c70_diff) >= 0x4000, [hex(e) for e in _c70_diff]
assert sum(1 for k, v in _c70.items() if _EXE[D4G + 1 + k[2]:D4G + 1 + k[2] + len(v)] == v) == 0
# 遊戲端:spawn_group(0x10b4e)結尾 fopen("FD2.TMP", "wb")、fwrite([0x53a61], 1, 0x32a00, fp);write(0x3d3e5)二進位模式 AH=40h
GAME_STATIC = {0x10C19: "push 0xd3", 0x10C1E: "push 0xd6", 0x10C23: "call 0x37324", 0x10C2E: "push 0x32a00", 0x10C33: "push 1",
               0x10C35: "push dword ptr [0x3a61]", 0x10C3B: "call 0x377a3", 0x3D470: "mov ah, 0x40", 0x3D472: "int 0x21",
               0x3E04B: "mov ah, 0x2c", 0x3E04D: "int 0x21"}
for _a, _t in GAME_STATIC.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)
assert _EXE.find(b"\x00wb\x00FD2.TMP\x00rb\x00") >= 0
TMP_LEN, CHUNK = 0x32A00, 8192
assert insn(0x10C2E) == f"push {TMP_LEN:#x}", insn(0x10C2E)


def write_chunks(lg: cs.Log) -> dict:
    """遊戲唯一一次 write(int 21h 在 0x3d472,I 紀錄的 eip 是下一條 0x3d474)到下一次遊戲 int 21h 之間的 0070 拷貝段。"""
    gi = [q for q in lg.irqs if q.num == 0x21 and q.type == 1 and q.cs == GAME_CS]
    w = [q for q in gi if q.eip == rt(0x3D474)]
    assert len(w) == 1, w
    nxt = gi[gi.index(w[0]) + 1]
    ch = [r for r in lg.runs if w[0].n < r.n_end <= nxt.n and (r.m, r.cs, r.e0, r.e1) == ("p", 0x70, 0xC9E, 0xD7C)]
    hw = [q for q in irqs_in(lg, w[0].n, nxt.n) if q.type == 0]
    return {"t_ms": round(w[0].t, 4), "next_int21_ms": round(nxt.t, 4), "next_int21_at": hex(nxt.eip - DELTA),
            "chunks": [r.count for r in ch], "hw_irqs": collections.Counter(f"{q.num:02x} {q.m} {q.cs:04x}:{q.eip:x}" for q in hw)}


WRITE = {nm: write_chunks(lg) for nm, lg in (("lc174a", LA), ("lc174b", LB))}
for nm, w in WRITE.items():
    ch = w["chunks"]
    # 26 塊 = 25 塊滿的 + 最後一塊;塊大小 S 滿足 ceil(0x32a00 / S) = 26
    assert len(ch) == 26 == -(-TMP_LEN // CHUNK) and min(ch[:-1]) >= 1000 > ch[-1], (nm, ch)
    # 拷貝那段關著中斷:IRQ 0 只在實模式 popf 之後(0c5c:10b5)收,沒有一個落在 0070 拷貝段
    assert w["hw_irqs"]["08 r 0c5c:10b5"] == 7, (nm, w["hw_irqs"])
    assert not [k for k in w["hw_irqs"] if " 0070:" in k and 0xEB5 <= int(k.split(":")[1], 16) <= 0xED9], w["hw_irqs"]
    assert w["next_int21_at"] == "0x3cf70"          # 下一次遊戲 int 21h 是 lseek(寫完之後)
# 最後一塊的拷貝量:滿塊 Y 區塊裡 rep movsw 的紀錄筆數 1042,其餘(固定部分)= 塊條數 − 1042
Y_WR = {nm: [t for t in lg.trigs if t.rule == 3] for nm, lg in (("lc174a", LA), ("lc174b", LB))}
_y17 = next(t for t in Y_WR["lc174a"] if t.seq == 17)
_rep = sum(1 for x in _y17.insns if at(x) == ("p", 0x70, 0xED2) and x.n < _y17.n0 + 1100)
_fixed = WRITE["lc174a"]["chunks"][1] - _rep
LAST_RATIO = {nm: round((w["chunks"][-1] - _fixed) / _rep, ndigits=4) for nm, w in WRITE.items()}
_expect = round((TMP_LEN - 25 * CHUNK) / CHUNK, 4)
assert _rep == 1042 and all(abs(v - _expect) < 0.005 for v in LAST_RATIO.values()), (_rep, _fixed, LAST_RATIO, _expect)
_chunk_fit = TMP_LEN / (len(WRITE["lc174a"]["chunks"]) - 1 + sum(LAST_RATIO.values()) / len(LAST_RATIO))
assert round(_chunk_fit) == CHUNK, _chunk_fit


def wtype(t: cs.Trig) -> dict:
    """甲型:在實模式 0c5c:10b4 popf 結束;乙型:popf 一開就收 IRQ 0,一路到遊戲 ISR 0x3eb15 sti 才結束。"""
    f, last, a = ends(t)
    assert at(f) == ("p", 0x70, 0xEB5), at(f)
    q8 = [q for q in t.irqs if t.n0 <= q.n <= t.n1 and q.type == 0]
    if not q8:
        assert at(last) == ("r", 0x0C5C, 0x10B4) and a.iff == 1, (t.seq, at(last))
        return {"seq": t.seq, "type": "a", "count": t.count, "ms": round(t.t1 - t.t0, 4)}
    assert [(q.num, q.m, q.cs, q.eip) for q in q8] == [(8, "r", 0x0C5C, 0x10B5)] and at(last) == ("P", GAME_CS, rt(0x3EB15)), t.seq
    pop = next(x for x in t.span() if at(x) == ("r", 0x0C5C, 0x10B4))
    w = {"seq": t.seq, "type": "b", "count": t.count, "ms": round(t.t1 - t.t0, 4), "to_popf": pop.n - t.n0 + 1,
         "after_popf": t.n1 - pop.n}
    assert w["to_popf"] + w["after_popf"] == t.count == t.n1 - t.n0 + 1, w
    return w


WTYPES = {nm: [wtype(t) for t in ys] for nm, ys in Y_WR.items()}
for nm, ws in WTYPES.items():
    a_ = [w for w in ws if w["type"] == "a"]
    b_ = [w for w in ws if w["type"] == "b"]
    assert a_ and b_ and len(ws) == 8, (nm, ws)
    # 乙型到 popf 為止的條數與甲型同一群(差不到 20 條,塊間拷貝的紀錄筆數本來就差十幾條);popf 之後(收 IRQ 0、反射、ISR 到 sti)差不到 4 條(ISR 每次溢位多 2 條,續一百六十五)
    _pre = [w["count"] for w in a_] + [w["to_popf"] for w in b_]
    assert max(_pre) - min(_pre) <= 20, (nm, _pre)
    assert max(w["after_popf"] for w in b_) - min(w["after_popf"] for w in b_) <= 4, b_
    # 每個區塊都在那一次寫檔裡
    assert all(WRITE[nm]["t_ms"] < t.t0 < WRITE[nm]["next_int21_ms"] for t in Y_WR[nm])
A_MS = sorted({w["ms"] for ws in WTYPES.values() for w in ws if w["type"] == "a"})
FULL_N = sum(c >= 1000 for c in WRITE["lc174a"]["chunks"])
assert FULL_N == len(WRITE["lc174a"]["chunks"]) - 1, FULL_N
AFTER_POPF = sorted({w["after_popf"] for ws in WTYPES.values() for w in ws if w["type"] == "b"})
assert AFTER_POPF[-1] - AFTER_POPF[0] <= 4 and AFTER_POPF[0] > 400, AFTER_POPF
# lc174b 的規則 3(if:1000-2000@0070)在 9500 ms 之後符合 25 次 = 寫檔的 25 塊滿塊(最後一塊不到 1000 條)
assert YC_B["3"]["matched"] == 25 == sum(1 for c in WRITE["lc174b"]["chunks"] if c >= 1000)


def read_runs(lg: cs.Log) -> dict:
    """讀檔回來拷回使用者緩衝(0070:0d81 .. 0e6b):每段之前最近一次遊戲 int 21h 的位置;IRQ 不落在 0x0e39 .. 0x0e6a。"""
    gi = [q for q in lg.irqs if q.num == 0x21 and q.type == 1 and q.cs == GAME_CS]
    gn = [q.n for q in gi]
    rr = [r for r in lg.runs if (r.m, r.cs, r.e0, r.e1) == ("p", 0x70, 0xD81, 0xE6B)]
    src = collections.Counter(hex(gi[bisect.bisect_left(gn, r.n_end) - 1].eip - DELTA) for r in rr)
    land = collections.Counter(q.eip for q in lg.irqs if q.type == 0 and (q.m, q.cs) == ("p", 0x70))
    return {"runs": len(rr), "max_count": max(r.count for r in rr), "after_int21_at": dict(src),
            "irq_inside_copy": sum(v for e, v in land.items() if 0xE39 <= e <= 0xE6A), "irq_at_e6c": land[0xE6C]}


READ = {nm: read_runs(lg) for nm, lg in LOGS.items()}
for nm, r in READ.items():
    # 全部接在 dos_read(0x3dce0)的 int 21h(0x3dcf2,I 的 eip 0x3dcf4)之後;拷貝段沒收過中斷,sti 之後一條(0x0e6c)收過
    assert set(r["after_int21_at"]) == {"0x3dcf4"} and r["irq_inside_copy"] == 0 and r["irq_at_e6c"] > 0, (nm, r)
assert insn(0x3DCF0) == "mov ah, 0x3f" and insn(0x3DCF2) == "int 0x21"
# 續一百七十三 9262 ms 那次(lc173a):按鍵前就開始的 0070:0d81 .. 0e6b 一段 1070 條,接在 dos_read 之後,結束後收 IRQ 0
_k9262 = next(k for k in L3.keys if 9262 <= k.t < 9263)
_r9262 = next(r for r in L3.runs if (r.m, r.cs, r.e0, r.e1) == ("p", 0x70, 0xD81, 0xE6B) and r.n_end - r.count < _k9262.n < r.n_end)
_q9262 = irqs_in(L3, _r9262.n_end, _r9262.n_end + 1)
assert _r9262.count == 1070 and [(q.num, q.m, q.cs, q.eip) for q in _q9262] == [(8, "p", 0x70, 0xE6C)], (_r9262, _q9262)
READ["lc173a_9262"] = {"count": _r9262.count, "key_ms": round(_k9262.t, 4), "irq0_ms": round(_q9262[0].t, 4)}


# ================= (D) P3:ng 600 .. 604 的 0080:0084 型 =================
NG_LO, NG_HI = map(int, re.search(r"ng:(\d+)-(\d+)", TRIG).groups())


def int21_spans(lg: cs.Log) -> dict:
    """從 DOS/4GW 保護模式 int 21h 入口 0080:0084 開始、直接進遊戲 ISR(0x3ea8e)的非遊戲段:條數 = IRQ 0 之前 + 之後。"""
    R = lg.runs
    rows = []
    for i in range(1, len(R)):
        if not ((R[i].m, R[i].cs, R[i].e0) == ("p", 0x80, 0x84) and R[i - 1].cs == GAME_CS):
            continue
        j = i
        while j < len(R) and R[j].cs != GAME_CS:
            j += 1
        if j == len(R) or R[j].e0 != rt(0x3EA8E):
            continue
        n0, n1 = R[i].n_end - R[i].count + 1, R[j - 1].n_end
        cnt = sum(r.count for r in R[i:j])
        assert cnt == n1 - n0 + 1, (i, j)
        qs = irqs_in(lg, n0 - 1, n1)
        sw = [q for q in qs if q.type == 1 and q.cs == GAME_CS]
        hw = [q for q in qs if q.type == 0]
        rows.append({"count": cnt, "from": hex(sw[0].eip - DELTA) if sw else None, "hw": len(hw),
                     "post": n1 - hw[-1].n + 1 if hw else None})
    return {"spans": len(rows), "min": min(r["count"] for r in rows), "max": max(r["count"] for r in rows),
            "in_600_604": sum(NG_LO <= r["count"] <= NG_HI for r in rows),
            "from": dict(collections.Counter(r["from"] for r in rows).most_common()),
            "post_one_irq": dict(collections.Counter(r["post"] for r in rows if r["hw"] == 1).most_common(4)),
            "rows": rows}


I21 = {nm: int21_spans(lg) for nm, lg in (("lc174a", LA), ("lc174b", LB))}
for nm, s in I21.items():
    _one = [r for r in s["rows"] if r["hw"] == 1]
    # 幾乎全是 delay 的 int 21h AH=2Ch(0x3e04d,I 的 eip 0x3e04f);只收一次 IRQ 0 的,IRQ 之後到 ISR 進入大多 237 條
    assert max(s["from"], key=s["from"].get) == "0x3e04f" and s["from"]["0x3e04f"] > 0.9 * s["spans"], (nm, s["from"])
    assert max(s["post_one_irq"], key=s["post_one_irq"].get) == 237 and s["post_one_irq"][237] > 0.9 * len(_one), s["post_one_irq"]
    # 600 .. 604 是連續分布的一小段
    assert s["min"] < NG_LO and s["max"] > 10000 and 0 < s["in_600_604"] < 0.05 * s["spans"], (nm, s["min"], s["max"], s["in_600_604"])
Y0084 = {}
for nm, lg in (("lc174a", LA), ("lc174b", LB)):
    for t in lg.trigs:
        if t.kind == "ng" and (t.cs, t.eip) == (0x80, 0x84):
            sw = [q for q in t.irqs if q.type == 1]
            hw = [q for q in t.irqs if q.type == 0 and t.n0 <= q.n <= t.n1]
            assert [(q.num, q.cs, q.eip) for q in sw] == [(0x21, GAME_CS, rt(0x3E04F))] and [q.num for q in hw] == [8], (nm, t.seq)
            assert at(ends(t)[2]) == ("P", GAME_CS, rt(0x3EA8E)) and t.n1 - hw[0].n + 1 == 237, (nm, t.seq)
            Y0084[f"{nm}#{t.seq}"] = {"count": t.count, "irq0_at": f"{hw[0].m} {hw[0].cs:04x}:{hw[0].eip:x}", "before_irq0": hw[0].n - t.n0}
assert len(Y0084) == 7 and all(v["count"] == v["before_irq0"] + 237 for v in Y0084.values()), Y0084

CONC = {
    "p1_p6": f"lc174a {len(LA.trigs)} 個、lc174b {len(LB.trigs)} 個區塊都有 YE、判準重核沒有問題;DIG 型長關中斷 lc174a 7 次(43928 ×6、43929 ×1),"
             f"G 一筆涵蓋、條數 = 前段 + 區間 + 1。lc174b 被砍掉後仍有統計(規則 3 符合 {YC_B['3']['matched']}、寫出 {YC_B['3']['written']})、"
             f"沒有 9500 ms 之前的區塊;START 放開 {P6['break_ms']} ms,DIG 型 if #{P6['dig_if']['seq']} 結束後 ng #{P6['ng']['seq']} {P6['ng']['count']} 條,"
             f"IRQ 1 在 0080:06ca 收(放開後 {P6['ng']['irq1_after_break_ms']} ms)。",
    "mdi375": f"ng 375 = 續一百六十五的 MDI 375:重入 ISR 之後的非遊戲段,MDI 型(回到 0x3f1a4)沒中斷時 302 / 303,lc174a #{Y375.seq} 中間在 "
              f"0c5c:1fad 收了一次 IRQ 7,SB16.DIG 的實模式處理 137c:0682 .. 0729 {len(_drv)} 條(碼位元組與檔案相同)→ 302 + 73 = 375。"
              f"lc174b、lc173a 沒有。lc163a 沒有 I 紀錄,同型是由條數差 73 推的(INFERRED)。",
    "dos4gw_write": f"0070 起頭的 if 區間 = DOS/4GW int 21h AH=40h 的轉送(FD2.EXE 檔內 0x{D4G:x} + 位移,分派表 AH=40h → 0x{H_WRITE:x}):"
                    f"spawn_group 把精靈快取 0x32a00 bytes 寫進 FD2.TMP,一次 write 分 {len(WRITE['lc174a']['chunks'])} 塊({FULL_N} 塊滿、最後一塊的拷貝量 "
                    f"{LAST_RATIO['lc174a']} 塊 ≈ {TMP_LEN - FULL_N * CHUNK} / {CHUNK}),每塊 0x0eb4 cli 拷到轉送緩衝、切實模式,0c5c:10b4 popf 才開中斷(甲型 {min(A_MS)} .. {max(A_MS)} ms);"
                    f"IRQ 0 在裡面到就積著,popf 一開就收、反射到遊戲 ISR,popf 之後再 {min(AFTER_POPF)} .. {max(AFTER_POPF)} 條到 0x3eb15 sti(乙型)。"
                    f"兩份紀錄各 {WRITE['lc174a']['hw_irqs']['08 r 0c5c:10b5']} / 26 塊是乙型,拷貝段裡沒有收過中斷。",
    "dos4gw_read": f"續一百七十三 9262 ms 的 0070:0d81 .. 0e6b({READ['lc173a_9262']['count']} 條)是 AH=3Fh(→ 0x{H_READ:x})"
                   f"實模式讀完、切回來把轉送緩衝拷回使用者緩衝那段,0x0e6a sti 之前關著中斷;三份紀錄這型的段都接在 dos_read 之後,"
                   f"拷貝段裡沒收過中斷、sti 之後一條(0x0e6c)收過。它從實模式就關著,不是 0070 起頭,所以規則 3 沒有選到。",
    "int21_0084": f"ng 600 .. 604 的 0080:0084 型:delay 的 int 21h AH=2Ch(0x3e04d),IRQ 0 落在 DOS/4GW 保護模式的 int 21h 入口段,"
                  f"之後反射到遊戲 ISR 固定 237 條;這型 lc174a {I21['lc174a']['spans']} 段、條數 {I21['lc174a']['min']} .. {I21['lc174a']['max']},"
                  f"600 .. 604 只有 {I21['lc174a']['in_600_604']} 段,是規則選到的一小段,跟 START 那型的 601 條數相同是巧合。",
}
for _part, _key in (("43928 ×6", "p1_p6"), ("規則 3 符合 25", "p1_p6"), ("137c:0682 .. 0729 73 條", "mdi375"), ("302 + 73 = 375", "mdi375"),
                    ("分 26 塊", "dos4gw_write"), ("各 7 / 26 塊是乙型", "dos4gw_write"), ("(1070 條)", "dos4gw_read"),
                    ("固定 237 條", "int21_0084")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s174.py"),
    "exe_md5": MD5,
    "calllogs": {nm: {"path": rel(p), "md5": LOG_MD5[nm]} for nm, p in
                 (("lc174a", RAW / "lc174a_CALLLOG.TXT"), ("lc174b", RAW / "lc174b_CALLLOG.TXT"), ("lc173a", RAW173 / "lc173a_CALLLOG.TXT"))},
    "trig": TRIG, "prediction": rel(DRV / "pred174.txt"), "check": rel(DRV / "check174.py"),
    "a_p1_p6": {"blocks": {"lc174a": len(LA.trigs), "lc174b": len(LB.trigs)}, "dig_g_rows": G_ROWS, "yc_lc174b": YC_B,
                "yn_lc174b": dict(LB.trig_spans), "p6": P6},
    "b_mdi375": MDI375,
    "c_dos4gw": {"file_base": hex(D4G), "int21_handler": {hex(k): hex(v) for k, v in HANDLER.items()}, "fd2_tmp_bytes": TMP_LEN,
                 "write": {nm: {**w, "hw_irqs": dict(sorted(w["hw_irqs"].items()))} for nm, w in WRITE.items()},
                 "rep_records_per_full_chunk": _rep, "last_chunk_ratio": LAST_RATIO, "y_types": WTYPES, "read": READ},
    "d_int21_0084": {nm: {k: v for k, v in s.items() if k != "rows"} for nm, s in I21.items()} | {"y_blocks": Y0084},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, len(LA.trigs), len(LB.trigs), MDI375["lc174a"]["count"], LAST_RATIO, AFTER_POPF, I21["lc174a"]["in_600_604"])
