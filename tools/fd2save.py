#!/usr/bin/env python3
"""Decode/encode the verified FD2.SAV storage envelope.

This is deliberately a *storage* tool, not a gameplay save editor.  Native
0x30119 writes a 0x59cb-byte buffer after storing a checksum; 0x4dbd8 applies
the reversible rolling XOR and 0x4dbb9 sums every byte except the final u32.
The remaining record fields are kept raw until their native meanings are
proven.  No original save or game asset is included in this repository.

Field-verification status (see docs/knowledge-base/58-remake-live-verification-log.md,
"續十一" 2026-08-18, "續三十二"/"續三十三" 2026-08-21, and "續三十四" 2026-08-21 for full
evidence):
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
  - PROVEN (2026-08-21, "續三十四"): the 8-slot inventory block at
    UNIT_INVENTORY_FLAG_OFFSET (record+0x0a) / UNIT_INVENTORY_ITEM_OFFSET
    (record+0x0b). This is not an analogy from a different structure — pure
    static Ghidra disassembly of the character-join constructor
    `FUN_000112a5` (0x112a5) shows it writing new-recruit starting items
    *directly into this persistent roster* (base `DAT_00053bf7`, i.e. the
    exact global the save writer/reader bulk-memcpy the 0xa00-byte roster
    block to/from) at `record + 0x0a + 2*slot` (presence flag, bit 0x80 =
    empty) / `record + 0x0b + 2*slot` (item id), slot = 0..7. The count/scan
    helpers used elsewhere in the EXE for the same 8-slot layout
    (`0x1b8a6`/`0x1b722`, previously only confirmed against a *different*,
    separately-allocated battle-time working roster at global `DAT_00053a45`)
    use an identical `+0x0a`/`+0x0b + 2*slot` formula and stride (0x50),
    corroborating rather than contradicting this. Sanity-checked against all
    three real FD2.SAV files on this machine: every decoded flag byte across
    all populated units/slots is one of exactly `{0x00, 0x40, 0x80}` (matching
    the three values the constructor ever writes), with zero exceptions.
  - STILL UNPROVEN: any other per-unit field (HP, MP, level, ...). A word at
    record+0x40/+0x42 has been *speculated* to be current/max HP by analogy
    with the runtime battle record's confirmed `target+0x40` HP write-back
    (0x2ebe1); the same 2026-08-21 disassembly pass that closed the inventory
    offset also happened to show `FUN_000112a5` initializing record+0x40/+0x42
    (current/max HP) and +0x44/+0x46 (current/max MP) directly on this same
    persistent record, which corroborates the offsets but does not by itself
    prove them, since construction time sets current==max and none of the
    three real save files hold a non-full HP value to cross-check against —
    do not treat HP/MP as confirmed. Do not binary-patch unproven fields
    expecting predictable in-game results.

Synthetic roster construction (2026-08-26): build_join_record()/
append_roster_members() port the production-verified native JOIN constructor
(remake/internal/campaign/native_join_constructor.go, itself covered by a
known-answer test) to write *new*, structurally-correct persistent roster
records instead of just bumping the roster_count byte or duplicating an
existing record. This distinction matters: a prior round (see
docs/knowledge-base/91-worklist.md UI-VIS-PREPARATION "writerfire",
2026-08-25) found that padding roster_count while duplicating record0 made
the game silently bounce back to the LOAD menu after confirming. A 2026-08-26
round used this module to build a 26-member roster (13 real + 13 synthetic,
each a distinct valid character id with constructor-accurate fields) and
loaded it live in DOSBox-X without that failure, reaching and completing the
preparation/deploy-selection screen. See that worklist entry for the full
live-verification writeup, including an important caveat: build_join_record()
deliberately skips the Go side's equipment-recalc tail (record+0x48/0x4a/
0x4c/0x4e stay zero), so synthetic units' *equipped* combat stats are not
accurate — only identity, inventory, and base stats are.
"""

from __future__ import annotations

import argparse
import json
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
# Verified 2026-08-21 (see module docstring, "續三十四"): 8-slot inventory
# block. Slot i's presence-flag byte is at UNIT_INVENTORY_FLAG_OFFSET+2*i
# (bit 0x80 set = empty); slot i's item-id byte is at
# UNIT_INVENTORY_ITEM_OFFSET+2*i (only meaningful while the flag's 0x80 bit
# is clear -- native never clears the item byte on removal, only the flag).
UNIT_INVENTORY_SLOT_COUNT = 8
UNIT_INVENTORY_FLAG_OFFSET = 0x0A
UNIT_INVENTORY_ITEM_OFFSET = 0x0B
UNIT_INVENTORY_EMPTY_BIT = 0x80


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


