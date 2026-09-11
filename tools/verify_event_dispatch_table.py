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

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(獨立路徑真值重現 + 32 格全為入口 + 嚴格遞增 + "
          "doc25 偏移的負向控制 + 兩張表全格判定 + 分界控制)。")
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
