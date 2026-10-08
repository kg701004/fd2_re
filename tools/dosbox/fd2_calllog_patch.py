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
"""
from __future__ import annotations

import sys
from pathlib import Path

ANCHOR = "bool DEBUG_HeavyIsBreakpoint(void) {\n"
HOOK = "\tfd2calllog::step();\n"

CODE = r'''/* ---- fd2_re: function call log (local patch, not upstream; tools/dosbox/fd2_calllog_patch.py) ----
 * Enabled only when env FD2_CALLLOG_ENTRIES names a file of hex EIPs (whitespace separated).
 * For a listed EIP executed in code selector FD2_CALLLOG_CS (hex, default 0170), the first
 * FD2_CALLLOG_CAP (default 200) hits per entry write an E record:
 *   E seq eip ret[?] esp ss eax ebx ecx edx esi edi ebp s=<8 dwords above ret> c=<16 code bytes>
 *     m=<FD2_CALLLOG_DUMP bytes (default 32, max 256) at DS:value for eax,edx,ebx,ecx,esi,edi,s1..s4>
 *   ("?" after ret = [esp] unreadable; "??" = unreadable byte).
 * R seq entry eax edx esp: control reached the return address ([esp] at entry) with a higher esp
 *   on the same stack.  A seq entry eip esp: the frame was left by a higher esp at another EIP.
 * Every hit is counted; "T tag n" + "C eip count" (changed counts) are written every 2^26
 * game-selector instructions and at exit.  Output: FD2_CALLLOG_OUT (default CALLLOG.TXT).
 */
namespace fd2calllog {
struct Frame { uint32_t ret, esp, entry; uint16_t ss; unsigned long long seq; };
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
    if (enabled && out) { dump_counts("exit"); fclose(out); out = NULL; enabled = false; }
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
    fprintf(out, "H fd2calllog 1 cs=%04x entries=%u cap=%llu dump=%u lo=%08x hi=%08x\n",
            (unsigned)game_cs, (unsigned)addrs.size(), cap, (unsigned)dumplen, (unsigned)lo, (unsigned)hi);
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
    if (SegValue(cs) != game_cs) return;
    ginstr++;
    const uint32_t eip = reg_eip, esp = reg_esp;
    const uint16_t ssv = SegValue(ss);
    while (!frames.empty()) {
        Frame &t = frames.back();
        if (t.ss != ssv || esp <= t.esp) break;
        if (eip == t.ret)
            fprintf(out, "R %llu %08x %08x %08x %08x\n", t.seq, (unsigned)t.entry,
                    (unsigned)reg_eax, (unsigned)reg_edx, (unsigned)esp);
        else
            fprintf(out, "A %llu %08x %08x %08x\n", t.seq, (unsigned)t.entry, (unsigned)eip, (unsigned)esp);
        frames.pop_back();
    }
    if (eip >= lo && eip < hi && isentry[eip - lo]) {
        const size_t i = eip - lo;
        calls[i]++;
        if (logged[i] < cap) {
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

'''


def patch_text(src: str) -> str:
    """回傳插入呼叫紀錄後的 debug.cpp 內容。

    Args:
        src: 原始 debug.cpp 內容。

    Returns:
        修補後內容。

    Raises:
        ValueError: 已修補過,或錨點(`DEBUG_HeavyIsBreakpoint` 定義)不是恰好一處。
    """
    if "fd2calllog" in src:
        raise ValueError("already patched")
    if src.count(ANCHOR) != 1:
        raise ValueError(f"anchor found {src.count(ANCHOR)} times, expected 1")
    return src.replace(ANCHOR, CODE + ANCHOR + HOOK, 1)


def main(argv: list[str]) -> int:
    """命令列:`fd2_calllog_patch.py <dosbox-x 樹根>`。"""
    if len(argv) != 1:
        print(__doc__)
        return 2
    p = Path(argv[0]) / "src" / "debug" / "debug.cpp"
    src = p.read_text(encoding="utf-8", errors="surrogateescape")
    try:
        out = patch_text(src)
    except ValueError as e:
        print(f"FAIL: {p}: {e}")
        return 1
    p.write_text(out, encoding="utf-8", errors="surrogateescape", newline="\n")
    print("patched", p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
