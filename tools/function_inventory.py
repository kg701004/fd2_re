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
* `ail`           `docs/data/ail_entry_points.json` 的 104 個進入點(多半經指標表呼叫,沒有直接 CALL;AIL_startup 未解析)
* `thunk_target`  某個入口的第一個位元組是 `E9`,它跳去的位址(`delay` 的本體 `0x3e01d` 只能這樣抵達)
* `fnptr`         函式指標的目標(2026-10-06,見下)
* `eip`           LE 標頭的程式進入點(`le_entry_point`;參考版 0x3ccb4 = `_cstart_`,2026-10-07 前漏列)
* `island`        走不到的死函式(`island_entries`,2026-10-07,見下)

* `call_reached`  對 `call` 的佐證(2026-10-07):唯一的呼叫端是「從 strong 入口可達反組譯走到的 `call` 指令」
                  (`confirm_reached_calls`,確認的再當種子到不動點;種子不含 weak 自己,避免循環論證;
                  本輪走到的 `jmp [reg*4 + 表]` 的 case 也當種子,`jmp_table_cases`)

`grade`:有 prologue / ail / thunk_target / fnptr / eip / call_reached,或被 CALL 兩次以上 = `strong`;只被 CALL 一次而呼叫端
沒走到、或只有 island = `weak`(E8 位元組掃描會接受資料位元組的偶然命中;island 只靠解碼,沒有執行路徑或引用佐證)。

`island`:函式庫連進來但沒人呼叫的函式(例 `_DoINTR_` 0x468cb)沒有 CALL、序頭、fixup,上面的訊號全部看不到。
以函式指標不動點最後一輪的可達指令為「走得到」:可達指令的無條件結尾之後若接著一段走不到、而且一路延伸到下一個入口的
位元組(中間夾著可達指令的是函式內部走不到的程式碼,只記 `_meta.island_interior_gaps`),就從段首依序剝:跳過對齊填充
(`00`/`90`/`cc`、`lea r, [r]`、`mov r, r`),`implausible` 為 None、不是 fixup 的來源或目標、`local_body` 解得出不重疊
且有結尾的本體才收;第一個剝不出來的就停。fixup 目標不收:是函式的話 `fnptr` 早收了,沒收的是被反證的資料指標或計算式
跳躍的落點(`int386xa` 的 `int N ; ret` 樁表)。

`fnptr`(`pointer_refs` -> `pointer_evidence` -> `fnptr_targets`):只經函式指標抵達、又沒有序頭的函式
(事件表裡 `push 0x28 ; jmp` 的共用本體入口、FLI 解碼表、遮罩繪製的二維表、中斷處理常式、CRT 初始化表)
不會有直接 CALL。從入口做可達反組譯,看每條可達指令裡的 fixup 怎麼被用:
  正向  `call [表(+reg*k)]` 的表內每格(表可夾值為 0 的空槽,遇到別的表頭、入口、程式碼起點就停)、
        `push`/`mov` 的立即值、不帶暫存器的 `lea`、obj1 以外物件裡指向 obj1 的槽(不屬於任何 `jmp` 表)
  反向  `jmp [表+reg*k]` 的表內每格(case 標籤)、其他記憶體運算元(資料)、取址後幾條指令內被當記憶體
        base/index 解參考(資料指標,例:數學函式庫的係數表 `lea esi, [..]` 後讀 `cs:[esi + 8]`)
有正向、沒有反向,而且本體解碼得通(`implausible`:不在可達指令中間、不是字串、線性解碼到 `ret`/`jmp` 之前
沒有解不出的位元組、`00 00`、跳出 obj1 的直接分支)才算。新入口與 `jmp` 表的 case 標籤再當可達反組譯的種子
(case 標籤只用來走進 case 本體,不當入口),反覆到不動點。

呼叫端先經**可達反組譯**過濾(`contradicted_sites`,2026-10-06):從序頭入口、AIL 進入點、指向 obj1 的 fixup
目標遞迴反組譯(`callgraph_le.CG.build`),呼叫端落在某條可達指令內部的剔除。實測剔除 7 個,全部人工判讀確認
是別的指令裡的 `E8` 位元組(例:`mov dword ptr [esp + 0xe8], 0` 的位移),入口 1102 -> 1095;剔除清單記在
`_meta.call_sites_dropped`。沒走到的呼叫端不判,所以仍可能留有假入口,只是沒有反證。

每個入口的機械事實:`callers`(直接呼叫端數)、`span_upper`(到下一個入口的距離,是大小的**上界**)、
`argc`(`derive_native_argcounts.callee_argc`:本體讀到第幾個參數,判不出來為 null)、
`callees`(本體範圍內直接 CALL 的目標,不含 `__STK`)、`globals`(本體範圍內的 fixup 指向 obj1 之外的位址)。

產物與覆蓋率分開
----------------
`docs/data/function_inventory.json` **只含由 EXE 算得出的東西**(加 AIL 表,它本身也是 EXE 導出的產物),
所以可以逐位元組重生比對。「有沒有名字/文件有沒有記載」會隨文件與命名表變動,不進產物,
由 `--coverage` 現算:名稱來源是 PRIM(`dump_chapter_beats`、`event_handler_dump`)、`DOC_OP_NAMES`、
AIL、`function_names.json`、Watcom 函式庫比對(`watcom_lib_matches.json`,單一符號名才算名稱)、
`verified_addresses.json`、勘誤的 `correct_address`;「文件記載為入口」取
`verify_address_claim_coverage.classify_all()` 的有訊號集合。

結構性自動命名(`--structural`)
------------------------------
有些函式不需要人讀:本體的**結構**就是它的描述。只用本清單的機械事實加上**有真名**的命名表
(PRIM、`DOC_OP_NAMES`、AIL、`function_names.json`、Watcom 函式庫比對;`verified_addresses`/勘誤只有位址
沒有名稱字串,不算)。依序判定,先中先贏:
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

人讀出來的名稱(`docs/data/function_names.json`,`--check-names`)
------------------------------------------------------------
機械方法處理不了的函式要人讀反編譯碼。讀出來的名稱登錄在 `function_names.json`(手動維護,本工具只讀不寫),
每筆必須帶**機器可驗證的證據**:`evidence` 是一串 `{"at": 位址, "insn": "助記符 運算元"}`,`--check-names` 會在該位址
實際反組譯、逐字比對,並要求位址落在該函式的 `[addr, addr+span_upper)` 內。名稱因此錨在位元組上,不是錨在散文上:
EXE 換版或位址抄錯,檢查就會失敗。其他規則:`addr` 必須是本清單的入口、名稱 snake_case 且不重複、不得與其他命名表
(PRIM、`DOC_OP_NAMES`、AIL)撞名或重複命名同一位址、`summary` 不得空、`confidence` 只能是 `static_re` 或 `verified_dynamic`。
登錄的名稱會進 `load_names()`,所以也會餵給結構性命名(新名字可能讓更多 wrapper 解得出來 —— 登錄後要重生
`function_structural_names.json`)。`--card ADDR` 印出一個入口的機械事實、呼叫端與本體反組譯,給人讀的時候用。

