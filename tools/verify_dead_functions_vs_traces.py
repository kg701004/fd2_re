#!/usr/bin/env python3
"""以原版實機執行軌跡反驗靜態的「死函式」判定(doc98 續九十六)。

輸入是 `tools/dosbox_exec_trace.sh dedup` 產生的去重 CS:EIP 清單(`trace_unique_cseip.txt`),
每份旁邊要有當次執行的 `FD2.EXE`;只採用 md5 與靜態分析的 EXE 相同的那些。
主程式段 CS 0170 的 EIP 減 0x19c000 換成 native 位址(doc48 / doc58 的慣例)。

能被推翻的主張只有一種:靜態判為「沒有執行路徑」的入口(`function_inventory.json` 的 weak 入口、
`function_names.json` 摘要寫「死函式」的入口)的本體,實機不該執行到。
「每個執行位址都落在某個入口的 span 內」必然成立(span 延伸到下一個入口),不拿來當證據。

用法:
    python tools/verify_dead_functions_vs_traces.py TRACE_ROOT [TRACE_ROOT ...]
        TRACE_ROOT 底下遞迴找 trace_unique_cseip.txt(例:WSL 的 ~ 或匯出的資料夾)。
    python tools/verify_dead_functions_vs_traces.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME_CS = "0170"
DELTA = 0x19C000
OBJ1 = (0x10000, 0x4EF29)


def parse_trace(text: str, cs: str = GAME_CS, delta: int = DELTA) -> set[int]:
    """`CCCC:IIIIIIII` 每行一筆 -> 指定段的 native 位址集合;格式不對的行略過。"""
    out: set[int] = set()
    for ln in text.splitlines():
        seg, sep, ip = ln.strip().partition(":")
        if not sep or seg.upper() != cs:
            continue
        try:
            out.add(int(ip, 16) - delta)
        except ValueError:
            continue
    return out


def body_hits(starts_spans: dict[int, int], live_sorted: list[int]) -> dict[int, list[int]]:
    """{入口: span} 中,本體 [入口, 入口 + span) 內有實機位址的 -> {入口: 命中位址(排序)}。"""
    hits: dict[int, list[int]] = {}
    for a, span in starts_spans.items():
        i = bisect.bisect_left(live_sorted, a)
        j = bisect.bisect_left(live_sorted, a + span)
        if i < j:
            hits[a] = live_sorted[i:j]
    return hits


def load_live(roots: list[Path], want_md5: str) -> tuple[set[int], int, int]:
    """(native 位址集合, 採用份數, 略過份數)。旁邊沒有 FD2.EXE 或 md5 不同的略過。"""
    live: set[int] = set()
    used = skipped = 0
    for root in roots:
        for f in sorted(root.rglob("trace_unique_cseip.txt")):
            exe = f.parent / "FD2.EXE"
            if not exe.is_file() or hashlib.md5(exe.read_bytes()).hexdigest() != want_md5:
                skipped += 1
                continue
            live |= parse_trace(f.read_text(encoding="utf-8", errors="replace"))
            used += 1
    return live, used, skipped


def run(roots: list[Path]) -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    import verify_address_claim_coverage as CC
    want = hashlib.md5(Path(CC.EXE).read_bytes()).hexdigest()
    live, used, skipped = load_live(roots, want)
    if used == 0:
        print(f"找不到 md5 {want} 的軌跡(略過 {skipped} 份);沒有可驗的資料,不是通過。")
        return 2
    live_obj1 = sorted(a for a in live if OBJ1[0] <= a < OBJ1[1])
    inv = json.loads((ROOT / "docs/data/function_inventory.json").read_text(encoding="utf-8"))["entries"]
    names = {n["addr"]: n for n in json.loads((ROOT / "docs/data/function_names.json").read_text(encoding="utf-8"))["names"]}
    span = {int(e["addr"], 16): e["span_upper"] for e in inv}
    weak = {a: s for a, s in span.items() if next(e for e in inv if int(e["addr"], 16) == a)["grade"] == "weak"}
    dead = {a: s for a, s in span.items() if "死函式" in names.get(hex(a), {}).get("summary", "")}
    print(f"軌跡 {used} 份(md5 {want[:8]}…,略過 {skipped} 份);obj1 內不重複執行位址 {len(live_obj1)}")
    bad = 0
    for label, group in (("weak 入口", weak), ("摘要寫「死函式」的入口", dead)):
        hits = body_hits(group, live_obj1)
        print(f"{label}:{len(group)} 個,本體(整個 span)有實機位址的 {len(hits)} 個")
        for a, h in sorted(hits.items()):
            print(f"   {a:#x} {names.get(hex(a), {}).get('name', '-')}:{len(h)} 個位址,例 {[hex(x) for x in h[:4]]}")
        bad += len(hits)
    entry_hit = sum(1 for a in span if a in live)
    print(f"入口位址本身出現在軌跡裡:{entry_hit} / {len(span)}(只是過去擷取場景的下限)")
    # 有命中不自動判錯:span 尾端可能是與活路徑共用的片段(0x46915 的 int N 樁表),要人讀命中位址
    return 1 if bad else 0


def selftest() -> int:
    fails: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
        if not ok:
            fails.append(label)

    text = "0170:001AC010\n0170:001AC012\n0070:00001234\nbad line\n0170:zzzz\n0170:001E26CB\n"
    check("parse_trace:只取 0170、減 0x19c000、略過壞行", parse_trace(text), {0x10010, 0x10012, 0x466CB})
    check("parse_trace:換段", parse_trace(text, cs="0070", delta=0), {0x1234})
    live = sorted({0x10010, 0x10012, 0x10100, 0x20000})
    check("body_hits:span 內命中、span 邊界不含終點、沒命中不列",
          body_hits({0x10010: 0x10, 0x100F0: 0x11, 0x1FFF0: 0x10, 0x30000: 0x100}, live),
          {0x10010: [0x10010, 0x10012], 0x100F0: [0x10100]})
    check("body_hits:空軌跡", body_hits({0x10010: 0x10}, []), {})
    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        return 1
    print("\n--selftest passed(4 項純函式案例)。")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="以原版實機執行軌跡反驗靜態的死函式判定")
    ap.add_argument("roots", nargs="*", type=Path, help="遞迴找 trace_unique_cseip.txt 的根目錄")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.roots:
        ap.error("需要至少一個 TRACE_ROOT")
    return run(a.roots)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
