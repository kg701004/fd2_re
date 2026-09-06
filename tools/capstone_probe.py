#!/usr/bin/env python3
"""fd2_re — chunked-fetch + local Capstone disassembly, independent of Ghidra's own disassembler.

背景(item 1117 SFX sample-identity調查,2026-09-06)：`ghidra_batch_probe.py`的`disasm`
action是Ghidra自己`getInstructionAt`/`.getNext()`的flow-directed反組譯，遇到「還沒被
Ghidra辨識成指令邊界」的位址(`-noanalysis`模式下常見，尤其是函式中段、非call-target的位址)
會回傳`count:0, stop_reason:"end_of_code"`的空結果，即使那個位址明明有真實可執行的code——
親測`0x1c5d0`/`0x1c5c0`皆是這樣，但這兩個位址本身在FUN_0001c4cc函式體內部，是合法的、
可執行的指令開頭。這個工具改用完全不同的路徑繞開這個問題：用`ghidra_batch_probe.py`的
`bytes` action(不做任何指令邊界判斷，純粹讀raw bytes)分段(每段<=32 bytes，`bytes`
action在本專案實測的單次上限)撈出一段連續記憶體，本地串接後餵給獨立安裝的capstone函式庫
做反組譯——不依賴Ghidra的指令資料庫，只要記憶體內容正確就一定能反組譯出正確結果(這是
x86定長對齊以外唯一可靠的反組譯方式)。

只跑一次`analyzeHeadless`(所有分段bytes查詢包在同一份queries.json裡)，不是每個32-byte
chunk各自啟動一次JVM——批次成本攤提，用法示範見`--selftest`。

用法:
    python tools/capstone_probe.py --address 0x1c4cc --length 200
    python tools/capstone_probe.py --address 0x1c4cc --length 200 --output out.json
    python tools/capstone_probe.py --selftest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import capstone

import ghidra_batch_probe as gbp

CHUNK_SIZE = 32  # matches ghidra_batch_probe.py's own documented per-call practical cap for `bytes`


def fetch_bytes(
    address: int,
    length: int,
    *,
    ghidra_install: str = gbp.DEFAULT_GHIDRA_INSTALL,
    project_dir: str = gbp.DEFAULT_PROJECT_DIR,
    project_name: str = gbp.DEFAULT_PROJECT_NAME,
    process_name: str = gbp.DEFAULT_PROCESS_NAME,
    timeout: int = 600,
    quiet: bool = True,
) -> bytes:
    """Fetch `length` bytes starting at `address` from the live Ghidra project, chunked and
    stitched, in exactly one analyzeHeadless invocation regardless of how many chunks it takes."""
    queries = []
    offset = 0
    while offset < length:
        chunk_len = min(CHUNK_SIZE, length - offset)
        queries.append(
            {
                "id": f"chunk_{offset:08x}",
                "address": hex(address + offset),
                "action": "bytes",
                "count": chunk_len,
            }
        )
        offset += chunk_len

    with tempfile.TemporaryDirectory(prefix="capstone_probe_") as tmpdir:
        queries_path = Path(tmpdir) / "queries.json"
        output_path = Path(tmpdir) / "results.json"
        queries_path.write_text(json.dumps(queries), encoding="utf-8")

        cmd = gbp.build_command(ghidra_install, project_dir, project_name, process_name, queries_path, output_path)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if not quiet:
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)
        if not output_path.exists():
            raise RuntimeError(
                f"capstone_probe: analyzeHeadless produced no output file. "
                f"returncode={proc.returncode}\nstdout tail:\n{proc.stdout[-2000:]}\nstderr tail:\n{proc.stderr[-2000:]}"
            )
        results = json.loads(output_path.read_text(encoding="utf-8"))

    by_id = {r["id"]: r for r in results}
    blob = bytearray()
    for q in queries:
        r = by_id.get(q["id"])
        if r is None or not r.get("ok"):
            raise RuntimeError(f"capstone_probe: chunk {q['id']} failed or missing: {r}")
        chunk_hex = r["result"]["hex"].replace(" ", "")
        blob += bytes.fromhex(chunk_hex)
    if len(blob) != length:
        raise RuntimeError(f"capstone_probe: expected {length} bytes, got {len(blob)}")
    return bytes(blob)


def disassemble(address: int, data: bytes) -> list[dict]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = []
    for ins in md.disasm(data, address):
        out.append(
            {
                "address": f"0x{ins.address:x}",
                "mnemonic": ins.mnemonic,
                "operands": ins.op_str,
                "bytes": ins.bytes.hex(),
                "size": ins.size,
            }
        )
    return out


# ===========================================================================================
# --selftest: pinned against instructions independently hand-verified during the item 1117 SFX
# sample-identity investigation (2026-09-06) -- these exact address/mnemonic/operand triples were
# read off this tool's own output and cross-checked by hand against the decompile's stack-offset
# arithmetic (see docs/knowledge-base/91-worklist.md item 1117, "2026-09-06再續十一" or later).
# A future Ghidra reanalysis, EXE swap, or bug in the chunking/stitching above should break at
# least one of these.
# ===========================================================================================

_SELFTEST_CASES = [
    # FUN_0001c4cc prologue: proves the Watcom stack-check call, the register-saves, and the
    # critical `mov ebp, [esp+0x8c]` (EBP used as a copy of param_2, not a frame pointer) all
    # decode correctly across a chunk boundary (0x1c4cc..0x1c4ec spans 2 chunks).
    (0x1C4CC, "push", "0xa0"),
    (0x1C4D1, "call", "0x3702f"),
    (0x1C4D6, "push", "ebx"),
    (0x1C4D9, "push", "ebp"),
    (0x1C4DA, "sub", "esp, 0x74"),
    (0x1C4DD, "mov", "ebp, dword ptr [esp + 0x8c]"),
    # The SFX dispatch call site itself: push 1 (priority) / movzx eax,[esp+ebp+0x28] (index,
    # resolved to be local_60[param_2], the same byte used as the trigger-flag condition) /
    # push eax / push [0x53b13] (table_ptr) / call 0x25a96 (play_sfx_a).
    (0x1C64E, "push", "1"),
    (0x1C650, "movzx", "eax, byte ptr [esp + ebp + 0x28]"),
    (0x1C656, "push", "dword ptr [0x53b13]"),
    (0x1C65C, "call", "0x25a96"),
]


def run_selftest(args: argparse.Namespace) -> int:
    address = 0x1C4CC
    length = 0x1A0  # covers 0x1c4cc..0x1c66c, well past the last pinned case
    print(f"[capstone_probe --selftest] fetching 0x{length:x} bytes from 0x{address:x}...")
    try:
        data = fetch_bytes(
            address,
            length,
            ghidra_install=args.ghidra,
            project_dir=args.project_dir,
            project_name=args.project_name,
            process_name=args.process_name,
            timeout=args.timeout,
            quiet=args.quiet,
        )
    except Exception as exc:  # noqa: BLE001 - selftest wants to report, not crash opaquely
        print(f"[capstone_probe --selftest] FETCH FAILED: {exc}")
        return 1

    instructions = disassemble(address, data)
    by_addr = {ins["address"]: ins for ins in instructions}

    failures = []
    for addr, expect_mnemonic, expect_operands in _SELFTEST_CASES:
        key = f"0x{addr:x}"
        got = by_addr.get(key)
        if got is None:
            failures.append(f"{key}: MISSING (no instruction decoded at this address)")
            continue
        if got["mnemonic"] != expect_mnemonic or got["operands"] != expect_operands:
            failures.append(
                f"{key}: expected `{expect_mnemonic} {expect_operands}`, "
                f"got `{got['mnemonic']} {got['operands']}`"
            )

    if failures:
        print(f"[capstone_probe --selftest] FAIL ({len(failures)}/{len(_SELFTEST_CASES)} mismatches):")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"[capstone_probe --selftest] PASS ({len(_SELFTEST_CASES)}/{len(_SELFTEST_CASES)} pinned instructions match)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--address", type=lambda s: int(s, 0), help="Start address (e.g. 0x1c4cc).")
    ap.add_argument("--length", type=lambda s: int(s, 0), default=64, help="Bytes to fetch and disassemble.")
    ap.add_argument("--output", type=Path, help="Optional path to write the instruction list as JSON.")
    ap.add_argument("--ghidra", default=gbp.DEFAULT_GHIDRA_INSTALL)
    ap.add_argument("--project-dir", default=gbp.DEFAULT_PROJECT_DIR)
    ap.add_argument("--project-name", default=gbp.DEFAULT_PROJECT_NAME)
    ap.add_argument("--process-name", default=gbp.DEFAULT_PROCESS_NAME)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--quiet", action="store_true", help="Suppress raw analyzeHeadless stdout/stderr.")
    ap.add_argument("--selftest", action="store_true", help="Run the fault-injection-style regression check instead of a real query.")
    args = ap.parse_args()

    if args.selftest:
        return run_selftest(args)

    if args.address is None:
        ap.error("--address is required unless --selftest is given")

    data = fetch_bytes(
        args.address,
        args.length,
        ghidra_install=args.ghidra,
        project_dir=args.project_dir,
        project_name=args.project_name,
        process_name=args.process_name,
        timeout=args.timeout,
        quiet=args.quiet,
    )
    instructions = disassemble(args.address, data)
    for ins in instructions:
        print(f"{ins['address']}: {ins['mnemonic']} {ins['operands']}")

    if args.output:
        args.output.write_text(json.dumps(instructions, indent=2), encoding="utf-8")
        print(f"[capstone_probe] wrote {len(instructions)} instructions to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
