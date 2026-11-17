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
* 函式回傳  `mov [x], eax` 在同一基本區塊內往回,eax 最後由 `call 立即數` 寫入(`call_source`)時,值是那個函式的
            回傳值:另計「函式回傳」,不算未判定,也不算值域核對(回傳值本身不核)。呼叫的參數由 call 前的 push 取得
            (`call_args`)。
* 來源宣告  指標 `type` 寫了 `X.DAT` / `FDOTHER`(檔名)、`第 N 號` / `第 N 或 M 號` / `第 0 / 1 / 2 號`(資源號)、
            `malloc 0xN`(大小)時(`source_claims`):load_res 寫入的第 1 個參數(fixup 指向的字串)必須是宣告的檔名,
            常數的第 3 個參數必須是宣告的號碼(陣列且號碼數 = 元素數時逐格對應),malloc 的常數大小必須是宣告的大小;
            宣告的每個號碼與大小都要至少有一個寫入點。load_res / malloc 以命名表的名稱認,不寫死位址。
* 初值      每段報告初值來源:`file`(EXE 檔內頁)、`zeroed`(落在 `_cstart_` 以 `rep stosd` 清零的
            [edi, ecx) 範圍,範圍由 `_cstart_` 的指令現算,不寫死)、`none`(兩者皆非,初值未定)。

不核對的(誠實列出)
--------------------
* 跨基本區塊(中間有分支、call、跳躍目標)或由其他指令算出的暫存器來源寫入值、索引定址但基底不是區段起點的存取、
  動態上限(`0 .. 地圖寬 − 13`)、語意性的說明文字。
* 值域只檢查立即數寫入:通過代表「程式碼裡寫死的值都合法」,不代表執行期不會出現別的值。
* 函式回傳的值本身(例如 malloc 回傳的是不是有效指標)、跨函式的暫存器保存、load_res / malloc 以外的呼叫目標的參數;
  參數不是常數(例如 `DATO.DAT` 的頭像號來自單位記錄)時只記錄「未核對」。

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
# 式子宣告:`byte + 2` = movzx 一個 byte 再加 2(值域核對以式子本身比對,不展開成範圍)
_FORMULA = re.compile(r"(?<![\w])(byte|word) \+ (\d+)(?![\w])")


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
    if c["pointer"]:
        sc = source_claims(rest)
        if any(sc.values()):
            c["source"] = sc
    if not c["pointer"]:
        vals, rng, upper = _values(rest)
        formula = {(WIDTH[w], int(n)) for w, n in _FORMULA.findall(rest)}
        if vals is not None or rng is not None or upper is not None or formula:
            c["allowed"] = {"set": vals, "range": rng, "upper": upper,
                            "sentinel": {int(x, 16) for x in _SENTINEL.findall(rest)}}
        if formula:
            c["allowed"]["formula"] = formula
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
FAMILY_MEMBERS = {fam: {r for r, f in FAMILY.items() if f == fam} for fam in set(FAMILY.values())}


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
    from capstone.x86 import X86_OP_REG

    x = seq[i]
    ops = x.operands
    if x.mnemonic != "mov" or len(ops) != 2 or ops[1].type != X86_OP_REG:
        return None, False, "不是 mov [m], 暫存器"
    return reg_value(seq, i, x.reg_name(ops[1].reg), targets, imm_of)


def reg_value(seq: list, i: int, src: str, targets: set[int],
              imm_of: Callable[[object], tuple[int | None, bool]]) -> tuple[int | None, bool, str]:
    """seq[i] 讀暫存器 src(`mov [m], src`、`push src`):同一基本區塊內往回找 src 的值;規則見 reg_const。"""
    from capstone.x86 import X86_OP_IMM, X86_OP_REG

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


# 參數:(值或 None, 值有沒有 fixup, 來源說明)
Arg = tuple[int | None, bool, str]


def call_source(seq: list, i: int, targets: set[int], imm_of: Callable[[object], tuple[int | None, bool]],
                argc_of: Callable[[int], int | None]) -> tuple[int | None, list[Arg] | None, str]:
    """seq[i] 是 `mov [m], eax`:同一基本區塊內往回,eax 最後一次被寫入是 `call 立即數` 時,值就是那個函式的回傳值。

    中間的指令不得寫 eax(含 ax / al / ah)、不得是其他控制流程、不得跨過區塊開頭;否則不判定。
    找到 call 後以 call_args 取它的參數(argc 不明或取不到時參數是 None,呼叫目標照樣回傳)。

    Returns:
        (呼叫目標或 None, 參數清單或 None, 不判定的原因;判定成功時是 "")。
    """
    from capstone.x86 import X86_OP_IMM, X86_OP_REG

    x = seq[i]
    ops = x.operands
    if (x.mnemonic != "mov" or len(ops) != 2 or ops[1].type != X86_OP_REG
            or x.reg_name(ops[1].reg) != "eax"):
        return None, None, "不是 mov [m], eax"
    members = {r for r, f in FAMILY.items() if f == "eax"}
    for k in reversed(range(i)):
        if seq[k + 1].address in targets:
            return None, None, f"{hex(seq[k + 1].address)} 是區塊開頭"
        y = seq[k]
        if y.mnemonic == "call":
            if y.operands[0].type != X86_OP_IMM:
                return None, None, f"{hex(y.address)} 間接 call"
            t = y.operands[0].imm
            n = argc_of(t)
            return t, None if n is None else call_args(seq, k, n, targets, imm_of), ""
        if y.mnemonic.startswith(FLOW):
            return None, None, f"{hex(y.address)} {y.mnemonic} 在中間"
        if {y.reg_name(r) for r in y.regs_access()[1]} & members:
            return None, None, f"{hex(y.address)} {y.mnemonic} 改寫 eax"
    return None, None, "往回到函式開頭沒有 call"


def call_args(seq: list, c: int, n: int, targets: set[int],
              imm_of: Callable[[object], tuple[int | None, bool]]) -> list[Arg] | None:
    """seq[c] 是 call:同一基本區塊內往回取最後 n 個 push 當參數(cdecl 由右至左 push,最後一個 push 是第 1 個)。

    push 立即數取 imm_of(有 fixup 時是目標)、push 暫存器以 reg_value 往回找常數、push 記憶體是變數(值 None)。
    中間遇到控制流程、區塊開頭,或 push 以外改動 esp 的指令(`add esp`、`pop`、`sub esp`)就不取(回傳 None):
    那些 push 可能不屬於這次呼叫。
    """
    from capstone.x86 import X86_OP_IMM, X86_OP_REG

    out: list[Arg] = []
    for k in reversed(range(c)):
        if len(out) == n:
            break
        if seq[k + 1].address in targets:
            return None
        y = seq[k]
        if y.mnemonic.startswith(FLOW):
            return None
        if y.mnemonic == "push":
            op = y.operands[0]
            if op.type == X86_OP_IMM:
                v, fx = imm_of(y)
                out.append((None if v is None else v & 0xFFFFFFFF, fx, "立即數"))
            elif op.type == X86_OP_REG:
                v, fx, why = reg_value(seq, k, y.reg_name(op.reg), targets, imm_of)
                out.append((v, fx, why or "暫存器常數"))
            else:
                out.append((None, False, "記憶體"))
            continue
        if "esp" in {y.reg_name(r) for r in y.regs_access()[1]}:
            return None
    return out if len(out) == n else None


# ---------------------------------------------------------------- 跨區塊 / 跨 call 的值分析

# 值:("imm", 值, 有沒有 fixup);("zx", 來源寬度 byte, 加的常數) = movzx 一個值不知道的 byte / word 再加常數;
#     ("ret", 呼叫目標, call 在 seq 的索引;load_facts 換成參數清單) = 函式回傳;("mem", 位址, 寬度) = 固定位址的舊值
Val = tuple
# 匯合深度(往回跨過的匯合點數)與每次查詢的步數上限:超過就不判定
FLOW_DEPTH = 12
FLOW_BUDGET = 4000
# 不會落到下一條的指令(助記符開頭)
NO_FALL = ("jmp", "ret", "iret", "hlt", "ud2")
# 條件跳躍 → cmp a, b 之後跳不跳(有號 / 無號)
_COND: dict[str, Callable[[int, int, int, int], bool]] = {
    "je": lambda sa, sb, ua, ub: ua == ub, "jz": lambda sa, sb, ua, ub: ua == ub,
    "jne": lambda sa, sb, ua, ub: ua != ub, "jnz": lambda sa, sb, ua, ub: ua != ub,
    "jl": lambda sa, sb, ua, ub: sa < sb, "jge": lambda sa, sb, ua, ub: sa >= sb,
    "jle": lambda sa, sb, ua, ub: sa <= sb, "jg": lambda sa, sb, ua, ub: sa > sb,
    "jb": lambda sa, sb, ua, ub: ua < ub, "jae": lambda sa, sb, ua, ub: ua >= ub,
    "jbe": lambda sa, sb, ua, ub: ua <= ub, "ja": lambda sa, sb, ua, ub: ua > ub,
}


def _width(reg: str) -> int:
    """暫存器寬度(byte):eax 4、ax / si 2、al / ah 1。"""
    if reg.startswith("e"):
        return 4
    return 1 if reg.endswith(("l", "h")) else 2


def _mask(w: int) -> int:
    return (1 << (8 * w)) - 1


def cond_taken(mn: str, a: int, b: int, w: int) -> bool | None:
    """`cmp a, b`(寬 w byte)之後條件跳躍 mn 跳不跳;不支援的條件回傳 None。"""
    fn = _COND.get(mn)
    if fn is None:
        return None
    m = _mask(w)
    ua, ub = a & m, b & m
    sign = 1 << (8 * w - 1)
    return fn(ua - 2 * (ua & sign), ub - 2 * (ub & sign), ua, ub)


class FlowCtx:
    """一個函式的跨區塊值分析資料。

    Args:
        seq: 函式的 capstone 指令清單(需 detail)。
        targets: 區塊開頭(block_starts)。
        indirect: 前驅看不到的位址:函式內的 fixup 目標(跳躍表的 case、函式指標)與函式外的跳躍目標。
        imm_of: 指令 → (立即數, 有沒有 fixup)。
        mem_of: 指令位址 → 它直接定址(沒有基底 / 索引)的 (目標線性位址, 寬度);沒有就 None。
        preserves: (呼叫目標, 暫存器族) → (有沒有證明保存, 原因);見 Preserve。
    """

    budget: int     # 剩下的步數;flow_values 每次查詢重設成 FLOW_BUDGET

    def __init__(self, seq: list, targets: set[int], indirect: set[int],
                 imm_of: Callable[[object], tuple[int | None, bool]],
                 mem_of: Callable[[int], tuple[int, int] | None],
                 preserves: Callable[[int, str], tuple[bool, str]]) -> None:
        from capstone.x86 import X86_OP_IMM

        self.seq = seq
        self.targets = targets
        self.indirect = indirect
        self.imm_of = imm_of
        self.mem_of = mem_of
        self.preserves = preserves
        self.preds: dict[int, list[int]] = {}
        for k, x in enumerate(seq):
            if x.mnemonic.startswith(("j", "loop")) and x.operands and x.operands[0].type == X86_OP_IMM:
                self.preds.setdefault(x.operands[0].imm, []).append(k)


def flow_values(ctx: FlowCtx, k: int, src: str) -> tuple[list[Val] | None, str]:
    """seq[k] 執行前暫存器 src 的所有可能值:沿每條前驅路徑往回找寫入者。

    比 reg_value 多做的(每一條都只在證得出時才用,否則整個不判定):
    * 跨過條件跳躍:從條件跳躍「不跳」那條路往回,它就是唯一的前驅(下一條不是區塊開頭時)。
      旗標由前一條 `test r, r` / `or r, r` / `and r, r`(r = 0)或 `cmp r, imm`(r = imm)設定時,
      `jne` 不跳 / `je` 跳的那條路上 r 的值就是那個常數。
    * 區塊開頭:匯合所有前驅(函式內指向它的直接跳躍 + 前一條會落下來);函式開頭、迴圈、間接進入、
      函式外有跳躍進來就不判定。
    * 跨過 `call 立即數`:eax 是回傳值(("ret", …));其他暫存器要 preserves 證明被呼叫者保存它。
    * 寫入者:`mov r, imm`、`xor` / `sub` 自己(= 0)、`or` / `and` 自己(值不變)、`setcc`(0 / 1)、
      `mov r, r2`(改追 r2)、`mov r, [固定位址]`(("mem", …))、`movzx`(("zx", …))、`add` / `sub r, imm`
      (對常數與 zx 平移)。其他寫入者、部分暫存器改寫就不判定。

    Returns:
        (值清單或 None, 不判定的原因;判定成功時是 "")。
    """
    ctx.budget = FLOW_BUDGET
    vals, why = _before(ctx, k, src, frozenset(), 0)
    if vals is not None and not vals:
        return None, why or "只有迴圈路徑"
    return vals, why


def _before(ctx: FlowCtx, k: int, src: str, seen: frozenset, depth: int) -> tuple[list[Val] | None, str]:
    if FAMILY.get(src) is None:
        return None, f"來源 {src} 不是通用暫存器"
    seq = ctx.seq
    while True:
        ctx.budget -= 1
        if ctx.budget < 0:
            return None, "超過步數上限"
        a = seq[k].address
        if a in ctx.indirect:
            return None, f"{hex(a)} 由間接跳躍 / 函式外進入,前驅看不到"
        if a in ctx.targets:
            return _join(ctx, k, src, seen, depth)
        if k == 0:
            return None, "往回到函式開頭沒有設定"
        y = seq[k - 1]
        if y.mnemonic.startswith(NO_FALL):
            return None, f"{hex(y.address)} {y.mnemonic} 不會落到 {hex(a)}"
        r = _through(ctx, k - 1, src, "fall", seen, depth)
        if r is not None:
            return r
        k -= 1


