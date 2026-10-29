"""ev_s166.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s166.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 原始紀錄
    ("不扣截斷那一筆", "assert _lines == len(REC) + 1,", "assert _lines == len(REC),"),
    ("入口沒多 redraw", "== [REDRAW] and set(_e163) <= set(ENTRIES)", "== [] and set(_e163) <= set(ENTRIES)"),
    ("沒有閒置", "RUN[\"idle_s\"] == 30.0", "RUN[\"idle_s\"] == 0.0"),
    # (B) 格點
    ("週期當 5 ms 整", "P = S161[\"timer_channels\"][\"pit_divisor\"] / 1193182 * 1000", "P = 5.0"),
    ("格點不加 0.2 容差", "slot[int((t - g0 + 0.2) // P)].append(t)", "slot[int((t - g0) // P)].append(t)"),
    ("不算合併", "lost = nre + len(empty)", "lost = nre"),
    ("從 MDI 起算", "dig0 = next(r[\"t\"] for r in rec if r[\"k\"] == \"E\" and r[\"eip\"] == DIG)",
     "dig0 = next(r[\"t\"] for r in rec if r[\"k\"] == \"E\" and r[\"eip\"] == MDI)"),
    ("切點用最後一次 redraw", "G = grid(REC, REDRAW_T[0])", "G = grid(REC, REDRAW_T[-1])"),
    ("BIOS tick 55 ms", "BIOS_MS = 54.925", "BIOS_MS = 55.0"),
    ("對照只比重入", "(G163[\"slots\"], G163[\"reentry\"], G163[\"merged\"], G163[\"lost\"]) == (_l[\"slots\"], _l[\"reentry\"], _l[\"merged\"], _l[\"total\"])",
     "(G163[\"slots\"], G163[\"reentry\"], G163[\"merged\"], G163[\"lost\"]) == (_l[\"slots\"], _l[\"reentry\"], 0, _l[\"reentry\"])"),
    # (C) 分型
    ("DIG 型預測 92", "\"DIG\": {EPI: _pd[\"dig_restore\"][hex(EPI)],", "\"DIG\": {EPI: _pd[\"dig_restore\"][hex(EPI)] - 1,"),
    ("MDI 型看下一筆是 MDI", "elif q[\"k\"] == \"E\" and q[\"eip\"] == DIG and d == PRED_DI[\"MDI\"]:",
     "elif q[\"k\"] == \"E\" and q[\"eip\"] == MDI and d == PRED_DI[\"MDI\"]:"),
    ("同格再叫不認", "elif q[\"k\"] == \"E\" and q[\"eip\"] == MDI and d == PRED_DI[\"MDI_AGAIN\"]:",
     "elif False:"),
    ("長服務門檻 55", "LONG_DIG[seg] += r[\"i\"] - e[\"i\"] > 10000", "LONG_DIG[seg] += r[\"i\"] - e[\"i\"] > 55"),
    # (D) 預測
    ("P1 門檻 0.96", "if REENTRY_SHARE >= 0.9 else", "if REENTRY_SHARE >= 0.96 else"),
    ("P3 下界 0.5%", "if 0.01 <= BAT[\"fraction\"] <= 0.03 else", "if 0.005 <= BAT[\"fraction\"] <= 0.03 else"),
    ("P4 下界 55", "if 55.5 <= BAT[\"bios_tick_avg_ms\"] <= 56.5 else", "if 55.0 <= BAT[\"bios_tick_avg_ms\"] <= 56.5 else"),
    ("判定讀戰場前", "REENTRY_SHARE = round(BAT[\"reentry\"] / BAT[\"lost\"], 4)", "REENTRY_SHARE = round(PRE[\"reentry\"] / PRE[\"lost\"], 4)"),
    ("預測檔改過", "assert \"P3 掉的比例在 1% .. 3% 之間\" in _pred", "assert \"P3 掉的比例在 0.5% .. 3% 之間\" in _pred"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s166", MUTANTS))
