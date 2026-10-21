"""ev_s139.py 的變異測試:每個變異改一個判準 / 規則 / 解析,必須讓 ev_s139.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 解碼
    ("模式 1 改成先寫再跳過", "out[pos + 1:pos + 2 * n:2] = [body[i]] * len(range(pos + 1, min(pos + 2 * n, total), 2))",
     "out[pos:pos + 2 * n:2] = [body[i]] * len(range(pos, min(pos + 2 * n, total), 2))"),
    ("跨列判準錯一格", "if pos // w != (pos + span - 1) // w:", "if pos // w != (pos + span) // w:"),
    ("切列時模式 1 只算 n 格", "        pos += 2 * n if m == 1 else n\n    return [bytes(r) for r in rows]",
     "        pos += n\n    return [bytes(r) for r in rows]"),
    # 編碼規則
    ("R1 門檻 4", '    "run_min": 3, ', '    "run_min": 4, '),
    ("R2 關掉", '    "pair_as_run": True, ', '    "pair_as_run": False, '),
    ("R4 列尾也用模式 1", '    "mode1_at_row_end": False, ', '    "mode1_at_row_end": True, '),
    ("R5a 同值開新的", '    "after_mode1_same": "merge", ', '    "after_mode1_same": "new", '),
    ("R5b 滿 64 後不用模式 1", '    "after_mode1_full": "new", ', '    "after_mode1_full": "no", '),
    ("R5c 不同值也用模式 1", '    "after_mode1_diff": "no", ', '    "after_mode1_diff": "new", '),
    ("R6 剩下的仍用模式 0", '    "run_leftover_to_literal": True, ', '    "run_leftover_to_literal": False, '),
    ("上限 63", "CAP = 64 ", "CAP = 63 "),
    ("literal 每 32 個切一段", "for s in range(0, len(lit), CAP):", "for s in range(0, len(lit), 32):"),
    ("透明每 32 個切一段", "k = min(n, CAP)", "k = min(n, 32)"),
    # 容器
    ("FDICON 位移表沒有哨兵", "and _off[_n] == len(_d), (_w", "and _off[_n - 1] == len(_d), (_w"),
    ("FDICON 第一個圖示預期在表尾 6726", "assert FDICON_FIRST == 6730 == 6 + 4 * 1681", "assert FDICON_FIRST == 6726 == 6 + 4 * 1680"),
    ("FDSHAP 預期沒有重複", 'assert _dup == {"FDSHAP_060.bin": "FDSHAP_020.bin"}, _dup', "assert _dup == {}, _dup"),
    ("FDSHAP 預期 32 份", 'for m in range(33)], _shp', 'for m in range(32)], _shp'),
    ("幀數當 u16", "or d[0] != (o0 - 8) // 4:", 'or struct.unpack_from("<H", d, 0)[0] != (o0 - 8) // 4:'),
    ("旗標預期全是 0", '"frame_containers_by_flag_byte"] == {0: 249, 1: 15}', '"frame_containers_by_flag_byte"] == {0: 264}'),
    ("FIGANI 預期 1821 幀", '"FIGANI": 2118, "FDOTHER": 701}, ITEMS', '"FIGANI": 1821, "FDOTHER": 701}, ITEMS'),
    ("含模式 1 的個數門檻錯", 'st["items_with_mode1"] += m1 > 0', 'st["items_with_mode1"] += m1 > 1'),
    # 比對器與對照本身
    ("比對器瞎了", "                if e != o:", "                if e != o and False:"),
    ("整串比對少最後一個 byte", 'b"".join(orig) == body for name', 'b"".join(orig) == body[:-1] for name'),
    ("R5b 的消融其實沒改", '"R5b_full_as_no": {"after_mode1_full": "no"}', '"R5b_full_as_no": {"after_mode1_full": "new"}'),
    ("對照沒有改成 literal", "for k, lit in enumerate((False, True), 1):", "for k, lit in enumerate((False, False), 1):"),
    ("對照計數放錯欄", "                row[k] += used", "                row[1] += used"),
    ("錯寬對照含正確寬度", "for dw in (-1, 1)}", "for dw in (0, 1)}"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s139", MUTANTS))
