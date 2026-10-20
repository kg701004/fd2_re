"""ev_s138.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s138.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 標題選單的按鍵
    ("kbd_flush 呼叫點少一個", "assert FLUSH_SITES == [0x1FA57, 0x1FC9C, 0x1FD7C]", "assert FLUSH_SITES == [0x1FA57, 0x1FC9C]"),
    ("確認鍵多一個 Esc", 'assert ACCEPT == {"ascii": [0x0D, 0x20], "scan": [0xE0, 0x52]}',
     'assert ACCEPT == {"ascii": [0x0D, 0x20, 0x1B], "scan": [0xE0, 0x52]}'),
    ("選擇初值預期 ebx", 'insn(0x1F8B5).op_str == "ebp, ebp"', 'insn(0x1F8B5).op_str == "ebp, ebx"'),
    ("閃爍 5 次", "CONFIRM_TO_FADE_END_MS = 4 * (0x50 + 0x50)", "CONFIRM_TO_FADE_END_MS = 5 * (0x50 + 0x50)"),
    ("借章節 32 預期兩處", "assert SET_CH32 == [0x32326] and", "assert SET_CH32 == [0x32326, 0x3231B] and"),
    ("GAME OVER 判準不排除單色", "if all(c == 0 and nc >= 8 for c, nc, _ in r)]", "if all(c == 0 and nc >= 1 for c, nc, _ in r)]"),
    ("GAME OVER 位移對照含原位", "for dx, dy in ((1, 0), (0, 1), (-1, 0))}", "for dx, dy in ((0, 0), (0, 1), (-1, 0))}"),
    ("資源 #79 的第 1 格當第 0 格", "    GO.append((x, y, w, h, dec4(f[13:], w, h)))", "    GO.append((x, y + 1, w, h, dec4(f[13:], w, h)))"),
    ("靜止選單用 LOAD 反白那張", "MENU_STATIC = [k for k, c in CLEAR.items() if (c == POLL).all()]",
     "MENU_STATIC = [k for k, c in CLEAR.items() if (c == BOOT_DOWN).all()]"),
    ("淡出判準用 LOAD 反白", "and not rows_not_palette_only(POLL_F, c, BTN_ROWS)", "and not rows_not_palette_only(BOOT_F, c, BTN_ROWS)"),
    ("不一致的幀預期少第 18 張", "assert UNI_LOW == {2: 0.9996, 15: 0.9998, 18: 0.9933}", "assert UNI_LOW == {2: 0.9996, 15: 0.9998}"),
    ("驅動迴圈等 0.5 秒", '            send_keys(name, "Return")\\n            time.sleep(0.6)\\n',
     '            send_keys(name, "Return")\\n            time.sleep(0.5)\\n'),
    ("對白位置 x 錯一", "TXT_X, TXT_Y = 111, 119", "TXT_X, TXT_Y = 112, 119"),
    ("字模位元順序反", "return np.unpackbits(b).reshape(16, 16).astype(bool)",
     'return np.unpackbits(b, bitorder="little").reshape(16, 16).astype(bool)'),
    ("對白預期在 FDTXT_032", 'v["windows"] == [("FDTXT_033.bin", 0, 50)]', 'v["windows"] == [("FDTXT_032.bin", 0, 50)]'),
    # (B) 第 27 章的明暗
    ("換色表錯一個 byte", "TAB = [np.frombuffer(F3[OFFS[lv]:OFFS[lv] + 256]", "TAB = [np.frombuffer(F3[OFFS[lv] + 1:OFFS[lv] + 257]"),
    ("參考幀用有明暗的那張", 'REF_NAME = "11_after_select2.png"', 'REF_NAME = "10_after_select.png"'),
    ("10_after_select 預期第 1 階", 'SKY_SHOTS = {"10_after_select.png": 0,', 'SKY_SHOTS = {"10_after_select.png": 1,'),
    ("錯一欄的對照沒有錯", "level_fit(frame(SKY / \"10_after_select.png\"), SX26 + 1, SY26, CM26)",
     "level_fit(frame(SKY / \"10_after_select.png\"), SX26, SY26, CM26)"),
    ("地圖用 25", "M26 = 26\n", "M26 = 25\n"),
    ("次佳階門檻 3 萬", "and runner > 2000, (name, per)", "and runner > 30000, (name, per)"),
    # (C) 灰階版
    ("灰階遮罩用 0xf", "GREY = [np.where(p >= 0, (p & 7) + 0x18, -1)", "GREY = [np.where(p >= 0, (p & 15) + 0x18, -1)"),
    ("找到的圖示預期有模式 1", 'assert all(v["mode1_runs_in_hit_sprites"] == [0]', 'assert all(v["mode1_runs_in_hit_sprites"] == [1]'),
    ("顏色數對照把原索引換成灰階索引", '"raw_indices": len(np.unique(SPR[s][_mk]))', '"raw_indices": len(np.unique(GREY[s][_mk]))'),
    ("單位上移 5 列", "assert _draw.count(\"81c3d8750000\") == 1", "assert _draw.count(\"81c3d8750001\") == 1"),
    ("姿勢 0 有模式 1 的鍵數 34", "assert len(KEYS_POSE0_M1) == 35", "assert len(KEYS_POSE0_M1) == 34"),
    # (D) 08-29 / 08-30 的 EXE
    ("cmp 差 251 bytes", 'assert CMP[0].strip() == "252"', 'assert CMP[0].strip() == "251"'),
    ("md5 錯一字", 'assert "72e36e47f1f7d77dc102839262956480  /home/kg701004/fd2-run/FD2.EXE" in EX[1]["result"]',
     'assert "72e36e47f1f7d77dc102839262956481  /home/kg701004/fd2-run/FD2.EXE" in EX[1]["result"]'),
    ("mtime 預期 09-02", 'and " Aug 19 11:07 " in LS[0]', 'and " Sep  2 23:56 " in LS[0]'),
    ("harness 預期 cp -a", "'cp -r \"$SOURCE_GAME_DIR\"/. \"$workdir\"/' in HARN", "'cp -a \"$SOURCE_GAME_DIR\"/. \"$workdir\"/' in HARN"),
    ("修改預期在程式碼物件", "assert obj == [0x60000], (obj, ranges)", "assert obj == [0x10000], (obj, ranges)"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s138", MUTANTS))
