"""ev_s185.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s185.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 模式 5 分支
    ("模式記成 4", "MODE_GRAB = 5", "MODE_GRAB = 4"),
    ("播放點前移一條", "SITE_AI, SITE_CHEST = 0x13D13, 0x191A9", "SITE_AI, SITE_CHEST = 0x13D0D, 0x191A9"),
    ("之後寫成模式 1", '"mov byte ptr [ebx + 0x34], 7"', '"mov byte ptr [ebx + 0x34], 1"'),
    ("事件號取 +0x3c", '"movzx ebp, byte ptr [ebx + 0x3d]"', '"movzx ebp, byte ptr [ebx + 0x3c]"'),
    ("分支範圍止於播放點", "assert 0x13C22 <= SITE_AI < 0x13D29", "assert 0x13C22 <= SITE_AI < 0x13D13"),
    # 0xc 播放點與呼叫點
    ("0xc 只找 handle A", "if t in (PLAY_A, PLAY_B) and k >= 2", "if t == PLAY_A and k >= 2"),
    ("index 記成 0xb", "int(ins[k - 2].op_str, 0) == 0xC:", "int(ins[k - 2].op_str, 0) == 0xB:"),
    ("test edx, edx 當陣營 2", 'return 0 if text == "test edx, edx"', 'return 2 if text == "test edx, edx"'),
    ("陣營讀 +7", 'insn(g - 4) == "movzx edx, byte ptr [eax + 6]"', 'insn(g - 4) == "movzx edx, byte ptr [eax + 7]"'),
    # (C) 格子判準
    ("可見判準用 0x40", "CHEST_MASK, CHEST_VISIBLE = 0x60, 0x20", "CHEST_MASK, CHEST_VISIBLE = 0x60, 0x40"),
    # 「x 外圈 y 內圈」不列:每個被引用的事件號只有一格可見寶箱(ev_s185 已斷言),掃描順序依構造不影響結果
    ("唯一格放寬成兩格", "if f == CHEST_VISIBLE and s == ev) == 1, (m, k, ev)", "if f == CHEST_VISIBLE and s == ev) == 2, (m, k, ev)"),
    ("不跳過寬高", "            o = 4 + (y * w + x) * 4", "            o = (y * w + x) * 4"),
    ("槽號取 byte 3", "comp[o + 2] & 0x1F, terr[tile * 4]", "comp[o + 3] & 0x1F, terr[tile * 4]"),
    ("地形取 byte 1", "terr[tile * 4] & CHEST_MASK", "terr[tile * 4 + 1] & CHEST_MASK"),
    ("FDSHAP 取第 2N 個", "SHP[m * 2 + 1].read_bytes()", "SHP[m * 2].read_bytes()"),
    # (D) 記錄
    ("模式比 +0x35", 'if u["native_record_byte34"] & 0xF != MODE_GRAB', 'if u["native_record_byte35"] & 0xF != MODE_GRAB'),
    ("事件號取 b3", 'ev, b0 = u["native_record_byte3d"], u["native_record_byte6"]',
     'ev, b0 = u["native_source_byte3"], u["native_record_byte6"]'),
    ("出場格不對齊記錄", "sx, sy = pos[k][0], pos[k][1]", "sx, sy = pos[k + 1][0], pos[k + 1][1]"),
    ("己方也算走得到", '"reaches_dispatch": b0 in DISPATCH_CAMPS', '"reaches_dispatch": True'),
    ("星之眼 tile 記成 164", "assert _star == (18, 37, 166, 0, CHEST_VISIBLE)", "assert _star == (18, 37, 164, 0, CHEST_VISIBLE)"),
    # 開場單位表順序(續一百八十七)
    ("開場 spawn group 1", '(0x10B3C, "push 0",', '(0x10B3C, "push 1",'),
    ("group 讀 +0x14", '"movzx eax, byte ptr [eax + 0x15]"', '"movzx eax, byte ptr [eax + 0x14]"'),
    ("單位表每筆 0x28", '(0x10C76, "shl eax, 4", "× 0x50")', '(0x10C76, "shl eax, 3", "× 0x50")'),
    ("單位號用記錄序號", '"unit": info["own_deploy"] + g0.index(k)', '"unit": info["own_deploy"] + k'),
    ("名次含所有記錄", 'g0 = [k for k, u in enumerate(info["units"]) if u["group"] == 0]', 'g0 = list(range(len(info["units"])))'),
    ("記錄 0 記成 group 0", '_INFO10["units"][0]["group"] == 1', '_INFO10["units"][0]["group"] == 0'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s185", MUTANTS))
