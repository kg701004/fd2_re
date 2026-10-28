"""ev_s160.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s160.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 原始紀錄
    ("harness EXE 不是原版", "assert META[1].split() == [MD5, \"FD2.EXE\"]", "assert META[1].split() != [MD5, \"FD2.EXE\"]"),
    ("閘門位址 + 1", "f\"gate={GATE + DELTA:08x}\" in HDR", "f\"gate={GATE + 1 + DELTA:08x}\" in HDR"),
    ("過濾後 2925 行", "assert len(_lines) == 2924", "assert len(_lines) == 2925"),
    ("過濾留下 has_key 0", "(r[\"k\"] == \"E\" or r[\"eax\"] == 0)]", "(r[\"k\"] == \"E\" or r[\"eax\"] != 0)]"),
    ("寫入前已是 1", "== (0, 1, []), KILL", "== (1, 1, []), KILL"),
    ("新遊戲 [0x53c03] = 0x21", "assert C03 == 0x20", "assert C03 == 0x21"),
    # (B) 設定步驟
    ("清對話 33 次", "assert len(_clears) == 32", "assert len(_clears) == 33"),
    ("Escape 改 Return", "(\"key\", \"Escape\", False),", "(\"key\", \"Return\", False),"),
    ("寫入在 YES 之後", "assert STEP[38][\"t0\"] < KILL[\"t_host\"] < STEP[39][\"ts0\"]",
     "assert STEP[39][\"ts0\"] < KILL[\"t_host\"]"),
    ("033 沒褪色", "assert SAT[2] < 0.8 * SAT[0]", "assert SAT[2] > 0.8 * SAT[0]"),
    ("Escape 之後沒還原", "assert DIFF_ESC < 0.05 and DIFF_SEL > 0.9", "assert DIFF_ESC > 0.05 and DIFF_SEL > 0.9"),
    ("提示框門檻 3 倍", "assert PROMPT_BLUE[1] > 1.5 * PROMPT_BLUE[0]", "assert PROMPT_BLUE[1] > 3 * PROMPT_BLUE[0]"),
    # (C) P0、P2
    ("閘門前有記錄", "assert G0[\"seq\"] == 1 and REC[0] is G0", "assert G0[\"seq\"] == 2 and REC[0] is G0"),
    ("確認在選單 flush 之前", "== [1, 132, 397, 524, 527, 528, 529, 538, 603, 668]",
     "== [1, 132, 397, 528, 527, 524, 529, 538, 603, 668]"),
    ("選單讀兩個鍵", "assert len(MENU_KEYS) == 1 and len(READS) == 1", "assert len(MENU_KEYS) == 2 and len(READS) == 1"),
    ("kbd_flush 回 0x1fd80", "FLUSH[0][\"ret\"] == 0x1FD81", "FLUSH[0][\"ret\"] == 0x1FD80"),
    # (D) P1
    ("閃爍改 3 次", "== [(0x50, 0x1FF0D), (0x50, 0x1FF28)] * 4", "== [(0x50, 0x1FF0D), (0x50, 0x1FF28)] * 3"),
    ("淡出 63 次 delay", "and len(_fd) == 64", "and len(_fd) == 63"),
    ("圈數公式不四捨五入", "LOOPS80 = (80 * CALIB + 500) // 1000", "LOOPS80 = (80 * CALIB + 1500) // 1000"),
    ("delay 80 上限 90", "assert min(BL_MS) > 85 and max(BL_MS) < 105", "assert min(BL_MS) > 85 and max(BL_MS) < 90"),
    ("閃爍判準 ±25%", "640 * 0.85 <= BLINK_MS <= 640 * 1.15", "640 * 0.75 <= BLINK_MS <= 640 * 1.25"),
    ("淡出門檻 450", "\"fade_le_300\": FADE_MS <= 300", "\"fade_le_300\": FADE_MS <= 450"),
    # (E) P5、P3
    ("最後送鍵不是最後到達", "D0 = HS[-1][1] - KEYS[-1][1]", "D0 = HS[-2][1] - KEYS[-1][1]"),
    # 分群門檻:28 .. 893 ms 之間結果相同(ev_s160 已斷言兩邊的餘裕),所以從兩邊越界
    ("有鍵群間隔 1000 ms", "if r[\"t\"] - _last > 50:", "if r[\"t\"] - _last > 1000:"),
    ("有鍵群間隔 20 ms", "if r[\"t\"] - _last > 50:", "if r[\"t\"] - _last > 20:"),
    ("P5 範圍 1.0 .. 1.1", "assert 0.9 <= SLOPE <= 1.1", "assert 1.0 <= SLOPE <= 1.1"),
    ("視窗不含對齊誤差", "if H_FLUSH - R_MAX <= h <= H_CONF + R_MAX]", "if H_FLUSH <= h <= H_CONF]"),
    ("確認是 clear012", "assert WIN == [CONF_SEND] == [\"clear011\"]", "assert WIN == [CONF_SEND] == [\"clear012\"]"),
    ("不含 YES 計數", "N_RETURN = [t for t, _ in HS].index(CONF_SEND) + 1", "N_RETURN = [t for t, _ in HS].index(CONF_SEND)"),
    # (F) P4
    ("11 沒變暗", "assert CORR_10_11 > 0.99 and MEAN[11] < 0.9 * MEAN[10]", "assert CORR_10_11 > 0.99 and MEAN[11] > 0.9 * MEAN[10]"),
    ("最後全亮選單是 11", "LAST_STILL = 10", "LAST_STILL = 11"),
    ("11 不在淡出區間", "H_FADE[0] <= SHOT_T[11] <= H_FADE[1]", "H_FADE[0] <= SHOT_T[10] <= H_FADE[1]"),
    # 判定
    ("P1 任一條件成立就 PASS", "\"PASS\" if all(P1_OK.values()) else", "\"PASS\" if any(P1_OK.values()) else"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s160", MUTANTS))
