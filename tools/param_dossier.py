#!/usr/bin/env python3
"""逐函式的參數資料卡,與「人工讀過反組譯」的登錄(doc98 續一百一十六)。

為什麼有這支
------------
`screen_summaries_by_calllog.py` 的篩選只比得到「名稱有型別、而且有值可比」的參數。續一百一十四到一百一十六
找到的 12 筆參數列錯誤裡,有 9 筆是靠人把下面四樣東西並排看才看出來的:

1. 本體在哪些指令引用這個參數的堆疊格;
2. 它原樣轉交給哪個被呼叫端的第幾個參數(那個參數在摘要裡叫什麼);
3. 實機紀錄裡這個位置最常見的值;
4. EXE 的呼叫點各推了什麼(常數、呼叫者的參數、別的函式的回傳)。

這四樣原本是每輪重寫一次的暫存腳本。本工具把它固定下來(`NAME ...`),並把讀過的結果登錄在
`docs/data/param_read_review.json`,讓「還沒有任何依據的參數」是一個數得出來、可以歸零的數字(`--coverage`)。

登錄(手動維護)
----------------
每筆 `{addr, name, param, pname, basis: [{kind, at, insn?}], note, date}`:第 `param` 個參數(摘要裡位置確定的第幾個)
名叫 `pname`,依據是 `basis`。登錄是可以被推翻的宣稱,每筆都要過檢查:

- `pname` 必須等於目前摘要該位置的名稱 —— 摘要改過,舊的閱讀結論就過期(FAIL,請重讀)。
- `basis` 至少一筆,三種:
  - `body`:`at` 是本體裡的指令,而且那個指令**引用這個參數的堆疊格**;`insn` 必須與反組譯相同。
  - `caller`:`at` 是 EXE 裡直接呼叫這個函式的呼叫點(本體不讀的參數,名稱只能依呼叫端)。
  - `live`:實機紀錄在這個參數的位置有值(名稱依實機值;`at` 不用填)。
  - `reg`(續一百一十八):Watcom 暫存器傳參的函式(`SS.call_conv` 回 'reg'),第 k 個參數在 eax / edx / ebx / ecx 的
    第 k 個。`at` 必須是本體依位址順序、第一個 call 之前**第一個提到那個暫存器(含 ax / al 這類部分暫存器)**的指令,
    而且不是單純覆寫它(`mov r, …` / `xor r, r`);`insn` 必須與反組譯相同。這只擋寫錯暫存器或指到已被覆寫之後的
    指令 —— 依位址順序不等於執行順序,它是人工閱讀的佐證,不是證明。`push r` 不算提到(續一百一十九):那只是把它
    存起來,暫存器裡的入口值還在,真正的第一次使用在後面。例外是它被推成第一個 call 的引數(call 後面緊跟
    `add esp, N`,而且那個 push 落在 N / 4 個引數之內)—— 那就是讀。
  - `via`(續一百一十九):暫存器傳參的函式,本體在第一個 call 之前完全沒有提到那個暫存器 —— 入口值原樣交給被呼叫端。
    `via` 是本體依位址順序的第一個 call(必須是直接呼叫),`at` / `insn` 是**被呼叫端**裡讀它的指令:被呼叫端第一個
    提到那個暫存器的指令(不是覆寫);或者被呼叫端入口就 `push r` 存起來時,之後以堆疊位置讀那一份的指令。
  - `raw`(續一百一十九):只給**走不出本體**的函式(以間接 jmp 結束、切換堆疊)。`at` 必須在入口起的直線段裡
    (依位址順序解到第一個控制轉移或改寫 ESP 的指令為止),而且引用這個參數的堆疊格;`insn` 必須相同。
    走得出本體的函式不收,請用 `body`。
  - `indirect`(續一百一十九):只經函式指標被呼叫、而且**本體不讀**的參數(回呼的簽章由呼叫它的那一端決定)。
    `store` 必須是 fixup 指到這個函式的位置(有人存了它的位址);`at` 必須是間接 call,後面緊跟 `add esp, N`,
    N / 4 等於摘要的堆疊格數;`push_at` / `push_insn` 必須是那個呼叫點推這個參數的 push。工具**不檢查**那個間接 call
    真的會走到這個函式(那要資料流),所以它和 `caller` 一樣是名稱的來源,不是證明;本體有引用的參數不收,請用 `body`。
- 同一個 (函式, 參數) 只能一筆。

`--coverage` 的三個數字:機器比過(實機型別 / 值流 / 讀寫角色任一個篩選比到)、只有人工讀過、兩者都沒有。
都沒有的那些就是下一批要讀的(`--worklist` 列出)。rc 1 只表示登錄本身有錯;「都沒有」不算失敗,但會印出來。
另印「名稱沿呼叫邊比過」的個數(`param_name`,續一百一十七)。它**不計入**機器比過:邊兩端的名稱都是人寫的,
相容只代表兩邊說法一致,不是獨立的證據;`--worklist` 會標出哪些參數至少有這一項。

用法:
    python tools/param_dossier.py NAME|0xADDR ... [--dis N]   # 資料卡(--dis:另印本體前 N 個指令)
    python tools/param_dossier.py --coverage                  # 登錄檢查 + 三個數字
    python tools/param_dossier.py --worklist                  # 沒有任何依據的參數
    python tools/param_dossier.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen_summaries_by_calllog as SS  # noqa: E402

ROOT = SS.ROOT
READS_JSON = ROOT / "docs" / "data" / "param_read_review.json"
BASIS_KINDS = ("body", "caller", "live", "reg", "via", "raw", "indirect")
Refs = dict[int, list[tuple[int, str]]]
RegUses = dict[str, tuple[int, str, bool]]
SavedRefs = dict[str, list[tuple[int, str]]]
Site = tuple[str, int, list[tuple[int, str] | None]]       # 間接呼叫點:(call 的文字, 引數個數, 各引數的 push)
# 暫存器參數與它的部分暫存器:先寫 al 再讀 eax,讀到的已經不是入口值
REG_ALIASES = {"eax": ("eax", "ax", "al", "ah"), "edx": ("edx", "dx", "dl", "dh"),
               "ebx": ("ebx", "bx", "bl", "bh"), "ecx": ("ecx", "cx", "cl", "ch")}
_OVERWRITE = ("mov", "lea", "pop", "movzx", "movsx")     # 第一個運算元是目的、不讀它原本的值
_ZEROING = ("xor", "sub")                                # 兩個運算元相同時是清 0


# ---------------------------------------------------------------- 純函式(selftest 直接測)

def named_params(summary: str) -> list[tuple[int, str]]:
    """摘要裡位置確定的具名參數 -> [(第 k 個, 名稱)]。與 `SS.audit_names` 同一個範圍:省略記號、暫存器寫法不算。"""
    params, _ = SS.parse_sig(summary or "")
    if not params or any("=" in p or "個參數" in p for p in params):
        return []
    return [(k, pn) for k, pn in enumerate(SS.positioned(params), 1) if SS.is_named(pn)]


def param_slots(summary: str, k: int) -> set[int]:
    """第 k 個參數佔的堆疊格(1 起;double 佔 2 格)。"""
    pre = SS.positioned(SS.parse_sig(summary or "")[0])
    start = SS.slot_starts(pre)[k - 1]
    return {start, start + 1} if pre[k - 1] == "double" else {start}


def body_refs(cg, target: int, entries: list[int]) -> Refs | None:
    """本體引用每個堆疊參數格的指令 -> {格: [(位址, 指令文字)]};走不出本體回 None。"""
    res = SS.cfg_states(cg, target, entries, {}, lambda i, td, st: st, frozenset())
    if res is None:
        return None
    _, trace, ins = res
    out: Refs = {}
    for at in sorted(ins):
        i = ins[at]
        for o in (i.op_str.split(",") if i.op_str else []):
            k = SS._stack_param(o.strip(), *trace[at])
            if k:
                out.setdefault(k, []).append((at, f"{i.mnemonic} {i.op_str}".strip()))
    return out


def reg_first_uses(cg, target: int, entries: list[int]) -> RegUses | None:
    """本體依位址順序、第一個 call 之前,第一個提到各暫存器參數的指令 -> {暫存器: (位址, 指令文字, 是不是單純覆寫)}。

    「提到」含部分暫存器(`REG_ALIASES`)。`push r` 不算,除非在它之前沒有別的指令提到 r、而且那個 push 是
    第一個 call 的引數(call 後面緊跟 `add esp, N`,push 落在 N / 4 個引數之內)。
    單純覆寫 = `mov` / `lea` / `pop` 把它當目的而來源沒有用到它,或 `xor r, r` / `sub r, r`:入口值沒有被讀。call 之後不再看 —— 入口值可能已交給被呼叫端或被它改掉。
    走不出本體回 None。"""
    res = SS.cfg_states(cg, target, entries, {}, lambda i, td, st: st, frozenset())
    if res is None:
        return None
    _, trace, ins = res
    out: RegUses = {}
    pushed: dict[str, int] = {}
    for at in sorted(ins):
        i = ins[at]
        ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
        for reg, al in REG_ALIASES.items():
            pat = re.compile(r"\b(?:" + "|".join(al) + r")\b")
            if reg in out or not pat.search(i.op_str or ""):
                continue
            if i.mnemonic == "push" and ops == [reg]:
                pushed.setdefault(reg, at)       # 只是存起來,暫存器裡的入口值還在;是不是 call 的引數到 call 才知道
                continue
            dest_only = ops[0] in al and not any(pat.search(o) for o in ops[1:])
            same = len(ops) == 2 and ops[0] == ops[1] and ops[0] in al
            out[reg] = (at, f"{i.mnemonic} {i.op_str}".strip(),
                        (i.mnemonic in _OVERWRITE and dest_only) or (i.mnemonic in _ZEROING and same))
        if i.mnemonic == "call":
            nxt = ins.get(at + i.size)
            m = re.fullmatch(r"esp, (0x[0-9a-f]+|\d+)", nxt.op_str) if nxt is not None and nxt.mnemonic == "add" else None
            for reg, pa in pushed.items():       # pushed 只記「在它之前沒有別的指令提到 r」的 push,所以它最早
                if m and 1 <= (trace[at][0] - trace[pa][0]) // 4 <= int(m.group(1), 0) // 4:
                    out[reg] = (pa, f"push {reg}", False)
            break
    return out


def first_call(cg, target: int, entries: list[int]) -> tuple[int, int | None] | None:
    """本體依位址順序的第一個 call -> (位址, 直接呼叫的目標;間接呼叫為 None);沒有 call 或走不出本體回 None。"""
    res = SS.cfg_states(cg, target, entries, {}, lambda i, td, st: st, frozenset())
    for at in sorted(res[2] if res else {}):
        i = res[2][at]
        if i.mnemonic == "call":
            return at, (int(i.op_str, 16) if i.op_str.startswith("0x") else None)
    return None


def saved_copy_refs(cg, target: int, entries: list[int]) -> SavedRefs | None:
    """入口就被 `push r` 存起來的暫存器參數,本體之後以堆疊位置引用那一份的指令 -> {暫存器: [(位址, 指令文字)]}。

    只認第一個 call 之前、而且在它之前沒有別的指令提到 r 的那個 push(存的才是入口值)。走不出本體回 None。"""
    res = SS.cfg_states(cg, target, entries, {}, lambda i, td, st: st, frozenset())
    if res is None:
        return None
    _, trace, ins = res
    depth: dict[str, int] = {}
    seen: set[str] = set()
    for at in sorted(ins):
        i = ins[at]
        for reg, al in REG_ALIASES.items():
            if reg not in seen and re.search(r"\b(?:" + "|".join(al) + r")\b", i.op_str or ""):
                seen.add(reg)
                if i.mnemonic == "push" and i.op_str.strip() == reg:
                    depth[reg] = trace[at][0] + 4           # push 之後它在入口 ESP 往下這麼多 byte 的地方
        if i.mnemonic == "call":
            break
    out: SavedRefs = {reg: [] for reg in depth}
    for at in sorted(ins):
        i = ins[at]
        for o in (i.op_str.split(",") if i.op_str else []):
            d = SS._depth(o.strip(), *trace[at])
            for reg, want in depth.items():
                if d == want:
                    out[reg].append((at, f"{i.mnemonic} {i.op_str}".strip()))
    return out


def raw_refs(cg, target: int, limit: int = 64) -> Refs:
    """入口起的直線段裡引用堆疊參數格的指令 -> {格: [(位址, 指令文字)]}。給走不出本體的函式用。

    依位址順序解,自己數 ESP 位移(push / pop / `sub|add esp, 常數`)與 ebp 框架(`mov ebp, esp`);遇到控制轉移、
    其他改寫 ESP 的指令、或不認得的堆疊指令(pushal / leave 之類)就停 —— 之後的位移不可信。"""
    delta, ebp, out, at = 0, None, {}, target
    for _ in range(limit):
        i = cg._insn(at)
        if i is None or i.mnemonic.startswith(("j", "call", "ret", "loop", "iret")):
            break
        ops = [o.strip() for o in i.op_str.split(",")] if i.op_str else []
        for o in ops:
            k = SS._stack_param(o, delta, ebp)
            if k:
                out.setdefault(k, []).append((at, f"{i.mnemonic} {i.op_str}".strip()))
        if i.mnemonic in ("push", "pop"):
            delta += 4 if i.mnemonic == "push" else -4
            if i.mnemonic == "pop" and ops == ["ebp"]:
                ebp = None
        elif i.mnemonic.startswith(("push", "pop", "enter", "leave")):
            break
        elif ops and ops[0] == "esp":
            if i.mnemonic not in ("sub", "add") or not re.fullmatch(r"(0x[0-9a-f]+|\d+)", ops[1]):
                break
            delta += int(ops[1], 0) * (1 if i.mnemonic == "sub" else -1)
        elif ops and ops[0] == "ebp" and i.mnemonic != "cmp" and i.mnemonic != "test":
            ebp = delta if (i.mnemonic == "mov" and ops[1] == "esp") else None
        at += i.size
    return out


def indirect_site(cg, owner: int, entries: list[int], at: int) -> Site | None:
    """owner 本體裡位於 at 的間接 call -> (call 的文字, 引數個數, [第 j 個引數的 push (位址, 文字) 或 None]);
    不是間接 call、後面沒有緊跟 `add esp, N`、或走不出 owner 的本體回 None。

    第 j 個引數的 push = call 之前依位址往回、進入時 ESP 位移正好比 call 少 4j 的最近一個 push
    (中間夾別的指令沒關係,位移對得上才算)。"""
    res = SS.cfg_states(cg, owner, entries, {}, lambda i, td, st: st, frozenset())
    if res is None or at not in res[2]:
        return None
    _, trace, ins = res
    i = ins[at]
    nxt = ins.get(at + i.size)
    m = re.fullmatch(r"esp, (0x[0-9a-f]+|\d+)", nxt.op_str) if nxt is not None and nxt.mnemonic == "add" else None
    if i.mnemonic != "call" or i.op_str.startswith("0x") or not m:
        return None
    n = int(m.group(1), 0) // 4
    before = sorted((a for a in ins if a < at), reverse=True)
    pushes: list[tuple[int, str] | None] = []
    for j in range(1, n + 1):
        hit = next((a for a in before if ins[a].mnemonic == "push" and trace[a][0] == trace[at][0] - 4 * j), None)
        pushes.append(None if hit is None else (hit, f"push {ins[hit].op_str}"))
    return f"call {i.op_str}", n, pushes


@dataclass
class Extra:
    """`via` / `raw` / `indirect` 三種依據要用到的事實(其他依據不用)。"""
    raw: Refs = field(default_factory=dict)                 # raw_refs
    call: tuple[int, int | None] | None = None              # first_call
    callee_regs: RegUses | None = None                      # 第一個 call 的目標的 reg_first_uses
    callee_saved: SavedRefs | None = None                   # 第一個 call 的目標的 saved_copy_refs
    ptr_refs: frozenset[int] = frozenset()                  # fixup 指到這個函式的位置
    sites: dict[int, Site | None] = field(default_factory=dict)     # 間接呼叫點 -> indirect_site


def _hex(b: dict, key: str) -> int | None:
    try:
        return int(b[key], 16)
    except (KeyError, TypeError, ValueError):
        return None


def check_entry(r: dict, fn: dict | None, refs: Refs | None, sites: set[int], live_slots: set[int],
                regs: RegUses | None = None, conv: str | None = None, more: Extra | None = None) -> str | None:
    """登錄的一筆 -> 錯誤訊息(None = 成立)。

    fn:登錄檔指到的函式(function_names.json 的條目;None = 不存在)。refs:`body_refs` 的結果(None = 走不出本體)。
    sites:EXE 裡直接呼叫它的呼叫點。live_slots:實機紀錄有值的堆疊格。
    regs:`reg_first_uses` 的結果(None = 走不出本體);conv:`SS.call_conv` 的結果。兩個只有 `reg` / `via` 依據會用到。
    more:`via` / `raw` / `indirect` 依據要用到的事實(`Extra`)。
    """
    more = more or Extra()
    if fn is None:
        return "函式不在 function_names.json"
    if r.get("name") != fn["name"]:
        return f"name {r.get('name')!r} 與登錄 {fn['name']!r} 不同"
    k = r.get("param")
    named = dict(named_params(fn.get("summary") or ""))
    if not isinstance(k, int) or isinstance(k, bool) or k not in named:
        return f"第 {k!r} 個不是摘要裡位置確定的具名參數"
    if r.get("pname") != named[k]:
        return f"第 {k} 個參數摘要現在叫 {named[k]!r},登錄寫 {r.get('pname')!r}(摘要改過,閱讀結論過期,請重讀)"
    if not str(r.get("note") or "").strip():
        return "沒有 note(讀到了什麼)"
    basis = r.get("basis")
    if not isinstance(basis, list) or not basis:
        return "沒有 basis"
    slots = param_slots(fn["summary"], k)
    for b in basis:
        kind = b.get("kind") if isinstance(b, dict) else None
        if kind not in BASIS_KINDS:
            return f"basis kind {kind!r} 不認得"
        if kind == "live":
            if not slots & live_slots:
                return f"basis live:實機紀錄在第 {k} 個參數的位置沒有值"
            continue
        try:
            at = int(b["at"], 16)
        except (KeyError, TypeError, ValueError):
            return f"basis {kind}:at 格式錯"
        if kind == "caller":
            if at not in sites:
                return f"basis caller:{at:#x} 不是直接呼叫這個函式的呼叫點"
            continue
        if kind == "reg":
            if conv != "reg":
                return "basis reg:這個函式不是暫存器傳參"
            if k > len(SS.VC.REG_ARGS):
                return f"basis reg:第 {k} 個參數不在暫存器(只有前 {len(SS.VC.REG_ARGS)} 個)"
            if regs is None:
                return "basis reg:走不出這個函式的本體,無從檢查"
            reg = SS.VC.REG_ARGS[k - 1]
            hit = regs.get(reg)
            if hit is None:
                return f"basis reg:本體在第一個 call 之前沒有提到 {reg}"
            if hit[0] != at:
                return f"basis reg:第一個提到 {reg} 的指令在 {hit[0]:#x},登錄寫 {at:#x}"
            if hit[2]:
                return f"basis reg:{at:#x} 只是覆寫 {reg},沒有讀入口值"
            if b.get("insn") != hit[1]:
                return f"basis reg:{at:#x} 的指令是 {hit[1]!r},登錄寫 {b.get('insn')!r}"
            continue
        if kind == "via":
            if conv != "reg" or k > len(SS.VC.REG_ARGS):
                return "basis via:這個函式不是暫存器傳參,或第 k 個參數不在暫存器"
            reg = SS.VC.REG_ARGS[k - 1]
            if regs is None or reg in regs:
                return f"basis via:本體在第一個 call 之前自己提到了 {reg}(或走不出本體),請用 reg"
            if more.call is None or more.call[1] is None or more.call[0] != _hex(b, "via"):
                return "basis via:via 不是本體依位址順序的第一個 call,或它不是直接呼叫"
            first = (more.callee_regs or {}).get(reg)
            good = [first[:2]] if first is not None and not first[2] else []     # 被呼叫端直接讀暫存器
            good = good + (more.callee_saved or {}).get(reg, [])                # 或讀它存在堆疊上的那一份
            if (at, b.get("insn")) not in good:
                return f"basis via:{at:#x} {b.get('insn')!r} 不是被呼叫端 {more.call[1]:#x} 讀 {reg} 入口值的指令"
            continue
        if kind == "raw":
            if refs is not None:
                return "basis raw:這個函式走得出本體,請用 body"
            hit = [txt for s in slots for a, txt in more.raw.get(s, []) if a == at]
            if b.get("insn") not in hit:
                return f"basis raw:{at:#x} {b.get('insn')!r} 不是入口直線段裡引用第 {k} 個參數堆疊格的指令"
            continue
        if kind == "indirect":
            if refs is None or any(refs.get(s) for s in slots):
                return "basis indirect:本體有引用這個參數(或走不出本體),請用 body"
            if _hex(b, "store") not in more.ptr_refs:
                return "basis indirect:store 不是 fixup 指到這個函式的位置"
            site = more.sites.get(at)
            if site is None:
                return f"basis indirect:{at:#x} 不是後面緊跟 add esp 的間接 call"
            pre = SS.positioned(SS.parse_sig(fn["summary"])[0])
            total = SS.slot_starts(pre)[-1] + (1 if pre[-1] == "double" else 0)
            if site[0] != b.get("insn") or site[1] != total:
                return f"basis indirect:{at:#x} 是 {site[0]!r}、推 {site[1]} 個引數;登錄寫 {b.get('insn')!r},摘要有 {total} 格"
            if site[2][min(slots) - 1] != (_hex(b, "push_at"), b.get("push_insn")):
                return f"basis indirect:{at:#x} 推第 {k} 個參數的是 {site[2][min(slots) - 1]},與登錄不同"
            continue
        if refs is None:
            return "basis body:走不出這個函式的本體,無從檢查(改用 caller / live)"
        hit = [txt for s in slots for a, txt in (refs or {}).get(s, []) if a == at]
        if not hit:
            return f"basis body:{at:#x} 沒有引用第 {k} 個參數的堆疊格"
        if b.get("insn") not in hit:
            return f"basis body:{at:#x} 的指令是 {hit[0]!r},登錄寫 {b.get('insn')!r}"
    return None


def classify(named: list[tuple[int, int]], machine: set[tuple[int, int]],
             read: set[tuple[int, int]]) -> tuple[int, int, list[tuple[int, int]]]:
    """具名參數 -> (機器比過的個數, 只有人工讀過的個數, 兩者都沒有的清單)。"""
    rest = [p for p in named if p not in machine and p not in read]
    return sum(p in machine for p in named), sum(p in read and p not in machine for p in named), rest


# ---------------------------------------------------------------- 真實資料

@dataclass
class Ctx:
    st: object
    names: list[dict]
    by: dict[int, dict]
    prof: dict[str, dict]
    cg: object
    cleanups: dict[int, set[int]]
    sources: dict


def load_ctx() -> Ctx:
    from callgraph_le import CG
    import verify_address_claim_coverage as CC
    st = SS.VC.load_static()
    names = json.loads(SS.NAMES_JSON.read_text(encoding="utf-8"))["names"]
    prof = json.loads(SS.PROFILES_JSON.read_text(encoding="utf-8"))["functions"]
    cg = CG(CC.EXE)
    cleanups = SS.call_cleanups(st.code, st.base, set(st.entries))
    sources = SS.arg_sources(cg, st.entries, st.code, st.base, st.fixups, st.thunk_of, cleanups, st.argc)
    return Ctx(st, names, {int(x["addr"], 16): x for x in names}, prof, cg, cleanups, sources)


def live_slots(ctx: Ctx, a: int) -> set[int]:
    """實機紀錄有值的堆疊格。"""
    p = ctx.prof.get(f"{a:#x}")
    return {int(s[1:]) for s, v in (p["params"] if p else {}).items() if s.startswith("s") and v.get("top")}


def load_reads(doc: dict, ctx: Ctx) -> tuple[dict[tuple[int, int], dict], list[str]]:
    """登錄檔 -> ({(函式, 第 k 個): 條目}, 錯誤)。有錯的條目不採用。"""
    out: dict[tuple[int, int], dict] = {}
    errs: list[str] = []
    memo: dict[int, Refs | None] = {}
    rmemo: dict[int, RegUses | None] = {}
    ents = sorted(ctx.st.entries)
    for i, r in enumerate(doc.get("reads", [])):
        try:
            a = int(r["addr"], 16)
        except (KeyError, TypeError, ValueError):
            errs.append(f"#{i}:addr 格式錯")
            continue
        if a not in memo:
            memo[a] = body_refs(ctx.cg, a, ctx.st.entries) if a in ctx.by else None
            rmemo[a] = reg_first_uses(ctx.cg, a, ctx.st.entries) if a in ctx.by else None
        more = None
        kinds = {b.get("kind") for b in r.get("basis") or [] if isinstance(b, dict)}
        if a in ctx.by and kinds & {"via", "raw", "indirect"}:
            call = first_call(ctx.cg, a, ctx.st.entries)
            t = call[1] if call else None
            ats = {_hex(b, "at") for b in r["basis"] if b.get("kind") == "indirect"} - {None}
            more = Extra(raw_refs(ctx.cg, a), call,
                         reg_first_uses(ctx.cg, t, ctx.st.entries) if t is not None else None,
                         saved_copy_refs(ctx.cg, t, ctx.st.entries) if t is not None else None,
                         frozenset(src for src, dst in ctx.st.fixups.items() if dst == a),
                         {x: indirect_site(ctx.cg, ents[max(bisect.bisect_right(ents, x) - 1, 0)], ctx.st.entries, x)
                          for x in ats})
        e = check_entry(r, ctx.by.get(a), memo[a], set(ctx.sources.get(a, {})), live_slots(ctx, a), rmemo[a],
                        SS.call_conv(a, ctx.cleanups, ctx.st.argc), more)
        key = (a, r.get("param"))
        if e is None and key in out:
            e = "重複"
        if e:
            errs.append(f"#{i} {r['addr']} {r.get('name')} 第 {r.get('param')} 個:{e}")
        else:
            out[key] = r
    return out, errs


def coverage(ctx: Ctx, reads: dict[tuple[int, int], dict]
             ) -> tuple[list[tuple[int, int]], set[tuple[int, int]], dict, set[tuple[int, int]]]:
    """(全部具名參數, 機器比過的, 各篩選比過的個數, 名稱沿呼叫邊比過的)。

    機器比過 = 實機型別 / 值流 / 讀寫角色任一個比到。名稱沿呼叫邊(`param_name`)另外回,不併入:它是一致性檢查。"""
    sc = SS.run(SS.REVIEW_JSON)[0]
    named = [(int(x["addr"], 16), k) for x in ctx.names for k, _ in named_params(x.get("summary") or "")]
    universe = set(named)
    parts = {"實機型別": sc.type_checked & universe, "值流": sc.flow_checked & universe, "讀寫角色": sc.role_checked & universe}
    return named, set().union(*parts.values()), {k: len(v) for k, v in parts.items()}, sc.name_checked & universe


def show_source(ctx: Ctx, d) -> str:
    if d is None or d == "*":
        return "不明"
    if d[0] == "imm":
        return f"{d[1]:#x}"
    if d[0] == "param":
        nm = dict(named_params(ctx.by.get(d[1], {}).get("summary") or "")).get(d[2], "?")
        return f"{ctx.by.get(d[1], {}).get('name', hex(d[1]))} 的第 {d[2]} 個({nm})"
    if d[0] == "ret":
        return f"{ctx.by.get(d[1], {}).get('name', hex(d[1]))} 的回傳"
    if d[0] == "load":
        return f"[{d[1]:#x}]"
    return str(d[0])


def dossier(ctx: Ctx, a: int) -> dict:
    """一個函式的資料卡:每個堆疊格的名稱、引用它的指令、原樣轉交、實機值、呼叫端來源。"""
    x = ctx.by.get(a, {"name": hex(a), "summary": ""})
    summ = x.get("summary") or ""
    params, _ = SS.parse_sig(summ)
    pre = SS.positioned(params)
    starts = SS.slot_starts(pre)
    slot_name = {s: pn for pn, s in zip(pre, starts)}
    refs = body_refs(ctx.cg, a, ctx.st.entries)
    walkable = refs is not None
    if not walkable:
        refs = raw_refs(ctx.cg, a)               # 只有入口的直線段
    nargs = max(list(ctx.cleanups.get(a, set())) + [ctx.st.argc.get(a) or 0] + list(refs or {}))
    fw: list = []
    if nargs:
        SS.param_uses(ctx.cg, a, ctx.st.entries, nargs, False, fw, exact=True)
    p = ctx.prof.get(f"{a:#x}")
    rows = []
    for j in range(1, nargs + 1):
        fws = sorted({(ctx.by.get(t, {}).get("name", hex(t)), jj,
                       dict(named_params(ctx.by.get(t, {}).get("summary") or "")).get(jj, "?"), site)
                      for kk, t, jj, site in fw if kk == j and t is not None and isinstance(jj, int)
                      and jj <= (SS.pushed_args(ctx.st.code, ctx.st.base, site) or 0)})
        rows.append({"slot": j, "name": slot_name.get(j, "(未列)"), "refs": (refs or {}).get(j, []), "forwards": fws,
                     "live": ((p["params"].get(f"s{j}") or {}).get("top", [])[:5] if p else None),
                     "sources": sorted({show_source(ctx, d) for _, ag in ctx.sources.get(a, {}).values()
                                        for d in ag.get(j, SS.UNK)})[:6]})
    return {"addr": a, "name": x["name"], "summary": summ, "params": params, "cleanups": sorted(ctx.cleanups.get(a, set())),
            "argc": ctx.st.argc.get(a), "recorded": p is not None, "walkable": walkable, "slots": rows}


def format_dossier(d: dict) -> list[str]:
    lines = [f"===== {d['addr']:#x} {d['name']}  參數列 {d['params']}  清堆疊 {d['cleanups']}  argc {d['argc']}  "
             f"有實機紀錄 {d['recorded']}" + ("" if d["walkable"] else "  (走不出本體:引用只看入口的直線段)"),
             f"   摘要:{d['summary'][:300]}"]
    for r in d["slots"]:
        lines.append(f"  第 {r['slot']} 格 {r['name']}")
        lines.append("     引用:" + ("; ".join(f"{a:#x} {t}" for a, t in r["refs"][:6]) or "(本體沒有引用)"))
        if r["forwards"]:
            lines.append("     原樣轉交:" + "; ".join(f"{n} 第 {j} 個 {pn} @{s:#x}" for n, j, pn, s in r["forwards"][:6]))
        lines.append(f"     實機:{r['live']}  呼叫端推:{r['sources']}")
    return lines


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    fails: list[str] = []

    def chk(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
        if not ok:
            fails.append(label)

    class _I:
        def __init__(self, address: int, mnemonic: str, op_str: str) -> None:
            self.address, self.mnemonic, self.op_str, self.size = address, mnemonic, op_str, 1

    class _G:
        def __init__(self, bodies: dict[int, list[tuple[str, str]]]) -> None:
            self.m = {at + k: _I(at + k, mn, op) for at, body in bodies.items() for k, (mn, op) in enumerate(body)}

        def _insn(self, a: int):
            return self.m.get(a)

    print("[1] 具名參數與堆疊格")
    chk("位置確定的具名參數", named_params("(dst, .., x, ..., late):…"), [(1, "dst"), (3, "x")])
    chk("暫存器寫法 / N 個參數 / 沒有參數列 -> 空", (named_params("(eax = ptr, x):…"), named_params("(3 個參數) …"),
                                        named_params("無參數")), ([], [], []))
    chk("double 佔 2 格,後面的往後移", (param_slots("(double, n):…", 1), param_slots("(double, n):…", 2)), ({1, 2}, {3}))

    print("[2] 本體引用")
    g = _G({0x100: [("push", "ebx"), ("mov", "eax, dword ptr [esp + 8]"), ("push", "dword ptr [esp + 0x10]"),
                    ("add", "esp, 4"), ("pop", "ebx"), ("mov", "ecx, dword ptr [esp]"), ("ret", "")]})
    refs = body_refs(g, 0x100, [0x100])
    chk("引用:push 之後的位移換算、push [esp+X] 也算;回傳位址那一格不是參數", refs,
        {1: [(0x101, "mov eax, dword ptr [esp + 8]")], 3: [(0x102, "push dword ptr [esp + 0x10]")]})
    chk("走不出本體 -> None", body_refs(_G({}), 0x100, [0x100]), None)

    print("[3] 登錄的一筆")
    fn = {"addr": "0x100", "name": "f", "summary": "(a, b, ...):…"}
    ok = {"addr": "0x100", "name": "f", "param": 1, "pname": "a", "note": "讀到了", "date": "2026-10-12",
          "basis": [{"kind": "body", "at": "0x101", "insn": "mov eax, dword ptr [esp + 8]"}]}

    def ce(**kw) -> str | None:
        return check_entry({**ok, **kw}, fn, refs, {0x900}, {2})

    chk("成立", ce(), None)
    chk("函式不存在", check_entry(ok, None, refs, set(), set()), "函式不在 function_names.json")
    chk("name 不同", (ce(name="g") or "")[:6], "name '")
    chk("參數超出範圍 / 不是整數 / 省略記號的位置", [bool(ce(param=v)) for v in (0, 9, "1", True, 3)], [True] * 5)
    chk("摘要改過 -> 過期", "閱讀結論過期" in (ce(pname="old") or ""), True)
    chk("沒有 note", ce(note="  "), "沒有 note(讀到了什麼)")
    chk("沒有 basis", (ce(basis=[]), ce(basis=None)), ("沒有 basis", "沒有 basis"))
    chk("kind 不認得", "不認得" in (ce(basis=[{"kind": "guess"}]) or ""), True)
    chk("body:指令引用的是別的參數", "沒有引用第 1 個參數" in (ce(basis=[{"kind": "body", "at": "0x102",
                                                             "insn": "push dword ptr [esp + 0x10]"}]) or ""), True)
    chk("body:位址不在本體", "沒有引用第 1 個參數" in (ce(basis=[{"kind": "body", "at": "0x555", "insn": "x"}]) or ""), True)
    chk("body:指令文字不同", "的指令是" in (ce(basis=[{"kind": "body", "at": "0x101", "insn": "mov eax, 1"}]) or ""), True)
    chk("body:at 格式錯", "at 格式錯" in (ce(basis=[{"kind": "body", "insn": "x"}]) or ""), True)
    chk("body:走不出本體 -> 無從檢查", "走不出" in (check_entry(ok, fn, None, set(), set()) or ""), True)
    chk("caller:是呼叫點 -> 成立;不是 -> 錯", (ce(basis=[{"kind": "caller", "at": "0x900"}]),
                                      "不是直接呼叫" in (ce(basis=[{"kind": "caller", "at": "0x901"}]) or "")), (None, True))
    chk("live:該位置有實機值 -> 成立(第 2 個);沒有 -> 錯(第 1 個)",
        (ce(param=2, pname="b", basis=[{"kind": "live"}]), "沒有值" in (ce(basis=[{"kind": "live"}]) or "")), (None, True))
    chk("多筆 basis:有一筆不成立就錯", "不是直接呼叫" in (ce(basis=ok["basis"] + [{"kind": "caller", "at": "0x1"}]) or ""), True)
    chk("多筆 basis:live 成立後仍檢查下一筆", "不是直接呼叫" in (ce(param=2, pname="b", basis=[
        {"kind": "live"}, {"kind": "caller", "at": "0x1"}]) or ""), True)
    chk("多筆 basis:caller 成立後仍檢查下一筆", "沒有值" in (ce(basis=[{"kind": "caller", "at": "0x900"}, {"kind": "live"}]) or ""),
        True)

    print("[3b] 暫存器傳參的依據(reg)")
    gr = _G({0x200: [("push", "esi"), ("sub", "ecx, ecx"), ("mov", "cx, word ptr [eax + 8]"), ("mov", "ebx, 1"),
                     ("cmp", "word ptr [edx + 8], 0"), ("pop", "esi"), ("ret", "")]})
    ru = reg_first_uses(gr, 0x200, [0x200])
    chk("第一個提到:讀 [eax + 8] 算讀;sub ecx, ecx 與 mov ebx, 1 是覆寫", ru,
        {"ecx": (0x201, "sub ecx, ecx", True), "eax": (0x202, "mov cx, word ptr [eax + 8]", False),
         "ebx": (0x203, "mov ebx, 1", True), "edx": (0x204, "cmp word ptr [edx + 8], 0", False)})
    chk("部分暫存器先被寫 -> 第一個提到的是那一條(覆寫)",
        reg_first_uses(_G({0x200: [("mov", "al, 1"), ("test", "eax, eax"), ("ret", "")]}), 0x200, [0x200]),
        {"eax": (0x200, "mov al, 1", True)})
    chk("mov 的來源用到自己不算覆寫;xor 兩個不同暫存器不算清 0",
        reg_first_uses(_G({0x200: [("mov", "eax, dword ptr [eax + 4]"), ("xor", "edx, ebx"), ("ret", "")]}), 0x200, [0x200]),
        {"eax": (0x200, "mov eax, dword ptr [eax + 4]", False), "edx": (0x201, "xor edx, ebx", False),
         "ebx": (0x201, "xor edx, ebx", False)})
    chk("call 之後不看(call 那一條自己算)",
        reg_first_uses(_G({0x200: [("test", "edx, edx"), ("call", "eax"), ("test", "ebx, ebx"), ("ret", "")]}), 0x200,
                       [0x200]),
        {"edx": (0x200, "test edx, edx", False), "eax": (0x201, "call eax", False)})
    chk("走不出本體 -> None", reg_first_uses(_G({}), 0x200, [0x200]), None)
    fr = {"addr": "0x200", "name": "r", "summary": "(p, q, cnt, m, extra):…"}
    okr = {"addr": "0x200", "name": "r", "param": 1, "pname": "p", "note": "讀到了", "date": "2026-10-13",
           "basis": [{"kind": "reg", "at": "0x202", "insn": "mov cx, word ptr [eax + 8]"}]}

    def cr(conv: str | None = "reg", regs=ru, **kw) -> str | None:
        return check_entry({**okr, **kw}, fr, None, set(), set(), regs, conv)

    chk("reg:成立(不需要堆疊引用)", cr(), None)
    chk("reg:不是暫存器傳參的函式", (cr(conv="stack"), cr(conv=None)), ("basis reg:這個函式不是暫存器傳參",) * 2)
    chk("reg:第 2 個(edx)指到別的暫存器的指令", "第一個提到 edx 的指令在 0x204" in (cr(param=2, pname="q") or ""), True)
    chk("reg:第 3 個(ebx)第一次提到就是覆寫", "只是覆寫 ebx" in (cr(param=3, pname="cnt", basis=[
        {"kind": "reg", "at": "0x203", "insn": "mov ebx, 1"}]) or ""), True)
    chk("reg:指令文字不同", "的指令是" in (cr(basis=[{"kind": "reg", "at": "0x202", "insn": "mov cx, 1"}]) or ""), True)
    chk("reg:第 4 個(ecx)還在暫存器範圍內,錯在它是覆寫", "只是覆寫 ecx" in (cr(param=4, pname="m", basis=[
        {"kind": "reg", "at": "0x201", "insn": "sub ecx, ecx"}]) or ""), True)
    chk("reg:第 5 個不在暫存器", "不在暫存器" in (cr(param=5, pname="extra") or ""), True)
    chk("reg:本體沒有提到那個暫存器", "沒有提到 eax" in (cr(regs={}) or ""), True)
    chk("reg:走不出本體", "走不出" in (cr(regs=None) or ""), True)
    chk("reg:at 格式錯", "at 格式錯" in (cr(basis=[{"kind": "reg", "insn": "x"}]) or ""), True)

    print("[3c] push 不算讀;via / raw / indirect(續一百一十九)")
    chk("push r 之後才讀:第一個提到的是後面那一條",
        reg_first_uses(_G({0x200: [("push", "eax"), ("mov", "si, word ptr [eax + 8]"), ("pop", "ecx"), ("ret", "")]}),
                       0x200, [0x200]).get("eax"), (0x201, "mov si, word ptr [eax + 8]", False))
    chk("push r 之後被覆寫:是覆寫(存起來的那一份 reg 不追)",
        reg_first_uses(_G({0x200: [("push", "ebx"), ("mov", "ebx, 1"), ("pop", "ebx"), ("ret", "")]}), 0x200,
                       [0x200]).get("ebx"), (0x201, "mov ebx, 1", True))
    gp = _G({0x200: [("push", "ebx"), ("push", "edx"), ("push", "eax"), ("call", "dword ptr [0x283c]"), ("add", "esp, 8"),
                     ("pop", "ebx"), ("ret", "")]})
    chk("push r 是第一個 call 的引數(add esp, 8 = 2 個):eax / edx 算讀,更早的 push ebx 只是存起來",
        reg_first_uses(gp, 0x200, [0x200]), {"edx": (0x201, "push edx", False), "eax": (0x202, "push eax", False)})
    chk("push r 是引數、之後才被覆寫:第一個提到的仍是那個 push(讀)",
        reg_first_uses(_G({0x200: [("push", "eax"), ("mov", "eax, 1"), ("call", "ecx"), ("add", "esp, 4"), ("ret", "")]}),
                       0x200, [0x200]).get("eax"), (0x200, "push eax", False))
    chk("call 後面沒有 add esp:push 不當引數",
        reg_first_uses(_G({0x200: [("push", "eax"), ("call", "ecx"), ("pop", "eax"), ("ret", "")]}), 0x200, [0x200]),
        {"ecx": (0x201, "call ecx", False)})
    gv = _G({0x400: [("push", "esi"), ("mov", "ecx, edx"), ("call", "0x500"), ("pop", "esi"), ("ret", "")],
             0x500: [("push", "ebx"), ("push", "eax"), ("mov", "ebx, 1"), ("test", "eax, eax"),
                     ("dec", "dword ptr [esp + 4]"), ("add", "esp, 8"), ("ret", "")]})
    ents = [0x400, 0x500]
    chk("第一個 call:直接呼叫的目標 / 間接 / 沒有 call",
        (first_call(gv, 0x400, ents), first_call(gp, 0x200, [0x200]), first_call(gv, 0x500, ents)),
        ((0x402, 0x500), (0x203, None), None))
    sv = saved_copy_refs(gv, 0x500, ents)
    chk("存起來的那一份:push ebx 在位移 4,[esp + 4](位移 8 時)讀的就是它;eax 那一份沒有人讀",
        sv, {"ebx": [(0x504, "dec dword ptr [esp + 4]")], "eax": []})
    chk("存起來的那一份:先被別的指令提到的暫存器不算(push 存的已不是入口值);第一個 call 之後的 push 也不算",
        (saved_copy_refs(_G({0x500: [("mov", "ebx, 1"), ("push", "ebx"), ("pop", "ebx"), ("ret", "")]}), 0x500, [0x500]),
         saved_copy_refs(_G({0x500: [("call", "ecx"), ("push", "ebx"), ("pop", "ebx"), ("ret", "")]}), 0x500, [0x500])),
        ({}, {}))
    fv = {"addr": "0x400", "name": "v", "summary": "(p, tab, n):…"}
    okv = {"addr": "0x400", "name": "v", "param": 3, "pname": "n", "note": "讀到了", "date": "2026-10-13",
           "basis": [{"kind": "via", "via": "0x402", "at": "0x504", "insn": "dec dword ptr [esp + 4]"}]}
    mv = Extra(call=first_call(gv, 0x400, ents), callee_regs=reg_first_uses(gv, 0x500, ents), callee_saved=sv)
    rv = reg_first_uses(gv, 0x400, ents)

    def cv(conv: str | None = "reg", regs=rv, more: Extra | None = mv, **kw) -> str | None:
        return check_entry({**okv, **kw}, fv, None, set(), set(), regs, conv, more)

    chk("via:被呼叫端讀存起來的那一份 -> 成立", cv(), None)
    chk("via:被呼叫端直接讀暫存器(第 1 個 eax,test eax, eax)-> 成立",
        cv(param=1, pname="p", basis=[{"kind": "via", "via": "0x402", "at": "0x503", "insn": "test eax, eax"}]), None)
    chk("via:指到被呼叫端覆寫它的指令", "不是被呼叫端 0x500 讀 ebx" in (cv(basis=[
        {"kind": "via", "via": "0x402", "at": "0x502", "insn": "mov ebx, 1"}]) or ""), True)
    chk("via:eax 存起來的那一份沒有人讀,指到讀 ebx 那一份的指令 -> 不成立", "讀 eax 入口值" in (cv(
        param=1, pname="p", basis=[{"kind": "via", "via": "0x402", "at": "0x504", "insn": "dec dword ptr [esp + 4]"}]) or ""),
        True)
    chk("via:指令文字不同", "讀 ebx 入口值" in (cv(basis=[
        {"kind": "via", "via": "0x402", "at": "0x504", "insn": "dec dword ptr [esp]"}]) or ""), True)
    chk("via:本體自己提到了那個暫存器(第 2 個 edx)", "請用 reg" in (cv(param=2, pname="tab") or ""), True)
    chk("via:via 不是第一個 call / 沒寫 / 第一個 call 是間接 / 沒有 call",
        ["不是本體依位址順序的第一個 call" in (e or "") for e in (
            cv(basis=[{**okv["basis"][0], "via": "0x401"}]), cv(basis=[{k: v for k, v in okv["basis"][0].items() if k != "via"}]),
            cv(more=Extra(call=(0x402, None), callee_saved=sv)), cv(more=None))], [True] * 4)
    chk("via:不是暫存器傳參 / 走不出本體", ("不是暫存器傳參" in (cv(conv="stack") or ""), "請用 reg" in (cv(regs=None) or "")),
        (True, True))

    gw = _G({0x600: [("push", "ebp"), ("mov", "ebp, esp"), ("mov", "ecx, dword ptr [esp + 4]"), ("cmp", "ebp, 0"),
                     ("mov", "eax, dword ptr [ebp + 8]"), ("sub", "esp, 8"), ("mov", "edx, dword ptr [esp + 0x14]"),
                     ("mov", "ebp, dword ptr [ebp + 0x10]"), ("mov", "ebx, dword ptr [ebp + 0x10]"), ("mov", "esp, edx"),
                     ("mov", "eax, dword ptr [esp + 0x10]"), ("jmp", "ecx")]})
    rw = raw_refs(gw, 0x600)
    chk("直線段:框架與 sub esp 之後的位移都換算;[esp + 4](回傳位址)不算;ebp 被改寫後的 [ebp + 0x10] 不算;改寫 ESP 之後不看",
        rw, {1: [(0x604, "mov eax, dword ptr [ebp + 8]")], 2: [(0x606, "mov edx, dword ptr [esp + 0x14]")],
             3: [(0x607, "mov ebp, dword ptr [ebp + 0x10]")]})
    chk("直線段:遇到 jmp / pushal 就停;pop ebp 之後 ebp 不再是框架",
        (raw_refs(_G({0x600: [("jmp", "0x700"), ("mov", "eax, dword ptr [esp + 4]")]}), 0x600),
         raw_refs(_G({0x600: [("pushal", ""), ("mov", "eax, dword ptr [esp + 0x24]")]}), 0x600),
         raw_refs(_G({0x600: [("push", "ebp"), ("mov", "ebp, esp"), ("pop", "ebp"), ("mov", "eax, dword ptr [ebp + 8]")]}),
                  0x600)), ({}, {}, {}))
    chk("直線段:add esp 往回算", raw_refs(_G({0x600: [("sub", "esp, 0x10"), ("add", "esp, 8"),
                                                 ("mov", "eax, dword ptr [esp + 0xc]"), ("jmp", "eax")]}), 0x600),
        {1: [(0x602, "mov eax, dword ptr [esp + 0xc]")]})
    chk("這個假本體走不出來(以間接 jmp 結束)", body_refs(gw, 0x600, [0x600]), None)
    fw = {"addr": "0x600", "name": "w", "summary": "(a, b, c):…"}
    okw = {"addr": "0x600", "name": "w", "param": 2, "pname": "b", "note": "讀到了", "date": "2026-10-13",
           "basis": [{"kind": "raw", "at": "0x606", "insn": "mov edx, dword ptr [esp + 0x14]"}]}

    def cw(refs_=None, more: Extra | None = Extra(raw=rw), **kw) -> str | None:
        return check_entry({**okw, **kw}, fw, refs_, set(), set(), None, None, more)

    chk("raw:成立", cw(), None)
    chk("raw:走得出本體的函式不收", cw(refs_={}), "basis raw:這個函式走得出本體,請用 body")
    chk("raw:指到引用別的參數的指令 / 指令文字不同 / 直線段以外的位址 / 位址錯但文字對 / 沒有 Extra",
        ["不是入口直線段裡引用第 2 個參數" in (e or "") for e in (
            cw(basis=[{"kind": "raw", "at": "0x604", "insn": "mov eax, dword ptr [ebp + 8]"}]),
            cw(basis=[{"kind": "raw", "at": "0x606", "insn": "mov edx, dword ptr [esp + 0x10]"}]),
            cw(basis=[{"kind": "raw", "at": "0x60a", "insn": "mov eax, dword ptr [esp + 0x10]"}]),
            cw(basis=[{"kind": "raw", "at": "0x604", "insn": "mov edx, dword ptr [esp + 0x14]"}]), cw(more=None))], [True] * 5)

    gi = _G({0x800: [("push", "edi"), ("push", "5"), ("mov", "eax, edx"), ("push", "esi"), ("push", "edx"),
                     ("call", "dword ptr [eax + 0x1a0]"), ("add", "esp, 0xc"), ("pop", "edi"), ("ret", "")],
             0x900: [("push", "eax"), ("call", "0x800"), ("add", "esp, 4"), ("sub", "esp, 4"), ("add", "esp, 4"),
                     ("call", "ebx"), ("ret", "")]})
    si = indirect_site(gi, 0x800, [0x800, 0x900], 0x805)
    chk("間接呼叫點:3 個引數,第 j 個的 push 依位移對(中間夾 mov 沒關係;更早的 push edi 不是引數)",
        si, ("call dword ptr [eax + 0x1a0]", 3, [(0x804, "push edx"), (0x803, "push esi"), (0x801, "push 5")]))
    chk("間接呼叫點:直接 call / 後面沒有 add esp / 不在本體 / 不是 call -> None",
        [indirect_site(gi, o, [0x800, 0x900], a) for o, a in ((0x900, 0x901), (0x900, 0x905), (0x800, 0x999), (0x900, 0x903))],
        [None] * 4)
    fi = {"addr": "0xa00", "name": "cb", "summary": "(drv, seq, st):…"}
    oki = {"addr": "0xa00", "name": "cb", "param": 2, "pname": "seq", "note": "讀到了", "date": "2026-10-13",
           "basis": [{"kind": "indirect", "store": "0x950", "at": "0x805", "insn": "call dword ptr [eax + 0x1a0]",
                      "push_at": "0x803", "push_insn": "push esi"}]}
    ri = {1: [(0xa01, "mov eax, dword ptr [esp + 4]")], 3: [(0xa02, "mov edx, dword ptr [esp + 0xc]")]}
    mi = Extra(ptr_refs=frozenset({0x950}), sites={0x805: si})

    def ci(fn_=fi, refs_=ri, more: Extra | None = mi, **kw) -> str | None:
        return check_entry({**oki, **kw}, fn_, refs_, set(), set(), None, None, more)

    def bi(**kw) -> list[dict]:
        return [{**oki["basis"][0], **kw}]

    chk("indirect:成立", ci(), None)
    chk("indirect:本體有引用的參數不收(第 1 個)/ 走不出本體",
        ["請用 body" in (e or "") for e in (ci(param=1, pname="drv"), ci(refs_=None))], [True, True])
    chk("indirect:store 不是指到它的 fixup / 沒寫 / 沒有 Extra",
        ["store 不是 fixup" in (e or "") for e in (ci(basis=bi(store="0x951")), ci(basis=[
            {k: v for k, v in oki["basis"][0].items() if k != "store"}]), ci(more=None))], [True] * 3)
    chk("indirect:at 不是間接呼叫點", "不是後面緊跟 add esp 的間接 call" in (ci(basis=bi(at="0x804")) or ""), True)
    chk("indirect:call 的文字不同 / 引數個數與摘要不同",
        ["推 3 個引數" in (e or "") for e in (ci(basis=bi(insn="call dword ptr [eax + 0x1a4]")),
                                          ci(fn_={**fi, "summary": "(drv, seq, st, extra):…"}))], [True, True])
    chk("indirect:最後一個參數是 double 時多算一格(4 個引數的呼叫點對 3 個參數)",
        ci(fn_={**fi, "summary": "(drv, seq, double):…"},
           more=Extra(ptr_refs=frozenset({0x950}), sites={0x805: (si[0], 4, si[2] + [(0x800, "push edi")])})), None)
    chk("indirect:push 指到別的引數 / push 的文字不同",
        ["與登錄不同" in (e or "") for e in (ci(basis=bi(push_at="0x804")), ci(basis=bi(push_insn="push edx")))], [True, True])

    print("[4] 三個數字")
    chk("機器比過 / 只有人工 / 都沒有", classify([(1, 1), (1, 2), (2, 1), (3, 1)], {(1, 1), (2, 1)}, {(2, 1), (1, 2)}),
        (2, 1, [(3, 1)]))

    print("[5] 真實檔")
    ctx = load_ctx()
    raw = json.loads(READS_JSON.read_text(encoding="utf-8"))
    reads, errs = load_reads(raw, ctx)
    chk("登錄零錯誤", errs, [])
    chk("登錄不是空的(≥ 30 筆)", len(reads) >= 30, True)
    named, machine, parts, edged = coverage(ctx, reads)
    n_m, n_r, rest = classify(named, machine, set(reads))
    print(f"    (具名參數 {len(named)}:機器比過 {n_m} {parts}、只有人工讀過 {n_r}、都沒有 {len(rest)};名稱邊 {len(edged)})")
    chk("名稱沿呼叫邊比過 ≥ 350,而且沒有併進機器比過(有參數只有名稱邊)",
        (len(edged) >= 350, edged <= set(named), bool(edged - machine)), (True, True, True))
    chk("三個數字加起來 = 全部", n_m + n_r + len(rest), len(named))
    chk("機器比過 ≥ 600(run() 的三個篩選都有接上)", (n_m >= 600, all(v > 0 for v in parts.values())), (True, True))
    d = dossier(ctx, 0x365AB)
    chk("資料卡:dpmi_dos_free 只有第 3 格被本體引用(0x365b5),三格都有實機值",
        ([r["slot"] for r in d["slots"] if r["refs"]], d["slots"][2]["refs"][:1], all(r["live"] for r in d["slots"])),
        ([3], [(0x365B5, "mov eax, dword ptr [esp + 0x44]")], True))
    d2 = dossier(ctx, 0x22AF6)
    chk("資料卡:effect_cure_status_flag 第 2 格原樣轉交給 play_map_effect_animation 的第 2 個(動畫號)",
        ("play_map_effect_animation", 2, "動畫號") in {f[:3] for f in d2["slots"][1]["forwards"]}, True)
    chk("資料卡:印得出來", any("原樣轉交" in ln for ln in format_dossier(d2)), True)
    chk("真實:emu_fprem 是暫存器傳參,第一個提到 edx 的是 0x4c4d2(讀除數的指數)",
        (SS.call_conv(0x4C4BD, ctx.cleanups, ctx.st.argc), (reg_first_uses(ctx.cg, 0x4C4BD, ctx.st.entries) or {}).get("edx")),
        ("reg", (0x4C4D2, "cmp word ptr [edx + 8], 0", False)))
    chk("真實:登錄裡有 reg 依據的條目(≥ 5 筆),全數成立",
        sum(any(b.get("kind") == "reg" for b in r["basis"]) for r in reads.values()) >= 5, True)
    chk("真實:emu_ld_fma_store 的 push eax 不算讀,第一個讀 eax 的是 0x4ce69;raise_via_hook 的 push eax 是 call 的引數",
        ((reg_first_uses(ctx.cg, 0x4CE64, ctx.st.entries) or {}).get("eax"),
         (reg_first_uses(ctx.cg, 0x4D726, ctx.st.entries) or {}).get("eax")),
        ((0x4CE69, "mov si, word ptr [eax + 8]", False), (0x4D726, "push eax", False)))
    chk("真實:emu_ld_mul_add 入口存起來的 ebx 只有 0x4ceca 讀(每輪減 1)",
        (saved_copy_refs(ctx.cg, 0x4CE84, ctx.st.entries) or {}).get("ebx"), [(0x4CECA, "dec dword ptr [ebp + 0xc]")])
    chk("真實:stack_switch_and_jump 走不出本體,入口直線段引用 3 個參數各 1 處",
        (body_refs(ctx.cg, 0x3F0F7, ctx.st.entries), {k: [a for a, _ in v] for k, v in raw_refs(ctx.cg, 0x3F0F7).items()}),
        (None, {1: [0x3F0FE], 2: [0x3F101], 3: [0x3F104]}))
    chk("真實:ail_xmidi_event 0x42d98 經 [+0x1a0] 呼叫 event 回呼,推 5 個,第 2 個是 0x42d94 push esi",
        (lambda t: t and (t[0], t[1], t[2][1]))(indirect_site(ctx.cg, 0x42980, ctx.st.entries, 0x42D98)),
        ("call dword ptr [eax + 0x1a0]", 5, (0x42D94, "push esi")))
    d3 = dossier(ctx, 0x3F0F7)
    chk("真實:走不出本體的函式,資料卡改印入口直線段的引用", (d3["walkable"], [bool(r["refs"]) for r in d3["slots"]]),
        (False, [True] * 3))
    kinds = [b.get("kind") for r in reads.values() for b in r["basis"]]
    chk("真實:登錄裡 via / raw / indirect 三種依據都有條目,全數成立",
        [kinds.count(k) >= 1 for k in ("via", "raw", "indirect")], [True] * 3)
    viar = next(r for r in raw["reads"] if r["basis"][0].get("kind") == "via")
    chk("真實:via 改指被呼叫端覆寫 ebx 的那一條(0x4cea5)-> 不成立",
        ["讀 ebx 入口值" in e for e in load_reads({"reads": [{**viar, "basis": [
            {**viar["basis"][0], "at": "0x4cea5", "insn": "mov ebx, dword ptr [ebp]"}]}]}, ctx)[1]], [True])
    indr = next(r for r in raw["reads"] if r["basis"][0].get("kind") == "indirect")
    chk("真實:indirect 的 push 改指第 1 個引數(0x42d97 push edx)-> 不成立",
        ["與登錄不同" in e for e in load_reads({"reads": [{**indr, "basis": [
            {**indr["basis"][0], "push_at": "0x42d97", "push_insn": "push edx"}]}]}, ctx)[1]], [True])
    first = raw["reads"][0]                           # 取原始條目:登錄全數不成立時也不會因為空清單當機
    chk("真實:把一筆登錄的 pname 改掉 -> 過期", ["過期" in e for e in load_reads({"reads": [{**first, "pname": "舊名"}]}, ctx)[1]],
        [True])
    chk("真實:同一個參數登兩次 -> 重複", ["重複" in e for e in load_reads({"reads": [first, first]}, ctx)[1]], [True])

    print()
    print("--selftest OK" if not fails else f"--selftest FAILED: {fails}")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="參數資料卡與人工閱讀登錄")
    ap.add_argument("targets", nargs="*", help="函式名稱或 0x 位址")
    ap.add_argument("--dis", type=int, default=0, metavar="N", help="另印本體前 N 個指令(含 ESP 位移)")
    ap.add_argument("--coverage", action="store_true", help="檢查登錄,印機器比過 / 只有人工讀過 / 都沒有")
    ap.add_argument("--worklist", action="store_true", help="列出沒有任何依據的參數")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    ctx = load_ctx()
    if a.coverage or a.worklist:
        reads, errs = load_reads(json.loads(READS_JSON.read_text(encoding="utf-8")), ctx)
        named, machine, parts, edged = coverage(ctx, reads)
        n_m, n_r, rest = classify(named, machine, set(reads))
        print(f"具名參數 {len(named)}:機器比過 {n_m}(" + "、".join(f"{k} {v}" for k, v in parts.items())
              + f";可重複)、只有人工讀過 {n_r}、都沒有 {len(rest)}")
        print(f"登錄 {len(reads)} 筆(其中 {sum(k in machine for k in reads)} 筆的參數機器也比過)")
        print(f"名稱沿呼叫邊比過 {len(edged)}(一致性檢查,不計入機器比過;「都沒有」的 {len(rest)} 個裡有 "
              f"{sum(p in edged for p in rest)} 個至少有這一項)")
        if a.worklist:
            for fa, k in rest:
                x = ctx.by[fa]
                pn = dict(named_params(x["summary"]))[k]
                print(f"  {fa:#x} {x['name']} 第 {k} 個 {pn}({SS.name_class(pn)};{'有' if f'{fa:#x}' in ctx.prof else '無'}實機紀錄"
                      + (";有名稱邊" if (fa, k) in edged else "") + ")")
        for e in errs:
            print(f"FAIL 登錄:{e}")
        print("結果:" + ("FAIL" if errs else "PASS"))
        return 1 if errs else 0
    if not a.targets:
        ap.error("給函式名稱 / 位址,或 --coverage / --worklist / --selftest")
    rev = {x["name"]: int(x["addr"], 16) for x in ctx.names}
    for t in a.targets:
        fa = rev[t] if t in rev else int(t, 16)
        for ln in format_dossier(dossier(ctx, fa)):
            print(ln)
        if a.dis:
            res = SS.cfg_states(ctx.cg, fa, ctx.st.entries, {}, lambda i, td, st: st, frozenset())
            for at in sorted(res[2] if res else {})[:a.dis]:
                i = res[2][at]
                print(f"      {at:#x} [{res[1][at][0]:>3}] {i.mnemonic} {i.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
