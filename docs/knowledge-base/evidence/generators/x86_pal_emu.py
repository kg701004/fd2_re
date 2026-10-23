"""極小的 x86-32 直譯器:直接執行原版 FD2.EXE 調色盤函式的位元組,記錄 `out 0x3c8 / 0x3c9`(續一百五十)。

只實作 0x2df01 / 0x11df2 / 0x11d40(與它們呼叫的 0x3702f、0x37ae5、共用的收尾)用到的指令;
遇到沒實作的指令、讀到沒初始化的記憶體、堆疊不平衡或步數超過上限都直接 raise,不會悄悄略過。
位元組取自 `disasm_le.object_bytes`(未套 LE fixup):`[0x3a65]` 就是線性 `[0x53a65]` 的調色盤指標。
0x37042(Watcom 堆疊檢查)以 ret 代替。這是模擬(SIMULATED),不是實機。
"""
from __future__ import annotations

import struct

import capstone
from capstone import x86

from disasm_le import object_bytes

PAL_PTR_VAR = 0x3A65          # 未套 fixup 的 [0x53a65]
PAL_BASE = 0x700000           # 調色盤放在這裡(任意、不與程式碼重疊)
STACK_TOP = 0x800000
RET_SENTINEL = 0xDEAD0000
CHK_STUB = 0x37042            # Watcom 堆疊檢查
STEP_LIMIT = 2_000_000
M32 = 0xFFFFFFFF
_JCC = ("jl", "jge", "jg", "jle", "je", "jne")
_DECODED: dict[tuple, tuple] = {}     # (eip, patches) -> 解碼結果;EXE 固定(md5 由呼叫端檢查)


def s32(v: int) -> int:
    """32 位元無號值轉有號。"""
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


