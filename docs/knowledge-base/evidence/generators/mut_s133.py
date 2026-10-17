"""ev_s133.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s133.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("HP 呼叫位元組改一個", '0x1AE8E: "0fb746400fb756426a03', '0x1AE8E: "0fb746400fb756426a02'),
    ("滿血色改 0x2a", "DIGIT_ADV, FULL_COLOR, PART_COLOR, WIDTH_MODE = 6, 0x1F, 0x2A, 3",
     "DIGIT_ADV, FULL_COLOR, PART_COLOR, WIDTH_MODE = 6, 0x2A, 0x1F, 3"),
    ("數字間距 7", "DIGIT_ADV, FULL_COLOR, PART_COLOR, WIDTH_MODE = 6, 0x1F, 0x2A, 3",
     "DIGIT_ADV, FULL_COLOR, PART_COLOR, WIDTH_MODE = 7, 0x1F, 0x2A, 3"),
    ("HP 列 + 0x16", "HP_X, HP_Y = 1 + 9, 0x9D + 0x15", "HP_X, HP_Y = 1 + 9, 0x9D + 0x16"),
    ("HP 橫向 + 10", "HP_X, HP_Y = 1 + 9, 0x9D + 0x15", "HP_X, HP_Y = 1 + 10, 0x9D + 0x15"),
    ("圖示框列 + 1", "BOX_X, BOX_Y = 1 + 6, 0x9D + 5", "BOX_X, BOX_Y = 1 + 6, 0x9D + 6"),
    ("預期用到模式 1", "assert sum(used_mode1.values()) == 0, used_mode1", "assert sum(used_mode1.values()) > 0, used_mode1"),
    ("模式 1 不計數", "            runs += 1\n", "            runs += 0\n"),
    ("數字格用 0xC0 codec", "w, h, px = digit(int(ch) + color, codec)", "w, h, px = digit(int(ch) + color, dec_c0)"),
    ("FDOTHER 第 4 個資源", "_o, _n = unpack_dat.parse_directory(_fd)[5]", "_o, _n = unpack_dat.parse_directory(_fd)[4]"),
    ("空白 sprite 也算", "exact = {t: [i for i in range(n_spr) if i not in blank and",
     "exact = {t: [i for i in range(n_spr) if True and"),
    ("D 預期 cycle 0", 'assert exact == {"D": [key * 12 + 1], "E": [key * 12 + 1], "F": [key * 12 + 0]}, exact',
     'assert exact == {"D": [key * 12 + 0], "E": [key * 12 + 1], "F": [key * 12 + 0]}, exact'),
    ("預期第 33 組", "assert (slot, key) == (0, 32), (slot, key)", "assert (slot, key) == (0, 33), (slot, key)"),
    ("預期 HP 不滿", "assert hp == {t: (823, 823) for t in \"DEF\"}, hp", "assert hp == {t: (823, 824) for t in \"DEF\"}, hp"),
    ("對照容許 0 不符", "assert all(bad > 0 for _, bad in c.values()), (name, c)", "assert all(bad == 0 for _, bad in c.values()), (name, c)"),
    ("數字格容許不符", "assert all(bad == 0 and known > 0 for known, bad in digits_only.values()), digits_only",
     "assert all(bad > 0 and known > 0 for known, bad in digits_only.values()), digits_only"),
    ("透明像素預期 D != F", 'assert all(BOX["D"][k] == BOX["E"][k] == BOX["F"][k] for k in both_open)',
     'assert not all(BOX["D"][k] == BOX["E"][k] == BOX["F"][k] for k in both_open)'),
    ("(10, 20) 預期 54", "assert in_cell_10_20 == 53, in_cell_10_20", "assert in_cell_10_20 == 54, in_cell_10_20"),
    ("框內差異預期少 1", 'assert len(diff_DF) == _s132["hud_pairs"]["D-F"]["band_diffs"]',
     'assert len(diff_DF) + 1 == _s132["hud_pairs"]["D-F"]["band_diffs"]'),
    ("lc131a 第 6 圈差預期 3", 'assert r6["lc131a"]["gap"] == 2 and', 'assert r6["lc131a"]["gap"] == 3 and'),
    ("lc131a 第 4、5 圈預期跨 tick", 'assert r6["lc131a"]["crossings_k4_k5"] == [0, 0], r6',
     'assert r6["lc131a"]["crossings_k4_k5"] == [0, 1], r6'),
    ("b、d 第 5 圈預期不跨", 'assert r6[n]["crossings_k4_k5"][1] == 1, r6', 'assert r6[n]["crossings_k4_k5"][1] == 0, r6'),
    ("b、d 差預期 >= 5", 'assert r6[n]["gap"] >= 3 and', 'assert r6[n]["gap"] >= 5 and'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s133", MUTANTS))
