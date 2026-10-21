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
    ("調色盤 6 → 8 bit 少了低兩位", "a = (a << 2) | (a >> 4)", "a = a << 2"),
    # 實拍取樣
    ("遊戲區左緣錯 2 px(= 1 個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 194, 201 "),
    # 判準本身
    ("比對器瞎了(每組取總和而非最大)", "return int(np.maximum.reduceat(c, starts).sum())", "return int(np.add.reduceat(c, starts).sum())"),
    ("乾淨門檻 0.5", "CLEAN = 0.999 ", "CLEAN = 0.5 "),
    ("乾淨幀比例要求 95%", "assert len(clean) >= 0.75 * len(pre)", "assert len(clean) >= 0.95 * len(pre)"),
    ("撕裂自由度只看 dy", "    for c in (dy - 1, dy, dy + 1):\n        if 0 <= c", "    for c in (dy,):\n        if 0 <= c"),
    ("撕裂自由度只看 dy + 1 一側", "    for c in (dy - 1, dy, dy + 1):\n        if 0 <= c", "    for c in (dy, dy + 1):\n        if 0 <= c"),
    ("換盤那一列的索引順序反過來", "max(new) < min(old) and prev <= set(new)", "max(new) > min(old) and prev <= set(new)"),
    ("換盤區往下已換的反而變少(續一百四十六)", "max(new) < min(old) and prev <= set(new)", "max(new) < min(old) and prev >= set(new)"),
    ("換盤幀的位置判準對調", 'if s["top"] == FLASH_K else TABLE[:-1]', 'if s["top"] != FLASH_K else TABLE[:-1]'),
    ("捲動方向預期往下", "assert all(x >= y for x, y in zip(dys, dys[1:])), dys", "assert all(x <= y for x, y in zip(dys, dys[1:])), dys"),
    ("預期不是原版 EXE", 'MD5 = "33464c81e6a364fd0660141139aa8e6e"', 'MD5 = "b97caf2239a27a896069d03549d96e1e"'),
    # 由 EXE 讀出的觸發常數
    ("ANI 觸發的 esi 差 3", "T_ANI = code(0x1fadd, 3)[2]", "T_ANI = code(0x1fadd, 3)[2] + 3"),
    ("ANI 索引讀錯(#2)", "ANI_INDEX = code(0x1fae6, 2)[1]", "ANI_INDEX = code(0x1fae6, 2)[1] + 2"),
    ("閃光步數少 3", "FLASH_STEPS = code(0x1fc08, 5)[4]", "FLASH_STEPS = code(0x1fc08, 5)[4] - 3"),
    ("閃光與基本調色盤對調", "PAL_FLASH, PAL_BASE = code(0x1fbd9, 2)[1], code(0x1fc0f, 2)[1]",
     "PAL_BASE, PAL_FLASH = code(0x1fbd9, 2)[1], code(0x1fc0f, 2)[1]"),
    ("閃光區間兩端也當成「一定是閃光」", 'assert not any(strictly_flash(r["dither"]["dy"]) for r in base)', 'assert not any(in_flash(r["dither"]["dy"]) for r in base)'),
    ("預期看到的命中值只算上界", "if h - FLASH_STEPS <= hi and h >= lo)", "if h - FLASH_STEPS <= hi and h >= hi)"),
    # 對照本身
    ("虛無沒有平移", "BS = shifted(BD, 1)", "BS = shifted(BD, 0)"),
    ("黑幕分段:把非黑幀也算進黑幕", 'while g1 + 1 < len(rows) and rows[g1 + 1]["nonblack"] == 0:',
     'while g1 + 1 < len(rows) and rows[g1 + 1]["nonblack"] >= 0:'),
    ("ANI 對照用 ANI #0 自己", 'F1 = ani_colours("ANI_001.bin")', 'F1 = ani_colours("ANI_000.bin")'),
    # ANI 段
    ("ANI 幀序預期遞減", "assert all(x <= y for x, y in zip(seq_k, seq_k[1:]))", "assert all(x >= y for x, y in zip(seq_k, seq_k[1:]))"),
    ("ANI 單幀完全相等要求 90%", 'assert sum(bool(r["ani"]["exact"]) for r in solid) >= 0.6 * len(solid)',
     'assert sum(bool(r["ani"]["exact"]) for r in solid) >= 0.9 * len(solid)'),
    # 續一百四十六:sweep_literals 逃過的常數補上的判準
    ("遊戲區左緣錯 1 px(半個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 193, 201 "),
    ("遊戲區上緣錯 1 px(半個遊戲像素)", "OX, OY = 192, 201 ", "OX, OY = 192, 202 "),
    ("對照上限放到 1.5", "CTRL_MAX = 0.99 ", "CTRL_MAX = 1.5 "),
    ("literal 對照把模式 1 當透明", "            m = 2\n", "            m = 3\n"),
    ("虛無平移 2 px", "BS = shifted(BD, 1)", "BS = shifted(BD, 2)"),
    ("撕裂自由度不看緩衝第 0 列", "if 0 <= c and c + WIN <= len(buf):", "if 1 <= c and c + WIN <= len(buf):"),
    ("撕裂自由度把黑像素也算進去", "    m = col != 0\n    return float(ok[m].mean())", "    m = col == col\n    return float(ok[m].mean())"),
    ("區段壓縮從第 1 列開始", "    out, s = [], 0\n", "    out, s = [], 1\n"),
    ("撕裂方向上下對調", 'return "top_newer" if srcs[0] < srcs[1] else "bottom_newer"', 'return "top_newer" if srcs[0] > srcs[1] else "bottom_newer"'),
    ("撕裂方向去重看錯一格", "if k == 0 or c != cs[k - 1]]", "if k == 0 or c != cs[k - 2]]"),
    ("ANI 相鄰幀報成隔一幀", '"pair": [k, k + 1]', '"pair": [k, k + 2]'),
    ("上下兩列不同只看上列", "(host[0::2] != host[1::2])", "(host[0::2] != host[0::2])"),
    ("黑幕分段多吃一張", "pre, gap, post = rows[:g0], rows[g0:g1 + 1], rows[g1 + 1:]", "pre, gap, post = rows[:g0], rows[g0:g1 + 2], rows[g1 + 1:]"),
    ("撕裂方向計數從 1 起算", 'tear_dir = {"top_newer": 0,', 'tear_dir = {"top_newer": 1,'),
    ("捲動起點 esi 讀錯一格", 'ESI_START = struct.unpack_from("<I", code(0x1fa85, 5), 1)[0]', 'ESI_START = struct.unpack_from("<H", code(0x1fa85, 5), 2)[0]'),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s141", MUTANTS))