實機執行位址:`live_exec_addresses.json`(`verify_dead_functions_vs_traces.py --export` 由原版 DOSBox-X 軌跡合併)。
`--selftest` 用它驗「weak 入口與摘要帶『(死函式:』的入口,本體指令沒有一條實機執行過」(續九十七);
`--card` 標出入口與本體有沒有執行紀錄。沒有紀錄只代表過去擷取的場景沒走到,不是沒用到。

誠實邊界
--------
* 函式指標只認 fixup:執行期算出來的位址(`push`+`ret` 跳進中斷樁表、只有表頭被引用的樁陣列)看不到。
  2026-10-06 對參考版 EXE 逐類手動核對過(doc98 續七十九):樁表位置上在 0x46915 的 span 裡(執行上與活的
  int386x_dispatch 0x468a7 共用,續九十六),沒有 fixup 的間接呼叫的目標
  都已是入口或在 DOS extender 裡 —— 但那是一次性的追蹤,不是本工具的檢查。
  `--ghidra-export` 會列出「Ghidra 有、這裡沒有」的起點供人工判斷。
* `span_upper` 以下一個入口為界,中間若夾資料表或漏掉的函式,會高估。
* `callees`/`globals` 以 `span_upper` 歸屬,因此繼承同樣的高估。

用法
----
    python tools/function_inventory.py docs/data/function_inventory.json   # 重生產物
    python tools/function_inventory.py --coverage                           # 命名/記載覆蓋率
    python tools/function_inventory.py --unnamed [--limit N]                # 無名的 strong 入口,依呼叫端數排序
    python tools/function_inventory.py --structural docs/data/function_structural_names.json
    python tools/function_inventory.py --check-names                        # 驗 function_names.json 的每一筆證據
    python tools/function_inventory.py --card 0x16c57                       # 一個入口的事實卡 + 反組譯
    python tools/function_inventory.py --ghidra-export PATH                 # 與 Ghidra 匯出對照
    python tools/function_inventory.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import contextlib
import copy
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
FUNCTION_NAMES_JSON = ROOT / "docs" / "data" / "function_names.json"
WATCOM_JSON = ROOT / "docs" / "data" / "watcom_lib_matches.json"
LIVE_EXEC_JSON = ROOT / "docs" / "data" / "live_exec_addresses.json"
LIVE_ENTRY_FLOOR = 626      # 入口位址出現在實機軌跡裡的個數(13 份不重複軌跡,續一百零六;續一百零五 12 份 618、續一百零二 6 份 555、續一百 5 份 525、續九十七 4 份 292);重匯出後只能升不能降
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CONFIDENCES = ("static_re", "verified_dynamic")
JMP_REL32 = 0xE9
STRONG_CALLERS = 2          # 只被 CALL 一次的位址可能是資料位元組的偶然命中
WRAPPER_MAX_SPAN = 256      # 再大就不是「只是包裝」,本體有自己的邏輯
LEAF_MAX_SPAN = 64
HEX = re.compile(r"0x[0-9a-fA-F]{4,6}")
GHIDRA_HEADER = re.compile(r"^FUNCTION \d+/\d+: \S+ @ (\S+?)\s+size=(\d+)\s*$", re.M)
# fixup 證據只收這些已知跳表:表基底 -> (格數, 名稱前綴, 說明)。白名單的理由:任何一個 fixup 都「指向某處」,
# 不限定表的話「表 X 第 N 項」可以拿任意資料指標冒充;帶格數是因為 0x51b91 之後的 fixup 一路連到第 179 項,
# 第 90 項起已是游標變數與另一張表(doc25 §20.3)。名稱形如「前綴_N」者必須有同一張表第 N 項的證據。
JUMP_TABLES = {
    0x51B91: (90, "event_handler", "event_id handler 跳表(doc25 L944/§20.3:90 格,event_id 0..89)"),
    0x51D01: (88, "command_handler", "指令/行動 dispatch 表(doc25 §20.3:88 格,0x1541f 與 0x1d479 以 call [eax*4+0x51d01] 分派)"),
    0x524C6: (10, "tai_phase_handler", "TAI.DAT 演出引擎 phase handler 表(doc35 §9.2 定性為戰鬥指令選單的演出:10 格,主控 0x2ff01 與 0x31266 以 "
                                       "call [reg*4+0x524c6] 分派;第 10 格是非 fixup 的 0x20000)"),
}
EVENT_TABLE = 0x51B91
TABLE_NAME_RE = re.compile(r"^(" + "|".join(v[1] for v in JUMP_TABLES.values()) + r")_(\d+)$")


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
    """只經 seeds 抵達的入口(不含 seeds):從 seeds 沿「引用」走得到,且每個引用者(直接呼叫端與取址者
    `takers`)都在 seeds 或這個集合裡。沒有引用者的不算。

    取址者也要算:AIL 以 `mov [eax + 0x20], 0x40c40` 登記的回呼沒有直接呼叫端,只有 AIL 取它的位址;
    不算的話,回呼本體裡的呼叫會讓被呼叫者(`0x364fb`)看起來有非 AIL 的呼叫端。

    用**最大**不動點(從候選全集逐輪剔除有外部引用者的),不是由下往上逐輪加入:互相取址的一對
    (`0x40100` 與 `0x41a40` 互相 `push` 對方的位址)由下往上會兩邊互等、永遠加不進來。
    限定「從 seeds 走得到」,孤立的互相引用(兩段沒人用的程式碼)才不會被當成只經 seeds 抵達。
    """
    refs = direct_callers(entries)
    for e in entries:
        # 自己取自己不必排除:自環不增加可達性,自己也一定在集合裡(最大不動點下無作用,2026-10-06 突變確認)
        for t in e.get("takers", []):
            refs.setdefault(int(e["addr"], 16), set()).add(int(t, 16))
    fwd: dict[int, set[int]] = {}
    for a, rs in refs.items():
        for r in rs:
            fwd.setdefault(r, set()).add(a)
    reach, todo = set(), list(seeds)
    while todo:
        for b in fwd.get(todo.pop(), ()):
            if b not in reach:
                reach.add(b)
                todo.append(b)
    inside = reach - set(seeds)         # 走得到的必有引用者

    while True:
        out = {a for a in inside if not refs[a] <= inside | set(seeds)}
        if not out:
            return inside
        inside -= out


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


def dead_body_hits(dead: set[int], spans_: dict[int, int], insn_at, live: set[int]) -> dict[int, list[int]]:
    """靜態判為沒有執行路徑的入口中,本體指令出現在實機執行位址裡的 -> {入口: 命中位址(排序)}。

    本體 = `body_insns` 的指令起點;沒有乾淨結尾就退回整個 span。不用 span 當本體:span 延伸到下一個入口,
    尾端可能是與活路徑共用的片段(0x46915 的 `int N ; ret` 樁表與 int386x_dispatch 共用,續九十六)。
    """
    hits: dict[int, list[int]] = {}
    for a in sorted(dead):
        body = body_insns(insn_at, a, a + spans_[a])
        addrs = {x for x, *_ in body} if body else set(range(a, a + spans_[a]))
        got = sorted(addrs & live)
        if got:
            hits[a] = got
    return hits


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
            if bodies is not None and a in bodies and bodies[a] is None:
                # 本體在 span 內沒有乾淨收尾:落進下一個入口(2026-10-07:0x4c68c 呼叫 __FLDAC 後不 ret,直接接 0x4c6a5),
                # 行為延伸到 span 外,清單的 callees 不完整,不能說它只是包一層
                continue
            calls = call_args(bodies[a], argc, skip) if bodies and bodies.get(a) else []
            if bodies and bodies.get(a) and not calls:
                # 本體乾淨收尾、裡面沒有任何 call:清單的 callees 來自 span 蓋到的下一段(沒列入口的函式),
                # 不是這個函式在呼叫(2026-10-06:0x37028 的 span 蓋到 __CHK 0x3702f 的 `call __STK`)
                continue
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


def contradicted_sites(call_index: dict[int, tuple[int, ...]], insns: dict[int, int],
                       calls: set[int]) -> frozenset[int]:
    """位元組掃描找到的呼叫端裡,被可達反組譯否定的那些。

    `insns`:可達指令 {起點: 長度};`calls`:其中是直接 CALL 的起點。呼叫端落在某條可達指令的**內部**
    (起點 < 呼叫端 < 起點+長度)就不可能是指令起點;剛好是可達指令起點、卻不是 CALL,也不可能是 CALL。
    可達反組譯沒走到的呼叫端不判(保留),所以這只會剔除**有反證**的命中。

    2026-10-06 實測:`0x2ff01`(spell_cast_scene)的 `mov dword ptr [esp + 0xe8], 0` 位移裡的 `E8 00 00 00 00`
    被當成呼叫 `0x2ff45`,憑空多出一個 weak 入口,還把 spell_cast_scene 的 span 截成 68 bytes。
    """
    starts = sorted(insns)
    bad: set[int] = set()
    for sites in call_index.values():
        for s in sites:
            i = bisect.bisect_right(starts, s) - 1
            if i < 0:
                continue
            st = starts[i]
            if (st == s and s not in calls) or st < s < st + insns[st]:
                bad.add(s)
    return frozenset(bad)


PTR_POSITIVE = frozenset({"calltab", "imm", "lea", "data_slot"})
PTR_NEGATIVE = frozenset({"jmptab", "mem", "deref", "jmpslot"})
TABLE_MAX_SLOTS = 1024      # 稀疏 call 表最多走幾格(實測最大的二維表 0x47988 約 256 格)
DEREF_WINDOW = 12           # 取址後往後看幾條指令(跨條件跳的落空路徑;實測 0x4cd39 的解參考在第 11 條)
PLAUSIBLE_MAX = 4096        # implausible 線性解碼找結尾的最大 bytes
STRING_OPS = ("lods", "movs", "stos", "scas", "cmps")


def table_slots(start: int, fixups: dict[int, int], base: int, hi: int, stops: set[int],
                zero_at=None) -> list[int]:
    """表頭 `start` 起,連續 4-byte 槽中「是 fixup 來源且指向 [base, hi)」的那些槽。

    `zero_at(addr) -> bool` 給了就允許值為 0 的空槽(稀疏的 call 表);遇到第一個不是指標也不是空槽的格停。
    `stops`(別的表頭、入口、程式碼起點)在表頭以外出現就停 —— 相鄰的表不會被併進來
    (`0x51b19` 的表緊接著事件表 `0x51b91`)。
    """
    out: list[int] = []
    a = start
    for _ in range(TABLE_MAX_SLOTS):
        if a != start and a in stops:
            break
        if a in fixups and base <= fixups[a] < hi:
            out.append(a)
        elif not (zero_at and zero_at(a)):
            break
        a += 4
    return out


def ref_role(mn: str, op: str, raw: int) -> tuple[str, bool] | None:
    """一條指令裡、未重定位值為 `raw` 的 fixup 是怎麼被用的:(角色, 方括號裡有沒有暫存器)。

    角色:`imm`(`push`/`mov` 的立即值)、`lea`、`call`/`jmp`(記憶體運算元)、`mem`(其他記憶體運算元)。
    其他指令的立即值(`cmp eax, 位址` 之類)回 None —— 不是正向也不是反向證據。
    以運算元文字判斷:`raw` 出現在方括號內是位移,否則是立即值。
    """
    h = hex(raw)
    for m in MEM.finditer(op):
        if re.search(r"(?<![0-9a-fx])" + h + r"\b", m.group(1)):
            has_reg = bool(re.search(r"\b(?:e?[abcd]x|e?[sd]i|e?[bs]p)\b", m.group(1)))
            if mn == "lea":
                return "lea", has_reg
            if mn in ("call", "jmp"):
                return mn, has_reg
            return "mem", has_reg
    if re.search(r"(?<![0-9a-fx\[])" + h + r"\b(?![^\[]*\])", op) and mn in ("push", "mov"):
        return "imm", False
    return None


def bare(mn: str) -> str:
    """去掉前綴的助記符:capstone 把 `3E` 前綴印成 `notrack jmp`、`F3` 印成 `rep movsd`。"""
    return mn.split()[-1] if mn else mn


def slot_of(op: str) -> str | None:
    """記憶體運算元的方括號部分(去掉 `dword ptr`、段前綴),當作「槽」的識別;沒有回 None。"""
    m = MEM.search(op)
    return m.group(0) if m else None


def pointer_use(reg: str, after: list[tuple[str, str]]) -> tuple[bool, str | None]:
    """取址到 `reg` 之後([(助記符, 運算元)]),被改寫或碰到無條件轉移之前:(有沒有被當記憶體 base/index, 存進哪個槽)。

    條件跳只走落空路徑(繼續往下看);`call`/`jmp`/`ret`/`int` 結束。esi/edi 另外算字串指令的隱含解參考。
    槽 = 第一個 `mov [..], reg` 的方括號(之後由 `jmp_only_slots` 判斷那個槽是不是只被間接 jmp 用)。
    """
    pat = re.compile(r"\b" + reg + r"\b")
    slot = None
    for mn, op in after:
        mn = bare(mn)
        if any(pat.search(m.group(1)) for m in MEM.finditer(op)):
            return True, slot
        if reg in ("esi", "edi") and mn.startswith(STRING_OPS):
            return True, slot
        dst, _, src = op.partition(",")
        if mn == "mov" and src.strip() == reg and slot is None:
            slot = slot_of(dst)
        if dst.strip() == reg and mn not in ("cmp", "test", "push"):
            break
        if mn in ("call", "jmp", "int") or mn.startswith("ret"):
            break
    return False, slot


def jmp_only_slots(ops: list[tuple[str, str]]) -> set[str]:
    """可達指令([(助記符, 運算元)])裡,經 `jmp [槽]` 間接轉移、卻從來沒有 `call [槽]` 的槽。

    取址後存進這種槽的位址是續行點(例:浮點模擬器把捨入常式存進 `[ebp + 0x76]`,只以 `jmp` 抵達),不是函式。
    """
    calls = {slot_of(op) for mn, op in ops if bare(mn) == "call"} - {None}
    jmps = {slot_of(op) for mn, op in ops if bare(mn) == "jmp"} - {None}
    return jmps - calls


def pointer_refs(reached: list[int], insn_at, fixups: dict[int, int], code: bytes, base: int, hi: int
                 ) -> list[tuple[int, int, str, bool, bool, str | None]]:
    """可達指令裡每個 fixup 的用法:[(指令位址, fixup 目標, 角色, 方括號裡有暫存器, 取址後被解參考, 存進的槽)]。

    `insn_at(addr) -> (長度, 助記符, 運算元) | None`。只看來源在 obj1 內的 fixup(未重定位值從 `code` 讀)。
    槽:`mov [槽], 立即值` 的目的地,或取址到暫存器後第一個 `mov [槽], 暫存器`(`pointer_use`)。
    """
    srcs = sorted(s for s in fixups if base <= s < hi)
    out = []
    for st in reached:
        i = bisect.bisect_left(srcs, st)
        if i >= len(srcs) or srcs[i] >= st + 15:
            continue
        got = insn_at(st)
        if got is None:
            continue
        size, mn, op = got
        mn = bare(mn)
        for s in srcs[i:]:
            if s >= st + size:
                break
            raw = int.from_bytes(code[s - base:s - base + 4], "little")
            role = ref_role(mn, op, raw)
            if role is None:
                continue
            deref, slot = False, None
            reg = op.split(",")[0].strip()
            if role[0] in ("imm", "lea") and re.fullmatch(r"e(?:[abcd]x|[sd]i|bp)", reg):
                after, a = [], st + size
                for _ in range(DEREF_WINDOW):
                    g = insn_at(a)
                    if g is None:
                        break
                    after.append((g[1], g[2]))
                    a += g[0]
                deref, slot = pointer_use(reg, after)
            elif role[0] == "imm" and mn == "mov":
                slot = slot_of(reg)
            out.append((st, fixups[s], role[0], role[1], deref, slot))
    return out


def pointer_evidence(refs: list[tuple[int, int, str, bool, bool, str | None]], fixups: dict[int, int],
                     base: int, hi: int, stops: set[int], zero_at=None,
                     jmp_only: set[str] = frozenset()) -> tuple[dict[int, set[str]], set[int]]:
    """({obj1 內的目標: 證據集合}, jmp 表的槽)。證據見 `PTR_POSITIVE` / `PTR_NEGATIVE`。

    `stops` 是表的邊界(入口、指向 obj1 的 fixup 目標);所有被 call/jmp 引用的表頭會自動加進去。
    `zero_at` 只給 call 表用(jmp 表不夾空槽)。obj1 以外的 fixup 來源是資料槽,除非它屬於某張 jmp 表。
    `jmp_only`(`jmp_only_slots`):取址後存進這些槽的是續行點,記 `jmpslot`(反向)。
    """
    ev: dict[int, set[str]] = {}

    def add(t: int, k: str) -> None:
        if base <= t < hi:
            ev.setdefault(t, set()).add(k)

    heads = {r[1] for r in refs if r[2] in ("call", "jmp")}
    stops = set(stops) | heads
    jmp_slots: set[int] = set()
    for _, t, role, has_reg, deref, slot in refs:
        if slot is not None and slot in jmp_only:
            add(t, "jmpslot")
        if role in ("call", "jmp"):
            add(t, "mem")                       # 表頭本身是資料
            if has_reg:
                slots = table_slots(t, fixups, base, hi, stops, zero_at if role == "call" else None)
            else:
                slots = [t] if t in fixups and base <= fixups[t] < hi else []
            for s in slots:
                add(fixups[s], "calltab" if role == "call" else "jmptab")
            if role == "jmp":
                jmp_slots.update(slots)
        elif role == "imm":
            add(t, "deref" if deref else "imm")
        elif role == "lea":
            add(t, "mem" if has_reg else ("deref" if deref else "lea"))
        else:
            add(t, "mem")
    for s, t in fixups.items():
        if not base <= s < hi and s not in jmp_slots:
            add(t, "data_slot")
    return ev, jmp_slots


def implausible(t: int, code: bytes, base: int, hi: int, insn_at, inside_insn) -> str | None:
    """`t` 不像函式起點的理由;像就回 None。

    `inside_insn(addr) -> bool`:落在某條可達指令中間。依序檢查:中間 / 字串(>= 3 個可印字元接 NUL)/
    線性解碼到 `ret*` 或無條件 `jmp` 之前遇到解不出的位元組、`00 00`、跳出 [base, hi) 的直接分支、
    `PLAUSIBLE_MAX` bytes 內沒有結尾。
    """
    if inside_insn(t):
        return "misaligned"
    b = code[t - base:t - base + 16]
    n = next((i for i, c in enumerate(b) if not 0x20 <= c < 0x7F), len(b))
    if 3 <= n < len(b) and b[n] == 0:
        return "string"
    a = t
    while a < min(hi, t + PLAUSIBLE_MAX):
        got = insn_at(a)
        if got is None:
            return "bad_decode"
        size, mn, op = got
        mn = bare(mn)
        if code[a - base:a - base + 2] == b"\x00\x00":
            return "zero_bytes"
        if (mn == "call" or mn.startswith("j")) and op.startswith("0x") and not base <= int(op, 16) < hi:
            return "branch_out"
        if mn.startswith("ret") or mn.startswith("iret") or mn == "jmp":
            return None
        a += size
    return "no_terminal"


def table_stops(entries: set[int], fixups: dict[int, int], base: int, hi: int) -> set[int]:
    """表範圍的邊界:入口與所有指向 [base, hi) 的 fixup 目標(程式碼起點;被引用的表頭另由 `pointer_evidence` 加入)。"""
    return set(entries) | {t for t in fixups.values() if base <= t < hi}


def fnptr_targets(ev: dict[int, set[str]], reject) -> set[int]:
    """有正向證據、沒有反向證據、`reject(t)` 為 None 的目標。"""
    return {t for t, k in ev.items() if k & PTR_POSITIVE and not k & PTR_NEGATIVE and reject(t) is None}


def le_entry_point(data: bytes, meta: dict) -> int | None:
    """LE 標頭的程式進入點(EIP 物件 + 偏移)換成線性位址;不在 obj1 回 None。

    載入器直接跳進來,沒有 CALL、序頭或 fixup 指向它 —— 參考版是 0x3ccb4(`_cstart_`),2026-10-07 前不在清單裡。
    """
    le = meta["le"]
    obj, off = int.from_bytes(data[le + 0x18:le + 0x1C], "little"), int.from_bytes(data[le + 0x1C:le + 0x20], "little")
    return meta["objs"][0]["base"] + off if obj == 1 else None


def filler_len(a: int, code: bytes, base: int, insn_at) -> int:
    """`a` 處對齊填充的長度(不是填充回 0):`00`/`90`/`cc` 單一位元組,或 Watcom 的 `lea r, [r]` / `mov r, r`。"""
    if code[a - base] in (0x00, 0x90, 0xCC):
        return 1
    got = insn_at(a)
    if got is None or bare(got[1]) not in ("lea", "mov"):
        return 0
    ops = [o.strip() for o in got[2].split(",")]
    return got[0] if len(ops) == 2 and ops[1] in (ops[0], f"[{ops[0]}]") else 0


def local_body(t: int, end: int, insn_at, base: int, hi: int) -> tuple[int, int] | None:
    """從 `t` 沿控制流走、只走 [t, end) 之內(call 不跟進):(本體終點, 指令數);不像一個完整函式回 None。

    不像 = 解不出的位元組、指令彼此重疊(把資料當程式碼解的典型徵狀)、跳出 [base, hi) 的直接分支、沒有任何
    `ret*`/`iret*`/`jmp` 結尾。跳到 [t, end) 之外但仍在 obj1 內的分支允許(Watcom 的共用尾段,例 `__RLDU4` 跳進 `__RLDI4`)。
    """
    seen: dict[int, int] = {}
    work, terms = [t], 0
    while work:
        a = work.pop()
        if a in seen or not t <= a < end:
            continue
        got = insn_at(a)
        if got is None:
            return None
        size, mn, op = got
        seen[a] = size
        mn = bare(mn)
        direct = op.startswith("0x") and (mn == "call" or mn.startswith("j") or mn.startswith("loop"))
        if direct and not base <= int(op, 16) < hi:
            return None
        if mn.startswith("ret") or mn.startswith("iret") or mn == "jmp":
            terms += 1
            if mn == "jmp" and direct:
                work.append(int(op, 16))
            continue
        if direct and mn != "call":
            work.append(int(op, 16))
        work.append(a + size)
    starts = sorted(seen)
    if not terms or any(x + seen[x] > y for x, y in zip(starts, starts[1:])):
        return None
    return max(x + seen[x] for x in starts), len(starts)


def island_entries(reached: set[int], insn_at, code: bytes, base: int, hi: int, entries: set[int],
                   fixups: dict[int, int]) -> tuple[set[int], int]:
    """走不到的死函式:(入口集合, 跳過的內部空隙數)。

    函式庫連進來但沒人呼叫的函式(例 `_DoINTR_` 0x468cb)沒有 CALL、序頭、fixup,位元組訊號看不到。
    做法:可達指令的無條件結尾(`ret*`/`iret*`/`jmp`)之後若接著一段**走不到**的位元組,而且這段一路延伸到下一個入口
    (中間沒有任何可達指令 —— 否則是函式內部走不到的程式碼,只計數不收),就從段首依序剝:跳過對齊填充,
    `implausible` 為 None、不是 fixup 來源(資料表)也不是 fixup 目標、`local_body` 解得出完整本體的位址算入口,
    下一個從本體終點接著剝;第一個剝不出來的就停(後面當資料)。
    fixup 目標若是函式,`fnptr` 早就收了;沒收的是被反證的(資料指標,例數學係數表 0x4cb9c)或計算式跳躍的落點
    (`int386xa` 的 `int N ; ret` 樁表 0x46948 起 256 格、`jmp cs:[ebx]` 的 case 0x3cb9b)—— 都不是函式。
    """
    sizes = {a: insn_at(a)[0] for a in reached}
    starts = sorted(sizes)
    ents = sorted(entries)
    fx_src = {s + k for s in fixups for k in range(4)}
    fx_tgt = set(fixups.values())
    no_inside = lambda _t: False   # noqa: E731  段內沒有可達指令
    found: set[int] = set()
    interior = 0
    for r in starts:
        mn = bare(insn_at(r)[1])
        if not (mn.startswith("ret") or mn.startswith("iret") or mn == "jmp"):
            continue
        g = r + sizes[r]
        i = bisect.bisect_left(starts, g)
        if g >= hi or (i < len(starts) and starts[i] == g) or g in entries:
            continue
        nxt_r = starts[i] if i < len(starts) else hi
        j = bisect.bisect_right(ents, g)
        nxt_e = ents[j] if j < len(ents) else hi
        if nxt_r < nxt_e:
            interior += 1
            continue
        pos = g
        while pos < nxt_e:
            f = filler_len(pos, code, base, insn_at)
            if f:
                pos += f
                continue
            if pos in fx_src or pos in fx_tgt or implausible(pos, code, base, hi, insn_at, no_inside) is not None:
                break
            body = local_body(pos, nxt_e, insn_at, base, hi)
            if body is None:
                break
            found.add(pos)
            pos = body[0]
    return found, interior


CONFIRM_MAX_ROUNDS = 10


def confirm_reached_calls(new_cg, strong: set[int], weak: set[int], call_index: dict[int, tuple[int, ...]],
                          insn_at, cases_of=None) -> set[int]:
    """weak 入口裡,呼叫端是「從 strong 入口可達反組譯走到的 `call` 指令」的那些(不動點:確認的再當種子)。

    weak 的疑慮是 E8 位元組掃描命中資料位元組;呼叫端若是可達的 call 指令,就不是偶然命中。種子刻意只用 strong:
    拿 weak 自己當種子會循環論證(實測從全部入口出發 218 個,只從 strong 出發 208 個)。
    `new_cg() -> callgraph_le.CG`。`cases_of(reached) -> set[int]` 給了就把「這一輪走到的 `jmp [reg*4 + 表]` 的格子目標」
    也當下一輪的種子:可達反組譯本身不跟間接 jmp,跳表後面的 case 本體(例:浮點模擬器經 opcode 跳表 0x49ec4 / 0x49fc4
    抵達的處理常式)裡的 call 不給它就永遠算沒走到。case 只來自本輪可達的 jmp,不引入 weak 的本體。
    """
    seeds, confirmed = set(strong), set()
    for _ in range(CONFIRM_MAX_ROUNDS):
        rd = new_cg()
        rd.build(sorted(seeds))
        reached = set(rd.reached)
        cases = set(cases_of(reached)) - seeds if cases_of else set()
        new = {a for a in weak - confirmed
               if any(s in reached and (g := insn_at(s)) is not None and bare(g[1]) == "call"
                      for s in call_index.get(a, ()))}
        if not new and not cases:
            return confirmed
        confirmed |= new
        seeds |= new | cases
    raise RuntimeError(f"呼叫端確認的不動點 {CONFIRM_MAX_ROUNDS} 輪內沒有收斂")


def jmp_table_cases(reached: set[int], insn_at, fixups: dict[int, int], code: bytes, base: int, hi: int,
                    stops: set[int]) -> set[int]:
    """可達指令裡 `jmp [reg*4 + 表]` 的表格目標(case 標籤);與 `discover_fnptr` 的 case 同一套 `pointer_evidence` 規則。"""
    refs = pointer_refs(sorted(reached), insn_at, fixups, code, base, hi)
    _, jslots = pointer_evidence(refs, fixups, base, hi, stops)    # 全部 refs:call 表頭也要當相鄰 jmp 表的邊界
    return {fixups[s] for s in jslots}


def entry_signals(prologue: set[int], callers: dict[int, int], ail: set[int],
                  thunks: dict[int, int], fnptr: set[int] = frozenset(),
                  eip: set[int] = frozenset(), island: set[int] = frozenset(),
                  call_reached: set[int] = frozenset()) -> dict[int, list[str]]:
    """{入口: 訊號名稱(固定順序)}。`call_reached` 只標在已經有 `call` 訊號的入口上(它是對 call 的佐證,不是新入口)。"""
    out: dict[int, list[str]] = {}
    for name, members in (("prologue", prologue), ("call", set(callers)), ("ail", ail),
                          ("thunk_target", set(thunks)), ("fnptr", set(fnptr)),
                          ("eip", set(eip)), ("island", set(island)),
                          ("call_reached", set(call_reached) & set(callers))):
        for a in members:
            out.setdefault(a, []).append(name)
    return out


WEAK_SIGNALS = ("call", "island")


def grade(signals: list[str], n_callers: int) -> str:
    """`call` 只一次可能是資料位元組的偶然命中;`island` 只靠解碼,沒有任何執行路徑或引用佐證 —— 兩者單獨都是 weak。"""
    if any(s not in WEAK_SIGNALS for s in signals) or n_callers >= STRONG_CALLERS:
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
                     skip: set[int], base: int, hi: int) -> dict[int, list[int]]:
    """{入口: 本體範圍內直接 CALL 的目標(去重、排序、不含 skip、只收 [base, hi) 內的)}。

    E8 位元組掃描命中資料位元組時,算出來的目標多半落在 obj1 之外(實測 `0x16c57` 的 callees 裡有 `0x75c1f2d7`);
    那不是呼叫,留著會讓「被呼叫者全部已知」的 wrapper 判定永遠不成立。
    """
    out: dict[int, set[int]] = {}
    for target, sites in call_index.items():
        if target in skip or not base <= target < hi:
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
             argc_of=None, bad_sites: frozenset[int] | None = None,
             fnptr: set[int] | None = None, ptr_sites: dict[int, set[int]] | None = None,
             eip: int | None = None, island: set[int] | None = None, island_interior: int | None = None,
             call_reached: set[int] | None = None, call_implausible: list[int] | None = None) -> dict:
    """由各訊號組出整份清單。`argc_of(addr) -> int | None`;不給就全部 null。

    `bad_sites`(`contradicted_sites` 的結果)先從呼叫端索引剔除,再算 callers / callees;
    不給(反組譯器不可用)就不剔除,並在 `_meta.call_sites_validated` 標 false。
    `fnptr`(`fnptr_targets` 的結果)是額外的入口訊號;不給就沒有,`_meta.fnptr_available` 標 false。
    `ptr_sites` = {目標: 以 `push`/`mov`/`lea` 取它位址的指令位址};換算成所屬入口記在 `takers`。
    取址不只是登記回呼:AIL 的 `push 終點 ; push 起點 ; call dpmi_lock_region` 鎖住一段程式碼,終點是下一個函式的起點
    (實測 0x41af4 鎖 [0x41af4, 0x420e1)),所以鎖定者也記成終點那個函式的 takers。
    `eip`(`le_entry_point`)與 `island`(`island_entries` 的結果)也是入口訊號;`island` 不給就標 `island_available` false,
    `island_interior` 是跳過的函式內部空隙數(只記數)。`call_reached`(`confirm_reached_calls` 的結果)標在呼叫端已被可達
    反組譯確認的 call 入口上,使它成 strong;不給就標 `call_reached_available` false。`call_implausible` 只記進
    `_meta.call_implausible_dropped`(剔除由呼叫端在 build 先做,這裡不再過濾);不給記 null。
    """
    # 只列會改變清單的剔除(目標在 obj1 內、不是 __STK);目標在 obj1 外的命中本來就不成入口,實測有數百個
    dropped = sorted(s for t, ss in call_index.items() if base <= t < hi and t != stack_probe
                     for s in ss if s in (bad_sites or ()))
    if bad_sites:
        call_index = {t: kept for t, ss in call_index.items() if (kept := tuple(s for s in ss if s not in bad_sites))}
    callers = {t: len(s) for t, s in call_index.items() if base <= t < hi and t != stack_probe}
    fp = {a for a in (fnptr or ()) if base <= a < hi and a != stack_probe}
    ep = {eip} if eip is not None and base <= eip < hi else set()
    isl = {a for a in (island or ()) if base <= a < hi}
    seeds = set(prologue) | set(callers) | set(ail) | fp | ep | isl
    thunks = thunk_targets(seeds, code, base, hi)
    sig = entry_signals(set(prologue), callers, set(ail), thunks, fp, ep, isl, set(call_reached or ()))
    addrs = sorted(sig)
    span = spans(addrs, hi)
    callee = callees_by_owner(addrs, call_index, {stack_probe}, base, hi)
    glob = globals_by_owner(addrs, fixups, base, hi)
    entries = []
    for a in addrs:
        n = callers.get(a, 0)
        entries.append({
            "addr": hex(a), "signals": sig[a], "callers": n, "grade": grade(sig[a], n),
            "span_upper": span[a], "argc": argc_of(a) if argc_of else None,
            "callees": [hex(t) for t in callee.get(a, [])],
            "globals": [hex(t) for t in glob.get(a, [])],
            "takers": [hex(o) for o in sorted({owner(addrs, s) for s in (ptr_sites or {}).get(a, ())} - {None})],
        })
    strong = sum(1 for e in entries if e["grade"] == "strong")
    return {"_meta": {"generator": "tools/function_inventory.py", "image_range": [hex(base), hex(hi)],
                      "entries": len(entries), "strong": strong, "weak": len(entries) - strong,
                      "by_signal": {k: sum(1 for e in entries if k in e["signals"])
                                    for k in ("prologue", "call", "ail", "thunk_target", "fnptr", "eip", "island",
                                              "call_reached")},
                      "argc_available": argc_of is not None,
                      "fnptr_available": fnptr is not None,
                      "island_available": island is not None,
                      "island_interior_gaps": island_interior,
                      "call_reached_available": call_reached is not None,
                      "call_implausible_dropped": (None if call_implausible is None
                                                   else [hex(a) for a in call_implausible]),
                      "call_sites_validated": bad_sites is not None,
                      "call_sites_dropped": [hex(s) for s in dropped]},
            "entries": entries}


