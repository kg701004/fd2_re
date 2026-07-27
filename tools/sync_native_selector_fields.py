#!/usr/bin/env python3
"""Synchronize only proven native visual-selector fields into map unit assets.

The editable map assets contain manual corrections which a full export_units.py
regeneration must not overwrite.  FDFIELD construction at 0x10d7f..0x10efc
does, however, close three fields for every scripted roster entry:

* roster b0 -> 0x11019 raw key -> runtime unit+2 cache slot
* roster b0 -> runtime unit+6
* roster b1 -> runtime unit+7 / unit+8 FIGANI selector and identity

This tool preserves every existing asset field and updates only
the fields above. The optional native table input adds only the independently
proven runtime ``+0x42`` word; it deliberately does not duplicate constructor
tables into every unit asset.

Optional constructor provenance can be synchronized without touching the
normalized HP field:

  python3 tools/sync_native_selector_fields.py extracted/raw remake/assets/maps \
    --native-tables docs/data/exe_tables/native_unit_tables.json --check

Usage:
  python3 tools/sync_native_selector_fields.py extracted/raw remake/assets/maps --check
  python3 tools/sync_native_selector_fields.py extracted/raw remake/assets/maps --write
"""
import argparse
import json
from pathlib import Path
import sys

import parse_field
import export_units


FIELDS = ("map_selector_key", "native_record_byte6", "battle_fig", "native_identity")


def expected_units(raw, map_index, native_tables=None):
    expected = []
    for unit in parse_field.parse_map(str(raw), map_index)["units"]:
        item = {
            "map_selector_key": unit["native_map_selector_key"],
            "native_record_byte6": unit["native_record_byte6"],
            "battle_fig": unit["portrait"],
            "native_identity": unit["portrait"],
        }
        if native_tables is not None:
            word42 = export_units.native_record_word42_for_portrait(
                native_tables, unit["portrait"], unit["lv"]
            )
            # Unsupported selector/table provenance remains absent.  The
            # runtime loader therefore keeps native predicates fail-closed.
            if word42 is not None:
                item["native_record_word42"] = word42
        expected.append(item)
    return expected


def sync_asset(raw, asset_path, write, native_tables=None):
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    map_index = asset.get("map")
    if not isinstance(map_index, int):
        raise ValueError(f"{asset_path}: missing integer map")
    units = asset.get("units")
    if not isinstance(units, list):
        raise ValueError(f"{asset_path}: missing units list")
    expected = expected_units(raw, map_index, native_tables)
    if len(units) != len(expected):
        raise ValueError(
            f"{asset_path}: asset has {len(units)} units but FDFIELD map {map_index} has {len(expected)}"
        )

    changed = 0
    for index, (unit, native) in enumerate(zip(units, expected)):
        if not isinstance(unit, dict):
            raise ValueError(f"{asset_path}: unit {index} is not an object")
        fields = list(FIELDS)
        if "native_record_word42" in native:
            fields.append("native_record_word42")
        for field in fields:
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
    parser.add_argument("--native-tables", type=Path,
                        help="raw constructor tables from extract_native_unit_tables.py")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    paths = sorted(args.assets.glob("map*/map*_units.json"), key=lambda p: int(p.parent.name[3:]))
    if not paths:
        raise ValueError(f"no map unit assets under {args.assets}")
    native_tables = None
    if args.native_tables is not None:
        native_tables = json.loads(args.native_tables.read_text(encoding="utf-8"))
    changed = 0
    for path in paths:
        map_index, count = sync_asset(args.raw, path, args.write, native_tables)
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
