#!/usr/bin/env python3
"""watcom_lib_match.py —— 拿 Watcom 函式庫的目的碼比對 FD2.EXE,替執行期區的函式找回原始符號名。

為什麼有這支
------------
FD2.EXE 的 obj1 後段(約 0x3702f 起)是 Watcom C 執行期函式庫、數學函式庫、浮點模擬器與 AIL。
`function_inventory.py` 把它們列成入口,但大多沒有名字;人讀 CRT 函式划不來,它們的名字本來就在
函式庫的 OMF 目的碼裡。

比對來源與版本落差(實測)
--------------------------
FD2 的 CRT 版權字串是 `WATCOM C/C++32 Run-Time system ... 1988-1993`(Watcom 9.5/10.0);能合法取得的
最舊版本是 open-watcom 官方 GitHub 釋出的 **Watcom 11.0c**(`open-watcom-1.9` repo 的 `w11.0c-zips`,
`clib_d32.zip` + `clib_a32.zip`)。授權條款不允許散布,所以函式庫檔**不進 repo**,放在 repo 外
(`--lib-dir`,預設 `~/fd2-watcom-libs/w11.0c/lib386`),產物只記 sha256。
新了約五年,**逐位元組比對幾乎全滅**(clib3s 979 個模組只有 13 個唯一命中,都很短;`memset` 只有前 12 bytes
相同),所以改在**指令層**比:

* 每條指令正規化成 token:分支目標換 `L`、`call` 一律 `call F`(兩邊的被呼叫者位址不可比)、
  被 fixup 蓋到的指令其數值換 `X`、其他 >= 0x1000 的常數換 `X`(多半是位址或位移)。
* 函式庫端以 OMF 的 PUBDEF 切函式(公開符號到下一個公開符號);FD2 端以清單入口與 `span_upper` 切。
* 相似度是 `difflib.SequenceMatcher` 的 ratio。

判定(`assign`)
---------------
* **本體(`via=body`)**:最佳 ratio >= `T_HI`、token 數 >= `MIN_TOK`,而且在差 `MARGIN` 以內沒有**不同名稱**
  的對手。對齊得上的 `call` 拿來當**一致性**:函式庫在該處呼叫的外部符號,與 FD2 該處呼叫的目標**已經被認定的名稱**
  比 —— 不一致(`conflict`)的候選直接淘汰;接近同分的候選以一致數(`agree`)決勝。依 token 數由長到短處理
  (長函式證據多,先定下來給短的包裝函式當一致性)。
* **被呼叫者(`via=callee`)**:已認定的函式在對齊位置呼叫外部符號 S,FD2 該處 call 的目標若是清單入口、
  所有隱含都指向同一個 S、而且沒有本體判定 → 名稱 S。同一個目標被不同呼叫端隱含成不同名稱就不命名
  (實測 0x4a314:新版把一個錯誤處理拆成 `F8InvalidOp`/`F8DivZero`/`F8OverFlow`)。
* 反覆到不動點。最後再整體驗一次:每一筆認定的每個對齊 call 都不得與目標的認定名稱衝突。

門檻來自零假設:**遊戲區**(`NULL_REGION`,遊戲本體一定不是函式庫)的入口對全部函式庫函式的最佳 ratio,
token >= 3 時最高 0.75、>= 16 時最高 0.686(2026-10-06 實測,565 個)。`T_HI = 0.8` 高於全部。
遊戲區也參加比對,任何名稱落進去都算假陽性(selftest 要求 0)。

誠實邊界
--------
* 只命名 11.0c 與 1993 版**仍然相像**的函式。改寫過的函式(實測多數)比不到,不代表不是函式庫。
* 別名組:token 與呼叫名稱完全相同的函式庫函式(例:16 個 math387 三角函式的進入樁)無法區分,
  一致性也救不回來時記成 `a|b|...`,不當單一名稱用。
* 名稱是 11.0c 的符號名;舊版同一位置的函式可能叫別的名字(實測一致的見 selftest 的對照組)。

用法
----
    python tools/watcom_lib_match.py docs/data/watcom_lib_matches.json
    python tools/watcom_lib_match.py --report            # 依位址列出認定結果與無描述入口的命中
    python tools/watcom_lib_match.py --selftest
"""
from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import json
import os
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
INVENTORY_JSON = ROOT / "docs" / "data" / "function_inventory.json"
DEFAULT_LIB_DIR = Path(os.environ.get("FD2_WATCOM_LIBS", Path.home() / "fd2-watcom-libs" / "w11.0c" / "lib386"))
SOURCE = "https://github.com/open-watcom/open-watcom-1.9/releases/tag/w11.0c-zips (clib_d32.zip, clib_a32.zip)"
# FD2 以 `push imm32 ; call __STK` 起頭 = 堆疊呼叫慣例(-3s),所以用 *3s / *387s 版本
LIBS = ("dos/clib3s.lib", "math3s.lib", "math387s.lib", "dos/emu387.lib")

T_HI = 0.8
T_LO = 0.6          # 第二級:要有 AGREE_MIN 個一致的對齊 call
AGREE_MIN = 1
MIN_TOK = 8
MARGIN = 0.05
CAND_MIN = 0.5
MAX_BODY = 8192
NULL_REGION = (0x10100, 0x3702F)     # 遊戲本體(cstart 在 0x10000,函式庫從 __STK 0x3702f 起)
LOC_SIZE = {0: 1, 1: 2, 2: 2, 3: 4, 4: 1, 5: 2, 9: 4, 11: 6, 13: 4}
HEXN = re.compile(r"0x[0-9a-f]+|\b\d+\b")
BRANCH = re.compile(r"^(?:j[a-z]+|loop[a-z]*)$")


# --------------------------------------------------------------------------- #
# OMF 函式庫解析
# --------------------------------------------------------------------------- #
@dataclass
class Module:
    """一個 OMF 模組:段、公開符號、外部符號、各段資料與 fixup。"""
    name: str
    lnames: list = field(default_factory=lambda: [None])
    segs: list = field(default_factory=lambda: [None])
    ext: list = field(default_factory=lambda: [None])
    pub: list = field(default_factory=list)          # (名稱, 段索引, 偏移)
    data: dict = field(default_factory=dict)         # 段索引 -> bytearray
    fix: list = field(default_factory=list)          # {"seg","at","loc","selfrel","tm","tdat","disp"}
    bak: list = field(default_factory=list)          # (段索引, 偏移, 大小)


