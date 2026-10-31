"""續一百七十二證據:evidence/calllog_slices_s172_20261030.json(DH = 0 那一秒、delay 每條指令時間隨時段變的原因、rep 多記的機制、
137c 是 DIG 驅動、START 那一下的 601 / 602)。

使用者 2026-10-30「還沒處理的 請依照你的建議自動繼續進行處理」。工具:tools/dosbox/fd2_calllog_patch.py 加 FD2_CALLLOG_SLICES
(每筆紀錄附累計時間片數 k、片起點 / 片內多出的週期 b / w)與 FD2_CALLLOG_PICEV(每 100 ms 各 PIC 事件處理函式的次數,P 紀錄);
tools/dosbox_harness.sh 加 FD2_HARNESS_DOS_TIME(FD2.EXE 之前 TIME)。實機 lc172a / lc172b(原版 FD2.EXE、WSL -d Ubuntu、
開機 → 標題 → START → 16 秒;drivers_s172/lc172.py;預測在跑之前寫在 drivers_s172/pred172.txt)。
(A) 紀錄本身:兩份都逐段相接、每筆 G / S / I 都帶 k / b / w,k 不減。
(B) P1 DH = 0:delay 迴圈的 int 21h 只有一段連續走長路,結束在一個 BIOS tick(int 1Ch)上;DOSBox-X 的公式算出那一秒 18 個 tick,
    往前數 18 個 tick 落在資料允許的起點範圍內。兩份紀錄都一樣。
(C) P2 時間片:S 窗逐條的時間差全部由「換片 +1、rep 迭代、I/O 延遲、單次字串指令 +1、mov / pop ss −1、sti 換片 0」解釋;
    每次乾淨的 delay(2) 的殘差(5000·Δt − Δn)= 時間片數 + 定值。片頭多出的時間片是 DOSBox-X Sound Blaster 的 DMA_DAC_Event
    (每 ms 22.05 次,DIG 驅動初始化之後到真正放音之前);續一百六十五的「0.5%」就是這個。
(D) P3 rep 多記:4 個 rep 位置的基準次數 = ⌈N / 4⌉(N 取自前一條 mov cx / ecx);多記的次數不超過 rep 期間 k 的增加。
(E) P4 137c:DIG 驅動(DIG.INI 的 SB16.DIG;5 個 .DIG 的 int 66h 分派段逐位元組相同)。第一次執行是 DIG 自己的功能,之後 MDI 的 0x502
    超出 0x300 .. 0x4ff,經 0x1fa ljmp cs:[0x36] 轉給舊向量(SBPRO2.MDI)。更正續一百七十一把轉送條件寫反的說法。
(F) P5 鍵盤:int 09h 在遊戲碼收時處理 532 .. 534 條;START 那一下 Return 撞上 DIG 型重入,重入的 69 條在 0080:06ca 被切開,
    中間夾 533 條鍵盤處理 = 602(lc171a 的 601、續一百六十五 lc163a 的 601 同型)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import itertools
import json
import re
import statistics

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("calllog_slices_s172_20261030.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DRV = GEN_DIR / "drivers_s172"
RAW = ROOT / ".wsl_build" / "lc172_live"
RAW171 = ROOT / ".wsl_build" / "lc171_live"
DELTA = 0x19C000
GAME_CS = 0x170
S165 = json.loads((EVIDENCE / "reentry_catchup_mdi_driver_s165_20261029.json").read_text(encoding="utf-8"))

assert hashlib.md5(_EXE).hexdigest() == MD5
LOGS = {"lc172a": "902d74f599b2786af3d1a09e0f47b886", "lc172b": "204c139f6a85d6983539d06b7cafbf12"}
LC171A_MD5 = "0323eeb1d98d77814b42148f6bd87a33"
SEGS = "3000-3800,3800-3810:x,3810-6300,6300-6310:x,6310-24000"
DOS_TIME = (12, 0, 54)
_drv_src = (DRV / "lc172.py").read_text(encoding="utf-8")
assert all(f'"{k}": "{SEGS}"' in _drv_src and f'"{k}": "12:00:54"' in _drv_src for k in LOGS)
assert 'PICEV = {"lc172a": "0", "lc172b": "1"}' in _drv_src          # P 紀錄只有 lc172b
TEXT: dict[str, list[str]] = {}
LOG: dict[str, cs.Log] = {}
EPS: dict[str, list[cs.Episode]] = {}
for _k, _path, _md5 in [(k, RAW / f"{k}_CALLLOG.TXT", v) for k, v in LOGS.items()] + [
        ("lc171a", RAW171 / "lc171a_CALLLOG.TXT", LC171A_MD5)]:
    _b = _path.read_bytes()
    assert hashlib.md5(_b).hexdigest() == _md5, _k
    TEXT[_k] = _b.decode("ascii").splitlines()
    LOG[_k] = cs.parse(TEXT[_k])
    EPS[_k] = cs.episodes(LOG[_k])
    assert LOG[_k].game_cs == GAME_CS
assert TEXT["lc172a"][0].endswith(f" icount=1 segs={SEGS} slices=1"), TEXT["lc172a"][0]
_mh = re.fullmatch(r"H fd2calllog .* icount=1 segs=" + re.escape(SEGS) + r" slices=1 picev=([0-9a-f]+)", TEXT["lc172b"][0])
assert _mh, TEXT["lc172b"][0]
PICEV_REF = int(_mh.group(1), 16)


def rt(a: int) -> int:
    return a + DELTA


# ================= (A) 紀錄本身 =================
def validity(k: str) -> dict:
    """逐段相接、每筆 G / S / I 都帶 k / b / w、k 依檔案次序不減。"""
    lg = LOG[k]
    seq = []
    for kind, i in lg.order:
        if kind == "I":
            seq.append(lg.irqs[i].sl)
        else:
            r = lg.runs[i]
            seq.extend(r.sls if r.sls is not None else [r.sl])
    return {"runs": len(lg.runs), "irqs": len(lg.irqs), "gaps": lg.gaps,
            "every_record_has_slices": all(s is not None for s in seq),
            "k_nondecreasing": all(a[0] <= b[0] for a, b in zip(seq, seq[1:])), "k_last": seq[-1][0]}


VALID = {k: validity(k) for k in LOGS}
# k_last = G / S / I 紀錄(validity 的 seq)裡最大的 k(k 不減,最後一筆就是最大)
assert all(VALID[k]["k_last"] == max(int(m.group(1)) for ln in TEXT[k] if ln[:2] in ("G ", "S ", "I ")
                                       for m in [re.search(r" k=(\d+) ", ln)] if m) for k in LOGS), VALID
for k in LOGS:
    assert VALID[k]["gaps"] == [] and VALID[k]["every_record_has_slices"] and VALID[k]["k_nondecreasing"], VALID[k]

# ================= (B) P1:DH = 0 那一秒 =================
DLY = 0x3E04D
E3B = ("p", 0x88, 0xE3B)                # DOS/4GW int 21h 轉送裡看 CF 的那一段(續一百七十一)
assert insn(DLY) == "int 0x21" and insn(0x3E04F) == "cmp bl, dh" and insn(0x3E047) == "xor eax, eax"


def path_class(c: int) -> str:
    """E3B 那段的條數:33 .. 35 短路、39 .. 41 長路(續一百七十一);其他是那段被中斷切開。"""
    return "short" if 33 <= c <= 35 else "long" if 39 <= c <= 41 else "split"


def cf_of(r: cs.Run) -> str | None:
    """依遊戲 run 的起點與條數判斷 int 21h 前的 CF(與 ev_s171 相同的規則);看不出來回傳 None。"""
    e0 = r.e0 - DELTA
    if e0 == 0x3E04F:
        return "cf1_loop" if r.count <= 5 else "cf0_first"
    if e0 in (0x3E051, 0x3E052):
        return "cf1_loop"
    if e0 in (0x3E04B, 0x3E04D):
        return None
    return "cf0_first"


_STOP = {rt(a) for a in (0x3E047, 0x3E049, 0x3E04B, 0x3E04F, 0x3E051, 0x3E052)}


def delay_rows(k: str) -> list[tuple[float, str, str]]:
    """delay 的每次 int 21h:(I 紀錄的時間, CF 來源, E3B 段的路)依時間排序。"""
    lg, eps = LOG[k], EPS[k]
    gr = [r for r in lg.runs if r.cs == GAME_CS and r.m == "P"]
    gi = {id(r): i for i, r in enumerate(gr)}

    def cf_source(g: cs.Run) -> str:
        i = gi[id(g)]
        cf = cf_of(g)
        while cf is None:
            i -= 1
            while i >= 0 and gr[i].e1 not in _STOP:
                i -= 1
            if i < 0:
                return "unknown"
            cf = cf_of(gr[i])
        return cf

    first_run = {id(e.runs[0]): e.index for e in eps if e.runs}
    pre: dict[int, cs.Run] = {}
    prev = None
    for kind, i in lg.order:
        if kind != "G":
            continue
        r = lg.runs[i]
        if id(r) in first_run and prev is not None and prev.cs == GAME_CS and prev.m == "P" and prev.n_end == r.n_start:
            pre[first_run[id(r)]] = prev
        prev = r
    irq_n = [q.n for q in lg.irqs]
    rows = []
    for e in eps:
        if not (e.complete and e.left_from == rt(DLY) and e.back_to == rt(DLY) + 2):
            continue
        g = pre.get(e.index)
        assert g is not None, e.index
        q = lg.irqs[bisect.bisect_right(irq_n, e.runs[0].n_start) - 1]
        assert (q.num, q.type, q.n) == (0x21, 1, e.runs[0].n_start), q
        s = [r for r in e.runs if (r.m, r.cs, r.e0) == E3B]
        cf = cf_source(g)
        assert cf in ("cf0_first", "cf1_loop"), cf
        rows.append((q.t, cf, path_class(s[0].count) if len(s) == 1 else "no_e3b"))
    rows.sort()
    return rows


# DOSBox-X:TIME -> int 21h AH=2Dh 把 BIOS tick 設成 csec × PIT / 6553600;AH=2Ch 以 tick × 100 / (PIT / 65536) 換回(摘錄)
SRC = (DRV / "dosbox_src_s172.txt").read_text(encoding="utf-8")
DOS2C = (GEN_DIR / "drivers_s171" / "dosbox_dos_int21_2c.txt").read_text(encoding="utf-8")
assert "const uint32_t ticks = (uint32_t)((double)csec * ((double)PIT_TICK_RATE/6553600.0));" in SRC
assert "Bitu time=(Bitu)((100.0/((double)PIT_TICK_RATE/65536.0)) * (double)ticks);" in DOS2C
assert "#define PIT_TICK_RATE_IBM 1193182" in SRC and "unsigned long PIT_TICK_RATE = PIT_TICK_RATE_IBM;" in SRC
assert "reg_ah=0x2d; // set system time" in SRC
# int 08h 的 callback:C 處理函式(BIOS_TIMER + 1)之後才 int 1Ch,所以每筆 I 1c 都在 tick 加一之後
assert "uint32_t value = mem_readd(BIOS_TIMER) + 1;" in SRC and "(uint16_t)0x1ccd);\t// int 1c" in SRC
PIT = 1193182


def dos_sec(ticks: int) -> int:
    return (int((100.0 / (PIT / 65536.0)) * ticks) // 100) % 60


_csec = ((DOS_TIME[0] * 60 + DOS_TIME[1]) * 60 + DOS_TIME[2]) * 100
T0 = int(_csec * (PIT / 6553600.0))
_t = T0
while dos_sec(_t) != 0:
    _t += 1
SEC0_FIRST = _t
while dos_sec(_t) == 0:
    _t += 1
SEC0_TICKS = _t - SEC0_FIRST
TIME_CALC = {"ticks_after_TIME": T0, "dos_seconds_of_day_at_TIME": int((100.0 / (PIT / 65536.0)) * T0) / 100,
             "dos_second_at_TIME": dos_sec(T0), "ticks_to_second_0": SEC0_FIRST - T0, "second_0_ticks": SEC0_TICKS}
assert TIME_CALC == {"ticks_after_TIME": 787504, "dos_seconds_of_day_at_TIME": 43253.97, "dos_second_at_TIME": 53,
                     "ticks_to_second_0": 110, "second_0_ticks": 18}, TIME_CALC


def dh0(k: str) -> dict:
    rows = delay_rows(k)
    tab = collections.Counter((a, b) for _, a, b in rows)
    assert tab[("cf0_first", "short")] == 0, tab                # 每次 delay 呼叫的第一次(xor 之後 CF = 0)一定長路
    cf1 = [(t, b) for t, a, b in rows if a == "cf1_loop" and b in ("short", "long")]
    longs = [i for i, (_t1, b) in enumerate(cf1) if b == "long"]
    assert longs and longs == list(range(longs[0], longs[-1] + 1)), "迴圈內走長路的不是一段連續"
    t_first, t_last = min(t for t, b in cf1 if b == "long"), max(t for t, b in cf1 if b == "long")
    t_short_before = max(t for t, b in cf1 if b == "short" and t < t_first)
    t_short_after = min(t for t, b in cf1 if b == "short" and t > t_last)
    allt = [t for t, _a, _b in rows]
    t_prev_last = allt[allt.index(t_last) - 1]                  # 最後一次長路讀的 DH 是它前一次 int 21h 讀到的
    ticks = sorted(q.t for q in LOG[k].irqs if q.num == 0x1C and q.type == 1)
    end = [x for x in ticks if t_prev_last < x < t_short_after]
    assert len(end) == 1, end                                   # 那一秒結束在恰好一個 BIOS tick 上
    ie = ticks.index(end[0])
    t_start = ticks[ie - SEC0_TICKS]
    assert t_short_before < t_start < t_first, (t_short_before, t_start, t_first)
    gaps = [round(b - a, ndigits=3) for a, b in zip(ticks[ie - SEC0_TICKS:ie], ticks[ie - SEC0_TICKS + 1:ie + 1])]
    assert all(54.5 < g < 60.5 for g in gaps), gaps              # 沒有漏掉的 tick(AIL 在 5 ms 格點轉接 BIOS:約 55 或 60 ms)
    return {"table": {f"{a}|{b}": n for (a, b), n in sorted(tab.items())},
            "cf1_long_block_ms": [t_first, t_last], "cf1_short_neighbours_ms": [t_short_before, t_short_after],
            "end_tick_ms": end[0], "start_tick_ms_18_back": t_start, "tick_gaps_ms": gaps}


DH0 = {k: dh0(k) for k in LOGS}
_raw_e3b = {k: collections.Counter(s1[0].count for e in EPS[k] if e.complete and e.left_from == rt(DLY) and e.back_to == rt(DLY) + 2
                                   for s1 in [[r for r in e.runs if (r.m, r.cs, r.e0) == E3B]] if len(s1) == 1) for k in LOGS}
assert all(path_class(c) != "split" for k in LOGS for c, n in _raw_e3b[k].items() if n >= 10), _raw_e3b
assert DH0["lc172a"]["table"]["cf1_loop|long"] == 3634 and DH0["lc172b"]["table"]["cf1_loop|long"] == 4160, DH0
assert (DH0["lc172a"]["end_tick_ms"], DH0["lc172b"]["end_tick_ms"]) == (8051.9194, 8055.2048), DH0
assert (DH0["lc172a"]["start_tick_ms_18_back"], DH0["lc172b"]["start_tick_ms_18_back"]) == (7056.8918, 7060.1912), DH0

# ================= (C) P2:時間片 =================
STRING1 = {"movsb", "movsw", "movsd", "stosb", "stosw", "stosd", "lodsb", "lodsw", "lodsd",
           "cmpsb", "cmpsw", "cmpsd", "scasb", "scasw", "scasd"}


def op_class(lg: cs.Log, m: str, c: int, e: int) -> str:
    code = lg.code.get((m, c, e))
    assert code is not None, (m, c, e)
    d = cs.disasm_one(m, e, code)
    mn, _, ops = d.partition(" ")
    if mn in ("rep", "repe", "repne"):
        return "rep"
    if mn in ("in", "out", "sti"):
        return mn
    if mn in STRING1:
        return "string1"
    if (mn == "mov" and ops.startswith("ss, ")) or (mn == "pop" and ops == "ss"):
        return "ss"
    return "plain"


def step_ok(cls: str, s: int, d: int) -> bool:
    """這一步的 d(= ΔA − 1)與上一條指令的種類、是否換片 s 相符。"""
    x = d - s
    if cls == "rep":
        return 0 <= x <= 4                      # 一次最多 4 次迭代(interruptible rep string op = -1 -> 4)
    return x == {"plain": 0, "sti": 0, "in": 5, "out": 3, "string1": 1, "ss": -1}[cls] or (cls == "sti" and s == 1 and d == 0)


def step_table(k: str) -> dict:
    lg = LOG[k]
    tab: collections.Counter = collections.Counter()
    prev = None   # (m, cs, eip, n, (k, b, w))
    for kind, i in lg.order:
        if kind != "G" or lg.runs[i].eips is None:
            prev = None
            continue
        r = lg.runs[i]
        assert r.sls is not None
        for j, (e, sl) in enumerate(zip(r.eips, r.sls)):
            n = r.n_start + j + 1
            if prev is not None and prev[3] + 1 == n:
                s = int(sl[0] != prev[4][0])
                assert sl[0] - prev[4][0] in (0, 1)
                d = (sl[1] - prev[4][1]) if s else (sl[2] - prev[4][2])
                cls = op_class(lg, prev[0], prev[1], prev[2])
                assert step_ok(cls, s, d), (k, cls, s, d, prev[:3])
                tab.update([(cls, s, d)])
            prev = (r.m, r.cs, e, n, sl)
    return {f"{a}|{b}|{c}": v for (a, b, c), v in sorted(tab.items())}


STEPS = {k: step_table(k) for k in LOGS}
for k in LOGS:
    assert sum(STEPS[k].values()) > 30000 and STEPS[k].get("plain|1|1", 0) > 500 and STEPS[k].get("ss|0|-1", 0) > 100, STEPS[k]
# 原始碼:核心迴圈 while (CPU_Cycles-->0)(片尾多減一次)、PIC_RunQueue 在下一個事件處切片、rep 每 4 次重啟、mov / pop ss 多給一條
for _s in ("\twhile (CPU_Cycles-->0) {", "if (DEBUG_HeavyIsBreakpoint()) {", "Bits cycles=(Bits)(pic_queue.next_entry->index*CPU_CycleMax-index_nd);",
           "if (cpu_rep_max < 0) cpu_rep_max = 4;", "if ((--CPU_Cycles) <= 0) break;", "CPU_Cycles++; //Always do another instruction",
           "CPU_IODelayRemoved += delaycyc;", "Pint = secprop->Add_int(\"interruptible rep string op\",Property::Changeable::Always,-1);"):
    assert _s in SRC, _s

_rx_er = re.compile(r"^([ER]) (\d+) ([0-9a-f]{8}) .*? i=(\d+) n=(\d+) t=([0-9.]+) k=(\d+) b=(-?\d+) w=(-?\d+)$")
_rx_s1 = re.compile(r" s=([0-9a-f]{8}),")
DELAY_E = rt(0x3E01D)
ISR = {rt(0x3EA8E), rt(0x3EBAD)}
assert insn(0x3E01D) != "" and insn(0x3EA8E) != ""


Delay = collections.namedtuple("Delay", "t0 dt dn dk db dw")
CYCLES = 5000                          # DOSBox-X 每 ms 的指令數(harness 的 config -set cycles)
assert f"-c 'config -set cycles={CYCLES}'" in (ROOT / "tools/dosbox_harness.sh").read_text(encoding="utf-8")


def clean_delays(k: str) -> tuple[list[Delay], list[tuple[Delay, str]]]:
    """delay(2) 的 (t0, Δt, Δn, Δk, Δb, Δw):乾淨的(E 到 R 之間沒有中斷處理程式進入、也沒有任何硬體 I 紀錄),
    與「沒有中斷處理程式進入、但有硬體 I 紀錄」的(在非遊戲碼收、不經遊戲 ISR 的中斷;另列)。"""
    opens: dict[str, tuple] = {}
    pairs = []
    isr_t = []
    for ln in TEXT[k]:
        if ln[:2] not in ("E ", "R "):
            continue
        mt = _rx_er.match(ln)
        if mt is None:
            continue
        eip, t = int(mt.group(3), 16), float(mt.group(6))
        v = tuple(int(mt.group(x)) for x in (5, 7, 8, 9))
        if mt.group(1) == "E" and eip in ISR:
            isr_t.append(t)
        if eip != DELAY_E:
            continue
        if mt.group(1) == "E":
            opens[mt.group(2)] = (t, v, int(_rx_s1.search(ln).group(1), 16))
        elif mt.group(2) in opens:
            t0, v0, a0 = opens.pop(mt.group(2))
            if a0 == 2:
                pairs.append((t0, t, v0, v))
    hw = [(q.n, q.num) for q in LOG[k].irqs if q.type == 0]
    hw_n = [n for n, _num in hw]
    out, other = [], []
    for t0, t1, v0, v1 in pairs:
        if bisect.bisect_right(isr_t, t0) != bisect.bisect_left(isr_t, t1):
            continue
        row = Delay(t0, t1 - t0, v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2], v1[3] - v0[3])
        inside = hw[bisect.bisect_right(hw_n, v0[0]):bisect.bisect_right(hw_n, v1[0])]
        if inside:
            other.append((row, ",".join(f"{num:02x}" for _n, num in inside)))
        else:
            out.append(row)
    return out, other


_CD = {k: clean_delays(k) for k in LOGS}
DELAYS = {k: v[0] for k, v in _CD.items()}
# 另列:沒進遊戲 ISR、但期間有在非遊戲碼收的硬體中斷(都是 int 09h);殘差 − 時間片數比定值多(鍵盤處理的 in / out 有 I/O 延遲)
HW_DELAYS = {k: [{"t": round(r.t0, ndigits=3), "irq": irq, "resid_minus_dk": round(r.dt * CYCLES - r.dn - r.dk, ndigits=3)} for r, irq in v[1]]
             for k, v in _CD.items()}
assert {k: sorted((d["irq"], d["resid_minus_dk"]) for d in v) for k, v in HW_DELAYS.items()} == {
    "lc172a": [("08", 1445.0), ("09", 1499.0), ("09", 1499.0)], "lc172b": []}, HW_DELAYS   # int 08h 那次在 R 之後才進 ISR,不影響
RESID = {}
for k, rows in DELAYS.items():
    res = [r.dt * CYCLES - r.dn for r in rows]
    assert all(abs(r - (db + dw)) < 1e-3 for r, (_t0, _dt, _dn, _dk, db, dw) in zip(res, rows))   # 定義上的恆等式(核對欄位)
    const = [r - dk for r, (_t0, _dt, _dn, dk, _db, _dw) in zip(res, rows)]
    ts = [r.t0 for r in rows]
    gi = max(range(1, len(ts)), key=lambda j: ts[j] - ts[j - 1])
    assert ts[gi] - ts[gi - 1] > 3000
    per = {}
    for nm, grp in (("early", rows[:gi]), ("late", rows[gi:])):
        per[nm] = {"t_ms": [round(min(g.t0 for g in grp), ndigits=1), round(max(g.t0 for g in grp), ndigits=1)], "n": len(grp),
                   "slices_per_ms": round(sum(g.dk for g in grp) / sum(g.dt for g in grp), ndigits=3),
                   "resid_mode": statistics.mode(round(g.dt * CYCLES - g.dn) for g in grp),
                   "dk_mode": statistics.mode(g.dk for g in grp)}
    RESID[k] = {"clean_delay2": len(rows), "with_kb_irq": HW_DELAYS[k], "resid_minus_dk": [round(min(const), 3), round(max(const), 3)], "periods": per}
    # 殘差 = 時間片數 + 定值(每一次都成立,不是平均)
    assert max(const) - min(const) < 1e-3, (k, min(const), max(const))
assert {k: round(v["resid_minus_dk"][0]) for k, v in RESID.items()} == {"lc172a": 1445, "lc172b": 1445}, RESID

# P 紀錄(lc172b):各 PIC 事件處理函式每 100 ms 的次數;以 nm 對回名稱
NM_LINES = (DRV / "nm_handlers_s172.txt").read_text(encoding="utf-8").splitlines()
assert NM_LINES[0].startswith("# nm ~/fd2-dosbox-calllog2/dosbox-x/src/dosbox-x sha256 ")
NM = {int(a, 16): s for a, _t, s in (ln.split() for ln in NM_LINES[1:])}
_ref = next(a for a, s in NM.items() if s == "_Z19fd2calllog_piceventPv")
BIAS = PICEV_REF - _ref


def short(sym: str) -> str:
    mt = re.fullmatch(r"_Z(?:L)?\d+(\w+?)(?:m|Pv)", sym)
    assert mt, sym
    return mt.group(1)


PREC: dict[int, dict[str, int]] = {}
for ln in TEXT["lc172b"]:
    if ln.startswith("P "):
        f = ln.split()
        d = {}
        for kv in f[2:]:
            a, c = kv.split("=")
            sym = NM.get(int(a, 16) - BIAS)
            assert sym is not None, (f[1], a)            # 每個處理函式都要對得到 nm 的名稱
            d[short(sym)] = int(c)
        assert sum(1 for kv in f if "=" in kv) == len(d), f[:3]
        PREC[int(f[1])] = d
BUCKET = 100                           # P 紀錄每格 ms
assert all(b % BUCKET == 0 for b in PREC) and len(PREC) > 300 and {b - a for a, b in itertools.pairwise(sorted(PREC))} == {BUCKET}


def rate(name: str, lo: int, hi: int) -> float:
    bs = [b for b in PREC if lo <= b < hi]
    return round(sum(PREC[b].get(name, 0) for b in bs) / (len(bs) * BUCKET), ndigits=3)


_rb = RESID["lc172b"]["periods"]
EV_LO = (int(_rb["early"]["t_ms"][0] // BUCKET + 1) * BUCKET, int(_rb["early"]["t_ms"][1] // BUCKET) * BUCKET)
EV_HI = (int(_rb["late"]["t_ms"][0] // BUCKET + 1) * BUCKET, int(_rb["late"]["t_ms"][1] // BUCKET) * BUCKET)
for (_lo, _hi), _per in ((EV_LO, _rb["early"]["t_ms"]), (EV_HI, _rb["late"]["t_ms"])):
    assert _lo - BUCKET < _per[0] <= _lo and _hi <= _per[1] < _hi + BUCKET, (_lo, _hi, _per)   # 段內第一個 / 最後一個完整格
NAMES = sorted({n for d in PREC.values() for n in d})
EVRATE = {"early": {n: rate(n, *EV_LO) for n in NAMES}, "late": {n: rate(n, *EV_HI) for n in NAMES}}
assert EVRATE["early"]["DMA_DAC_Event"] == 22.05 and EVRATE["late"]["DMA_DAC_Event"] == 0, EVRATE
assert abs(EVRATE["early"]["VGA_DrawSingleLine"] - EVRATE["late"]["VGA_DrawSingleLine"]) < 0.05, EVRATE
_dslice = {k: RESID[k]["periods"]["early"]["slices_per_ms"] - RESID[k]["periods"]["late"]["slices_per_ms"] for k in LOGS}
# 片頭比新遊戲開場每 ms 多的時間片 ≈ DMA_DAC_Event 的 22.05(其他事件兩段相同)
assert all(abs(v - 22.05) < 1.0 for v in _dslice.values()), _dslice
_dac = sorted(b for b, d in PREC.items() if d.get("DMA_DAC_Event"))
DAC = {"first_bucket": _dac[0], "first_count": PREC[_dac[0]].get("DMA_DAC_Event"), "last_bucket": _dac[-1],
       "last_count": PREC[_dac[-1]].get("DMA_DAC_Event"), "contiguous": _dac == list(range(_dac[0], _dac[-1] + 100, 100)),
       "middle_counts": sorted({PREC[b].get("DMA_DAC_Event", 0) for b in _dac[1:-1]})}
assert DAC == {"first_bucket": 3100, "first_count": 224, "last_bucket": 8400, "last_count": 1514, "contiguous": True,
               "middle_counts": [2205]}, DAC
KHZ = DAC["middle_counts"][0] / BUCKET
DAC["start_ms_est"] = round(DAC["first_bucket"] + BUCKET - DAC["first_count"] / KHZ, ndigits=2)
DAC["stop_ms_est"] = round(DAC["last_bucket"] + DAC["last_count"] / KHZ, ndigits=2)
_irq7 = [q for q in LOG["lc172b"].irqs if q.num == 0x0F and q.type == 0]
IRQ7 = {"first": [_irq7[0].t, f"{_irq7[0].m} {_irq7[0].cs:04x}:{_irq7[0].eip:x}"],
        "second_ms": _irq7[1].t, "period_ms_median": round(statistics.median(b.t - a.t for a, b in zip(_irq7[1:], _irq7[2:])), 3),
        "count": len(_irq7)}
assert IRQ7["first"][0] < IRQ7["second_ms"] and not any(IRQ7["first"][0] < q.t < IRQ7["second_ms"] for q in _irq7), IRQ7
# DIG 驅動(137c)裡收的第一次 IRQ7 與 DMA_DAC_Event 開始同時;真正放音(每 2048 / 22050 秒一次 IRQ7)在它停了之後
assert IRQ7["first"][1] == "r 137c:31a" and abs(IRQ7["first"][0] - DAC["start_ms_est"]) < 0.1, (IRQ7, DAC)
assert DAC["stop_ms_est"] < IRQ7["second_ms"] and abs(IRQ7["period_ms_median"] - 2048 / 22.05) < 0.3, (IRQ7, DAC)
for _s in ("if (dsp.force_goldplay || (goldplay && freq > 0 && single_sample_dma))", "if (sb[ci].dma.chan->masked) {",
           "PIC_AddEvent(DMA_DAC_Event,1000.0 / sb[ci].dma_dac_srcrate,(ci << CARD_INDEX_BIT));",
           "Pbool = secprop->Add_bool(\"goldplay\",Property::Changeable::WhenIdle,true);"):
    assert _s in SRC, _s
# 續一百六十五 lc163a:片頭 / 新遊戲開場 delay 的時間差扣掉指令數差 ≈ 22.05 × 每次 delay 的 ms
_ph = S165["calibration"]["phase"]
S165_LINK = {"resid_step": round((_ph["early"]["ms_median"] - _ph["late"]["ms_median"]) * CYCLES
                                 - (_ph["early"]["nongame_mean"] - _ph["late"]["nongame_mean"]), 2),
             "dac_per_delay": round(KHZ * _ph["early"]["ms_median"], ndigits=2)}
assert abs(S165_LINK["resid_step"] - S165_LINK["dac_per_delay"]) < 3, S165_LINK

# ================= (D) P3:rep 多記 =================
REP_SITES = [("p", 0x80, 0x6B0), ("p", 0x88, 0xE1F), ("p", 0x70, 0xCD4), ("p", 0x88, 0x21B5)]


def rep_n(lg: cs.Log, site: tuple[str, int, int]) -> int:
    """rep 前一條(S 紀錄裡緊接在前)是 mov cx / ecx, imm;回傳 imm。"""
    for r in lg.runs:
        if r.eips and site[2] in r.eips and (r.m, r.cs) == site[:2]:
            j = r.eips.index(site[2])
            if j > 0:
                d = cs.disasm_one(r.m, r.eips[j - 1], lg.code[(r.m, r.cs, r.eips[j - 1])])
                mt = re.fullmatch(r"mov e?cx, (0x[0-9a-f]+|\d+)", d)
                assert mt, d
                return int(mt.group(1), 0)
    raise AssertionError(site)


REP_N = {f"{c:04x}:{e:x}": rep_n(LOG["lc172a"], (m, c, e)) for m, c, e in REP_SITES}
assert REP_N == {"0080:6b0": 14, "0088:e1f": 31, "0070:cd4": 12, "0088:21b5": 31}, REP_N


def rep_table(k: str) -> dict:
    lg = LOG[k]
    tab: collections.Counter = collections.Counter()
    edges = []
    for r in lg.runs:
        if r.eips is None:
            continue
        E, SL = r.eips, r.sls
        i = 0
        while i < len(E):
            j = i
            while j + 1 < len(E) and E[j + 1] == E[i]:
                j += 1
            key = (r.m, r.cs, E[i])
            if key in REP_SITES:
                base = -(-REP_N[f"{key[1]:04x}:{key[2]:x}"] // 4)
                extra, dk_in = (j - i + 1) - base, SL[j][0] - SL[i][0]
                if extra < 0:
                    # 只在 S 段的頭尾(時間窗或 I 紀錄切開),或前一條是 iret(被中斷的 rep 回來續做,ECX 已減少)
                    resumed = i > 0 and cs.disasm_one(r.m, E[i - 1], lg.code[(r.m, r.cs, E[i - 1])]) in ("iret", "iretd")
                    assert i == 0 or j == len(E) - 1 or resumed, (k, key, i, j)
                    edges.append((key, i, j))
                else:
                    assert extra <= dk_in, (k, key, extra, dk_in)       # 多記一次 = rep 期間時間片結束一次
                    tab.update([(extra, dk_in)])
            i = j + 1
    return {"by_extra_dk": {f"{a}|{b}": v for (a, b), v in sorted(tab.items())}, "cut_or_resumed": len(edges)}


REPT = {k: rep_table(k) for k in LOGS}
for k in LOGS:
    t = REPT[k]["by_extra_dk"]
    assert t["0|0"] > 200 and t.get("1|1", 0) > 40 and REPT[k]["cut_or_resumed"] <= 3, REPT[k]
    # 對照:k 增加但沒多記也有(片剛好結束在 4 次一段的邊界上,rep 本來就要重啟)
    assert t.get("0|1", 0) > 0, t

# ================= (E) P4:137c 是 DIG 驅動 =================
DIGS = ["SB16.DIG", "SBPRO.DIG", "SBLASTER.DIG", "PROAUDIO.DIG", "RAP10.DIG"]
DIGB = {f: (GAME / f).read_bytes() for f in DIGS}
assert all(b[:8] == b"AIL3DIG\x1a" and b[0x34:0x36] == b"\x6a\x01" for b in DIGB.values())
assert len({b[0x16A:0x200] for b in DIGB.values()}) == 1                           # 分派段逐位元組相同
DIG_INI = (GAME / "DIG.INI").read_text(encoding="ascii")
assert re.search(r"^DRIVER\s+SB16\.DIG\s*$", DIG_INI, re.M), DIG_INI
SB16 = DIGB["SB16.DIG"]
DISP = {hex(a): cs.disasm_one("r", a, SB16[a:a + 16]) for a in (0x16A, 0x16D, 0x16F, 0x172, 0x174, 0x179, 0x17B, 0x1E9, 0x1EA, 0x1F0, 0x1FA)}
assert DISP == {"0x16a": "cmp ax, 0x300", "0x16d": "jb 0x1ea", "0x16f": "cmp ax, 0x4ff", "0x172": "ja 0x1ea",
                "0x174": "cmp bx, word ptr cs:[0x32]", "0x179": "jne 0x1ea", "0x17b": "cli", "0x1e9": "iret",
                "0x1ea": "cmp word ptr cs:[0x36], 0", "0x1f0": "jne 0x1fa", "0x1fa": "ljmp cs:[0x36]"}, DISP
_pos = {k: sorted((e, b) for (m, c, e), b in LOG[k].code.items() if c == 0x137C and b is not None) for k in LOGS}
# 紀錄裡 137c 帶碼位元組的位置(分派段 0x16a 與驅動自己的程式):只有 SB16.DIG 每一處都對得上
ALL_DIG = {p.name: p.read_bytes() for p in sorted(GAME.glob("*.DIG"))}
DIG_MATCH = {k: {f: sum(b[e:e + 16] == c for e, c in v) for f, b in ALL_DIG.items()} for k, v in _pos.items()}
for k, v in _pos.items():
    assert [e for e, _c in v] == {"lc172a": [0x16A, 0x31A, 0x682], "lc172b": [0x16A, 0x318, 0x682]}[k], v
    assert [f for f, n in DIG_MATCH[k].items() if n == len(v)] == ["SB16.DIG"], DIG_MATCH[k]


def int66_kinds(k: str) -> list[tuple[float, str]]:
    lg = LOG[k]
    starts = [r.n_start for r in lg.runs]
    out = []
    for q in lg.irqs:
        if q.num == 0x66 and q.type == 1:
            r = lg.runs[bisect.bisect_left(starts, q.n)]
            assert r.n_start == q.n
            out.append((q.t, f"{r.m} {r.cs:04x}:{r.e0:x}-{r.e1:x}" + (f" x{r.count}" if r.cs == 0x137C else "")))
    return out


I66 = {k: int66_kinds(k) for k in ("lc172a", "lc172b", "lc171a")}
HOOK = {}
for k in ("lc172a", "lc172b"):
    kinds = I66[k]
    i137 = next(i for i, (_t, s) in enumerate(kinds) if s.startswith("r 137c:"))
    # 137c 之前全是直接進 SBPRO2.MDI 的分派(0f71:0132);之後全從 137c 進
    assert all(s.startswith("r 0f71:132-") for _t, s in kinds[:i137]) and all(s.startswith("r 137c:16a-") for _t, s in kinds[i137:])
    chain = [s for _t, s in kinds[i137:] if s == "r 137c:16a-1fa x7"]
    # 其餘是 DIG 自己的功能:到 0x1e9 iret,或在功能裡被 I 紀錄切開(結尾不是 0x1fa)
    own = [s for _t, s in kinds[i137:] if s != "r 137c:16a-1fa x7"]
    assert all(not s.split(" x")[0].endswith("-1fa") for s in own), own
    assert sum(s.startswith("r 137c:16a-1e9 ") for s in own) >= len(own) - 1, own
    HOOK[k] = {"direct_before": i137, "first_137c": list(kinds[i137]), "own_function_calls": len(own),
               "chained_calls": len(chain), "first_chain_ms": next(t for t, s in kinds if s == "r 137c:16a-1fa x7")}
    assert kinds[i137][1].startswith("r 137c:16a-1e9 ") and HOOK[k]["first_chain_ms"] > kinds[i137][0]
# lc171a(續一百七十一):137c 第一次出現在 3400 .. 3700 的空窗之後;直接進驅動的 MDI 呼叫比 lc172a 晚約 200 ms
_d171 = [t for t, s in I66["lc171a"] if s.startswith("r 0f71:132-")]
TIMING = {"first_direct_mdi_ms": {k: min(t for t, s in I66[k] if s.startswith("r 0f71:132-")) for k in ("lc171a", "lc172a", "lc172b")},
          "lc171a_first_137c_ms": next(t for t, s in I66["lc171a"] if s.startswith("r 137c:")),
          "lc171a_last_direct_ms": max(_d171)}
assert TIMING["lc171a_last_direct_ms"] < 3400 < 3700 < TIMING["lc171a_first_137c_ms"], TIMING

# ================= (F) P5:鍵盤 IRQ 與 START 那一下的 601 / 602 =================
REENTRY = rt(0x3EBAD)
_rx_era = re.compile(r"^([ERA]) (\d+) ([0-9a-f]{8}) .*? i=(\d+) n=(\d+) t=([0-9.]+)")


def kb_costs(k: str) -> dict:
    """int 09h(硬體):收中斷到回到被中斷的 (模式, CS, EIP) 的指令數,依收的位置分組。"""
    lg = LOG[k]
    starts = [r.n_start for r in lg.runs]
    out: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for q in lg.irqs:
        if q.num != 0x09 or q.type != 0:
            continue
        j = bisect.bisect_left(starts, q.n)
        back = next((r for r in lg.runs[j:j + 400] if (r.m, r.cs, r.e0) == (q.m, q.cs, q.eip)), None)
        key = "game" if (q.m, q.cs) == ("P", GAME_CS) else f"{q.m} {q.cs:04x}:{q.eip:x}"
        if back is None:
            out[key].update(["merged"])        # 回到的那條與處理程式最後一段同 selector,併成一段,切不出來
        elif any(x.type == 0 and q.n < x.n < back.n_start for x in lg.irqs):
            out[key].update(["nested"])        # 處理期間又收了別的硬體中斷
        else:
            out[key].update([str(back.n_start - q.n)])
    return {a: dict(sorted(b.items())) for a, b in sorted(out.items())}


KB = {k: kb_costs(k) for k in ("lc171a", "lc172a", "lc172b")}
KB_GAME = sorted({int(c) for k in KB for c in KB[k].get("game", {}) if c.isdigit()})
assert KB_GAME and set(KB_GAME) <= {532, 533, 534}, KB


def reentry_post(k: str) -> tuple[collections.Counter, list[dict]]:
    recs = []
    for ln in TEXT[k]:
        if ln[:2] in ("E ", "R ", "A "):
            mt = _rx_era.match(ln)
            if mt:
                recs.append((mt.group(1), int(mt.group(3), 16), int(mt.group(4)), int(mt.group(5)), float(mt.group(6))))
    c: collections.Counter = collections.Counter()
    odd = []
    for p, q in zip(recs, recs[1:]):
        if p[0] == "E" and p[1] == REENTRY:
            v = (q[3] - p[3]) - (q[2] - p[2])
            c.update([v])
            if v not in (69, 70, 302, 303):
                odd.append({"t": p[4], "post": v, "n0": p[3], "n1": q[3]})
    return c, odd


POST = {k: reentry_post(k) for k in ("lc171a", "lc172a", "lc172b")}
assert {k: [o["post"] for o in v[1]] for k, v in POST.items()} == {"lc171a": [601], "lc172a": [602], "lc172b": [602]}, POST
SPLIT = {}
for k in ("lc172a", "lc172b"):
    o = POST[k][1][0]
    lg = LOG[k]
    kb = [q for q in lg.irqs if o["n0"] < q.n < o["n1"] and q.type == 0]
    assert [(q.num, q.m, q.cs, q.eip) for q in kb] == [(0x09, "p", 0x80, 0x6CA)], kb
    runs = [r for r in lg.runs if o["n0"] <= r.n_start < o["n1"] and r.cs != GAME_CS]
    normal = collections.Counter((r.e0, r.e1, r.count) for r in lg.runs if (r.m, r.cs, r.e0, r.e1) == ("p", 0x80, 0xED6, 0x6D5))
    (n_e0, n_e1, n_cnt), n_times = normal.most_common(1)[0]
    head = runs[0]
    assert (head.m, head.cs, head.e0, head.e1) == ("p", 0x80, 0xED6, 0x6C9) and head.n_end == kb[0].n, head
    assert runs[-1].cs == 0x80 and runs[-1].e1 == 0x6D5
    SPLIT[k] = {"t": o["t"], "post": o["post"], "kb_irq_ms": kb[0].t, "head": head.count, "normal_path": n_cnt,
                "normal_path_seen": n_times, "kb_handling": o["post"] - n_cnt}
    assert n_cnt == 69 and SPLIT[k]["kb_handling"] in KB_GAME, SPLIT[k]
# 續一百六十五 lc163a 的 DIG 601 / MDI 375;三份新紀錄都沒有 MDI 型的離群
assert S165["mdi_driver"]["post_nongame"] == {"DIG": {"69": 60, "70": 2, "601": 1}, "MDI": {"302": 14, "375": 1}}

# ================= (G) 更正續一百七十一 =================
# ev_s171 / doc98 續一百七十一寫「AX 在 0x300 .. 0x4ff 時 ljmp cs:[0x36] 轉給驅動」:反了。0x300 .. 0x4ff 是 DIG 自己的功能,
# 其餘(MDI 的 0x502)走 0x1ea -> 0x1fa ljmp cs:[0x36] 轉給舊向量。
S171 = json.loads((EVIDENCE / "calllog_segments_s171_20261030.json").read_text(encoding="utf-8"))
assert "ljmp cs:[0x36]" in S171["mdi_irq"]["chain"]["hook_137c_chain"]

CONC = {
    "dh0": f"P1 成立(兩份):delay 迴圈的 int 21h 只有一段連續走長路(lc172a {DH0['lc172a']['table']['cf1_loop|long']} 次、"
           f"lc172b {DH0['lc172b']['table']['cf1_loop|long']} 次),段內沒有短路、段外沒有長路;結束在 BIOS tick "
           f"{DH0['lc172a']['end_tick_ms']} / {DH0['lc172b']['end_tick_ms']} ms。TIME 12:00:54 依 DOSBox-X 公式是第 "
           f"{T0} 個 tick(換算 {TIME_CALC['dos_seconds_of_day_at_TIME'] % 60:.2f} 秒),秒數 0 共 {SEC0_TICKS} 個 tick;往前數 {SEC0_TICKS} 個 tick 落在資料允許的起點範圍內。",
    "slices": f"S 窗逐條的時間差全由換片 +1、rep 迭代、I/O 延遲(out +3 / in +5)、單次字串指令 +1、mov / pop ss −1、sti 換片 0 解釋。"
              f"乾淨的 delay(2) 每一次:5000·Δt − Δn − 時間片數 = {round(RESID['lc172a']['resid_minus_dk'][0])}(兩份相同)。"
              f"片頭每 ms {RESID['lc172b']['periods']['early']['slices_per_ms']} 片、新遊戲開場 {RESID['lc172b']['periods']['late']['slices_per_ms']} 片,"
              f"差的是 DOSBox-X Sound Blaster 的 DMA_DAC_Event(每 ms {EVRATE['early']['DMA_DAC_Event']} 次,"
              f"{DAC['start_ms_est']} .. {DAC['stop_ms_est']} ms:DIG 驅動初始化時的 IRQ7 之後到真正放音之前);"
              f"每個時間片在核心迴圈多減一個週期。續一百六十五的 delay 時間差 {S165_LINK['resid_step']} 週期 ≈ "
              f"22.05 × {_ph['early']['ms_median']} ms = {S165_LINK['dac_per_delay']}。",
    "rep": f"rep 的基準次數 = ⌈N / 4⌉(N = {REP_N});多記的每一次,rep 期間 k 都至少增加同樣次數(反例 0)。",
    "dig_137c": f"137c 是 DIG 驅動(DIG.INI 的 SB16.DIG;5 個 .DIG 的分派段逐位元組相同):AX 在 0x300 .. 0x4ff 且 BX 對上是自己的功能"
                f"(到 0x1e9 iret),其餘經 0x1fa ljmp cs:[0x36] 轉給舊向量。lc172a 第一次經過 137c 是 {HOOK['lc172a']['first_137c'][0]} ms 的自己功能,"
                f"之後 MDI 的 0x502 全經它轉送;續一百七十一「0x300 .. 0x4ff 時轉給驅動」寫反了。",
    "kb": f"int 09h 在遊戲碼收時處理 {KB_GAME[0]} .. {KB_GAME[-1]} 條;START 那一下的 602(lc172a / lc172b)是 DIG 型重入的 69 條在 0080:06ca "
          f"被鍵盤 IRQ 切開,中間 {SPLIT['lc172a']['kb_handling']} 條鍵盤處理;lc171a 的 601、續一百六十五 lc163a 的 601 同型。"
          f"MDI 375 三份新紀錄都沒再出現。",
}
for _part, _key in (("3634 次", "dh0"), ("4160 次", "dh0"), ("8051.9194 / 8055.2048", "dh0"), ("共 18 個 tick", "dh0"),
                    ("換算 53.97 秒", "dh0"), ("第一次經過 137c 是 3185.5406 ms 的自己功能", "dig_137c"), ("= 1445", "slices"), ("每 ms 22.05 次", "slices"), ("46.12 週期", "slices"), ("反例 0", "rep"),
                    ("'0080:6b0': 14", "rep"), ("SB16.DIG", "dig_137c"), ("寫反了", "dig_137c"), ("602", "kb"),
                    ("中間 533 條", "kb"), ("532 .. 534", "kb")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s172.py"),
    "exe_md5": MD5,
    "calllogs": {**{k: {"path": rel(RAW / f"{k}_CALLLOG.TXT"), "md5": v, "segs": SEGS} for k, v in LOGS.items()},
                 "lc171a": {"path": rel(RAW171 / "lc171a_CALLLOG.TXT"), "md5": LC171A_MD5}},
    "dosbox_src": rel(DRV / "dosbox_src_s172.txt"), "nm": rel(DRV / "nm_handlers_s172.txt"), "prediction": rel(DRV / "pred172.txt"),
    "validity": VALID,
    "dh0": {"time_calc": TIME_CALC, "runs": DH0},
    "slices": {"step_table": STEPS, "delay": RESID, "pic_event_rates_per_ms": EVRATE, "dma_dac": DAC, "irq7": IRQ7,
               "s165_link": S165_LINK},
    "rep": {"n": REP_N, "tables": REPT},
    "dig_137c": {"dispatcher": DISP, "dig_files_same_dispatcher": DIGS, "logged_positions": {k: [hex(e) for e, _c in v] for k, v in _pos.items()}, "dig_match": DIG_MATCH,
                 "hook": HOOK, "timing": TIMING},
    "keyboard": {"cost": KB, "game_cost_values": KB_GAME, "reentry_post": {k: dict(sorted(v[0].items())) for k, v in POST.items()},
                 "split": SPLIT},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, {k: v["table"] for k, v in DH0.items()}, RESID)
