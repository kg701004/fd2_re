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
* rep     `rep stos*` / `rep movs*` 前 REP_WINDOW 條內 `mov edi, 位址(有 fixup)` 與 `mov ecx, 立即數`,中間沒有
          分支、也沒有任何跳躍跳進來;長度 = ecx × 寬度,緊接的非 rep `movs*` / `stos*` 依序加上(內嵌 strcpy 的尾巴)。
          函式內有 `std` 就不採信(Watcom / C 呼叫約定在函式邊界 DF = 0)。

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
# rep 前幾條內要找到 edi / ecx 的立即數(FD2 實際最多 3 條)
REP_WINDOW = 4
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


def rep_extent(lst: list[Ins], i: int, srcs: dict[int, set[int]], has_std: bool) -> tuple[dict | None, str]:
    """lst[i] 是 rep stos / movs:回傳 ({"start", "len"}, "") 或 (None, 原因)。"""
    w = REP[lst[i].mn]
    if has_std:
        return None, "函式內有 std"
    got: dict[str, Ins] = {}
    for x in reversed(lst[max(0, i - REP_WINDOW):i]):
        if x.mn in ("jmp", "call", "ret", "int") or x.mn in COND:
            break
        for r in ("edi", "ecx"):
            if r not in got and _writes(x, r):
                got[r] = x
    edi, ecx = got.get("edi"), got.get("ecx")
    if edi is None or ecx is None:
        return None, f"前 {REP_WINDOW} 條內找不到 edi / ecx 的設定"
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


def collect(funcs: dict[int, list[Ins]], regions: list[tuple[int, int]]) -> dict:
    """掃全部函式,蒐集每段的證據、未解出的索引存取、記憶體運算元位置。"""
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
    wit: dict[int, dict] = {s: {"direct": {}, "loop": {}, "rep": {}, "range": {}, "value": {}, "unresolved": {},
                                "mem_sites": set()}
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
            if x.mn == "call" and x.target in ranged and i >= 2:
                pa, pn = lst[i - 1], lst[i - 2]
                if pa.mn == "push" and pa.imm_fx and pn.mn == "push" and pn.imm is not None and not pn.imm_fx \
                        and not srcs.get(pa.addr) and not srcs.get(x.addr) and (reg := region_of(pa.imm)):
                    wit[reg[0]]["range"][x.addr] = (pa.imm, pa.imm + pn.imm, ranged[x.target])
    return {"wit": wit, "ranged": ranged}


def judge(start: int, size: int, w: dict, cov_sites: set[int], content: bool = False) -> dict:
    """一段的結論:access / declared 下限、等級、失敗。

    content 為 True 代表 verify_data_types 已以內容證明整段(C 字串逐 byte + NUL、函式指標表每格 fixup)。
    """
    end = start + size
    fail: list[str] = []
    lb_access = 0
    for kind in ("direct", "loop", "rep"):
        for ins, (lo, hi, *_r) in w[kind].items():
            if lo < start or hi > end:
                fail.append(f"{hex(start)}: {kind} {hex(ins)} 定址 [{hex(lo)}, {hex(hi)}) 跑出區段 "
                            f"[{hex(start)}, {hex(end)})")
            lb_access = max(lb_access, min(hi, end) - start)
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

def load() -> tuple[dict[int, list[Ins]], list[dict], dict[int, set[int]], set[int]]:
    """回傳 (函式入口 → 指令摘要清單, data_map regions, 區段起點 → re_coverage mem 存取的指令位址,
    verify_data_types 以內容證明整段的區段起點)。"""
    import disasm_le
    import le_xref
    import re_coverage as R
    import verify_data_types as V
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

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

    def conv(x: object) -> Ins:
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
                          op.mem.scale, disp, op.size)
        imm_fx = imm_site in fx1
        if (x.mnemonic == "jmp" or x.mnemonic in COND or x.mnemonic == "call") and imm is not None and not imm_fx:
            target = imm
        _rd, wr = x.regs_access()
        writes = frozenset(FULL[n] for n in (md.reg_name(r) for r in wr) if n in FULL)
        return Ins(x.address, x.mnemonic, tuple(regs), imm, imm_fx, mem if x.mnemonic != "lea" else None,
                   writes, target)

    funcs: dict[int, list[Ins]] = {}
    for e in inv:
        a = int(e["addr"], 16)
        funcs[a] = [conv(x) for x in disasm_le.sweep_range(md, code, cbase, a, a + e["span_upper"])
                    if not isinstance(x, tuple)]
    cov: dict[int, set[int]] = {}
    spans = [(int(r["start"], 16), int(r["start"], 16) + r["size"]) for r in regions]
    for ins, t, _width, _rw, kind, _indexed in facts.accesses:
        if kind != "mem":
            continue
        for s, e in spans:
            if s <= t < e:
                cov.setdefault(s, set()).add(ins)
    return funcs, regions, cov, content


def run(funcs: dict[int, list[Ins]], regions: list[dict], cov: dict[int, set[int]],
        content: set[int]) -> tuple[list, dict]:
    spans = [(int(r["start"], 16), int(r["start"], 16) + r["size"]) for r in regions]
    col = collect(funcs, spans)
    out = []
    for r in regions:
        s = int(r["start"], 16)
        out.append((r, col["wit"][s], judge(s, r["size"], col["wit"][s], cov.get(s, set()), s in content)))
    return out, col


