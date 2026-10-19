"""ev_cmd_table_0_9_coverage_lut_cycles.py 的變異測試:每個變異改產生器或 lc129t_analyze.py 裡一個判準 / 預測,
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。lc129_analyze.py 以子行程執行(不受這裡的變異影響),由 lc129_mut.py 的 15 個突變把關,
結果由產生器寫進證據。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

T = "lc129t_analyze.py"
MUTANTS = [
    ("預測區間改窄", "PRED = {(2500, 12): (17, 24),", "PRED = {(2500, 12): (17, 21),", T),
    ("裂地術呼叫點錯一條", "SITES = {11: 0x2187B, 12: 0x21ABA}", "SITES = {11: 0x2187B, 12: 0x21ABC}", T),
    ("迴圈結束站換成 redraw 之後", "LUT, FRAME, END, AFTER = 0x2189A, 0x2198E, 0x21998, 0x219A8",
     "LUT, FRAME, END, AFTER = 0x2189A, 0x2198E, 0x219A8, 0x21998", T),
    ("半徑每幀少加", "and [s[\"radius\"] for s in fr] == [r0 + k * step for k in range(len(fr))]",
     "and [s[\"radius\"] for s in fr] == [r0 + k * (step - 1) for k in range(len(fr))]", T),
    ("H0 容許 9 tick", "h0 = all(abs(v - w) <= 1 for sp", "h0 = all(abs(v - w) <= 9 for sp", T),
    ("單調改成遞增", "check(f\"法術 {sp}:2500 > 5000 > 10000\", seq[0] > seq[1] > seq[2],",
     "check(f\"法術 {sp}:2500 > 5000 > 10000\", seq[0] < seq[1] < seq[2],", T),
    ("跑過的格預期含 1", "assert out[\"cmd_table_0_9\"][\"ran_in_traces\"] == [0, 3, 4, 6, 9]",
     "assert out[\"cmd_table_0_9\"][\"ran_in_traces\"] == [0, 1, 3, 4, 6, 9]"),
    ("靜態檢查預期 11 項", 'len(out["cmd_table_0_9"]["checks"]) == 10', 'len(out["cmd_table_0_9"]["checks"]) == 11'),
    ("10000 地震術預期 4 tick", '"10000_11": [3]', '"10000_11": [4]'),
    ("預測文字預期 18..24", "約 20 tick(容許 17..24)\" in pred", "約 20 tick(容許 18..24)\" in pred"),
    ("突變預期漏 1", '== "抓到 15 / 15,漏掉 0"', '== "抓到 14 / 15,漏掉 1"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_cmd_table_0_9_coverage_lut_cycles", MUTANTS))
