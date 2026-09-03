#!/usr/bin/env python3
"""全域事件增援擷取器的固定原版回歸。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
# extract_event_id_groups 在 module level 就對 FD2.EXE 做身分檢查,而它釘的是
# 已遺失的「舊版」(357074 B)。使用者手上只有新版(509158 B),所以這個 import
# 一定 raise。2026-09-03 全工具驗證期間實測過:把該檢查改成新版雜湊後強行執行,
# 抽出來的資料與既有 docs/data 版本不同(treasure 表整組物品編號都變了),
# 證明那些位址在新版上指到別的東西——所以這個 gate 是對的,不能放寬。
# 這裡改成 skip,讓這條已知的永久缺口不會偽裝成「測試壞掉」。
_IMPORT_ERROR = None
try:
    import extract_event_id_groups as extractor
except Exception as exc:  # RuntimeError(版本不符) / FileNotFoundError(無 EXE)
    extractor = None
    _IMPORT_ERROR = exc


class EventIDGroupExtractorTest(unittest.TestCase):
    def setUp(self):
        if extractor is None:
            self.skipTest(f"extract_event_id_groups 無法載入:{_IMPORT_ERROR}")

    def test_event63_preserves_both_staging_calls(self):
        self.assertEqual(
            extractor.walk_handler(0x358C7),
            [
                {
                    "group": 1,
                    "via": "staging_helper_0x35822",
                    "source": "0x358d7",
                    "raw_placement_gate": 0,
                    "staging": {
                        "helper": "0x35822",
                        "spawn_source": "0x35842",
                        "x": 3,
                        "y": 27,
                    },
                },
                {
                    "group": 2,
                    "via": "staging_helper_0x35822",
                    "source": "0x358e5",
                    "raw_placement_gate": 0,
                    "staging": {
                        "helper": "0x35822",
                        "spawn_source": "0x35842",
                        "x": 15,
                        "y": 27,
                    },
                },
            ],
        )

    def test_staging_push_order_rejects_dynamic_or_incomplete_values(self):
        self.assertIsNone(extractor.staging_spawn([1, 2], 0x100))
        self.assertIsNone(extractor.staging_spawn(["$eax", 2, 3], 0x100))

    def test_late_game_staging_handlers_keep_exact_groups_and_coordinates(self):
        expected = {
            0x358EA: [(3, 9, 44), (4, 0, 9), (5, 17, 9)],  # event64
            0x359C8: [(1, 17, 18)],                         # event66
            0x35A48: [(2, 14, 7)],                          # event68
            0x35B05: [(3, 8, 7), (4, 4, 7)],                # event70
            0x35BF2: [(2, 4, 35), (3, 14, 35)],              # event72
        }
        for handler, rows in expected.items():
            calls = extractor.walk_handler(handler)
            self.assertEqual(
                [
                    (call["group"], call["staging"]["x"], call["staging"]["y"])
                    for call in calls
                ],
                rows,
            )
            self.assertTrue(
                all(call["via"] == "staging_helper_0x35822" for call in calls)
            )


if __name__ == "__main__":
    unittest.main()