def _describe(r: dict, w: dict, j: dict) -> list[str]:
    s = int(r["start"], 16)
    lines = [f"{r['start']:>8} {r['size']:4d} {r.get('name', ''):28} {j['grade']:8} 存取下限 {j['lb_access']:4d} "
             f"變數值 {j['lb_value']:4d} 宣告 {j['lb_declared']:4d}  direct {len(w['direct'])} loop {len(w['loop'])} "
             f"rep {len(w['rep'])} value {len(w['value'])} range {len(w['range'])} 未解出 {len(w['unresolved'])}"]
    best = [(hi, kind, ins) for kind in ("direct", "loop", "rep") for ins, (lo, hi, *_x) in w[kind].items()]
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
          f"{sum(len(w['value']) for _r, w, _j in out)} 筆);rep {sum(len(w['rep']) for _r, w, _j in out)} 筆;"
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
    for kind in ("direct", "loop", "rep", "value", "range"):
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
    check("(4f) 有跳躍跳進設定與 rep 之間不採信",
          "跳躍目標" in rep_extent(rp, 3, branch_sources([rp, [I(0x900, "jmp", (None,), 0x0A, target=0x0A)]]), False)[1])
    check("(4g) rep stosd 不接 movs 尾巴",
          rext([rp[0], rp[1], I(0x0A, "mov", ("eax", None), 0, writes=("eax",)),
                I(0x0F, "rep stosd", (), writes=("edi", "ecx")), rp[4], rp[6]]) == (S, 40))
    check("(4i) 設定在函式第一條、rep 前恰好 REP_WINDOW 條內採信",
          rext([rp[0], rp[1], *[I(0x06 + k, "nop") for k in range(REP_WINDOW - 2)], *rp[3:]], REP_WINDOW)
          == (S, 43))
    check("(4h) 設定超出 REP_WINDOW 不採信",
          "找不到" in str(rext([rp[0], rp[1], *[I(0x06 + k, "nop") for k in range(REP_WINDOW)], *rp[3:]],
                              2 + REP_WINDOW)))
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
        d = {"direct": {}, "loop": {}, "rep": {}, "range": {}, "value": {}, "unresolved": {}, "mem_sites": set()}
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

    # (8) 真實檔已知答案
    try:
        funcs, regions, cov, content = load()
    except SystemExit as e:
        print(f"  (8) 真實檔無法載入:{e}")
        fails.append("(8) 載入")
    else:
        out, col = run(funcs, regions, cov, content)
        by = {int(r["start"], 16): (w, jj) for r, w, jj in out}
        w, jj = by[0x541B4]
        check("(8a) 0x541b4 由迴圈證到 64(access)", jj["grade"] == "access" and len(w["loop"]) == 6
              and not w["unresolved"])
        check("(8b) 0x3fdb7 遞減迴圈 esi 15..0", w["loop"][0x3FDB7][2]["values"] == (0, 15))
        w, jj = by[0x52A94]
        check("(8c) 0x52a94 access 64,rep 0x3eccf 長度 64", jj["grade"] == "access"
              and w["rep"].get(0x3ECCF) == (0x52A94, 0x52AD4))
        w, jj = by[0x541F4]
        check("(8d) 0x541f4 rep 0x3f972 = 43 byte", w["rep"].get(0x3F972) == (0x541F4, 0x541F4 + 43))
        check("(8e) 0x541f4 鎖定宣告 0x100(declared)", jj["grade"] == "declared" and jj["lb_declared"] == 256
              and w["range"].get(0x3F524) == (0x541F4, 0x542F4, "lock"))
        check("(8f) 範圍函式恰好 0x3666c lock / 0x36683 unlock", col["ranged"] == {0x3666C: "lock", 0x36683: "unlock"})
        w, jj = by[0x5417C]
        check("(8g) 0x5417c 只證到 25 / 26(partial)", jj["grade"] == "partial" and jj["lb_access"] == 25)
        w, jj = by[0x52387]
        check("(8h) 0x52387 由 [0x53f4a] 的立即數 5 證到 6(value)", jj["grade"] == "value" and jj["lb_access"] == 5
              and w["value"].get(0x27A53) == (0x52387, 0x5238D, 0x53F4A, 5))
        w, jj = by[0x51B91]
        check("(8i) 0x51b91 content;[0x51a8f] 的 255 哨兵讓 value 不採信",
              jj["grade"] == "content" and not w["value"] and "255" in w["unresolved"].get(0x1199C, ""))
        w, jj = by[0x53A8D]
        check("(8j) int386_regs 只證到 2(partial,經指標交給函式庫)", jj["grade"] == "partial" and jj["lb_access"] == 2)
        check("(8k) 記憶體運算元與 re_coverage 逐筆相同(非空)", sum(len(w["mem_sites"]) for _r, w, _j in out) > 4000)
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
    funcs, regions, cov, content = load()
    out, col = run(funcs, regions, cov, content)
    if a.show:
        return show(out, int(a.show, 16))
    return report(out, col, a.verbose)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
