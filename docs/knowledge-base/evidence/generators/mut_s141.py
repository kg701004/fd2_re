"""ev_s141.py 的變異測試:每個變異改一個判準 / 解碼 / 對照,必須讓 ev_s141.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 解碼
    ("模式 1 先寫值再寫透明", "out += bytes([0, body[i]]) * n", "out += bytes([body[i], 0]) * n"),
    ("literal 對照沒有改成 literal", "if m == 1 and mode1_literal:", "if m == 1 and False:"),
    ("緩衝只疊四幀", "for n in range(69, 74)]", "for n in range(69, 73)]"),
    # 實拍取樣
    ("遊戲區左緣錯 2 px(= 1 個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 194, 201 "),
    # 判準本身
    ("比對器瞎了(每組取總和而非最大)", "return int(np.maximum.reduceat(c, starts).sum())", "return int(np.add.reduceat(c, starts).sum())"),
    ("乾淨門檻 0.5", "CLEAN = 0.999 ", "CLEAN = 0.5 "),
    ("撕裂拼接下半段沒有差一列", "buf[dy1 - 1 + cut:dy1 - 1 + WIN]", "buf[dy1 + cut:dy1 + WIN]"),
    ("乾淨幀比例要求 95%", "assert len(clean) >= 0.75 * len(pre)", "assert len(clean) >= 0.95 * len(pre)"),
    ("捲動方向預期往下", "assert all(x >= y for x, y in zip(dys, dys[1:])), dys", "assert all(x <= y for x, y in zip(dys, dys[1:])), dys"),
    ("預期捲到 dy = 0", "assert pre[-1] in clean and last_dy > 0,", "assert pre[-1] in clean and last_dy == 0,"),
    ("預期不是原版 EXE", 'assert META["exe_md5"] == "33464c81e6a364fd0660141139aa8e6e"', 'assert META["exe_md5"] == "b97caf2239a27a896069d03549d96e1e"'),
    # 對照本身
    ("虛無沒有平移", "na, nb, _ = scores(BD, col, dy, dx=1)", "na, nb, _ = scores(BD, col, dy, dx=0)"),
    ("literal 的撕裂拼接其實用 dither 緩衝", 'r["literal_tear"] = tear(BL, col_of[r["shot"]], r["literal"]["dy"])',
     'r["literal_tear"] = tear(BD, col_of[r["shot"]], r["dither"]["dy"])'),
    ("黑幕分段:把非黑幀也算進黑幕", 'while g1 + 1 < len(rows) and rows[g1 + 1]["nonblack"] == 0:',
     'while g1 + 1 < len(rows) and rows[g1 + 1]["nonblack"] >= 0:'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s141", MUTANTS))
