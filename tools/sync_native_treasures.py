#!/usr/bin/env python3
"""把已證實的 FDFIELD/FDSHAP 寶物資料同步到既有可編輯資產。

本工具只更新 map.json 的 treasure_slots/treasure_hidden，以及同圖
mapN_units.json 的 chests。其他人工校正欄位保持不變。
"""

import argparse
import glob
import json
import os
import struct

import parse_field


def resource_index(path):
    return int(os.path.basename(path).split("_")[1].split(".")[0])


def expected(raw, map_index, map_data):
    fields = sorted(
        glob.glob(os.path.join(raw, "FDFIELD", "*.bin")), key=resource_index
    )
    shapes = sorted(
        glob.glob(os.path.join(raw, "FDSHAP", "*.bin")), key=resource_index
    )
    composition = open(fields[map_index * 3], "rb").read()
    control = open(fields[map_index * 3 + 1], "rb").read()
    terrain = open(shapes[map_index * 2 + 1], "rb").read()
    w, h = struct.unpack_from("<HH", composition, 0)
    tiles = map_data.get("tiles")
    if (
        map_data.get("w") != w
        or map_data.get("h") != h
        or len(tiles or []) != w * h
        or len(terrain) % 4
    ):
        raise ValueError(f"map{map_index}: source dimensions/provenance invalid")

    slots = []
    hidden = []
    for cell, tile in enumerate(tiles):
        if tile < 0 or tile * 4 >= len(terrain):
            slots.append(-1)
            hidden.append(False)
            continue
        flags = terrain[tile * 4]
        if flags & 0x60:
            event_word = struct.unpack_from("<H", composition, 6 + cell * 4)[0]
            slots.append(event_word & 0x1F)
            hidden.append(bool(flags & 0x40))
        else:
            slots.append(-1)
            hidden.append(False)

    offset = 3 + 16 * 3 + 16 * 2
    chests = []
    for slot in range(16):
        native_type = control[offset + slot * 3]
        value = struct.unpack_from("<H", control, offset + slot * 3 + 1)[0]
        if native_type == 0xFF or value == 0:
            continue
        kind = parse_field.native_reward_kind(native_type)
        chests.append(
            {
                "slot": slot,
                "type": kind,
                "native_type": native_type,
                "value": value,
            }
        )
    return slots, hidden, chests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("assets")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    maps = sorted(
        glob.glob(os.path.join(args.assets, "map*", "map.json")),
        key=lambda path: int(os.path.basename(os.path.dirname(path))[3:]),
    )
    changed = 0
    for map_path in maps:
        map_dir = os.path.dirname(map_path)
        map_index = int(os.path.basename(map_dir)[3:])
        units_path = os.path.join(map_dir, f"map{map_index}_units.json")
        with open(map_path, encoding="utf-8") as source:
            map_data = json.load(source)
        with open(units_path, encoding="utf-8") as source:
            units_data = json.load(source)
        slots, hidden, chests = expected(args.raw, map_index, map_data)
        mismatch = (
            map_data.get("treasure_slots") != slots
            or map_data.get("treasure_hidden") != hidden
            or units_data.get("chests") != chests
        )
        if mismatch:
            changed += 1
            if args.write:
                map_data["treasure_slots"] = slots
                map_data["treasure_hidden"] = hidden
                units_data["chests"] = chests
                with open(map_path, "w", encoding="utf-8") as output:
                    json.dump(map_data, output, ensure_ascii=False, separators=(",", ":"))
                    output.write("\n")
                with open(units_path, "w", encoding="utf-8") as output:
                    json.dump(units_data, output, ensure_ascii=False, separators=(",", ":"))
                    output.write("\n")
        state = "更新" if mismatch and args.write else "缺少" if mismatch else "已驗證"
        print(f"map{map_index}: {state}；寶物格 {sum(slot >= 0 for slot in slots)}")
    if args.check and changed:
        raise SystemExit(f"{changed} 張地圖的寶物資料尚未同步")
    print(f"{len(maps)} 張地圖；異動 {changed}")


if __name__ == "__main__":
    main()