def roster_inventory(plain: bytes, slot: int, unit_index: int) -> list[tuple[int, int]]:
    """Return one roster unit's 8 inventory cells as (flag_byte, item_id_byte) pairs.

    This offset pair is proven (see module docstring, "續三十四"). `unit_index`
    is the record index within the slot's 32-record roster block (0-based).
    Cell i lives at record + UNIT_INVENTORY_FLAG_OFFSET + 2*i (flag) and
    record + UNIT_INVENTORY_ITEM_OFFSET + 2*i (item id). Use
    `roster_inventory_items()` to filter down to only the occupied cells.
    """
    start, _ = slot_bounds(slot)
    record = start + unit_index * UNIT_SIZE
    return [
        (
            plain[record + UNIT_INVENTORY_FLAG_OFFSET + 2 * i],
            plain[record + UNIT_INVENTORY_ITEM_OFFSET + 2 * i],
        )
        for i in range(UNIT_INVENTORY_SLOT_COUNT)
    ]


def roster_inventory_items(plain: bytes, slot: int, unit_index: int) -> list[int]:
    """Return only the occupied item ids (flag's 0x80 bit clear), in slot order."""
    return [
        item
        for flag, item in roster_inventory(plain, slot, unit_index)
        if not (flag & UNIT_INVENTORY_EMPTY_BIT)
    ]



# --- Synthetic roster-record construction (2026-08-26) -----------------
#
# Everything below ports, byte-for-byte, the *already production-verified*
# native JOIN constructor (0x112a5) implementation at
# remake/internal/campaign/native_join_constructor.go
# (`MaterializePersistentUnit`), which itself is covered by
# TestNativeJoinConstructorMaterializesKeliFromRawTables (a known-answer
# test against character id 12, cross-checked in this module too, see
# tools/test_fd2save.py). This Python port is therefore NOT a fresh,
# unverified reverse-engineering claim -- it is a re-expression of a
# formula this repository already trusts enough to ship in the remake, now
# applied to *native* FD2.SAV bytes instead of the remake's in-memory
# battle.Unit. The one thing this port intentionally SKIPS is the Go side's
# `battle.ApplyNativeEquipmentRecalc` tail, which fills the *equipped*
# combat-stat words at record+0x48/0x4a/0x4c/0x4e (AP/DP/HIT/EV after
# equipment bonuses). Those four words are left as 0x0000 here. This is a
# known, deliberate gap: it only affects the equipped-stat display, not the
# roster-count/character-id/selection-cursor mechanics this tool's roster
# construction exists to unblock (see docs/knowledge-base/91-worklist.md
# UI-VIS-PREPARATION 2026-08-26 entry for the live-verification context).
#
# All character stat/inventory *source* data comes from
# remake/assets/data/native_join_constructor.json, the same
# exe-identity-checked (357074-byte FD2.EXE, MD5
# b97caf2239a27a896069d03549d96e1e) 32-row table LoadNativeJoinConstructorTable
# validates in Go. That identity check is intentionally re-run here too.

JOIN_CONSTRUCTOR_TABLE_PATH = (
    Path(__file__).resolve().parent.parent
    / "remake" / "assets" / "data" / "native_join_constructor.json"
)
JOIN_CONSTRUCTOR_EXE_SIZE = 357074
JOIN_CONSTRUCTOR_EXE_MD5 = "b97caf2239a27a896069d03549d96e1e"
JOIN_CONSTRUCTOR_EXE_SHA256 = (
    "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f"
)


