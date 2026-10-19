"""ev_s134.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s134.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("模式 1 位元組改成先寫再跳", '0x4E25D: "c0e902fec12af92af9ac47aae2fc"', '0x4E25D: "c0e902fec12af92af9acaa47e2fc"'),
    ("單位原點位元組改一個", "8b048201d081c3d8750000", "8b048201d081c3d8760000"),
    ("灰階遮罩 15", "GREY_MASK, GREY_BASE = 7, 0x18", "GREY_MASK, GREY_BASE = 15, 0x18"),
    ("預設次序改成先寫再跳", 'def render(s: int, order: str = "skip_then_value"', 'def render(s: int, order: str = "value_then_skip"'),
    ("先跳再寫的定義對調", '"skip_then_value": [None, v[0]]', '"skip_then_value": [v[0], None]'),
    ("兩格都寫的定義改成先跳再寫", '"value_both": [v[0], v[0]]', '"value_both": [None, v[0]]'),
    ("灰階版不換值", "(x & GREY_MASK) + GREY_BASE for x in vals]", "x for x in vals]"),
    ("模式 1 只算一倍長度", "            n *= 2\n", "            n *= 1\n"),
    ("上移 5 列", "UNIT_DY = (UNIT_ORIGIN - ORIGIN) // STRIDE", "UNIT_DY = (UNIT_ORIGIN - ORIGIN) // STRIDE + 1"),
    ("改看單位 #6", "ENEMY = 5 ", "ENEMY = 6 "),
    ("預期我方單位", "assert (EX, EY, EKEY, ue[\"D\"][6]) == (16, 14, 134, 1)", "assert (EX, EY, EKEY, ue[\"D\"][6]) == (16, 14, 134, 2)"),
    ("空白 sprite 也算", "exact = {t: [s for s in range(n_spr) if s not in blank and",
     "exact = {t: [s for s in range(n_spr) if True and"),
    ("D 預期 cycle 0", 'assert exact == {"D": [EKEY * 12 + 1], "E": [EKEY * 12 + 1], "F": [EKEY * 12 + 0]}, exact',
     'assert exact == {"D": [EKEY * 12 + 0], "E": [EKEY * 12 + 1], "F": [EKEY * 12 + 0]}, exact'),
    ("已知像素預期多 1", 'assert fit == {"D": (437, 0)', 'assert fit == {"D": (438, 0)'),
    ("時脈預期 F 為 1", '== {"D": 1, "E": 1, "F": 0}, sol_cycle', '== {"D": 1, "E": 1, "F": 1}, sol_cycle'),
    ("錯一列預期 339", 'assert shift == {-1: {"D": (437, 338)', 'assert shift == {-1: {"D": (437, 339)'),
    ("判準反過來:跳過的格 = 原值", "assert got_val == v[0] and got_skip != v[0], m1_pixels[t]",
     "assert got_val == v[0] and got_skip == v[0], m1_pixels[t]"),
    ("預期模式 1 長度 2", "assert len(rs) == 1 and rs[0][2] == 2, rs", "assert len(rs) == 1 and rs[0][2] == 4, rs"),
    ("兩幀預期同一張 sprite", 'assert m1_pixels["D"]["sprite"] != m1_pixels["F"]["sprite"]',
     'assert m1_pixels["D"]["sprite"] == m1_pixels["F"]["sprite"]'),
    ("對照容許 0 不符", "assert all(bad > 0 for _, bad in c.values()), (name, c)", "assert all(bad == 0 for _, bad in c.values()), (name, c)"),
    ("對調次序預期 2 個不符", '"value_then_skip": {"D": (437, 1)', '"value_then_skip": {"D": (437, 2)'),
    ("預期有 run 跨列", "assert crossing == 0, crossing", "assert crossing == 1, crossing"),
    ("模式 1 run 預期 817", "== (450, 818), (len(mode1_sprites), mode1_runs)", "== (450, 817), (len(mode1_sprites), mode1_runs)"),
    ("第 12 格預期有模式 1", "assert grp_mode1 == [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0]",
     "assert grp_mode1 == [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s134", MUTANTS))
