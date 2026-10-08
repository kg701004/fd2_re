#!/usr/bin/env python3
"""以原版實機的「函式呼叫紀錄」逐函式反驗名稱與摘要(doc98 續一百零七)。

逐一下斷點(入口讀參數、返回處讀回傳值)一次只看得到一個函式;`tools/dosbox/fd2_calllog_patch.py` 修補的
dosbox-x 在每個入口都做同一件事,一次執行寫出 `CALLLOG.TXT`(格式見該檔)。本工具讀它,做三層檢查:

1. **紀錄本身可信**:每筆 E 的 16 個碼位元組要等於 EXE obj1 在 `eip - 0x19c000` 的位元組(fixup 位置遮掉,
   那裡是載入後的重定位值)。對不上的記錄(位移錯、別的程式用同一個 selector、EXE 換版)不採用,並記 FAIL。
2. **呼叫結構**(所有被執行的入口都適用):返回位址前面的指令要是「直接 call 這個入口」、「call 跳到它的
   thunk」或「間接 call」。直接 / thunk 呼叫的動態邊必須在 `function_inventory.json` 的靜態 callees 裡;
   間接 call 依入口當下的暫存器反算 call 的目標(暫存器或記憶體 slot),slot 有 fixup 的,fixup 目標(可經
   jmp 跳板)必須就是這個入口。這些都是名稱證據所依據的呼叫圖,在實機上逐筆對。
3. **名稱 / 摘要的語意宣稱**:
   - libc 名稱(`memcpy`、`memset`、`strcpy`、`strcat`、`strlen`、`rand`):以參數與回傳值直接驗算
     (strlen 以 eax 指向的位元組找 NUL;dump 長度內沒有 NUL 時只要求回傳值 ≥ dump 長度)。
   - 摘要寫「回傳緩衝區 / 回傳目的」:回傳值必須等於第一個參數(eax,或 cdecl 的 [esp+4];兩者都記)。
   宣稱與實機不符 = FAIL(名稱、摘要或這裡的規則有一邊錯,要人看)。

沒被執行到的入口不算通過也不算失敗,另列「未執行」;入口數、執行數、有宣稱數、通過 / 失敗數分開報,
不把「沒有宣稱」算成通過。

用法:
    python tools/verify_names_by_calllog.py --write-entries OUT      # 寫 harness 用的入口檔(執行期 EIP)
    python tools/verify_names_by_calllog.py CALLLOG.TXT [...]         # 檢查(可多份)
    python tools/verify_names_by_calllog.py CALLLOG.TXT --json OUT    # 另寫逐函式剖面(參數 / 回傳 / 呼叫端)
    python tools/verify_names_by_calllog.py --selftest
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DELTA = 0x19C000          # obj1 / obj2 的執行期位移(doc48 / doc58;紀錄的碼位元組比對會再驗一次)
INVENTORY_JSON = ROOT / "docs" / "data" / "function_inventory.json"
REG32 = ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")   # ModRM 編號順序
PTR_ORDER = ("eax", "edx", "ebx", "ecx", "esi", "edi", "s1", "s2", "s3", "s4")  # E 記錄 m= 的順序


# ---------------------------------------------------------------- 解析

@dataclass
class Entry:
    seq: int
    eip: int                       # native(已減 DELTA)
    ret: int                       # 執行期返回位址
    ret_bad: bool
    esp: int
    regs: dict[str, int]
    stack: list[int]               # [esp+4] .. [esp+0x20]
    code: bytes
    mem: list[bytes | None]        # 依 PTR_ORDER;None = 該處有讀不到的位元組
    mem_prefix: list[bytes]        # 讀不到之前的位元組


@dataclass
class CallLog:
    header: dict[str, str] = field(default_factory=dict)
    entries: dict[int, Entry] = field(default_factory=dict)
    returns: dict[int, tuple[int, int]] = field(default_factory=dict)   # seq -> (eax, edx)
    abandoned: dict[int, int] = field(default_factory=dict)             # seq -> 離開時 eip(native)
    counts: dict[int, int] = field(default_factory=dict)                # native 入口 -> 總呼叫次數
    ended: bool = False                                                 # 有 "T exit"
    errors: list[str] = field(default_factory=list)


def _hexbytes(tok: str) -> tuple[bytes | None, bytes]:
    """'4142??43' -> (None, b'AB');全可讀 -> (bytes, bytes)。"""
    pre = bytearray()
    for k in range(0, len(tok), 2):
        h = tok[k:k + 2]
        if h == "??":
            return None, bytes(pre)
        pre.append(int(h, 16))
    return bytes(pre), bytes(pre)


def parse_calllog(text: str, delta: int = DELTA) -> CallLog:
    """CALLLOG.TXT 內容 -> CallLog;格式不對的行記進 errors(讀不懂不等於沒有)。"""
    log = CallLog()
    for n, line in enumerate(text.splitlines(), 1):
        t = line.split()
        if not t:
            continue
        try:
            kind = t[0]
            if kind == "H":
                log.header = dict(x.split("=", 1) for x in t[3:] if "=" in x)
                log.header["version"] = t[2]
            elif kind == "E":
                if len(t) != 16 or not (t[13].startswith("s=") and t[14].startswith("c=") and t[15].startswith("m=")):
                    raise ValueError("E record shape")
                vals = [int(x, 16) for x in t[6:13]]
                regs = dict(zip(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"), vals))
                stack = [int(x, 16) for x in t[13][2:].split(",")]
                if len(stack) != 8:
                    raise ValueError("stack dwords")
                code, _ = _hexbytes(t[14][2:])
                if code is None or len(code) != 16:
                    raise ValueError("code bytes")
                mems = t[15][2:].split(",")
                if len(mems) != len(PTR_ORDER):
                    raise ValueError("memory dumps")
                parsed = [_hexbytes(m) for m in mems]
                seq = int(t[1])
                log.entries[seq] = Entry(seq, int(t[2], 16) - delta, int(t[3].rstrip("?"), 16), t[3].endswith("?"),
                                         int(t[4], 16), regs, stack, code, [p[0] for p in parsed],
                                         [p[1] for p in parsed])
            elif kind == "R":
                if len(t) != 6:
                    raise ValueError("R record shape")
                log.returns[int(t[1])] = (int(t[3], 16), int(t[4], 16))
            elif kind == "A":
                if len(t) != 5:
                    raise ValueError("A record shape")
                log.abandoned[int(t[1])] = int(t[3], 16) - delta
            elif kind == "C":
                log.counts[int(t[1], 16) - delta] = int(t[2])
            elif kind == "T":
                log.ended = log.ended or t[1] == "exit"
            elif kind == "X":
                log.errors.append(f"line {n}: frame stack overflow ({line.strip()})")
            else:
                raise ValueError(f"unknown record {kind!r}")
        except (ValueError, IndexError) as exc:
            log.errors.append(f"line {n}: {exc}: {line[:80]!r}")
    return log


# ---------------------------------------------------------------- 靜態資料

@dataclass
class Static:
    code: bytes
    base: int
    hi: int
    fixups: dict[int, int]
    masked: set[int]
    entries: list[int]
    thunk_of: dict[int, int]          # 目標 -> thunk 入口
    callees: dict[int, set[int]]
    names: dict[int, str]
    summaries: dict[int, str]
    argc: dict[int, int | None] = field(default_factory=dict)   # 本體從堆疊讀到第幾個參數(inventory)


def load_static() -> Static:
    """讀參考版 EXE、fixup、函式清單、名稱與摘要。"""
    import disasm_le as D
    import function_inventory as FI
    import verify_address_claim_coverage as CC
    data, meta, code, base, hi = CC.load_image()
    fixups = D.build_fixups(data, meta)
    masked = {s + k for s in fixups if base <= s < hi for k in range(4)}
    inv = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))["entries"]
    ents = sorted(int(e["addr"], 16) for e in inv)
    callees = {int(e["addr"], 16): {int(x, 16) for x in e["callees"]} for e in inv}
    names = {a: v["name"] for a, v in FI.load_names().items() if v["name"]}
    summaries = {int(e["addr"], 16): e["summary"] for e in FI.load_function_names()}
    argc = {int(e["addr"], 16): e["argc"] for e in inv}
    return Static(code, base, hi, fixups, masked, ents, FI.thunk_targets(set(ents), code, base, hi),
                  callees, names, summaries, argc)


def owner(st: Static, a: int) -> int | None:
    i = bisect.bisect_right(st.entries, a) - 1
    return st.entries[i] if i >= 0 else None


def code_matches(st: Static, e: Entry) -> bool:
    """紀錄的 16 個碼位元組 == EXE(fixup 位置不比)。"""
    a = e.eip
    if not (st.base <= a and a + 16 <= st.hi):
        return False
    return all(a + k in st.masked or st.code[a + k - st.base] == e.code[k] for k in range(16))


def jmp_chain(st: Static, t: int, limit: int = 3) -> list[int]:
    """t 與沿 `jmp rel32` / `jmp rel8` 跳板走過的每一站(最多 limit 步)。"""
    chain = [t]
    for _ in range(limit):
        nxt = follow_jmps(st, chain[-1], 1)
        if nxt == chain[-1]:
            break
        chain.append(nxt)
    return chain


def follow_jmps(st: Static, t: int, limit: int = 3) -> int:
    """從 t 沿 `jmp rel32` / `jmp rel8` 跳板走到底(最多 limit 步)。"""
    for _ in range(limit):
        if not (st.base <= t < st.hi - 5):
            break
        op = st.code[t - st.base]
        if op == 0xE9:
            t = (t + 5 + int.from_bytes(st.code[t + 1 - st.base:t + 5 - st.base], "little", signed=True)) & 0xFFFFFFFF
        elif op == 0xEB:
            t = (t + 2 + int.from_bytes(st.code[t + 1 - st.base:t + 2 - st.base], "little", signed=True)) & 0xFFFFFFFF
        else:
            break
    return t


def decode_ff2(b: bytes) -> dict | None:
    """`FF /2`(call r/m32)解碼;b 須恰好是整條指令。回 {reg|base,index,scale,disp} 或 None。"""
    if len(b) < 2 or b[0] != 0xFF or (b[1] >> 3) & 7 != 2:
        return None
    mod, rm = b[1] >> 6, b[1] & 7
    if mod == 3:
        return {"reg": REG32[rm]} if len(b) == 2 else None
    pos, base, index, scale = 2, REG32[rm], None, 1
    if rm == 4:
        if len(b) < 3:
            return None
        sib = b[2]
        pos = 3
        scale, idx, bs = 1 << (sib >> 6), (sib >> 3) & 7, sib & 7
        index = None if idx == 4 else REG32[idx]
        base = REG32[bs]
        if bs == 5 and mod == 0:
            base = None
            disp_len = 4
        else:
            disp_len = {0: 0, 1: 1, 2: 4}[mod]
    elif rm == 5 and mod == 0:
        base, disp_len = None, 4
    else:
        disp_len = {0: 0, 1: 1, 2: 4}[mod]
    if len(b) != pos + disp_len:
        return None
    disp = int.from_bytes(b[pos:pos + disp_len], "little", signed=True) if disp_len else 0
    return {"base": base, "index": index, "scale": scale, "disp": disp}


def classify_site(st: Static, e: Entry, delta: int = DELTA) -> tuple[str, int | None, dict | None]:
    """返回位址前的呼叫指令 -> (direct | thunk | indirect | ambiguous | other | outside, call 位址, 解碼)。"""
    r = e.ret - delta
    if e.ret_bad or not (st.base + 8 <= r < st.hi):
        return "outside", None, None
    if st.code[r - 5 - st.base] == 0xE8:
        tgt = (r + int.from_bytes(st.code[r - 4 - st.base:r - st.base], "little", signed=True)) & 0xFFFFFFFF
        if tgt == e.eip:
            return "direct", r - 5, None
        if st.thunk_of.get(e.eip) == tgt or e.eip in jmp_chain(st, tgt)[1:]:
            return "thunk", r - 5, None
    cands = [(r - n, d) for n in range(2, 8) if (d := decode_ff2(st.code[r - n - st.base:r - st.base])) is not None]
    if len(cands) == 1:
        return "indirect", cands[0][0], cands[0][1]
    if len(cands) > 1:
        return "ambiguous", None, None
    return "other", None, None


def indirect_target(st: Static, e: Entry, d: dict, delta: int = DELTA) -> tuple[str, int | None]:
    """間接 call 的目標:('reg', 執行期值) / ('slot', fixup 目標 native) / ('runtime', slot native)。"""
    regs = dict(e.regs, esp=e.esp + 4)    # call 當下的 esp = 入口 esp + 4
    if "reg" in d:
        return "reg", regs[d["reg"]]
    addr = d["disp"]
    if d["base"]:
        addr += regs[d["base"]]
    if d["index"]:
        addr += regs[d["index"]] * d["scale"]
    slot = (addr & 0xFFFFFFFF) - delta
    if slot in st.fixups:
        return "slot", st.fixups[slot]
    return "runtime", slot


# ---------------------------------------------------------------- 語意宣稱

def _cstr_len(full: bytes | None, prefix: bytes) -> tuple[int | None, int]:
    """(NUL 位置或 None, 可讀長度)。"""
    buf = full if full is not None else prefix
    i = buf.find(b"\0")
    return (i if i >= 0 else None), len(buf)


REG_ARGS = ("eax", "edx", "ebx", "ecx")      # Watcom 暫存器傳參順序
MEM_INDEX = {k: i for i, k in enumerate(PTR_ORDER)}


def param_slot(argc: int | None, k: int) -> str | None:
    """第 k 個參數(1 起)在 E 記錄裡的位置。

    `argc` 是 inventory 的「本體從堆疊讀到第幾個參數」(derive_native_argcounts.callee_argc):
    argc >= k -> `s<k>`([esp+4k]);argc == 0 -> Watcom 暫存器(eax, edx, ebx, ecx);
    其他(不知道、或 0 < argc < k)-> None,不猜。
    """
    if argc is None or not 1 <= k <= 8:
        return None
    if argc >= k:
        return f"s{k}"
    if argc == 0 and k <= len(REG_ARGS):
        return REG_ARGS[k - 1]
    return None


def param_value(e: Entry, slot: str) -> int:
    return e.stack[int(slot[1:]) - 1] if slot.startswith("s") else e.regs[slot]


def param_mem(e: Entry, slot: str) -> tuple[bytes | None, bytes] | None:
    i = MEM_INDEX.get(slot)
    return None if i is None else (e.mem[i], e.mem_prefix[i])


def _cmp_sign(a: tuple[bytes | None, bytes], b: tuple[bytes | None, bytes]) -> int | None:
    """兩段 dump 的 C 字串比較結果(-1/0/1);在 dump 內分不出來回 None。"""
    x, y = (a[0] if a[0] is not None else a[1]), (b[0] if b[0] is not None else b[1])
    for i in range(min(len(x), len(y))):
        if x[i] != y[i]:
            return -1 if x[i] < y[i] else 1
        if x[i] == 0:
            return 0
    return None


def oracle_check(name: str, e: Entry, ret: tuple[int, int], argc: int | None) -> tuple[bool, str] | None:
    """libc 名稱的語意驗算;不適用(不是這些名稱、參數位置不明、dump 分不出)回 None。回 (成立?, 說明)。"""
    eax = ret[0]
    if name == "rand":
        return 0 <= eax <= 0x7FFF, f"ret {eax:#x}"
    s1 = param_slot(argc, 1)
    if s1 is None:
        return None
    if name in ("memcpy", "memset", "strcpy", "strcat", "memmove"):
        p = param_value(e, s1)
        return eax == p, f"ret {eax:#x} vs 第 1 參數({s1}){p:#x}"
    if name == "strlen":
        full, prefix = param_mem(e, s1) or (None, b"")
        nul, n = _cstr_len(full, prefix)
        if nul is not None:
            return eax == nul, f"ret {eax} vs {s1} 字串的 NUL 在 {nul}"
        if n == 0:
            return None
        return eax >= n, f"ret {eax} vs {s1} 前 {n} 個可讀位元組沒有 NUL"
    if name == "strcmp":
        s2 = param_slot(argc, 2)
        ma, mb = param_mem(e, s1), (param_mem(e, s2) if s2 else None)
        want = _cmp_sign(ma, mb) if ma and mb else None
        if want is None:
            return None
        got = (eax > 0x7FFFFFFF and -1) or (eax and 1) or 0
        return got == want, f"ret {eax:#x}(符號 {got})vs dump 比較 {want}"
    return None


ORACLE_NAMES = frozenset({"rand", "memcpy", "memset", "strcpy", "strcat", "memmove", "strlen", "strcmp"})
PARAMS = re.compile(r"^\s*\(([^()]*)\)")
RET_PARAM = re.compile(r"回傳(緩衝區|目的)")
RET_NULL = re.compile(r"回(傳)? ?NULL")


def summary_claims(summary: str) -> list[tuple[str, int | None, str]]:
    """摘要中能機械檢查的宣稱。目前一種:「回傳緩衝區 / 回傳目的」-> ('ret_param', 第幾個參數, 字)。

    第幾個參數取自摘要開頭的參數列 `(a, b, c)` 裡第一個含該字的;參數列沒有就是 None(宣稱無法定位,另計)。
    """
    m = RET_PARAM.search(summary or "")
    if not m:
        return []
    pm = PARAMS.match(summary)
    params = [p.strip() for p in pm.group(1).split(",")] if pm else []
    k = next((i + 1 for i, p in enumerate(params) if m.group(1) in p), None)
    return [("ret_param", k, params[k - 1] if k else m.group(1))]


def claim_check(claim: tuple[str, int | None, str], e: Entry, ret: tuple[int, int], argc: int | None,
                summary: str) -> tuple[bool, str] | None:
    """宣稱是否成立;不適用(參數位置不明、該參數為 NULL 而摘要說會自行配置)回 None。"""
    kind, k, pname = claim
    if kind != "ret_param":
        raise ValueError(kind)
    slot = param_slot(argc, k) if k else None
    if slot is None:
        return None
    p = param_value(e, slot)
    if ret[0] == p:
        return True, f"ret == 第 {k} 參數 {pname}"
    if ret[0] == 0 and RET_NULL.search(summary):
        return True, "回 NULL(摘要寫的失敗路徑)"
    if p == 0 and "NULL" in pname:
        return None
    return False, f"ret {ret[0]:#x} vs 第 {k} 參數 {pname}({slot}){p:#x}"


# ---------------------------------------------------------------- 主檢查

@dataclass
class Report:
    records: int = 0
    foreign: list[int] = field(default_factory=list)          # 碼位元組對不上的 seq
    kinds: collections.Counter = field(default_factory=collections.Counter)
    edges_absent: set[tuple[int, int]] = field(default_factory=set)
    edges: set[tuple[int, int, str]] = field(default_factory=set)
    indirect: collections.Counter = field(default_factory=collections.Counter)
    indirect_bad: list[tuple] = field(default_factory=list)
    executed: set[int] = field(default_factory=set)
    returned: set[int] = field(default_factory=set)
    checks: dict[int, dict[str, list]] = field(default_factory=dict)   # 入口 -> {規則: [成立數, 失敗例]}
    profiles: dict[int, dict] = field(default_factory=dict)


def _profile_add(p: dict, e: Entry, ret: tuple[int, int] | None, caller: int | None) -> None:
    p["calls_logged"] += 1
    for r in ("eax", "edx", "ebx", "ecx"):
        p["args"][r].add(e.regs[r])
    p["args"]["s1"].add(e.stack[0])
    if ret is not None:
        p["ret"].add(ret[0])
    if caller is not None:
        p["callers"].add(caller)


def check(st: Static, logs: list[CallLog]) -> Report:
    rep = Report()
    for log in logs:
        for seq, e in log.entries.items():
            rep.records += 1
            if not code_matches(st, e):
                rep.foreign.append(seq)
                continue
            rep.executed.add(e.eip)
            ret = log.returns.get(seq)
            if ret is not None:
                rep.returned.add(e.eip)
            kind, at, d = classify_site(st, e)
            rep.kinds[kind] += 1
            caller = owner(st, at) if at is not None else None
            if kind in ("direct", "thunk"):
                rep.edges.add((caller, e.eip, kind))
                cal = st.callees.get(caller, set())
                if e.eip not in cal and st.thunk_of.get(e.eip) not in cal:
                    rep.edges_absent.add((caller, e.eip))
            elif kind == "indirect":
                how, v = indirect_target(st, e, d)
                if how == "runtime":
                    rep.indirect["runtime_slot"] += 1
                else:
                    t = v - DELTA if how == "reg" else v
                    if e.eip in jmp_chain(st, t):
                        rep.indirect[f"{how}_consistent"] += 1
                    else:
                        rep.indirect[f"{how}_inconsistent"] += 1
                        rep.indirect_bad.append((at, how, v, e.eip))
            p = rep.profiles.setdefault(e.eip, {"calls_logged": 0, "args": collections.defaultdict(set),
                                                "ret": set(), "callers": set()})
            _profile_add(p, e, ret, caller)
            if ret is None:
                continue
            name = st.names.get(e.eip, "")
            argc = st.argc.get(e.eip)
            summ = st.summaries.get(e.eip, "")
            rules: list[tuple[str, tuple[bool, str] | None]] = []
            if name in ORACLE_NAMES:
                rules.append((f"oracle:{name}", oracle_check(name, e, ret, argc)))
            for c in summary_claims(summ):
                rules.append((f"summary:{c[0]}({c[2]})", claim_check(c, e, ret, argc, summ)))
            for rule, res in rules:
                slot = rep.checks.setdefault(e.eip, {}).setdefault(rule, {"pass": 0, "fail": 0, "na": 0, "examples": []})
                if res is None:
                    slot["na"] += 1
                elif res[0]:
                    slot["pass"] += 1
                else:
                    slot["fail"] += 1
                    if len(slot["examples"]) < 3:
                        slot["examples"].append(f"seq {seq}: {res[1]}")
    return rep


def summarize(st: Static, logs: list[CallLog], rep: Report) -> tuple[list[str], list[str]]:
    """(報告行, FAIL 行)。"""
    lines, fails = [], []
    errs = sum(len(l.errors) for l in logs)
    lines.append(f"紀錄 {len(logs)} 份:E {rep.records} 筆、解析錯誤 {errs}、以 'T exit' 結束 {sum(l.ended for l in logs)} 份")
    for l in logs:
        for msg in l.errors[:5]:
            fails.append(f"解析:{msg}")
    if rep.foreign:
        fails.append(f"碼位元組與 EXE 不符 {len(rep.foreign)} 筆(位移 / EXE 版本 / 別的程式),例 seq {rep.foreign[:5]}")
    lines.append(f"入口 {len(st.entries)}:被執行 {len(rep.executed)}、有返回紀錄 {len(rep.returned)}、"
                 f"未執行 {len(st.entries) - len(rep.executed)}")
    lines.append("呼叫點:" + "、".join(f"{k} {v}" for k, v in sorted(rep.kinds.items())))
    lines.append(f"動態直接 / thunk 呼叫邊 {len(rep.edges)},不在靜態 callees 的 {len(rep.edges_absent)}")
    for c, t in sorted(rep.edges_absent)[:20]:
        fails.append(f"呼叫圖:{c:#x} -> {t:#x} 實機有、靜態 callees 沒有")
    lines.append("間接呼叫:" + "、".join(f"{k} {v}" for k, v in sorted(rep.indirect.items())))
    for at, how, v, ent in rep.indirect_bad[:20]:
        fails.append(f"間接呼叫:{at:#x} 的 {how} 目標 {v:#x} 不是實際進入的 {ent:#x}")
    verdicts = collections.Counter()
    for a in sorted(rep.checks):
        for rule, v in sorted(rep.checks[a].items()):
            if v["fail"]:
                verdicts["不成立"] += 1
                fails.append(f"語意:{a:#x} {st.names.get(a, '?')} {rule} 不成立 {v['fail']} 次 / 成立 {v['pass']} 次:"
                             f"{v['examples'][0]}")
            elif v["pass"]:
                verdicts["成立"] += 1
            else:
                verdicts["無法判定"] += 1
    lines.append(f"語意宣稱:{len(rep.checks)} 個入口、{sum(verdicts.values())} 條規則:"
                 + "、".join(f"{k} {verdicts[k]}" for k in ("成立", "不成立", "無法判定")))
    return lines, fails


def profiles_doc(st: Static, rep: Report) -> dict:
    """逐函式剖面(JSON 用):呼叫端、參數 / 回傳的相異值數與範圍、宣稱結果。"""
    def rng(vals: set[int]) -> dict:
        v = sorted(vals)
        return {"distinct": len(v), "min": f"{v[0]:#x}", "max": f"{v[-1]:#x}",
                "sample": [f"{x:#x}" for x in v[:6]]} if v else {"distinct": 0}
    out = {}
    for a in sorted(rep.profiles):
        p = rep.profiles[a]
        out[f"{a:#x}"] = {
            "name": st.names.get(a),
            "calls_logged": p["calls_logged"],
            "callers": sorted(f"{c:#x}" for c in p["callers"]),
            "args": {r: rng(v) for r, v in sorted(p["args"].items())},
            "ret": rng(p["ret"]),
            "checks": rep.checks.get(a, {}),
        }
    return out


# ---------------------------------------------------------------- selftest

def _synthetic(st: Static, eip: int, ret_rt: int, regs: dict[str, int] | None = None, code: bytes | None = None,
               mems: dict[str, str] | None = None, seq: int = 1, ret_line: str | None = None,
               stack: list[int] | None = None) -> str:
    """合成一筆 E(碼位元組預設取 EXE)與選用的 R 行;mems = {PTR_ORDER 名: hex}。"""
    r = {"eax": 0, "ebx": 0, "ecx": 0, "edx": 0, "esi": 0, "edi": 0, "ebp": 0}
    r.update(regs or {})
    c = code if code is not None else st.code[eip - st.base:eip - st.base + 16]
    sk = (stack or []) + [0] * (8 - len(stack or []))
    stack_s = ",".join(f"{x:08x}" for x in sk)
    m = ",".join((mems or {}).get(k, "00" * 32) for k in PTR_ORDER)
    line = (f"E {seq} {eip + DELTA:08x} {ret_rt:08x} 001f1000 0178 " + " ".join(f"{r[k]:08x}" for k in
            ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp")) + f" s={stack_s} c={c.hex()} m={m}\n")
    return line + (ret_line or "")


def selftest() -> int:
    st = load_static()
    fails: list[str] = []

    def chk(label: str, got, want) -> None:
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f"  got={got!r} want={want!r}"))
        if not ok:
            fails.append(label)

    names_rev = {v: a for a, v in st.names.items()}
    memcpy, strlen = names_rev["memcpy"], names_rev["strlen"]
    # 找一個真實的 `call memcpy`(E8)呼叫點
    site = next(a for a in range(st.base, st.hi - 5) if st.code[a - st.base] == 0xE8 and
                a + 5 + int.from_bytes(st.code[a + 1 - st.base:a + 5 - st.base], "little", signed=True) == memcpy)
    ret_rt = site + 5 + DELTA

    print("[1] 解析")
    log = parse_calllog("H fd2calllog 1 cs=0170\n" + _synthetic(st, memcpy, ret_rt, {"eax": 0x1000},
                        ret_line="R 1 0 00001000 0 0\n") + "T exit 5\nE 2 truncated\n")
    chk("E 記錄 1 筆", len(log.entries), 1)
    chk("截斷的行記成解析錯誤(不是靜默略過)", len(log.errors), 1)
    chk("T exit 標記", log.ended, True)
    chk("位移換算:eip 為 native", log.entries[1].eip, memcpy)

    print("[2] 碼位元組")
    e = log.entries[1]
    chk("與 EXE 相同 -> 相符", code_matches(st, e), True)
    flip = bytearray(e.code)
    k = next(i for i in range(16) if memcpy + i not in st.masked)
    flip[k] ^= 0xFF
    e2 = parse_calllog(_synthetic(st, memcpy, ret_rt, code=bytes(flip))).entries[1]
    chk("非 fixup 位元組被改 -> 不符", code_matches(st, e2), False)
    fx_ent = next(a for a in st.entries if any(a + i in st.masked for i in range(16)) and a + 16 <= st.hi)
    i = next(i for i in range(16) if fx_ent + i in st.masked)
    cb = bytearray(st.code[fx_ent - st.base:fx_ent - st.base + 16])
    cb[i] ^= 0xFF
    e3 = parse_calllog(_synthetic(st, fx_ent, ret_rt, code=bytes(cb))).entries[1]
    chk("fixup 位元組不同 -> 仍相符(遮罩生效)", code_matches(st, e3), True)

    print("[3] 呼叫點")
    chk("真實 call memcpy -> direct", classify_site(st, e)[0], "direct")
    e_wrong = parse_calllog(_synthetic(st, strlen, ret_rt)).entries[1]
    chk("同一呼叫點但進入別的入口 -> 不是 direct", classify_site(st, e_wrong)[0] != "direct", True)
    chk("FF D0 = call eax", decode_ff2(bytes([0xFF, 0xD0])), {"reg": "eax"})
    chk("FF 14 85 disp32 = call [eax*4+disp]", decode_ff2(bytes([0xFF, 0x14, 0x85, 0x10, 0x00, 0x00, 0x00])),
        {"base": None, "index": "eax", "scale": 4, "disp": 0x10})
    chk("FF 15 disp32 = call [disp]", decode_ff2(bytes([0xFF, 0x15, 0x44, 0x33, 0x22, 0x11])),
        {"base": None, "index": None, "scale": 1, "disp": 0x11223344})
    chk("長度不符 -> None", decode_ff2(bytes([0xFF, 0x15, 0x44])), None)
    chk("FF /3(callf)-> None", decode_ff2(bytes([0xFF, 0xD8])), None)

    print("[4] 參數位置(argc)")
    chk("argc 3、第 1 參數 -> s1", param_slot(3, 1), "s1")
    chk("argc 0、第 2 參數 -> edx(Watcom 暫存器)", param_slot(0, 2), "edx")
    chk("argc 1、第 2 參數 -> 不猜", param_slot(1, 2), None)
    chk("argc 不明 -> 不猜", param_slot(None, 1), None)
    chk("參考版 memcpy / strlen 是堆疊傳參(argc ≥ 1)", (st.argc[memcpy] or 0) >= 1 and (st.argc[strlen] or 0) >= 1, True)

    print("[5] 語意驗算")
    ac_m, ac_s = st.argc[memcpy], st.argc[strlen]
    good = parse_calllog(_synthetic(st, memcpy, ret_rt, stack=[0x2000, 0x3000, 4], ret_line="R 1 0 00002000 0 0\n"))
    bad = parse_calllog(_synthetic(st, memcpy, ret_rt, stack=[0x2000, 0x3000, 4], ret_line="R 1 0 00003000 0 0\n"))
    regonly = parse_calllog(_synthetic(st, memcpy, ret_rt, {"eax": 0x3000}, stack=[0x2000],
                                       ret_line="R 1 0 00003000 0 0\n"))
    chk("memcpy 回傳 dst([esp+4])-> 成立", oracle_check("memcpy", good.entries[1], good.returns[1], ac_m)[0], True)
    chk("memcpy 回傳 src -> 不成立", oracle_check("memcpy", bad.entries[1], bad.returns[1], ac_m)[0], False)
    chk("堆疊傳參的 memcpy 回傳 eax 不算 dst(不兩邊都收)",
        oracle_check("memcpy", regonly.entries[1], regonly.returns[1], ac_m)[0], False)
    s5 = "4142434445" + "00" + "41" * 26
    l5 = parse_calllog(_synthetic(st, strlen, ret_rt, mems={"s1": s5}, ret_line="R 1 0 00000005 0 0\n"))
    l6 = parse_calllog(_synthetic(st, strlen, ret_rt, mems={"s1": s5}, ret_line="R 1 0 00000006 0 0\n"))
    l_eax = parse_calllog(_synthetic(st, strlen, ret_rt, mems={"eax": s5, "s1": "41" + "00" * 31},
                                     ret_line="R 1 0 00000005 0 0\n"))
    chk("strlen 5 對 [esp+4] 'ABCDE\\0' -> 成立", oracle_check("strlen", l5.entries[1], l5.returns[1], ac_s)[0], True)
    chk("strlen 6 -> 不成立", oracle_check("strlen", l6.entries[1], l6.returns[1], ac_s)[0], False)
    chk("字串在 eax 不在 [esp+4] -> 依 argc 看 [esp+4],不成立",
        oracle_check("strlen", l_eax.entries[1], l_eax.returns[1], ac_s)[0], False)
    lq = parse_calllog(_synthetic(st, strlen, ret_rt, mems={"s1": "41" * 4 + "??" * 28},
                                  ret_line="R 1 0 00000002 0 0\n"))
    chk("讀不到之前沒有 NUL、回 2 < 可讀 4 -> 不成立", oracle_check("strlen", lq.entries[1], lq.returns[1], ac_s)[0],
        False)
    chk("rand 0x8000 -> 不成立", oracle_check("rand", good.entries[1], (0x8000, 0), 0)[0], False)
    chk("strcmp 'AB' vs 'AC' 回負 -> 成立", oracle_check("strcmp", parse_calllog(_synthetic(
        st, memcpy, ret_rt, mems={"s1": "414200" + "00" * 29, "s2": "414300" + "00" * 29})).entries[1],
        (0xFFFFFFFF, 0), 2)[0], True)
    chk("strcmp 'AB' vs 'AC' 回正 -> 不成立", oracle_check("strcmp", parse_calllog(_synthetic(
        st, memcpy, ret_rt, mems={"s1": "414200" + "00" * 29, "s2": "414300" + "00" * 29})).entries[1],
        (1, 0), 2)[0], False)
    chk("非 libc 名稱 -> 不適用", oracle_check("draw_unit", good.entries[1], good.returns[1], 3), None)
    chk("摘要「回傳緩衝區」-> 定位到參數列第 2 個",
        summary_claims("(值, 緩衝區, 進位):... 回傳緩衝區。"), [("ret_param", 2, "緩衝區")])
    chk("沒有參數列 -> 宣稱無法定位", summary_claims("... 回傳緩衝區"), [("ret_param", None, "緩衝區")])
    chk("摘要沒寫 -> 沒有宣稱", summary_claims("畫單位"), [])
    cl = ("ret_param", 2, "緩衝區")
    ent = parse_calllog(_synthetic(st, memcpy, ret_rt, stack=[5, 0x4000, 10])).entries[1]
    chk("回傳第 2 參數 -> 成立", claim_check(cl, ent, (0x4000, 0), 3, "")[0], True)
    chk("回傳第 1 參數 -> 不成立", claim_check(cl, ent, (5, 0), 3, "")[0], False)
    chk("回 0 且摘要寫「回 NULL」-> 成立", claim_check(cl, ent, (0, 0), 3, "失敗時回 NULL")[0], True)
    chk("回 0 但摘要沒寫 NULL -> 不成立", claim_check(cl, ent, (0, 0), 3, "")[0], False)
    ent0 = parse_calllog(_synthetic(st, memcpy, ret_rt, stack=[0x500, 0])).entries[1]
    chk("參數是「緩衝區或 NULL」且傳 NULL -> 不適用",
        claim_check(("ret_param", 2, "緩衝區或 NULL"), ent0, (0x9000, 0), 2, ""), None)

    print("[6] 整體 check():失敗會被報出來")
    txt = (_synthetic(st, memcpy, ret_rt, stack=[0x2000, 0x3000, 4], seq=1, ret_line="R 1 0 00003000 0 0\n")
           + _synthetic(st, memcpy, ret_rt, code=bytes(flip), seq=2))
    lg = parse_calllog(txt)
    rep = check(st, [lg])
    lines, fl = summarize(st, [lg], rep)
    chk("碼位元組不符的那筆不採用", rep.foreign, [2])
    chk("FAIL 行含碼位元組不符", any("碼位元組" in f for f in fl), True)
    chk("FAIL 行含 memcpy 語意不成立", any("oracle:memcpy" in f for f in fl), True)
    rep_ok = check(st, [good])
    chk("全部成立時沒有 FAIL", summarize(st, [good], rep_ok)[1], [])
    chk("成立的規則有被計數", rep_ok.checks[memcpy]["oracle:memcpy"]["pass"], 1)

    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        return 1
    print("\n--selftest OK")
    return 0


# ---------------------------------------------------------------- CLI

def write_entries(path: Path) -> int:
    inv = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))["entries"]
    path.write_bytes("".join(f"{int(e['addr'], 16) + DELTA:08x}\n" for e in inv).encode("ascii"))
    print(f"wrote {len(inv)} entries (runtime EIP = native + {DELTA:#x}) -> {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="以原版實機函式呼叫紀錄反驗名稱與摘要")
    ap.add_argument("logs", nargs="*", type=Path, help="CALLLOG.TXT")
    ap.add_argument("--write-entries", metavar="OUT", type=Path, help="寫 harness 用的入口檔")
    ap.add_argument("--json", metavar="OUT", type=Path, help="寫逐函式剖面")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.write_entries:
        return write_entries(a.write_entries)
    if not a.logs:
        ap.error("需要 CALLLOG.TXT、--write-entries 或 --selftest")
    st = load_static()
    logs = [parse_calllog(p.read_text(encoding="ascii", errors="replace")) for p in a.logs]
    rep = check(st, logs)
    lines, fails = summarize(st, logs, rep)
    for ln in lines:
        print(ln)
    if a.json:
        a.json.write_text(json.dumps(profiles_doc(st, rep), ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                          newline="\n")
        print(f"剖面 -> {a.json}")
    for f in fails:
        print(f"FAIL {f}")
    print("結果:" + ("FAIL" if fails else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