class _Rd:
    def __init__(self, b: bytes) -> None:
        self.b, self.i = b, 0

    def u8(self) -> int:
        self.i += 1
        return self.b[self.i - 1]

    def u16(self) -> int:
        self.i += 2
        return struct.unpack_from("<H", self.b, self.i - 2)[0]

    def off(self, big: int) -> int:
        n = 4 if big else 2
        self.i += n
        return int.from_bytes(self.b[self.i - n:self.i], "little")

    def idx(self) -> int:
        v = self.u8()
        return ((v & 0x7F) << 8) | self.u8() if v & 0x80 else v

    def name(self) -> str:
        n = self.u8()
        self.i += n
        return self.b[self.i - n:self.i].decode("latin-1")

    def more(self) -> bool:
        return self.i < len(self.b)


def _put(m: Module, seg: int, at: int, d: bytes) -> None:
    buf = m.data.setdefault(seg, bytearray())
    if len(buf) < at + len(d):
        buf.extend(bytes(at + len(d) - len(buf)))
    buf[at:at + len(d)] = d


def parse_omf(raw: bytes) -> list[Module]:
    """解析 OMF 目的檔或函式庫(`F0` 開頭時依頁面大小對齊模組)。只取比對需要的記錄型別。"""
    mods: list[Module] = []
    page = struct.unpack_from("<H", raw, 1)[0] + 3 if raw[:1] == b"\xF0" else 0
    pos = page
    cur: Module | None = None
    last = (0, 0)
    while pos + 3 <= len(raw):
        t = raw[pos]
        ln = struct.unpack_from("<H", raw, pos + 1)[0]
        body = raw[pos + 3:pos + 2 + ln]            # 去掉 checksum
        pos += 3 + ln
        if t == 0xF1:
            break
        if t == 0x80:
            cur = Module(_Rd(body).name())
            continue
        if cur is None:
            continue
        r, big = _Rd(body), t & 1
        if t == 0x96:
            while r.more():
                cur.lnames.append(r.name())
        elif t in (0x98, 0x99):
            acbp = r.u8()
            if acbp >> 5 == 0:
                r.u16()
                r.u8()
            size = r.off(big)
            sn, cn = r.idx(), r.idx()
            cur.segs.append({"name": cur.lnames[sn], "class": cur.lnames[cn], "size": size})
        elif t in (0x8C, 0xB4):
            while r.more():
                cur.ext.append(r.name())
                r.idx()
        elif t in (0xB0, 0xB8):
            while r.more():
                cur.ext.append(r.name())
                r.idx()
                kinds = 2 if r.u8() == 0x61 else 1
                for _ in range(kinds):
                    v = r.u8()
                    if v > 0x80:
                        r.i += {0x81: 2, 0x84: 3, 0x88: 4}[v]
        elif t in (0x90, 0x91, 0xB6, 0xB7):
            r.idx()
            sg = r.idx()
            if sg == 0:
                r.u16()
            while r.more():
                n = r.name()
                o = r.off(big)
                r.idx()
                cur.pub.append((n, sg, o))
        elif t in (0xA0, 0xA1):
            sg = r.idx()
            o = r.off(big)
            _put(cur, sg, o, body[r.i:])
            last = (sg, o)
        elif t in (0xA2, 0xA3):
            sg = r.idx()
            o = r.off(big)

            def blk() -> bytes:
                rep, cnt = r.off(big), r.u16()
                if cnt == 0:
                    n = r.u8()
                    r.i += n
                    return r.b[r.i - n:r.i] * rep
                return b"".join(blk() for _ in range(cnt)) * rep
            d = b""
            while r.more():
                d += blk()
            _put(cur, sg, o, d)
            last = (sg, o)
        elif t in (0x9C, 0x9D):
            thr: dict[str, dict[int, tuple[int, int | None]]] = {"F": {}, "T": {}}
            while r.more():
                b0 = r.u8()
                if not b0 & 0x80:                       # THREAD 子記錄
                    d, meth, num = (b0 >> 6) & 1, (b0 >> 2) & 7, b0 & 3
                    datum = r.idx() if (meth < 3 if d else meth < 4) else None
                    thr["F" if d else "T"][num] = (meth, datum)
                    continue
                at = ((b0 & 3) << 8) | r.u8()
                fd = r.u8()
                if not fd & 0x80:
                    fm = (fd >> 4) & 7
                    if fm < 3:
                        r.idx()
                if fd & 0x08:
                    tm, tdat = thr["T"][fd & 3]
                else:
                    tm, tdat = fd & 3, r.idx()
                disp = 0 if fd & 4 else r.off(big)
                cur.fix.append({"seg": last[0], "at": last[1] + at, "loc": (b0 >> 2) & 15,
                                "selfrel": not (b0 >> 6) & 1, "tm": tm & 3, "tdat": tdat, "disp": disp})
        elif t in (0xB2, 0xB3):
            sg = r.idx()
            n = {0: 1, 1: 2, 2: 4}.get(r.u8(), 4)
            while r.more():
                o = r.off(big)
                r.off(big)
                cur.bak.append((sg, o, n))
        elif t in (0x8A, 0x8B):
            mods.append(cur)
            cur = None
            if page:
                pos = (pos + page - 1) // page * page
    return mods


# --------------------------------------------------------------------------- #
# 指令 token
# --------------------------------------------------------------------------- #
def norm(mn: str, op: str, wild: bool) -> str:
    """一條指令的 token。call 不帶目標;分支目標換 L;fixup 蓋到的數值與大常數換 X。"""
    mn = mn.split()[-1] if mn.split() and mn.split()[0] in ("notrack",) else mn
    if mn == "call":
        return "call F"
    if BRANCH.match(mn) and HEXN.fullmatch(op):
        return mn + " L"
    if wild:
        return mn + " " + HEXN.sub("X", op)
    return mn + " " + HEXN.sub(lambda m: m.group(0) if int(m.group(0), 0) < 0x1000 else "X", op)


def tokenize(insns, start: int, length: int, wild, target_of) -> list[tuple[str, object]]:
    """[(token, 轉移目標)]。`insns` 是 (位址, 大小, 助記符, 運算元) 的序列;`target_of` 給 call/jmp 的目標
    (函式庫端是符號名,FD2 端是位址;不知道為 None)。解到 `start+length` 為止。"""
    out = []
    for a, size, mn, op in insns:
        o = a - start
        if o >= length:
            break
        w = any(wild[k] for k in range(o, min(o + size, length)))
        tgt = target_of(a, size, mn, op) if mn in ("call", "jmp") else None
        out.append((norm(mn, op, w), tgt))
    return out


