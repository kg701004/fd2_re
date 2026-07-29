#!/usr/bin/env python3
"""匯出 map25 已閉合的格子事件 59／60／61 規則。"""

import hashlib
import json
import os
import sys

EXPECTED_SIZE = 357074
EXPECTED_MD5 = "b97caf2239a27a896069d03549d96e1e"


def main(argv):
    if len(argv) != 3:
        print(f"usage: {argv[0]} FD2.EXE output.json", file=sys.stderr)
        return 2
    data = open(argv[1], "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    if len(data) != EXPECTED_SIZE or md5 != EXPECTED_MD5:
        raise SystemExit("FD2.EXE 版本不符，禁止沿用固定 handler 位址")
    result = {
        "source": {
            "file": os.path.basename(argv[1]),
            "size": len(data),
            "md5": md5,
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        "rules": [
            {
                "event_id": 59,
                "handler": "0x35641",
                "selector": 0,
                "trigger_gate": "record_byte6_nonzero",
                "set_mode_ranges": [{"start": 39, "end": 44, "mode": 0}],
            },
            {
                "event_id": 60,
                "handler": "0x35675",
                "selector": 0,
                "trigger_gate": "record_byte6_nonzero",
                "set_mode_ranges": [
                    {"start": 23, "end": 24, "mode": 0},
                    {"start": 53, "end": 56, "mode": 0},
                ],
            },
            {
                "event_id": 61,
                "handler": "0x356b7",
                "selector": 1,
                "once_state_index": 12,
                "required_item": 208,
                "consume_item": True,
                "spawn_group": 1,
                "join_character": 31,
                "text_indices": {"missing_item": 2, "success": 3, "final": 4},
                "presentation": {
                    "archive": "FDOTHER.DAT",
                    "resource": 45,
                    "frames": 59,
                    "helper": "0x2935b",
                    "destination_offset": 48356,
                    "stride": 320,
                    "transparent": -1,
                    "delay_helper": "0x17aa9",
                    "delay_ticks": 2,
                },
            },
        ],
    }
    with open(argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
