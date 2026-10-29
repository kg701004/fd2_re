"""ev_s168.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s168.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 原始紀錄、標記順序、預測檔
    ("標記少了指令環", "LOOP: \"loop\", RING: \"ring\",", "LOOP: \"loop\","),
    ("預測檔原文改過", "\"Q2 ensure_battle_hud 送出的 Return 次數 ≤ 32\"", "\"Q2 ensure_battle_hud 送出的 Return 次數 ≤ 33\""),
    # (B) 校準
    ("最多色不必是 HUD 藍", "frac = n / sum(c.values()) if sw._is_hud_blue(col) else 0.0", "frac = n / sum(c.values())"),
    ("低群算進 HUD 畫面", "LOW = [r[\"flat\"] for r in NONHUD if", "LOW = [r[\"flat\"] for r in ROWS if"),
    ("藍色地形判準反向", "\"panel\": sw.screen_shows_dialogue_panel(p)} for n, p in BLUE_TERRAIN.items()",
     "\"panel\": not sw.screen_shows_dialogue_panel(p)} for n, p in BLUE_TERRAIN.items()"),
    # (C) lc167a 重放
    ("按鍵數多算 HUD 那張", "NOPANEL_PRESSED = [SEQ167[i] for i in range(33) if", "NOPANEL_PRESSED = [SEQ167[i] for i in range(34) if"),
    ("舊判準漏判反向", "if P167[i] and not OLD167[i]]", "if P167[i] and OLD167[i]]"),
    ("錨點換算方向反了", "T_A - (H_A - MT[n]) * 1000", "T_A + (H_A - MT[n]) * 1000"),
    ("取第二筆輸入迴圈", "E_LOOP_167 = markers(RAW167 / \"lc167a_CALLLOG.TXT\")[0]", "E_LOOP_167 = markers(RAW167 / \"lc167a_CALLLOG.TXT\")[1]"),
    ("飽和度取整張", "SAT_REGION = (360, 215, 824, 520)", "SAT_REGION = (0, 0, 1024, 768)"),
    # (D) 寫入落後
    ("每 512 筆 flush", "FLUSH_S = round(1024 / E_PER_S, 2)", "FLUSH_S = round(512 / E_PER_S, 2)"),
    ("毫秒當成 0.1 秒", "E_PER_S = round(N_E / ((PB - PA) / 1000), 1)", "E_PER_S = round(N_E / ((PB - PA) / 100), 1)"),
    ("落後與 LEAD 比較反向", "assert FLUSH_S * 1000 > LEAD_MS_S167", "assert FLUSH_S * 1000 < LEAD_MS_S167"),
    # (E) 預測與送鍵順序
    ("等待幀倒序", "last = WAIT_Q.pop(0)", "last = WAIT_Q.pop()"),
    ("送鍵前檢查反向", "PRE_PRESS_NOPANEL = [n for n in PRESS_AFTER if not", "PRE_PRESS_NOPANEL = [n for n in PRESS_AFTER if"),
    ("Q2 門檻 24", "\"Q2\": RUN[\"hud\"][\"clears\"] <= 32,", "\"Q2\": RUN[\"hud\"][\"clears\"] <= 24,"),
    ("Q3 輸入迴圈 0 筆", "STATE[\"loop_E\"] == 1 and STATE[\"ring_E\"] == 0,", "STATE[\"loop_E\"] == 0 and STATE[\"ring_E\"] == 0,"),
    ("Q4 逾時 0.1 秒", "RING_WAIT_S < 8.0,", "RING_WAIT_S < 0.1,"),
    ("Q5 方向反了", "\"Q5\": SAT[\"lc168a_after_up\"] >= SAT_SELECTED_MAX,", "\"Q5\": SAT[\"lc168a_after_up\"] < SAT_SELECTED_MAX,"),
    ("差額不是 8", "== len(NOPANEL_PRESSED) == 8", "== len(NOPANEL_PRESSED) == 9"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s168", MUTANTS))
