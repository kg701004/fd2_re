"""Dump explicitly requested IDA database byte ranges.

Run only inside the user-authorized local IDA Docker environment. Ranges use
START:SIZE (hex is accepted); output stays at the caller-selected path.
"""

import os

import ida_auto
import ida_bytes
import idaapi


def main():
    ranges = os.environ.get("FD2_IDA_BYTE_RANGES", "").split()
    out_path = os.environ.get("FD2_IDA_OUTPUT", "/tmp/fd2-bytes.txt")
    if not ranges:
        raise RuntimeError("FD2_IDA_BYTE_RANGES is empty")
    ida_auto.auto_wait()
    with open(out_path, "w", encoding="utf-8") as out:
        for item in ranges:
            start_text, size_text = item.split(":", 1)
            start = int(start_text, 0)
            size = int(size_text, 0)
            data = ida_bytes.get_bytes(start, size)
            if data is None or len(data) != size:
                out.write(f"=== {start:#x}:{size:#x} ===\n<unavailable>\n")
                continue
            out.write(f"=== {start:#x}:{size:#x} ===\n{data.hex(' ')}\n")
    idaapi.qexit(0)


main()