def _cs():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    return Cs(CS_ARCH_X86, CS_MODE_32)


def _insns(md, buf: bytes, addr: int):
    return ((i.address, i.size, i.mnemonic, i.op_str) for i in md.disasm(bytes(buf), addr))


def reach_insns(md, buf: bytes, addr: int) -> list[tuple[int, int, str, str]]:
    """從 `addr` 沿控制流走得到、而且落在 `buf` 範圍內的指令,依位址排序(call 不跟進,繼續往下)。
    範圍內走不到的位元組(別的函式共用的尾段、資料)不算進這個函式 —— 兩邊都這樣切,才比得起來。"""
    end = addr + len(buf)
    seen: dict[int, tuple[int, int, str, str]] = {}
    work = [addr]
    while work:
        a = work.pop()
        if a in seen or not addr <= a < end:
            continue
        ins = next(md.disasm(bytes(buf[a - addr:a - addr + 15]), a, 1), None)
        if ins is None:
            continue
        seen[a] = (a, ins.size, ins.mnemonic, ins.op_str)
        mn = ins.mnemonic.split()[-1]
        nxt = a + ins.size
        if mn in ("ret", "retf", "iret", "iretd", "hlt"):
            continue
        if BRANCH.match(mn) and HEXN.fullmatch(ins.op_str):
            work.append(int(ins.op_str, 16))
            if mn == "jmp":
                continue
        elif mn == "jmp":
            continue                                    # 間接 jmp:不知道去哪,停
        work.append(nxt)
    return [seen[a] for a in sorted(seen)]


@dataclass
class Fn:
    """一個比對單位。lib 端 `key` 是符號名,FD2 端是位址。"""
    key: object
    tc: list
    lib: str = ""
    module: str = ""

    @property
    def toks(self) -> list[str]:
        return [t for t, _ in self.tc]


def lib_functions(mods: list[Module], libname: str, md=None) -> list[Fn]:
    """CODE 類段裡,每個公開符號到下一個公開符號(或段尾)是一個函式。"""
    md = md or _cs()
    out = []
    for m in mods:
        for si, s in enumerate(m.segs):
            if not s or s["class"].upper() != "CODE" or not m.data.get(si):
                continue
            b = bytes(m.data[si])
            wild = bytearray(len(b))
            tgt: dict[int, object] = {}
            for f in m.fix:
                if f["seg"] != si:
                    continue
                for k in range(LOC_SIZE.get(f["loc"], 4)):
                    if f["at"] + k < len(b):
                        wild[f["at"] + k] = 1
                if f["tm"] == 2:
                    tgt[f["at"]] = m.ext[f["tdat"]]
                elif f["tm"] == 0 and f["tdat"] == si:
                    tgt[f["at"]] = ("local", f["disp"])
            for sg, o, n in m.bak:
                if sg == si:
                    for k in range(n):
                        if o + k < len(b):
                            wild[o + k] = 1
            def raw_target(a: int, size: int, op: str) -> object:
                t = tgt.get(a + size - 4) if size >= 5 else None
                if isinstance(t, tuple):
                    return t[1]
                if t is None and HEXN.fullmatch(op):
                    return int(op, 16)                  # 模組內已解析的直接轉移
                return t
            # 切點:公開符號,加上模組內 call 的目標(static 函式,沒有名字,記成「模組+偏移」)。
            # 不切的話 static 會黏在前一個公開函式後面(實測 __FLDD 本體帶著 ___LDD 之前的兩段 static)。
            local = {o: n for n, sg, o in m.pub if sg == si}
            # 段首在第一個公開符號之前的程式碼也是 static(實測 stk 模組 +0x0 是 XI 初始化:存 SS)
            local.setdefault(0, f"{m.name}+0x0")
            for a, size, mn, op in _insns(md, b, 0):
                t = raw_target(a, size, op) if mn == "call" else None
                if isinstance(t, int) and 0 <= t < len(b) and t not in local:
                    local[t] = f"{m.name}+{t:#x}"

            def target_of(a: int, size: int, mn: str, op: str) -> str | None:
                t = raw_target(a, size, op)
                return local.get(t) if isinstance(t, int) else t
            cuts = sorted(local)
            for i, o in enumerate(cuts):
                end = cuts[i + 1] if i + 1 < len(cuts) else len(b)
                if end > o:
                    tc = tokenize(reach_insns(md, b[o:end], o), o, end - o, wild[o:end], target_of)
                    out.append(Fn(local[o], tc, libname, m.name))
    return out


def is_static(name: str) -> bool:
    """`模組+0x偏移`:函式庫模組內的 static 函式(Watcom 符號名不含 `+`)。"""
    return "+" in name


def fd2_functions(entries: list[dict], code: bytes, base: int, fixups: dict[int, int], md=None) -> list[Fn]:
    md = md or _cs()
    fx_bytes = {s + k for s in fixups for k in range(4)}
    out = []
    for e in entries:
        a = int(e["addr"], 16)
        n = min(e["span_upper"], MAX_BODY)
        wild = [1 if a + k in fx_bytes else 0 for k in range(n)]

        def target_of(x: int, size: int, mn: str, op: str) -> int | None:
            return int(op, 16) if HEXN.fullmatch(op) else None
        tc = tokenize(reach_insns(md, code[a - base:a - base + n], a), a, n, wild, target_of)
        out.append(Fn(a, tc))
    return out


# --------------------------------------------------------------------------- #
# 判定
# --------------------------------------------------------------------------- #
def similar(a: list[str], b: list[str]) -> difflib.SequenceMatcher | None:
    la, lb = len(a), len(b)
    if la < 3 or lb < la * 0.5 or lb > la * 2:
        return None
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < CAND_MIN or sm.quick_ratio() < CAND_MIN:
        return None
    return sm


def aligned_calls(sm: difflib.SequenceMatcher, lib: Fn, fd: Fn) -> list[tuple[str, int]]:
    """對齊相等區塊裡,兩邊都有目標的 call/jmp:(函式庫符號, FD2 目標位址)。"""
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                lt, lc = lib.tc[i1 + k]
                gt, gc = fd.tc[j1 + k]
                if (lt.startswith("call") or lt.startswith("jmp")) and isinstance(lc, str) and gc is not None:
                    out.append((lc, gc))
    return out


def name_set(v: str) -> set[str]:
    return set(v.split("|"))


