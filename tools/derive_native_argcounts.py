#!/usr/bin/env python3
"""fd2_re — 從呼叫端機械推導原生函式的參數個數(cdecl),多個獨立機制互相驗證。

為什麼需要這支
--------------
`dump_chapter_beats.py` 把 30 章的過場 handler 抽成 beats,而它認得的原語表
`PRIM` 是 `位址 -> (op 名, 參數個數)`。參數個數填錯不會報錯,只會讓 beat 的
`args` 靜默取錯數量的 push——所以 91-worklist L212 把「逐一驗證尚未收錄原語的
參數個數」列為 chapter_beats 61 個檔案遷移的前置條件,並明言**填錯比留 unknown
更糟**。那份工作先前被當成需要人工反組譯;實測它是機械可導的。

判準
----
cdecl 的呼叫端同時要做兩件事,兩者都編碼了參數個數,而且是**互相獨立**的:

  A. 清理:`call f` 之後的 `add esp, N` -> 參數個數 = N / 4
  B. 佈置:`call f` 之前緊鄰的連續 `push` 個數

同一個函式的所有呼叫端必須給出一致的答案;不一致本身就是訊號。兩個訊號
**同時**用,是因為各有已知的失效模式:

  * A 會被**合併清理**騙:`call f; call g; add esp,8` 的清理涵蓋兩個呼叫,
    前一個會被誤讀成 0 個參數。全 image 只有 1.4% 的 call 後面緊接 call,
    但受影響的目標必須個別標出來,不能混在一起報。
  * B 會被**行內計算的參數**騙:參數不是連續 push 而是邊算邊推時,連續
    push 數會低估。實測 `0x24618` 就是這樣(A 得 4、B 得 2),而 doc56
    早已獨立反組譯記載它「first two arguments feed tile geometry
    (arg1*24+12, arg2*24+16); the third starts a radial radius and the
    fourth increments that radius」= 4 個參數——第三條證據站在 A 這邊。

單一呼叫端的「100% 一致」是恆真的,不算證據,一律降級。

呼叫端從哪裡來也有兩種獨立機制:CFG 可達走訪(從 chapter handler 跳表出發)
與全 image 位元組掃描(直接找 `E8 rel32`)。兩者對「哪些位址是呼叫端」的認定
完全獨立,而實測 27 個目標的參數個數在兩種機制下**沒有一個改變**,儘管呼叫端
數量差到 3~6 倍。這比「兩個訊號一致」更強,因為連取樣母體都換了。

op 名稱(2026-09-09 加入,與參數個數是**兩種不同的主張**)
--------------------------------------------------------
`DOC_OP_NAMES` 只收「repo 文件裡已經反組譯過、而且引文可以逐字定位」的名稱,一律不
用推的。入場規則是:引文必須逐字存在,**而且**該位址要寫在引文的 ±3 行內。第二個
條件不是裝飾——建表時先用純鄰近掃描得到「22/27 有完整反組譯」,查證後發現
`91-worklist.md` L213 是本工具自己那條列了一堆位址的摘要行,被算成六個位址各自的
證據,`0x31529`/`0x25089` 也都是假陽性。錨點每次呼叫都會複驗,文件被改掉就自動失效。

**名稱不會帶動參數個數**:`0x22253` 有完整的 5 參數 ABI 記載(所以有名稱),但呼叫端
母體擴大後判定 LIKELY,它的 `args` 仍然保留原始 push 並標記。反過來也一樣。這是刻意
的——worklist 說的「填錯比留 unknown 更糟」主要針對語意,兩件事不混為一談。

27 個目標中 **19 個**有名稱。**先前寫「13 個,其餘全庫查無命名段落」是錯的**:當時的搜尋
要求位址與確認詞出現在**同一行**,而文件是在表格、標題、敘述裡命名的——`0x17aa9`(doc23
「tick 計數忙等」)、`0x25052`(doc56 給了完整簽名)、`0x13536`(doc56「對全部 runtime
records 執行 raw `+5 &= 0x7F`」)、`0x31529`(doc35 §9.11.3 標題)、`0x35b78`(doc25 §11
訂正過的簽名)全都有,只是搜不到。這是同一個 session 裡第四次「查無資料」的結論來自不完整
的搜尋,寫在這裡當提醒。

仍然維持 unknown 的 8 個各有理由:`0x3776e` doc13 明寫「語意仍是推測,**未證實**」(被反組譯成
memmove 的是它的鄰居 `0x3771c`);`0x35f10` doc25 明寫「本體未展開」;`0x361b0`/`0x1c2da`/
`0x4df4c` 文件只提到被呼叫、沒有命名(`0x4df4c` 另有一筆未收斂的行為矛盾);`0x1f882`/
`0x25089` 有合併清理風險;`0x24336` 全 image 只有一個呼叫端。

`doc_argc` 記 `None` 表示**文件只給名稱、沒給簽名**:此時名稱由文件負責、參數個數由本工具的
雙訊號推導負責(規則是必須 CONFIRMED),兩種主張各自有支撐,不互相借力。

`0x24bde` 的名稱刻意與 PRIM 的 `0x33499` 相同:doc25 記載它是同一個 `roster_has(id)`
原語的第二個獨立編譯實例,本體逐位元組相同。所以撞名規則不是一律禁止,而是**撞名時
引文必須自己提到那個名字**——引文沒提到就是認錯函式,照樣擋下。

用法
----
    python tools/derive_native_argcounts.py <EXE>              報告 27 個未收錄目標
    python tools/derive_native_argcounts.py <EXE> --all        報告全部被呼叫的目標
    python tools/derive_native_argcounts.py <EXE> --wide       用全 image 位元組掃描找呼叫端
    python tools/derive_native_argcounts.py <EXE> --json out   輸出 JSON
    python tools/derive_native_argcounts.py --selftest
"""
from __future__ import annotations

import argparse
import collections
import functools
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXE = ROOT / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"

