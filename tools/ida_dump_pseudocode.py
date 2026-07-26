"""Headless IDA/Hex-Rays probe for explicitly requested FD2 functions.

The script is intended to run inside the user-authorized IDA Docker image;
output is written to the caller-provided path so no IDA database is stored in
the repository.
"""
import sys

import ida_auto
import ida_hexrays
import idaapi


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fd2-pseudocode.txt"
    addresses = [int(value, 16) for value in sys.argv[2:]] or [0x15B77, 0x15DA2]
    ida_auto.auto_wait()
    if not ida_hexrays.init_hexrays_plugin():
        raise RuntimeError("Hex-Rays is unavailable")
    with open(out_path, "w", encoding="utf-8") as out:
        for address in addresses:
            out.write(f"=== {address:#x} ===\n")
            function = idaapi.get_func(address)
            if function is None:
                out.write("<no function>\n")
                continue
            cfunc = ida_hexrays.decompile(function)
            out.write(str(cfunc) if cfunc is not None else "<decompile failed>")
            out.write("\n")
    idaapi.qexit(0)


main()