class Emu:
    """一次呼叫用的機器狀態。

    Args:
        exe: FD2.EXE 全檔位元組。
        le: `le_xref.parse_le(exe)` 的結果。
        pal: 768 byte 的 6-bit 調色盤(放在 `[0x53a65]` 指的位置)。
        patches: {線性位址: 位元組} —— 故障注入用,只改直譯器讀到的位元組,不改檔案。
    """

    def __init__(self, exe: bytes, le, pal: bytes, patches: dict[int, bytes] | None = None) -> None:
        assert len(pal) == 768, len(pal)
        self.exe, self.le = exe, le
        self.r = {k: 0 for k in ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")}
        self.mem: dict[int, int] = {PAL_BASE + i: b for i, b in enumerate(pal)}
        self.w32(PAL_PTR_VAR, PAL_BASE)
        self.r["esp"] = STACK_TOP
        self.patches = patches or {}
        self.out: list[tuple[int, int]] = []
        self.flags = {"zf": 0, "sf": 0, "of": 0, "cf": 0}
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.cs.detail = True
        self.pkey = tuple(sorted(self.patches.items()))
        self.steps = 0

    # --- 記憶體 ---
    def r8(self, a: int) -> int:
        if a not in self.mem:
            raise RuntimeError(f"讀未初始化位址 {a:#x}")
        return self.mem[a]

    def r32(self, a: int) -> int:
        return struct.unpack("<I", bytes(self.r8(a + i) for i in range(4)))[0]

    def w32(self, a: int, v: int) -> None:
        for i, b in enumerate(struct.pack("<I", v & M32)):
            self.mem[a + i] = b

    def push(self, v: int) -> None:
        self.r["esp"] = (self.r["esp"] - 4) & M32
        self.w32(self.r["esp"], v)

    def pop(self) -> int:
        v = self.r32(self.r["esp"])
        self.r["esp"] = (self.r["esp"] + 4) & M32
        return v

    # --- 運算元 ---
    def getreg(self, name: str) -> int:
        if name in self.r:
            return self.r[name]
        if name in ("al", "bl", "cl", "dl"):
            return self.r["e" + name[0] + "x"] & 0xFF
        if name == "dx":
            return self.r["edx"] & 0xFFFF
        raise NotImplementedError(name)

    def setreg(self, name: str, v: int) -> None:
        if name in self.r:
            self.r[name] = v & M32
        elif name in ("al", "bl", "cl", "dl"):          # 只改低 8 位元
            k = "e" + name[0] + "x"
            self.r[k] = (self.r[k] & 0xFFFFFF00) | (v & 0xFF)
        else:
            raise NotImplementedError(name)

    def addr(self, op: tuple) -> int:
        _, base, index, scale, disp, _ = op
        a = disp
        if base:
            a += self.getreg(base)
        if index:
            a += self.getreg(index) * scale
        return a & M32

    def get(self, op: tuple) -> int:
        if op[0] == "r":
            return self.getreg(op[1])
        if op[0] == "i":
            return op[1] & M32
        a = self.addr(op)
        if op[5] == 1:
            return self.r8(a)
        if op[5] == 4:
            return self.r32(a)
        raise NotImplementedError(op)

    def put(self, op: tuple, v: int) -> None:
        if op[0] == "r":
            self.setreg(op[1], v)
        elif op[0] == "m" and op[5] == 4:
            self.w32(self.addr(op), v)
        else:
            raise NotImplementedError(op)

    def _sub_flags(self, a: int, b: int) -> int:
        res = (a - b) & M32
        sa, sb, sr = s32(a), s32(b), s32(res)
        self.flags = {"zf": int(res == 0), "sf": int(sr < 0), "cf": int((a & M32) < (b & M32)),
                      "of": int((sa < 0) != (sb < 0) and (sr < 0) != (sa < 0))}
        return res

    def _logic_flags(self, res: int) -> None:
        res &= M32
        self.flags = {"zf": int(res == 0), "sf": int(s32(res) < 0), "cf": 0, "of": 0}

    def cond(self, mn: str) -> bool:
        f = self.flags
        return {"jl": f["sf"] != f["of"], "jge": f["sf"] == f["of"],
                "jg": f["zf"] == 0 and f["sf"] == f["of"], "jle": f["zf"] == 1 or f["sf"] != f["of"],
                "je": f["zf"] == 1, "jne": f["zf"] == 0}[mn]

    # --- 執行 ---
    def fetch(self, eip: int) -> tuple:
        """解碼 eip 那一條指令成 (mnemonic, size, 運算元...);依 patches 分開快取(只解碼一次)。"""
        key = (eip, self.pkey)
        if key not in _DECODED:
            raw = bytearray(object_bytes(self.exe, self.le, eip, 16))
            for pa, pb in self.patches.items():
                for i, b in enumerate(pb):
                    if 0 <= pa + i - eip < len(raw):
                        raw[pa + i - eip] = b
            ins = next(self.cs.disasm(bytes(raw), eip))
            ops = []
            for op in ins.operands:
                if op.type == x86.X86_OP_REG:
                    ops.append(("r", self.cs.reg_name(op.reg)))
                elif op.type == x86.X86_OP_IMM:
                    ops.append(("i", op.imm))
                elif op.type == x86.X86_OP_MEM:
                    m = op.mem
                    assert m.segment == 0
                    ops.append(("m", self.cs.reg_name(m.base) if m.base else None,
                                self.cs.reg_name(m.index) if m.index else None, m.scale, m.disp, op.size))
                else:
                    raise NotImplementedError(op.type)
            _DECODED[key] = (ins.mnemonic, ins.size, tuple(ops), ins.op_str)
        return _DECODED[key]

    def call(self, fn: int, args: list[int]) -> None:
        """以 cdecl 呼叫 fn(args),跑到它 ret 回來。"""
        for a in reversed(args):
            self.push(a)
        self.push(RET_SENTINEL)
        eip = fn
        while eip != RET_SENTINEL:
            if eip == CHK_STUB:
                eip = self.pop()
                continue
            self.steps += 1
            if self.steps > STEP_LIMIT:
                raise RuntimeError("步數超過上限")
            mn, size, ops, op_str = self.fetch(eip)
            nxt = eip + size
            if mn == "push":
                self.push(self.get(ops[0]))
            elif mn == "pop":
                self.put(ops[0], self.pop())
            elif mn in ("mov", "movzx"):
                self.put(ops[0], self.get(ops[1]))
            elif mn == "xchg":
                a, b = self.get(ops[0]), self.get(ops[1])
                self.put(ops[0], b)
                self.put(ops[1], a)
            elif mn == "add":
                a, b = self.get(ops[0]), self.get(ops[1])
                res = (a + b) & M32
                sa, sb, sr = s32(a), s32(b), s32(res)
                self.flags = {"zf": int(res == 0), "sf": int(sr < 0), "cf": int(a + b > M32),
                              "of": int((sa < 0) == (sb < 0) and (sr < 0) != (sa < 0))}
                self.put(ops[0], res)
            elif mn in ("sub", "cmp"):
                res = self._sub_flags(self.get(ops[0]), self.get(ops[1]))
                if mn == "sub":
                    self.put(ops[0], res)
            elif mn == "inc":
                a = self.get(ops[0])
                res = (a + 1) & M32
                self.flags = {"zf": int(res == 0), "sf": int(s32(res) < 0), "cf": self.flags["cf"],
                              "of": int(a == 0x7FFFFFFF)}
                self.put(ops[0], res)
            elif mn in ("xor", "test"):
                res = self.get(ops[0]) ^ self.get(ops[1]) if mn == "xor" else self.get(ops[0]) & self.get(ops[1])
                self._logic_flags(res)
                if mn == "xor":
                    self.put(ops[0], res)
            elif mn == "shl":
                res = (self.get(ops[0]) << self.get(ops[1])) & M32
                self._logic_flags(res)
                self.put(ops[0], res)
            elif mn == "sar":
                res = (s32(self.get(ops[0])) >> self.get(ops[1])) & M32
                self._logic_flags(res)
                self.put(ops[0], res)
            elif mn == "imul" and len(ops) == 2:
                self.put(ops[0], s32(self.get(ops[0])) * s32(self.get(ops[1])))
            elif mn == "idiv":
                num = self.r["edx"] << 32 | self.r["eax"]          # 先當無號 64 位元,再轉有號
                num = num - (1 << 64) if num & (1 << 63) else num
                d = s32(self.get(ops[0]))
                q = abs(num) // abs(d) * (1 if (num < 0) == (d < 0) else -1)   # 向 0 截斷
                self.r["eax"], self.r["edx"] = q & M32, (num - q * d) & M32
            elif mn == "out":
                assert ops == (("r", "dx"), ("r", "al")), ops
                self.out.append((self.r["edx"] & 0xFFFF, self.r["eax"] & 0xFF))
            elif mn == "call":
                self.push(nxt)
                nxt = ops[0][1]
            elif mn == "ret":
                nxt = self.pop()
                if ops:
                    self.r["esp"] = (self.r["esp"] + ops[0][1]) & M32
            elif mn == "jmp":
                nxt = ops[0][1]
            elif mn in _JCC:
                if self.cond(mn):
                    nxt = ops[0][1]
            else:
                raise NotImplementedError(f"{eip:#x} {mn} {op_str}")
            eip = nxt
        if self.r["esp"] != STACK_TOP - 4 * len(args):
            raise RuntimeError("堆疊不平衡")
        self.r["esp"] = STACK_TOP


def dac_writes(out: list[tuple[int, int]]) -> dict[int, tuple[int, int, int]]:
    """把 out 序列解讀成 DAC 寫入:0x3c8 設索引,之後每 3 個 0x3c9 寫一組並自動加 1。

    Raises:
        AssertionError: RGB 寫到一半換索引、同一次呼叫寫同一索引兩次、或出現別的埠。
    """
    res: dict[int, tuple[int, int, int]] = {}
    idx, buf = None, []
    for port, v in out:
        if port == 0x3C8:
            assert not buf, "RGB 寫到一半就換索引"
            idx = v
        else:
            assert port == 0x3C9 and idx is not None, (hex(port), idx)
            buf.append(v)
            if len(buf) == 3:
                assert idx not in res, f"索引 {idx} 寫兩次"
                res[idx] = (buf[0], buf[1], buf[2])
                buf, idx = [], (idx + 1) & 0xFF
    assert not buf
    return res


def run(exe: bytes, le, fn: int, args: list[int], pal: bytes,
        patches: dict[int, bytes] | None = None) -> dict[int, tuple[int, int, int]]:
    """執行 fn(args) 一次,回傳 {DAC 索引: (R, G, B)}。"""
    e = Emu(exe, le, pal, patches)
    e.call(fn, args)
    return dac_writes(e.out)