def _join(ctx: FlowCtx, k: int, src: str, seen: frozenset, depth: int) -> tuple[list[Val] | None, str]:
    seq = ctx.seq
    a = seq[k].address
    if k == 0:
        return None, f"{hex(a)} 是函式開頭(呼叫者也從這裡進入)"
    if (k, src) in seen:
        # 迴圈:往回又回到這個匯合點。這條路上只有複製、沒有產生新值,它帶來的值就是其他前驅帶來的值
        # (最小不動點)→ 貢獻空集合;路上有累加(add / sub)時,累加那一步拿到空集合會整個不判定。
        return [], f"{hex(a)} 是迴圈"
    if depth >= FLOW_DEPTH:
        return None, f"{hex(a)} 超過匯合深度上限"
    seen = seen | {(k, src)}
    edges = [(j, "taken") for j in ctx.preds.get(a, [])]
    if not seq[k - 1].mnemonic.startswith(NO_FALL):
        edges.append((k - 1, "fall"))
    if not edges:
        return None, f"{hex(a)} 沒有看得到的前驅"
    out: list[Val] = []
    for j, edge in edges:
        r = _through(ctx, j, src, edge, seen, depth + 1)
        if r is None:
            r = _before(ctx, j, src, seen, depth + 1)
        if r[0] is None:
            return r
        out += [v for v in r[0] if v not in out]
    return out, "" if out else f"{hex(a)} 只有迴圈路徑"


def _refine(ctx: FlowCtx, j: int, src: str, edge: str) -> Val | None:
    """seq[j] 是條件跳躍:沿 edge 走時 src 是不是被前一條的比較釘成常數。"""
    from capstone.x86 import X86_OP_IMM, X86_OP_REG

    seq = ctx.seq
    mn = seq[j].mnemonic
    if not ((mn in ("je", "jz") and edge == "taken") or (mn in ("jne", "jnz") and edge == "fall")):
        return None
    z = seq[j - 1]
    zo = z.operands
    if len(zo) != 2 or zo[0].type != X86_OP_REG or z.reg_name(zo[0].reg) != src:
        return None
    if z.mnemonic in ("test", "or", "and") and zo[1].type == X86_OP_REG and z.reg_name(zo[1].reg) == src:
        return ("imm", 0, False)
    if z.mnemonic == "cmp" and zo[1].type == X86_OP_IMM:
        v, fx = ctx.imm_of(z)
        if v is not None and not fx:
            return ("imm", v & _mask(_width(src)), False)
    return None


def _through(ctx: FlowCtx, j: int, src: str, edge: str, seen: frozenset,
             depth: int) -> tuple[list[Val] | None, str] | None:
    """沿 edge 執行 seq[j] 對 src 的影響:None = 不碰 src(繼續往回);否則是 (值清單或 None, 原因)。"""
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

    seq = ctx.seq
    y = seq[j]
    mn = y.mnemonic
    fam = FAMILY[src]
    where = f"{hex(y.address)} {mn}"
    if mn == "call":
        op = y.operands[0]
        if op.type != X86_OP_IMM:
            return None, f"{where} 間接 call"
        if fam == "eax":
            return ([("ret", op.imm, j)], "") if src == "eax" else (None, f"{where} 之後只取完整 eax 當回傳")
        ok, why = ctx.preserves(op.imm, fam)
        return None if ok else (None, f"{where} {hex(op.imm)} 沒有證明保存 {fam}({why})")
    if mn.startswith(("j", "loop")):
        if mn.startswith("loop") and fam == "ecx":
            return None, f"{where} 改寫 ecx"
        if (mn != "jmp" and j > 0 and y.address not in ctx.targets and y.address not in ctx.indirect):
            v = _refine(ctx, j, src, edge)
            if v is not None:
                return [v], ""
        return None
    if mn.startswith(FLOW):
        return None, f"{where} 在中間"
    written = {y.reg_name(r) for r in y.regs_access()[1]}
    if not written & FAMILY_MEMBERS[fam]:
        return None
    yo = y.operands
    dst = y.reg_name(yo[0].reg) if yo and yo[0].type == X86_OP_REG else None
    w = _width(src)
    if dst == src:
        if mn == "mov" and yo[1].type == X86_OP_IMM:
            v, fx = ctx.imm_of(y)
            if fx and w != 4:
                return None, f"{where} 的位址只取 {src}"
            return [("imm", v & _mask(w), fx)], ""
        if mn in ("xor", "sub") and yo[1].type == X86_OP_REG and y.reg_name(yo[1].reg) == src:
            return [("imm", 0, False)], ""
        if mn in ("or", "and") and yo[1].type == X86_OP_REG and y.reg_name(yo[1].reg) == src:
            return None
        if mn.startswith("set") and w == 1:
            return [("imm", 0, False), ("imm", 1, False)], ""
        if mn == "mov" and yo[1].type == X86_OP_REG and FAMILY.get(y.reg_name(yo[1].reg)):
            return _before(ctx, j, y.reg_name(yo[1].reg), seen, depth)
        if mn == "mov" and yo[1].type == X86_OP_MEM:
            m = ctx.mem_of(y.address)
            if m is not None and yo[1].mem.base == 0 and yo[1].mem.index == 0 and m[1] == w:
                return [("mem", m[0], w)], ""
            return None, f"{where} 由非固定位址的記憶體讀入"
        if mn == "movzx" and yo[1].size < w:
            return [("zx", yo[1].size, 0)], ""
        if mn in ("add", "sub") and yo[1].type == X86_OP_IMM:
            v, fx = ctx.imm_of(y)
            if fx or v is None:
                return None, f"{where} 的立即數有 fixup"
            d = v if mn == "add" else -v
            prev, why = _before(ctx, j, src, seen, depth)
            if prev is None:
                return None, why
            if not prev:
                return None, f"{where} 在迴圈裡累加"
            out: list[Val] = []
            for p in prev:
                if p[0] == "imm" and not p[2]:
                    out.append(("imm", (p[1] + d) & _mask(w), False))
                elif p[0] == "zx":
                    out.append(("zx", p[1], p[2] + d))
                else:
                    return None, f"{where} 加在 {p[0]} 值上"
            return out, ""
        return None, f"{where} 改寫 {src}"
    if dst == fam:      # 只剩部分暫存器(32 位元時 fam == src,上面已處理)
        if mn == "mov" and yo[1].type == X86_OP_IMM:
            v, fx = ctx.imm_of(y)
            if fx:
                return None, f"{where} 的位址只取 {src}"
            return [("imm", (v >> 8) & 0xFF if src.endswith("h") else v & _mask(w), False)], ""
        if mn in ("xor", "sub") and yo[1].type == X86_OP_REG and y.reg_name(yo[1].reg) == fam:
            return [("imm", 0, False)], ""
    return None, f"{where} 改寫 {fam}"


class Preserve:
    """被呼叫的函式有沒有保存某個暫存器族(跨函式;結果快取)。

    從呼叫目標沿控制流程探索可達的指令(落下、直接跳躍、條件跳躍兩邊;`call` 的下一條只在被呼叫者
    可能回傳時才可達;`mov ah, 0x4c` + `int 0x21` 是 DOS 結束、不回傳),只看**走得到 ret 的指令**
    (不回傳的路徑上改寫暫存器不影響呼叫者)。兩種證明,每一種都會說不:

    * 存回:入口的直線序言(`push 立即數` / `call` / `sub esp, 立即數` / `push 暫存器`)在改寫它之前
      push 了它(序言裡先執行的 call 也要保存它),而且每個可達的 ret 前面連續的 `pop` 正好是序言 push 的倒序
      (中間夾 `add esp, 立即數` 可以)—— Watcom 的標準序言 / 結語。
    * 不碰:走得到 ret 的指令沒有一條寫它(含 pop、隱含寫入;`int` 當作全部改寫),其中的 `call 立即數`
      目標也都保存它。

    可達範圍裡有間接 call / jmp 就不判定。遞迴呼叫以「假設成立」處理(最大不動點),只快取不依賴
    假設、或查詢起點本身的結果。堆疊平衡(函式內 push / pop 與 add esp 配對、保存槽不被改寫)假設由
    編譯器保證,不另證。

    Args:
        decode: 線性位址 → 該處的 capstone 指令(需 detail);不在程式碼裡時 None。
    """

    LIMIT = 20000

    def __init__(self, decode: Callable[[int], object | None]) -> None:
        self.decode = decode
        self.memo: dict[tuple[int, str], tuple[bool, str]] = {}
        self.stack: set[tuple[int, str]] = set()
        self.assumed = False
        self._ret: dict[int, bool] = {}
        self._ret_stack: set[int] = set()
        self._graph: dict[int, tuple[dict, dict, str]] = {}

    def __call__(self, e: int, fam: str) -> tuple[bool, str]:
        key = (e, fam)
        if key in self.memo:
            return self.memo[key]
        if key in self.stack:
            self.assumed = True
            return True, "遞迴(假設成立)"
        outer, self.assumed = self.assumed, False
        self.stack.add(key)
        try:
            r = self._check(e, fam)
        finally:
            self.stack.discard(key)
        if not r[0] or not self.assumed or not self.stack:
            self.memo[key] = r
        self.assumed = outer or self.assumed
        return r

    def returns(self, e: int) -> bool:
        """e 開始的程式碼有沒有可達的 ret(遞迴以「會回傳」處理:多算路徑比較保守)。"""
        if e in self._ret:
            return self._ret[e]
        if e in self._ret_stack:
            return True
        self._ret_stack.add(e)
        try:
            nodes, _succ, bad = self.graph(e)
            r = bool(bad) or any(x.mnemonic.startswith(("ret", "iret")) for x in nodes.values())
        finally:
            self._ret_stack.discard(e)
        self._ret[e] = r
        return r

    def graph(self, e: int) -> tuple[dict, dict, str]:
        """從 e 探索:(位址 → 指令, 位址 → 後繼位址清單, 不判定的原因)。"""
        from capstone.x86 import X86_OP_IMM

        if e in self._graph:
            return self._graph[e]
        nodes: dict[int, object] = {}
        succ: dict[int, list[int]] = {}
        bad = ""
        todo = [e]
        while todo and not bad:
            a = todo.pop()
            if a in nodes:
                continue
            x = self.decode(a)
            if x is None:
                bad = f"{hex(a)} 不是程式碼"
                break
            nodes[a] = x
            if len(nodes) > self.LIMIT:
                bad = "可達指令太多"
                break
            mn = x.mnemonic
            nxt = a + x.size
            if mn.startswith(("ret", "iret", "hlt", "ud2")):
                out = []
            elif mn == "jmp" or mn.startswith(("j", "loop")):
                if x.operands[0].type != X86_OP_IMM:
                    bad = f"{hex(a)} 間接 jmp"
                    break
                out = [x.operands[0].imm] + ([] if mn == "jmp" else [nxt])
            elif mn == "call":
                # 間接 call 的目標不知道:假設會回傳(多算路徑比較保守);「不碰」證明遇到它就不判定
                out = [nxt] if x.operands[0].type != X86_OP_IMM or self.returns(x.operands[0].imm) else []
            elif mn == "int" and x.op_str == "0x21" and self._ah4c(nodes, a):
                out = []
            else:
                out = [nxt]
            succ[a] = out
            todo += out
        # `int 0x21` 當結束只在它不是跳躍目標時成立(前一條 mov ah, 0x4c 是唯一前驅)
        tg = {t for a, out in succ.items() for t in out if t != a + nodes[a].size}
        if not bad and any(a in tg for a, x in nodes.items() if x.mnemonic == "int" and not succ.get(a)):
            bad = "DOS 結束的 int 0x21 是跳躍目標"
        self._graph[e] = (nodes, succ, bad)
        return self._graph[e]

    def _ah4c(self, nodes: dict, a: int) -> bool:
        """a 的前一條(已探索、緊鄰)是 `mov ah, 0x4c` / `mov ax, 0x4cNN` / `mov eax, 0x4cNN`。"""
        from capstone.x86 import X86_OP_IMM, X86_OP_REG

        for p, y in nodes.items():
            if p + y.size == a and y.mnemonic == "mov" and len(y.operands) == 2:
                d = y.reg_name(y.operands[0].reg) if y.operands[0].type == X86_OP_REG else None
                v = y.operands[1].imm if y.operands[1].type == X86_OP_IMM else None
                if v is not None and ((d == "ah" and v == 0x4C) or (d in ("ax", "eax") and (v >> 8) & 0xFF == 0x4C)):
                    return True
        return False

    def _check(self, e: int, fam: str) -> tuple[bool, str]:
        from capstone.x86 import X86_OP_IMM, X86_OP_REG

        nodes, succ, bad = self.graph(e)
        if bad:
            return False, bad
        preds: dict[int, list[int]] = {}
        for a, out in succ.items():
            for t in out:
                preds.setdefault(t, []).append(a)
        rets = [a for a, x in nodes.items() if x.mnemonic.startswith(("ret", "iret"))]
        live = set(rets)
        todo = list(rets)
        while todo:
            a = todo.pop()
            for p in preds.get(a, []):
                if p not in live:
                    live.add(p)
                    todo.append(p)
        members = FAMILY_MEMBERS[fam]
        # 存回:入口直線序言 push 了它
        pushed: list[str] = []
        a = e
        while a in nodes and (a == e or len(preds.get(a, [])) == 1):
            x = nodes[a]
            ops = x.operands
            if x.mnemonic == "push" and ops[0].type == X86_OP_REG:
                pushed.append(x.reg_name(ops[0].reg))
            elif x.mnemonic == "push" and ops[0].type == X86_OP_IMM:
                pass
            elif x.mnemonic == "sub" and ops[0].type == X86_OP_REG and x.reg_name(ops[0].reg) == "esp" \
                    and ops[1].type == X86_OP_IMM:
                pass
            elif x.mnemonic == "jmp" and ops[0].type == X86_OP_IMM:
                pass
            elif x.mnemonic == "mov" and "ebp" in pushed and x.op_str == "ebp, esp":
                pass
            elif x.mnemonic == "call" and fam not in pushed:
                if ops[0].type != X86_OP_IMM or not self(ops[0].imm, fam)[0]:
                    break
            elif x.mnemonic != "call":
                break
            if len(succ.get(a, [])) != 1:
                break
            a = succ[a][0]
        if fam in pushed:
            want = list(reversed(pushed))
            for r in rets:
                pops: list[str] = []
                cur = r
                while len(preds.get(cur, [])) == 1:
                    p = preds[cur][0]
                    y = nodes[p]
                    if p + y.size != cur:
                        break
                    yo = y.operands
                    if y.mnemonic == "pop" and yo[0].type == X86_OP_REG:
                        pops.insert(0, y.reg_name(yo[0].reg))
                    elif y.mnemonic == "leave":
                        pops.insert(0, "ebp")
                    elif not (y.mnemonic == "add" and yo[0].type == X86_OP_REG and y.reg_name(yo[0].reg) == "esp"
                              and yo[1].type == X86_OP_IMM):
                        break
                    cur = p
                if pops != want:
                    return False, f"{hex(r)} 的結語 pop {pops} 不是序言 push 的倒序 {want}"
            return True, f"序言 push、{len(rets)} 個 ret 前倒序 pop"
        # 不碰:走得到 ret 的指令都不寫它
        for a in sorted(live):
            x = nodes[a]
            if x.mnemonic == "int":
                return False, f"{hex(a)} int(當作全部改寫)"
            if x.mnemonic == "call":
                if x.operands[0].type != X86_OP_IMM:
                    return False, f"{hex(a)} 間接 call"
                ok, why = self(x.operands[0].imm, fam)
                if not ok:
                    return False, f"{hex(a)} call {hex(x.operands[0].imm)} 不保存({why})"
                continue
            if {x.reg_name(r) for r in x.regs_access()[1]} & members:
                return False, f"{hex(a)} {x.mnemonic} 改寫 {fam}"
        return True, f"走得到 ret 的 {len(live)} 條指令都不寫它"


