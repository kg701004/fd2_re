#!/usr/bin/env python3
"""ail_driver_disasm.py —— 反組譯 Miles AIL 3 的 16 位元驅動檔(.DIG / .MDI):功能表、I/O 埠、呼叫參數。

為什麼需要這支
--------------
續一百七十二留下三件只能在驅動程式碼裡回答的事:SB16.DIG 初始化是不是留下單一樣本 DMA
(DOSBox-X 只在 DMA 計數暫存器寫 0 時進 DMA_DAC_Event,INFERRED)、續一百七十 MDI 每 8 次服務
多一次驅動呼叫、4 次短驅動呼叫的來源。`calllog_segments.py disasm` 只解紀錄裡帶位元組的單條指令,
`disasm_le.py` 只讀 FD2.EXE 的 LE 格式,整份驅動檔一直沒有工具能看。

驅動檔格式(只用到的部分)
--------------------------
檔頭前 8 位元組是 `AIL3DIG\\x1a` 或 `AIL3MDI\\x1a`;+0x34 一個 word 是 int 66h 分派段的位移。
驅動整檔載入一個段、位移 0 就是檔頭(分派段用 `cs:[0x32]`、`ljmp cs:[0x36]` 讀檔頭欄位),
所以檔內位移 = 執行時的 IP。功能表不寫死:從分派段依序讀 `mov si, 表`、`sub ax, 差`、`cmp ax, 個數`,
直到第一個 `call`(分派段的 `call word ptr [bx + si]`),每組得到 (功能號起點, 表位址, 個數)。

做法
----
* 遞迴走訪:起點是分派段與功能表每一格;跟 jcc 兩邊、jmp / call 的直接目標;
  ret / iret / retf / jmp 後停。間接 near 跳轉 / 呼叫列在「間接」裡(分派段那一個標 function table),
  間接 far(`ljmp cs:[0x36]` 轉給舊向量)標 external。
* 暫存器常數:進入點的暫存器記成符號 `dx@0x328`(呼叫端傳進來的值),call / int 之後全部歸為未知;
  跳轉會合處取所有前驅都相同的值(迴圈裡每圈不同的值掉成未知),反覆推到不再變。逐條往前推的只有:mov / xor 自己 / add sub and or xor shl shr inc dec 對常數;
  記憶體來源記成符號(`word[0x63]`、`byte[bx+0x148]`,基底暫存器已知時併進位移)。
  對符號做 `add dl, 6` 這種低位元組加減時當成不進位(I/O 基底 0x220 這類位址成立;其他情況要自己核)。
  capstone 報告會寫的其他暫存器(含隱含的)一律歸為未知。
* 執行時才裝上的進入點(不在功能表裡):`mov word ptr X, 位移` 後 4 條內有 `mov word ptr X+2, cs`
  (組遠指標;位移是立即值或已知的暫存器),或位移是某進入點收到的參數(`dx@0x328`)時到每個 `call 0x328`
  看當下的值(SB16.DIG 0x328 設 IRQ 向量就是這樣;續一百七十三 lc173a 的 O 紀錄在 0x3f3 / 0x408 寫 PIC,
  只看立即值時這段沒走到);或 `int 21h` 時 AH = 25h 且 DX 已知。新進入點走完再掃一次,直到不再增加。
* 沒走到的位元組逐段列出(檔頭、表格、資料、或靠暫存器 / 執行時資料才到得了的程式),
  「沒走到」不等於「是資料」。

子命令
------
    python tools/ail_driver_disasm.py header <DRIVER>                 # 種類、分派段、功能表
    python tools/ail_driver_disasm.py disasm <DRIVER> [--entry 0xNNN]  # 整份清單(標進入點、I/O 的埠與值)
    python tools/ail_driver_disasm.py io     <DRIVER> [--entry ...]    # 每條 in / out:埠、寫入值、所在進入點
    python tools/ail_driver_disasm.py calls  <DRIVER> 0xNNN [--entry ...]  # 每個 call 0xNNN 當下已知的暫存器
    python tools/ail_driver_disasm.py refs   <DRIVER> 0xNNN [--entry ...]  # 記憶體位移或立即值等於 0xNNN 的指令
    python tools/ail_driver_disasm.py --selftest

<DRIVER> 是路徑;只給檔名且不存在時到 `--game`(預設 FD2_GAME_DIR 或 org_game/炎龍騎士團/FLAME2)找。
只讀檔案,不寫任何檔案。需要 capstone。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
MAGIC = {b"AIL3DIG\x1a": "DIG", b"AIL3MDI\x1a": "MDI"}
DISPATCH_OFF = 0x34

# 8 位元半邊的值:常數、8 位元符號、或 16 位元符號的低 / 高半 ("lo" | "hi", 符號)
Half = Union[int, str, tuple, None]
Val = Union[int, str, None]
_R16 = ("ax", "bx", "cx", "dx", "si", "di", "bp", "sp")
_R8 = {"al": ("ax", 0), "ah": ("ax", 1), "bl": ("bx", 0), "bh": ("bx", 1),
       "cl": ("cx", 0), "ch": ("cx", 1), "dl": ("dx", 0), "dh": ("dx", 1)}
_ARITH = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b, "and": lambda a, b: a & b,
          "or": lambda a, b: a | b, "xor": lambda a, b: a ^ b, "shl": lambda a, b: a << b,
          "shr": lambda a, b: a >> b}
_RET = ("ret", "retf", "iret")
DATAFLOW_ROUNDS = 64                                    # reg_states 的保險上限:平均每條指令最多重算幾次


def _md() -> Any:
    import capstone  # 選用:Windows 端的 Python 有
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    md.detail = True
    return md


def _w(b: bytes, a: int) -> int:
    return int.from_bytes(b[a:a + 2], "little")


@dataclass(frozen=True)
class FuncEntry:
    """功能表一格:功能號、表內位址、指向的進入點。"""

    num: int
    slot: int
    addr: int


def parse_header(b: bytes) -> tuple[str, int]:
    """讀檔頭。

    Args:
        b: 整份驅動檔。

    Returns:
        (種類 "DIG" / "MDI", 分派段位移)。

    Raises:
        ValueError: 不是 AIL 3 驅動,或分派段位移在檔外。
    """
    kind = MAGIC.get(b[:8])
    if kind is None:
        raise ValueError(f"not an AIL3 driver: magic {b[:8].hex()}")
    disp = _w(b, DISPATCH_OFF)
    if not disp or disp >= len(b):
        raise ValueError(f"dispatcher offset {disp:#x} outside file ({len(b):#x} bytes)")
    return kind, disp


def function_table(b: bytes, disp: int) -> tuple[list[FuncEntry], int | None]:
    """從分派段讀出功能表。

    Returns:
        (每一格, 分派段 `call [bx + si]` 的位址;沒找到是 None)。
    """
    import capstone
    out: list[FuncEntry] = []
    si: int | None = None
    base = 0
    for ins in _md().disasm(b[disp:], disp):
        if ins.mnemonic == "call":
            return out, ins.address
        ops = ins.operands
        if len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG and ops[1].type == capstone.x86.X86_OP_IMM:
            r, v = ins.reg_name(ops[0].reg), ops[1].imm & 0xFFFF
            if ins.mnemonic == "mov" and r == "si":
                si = v
            elif ins.mnemonic == "sub" and r == "ax":
                base += v
            elif ins.mnemonic == "cmp" and r == "ax" and si is not None:
                out += [FuncEntry(base + i, si + 2 * i, _w(b, si + 2 * i)) for i in range(v)]
    return out, None


class Regs:
    """區塊內的暫存器常數 / 符號(每個 16 位元暫存器存低、高兩個半邊)。"""

    def __init__(self) -> None:
        self.h: dict[tuple[str, int], Half] = {}

    def copy(self) -> "Regs":
        r = Regs()
        r.h = dict(self.h)
        return r

    def get(self, n: str) -> Val:
        if n in _R8:
            v = self.h.get(_R8[n])
            return f"{v[0]}({v[1]})" if isinstance(v, tuple) else v
        lo, hi = self.h.get((n, 0)), self.h.get((n, 1))
        if isinstance(lo, int) and isinstance(hi, int):
            return hi << 8 | lo
        if hi == 0 and isinstance(lo, str):
            return lo                                   # 8 位元符號零延伸(mov dl, byte[..]; mov dh, 0)
        if isinstance(lo, tuple) and lo == ("lo", hi[1] if isinstance(hi, tuple) else None) and hi[0] == "hi":
            return lo[1]
        return None

    def set(self, n: str, v: Val) -> None:
        if n in _R8:
            self.h[_R8[n]] = v
        elif n in _R16:
            if isinstance(v, int):
                self.h[(n, 0)], self.h[(n, 1)] = v & 0xFF, v >> 8 & 0xFF
            elif isinstance(v, str):
                self.h[(n, 0)], self.h[(n, 1)] = ("lo", v), ("hi", v)
            else:
                self.h[(n, 0)] = self.h[(n, 1)] = None


def _memsym(ins: Any, op: Any, st: Regs) -> str:
    m = op.mem
    disp = m.disp & 0xFFFF
    regs: list[str] = []
    for r in (m.base, m.index):
        if r:
            n = ins.reg_name(r)
            v = st.get(n)
            if isinstance(v, int):
                disp = (disp + v) & 0xFFFF
            else:
                regs.append(n)
    seg = ins.reg_name(m.segment) + ":" if m.segment else ""
    return f"{'byte' if op.size == 1 else 'word'}[{seg}{'+'.join(regs + [f'{disp:#x}'])}]"


def _opval(ins: Any, op: Any, st: Regs) -> Val:
    import capstone
    if op.type == capstone.x86.X86_OP_IMM:
        return op.imm & (0xFF if op.size == 1 else 0xFFFF)
    if op.type == capstone.x86.X86_OP_REG:
        return st.get(ins.reg_name(op.reg))
    return _memsym(ins, op, st)


def step(ins: Any, st: Regs) -> None:
    """把一條指令對暫存器的作用推進 st(就地修改)。"""
    import capstone
    m, ops = ins.mnemonic, ins.operands
    if m == "call" or m == "int":
        st.h.clear()                                    # 被呼叫端 / 中斷服務可能改任何暫存器
        return
    dst = ins.reg_name(ops[0].reg) if ops and ops[0].type == capstone.x86.X86_OP_REG else None
    new: tuple[str, Val] | None = None
    if dst in _R8 or dst in _R16:
        src = _opval(ins, ops[1], st) if len(ops) == 2 else None
        cur = st.get(dst)
        mask = 0xFF if ops[0].size == 1 else 0xFFFF
        if m == "mov":
            new = (dst, src)
        elif m in ("xor", "sub") and len(ops) == 2 and ops[1].type == capstone.x86.X86_OP_REG and ops[1].reg == ops[0].reg:
            new = (dst, 0)
        elif m in _ARITH and isinstance(cur, int) and isinstance(src, int):
            new = (dst, _ARITH[m](cur, src) & mask)
        elif m in ("inc", "dec") and isinstance(cur, int):
            new = (dst, (cur + (1 if m == "inc" else -1)) & mask)
        elif m in ("add", "sub") and isinstance(src, int) and dst in _R8 and _R8[dst][1] == 0 \
                and isinstance(st.get(_R8[dst][0]), str):
            # 低位元組對符號加減:當成不進位,記在整個 16 位元暫存器上
            full = _R8[dst][0]
            new = (full, f"{st.get(full)}{'+' if m == 'add' else '-'}{src:#x}")
    _, written = ins.regs_access()
    for r in written:
        st.set(ins.reg_name(r), None)
    if new is not None:
        st.set(*new)


@dataclass
class Prog:
    """走訪結果。"""

    b: bytes
    insns: dict[int, Any] = field(default_factory=dict)
    entries: dict[int, str] = field(default_factory=dict)
    indirect: dict[int, str] = field(default_factory=dict)


def _is_jump(ins: Any) -> bool:
    import capstone
    # capstone 5 的 loop / loope / loopne 只在 branch_relative 群組,不在 jump
    return bool(ins.group(capstone.CS_GRP_JUMP)) or ins.mnemonic.startswith("loop")


def _walk(prog: Prog, roots: list[int]) -> None:
    import capstone
    md = _md()
    work = list(roots)
    while work:
        a = work.pop()
        while a < len(prog.b) and a not in prog.insns:
            ins = next(md.disasm(prog.b[a:], a), None)
            if ins is None:
                break
            prog.insns[a] = ins
            m, ops = ins.mnemonic, ins.operands
            if m in _RET:
                break
            if _is_jump(ins) or ins.group(capstone.CS_GRP_CALL):
                if ops and ops[0].type == capstone.x86.X86_OP_IMM:
                    t = ops[0].imm & 0xFFFF
                    if m == "call":
                        prog.entries.setdefault(t, "call")
                    work.append(t)
                else:
                    prog.indirect[a] = "external" if m in ("ljmp", "lcall") else "unresolved"
                if m in ("jmp", "ljmp"):
                    break
            a += ins.size


def _succ(ins: Any) -> list[int]:
    import capstone
    m, ops = ins.mnemonic, ins.operands
    nxt = ins.address + ins.size
    if m in _RET or m == "ljmp":
        return []
    if _is_jump(ins):
        t = [ops[0].imm & 0xFFFF] if ops[0].type == capstone.x86.X86_OP_IMM else []
        return t if m == "jmp" else t + [nxt]
    return [nxt]


def _meet(states: list[Regs]) -> Regs:
    r = Regs()
    first = states[0].h
    r.h = {k: v for k, v in first.items() if all(s.h.get(k, None) == v for s in states[1:]) and v is not None}
    return r


def _entry_state(a: int) -> Regs:
    st = Regs()
    for r in _R16[:-1]:                                 # sp 不追
        st.set(r, f"{r}@{a:#x}")                        # 呼叫端傳進來的值(符號)
    return st


def reg_states(prog: Prog, budget: int | None = None) -> dict[int, Regs]:
    """每條指令執行前的暫存器狀態。

    進入點的暫存器是符號 `dx@0x328`(呼叫端傳進來的值);其他位置取所有已算過的前驅
    (落下來的、跳過來的)都相同的值,反覆推到不再變(迴圈裡每圈不同的值會掉成未知)。

    Args:
        prog: 走訪結果。
        budget: 最多處理幾次指令;None = DATAFLOW_ROUNDS × 指令數。

    Raises:
        RuntimeError: 用完 budget 還沒收斂(不默默給半套答案)。
    """
    import heapq
    preds: dict[int, list[int]] = {a: [] for a in prog.insns}
    for a, ins in prog.insns.items():
        for s in _succ(ins):
            if s in preds:
                preds[s].append(a)
    inn: dict[int, Regs] = {}
    outs: dict[int, Regs] = {}
    work = sorted(prog.insns)
    queued = set(work)
    if budget is None:
        budget = DATAFLOW_ROUNDS * len(work)
    while work:
        budget -= 1
        if budget < 0:
            raise RuntimeError("register dataflow did not converge")
        a = heapq.heappop(work)
        queued.discard(a)
        ps = [outs[p] for p in preds[a] if p in outs]
        st = _entry_state(a) if a in prog.entries else _meet(ps) if ps else Regs()
        if a in outs and inn[a].h == st.h:
            continue
        inn[a] = st
        o = st.copy()
        step(prog.insns[a], o)
        outs[a] = o
        for s in _succ(prog.insns[a]):
            if s in preds and s not in queued:
                heapq.heappush(work, s)
                queued.add(s)
    return inn


def _memkey(op: Any) -> tuple[int, int, int, int]:
    return op.mem.segment, op.mem.base, op.mem.index, op.mem.disp & 0xFFFF


_ARG = re.compile(r"([a-d]x|si|di|bp)@0x([0-9a-f]+)")


def runtime_entries(prog: Prog, states: dict[int, Regs]) -> dict[int, str]:
    """組遠指標或 int 21h AH=25h 裝上的進入點(尚未走過的)。

    遠指標的位移是常數(立即值,或暫存器已知)就直接收;是進入點收到的參數(`dx@0x328`,
    SB16.DIG 設 IRQ 向量的副程式就是這樣)就到每個 `call 0x328` 看當下 DX 是不是常數。
    """
    import capstone
    found: dict[int, str] = {}
    setters: set[tuple[str, int]] = set()
    addrs = sorted(prog.insns)
    for i, a in enumerate(addrs):
        ins = prog.insns[a]
        ops = ins.operands
        if ins.mnemonic == "mov" and len(ops) == 2 and ins.op_str.startswith("word ptr ") \
                and ops[1].type in (capstone.x86.X86_OP_IMM, capstone.x86.X86_OP_REG):
            src = _opval(ins, ops[1], states[a])
            seg, base, idx, disp = _memkey(ops[0])
            for nxt in addrs[i + 1:i + 5]:
                o = prog.insns[nxt].operands
                if prog.insns[nxt].mnemonic == "mov" and len(o) == 2 and o[0].type == capstone.x86.X86_OP_MEM \
                        and o[1].type == capstone.x86.X86_OP_REG and prog.insns[nxt].reg_name(o[1].reg) == "cs" \
                        and _memkey(o[0]) == (seg, base, idx, (disp + 2) & 0xFFFF):
                    if isinstance(src, int):
                        found[src] = f"far pointer @{a:#x}"
                    elif isinstance(src, str) and _ARG.fullmatch(src):
                        mt = _ARG.fullmatch(src)
                        setters.add((mt.group(1), int(mt.group(2), 16)))
        elif ins.mnemonic == "int" and ops[0].imm == 0x21 and states[a].get("ah") == 0x25 \
                and isinstance(states[a].get("dx"), int):
            found[states[a].get("dx")] = f"int 21h/25h @{a:#x}"
    for reg, ent in sorted(setters):
        for site, regs in call_args(prog, states, ent):
            if isinstance(regs.get(reg), int):
                found[regs[reg]] = f"far pointer via call {ent:#x} @{site:#x}"
    return {t: why for t, why in found.items() if t < len(prog.b) and t not in prog.insns}


def explore(b: bytes, extra: list[int] | None = None) -> tuple[Prog, list[FuncEntry], dict[int, Regs]]:
    """整份走訪:分派段、功能表、--entry、執行時才裝上的進入點(到不再增加為止)。"""
    _kind, disp = parse_header(b)
    table, call_site = function_table(b, disp)
    prog = Prog(b)
    prog.entries[disp] = "int 66h dispatcher"
    for f in table:
        prog.entries.setdefault(f.addr, f"function {f.num:#x}")
    for a in extra or []:
        prog.entries.setdefault(a, "--entry")
    _walk(prog, list(prog.entries))
    while True:
        states = reg_states(prog)
        new = runtime_entries(prog, states)
        if not new:
            break
        for t, why in new.items():
            prog.entries.setdefault(t, why)
        _walk(prog, list(new))
    if call_site in prog.indirect:
        prog.indirect[call_site] = "function table"
    return prog, table, states


@dataclass(frozen=True)
class IoSite:
    """一條 in / out。"""

    addr: int
    op: str
    port: Val
    value: Val
    entry: int


def _entry_of(prog: Prog, a: int) -> int:
    return max(e for e in prog.entries if e <= a)


def io_sites(prog: Prog, states: dict[int, Regs]) -> list[IoSite]:
    """每條 in / out 的埠與(out 的)寫入值。"""
    import capstone
    out = []
    for a in sorted(prog.insns):
        ins = prog.insns[a]
        if ins.mnemonic not in ("in", "out"):
            continue
        ops, st = ins.operands, states[a]
        pi = 0 if ins.mnemonic == "out" else 1
        po = ops[pi]
        port = po.imm & 0xFF if po.type == capstone.x86.X86_OP_IMM else st.get("dx")
        value = st.get(ins.reg_name(ops[1].reg)) if ins.mnemonic == "out" else None
        out.append(IoSite(a, ins.mnemonic, port, value, _entry_of(prog, a)))
    return out


CALL_REGS = ("ax", "bx", "cx", "dx", "si", "di", "bp")


def call_args(prog: Prog, states: dict[int, Regs], target: int) -> list[tuple[int, dict[str, Val]]]:
    """每個 `call target` 當下已知的暫存器(AX 整個未知時改列 AL / AH)。"""
    import capstone
    out = []
    for a in sorted(prog.insns):
        ins = prog.insns[a]
        ops = ins.operands
        if ins.mnemonic == "call" and ops[0].type == capstone.x86.X86_OP_IMM and ops[0].imm & 0xFFFF == target:
            st = states[a]
            known = {r: st.get(r) for r in CALL_REGS}
            if known["ax"] is None:
                known.update(al=st.get("al"), ah=st.get("ah"))
            out.append((a, {r: v for r, v in known.items() if v is not None}))
    return out


def refs(prog: Prog, addr: int) -> list[int]:
    """記憶體位移或立即值等於 addr 的指令。"""
    import capstone
    out = []
    for a in sorted(prog.insns):
        for op in prog.insns[a].operands:
            if (op.type == capstone.x86.X86_OP_MEM and op.mem.disp & 0xFFFF == addr) or \
                    (op.type == capstone.x86.X86_OP_IMM and op.imm & 0xFFFF == addr):
                out.append(a)
                break
    return out


def gaps(prog: Prog) -> list[tuple[int, int]]:
    """沒走到的位元組 [起, 訖)。"""
    seen = bytearray(len(prog.b))
    for a, ins in prog.insns.items():
        seen[a:a + ins.size] = b"\x01" * ins.size
    out: list[tuple[int, int]] = []
    a = 0
    while a < len(seen):
        if seen[a]:
            a += 1
            continue
        s = a
        while a < len(seen) and not seen[a]:
            a += 1
        out.append((s, a))
    return out


def _fmt(v: Val) -> str:
    return "?" if v is None else f"{v:#x}" if isinstance(v, int) else v


def _table_hint(b: bytes, port: Val) -> str:
    # 埠來自 byte[reg+T] / byte[T] 時附上檔案裡 T 起 8 個位元組(執行時可能被改)
    if isinstance(port, str) and port.startswith("byte[") and port.endswith("]"):
        try:
            t = int(port[5:-1].split("+")[-1], 16)
        except ValueError:
            return ""
        return f"  (file bytes @{t:#x}: {b[t:t + 8].hex(' ')})"
    return ""


# ---------------------------------------------------------------- selftest

def _fixture() -> bytes:
    """合成的 AIL3DIG 驅動(位址與位元組在註解裡逐條寫明,selftest 先用 capstone 核對)。"""
    b = bytearray(0x17F)
    code = {
        0x00: "41494c334449471a",                       # "AIL3DIG\x1a"
        0x34: "6000ffff",                               # 分派段 0x60;+0x36 非 0,抓讀超過 2 位元組
        0x40: "9000a000b80000000a0b",                   # 表一 0x40:0x90 0xa0;表二 0x44:0xb8;0x48 埠表
        0x60: "be4000" "2d0003" "3d0200" "720b"         # mov si,0x40; sub ax,0x300; cmp ax,2; jb 0x76
              "be4400" "2d0001" "3d0100" "7306"         # mov si,0x44; sub ax,0x100; cmp ax,1; jae 0x7c
              "89c3" "01db" "ff10" "cf",                # mov bx,ax; add bx,bx; call [bx+si]; iret
        0x90: "8b163a00" "80c20c" "b0d1" "ee"           # mov dx,[0x3a]; add dl,0xc; mov al,0xd1; out dx,al
              "b014" "e82500" "c3",                     # mov al,0x14; call 0xc4; ret
        0xA0: "c7065000d000" "8c0e5200"                 # mov [0x50],0xd0; mov [0x52],cs  -> 進入點 0xd0
              "c70654001701" "89065600" "eb6a",         # mov [0x54],0x117; mov [0x56],ax -> 不是(不是 cs); jmp 0x120
        0xB8: "bae000" "b80f25" "cd21" "ff6746",        # mov dx,0xe0; mov ax,0x250f; int 21h; jmp [bx+0x46]
        0xC4: "ec" "ee" "c3",                           # in al,dx; out dx,al; ret
        0xD0: "e460" "b020" "e620" "cf",                # in al,0x60; mov al,0x20; out 0x20,al; iret
        0xE0: "bb0100" "8a5748" "b600" "30c0" "ee"      # mov bx,1; mov dl,[bx+0x48]; mov dh,0; xor al,al; out dx,al
              "b80500" "050300" "25fe00" "0d1000"       # mov ax,5; add ax,3; and ax,0xfe; or ax,0x10
              "351100" "c1e002" "d1e8" "48" "40" "40"   # xor ax,0x11; shl ax,2; shr ax,1; dec ax; inc ax; inc ax
              "2d0200" "e621"                           # sub ax,2; out 0x21,al            (0x11)
              "8b0e3c00" "80e908" "89ca" "ee"           # mov cx,[0x3c]; sub cl,8; mov dx,cx; out dx,al
              "86e9" "89ca" "ee" "cb",                  # xchg cl,ch; mov dx,cx; out dx,al; retf
        0x120: "b207" "b602" "b001" "3c00" "7404"       # mov dl,7; mov dh,2; mov al,1; cmp al,0; je 0x12e
               "b002" "b405" "ee"                       # mov al,2; mov ah,5; out dx,al   (會合:dx 同、al 不同)
               "b90300" "42" "e2fd" "ee"                # mov cx,3; inc dx; loop 0x132; out dx,al
               "ba6001" "e80400" "c3",                  # mov dx,0x160; call 0x140; ret
        0x140: "268917" "268c4f02" "c3",                # mov es:[bx],dx; mov es:[bx+2],cs; ret  (設向量,DX 是參數)
        0x160: "b020" "04f0" "e622"                     # 只能經 call 0x140 的 DX 找到;al = 0x20 + 0xf0 取 8 位元 = 0x10
               "b80600" "bb0300" "31d8" "e623"          # mov ax,6; mov bx,3; xor ax,bx(不同暫存器,= 5); out 0x23,al
               "c70658001701" "90909090"                # mov [0x58],0x117; 4 個 nop
               "8c0e5a00" "cf",                         # mov [0x5a],cs 是第 5 條:超出 4 條的窗,不算遠指標; iret
        0x117: "90909090",                              # 沒有人到得了(0xa0 / 0x170 兩個不成立的遠指標指這裡)
    }
    for a, h in code.items():
        bs = bytes.fromhex(h)
        b[a:a + len(bs)] = bs                           # 依長度放:位元組數不會改到檔案大小
    return bytes(b)


def selftest() -> int:
    """合成驅動檔上的固定答案;另有幾個反例(魔數錯、分派段越界、遠指標段不是 cs)。"""
    try:
        import capstone  # noqa: F401
    except ImportError:
        print("selftest: FAIL (capstone missing)")
        return 1
    fails: list[str] = []

    def eq(name: str, got: object, want: object) -> None:
        if got != want:
            fails.append(f"{name}: got {got!r}, want {want!r}")

    fx = _fixture()
    md = _md()
    for a, want in ((0x69, "jb 0x76"), (0x7a, "call word ptr [bx + si]"), (0x9c, "call 0xc4"),
                    (0xC0, "jmp word ptr [bx + 0x46]"), (0xE3, "mov dl, byte ptr [bx + 0x48]"),
                    (0xFA, "shl ax, 2"), (0x111, "xchg cl, ch"), (0x116, "retf"), (0xB4, "jmp 0x120"),
                    (0x128, "je 0x12e"), (0x133, "loop 0x132"), (0x139, "call 0x140"),
                    (0x143, "mov word ptr es:[bx + 2], cs"), (0x162, "add al, 0xf0"), (0x16C, "xor ax, bx"),
                    (0x17A, "mov word ptr [0x5a], cs"), (0x17E, "iret")):
        i = next(md.disasm(fx[a:a + 16], a))
        eq(f"fixture {a:#x}", f"{i.mnemonic} {i.op_str}".strip(), want)
    eq("fixture size", len(fx), 0x17F)

    eq("header", parse_header(fx), ("DIG", 0x60))
    eq("header MDI", parse_header(b"AIL3MDI\x1a" + fx[8:])[0], "MDI")
    for name, bad in (("magic", b"AIL3XXX\x1a" + fx[8:]), ("disp 0", fx[:0x34] + b"\0\0" + fx[0x36:]),
                      ("disp == len", fx[:0x34] + len(fx).to_bytes(2, "little") + fx[0x36:])):
        try:
            parse_header(bad)
            fails.append(f"header {name}: no ValueError")
        except ValueError:
            pass

    table, site = function_table(fx, 0x60)
    eq("table", [(f.num, f.slot, f.addr) for f in table], [(0x300, 0x40, 0x90), (0x301, 0x42, 0xA0), (0x400, 0x44, 0xB8)])
    eq("table call site", site, 0x7A)
    eq("table no call", function_table(fx[:0x7A], 0x60)[1], None)

    prog, _t, states = explore(fx)
    eq("entries", dict(sorted(prog.entries.items())),
       {0x60: "int 66h dispatcher", 0x90: "function 0x300", 0xA0: "function 0x301", 0xB8: "function 0x400",
        0xC4: "call", 0xD0: "far pointer @0xa0", 0xE0: "int 21h/25h @0xbe", 0x140: "call",
        0x160: "far pointer via call 0x140 @0x139"})
    eq("indirect", prog.indirect, {0x7A: "function table", 0xC0: "unresolved"})
    # 手算:0x7c iret 止、0xb4 jmp 止、0xc0 jmp 止、0xc6 ret 止、0xd6 iret 止、0x116 retf 止、0x136 ret 止
    eq("gaps", gaps(prog), [(0, 0x60), (0x7D, 0x90), (0xB6, 0xB8), (0xC3, 0xC4), (0xC7, 0xD0), (0xD7, 0xE0),
                            (0x117, 0x120), (0x13D, 0x140), (0x148, 0x160)])

    io = [(s.addr, s.op, s.port, s.value, s.entry) for s in io_sites(prog, states)]
    eq("io", io, [(0x99, "out", "word[0x3a]+0xc", 0xD1, 0x90),
                  (0xC4, "in", "dx@0xc4", None, 0xC4), (0xC5, "out", "dx@0xc4", None, 0xC4),  # in 改了 al
                  (0xD0, "in", 0x60, None, 0xD0), (0xD4, "out", 0x20, 0x20, 0xD0),
                  (0xEA, "out", "byte[0x49]", 0, 0xE0),       # bx = 1 併進位移
                  (0x105, "out", 0x21, 0x11, 0xE0),            # 5+3 &fe |10 ^11 <<2 >>1 -1 +1 +1 -2
                  (0x110, "out", "word[0x3c]-0x8", 0x11, 0xE0),
                  (0x115, "out", None, 0x11, 0xE0),            # xchg 改了 cl / ch
                  (0x12E, "out", 0x207, None, 0xE0),           # 會合:兩條路 dx 相同、al 1 / 2
                  (0x135, "out", None, None, 0xE0),            # 迴圈裡 inc dx:每圈不同
                  (0x164, "out", 0x22, 0x10, 0x160),           # 8 位元加法進位丟掉
                  (0x16E, "out", 0x23, 5, 0x160)])             # 6 xor 3
    eq("calls", call_args(prog, states, 0xC4),
       [(0x9C, {"bx": "bx@0x90", "cx": "cx@0x90", "dx": "word[0x3a]+0xc", "si": "si@0x90", "di": "di@0x90",
                "bp": "bp@0x90", "al": 0x14, "ah": "hi(ax@0x90)"})])
    # 0x120 由 0x301 跳來;會合處 al(1 / 2)與 ah(原值 / 5)都不同,loop 改了 cx
    eq("calls via join", call_args(prog, states, 0x140),
       [(0x139, {"bx": "bx@0xa0", "dx": 0x160, "si": "si@0xa0", "di": "di@0xa0", "bp": "bp@0xa0"})])
    eq("calls none", call_args(prog, states, 0x90), [])
    eq("refs 0x3a", refs(prog, 0x3A), [0x90])
    eq("refs 0xd0", refs(prog, 0xD0), [0xA0])
    xp = explore(fx, [0x117])[0]
    eq("extra entry", (xp.entries.get(0x117), [xp.insns[a].mnemonic for a in range(0x117, 0x11B)]),
       ("--entry", ["nop"] * 4))                       # 走 0x117 .. 0x11a 四個 nop 後接 0x11b 的 00 00
    # 收斂保險:合成檔剛好要處理 96 次(92 條指令,迴圈與會合多算 4 次);95 次要報錯,不能給半套答案。
    # 上限 64 輪是寬裕值:SB16.DIG 實際 1.17 輪、SBPRO2.MDI 1.13 輪(續一百七十三量)。
    eq("budget exact", {a: r.h for a, r in reg_states(prog, 96).items()} == {a: r.h for a, r in states.items()}, True)
    try:
        reg_states(prog, 95)
        fails.append("budget 95: no RuntimeError")
    except RuntimeError:
        pass
    eq("budget default", DATAFLOW_ROUNDS, 64)

    st = Regs()
    st.set("dx", "word[0x63]")
    eq("sym halves", (st.get("dx"), st.get("dl"), st.get("dh")), ("word[0x63]", "lo(word[0x63])", "hi(word[0x63])"))
    st.set("dh", 0)
    eq("sym lo + 0 hi", st.get("dx"), None)
    st.set("dl", "byte[0x48]")
    eq("byte zero-extended", st.get("dx"), "byte[0x48]")
    st.set("dh", 1)
    eq("byte + nonzero hi", st.get("dx"), None)
    st.set("ax", 0x1234)
    eq("const halves", (st.get("ax"), st.get("al"), st.get("ah")), (0x1234, 0x34, 0x12))
    st.set("ax", None)
    eq("cleared", (st.get("al"), st.get("ah")), (None, None))
    st.set("cs", 5)
    eq("segment ignored", st.h.get(("cs", 0)), None)

    if fails:
        for f in fails:
            print("FAIL:", f)
    print("selftest:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


# ---------------------------------------------------------------- CLI

def _load(name: str, game: Path) -> bytes:
    p = Path(name)
    if not p.exists() and p.parent == Path("."):
        p = game / name
    return p.read_bytes()


def main(argv: list[str] | None = None) -> int:
    """命令列進入點。"""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--game", type=Path,
                    default=Path(os.environ.get("FD2_GAME_DIR") or ROOT / "org_game/炎龍騎士團/FLAME2"))
    ap.add_argument("cmd", nargs="?", choices=("header", "disasm", "io", "calls", "refs"))
    ap.add_argument("driver", nargs="?")
    ap.add_argument("addr", nargs="?", type=lambda s: int(s, 0))
    ap.add_argument("--entry", action="append", type=lambda s: int(s, 0), default=[])
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.cmd or not args.driver:
        ap.error("cmd and driver are required unless --selftest")
    if args.cmd in ("calls", "refs") and args.addr is None:
        ap.error(f"{args.cmd} needs an address")
    try:
        b = _load(args.driver, args.game)
        kind, disp = parse_header(b)
    except (OSError, ValueError) as e:
        print(f"FAIL: {args.driver}: {e}")
        return 1
    prog, table, states = explore(b, args.entry)
    if args.cmd == "header":
        print(f"{kind} driver, {len(b):#x} bytes, int 66h dispatcher {disp:#x}")
        for f in table:
            print(f"  function {f.num:#x}  slot {f.slot:#x} -> {f.addr:#x}")
        print(f"reached {sum(i.size for i in prog.insns.values())} / {len(b)} bytes; "
              f"entries {len(prog.entries)}; indirect {len(prog.indirect)}")
    elif args.cmd == "io":
        for s in io_sites(prog, states):
            val = f" <- {_fmt(s.value)}" if s.op == "out" else ""
            print(f"{s.addr:#06x} {s.op:3s} port {_fmt(s.port)}{val}   [entry {s.entry:#x}]{_table_hint(b, s.port)}")
    elif args.cmd == "calls":
        for a, regs in call_args(prog, states, args.addr):
            print(f"{a:#06x} call {args.addr:#x}  " + " ".join(f"{r}={_fmt(v)}" for r, v in regs.items()))
    elif args.cmd == "refs":
        for a in refs(prog, args.addr):
            i = prog.insns[a]
            print(f"{a:#06x} {i.mnemonic} {i.op_str}   [entry {_entry_of(prog, a):#x}]")
    else:
        io = {s.addr: s for s in io_sites(prog, states)}
        prev_end = None
        for a in sorted(prog.insns):
            i = prog.insns[a]
            if a != prev_end:
                print()
            if a in prog.entries:
                print(f"; ---- {a:#x}: {prog.entries[a]}")
            note = ""
            if a in io:
                s = io[a]
                note = f"   ; port {_fmt(s.port)}" + (f" <- {_fmt(s.value)}" if s.op == "out" else "")
            if a in prog.indirect:
                note = f"   ; indirect: {prog.indirect[a]}"
            print(f"{a:#06x}  {i.bytes.hex():<14s} {i.mnemonic} {i.op_str}{note}")
            prev_end = a + i.size
        print("\n; unreached byte ranges [start, end):")
        for s, e in gaps(prog):
            print(f";   {s:#06x} .. {e:#06x} ({e - s} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
