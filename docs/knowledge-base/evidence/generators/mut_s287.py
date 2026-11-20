"""ev_s287.py 的變異測試:每個變異改一個判準 / 解讀,必須讓 ev_s287.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 演出序列庫
    ("序列表多一格", "TAB, N, BANK = 0x627D8, 106, 0x62980", "TAB, N, BANK = 0x627D8, 107, 0x62980"),
    ("幀頭只讀拍數", "        o += 2\n        assert o + 2 * n", "        o += 1\n        assert o + 2 * n"),
    ("每對只佔 1 byte", "        o += 2 * n\n", "        o += n\n"),
    ("沒有不相接的序列", "assert ODD == [24, 84]", "assert ODD == []"),
    ("第 24 筆第 5 對是 pose 0", "(0x33, 0), (1, 5)])]", "(0x33, 0), (1, 0)])]"),
    ("第 84 筆尾端 3 byte", "TAIL84 == bytes([0x88, 1, 1, 2])", "TAIL84 == bytes([0x88, 1, 1])"),
    ("pose 只有 0 .. 3", "assert POSES == {0, 1, 2, 3, 5}", "assert POSES == {0, 1, 2, 3}"),
    ("繪製以 pose × 4 取圖", '"mov eax, esi", "shl eax, 2", "sub eax, esi"', '"mov eax, esi", "shl eax, 2", "add eax, esi"'),
    ("事件 17 在第 5 圖", "assert EV17 == [(4, 8, 0)]", "assert EV17 == [(5, 8, 0)]"),
    # (B) 對齊填充
    ("填充可到 4 byte", 'assert r["size"] < 4 and e % 4 == 0', 'assert r["size"] < 3 and e % 4 == 0'),
    ("結尾 8 對齊", 'assert r["size"] < 4 and e % 4 == 0', 'assert r["size"] < 4 and e % 8 == 0'),
    ("開頭 4 byte 是 0", "0x50000: bytes([1, 1, 1, 0])", "0x50000: bytes(4)"),
    ("模式表第 2 格是 1", "== [1, 2, 2, 3, 2] + [0] * 15", "== [1, 1, 2, 3, 2] + [0] * 15"),
    ("覆蓋少一 byte", "assert COVER == 0x56B0 + 0x34D2", "assert COVER == 0x56B0 + 0x34D1"),
    # (C) BSS
    ("舊公式換算 obj2 的檔內位址", "(OB2[\"first\"] - 1) * PS + (0x54157 - OB2[\"base\"])", "(OB2[\"first\"] - 1) * PS + (0x53157 - OB2[\"base\"])"),
    ("lin2file 不丟錯", 'assert BSS_RAISES == ["lin2file", "object_bytes"]', 'assert BSS_RAISES == ["object_bytes"]'),
    # (D) 沒有用途的資源
    ("空資源不是最後一格", "assert z == [len(d) - 1] and d[-1][0] == len(b), dat", "assert z == [len(d) - 2] and d[-1][0] == len(b), dat"),
    ("BG 背景號不含常數 2", "USED = {0, 1, 2} | TERRAIN", "USED = {0, 1} | TERRAIN"),
    ("地形取 byte 1", "TERRAIN |= {t[k + 2] | t[k + 3] << 8", "TERRAIN |= {t[k + 1] | t[k + 3] << 8"),
    ("片尾表少一格", "ENDING = list(image(0x52711, 20))", "ENDING = list(image(0x52711, 19))"),
    ("章節表沒有 0", "assert CHAP == {0, 3}", "assert CHAP == {3}"),
    ("佔位曲多一首", "assert PLACE == [0, 2, 5, 7, 9]", "assert PLACE == [0, 2, 5, 7, 9, 11]"),
    ("循環到 11", '"cmp edx, 0x22", "inc byte ptr [esp + 0xc]", "cmp eax, 0xa"', '"cmp edx, 0x22", "inc byte ptr [esp + 0xc]", "cmp eax, 0xb"'),
    # (E) 單位記錄 +7
    ("名字取第 +8 條", "[text0(k + 1) for k in range(32)] == [c[\"name\"] for c in CHAR]",
     "[text0(k) for k in range(32)] == [c[\"name\"] for c in CHAR]"),
    ("名字不加一", '"movzx eax, byte ptr [esi + 8]", "inc eax"', '"movzx eax, byte ptr [esi + 8]", "dec eax"'),
    ("轉職形態涵蓋 66 / 67", "sorted(set(range(32, 68)) - {66, 67})", "sorted(set(range(32, 68)))"),
    ("轉職資格擋 8", '"cmp ebx, 0x12", "cmp ebx, 7"]', '"cmp ebx, 0x12", "cmp ebx, 8"]'),
    ("FIGANI 載入點 18", "assert len(FIG_SITES) == 19", "assert len(FIG_SITES) == 18"),
    ("k = 2 沒有幀時改載 k = 0", '"jne 0x302a7", "inc edi", "push edi"]', '"jne 0x302a7", "dec edi", "push edi"]'),
    ("k = 2 有幀 16 組", "assert len(K2) == 17", "assert len(K2) == 16"),
    ("DATO 135 張", "== 136 and len(unpack_dat.parse_directory((GAME / \"DATO.DAT\")",
     "== 135 and len(unpack_dat.parse_directory((GAME / \"DATO.DAT\")"),
    # (F) 實機
    ("高水位以第一個 0 起算", "    HW[lab] = 0x800 - nz[0]", "    HW[lab] = 0x800 - nz[-1]"),
    ("高水位 C = 228", 'assert HW == {"A": 228, "B": 228, "C": 230}', 'assert HW == {"A": 228, "B": 228, "C": 228}'),
    ("執行期位移 0x19B000", "assert (0x3EB42 + 0x19C000)", "assert (0x3EB42 + 0x19B000)"),
    ("FPU 偵測 0", 'assert raw["fpu"] == b"\\x03\\x03"', 'assert raw["fpu"] == b"\\0\\0"'),
    ("CR0 緩衝被寫", 'assert raw["sysreg"] == bytes(0x40)', 'assert raw["sysreg"] != bytes(0x40)'),
    # (G) FDMUS 佔位曲
    ("佔位曲後狀態 2", 'assert B["sg2"]["err"] == INVALID and B["sg2"]["status"] == 4', 'assert B["sg2"]["err"] == INVALID and B["sg2"]["status"] == 2'),
    ("佔位曲換了 p10", 'and B["sg2"]["p10"] == B["sg1"]["p10"]', 'and B["sg2"]["p10"] != B["sg1"]["p10"]'),
    ("佔位曲後指標不動", 'B["sg5b"]["evnt"] > B["sg5a"]["evnt"]', 'B["sg5b"]["evnt"] == B["sg5a"]["evnt"]'),
    ("卡住時有換曲", 'assert B[k]["bgm"] == 255 and B[k]["status"] == 4', 'assert B[k]["bgm"] == 2 and B[k]["status"] == 4'),
    ("卡住的實例也進了輸入迴圈", 'IL["lc287b"] == 0 and IL["lc287f"] == 0', 'IL["lc287b"] >= 1 and IL["lc287f"] == 0'),
    ("輸入迴圈入口 0x117e8", "c.eip - LIVE_DELTA == 0x117E7)", "c.eip - LIVE_DELTA == 0x117E8)"),
    ("p10 落在新緩衝", "assert not B[k][\"musbuf\"] <= B[k][\"p10\"]", "assert B[k][\"musbuf\"] <= B[k][\"p10\"]"),
    ("錯誤字串成功時清除", "assert B[\"sg3\"][\"err\"] == B[\"sg4\"][\"err\"] == INVALID", "assert B[\"sg3\"][\"err\"] == B[\"sg4\"][\"err\"] == b\"\""),
    ("卡住的實例有戰鬥曲", "PB[\"lc287b\"][-2:] == [5, MINUS1]", "PB[\"lc287b\"][-2:] == [MINUS1, 3]"),
    ("正常實例淡出後換第 4 首", "PB[k].index(MINUS1) + 1] == 3 for k", "PB[k].index(MINUS1) + 1] == 4 for k"),
    ("play_bgm 入口 0x25978", "c.eip - LIVE_DELTA == 0x25977]", "c.eip - LIVE_DELTA == 0x25978]"),
    # (H) 演出第 24 筆
    ("演出號 0x17", "c.stack[0] == 0x18]", "c.stack[0] == 0x17]"),
    ("單位 1 的 pose 是 1", "and U1[3] == 5 and U1[6] == 2", "and U1[3] == 1 and U1[6] == 2"),
    ("單位 48 .. 51 的 pose 是 5", "unit(f\"A2u{i}\", i)[0][3] == 0", "unit(f\"A2u{i}\", i)[0][3] == 5"),
    ("之後仍是 pose 5", "assert RNDB == 8 and U1B[3] == 0", "assert RNDB == 8 and U1B[3] == 5"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s287", MUTANTS))
