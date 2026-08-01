// 匯出標題 CONTINUE 的原始函式名稱、線性位址、交叉參照及直接指令。
//
// 本腳本只讀 IDA 資料庫，不改名、不套型別，也不寫回註解。輸出保留
// 原始定位資訊，語意與推論等級由 docs/data 的證據紀錄附加。

#include <idc.idc>

static dump_function(out, target) {
    auto start, end, ea, x, caller;
    start = get_func_attr(target, FUNCATTR_START);
    end = get_func_attr(target, FUNCATTR_END);
    fprintf(out, "=== target %x ===\n", target);
    if (start == BADADDR || end == BADADDR) {
        fprintf(out, "function=<none>\n");
        return;
    }
    fprintf(out, "function=%x..%x name=%s\n", start, end, get_func_name(start));
    for (x = get_first_cref_to(start); x != BADADDR; x = get_next_cref_to(start, x)) {
        caller = get_func_attr(x, FUNCATTR_START);
        fprintf(out, "xref=%x caller=%x instruction=%s\n", x, caller, GetDisasm(x));
    }
    fprintf(out, "instructions:\n");
    for (ea = start; ea != BADADDR && ea < end; ea = next_head(ea, end)) {
        if (is_code(get_full_flags(ea))) {
            fprintf(out, "%x %s\n", ea, GetDisasm(ea));
        }
    }
}

static main() {
    auto out;
    Wait();
    out = fopen("/work/fd2-continue-controller-ida.txt", "w");
    if (out == 0) qexit(2);
    dump_function(out, 0x10010);
    dump_function(out, 0x117e7);
    dump_function(out, 0x11cac);
    dump_function(out, 0x1297d);
    dump_function(out, 0x25bf4);
    dump_function(out, 0x25ebb);
    dump_function(out, 0x4e031);
    fclose(out);
    qexit(0);
}
