#!/usr/bin/env python3
"""Export the native item-name range from the permanent FDTXT table.

The item/status panel renderer at 0x184c0 calls 0x15f84 with FDTXT_000 index
0xb5 + item_id for each occupied inventory slot (byte-exact disassembly,
2026-09-06: `MOV EAX,[item_id_slot]; ADD EAX,0xb5; PUSH EAX; PUSH [0x53a7d];
CALL 0x15f84`, same [0x53a7d]/0x15f84 pipeline documented for command labels
in export_command_labels.py). This tool preserves that literal mapping as
editable data. It deliberately does not infer icon/SFX presentation, which
is a separate, still-open question.

Usage:
    python3 tools/export_item_labels.py \
        extracted/raw/FDTXT/FDTXT_000.bin docs/data/item_labels.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_story_index_map import parse_fdtxt_strings


INDEX_BASE = 0xB5
ITEM_ID_COUNT = 215


def load_glyphs(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(key): value for key, value in raw.items() if key != "_comment"}


def decode(words: list[int], glyphs: dict[int, str]) -> str:
    # These entries contain ordinary glyph words. Preserve an unexpected
    # control word visibly rather than silently converting it to presentation.
    return "".join(glyphs.get(word, f"<0x{word:04X}>") for word in words)


def export(fdtxt_path: Path, glyph_path: Path) -> dict:
    strings = parse_fdtxt_strings(fdtxt_path)
    required = INDEX_BASE + ITEM_ID_COUNT
    if len(strings) < required:
        raise ValueError(f"FDTXT table has {len(strings)} strings; need {required}")
    glyphs = load_glyphs(glyph_path)
    entries = [
        {
            "item_id": item_id,
            "string_index": INDEX_BASE + item_id,
            "label": decode(strings[INDEX_BASE + item_id], glyphs),
        }
        for item_id in range(ITEM_ID_COUNT)
    ]
    # Direct raw-string anchors: abort rather than emit a shifted table.
    # item 0 = weakest starter weapon (item.json id0: type1/ap10/hit95);
    # item 31 sells for exactly 18000 (= item.json price 24000 * the
    # independently-documented 75% sell rate), matching the live shop
    # dialogue "這個巨神戟，18000元" recorded in doc58.
    if entries[0]["label"] != "短劍" or entries[4]["label"] != "黑暗劍" or entries[31]["label"] != "巨神戟":
        raise ValueError("FDTXT item-label anchor mismatch")
    return {
        "schema": "fd2.native_item_labels.v1",
        "source": {
            "resource": "FDTXT_000",
            "string_index_formula": "0xb5 + item_id",
            "item_id_count": ITEM_ID_COUNT,
            "provenance": "0x184c0 -> 0x15f84([0x53a7d], 0xb5 + item_id, ...)",
        },
        "entries": entries,
        "semantic_status": "raw native item display names only; icon/SFX presentation is a separate, still-open question (worklist 1117)",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 1
    output = export(Path(argv[1]), Path(__file__).parent.parent / "docs" / "data" / "glyph_map.json")
    Path(argv[2]).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {argv[2]} ({len(output['entries'])} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
