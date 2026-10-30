"""續一百六十九證據:evidence/driver_followups_s169_20261030.json(CALLLOG 尾端讀數的真實落後、HUD 邊框樣板、選中單位的實機重現)。

使用者 2026-10-30「依照你的建議自動繼續進行處理」(續一百六十八的仍留:閒置窗開頭的寫入落後、藍色地形上 HUD 漏判)。
(A) CALLLOG 的寫盤位置。寫入端 `setvbuf(out, NULL, _IOFBF, 1 << 20)` 的 buf 是 NULL;若真是 1 MiB 緩衝,
    尾端讀數時的檔尾只會落在明確 fflush(每 1024 筆 E、periodic 計數)的位置。lc167a / lc168a 的 9 次尾端讀數
    逐一比對:檔尾都在「上一次明確 fflush + k × 4096」上(glibc 的預設區塊緩衝),1 MiB 模型 0 次。
    對照:在整份紀錄均勻取 1000 個假讀數,命中率約為行長 / 4096。
    由下一次寫盤位置推出每次讀數的落後上界,與續一百六十七閒置窗開頭扣掉的 1000 ms 比較。
(B) HUD 邊框樣板(tools/fd2_chapter_sweep.py BATTLE_HUD_FRAME_RUNS)。827 張校準截圖(drivers_s168/calib_frames.txt)
    的人工標記(drivers_s169/hud_labels.txt,139 張有 HUD 框):樣板吻合率、舊藍佔比判準與新判準的混淆表、側別、
    樣板每個像素在 139 張上都相同。
(C) 實機 lc169a(DOSBox-X 呼叫紀錄,入口 = lc168a 的 26 個 + 0x18890 選格 / 動作分派 + 0x17aed 狀態卡):同 lc168a 進第 1 章戰場,
    清對話只在面板上按;一讀到 E 0x117e7 就送一次 Return(複製 lc167a 的第 33 次),之後 sel_0、Up、sel_up。
    實機前預測 S1 .. S6(drivers_s169/pred169_select.txt)逐項判定。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import re
import sys
import warnings

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
warnings.filterwarnings("ignore", category=DeprecationWarning)      # Pillow getdata 的棄用警告
sys.path.insert(0, str(ROOT / "tools"))
import fd2_chapter_sweep as sw  # noqa: E402
from PIL import Image, ImageStat  # noqa: E402

OUT = out_path("driver_followups_s169_20261030.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
PATCH = ROOT / "tools" / "dosbox" / "fd2_calllog_patch.py"
DRV = GEN_DIR / "drivers_s169"
BLOCK = 4096
LEAD_MS_S167 = 1000                    # 續一百六十七閒置窗開頭扣掉的毫秒數((A) 對其證據核對)
NULL_PER_LOG = 500                     # 對照:每份紀錄均勻取的假讀數個數


def md5(p) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------- (A) 寫盤位置
_patch = PATCH.read_text(encoding="utf-8")
for _s in ("setvbuf(out, NULL, _IOFBF, 1 << 20);", "if ((seq & 1023u) == 0) fflush(out);",
           'if ((ginstr & ((1ull << 26) - 1)) == 0) dump_counts("periodic");'):
    assert _patch.count(_s) == 1, _s
_dump = _patch[_patch.index("static void dump_counts"):_patch.index("static void at_exit_flush")]
assert "fflush(out);" in _dump                                         # periodic 計數也是一次明確 fflush

RUNS = {"lc167a": (ROOT / ".wsl_build" / "lc167_live", ("lc167a_run.json", "lc167a_finish.json"), "ac9401da607102caa569be467c178b92"),
        "lc168a": (ROOT / ".wsl_build" / "lc168_live", ("lc168a_run.json",), "068485e3e8b80dd89c6a3a481b57c45f")}
READS = []        # (tag, mark, t, e0, e1, prev_flush, flushes, raw)
LOGS = {}
for tag, (d, runs, cmd5) in RUNS.items():
    raw = (d / f"{tag}_CALLLOG.TXT").read_bytes()
    assert hashlib.md5(raw).hexdigest() == cmd5, tag
    flush = [raw.index(b"\n") + 1]                                    # 表頭行尾(init 的 fflush)
    flush += [m.end() for m in re.finditer(rb"^E (\d+) [^\n]*\n", raw, re.M) if int(m.group(1)) % 1024 == 0]
    flush += [m.end() for m in re.finditer(rb"^T periodic \d+\n(?:C [^\n]*\n)*", raw, re.M)]
    flush.sort()
    marks = {}
    for rn in runs:
        for k, v in json.loads((d / rn).read_text(encoding="utf-8"))["marks"].items():
            if isinstance(v, list) and len(v) == 2:
                marks[k] = v[1]
    LOGS[tag] = {"bytes": len(raw), "E": raw.count(b"\nE "), "explicit_flushes": len(flush), "marks": sorted(marks)}
    for nm, t in sorted(marks.items(), key=lambda kv: kv[1]):
        key = (" t=%.6f\n" % t).encode()
        pos = raw.find(key)
        assert pos >= 0 and raw.find(key, pos + 1) < 0, (tag, nm)      # 讀到的 t 在紀錄裡恰好一行
        e0 = pos + len(key)
        e1 = raw.index(b"\n", e0) + 1
        READS.append((tag, nm, t, e0, e1, max(f for f in flush if f <= e0), flush, raw))
assert [(r[0], r[1]) for r in READS] == [("lc167a", "P_a"), ("lc167a", "P_b"), ("lc167a", "yes"), ("lc167a", "P2_c"),
                                         ("lc167a", "P2_d"), ("lc168a", "P_a"), ("lc168a", "P_b"), ("lc168a", "P2_c"),
                                         ("lc168a", "P2_d")], [(r[0], r[1]) for r in READS]


def hit(e0: int, e1: int, prev: int, b: int) -> bool:
    """檔尾(讀數那一行之後、下一行結束之前)是否可能落在 prev + k*b 上。"""
    nxt = prev + ((e0 - prev) // b + 1) * b
    return e0 < nxt <= e1


MODEL = {str(b): sum(hit(e0, e1, prev, b) for _, _, _, e0, e1, prev, _, _ in READS) for b in (BLOCK, 2 * BLOCK, 1 << 16, 1 << 20)}
assert MODEL == {"4096": 9, "8192": 7, "65536": 1, "1048576": 0}, MODEL
# 1 MiB 模型下檔尾只能在明確 fflush 上;讀數那一行到上一次明確 fflush 都隔了好幾行
GAP_LINES = [raw[prev:e0].count(b"\n") for _, _, _, e0, _, prev, _, raw in READS]
assert min(GAP_LINES) >= 100, GAP_LINES

# 對照:在整份紀錄均勻取的假讀數(每份 NULL_PER_LOG 個有 t 的行,同樣的 prev 規則)。
# (只往前移幾行不行:讀數就在一個 4 KiB 邊界之後,往前 20 行還不到一塊,怎麼移都碰不到邊界。)
_null = []
_seen = set()
for tag, nm, t, e0, e1, prev, flush, raw in READS:
    if tag in _seen:
        continue
    _seen.add(tag)
    _pat = re.compile(rb" t=[0-9.]+\n")
    for i in range(1, NULL_PER_LOG + 1):
        a = _pat.search(raw, len(raw) * i // (NULL_PER_LOG + 1)).end()
        b2 = raw.index(b"\n", a) + 1
        _null.append(hit(a, b2, max(f for f in flush if f <= a), BLOCK))
NULL = {"pseudo_reads": len(_null), "hits": sum(_null), "rate": round(sum(_null) / len(_null), 4)}
NEXT_LEN = [e1 - e0 for _, _, _, e0, e1, _, _, _ in READS]
P_CHANCE = math.prod(n / BLOCK for n in NEXT_LEN)                       # 每次讀數「剛好」碰上 4 KiB 邊界的機率連乘
assert NULL == {"pseudo_reads": 1000, "hits": 43, "rate": 0.043}, NULL
assert f"{P_CHANCE:.4g}" == "1.978e-11" and NULL["rate"] < 0.15, (P_CHANCE, NULL)


def t_at(raw: bytes, byte: int) -> float:
    """byte 位置所在(或之後第一個)有 t 的行的 t。"""
    m = re.compile(rb" t=([0-9.]+)\n").search(raw, byte)
    return float(m.group(1))


# 落後上界:讀數時檔尾在 b;下一次寫盤是 b + 4096 或更早的明確 fflush;那一筆還沒寫出,所以真實時刻早於它的 t
LAG = {}
for tag, nm, t, e0, e1, prev, flush, raw in READS:
    b = prev + ((e0 - prev) // BLOCK + 1) * BLOCK
    nxt = min([b + BLOCK] + [f for f in flush if f > b])
    LAG[f"{tag}:{nm}"] = round(t_at(raw, nxt - 1) - t, 2)
assert LAG == {"lc167a:P_a": 25.0, "lc167a:P_b": 24.98, "lc167a:yes": 25.0, "lc167a:P2_c": 24.98, "lc167a:P2_d": 24.97,
               "lc168a:P_a": 25.0, "lc168a:P_b": 20.15, "lc168a:P2_c": 20.04, "lc168a:P2_d": 24.98}, LAG
LAG_MAX = max(LAG.values())
assert LAG_MAX <= 25
# 續一百六十七閒置窗:開頭 = P_a 讀數 + 1000 ms(對已提交證據核對),真實閒置開始最晚在 P_a + LAG_MAX
_S167 = json.loads((EVIDENCE / "battle_turn_interrupt_loss_s167_20261029.json").read_text(encoding="utf-8"))["windows_ms"]
_P_a = {r[1]: r[2] for r in READS if r[0] == "lc167a"}
assert round(_S167["P"][0] - _P_a["P_a"]) == LEAD_MS_S167 and round(_S167["P2"][0] - _P_a["P2_c"]) == LEAD_MS_S167, _S167
MARGIN_MS = round(LEAD_MS_S167 - LAG_MAX, 2)                          # 窗口開頭至少晚於真實讀數時刻這麼多
assert MARGIN_MS == 975.0
# 續一百六十八 (D) 用「每 1024 筆 E 才寫盤」算出的間隔
_S168 = json.loads((EVIDENCE / "battle_driver_gates_s168_20261030.json").read_text(encoding="utf-8"))
S168_CLAIM_S = _S168["flush_lag"]["flush_interval_s"]
assert S168_CLAIM_S == 1.92 and LAG_MAX < S168_CLAIM_S * 1000 / 40
BYTES_PER_1024E = {tag: round(1024 * v["bytes"] / v["E"]) for tag, v in LOGS.items()}
assert BYTES_PER_1024E == {"lc167a": 356072, "lc168a": 351257}, BYTES_PER_1024E
assert all(v < (1 << 20) / 2 for v in BYTES_PER_1024E.values())     # 1 MiB 緩衝永遠等不到滿

# ---------------------------------------------------------------- (B) HUD 邊框樣板
CALIB = [ROOT / ln for ln in (GEN_DIR / "drivers_s168" / "calib_frames.txt").read_text(encoding="utf-8").split()]
assert len(CALIB) == len(set(CALIB)) == 827
LABEL_FILE = DRV / "hud_labels.txt"
LABEL = {}
for ln in LABEL_FILE.read_text(encoding="utf-8").splitlines():
    if ln and not ln.startswith("#"):
        s, f = ln.split(" ", 1)
        assert s in ("L", "R") and f not in LABEL
        LABEL[f] = s
assert len(LABEL) == 139 and set(LABEL) <= {rel(f) for f in CALIB}
FRAME_PX = [(x, y, c) for y, x0, x1, c in sw.BATTLE_HUD_FRAME_RUNS for x in range(x0, x1 + 1)]
assert len(FRAME_PX) == 868 and sw.BATTLE_HUD_FRAME_DX_R == 474 and sw.BATTLE_HUD_FRAME_MATCH_MIN == 0.8


def old_side(im) -> str | None:
    """續一百六十八以前的判準(只有藍佔比)。"""
    if sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION, sw.BATTLE_HUD_RIGHT_STRIP_REGION):
        return "L"
    if sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION_R, sw.BATTLE_HUD_LEFT_STRIP_REGION_R):
        return "R"
    return None


ROWS = []
_const = {}                                                           # 樣板像素在有框那一側的顏色是否每張都一樣
for f in CALIB:
    im = Image.open(f).convert("RGB")
    assert im.size == (1024, 768), f
    lab = LABEL.get(rel(f))
    m = {s: sw._hud_frame_match(im, s) for s in "LR"}
    # 自己數一次吻合(不經工具),與工具的回傳值核對
    px = im.load()
    mine = {s: sum(px[x + (0 if s == "L" else 474), y] == c for x, y, c in FRAME_PX) / len(FRAME_PX) for s in "LR"}
    assert mine == m, (f, mine, m)
    if lab:
        dx = 0 if lab == "L" else 474
        for x, y, c in FRAME_PX:
            _const.setdefault((x, y), set()).add(px[x + dx, y])
    ROWS.append({"f": rel(f), "label": lab, "match": m, "old": old_side(im), "new": sw._find_hud_box_side(im),
                 "hud": sw.screen_shows_battle_hud(f)})
assert all(v == {c} for (x, y), v in _const.items() for xx, yy, c in [next(p for p in FRAME_PX if p[:2] == (x, y))])
ON = [r["match"][r["label"]] for r in ROWS if r["label"]]
OFF = [v for r in ROWS for s, v in r["match"].items() if s != r["label"]]
GAP = {"labelled_side_min": min(ON), "other_sides_max": round(max(OFF), 4), "other_sides": len(OFF)}
assert GAP == {"labelled_side_min": 1.0, "other_sides_max": 0.4009, "other_sides": 1515}, GAP
assert GAP["other_sides_max"] < sw.BATTLE_HUD_FRAME_MATCH_MIN < GAP["labelled_side_min"]


def confusion(pred) -> dict:
    c = collections.Counter((bool(r["label"]), bool(pred(r))) for r in ROWS)
    return {"tp": c[(True, True)], "fp": c[(False, True)], "fn": c[(True, False)], "tn": c[(False, False)]}


CONF = {"old_blue_fraction": confusion(lambda r: r["old"]),
        "frame_only": confusion(lambda r: max(r["match"].values()) >= sw.BATTLE_HUD_FRAME_MATCH_MIN),
        "tool_now": confusion(lambda r: r["hud"])}
assert CONF == {"old_blue_fraction": {"tp": 105, "fp": 75, "fn": 34, "tn": 613},
                "frame_only": {"tp": 139, "fp": 0, "fn": 0, "tn": 688},
                "tool_now": {"tp": 139, "fp": 75, "fn": 0, "tn": 613}}, CONF
# 工具保留舊判準的每一個 True(只會多不會少);補上的 34 張是哪些
assert all(r["hud"] for r in ROWS if r["old"])
GAINED = collections.Counter(r["f"].rsplit("/", 1)[0] for r in ROWS if r["hud"] and not r["old"])
assert dict(GAINED) == {".wsl_build/chapter_sweep_ch11chest/real_open5/shots": 1, ".wsl_build/ctr/terr2/ch20/shots": 20,
                        ".wsl_build/ctr/terr2/ch29/shots_t2": 13}, GAINED
# 續一百六十八記錄的兩張藍色地形截圖
for _n in ("ch20/shots/hudcheck_hud3_clear4.png", "ch29/shots_t2/hudcheck_t2_clear1.png"):
    _r = next(r for r in ROWS if r["f"] == f".wsl_build/ctr/terr2/{_n}")
    assert _r["old"] is None and _r["new"] == "L" == _r["label"], _r
# 側別:新判準在 139 張有框截圖上都說對;舊判準在它判對的 105 張上也對
SIDE = {"new_correct": sum(r["new"] == r["label"] for r in ROWS if r["label"]),
        "old_tp_correct": sum(r["old"] == r["label"] for r in ROWS if r["label"] and r["old"])}
assert SIDE == {"new_correct": 139, "old_tp_correct": 105}, SIDE
LABEL_MD5 = md5(LABEL_FILE)

# ---------------------------------------------------------------- (C) 實機 lc169a:輸入迴圈裡的 Return 選中索爾
RAW = ROOT / ".wsl_build" / "lc169_live"
PRED_FILE = DRV / "pred169_select.txt"
PRED_MD5 = md5(PRED_FILE)
assert PRED_MD5 == "21ab7bd7a3157df7da843f3f0e2b8a8a", PRED_MD5      # 實機前(2026-10-30 02:42:51)量的 md5;實機 02:42:56 開始
_pred = PRED_FILE.read_text(encoding="utf-8")
for _q in ("S1 複製的 Return 送出之前,CALLLOG 沒有 E 0x18890,也沒有 E 0x17aed", "整份紀錄恰好 1 筆;E 0x17aed 為 0 筆",
           "差 ≤ 2000 ms", "平均 HSV 飽和度 ≤ 110", "S5 複製的 Return 送出前最後一張截圖沒有 HUD", "S6 sel_0 截圖上出現索爾的標頭卡"):
    assert _q in _pred, _q
META = (RAW / "lc169a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG = RAW / "lc169a_CALLLOG.TXT"
CL_MD5 = "62f7fb794580a40befef7673d69a12fa"
assert META[0].split() == [CL_MD5, "CALLLOG.TXT"] and META[1].split() == [MD5, "FD2.EXE"] and md5(CALLLOG) == CL_MD5
_cl = CALLLOG.read_bytes()
assert _cl.count(b"\n") == int(META[2]) == 99562
assert META[3] == "H fd2calllog 1 cs=0170 entries=28 cap=100000000 dump=0 lo=001ad7e7 hi=001df271 icount=1", META[3]
DELTA = 0x19C000
LOOP, SELECT, STATUS_CARD = 0x117E7, 0x18890, 0x17AED
_e168 = (ROOT / ".wsl_build" / "lc168_live" / "lc168a_meta.txt").read_text(encoding="utf-8").splitlines()[4].split()
assert sorted(set(META[4].split()) - set(_e168)) == sorted(f"{a + DELTA:x}" for a in (SELECT, STATUS_CARD)) and len(META[4].split()) == 28
MK = {}
for m in re.finditer(rb"^([ERA]) (\d+) ([0-9a-f]{8}) [^\n]* t=([0-9.]+)\n", _cl, re.M):
    e = int(m.group(3), 16) - DELTA
    if e in (LOOP, SELECT, STATUS_CARD):
        MK.setdefault((m.group(1).decode(), e), []).append(float(m.group(4)))
MKN = {f"{k} {e:#x}": len(v) for (k, e), v in sorted(MK.items())}
assert MKN == {"E 0x117e7": 1, "E 0x18890": 1}, MKN                   # 狀態卡 0 筆;0x18890 沒有 R(到 teardown 還在選格裡)
T_LOOP, T_SEL = MK[("E", LOOP)][0], MK[("E", SELECT)][0]
RUN = json.loads((RAW / "lc169a_run.json").read_text(encoding="utf-8"))
assert RUN["ok"] and RUN["runner"]["ok"] and RUN["loop_E_base"] == 0
REP = RUN["replica"]
assert REP == {"frame": 64, "t_host_press": 1793299462.437, "pre_frame_hud": True, "pre_frame_panel": False,
               "trigger": "loop_E", "dialogue_returns_before": 25}, REP
FR = RUN["frames"]
assert len(FR) == 65 and sum(f.get("pressed", False) for f in FR) == 25 and all(f["loop_E"] == 0 for f in FR[:64])
assert all(f.get("pressed", False) == f["panel"] for f in FR[:64])           # 清對話只在面板上按
H_AFTER, T_AFTER = RUN["marks"]["after_press"]
# 送鍵開始的模擬器時刻:以送鍵後的尾端讀數換算(讀數落後 ≤ (A) 的上界,模擬器 / 主機同速見續一百六十七)
T_PRESS = round(T_AFTER - (H_AFTER - REP["t_host_press"]) * 1000, 1)
T_LAST_DIALOGUE = round(T_AFTER - (H_AFTER - FR[61]["t_host"]) * 1000, 1)   # 最後一次清對話 Return(第 61 張)之後讀檔完成的時刻
assert FR[61].get("pressed") and not any(f.get("pressed") for f in FR[62:])
TIMES = {"E_loop": round(T_LOOP, 1), "press_send_start": T_PRESS, "E_select": round(T_SEL, 1), "after_press_tail": T_AFTER,
         "last_dialogue_frame": T_LAST_DIALOGUE}
assert TIMES == {"E_loop": 81277.4, "press_send_start": 81643.2, "E_select": 81686.2, "after_press_tail": 81828.0948,
                 "last_dialogue_frame": 80071.2}, TIMES
assert T_LOOP < T_PRESS < T_SEL and T_SEL - T_PRESS > LAG_MAX          # 選格在送鍵開始之後(差距大於讀數落後上界)
SAT = {n: round(ImageStat.Stat(Image.open(RAW / "frames" / f"{n}.png").convert("HSV").crop((360, 215, 824, 520))).mean[1], 1)
       for n in ("c064", "sel_0", "sel_up")}
assert SAT == {"c064": 161.9, "sel_0": 102.1, "sel_up": 110.8}, SAT
assert RUN["sel_0"]["sat"] == SAT["sel_0"] and RUN["sel_up"]["sat"] == SAT["sel_up"]
S6_MANUAL = "sel_0:左上標頭卡「索爾 LV·06 HP 823 MP 805」,移動範圍外的地圖變暗(人工比對截圖)"
VERDICT = {
    "S1_no_select_before_replica": "PASS" if MKN.get("E 0x17aed", 0) == 0 and T_SEL > T_PRESS else "FAIL",
    "S2_one_select_no_status_card": "PASS" if MKN["E 0x18890"] == 1 and "E 0x17aed" not in MKN and RUN["after"]["select_E"] == 1 else "FAIL",
    "S3_first_half_after_loop": "PASS" if T_SEL > T_LOOP else "FAIL",
    "S3_second_half_vs_pre_press_tail": "NOT TESTED",                 # 驅動沒有在送鍵前讀尾端(與預測的寫法不同);換算見 TIMES
    "S4_sat_le_110": "PASS" if SAT["sel_up"] <= 110 else "FAIL",
    "S5_no_hud_before_replica": "PASS" if not REP["pre_frame_hud"] else "FAIL",
    "S6_sol_header_card": "PASS (MANUAL)",
}
assert VERDICT == {"S1_no_select_before_replica": "PASS", "S2_one_select_no_status_card": "PASS", "S3_first_half_after_loop": "PASS",
                   "S3_second_half_vs_pre_press_tail": "NOT TESTED", "S4_sat_le_110": "FAIL", "S5_no_hud_before_replica": "FAIL",
                   "S6_sol_header_card": "PASS (MANUAL)"}, VERDICT

CONC = {
    "flush": f"lc167a / lc168a 的 9 次尾端讀數,檔尾全在「上一次明確 fflush + k × 4096」上(1 MiB 模型 0 次;"
             f"整份紀錄均勻取的 {NULL['pseudo_reads']} 個假讀數命中 {NULL['hits']} 次)。寫入端 setvbuf 的 buf 是 NULL,實際是 4 KiB 區塊緩衝。",
    "lag": f"讀數落後真實時刻的上界 {min(LAG.values())} .. {LAG_MAX} ms;續一百六十七閒置窗開頭扣 {LEAD_MS_S167} ms,"
           f"窗口開頭至少晚於真實時刻 {MARGIN_MS} ms,P / P2 不必重算。續一百六十八 (D) 的「約每 {S168_CLAIM_S} 秒寫盤」不成立。",
    "hud": f"HUD 邊框樣板 868 個像素:有框那一側吻合率 {GAP['labelled_side_min']},其他 {GAP['other_sides']} 個側別最高 "
           f"{GAP['other_sides_max']}。827 張人工標記(139 張有框)上,只用樣板 0 誤判 0 漏判;舊藍佔比判準誤判 "
           f"{CONF['old_blue_fraction']['fp']}、漏判 {CONF['old_blue_fraction']['fn']};工具先樣板後藍佔比,漏判 0、誤判照舊 "
           f"{CONF['tool_now']['fp']}(保留舊判準的每個 True)。",
    "select": f"lc169a:清對話 Return {REP['dialogue_returns_before']} 次(與 lc168a 相同),E 0x117e7 出現後送一次 Return,"
              f"約 {round(T_SEL - T_PRESS, 1)} ms 後 E 0x18890(選格 / 動作分派),全份恰 1 筆、狀態卡 0x17aed 0 筆、0x18890 沒有返回;"
              f"sel_0 是索爾的標頭卡。輸入迴圈裡、游標在初始位置時按 Return 會選中索爾。送鍵時 HUD 已畫出(S5 FAIL),"
              f"Up 之後飽和度 {SAT['sel_up']}(S4 FAIL,門檻 110)。",
}
for _part, _key in (("9 次尾端讀數", "flush"), ("1 MiB 模型 0 次", "flush"), ("假讀數命中 43 次", "flush"),
                    ("20.04 .. 25.0 ms", "lag"), ("至少晚於真實時刻 975.0 ms", "lag"), ("1.92 秒", "lag"),
                    ("約 43.0 ms 後 E 0x18890", "select"), ("Return 25 次", "select"), ("S5 FAIL", "select"), ("飽和度 110.8", "select"),
                    ("吻合率 1.0", "hud"), ("最高 0.4009", "hud"), ("誤判 75、漏判 34", "hud"), ("漏判 0、誤判照舊 75", "hud")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s169.py"),
    "exe_md5": MD5,
    "flush_model": {"patch": rel(PATCH), "block_bytes": BLOCK, "logs": LOGS, "hits_by_block": MODEL,
                    "lines_since_explicit_flush": GAP_LINES, "null_control": NULL, "chance_all_9": P_CHANCE,
                    "bytes_per_1024_E": BYTES_PER_1024E},
    "lag_upper_bound_ms": LAG,
    "s167_idle_windows": {"lead_ms": LEAD_MS_S167, "max_lag_ms": LAG_MAX, "margin_ms": MARGIN_MS},
    "s168_claim_flush_interval_s": S168_CLAIM_S,
    "hud_frame": {"labels": {"path": rel(LABEL_FILE), "md5": LABEL_MD5, "hud": len(LABEL), "frames": len(ROWS)},
                  "template_px": len(FRAME_PX), "threshold": sw.BATTLE_HUD_FRAME_MATCH_MIN, "gap": GAP,
                  "confusion": CONF, "gained_by_dir": dict(GAINED), "side": SIDE},
    "select_live": {"approval": "使用者 2026-10-29「永遠核准你進行實機」;2026-10-30「依照你的建議自動繼續進行處理」;"
                                "不改記憶體、不下斷點、不進除錯器",
                    "prediction_file": {"path": rel(PRED_FILE), "md5": PRED_MD5}, "calllog": rel(CALLLOG), "calllog_md5": CL_MD5,
                    "markers": MKN, "times_ms": TIMES, "replica": REP, "saturation": SAT, "s6_manual": S6_MANUAL},
    "predictions": VERDICT,
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, LAG_MAX, GAP, CONF["tool_now"])