WORD = 4                    # 32-bit cdecl:一個參數一個 dword
MAX_PUSH_SCAN = 16          # 往回數 push 的上限,避免掃過整個 basic block


def build_graph(exe: str):
    """用 chapter handler 跳表當種子做可達反組譯,回傳 (cg, 已排序位址)。"""
    from callgraph_le import CG, fixup_map
    import dump_chapter_beats as DC
    cg = CG(exe)
    fx = fixup_map(cg.d, cg.meta)
    seeds = sorted({h for _, h in DC.resolve_table(fx, DC.TABLE_PRE, DC.N_CHAPTERS)}
                   | {h for _, h in DC.resolve_table(fx, DC.TABLE_POST, DC.N_CHAPTERS)})
    cg.build(seeds)
    return cg, sorted(cg.reached)


def cleanup_after(cg, site: int) -> tuple[int | None, str]:
    """(add esp,N 的 N,call 之後那條指令的助憶符)。沒有清理就是 None。"""
    ins = cg._insn(site)
    if ins is None:
        return None, "?"
    nxt = cg._insn(site + ins.size)
    if nxt is None:
        return None, "?"
    if nxt.mnemonic == "add" and nxt.op_str.replace(" ", "").startswith("esp,"):
        try:
            return int(nxt.op_str.split(",")[1].strip(), 0), nxt.mnemonic
        except ValueError:
            return None, nxt.mnemonic
    return None, nxt.mnemonic


def pushes_before(cg, order: list[int], index: dict[int, int], site: int) -> int:
    """呼叫端之前**緊鄰連續**的 push 個數。行內計算參數時會低估,這是已知的。"""
    i = index.get(site)
    if i is None:
        return 0
    n, j = 0, i - 1
    while j >= 0 and n < MAX_PUSH_SCAN:
        ins = cg._insn(order[j])
        if ins is None or ins.mnemonic != "push":
            break
        n += 1
        j -= 1
    return n


STACK_CHECK = 0x3702f       # Watcom 序頭 `push <frame>; call 0x3702f`(541 個呼叫端)
FUNCTION_ENTRIES = 541      # 實測值;與 verify_findings.function_entries() 逐一相同


def _scan(cg) -> tuple[dict[int, tuple[int, ...]], frozenset[int]]:
    """掃 `cg.code` 找 `E8 rel32`,一次得出(呼叫端索引, 函式入口集合)。

    **判準是借來的,位元組是自己的。** 「什麼算函式入口」這條判準屬於
    `verify_findings`(Watcom `push <frame>; call 0x3702f`,入口 = 該 call 位址
    減 5),這裡沿用同一條規則;但不透過它取位元組——`verify_findings.segments()`
    是走 **Ghidra headless** 讀的,實測 **22.3 秒**,而 `callgraph_le.CG` 已經
    把同一份 image 載在 `cg.code` 裡了。自己掃 **0.004 秒**,快 5500 倍,而且
    實測結果相同:函式入口 541 個逐一相同、呼叫端索引在共同範圍內完全一致。

    為什麼在意這 22 秒:它會被乘。突變測試每個突變都是新行程,lru_cache 救不到,
    96 個突變就是 40 分鐘;`verify_everything` 的 discrim 軸每支工具跑 12 次,
    也一起付。先量成本,再看它會被乘幾次——這輪第三次踩到同一件事。

    對兄弟工具的核對沒有省掉,只是移到 `--verify-entries`(見 main),不讓每次
    執行都付 Ghidra 的代價;入口數 541 也釘進 selftest 當回歸。
    """
    d, lo = cg.code, cg.base
    idx: dict[int, list[int]] = collections.defaultdict(list)
    ents: set[int] = set()
    limit = len(d) - 5
    i = d.find(0xE8)
    while 0 <= i <= limit:
        rel = int.from_bytes(d[i + 1:i + 5], "little", signed=True)
        tgt = lo + i + 5 + rel
        idx[tgt].append(lo + i)
        if tgt == STACK_CHECK:
            ents.add(lo + i - 5)
        i = d.find(0xE8, i + 1)
    return {k: tuple(v) for k, v in idx.items()}, frozenset(ents)


@functools.lru_cache(maxsize=4)
def _scan_cached(exe: str):
    from callgraph_le import CG
    return _scan(CG(exe))


def byte_scan_call_index(cg) -> dict[int, tuple[int, ...]]:
    """目標 -> 全 image 的直接呼叫端,用**位元組掃描**找,不依賴可達性。

    第二種呼叫端發現機制,與 CFG 走訪完全獨立。用它的理由是 CFG 種子只從
    chapter handler 跳表出發,子系統外的呼叫端看不到——實測 `0x1b8e7` 在 CFG
    圖裡只有 1 個呼叫端(因而被降級成 WEAK),位元組掃描找到 **13 個**;
    `0x1c2da` 1 -> 11、`0x1f882` 11 -> 38。
    """
    return _scan(cg)[0]


def collect_wide(cg, target: int) -> list[dict]:
    """用位元組掃描的呼叫端算兩個訊號。

    清理訊號:`E8 rel32` 固定 5 bytes,所以 `site+5` 就是下一條指令,可直接解。
    push 訊號:需要一條可靠的指令流,所以從**包住這個呼叫端的函式入口**線性
    反組譯到該位址再取尾端連續 push——不是往回猜指令邊界。
    """
    idx, entries = _scan(cg)
    ents = sorted(entries)
    out = []
    for site in idx.get(target, ()):
        ins = cg._insn(site)
        if ins is None or ins.mnemonic != "call":
            continue                      # 資料裡碰巧的 E8,不是真的呼叫
        n, after = cleanup_after(cg, site)
        lo = [e for e in ents if e <= site]
        pushes = 0
        if lo:
            a, stream = max(lo), []
            while a < site:
                cur = cg._insn(a)
                if cur is None:
                    break
                stream.append(cur)
                a += cur.size
            if a == site:                 # 必須剛好停在呼叫端,否則指令流對不齊
                for cur in reversed(stream):
                    if cur.mnemonic != "push":
                        break
                    pushes += 1
        out.append({"site": site, "cleanup_bytes": n,
                    "after_mnemonic": after, "pushes": pushes})
    return out


