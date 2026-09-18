#!/usr/bin/env python3
"""function_inventory.py —— 程式碼層的分母:FD2.EXE obj1 裡每一個函式入口的機械事實卡。

為什麼有這支
------------
2026-09-18 量「程式碼層解析了多少」時發現,一直被當成分母的 Ghidra「976 個函式」兩個方向都錯:
226 個是 `.image::` 位址空間的 1-byte 空白佔位(真函式 750),而有 Watcom 序頭或被直接 CALL、
卻落在任何 Ghidra 函式之外的入口有 317 個(其中 101 個知識庫早就主張為入口)。AIL 的 105 個
進入點也只有 44 個是 Ghidra 起點。所以函式清單的骨架必須由**位元組訊號**建立,Ghidra 只能是
拿來對照的來源之一(`--ghidra-export`),不能當骨架。

入口判準(全部沿用兄弟工具,不另立一套)
----------------------------------------
* `prologue`      Watcom `push imm32 ; call __STK`(`verify_address_claim_coverage.prologue_entries`,541 個)
* `call`          直接 `E8 rel32` 的目標(`derive_native_argcounts._scan` 的位元組掃描,附呼叫端位址)
* `ail`           `docs/data/ail_entry_points.json` 的 105 個進入點(多半經指標表呼叫,沒有直接 CALL)
* `thunk_target`  某個入口的第一個位元組是 `E9`,它跳去的位址(`delay` 的本體 `0x3e01d` 只能這樣抵達)

`grade`:有 prologue / ail / thunk_target,或被 CALL 兩次以上 = `strong`;只被 CALL 一次 = `weak`
(E8 位元組掃描會接受資料位元組的偶然命中,單一命中不足以當函式)。

每個入口的機械事實:`callers`(直接呼叫端數)、`span_upper`(到下一個入口的距離,是大小的**上界**)、
`argc`(`derive_native_argcounts.callee_argc`:本體讀到第幾個參數,判不出來為 null)、
`callees`(本體範圍內直接 CALL 的目標,不含 `__STK`)、`globals`(本體範圍內的 fixup 指向 obj1 之外的位址)。

產物與覆蓋率分開
----------------
`docs/data/function_inventory.json` **只含由 EXE 算得出的東西**(加 AIL 表,它本身也是 EXE 導出的產物),
所以可以逐位元組重生比對。「有沒有名字/文件有沒有記載」會隨文件與命名表變動,不進產物,
由 `--coverage` 現算:名稱來源是 PRIM(`dump_chapter_beats`、`event_handler_dump`)、`DOC_OP_NAMES`、
AIL、`verified_addresses.json`、勘誤的 `correct_address`;「文件記載為入口」取
`verify_address_claim_coverage.classify_all()` 的有訊號集合。

結構性自動命名(`--structural`)
------------------------------
有些函式不需要人讀:本體的**結構**就是它的描述。只用本清單的機械事實加上**有真名**的命名表
(PRIM、`DOC_OP_NAMES`、AIL;`verified_addresses`/勘誤只有位址沒有名稱字串,不算)。依序判定,先中先贏:
  * `thunk`         入口即 `jmp`:`thunk->目標`
  * `ail_only`      所有直接呼叫端都是 AIL 進入點或已判定的 ail_only(不動點;自己呼叫自己不算呼叫端)。
                    名稱只說工具能證明的事:它可能是 AIL 的內部輔助(實測 `0x364d4`/`0x364fb` 是配置後鎖定、
                    解鎖後釋放的記憶體輔助),也可能是只有 AIL 用到的 CRT 函式 —— 兩者都可以從遊戲邏輯的待辦扣掉。
  * `wrapper`       有被呼叫者、全部已知、`span_upper` <= 256。已知 = 有真名,或前幾輪已被結構性命名(以 `~0x位址`
                    表示)。逐輪傳播到不動點,`round` 記第幾輪。本體反組譯得出來、且本體裡的直接 CALL 目標與清單的
                    callees 完全一致時,依**呼叫順序**列出每次呼叫與參數:`wrapper(load_res(0x1c8, _, 3), redraw())`
                    —— 參數取 CALL 前最近的 N 個 push(N = 被呼叫者的 `argc`),立即值照寫、非立即值 `_`、
                    push 不夠 `?`、`argc` 不明 `(?)`。不一致或反組譯不出來就退回 `wrapper(a, b)`(依位址排序)。
  * `leaf_*`        沒有直接被呼叫者、`span_upper` <= 64,且本體反組譯到乾淨的結尾、裡面**沒有任何 call 或間接 jmp**
                    (清單的 callees 只有直接 CALL,`call [ptr]` 要靠反組譯才看得到)。依本體的記憶體存取分:
                    `leaf_global`  有帶 fixup 的指令(碰全域):`leaf_get[0x…]` / `leaf_set` / `leaf_rw` / `leaf_ref`
                                   (只取位址);括號裡有暫存器加 `_idx`(查表);另外還經指標存取加 `+ptr`
                    `leaf_ptr`     只經暫存器指標存取(多半是參數指標):`leaf_ptr_get` / `_set` / `_rw`
                    `leaf_pure`    完全不碰記憶體(堆疊除外)
只對 `strong` 且沒有真名的入口命名。這些是**描述不是語意**:`wrapper(load_res)` 說的是「它只呼叫 load_res」,
不是「它載入什麼」。產物 `docs/data/function_structural_names.json` 的每一筆都標 `kind`,不得當成 verified 引用。

誠實邊界
--------
* 只經跳表/函式指標抵達、又沒有 Watcom 序頭的函式看不到(fixup 目標大多是函式內的 case 標籤,
  單獨不當入口訊號)。`--ghidra-export` 會列出「Ghidra 有、這裡沒有」的起點供人工判斷。
* `span_upper` 以下一個入口為界,中間若夾資料表或漏掉的函式,會高估。
* `callees`/`globals` 以 `span_upper` 歸屬,因此繼承同樣的高估。

用法
----
    python tools/function_inventory.py docs/data/function_inventory.json   # 重生產物
    python tools/function_inventory.py --coverage                           # 命名/記載覆蓋率
    python tools/function_inventory.py --unnamed [--limit N]                # 無名的 strong 入口,依呼叫端數排序
    python tools/function_inventory.py --structural docs/data/function_structural_names.json
    python tools/function_inventory.py --ghidra-export PATH                 # 與 Ghidra 匯出對照
    python tools/function_inventory.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
import types
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

AIL_JSON = ROOT / "docs" / "data" / "ail_entry_points.json"
VERIFIED_JSON = ROOT / "docs" / "data" / "verified_addresses.json"
ERRATA_JSON = ROOT / "docs" / "data" / "known_address_errata.json"
JMP_REL32 = 0xE9
STRONG_CALLERS = 2          # 只被 CALL 一次的位址可能是資料位元組的偶然命中
WRAPPER_MAX_SPAN = 256      # 再大就不是「只是包裝」,本體有自己的邏輯
LEAF_MAX_SPAN = 64
HEX = re.compile(r"0x[0-9a-fA-F]{4,6}")
GHIDRA_HEADER = re.compile(r"^FUNCTION \d+/\d+: \S+ @ (\S+?)\s+size=(\d+)\s*$", re.M)


# --------------------------------------------------------------------------- #
# 純函式核心(selftest 直接餵合成位元組,不需要 EXE 或 capstone)
# --------------------------------------------------------------------------- #
def entry_thunks(entries: set[int], code: bytes, base: int, hi: int) -> dict[int, int]:
    """{thunk 入口: 跳去的位址}:入口的第一個位元組是 `E9 rel32`,且目標落在 [base, hi)。"""
    out: dict[int, int] = {}
    for a in entries:
        off = a - base
        if off < 0 or off + 5 > len(code) or code[off] != JMP_REL32:
            continue
        t = a + 5 + int.from_bytes(code[off + 1:off + 5], "little", signed=True)
        if base <= t < hi:
            out[a] = t
    return out


def thunk_targets(entries: set[int], code: bytes, base: int, hi: int) -> dict[int, int]:
    """{跳去的位址: thunk 入口};多個 thunk 指向同一目標時記位址最小的那個。"""
    out: dict[int, int] = {}
    for a, t in sorted(entry_thunks(entries, code, base, hi).items()):
        out.setdefault(t, a)
    return out


def direct_callers(entries: list[dict]) -> dict[int, set[int]]:
    """由各入口的 callees 反推 {被呼叫者: 呼叫它的入口};自己呼叫自己不算。"""
    out: dict[int, set[int]] = {}
    for e in entries:
        a = int(e["addr"], 16)
        for t in e["callees"]:
            if int(t, 16) != a:
                out.setdefault(int(t, 16), set()).add(a)
    return out


def closed_under_callers(entries: list[dict], seeds: set[int]) -> set[int]:
    """所有直接呼叫端都在集合內的入口,逐輪加入到不動點;回傳**新加入**的(不含 seeds)。沒有呼叫端的不算。"""
    callers = direct_callers(entries)
    inside = set(seeds)
    while True:
        new = {a for a, cs in callers.items() if a not in inside and cs <= inside}
        if not new:
            return inside - set(seeds)
        inside |= new


MEM = re.compile(r"\[([^\]]*)\]")
STACK_BASED = re.compile(r"\b(?:esp|ebp)\b")
ANY_REG = re.compile(r"\b(?:e?[abcd]x|e?[sd]i|[abcd][lh])\b")
IMMEDIATE = re.compile(r"^-?(?:0x[0-9a-f]+|\d+)$")
NO_ACCESS = {"lea", "nop"}


def body_insns(insn_at, start: int, limit: int) -> list[tuple[int, int, str, str]] | None:
    """從 start 線性解碼到函式結尾,回傳 [(位址, 長度, 助記符, 運算元)];解不出乾淨的結尾回 None。

    `insn_at(addr) -> (長度, 助記符, 運算元) | None`。結尾 = `ret*` 或無條件 `jmp`,且在它之前沒有任何
    往前跳、目標落在它之後(仍在 limit 內)的分支 —— 那表示後面還有本體。走到 limit 還沒結尾就是 None。
    """
    out = []
    a = far = start
    while a < limit:
        got = insn_at(a)
        if got is None:
            return None
        size, mn, op = got
        out.append((a, size, mn, op))
        if mn.startswith("j") and op.startswith("0x") and a < int(op, 16) < limit:
            far = max(far, int(op, 16))
        if (mn.startswith("ret") or mn == "jmp") and far <= a:
            return out
        a += size
    return None


def call_args(insns: list[tuple[int, int, str, str]], argc: dict[int, int | None],
              skip: frozenset[int] = frozenset()) -> list[tuple[int, list[str] | None]]:
    """本體裡每個直接 CALL(依出現順序)與它的參數:[(目標, 參數 | None)]。None = 被呼叫者的 argc 不明。

    cdecl 由右至左 push,所以 CALL 前最後一個 push 是第 1 個參數。分支與 CALL 之後 push 清空。
    `skip` 裡的目標(`__STK`)不列出 —— 清單的 callees 也不含它 —— 但它前面那個 `push <frame>` 照樣被它吃掉。
    """
    out: list[tuple[int, list[str] | None]] = []
    pushed: list[str] = []
    for _, _, mn, op in insns:
        if mn == "push":
            pushed.append(op if IMMEDIATE.match(op) else "_")
        elif mn == "call":
            if op.startswith("0x") and int(op, 16) not in skip:
                n = argc.get(int(op, 16))
                got = None if n is None else (pushed[::-1][:n] + ["?"] * n)[:n]
                out.append((int(op, 16), got))
            pushed = []
        elif mn.startswith("j") or mn.startswith("ret"):
            pushed = []
    return out


def leaf_kind(insns: list[tuple[int, int, str, str]], fixups: dict[int, int], base: int, hi: int) -> dict | None:
    """無直接被呼叫者的小函式依本體分類;本體裡有任何 call 或間接 jmp 就不是 leaf(回 None)。"""
    globals_: set[int] = set()
    modes: set[str] = set()
    ptr: set[str] = set()
    indexed = False
    for a, size, mn, op in insns:
        if mn == "call" or (mn == "jmp" and not op.startswith("0x")):
            return None
        here = {fixups[x] for x in range(a, a + size) if x in fixups and not base <= fixups[x] < hi}
        globals_ |= here
        first, _, rest = op.partition(",")
        access = set()
        if mn not in NO_ACCESS:
            if "[" in first and mn == "mov":
                access.add("set")
            elif "[" in first:
                access |= {"get", "set"} if mn not in ("cmp", "test", "push") else {"get"}
            if "[" in rest:
                access.add("get")
        mems = [m for m in MEM.findall(op) if not STACK_BASED.search(m)]
        if here:
            modes |= access or {"ref"}
            indexed = indexed or any(ANY_REG.search(m) for m in mems)
        elif mems and access:
            ptr |= access
    def mode(ms: set[str]) -> str:
        return "rw" if {"get", "set"} <= ms else "get" if "get" in ms else "set" if "set" in ms else "ref"
    if globals_:
        name = f"leaf_{mode(modes)}{'_idx' if indexed else ''}[{', '.join(hex(g) for g in sorted(globals_))}]" + ("+ptr" if ptr else "")
        return {"kind": "leaf_global", "name": name}
    if ptr:
        return {"kind": "leaf_ptr", "name": f"leaf_ptr_{mode(ptr)}"}
    return {"kind": "leaf_pure", "name": "leaf_pure"}


def structural(entries: list[dict], names: dict[int, str], thunks: dict[int, int], ail: set[int],
               bodies: dict[int, list | None] | None = None, fixups: dict[int, int] | None = None,
               base: int = 0, hi: int = 0, skip: frozenset[int] = frozenset()) -> dict[int, dict]:
    """{入口: {"kind", "name", "round"}}。判定順序與各 kind 的定義見模組 docstring。

    `bodies` = {入口: body_insns 的結果};不給(沒有反組譯器)就只出 thunk / ail_only / 不帶參數的 wrapper。
    """
    todo = {int(e["addr"], 16): e for e in entries if e["grade"] == "strong" and int(e["addr"], 16) not in names}
    argc = {int(e["addr"], 16): e["argc"] for e in entries}
    out: dict[int, dict] = {}
    for a in sorted(todo):
        if a in thunks:
            out[a] = {"kind": "thunk", "name": f"thunk->{names.get(thunks[a], hex(thunks[a]))}", "round": 0}
    for a in sorted(closed_under_callers(entries, ail)):
        if a in todo and a not in out:
            out[a] = {"kind": "ail_only", "name": "ail_only", "round": 0}
    label = dict(names)
    rnd = 0
    while True:
        rnd += 1
        new = {}
        for a, e in sorted(todo.items()):
            cs = [int(t, 16) for t in e["callees"]]
            if a in out or not cs or e["span_upper"] > WRAPPER_MAX_SPAN or not all(t in label for t in cs):
                continue
            calls = call_args(bodies[a], argc, skip) if bodies and bodies.get(a) else []
            if {t for t, _ in calls} == set(cs):
                inner = ", ".join(f"{label[t]}({'?' if args is None else ', '.join(args)})" for t, args in calls)
            else:
                inner = ", ".join(label[t] for t in cs)
            new[a] = {"kind": "wrapper", "name": f"wrapper({inner})", "round": rnd}
        if not new:
            break
        out.update(new)
        label.update({a: f"~{a:#x}" for a in new})
    for a, e in sorted(todo.items()):
        if a in out or e["callees"] or e["span_upper"] > LEAF_MAX_SPAN or not bodies or not bodies.get(a):
            continue
        got = leaf_kind(bodies[a], fixups or {}, base, hi)
        if got:
            out[a] = {**got, "round": 0}
    return out


def structural_doc(entries: list[dict], named: dict[int, dict]) -> dict:
    by = {int(e["addr"], 16): e for e in entries}
    kinds = ("thunk", "ail_only", "wrapper", "leaf_global", "leaf_ptr", "leaf_pure")
    return {"_meta": {"generator": "tools/function_inventory.py --structural",
                      "caution": "結構性描述,不是語意;不得當成 verified 引用",
                      "total": len(named), "by_kind": {k: sum(1 for v in named.values() if v["kind"] == k) for k in kinds},
                      "wrapper_rounds": max([v["round"] for v in named.values()] or [0])},
            "names": {hex(a): {**v, "callers": by[a]["callers"], "argc": by[a]["argc"]} for a, v in sorted(named.items())}}


def entry_signals(prologue: set[int], callers: dict[int, int], ail: set[int],
                  thunks: dict[int, int]) -> dict[int, list[str]]:
    """{入口: 訊號名稱(固定順序)}。"""
    out: dict[int, list[str]] = {}
    for name, members in (("prologue", prologue), ("call", set(callers)), ("ail", ail),
                          ("thunk_target", set(thunks))):
        for a in members:
            out.setdefault(a, []).append(name)
    return out


def grade(signals: list[str], n_callers: int) -> str:
    if any(s != "call" for s in signals) or n_callers >= STRONG_CALLERS:
        return "strong"
    return "weak"


def spans(addrs: list[int], hi: int) -> dict[int, int]:
    """{入口: 到下一個入口(最後一個到 hi)的距離}。`addrs` 須已排序。"""
    return {a: (addrs[i + 1] if i + 1 < len(addrs) else hi) - a for i, a in enumerate(addrs)}


def owner(addrs: list[int], addr: int) -> int | None:
    """`addr` 所屬的入口(小於等於它的最大入口);在第一個入口之前回 None。"""
    i = bisect.bisect_right(addrs, addr) - 1
    return addrs[i] if i >= 0 else None


def callees_by_owner(addrs: list[int], call_index: dict[int, tuple[int, ...]],
                     skip: set[int]) -> dict[int, list[int]]:
    """{入口: 本體範圍內直接 CALL 的目標(去重、排序、不含 skip)}。"""
    out: dict[int, set[int]] = {}
    for target, sites in call_index.items():
        if target in skip:
            continue
        for site in sites:
            o = owner(addrs, site)
            if o is not None:
                out.setdefault(o, set()).add(target)
    return {o: sorted(ts) for o, ts in out.items()}


def globals_by_owner(addrs: list[int], fixups: dict[int, int], base: int, hi: int) -> dict[int, list[int]]:
    """{入口: 本體範圍內的 fixup 指向 obj1 之外([base, hi) 之外)的位址}。來源不在 obj1 的 fixup 不算。"""
    out: dict[int, set[int]] = {}
    for src, tgt in fixups.items():
        if not base <= src < hi or base <= tgt < hi:
            continue
        o = owner(addrs, src)
        if o is not None:
            out.setdefault(o, set()).add(tgt)
    return {o: sorted(ts) for o, ts in out.items()}


def assemble(prologue: set[int], call_index: dict[int, tuple[int, ...]], ail: set[int], code: bytes,
             base: int, hi: int, fixups: dict[int, int], stack_probe: int,
             argc_of=None) -> dict:
    """由各訊號組出整份清單。`argc_of(addr) -> int | None`;不給就全部 null。"""
    callers = {t: len(s) for t, s in call_index.items() if base <= t < hi and t != stack_probe}
    seeds = set(prologue) | set(callers) | set(ail)
    thunks = thunk_targets(seeds, code, base, hi)
    sig = entry_signals(set(prologue), callers, set(ail), thunks)
    addrs = sorted(sig)
    span = spans(addrs, hi)
    callee = callees_by_owner(addrs, call_index, {stack_probe})
    glob = globals_by_owner(addrs, fixups, base, hi)
    entries = []
    for a in addrs:
        n = callers.get(a, 0)
        entries.append({
            "addr": hex(a), "signals": sig[a], "callers": n, "grade": grade(sig[a], n),
            "span_upper": span[a], "argc": argc_of(a) if argc_of else None,
            "callees": [hex(t) for t in callee.get(a, [])],
            "globals": [hex(t) for t in glob.get(a, [])],
        })
    strong = sum(1 for e in entries if e["grade"] == "strong")
    return {"_meta": {"generator": "tools/function_inventory.py", "image_range": [hex(base), hex(hi)],
                      "entries": len(entries), "strong": strong, "weak": len(entries) - strong,
                      "by_signal": {k: sum(1 for e in entries if k in e["signals"])
                                    for k in ("prologue", "call", "ail", "thunk_target")},
                      "argc_available": argc_of is not None},
            "entries": entries}


def tier(addr: int, names: dict[int, dict], documented: set[int]) -> str:
    """覆蓋率分層:命名表有 = named;否則文件記載為入口 = documented;否則 unnamed。"""
    if addr in names:
        return "named"
    return "documented" if addr in documented else "unnamed"


def coverage_counts(entries: list[dict], names: dict[int, dict], documented: set[int],
                    strong_only: bool) -> dict[str, int]:
    out = {"total": 0, "named": 0, "documented": 0, "unnamed": 0}
    for e in entries:
        if strong_only and e["grade"] != "strong":
            continue
        out["total"] += 1
        out[tier(int(e["addr"], 16), names, documented)] += 1
    return out


def parse_ghidra(text: str) -> tuple[dict[int, int], int]:
    """Ghidra 匯出的函式標頭 -> ({起點: size}, 佔位數)。位址帶位址空間前綴(`.image::`)的是佔位。"""
    real: dict[int, int] = {}
    placeholders = 0
    for where, size in GHIDRA_HEADER.findall(text):
        if "::" in where:
            placeholders += 1
        else:
            real[int(where, 16)] = int(size)
    return real, placeholders


def compare_ghidra(entries: list[dict], real: dict[int, int]) -> dict:
    """本清單 vs Ghidra 真函式:共有 / 只有 Ghidra / 只有本清單(再分落在某個 Ghidra 函式內或空隙)。"""
    mine = {int(e["addr"], 16): e for e in entries}
    starts = sorted(real)
    inside, gap = [], []
    for a in sorted(set(mine) - set(real)):
        o = owner(starts, a)
        (inside if o is not None and a < o + real[o] else gap).append(a)
    return {"both": len(set(mine) & set(real)), "ghidra_only": sorted(set(real) - set(mine)),
            "mine_inside_ghidra_fn": inside, "mine_in_gap": gap,
            "gap_strong": [a for a in gap if mine[a]["grade"] == "strong"]}


# --------------------------------------------------------------------------- #
# 讀真實輸入
# --------------------------------------------------------------------------- #
def load_ail() -> dict[int, str]:
    data = json.loads(AIL_JSON.read_text(encoding="utf-8"))
    return {int(k, 16): v for k, v in data["entry_points"].items()}


def build(with_argc: bool = True) -> dict:
    import disasm_le as D
    import derive_native_argcounts as DNA
    import verify_address_claim_coverage as CC
    data, meta, code, base, hi = CC.load_image()
    prologue = CC.prologue_entries(code, base)
    call_index, _ = DNA._scan(types.SimpleNamespace(code=code, base=base))
    fixups = D.build_fixups(data, meta)
    argc_of = None
    if with_argc:
        try:
            from callgraph_le import CG
            cg = CG(CC.EXE)
            ents = frozenset(prologue)
            argc_of = lambda a: DNA.callee_argc(cg, a, ents)[0]   # noqa: E731
        except ImportError:
            argc_of = None
    return assemble(prologue, call_index, set(load_ail()), code, base, hi, fixups, CC.STACK_PROBE, argc_of)


def load_names() -> dict[int, dict]:
    """{位址: {"name": 第一個可用名稱或 None, "sources": [...]}}。"""
    import dump_chapter_beats as DCB
    import event_handler_dump as EHD
    import derive_native_argcounts as DNA
    out: dict[int, dict] = {}

    def add(addr: int, source: str, name: str | None) -> None:
        slot = out.setdefault(addr, {"name": None, "sources": []})
        slot["sources"].append(source)
        if slot["name"] is None and name:
            slot["name"] = name

    for a, v in DCB.PRIM.items():
        add(a, "PRIM(chapter_beats)", v[0])
    for a, v in EHD.PRIM.items():
        add(a, "PRIM(event_handler)", v)
    for a, v in DNA.DOC_OP_NAMES.items():
        add(a, "DOC_OP_NAMES", v[0])
    for a, v in load_ail().items():
        add(a, "AIL", v)
    for e in json.loads(VERIFIED_JSON.read_text(encoding="utf-8"))["entries"]:
        for h in HEX.findall(str(e.get("address", ""))):
            add(int(h, 16), "verified_addresses", None)
    for e in json.loads(ERRATA_JSON.read_text(encoding="utf-8"))["errata"]:
        for h in HEX.findall(str(e.get("correct_address", ""))):
            add(int(h, 16), "errata.correct", None)
    return out


def real_names() -> dict[int, str]:
    """只收有名稱字串的來源(PRIM、DOC_OP_NAMES、AIL)。"""
    return {a: v["name"] for a, v in load_names().items() if v["name"]}


def build_structural() -> dict:
    import disasm_le as D
    import verify_address_claim_coverage as CC
    inv = build(with_argc=True)
    data, meta, code, base, hi = CC.load_image()
    ents = {int(e["addr"], 16) for e in inv["entries"]}
    bodies = None
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        md = Cs(CS_ARCH_X86, CS_MODE_32)

        def insn_at(a: int):
            for ins in md.disasm(code[a - base:a - base + 15], a):
                return ins.size, ins.mnemonic, ins.op_str
            return None

        bodies = {int(e["addr"], 16): body_insns(insn_at, int(e["addr"], 16), int(e["addr"], 16) + e["span_upper"])
                  for e in inv["entries"] if e["span_upper"] <= WRAPPER_MAX_SPAN}
    except ImportError:
        pass
    named = structural(inv["entries"], real_names(), entry_thunks(ents, code, base, hi), set(load_ail()),
                       bodies, D.build_fixups(data, meta), base, hi, frozenset({CC.STACK_PROBE}))
    doc = structural_doc(inv["entries"], named)
    doc["_meta"]["disasm_available"] = bodies is not None
    return doc


def documented_entries() -> set[int]:
    import verify_address_claim_coverage as CC
    return set(CC.classify_all()["covered"])


def dump(inv: dict) -> str:
    return json.dumps(inv, ensure_ascii=False, indent=1) + "\n"


# --------------------------------------------------------------------------- #
# 報表
# --------------------------------------------------------------------------- #
def report_coverage() -> int:
    inv = build(with_argc=False)
    names, documented = load_names(), documented_entries()
    m = inv["_meta"]
    print(f"入口 {m['entries']}(strong {m['strong']} / weak {m['weak']});訊號:{m['by_signal']}")
    for label, strong_only in (("strong", True), ("全部", False)):
        c = coverage_counts(inv["entries"], names, documented, strong_only)
        done = c["named"] + c["documented"]
        print(f"  {label:<6} 分母 {c['total']:>4}:有名稱 {c['named']:>4} / 文件記載為入口 {c['documented']:>4} / "
              f"無名 {c['unnamed']:>4}  ->  {done * 100 // max(c['total'], 1)}% 有名稱或記載")
    sd = build_structural()
    left = sum(1 for e in inv["entries"] if e["grade"] == "strong" and e["addr"] not in sd["names"]
               and tier(int(e["addr"], 16), names, documented) == "unnamed")
    print(f"  結構性命名 {sd['_meta']['total']} 個 {sd['_meta']['by_kind']};扣掉之後 strong 裡仍完全無描述的:{left}")
    have = {int(e["addr"], 16) for e in inv["entries"]}
    stray = sorted(a for a in names if a not in have and int(m["image_range"][0], 16) <= a < int(m["image_range"][1], 16))
    print(f"  命名表裡不是任何入口的 obj1 位址:{len(stray)} 個" + (f"(前 12:{[hex(a) for a in stray[:12]]})" if stray else ""))
    return 0


def report_unnamed(limit: int | None) -> int:
    inv = build(with_argc=True)
    names, documented = load_names(), documented_entries()
    rows = [e for e in inv["entries"] if e["grade"] == "strong"
            and tier(int(e["addr"], 16), names, documented) == "unnamed"]
    rows.sort(key=lambda e: (-e["callers"], e["addr"]))
    print(f"無名的 strong 入口 {len(rows)} 個(依直接呼叫端數排序)")
    for e in rows[:limit]:
        known = [names[int(t, 16)]["name"] or t for t in e["callees"] if int(t, 16) in names]
        print(f"  {e['addr']}  callers={e['callers']:<3} span<={e['span_upper']:<5} argc={e['argc']}  "
              f"callees={len(e['callees'])} globals={len(e['globals'])}  已命名被呼叫者:{known[:6]}")
    return 0


def report_ghidra(path: str) -> int:
    inv = build(with_argc=False)
    real, placeholders = parse_ghidra(Path(path).read_text(encoding="utf-8", errors="replace"))
    c = compare_ghidra(inv["entries"], real)
    print(f"Ghidra 標頭 {len(real) + placeholders}:真函式 {len(real)}、位址空間佔位 {placeholders}")
    print(f"共有 {c['both']};只有 Ghidra {len(c['ghidra_only'])};只有本清單:落在某個 Ghidra 函式內 "
          f"{len(c['mine_inside_ghidra_fn'])}、落在空隙 {len(c['mine_in_gap'])}(其中 strong {len(c['gap_strong'])})")
    print(f"  只有 Ghidra 的前 20 個:{[hex(a) for a in c['ghidra_only'][:20]]}")
    return 0


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #
def _selftest_pure(fails: list[str]) -> None:
    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}")
        if not ok:
            fails.append(f"{label}: got {got!r} want {want!r}")

    base, hi = 0x1000, 0x1040
    code = bytearray(0x40)

    def jmp(at: int, to: int) -> None:
        # 靠近尾端時只寫得下的部分:切片賦值超出尾端會把 bytearray **撐長**,「讀不滿」的案例就變成讀得滿
        # (2026-09-18 突變窮舉抓到:`off + 5 > len(code)` 改成 6 沒有任何案例失敗)。
        raw = bytes([JMP_REL32]) + (to - at - 5).to_bytes(4, "little", signed=True)
        room = len(code) - (at - base)
        code[at - base:at - base + 5] = raw[:room]

    print("(1) thunk_targets:只認入口上的 E9,目標須在 [base, hi)")
    jmp(0x1000, 0x1020)        # 入口上的 thunk,目標在範圍內
    jmp(0x1008, 0x1030)        # 不是入口的 E9 —— 不算
    jmp(0x1010, hi)            # 目標 == hi —— 範圍外
    jmp(0x1018, base - 1)      # 目標 == base-1 —— 範圍外
    jmp(0x1028, base)          # 目標 == base —— 範圍內(下界含)
    jmp(0x103c, 0x1034)        # 入口太靠近尾端,讀不滿 5 bytes —— 不算(目標刻意獨一:算進來會多出 0x1034)
    ents = {0x1000, 0x1010, 0x1018, 0x1020, 0x1028, 0x103c}
    check("入口 thunk 命中、非入口 E9/範圍外/讀不滿都不算", thunk_targets(ents, bytes(code), base, hi),
          {0x1020: 0x1000, 0x1000: 0x1028})
    check("夾具前提:寫入沒有把 image 撐長", len(code), 0x40)
    jmp(0x103b, 0x1020)        # 剛好讀得滿 5 bytes 的最後位置
    check("剛好讀滿 5 bytes 的入口要算", thunk_targets({0x103b}, bytes(code), base, hi), {0x1020: 0x103b})
    check("入口在 base 之前不讀", thunk_targets({base - 1}, bytes(code), base, hi), {})
    two = bytearray(0x40)
    code_b = two
    for at in (0x1000, 0x1008):
        code_b[at - base] = JMP_REL32
        code_b[at - base + 1:at - base + 5] = (0x1020 - at - 5).to_bytes(4, "little", signed=True)
    check("兩個 thunk 同一目標時記位址較小的那個", thunk_targets({0x1000, 0x1008}, bytes(code_b), base, hi), {0x1020: 0x1000})

    print("(2) entry_signals / grade")
    sig = entry_signals({0x10, 0x20}, {0x20: 1, 0x30: 1, 0x40: 2}, {0x50}, {0x60: 0x10})
    check("訊號名稱與固定順序", sig, {0x10: ["prologue"], 0x20: ["prologue", "call"], 0x30: ["call"],
                              0x40: ["call"], 0x50: ["ail"], 0x60: ["thunk_target"]})
    check("grade:只被 CALL 一次 = weak;兩次 = strong;其他訊號 = strong",
          [grade(["call"], 1), grade(["call"], 2), grade(["prologue"], 0), grade(["ail"], 0),
           grade(["thunk_target"], 0), grade(["prologue", "call"], 1)],
          ["weak", "strong", "strong", "strong", "strong", "strong"])

    print("(3) spans / owner")
    check("spans:中間到下一個入口,最後一個到 hi", spans([0x10, 0x18, 0x30], 0x40), {0x10: 8, 0x18: 0x18, 0x30: 0x10})
    check("spans:空清單", spans([], 0x40), {})
    check("owner:第一個入口之前 None、起點屬於自己、下一個入口前一格屬於前一個",
          [owner([0x10, 0x18], 0xf), owner([0x10, 0x18], 0x10), owner([0x10, 0x18], 0x17),
           owner([0x10, 0x18], 0x18), owner([0x10, 0x18], 0x999)], [None, 0x10, 0x10, 0x18, 0x18])

    print("(4) callees_by_owner / globals_by_owner")
    idx = {0x500: (0x11, 0x12, 0x19), 0x600: (0x13,), 0x700: (0x5,), 0x3702f: (0x14,)}
    check("呼叫端歸屬、去重排序、__STK 不算、第一個入口之前的呼叫端丟掉",
          callees_by_owner([0x10, 0x18], idx, {0x3702f}), {0x10: [0x500, 0x600], 0x18: [0x500]})
    fx = {0x1011: 0x9000, 0x1012: 0x9000, 0x1013: 0x8000, 0x1019: base, 0x101a: hi, 0x101b: base - 1,
          0x101c: hi - 1, 0x0fff: 0x9000, hi: 0x9000, 0x1005: 0x9000}
    check("fixup:目標在 obj1 內不算(base 含、hi 不含)、來源在 obj1 外不算、第一個入口之前不算",
          globals_by_owner([0x1010, 0x1018], fx, base, hi),
          {0x1010: [0x8000, 0x9000], 0x1018: [base - 1, hi]})
    check("fixup:來源 == base 要算", globals_by_owner([base], {base: 0x9000}, base, hi), {base: [0x9000]})

    print("(5) assemble:訊號 -> 清單;__STK 不當入口、obj1 外的 CALL 目標不當入口")
    code5 = bytearray(0x40)
    code5[0x20] = JMP_REL32
    code5[0x21:0x25] = (0x1030 - 0x1020 - 5).to_bytes(4, "little", signed=True)
    inv = assemble({0x1000}, {0x1010: (0x1002,), 0x1020: (0x1004, 0x1012), 0x1038: (0x1003,),
                              0x9000: (0x1005,), base - 1: (0x1006,), hi: (0x1007,)},
                   {0x1008}, bytes(code5), base, hi, {0x1001: 0x9000}, 0x1038, argc_of=lambda a: a & 3)
    got = {e["addr"]: (e["signals"], e["callers"], e["grade"], e["span_upper"], e["argc"]) for e in inv["entries"]}
    check("入口集合與每筆欄位", got, {
        "0x1000": (["prologue"], 0, "strong", 8, 0), "0x1008": (["ail"], 0, "strong", 8, 0),
        "0x1010": (["call"], 1, "weak", 0x10, 0), "0x1020": (["call"], 2, "strong", 0x10, 0),
        "0x1030": (["thunk_target"], 0, "strong", 0x10, 0)})
    by = {e["addr"]: e for e in inv["entries"]}
    check("callees(含指向 obj1 外與 hi 的目標,但不含 __STK)與 globals",
          (by["0x1000"]["callees"], by["0x1010"]["callees"], by["0x1000"]["globals"]),
          (["0xfff", "0x1010", "0x1020", "0x1040", "0x9000"], ["0x1020"], ["0x9000"]))
    check("_meta 計數", {k: inv["_meta"][k] for k in ("entries", "strong", "weak", "by_signal", "argc_available")},
          {"entries": 5, "strong": 4, "weak": 1, "argc_available": True,
           "by_signal": {"prologue": 1, "call": 2, "ail": 1, "thunk_target": 1}})
    none = assemble({0x1000}, {}, set(), bytes(0x40), base, hi, {}, 0x1038)
    check("不給 argc_of:argc 為 null 且 _meta 如實標示", (none["entries"][0]["argc"], none["_meta"]["argc_available"]), (None, False))
    check("dump:穩定、結尾換行、中文原樣", (dump(none) == dump(none), dump(none).endswith("}\n"), "\\u" in dump({"名": 1})),
          (True, True, False))

    print("(6) tier / coverage_counts:命名表優先於文件記載;strong_only 真的只數 strong")
    ents6 = [{"addr": "0x10", "grade": "strong"}, {"addr": "0x20", "grade": "strong"},
             {"addr": "0x30", "grade": "weak"}, {"addr": "0x40", "grade": "strong"}, {"addr": "0x50", "grade": "weak"}]
    names6, doc6 = {0x10: {}, 0x30: {}}, {0x10, 0x20, 0x50}
    check("tier 三分", [tier(0x10, names6, doc6), tier(0x20, names6, doc6), tier(0x40, names6, doc6)],
          ["named", "documented", "unnamed"])
    check("strong_only", coverage_counts(ents6, names6, doc6, True), {"total": 3, "named": 1, "documented": 1, "unnamed": 1})
    check("全部", coverage_counts(ents6, names6, doc6, False), {"total": 5, "named": 2, "documented": 2, "unnamed": 1})

    print("(7) parse_ghidra / compare_ghidra")
    text = ("FUNCTION 1/4: FUN_00001000 @ 00001000  size=16\n"
            "FUNCTION 2/4: thunk_FUN_00001030 @ 00001020  size=5\n"
            "FUNCTION 3/4: FUN_.image__00002af6 @ .image::00002af6  size=1\n"
            "FUNCTION 4/4: FUN_.image__00002b50 @ .image::00002b50  size=1\n"
            "00001000  PUSH 0x3c\n")
    real, ph = parse_ghidra(text)
    check("真函式與佔位分開;thunk_ 標頭也要配到;指令行不配", (real, ph), ({0x1000: 16, 0x1020: 5}, 2))
    mine = [{"addr": "0x1000", "grade": "strong"}, {"addr": "0x1008", "grade": "weak"},
            {"addr": "0x1010", "grade": "strong"}, {"addr": "0x1018", "grade": "weak"}, {"addr": "0xfff", "grade": "strong"}]
    check("共有 / 只有 Ghidra / 落在函式內(size 上界不含)/ 空隙 / 空隙裡的 strong",
          compare_ghidra(mine, real),
          {"both": 1, "ghidra_only": [0x1020], "mine_inside_ghidra_fn": [0x1008],
           "mine_in_gap": [0xfff, 0x1010, 0x1018], "gap_strong": [0xfff, 0x1010]})


def _selftest_structural(fails: list[str]) -> None:
    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}")
        if not ok:
            fails.append(f"{label}: got {got!r} want {want!r}")

    def ent(addr, callees=(), globals_=(), span=16, grade_="strong"):
        return {"addr": hex(addr), "callees": [hex(t) for t in callees], "globals": [hex(g) for g in globals_],
                "span_upper": span, "grade": grade_, "callers": 0, "argc": None}

    print("(9) entry_thunks:每個 thunk 各自的目標(thunk_targets 是它的反向、取最小入口)")
    base, hi = 0x1000, 0x1040
    code = bytearray(0x40)
    for at, to in ((0x1000, 0x1020), (0x1008, 0x1020), (0x1010, hi)):
        code[at - base:at - base + 5] = bytes([JMP_REL32]) + (to - at - 5).to_bytes(4, "little", signed=True)
    check("兩個 thunk 同目標都列出;目標 == hi 不算;非入口不算",
          entry_thunks({0x1000, 0x1008, 0x1010, 0x1020}, bytes(code), base, hi), {0x1000: 0x1020, 0x1008: 0x1020})

    print("(10) direct_callers / closed_under_callers")
    es = [ent(0x10, [0x20, 0x30]), ent(0x20, [0x20, 0x40]), ent(0x30, [0x40]), ent(0x40), ent(0x50, [0x30]), ent(0x60)]
    check("反推呼叫端;自己呼叫自己不算", direct_callers(es), {0x20: {0x10}, 0x30: {0x10, 0x50}, 0x40: {0x20, 0x30}})
    check("只被集合內呼叫 -> 加入,逐輪到不動點;有集合外呼叫端(0x30 被 0x50 呼叫)-> 不加入,連帶 0x40 也不加入;沒有呼叫端不算",
          closed_under_callers(es, {0x10}), {0x20})
    check("把 0x50 也放進種子,0x30 與 0x40 才逐輪加入", closed_under_callers(es, {0x10, 0x50}), {0x20, 0x30, 0x40})
    check("種子本身不回傳", closed_under_callers(es, {0x10, 0x20}), set())

    print("(11) body_insns:乾淨結尾、往前分支延後結尾、解不出來與走到 limit 都是 None")
    def decoder(table):
        return lambda a: table.get(a)
    t1 = {0: (1, "push", "ebx"), 1: (2, "je", "0x6"), 3: (1, "ret", ""), 4: (2, "mov", "eax, 1"), 6: (1, "ret", ""), 7: (1, "nop", "")}
    check("je 0x6 越過第一個 ret -> 本體到第二個 ret", [x[0] for x in body_insns(decoder(t1), 0, 0x10)], [0, 1, 3, 4, 6])
    check("分支目標 == limit 不算本體內 -> 第一個 ret 就結尾", [x[0] for x in body_insns(decoder(t1), 0, 6)], [0, 1, 3])
    check("往回跳不延後結尾", [x[0] for x in body_insns(decoder({0: (2, "jne", "0x0"), 2: (1, "ret", "")}), 0, 8)], [0, 2])
    check("尾端無條件 jmp 也是結尾;retn 也算", ([x[0] for x in body_insns(decoder({0: (5, "jmp", "0x900")}), 0, 8)],
                                       [x[0] for x in body_insns(decoder({0: (3, "retn", "4")}), 0, 8)]), ([0], [0]))
    check("解不出來 -> None;走到 limit 沒結尾 -> None;start == limit -> None",
          (body_insns(decoder({0: (1, "nop", "")}), 0, 8), body_insns(decoder({0: (4, "nop", ""), 4: (4, "nop", "")}), 0, 8),
           body_insns(decoder(t1), 0, 0)), (None, None, None))

    print("(12) call_args:最近 N 個 push 反序、立即值/非立即值/不足/argc 不明、分支與 CALL 清空")
    ins = [(0, 1, "push", "ebx"), (1, 1, "push", "3"), (2, 1, "push", "eax"), (3, 1, "push", "0x1c8"), (4, 5, "call", "0x500"),
           (9, 1, "push", "-1"), (10, 5, "call", "0x600"), (15, 1, "push", "1"), (16, 2, "je", "0x20"), (18, 5, "call", "0x500"),
           (23, 1, "push", "2"), (24, 5, "call", "0x700"), (29, 2, "call", "eax"), (31, 5, "call", "0x800"), (36, 1, "ret", "")]
    check("每次呼叫的參數", call_args(ins, {0x500: 3, 0x600: 2, 0x700: None, 0x800: 0}),
          [(0x500, ["0x1c8", "_", "3"]), (0x600, ["-1", "?"]), (0x500, ["?", "?", "?"]), (0x700, None), (0x800, [])])
    check("ret 也清空 push", call_args([(0, 1, "push", "1"), (1, 1, "ret", ""), (2, 5, "call", "0x500")], {0x500: 1}), [(0x500, ["?"])])
    check("argc 表裡沒有的目標 = 不明", call_args([(0, 5, "call", "0x999")], {}), [(0x999, None)])
    stk = [(0, 5, "push", "0x28"), (5, 5, "call", "0x3702f"), (10, 1, "push", "9"), (11, 5, "call", "0x500"), (16, 1, "ret", "")]
    check("skip 的目標不列出,而且它前面的 push <frame> 不會漏給下一個呼叫",
          (call_args(stk, {0x500: 2, 0x3702f: 0}, frozenset({0x3702f})), call_args(stk, {0x500: 2, 0x3702f: 0})),
          ([(0x500, ["9", "?"])], [(0x3702f, []), (0x500, ["9", "?"])]))

    print("(13) leaf_kind")
    base, hi = 0x1000, 0x2000
    fx = {0x1002: 0x53a45, 0x1012: 0x53a45, 0x1022: 0x53a45, 0x1032: 0x53a45, 0x1042: 0x1800, 0x1051: 0x53a45,
          0x1061: 0x60000, 0x1071: 0x53a45, 0x1092: 0x53a45, 0x1099: 0x53b00, 0x1201: 0x1000, 0x1211: 0x2000}
    def lk(*insns):
        return leaf_kind(list(insns), fx, base, hi)
    check("讀全域", lk((0x1000, 6, "mov", "eax, dword ptr [0x3a45]"), (0x1006, 1, "ret", "")), {"kind": "leaf_global", "name": "leaf_get[0x53a45]"})
    check("寫全域", lk((0x1010, 6, "mov", "dword ptr [0x3a45], eax"), (0x1016, 1, "ret", "")), {"kind": "leaf_global", "name": "leaf_set[0x53a45]"})
    check("add [g], 1 = 讀寫", lk((0x1020, 7, "add", "dword ptr [0x3a45], 1"), (0x1027, 1, "ret", "")), {"kind": "leaf_global", "name": "leaf_rw[0x53a45]"})
    check("cmp [g], 0 只算讀", lk((0x1030, 7, "cmp", "dword ptr [0x3a45], 0"), (0x1037, 1, "ret", "")), {"kind": "leaf_global", "name": "leaf_get[0x53a45]"})
    check("fixup 指向 obj1 內(跳表/程式碼位址)不算全域 -> 退到 ptr 判定", lk((0x1040, 6, "mov", "eax, dword ptr [0x800]"), (0x1046, 1, "ret", "")),
          {"kind": "leaf_ptr", "name": "leaf_ptr_get"})
    check("只取位址(無括號)= ref", lk((0x1050, 5, "mov", "eax, 0x3a45"), (0x1055, 1, "ret", "")), {"kind": "leaf_global", "name": "leaf_ref[0x53a45]"})
    check("查表(括號裡有暫存器)= _idx;fixup 目標 == hi 之外也算全域",
          lk((0x1060, 7, "mov", "al, byte ptr [eax + 0x10000]"), (0x1067, 1, "ret", "")), {"kind": "leaf_global", "name": "leaf_get_idx[0x60000]"})
    check("全域 + 經指標寫 = +ptr", lk((0x1070, 6, "mov", "eax, dword ptr [0x3a45]"), (0x1076, 2, "mov", "dword ptr [ebx], eax"), (0x1078, 1, "ret", "")),
          {"kind": "leaf_global", "name": "leaf_get[0x53a45]+ptr"})
    check("兩個全域依位址排序、讀一個寫一個 = rw", lk((0x1090, 6, "mov", "eax, dword ptr [0x3a45]"), (0x1097, 6, "mov", "dword ptr [0x3b00], eax"), (0x109d, 1, "ret", "")),
          {"kind": "leaf_global", "name": "leaf_rw[0x53a45, 0x53b00]"})
    check("只經指標:讀 / 寫 / 讀寫", [lk((0x1100, 2, "mov", "eax, dword ptr [ebx]"), (0x1102, 1, "ret", ""))["name"],
                              lk((0x1100, 2, "mov", "dword ptr [ebx + 4], eax"), (0x1102, 1, "ret", ""))["name"],
                              lk((0x1100, 2, "inc", "dword ptr [ebx]"), (0x1102, 1, "ret", ""))["name"]],
          ["leaf_ptr_get", "leaf_ptr_set", "leaf_ptr_rw"])
    check("堆疊存取與 lea 不算 -> pure", lk((0x1100, 4, "mov", "eax, dword ptr [esp + 4]"), (0x1104, 3, "lea", "eax, [eax + eax*2]"),
                                     (0x1107, 3, "mov", "dword ptr [ebp - 4], eax"), (0x110a, 1, "ret", "")), {"kind": "leaf_pure", "name": "leaf_pure"})
    check("有間接 call / 間接 jmp 就不是 leaf;直接 jmp(尾端跳)不擋",
          (lk((0x1100, 6, "call", "dword ptr [0x2758]"), (0x1106, 1, "ret", "")), lk((0x1100, 7, "jmp", "dword ptr [eax*4 + 0x100]")),
           lk((0x1100, 5, "jmp", "0x1200"))), (None, None, {"kind": "leaf_pure", "name": "leaf_pure"}))
    check("fixup 落在指令最後一個 byte 要算、落在下一條不算", (lk((0x105c, 6, "mov", "eax, dword ptr [0x10000]"), (0x1062, 1, "ret", ""))["name"],
                                              lk((0x105b, 6, "mov", "eax, dword ptr [ebx]"), (0x1500, 1, "ret", ""))["name"]),
          ("leaf_get[0x60000]", "leaf_ptr_get"))
    check("fixup 目標 == base 算 obj1 內(不是全域)、== hi 算 obj1 外(是全域)",
          (lk((0x1200, 6, "mov", "eax, dword ptr [0x0]"), (0x1500, 1, "ret", ""))["name"],
           lk((0x1210, 6, "mov", "eax, dword ptr [0x1000]"), (0x1500, 1, "ret", ""))["name"]), ("leaf_ptr_get", "leaf_get[0x2000]"))

    print("(14) structural:判定順序、邊界、傳播、帶參數的 wrapper")
    names = {0x100: "pan", 0x200: "spawn"}
    es = [
        ent(0x10, [0x100, 0x200], span=WRAPPER_MAX_SPAN),          # wrapper,span 恰為上限
        ent(0x11, [0x100], span=WRAPPER_MAX_SPAN + 1),             # 超過上限
        ent(0x12, [0x100, 0x999]),                                 # 有一個未知被呼叫者
        ent(0x13, [0x100], grade_="weak"),                         # weak 不命名
        ent(0x14, [0x10, 0x200]),                                  # 第 2 輪:靠 0x10 的結構性名稱
        ent(0x15, [0x14]),                                         # 第 3 輪
        ent(0x16, [0x17]), ent(0x17, [0x16]),                      # 互相呼叫,永遠不會已知
        ent(0x18, span=LEAF_MAX_SPAN),                             # leaf,span 恰為上限
        ent(0x19, span=LEAF_MAX_SPAN + 1),
        ent(0x1a),                                                 # 本體解不出來(bodies 是 None)
        ent(0x1b),                                                 # 本體裡有間接 call
        ent(0x1c, [0x100]),                                        # thunk 優先於 wrapper
        ent(0x1d, [0x100]),                                        # thunk 目標無名 -> 用位址
        ent(0x100, [0x200]), ent(0x200),                           # 已有真名 -> 不命名
        ent(0x300, [0x1e]), ent(0x1e, [0x100]),                    # 只被 AIL 種子呼叫 -> ail_only 優先於 wrapper
        ent(0x1f, [0x100]),                                        # 本體的 CALL 目標與 callees 不一致 -> 退回不帶參數
    ]
    es[15]["argc"] = 1                                             # spawn(0x200)讀 1 個參數;pan(0x100)argc 不明
    ret = (0x900, 1, "ret", "")
    bodies = {0x10: [(0, 5, "push", "0x28"), (5, 5, "call", "0x3702f"), (10, 1, "push", "5"), (11, 5, "call", "0x200"), (16, 5, "call", "0x100"), ret],
              0x14: [(0, 1, "push", "eax"), (1, 5, "call", "0x200"), (6, 5, "call", "0x10"), ret],
              0x18: [ret], 0x19: [ret], 0x1a: None, 0x1b: [(0, 2, "call", "eax"), ret],
              0x1f: [(0, 5, "call", "0x100"), (5, 5, "call", "0x200"), ret]}
    got = structural(es, names, {0x1c: 0x200, 0x1d: 0x777}, {0x300}, bodies, {}, 0x1000, 0x2000, frozenset({0x3702f}))
    check("不給 skip:本體多出 __STK,與 callees 不一致 -> 退回不帶參數",
          structural(es, names, {}, set(), bodies, {}, 0x1000, 0x2000)[0x10]["name"], "wrapper(pan, spawn)")
    check("每一筆的 kind / name / round", got, {
        0x10: {"kind": "wrapper", "name": "wrapper(spawn(5), pan(?))", "round": 1},
        0x14: {"kind": "wrapper", "name": "wrapper(spawn(_), ~0x10(?))", "round": 2},
        0x15: {"kind": "wrapper", "name": "wrapper(~0x14)", "round": 3},
        0x18: {"kind": "leaf_pure", "name": "leaf_pure", "round": 0},
        0x1c: {"kind": "thunk", "name": "thunk->spawn", "round": 0},
        0x1d: {"kind": "thunk", "name": "thunk->0x777", "round": 0},
        0x1e: {"kind": "ail_only", "name": "ail_only", "round": 0},
        0x1f: {"kind": "wrapper", "name": "wrapper(pan)", "round": 1},
    })
    nob = structural(es, names, {0x1c: 0x200, 0x1d: 0x777}, {0x300})
    check("不給 bodies:wrapper 不帶參數、完全不出 leaf", (nob[0x10]["name"], nob[0x14]["name"], 0x18 in nob), ("wrapper(pan, spawn)", "wrapper(~0x10, spawn)", False))
    doc = structural_doc(es, got)
    check("structural_doc 的計數與每筆附帶 callers/argc",
          (doc["_meta"]["total"], doc["_meta"]["by_kind"], doc["_meta"]["wrapper_rounds"], doc["names"]["0x10"]),
          (8, {"thunk": 2, "ail_only": 1, "wrapper": 4, "leaf_global": 0, "leaf_ptr": 0, "leaf_pure": 1}, 3,
           {"kind": "wrapper", "name": "wrapper(spawn(5), pan(?))", "round": 1, "callers": 0, "argc": None}))
    check("空輸入", (structural([], {}, {}, set()), structural_doc([], {})["_meta"]["wrapper_rounds"]), ({}, 0))


def _selftest_live(fails: list[str]) -> bool:
    """真實 EXE 上的回歸與交叉核對。沒有 EXE 回 False(SKIP)。"""
    import verify_address_claim_coverage as CC
    if not os.path.exists(CC.EXE):
        print("(8) SKIP:找不到 org_game 的 FD2.EXE")
        return False

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + (f"  [{detail}]" if detail and not ok else ""))
        if not ok:
            fails.append(f"{label} {detail}")

    print("(8) 真實 EXE:與兄弟工具/已登記結論交叉核對")
    inv = build(with_argc=False)
    m, by = inv["_meta"], {int(e["addr"], 16): e for e in inv["entries"]}
    check("Watcom 序頭入口 541(與 verify_findings 的 584-entries 同一數字)", m["by_signal"]["prologue"] == 541, str(m["by_signal"]))
    ail = load_ail()
    check("AIL 105 個進入點全部在清單裡且 strong", len(ail) == 105 and all(by.get(a, {}).get("grade") == "strong" for a in ail))
    check("__STK 本身不是入口", CC.STACK_PROBE not in by)
    check("delay 的本體 0x3e01d 只由 thunk 抵達,要以 thunk_target 收進來", "thunk_target" in by.get(0x3e01d, {}).get("signals", []))
    e = by.get(0x35b78, {})
    check("0x35b78(pan_spawn_group)的 callees 含 pan 0x135dd 與 spawn 0x10b4e",
          {"0x135dd", "0x10b4e"} <= set(e.get("callees", [])), str(e.get("callees")))
    check("0x26b91(debits gold)的 globals 含金幣全域 0x53bf3", "0x53bf3" in by.get(0x26b91, {}).get("globals", []),
          str(by.get(0x26b91, {}).get("globals")))
    check("回歸釘值:strong 858 / weak 244(參考版 EXE 固定,數字變了就是判準變了)", (m["strong"], m["weak"]) == (858, 244), f"{m['strong']}/{m['weak']}")
    check("每筆 span_upper > 0 且總和 = 最後入口之後到 hi 的整段",
          all(x["span_upper"] > 0 for x in inv["entries"])
          and sum(x["span_upper"] for x in inv["entries"]) == int(m["image_range"][1], 16) - min(by))
    check("重建兩次逐位元組相同", dump(inv) == dump(build(with_argc=False)))
    print("(15) 真實 EXE:結構性命名")
    sd = build_structural()
    check("回歸釘值:thunk 4 / ail_only 30 / wrapper 95 / leaf_global 14 / leaf_ptr 15 / leaf_pure 9",
          sd["_meta"]["by_kind"] == {"thunk": 4, "ail_only": 30, "wrapper": 95, "leaf_global": 14, "leaf_ptr": 15, "leaf_pure": 9},
          str(sd["_meta"]["by_kind"]))
    check("0x2185f 依呼叫順序帶參數:先 play_sfx 再 sprite_walk_on",
          sd["names"].get("0x2185f", {}).get("name") == "wrapper(play_sfx(_, 2, 1), sprite_walk_on(_, 0xf, 0xa))", str(sd["names"].get("0x2185f")))
    check("0x20707 的常數參數讀得出來(兩次 unit_inactive 的單位編號)",
          sd["names"].get("0x20707", {}).get("name") == "wrapper(raw_result_code_0_1_2(), unit_inactive(0x32), unit_inactive(0x33))",
          str(sd["names"].get("0x20707")))
    plain = [a for a, v in sd["names"].items() if v["kind"] == "wrapper" and "(" not in v["name"][len("wrapper("):]]
    check("退回不帶參數的 wrapper 只有 1 個(本體的 CALL 與 callees 不一致)", len(plain) == 1, str(plain))
    check("反組譯器可用時 _meta 如實標示", sd["_meta"]["disasm_available"] is True)
    check("0x364fb(解鎖後釋放的記憶體輔助,24 個呼叫端全在 AIL 內)= ail_only", sd["names"].get("0x364fb", {}).get("kind") == "ail_only")
    real = real_names()
    check("有真名的入口一個都不會被結構性命名", not any(int(a, 16) in real for a in sd["names"]))
    check("每一筆都是 strong 入口", all(by[int(a, 16)]["grade"] == "strong" for a in sd["names"]))
    sc = ROOT / "docs" / "data" / "function_structural_names.json"
    if sc.exists():
        check("已提交的結構性命名產物與現算逐位元組相同", sc.read_text(encoding="utf-8") == dump(sd))
    committed = ROOT / "docs" / "data" / "function_inventory.json"
    if committed.exists():
        old = json.loads(committed.read_text(encoding="utf-8"))
        strip = lambda d: [{k: v for k, v in x.items() if k != "argc"} for x in d["entries"]]   # noqa: E731
        check("已提交產物(不看 argc)與現算相同", strip(old) == strip(inv))
    return True


def selftest() -> int:
    fails: list[str] = []
    _selftest_pure(fails)
    _selftest_structural(fails)
    live = _selftest_live(fails)
    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(7 組清單純函式 + 6 組結構性命名純函式的成對案例"
          + (" + 真實 EXE 的 18 項交叉核對)。" if live else ";真實 EXE 部分 SKIP)。"))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="FD2.EXE obj1 的函式入口清單(位元組訊號為骨架)")
    ap.add_argument("out", nargs="?", help="寫出 function_inventory.json 的路徑")
    ap.add_argument("--coverage", action="store_true", help="命名/記載覆蓋率")
    ap.add_argument("--unnamed", action="store_true", help="列出無名的 strong 入口")
    ap.add_argument("--limit", type=int, default=None, help="--unnamed 的列數上限")
    ap.add_argument("--ghidra-export", metavar="PATH", help="與 Ghidra 的 FD2_disasm_full.txt 對照")
    ap.add_argument("--structural", metavar="OUT", help="寫出結構性自動命名 function_structural_names.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.coverage:
        return report_coverage()
    if a.unnamed:
        return report_unnamed(a.limit)
    if a.ghidra_export:
        return report_ghidra(a.ghidra_export)
    if a.structural:
        sd = build_structural()
        Path(a.structural).write_text(dump(sd), encoding="utf-8", newline="\n")
        print(f"wrote {a.structural}: {sd['_meta']['total']} {sd['_meta']['by_kind']}")
        return 0
    if not a.out:
        ap.error("需要輸出路徑,或 --coverage / --unnamed / --ghidra-export / --structural / --selftest 之一")
    inv = build(with_argc=True)
    Path(a.out).write_text(dump(inv), encoding="utf-8", newline="\n")
    m = inv["_meta"]
    print(f"wrote {a.out}: entries {m['entries']} (strong {m['strong']} / weak {m['weak']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
