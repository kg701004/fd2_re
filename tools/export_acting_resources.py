#!/usr/bin/env python3
"""Export FD2 acting resources as editable, deterministic behaviour JSON.

The original executable stays an input outside version control.  This tool
reads its 106-entry acting directory and emits only the decoded frame
semantics used by the remake: duration, special-mode flag, original runtime
slot, and pose.  It deliberately does not write pointers, offsets, or source
bytes to the output.

Example:

    python3 tools/export_acting_resources.py \
      org_game/炎龍騎士團/FLAME2/FD2.EXE \
      remake/assets/cutscenes/acting/map32.json
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any


# FD2.EXE file-relative layout, verified against the acting getter's 106-entry
# table.  These are extractor implementation details only: never serialized.
#
# 2026-08-20: rebased for the "新版(1998 重打包版)" FD2.EXE (509158 bytes,
# md5 33464c81e6a364fd0660141139aa8e6e — see docs/data/fd2-reference-files.json).
# The old constants below (0x565D8/0x53E00) matched the lost 357074-byte
# edition only; running this tool against the new baseline previously raised
# "resource 0 starts outside input". Recovered the new offsets by locating
# the byte-identical resource-0 and resource-99 frame payloads (their bytes
# are game content, not addresses, so they carry over unchanged) via direct
# signature search, then solving for the directory/data bases that are
# jointly consistent with both hits. All 106 resulting entries parse cleanly
# and reproduce the existing map32.json byte-for-byte, confirming the values.
# Old constants (357074-byte edition, kept for history only):
#   DIRECTORY_OFFSET = 0x565D8; DATA_OFFSET = 0x53E00
DIRECTORY_OFFSET = 0x7B7EC
DATA_OFFSET = 0x79014
RESOURCE_COUNT = 106


def selftest() -> int:
    """檔頭那段註解記載了一個**可驗證的宣稱**,這裡把它變成每次重跑的檢查。

    註解說:舊常數 `0x565D8`/`0x53E00` 只對應**已遺失的 357074-byte 版本**,
    在現行基準上會丟「resource 0 starts outside input」;新常數是靠 resource 0
    與 99 的位元組簽章重新解出來的,且「106 筆全部乾淨解析」。

    第 (1)(2) 題就是那個宣稱的兩半 —— **新常數必須 106/106 成功,舊常數必須
    在現行版本大量失敗**。少了第 (2) 題,這個檢查無法分辨「常數是對的」與
    「這段程式碼寬鬆到什麼常數都能過」;這正是本輪在 dump_chapter_beats 上
    踩過的同一類版本漂移。
    """
    import os
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2", "FD2.EXE")
    if not os.path.isfile(exe):
        print("SKIP: 找不到 org_game 的 FD2.EXE")
        return 0
    data = open(exe, "rb").read()

    def sweep(dir_off, data_off):
        ok = frames = 0
        for i in range(RESOURCE_COUNT):
            try:
                off = read_u32(data, dir_off + i * 4, f"dir[{i}]")
                frames += len(parse_resource(data, data_off + off, i))
                ok += 1
            except (ValueError, IndexError, struct.error):
                pass
        return ok, frames

    print("(1) 現行常數必須 106/106 全部乾淨解析")
    ok_n, frames = sweep(DIRECTORY_OFFSET, DATA_OFFSET)
    ok1 = ok_n == RESOURCE_COUNT and frames > 0
    print(f"    {'PASS' if ok1 else 'FAIL'}: {ok_n}/{RESOURCE_COUNT} 成功,"
          f"總 frame {frames}")
    if not ok1:
        fails.append(f"現行常數只解出 {ok_n}/{RESOURCE_COUNT}")

    print("\n(2) 對照:舊版常數在現行 EXE 上必須大量失敗")
    # 沒有這一題,第 (1) 題無法分辨「常數是對的」與「這段程式碼寬鬆到什麼常數都能過」。
    ok_o, _ = sweep(0x565D8, 0x53E00)
    ok2 = ok_o < RESOURCE_COUNT // 2
    print(f"    {'PASS' if ok2 else 'FAIL'}: 舊常數只成功 {ok_o}/{RESOURCE_COUNT}"
          f"(應遠少於一半 —— 否則解析器沒有鑑別力)")
    if not ok2:
        fails.append(f"舊常數竟然也能解出 {ok_o}/{RESOURCE_COUNT},解析器不夠嚴")

    print("\n(3) read_u32 的邊界必須真的擋住越界讀取")
    for label, off in (("負數", -1), ("剛好越界", len(data) - 3), ("遠超檔尾", len(data) * 2)):
        try:
            read_u32(data, off, "probe")
            print(f"    FAIL: 「{label}」沒有被擋下")
            fails.append(f"read_u32 {label} 沒有被擋下")
        except ValueError:
            print(f"    PASS: 「{label}」-> ValueError")

    print("\n(4) parse_resource 的起點越界與 frame_count=0 必須被擋下")
    try:
        parse_resource(data, len(data) + 1, 0)
        print("    FAIL: 起點越界沒有被擋下")
        fails.append("parse_resource 起點越界沒有被擋下")
    except ValueError:
        print("    PASS: 起點越界 -> ValueError")
    zero = bytes([0]) + b"\x00" * 16
    try:
        parse_resource(zero, 0, 0)
        print("    FAIL: frame_count=0 沒有被擋下")
        fails.append("frame_count=0 沒有被擋下")
    except ValueError:
        print("    PASS: frame_count=0 -> ValueError")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(現行常數 106/106 + 舊常數對照 + read_u32 邊界 ×3 + "
          "parse_resource 兩條拒絕路徑)。")
    return 0


def read_u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"{label} u32 at file+0x{offset:x} is outside input")
    return struct.unpack_from("<I", data, offset)[0]


def parse_resource(data: bytes, start: int, resource_id: int) -> list[dict[str, Any]]:
    """Decode one self-describing acting resource without retaining raw data."""

    if start >= len(data):
        raise ValueError(f"resource {resource_id} starts outside input")
    cursor = start
    frame_count = data[cursor]
    cursor += 1
    if frame_count == 0:
        raise ValueError(f"resource {resource_id} has no frames")

    frames: list[dict[str, Any]] = []
    for frame_index in range(frame_count):
        if cursor + 2 > len(data):
            raise ValueError(f"resource {resource_id} frame {frame_index} header is truncated")
        duration_raw, unit_count = data[cursor], data[cursor + 1]
        cursor += 2
        pair_bytes = unit_count * 2
        if cursor + pair_bytes > len(data):
            raise ValueError(f"resource {resource_id} frame {frame_index} units are truncated")
        units = [
            {"slot": data[pair], "pose": data[pair + 1]}
            for pair in range(cursor, cursor + pair_bytes, 2)
        ]
        cursor += pair_bytes
        frame: dict[str, Any] = {"beats": duration_raw & 0x7F, "units": units}
        if duration_raw & 0x80:
            frame["special"] = True
        frames.append(frame)
    return frames


def export_resources(executable: Path) -> dict[str, list[dict[str, Any]]]:
    """Decode all original global acting IDs (0 through 105)."""

    data = executable.read_bytes()
    directory_end = DIRECTORY_OFFSET + RESOURCE_COUNT * 4
    if directory_end > len(data):
        raise ValueError("acting directory is outside input")
    resources: dict[str, list[dict[str, Any]]] = {}
    for resource_id in range(RESOURCE_COUNT):
        relative = read_u32(data, DIRECTORY_OFFSET + resource_id * 4, "acting directory")
        start = DATA_OFFSET + relative
        resources[str(resource_id)] = parse_resource(data, start, resource_id)
    return resources


def render(resources: dict[str, list[dict[str, Any]]]) -> str:
    """Use one canonical representation so reruns produce byte-identical JSON."""

    return json.dumps(
        {"schema_version": 1, "resources": resources},
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def main() -> int:
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        return selftest()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="local, user-supplied FD2.EXE")
    parser.add_argument("output", type=Path, help="editable acting-resource JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless output already equals the deterministic regenerated content",
    )
    args = parser.parse_args()

    output = render(export_resources(args.executable))
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != output:
            raise SystemExit(f"{args.output} is not current; rerun this extractor")
        print(f"verified {RESOURCE_COUNT} acting resources in {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(f"exported {RESOURCE_COUNT} acting resources -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