def collect(cg, order: list[int]) -> dict[int, list[dict]]:
    """目標位址 -> 每個呼叫端的兩個訊號(CFG 可達走訪找到的呼叫端)。"""
    index = {a: i for i, a in enumerate(order)}
    out: dict[int, list[dict]] = collections.defaultdict(list)
    for site, target in cg.calls.items():
        n, after = cleanup_after(cg, site)
        out[target].append({
            "site": site,
            "cleanup_bytes": n,
            "after_mnemonic": after,
            "pushes": pushes_before(cg, order, index, site),
        })
    return out


def derive(sites: list[dict]) -> dict:
    """兩個訊號各自多數決,再合併成一個帶信心等級的判定。

    多數決**必須把「沒有清理」一起算進去**:`palfade`(0x1f525)的 9 個呼叫端
    有 8 個沒有清理、只有 1 個 `add esp,48`,先濾掉 None 就會採信那個離群值
    而得出 12 個參數。沒有清理 = 0 個參數。
    """
    if not sites:
        return {"argc": None, "verdict": "NO_CALLSITE", "sites": 0}
    cl = collections.Counter(s["cleanup_bytes"] for s in sites)
    top_cl, n_cl = cl.most_common(1)[0]
    argc_cleanup = 0 if top_cl is None else top_cl // WORD
    ps = collections.Counter(s["pushes"] for s in sites)
    argc_push = ps.most_common(1)[0][0]

    merged = [s["site"] for s in sites
              if s["cleanup_bytes"] is None and s["after_mnemonic"] == "call"]
    flags = []
    if len(sites) < 2:
        flags.append("single_callsite")
    if merged:
        flags.append("merged_cleanup_risk")
    if argc_push != argc_cleanup:
        flags.append("signals_disagree")
    agreement = n_cl / len(sites)
    if agreement < 1.0:
        flags.append("callsites_disagree")

    if "single_callsite" in flags or "merged_cleanup_risk" in flags:
        verdict = "WEAK"
    elif "signals_disagree" in flags or agreement < 0.9:
        verdict = "LIKELY"
    else:
        verdict = "CONFIRMED"
    return {
        "argc": argc_cleanup,
        "argc_from_pushes": argc_push,
        "verdict": verdict,
        "sites": len(sites),
        "agreement": round(agreement, 3),
        "flags": flags,
        "cleanup_distribution": {str(k): v for k, v in
                                 sorted(cl.items(), key=lambda x: (x[0] is None, x[0]))},
        "merged_cleanup_sites": [hex(s) for s in sorted(merged)],
    }


def report(exe: str, only_unknown: bool = True, wide: bool = False) -> dict:
    import dump_chapter_beats as DC
    cg, order = build_graph(exe)
    sites = collect(cg, order)
    targets = sorted(UNKNOWN_TARGETS) if only_unknown else sorted(sites)
    out = {}
    for t in targets:
        d = derive(collect_wide(cg, t) if wide else sites.get(t, []))
        d["known_op"] = DC.PRIM.get(t, (None, None))[0]
        # 名稱與參數個數是兩種主張,所以分開存:`known_op` 來自原生位址表,
        # `doc_op_name` 來自 repo 文件裡可逐字定位的反組譯記載(見 DOC_OP_NAMES)。
        d["doc_op_name"] = doc_op_name(t)
        out[hex(t)] = d
    return out


# `dump_chapter_beats.py all` 在現行參考版下產出的 27 個 `op: unknown` 呼叫目標
# (101 個 unknown beats)。91-worklist L212 寫「8 個」——那是高頻的那批,前 8 名
# 佔 64/101;實測相異目標是 27 個。
UNKNOWN_TARGETS = [
    0x24b4d, 0x11df2, 0x37910, 0x24618, 0x33f78, 0x25052, 0x1f882, 0x25089,
    0x361b0, 0x24b14, 0x2189a, 0x17aa9, 0x35b78, 0x11d40, 0x13536, 0x2aedb,
    0x24d22, 0x22253, 0x31529, 0x12cea, 0x1b8e7, 0x24336, 0x24bde, 0x4df4c,
    0x3776e, 0x1c2da, 0x35f10,
]

# --- selftest 的回歸釘子(全部是實測值,不是設計值)---------------------------
# 拿 dump_chapter_beats.PRIM 當正對照:24 個有呼叫端的項目中 19 個相符。
PRIM_AGREE = 19
PRIM_TOTAL_WITH_SITES = 24
# 不相符的 5 個,以及各自的原因。這些**不是**本工具的錯:
#   dialog       PRIM 註解自己就寫「9 個 push,只取最近 2 個」= 刻意的投影
#   load_res     PRIM 註解:「參數個數未逐一核對」
#   play_sfx     同上
#   layout_units PRIM 記 0,與「依 call-site 陣列佈置」的描述不合
#   loadch       PRIM 記 0,但 3/3 呼叫端一致為 add esp,4
PRIM_DIVERGENT = {
    0x1088d: (0, 1), 0x111ba: (0, 3), 0x15f84: (2, 9),
    0x233c6: (0, 11), 0x25a96: (1, 3),
}
# 兩個訊號在 27 個未知目標上一致 26 個;唯一的例外是 0x24618,
# 而 doc56 的獨立反組譯記載它有 4 個參數,與 cleanup 訊號相同、與 push 訊號不同。
TWO_SIGNAL_AGREE = 26
SIGNAL_EXCEPTION = 0x24618
DOC56_ARGC_24618 = 4
# 合併清理風險只出現在這兩個目標身上(CFG 走訪的呼叫端母體)。
MERGED_RISK = {0x1f882, 0x25089}
# 只有一個呼叫端、因而「一致度 100%」恆真的目標(CFG 走訪的呼叫端母體)。
SINGLE_SITE = {0x1b8e7, 0x24336, 0x24bde, 0x1c2da, 0x35f10}
# 換成位元組掃描的呼叫端後,0x1b8e7 / 0x1c2da / 0x35f10 拿到足夠的呼叫端而升級;
# 0x24336 / 0x24bde 全 image 就真的只有一個呼叫端,仍然不構成證據。
# 反向也有一筆:0x22253 呼叫端 3 -> 5 後一致度掉到 1.0 以下,誠實降級成 LIKELY
# (參數個數仍是 5,與文件簽名相同)——證據變多不一定讓信心變高,這是對的。
WIDE_UPGRADES = 3

