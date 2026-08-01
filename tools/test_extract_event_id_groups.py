#!/usr/bin/env python3
"""全域事件增援擷取器的固定原版回歸。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import extract_event_id_groups as extractor


class EventIDGroupExtractorTest(unittest.TestCase):
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