def check_names(items: list[dict], spans_: dict[int, int], other_names: dict[int, str], insn_at,
                fixups: dict[int, int] | None = None, lib_names: dict[int, str] | None = None) -> list[str]:
    """驗 function_names.json 的每一筆;回傳錯誤訊息(空 = 全過)。`insn_at` 為 None 時證據無法驗,算錯誤。

    `spans_` = {入口: span_upper};`other_names` = 其他命名表的 {位址: 名稱};`fixups` = {fixup 來源: 目標}。
    `lib_names` = Watcom 函式庫比對的 {位址: 符號名}(2026-10-06):它是另一種來源 —— 同一位址人讀的描述名與函式庫
    符號名並存是正常的(`ld_add` 與 `__FLDA`),不算重複命名;但**同一個名稱落在不同位址**就是其中一邊錯了。

    證據有兩種(2026-09-28 加第二種):
    * `{"at", "insn"}`:本體裡的一條指令,逐字比對反組譯。
    * `{"fixup_from", "table", "index"}`:已知跳表(JUMP_TABLES)第 index 項的 fixup 指向這個入口。事件 handler 的身分
      只由跳表決定,本體裡沒有任何一條指令能證明「這是事件 82」。`fixups` 為 None 時無法驗,算錯誤。
    名稱形如「表前綴_N」(`event_handler_N`、`command_handler_N`)的,必須有一筆指向該表第 N 項的 fixup 證據;
    index 不得超出表的格數。
    """
    errs: list[str] = []
    seen_addr: set[int] = set()
    seen_name: set[str] = set()
    taken = set(other_names.values())
    for it in items:
        tag = f"{it.get('addr')} {it.get('name')}"
        try:
            a = int(str(it.get("addr")), 16)
        except ValueError:
            errs.append(f"{tag}: addr 不是十六進位")
            continue
        name = str(it.get("name", ""))
        if a not in spans_:
            errs.append(f"{tag}: addr 不是清單裡的入口")
            continue
        if a in seen_addr:
            errs.append(f"{tag}: addr 重複登錄")
        if a in other_names:
            errs.append(f"{tag}: 其他命名表已命名為 {other_names[a]}")
        if not NAME_RE.match(name):
            errs.append(f"{tag}: 名稱須為 snake_case")
        if name in seen_name or name in taken:
            errs.append(f"{tag}: 名稱重複或與其他命名表撞名")
        lib_at = [b for b, n in (lib_names or {}).items() if n == name and b != a]
        if lib_at:
            errs.append(f"{tag}: 與 Watcom 函式庫比對在 {lib_at[0]:#x} 的同名符號撞名")
        seen_addr.add(a)
        seen_name.add(name)
        if not str(it.get("summary", "")).strip():
            errs.append(f"{tag}: summary 不得空")
        if it.get("confidence") not in CONFIDENCES:
            errs.append(f"{tag}: confidence 須為 {'/'.join(CONFIDENCES)}")
        ev = it.get("evidence") or []
        if not ev:
            errs.append(f"{tag}: 沒有 evidence")
        slots: set[tuple[int, int]] = set()          # 驗證通過的 (表, 索引)
        for e in ev:
            if "fixup_from" in e:
                try:
                    src, tbl, idx = int(str(e.get("fixup_from")), 16), int(str(e.get("table")), 16), int(e.get("index"))
                except (TypeError, ValueError):
                    errs.append(f"{tag}: fixup 證據欄位格式錯:{e}")
                    continue
                if tbl not in JUMP_TABLES:
                    errs.append(f"{tag}: fixup 證據的表 {tbl:#x} 不在已知跳表清單")
                    continue
                if idx < 0 or src != tbl + 4 * idx:
                    errs.append(f"{tag}: fixup_from {src:#x} 不等於 表 {tbl:#x} + 4×{idx}")
                    continue
                if idx >= JUMP_TABLES[tbl][0]:
                    errs.append(f"{tag}: index {idx} 超出表 {tbl:#x} 的 {JUMP_TABLES[tbl][0]} 格")
                    continue
                got_t = fixups.get(src) if fixups is not None else None
                if got_t != a:
                    errs.append(f"{tag}: fixup {src:#x} 指向 {'None' if got_t is None else hex(got_t)},不是 {a:#x}")
                    continue
                slots.add((tbl, idx))
                continue
            try:
                at = int(str(e.get("at")), 16)
            except ValueError:
                errs.append(f"{tag}: evidence.at 不是十六進位:{e.get('at')}")
                continue
            if not a <= at < a + spans_[a]:
                errs.append(f"{tag}: evidence {at:#x} 不在函式範圍 [{a:#x}, {a + spans_[a]:#x}) 內")
                continue
            got = insn_at(at) if insn_at else None
            text = f"{got[1]} {got[2]}".strip() if got else None
            if text != e.get("insn"):
                errs.append(f"{tag}: evidence {at:#x} 期望 {e.get('insn')!r},實際 {text!r}")
        m = TABLE_NAME_RE.match(name)
        if m:
            tbl = next(t for t, v in JUMP_TABLES.items() if v[1] == m.group(1))
            if (tbl, int(m.group(2))) not in slots:
                errs.append(f"{tag}: 名稱是 {tbl:#x} 表第 {m.group(2)} 項,卻沒有通過驗證的該項 fixup 證據")
    return errs


def tier(addr: int, names: dict[int, dict], documented: set[int]) -> str:
    """覆蓋率分層:有名稱字串 = named;否則文件記載為入口 = documented;否則 unnamed。

    2026-09-28 修正:原本「位址出現在任何來源」就算 named,但 verified_addresses 與勘誤的 correct_address
    只有位址、沒有名稱(load_names 記成 name=None)。--stale-edition 登錄 79 筆勘誤後 named 從 306 跳到 363,
    接著真的命名 32 個卻只 +1 —— 那 57 個是只有位址的勘誤被算成有名稱。
    """
    if (names.get(addr) or {}).get("name"):
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


# selftest 真實 EXE 段的 build() 結果暫存:None = 不暫存(預設,所有 CLI 路徑都是這樣)。
# 只在同一個行程內、輸入(FD2.EXE 與工具原始碼)不變的期間重用 —— 不寫磁碟,所以沒有「快取過期」的問題。
_BUILD_MEMO: dict[bool, dict] | None = None
_BUILD_RUNS = 0             # `_build` 真正執行的次數;selftest 用它確認「重建比對」真的重算了


@contextlib.contextmanager
def _memo_builds():
    """在這個區塊內,同一個 `with_argc` 的 `build()` 只算一次,之後回傳深拷貝(呼叫端改了也不會互相影響)。

    selftest 的真實 EXE 段原本算 5 次(自己、重建比對、`build_structural` 兩次、`run_check_names`),
    其中 3 次與前面的輸入完全相同。「重建兩次逐位元組相同」那一項刻意繞過暫存(直接呼叫 `_build`),
    否則它就變成拿暫存跟自己比。
    """
    global _BUILD_MEMO
    prev, _BUILD_MEMO = _BUILD_MEMO, {}
    try:
        yield
    finally:
        _BUILD_MEMO = prev


def build(with_argc: bool = True) -> dict:
    """函式入口清單;`_memo_builds()` 區塊內會重用同一行程已算好的結果。"""
    if _BUILD_MEMO is None:
        return _build(with_argc)
    if with_argc not in _BUILD_MEMO:
        _BUILD_MEMO[with_argc] = _build(with_argc)
    return copy.deepcopy(_BUILD_MEMO[with_argc])


