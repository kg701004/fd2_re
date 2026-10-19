"""ev_ai_item_action_item79_flow.py 的變異測試:每個變異改一個判準 / 預測,必須讓產生器以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("頭尾亮度差門檻 10", "if b[0] - b[-1] < 4:", "if b[0] - b[-1] < 10:"),
    ("同相位容許改 0", "if same and abs(b[i] - b[i + 1]) >= 0.1:", "if same and abs(b[i] - b[i + 1]) >= 0.0:"),
    ("相位大的可以比較亮", "if not same and b[i + 1] - b[i] > 0.1:", "if not same and b[i + 1] - b[i] > 9.9:"),
    ("對照帶容許 0.01", "if max(c) - min(c) > 1.5:", "if max(c) - min(c) > 0.01:"),
    ("亮帶多算一格", "(cx1 - sx) * 24 + 27, (cy1 - sy) * 24 + 27)", "(cx1 - sx) * 24 + 51, (cy1 - sy) * 24 + 51)"),
    ("亮度用滿 8 位元", "((pal[i * 3] & 63) + (pal[i * 3 + 1] & 63) + (pal[i * 3 + 2] & 63)) / 3",
     "((pal[i * 3] & 15) + (pal[i * 3 + 1] & 63) + (pal[i * 3 + 2] & 63)) / 3"),
    ("調色盤迴圈預期從 63 起", "assert log[\"pal\"] == list(range(64, -1, -1))", "assert log[\"pal\"] == list(range(63, -1, -1))"),
    ("對照圖每格 325", "x, y = (n % 4) * 324 + 2, (n // 4) * 216 + 14", "x, y = (n % 4) * 325 + 2, (n // 4) * 216 + 14"),
    # 「相位幀改用 151dd 的調色盤」是等價突變:兩輪的 151dd 與 1528c 調色盤逐 byte 相同
    ("對照圖調色盤不換算", "return bytes(min(255, (v & 0x3F) * 255 // 63) for v in f.read_bytes())",
     "return bytes(min(255, (v & 0x3F)) for v in f.read_bytes())"),
    ("視窗圖間距 320", "pal_sheet.paste(window_crop(\"runA\", name), (i * 322, 0))", "pal_sheet.paste(window_crop(\"runA\", name), (i * 320, 0))"),
    ("標題截圖換一張", '(S / "040_B2.png").read_bytes()', '(D / "runA_151dd.png").read_bytes()'),
    ("runA 預期目標 5、11", '"runA": {"targets": [5, 10]', '"runA": {"targets": [5, 11]'),
    ("runB 預期相位全偶數", '"phases": [1, 3, 3, 5, 5, 7, 7, 9]', '"phases": [2, 2, 4, 4, 6, 6, 8, 8]'),
    ("runB 預期 #3 沒受傷", '3: (493, 0), 5: (0, 1)', '3: (867, 0), 5: (0, 1)'),
    ("少一個相位站", '+ ["0x152ba"] * 8 +', '+ ["0x152ba"] * 7 +'),
    ("索爾預期 HP 3", 'out["runs"][1]["stops"][0]["units"][0]["hp"] == 167', 'out["runs"][1]["stops"][0]["units"][0]["hp"] == 3'),
    ("戰敗預期沒有判定", '== [("0x22e5c", 1), ("0x25ebb", 0)]', '== [("0x22e5c", 0), ("0x25ebb", 0)]'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_ai_item_action_item79_flow", MUTANTS))