# --- 第三方核對:repo 文件裡**獨立記載過的呼叫簽名** -------------------------
# 這一組不是本工具算出來的,是別人在別的時間用反編譯/反組譯寫進文件的參數列表。
# 沒有這一組,前面兩個訊號一致只證明它們「一起說同一件事」——而它們可能因為
# 同一個錯誤假設(例如我對 cdecl 的認定)一起錯。有了它,一致才變成證據。
DOC_SIGNATURES = {
    0x22253: (5, "`0x22253(unitSlot,newX,newY,visualX,visualY)`"),
    0x1c2da: (4, "`0x1c2da(a1, subcommand, count, targetBytes)`"),
    0x24618: (4, "doc56:arg1/arg2 餵 tile geometry、第三個起始半徑、第四個每 pass 遞增"),
    0x11d40: (3, "`0x11d40(0, 0xff, esi*6)`"),
    0x11df2: (3, "`0x11df2(0,255,delta)`"),
    0x35b78: (3, "`0x35b78(5,7,0)`"),
    0x25052: (2, "`0x25052(start,delay_ms)`"),
    0x12cea: (2, "`0x12cea(slot,x)`"),
    # doc99 L4171 `FUN_0002aedb(char_idx, item_id)` 註明「decompile確認」,
    # doc58 L3158 的 thunk `0x31860(unit,item)` 也是兩個參數。
    # doc58 L2291 寫成 `0x2aedb(index)` 是**不精確的簡寫**——本工具推得 2,
    # 3/3 呼叫端一致為 `add esp,8`,與 decompile 簽名相同。這一筆是反過來
    # 由本工具指出文件有誤,所以特別留著。
    0x2aedb: (2, "doc99 `FUN_0002aedb(char_idx, item_id)`(decompile 確認)"),
    0x24b4d: (1, "`0x24b4d(N)`"),
    0x24b14: (1, "`0x24b14(0x64)`"),
    0x17aa9: (1, "`0x17aa9(1)`"),
    0x24d22: (1, "`0x24d22(arg)`"),
    0x24bde: (1, "`0x24bde(18)`"),
    0x4df4c: (1, "verified_addresses:精確呼叫位址 `PUSH [0x53a51]; CALL 0x4df4c`"),
}

# --- op 名稱:只收「文件已反組譯、且引文可逐字定位」的 ---------------------------
# 背景:91-worklist 這一項自己寫著「**填錯比留 unknown 更糟**」,所以名稱不能用推的。
# 一度以為 doc50 §3.1(「疑是」)與 doc31 §9.6(「已完整反組譯」)對 `0x24b4d` 的
# 信心度互相矛盾、需要先收斂。實際查證**沒有矛盾**:兩者對可觀察量完全一致(同樣的
# `0x11eee` + `0x11cac` + present 迴圈 + delay、同樣 15 個呼叫點),doc31 只是把「疑」
# 拿掉,並且**修正了語意標籤**——不是漸現(reveal),是兩張緩衝區來回閃爍 N 次。
#
# 入場規則(見 `anchor_lines`):引文必須逐字存在,**而且**該位址要寫在引文的
# ±ANCHOR_WINDOW 行內。第二個條件不是裝飾:建這張表時先用純鄰近掃描得到「22/27 有
# 完整反組譯」,查證後發現 `91-worklist.md` L213 是本工具自己那條列了一堆位址的摘要行,
# 被算成六個位址各自的證據;`0x31529`(其實在講鄰近的 `FUN_00031266`)與 `0x25089`
# (一張排除假說的表格)也都是假陽性。名稱與參數個數是兩種不同的主張,所以這張表
# **不參與 args 切割**——切割仍然只採信 CONFIRMED(見 dump_chapter_beats._confirmed_argc)。
DOCS = ROOT / "docs" / "knowledge-base"
ANCHOR_WINDOW = 3

