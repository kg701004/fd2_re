"""ev_s145.py 的變異測試:每個變異改一個判準 / 解碼 / 由 EXE 讀出的常數,必須讓 ev_s145.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # 解碼與取樣
    ("調色盤 6 → 8 bit 少了低兩位", "a = (a << 2) | (a >> 4)", "a = a << 2"),
    ("遊戲區左緣錯 2 px(= 1 個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 194, 201 "),
    ("預期不是原版 EXE", 'MD5 = "33464c81e6a364fd0660141139aa8e6e"', 'MD5 = "b97caf2239a27a896069d03549d96e1e"'),
    # 判準本身
    ("逐列判準退化成整張判準", "r = np.repeat(np.arange(200, dtype=np.int64), 320)", "r = np.zeros(64000, dtype=np.int64)"),
    ("單色畫面沒有排除(退化樣本)", "    if len(u) == 1:\n", "    if len(u) == 0:\n"),
    ("撕裂改成隔一個 dy", "pairs = [(d, d + 1) for d in range(MAX_DY)]", "pairs = [(d, d + 2) for d in range(MAX_DY - 1)]"),
    ("選單方框容許整張 0.1%", "assert diff.sum() < 0.02 * diff.size", "assert diff.sum() < 0.001 * diff.size"),
    # 由 EXE 讀出的常數
    ("ANI 觸發的 esi 差 1", "T_ANI = code(0x1fadd, 3)[2] ", "T_ANI = code(0x1fadd, 3)[2] + 1 "),
    ("浮空城觸發的 esi 差 1", "T_CASTLE = code(0x1fba4, 3)[2] ", "T_CASTLE = code(0x1fba4, 3)[2] + 1 "),
    ("浮空城的圖與調色盤對調", "CASTLE_PAL, CASTLE_IMG = code(0x1fbab, 4)[1], code(0x1fbab, 4)[3]",
     "CASTLE_IMG, CASTLE_PAL = code(0x1fbab, 4)[1], code(0x1fbab, 4)[3]"),
    ("停留多 500 ms", 'HOLD_MS = struct.unpack("<I", code(0x1fc4d, 4))[0] ', 'HOLD_MS = struct.unpack("<I", code(0x1fc4d, 4))[0] + 500 '),
    ("轉場目標紅色少 1", "RED6 = code(0x1fc71, 2)[1] ", "RED6 = code(0x1fc71, 2)[1] - 1 "),
    ("轉場每步多 10 ms", "TRANS_MS = code(0x1fc83, 2)[1] ", "TRANS_MS = code(0x1fc83, 2)[1] + 10 "),
    ("閃光步數少 3", "FLASH_STEPS = code(0x1fc08, 5)[4]", "FLASH_STEPS = code(0x1fc08, 5)[4] - 3"),
    ("標題調色盤錯一號", "TITLE_IMG, TITLE_PAL = code(0x1fcb6, 2)[1], code(0x1fccf, 2)[1]",
     "TITLE_IMG, TITLE_PAL = code(0x1fcb6, 2)[1], code(0x1fccf, 2)[1] + 1"),
    # 各段的方向
    ("ANI 幀序預期遞減", "assert all(x <= y for x, y in zip(k0, k0[1:])), k0", "assert all(x >= y for x, y in zip(k0, k0[1:])), k0"),
    ("淡出 / 淡入方向對調", "assert nb_out[0] > nb_out[-1] and nb_in[0] < nb_in[-1]", "assert nb_out[0] < nb_out[-1] and nb_in[0] > nb_in[-1]"),
    ("紅閃光預期 R 下降", "assert all(a[0] < b[0] and a[1] > b[1]", "assert all(a[0] > b[0] and a[1] > b[1]"),
    ("logo 末幀預期變暗", 'assert lum(S["ani1_out"][-1]) > lum(S["ani1"][-1])', 'assert lum(S["ani1_out"][-1]) < lum(S["ani1"][-1])'),
    ("多段只算一段", "            n += 1\n            cur = dict(m)", "            n = 1\n            cur = dict(m)"),
    # 續一百四十六:sweep_literals 逃過的常數補上的判準
    ("遊戲區左緣錯 1 px(半個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 193, 201 "),
    ("遊戲區上緣錯 1 px(半個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 192, 202 "),
    ("逐列判準的列號取錯位元", "bad_rows = np.unique(multi >> 8)", "bad_rows = np.unique(multi >> 9)"),
    ("段的映射把列號混進索引", "maps[kk >> 8][kk & 255] = cc", "maps[kk >> 8][kk & 256] = cc"),
    ("ANI 相鄰幀報成隔一幀", '"pair": [pairs[0], pairs[0] + 1]', '"pair": [pairs[0], pairs[0] + 2]'),
    ("轉場目標 B 讀到 push 的操作碼", "B6, G6 = code(0x1fc6d, 4)[1], code(0x1fc6d, 4)[3]", "B6, G6 = code(0x1fc6d, 4)[0], code(0x1fc6d, 4)[3]"),
    ("R 平均取錯位元", "return float(((col >> 16) & 255).mean())", "return float(((col >> 17) & 255).mean())"),
    ("撕裂的 split_rows 對照看奇數列", "y % 2 == 0 and y + 1 in lab", "y % 2 == 1 and y + 1 in lab"),
    ("淡入淡出候選沒有 dy", 'CANDS.update({f"dy{d}": BUF[d:d + 200] for d in range(MAX_DY + 1)})', "CANDS.update({})"),
    ("命中表多切掉一個值", "FLASH_HITS = TABLE[:-1] ", "FLASH_HITS = TABLE[:-2] "),
    ("連拍時間不必遞增 → 預期遞減", "assert all(a < b for a, b in zip(T, T[1:]))", "assert all(a > b for a, b in zip(T, T[1:]))"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s145", MUTANTS))
