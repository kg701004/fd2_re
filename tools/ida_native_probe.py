import ida_auto
import ida_funcs
import ida_xref
import idaapi
import idc
import ida_hexrays

TARGET = 0x1B8E7

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
