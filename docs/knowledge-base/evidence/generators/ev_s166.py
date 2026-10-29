"""續一百六十六證據:evidence/battle_interrupt_loss_s166_20261029.json(戰場時段的計時器掉中斷比例;實機一次 lc166a)。

使用者 2026-10-29「核准戰場跑實機的部分」(續一百六十三 / 一百六十四 / 一百六十五「仍留」的戰場掉中斷比例)。
DOSBox-X 呼叫紀錄 lc166a:instance 的 FD2.SAV 複本章節設 1 → 標題讀檔 → 城鎮 → 「要進入戰場嗎?」YES → 第 1 章戰場地圖
(開場劇情對話)→ 主機時間閒置 30 秒 → teardown。不改記憶體、不下斷點。預測 drivers_s166/pred166_battle.txt(實機前寫)。
(A) 原始紀錄:指紋、入口 20 個(lc163a 的 19 個 + redraw 0x11cac 當戰場時段標記)。
(B) 方法同續一百六十三:DIG 第一次被服務起的 200 Hz 期,5 ms 格點對齊;沒算進累加器 = 重入(0x3ebad)+ 空格(合併)。
    用同一支函式重算 lc163a,必須得到續一百六十三的 5499 格、重入 78、合併 3(方法對照)。
    以第一次 redraw 所在的格把 lc166a 切成「戰場前」(標題、讀檔、城鎮)與「戰場」。
(C) 重入分型:續一百六十四 DIG 型(到自己 A 93 / 94)、MDI 型(到下一筆 DIG 62)、續一百六十五同格再叫 MDI(57)。
(D) 預測 P1 .. P4 逐項判定。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)

OUT = out_path("battle_interrupt_loss_s166_20261029.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
RAW = ROOT / ".wsl_build" / "lc166_live"
RAW163 = ROOT / ".wsl_build" / "lc163_live"
PRED_FILE = GEN_DIR / "drivers_s166" / "pred166_battle.txt"
DELTA = 0x19C000
S161 = json.loads((EVIDENCE / "timer_base_and_delay_slowdown_s161_20261028.json").read_text(encoding="utf-8"))
S163 = json.loads((EVIDENCE / "timer_interrupt_loss_s163_20261029.json").read_text(encoding="utf-8"))
S164 = json.loads((EVIDENCE / "interrupt_off_sections_s164_20261029.json").read_text(encoding="utf-8"))
S165 = json.loads((EVIDENCE / "reentry_catchup_mdi_driver_s165_20261029.json").read_text(encoding="utf-8"))
ISR, REENTRY, DIG, MDI, REDRAW = 0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x11CAC
EPI, EPI_CHAIN = 0x3EB9D, 0x3EB69
P = S161["timer_channels"]["pit_divisor"] / 1193182 * 1000
BIOS_MS = 54.925


def load(path) -> list[dict]:
    """E / R / A 記錄(最後一筆被 teardown 截斷、沒有 t 的不算)。"""
    out = []
    for ln in path.read_text(encoding="ascii").splitlines()[1:]:
        p = ln.split()
        if not p or p[0] not in ("E", "R", "A"):
            continue
        kv = dict(x.split("=", 1) for x in p if "=" in x)
        if "t" not in kv:
            continue
        r = {"k": p[0], "seq": int(p[1]), "eip": int(p[2], 16) - DELTA, "i": int(kv["i"]), "n": int(kv["n"]), "t": float(kv["t"])}
        if p[0] == "A":
            r["at"] = int(p[3], 16) - DELTA
        out.append(r)
    return out


# ================= (A) 原始紀錄 =================
META = (RAW / "lc166a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG_MD5 = "4a838626822473b4352591fd16c642cd"
assert META[0].split() == [CALLLOG_MD5, "CALLLOG.TXT"] and META[1].split() == [MD5, "FD2.EXE"], META
_raw = (RAW / "lc166a_CALLLOG.TXT").read_bytes()
assert hashlib.md5(_raw).hexdigest() == CALLLOG_MD5 and _raw.count(b"\n") == int(META[2]) == 117066
assert META[3] == "H fd2calllog 1 cs=0170 entries=20 cap=100000000 dump=0 lo=001adcac hi=001df271 icount=1", META[3]
ENTRIES = sorted(int(x, 16) - DELTA for x in META[4].split())
_e163 = sorted(int(x, 16) - DELTA for x in (RAW163 / "lc163a_meta.txt").read_text(encoding="utf-8").splitlines()[4].split())
assert sorted(set(ENTRIES) - set(_e163)) == [REDRAW] and set(_e163) <= set(ENTRIES)
REC = load(RAW / "lc166a_CALLLOG.TXT")
_lines = sum(1 for ln in _raw.decode("ascii").splitlines() if ln[:2] in ("E ", "R ", "A "))
assert _lines == len(REC) + 1, (_lines, len(REC))                                  # 只少截斷的那一筆
RUN = json.loads((RAW / "lc166a_run.json").read_text(encoding="utf-8"))
assert RUN["ok"] and RUN["idle_s"] == 30.0 and [a[0] for a in RUN["assertions"]] == ["instance_up", "patch_chapter", "poll_title"]
assert all(a[1] for a in RUN["assertions"]) and "chapter byte -> 1" in RUN["assertions"][1][2]
assert list(RUN["shots"])[-4:] == ["r05_Return", "r06_Return", "r07_Return", "r08_Return"]


# ================= (B) 掉中斷:格點 =================
def grid(rec: list[dict], cut: float | None) -> dict:
    """續一百六十三的格點法;cut 給時間時,另以 cut 所在的格切成前後兩段。"""
    isr = [r["t"] for r in rec if r["k"] == "E" and r["eip"] == ISR]
    dig0 = next(r["t"] for r in rec if r["k"] == "E" and r["eip"] == DIG)
    re_t = [r["t"] for r in rec if r["k"] == "E" and r["eip"] == REENTRY]
    w0 = max(i for i, t in enumerate(isr) if t <= dig0)
    win = isr[w0:]
    ph = collections.Counter(round((t - win[0] + P / 2) % P - P / 2, 2) for t in win)
    phi = ph.most_common(1)[0][0]
    g0 = win[0] + phi - P
    slot: dict[int, list[float]] = collections.defaultdict(list)
    for t in win:
        slot[int((t - g0 + 0.2) // P)].append(t)
    lo, hi = min(slot), max(slot)
    assert re_t[0] > win[0]
    re_k = [int((t - g0 + 0.2) // P) for t in re_t]
    kc = hi + 1 if cut is None else int((cut - g0 + 0.2) // P)
    segs = {}
    for nm, a, b in (("all", lo, hi), ("pre", lo, kc - 1), ("post", kc, hi)):
        if a > b:
            continue
        empty = [k for k in range(a, b + 1) if k not in slot]
        nre = sum(1 for k in re_k if a <= k <= b)
        n = b - a + 1
        lost = nre + len(empty)
        segs[nm] = {"t_ms": [round(g0 + a * P, 3), round(g0 + (b + 1) * P, 3)], "slots": n, "reentry": nre, "merged": len(empty),
                    "lost": lost, "fraction": round(lost / n, 5), "bios_tick_avg_ms": round(BIOS_MS / (1 - lost / n), 3),
                    "double": sum(1 for k in range(a, b + 1) if len(slot.get(k, [])) > 1)}
    return {"phase_mode_ms": phi, "within_0_1ms": sum(v for k, v in ph.items() if abs(k - phi) <= 0.1),
            "isr_entries": len(win), "segments": segs}


# 方法對照:lc163a 必須重現續一百六十三
G163 = grid(load(RAW163 / "lc163a_CALLLOG.TXT"), None)["segments"]["all"]
_l = S163["loss"]
assert (G163["slots"], G163["reentry"], G163["merged"], G163["lost"]) == (_l["slots"], _l["reentry"], _l["merged"], _l["total"]), G163
REDRAW_T = [r["t"] for r in REC if r["k"] == "E" and r["eip"] == REDRAW]
G = grid(REC, REDRAW_T[0])
BAT, PRE = G["segments"]["post"], G["segments"]["pre"]
assert (G["phase_mode_ms"], G["within_0_1ms"], G["isr_entries"]) == (0.0, 21982, 22144), G
assert G163["double"] == S163["timeline"]["double_slots"] == 2, G163
assert {k: v["double"] for k, v in G["segments"].items()} == {"all": 1, "pre": 1, "post": 0}, G
assert BAT["slots"] + PRE["slots"] == G["segments"]["all"]["slots"] and BAT["lost"] + PRE["lost"] == G["segments"]["all"]["lost"]
assert {k: (v["slots"], v["reentry"], v["merged"], v["fraction"], v["bios_tick_avg_ms"]) for k, v in G["segments"].items()} == {
    "all": (22149, 123, 6, 0.00582, 55.247), "pre": (7789, 47, 2, 0.00629, 55.273), "post": (14360, 76, 4, 0.00557, 55.233)}, G
assert BAT["t_ms"] == [42475.587, 114276.67] and len(REDRAW_T) == 71, (BAT["t_ms"], len(REDRAW_T))
# 戰場時段裡 redraw 只在開頭 5 秒(地圖畫面建立);之後是對話框等 Return,沒再重繪
REDRAW_SPAN = [round(REDRAW_T[0], 3), round(REDRAW_T[-1], 3)]
assert REDRAW_SPAN == [42476.106, 47524.028] and REDRAW_SPAN[1] - REDRAW_SPAN[0] < 6000, REDRAW_SPAN

# ================= (C) 重入分型 =================
_pd = S164["interrupt_off"]["predicted_di"]
PRED_DI = {"DIG": {EPI: _pd["dig_restore"][hex(EPI)], EPI_CHAIN: _pd["dig_restore"][hex(EPI_CHAIN)]},
           "MDI": _pd["mdi_driver_return"], "MDI_AGAIN": int(S165["reentry_3665"]["di_reentry_to_next"])}
assert PRED_DI == {"DIG": {EPI: 93, EPI_CHAIN: 94}, "MDI": 62, "MDI_AGAIN": 57}, PRED_DI
TYPES = collections.Counter()
OTHER = []
for k, r in enumerate(REC):
    if not (r["k"] == "E" and r["eip"] == REENTRY):
        continue
    q = REC[k + 1]
    d = q["i"] - r["i"]
    if q["k"] == "A" and q["eip"] == REENTRY and d == PRED_DI["DIG"].get(q["at"]):
        c = "DIG"
    elif q["k"] == "E" and q["eip"] == DIG and d == PRED_DI["MDI"]:
        c = "MDI"
    elif q["k"] == "E" and q["eip"] == MDI and d == PRED_DI["MDI_AGAIN"]:
        c = "MDI_AGAIN"
    else:
        c = "other"
        OTHER.append({"t": round(r["t"], 3), "next": f"{q['k']} {q['eip']:#x}", "di": d})
    TYPES[(c, "post" if r["t"] >= BAT["t_ms"][0] - 0.2 else "pre")] += 1
TYPE_TABLE = {seg: {c: TYPES[(c, seg)] for c in ("DIG", "MDI", "MDI_AGAIN", "other")} for seg in ("pre", "post")}
assert OTHER == [] and sum(TYPE_TABLE["post"].values()) == BAT["reentry"] and sum(TYPE_TABLE["pre"].values()) == PRE["reentry"]
assert TYPE_TABLE == {"pre": {"DIG": 40, "MDI": 5, "MDI_AGAIN": 2, "other": 0},
                      "post": {"DIG": 48, "MDI": 28, "MDI_AGAIN": 0, "other": 0}}, TYPE_TABLE
# DIG 長服務(遊戲指令 > 10000,約 3.5 ms 整段關中斷)每段的次數與占比
_open, LONG_DIG = {}, collections.Counter()
_dig_n = collections.Counter()
_dig_di: list[int] = []
for r in REC:
    if r["eip"] != DIG:
        continue
    if r["k"] == "E":
        _open[r["seq"]] = r
    elif r["seq"] in _open:
        e = _open.pop(r["seq"])
        seg = "post" if e["t"] >= BAT["t_ms"][0] else "pre"
        if e["t"] >= PRE["t_ms"][0] - 0.2:
            _dig_n[seg] += 1
            _dig_di.append(r["i"] - e["i"])
            LONG_DIG[seg] += r["i"] - e["i"] > 10000
assert all(d < 100 or d > 15000 for d in _dig_di) and min(_dig_di) == 50, sorted(set(d for d in _dig_di if 100 <= d <= 15000))[:5]   # 兩群,門檻落在中間
LONG = {s: {"dig_calls": _dig_n[s], "long": LONG_DIG[s], "share": round(LONG_DIG[s] / _dig_n[s], 4)} for s in ("pre", "post")}
assert LONG == {"pre": {"dig_calls": 7741, "long": 65, "share": 0.0084}, "post": {"dig_calls": 14279, "long": 60, "share": 0.0042}}, LONG

# ================= (D) 預測 =================
_pred = PRED_FILE.read_text(encoding="utf-8")
PRED_MD5 = hashlib.md5(PRED_FILE.read_bytes()).hexdigest()
assert "P3 掉的比例在 1% .. 3% 之間" in _pred and "落在 55.5 .. 56.5 ms" in _pred and "重入 ≥ 90%" in _pred
REENTRY_SHARE = round(BAT["reentry"] / BAT["lost"], 4)
VERDICT = {"P1_reentry_share_ge_0_9": "PASS" if REENTRY_SHARE >= 0.9 else "FAIL",
           "P2_all_classified": "PASS" if TYPE_TABLE["post"]["other"] == 0 else "FAIL",
           "P3_fraction_1_to_3pct": "PASS" if 0.01 <= BAT["fraction"] <= 0.03 else "FAIL",
           "P3_main_1_to_2pct": "PASS" if 0.01 <= BAT["fraction"] <= 0.02 else "FAIL",
           "P4_tick_55_5_to_56_5": "PASS" if 55.5 <= BAT["bios_tick_avg_ms"] <= 56.5 else "FAIL"}
assert VERDICT == {"P1_reentry_share_ge_0_9": "PASS", "P2_all_classified": "PASS", "P3_fraction_1_to_3pct": "FAIL",
                   "P3_main_1_to_2pct": "FAIL", "P4_tick_55_5_to_56_5": "FAIL"}, VERDICT
assert REENTRY_SHARE == 0.95

S163_FRAC = _l["fraction"]
CONC = {
    "battle": f"第 1 章戰場地圖(開場對話期間)200 Hz 的 {BAT['slots']} 格裡,沒算進累加器 {BAT['lost']} 次({BAT['fraction']:.3%}):"
              f"重入 {BAT['reentry']}、合併 {BAT['merged']};換算 BIOS tick 平均 {BAT['bios_tick_avg_ms']} ms。"
              f"重入全部歸得進兩型(DIG {TYPE_TABLE['post']['DIG']}、MDI {TYPE_TABLE['post']['MDI']})。",
    "compare": f"同一次的戰場前(標題、讀檔、城鎮){PRE['fraction']:.3%};續一百六十三新遊戲開場 {S163_FRAC:.2%}。"
               f"DIG 長服務(> 10000 條)占比戰場 {LONG['post']['share']:.2%}、戰場前 {LONG['pre']['share']:.2%}。"
               f"續一百五十八戰場量到的 56.21 .. 56.44 ms 是敵方法術動畫期間,和這次的對話期間負載不同,不能直接比。",
    "predictions": f"P1 PASS(重入占 {REENTRY_SHARE:.0%})、P2 PASS(未歸類 0)、P3 FAIL(實測 {BAT['fraction']:.2%} < 1%)、P4 FAIL({BAT['bios_tick_avg_ms']} ms < 55.5)。",
}
for _part, _key in (("14360 格裡,沒算進累加器 80 次(0.557%)", "battle"), ("重入 76、合併 4", "battle"), ("55.233 ms", "battle"),
                     ("DIG 48、MDI 28", "battle"), ("戰場前(標題、讀檔、城鎮)0.629%", "compare"), ("新遊戲開場 1.47%", "compare"),
                     ("戰場 0.42%、戰場前 0.84%", "compare"), ("重入占 95%", "predictions"), ("實測 0.56% < 1%", "predictions")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s166.py"),
    "exe_md5": MD5,
    "approval": "使用者 2026-10-29「核准戰場跑實機的部分」;實機一次 lc166a,不改記憶體、不下斷點",
    "prediction_file": {"path": rel(PRED_FILE), "md5": PRED_MD5},
    "run": {"calllog": rel(RAW / "lc166a_CALLLOG.TXT"), "calllog_md5": CALLLOG_MD5, "lines": int(META[2]), "records": len(REC),
            "entries": [hex(a) for a in ENTRIES], "route": "patch_chapter 1 → 讀檔 → 城鎮 → 要進入戰場嗎 YES → 戰場開場對話 → 閒置 30 s",
            "redraw_span_ms": REDRAW_SPAN, "redraw_calls": len(REDRAW_T)},
    "method_check_lc163a": G163,
    "grid": G,
    "reentry_types": TYPE_TABLE,
    "predicted_di": {"DIG": {hex(k): v for k, v in PRED_DI["DIG"].items()}, "MDI": PRED_DI["MDI"], "MDI_AGAIN": PRED_DI["MDI_AGAIN"]},
    "long_dig_services": LONG,
    "predictions": VERDICT,
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, BAT, TYPE_TABLE["post"], VERDICT)
