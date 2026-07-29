"""輸出指定 FD2 函式的邊界、交叉參照與直接指令。

本腳本只供使用者授權的 IDA Pro Docker 流程使用。輸入位址以
``FD2_IDA_ADDRESSES`` 傳入，輸出只寫到 ``FD2_IDA_OUTPUT`` 指定的位置。
"""

import os

import ida_auto
import ida_bytes
import ida_funcs
import ida_xref
import idaapi
import idc


def code_xrefs_to(address):
    current = ida_xref.get_first_cref_to(address)
    while current != idaapi.BADADDR:
        caller = ida_funcs.get_func(current)
        if caller is None:
            bounds = "<none>"
        else:
            bounds = f"{caller.start_ea:#x}..{caller.end_ea:#x}"
        yield current, bounds
        current = ida_xref.get_next_cref_to(address, current)


def main():
    addresses = [
        int(value, 0)
        for value in os.environ.get("FD2_IDA_ADDRESSES", "").split()
    ]
    if not addresses:
        raise RuntimeError("FD2_IDA_ADDRESSES is empty")
    output = os.environ.get("FD2_IDA_OUTPUT", "/work/fd2-functions.txt")

    ida_auto.auto_wait()
    with open(output, "w", encoding="utf-8") as out:
        for address in addresses:
            out.write(f"=== target {address:#x} ===\n")
            function = ida_funcs.get_func(address)
            if function is None:
                out.write("function=<none>\n")
                continue
            out.write(
                f"function={function.start_ea:#x}..{function.end_ea:#x} "
                f"name={idc.get_func_name(function.start_ea)}\n"
            )
            for source, bounds in code_xrefs_to(function.start_ea):
                line = idc.generate_disasm_line(source, 0) or ""
                out.write(
                    f"xref={source:#x} caller={bounds} instruction={line}\n"
                )
            out.write("instructions:\n")
            for instruction in idautils_func_items(function.start_ea):
                line = idc.generate_disasm_line(instruction, 0) or ""
                out.write(f"{instruction:#x} {line}\n")
    idc.qexit(0)


def idautils_func_items(start):
    """避免額外依賴，只沿 IDA 已建立的函式項目列舉。"""
    function = ida_funcs.get_func(start)
    current = function.start_ea
    while current != idaapi.BADADDR and current < function.end_ea:
        if ida_bytes.is_code(ida_bytes.get_full_flags(current)):
            yield current
        current = idc.next_head(current, function.end_ea)


if __name__ == "__main__":
    main()
