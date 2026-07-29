#!/usr/bin/env python3
"""把已證實的 FDFIELD 格子事件資料同步到可編輯 map.json。

只新增／更新：
* native_field_event_slots：每格 -1 或 0..15
* native_field_events：控制段 16 筆 (event_id, selector)

既有地圖、成本、寶箱、手動修正與單位資料均不改動。
"""

import argparse
import glob
import json
import os
import struct


def resource_index(path):
    return int(os.path.basename(path).split("_")[1].split(".")[0])


def expected(raw, map_index, map_data):
    fields = sorted(
        glob.glob(os.path.join(raw, "FDFIELD", "*.bin")),
        key=resource_index,
    )
    shapes = sorted(
        glob.glob(os.path.join(raw, "FDSHAP", "*.bin")),
        key=resource_index,
    )
    comp = open(fields[map_index * 3], "rb").read()
    control = open(fields[map_index * 3 + 1], "rb").read()
    terrain = open(shapes[map_index * 2 + 1], "rb").read()
    w, h = struct.unpack_from("<HH", comp, 0)
    if map_data.get("w") != w or map_data.get("h") != h:
        raise ValueError(f"map{map_index}: dimensions differ")
    tiles = map_data.get("tiles")
    if len(tiles or []) != w * h or len(terrain or []) % 4:
        raise ValueError(f"map{map_index}: raw terrain provenance invalid")

    slots = []
    for cell, tile in enumerate(tiles):
        if tile < 0 or tile * 4 >= len(terrain):
            slots.append(-1)
            continue
        event_word = struct.unpack_from("<H", comp, 6 + cell * 4)[0]
        raw_slot = event_word & 0x1F
        flags = terrain[tile * 4]
        slots.append(raw_slot - 1 if raw_slot and flags & 0x60 == 0 else -1)

    offset = 3 + 16 * 3
    events = [
        {
            "event_id": control[offset + slot * 2],
            "selector": control[offset + slot * 2 + 1],
        }
        for slot in range(16)
    ]
    return slots, events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("assets")
    parser.add_argument(
        "--rules",
        default="docs/data/native_field_event_rules.json",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with open(args.rules, encoding="utf-8") as source:
        rules = json.load(source)["rules"]

    maps = sorted(
        glob.glob(os.path.join(args.assets, "map*", "map.json")),
        key=lambda path: int(os.path.basename(os.path.dirname(path))[3:]),
    )
    changed = 0
    referenced_event_ids = set()
    for path in maps:
        map_index = int(os.path.basename(os.path.dirname(path))[3:])
        with open(path, encoding="utf-8") as source:
            data = json.load(source)
        slots, events = expected(args.raw, map_index, data)
        event_ids = {
            events[slot]["event_id"]
            for slot in slots
            if slot >= 0 and events[slot]["event_id"] != 0xFF
        }
        map_rules = [rule for rule in rules if rule["event_id"] in event_ids]
        rules_mismatch = (
            data.get("native_field_event_rules", []) != map_rules
            or (not map_rules and "native_field_event_rules" in data)
        )
        referenced_event_ids.update(
            events[slot]["event_id"]
            for slot in slots
            if slot >= 0 and events[slot]["event_id"] != 0xFF
        )
        mismatch = (
            data.get("native_field_event_slots") != slots
            or data.get("native_field_events") != events
            or rules_mismatch
        )
        if mismatch:
            changed += 1
            if args.write:
                data["native_field_event_slots"] = slots
                data["native_field_events"] = events
                if map_rules:
                    data["native_field_event_rules"] = map_rules
                else:
                    data.pop("native_field_event_rules", None)
                with open(path, "w", encoding="utf-8") as output:
                    json.dump(data, output, ensure_ascii=False, separators=(",", ":"))
                    output.write("\n")
        print(f"map{map_index}: {'更新' if mismatch and args.write else '缺少' if mismatch else '已驗證'}")
    if args.check and changed:
        raise SystemExit(f"{changed} 張 map.json 尚未同步")
    print(f"{len(maps)} 張地圖；異動 {changed}")
    print(
        "實際格子引用 event_id："
        + ",".join(str(event_id) for event_id in sorted(referenced_event_ids))
    )


if __name__ == "__main__":
    main()
