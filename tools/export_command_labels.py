#!/usr/bin/env python3
"""Export the native command-label range from the permanent FDTXT table.

The battle command renderer at 0x1ceed calls 0x15f84 with FDTXT_000 index
0x1b9 + command_id.  This tool preserves that literal mapping as editable
data.  It deliberately does not infer that every one of the 40 slots is an
available command, nor assign effects, targets, or gameplay semantics.

Usage:
    python3 tools/export_command_labels.py \
        extracted/raw/FDTXT/FDTXT_000.bin docs/data/command_labels.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_story_index_map import parse_fdtxt_strings


INDEX_BASE = 0x1B9
COMMAND_SLOT_COUNT = 40


def load_glyphs(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(key): value for key, value in raw.items() if key != "_comment"}


def decode(words: list[int], glyphs: dict[int, str]) -> str:
    # These entries contain ordinary glyph words.  Preserve an unexpected
    # control word visibly rather than silently converting it to presentation.
    return "".join(glyphs.get(word, f"<0x{word:04X}>") for word in words)


def export(fdtxt_path: Path, glyph_path: Path) -> dict:
    strings = parse_fdtxt_strings(fdtxt_path)
    required = INDEX_BASE + COMMAND_SLOT_COUNT
    if len(strings) < required:
        raise ValueError(f"FDTXT table has {len(strings)} strings; need {required}")
    glyphs = load_glyphs(glyph_path)
    entries = [
        {
            "command_id": command_id,
            "string_index": INDEX_BASE + command_id,
            "label": decode(strings[INDEX_BASE + command_id], glyphs),
        }
        for command_id in range(COMMAND_SLOT_COUNT)
    ]
    # Direct raw-string anchors: abort rather than emit a shifted table.
    if entries[0]["label"] != "火炎術" or entries[30]["label"] != "音速刃" or entries[32]["label"] != "熾天使":
        raise ValueError("FDTXT command-label anchor mismatch")
    return {
        "schema": "fd2.native_command_labels.v1",
        "source": {
            "resource": "FDTXT_000",
            "string_index_formula": "0x1b9 + command_id",
            "slot_count": COMMAND_SLOT_COUNT,
            "provenance": "0x1ceed -> 0x15f84([0x53a7d], 0x1b9 + command_id, ...)",
        },
        "entries": entries,
        "semantic_status": "raw native labels only; a label does not prove a slot is reachable or define its gameplay effect",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 1
    output = export(Path(argv[1]), Path(__file__).parent.parent / "docs" / "data" / "glyph_map.json")
    Path(argv[2]).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {argv[2]} ({len(output['entries'])} slots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
