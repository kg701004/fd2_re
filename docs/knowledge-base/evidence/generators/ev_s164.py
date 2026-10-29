"""續一百六十四證據:evidence/interrupt_off_sections_s164_20261029.json(續一百六十三「仍留」的離線分析;沒有實機)。

使用者 2026-10-29「還沒做的 請逐項自動進行處理」。只用續一百六十三已錄的 lc163a 呼叫紀錄與 FD2.EXE 反組譯,不重跑。
(A) 原始紀錄:沿用續一百六十三的指紋檢查;每筆 E / R / A 帶 i(遊戲 selector 指令數)、n(全部指令數)、t(ms)。
(B) 重入時關中斷的是哪一段:
    - DIG 服務 0x404c0 一進來就 `pushfd; cli`(0x404ea → 0x382d6 → 0x3f0a8),到結尾才還原(0x3f0ac 依存下的 IF 決定 sti);
      直接呼叫可達的 cli / sti 只有這三處。MDI 服務 0x43270 的可達集沒有 cli / sti,但會經 DPMI 0300h 呼叫真實模式 int 66h(驅動)。
    - 正常進入時「回呼返回 → 中斷處理程式結尾」的遊戲指令數是定值;重入從進來到重入自己的 A 記錄(在 0x3eb9d / 0x3eb69 偵測)
      的指令數 = 重入分支剩下 4 條 + 被打斷那段的剩餘 + 正常結尾。被打斷的點若在 DIG 的 sti 之後(STI 延遲一條)剩 12 條、
      在 MDI 的 int 31h 返回後剩 43 條;這兩個預測值和紀錄逐筆比對。
(C) 校準每圈慢約 1%(續一百六十一 1.033 拆出的 0.9898):校準與 delay 迴圈每圈都是一次 int 21h AH=2Ch;
    拆成每次 int 21h 的非遊戲指令數與每 ms 的指令數,並估 BIOS tick 能解釋多少。
(D) 0x37c30 沒被呼叫:AIL_startup 只在 getenv("AIL_DEBUG") 非空時才登錄這個 100 Hz 回呼;lc163 沒設環境變數。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import json
import statistics

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
import _exeops as X  # noqa: E402
from _exeops import insn  # noqa: E402
import callgraph_le as cg  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("interrupt_off_sections_s164_20261029.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
RAW = ROOT / ".wsl_build" / "lc163_live"
DELTA = 0x19C000
S161 = json.loads((EVIDENCE / "timer_base_and_delay_slowdown_s161_20261028.json").read_text(encoding="utf-8"))
S163 = json.loads((EVIDENCE / "timer_interrupt_loss_s163_20261029.json").read_text(encoding="utf-8"))
ISR, REENTRY, DIG, MDI, AIL100, CAL_FN, DELAY = 0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x37C30, 0x3DFEF, 0x3E01D
EPI, EPI_CHAIN = 0x3EB9D, 0x3EB69       # 中斷處理程式換回原堆疊後的第一條(不轉接 / 轉接 BIOS)

# ================= (A) 原始紀錄 =================
META = (RAW / "lc163a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG_MD5 = S163["run"]["calllog_md5"]
assert META[0].split() == [CALLLOG_MD5, "CALLLOG.TXT"] and META[1].split() == [MD5, "FD2.EXE"], META
_text = (RAW / "lc163a_CALLLOG.TXT").read_text(encoding="ascii")
assert _text.count("\n") == int(META[2]) == S163["run"]["lines"]
REC: list[dict] = []
for ln in _text.splitlines()[1:]:
    p = ln.split()
    if p[0] not in ("E", "R", "A"):
        continue
    kv = dict(x.split("=", 1) for x in p if "=" in x)
    if "t" not in kv:                    # 最後一筆被 teardown 截斷(續一百六十三)
        continue
    REC.append({"k": p[0], "seq": int(p[1]), "eip": int(p[2], 16) - DELTA,
                "at": int(p[3], 16) - DELTA if p[0] == "A" else None,
                "i": int(kv["i"]), "n": int(kv["n"]), "t": float(kv["t"]), "s": kv.get("s")})
assert sum(1 for ln in _text.splitlines() if ln[:2] in ("E ", "R ", "A ")) == len(REC) + 1   # 只少截斷的那一筆


def walk(start: int, end: int) -> list[str]:
    """[start, end) 逐條反組譯的文字;遇到解不出的位元組就 assert 失敗。"""
    out = []
    for ins in dl.sweep_range(X._MD, X._CODE, X._CBASE, start, end):
        assert not isinstance(ins, tuple), (hex(start), ins)
        out.append(f"{ins.mnemonic} {ins.op_str}".strip())
    return out


def at(addr: int) -> str:
    return insn(addr).strip()


def pairs(entry: int) -> list[tuple[dict, dict]]:
    """entry 的 (E, R) 配對(依序號);沒有 R 的(A 結束)不算。"""
    opn, out = {}, []
    for r in REC:
        if r["eip"] != entry:
            continue
        if r["k"] == "E":
            opn[r["seq"]] = r
        elif r["k"] == "R" and r["seq"] in opn:
            out.append((opn.pop(r["seq"]), r))
    return out


ISR_T = [r["t"] for r in REC if r["k"] == "E" and r["eip"] in (ISR, REENTRY)]

# ================= (B) 關中斷的區段:程式碼 =================
assert at(0x3EB11) == "mov al, 0x20" and at(0x3EB13) == "out 0x20, al" and at(0x3EB15) == "sti"   # 先 EOI、開中斷才叫回呼
assert at(ISR) == "cmp dword ptr cs:[0x2be6], 0" and at(0x3EA96) == "ja 0x3ebad"                # 忙碌中再進來 → 重入
REENTRY_REST = walk(REENTRY + 1, 0x3EBB4)
assert REENTRY_REST == ["mov al, 0x20", "out 0x20, al", "pop eax", "iretd"], REENTRY_REST
# DIG:進來就關,結尾才依存下的旗標開
assert at(0x404EA) == "call 0x382d6" and at(0x382D6) == "jmp 0x3f0a8"
assert walk(0x3F0A8, 0x3F0AC) == ["pushfd", "pop eax", "cli", "ret"]
assert [at(a) for a in (0x40502, 0x40534, 0x4066C)] == ["call 0x382db"] * 3 and at(0x382E0) == "call 0x3f0ac"
assert walk(0x3F0B5, 0x3F0C1) == ["test byte ptr [ebp + 5], 2", "cli", "je 0x3f0bd", "sti", "pop ebp", "popfd", "leave", "ret"]
_g = {}
SITES = {}
for seed, nm in ((DIG, "dig"), (MDI, "mdi")):
    g = cg.CG(str(GAME / "FD2.EXE"))
    g.build([seed])
    _g[nm] = g
    SITES[nm] = {m: sorted(hex(a) for a in g.reached if g._insn(a).mnemonic == m) for m in ("cli", "sti", "pushfd", "popfd")}
    SITES[nm]["int_0x31"] = sorted(hex(a) for a in g.reached if f"{g._insn(a).mnemonic} {g._insn(a).op_str}" == "int 0x31")
assert SITES["dig"]["cli"] == ["0x3f0aa", "0x3f0b9"] and SITES["dig"]["sti"] == ["0x3f0bc"], SITES["dig"]
assert SITES["mdi"]["cli"] == [] and SITES["mdi"]["sti"] == [], SITES["mdi"]
assert "0x3f1a2" in SITES["mdi"]["int_0x31"]
assert at(0x3F190) == "mov eax, 0x300" and at(0x3F195) == "mov ebx, 0x66" and at(0x3F1A2) == "int 0x31"   # DPMI 模擬真實模式 int 66h
assert at(0x4396B) == "call 0x382e9" and at(0x3836B) == "call 0x3f113"
assert any(t == 0x382E9 for a, t in _g["mdi"].calls.items() if a == 0x4396B)

# ================= (B) 關中斷的區段:紀錄 =================
# 正常進入時的結尾:DIG 的 R(記在 0x3eb42)→ 中斷處理程式的 A(換回原堆疊後偵測);MDI 的 R → 同一輪 DIG 的 E
_tail = collections.Counter()
_m2d = collections.Counter()
for p, q in zip(REC, REC[1:]):
    if p["k"] == "R" and p["eip"] == DIG and q["k"] == "A" and q["eip"] == ISR:
        _tail[(q["at"], q["i"] - p["i"])] += 1
    if p["k"] == "R" and p["eip"] == MDI and q["k"] == "E" and q["eip"] == DIG:
        _m2d[q["i"] - p["i"]] += 1
NORMAL_TAIL = {EPI: None, EPI_CHAIN: None}
for (a, d), c in _tail.items():
    assert a in NORMAL_TAIL and NORMAL_TAIL[a] is None, _tail                                  # 每個結尾點只有一個值
    NORMAL_TAIL[a] = d
assert NORMAL_TAIL[EPI_CHAIN] == NORMAL_TAIL[EPI] + 1, NORMAL_TAIL                            # 轉接 BIOS 多一條 dec
MDI_TO_DIG, _c = _m2d.most_common(1)[0]
assert _c / sum(_m2d.values()) > 0.99, _m2d
# 被打斷那段剩下的指令(靜態):DIG = sti 之後再一條(pop ebp)才收中斷,剩 popfd .. DIG 的 ret
DIG_TAIL = walk(0x3F0BE, 0x3F0C1) + walk(0x382E5, 0x382E9) + walk(0x40671, 0x40684)
assert DIG_TAIL[-1] == "ret" and len(DIG_TAIL) == 12, DIG_TAIL
# MDI:int 31h 返回後的第一條起,一路到 MDI 的 ret。分支方向:
#   0x3f1aa je —— [ebp+0x14] 是第 4 個引數,0x43956 先推的 0;0x3837c je —— [0x54174] 只有 AIL_DEBUG 分支才設 1(見 D)
assert walk(0x43956, 0x4396B)[0] == "push 0" and sum(s.startswith("push") for s in walk(0x43956, 0x4396B)) == 4
assert walk(0x38357, 0x3836B) == ["mov ecx, dword ptr [esp + 0x1c]", "push ecx", "mov esi, dword ptr [esp + 0x1c]", "push esi",
                                  "mov edi, dword ptr [esp + 0x1c]", "push edi", "mov ebp, dword ptr [esp + 0x1c]", "push ebp"]
MDI_TAIL = (walk(0x3F1A4, 0x3F1AC) + walk(0x3F1DB, 0x3F1E5) + [at(0x3806F)] + walk(0x3EA81, 0x3EA8E)
            + walk(0x3F1E5, 0x3F1ED) + walk(0x38370, 0x38382) + walk(0x3916A, 0x39176) + walk(0x43970, 0x43996))
assert MDI_TAIL[2] == "je 0x3f1db" and MDI_TAIL[6] == "jmp 0x3ea81" and "je 0x3916a" in MDI_TAIL, MDI_TAIL
assert len(MDI_TAIL) == 43 and MDI_TAIL[-1] == "ret", len(MDI_TAIL)
PRED = {"dig_restore": {EPI: len(REENTRY_REST) + len(DIG_TAIL) + 1 + NORMAL_TAIL[EPI],
                        EPI_CHAIN: len(REENTRY_REST) + len(DIG_TAIL) + 1 + NORMAL_TAIL[EPI_CHAIN]},
        "mdi_driver_return": len(REENTRY_REST) + len(MDI_TAIL) + 1 + MDI_TO_DIG}

# 5 ms 格點(同續一百六十三):晚到 = 進入時間 − 所在格的格點
P = S161["timer_channels"]["pit_divisor"] / 1193182 * 1000
_dig0 = next(r["t"] for r in REC if r["k"] == "E" and r["eip"] == DIG)
WIN = [r["t"] for r in REC if r["k"] == "E" and r["eip"] == ISR and r["t"] >= _dig0 - 0.05]
_ph = collections.Counter(round((t - WIN[0] + P / 2) % P - P / 2, 2) for t in WIN)
G0 = WIN[0] + _ph.most_common(1)[0][0] - P
_isr_only = [r["t"] for r in REC if r["k"] == "E" and r["eip"] == ISR]


def lateness(t_reentry: float) -> float:
    o = _isr_only[bisect.bisect_right(_isr_only, t_reentry) - 1]   # 重入那次中斷的 0x3ea8e 進入
    assert t_reentry - o < 0.05
    return o - (G0 + int((o - G0 + 0.2) // P) * P)


CLASS = collections.defaultdict(list)
for k, r in enumerate(REC):
    if not (r["k"] == "E" and r["eip"] == REENTRY):
        continue
    q = REC[k + 1]
    d = q["i"] - r["i"]
    if q["k"] == "A" and q["eip"] == REENTRY and d == PRED["dig_restore"].get(q["at"]):
        c = "dig_restore"
    elif q["k"] == "E" and q["eip"] == DIG and d == PRED["mdi_driver_return"]:
        c = "mdi_driver_return"
    else:
        c = "other"
    CLASS[c].append({"t": round(r["t"], 3), "late_ms": round(lateness(r["t"]), 2), "next": f"{q['k']} {q['eip']:#x}", "di": d})
COUNT = {c: len(CLASS[c]) for c in ("dig_restore", "mdi_driver_return", "other")}
LATE_TH = 0.3
LATE = {c: sum(1 for x in CLASS[c] if x["late_ms"] > LATE_TH) for c in COUNT}
_run = S163["reentry"]["callback_running"]
assert sum(COUNT.values()) == S163["reentry"]["count"] == 78 and sum(LATE.values()) == S163["reentry"]["late_gt_0_3ms"]
assert COUNT["dig_restore"] == _run["DIG"] + _run["DIG+MDI"], (COUNT, _run)                    # DIG 還沒返回的全是這一型
assert COUNT["mdi_driver_return"] + COUNT["other"] == _run["MDI"], (COUNT, _run)
# DIG 型:61 次晚到 0.7 .. 4 ms,另 2 次 sti 剛好落在格點附近(±0.2 ms);都在同一個固定點收中斷
assert LATE["dig_restore"] == 61 and all(abs(x["late_ms"]) < LATE_TH for x in CLASS["dig_restore"] if x["late_ms"] <= LATE_TH), LATE
assert COUNT["dig_restore"] == 63 and COUNT["mdi_driver_return"] == 14 and COUNT["other"] == 1, COUNT
CHAIN_N = sum(1 for k, r in enumerate(REC) if r["k"] == "E" and r["eip"] == REENTRY
              and REC[k + 1]["k"] == "A" and REC[k + 1]["at"] == EPI_CHAIN)
DIG_LATE_RANGE = [min(x["late_ms"] for x in CLASS["dig_restore"]), max(x["late_ms"] for x in CLASS["dig_restore"])]
MDI_LATE = sorted(x["late_ms"] for x in CLASS["mdi_driver_return"])
# 對照:MDI 服務 E→R 的指令大半不在遊戲 selector(真實模式驅動)
_mdi_long = [(r["n"] - e["n"] - (r["i"] - e["i"])) / (r["n"] - e["n"]) for e, r in pairs(MDI) if r["t"] - e["t"] > 2]
MDI_LONG_NONGAME = round(statistics.median(_mdi_long), 3)
assert MDI_LONG_NONGAME > 0.7, MDI_LONG_NONGAME
assert (PRED, CHAIN_N, DIG_LATE_RANGE, MDI_LONG_NONGAME) == (
    {"dig_restore": {EPI: 93, EPI_CHAIN: 94}, "mdi_driver_return": 62}, 7, [-0.18, 4.5], 0.819), (PRED, CHAIN_N, DIG_LATE_RANGE)
assert MDI_LATE == [0.19, 0.2, 0.21, 0.22, 0.27, 0.34, 0.83, 0.83, 0.83, 0.85, 2.02, 2.19, 2.42, 2.42], MDI_LATE
assert CLASS["other"] == [{"t": 3665.216, "late_ms": 1.95, "next": "E 0x43270", "di": 57}], CLASS["other"]
assert (NORMAL_TAIL, MDI_TO_DIG, len(REENTRY_REST), len(DIG_TAIL), len(MDI_TAIL)) == ({EPI: 76, EPI_CHAIN: 77}, 14, 4, 12, 43)

# ================= (C) 校準每圈慢約 1% =================
_cl = walk(CAL_FN, 0x3E01D)
assert _cl[2:4] == ["mov ah, 0x2c", "int 0x21"] and len(_cl) == 24
CAL_PRE, CAL_WAIT, CAL_MID, CAL_CNT, CAL_POST = (len(walk(CAL_FN, 0x3DFFB)), len(walk(0x3DFFB, 0x3E007)), len(walk(0x3E007, 0x3E00B)),
                                                  len(walk(0x3E00B, 0x3E014)), len(walk(0x3E014, 0x3E01D)))
assert (CAL_PRE, CAL_WAIT, CAL_MID, CAL_CNT, CAL_POST) == (7, 6, 2, 5, 4)
assert walk(0x3E00B, 0x3E014) == ["mov ah, 0x2c", "int 0x21", "inc esi", "cmp bl, dh", "je 0x3e00b"]
(CE, CR), = pairs(CAL_FN)
CAL_DI, CAL_DN, CAL_DT = CR["i"] - CE["i"], CR["n"] - CE["n"], CR["t"] - CE["t"]
_lin = CAL_DI - CAL_PRE - CAL_MID - CAL_POST                                       # = 6W + 5C(W 等待圈、C 校準值)
C_LO, C_HI = S163["calibration"]["this_run_calibration_bounds"]
_x = [w + c + 1 for c in range(C_LO, C_HI + 1) for w in [(_lin - CAL_CNT * c) // CAL_WAIT]
      if (_lin - CAL_CNT * c) % CAL_WAIT == 0 and w > 0]
X_RANGE = [min(_x), max(_x)]                                                       # 校準期間 int 21h 的次數
_dl = walk(DELAY, 0x3E04B)
assert _dl[14:16] == ["jne 0x3e047", "inc esi"] and len(_dl) == 18                  # 圈數非 0 時跳過 inc
assert walk(0x3E04B, 0x3E054) == ["mov ah, 0x2c", "int 0x21", "cmp bl, dh", "dec esi", "jne 0x3e04b"]
DELAY_FIXED = len(_dl) - 1 + len(walk(0x3E054, 0x3E058))
_clean = [(e, r) for e, r in pairs(DELAY)
          if not any(e["t"] < t < r["t"] for t in ISR_T[max(0, bisect.bisect_left(ISR_T, e["t"]) - 1):][:3])
          and r["i"] - e["i"] == DELAY_FIXED + 5 * 18]
assert len(_clean) == S163["calibration"]["bound_from"]["delay(2) = 18 圈"], len(_clean)
DELAY_DN = statistics.median(r["n"] - e["n"] for e, r in _clean)
NG_DELAY = round((DELAY_DN - (DELAY_FIXED + 5 * 18)) / 18, 2)                       # 每次 int 21h 的非遊戲指令
NG_CAL = [round((CAL_DN - CAL_DI) / x, 2) for x in (X_RANGE[1], X_RANGE[0])]
NMS = {"calibration": round(CAL_DN / CAL_DT, 1),
       "delay_clean": round(sum(r["n"] - e["n"] for e, r in _clean) / sum(r["t"] - e["t"] for e, r in _clean), 1)}
# AIL 接管 int 8 之前被 BIOS tick 打斷的呼叫:遊戲指令數同常值、非遊戲指令多出來的量
_isr0 = next(r["t"] for r in REC if r["k"] == "E" and r["eip"] == ISR)
_pre = collections.defaultdict(list)
for e in {r["eip"] for r in REC if r["k"] == "E" and r["t"] < _isr0} - {CAL_FN}:
    for a, b in pairs(e):
        if b["t"] < _isr0:
            _pre[(e, b["i"] - a["i"])].append((b["n"] - a["n"] - (b["i"] - a["i"]), round(a["t"], 1)))
TICK_SAMPLES = []
for (e, di), v in _pre.items():
    base = statistics.median(x for x, _ in v)
    TICK_SAMPLES += [{"fn": hex(e), "t": t, "extra_nongame": round(x - base)} for x, t in v if x - base > 100]
assert TICK_SAMPLES == [{"fn": "0x370f0", "t": 3311.7, "extra_nongame": 689}], TICK_SAMPLES
TICK_MS = 65536 / 1193182 * 1000
TICKS_CAL = CAL_DT / TICK_MS
_tick_per_call = [round(-(-TICKS_CAL // 1) * TICK_SAMPLES[0]["extra_nongame"] / x, 2) for x in (X_RANGE[1], X_RANGE[0])]
EXCESS = [round(NG_CAL[0] - _tick_per_call[1] - NG_DELAY, 2), round(NG_CAL[1] - _tick_per_call[0] - NG_DELAY, 2)]
assert NG_CAL[0] > NG_DELAY and EXCESS[0] > 0, (NG_CAL, NG_DELAY, EXCESS)                       # tick 扣掉仍有剩
_per_iter = [round(CAL_DN / x, 2) for x in (X_RANGE[1], X_RANGE[0])]
INSN_RATIO = [round(v / (NG_DELAY + 5), 4) for v in _per_iter]
TIME_PER_INSN_RATIO = round(NMS["delay_clean"] / NMS["calibration"], 4)
assert TIME_PER_INSN_RATIO < 1 < INSN_RATIO[0]                                     # 指令多、每條稍快
CALIB = {"loop_layout": {"prefix": CAL_PRE, "wait_loop": CAL_WAIT, "between": CAL_MID, "count_loop": CAL_CNT, "suffix": CAL_POST},
         "delta_i": CAL_DI, "delta_n": CAL_DN, "delta_t_ms": round(CAL_DT, 4), "int21_calls_range": X_RANGE,
         "nongame_per_int21_calibration": NG_CAL, "nongame_per_int21_delay": NG_DELAY,
         "delay_clean_count": len(_clean), "delay_fixed_game_insns": DELAY_FIXED,
         "insn_per_ms": NMS, "insn_per_iter_ratio": INSN_RATIO, "time_per_insn_ratio": TIME_PER_INSN_RATIO,
         "bios_tick_samples_pre_ail": TICK_SAMPLES, "bios_ticks_in_calibration": round(TICKS_CAL, 2),
         "tick_share_per_int21": _tick_per_call, "excess_per_int21_after_ticks": EXCESS,
         "s163_rate_ratio": S163["calibration"]["s161_ratio_split"]["rate_ratio"]}

assert {k: CALIB[k] for k in ("int21_calls_range", "nongame_per_int21_calibration", "nongame_per_int21_delay", "insn_per_ms",
                              "insn_per_iter_ratio", "time_per_insn_ratio", "bios_ticks_in_calibration",
                              "tick_share_per_int21", "excess_per_int21_after_ticks")} == {
    "int21_calls_range": [13085, 13167], "nongame_per_int21_calibration": [481.49, 484.51], "nongame_per_int21_delay": 475.94,
    "insn_per_ms": {"calibration": 4232.4, "delay_clean": 4215.0}, "insn_per_iter_ratio": [1.0122, 1.0185],
    "time_per_insn_ratio": 0.9959, "bios_ticks_in_calibration": 27.57, "tick_share_per_int21": [1.47, 1.47],
    "excess_per_int21_after_ticks": [4.08, 7.1]}, CALIB

# ================= (D) 0x37c30 只在 AIL_DEBUG 時登錄 =================
assert dl.object_bytes(X._EXE, X._META, 0x50313, 10) == b"AIL_DEBUG\0"
assert [at(a) for a in (0x37D57, 0x37D5C, 0x37D66, 0x37D68, 0x37D6A, 0x37D6F)] == [
    "push 0x313", "call 0x3f48b", "test eax, eax", "jne 0x37d74", "call 0x3fca9", "jmp 0x37ed1"]   # 沒設 → 只初始化計時器就跳走
assert [at(a) for a in (0x37E76, 0x37E7B, 0x37E88, 0x37E8B, 0x37E99)] == [
    "push 0x27c30", "call 0x3f236", "push 0x64", "call 0x3f3c8", "call 0x3f2f0"]                 # 有設才登錄 100 Hz 並啟動
assert 0x37D6A < 0x37E76 < 0x37ED1 and at(0x37EA6) == "mov dword ptr [0x4174], edx" and at(0x37EA1) == "mov edx, 1"
_refs = sorted(a for a, t in dl.build_fixups(X._EXE, X._META).items() if t == AIL100)
assert _refs == [0x37E77], [hex(a) for a in _refs]                                 # 全部 object 只有這一處拿 0x37c30 的位址
_drv = (GEN_DIR / "drivers_s163" / "lc163.py").read_text(encoding="utf-8")
_hs = (ROOT / "tools" / "dosbox_harness.sh").read_text(encoding="utf-8")
assert "DOS_SET" not in _drv and "AIL_DEBUG" not in _drv
assert "dos_set_args+=\" -c 'SET $kv'\"" in _hs and 'if [[ -n "${FD2_HARNESS_DOS_SET:-}" ]]; then' in _hs
assert S163["callbacks"]["ail_internal_0x37c30_calls"] == 0
_bios = S163["timeline"]["pre_dig_intervals_ms"]["bios_18hz"]
assert _bios[0] > 50                                                              # AIL 接管後第一格仍是 BIOS 18.2 Hz(沒有 10 ms 通道)
GATE = {"getenv_arg": "0x50313 \"AIL_DEBUG\"", "getenv_call": "0x37d5c", "no_debug_path": "0x37d6a → 0x37ed1",
        "register": "0x37e76 push 0x27c30 → 0x3f236;0x37e8b 100 Hz;0x37e99 start", "debug_flag": "[0x54174] = 1 at 0x37ea6",
        "lc163_sets_env": False, "calls_in_lc163a": S163["callbacks"]["ail_internal_0x37c30_calls"],
        "first_interval_after_ail_ms": _bios[0]}
assert GATE["first_interval_after_ail_ms"] == 54.925, GATE

CONC = {
    "interrupt_off": f"DIG 服務 0x404c0 整段關中斷:進來就 cli(0x404ea → 0x3f0aa),到結尾 0x3f0ac 才 sti。"
                     f"DIG 還沒返回時的重入 {COUNT['dig_restore']} 次,{LATE['dig_restore']} 次晚到超過 {LATE_TH} ms"
                     f"(範圍 {DIG_LATE_RANGE[0]} .. {DIG_LATE_RANGE[1]} ms),而且每一次重入到結尾的指令數都等於「在 sti 之後一條收中斷」的預測值({PRED['dig_restore'][EPI]} / 轉接 BIOS 時 "
                     f"{PRED['dig_restore'][EPI_CHAIN]})。MDI 的 {COUNT['mdi_driver_return']} 次重入都在 int 31h(DPMI 0300h、"
                     f"真實模式 int 66h 驅動)返回後的第一條收中斷(預測 {PRED['mdi_driver_return']},逐筆相符);"
                     f"MDI 本身沒有 cli,中斷被擋到 DPMI 呼叫返回;是驅動自己關中斷還是 DOS/4GW 在真實模式期間不轉送,沒查。",
    "calibration": f"校準與 delay 每圈都是一次 int 21h AH=2Ch。校準期間每次 int 21h 的非遊戲指令 {NG_CAL[0]} .. {NG_CAL[1]} 條,"
                   f"遊戲中沒遇到中斷的 delay 是 {NG_DELAY} 條;每 ms 的指令數反而多 {1 / TIME_PER_INSN_RATIO - 1:.2%}。"
                   f"BIOS tick 以 AIL 接管前唯一的樣本({TICK_SAMPLES[0]['extra_nongame']} 條)、{-(-TICKS_CAL // 1):.0f} 個 tick 估,每次約 {_tick_per_call[1]} 條,"
                   f"扣掉後每次仍多 {EXCESS[0]} .. {EXCESS[1]} 條,原因沒找到。",
    "ail_100hz": "0x37c30 是 AIL 除錯紀錄的碼錶回呼,AIL_startup 只在 getenv(\"AIL_DEBUG\") 非空時登錄(0x37d5c / 0x37d68);"
                 "lc163 沒設 FD2_HARNESS_DOS_SET,所以這段 0 次。續一百六十三預測的「約 0.5 倍」沒考慮這個條件。",
}
for _part, _key in (("範圍 -0.18 .. 4.5 ms", "interrupt_off"), ("預測值(93 / 轉接 BIOS 時 94)", "interrupt_off"),
                     ("非遊戲指令 481.49 .. 484.51 條", "calibration"), ("delay 是 475.94 條", "calibration"),
                     ("反而多 0.41%", "calibration"), ("(689 條)、28 個 tick 估,每次約 1.47 條", "calibration"),
                     ("仍多 4.08 .. 7.1 條", "calibration")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s164.py"),
    "exe_md5": MD5,
    "approval": "使用者 2026-10-29「還沒做的 請逐項自動進行處理」;離線分析,沒有實機",
    "source_run": {"calllog": rel(RAW / "lc163a_CALLLOG.TXT"), "calllog_md5": CALLLOG_MD5, "records": len(REC)},
    "interrupt_off": {
        "isr_eoi_sti_before_callbacks": "0x3eb11 .. 0x3eb15",
        "dig_disable": "0x404ea call 0x382d6 → 0x3f0a8 pushfd; pop eax; cli",
        "dig_restore_sites": ["0x40502", "0x40534", "0x4066c"], "restore_fn": "0x3f0ac(存下的 IF = 1 才 sti 0x3f0bc)",
        "direct_call_sites": SITES,
        "mdi_driver_call": "0x4396b → 0x382e9 → 0x3f113:DPMI 0300h(0x3f190)模擬真實模式 int 66h(0x3f195),int 31h 在 0x3f1a2",
        "normal_tail": {"dig_R_to_isr_A": {hex(k): v for k, v in NORMAL_TAIL.items()}, "mdi_R_to_dig_E": MDI_TO_DIG},
        "static_tail": {"reentry_rest": len(REENTRY_REST), "dig_after_sti_shadow": len(DIG_TAIL),
                        "mdi_after_int31_return": len(MDI_TAIL)},
        "predicted_di": {"dig_restore": {hex(k): v for k, v in PRED["dig_restore"].items()},
                         "mdi_driver_return": PRED["mdi_driver_return"]},
        "reentry_classes": COUNT, "late_gt_0_3ms": LATE, "dig_restore_chain": CHAIN_N,
        "dig_late_range_ms": DIG_LATE_RANGE, "mdi_late_ms": MDI_LATE, "other": CLASS["other"],
        "mdi_long_spans_nongame_share": MDI_LONG_NONGAME},
    "calibration": CALIB,
    "ail_debug_gate": GATE,
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, COUNT, LATE, "ng", NG_CAL, NG_DELAY, "excess", EXCESS)
