"""續一百六十證據:evidence/item5_title_return_s160_20261028.json(第 5 項第 6 次,lc159b;
使用者 2026-10-28 再次核准「第五項 核准授權你重新實機重跑驗證」)。

第 5 項:GAME OVER 回標題後,選新遊戲的是哪一次 Return,以及 delay 的校準。預測 P0 .. P5 在 drivers_s159/pred159_item5.txt
(2026-10-28 03:18,第 5 次之前寫,這次照原文用)。做法:逐鍵送、逐鍵截圖(drivers_s160/step159.py),停在「結束這回合?」框,
只把索爾 +5 的 bit0 設 1(讀回比對),送 YES,再照 lc131a 的清對話迴圈固定送 45 次 Return,主機端記每次送鍵 / 截圖的時間;
呼叫紀錄(修補版 dosbox-x,ICOUNT,閘門 = show_result_resource_79)記 GAME OVER 之後的標題序列與讀鍵的模擬時間。
(A) 原始紀錄:完整呼叫紀錄的指紋與過濾規則、寫入讀回、post 讀到的 [0x541b0] / [0x53c03]。
(B) 設定步驟:清對話的第 32 次 Return 讓索爾的資訊框出現、地圖褪色(選了索爾);Escape 還原;之後 Up → Return → Down → Return 到提示框。
    第 5 次 FAIL(索爾移到上一格)與此相符。
(C) P0、P2:事件順序;選單 flush 到確認之間只讀一個鍵。
(D) P1:閃爍 / 淡出的模擬時間與 delay 每次的實際長度。
(E) P5、P3:主機與模擬時間的線性對齊;確認的讀鍵是哪一次送鍵。
(F) P4:迴圈截圖的規則。
全部從 .wsl_build/lc159_live/ 與 drivers_s159/pred159_item5.txt 重算;任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import re

import numpy as np
from PIL import Image

from _evpaths import GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)

RAW = ROOT / ".wsl_build" / "lc159_live"
STEPS = RAW / "lc159b" / "steps"
LOOP = RAW / "lc159b" / "loop"
OUT = out_path("item5_title_return_s160_20261028.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
GATE = 0x22E5C
PRED = GEN_DIR / "drivers_s159" / "pred159_item5.txt"
NAMES = {0x22E5C: "gameover", 0x1F894: "title", 0x1FC66: "intro_exit", 0x1FD7C: "menu_flush", 0x370F0: "readkey",
         0x1FE63: "menu_key", 0x1FED3: "confirm", 0x1FEF0: "blink", 0x1FF31: "fade", 0x1FF36: "cls",
         0x32326: "newgame", 0x4E381: "kbd_flush", 0x3E01D: "delay", 0x10620: "has_key"}


def sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ================= (A) 原始紀錄 =================
META = (RAW / "lc159b_meta.txt").read_text(encoding="utf-8").splitlines()
assert META[0].split() == ["2dbf231b7f649cb8cd59d55407715f6b", "CALLLOG.TXT"], META
assert META[1].split() == [MD5, "FD2.EXE"], META          # harness 目錄裡跑的就是原版
FULL_LINES = int(META[2])
assert FULL_LINES == 58500104
HDR = META[3]
assert HDR.startswith("H fd2calllog 1 ") and "icount=1" in HDR and f"gate={GATE + DELTA:08x}" in HDR, HDR
assert META[4] == 'filter: awk !($3=="001ac620" && ($1=="E" || $4=="00000000"))', META[4]

_lines = (RAW / "lc159b_calllog_filtered.txt").read_text(encoding="ascii").splitlines()
assert _lines[0] == HDR
assert len(_lines) == 2924 and len(_lines) < FULL_LINES
REC: list[dict] = []
for ln in _lines:
    t = ln.split()
    if t[0] not in ("E", "R"):
        continue
    d = {"k": t[0], "seq": int(t[1]), "eip": int(t[2], 16) - DELTA}
    if t[0] == "R":
        d["eax"] = int(t[3], 16)
    else:
        d["ret"] = int(t[3], 16) - DELTA
        d["s0"] = int(next(x for x in t if x.startswith("s="))[2:].split(",")[0], 16)
    d["t"] = float(next(x for x in t if x.startswith("t="))[2:])
    REC.append(d)
# 過濾規則確實套用:has_key 只剩回傳非 0 的 R 記錄
assert not [r for r in REC if r["eip"] == 0x10620 and (r["k"] == "E" or r["eax"] == 0)]
assert {r["eip"] for r in REC} <= set(NAMES), {hex(r["eip"]) for r in REC} - set(NAMES)

KILL = json.loads((RAW / "lc159b_kill.json").read_text(encoding="utf-8"))
assert (KILL["sol_plus5_before"], KILL["sol_plus5_after"], KILL["bps"]) == (0, 1, []), KILL
assert KILL["sol_hp"] == [823, 823]                       # 只改 +5 的 bit0,HP 沒動
POST = json.loads((RAW / "lc159b_post.json").read_text(encoding="utf-8"))
CALIB, C03 = POST["calib_541b0"], POST["c03"]
assert C03 == 0x20                                         # 0x32326:新遊戲開場寫 [0x53c03] = 0x20
assert CALIB == 9057

# ================= (B) 設定步驟(逐鍵截圖) =================
STEP = [json.loads(x) for x in (RAW / "lc159b_steps.jsonl").read_text(encoding="utf-8").splitlines()]
assert [s["n"] for s in STEP] == list(range(len(STEP))) and len(STEP) == 41
_clears = [s for s in STEP if s["cmd"] == "key" and s["png"].endswith("_clear.png")]
assert len(_clears) == 32 and all(s["key"] == "Return" for s in _clears)
SEQ_AFTER = [(s["cmd"], s.get("key"), s["empty"]) for s in STEP[31:40]]
assert SEQ_AFTER == [("key", "Return", None), ("key", "Return", False), ("shot", None, False), ("key", "Escape", False),
                     ("key", "Up", True), ("key", "Return", True), ("key", "Down", True), ("key", "Return", None),
                     ("shot", None, None)], SEQ_AFTER
assert STEP[38]["t0"] < KILL["t_host"] < STEP[39]["ts0"]   # 寫入發生在提示框之後、YES 之前


def img(name: str) -> np.ndarray:
    return np.asarray(Image.open(STEPS / name).convert("RGB")).astype(int)


I31, I32, I33, I34 = (img(f"{n}.png") for n in ("031_clear", "032_clear", "033_idle3s", "034_esc"))
I37, I38, I39 = (img(f"{n}.png") for n in ("037_down", "038_endsel", "039_afterkill"))


def panel(a: np.ndarray) -> float:            # 左上的角色資訊框(名字 / LV / HP / MP)的藍色通道
    return round(float(a[222:300, 214:505, 2].mean()), 1)


def sat(a: np.ndarray) -> float:              # 右側地圖一塊的平均飽和度(max − min)
    r = a[320:420, 520:824]
    return round(float((r.max(axis=2) - r.min(axis=2)).mean()), 2)


PANEL = [panel(a) for a in (I31, I32, I33, I34)]
SAT = [sat(a) for a in (I31, I32, I33, I34)]
assert PANEL[1] > 3 * PANEL[0] and PANEL[2] > 3 * PANEL[0] and PANEL[3] == PANEL[0]
assert SAT[2] < 0.8 * SAT[0] and SAT[3] == SAT[0]             # 033 褪色;Escape 之後回到選之前
def diff_frac(a: np.ndarray, b: np.ndarray) -> float:   # 地圖一塊(避開左下 HUD 框)不同的像素比例
    return round(float((a[210:520, 340:824] != b[210:520, 340:824]).any(axis=2).mean()), 4)


DIFF_ESC, DIFF_SEL = diff_frac(I31, I34), diff_frac(I31, I33)
assert DIFF_ESC < 0.05 and DIFF_SEL > 0.9                   # Escape 之後只剩單位待機動畫的差;033 幾乎整塊變了
MAP_RESTORED = DIFF_ESC < 0.05
assert (DIFF_ESC, DIFF_SEL) == (0.0256, 0.9789), (DIFF_ESC, DIFF_SEL)
PROMPT_BLUE = [round(float(a[440:580, 380:810, 2].mean()), 1) for a in (I37, I38)]
assert PROMPT_BLUE[1] > 1.5 * PROMPT_BLUE[0]                  # 038 下方出現藍色提示框
SOL_TILE = round(float(np.abs(I38[292:340, 728:776] - I39[292:340, 728:776]).mean()), 2)
REST = round(float(np.abs(I38[210:420, 200:700] - I39[210:420, 200:700]).mean()), 3)
assert SOL_TILE > 10 * REST                                   # 寫入之後只有索爾那一格變(不畫倒下的單位)
assert (PANEL, SAT, PROMPT_BLUE, SOL_TILE, REST) == ([34.1, 127.0, 127.0, 34.1], [83.6, 83.76, 60.89, 83.6],
                                                     [69.2, 137.3], 52.32, 2.3), (PANEL, SAT, PROMPT_BLUE, SOL_TILE, REST)

# ================= (C) P0、P2:事件順序 =================
EV = [r for r in REC if r["k"] == "E" and r["eip"] not in (0x10620, 0x3E01D, 0x4E381)]
G0 = next(r for r in REC if r["k"] == "E" and r["eip"] == GATE)
assert G0["seq"] == 1 and REC[0] is G0                        # 閘門在 GAME OVER 打開,之前沒有記錄
FIRST = {}
for r in EV:
    FIRST.setdefault(NAMES[r["eip"]], r)
ORDER = ["gameover", "title", "intro_exit", "menu_flush", "menu_key", "confirm", "blink", "fade", "cls", "newgame"]
assert all(k in FIRST for k in ORDER), sorted(FIRST)
assert [FIRST[k]["seq"] for k in ORDER] == sorted(FIRST[k]["seq"] for k in ORDER)
assert [FIRST[k]["seq"] for k in ORDER] == [1, 132, 397, 524, 527, 528, 529, 538, 603, 668]
for k in ORDER[1:-1]:
    assert sum(NAMES[r["eip"]] == k for r in EV) == 1, k       # 標題序列每個點只走一次
P0 = {"gate_opened": True, "newgame_seq": FIRST["newgame"]["seq"], "c03_after": C03}

S_FL, S_CF = FIRST["menu_flush"]["seq"], FIRST["confirm"]["seq"]
_between = [r for r in REC if S_FL < r["seq"] < S_CF]
MENU_KEYS = [r for r in _between if r["k"] == "E" and r["eip"] == 0x1FE63]
READS = [r for r in _between if r["k"] == "E" and r["eip"] == 0x370F0]
FLUSH = [r for r in _between if r["k"] == "E" and r["eip"] == 0x4E381]
assert len(MENU_KEYS) == 1 and len(READS) == 1               # P2:選單只讀一個鍵
assert len(FLUSH) == 1 and FLUSH[0]["ret"] == 0x1FD81 and FLUSH[0]["seq"] == S_FL + 1   # 0x1fd7c 的 call kbd_flush
assert not [r for r in _between if r["eip"] == 0x10620]       # 這段沒有 has_key 非 0:讀鍵是阻塞讀
R_CONF = next(r for r in REC if r["k"] == "R" and r["seq"] == READS[0]["seq"])
P2 = {"menu_reads": len(READS), "flush_seq": FLUSH[0]["seq"], "read_seq": READS[0]["seq"]}

# ================= (D) P1:閃爍 / 淡出 =================
T = {k: FIRST[k]["t"] for k in ORDER}
BLINK_MS = round(T["fade"] - T["blink"], 1)
FADE_MS = round(T["cls"] - T["fade"], 1)
_rets = {r["seq"]: r for r in REC if r["k"] == "R" and r["eip"] == 0x3E01D}
DELAYS = [(r["s0"], r["ret"], round(_rets[r["seq"]]["t"] - r["t"], 1)) for r in REC
          if r["k"] == "E" and r["eip"] == 0x3E01D and r["seq"] in _rets]
_bl = [d for r, d in zip([r for r in REC if r["k"] == "E" and r["eip"] == 0x3E01D and r["seq"] in _rets], DELAYS)
       if T["blink"] <= r["t"] < T["fade"]]
_fd = [d for r, d in zip([r for r in REC if r["k"] == "E" and r["eip"] == 0x3E01D and r["seq"] in _rets], DELAYS)
       if T["fade"] <= r["t"] < T["cls"]]
assert [(a, rt) for a, rt, _ in _bl] == [(0x50, 0x1FF0D), (0x50, 0x1FF28)] * 4   # 閃爍 4 ×(delay 80 + delay 80)
assert {(a, rt) for a, rt, _ in _fd} == {(2, 0x1F51A)} and len(_fd) == 64         # 淡出:64 × delay 2
BL_MS = [d for _, _, d in _bl]
LOOPS80 = (80 * CALIB + 500) // 1000                           # 0x3e01d 的圈數公式(靜態依據,見預測檔)
assert LOOPS80 == 725
assert min(BL_MS) > 85 and max(BL_MS) < 105
FD_DELAY_MS = round(sum(d for _, _, d in _fd), 1)
assert (BLINK_MS, FADE_MS, round(sum(BL_MS), 1), FD_DELAY_MS) == (762.9, 432.4, 757.4, 139.2), \
    (BLINK_MS, FADE_MS, round(sum(BL_MS), 1), FD_DELAY_MS)
P1_OK = {"calib_nonzero": CALIB != 0, "blink_640_pm15": 640 * 0.85 <= BLINK_MS <= 640 * 1.15,
         "fade_le_300": FADE_MS <= 300, "sum_le_900": BLINK_MS + FADE_MS <= 900}
assert P1_OK == {"calib_nonzero": True, "blink_640_pm15": False, "fade_le_300": False, "sum_le_900": False}, P1_OK
D80_RATIO = [round(min(BL_MS) / 80, 3), round(max(BL_MS) / 80, 3)]
INT21_RATE = round(LOOPS80 / (sum(BL_MS) / len(BL_MS) / 1000))     # 閃爍時每秒的 int 21h 次數(開機量的是 CALIB)
assert INT21_RATE < CALIB                                        # delay 偏長 = 這段時間 int 21h 比開機時慢
assert (D80_RATIO, INT21_RATE) == ([1.131, 1.235], 7658), (D80_RATIO, INT21_RATE)
P1 = {"calib_541b0": CALIB, "blink_ms": BLINK_MS, "fade_ms": FADE_MS, "delay80_ms": BL_MS,
      "delay80_vs_nominal": D80_RATIO, "int21_rate_during_blink_per_s": INT21_RATE,
      "fade_delay_ms": FD_DELAY_MS, "fade_non_delay_ms": round(FADE_MS - FD_DELAY_MS, 1), "checks": P1_OK}

# ================= (E) P5、P3:主機 / 模擬時間對齊 =================
LP = json.loads((RAW / "lc159b_loop.json").read_text(encoding="utf-8"))
SENDS = [e for e in LP["events"] if e["op"] == "send"]
SHOTS = [e for e in LP["events"] if e["op"] == "shot"]
assert [e["tag"] for e in SENDS] == ["yes"] + [f"clear{k:03d}" for k in range(1, 46)] and len(SHOTS) == 45
H0 = SENDS[0]["t0"]
assert STEP[39]["ts1"] < H0                                   # YES 在寫入確認的截圖之後
HS = [(e["tag"], e["t0"] - H0) for e in SENDS]
G0T = G0["t"]
KEYS: list[tuple[str, float, int]] = []                        # 鍵到達:has_key 非 0 群的第一筆(相隔 > 50 ms 算新的一群)+ 阻塞讀的返回
_last = -1e9
for r in REC:
    if r["k"] == "R" and r["eip"] == 0x10620:
        if r["t"] - _last > 50:
            KEYS.append(("hk", (r["t"] - G0T) / 1000, r["seq"]))
        _last = r["t"]
    elif r["k"] == "R" and r["eip"] == 0x370F0:
        KEYS.append(("rd", (r["t"] - G0T) / 1000, r["seq"]))
KEYS.sort(key=lambda k: k[1])
_hk_t = [r["t"] for r in REC if r["k"] == "R" and r["eip"] == 0x10620]
_gaps = [b - a for a, b in zip(_hk_t, _hk_t[1:])]
HK_INTRA_MAX, HK_INTER_MIN = round(max(g for g in _gaps if g <= 50), 1), round(min(g for g in _gaps if g > 50), 1)
assert HK_INTRA_MAX < 50 < HK_INTER_MIN / 10                   # 50 ms 的分群門檻離兩邊都有餘裕(28 .. 893 ms 之間任一值結果相同)
assert (len(_hk_t), HK_INTRA_MAX, HK_INTER_MIN, sum(k[0] == "hk" for k in KEYS)) == (202, 28.3, 893.3, 17)
D0 = HS[-1][1] - KEYS[-1][1]                                   # 迴圈最後一次送鍵 = 最後一個到達的鍵(之後沒有再送)
PAIRS = []
for kind, ks, seq in KEYS:
    cand = [(tag, h) for tag, h in HS if h <= ks + D0 + 0.08]
    if cand and ks + D0 - cand[-1][1] < 0.35:
        PAIRS.append((cand[-1][0], cand[-1][1], ks, kind, seq))
assert len(PAIRS) == len(KEYS) == 33                          # 每個鍵到達都配到一次送鍵(YES 在閘門打開前就被讀走)
_x = np.array([p[1] for p in PAIRS])
_y = np.array([p[2] for p in PAIRS])
SLOPE, ICPT = (float(v) for v in np.polyfit(_x, _y, 1))


def host_of(sim_rel: float) -> float:
    return (sim_rel - ICPT) / SLOPE


RESID = {(p[0], p[3], p[4]): host_of(p[2]) - p[1] for p in PAIRS}
assert 0.9 <= SLOPE <= 1.1                                     # P5
conf_key = next(k for k in RESID if k[2] == R_CONF["seq"])
R_MAX = max(abs(v) for k, v in RESID.items() if k != conf_key)
H_FLUSH = host_of((FIRST["menu_flush"]["t"] - G0T) / 1000)
H_CONF = host_of((R_CONF["t"] - G0T) / 1000)
WIN = [tag for tag, h in HS if H_FLUSH - R_MAX <= h <= H_CONF + R_MAX]
CONF_SEND = conf_key[0]
LAG = RESID[conf_key]
assert WIN == [CONF_SEND] == ["clear011"]                       # P3:flush 到確認之間(含對齊誤差)恰好一次送鍵
assert [t for t, h in HS if h > H_FLUSH][0] == CONF_SEND       # 而且是 0x1fd7c 之後的第一次送鍵
assert -R_MAX <= LAG <= 0.3
FIT = {"slope": round(SLOPE, 5), "intercept_s": round(ICPT, 3), "max_abs_resid_s": round(R_MAX, 3),
       "confirm_lag_s": round(LAG, 3), "host_menu_flush_s": round(H_FLUSH, 3), "host_confirm_read_s": round(H_CONF, 3)}
assert FIT == {"slope": 0.99951, "intercept_s": -0.632, "max_abs_resid_s": 0.136, "confirm_lag_s": -0.059,
               "host_menu_flush_s": 9.653, "host_confirm_read_s": 9.924}, FIT
N_RETURN = [t for t, _ in HS].index(CONF_SEND) + 1             # 含 YES 的第幾次 Return
assert N_RETURN == 12
PD = [{"send": p[0], "host_s": round(p[1], 3), "sim_s": round(p[2], 3), "kind": p[3], "seq": p[4],
       "resid_s": round(RESID[(p[0], p[3], p[4])], 3)} for p in PAIRS]
assert all(d["sim_s"] < d["host_s"] for d in PD) and {d["kind"] for d in PD} == {"hk", "rd"}
assert [d["send"] for d in PD if d["kind"] == "rd"][:2] == ["clear005", "clear011"]   # GAME OVER 畫面的讀鍵、選單的確認
PD_SHA = hashlib.sha256(json.dumps(PD, ensure_ascii=False).encode()).hexdigest()[:16]
assert PD_SHA == "8dc4b9c8e6b5b4e0", PD_SHA                                   # 33 筆配對的內容釘住
P35 = {**FIT, "pairs": len(PAIRS), "confirm_send": CONF_SEND, "return_count_incl_yes": N_RETURN,
       "pairs_detail": PD}

# ================= (F) P4:迴圈截圖 =================
def gray(k: int) -> np.ndarray:
    return np.asarray(Image.open(LOOP / f"findempty_clear_{k:03d}.png").convert("RGB")).astype(float).mean(axis=2)[184:600, 192:832]


GR = {k: gray(k) for k in (9, 10, 11, 12, 13)}
MEAN = {k: round(float(v.mean()), 2) for k, v in GR.items()}
CORR_10_11 = round(float(np.corrcoef(GR[10].ravel(), GR[11].ravel())[0, 1]), 4)
CORR_10_13 = round(float(np.corrcoef(GR[10].ravel(), GR[13].ravel())[0, 1]), 4)
assert CORR_10_11 > 0.99 and MEAN[11] < 0.9 * MEAN[10]        # 11 = 同一張選單、變暗(淡出中)
assert MEAN[9] < 5 and MEAN[12] < 5 and CORR_10_13 < 0.3       # 9 片頭暗場、12 清畫面、13 是別的畫面(新遊戲)
SHOT_T = {k: SHOTS[k - 1]["t0"] - H0 for k in (10, 11)}
H_FADE = (host_of((T["fade"] - G0T) / 1000), host_of((T["cls"] - G0T) / 1000))
assert SHOT_T[10] < H_CONF and H_FADE[0] <= SHOT_T[11] <= H_FADE[1]   # 10 在確認之前;11 落在紀錄算出的淡出區間裡
LAST_STILL = 10
assert f"clear{LAST_STILL + 1:03d}" == CONF_SEND                # P4:最後一張全亮選單的下一張編號 = 確認的送鍵
assert (MEAN, CORR_10_11, CORR_10_13) == ({9: 3.13, 10: 66.37, 11: 55.02, 12: 3.13, 13: 132.08}, 0.9983, 0.0506), \
    (MEAN, CORR_10_11, CORR_10_13)
SHOT11_T, FADE_T = round(SHOT_T[11], 3), [round(x, 3) for x in H_FADE]
assert (SHOT11_T, FADE_T) == (10.777, [10.688, 11.121]), (SHOT11_T, FADE_T)
P4 = {"means": MEAN, "corr_10_11": CORR_10_11, "corr_10_13": CORR_10_13, "last_still_menu_shot": LAST_STILL,
      "shot11_host_s": SHOT11_T, "fade_host_s": FADE_T}
EVS = {k: round((T[k] - G0T) / 1000, 3) for k in ORDER}
assert EVS == {"gameover": 0.0, "title": 3.459, "intro_exit": 7.349, "menu_flush": 9.016, "menu_key": 9.288,
               "confirm": 9.288, "blink": 9.288, "fade": 10.051, "cls": 10.484, "newgame": 10.934}, EVS

# ================= 判定 =================
_pl = re.findall(r"^(P\d) ", PRED.read_text(encoding="utf-8"), re.M)
assert _pl == [f"P{i}" for i in range(6)], _pl
# P0、P2 .. P5 的判準都在上面 assert(不符就停在那裡);P1 由四個條件推出
VERDICT = {"P0": "PASS", "P1": "PASS" if all(P1_OK.values()) else "FAIL", "P2": "PASS", "P3": "PASS", "P4": "PASS",
           "P5": "PASS"}
assert list(VERDICT) == _pl
assert VERDICT == {"P0": "PASS", "P1": "FAIL", "P2": "PASS", "P3": "PASS", "P4": "PASS", "P5": "PASS"}, VERDICT

OUTD = {
    "generator": rel(GEN_DIR / "ev_s160.py"),
    "approval": "使用者 2026-10-28「第五項 核准授權你重新實機重跑驗證」(第 6 次,lc159b)",
    "exe_md5": MD5,
    "calllog": {"full_md5": "2dbf231b7f649cb8cd59d55407715f6b", "full_lines": FULL_LINES, "header": HDR,
                "filtered": rel(RAW / "lc159b_calllog_filtered.txt"), "filter": META[4]},
    "predictions": {"file": rel(PRED), "sha256": sha(PRED), "verdict": VERDICT},
    "setup_steps": {"panel_blue": PANEL, "map_saturation": SAT, "map_restored_after_escape": MAP_RESTORED,
                    "map_diff_frac_vs_031": {"033_idle3s": DIFF_SEL, "034_esc": DIFF_ESC},
                    "prompt_blue": PROMPT_BLUE, "sol_tile_diff": SOL_TILE, "rest_diff": REST,
                    "kill": {k: KILL[k] for k in ("sol_plus5_before", "sol_plus5_after", "sol_hp", "bps")},
                    "note": "清對話第 32 次 Return 出現索爾的資訊框、3 秒後地圖褪色(推論:選了索爾、顯示移動範圍);"
                            "Escape 回到選之前。第 5 次在這個狀態送 Up → Return,索爾移到上一格(推論)。"},
    "events_seq": {k: FIRST[k]["seq"] for k in ORDER},
    "events_sim_s_from_gameover": EVS,
    "P0": P0, "P1": P1, "P2": P2, "P3_P5": P35, "P4": P4,
    "conclusion": "選新遊戲的是標題選單 0x1fd7c 清掉鍵盤緩衝之後送到的第一個 Return(選單阻塞讀一個鍵,預設是 START);"
                  "這一次是 YES 之後的第 12 次 Return(clear011)。次數取決於 GAME OVER 與送鍵的時間,"
                  "lc131a 的「第 18 次」是同一個機制的一個例子,不是固定值。",
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, VERDICT, "confirm", CONF_SEND, "slope", round(SLOPE, 5))
