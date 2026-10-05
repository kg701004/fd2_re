"""ev_s74.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s74.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    ("DAC 只取高位(沒有 | v>>4)", "return (v6 << 2) | (v6 >> 4)", "return v6 << 2"),
    ("假資源以正常頭像規則取第 0 格(res + 0x10)", 'w, h = struct.unpack_from("<HH", res, res[0])', 'w, h = struct.unpack_from("<HH", res, 0x10)'),
    ("AIL_shutdown 只釋放 [0x538ac]", '[[20, "lib_buf_538ac"], [33, "ail_seq_53ed0"]]', '[[20, "lib_buf_538ac"]]'),
    ("16 MB 外讀到 0", 'rd["edi_h"] == "0x3f000000" and ad["eax_h"] == "0x3effffff"', 'rd["edi_h"] == "0x3f000000" and ad["eax_h"] == "0x3f000000"'),
    ("插入後 S 在空閒串列裡", '"0x1fa6b8": False, "0x1fd0c0": False', '"0x1fa6b8": True, "0x1fd0c0": False'),
    ("LOAD 的調色盤重載是 0x25f55 那次", '("l2", 1, "0x25f79", "0x25f7c", "0x22841c")', '("l2", 1, "0x25f5a", "0x25f7c", "0x22841c")'),
    ("CONTINUE / LOAD 真的釋放(有 0x3d685)", 'assert not has_stop(s, "0x3d685") and', 'assert has_stop(s, "0x3d685") and'),
    ("外框在上傳前就已變色", "[(0, 0, 0), pred0, pred0, (0, 0, 0)]", "[pred0, pred0, pred0, (0, 0, 0)]"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s74", MUTANTS))
