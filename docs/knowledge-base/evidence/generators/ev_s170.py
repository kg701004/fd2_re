"""續一百七十證據:evidence/followups_s170_20261030.json(CALLLOG 緩衝實測、敵方回合 MDI 型重入、P 之前 5 次未歸類重入、HUD 樣板在其他章節)。

使用者 2026-10-30「依照你的建議自動繼續進行處理」(續一百六十九 / 一百六十七的仍留;不跑實機)。
(A) CALLLOG 的 4 KiB 區塊緩衝(續一百六十九由寫盤位置推得):drivers_s170/setvbuf_probe.py 在 WSL 對 DOSBox-X 連結的同一份 glibc
    照 CALLLOG 的寫法 setvbuf(NULL, _IOFBF, 1 MiB),逐筆看檔案大小;輸出 drivers_s170/setvbuf_probe_out.txt 逐行核對。
(B) 敵方回合 MDI 型重入每千格 16.28 次(其他時段 4.6 .. 5.1):lc167a 每次 MDI 服務(0x43270,120 Hz)有沒有叫驅動,
    逐次對齊章節曲表(0x51e63 基本曲 / 0x51e81 敵方回合曲;battle_phase_advance 在呼叫 0x1d8ba 前後換曲)指到的 FDMUS 曲的
    事件 tick。對照:換成另一首曲、全部判成「沒叫」。另算每次驅動呼叫被計時器中斷撞上的比例。
(C) P 之前 5 次未歸類重入:插斷點與 DIG 型相同(外層 DIG 進入後 229 條非遊戲指令),之後的指令數由 ISR 派送迴圈的靜態路徑推出;
    AIL 鎖([0x52bea] > 0)期間沒派送的 tick 由下一次 ISR 補叫 DIG。
(D) HUD 邊框樣板在校準集沒涵蓋的章節:drivers_s170/uncovered_frames.txt(.wsl_build 下路徑標記為其他 20 章的 1024x768 截圖,
    依像素去重)逐張算樣板吻合率與舊藍佔比判準;兩者不一致的與抽樣的人工判讀在 drivers_s170/hud_labels_s170.txt。
    工具(續一百七十只看樣板)在這些截圖上的判定也一併核對。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import re
import sys

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, _META, dl, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import warnings  # noqa: E402
import xmi2mid  # noqa: E402
warnings.filterwarnings("ignore", category=DeprecationWarning)      # Pillow getdata 的棄用警告
import fd2_chapter_sweep as sw  # noqa: E402
from PIL import Image  # noqa: E402

OUT = out_path("followups_s170_20261030.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DRV = GEN_DIR / "drivers_s170"
RAW = ROOT / ".wsl_build" / "lc167_live"
FDMUS = ROOT / "extracted" / "raw" / "FDMUS"
DELTA = 0x19C000
S164 = json.loads((EVIDENCE / "interrupt_off_sections_s164_20261029.json").read_text(encoding="utf-8"))
S167 = json.loads((EVIDENCE / "battle_turn_interrupt_loss_s167_20261029.json").read_text(encoding="utf-8"))
S169 = json.loads((EVIDENCE / "driver_followups_s169_20261030.json").read_text(encoding="utf-8"))
ISR, REENTRY, DIG, MDI = 0x3EA8E, 0x3EBAD, 0x404C0, 0x43270
LOOP_CALL_RET = 0x3EB42                 # ISR 派送迴圈 call [edi + 0x2a54] 的返回點
EPI = 0x3EB9D
PLAY_BGM, ENEMY_PHASE = 0x25977, 0x1D8BA
S161 = json.loads((EVIDENCE / "timer_base_and_delay_slowdown_s161_20261028.json").read_text(encoding="utf-8"))
PIT_MS = S161["timer_channels"]["pit_divisor"] / 1193182 * 1000
FADE_STEP = 8                           # 換曲前後多出的驅動呼叫的間隔(MDI 服務次數)

# ================= (A) CALLLOG 緩衝:WSL 實測 =================
PROBE_TXT = (DRV / "setvbuf_probe_out.txt").read_text(encoding="utf-8").splitlines()
assert PROBE_TXT[0] == ("glibc 2.39; probe libc /usr/lib/x86_64-linux-gnu/libc.so.6; "
                        "dosbox-x libc /usr/lib/x86_64-linux-gnu/libc.so.6; same=True"), PROBE_TXT[0]
_m = re.fullmatch(r"testdir st_dev=(\d+) home st_dev=(\d+) st_blksize=(\d+); harness dirs (\d+) same_fs=True", PROBE_TXT[1])
assert _m and _m.group(1) == _m.group(2), PROBE_TXT[1]
BLK = int(_m.group(3))
SIZES = {}
for ln in PROBE_TXT[2:8]:
    mm = re.fullmatch(r"(\w+): (phase[01]) sizes \[([\d, ]+)\]", ln)
    assert mm, ln
    SIZES[(mm.group(1), mm.group(2))] = [int(v) for v in mm.group(3).split(", ")]
FLUSH_AT = 20000                        # 探針第一段後明確 fflush 的位置(setvbuf_probe.py 的 FLUSH_AT)
assert "FLUSH_AT = 20000" in (DRV / "setvbuf_probe.py").read_text(encoding="utf-8")


def on_grid(v: list[int], base: int, step: int) -> bool:
    return all(x >= base and (x - base) % step == 0 for x in v)


PROBE = {
    "null_1MiB_blocks": on_grid(SIZES[("null_1MiB", "phase0")], 0, BLK) and len(SIZES[("null_1MiB", "phase0")]) >= 4,
    "null_1MiB_after_fflush": on_grid(SIZES[("null_1MiB", "phase1")], FLUSH_AT, BLK) and len(SIZES[("null_1MiB", "phase1")]) >= 4,
    "same_as_default": all(SIZES[("null_1MiB", p)] == SIZES[("default", p)] for p in ("phase0", "phase1")),
    "control_real_1MiB_no_write": SIZES[("buf_1MiB", "phase0")] == [0] and SIZES[("buf_1MiB", "phase1")] == [FLUSH_AT],
}
assert all(PROBE.values()) and PROBE_TXT[-1] == "PASS" and sum(ln.startswith("PASS ") for ln in PROBE_TXT) == 6, PROBE
assert BLK == S169["flush_model"]["block_bytes"] == 4096                     # 續一百六十九由寫盤位置推得的區塊大小

# ================= lc167a 原始紀錄 =================
META = (RAW / "lc167a_meta.txt").read_text(encoding="utf-8").splitlines()
_raw = (RAW / "lc167a_CALLLOG.TXT").read_bytes()
CALLLOG_MD5 = hashlib.md5(_raw).hexdigest()
assert META[0].split() == [CALLLOG_MD5, "CALLLOG.TXT"] and CALLLOG_MD5 == "ac9401da607102caa569be467c178b92"
REC = []                                # (k, seq, eip, i, n, t, E 的返回位址 / A 的所在位址, E 的 edi)
for ln in _raw.decode("ascii").splitlines()[1:]:
    p = ln.split()
    if not p or p[0] not in ("E", "R", "A"):
        continue
    kv = dict(x.split("=", 1) for x in p if "=" in x)
    if "t" not in kv:
        continue
    e = p[0] == "E"
    REC.append((p[0], p[1], int(p[2], 16) - DELTA, int(kv["i"]), int(kv["n"]), float(kv["t"]),
                int(p[3].rstrip("?"), 16) - DELTA if p[0] in "EA" else None, int(p[11], 16) if e else None))
del _raw
WIN = {k: tuple(v) for k, v in S167["windows_ms"].items()}

# ================= (B) MDI 服務對齊曲子 =================
# MDI 服務的每一次進入(都由派送迴圈呼叫);有 R 的看非遊戲指令數,沒有 R 的另外核對
_open: dict[str, int] = {}
CALLS: list[list] = []                  # [t, drv(None = 沒有 R), k_E]
for k, r in enumerate(REC):
    if r[2] != MDI:
        continue
    if r[0] == "E":
        assert r[6] == LOOP_CALL_RET and r[7] == 0, r                       # MDI 是派送表第 0 格
        _open[r[1]] = len(CALLS)
        CALLS.append([r[5], None, k])
    elif r[0] == "R" and r[1] in _open:
        c = CALLS[_open.pop(r[1])]
        e = REC[c[2]]
        c[1] = (r[4] - e[4]) - (r[3] - e[3])
UNCLOSED = [c for c in CALLS if c[1] is None]


def kind(k: int) -> str:
    """續一百六十七 ev_s167 的重入分型(指令數 = 續一百六十四 / 一百六十五的預測)。"""
    r, q = REC[k], REC[k + 1]
    d = q[3] - r[3]
    if q[0] == "A" and q[2] == REENTRY and d == {EPI: 93, 0x3EB69: 94}.get(q[6]):
        return "DIG"
    if q[0] == "E" and q[2] == DIG and d == 62:
        return "MDI"
    if q[0] == "E" and q[2] == MDI and d == 57:
        return "MDI_AGAIN"
    return "other"


RE_K = [k for k, r in enumerate(REC) if r[0] == "E" and r[2] == REENTRY]
KIND = {k: kind(k) for k in RE_K}
# 沒有 R 的 MDI 服務 = MDI 型重入:每一次 MDI / MDI_AGAIN 型重入之前最近的 MDI 進入都沒有 R,反之亦然
_mdi_re = [k for k in RE_K if KIND[k] in ("MDI", "MDI_AGAIN")]
_prev_mdi = []
for k in _mdi_re:
    j = k - 1
    while not (REC[j][0] == "E" and REC[j][2] == MDI):
        j -= 1
    _prev_mdi.append(j)
assert sorted(_prev_mdi) == sorted(c[2] for c in UNCLOSED) and len(UNCLOSED) == len(_mdi_re) == 604
for c in UNCLOSED:                                                          # 它們都進過驅動(重入之前已有非遊戲指令)
    k = next(k for k in range(c[2] + 1, len(REC)) if REC[k][0] == "E" and REC[k][2] in (ISR, REENTRY))
    assert (REC[k][4] - REC[c[2]][4]) - (REC[k][3] - REC[c[2]][3]) > 0
DRVCALL = [c[1] is None or c[1] > 0 for c in CALLS]
T = [c[0] for c in CALLS]

# 靜態:battle_phase_advance(0x1a30b)在呼叫敵方回合 0x1d8ba 之前換成 0x51e81[章],之後換回 0x51e63[章]
STATIC = {
    0x1A507: "movzx ebx, byte ptr [eax + 0x1e63]", 0x1A50E: "movzx eax, byte ptr [eax + 0x1e81]",
    0x1A519: "push 0", 0x1A51B: "push -1", 0x1A51D: f"call {PLAY_BGM:#x}",
    0x1A57A: "movzx eax, byte ptr [eax + 0x1e81]", 0x1A581: "push eax", 0x1A582: f"call {PLAY_BGM:#x}",
    0x1A58F: f"call {ENEMY_PHASE:#x}",
    0x1A5C3: "push 0", 0x1A5C5: "push -1", 0x1A5C7: f"call {PLAY_BGM:#x}",
    0x1A610: "movzx eax, byte ptr [eax + 0x1e63]", 0x1A617: "push eax", 0x1A618: f"call {PLAY_BGM:#x}",
}
assert len(STATIC) == 15                                                    # 位址鍵沒有重複
for a, txt in STATIC.items():
    assert insn(a) == txt, (hex(a), insn(a), txt)
TAB_BASE = dl.object_bytes(_EXE, _META, 0x51E63, 30)
TAB_ENEMY = dl.object_bytes(_EXE, _META, 0x51E81, 30)
# 實機 patch_chapter 把章節位元組設 1;0 起算或 1 起算都落在同一組曲號
TRACKS = {"base": TAB_BASE[1], "enemy": TAB_ENEMY[1]}
assert (TAB_BASE[0], TAB_ENEMY[0]) == (TAB_BASE[1], TAB_ENEMY[1]) and TRACKS == {"base": 0x13, "enemy": 0x0C}, TRACKS


def song(n: int) -> dict:
    """FDMUS_<n>.bin 的 XMIDI:送驅動的事件(非 meta)所在 tick、最後一個 tick。"""
    d = (FDMUS / f"FDMUS_{n:03d}.bin").read_bytes()
    (timb, eo, el), = xmi2mid.find_evnt_timb(d)
    ev, st = xmi2mid.parse_evnt(d, eo, el)
    return {"ticks": {t for t, mb in ev if mb[0] != 0xFF}, "max_tick": st["max_tick"], "md5": hashlib.md5(d).hexdigest()}


SONG = {n: song(n) for n in (TRACKS["base"], TRACKS["enemy"])}
DENSITY = {n: round(len(s["ticks"]) / (s["max_tick"] + 1), 4) for n, s in SONG.items()}


def pattern(n: int, period: int) -> bytes:
    return bytes(1 if t in SONG[n]["ticks"] else 0 for t in range(period))


def match(js: range, n: int, period: int, o: int) -> int:
    """序號 js 的 MDI 服務裡,「有沒有叫驅動」與曲 n(週期 period、第 o 次服務是第 0 tick)相符的次數。"""
    pat = pattern(n, period)
    rep = pat * (len(js) // period + 2)
    r = (js[0] - o) % period
    a = int.from_bytes(bytes(DRVCALL[j] for j in js), "big")
    b = int.from_bytes(rep[r:r + len(js)], "big")
    return len(js) - (a ^ b).bit_count()


def scan(js: range, n: int) -> list[tuple[int, int, int]]:
    """週期 max_tick 與 max_tick + 1 的所有起點,依相符次數排序。"""
    out = []
    for period in (SONG[n]["max_tick"], SONG[n]["max_tick"] + 1):
        pat = pattern(n, period)
        rep = pat * (len(js) // period + 2)
        a = int.from_bytes(bytes(DRVCALL[j] for j in js), "big")
        for o in range(period):
            r = (js[0] - o) % period
            out.append((len(js) - (a ^ int.from_bytes(rep[r:r + len(js)], "big")).bit_count(), o, period))
    out.sort(reverse=True)
    return out


def idx(a: float, b: float) -> range:
    js = [j for j in range(len(CALLS)) if a <= T[j] < b]
    assert js == list(range(js[0], js[-1] + 1))
    return range(js[0], js[-1] + 1)


ALIGN = {}
for nm, n, ctrl in (("P", 0x13, 0x0C), ("S_ring", 0x13, 0x0C), ("P2_loop", 0x13, 0x0C), ("EN", 0x0C, 0x13)):
    js = idx(*WIN[nm])
    sc = scan(js, n)
    best = sc[0]
    ALIGN[nm] = {"song": n, "services": len(js), "best": {"match": best[0], "offset": best[1], "period": best[2]},
                 "second_best_match": sc[1][0], "all_false_match": sum(not DRVCALL[j] for j in js),
                 "other_song_best_match": scan(js, ctrl)[0][0]}
for nm in ("P", "S_ring", "P2_loop"):
    a = ALIGN[nm]
    assert a["best"]["match"] == a["services"] and a["best"]["period"] == SONG[0x13]["max_tick"] + 1, (nm, a)
# P 與 S_ring 同一個起點(中間 360 秒連續播放);diag 只用這個起點核對
assert ALIGN["P"]["best"]["offset"] == ALIGN["S_ring"]["best"]["offset"]
assert {k: (v["best"]["offset"], v["second_best_match"], v["all_false_match"], v["other_song_best_match"]) for k, v in ALIGN.items()} == {
    "P": (1617, 3394, 3203, 2550), "S_ring": (1617, 4638, 4380, 3480), "P2_loop": (866, 2452, 2315, 1853),
    "EN": (276, 2582, 2326, 2250)}, ALIGN
_jd = idx(*WIN["diag"])
DIAG = {"services": len(_jd), "match": match(_jd, 0x13, ALIGN["P"]["best"]["period"], ALIGN["P"]["best"]["offset"])}
_pd = pattern(0x13, ALIGN["P"]["best"]["period"])
DIAG["extra"] = [(round(T[j], 1), CALLS[j][1]) for j in _jd
                 if DRVCALL[j] != _pd[(j - ALIGN["P"]["best"]["offset"]) % ALIGN["P"]["best"]["period"]]]
assert DIAG["match"] == DIAG["services"] - 1 and DIAG["extra"] == [(119237.6, 532)], DIAG    # 唯一不符是一次多叫的短驅動呼叫
EN = ALIGN["EN"]
assert EN["best"]["period"] == SONG[0x0C]["max_tick"] + 1 and EN["services"] - EN["best"]["match"] == 26, EN
for nm, a in ALIGN.items():
    miss = {k: a["services"] - a[k] for k in ("second_best_match", "other_song_best_match", "all_false_match")}
    miss_best = a["services"] - a["best"]["match"]
    # 次佳起點(曲子內部重複的段落)至少多錯 16 次;另一首曲、全部判成沒叫至少多錯服務次數的 5%
    assert miss["second_best_match"] >= max(16, 10 * miss_best), (nm, miss, miss_best)
    assert min(miss["other_song_best_match"], miss["all_false_match"]) - miss_best >= 0.05 * a["services"], (nm, miss, miss_best)
# EN 的 26 個不符:全是「多叫了」;開頭 2.5 秒內 23 個落在同一個 8 次服務的相位上,另 3 個是很短的驅動呼叫
_js = idx(*WIN["EN"])
_pat = pattern(0x0C, EN["best"]["period"])
EN_EXTRA = [j for j in _js if DRVCALL[j] != _pat[(j - EN["best"]["offset"]) % EN["best"]["period"]]]
assert all(DRVCALL[j] for j in EN_EXTRA)
_res = collections.Counter(j % FADE_STEP for j in EN_EXTRA)
_r0, _n0 = _res.most_common(1)[0]
_fade = [j for j in EN_EXTRA if j % FADE_STEP == _r0]
_rest = [j for j in EN_EXTRA if j % FADE_STEP != _r0]
EN_EXTRA_SUM = {"on_one_phase_of_8": _n0, "phase_span_ms": [round(T[_fade[0]], 1), round(T[_fade[-1]], 1)],
                "others": [(round(T[j], 1), CALLS[j][1]) for j in _rest]}
assert _n0 == 23 and T[_fade[-1]] - WIN["EN"][0] < 2500 and EN_EXTRA_SUM["others"] == [
    (540499.0, 558), (542774.0, 558), (542959.0, 558)], EN_EXTRA_SUM

assert EN_EXTRA_SUM["phase_span_ms"] == [538088.9, 540079.0], EN_EXTRA_SUM
# 換曲過渡:友軍回合結束 → 敵方回合開始(基本曲照常 + 每 8 次服務多叫一次);敵方回合結束 → 主迴圈(兩首都對不上,未解)
GAP1 = idx(WIN["S_friend"][1], WIN["EN"][0])
_pb = pattern(0x13, ALIGN["P"]["best"]["period"])
_pred = {j: _pb[(j - ALIGN["P"]["best"]["offset"]) % ALIGN["P"]["best"]["period"]] for j in GAP1}
_extra1 = [j for j in GAP1 if DRVCALL[j] and not _pred[j]]
_ph1 = collections.Counter(j % FADE_STEP for j in _extra1).most_common(1)[0]
TRANS = {"friend_end_to_enemy": {"services": len(GAP1), "song_events": sum(_pred.values()),
                                 "song_events_called": sum(DRVCALL[j] for j in GAP1 if _pred[j]), "extra": len(_extra1),
                                 "extra_on_one_phase_of_8": _ph1[1],
                                 "extra_span_ms": [round(T[_extra1[0]], 1), round(T[_extra1[-1]], 1)]}}
assert TRANS["friend_end_to_enemy"] == {"services": 553, "song_events": 34, "song_events_called": 34, "extra": 56,
                                        "extra_on_one_phase_of_8": 55, "extra_span_ms": [533408.9, 537363.9]}, TRANS
GAP2 = idx(WIN["EN"][1], WIN["P2_loop"][0])
_g2 = {"services": len(GAP2), "called": sum(DRVCALL[j] for j in GAP2)}
for nm, n in (("base_song_best", 0x13), ("enemy_song_best", 0x0C)):
    _g2[nm] = scan(GAP2, n)[0][0]
_g2["all_false"] = _g2["services"] - _g2["called"]
TRANS["enemy_end_to_loop"] = _g2
assert _g2 == {"services": 991, "called": 230, "base_song_best": 776, "enemy_song_best": 822, "all_false": 761}, _g2
assert max(_g2["base_song_best"], _g2["enemy_song_best"]) <= 0.9 * _g2["services"], _g2    # 真的對上時是 ≥ 99%

# 每秒驅動呼叫次數、每次驅動呼叫被計時器中斷撞上的比例
RATE = {}
for nm in ("P", "diag", "S_ring", "S_adv", "EN", "P2_loop"):
    js = idx(*WIN[nm])
    sec = (WIN[nm][1] - WIN[nm][0]) / 1000
    calls = sum(DRVCALL[j] for j in js)
    hit = sum(1 for j in js if CALLS[j][1] is None)
    RATE[nm] = {"services": len(js), "driver_calls": calls, "driver_calls_per_s": round(calls / sec, 2),
                "mdi_reentry": hit, "hit_per_driver_call": round(hit / calls, 4)}
    s167_types = S167["segments"][nm]["types"]
    assert hit == s167_types["MDI"] + s167_types["MDI_AGAIN"], (nm, hit, s167_types)   # 與續一百六十七的分型同數
_rest_calls = sum(RATE[n]["driver_calls"] for n in RATE if n != "EN")
_rest_hit = sum(RATE[n]["mdi_reentry"] for n in RATE if n != "EN")


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """2×2 表 [[a, b], [c, d]] 的 Fisher 精確檢定(雙尾,機率不大於觀測值者相加)。"""
    r1, c1, n = a + b, a + c, a + b + c + d
    den = math.comb(n, c1)

    def pr(x: int) -> float:
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / den
    p0 = pr(a)
    return sum(pr(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if pr(x) <= p0 * (1 + 1e-9))


HIT = {"EN": [RATE["EN"]["mdi_reentry"], RATE["EN"]["driver_calls"]], "rest": [_rest_hit, _rest_calls],
       "fisher_p": round(fisher_two_sided(RATE["EN"]["mdi_reentry"], RATE["EN"]["driver_calls"] - RATE["EN"]["mdi_reentry"],
                                          _rest_hit, _rest_calls - _rest_hit), 3)}
RATIO = {"driver_calls_EN_over_P": round(RATE["EN"]["driver_calls_per_s"] / RATE["P"]["driver_calls_per_s"], 2),
         "mdi_per_1000_slots_EN_over_others_max": round(S167["segments"]["EN"]["mdi_per_1000_slots"] / max(
             S167["segments"][n]["mdi_per_1000_slots"] for n in ("P", "S", "P2")), 2),
         "song_density_enemy_over_base": round(DENSITY[0x0C] / DENSITY[0x13], 2)}
assert HIT == {"EN": [85, 718], "rest": [457, 3528], "fisher_p": 0.462}, HIT
assert RATIO == {"driver_calls_EN_over_P": 3.73, "mdi_per_1000_slots_EN_over_others_max": 3.34,
                 "song_density_enemy_over_base": 3.65}, RATIO
assert {k: (v["driver_calls_per_s"], v["hit_per_driver_call"]) for k, v in RATE.items()} == {
    "P": (7.38, 0.128), "diag": (7.42, 0.1323), "S_ring": (7.4, 0.1276), "S_adv": (10.4, 0.089), "EN": (27.51, 0.1184),
    "P2_loop": (7.4, 0.1373)}, RATE
assert DENSITY == {0x13: 0.0621, 0x0C: 0.2269}, DENSITY

# ================= (C) P 之前 5 次未歸類重入 =================
OTHER_K = [k for k in RE_K if KIND[k] == "other"]
assert [round(REC[k][5], 3) for k in OTHER_K] == [o["t"] for o in S167["unclassified_before_P"]]
# 派送表的格:MDI 第 0 格(edi 0)、DIG 第 1 格(edi 4)
SLOT = collections.Counter((REC[k][2], REC[k][7]) for k in range(len(REC))
                           if REC[k][0] == "E" and REC[k][2] in (DIG, MDI) and REC[k][6] == LOOP_CALL_RET)
assert set(SLOT) == {(MDI, 0), (DIG, 4)}, SLOT
DIG_EDI = 4
# 靜態路徑:DIG 返回(0x3eb42)之後到 0x3eb9d(派送表空了、不轉 BIOS)與到下一次 DIG 進入(同格計數還 > 0)的指令數
assert insn(0x3EB44) == "jmp 0x3eb24" and insn(0x3EB2B) == "je 0x3eb46" and insn(0x3EB4C) == "jb 0x3eb24"
assert insn(0x3EB49) == "cmp edi, 0x3c" and insn(0x3EB55) == "je 0x3eb91" and insn(0x3EB3C) == "call dword ptr [edi + 0x2a54]"
_slots_left = (0x3C - DIG_EDI) // 4
PATH_END = [0x3EB42, 0x3EB44] + [0x3EB24, 0x3EB2B, 0x3EB46, 0x3EB49, 0x3EB4C] * _slots_left + [0x3EB4E, 0x3EB55, 0x3EB91, 0x3EB97, EPI]
PATH_AGAIN = [0x3EB42, 0x3EB44, 0x3EB24, 0x3EB2B, 0x3EB2D, 0x3EB33, 0x3EB35, 0x3EB3B, 0x3EB3C, DIG]
for a in set(PATH_END + PATH_AGAIN) - {DIG}:
    assert insn(a)                                                          # 每個位址都是指令起點
D_DIG = S164["interrupt_off"]["predicted_di"]["dig_restore"][hex(EPI)]
D_AGAIN = D_DIG - len(PATH_END) + len(PATH_AGAIN)
assert (D_DIG, len(PATH_END), len(PATH_AGAIN), D_AGAIN) == (93, 77, 10, 26)


def outer_dig(k: int) -> int:
    j = k - 1
    while not (REC[j][0] == "E" and REC[j][2] in (DIG, MDI) and REC[j][6] == LOOP_CALL_RET):
        j -= 1
    return j


def nongame(a: int, b: int) -> int:
    return (REC[b][4] - REC[a][4]) - (REC[b][3] - REC[a][3])


# 插斷點:外層 DIG 進入到重入之間的非遊戲指令數;DIG 型重入的分佈作對照
NG_DIG = collections.Counter(nongame(outer_dig(k), k) == 229 for k in RE_K if KIND[k] == "DIG" and REC[outer_dig(k)][2] == DIG)
CASES = []
for k in OTHER_K:
    j = outer_dig(k)
    q = REC[k + 1]
    c = {"t": round(REC[k][5], 3), "outer": f"E {REC[j][2]:#x}", "nongame_before": nongame(j, k), "next": f"{q[0]} {q[2]:#x}",
         "di_next": q[3] - REC[k][3]}
    if q[0] == "E" and q[2] == DIG:
        c["next_ret"] = hex(q[6])
        c["kind"] = "DIG_AGAIN" if c["di_next"] == D_AGAIN and q[6] == LOOP_CALL_RET else "?"
    elif q[0] == "E" and q[2] == ISR:
        r2 = REC[k + 2]
        tail = next(x for x in REC[k + 3:k + 12] if x[0] == "A" and x[2] == REENTRY)
        c.update({"second_reentry_di": r2[3] - REC[k][3], "nongame_until_second": nongame(k, k + 1),
                  "second_to_epi": tail[3] - r2[3]})
        c["kind"] = "DIG_DOUBLE" if r2[2] == REENTRY and tail[3] - r2[3] == D_DIG else "?"
    CASES.append(c)
assert [c["kind"] for c in CASES] == ["DIG_AGAIN", "DIG_DOUBLE", "DIG_AGAIN", "DIG_AGAIN", "DIG_AGAIN"], CASES
assert all(c["outer"] == f"E {DIG:#x}" and c["nongame_before"] == 229 for c in CASES)
assert [(c["t"], c["next"], c.get("next_ret"), c.get("second_reentry_di")) for c in CASES] == [
    (12755.406, "E 0x404c0", "0x3eb42", None), (21506.01, "E 0x3ea8e", None, 7), (70304.844, "E 0x404c0", "0x3eb42", None),
    (80574.992, "E 0x404c0", "0x3eb42", None), (84364.72, "E 0x404c0", "0x3eb42", None)], CASES
assert NG_DIG == {True: 401, False: 15}, NG_DIG

# AIL 鎖:ISR 一進入就把 DIG 的計數 +1(週期 = 計時器基準),鎖住時([0x52bea] > 0)跳過派送;下一次 ISR 補叫
assert insn(0x3EB16) == "cmp dword ptr [0x2bea], 0" and insn(0x3EB1D) == "jg 0x3eb4e"
OUTER = []                              # [t, [服務...], 有沒有重入]
for k, r in enumerate(REC[:-1]):
    if r[0] == "E" and r[2] == ISR and not (REC[k + 1][0] == "E" and REC[k + 1][2] == REENTRY):
        OUTER.append([r[5], []])
    elif r[0] == "E" and r[2] in (DIG, MDI) and r[6] == LOOP_CALL_RET and OUTER:
        OUTER[-1][1].append("DIG" if r[2] == DIG else "MDI")
FIRST_DIG_T = next(r[5] for r in REC if r[0] == "E" and r[2] == DIG)
LOCK_RUNS = []
_i = 0
while _i < len(OUTER):
    if OUTER[_i][1]:
        _i += 1
        continue
    j = _i
    while j < len(OUTER) and not OUTER[j][1]:
        j += 1
    nxt = OUTER[j]
    LOCK_RUNS.append({"t": round(OUTER[_i][0], 2), "skipped": j - _i, "next_t": round(nxt[0], 2), "next_dig": nxt[1].count("DIG"),
                      "after_first_dig": nxt[0] > FIRST_DIG_T})
    _i = j
_after = [r for r in LOCK_RUNS if r["after_first_dig"]]
assert len(LOCK_RUNS) == 9 and len(_after) == 7 and all(r["next_dig"] == 1 + r["skipped"] for r in _after), LOCK_RUNS
assert [(r["t"], r["skipped"], r["next_t"], r["next_dig"]) for r in LOCK_RUNS] == [
    (3022.57, 4, 3176.95, 0), (3185.29, 2, 3200.83, 1), (3310.86, 2, 3320.83, 3), (12741.03, 1, 12745.97, 2),
    (15776.05, 3, 15791.02, 4), (24151.18, 1, 24156.18, 2), (70291.89, 1, 70296.84, 2), (80562.04, 1, 80566.99, 2),
    (84347.07, 1, 84352.05, 2)], LOCK_RUNS
_multi = [o for o in OUTER if o[1].count("DIG") >= 2]
assert sorted(round(o[0], 2) for o in _multi) == sorted(r["next_t"] for r in _after)    # 補叫只出現在鎖之後
# DIG_AGAIN 那 4 次的外層 ISR(第一次 DIG 之前最近的外層 ISR)都是補叫的 ISR
_again_outer = [max(o[0] for o in OUTER if o[0] <= REC[outer_dig(k)][5])
                for k, c in zip(OTHER_K, CASES) if c["kind"] == "DIG_AGAIN"]
CATCHUP = {"lock_runs": LOCK_RUNS, "catchup_isr": len(_multi),
           "catchup_isr_with_again_reentry": sum(1 for o in _multi if o[0] in _again_outer)}
assert CATCHUP["catchup_isr"] == 7 and CATCHUP["catchup_isr_with_again_reentry"] == 4 == len(_again_outer), CATCHUP

# DIG_DOUBLE:第一次插斷晚了 4.909 ms(比其他 416 次 DIG 型都晚),0.17 ms 後下一個 tick 又進來
_isr_t = [r[5] for r in REC if r[0] == "E" and r[2] == ISR]
_g0 = max(t for t in _isr_t if t <= FIRST_DIG_T)


def late(t: float) -> float:
    return round((t - _g0) % PIT_MS, 3)


_dbl = OTHER_K[1]
LATE = {"double_first": late(REC[_dbl][5]), "double_second": late(REC[_dbl + 2][5]),
        "dig_type_max": max(late(REC[k][5]) for k in RE_K if KIND[k] == "DIG" and k != _dbl + 2),
        "gap_ms": round(REC[_dbl + 2][5] - REC[_dbl][5], 3)}
assert LATE == {"double_first": 4.909, "double_second": 0.074, "dig_type_max": 4.74, "gap_ms": 0.166}, LATE
assert CASES[1]["nongame_until_second"] == 748 and CASES[1]["second_to_epi"] == D_DIG

# ================= (D) HUD 邊框樣板在校準集沒涵蓋的章節 =================
CALIB = (GEN_DIR / "drivers_s168" / "calib_frames.txt").read_text(encoding="utf-8").split()


def chapter_tag(p: str) -> int | None:
    """路徑裡最後一個 chNN 的數字(檔名 / 目錄名上的章節標記;沒有就 None)。"""
    m = re.findall(r"ch(\d+)", p)
    return int(m[-1]) if m else None


COVERED = sorted({c for c in map(chapter_tag, CALIB) if c is not None})
assert COVERED == [1, 2, 11, 19, 20, 21, 23, 25, 26, 27, 29], COVERED
UNCOV = (DRV / "uncovered_frames.txt").read_text(encoding="utf-8").split()
LAB = {}
for ln in (DRV / "hud_labels_s170.txt").read_text(encoding="utf-8").splitlines():
    if ln and not ln.startswith("#"):
        s, f = ln.split(" ", 1)
        assert s in ("N", "L", "R") and f not in LAB and f in UNCOV, ln
        LAB[f] = s
assert len(UNCOV) == len(set(UNCOV)) == 3015 and not set(UNCOV) & set(CALIB)
FR = []
_pix = set()
for f in UNCOV:
    c = chapter_tag(f)
    assert c is not None and c not in COVERED and c <= 30, f
    im = Image.open(ROOT / f).convert("RGB")
    assert im.size == (1024, 768), f
    h = hashlib.md5(im.tobytes()).hexdigest()
    assert h not in _pix, f                                                   # 清單已依像素去重
    _pix.add(h)
    FR.append({"f": f, "ch": c, "m": {s: sw._hud_frame_match(im, s) for s in "LR"},
               "old": bool(sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION, sw.BATTLE_HUD_RIGHT_STRIP_REGION)
                           or sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION_R, sw.BATTLE_HUD_LEFT_STRIP_REGION_R)),
               "tool": sw._find_hud_box_side(im)})
for r in FR:
    r["tpos"] = max(r["m"].values()) >= sw.BATTLE_HUD_FRAME_MATCH_MIN
TPOS = [r for r in FR if r["tpos"]]
OLD_ONLY = [r for r in FR if r["old"] and not r["tpos"]]
UNC = {"frames": len(FR), "chapters": sorted({r["ch"] for r in FR}), "template_pos": len(TPOS),
       "template_pos_min": min(max(r["m"].values()) for r in TPOS),
       "template_neg_max": round(max(max(r["m"].values()) for r in FR if not r["tpos"]), 4),
       "old_pos": sum(r["old"] for r in FR), "old_only": len(OLD_ONLY), "template_only": sum(1 for r in TPOS if not r["old"]),
       "template_pos_by_ch": dict(sorted(collections.Counter(r["ch"] for r in TPOS).items()))}
assert {k: UNC[k] for k in ("frames", "template_pos", "template_pos_min", "template_neg_max", "old_pos", "old_only", "template_only")} == {
    "frames": 3015, "template_pos": 464, "template_pos_min": 1.0, "template_neg_max": 0.4009, "old_pos": 812, "old_only": 348,
    "template_only": 0}, UNC
assert len(UNC["chapters"]) == 20 and len(UNC["template_pos_by_ch"]) == 18, UNC
# 人工判讀:退回藍佔比多判的 348 張逐張看都沒有框;樣板判有框的抽 66 張都有框、側別相符
assert {r["f"] for r in OLD_ONLY} == {f for f, s in LAB.items() if s == "N"}
_sample = [r for r in FR if LAB.get(r["f"]) in ("L", "R")]
assert len(_sample) == 66 and all(r["tpos"] and r["m"][LAB[r["f"]]] >= sw.BATTLE_HUD_FRAME_MATCH_MIN for r in _sample)
assert len({r["ch"] for r in _sample}) == 18
# 工具(續一百七十只看樣板)在這 3015 張上:有框的那一側 = 樣板那一側,其餘 None;348 張全判 None
assert all(r["tool"] == next((s for s in "LR" if r["m"][s] >= sw.BATTLE_HUD_FRAME_MATCH_MIN), None) for r in FR)
assert all(r["tool"] is None for r in OLD_ONLY)
S169_FP = S169["hud_frame"]["confusion"]["tool_now"]["fp"]
assert S169_FP == 75 and S169["hud_frame"]["confusion"]["frame_only"]["fp"] == 0

CONC = {
    "buffer": f"WSL 實測(glibc 2.39,與 DOSBox-X 同一份 libc、與 harness 目錄同一檔案系統,st_blksize {BLK}):"
              f"setvbuf(NULL, _IOFBF, 1 MiB) 的寫盤位置是 {BLK} 的倍數,明確 fflush 之後是「fflush 位置 + k × {BLK}」,與不呼叫 setvbuf 相同;"
              f"對照組明確給 1 MiB buf 時 40000 位元組都沒寫盤。續一百六十九的 4 KiB 由 INFERRED 改為實測確認。",
    "enemy_mdi": f"敵方回合 MDI 型重入多,是因為換了曲:battle_phase_advance 在呼叫 0x1d8ba 前換成 0x51e81[章] = FDMUS_{TRACKS['enemy']:03d},"
                 f"之後換回 0x51e63[章] = FDMUS_{TRACKS['base']:03d}。每次 MDI 服務有沒有叫驅動,玩家回合 P / S_ring / P2_loop 與 FDMUS_019 的事件 tick "
                 f"逐次相符({ALIGN['P']['services']} / {ALIGN['S_ring']['services']} / {ALIGN['P2_loop']['services']} 次全中;diag {DIAG['match']} / {DIAG['services']},唯一不符是 1 次多叫的短驅動呼叫),"
                 f"敵方回合與 FDMUS_012 相符 {EN['best']['match']} / {EN['services']}(不符 26 次全是多叫:開頭 23 次每 8 次服務一次、另 3 次很短)。"
                 f"驅動呼叫每秒 {RATE['EN']['driver_calls_per_s']} 對 {RATE['P']['driver_calls_per_s']}({RATIO['driver_calls_EN_over_P']} 倍;"
                 f"兩首曲的事件 tick 密度比 {RATIO['song_density_enemy_over_base']});每次驅動呼叫被計時器中斷撞上的比例敵方回合 "
                 f"{HIT['EN'][0]} / {HIT['EN'][1]}、其他 {HIT['rest'][0]} / {HIT['rest'][1]}(Fisher p = {HIT['fisher_p']})。"
                 f"多出來的驅動呼叫全來自曲子本身,曲子以外的只有開頭 {EN_EXTRA_SUM['on_one_phase_of_8']} 次與 {len(EN_EXTRA_SUM['others'])} 次短呼叫,所以不是敵方移動的音效讓驅動變忙。",
    "transition": f"友軍回合結束到敵方回合開始的 {TRANS['friend_end_to_enemy']['services']} 次服務:FDMUS_019 照常({TRANS['friend_end_to_enemy']['song_events']} 個事件全叫),"
                  f"另外多叫 {TRANS['friend_end_to_enemy']['extra']} 次,其中 {TRANS['friend_end_to_enemy']['extra_on_one_phase_of_8']} 次落在同一個 8 次服務的相位上;"
                  f"敵方回合結束到主迴圈的 {_g2['services']} 次服務兩首曲都對不上(未解)。",
    "unclassified": f"P 之前 5 次未歸類重入的插斷點都與 DIG 型相同(外層 DIG 進入後 229 條非遊戲指令;DIG 型 401 / 416 次是 229)。"
                    f"其中 4 次是 DIG 補叫:AIL 鎖([0x52bea] > 0)讓前一次 ISR 沒派送,這次 ISR 叫 DIG 兩次,重入落在第一次的驅動呼叫裡,"
                    f"返回後走 {len(PATH_AGAIN)} 條進第二次 DIG,而不是 {len(PATH_END)} 條到 0x3eb9d:{D_DIG} − {len(PATH_END)} + {len(PATH_AGAIN)} = {D_AGAIN},"
                    f"與紀錄的 26 相同。鎖之後補叫的 7 次 ISR 都恰好多叫「被跳過的 ISR 數」次 DIG。另 1 次是重入了兩次:第一次晚了 {LATE['double_first']} ms"
                    f"(其他 DIG 型最晚 {LATE['dig_type_max']} ms),{LATE['gap_ms']} ms 後下一個 tick 又進來,第二次重入之後 {D_DIG} 條到 0x3eb9d(DIG 型)。",
    "hud_uncovered": f"校準集(827 張,章節 {', '.join(map(str, COVERED))})沒涵蓋的 {len(UNC['chapters'])} 章,.wsl_build 截圖依像素去重 "
                     f"{UNC['frames']} 張:邊框樣板判有框 {UNC['template_pos']} 張(分佈在 {len(UNC['template_pos_by_ch'])} 章),吻合率全是 "
                     f"{UNC['template_pos_min']},其餘最高 {UNC['template_neg_max']}(與校準集相同)。舊藍佔比判準判有 {UNC['old_pos']} 張,"
                     f"其中 {UNC['old_only']} 張樣板判沒有,逐張目視都沒有 HUD 框;樣板有、舊判準沒有的 {UNC['template_only']} 張。"
                     f"所以工具拿掉退回藍佔比那一步:這 20 章少掉 {UNC['old_only']} 個誤判、校準集少掉 {S169_FP} 個,沒有漏掉任何有框的截圖。",
}
for _part, _key in (("4096 的倍數", "buffer"), ("40000 位元組都沒寫盤", "buffer"), ("FDMUS_012", "enemy_mdi"), ("3414 / 4670 / 2468", "enemy_mdi"),
                    ("3018 / 3044", "enemy_mdi"), ("diag 43164 / 43165", "enemy_mdi"), ("85 / 718、其他 457 / 3528", "enemy_mdi"), ("3.73 倍", "enemy_mdi"), ("Fisher p = 0.462", "enemy_mdi"), ("多叫 56 次", "transition"),
                    ("93 − 77 + 10 = 26", "unclassified"), ("晚了 4.909 ms", "unclassified"), ("3015 張", "hud_uncovered"),
                    ("其中 348 張樣板判沒有", "hud_uncovered"), ("最高 0.4009", "hud_uncovered"), ("少掉 75 個", "hud_uncovered")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s170.py"),
    "exe_md5": MD5,
    "buffer_probe": {"script": rel(DRV / "setvbuf_probe.py"), "output": rel(DRV / "setvbuf_probe_out.txt"), "st_blksize": BLK,
                     "sizes": {f"{a}:{b}": v for (a, b), v in SIZES.items()}, "checks": PROBE},
    "calllog": {"path": rel(RAW / "lc167a_CALLLOG.TXT"), "md5": CALLLOG_MD5},
    "enemy_mdi": {"static": {hex(a): t for a, t in STATIC.items()}, "tracks": TRACKS,
                  "songs": {f"FDMUS_{n:03d}": {"md5": s["md5"], "max_tick": s["max_tick"], "event_ticks": len(s["ticks"]),
                                               "density": DENSITY[n]} for n, s in SONG.items()},
                  "unclosed_mdi_services": len(UNCLOSED), "align": ALIGN, "diag": DIAG, "en_extra": EN_EXTRA_SUM,
                  "transitions": TRANS, "rates": RATE, "hit": HIT, "ratios": RATIO},
    "unclassified": {"cases": CASES, "path_end": len(PATH_END), "path_again": len(PATH_AGAIN), "predicted_again": D_AGAIN,
                     "dig_type_nongame_229": NG_DIG[True], "dig_type_total": NG_DIG[True] + NG_DIG[False],
                     "catchup": CATCHUP, "lateness_ms": LATE},
    "hud_uncovered": {"frames_list": rel(DRV / "uncovered_frames.txt"), "labels": rel(DRV / "hud_labels_s170.txt"),
                      "covered_chapters": COVERED, "summary": UNC, "labelled_no_hud": len(OLD_ONLY), "labelled_sample": len(_sample),
                      "s169_tool_fp_on_calib": S169_FP},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, RATIO, HIT, D_AGAIN)
