"""ev_item79_aim_exp_reward_lines.py 的變異測試:每個變異改產生器或 lc125_analyze.py 裡一個判準 / 預測,
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。lc125_mut.py 是另一層(把紀錄改錯,要求分析判 FAIL),結果由產生器寫進證據。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

A = "lc125_analyze.py"
MUTANTS = [
    ("施放點含中心", "            if d == 1 or (centre and d == 0):", "            if d <= 1 or (centre and d == 0):", A),
    # 範圍:道具 79 的數值 3 打不死任何目標,紀錄裡的分數都是 2 × 8 = 16;「打得死 = 0x12」那一支在這組樣本沒有出現,
    # 改它是等價突變(續一百三十四曾列入,存活)。
    ("打不死的目標 9 分", "return sum(0x12 if value >= hp[t] else 8 for t in targets)",
     "return sum(0x12 if value >= hp[t] else 9 for t in targets)", A),
    ("同分就換", "if s > bs or (ge and s >= bs and s > 0):", "if s >= bs or (ge and s >= bs and s > 0):", A),
    ("高階職業表 +8", "return high_class_row(f7)[9]", "return high_class_row(f7)[8]", A),
    ("陣亡也縮放", 'pred = base if s["edi_new_hp"] == 0 else base * s["ebp_damage"] // u["mhp"]',
     'pred = base * s["ebp_damage"] // u["mhp"]', A),
    ("種類 3 改看種類 2", "want = [struct.unpack_from(\"<H\", rows, 3 * i + 1)[0] for i in range(n) if rows[3 * i] == 3]",
     "want = [struct.unpack_from(\"<H\", rows, 3 * i + 1)[0] for i in range(n) if rows[3 * i] == 2]", A),
    ("道具 78 的列", "ITEM79 = sbytes(0x602AD + 79 * ITEM_SIZE, ITEM_SIZE)", "ITEM79 = sbytes(0x602AD + 78 * ITEM_SIZE, ITEM_SIZE)", A),
    ("檢查數預期 36", "== (35, 21, 5), a", "== (36, 21, 5), a"),
    ("對照可以判符合", 'a["controls_fail_as_expected"] + a["controls_not_applicable"] == a["controls"]',
     'a["controls_fail_as_expected"] + a["controls_not_applicable"] < a["controls"]'),
    ("突變預期漏 1", '== "突變 12 個,抓到 12,漏掉 0"', '== "突變 12 個,抓到 11,漏掉 1"'),
    ("截圖對調", 'FILES = {"a1_k3_1.png": "grant_reward_rows_kind3_line_unit5_20261014.png", "a1b_k3_1.png"',
     'FILES = {"a1b_k3_1.png": "grant_reward_rows_kind3_line_unit5_20261014.png", "a1_k3_1.png"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_item79_aim_exp_reward_lines", MUTANTS))
