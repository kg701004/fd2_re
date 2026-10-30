"""ev_s170.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s170.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) CALLLOG 緩衝實測
    ("區塊當成 8 KiB", "on_grid(SIZES[(\"null_1MiB\", \"phase0\")], 0, BLK)", "on_grid(SIZES[(\"null_1MiB\", \"phase0\")], 0, 2 * BLK)"),
    ("fflush 之後從 0 起算", "on_grid(SIZES[(\"null_1MiB\", \"phase1\")], FLUSH_AT, BLK)", "on_grid(SIZES[(\"null_1MiB\", \"phase1\")], 0, BLK)"),
    ("對照組方向反了", "SIZES[(\"buf_1MiB\", \"phase0\")] == [0]", "SIZES[(\"buf_1MiB\", \"phase0\")] != [0]"),
    # (B) 敵方回合 MDI
    ("基本曲 / 敵方曲對調", "TRACKS = {\"base\": TAB_BASE[1], \"enemy\": TAB_ENEMY[1]}", "TRACKS = {\"base\": TAB_ENEMY[1], \"enemy\": TAB_BASE[1]}"),
    ("循環週期只試 max_tick", "for period in (SONG[n][\"max_tick\"], SONG[n][\"max_tick\"] + 1):", "for period in (SONG[n][\"max_tick\"],):"),
    ("曲子事件只算 note on", "if mb[0] != 0xFF}", "if mb[0] & 0xF0 == 0x90}"),
    ("沒有 R 的服務當成沒叫驅動", "DRVCALL = [c[1] is None or c[1] > 0 for c in CALLS]",
     "DRVCALL = [c[1] is not None and c[1] > 0 for c in CALLS]"),
    ("短驅動呼叫不算", "DRVCALL = [c[1] is None or c[1] > 0 for c in CALLS]", "DRVCALL = [c[1] is None or c[1] > 600 for c in CALLS]"),
    ("R 配錯 seq", "    elif r[0] == \"R\" and r[1] in _open:", "    elif r[0] == \"R\" and r[1] in _open and False:"),
    ("撞上數改數有 R 的", "    hit = sum(1 for j in js if CALLS[j][1] is None)", "    hit = sum(1 for j in js if CALLS[j][1] == 0)"),
    ("Fisher 加總方向反了", "if pr(x) <= p0 * (1 + 1e-9)", "if pr(x) >= p0 * (1 - 1e-9)"),
    ("淡入淡出間隔 16", "FADE_STEP = 8 ", "FADE_STEP = 16 "),
    ("過渡從友軍回合開頭算", "GAP1 = idx(WIN[\"S_friend\"][1], WIN[\"EN\"][0])", "GAP1 = idx(WIN[\"S_friend\"][0], WIN[\"EN\"][0])"),
    ("倍數拿 S_adv 當分母", "RATE[\"EN\"][\"driver_calls_per_s\"] / RATE[\"P\"][\"driver_calls_per_s\"]",
     "RATE[\"EN\"][\"driver_calls_per_s\"] / RATE[\"S_adv\"][\"driver_calls_per_s\"]"),
    ("結論的相符數寫成服務數", "相符 {EN['best']['match']} / {EN['services']}", "相符 {EN['services']} / {EN['services']}"),
    # (B2) 續一百七十三:音量漸變與敵方回合結束後的 991 次
    ("漸變週期當 4", "assert FADE_STEP == 1 + 7 ", "assert FADE_STEP == 1 + 3 "),
    ("敵方曲不晚(晚的方向反了)", "return _pe[(j - _o_en - (j >= slip)) % _PE]", "return _pe[(j - _o_en + (j >= slip)) % _PE]"),
    ("淡出相位不跟著晚一次", "FADE_OUT_PHASE = (_r0 + 1) % FADE_STEP", "FADE_OUT_PHASE = _r0 % FADE_STEP"),
    ("基本曲起點不對 P2_loop", "B0 = GAP2[0] + (_o_p2 - GAP2[0]) % _PB", "B0 = GAP2[0] + (_o_p2 + 1 - GAP2[0]) % _PB"),
    ("淡入只算一半", "_fi_all = range(_fi[0], _fi[-1] + 1, FADE_STEP)", "_fi_all = range(_fi[0], _fi[-1] + 1, 2 * FADE_STEP)"),
    ("模型不含淡出", "MODEL = {j: bool(_pred1[j]) or j in _fo_all for j in R1}", "MODEL = {j: bool(_pred1[j]) for j in R1}"),
    ("對照不拿掉淡出", "_no_fade = sum((bool(_pred1[j]) if j in R1 else bool(_pred2[j])) == DRVCALL[j] for j in GAP2)",
     "_no_fade = sum(MODEL[j] == DRVCALL[j] for j in GAP2)"),
    ("短呼叫拿淡出相位比", "all(p != _r0 for _t, _n, p in SHORT_EN)", "all(p != FADE_OUT_PHASE for _t, _n, p in SHORT_EN)"),
    ("結論的相符數拿對照", "逐次相符 {END_LOOP['model_match']} / {END_LOOP['services']}", "逐次相符 {END_LOOP['control_no_fade']} / {END_LOOP['services']}"),
    # (C) 5 次未歸類重入
    ("DIG 當成派送表第 0 格", "_slots_left = (0x3C - DIG_EDI) // 4", "_slots_left = (0x3C - 0) // 4"),
    ("補叫路徑不含 DIG 進入", "0x3EB3B, 0x3EB3C, DIG]", "0x3EB3B, 0x3EB3C]"),
    ("DIG 型指令數取轉 BIOS 那條", "[\"dig_restore\"][hex(EPI)]", "[\"dig_restore\"][hex(0x3EB69)]"),
    ("DIG 型不看下一筆是什麼", "if q[0] == \"A\" and q[2] == REENTRY and d == {EPI: 93, 0x3EB69: 94}.get(q[6]):",
     "if d in (93, 94, 26):"),
    ("非遊戲指令數改算全部指令", "return (REC[b][4] - REC[a][4]) - (REC[b][3] - REC[a][3])", "return REC[b][4] - REC[a][4]"),
    ("補叫數拿 MDI 數", "\"next_dig\": nxt[1].count(\"DIG\")", "\"next_dig\": nxt[1].count(\"MDI\")"),
    ("外層服務只找 MDI", "while not (REC[j][0] == \"E\" and REC[j][2] in (DIG, MDI) and REC[j][6] == LOOP_CALL_RET):",
     "while not (REC[j][0] == \"E\" and REC[j][2] == MDI and REC[j][6] == LOOP_CALL_RET):"),
    ("tick 週期當成整 5 ms", "PIT_MS = S161[\"timer_channels\"][\"pit_divisor\"] / 1193182 * 1000", "PIT_MS = 5.0"),
    # (D) HUD 樣板在其他章節
    ("樣板門檻 0.4", "r[\"tpos\"] = max(r[\"m\"].values()) >= sw.BATTLE_HUD_FRAME_MATCH_MIN",
     "r[\"tpos\"] = max(r[\"m\"].values()) >= 0.4"),
    ("舊判準只看左側", "or sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION_R, sw.BATTLE_HUD_LEFT_STRIP_REGION_R)),",
     "or False),"),
    ("章節標記取第一個", "return int(m[-1]) if m else None", "return int(m[0]) if m else None"),
    ("人工判讀 N 對到樣板有框的", "assert {r[\"f\"] for r in OLD_ONLY} == {f for f, s in LAB.items() if s == \"N\"}",
     "assert {r[\"f\"] for r in OLD_ONLY} == {f for f, s in LAB.items() if s != \"N\"}"),
    ("工具判定固定回左", "\"tool\": sw._find_hud_box_side(im)})", "\"tool\": \"L\"})"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s170", MUTANTS))
