"""Export IDA data xrefs for explicitly requested FD2 globals.

Run only inside the user-authorized local IDA Docker environment. Targets and
output are supplied through environment variables so Docker entrypoints that
misparse IDA's quoted -S arguments can still run the script reproducibly.
"""

import os

import ida_auto
import ida_funcs
import ida_xref
import idaapi
import idc


def function_bounds(ea):
    function = ida_funcs.get_func(ea)
    if function is None:
        return None
    return function.start_ea, function.end_ea


def main():
    targets = [
        int(value, 16)
        for value in os.environ.get(
            "FD2_IDA_DATA_TARGETS", "53c1f 51a83 51aab 51aac 51a0c"
        ).split()
    ]
    out_path = os.environ.get("FD2_IDA_OUTPUT", "/tmp/fd2-data-xrefs.txt")
    ida_auto.auto_wait()
    with open(out_path, "w", encoding="utf-8") as out:
        for target in targets:
            out.write(f"=== {target:#x} ===\n")
            current = ida_xref.get_first_dref_to(target)
            while current != idaapi.BADADDR:
                bounds = function_bounds(current)
                function = (
                    "<none>"
                    if bounds is None
                    else f"{bounds[0]:#x}..{bounds[1]:#x}"
                )
                line = idc.generate_disasm_line(current, 0) or ""
                out.write(f"{current:#x} function={function} {line}\n")
                current = ida_xref.get_next_dref_to(target, current)
    idc.qexit(0)


if __name__ == "__main__":
    main()
