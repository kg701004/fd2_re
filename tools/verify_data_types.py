#!/usr/bin/env python3
"""verify_data_types.py —— 把 data_map.json 每段的 `type` 宣告逐項對 FD2.EXE 核對(re_coverage 只核邊界)。

為什麼有這支
------------
`re_coverage.py --check` 核對的是區段**邊界**:不重疊、直接定址的存取不跨出區段、區段內被引用的位址都有名稱。
它的負向對照一再寫著「檢查器只證明長度上限」—— 字串區段多登 1 byte 會被抓,少登 1 byte 不會;
`dword[90] 函式指標表` 只有索引存取,登成 356 byte 也通過。`type` 欄位本身(字串內容、元素寬度、
函式指標、常數、值域、初值)是自由文字,從來沒有被機器讀過。2026-11-07 使用者要求「未證實的部分新增工具
加強清查及驗證」,這支把 `type` 用固定文法解析成可核對的宣告,逐項對原版位元組與指令核對。

解析不了的 `type` 不算通過:列為「未解析」並讓 `--check` 失敗(清單要能歸零,不能靠沒讀到而乾淨)。

核對項目(每一項都會說不)
--------------------------
* 大小      `byte` / `word` / `dword` 的元素寬 × 個數(`[N]`、`union REGS(… N 個 dword)`)必須等於 `size`;
            C 字串的 `(N bytes 含 NUL)` 與字面長度 + 1 都必須等於 `size`。
* 字串內容  `C 字串 "…"` 的字面(`\\xNN` 跳脫)+ NUL 必須逐 byte 等於 EXE 檔內該處位元組,而且該處不在
            `_cstart_` 的清零範圍內(否則執行時看到的是 0)。→ 證明長度**下限**:字串真的有那麼長。
* 函式指標表 `dword[N] 函式指標表`:N 個 dword 位置各有一筆 LE fixup,目標是 function_inventory 的入口;
            表尾後一個 dword 若也是指向入口的 fixup,而且不屬於另一個已登錄區段,就是表登短了。→ 下限與上限。
* 元素寬度  直接定址的存取寬度大於元素寬度 → 失敗;小於元素寬度(例如 `cmp byte [dword 變數], 0`)列為窄存取,
            只報告不失敗(合法,但代表那處只看低位元組,值域宣稱要能放進那個寬度)。陣列的直接存取必須對齊元素。
            `union` 不核寬度。
* 常數      `常數`:區段內沒有任何寫入(直接或以區段起點為基底的索引寫入);初值必須來自 EXE 檔內(不在清零範圍);
            純量常數的 `type` 若恰好寫了一個十進位數,檔內值必須等於它。
* 值域      `A .. B`、`A / B / C`、`0 空、1 已配置、2 執行中` 這類列舉、`旗標`(= 0 / 1)、`上限 N`;
            有值域時 `0xNN = …` 標的哨兵值也算合法。每一筆**立即數寫入**(`mov [x], imm`)的值必須在值域內;
            `mov [x], 暫存器` 在同一基本區塊內往回找得到 `mov 32 位元暫存器, 立即數` 或 `xor` / `sub` 同一暫存器
            (見 `reg_const`)時,同樣核對;其餘暫存器來源、`inc` / `add` 等讀改寫只計數為「未判定寫入」,
            不當作通過。指標型別不做值域。
* 指標      `指標`:立即數寫入只能是 0,或立即數本身有 fixup(指向程式自己的位址)。
* 初值      每段報告初值來源:`file`(EXE 檔內頁)、`zeroed`(落在 `_cstart_` 以 `rep stosd` 清零的
            [edi, ecx) 範圍,範圍由 `_cstart_` 的指令現算,不寫死)、`none`(兩者皆非,初值未定)。

不核對的(誠實列出)
--------------------
* 跨基本區塊(中間有分支、call、跳躍目標)或由其他指令算出的暫存器來源寫入值、索引定址但基底不是區段起點的存取、
  動態上限(`0 .. 地圖寬 − 13`)、語意性的說明文字。
* 值域只檢查立即數寫入:通過代表「程式碼裡寫死的值都合法」,不代表執行期不會出現別的值。

用法
----
    python tools/verify_data_types.py              # 逐段報告 + 摘要
    python tools/verify_data_types.py --check      # 有失敗或未解析就 exit 1
    python tools/verify_data_types.py --show 0x51b91
    python tools/verify_data_types.py --selftest
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

WIDTH = {"byte": 1, "word": 2, "dword": 4}
# `sub ecx, edi` 之後幾條內要看到 `rep stosd`(FD2 實際在第 4 條)
STOSD_WINDOW = 8

# 寫入指令的立即數:(助記符, 立即數或 None, 立即數有沒有 fixup)
Insn = tuple[str, int | None, bool]


# ---------------------------------------------------------------- type 文法

_STR = re.compile(r'^C 字串 "((?:[^"\\]|\\x[0-9A-Fa-f]{2})*)"'
                  r'(?:\((\d+) bytes 含 NUL\)|\(((?:[0-9a-f]{2} ?)+)\))?')
_UNION = re.compile(r"^union REGS\(.*?(\d+) 個 dword\)")
_CHAR = re.compile(r"^char\[(\d+)\]")
_BASE = re.compile(r"^(byte|word|dword)( 指標)?(?:\[(\d+)\])?")
_RANGE = re.compile(r"(?<![\w.])(\d+) ?\.\. ?(\d+)(?![\w.])")
_LIST = re.compile(r"(?<![\w/])(\d+)((?: ?/ ?\d+)+)(?![\w/])")
_LABELLED = re.compile(r"(?<![\w])(\d+) [^\d、,()::]+(?=、|\)|$)")
_UPPER = re.compile(r"上限 (\d+)(?![\w])")
_FLAGS_AS = re.compile(r"(?<![\w/])(\d+(?: ?/ ?\d+)+) 當旗標")
_SENTINEL = re.compile(r"(?<![\w])(0x[0-9a-f]+) = ")
_DEC = re.compile(r"(?<![\w\[.])(\d+)(?![\w\].])")


def _unescape(lit: str) -> bytes:
    """`\\xNN` 跳脫還原成 byte,其他字元以 latin-1 編碼(字串區段都是 ASCII 檔名)。"""
    out = bytearray()
    i = 0
    while i < len(lit):
        if lit.startswith("\\x", i):
            out.append(int(lit[i + 2:i + 4], 16))
            i += 4
        else:
            out += lit[i].encode("latin-1")
            i += 1
    return bytes(out)


def _values(t: str) -> tuple[set[int] | None, tuple[int, int] | None, int | None]:
    """從說明文字取值域:(列舉集合, (下限, 上限), 只有上限)。"""
    # 位址([0x....])與十六進位數不參與十進位值域
    plain = re.sub(r"\[0x[0-9a-f]+\]", "", t)
    m = _RANGE.search(plain)
    rng = (int(m.group(1)), int(m.group(2))) if m else None
    vals: set[int] | None = None
    lm = _LIST.search(plain)
    if lm:
        vals = {int(lm.group(1))} | {int(x) for x in re.findall(r"\d+", lm.group(2))}
    lab = _LABELLED.findall(plain.partition(":")[2])
    if len(lab) >= 2:
        vals = (vals or set()) | {int(x) for x in lab}
    if "旗標" in plain and rng is None and vals is None:
        vals = {0, 1}
    um = _UPPER.search(plain)
    return vals, rng, int(um.group(1)) if um else None


def parse_type(t: str, size: int) -> dict:
    """把一段的 `type` 解析成宣告;解析不了時 kind = "unparsed"。"""
    m = _STR.match(t)
    if m:
        lit = _unescape(m.group(1))
        c: dict = {"kind": "cstring", "elem": 1, "count": len(lit) + 1, "literal": lit}
        if m.group(2):
            c["declared_len"] = int(m.group(2))
        if m.group(3):
            c["declared_hex"] = bytes.fromhex(m.group(3))
        return c
    m = _UNION.match(t)
    if m:
        return {"kind": "union", "elem": 4, "count": int(m.group(1))}
    m = _CHAR.match(t)
    if m:
        return {"kind": "array", "elem": 1, "count": int(m.group(1))}
    m = _BASE.match(t)
    if not m:
        return {"kind": "unparsed"}
    elem = WIDTH[m.group(1)]
    pointer = bool(m.group(2))
    count = int(m.group(3)) if m.group(3) else 1
    rest = t[m.end():]
    kind = "fptr_table" if "函式指標表" in rest else ("array" if m.group(3) else "scalar")
    c = {"kind": kind, "elem": elem, "count": count, "pointer": pointer or kind == "fptr_table",
         "const": "常數" in rest}
    # 指標兼旗標:`0 / 1 當旗標` 明寫的立即數也合法(例:[0x53a51] 城鎮側當旗標)
    fm = _FLAGS_AS.search(rest)
    if c["pointer"] and fm:
        c["pointer_flags"] = {int(x) for x in re.findall(r"\d+", fm.group(1))}
    if not c["pointer"]:
        vals, rng, upper = _values(rest)
        if vals is not None or rng is not None or upper is not None:
            c["allowed"] = {"set": vals, "range": rng, "upper": upper,
                            "sentinel": {int(x, 16) for x in _SENTINEL.findall(rest)}}
        if c["const"] and kind == "scalar":
            nums = _DEC.findall(re.sub(r"0x[0-9a-f]+", "", rest))
            if len(nums) == 1:
                c["const_value"] = int(nums[0])
    return c


def allowed_ok(a: dict, v: int) -> bool:
    if v in a["sentinel"]:
        return True
    if a["set"] is not None and v in a["set"]:
        return True
    if a["range"] is not None and a["range"][0] <= v <= a["range"][1]:
        return True
    if a["upper"] is not None and 0 <= v <= a["upper"]:
        return True
    return False


# ---------------------------------------------------------------- 暫存器常數

# 暫存器族:寫入任一成員都算改寫整個暫存器
FAMILY = {r: fam for fam, regs in (("eax", ("eax", "ax", "al", "ah")), ("ebx", ("ebx", "bx", "bl", "bh")),
                                   ("ecx", ("ecx", "cx", "cl", "ch")), ("edx", ("edx", "dx", "dl", "dh")),
                                   ("esi", ("esi", "si")), ("edi", ("edi", "di")), ("ebp", ("ebp", "bp")))
          for r in regs}
# 控制流程(助記符開頭):遇到就停(值可能來自別條路徑,或被呼叫 / 中斷處理改寫)
FLOW = ("j", "call", "ret", "iret", "int", "loop")


def reg_const(seq: list, i: int, targets: set[int],
              imm_of: Callable[[object], tuple[int | None, bool]]) -> tuple[int | None, bool, str]:
    """seq[i] 是 `mov [m], 暫存器`:在同一基本區塊內往回找那個暫存器最後一次被寫入的值。

    只接受寫入者是 `mov 32 位元暫存器, 立即數`(立即數以 imm_of 取,有 fixup 時是目標)或
    `xor` / `sub` 同一個 32 位元暫存器(= 0);來源是 ax / al / ah 這類部分暫存器時取對應位元。
    中間遇到分支 / call / ret / int、跨過跳躍目標(targets),或寫入者是其他指令(只寫部分暫存器、
    `cdq` 這類隱含寫入、算術)就不判定 —— 寧可留在「未判定」,不猜。

    Args:
        seq: 函式的 capstone 指令清單(需 detail)。
        i: 寫入指令在 seq 的索引。
        targets: 基本區塊開頭(跳躍目標與函式內的 fixup 目標)。
        imm_of: 指令 → (立即數, 有沒有 fixup)。

    Returns:
        (值或 None, 值有沒有 fixup, 不判定的原因;判定成功時是 "")。
    """
    from capstone.x86 import X86_OP_IMM, X86_OP_REG

    x = seq[i]
    ops = x.operands
    if x.mnemonic != "mov" or len(ops) != 2 or ops[1].type != X86_OP_REG:
        return None, False, "不是 mov [m], 暫存器"
    src = x.reg_name(ops[1].reg)
    fam = FAMILY.get(src)
    if fam is None:
        return None, False, f"來源 {src} 不是通用暫存器"
    members = {r for r, f in FAMILY.items() if f == fam}
    for k in reversed(range(i)):
        if seq[k + 1].address in targets:
            return None, False, f"{hex(seq[k + 1].address)} 是區塊開頭"
        y = seq[k]
        if y.mnemonic.startswith(FLOW):
            return None, False, f"{hex(y.address)} {y.mnemonic} 在中間"
        written = {y.reg_name(r) for r in y.regs_access()[1]}
        if not written & members:
            continue
        yo = y.operands
        if (y.mnemonic == "mov" and len(yo) == 2 and yo[0].type == X86_OP_REG and y.reg_name(yo[0].reg) == fam
                and yo[1].type == X86_OP_IMM):
            v, fx = imm_of(y)
        elif y.mnemonic in ("xor", "sub") and yo[1].type == X86_OP_REG and y.reg_name(yo[1].reg) == fam:
            # 目的必是 fam 的成員(上面 written 已確認)且與來源同寬 → 就是 fam 本身:xor / sub 自己 = 0
            v, fx = 0, False
        else:
            return None, False, f"{hex(y.address)} {y.mnemonic} 改寫 {fam}"
        if src == fam:
            return v & 0xFFFFFFFF, fx, ""
        if fx:
            return None, False, f"{hex(y.address)} 的位址只取 {src}"
        if src.endswith("h"):
            return (v >> 8) & 0xFF, False, ""
        return v & (0xFF if src.endswith("l") else 0xFFFF), False, ""
    return None, False, "往回到函式開頭沒有設定"


def block_starts(seq: list, lo: int, hi: int, fixup_targets: set[int]) -> set[int]:
    """函式 [lo, hi) 內的基本區塊開頭:跳躍 / loop 的立即數目標,加上落在函式內的 fixup 目標
    (跳躍表的 case 由間接 jmp 進入,指令裡看不到,只看得到表內指向它的 fixup)。"""
    from capstone.x86 import X86_OP_IMM

    tg = {t for t in fixup_targets if lo <= t < hi}
    for x in seq:
        if x.mnemonic.startswith(("j", "loop")) and x.operands[0].type == X86_OP_IMM:
            tg.add(x.operands[0].imm)
    return tg


# ---------------------------------------------------------------- 原版事實

class Facts:
    """核對需要的原版事實;selftest 以合成資料建構同一個介面。

    Args:
        image: 線性位址 → 該處 n bytes(不在檔內頁時回傳 None)。
        zeroed: `_cstart_` 清零的 [lo, hi) 範圍清單。
        fixups: 全部物件的 fixup {來源線性位址: 目標}。
        entries: function_inventory 的入口集合。
        accesses: re_coverage 的指令層存取(指令, 目標, 寬度, 讀寫, 種類, 有沒有索引)。
        insn: 指令位址 → (助記符, 立即數, 立即數有沒有 fixup);`mov [m], 暫存器` 由 reg_const 判定出值時,
            立即數就是那個值。
        regions: 已登錄區段 [(start, end)]。
        reg_src: 寫入位址 → reg_const 的結果(只用來把核對數拆成「立即數 / 暫存器常數」報告)。
    """

    def __init__(self, image: Callable[[int, int], bytes | None], zeroed: list[tuple[int, int]],
                 fixups: dict[int, int], entries: set[int], accesses: list | tuple,
                 insn: Callable[[int], Insn], regions: list[tuple[int, int]],
                 reg_src: dict[int, tuple[int | None, bool, str]] | None = None) -> None:
        self.image = image
        self.zeroed = zeroed
        self.fixups = fixups
        self.entries = entries
        self.accesses = accesses
        self.insn = insn
        self.regions = regions
        self.reg_src = reg_src or {}


def find_zeroed(insns: list[tuple[int, str, str, int | None]]) -> list[tuple[int, int]]:
    """在 `_cstart_` 的指令裡找 BSS 清零:緊接著的 `mov ecx, A` / `mov edi, B`(順序不拘)/ `sub ecx, edi`,
    之後 STOSD_WINDOW 條內有 `rep stosd`。

    insns 元素是 (位址, 助記符, 運算元字串, 立即數或 None)。回傳 [(B, A)];找不到時回傳空清單。
    `sub` 前面兩條必須正好是這兩個 mov(FD2 的 `_cstart_` 就是這樣);中間夾別的指令就不採信,
    因為那條指令可能改掉 ecx / edi。
    """
    out = []
    for i, (_a, mn, ops, _imm) in enumerate(insns):
        if mn != "sub" or ops.replace(" ", "") != "ecx,edi" or i < 2:
            continue
        regs = {ops2.split(",")[0].strip(): imm2 for _b, mn2, ops2, imm2 in insns[i - 2:i]
                if mn2 == "mov" and imm2 is not None}
        ecx, edi = regs.get("ecx"), regs.get("edi")
        if ecx is None or edi is None or ecx <= edi:
            continue
        if any(mn3 == "rep stosd" for _c, mn3, _o, _i in insns[i + 1:i + 1 + STOSD_WINDOW]):
            out.append((edi, ecx))
    return out


def init_source(f: Facts, start: int, size: int) -> tuple[str, bytes | None]:
    """初值來源:zeroed(整段在清零範圍)、file(整段在檔內頁)、none。"""
    if any(lo <= start and start + size <= hi for lo, hi in f.zeroed):
        return "zeroed", bytes(size)
    b = f.image(start, size)
    if b is not None and len(b) == size and not any(start < hi and lo < start + size for lo, hi in f.zeroed):
        return "file", b
    return "none", None


# ---------------------------------------------------------------- 逐段核對

def check_region(r: dict, f: Facts) -> dict:
    """核對一段;回傳 {"claim", "fail": [...], "note": [...], "init", "imm_checked", "undetermined", "narrow"}。"""
    start = int(r["start"], 16)
    size = r["size"]
    end = start + size
    c = parse_type(r.get("type", ""), size)
    res: dict = {"claim": c, "fail": [], "note": [], "imm_checked": 0, "via_reg": 0, "undetermined": 0, "narrow": []}
    src, init = init_source(f, start, size)
    res["init"] = src
    if c["kind"] == "unparsed":
        res["fail"].append(f"type 無法解析:{r.get('type', '')!r}")
        return res
    where = r["start"]

    # 大小
    if c["elem"] * c["count"] != size:
        res["fail"].append(f"{where}: type 宣告 {c['elem']} × {c['count']} = {c['elem'] * c['count']} byte,size 是 {size}")
    if c["kind"] == "cstring":
        if "declared_len" in c and c["declared_len"] != size:
            res["fail"].append(f"{where}: type 寫 {c['declared_len']} bytes 含 NUL,size 是 {size}")
        want = c["literal"] + b"\0"
        if "declared_hex" in c and c["declared_hex"] != want:
            res["fail"].append(f"{where}: type 的 hex {c['declared_hex'].hex(' ')} 與字面 {want.hex(' ')} 不同")
        if src != "file":
            res["fail"].append(f"{where}: 字串不在 EXE 檔內頁(初值 {src}),無法核對內容")
        elif init != want:
            res["fail"].append(f"{where}: EXE 位元組 {init.hex(' ') if init else None} ≠ 字面 + NUL {want.hex(' ')}")

    # 函式指標表
    if c["kind"] == "fptr_table":
        bad = [hex(a) for a in range(start, end, 4) if f.fixups.get(a) not in f.entries]
        if bad:
            res["fail"].append(f"{where}: {len(bad)} 格不是指向函式入口的 fixup:{bad}")
        nxt = end
        if f.fixups.get(nxt) in f.entries and not any(s <= nxt < e for s, e in f.regions if s != start):
            res["fail"].append(f"{where}: 表尾後 {hex(nxt)} 仍是指向入口 {hex(f.fixups[nxt])} 的 fixup,"
                               f"且不屬於其他已登錄區段(表登短了?)")
        res["note"].append(f"{c['count']} 格函式指標全部有 fixup 指向入口" if not bad else "")

    # 存取寬度與寫入
    writes = []
    for ins, t, width, rw, kind, indexed in f.accesses:
        if kind != "mem" or not (start <= t < end):
            continue
        if "w" in rw:
            writes.append((ins, t, width, rw))
        if indexed or c["kind"] == "union":
            continue
        off = t - start
        if off % c["elem"]:
            res["fail"].append(f"{where}: {hex(ins)} 直接存取 {hex(t)} 沒有對齊 {c['elem']} byte 元素")
        elif width > c["elem"]:
            res["fail"].append(f"{where}: {hex(ins)} 以 {width} byte 存取 {c['elem']} byte 元素")
        elif width < c["elem"]:
            res["narrow"].append((ins, t, width, rw))

    # 常數
    if c.get("const"):
        if writes:
            res["fail"].append(f"{where}: 宣告常數,但有 {len(writes)} 筆寫入:{[hex(ins) for ins, *_rest in writes]}")
        if src != "file":
            res["fail"].append(f"{where}: 宣告常數,但初值不是 EXE 檔內位元組({src})")
        elif "const_value" in c:
            v = int.from_bytes(init[:c["elem"]], "little")
            if v != c["const_value"]:
                res["fail"].append(f"{where}: 宣告常數 {c['const_value']},EXE 檔內值 {v}")

    # 值域與指標的立即數寫入
    for ins, t, width, rw in writes:
        mn, imm, imm_fx = f.insn(ins)
        if mn != "mov" or imm is None:
            res["undetermined"] += 1
            continue
        v = imm & ((1 << (8 * width)) - 1)
        if (c.get("pointer") or "allowed" in c) and f.reg_src.get(ins, (None,))[0] is not None:
            res["via_reg"] += 1
        if c.get("pointer"):
            res["imm_checked"] += 1
            if v != 0 and not imm_fx and v not in c.get("pointer_flags", ()):
                res["fail"].append(f"{where}: 指標以立即數 {hex(v)} 寫入({hex(ins)}),既不是 0 也沒有 fixup")
        elif "allowed" in c:
            res["imm_checked"] += 1
            if not allowed_ok(c["allowed"], v):
                res["fail"].append(f"{where}: {hex(ins)} 寫入立即數 {v}({hex(v)}),不在宣告值域內")
        else:
            res["undetermined"] += 1
    res["note"] = [n for n in res["note"] if n]
    return res


# ---------------------------------------------------------------- 讀原版

def load_facts() -> tuple[Facts, list[dict]]:
    import disasm_le
    import function_inventory as FI
    import le_xref
    import re_coverage as R
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM

    w = R.load_world()
    dm = json.loads(R.DATA_MAP.read_text(encoding="utf-8"))
    exe = (R.game_dir() / "FD2.EXE").read_bytes()
    meta = le_xref.parse_le(exe)
    ps = meta["page_size"]

    def image(a: int, n: int) -> bytes | None:
        for ob in meta["objs"]:
            if ob["base"] <= a and a + n <= ob["base"] + ob["pages"] * ps:
                fo = le_xref.page_file(meta, ob["first"] - 1) + (a - ob["base"])
                b = exe[fo:fo + n]
                return b if len(b) == n else None
        return None

    code, cbase = disasm_le.load_code(exe, meta)
    fx1 = disasm_le.build_fixups(exe, meta, {1})
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True

    def imm_of(x: object) -> tuple[int | None, bool]:
        """指令的立即數;LE 映像裡的立即數是物件內位移,有 fixup 時以 fixup 目標(線性位址)為準。"""
        imm = next((op.imm for op in x.operands if op.type == X86_OP_IMM), None)
        site = x.address + x.imm_offset
        has_fx = imm is not None and site in fx1
        return (fx1[site] if has_fx else imm), has_fx

    # `mov [m], 暫存器` 的寫入位址:在所屬函式(inventory 入口 .. span_upper)內以 reg_const 往回找常數
    fx_all = disasm_le.build_fixups(exe, meta, None)
    fx_targets = set(fx_all.values())
    inv = sorted((int(e["addr"], 16), e["span_upper"])
                 for e in json.loads(R.INVENTORY.read_text(encoding="utf-8"))["entries"])
    sites = sorted({ins for ins, _t, _w, rw, kind, _ix in w["ctx"].accesses if kind == "mem" and "w" in rw})
    reg_src: dict[int, tuple[int | None, bool, str]] = {}
    cache: dict[int, tuple[list, dict[int, int], set[int]]] = {}
    for a in sites:
        owner = [(e, n) for e, n in inv if e <= a < e + n]
        if not owner:
            continue
        e, n = max(owner)
        if e not in cache:
            seq = [x for x in disasm_le.sweep_range(md, code, cbase, e, e + n) if not isinstance(x, tuple)]
            cache[e] = (seq, {x.address: k for k, x in enumerate(seq)}, block_starts(seq, e, e + n, fx_targets))
        seq, pos, tg = cache[e]
        if a in pos:
            reg_src[a] = reg_const(seq, pos[a], tg, imm_of)

    def insn(a: int) -> Insn:
        x = next(md.disasm(code[a - cbase:], a), None)
        if x is None:
            return ("", None, False)
        imm, has_fx = imm_of(x)
        if imm is None and a in reg_src:
            imm, has_fx = reg_src[a][:2]
        return (x.mnemonic, imm, has_fx)

    cstart = [a for a, n in FI.load_watcom().items() if str(n) == "_cstart_"]
    if len(cstart) != 1:
        raise SystemExit(f"_cstart_ 在 Watcom 名單出現 {len(cstart)} 次")
    # 掃到下一個 inventory 入口為止(`_cstart_` 開頭是跳過版權字串的 jmp,線性掃描會續掃過去)
    nxt = min(a for a in w["funcs"] if a > cstart[0])
    lst = [(x.address, x.mnemonic, x.op_str, imm_of(x)[0])
           for x in disasm_le.sweep_range(md, code, cbase, cstart[0], nxt) if not isinstance(x, tuple)]
    zeroed = find_zeroed(lst)
    if not zeroed:
        raise SystemExit("在 _cstart_ 找不到 rep stosd 清零範圍")
    regions = [(int(r["start"], 16), int(r["start"], 16) + r["size"]) for r in dm["regions"]]
    facts = Facts(image, zeroed, fx_all, set(w["funcs"]), w["ctx"].accesses, insn, regions, reg_src)
    return facts, dm["regions"]


def run(facts: Facts, regions: list[dict]) -> list[tuple[dict, dict]]:
    return [(r, check_region(r, facts)) for r in regions]


def print_report(facts: Facts, out: list[tuple[dict, dict]], verbose: bool) -> int:
    nfail = sum(1 for _r, x in out if x["fail"])
    unparsed = sum(1 for _r, x in out if x["claim"]["kind"] == "unparsed")
    kinds: dict[str, int] = {}
    inits: dict[str, int] = {}
    for _r, x in out:
        kinds[x["claim"]["kind"]] = kinds.get(x["claim"]["kind"], 0) + 1
        inits[x["init"]] = inits.get(x["init"], 0) + 1
    print(f"data_map type 核對:{len(out)} 段;失敗 {nfail}、未解析 {unparsed}")
    print(f"  型別 {dict(sorted(kinds.items()))}")
    print(f"  初值來源 {dict(sorted(inits.items()))};_cstart_ 清零範圍 "
          f"{[(hex(a), hex(b)) for a, b in facts.zeroed]}")
    ranged = [(r, x) for r, x in out if "allowed" in x["claim"] or x["claim"].get("pointer")]
    print(f"  值域 / 指標宣告 {len(ranged)} 段:立即數寫入核對 {sum(x['imm_checked'] for _r, x in ranged)} 筆"
          f"(其中區塊內暫存器常數 {sum(x['via_reg'] for _r, x in ranged)} 筆)、"
          f"未判定寫入 {sum(x['undetermined'] for _r, x in ranged)} 筆")
    print(f"  常數宣告 {sum(1 for _r, x in out if x['claim'].get('const'))} 段;"
          f"字串 {kinds.get('cstring', 0)} 段;函式指標表 {kinds.get('fptr_table', 0)} 段")
    print(f"  窄存取(寬度小於元素,不算失敗) {sum(len(x['narrow']) for _r, x in out)} 筆,"
          f"分布在 {sum(1 for _r, x in out if x['narrow'])} 段")
    for r, x in out:
        if verbose or x["fail"]:
            c = x["claim"]
            extra = ""
            if "allowed" in c:
                a = c["allowed"]
                extra = f" 值域 set={sorted(a['set']) if a['set'] is not None else None} range={a['range']} " \
                        f"upper={a['upper']} 哨兵={sorted(a['sentinel'])}"
            print(f"{r['start']:>8} {r['size']:4d} {c['kind']:10} init={x['init']:6} 立即數 {x['imm_checked']} "
                  f"(暫存器 {x['via_reg']}) 未判定 {x['undetermined']} 窄 {len(x['narrow'])}{extra}")
            for n in x["note"]:
                print(f"           {n}")
            for e in x["fail"]:
                print(f"    FAIL {e}")
    return 1 if nfail or unparsed else 0


def show(facts: Facts, regions: list[dict], addr: int) -> int:
    hit = [r for r in regions if int(r["start"], 16) <= addr < int(r["start"], 16) + r["size"]]
    if not hit:
        print(f"{hex(addr)} 不在任何已登錄區段")
        return 1
    r = hit[0]
    x = check_region(r, facts)
    print(json.dumps({k: (sorted(v) if isinstance(v, set) else v) for k, v in x["claim"].items()
                      if k not in ("literal", "declared_hex", "allowed")}, ensure_ascii=False))
    if "allowed" in x["claim"]:
        print(f"  值域 {x['claim']['allowed']}")
    print(f"  初值 {x['init']}  {(facts.image(int(r['start'], 16), min(r['size'], 32)) or b'').hex(' ')}")
    for ins, t, width, rw in x["narrow"]:
        print(f"  窄存取 {hex(ins)} {width} byte {rw} @ {hex(t)}")
    for e in x["fail"]:
        print(f"  FAIL {e}")
    return 1 if x["fail"] else 0


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    # 合成映像:0x1000 起檔內頁;0x2000 .. 0x2100 清零
    mem = bytearray(0x200)
    mem[0:7] = b"BG.DAT\0"
    mem[0x10:0x14] = struct.pack("<I", 13)
    mem[0x20:0x22] = b"\xfa\0"

    def image(a: int, n: int) -> bytes | None:
        if 0x1000 <= a and a + n <= 0x1200:
            return bytes(mem[a - 0x1000:a - 0x1000 + n])
        return None

    imms: dict[int, Insn] = {0x900: ("mov", 1, False), 0x901: ("mov", 7, False), 0x902: ("inc", None, False),
                             0x903: ("mov", 0xff, False), 0x904: ("mov", 0x5000, True),
                             0x905: ("mov", 0x5000, False), 0x906: ("mov", 0, False), 0x907: ("mov", -1, False),
                             0x908: ("mov", 1, False), 0x909: ("mov", 3, False), 0x90a: ("mov", None, False)}
    fx = {0x1100: 0x400, 0x1104: 0x404, 0x1108: 0x408}
    ents = {0x400, 0x404, 0x408, 0x40c}

    def facts(acc: list, fixups: dict[int, int] | None = None,
              rs: dict[int, tuple[int | None, bool, str]] | None = None) -> Facts:
        return Facts(image, [(0x2000, 0x2100)], fx if fixups is None else fixups, ents, acc,
                     lambda a: imms.get(a, ("", None, False)), [(0x1100, 0x110c)], rs)

    def reg(start: int, size: int, t: str) -> dict:
        return {"start": hex(start), "size": size, "type": t}

    def errs(r: dict, acc: list | None = None, fixups: dict[int, int] | None = None) -> list[str]:
        return check_region(r, facts(acc or [], fixups))["fail"]

    # 文法
    check("文法:C 字串 + 長度", parse_type('C 字串 "BG.DAT"(7 bytes 含 NUL)', 7)["literal"] == b"BG.DAT")
    check("文法:hex 形式", parse_type('C 字串 "\\xFA"(fa 00)', 2)["declared_hex"] == b"\xfa\0")
    check("文法:函式指標表", parse_type("dword[90] 函式指標表(事件號 0 .. 89)", 360)["kind"] == "fptr_table")
    check("文法:指標陣列不做值域", "allowed" not in parse_type("dword 指標[3](BG.DAT 第 0 / 1 / 2 號)", 12))
    a = parse_type("dword[16](AIL 計時器槽狀態:0 空、1 已配置、2 執行中)", 64)["allowed"]
    check("文法:標籤列舉", a["set"] == {0, 1, 2})
    check("文法:十六進位不算列舉", "allowed" not in parse_type("dword(章節編號;序章暫借 0x1f / 0x20)", 4))
    check("文法:動態上限不算值域", "allowed" not in parse_type("dword(格,0 .. 地圖寬 [0x53ac1] − 13)", 4))
    check("文法:旗標 = 0/1", parse_type("byte 旗標(呼叫 0x10b4e 期間暫設 1)", 1)["allowed"]["set"] == {0, 1})
    check("文法:上限", parse_type("dword(待入帳經驗值,上限 99)", 4)["allowed"]["upper"] == 99)
    check("文法:常數值", parse_type("dword 常數(戰場視野寬 13 格)", 4).get("const_value") == 13)
    check("文法:無法解析", parse_type("qword 什麼", 8)["kind"] == "unparsed")
    check("跳脫在中間", _unescape(r"A\x41B") == b"AAB" and _unescape(r"\xFAB") == b"\xfaB")

    # 字串:正確通過;內容錯、長度登短、hex 錯、不在檔內都要失敗
    check("字串正確 → 0", errs(reg(0x1000, 7, 'C 字串 "BG.DAT"(7 bytes 含 NUL)')) == [])
    check("字串內容不同 → 失敗", errs(reg(0x1000, 7, 'C 字串 "BG.DAX"(7 bytes 含 NUL)')) != [])
    check("字串登短 1 byte → 失敗", errs(reg(0x1000, 6, 'C 字串 "BG.DA"(6 bytes 含 NUL)')) != [])
    check("字串宣告長度與 size 不同 → 失敗", errs(reg(0x1000, 7, 'C 字串 "BG.DAT"(8 bytes 含 NUL)')) != [])
    check("hex 正確 → 0", errs(reg(0x1020, 2, 'C 字串 "\\xFA"(fa 00)')) == [])
    check("hex 與字面不同 → 失敗", errs(reg(0x1020, 2, 'C 字串 "\\xFA"(fb 00)')) != [])
    check("字串在清零範圍 → 失敗", errs(reg(0x2000, 7, 'C 字串 "BG.DAT"(7 bytes 含 NUL)')) != [])

    # 函式指標表
    check("指標表正確 → 0", errs(reg(0x1100, 12, "dword[3] 函式指標表")) == [])
    check("指標表缺 fixup → 失敗", errs(reg(0x1100, 12, "dword[3] 函式指標表"), fixups={0x1100: 0x400, 0x1104: 0x404}) != [])
    check("指標表目標不是入口 → 失敗",
          errs(reg(0x1100, 12, "dword[3] 函式指標表"), fixups={**fx, 0x1108: 0x409}) != [])
    check("指標表登短(表尾後仍是指標)→ 失敗", errs(reg(0x1100, 8, "dword[2] 函式指標表")) != [])
    check("表尾後是指標但屬於別段 → 0",
          check_region(reg(0x1100, 8, "dword[2] 函式指標表"),
                       Facts(image, [], fx, ents, [], lambda a: ("", None, False),
                             [(0x1100, 0x1108), (0x1108, 0x110c)]))["fail"] == [])
    check("大小與元素數不同 → 失敗", errs(reg(0x1100, 16, "dword[3] 函式指標表")) != [])

    # 寬度
    check("寬度相同 → 0", errs(reg(0x1010, 4, "dword(x)"), [(0x800, 0x1010, 4, "r", "mem", False)]) == [])
    check("寬存取 → 失敗", errs(reg(0x1030, 1, "byte(x)"), [(0x800, 0x1030, 4, "r", "mem", False)]) != [])
    check("未對齊 → 失敗", errs(reg(0x1030, 8, "dword[2](x)"), [(0x800, 0x1032, 2, "r", "mem", False)]) != [])
    nr = check_region(reg(0x1010, 4, "dword(x)"), facts([(0x800, 0x1010, 1, "r", "mem", False)]))
    check("窄存取只報告", nr["fail"] == [] and len(nr["narrow"]) == 1)
    check("union 不核寬度",
          errs(reg(0x1040, 8, "union REGS(x:2 個 dword)"), [(0x800, 0x1041, 1, "r", "mem", False)]) == [])

    # 常數
    check("常數正確 → 0", errs(reg(0x1010, 4, "dword 常數(寬 13 格)")) == [])
    check("常數值不同 → 失敗", errs(reg(0x1010, 4, "dword 常數(寬 12 格)")) != [])
    check("常數被寫 → 失敗", errs(reg(0x1010, 4, "dword 常數(寬 13 格)"), [(0x900, 0x1010, 4, "w", "mem", False)]) != [])
    check("常數在清零範圍 → 失敗", errs(reg(0x2010, 4, "dword 常數(寬 0 格)")) != [])

    # 值域
    w1 = [(0x900, 0x1050, 4, "w", "mem", False)]
    check("值域內 → 0", errs(reg(0x1050, 4, "dword(x 0 .. 6)"), w1) == [])
    check("值域外 → 失敗", errs(reg(0x1050, 4, "dword(x 0 .. 6)"), [(0x901, 0x1050, 4, "w", "mem", False)]) != [])
    check("列舉外 → 失敗", errs(reg(0x1050, 4, "dword(碼 0 / 1 / 2)"), [(0x901, 0x1050, 4, "w", "mem", False)]) != [])
    check("上限外 → 失敗", errs(reg(0x1050, 4, "dword(x,上限 6)"), [(0x901, 0x1050, 4, "w", "mem", False)]) != [])
    check("哨兵值 → 0", errs(reg(0x1050, 4, "dword(x 0 .. 6,0xff = 沒有)"), [(0x903, 0x1050, 4, "w", "mem", False)]) == [])
    check("-1 以寬度遮罩 → 值域外",
          errs(reg(0x1050, 1, "byte 旗標(x)"), [(0x907, 0x1050, 1, "w", "mem", False)]) != [])
    ir = check_region(reg(0x1050, 4, "dword(x 0 .. 6)"), facts([(0x902, 0x1050, 4, "rw", "mem", False)]))
    check("讀改寫 → 未判定,不算核對", ir["undetermined"] == 1 and ir["imm_checked"] == 0)
    check("陣列索引寫入也核值域",
          errs(reg(0x1060, 8, "dword[2](槽:0 空、1 用)"), [(0x901, 0x1060, 4, "w", "mem", True)]) != [])

    # 寫入計數:核對與未判定各算一次
    cnt = check_region(reg(0x1070, 4, "dword 指標(x)"), facts([(0x904, 0x1070, 4, "w", "mem", False)]))
    check("指標立即數計 1 次核對", (cnt["imm_checked"], cnt["undetermined"]) == (1, 0))
    cnt = check_region(reg(0x1050, 4, "dword(x 0 .. 6)"), facts(w1))
    check("值域立即數計 1 次核對", (cnt["imm_checked"], cnt["undetermined"]) == (1, 0))
    cnt = check_region(reg(0x1050, 4, "dword(x)"), facts(w1))
    check("沒有宣告的立即數計 1 次未判定", (cnt["imm_checked"], cnt["undetermined"]) == (0, 1))
    check("純量的索引寫入也核值域",
          errs(reg(0x1050, 4, "dword(x 0 .. 6)"), [(0x901, 0x1050, 4, "w", "mem", True)]) != [])
    check("byte -1 遮罩成哨兵 0xff → 0",
          errs(reg(0x1050, 1, "byte(x 0 .. 6,0xff = 沒有)"), [(0x907, 0x1050, 1, "w", "mem", False)]) == [])
    check("char 陣列不當指標",
          errs(reg(0x1080, 4, "char[4] 緩衝"), [(0x905, 0x1080, 1, "w", "mem", False)]) == [])

    # 指標
    check("指標 fixup 立即數 → 0", errs(reg(0x1070, 4, "dword 指標(x)"), [(0x904, 0x1070, 4, "w", "mem", False)]) == [])
    check("指標 0 → 0", errs(reg(0x1070, 4, "dword 指標(x)"), [(0x906, 0x1070, 4, "w", "mem", False)]) == [])
    check("指標無 fixup 立即數 → 失敗",
          errs(reg(0x1070, 4, "dword 指標(x)"), [(0x905, 0x1070, 4, "w", "mem", False)]) != [])
    pf = "dword 指標(x;城鎮側 0 / 1 當旗標)"
    check("文法:指標兼旗標", parse_type(pf, 4).get("pointer_flags") == {0, 1})
    check("指標兼旗標 1 → 0", errs(reg(0x1070, 4, pf), [(0x908, 0x1070, 4, "w", "mem", False)]) == [])
    check("指標兼旗標以外的立即數 → 失敗", errs(reg(0x1070, 4, pf), [(0x905, 0x1070, 4, "w", "mem", False)]) != [])
    check("沒寫當旗標的指標寫 1 → 失敗",
          errs(reg(0x1070, 4, "dword 指標(x)"), [(0x908, 0x1070, 4, "w", "mem", False)]) != [])

    # 初值來源
    check("初值 file", init_source(facts([]), 0x1000, 4)[0] == "file")
    check("初值 zeroed", init_source(facts([]), 0x2004, 4)[0] == "zeroed")
    check("初值 none", init_source(facts([]), 0x3000, 4)[0] == "none")
    check("跨清零邊界 → none", init_source(facts([]), 0x1ffe, 4)[0] == "none")
    inner = Facts(image, [(0x1100, 0x1104)], {}, set(), [], lambda a: ("", None, False), [])
    check("檔內頁裡的清零範圍:跨進去 → none、緊鄰之後 → file、整段在內 → zeroed",
          [init_source(inner, a, 4)[0] for a in (0x10fe, 0x1104, 0x1100)] == ["none", "file", "zeroed"])
    check("未解析 → 失敗", errs(reg(0x1000, 4, "qword x")) != [])

    # _cstart_ 清零範圍推導
    seq = [(0, "mov", "ecx, 0x46b0", 0x546b0), (1, "mov", "edi, 0x39ec", 0x539ec), (2, "sub", "ecx, edi", None),
           (3, "mov", "dl, cl", None), (4, "shr", "ecx, 2", 2), (5, "sub", "eax, eax", None),
           (6, "rep stosd", "dword ptr es:[edi], eax", None)]
    check("清零範圍推導", find_zeroed(seq) == [(0x539ec, 0x546b0)])
    check("沒有 rep stosd → 找不到", find_zeroed(seq[:-1]) == [])
    check("ecx ≤ edi → 不採信", find_zeroed([(0, "mov", "ecx, 1", 0x10), (1, "mov", "edi, 2", 0x20)] + seq[2:]) == [])
    nop = (9, "nop", "", None)
    check("mov 與 sub 之間夾指令 → 不採信", find_zeroed(seq[:2] + [nop] + seq[2:]) == [])
    stosd = seq[-1]
    check("rep stosd 緊接 sub → 找到", find_zeroed(seq[:3] + [stosd]) == [(0x539ec, 0x546b0)])
    check(f"rep stosd 在第 {STOSD_WINDOW} 條 → 找到",
          find_zeroed(seq[:3] + [nop] * (STOSD_WINDOW - 1) + [stosd]) == [(0x539ec, 0x546b0)])
    check(f"rep stosd 在第 {STOSD_WINDOW + 1} 條 → 找不到", find_zeroed(seq[:3] + [nop] * STOSD_WINDOW + [stosd]) == [])

    # 暫存器常數的計數:判定出值的算核對、也算「暫存器」;判定不出的算未判定
    rs = {0x909: (3, False, ""), 0x90a: (None, False, "call 在中間")}
    wr = [(0x909, 0x1050, 4, "w", "mem", False)]
    cnt = check_region(reg(0x1050, 4, "dword(x 0 .. 6)"), facts(wr, rs=rs))
    check("(r0a) 暫存器常數 3 在值域內 → 核對 1、暫存器 1", (cnt["imm_checked"], cnt["via_reg"], cnt["fail"]) == (1, 1, []))
    cnt = check_region(reg(0x1050, 4, "dword(x 0 .. 2)"), facts(wr, rs=rs))
    check("(r0b) 暫存器常數 3 在值域外 → 失敗", cnt["fail"] != [] and cnt["via_reg"] == 1)
    cnt = check_region(reg(0x1070, 4, "dword 指標(x)"), facts([(0x909, 0x1070, 4, "w", "mem", False)], rs=rs))
    check("(r0c) 指標的暫存器常數也計暫存器", (cnt["imm_checked"], cnt["via_reg"]) == (1, 1))
    cnt = check_region(reg(0x1050, 4, "dword(x)"), facts(wr, rs=rs))
    check("(r0d) 沒有宣告 → 未判定、不計暫存器", (cnt["undetermined"], cnt["via_reg"]) == (1, 0))
    cnt = check_region(reg(0x1050, 4, "dword(x 0 .. 6)"), facts([(0x90a, 0x1050, 4, "w", "mem", False)], rs=rs))
    check("(r0e) 判定不出 → 未判定", (cnt["undetermined"], cnt["imm_checked"], cnt["via_reg"]) == (1, 0, 0))
    cnt = check_region(reg(0x1050, 4, "dword(x 0 .. 6)"), facts(wr))
    check("(r0f) 沒有 reg_src 的立即數不計暫存器", (cnt["imm_checked"], cnt["via_reg"]) == (1, 0))

    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM
    cs = Cs(CS_ARCH_X86, CS_MODE_32)
    cs.detail = True

    def rc(hexs: str, targets: set[int] | None = None,
           fxs: dict[int, int] | None = None) -> tuple[int | None, bool, str]:
        seq = list(cs.disasm(bytes.fromhex(hexs), 0x100))
        assert sum(x.size for x in seq) == len(hexs) // 2, hexs

        def imm(x: object) -> tuple[int | None, bool]:
            v = next((op.imm for op in x.operands if op.type == X86_OP_IMM), None)
            site = x.address + x.imm_offset
            return (fxs[site], True) if fxs and site in fxs else (v, False)
        return reg_const(seq, len(seq) - 1, targets or set(), imm)

    st = "a300200000"                                   # mov [0x2000], eax
    check("(r1) mov eax, 5 → 5", rc("b805000000" + st) == (5, False, ""))
    check("(r2) xor ecx, ecx;mov [m], cl → 0", rc("31c9" + "880d00200000") == (0, False, ""))
    check("(r3) sub edx, edx;mov [m], edx → 0", rc("29d2" + "891500200000") == (0, False, ""))
    # 每個暫存器族、每種寬度:mov r32, 0x1234 後以 32 / 16 / 低 8 / 高 8 位元寫出
    fam_ok = []
    for k, name in enumerate(("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")):
        setter = bytes((0xB8 + k,)).hex() + "34120000"
        got = [rc(setter + "89" + bytes(((k << 3) | 5,)).hex() + "00200000")[:2],
               rc(setter + "6689" + bytes(((k << 3) | 5,)).hex() + "00200000")[:2]]
        want = [(None, False)] * 2 if name == "esp" else [(0x1234, False)] * 2
        if k < 4:
            got += [rc(setter + "88" + bytes(((k << 3) | 5,)).hex() + "00200000")[:2],
                    rc(setter + "88" + bytes((((k + 4) << 3) | 5,)).hex() + "00200000")[:2]]
            want += [(0x34, False), (0x12, False)]
        fam_ok.append(got == want)
    check("(r4) 7 個暫存器族 × 32 / 16 / 8 / 高 8 位元取值;esp 不判定", all(fam_ok))
    check("(r5) 中間有分支 / call / ret / iret / int / loop → 不判定",
          all(rc("b805000000" + mid + st)[:2] == (None, False) for mid in ("eb00", "7400", "e800000000", "c3", "cf", "cd21", "e200")))
    check("(r6) 寫入指令本身是區塊開頭 → 不判定", rc("b805000000" + st, {0x105})[:2] == (None, False))
    check("(r7) 中間一條是區塊開頭 → 不判定", rc("b805000000" + "b907000000" + st, {0x105})[:2] == (None, False))
    check("(r8) 設定指令本身是區塊開頭不影響 → 5", rc("b805000000" + st, {0x100}) == (5, False, ""))
    check("(r9) 中間改寫別的暫存器 → 略過,仍是 5", rc("b805000000" + "b907000000" + st) == (5, False, ""))
    check("(r10) 中間有其他指令改寫(inc / cdq / mov al / mov eax,[m] / xor eax,ebx / xor eax,[m] / mov ax)→ 不判定",
          all(rc(h)[:2] == (None, False) for h in ("b805000000" + "40" + st, "b805000000" + "99" + "891500200000",
                                          "b005" + st, "8b0500300000" + st, "31d8" + st, "330500300000" + st,
                                          "66b83412" + st)))
    check("(r11) 往回到開頭沒有設定 → 不判定", rc(st)[:2] == (None, False))
    check("(r12) 立即數有 fixup → 取目標、帶 fixup", rc("b800300000" + st, fxs={0x101: 0x53000}) == (0x53000, True, ""))
    check("(r13) fixup 位址只取 al → 不判定", rc("b800300000" + "a200200000", fxs={0x101: 0x53000})[:2] == (None, False))
    check("(r14) 不是 mov [m], 暫存器 / 來源是區段暫存器 → 不判定",
          rc("c7050020000005000000")[:2] == (None, False) and rc("8c1d00200000")[:2] == (None, False))
    check("(r15) 0xffffffff 保留 32 位元", rc("b8ffffffff" + st) == (0xFFFFFFFF, False, ""))
    seq = list(cs.disasm(bytes.fromhex("eb02" + "ffe0" + "e2fc" + "c3"), 0x100))
    check("(r16) 區塊開頭 = jmp / loop 立即數目標 + 函式內 fixup 目標(含下界、不含上界);jmp eax 不算",
          block_starts(seq, 0x100, 0x107, {0xFF, 0x100, 0x105, 0x107}) == {0x104, 0x102, 0x100, 0x105})

    # 真實檔:倉庫登錄零失敗、零未解析
    try:
        f, regions = load_facts()
        out = run(f, regions)
        bad = [(r["start"], x["fail"]) for r, x in out if x["fail"]]
        check(f"真實 data_map {len(out)} 段零失敗", not bad)
        for s, e in bad[:5]:
            print(f"      {s} {e[:2]}")
        # 已知答案(2026-11-07 逐條讀 `_cstart_` 0x3cea2 .. 0x3cebc 的反組譯得到)
        check("真實 _cstart_ 清零範圍 = [0x539ec, 0x546b0)", f.zeroed == [(0x539ec, 0x546b0)])
        check("真實 0x262e2 = mov [0x53a51], 1(無 fixup)", f.insn(0x262e2) == ("mov", 1, False))
        check("真實 0x46170 立即數以 fixup 目標 0x49ad8 為準", f.insn(0x46170) == ("mov", 0x49ad8, True))
        # 暫存器常數(2026-11-14 逐條讀反組譯核對)
        check("真實 0x37ea6 = mov [0x54174], eax,區塊內 mov eax, 1 → 1", f.reg_src.get(0x37ea6) == (1, False, "")
              and f.insn(0x37ea6) == ("mov", 1, False))
        check("真實 0x3dbcd 跨過區塊開頭 0x3dbbf → 不判定", f.reg_src.get(0x3dbcd, (0, False, ""))[:2] == (None, False)
              and "0x3dbbf" in f.reg_src[0x3dbcd][2])
        check("真實 寫入位址判定出值 38 處", sum(1 for v in f.reg_src.values() if v[0] is not None) == 38)
        got = {r["start"]: x for r, x in out}
        check("真實 0x541ac 初值 zeroed、0x51a87 初值 file",
              got["0x541ac"]["init"] == "zeroed" and got["0x51a87"]["init"] == "file")
        ranged = [x for r, x in out if "allowed" in x["claim"] or x["claim"].get("pointer")]
        check("真實 值域 / 指標寫入:核對 273(暫存器 13)、未判定 194",
              (sum(x["imm_checked"] for x in ranged), sum(x["via_reg"] for x in ranged),
               sum(x["undetermined"] for x in ranged)) == (273, 13, 194))
    except SystemExit as e:
        check(f"讀原版失敗:{e}", False)

    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} 項失敗)")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="有失敗或未解析就 exit 1")
    ap.add_argument("--verbose", action="store_true", help="逐段列出(預設只列失敗)")
    ap.add_argument("--show", help="只看某個位址所在的區段")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    facts, regions = load_facts()
    if a.show:
        return show(facts, regions, int(a.show, 16))
    rc = print_report(facts, run(facts, regions), a.verbose or not a.check)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
