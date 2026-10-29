"""續一百六十三證據:evidence/timer_interrupt_loss_s163_20261029.json(③b 實機,lc163a;
使用者 2026-10-29「還沒做的兩件 請依照你的建議自動進行處理」核准一次)。

③b:續一百五十八量到 BIOS tick 平均比 54.925 ms 長(有計時器中斷沒算進去),續一百六十一靜態找到兩條可能的路:
`0x3ea8e` 重入時走 `0x3ebad` 只送 EOI 就返回(這次中斷不加任何通道的累加器),或關中斷期間 IRQ 疊在一起被合併。
這次從開機錄到標題 START 之後的新遊戲開場(修補版 dosbox-x,ICOUNT,不設閘門),入口含中斷處理程式、重入分支、
DIG / MDI / AIL 內部服務與校準函式。預測 P1 .. P4 在 drivers_s163/pred163_3b.txt(實機前寫)。
(A) 原始紀錄:指紋、表頭、入口與預測檔一致、harness 的執行結果。
(B) 中斷時間軸:BIOS 18.2 Hz → MDI 120 Hz(8.333 ms)→ DIG 起 200 Hz(5 ms);5 ms 格點對齊後數合併(空格)與重入。
(C) 重入的成因:重入當下哪個回呼還沒返回;回呼次數與正常進入數的比例。
(D) 校準 0x3dfef:DOS 時間由 BIOS tick 換算,返回時 DL = 5 → 數到的「一秒」正好 19 個 tick;delay(2) 的圈數限制本輪校準值;
    續一百六十一「校準 / 沒中斷 = 1.033」拆成 19 tick 的長度與校準期間每圈較慢。
全部從 .wsl_build/lc163_live/ 與 FD2.EXE 重算;任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import json
import math

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import insn, operand  # noqa: E402

OUT = out_path("timer_interrupt_loss_s163_20261029.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
RAW = ROOT / ".wsl_build" / "lc163_live"
DELTA = 0x19C000                        # 紀錄裡的 EIP = linear + DELTA(續一百五十九起)
PRED = GEN_DIR / "drivers_s163" / "pred163_3b.txt"
S158 = json.loads((EVIDENCE / "followups_s158_20261027.json").read_text(encoding="utf-8"))
S161 = json.loads((EVIDENCE / "timer_base_and_delay_slowdown_s161_20261028.json").read_text(encoding="utf-8"))
ISR, REENTRY, DIG, MDI, AIL100, CAL_FN, AIL_CALL, DELAY = (0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x37C30,
                                                           0x3DFEF, 0x25C01, 0x3E01D)
NAMES = {CAL_FN: "calibration", AIL_CALL: "main_call_AIL_startup", 0x1F894: "title_seq", 0x1FC66: "intro_key_exit",
         0x1FD7C: "menu_kbd_flush", 0x1FED3: "confirm", 0x1FEF0: "blink", 0x1FF31: "fade", 0x1FF36: "clear",
         0x32326: "new_game"}

# ================= (A) 原始紀錄 =================
META = (RAW / "lc163a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG_MD5 = "3bebd4f463c821dfc137cd267c5c6112"
assert META[0].split() == [CALLLOG_MD5, "CALLLOG.TXT"], META
assert META[1].split() == [MD5, "FD2.EXE"], META           # harness 目錄裡跑的就是原版
HDR = META[3]
assert HDR.startswith("H fd2calllog 1 cs=0170 ") and "icount=1" in HDR and "gate=" not in HDR, HDR
ENTRY_RT = [int(x, 16) for x in META[4].split()]
NATIVE = sorted(a - DELTA for a in ENTRY_RT)
assert len(NATIVE) == 19 and f"entries={len(NATIVE)}" in HDR
_pred = PRED.read_text(encoding="utf-8")
assert all(f"{a:#x}" in _pred for a in NATIVE), [hex(a) for a in NATIVE if f"{a:#x}" not in _pred]
RUN = json.loads((RAW / "lc163a_run.json").read_text(encoding="utf-8"))
HARNESS = [a[:2] for a in RUN["assertions"]]
assert RUN["ok"] and HARNESS == [["instance_up", True], ["poll_title", True]], RUN

_text = (RAW / "lc163a_CALLLOG.TXT").read_text(encoding="ascii")
# teardown 砍掉 DOSBox-X 時最後一行寫到一半:換行數 = wc -l,最後一行沒有換行
assert _text.count("\n") == int(META[2]) and not _text.endswith("\n")
_lines = _text.splitlines()
assert _lines[0] == HDR
REC: list[dict] = []
for ln in _lines[1:]:
    p = ln.split()
    if p[0] not in ("E", "R", "A"):
        continue
    kv = dict(x.split("=", 1) for x in p if "=" in x)
    REC.append({"k": p[0], "seq": int(p[1]), "eip": int(p[2], 16) - DELTA, "f": p[3:],
                "t": float(kv["t"]) if "t" in kv else None, "i": int(kv["i"]) if "i" in kv else None,
                "s": kv.get("s")})
UNTIMED = [r for r in REC if r["t"] is None]
# 最後一筆 A 記錄被 teardown 截斷(沒有 t),只有這一筆
assert len(UNTIMED) == 1 and UNTIMED[0] is REC[-1] and UNTIMED[0]["eip"] == ISR, UNTIMED
assert {r["eip"] for r in REC} <= set(NATIVE)


def times(kind: str, eip: int) -> list[float]:
    return [r["t"] for r in REC if r["k"] == kind and r["eip"] == eip and r["t"] is not None]


COUNTS = {name: len(times("E", a)) for name, a in (("isr", ISR), ("reentry", REENTRY), ("dig", DIG), ("mdi", MDI),
                                                    ("ail_100hz", AIL100), ("delay", DELAY))}

# ================= (B) 中斷時間軸 =================
_ch = S161["timer_channels"]
DIVISOR = _ch["pit_divisor"]
PIT_HZ = 1193182                        # DOSBox-X 的 PIT_TICK_RATE
P = DIVISOR / PIT_HZ * 1000             # 200 Hz 期的實際週期(ms)
TICK_MS = 65536 / PIT_HZ * 1000         # BIOS 18.2 Hz 的 tick(ms)
assert DIVISOR == 5966 and _ch["base_us"] == 5000
ISR_T = times("E", ISR)
DIG0, MDI0 = times("E", DIG)[0], times("E", MDI)[0]
CAL_E, CAL_R = (next(r for r in REC if r["eip"] == CAL_FN and r["k"] == k) for k in ("E", "R"))
AIL_T = times("E", AIL_CALL)[0]
assert CAL_R["t"] < AIL_T < ISR_T[0], (CAL_R["t"], AIL_T, ISR_T[0])          # P4:校準時還沒有 AIL 的中斷
_dt = [b - a for a, b in zip(ISR_T, ISR_T[1:])]
W0 = max(i for i, t in enumerate(ISR_T) if t <= DIG0)                         # DIG 第一次被服務的那次中斷
M0 = max(i for i, t in enumerate(ISR_T) if t <= MDI0)
# DIG 之前的間隔:> 20 ms 是 18.2 Hz 期(AIL 剛接管 int 8),其餘是 MDI 的 8333 µs 基底;
# 每次換基底 AIL 都重寫 PIT,換的那一格長度不完整(第一格 8.366、最後一格 7.208)
PRE = {"bios_18hz": [round(x, 3) for x in _dt[:W0] if x > 20],
       "mdi_120hz": [round(x, 3) for x in _dt[:W0] if x <= 20]}
assert abs(_dt[0] - TICK_MS) < 0.01 and M0 == len(PRE["bios_18hz"]) + 1, (PRE, M0)
assert all(abs(x - _ch["period_us"]["MDI 服務 0x43270"] / 1000) < 0.002 for x in PRE["mdi_120hz"][1:-1]), PRE
WIN = ISR_T[W0:]
T0, T1 = WIN[0], WIN[-1]
_ph = collections.Counter(round((t - T0 + P / 2) % P - P / 2, 2) for t in WIN)   # 置中到 ±P/2,0 附近不會被折成兩半
PHI = _ph.most_common(1)[0][0]
ON_GRID = sum(v for k, v in _ph.items() if abs(k - PHI) <= 0.1)
G0 = T0 + PHI - P                                                             # 格點原點(往前一格)
SLOT: dict[int, list[float]] = collections.defaultdict(list)
for t in WIN:
    SLOT[int((t - G0 + 0.2) // P)].append(t)
K_LO, K_HI = min(SLOT), max(SLOT)
EMPTY = [k for k in range(K_LO, K_HI + 1) if k not in SLOT]
LATE = {k: v[0] - (G0 + k * P) for k, v in SLOT.items()}
DOUBLE = sorted(k for k, v in SLOT.items() if len(v) > 1)
RE_T = times("E", REENTRY)
assert RE_T[0] > T0                                                           # 重入都在 200 Hz 期


def owner(t: float) -> float | None:
    """重入那一筆對應的中斷進入:t 之前最近、差不到 0.05 ms 的 0x3ea8e。"""
    j = bisect.bisect_right(ISR_T, t) - 1
    return ISR_T[j] if j >= 0 and t - ISR_T[j] < 0.05 else None


RE_OWN = [owner(t) for t in RE_T]
assert all(o is not None for o in RE_OWN)
RE_SLOT = [int((o - G0 + 0.2) // P) for o in RE_OWN]
LATE_TH = 0.3
RE_LATE = sum(1 for k in RE_SLOT if LATE[k] > LATE_TH)
LATE_ALL = sorted(k for k in SLOT if LATE[k] > LATE_TH)
LATE_NONRE = [k for k in LATE_ALL if k not in set(RE_SLOT)]
N_SLOTS = K_HI - K_LO + 1
LOST = len(RE_T) + len(EMPTY)
TICK_AVG = round(_ch["period_us"]["BIOS 轉接(通道 15)"] / 1000 / (1 - LOST / N_SLOTS), 2)

ev = sorted((r["t"], NAMES[r["eip"]]) for r in REC if r["k"] == "E" and r["eip"] in NAMES)
EVENTS = [(round(t, 3), n) for t, n in ev]


def phase(t: float) -> str:
    cur = "boot"
    for tt, nm in ev:
        if tt <= t:
            cur = nm
    return cur


RE_PHASE = dict(sorted(collections.Counter(phase(t) for t in RE_T).items()))
EMPTY_AT = [[round(G0 + k * P, 3), phase(G0 + k * P)] for k in EMPTY]

# ================= (C) 重入的成因 =================
SPANS: dict[int, list[tuple[float, float]]] = {DIG: [], MDI: []}
_open: dict[tuple[int, int], float] = {}
for r in REC:
    if r["eip"] in SPANS and r["t"] is not None:
        if r["k"] == "E":
            _open[(r["eip"], r["seq"])] = r["t"]
        elif (r["eip"], r["seq"]) in _open:
            SPANS[r["eip"]].append((_open.pop((r["eip"], r["seq"])), r["t"]))
RUNNING = collections.Counter()
for t in RE_T:
    RUNNING["+".join(nm for a, nm in ((DIG, "DIG"), (MDI, "MDI")) if any(s < t < e for s, e in SPANS[a])) or "none"] += 1
LONG = {nm: sum(1 for s, e in SPANS[a] if e - s > P) for a, nm in ((DIG, "DIG"), (MDI, "MDI"))}
NORMAL_DIG = sum(1 for t in ISR_T if t >= ISR_T[W0]) - len(RE_T)
NORMAL_MDI = sum(1 for t in ISR_T if t >= ISR_T[M0]) - len(RE_T)

# ================= (D) 校準 =================
assert (insn(0x3DFF1), insn(0x3DFF3), insn(0x3E00F)) == ("mov ah, 0x2c", "int 0x21", "inc esi")
assert insn(0x3E010) == "cmp bl, dh" and insn(0x3E012) == "je 0x3e00b"     # 秒數(DH)一變就停
CAL_SLOT = operand(0x3E014, "mov dword ptr [", "], esi")
assert CAL_SLOT == 0x41B0                                                     # fixup 後是 0x541b0
EDX = int(CAL_R["f"][1], 16)                                                  # R seq entry eax edx esp
DH, DL = EDX >> 8 & 0xFF, EDX & 0xFF
CS_PER_TICK = 100 / (PIT_HZ / 65536)                                          # DOSBox-X dos.cpp 0x2c:time = 100/(PIT/65536) × ticks
TICKS_IN_SECOND = set()
for k in range(1000):                                                         # 返回時 DL 的分數部分 u ∈ [DL, DL + 1)
    u = DL + k / 1000
    # 往前第 m 個 tick 還在上一秒、第 m + 1 個已經是再上一秒 → 上一秒正好 m 個 tick
    ms_ = [m for m in range(1, 60) if u - CS_PER_TICK * (m + 1) < -100 <= u - CS_PER_TICK * m]
    assert len(ms_) == 1, (u, ms_)
    TICKS_IN_SECOND.add(ms_[0])
COUNT_MS = round(max(TICKS_IN_SECOND) * TICK_MS, 2)
WAIT_MS = round(CAL_R["t"] - CAL_E["t"] - COUNT_MS, 1)
# 本輪校準值:沒遇到中斷的 delay 每圈 6 條、固定 3 條遊戲選擇子指令(續一百六十一),圈數 = (ms × C + 500) // 1000
_iE = {r["seq"]: r for r in REC if r["eip"] == DELAY and r["k"] == "E"}
_iR = {r["seq"]: r for r in REC if r["eip"] == DELAY and r["k"] == "R"}
C_LO, C_HI, CLEAN = 0, 10 ** 9, collections.Counter()
for q, e in _iE.items():
    if q not in _iR:
        continue
    j = bisect.bisect_right(ISR_T, e["t"])
    if j < len(ISR_T) and ISR_T[j] < _iR[q]["t"]:
        continue
    di = _iR[q]["i"] - e["i"]
    assert (di - 3) % 6 == 0, di
    it, ms = (di - 3) // 6, int(e["s"].split(",")[0], 16)
    CLEAN[(ms, it)] += 1
    C_LO = max(C_LO, math.ceil((1000 * it - 500) / ms))
    C_HI = min(C_HI, math.ceil((1000 * (it + 1) - 500) / ms) - 1)
CAL_S160 = S161["delay_decomposition"]["calibration"]
NO_ISR = S161["delay_decomposition"]["classes"]["no_isr"]["iter_per_s"]
RATE_CAL = round(CAL_S160 / (COUNT_MS / 1000), 1)
SPLIT = {"second_len": round(COUNT_MS / 1000, 4), "rate_ratio": round(RATE_CAL / NO_ISR, 4),
         "product": round(COUNT_MS / 1000 * RATE_CAL / NO_ISR, 3)}

DT_WIN = _dt[W0:]
S158_TICK = [S158["bios_tick_interval"]["runs"][k]["mean_ms_per_tick"] for k in ("lc157c", "lc157d", "lc157e")]
R = {"period_ms": round(P, 6), "bios_tick_ms": round(TICK_MS, 4), "first_mdi_ms": round(MDI0, 3),
     "first_dig_ms": round(DIG0, 3), "window_ms": [round(T0, 3), round(T1, 3)], "fraction": round(LOST / N_SLOTS, 4),
     "cs_per_tick": round(CS_PER_TICK, 4)}
P2_SHARE = round(sum(1 for x in DT_WIN if abs(x - P) <= 0.05) / len(DT_WIN), 4)

# ================= 釘值 =================
assert COUNTS == {"isr": 5505, "reentry": 78, "dig": 5420, "mdi": 3255, "ail_100hz": 0, "delay": 584}, COUNTS
assert PRE == {"bios_18hz": [54.925, 55.346, 43.632], "mdi_120hz": [8.366, 8.333, 8.334, 7.208]}, PRE
assert (round(T0, 3), round(T1, 3), round(DIG0, 3), round(MDI0, 3)) == (3538.26, 31028.675, 3538.338, 3514.41)
assert (len(WIN), N_SLOTS, len(EMPTY), len(DOUBLE), PHI, ON_GRID) == (5498, 5499, 3, 2, 0.0, 5390),     (len(WIN), N_SLOTS, len(EMPTY), len(DOUBLE), PHI, ON_GRID)
assert len(WIN) - len(DOUBLE) + len(EMPTY) == N_SLOTS                          # 每格最多兩筆
assert EMPTY_AT == [[9078.344, "intro_key_exit"], [9173.345, "intro_key_exit"], [19948.508, "new_game"]], EMPTY_AT
assert (RE_LATE, len(LATE_ALL), len(LATE_NONRE)) == (71, 92, 21), (RE_LATE, len(LATE_ALL), len(LATE_NONRE))
assert RE_PHASE == {"blink": 5, "intro_key_exit": 14, "new_game": 56, "title_seq": 3}, RE_PHASE
assert dict(RUNNING) == {"DIG": 62, "MDI": 15, "DIG+MDI": 1} and LONG == {"DIG": 61, "MDI": 15}, (RUNNING, LONG)
assert (LOST, round(LOST / N_SLOTS, 4), TICK_AVG) == (81, 0.0147, 55.75), (LOST, TICK_AVG)
assert (NORMAL_DIG, NORMAL_MDI) == (COUNTS["dig"], 5423) and round(COUNTS["mdi"] / NORMAL_MDI, 4) == 0.6002
assert (EDX & 0xFFFF, DH, DL, TICKS_IN_SECOND, COUNT_MS, WAIT_MS) == (0x3705, 55, 5, {19}, 1043.58, 470.8)
assert (C_LO, C_HI, dict(CLEAN)) == (8750, 9249, {(2, 18): 243}) and C_LO <= CAL_S160 <= C_HI
assert (CAL_S160, NO_ISR, RATE_CAL) == (9057, 8767.8, 8678.8)
assert SPLIT == {"second_len": 1.0436, "rate_ratio": 0.9898, "product": 1.033}     and SPLIT["product"] == S161["delay_decomposition"]["calibration_over_no_isr"], SPLIT
assert P2_SHARE == 0.9169, P2_SHARE
assert R == {"period_ms": 5.000075, "bios_tick_ms": 54.9254, "first_mdi_ms": 3514.41, "first_dig_ms": 3538.338,
             "window_ms": [3538.26, 31028.675], "fraction": 0.0147, "cs_per_tick": 5.4925}, R
assert S158_TICK == [56.437, 56.365, 56.214] and min(S158_TICK) > TICK_AVG, S158_TICK
assert EVENTS == [(1781.374, "calibration"), (3295.825, "main_call_AIL_startup"), (3657.061, "title_seq"),
                  (7987.464, "intro_key_exit"), (9967.982, "menu_kbd_flush"), (10753.603, "confirm"),
                  (10754.207, "blink"), (11515.742, "fade"), (11952.569, "clear"), (12402.422, "new_game")], EVENTS

# ================= 預測對照 =================
def verdict(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# 判定由資料算(判準照 pred163_3b.txt 原文),不寫死結果
_mdi_ratio = COUNTS["mdi"] / NORMAL_MDI
_cb = [COUNTS["dig"] == NORMAL_DIG, abs(_mdi_ratio - 0.6) < 0.01, COUNTS["ail_100hz"] > 0]
PRED_RESULT = {
    "P1": [verdict(COUNTS["isr"] > 0), f"0x3ea8e 在 cs 0170 有 {COUNTS['isr']} 筆 E 記錄"],
    "P2": [verdict(P2_SHARE >= 0.9),
           f"200 Hz 期相鄰兩次進入的間隔 {P2_SHARE:.1%} 在 {P:.4f} ± 0.05 ms 內;相位 ±0.1 ms 內 {ON_GRID} / {len(WIN)}"],
    "P3_main": [verdict(len(RE_T) == 0 and len(EMPTY) > 0),
                f"主要假說是 D = 0、全靠合併;實測重入 D = {len(RE_T)}、合併 M = {len(EMPTY)}"],
    "P3_alt": [verdict(len(RE_T) > 0 and RE_PHASE.get("blink", 0) > len(RE_T) / 2),
               f"替代假說「D > 0、集中在確認音效」:D > 0,但 {RE_PHASE['new_game']} 次在新遊戲開場、"
               f"{RE_PHASE['intro_key_exit']} 次在片頭,確認音效 / 閃爍期間只有 {RE_PHASE['blink']} 次"],
    "P4": [verdict(CAL_R["t"] < AIL_T < ISR_T[0]),
           f"校準在 {CAL_E['t']:.3f} .. {CAL_R['t']:.3f} ms,早於 main 呼叫 AIL_startup({AIL_T:.3f})與第一次 0x3ea8e"],
    "callbacks": ["PASS" if all(_cb) else "PARTIAL" if any(_cb) else "FAIL",
                  f"0x404c0 = 正常進入數 {NORMAL_DIG}(相等);0x43270 / 正常進入 = {_mdi_ratio:.4f}(預測 0.6);"
                  f"0x37c30 預測約 0.5 倍,實測 {COUNTS['ail_100hz']} 次"],
}
assert [v[0] for v in PRED_RESULT.values()] == ["PASS", "PASS", "FAIL", "FAIL", "PASS", "PARTIAL"], PRED_RESULT

OUTD = {
    "generator": rel(GEN_DIR / "ev_s163.py"),
    "exe_md5": MD5,
    "approval": "使用者 2026-10-29「還沒做的兩件 請依照你的建議自動進行處理」;實機一次(lc163a),不重跑",
    "prediction_file": rel(PRED),
    "run": {"instance": "lc163a", "calllog": rel(RAW / "lc163a_CALLLOG.TXT"), "calllog_md5": CALLLOG_MD5,
            "lines": int(META[2]), "header": HDR, "entries_native": [hex(a) for a in NATIVE],
            "harness": HARNESS, "events_ms": EVENTS},
    "timeline": {"pit_divisor": DIVISOR, "period_ms": R["period_ms"], "bios_tick_ms": R["bios_tick_ms"],
                 "pre_dig_intervals_ms": PRE, "first_mdi_ms": R["first_mdi_ms"], "first_dig_ms": R["first_dig_ms"],
                 "window_ms": R["window_ms"], "isr_entries": len(WIN), "grid_slots": N_SLOTS,
                 "phase_mode_ms": PHI, "within_0_1ms": ON_GRID, "interval_within_0_05ms": P2_SHARE,
                 "empty_slots_merged": EMPTY_AT, "double_slots": len(DOUBLE)},
    "reentry": {"count": len(RE_T), "late_gt_0_3ms": RE_LATE, "on_time": len(RE_T) - RE_LATE, "by_phase": RE_PHASE,
                "callback_running": dict(RUNNING), "callback_spans_gt_period": LONG,
                "late_entries_all": len(LATE_ALL), "late_not_reentry": len(LATE_NONRE)},
    "loss": {"reentry": len(RE_T), "merged": len(EMPTY), "total": LOST, "slots": N_SLOTS,
             "fraction": R["fraction"], "bios_tick_avg_ms": TICK_AVG,
             "s158_measured_ms": S158_TICK},
    "callbacks": {"dig_calls": COUNTS["dig"], "normal_entries_since_dig": NORMAL_DIG, "mdi_calls": COUNTS["mdi"],
                  "normal_entries_since_mdi": NORMAL_MDI, "ail_internal_0x37c30_calls": COUNTS["ail_100hz"]},
    "calibration": {"function": hex(CAL_FN), "result_slot": "0x541b0", "return_edx": hex(EDX), "dos_second": DH,
                    "dos_hundredths": DL, "cs_per_tick": R["cs_per_tick"], "ticks_in_counted_second": max(TICKS_IN_SECOND),
                    "counted_second_ms": COUNT_MS, "wait_phase_ms": WAIT_MS,
                    "this_run_calibration_bounds": [C_LO, C_HI], "bound_from": {f"delay({m}) = {i} 圈": n for (m, i), n in CLEAN.items()},
                    "s160_calibration": CAL_S160, "s161_no_isr_iter_per_s": NO_ISR, "calibration_iter_per_s": RATE_CAL,
                    "s161_ratio_split": SPLIT},
    "predictions": PRED_RESULT,
    "conclusion": {
        "3b": f"200 Hz 期 {N_SLOTS} 格裡,計時器中斷沒算進累加器的有 {LOST} 次({LOST / N_SLOTS:.2%}):"
              f"重入 0x3ebad {len(RE_T)} 次、合併 {len(EMPTY)} 次。重入當下多半是 DIG 服務 0x404c0 還沒返回({RUNNING['DIG']} 次),"
              f"其次 MDI 0x43270({RUNNING['MDI']} 次);{RE_LATE} 次重入的中斷晚到 1 .. 4 ms(回呼裡有關中斷的區間)。"
              f"這段的 BIOS tick 平均應為 {TICK_AVG} ms(續一百五十八在戰場量到 56.2 .. 56.4 ms,負載不同)。",
        "calibration": f"0x3dfef 數的是 DOS 時間(int 21h AH=2Ch)的一秒;DOSBox-X 由 BIOS tick 換算時間,返回時 DL = {DL} "
                       f"→ 這一秒正好 {max(TICKS_IN_SECOND)} 個 tick({COUNT_MS} ms)。續一百六十一的 1.033 = {SPLIT['second_len']}(19 tick)"
                       f" × {SPLIT['rate_ratio']}(校準期間每圈比遊戲中沒遇到中斷的 delay 慢約 1%,原因沒查)。",
    },
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, "lost", LOST, "of", N_SLOTS, "reentry", len(RE_T), "merged", len(EMPTY), "tick_avg", TICK_AVG)
