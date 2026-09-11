#!/usr/bin/env python3
"""fd2_re — 全域事件跳表 `0x51b91` 的 58..89 槽位:逐格證明它們都是乾淨的函式入口。

為什麼需要這支
--------------
doc25 §10(2026-08-20)為 58..89 建了一張「event_id → handler 入口位址」表,後續各輪
據此把其中 14 格判為「table artifact,無獨立語意」(`58/64/68/70/71/76/77/78/81/85/86/87/88/89`)。
2026-09-07 那輪推翻了其中 3 格(58/76/78),並誠實記下「其餘 11 格未逐一重驗,
既然判定方法本身在這 3 格上都失效,應視為**存疑待重驗**」。

本輪把 32 格全部重驗,結論是**一格 artifact 都沒有**,而且原因是單一的系統性錯誤:
**doc25 記的位址欄是 LE 檔案裡的未重定位值,比實際入口一律低 `0x356`**。跳表存的
dword 是相對 obj1 的位移,真正的入口是 `stored + 0x10000`;doc25 的欄位少了這一步,
於是有些格「剛好」重新同步到某條指令邊界(看起來像乾淨 handler)、有些落在指令中段
(被判成 artifact)。artifact 這個分類本身就是那個 `0x356` 偏移的產物。

判定方法:純位元組樣式,不做線性反組譯
------------------------------------
本專案已經被「線性反組譯失去對齊」咬過多次,而且 doc25 這個錯誤正是用反組譯邊界
推論造成的。所以本工具**完全不反組譯**,只比對 Watcom 的兩種固定序頭位元組樣式:

  CLEAN_PROLOGUE     68 <imm32> E8 <rel32>     push imm32 ; call __STK(0x3702f)
  TAIL_MERGED_STUB   68 <imm32> EB <rel8>      push imm32 ; jmp -> 某個 CLEAN_PROLOGUE 的 call

`call`/`jmp` 的目標都實際算出來核對,不是只看 opcode。任何其他形狀一律 `MID_BODY`,
即「這個位址不是函式起點」。這樣連 capstone 都不需要,也就不可能有對齊問題。

用法:
    python tools/verify_event_dispatch_table.py --exe <FD2.EXE>
    python tools/verify_event_dispatch_table.py --exe <FD2.EXE> --json docs/data/event_dispatch_table_58_89.json
    python tools/verify_event_dispatch_table.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from le_xref import parse_le                                     # noqa: E402
from disasm_le import object_bytes, load_code                    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"

TABLE_BASE = 0x51B91        # doc25 §11.7 定出的跳表基底,本工具以真值檢查間接複驗
FIRST_INDEX, LAST_INDEX = 58, 89

# 2026-09-11 續:追 `0x25089`/`0x361b0` 的呼叫端時發現這一帶其實有**兩張**表。
#   A `0x51b91` 90 格(0..89)   —— 全域事件,dispatch 見 `0x1d890` 等 8 處
#   兩個 dword 變數 `0x51cf9`/`0x51cfd` —— **不是表格**,是游標 x/y 備份
#                                    (寫入端 `0x1be07`/`0x1be11`,各 5 個程式端參照)
#   B `0x51d01` 88 格(0..87)   —— 指令/行動,只有 2 個 dispatch 點:
#                                  `0x1541f`(AI 路徑)與 `0x1d479`(玩家 command ring),
#                                  兩者都是 `call [eax*4+0x51d01]` 且都接 `call 0x1d4f6`
TABLES = {
    "event":   (0x51B91, 90),
    "command": (0x51D01, 88),
}
# 兩張表之間那兩格:必須**通不過**序頭判定,否則「兩張表」的分界就是我畫出來的而非資料決定的。
BETWEEN_TABLES = (0x51CF9, 0x51CFD)
CODE_BASE = 0x10000         # 跳表存的是相對 obj1 的位移
STACK_PROBE = 0x3702F       # Watcom __STK;每個 handler 序頭都先呼叫它
DOC25_SHIFT = 0x356         # doc25 §10 位址欄的系統性偏差(未重定位值)

PUSH_IMM32 = 0x68
CALL_REL32 = 0xE8
JMP_REL8 = 0xEB
JMP_REL32 = 0xE9

# 2026-09-07 那輪以完全獨立的路徑(讀 raw 檔案 + 四錨點校準 relocation)定出的三個入口,
# 本工具必須用另一條路徑(讀已重定位的 image + CODE_BASE)重現同樣的值。
GROUND_TRUTH = {58: 0x35854, 76: 0x360B6, 78: 0x36228}


def read_table(data: bytes, meta: dict, base: int = TABLE_BASE,
               first: int = FIRST_INDEX, count: int | None = None) -> dict[int, int]:
    """{index: 重定位後的 handler 入口}。"""
    n = count if count is not None else LAST_INDEX - FIRST_INDEX + 1
    raw = object_bytes(data, meta, base + first * 4, n * 4)
    return {first + i: int.from_bytes(raw[i * 4:i * 4 + 4], "little") + CODE_BASE
            for i in range(n)}


def read_slot(data: bytes, meta: dict, addr: int) -> int:
    """單一 dword 槽位的重定位後值(供分界的負向控制用)。"""
    return int.from_bytes(object_bytes(data, meta, addr, 4), "little") + CODE_BASE


def classify(code: bytes, code_base: int, addr: int) -> tuple[str, str]:
    """(判定, 說明)。判定 ∈ CLEAN_PROLOGUE / TAIL_MERGED_STUB / MID_BODY。"""
    off = addr - code_base
    if off < 0 or off + 10 > len(code):
        return "MID_BODY", "位址落在 code object 之外"
    if code[off] != PUSH_IMM32:
        return "MID_BODY", f"起始位元組 {code[off]:#04x} 不是 push imm32"
    imm = int.from_bytes(code[off + 1:off + 5], "little")
    op = code[off + 5]
    if op == CALL_REL32:
        rel = int.from_bytes(code[off + 6:off + 10], "little", signed=True)
        tgt = addr + 10 + rel
        if tgt == STACK_PROBE:
            return "CLEAN_PROLOGUE", f"push {imm:#x} ; call __STK({STACK_PROBE:#x})"
        return "MID_BODY", f"push {imm:#x} 之後的 call 指向 {tgt:#x},不是 __STK"
    if op in (JMP_REL8, JMP_REL32):
        if op == JMP_REL8:
            rel = int.from_bytes(code[off + 6:off + 7], "little", signed=True)
            tgt = addr + 7 + rel
        else:
            rel = int.from_bytes(code[off + 6:off + 10], "little", signed=True)
            tgt = addr + 10 + rel
        # 跳到的地方必須就是某個 CLEAN_PROLOGUE 的 `call __STK`,否則不算共用尾段。
        t = tgt - code_base
        # 2026-09-11:突變測試把開頭的 0 改成 1 逃掉了。查過是可證明的等價突變:
        # 這個下界只在 t∈[-5,-1] 時與 `1<=t+5` 給出不同的布林值,而掃過整個範圍
        # 實測 —— 對這五個 t 值,不論在 wraparound 命中的位置放什麼陷阱位元組,
        # `classify()` 都回傳 MID_BODY,原因是下一行 `code[t+1:t+5]` 這個 slice
        # 對負的 t 不會像單一索引那樣做 wraparound(`code[-4:0]` 這類切片在
        # start>stop 時直接是空切片),導致 r2 算不出配對值。上界(t+5<=len(code))
        # 才是真正承重的那一半,已由 selftest (9) 釘住。
        if 0 <= t + 5 <= len(code) and code[t] == CALL_REL32:
            r2 = int.from_bytes(code[t + 1:t + 5], "little", signed=True)
            if tgt + 5 + r2 == STACK_PROBE:
                return "TAIL_MERGED_STUB", f"push {imm:#x} ; jmp {tgt:#x}(共用 __STK 尾段)"
        return "MID_BODY", f"push {imm:#x} 之後的 jmp 指向 {tgt:#x},不是共用的 __STK 尾段"
    return "MID_BODY", f"push {imm:#x} 之後是 {op:#04x},不是 call/jmp"


def analyse(exe: str | Path, shift: int = 0) -> dict[int, dict]:
    """shift 用於負向控制:套上 doc25 的 0x356 偏移後,判定必須塌掉。"""
    data = Path(exe).read_bytes()
    meta = parse_le(data)
    code, code_base = load_code(data, meta)
    out = {}
    for ev, addr in read_table(data, meta).items():
        a = addr - shift
        verdict, why = classify(code, code_base, a)
        out[ev] = {"entry": a, "verdict": verdict, "detail": why}
    return out


def build(exe: str | Path) -> dict:
    res = analyse(exe)
    entries = [r["entry"] for _, r in sorted(res.items())]
    counts: dict[str, int] = {}
    for r in res.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {
        "_source": "fd2_re — 全域事件跳表 0x51b91 的 58..89 槽位逐格判定。",
        "_generator": "tools/verify_event_dispatch_table.py",
        "_method": "純位元組序頭樣式(push imm32 + call __STK / + jmp 共用尾段),不做線性反組譯。",
        "_table_base": hex(TABLE_BASE),
        "_code_base": hex(CODE_BASE),
        "_note": ("doc25 §10 的位址欄是未重定位值,一律比實際入口低 0x356;"
                  "先前的「14 個 table artifact」全部是該偏移造成的假象。"),
        "_monotonic": all(entries[i] < entries[i + 1] for i in range(len(entries) - 1)),
        "_verdict_counts": counts,
        "slots": {str(ev): {"entry": hex(r["entry"]), "verdict": r["verdict"],
                            "detail": r["detail"],
                            "doc25_recorded": hex(r["entry"] - DOC25_SHIFT)}
                  for ev, r in sorted(res.items())},
        "tables": all_tables(exe),
    }


def all_tables(exe: str | Path) -> dict:
    """兩張表的全表判定,外加中間那兩個 dword 的分界控制。"""
    data = Path(exe).read_bytes()
    meta = parse_le(data)
    code, code_base = load_code(data, meta)
    out = {}
    for name, (base, count) in TABLES.items():
        rows = {}
        for idx, addr in read_table(data, meta, base, 0, count).items():
            v, why = classify(code, code_base, addr)
            rows[str(idx)] = {"entry": hex(addr), "verdict": v, "detail": why}
        out[name] = {
            "base": hex(base), "count": count,
            "all_entries": all(r["verdict"] != "MID_BODY" for r in rows.values()),
            "slots": rows,
        }
    out["between_tables"] = {
        hex(a): classify(code, code_base, read_slot(data, meta, a))[1]
        for a in BETWEEN_TABLES
    }
    return out


def selftest() -> int:
    fails = []
    exe = DEFAULT_EXE
    if not exe.exists():
        print(f"SKIP:找不到 {exe}(本檢查需要原版 EXE)")
        return 0

    res = analyse(exe)

    print("(1) 三個由**完全獨立路徑**定出的入口必須被重現")
    # 2026-09-07 那輪讀 raw 檔案 + 四錨點校準;本工具讀已重定位 image + CODE_BASE。
    wrong = {ev: (hex(want), hex(res[ev]["entry"])) for ev, want in GROUND_TRUTH.items()
             if res[ev]["entry"] != want}
    ok1 = not wrong
    print(f"    {'PASS' if ok1 else 'FAIL'}: 真值 {len(GROUND_TRUTH)} 筆;不符 {wrong or '無'}")
    if not ok1:
        fails.append(f"真值對不上:{wrong}")

    print("\n(2) 32 格全部必須是函式起點 —— 一格 MID_BODY 都不該有")
    bad = {ev: r["detail"] for ev, r in res.items() if r["verdict"] == "MID_BODY"}
    ok2 = len(res) == LAST_INDEX - FIRST_INDEX + 1 and not bad
    print(f"    {'PASS' if ok2 else 'FAIL'}: {len(res)} 格;MID_BODY {bad or '無'}")
    if not ok2:
        fails.append(f"仍有非入口的槽位:{bad}")

    print("\n(3) 入口位址必須嚴格遞增(跳表與函式佈局同序)")
    ent = [r["entry"] for _, r in sorted(res.items())]
    ok3 = all(ent[i] < ent[i + 1] for i in range(len(ent) - 1))
    print(f"    {'PASS' if ok3 else 'FAIL'}: {hex(ent[0])} .. {hex(ent[-1])}")
    if not ok3:
        fails.append("入口位址非嚴格遞增")

    print(f"\n(4) 負向控制:套上 doc25 的 {DOC25_SHIFT:#x} 偏移後,判定必須塌掉")
    # 沒有這一項,(2) 會是平凡的——一個永遠回傳 CLEAN 的分類器也能通過 (2)。
    shifted = analyse(exe, shift=DOC25_SHIFT)
    n_mid = sum(1 for r in shifted.values() if r["verdict"] == "MID_BODY")
    ok4 = n_mid >= len(shifted) - 1        # 允許至多 1 格巧合重新同步
    print(f"    {'PASS' if ok4 else 'FAIL'}: 偏移後 {n_mid}/{len(shifted)} 格判為 MID_BODY")
    if not ok4:
        fails.append(f"偏移後仍有 {len(shifted) - n_mid} 格被判為入口,分類器缺乏鑑別力")

    print("\n(5) 兩張表(0x51b91 90 格 / 0x51d01 88 格)必須每一格都是入口")
    tb = all_tables(exe)
    bad5 = {k: [i for i, r in tb[k]["slots"].items() if r["verdict"] == "MID_BODY"]
            for k in TABLES if not tb[k]["all_entries"]}
    ok5 = not bad5
    print(f"    {'PASS' if ok5 else 'FAIL'}: "
          + " / ".join(f"{k} {tb[k]['count']} 格" for k in TABLES)
          + f";非入口 {bad5 or '無'}")
    if not ok5:
        fails.append(f"表內有非入口的槽位:{bad5}")

    print("\n(6) 分界控制:兩張表之間的 0x51cf9/0x51cfd 必須**通不過**入口判定")
    # 沒有這一項,「這是兩張表」就是我畫的界線而不是資料決定的——把它們併成一張
    # 178 格的大表也不會有任何檢查失敗。實際上那兩格是游標 x/y 備份變數
    # (寫入端 0x1be07/0x1be11,各有 5 個程式端參照)。
    ok6 = all(("不是 push imm32" in why) or ("不在程式段" in why)
              for why in tb["between_tables"].values())
    print(f"    {'PASS' if ok6 else 'FAIL'}: {tb['between_tables']}")
    if not ok6:
        fails.append("分界的兩個 dword 也被判成入口,兩張表的界線因此沒有依據")

    print("\n(7) 與 `verify_findings` 的判準必須逐格一致(兩套獨立實作,不是兩份複本)")
    # 為什麼不是直接 import 它的 `is_function_entry`:那條路徑的位元組來源是
    # `capstone_probe.fetch_bytes`,走 Ghidra headless(要 JVM,且在 WSL 下不可用),
    # 而本工具刻意保持「只讀 EXE、免 capstone/免 JVM」,才能待在 verify_everything 的
    # wsl 軸裡。所以改成**斷言兩套實作一致**——這比只留一份更強,也正是
    # `verify_findings` 自己對 `image_ref_scan.py` 用的做法(「不要讓同一條程式碼被信兩次」)。
    # 兩者的位元組來源不同(原始檔 + 0x10000 vs Ghidra 的已重定位映像),所以這是真的交叉核對。
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import verify_findings as VF
        VF.segments()                       # WSL 無 capstone 時在這裡就會拋
    except Exception as exc:                # noqa: BLE001
        print(f"    SKIP:取不到 verify_findings 的位元組來源({str(exc)[:50]})")
    else:
        tb = all_tables(exe)
        disagree = []
        for name in TABLES:
            for idx, row in tb[name]["slots"].items():
                mine = row["verdict"] != "MID_BODY"
                theirs = VF.is_handler_entry(int(row["entry"], 16))
                if mine != theirs:
                    disagree.append(f"{name}[{idx}] {row['entry']} 本工具={mine} VF={theirs}")
        ok7 = not disagree
        print(f"    {'PASS' if ok7 else 'FAIL'}: 逐格比對 "
              f"{sum(t['count'] for t in (tb[k] for k in TABLES))} 格;分歧 {disagree[:3] or '無'}")
        if not ok7:
            fails.append(f"兩套判準分歧(代表其中一套漂移了):{disagree[:3]}")

    print("\n(8) 合成案例:**往回呼叫**的序頭也必須判成入口(真實資料到不了這條路徑)")
    # 2026-09-11,突變測試發現的缺口:把 L105 的 `signed=True` 改成 `False`,七題全過。
    # 原因不是檢查太鬆,是**真實資料碰不到**——本映像所有 handler(0x35854..0x3644e)
    # 都在 stack probe `0x3702f` **之前**,所以每一個 rel32 都是正數,有號/無號無差別。
    # 但 `signed=True` 在一般情況下是對的且必要的:任何位於 probe 之後的入口,rel 為負,
    # 無號解讀會得到 +2^32 的垃圾目標而被誤判成 MID_BODY。所以這裡自己造一段程式碼,
    # 讓入口落在 probe **之後**,把那條路徑逼出來。
    base = CODE_BASE
    probe_off = STACK_PROBE - base
    synth = bytearray(probe_off + 0x100)
    fwd = base + 0x20                                  # probe 之前:rel 為正
    back = STACK_PROBE + 0x40                           # probe 之後:rel 為負
    for entry in (fwd, back):
        o = entry - base
        synth[o] = PUSH_IMM32
        synth[o + 1:o + 5] = (0x1234).to_bytes(4, "little")
        synth[o + 5] = CALL_REL32
        synth[o + 6:o + 10] = (STACK_PROBE - (entry + 10)).to_bytes(4, "little", signed=True)
    v_fwd = classify(bytes(synth), base, fwd)[0]
    v_back = classify(bytes(synth), base, back)[0]
    rel_back = int.from_bytes(synth[back - base + 6:back - base + 10], "little", signed=True)
    ok8 = v_fwd == "CLEAN_PROLOGUE" and v_back == "CLEAN_PROLOGUE" and rel_back < 0
    print(f"    {'PASS' if ok8 else 'FAIL'}: 往前呼叫({fwd:#x})={v_fwd}、"
          f"往回呼叫({back:#x},rel={rel_back})={v_back}")
    if rel_back >= 0:
        fails.append("合成的『往回呼叫』rel 不是負數 —— 這題沒有測到有號解讀")
    elif not ok8:
        fails.append(f"往回呼叫的序頭被誤判:{v_back}(有號/無號解讀出錯)")

    print("\n(9) TAIL_MERGED_STUB 的越界防呆必須**恰好貼齊** len(code),不能多容忍 1 byte")
    # 突變測試發現:`0 <= t + 5 <= len(code)` 的 `5` 改成 `6` 逃掉。真實跳表格從不
    # 落在 code object 最尾端,所以邊界從沒被真的踩過。合成一段程式碼,讓 jmp
    # 目標恰好落在 code 陣列的最後 5 個 byte(合法、應判成 TAIL_MERGED_STUB)與
    # 再往後 1 byte(不合法,code[t+1:t+5] 會讀出陣列外,應判成 MID_BODY)。
    tail_len = 20
    tail_code_base = 0

    def make_tail(t: int) -> bytes:
        buf = bytearray(tail_len)
        buf[0] = PUSH_IMM32
        buf[1:5] = (0x1234).to_bytes(4, "little")
        buf[5] = JMP_REL32
        tgt = t                                     # tail_code_base = 0,故 tgt == t
        rel = tgt - 10
        buf[6:10] = rel.to_bytes(4, "little", signed=True)
        if 0 <= t and t + 5 <= tail_len:
            buf[t] = CALL_REL32
            r2 = STACK_PROBE - (tgt + 5)
            buf[t + 1:t + 5] = r2.to_bytes(4, "little", signed=True)
        return bytes(buf)

    v_ok = classify(make_tail(tail_len - 5), tail_code_base, 0)[0]     # t+5 == len(code),應通過
    v_over = classify(make_tail(tail_len - 4), tail_code_base, 0)[0]   # t+5 == len(code)+1,應拒絕
    ok9 = v_ok == "TAIL_MERGED_STUB" and v_over == "MID_BODY"
    print(f"    {'PASS' if ok9 else 'FAIL'}: 恰好貼齊 len(code) -> {v_ok}(應 TAIL_MERGED_STUB)、"
          f"多 1 byte -> {v_over}(應 MID_BODY)")
    if not ok9:
        fails.append(f"TAIL_MERGED_STUB 的越界邊界不對:{v_ok}/{v_over}")

    print("\n(10) 序頭恰好剩 10 bytes 的邊界 + 共用尾段往回呼叫 __STK(r2 為負)")
    # 2026-09-11 窮舉突變測試:`off + 10 > len(code)` 的 10 改 11 逃掉(真實跳表格
    # 從不落在 code 最尾端);共用尾段那個 call 的 `signed=True` 改 False 也逃掉 ——
    # 真實 handler 全在 stack probe 之前,r2 永遠為正。這裡把 code 放在 probe **之後**,
    # 逼出負的 r2,並斷言它真的是負的(否則這題會安靜地退化成正數情況)。
    base10 = 0x20000
    clean10 = bytearray(10)
    clean10[0], clean10[5] = PUSH_IMM32, CALL_REL32
    clean10[6:10] = (STACK_PROBE - (base10 + 10)).to_bytes(4, "little", signed=True)
    after = STACK_PROBE + 0x100                    # 位於 probe 之後
    tail10 = bytearray(20)
    t10 = 12
    tail10[0], tail10[5] = PUSH_IMM32, JMP_REL8
    tail10[6] = t10 - 7                            # addr + 7 + rel8 == after + t10
    r2_10 = STACK_PROBE - (after + t10 + 5)
    tail10[t10] = CALL_REL32
    tail10[t10 + 1:t10 + 5] = r2_10.to_bytes(4, "little", signed=True)
    v10a = classify(bytes(clean10), base10, base10)[0]
    v10b = classify(bytes(tail10), after, after)[0]
    ok10 = v10a == "CLEAN_PROLOGUE" and r2_10 < 0 and v10b == "TAIL_MERGED_STUB"
    print(f"    {'PASS' if ok10 else 'FAIL'}: 恰好 10 bytes 的序頭 -> {v10a}(應 CLEAN_PROLOGUE)、"
          f"probe 之後的共用尾段(r2={r2_10},前提 <0)-> {v10b}(應 TAIL_MERGED_STUB)")
    if not ok10:
        fails.append(f"序頭尾端邊界或尾段的有號位移不對:{v10a}/{v10b}/r2={r2_10}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(獨立路徑真值重現 + 32 格全為入口 + 嚴格遞增 + "
          "doc25 偏移的負向控制 + 兩張表全格判定 + 分界控制 + 與 verify_findings 的逐格一致 + "
          "往回呼叫的合成案例 + TAIL_MERGED_STUB 越界邊界)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    data = build(a.exe)
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if a.json:
        Path(a.json).write_text(text, encoding="utf-8")
        print(f"-> {a.json}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