# 位址 -> (op 名稱, 文件記載的參數個數, 文件檔名, 必須逐字出現的引文)
DOC_OP_NAMES = {
    0x37910: ("memset", 3, "58-remake-live-verification-log.md",
              "FUN_00037910(dest,byteVal,n)"),
    0x2aedb: ("find_item_slot", 2, "99-chapter-sweep-results.md",
              "FUN_0002aedb(char_idx, item_id)"),
    0x24b14: ("party_has_item", 1, "99-chapter-sweep-results.md",
              "FUN_00024b14(item_id)"),
    0x1b8e7: ("remove_inventory_slot", 2, "56-fd2-remake-sdd.md",
              "sub_1B8E7(int unit, int slot)"),
    0x12cea: ("camera_step_to", 2, "58-remake-live-verification-log.md",
              "0x12cea(param_1, param_2)"),
    0x22253: ("unit_present", 5, "35-battle-animation-rendering.md",
              "(unitSlot,newX,newY,visualX,visualY)"),
    0x24b4d: ("buffer_flicker", 1, "31-map-unit-sprites-fdicon.md",
              "indexed double-buffer visual adapter"),
    0x24d22: ("reveal_wipe", 1, "58-remake-live-verification-log.md",
              "設定/觸發」雙模式函式"),
    0x2189a: ("sprite_walk_on", 3, "58-remake-live-verification-log.md",
              "10-iteration 的 sprite walk-on 動畫迴圈"),
    0x11d40: ("palette_brightness_ramp", 3, "35-battle-animation-rendering.md",
              "figure/台座的色盤淡入(brightness ramp 0→48)"),
    0x11df2: ("palette_delta_ramp", 3, "50-cutscene-script-system-design.md",
              "是獨立的調色盤/淡變數值計算函式"),
    # 這兩筆是 2026-09-09 續六補的,補的理由是我自己前一輪的判準不一致:
    # 當初以「判定 WEAK/LIKELY」為由排除它們,但 WEAK/LIKELY 講的是**參數個數**的
    # 信心,而本表的設計明說名稱與參數個數互不帶動。文件對這兩個位址的**語意**都
    # 已經反組譯到底,排除它們沒有道理。
    #
    # 0x24bde 的名稱刻意與 PRIM 的 0x33499 相同——doc25 明說它是「同一個 roster_has(id)
    # 原語的第二個獨立編譯實例」,本體逐位元組相同,只是 Watcom 序頭讓 Ghidra 漏判了
    # function 邊界。撞名在這裡是**正確答案**,所以撞名規則改成「撞名時引文必須自己
    # 提到那個名字」,而不是一律禁止。
    0x24bde: ("roster_has", 1, "25-battle-event-system.md",
              "同一個`roster_has(id)`原語的第二個獨立編譯實例"),
    0x24618: ("palette_transition_loop", 4, "58-remake-live-verification-log.md",
              "反編譯確認函式本體正是已證實的 9-frame/0x40-step palette 迴圈"),
    # 2026-09-09 續:先前判定這幾個「全庫查無命名段落」——**那是搜尋方式的問題**,
    # 我當時要求位址與確認詞出現在**同一行**,而文件是在表格、標題、敘述裡命名的。
    # 這是本 session 第四次「查無資料」的結論來自不完整的搜尋。
    #
    # 文件沒有寫出參數個數的,`doc_argc` 記 None:名稱由文件負責,參數個數由本工具的
    # 雙訊號推導負責(規則是此時必須 CONFIRMED)。兩種主張分開,與整張表的設計一致。
    0x17aa9: ("wait_ticks", 1, "23-boot-title-and-scenario-flow.md",
              "是 tick 計數忙等"),
    0x25052: ("palette_ramp_down", 2, "56-fd2-remake-sdd.md",
              "is an independently editable palette-ramp primitive"),
    0x13536: ("clear_acted_flags", None, "56-fd2-remake-sdd.md",
              "runtime records 執行 raw `+5 &= 0x7F`"),
    0x31529: ("scene_charcard_orchestrator", None, "35-battle-animation-rendering.md",
              "一個「換場+角色卡」的 orchestrator"),
    # doc25 §11 明寫這是**訂正**先前 §10.2/§10.4.2/§10.4.3 的讀法,3 個引數與推導相符。
    # 名稱刻意不叫 `grant_item`(PRIM 的 0x1c220 是 1 引數的另一個函式)。
    0x35b78: ("give_item_to_group", 3, "25-battle-event-system.md",
              "func_0x35B78(group_id, item_id, count?)"),
    # 這一筆是**先被本規則擋下、回頭查證後才成立**的:doc31 §9.5 寫「`0x33f78` wrapper
    # 的 5 引數」,而兩個訊號都得出 3(9/10 個呼叫端 `add esp,12`)。反組譯本體發現那個
    # 5 屬於它呼叫的 `0x22253`——wrapper 收 3 個引數,先用兩個呼叫 `0x12cea` 做鏡頭步進,
    # 再湊 5 個 push 交給 `0x22253`。訂正寫在 doc31 §10,名稱錨在那一節。
    0x33f78: ("camera_step_then_present", 3, "31-map-unit-sprites-fdicon.md",
              "這個 wrapper 收 3 個引數,先用其中兩個呼叫 `0x12cea` 做鏡頭步進"),
}
# 刻意留在 unknown 的:`0x33f78`/`0x35f10`/`0x361b0`/`0x13536` 全庫查無任何命名段落;
# `0x31529`/`0x25089`/`0x3776e` 只有假陽性或旁證(`0x3776e` 的鄰居 `0x3771c` 才是被
# 反組譯成 memmove 的那個,不是它本身);`0x24336`/`0x24bde` 全 image 只有一個呼叫端。


def anchor_lines(doc: str, quote: str, addr: int) -> list[int]:
    """引文逐字出現、**且**該位址就寫在 ±ANCHOR_WINDOW 行內的行號(1-based)。

    只比對引文會被「同一份文件別處提到過這串字」騙(實測 doc99 的
    `FUN_0002aedb(char_idx, item_id)` 出現兩次,只有一處旁邊有位址)。
    """
    lines = (DOCS / doc).read_text(encoding="utf-8").split("\n")
    # 位址比對**不分大小寫**:文件裡 `0x35B78` 與 `0x35b78` 兩種寫法都有(doc25 同一節
    # 就混用),分大小寫會讓錨點在正確的段落上落空。引文仍然逐字比對,不放寬。
    hexa = hex(addr).lower()
    out = []
    for i, line in enumerate(lines):
        if quote not in line:
            continue
        lo, hi = max(0, i - ANCHOR_WINDOW), min(len(lines), i + ANCHOR_WINDOW + 1)
        if any(hexa in lines[j].lower() for j in range(lo, hi)):
            out.append(i + 1)
    return out


def collision_ok(name: str, quote: str, prim_names: set[str]) -> bool:
    """與 PRIM 撞名時,引文必須自己說出那個名字(否則就是認錯函式)。

    同一個原語被編譯成兩份是真的會發生:doc25 記載 `0x24bde` 是 `0x33499` 的
    `roster_has(id)` 第二個獨立編譯實例,本體逐位元組相同。所以撞名不能一律禁止,
    但也不能一律放行——放行條件必須寫在引文裡。
    """
    return name not in prim_names or name in quote


