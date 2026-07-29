#!/usr/bin/env python3
"""Export the constructor's proven EXE static unit tables as editable raw JSON.

The constructor at ``0x10d7f..0x10efc`` does not read a DATO portrait byte for
``unit+0x1f``.  It selects one of these fixed LE-object tables.  This tool keeps
the bytes raw (no guessed class/portrait names) so later branch/field mapping
can be reviewed and versioned independently of the executable.

Usage (normally inside ``fd2-cap-local``):
  python3 tools/extract_native_unit_tables.py org_game/.../FD2.EXE /tmp/unit_tables.json
"""
import json
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from le_xref import parse_le


TABLES = {
    "high_class": {"linear": 0x61AF9, "record_size": 10, "count": 68,
                   "helper": "0x4e4ff", "selector": "FDFIELD b1-0x44"},
    "lower_class": {"linear": 0x61DA1, "record_size": 24, "count": 32,
                     "helper": "0x4e4e8", "selector": "FDFIELD b1, lower branch"},
    "lower_aux": {"linear": 0x620A1, "record_size": 11, "count": 68,
                  "helper": "0x4e4d1", "selector": "FDFIELD b1, lower branch"},
}


def linear_file_offset(meta, linear):
    for obj in meta["objs"]:
        if obj["base"] <= linear < obj["base"] + obj["vsize"]:
            return meta["data_off"] + (obj["first"] - 1) * meta["page_size"] + (linear - obj["base"])
    raise ValueError(f"linear address outside LE objects: {linear:#x}")


def extract(path):
    raw = open(path, "rb").read()
    meta = parse_le(raw)
    result = {"schema_version": 1, "source": "FD2.EXE", "tables": {}}
    for name, spec in TABLES.items():
        size = spec["record_size"] * spec["count"]
        off = linear_file_offset(meta, spec["linear"])
        blob = raw[off:off + size]
        if len(blob) != size:
            raise ValueError(f"short {name}: got {len(blob)}, want {size}")
        result["tables"][name] = {
            "linear": hex(spec["linear"]),
            "record_size": spec["record_size"],
            "count": spec["count"],
            "helper": spec["helper"],
            "selector": spec["selector"],
            "records": [
                {"index": i, "bytes_hex": blob[i * spec["record_size"]:(i + 1) * spec["record_size"]].hex()}
                for i in range(spec["count"])
            ],
        }
    return result


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    result = extract(argv[1])
    with open(argv[2], "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    for name, table in result["tables"].items():
        print(f"{name}: {table['count']} records × {table['record_size']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
