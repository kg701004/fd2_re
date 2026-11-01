"""ev_s183.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s183.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 靜態
    ("名字不加 1", "NAME_ADD = 1 ", "NAME_ADD = 0 "),
    ("名字鍵取 +7", "NAME_FIELD = 8", "NAME_FIELD = 7"),
    ("單位索引取第 2 個參數", "UNIT_ARG = (0x28 - FRAME) // 4 - 1", "UNIT_ARG = (0x28 - FRAME) // 4 - 2"),
    ("框架少算一個 push", "FRAME = 4 * 4 + 0xC", "FRAME = 3 * 4 + 0xC"),
    ("畫名字配錯返回點", "NAME_RET = 0x18D84", "NAME_RET = 0x18D7F"),
    ("s1 對照錯資源", "FDTXT/FDTXT_000.bin", "FDTXT/FDTXT_001.bin"),
    # (B) 每份紀錄
    ("永遠用第一個基底", "return order[max(0, bisect.bisect_right(starts, seq) - 1)]", "return order[0]"),
    ("子函式的 esi 對照錯一格", "assert all(v == rec for v, _k in inner)", "assert all(v == rec + STRIDE for v, _k in inner)"),
    # 「子函式從函式開頭算」是等價變異:esi 設好之前唯一的呼叫 0x3702f(堆疊檢查)不在 cl 紀錄的入口清單裡,不列
    ("esi 之後還有寫入也不管", "op_str.startswith(\"esi\") or", "op_str.startswith(\"esi:\") or"),
    ("記錄序號不扣己方出場數", "src = [(g[\"map\"], u - g[\"own_deploy\"]) for g", "src = [(g[\"map\"], u) for g"),
    ("出場記錄起點少算寶箱", "REC0 = 3 + 16 * 3 + 16 * 2 + 16 * 3", "REC0 = 3 + 16 * 3 + 16 * 2"),
    ("b1 取成 b2", "return CTL[m][REC0 + i * REC_LEN + 1]", "return CTL[m][REC0 + i * REC_LEN + 2]"),
    ("續一百八十二對照差 1", "assert r182 == {k8}, (nm, hex(b), u, r182, k8)", "assert r182 == {k8 + 1}, (nm, hex(b), u, r182, k8)"),
    # (C) 名稱
    ("角色名不加 1", "((\"character_names_by_id\", \"角色名\", 1)", "((\"character_names_by_id\", \"角色名\", 0)"),
    ("空字串段只認大寫", "if \"empty\" in _v.lower():", "if \"EMPTY\" in _v:"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s183", MUTANTS))
