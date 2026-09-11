#!/usr/bin/env python3
"""fd2_re - re-derive the project's headline numeric findings, with strict criteria.

Why this exists
---------------
2026-09-08: re-checking the day's conclusions by hand produced one false
mismatch. The handler table at `0x524c6` was reported as 11 entries instead of
10 because the ad-hoc script asked *"is this dword inside the code address
range?"* — and the dword after the table is `0x00010000`, which is **exactly the
lower bound**. Neither the tools nor the original conclusion had drifted; a
throwaway criterion was weaker than the reasoning it replaced.

Two things follow, and this file is both of them:

1. **The criterion belongs in code, once.** `is_function_entry()` answers "is
   this address a real function?" by membership in the set of Watcom stack-check
   prologues (`push N; call 0x3702f`) recovered from the whole image — not by an
   address-range test. Every pointer-table question in this repo should use it.
2. **Re-derivation should be repeatable.** Each finding below carries the number
   that was recorded and the code that re-derives it, so "are the conclusions
   still true?" is one command rather than a fresh script each time — and a
   fresh script is what went wrong.

Where a second, independent implementation exists it is used as a cross-check
rather than trusting one code path twice: `tools/image_ref_scan.py` (its own
selftest fault-injects the rel32 arithmetic, and cross-checks Ghidra's xref
database) is run against the same targets, and disagreement is a failure.

Usage
-----
    python tools/verify_findings.py
    python tools/verify_findings.py --cross-check      # 也跑獨立實作比對(較慢)
    python tools/verify_findings.py --selftest
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
STACK_CHECK = 0x3702F
SEGMENTS = ((0x10000, 0x4E000), (0x50000, 0x55000), (0x60000, 0x63000))

_segs: list[tuple[int, bytes]] | None = None
_entries: frozenset[int] | None = None


def segments() -> list[tuple[int, bytes]]:
    global _segs
    if _segs is None:
        import capstone_probe as c
        out = []
        for lo, hi in SEGMENTS:
            try:
                out.append((lo, bytes(c.fetch_bytes(lo, hi - lo, quiet=True))))
            except Exception as exc:                      # noqa: BLE001
                print(f"  (區段 {lo:#x} 讀取失敗,略過: {str(exc)[:60]})")
        _segs = out
    return _segs


def function_entries() -> frozenset[int]:
    """Every Watcom function entry in the image.

    A function opens with `push <frame>; call 0x3702f`, so the entry is the
    address of that call minus 5. This set — not an address range — is what
    "is this a function?" means in this codebase.
    """
    global _entries
    if _entries is None:
        ent = set()
        for lo, d in segments():
            for i in range(len(d) - 5):
                if d[i] != 0xE8:
                    continue
                rel = int.from_bytes(d[i + 1:i + 5], "little", signed=True)
                if lo + i + 5 + rel == STACK_CHECK:
                    ent.add(lo + i - 5)
        _entries = frozenset(ent)
    return _entries


def is_function_entry(addr: int) -> bool:
    """The strict criterion. `0x00010000` fails this and an address-range test
    does not — that difference is the entire reason this module exists."""
    return addr in function_entries()


def call_sites(target: int) -> list[int]:
    out = []
    for lo, d in segments():
        for i in range(len(d) - 5):
            if d[i] != 0xE8:
                continue
            rel = int.from_bytes(d[i + 1:i + 5], "little", signed=True)
            if lo + i + 5 + rel == target:
                out.append(lo + i)
    return out


def read(addr: int, n: int) -> bytes:
    for lo, d in segments():
        if lo <= addr and addr + n <= lo + len(d):
            return bytes(d[addr - lo:addr - lo + n])
    import capstone_probe as c
    return bytes(c.fetch_bytes(addr, n, quiet=True))


def is_tail_merged_stub(addr: int) -> bool:
    """`push <frame> ; jmp <某個真入口的 __STK 呼叫>` —— 編譯器把數個**內容相同**的
    函式尾段合併之後留下的 7/10-byte 殘樁。

    2026-09-11 加入。它與 `is_function_entry` 是兩件事,**不可合併**:後者的計數
    (541)是已登記的結論 `584-entries`。但對**跳表**而言殘樁同樣是合法的 handler
    入口——`0x51b91` 的 index 5/34/86..89 與 `0x51d01` 的 43/46..48 都是這種,
    先前 `pointer_table_len` 會在第一個殘樁就當成「表結束」,把 90 格的表報成 5 格。
    """
    # 先擋邊界:跳表結尾之後的 dword 是任意垃圾值(例如 0x13140101),若直接丟給
    # `read()` 會落到 Ghidra 後端去抓一段不存在的記憶體,錯誤訊息看起來像工具壞了。
    if not any(lo <= addr and addr + 12 <= lo + len(d) for lo, d in segments()):
        return False
    b = read(addr, 12)
    if b[0] != 0x68:
        return False
    if b[5] == 0xEB:
        tgt = addr + 7 + struct.unpack_from("<b", b, 6)[0]
    elif b[5] == 0xE9:
        tgt = addr + 10 + struct.unpack_from("<i", b, 6)[0]
    else:
        return False
    return is_function_entry(tgt - 5)        # 跳到某個真入口的 `call __STK`


def is_handler_entry(addr: int) -> bool:
    """跳表槽位該用的判準:真入口**或**共用尾段的殘樁。"""
    return is_function_entry(addr) or is_tail_merged_stub(addr)


def pointer_table_len(base: int, probe: int = 24, predicate=is_function_entry) -> int:
    """How many leading dwords at `base` satisfy `predicate`.

    Stops at the first one that does not, which is what a jump table's end looks
    like. 預設仍是嚴格的 `is_function_entry`(`0x524c6` 的 10 因此不變);含共用
    尾段殘樁的跳表要傳 `is_handler_entry`。
    """
    raw = read(base, 4 * probe)
    n = 0
    for i in range(probe):
        if not predicate(struct.unpack_from("<I", raw, i * 4)[0]):
            break
        n += 1
    return n


def _names() -> list[str]:
    from decode_story_text import gm
    from decode_text import parse_strings
    GM = gm()
    ss = parse_strings(str(ROOT / "extracted/raw/FDTXT/FDTXT_000.bin"))
    return ["".join(GM.get(c, "?") for c in s if c < 0xFF00) for s in ss]


def _growth(portrait: int) -> list[int]:
    raw = read(0x620A1, 11 * (portrait + 1))
    return [raw[portrait * 11 + o] for o in (1, 3, 5, 7, 9)]


# id, 說明, 記錄值, 重新推導
FINDINGS = [
    ("848-join-sites", "call 0x112a5 的呼叫端數", 28, lambda: len(call_sites(0x112A5))),
    ("1069-callers", "call 0x1c4cc 的呼叫端數", 16, lambda: len(call_sites(0x1C4CC))),
    ("584-ff01-callers", "FUN_0002ff01 的呼叫端數", 2, lambda: len(call_sites(0x2FF01))),
    ("584-entries", "全 image 的 Watcom 函式入口數", 541, lambda: len(function_entries())),
    ("584-handler-table", "0x524c6 攻擊法術 handler 數(嚴格判準)", 10,
     lambda: pointer_table_len(0x524C6)),
    ("584-spell-table", "0x51d01 法術 handler 表前 12 筆皆為函式", 12,
     lambda: pointer_table_len(0x51D01, probe=12)),
    # 2026-09-11(doc25 §20):上面那筆的 `probe=12` 是呼叫端設的上限,不是表的結尾。
    # 兩張表的**完整**格數改由下面兩筆涵蓋,判準用 `is_handler_entry`(含共用尾段殘樁)。
    # 這正是 `findings` 軸每輪報「15/15 相符」卻沒能擋下 doc25 §10 那個 0x356 偏移的原因:
    # 表本身從來沒有整張被登記過。
    ("212-event-table", "0x51b91 全域事件跳表格數(含共用尾段殘樁)", 90,
     lambda: pointer_table_len(0x51B91, probe=120, predicate=is_handler_entry)),
    ("212-command-table", "0x51d01 指令/法術跳表格數(含共用尾段殘樁)", 88,
     lambda: pointer_table_len(0x51D01, probe=120, predicate=is_handler_entry)),
    ("248-class-151", "FDTXT_000[151] = 劍士", "劍士", lambda: _names()[151]),
    ("248-class-159", "class 9 + 0x96 -> 劍聖", "劍聖", lambda: _names()[159]),
    ("248-class-count", "職業名區段 151..178 非空數", 28,
     lambda: sum(1 for i in range(151, 179) if _names()[i])),
    ("248-char-15", "角色名表 id 15(名稱表寫法)", "塞可邦勒", lambda: _names()[16]),
    ("406-bonus-3e", "portrait 0x3e 的 bonus 上限(AP,DP,DX,HP,MP)", [15, 9, 6, 18, 0],
     lambda: _growth(0x3E)),
    ("406-growth-all", "32 個基礎 portrait 皆有非零成長", 32,
     lambda: sum(1 for p in range(32) if sum(read(0x620A1 + p * 11, 11)[o] for o in (0, 2, 4, 6, 8)) > 0)),
]

CROSS = [("848-join-sites", 0x112A5, 28), ("1069-callers", 0x1C4CC, 16),
         ("584-ff01-callers", 0x2FF01, 2)]


def evaluate(findings) -> list[tuple[str, str, bool, object, object]]:
    """Re-derive each finding and compare. `main()` and `selftest()` both go
    through here, so the comparison itself is under test -- mutation scoring
    showed the verdict logic was invisible to the selftest when `main()` had
    its own inline `got == want`."""
    rows = []
    for fid, label, want, fn in findings:
        try:
            got = fn()
        except Exception as exc:                          # noqa: BLE001
            rows.append((fid, label, False, want, f"ERROR: {str(exc)[:50]}"))
            continue
        rows.append((fid, label, got == want, want, got))
    return rows


def cross_check(timeout: int = 900) -> list[tuple[str, bool, str]]:
    """Independent implementation, so a shared bug cannot pass as agreement."""
    out = []
    for fid, target, want in CROSS:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "image_ref_scan.py"),
                            "--target", hex(target), "--kinds", "call"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=timeout)
        got = None
        for line in (r.stdout or "").splitlines():
            if line.strip().startswith("call:"):
                try:
                    got = int(line.split(":")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        out.append((fid, got == want, f"image_ref_scan={got} 記錄={want}"))
    return out


def selftest() -> int:
    fails = []
    print("(1) 嚴格判準必須拒絕 0x00010000(那次假不符的元兇),並接受真正的入口")
    bad_ok = not is_function_entry(0x00010000)
    good_ok = is_function_entry(0x2B996)
    print(f"    {'PASS' if bad_ok else 'FAIL'}: 0x00010000 判為函式入口={not bad_ok}(應為 False)")
    print(f"    {'PASS' if good_ok else 'FAIL'}: 0x2b996 判為函式入口={good_ok}(應為 True)")
    if not bad_ok:
        fails.append("弱判準的元兇仍被當成函式入口")
    if not good_ok:
        fails.append("真正的函式入口被拒絕")

    print("\n(2) 對照:改用「位址範圍」這個弱判準,同一張表必須算出 11 —— 證明差別真的來自判準")
    raw = read(0x524C6, 4 * 12)
    loose = 0
    for i in range(12):
        v = struct.unpack_from("<I", raw, i * 4)[0]
        if 0x10000 <= v < 0x40000:
            loose += 1
        else:
            break
    strict = pointer_table_len(0x524C6)
    ok2 = loose == 11 and strict == 10
    print(f"    {'PASS' if ok2 else 'FAIL'}: 弱判準={loose}(應為 11) 嚴格判準={strict}(應為 10)")
    if not ok2:
        fails.append(f"判準對照不成立 loose={loose} strict={strict}")

    print("\n(3) 故障注入:把 stack-check 位址改掉,入口集合必須崩掉")
    global _entries
    keep = _entries
    _entries = None
    try:
        import builtins  # noqa: F401
        orig = globals()["STACK_CHECK"]
        globals()["STACK_CHECK"] = orig + 0x10
        _entries = None
        n = len(function_entries())
        ok3 = n < 50
        print(f"    {'PASS' if ok3 else 'FAIL'}: 注入後入口數={n}(應遠少於 541)")
        if not ok3:
            fails.append("故障注入後入口集合幾乎不變——該判準不是載重的")
    finally:
        globals()["STACK_CHECK"] = orig
        _entries = keep

    print("\n(4) 配對控制:同一個 evaluate() 必須讓正確的記錄值相符、刻意寫錯的不符")
    paired = [("good", "正確的記錄值", 28, lambda: len(call_sites(0x112A5))),
              ("bad", "刻意錯的記錄值", 999, lambda: len(call_sites(0x112A5)))]
    rows = evaluate(paired)
    got_good = next(r for r in rows if r[0] == "good")
    got_bad = next(r for r in rows if r[0] == "bad")
    ok4 = got_good[2] and not got_bad[2]
    print(f"    {'PASS' if ok4 else 'FAIL'}: good 相符={got_good[2]}(應 True) "
          f"bad 相符={got_bad[2]}(應 False)")
    if not ok4:
        fails.append("evaluate() 的判定邏輯不正確——單邊通過不算,必須一對一錯")

    print("\n(5) evaluate() 遇到會拋例外的推導必須判為不符,而不是靜默略過")
    boom = evaluate([("boom", "必炸", 1, lambda: 1 // 0)])
    ok5 = (not boom[0][2]) and str(boom[0][4]).startswith("ERROR")
    print(f"    {'PASS' if ok5 else 'FAIL'}: 判定={boom[0][2]}(應 False) 內容={str(boom[0][4])[:40]}")
    if not ok5:
        fails.append("推導拋例外時沒有被判為不符")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(嚴格/弱判準對照 + 故障注入 + 配對控制 + 例外處理)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cross-check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    ok = bad = 0
    for fid, label, good, want, got in evaluate(FINDINGS):
        ok += good
        bad += not good
        print(f"  {'相符' if good else '**不符**'} {fid:<20} {label:<40} "
              f"記錄={want} 重測={got}")
    if a.cross_check:
        print("\n獨立實作交叉比對(image_ref_scan.py):")
        for fid, good, detail in cross_check():
            ok += good
            bad += not good
            print(f"  {'相符' if good else '**不符**'} {fid:<20} {detail}")
    print(f"\n共 {ok + bad} 項:相符 {ok} / 不符 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
