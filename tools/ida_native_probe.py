"""fd2_re - IDA Pro 內部腳本:傾印單一函式的反編譯結果。

**這支不是給命令列跑的**,它 import 的 `ida_auto`/`idaapi`/`ida_hexrays` 只存在於
IDA Pro 的內嵌直譯器裡,在一般 python 下必定 `ModuleNotFoundError`。用法是把它
交給 IDA 的批次模式(容器內路徑 `/work/decomp.out` 是輸出),目標位址由環境變數
`IDA_TARGET` 指定,預設 `0x1B8E7`。

因此它也**沒有、而且不可能有 selftest**:任何自檢都得先進得了 IDA 的執行環境。
它在 `docs/data/hygiene_baseline.json` 裡以這個理由列管。與它對應的、跑得起來的
交叉驗證管道是 `tools/ida_export_fd2_xrefs.py` 的輸出,以及本專案主要使用的
Ghidra 路徑(`tools/ghidra_batch_probe.py`)。
"""

import ida_auto
import ida_funcs
import ida_xref
import idaapi
import idc
import ida_hexrays
import os

TARGET = int(os.environ.get("IDA_TARGET", "0x1B8E7"), 0)

def main():
    ida_auto.auto_wait()
    out = open("/work/decomp.out", "w", encoding="utf-8")
    def emit(*args):
        print(*args, file=out)
        out.flush()
    fn = ida_funcs.get_func(TARGET)
    emit("TARGET", hex(TARGET), "FUNC", None if not fn else (hex(fn.start_ea), hex(fn.end_ea)))
    try:
        if fn and ida_hexrays.init_hexrays_plugin():
            cfunc = ida_hexrays.decompile(fn.start_ea)
            if cfunc:
                emit("DECOMP_START")
                emit(str(cfunc))
                emit("DECOMP_END")
    except Exception as exc:
        emit("DECOMP_ERROR", repr(exc))
    cur = ida_xref.get_first_cref_to(TARGET)
    while cur != idaapi.BADADDR:
        f = ida_funcs.get_func(cur)
        emit("CALLER", hex(cur), "FUNC", None if not f else (hex(f.start_ea), hex(f.end_ea)))
        for ea in range(max(cur - 0x20, f.start_ea if f else cur - 0x20), cur):
            m = idc.print_insn_mnem(ea)
            if m in ("push", "mov", "lea", "add", "sub"):
                emit("  PRE", hex(ea), m, idc.generate_disasm_line(ea, 0) or "")
        cur = ida_xref.get_next_cref_to(TARGET, cur)
    idc.qexit(0)

if __name__ == "__main__":
    main()
