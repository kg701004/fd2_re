"""續二百六十四證據(靜態 + 既有實機紀錄):evidence/static_s264_lower_bound_gaps_20261114.json。

使用者 2026-11-14「還有哪些未完成? 請依照你的建議將每項都優化完善」—— 續二百六十三 `verify_data_lower_bounds`
「只記錄、不做成證據等級」的兩段,改以本產生器證明(工具的 access / value 等級只代表程式碼定址,不混入這裡的前提):
(A) `0x5417c`(char[26],AIL_DEBUG 開始時間)第 26 byte:
    `0x37dec` strcpy(0x5417c, asctime(localtime(time())))。strcpy(`0x400cc`)逐 byte 複製到 NUL(含 NUL)。
    asctime(`0x3ff8b`)把字串寫進 `0x54394`:+0x18 = '\\n'、+0x19 = 0,其餘 24 byte 來自名稱表與 `div(x, 10)` 的商 / 餘。
    tm 欄位只由 `__brktime`(`0x47525`)寫入(localtime `0x3fee0` 呼叫它一或兩次;中間的 isdst `0x476c1` 只寫 tm+0x20):
    全部以無號 `div` 拆,days 落在 [0x63de, 0x63df + (2^32 − 1) // 86400],對任何 time_t 與時區都成立。
    以 Python 照指令逐條重算全部 days → 月 0..11、日 1..31、年 69..206;時 / 分 / 秒由除數得上限。
    ⇒ asctime 的 +0 .. +0x17 對任何輸入都不是 0,strcpy 恰好寫 [0x5417c, 0x5417c + 26)。
(B) `0x52387`(byte[6],城鎮店主頭像)第 6 byte:
    [0x53f4a] 的寫入全碼只有 6 處,值 5 只在 `0x26572`(秘密商店入口:按鍵與選項比對執行期表 [0x53f56] 的 +2 / +1);
    `shop_menu` `0x27a53` 以 [0x53f4a] 為索引讀 `0x52387`。「5 確實流到讀取」由既有實機紀錄證明:
    doc58 2026-09-03 三續,原版 ch02 在酒店前按 Shift+F1 → 標籤變「？　？　？」→ 進入後店主與武器店不同(秘密商店)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re

from _evpaths import ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, _META, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import disasm_le as dl  # noqa: E402
import le_xref  # noqa: E402

OUT = out_path("static_s264_lower_bound_gaps_20261114.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DATA_MAP = ROOT / "docs/data/data_map.json"
DOC58 = ROOT / "docs/knowledge-base/58-remake-live-verification-log.md"
FIG = ROOT / "docs/figures/secret-shop-ch02-original-dosbox.png"
FIG_SHA256 = "7d751ab8baaacb38e27c5b8038f87dc5ab550f108cd94b042edf78cca525ab99"

assert hashlib.md5(_EXE).hexdigest() == MD5
_FX = dl.build_fixups(_EXE, _META)
INSNS, _stops = dl.resync_sweep(_MD, _CODE, _CBASE)


def listing(a: int, b: int) -> list[str]:
    """[a, b) 從 a 起連續解碼的指令文字(不跟跳躍)。"""
    return [f"{i.mnemonic} {i.op_str}".strip() for i in _MD.disasm(_CODE[a - _CBASE:b - _CBASE], a)]


def fixups_in(a: int) -> list[int]:
    """a 那一條指令的位元組範圍內,每個 fixup 欄位指到的線性位址。"""
    i = next(_MD.disasm(_CODE[a - _CBASE:a - _CBASE + 16], a, 1))
    return [_FX[k] for k in range(a, a + i.size) if k in _FX]


def image(a: int, n: int) -> bytes:
    """EXE 檔內線性位址 [a, a + n) 的初值(只接受落在某個物件頁內)。"""
    ps = _META["page_size"]
    for ob in _META["objs"]:
        if ob["base"] <= a and a + n <= ob["base"] + ob["pages"] * ps:
            fo = le_xref.page_file(_META, ob["first"] - 1) + (a - ob["base"])
            return _EXE[fo:fo + n]
    raise AssertionError(hex(a))


REGIONS = {r["start"]: r for r in json.loads(DATA_MAP.read_text(encoding="utf-8"))["regions"]}

# ================= (A) 0x5417c =================
AIL_BUF, ASC_BUF, TM = 0x5417C, 0x54394, 0x54370
assert REGIONS["0x5417c"]["size"] == 26
# 呼叫端:time → localtime → asctime → strcpy(0x5417c, ·) → 把 +0x18 的 '\n' 改成 0
assert [insn(a) for a in (0x37DCA, 0x37DD5, 0x37DDE, 0x37DE6, 0x37DE7, 0x37DEC, 0x37DF4, 0x37DF6)] == [
    "call 0x3fea7", "call 0x3ff35", "call 0x4007b", "push eax", "push 0x417c", "call 0x400cc",
    "xor ah, ah", "mov byte ptr [0x4194], ah"]
assert fixups_in(0x37DE7) == [AIL_BUF] and fixups_in(0x37DF6) == [AIL_BUF + 0x18]
# localtime / asctime 的包裝:靜態 tm 0x54370、靜態字串 0x54394
assert listing(0x3FF35, 0x3FF4A) == ["push ebp", "mov ebp, esp", "push 0x4370", "push dword ptr [ebp + 8]",
                                     "call 0x3fee0", "add esp, 8", "pop ebp", "ret"]
assert fixups_in(0x3FF38) == [TM]
assert listing(0x4007B, 0x40090) == ["push ebp", "mov ebp, esp", "push 0x4394", "push dword ptr [ebp + 8]",
                                     "call 0x3ff8b", "add esp, 8", "pop ebp", "ret"]
assert fixups_in(0x4007E) == [ASC_BUF]
# strcpy:逐 byte(兩個一組)複製到 NUL,NUL 本身也寫
STRCPY = ["push ebp", "mov ebp, esp", "mov eax, dword ptr [ebp + 8]", "mov edx, dword ptr [ebp + 0xc]", "push eax",
          "mov cl, byte ptr [edx]", "mov byte ptr [eax], cl", "cmp cl, 0", "je 0x400f2",
          "mov cl, byte ptr [edx + 1]", "add edx, 2", "mov byte ptr [eax + 1], cl", "add eax, 2", "cmp cl, 0",
          "jne 0x400d6", "pop eax", "pop ebp", "ret"]
assert listing(0x400CC, 0x400F5) == STRCPY

# localtime(0x3fee0):tzset;__brktime(0x63df, t, timezone, tm);isdst(tm) ≠ 0 時再 __brktime(0x63df, t, tz − dst, tm)
LOCALTIME = ["push ebx", "push esi", "push ebp", "mov ebp, esp", "mov ebx, dword ptr [ebp + 0x14]", "call 0x4726f",
             "push ebx", "mov eax, dword ptr [ebp + 0x10]", "push dword ptr [0x384c]", "mov esi, dword ptr [eax]",
             "push esi", "push 0x63df", "call 0x47525", "add esp, 0x10", "push ebx", "call 0x476c1", "add esp, 4",
             "test eax, eax", "je 0x3ff2f", "mov eax, dword ptr [0x384c]", "push ebx", "sub eax, dword ptr [0x3850]",
             "push eax", "push esi", "push 0x63df", "call 0x47525", "add esp, 0x10", "mov eax, ebx", "pop ebp",
             "pop esi", "pop ebx", "ret"]
assert listing(0x3FEE0, 0x3FF35) == LOCALTIME
DAYS0 = 0x63DF

# __brktime(days0, t, tz, tm):整段指令(Python 模型 brktime_days 逐條對應)
BRKTIME = [
    "push ebx", "push esi", "push edi", "push ebp", "mov ebp, esp", "sub esp, 4", "mov ebx, dword ptr [ebp + 0x18]",
    "mov eax, dword ptr [ebp + 0x1c]", "mov edi, dword ptr [ebp + 0x20]", "cmp ebx, 0xa8c0", "jae 0x4755e",
    "test eax, eax", "jle 0x4755e",
    # 路徑一:t < 12 小時且 tz > 0 → X = t + 86400 − tz,days = days0 + X // 86400 − 1
    "add ebx, 0x15180", "mov esi, 0x15180", "sub ebx, eax", "xor edx, edx", "mov eax, ebx", "div esi",
    "add dword ptr [ebp + 0x14], eax", "dec dword ptr [ebp + 0x14]", "jmp 0x4756e",
    # 路徑二:X = t − tz,days = days0 + X // 86400
    "mov esi, 0x15180", "sub ebx, eax", "xor edx, edx", "mov eax, ebx", "div esi", "add dword ptr [ebp + 0x14], eax",
    # 時分秒:X % 86400 → 時 = / 3600、分 = % 3600 / 60、秒 = % 60(全是無號 div)
    "mov esi, 0x15180", "mov eax, ebx", "xor edx, edx", "div esi", "mov ebx, edx", "mov esi, 0xe10", "mov eax, ebx",
    "xor edx, edx", "div esi", "xor edx, edx", "mov dword ptr [edi + 8], eax", "mov eax, ebx", "div esi",
    "mov ebx, edx", "mov esi, 0x3c", "mov eax, ebx", "xor edx, edx", "div esi", "xor edx, edx",
    "mov dword ptr [edi + 4], eax", "mov eax, ebx", "div esi",
    # 年:y = days // 366;r = days − 365y − (y − 1) // 4(y > 0);r ≥ 365 + 閏(1900 + y 起始)就 y++、r −= 同一個值
    "mov ebx, 0x16e", "mov eax, dword ptr [ebp + 0x14]", "mov dword ptr [edi], edx", "xor edx, edx", "div ebx",
    "imul ebx, eax, 0x16d", "mov esi, eax", "mov eax, dword ptr [ebp + 0x14]", "sub eax, ebx", "mov ebx, eax",
    "test esi, esi", "jbe 0x475ce", "lea eax, [esi - 1]", "shr eax, 2", "sub ebx, eax", "lea eax, [esi + 0x76c]",
    "push eax", "call 0x4768d", "add esp, 4", "add eax, 0x16d", "cmp ebx, eax", "jb 0x475eb", "inc esi",
    "sub ebx, eax", "jmp 0x475e2", "mov dword ptr [edi + 0x1c], ebx", "mov dword ptr [edi + 0x14], esi",
    # 月:表 0x51944(平年)/ 0x5195e(閏年)是 13 個 word 的累計日數;m = r // 31,r ≥ 表[m + 1] 就 m++
    "add esi, 0x76c", "push esi", "mov dword ptr [ebp - 4], 0x1944", "call 0x4768d", "add esp, 4", "test eax, eax",
    "je 0x47612", "mov dword ptr [ebp - 4], 0x195e", "mov esi, 0x1f", "mov eax, ebx", "xor edx, edx", "div esi",
    "lea esi, [eax + eax]", "add esi, dword ptr [ebp - 4]", "movsx esi, word ptr [esi + 2]", "cmp ebx, esi",
    "jb 0x4762c", "inc eax", "mov dword ptr [edi + 0x10], eax", "add eax, eax", "add eax, dword ptr [ebp - 4]",
    "movsx eax, word ptr [eax]", "xor edx, edx", "sub ebx, eax",
    # 日 = r − 表[m] + 1;星期 = (days + 1) % 7
    "mov eax, dword ptr [ebp + 0x14]", "inc ebx", "inc eax", "mov dword ptr [edi + 0xc], ebx", "mov ebx, 7",
    "div ebx", "mov eax, edi", "mov dword ptr [edi + 0x18], edx", "leave", "pop edi", "pop esi", "pop ebx", "ret"]
assert listing(0x47525, 0x47654) == BRKTIME
assert fixups_in(0x475F8) == [0x51944] and fixups_in(0x4760B) == [0x5195E]
# isleap(0x4768d):y % 4 ≠ 0 → 0;y % 100 ≠ 0 → 1;否則 y % 400 == 0
ISLEAP = ["push ebx", "push ebp", "mov ebp, esp", "mov ebx, dword ptr [ebp + 0xc]", "test bl, 3", "jne 0x476bc",
          "mov eax, ebx", "mov ecx, 0x64", "cdq", "idiv ecx", "test edx, edx", "je 0x476ae", "mov eax, 1",
          "jmp 0x476be", "mov eax, ebx", "mov ecx, 0x190", "cdq", "idiv ecx", "test edx, edx", "je 0x476a7",
          "xor eax, eax", "pop ebp", "pop ebx", "ret"]
assert listing(0x4768D, 0x476C1) == ISLEAP


def isleap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


CUM = {False: [int.from_bytes(image(0x51944 + 2 * k, 2), "little", signed=True) for k in range(13)],
       True: [int.from_bytes(image(0x5195E + 2 * k, 2), "little", signed=True) for k in range(13)]}
assert CUM[False] == [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
assert CUM[True] == [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366]


def brktime_days(days: int) -> tuple[int, int, int, int]:
    """__brktime 由 days 算 (tm_year, tm_mon, tm_mday, tm_wday),逐條對應 0x475a5 .. 0x4764c。"""
    y = days // 366
    r = days - 365 * y
    if y > 0:
        r -= (y - 1) >> 2
    assert r >= 0
    lim = 365 + isleap(y + 1900)
    while r >= lim:
        y += 1
        r -= lim
    tab = CUM[isleap(y + 1900)]
    m = r // 31
    if r >= tab[m + 1]:
        m += 1
    return y, m, r - tab[m] + 1, (days + 1) % 7


DAYS_LO, DAYS_HI = DAYS0 - 1, DAYS0 + (2**32 - 1) // 86400   # 路徑一最少 −1,兩條路徑的 X 都是 32 位元無號
YEARS, MONS, MDAYS, WDAYS = set(), set(), set(), set()
CAL0, MISMATCH = datetime.date(1900, 1, 1), []
for d in range(DAYS_LO, DAYS_HI + 1):
    y, m, md, wd = brktime_days(d)
    YEARS.add(y), MONS.add(m), MDAYS.add(md), WDAYS.add(wd)
    t = CAL0 + datetime.timedelta(d)
    if (y, m, md, wd) != (t.year - 1900, t.month - 1, t.day, (t.weekday() + 1) % 7):
        MISMATCH.append(d)
# 模型對照真實曆法(datetime,與 FD2 無關的獨立來源):到 2101-06-01 逐日相同;之後 Watcom 以 (y − 1) // 4 估閏年、
# 沒扣 2100 年,日期全部晚一天(星期仍對)。不影響範圍結論,但模型與指令的對應由這個對照釘住。
assert MISMATCH == list(range(73566, DAYS_HI + 1)) and str(CAL0 + datetime.timedelta(MISMATCH[0])) == "2101-06-02"
HOURS, MINS, SECS = range((86400 - 1) // 3600 + 1), range(60), range(60)
assert (min(YEARS), max(YEARS)) == (69, 206) and MONS == set(range(12)) and MDAYS == set(range(1, 32))
assert WDAYS == set(range(7))

# isdst(0x476c1):tm 指標在 ebx;寫記憶體只有區域變數 [ebp − k] 與 tm+0x20;ebx 只當基底讀,或推給比較函式 0x47922
ISDST = [i for i in INSNS if 0x476C1 <= i.address < 0x47922]
WRITERS = ("mov", "add", "sub", "inc", "dec", "and", "or", "xor", "pop", "shl", "shr", "sar", "neg", "not")
MEM_WRITES = sorted({i.op_str.split(",")[0] for i in ISDST
                     if i.mnemonic in WRITERS and re.match(r"(byte|word|dword) ptr \[", i.op_str)})
assert MEM_WRITES == ["dword ptr [ebp - 0x10]", "dword ptr [ebp - 0xc]", "dword ptr [ebp - 4]",
                      "dword ptr [ebp - 8]", "dword ptr [ebx + 0x20]"], MEM_WRITES
assert not [i for i in ISDST if i.op_str.endswith(", ebx")]   # ebx 不被複製到別的暫存器 / 記憶體
assert [(i.address, f"{i.mnemonic} {i.op_str}") for i in ISDST if i.op_str.split(",")[0] == "ebx"] == [
    (0x476C1, "push ebx"), (0x476CA, "mov ebx, dword ptr [ebp + 0x14]"), (0x47808, "push ebx"), (0x4790D, "push ebx"),
    (0x47920, "pop ebx")]
assert sorted({i.op_str for i in ISDST if i.mnemonic == "call"}) == ["0x4768d", "0x47922"]
assert all(ISDST[k + 1].op_str == "0x47922" for k, i in enumerate(ISDST) if f"{i.mnemonic} {i.op_str}" == "push ebx"
           and i.address != 0x476C1)
CMPTM = ["push ebx", "push ebp", "mov ebp, esp", "mov eax, dword ptr [ebp + 0xc]", "mov edx, dword ptr [ebp + 0x10]",
         "mov ecx, dword ptr [eax + 8]", "xor ebx, ebx", "cmp ecx, dword ptr [edx + 8]", "jl 0x47948", "jne 0x4794d",
         "mov ecx, dword ptr [eax + 4]", "cmp ecx, dword ptr [edx + 4]", "jl 0x47948", "jne 0x4794d",
         "mov eax, dword ptr [eax]", "cmp eax, dword ptr [edx]", "jge 0x4794d", "mov ebx, 1", "mov eax, ebx",
         "pop ebp", "pop ebx", "ret"]
assert listing(0x47922, 0x47952) == CMPTM   # 只讀

# asctime(0x3ff8b)與數字寫入(0x3ff4a:div(x, 10) 的商 / 餘各加 '0';div 0x47952 是 cdq / idiv)
assert listing(0x3FF4A, 0x3FF8B) == [
    "push esi", "push edi", "push es", "push ebp", "mov ebp, esp", "sub esp, 0x10", "push 0xa",
    "lea esi, [ebp - 0x10]", "push dword ptr [ebp + 0x14]", "lea edi, [ebp - 8]", "call 0x47952", "mov eax, ds",
    "lea esi, [ebp - 0x10]", "mov es, eax", "movsd dword ptr es:[edi], dword ptr [esi]",
    "movsd dword ptr es:[edi], dword ptr [esi]", "mov eax, dword ptr [ebp + 0x1c]", "mov dl, byte ptr [ebp - 8]",
    "add eax, dword ptr [ebp + 0x18]", "add dl, 0x30", "mov byte ptr [eax], dl", "mov dl, byte ptr [ebp - 4]",
    "add dl, 0x30", "add esp, 8", "mov byte ptr [eax + 1], dl", "leave", "pop es", "pop edi", "pop esi", "ret"]
assert listing(0x47952, 0x47985) == [
    "push ebx", "push edi", "push es", "push ebp", "mov ebp, esp", "sub esp, 8", "mov ecx, dword ptr [ebp + 0x14]",
    "mov ebx, esi", "mov esi, dword ptr [ebp + 0x18]", "mov eax, ecx", "cdq", "idiv esi",
    "mov dword ptr [ebp - 8], eax", "mov eax, ecx", "cdq", "idiv esi", "mov edi, ebx", "mov dword ptr [ebp - 4], edx",
    "mov eax, ds", "lea esi, [ebp - 8]", "mov es, eax", "movsd dword ptr es:[edi], dword ptr [esi]",
    "movsd dword ptr es:[edi], dword ptr [esi]", "mov eax, ebx", "leave", "pop es", "pop edi", "pop ebx", "ret"]
ASCTIME_KEY = {0x3FF9B: "mov eax, dword ptr [esi + 0x18]", 0x3FF9E: "mov dl, byte ptr [eax + 0x1828]",
               0x3FFA6: "mov dl, byte ptr [eax + 0x182f]", 0x3FFAF: "mov al, byte ptr [eax + 0x1836]",
               0x3FFB8: "mov byte ptr [ebx + 3], 0x20", 0x3FFBC: "mov eax, dword ptr [esi + 0x10]",
               0x3FFBF: "mov dl, byte ptr [eax + 0x1804]", 0x3FFC8: "mov dl, byte ptr [eax + 0x1810]",
               0x3FFD1: "mov al, byte ptr [eax + 0x181c]", 0x3FFDD: "mov byte ptr [ebx + 7], 0x20",
               0x3FFE1: "push dword ptr [esi + 0xc]", 0x3FFEC: "cmp byte ptr [ebx + 8], 0x30",
               0x3FFF2: "mov byte ptr [ebx + 8], 0x20", 0x3FFF9: "mov byte ptr [ebx + 0xa], 0x20",
               0x3FFFD: "push dword ptr [esi + 8]", 0x4000B: "mov byte ptr [ebx + 0xd], 0x3a",
               0x4000F: "push dword ptr [esi + 4]", 0x4001D: "mov byte ptr [ebx + 0x10], 0x3a",
               0x40021: "push dword ptr [esi]", 0x4002B: "push 0x64", 0x4002D: "mov byte ptr [ebx + 0x13], 0x20",
               0x40031: "push dword ptr [esi + 0x14]", 0x4004C: "mov eax, dword ptr [ebp - 8]",
               0x40051: "add eax, 0x13", 0x40060: "push dword ptr [ebp - 4]", 0x4006B: "mov byte ptr [ebx + 0x18], 0xa",
               0x40071: "mov byte ptr [ebx + 0x19], 0"}
assert {a: insn(a) for a in ASCTIME_KEY} == ASCTIME_KEY
assert [insn(a) for a in (0x3FFDB, 0x3FFF7, 0x40009, 0x4001B, 0x4004F, 0x4005E)] == [
    "push 8", "push 0xb", "push 0xe", "push 0x11", "push 0x14", "push 0x16"]
NAMES = image(0x51804, 0x5183D - 0x51804)
assert 0 not in NAMES   # 月 3 張 × 12、星期 3 張 × 7


def two(x: int) -> tuple[int, int]:
    q, r = int(x / 10), x - 10 * int(x / 10)   # idiv:向 0 截斷
    return (0x30 + q) & 0xFF, (0x30 + r) & 0xFF


POS: dict[int, set[int]] = {k: set() for k in range(26)}
for wd in WDAYS:
    for k, t in enumerate((0x51828, 0x5182F, 0x51836)):
        POS[k].add(NAMES[t + wd - 0x51804])
for m in MONS:
    for k, t in enumerate((0x51804, 0x51810, 0x5181C)):
        POS[4 + k].add(NAMES[t + m - 0x51804])
for k, c in ((3, 0x20), (7, 0x20), (0xA, 0x20), (0xD, 0x3A), (0x10, 0x3A), (0x13, 0x20), (0x18, 0x0A), (0x19, 0)):
    POS[k].add(c)
for md in MDAYS:
    a, b = two(md)
    POS[8].add(0x20 if a == 0x30 else a), POS[9].add(b)
for pos, vals in ((0xB, HOURS), (0xE, MINS), (0x11, SECS)):
    for v in vals:
        a, b = two(v)
        POS[pos].add(a), POS[pos + 1].add(b)
for y in YEARS:
    q, r = int(y / 100), y - 100 * int(y / 100)
    for pos, v in ((0x14, q + 0x13), (0x16, r)):
        a, b = two(v)
        POS[pos].add(a), POS[pos + 1].add(b)
FIRST_NUL = min(k for k in range(26) if 0 in POS[k])
assert FIRST_NUL == 0x19 and POS[0x19] == {0}
STRCPY_WRITES = (AIL_BUF, AIL_BUF + FIRST_NUL + 1)
assert STRCPY_WRITES[1] - STRCPY_WRITES[0] == REGIONS["0x5417c"]["size"]

# ================= (B) 0x52387 =================
KEEPER, SEL = 0x52387, 0x53F4A
assert REGIONS["0x52387"]["size"] == 6 and image(KEEPER, 6) == bytes((0x81, 0x80, 0x00, 0x82, 0x83, 0x84))
SEL_WRITES = [(i.address, f"{i.mnemonic} {i.op_str}") for i in INSNS
              if i.op_str.startswith("dword ptr [0x3f4a]") and i.mnemonic not in ("cmp", "push", "test")
              and SEL in fixups_in(i.address)]
assert SEL_WRITES == [(0x263B7, "mov dword ptr [0x3f4a], 0"), (0x2650C, "dec dword ptr [0x3f4a]"),
                      (0x2651B, "mov dword ptr [0x3f4a], 4"), (0x2653E, "inc dword ptr [0x3f4a]"),
                      (0x2654D, "mov dword ptr [0x3f4a], 0"), (0x26572, "mov dword ptr [0x3f4a], 5")], SEL_WRITES
# dec / inc 之後的回繞:dec 到負就設 4,inc 超過 4 就設 0 —— 5 只來自 0x26572
assert [insn(a) for a in (0x26512, 0x26544, 0x2654B)] == [
    "cmp dword ptr [0x3f4a], 0", "cmp dword ptr [0x3f4a], 4", "jle 0x2657c"]
GATE = ["mov eax, dword ptr [0x3f56]", "movzx ebx, byte ptr [eax + 2]", "cmp edx, ebx", "jne 0x2657c",
        "movzx eax, byte ptr [eax + 1]", "cmp eax, dword ptr [0x3f4a]", "jne 0x2657c", "mov dword ptr [0x3f4a], 5"]
assert listing(0x26559, 0x2657C) == GATE
assert [insn(a) for a in (0x27A4E, 0x27A53)] == ["mov eax, dword ptr [0x3f4a]", "movzx eax, byte ptr [eax + 0x2387]"]
assert fixups_in(0x27A4E) == [SEL] and fixups_in(0x27A53) == [KEEPER]
LIVE_HEAD = "### 2026-09-03 三續：★ 秘密商店（selection5）成功開啟"
doc58 = DOC58.read_text(encoding="utf-8")
assert doc58.count(LIVE_HEAD) == 1
live = doc58.split(LIVE_HEAD, 1)[1].split("\n### ", 1)[0]
for s in ("酒店前按 Shift+F1", "「？　？　？」", "與一般武器店的", "secret-shop-ch02-original-dosbox.png"):
    assert s in live, s
assert hashlib.sha256(FIG.read_bytes()).hexdigest() == FIG_SHA256

OUT.write_text(json.dumps({
    "generator": "docs/knowledge-base/evidence/generators/ev_s264.py",
    "exe_md5": MD5,
    "A_0x5417c": {
        "claim": "strcpy(0x5417c, asctime(localtime(time()))) 對任何 time_t 與時區都恰好寫 26 byte",
        "brktime_days_range": [DAYS_LO, DAYS_HI],
        "tm_year": [min(YEARS), max(YEARS)], "tm_mon": [min(MONS), max(MONS)],
        "tm_mday": [min(MDAYS), max(MDAYS)], "tm_wday": [min(WDAYS), max(WDAYS)],
        "calendar_mismatch_from": str(CAL0 + datetime.timedelta(MISMATCH[0])), "calendar_mismatch_days": len(MISMATCH),
        "tm_hour_max": max(HOURS), "tm_min_max": max(MINS), "tm_sec_max": max(SECS),
        "isdst_memory_writes": MEM_WRITES,
        "asctime_byte_values": {f"+{k:#x}": sorted(POS[k]) for k in range(26)},
        "asctime_first_nul": FIRST_NUL,
        "strcpy_writes": [hex(STRCPY_WRITES[0]), hex(STRCPY_WRITES[1])],
        "data_map_size": REGIONS["0x5417c"]["size"],
    },
    "B_0x52387": {
        "claim": "[0x53f4a] = 5 只由 0x26572 寫入,shop_menu 0x27a53 以它索引 0x52387;實機秘密商店證明 5 流到讀取",
        "exe_values": list(image(KEEPER, 6)),
        "sel_writes": [[hex(a), t] for a, t in SEL_WRITES],
        "gate": GATE,
        "read": ["0x27a4e", "0x27a53"],
        "live_record": {"doc": rel(DOC58), "heading": LIVE_HEAD, "figure": rel(FIG), "figure_sha256": FIG_SHA256},
        "data_map_size": REGIONS["0x52387"]["size"],
    },
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ev_s264 ok", OUT.name)