def _build(with_argc: bool = True) -> dict:
    global _BUILD_RUNS
    _BUILD_RUNS += 1
    import disasm_le as D
    import derive_native_argcounts as DNA
    import verify_address_claim_coverage as CC
    data, meta, code, base, hi = CC.load_image()
    prologue = CC.prologue_entries(code, base)
    call_index, _ = DNA._scan(types.SimpleNamespace(code=code, base=base))
    fixups = D.build_fixups(data, meta)
    ail = set(load_ail())
    argc_of = None
    bad_sites = None
    try:
        from callgraph_le import CG
        # 可達反組譯的種子:序頭入口、AIL 進入點、指向 obj1 的 fixup 目標(函式指標與 case 標籤)。
        # fixup 目標只當「這裡是指令起點」的種子,不當入口訊號(見模組說明的誠實邊界)。
        rd = CG(CC.EXE)
        rd.build(sorted(a for a in set(prologue) | ail | set(fixups.values()) if base <= a < hi))
        bad_sites = contradicted_sites(call_index, {a: rd._insn(a).size for a in rd.reached}, set(rd.calls))
        if with_argc:
            cg = CG(CC.EXE)
            ents = frozenset(prologue)
            argc_of = lambda a: DNA.callee_argc(cg, a, ents)[0]   # noqa: E731
    except ImportError:
        pass
    eip = le_entry_point(data, meta)
    fnptr, ptr_sites, island, interior, reached_calls = None, None, None, None, None
    implausible_calls: list[int] = []
    if bad_sites is not None:
        # 函式指標的可達反組譯只從**入口**出發(不拿全部 fixup 目標當種子:資料被當程式碼解,會長出假的引用)
        pre = assemble(prologue, call_index, ail, code, base, hi, fixups, CC.STACK_PROBE, None, bad_sites, eip=eip)
        insn_at = insn_decoder(code, base)
        trace: dict = {}
        fnptr, ptr_sites = discover_fnptr(lambda: CG(CC.EXE), {int(e["addr"], 16) for e in pre["entries"]},
                                          code, base, hi, fixups, insn_at, trace)
        # 死函式:以函式指標不動點最後一輪的可達指令(含 case 本體)為「走得到」,下一個入口以加入 fnptr 後的清單為界
        mid = assemble(prologue, call_index, ail, code, base, hi, fixups, CC.STACK_PROBE, None, bad_sites,
                       fnptr, None, eip)
        island, interior = island_entries(trace["reached"], insn_at, code, base, hi,
                                          {int(e["addr"], 16) for e in mid["entries"]}, fixups)
        # weak 的 call 入口:呼叫端若是從 strong 入口走得到的 call 指令就確認(種子只用 strong,避免循環論證)
        late = assemble(prologue, call_index, ail, code, base, hi, fixups, CC.STACK_PROBE, None, bad_sites,
                        fnptr, None, eip, island, interior)
        grades = {int(e["addr"], 16): (e["grade"], e["signals"]) for e in late["entries"]}
        # 不必先剔除 bad_sites:它們不是落在可達指令中間(不在 reached 的指令起點裡)就是非 call 的起點,確認條件本來就擋掉
        stops = table_stops(set(grades), fixups, base, hi)
        reached_calls = confirm_reached_calls(lambda: CG(CC.EXE), {a for a, (g, _) in grades.items() if g == "strong"},
                                              {a for a, (g, s) in grades.items() if g == "weak" and "call" in s},
                                              call_index, insn_at,
                                              lambda r: jmp_table_cases(r, insn_at, fixups, code, base, hi, stops))
        # 沒被確認、又只有 call 訊號的 weak:本體解碼不合理(implausible)就不收 —— 呼叫端與本體都沒有佐證,
        # 只剩 E8 位元組命中(實測只有 0x4dddc:embedded_const_table 0x4dda3 之後常數資料裡的偶然命中)。
        # 已確認的不套這條:0x4dda3 自己(call 一個 pop/ret 取位址,後面接資料)也會被 implausible 判成 zero_bytes。
        implausible_calls = sorted(a for a, (g, s) in grades.items() if g == "weak" and s == ["call"]
                                   and a not in reached_calls
                                   and implausible(a, code, base, hi, insn_at, lambda _t: False) is not None)
        call_index = {t: ss for t, ss in call_index.items() if t not in implausible_calls}
    return assemble(prologue, call_index, ail, code, base, hi, fixups, CC.STACK_PROBE, argc_of, bad_sites,
                    fnptr, ptr_sites, eip, island, interior, reached_calls,
                    implausible_calls if bad_sites is not None else None)


FNPTR_MAX_ROUNDS = 10


def discover_fnptr(new_cg, entries: set[int], code: bytes, base: int, hi: int, fixups: dict[int, int],
                   insn_at, trace: dict | None = None) -> tuple[set[int], dict[int, set[int]]]:
    """函式指標目標的不動點:種子 = 入口 + 上一輪的函式指標 + jmp 表的 case 標籤,直到兩者都不再變。

    回傳 (函式指標目標, {目標: 以 push/mov/lea 取它位址的指令位址})。
    `new_cg() -> callgraph_le.CG`。case 標籤只當種子(走進 case 本體才看得到裡面的取址),不回傳。
    `trace` 給了就填入最後一輪的 `reached`(可達指令集合)、`cases`、`rounds`,給 selftest 驗證種子真的有作用。
    """
    stops = table_stops(entries, fixups, base, hi)
    zero_at = lambda a: base <= a and a + 4 <= hi and code[a - base:a - base + 4] == bytes(4)   # noqa: E731
    fp: set[int] = set()
    cases: set[int] = set()
    for rnd in range(1, FNPTR_MAX_ROUNDS + 1):
        rd = new_cg()
        rd.build(sorted(set(entries) | fp | cases))
        reached = sorted(rd.reached)
        size = {a: insn_at(a)[0] for a in reached}

        def inside(t: int) -> bool:
            i = bisect.bisect_right(reached, t) - 1
            return i >= 0 and reached[i] < t < reached[i] + size[reached[i]]

        ops = [(g[1], g[2]) for g in map(insn_at, reached) if g and bare(g[1]) in ("call", "jmp")]
        refs = pointer_refs(reached, insn_at, fixups, code, base, hi)
        ev, jslots = pointer_evidence(refs, fixups, base, hi, stops, zero_at, jmp_only_slots(ops))
        nfp = fnptr_targets(ev, lambda t: implausible(t, code, base, hi, insn_at, inside))
        ncases = {fixups[s] for s in jslots} - nfp
        if (nfp, ncases) == (fp, cases):
            sites: dict[int, set[int]] = {}
            for st, t, role, _, _, _ in refs:
                if t in fp and role in ("imm", "lea"):     # 被解參考的目標本來就進不了 fp
                    sites.setdefault(t, set()).add(st)
            if trace is not None:
                trace.update(reached=set(reached), cases=cases, rounds=rnd)
            return fp, sites
        fp, cases = nfp, ncases
    raise RuntimeError(f"函式指標的不動點 {FNPTR_MAX_ROUNDS} 輪內沒有收斂")


def load_function_names() -> list[dict]:
    if not FUNCTION_NAMES_JSON.exists():
        return []
    return json.loads(FUNCTION_NAMES_JSON.read_text(encoding="utf-8"))["names"]


def load_watcom() -> dict[int, str | None]:
    """`watcom_lib_match.py` 的認定:{位址: 符號名}。別名組(`a|b`)與模組內 static(`模組+0x偏移`)
    不是單一名稱,記成 None(來源留著,不算有名稱)。"""
    if not WATCOM_JSON.exists():
        return {}
    return watcom_names(json.loads(WATCOM_JSON.read_text(encoding="utf-8"))["matches"])


def watcom_names(matches: dict[str, dict]) -> dict[int, str | None]:
    """`watcom_lib_matches.json` 的 `matches` -> {位址: 單一符號名或 None}。"""
    return {int(a, 16): None if "|" in r["name"] or "+" in r["name"] else r["name"] for a, r in matches.items()}


def insn_decoder(code: bytes, base: int):
    """`insn_at(addr) -> (長度, 助記符, 運算元) | None`;沒有 capstone 回 None。"""
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except ImportError:
        return None
    md = Cs(CS_ARCH_X86, CS_MODE_32)

    def insn_at(a: int):
        for ins in md.disasm(code[a - base:a - base + 15], a):
            return ins.size, ins.mnemonic, ins.op_str
        return None

    return insn_at


def other_real_names() -> dict[int, str]:
    """function_names.json 以外、有名稱字串的命名表(PRIM、DOC_OP_NAMES、AIL)。Watcom 函式庫比對另外由
    `check_names` 的 `lib_names` 驗(同址並存可以、異址同名不行)。"""
    return {a: v["name"] for a, v in load_names(include_registry=False, include_watcom=False).items() if v["name"]}


def run_check_names() -> list[str]:
    import verify_address_claim_coverage as CC
    inv = build(with_argc=False)
    _, _, code, base, _ = CC.load_image()
    spans_ = {int(e["addr"], 16): e["span_upper"] for e in inv["entries"]}
    import disasm_le as D
    data, meta = CC.load_image()[:2]
    return check_names(load_function_names(), spans_, other_real_names(), insn_decoder(code, base),
                       D.build_fixups(data, meta), {a: n for a, n in load_watcom().items() if n})


def load_names(include_registry: bool = True, include_watcom: bool = True) -> dict[int, dict]:
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
    for it in load_function_names() if include_registry else []:
        add(int(it["addr"], 16), "function_names", it["name"])
    # 排在人讀的名稱之後:同一位址已有名稱時只多記一個來源
    for a, v in load_watcom().items() if include_watcom else []:
        add(a, "watcom_lib", v)
    for e in json.loads(VERIFIED_JSON.read_text(encoding="utf-8"))["entries"]:
        for h in HEX.findall(str(e.get("address", ""))):
            add(int(h, 16), "verified_addresses", None)
    for e in json.loads(ERRATA_JSON.read_text(encoding="utf-8"))["errata"]:
        for h in HEX.findall(str(e.get("correct_address", ""))):
            add(int(h, 16), "errata.correct", None)
    return out


def real_names(include_registry: bool = True) -> dict[int, str]:
    """只收有名稱字串的來源(PRIM、DOC_OP_NAMES、AIL,以及 function_names.json)。"""
    return {a: v["name"] for a, v in load_names(include_registry).items() if v["name"]}