def load_join_constructor_table(path: Path | None = None) -> dict[int, tuple[bytes, bytes]]:
    """Load+validate the 32-row native JOIN source table (id -> (defaults[0x18], growth[0xb])).

    Mirrors the identity/shape checks Go's LoadNativeJoinConstructorTable
    performs (exe size/md5/sha256, evidence_level, position-indexed rows,
    fixed raw strides) so a stale or hand-edited table fails loudly instead
    of silently producing wrong records.
    """
    path = path or JOIN_CONSTRUCTOR_TABLE_PATH
    wire = json.loads(path.read_text(encoding="utf-8"))
    source = wire.get("source", {})
    if (
        wire.get("schema_version") != 1
        or source.get("exe_size") != JOIN_CONSTRUCTOR_EXE_SIZE
        or source.get("exe_md5") != JOIN_CONSTRUCTOR_EXE_MD5
        or source.get("exe_sha256") != JOIN_CONSTRUCTOR_EXE_SHA256
        or wire.get("evidence_level") != "已證實"
    ):
        raise ValueError(f"{path} native JOIN constructor manifest identity is invalid")
    rows = wire.get("rows", [])
    if len(rows) != 32:
        raise ValueError(f"{path} must have exactly 32 JOIN rows, got {len(rows)}")
    table: dict[int, tuple[bytes, bytes]] = {}
    for index, row in enumerate(rows):
        if row.get("id") != index:
            raise ValueError(f"native JOIN row {index} is not position-indexed")
        defaults = bytes.fromhex(row.get("default_raw", ""))
        growth = bytes.fromhex(row.get("growth_raw", ""))
        if len(defaults) != 0x18 or len(growth) != 0x0B:
            raise ValueError(f"native JOIN row {index} has invalid raw stride")
        table[index] = (defaults, growth)
    return table


def _word_le(raw: bytes, offset: int) -> int:
    return raw[offset] | (raw[offset + 1] << 8)


def build_join_record(char_id: int, table: dict[int, tuple[bytes, bytes]] | None = None) -> bytes:
    """Build one 0x50-byte persistent roster record for a freshly-joined character.

    Byte-for-byte port of native_join_constructor.go's MaterializePersistentUnit
    record construction (see module comment above). `char_id` must be a key in
    `table` (0..31, remake/assets/data/native_character_catalog.json identity
    list). Does NOT run the equipment-recalc tail (record+0x48/0x4a/0x4c/0x4e
    are left zero) -- see the module comment for what that means.
    """
    table = table if table is not None else load_join_constructor_table()
    if char_id not in table:
        raise ValueError(f"native JOIN character {char_id} has no constructor row")
    defaults, growth = table[char_id]
    level = defaults[2]
    if level <= 0:
        raise ValueError(f"native JOIN character {char_id} has invalid level {level}")
    max_hp = _word_le(defaults, 3) + growth[6] * (level - 1)
    max_mp = _word_le(defaults, 5) + growth[8] * (level - 1)
    if not (0 <= max_hp <= 0xFFFF) or not (0 <= max_mp <= 0xFFFF):
        raise ValueError(f"native JOIN character {char_id} HP/MP exceeds raw word")
    base_ap = _word_le(defaults, 0x12) + growth[0] * level
    base_dp = _word_le(defaults, 0x14) + growth[2] * level
    base_dx = _word_le(defaults, 0x16) + growth[4] * level

    record = bytearray(UNIT_SIZE)
    record[0x05] = 0
    record[0x06] = 2
    record[0x07] = char_id
    record[0x08] = char_id
    record[0x09] = 0
    record[0x0A], record[0x0B] = 0x40, defaults[0x0C]
    record[0x0C], record[0x0D] = 0x40, defaults[0x0D]
    for slot in range(4):
        item = defaults[0x0E + slot]
        cell = 0x0E + slot * 2
        if item == 0xFF:
            record[cell] = 0x80
        record[cell + 1] = item
    record[0x16], record[0x18] = 0x80, 0x80
    record[0x1A:0x1E] = defaults[8:12]
    record[0x1E] = 0
    record[0x1F] = defaults[0]
    record[0x20] = defaults[1]
    record[0x21] = level
    record[0x31] = 0xFF
    struct.pack_into("<H", record, 0x37, base_ap & 0xFFFF)
    struct.pack_into("<H", record, 0x39, base_dp & 0xFFFF)
    record[0x3B] = defaults[7]
    record[0x3C] = 0
    struct.pack_into("<H", record, 0x3E, base_dx & 0xFFFF)
    struct.pack_into("<H", record, 0x40, max_hp)
    struct.pack_into("<H", record, 0x42, max_hp)
    struct.pack_into("<H", record, 0x44, max_mp)
    struct.pack_into("<H", record, 0x46, max_mp)
    return bytes(record)


