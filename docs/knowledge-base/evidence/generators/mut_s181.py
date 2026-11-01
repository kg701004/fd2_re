"""ev_s181.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s181.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (P) 5 / 6
    ("展開與收起的兩格相同", 'and F["open"][1] != F["close"][1], F', 'and F["open"][1] == F["close"][1], F'),
    ("迴圈方向對調", '_dir == {"open": "jl", "sortie_open": "jl", "close": "jg", "sortie_close": "jg"}',
     '_dir == {"open": "jg", "sortie_open": "jg", "close": "jl", "sortie_close": "jl"}'),
    ("起始值不在兩格之中", "assert start in (first, int(m[3], 0)), (hex(site), init, first, m[3])",
     "assert start not in (first, int(m[3], 0)), (hex(site), init, first, m[3])"),
    ("test ebx 當成第 1 格", 'first = 0 if m[1] == "test ebx, ebx" else int(m[2], 0)', 'first = 1 if m[1] == "test ebx, ebx" else int(m[2], 0)'),
    ("法術段條件反向", "([S_SWAP, S_LIST] if has_spells else [])", "([S_SWAP, S_LIST] if not has_spells else [])"),
    ("收走與列表展開對調", "([S_SWAP, S_LIST] if has_spells else [])", "([S_LIST, S_SWAP] if has_spells else [])"),
    ("順序表 6 與列表對調", '"unit_list_bits_1a", "play 6", "draw_command_list", "play 5"',
     '"unit_list_bits_1a", "draw_command_list", "play 6", "play 5"'),
    ("跳過點在收起之後", "assert S_LIST < SKIP_TO < S_CLOSE, hex(SKIP_TO)", "assert S_CLOSE < SKIP_TO, hex(SKIP_TO)"),
    ("unit_list_bits_1a 不限本體那次", "\n                    and d.ret - DELTA == B_CARDS[_k].address + B_CARDS[_k].size]", "]"),
    ("記錄上限前的也當成截斷", "if capped_after is not None and hi > capped_after:", "if capped_after is not None:"),
    ("截斷段比到預測後段", "assert got == exp[:len(got)], (nm", "assert got == exp[len(exp) - len(got):] and got, (nm"),
    # (Q) 1 / 8 / 0xc
    ("index 1 接著的函式", '_r1["next_call"] == "town_hub_select"', '_r1["next_call"] == "town_hub_main"'),
    ("index 1 的按鍵 0x1d", '{"cmp eax, 0x1c", "cmp eax, 0x20"}', '{"cmp eax, 0x1d", "cmp eax, 0x20"}'),
    ("index 8 只有開", 'sorted(r["func"] for r in CTX[8]) == ["action_ring_close", "action_ring_open"]',
     'sorted(r["func"] for r in CTX[8]) == ["action_ring_open", "action_ring_open"]'),
    ("index 0xc 走 handle A", 'all(r["handle"] == "B" for r in CTX[0xC])', 'all(r["handle"] == "A" for r in CTX[0xC])'),
    ("寶箱回答 0", '"cmp ebx, 1" in _c["field_cell_treasure_check"]["cmp_before"]', '"cmp ebx, 0" in _c["field_cell_treasure_check"]["cmp_before"]'),
    ("呼叫點往前只看 1 條", "ins[max(0, n - 12):n] if target(i) in _NM]", "ins[max(0, n - 1):n] if target(i) in _NM]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s181", MUTANTS))
