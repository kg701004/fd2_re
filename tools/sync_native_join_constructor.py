#!/usr/bin/env python3
"""從雜湊綁定的 EXE 表格輸出重製端 JOIN 建構器資產。"""

import argparse
import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build(reference: Path, defaults: Path, growth: Path) -> dict:
    refs = load_json(reference)
    exe = next((row for row in refs.get("files", []) if row.get("file") == "FD2.EXE"), None)
    if exe is None:
        raise ValueError("reference manifest lacks FD2.EXE")
    default_rows = load_json(defaults)
    growth_rows = load_json(growth)
    if len(default_rows) < 32 or len(growth_rows) < 32:
        raise ValueError("JOIN tables must contain at least 32 rows")

    rows = []
    for idx in range(32):
        default = default_rows[idx]
        grow = growth_rows[idx]
        if default.get("idx") != idx or grow.get("idx") != idx:
            raise ValueError(f"JOIN row {idx} is not position-indexed")
        default_raw = bytes.fromhex(default.get("raw", ""))
        growth_raw = bytes.fromhex(grow.get("raw", ""))
        if len(default_raw) != 0x18 or len(growth_raw) != 0x0B:
            raise ValueError(f"JOIN row {idx} has invalid raw stride")
        rows.append(
            {
                "id": idx,
                "default_file_offset": default["off"],
                "growth_file_offset": grow["off"],
                "default_raw": default_raw.hex(),
                "growth_raw": growth_raw.hex(),
            }
        )
    return {
        "schema_version": 1,
        "source": {
            "reference_file": "docs/data/fd2-reference-files.json",
            "exe_size": exe["size"],
            "exe_md5": exe["md5"],
            "exe_sha256": exe["sha256"],
            "ida_default_table": "0x61da1",
            "ida_growth_table": "0x620a1",
            "constructor": "0x112a5",
        },
        "evidence_level": "已證實",
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("defaults", type=Path)
    parser.add_argument("growth", type=Path)
    parser.add_argument("output", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    rendered = json.dumps(
        build(args.reference, args.defaults, args.growth),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"{args.output} is not synchronized")
        print(f"verified {args.output}")
        return 0
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