def consistency(lib_fn: Fn, sm: difflib.SequenceMatcher, g: Fn, got: dict[int, dict]) -> tuple[int, int]:
    """(一致數, 衝突數):對齊 call 的函式庫符號 vs FD2 目標已認定的名稱。"""
    agree = conflict = 0
    for lc, gc in aligned_calls(sm, lib_fn, g):
        if gc in got:
            if lc in name_set(got[gc]["name"]):
                agree += 1
            else:
                conflict += 1
    return agree, conflict


def body_rank(lib: list[Fn], g: Fn, name: str) -> tuple[bool, float]:
    """`name` 是不是 g 本體**嚴格**最像的函式庫函式(不套長度過濾;同分的別名不同名就不算)。"""
    best: dict[str, float] = {}
    for f in lib:
        r = difflib.SequenceMatcher(None, f.toks, g.toks, autojunk=False).ratio()
        best[f.key] = max(best.get(f.key, 0.0), r)
    mine = best.get(name, 0.0)
    return all(r < mine for k, r in best.items() if k != name), mine


def assign(lib: list[Fn], fd: list[Fn], entries: set[int], stats: dict | None = None) -> dict[int, dict]:
    """本體判定(兩級)+ 被呼叫者傳播,到不動點。回傳 {位址: 認定紀錄}。

    `stats` 若給,填入 `top`(每個入口對全部函式庫的最佳 ratio)、`agree_top`(收斂後,有一致數且無衝突的
    最佳 ratio)與 `callee_unconfirmed`(被呼叫者傳播但本體旁證不成立的),給零假設與報表用。
    """
    pairs: dict[int, list[tuple[float, int, difflib.SequenceMatcher]]] = {}
    top: dict[int, float] = {}
    for g in fd:
        c = []
        for i, f in enumerate(lib):
            sm = similar(f.toks, g.toks)
            if sm is not None:
                r = sm.ratio()
                top[g.key] = max(top.get(g.key, 0.0), r)
                c.append((r, i, sm))
        c.sort(key=lambda x: -x[0])
        pairs[g.key] = c
    by_addr = {g.key: g for g in fd}
    got: dict[int, dict] = {}
    used: dict[str, int] = {}                  # 單一名稱 -> 位址(一個符號只能在一個位址)
    unconfirmed: dict[int, dict] = {}
    rank_cache: dict[tuple[int, str], tuple[bool, float]] = {}

    def viable_of(g: Fn) -> list[tuple[float, int, int]]:
        out = []
        for r, i, sm in pairs[g.key]:
            agree, conflict = consistency(lib[i], sm, g, got)
            if conflict == 0 and used.get(lib[i].key, g.key) == g.key:
                out.append((r, agree, i))
        return out

    order = sorted(fd, key=lambda g: -len(g.toks))
    while True:
        changed = False
        for g in order:
            if g.key in got or len(g.toks) < MIN_TOK or not pairs[g.key]:
                continue
            viable = viable_of(g)
            if not viable or viable[0][0] < T_LO:
                continue
            top_r = viable[0][0]
            near = [v for v in viable if v[0] >= top_r - MARGIN]
            best_agree = max(v[1] for v in near)
            win = [v for v in near if v[1] == best_agree]
            names = sorted({lib[i].key for _, _, i in win})
            r, agree, i = win[0]
            # 第二級:ratio 在 [T_LO, T_HI) 要有一致數佐證,而且不能是別名組
            if r < T_HI and (best_agree < AGREE_MIN or len(names) > 1):
                continue
            got[g.key] = {"name": "|".join(names), "via": "body", "tier": 1 if r >= T_HI else 2,
                          "ratio": round(r, 3), "tokens": len(g.toks), "lib": lib[i].lib, "module": lib[i].module,
                          "agree": agree,
                          "rivals": sorted({lib[j].key for rr, _a, j in viable if lib[j].key not in names
                                            and rr >= T_LO - MARGIN})[:5]}
            if len(names) == 1:
                used[names[0]] = g.key
            changed = True
        # 被呼叫者傳播
        implied: dict[int, dict[str, set[int]]] = collections.defaultdict(lambda: collections.defaultdict(set))
        for a, rec in got.items():
            if rec["via"] != "body" or "|" in rec["name"]:
                continue
            for r, i, sm in pairs[a]:
                if lib[i].key == rec["name"]:
                    for lc, gc in aligned_calls(sm, lib[i], by_addr[a]):
                        implied[gc][lc].add(a)
                    break
        for gc, opts in implied.items():
            if gc in got or gc not in entries or gc not in by_addr or len(opts) != 1:
                continue
            (nm, callers), = opts.items()
            if nm in used:
                continue
            # 旁證:被呼叫者本體自己也得最像這個名稱(實測擋下新版改呼叫 `allocate`/`free` 這類版本差異)
            if (gc, nm) not in rank_cache:
                rank_cache[(gc, nm)] = body_rank(lib, by_addr[gc], nm)
            ok, br = rank_cache[(gc, nm)]
            if not ok:
                unconfirmed[gc] = {"name": nm, "callers": sorted(hex(c) for c in callers), "body_ratio": round(br, 3)}
                continue
            unconfirmed.pop(gc, None)
            got[gc] = {"name": nm, "via": "callee", "callers": sorted(hex(c) for c in callers),
                       "body_ratio": round(br, 3)}
            used[nm] = gc
            changed = True
        if not changed:
            break
    if stats is not None:
        stats["top"] = top
        stats["agree_top"] = {g.key: max((r for r, agree, i in viable_of(g) if agree >= AGREE_MIN), default=0.0)
                              for g in fd if len(g.toks) >= MIN_TOK}
        stats["callee_unconfirmed"] = {a: v for a, v in unconfirmed.items() if a not in got}
    return got


def final_conflicts(lib: list[Fn], fd: list[Fn], got: dict[int, dict]) -> list[str]:
    """每一筆本體認定的每個對齊 call,不得與目標的認定名稱衝突。"""
    by_addr = {g.key: g for g in fd}
    out = []
    names = {f.key: [] for f in lib}
    for i, f in enumerate(lib):
        names[f.key].append(i)
    for a, rec in got.items():
        if rec["via"] != "body":
            continue
        for nm in name_set(rec["name"]):
            for i in names.get(nm, []):
                sm = similar(lib[i].toks, by_addr[a].toks)
                if sm is None or round(sm.ratio(), 3) != rec["ratio"]:
                    continue
                for lc, gc in aligned_calls(sm, lib[i], by_addr[a]):
                    if gc in got and lc not in name_set(got[gc]["name"]):
                        out.append(f"{a:#x}={nm} 在對齊處呼叫 {lc},但 {gc:#x} 被認定為 {got[gc]['name']}")
    seen: dict[str, int] = {}
    for a in sorted(got):
        nm = got[a]["name"]
        if "|" not in nm:
            if nm in seen:
                out.append(f"{nm} 同時認定在 {seen[nm]:#x} 與 {a:#x}")
            seen.setdefault(nm, a)
    return out


