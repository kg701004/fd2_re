"""ev_s182.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s182.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 靜態
    ("row19 只認種族 4", "row19 = t7 != 0x1C and race in (4, 5)", "row19 = t7 != 0x1C and race in (4,)"),
    ("row19 的 +7 條件反向", "row19 = t7 != 0x1C and race in (4, 5)", "row19 = t7 == 0x1C and race in (4, 5)"),
    ("腳步音配對錯返回點", "STEP_PLAY_RET = 0x3230C", "STEP_PLAY_RET = 0x32307"),
    # (B) 建構與身分
    ("己方出場數差 1", "assert k == CTL[m][1], (nm, m, k, CTL[m][1])", "assert k == CTL[m][1] + 1, (nm, m, k, CTL[m][1])"),
    ("出場記錄起點少算寶箱", "REC0 = 3 + 16 * 3 + 16 * 2 + 16 * 3", "REC0 = 3 + 16 * 3 + 16 * 2"),
    ("b1 取成 b2", "return CTL[m][REC0 + i * REC_LEN + 1]", "return CTL[m][REC0 + i * REC_LEN + 2]"),
    ("主導門檻九成九九", "DOMINANT = 0.9", "DOMINANT = 0.999"),
    ("不等自己那次建構", "and max(win[hit[0]][0], born.get(hit, 0)) <= c.seq < win[hit[0]][1]:",
     "and win[hit[0]][0] <= c.seq < win[hit[0]][1]:"),
    ("第一個基底也從建構起算", "win = {b: (first[b] if k else 0,", "win = {b: (first[b],"),
    ("隊長不是角色 0", "LEADER = 0 ", "LEADER = 9 "),
    ("隊長也算開機前的資料", "and lead_lo[c.regs[r]] <= c.seq < win[c.regs[r]][1]:", "and 0 <= c.seq < win[c.regs[r]][1]:"),
    ("CONTINUE 的基底差一格", "win = {sb: (0, float(\"inf\"))}", "win = {sb + STRIDE: (0, float(\"inf\"))}"),
    ("單位索引改從 0 數到記錄", "src = sorted({(g[\"map\"], u - g[\"own_deploy\"])", "src = sorted({(g[\"map\"], u)"),
    # (C) 實機單位表
    ("實機表錯一格", "assert [x[1] for x in t[5:21]] == [rec_b1(1, i) for i in range(16)], f",
     "assert [x[1] for x in t[4:20]] == [rec_b1(1, i) for i in range(16)], f"),
    # (D) 名稱
    ("兵種名不加 1", "return _NT[\"unit_types_by_index\"][str(key + 1)]", "return _NT[\"unit_types_by_index\"].get(str(key), \"\")"),
    ("角色名差 1", "return _NT[\"character_names_by_id\"][str(key)]", "return _NT[\"character_names_by_id\"][str(key + 1)]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s182", MUTANTS))
