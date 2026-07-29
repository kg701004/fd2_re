#!/usr/bin/env python3
"""從固定版本 FD2.EXE 匯出已閉合的特殊寶物事件規則。"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from le_xref import parse_le


def linear_bytes(data, meta, address, size):
    obj = next(
        obj
        for obj in meta["objs"]
        if obj["base"] <= address and address + size <= obj["base"] + obj["vsize"]
    )
    offset = (
        meta["data_off"]
        + (obj["first"] - 1) * meta["page_size"]
        + address
        - obj["base"]
    )
    return data[offset:offset + size]


def main(argv):
    if len(argv) != 3:
        print(f"usage: {argv[0]} FD2.EXE output.json", file=sys.stderr)
        return 2
    data = open(argv[1], "rb").read()
    meta = parse_le(data)
    items = list(linear_bytes(data, meta, 0x5274E, 5))
    result = {
        "source": {
            "file": os.path.basename(argv[1]),
            "size": len(data),
            "md5": hashlib.md5(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        "rules": [
            {
                "event_id": 58,
                "handler": "0x354fe",
                "item_table_address": "0x5274e",
                "item_by_slot": items,
                "open_slots": [0, 1, 2, 3, 4],
            }
        ],
    }
    with open(argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