def build_structural(include_registry: bool = True) -> dict:
    import disasm_le as D
    import verify_address_claim_coverage as CC
    inv = build(with_argc=True)
    data, meta, code, base, hi = CC.load_image()
    ents = {int(e["addr"], 16) for e in inv["entries"]}
    bodies = None
    insn_at = insn_decoder(code, base)
    if insn_at:
        bodies = {int(e["addr"], 16): body_insns(insn_at, int(e["addr"], 16), int(e["addr"], 16) + e["span_upper"])
                  for e in inv["entries"] if e["span_upper"] <= WRAPPER_MAX_SPAN}
    named = structural(inv["entries"], real_names(include_registry), entry_thunks(ents, code, base, hi), set(load_ail()),
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
    # 只有位址的來源(verified_addresses、勘誤)多半引用函式中間的一條指令,不是入口很正常;
    # 有名稱字串卻不是入口的才需要看(舊版位址、__STK 這類刻意不當入口的,或真的抄錯)
    named_stray = [f"{a:#x}={names[a]['name']}" for a in stray if names[a]["name"]]
    print(f"  命名表裡不是任何入口的 obj1 位址:{len(stray)} 個;其中有名稱 {len(named_stray)} 個"
          + (f":{named_stray}" if named_stray else "")
          + f";其餘 {len(stray) - len(named_stray)} 個只有位址(指令層引用)")
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


def report_card(addr_s: str) -> int:
    import derive_native_argcounts as DNA
    import verify_address_claim_coverage as CC
    inv = build(with_argc=True)
    addrs = [int(e["addr"], 16) for e in inv["entries"]]
    by = {int(e["addr"], 16): e for e in inv["entries"]}
    a = int(addr_s, 16)
    if a not in by:
        o = owner(addrs, a)
        print(f"{a:#x} 不是入口;所屬入口 {o:#x}" if o is not None else f"{a:#x} 在第一個入口之前")
        return 1
    e = by[a]
    names = load_names()
    sd = build_structural()["names"]

    def lab(t: int) -> str:
        n = names.get(t, {}).get("name") or sd.get(hex(t), {}).get("name")
        return f"{t:#x}" + (f"={n}" if n else "")

    _, _, code, base, _ = CC.load_image()
    idx, _ = DNA._scan(types.SimpleNamespace(code=code, base=base))
    callers = sorted({owner(addrs, s) for s in idx.get(a, ()) if owner(addrs, s) is not None})
    print(f"{lab(a)}  signals={e['signals']} grade={e['grade']} callers={e['callers']} span<={e['span_upper']} argc={e['argc']}")
    print("  callees:", [lab(int(t, 16)) for t in e["callees"]])
    print("  globals:", e["globals"])
    print("  called from:", [lab(c) for c in callers])
    insn_at = insn_decoder(code, base)
    body = body_insns(insn_at, a, a + e["span_upper"]) if insn_at else None
    fix = None
    if body is None and insn_at:                      # 沒有乾淨結尾:照樣線性印到 span 為止
        body, x = [], a
        while x < a + e["span_upper"]:
            got = insn_at(x)
            if got is None:
                break
            body.append((x, *got))
            x += got[0]
    if LIVE_EXEC_JSON.exists():
        live, lm = load_live_exec()
        ran = sum(1 for x, *_ in body or [] if x in live)
        print(f"  實機執行({lm['traces_distinct']} 份原版軌跡,下限):入口 {'有' if a in live else '無'};"
              f"本體 {ran} / {len(body or [])} 條指令有紀錄" + ("" if ran else "(沒有紀錄 ≠ 沒用到)"))
    import disasm_le as D
    data, meta = CC.load_image()[:2]
    fix = D.build_fixups(data, meta)
    for x, size, mn, op in body or []:
        refs = [hex(fix[y]) for y in range(x, x + size) if y in fix]
        tgt = f"   ; {lab(int(op, 16))}" if mn == "call" and op.startswith("0x") else ""
        print(f"    {x:#x}  {mn} {op}{tgt}" + (f"   ; -> {', '.join(refs)}" if refs else ""))
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
    check("grade:island 單獨 = weak(只靠解碼);island + call 一次仍 weak;eip = strong;island + 其他訊號 = strong",
          [grade(["island"], 0), grade(["call", "island"], 1), grade(["eip"], 0), grade(["fnptr", "island"], 0)],
          ["weak", "weak", "strong", "strong"])
    check("entry_signals:call_reached 只標在有 call 的入口上(不憑空生入口);call + call_reached 一次呼叫也是 strong",
          (entry_signals(set(), {0x10: 1}, set(), {}, call_reached={0x10, 0x20}), grade(["call", "call_reached"], 1)),
          ({0x10: ["call", "call_reached"]}, "strong"))

    class FakeCG:
        """可達反組譯的替身:build(種子) 後 reached = 各種子可達集合的聯集。"""
        REACH = {0x100: {0x100, 0x105, 0x106}, 0x200: {0x200, 0x205}, 0x300: {0x300}, 0x400: {0x400, 0x405}}

        def __init__(self) -> None:
            self.reached: set[int] = set()

        def build(self, seeds) -> None:
            self.reached = set().union(*(self.REACH.get(s, set()) for s in seeds))
    fake_c = {0x105: (5, "call", "0x200"), 0x205: (5, "call", "0x300"), 0x405: (5, "call", "0x400"),
              0x106: (2, "mov", "eax, ebx")}
    idx_c = {0x200: (0x105,), 0x300: (0x205,), 0x400: (0x405,), 0x500: (0x106,), 0x600: (0x999,)}
    check("confirm_reached_calls:由 strong 出發逐輪確認(0x200 -> 0x300);只被自己走到的呼叫端(0x400)、"
          "呼叫端不是 call(0x500)、沒走到(0x600)都不確認",
          confirm_reached_calls(FakeCG, {0x100}, {0x200, 0x300, 0x400, 0x500, 0x600}, idx_c, fake_c.get), {0x200, 0x300})

    class FakeCGJ(FakeCG):
        REACH = {**FakeCG.REACH, 0x700: {0x700, 0x705}}
    fake_j = {**fake_c, 0x705: (5, "call", "0x800")}
    idx_j = {**idx_c, 0x800: (0x705,)}
    # 0x106 當作可達的 `jmp [reg*4 + 表]`,表裡的 case 是 0x700;0x700 的本體只有經 case 種子才走得到
    cases_j = lambda r: {0x700} if 0x106 in r else set()     # noqa: E731
    cases_n = lambda r: {0x700} if 0x405 in r else set()     # noqa: E731

    def confirm_or_err(*args):
        try:
            return confirm_reached_calls(*args)
        except RuntimeError:
            return "沒有收斂"
    check("confirm_reached_calls:可達 jmp 表的 case 當下一輪種子 -> case 本體裡的 call(0x800)確認;不給 cases_of 不確認;"
          "case 只能來自本輪可達的 jmp(只有 weak 0x400 的本體走得到的 jmp 不算);第一輪只有 case、沒有新確認也要再走一輪",
          (confirm_or_err(FakeCGJ, {0x100}, {0x200, 0x300, 0x400, 0x800}, idx_j, fake_j.get, cases_j),
           confirm_or_err(FakeCGJ, {0x100}, {0x200, 0x300, 0x400, 0x800}, idx_j, fake_j.get),
           confirm_or_err(FakeCGJ, {0x100}, {0x200, 0x300, 0x400, 0x800}, idx_j, fake_j.get, cases_n),
           confirm_or_err(FakeCGJ, {0x100}, {0x800}, idx_j, fake_j.get, cases_j)),
          ({0x200, 0x300, 0x800}, {0x200, 0x300}, {0x200, 0x300}, {0x800}))
    code_j = bytearray(0x200)
    code_j[0x003:0x007] = (0x1100).to_bytes(4, "little")
    code_j[0x013:0x017] = (0x1108).to_bytes(4, "little")
    fx_j = {0x1003: 0x1100, 0x1013: 0x1108, 0x1100: 0x1040, 0x1104: 0x1050, 0x1108: 0x1060}
    dec_j = {0x1000: (7, "jmp", "dword ptr [ebx*4 + 0x1100]"), 0x1010: (7, "call", "dword ptr [ebx*4 + 0x1108]")}
    check("jmp_table_cases:可達 jmp 表的格子目標;相鄰的 call 表頭(0x1108)是邊界、call 表的目標不算 case;jmp 沒走到就沒有",
          (jmp_table_cases({0x1000, 0x1010}, dec_j.get, fx_j, bytes(code_j), 0x1000, 0x1200, set()),
           jmp_table_cases({0x1010}, dec_j.get, fx_j, bytes(code_j), 0x1000, 0x1200, set())),
          ({0x1040, 0x1050}, set()))
    check("entry_signals:eip、island 排在 fnptr 之後",
          entry_signals({0x10}, {}, set(), {}, {0x10}, {0x10, 0x20}, {0x20}), {0x10: ["prologue", "fnptr", "eip"],
                                                                           0x20: ["eip", "island"]})

    print("(3) spans / owner")
    check("spans:中間到下一個入口,最後一個到 hi", spans([0x10, 0x18, 0x30], 0x40), {0x10: 8, 0x18: 0x18, 0x30: 0x10})
    check("spans:空清單", spans([], 0x40), {})
    check("owner:第一個入口之前 None、起點屬於自己、下一個入口前一格屬於前一個",
          [owner([0x10, 0x18], 0xf), owner([0x10, 0x18], 0x10), owner([0x10, 0x18], 0x17),
           owner([0x10, 0x18], 0x18), owner([0x10, 0x18], 0x999)], [None, 0x10, 0x10, 0x18, 0x18])

    print("(4) callees_by_owner / globals_by_owner")
    idx = {0x500: (0x11, 0x12, 0x19), 0x600: (0x13,), 0x700: (0x5,), 0x3702f: (0x14,),
           0xff: (0x15,), 0x100: (0x16,), 0x8ff: (0x17,), 0x900: (0x1a,)}
    check("呼叫端歸屬、去重排序、__STK 不算、第一個入口之前的呼叫端丟掉;目標只收 [base, hi)(base 含、hi 不含)",
          callees_by_owner([0x10, 0x18], idx, {0x3702f}, 0x100, 0x900), {0x10: [0x100, 0x500, 0x600, 0x8ff], 0x18: [0x500]})
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
    check("callees(不含 obj1 外的目標、不含 __STK)與 globals",
          (by["0x1000"]["callees"], by["0x1010"]["callees"], by["0x1000"]["globals"]),
          (["0x1010", "0x1020"], ["0x1020"], ["0x9000"]))
    check("_meta 計數", {k: inv["_meta"][k] for k in ("entries", "strong", "weak", "by_signal", "argc_available")},
          {"entries": 5, "strong": 4, "weak": 1, "argc_available": True,
           "by_signal": {"prologue": 1, "call": 2, "ail": 1, "thunk_target": 1, "fnptr": 0, "eip": 0, "island": 0,
                         "call_reached": 0}})
    none = assemble({0x1000}, {}, set(), bytes(0x40), base, hi, {}, 0x1038)
    check("不給 argc_of:argc 為 null 且 _meta 如實標示", (none["entries"][0]["argc"], none["_meta"]["argc_available"]), (None, False))
    check("dump:穩定、結尾換行、中文原樣", (dump(none) == dump(none), dump(none).endswith("}\n"), "\\u" in dump({"名": 1})),
          (True, True, False))

    print("(5b) contradicted_sites:可達指令內部 / 非 CALL 的起點才剔除;邊界與沒走到的保留")
    # 可達指令:0x1000(長 11)、0x100b(CALL,長 5)、0x1010(長 2)
    ins5 = {0x1000: 11, 0x100b: 5, 0x1010: 2}
    idx5 = {0x2000: (0x1003,), 0x2100: (0x100b,), 0x2200: (0x1010,), 0x2300: (0x1012,),
            0x2400: (0x1001, 0x100a), 0x2500: (0x0fff,), 0x2600: (0x1100,)}
    check("內部(0x1003/0x1001/0x100a)與非 CALL 起點(0x1010)剔除;CALL 起點、緊接最後一條之後、"
          "第一條之前、沒走到的保留",
          sorted(contradicted_sites(idx5, ins5, {0x100b})), [0x1001, 0x1003, 0x100a, 0x1010])
    check("起點 + 長度那一格不算內部(屬於下一條)", sorted(contradicted_sites({0x1: (0x100b,)}, {0x1000: 11}, set())), [])
    inv5 = assemble({0x1000}, {0x1010: (0x1002,), 0x1020: (0x1004, 0x1012), 0x1030: (0x1006,), 0x9000: (0x1008,),
                              0x1038: (0x100a,)},
                    set(), bytes(0x40), base, hi, {}, 0x1038, bad_sites=frozenset({0x1004, 0x1006, 0x1008, 0x100a}))
    got5 = {e["addr"]: (e["callers"], e["grade"]) for e in inv5["entries"]}
    check("剔除後:0x1020 降為 weak、0x1030 消失、0x1010 不受影響;callees 也跟著少",
          (got5, inv5["entries"][0]["callees"]), ({"0x1000": (0, "strong"), "0x1010": (1, "weak"), "0x1020": (1, "weak")},
                                                  ["0x1010"]))
    check("_meta 標示已驗並列出剔除的呼叫端(目標在 obj1 外、目標是 __STK 的不列);沒給 bad_sites 時標 false、清單空",
          (inv5["_meta"]["call_sites_validated"], inv5["_meta"]["call_sites_dropped"],
           none["_meta"]["call_sites_validated"], none["_meta"]["call_sites_dropped"]),
          (True, ["0x1004", "0x1006"], False, []))

    print("(5c) 函式指標:表的範圍、fixup 的用法、取址後的去向、證據合成、本體合理性")
    fx5 = {0x2000: 0x1010, 0x2004: 0x1020, 0x2010: 0x1030, 0x2014: 0x9000}
    z5 = lambda a: a in (0x2008, 0x200c)   # noqa: E731
    check("table_slots:不夾空槽時停在第一個空槽;夾空槽時越過、停在指向 obj1 外的格;別的表頭擋住;表頭自己在 stops 裡不擋",
          [table_slots(0x2000, fx5, 0x1000, 0x1040, set()), table_slots(0x2000, fx5, 0x1000, 0x1040, set(), z5),
           table_slots(0x2000, fx5, 0x1000, 0x1040, {0x2010}, z5), table_slots(0x2010, fx5, 0x1000, 0x1040, {0x2010})],
          [[0x2000, 0x2004], [0x2000, 0x2004, 0x2010], [0x2000, 0x2004], [0x2010]])
    check("table_slots:夾空槽時,非 0 又不是指標的格(0x2014 指向 obj1 外)照樣停,後面的指標(0x2018)不收",
          table_slots(0x2000, {**fx5, 0x2018: 0x1038}, 0x1000, 0x1040, set(), z5), [0x2000, 0x2004, 0x2010])
    check("table_stops:入口 + 指向 [base, hi) 的 fixup 目標(範圍外的不算)",
          sorted(table_stops({0x1000}, {0x2000: 0x1010, 0x2004: 0x9000, 0x2008: 0x1000}, 0x1000, 0x1040)), [0x1000, 0x1010])
    check("ref_role:立即值 / 位移 / lea 帶不帶暫存器 / call、jmp 表 / 段前綴 / 其他指令的立即值不算 / 不吃較長的十六進位",
          [ref_role("push", "0x2ca23", 0x2CA23), ref_role("mov", "dword ptr [0x37f4], 0x39ad8", 0x39AD8),
           ref_role("mov", "dword ptr [0x37f4], 0x39ad8", 0x37F4), ref_role("lea", "edx, [0x3a0c4]", 0x3A0C4),
           ref_role("lea", "ebx, [ebx*4 + 0x2cae6]", 0x2CAE6), ref_role("call", "dword ptr cs:[ebx*4 + 0x39e04]", 0x39E04),
           ref_role("call", "dword ptr [0x27d8]", 0x27D8), ref_role("jmp", "dword ptr cs:[eax*4 + 0x30684]", 0x30684),
           ref_role("fld", "xword ptr cs:[0x2cac8]", 0x2CAC8), ref_role("cmp", "eax, 0x3cf1c", 0x3CF1C),
           ref_role("push", "0x12ca23", 0x2CA23)],
          [("imm", False), ("imm", False), ("mem", False), ("lea", False), ("lea", True), ("call", True),
           ("call", False), ("jmp", True), ("mem", False), None, None])
    check("pointer_use:跨條件跳仍追、字串指令(含 rep 前綴)算解參考、cmp 不算改寫、改寫 / int 就停、記下存進的槽",
          [pointer_use("esi", [("or", "ecx, ecx"), ("je", "0x10"), ("mov", "ax, word ptr cs:[esi + 8]")]),
           pointer_use("esi", [("rep movsd", "dword ptr es:[edi], dword ptr [esi]")]),
           pointer_use("esi", [("rep movsd", "")]),
           pointer_use("edx", [("cmp", "edx, 0"), ("mov", "eax, dword ptr [edx]")]),
           pointer_use("edx", [("mov", "edx, 5"), ("mov", "eax, dword ptr [edx]")]),
           pointer_use("edx", [("int", "0x21"), ("mov", "eax, dword ptr [edx]")]),
           pointer_use("edx", [("mov", "dword ptr ds:[ebp + 0x76], edx"), ("jmp", "0x1000")])],
          [(True, None), (True, None), (True, None), (True, None), (False, None), (False, None), (False, "[ebp + 0x76]")])
    check("jmp_only_slots:只被 jmp(含 notrack 前綴)用的槽;同時被 call 的不算;直接 jmp 沒有槽",
          jmp_only_slots([("notrack jmp", "dword ptr ds:[ebp + 0x76]"), ("call", "dword ptr [0x37f4]"),
                          ("jmp", "dword ptr [0x37f4]"), ("jmp", "0x1000")]), {"[ebp + 0x76]"})
    # obj1 = [0x1000, 0x1100);call 表 0x1080(0x1084 是空槽)、jmp 表 0x1090;obj2 的槽 0x5000、obj2 的 jmp 槽 0x5010
    # 0x1098 也是 0 槽、0x109c 有指標:jmp 表不夾空槽,0x1038 不該成 case 標籤
    fxe = {0x1080: 0x1010, 0x1088: 0x1020, 0x1090: 0x1030, 0x1094: 0x1034, 0x109c: 0x1038, 0x5000: 0x1040, 0x5010: 0x1044}
    refs = [(0x1000, 0x1080, "call", True, False, None), (0x1002, 0x1090, "jmp", True, False, None),
            (0x1004, 0x1050, "imm", False, False, None), (0x1006, 0x1054, "imm", False, True, None),
            (0x1008, 0x1058, "lea", False, False, "[ebp + 0x76]"), (0x100a, 0x105c, "lea", True, False, None),
            (0x100c, 0x1060, "mem", False, False, None), (0x100e, 0x5010, "jmp", False, False, None)]
    ev, js = pointer_evidence(refs, fxe, 0x1000, 0x1100, set(), lambda a: a in (0x1084, 0x1098), {"[ebp + 0x76]"})
    check("pointer_evidence:call 表越過空槽、jmp 表成 case、取址後解參考 / 存進只被 jmp 的槽 / 帶暫存器的 lea 都是反向、"
          "表頭是資料、obj2 的槽是資料槽(jmp 槽除外)",
          ({hex(t): sorted(k) for t, k in sorted(ev.items())}, sorted(js)),
          ({"0x1010": ["calltab"], "0x1020": ["calltab"], "0x1030": ["jmptab"], "0x1034": ["jmptab"],
            "0x1040": ["data_slot"], "0x1044": ["jmptab"], "0x1050": ["imm"], "0x1054": ["deref"],
            "0x1058": ["jmpslot", "lea"], "0x105c": ["mem"], "0x1060": ["mem"], "0x1080": ["mem"], "0x1090": ["mem"]},
           [0x1090, 0x1094, 0x5010]))
    ev0, _ = pointer_evidence(refs, fxe, 0x1000, 0x1100, set(), None, set())
    check("pointer_evidence:不給 zero_at 時 call 表停在空槽;不給 jmp_only 時存進槽的 lea 是正向",
          (sorted(k for k, v in ev0.items() if "calltab" in v), sorted(ev0[0x1058])), ([0x1010], ["lea"]))
    check("fnptr_targets:有正向、沒有反向、reject 為 None",
          [sorted(fnptr_targets(ev, lambda t: None)), sorted(fnptr_targets(ev, lambda t: "x" if t == 0x1050 else None))],
          [[0x1010, 0x1020, 0x1040, 0x1050], [0x1010, 0x1020, 0x1040]])
    code_i = bytearray(b"\x90" * 0x100)    # 預設非 0:否則每個案例都先被 00 00 判掉,其他理由測不到
    code_i[0x00:0x04] = b"abc\x00"
    code_i[0x08:0x0b] = b"ab\x00"
    code_i[0x30:0x32] = b"\x00\x00"
    fake = {0x1008: (1, "push", "ebx"), 0x1009: (1, "ret", ""), 0x1010: (1, "push", "ebx"), 0x1011: (1, "ret", ""),
            0x1030: (2, "add", "byte ptr [eax], al"), 0x1040: (5, "jmp", "0x9abaaf91"), 0x1050: (5, "jmp", "0x1000"),
            0x1060: (2, "notrack jmp", "dword ptr [eax]"), 0x1068: (5, "call", "0x1000"), 0x106d: (1, "iretd", "")}
    fake.update({a: (1, "nop", "") for a in range(0x1080, 0x1100)})
    imp = lambda t: implausible(t, bytes(code_i), 0x1000, 0x1100, fake.get, lambda x: x == 0x1070)   # noqa: E731
    check("implausible:字串(>= 3 個可印字元接 NUL;2 個不算)/ 正常 / 解不出 / 00 00 / 分支出界 / 範圍內 jmp 與 "
          "notrack jmp 是結尾 / call 不是結尾、iretd 是 / 在指令中間 / 走到 hi 沒有結尾",
          [imp(t) for t in (0x1000, 0x1008, 0x1010, 0x1020, 0x1030, 0x1040, 0x1050, 0x1060, 0x1068, 0x1070, 0x1080)],
          ["string", None, None, "bad_decode", "zero_bytes", "branch_out", None, None, None, "misaligned", "no_terminal"])
    inv5c = assemble({0x1000}, {}, set(), bytes(0x40), base, hi, {}, 0x1038, fnptr={0x1010, 0x1038, 0x9000},
                     ptr_sites={0x1010: {0x1004, 0x1012, 0x0f00}})
    got5c = {e["addr"]: (e["signals"], e["grade"], e["takers"]) for e in inv5c["entries"]}
    check("assemble:fnptr 成 strong 入口、__STK 與範圍外的不收;takers 換算成所屬入口(含自己,第一個入口之前的不算)",
          (got5c, inv5c["_meta"]["by_signal"]["fnptr"], inv5c["_meta"]["fnptr_available"], none["_meta"]["fnptr_available"]),
          ({"0x1000": (["prologue"], "strong", []), "0x1010": (["fnptr"], "strong", ["0x1000", "0x1010"])}, 1, True, False))

    print("(5d) 死函式島與 LE 進入點")
    le_img = bytearray(0x40)
    le_img[0x28:0x2C] = (1).to_bytes(4, "little")
    le_img[0x2C:0x30] = (0x2CCB4).to_bytes(4, "little")
    le_meta = {"le": 0x10, "objs": [{"base": 0x10000}]}
    le_img2 = bytearray(le_img)
    le_img2[0x28] = 2
    check("le_entry_point:obj1 的 EIP 換成線性位址;EIP 在別的物件回 None",
          (le_entry_point(bytes(le_img), le_meta), le_entry_point(bytes(le_img2), le_meta)), (0x3CCB4, None))
    code_f = bytes([0x00, 0x90, 0xCC, 0x8D, 0x89, 0x89, 0x8D, 0x55])
    fake_f = {0x1003: (3, "lea", "eax, [eax]"), 0x1004: (2, "mov", "ecx, ecx"), 0x1005: (2, "mov", "eax, ecx"),
              0x1006: (3, "lea", "eax, [eax + 1]")}
    check("filler_len:00/90/cc 各 1;lea r,[r] 與 mov r,r 取指令長;不同暫存器、帶位移、解不出都不是填充",
          [filler_len(0x1000 + k, code_f, 0x1000, fake_f.get) for k in range(8)], [1, 1, 1, 3, 2, 0, 0, 0])
    lb = {"overlap": {0x2000: (3, "mov", "eax, 1"), 0x2003: (2, "jne", "0x2001"), 0x2001: (2, "add", "al, 1"),
                      0x2005: (1, "ret", "")},
          "no_term": {0x2000: (16, "nop", "")},      # 走出段外仍沒有結尾(不是解不出)
          "out": {0x2000: (5, "call", "0x9000"), 0x2005: (1, "ret", "")},
          "bad": {0x2000: (2, "jne", "0x2008"), 0x2002: (1, "ret", "")},
          "ok": {0x2000: (2, "jne", "0x2800"), 0x2002: (2, "jmp", "0x2006"), 0x2004: (1, "int3", ""),
                 0x2006: (2, "loop", "0x2000"), 0x2008: (1, "iretd", "")}}
    check("local_body:重疊 / 沒有結尾 / call 出 obj1 / 走到解不出的位元組都是 None;跳出段外但在 obj1 內可以、"
          "jmp 跟進、跳過的位元組不算、loop 的落空路徑照走",
          {k: local_body(0x2000, 0x2010, v.get, 0x1000, 0x3000) for k, v in lb.items()},
          {"overlap": None, "no_term": None, "out": None, "bad": None, "ok": (0x2009, 4)})
    code_d = bytearray(b"\x55" * 0x100)     # 預設非填充、非 0、無 NUL(不會被當字串)
    code_d[0x02] = 0x90
    code_d[0x03] = 0x8D
    fake_d = {0x1000: (1, "push", "ebx"), 0x1001: (1, "ret", ""), 0x1003: (3, "lea", "eax, [eax]"),
              0x1006: (1, "push", "ebp"), 0x1007: (2, "jne", "0x100a"), 0x1009: (1, "ret", ""), 0x100a: (1, "pop", "ebp"),
              0x100b: (1, "ret", ""), 0x100c: (5, "mov", "eax, 1"), 0x1011: (5, "jmp", "0x1000"),
              0x1016: (1, "inc", "eax"), 0x1017: (1, "ret", ""),       # fixup 目標:不收,而且整串就停在這裡
              0x1040: (1, "ret", ""), 0x1041: (1, "inc", "eax"), 0x1042: (1, "ret", ""),   # 內部空隙:只計數
              0x1050: (1, "ret", ""),                                  # 之後 0x1051 解不出 -> 停
              0x1080: (1, "ret", ""), 0x1081: (1, "inc", "eax"), 0x1082: (1, "ret", ""),
              0x1083: (1, "inc", "eax"), 0x1084: (1, "ret", ""),       # fixup 來源(資料表):不收
              0x10c0: (1, "jmp", "eax"), 0x10c1: (1, "inc", "eax"), 0x10c2: (1, "ret", ""),   # 緊接入口:不算空隙
              0x10e0: (5, "call", "0x1000"), 0x10e5: (1, "inc", "eax"), 0x10e6: (1, "ret", "")}   # call 不是結尾
    reached_d = {0x1000, 0x1001, 0x1040, 0x1050, 0x1080, 0x10c0, 0x10e0}
    got_d = island_entries(reached_d, fake_d.get, bytes(code_d), 0x1000, 0x1100,
                           {0x1000, 0x1040, 0x1080, 0x10c0, 0x10c1, 0x10d0}, {0x2000: 0x1016, 0x1083: 0x9000})
    check("island_entries:結尾之後跳過填充依序剝出 0x1006、0x100c,停在 fixup 目標;內部空隙只計數;"
          "解不出就停;fixup 來源不收;緊接入口與 call 之後都不算",
          (sorted(got_d[0]), got_d[1]), ([0x1006, 0x100c, 0x1081], 1))
    # 2026-10-07 突變存活補的兩題:停點來自 local_body(線性解碼看似合理、可達走法重疊)與 implausible(字串)。
    # 兩題都在停點之後放一個本身合格的本體,不停的話會被收進來。
    code_o = bytearray(b"\x55" * 0x40)
    fake_o = {0x1000: (1, "ret", ""), 0x1001: (2, "jne", "0x1002"), 0x1002: (1, "inc", "eax"), 0x1003: (1, "ret", "")}
    code_s = bytearray(b"\x55" * 0x40)
    code_s[0x01:0x05] = b"abc\x00"
    fake_s = {0x1000: (1, "ret", ""), 0x1001: (3, "inc", "eax"), 0x1004: (1, "ret", ""),
              0x1005: (1, "inc", "eax"), 0x1006: (1, "ret", "")}
    check("island_entries:local_body 不成立(跳進自己中間)就停,不往下一個位元組找;字串(implausible)也停",
          [island_entries({0x1000}, f.get, bytes(c), 0x1000, 0x1040, {0x1000, 0x1020}, {})
           for f, c in ((fake_o, code_o), (fake_s, code_s))], [(set(), 0), (set(), 0)])
    inv5d = assemble({0x1000}, {}, set(), bytes(0x40), base, hi, {}, 0x1038, eip=0x1010, island={0x1020, 0x9000},
                     island_interior=3)
    got5d = {e["addr"]: (e["signals"], e["grade"]) for e in inv5d["entries"]}
    check("assemble:eip 成 strong、island 成 weak、範圍外的不收;_meta 計數與 island 旗標",
          (got5d, inv5d["_meta"]["by_signal"]["eip"], inv5d["_meta"]["by_signal"]["island"],
           inv5d["_meta"]["island_available"], inv5d["_meta"]["island_interior_gaps"], none["_meta"]["island_available"]),
          ({"0x1000": (["prologue"], "strong"), "0x1010": (["eip"], "strong"), "0x1020": (["island"], "weak")},
           1, 1, True, 3, False))
    inv5e = assemble({0x1000}, {0x1010: (0x1002,), 0x1020: (0x1004,)}, set(), bytes(0x40), base, hi, {}, 0x1038,
                     call_reached={0x1010, 0x1030}, call_implausible=[0x1030])
    check("assemble:call_reached 讓只被 CALL 一次的入口成 strong、沒確認的維持 weak、沒有 call 的位址不成入口;旗標如實;"
          "call_implausible 只記錄(給了記清單、沒給記 null)",
          ({e["addr"]: (e["signals"], e["grade"]) for e in inv5e["entries"]}, inv5e["_meta"]["call_reached_available"],
           none["_meta"]["call_reached_available"], inv5e["_meta"]["call_implausible_dropped"],
           none["_meta"]["call_implausible_dropped"]),
          ({"0x1000": (["prologue"], "strong"), "0x1010": (["call", "call_reached"], "strong"), "0x1020": (["call"], "weak")},
           True, False, ["0x1030"], None))
    check("assemble:eip 在 obj1 之外不收",
          [e["addr"] for e in assemble({0x1000}, {}, set(), bytes(0x40), base, hi, {}, 0x1038, eip=hi)["entries"]], ["0x1000"])

    print("(6) tier / coverage_counts:命名表優先於文件記載;strong_only 真的只數 strong")
    ents6 = [{"addr": "0x10", "grade": "strong"}, {"addr": "0x20", "grade": "strong"},
             {"addr": "0x30", "grade": "weak"}, {"addr": "0x40", "grade": "strong"}, {"addr": "0x50", "grade": "weak"}]
    names6, doc6 = {0x10: {"name": "a"}, 0x30: {"name": "b"}}, {0x10, 0x20, 0x50}
    check("tier 三分", [tier(0x10, names6, doc6), tier(0x20, names6, doc6), tier(0x40, names6, doc6)],
          ["named", "documented", "unnamed"])
    # 只有位址、沒有名稱的來源(勘誤 correct_address、verified_addresses)不算 named:
    # 有文件記載落 documented、沒有落 unnamed;同一位址補上名稱才是 named(成對)
    nl6 = {0x20: {"name": None, "sources": ["errata.correct"]}, 0x40: {"name": None, "sources": ["verified_addresses"]}}
    check("無名稱字串的來源不算 named", [tier(0x20, nl6, doc6), tier(0x40, nl6, doc6),
                                     tier(0x40, {0x40: {"name": "c", "sources": ["function_names"]}}, doc6)],
          ["documented", "unnamed", "named"])
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
    # 互相取址:0x10(種子)呼叫 0x20;0x20 與 0x30 互取位址;0x30 也取自己(不算)。0x60 與 0x70 互取但沒人用;
    # 0x80 與 0x90 互取,0x90 另被集合外的 0xa0 呼叫。
    ent2 = lambda a, cs=(), tk=(): {**ent(a, list(cs)), "takers": [hex(t) for t in tk]}   # noqa: E731
    cyc = [ent2(0x10, [0x20]), ent2(0x20, [], [0x30]), ent2(0x30, [], [0x20, 0x30]), ent2(0x60, [], [0x70]),
           ent2(0x70, [], [0x60]), ent2(0x80, [], [0x90]), ent2(0x90, [], [0x80]), ent2(0xa0, [0x90])]
    check("互相取址的一對只經種子抵達 -> 兩個都加入;沒人用的一對、有集合外引用者的一對都不加入",
          closed_under_callers(cyc, {0x10}), {0x20, 0x30})
    check("集合外引用者也成種子時,那一對才加入", closed_under_callers(cyc, {0x10, 0xa0}), {0x20, 0x30, 0x80, 0x90})

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

    print("(11b) dead_body_hits:只算本體指令起點;沒有乾淨結尾才退回整個 span")
    sp = {0: 0x10, 0x20: 8}
    check("span 尾端(本體結尾之後)的執行位址不算;本體內的算",
          (dead_body_hits({0}, sp, decoder(t1), {7, 8}), dead_body_hits({0}, sp, decoder(t1), {4, 7})), ({}, {0: [4]}))
    check("本體指令中間的位址不算(只比指令起點)", dead_body_hits({0}, sp, decoder(t1), {2, 5}), {})
    check("解不出本體 -> 整個 span,上界不含", (dead_body_hits({0x20}, sp, decoder({}), {0x27, 0x28}),
                                       dead_body_hits({0x20}, sp, decoder({}), {0x28})), ({0x20: [0x27]}, {}))
    check("只看傳進來的入口", dead_body_hits(set(), sp, decoder(t1), {0, 4}), {})

    print("(11c) _memo_builds:區塊內同一 with_argc 只算一次、回傳深拷貝;區塊外不暫存")
    calls: list[bool] = []
    real_build = globals()["_build"]
    globals()["_build"] = lambda with_argc=True: calls.append(with_argc) or {"entries": [with_argc]}
    try:
        with _memo_builds():
            first = build(False)
            first["entries"].append("改過")
            inside = (build(False), build(True), build(True))
        after = (_BUILD_MEMO, build(False))
    except Exception as exc:        # 暫存邏輯壞掉時記成 FAIL,不讓整個 selftest 以 Traceback 結束
        inside, after = (f"{type(exc).__name__}: {exc}",), None
    finally:
        globals()["_build"] = real_build
    check("區塊內 False / True 各算一次,區塊外再呼叫會重算", calls, [False, True, False])
    check("回傳的是深拷貝:改了第一次的結果,第二次拿到的不受影響", inside[0], {"entries": [False]})
    check("with_argc 不同各拿各的結果(暫存以 with_argc 為鍵)", inside[1:], ({"entries": [True]}, {"entries": [True]}))
    check("離開區塊後恢復為不暫存", after, (None, {"entries": [False]}))

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
        ent(0x20, [0x100]),                                        # 本體沒有乾淨收尾(落進下一個入口)-> 不是 wrapper
    ]
    es[15]["argc"] = 1                                             # spawn(0x200)讀 1 個參數;pan(0x100)argc 不明
    ret = (0x900, 1, "ret", "")
    bodies = {0x10: [(0, 5, "push", "0x28"), (5, 5, "call", "0x3702f"), (10, 1, "push", "5"), (11, 5, "call", "0x200"), (16, 5, "call", "0x100"), ret],
              0x14: [(0, 1, "push", "eax"), (1, 5, "call", "0x200"), (6, 5, "call", "0x10"), ret],
              0x18: [ret], 0x19: [ret], 0x1a: None, 0x1b: [(0, 2, "call", "eax"), ret],
              0x1f: [(0, 5, "call", "0x100"), (5, 5, "call", "0x200"), ret], 0x20: None}
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
    span_only = [ent(0x40, [0x200]), ent(0x200)]
    check("本體乾淨且沒有 call、callees 只來自 span -> 不是 wrapper;沒有本體可看才退回 wrapper",
          (0x40 in structural(span_only, names, {}, set(), {0x40: [ret]}), structural(span_only, names, {}, set())[0x40]["name"]),
          (False, "wrapper(spawn)"))


