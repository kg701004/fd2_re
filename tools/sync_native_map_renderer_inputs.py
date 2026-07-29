#!/usr/bin/env python3
"""同步 33 張地圖的原版構成格輸入，不重寫其他可編輯欄位。

來源：
* FDFIELD composition entry byte+2 → native_composition_event_bytes
* FDFIELD composition entry byte+3 → native_tile_blit_modes
* FDSHAP terrain/control resource → native_terrain_control

固定資源編號沿用已證實的 map 關係：FDFIELD map*3、FDSHAP map*2+1。
執行前驗證原始 FDFIELD.DAT／FDSHAP.DAT 的大小與雜湊，避免不同版本的
extracted/raw 資源被靜默同步到固定位址／格式結論。
"""

import argparse
import glob
import hashlib
import json
import os
import struct


def resource_index(path):
    return int(os.path.basename(path).split("_")[1].split(".")[0])


def verify_archive(originals, reference_path, filename):
    with open(reference_path, encoding="utf-8") as source:
        reference = json.load(source)
    entries = {
        entry["file"]: entry
        for entry in reference.get("files", [])
    }
    expected = entries.get(filename)
    if expected is None:
        raise ValueError(f"reference manifest lacks {filename}")
    path = os.path.join(originals, filename)
    with open(path, "rb") as source:
        data = source.read()
    if (
        len(data) != expected["size"]
        or hashlib.md5(data).hexdigest() != expected["md5"]
        or hashlib.sha256(data).hexdigest() != expected["sha256"]
    ):
        raise ValueError(f"{filename} version differs from reference manifest")


def expected_inputs(raw, map_index, data):
    fields = sorted(
        glob.glob(os.path.join(raw, "FDFIELD", "*.bin")),
        key=resource_index,
    )
    shapes = sorted(
        glob.glob(os.path.join(raw, "FDSHAP", "*.bin")),
        key=resource_index,
    )
    field_index = map_index * 3
    terrain_index = map_index * 2 + 1
    if field_index >= len(fields) or terrain_index >= len(shapes):
        raise ValueError(f"map{map_index}: extracted resource is absent")
    with open(fields[field_index], "rb") as source:
        composition = source.read()
    with open(shapes[terrain_index], "rb") as source:
        control = source.read()
    if len(composition) < 4 or len(control) == 0 or len(control) % 4:
        raise ValueError(f"map{map_index}: malformed renderer source")
    width, height = struct.unpack_from("<HH", composition, 0)
    if (
        data.get("w") != width
        or data.get("h") != height
        or len(data.get("tiles", [])) != width * height
        or len(composition) < 4 + width * height * 4
    ):
        raise ValueError(f"map{map_index}: editable/source dimensions differ")
    max_tile = len(control) // 4
    if any(tile < 0 or tile >= max_tile for tile in data["tiles"]):
        raise ValueError(f"map{map_index}: tile exceeds terrain control table")
    flags = [
        composition[4 + cell * 4 + 2]
        for cell in range(width * height)
    ]
    modes = [
        composition[4 + cell * 4 + 3]
        for cell in range(width * height)
    ]
    return flags, modes, list(control)


def sync_map(path, map_index, raw, write):
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    flags, modes, control = expected_inputs(raw, map_index, data)
    mismatch = (
        data.get("native_composition_event_bytes") != flags
        or "native_target_flags" in data
        or data.get("native_tile_blit_modes") != modes
        or data.get("native_terrain_control") != control
    )
    if mismatch and write:
        data["native_composition_event_bytes"] = flags
        data.pop("native_target_flags", None)
        data["native_tile_blit_modes"] = modes
        data["native_terrain_control"] = control
        with open(path, "w", encoding="utf-8") as output:
            json.dump(
                data, output, ensure_ascii=False,
                separators=(",", ":"),
            )
            output.write("\n")
    return mismatch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("assets")
    parser.add_argument("originals")
    parser.add_argument(
        "--reference",
        default="docs/data/fd2-reference-files.json",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    for filename in ("FDFIELD.DAT", "FDSHAP.DAT"):
        verify_archive(args.originals, args.reference, filename)

    maps = sorted(
        glob.glob(os.path.join(args.assets, "map*", "map.json")),
        key=lambda path: int(os.path.basename(os.path.dirname(path))[3:]),
    )
    if len(maps) != 33:
        raise ValueError(f"expected 33 editable maps, found {len(maps)}")
    changed = 0
    for path in maps:
        map_index = int(os.path.basename(os.path.dirname(path))[3:])
        mismatch = sync_map(
            path, map_index, args.raw, args.write,
        )
        if mismatch:
            changed += 1
        state = "更新" if mismatch and args.write else "缺少" if mismatch else "已驗證"
        print(f"map{map_index}: {state}")
    root_map = os.path.join(os.path.dirname(args.assets), "map.json")
    if os.path.exists(root_map):
        mismatch = sync_map(
            root_map, 0, args.raw, args.write,
        )
        if mismatch:
            changed += 1
        state = "更新" if mismatch and args.write else "缺少" if mismatch else "已驗證"
        print(f"root-map0: {state}")
    if args.check and changed:
        raise SystemExit(f"{changed} 張 map.json 尚未同步原版構成格輸入")
    print(f"{len(maps)} 張地圖；異動 {changed}")


if __name__ == "__main__":
    main()
