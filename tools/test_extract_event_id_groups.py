#!/usr/bin/env python3
"""全域事件增援擷取器的固定原版回歸。

2026-09-03:改成版本無關。原本的斷言寫死舊版(357074 B,已遺失)的 linear 位址,
所以在使用者手上唯一存在的新版(509158 B)上必然失敗。抽取器現在自己判斷版本並
提供 `HANDLER_DELTA`(舊版 0、新版 +0x356),測試把位址與預期輸出一起套用同一個
位移——**斷言的是資料內容(group / 座標 / 兩筆 staging 都保留),不是絕對位址**,
那才是這幾條測試真正要守的東西。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
_IMPORT_ERROR = None
try:
    import extract_event_id_groups as extractor
except Exception as exc:  # RuntimeError(未知版本) / FileNotFoundError(無 EXE)
    extractor = None
    _IMPORT_ERROR = exc


class EventIDGroupExtractorTest(unittest.TestCase):
    def setUp(self):
        if extractor is None:
            self.skipTest(f"extract_event_id_groups 無法載入:{_IMPORT_ERROR}")
        self.D = extractor.HANDLER_DELTA

    def test_event63_preserves_both_staging_calls(self):
        """這條測試的重點是「兩筆 staging 呼叫都要留住」——第二筆在原版是
        `push args; jmp helper` 的 tail-call,只認 `call` 的話會漏掉。"""
        got = extractor.walk_handler(0x358C7 + self.D)
        self.assertEqual(len(got), 2, "event63 的兩筆 staging 呼叫必須都在")
        self.assertEqual(
            [(c["group"], c["staging"]["x"], c["staging"]["y"]) for c in got],
            [(1, 3, 27), (2, 15, 27)],
        )
        self.assertEqual([c["source"] for c in got],
                         [hex(0x358d7 + self.D), hex(0x358e5 + self.D)])
        self.assertTrue(all(c["raw_placement_gate"] == 0 for c in got))
        self.assertTrue(all(c["via"] == "staging_helper_0x35822" for c in got))

    def test_staging_push_order_rejects_dynamic_or_incomplete_values(self):
        self.assertIsNone(extractor.staging_spawn([1, 2], 0x100))
        self.assertIsNone(extractor.staging_spawn(["$eax", 2, 3], 0x100))

    def test_late_game_staging_handlers_keep_exact_groups_and_coordinates(self):
        expected = {
            0x358EA: [(3, 9, 44), (4, 0, 9), (5, 17, 9)],   # event64
            0x359C8: [(1, 17, 18)],                          # event66
            0x35A48: [(2, 14, 7)],                           # event68
            0x35B05: [(3, 8, 7), (4, 4, 7)],                 # event70
            0x35BF2: [(2, 4, 35), (3, 14, 35)],              # event72
        }
        for handler, rows in expected.items():
            calls = extractor.walk_handler(handler + self.D)
            self.assertEqual(
                [(c["group"], c["staging"]["x"], c["staging"]["y"]) for c in calls],
                rows,
                f"handler {hex(handler)}(+{hex(self.D)})",
            )
            self.assertTrue(all(c["via"] == "staging_helper_0x35822" for c in calls))

    def test_edition_table_is_self_consistent(self):
        """對照組:確認版本表本身沒寫錯,而不是靠上面幾條間接推斷。"""
        for md5, ed in extractor.EDITIONS.items():
            self.assertEqual(len(md5), 32)
            self.assertIn("handler_delta", ed)
            self.assertIn("size", ed)
        self.assertIn(extractor.HANDLER_DELTA, {0, 0x356})


if __name__ == "__main__":
    unittest.main()
