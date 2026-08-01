#!/usr/bin/env python3
"""把已證實的 FDFIELD 格子事件資料同步到可編輯 map.json。

只新增／更新：
* assets 根目錄 native_turn_event_controls.json：每張地圖控制段全部 16 筆
  原始 (turn, event_id, raw_camp)，包含 turn=0xff 的休眠列；它們不會被
  解讀成第 255 回合事件
* native_field_event_slots：每格 -1 或 0..15
* native_field_events：控制段 16 筆 (event_id, selector)

既有地圖、成本、寶箱、手動修正與單位資料均不改動。
"""

import argparse
import glob
import hashlib
import json
import os
import struct

FDFIELD_SOURCE = {
    "file": "FDFIELD.DAT",
    "size": 243169,
    "md5": "ecdb0436d26adfe5d107f2713fa7e9a2",
    "sha256": "b0cf75d94f58603f091c7462c0494f0e83bd6edfb04c1acbf83ed4d938c7a513",
}
FD2_SOURCE = {
    "file": "FD2.EXE",
    "size": 357074,
    "md5": "b97caf2239a27a896069d03549d96e1e",
    "sha256": "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f",
}


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

    turn_controls = [
        {
            "turn": control[3 + slot * 3],
            "event_id": control[3 + slot * 3 + 1],
            "raw_camp": control[3 + slot * 3 + 2],
        }
        for slot in range(16)
    ]
    offset = 3 + 16 * 3
    events = [
        {
            "event_id": control[offset + slot * 2],
            "selector": control[offset + slot * 2 + 1],
        }
        for slot in range(16)
    ]
    return (
        turn_controls,
        slots,
        events,
        os.path.basename(fields[map_index * 3 + 1]),
        hashlib.sha256(control).hexdigest(),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("assets")
    parser.add_argument(
        "--field-archive",
        default="org_game/炎龍騎士團/FLAME2/FDFIELD.DAT",
    )
    parser.add_argument(
        "--exe",
        default="org_game/炎龍騎士團/FLAME2/FD2.EXE",
    )
    parser.add_argument(
        "--rules",
        default="docs/data/native_field_event_rules.json",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with open(args.field_archive, "rb") as source:
        field_archive = source.read()
    if (
        len(field_archive) != FDFIELD_SOURCE["size"]
        or hashlib.md5(field_archive).hexdigest() != FDFIELD_SOURCE["md5"]
        or hashlib.sha256(field_archive).hexdigest() != FDFIELD_SOURCE["sha256"]
    ):
        raise SystemExit("FDFIELD.DAT 與固定參考版本不符；禁止重生 native controls")
    with open(args.exe, "rb") as source:
        executable = source.read()
    if (
        len(executable) != FD2_SOURCE["size"]
        or hashlib.md5(executable).hexdigest() != FD2_SOURCE["md5"]
        or hashlib.sha256(executable).hexdigest() != FD2_SOURCE["sha256"]
    ):
        raise SystemExit("FD2.EXE 與固定參考版本不符；禁止重生 native round seed")
    with open(args.rules, encoding="utf-8") as source:
        rules = json.load(source)["rules"]

    maps = sorted(
        glob.glob(os.path.join(args.assets, "map*", "map.json")),
        key=lambda path: int(os.path.basename(os.path.dirname(path))[3:]),
    )
    changed = 0
    referenced_event_ids = set()
    turn_control_maps = []
    for path in maps:
        map_index = int(os.path.basename(os.path.dirname(path))[3:])
        with open(path, encoding="utf-8") as source:
            data = json.load(source)
        turn_controls, slots, events, control_resource, control_sha256 = expected(
            args.raw, map_index, data
        )
        turn_control_maps.append({
            "map": map_index,
            "control_resource": control_resource,
            "control_sha256": control_sha256,
            "controls": turn_controls,
        })
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
    catalog_path = os.path.join(args.assets, "native_turn_event_controls.json")
    catalog = {
        "schema_version": 1,
        "source": FDFIELD_SOURCE,
        "round_seed": {
            "value": 1,
            "writer": "0x2066e",
            "source": FD2_SOURCE,
        },
        "maps": turn_control_maps,
    }
    try:
        with open(catalog_path, encoding="utf-8") as source:
            catalog_mismatch = json.load(source) != catalog
    except (FileNotFoundError, json.JSONDecodeError):
        catalog_mismatch = True
    if catalog_mismatch:
        changed += 1
        if args.write:
            with open(catalog_path, "w", encoding="utf-8") as output:
                json.dump(catalog, output, ensure_ascii=False, indent=2)
                output.write("\n")
    print(
        "turn controls: "
        + ("更新" if catalog_mismatch and args.write else "缺少" if catalog_mismatch else "已驗證")
    )
    if args.check and changed:
        raise SystemExit(f"{changed} 張 map.json 尚未同步")
    print(f"{len(maps)} 張地圖；異動 {changed}")
    print(
        "實際格子引用 event_id："
        + ",".join(str(event_id) for event_id in sorted(referenced_event_ids))
    )


if __name__ == "__main__":
    main()