# --------------------------------------------------------------------------- #
# 組裝
# --------------------------------------------------------------------------- #
def null_hits(got: dict[int, dict], region: tuple[int, int]) -> list[str]:
    """落進零假設區(遊戲本體)的認定;應為空。"""
    return [hex(a) for a in sorted(got) if region[0] <= a < region[1]]


def lib_inputs(lib_dir: Path) -> tuple[list[Fn], dict[str, str]]:
    md = _cs()
    fns: list[Fn] = []
    sha = {}
    for name in LIBS:
        raw = (lib_dir / name).read_bytes()
        sha[name] = hashlib.sha256(raw).hexdigest()
        fns += lib_functions(parse_omf(raw), name.split("/")[-1], md)
    return fns, sha


def build(lib_dir: Path) -> dict:
    import disasm_le as D
    import verify_address_claim_coverage as CC
    data, meta, code, base, hi = CC.load_image()
    fixups = D.build_fixups(data, meta)
    inv = json.loads(INVENTORY_JSON.read_text(encoding="utf-8"))
    entries = [e for e in inv["entries"] if int(e["addr"], 16) >= NULL_REGION[0]]
    lib, sha = lib_inputs(lib_dir)
    fd = fd2_functions(entries, code, base, fixups)
    stats: dict = {}
    got = assign(lib, fd, {int(e["addr"], 16) for e in entries}, stats)

    def null_max(d: dict[int, float]) -> float:
        return round(max((r for g in fd if NULL_REGION[0] <= g.key < NULL_REGION[1] and len(g.toks) >= MIN_TOK
                          for r in [d.get(g.key, 0.0)]), default=0.0), 3)
    n_null = sum(1 for e in entries if NULL_REGION[0] <= int(e["addr"], 16) < NULL_REGION[1])
    return {
        "_meta": {
            "source": SOURCE, "libs_sha256": sha, "lib_functions": len(lib), "fd2_entries_compared": len(fd),
            "thresholds": {"T_HI": T_HI, "T_LO": T_LO, "AGREE_MIN": AGREE_MIN, "MIN_TOK": MIN_TOK, "MARGIN": MARGIN},
            "null_region": [hex(x) for x in NULL_REGION], "null_entries": n_null,
            "names_in_null_region": null_hits(got, NULL_REGION),
            # 零假設:遊戲區入口的最佳 ratio(第一級門檻要高於它)與「有一致數佐證」的最佳 ratio(第二級要高於它)
            "null_best_ratio_max": null_max(stats["top"]),
            "null_best_ratio_with_agree_max": null_max(stats["agree_top"]),
            "final_conflicts": final_conflicts(lib, fd, got),
            "matched": len(got), "by_via": dict(collections.Counter(r["via"] for r in got.values())),
            "body_tier2": sum(1 for r in got.values() if r.get("tier") == 2),
            "ambiguous_alias": sum(1 for r in got.values() if "|" in r["name"]),
            "callee_unconfirmed": {hex(a): v for a, v in sorted(stats["callee_unconfirmed"].items())},
        },
        "matches": {hex(a): got[a] for a in sorted(got)},
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def report(doc: dict) -> int:
    import function_inventory as FI
    names = FI.real_names()
    m = doc["_meta"]
    print(f"認定 {m['matched']}({m['by_via']},別名組 {m['ambiguous_alias']});遊戲區落點 {m['names_in_null_region']};"
          f"最終衝突 {len(m['final_conflicts'])}")
    for a, r in doc["matches"].items():
        have = names.get(int(a, 16), "")
        extra = f"r={r['ratio']} tok={r['tokens']} agree={r['agree']}" if r["via"] == "body" else f"呼叫端 {r['callers']}"
        print(f"  {a} {r['name']:<28} {r['via']:<6} {extra}   {('現名 ' + have) if have else ''}")
    return 0


# --------------------------------------------------------------------------- #
# 自我測試
# --------------------------------------------------------------------------- #
def _rec(t: int, body: bytes) -> bytes:
    b = body + b"\0"
    return bytes([t]) + struct.pack("<H", len(b)) + b


def _str(s: str) -> bytes:
    return bytes([len(s)]) + s.encode()


def synthetic_lib() -> bytes:
    """兩個模組的 OMF 函式庫:A 有兩個公開函式(foo 經 EXTDEF 呼叫 bar),B 定義 bar。
    fixup 用一個 THREAD + 一個顯式,另有一筆 LIDATA。"""
    def module(name: str, code: bytes, pubs: list[tuple[str, int]], exts: list[str], fixes: bytes,
               lidata: bytes = b"") -> bytes:
        out = _rec(0x80, _str(name))
        out += _rec(0x96, _str("") + _str("_TEXT") + _str("CODE"))
        # ACBP 0x69 = 段落對齊、public、use32;段名 _TEXT(2)、類別 CODE(3)、overlay(1)
        out += _rec(0x99, b"\x69" + struct.pack("<I", len(code)) + b"\x02\x03\x01")
        if exts:
            out += _rec(0x8C, b"".join(_str(e) + b"\0" for e in exts))
        out += _rec(0x91, b"\0\x01" + b"".join(_str(n) + struct.pack("<I", o) + b"\0" for n, o in pubs))
        out += _rec(0xA1, b"\x01" + struct.pack("<I", 0) + code)
        if fixes:
            out += _rec(0x9D, fixes)
        if lidata:
            out += _rec(0xA3, b"\x01" + struct.pack("<I", len(code)) + lidata)
        return out + _rec(0x8B, b"\0")
    # A:foo = push ebp; call bar(rel32, 外部); pop ebp; ret / baz = xor eax,eax; ret
    code_a = b"\x55\xE8\0\0\0\0\x5D\xC3" + b"\x31\xC0\xC3"
    # THREAD:target thread 0 = EXTDEF 方法 2、索引 1;FIXUP:self-relative、offset32(loc 9)、位置 2、用 target thread 0、frame 方法 5
    fixes = bytes([(2 << 2) | 0, 0x01])
    fixes += bytes([0x80 | (9 << 2), 0x02, 0x50 | 0x08 | 0x04])
    mod_a = module("a", code_a, [("foo", 0), ("baz", 8)], ["bar"], fixes)
    # B:bar = mov eax, [0x1000](顯式 fixup:segment-relative、EXTDEF 1、帶 4 bytes 位移)、ret;再一筆 LIDATA 重複 2 次 "\x90"
    code_b = b"\xA1\0\0\0\0\xC3"
    fixes_b = bytes([0x80 | 0x40 | (9 << 2) | 0, 0x01, 0x50 | 0x02]) + b"\x01" + struct.pack("<I", 4)
    lid = struct.pack("<I", 2) + struct.pack("<H", 0) + b"\x01\x90"
    mod_b = module("b", code_b, [("bar", 0)], ["gvar"], fixes_b, lid)
    page = 16
    hdr = bytes([0xF0]) + struct.pack("<H", page - 3) + bytes(page - 3)
    body = hdr
    for m in (mod_a, mod_b):
        body += m
        body += bytes((-len(body)) % page)
    return body + _rec(0xF1, b"")


def selftest(lib_dir: Path) -> int:
    fails: list[str] = []

    def check(ok: bool, label: str) -> None:
        print(f"    {'PASS' if ok else 'FAIL'}: {label}")
        if not ok:
            fails.append(label)

    print("(1) parse_omf:合成函式庫(頁面對齊、THREAD + 顯式 fixup、LIDATA)")
    try:
        mods = parse_omf(synthetic_lib())
    except Exception as ex:                     # 解析錯位會在這裡炸;記成 FAIL,不讓 Traceback 蓋掉判定
        check(False, f"parse_omf 例外 {type(ex).__name__}: {ex}")
        mods = [Module("x"), Module("y")]
    check([m.name for m in mods] == ["a", "b"], f"模組 {[m.name for m in mods]}")
    a, b = (mods + [Module("x"), Module("y")])[:2]
    b.data.setdefault(1, bytearray())
    check(a.pub == [("foo", 1, 0), ("baz", 1, 8)] and a.ext == [None, "bar"], f"A 公開/外部 {a.pub} {a.ext}")
    check(a.fix == [{"seg": 1, "at": 2, "loc": 9, "selfrel": True, "tm": 2, "tdat": 1, "disp": 0}],
          f"A 的 thread fixup {a.fix}")
    check(b.fix == [{"seg": 1, "at": 1, "loc": 9, "selfrel": False, "tm": 2, "tdat": 1, "disp": 4}],
          f"B 的顯式 fixup {b.fix}")
    check(bytes(b.data[1]) == b"\xA1\0\0\0\0\xC3\x90\x90", f"B 的資料含 LIDATA 展開 {bytes(b.data[1]).hex()}")

    print("(2) lib_functions:以公開符號切函式、fixup 處萬用、call 目標取外部符號名")
    fns = collections.defaultdict(lambda: Fn("?", [("?", None)]), {f.key: f for f in lib_functions(mods, "syn")})
    check(sorted(fns) == ["bar", "baz", "foo"], f"函式 {sorted(fns)}")
    check(fns["foo"].tc == [("push ebp", None), ("call F", "bar"), ("pop ebp", None), ("ret ", None)],
          f"foo {fns['foo'].tc}")
    check(fns["bar"].toks[0] == "mov eax, dword ptr [X]", f"bar 的 fixup 位移換 X:{fns['bar'].toks[0]}")

    print("(2b) static 切點與可達指令")
    st = Module("m")
    st.segs.append({"name": "_TEXT", "class": "CODE", "size": 13})
    # f:call 0xa(模組內已解析)、ret、4 個走不到的 nop;0xa:xor eax,eax、ret
    st.data[1] = bytearray(b"\xE8\x05\0\0\0\xC3\x90\x90\x90\x90\x31\xC0\xC3")
    st.pub.append(("f", 1, 0))
    sf = {f.key: f for f in lib_functions([st], "syn")}
    check(sorted(sf) == ["f", "m+0xa"] and is_static("m+0xa") and not is_static("f"), f"static 切成 m+0xa {sorted(sf)}")
    check(sf["f"].tc == [("call F", "m+0xa"), ("ret ", None)], f"f 不含走不到的 nop、call 目標是 static 名 {sf['f'].tc}")
    st0 = Module("s0")
    st0.segs.append({"name": "_TEXT", "class": "CODE", "size": 3})
    st0.data[1] = bytearray(b"\x90\xC3\xC3")           # +0:nop、ret(段首 static);+2:g
    st0.pub.append(("g", 1, 2))
    check(sorted(f.key for f in lib_functions([st0], "syn")) == ["g", "s0+0x0"], "段首在第一個公開符號之前的也切成 static")
    md = _cs()
    # jne 跳過一條 ud2(走不到)到 ret;落空路徑的 inc 走得到
    r = reach_insns(md, b"\x75\x05\x40\xEB\x02\x0F\x0B\xC3", 0x100)
    check([x[2] for x in r] == ["jne", "inc", "jmp", "ret"], f"條件分支兩路都走、jmp 越過的不算 {[x[2] for x in r]}")

    # FD2 端:fixup 蓋到的指令整條換 X(同一條的小立即值也換,才和函式庫端一致)
    fdx = fd2_functions([{"addr": "0x1000", "span_upper": 11}], b"\xC7\x05\xEA\x2B\x05\x00\x05\0\0\0\xC3", 0x1000,
                        {0x1002: 0x52BEA})
    check(fdx[0].toks == ["mov dword ptr [X], X", "ret "], f"FD2 fixup 指令的小立即值也換 X {fdx[0].toks}")

    print("(3) norm:分支、大常數、小常數")
    check(norm("jne", "0x1234", False) == "jne L" and norm("call", "0x10", False) == "call F", "分支換 L、call 換 F")
    check(norm("mov", "eax, 0x12345", False) == "mov eax, X" and norm("mov", "eax, 0x12", False) == "mov eax, 0x12",
          "大常數換 X、小常數保留")
    check(norm("mov", "eax, 0x12", True) == "mov eax, X", "fixup 蓋到的小常數也換 X")

    print("(4) assign:被呼叫者決勝、衝突淘汰、傳播、別名組")
    body = [("push ebp", None), ("mov ebp, esp", None), ("sub esp, 8", None), ("mov eax, dword ptr [ebp + 8]", None),
            ("add eax, 1", None), ("mov dword ptr [ebp - 4], eax", None), ("leave ", None), ("ret ", None)]

    def lf(name: str, callee: str) -> Fn:
        return Fn(name, body[:3] + [("call F", callee)] + body[3:], "syn", name)

    core = [("x%d" % k, None) for k in range(10)]
    lib = [lf("w_add", "core_add"), lf("w_div", "core_div"), Fn("core_div", core, "syn", "m"),
           Fn("twin1", body, "syn", "t"), Fn("twin2", body, "syn", "t")]
    fd = [Fn(0x100, body[:3] + [("call F", 0x200)] + body[3:]), Fn(0x200, core), Fn(0x300, body)]
    got = assign(lib, fd, {0x100, 0x200, 0x300})
    check(got.get(0x200, {}).get("name") == "core_div", f"長函式先定 {got.get(0x200)}")
    check(got.get(0x100, {}).get("name") == "w_div", f"包裝函式由被呼叫者決勝(不是 w_add){got.get(0x100)}")
    check(got.get(0x300, {}).get("name") == "twin1|twin2", f"分不開的記成別名組 {got.get(0x300)}")
    lib2 = [lf("w_add", "core_add"), Fn("core_add", [("y", None)] * 3, "syn", "c")]
    fd2 = [Fn(0x100, body[:3] + [("call F", 0x200)] + body[3:]), Fn(0x200, [("y", None)] * 3)]
    got2 = assign(lib2, fd2, {0x100, 0x200})
    check(got2.get(0x200, {}).get("name") == "core_add" and got2[0x200]["via"] == "callee",
          f"被呼叫者傳播(token 太少不能本體判定,但本體最像 core_add){got2.get(0x200)}")
    got3 = assign(lib2, fd2, {0x100})
    check(0x200 not in got3, "傳播目標不是清單入口就不命名")
    st7: dict = {}
    lib7 = [lf("w_add", "core_add"), Fn("zz", [("y", None)] * 3, "syn", "z")]
    got7 = assign(lib7, fd2, {0x100, 0x200}, st7)
    check(0x200 not in got7 and st7["callee_unconfirmed"].get(0x200, {}).get("name") == "core_add",
          f"本體最像的是別的名稱 -> 不命名,記在 callee_unconfirmed {st7.get('callee_unconfirmed')}")
    lib4 = [lf("w_add", "core_add"), Fn("core_div", core, "syn", "m")]
    fd4 = [Fn(0x100, body[:3] + [("call F", 0x200)] + body[3:]), Fn(0x200, core)]
    got4 = assign(lib4, fd4, {0x100, 0x200})
    check(0x100 not in got4 and got4.get(0x200, {}).get("name") == "core_div",
          f"與被呼叫者衝突的候選淘汰(唯一候選也不命名){sorted(hex(k) for k in got4)}")
    short = Fn(0x400, body[:MIN_TOK - 1])
    check(0x400 not in assign([Fn("s", body[:MIN_TOK - 1], "syn", "s")], [short], {0x400}), "token 太少不命名")
    lib5 = [lf("w_a", "p"), lf("w_b", "q")]
    fd5 = [Fn(0x100, body[:3] + [("call F", 0x200)] + body[3:]), Fn(0x500, [("z", None)] * 9)]
    got5 = assign(lib5, fd5, {0x100, 0x500})
    check(got5.get(0x100, {}).get("name") == "w_a|w_b", f"同分又沒有一致性可決勝 -> 別名組 {got5.get(0x100)}")
    # 同分、都沒衝突:一致數多的贏(被呼叫者不明的 w_unk 不會進別名組)
    lib6 = [lf("w_div", "core_div"), Fn("w_unk", body[:3] + [("call F", None)] + body[3:], "syn", "u"),
            Fn("core_div", core, "syn", "m")]
    got6 = assign(lib6, fd4, {0x100, 0x200})
    check(got6.get(0x100, {}).get("name") == "w_div", f"同分以一致數決勝 {got6.get(0x100)}")
    # ratio 落在 [T_HI - MARGIN, T_HI) 不命名
    base10 = [("b%d" % k, None) for k in range(10)]
    lo_lib = Fn("lo", base10 + [("l1", None), ("l2", None), ("l3", None)], "syn", "lo")
    lo_fd = Fn(0x600, base10 + [("f1", None), ("f2", None), ("f3", None)])
    r_lo = similar(lo_lib.toks, lo_fd.toks).ratio()
    check(T_HI - MARGIN <= r_lo < T_HI and 0x600 not in assign([lo_lib], [lo_fd], {0x600}),
          f"ratio {r_lo:.3f} 低於 T_HI 不命名")
    # 第二級:[T_LO, T_HI) 有一致的對齊 call 才命名
    diff4 = [("d%d" % k, None) for k in range(4)]
    mid_lib = Fn("mid", base10 + [("call F", "core_div")] + diff4, "syn", "mid")
    mid_fd = Fn(0x700, base10 + [("call F", 0x200)] + [("e%d" % k, None) for k in range(4)])
    r_mid = similar(mid_lib.toks, mid_fd.toks).ratio()
    g8 = assign([mid_lib, Fn("core_div", core, "syn", "m")], [mid_fd, Fn(0x200, core)], {0x700, 0x200})
    check(T_LO <= r_mid < T_HI and g8.get(0x700, {}).get("name") == "mid" and g8[0x700]["tier"] == 2,
          f"ratio {r_mid:.3f} + 一致 call -> 第二級命名 {g8.get(0x700)}")
    g9 = assign([mid_lib], [mid_fd, Fn(0x200, core)], {0x700, 0x200})
    check(0x700 not in g9, "同樣 ratio、被呼叫者沒有認定 -> 不命名")
    mid_twin = Fn("mid_twin", mid_lib.tc, "syn", "mid")
    g11 = assign([mid_lib, mid_twin, Fn("core_div", core, "syn", "m")], [mid_fd, Fn(0x200, core)], {0x700, 0x200})
    check(0x700 not in g11, "第二級不收別名組")
    # 傳播的三個擋點:兩個呼叫端隱含不同名稱、名稱已在別處、本體與別的名稱同分
    alt = [("q%d" % k, None) for k in range(8)]
    ys = [("y%d" % k, None) for k in range(8)]
    lib12 = [lf("w_a", "p"), Fn("w_b", alt + [("call F", "q")], "syn", "b"), Fn("p", ys, "syn", "p"),
             Fn("q", [("z", None)] * 8, "syn", "q")]
    fd12 = [Fn(0x100, body[:3] + [("call F", 0x900)] + body[3:]), Fn(0x110, alt + [("call F", 0x900)]),
            Fn(0x900, ys[:7])]
    g12 = assign(lib12, fd12, {0x100, 0x110, 0x900})
    check(0x900 not in g12, f"兩個呼叫端隱含不同名稱(其一本體最像)-> 不命名 {g12.get(0x900)}")
    lib13 = [lf("w_a", "p"), Fn("p", ys, "syn", "p")]
    fd13 = [Fn(0x100, body[:3] + [("call F", 0x900)] + body[3:]), Fn(0x950, ys), Fn(0x900, ys[:7])]
    g13 = assign(lib13, fd13, {0x100, 0x900, 0x950})
    check(g13.get(0x950, {}).get("name") == "p" and 0x900 not in g13, f"名稱已在別處 -> 不傳播 {sorted(hex(k) for k in g13)}")
    lib14 = [lf("w_a", "p"), Fn("p", [("y", None)] * 3, "syn", "p"), Fn("p2", [("y", None)] * 3, "syn", "p2")]
    g14 = assign(lib14, fd2, {0x100, 0x200})
    check(0x200 not in g14, "本體與別的名稱同分 -> 旁證不成立")
    # 一個名稱只能在一個位址
    g10 = assign([Fn("uniq", body, "syn", "u")], [Fn(0x800, body), Fn(0x810, body)], {0x800, 0x810})
    check(sorted(g10) == [0x800], f"同名只認定一處 {sorted(hex(k) for k in g10)}")
    dup = final_conflicts([], [], {0x800: {"name": "uniq", "via": "callee"}, 0x810: {"name": "uniq", "via": "callee"}})
    check(len(dup) == 1 and "uniq" in dup[0], f"final_conflicts 抓得到重名 {dup}")
    # final_conflicts:人為放一筆與被呼叫者衝突的認定
    bad_got = {0x100: {"name": "w_add", "via": "body", "ratio": 1.0}, 0x200: {"name": "core_div", "via": "body"}}
    fc = final_conflicts([lf("w_add", "core_add")], fd4, bad_got)
    check(len(fc) == 1 and "core_add" in fc[0], f"final_conflicts 抓得到衝突 {fc}")
    check(null_hits({0x150: {}, 0x250: {}, 0x350: {}}, (0x200, 0x300)) == ["0x250"], "null_hits 只收區間內的位址")

    if not (lib_dir / LIBS[0]).is_file():
        print(f"SKIP 真實比對:找不到函式庫 {lib_dir}")
    else:
        print("(5) 真實 FD2.EXE × Watcom 11.0c")
        doc = build(lib_dir)
        m, got = doc["_meta"], doc["matches"]
        print(f"    認定 {m['matched']} {m['by_via']};零假設區 {m['null_entries']} 個入口")
        check(m["names_in_null_region"] == [], f"遊戲區沒有任何名稱 {m['names_in_null_region']}")
        check(m["final_conflicts"] == [], f"最終一致性 0 衝突 {m['final_conflicts'][:3]}")
        # 對照組:現有命名(人讀或文件)與函式庫名稱一致
        controls = {0x37910: "memset", 0x37b55: "strlen", 0x3cf26: "memcpy", 0x3da49: "segread",
                    0x37af4: "__CHP", 0x4b882: "___LDA", 0x4bab1: "___LDD", 0x4bc86: "___LDM", 0x3cf50: "lseek"}
        bad = {hex(a): got.get(hex(a), {}).get("name") for a, n in controls.items() if got.get(hex(a), {}).get("name") != n}
        check(not bad, f"已知名稱對照 {len(controls)} 個全一致 {bad}")
        check(got.get("0x3d2c0", {}).get("name") == "strcmp", "0x3d2c0 = strcmp(無描述入口,ratio 1.0)")
        check(m["null_best_ratio_max"] < T_HI, f"零假設區最佳 ratio {m['null_best_ratio_max']} < T_HI {T_HI}")
        check(m["null_best_ratio_with_agree_max"] < T_LO,
              f"零假設區有一致數的最佳 ratio {m['null_best_ratio_with_agree_max']} < T_LO {T_LO}")
        # 陷阱:新版 __setenvp 改呼叫模組內的 allocate;舊版在同一位置呼叫的是 0x3707e(現名 nmalloc)
        cu = m["callee_unconfirmed"].get("0x3707e", {})
        check("0x3707e" not in got and cu.get("name") == "allocate",
              f"0x3707e 不被傳播成 allocate(本體旁證不成立){cu}")
        # int N 樁表的分派(doc98 續七十九)是 int386xa 模組的 static,在 __int386x_ 之後 0xaa
        check(got.get("0x46915", {}).get("name") == "int386xa+0xaa" and got.get("0x46870", {}).get("name") == "__int386x_",
              f"0x46915 = int386xa+0xaa、0x46870 = __int386x_ {got.get('0x46915')}")
        # 陷阱:0x4ba87 的 token 與 __FLDA/__FLDS 完全相同(1.0),只有被呼叫者 ___LDD 能分辨
        check(got.get("0x4ba87", {}).get("name") == "__FLDD", f"0x4ba87 由被呼叫者決勝為 __FLDD {got.get('0x4ba87')}")
        check("0x4a314" not in got, "0x4a314 被不同呼叫端隱含成不同名稱 -> 不命名")
        # 2026-10-07 函式清單加了 LE 進入點與死函式島(doc98 續八十一):_DoINTR_ 正是呼叫 int386xa+0xaa 的那個;
        # 進入點的本體比得出 _cstart_,它呼叫的兩個也經傳播得名
        want = {"0x468cb": "_DoINTR_", "0x3ccb4": "_cstart_", "0x4609b": "__CMain", "0x460ea": "__InitRtns",
                "0x4db0c": "__ModF", "0x4bd87": "__RLDI4"}
        bad = {a: got.get(a, {}).get("name") for a, n in want.items() if got.get(a, {}).get("name") != n}
        check(not bad, f"進入點與死函式的名稱 {bad}")
    if fails:
        print(f"\n--selftest FAILED({len(fails)} 筆)")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Watcom 函式庫 × FD2.EXE 的指令層比對")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--lib-dir", type=Path, default=DEFAULT_LIB_DIR)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest(a.lib_dir)
    if not (a.lib_dir / LIBS[0]).is_file():
        print(f"找不到函式庫:{a.lib_dir / LIBS[0]}(來源 {SOURCE})", file=sys.stderr)
        return 2
    if a.report:
        return report(build(a.lib_dir))
    if not a.out:
        ap.error("需要輸出路徑,或 --report / --selftest")
    Path(a.out).write_bytes(dump(build(a.lib_dir)).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