def rmw_guard(ctx: FlowCtx, k: int) -> tuple:
    """seq[k] 是讀改寫一個固定位址:回傳歸納核對要的資料;不是可核對的樣式就回傳 (None, 原因)。

    * ("xor", 立即數, 寬度):`xor [m], 立即數`。
    * ("wrap", +1 / -1, 條件跳躍, 比較常數, 比較常數在左邊, 寬度):`inc` / `dec [m]` 緊接
      `cmp [m], 立即數`(或 `mov r, [m]` + `cmp r, 立即數`、或 `cmp r, [m]` 且 r 是跨區塊常數)與條件跳躍;
      不跳的那條路在下一條(中間最多夾一條不碰 [m] 的非控制流程指令)就把 [m] 重設(重設值是另一筆寫入,另外核對)。
      跳的那條路上的值 = 舊值 ± 1 且滿足比較條件。
    """
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

    seq = ctx.seq
    x = seq[k]
    m = ctx.mem_of(x.address)
    if m is None or not x.operands or x.operands[0].type != X86_OP_MEM:
        return (None, "不是固定位址的讀改寫")
    wd = m[1]
    if x.mnemonic == "xor":
        v, fx = ctx.imm_of(x)
        if x.operands[1].type != X86_OP_IMM or v is None or fx:
            return (None, "xor 的來源不是立即數")
        return ("xor", v & _mask(wd), wd)
    if x.mnemonic not in ("inc", "dec"):
        return (None, f"{x.mnemonic} 不是 inc / dec / xor")
    d = 1 if x.mnemonic == "inc" else -1
    j = k + 1
    if j + 1 >= len(seq):
        return (None, "後面沒有比較與跳躍")
    y = seq[j]
    yo = y.operands
    rev = False
    if y.mnemonic == "cmp" and ctx.mem_of(y.address) == m and yo[0].type == X86_OP_MEM and yo[1].type == X86_OP_IMM:
        cv, cfx = ctx.imm_of(y)
    elif (y.mnemonic == "mov" and yo[0].type == X86_OP_REG and yo[1].type == X86_OP_MEM and ctx.mem_of(y.address) == m
          and seq[j + 1].mnemonic == "cmp" and seq[j + 1].operands[0].type == X86_OP_REG
          and seq[j + 1].reg_name(seq[j + 1].operands[0].reg) == y.reg_name(yo[0].reg)
          and seq[j + 1].operands[1].type == X86_OP_IMM):
        j += 1
        cv, cfx = ctx.imm_of(seq[j])
    elif y.mnemonic == "cmp" and yo[0].type == X86_OP_REG and yo[1].type == X86_OP_MEM and ctx.mem_of(y.address) == m:
        vals, why = flow_values(ctx, j, y.reg_name(yo[0].reg))
        if vals is None or len(vals) != 1 or vals[0][0] != "imm" or vals[0][2]:
            return (None, f"{hex(y.address)} 比較的暫存器不是單一常數({why})")
        cv, cfx, rev = vals[0][1], False, True
    else:
        return (None, "inc / dec 之後不是比較同一位址")
    if cv is None or cfx:
        return (None, "比較常數有 fixup")
    if j + 1 >= len(seq):
        return (None, "後面沒有條件跳躍")
    jc = seq[j + 1]
    if jc.mnemonic not in _COND:
        return (None, f"{hex(jc.address)} {jc.mnemonic} 不是支援的條件跳躍")
    if any(seq[i].address in ctx.targets or seq[i].address in ctx.indirect for i in range(k + 1, j + 2)):
        return (None, "讀改寫到條件跳躍之間有區塊開頭")
    if j + 2 >= len(seq):
        return (None, "不跳的那條路沒有重設")

    def resets(z: object) -> bool:
        return z.mnemonic == "mov" and z.operands[0].type == X86_OP_MEM and ctx.mem_of(z.address) == m

    n1 = seq[j + 2]
    n2 = seq[j + 3] if j + 3 < len(seq) else None
    if not (resets(n1) or (n2 is not None and not n1.mnemonic.startswith(FLOW) and ctx.mem_of(n1.address) != m
                           and resets(n2))):
        return (None, "不跳的那條路沒有馬上重設")
    return ("wrap", d, jc.mnemonic, cv & _mask(wd), rev, wd)


def allowed_values(a: dict, limit: int = 1 << 16) -> set[int] | None:
    """宣告值域的全部值(列舉 ∪ 範圍 ∪ 0 .. 上限 ∪ 哨兵);超過 limit 個就 None。"""
    out = set(a["set"] or ()) | set(a["sentinel"])
    spans = [a["range"]] if a["range"] is not None else []
    if a["upper"] is not None:
        spans.append((0, a["upper"]))
    for lo, hi in spans:
        if hi - lo + 1 > limit:
            return None
        out |= set(range(lo, hi + 1))
    return out if len(out) <= limit else None


def rmw_bad(g: tuple, a: dict) -> list[str]:
    """讀改寫的歸納核對:舊值取遍宣告值域,寫入後(wrap 取跳的那條路)的值都必須仍在值域內;回傳違反的說明。"""
    vals = allowed_values(a)
    if vals is None:
        return ["值域太大,無法逐值歸納"]
    out = []
    for v in sorted(vals):
        if g[0] == "xor":
            n = (v ^ g[1]) & _mask(g[2])
            if not allowed_ok(a, n):
                out.append(f"舊值 {v} xor {hex(g[1])} = {n}")
        else:
            _k, d, mn, cv, rev, wd = g
            n = (v + d) & _mask(wd)
            if cond_taken(mn, *((cv, n) if rev else (n, cv)), wd) and not allowed_ok(a, n):
                out.append(f"舊值 {v} {'+' if d > 0 else '-'} 1 = {n},{mn} 跳走不重設")
    return out


# ---------------------------------------------------------------- 指標的來源宣告

_SRC_FILE = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9]{1,7}\.DAT|FD[A-Z]{2,6})(?![A-Za-z0-9_.])")
_SRC_MALLOC = re.compile(r"malloc ?\(?(0x[0-9a-f]+)")
_SRC_INDEX = re.compile(r"第 (\d+(?: ?(?:/|或) ?\d+)*) ?(?:號|條)")
# 來源宣告核對的兩種呼叫目標(以命名表的名稱認,不寫死位址)
LOAD_RES = "load_res"
MALLOC = "malloc"


