#!/usr/bin/env python3
"""下一輪原版實機擷取該跑哪裡:以已執行的程式為邊界,排出「打開哪個分支能多涵蓋最多入口」(doc98 續九十八)。

輸入全是倉庫裡的東西:`function_inventory.json`(入口、grade、直接呼叫的 callees)、`live_exec_addresses.json`
(原版 DOSBox-X 執行過的位址)、FD2.EXE 的 LE fixup。不開模擬器,只產生建議清單,由人決定要不要擷取。

呼叫圖的邊(父 -> 子),四種:
  call   父的本體直接 `call 子`(inventory 的 callees)。
  jmp    父的 span 線性解碼有 `j* 子`,且子是別的入口(thunk、尾呼叫)。
  ref   父的程式碼裡有一個 fixup 指向子(取函式位址,之後當回呼或存進結構)。
  table  子的位址存在資料區的指標表裡(連續 4 bytes 的 fixup),父的程式碼有 fixup 指向那張表(以索引分派)。

「前線」= 父有執行紀錄(入口位址在軌跡裡)、子沒有。子在呼叫圖上能走到、且同樣沒有執行紀錄的 strong 入口
就是打開這條邊的**收益**。weak 入口(靜態判為沒有執行路徑)不計收益。收益互相重疊,所以清單以貪婪法排:每一步選
**新增**最多的前線,扣掉已涵蓋的再選下一步 —— 用最少的擷取次數換最多的新入口。

另有一致性檢查:軌跡裡有執行紀錄的 `call 目標` 指令,其目標入口也必須有執行紀錄;不成立代表軌跡截斷或位址換算錯,
這時整份計畫不可信(回傳 1)。

誠實邊界:
  * 邊只到 fixup 與直接 call 為止:執行期算出來的位址(`push`+`ret`、算出來的表索引)看不到,這類子會落在
    「沒有任何路徑」那一欄,不是真的到不了。
  * 前線只說「這條邊在已擷取的場景裡沒走到」,要觸發它的遊戲操作得讀父函式(`function_inventory.py --card`)。
  * 收益是入口數,不是指令數,也不保證實機一定能觸發(例如只有錯誤路徑才會走到的)。

用法:
    python tools/plan_trace_coverage.py [--steps N] [--by-parent N]
    python tools/plan_trace_coverage.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

INVENTORY_JSON = ROOT / "docs" / "data" / "function_inventory.json"
TABLE_REF_SLACK = 8         # 以 1 起算的索引會引用表頭前 4 / 8 bytes(`[eax*4+表頭-4]`)

Edges = dict[int, dict[int, list[tuple[str, int | None]]]]


def owner_in_span(addrs: list[int], spans: dict[int, int], a: int) -> int | None:
    """`a` 所屬的入口;不在任何入口的 [入口, 入口 + span) 內回 None。"""
    i = bisect.bisect_right(addrs, a) - 1
    if i < 0:
        return None
    o = addrs[i]
    return o if a < o + spans[o] else None


def pointer_tables(data_slots: list[int]) -> list[tuple[int, int]]:
    """資料區裡指向入口的 fixup 位置 -> 指標表 [起, 迄)(連續、間隔 4 bytes 的一段算一張)。"""
    out: list[tuple[int, int]] = []
    for s in sorted(set(data_slots)):
        if out and s == out[-1][1]:
            out[-1] = (out[-1][0], s + 4)
        else:
            out.append((s, s + 4))
    return out


def build_edges(spans: dict[int, int], callees: dict[int, list[int]], fixups: dict[int, int],
                code_lo: int, code_hi: int, jumps: dict[int, list[int]] | None = None) -> Edges:
    """父 -> {子: [(種類, 細節)]};細節:call / jmp 為 None、ref 為 fixup 位置、table 為表格位置。

    `jumps` = {父: [跳進去的別的入口]}(thunk、尾呼叫;`decoded_jumps` 的結果)。
    """
    addrs = sorted(spans)
    ents = set(addrs)
    out: Edges = collections.defaultdict(lambda: collections.defaultdict(list))
    for kind, src in (("call", callees), ("jmp", jumps or {})):
        for p, cs in src.items():
            for c in cs:
                if c in ents and c != p:
                    out[p][c].append((kind, None))
    slot_target: dict[int, int] = {}
    code_refs: list[tuple[int, int]] = []           # (fixup 位置, 目標),來源在程式碼區
    for src, tgt in fixups.items():
        if code_lo <= src < code_hi:
            code_refs.append((src, tgt))
            if tgt in ents:
                p = owner_in_span(addrs, spans, src)
                if p is not None and p != tgt:
                    out[p][tgt].append(("ref", src))
        elif tgt in ents:
            slot_target[src] = tgt
    tables = pointer_tables(list(slot_target))
    starts = [t[0] for t in tables]
    for src, tgt in code_refs:
        i = bisect.bisect_right(starts, tgt + TABLE_REF_SLACK) - 1
        if i < 0:
            continue
        lo, hi = tables[i]
        if not (lo - TABLE_REF_SLACK <= tgt < hi):
            continue
        p = owner_in_span(addrs, spans, src)
        if p is None:
            continue
        for slot in range(lo, hi, 4):
            c = slot_target[slot]
            if c != p:
                out[p][c].append(("table", slot))
    return {p: dict(cs) for p, cs in out.items()}


def closure(start: int, edges: Edges, pool: set[int]) -> set[int]:
    """從 start 沿邊走、只經過 pool 裡的節點能到的集合(含 start;start 不在 pool 回空集合)。"""
    if start not in pool:
        return set()
    seen, todo = {start}, [start]
    while todo:
        for c in edges.get(todo.pop(), {}):
            if c in pool and c not in seen:
                seen.add(c)
                todo.append(c)
    return seen


def frontier(edges: Edges, executed: set[int], pool: set[int]) -> dict[int, list[tuple[int, str, int | None]]]:
    """子 -> [(已執行的父, 種類, 細節)];子在 pool(沒執行過的 strong 入口)裡。"""
    out: dict[int, list[tuple[int, str, int | None]]] = collections.defaultdict(list)
    for p, cs in edges.items():
        if p not in executed:
            continue
        for c, kinds in cs.items():
            if c in pool:
                out[c].extend((p, k, d) for k, d in kinds)
    return dict(out)


def greedy_plan(gains: dict[int, set[int]], steps: int) -> list[tuple[int, set[int]]]:
    """每一步選新增最多的前線子(同分取位址小的),回傳 [(子, 這一步新增的入口)];新增為 0 就停。"""
    covered: set[int] = set()
    plan: list[tuple[int, set[int]]] = []
    left = dict(gains)
    for _ in range(steps):
        best = max(left, key=lambda c: (len(left[c] - covered), -c), default=None)
        if best is None:
            break
        new = left.pop(best) - covered
        if not new:
            break
        plan.append((best, new))
        covered |= new
    return plan


def call_consistency(live: set[int], call_sites: dict[int, int]) -> tuple[int, list[tuple[int, int]]]:
    """(執行過的 call 指令數, [(call 位址, 沒有執行紀錄的目標)])。`call_sites` = {call 位址: 目標入口}。"""
    ran = [(s, t) for s, t in call_sites.items() if s in live]
    return len(ran), sorted((s, t) for s, t in ran if t not in live)


def decoded_call_sites(entries: list[dict], insn_at) -> dict[int, int]:
    """每個入口的 callees 對應到本體裡真的解成 `call 目標` 的位址 -> {call 位址: 目標}。

    以 inventory 的 span 線性解碼(與 `--card` 相同);只收目標是 callees 之一的,資料位元組偶然解成 call 的不收。
    """
    out: dict[int, int] = {}
    for e in entries:
        a, end = int(e["addr"], 16), int(e["addr"], 16) + e["span_upper"]
        want = {int(c, 16) for c in e["callees"]}
        x = a
        while x < end and want:
            got = insn_at(x)
            if got is None:
                x += 1
                continue
            size, mn, op = got
            if mn == "call" and op.startswith("0x") and int(op, 16) in want:
                out[x] = int(op, 16)
            x += size
    return out


def decoded_jumps(entries: list[dict], insn_at) -> dict[int, list[int]]:
    """每個入口的 span 線性解碼,`j*`(含條件跳)的立即目標若是**別的**入口 -> {父: [子]}。

    inventory 的 callees 只收 call;thunk(入口第一條就是 jmp)與尾呼叫(`jmp 別的函式`)要靠這個補邊。
    跳回自己 span 內的不算(那是函式內的分支)。
    """
    ents = {int(e["addr"], 16) for e in entries}
    out: dict[int, list[int]] = {}
    for e in entries:
        a = int(e["addr"], 16)
        end = a + e["span_upper"]
        got_set: set[int] = set()
        x = a
        while x < end:
            got = insn_at(x)
            if got is None:
                x += 1
                continue
            size, mn, op = got
            if mn.startswith("j") and op.startswith("0x"):
                t = int(op, 16)
                if t in ents and not (a <= t < end):
                    got_set.add(t)
            x += size
        if got_set:
            out[a] = sorted(got_set)
    return out


def table_slot_label(kind: str, slot: int | None) -> str:
    """已知跳表(`function_inventory.JUMP_TABLES`)的格位 -> `(event_handler 第 N 格)`;其他回空字串。"""
    if kind != "table" or slot is None:
        return ""
    import function_inventory as FI
    for base, (n, prefix, _) in FI.JUMP_TABLES.items():
        if base <= slot < base + 4 * n and (slot - base) % 4 == 0:
            return f"({prefix} 第 {(slot - base) // 4} 格)"
    return ""


def load_inputs():
    import function_inventory as FI
    import verify_address_claim_coverage as CC
    import disasm_le as D
    inv = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))["entries"]
    live, lm = FI.load_live_exec()
    data, meta, code, base, hi = CC.load_image()
    fixups = D.build_fixups(data, meta)
    insn_at = FI.insn_decoder(code, base)
    return inv, live, lm, fixups, base, hi, insn_at, FI.load_names()


def run(steps: int, by_parent: int) -> int:
    inv, live, lm, fixups, base, hi, insn_at, names = load_inputs()
    if insn_at is None:
        print("沒有 capstone:無法做 call 指令的一致性檢查,不產生計畫。")
        return 2
    spans = {int(e["addr"], 16): e["span_upper"] for e in inv}
    callees = {int(e["addr"], 16): [int(c, 16) for c in e["callees"]] for e in inv}
    grade = {int(e["addr"], 16): e["grade"] for e in inv}

    def lab(a: int) -> str:
        n = (names.get(a) or {}).get("name")
        return f"{a:#x}" + (f" {n}" if n else "")

    executed = {a for a in spans if a in live}
    weak = {a for a, g in grade.items() if g == "weak"}
    pool = set(spans) - executed - weak
    print(f"實機軌跡 {lm['traces_distinct']} 份不重複;入口有執行紀錄 {len(executed)} / {len(spans)};"
          f"沒有紀錄的 strong {len(pool)}、weak {len(weak - executed)}(weak 不計收益)")

    n_ran, bad = call_consistency(live, decoded_call_sites(inv, insn_at))
    print(f"一致性:有執行紀錄的 call 指令 {n_ran} 條,目標沒有執行紀錄的 {len(bad)} 條"
          + (":" + ", ".join(f"{s:#x}->{lab(t)}" for s, t in bad[:5]) if bad else ""))
    if bad:
        print("  軌跡與呼叫圖對不上(截斷或位址換算錯),以下計畫不可信。")
        return 1

    edges = build_edges(spans, callees, fixups, base, hi, decoded_jumps(inv, insn_at))
    fr = frontier(edges, executed, pool)
    eip = [a for a, e in ((int(e["addr"], 16), e) for e in inv) if "eip" in e["signals"]]
    if eip and not any(a in live for a in eip):
        print(f"注意:LE 進入點 {', '.join(lab(a) for a in eip)} 沒有執行紀錄 —— 現有軌跡都是開機後才開始錄,"
              "啟動段只能靠「從開機就錄」的擷取補。")
    gains = {c: closure(c, edges, pool) for c in fr}
    kinds = collections.Counter(k for ps in fr.values() for _, k, _ in ps)
    reach = set().union(*gains.values()) if gains else set()
    print(f"前線(父有紀錄、子沒有)的子 {len(fr)} 個;邊的種類 {dict(kinds)}")
    print(f"所有前線打開後可涵蓋 {len(reach)} / {len(pool)};從已執行的程式沒有任何路徑可到的 {len(pool - reach)}")

    plan = greedy_plan(gains, steps)
    print(f"\n貪婪計畫(每一步新增最多;前 {len(plan)} 步):")
    total = 0
    for i, (c, new) in enumerate(plan, 1):
        total += len(new)
        via = []
        for p, k, d in fr[c][:3]:
            via.append(f"{lab(p)} {k}" + (f"@{d:#x}" if d is not None else "") + table_slot_label(k, d))
        sample = ", ".join(lab(x) for x in sorted(new - {c})[:3])
        print(f"{i:3d}. +{len(new):3d}(累計 {total:4d})  {lab(c)}  <- {'; '.join(via)}")
        if sample:
            print(f"        連帶:{sample}" + (" …" if len(new) > 4 else ""))

    agg: dict[int, set[int]] = collections.defaultdict(set)
    for c, ps in fr.items():
        for p, _, _ in ps:
            agg[p] |= gains[c]
    print(f"\n依已執行的父函式彙總(它底下沒走到的分支合計可涵蓋;前 {by_parent} 個):")
    for p, g in sorted(agg.items(), key=lambda x: (-len(x[1]), x[0]))[:by_parent]:
        kids = sorted({c for c, ps in fr.items() if any(q == p for q, _, _ in ps)})
        print(f"  {len(g):4d}  {lab(p)}  前線子 {len(kids)} 個,例 {', '.join(lab(c) for c in kids[:3])}")

    rest = pool - reach
    sig = {int(e["addr"], 16): e["signals"] for e in inv}
    has_parent = {c for cs in edges.values() for c in cs}
    root_gain = {a: closure(a, edges, rest) for a in rest - has_parent}
    roots = sorted(root_gain, key=lambda a: (-len(root_gain[a]), a))
    under = set().union(*root_gain.values()) if root_gain else set()
    print(f"\n沒有路徑可到的 {len(rest)} 個:沒有任何父邊的根 {len(roots)} 個,連同它們帶出的共 {len(under)} 個;"
          f"其餘 {len(rest - under)} 個的父邊只來自 weak 入口或彼此成環。")
    print("  根是本工具看不到抵達方式的入口(LE 進入點、只由 AIL 名稱表或執行期算出的位址抵達等);依可帶出的入口數前 10:")
    for a in roots[:10]:
        print(f"  {len(root_gain[a]):4d}  {lab(a)}  {sig[a]}")
    return 0


def selftest() -> int:
    fails: list[str] = []

    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
        if not ok:
            fails.append(label)

    print("(1) owner_in_span / pointer_tables")
    check("span 內歸屬、span 外與第一個入口之前為 None",
          [owner_in_span([0x100, 0x200], {0x100: 0x10, 0x200: 0x10}, a) for a in (0x100, 0x10F, 0x110, 0xFF, 0x205)],
          [0x100, 0x100, None, None, 0x200])
    check("連續 4 bytes 合成一張表,斷開就分開,重複位置不重算",
          pointer_tables([0x5000, 0x5004, 0x5008, 0x5010, 0x5004]), [(0x5000, 0x500C), (0x5010, 0x5014)])

    print("(2) build_edges:call / jmp / ref / table 四種邊;table_slot_label")
    spans = {0x100: 0x20, 0x200: 0x20, 0x300: 0x20, 0x400: 0x20, 0x500: 0x20}
    fx = {0x110: 0x300,            # 0x100 的程式碼取 0x300 的位址 -> ref
          0x9000: 0x400, 0x9004: 0x500,   # 資料區指標表 [0x9000, 0x9008)
          0x210: 0x8FFC,           # 0x200 以表頭 -4 引用表(1 起算的索引)-> table
          0x9100: 0x100,           # 孤立的資料指標,沒有程式碼引用 -> 不成邊
          0x120: 0x777,            # 指向非入口 -> 不成邊
          0x150: 0x9000}           # 0x150 不在任何 span 內 -> 不成邊
    e = build_edges(spans, {0x100: [0x200, 0x100, 0x999]}, fx, 0x100, 0x600)
    check("call 只收入口、不收自己;ref 帶 fixup 位置;table 帶表格位置",
          e, {0x100: {0x200: [("call", None)], 0x300: [("ref", 0x110)]},
              0x200: {0x400: [("table", 0x9000)], 0x500: [("table", 0x9004)]}})
    check("引用落在表頭前超過 slack、或落在表尾之後,都不算",
          (build_edges(spans, {}, {0x9000: 0x400, 0x210: 0x8FF0}, 0x100, 0x600),
           build_edges(spans, {}, {0x9000: 0x400, 0x210: 0x9004}, 0x100, 0x600)), ({}, {}))
    check("jmp 邊(thunk / 尾呼叫)與 call 同規則:只收入口、不收自己",
          build_edges(spans, {}, {}, 0x100, 0x600, {0x300: [0x400, 0x300, 0x999]}), {0x300: {0x400: [("jmp", None)]}})
    check("已知跳表格位標出第幾格;非跳表、非格位邊界、非 table 種類不標",
          (table_slot_label("table", 0x51D01 + 4 * 12), table_slot_label("table", 0x51D01 + 2),
           table_slot_label("table", 0x9000), table_slot_label("ref", 0x51D01)),
          ("(command_handler 第 12 格)", "", "", ""))

    print("(3) closure / frontier / greedy_plan")
    g = {1: {2: [("call", None)]}, 2: {3: [("call", None)], 9: [("call", None)]}, 3: {2: [("call", None)]},
         4: {5: [("table", 0x9000)], 6: [("call", None)], 1: [("call", None)]}, 7: {8: [("ref", 0x11)]}}
    pool = {2, 3, 5, 6, 8}
    check("只經過 pool、有環也會停;start 不在 pool 為空", (closure(2, g, pool), closure(1, g, pool)), ({2, 3}, set()))
    check("前線:父已執行、子在 pool;父沒執行(7)、子已執行(4 -> 1)不算", frontier(g, {1, 4}, pool),
          {2: [(1, "call", None)], 5: [(4, "table", 0x9000)], 6: [(4, "call", None)]})
    gains = {10: {1, 2, 3}, 11: {3, 4}, 12: {4, 5}, 13: {1}}
    check("貪婪:先最大,再算扣掉已涵蓋後的新增;新增 0 就停", greedy_plan(gains, 10), [(10, {1, 2, 3}), (12, {4, 5})])
    check("同分取位址小的;steps 上限", greedy_plan({20: {1}, 19: {2}}, 1), [(19, {2})])

    print("(4) call_consistency / decoded_call_sites / decoded_jumps")
    check("執行過的 call 才算;目標沒紀錄的列出", call_consistency({0x10, 0x20, 0x50}, {0x10: 0x50, 0x20: 0x60, 0x30: 0x70}),
          (2, [(0x20, 0x60)]))
    table = {0x100: (5, "call", "0x200"), 0x105: (5, "call", "0x300"), 0x10C: (5, "call", "0x400")}

    def fake(a):
        return table.get(a)

    check("只收 callees 裡的目標;解不出來的位元組跳過",
          decoded_call_sites([{"addr": "0x100", "span_upper": 0x11, "callees": ["0x200", "0x400"]}], fake),
          {0x100: 0x200, 0x10C: 0x400})
    jt = {0x100: (2, "jne", "0x100"), 0x102: (3, "je", "0x300"), 0x105: (3, "call", "0x200"),
          0x200: (5, "jmp", "0x100"), 0x300: (5, "call", "0x100"), 0x305: (2, "jmp", "0x308")}
    ents_j = [{"addr": "0x100", "span_upper": 0x8, "callees": []}, {"addr": "0x200", "span_upper": 0x10, "callees": []},
              {"addr": "0x300", "span_upper": 0x10, "callees": []}]
    check("decoded_jumps:跳進別的入口(含條件跳、thunk)才算;跳回自己 span 內、call 不算",
          decoded_jumps(ents_j, lambda a: jt.get(a)), {0x100: [0x300], 0x200: [0x100]})
    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        return 1
    print("\n--selftest passed(4 組 16 項純函式案例,含成對的反向案例)。")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="以實機執行位址為邊界,排出下一輪擷取的優先順序")
    ap.add_argument("--steps", type=int, default=30, help="貪婪計畫列幾步(預設 30)")
    ap.add_argument("--by-parent", type=int, default=15, help="依父函式彙總列幾個(預設 15)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return run(a.steps, a.by_parent)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
