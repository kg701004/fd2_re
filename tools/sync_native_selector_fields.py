#!/usr/bin/env python3
"""Synchronize only proven native visual-selector fields into map unit assets.

The editable map assets contain manual corrections which a full export_units.py
regeneration must not overwrite.  FDFIELD construction at 0x10d7f..0x10efc
does, however, close two fields for every scripted roster entry:

* roster b0 -> 0x11019 raw key -> runtime unit+2 cache slot
* roster b1 -> runtime unit+7 / unit+8 FIGANI selector

This tool preserves every existing asset field and updates only
``map_selector_key`` and ``battle_fig``.  It refuses mismatched roster counts
or conflicting existing values.  Use --check in regression verification; use
--write to make the mechanical update.

Usage:
  python3 tools/sync_native_selector_fields.py extracted/raw remake/assets/maps --check
  python3 tools/sync_native_selector_fields.py extracted/raw remake/assets/maps --write
"""
import argparse
import json
from pathlib import Path
import sys

import parse_field


FIELDS = ("map_selector_key", "battle_fig")


def expected_units(raw, map_index):
    return [
        {
            "map_selector_key": unit["native_map_selector_key"],
            "battle_fig": unit["portrait"],
        }
        for unit in parse_field.parse_map(str(raw), map_index)["units"]
    ]


def sync_asset(raw, asset_path, write):
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    map_index = asset.get("map")
    if not isinstance(map_index, int):
        raise ValueError(f"{asset_path}: missing integer map")
    units = asset.get("units")
    if not isinstance(units, list):
        raise ValueError(f"{asset_path}: missing units list")
    expected = expected_units(raw, map_index)
    if len(units) != len(expected):
        raise ValueError(
            f"{asset_path}: asset has {len(units)} units but FDFIELD map {map_index} has {len(expected)}"
        )

    changed = 0
    for index, (unit, native) in enumerate(zip(units, expected)):
        if not isinstance(unit, dict):
            raise ValueError(f"{asset_path}: unit {index} is not an object")
        for field in FIELDS:
            current = unit.get(field)
            value = native[field]
            if current is not None and current != value:
                raise ValueError(
                    f"{asset_path}: unit {index} {field}={current!r}, expected native {value!r}"
                )
            if current is None:
                unit[field] = value
                changed += 1

    if write and changed:
        asset_path.write_text(
            json.dumps(asset, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    return map_index, changed


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("assets", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    paths = sorted(args.assets.glob("map*/map*_units.json"), key=lambda p: int(p.parent.name[3:]))
    if not paths:
        raise ValueError(f"no map unit assets under {args.assets}")
    changed = 0
    for path in paths:
        map_index, count = sync_asset(args.raw, path, args.write)
        changed += count
        print(f"map{map_index}: {'updated' if args.write else 'verified'} ({count} missing selector fields)")
    if args.check and changed:
        raise ValueError(f"{changed} native selector fields are missing; run with --write")
    print(f"{len(paths)} map assets {'updated' if args.write else 'verified'}; {changed} fields {'written' if args.write else 'missing'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
