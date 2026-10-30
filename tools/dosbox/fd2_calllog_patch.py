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
2026-10-30 續一百七十三:加 FD2_CALLLOG_IO 與 FD2_CALLLOG_KBD(harness 的 FD2_HARNESS_CALLLOG_IO / _KBD)。續一百七十二留下
「SB16.DIG 初始化留下單一樣本 DMA」(DOSBox-X 只在 DMA 計數低於一個樣本時進 DMA_DAC_Event,INFERRED)與「START 那一下為什麼
總撞上 DIG 型重入」:前者要看驅動實際寫了哪些埠、什麼值,後者要知道按鍵是什麼時候進模擬器的(I 紀錄只有 IRQ 1 何時被收)。
IO=<埠範圍> 在 src/hardware/iohandler.cpp 的 IO_ReadB/W/D、IO_WriteB/W/D 記每次存取(O 寫、N 讀),KBD=1 在
src/hardware/keyboard.cpp 的 KEYBOARD_AddBuffer 開頭記每個進鍵盤控制器佇列的位元組(K)。兩個都不設時輸出與之前逐字相同。
`--selftest` 只檢查文字修補本身(錨點、重複修補、升級、各檔一致);C++ 是否編得過、紀錄是否正確要實際建置再跑。
2026-10-31 續一百七十四:加 FD2_CALLLOG_TRIG(harness 的 FD2_HARNESS_CALLLOG_TRIG 與 _TRIGRING / _TRIGPRE / _TRIGCAP)。
G / S 只能用時間窗指定,罕見又不知道何時出現的一段(續一百六十五的 MDI 375、續一百七十三的 DOS/4GW 0070 關中斷 1070 條)
窗外只剩條數。設了之後每條指令與每次 CPU_Interrupt 進記憶體裡的環形緩衝,一段「非遊戲 selector」或「IF = 0」的連續指令結束時,
條數(與第一條的 CS:EIP)符合規則才把前文 + 那一段 + 結束那一條寫成 Y .. YE 區塊;結尾寫每條規則的符合 / 寫出數與區間總數。
不設時輸出與之前逐字相同(`--mocktest --baseline <舊版>` 比對)。
`--mocktest`(要 g++,WSL 端跑):把 CODE 與替身(CPU 狀態、記憶體、PIC 時間)編成小程式,餵合成的指令序列,
以 `tools/calllog_segments.py` 解析並逐項核對觸發的行為(每項都有成對對照)。它只驗 CODE 的邏輯,不驗 DOSBox-X 的掛勾位置。
`--mockmut --baseline <舊版>`:MOCK_MUTANTS 逐一改壞 CODE 再跑 mocktest,每個都要被抓到(故障注入)。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
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

# 續一百七十三:I/O 存取(src/hardware/iohandler.cpp)。寫入掛在 log_io 之後、交給裝置之前;讀出掛在 log_io 之後、return 之前。
IO_HOOKS: list[tuple[str, str]] = [
    (f"\tlog_io({w}, {wr}, port, {v});\n",
     "#if C_DEBUG && C_HEAVY_DEBUG\n"
     "\t{ void fd2calllog_io(Bitu port,Bitu val,unsigned width,bool wr); /* fd2_re local patch */\n"
     f"\t  fd2calllog_io(port,(Bitu){v},{n},{wr}); }}\n"
     "#endif\n")
    for w, n in ((0, 1), (1, 2), (2, 4)) for wr, v in (("true", "val"), ("false", "retval"))]
