"""ev_s167.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s167.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 原始紀錄、時段
    ("不扣截斷那一筆", "assert _lines == len(REC) + 1,", "assert _lines == len(REC),"),
    ("標記少一個", "== sorted(MARKERS) and set(_e166) <= set(ENTRIES)", "== sorted(MARKERS[1:]) and set(_e166) <= set(ENTRIES)"),
    ("第一次結束回合當成功", "assert RUN[\"ok\"] is False and", "assert RUN[\"ok\"] is True and"),
    ("同速門檻收緊", "all(0.98 <= v <= 1.02 for v in SPEED.values())", "all(1.0 <= v <= 1.02 for v in SPEED.values())"),
    ("P 不扣開頭 1 秒", "WIN = {\"P\": (Pa + LEAD_MS, Pb - TAIL_MS),", "WIN = {\"P\": (Pa, Pb - TAIL_MS),"),
    ("敵方回合從友軍起算", "\"EN\": (T[\"E_enemy\"], T[\"R_enemy\"])", "\"EN\": (T[\"E_friend\"], T[\"R_enemy\"])"),
    ("P2 晚 3 秒起算", "\"P2\": (Pc + LEAD_MS, Pd - TAIL_MS),", "\"P2\": (Pc + LEAD_MS + 3000, Pd - TAIL_MS),"),
    # (B) 格點
    ("週期當 5 ms 整", "P = S161[\"timer_channels\"][\"pit_divisor\"] / 1193182 * 1000", "P = 5.0"),
    ("格點不加 0.2 容差", "slot[int((t - g0 + 0.2) // P)].append(t)", "slot[int((t - g0) // P)].append(t)"),
    ("不算合併", "lost = nre + len(empty)", "lost = nre"),
    ("從 MDI 起算", "dig0 = next(r[\"t\"] for r in rec if r[\"k\"] == \"E\" and r[\"eip\"] == DIG)",
     "dig0 = next(r[\"t\"] for r in rec if r[\"k\"] == \"E\" and r[\"eip\"] == MDI)"),
    ("對照只比重入", "(G163[\"slots\"], G163[\"reentry\"], G163[\"merged\"], G163[\"lost\"]) == (_l[\"slots\"], _l[\"reentry\"], _l[\"merged\"], _l[\"total\"])",
     "(G163[\"slots\"], G163[\"reentry\"], G163[\"merged\"], G163[\"lost\"]) == (_l[\"slots\"], _l[\"reentry\"], 0, _l[\"reentry\"])"),
    # (C) 分型、長服務
    ("DIG 型預測 92", "\"DIG\": {EPI: _pd[\"dig_restore\"][hex(EPI)],", "\"DIG\": {EPI: _pd[\"dig_restore\"][hex(EPI)] - 1,"),
    ("MDI 型看下一筆是 MDI", "if q[\"k\"] == \"E\" and q[\"eip\"] == DIG and d == PRED_DI[\"MDI\"]:",
     "if q[\"k\"] == \"E\" and q[\"eip\"] == MDI and d == PRED_DI[\"MDI\"]:"),
    ("同格再叫不認", "if q[\"k\"] == \"E\" and q[\"eip\"] == MDI and d == PRED_DI[\"MDI_AGAIN\"]:", "if False:"),
    ("長服務門檻 55", "LONG_I = 10000", "LONG_I = 55"),
    ("未歸類離 P 很遠", "assert max(o[\"t\"] for o in OTHER) < WIN[\"P\"][0] and", "assert max(o[\"t\"] for o in OTHER) < WIN[\"P\"][0] - 10000 and"),
    # (D) 預測
    ("P1 下界 0.5%", "if 0.003 <= PS[\"fraction\"] <= 0.008 else", "if 0.005 <= PS[\"fraction\"] <= 0.008 else"),
    ("P2 上界 2%", "0.005 <= ENS[\"fraction\"] <= 0.03 else", "0.005 <= ENS[\"fraction\"] <= 0.02 else"),
    ("P4 門檻 0.995", "if min(SHARE.values()) >= 0.9 else", "if min(SHARE.values()) >= 0.995 else"),
    ("P5 門檻 0.01 pp", "if abs(P2S[\"fraction\"] - PS[\"fraction\"]) <= 0.003 else", "if abs(P2S[\"fraction\"] - PS[\"fraction\"]) <= 0.0001 else"),
    ("P6 反向", "if SS[\"mdi_per_1000_slots\"] > PS[\"mdi_per_1000_slots\"] else", "if SS[\"mdi_per_1000_slots\"] < PS[\"mdi_per_1000_slots\"] else"),
    ("判定讀 P2_loop", "PS, ENS, P2S, SS = SEG[\"P\"], SEG[\"EN\"], SEG[\"P2\"], SEG[\"S\"]",
     "PS, ENS, P2S, SS = SEG[\"P\"], SEG[\"EN\"], SEG[\"P2_loop\"], SEG[\"S\"]"),
    ("預測檔改過", "(\"P1 P 的比例在 0.3% .. 0.8%\",", "(\"P1 P 的比例在 0.2% .. 0.8%\","),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s167", MUTANTS))