def source_claims(t: str) -> dict:
    """指標型別說明文字裡的來源宣告:{"files": {檔名}, "malloc": {大小}, "index": [資源號, …]};沒有就是空的。

    檔名是 `X.DAT`,或 FD 開頭的裸名(`FDOTHER` → `FDOTHER.DAT`);`malloc(0x20)` / `malloc 0xfa00` 是配置大小;
    `第 N 號` / `第 N 條` / `第 0 / 1 / 2 號` / `第 80 或 88 號` 是資源號(依出現順序)。
    """
    files = {f if f.endswith(".DAT") else f + ".DAT" for f in _SRC_FILE.findall(t)}
    m = _SRC_INDEX.search(t)
    return {"files": files, "malloc": {int(x, 16) for x in _SRC_MALLOC.findall(t)},
            "index": [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []}


def _cstr(f: "Facts", a: int, limit: int = 32) -> str | None:
    """a 處的 C 字串(latin-1);limit byte 內沒有 NUL 或不在檔內頁時回傳 None。"""
    for n in range(limit, 0, -1):
        b = f.image(a, n)
        if b is not None:
            return b.split(b"\0")[0].decode("latin-1") if b"\0" in b else None
    return None


def check_sources(c: dict, calls: list[tuple[int, int, int | None, list[Arg] | None]], f: "Facts",
                  where: str, res: dict) -> None:
    """把 `source_claims` 對函式回傳寫入核對;結果寫進 res["fail"] / res["note"] / res["src_checked"]。

    calls 元素是 (寫入指令, 元素索引, 呼叫目標, 參數)。每一項都會說不:
    * 檔名:每個 load_res 寫入的第 1 個參數(fixup 指向的 C 字串)必須是宣告的檔名之一。
    * 資源號:load_res 的第 3 個參數是常數時必須在宣告裡;陣列且資源號個數 = 元素數時,第 k 格必須是第 k 個號碼;
      宣告的每個號碼都要有載入點。
    * malloc:常數大小必須在宣告裡;宣告的每個大小都要有配置點。
    參數取不到或不是常數的只記錄,不算通過也不算失敗。
    """
    sc = c.get("source")
    if not sc:
        return
    seen_idx: set[int] = set()
    seen_size: set[int] = set()
    vague = 0
    other = 0
    loads = 0
    for ins, k, callee, args in calls:
        name = f.names.get(callee) if callee is not None else None
        if (name not in (LOAD_RES, MALLOC) or (name == MALLOC and not sc["malloc"])
                or (name == LOAD_RES and not sc["files"] and not sc["index"])):
            other += 1
            continue
        loads += name == LOAD_RES
        if args is None:
            vague += 1
            continue
        if name == LOAD_RES:
            fv, ffx, _how = args[0]
            fname = _cstr(f, fv) if ffx and fv is not None else None
            if sc["files"]:
                res["src_checked"] += 1
                if fname is None:
                    vague += 1
                elif fname.upper() not in sc["files"]:
                    res["fail"].append(f"{where}: {hex(ins)} 由 load_res 載入 {fname!r},type 寫的是 {sorted(sc['files'])}")
            iv, ifx, _how = args[2]
            if sc["index"]:
                res["src_checked"] += 1
                if iv is None or ifx:
                    vague += 1
                    continue
                seen_idx.add(iv)
                want = ([sc["index"][k]] if c["count"] == len(sc["index"]) > 1 else sc["index"])
                if iv not in want:
                    res["fail"].append(f"{where}: {hex(ins)} 載入第 {iv} 號(第 {k} 格),type 寫的是 {want}")
        elif sc["malloc"]:
            res["src_checked"] += 1
            sv, sfx, _how = args[0]
            if sv is None or sfx:
                vague += 1
                continue
            seen_size.add(sv)
            if sv not in sc["malloc"]:
                res["fail"].append(f"{where}: {hex(ins)} malloc({hex(sv)}),type 寫的是 {[hex(x) for x in sorted(sc['malloc'])]}")
    for i in sorted(set(sc["index"]) - seen_idx):
        res["fail"].append(f"{where}: type 寫第 {i} 號,但沒有任何 load_res 寫入點載入它")
    for s in sorted(sc["malloc"] - seen_size):
        res["fail"].append(f"{where}: type 寫 malloc {hex(s)},但沒有任何寫入點以這個大小配置")
    if vague:
        res["note"].append(f"來源宣告:{vague} 個參數不是常數或取不到,未核對")
    if other:
        res["note"].append(f"來源宣告:{other} 筆回傳來自宣告沒寫的函式種類,未核對")
    if sc["files"] and not loads:
        res["note"].append(f"來源宣告:檔名 {sorted(sc['files'])} 沒有 load_res 寫入點,未核對")


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
        call_src: 寫入位址 → (呼叫目標, 參數或 None):`mov [m], eax` 的值是那個函式的回傳值(call_source)。
        names: 呼叫目標 → 函式名稱(命名表;來源宣告只認 load_res / malloc)。
        flow_src: 寫入位址 → flow_values 的結果((值清單或 None, 原因);("ret", …) 的第 3 項已換成參數清單或 None)。
        rmw_src: 寫入位址 → rmw_guard 的結果。
        rtypes: 已登錄區段起點 → (size, type)(核對「複製自別段」時用)。
    """

    def __init__(self, image: Callable[[int, int], bytes | None], zeroed: list[tuple[int, int]],
                 fixups: dict[int, int], entries: set[int], accesses: list | tuple,
                 insn: Callable[[int], Insn], regions: list[tuple[int, int]],
                 reg_src: dict[int, tuple[int | None, bool, str]] | None = None,
                 call_src: dict[int, tuple[int, list[Arg] | None]] | None = None,
                 names: dict[int, str] | None = None,
                 flow_src: dict[int, tuple[list[Val] | None, str]] | None = None,
                 rmw_src: dict[int, tuple] | None = None,
                 rtypes: dict[int, tuple[int, str]] | None = None) -> None:
        self.image = image
        self.zeroed = zeroed
        self.fixups = fixups
        self.entries = entries
        self.accesses = accesses
        self.insn = insn
        self.regions = regions
        self.reg_src = reg_src or {}
        self.call_src = call_src or {}
        self.names = names or {}
        self.flow_src = flow_src or {}
        self.rmw_src = rmw_src or {}
        self.rtypes = rtypes or {}


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

def _init_ok(c: dict, f: Facts, start: int, size: int, addr: int) -> bool:
    """addr 那一格的初值合不合宣告(歸納的起點):指標是 0、檔內 fixup 或宣告的旗標值;值域型別要在值域內。"""
    src, init = init_source(f, start, size)
    if init is None:
        return False
    off = addr - start
    v = int.from_bytes(init[off:off + c["elem"]], "little")
    if c.get("pointer"):
        return v == 0 or (src == "file" and addr in f.fixups) or v in c.get("pointer_flags", ())
    return "allowed" in c and allowed_ok(c["allowed"], v)


def copy_ok(c: dict, addr: int, width: int, start: int, end: int, f: Facts) -> tuple[bool, str]:
    """寫入的值是固定位址 addr(寬 width)的舊值:歸納成立就 (True, 說明),否則 (False, 原因)。

    * 同一段(同一陣列的元素,對齊、同寬):舊值本來就要合宣告;歸納的起點是初值,初值也要合宣告。
    * 別的已登錄區段(對齊、同寬、初值合它自己的宣告):本段是指標 → 對方也要是指標;
      本段是值域 → 對方的值域(全部值)要落在本段值域內。
    未登錄的位址、寬度不同、值域不包含都不算。結論依賴來源段的宣告成立(來源段的寫入同樣由本工具核對)。
    """
    if start <= addr < end:
        if (addr - start) % c["elem"] or width != c["elem"]:
            return False, "同段但沒有對齊元素"
        return (True, "自身舊值") if _init_ok(c, f, start, end - start, addr) else (False, "初值不合宣告")
    hit = [(s, sz, ty) for s, (sz, ty) in f.rtypes.items() if s <= addr < s + sz]
    if not hit:
        return False, f"複製自未登錄的 {hex(addr)}"
    s, sz, ty = hit[0]
    c2 = parse_type(ty, sz)
    if c2["kind"] == "unparsed" or (addr - s) % c2["elem"] or width != c2["elem"]:
        return False, f"{hex(addr)} 的宣告寬度不同"
    if not _init_ok(c2, f, s, sz, addr):
        return False, f"{hex(s)} 的初值不合它的宣告"
    if c.get("pointer"):
        return (True, f"複製自指標 {hex(s)}") if c2.get("pointer") else (False, f"{hex(s)} 不是指標")
    if "allowed" in c and "allowed" in c2:
        vals = allowed_values(c2["allowed"])
        if vals is not None and all(allowed_ok(c["allowed"], v) for v in vals):
            return True, f"複製自 {hex(s)}(值域包含)"
    return False, f"{hex(s)} 的值域不在本段值域內"


def flow_verdict(c: dict, vals: list[Val], f: Facts, start: int, end: int, width: int, where: str, ins: int,
                 k: int, res: dict, calls: list) -> bool:
    """跨區塊值逐一核對:全部值都判定得了才回傳 True(違反寫進 res["fail"]),否則 False(算未判定,不寫失敗)。

    常數 → 值域 / 指標規則;回傳 → 指標才收(交給來源宣告核對);舊值 → copy_ok;
    movzx(+ 常數) → 與 type 的式子(`byte + 2`)相同、或整個範圍在值域內;type 有式子而兩者都不成立 → 失敗。
    """
    fails: list[str] = []
    rets: list[Val] = []
    for v in vals:
        if v[0] == "imm":
            x = v[1] & _mask(width)
            if c.get("pointer"):
                if x != 0 and not v[2] and x not in c.get("pointer_flags", ()):
                    fails.append(f"{where}: 指標以跨區塊常數 {hex(x)} 寫入({hex(ins)}),既不是 0 也沒有 fixup")
            elif not allowed_ok(c["allowed"], x):
                fails.append(f"{where}: {hex(ins)} 寫入跨區塊常數 {x}({hex(x)}),不在宣告值域內")
        elif v[0] == "ret":
            if not c.get("pointer"):
                return False
            rets.append(v)
        elif v[0] == "mem":
            if not copy_ok(c, v[1], v[2], start, end, f)[0]:
                return False
        elif v[0] == "zx" and not c.get("pointer"):
            a = c["allowed"]
            form = a.get("formula", set())
            if (v[1], v[2]) in form:
                continue
            if all(allowed_ok(a, (v[2] + n) & _mask(width)) for n in range(1 << (8 * v[1]))):
                continue
            if not form:
                return False
            fails.append(f"{where}: {hex(ins)} 寫入 movzx {v[1]} byte + {v[2]},type 的式子是 {sorted(form)}、值域也不包含")
        else:
            return False
    res["fail"] += fails
    for v in rets:
        calls.append((ins, k, v[1], v[2]))
    for v in vals:
        res["flow_vals"][v[0]] = res["flow_vals"].get(v[0], 0) + 1
    return True


def check_region(r: dict, f: Facts) -> dict:
    """核對一段;回傳 {"claim", "fail": [...], "note": [...], "init", "imm_checked", "undetermined", "narrow"}。"""
    start = int(r["start"], 16)
    size = r["size"]
    end = start + size
    c = parse_type(r.get("type", ""), size)
    res: dict = {"claim": c, "fail": [], "note": [], "imm_checked": 0, "via_reg": 0, "undetermined": 0, "narrow": [],
                 "call_ret": 0, "src_checked": 0, "flow": 0, "flow_vals": {}, "inductive": 0}
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

    # 值域與指標的立即數寫入;函式回傳的寫入另計,並對 type 的來源宣告核對
    calls: list[tuple[int, int, int | None, list[Arg] | None]] = []
    for ins, t, width, rw in writes:
        mn, imm, imm_fx = f.insn(ins)
        if mn == "mov" and imm is None and ins in f.call_src:
            res["call_ret"] += 1
            calls.append((ins, (t - start) // c["elem"], *f.call_src[ins]))
            continue
        ranged = c.get("pointer") or "allowed" in c
        fv = f.flow_src.get(ins, (None, ""))[0]
        if (ranged and mn == "mov" and imm is None and fv is not None
                and flow_verdict(c, fv, f, start, end, width, where, ins, (t - start) // c["elem"], res, calls)):
            res["flow"] += 1
            continue
        g = f.rmw_src.get(ins, (None,))
        if g[0] is not None and "allowed" in c and allowed_values(c["allowed"]) is not None:
            res["inductive"] += 1
            bad = rmw_bad(g, c["allowed"])
            if bad:
                res["fail"].append(f"{where}: {hex(ins)} 讀改寫的歸納不成立:{'; '.join(bad[:3])}")
            continue
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
    check_sources(c, calls, f, where, res)
    res["note"] = [n for n in res["note"] if n]
    return res


# ---------------------------------------------------------------- 讀原版

def load_facts() -> tuple[Facts, list[dict]]:
    import disasm_le
    import function_inventory as FI
    import le_xref
    import re_coverage as R
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM, X86_OP_REG

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
    inv_entries = json.loads(R.INVENTORY.read_text(encoding="utf-8"))["entries"]
    inv = sorted((int(e["addr"], 16), e["span_upper"]) for e in inv_entries)
    argc = {int(e["addr"], 16): e.get("argc") for e in inv_entries}
    sites = sorted({ins for ins, _t, _w, rw, kind, _ix in w["ctx"].accesses if kind == "mem" and "w" in rw})
    reg_src: dict[int, tuple[int | None, bool, str]] = {}
    call_src: dict[int, tuple[int, list[Arg] | None]] = {}
    flow_src: dict[int, tuple[list[Val] | None, str]] = {}
    rmw_src: dict[int, tuple] = {}
    cache: dict[int, tuple[list, dict[int, int], set[int]]] = {}
    # 直接定址(沒有基底 / 索引)的存取:指令 → (目標, 寬度)
    direct: dict[int, tuple[int, int]] = {}
    for ins, t, wd, _rw, kind, ix in w["ctx"].accesses:
        if kind == "mem" and not ix:
            direct.setdefault(ins, (t, wd))
    # 全部函式的直接跳躍(來源, 目標):函式外跳進來的位址,前驅在別的函式裡看不到
    md0 = Cs(CS_ARCH_X86, CS_MODE_32)
    jumps: list[tuple[int, int]] = []
    for e, n in inv:
        for x in disasm_le.sweep_range(md0, code, cbase, e, e + n):
            if not isinstance(x, tuple) and x.mnemonic.startswith(("j", "loop")) and x.op_str.startswith("0x"):
                jumps.append((x.address, int(x.op_str, 16)))
    dcache: dict[int, object | None] = {}

    def decode(a: int) -> object | None:
        if a not in dcache:
            o = a - cbase
            dcache[a] = next(md.disasm(code[o:o + 16], a), None) if o in range(len(code)) else None
        return dcache[a]

    keep = Preserve(decode)
    ind_of: dict[int, set[int]] = {}
    for a in sites:
        owner = [(e, n) for e, n in inv if e <= a < e + n]
        if not owner:
            continue
        e, n = max(owner)
        if e not in cache:
            seq = [x for x in disasm_le.sweep_range(md, code, cbase, e, e + n) if not isinstance(x, tuple)]
            ext = {t for s0, t in jumps if e <= t < e + n and not e <= s0 < e + n}
            cache[e] = (seq, {x.address: k for k, x in enumerate(seq)}, block_starts(seq, e, e + n, fx_targets) | ext)
            ind_of[e] = {t for t in fx_targets if e <= t < e + n} | ext
        seq, pos, tg = cache[e]
        if a in pos:
            reg_src[a] = reg_const(seq, pos[a], tg, imm_of)
            if reg_src[a][0] is None:
                callee, args, _why = call_source(seq, pos[a], tg, imm_of, argc.get)
                if callee is not None:
                    call_src[a] = (callee, args)
            if reg_src[a][0] is not None or a in call_src:
                continue
            ctx = FlowCtx(seq, tg, ind_of[e], imm_of, direct.get, keep)
            x = seq[pos[a]]
            ops = x.operands
            if x.mnemonic == "mov" and len(ops) == 2 and ops[1].type == X86_OP_REG:
                vals, why = flow_values(ctx, pos[a], x.reg_name(ops[1].reg))
                if vals is not None:
                    vals = [("ret", v[1], None if argc.get(v[1]) is None
                             else call_args(seq, v[2], argc[v[1]], tg, imm_of)) if v[0] == "ret" else v
                            for v in vals]
                flow_src[a] = (vals, why)
            elif x.mnemonic in ("inc", "dec", "xor"):
                rmw_src[a] = rmw_guard(ctx, pos[a])
    names = FI.real_names()     # Facts 只用 .get 查呼叫目標(call_src / flow_src 的 ret)的名稱

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
    rtypes = {int(r["start"], 16): (r["size"], r.get("type", "")) for r in dm["regions"]}
    facts = Facts(image, zeroed, fx_all, set(w["funcs"]), w["ctx"].accesses, insn, regions, reg_src, call_src, names,
                  flow_src, rmw_src, rtypes)
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
          f"函式回傳 {sum(x['call_ret'] for _r, x in ranged)} 筆、"
          f"未判定寫入 {sum(x['undetermined'] for _r, x in ranged)} 筆")
    fv = {k: sum(x["flow_vals"].get(k, 0) for _r, x in ranged) for k in ("imm", "ret", "mem", "zx")}
    print(f"    跨區塊 / 跨 call 判定 {sum(x['flow'] for _r, x in ranged)} 筆(值:常數 {fv['imm']}、"
          f"函式回傳 {fv['ret']}、固定位址舊值 {fv['mem']}、movzx 式子 {fv['zx']});"
          f"讀改寫歸納 {sum(x['inductive'] for _r, x in ranged)} 筆")
    srcd = [(r, x) for r, x in out if x["claim"].get("source")]
    print(f"  來源宣告(load_res 檔名 / 資源號、malloc 大小) {len(srcd)} 段:參數核對 "
          f"{sum(x['src_checked'] for _r, x in srcd)} 項")
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
                if a.get("formula"):
                    extra += f" 式子={sorted(a['formula'])}"
            print(f"{r['start']:>8} {r['size']:4d} {c['kind']:10} init={x['init']:6} 立即數 {x['imm_checked']} "
                  f"(暫存器 {x['via_reg']}) 回傳 {x['call_ret']}(來源核對 {x['src_checked']}) "
                  f"跨區塊 {x['flow']} 歸納 {x['inductive']} 未判定 {x['undetermined']} 窄 {len(x['narrow'])}{extra}")
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
    mem[0x180:0x1a0] = b"A" * 32                        # _cstr:第 33 byte 才是 NUL
    mem[0x1fd:0x1ff] = b"AA"                            # _cstr:映像最後 3 byte = "AA\0"

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

    # 函式回傳:call_source / call_args(push 0x20;call 0x200;add esp, 4;mov [0x2000], eax)
    def cs_(hexs: str, argc: dict[int, int] | None = None, targets: set[int] | None = None,
            fxs: dict[int, int] | None = None) -> tuple[int | None, list | None, str]:
        seq = list(cs.disasm(bytes.fromhex(hexs), 0x100))
        assert sum(x.size for x in seq) == len(hexs) // 2, hexs

        def imm(x: object) -> tuple[int | None, bool]:
            v = next((op.imm for op in x.operands if op.type == X86_OP_IMM), None)
            site = x.address + x.imm_offset
            return (fxs[site], True) if fxs and site in fxs else (v, False)
        return call_source(seq, len(seq) - 1, targets or set(), imm, (argc if argc is not None else {0x200: 1}).get)

    call200 = "e8f9000000"                              # 位於 0x102 時 → 0x200
    check("(c1) push 0x20;call;add esp;mov [m], eax → (0x200, [0x20])",
          cs_("6a20" + call200 + "83c404" + st) == (0x200, [(0x20, False, "立即數")], ""))
    check("(c2) argc 不明 → 目標照回、參數 None", cs_("6a20" + call200 + "83c404" + st, argc={}) == (0x200, None, ""))
    check("(c3) call 與寫入之間改寫 eax(inc / mov eax, 5 / mov al)→ 不判定",
          all(cs_("6a20" + call200 + mid + st)[0] is None for mid in ("40", "b805000000", "b005")))
    check("(c4) 之間有分支 / 寫入是區塊開頭 / 間接 call / 來源不是 eax → 不判定",
          cs_("6a20" + call200 + "eb00" + st)[0] is None
          and cs_("6a20" + call200 + "83c404" + st, targets={0x10a})[0] is None
          and cs_("6a20" + "ffd0" + st)[0] is None
          and cs_("6a20" + call200 + "891d00200000")[0] is None)
    check("(c5) 之間改寫別的暫存器 → 略過,仍是 0x200",
          cs_("6a20" + call200 + "8b1d00300000" + st)[0] == 0x200)
    check("(c6) 往回到開頭沒有 call → 不判定", cs_("b805000000" + st)[0] is None)
    # 3 個參數:push [m];push ebx(mov ebx, 7);push 0x1000(fixup → 0x51a4d);call
    three = "bb07000000" + "ff3500300000" + "53" + "6800100000" + "e8ea000000" + st
    got = cs_(three, argc={0x200: 3}, fxs={0x10d: 0x51a4d})
    check("(c7) 參數順序 = 最後一個 push 是第 1 個;立即數 fixup 取目標;暫存器常數;記憶體是變數",
          got == (0x200, [(0x51a4d, True, "立即數"), (7, False, "暫存器常數"), (None, False, "記憶體")], ""))
    check("(c8) push 之間有 add esp / pop / 分支 / 區塊開頭,或 push 不夠 → 參數 None",
          all(cs_(h, argc={0x200: 2}, targets=tg)[1] is None and cs_(h, argc={0x200: 2}, targets=tg)[0] == 0x200
              for h, tg in (("6a01" + "83c404" + "6a02" + "e8f4000000" + st, None),
                            ("6a01" + "59" + "6a02" + "e8f6000000" + st, None),
                            ("6a01" + "7400" + "6a02" + "e8f5000000" + st, None),
                            ("6a01" + "6a02" + "e8f7000000" + st, {0x102}),
                            ("6a02" + call200 + st, None))))
    check("(c9) push 暫存器判定不出 → 值 None 並帶原因",
          cs_("53" + "e8fa000000" + st)[1][0][:2] == (None, False) and cs_("53" + "e8fa000000" + st)[1][0][2] != "")

    # 來源宣告的文法與核對(0x700 = load_res、0x704 = malloc、0x708 = 其他;0x1000 是 "BG.DAT")
    sc = source_claims("dword 指標[3](BG.DAT 第 0 / 1 / 2 號;FDOTHER 第 80 或 88 號,malloc(0x20)、malloc 0xfa00)")
    check("(s1) 文法:檔名(含裸名)、malloc 兩種寫法、資源號依序",
          sc == {"files": {"BG.DAT", "FDOTHER.DAT"}, "malloc": {0x20, 0xfa00}, "index": [0, 1, 2]})
    check("(s2) 文法:沒有宣告 → 空;小寫 / 數字開頭 / FD2 不算檔名;非數字的第 … 條不算",
          not any(source_claims("dword 指標(fd.dat、2BG.DAT、FD2、FDFIELD.DATX、第 章節×3 條)").values())
          and source_claims("指標 → FDTXT.DAT 第 0 條")["index"] == [0])
    check("(s3) 只有指標型別收來源宣告", "source" in parse_type("dword 指標(BG.DAT 第 2 號)", 4)
          and "source" not in parse_type("dword(BG.DAT 第 2 號 0 .. 6)", 4)
          and "source" not in parse_type("dword 指標(畫面)", 4))
    for a in range(0x910, 0x920):
        imms[a] = ("mov", None, False)
    nm = {0x700: LOAD_RES, 0x704: MALLOC, 0x708: "other"}
    bg = (0x1000, True, "立即數")
    var = (None, False, "記憶體")

    def src(t: str, cl: dict[int, tuple[int, list | None]], size: int = 4) -> dict:
        acc = [(ins, 0x1070 + 4 * (k % (size // 4)), 4, "w", "mem", False) for k, ins in enumerate(cl)]
        return check_region(reg(0x1070, size, t), Facts(image, [], fx, ents, acc, lambda a: imms.get(a, ("", None, False)),
                                                        [], {}, cl, nm))

    ok = src("dword 指標(BG.DAT 第 2 號)", {0x910: (0x700, [bg, var, (2, False, "")])})
    check("(s4) 檔名與資源號相符 → 0;回傳 1、來源核對 2、不算未判定、沒有記錄",
          (ok["fail"], ok["call_ret"], ok["src_checked"], ok["undetermined"], ok["note"]) == ([], 1, 2, 0, []))
    bad = src("dword 指標(BG.DAT 第 2 號)", {0x910: (0x700, [bg, var, (3, False, "")])})["fail"]
    check("(s5) 資源號不同 → 失敗(且宣告的第 2 號沒有載入點也失敗)", len(bad) == 2)
    check("(s6) 檔名不同 → 失敗",
          src("dword 指標(DATO.DAT 第 2 號)", {0x910: (0x700, [bg, var, (2, False, "")])})["fail"] != [])
    vg = src("dword 指標(BG.DAT 第 2 號)", {0x910: (0x700, [(0x1000, False, "立即數"), var, var])})
    check("(s7) 檔名沒有 fixup、資源號是變數 → 未核對的記錄,不失敗以外還要報『沒有載入點』",
          vg["note"] == ["來源宣告:2 個參數不是常數或取不到,未核對"] and len(vg["fail"]) == 1)
    arr = "dword 指標[3](BG.DAT 第 0 / 1 / 2 號)"
    cl3 = {0x910 + k: (0x700, [bg, var, (k, False, "")]) for k in range(3)}
    check("(s8) 陣列逐格對號碼 → 0", src(arr, cl3, 12)["fail"] == [])
    sw = {**cl3, 0x911: (0x700, [bg, var, (0, False, "")])}
    check("(s9) 第 1 格載入第 0 號 → 失敗", src(arr, sw, 12)["fail"] != [])
    two = {0x910: (0x700, [bg, var, (1, False, "")]), 0x911: (0x700, [bg, var, (0, False, "")])}
    check("(s9b) 2 格陣列號碼對調 → 失敗(號碼數 = 元素數 = 2 也逐格對)",
          src("dword 指標[2](BG.DAT 第 0 / 1 號)", two, 8)["fail"] != [])
    either = "dword 指標(BG.DAT 第 80 或 88 號)"
    check("(s10) 純量的多個號碼:任一相符,但每個號碼都要有載入點",
          src(either, {0x910: (0x700, [bg, var, (88, False, "")])})["fail"] != []
          and src(either, {0x910: (0x700, [bg, var, (88, False, "")]),
                           0x911: (0x700, [bg, var, (80, False, "")])})["fail"] == [])
    mal = "dword 指標(畫布,malloc 0xfa00)"
    check("(s11) malloc 大小相符 → 0;不同 → 失敗;沒有配置點 → 失敗",
          src(mal, {0x910: (0x704, [(0xfa00, False, "")])})["fail"] == []
          and src(mal, {0x910: (0x704, [(0xfa01, False, "")])})["fail"] != []
          and src(mal, {0x910: (0x708, [(0xfa00, False, "")])})["fail"] != [])
    oth = src("dword 指標(BG.DAT)", {0x910: (0x708, None), 0x911: (0x704, [(0x20, False, "")])})
    check("(s12) 其他函式 / 宣告沒寫 malloc 的配置 → 記錄、不失敗;沒有 load_res → 檔名未核對的記錄",
          oth["fail"] == [] and oth["call_ret"] == 2 and oth["src_checked"] == 0
          and oth["note"] == ["來源宣告:2 筆回傳來自宣告沒寫的函式種類,未核對",
                              "來源宣告:檔名 ['BG.DAT'] 沒有 load_res 寫入點,未核對"])
    check("(s13) 參數 None → 記錄未核對 1 個", src("dword 指標(BG.DAT 第 2 號)", {0x910: (0x700, None)})["note"]
          == ["來源宣告:1 個參數不是常數或取不到,未核對"])
    mv = src(mal, {0x910: (0x704, [var])})
    check("(s13b) malloc 大小是變數 → 記錄未核對 1 個,且宣告的大小沒有配置點 → 失敗",
          mv["note"] == ["來源宣告:1 個參數不是常數或取不到,未核對"] and len(mv["fail"]) == 1)
    check("(s14) 字串讀取:NUL 結尾、沒有 NUL、不在檔內",
          (_cstr(facts([]), 0x1000), _cstr(facts([]), 0x1000, 4), _cstr(facts([]), 0x3000))
          == ("BG.DAT", None, None))
    check("(s14b) 字串讀取的邊界:32 byte 內沒有 NUL → None、31 byte + NUL → 字串;映像尾端只剩 1 / 3 byte 也讀",
          (_cstr(facts([]), 0x1180), _cstr(facts([]), 0x1181), _cstr(facts([]), 0x11ff), _cstr(facts([]), 0x11fd))
          == (None, "A" * 31, "", "AA"))

    # 跨區塊值分析(flow_values):合成程式碼從 0x100 起;寫入點是 [0x2000]
    from capstone.x86 import X86_OP_MEM

    def j8(op: int, at: int, to: int) -> str:
        """位於 at、目標 to 的 2 byte 短跳躍。"""
        return bytes((op, (to - at - 2) & 0xFF)).hex()

    def rel32(op: str, at: int, to: int) -> str:
        """位於 at、目標 to 的 5 byte call / jmp。"""
        return op + struct.pack("<i", to - at - 5).hex()

    def ctx_of(hexs: str, base: int = 0x100, extra: set[int] | None = None, ind: set[int] | None = None,
               keep: Callable[[int, str], tuple[bool, str]] | None = None,
               fxs: dict[int, int] | None = None) -> FlowCtx:
        seq = list(cs.disasm(bytes.fromhex(hexs), base))
        assert sum(x.size for x in seq) == len(hexs) // 2, hexs

        def imm(x: object) -> tuple[int | None, bool]:
            v = next((op.imm for op in x.operands if op.type == X86_OP_IMM), None)
            site = x.address + x.imm_offset
            return (fxs[site], True) if fxs and site in fxs else (v, False)
        direct = {x.address: (op.mem.disp, op.size) for x in seq for op in x.operands
                  if op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0}
        tg = block_starts(seq, base, base + len(hexs) // 2, set()) | (extra or set())
        return FlowCtx(seq, tg, ind or set(), imm, direct.get, keep or (lambda e, fam: (False, "合成:不保存")))

    def fl(hexs: str, at: int = -1, **kw: object) -> tuple[list | None, str]:
        ctx = ctx_of(hexs, **kw)
        k = at % len(ctx.seq)
        x = ctx.seq[k]
        return flow_values(ctx, k, x.reg_name(x.operands[1].reg))

    def one(hexs: str, **kw: object) -> list | None:
        return fl(hexs, **kw)[0]

    def keep_all(e: int, fam: str) -> tuple[bool, str]:
        return True, "合成:保存"

    WA, WS, WL, WH = "a300200000", "893500200000", "a200200000", "882500200000"
    I0 = [("imm", 0, False)]
    check("(f1) test eax, eax;jne 不跳 → eax = 0;je 不跳 → 不判定",
          fl("85c0" + j8(0x75, 0x102, 0x109) + WA) == (I0, "") and one("85c0" + j8(0x74, 0x102, 0x109) + WA) is None)
    check("(f2) cmp eax, 5;jne 不跳 → 5;cmp eax, −1 → 0xffffffff;jg 不跳 / 比較常數有 fixup → 不判定",
          one("83f805" + j8(0x75, 0x103, 0x10a) + WA) == [("imm", 5, False)]
          and one("83f8ff" + j8(0x75, 0x103, 0x10a) + WA) == [("imm", 0xFFFFFFFF, False)]
          and one("83f805" + j8(0x7f, 0x103, 0x10a) + WA) is None
          and one("3d00300000" + j8(0x75, 0x105, 0x10c) + WA, fxs={0x101: 0x53000}) is None)
    check("(f3) 比較的是別的暫存器 / 只比 al 而寫 eax → 不判定;or / and 自己 → 0;test al 寫 al → 0",
          one("85db" + j8(0x75, 0x102, 0x109) + WA) is None
          and one("84c0" + j8(0x75, 0x102, 0x109) + WA) is None
          and all(one(h + j8(0x75, 0x102, 0x109) + WA) == I0 for h in ("09c0", "21c0"))
          and one("84c0" + j8(0x75, 0x102, 0x109) + WL) == I0)
    check("(f4) je 跳到的區塊開頭 → 0;前一條會落下來 → 多一條不知道的路 → 不判定;jne 跳過來 → 不判定",
          one("85c0" + j8(0x74, 0x102, 0x105) + "c3" + WA) == I0
          and one("85c0" + j8(0x74, 0x102, 0x105) + "90" + WA) is None
          and one("85c0" + j8(0x75, 0x102, 0x105) + "c3" + WA) is None)
    two = "85c9" + j8(0x74, 0x102, 0x10b) + "b801000000" + j8(0xeb, 0x109, 0x110)
    got = one(two + "b802000000" + WA)
    check("(f5) 兩條路各是 1、2 → {1, 2};其中一條是 inc → 不判定",
          got is not None and sorted(got) == [("imm", 1, False), ("imm", 2, False)] and one(two + "4090909090" + WA) is None)
    loop = "be03000000" + WS
    acc6 = fl(loop + "83c601" + j8(0x75, 0x10e, 0x105), at=1)
    check("(f6) 迴圈裡不改寫 → 只有進入時的 3;迴圈裡 mov esi, 4 → {3, 4};迴圈裡 add esi, 1 → 不判定(累加)",
          fl(loop + "49" + j8(0x75, 0x10c, 0x105), at=1) == ([("imm", 3, False)], "")
          and sorted(one(loop + "be04000000" + j8(0x75, 0x110, 0x105), at=1) or []) == [("imm", 3, False),
                                                                                       ("imm", 4, False)]
          and acc6[0] is None and "累加" in acc6[1])
    check("(f6b) 只有迴圈路徑(沒有進入點)→ 不判定", one("c3" + WS + "49" + j8(0x75, 0x108, 0x101), at=1) is None)
    base1 = "85c0" + j8(0x75, 0x102, 0x109) + WA
    check("(f7) 寫入點間接進入 / jne 本身是區塊開頭或間接進入 → 不判定;寫入點是函式開頭的跳躍目標 → 不判定",
          one(base1, ind={0x104}) is None and one(base1, extra={0x102}) is None and one(base1, ind={0x102}) is None
          and one(WA + j8(0xeb, 0x105, 0x100), at=0) is None)
    check("(f8) xor esi, esi;call;寫 esi:被呼叫者保存 → 0、沒證明 → 不判定",
          one("31f6" + rel32("e8", 0x102, 0x300) + WS, keep=keep_all) == I0
          and one("31f6" + rel32("e8", 0x102, 0x300) + WS) is None)
    check("(f9) call 之後寫 eax → 回傳 (目標, call 的索引);寫 al / 間接 call → 不判定",
          one("b805000000" + rel32("e8", 0x105, 0x300) + WA) == [("ret", 0x300, 1)]
          and one("b805000000" + rel32("e8", 0x105, 0x300) + WL) is None
          and one("b805000000" + "ffd3" + WA) is None)
    check("(f10) mov eax, ebx(= 7)→ 7;mov eax / al, [固定位址] → 舊值;mov eax, [ebx] / 來源 esp → 不判定",
          one("bb07000000" + "89d8" + WA) == [("imm", 7, False)] and one("a100300000" + WA) == [("mem", 0x3000, 4)]
          and one("a000300000" + WL) == [("mem", 0x3000, 1)] and one("8b03" + WA) is None
          and one("892500200000") is None)
    check("(f11) movzx byte + 2 → zx(1, 2);movzx word − 2 → zx(2, −2);sete al → {0, 1};sete al 但寫 eax → 不判定",
          one("0fb603" + "83c002" + WA) == [("zx", 1, 2)] and one("0fb703" + "83e802" + WA) == [("zx", 2, -2)]
          and one("0f94c0" + WL) == [("imm", 0, False), ("imm", 1, False)] and one("0f94c0" + WA) is None)
    check("(f12) 5 + 3 = 8、5 − 3 = 2、1 − 3 以 32 位元繞回;fixup 常數 / 立即數有 fixup / 舊值再加 → 不判定",
          one("b805000000" + "83c003" + WA) == [("imm", 8, False)]
          and one("b805000000" + "83e803" + WA) == [("imm", 2, False)]
          and one("b801000000" + "83e803" + WA) == [("imm", 0xFFFFFFFE, False)]
          and one("b800300000" + "83c003" + WA, fxs={0x101: 0x53000}) is None
          and one("b805000000" + "0500300000" + WA, fxs={0x106: 0x53000}) is None
          and one("a100300000" + "83c003" + WA) is None
          and fl("a100300000" + "83c003" + WA)[1].endswith("加在 mem 值上"))
    check("(f13) mov eax, fixup → 目標帶 fixup;mov al, 5 → 5;mov eax, 0x1234 跨 jne 寫 al → 0x34、寫 ah → 0x12;"
          "xor eax, eax 後寫 al → 0;mov ah 改寫 / fixup 只取 al → 不判定",
          one("b800300000" + WA, fxs={0x101: 0x53000}) == [("imm", 0x53000, True)]
          and one("b005" + WL) == [("imm", 5, False)]
          and one("b834120000" + "85c9" + j8(0x75, 0x107, 0x10e) + WL) == [("imm", 0x34, False)]
          and one("b834120000" + "85c9" + j8(0x75, 0x107, 0x10f) + WH) == [("imm", 0x12, False)]
          and one("31c0" + "85c9" + j8(0x75, 0x104, 0x10b) + WL) == I0
          and one("b805000000" + "b407" + WA) is None
          and one("b800300000" + "85c9" + j8(0x75, 0x107, 0x10e) + WL, fxs={0x101: 0x53000}) is None)
    check("(f14) 前一條 ret 而寫入不是區塊開頭 / 中間 int / 跨 loop 寫 ecx → 不判定;跨 loop 寫 eax → 5",
          one("c3" + WA) is None and one("b805000000" + "cd21" + WA) is None
          and one("b905000000" + j8(0xe2, 0x105, 0x10d) + "890d00200000") is None
          and one("b805000000" + j8(0xe2, 0x105, 0x10c) + WA) == [("imm", 5, False)])

    def jmps(n: int) -> str:
        return "b805000000" + "".join(j8(0xeb, 0x105 + 2 * i, 0x107 + 2 * i) for i in range(n)) + WA
    check("(f15) 匯合深度:12 個 jmp → 5、13 個 → 不判定", one(jmps(12)) == [("imm", 5, False)] and one(jmps(13)) is None)
    check("(f16) 步數上限:3999 條 nop → 5、4000 條 → 不判定",
          one("b805000000" + "90" * 3999 + WA) == [("imm", 5, False)] and one("b805000000" + "90" * 4000 + WA) is None)
    check("(f17) or / and 自己 → 值不變(5);or eax, ebx → 不判定",
          one("b805000000" + "09c0" + WA) == [("imm", 5, False)] and one("b805000000" + "21c0" + WA) == [("imm", 5, False)]
          and one("b805000000" + "09d8" + WA) is None)

    def movs(n: int) -> str:
        """mov eax, 7;mov ebx, 7;n 條交替的 mov ebx, eax / mov eax, ebx(每條都是跳躍目標);寫 [m];
        每條各有一個 mov eax, 5;mov ebx, 5;jmp 過去的進入塊 —— 每個匯合點都經「落下的 mov」往前一層。"""
        body = ["89d8" if (n - 1 - i) % 2 == 0 else "89c3" for i in range(n)]
        at, head = 0x100 + 10, "b807000000" + "bb07000000"
        addrs = [at + 2 * i for i in range(n)]
        h = head + "".join(body) + WA + "c3"
        pos = 0x100 + len(h) // 2
        for a in addrs:
            h += "b805000000" + "bb05000000" + rel32("e9", pos + 10, a)
            pos += 15
        return h
    got18 = one(movs(12), at=2 + 12)
    check("(f18) 匯合深度經「落下的 mov」累計:12 層 → {5, 7}、13 層 → 不判定",
          got18 is not None and sorted(got18) == [("imm", 5, False), ("imm", 7, False)]
          and one(movs(13), at=2 + 13) is None)

    # 被呼叫者保存暫存器(Preserve):合成程式碼放在 0x400 / 0x480 / 0x500 / 0x580 / 0x600
    def pres(blobs: dict[int, str]) -> Preserve:
        raw = {b0: bytes.fromhex(h) for b0, h in blobs.items()}

        def dec(a: int) -> object | None:
            for b0, r in raw.items():
                if b0 <= a < b0 + len(r):
                    return next(cs.disasm(r[a - b0:a - b0 + 16], a), None)
            return None
        return Preserve(dec)

    a1 = "6a10" + rel32("e8", 0x402, 0x480) + "5356" + "be05000000" + "5e5b" + "c3"
    k1 = pres({0x400: a1, 0x480: "c20400"})
    r_esi, r_ebx, r_edi = k1(0x400, "esi"), k1(0x400, "ebx"), k1(0x400, "edi")
    check("(p1) 序言 push ebx / esi、結語倒序 pop → 保存 esi / ebx(存回);edi 走得到 ret 的指令都不寫 → 保存(不碰)",
          r_esi[0] and r_esi[1].startswith("序言") and r_ebx[0] and r_edi[0] and r_edi[1].startswith("走得到"))
    check("(p2) 序言 push 之前的 call 改寫 esi → 不保存", not pres({0x400: a1, 0x480: "be01000000c3"})(0x400, "esi")[0])
    check("(p3) 結語 pop 順序不對 → 不保存;有一個 ret 前面沒有 pop → 不保存;兩個 ret 都 pop → 保存",
          not pres({0x400: "53565b5ec3"})(0x400, "esi")[0]
          and not pres({0x400: "56" + "85c0" + j8(0x74, 0x403, 0x407) + "5ec3" + "c3"})(0x400, "esi")[0]
          and pres({0x400: "56" + "85c0" + j8(0x74, 0x403, 0x407) + "5ec3" + "5ec3"})(0x400, "esi")[0])
    check("(p4) 函式內寫 esi → 不保存 esi、保存 edi",
          not pres({0x400: "be01000000c3"})(0x400, "esi")[0] and pres({0x400: "be01000000c3"})(0x400, "edi")[0])
    call_b = rel32("e8", 0x400, 0x500) + "c3"
    check("(p5) 呼叫的函式寫 esi → 不保存;不寫 → 保存",
          not pres({0x400: call_b, 0x500: "be01000000c3"})(0x400, "esi")[0]
          and pres({0x400: call_b, 0x500: "c3"})(0x400, "esi")[0])
    kc = pres({0x400: call_b, 0x500: rel32("e8", 0x500, 0x400) + "c3"})
    check("(p6) 互相遞迴、都不寫 → 保存;只快取查詢起點,依賴假設的中間結果不快取",
          kc(0x400, "esi")[0] and (0x400, "esi") in kc.memo and (0x500, "esi") not in kc.memo and kc(0x500, "esi")[0])
    check("(p6b) 互相遞迴、其中一個寫 esi → 不保存",
          not pres({0x400: call_b, 0x500: "be01000000" + rel32("e8", 0x505, 0x400) + "c3"})(0x400, "esi")[0])
    check("(p7) 走得到 ret 的間接 call → 不保存(不碰);序言 push 了它就不受影響;間接 jmp → 不判定",
          not pres({0x400: "ffd0c3"})(0x400, "esi")[0] and pres({0x400: "56ffd05ec3"})(0x400, "esi")[0]
          and not pres({0x400: "56ffe0"})(0x400, "esi")[0])
    dos = "85c0" + j8(0x75, 0x402, 0x40d) + "be01000000" + "b44c" + "cd21" + "c3"
    check("(p8) mov ah, 0x4c + int 0x21 不回傳:那條路改寫 esi 不影響 → 保存;ah 0x4d / int 0x10 → 會回傳 → 不保存",
          pres({0x400: dos})(0x400, "esi")[0] and not pres({0x400: dos.replace("b44c", "b44d")})(0x400, "esi")[0]
          and not pres({0x400: dos.replace("cd21", "cd10")})(0x400, "esi")[0])
    check("(p8b) mov ax, 0x4c00 / mov eax, 0x4c00 也算;DOS 結束的 int 是跳躍目標 → 不判定",
          pres({0x400: "85c0" + j8(0x75, 0x402, 0x40f) + "be01000000" + "66b8004c" + "cd21" + "c3"})(0x400, "esi")[0]
          and pres({0x400: "85c0" + j8(0x75, 0x402, 0x410) + "be01000000" + "b8004c0000" + "cd21" + "c3"})(0x400, "esi")[0]
          and not pres({0x400: "85c0" + j8(0x75, 0x402, 0x40b) + "be01000000" + "b44c" + "cd21" + "c3"})(0x400, "esi")[0])
    check("(p6c) 不依賴假設的非起點結果要快取;依賴假設而失敗的也快取(假設成立都失敗 = 真的失敗)",
          (lambda k: k(0x400, "esi")[0] and (0x500, "esi") in k.memo)(pres({0x400: call_b, 0x500: "c3"}))
          and (lambda k: not k(0x400, "esi")[0] and k.memo.get((0x500, "esi"), (True,))[0] is False)(
              pres({0x400: call_b, 0x500: rel32("e8", 0x500, 0x400) + "be01000000" + "c3"})))
    tail = "5653" + rel32("e9", 0x402, 0x580)
    check("(p9) jmp 到共用結語、pop 倒序 → 保存;結語順序不對 → 不保存",
          pres({0x400: tail, 0x580: "5b5ec3"})(0x400, "esi")[0] and not pres({0x400: tail, 0x580: "5e5bc3"})(0x400, "esi")[0])
    check("(p10) push ebp;mov ebp, esp;… leave → 保存 ebp;沒有 leave → 不保存;mov ebp, esp 之後再 push ebx → 保存 ebx;"
          "先 mov ebp, esp → 不保存 ebx;結語夾 add esp → 保存",
          pres({0x400: "5589e583ec08c9c3"})(0x400, "ebp")[0] and not pres({0x400: "5589e583ec08c3"})(0x400, "ebp")[0]
          and pres({0x400: "5589e5535bc9c3"})(0x400, "ebx")[0] and not pres({0x400: "89e5535bc9c3"})(0x400, "ebx")[0]
          and pres({0x400: "5383ec0883c4085bc3"})(0x400, "ebx")[0])
    check("(p11) 段暫存器也算序言 push:push esi / es … pop es / esi → 保存;順序錯 → 不保存",
          pres({0x400: "5606075ec3"})(0x400, "esi")[0] and not pres({0x400: "56065e07c3"})(0x400, "esi")[0])
    check("(p12) 入口是 jmp(轉接)→ 跟著 jmp 看序言;不是程式碼 → 不判定",
          pres({0x400: rel32("e9", 0x400, 0x580), 0x580: "565ec3"})(0x400, "esi")[0] and not pres({})(0x400, "esi")[0])
    nr = rel32("e8", 0x400, 0x600) + "be01000000" + "c3"
    k13 = pres({0x400: nr, 0x600: "b44ccd21"})
    check("(p13) 呼叫不回傳的函式之後的路不可達 → 保存;被呼叫者會回傳 → 不保存",
          k13(0x400, "esi")[0] and not k13.returns(0x600) and not pres({0x400: nr, 0x600: "c3"})(0x400, "esi")[0])
    check("(p15) 走得到 ret 的 int → 不保存(不碰);序言 push 了它 → 保存",
          pres({0x400: "cd10c3"})(0x400, "esi") == (False, "0x400 int(當作全部改寫)")
          and pres({0x400: "56cd105ec3"})(0x400, "esi")[0])
    check("(p16) 序言 sub esp, 8 之後 push → 保存;sub esp, eax → 序言停;結語 pop 之間夾 add esp, 4 → 保存;"
          "夾 add esp, eax / add ebx, 4 → 不保存",
          pres({0x400: "83ec0856be050000005e83c408c3"})(0x400, "esi")[0]
          and not pres({0x400: "29c456be050000005ec3"})(0x400, "esi")[0]
          and pres({0x400: "5683ec04535b83c4045ec3"})(0x400, "esi")[0]
          and not pres({0x400: "5683ec04535b01c45ec3"})(0x400, "esi")[0]
          and not pres({0x400: "5683ec04535b83c3045ec3"})(0x400, "esi")[0])
    check("(p14) 可達指令 20000 條 → 判定;20001 條 → 不判定",
          pres({0x400: "90" * 19999 + "c3"})(0x400, "esi")[0] and not pres({0x400: "90" * 20000 + "c3"})(0x400, "esi")[0])

    # 條件跳躍與遮罩
    lt = {m: cond_taken(m, 1, 2, 4) for m in _COND}
    eq = {m: cond_taken(m, 2, 2, 4) for m in _COND}
    check("(k1) 條件跳躍:1 vs 2、2 vs 2 的每個條件;有號 −1 < 0、無號 0xffffffff 不小於 0;byte 0x80 有號 < 1;不支援 → None",
          lt == {"je": False, "jz": False, "jne": True, "jnz": True, "jl": True, "jge": False, "jle": True, "jg": False,
                 "jb": True, "jae": False, "jbe": True, "ja": False}
          and eq == {"je": True, "jz": True, "jne": False, "jnz": False, "jl": False, "jge": True, "jle": True,
                     "jg": False, "jb": False, "jae": True, "jbe": True, "ja": False}
          and cond_taken("jl", 0xFFFFFFFF, 0, 4) and not cond_taken("jb", 0xFFFFFFFF, 0, 4)
          and cond_taken("jl", 0x80, 1, 1) and not cond_taken("jl", 0x80, 1, 4) and cond_taken("js", 1, 2, 4) is None
          and cond_taken("jl", 0xFE, 0xFF, 1) and not cond_taken("jl", 0xFF, 0xFE, 1))
    check("(k2) 暫存器寬度與遮罩", [_width(r) for r in ("eax", "ax", "al", "ah", "si", "bp")] == [4, 2, 1, 1, 2, 2]
          and (_mask(1), _mask(2), _mask(4)) == (0xFF, 0xFFFF, 0xFFFFFFFF))

    # 讀改寫歸納(rmw_guard / rmw_bad)
    mi, md_ = "ff0500200000", "ff0d00200000"
    r0, r4 = "c7050020000000000000", "c7050020000004000000"

    def rg(h: str, at: int = 0, **kw: object) -> tuple:
        return rmw_guard(ctx_of(h, **kw), at)

    def dom(t: str, size: int = 4) -> dict:
        return parse_type(t, size)["allowed"]
    inc4 = mi + "833d0020000004" + j8(0x75, 0x10d, 0x119) + r0 + "c3"
    check("(m1) inc;cmp [m], 4;jne 跳過重設 → wrap(+1, jne, 4);0 .. 3 歸納成立、0 .. 2 不成立;重設是最後一條也接受",
          rg(inc4) == ("wrap", 1, "jne", 4, False, 4) and rmw_bad(rg(inc4), dom("dword(x 0 .. 3)")) == []
          and rmw_bad(rg(inc4), dom("dword(x 0 .. 2)")) != []
          and rg(mi + "833d0020000004" + j8(0x75, 0x10d, 0x119) + r0) == ("wrap", 1, "jne", 4, False, 4))
    dec0 = md_ + "833d0020000000" + j8(0x7d, 0x10d, 0x119) + r4 + "c3"
    check("(m2) dec;cmp [m], 0;jge 跳過重設 → 0 .. 5 成立;cmp [m], −1 → 舊值 0 減成 −1 也跳走 → 不成立",
          rg(dec0) == ("wrap", -1, "jge", 0, False, 4) and rmw_bad(rg(dec0), dom("dword(x 0 .. 5)")) == []
          and rmw_bad(rg(dec0.replace("833d0020000000", "833d00200000ff")), dom("dword(x 0 .. 5)")) != [])
    check("(m3) xor byte [m], 1 → 旗標封閉;xor 2 → 不封閉;xor [m], bl → 不是立即數",
          rg("80350020000001") == ("xor", 1, 1) and rmw_bad(rg("80350020000001"), dom("byte 旗標(x)", 1)) == []
          and rmw_bad(rg("80350020000002"), dom("byte 旗標(x)", 1)) != [] and rg("301d00200000")[0] is None)
    m4 = mi + "8b1d00200000" + "83fb3c" + j8(0x75, 0x10f, 0x118) + "31c0" + WA + "c3"
    check("(m4) inc;mov ebx, [m];cmp ebx, 60;jne;xor eax, eax;mov [m], eax → wrap;0 .. 59 成立、0 .. 58 不成立;"
          "中間夾 jmp / 讀 [m] → 不是樣式",
          rg(m4) == ("wrap", 1, "jne", 60, False, 4) and rmw_bad(rg(m4), dom("dword 0..59")) == []
          and rmw_bad(rg(m4), dom("dword 0..58")) != [] and rg(m4.replace("31c0", "eb00"))[0] is None
          and rg(mi + "8b1d00200000" + "83fb3c" + j8(0x75, 0x10f, 0x11b) + "a100200000" + WA + "c3")[0] is None)
    m5 = "bb3c000000" + mi + "3b1d00200000" + j8(0x75, 0x111, 0x11d) + r0 + "c3"
    check("(m5) cmp ebx, [m] 且 ebx = 60(跨區塊常數)→ 常數在左;0 .. 59 成立、0 .. 58 不成立;ebx 不知道 → 不是樣式",
          rg(m5, at=1) == ("wrap", 1, "jne", 60, True, 4) and rmw_bad(rg(m5, at=1), dom("dword 0..59")) == []
          and rmw_bad(rg(m5, at=1), dom("dword 0..58")) != [] and rg("9090909090" + m5[10:], at=5)[0] is None)
    check("(m5b) 常數在左的條件方向:cmp 2, n;jl 跳 → n = 6 跳走 → 不成立;常數在右 → 成立",
          rmw_bad(("wrap", 1, "jl", 2, True, 4), dom("dword(x 0 .. 5)")) != []
          and rmw_bad(("wrap", 1, "jl", 2, False, 4), dom("dword(x 0 .. 5)")) == [])
    check("(m6) 不是樣式:後面沒東西 / 不是比較 / 比較別的位址 / 不支援的條件 / 中間有區塊開頭 / 不跳的路沒重設 / "
          "比較常數有 fixup / 沒有條件跳躍 / 不是固定位址 / add [m], 1",
          rg(mi + "c3")[0] is None and rg(mi + "909090")[0] is None
          and rg(mi + "833d0430000004" + j8(0x75, 0x10d, 0x119) + r0 + "c3")[0] is None
          and rg(inc4.replace(j8(0x75, 0x10d, 0x119), j8(0x78, 0x10d, 0x119)))[0] is None
          and rg(inc4, extra={0x106})[0] is None
          and rg(mi + "833d0020000004" + j8(0x75, 0x10d, 0x111) + "9090" + "c3")[0] is None
          and rg(mi + "833d0020000004" + j8(0x75, 0x10d, 0x111))[0] is None
          and rg(inc4, fxs={0x10c: 0x53000})[0] is None
          and rg(mi + "8b1d00200000" + "83fb3c")[0] is None
          and rg("ff03" + "c3")[0] is None and rg("83050020000001" + "c3")[0] is None)
    check("(m8) 不跳的路是最後一條之前的 nop + 重設 → 樣式;inc / cmp / jne 之後沒東西 → 「沒有重設」",
          rg(mi + "833d0020000004" + j8(0x75, 0x10d, 0x11a) + "90" + r0) == ("wrap", 1, "jne", 4, False, 4)
          and rg(mi + "833d0020000004" + j8(0x75, 0x10d, 0x119)) == (None, "不跳的那條路沒有重設"))
    check("(m9) 歸納不成立的說明:xor 的常數、+ / − 1 的方向與跳走的條件",
          rmw_bad(("xor", 2, 1), dom("byte(x 0 .. 1)", 1)) == ["舊值 0 xor 0x2 = 2", "舊值 1 xor 0x2 = 3"]
          and rmw_bad(("wrap", 1, "jne", 4, False, 4), dom("dword(x 0 .. 2)")) == ["舊值 2 + 1 = 3,jne 跳走不重設"]
          and rmw_bad(("wrap", -1, "jne", 5, False, 4), dom("dword(x 0 .. 2)"))
          == ["舊值 0 - 1 = 4294967295,jne 跳走不重設"])
    check("(m7) 值域全部值 = 列舉 ∪ 範圍 ∪ 0 .. 上限 ∪ 哨兵;65536 個 → 列得出、65537 個(範圍 / 上限 / 合計)→ None;"
          "值域太大的歸納 → 記錄",
          allowed_values({"set": {1, 2}, "range": (5, 6), "upper": 3, "sentinel": {255}}) == {0, 1, 2, 3, 5, 6, 255}
          and len(allowed_values({"set": None, "range": (0, 65535), "upper": None, "sentinel": set()}) or ()) == 65536
          and allowed_values({"set": None, "range": (0, 65536), "upper": None, "sentinel": set()}) is None
          and allowed_values({"set": None, "range": None, "upper": 65536, "sentinel": set()}) is None
          and allowed_values({"set": {70000}, "range": (0, 65535), "upper": None, "sentinel": set()}) is None
          and rmw_bad(("xor", 1, 1), {"set": None, "range": (0, 1 << 20), "upper": None, "sentinel": set()})
          == ["值域太大,無法逐值歸納"])

    # check_region 的跨區塊 / 歸納核對(0x930.. = mov [m], 暫存器;0x940 = inc)
    for a in range(0x930, 0x940):
        imms[a] = ("mov", None, False)
    imms[0x940] = ("inc", None, False)

    def fr(t: str, vals: list | None, start: int = 0x1050, size: int = 4, rt: dict | None = None,
           ins: int = 0x930, rmw: tuple | None = None) -> dict:
        acc = [(ins, start, min(size, 4), "w", "mem", False)]
        return check_region(reg(start, size, t),
                            Facts(image, [(0x2000, 0x2100)], fx, ents, acc, lambda a: imms.get(a, ("", None, False)),
                                  [], {}, {}, nm, {ins: (vals, "")} if vals is not None else {},
                                  {ins: rmw} if rmw else {}, rt or {}))

    a6 = "dword(x 0 .. 6)"
    mem[0x104:0x108] = struct.pack("<I", 0x404)         # 0x1104:有 fixup 的非零指標初值
    v = fr(a6, [("imm", 3, False)])
    check("(v1) 跨區塊常數在值域內 → 跨區塊 1、未判定 0、不算立即數核對、值的種類計數",
          (v["flow"], v["undetermined"], v["fail"], v["flow_vals"], v["imm_checked"]) == (1, 0, [], {"imm": 1}, 0))
    v = fr(a6, [("imm", 3, False), ("imm", 7, False)])
    check("(v2) 兩個值之一在值域外 → 失敗 1、仍算跨區塊、種類計 2",
          len(v["fail"]) == 1 and v["flow"] == 1 and v["flow_vals"] == {"imm": 2})
    check("(v3) 指標:常數 5 → 失敗;fixup / 0 / 宣告的旗標值 → 0;byte 以寬度遮罩成哨兵 → 0",
          fr("dword 指標(x)", [("imm", 5, False)])["fail"] != []
          and fr("dword 指標(x)", [("imm", 0x5000, True), ("imm", 0, False)])["fail"] == []
          and fr("dword 指標(x;0 / 1 當旗標)", [("imm", 1, False)])["fail"] == []
          and fr("byte(x 0 .. 6,0xff = 沒有)", [("imm", 0xFFFFFFFF, False)], size=1)["fail"] == [])
    ok_ = fr("dword 指標(BG.DAT 第 2 號)", [("ret", 0x700, [bg, var, (2, False, "")])])
    check("(v4) 回傳:值域型別 → 未判定;指標 → 跨區塊並交給來源宣告核對(相符 0、號碼不同 → 失敗)",
          fr(a6, [("ret", 0x700, None)])["undetermined"] == 1
          and (ok_["flow"], ok_["src_checked"], ok_["fail"]) == (1, 2, [])
          and fr("dword 指標(BG.DAT 第 2 號)", [("ret", 0x700, [bg, var, (3, False, "")])])["fail"] != [])
    check("(v5) 自身舊值:初值 0 / 清零 → 跨區塊;初值 13 → 未判定;指標初值有 fixup / 宣告的旗標值 → 跨區塊、13 → 未判定;"
          "沒對齊 / 寬度不同 → 未判定",
          fr(a6, [("mem", 0x1050, 4)])["flow"] == 1
          and fr(a6, [("mem", 0x1010, 4)], start=0x1010)["undetermined"] == 1
          and fr(a6, [("mem", 0x2010, 4)], start=0x2010)["flow"] == 1
          and fr("dword 指標(x)", [("mem", 0x1104, 4)], start=0x1104)["flow"] == 1
          and fr("dword 指標(x)", [("mem", 0x1010, 4)], start=0x1010)["undetermined"] == 1
          and fr("dword 指標(x;13 / 14 當旗標)", [("mem", 0x1010, 4)], start=0x1010)["flow"] == 1
          and fr("dword[2](x 0 .. 6)", [("mem", 0x1052, 4)], size=8)["undetermined"] == 1
          and fr(a6, [("mem", 0x1050, 2)])["undetermined"] == 1
          and fr(a6, [("mem", 0x3000, 4)], start=0x3000)["undetermined"] == 1)
    rt_p = {0x2020: (4, "dword 指標(y)")}
    rt_v = {0x2020: (4, "dword(y 0 .. 3)")}
    arr2 = {0x2020: (8, "dword[2](y 0 .. 3)")}
    check("(v6) 複製自別段:指標 ← 指標 / 值域包含 / 陣列對齊的格 → 跨區塊;指標 ← 值域段、值域 ← 指標、不包含、未登錄、"
          "對方解析不了、對方初值不合、寬度不同、沒對齊 → 未判定",
          fr("dword 指標(x)", [("mem", 0x2020, 4)], start=0x2010, rt=rt_p)["flow"] == 1
          and fr(a6, [("mem", 0x2020, 4)], rt=rt_v)["flow"] == 1
          and fr(a6, [("mem", 0x2024, 4)], rt=arr2)["flow"] == 1
          and fr("dword 指標(x)", [("mem", 0x2020, 4)], start=0x2010, rt=rt_v)["undetermined"] == 1
          and fr(a6, [("mem", 0x2020, 4)], rt=rt_p)["undetermined"] == 1
          and fr("dword(x 0 .. 2)", [("mem", 0x2020, 4)], rt=rt_v)["undetermined"] == 1
          and fr(a6, [("mem", 0x2020, 4)])["undetermined"] == 1
          and fr(a6, [("mem", 0x2020, 4)], rt={0x2020: (4, "qword y")})["undetermined"] == 1
          and fr(a6, [("mem", 0x1010, 4)], rt={0x1010: (4, "dword(y 0 .. 3)")})["undetermined"] == 1
          and fr(a6, [("mem", 0x2020, 2)], rt=rt_v)["undetermined"] == 1
          and fr(a6, [("mem", 0x2022, 4)], rt=arr2)["undetermined"] == 1)
    fm = "dword(x 0 .. 6,或記錄 byte + 2 的半徑)"
    check("(v7) movzx 式子:= type 的 byte + 2 → 跨區塊;byte + 3 → 失敗;沒有式子時整個範圍在值域內才算(寫入寬度遮罩、"
          "word 範圍到 65535)、否則未判定;指標 / 不認得的值 → 未判定",
          (fr(fm, [("zx", 1, 2)])["fail"], fr(fm, [("zx", 1, 2)])["flow"]) == ([], 1)
          and fr(fm, [("zx", 1, 3)])["fail"] != []
          and "寫入 movzx 1 byte + 3,type 的式子是 [(1, 2)]" in fr(fm, [("zx", 1, 3)])["fail"][0]
          and fr("dword(x 0 .. 255)", [("zx", 1, 0)])["flow"] == 1
          and fr(a6, [("zx", 1, 0)])["undetermined"] == 1
          and fr("byte(x 0 .. 255)", [("zx", 1, 1)], size=1)["flow"] == 1
          and fr("dword(x 0 .. 65535)", [("zx", 2, 0)])["flow"] == 1
          and fr("dword(x 0 .. 65534)", [("zx", 2, 0)])["undetermined"] == 1
          and fr("dword 指標(x)", [("zx", 1, 0)])["undetermined"] == 1
          and fr(a6, [("foo", 1)])["undetermined"] == 1)
    check("(v8) 跨區塊值只用在 mov 且有宣告的段:inc / 沒有值域 → 未判定",
          fr(a6, [("imm", 3, False)], ins=0x940)["undetermined"] == 1
          and fr("dword(x)", [("imm", 3, False)])["undetermined"] == 1)
    wr4 = ("wrap", 1, "jne", 4, False, 4)
    ind_ok = fr("dword(x 0 .. 3)", None, ins=0x940, rmw=wr4)
    check("(v9) 讀改寫歸納:成立 → 歸納 1、不算未判定;不成立 → 失敗;指標 / 值域太大 / 不是樣式 → 未判定",
          (ind_ok["inductive"], ind_ok["undetermined"], ind_ok["fail"]) == (1, 0, [])
          and fr("dword(x 0 .. 2)", None, ins=0x940, rmw=wr4)["fail"] != []
          and fr("dword 指標(x)", None, ins=0x940, rmw=wr4)["undetermined"] == 1
          and fr("dword(x,上限 70000)", None, ins=0x940, rmw=wr4)["undetermined"] == 1
          and fr("dword(x 0 .. 3)", None, ins=0x940, rmw=(None, "x"))["undetermined"] == 1
          and [m.count("舊值") for m in fr(a6, None, ins=0x940, rmw=("xor", 0x10, 4))["fail"]] == [3])
    check("(v10) 文法:byte + 2 / word + 3 是式子;bytes + 2 不算;只有式子也建值域;沒有式子就沒有 formula",
          dom(fm)["formula"] == {(1, 2)} and dom("dword(word + 3)")["formula"] == {(2, 3)}
          and "allowed" not in parse_type("dword(bytes + 2)", 4) and "formula" not in dom(a6))

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
        check("真實 值域 / 指標寫入:核對 302(暫存器 17)、函式回傳 111、跨區塊 24、歸納 8、未判定 55",
              (sum(x["imm_checked"] for x in ranged), sum(x["via_reg"] for x in ranged),
               sum(x["call_ret"] for x in ranged), sum(x["flow"] for x in ranged),
               sum(x["inductive"] for x in ranged), sum(x["undetermined"] for x in ranged))
              == (302, 17, 111, 24, 8, 55))
        srcd = [x for r, x in out if x["claim"].get("source")]
        check("真實 來源宣告 24 段、參數核對 122 項",
              (len(srcd), sum(x["src_checked"] for x in srcd)) == (24, 122))
        # 跨區塊 / 歸納(2026-11-15 逐條讀反組譯核對)
        fs = f.flow_src
        q = fs.get(0x21675, (None, ""))[0]
        check("真實 0x21675 = earthquake_spell_effect 把 malloc(0xfa00) 寫進 [0x53a49](跨迴圈、跨 call)",
              q is not None and len(q) == 1 and q[0][0] == "ret" and f.names.get(q[0][1]) == MALLOC
              and q[0][2] == [(0xfa00, False, "立即數")])
        check("真實 0x24c54 esi = 0 跨過 call 0x15f84、0x2679f ebp = 0、0x13df8 eax = 0(jne 不跳)",
              fs.get(0x24c54) == ([("imm", 0, False)], "") and fs.get(0x2679f) == ([("imm", 0, False)], "")
              and fs.get(0x13df8) == ([("imm", 0, False)], ""))
        check("真實 0x1dd9a 寫回 [0x53a49] 自己的舊值、0x1736e sete → {0, 1}、0x15140 movzx byte + 2",
              fs.get(0x1dd9a) == ([("mem", 0x53a49, 4)], "")
              and fs.get(0x1736e) == ([("imm", 0, False), ("imm", 1, False)], "")
              and fs.get(0x15140) == ([("zx", 1, 2)], ""))
        check("真實 讀改寫:0x129ac inc + cmp 4 + jne、0x37c82 cmp ebx(= 60), [m]、0x173ba xor 1",
              f.rmw_src.get(0x129ac) == ("wrap", 1, "jne", 4, False, 4)
              and f.rmw_src.get(0x37c82) == ("wrap", 1, "jne", 60, True, 4)
              and f.rmw_src.get(0x173ba) == ("xor", 1, 1))
        import contextlib
        import io

        def rep(o: list) -> tuple[int, list[str]]:
            """print_report 的回傳碼與輸出行(不印到畫面)。"""
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = print_report(f, o, False)
            return rc, buf.getvalue().splitlines()
        rc0, txt = rep(out)
        check("真實 報告的統計行(型別 / 初值來源 / 每種跨區塊值分開加總 / 常數字串 / 窄存取);失敗 0 → 回傳 0",
              rc0 == 0 and txt[:3] == [
                  "data_map type 核對:107 段;失敗 0、未解析 0",
                  "  型別 {'array': 13, 'cstring': 8, 'fptr_table': 4, 'scalar': 81, 'union': 1}",
                  "  初值來源 {'file': 40, 'zeroed': 67};_cstart_ 清零範圍 [('0x539ec', '0x546b0')]"]
              and "    跨區塊 / 跨 call 判定 24 筆(值:常數 11、函式回傳 3、固定位址舊值 7、movzx 式子 4);讀改寫歸納 8 筆"
              in txt
              and "  常數宣告 10 段;字串 8 段;函式指標表 4 段" in txt
              and "  窄存取(寬度小於元素,不算失敗) 30 筆,分布在 11 段" in txt)
        rce, txe = rep([])
        check("報告 空輸入:各計數 0、型別 {}、回傳 0",
              rce == 0 and txe[:2] == ["data_map type 核對:0 段;失敗 0、未解析 0", "  型別 {}"]
              and "  常數宣告 0 段;字串 0 段;函式指標表 0 段" in txe)
        r0, x0 = out[0]
        rcb, txb = rep([(r0, dict(x0, fail=["假失敗"])), (r0, dict(x0, claim=dict(x0["claim"], kind="unparsed")))])
        check("報告 1 段失敗 + 1 段未解析 → 各計 1、回傳 1",
              rcb == 1 and txb[0] == "data_map type 核對:2 段;失敗 1、未解析 1" and "    FAIL 假失敗" in txb)
        check("真實 跨區塊判定只用在區塊內判定不出的寫入",
              not set(fs) & ({a for a, v in f.reg_src.items() if v[0] is not None} | set(f.call_src)))
        # 函式回傳(2026-11-14 逐條讀反組譯核對):0x25d26 push 6 / push [0x53ad1] / push 0x1a4d(fixup → "FDOTHER.DAT")
        cs6 = f.call_src.get(0x25d2e)
        check("真實 0x25d2e = load_res(\"FDOTHER.DAT\", 記憶體, 6)",
              cs6 is not None and f.names.get(cs6[0]) == LOAD_RES and cs6[1] is not None
              and _cstr(f, cs6[1][0][0]) == "FDOTHER.DAT" and cs6[1][2][:2] == (6, False) and cs6[1][1][0] is None)
        check("真實 0x17e23 = malloc(0xfa00)", f.call_src.get(0x17e23) is not None
              and f.names.get(f.call_src[0x17e23][0]) == MALLOC and f.call_src[0x17e23][1] == [(0xfa00, False, "立即數")])
        check("真實 0x2fb60 第 0 號由 push ebp 的暫存器常數取得",
              f.call_src.get(0x2fb60) is not None and f.call_src[0x2fb60][1][2] == (0, False, "暫存器常數"))
        # 對照:把真實 type 的宣告改錯一處,必須失敗
        byst = {r["start"]: r for r in regions}

        def alt(start: str, old: str, new: str) -> list[str]:
            r = dict(byst[start])
            assert r["type"].count(old) == 1, (start, old)
            r["type"] = r["type"].replace(old, new)
            return check_region(r, f)["fail"]
        check("真實 對照:第 6 號 → 7、malloc 0xfa00 → 0xfa01、BG 號碼順序對調、DATO → FDOTHER、FDOTHER 第 80 → 81 全部失敗",
              all(alt(*a) for a in (("0x53ad1", "第 6 號", "第 7 號"), ("0x53c5b", "0xfa00", "0xfa01"),
                                    ("0x5413f", "0 / 1 / 2", "0 / 2 / 1"), ("0x53a85", "DATO.DAT", "FDOTHER.DAT"),
                                    ("0x53b13", "第 80 或", "第 81 或"), ("0x53a49", "malloc 0x25680", "malloc 0x25681"))))
        check("真實 對照:拿掉 0x53a49 的 malloc 0xfa00、0x53c0b 0 .. 3 → 0 .. 2、0x51a83 byte + 2 → byte + 3 全部失敗",
              all(alt(*a) for a in (("0x53a49", "暫換成 malloc 0xfa00 緩衝", "暫換成緩衝"), ("0x53c0b", "0 .. 3", "0 .. 2"),
                                    ("0x51a83", "byte + 2", "byte + 3"))))
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
