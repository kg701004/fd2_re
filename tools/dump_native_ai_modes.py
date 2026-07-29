#!/usr/bin/env python3
"""Dump reproducible FDFIELD b17..b19 / runtime +0x34..+0x36 distributions."""

import argparse
import collections
import hashlib
import json
from pathlib import Path

import parse_field


def file_hashes(path):
    data = path.read_bytes()
    return {
        "file": path.name,
        "size": len(data),
        "md5": hashlib.md5(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path, help="unpack_dat output root")
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, help="original FDFIELD.DAT for hashes")
    args = parser.parse_args()

    field_files = sorted((args.raw / "FDFIELD").glob("*.bin"))
    if not field_files or len(field_files) // 3 != 33:
        raise ValueError(f"expected 33 FDFIELD maps, found {len(field_files) // 3}")

    mode_counts = collections.Counter()
    byte34_counts = collections.Counter()
    triples = collections.Counter()
    maps = []
    for map_index in range(33):
        units = parse_field.parse_map(str(args.raw), map_index)["units"]
        local_modes = collections.Counter()
        for unit in units:
            byte34 = unit["native_record_byte34"]
            mode = byte34 & 0x0F
            mode_counts[mode] += 1
            local_modes[mode] += 1
            byte34_counts[byte34] += 1
            triples[(
                byte34,
                unit["native_record_byte35"],
                unit["native_record_byte36"],
            )] += 1
        maps.append({
            "map": map_index,
            "units": len(units),
            "mode_low_nibble_counts": {
                str(key): value for key, value in sorted(local_modes.items())
            },
        })

    report = {
        "provenance": {
            "constructor": "FD2.EXE 0x10fb6..0x10fc5",
            "mapping": {
                "FDFIELD_b17": "runtime_record_0x34",
                "FDFIELD_b18": "runtime_record_0x35",
                "FDFIELD_b19": "runtime_record_0x36",
            },
        },
        "source": file_hashes(args.source) if args.source else None,
        "maps": 33,
        "units": sum(mode_counts.values()),
        "mode_low_nibble_counts": {
            str(key): value for key, value in sorted(mode_counts.items())
        },
        "record_byte34_counts": {
            str(key): value for key, value in sorted(byte34_counts.items())
        },
        "record_34_35_36_combinations": [
            {"bytes": list(key), "count": count}
            for key, count in sorted(triples.items())
        ],
        "per_map": maps,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
