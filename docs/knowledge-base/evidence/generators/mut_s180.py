"""ev_s180.py 的變異測試:每個變異改一個判準 / 推導,必須讓 ev_s180.py 以 AssertionError 失敗(不能是其他例外)。
推導類的變異(計數、函式欄、index 寫法)要靠「與 doc36 表格逐格比對」那條抓到 —— 證明表格核對有鑑別力。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (S) 靜態列舉
    ("不收 jmp 跳入的路徑", "paths.append((src, INSNS[_IX[src] - 1]))", "paths += []"),
    ("UI 池當成 [0x53b13]", 'POOL_PUSH = "push dword ptr [0x3eec]"', 'POOL_PUSH = "push dword ptr [0x3b13]"'),
    ("共用尾端屬於別的函式", '_NM[func_of(a)] == "play_step_sfx" for', '_NM[func_of(a)] == "play_sfx" for'),
    ("舊 0xb 位址換成真的呼叫端", "OLD_0B = 0x2CAC3", "OLD_0B = 0x322FF"),
    # (L) cl1 .. cl14
    ("返回位址減 4", "k, call = c.stack[1], c.ret - DELTA - 5", "k, call = c.stack[1], c.ret - DELTA - 4"),
    ("池播放次數與續一百七十九差 1", 'assert len(plays) == S179["cl_logs"][nm]["pool_plays"]',
     'assert len(plays) + 1 == S179["cl_logs"][nm]["pool_plays"]'),
    ("cl 的 index 不必有靜態呼叫端改成反向", "assert set(CL_N) <= set(BY_IDX)", "assert set(CL_N) >= set(BY_IDX)"),
    ("index 10 不存在", "assert N10 > 0 and", "assert N10 == 0 and"),
    ("函式別次數重複計", "CL_BY_FUNC[k][_NM[func_of(call)]] += 1", "CL_BY_FUNC[k][_NM[func_of(call)]] += 2"),
    # 表格各欄的推導(由 doc36 逐格比對抓)
    ("handle B 不計", 'b = sum(s["target"] == PLAY_B for s in v)', "b = 0 * len(v)"),
    ("防拷走不到的不計", 'dead = sum(func_of(s["call"]) == CP for s in v)', "dead = 0 * len(v)"),
    ("cl 次數重複計", "CL_N[k] += 1", "CL_N[k] += 2"),
    ("函式欄改依名稱排序", 'dict.fromkeys(_NM[func_of(s["idx_at"])] for s in v))', 'sorted({_NM[func_of(s["idx_at"])] for s in v}))'),
    ("index 一律寫十進位", "return str(k) if k < 10 else hex(k)", "return str(k)"),
    # (D) doc36
    ("表頭第二欄改名", '"index", "靜態呼叫端", "呼叫端函式(登錄名)"', '"index", "呼叫端數量", "呼叫端函式(登錄名)"'),
    ("表格讀到下一張表", "    elif _tbl:\n        break", "    elif _tbl and False:\n        break"),
    ("總數句用舊的 107", "[(str(N_CALLS[PLAY_A]), str(N_CALLS[PLAY_B]))]", "[(str(N_CALLS[PLAY_A] - 4), str(N_CALLS[PLAY_B]))]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s180", MUTANTS))
