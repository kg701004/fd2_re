"""續二百八十七證據(靜態):evidence/static_s287_data_resources_20261119.json。

使用者 2026-11-19「還有哪些問題?該如何全面完善?依照你的建議自動逐項進行」—— 規格層剩下的缺口逐項補齊:
(A) 演出序列庫 0x62980 .. 0x634d2(acting_seq_table 106 格的 fixup 指向):逐筆解碼,104 筆首尾相接,
    第 24 筆宣告 N = 5 只有 4 對(第 5 對讀到第 25 筆開頭 01 05 = 單位 1 寫 pose 5),第 84 筆尾端多 4 byte
    (宣告 1 幀,88 01 01 02 不會播到);最後一筆正好結束在物件 3 結尾。pose 5 經繪製 0x127e0 的
    槽 × 12 + pose × 3 + 幀 取到下一個快取槽的圖(靜態推論)。第 24 筆由 event_handler_17 播放,
    第 4 圖第 8 回合的回合事件 17 觸發。
(B) data_map 對齊填充:名稱 align_pad_* 的每段 size < 4、結尾 4 對齊、沒有任何指令引用或 fixup 指向;
    各個「沒有引用」段的檔內位元組。
(C) LE 物件的零填頁(BSS):obj2 vsize 0x56b0 大於檔內 4 頁,舊的逐 object 公式對 0x54157 會落到 obj3 的檔內頁;
    disasm_le.lin2file / object_bytes 現在丟錯。
(D) 34 筆沒有用途的資源:11 筆空資源都是目錄最後一格;BG 的背景號來源值集合不含 12 個號碼;
    TITLE.DAT 不被 FD2.EXE 開啟;FDMUS 0 / 2 / 5 / 7 / 9 是 3 byte 佔位,只有城鎮循環鍵會載入。
(E) 單位記錄 +7(FIGANI 組號 = DATO 頭像號)的 136 個值:0 .. 31 角色、32 .. 67 轉職形態、68 .. 135 一般單位
    (high_class 第 +7 − 68 列);名稱 = FDTXT_000 第 +8 + 1 條。FIGANI k:0 每個場景都載、1 攻擊 / 行動、
    2 只有特技 / 施法場景載入,spell_cast_scene 在 k = 2 沒有幀時改載 k = 1。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct

from _evpaths import GAME, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, _META, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import disasm_le as dl  # noqa: E402
import unpack_dat  # noqa: E402

OUT = out_path("static_s287_data_resources_20261119.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DATA_MAP = ROOT / "docs/data/data_map.json"
RES_MAP = ROOT / "docs/data/resource_map.json"
GLYPH = ROOT / "docs/data/glyph_map.json"
CHARS = ROOT / "docs/data/exe_tables/characters.json"
CC = ROOT / "docs/data/exe_tables/class_change_targets.json"

assert hashlib.md5(_EXE).hexdigest() == MD5
FX = dl.build_fixups(_EXE, _META)
TG = set(FX.values())
PS = _META["page_size"]
OBJ3_END = 0x60000 + 0x34D2


def image(a: int, n: int) -> bytes:
    """檔內頁的位元組(零填頁不收)。"""
    for ob in _META["objs"]:
        if ob["base"] <= a and a + n <= ob["base"] + ob["pages"] * PS:
            fo = _META["data_off"] + (ob["first"] - 1) * PS + (a - ob["base"])
            return _EXE[fo:fo + n]
    raise AssertionError(hex(a))


def res(dat: str, i: int) -> bytes:
    b = (GAME / dat).read_bytes()
    o, n = unpack_dat.parse_directory(b)[i]
    return b[o:o + n]


# 程式碼引用的全域位址:每條指令的 fixup 目標(obj1 內的 fixup 來源)
CODE_REFS = {t for s, t in FX.items() if _CBASE <= s < _CBASE + len(_CODE)}

# ================= (A) 演出序列庫 =================
TAB, N, BANK = 0x627D8, 106, 0x62980
AP = [FX.get(TAB + 4 * i) for i in range(N)]
assert None not in AP
assert (TAB + 4 * N) not in FX and AP[0] == BANK == TAB + 4 * N and all(x < y for x, y in zip(AP, AP[1:]))
assert insn(0x4EB51) == "mov eax, dword ptr [eax + 0x27d8]" and FX[0x4EB53] == TAB
BLOB = image(BANK, OBJ3_END - BANK)


def walk(p: int) -> tuple[int, list]:
    o = p - BANK
    nf = BLOB[o]
    o += 1
    fr = []
    for _ in range(nf):
        assert o + 2 <= len(BLOB), hex(p)                 # 讀過物件結尾 = 解錯(不讓它變成 IndexError)
        bt, n = BLOB[o], BLOB[o + 1]
        o += 2
        assert o + 2 * n <= len(BLOB), hex(p)
        fr.append((bt, [(BLOB[o + 2 * k], BLOB[o + 2 * k + 1]) for k in range(n)]))
        o += 2 * n
    return BANK + o, fr


ENDS = [walk(p)[0] for p in AP]
NXT = AP[1:] + [OBJ3_END]
ODD = [i for i in range(N) if ENDS[i] != NXT[i]]
assert ODD == [24, 84]
assert ENDS[24] - NXT[24] == 2 and walk(AP[24])[1] == [(0x80, [(0x30, 0), (0x31, 0), (0x32, 0), (0x33, 0), (1, 5)])]
assert BLOB[NXT[24] - BANK:NXT[24] - BANK + 2] == bytes([1, 5])
TAIL84 = BLOB[ENDS[84] - BANK:NXT[84] - BANK]
assert TAIL84 == bytes([0x88, 1, 1, 2]) and walk(AP[84])[1] == [(2, [(1, 2)])]
assert ENDS[-1] == OBJ3_END
POSES = {p for i in range(N) for _, us in walk(AP[i])[1] for _, p in us}
POSES_NOT24 = {p for i in range(N) if i != 24 for _, us in walk(AP[i])[1] for _, p in us}
assert POSES == {0, 1, 2, 3, 5} and POSES_NOT24 == {0, 1, 2, 3}
# 播放端:特殊幀把 pose 原值寫 +3(0x1373f),再交給繪製;繪製以 槽 × 12 + pose × 3 + 幀 取圖
assert [insn(a) for a in (0x1373C, 0x1373F, 0x1374B)] == [
    "mov dl, byte ptr [esp + edx]", "mov byte ptr [eax + 3], dl", "call 0x127e0"]
assert [insn(a) for a in (0x12835, 0x1291E, 0x12921, 0x12923, 0x12926, 0x12928, 0x1292A, 0x12932)] == [
    "movzx esi, byte ptr [eax + 3]", "imul edi, edi, 0xc", "mov eax, esi", "shl eax, 2", "sub eax, esi",
    "add eax, edi", "add eax, edx", "mov eax, dword ptr [edx + eax*4]"]
# 第 24 筆的播放點:event_handler_17 0x34a5d push 0x18 → act;第 4 圖第 8 回合的回合事件 17
assert insn(0x34A5D) == "push 0x18" and insn(0x34A5F) == "call 0x1366a"
FDF = (GAME / "FDFIELD.DAT").read_bytes()
FDF_E = [FDF[o:o + n] for o, n in unpack_dat.parse_directory(FDF)]
EV17 = []
for m in range(33):
    c = FDF_E[3 * m + 1]
    EV17 += [(m, c[3 + s * 3], c[5 + s * 3]) for s in range(16) if c[3 + s * 3] != 0xFF and c[4 + s * 3] == 17]
    EV17 += [(m, "cell", s) for s in range(16) if c[0x33 + s * 2] == 17]
assert EV17 == [(4, 8, 0)]

# ================= (B) data_map 的對齊填充與沒有引用的段 =================
REG = json.loads(DATA_MAP.read_text(encoding="utf-8"))["regions"]
PADS = [r for r in REG if r["name"].startswith("align_pad_")]
for r in PADS:
    s = int(r["start"], 16)
    e = s + r["size"]
    assert r["size"] < 4 and e % 4 == 0, r["start"]
    assert not any(s <= x < e for x in CODE_REFS | TG), r["start"]
    assert any(int(q["start"], 16) == e for q in REG), r["start"]
assert len(PADS) == 49 and sum(r["size"] for r in PADS) == 103
NOREF = {0x50000: bytes([1, 1, 1, 0]), 0x51940: bytes(4), 0x52828: bytes(8), 0x53734: bytes(60), 0x53AC9: bytes(8),
         0x53AE5: bytes(4), 0x53BB7: bytes(40), 0x53ED4: bytes(4), 0x53F42: bytes(4), 0x6017D: bytes(4)}
for a, want in NOREF.items():
    assert image(a, len(want)) == want and not any(a <= x < a + len(want) for x in CODE_REFS | TG), hex(a)
assert [int.from_bytes(image(0x51EC5 + 4 * k, 4), "little") for k in range(4)] == [0, 1, 2, 3]
assert image(0x51EC5, 16) == image(0x51ED5, 16)
assert [int.from_bytes(image(0x53794 + 4 * k, 4), "little") for k in range(20)] == [1, 2, 2, 3, 2] + [0] * 15
assert FX[0x537E4] == 0x53794 and FX[0x53896] == 0x53858 and FX[0x5389A] == 0x53877 and FX[0x52A4D] == 0x541AC
COVER = sum(r["size"] for r in REG)
assert COVER == 0x56B0 + 0x34D2

# ================= (C) 零填頁(BSS)=================
OB2 = _META["objs"][1]
assert (OB2["base"], OB2["vsize"], OB2["pages"]) == (0x50000, 0x56B0, 4)
OLD = _META["data_off"] + (OB2["first"] - 1) * PS + (0x54157 - OB2["base"])     # 舊公式
OB3 = _META["objs"][2]
OB3_FILE = _META["data_off"] + (OB3["first"] - 1) * PS
assert OB3_FILE <= OLD < OB3_FILE + OB3["pages"] * PS                              # 舊公式落進 obj3 的檔內頁
BSS_RAISES = []
for f, args in ((dl.lin2file, (_META, 0x54157)), (dl.object_bytes, (_EXE, _META, 0x54000, 1))):
    try:
        f(*args)
    except ValueError:
        BSS_RAISES.append(f.__name__)
assert BSS_RAISES == ["lin2file", "object_bytes"]
assert dl.lin2file(_META, 0x53FFF) == _META["data_off"] + (OB2["first"] - 1) * PS + 0x3FFF

# ================= (D) 34 筆沒有用途的資源 =================
RM = json.loads(RES_MAP.read_text(encoding="utf-8"))["resources"]
DATS = sorted({r["dat"] for r in RM})
EMPTY = []
for dat in DATS:
    b = (GAME / dat).read_bytes()
    d = unpack_dat.parse_directory(b)
    z = [i for i, (o, n) in enumerate(d) if n == 0]
    assert z == [len(d) - 1] and d[-1][0] == len(b), dat
    EMPTY.append(f"{dat}#{z[0]}")
assert len(EMPTY) == 11
# BG 背景號來源
BG_SITES = sorted(s - 1 for s, t in FX.items() if t == 0x5248E and _CBASE <= s < _CBASE + len(_CODE))
assert len(BG_SITES) == 16 and all(insn(a + 5) == "call 0x111ba" for a in BG_SITES)
ARGS = {a: insn(a - {0x2D0CA: 8, 0x2D104: 8, 0x2D8B7: 3, 0x2E0D3: 10, 0x2E50B: 10, 0x2E5E1: 6, 0x3015B: 8}.get(a, 0))
        for a in (0x2D0CA, 0x2D104, 0x2D8B7, 0x2E0D3, 0x2E50B, 0x2E5E1, 0x3015B)}
assert ARGS == {0x2D0CA: "push edi", 0x2D104: "push esi", 0x2D8B7: "push eax", 0x2E0D3: "push dword ptr [esp + 8]",
                0x2E50B: "push dword ptr [esp + 0x18]", 0x2E5E1: "push dword ptr [esp + 8]", 0x3015B: "push edi"}
CONST_SITES = {0x2D13C: (0x2D138, "push 0"), 0x2D156: (0x2D14E, "push 1"), 0x2D170: (0x2D168, "push 2"),
               0x2E5FB: (0x2E5F3, "push 0"), 0x2E615: (0x2E60D, "push 1"), 0x2E62F: (0x2E627, "push 2"),
               0x2FB53: (0x2FB51, "push ebp"), 0x2FB6D: (0x2FB65, "push 1"), 0x2FB87: (0x2FB7F, "push 2")}
assert sorted(set(ARGS) | set(CONST_SITES)) == BG_SITES
assert all(insn(src) == txt for src, txt in CONST_SITES.values())
assert insn(0x2FB3D) == "xor ebp, ebp"                                      # push ebp = 0
# 變數型的來源:map_cell_info 輸出 +6、0x52470 章節表、[0x54133](0x52711 表)
assert [insn(a) for a in (0x2D0A5, 0x2D892, 0x2E06E, 0x2E3F1, 0x2E445, 0x2E450, 0x30120)] == [
    "movzx edi, byte ptr [esp + 0x7e]", "mov bl, byte ptr [esp + 6]", "movzx eax, byte ptr [esp + 6]",
    "movzx eax, byte ptr [esp + 6]", "movzx edx, byte ptr [esp + 6]", "movzx eax, byte ptr [esp + 6]",
    "movzx ebx, byte ptr [esp + 0xce]"]
assert FX[0x2E3AE] == FX[0x2E416] == FX[0x30E42] == 0x52470 and FX[0x2E463] == 0x54133
ENDING = list(image(0x52711, 20))
CHAP = set(image(0x52470, 30))
assert ENDING == [4, 3, 51, 14, 25, 18, 40, 53, 22, 24, 28, 17, 30, 31, 50, 33, 34, 52, 36, 47]
TERRAIN = set()
ATTRS = [r["idx"] for r in RM if r["format"] == "terrain_attr"]
assert len(ATTRS) == 33 and all(r["dat"] == "FDSHAP.DAT" for r in RM if r["format"] == "terrain_attr")
for i in ATTRS:
    t = res("FDSHAP.DAT", i)
    TERRAIN |= {t[k + 2] | t[k + 3] << 8 for k in range(0, len(t), 4)}
USED = {0, 1, 2} | TERRAIN | set(ENDING) | CHAP
BG_UNUSED = sorted(set(range(56)) - USED)
assert CHAP == {0, 3} and BG_UNUSED == [11, 12, 13, 15, 20, 23, 26, 38, 39, 45, 46, 54]
# TITLE.DAT 不被開啟;FDMUS 佔位曲只有城鎮循環鍵載入
assert b"TITLE" not in _EXE.upper() and b"TITLE" not in (GAME / "SETSOUND.EXE").read_bytes().upper()
PLACE = [i for i in range(20) if res("FDMUS.DAT", i) == b" \r\n"]
assert PLACE == [0, 2, 5, 7, 9]
assert [insn(a) for a in (0x264C8, 0x264CD, 0x264D6, 0x264DB, 0x264E8)] == [
    "cmp edx, 0x22", "inc byte ptr [esp + 0xc]", "cmp eax, 0xa", "mov byte ptr [esp + 0xc], 0", "call 0x25977"]
assert [insn(a) for a in (0x25A24, 0x25A29, 0x25A32)] == ["call 0x3adf5", "add esp, 0xc", "call 0x3aeee"]

# ================= (E) 單位記錄 +7 的值 =================
G = json.loads(GLYPH.read_text(encoding="utf-8"))
T0 = res("FDTXT.DAT", 0)
NS = struct.unpack_from("<H", T0, 0)[0] // 2
OFFS = [struct.unpack_from("<H", T0, 2 * i)[0] for i in range(NS)] + [len(T0)]


def text0(i: int) -> str:
    w = [struct.unpack_from("<H", T0, k)[0] for k in range(OFFS[i], OFFS[i + 1], 2)]
    assert w[-1] == 0xFFFF and all(c < 0xFF00 for c in w[:-1]), i
    return "".join(G[str(c)] for c in w[:-1])


assert NS == 661
# 名字 = FDTXT_000 第 +8 + 1 條(0x18d73 byte [+8] + 1)
assert [insn(a) for a in (0x18D73, 0x18D77, 0x18D79, 0x18D7F)] == [
    "movzx eax, byte ptr [esi + 8]", "inc eax", "push dword ptr [0x3a7d]", "call 0x15f84"]
CHAR = json.loads(CHARS.read_text(encoding="utf-8"))
assert [text0(k + 1) for k in range(32)] == [c["name"] for c in CHAR]
CCT = json.loads(CC.read_text(encoding="utf-8"))["current_portraits"]
FORM: dict[int, str] = {}
for c in CCT:
    p = c["portrait"]
    FORM[c["default_target"]] = f"{CHAR[p]['name']}(角色 {p})轉職"
    if "optional_target" in c:
        FORM[c["optional_target"]] = f"{CHAR[p]['name']}(角色 {p})持指定道具轉職"
    if "special_target" in c:
        FORM[c["special_target"]] = f"{CHAR[p]['name']}(角色 {p})持道具 {c['special_item']} 轉職"
assert sorted(FORM) == sorted(set(range(32, 68)) - {66, 67})
# 轉職資格 unit[+7] != 7:角色 7 的兩個形態 39 / 57 經教會轉職到不了
assert [insn(a) for a in (0x2AE5D, 0x2AE61, 0x2AE66, 0x2AE6B)] == [
    "movzx eax, byte ptr [esi + 0x21]", "cmp eax, 0x14", "cmp ebx, 0x12", "cmp ebx, 7"]
# FDFIELD 記錄的 b1 使用次數
USE: dict[int, list[int]] = {}
for m in range(33):
    c = FDF_E[3 * m + 1]
    for k in range(c[2]):
        USE.setdefault(c[0x83 + k * 26 + 1], []).append(m)
KEYS = []
for k in range(136):
    if k < 32:
        who = f"角色 {k}「{text0(k + 1)}」({CHAR[k]['cls_name']})"
    elif k < 68:
        who = FORM.get(k, "沒有轉職公式會產生")
    else:
        nm = text0(k + 1)
        who = f"一般單位「{nm}」(high_class 第 {k - 68} 列)" if nm else f"一般單位(high_class 第 {k - 68} 列;名稱字串空白)"
    maps = sorted(set(USE.get(k, [])))
    KEYS.append(f"{k}: {who};FDFIELD {len(USE.get(k, []))} 筆" + (f"(圖 {', '.join(map(str, maps))})" if maps else ""))
assert len(KEYS) == 136 and len(unpack_dat.parse_directory((GAME / "DATO.DAT").read_bytes())) - 1 == 136
assert len(unpack_dat.parse_directory((GAME / "FIGANI.DAT").read_bytes())) - 1 == 136 * 3
# FIGANI k 的載入點:k = 0 11、k = 1 6、k = 2 2;spell_cast_scene 在 k = 2 幀數為 0 時改載 k = 1
FIG_SITES = sorted(s - 1 for s, t in FX.items() if t == 0x52495 and _CBASE <= s < _CBASE + len(_CODE))
assert len(FIG_SITES) == 19
assert [insn(a) for a in (0x30241, 0x30289, 0x3028C, 0x3028E, 0x30290, 0x30291)] == [
    "lea eax, [edi + 2]", "movsx eax, word ptr [ebx]", "test eax, eax", "jne 0x302a7", "inc edi", "push edi"]
assert [insn(a) for a in (0x2D248, 0x2D24B)] == ["add ebx, 2", "push ebx"]
K2 = [g for g in range(136) if len(res("FIGANI.DAT", g * 3 + 2)) > 3]
assert len(K2) == 17
K2_NAMES = [f"{g}:{text0(g + 1) or FORM.get(g, '')}" for g in K2]

# ================= (F) 實機:ISR 堆疊高水位、兩個 extender 緩衝(drivers_s287/lc287.py,預測 pred287.txt)=================
LIVE = ROOT / ".wsl_build" / "lc287_live" / "lc287a"
ISR_MD5 = {"A": "3ef9ff338c0b0b1a465252fd22ac8261", "B": "cbb52a9d96673a62ccf7685299df7f62",
           "C": "e59e15fc315e51a5185fadd3207a8f36"}
HW = {}
for lab, want in ISR_MD5.items():
    raw = {k: (LIVE / lab / f"{k}.bin").read_bytes() for k in
           ("isr_stack", "sysreg", "fa20", "ctl_dos4g", "ctl_tz", "fpu", "emu_flags")}
    assert hashlib.md5(raw["isr_stack"]).hexdigest() == want, lab
    # 對照:讀到的是本程式資料區(執行期 = LE 線性 + 0x19C000)
    assert raw["ctl_dos4g"] == image(0x51760, 16) == b"RATIONAL DOS/4G\0" and raw["ctl_tz"] == image(0x516F0, 3) == b"TZ\0"
    st = raw["isr_stack"][:0x800]
    nz = [i for i, x in enumerate(st) if x]
    assert nz and image(0x52DFC, 0x800) == bytes(0x800)              # 檔內初值全 0,非 0 = 執行時寫的
    HW[lab] = 0x800 - nz[0]
    assert raw["sysreg"] == bytes(0x40) and raw["fa20"] == bytes(0x80)
    assert raw["fpu"] == b"\x03\x03" and raw["emu_flags"] == b"\0\0"
    # 返回位址在 ail_timer_isr 的回呼迴圈(0x3eb3c call [edi + 0x52a54] 之後一條)
    assert (0x3EB42 + 0x19C000).to_bytes(4, "little") in st
assert HW == {"A": 228, "B": 228, "C": 230}
assert insn(0x3EB3C) == "call dword ptr [edi + 0x2a54]"

# ================= (G) 實機:FDMUS 佔位曲(drivers_s287/lc287b.py,預測 pred287b.txt)=================
import calllog_segments as cs  # noqa: E402

LB = ROOT / ".wsl_build" / "lc287b_live"
CALLLOG_MD5 = {"lc287b": "42db616db7193bdaf90ab5cae631fde6", "lc287e": "e06074c58dcd6a52806d8ea0a138a828",
               "lc287f": "7ef7c889f7ed6a420cafddf019628eb9"}
LIVE_DELTA = 0x19C000


def seq(inst: str, label: str) -> dict:
    """lc287b.py `seq` 存下的原始 dump:handle 0x20 byte、[0x53ee0]、AIL 錯誤緩衝、[0x51a11]。"""
    d = LB / "cl" / inst
    st = (d / f"{label}_seq.bin").read_bytes()
    assert len(st) == 0x20, (inst, label)
    u = lambda b, o=0: int.from_bytes(b[o:o + 4], "little")  # noqa: E731
    return {"status": u(st, 4), "p10": u(st, 0x10), "evnt": u(st, 0x14),
            "musbuf": u((d / f"{label}_musbuf.bin").read_bytes()),
            "bgm": (d / f"{label}_bgmno.bin").read_bytes()[0],
            "err": (d / f"{label}_ailerr.bin").read_bytes().split(b"\0")[0]}


INVALID = image(0x515F4, 24)[:-1]
assert INVALID == b"Invalid XMIDI sequence\n"
B = {k: seq("lc287b", k) for k in ("sg1", "sg2", "sg3", "sg4", "sg5a", "sg5b", "sh1", "sh2")}
assert [B[k]["bgm"] for k in ("sg1", "sg2", "sg3", "sg4", "sg5a")] == [1, 2, 3, 4, 5]
assert B["sg1"]["status"] == 4 and B["sg1"]["err"] == b""
# 佔位曲 2:init 失敗(錯誤緩衝 = "Invalid XMIDI sequence\n"),start 仍設狀態 4;p10 沿用第 1 首,新的 3 byte 緩衝在別處
assert B["sg2"]["err"] == INVALID and B["sg2"]["status"] == 4 and B["sg2"]["p10"] == B["sg1"]["p10"]
assert B["sg2"]["musbuf"] != B["sg1"]["musbuf"] and B["sg3"]["musbuf"] == B["sg1"]["musbuf"]
assert B["sg2"]["evnt"] == B["sg1"]["evnt"]                     # 同樣按鍵後約 2 s 讀:從第 1 首開頭重播到同一點
# 佔位曲 5:沿用第 4 首的 p10,兩次讀之間事件指標前進
assert B["sg5a"]["p10"] == B["sg4"]["p10"] and B["sg5a"]["err"] == INVALID and B["sg5b"]["evnt"] > B["sg5a"]["evnt"]
# 出擊後卡住:play_bgm(-1)([0x51a11] = 255)只淡出,序列仍是狀態 4、緩衝仍是佔位曲那塊,事件指標不動
for k in ("sh1", "sh2"):
    assert B[k]["bgm"] == 255 and B[k]["status"] == 4 and B[k]["musbuf"] == B["sg5a"]["musbuf"]
assert B["sh1"]["evnt"] == B["sh2"]["evnt"]
F = {k: seq("lc287f", k) for k in ("sg1", "sg2", "sh1", "sh2")}
assert F["sg2"] == {**B["sg2"]}                                    # 重現:同一份存檔、同樣按鍵,讀值逐欄相同
assert all(F[k]["bgm"] == 255 and F[k]["status"] == 4 for k in ("sh1", "sh2")) and F["sh1"]["evnt"] == F["sh2"]["evnt"]
E2 = {k: seq("lc287e", k) for k in ("sg1", "sg2", "sg3", "sg4")}
assert E2["sg4"]["bgm"] == 4 and E2["sg2"]["err"] == INVALID


def inputs(inst: str) -> int:
    p = LB / f"{inst}_CALLLOG.TXT"
    assert hashlib.md5(p.read_bytes()).hexdigest() == CALLLOG_MD5[inst], inst
    log = cs._read(str(p), calls=True)
    assert log.calls_parsed and log.game_cs == 0x170
    return sum(1 for c in log.calls if c.eip - LIVE_DELTA == 0x117E7)


CALLLOG_MD5["lc287d"] = "b1f6bc7437a1b94c067ac55ddc0d8118"
IL = {k: inputs(k) for k in CALLLOG_MD5}
assert IL["lc287b"] == 0 and IL["lc287f"] == 0 and IL["lc287e"] >= 1 and IL["lc287d"] >= 1, IL

# ================= (H) 實機:演出第 24 筆的 pose 5(lc287d,不寫記憶體、正常結束 7 次回合)=================
LOG_D = cs._read(str(LB / "lc287d_CALLLOG.TXT"), calls=True)
EV17_CALLS = [c for c in LOG_D.calls if c.eip - LIVE_DELTA == 0x34A1E]
ACT18 = [c for c in LOG_D.calls if c.eip - LIVE_DELTA == 0x1366A and c.stack[0] == 0x18]   # s1 = 第 1 個引數
assert len(EV17_CALLS) == 1 and len(ACT18) == 1 and ACT18[0].line > EV17_CALLS[0].line


def unit(label: str, idx: int) -> tuple[bytes, int]:
    d = LB / "cl" / "lc287d"
    return (d / f"{label}_u{idx}.bin").read_bytes(), int.from_bytes((d / f"{label}_round.bin").read_bytes(), "little")


U1, RND = unit("A2u1", 1)
assert RND == 8 and len(U1) == 0x10 and U1[3] == 5 and U1[6] == 2 and U1[2] == 1   # 我方、快取槽 1、pose 5
assert (U1[7], U1[8]) == (0x34, 9)                                                    # 悠妮(角色 9)持道具 0x5a 的轉職形態
assert all(unit(f"A2u{i}", i)[0][3] == 0 for i in (48, 49, 50, 51))
U2, _ = unit("A2u2", 2)
assert U2[2] == 2                                                                     # pose 5 會取到槽 2 = 單位 2 的向左圖
U1B, RNDB = unit("A2b", 1)
assert RNDB == 8 and U1B[3] == 0                                                      # 對白之後、敵方階段裡被改回 0

OUT.write_text(json.dumps({
    "generator": "docs/knowledge-base/evidence/generators/ev_s287.py",
    "exe_md5": MD5,
    "A_acting_bank": {"start": hex(BANK), "end": hex(OBJ3_END), "sequences": N,
                      "contiguous": N - len(ODD), "odd": ODD,
                      "act24_overrun_pair": [1, 5], "act84_tail": TAIL84.hex(" "),
                      "poses": sorted(POSES), "poses_without_act24": sorted(POSES_NOT24),
                      "event17_trigger": [list(x) for x in EV17]},
    "B_data_map": {"align_pads": len(PADS), "align_pad_bytes": sum(r["size"] for r in PADS),
                   "unreferenced": [hex(a) for a in NOREF], "covered_bytes": COVER},
    "C_bss": {"old_formula_file_offset_0x54157": hex(OLD), "obj3_file_start": hex(OB3_FILE), "now_raises": BSS_RAISES},
    "D_unused_resources": {"empty_last_slots": EMPTY, "bg_unused": BG_UNUSED, "bg_terrain_values": sorted(TERRAIN),
                           "bg_ending_table": ENDING, "fdmus_placeholders": PLACE},
    "E_unit_keys": {"keys": KEYS, "figani_k2_groups": K2_NAMES,
                    "figani_sites": {"k0": 11, "k1": 6, "k2": 2}},
    "F_live": {"isr_high_water": HW, "isr_stack_md5": ISR_MD5, "sysreg_all_zero": True, "fa20_all_zero": True,
               "fpu_detect": "03 03", "emu387_flags": "00 00"},
    "G_fdmus_placeholder": {"status_after_placeholder": B["sg2"]["status"], "ail_error": INVALID.decode(),
                            "replay_same_evnt": hex(B["sg2"]["evnt"]), "hang_evnt": [hex(B["sh1"]["evnt"]), hex(F["sh1"]["evnt"])],
                            "input_loop_entries": IL, "calllog_md5": CALLLOG_MD5},
    "H_act24_pose5": {"round": RND, "unit1_pose_after_act": U1[3], "unit1_slot": U1[2], "unit1_key7_key8": [U1[7], U1[8]],
                      "units48_51_pose": 0, "unit1_pose_later": U1B[3], "ev17_calls": 1, "act18_calls": 1},
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ev_s287 ok", OUT.name)
