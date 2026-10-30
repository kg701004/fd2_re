"""fd2_calllog_patch.py —— 在 DOSBox-X 的 src/debug/debug.cpp 加「函式呼叫紀錄」(fd2_re 本地修補,不是上游功能)。

用途:名稱的實機驗證要逐一在函式入口下斷點、讀參數、在返回處讀回傳值;互動式斷點一次只能看一個。
這個修補在重度除錯核心每條指令的掛勾(`DEBUG_HeavyIsBreakpoint`)裡做同一件事:列在入口檔的每個 EIP
被執行時寫一筆 E(暫存器、返回位址上方 8 個 dword、16 個碼位元組、各參數指向的記憶體),控制回到返回位址時
寫 R(eax / edx)。一次執行就有全部入口的參數與回傳;解析與檢查在 `tools/verify_names_by_calllog.py`。
沒有設 FD2_CALLLOG_ENTRIES 時每條指令只多一個布林判斷,其餘行為與原版相同。

只修補**複本樹**,不碰 harness 預設用的建置(doc48 §8 的 ~/fd2-dosbox-build):

    cp -a ~/fd2-dosbox-build ~/fd2-dosbox-calllog
    cd ~/fd2-dosbox-calllog/dosbox-x
    for f in $(grep -rl /home/$USER/fd2-dosbox-build/ --include=Makefile .); do
        sed -i "s#/home/$USER/fd2-dosbox-build/#/home/$USER/fd2-dosbox-calllog/#g" $f; done
    python3 <repo>/tools/dosbox/fd2_calllog_patch.py ~/fd2-dosbox-calllog/dosbox-x
    make -j4

再以 `FD2_HARNESS_DOSBOX_BIN=~/fd2-dosbox-calllog/dosbox-x/src/dosbox-x FD2_HARNESS_CALLLOG=<入口檔>`
啟動 harness。記錄格式寫在插入的 C++ 註解裡。2026-10-08 續一百零七。

2026-10-27 續一百五十七:加兩個選用變數(harness 的 FD2_HARNESS_CALLLOG_ICOUNT / FD2_HARNESS_CALLLOG_GATE)。
FD2_CALLLOG_ICOUNT=1 在 E / R / A 行尾附指令數與模擬時間,用來量函式內部花了多久(BIOS tick 只有約 55 ms 的解析度);
FD2_CALLLOG_GATE=<EIP> 在那個 EIP 第一次執行之前不寫 E,免得開機以來每一幀的重畫都進紀錄。兩個都不設時輸出與之前逐字相同。
`verify_names_by_calllog.py` 的解析器只收沒有附加欄位的形式,附了指令數的紀錄不要取 `*_CALLLOG.TXT` 的檔名。

2026-10-30 續一百七十一:加 FD2_CALLLOG_SEGS(harness 的 FD2_HARNESS_CALLLOG_SEGS)。呼叫紀錄原本只數非遊戲指令的條數,
看不到它們落在 DOS/4GW、驅動還是 BIOS 的哪一段,硬體中斷在哪一條指令收的也只能推。設了之後,在指定的模擬時間窗內
每段「同一 code selector、同一 CPU 模式」的連續指令寫一筆 G(起訖 EIP、條數;第一次看到的起點附 16 個碼位元組),
窗尾加 `:x` 的窗改成每條指令一筆 S;每次 `CPU_Interrupt` 寫一筆 I(中斷號、種類、當時的 CS:EIP)。I 要另外修補
src/cpu/cpu.cpp(`CPU_Interrupt` 開頭呼叫 `fd2calllog_interrupt`)。解析在 `tools/calllog_segments.py`。不設時輸出與之前逐字相同。
已修補過舊版的樹用 `--upgrade` 換掉舊的插入段(目的檔留著,make 只重編 debug.cpp / cpu.cpp)。
2026-10-30 續一百七十二:加 FD2_CALLLOG_SLICES(harness 的 FD2_HARNESS_CALLLOG_SLICES)。續一百六十五「delay 每條指令的週期數隨時段變 0.5%」
與續一百七十一「同一條 rep 多記一次」都推到 DOSBox-X 的時間片,但紀錄看不到時間片。設了之後每筆 E / R / A / I / G / S 附
「到這條指令為止」的時間片數 k、片起點多出的週期 b、片內多出的週期 w(定義寫在插入的 C++ 註解);不設時輸出與之前逐字相同。
同輪另加 FD2_CALLLOG_PICEV(harness 的 FD2_HARNESS_CALLLOG_PICEV):時間片是在下一個 PIC 事件處切的,要知道片頭每 ms 多出的
約 22 片是哪個模擬裝置排的事件,就在 src/hardware/pic.cpp 的 PIC_RunQueue 呼叫處理函式之前計數,每 100 ms 寫一筆 P。
`--selftest` 只檢查文字修補本身(錨點、重複修補、升級、兩檔一致);C++ 是否編得過、紀錄是否正確要實際建置再跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

ANCHOR = "bool DEBUG_HeavyIsBreakpoint(void) {\n"
HOOK = "\tfd2calllog::step();\n"
BEGIN = "/* ---- fd2_re: function call log (local patch, not upstream; tools/dosbox/fd2_calllog_patch.py) ----\n"
END = "/* ---- end fd2_re call log ---- */\n"
# 續一百七十以前的插入段沒有 END,以 namespace 結尾加一個空行收尾。
OLD_END = "} // namespace fd2calllog\n\n"

CPU_ANCHOR = "\tlastint=(uint8_t)num;\n\tFillFlags();\n"
CPU_HOOK = ("#if C_DEBUG && C_HEAVY_DEBUG\n"
            "\t{ void fd2calllog_interrupt(Bitu num,Bitu type,uint32_t oldeip); /* fd2_re local patch */\n"
            "\t  fd2calllog_interrupt(num,type,oldeip); }\n"
            "#endif\n")

# 續一百七十二:PIC 事件的處理函式計數(src/hardware/pic.cpp 的 PIC_RunQueue)。if 的本體只有一行,所以插在 if 之前。
PIC_ANCHOR = ("            if (entry->pic_event != NULL)\n"
              "                (entry->pic_event)(entry->value); // call the event handler\n")
PIC_HOOK = ("#if C_DEBUG && C_HEAVY_DEBUG\n"
            "            { void fd2calllog_picevent(void *fn); /* fd2_re local patch */\n"
            "              fd2calllog_picevent((void *)entry->pic_event); }\n"
            "#endif\n")

CODE = BEGIN + r''' * Enabled only when env FD2_CALLLOG_ENTRIES names a file of hex EIPs (whitespace separated).
 * For a listed EIP executed in code selector FD2_CALLLOG_CS (hex, default 0170), the first
 * FD2_CALLLOG_CAP (default 200) hits per entry write an E record:
 *   E seq eip ret[?] esp ss eax ebx ecx edx esi edi ebp s=<8 dwords above ret> c=<16 code bytes>
 *     m=<FD2_CALLLOG_DUMP bytes (default 32, max 256) at DS:value for eax,edx,ebx,ecx,esi,edi,s1..s4>
 *   ("?" after ret = [esp] unreadable; "??" = unreadable byte).
 * R seq entry eax edx esp: control reached the return address ([esp] at entry) with a higher esp
 *   on the same stack.  A seq entry eip esp: the frame was left by a higher esp at another EIP.
 * Every hit is counted; "T tag n" + "C eip count" (changed counts) are written every 2^26
 * game-selector instructions and at exit.  Output: FD2_CALLLOG_OUT (default CALLLOG.TXT).
 * Optional (all unset = output identical to the version without them):
 *   FD2_CALLLOG_ICOUNT=1 appends " i=<game-selector instructions> n=<all instructions> t=<PIC_FullIndex ms>"
 *     to every E, R and A record and " icount=1" to H; the counts include the current instruction.
 *   FD2_CALLLOG_GATE=<hex eip> writes no E record (and tracks no frame) until that EIP has executed in the
 *     game selector; hits are still counted.  H gets " gate=<eip>".
 *   FD2_CALLLOG_SEGS=<t0>-<t1>[:x][,<t0>-<t1>[:x]...] (PIC_FullIndex ms, t0 inclusive, t1 exclusive): inside a
 *     window, every selector is followed, not only the game's.  H gets " segs=<spec>".
 *       G m cs eip0 eip1 count n=<all instructions through eip1>[ c=<16 code bytes at cs:eip0>]
 *         one run of consecutive instructions with the same code selector and CPU mode; eip0 / eip1 are
 *         the first / last executed (not a range), c= only the first time (m, cs, eip0) is seen.
 *       S m cs eip n=<all instructions through this one>[ c=<16 code bytes>]
 *         in a window ending in ":x", one record per instruction instead of G; c= on first sighting.
 *       I num type m cs eip n=<all instructions executed before it> t=<ms>
 *         every CPU_Interrupt call (needs the src/cpu/cpu.cpp hook); m cs = the selector it was taken in,
 *         eip = the eip CPU_Interrupt is given (hardware: the interrupted instruction; software: the
 *         instruction after INT).  type = CPU_INT_* bits (0 hardware, 1 software, 2/6 exception).
 *     m = r real mode, v V86, p 16-bit protected, P 32-bit protected.  An open run is closed by an I record,
 *     a selector or mode change, the window's end and exit.
 *   FD2_CALLLOG_SLICES=1 appends " k=<slices> b=<cycles> w=<cycles>" (cumulative, through the current
 *     instruction) at the end of E / R / A (after i= n= t= when ICOUNT is set) and I, and after n= on G / S;
 *     H gets " slices=1".  Emulated time in
 *     cycles is A = PIC_Ticks * CPU_CycleMax + CPU_CycleMax - CPU_CycleLeft - CPU_Cycles, read at every
 *     instruction; d = A - A(previous instruction) - 1 is the time that passed beyond one cycle per instruction.
 *     A slice starts when CPU_CycleLeft or PIC_Ticks differs from the previous instruction's: k counts them,
 *     b sums d over slice-start instructions, w sums d over the others (REP iterations, I/O delay).
 *   FD2_CALLLOG_PICEV=1 counts PIC event handler calls (needs the src/hardware/pic.cpp hook) per 100 ms of
 *     emulated time and writes, when a 100 ms bucket ends (and at exit):
 *       P <bucket start ms> <handler address>=<calls>[ ...]   (addresses ascending)
 *     H gets " picev=<run-time address of fd2calllog_picevent>"; subtract its nm address to resolve handlers.
 */
#include <unordered_set>
#include <map>
void fd2calllog_picevent(void *fn);
namespace fd2calllog {
struct Frame { uint32_t ret, esp, entry; uint16_t ss; unsigned long long seq; };
struct Win { double t0, t1; bool each; };
static bool inited = false, enabled = false;
static FILE *out = NULL;
static uint16_t game_cs = 0x170;
static uint32_t lo = 0, hi = 0;
static std::vector<uint8_t> isentry;
static std::vector<unsigned long long> calls, dumped_calls;
static std::vector<unsigned long long> logged;
static std::vector<Frame> frames;
static unsigned long long seq = 0, ginstr = 0, cap = 200;
static uint32_t dumplen = 32;
static bool icount = false, has_gate = false, gate_open = true;
static uint32_t gate_eip = 0;
static unsigned long long allinstr = 0;
/* FD2_CALLLOG_SEGS state */
static bool segs = false;
static std::vector<Win> seg_win;
static std::unordered_set<unsigned long long> seen;
static bool run_open = false, run_first = false;
static char run_m = 0;
static uint16_t run_cs = 0;
static uint32_t run_e0 = 0, run_e1 = 0;
static unsigned long long run_n = 0, run_last = 0;
static uint8_t run_code[16];
static bool run_bad[16];
static unsigned long long run_k = 0;
static long long run_b = 0, run_w = 0;
/* FD2_CALLLOG_SLICES state */
static bool slices = false, sl_have = false;
static unsigned long long sl_k = 0;
static long long sl_b = 0, sl_w = 0, sl_a = 0, sl_left = 0;
static Bitu sl_ticks = 0;
/* FD2_CALLLOG_PICEV state */
static bool picev = false;
static std::map<uintptr_t, unsigned long long> pe_counts;
static long long pe_bucket = -1;

static void pe_flush(void) {
    if (pe_counts.empty()) return;
    fprintf(out, "P %lld", pe_bucket * 100);
    for (std::map<uintptr_t, unsigned long long>::const_iterator it = pe_counts.begin(); it != pe_counts.end(); ++it)
        fprintf(out, " %llx=%llu", (unsigned long long)it->first, it->second);
    fputc('\n', out);
    pe_counts.clear();
}

static void put_slices(unsigned long long k, long long b, long long w) {
    if (slices) fprintf(out, " k=%llu b=%lld w=%lld", k, b, w);
}

static void put_icount(void) {
    if (icount) fprintf(out, " i=%llu n=%llu t=%.6f", ginstr, allinstr, (double)PIC_FullIndex());
    put_slices(sl_k, sl_b, sl_w);
}

static void slice_step(void) {
    const long long a = (long long)PIC_Ticks * (long long)CPU_CycleMax
                        + (long long)(CPU_CycleMax - CPU_CycleLeft - CPU_Cycles);
    const long long left = (long long)CPU_CycleLeft;
    if (sl_have) {
        const long long d = a - sl_a - 1;
        if (left != sl_left || PIC_Ticks != sl_ticks) { sl_k++; sl_b += d; }
        else sl_w += d;
    }
    sl_have = true;
    sl_a = a; sl_left = left; sl_ticks = PIC_Ticks;
}

static char cpu_mode(void) {
    if (!cpu.pmode) return 'r';
    if (GETFLAG(VM)) return 'v';
    return cpu.code.big ? 'P' : 'p';
}

static bool parse_segs(const char *s) {
    while (*s) {
        char *end;
        Win w;
        w.t0 = strtod(s, &end);
        if (end == s || *end != '-') return false;
        s = end + 1;
        w.t1 = strtod(s, &end);
        if (end == s) return false;
        s = end;
        w.each = false;
        if (*s == ':') {
            if (s[1] != 'x') return false;
            w.each = true;
            s += 2;
        }
        if (!(w.t1 > w.t0)) return false;
        seg_win.push_back(w);
        if (*s == ',') {
            s++;
            if (!*s) return false;
        } else if (*s) {
            return false;
        }
    }
    return !seg_win.empty();
}

/* -1 = outside every window, 0 = run window, 1 = per-instruction window */
static int seg_window(void) {
    const double now = (double)PIC_FullIndex();
    for (size_t k = 0; k < seg_win.size(); k++)
        if (now >= seg_win[k].t0 && now < seg_win[k].t1) return seg_win[k].each ? 1 : 0;
    return -1;
}

/* true the first time (m, cs, eip) is seen */
static bool first_sighting(char m, uint16_t c, uint32_t e) {
    const unsigned long long key = ((unsigned long long)(uint8_t)m << 48) | ((unsigned long long)c << 32) | e;
    return seen.insert(key).second;
}

static void read_code(uint8_t *buf, bool *bad) {
    const uint32_t lin = (uint32_t)SegPhys(cs) + reg_eip;
    for (uint32_t k = 0; k < 16; k++) bad[k] = mem_readb_checked((LinearPt)(lin + k), &buf[k]);
}

static void put_code(const uint8_t *buf, const bool *bad) {
    fputs(" c=", out);
    for (int k = 0; k < 16; k++) {
        if (bad[k]) fputs("??", out);
        else fprintf(out, "%02x", (unsigned)buf[k]);
    }
}

static void close_run(void) {
    if (!run_open) return;
    run_open = false;
    fprintf(out, "G %c %04x %08x %08x %llu n=%llu", run_m, (unsigned)run_cs, (unsigned)run_e0, (unsigned)run_e1,
            run_n, run_last);
    put_slices(run_k, run_b, run_w);
    if (run_first) put_code(run_code, run_bad);
    fputc('\n', out);
}

static void seg_step(void) {
    const int w = seg_window();
    if (w < 0) { close_run(); return; }
    const char m = cpu_mode();
    const uint16_t c = SegValue(cs);
    const uint32_t e = reg_eip;
    if (w == 1) {
        close_run();
        fprintf(out, "S %c %04x %08x n=%llu", m, (unsigned)c, (unsigned)e, allinstr);
        put_slices(sl_k, sl_b, sl_w);
        if (first_sighting(m, c, e)) {
            uint8_t buf[16];
            bool bad[16];
            read_code(buf, bad);
            put_code(buf, bad);
        }
        fputc('\n', out);
        return;
    }
    if (run_open && m == run_m && c == run_cs) {
        run_e1 = e;
        run_n++;
        run_last = allinstr;
        run_k = sl_k; run_b = sl_b; run_w = sl_w;
        return;
    }
    close_run();
    run_open = true;
    run_m = m; run_cs = c; run_e0 = e; run_e1 = e; run_n = 1; run_last = allinstr;
    run_k = sl_k; run_b = sl_b; run_w = sl_w;
    run_first = first_sighting(m, c, e);
    if (run_first) read_code(run_code, run_bad);
}

static void dump_counts(const char *tag) {
    fprintf(out, "T %s %llu\n", tag, ginstr);
    for (size_t i = 0; i < calls.size(); i++) {
        if (calls[i] != dumped_calls[i]) {
            fprintf(out, "C %08x %llu\n", (unsigned)(lo + i), calls[i]);
            dumped_calls[i] = calls[i];
        }
    }
    fflush(out);
}

static void at_exit_flush(void) {
    if (enabled && out) { close_run(); pe_flush(); dump_counts("exit"); fclose(out); out = NULL; enabled = false; }
}

static void init(void) {
    inited = true;
    const char *ef = getenv("FD2_CALLLOG_ENTRIES");
    if (!ef || !*ef) return;
    const char *of = getenv("FD2_CALLLOG_OUT");
    const char *cs_s = getenv("FD2_CALLLOG_CS");
    const char *cap_s = getenv("FD2_CALLLOG_CAP");
    const char *dl_s = getenv("FD2_CALLLOG_DUMP");
    if (cs_s && *cs_s) game_cs = (uint16_t)strtoul(cs_s, NULL, 16);
    if (cap_s && *cap_s) cap = strtoull(cap_s, NULL, 10);
    if (dl_s && *dl_s) dumplen = (uint32_t)strtoul(dl_s, NULL, 10);
    if (dumplen > 256) dumplen = 256;
    const char *ic_s = getenv("FD2_CALLLOG_ICOUNT");
    const char *gate_s = getenv("FD2_CALLLOG_GATE");
    const char *segs_s = getenv("FD2_CALLLOG_SEGS");
    const char *sl_s = getenv("FD2_CALLLOG_SLICES");
    const char *pe_s = getenv("FD2_CALLLOG_PICEV");
    icount = ic_s && *ic_s && strcmp(ic_s, "0") != 0;
    slices = sl_s && *sl_s && strcmp(sl_s, "0") != 0;
    picev = pe_s && *pe_s && strcmp(pe_s, "0") != 0;
    if (gate_s && *gate_s) { has_gate = true; gate_open = false; gate_eip = (uint32_t)strtoul(gate_s, NULL, 16); }
    if (segs_s && *segs_s) {
        if (!parse_segs(segs_s)) E_Exit("FD2_CALLLOG: bad FD2_CALLLOG_SEGS '%s' (t0-t1[:x][,...], ms)", segs_s);
        segs = true;
    }
    std::vector<uint32_t> addrs;
    FILE *f = fopen(ef, "r");
    if (!f) E_Exit("FD2_CALLLOG: cannot open entries file %s", ef);
    unsigned int v;
    while (fscanf(f, "%x", &v) == 1) addrs.push_back((uint32_t)v);
    fclose(f);
    if (addrs.empty()) E_Exit("FD2_CALLLOG: no entries read from %s", ef);
    lo = 0xffffffffu; hi = 0;
    for (size_t i = 0; i < addrs.size(); i++) {
        if (addrs[i] < lo) lo = addrs[i];
        if (addrs[i] + 1 > hi) hi = addrs[i] + 1;
    }
    if (hi - lo > 0x1000000u) E_Exit("FD2_CALLLOG: entry span %x too large", (unsigned)(hi - lo));
    isentry.assign(hi - lo, 0);
    for (size_t i = 0; i < addrs.size(); i++) isentry[addrs[i] - lo] = 1;
    calls.assign(hi - lo, 0); dumped_calls.assign(hi - lo, 0); logged.assign(hi - lo, 0);
    out = fopen(of && *of ? of : "CALLLOG.TXT", "w");
    if (!out) E_Exit("FD2_CALLLOG: cannot open output file");
    setvbuf(out, NULL, _IOFBF, 1 << 20);
    fprintf(out, "H fd2calllog 1 cs=%04x entries=%u cap=%llu dump=%u lo=%08x hi=%08x",
            (unsigned)game_cs, (unsigned)addrs.size(), cap, (unsigned)dumplen, (unsigned)lo, (unsigned)hi);
    if (icount) fputs(" icount=1", out);
    if (has_gate) fprintf(out, " gate=%08x", (unsigned)gate_eip);
    if (segs) fprintf(out, " segs=%s", segs_s);
    if (slices) fputs(" slices=1", out);
    if (picev) fprintf(out, " picev=%llx", (unsigned long long)(uintptr_t)&fd2calllog_picevent);
    fputc('\n', out);
    fflush(out);
    atexit(at_exit_flush);
    enabled = true;
}

static void hexdump(uint32_t lin, uint32_t n) {
    for (uint32_t k = 0; k < n; k++) {
        uint8_t b;
        if (mem_readb_checked((LinearPt)(lin + k), &b)) fputs("??", out);
        else fprintf(out, "%02x", (unsigned)b);
    }
}

static void step(void) {
    if (GCC_UNLIKELY(!inited)) init();
    if (!enabled) return;
    allinstr++;
    if (slices) slice_step();
    if (segs) seg_step();
    if (SegValue(cs) != game_cs) return;
    ginstr++;
    const uint32_t eip = reg_eip, esp = reg_esp;
    const uint16_t ssv = SegValue(ss);
    if (!gate_open && eip == gate_eip) gate_open = true;
    while (!frames.empty()) {
        Frame &t = frames.back();
        if (t.ss != ssv || esp <= t.esp) break;
        if (eip == t.ret)
            fprintf(out, "R %llu %08x %08x %08x %08x", t.seq, (unsigned)t.entry,
                    (unsigned)reg_eax, (unsigned)reg_edx, (unsigned)esp);
        else
            fprintf(out, "A %llu %08x %08x %08x", t.seq, (unsigned)t.entry, (unsigned)eip, (unsigned)esp);
        put_icount();
        fputc('\n', out);
        frames.pop_back();
    }
    if (eip >= lo && eip < hi && isentry[eip - lo]) {
        const size_t i = eip - lo;
        calls[i]++;
        if (gate_open && logged[i] < cap) {
            logged[i]++;
            seq++;
            const uint32_t ssb = (uint32_t)SegPhys(ss), dsb = (uint32_t)SegPhys(ds), csb = (uint32_t)SegPhys(cs);
            uint32_t ret = 0, s[9] = {0};
            bool ret_bad = mem_readd_checked((LinearPt)(ssb + esp), &ret);
            for (int k = 1; k <= 8; k++) {
                if (mem_readd_checked((LinearPt)(ssb + esp + 4u * (uint32_t)k), &s[k])) s[k] = 0xdeadbeefu;
            }
            fprintf(out, "E %llu %08x %08x%s %08x %04x %08x %08x %08x %08x %08x %08x %08x s=",
                    seq, (unsigned)eip, (unsigned)ret, ret_bad ? "?" : "", (unsigned)esp, (unsigned)ssv,
                    (unsigned)reg_eax, (unsigned)reg_ebx, (unsigned)reg_ecx, (unsigned)reg_edx,
                    (unsigned)reg_esi, (unsigned)reg_edi, (unsigned)reg_ebp);
            for (int k = 1; k <= 8; k++) fprintf(out, k == 1 ? "%08x" : ",%08x", (unsigned)s[k]);
            fputs(" c=", out);
            hexdump(csb + eip, 16);
            const uint32_t ptrs[10] = { (uint32_t)reg_eax, (uint32_t)reg_edx, (uint32_t)reg_ebx, (uint32_t)reg_ecx,
                                        (uint32_t)reg_esi, (uint32_t)reg_edi, s[1], s[2], s[3], s[4] };
            fputs(" m=", out);
            for (int k = 0; k < 10; k++) { if (k) fputc(',', out); hexdump(dsb + ptrs[k], dumplen); }
            put_icount();
            fputc('\n', out);
            if (!ret_bad) {
                if (frames.size() >= 100000) { fprintf(out, "X frames-overflow %llu\n", seq); frames.clear(); }
                Frame fr; fr.ret = ret; fr.esp = esp; fr.entry = eip; fr.ss = ssv; fr.seq = seq;
                frames.push_back(fr);
            }
            if ((seq & 1023u) == 0) fflush(out);
        }
    }
    if ((ginstr & ((1ull << 26) - 1)) == 0) dump_counts("periodic");
}
} // namespace fd2calllog

/* Called from PIC_RunQueue (src/hardware/pic.cpp, same local patch) before each event handler runs. */
void fd2calllog_picevent(void *fn) {
    if (GCC_UNLIKELY(!fd2calllog::inited)) fd2calllog::init();
    if (!fd2calllog::enabled || !fd2calllog::picev) return;
    const long long bucket = (long long)((double)PIC_FullIndex() / 100.0);
    if (bucket != fd2calllog::pe_bucket) { fd2calllog::pe_flush(); fd2calllog::pe_bucket = bucket; }
    fd2calllog::pe_counts[(uintptr_t)fn]++;
}

/* Called from CPU_Interrupt (src/cpu/cpu.cpp, same local patch) before the interrupt is delivered. */
void fd2calllog_interrupt(Bitu num, Bitu type, uint32_t oldeip) {
    if (GCC_UNLIKELY(!fd2calllog::inited)) fd2calllog::init();
    if (!fd2calllog::enabled || !fd2calllog::segs || fd2calllog::seg_window() < 0) return;
    fd2calllog::close_run();
    fprintf(fd2calllog::out, "I %02x %x %c %04x %08x n=%llu t=%.6f", (unsigned)num, (unsigned)type,
            fd2calllog::cpu_mode(), (unsigned)SegValue(cs), (unsigned)oldeip, fd2calllog::allinstr,
            (double)PIC_FullIndex());
    fd2calllog::put_slices(fd2calllog::sl_k, fd2calllog::sl_b, fd2calllog::sl_w);
    fputc('\n', fd2calllog::out);
}
''' + END + "\n"


def _strip_block(src: str) -> str:
    """拿掉 debug.cpp 裡已插入的呼叫紀錄段(新版以 END 收尾,續一百七十以前的版本以 OLD_END 收尾)。

    Args:
        src: 已修補的 debug.cpp 內容。

    Returns:
        拿掉插入段與 HOOK 後的內容。

    Raises:
        ValueError: 起點、終點或 HOOK 不是恰好一處。
    """
    if src.count(BEGIN) != 1:
        raise ValueError(f"block start found {src.count(BEGIN)} times, expected 1")
    a = src.index(BEGIN)
    if END in src:
        end_mark = END + "\n"
    else:
        end_mark = OLD_END
    if src.count(end_mark) != 1:
        raise ValueError(f"block end found {src.count(end_mark)} times, expected 1")
    b = src.index(end_mark) + len(end_mark)
    if b <= a:
        raise ValueError("block end precedes block start")
    out = src[:a] + src[b:]
    if out.count(ANCHOR + HOOK) != 1:
        raise ValueError("hook after anchor not found exactly once")
    return out.replace(ANCHOR + HOOK, ANCHOR)  # 上面已確認恰好一處


def patch_text(src: str, upgrade: bool = False) -> str:
    """回傳插入呼叫紀錄後的 debug.cpp 內容。

    Args:
        src: 原始 debug.cpp 內容(`upgrade` 時可以是已修補過的版本)。
        upgrade: 已修補過時先拿掉舊的插入段再插入目前版本;沒修補過時與 False 相同。

    Returns:
        修補後內容。

    Raises:
        ValueError: 已修補過而沒有指定 `upgrade`,或錨點(`DEBUG_HeavyIsBreakpoint` 定義)不是恰好一處。
    """
    if "fd2calllog" in src:
        if not upgrade:
            raise ValueError("already patched")
        src = _strip_block(src)
        if "fd2calllog" in src:
            raise ValueError("call-log text left after removing the old block")
    if src.count(ANCHOR) != 1:
        raise ValueError(f"anchor found {src.count(ANCHOR)} times, expected 1")
    return src.replace(ANCHOR, CODE + ANCHOR + HOOK)  # 上面已確認恰好一處


def patch_cpu_text(src: str) -> str:
    """回傳在 `CPU_Interrupt` 開頭加上 `fd2calllog_interrupt` 呼叫後的 cpu.cpp 內容(已加過則原樣回傳)。

    Args:
        src: src/cpu/cpu.cpp 內容。

    Returns:
        修補後內容。

    Raises:
        ValueError: 錨點(`lastint=(uint8_t)num;` 後接 `FillFlags();`)不是恰好一處。
    """
    if "fd2calllog_interrupt" in src:
        if src.count(CPU_ANCHOR + CPU_HOOK) != 1:
            raise ValueError("cpu.cpp mentions fd2calllog_interrupt but not as the expected hook")
        return src
    if src.count(CPU_ANCHOR) != 1:
        raise ValueError(f"cpu.cpp anchor found {src.count(CPU_ANCHOR)} times, expected 1")
    return src.replace(CPU_ANCHOR, CPU_ANCHOR + CPU_HOOK)  # 上面已確認恰好一處


def patch_pic_text(src: str) -> str:
    """回傳在 `PIC_RunQueue` 呼叫事件處理函式之前加上 `fd2calllog_picevent` 呼叫後的 pic.cpp 內容(已加過則原樣回傳)。

    Args:
        src: src/hardware/pic.cpp 內容。

    Returns:
        修補後內容。

    Raises:
        ValueError: 錨點(`if (entry->pic_event != NULL)` 後接呼叫處理函式那行)不是恰好一處。
    """
    if "fd2calllog_picevent" in src:
        if src.count(PIC_HOOK + PIC_ANCHOR) != 1:
            raise ValueError("pic.cpp mentions fd2calllog_picevent but not as the expected hook")
        return src
    if src.count(PIC_ANCHOR) != 1:
        raise ValueError(f"pic.cpp anchor found {src.count(PIC_ANCHOR)} times, expected 1")
    return src.replace(PIC_ANCHOR, PIC_HOOK + PIC_ANCHOR)  # 上面已確認恰好一處


def selftest() -> int:
    """文字修補的自我檢查(不編譯 C++)。

    Returns:
        0 = 全部通過,1 = 有失敗。
    """
    fails: list[str] = []

    def check(cond: bool, what: str) -> None:
        if not cond:
            fails.append(what)

    dbg = "int a;\n#if C_HEAVY_DEBUG\n" + ANCHOR + "\treturn false;\n}\n#endif\n"
    p1 = patch_text(dbg)
    check(p1.count(BEGIN) == 1 and p1.count(END) == 1, "patch inserts one block")
    check(p1.index(BEGIN) < p1.index(ANCHOR) < p1.index(HOOK), "block precedes anchor, hook follows it")
    check(p1.index(ANCHOR + HOOK) >= 0, "hook directly after anchor")
    check(p1.startswith("int a;\n#if C_HEAVY_DEBUG\n" + BEGIN), "block inserted right before the anchor")
    check(p1.endswith(ANCHOR + HOOK + "\treturn false;\n}\n#endif\n"), "text after the anchor unchanged")
    try:
        patch_text(p1)
        check(False, "re-patch without upgrade must fail")
    except ValueError as e:
        check("already patched" in str(e), "re-patch error names the reason")
    p2 = patch_text(p1, upgrade=True)
    check(p2 == p1, "upgrade of the current version is a no-op")
    # 舊版插入段(以 OLD_END 收尾、沒有 END)要能升級成目前版本
    old_block = BEGIN + " * old\n */\nnamespace fd2calllog {\nstatic void step(void) {}\n" + OLD_END
    old = "int a;\n#if C_HEAVY_DEBUG\n" + old_block + ANCHOR + HOOK + "\treturn false;\n}\n#endif\n"
    p3 = patch_text(old, upgrade=True)
    check(p3 == p1, "upgrade from the pre-SEGS block gives the current patch")
    check(" * old\n" not in p3, "old block text removed")
    # 只有 END、沒有 BEGIN(半個插入段)不能被當成已修補而升級
    try:
        patch_text(dbg.replace("int a;", "int a; /* fd2calllog */"), upgrade=True)
        check(False, "upgrade of a tree without the block start must fail")
    except ValueError:
        pass
    try:
        patch_text(dbg + ANCHOR)
        check(False, "two anchors must fail")
    except ValueError as e:
        check("2 times" in str(e), "anchor count reported")
    for env in ("FD2_CALLLOG_ENTRIES", "FD2_CALLLOG_ICOUNT", "FD2_CALLLOG_GATE", "FD2_CALLLOG_SEGS",
                "FD2_CALLLOG_SLICES", "FD2_CALLLOG_PICEV"):
        check(env in CODE, f"CODE reads {env}")
    check("void fd2calllog_interrupt(Bitu num, Bitu type, uint32_t oldeip)" in CODE,
          "CODE defines the function the cpu.cpp hook declares")
    check("fd2calllog_interrupt(Bitu num,Bitu type,uint32_t oldeip)" in CPU_HOOK, "cpu hook declares it")

    cpu = "void CPU_Interrupt(Bitu num,Bitu type,uint32_t oldeip) {\n" + CPU_ANCHOR + "\tx();\n}\n"
    c1 = patch_cpu_text(cpu)
    check(c1 == cpu.replace(CPU_ANCHOR, CPU_ANCHOR + CPU_HOOK), "cpu hook right after FillFlags")
    check(patch_cpu_text(c1) == c1, "cpu re-patch is a no-op")
    try:
        patch_cpu_text(cpu.replace("FillFlags", "FillFlagz"))
        check(False, "missing cpu anchor must fail")
    except ValueError as e:
        check("0 times" in str(e), "cpu anchor count reported")
    try:
        patch_cpu_text(cpu + "/* fd2calllog_interrupt */\n")
        check(False, "a stray mention without the hook must fail")
    except ValueError:
        pass
    check("void fd2calllog_picevent(void *fn) {" in CODE, "CODE defines the function the pic.cpp hook declares")
    check("void fd2calllog_picevent(void *fn);" in PIC_HOOK, "pic hook declares it")
    pic = "\t\twhile (x) {\n" + PIC_ANCHOR + "            else\n                y();\n"
    q1 = patch_pic_text(pic)
    check(q1 == "\t\twhile (x) {\n" + PIC_HOOK + PIC_ANCHOR + "            else\n                y();\n",
          "pic hook right before the if")
    check(patch_pic_text(q1) == q1, "pic re-patch is a no-op")
    try:
        patch_pic_text(pic.replace("pic_event)(entry", "pic_event) (entry"))
        check(False, "missing pic anchor must fail")
    except ValueError as e:
        check("0 times" in str(e), "pic anchor count reported")
    try:
        patch_pic_text(pic + "/* fd2calllog_picevent */\n")
        check(False, "a stray pic mention without the hook must fail")
    except ValueError:
        pass
    for f in fails:
        print("FAIL:", f)
    print("selftest:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1


def main(argv: list[str]) -> int:
    """命令列:`fd2_calllog_patch.py [--upgrade] <dosbox-x 樹根>`,或 `--selftest`。"""
    if argv == ["--selftest"]:
        return selftest()
    upgrade = False
    if argv and argv[0] == "--upgrade":
        upgrade = True
        argv = argv[1:]
    if len(argv) != 1:
        print(__doc__)
        return 2
    root = Path(argv[0])
    p = root / "src" / "debug" / "debug.cpp"
    q = root / "src" / "cpu" / "cpu.cpp"
    r = root / "src" / "hardware" / "pic.cpp"
    src = p.read_text(encoding="utf-8", errors="surrogateescape")
    csrc = q.read_text(encoding="utf-8", errors="surrogateescape")
    psrc = r.read_text(encoding="utf-8", errors="surrogateescape")
    try:
        out = patch_text(src, upgrade=upgrade)
        cout = patch_cpu_text(csrc)
        pout = patch_pic_text(psrc)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1
    if out != src:
        p.write_text(out, encoding="utf-8", errors="surrogateescape", newline="\n")
        print("patched", p)
    else:
        print("unchanged", p)
    if cout != csrc:
        q.write_text(cout, encoding="utf-8", errors="surrogateescape", newline="\n")
        print("patched", q)
    else:
        print("unchanged", q)
    if pout != psrc:
        r.write_text(pout, encoding="utf-8", errors="surrogateescape", newline="\n")
        print("patched", r)
    else:
        print("unchanged", r)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
