"""續一百六十七證據:evidence/battle_turn_interrupt_loss_s167_20261029.json(戰場玩家回合 / 換邊 / 敵方回合的計時器掉中斷比例;實機 lc167a)。

使用者 2026-10-29「永遠核准你進行實機」(續一百六十六「仍留」的玩家回合與敵方回合)。
DOSBox-X 呼叫紀錄 lc167a:同 lc166a 進第 1 章戰場 → ensure_battle_hud 清開場對話 → 玩家回合閒置 30 秒(P)→
結束回合第一次沒成功(見 (A))→ 逐鍵截圖改走:Escape、Return 關狀態畫面、Down、Return 開指令環、Down、Return(確認框)、
Return YES → 敵方回合 → 第二個玩家回合閒置 25 秒(P2)→ teardown。不改記憶體、不下斷點、不進除錯器。
預測 drivers_s167/pred167_turns.txt(實機前寫)。
(A) 原始紀錄:指紋、入口 26 個(lc166a 的 20 個 + 6 個回合標記)、標記的巢狀順序、時段邊界、模擬器 / 主機時間比。
(B) 方法同續一百六十三 / 一百六十六:5 ms 格點,沒算進累加器 = 重入(0x3ebad)+ 空格(合併);先重算 lc163a 對照。
(C) 重入分型(續一百六十四 / 一百六十五的預測指令數)、MDI 型每千格次數、DIG 長服務數。
(D) 預測 P1 .. P6 逐項判定。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)

OUT = out_path("battle_turn_interrupt_loss_s167_20261029.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
RAW = ROOT / ".wsl_build" / "lc167_live"
RAW163 = ROOT / ".wsl_build" / "lc163_live"
RAW166 = ROOT / ".wsl_build" / "lc166_live"
PRED_FILE = GEN_DIR / "drivers_s167" / "pred167_turns.txt"
DELTA = 0x19C000
S161 = json.loads((EVIDENCE / "timer_base_and_delay_slowdown_s161_20261028.json").read_text(encoding="utf-8"))
S163 = json.loads((EVIDENCE / "timer_interrupt_loss_s163_20261029.json").read_text(encoding="utf-8"))
S164 = json.loads((EVIDENCE / "interrupt_off_sections_s164_20261029.json").read_text(encoding="utf-8"))
S165 = json.loads((EVIDENCE / "reentry_catchup_mdi_driver_s165_20261029.json").read_text(encoding="utf-8"))
S166 = json.loads((EVIDENCE / "battle_interrupt_loss_s166_20261029.json").read_text(encoding="utf-8"))
ISR, REENTRY, DIG, MDI = 0x3EA8E, 0x3EBAD, 0x404C0, 0x43270
EPI, EPI_CHAIN = 0x3EB9D, 0x3EB69
LOOP, CHOOSE, RING, ADVANCE, FRIEND, ENEMY = 0x117E7, 0x14EF0, 0x16F55, 0x1A30B, 0x1D80B, 0x1D8BA
MARKERS = [LOOP, CHOOSE, RING, ADVANCE, FRIEND, ENEMY]
P = S161["timer_channels"]["pit_divisor"] / 1193182 * 1000
BIOS_MS = 54.925
LONG_I = 10000                         # DIG 長服務門檻(遊戲指令數;兩群 50 .. 57 與 > 15000 之間)
LEAD_MS, TAIL_MS = 1000, 500           # 閒置窗:開頭扣 1 秒、結尾扣 0.5 秒(預測檔寫的,(D) 核對原文)


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
        r = {"k": p[0], "seq": int(p[1]), "eip": int(p[2], 16) - DELTA, "i": int(kv["i"]), "t": float(kv["t"])}
        if p[0] == "A":
            r["at"] = int(p[3], 16) - DELTA
        out.append(r)
    return out


# ================= (A) 原始紀錄 =================
META = (RAW / "lc167a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG_MD5 = "ac9401da607102caa569be467c178b92"
assert META[0].split() == [CALLLOG_MD5, "CALLLOG.TXT"] and META[1].split() == [MD5, "FD2.EXE"], META
_raw = (RAW / "lc167a_CALLLOG.TXT").read_bytes()
assert hashlib.md5(_raw).hexdigest() == CALLLOG_MD5 and _raw.count(b"\n") == int(META[2]) == 631212
assert META[3] == "H fd2calllog 1 cs=0170 entries=26 cap=100000000 dump=0 lo=001ad7e7 hi=001df271 icount=1", META[3]
ENTRIES = sorted(int(x, 16) - DELTA for x in META[4].split())
_e166 = sorted(int(x, 16) - DELTA for x in (RAW166 / "lc166a_meta.txt").read_text(encoding="utf-8").splitlines()[4].split())
assert sorted(set(ENTRIES) - set(_e166)) == sorted(MARKERS) and set(_e166) <= set(ENTRIES) and len(ENTRIES) == 26
REC = load(RAW / "lc167a_CALLLOG.TXT")
_lines = sum(1 for ln in _raw.decode("ascii").splitlines() if ln[:2] in ("E ", "R ", "A "))
assert _lines == len(REC) + 1, (_lines, len(REC))                                  # 只少截斷的那一筆
RUN = json.loads((RAW / "lc167a_run.json").read_text(encoding="utf-8"))
FIN = json.loads((RAW / "lc167a_finish.json").read_text(encoding="utf-8"))
STEPS = [json.loads(ln) for ln in (RAW / "lc167a_steps.jsonl").read_text(encoding="utf-8").splitlines()]
assert RUN["runner"]["ok"] and [a[0] for a in RUN["runner"]["assertions"]] == ["instance_up", "patch_chapter", "poll_title"]
assert all(a[1] for a in RUN["runner"]["assertions"]) and "chapter byte -> 1" in RUN["runner"]["assertions"][1][2]
assert RUN["hud"] == {"ok": True, "clears": 33} and RUN["empty_tile"] is True
# 第一次結束回合:240 秒沒等到 R 0x1d8ba(停在索爾的狀態畫面),於是同一個 instance 逐鍵截圖改走
assert RUN["ok"] is False and RUN["error"] == "enemy_phase_timeout" and RUN["enemy_wait"] == {"grep": "0", "shots": 46}
assert [(s["label"], s["key"]) for s in STEPS] == [("esc", "Escape"), ("close", "Return"), ("ring", "Down"), ("ring", "Return"),
                                                   ("end", "Down"), ("end", "Return")], STEPS
assert FIN["ok"] is True and FIN["enemy_wait"]["grep"] == "1"

# 標記:E / R 次數與巢狀
MK = collections.Counter((r["k"], r["eip"]) for r in REC if r["eip"] in MARKERS)
assert {hex(e): (MK[("E", e)], MK[("R", e)]) for e in MARKERS} == {
    hex(LOOP): (5, 4), hex(CHOOSE): (10, 10), hex(RING): (1, 1), hex(ADVANCE): (1, 1), hex(FRIEND): (1, 1), hex(ENEMY): (1, 1)}, MK


def one(k: str, eip: int) -> dict:
    (r,) = [r for r in REC if r["k"] == k and r["eip"] == eip]
    return r


T = {f"{k}_{n}": one(k, e)["t"] for n, e in (("ring", RING), ("adv", ADVANCE), ("friend", FRIEND), ("enemy", ENEMY)) for k in "ER"}
# 結束回合 → 戰鬥階段推進 → 友軍回合 → 敵方回合,全部在指令環的呼叫裡面
assert T["E_ring"] < T["E_adv"] < T["E_friend"] < T["R_friend"] < T["E_enemy"] < T["R_enemy"] < T["R_adv"] <= T["R_ring"], T
_choose = [r["t"] for r in REC if r["k"] == "E" and r["eip"] == CHOOSE]
assert all(T["E_enemy"] < t < T["R_enemy"] for t in _choose)                        # ai_choose_action 10 次都在敵方回合裡
# 模擬器時間對主機時間(閒置窗由尾端讀數決定,要確認兩者同速)
(hPa, Pa), (hPb, Pb) = RUN["marks"]["P_a"], RUN["marks"]["P_b"]
(hPc, Pc), (hPd, Pd) = FIN["marks"]["P2_c"], FIN["marks"]["P2_d"]
SPEED = {"P": round((Pb - Pa) / 1000 / (hPb - hPa), 4), "P2": round((Pd - Pc) / 1000 / (hPd - hPc), 4)}
assert all(0.98 <= v <= 1.02 for v in SPEED.values()), SPEED
WIN = {"P": (Pa + LEAD_MS, Pb - TAIL_MS), "S": (T["E_ring"], T["E_enemy"]), "EN": (T["E_enemy"], T["R_enemy"]), "P2": (Pc + LEAD_MS, Pd - TAIL_MS),
       "S_ring": (T["E_ring"], T["E_adv"]), "S_adv": (T["E_adv"], T["E_enemy"]), "S_friend": (T["E_friend"], T["R_friend"]),
       "diag": (Pb, T["E_ring"])}
_loop = [(r["k"], r["t"]) for r in REC if r["eip"] == LOOP]
# P:主迴圈 E 在前、P 裡沒有任何標記
assert _loop[0][0] == "E" and _loop[0][1] < WIN["P"][0] and _loop[1][1] > WIN["P"][1], _loop[:2]
assert not [r for r in REC if r["eip"] in MARKERS and WIN["P"][0] <= r["t"] <= WIN["P"][1]]
# P2(預測照實機前寫的讀法)的開頭 2.9 秒還在換邊:推進 / 指令環 R、主迴圈 R 再 E 都落在 P2 裡。
# 另算 P2_loop = 主迴圈最後一次 E(第二個玩家回合開始)→ P2 結尾,只當參考,不拿來判定預測。
_in_p2 = [(r["k"], r["eip"]) for r in REC if r["eip"] in MARKERS and WIN["P2"][0] <= r["t"] <= WIN["P2"][1]]
assert _in_p2 == [("R", ADVANCE), ("R", RING), ("R", LOOP), ("E", LOOP)], _in_p2
assert _loop[-1][0] == "E" and _loop[-1][1] - T["R_ring"] < 0.01 and WIN["P2"][0] < _loop[-1][1] < WIN["P2"][1]
WIN["P2_loop"] = (_loop[-1][1], WIN["P2"][1])
WINDOWS = {nm: [round(a, 3), round(b, 3)] for nm, (a, b) in WIN.items()}
assert WINDOWS == {"P": [89737.116, 118322.657], "S": [480443.596, 538025.919], "EN": [538025.919, 564129.218],
                   "P2": [569539.407, 593144.901], "S_ring": [480443.596, 519657.038], "S_adv": [519657.038, 538025.919],
                   "S_friend": [519767.684, 533400.064], "diag": [118822.657, 480443.596], "P2_loop": [572474.713, 593144.901]}, WINDOWS
# 第一次結束回合(P_b 之後到逐鍵的第一步)沒有開出指令環
assert STEPS[0]["t"] < T["E_ring"] and STEPS[3]["t"] > T["E_ring"] > STEPS[2]["t"], (STEPS[2]["t"], T["E_ring"], STEPS[3]["t"])


# ================= (B) 掉中斷:格點 =================
def grid(rec: list[dict]) -> dict:
    """續一百六十三的格點法:DIG 第一次被服務起的 200 Hz 期,回傳格點與每格的進入。"""
    isr = [r["t"] for r in rec if r["k"] == "E" and r["eip"] == ISR]
    dig0 = next(r["t"] for r in rec if r["k"] == "E" and r["eip"] == DIG)
    w0 = max(i for i, t in enumerate(isr) if t <= dig0)
    win = isr[w0:]
    ph = collections.Counter(round((t - win[0] + P / 2) % P - P / 2, 2) for t in win)
    phi = ph.most_common(1)[0][0]
    g0 = win[0] + phi - P
    slot: dict[int, list[float]] = collections.defaultdict(list)
    for t in win:
        slot[int((t - g0 + 0.2) // P)].append(t)
    re_k = [(int((r["t"] - g0 + 0.2) // P), k) for k, r in enumerate(rec) if r["k"] == "E" and r["eip"] == REENTRY]
    assert rec[re_k[0][1]]["t"] > win[0]
    return {"g0": g0, "phi": phi, "within": sum(v for k, v in ph.items() if abs(k - phi) <= 0.1), "n": len(win),
            "slot": slot, "re_k": re_k, "lo": min(slot), "hi": max(slot)}


def k_of(g: dict, t: float) -> int:
    return int((t - g["g0"] + 0.2) // P)


def seg(g: dict, a: int, b: int) -> dict:
    """格 a .. b(含)的掉中斷。"""
    empty = [k for k in range(a, b + 1) if k not in g["slot"]]
    nre = sum(1 for k, _ in g["re_k"] if a <= k <= b)
    n = b - a + 1
    lost = nre + len(empty)
    return {"t_ms": [round(g["g0"] + a * P, 3), round(g["g0"] + (b + 1) * P, 3)], "slots": n, "reentry": nre, "merged": len(empty),
            "lost": lost, "fraction": round(lost / n, 5), "bios_tick_avg_ms": round(BIOS_MS / (1 - lost / n), 3)}


# 方法對照:lc163a 必須重現續一百六十三
_g163 = grid(load(RAW163 / "lc163a_CALLLOG.TXT"))
G163 = seg(_g163, _g163["lo"], _g163["hi"])
_l = S163["loss"]
assert (G163["slots"], G163["reentry"], G163["merged"], G163["lost"]) == (_l["slots"], _l["reentry"], _l["merged"], _l["total"]), G163
assert G163["t_ms"] == [3538.26, 31033.675], G163["t_ms"]
GR = grid(REC)
assert (GR["phi"], GR["within"], GR["n"]) == (0.0, 119503, 120602), (GR["phi"], GR["within"], GR["n"])
SEG = {nm: seg(GR, k_of(GR, a), k_of(GR, b) - 1) for nm, (a, b) in WIN.items()}

# ================= (C) 重入分型、DIG 長服務 =================
_pd = S164["interrupt_off"]["predicted_di"]
PRED_DI = {"DIG": {EPI: _pd["dig_restore"][hex(EPI)], EPI_CHAIN: _pd["dig_restore"][hex(EPI_CHAIN)]},
           "MDI": _pd["mdi_driver_return"], "MDI_AGAIN": int(S165["reentry_3665"]["di_reentry_to_next"])}
assert PRED_DI == {"DIG": {EPI: 93, EPI_CHAIN: 94}, "MDI": 62, "MDI_AGAIN": 57}, PRED_DI


def kind(k: int) -> str:
    r, q = REC[k], REC[k + 1]
    d = q["i"] - r["i"]
    if q["k"] == "A" and q["eip"] == REENTRY and d == PRED_DI["DIG"].get(q["at"]):
        return "DIG"
    if q["k"] == "E" and q["eip"] == DIG and d == PRED_DI["MDI"]:
        return "MDI"
    if q["k"] == "E" and q["eip"] == MDI and d == PRED_DI["MDI_AGAIN"]:
        return "MDI_AGAIN"
    return "other"


KIND = {k: kind(k) for _, k in GR["re_k"]}
# 未歸類 5 次,全在 P 之前(標題、城鎮、戰場開場);4 次是重入後 26 條就進 DIG,1 次是重入後 5 條又進 ISR(接著再重入)。
# 續一百六十六 lc166a 整份紀錄沒有這兩種;預測 P3 只看 P / S / EN / P2。
OTHER = [{"t": round(REC[k]["t"], 3), "next": f"{REC[k + 1]['k']} {REC[k + 1]['eip']:#x}", "di": REC[k + 1]["i"] - REC[k]["i"],
          "next2": f"{REC[k + 2]['k']} {REC[k + 2]['eip']:#x}"} for k, c in KIND.items() if c == "other"]
assert [(o["next"], o["di"], o["next2"]) for o in OTHER] == [
    ("E 0x404c0", 26, "R 0x404c0"), ("E 0x3ea8e", 5, "E 0x3ebad"), ("E 0x404c0", 26, "R 0x404c0"), ("E 0x404c0", 26, "R 0x404c0"),
    ("E 0x404c0", 26, "R 0x404c0")], OTHER
assert [o["t"] for o in OTHER] == [12755.406, 21506.01, 70304.844, 80574.992, 84364.72], OTHER
assert max(o["t"] for o in OTHER) < WIN["P"][0] and len(KIND) == 1025
_open: dict[int, dict] = {}
DIGS: list[tuple[float, int]] = []
for r in REC:
    if r["eip"] != DIG:
        continue
    if r["k"] == "E":
        _open[r["seq"]] = r
    elif r["seq"] in _open:
        e = _open.pop(r["seq"])
        DIGS.append((e["t"], r["i"] - e["i"]))
assert all(d < 100 or d > 15000 for _, d in DIGS) and min(d for _, d in DIGS) == 50     # 兩群,門檻落在中間
for nm, s in SEG.items():
    a, b = k_of(GR, s["t_ms"][0]), k_of(GR, s["t_ms"][1]) - 1
    c = collections.Counter(KIND[k] for kk, k in GR["re_k"] if a <= kk <= b)
    s["types"] = {t: c[t] for t in ("DIG", "MDI", "MDI_AGAIN", "other")}
    s["mdi_per_1000_slots"] = round(1000 * (c["MDI"] + c["MDI_AGAIN"]) / s["slots"], 3)
    _d = [d for t, d in DIGS if s["t_ms"][0] <= t < s["t_ms"][1]]
    s["dig_calls"], s["dig_long"] = len(_d), sum(d > LONG_I for d in _d)
    s["dig_long_share"] = round(s["dig_long"] / len(_d), 4)
SEG_T = {nm: s["t_ms"] for nm, s in SEG.items()}
assert SEG_T == {"P": [89737.131, 118322.562], "S": [480443.025, 538023.894], "EN": [538023.894, 564129.288],
                 "P2": [569539.369, 593144.725], "S_ring": [480443.025, 519653.617], "S_adv": [519653.617, 538023.894],
                 "S_friend": [519763.618, 533398.824], "diag": [118822.57, 480443.025], "P2_loop": [572474.414, 593144.725]}, SEG_T
# 格點時段 = 窗口落進的整格(邊界差 < 一格)
assert all(abs(SEG_T[nm][i] - WINDOWS[nm][i]) < P for nm in WIN for i in (0, 1)), (SEG_T, WINDOWS)
assert {nm: s["dig_long_share"] for nm, s in SEG.items()} == {"P": 0.0, "S": 0.0112, "EN": 0.0341, "P2": 0.0, "S_ring": 0.004,
                                                           "S_adv": 0.0268, "S_friend": 0.0362, "diag": 0.0007, "P2_loop": 0.0}
TABLE = {nm: (s["slots"], s["reentry"], s["merged"], s["fraction"], s["bios_tick_avg_ms"], s["types"]["DIG"], s["types"]["MDI"],
              s["types"]["MDI_AGAIN"], s["dig_long"]) for nm, s in SEG.items()}
assert TABLE == {
    "P": (5717, 27, 0, 0.00472, 55.186, 0, 27, 0, 0), "S": (11516, 111, 1, 0.00973, 55.464, 57, 54, 0, 128),
    "EN": (5221, 146, 1, 0.02816, 56.516, 61, 85, 0, 173), "P2": (4721, 23, 0, 0.00487, 55.194, 0, 23, 0, 0),
    "S_ring": (7842, 59, 1, 0.00765, 55.348, 22, 37, 0, 31), "S_adv": (3674, 52, 0, 0.01415, 55.714, 35, 17, 0, 97),
    "S_friend": (2727, 49, 0, 0.01797, 55.93, 35, 14, 0, 97), "diag": (72323, 383, 0, 0.0053, 55.217, 28, 355, 0, 49),
    "P2_loop": (4134, 21, 0, 0.00508, 55.205, 0, 21, 0, 0)}, TABLE
assert SPEED == {"P": 0.9999, "P2": 1.0006}, SPEED
for nm, s in SEG.items():
    assert sum(s["types"].values()) == s["reentry"] and s["types"]["other"] == 0, nm
    assert (s["dig_long"] == 0) == (s["types"]["DIG"] == 0), nm                     # 沒有長服務的時段就沒有 DIG 型重入
MDI_RATE = {nm: s["mdi_per_1000_slots"] for nm, s in SEG.items()}
assert MDI_RATE == {"P": 4.723, "S": 4.689, "EN": 16.28, "P2": 4.872, "S_ring": 4.718, "S_adv": 4.627, "S_friend": 5.134,
                    "diag": 4.909, "P2_loop": 5.08}, MDI_RATE
assert all(4.5 <= v <= 5.2 for nm, v in MDI_RATE.items() if nm != "EN") and MDI_RATE["EN"] > 3 * max(
    v for nm, v in MDI_RATE.items() if nm != "EN")                                  # 敵方回合以外都在每千格 4.6 .. 5.1

# ================= (D) 預測 =================
_pred = PRED_FILE.read_text(encoding="utf-8")
PRED_MD5 = hashlib.md5(PRED_FILE.read_bytes()).hexdigest()
assert PRED_MD5 == "ecf9abcb043fccd40eca5fa60bb8279c"
for _p in ("P1 P 的比例在 0.3% .. 0.8%", "P2 EN 的比例高於 P,且在 0.5% .. 3%", "未歸類 0", "≥ 90%", "相差 ≤ 0.3 個百分點",
           "P6(探索)S 的 MDI 型重入每千格次數高於 P", f"P = [t_a + {LEAD_MS}, t_b − {TAIL_MS}] ms",
           f"P2 = [t_c + {LEAD_MS}, t_d − {TAIL_MS}] ms"):
    assert _p in _pred, _p
PS, ENS, P2S, SS = SEG["P"], SEG["EN"], SEG["P2"], SEG["S"]
SHARE = {nm: round(SEG[nm]["reentry"] / SEG[nm]["lost"], 4) for nm in ("P", "EN")}
VERDICT = {"P1_P_0_3_to_0_8pct": "PASS" if 0.003 <= PS["fraction"] <= 0.008 else "FAIL",
           "P2_EN_above_P_and_0_5_to_3pct": "PASS" if ENS["fraction"] > PS["fraction"] and 0.005 <= ENS["fraction"] <= 0.03 else "FAIL",
           "P3_all_classified": "PASS" if all(SEG[nm]["types"]["other"] == 0 for nm in ("P", "S", "EN", "P2")) else "FAIL",
           "P4_reentry_share_ge_0_9": "PASS" if min(SHARE.values()) >= 0.9 else "FAIL",
           "P5_P2_within_0_3pp_of_P": "PASS" if abs(P2S["fraction"] - PS["fraction"]) <= 0.003 else "FAIL",
           "P6_S_mdi_rate_above_P": "PASS" if SS["mdi_per_1000_slots"] > PS["mdi_per_1000_slots"] else "FAIL"}
assert VERDICT == {"P1_P_0_3_to_0_8pct": "PASS", "P2_EN_above_P_and_0_5_to_3pct": "PASS", "P3_all_classified": "PASS",
                   "P4_reentry_share_ge_0_9": "PASS", "P5_P2_within_0_3pp_of_P": "PASS", "P6_S_mdi_rate_above_P": "FAIL"}, VERDICT
assert SHARE == {"P": 1.0, "EN": 0.9932}, SHARE

DIALOG = S166["grid"]["segments"]["post"]["fraction"]
assert DIALOG == 0.00557
CONC = {
    "player": f"玩家回合閒置(P,{PS['slots']} 格){PS['fraction']:.3%}、第二個玩家回合(P2){P2S['fraction']:.3%}"
              f"(主迴圈重新進入之後 {SEG['P2_loop']['fraction']:.3%});沒算進的全是 MDI 型重入,DIG 型 0 次,這兩段 DIG 長服務也是 0 次。"
              f"續一百六十六戰場開場對話 {DIALOG:.3%}。",
    "enemy": f"敵方回合(EN,{ENS['slots']} 格){ENS['fraction']:.3%}:重入 {ENS['reentry']}(DIG {ENS['types']['DIG']}、MDI {ENS['types']['MDI']})、"
             f"合併 {ENS['merged']};換算 BIOS tick 平均 {ENS['bios_tick_avg_ms']} ms。DIG 長服務占 {ENS['dig_long_share']:.2%}、"
             f"MDI 型每千格 {ENS['mdi_per_1000_slots']} 次(其他時段 4.6 .. 5.1)。",
    "switch": f"換邊(S){SS['fraction']:.3%}:指令環與確認框 {SEG['S_ring']['fraction']:.3%}、推進到敵方回合前 {SEG['S_adv']['fraction']:.3%}"
              f"(其中友軍回合 {SEG['S_friend']['fraction']:.3%})。",
    "mechanism": "DIG 型重入只出現在有 DIG 長服務的時段(長服務 0 次的 P / P2 也沒有 DIG 型);MDI 型在敵方回合以外每千格 4.6 .. 5.1 次,"
                 "敵方回合升到 16.28 次。",
    "predictions": f"P1 PASS({PS['fraction']:.2%})、P2 PASS({ENS['fraction']:.2%} > P)、P3 PASS、P4 PASS(重入占 P 100%、EN 99%)、"
                   f"P5 PASS(相差 {abs(P2S['fraction'] - PS['fraction']) * 100:.3f} 個百分點)、"
                   f"P6 FAIL(S 每千格 {SS['mdi_per_1000_slots']} ≤ P {PS['mdi_per_1000_slots']})。",
}
for _part, _key in (("0.472%", "player"), ("0.487%", "player"), ("0.508%", "player"), ("對話 0.557%", "player"),
                    ("2.816%", "enemy"), ("DIG 61、MDI 85", "enemy"), ("56.516 ms", "enemy"), ("16.28 次", "enemy"),
                    ("0.973%", "switch"), ("友軍回合 1.797%", "switch"), ("P6 FAIL(S 每千格 4.689 ≤ P 4.723)", "predictions"),
                    ("相差 0.015 個百分點", "predictions")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s167.py"),
    "exe_md5": MD5,
    "approval": "使用者 2026-10-29「永遠核准你進行實機」;實機 lc167a,不改記憶體、不下斷點、不進除錯器",
    "prediction_file": {"path": rel(PRED_FILE), "md5": PRED_MD5},
    "run": {"calllog": rel(RAW / "lc167a_CALLLOG.TXT"), "calllog_md5": CALLLOG_MD5, "lines": int(META[2]), "records": len(REC),
            "entries": [hex(a) for a in ENTRIES], "markers": {hex(e): [MK[("E", e)], MK[("R", e)]] for e in MARKERS},
            "marker_t_ms": T, "speed_emulated_over_host": SPEED,
            "first_end_turn": "find_empty_adjacent_tile 往上找到空格,但後面 Return / Down / Return / Return 沒開出指令環(0x16f55 沒進入),"
                              "停在索爾的狀態畫面,240 秒沒等到敵方回合;同一個 instance 逐鍵截圖改走(steps),之後按 YES",
            "steps": [{k: s[k] for k in ("label", "key", "t")} for s in STEPS]},
    "windows_ms": WINDOWS,
    "method_check_lc163a": G163,
    "grid": {"phase_mode_ms": GR["phi"], "within_0_1ms": GR["within"], "isr_entries": GR["n"]},
    "segments": SEG,
    "unclassified_before_P": OTHER,
    "predicted_di": {"DIG": {hex(k): v for k, v in PRED_DI["DIG"].items()}, "MDI": PRED_DI["MDI"], "MDI_AGAIN": PRED_DI["MDI_AGAIN"]},
    "predictions": VERDICT,
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, TABLE["P"], TABLE["EN"], TABLE["P2"], VERDICT)
