#!/usr/bin/env python3
"""Decode/encode the verified FD2.SAV storage envelope.

This is deliberately a *storage* tool, not a gameplay save editor.  Native
0x30119 writes a 0x59cb-byte buffer after storing a checksum; 0x4dbd8 applies
the reversible rolling XOR and 0x4dbb9 sums every byte except the final u32.
The remaining record fields are kept raw until their native meanings are
proven.  No original save or game asset is included in this repository.
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


def summarize(plain: bytes) -> str:
    """Print only fixed raw mappings; do not assign unproven gameplay names."""
    lines = [
        f"plaintext_size={len(plain):#x}",
        f"checksum={struct.unpack_from('<I', plain, CHECKSUM_OFFSET)[0]:#010x}",
    ]
    for slot in range(SLOT_COUNT):
        start, end = slot_bounds(slot)
        meta = plain[start + ROSTER_SIZE:start + SLOT_SIZE]
        chapter = meta[0]
        roster_count = meta[1]
        global_3bf3, = struct.unpack_from("<I", meta, 2)
        lines.append(
            f"slot={slot} range={start:#06x}..{end:#06x} "
            f"roster={ROSTER_UNITS}x{UNIT_SIZE:#x} "
            f"chapter_raw={chapter:#04x} roster_count_raw={roster_count:#04x} "
            f"global_53bf3={global_3bf3:#010x} "
            f"globals_51aab_53af9_51e61_51e62={meta[6:10].hex()}"
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
