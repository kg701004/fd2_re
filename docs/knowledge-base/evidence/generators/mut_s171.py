"""ev_s171.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s171.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 紀錄本身
    # (bisect_right 是等價突變:E / R / A 的 n 沒有一筆剛好等於段的結尾)
    ("找段差一段", "r = lg.runs[bisect.bisect_left(ends, n)]", "r = lg.runs[bisect.bisect_left(ends, n) - 1]"),
    ("I 的邊界差一", "at = sum(1 for q in lg.irqs if q.n in ends and q.n in starts)",
     "at = sum(1 for q in lg.irqs if q.n + 1 in ends and q.n in starts)"),
    # (B) CF 分支
    ("看 CF 的段換成 0088:da3", "E3B = (\"p\", 0x88, 0xE3B) ", "E3B = (\"p\", 0x88, 0xDA3) "),
    ("短路門檻放寬到 41", "return \"short\" if 33 <= c <= 35 else", "return \"short\" if 33 <= c <= 41 else"),
    ("從 04f 起的長 run 也當迴圈", "return \"cf1_loop\" if r.count <= 5 else \"cf0_first\"",
     "return \"cf1_loop\" if r.count >= 5 else \"cf0_first\""),
    # (起點 051 / 052 那條規則在兩份紀錄裡沒有觸發過,改它不會有任何效果,不列)
    ("片段不往前追", "    while cf is None:\n", "    while cf is None and False:\n"),
    ("逐指令對齊兩邊對調", "DIFF = cs.diff_runs(CAL_EP, DLY_EP, LOG[\"lc171b\"].code)",
     "DIFF = cs.diff_runs(DLY_EP, CAL_EP, LOG[\"lc171b\"].code)"),
    ("結論的長路次數拿短路的", "delay 第一次 {CF['lc171a']['cf0_first|long']} 次全走長路",
     "delay 第一次 {CF['lc171a']['cf1_loop|short']} 次全走長路"),
    # (C) rep 多記
    ("rep 只認 repe / repne", "in (\"rep\", \"repe\", \"repne\")", "in (\"repe\", \"repne\")"),
    ("rep 不併", "if out and out[-1] == item and is_rep(*item):", "if out and out[-1] == item and is_rep(*item) and False:"),
    ("校準組混進 delay", "        if e.left_from == rt(CAL2):", "        if e.left_from in (rt(CAL2), rt(DLY)):"),
    # (D) MDI 型收中斷的點
    ("連軟體中斷一起算", "MDI_IRQ = [q for q in LA.irqs if q.type == 0 and", "MDI_IRQ = [q for q in LA.irqs if q.type <= 1 and"),
    ("看 I 之後那段而不是之前", "kind, i = LA.order[k - 1]", "kind, i = LA.order[k + 1]"),
    ("驅動位元組錯一格", "all(MDI_FILE[e:e + 16] == b for e, b in _drv)", "all(MDI_FILE[e + 1:e + 17] == b for e, b in _drv)"),
    ("掛勾判斷反了", "    if keys[i - 1] == HOOK:", "    if keys[i - 1] != HOOK:"),
    ("沒掛勾的排在後面", "\"without_first\": max(e.index for e, h in zip(MDI_ALL, _hook) if not h) < min(",
     "\"without_first\": max(e.index for e, h in zip(MDI_ALL, _hook) if not h) > min("),
    ("MDI 呼叫點換成 int 31h 的下一條", "_ep_of_irq[id(q)].left_from == rt(0x3F1A2)]",
     "_ep_of_irq[id(q)].left_from == rt(0x3F1A4)]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s171", MUTANTS))
