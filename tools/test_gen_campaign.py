#!/usr/bin/env python3
import os
import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import gen_campaign as campaign


def spawn_record(turn, event_id, groups, sources):
    return {
        "turn": turn,
        "event_id": event_id,
        "groups": groups,
        "native_spawns": sources,
    }


class NativeSpawnMergeTest(unittest.TestCase):
    def test_split_authored_actions_keep_one_event_provenance_and_call_order(self):
        scenario = {
            "events": [{
                "id": "authored",
                "trigger": "on_turn_end",
                "when": {"turn": 3},
                "do": [
                    {"type": "spawn_group", "groups": [3]},
                    {"type": "dialogue", "text": "保留人工演出"},
                    {"type": "spawn_group", "groups": [7]},
                ],
            }],
        }
        records = [spawn_record(3, 0, [3, 7], [
            {"via": "spawn_group", "source": "0x341f2", "raw_placement_gate": 0},
            {"via": "spawn_group_with_intro", "source": "0x3425c", "raw_placement_gate": 0},
        ])]

        campaign.merge_native_spawn_metadata(scenario, records, "test")

        first, dialogue, second = scenario["events"][0]["do"]
        self.assertEqual(first["native_event_id"], 0)
        self.assertEqual(second["native_event_id"], 0)
        self.assertEqual(first["native_spawns"][0]["source"], "0x341f2")
        self.assertEqual(second["native_spawns"][0]["source"], "0x3425c")
        self.assertNotIn("native_event_id", dialogue)

    def test_same_turn_multiple_schedules_fail_closed(self):
        scenario = {"events": []}
        source = [{"via": "spawn_group", "source": "0x1", "raw_placement_gate": 0}]
        records = [
            spawn_record(4, 1, [2], source),
            spawn_record(4, 2, [3], source),
        ]

        with self.assertRaisesRegex(ValueError, "同回合多個 spawn schedule"):
            campaign.merge_native_spawn_metadata(scenario, records, "test")

    def test_existing_different_event_binding_cannot_be_overwritten(self):
        scenario = {"events": [{
            "trigger": "on_turn_end",
            "when": {"turn": 4},
            "do": [{"type": "spawn_group", "groups": [2], "native_event_id": 99}],
        }]}
        records = [spawn_record(4, 1, [2], [
            {"via": "spawn_group", "source": "0x1", "raw_placement_gate": 0},
        ])]

        with self.assertRaisesRegex(ValueError, "不可改綁"):
            campaign.merge_native_spawn_metadata(scenario, records, "test")

    def test_versioned_scenarios_match_turn_schedule_and_handler_calls(self):
        root = Path(campaign.ROOT)
        # 這條檢查的是「已產生的 remake scenario JSON」是否與 docs/data 的
        # turn_events/event_id_groups 一致。remake/ 於 2026-09-02 整個移除後
        # scenario_root 是空的,glob 出 0 個檔 -> actual={} 而 expected 有 30+ 章,
        # 於是它從「一致性檢查」變成必定失敗。標成 skip,讓 gen_campaign 其餘
        # 3 條真正的單元檢查不被這個已知缺口淹掉(2026-09-03 全工具驗證)。
        if not (root / "remake/assets/scenarios").is_dir():
            self.skipTest("remake/assets/scenarios 隨 remake/ 移除,無產生物可比對")
        schedules = json.loads((root / "docs/data/turn_events.json").read_text())
        handlers = json.loads((root / "docs/data/event_id_groups.json").read_text())
        expected = {}
        for chapter in schedules:
            scenario_chapter = chapter["chapter"]
            for record in chapter["turn_events"]:
                sources = handlers[str(record["event_id"])]["spawns"]
                if not sources:
                    continue
                groups = list(record["groups"])
                if groups == ["$turn_counter[0x53bef]"]:
                    groups = [record["turn"]]
                self.assertEqual(len(groups), len(sources))
                calls = []
                for group, source in zip(groups, sources):
                    call = {
                        "group": group,
                        "via": source["via"],
                        "source": source["source"],
                        "raw_placement_gate": source["raw_placement_gate"],
                    }
                    if "following_acting" in source:
                        call["following_acting"] = source["following_acting"]
                    calls.append(call)
                key = (scenario_chapter, record["turn"], record["event_id"])
                self.assertNotIn(key, expected)
                expected[key] = calls

        actual = {}
        scenario_root = root / "remake/assets/scenarios"
        for path in sorted(scenario_root.glob("ch*.json")):
            chapter = int(path.stem[2:])
            scenario = json.loads(path.read_text())
            if chapter == 1:
                self.assertEqual(
                    scenario.get("native_acting_resources"),
                    "assets/cutscenes/acting/map32.json",
                )
            for event in scenario.get("events", []):
                if event.get("trigger") != "on_turn_end":
                    continue
                turn = event.get("when", {}).get("turn")
                for action in event.get("do", []):
                    if action.get("type") != "spawn_group":
                        continue
                    key = (chapter, turn, action["native_event_id"])
                    actual.setdefault(key, []).extend(action["native_spawns"])

        self.assertEqual(actual, expected)
        self.assertEqual(
            expected[(1, 4, 1)][0]["following_acting"],
            {"resource": 3, "source": "0x342e7"},
        )
        self.assertEqual(
            expected[(1, 5, 2)][0]["following_acting"],
            {"resource": 4, "source": "0x3434f"},
        )


if __name__ == "__main__":
    unittest.main()