def _selftest_names(fails: list[str]) -> None:
    def check(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}")
        if not ok:
            fails.append(f"{label}: got {got!r} want {want!r}")

    print("(16) check_names:每一條規則各有一筆違規與一筆合格")
    table = {0x1000: (1, "push", "esi"), 0x1001: (5, "call", "0x500"), 0x100f: (1, "ret", ""), 0x1010: (1, "nop", "")}
    insn_at = table.get
    spans_ = {0x1000: 0x10, 0x1010: 8}
    ok = {"addr": "0x1000", "name": "draw_wait_marker", "summary": "畫等待標記", "confidence": "static_re",
          "evidence": [{"at": "0x1001", "insn": "call 0x500"}, {"at": "0x100f", "insn": "ret"}]}
    check("合格的一筆(含範圍內最後一個 byte 的證據、無運算元的指令)", check_names([ok], spans_, {0x500: "pan"}, insn_at), [])

    def bad(**kw):
        return check_names([{**ok, **kw}], spans_, {0x500: "pan", 0x1010: "spawn"}, insn_at)
    check("addr 不是十六進位", bad(addr="zz"), ["zz draw_wait_marker: addr 不是十六進位"])
    check("addr 不是入口", bad(addr="0x1004"), ["0x1004 draw_wait_marker: addr 不是清單裡的入口"])
    check("其他命名表已命名(證據範圍也跟著換,所以只看這一條)",
          [x for x in bad(addr="0x1010", evidence=[{"at": "0x1010", "insn": "nop"}])], ["0x1010 draw_wait_marker: 其他命名表已命名為 spawn"])
    check("名稱格式", bad(name="DrawMarker"), ["0x1000 DrawMarker: 名稱須為 snake_case"])
    check("與其他命名表撞名", bad(name="pan"), ["0x1000 pan: 名稱重複或與其他命名表撞名"])
    check("watcom_names:單一符號名照收,別名組與模組內 static 記成 None",
          watcom_names({"0x10": {"name": "strcmp"}, "0x20": {"name": "sin|cos"}, "0x30": {"name": "stk+0x0"}}),
          {0x10: "strcmp", 0x20: None, 0x30: None})
    check("Watcom 符號名在同一位址並存:不算錯",
          check_names([ok], spans_, {}, insn_at, None, {0x1000: "__FLDA", 0x500: "strlen"}), [])
    check("Watcom 符號名落在別的位址:撞名",
          check_names([{**ok, "name": "strlen"}], spans_, {}, insn_at, None, {0x500: "strlen"}),
          ["0x1000 strlen: 與 Watcom 函式庫比對在 0x500 的同名符號撞名"])
    check("summary 空白", bad(summary="  "), ["0x1000 draw_wait_marker: summary 不得空"])
    check("confidence 不在清單", bad(confidence="guess"), ["0x1000 draw_wait_marker: confidence 須為 static_re/verified_dynamic"])
    check("verified_dynamic 也合格", bad(confidence="verified_dynamic"), [])
    check("沒有 evidence", bad(evidence=[]), ["0x1000 draw_wait_marker: 沒有 evidence"])
    check("evidence.at 不是十六進位", bad(evidence=[{"at": "q", "insn": "ret"}]), ["0x1000 draw_wait_marker: evidence.at 不是十六進位:q"])
    check("evidence 剛好落在範圍上界(下一個函式的第一個 byte)", bad(evidence=[{"at": "0x1010", "insn": "nop"}]),
          ["0x1000 draw_wait_marker: evidence 0x1010 不在函式範圍 [0x1000, 0x1010) 內"])
    check("evidence 在函式起點之前", bad(evidence=[{"at": "0xfff", "insn": "nop"}]),
          ["0x1000 draw_wait_marker: evidence 0xfff 不在函式範圍 [0x1000, 0x1010) 內"])
    check("evidence 在起點本身要算範圍內", bad(evidence=[{"at": "0x1000", "insn": "push esi"}]), [])
    check("指令文字不符", bad(evidence=[{"at": "0x1001", "insn": "call 0x501"}]),
          ["0x1000 draw_wait_marker: evidence 0x1001 期望 'call 0x501',實際 'call 0x500'"])
    check("該位址解不出指令", bad(evidence=[{"at": "0x1002", "insn": "nop"}]),
          ["0x1000 draw_wait_marker: evidence 0x1002 期望 'nop',實際 None"])
    check("沒有反組譯器:證據無法驗,算錯誤而不是放行", check_names([ok], spans_, {}, None),
          ["0x1000 draw_wait_marker: evidence 0x1001 期望 'call 0x500',實際 None", "0x1000 draw_wait_marker: evidence 0x100f 期望 'ret',實際 None"])
    two = [ok, {**ok, "name": "other_name"}, {**ok, "addr": "0x1010", "evidence": [{"at": "0x1010", "insn": "nop"}]}]
    check("同一 addr 登錄兩次 / 同一名稱用兩次", check_names(two, spans_, {}, insn_at),
          ["0x1000 other_name: addr 重複登錄", "0x1010 draw_wait_marker: 名稱重複或與其他命名表撞名"])

    print("(16b) fixup 證據(跳表第 N 項)與 event_handler_N 名稱:每條規則各有一筆違規與一筆合格")
    T = EVENT_TABLE
    C = 0x51D01
    fx = {T + 4 * 3: 0x1000, T: 0x1000, T + 4 * 5: 0x1010, 0x60000: 0x1000,
          T + 4 * 89: 0x1000, T + 4 * 90: 0x1000, C + 4 * 2: 0x1000}
    ev3 = {"fixup_from": f"{T + 12:#x}", "table": f"{T:#x}", "index": 3}
    h3 = {**ok, "name": "event_handler_3", "evidence": [ev3]}

    def fb(item, fixups=fx):
        return check_names([item], spans_, {}, insn_at, fixups)
    check("合格:只有 fixup 證據、名稱索引一致", fb(h3), [])
    check("合格:索引 0 的邊界", fb({**h3, "name": "event_handler_0",
                                  "evidence": [{"fixup_from": f"{T:#x}", "table": f"{T:#x}", "index": 0}]}), [])
    check("合格:指令證據與 fixup 證據並存", fb({**h3, "evidence": [ev3, {"at": "0x1001", "insn": "call 0x500"}]}), [])
    check("合格:非 event_handler 名稱帶 fixup 證據也可以", fb({**h3, "name": "some_handler"}), [])
    check("沒有 fixup 表:無法驗,算錯誤", fb(h3, None),
          [f"0x1000 event_handler_3: fixup {T + 12:#x} 指向 None,不是 0x1000",
           "0x1000 event_handler_3: 名稱是 0x51b91 表第 3 項,卻沒有通過驗證的該項 fixup 證據"])
    check("合格:表的最後一格(89)", fb({**h3, "name": "event_handler_89",
                                     "evidence": [{"fixup_from": f"{T + 4 * 89:#x}", "table": f"{T:#x}", "index": 89}]}), [])
    check("index 等於格數(90,該處 fixup 存在但已是別的資料)",
          fb({**h3, "name": "x_handler", "evidence": [{"fixup_from": f"{T + 4 * 90:#x}", "table": f"{T:#x}", "index": 90}]}),
          ["0x1000 x_handler: index 90 超出表 0x51b91 的 90 格"])
    ec2 = {"fixup_from": f"{C + 8:#x}", "table": f"{C:#x}", "index": 2}
    check("合格:第二張表 command_handler_N", fb({**h3, "name": "command_handler_2", "evidence": [ec2]}), [])
    check("前綴與表不符:command_handler_3 拿事件表第 3 項", fb({**h3, "name": "command_handler_3"}),
          ["0x1000 command_handler_3: 名稱是 0x51d01 表第 3 項,卻沒有通過驗證的該項 fixup 證據"])
    # 白名單裡的每一張表都跑同一組邊界:最後一格合格、等於格數的 index 被拒、前綴配本表合格、配別張表不合格。
    # 逐表寫死的案例只釘得住寫到的那幾張表;新增一張表時它的格數或前綴被改掉,沒有任何一題會失敗。
    for tb, (cnt, pre, _) in sorted(JUMP_TABLES.items()):
        other = next(t for t in sorted(JUMP_TABLES) if t != tb)
        fxt = {tb + 4 * (cnt - 1): 0x1000, tb + 4 * cnt: 0x1000, tb: 0x1000, other: 0x1000}

        def ev_(t, i):
            return [{"fixup_from": f"{t + 4 * i:#x}", "table": f"{t:#x}", "index": i}]
        got = [fb({**ok, "name": f"{pre}_{cnt - 1}", "evidence": ev_(tb, cnt - 1)}, fxt),
               fb({**ok, "name": "x_handler", "evidence": ev_(tb, cnt)}, fxt),
               fb({**ok, "name": f"{pre}_0", "evidence": ev_(tb, 0)}, fxt),
               fb({**ok, "name": f"{pre}_0", "evidence": ev_(other, 0)}, fxt)]
        check(f"表 {tb:#x}({pre},{cnt} 格):末格合格/越界被拒/前綴配本表合格/配別表不合格",
              [bool(g) for g in got], [False, True, False, True])
    check("表不在白名單(0x60000 的 fixup 確實指向入口,仍不收)",
          fb({**h3, "name": "x_handler", "evidence": [{"fixup_from": "0x60000", "table": "0x60000", "index": 0}]}),
          ["0x1000 x_handler: fixup 證據的表 0x60000 不在已知跳表清單"])
    check("fixup_from 不等於 表+4×index", fb({**h3, "name": "x_handler", "evidence": [{**ev3, "index": 4}]}),
          [f"0x1000 x_handler: fixup_from {T + 12:#x} 不等於 表 {T:#x} + 4×4"])
    check("負索引", fb({**h3, "name": "x_handler", "evidence": [{"fixup_from": f"{T - 4:#x}", "table": f"{T:#x}", "index": -1}]}),
          [f"0x1000 x_handler: fixup_from {T - 4:#x} 不等於 表 {T:#x} + 4×-1"])
    check("fixup 指向別的入口", fb({**h3, "name": "x_handler",
                                  "evidence": [{"fixup_from": f"{T + 20:#x}", "table": f"{T:#x}", "index": 5}]}),
          [f"0x1000 x_handler: fixup {T + 20:#x} 指向 0x1010,不是 0x1000"])
    check("欄位格式錯", fb({**h3, "name": "x_handler", "evidence": [{"fixup_from": "zz", "table": f"{T:#x}", "index": 3}]}),
          ["0x1000 x_handler: fixup 證據欄位格式錯:{'fixup_from': 'zz', 'table': '0x51b91', 'index': 3}"])
    check("event_handler_N 只有指令證據", fb({**ok, "name": "event_handler_3"}),
          ["0x1000 event_handler_3: 名稱是 0x51b91 表第 3 項,卻沒有通過驗證的該項 fixup 證據"])
    check("event_handler_N 的證據是別的索引", fb({**h3, "name": "event_handler_0"}),
          ["0x1000 event_handler_0: 名稱是 0x51b91 表第 0 項,卻沒有通過驗證的該項 fixup 證據"])


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
    check("AIL 104 個進入點全部在清單裡且 strong(AIL_startup 沒有標準前導,列未解析;它的真入口 0x37d3e 由 call 收進來)",
          len(ail) == 104 and all(by.get(a, {}).get("grade") == "strong" for a in ail)
          and 0x37eb7 not in by and by.get(0x37d3e, {}).get("grade") == "strong")
    check("__STK 本身不是入口", CC.STACK_PROBE not in by)
    check("delay 的本體 0x3e01d 只由 thunk 抵達,要以 thunk_target 收進來", "thunk_target" in by.get(0x3e01d, {}).get("signals", []))
    e = by.get(0x35b78, {})
    check("0x35b78(pan_spawn_group)的 callees 含 pan 0x135dd 與 spawn 0x10b4e",
          {"0x135dd", "0x10b4e"} <= set(e.get("callees", [])), str(e.get("callees")))
    check("0x26b91(debits gold)的 globals 含金幣全域 0x53bf3", "0x53bf3" in by.get(0x26b91, {}).get("globals", []),
          str(by.get(0x26b91, {}).get("globals")))
    check("回歸釘值:entries 1356 / strong 1304 / weak 52 / fnptr 422 / eip 1 / island 44 / 內部空隙 15 / call_reached 219"
          "(參考版 EXE 固定,數字變了就是判準變了;2026-10-06 剔除 7 個被反證的 weak,再加函式指標 215 個新入口 + 3 個經它們抵達的 "
          "thunk_target;2026-10-07 加 LE 進入點 1 個與死函式島 44 個,再以呼叫端可達確認 208 個 weak -> strong,"
          "AIL_startup 的假入口 0x37eb7 移除,未確認又解碼不合理的 weak 0x4dddc 移除;同日確認時加跳表 case 種子,"
          "浮點模擬器 opcode 跳表後面的 11 個再升 strong)",
          (m["entries"], m["strong"], m["weak"], m["by_signal"]["fnptr"], m["fnptr_available"], m["by_signal"]["eip"],
           m["by_signal"]["island"], m["island_available"], m["island_interior_gaps"], m["by_signal"].get("call_reached"),
           m["call_reached_available"])
          == (1356, 1304, 52, 422, True, 1, 44, True, 15, 219, True),
          f"{m['entries']}/{m['strong']}/{m['weak']}/{m['by_signal']}/{m.get('island_interior_gaps')}")
    # 呼叫端確認(doc98 續八十四)。正向:有真名、原本只被 CALL 一次的;反向:唯一呼叫端在死函式裡的
    cr_pos = {0x372f9: "fsopen", 0x3cc7d: "rand", 0x3d3a6: "filelength", 0x3da76: "int386x",
              # 呼叫端在浮點模擬器 opcode 跳表(0x4a182 jmp cs:[ebx*4 + 0x49ec4])後面的處理常式裡,要跳表 case 種子才走得到
              0x4c59e: "emu_check_exception", 0x4cd98: "__sqrt",
              # 再下一層:唯一呼叫端在上面那批本體裡(0x4c314 在 emu_fpatan_core 0x4c2a4 內)
              0x4c35a: "emu_atan_core"}
    check("正向控制:只被 CALL 一次但呼叫端可達的有名函式都升為 strong(call + call_reached)",
          all(by.get(a, {}).get("signals") == ["call", "call_reached"] and by[a]["grade"] == "strong" for a in cr_pos),
          str({hex(a): by.get(a, {}).get("signals") for a in cr_pos}))
    cr_neg = {0x46915: "int386xa+0xaa,唯一呼叫端 0x468d3 在死函式 _DoINTR_ 裡", 0x3669a: "唯一呼叫端 0x36822 在死函式 0x367d1 裡",
              0x4d7b4: "IF@DLOG,唯一呼叫端 0x4d80c 在死函式 log 0x4d808 裡"}
    check("未確認又解碼不合理的 weak call 入口不收:只有 0x4dddc(0x4dda3 之後常數資料裡的 E8 命中);"
          "0x4dda3 自己 implausible 也不合格,但已確認(call_reached)所以保留",
          m["call_implausible_dropped"] == ["0x4dddc"] and 0x4dddc not in by
          and "call_reached" in by.get(0x4dda3, {}).get("signals", []),
          str((m["call_implausible_dropped"], by.get(0x4dda3, {}).get("signals"))))
    check("反向控制:唯一呼叫端在死函式裡的維持 weak",
          all(by.get(a, {}).get("grade") == "weak" and "call_reached" not in by[a]["signals"] for a in cr_neg),
          str({hex(a): by.get(a, {}).get("signals") for a in cr_neg}))
    # 死函式島與 LE 進入點(doc98 續八十一)。正向:進入點本身、Watcom 比對認得出的死函式;反向:每個都曾在原型裡被剝出來過
    check("LE 進入點 0x3ccb4(_cstart_)是 eip 入口且 strong(載入器直接跳進來,沒有 CALL / 序頭 / fixup)",
          by.get(0x3ccb4, {}).get("signals") == ["eip"] and by[0x3ccb4]["grade"] == "strong", str(by.get(0x3ccb4)))
    isl_pos = {0x468cb: "_DoINTR_(int386xa 模組,沒人呼叫)", 0x4db0c: "__ModF", 0x4bd87: "__RLDI4", 0x3ca86: "__@DSQRT",
               0x3703f: "__GRO(stk 模組 +0x18,`ret 4`)"}
    check("正向控制:Watcom 函式庫比對認得出的死函式都以 island 收進來、weak",
          all(by.get(a, {}).get("signals") == ["island"] and by[a]["grade"] == "weak" for a in isl_pos),
          str([hex(a) for a in isl_pos if by.get(a, {}).get("signals") != ["island"]]))
    isl_neg = {0x46948: "int386xa 的 `int N ; ret` 樁表第 0 格(fixup 目標,push+ret 計算式跳入)",
               0x46c45: "樁表最後一格", 0x3cb9b: "`jmp cs:[ebx]` 的 case(fixup 目標)",
               0x49de5: "0x49cf5 之後的資料(解碼會重疊、遇 00 00)"}
    check("反向控制:計算式跳躍的落點、資料不是入口", not any(a in by for a in isl_neg),
          str([hex(a) for a in isl_neg if a in by]))
    # 剔除清單逐一人工判讀過(2026-10-06,doc98 續七十八):每個 E8 都落在另一條指令裡
    #   0x2ff40 mov [esp+0xe8],0 的位移 / 0x3cdcb mov eax,gs(8c e8)/ 0x4bf50 shr eax,8(c1 e8 08)/
    #   0x4ca93、0x4cac4 mov ecx,[ebp-0x18](8b 4d e8)/ 0x4ddcc、0x4de10 資料區
    check("剔除的呼叫端 = 人工判讀的 7 個", m["call_sites_validated"] and m["call_sites_dropped"]
          == ["0x2ff40", "0x3cdcb", "0x4bf50", "0x4ca93", "0x4cac4", "0x4ddcc", "0x4de10"], str(m["call_sites_dropped"]))
    check("0x2ff45 不再是入口;spell_cast_scene 0x2ff01 的 span 不再被截在 68 bytes",
          0x2ff45 not in by and by.get(0x2ff01, {}).get("span_upper", 0) > 68, str(by.get(0x2ff01, {}).get("span_upper")))
    img = CC.load_image()
    dec = insn_decoder(img[2], img[3])
    got = dec(0x2ff3d) if dec else None
    check("反證本身可獨立重現:0x2ff3d 解出 11 bytes 的 mov,蓋住 0x2ff40", got is not None and got[0] == 11 and got[1] == "mov",
          str(got))
    check("正向控制:0x4b75f 的 call 0x4c4bd 沒被剔除(線性解碼會失步的區段)",
          by.get(0x4c4bd, {}).get("callers", 0) == 2, str(by.get(0x4c4bd, {}).get("callers")))
    # 函式指標(doc98 續七十九)。正向:每種證據各一個;反向:每個都曾是候選(有正向證據),理由逐一獨立重現。
    pos = {0x4a0c4: "lea edx 後 int 21h AX=2504h 安裝的中斷處理", 0x335a0: "指令表 0x51d01 的 push 0x28;jmp 樁",
           0x49ad8: "mov [0x537f4], 立即值(之後 call [0x537f4])", 0x47d88: "稀疏二維 call 表 0x47988 第 0 格",
           0x37028: "CRT 初始化表(obj2,6 bytes 一筆)", 0x4a362: "call cs:[ebx*4 + 0x49e04] 的表"}
    check("正向控制:各種證據各一個都成 fnptr 入口", all("fnptr" in by.get(a, {}).get("signals", []) for a in pos),
          str([hex(a) for a in pos if "fnptr" not in by.get(a, {}).get("signals", [])]))
    neg = (0x3cd2a, 0x4c646, 0x4cb9c, 0x4a238, 0x47988, 0x40761)
    check("反向控制:字串 / 解碼出界 / 取址後解參考 / 只被 jmp 的槽 / 表頭 / jmp 表的 case 標籤都不是入口",
          not any(a in by for a in neg), str([hex(a) for a in neg if a in by]))
    import disasm_le as D
    code_r, base_r, hi_r = img[2], img[3], img[4]
    fx_r = D.build_fixups(*CC.load_image()[:2])
    no_inside = lambda t: False   # noqa: E731
    check("反向理由可獨立重現:0x3cd2a 是字串(int 21h AH=3Dh 開檔的檔名)、0x4c646 解碼後跳出 obj1",
          dec is not None and [implausible(t, code_r, base_r, hi_r, dec, no_inside) for t in (0x3cd2a, 0x4c646)]
          == ["string", "branch_out"])
    r1 = pointer_refs([0x49915, 0x4a5fe, 0x4cd39], dec, fx_r, code_r, base_r, hi_r) if dec else []
    check("反向理由可獨立重現:0x4cd39 的 lea esi 取 0x4cb9c 後被解參考;0x4a5fe 的 lea edx 存進 [ebp + 0x76];"
          "0x49915 以 call [eax*4 + 0x47988] 把表頭當記憶體運算元",
          [(hex(t), role, reg, deref, slot) for _, t, role, reg, deref, slot in r1]
          == [("0x47988", "call", True, False, None), ("0x4a238", "lea", False, False, "[ebp + 0x76]"),
              ("0x4cb9c", "lea", False, True, None)], str(r1))
    ops_r = [(g[1], g[2]) for g in (dec(0x4a47c), dec(0x4a64a))] if dec else []
    check("[ebp + 0x76] 只被 notrack jmp 使用(0x4a47c、0x4a64a 等),是續行點的槽", "[ebp + 0x76]" in jmp_only_slots(ops_r),
          str(ops_r))
    check("takers:AIL 以 mov [eax + 0x20], 立即值登記的回呼 0x40c40 只被 0x40cf0 取址",
          by.get(0x40c40, {}).get("takers") == ["0x40cf0"], str(by.get(0x40c40, {}).get("takers")))
    from callgraph_le import CG
    tr: dict = {}
    discover_fnptr(lambda: CG(CC.EXE), {a for a, x in by.items() if x["signals"] != ["fnptr"]} - {0x46186, 0x46306, 0x4dc3a},
                   code_r, base_r, hi_r, fx_r, dec, tr)
    check("case 標籤真的當了種子:0x4a5fe(0x40684 那類 jmp 表之後的 case 本體)只有經 case 標籤才走得到;"
          "0x40761 在 case 集合;3 輪收斂",
          0x4a5fe in tr.get("reached", ()) and 0x40761 in tr.get("cases", ()) and tr.get("rounds") == 3,
          f"rounds={tr.get('rounds')} cases={len(tr.get('cases', ()))}")
    check("0x46186 只能經 fnptr 入口 0x3cf1c 的 jmp 抵達:以 thunk_target 收進來",
          by.get(0x46186, {}).get("signals") == ["thunk_target"] and by.get(0x3cf1c, {}).get("signals") == ["fnptr"])
    check("每筆 span_upper > 0 且總和 = 最後入口之後到 hi 的整段",
          all(x["span_upper"] > 0 for x in inv["entries"])
          and sum(x["span_upper"] for x in inv["entries"]) == int(m["image_range"][1], 16) - min(by))
    # 繞過 _memo_builds 的暫存:這一項要的是真的再算一次(計數沒增加 = 拿暫存跟自己比)
    runs0 = _BUILD_RUNS
    again = _build(with_argc=False)
    check("重建兩次逐位元組相同(真的重算,不是拿暫存)", dump(inv) == dump(again) and _BUILD_RUNS == runs0 + 1,
          f"runs {runs0} -> {_BUILD_RUNS}")
    print("(15) 真實 EXE:結構性命名")
    # 釘值用「不含 function_names.json」的版本:登錄新名字會改變誰是 wrapper、誰已有真名,那是預期中的變動,
    # 不該每登一批就來改釘值;含登錄表的版本由下面「已提交產物逐位元組相同」那一條管。
    sd = build_structural(include_registry=False)
    # 2026-10-06 第二次:加 Watcom 函式庫名稱 -> wrapper +10(被呼叫者有了名字,例 0x370f0 = segread + int386x)、
    # leaf -3(0x37af4/0x37b55/0x3cf26 改有真名);「本體乾淨且沒有 call」不算 wrapper -> wrapper -1(0x4670c)
    # 2026-10-07:死函式島成入口 -> 0x43160 多了死函式 0x43210 這個呼叫端,不再只被 AIL 呼叫(ail_only -1、wrapper +1);
    # 0x4670c 的 span 被 island 0x46715 截到 9 bytes,成 leaf_get[0x52814](leaf_global +1)
    # 同日再以呼叫端可達確認 208 個 weak -> strong:結構性命名只對 strong,AIL 內部只被呼叫一次的輔助大批進來(ail_only +115)
    check("回歸釘值(不含登錄表):thunk 7 / ail_only 169 / wrapper 115 / leaf_global 119 / leaf_ptr 72 / leaf_pure 34"
          "(2026-10-07 呼叫端確認後;死函式島後 7/54/114/100/69/29,前一版 7/55/113/99/69/29,再前 7/55/104/99/71/30,"
          "更早 4/30/105/16/16/11)",
          sd["_meta"]["by_kind"] == {"thunk": 7, "ail_only": 169, "wrapper": 115, "leaf_global": 119, "leaf_ptr": 72,
                                     "leaf_pure": 34},
          str(sd["_meta"]["by_kind"]))
    check("span 蓋到下一個沒列入口的函式的不算 wrapper:0x37028(蓋到 __CHK 0x3702f);0x4670c 的 span 改以死函式 0x46715 為界後"
          "是 leaf_get[0x52814]",
          "0x37028" not in sd["names"] and sd["names"].get("0x4670c", {}).get("name") == "leaf_get[0x52814]",
          str((sd["names"].get("0x37028"), sd["names"].get("0x4670c"))))
    check("0x2185f 依呼叫順序帶參數:先 play_sfx 再 sprite_walk_on",
          sd["names"].get("0x2185f", {}).get("name") == "wrapper(play_sfx(_, 2, 1), sprite_walk_on(_, 0xf, 0xa))", str(sd["names"].get("0x2185f")))
    check("0x20707 的常數參數讀得出來(兩次 unit_inactive 的單位編號)",
          sd["names"].get("0x20707", {}).get("name") == "wrapper(raw_result_code_0_1_2(), unit_inactive(0x32), unit_inactive(0x33))",
          str(sd["names"].get("0x20707")))
    plain = [a for a, v in sd["names"].items() if v["kind"] == "wrapper" and "(" not in v["name"][len("wrapper("):]]
    # 原本唯一的一個是 0x4670c(本體沒有 call,callees 全來自 span),2026-10-06 起不算 wrapper
    check("退回不帶參數的 wrapper 為 0 個(本體的 CALL 與 callees 不一致)", len(plain) == 0, str(plain))
    check("反組譯器可用時 _meta 如實標示", sd["_meta"]["disasm_available"] is True)
    check("0x364fb(解鎖後釋放的記憶體輔助,24 個呼叫端全在 AIL 內)= ail_only", sd["names"].get("0x364fb", {}).get("kind") == "ail_only")
    full = build_structural()
    real = real_names()
    check("有真名的入口(含登錄表)一個都不會被結構性命名", not any(int(a, 16) in real for a in full["names"]))
    check("每一筆都是 strong 入口", all(by[int(a, 16)]["grade"] == "strong" for a in sd["names"]))
    errs = run_check_names()
    check(f"function_names.json 的 {len(load_function_names())} 筆全部通過位元組證據檢查", not errs, "; ".join(errs[:3]))
    # 求完整的回歸看守(doc98 續九十四):每個入口都要有名稱;新增入口沒命名、或名稱被刪,就在這裡失敗
    nm_all = load_names()
    unnamed_all = [e["addr"] for e in inv["entries"] if not (nm_all.get(int(e["addr"], 16)) or {}).get("name")]
    check(f"全部 {len(inv['entries'])} 個入口都有名稱(登錄表 / Watcom / AIL)", not unnamed_all, str(unnamed_all[:5]))
    nm_wo = load_names(include_registry=False)
    check("反向控制:不含登錄表時有上百個入口沒有名稱(上一項不是空轉)",
          sum(1 for e in inv["entries"] if not (nm_wo.get(int(e["addr"], 16)) or {}).get("name")) > 100)
    _selftest_live_exec(check, inv)
    # 事件跳表的正向控制:doc25 L950 記 slot 82 指向舊版 0x35f92,新版 +0x356 = 0x362e8(續三十勘誤)。
    # 表基底或 fixup 解析錯了,這題先失敗,而不是讓所有 event_handler_N 一起變成「fixup 指向別處」。
    import disasm_le as D
    data_l, meta_l = CC.load_image()[:2]
    fx_l = D.build_fixups(data_l, meta_l)
    check("事件跳表第 82 項的 fixup 指向 0x362e8(doc25 L950 舊 0x35f92 + 0x356)", fx_l.get(EVENT_TABLE + 4 * 82) == 0x362E8,
          f"實際 {fx_l.get(EVENT_TABLE + 4 * 82)}")
    check("TAI phase 表第 5 項指向 0x2c441、第 10 項沒有 fixup(doc35 §9.2 逐 byte 核對的表)",
          fx_l.get(0x524C6 + 4 * 5) == 0x2C441 and (0x524C6 + 4 * 10) not in fx_l, f"實際 {fx_l.get(0x524C6 + 4 * 5)}")
    sc = ROOT / "docs" / "data" / "function_structural_names.json"
    if sc.exists():
        check("已提交的結構性命名產物與現算(含登錄表)逐位元組相同", sc.read_text(encoding="utf-8") == dump(full))
    committed = ROOT / "docs" / "data" / "function_inventory.json"
    if committed.exists():
        old = json.loads(committed.read_text(encoding="utf-8"))
        strip = lambda d: [{k: v for k, v in x.items() if k != "argc"} for x in d["entries"]]   # noqa: E731
        check("已提交產物(不看 argc)與現算相同", strip(old) == strip(inv))
    return True


