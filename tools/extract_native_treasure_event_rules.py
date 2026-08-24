#!/usr/bin/env python3
"""從固定版本 FD2.EXE 匯出已閉合的特殊寶物事件規則。"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from le_xref import parse_le

EXPECTED_SIZE = 357074
EXPECTED_MD5 = "b97caf2239a27a896069d03549d96e1e"


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
    md5 = hashlib.md5(data).hexdigest()
    if len(data) != EXPECTED_SIZE or md5 != EXPECTED_MD5:
        raise SystemExit("FD2.EXE 版本不符，禁止沿用固定 handler/table 位址")
    meta = parse_le(data)
    items = list(linear_bytes(data, meta, 0x5274E, 5))
    result = {
        "source": {
            "file": os.path.basename(argv[1]),
            "size": len(data),
            "md5": md5,
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        "rules": [
            {
                "event_id": 58,
                # NOTE(2026-08-24, doc25 §11.7): 0x354fe is the literal, byte-confirmed
                # value of the 0x51b91 dispatch table's event_id=58 slot, but that address
                # falls mid-instruction inside event57's own handler (0x354dd) and does not
                # reach this logic at all -- it's a table artifact. The five-choice-treasure
                # code (0x1B8A6 inventory check / 0x5274E table / 0x1BB8C write) actually
                # lives in a separate function starting at 0x35854, which currently has no
                # known static caller. "handler" below records where the logic body is, not
                # a verified call target reachable from event_id 58 -- see doc25 §11.7.5 and
                # 91-worklist.md L212 before changing this back.
                "handler": "0x35854",
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
