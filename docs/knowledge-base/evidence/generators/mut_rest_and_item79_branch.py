"""ev_rest_and_item79_branch.py 的變異測試:每個變異改產生器或 lc124_analyze.py 裡一個判準 / 預測,
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。lc124_mut.py 是另一層(把紀錄改錯,要求分析判 FAIL),結果由產生器寫進證據。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

A = "lc124_analyze.py"
MUTANTS = [
    ("休息回 MaxHP / 4", "q = round(mhp / 5) if rounding else mhp // 5", "q = round(mhp / 5) if rounding else mhp // 4", A),
    ("休息不看滿血", "if hp == mhp or poison or para:", "if poison or para:", A),
    ("魔抗表不減 1", 'base = power * live_res[u["cls"] - 1] // 10', 'base = power * live_res[u["cls"]] // 10', A),
    ("傷害 8 / 10", "dmg = base * 9 // 10 + r2 * base // 1000", "dmg = base * 8 // 10 + r2 * base // 1000", A),
    ("命中判定反過來", "            if roll < hit:\n", "            if roll >= hit:\n", A),
    ("跳字位移 +3", "exp_dx.append(i * 5 + 2)", "exp_dx.append(i * 5 + 3)", A),
    ("沒命中的字形換一個", "exp_g += [0x74, 0x75, 0x76, 0x76]", "exp_g += [0x74, 0x75, 0x76, 0x77]", A),
    ("單位格上移 5 列", "y0 = VY + (uy - sy) * 24 - 6", "y0 = VY + (uy - sy) * 24 - 5", A),
    ("閃爍 9 幀", 'check(f"{tag} 閃爍幀數", fl == list(range(10))', 'check(f"{tag} 閃爍幀數", fl == list(range(9))', A),
    ("收尾 21 幀", "fin == list(range(22)) if full", "fin == list(range(21)) if full", A),
    ("法術列換第 4 列", "static_row3 = DL.object_bytes(data, meta, 0x619FD + 3 * 7, 7)",
     "static_row3 = DL.object_bytes(data, meta, 0x619FD + 4 * 7, 7)", A),
    ("檢查數預期 45", "== (44, 26, 3), a", "== (45, 26, 3), a"),
    ("對照可以判 PASS", 'a["controls_fail_as_expected"] + a["controls_not_applicable"] == a["controls"]',
     'a["controls_fail_as_expected"] + a["controls_not_applicable"] < a["controls"]'),
    ("突變預期 8 個", 'sum(x.startswith("抓到") for x in out["mutation"]["stdout"]) == 9',
     'sum(x.startswith("抓到") for x in out["mutation"]["stdout"]) == 8'),
    ("對照圖放大 3 倍", "cw0, ch0, z = 112, 84, 2", "cw0, ch0, z = 112, 84, 3"),
    ("對照圖收尾每幀都畫", "[f\"{tag}_fin{k:02d}\" for k in range(0, nfin, 2)]", "[f\"{tag}_fin{k:02d}\" for k in range(0, nfin, 1)]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_rest_and_item79_branch", MUTANTS))
