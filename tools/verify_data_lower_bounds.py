#!/usr/bin/env python3
"""verify_data_lower_bounds.py —— data_map 每段的長度**下限**:程式碼實際定址到哪裡,逐段對 FD2.EXE 算出來。

為什麼有這支
------------
`re_coverage.py --check` 只證明長度**上限**(直接定址的存取不跨出區段);`verify_data_types.py` 補上了字串與
函式指標表的下限,但「只有索引存取的陣列」(`0x52a94`、`0x541b4`、`0x5417c`、`0x541f4`)仍寫在「仍未證」:
`[eax + 0x541b4]` 這種存取,re_coverage 只看得到位移 `0x541b4`,看不到 eax 會跑到多少,陣列登成 4 byte 也通過。
2026-11-11 使用者要求「先做一支工具證明只用索引存取的陣列的長度下限」。

下限的意思是「程式碼定址到區段起點 + N 為止」:陣列短於 N 就會被程式自己寫出界。它是**程式碼的定址範圍**,
不是實機觀察(迴圈若提早 break,執行期不一定走到最後一格;但那一格的位址是程式碼寫出來的,和直接定址同一個標準)。

證據分兩級,互不混算
--------------------
存取證據(access)—— 指令真的讀寫那些 byte:
* direct  沒有基底 / 索引暫存器的記憶體運算元:[位移, 位移 + 寬度)。
* loop    索引存取 `[R + 位移]`、`[R * s + 位移]`,或 `[Q + 位移]` 且 Q 在迴圈體內由 `mov Q, R` / `shl Q, k` 算出;
          R 是迴圈計數器,迴圈形狀必須逐項成立才採信(任何一項不成立就列為「未解出」,附原因):
            - 包住存取的最內層向後條件跳躍,前一條是 `cmp R, 立即數` 或 `test R, R`;迴圈體內沒有其他向後跳躍;
            - 迴圈體內 R 只被寫一次:位在存取之後、比較之前的 `inc` / `dec` / `add R, 立即數` / `sub R, 立即數`;
              `call` 視為改寫 eax / ecx / edx、`int` 視為改寫全部通用暫存器;
            - 遞增那一條不能被迴圈體內的向前跳躍繞過;
            - 唯一入口:迴圈起點前一條就是初值(`mov R, 立即數` / `xor R, R`),或前一條是跳到比較的 `jmp`、再前一條是
              初值;整個程式(不只本函式)沒有其他跳躍跳進初值之後、迴圈體或比較裡;
          計數器的值由「初值、步長、比較條件(有號 / 無號)」逐次模擬,不套公式;超過 MAX_ITERS 次不採信。
* rep     `rep stos*` / `rep movs*` 所在基本區塊內(往回到前一條分支 / call / ret / int,或第一條跳躍目標為止,
          不限條數)`mov edi, 位址(有 fixup)` 與 `mov ecx, 立即數`;長度 = ecx × 寬度,緊接的非 rep `movs*` / `stos*`
          依序加上(內嵌 strcpy 的尾巴)。函式內有 `std` 就不採信(Watcom / C 呼叫約定在函式邊界 DF = 0)。
          (續二百六十二用固定 4 條視窗,漏掉 `ecx` 在前 5 條的 9 個 rep;續二百六十三改成基本區塊。)
* chain   一串連續非 rep `movs*` / `stos*`(前一條不是 rep 或同類字串指令),edi 在同一基本區塊內由
          `mov edi, 位址(有 fixup)` 設定:長度 = 各條寬度之和(沒有 rep 的內嵌 strcpy,例 `0x4469b` 19 byte)。
* ptr     指標追蹤:`call` 所在基本區塊內有立即數(有 fixup)指到某段,就從區塊開頭逐條執行(trace)到這個
          call 返回,跨進被呼叫的函式;經暫存器定址、位址由 fixup 推得的存取依指標來源歸段。只走直線,遇到條件
          跳躍等就停,停之前的存取仍採信。前提(平面模式、`int` 不改 esp 以上的堆疊、data_map 區段不是堆疊)
          寫在 trace 的說明。例:`int386` 的 out 參數在 `0x46897` 寫 `[edi + 0x18]` → `0x53a8d` 28 byte。

變數值證據(value)—— 比 access 弱:索引在同一基本區塊內由 `mov R, [V]` / `movzx R, [V]` 載入(前 VALUE_WINDOW 條內、
          中間沒有分支也沒有跳躍目標),V 是直接定址的變數;下限取「程式寫進 V 的最大立即數」(`mov [V], 立即數`,
          寫入寬度等於載入寬度)。**沒有證明那個值一定流到這次讀取**(讀取前若另有檢查擋掉,就到不了),所以單獨分級。
          V 的任何一個立即數會定址出區段時,整筆不採信(列為未解出,附出界的值):那代表 V 不是單純的索引
          (例如 `[0x51a8f]` 的 255 是「沒有事件」哨兵,讀取前另有檢查),不另挑塞得下的值充當下限。

宣告證據(declared)—— 程式把這段的長度當參數交出去,但不保證真的用到:
* range   `push 長度` / `push 位址(有 fixup)` / `call F`,F 由結構辨認為 DPMI 鎖定 / 解鎖範圍的包裝
          (F 開頭 `mov eax, [esp + 4]` / `add eax, [esp + 8]` 算出結束位址並呼叫 G;G 內有 `mov dword [esp], 0x600`
          或 `0x601` 與 `push 0x31` + `call`,即 int386(0x31) 的 DPMI 0600h / 0601h)。

核對與失敗條件(--check 以這些 exit 1)
--------------------------------------
* 任何證據的範圍跑出它所在區段(低於起點,或超過 start + size)→ 失敗:區段登短了,或迴圈跑進鄰段。
* 宣告長度大於 size → 失敗。
* 本工具解出的記憶體運算元位置,必須和 re_coverage 的指令層存取(kind "mem")逐筆相同;對不上 → 失敗
  (兩條解碼路徑互相核對,避免本工具少看存取而顯得乾淨)。
* 下限小於 size 不算失敗:列為 partial,附缺口、未解出的索引存取與原因(清單誠實列出,不靠沒讀到而乾淨)。

用法
----
    python tools/verify_data_lower_bounds.py              # 摘要 + 下限未達 size 的區段
    python tools/verify_data_lower_bounds.py --verbose    # 每段都列
    python tools/verify_data_lower_bounds.py --check
    python tools/verify_data_lower_bounds.py --show 0x541b4
    python tools/verify_data_lower_bounds.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

M32 = 0xFFFFFFFF
# 計數器模擬的次數上限(FD2 的迴圈最多 256 次;超過就不採信,避免把無窮迴圈當成有界)
MAX_ITERS = 4096
# 索引暫存器的載入要在存取前幾條內(FD2 實際是緊接的前一條)
VALUE_WINDOW = 4

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp")
FULL: dict[str, str] = {}
for _r in "abcd":
    for _n in (f"{_r}l", f"{_r}h", f"{_r}x", f"e{_r}x"):
        FULL[_n] = f"e{_r}x"
for _r in ("si", "di", "bp", "sp"):
    FULL[_r] = FULL["e" + _r] = "e" + _r
CALL_CLOBBER = frozenset(("eax", "ecx", "edx"))
COND = frozenset(("jb", "jae", "jbe", "ja", "jl", "jge", "jle", "jg", "jne", "je", "js", "jns"))
STEP = {"inc": 1, "dec": -1, "add": 1, "sub": -1}
REP = {"rep stosd": 4, "rep stosw": 2, "rep stosb": 1, "rep movsd": 4, "rep movsw": 2, "rep movsb": 1}
TAIL = {"stosd": 4, "stosw": 2, "stosb": 1, "movsd": 4, "movsw": 2, "movsb": 1}
# 存取證據的種類(judge 取這些的最遠位置當 access 下限)
ACCESS_KINDS = ("direct", "loop", "rep", "chain", "ptr")


class Mem(NamedTuple):
    """記憶體運算元:基底、索引(32 位元名稱或 None)、倍率、位移(有 fixup 時是線性位址)、寬度。"""
    base: str | None
    index: str | None
    scale: int
    disp: int
    width: int


class Ins(NamedTuple):
    """分析用的指令摘要;selftest 直接建構,真實檔由 capstone 轉換。

    regs 是每個運算元的暫存器(32 位元名稱;不是暫存器的運算元為 None)。
    """
    addr: int
    mn: str
    regs: tuple[str | None, ...]
    imm: int | None
    imm_fx: bool
    mem: Mem | None
    writes: frozenset[str]
    target: int | None


def _signed(v: int) -> int:
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


def taken(mn: str, v: int, k: int) -> bool:
    """`cmp v, k` 之後條件跳躍 mn 會不會跳(32 位元;有號 / 無號依助記符)。"""
    u, uk = v & M32, k & M32
    s, sk = _signed(u), _signed(uk)
    return {"jb": u < uk, "jae": u >= uk, "jbe": u <= uk, "ja": u > uk,
            "jl": s < sk, "jge": s >= sk, "jle": s <= sk, "jg": s > sk,
            "jne": u != uk, "je": u == uk,
            "js": _signed(u - uk) < 0, "jns": _signed(u - uk) >= 0}[mn]


def simulate(init: int, step: int, mn: str, k: int, top_tested: bool) -> list[int] | None:
    """逐次模擬計數器在迴圈體裡出現的值;超過 MAX_ITERS 次回傳 None。"""
    vals: list[int] = []
    v = init & M32
    if top_tested and not taken(mn, v, k):
        return vals
    while len(vals) < MAX_ITERS:
        vals.append(_signed(v))
        v = (v + step) & M32
        if not taken(mn, v, k):
            return vals
    return None


def branch_sources(func_lists: list[list[Ins]]) -> dict[int, set[int]]:
    """全部指令的跳躍目標 → 來源位址集合(call 不算;迴圈入口核對用)。"""
    out: dict[int, set[int]] = {}
    for lst in func_lists:
        for x in lst:
            if x.target is not None and (x.mn == "jmp" or x.mn in COND):
                out.setdefault(x.target, set()).add(x.addr)
    return out


def _writes(x: Ins, r: str) -> bool:
    if x.mn == "call":
        return r in CALL_CLOBBER or r in x.writes
    if x.mn == "int":
        return True
    return r in x.writes


def resolve_loop(lst: list[Ins], ia: int, srcs: dict[int, set[int]]) -> tuple[dict | None, str]:
    """解出 lst[ia] 這筆索引存取在迴圈裡的位移範圍。

    Returns:
        ({"lo", "hi", "counter", "values", "loop"}, "") 或 (None, 不採信的原因)。lo / hi 是相對 disp 的 byte 位移,
        hi 已含存取寬度(範圍是 [disp + lo, disp + hi))。
    """
    a = lst[ia]
    m = a.mem
    if m is None or (m.base is None and m.index is None):
        return None, "不是索引存取"
    if m.base is not None and m.index is not None:
        return None, "基底與索引都是暫存器"
    # 最內層的向後條件跳躍
    cands = [j for j in range(ia + 1, len(lst))
             if lst[j].mn in COND and lst[j].target is not None and lst[j].target <= a.addr]
    if not cands:
        return None, "不在迴圈內(後面沒有跳回存取之前的條件跳躍)"
    ij = max(cands, key=lambda j: (lst[j].target, -j))
    t = lst[ij].target
    it = next((i for i, x in enumerate(lst) if x.addr == t), None)
    if it is None:
        return None, f"迴圈起點 {hex(t)} 不在指令邊界"
    if it == 0:
        return None, f"迴圈起點 {hex(t)} 是函式第一條(函式清單內看不到初值)"
    for k in range(it, ij):
        x = lst[k]
        if x.target is not None and (x.mn == "jmp" or x.mn in COND) and x.target <= x.addr \
                and lst[it].addr <= x.target:
            return None, f"迴圈體內另有向後跳躍 {hex(x.addr)}(巢狀迴圈)"
    cmp = lst[ij - 1]
    if cmp.mn == "cmp" and len(cmp.regs) == 2 and cmp.regs[0] and cmp.regs[1] is None and cmp.imm is not None:
        r, k_imm = cmp.regs[0], cmp.imm
    elif cmp.mn == "test" and len(cmp.regs) == 2 and None not in cmp.regs and len(set(cmp.regs)) == 1:
        (r,), k_imm = set(cmp.regs), 0
    else:
        return None, f"迴圈條件 {hex(cmp.addr)} 不是 cmp R, 立即數 / test R, R"
    # 位移運算式:R 本身,或由 R 算出的 Q
    q = m.base if m.base is not None else m.index
    mult = m.scale if m.index is not None else 1
    if q != r:
        p = max((i for i in range(it, ia) if _writes(lst[i], q)), default=None)
        if p is None or p - 1 < it:
            return None, f"索引暫存器 {q} 不是計數器 {r},也不是在迴圈體內由它算出"
        sh, mv = lst[p], lst[p - 1]
        if not (sh.mn == "shl" and sh.regs[:1] == (q,) and sh.imm is not None
                and mv.mn == "mov" and mv.regs == (q, r)):
            return None, f"{q} 不是由 mov {q}, {r} / shl {q}, k 算出"
        if any(srcs.get(x.addr) for x in lst[p:ia + 1]):
            return None, f"{q} 的推導與存取之間有跳躍目標"
        mult *= 1 << sh.imm
    # 迴圈體內 R 只寫一次,在存取之後、比較之前
    ws = [i for i in range(it, ij - 1) if _writes(lst[i], r)]
    if len(ws) != 1:
        return None, f"迴圈體內寫 {r} 的指令有 {len(ws)} 條(要恰好 1 條遞增 / 遞減)"
    iu = ws[0]
    u = lst[iu]
    if not ia < iu or u.mn not in STEP or u.regs[:1] != (r,):
        return None, f"{hex(u.addr)} 不是存取之後的 inc / dec / add / sub {r}"
    if u.mn in ("add", "sub"):
        if u.imm is None or u.imm_fx or not 0 < u.imm < 0x10000:
            return None, f"{hex(u.addr)} 的步長不是正的立即數"
        step = STEP[u.mn] * u.imm
    else:
        step = STEP[u.mn]
    for x in lst[it:iu]:
        if x.target is not None and u.addr < x.target <= lst[ij].addr:
            return None, f"{hex(x.addr)} 可以跳過遞增 {hex(u.addr)}"
    # 唯一入口與初值
    prev = lst[it - 1]
    top = prev.mn == "jmp" and prev.target == cmp.addr
    ii = it - 2 if top else it - 1
    if ii < 0:
        return None, "迴圈前沒有初值指令"
    init = lst[ii]
    if init.mn == "mov" and init.regs[:1] == (r,) and init.imm is not None and not init.imm_fx:
        v0 = init.imm
    elif init.mn in ("xor", "sub") and init.regs == (r, r):
        v0 = 0
    else:
        return None, f"迴圈前一條 {hex(init.addr)} 不是 {r} 的立即數初值"
    for tgt, ss in srcs.items():
        if not lst[ii].addr < tgt <= lst[ij].addr:
            continue
        outside = {s for s in ss if not lst[it].addr <= s <= lst[ij].addr}
        if top and tgt == cmp.addr:
            outside.discard(prev.addr)
        if outside:
            return None, f"{sorted(hex(s) for s in outside)} 從迴圈外跳進 {hex(tgt)}"
    vals = simulate(v0, step, lst[ij].mn, k_imm, top)
    if vals is None:
        return None, f"計數器模擬超過 {MAX_ITERS} 次"
    if not vals:
        return None, "迴圈體一次都不會執行"
    offs = [v * mult for v in vals]
    return ({"lo": min(offs), "hi": max(offs) + m.width, "counter": r, "values": (min(vals), max(vals)),
             "loop": (lst[it].addr, lst[ij].addr)}, "")


def _block_setters(lst: list[Ins], i: int, srcs: dict[int, set[int]], regs: tuple[str, ...]) -> dict[str, Ins]:
    """從 lst[i] 往回掃到所在基本區塊的開頭,回傳 regs 中每個暫存器最近一次被寫的指令。

    區塊開頭 = 前一條分支 / call / ret / int 之後,或第一條身為跳躍目標的指令(那一條本身屬於區塊)。
    沒有條數上限:續二百六十二的 REP_WINDOW = 4 漏掉 9 個 `ecx` 在前 5 條設定的 rep(0x40f35 等)。
    """
    got: dict[str, Ins] = {}
    for x in reversed(lst[:i]):
        if x.mn in ("jmp", "call", "ret", "int") or x.mn in COND:
            break
        for r in regs:
            if r not in got and _writes(x, r):
                got[r] = x
        if srcs.get(x.addr):
            break
    return got


def rep_extent(lst: list[Ins], i: int, srcs: dict[int, set[int]], has_std: bool) -> tuple[dict | None, str]:
    """lst[i] 是 rep stos / movs:回傳 ({"start", "len"}, "") 或 (None, 原因)。"""
    w = REP[lst[i].mn]
    if has_std:
        return None, "函式內有 std"
    got = _block_setters(lst, i, srcs, ("edi", "ecx"))
    edi, ecx = got.get("edi"), got.get("ecx")
    if edi is None or ecx is None:
        return None, "同一基本區塊內找不到 edi / ecx 的設定"
    if not (edi.mn == "mov" and edi.regs[:1] == ("edi",) and edi.imm is not None and edi.imm_fx):
        return None, f"{hex(edi.addr)} 不是 mov edi, 位址(有 fixup)"
    if not (ecx.mn == "mov" and ecx.regs[:1] == ("ecx",) and ecx.imm is not None and not ecx.imm_fx):
        return None, f"{hex(ecx.addr)} 不是 mov ecx, 立即數"
    first = min(edi.addr, ecx.addr)
    if any(srcs.get(a) for a in [x.addr for x in lst if first < x.addr <= lst[i].addr]):
        return None, "設定與 rep 之間有跳躍目標"
    n = ecx.imm * w
    fam = lst[i].mn[4:8]
    k = i + 1
    while k < len(lst) and lst[k].mn in TAIL and lst[k].mn.startswith(fam):
        n += TAIL[lst[k].mn]
        k += 1
    return {"start": edi.imm, "len": n}, ""


def chain_extent(lst: list[Ins], i: int, srcs: dict[int, set[int]], has_std: bool) -> tuple[dict | None, str]:
    """lst[i] 是一串連續非 rep `movs*` / `stos*` 的第一條(前一條不是 rep 或同類字串指令):
    回傳 ({"start", "len"}, "") 或 (None, 原因)。

    例:`0x4468c` `mov edi, 0x541f4` / `mov esi, 0x51624` / `mov eax, -1` / 4 × movsd / movsw / movsb = 19 byte
    (內嵌 strcpy 沒有 rep 的形式)。edi 要在同一基本區塊內由 `mov edi, 位址(有 fixup)` 設定;
    設定到串尾之間不能有跳躍目標。
    """
    if has_std:
        return None, "函式內有 std"
    fam = lst[i].mn[:4]
    got = _block_setters(lst, i, srcs, ("edi",))
    edi = got.get("edi")
    if edi is None:
        return None, "同一基本區塊內找不到 edi 的設定"
    if not (edi.mn == "mov" and edi.regs[:1] == ("edi",) and edi.imm is not None and edi.imm_fx):
        return None, f"{hex(edi.addr)} 不是 mov edi, 位址(有 fixup)"
    n, k = 0, i
    while k < len(lst) and lst[k].mn in TAIL and lst[k].mn.startswith(fam):
        n += TAIL[lst[k].mn]
        k += 1
    if any(srcs.get(x.addr) for x in lst if edi.addr < x.addr <= lst[k - 1].addr):
        return None, "設定與字串指令之間有跳躍目標"
    return {"start": edi.imm, "len": n}, ""


def _suffix_at(funcs: dict[int, list[Ins]], addr: int) -> list[Ins]:
    """從 addr 那條指令起到所在函式結尾(尾端 jmp 跳進別的函式中段時用);找不到回傳空清單。"""
    for lst in funcs.values():
        for i, x in enumerate(lst):
            if x.addr == addr:
                return lst[i:]
    return []


def index_load(lst: list[Ins], i: int, srcs: dict[int, set[int]]) -> tuple[tuple[int, int, int] | None, str]:
    """lst[i] 的索引暫存器是不是剛由變數載入。

    Returns:
        ((變數位址, 載入寬度, 倍率), "") 或 (None, 原因)。
    """
    m = lst[i].mem
    if m is None or (m.base is None) == (m.index is None):
        return None, "不是單一暫存器索引"
    q = m.base if m.base is not None else m.index
    mult = m.scale if m.index is not None else 1
    for j in reversed(range(max(0, i - VALUE_WINDOW), i)):
        x = lst[j]
        if x.mn in ("jmp", "call", "ret", "int") or x.mn in COND or srcs.get(lst[j + 1].addr):
            return None, "載入與存取之間有分支或跳躍目標"
        if _writes(x, q):
            if x.mn in ("mov", "movzx") and x.regs[:1] == (q,) and x.mem is not None                     and x.mem.base is None and x.mem.index is None:
                return (x.mem.disp, x.mem.width, mult), ""
            return None, f"{hex(x.addr)} 寫 {q},不是由變數載入"
    return None, f"前 {VALUE_WINDOW} 條內沒有載入 {q}"


def range_fn_kind(f: list[Ins], funcs: dict[int, list[Ins]]) -> str | None:
    """F 是不是 DPMI 鎖定 / 解鎖範圍的包裝(結構辨認);是就回傳 "lock" / "unlock"。

    G 設好功能號後可以用最後一條 `jmp` 跳進另一個函式的中段共用 int386 呼叫(FD2 的 unlock 就是這樣),
    只跟這一次;功能號只看 G 本身。
    """
    if len(f) < 3:
        return None
    a0, a1 = f[0], f[1]
    if not (a0.mn == "mov" and a0.regs[:1] == ("eax",) and a0.mem == Mem("esp", None, 1, 4, 4)):
        return None
    if not (a1.mn == "add" and a1.regs[:1] == ("eax",) and a1.mem == Mem("esp", None, 1, 8, 4)):
        return None
    for x in f[2:]:
        if x.mn != "call" or x.target not in funcs:
            continue
        g = funcs[x.target]
        kinds = {y.imm for y in g if y.mn == "mov" and y.mem == Mem("esp", None, 1, 0, 4) and y.imm in (0x600, 0x601)}
        tail = _suffix_at(funcs, g[-1].target) if g and g[-1].mn == "jmp" and g[-1].target is not None else []
        h = g + tail
        dpmi = any(h[j].mn == "push" and h[j].imm == 0x31 and h[j + 1].mn == "call" for j in range(len(h) - 1))
        if len(kinds) == 1 and dpmi:
            return "lock" if kinds == {0x600} else "unlock"
    return None


# ---------------------------------------------------------------- 指標追蹤(ptr)
#
# 值:("a", n, b) 由 fixup 來的線性位址 n(加減一般數值仍是位址;b 是那個 fixup 的目標,存取依 b 歸段,
# 指標跑出它來源的區段就和迴圈跑進鄰段一樣算失敗)、("c", n) 一般數值(有號 32 位元)、
# ("s", k) 追蹤起點 esp + k 的堆疊位址、("g", 名稱) 追蹤起點的區段暫存器值、None 未知。
# 沒有 fixup 的立即數永遠只是數值:LE 載入時只重定位有 fixup 的欄位,數值剛好等於某個位址不代表指到那裡。

MAX_TRACE = 4000
SEG = ("cs", "ds", "es", "fs", "gs", "ss")
GPR32 = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
HIGH8 = frozenset(("ah", "bh", "ch", "dh"))
# 平面模式(DOS/4GW)ds = es = ss:用起點的這三個值定址都等同直接定址
FLAT = frozenset((("g", "ds"), ("g", "es"), ("g", "ss")))


class Decoder:
    """位址 → capstone 指令(快取);fixups 是欄位位置 → 線性位址。"""

    def __init__(self, md: object, code: bytes, base: int, fixups: dict[int, int]) -> None:
        self.md, self.code, self.base, self.fx = md, code, base, fixups
        self._cache: dict[int, object | None] = {}

    def at(self, addr: int) -> object | None:
        if addr not in self._cache:
            off = addr - self.base
            x = None
            if 0 <= off < len(self.code):
                x = next(iter(self.md.disasm(self.code[off:off + 16], addr)), None)
            self._cache[addr] = x
        return self._cache[addr]


class _Stop(Exception):
    """追蹤停止(原因字串)。停止前記下的存取仍然有效:那些指令在每一條從追蹤起點出發的路徑上都會執行。"""


def _add(a: tuple | None, b: tuple | None) -> tuple | None:
    if a is None or b is None:
        return None
    if a[0] == "c" and b[0] == "c":
        return ("c", _signed(a[1] + b[1]))
    if a[0] == "c":
        a, b = b, a
    if b[0] != "c" or a[0] not in ("a", "s"):
        return None
    return ("a", (a[1] + b[1]) & M32, a[2]) if a[0] == "a" else ("s", a[1] + b[1])


def _neg(a: tuple | None) -> tuple | None:
    return ("c", _signed(-a[1])) if a is not None and a[0] == "c" else None


def trace(dec: Decoder, start: int, call: int, regions: list[tuple[int, int]]) -> tuple[list[tuple], str]:
    """從 start 起逐條執行到 call 這一條 call 返回為止,記下經暫存器定址、位址已知的記憶體存取。

    追蹤只走直線:遇到條件跳躍、`loop`、rep 字串指令、間接跳躍到未知位址、esp 不再是堆疊位址等就停;
    停之前的存取仍採信(它們在每一條從 start 出發的路徑上都會執行)。起點的暫存器全部未知。

    前提(寫在這裡,不由本函式證明):
      - 平面模式:起點的 ds / es / ss 指向同一個平面區段,所以用它們定址等同直接定址;
      - `int n` 返回到下一條,esp 與 esp 以上的堆疊內容不變;通用暫存器視為未知、esp 以下的內容丟棄;
        int 前若有暫存器持有堆疊位址(處理程式可能寫那個緩衝區),整個堆疊模型丟棄;
      - data_map 區段不是堆疊:寫到區段內的位址不影響堆疊模型(寫到其他已知位址、未知位址就整個丟棄)。

    Returns:
        ([(指令位址, 線性位址, 寬度, 指標來源的 fixup 目標), ...], 停止原因;正常返回時是 "")。
    """
    from capstone import CS_AC_WRITE
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

    regs: dict[str, tuple | None] = {r: None for r in GPR32}
    regs["esp"] = ("s", 0)
    segs: dict[str, tuple | None] = {s: ("g", s) for s in SEG}
    mem: dict[int, tuple[int, tuple | None]] = {}
    acc: list[tuple] = []
    ret_slot: list[int] = []

    def in_region(n: int) -> bool:
        return any(s <= n < e for s, e in regions)

    def rd_slot(k: int, w: int) -> tuple | None:
        e = mem.get(k)
        if e is None or e[0] < w:
            return None
        v = e[1]
        if e[0] == w or v is None:
            return v
        if v[0] == "c":
            return ("c", _signed(v[1] & ((1 << (8 * w)) - 1)))
        return v if v[0] == "g" and w == 2 else None

    def wr_slot(k: int, w: int, v: tuple | None) -> None:
        for o in [o for o, (ow, _v) in mem.items() if o < k + w and k < o + ow]:
            del mem[o]
        mem[k] = (w, v)

    def rd_reg(name: str, w: int) -> tuple | None:
        if name in SEG:
            return segs[name]
        v = regs.get(FULL.get(name, ""))
        if w == 4 or v is None:
            return v
        if v[0] == "g":
            return v if w == 2 else None
        if v[0] != "c":
            return None
        n = v[1] & M32
        n = (n >> 8) & 0xFF if name in HIGH8 else n & ((1 << (8 * w)) - 1)
        return ("c", n)

    def wr_reg(name: str, w: int, v: tuple | None) -> None:
        if name in SEG:
            if name == "ss":
                raise _Stop("改寫 ss")
            segs[name] = v if v is not None and v[0] == "g" else None
            return
        full = FULL.get(name)
        if full is None:
            raise _Stop(f"不認得的暫存器 {name}")
        if full == "esp" and (w != 4 or v is None or v[0] != "s"):
            raise _Stop("esp 不再是已知堆疊位址")
        if w == 4:
            regs[full] = v
            return
        old = regs[full]
        if v is not None and v[0] == "g" and w == 2:
            regs[full] = v
        elif v is not None and v[0] == "c" and old is not None and old[0] == "c" and name not in HIGH8:
            m = (1 << (8 * w)) - 1
            regs[full] = ("c", _signed((old[1] & M32 & ~m) | (v[1] & m)))
        else:
            regs[full] = None

    def ea(x: object, op: object) -> tuple | None:
        m = op.mem
        site = x.address + x.disp_offset
        v = ("a", dec.fx[site], dec.fx[site]) if x.disp_offset and site in dec.fx else ("c", _signed(m.disp))
        if m.base:
            v = _add(v, regs.get(FULL.get(x.reg_name(m.base), "")))
        if m.index:
            iv = regs.get(FULL.get(x.reg_name(m.index), ""))
            v = _add(v, iv if m.scale == 1 else (("c", _signed(iv[1] * m.scale)) if iv and iv[0] == "c" else None))
        return v

    def seg_of(x: object, op: object) -> str:
        if op.mem.segment:
            return x.reg_name(op.mem.segment)
        b = x.reg_name(op.mem.base) if op.mem.base else ""
        return "ss" if b in ("esp", "ebp") else "ds"

    def touch(x: object, op: object, write: bool, v: tuple | None = None) -> tuple | None:
        """一個記憶體運算元:記存取、讀出或寫入值(堆疊模型)。"""
        a = ea(x, op)
        if a is not None and a[0] == "a" and (op.mem.base or op.mem.index) \
                and segs.get(seg_of(x, op)) in FLAT:
            acc.append((x.address, a[1], op.size, a[2]))
        if a is not None and a[0] == "s":
            if write:
                wr_slot(a[1], op.size, v)
                return None
            return rd_slot(a[1], op.size)
        if write and not (a is not None and a[0] == "a" and in_region(a[1])):
            mem.clear()
        return None

    def val(x: object, op: object) -> tuple | None:
        if op.type == X86_OP_REG:
            return rd_reg(x.reg_name(op.reg), op.size)
        if op.type == X86_OP_IMM:
            site = x.address + x.imm_offset
            return ("a", dec.fx[site], dec.fx[site]) if site in dec.fx else ("c", _signed(op.imm))
        return touch(x, op, False)

    def put(x: object, op: object, v: tuple | None) -> None:
        if op.type == X86_OP_REG:
            wr_reg(x.reg_name(op.reg), op.size, v)
        else:
            touch(x, op, True, v)

    def push(v: tuple | None) -> None:
        sp = _add(regs["esp"], ("c", -4))
        wr_reg("esp", 4, sp)
        wr_slot(sp[1], 4, v)

    def pop() -> tuple | None:
        sp = regs["esp"]
        v = rd_slot(sp[1], 4)
        wr_reg("esp", 4, _add(sp, ("c", 4)))
        return v

    def target(v: tuple | None) -> int:
        if v is None or v[0] != "a":
            raise _Stop("跳躍目標不是已知位址")
        return v[1]

    pc = start
    try:
        for _step in range(MAX_TRACE):
            x = dec.at(pc)
            if x is None:
                raise _Stop(f"{hex(pc)} 無法解碼")
            mn, ops, nxt = x.mnemonic, x.operands, pc + x.size
            if x.prefix[2] == 0x66 and mn in ("push", "pop", "call", "ret", "leave"):
                raise _Stop(f"{hex(pc)} 16 位元堆疊操作")
            if mn.startswith(("rep", "loop")) or (mn.startswith("j") and mn != "jmp"):
                raise _Stop(f"{hex(pc)} {mn}")
            if mn == "push" and len(ops) == 1:
                push(val(x, ops[0]))
            elif mn == "pop" and len(ops) == 1:
                if ops[0].type == X86_OP_MEM and ops[0].mem.base and x.reg_name(ops[0].mem.base) == "esp":
                    raise _Stop(f"{hex(pc)} pop 到 esp 定址的記憶體")
                put(x, ops[0], pop())
            elif mn == "mov" and len(ops) == 2:
                put(x, ops[0], val(x, ops[1]))
            elif mn in ("movzx", "movsx") and len(ops) == 2:
                v = val(x, ops[1])
                if v is not None and v[0] == "c":
                    n = v[1] & ((1 << (8 * ops[1].size)) - 1)
                    if mn == "movsx" and n >> (8 * ops[1].size - 1):
                        n -= 1 << (8 * ops[1].size)
                    v = ("c", _signed(n))
                else:
                    v = None
                put(x, ops[0], v)
            elif mn == "lea" and len(ops) == 2 and ops[0].size == 4:
                wr_reg(x.reg_name(ops[0].reg), 4, ea(x, ops[1]))
            elif mn in ("xor", "sub") and len(ops) == 2 and ops[0].type == ops[1].type == X86_OP_REG \
                    and ops[0].reg == ops[1].reg:
                wr_reg(x.reg_name(ops[0].reg), ops[0].size, ("c", 0))
            elif mn in ("add", "sub") and len(ops) == 2 and ops[0].type == X86_OP_REG and ops[0].size == 4:
                d = x.reg_name(ops[0].reg)
                b = val(x, ops[1])
                wr_reg(d, 4, _add(regs[d], b if mn == "add" else _neg(b)))
            elif mn in ("inc", "dec") and len(ops) == 1 and ops[0].type == X86_OP_REG and ops[0].size == 4:
                d = x.reg_name(ops[0].reg)
                wr_reg(d, 4, _add(regs[d], ("c", 1 if mn == "inc" else -1)))
            elif mn == "leave":
                wr_reg("esp", 4, regs["ebp"])
                regs["ebp"] = pop()
            elif mn == "call" and len(ops) == 1:
                t = dec.fx.get(pc + x.imm_offset, ops[0].imm & M32) if ops[0].type == X86_OP_IMM \
                    else target(val(x, ops[0]))
                push(("a", nxt, nxt))
                if pc == call and not ret_slot:
                    ret_slot.append(regs["esp"][1])
                nxt = t
            elif mn == "ret":
                sp = regs["esp"][1]
                t = pop()
                if ops:
                    wr_reg("esp", 4, _add(regs["esp"], ("c", ops[0].imm)))
                if ret_slot and sp >= ret_slot[0]:
                    return acc, "" if sp == ret_slot[0] else "返回時 esp 跑過呼叫點"
                nxt = target(t)
            elif mn == "jmp" and len(ops) == 1:
                nxt = (ops[0].imm & M32) if ops[0].type == X86_OP_IMM else target(val(x, ops[0]))
            elif mn in ("int", "int3", "into", "int1"):
                if any(v is not None and v[0] == "s" for r, v in regs.items() if r != "esp"):
                    mem.clear()
                for r in GPR32:
                    if r != "esp":
                        regs[r] = None
                sp = regs["esp"][1]
                for o in [o for o in mem if o < sp]:
                    del mem[o]
            elif mn in ("iret", "iretd", "retf", "hlt", "ljmp", "lcall", "enter", "pushal", "popal", "pushad",
                        "popad", "pushfd", "popfd", "pushf", "popf", "std"):
                raise _Stop(f"{hex(pc)} {mn}")
            else:
                # 其他指令:記憶體運算元照記存取;寫入的暫存器變未知;寫記憶體依位址更新堆疊模型。
                # nop / lea 的記憶體運算元只是位址,不存取記憶體(16 位元 lea 會落到這裡,見 (10ag))
                for op in ops:
                    if op.type == X86_OP_MEM and mn not in ("nop", "lea"):
                        touch(x, op, bool(op.access & CS_AC_WRITE), None)
                _rd, wr = x.regs_access()
                for r in (x.reg_name(k) for k in wr):
                    if r in ("esp", "sp", "ss"):
                        raise _Stop(f"{hex(pc)} {mn} 改寫 {r}")
                    if r in SEG:
                        segs[r] = None
                    elif r in FULL:
                        regs[FULL[r]] = None
            pc = nxt
        raise _Stop(f"超過 {MAX_TRACE} 條")
    except _Stop as e:
        return acc, str(e)


def block_start(lst: list[Ins], i: int, srcs: dict[int, set[int]]) -> int:
    """lst[i] 所在基本區塊的第一條的索引(前一條分支 / call / ret / int 之後,或跳躍目標本身)。"""
    b = i
    while b > 0 and not srcs.get(lst[b].addr):
        y = lst[b - 1]
        if y.mn in ("jmp", "call", "ret", "int") or y.mn in COND:
            break
        b -= 1
    return b


def collect(funcs: dict[int, list[Ins]], regions: list[tuple[int, int]], dec: Decoder | None = None) -> dict:
    """掃全部函式,蒐集每段的證據、未解出的索引存取、記憶體運算元位置。

    dec 不是 None 時另做指標追蹤:每個 `call` 所在基本區塊內有立即數(有 fixup)指到某一段,就從區塊開頭
    逐條執行到這個 call 返回(trace),經暫存器定址、位址已知的存取記為 ptr 證據(以 call 位址為鍵)。
    """
    lists = list(funcs.values())
    srcs = branch_sources(lists)
    ranged = {a: k for a, f in funcs.items() if (k := range_fn_kind(f, funcs))}

    def region_of(addr: int) -> tuple[int, int] | None:
        return next(((s, e) for s, e in regions if s <= addr < e), None)

    # 變數位址 → {寫入寬度: 立即數集合}(`mov [V], 立即數`)
    imm_w: dict[int, dict[int, set[int]]] = {}
    for lst in lists:
        for x in lst:
            if x.mn == "mov" and x.mem is not None and x.mem.base is None and x.mem.index is None                     and x.imm is not None and not x.imm_fx:
                imm_w.setdefault(x.mem.disp, {}).setdefault(x.mem.width, set()).add(
                    x.imm & ((1 << (8 * x.mem.width)) - 1))
    wit: dict[int, dict] = {s: {"direct": {}, "loop": {}, "rep": {}, "chain": {}, "ptr": {}, "range": {}, "value": {},
                                "unresolved": {}, "mem_sites": set()}
                            for s, _e in regions}
    for lst in lists:
        has_std = any(x.mn == "std" for x in lst)
        for i, x in enumerate(lst):
            if x.mem is not None and x.mem.base not in ("esp", "ebp") and (reg := region_of(x.mem.disp)):
                w = wit[reg[0]]
                w["mem_sites"].add(x.addr)
                if x.mem.base is None and x.mem.index is None:
                    w["direct"][x.addr] = (x.mem.disp, x.mem.disp + x.mem.width)
                else:
                    res, why = resolve_loop(lst, i, srcs)
                    if res is None:
                        w["unresolved"][x.addr] = why
                        ld, _why2 = index_load(lst, i, srcs)
                        vals = imm_w.get(ld[0], {}).get(ld[1], set()) if ld else set()
                        out = sorted(v for v in vals if x.mem.disp + v * ld[2] + x.mem.width > reg[1]) if ld else []
                        if ld and vals and out:
                            w["unresolved"][x.addr] = (f"{why};索引取自 [{hex(ld[0])}],但它的立即數 {out} "
                                                       f"會定址出區段(不是單純索引,不採信)")
                        elif ld and vals:
                            v = max(vals)
                            w["value"][x.addr] = (x.mem.disp, x.mem.disp + v * ld[2] + x.mem.width, ld[0], v)
                    else:
                        w["loop"][x.addr] = (x.mem.disp + res["lo"], x.mem.disp + res["hi"], res)
            if x.mn in REP:
                res, why = rep_extent(lst, i, srcs, has_std)
                if res is not None and (reg := region_of(res["start"])):
                    wit[reg[0]]["rep"][x.addr] = (res["start"], res["start"] + res["len"])
            elif x.mn in TAIL and not (i and (lst[i - 1].mn in REP or lst[i - 1].mn in TAIL)):
                res, why = chain_extent(lst, i, srcs, has_std)
                if res is not None and (reg := region_of(res["start"])):
                    wit[reg[0]]["chain"][x.addr] = (res["start"], res["start"] + res["len"])
            if x.mn == "call" and x.target in ranged and i >= 2:
                pa, pn = lst[i - 1], lst[i - 2]
                if pa.mn == "push" and pa.imm_fx and pn.mn == "push" and pn.imm is not None and not pn.imm_fx \
                        and not srcs.get(pa.addr) and not srcs.get(x.addr) and (reg := region_of(pa.imm)):
                    wit[reg[0]]["range"][x.addr] = (pa.imm, pa.imm + pn.imm, ranged[x.target])
            if dec is not None and x.mn == "call":
                b = block_start(lst, i, srcs)
                if any(y.imm_fx and y.imm is not None and region_of(y.imm) for y in lst[b:i]):
                    acc, why = trace(dec, lst[b].addr, x.addr, regions)
                    per: dict[int, list[tuple]] = {}
                    for site, a, wd, src in acc:
                        if reg := region_of(src):
                            per.setdefault(reg[0], []).append((site, a, wd))
                    for s, hits in per.items():
                        wit[s]["ptr"][x.addr] = (min(a for _s, a, _w in hits), max(a + wd for _s, a, wd in hits),
                                                 {"start": lst[b].addr, "hits": hits, "stop": why})
    return {"wit": wit, "ranged": ranged}


# 原程式本身的越界寫入(2026-11-18):type 寫 `0x2ba21 迴圈多寫 4 byte`,代表那條指令的定址範圍
# 正好是 [start, end + 4)。只放行逐字相符的那一條;宣告了卻沒看到、或多寫的量不同都算失敗。
_OVERRUN = re.compile(r"(0x[0-9a-f]+) 迴圈多寫 (\d+) byte")


def declared_overruns(t: str) -> dict[int, int]:
    """type 裡宣告的原程式越界:{指令位址: 超出區段尾端的 byte 數}。"""
    return {int(a, 16): int(n) for a, n in _OVERRUN.findall(t)}


def judge(start: int, size: int, w: dict, cov_sites: set[int], content: bool = False,
          overruns: dict[int, int] | None = None) -> dict:
    """一段的結論:access / declared 下限、等級、失敗。

    content 為 True 代表 verify_data_types 已以內容證明整段(C 字串逐 byte + NUL、函式指標表每格 fixup)。
    overruns 是 type 宣告的原程式越界(declared_overruns):那條指令的範圍必須正好是 [start, end + N),
    才不算失敗;宣告了而沒有那條指令、或範圍不同,都失敗。越界的部分不計入下限。
    """
    end = start + size
    fail: list[str] = []
    lb_access = 0
    over = dict(overruns or {})
    for kind in ACCESS_KINDS:
        for ins, (lo, hi, *_r) in w[kind].items():
            if ins in over and lo == start and hi == end + over[ins]:
                over.pop(ins)
            elif lo < start or hi > end:
                fail.append(f"{hex(start)}: {kind} {hex(ins)} 定址 [{hex(lo)}, {hex(hi)}) 跑出區段 "
                            f"[{hex(start)}, {hex(end)})")
            lb_access = max(lb_access, min(hi, end) - start)
    for ins, n in over.items():
        fail.append(f"{hex(start)}: type 宣告 {hex(ins)} 迴圈多寫 {n} byte,但沒有那條指令定址 "
                    f"[{hex(start)}, {hex(end + n)})")
    lb_value = max((min(hi, end) - start for lo, hi, _var, _v in w["value"].values()), default=0)
    lb_decl = 0
    for ins, (lo, hi, _k) in w["range"].items():
        if lo != start or hi > end:
            fail.append(f"{hex(start)}: range {hex(ins)} 宣告 [{hex(lo)}, {hex(hi)}) 與區段 [{hex(start)}, {hex(end)}) 不合")
        lb_decl = max(lb_decl, min(hi, end) - start)
    if w["mem_sites"] != cov_sites:
        only_me = sorted(hex(a) for a in w["mem_sites"] - cov_sites)
        only_cov = sorted(hex(a) for a in cov_sites - w["mem_sites"])
        fail.append(f"{hex(start)}: 記憶體運算元與 re_coverage 存取不一致:只有本工具 {only_me},只有 re_coverage {only_cov}")
    if lb_access == size:
        grade = "access"
    elif content:
        grade = "content"
    elif max(lb_access, lb_value) == size:
        grade = "value"
    elif lb_decl == size:
        grade = "declared"
    else:
        grade = "partial"
    return {"lb_access": lb_access, "lb_value": lb_value, "lb_declared": lb_decl, "grade": grade, "fail": fail}


# ---------------------------------------------------------------- 讀原版

def conv(md: object, fx1: dict[int, int], x: object) -> Ins:
    """capstone 指令 → Ins(立即數 / 位移有 fixup 時換成線性位址)。"""
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

    regs: list[str | None] = []
    imm, imm_site, mem, target = None, None, None, None
    for op in x.operands:
        if op.type == X86_OP_REG:
            regs.append(FULL.get(md.reg_name(op.reg)))
        else:
            regs.append(None)
        if op.type == X86_OP_IMM:
            imm_site = x.address + x.imm_offset
            imm = fx1[imm_site] if imm_site in fx1 else op.imm & M32
        elif op.type == X86_OP_MEM:
            site = x.address + x.disp_offset
            disp = fx1[site] if x.disp_offset and site in fx1 else op.mem.disp & M32
            mem = Mem(FULL.get(md.reg_name(op.mem.base)) if op.mem.base else None,
                      FULL.get(md.reg_name(op.mem.index)) if op.mem.index else None,
                      op.mem.scale, disp,
                      # 遠指標載入讀 offset + 2 byte selector(與 re_coverage.FAR_LOADS 相同,2026-11-19)
                      op.size + 2 if x.mnemonic in ("lds", "les", "lfs", "lgs", "lss") else op.size)
    imm_fx = imm_site in fx1
    if (x.mnemonic == "jmp" or x.mnemonic in COND or x.mnemonic == "call") and imm is not None and not imm_fx:
        target = imm
    _rd, wr = x.regs_access()
    writes = frozenset(FULL[n] for n in (md.reg_name(r) for r in wr) if n in FULL)
    return Ins(x.address, x.mnemonic, tuple(regs), imm, imm_fx, mem if x.mnemonic != "lea" else None,
               writes, target)


def load() -> tuple[dict[int, list[Ins]], list[dict], dict[int, set[int]], set[int], Decoder]:
    """回傳 (函式入口 → 指令摘要清單, data_map regions, 區段起點 → re_coverage mem 存取的指令位址,
    verify_data_types 以內容證明整段的區段起點, 指標追蹤用的解碼器)。"""
    import disasm_le
    import le_xref
    import re_coverage as R
    import verify_data_types as V
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    facts, regions = V.load_facts()
    content = set()
    for r in regions:
        x = V.check_region(r, facts)
        if x["claim"]["kind"] in ("cstring", "fptr_table") and not x["fail"]:
            content.add(int(r["start"], 16))
    inv = json.loads(R.INVENTORY.read_text(encoding="utf-8"))["entries"]
    exe = (R.game_dir() / "FD2.EXE").read_bytes()
    meta = le_xref.parse_le(exe)
    code, cbase = disasm_le.load_code(exe, meta)
    fx1 = disasm_le.build_fixups(exe, meta, {1})
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    funcs: dict[int, list[Ins]] = {}
    for e in inv:
        a = int(e["addr"], 16)
        funcs[a] = [conv(md, fx1, x) for x in disasm_le.sweep_range(md, code, cbase, a, a + e["span_upper"])
                    if not isinstance(x, tuple)]
    cov: dict[int, set[int]] = {}
    spans = [(int(r["start"], 16), int(r["start"], 16) + r["size"]) for r in regions]
    for ins, t, _width, _rw, kind, _indexed in facts.accesses:
        if kind != "mem":
            continue
        for s, e in spans:
            if s <= t < e:
                cov.setdefault(s, set()).add(ins)
    return funcs, regions, cov, content, Decoder(md, code, cbase, fx1)


def run(funcs: dict[int, list[Ins]], regions: list[dict], cov: dict[int, set[int]],
        content: set[int], dec: Decoder | None = None) -> tuple[list, dict]:
    spans = [(int(r["start"], 16), int(r["start"], 16) + r["size"]) for r in regions]
    col = collect(funcs, spans, dec)
    out = []
    for r in regions:
        s = int(r["start"], 16)
        out.append((r, col["wit"][s], judge(s, r["size"], col["wit"][s], cov.get(s, set()), s in content,
                                            declared_overruns(r.get("type", "")))))
    return out, col


def _describe(r: dict, w: dict, j: dict) -> list[str]:
    s = int(r["start"], 16)
    lines = [f"{r['start']:>8} {r['size']:4d} {r.get('name', ''):28} {j['grade']:8} 存取下限 {j['lb_access']:4d} "
             f"變數值 {j['lb_value']:4d} 宣告 {j['lb_declared']:4d}  direct {len(w['direct'])} loop {len(w['loop'])} "
             f"rep {len(w['rep'])} chain {len(w['chain'])} ptr {len(w['ptr'])} value {len(w['value'])} "
             f"range {len(w['range'])} 未解出 {len(w['unresolved'])}"]
    best = [(hi, kind, ins) for kind in ACCESS_KINDS for ins, (lo, hi, *_x) in w[kind].items()]
    if best:
        hi, kind, ins = max(best)
        lines.append(f"           最遠:{kind} {hex(ins)} → +{hex(min(hi, s + r['size']) - s)}")
    return lines


def report(out: list, col: dict, verbose: bool) -> int:
    nfail = sum(1 for *_x, j in out if j["fail"])
    grades: dict[str, int] = {}
    for *_x, j in out:
        grades[j["grade"]] = grades.get(j["grade"], 0) + 1
    unres = sum(len(w["unresolved"]) for _r, w, _j in out)
    loops = sum(len(w["loop"]) for _r, w, _j in out)
    print(f"data_map 長度下限:{len(out)} 段;失敗 {nfail}")
    print(f"  等級 {dict(sorted(grades.items()))}(access = 存取證據達 size;content = verify_data_types 以內容證明;"
          f"value = 加上變數值證據才達 size;declared = 只有宣告長度達 size)")
    print(f"  記憶體運算元與 re_coverage 指令層存取逐筆核對 {sum(len(w['mem_sites']) for _r, w, _j in out)} 筆")
    print(f"  索引存取:迴圈解出 {loops} 筆、迴圈解不出 {unres} 筆(其中變數值證據 "
          f"{sum(len(w['value']) for _r, w, _j in out)} 筆);rep {sum(len(w['rep']) for _r, w, _j in out)} 筆、"
          f"非 rep 字串串 {sum(len(w['chain']) for _r, w, _j in out)} 筆、"
          f"指標追蹤 {sum(len(w['ptr']) for _r, w, _j in out)} 個呼叫點;"
          f"DPMI 範圍呼叫 {sum(len(w['range']) for _r, w, _j in out)} 筆(範圍函式 "
          f"{sorted((hex(a), k) for a, k in col['ranged'].items())})")
    for r, w, j in out:
        if verbose or j["fail"] or j["grade"] in ("value", "declared", "partial"):
            for ln in _describe(r, w, j):
                print(ln)
            for ins, why in sorted(w["unresolved"].items()):
                print(f"           未解出 {hex(ins)}:{why}")
            for e in j["fail"]:
                print(f"    FAIL {e}")
    return 1 if nfail else 0


def show(out: list, addr: int) -> int:
    hit = [(r, w, j) for r, w, j in out if int(r["start"], 16) <= addr < int(r["start"], 16) + r["size"]]
    if not hit:
        print(f"{hex(addr)} 不在任何已登錄區段")
        return 1
    r, w, j = hit[0]
    for ln in _describe(r, w, j):
        print(ln)
    for kind in (*ACCESS_KINDS, "value", "range"):
        for ins, (lo, hi, *x) in sorted(w[kind].items()):
            extra = ""
            if kind == "loop":
                d = x[0]
                extra = f"  計數器 {d['counter']} ∈ [{d['values'][0]}, {d['values'][1]}],迴圈 " \
                        f"[{hex(d['loop'][0])}, {hex(d['loop'][1])}]"
            elif kind == "range":
                extra = f"  {x[0]}"
            elif kind == "value":
                extra = f"  索引取自 [{hex(x[0])}],最大立即數寫入 {x[1]}"
            elif kind == "ptr":
                d = x[0]
                far = max(d["hits"], key=lambda h: h[1] + h[2])
                extra = (f"  追蹤起點 {hex(d['start'])},{len(d['hits'])} 筆經暫存器存取,最遠 {hex(far[0])} "
                         f"[{hex(far[1])}, +{far[2]});停止:{d['stop'] or '返回呼叫點'}")
            print(f"  {kind:6} {hex(ins)} [{hex(lo)}, {hex(hi)}){extra}")
    for ins, why in sorted(w["unresolved"].items()):
        print(f"  未解出 {hex(ins)}:{why}")
    for e in j["fail"]:
        print(f"  FAIL {e}")
    return 1 if j["fail"] else 0


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'PASS' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    def I(addr: int, mn: str, regs: tuple = (), imm: int | None = None, fx: bool = False,
          mem: Mem | None = None, writes: tuple = (), target: int | None = None) -> Ins:
        return Ins(addr, mn, regs, imm, fx, mem, frozenset(writes), target)

    B = 0x541B4
    # (1) 0x3fa58 形:xor ecx; jmp cmp; mov eax, ecx; shl eax, 2; cmp [eax+B], 0; inc ecx; cmp ecx, 16; jb
    def loop_a(k: int = 0x10, jcc: str = "jb", init: Ins | None = None, extra: list | None = None,
               inc: Ins | None = None) -> list[Ins]:
        body = [I(0x14, "mov", ("eax", "ecx"), writes=("eax",)),
                I(0x16, "shl", ("eax", None), 2, writes=("eax",)),
                I(0x19, "cmp", (None, None), 0, mem=Mem("eax", None, 1, B, 4))]
        body += extra or []
        return [I(0x00, "push", ("esi",)),
                init or I(0x10, "xor", ("ecx", "ecx"), writes=("ecx",)),
                I(0x12, "jmp", (None,), 0x2A, target=0x2A)] + body + [
                inc or I(0x29, "inc", ("ecx",), writes=("ecx",)),
                I(0x2A, "cmp", ("ecx", None), k),
                I(0x2D, jcc, (None,), 0x14, target=0x14),
                I(0x2F, "ret")]

    def lo_hi(lst: list[Ins], ia: int = 5) -> tuple | str:
        res, why = resolve_loop(lst, ia, branch_sources([lst]))
        return (res["lo"], res["hi"]) if res else why

    check("(1a) 頂端測試迴圈 ecx 0..15、shl 2 → [0, 64)", lo_hi(loop_a()) == (0, 64))
    check("(1b) 上界 0x20 → [0, 128)", lo_hi(loop_a(0x20)) == (0, 128))
    check("(1c) jbe → 多一格 [0, 68)", lo_hi(loop_a(jcc="jbe")) == (0, 68))
    check("(1d) 初值 mov ecx, 3 → [12, 64)",
          lo_hi(loop_a(init=I(0x10, "mov", ("ecx", None), 3, writes=("ecx",)))) == (12, 64))
    check("(1e) 初值有 fixup 不採信",
          "立即數初值" in str(lo_hi(loop_a(init=I(0x10, "mov", ("ecx", None), 3, True, writes=("ecx",))))))
    check("(1f) 初值不是計數器不採信",
          "立即數初值" in str(lo_hi(loop_a(init=I(0x10, "xor", ("edx", "edx"), writes=("edx",))))))
    check("(1g) 迴圈體內另寫計數器不採信",
          "有 2 條" in str(lo_hi(loop_a(extra=[I(0x20, "mov", ("ecx", None), 0, writes=("ecx",))]))))
    check("(1h) 迴圈體內 call 改寫 ecx 不採信",
          "有 2 條" in str(lo_hi(loop_a(extra=[I(0x20, "call", (None,), 0x100, target=0x100)]))))
    check("(1i) shl 改寫成別的暫存器來源不採信",
          "不是由 mov eax, ecx" in str(lo_hi([*loop_a()[:3], I(0x14, "mov", ("eax", "edx"), writes=("eax",)), *loop_a()[4:]])))
    check("(1j) add ecx, 2 步長 → 0, 2, .., 14 → [0, 60)",
          lo_hi(loop_a(inc=I(0x29, "add", ("ecx", None), 2, writes=("ecx",)))) == (0, 60))
    check("(1k) 遞增在存取之前不採信",
          "存取之後" in str(lo_hi([*loop_a()[:3], I(0x14, "inc", ("ecx",), writes=("ecx",)),
                                    I(0x15, "mov", ("eax", "ecx"), writes=("eax",)), *loop_a()[4:6],
                                    *loop_a()[7:]], ia=6)))
    # 從外面跳進迴圈體 / 繞過遞增
    la = loop_a()
    check("(1l) 迴圈外跳進迴圈體不採信",
          "從迴圈外跳進" in resolve_loop(la, 5, branch_sources([la, [I(0x900, "jmp", (None,), 0x29, target=0x29)]]))[1])
    check("(1q) 跳進索引推導與存取之間不採信",
          "推導與存取之間" in resolve_loop(la, 5, branch_sources([la, [I(0x900, "jmp", (None,), 0x16, target=0x16)]]))[1])
    check("(1m) 迴圈外跳進比較(不是入口 jmp)不採信",
          "從迴圈外跳進" in resolve_loop(la, 5, branch_sources([la, [I(0x900, "jne", (None,), 0x2A, target=0x2A)]]))[1])
    check("(1n) 迴圈體內向前跳過遞增不採信",
          "跳過遞增" in str(lo_hi(loop_a(extra=[I(0x20, "jne", (None,), 0x2A, target=0x2A)]))))
    check("(1o) 迴圈體內跳出迴圈(提早 break)仍採信",
          lo_hi(loop_a(extra=[I(0x20, "jne", (None,), 0x2F, target=0x2F)])) == (0, 64))
    check("(1p) 跳進初值之後的位置不採信",
          "從迴圈外跳進" in resolve_loop(la, 5, branch_sources([la, [I(0x900, "jmp", (None,), 0x12, target=0x12)]]))[1])
    check("(1r) 迴圈外跳進條件跳躍本身不採信",
          "從迴圈外跳進" in resolve_loop(la, 5, branch_sources([la, [I(0x900, "jmp", (None,), 0x2D, target=0x2D)]]))[1])
    check("(1s) 迴圈外跳到初值本身(會重新初始化)仍採信",
          resolve_loop(la, 5, branch_sources([la, [I(0x900, "jmp", (None,), 0x10, target=0x10)]]))[0] is not None)
    check("(1t) 迴圈外跳到迴圈之後仍採信",
          resolve_loop(la, 5, branch_sources([la, [I(0x900, "jmp", (None,), 0x2F, target=0x2F)]]))[0] is not None)
    check("(1u) 迴圈體內另有向後 jmp 不採信",
          "巢狀" in str(lo_hi(loop_a(extra=[I(0x20, "jmp", (None,), 0x14, target=0x14)]))))
    check("(1v) 迴圈體內向後跳到迴圈起點之前(離開迴圈)仍採信",
          lo_hi(loop_a(extra=[I(0x20, "jne", (None,), 0x00, target=0x00)])) == (0, 64))
    check("(1w) add ecx, 1 步長採信", lo_hi(loop_a(inc=I(0x29, "add", ("ecx", None), 1, writes=("ecx",)))) == (0, 64))
    check("(1x) 步長 0x10000 不採信",
          "步長" in str(lo_hi(loop_a(inc=I(0x29, "add", ("ecx", None), 0x10000, writes=("ecx",))))))
    check("(1y) 存取後緊接向後條件跳躍(前一條不是 cmp R)不採信",
          "迴圈條件" in str(lo_hi([I(0x00, "mov", ("ecx", None), 0, writes=("ecx",)),
                                    I(0x05, "cmp", (None, None), 0, mem=Mem("ecx", None, 1, B, 4)),
                                    I(0x0C, "jne", (None,), 0x05, target=0x05), I(0x0E, "ret")], 1)))
    # (2) 0x3eade 形:mov edi, 0; [edi+B]; add edi, 4; cmp edi, 0x40; jb(底部測試)
    lb = [I(0x00, "mov", ("edi", None), 0, writes=("edi",)),
          I(0x05, "cmp", (None, None), 2, mem=Mem("edi", None, 1, B, 4)),
          I(0x0C, "add", ("edi", None), 4, writes=("edi",)),
          I(0x0F, "cmp", ("edi", None), 0x40),
          I(0x12, "jb", (None,), 0x05, target=0x05),
          I(0x14, "ret")]
    check("(2a) 底部測試 edi 0..0x3c 步長 4 → [0, 64)", lo_hi(lb, 1) == (0, 64))
    lb2 = [*lb[:3], I(0x0F, "cmp", ("edi", None), 0x41), *lb[4:]]
    check("(2b) jb 0x41(不整除)→ 最後 0x40 → [0, 68)", lo_hi(lb2, 1) == (0, 68))
    lb3 = [*lb[:4], I(0x12, "jne", (None,), 0x05, target=0x05), lb[5]]
    check("(2c) jne 0x40 → [0, 64)", lo_hi(lb3, 1) == (0, 64))
    lb4 = [*lb[:3], I(0x0F, "cmp", ("edi", None), 0x41), I(0x12, "jne", (None,), 0x05, target=0x05), lb[5]]
    check("(2d) jne 永不相等 → 超過上限不採信", "模擬超過" in str(lo_hi(lb4, 1)))
    check("(2f) 迴圈起點是函式第一條不採信", "函式第一條" in str(lo_hi(lb[1:], 0)))
    check("(2g) 迴圈起點不在指令邊界不採信",
          "指令邊界" in str(lo_hi([*lb[:4], I(0x12, "jb", (None,), 0x03, target=0x03), lb[5]], 1)))
    check("(2e) 迴圈起點前一條是 jmp(初值流不進來)不採信",
          "立即數初值" in str(lo_hi([I(0x00, "jmp", (None,), 0x40, target=0x40), *lb[1:]], 1)))
    # (3) 0x3fdaf 形:mov esi, 15; jmp test; [esi*4+B]; call; dec esi; test esi, esi; jge
    lc = [I(0x00, "mov", ("esi", None), 0xF, writes=("esi",)),
          I(0x05, "jmp", (None,), 0x1D, target=0x1D),
          I(0x08, "mov", ("eax", None), mem=Mem(None, "esi", 4, B, 4), writes=("eax",)),
          I(0x0F, "call", (None,), 0x100, target=0x100),
          I(0x1C, "dec", ("esi",), writes=("esi",)),
          I(0x1D, "test", ("esi", "esi")),
          I(0x1F, "jge", (None,), 0x08, target=0x08),
          I(0x21, "ret")]
    check("(3a) 遞減 esi 15..0、test / jge、call 不改 esi → [0, 64)", lo_hi(lc, 2) == (0, 64))
    lc2 = [*lc[:5], I(0x1D, "test", ("esi", "esi")), I(0x1F, "jg", (None,), 0x08, target=0x08), lc[7]]
    check("(3b) jg → 15..1 → [4, 64)", lo_hi(lc2, 2) == (4, 64))
    lc3 = [I(0x00, "mov", ("ecx", None), 0xF, writes=("ecx",)), lc[1],
           I(0x08, "mov", ("eax", None), mem=Mem(None, "ecx", 4, B, 4), writes=("eax",)), lc[3],
           I(0x1C, "dec", ("ecx",), writes=("ecx",)), I(0x1D, "test", ("ecx", "ecx")), lc[6], lc[7]]
    check("(3c) 計數器 ecx 遇 call 被改寫不採信", "有 2 條" in str(lo_hi(lc3, 2)))
    check("(3l) test 兩個不同暫存器不採信",
          "迴圈條件" in str(lo_hi([*lc[:5], I(0x1D, "test", ("esi", "edi")), *lc[6:]], 2)))
    check("(3m) test 記憶體 / 立即數(沒有暫存器)不採信",
          "迴圈條件" in str(lo_hi([*lc[:5], I(0x1D, "test", (None, None), 1, mem=Mem(None, None, 1, B, 4)),
                                    *lc[6:]], 2)))
    check("(3n) 有號轉換:0xffffffff → -1、0x80000000 → -2^31、0x7fffffff 不變",
          _signed(0xFFFFFFFF) == -1 and _signed(0x80000000) == -0x80000000 and _signed(0x7FFFFFFF) == 0x7FFFFFFF)
    check("(3d) 不在迴圈內不採信", "不在迴圈內" in str(lo_hi([lc[0], lc[2], lc[7]], 1)))
    check("(3e) 基底與索引都是暫存器不採信",
          "基底與索引" in str(lo_hi([*lc[:2], I(0x08, "mov", ("eax", None), mem=Mem("ebx", "esi", 4, B, 4),
                                                 writes=("eax",)), *lc[3:]], 2)))
    check("(3f) 模擬:jl 0 起 1 步 → 0..15", simulate(0, 1, "jl", 16, True) == list(range(16)))
    check("(3g) 模擬:頂端測試條件一開始不成立 → 空", simulate(16, 1, "jl", 16, True) == [])
    check("(3h) 模擬:底部測試至少一次", simulate(16, 1, "jl", 16, False) == [16])
    check("(3i) 有號 / 無號:jl -1 < 0 成立、jb 不成立", taken("jl", -1, 0) and not taken("jb", -1, 0))
    check("(3j) js / jns 看差值符號", taken("js", 1, 2) and taken("jns", 2, 1) and not taken("js", 2, 2)
          and taken("jns", 2, 2) and not taken("jns", 1, 2))
    check("(3k) ja / jae / jbe / jle / jg / jge / je 邊界",
          taken("ja", 2, 1) and not taken("ja", 1, 1) and taken("jae", 1, 1) and not taken("jae", 0, 1)
          and taken("jbe", 1, 1) and not taken("jbe", 2, 1) and taken("jle", 1, 1) and not taken("jle", 2, 1)
          and taken("jg", 2, 1) and not taken("jg", 1, 1) and taken("jge", 1, 1) and not taken("jge", 0, 1)
          and taken("je", 1, 1) and not taken("je", 0, 1) and taken("jne", 0, 1) and not taken("jne", 1, 1))
    # (4) rep
    S = 0x541F4
    rp = [I(0x00, "mov", ("ecx", None), 0xA, writes=("ecx",)),
          I(0x05, "mov", ("edi", None), S, True, writes=("edi",)),
          I(0x0A, "mov", ("esi", None), 0x5120C, True, writes=("esi",)),
          I(0x0F, "rep movsd", (), writes=("edi", "esi", "ecx")),
          I(0x11, "movsw", (), writes=("edi", "esi")),
          I(0x13, "movsb", (), writes=("edi", "esi")),
          I(0x14, "ret")]

    def rext(lst: list[Ins], i: int = 3, std: bool = False) -> tuple | str:
        res, why = rep_extent(lst, i, branch_sources([lst]), std)
        return (res["start"], res["len"]) if res else why

    check("(4a) rep movsd ×10 + movsw + movsb = 43 byte", rext(rp) == (S, 43))
    check("(4b) 函式有 std 不採信", "std" in str(rext(rp, std=True)))
    check("(4c) edi 沒有 fixup 不採信",
          "不是 mov edi" in str(rext([rp[0], I(0x05, "mov", ("edi", None), S, False, writes=("edi",)), *rp[2:]])))
    check("(4d) ecx 不是立即數不採信",
          "不是 mov ecx" in str(rext([I(0x00, "mov", ("ecx", "edx"), writes=("ecx",)), *rp[1:]])))
    check("(4e) 中間有 call 不採信",
          "找不到" in str(rext([rp[0], rp[1], I(0x0A, "call", (None,), 0x100, target=0x100), *rp[3:]])))
    check("(4f) 有跳躍跳進設定與 rep 之間(區塊從那裡開始)不採信",
          "找不到" in rep_extent(rp, 3, branch_sources([rp, [I(0x900, "jmp", (None,), 0x0A, target=0x0A)]]), False)[1])
    check("(4g) rep stosd 不接 movs 尾巴",
          rext([rp[0], rp[1], I(0x0A, "mov", ("eax", None), 0, writes=("eax",)),
                I(0x0F, "rep stosd", (), writes=("edi", "ecx")), rp[4], rp[6]]) == (S, 40))
    far = [rp[0], rp[1], *[I(0x06 + k, "nop") for k in range(9)], *rp[3:]]
    check("(4i) 設定在函式第一條、與 rep 隔 9 條(同一基本區塊)採信", rext(far, 11) == (S, 43))
    check("(4h) 跳躍目標在設定之後(區塊從那裡開始)不採信",
          "找不到" in rep_extent(far, 11, branch_sources([far, [I(0x900, "jmp", (None,), 0x09, target=0x09)]]),
                                False)[1])
    check("(4j) 設定本身是跳躍目標(區塊第一條)仍採信",
          rep_extent(far, 11, branch_sources([far, [I(0x900, "jmp", (None,), 0x00, target=0x00)]]), False)[0]
          == {"start": S, "len": 43})
    check("(4k) rep 本身是跳躍目標不採信",
          "跳躍目標" in rep_extent(rp, 3, branch_sources([rp, [I(0x900, "jmp", (None,), 0x0F, target=0x0F)]]), False)[1])
    ch = [I(0x00, "mov", ("edi", None), S, True, writes=("edi",)),
          I(0x05, "mov", ("esi", None), 0x51624, True, writes=("esi",)),
          I(0x0A, "mov", ("eax", None), 0xFFFFFFFF, writes=("eax",)),
          *[I(0x0F + k, "movsd", (), writes=("edi", "esi")) for k in range(4)],
          I(0x13, "movsw", (), writes=("edi", "esi")),
          I(0x15, "movsb", (), writes=("edi", "esi")),
          I(0x16, "ret")]

    def cext(lst: list[Ins], i: int = 3, std: bool = False, extra: list | None = None) -> tuple | str:
        res, why = chain_extent(lst, i, branch_sources([lst, extra or []]), std)
        return (res["start"], res["len"]) if res else why

    check("(4l) 非 rep:4 × movsd + movsw + movsb = 19 byte", cext(ch) == (S, 19))
    check("(4m) 非 rep 串:函式有 std 不採信", "std" in str(cext(ch, std=True)))
    check("(4n) 非 rep 串:edi 沒有 fixup 不採信",
          "不是 mov edi" in str(cext([I(0x00, "mov", ("edi", None), S, False, writes=("edi",)), *ch[1:]])))
    check("(4o) 非 rep 串:串中有跳躍目標不採信",
          "跳躍目標" in str(cext(ch, extra=[I(0x900, "jmp", (None,), 0x13, target=0x13)])))
    check("(4p) 非 rep 串:設定前有 call(不同區塊)不採信",
          "找不到" in str(cext([ch[0], I(0x03, "call", (None,), 0x100, target=0x100), *ch[1:]], 4)))
    check("(4q) 非 rep 串:stos 不接 movs", cext([ch[0], I(0x0F, "stosd", (), writes=("edi",)), *ch[3:]], 1) == (S, 4))
    wch = collect({0x0: rp}, [(S, S + 0x100)])["wit"][S]
    check("(4r) rep 後面的 movs 尾巴不另算成串", wch["rep"] == {0x0F: (S, S + 43)} and wch["chain"] == {})
    wch = collect({0x0: ch}, [(S, S + 0x100)])["wit"][S]
    check("(4s) collect 只在串首記一筆", wch["chain"] == {0x0F: (S, S + 19)})
    check("(4t) 非 rep 串:最後一條是跳躍目標不採信",
          "跳躍目標" in str(cext(ch, extra=[I(0x900, "jmp", (None,), 0x15, target=0x15)])))
    # (5) DPMI 範圍函式辨認與宣告長度
    g = [I(0x200, "sub", ("esp", None), 0x38, writes=("esp",)),
         I(0x203, "mov", (None, None), 0x600, mem=Mem("esp", None, 1, 0, 4)),
         I(0x20A, "push", (None,), 0x31),
         I(0x20C, "call", (None,), 0x300, target=0x300),
         I(0x211, "ret")]
    f = [I(0x100, "mov", ("eax", None), mem=Mem("esp", None, 1, 4, 4), writes=("eax",)),
         I(0x104, "add", ("eax", None), mem=Mem("esp", None, 1, 8, 4), writes=("eax",)),
         I(0x108, "push", ("eax",)), I(0x109, "call", (None,), 0x200, target=0x200), I(0x10E, "ret")]
    check("(5a) 鎖定包裝辨認為 lock", range_fn_kind(f, {0x200: g}) == "lock")
    g2 = [*g[:1], I(0x203, "mov", (None, None), 0x601, mem=Mem("esp", None, 1, 0, 4)), *g[2:]]
    check("(5b) 0x601 辨認為 unlock", range_fn_kind(f, {0x200: g2}) == "unlock")
    check("(5c) 沒有 push 0x31 不算", range_fn_kind(f, {0x200: [*g[:2], I(0x20A, "push", (None,), 0x21), *g[3:]]}) is None)
    check("(5d) 開頭不是 [esp+4] + [esp+8] 不算",
          range_fn_kind([f[0], I(0x104, "add", ("eax", None), mem=Mem("esp", None, 1, 0xC, 4)), *f[2:]],
                        {0x200: g}) is None)
    check("(5e) 開頭第一條不是 mov eax, [esp+4] 不算",
          range_fn_kind([I(0x100, "mov", ("eax", None), mem=Mem("esp", None, 1, 8, 4)), *f[1:]], {0x200: g}) is None)
    check("(5f) 指令太少不算", range_fn_kind(f[:2], {0x200: g}) is None)
    check("(5i) 恰好三條(call 緊接開頭兩條)辨認為 lock", range_fn_kind([f[0], f[1], f[3]], {0x200: g}) == "lock")
    check("(5j) push 0x31 / call 是 G 的最後兩條仍辨認", range_fn_kind(f, {0x200: g[:4]}) == "lock")
    check("(5k) push 0x31 與 call 之間隔一條不算",
          range_fn_kind(f, {0x200: [*g[:3], I(0x20B, "nop"), *g[3:]]}) is None)
    caller = [I(0x400, "push", (None,), 0x40), I(0x402, "push", (None,), B, True),
              I(0x407, "call", (None,), 0x100, target=0x100), I(0x40C, "ret")]
    wit = collect({0x100: f, 0x200: g, 0x400: caller}, [(B, B + 0x40)])["wit"][B]
    check("(5g) push 0x40 / push B / call lock → 宣告 [B, B+0x40)", wit["range"] == {0x407: (B, B + 0x40, "lock")})
    caller2 = [I(0x400, "push", (None,), 0x40), I(0x402, "push", (None,), B, False), *caller[2:]]
    check("(5h) 位址沒有 fixup 不算宣告",
          collect({0x100: f, 0x200: g, 0x400: caller2}, [(B, B + 0x40)])["wit"][B]["range"] == {})
    # (6) judge
    def wset(**kw: dict) -> dict:
        d = {"direct": {}, "loop": {}, "rep": {}, "chain": {}, "ptr": {}, "range": {}, "value": {}, "unresolved": {},
             "mem_sites": set()}
        d.update(kw)
        return d

    j = judge(B, 64, wset(loop={1: (B, B + 64, {})}), set())
    check("(6a) 迴圈達 size → access、不失敗", j["grade"] == "access" and not j["fail"] and j["lb_access"] == 64)
    j = judge(B, 60, wset(loop={1: (B, B + 64, {})}), set())
    check("(6b) 迴圈超過 size(登短)→ 失敗", bool(j["fail"]) and j["lb_access"] == 60)
    j = judge(B, 64, wset(direct={1: (B - 4, B, )}), set())
    check("(6c) 低於起點 → 失敗", bool(j["fail"]))
    j = judge(B, 64, wset(direct={1: (B, B + 4)}, range={2: (B, B + 64, "lock")}), set())
    check("(6d) 只有宣告達 size → declared", j["grade"] == "declared" and j["lb_access"] == 4 and not j["fail"])
    j = judge(B, 64, wset(direct={1: (B, B + 4)}), set())
    check("(6e) 都不達 → partial", j["grade"] == "partial" and not j["fail"])
    j = judge(B, 32, wset(range={2: (B, B + 64, "lock")}), set())
    check("(6f) 宣告大於 size → 失敗", bool(j["fail"]))
    j = judge(B, 64, wset(range={2: (B + 4, B + 64, "lock")}), set())
    check("(6g) 宣告起點不是區段起點 → 失敗", bool(j["fail"]))
    j = judge(B, 64, wset(mem_sites={1, 2}), {1})
    check("(6h) 與 re_coverage 存取不一致 → 失敗", bool(j["fail"]))
    j = judge(B, 64, wset(mem_sites={1}), {1, 2})
    check("(6i) re_coverage 多一筆 → 失敗", bool(j["fail"]))
    j = judge(B, 64, wset(), set())
    check("(6o) 沒有任何證據 → 三種下限都是 0、partial",
          (j["lb_access"], j["lb_value"], j["lb_declared"], j["grade"]) == (0, 0, 0, "partial"))
    j = judge(B, 64, wset(rep={1: (B, B + 64)}, direct={2: (B, B + 4)}), set())
    check("(6j) rep 達 size → access", j["grade"] == "access" and j["lb_access"] == 64)
    # 宣告的原程式越界:只放行逐字相符的那一條
    ov = wset(loop={1: (B, B + 64, {})})
    check("(6p) 文法:迴圈多寫", declared_overruns("dword[15](x;原程式 0x2ba21 迴圈多寫 4 byte)") == {0x2ba21: 4})
    j = judge(B, 60, ov, set(), overruns={1: 4})
    check("(6q) 宣告多寫 4 byte 且相符 → 不失敗、下限只算到 size", not j["fail"] and j["lb_access"] == 60)
    check("(6r) 宣告多寫 8 byte(不符)→ 失敗", bool(judge(B, 60, ov, set(), overruns={1: 8})["fail"]))
    check("(6s) 宣告的是別條指令 → 失敗(兩筆:越界本身與宣告落空)",
          len(judge(B, 60, ov, set(), overruns={2: 4})["fail"]) == 2)
    check("(6t) 宣告了但範圍沒越界 → 失敗", bool(judge(B, 64, ov, set(), overruns={1: 4})["fail"]))
    check("(6u) 越界且低於起點 → 失敗",
          bool(judge(B, 60, wset(loop={1: (B - 4, B + 64, {})}), set(), overruns={1: 4})["fail"]))
    # (7) collect:直接 / 索引分流、esp 基底不算
    fl = [I(0x10, "mov", (None, None), 1, mem=Mem(None, None, 1, B + 8, 4)),
          I(0x16, "mov", ("eax", None), mem=Mem("esp", None, 1, B, 4), writes=("eax",)),
          I(0x1A, "mov", ("eax", None), mem=Mem("eax", None, 1, B, 4), writes=("eax",)),
          I(0x1E, "ret")]
    wc = collect({0x10: fl}, [(B, B + 64)])["wit"][B]
    check("(7a) 直接存取 → direct [B+8, B+12)", wc["direct"] == {0x10: (B + 8, B + 12)})
    check("(7b) esp 基底不算區段存取", 0x16 not in wc["mem_sites"])
    check("(7c) 解不出的索引存取列為未解出", set(wc["unresolved"]) == {0x1A} and wc["mem_sites"] == {0x10, 0x1A})
    j = judge(B, 64, wset(direct={1: (B, B + 4)}, value={2: (B, B + 64, 0x9000, 15)}), set())
    check("(6k) 加上變數值才達 size → value", j["grade"] == "value" and j["lb_value"] == 64 and j["lb_access"] == 4)
    j = judge(B, 64, wset(value={2: (B, B + 64, 0x9000, 15)}, range={3: (B, B + 64, "lock")}), set(), True)
    check("(6l) content 優先於 value / declared", j["grade"] == "content")
    j = judge(B, 64, wset(direct={1: (B, B + 64)}), set(), True)
    check("(6m) 存取已達 size 時仍是 access", j["grade"] == "access")
    j = judge(B, 64, wset(value={2: (B, B + 32, 0x9000, 7)}, range={3: (B, B + 64, "lock")}), set())
    check("(6n) value 未達、宣告達 → declared", j["grade"] == "declared" and j["lb_value"] == 32)
    # (9) 變數值證據:索引由變數載入、取變數的最大立即數寫入
    V, T = 0x53F4A, 0x52387

    def vfuncs(vals: list[tuple[int, int]], mid: list[Ins] | None = None, load: Ins | None = None) -> dict:
        writer = [I(0x100 + 0x10 * k, "mov", (None, None), v, mem=Mem(None, None, 1, V, wd)) for k, (v, wd) in
                  enumerate(vals)] + [I(0x1F0, "ret")]
        reader = [load or I(0x300, "mov", ("eax", None), mem=Mem(None, None, 1, V, 4), writes=("eax",)),
                  *(mid or []),
                  I(0x30A, "movzx", ("eax", None), mem=Mem("eax", None, 1, T, 1), writes=("eax",)),
                  I(0x312, "ret")]
        return {0x100: writer, 0x300: reader}

    def vw(fs: dict) -> dict:
        return collect(fs, [(T, T + 6)])["wit"][T]

    wv = vw(vfuncs([(0, 4), (4, 4), (5, 4)]))
    check("(9a) 立即數 0 / 4 / 5 → value [T, T+6)", wv["value"] == {0x30A: (T, T + 6, V, 5)})
    check("(9b) 變數值證據的存取仍列在未解出(迴圈)", 0x30A in wv["unresolved"])
    wv = vw(vfuncs([(0, 4), (255, 4)]))
    check("(9c) 有立即數會定址出界 → 整筆不採信、附原因", wv["value"] == {} and "255" in wv["unresolved"][0x30A])
    wv = vw(vfuncs([(0, 4), (9, 1)]))
    check("(9d) 寫入寬度與載入寬度不同的立即數不算", wv["value"] == {0x30A: (T, T + 1, V, 0)})
    wv = vw(vfuncs([(5, 4)], mid=[I(0x305, "jne", (None,), 0x30A, target=0x30A)]))
    check("(9e) 載入與存取之間有分支 → 不採信", wv["value"] == {})
    wv = vw(vfuncs([(5, 4)], mid=[I(0x305, "add", ("eax", None), 1, writes=("eax",))]))
    check("(9f) 載入後另被改寫 → 不採信", wv["value"] == {})
    wv = vw(vfuncs([(5, 4)], mid=[I(0x305 + k, "nop") for k in range(VALUE_WINDOW)]))
    check("(9g) 載入超出 VALUE_WINDOW → 不採信", wv["value"] == {})
    wv = vw(vfuncs([(5, 4)], load=I(0x300, "mov", ("eax", None), mem=Mem("ebx", None, 1, V, 4), writes=("eax",))))
    check("(9h) 由索引定址載入的不算變數 → 不採信", wv["value"] == {})
    fs = vfuncs([(5, 4)])
    fs[0x900] = [I(0x900, "jmp", (None,), 0x30A, target=0x30A)]
    check("(9i) 存取是跳躍目標 → 不採信", vw(fs)["value"] == {})
    wv = vw(vfuncs([(5, 4)], load=I(0x300, "mov", ("eax", None), 5, writes=("eax",))))
    check("(9j) 立即數載入(不是變數)→ 不採信", wv["value"] == {})
    wv = vw(vfuncs([(5, 4)], load=I(0x300, "mov", ("ebx", None), mem=Mem(None, None, 1, V, 4), writes=("ebx",))))
    check("(9k) 載入別的暫存器 → 不採信", wv["value"] == {})
    rs, _why = index_load([I(0x300, "mov", ("ecx", None), mem=Mem(None, None, 1, V, 4), writes=("ecx",)),
                           I(0x306, "mov", ("eax", None), mem=Mem(None, "ecx", 4, T, 4), writes=("eax",))], 1, {})
    check("(9l) 索引倍率帶出來", rs == (V, 4, 4))
    wv = vw(vfuncs([(1, 4)]))
    check("(9m) 立即數 1 → value [T, T+2)(取最大值,不是個數)", wv["value"] == {0x30A: (T, T + 2, V, 1)})
    wv = vw(vfuncs([(-3, 1)], load=I(0x300, "movzx", ("eax", None), mem=Mem(None, None, 1, V, 1), writes=("eax",))))
    check("(9n) byte 寫入的負立即數取 8 位元(-3 → 253);原因帶變數位址",
          wv["value"] == {} and "[253]" in wv["unresolved"][0x30A] and "[0x53f4a]" in wv["unresolved"][0x30A])

    # (10) 指標追蹤:手組機器碼,經真的 capstone 解碼(呼叫端 0x1000 push P / push P / push 0x10 / call F)
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    P, GX = 0x53A8D, 0x60000
    # F(不用 ebp 當框架指標,int 時沒有暫存器持有堆疊位址):
    # mov edi, [esp+8] / mov edx, [esp+0xc] / mov eax, [edi] / push edx
    FB = bytes.fromhex("8b7c24088b54240c8b0752")
    # F 尾:pop edi / mov [edi+0x18], eax / ret
    FE = bytes.fromhex("5f894718c3")

    def build(mid: bytes = bytes.fromhex("cd10"), fx_p: bool = True, after: bytes = b"", f: bytes | None = None,
              more: dict | None = None, xfx: dict | None = None) -> tuple[Decoder, int, dict]:
        cal, fx = bytearray(), dict(xfx or {})
        for _k in range(2):
            if fx_p:
                fx[0x1000 + len(cal) + 1] = P
            cal += b"\x68" + P.to_bytes(4, "little")
        cal += bytes.fromhex("6a10")
        at = 0x1000 + len(cal)
        cal += b"\xe8" + ((0x1100 - (at + 5)) & M32).to_bytes(4, "little") + after + bytes.fromhex("83c40cc3")
        code = bytearray(0x300)
        code[0:len(cal)] = cal
        body = f if f is not None else FB + mid + FE
        code[0x100:0x100 + len(body)] = body
        for a, bs in (more or {}).items():
            code[a - 0x1000:a - 0x1000 + len(bs)] = bs
        return Decoder(md, bytes(code), 0x1000, fx), at, fx

    def tr(size: int = 0x1C, **kw: object) -> tuple[set, str]:
        dec, at, _fx = build(**kw)
        acc, why = trace(dec, 0x1000, at, [(P, P + size)])
        return {(a - P, w) for _s, a, w, _b in acc}, why

    check("(10a) 讀 [P] 4 byte、int 後由堆疊取回 P 寫 [P+0x18] → 正常返回", tr() == ({(0, 4), (0x18, 4)}, ""))
    check("(10b) push 沒有 fixup(數值剛好等於位址)不算指標", tr(fx_p=False)[0] == set())
    r = tr(mid=bytes.fromhex("7500"))
    check("(10c) 條件跳躍就停,停之前的存取仍採信", r[0] == {(0, 4)} and "jne" in r[1])
    check("(10d) int 前有暫存器持有堆疊位址 → 堆疊模型丟棄", tr(mid=bytes.fromhex("8d0c24cd10"))[0] == {(0, 4)})
    check("(10e) 經未知指標寫記憶體 → 堆疊模型丟棄", tr(mid=bytes.fromhex("8901"))[0] == {(0, 4)})
    check("(10f) ds 改成未知值後的存取不算", tr(mid=bytes.fromhex("8ed8"))[0] == {(0, 4)})
    site = 0x1100 + len(FB) + 1
    check("(10g) 寫到區段外的已知位址 → 堆疊模型丟棄",
          tr(mid=b"\xa3" + bytes(4), xfx={site: GX})[0] == {(0, 4)})
    check("(10h) 寫到區段內的已知位址 → 堆疊模型保留",
          tr(mid=b"\xa3" + bytes(4), xfx={site: P + 8})[0] == {(0, 4), (0x18, 4)})
    check("(10i) 返回呼叫點就停(之後的存取不算)",
          tr(size=0x40, after=bytes.fromhex("894730")) == ({(0, 4), (0x18, 4)}, ""))
    r = tr(mid=bytes.fromhex("ebfe"))
    check("(10j) 無窮迴圈 → 超過上限停", r[0] == {(0, 4)} and "超過" in r[1])
    check("(10k) ds 存到堆疊再以 16 位元讀回 → 恢復平面 ds,存取採信",
          tr(mid=bytes.fromhex("8cd8508b078ed88e1c2458"))[0] == {(0, 4), (0x18, 4)})
    check("(10l) 同上但沒有讀回 ds → 不算", tr(mid=bytes.fromhex("8cd8508b078ed858"))[0] == {(0, 4)})
    # int386x 形:call 跳板 / push 位址(有 fixup)/ ret 進 int n; ret / 回來後由堆疊重載 edi
    thunk = bytes.fromhex("8b7c2408" "e877000000" "8b7c2408" "894718" "c3")
    jt = {0x1180: b"\x68" + bytes(4) + b"\xc3", 0x1200: bytes.fromhex("cd10c3")}
    check("(10m) push 位址 / ret 跳進 int 跳板再返回 → [P+0x18] 採信",
          tr(f=thunk, more=jt, xfx={0x1181: 0x1200}) == ({(0x18, 4)}, ""))
    r = tr(f=thunk, more=jt)
    check("(10n) 跳板位址沒有 fixup → 停在 ret", r[0] == set() and "跳躍目標" in r[1])
    check("(10o) sub esp / leave / ret 正常返回",
          tr(f=bytes.fromhex("5589e583ec108b7d0c894718c9c3")) == ({(0x18, 4)}, ""))
    r = tr(f=bytes.fromhex("5589e58b6d00c9c3"))
    check("(10p) ebp 變未知後 leave → 停", r[0] == set() and "esp" in r[1])
    check("(10q) _add:位址 + 位址 = 未知、堆疊 + 數值、數值 + 位址、32 位元回繞",
          _add(("a", 1, 1), ("a", 2, 2)) is None and _add(("s", -8), ("c", 4)) == ("s", -4)
          and _add(("c", -1), ("a", 0x10, 0x10)) == ("a", 0xF, 0x10)
          and _add(("c", 0x7FFFFFFF), ("c", 1)) == ("c", -0x80000000)
          and _add(("g", "ds"), ("c", 1)) is None and _neg(("a", 4, 4)) is None and _neg(("c", 4)) == ("c", -4))
    dec, at, fx = build()
    fl = {0x1000: [conv(md, fx, x) for x in md.disasm(dec.code[0:0x20], 0x1000)],
          0x1100: [conv(md, fx, x) for x in md.disasm(dec.code[0x100:0x100 + len(FB) + 2 + len(FE)], 0x1100)]}
    wp = collect(fl, [(P, P + 0x10)], dec)["wit"][P]
    check("(10r) collect:以 call 位址為鍵記 ptr [P, P+0x1c)", set(wp["ptr"]) == {at}
          and wp["ptr"][at][:2] == (P, P + 0x1C) and wp["ptr"][at][2]["start"] == 0x1000)
    j = judge(P, 0x10, wp, set())
    check("(10s) ptr 超過 size → 失敗", any("ptr" in e for e in j["fail"]))
    wv2 = collect(fl, [(P, P + 0x10), (P + 0x10, P + 0x40)], dec)["wit"]
    check("(10v) 指標寫進鄰段仍歸它來源的區段(不算鄰段的證據)", wv2[P + 0x10]["ptr"] == {}
          and wv2[P]["ptr"][at][:2] == (P, P + 0x1C))
    check("(10t) 不傳解碼器就不追蹤", collect(fl, [(P, P + 0x10)])["wit"][P]["ptr"] == {})
    fl2 = {0x1000: [conv(md, {}, x) for x in md.disasm(dec.code[0:0x20], 0x1000)], 0x1100: fl[0x1100]}
    check("(10u) 區塊內沒有指到區段的 fixup 立即數 → 不追蹤",
          collect(fl2, [(P, P + 0x10)], dec)["wit"][P]["ptr"] == {})

    # (10w)–(10al) 續二百六十三窮舉突變的逃逸:追蹤器每個特例分支各一題,分支算出的值都要流進一筆被記下的存取
    # (F 的 mid 第一條在 M0;FB 之後 edi = edx = P,堆疊頂是 FB push 的 edx = P,FE 由那裡取回 edi)
    # (題內有經未知指標寫的反例時,依 (10e) 堆疊模型丟棄,FE 的 [P+0x18] 就不在預期內)
    M0 = 0x1100 + len(FB)
    hit0 = {(0, 4), (0x18, 4)}

    def tw(**kw: object) -> tuple[set, str]:
        """區段 [P, P + 0x2000):題內的寫入都在區段內,堆疊模型保留,FE 取回的 edi 仍是 P。"""
        return tr(size=0x2000, **kw)
    check("(10w) _add:位址 + 數值保留指標來源(來源 ≠ 位址)",
          _add(("a", 0x14, 0x10), ("c", 4)) == ("a", 0x18, 0x10)
          and _add(("c", 4), ("a", 0x14, 0x10)) == ("a", 0x18, 0x10))
    # push 0x1335 / movzx ecx, byte [esp] / mov [edi+ecx], eax / pop ecx
    check("(10x) 堆疊上 4 byte 數值以 1 byte 讀出(movzx)→ 遮罩成 0x35 當索引",
          tw(mid=bytes.fromhex("6835130000" "0fb60c24" "89040f" "59")) == (hit0 | {(0x35, 4)}, ""))
    # mov ecx, 0x1335 / movzx edx, cl / mov [edi+edx], eax / movzx edx, ch / mov [edi+edx], eax
    check("(10y) 部分暫存器讀:cl = 0x35、ch = 0x13(movzx 寫入目的暫存器)",
          tw(mid=bytes.fromhex("b935130000" "0fb6d1" "890417" "0fb6d5" "890417"))
          == (hit0 | {(0x35, 4), (0x13, 4)}, ""))
    # mov ecx, 0x8555 / movsx edx, cl / mov ebx, [edi+edx] / movsx edx, ch / mov ebx, [edi+edx]
    # / movzx edx, ch / mov ebx, [edi+edx+0x200](只讀:區段外的讀不丟堆疊模型)
    check("(10am) movsx 依來源最高位元延伸:cl 0x55 → +0x55、ch 0x85 → −0x7b;movzx ch 0x85 → +0x85",
          tw(mid=bytes.fromhex("b955850000" "0fbed1" "8b1c17" "0fbed5" "8b1c17" "0fb6d5" "8b9c1700020000"))
          == (hit0 | {(0x55, 4), (-0x7B, 4), (0x285, 4)}, ""))
    # mov ecx, 0x1300 / mov cl, 0x35 / mov [edi+ecx], eax / mov ch, 7 / mov [edi+ecx+0x40], eax
    check("(10z) 部分暫存器寫:cl 併進原數值;寫 ch 之後變未知",
          tw(mid=bytes.fromhex("b900130000" "b135" "89040f" "b507" "89440f40")) == ({(0, 4), (0x1335, 4)}, ""))
    # mov ax, ds / mov es, ax / mov es:[edi+0x10], ecx
    check("(10aa) ds 經 16 位元暫存器搬到 es 仍是平面區段,es: 存取採信",
          tw(mid=bytes.fromhex("668cd8" "668ec0" "26894f10")) == (hit0 | {(0x10, 4)}, ""))
    # mov ecx, 4 / mov [edi+ecx*4+0x20], eax / mov ecx, P(fixup) / mov [ecx*1+0x40], eax(只有索引、倍率 1)
    check("(10ab) 索引倍率:ecx × 4;倍率 1 的索引可以是指標",
          tw(mid=bytes.fromhex("b904000000" "89448f20" "b9") + P.to_bytes(4, "little") + bytes.fromhex("89040d40000000"),
             xfx={M0 + 10: P}) == (hit0 | {(0x30, 4), (0x40, 4)}, ""))
    # mov [edi+0x100], eax:位址在區段外、指標來源 P 在區段內 —— 依位址判斷,堆疊模型丟棄,FE 取回的 edi 變未知
    check("(10ac) 寫到區段外(指標來源在區段內)→ 堆疊模型丟棄",
          tr(mid=bytes.fromhex("898700010000")) == ({(0, 4), (0x100, 4)}, ""))
    # mov eax, 0x1180(fixup)/ add eax, 0x10 / call eax → 0x1190:mov [edi+0x20], ecx / ret;0x1180 是 jne
    check("(10ad) call 暫存器:目標是位址本身(0x1190),不是指標來源(0x1180)",
          tw(mid=bytes.fromhex("b880110000" "83c010" "ffd0"), xfx={M0 + 1: 0x1180},
             more={0x1180: bytes.fromhex("7500"), 0x1190: bytes.fromhex("894f20c3")}) == (hit0 | {(0x20, 4)}, ""))
    r = tr(mid=bytes.fromhex("6650"))
    check("(10ae) 16 位元 push → 停", r[0] == {(0, 4)} and "16 位元" in r[1])
    r = tr(mid=bytes.fromhex("8f0424"))
    check("(10af) pop 到 esp 定址的記憶體 → 停", r[0] == {(0, 4)} and "pop 到 esp" in r[1])
    # lea ecx, [edi+0x30] / mov [ecx], eax / lea cx, [edi+0x40] / mov [ecx+8], eax
    check("(10ag) lea 32 位元算出位址;16 位元 lea 之後 ecx 未知",
          tw(mid=bytes.fromhex("8d4f30" "8901" "668d4f40" "894108")) == ({(0, 4), (0x30, 4)}, ""))
    # mov ecx, 5 / xor ecx, ecx / mov [edi+ecx+0x28], eax / xor ecx, edx / mov [edi+ecx+0x38], eax
    check("(10ah) xor 同一暫存器 = 0;不同暫存器 → 未知",
          tw(mid=bytes.fromhex("b905000000" "31c9" "89440f28" "31d1" "89440f38")) == ({(0, 4), (0x28, 4)}, ""))
    # inc edi / mov [edi+0x40], eax / dec edi / dec edi / mov [edi+0x50], eax
    check("(10ai) inc / dec 32 位元暫存器",
          tw(mid=bytes.fromhex("47" "894740" "4f4f" "894750")) == (hit0 | {(0x41, 4), (0x4F, 4)}, ""))
    # mov eax, 0x1180(fixup)/ jmp eax → 0x1180:mov [edi+0x20], ecx + FE
    check("(10aj) jmp 暫存器(已知位址)",
          tw(mid=bytes.fromhex("b880110000" "ffe0"), xfx={M0 + 1: 0x1180},
             more={0x1180: bytes.fromhex("894f20") + FE}) == (hit0 | {(0x20, 4)}, ""))
    # add [edi+0x30], eax(其他指令的記憶體運算元照記)/ nop dword [edi+0x40](nop 不算存取)
    check("(10ak) 其他指令的記憶體運算元記為存取,nop 的不算",
          tw(mid=bytes.fromhex("014730" "0f1f4740")) == (hit0 | {(0x30, 4)}, ""))
    check("(10al) block_start:區塊從前一條 ret 之後開始",
          block_start([I(0x0, "ret"), I(0x1, "nop"), I(0x2, "call", (None,), 0x100, target=0x100)], 2, {}) == 1)

    # (8) 真實檔已知答案
    try:
        funcs, regions, cov, content, dec = load()
    except SystemExit as e:
        print(f"  (8) 真實檔無法載入:{e}")
        fails.append("(8) 載入")
    else:
        out, col = run(funcs, regions, cov, content, dec)
        by = {int(r["start"], 16): (w, jj) for r, w, jj in out}
        w, jj = by[0x541B4]
        check("(8a) 0x541b4 由迴圈證到 64(access)", jj["grade"] == "access" and len(w["loop"]) == 6
              and not w["unresolved"])
        check("(8b) 0x3fdb7 遞減迴圈 esi 15..0", w["loop"][0x3FDB7][2]["values"] == (0, 15))
        w, jj = by[0x52A94]
        check("(8c) 0x52a94 access 64,rep 0x3eccf 長度 64", jj["grade"] == "access"
              and w["rep"].get(0x3ECCF) == (0x52A94, 0x52AD4))
        w, jj = by[0x541F4]
        check("(8d) 0x541f4 rep 0x3f972 = 43 byte;rep 34 筆(ecx 在前 5 條的 0x43e30 = 41)、非 rep 串 0x4469b = 19",
              w["rep"].get(0x3F972) == (0x541F4, 0x541F4 + 43) and len(w["rep"]) == 34
              and w["rep"].get(0x43E30) == (0x541F4, 0x541F4 + 41)
              and w["chain"] == {0x4469B: (0x541F4, 0x541F4 + 19)})
        check("(8e) 0x541f4 鎖定宣告 0x100(declared)", jj["grade"] == "declared" and jj["lb_declared"] == 256
              and w["range"].get(0x3F524) == (0x541F4, 0x542F4, "lock"))
        check("(8f) 範圍函式恰好 0x3666c lock / 0x36683 unlock", col["ranged"] == {0x3666C: "lock", 0x36683: "unlock"})
        w, jj = by[0x5417C]
        check("(8g) 0x5417c 只證到 25 / 26(partial);strcpy 0x400cc 追到第一個 je 就停",
              jj["grade"] == "partial" and jj["lb_access"] == 25
              and w["ptr"].get(0x37DEC, (0, 0, {}))[2].get("stop") == "0x400dd je")
        w, jj = by[0x52387]
        check("(8h) 0x52387 由 [0x53f4a] 的立即數 5 證到 6(value)", jj["grade"] == "value" and jj["lb_access"] == 5
              and w["value"].get(0x27A53) == (0x52387, 0x5238D, 0x53F4A, 5))
        w, jj = by[0x51B91]
        check("(8i) 0x51b91 content;[0x51a8f] 的 255 哨兵讓 value 不採信",
              jj["grade"] == "content" and not w["value"] and "255" in w["unresolved"].get(0x1199C, ""))
        w, jj = by[0x53A8D]
        check("(8j) int386_regs 由指標追蹤證到 28(access):19 個 int386 呼叫點,0x46897 寫 out+0x18",
              jj["grade"] == "access" and jj["lb_access"] == 28 and len(w["ptr"]) == 19
              and w["ptr"][0x10049][:2] == (0x53A8D, 0x53AA9)
              and (0x46897, 0x53AA5, 4) in w["ptr"][0x10049][2]["hits"] and w["ptr"][0x10049][2]["stop"] == "")
        check("(8k) 記憶體運算元與 re_coverage 逐筆相同(非空)", sum(len(w["mem_sites"]) for _r, w, _j in out) > 4000)
        w, jj = by[0x52834]
        check("(8m) 0x52834 遠指標:0x4cf66 lfs 讀 6 byte(offset + selector)→ access 6",
              jj["grade"] == "access" and jj["lb_access"] == 6 and w["direct"].get(0x4CF66, (0, 0))[:2] == (0x52834, 0x5283A))
        check("(8l) 真實檔零失敗", len(out) == len(regions) and not [x for *_y, x in out if x["fail"]])
    print(f"selftest: {'PASS' if not fails else 'FAIL'}({len(fails)} 項失敗)")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="有失敗就 exit 1")
    g.add_argument("--verbose", action="store_true", help="每段都列")
    g.add_argument("--show", metavar="ADDR", help="列出某段的全部證據")
    g.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    funcs, regions, cov, content, dec = load()
    out, col = run(funcs, regions, cov, content, dec)
    if a.show:
        return show(out, int(a.show, 16))
    return report(out, col, a.verbose)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