# 同輪:進鍵盤控制器佇列的位元組(src/hardware/keyboard.cpp),在佇列滿的檢查之前。
KBD_ANCHOR = "void KEYBOARD_AddBuffer(uint16_t data) {\n"
KBD_HOOK = ("#if C_DEBUG && C_HEAVY_DEBUG\n"
            "    { void fd2calllog_key(uint16_t data,unsigned used); /* fd2_re local patch */\n"
            "      fd2calllog_key(data,(unsigned)keyb.used); }\n"
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
 *   FD2_CALLLOG_IO=<hex port>[-<hex port>][,...] logs every IO_Read / IO_Write of those ports (needs the
 *     src/hardware/iohandler.cpp hooks; V86 fake I/O and accesses that bypass IO_Read / IO_Write are not seen):
 *       O port value width m cs eip n=<all instructions through the current one> t=<ms>   (write)
 *       N port value width m cs eip n=... t=...                                       (read; value returned)
 *     width in bytes; m cs eip as seen when the handler runs (eip may already point past the instruction).
 *     Written immediately: an open G run that contains the instruction is written after it (order by n=).
 *     H gets " io=<spec>".
 *   FD2_CALLLOG_KBD=1 writes, at the top of KEYBOARD_AddBuffer (needs the src/hardware/keyboard.cpp hook),
 *       K data used n=... t=...   data = the queued byte (0x100 bit = AUX), used = bytes already queued.
 *     H gets " kbd=1".
 *   O / N / K end with " k= b= w=" when FD2_CALLLOG_SLICES is set.
 *   FD2_CALLLOG_TRIG=<rule>[,<rule>...] keeps the last FD2_CALLLOG_TRIGRING (default 131072, 1024 .. 4194304)
 *     instructions and CPU_Interrupt calls in memory (any selector, independent of FD2_CALLLOG_SEGS) and writes
 *     a span only when it matches a rule.  Spans: "ng" = maximal run of instructions whose code selector is
 *     not FD2_CALLLOG_CS; "if" = maximal run of instructions that start executing with IF = 0.  A span ends at
 *     the first instruction outside it (that instruction is the last one written).  Rule:
 *       <ng|if>:<lo>[-[<hi>]][@<hex cs>[:<hex eip>]]   lo alone = exactly lo, "lo-" = lo or more instructions;
 *       @cs[:eip] = the span's first instruction.
 *     Spans are counted and matched only after the gate opened (FD2_CALLLOG_GATE) and, when
 *     FD2_CALLLOG_TRIGT=<t0>-<t1> (ms) is set, only if they end at t0 <= t < t1; each rule writes at most
 *     FD2_CALLLOG_TRIGCAP (default 20) spans; a span matching several rules is written once (first rule).
 *       Y seq kind rule count n0=<first span instruction> n1=<last span instruction> t0=<ms at span start>
 *         t1=<ms at span end> cs eip[ trunc=1]     (cs eip = the span's first instruction)
 *       YS m cs eip n=<all instructions through this one> if=<IF before it>[ k= b= w=][ c=<16 code bytes>]
 *       YI num type m cs eip n=<instructions before it> t=<ms>[ k= b= w=]
 *       YE seq
 *     from FD2_CALLLOG_TRIGPRE (default 64) instructions before the span through the instruction that ended it.
 *     c= on the first sighting within the block, read when the block is written (code base kept per
 *     instruction).  trunc=1: the ring no longer held the start.  Totals so far, per rule and per kind:
 *       YC rule kind matched written      YN kind spans
 *     after every written block, at the first span end and then every >= 1000 emulated ms (checked at span ends),
 *     and at exit; each block and each set of totals is flushed (a killed emulator keeps them; the last set wins).
 *     H gets " trig=<spec> trigring=<n> trigpre=<n> trigcap=<n>"[ " trigt=<t0>-<t1>"].
 */
#include <cctype>
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
/* FD2_CALLLOG_IO / FD2_CALLLOG_KBD state */
static std::vector<uint8_t> io_ports;   /* 65536 flags when FD2_CALLLOG_IO is set, empty otherwise */
static bool kbd = false;
/* FD2_CALLLOG_TRIG state */
struct TrRule { char kind; unsigned long long lo, hi, matched, written; bool has_cs, has_eip; uint16_t cs; uint32_t eip; };
struct TrEnt { unsigned long long n, k; long long b, w; double t; uint32_t eip, base; uint16_t cs;
               char m, rec; uint8_t num, type, iff; };
struct TrSpan { bool open; unsigned long long n0, n1, count, spans; uint16_t cs; uint32_t eip; double t0; };
static bool trig = false;
static std::vector<TrRule> tr_rules;
static std::vector<TrEnt> tr_ring;
static size_t tr_head = 0, tr_fill = 0;   /* next slot to write, entries held */
static unsigned long long tr_pre = 64, tr_cap = 20, tr_seq = 0;
static bool tr_has_t = false;
static double tr_t0 = 0, tr_t1 = 0, tr_next_sum = 0;   /* FD2_CALLLOG_TRIGT window; next periodic totals */
static TrSpan tr_span[2];                  /* 0 = ng, 1 = if */

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

static bool parse_io(const char *s) {
    io_ports.assign(65536, 0);
    while (*s) {
        char *end;
        const unsigned long a = strtoul(s, &end, 16);
        if (end == s) return false;
        unsigned long b = a;
        s = end;
        if (*s == '-') {
            s++;
            b = strtoul(s, &end, 16);
            if (end == s) return false;
            s = end;
        }
        if (b < a || b > 0xffffUL) return false;
        for (unsigned long k = a; k <= b; k++) io_ports[k] = 1;
        if (*s == ',') {
            s++;
            if (!*s) return false;
        } else if (*s) {
            return false;
        }
    }
    return true;
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

static bool parse_trig(const char *s) {
    while (*s) {
        TrRule r;
        if (!strncmp(s, "ng:", 3)) r.kind = 'n';
        else if (!strncmp(s, "if:", 3)) r.kind = 'i';
        else return false;
        s += 3;
        char *end;
        if (!isdigit((unsigned char)*s)) return false;
        r.lo = strtoull(s, &end, 10);
        s = end;
        r.hi = r.lo;
        if (*s == '-') {
            s++;
            if (isdigit((unsigned char)*s)) { r.hi = strtoull(s, &end, 10); s = end; }
            else r.hi = ~0ull;
        }
        if (r.lo == 0 || r.hi < r.lo) return false;
        r.has_cs = r.has_eip = false; r.cs = 0; r.eip = 0;
        if (*s == '@') {
            s++;
            if (!isxdigit((unsigned char)*s)) return false;
            const unsigned long long v = strtoull(s, &end, 16);
            if (v > 0xffffull) return false;
            r.has_cs = true; r.cs = (uint16_t)v; s = end;
            if (*s == ':') {
                s++;
                if (!isxdigit((unsigned char)*s)) return false;
                const unsigned long long e = strtoull(s, &end, 16);
                if (e > 0xffffffffull) return false;
                r.has_eip = true; r.eip = (uint32_t)e; s = end;
            }
        }
        r.matched = r.written = 0;
        tr_rules.push_back(r);
        if (*s == ',') {
            s++;
            if (!*s) return false;
        } else if (*s) {
            return false;
        }
    }
    return !tr_rules.empty();
}

static void trig_summary(void);

static TrEnt &tr_slot(void) {
    TrEnt &x = tr_ring[tr_head];
    tr_head = (tr_head + 1) % tr_ring.size();
    if (tr_fill < tr_ring.size()) tr_fill++;
    return x;
}

/* write the ring from tr_pre instructions before the span through the newest entry */
static void tr_write(size_t rule, const TrSpan &p) {
    tr_seq++;
    const size_t sz = tr_ring.size();
    const unsigned long long from = p.n0 > tr_pre ? p.n0 - tr_pre : 1;  /* n of the first instruction is 1 */
    size_t i = (tr_head + sz - tr_fill) % sz, left = tr_fill;
    const bool trunc = left == 0 || tr_ring[i].n > from;
    while (left && tr_ring[i].n < from) { i = (i + 1) % sz; left--; }
    fprintf(out, "Y %llu %s %u %llu n0=%llu n1=%llu t0=%.6f t1=%.6f %04x %08x%s\n", tr_seq,
            tr_rules[rule].kind == 'n' ? "ng" : "if", (unsigned)rule, p.count, p.n0, p.n1, p.t0,
            (double)PIC_FullIndex(), (unsigned)p.cs, (unsigned)p.eip, trunc ? " trunc=1" : "");
    std::unordered_set<unsigned long long> local;
    for (; left; left--, i = (i + 1) % sz) {
        const TrEnt &x = tr_ring[i];
        if (x.rec == 'I') {
            fprintf(out, "YI %02x %x %c %04x %08x n=%llu t=%.6f", (unsigned)x.num, (unsigned)x.type, x.m,
                    (unsigned)x.cs, (unsigned)x.eip, x.n, x.t);
            put_slices(x.k, x.b, x.w);
        } else {
            fprintf(out, "YS %c %04x %08x n=%llu if=%u", x.m, (unsigned)x.cs, (unsigned)x.eip, x.n, (unsigned)x.iff);
            put_slices(x.k, x.b, x.w);
            const unsigned long long key = ((unsigned long long)(uint8_t)x.m << 48) |
                                           ((unsigned long long)x.cs << 32) | x.eip;
            if (local.insert(key).second) {
                uint8_t buf[16];
                bool bad[16];
                for (uint32_t k = 0; k < 16; k++) bad[k] = mem_readb_checked((LinearPt)(x.base + x.eip + k), &buf[k]);
                put_code(buf, bad);
            }
        }
        fputc('\n', out);
    }
    fprintf(out, "YE %llu\n", tr_seq);
    trig_summary();
    fflush(out);
}

static void tr_close(int s, TrSpan &p) {
    p.open = false;
    const double now = (double)PIC_FullIndex();
    if (now >= tr_next_sum) { trig_summary(); fflush(out); tr_next_sum = now + 1000.0; }
    if (!gate_open || (tr_has_t && !(now >= tr_t0 && now < tr_t1))) return;
    p.spans++;
    const char kind = s == 0 ? 'n' : 'i';
    bool done = false;
    for (size_t r = 0; r < tr_rules.size(); r++) {
        TrRule &q = tr_rules[r];
        if (q.kind != kind || p.count < q.lo || p.count > q.hi) continue;
        if ((q.has_cs && q.cs != p.cs) || (q.has_eip && q.eip != p.eip)) continue;
        q.matched++;
        if (!done && q.written < tr_cap) { q.written++; done = true; tr_write(r, p); }
    }
}

static void trig_step(void) {
    const char m = cpu_mode();
    const uint16_t c = SegValue(cs);
    const uint32_t e = reg_eip;
    TrEnt &x = tr_slot();
    x.rec = 'S'; x.n = allinstr; x.m = m; x.cs = c; x.eip = e; x.base = (uint32_t)SegPhys(cs);
    x.iff = GETFLAG(IF) ? 1 : 0; x.k = sl_k; x.b = sl_b; x.w = sl_w; x.t = 0; x.num = 0; x.type = 0;
    const bool in[2] = { c != game_cs, x.iff == 0 };
    for (int s = 0; s < 2; s++) {
        TrSpan &p = tr_span[s];
        if (in[s]) {
            if (!p.open) { p.open = true; p.n0 = allinstr; p.count = 0; p.cs = c; p.eip = e; p.t0 = (double)PIC_FullIndex(); }
            p.count++;
            p.n1 = allinstr;
        } else if (p.open) {
            tr_close(s, p);
        }
    }
}

static void trig_irq(Bitu num, Bitu type, uint32_t oldeip) {
    TrEnt &x = tr_slot();
    x.rec = 'I'; x.n = allinstr; x.m = cpu_mode(); x.cs = SegValue(cs); x.eip = oldeip; x.base = 0;
    x.iff = 0; x.k = sl_k; x.b = sl_b; x.w = sl_w; x.t = (double)PIC_FullIndex();
    x.num = (uint8_t)num; x.type = (uint8_t)type;
}

static void trig_summary(void) {
    for (size_t r = 0; r < tr_rules.size(); r++)
        fprintf(out, "YC %u %s %llu %llu\n", (unsigned)r, tr_rules[r].kind == 'n' ? "ng" : "if",
                tr_rules[r].matched, tr_rules[r].written);
    fprintf(out, "YN ng %llu\nYN if %llu\n", tr_span[0].spans, tr_span[1].spans);
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
    if (enabled && out) {
        close_run(); pe_flush();
        if (trig) trig_summary();
        dump_counts("exit"); fclose(out); out = NULL; enabled = false;
    }
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
    const char *io_s = getenv("FD2_CALLLOG_IO");
    const char *kb_s = getenv("FD2_CALLLOG_KBD");
    kbd = kb_s && *kb_s && strcmp(kb_s, "0") != 0;
    if (io_s && *io_s && !parse_io(io_s))
        E_Exit("FD2_CALLLOG: bad FD2_CALLLOG_IO '%s' (hex port or lo-hi, comma separated)", io_s);
    const char *tr_s = getenv("FD2_CALLLOG_TRIG");
    if (tr_s && *tr_s) {
        if (!parse_trig(tr_s))
            E_Exit("FD2_CALLLOG: bad FD2_CALLLOG_TRIG '%s' (<ng|if>:<lo>[-[<hi>]][@cs[:eip]][,...])", tr_s);
        const char *rg_s = getenv("FD2_CALLLOG_TRIGRING");
        const char *pr_s = getenv("FD2_CALLLOG_TRIGPRE");
        const char *tc_s = getenv("FD2_CALLLOG_TRIGCAP");
        unsigned long long ring = 131072;
        if (rg_s && *rg_s) ring = strtoull(rg_s, NULL, 10);
        if (ring < 1024 || ring > 4194304) E_Exit("FD2_CALLLOG: FD2_CALLLOG_TRIGRING '%s' not in 1024 .. 4194304", rg_s);
        if (pr_s && *pr_s) tr_pre = strtoull(pr_s, NULL, 10);
        if (tc_s && *tc_s) tr_cap = strtoull(tc_s, NULL, 10);
        const char *tt_s = getenv("FD2_CALLLOG_TRIGT");
        if (tt_s && *tt_s) {
            char *end;
            tr_t0 = strtod(tt_s, &end);
            if (end == tt_s || *end != '-') E_Exit("FD2_CALLLOG: bad FD2_CALLLOG_TRIGT '%s' (t0-t1, ms)", tt_s);
            const char *b = end + 1;
            tr_t1 = strtod(b, &end);
            if (end == b || *end || !(tr_t1 > tr_t0)) E_Exit("FD2_CALLLOG: bad FD2_CALLLOG_TRIGT '%s' (t0-t1, ms)", tt_s);
            tr_has_t = true;
        }
        tr_ring.assign((size_t)ring, TrEnt());
        for (int s = 0; s < 2; s++) { tr_span[s].open = false; tr_span[s].spans = 0; }
        trig = true;
    }
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
    if (!io_ports.empty()) fprintf(out, " io=%s", io_s);
    if (kbd) fputs(" kbd=1", out);
    if (trig) fprintf(out, " trig=%s trigring=%llu trigpre=%llu trigcap=%llu", tr_s,
                      (unsigned long long)tr_ring.size(), tr_pre, tr_cap);
    if (tr_has_t) fprintf(out, " trigt=%s", getenv("FD2_CALLLOG_TRIGT"));
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
    if (trig) trig_step();
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

/* Called from IO_ReadB/W/D and IO_WriteB/W/D (src/hardware/iohandler.cpp, same local patch). */
void fd2calllog_io(Bitu port, Bitu val, unsigned width, bool wr) {
    if (GCC_UNLIKELY(!fd2calllog::inited)) fd2calllog::init();
    if (!fd2calllog::enabled || fd2calllog::io_ports.empty() || !fd2calllog::io_ports[port & 0xffffu]) return;
    fprintf(fd2calllog::out, "%c %04x %x %u %c %04x %08x n=%llu t=%.6f", wr ? 'O' : 'N', (unsigned)(port & 0xffffu),
            (unsigned)val, width, fd2calllog::cpu_mode(), (unsigned)SegValue(cs), (unsigned)reg_eip,
            fd2calllog::allinstr, (double)PIC_FullIndex());
    fd2calllog::put_slices(fd2calllog::sl_k, fd2calllog::sl_b, fd2calllog::sl_w);
    fputc('\n', fd2calllog::out);
}

/* Called at the top of KEYBOARD_AddBuffer (src/hardware/keyboard.cpp, same local patch). */
void fd2calllog_key(uint16_t data, unsigned used) {
    if (GCC_UNLIKELY(!fd2calllog::inited)) fd2calllog::init();
    if (!fd2calllog::enabled || !fd2calllog::kbd) return;
    fprintf(fd2calllog::out, "K %03x %u n=%llu t=%.6f", (unsigned)data, used, fd2calllog::allinstr,
            (double)PIC_FullIndex());
    fd2calllog::put_slices(fd2calllog::sl_k, fd2calllog::sl_b, fd2calllog::sl_w);
    fputc('\n', fd2calllog::out);
}

/* Called from CPU_Interrupt (src/cpu/cpu.cpp, same local patch) before the interrupt is delivered. */
void fd2calllog_interrupt(Bitu num, Bitu type, uint32_t oldeip) {
    if (GCC_UNLIKELY(!fd2calllog::inited)) fd2calllog::init();
    if (!fd2calllog::enabled) return;
    if (fd2calllog::trig) fd2calllog::trig_irq(num, type, oldeip);
    if (!fd2calllog::segs || fd2calllog::seg_window() < 0) return;
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


def _patch_after(src: str, pairs: list[tuple[str, str]], marker: str, what: str) -> str:
    """每個錨點之後接上它的掛勾;已修補過(含 marker)時確認每組都恰好一處後原樣回傳。

    Raises:
        ValueError: 某個錨點不是恰好一處,或含 marker 卻不是預期的掛勾。
    """
    if marker in src:
        for a, h in pairs:
            if src.count(a + h) != 1:
                raise ValueError(f"{what} mentions {marker} but not as the expected hooks")
        return src
    for a, _h in pairs:
        if src.count(a) != 1:
            raise ValueError(f"{what} anchor {a.strip()!r} found {src.count(a)} times, expected 1")
    for a, h in pairs:
        src = src.replace(a, a + h)  # 上面已確認每個恰好一處
    return src


def patch_io_text(src: str) -> str:
    """回傳在 IO_ReadB/W/D、IO_WriteB/W/D 的 log_io 之後加上 `fd2calllog_io` 呼叫的 iohandler.cpp 內容(已加過則原樣回傳)。"""
    return _patch_after(src, IO_HOOKS, "fd2calllog_io", "iohandler.cpp")


def patch_kbd_text(src: str) -> str:
    """回傳在 KEYBOARD_AddBuffer 開頭加上 `fd2calllog_key` 呼叫的 keyboard.cpp 內容(已加過則原樣回傳)。"""
    return _patch_after(src, [(KBD_ANCHOR, KBD_HOOK)], "fd2calllog_key", "keyboard.cpp")


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
    # 續一百七十三:IO / KBD
    for env in ("FD2_CALLLOG_IO", "FD2_CALLLOG_KBD"):
        check(env in CODE, f"CODE reads {env}")
    check("void fd2calllog_io(Bitu port, Bitu val, unsigned width, bool wr) {" in CODE, "CODE defines fd2calllog_io")
    check("void fd2calllog_key(uint16_t data, unsigned used) {" in CODE, "CODE defines fd2calllog_key")
    check(len(IO_HOOKS) == 6 and all("void fd2calllog_io(Bitu port,Bitu val,unsigned width,bool wr);" in h
                                     for _a, h in IO_HOOKS), "six io hooks declare it")
    check([h.split("fd2calllog_io(port,(Bitu)")[1].split("); }")[0] for _a, h in IO_HOOKS] ==
          ["val,1,true", "retval,1,false", "val,2,true", "retval,2,false", "val,4,true", "retval,4,false"],
          "io hook value / width / direction per anchor")
    check([a for a, _h in IO_HOOKS][:2] == ["\tlog_io(0, true, port, val);\n", "\tlog_io(0, false, port, retval);\n"]
          and IO_HOOKS[5][0] == "\tlog_io(2, false, port, retval);\n", "io anchors")
    check("void fd2calllog_key(uint16_t data,unsigned used);" in KBD_HOOK, "kbd hook declares it")
    io = "".join(f"void F{i}() {{\n{a}\tx();\n}}\n" for i, (a, _h) in enumerate(IO_HOOKS))
    o1 = patch_io_text(io)
    check(o1 == "".join(f"void F{i}() {{\n{a}{h}\tx();\n}}\n" for i, (a, h) in enumerate(IO_HOOKS)),
          "each io hook right after its log_io")
    check(patch_io_text(o1) == o1, "io re-patch is a no-op")
    try:
        patch_io_text(io.replace("log_io(1, true", "log_io(1,true"))
        check(False, "missing io anchor must fail")
    except ValueError as e:
        check("0 times" in str(e), "io anchor count reported")
    try:
        patch_io_text(io + IO_HOOKS[2][0])
        check(False, "duplicated io anchor must fail")
    except ValueError as e:
        check("2 times" in str(e), "io duplicate count reported")
    try:
        patch_io_text(o1.replace(IO_HOOKS[3][0] + IO_HOOKS[3][1], IO_HOOKS[3][0]))
        check(False, "a partly hooked iohandler.cpp must fail")
    except ValueError:
        pass
    kb = "static void x();\n" + KBD_ANCHOR + "    if (keyb.used>=KEYBUFSIZE) {\n"
    k1 = patch_kbd_text(kb)
    check(k1 == "static void x();\n" + KBD_ANCHOR + KBD_HOOK + "    if (keyb.used>=KEYBUFSIZE) {\n",
          "kbd hook right after the function's opening line")
    check(patch_kbd_text(k1) == k1, "kbd re-patch is a no-op")
    try:
        patch_kbd_text(kb.replace("(uint16_t data) {", "(uint16_t data)\n{"))
        check(False, "missing kbd anchor must fail")
    except ValueError as e:
        check("0 times" in str(e), "kbd anchor count reported")
    try:
        patch_kbd_text(kb + "/* fd2calllog_key */\n")
        check(False, "a stray kbd mention without the hook must fail")
    except ValueError:
        pass
    # 續一百七十四:TRIG
    for env in ("FD2_CALLLOG_TRIG", "FD2_CALLLOG_TRIGRING", "FD2_CALLLOG_TRIGPRE", "FD2_CALLLOG_TRIGCAP"):
        check(env in CODE, f"CODE reads {env}")
    check("if (trig) trig_step();" in CODE and CODE.index("if (trig) trig_step();") <
          CODE.index("if (SegValue(cs) != game_cs) return;"), "trig_step runs before the game-selector return")
    fi = CODE.index("void fd2calllog_interrupt(")
    check(CODE.index("trig_irq(num, type, oldeip)", fi) < CODE.index("seg_window() < 0) return;", fi),
          "interrupts reach the ring before the SEGS window check")
    for f in fails:
        print("FAIL:", f)
    print("selftest:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1


# --mocktest:CODE 之前補上的替身(DOSBox-X 裡這些由 debug.cpp 的 include 與 CPU 核心提供)
MOCK_PRELUDE = r'''#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cstdarg>
#include <vector>
#include <unistd.h>
typedef uintptr_t Bitu;
typedef uint32_t LinearPt;
#define GCC_UNLIKELY(x) (x)
#define FLAG_IF 0x200u
#define FLAG_VM 0x20000u
static uint32_t reg_flags = FLAG_IF;
#define GETFLAG(f) (reg_flags & FLAG_##f)
struct MockCode { bool big; };
struct MockCpu { bool pmode; MockCode code; };
static MockCpu cpu = { true, { true } };
enum SegNames { es = 0, cs, ss, ds, fs, gs };
static uint16_t mock_seg[6];
static uint16_t SegValue(SegNames s) { return mock_seg[s]; }
static uint32_t SegPhys(SegNames s) { return (uint32_t)mock_seg[s] << 4; }
static uint32_t reg_eip, reg_esp = 0x1000, reg_eax, reg_ebx, reg_ecx, reg_edx, reg_esi, reg_edi, reg_ebp;
static double mock_t = 0;
static double PIC_FullIndex(void) { return mock_t; }
static Bitu PIC_Ticks = 0;
static int32_t CPU_CycleMax = 1000, CPU_CycleLeft = 500, CPU_Cycles = 0;
static uint8_t mock_mem[1 << 21];
static bool mem_readb_checked(LinearPt a, uint8_t *v) {
    if (a >= sizeof(mock_mem)) return true;
    *v = mock_mem[a];
    return false;
}
static bool mem_readd_checked(LinearPt a, uint32_t *v) {
    if (a + 3 >= sizeof(mock_mem)) return true;
    memcpy(v, mock_mem + a, 4);
    return false;
}
static void E_Exit(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    exit(3);
}
'''

# 標準輸入每行一個動作:X m cs eip if = 設好狀態後執行一條指令;I num type = 一次 CPU_Interrupt;T ms = 設時間;
# Q = _exit(0)(不跑 atexit、不清 stdio 緩衝,模擬 harness 砍掉模擬器)
MOCK_MAIN = r'''
int main(void) {
    for (size_t a = 0; a < sizeof(mock_mem); a++) mock_mem[a] = (uint8_t)(a * 7 + 3);
    mock_seg[ss] = 0x10; mock_seg[ds] = 0x10;
    char line[256];
    while (fgets(line, sizeof line, stdin)) {
        char m;
        unsigned sel, eip, iff, num, type;
        double t;
        if (sscanf(line, "X %c %x %x %u", &m, &sel, &eip, &iff) == 4) {
            cpu.pmode = m != 'r';
            cpu.code.big = m == 'P';
            reg_flags = (iff ? FLAG_IF : 0u) | (m == 'v' ? FLAG_VM : 0u);
            mock_seg[cs] = (uint16_t)sel;
            reg_eip = eip;
            CPU_CycleLeft--;
            fd2calllog::step();
        } else if (sscanf(line, "I %x %u", &num, &type) == 2) {
            fd2calllog_interrupt(num, type, reg_eip);
        } else if (sscanf(line, "T %lf", &t) == 1) {
            mock_t = t;
        } else if (line[0] == 'Q') {
            _exit(0);
        }
    }
    return 0;
}
'''


def _mock_build(code: str, work: Path, name: str) -> Path:
    """把 CODE 與替身編成可執行檔。

    Raises:
        RuntimeError: g++ 失敗(附最後的錯誤訊息)。
    """
    src = work / f"{name}.cpp"
    src.write_text(MOCK_PRELUDE + code + MOCK_MAIN, encoding="utf-8", newline="\n")
    exe = work / name
    r = subprocess.run(["g++", "-std=c++11", "-O1", "-o", str(exe), str(src)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"g++ failed for {name}:\n{r.stderr[-3000:]}")
    return exe


def _mock_run(exe: Path, work: Path, env_extra: dict[str, str], script: list[str]) -> tuple[int, str, str]:
    """跑一次替身程式;回傳 (結束碼, 紀錄檔內容, stderr)。"""
    out = work / "out.txt"
    if out.exists():
        out.unlink()
    ent = work / "entries.txt"
    ent.write_text("deadbeef\n", encoding="ascii")
    env = {k: v for k, v in os.environ.items() if not k.startswith("FD2_CALLLOG_")}
    env.update({"FD2_CALLLOG_ENTRIES": str(ent), "FD2_CALLLOG_OUT": str(out)})
    env.update(env_extra)
    r = subprocess.run([str(exe)], input="\n".join(script) + "\n", capture_output=True, text=True, env=env,
                       timeout=300)
    text = out.read_text(encoding="ascii") if out.exists() else ""
    return r.returncode, text, r.stderr


def _xs(n: int, sel: int, e0: int, m: str = "p", iff: int = 1) -> list[str]:
    """n 條連續指令(EIP 從 e0 起每條加 1)。"""
    return [f"X {m} {sel:04x} {e0 + k:x} {iff}" for k in range(n)]


def _game(n: int, e0: int = 0x3E000, iff: int = 1) -> list[str]:
    return _xs(n, 0x170, e0, "P", iff)


def _mem16(lin: int) -> bytes:
    """替身記憶體在 lin 起的 16 個位元組(與 MOCK_MAIN 的填法相同)。"""
    return bytes(((a * 7 + 3) & 0xFF) for a in range(lin, lin + 16))


def mocktest(baseline: Path | None = None) -> int:
    """以 g++ 編譯 CODE 加替身,核對 FD2_CALLLOG_TRIG 的行為;給了 baseline 時另比不設 TRIG 的輸出與舊版逐字相同。

    Args:
        baseline: 舊版 fd2_calllog_patch.py(取它的 CODE);None 時不比。

    Returns:
        0 = 全部通過,1 = 有失敗,2 = 沒有 g++(BLOCKED)。
    """
    import importlib.util
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import calllog_segments as cls

    if subprocess.run(["sh", "-c", "command -v g++"], capture_output=True).returncode != 0:
        print("mocktest: BLOCKED (g++ not found; run under WSL)")
        return 2
    fails: list[str] = []

    def check(cond: bool, what: str) -> None:
        if not cond:
            fails.append(what)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        exe = _mock_build(CODE, work, "cur")

        def run(env: dict[str, str], script: list[str]) -> tuple[int, str, str]:
            return _mock_run(exe, work, env, script)

        def parse(text: str) -> "cls.Log":
            # 紀錄格式壞掉(例如被砍掉時截斷的一行)本身就是失敗,記下來,不讓例外中斷其他項
            try:
                return cls.parse(text.splitlines())
            except ValueError as e:
                fails.append(f"log does not parse: {e}")
                return cls.parse(["H x cs=0170"])

        # 主序列:遊戲 100、非遊戲 375(中間一次中斷)、遊戲 10、非遊戲 374、遊戲 5、非遊戲 376、遊戲 3
        span375 = _xs(200, 0x80, 0x100) + ["T 5.5", "I 08 0"] + _xs(175, 0x80, 0x100 + 200)
        main_seq = (_game(100) + ["T 5.25"] + span375 + ["T 6.25"] + _game(10) + _xs(374, 0x80, 0x100) + _game(5)
                    + _xs(376, 0x80, 0x100) + _game(3))
        # A 對照:不設 TRIG 沒有任何 Y,H 沒有 trig=
        rc, text, err = run({}, main_seq)
        check(rc == 0 and text.startswith("H fd2calllog 1 ") and "trig=" not in text
              and not any(s.startswith("Y") for s in text.splitlines()), f"A: no TRIG -> no Y records ({rc} {err})")
        # B 恰好 375,前文 10
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375", "FD2_CALLLOG_TRIGPRE": "10"}, main_seq)
        lg = parse(text)
        check(rc == 0 and " trig=ng:375 trigring=131072 trigpre=10 trigcap=20" in text.splitlines()[0],
              f"B: H fields ({rc} {err})")
        check(len(lg.trigs) == 1, f"B: one block ({len(lg.trigs)})")
        if lg.trigs:
            t = lg.trigs[0]
            check((t.kind, t.rule, t.count, t.n0, t.n1, t.cs, t.eip, t.trunc, t.t0, t.t1) ==
                  ("ng", 0, 375, 101, 475, 0x80, 0x100, False, 5.25, 6.25), f"B: header {t}")
            check([x.n for x in t.insns] == list(range(91, 477)), "B: YS from n0 - 10 through the closing instruction")
            check(cls.trig_problems(t, lg.game_cs) == [], f"B: parser re-check {cls.trig_problems(t, lg.game_cs)}")
            check([(q.num, q.type, q.n, q.t, q.cs, q.eip) for q in t.irqs] == [(8, 0, 300, 5.5, 0x80, 0x100 + 199)],
                  f"B: YI between n 300 and 301 ({t.irqs})")
            check(t.code.get(("p", 0x80, 0x100)) == _mem16((0x80 << 4) + 0x100)
                  and t.code.get(("P", 0x170, 0x3E000 + 90)) == _mem16((0x170 << 4) + 0x3E000 + 90),
                  "B: c= = memory at the instruction's base + eip")
            check(all(x.iff == 1 for x in t.insns), "B: if=1 throughout")
        check(lg.trig_counts == {0: ("ng", 1, 1)} and lg.trig_spans == {"ng": 3, "if": 0},
              f"B: YC / YN ({lg.trig_counts} {lg.trig_spans})")
        # C 兩條規則:374 只中一次;300- 中三次但 374 那次已由規則 0 寫出 -> 寫 2
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:374,ng:300-", "FD2_CALLLOG_TRIGPRE": "0"}, main_seq)
        lg = parse(text)
        check([(t.rule, t.count) for t in lg.trigs] == [(1, 375), (0, 374), (1, 376)], "C: first matching rule writes")
        check(lg.trig_counts == {0: ("ng", 1, 1), 1: ("ng", 3, 2)}, f"C: matched / written ({lg.trig_counts})")
        check(all(("p", 0x80, 0x100) in t.code for t in lg.trigs), "C: c= repeats in every block (per-block sighting)")
        check(all(sum(1 for x in t.insns if x.eip == 0x100 and x.cs == 0x80) == 1 for t in lg.trigs),
              "C: pre-context 0 -> block starts at the span")
        # D CS:EIP 篩選與上限:@0080:100 中三次寫二次;@0081 一次也不中
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:1-@0080:100,ng:1-@0081", "FD2_CALLLOG_TRIGCAP": "2"}, main_seq)
        lg = parse(text)
        check(lg.trig_counts == {0: ("ng", 3, 2), 1: ("ng", 0, 0)} and len(lg.trigs) == 2,
              f"D: cs:eip filter and cap ({lg.trig_counts})")
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:1-@0080:101"}, main_seq)
        check(parse(text).trig_counts == {0: ("ng", 0, 0)}, "D: control eip filter one off -> no match")
        # E IF 區間:遊戲 selector 裡 IF = 0 的 50 條與 49 條
        if_seq = _game(20) + _game(50, 0x3F000, 0) + _game(5) + _game(49, 0x3F000, 0) + _game(1)
        rc, text, err = run({"FD2_CALLLOG_TRIG": "if:50", "FD2_CALLLOG_TRIGPRE": "3"}, if_seq)
        lg = parse(text)
        check(len(lg.trigs) == 1 and lg.trigs[0].kind == "if" and lg.trigs[0].count == 50
              and (lg.trigs[0].n0, lg.trigs[0].n1) == (21, 70), f"E: if span ({[(t.kind, t.count) for t in lg.trigs]})")
        if lg.trigs:
            t = lg.trigs[0]
            check([x.iff for x in t.insns] == [1] * 3 + [0] * 50 + [1] and cls.trig_problems(t, lg.game_cs) == [],
                  "E: if= per instruction, closing instruction if=1")
        check(lg.trig_spans == {"ng": 0, "if": 2}, f"E: span totals ({lg.trig_spans})")
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:50"}, if_seq)
        check(parse(text).trig_spans == {"ng": 0, "if": 2} and parse(text).trigs == [],
              "E: control ng rule on the same stream -> nothing")
        # F 環形緩衝不夠長 -> trunc=1;對照:夠長時不截
        long_seq = _game(100) + _xs(2000, 0x80, 0x100) + _game(2)
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:2000", "FD2_CALLLOG_TRIGRING": "1024"}, long_seq)
        lg = parse(text)
        check(len(lg.trigs) == 1 and lg.trigs[0].trunc and len(lg.trigs[0].insns) == 1024
              and lg.trigs[0].insns[-1].n == 2101 and cls.trig_problems(lg.trigs[0], lg.game_cs) == [],
              "F: truncated block keeps the newest 1024")
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:2000", "FD2_CALLLOG_TRIGRING": "4096"}, long_seq)
        lg = parse(text)
        check(len(lg.trigs) == 1 and not lg.trigs[0].trunc and len(lg.trigs[0].insns) == 64 + 2000 + 1,
              "F: control ring 4096 -> whole span + default pre 64")
        # 邊界:最舊的一筆正好是前文第一條(n = 1)時不算截斷
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:100"}, _game(64) + _xs(100, 0x80, 0x100) + _game(1))
        lg = parse(text)
        check(len(lg.trigs) == 1 and not lg.trigs[0].trunc and lg.trigs[0].insns[0].n == 1
              and len(lg.trigs[0].insns) == 165, "F: oldest entry exactly at the pre-context start is not trunc")
        # G 閘門:閘門前結束的區間不算(對照:沒有閘門時兩次都算)
        gate_seq = _game(3) + _xs(375, 0x80, 0x100) + _game(10) + _xs(375, 0x80, 0x100) + _game(1)
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375", "FD2_CALLLOG_GATE": "3e005"}, gate_seq)
        lg = parse(text)
        check(lg.trig_counts == {0: ("ng", 1, 1)} and lg.trig_spans["ng"] == 1, f"G: gate ({lg.trig_counts})")
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375"}, gate_seq)
        check(parse(text).trig_counts == {0: ("ng", 2, 2)}, "G: control without gate")
        # H 真實模式 / V86:模式字元與 c= 的基底
        rv_seq = _game(2) + _xs(3, 0xF000, 0x10, "r") + _xs(2, 0x88, 0x20, "v") + _game(1)
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:5"}, rv_seq)
        lg = parse(text)
        check(len(lg.trigs) == 1 and [x.m for x in lg.trigs[0].span()] == ["r"] * 3 + ["v"] * 2
              and lg.trigs[0].code.get(("r", 0xF000, 0x10)) == _mem16(0xF0000 + 0x10), "H: r / v modes and base")
        # K 被砍掉(Q):寫出的區塊與它之後的統計都要在檔案裡;對照:沒有 T exit
        kill_seq = _game(100) + _xs(375, 0x80, 0x100) + _game(3) + ["Q"]
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375"}, kill_seq)
        lg = parse(text)
        check(rc == 0 and "T exit" not in text and len(lg.trigs) == 1 and lg.trigs[0].complete
              and lg.trig_counts == {0: ("ng", 1, 1)} and lg.trig_spans == {"ng": 1, "if": 0},
              f"K: killed after a block keeps the block and its totals ({lg.trig_counts} {lg.trig_spans})")
        # L 時間窗:只算 5 .. 6 ms 結束的區間(對照:窗外那次不算、不寫)
        win_seq = (_game(10) + ["T 4.5"] + _xs(375, 0x80, 0x100) + _game(2) + ["T 5.5"] + _xs(375, 0x80, 0x100)
                   + _game(2) + ["T 6.5"] + _xs(375, 0x80, 0x100) + _game(2))
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375", "FD2_CALLLOG_TRIGT": "5-6"}, win_seq)
        lg = parse(text)
        check(" trigt=5-6" in text.splitlines()[0] and lg.trig_counts == {0: ("ng", 1, 1)}
              and lg.trig_spans["ng"] == 1 and len(lg.trigs) == 1 and lg.trigs[0].t1 == 5.5,
              f"L: TRIGT window ({lg.trig_counts} {lg.trig_spans})")
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375"}, win_seq)
        check(parse(text).trig_counts == {0: ("ng", 3, 3)}, "L: control without TRIGT counts all three")
        for bad in ("5", "6-5", "x-6", "5-6x"):
            rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:375", "FD2_CALLLOG_TRIGT": bad}, _game(1))
            check(rc == 3 and "bad FD2_CALLLOG_TRIGT" in err, f"L: bad TRIGT rejected: {bad!r}")
        # M 沒有區塊時的定期統計:第一個區間結束時一組、之後滿 1000 ms 才再一組;被砍掉後留最後一組
        per_seq = (["T 0"] + _game(2) + _xs(3, 0x80, 0x100) + _game(1) + ["T 500"] + _xs(3, 0x80, 0x100) + _game(1)
                   + ["T 999"] + _xs(3, 0x80, 0x100) + _game(1) + ["T 1000"] + _xs(3, 0x80, 0x100) + _game(1)
                   + ["T 1500"] + _xs(3, 0x80, 0x100) + _game(1) + ["Q"])
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:999"}, per_seq)
        yn = [s for s in text.splitlines() if s.startswith("YN ng")]
        check(yn == ["YN ng 0", "YN ng 3"] and parse(text).trig_counts == {0: ("ng", 0, 0)},
              f"M: periodic totals at the first span end and >= 1000 ms later ({yn})")
        # I 規格錯誤要停(E_Exit);對照:合法的寫法要能跑
        for bad in ("ng:0", "ng:5-3", "xx:5", "ng:5,", "ng:5@zz", "ng:5@10000", "ng:-5", "ng:5@80:zz", "ng:5x",
                    "if:", "ng:5@80:100000000"):
            rc, text, err = run({"FD2_CALLLOG_TRIG": bad}, _game(1))
            check(rc == 3 and "bad FD2_CALLLOG_TRIG" in err, f"I: bad spec rejected: {bad!r} ({rc})")
        for good in ("ng:5@80:100", "if:1-", "ng:1-2,if:3"):
            rc, text, err = run({"FD2_CALLLOG_TRIG": good}, _game(1))
            check(rc == 0 and f" trig={good} " in text, f"I: good spec accepted: {good!r} ({rc} {err})")
        rc, text, err = run({"FD2_CALLLOG_TRIG": "ng:5", "FD2_CALLLOG_TRIGRING": "1023"}, _game(1))
        check(rc == 3 and "TRIGRING" in err, "I: ring below 1024 rejected")
        # J 不設 TRIG 時與舊版逐字相同(SEGS 逐條 / run 窗、ICOUNT、SLICES、GATE、中斷都開)
        if baseline is not None:
            spec = importlib.util.spec_from_file_location("fd2_calllog_patch_baseline", baseline)
            assert spec is not None and spec.loader is not None
            old = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(old)
            old_exe = _mock_build(old.CODE, work, "old")
            env = {"FD2_CALLLOG_SEGS": "0-2:x,2-4", "FD2_CALLLOG_ICOUNT": "1", "FD2_CALLLOG_SLICES": "1",
                   "FD2_CALLLOG_GATE": "3e001"}
            plain = [s for s in main_seq if not s.startswith("T ")]  # 時間只由這裡設,三種窗都要走到
            seq = ["T 1"] + plain[:300] + ["T 3"] + plain[300:900] + ["T 5"] + plain[900:]
            a = _mock_run(exe, work, env, seq)
            b = _mock_run(old_exe, work, env, seq)
            check(a[0] == 0 and a == b and a[1].count("\nS ") > 100 and a[1].count("\nG ") > 3 and "\nI 08" in a[1],
                  "J: TRIG unset -> output identical to the baseline")
            print(f"mocktest: baseline compared ({len(a[1].splitlines())} lines)")
    for f in fails:
        print("FAIL:", f)
    print("mocktest:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1


# --mockmut:CODE 的故障注入(名稱, 原文, 改成);每個都要讓 mocktest 回 1。原文必須在 CODE 裡恰好一處。
MOCK_MUTANTS: list[tuple[str, str, str]] = [
    ("上限比成 >=", "p.count < q.lo || p.count > q.hi", "p.count < q.lo || p.count >= q.hi"),
    ("下限比成 <=", "p.count < q.lo || p.count > q.hi", "p.count <= q.lo || p.count > q.hi"),
    ("IF 區間反了", "const bool in[2] = { c != game_cs, x.iff == 0 };", "const bool in[2] = { c != game_cs, x.iff != 0 };"),
    ("ng 區間反了", "const bool in[2] = { c != game_cs, x.iff == 0 };", "const bool in[2] = { c == game_cs, x.iff == 0 };"),
    ("前文多一條", "p.n0 > tr_pre ? p.n0 - tr_pre : 1;", "p.n0 > tr_pre ? p.n0 - tr_pre - 1 : 1;"),
    ("trunc 用 >=", "left == 0 || tr_ring[i].n > from", "left == 0 || tr_ring[i].n >= from"),
    ("閘門不看", "if (!gate_open || (tr_has_t && !(now >= tr_t0 && now < tr_t1))) return;",
     "if (tr_has_t && !(now >= tr_t0 && now < tr_t1)) return;"),
    ("中斷不進環", "    if (fd2calllog::trig) fd2calllog::trig_irq(num, type, oldeip);\n", ""),
    ("中斷移到窗檢查之後",
     "    if (fd2calllog::trig) fd2calllog::trig_irq(num, type, oldeip);\n    if (!fd2calllog::segs || fd2calllog::seg_window() < 0) return;\n",
     "    if (!fd2calllog::segs || fd2calllog::seg_window() < 0) return;\n    if (fd2calllog::trig) fd2calllog::trig_irq(num, type, oldeip);\n"),
    ("lo 0 不擋", "if (r.lo == 0 || r.hi < r.lo) return false;", "if (r.hi < r.lo) return false;"),
    ("同一區間寫多次", "if (!done && q.written < tr_cap)", "if (q.written < tr_cap)"),
    ("c= 用全域首見", "if (local.insert(key).second) {", "if (first_sighting(x.m, x.cs, x.eip)) {"),
    ("c= 少加 eip", "mem_readb_checked((LinearPt)(x.base + x.eip + k)", "mem_readb_checked((LinearPt)(x.base + k)"),
    ("CS 篩選不看", "if ((q.has_cs && q.cs != p.cs) || (q.has_eip && q.eip != p.eip)) continue;",
     "if (q.has_eip && q.eip != p.eip) continue;"),
    ("EIP 篩選不看", "if ((q.has_cs && q.cs != p.cs) || (q.has_eip && q.eip != p.eip)) continue;",
     "if (q.has_cs && q.cs != p.cs) continue;"),
    ("環大小下限放寬", "if (ring < 1024 || ring > 4194304)", "if (ring < 1000 || ring > 4194304)"),
    ("結尾不寫 YC", "        if (trig) trig_summary();\n", ""),
    ("t1 用 t0", "(double)PIC_FullIndex(), (unsigned)p.cs", "p.t0, (unsigned)p.cs"),
    ("區間第一條取錯", "p.count = 0; p.cs = c; p.eip = e;", "p.count = 0; p.cs = c; p.eip = e + 1;"),
    ("I 的 n 加一", "x.rec = 'I'; x.n = allinstr;", "x.rec = 'I'; x.n = allinstr + 1;"),
    ("trig 在 segs 之前改到 game 判斷之後(漏遊戲指令)", "    if (trig) trig_step();\n    if (SegValue(cs) != game_cs) return;\n",
     "    if (SegValue(cs) != game_cs) return;\n    if (trig) trig_step();\n"),
    ("不設 TRIG 時中斷行為改變", "    if (!fd2calllog::segs || fd2calllog::seg_window() < 0) return;\n",
     "    if (!fd2calllog::segs || fd2calllog::seg_window() < 1) return;\n"),
    ("H 不寫 trigpre", " trig=%s trigring=%llu trigpre=%llu trigcap=%llu", " trig=%s trigring=%llu trigcap=%llu"),
    ("YN 對調", "tr_span[0].spans, tr_span[1].spans);", "tr_span[1].spans, tr_span[0].spans);"),
    ("區塊之後不 flush", "    trig_summary();\n    fflush(out);\n}", "    trig_summary();\n}"),
    ("區塊之後不寫統計", "    fprintf(out, \"YE %llu\\n\", tr_seq);\n    trig_summary();\n", "    fprintf(out, \"YE %llu\\n\", tr_seq);\n"),
    ("定期統計間隔 500", "tr_next_sum = now + 1000.0;", "tr_next_sum = now + 500.0;"),
    ("定期統計不 flush", "{ trig_summary(); fflush(out); tr_next_sum", "{ trig_summary(); tr_next_sum"),
    ("時間窗不看", "if (!gate_open || (tr_has_t && !(now >= tr_t0 && now < tr_t1))) return;", "if (!gate_open) return;"),
    ("時間窗上限含端點", "now >= tr_t0 && now < tr_t1", "now >= tr_t0 && now <= tr_t1 + 1"),
    ("TRIGT 反向不擋", "if (end == b || *end || !(tr_t1 > tr_t0))", "if (end == b || *end)"),
]


def mock_mutants(baseline: Path) -> int:
    """逐一套用 MOCK_MUTANTS 跑 mocktest(含 baseline 比對),每個都必須是 FAIL(回 1),不能 PASS、BLOCKED 或例外。

    Args:
        baseline: 舊版 fd2_calllog_patch.py(J 項要它才抓得到「不設 TRIG 時輸出改變」)。

    Returns:
        0 = 全殺,1 = 有存活 / 例外 / 原文不唯一。
    """
    global CODE
    import contextlib
    import io

    orig = CODE
    survived = 0
    try:
        for name, a, b in MOCK_MUTANTS:
            if orig.count(a) != 1:
                print(f"BAD   {name}: original text found {orig.count(a)} times")
                survived += 1
                continue
            CODE = orig.replace(a, b)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    rc = mocktest(baseline)
                res = "KILLED" if rc == 1 else f"SURVIVED (rc {rc})"
            except Exception as e:  # noqa: BLE001 —— 例外不算殺掉,照實報
                res = f"EXCEPTION {type(e).__name__}: {str(e)[:120]}"
            survived += res != "KILLED"
            first = next((x for x in buf.getvalue().splitlines() if x.startswith("FAIL")), "")
            print(f"{res:10} {name}  {first[:100]}")
    finally:
        CODE = orig
    print(f"mockmut: killed {len(MOCK_MUTANTS) - survived} / {len(MOCK_MUTANTS)}")
    return 0 if survived == 0 else 1


def main(argv: list[str]) -> int:
    """命令列:`fd2_calllog_patch.py [--upgrade] <dosbox-x 樹根>`,或 `--selftest`。"""
    if argv == ["--selftest"]:
        return selftest()
    if argv[:1] == ["--mocktest"]:
        if argv[1:] == []:
            return mocktest()
        if len(argv) == 3 and argv[1] == "--baseline":
            return mocktest(Path(argv[2]))
        print(__doc__)
        return 2
    if argv[:1] == ["--mockmut"]:
        if len(argv) == 3 and argv[1] == "--baseline":
            return mock_mutants(Path(argv[2]))
        print(__doc__)
        return 2
    upgrade = False
    if argv and argv[0] == "--upgrade":
        upgrade = True
        argv = argv[1:]
    if len(argv) != 1:
        print(__doc__)
        return 2
    root = Path(argv[0])
    jobs = [(root / "src" / "debug" / "debug.cpp", lambda s: patch_text(s, upgrade=upgrade)),
            (root / "src" / "cpu" / "cpu.cpp", patch_cpu_text),
            (root / "src" / "hardware" / "pic.cpp", patch_pic_text),
            (root / "src" / "hardware" / "iohandler.cpp", patch_io_text),
            (root / "src" / "hardware" / "keyboard.cpp", patch_kbd_text)]
    srcs = [p.read_text(encoding="utf-8", errors="surrogateescape") for p, _f in jobs]
    try:
        outs = [f(s) for (_p, f), s in zip(jobs, srcs)]  # 全部先算完,任何一檔失敗就一檔都不寫
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1
    for (p, _f), s, o in zip(jobs, srcs, outs):
        if o != s:
            p.write_text(o, encoding="utf-8", errors="surrogateescape", newline="\n")
            print("patched", p)
        else:
            print("unchanged", p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
