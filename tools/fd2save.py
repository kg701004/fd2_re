#!/usr/bin/env python3
"""Decode/encode the verified FD2.SAV storage envelope.

This is deliberately a *storage* tool, not a gameplay save editor.  Native
0x30119 writes a 0x59cb-byte buffer after storing a checksum; 0x4dbd8 applies
the reversible rolling XOR and 0x4dbb9 sums every byte except the final u32.
The remaining record fields are kept raw until their native meanings are
proven.  No original save or game asset is included in this repository.

Field-verification status (see docs/knowledge-base/58-remake-live-verification-log.md,
"續十一" 2026-08-18 and its "續三十二" 2026-08-21 follow-up, for full evidence):
  - PROVEN: SLOT_OFFSET/SLOT_SIZE/ROSTER_SIZE/UNIT_SIZE (roster stride), the
    per-slot chapter/roster_count/currency metadata bytes, and
    UNIT_CHARACTER_ID_OFFSET (record+0x08). The character-id offset was
    confirmed twice independently: (a) live DOSBox-X patch-and-play — editing
    record 12's id byte made the game actually display a different party
    member on the roster-select screen — and (b) a static cross-check done
    2026-08-21 of three real FD2.SAV files (ch10/ch21/ch23 progress) whose
    13 populated record+0x08 bytes match the documented recruitment order
    exactly (索爾/悠妮/亞雷斯/蓋亞/哈諾/希莉亞/鐵諾/瑪琳/貝克威/凱麗/洛娜/
    索菲亞/萊汀).
  - STILL UNPROVEN: any other per-unit field (HP, MP, level, inventory
    slots, ...). A word at record+0x40/+0x42 has been *speculated* to be
    current/max HP by analogy with the runtime battle record's confirmed
    `target+0x40` HP write-back (0x2ebe1), but that battle-time record is a
    separate in-memory structure from this persistent save record, and the
    analogy has never been checked against a live/known HP value in the save
    file itself — do not treat it as confirmed. Inventory slot offsets in
    this persistent record are completely unresolved; no decode logic for
    them exists in this module. Do not binary-patch these fields expecting
    predictable in-game results.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


FILE_SIZE = 0x59CB
CHECKSUM_OFFSET = FILE_SIZE - 4
SLOT_OFFSET = 0x312B
SLOT_SIZE = 0xA28
SLOT_COUNT = 4
ROSTER_SIZE = 0xA00
UNIT_SIZE = 0x50
ROSTER_UNITS = ROSTER_SIZE // UNIT_SIZE
# 0x10010 restores the active runtime header from these fixed plaintext
# offsets before entering 0x11cac. Keep the still-opaque neighbours raw.
CURRENT_RUNTIME_OFFSET = 0x30C3
CURRENT_PERSISTENT_ROSTER_OFFSET = 0x08A3
CURRENT_RUNTIME_ROSTER_OFFSET = 0x12A3
# Verified 2026-08-21 (see module docstring): each 0x50-byte persistent
# roster record's character-id byte lives at this offset.
UNIT_CHARACTER_ID_OFFSET = 0x08


def rol16(value: int, count: int) -> int:
    value &= 0xFFFF
    return ((value << count) | (value >> (16 - count))) & 0xFFFF


def xor_envelope(data: bytes) -> bytes:
    """Apply native 0x4dbd8; applying it twice restores the input."""
    out = bytearray(data)
    state = 0x00A5
    for i, value in enumerate(out):
        state = rol16(state + 0x9014, 3)
        out[i] = value ^ (state & 0xFF)
    return bytes(out)


def checksum(data: bytes) -> int:
    if len(data) != FILE_SIZE:
        raise ValueError(f"FD2.SAV must be {FILE_SIZE:#x} bytes, got {len(data):#x}")
    return sum(data[:CHECKSUM_OFFSET]) & 0xFFFFFFFF


def decode(stored: bytes) -> bytes:
    """Return native plaintext buffer after size/checksum validation."""
    plain = xor_envelope(stored)
    if len(plain) != FILE_SIZE:
        raise ValueError(f"FD2.SAV must be {FILE_SIZE:#x} bytes, got {len(plain):#x}")
    expected, = struct.unpack_from("<I", plain, CHECKSUM_OFFSET)
    actual = checksum(plain)
    if actual != expected:
        raise ValueError(f"checksum mismatch: expected {expected:#010x}, got {actual:#010x}")
    return plain


def encode(plain: bytes) -> bytes:
    """Set the native checksum and return the native stored representation."""
    if len(plain) != FILE_SIZE:
        raise ValueError(f"FD2.SAV must be {FILE_SIZE:#x} bytes, got {len(plain):#x}")
    buf = bytearray(plain)
    struct.pack_into("<I", buf, CHECKSUM_OFFSET, checksum(buf))
    return xor_envelope(bytes(buf))


def slot_bounds(slot: int) -> tuple[int, int]:
    if not 0 <= slot < SLOT_COUNT:
        raise ValueError(f"slot must be 0..{SLOT_COUNT - 1}, got {slot}")
    start = SLOT_OFFSET + slot * SLOT_SIZE
    return start, start + SLOT_SIZE


def roster_character_ids(plain: bytes, slot: int, count: int | None = None) -> list[int]:
    """Return each roster record's character-id byte (record + UNIT_CHARACTER_ID_OFFSET).

    This offset is proven (see module docstring). `count` defaults to
    ROSTER_UNITS (all 32 record slots, including unused/garbage ones past
    the slot's real roster_count); pass the slot's roster_count to read only
    the populated records.
    """
    start, _ = slot_bounds(slot)
    n = ROSTER_UNITS if count is None else count
    return [
        plain[start + i * UNIT_SIZE + UNIT_CHARACTER_ID_OFFSET]
        for i in range(n)
    ]


def summarize(plain: bytes) -> str:
    """Print only fixed raw mappings; do not assign unproven gameplay names."""
    lines = [
        f"plaintext_size={len(plain):#x}",
        f"checksum={struct.unpack_from('<I', plain, CHECKSUM_OFFSET)[0]:#010x}",
    ]
    runtime = plain[CURRENT_RUNTIME_OFFSET:CURRENT_RUNTIME_OFFSET + 18]
    lines.append(
        f"current_runtime={CURRENT_RUNTIME_OFFSET:#06x} "
        f"turn_counter={runtime[0]:#04x} runtime_count={runtime[1]:#04x} "
        f"chapter={runtime[2]:#04x} "
        f"camera_xy={runtime[3]:#04x},{runtime[4]:#04x} "
        f"cursor_xy={runtime[5]:#04x},{runtime[6]:#04x} "
        f"visible_cursor_xy={runtime[7]:#04x},{runtime[8]:#04x} "
        f"persistent_count={runtime[9]:#04x} "
        f"raw_53bf3={struct.unpack_from('<I', runtime, 10)[0]:#010x} "
        f"raw_53af9={runtime[14]:#04x} hud_gate_a={runtime[15]:#04x} "
        f"raw_51e61_51e62={runtime[16:18].hex()}"
    )
    for slot in range(SLOT_COUNT):
        start, end = slot_bounds(slot)
        meta = plain[start + ROSTER_SIZE:start + SLOT_SIZE]
        chapter = meta[0]
        roster_count = meta[1]
        global_3bf3, = struct.unpack_from("<I", meta, 2)
        lines.append(
            f"slot={slot} range={start:#06x}..{end:#06x} "
            f"roster={ROSTER_UNITS}x{UNIT_SIZE:#x} "
            f"chapter={chapter:#04x} empty={chapter == 0xFF} roster_count={roster_count:#04x} "
            f"currency={global_3bf3:#010x} "
            f"globals_51aab_53af9_51e61_51e62={meta[6:10].hex()}"
        )
        if chapter != 0xFF and 0 < roster_count <= ROSTER_UNITS:
            char_ids = roster_character_ids(plain, slot, roster_count)
            lines.append(
                f"  roster_char_ids(record+{UNIT_CHARACTER_ID_OFFSET:#04x})="
                f"{char_ids}"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", type=Path, help="user-provided FD2.SAV")
    parser.add_argument("--write-plain", type=Path, help="write verified plaintext buffer")
    args = parser.parse_args()
    plain = decode(args.save.read_bytes())
    print(summarize(plain))
    if args.write_plain:
        args.write_plain.write_bytes(plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
