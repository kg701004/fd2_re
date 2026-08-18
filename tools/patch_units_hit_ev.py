#!/usr/bin/env python3
"""Surgically patch hit/ev in an already-committed map<N>_units.json in place.

export_units.py's full regeneration also drops native_treasure_event_rules,
native_record_class/race and death_effect/death_reward — those are populated
by a separate later pipeline step this script does not know about. Re-running
export_units.py wholesale therefore silently regresses already-verified data.
This script instead loads the existing file byte-for-byte, recomputes only
hit/ev via the same formula as export_units.py's hit_ev_for_unit(), and
rewrites just those two keys per unit — every other key is left untouched.

race isn't stored per-unit in the existing JSON schema, so it's re-derived by
re-running parse_field.parse_map() fresh and zipping by index (same FDFIELD
roster order export_units.py originally used to build the file).

用法: python3 patch_units_hit_ev.py <extracted/raw> <map_index> <units.json path>
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(__file__))
import parse_field
from export_units import base_stats, hit_ev_for_unit, EXE_UNIT, EXE_ITEM


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 1
    raw, m, path = argv[1], int(argv[2]), argv[3]
    info = parse_field.parse_map(raw, m)
    exe = json.load(open(EXE_UNIT, encoding="utf-8"))
    items_by_id = {it["id"]: it for it in json.load(open(EXE_ITEM, encoding="utf-8"))}

    doc = json.load(open(path, encoding="utf-8"))
    src_units = info["units"]
    if len(src_units) != len(doc.get("units", [])):
        print(f"{path}: unit count mismatch ({len(src_units)} vs {len(doc.get('units', []))}), skip", file=sys.stderr)
        return 2

    changed = 0
    for src, dst in zip(src_units, doc["units"]):
        bs = base_stats(exe, src["race"], src["cls"])
        hit, ev = hit_ev_for_unit(bs["dx"], dst.get("inventory_slots", []), items_by_id)
        if dst.get("hit") != hit or dst.get("ev") != ev:
            dst["hit"], dst["ev"] = hit, ev
            changed += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{path}: patched {changed}/{len(doc['units'])} units")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