def append_roster_members(
    plain: bytes,
    slot: int,
    char_ids: list[int],
    table: dict[int, tuple[bytes, bytes]] | None = None,
) -> bytes:
    """Return a new plaintext buffer with `char_ids` appended as new roster records.

    Appends after the slot's existing roster_count records (leaves all
    existing records, including record0/the fixed leader, untouched) and
    bumps the roster_count metadata byte accordingly. Refuses to write past
    the 32-record buffer or to introduce a character id already present in
    the slot (this is the one integrity property we can cheaply self-check;
    see docs/knowledge-base/91-worklist.md UI-VIS-PREPARATION 2026-08-26 for
    why duplicate/ill-formed records are suspected to trigger a native
    roster-integrity rejection that silently bounces back to the LOAD menu).
    """
    start, end = slot_bounds(slot)
    meta_start = start + ROSTER_SIZE
    plain = bytearray(plain)
    roster_count = plain[meta_start + 1]
    existing_ids = set(roster_character_ids(bytes(plain), slot, roster_count))
    new_count = roster_count + len(char_ids)
    if new_count > ROSTER_UNITS:
        raise ValueError(
            f"slot {slot} roster_count {roster_count} + {len(char_ids)} new "
            f"members = {new_count} exceeds the {ROSTER_UNITS}-record buffer"
        )
    seen = set()
    for char_id in char_ids:
        if char_id in existing_ids or char_id in seen:
            raise ValueError(
                f"character id {char_id} already present in slot {slot} roster "
                "(duplicate ids are the known failure mode, refusing)"
            )
        seen.add(char_id)
    table = table if table is not None else load_join_constructor_table()
    for offset, char_id in enumerate(char_ids):
        record = build_join_record(char_id, table)
        record_start = start + (roster_count + offset) * UNIT_SIZE
        plain[record_start:record_start + UNIT_SIZE] = record
    plain[meta_start + 1] = new_count
    return bytes(plain)


def set_slot_chapter(plain: bytes, slot: int, raw_chapter: int) -> bytes:
    """Return a new plaintext buffer with slot's raw chapter metadata byte set.

    raw_chapter is the 0-based byte the game stores; the LOAD screen displays
    raw_chapter+1 ("第 N 章"). See docs/knowledge-base/25-battle-event-system.md
    §9.1 for the raw-chapter-range -> town/preparation-only flow mapping this
    tool exists to reach (22..24/27..29 = preparation-only, skips town hub).
    """
    if not 0 <= raw_chapter <= 0xFF:
        raise ValueError(f"raw_chapter must be 0..255, got {raw_chapter}")
    start, _ = slot_bounds(slot)
    plain = bytearray(plain)
    plain[start + ROSTER_SIZE] = raw_chapter
    return bytes(plain)


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
            inventories = [
                roster_inventory_items(plain, slot, i) for i in range(roster_count)
            ]
            lines.append(
                f"  roster_inventory_items(record+{UNIT_INVENTORY_FLAG_OFFSET:#04x}/"
                f"{UNIT_INVENTORY_ITEM_OFFSET:#04x})={inventories}"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", type=Path, help="user-provided FD2.SAV")
    parser.add_argument("--write-plain", type=Path, help="write verified plaintext buffer")
    parser.add_argument(
        "--append-roster",
        metavar="SLOT:ID,ID,...",
        action="append",
        default=[],
        help=(
            "append synthetic (but constructor-formula-accurate) roster "
            "records to a slot, e.g. --append-roster 0:14,17,3,15,18. "
            "Repeatable. Character ids must not already be in the slot."
        ),
    )
    parser.add_argument(
        "--set-chapter",
        metavar="SLOT:RAW_CHAPTER",
        action="append",
        default=[],
        help="set a slot's raw chapter metadata byte, e.g. --set-chapter 0:27. Repeatable.",
    )
    parser.add_argument("--out", type=Path, help="write the modified, re-encoded FD2.SAV here")
    args = parser.parse_args()
    plain = decode(args.save.read_bytes())

    mutated = plain
    for spec in args.append_roster:
        slot_str, ids_str = spec.split(":", 1)
        ids = [int(x) for x in ids_str.split(",") if x != ""]
        mutated = append_roster_members(mutated, int(slot_str), ids)
    for spec in args.set_chapter:
        slot_str, chapter_str = spec.split(":", 1)
        mutated = set_slot_chapter(mutated, int(slot_str), int(chapter_str, 0))

    print(summarize(mutated))
    if args.write_plain:
        args.write_plain.write_bytes(mutated)
    if args.out:
        # Round-trip self-check before writing anything claiming to be a
        # valid save: encode() must produce bytes that decode() accepts.
        stored = encode(mutated)
        decode(stored)
        args.out.write_bytes(stored)
        print(f"wrote {args.out} ({len(stored)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
