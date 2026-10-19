"""ev_lut_circle_ramp_frame_time_ch22_post.py 的變異測試:每個變異改產生器或 lc126_analyze.py 裡一個判準 / 預測,
必須讓產生器以 AssertionError 失敗(不能是其他例外)。變異版與輸出都在暫存目錄,不碰已提交的證據檔;
先跑未變異的對照(見 _mutrun.py)。lc126_mut.py 是另一層(把紀錄改錯,要求分析判不符合),結果由產生器寫進證據。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

A = "lc126_analyze.py"
MUTANTS = [
    ("戰後表第 21 格", "HANDLER = post_table(22)", "HANDLER = post_table(21)", A),
    ("戰後表不加 obj1 基底", "return struct.unpack(\"<I\", sbytes(0x51DE9 + idx * 4, 4))[0] + 0x10000",
     "return struct.unpack(\"<I\", sbytes(0x51DE9 + idx * 4, 4))[0]", A),
    ("dialog 14 之前章節預期 22", 'dlg["g"]["chap"] == 23 and dlg["dialog_idx"] == 14', 'dlg["g"]["chap"] == 22 and dlg["dialog_idx"] == 14', A),
    ("半徑每幀少加 1", "want = [(k, r0 + k * step) for k in range(10)]", "want = [(k, r0 + k * (step - 1)) for k in range(10)]", A),
    ("迴圈結束 ebx 預期 9", 'end is not None and end["ebx"] == 10', 'end is not None and end["ebx"] == 9', A),
    ("逐幀停預期多 tick", "a is not None and a == b, f\"逐幀 {a},不停 {b}\"", "a is not None and a > b, f\"逐幀 {a},不停 {b}\"", A),
    ("返回位址少 1", "int(ent[\"ret\"], 16) == site + 5,", "int(ent[\"ret\"], 16) == site + 4,", A),
    ("檢查數預期 22", "== (21, 1, 0), a", "== (22, 1, 0), a"),
    ("裂地術預期 9 tick", '"s12_frames": 10}, tm', '"s12_frames": 9}, tm'),
    ("每步 tick 加總不必相等", 'assert all(sum(t["tick_steps"]) == t["ticks_entry_to_loop_end"]',
     'assert not all(sum(t["tick_steps"]) == t["ticks_entry_to_loop_end"]'),
    ("第 3 次 lut 預期同地震術", "[[1, 15, 10], [1, 15, 10], [1, 30, 16]]", "[[1, 15, 10], [1, 15, 10], [1, 15, 10]]"),
    ("突變預期漏 1", '== "突變 14 個,抓到 14,漏掉 0"', '== "突變 14 個,抓到 13,漏掉 1"'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_lut_circle_ramp_frame_time_ch22_post", MUTANTS))