def load_live_exec() -> tuple[set[int], dict]:
    """`live_exec_addresses.json` -> (實機執行位址, _meta);格式不對 ValueError(`read_export` 的檢查)。"""
    import verify_dead_functions_vs_traces as V
    return V.read_export(LIVE_EXEC_JSON.read_text(encoding="utf-8"))


def _selftest_live_exec(check, inv: dict) -> None:
    """靜態「沒有執行路徑」對原版實機執行位址的反驗(續九十七)。"""
    import hashlib
    import verify_address_claim_coverage as CC
    import verify_dead_functions_vs_traces as V
    try:
        live, lm = load_live_exec()
    except (OSError, ValueError, KeyError) as exc:
        check("live_exec_addresses.json 讀得到且格式正確", False, f"{type(exc).__name__}: {exc}")
        return
    check("live_exec_addresses.json 的 exe_md5 與靜態分析的 FD2.EXE 相同",
          lm["exe_md5"] == hashlib.md5(open(CC.EXE, "rb").read()).hexdigest(), lm["exe_md5"])
    _, _, code, base, _ = CC.load_image()
    insn_at = insn_decoder(code, base)
    if insn_at is None:
        check("實機反驗需要 capstone(本體邊界)", False)
        return
    sp = {int(e["addr"], 16): e["span_upper"] for e in inv["entries"]}
    names_hex = {n["addr"]: n for n in load_function_names()}
    dead = V.claimed_dead(inv["entries"], names_hex)
    hits = dead_body_hits(dead, sp, insn_at, live)
    check(f"{len(dead)} 個靜態判為沒有執行路徑的入口,本體指令沒有一條出現在 {lm['traces_distinct']} 份原版實機軌跡裡",
          not hits, str({hex(a): [hex(x) for x in h[:3]] for a, h in list(hits.items())[:3]}))
    # 正向控制:同一份資料用 span 當本體,0x46915 會命中共用樁 0x4698a(int 16h)/ 0x469db(int 31h)。
    # 這證明位址換算與資料都對得上,上一項通過靠的是本體邊界,不是資料沒涵蓋到。
    tail = set(V.body_hits({0x46915: sp[0x46915]}, sorted(live)).get(0x46915, []))
    check("正向控制:以 span 當本體時 0x46915 命中共用樁 0x4698a / 0x469db", {0x4698A, 0x469DB} <= tail, str(sorted(tail)[:4]))
    # 反向控制:把每個死入口自己的位址加進執行集合,每一個都要被抓到(檢查不是空轉)
    check("反向控制:注入死入口位址後每一個都被抓到", set(dead_body_hits(dead, sp, insn_at, live | dead)) == dead)
    check("已知活入口 int386x_dispatch 0x468a7 有執行紀錄", 0x468A7 in live)
    n_entry = sum(1 for a in sp if a in live)
    check(f"入口位址出現在實機軌跡裡 {n_entry} 個,不少於 LIVE_ENTRY_FLOOR {LIVE_ENTRY_FLOOR}(重匯出不能變少)",
          n_entry >= LIVE_ENTRY_FLOOR, str(n_entry))