def doc_op_name(target: int) -> str | None:
    """該位址的 op 名稱,錨點當場複驗過才回傳(文件被改掉就自動失效)。"""
    entry = DOC_OP_NAMES.get(target)
    if entry is None:
        return None
    name, _argc, doc, quote = entry
    try:
        return name if anchor_lines(doc, quote, target) else None
    except OSError:
        return None


def selftest() -> int:
    fails = []
    exe = str(DEFAULT_EXE)
    if not os.path.exists(exe):
        print(f"缺少 {exe},無法自我驗證", file=sys.stderr)
        return 1
    import dump_chapter_beats as DC
    cg, order = build_graph(exe)
    sites = collect(cg, order)

    print("(1) 正向控制:對照 dump_chapter_beats.PRIM 已記錄的參數個數")
    agree, divergent = 0, {}
    for addr, (name, want) in DC.PRIM.items():
        d = derive(sites.get(addr, []))
        if d["argc"] is None:
            continue
        if d["argc"] == want:
            agree += 1
        else:
            divergent[addr] = (want, d["argc"])
    ok1 = agree == PRIM_AGREE and divergent == PRIM_DIVERGENT
    print(f"    {'PASS' if ok1 else 'FAIL'}: 相符 {agree}/{PRIM_TOTAL_WITH_SITES}"
          f"(應 {PRIM_AGREE}),不符的 {len(divergent)} 個"
          f"{'與記錄一致' if divergent == PRIM_DIVERGENT else ':' + str({hex(k): v for k, v in divergent.items()})}")
    if not ok1:
        fails.append(f"PRIM 對照漂移:相符 {agree}、不符 {({hex(k): v for k, v in divergent.items()})}")

    print("\n(2) 兩個獨立訊號(清理 vs push)必須在絕大多數目標上一致")
    same, diff = 0, []
    for t in UNKNOWN_TARGETS:
        d = derive(sites.get(t, []))
        if d["argc"] == d["argc_from_pushes"]:
            same += 1
        else:
            diff.append(t)
    ok2 = same == TWO_SIGNAL_AGREE and diff == [SIGNAL_EXCEPTION]
    print(f"    {'PASS' if ok2 else 'FAIL'}: 一致 {same}/27(應 {TWO_SIGNAL_AGREE}),"
          f"例外 {[hex(x) for x in diff]}(應 [{hex(SIGNAL_EXCEPTION)}])")
    if not ok2:
        fails.append(f"雙訊號一致度漂移:{same}、例外 {[hex(x) for x in diff]}")

    print("\n(3) 第三條獨立證據:doc56 反組譯記載 0x24618 有 4 個參數")
    # 這是唯一雙訊號打架的目標,所以必須有一個**不是**這兩個訊號的來源來裁決。
    d618 = derive(sites.get(SIGNAL_EXCEPTION, []))
    ok3 = (d618["argc"] == DOC56_ARGC_24618
           and d618["argc_from_pushes"] != DOC56_ARGC_24618)
    print(f"    {'PASS' if ok3 else 'FAIL'}: 清理訊號={d618['argc']}(與 doc56 相同)、"
          f"push 訊號={d618['argc_from_pushes']}(低估,參數為行內計算)")
    if not ok3:
        fails.append(f"0x24618 裁決不成立:{d618['argc']}/{d618['argc_from_pushes']}")

    print("\n(4) 已知失效模式必須被標出來,而不是混在一起報")
    merged = {t for t in UNKNOWN_TARGETS
              if "merged_cleanup_risk" in derive(sites.get(t, []))["flags"]}
    single = {t for t in UNKNOWN_TARGETS
              if "single_callsite" in derive(sites.get(t, []))["flags"]}
    ok4 = merged == MERGED_RISK and single == SINGLE_SITE
    print(f"    {'PASS' if ok4 else 'FAIL'}: 合併清理風險 {sorted(hex(x) for x in merged)}、"
          f"單一呼叫端 {len(single)} 個")
    if not ok4:
        fails.append(f"失效模式標記漂移:merged={sorted(hex(x) for x in merged)}、"
                     f"single={sorted(hex(x) for x in single)}")

    print("\n(5) 多數決必須把「沒有清理」算進去(palfade 的離群值回歸)")
    # 0x1f525 的 9 個呼叫端:8 個沒有清理、1 個 add esp,48。先濾掉 None 會得 12。
    d525 = derive(sites.get(0x1f525, []))
    dist = d525["cleanup_distribution"]
    ok5 = (d525["argc"] == 0 and dist.get("48") == 1 and dist.get("None") == 8)
    print(f"    {'PASS' if ok5 else 'FAIL'}: palfade argc={d525['argc']}(應 0),"
          f"分布 {dist}")
    if not ok5:
        fails.append(f"離群值仍被採信:{d525['argc']} / {dist}")

    print("\n(6) 非平凡性 + 負向控制")
    argcs = {derive(sites.get(t, []))["argc"] for t in UNKNOWN_TARGETS}
    bogus = derive(sites.get(0xDEAD, []))
    ok6 = len(argcs) >= 5 and bogus["verdict"] == "NO_CALLSITE" and bogus["argc"] is None
    print(f"    {'PASS' if ok6 else 'FAIL'}: 27 個目標得出 {len(argcs)} 種不同的參數個數 "
          f"{sorted(argcs)}、不存在的位址 -> {bogus['verdict']}")
    if not ok6:
        fails.append(f"非平凡性或負向控制不成立:{sorted(argcs)} / {bogus['verdict']}")

    print("\n(7) 兩種呼叫端發現機制:CFG 可達走訪 vs 位元組掃描,答案必須相同")
    # 這一題問的不是「多找到幾個呼叫端」,而是**多找到的證據會不會改變答案**。
    # 兩種機制對「哪些位址是呼叫端」的認定完全獨立:一個從 chapter handler 跳表
    # 走可達路徑,一個直接在位元組流裡找 E8 rel32。實測呼叫端數量差到 3~6 倍
    # (0x3776e 58->205、0x17aa9 35->96、0x4df4c 3->32),而 27 個目標的參數個數
    # 沒有一個改變。這比「兩個訊號一致」強,因為連取樣母體都換了。
    flips, upgraded, fewer = [], 0, []
    for t in UNKNOWN_TARGETS:
        dn = derive(sites.get(t, []))
        dw = derive(collect_wide(cg, t))
        if dn["argc"] != dw["argc"]:
            flips.append((hex(t), dn["argc"], dw["argc"]))
        if dw["sites"] < dn["sites"]:
            fewer.append(hex(t))
        if dn["verdict"] != "CONFIRMED" and dw["verdict"] == "CONFIRMED":
            upgraded += 1
    ok7 = not flips and not fewer and upgraded == WIDE_UPGRADES
    print(f"    {'PASS' if ok7 else 'FAIL'}: 27 個目標的參數個數改變 {len(flips)} 個"
          f"(應 0){'、' + str(flips) if flips else ''}、"
          f"WEAK->CONFIRMED 升級 {upgraded} 個(應 {WIDE_UPGRADES})"
          f"{'、呼叫端反而變少的 ' + str(fewer) if fewer else ''}")
    if not ok7:
        fails.append(f"兩種發現機制不一致:flips={flips}、upgraded={upgraded}、fewer={fewer}")

    print("\n(8) 函式入口數回歸:自帶掃描必須與 verify_findings 的判準得出同一組")
    # 位元組來源換掉了(不再走 Ghidra 的 22.3 秒),但判準沒換。入口數釘成常數
    # 當回歸;要對活的兄弟工具做完整逐一比對請用 --verify-entries。
    _, ents = _scan(cg)
    has_31529 = 0x31529 in ents
    ok_e = len(ents) == FUNCTION_ENTRIES and has_31529
    print(f"    {'PASS' if ok_e else 'FAIL'}: 入口 {len(ents)} 個(應 {FUNCTION_ENTRIES})、"
          f"含 doc35 記載序頭為 `PUSH 0x80; CALL 0x3702f` 的 0x31529={has_31529}")
    if not ok_e:
        fails.append(f"函式入口集合漂移:{len(ents)} 個、0x31529={has_31529}")

    print("\n(9) 第三方核對:文件裡獨立記載過的呼叫簽名必須逐一相符")
    # 這是唯一能區分「兩個訊號都對」與「兩個訊號一起錯」的檢查。
    sig_bad = []
    for addr, (want, where) in sorted(DOC_SIGNATURES.items()):
        got = derive(sites.get(addr, []))["argc"]
        if got != want:
            sig_bad.append(f"{addr:#07x}: 文件 {want}、推得 {got}({where})")
    spread = {w for w, _ in DOC_SIGNATURES.values()}
    ok8 = not sig_bad and len(spread) >= 4
    print(f"    {'PASS' if ok8 else 'FAIL'}: {len(DOC_SIGNATURES)} 個有文件簽名的目標"
          + (f"全部相符,參數個數跨 {sorted(spread)}" if ok8 else f",不符 {sig_bad}"))
    if not ok8:
        fails.append(f"與文件簽名不符:{sig_bad}")

    print("\n(10) op 名稱:每一筆的引文都要能定位,且文件記載的參數個數要與推導相符")
    name_bad = []
    for addr, (name, want, doc, quote) in sorted(DOC_OP_NAMES.items()):
        where = anchor_lines(doc, quote, addr)
        if not where:
            name_bad.append(f"{addr:#07x} {name}: 引文在 {doc} 找不到(或位址不在 ±{ANCHOR_WINDOW} 行內)")
            continue
        d = derive(collect_wide(cg, addr))
        if want is None:
            # 文件只給名稱、沒給簽名:參數個數這一半就必須由本工具自己站得住,
            # 也就是雙訊號一致到 CONFIRMED。否則兩半都沒有支撐。
            if d["verdict"] != "CONFIRMED":
                name_bad.append(f"{addr:#07x} {name}: 文件沒給簽名,而推導判定是 "
                                f"{d['verdict']}(需 CONFIRMED)")
        elif d["argc"] != want:
            name_bad.append(f"{addr:#07x} {name}: 文件 {want}、推得 {d['argc']}({doc}:{where[0]})")
    # 非平凡性:名稱不得在本表內重複。與 PRIM 撞名則要看情況——同一個原語被編譯成
    # 兩份是真的會發生(0x24bde vs 0x33499),所以規則是**撞名時引文必須自己提到那個
    # 名字**;引文沒提到就是認錯函式,照樣擋下。
    names = [n for n, _, _, _ in DOC_OP_NAMES.values()]
    prim_names = {n for n, _ in DC.PRIM.values()}
    dup = sorted(n for n in set(names) if names.count(n) > 1)
    if dup:
        name_bad.append(f"名稱在本表內重複:{dup}")
    for addr, (name, _w, _d, quote) in sorted(DOC_OP_NAMES.items()):
        if not collision_ok(name, quote, prim_names):
            name_bad.append(f"{addr:#07x} {name}: 與 PRIM 撞名,但引文沒有說它是同一個原語")
    ok10 = not name_bad and len(DOC_OP_NAMES) >= 10
    print(f"    {'PASS' if ok10 else 'FAIL'}: {len(DOC_OP_NAMES)} 筆 op 名稱"
          + ("全部定位成功且參數個數相符" if ok10 else f",問題 {name_bad}"))
    if not ok10:
        fails.append(f"op 名稱錨點失效:{name_bad}")

    print("\n(10b) 負向控制:錯配的引文與位址必須被同一條規則擋下")
    # 沒有這一題,第 (10) 題對一個「永遠回傳有結果」的 anchor_lines 也會通過。
    ctrl = []
    # (a) 引文對、位址換成另一個目標 -> 必須落空(否則鄰近條件是裝飾)。
    if anchor_lines("99-chapter-sweep-results.md", "FUN_0002aedb(char_idx, item_id)", 0x11d40):
        ctrl.append("換位址仍然定位成功")
    # (b) 引文不存在 -> 必須落空。
    if anchor_lines("58-remake-live-verification-log.md", "這串字不存在於任何文件", 0x37910):
        ctrl.append("不存在的引文仍然定位成功")
    # (c) 真實的假陽性回歸:doc99 那句話出現兩次,只有一處旁邊有 0x2aedb。
    #     這是建表時實際踩到的那一類——純比對引文會多收一處。
    body = (DOCS / "99-chapter-sweep-results.md").read_text(encoding="utf-8")
    raw_hits = sum(1 for l in body.split("\n") if "FUN_0002aedb(char_idx, item_id)" in l)
    kept = anchor_lines("99-chapter-sweep-results.md", "FUN_0002aedb(char_idx, item_id)", 0x2aedb)
    if not (raw_hits > len(kept) >= 1):
        ctrl.append(f"假陽性回歸失效:純比對 {raw_hits} 處、加鄰近後 {len(kept)} 處")
    # (d) 撞名規則的兩極,兩邊都走同一個 collision_ok:0x24bde 用它真正的引文必須
    #     **放行**(引文自己說了「同一個 roster_has(id) 原語的第二個獨立編譯實例」),
    #     同一個名字換成本表裡另一段沒提到它的真實引文則必須**擋下**。只驗放行那一邊,
    #     一個永遠回 True 的實作也會通過。
    prim_now = {n for n, _ in DC.PRIM.values()}
    _n, _w, _d, q_bde = DOC_OP_NAMES[0x24bde]
    other_quote = DOC_OP_NAMES[0x24618][3]
    if not collision_ok(_n, q_bde, prim_now):
        ctrl.append("0x24bde 用它真正的引文卻被擋下")
    if collision_ok(_n, other_quote, prim_now):
        ctrl.append("換成沒提到 roster_has 的引文仍然放行 —— 撞名規則是裝飾")
    ok10b = not ctrl
    print(f"    {'PASS' if ok10b else 'FAIL'}: 四個控制"
          + (f"全部如預期(假陽性 {raw_hits} -> {len(kept)})" if ok10b else f",問題 {ctrl}"))
    if not ok10b:
        fails.append(f"op 名稱負向控制失效:{ctrl}")

    print("\n(11) 已登錄的產物必須與本工具現在會產出的內容一致(把驗證往前搬)")
    # 2026-09-09 實際踩到:加了兩個 op 名稱、卻忘了重生 native_argcounts.json,
    # 一直到 10 軸驗證的 artifacts 軸(整輪 30 分鐘)才報出漂移。同一件事在這裡
    # 2 秒就能知道。這不是取代 verify_generated_artifacts,是把它的回饋提前。
    art = ROOT / "docs" / "data" / "native_argcounts.json"
    if not art.exists():
        ok11, detail = False, "產物不存在"
    else:
        want = json.loads(art.read_text(encoding="utf-8"))
        got = report(exe, only_unknown=True, wide=True)
        diff = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
        ok11 = not diff
        detail = "相同" if ok11 else f"漂移 {diff[:4]} —— 請重跑 --wide --json 重生"
    print(f"    {'PASS' if ok11 else 'FAIL'}: {art.name} {detail}")
    if not ok11:
        fails.append(f"已登錄產物漂移:{detail}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(PRIM 正向對照 + 雙訊號交叉驗證 + doc56 第三方裁決 "
          "+ 兩種已知失效模式的標記 + 離群值回歸 + 非平凡性與負向控制 "
          "+ 兩種呼叫端發現機制的一致性 + 函式入口數回歸 + 15 個文件簽名的第三方核對 "
          "+ 19 個 op 名稱的錨點複驗與四個負向控制 + 已登錄產物的即時漂移檢查)。")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe", nargs="?", help="FD2.EXE(不給就用 repo 內的 org_game 副本)")
    ap.add_argument("--all", action="store_true", help="報告全部被呼叫的目標,不只未收錄的 27 個")
    ap.add_argument("--wide", action="store_true",
                    help="改用全 image 位元組掃描找呼叫端(涵蓋 chapter handler 圖之外的呼叫端)")
    ap.add_argument("--json", help="輸出 JSON 到這個路徑")
    ap.add_argument("--verify-entries", action="store_true",
                    help="對 verify_findings.function_entries() 做完整逐一比對"
                         "(走 Ghidra,約 22 秒;平時由 selftest 的入口數回歸代替)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv[1:])
    if a.selftest:
        return selftest()
    exe = a.exe or str(DEFAULT_EXE)
    if a.verify_entries:
        import verify_findings as VF
        from callgraph_le import CG
        _, mine = _scan(CG(exe))
        ref = frozenset(VF.function_entries())
        same = mine == ref
        print(f"自帶掃描 {len(mine)} 個入口、verify_findings {len(ref)} 個;"
              f"{'逐一相同' if same else '不同:' + str(sorted(mine ^ ref)[:10])}")
        return 0 if same else 1
    if not os.path.exists(exe):
        print(f"找不到 {exe};請給 EXE 路徑或用 --selftest。", file=sys.stderr)
        return 1
    res = report(exe, only_unknown=not a.all, wide=a.wide)
    order = sorted(res.items(), key=lambda kv: (kv[1]["verdict"] != "CONFIRMED", kv[0]))
    for h, d in order:
        op = f" [{d['known_op']}]" if d.get("known_op") else ""
        print(f"{h}{op:>28}  args={d['argc']}  {d['verdict']:9s} "
              f"呼叫端={d['sites']:3d} 一致度={d['agreement']:.0%} "
              f"push={d.get('argc_from_pushes')} {','.join(d['flags']) or '-'}")
    n_conf = sum(1 for _, d in res.items() if d["verdict"] == "CONFIRMED")
    print(f"\n共 {len(res)} 個目標:CONFIRMED {n_conf} / 其餘 {len(res) - n_conf}"
          f"(WEAK 代表單一呼叫端或有合併清理風險,不是證據)")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        print(f"-> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
