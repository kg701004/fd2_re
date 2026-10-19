"""ev_s135.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s135.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("地形模式 1 位元組改成先寫再跳", '0x4E052: M1_LOOP + "8a44050047aae2fc"', '0x4E052: M1_LOOP + "8a440500aa47e2fc"'),
    ("地圖格重畫的位元組改一個", '0x4E0DE: M1_LOOP + "8a44050047aae2fc"', '0x4E0DE: M1_LOOP + "8a44050147aae2fc"'),
    ("迴圈判準改成 loop 跳 3 bytes", "body[3] == 0x100 - 4", "body[3] == 0x100 - 3"),
    ("先跳再寫的定義對調", "                    px[p + 2 * j + 1] = v\n", "                    px[p + 2 * j] = v\n"),
    ("兩格都寫只寫一格", "px[p + 2 * j] = px[p + 2 * j + 1] = v", "px[p + 2 * j + 1] = v"),
    ("圖示預期有長度 2", "assert fdicon_m1 == {1: 818}, fdicon_m1", "assert fdicon_m1 == {1: 817, 2: 1}, fdicon_m1"),
    ("地形預期 6 個長度 2", "== {1: 325, 2: 5}, shap_total", "== {1: 325, 2: 6}, shap_total"),
    ("長度 1 也列進長 run", 'if m == 1 and k > 1]', 'if m == 1 and k > 0]'),
    ("地圖 25 圖塊 38 預期 6 格", '{"25:38": 7,', '{"25:38": 6,'),
    ("FDFIELD 配對錯一個資源", 'fp = FIELD / f"FDFIELD_{3 * m:03d}.bin"', 'fp = FIELD / f"FDFIELD_{3 * m + 1:03d}.bin"'),
    ("tileset 對地圖錯一張", 'm = int(r["tileset"][7:10]) // 2', 'm = int(r["tileset"][7:10]) // 2 + 1'),
    ("VGA 幀預期 184 個檔", "assert len(frame_files) == 185, len(frame_files)", "assert len(frame_files) == 184, len(frame_files)"),
    ("不去重複", "    if h in frame_sha.values():\n        continue\n", ""),
    ("單位上移 5 列", "UNIT_DY = -6 ", "UNIT_DY = -5 "),
    ("全中門檻 600 像素", "MIN_KNOWN = 100 ", "MIN_KNOWN = 600 "),
    ("空白 sprite 也算全中", "return [int(s) for s in np.where((bad == 0) & NONBLANK)[0]]",
     "return [int(s) for s in np.where(bad == 0)[0]]"),
    ("對手假說不重算模式 1 的 sprite", "                    bad[HAS_M1] = ", "                    _ = "),
    ("對手預期帶模式 1 的 1 處", '"value_then_skip": {"unique_hits": 658, "with_mode1": 0,', '"value_then_skip": {"unique_hits": 658, "with_mode1": 1,'),
    ("子集判準反過來", "assert all(set(hits[o]) <= skip_set for o in ORDERS[1:])", "assert all(set(hits[o]) >= skip_set for o in ORDERS[1:])"),
    ("判準反過來:跳過格 = 值才算", 'e["discriminating"] += skipped != v', 'e["discriminating"] += skipped == v'),
    ("sprite 361 預期 34 處", '"361:0,20": 35,', '"361:0,20": 34,'),
    ("灰階遮罩 15", "(SPR[\"skip_then_value\"] & 7) + 0x18", "(SPR[\"skip_then_value\"] & 15) + 0x18"),
    ("地形預期 93 格", 'assert terrain == {"0,0": 94,', 'assert terrain == {"0,0": 93,'),
    ("模式 1 sprite 預期 449 張", "== 1455 and int(HAS_M1.sum()) == 450", "== 1455 and int(HAS_M1.sum()) == 449"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s135", MUTANTS))