def selftest() -> int:
    fails: list[str] = []
    _selftest_pure(fails)
    _selftest_structural(fails)
    _selftest_names(fails)
    try:
        with _memo_builds():
            live = _selftest_live(fails)
    except RuntimeError as exc:
        # 不動點的輪數保護(`CONFIRM_MAX_ROUNDS` / `FNPTR_MAX_ROUNDS`)觸發 = 判準壞了沒收斂,記成 FAIL 而不是當掉
        live = True
        fails.append(f"真實 EXE:build 沒有收斂 {exc}")
        print(f"    FAIL: 真實 EXE:build 沒有收斂  [{exc}]")
    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(8 組清單純函式 + 7 組結構性命名純函式 + 1 組名稱登錄表規則的成對案例"
          + (" + 真實 EXE 的 49 項交叉核對)。" if live else ";真實 EXE 部分 SKIP)。"))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="FD2.EXE obj1 的函式入口清單(位元組訊號為骨架)")
    ap.add_argument("out", nargs="?", help="寫出 function_inventory.json 的路徑")
    ap.add_argument("--coverage", action="store_true", help="命名/記載覆蓋率")
    ap.add_argument("--unnamed", action="store_true", help="列出無名的 strong 入口")
    ap.add_argument("--limit", type=int, default=None, help="--unnamed 的列數上限")
    ap.add_argument("--ghidra-export", metavar="PATH", help="與 Ghidra 的 FD2_disasm_full.txt 對照")
    ap.add_argument("--structural", metavar="OUT", help="寫出結構性自動命名 function_structural_names.json")
    ap.add_argument("--check-names", action="store_true", help="驗 function_names.json 每一筆的位元組證據")
    ap.add_argument("--card", metavar="ADDR", help="一個入口的事實卡與本體反組譯")
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
    if a.check_names:
        errs = run_check_names()
        for x in errs:
            print("  FAIL", x)
        print(f"function_names.json:{len(load_function_names())} 筆," + (f"{len(errs)} 個錯誤" if errs else "全部通過"))
        return 1 if errs else 0
    if a.card:
        return report_card(a.card)
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
