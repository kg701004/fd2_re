"""續一百六十八證據:evidence/battle_driver_gates_s168_20261030.json(戰場驅動的兩道送鍵閘門;實機 lc168a)。

續一百六十七 lc167a 的兩個驅動問題:confirm_end_turn 會進除錯器(停住模擬器),以及 ensure_battle_hud
在「已有控制權、HUD 還沒畫出」那一刻多按一次 Return。tools/fd2_chapter_sweep.py 新增
screen_shows_dialogue_panel、ensure_battle_hud(panel_gate=True)、send_end_turn_keys、calllog_count。
(A) 原始紀錄:lc168a 指紋、入口與 lc167a 相同、回合標記的順序。
(B) 面板判準的校準:827 張歷史 hudcheck 截圖(drivers_s168/calib_frames.txt)上,非 HUD 畫面的
    「單一 HUD 藍佔比」分成兩群、中間沒有樣本;舊的 screen_looks_like_dialogue 把第 1 章上方對話框判成非對話。
(C) lc167a 重放:第 33 次 Return 在 battle_main_input_loop 進入(E 0x117e7)之後才送出;當時按在
    「看不到面板」畫面後的 Return 有 8 次,正好是 lc167a(33)與 lc168a(25)的差。
(D) CALLLOG 的寫入落後:寫入端每 1024 筆 E 才 fflush,用 lc168a 玩家回合的 E 速率換算間隔。
(E) 實機前預測 Q1 .. Q6(drivers_s168/pred168_gates.txt)逐項判定。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
import warnings

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
warnings.filterwarnings("ignore", category=DeprecationWarning)      # Pillow getdata 的棄用警告
sys.path.insert(0, str(ROOT / "tools"))
import fd2_chapter_sweep as sw  # noqa: E402
from PIL import Image, ImageStat  # noqa: E402

OUT = out_path("battle_driver_gates_s168_20261030.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
RAW = ROOT / ".wsl_build" / "lc168_live"
RAW167 = ROOT / ".wsl_build" / "lc167_live"
DRV = GEN_DIR / "drivers_s168"
PRED_FILE = DRV / "pred168_gates.txt"
DELTA = 0x19C000
LOOP, RING, ADVANCE, FRIEND, ENEMY = 0x117E7, 0x16F55, 0x1A30B, 0x1D80B, 0x1D8BA
NAMES = {LOOP: "loop", RING: "ring", ADVANCE: "advance", FRIEND: "friend", ENEMY: "enemy"}
SAT_REGION = (360, 215, 824, 520)
SAT_SELECTED_MAX = 110                 # 預測檔 Q5 的門檻
LEAD_MS_S167 = 1000                    # 續一百六十七閒置窗開頭扣掉的毫秒數


def md5(p) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def markers(path) -> list[tuple[str, str, float]]:
    """CALLLOG 中五個回合標記的 E / R 記錄 (種類, 名稱, t);沒有 t 的截斷行不算。"""
    want = {f"{a + DELTA:08x}": n for a, n in NAMES.items()}
    out = []
    with path.open(encoding="ascii") as fh:
        for ln in fh:
            p = ln.split(" ", 3)
            if len(p) > 3 and p[0] in ("E", "R") and p[2] in want and " t=" in ln:
                out.append((p[0], want[p[2]], float(ln.rsplit(" t=", 1)[1])))
    return out


def hud_s168(p) -> bool:
    """續一百六十八當時的 screen_shows_battle_hud(只有藍佔比判準)。續一百六十九起工具先比對 HUD 邊框樣板,
    這裡固定用舊判準,讓本證據的重算結果不變。"""
    im = Image.open(p).convert("RGB")
    return (sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION, sw.BATTLE_HUD_RIGHT_STRIP_REGION)
            or sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION_R, sw.BATTLE_HUD_LEFT_STRIP_REGION_R))


def sat(p) -> float:
    return round(ImageStat.Stat(Image.open(p).convert("HSV").crop(SAT_REGION)).mean[1], 1)


# ---------------------------------------------------------------- (A) 原始紀錄
META = (RAW / "lc168a_meta.txt").read_text(encoding="utf-8").splitlines()
META167 = (RAW167 / "lc167a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG = RAW / "lc168a_CALLLOG.TXT"
CALLLOG_MD5 = md5(CALLLOG)
assert META[0].split()[0] == MD5 and META[0].endswith("FD2.EXE"), META[0]
assert META[1].split()[0] == CALLLOG_MD5 == "068485e3e8b80dd89c6a3a481b57c45f", (META[1], CALLLOG_MD5)
assert int(META[2]) == 224299 and META[3].startswith("H fd2calllog 1 ") and "entries=26" in META[3], META[2:4]
# 入口與 lc167a 完全相同(同一份 26 個位址),兩次的呼叫紀錄可以直接比較
assert META[4] == META167[4] and META[3] == META167[3], (META[3:5], META167[3:5])
RUN = json.loads((RAW / "lc168a_run.json").read_text(encoding="utf-8"))
assert RUN["ok"] is True and RUN["error"] is None and RUN["runner"]["ok"] is True, (RUN["ok"], RUN["error"])
MK = markers(CALLLOG)
SEQ = [(k, n) for k, n, _ in MK]
# 對話結束進入輸入迴圈 → 空格上按 Return(迴圈 R/E)→ 指令環 → 推進 → 友軍 → 敵方 → 依序返回 → 第二個玩家回合
assert SEQ == [("E", "loop"), ("R", "loop"), ("E", "loop"), ("E", "ring"), ("E", "advance"), ("E", "friend"),
               ("R", "friend"), ("E", "enemy"), ("R", "enemy"), ("R", "advance"), ("R", "ring"), ("R", "loop"),
               ("E", "loop")], SEQ
T = {"E_loop_first": MK[0][2], "E_ring": MK[3][2], "E_enemy": MK[7][2], "R_enemy": MK[8][2]}
assert [round(v, 1) for v in T.values()] == [86781.8, 122687.2, 144510.9, 170620.1], T
PRED_TEXT = PRED_FILE.read_text(encoding="utf-8")
PRED_MD5 = md5(PRED_FILE)
assert PRED_MD5 == "0449c05fc75c73179000361e71431a04", PRED_MD5     # 實機前(2026-10-30 00:05:17)量的 md5
for _q in ("Q1 ensure_battle_hud 回傳 ok=True,且至少 1 張不送鍵的等待幀", "Q2 ensure_battle_hud 送出的 Return 次數 ≤ 32",
           "CALLLOG 的 E 0x117e7 恰好 1 筆、E 0x16f55 為 0 筆", "ring_probe 在逾時(8 秒)前為 True",
           "平均 HSV 飽和度 ≥ 110", "YES 之後 240 秒內 CALLLOG 出現 R 0x1d8ba"):
    assert _q in PRED_TEXT, _q

# ---------------------------------------------------------------- (B) 面板判準的校準
CALIB = [ROOT / ln for ln in (DRV / "calib_frames.txt").read_text(encoding="utf-8").split()]
assert len(CALIB) == len(set(CALIB)) == 827, len(CALIB)
ROWS = []
for f in CALIB:
    im = Image.open(f).convert("RGB")
    assert im.size == (1024, 768), (f, im.size)
    best = (0.0, None)
    for band in sw.DIALOGUE_PANEL_BANDS:
        c = collections.Counter(im.crop(band).getdata())
        col, n = c.most_common(1)[0]
        frac = n / sum(c.values()) if sw._is_hud_blue(col) else 0.0
        best = max(best, (frac, col), key=lambda x: x[0])
    ROWS.append({"f": rel(f), "hud": hud_s168(f), "panel": sw.screen_shows_dialogue_panel(f),
                 "flat": round(best[0], 3), "color": best[1]})
# 自己算的比例要與工具的判準一致(兩種寫法:Counter.most_common 與工具的 dict 計數)
assert all(r["panel"] == (r["flat"] >= sw.DIALOGUE_PANEL_FLAT_MIN) for r in ROWS)
NONHUD = [r for r in ROWS if not r["hud"]]
LOW = [r["flat"] for r in NONHUD if r["flat"] < sw.DIALOGUE_PANEL_FLAT_MIN]
HIGH = [r for r in NONHUD if r["flat"] >= sw.DIALOGUE_PANEL_FLAT_MIN]
CAL = {"frames": len(ROWS), "hud": len(ROWS) - len(NONHUD), "non_hud": len(NONHUD),
       "low": len(LOW), "low_max": max(LOW), "high": len(HIGH), "high_min": min(r["flat"] for r in HIGH),
       "high_colors": sorted({str(r["color"]) for r in HIGH}), "threshold": sw.DIALOGUE_PANEL_FLAT_MIN}
assert (CAL["frames"], CAL["hud"], CAL["non_hud"], CAL["low"], CAL["high"]) == (827, 180, 647, 189, 458), CAL
assert CAL["low_max"] == 0.187 and CAL["high_min"] == 0.621 and CAL["low_max"] < CAL["threshold"] <= CAL["high_min"], CAL
assert CAL["high_colors"] == ["(40, 69, 138)", "(56, 85, 154)"], CAL["high_colors"]
# 藍色地形:HUD 在畫面上但 HUD 判準漏判(範圍外,只記錄),面板判準也不能把它當成面板
BLUE_TERRAIN = {n: ROOT / ".wsl_build" / "ctr" / "terr2" / n for n in ("ch20/shots/hudcheck_hud3_clear4.png",
                                                                       "ch29/shots_t2/hudcheck_t2_clear1.png")}
BT = {n: {"hud": hud_s168(p), "panel": sw.screen_shows_dialogue_panel(p)} for n, p in BLUE_TERRAIN.items()}
assert all(v == {"hud": False, "panel": False} for v in BT.values()), BT
assert all(rel(p) in {r["f"] for r in ROWS} for p in BLUE_TERRAIN.values())

# ---------------------------------------------------------------- (C) lc167a 重放
FR167 = RAW167 / "frames"
SEQ167 = ["hudcheck_hud.png"] + [f"hudcheck_hud_clear{i}.png" for i in range(33)]
P167 = [sw.screen_shows_dialogue_panel(FR167 / n) for n in SEQ167]
H167 = [hud_s168(FR167 / n) for n in SEQ167]
OLD167 = [sw.screen_looks_like_dialogue(FR167 / n) for n in SEQ167]
assert H167 == [False] * 33 + [True], H167
# 每張非 HUD 畫面之後都按了一次 Return(舊路徑),其中畫面上沒有面板的:
NOPANEL_PRESSED = [SEQ167[i] for i in range(33) if not P167[i]]
assert NOPANEL_PRESSED == [f"hudcheck_hud_clear{i}.png" for i in (1, 2, 3, 7, 8, 9, 19, 31)], NOPANEL_PRESSED
# 舊判準漏掉的對話框(對話框在畫面上方,y=500 那一列取到的是地圖)
OLD_MISSED = [SEQ167[i] for i in range(33) if P167[i] and not OLD167[i]]
assert OLD_MISSED == [f"hudcheck_hud_clear{i}.png" for i in (4, 14, 18, 20, 21, 22, 23, 24, 28, 29, 30)], OLD_MISSED
RUN167 = json.loads((RAW167 / "lc167a_run.json").read_text(encoding="utf-8"))
assert RUN167["hud"] == {"ok": True, "clears": 33}, RUN167["hud"]
MT = json.loads((RAW167 / "frames_mtime.json").read_text(encoding="utf-8"))["mtime"]
H_A, T_A = RUN167["marks"]["P_a"]
# 以 P_a 讀到的尾端 t 當錨點換算截圖時刻;尾端 t 本身落後(見 (D)),所以真實時刻只會更晚
EM = {n: round(T_A - (H_A - MT[n]) * 1000, 1) for n in ("hudcheck_hud_clear30.png", "hudcheck_hud_clear31.png",
                                                       "hudcheck_hud_clear32.png")}
E_LOOP_167 = markers(RAW167 / "lc167a_CALLLOG.TXT")[0]
assert E_LOOP_167[:2] == ("E", "loop") and round(E_LOOP_167[2], 1) == 87411.2, E_LOOP_167
assert EM["hudcheck_hud_clear30.png"] < E_LOOP_167[2] < EM["hudcheck_hud_clear31.png"], (EM, E_LOOP_167)
assert EM == {"hudcheck_hud_clear30.png": 86134.7, "hudcheck_hud_clear31.png": 87438.4,
              "hudcheck_hud_clear32.png": 88715.4}, EM
SAT = {"lc167a_start": sat(FR167 / "findempty_000_start.png"), "lc167a_after_up": sat(FR167 / "findempty_001_Up.png"),
       "lc168a_after_up": sat(RAW / "frames" / "findempty_001_Up.png")}
assert SAT == {"lc167a_start": 133.5, "lc167a_after_up": 89.4, "lc168a_after_up": 150.9}, SAT

# ---------------------------------------------------------------- (D) CALLLOG 寫入落後
PA, PB = RUN["marks"]["P_a"][1], RUN["marks"]["P_b"][1]
N_E = 0
with CALLLOG.open(encoding="ascii") as fh:
    for ln in fh:
        if ln.startswith("E ") and " t=" in ln and PA <= float(ln.rsplit(" t=", 1)[1]) < PB:
            N_E += 1
E_PER_S = round(N_E / ((PB - PA) / 1000), 1)
FLUSH_S = round(1024 / E_PER_S, 2)
assert N_E == 16033 and E_PER_S == 532.6 and FLUSH_S == 1.92, (N_E, E_PER_S, FLUSH_S)
# LEAD_MS_S167 對已提交的續一百六十七證據核對:P 窗起點 − P_a 讀到的尾端 t
_W167 = json.loads((EVIDENCE / "battle_turn_interrupt_loss_s167_20261029.json").read_text(encoding="utf-8"))["windows_ms"]["P"]
assert round(_W167[0] - RUN167["marks"]["P_a"][1]) == LEAD_MS_S167, (_W167, RUN167["marks"]["P_a"])
assert FLUSH_S * 1000 > LEAD_MS_S167                     # 續一百六十七閒置窗開頭只扣 1 秒,不夠蓋過落後

# ---------------------------------------------------------------- (E) 預測
FR = RAW / "frames"
WAITS = sorted(p.name for p in FR.glob("hudcheck_hud_wait*.png"))
CLEARS = sorted(p.name for p in FR.glob("hudcheck_hud_clear*.png"))
assert RUN["hud"] == {"ok": True, "clears": 25, "wait_frames": 10, "fallback_returns": 0, "probe_stop": False}, RUN["hud"]
assert len(WAITS) == 10 and len(CLEARS) == 25
# 依 panel_gate 的規則重建截圖順序(複製後 mtime 已不可靠):每張看不到面板的畫面之後,依序接等待幀,
# 直到某張等待幀出現面板(或 HUD)為止。每一次 Return 之前的最後一張都必須有面板。
WAIT_Q = [f"hudcheck_hud_wait{i}.png" for i in range(len(WAITS))]
ORDER, PRESS_AFTER, last = [], [], "hudcheck_hud.png"
for k in range(len(CLEARS) + 1):
    ORDER.append(last)
    while not sw.screen_shows_dialogue_panel(FR / last) and not hud_s168(FR / last):
        last = WAIT_Q.pop(0)
        ORDER.append(last)
    if hud_s168(FR / last):
        break
    PRESS_AFTER.append(last)
    last = f"hudcheck_hud_clear{k}.png"
assert WAIT_Q == [] and len(PRESS_AFTER) == RUN["hud"]["clears"] and ORDER[-1] == "hudcheck_hud_wait9.png", (WAIT_Q, ORDER[-3:])
PRE_PRESS_NOPANEL = [n for n in PRESS_AFTER if not sw.screen_shows_dialogue_panel(FR / n)]
NOPANEL_168 = [n for n in ORDER if not sw.screen_shows_dialogue_panel(FR / n) and not hud_s168(FR / n)]
assert NOPANEL_168 == ["hudcheck_hud_clear1.png", "hudcheck_hud_wait0.png", "hudcheck_hud_wait1.png", "hudcheck_hud_clear4.png",
                       "hudcheck_hud_wait3.png", "hudcheck_hud_wait4.png", "hudcheck_hud_wait5.png", "hudcheck_hud_clear13.png",
                       "hudcheck_hud_wait7.png", "hudcheck_hud_clear24.png"], NOPANEL_168
# 三段無字幕過場都沒按鍵就自己走到下一個對話框(wait2 / wait6 / wait8 有面板);最後一段走到 HUD(wait9)
SELF_ADVANCED = [n for n in ORDER if n.startswith("hudcheck_hud_wait") and sw.screen_shows_dialogue_panel(FR / n)]
assert SELF_ADVANCED == ["hudcheck_hud_wait2.png", "hudcheck_hud_wait6.png", "hudcheck_hud_wait8.png"], SELF_ADVANCED
LAST = {"clear24_panel": sw.screen_shows_dialogue_panel(FR / "hudcheck_hud_clear24.png"),
        "clear24_hud": hud_s168(FR / "hudcheck_hud_clear24.png"),
        "wait9_hud": hud_s168(FR / "hudcheck_hud_wait9.png")}
STATE = RUN["state_pre_idle"]
PRE = FR / "state_pre_idle.png"
assert STATE == {"hud": hud_s168(PRE), "panel": sw.screen_shows_dialogue_panel(PRE),
                 "sat": sat(PRE), "loop_E": 1, "ring_E": 0}, STATE
END = RUN["end_turn"]
RING_WAIT_S = round(END["t_host"]["ring_seen"] - END["t_host"]["ring"], 2)
assert RING_WAIT_S == 0.29, END["t_host"]
assert RUN["findempty_first_move"] == {"shot": "findempty_001_Up.png", "sat": SAT["lc168a_after_up"]}, RUN["findempty_first_move"]
CHECK = {
    "Q1": RUN["hud"]["ok"] and RUN["hud"]["wait_frames"] >= 1,
    "Q2": RUN["hud"]["clears"] <= 32,
    "Q3": STATE["hud"] and not STATE["panel"] and STATE["loop_E"] == 1 and STATE["ring_E"] == 0,
    "Q4": END["ok"] and END["stage"] == "yes" and RING_WAIT_S < 8.0,
    "Q5": SAT["lc168a_after_up"] >= SAT_SELECTED_MAX,
    "Q6": RUN["enemy_wait"]["R_count"] == 1 and RUN["enemy_wait"]["s"] <= 240,
}
VERDICT = {k: "PASS" if v else "FAIL" for k, v in CHECK.items()}
assert VERDICT == dict.fromkeys(("Q1", "Q2", "Q3", "Q4", "Q5", "Q6"), "PASS"), VERDICT
assert PRE_PRESS_NOPANEL == [] and LAST == {"clear24_panel": False, "clear24_hud": False, "wait9_hud": True}, (PRE_PRESS_NOPANEL, LAST)
assert 33 - RUN["hud"]["clears"] == len(NOPANEL_PRESSED) == 8

CONC = {
    "gate_hud": f"panel_gate:lc168a 按 Return {RUN['hud']['clears']} 次、不送鍵等待 {RUN['hud']['wait_frames']} 張,"
                f"沒有補按;lc167a 按了 33 次,其中 {len(NOPANEL_PRESSED)} 次是在看不到面板的畫面之後"
                f"(7 張無字幕過場 + clear31),33 − 25 正好是 8。lc168a 的無字幕過場都自己走到下一個對話框。",
    "extra_return": f"lc167a 的 E 0x117e7 在 t={E_LOOP_167[2]:.1f},介於 clear30({EM['hudcheck_hud_clear30.png']})與 "
                    f"clear31({EM['hudcheck_hud_clear31.png']})之間,所以第 33 次 Return 是進入輸入迴圈之後才送的。"
                    f"lc168a 同一個畫面(clear24)沒有再按,之後方向鍵後的地圖飽和度 {SAT['lc168a_after_up']}"
                    f"(lc167a 是 {SAT['lc167a_after_up']}),指令環一次就開。",
    "gate_end": f"send_end_turn_keys:指令環 E 0x16f55 在 Return 後 {RING_WAIT_S} 秒讀到,確認框面板在,YES 後 "
                f"{RUN['enemy_wait']['s']} 秒讀到 R 0x1d8ba;全程沒進除錯器。",
    "calibration": f"面板判準:{CAL['frames']} 張歷史截圖中非 HUD {CAL['non_hud']} 張,單一 HUD 藍佔比 ≤ {CAL['low_max']} 的 "
                   f"{CAL['low']} 張、≥ {CAL['high_min']} 的 {CAL['high']} 張,門檻 {CAL['threshold']} 落在空檔;舊判準漏掉第 1 章"
                   f"上方對話框 {len(OLD_MISSED)} 張。",
    "flush_lag": f"CALLLOG 每 1024 筆 E 才寫盤;lc168a 玩家回合 {E_PER_S} 筆 / 秒,約每 {FLUSH_S} 秒一次。"
                 f"續一百六十七閒置窗開頭只扣 {LEAD_MS_S167} ms,不足以蓋過落後(仍留)。",
    "out_of_scope": "ch20 / ch29 的兩張截圖 HUD 在畫面上,但 screen_shows_battle_hud 判 False(框右是藍色地形),"
                    "當時連按到 clear55 / clear37;只記錄,未修改。",
}
for _part, _key in (("按 Return 25 次", "gate_hud"), ("33 − 25 正好是 8", "gate_hud"), ("t=87411.2", "extra_return"),
                    ("飽和度 150.9", "extra_return"), ("89.4", "extra_return"), ("≤ 0.187", "calibration"),
                    ("≥ 0.621 的 458 張", "calibration"), ("532.6 筆", "flush_lag"), ("1.92 秒", "flush_lag"),
                    ("47.0 秒", "gate_end")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s168.py"),
    "exe_md5": MD5,
    "approval": "使用者 2026-10-29「永遠核准你進行實機」與「依照你的建議執行」;實機 lc168a,不改記憶體、不下斷點、不進除錯器",
    "prediction_file": {"path": rel(PRED_FILE), "md5": PRED_MD5},
    "run": {"calllog": rel(CALLLOG), "calllog_md5": CALLLOG_MD5, "lines": int(META[2]), "marker_sequence": SEQ,
            "marker_t_ms": T, "hud": RUN["hud"], "frame_order": ORDER, "no_panel_frames": NOPANEL_168,
            "self_advanced_to_panel": SELF_ADVANCED, "state_pre_idle": STATE, "end_turn": END, "ring_wait_s": RING_WAIT_S,
            "enemy_wait": RUN["enemy_wait"], "marks": RUN["marks"]},
    "calibration": CAL,
    "calibration_rows": [{k: r[k] for k in ("f", "hud", "flat")} for r in ROWS],
    "blue_terrain_hud_false_negative": BT,
    "replay_lc167a": {"panel": dict(zip(SEQ167, P167)), "old_dialogue_check_missed": OLD_MISSED,
                      "pressed_after_no_panel": NOPANEL_PRESSED, "frame_t_ms_from_P_a": EM,
                      "E_loop_first_t": E_LOOP_167[2], "saturation": SAT},
    "flush_lag": {"E_in_P": N_E, "E_per_s": E_PER_S, "flush_interval_s": FLUSH_S, "lead_ms_s167": LEAD_MS_S167},
    "predictions": VERDICT,
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, VERDICT, CAL["low_max"], CAL["high_min"], FLUSH_S)
