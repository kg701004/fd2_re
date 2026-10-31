"""續一百七十八證據:evidence/dig_word_order_sfx_s178_20261101.json(續一百七十六仍留:(D) 回傳字序與 DS 基底、兩群各 3 筆的 m、
31253 / 36793 型各是哪個音效)。

使用者 2026-11-01「做三項離線分析」。沒有新實機:用 FD2.EXE / SB16.DIG 反組譯、遊戲 .DAT,與既有的 DOSBox-X 呼叫紀錄
—— 續一百零七的 cl1 .. cl14(dump=32,每個入口前 200 次附指標處 32 位元組)與續一百七十六證據裡逐次填緩衝的區間。
(D1) 字序:0x382e9 → 0x3836b call 0x3f113,以 DPMI 0300h 模擬真實模式中斷,呼叫結構在 ebp-0x3a;0x3f1ac .. 0x3f1d7 把結構裡的
     ax / bx / cx / dx 抄到回傳結構 +0 / +2 / +4 / +6,遊戲 0x40d79 .. 0x40d9b 讀字 3:字 0 與字 2:字 1 → [drv+4] = dx:ax、[drv+8] = cx:bx。
     SB16.DIG 派送 0x191 .. 0x19c 存、0x1ca .. 0x1d5 讀回 [0x124 + 2k];功能 0x301 寫 ax = 0x40c、bx = 0x4fc、cx = dx = cs。
     紀錄:12 份的 DIG 服務入口 s1 = drv,[drv+4] / [drv+8] = 段 × 16 + 0x40c / 0x4fc(9 份段 137c、3 份 137e);24 種字序只有 2 種
     (cx / dx 互換,兩者都是 cs)對得上全部,靜態取的是其中之一。[drv+0x34] 由 0x40dd4 call 0x37910 入口的 eax 直接看到 = [drv+8] + 8。
(D2) DS 基底 0:SB16.DIG 功能 0x300(派送 ds = cs)經 0x785 call 0x1ff 與 0x788 .. 0x79a 寫 [0xc] = 0x50e、[0xe] = [0x14] = cs、[0x10] = 2、
     [0x12] = 0x506、[0x2e] = [0x504] = 0xffff。遊戲以 DS:段 × 16 + 位移 讀到:呼叫 0x300 之前是檔案位元組(全 0)或剛配置的 0xcc,
     之後正好是這些值,[0xe] / [0x14] 等於自己的段 —— 實模式寫在實體 段 × 16 + 位移,DS 讀同一個數字的位址看到它,DS 基底只能是 0。
(M) 兩群各 3 筆:續一百七十六的雜訊窗(觀測 − 真值 ∈ [−9, +2])與「m 為整數」各只留一個真值:25273(m = 181)、27073(m = 361)。
(S) 音效:混音器 0x49690 步長 = 取樣率 × 65536 / 輸出率(0x49702 .. 0x49715),每次填緩衝 0x497c0 把小數累加器設 0x80000000,
     0x49430 每輸出一個樣本先讀再加步長;11025 / 22050 時步長 0.5 → 一個 L 位元組的樣本放 k 次混滿加最後一次 m 個輸出。
     逐次模擬所有 .DAT 的資源與巢狀子段,五型各只對到一份波形:30133 型 FDOTHER #78 第 0 段(6478)、25273 型 6235 位元組那段
     (#49 第 6 / #53 第 2 / #77 第 3 段逐位元組相同)、27073 型 #77 第 1 段(4277,續一百六十一的確認音效)、31253 型 #31 第 9 段(390)、
     36793 型 #31 第 2 段(667)。對照:累加器從 0 起算時 m 都是偶數,五型一個都對不到。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import itertools
import json
import re

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import ail_driver_disasm as ad  # noqa: E402
import calllog_segments as cs  # noqa: E402
import unpack_dat as ud  # noqa: E402

OUT = out_path("dig_word_order_sfx_s178_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S176 = json.loads((EVIDENCE / "dig_fill_lengths_s176_20261031.json").read_text(encoding="utf-8"))
CL = ["cl1", "cl2", "cl3", "cl4", "cl5", "cl6", "cl7", "cl9", "cl11", "cl12", "cl13", "cl14"]
LOG_MD5 = {"cl1": "8abf1cb92b0116ce1aa799df2c2e60aa", "cl2": "4e7c32f7f87bd445f6a7113af1f0ba7b", "cl3": "099f3908148b60a30fffc142163158d4",
           "cl4": "0146d00b11c60c2c4af4b3634830af42", "cl5": "5bbb99e2b0d9ceb51911aea81fe78136", "cl6": "ea9e81aa4498215f1d3d493d064a2501",
           "cl7": "47e61b1f95407a604b4d3497dfe4c4a5", "cl9": "85309696d4f62765a01d70585f9e6f07", "cl11": "20b89f9579c609a6298c2e8c2e954c01",
           "cl12": "ca706ebabe69b66d14f6ab233564a869", "cl13": "7bda602d49a41cd635553357752204ba", "cl14": "aa50b76a131b35cf8c719dd747ba6b5c"}
RAW = {nm: ROOT / f".wsl_build/{nm}_CALLLOG.TXT" for nm in CL}
SERVE, DRVCALL, MIXCALL, MEMSET, AFTER_301 = 0x404C0, 0x382E9, 0x49690, 0x37910, 0x40DD9
REAL_TOP = 0x100000                  # 真實模式定得到的範圍(遊戲自己讀檔的緩衝在這之上)
FRESH = 0xCCCC                       # 剛配置、還沒載入驅動時那塊記憶體的內容(紀錄裡看到的)

assert hashlib.md5(_EXE).hexdigest() == MD5


def rt(a: int) -> int:
    return a + DELTA


# ================= (D1) 靜態:FD2.EXE 這邊的字序 =================
STATIC_EXE = {0x3836B: "call 0x3f113", 0x3F190: "mov eax, 0x300", 0x3F1A2: "int 0x31", 0x3F1A4: "mov ebx, dword ptr [ebp + 0x14]",
              0x3F14B: "pushf", 0x3F153: "mov eax, dword ptr [ebp + 0xc]", 0x40D6D: "call 0x382e9", 0x40D72: "add esp, 0x10",
              0x40DA7: "lea eax, [edx + 8]", 0x40DD1: "mov dword ptr [edx + 0x34], eax", 0x40DD4: "call 0x37910"}
for _a, _t in STATIC_EXE.items():
    assert insn(_a).rstrip() == _t.rstrip(), (hex(_a), insn(_a), _t)
# 0x382e9 把自己的 4 個參數原樣再推給 0x3f113(每推一個 esp 少 4,同一個 [esp + 0x1c] 依序取到第 4、3、2、1 個)
for _a, _r in ((0x38357, "ecx"), (0x3835C, "esi"), (0x38361, "edi"), (0x38366, "ebp")):
    assert insn(_a) == f"mov {_r}, dword ptr [esp + 0x1c]", (hex(_a), insn(_a))
RMCS_AT = operand(0x3F19F, "lea edi, [ebp - ", "]")          # int 31h 0300h 的 es:edi
# DPMI 0.9 的真實模式呼叫結構:位移 → 暫存器
DPMI_RMCS = {0x00: "edi", 0x04: "esi", 0x08: "ebp", 0x10: "ebx", 0x14: "edx", 0x18: "ecx", 0x1C: "eax", 0x20: "flags"}


def rmcs_field(addr: int, text_before: str, text_after: str = "") -> str:
    """addr 那一條以 [ebp - d] 存取呼叫結構;回傳那一格的暫存器名。"""
    return DPMI_RMCS[RMCS_AT - operand(addr, text_before, text_after)]


# 版面自洽:pushf 的旗標放在旗標格、功能號(第 2 個參數)放在 eax 格
assert rmcs_field(0x3F14F, "mov word ptr [ebp - ", "], ax") == "flags"
assert rmcs_field(0x3F156, "mov word ptr [ebp - ", "], ax") == "eax"
# 回傳:呼叫結構的暫存器 → 回傳結構位移
OUT_REG: dict[int, str] = {}
for _ld, _st, _r in ((0x3F1AC, 0x3F1C0, "ax"), (0x3F1B0, 0x3F1C3, "cx"), (0x3F1B4, 0x3F1C7, "dx"), (0x3F1D3, 0x3F1D7, "ax")):
    _f = rmcs_field(_ld, f"mov {_r}, word ptr [ebp - ", "]")
    _o = 0 if insn(_st) == f"mov word ptr [ebx], {_r}" else operand(_st, "mov word ptr [ebx + ", f"], {_r}")
    OUT_REG[_o] = _f[1:]                                       # eax → ax
assert sorted(OUT_REG) == [0, 2, 4, 6], OUT_REG
# 遊戲讀回傳結構的哪個字(同續一百七十六)
_ws = operand(0x40D61, "lea edx, [esp + ", "]")
WIDX = {nm: (operand(a, f"mov {r}, word ptr [esp + ", "]") - _ws) // 2
        for nm, a, r in (("seg4", 0x40D79, "ax"), ("off4", 0x40D7E, "dx"), ("seg8", 0x40D8F, "ax"), ("off8", 0x40D9B, "ax"))}
SEG_SHIFT = operand(0x40D83, "shl eax, ")
assert operand(0x40D98, "shl edx, ") == SEG_SHIFT
PLUS34 = operand(0x40DA7, "lea eax, [edx + ", "]")
WORD_REG = {nm: OUT_REG[2 * k] for nm, k in WIDX.items()}     # {"seg4": "dx", "off4": "ax", "seg8": "cx", "off8": "bx"}

# ================= (D1) 靜態:SB16.DIG 這邊 =================
DIG = (GAME / "SB16.DIG").read_bytes()
KIND, DISP = ad.parse_header(DIG)
FTAB, _call = ad.function_table(DIG, DISP)
FN = {e.num: e.addr for e in FTAB}
assert KIND == "DIG" and _call is not None


def insn16(a: int) -> str:
    try:
        return ad.insn_text(DIG, a)
    except ValueError as e:
        raise AssertionError((hex(a), str(e))) from e


INIT_FN = [n for n, a in FN.items() if insn16(a) == "call 0x1ff"]     # 初始化:表裡唯一一格一進來就 call 0x1ff
assert len(INIT_FN) == 1, INIT_FN
INIT_FN = INIT_FN[0]
STATIC_DIG = {0x18C: "push cs", 0x18D: "push cs", 0x18E: "pop ds", 0x18F: "pop es", FN[INIT_FN]: "call 0x1ff", 0x20D: "ret "}
for _a, _t in STATIC_DIG.items():
    assert insn16(_a) == _t, (hex(_a), insn16(_a), _t)
# 派送:存 / 讀回暫存器的那幾格
SAVE = {m.group(2): int(m.group(1), 16) for a in (0x191, 0x194, 0x198, 0x19C)
        for m in [re.fullmatch(r"mov word ptr \[(0x[0-9a-f]+)\], (ax|bx|cx|dx)", insn16(a))] if m}
LOAD = {m.group(1): int(m.group(2), 16) for a in (0x1CA, 0x1CD, 0x1D1, 0x1D5)
        for m in [re.fullmatch(r"mov (ax|bx|cx|dx), word ptr \[(0x[0-9a-f]+)\]", insn16(a))] if m}
assert SAVE == LOAD and len(SAVE) == 4, (SAVE, LOAD)


def writes(addrs: list[int]) -> dict[int, int | str]:
    """一段直線碼對 [位移] 寫的字;cs 記成 "cs",ax 取最近一次 mov ax, 立即數。"""
    out: dict[int, int | str] = {}
    ax = None
    for a in addrs:
        t = insn16(a)
        m = re.fullmatch(r"mov ax, (0x[0-9a-f]+)", t)
        if m:
            ax = int(m.group(1), 16)
            continue
        m = re.fullmatch(r"mov word ptr \[(0x[0-9a-f]+)\], (cs|ax|0x[0-9a-f]+|\d+)", t)
        assert m, (hex(a), t)
        v = m.group(2)
        out[int(m.group(1), 16)] = "cs" if v == "cs" else (ax if v == "ax" else int(v, 0))
        assert out[int(m.group(1), 16)] is not None, (hex(a), t)
    return out


RET301 = writes([FN[0x301], FN[0x301] + 4, FN[0x301] + 0xA, FN[0x301] + 0xE])
REG301 = {r: RET301[slot] for r, slot in LOAD.items()}          # 功能 0x301 返回時的 ax / bx / cx / dx
assert set(REG301) == {"ax", "bx", "cx", "dx"}, REG301
# 功能 0x300:0x785 call 0x1ff(0x1ff .. 0x209)後 0x788 .. 0x79a
INIT_W = writes([0x1FF, 0x205, 0x209]) | writes([0x788, 0x78B, 0x78E, 0x794, 0x797, 0x79A])
OFF4, OFF8 = REG301[WORD_REG["off4"]], REG301[WORD_REG["off8"]]
assert REG301[WORD_REG["seg4"]] == REG301[WORD_REG["seg8"]] == "cs", REG301
OFF34 = OFF8 + PLUS34
assert OFF34 in INIT_W and [k for k, v in INIT_W.items() if v == "cs"], INIT_W


# ================= (D) 紀錄:cl1 .. cl14 =================
def word(c: cs.Call, nm: str, addr: int) -> int | None:
    """DS:addr 的字(由 c 的 nm 那格傾印讀;不在傾印範圍內是 None)。"""
    rel_ = addr - c.ptr(nm)
    return c.field_at(nm, rel_, 2) if rel_ >= 0 else None


MAGIC = DIG[:8]
D_ROWS = {}
for nm, p in RAW.items():
    assert hashlib.md5(p.read_bytes()).hexdigest() == LOG_MD5[nm], nm
    lg = cs._read(str(p), calls=True)
    assert lg.game_cs == 0x170 and lg.dump_len == 32, (nm, lg.dump_len)
    svc = [c for c in lg.calls if c.eip == rt(SERVE)]
    drvs = {c.ptr("s1") for c in svc}
    assert svc and len(drvs) == 1, (nm, drvs)
    drv = drvs.pop()
    f = {o: {c.field_at("s1", o, 4) for c in svc} for o in (0, 4, 8, 0x10, 0x14)}
    assert all(len(v) == 1 for v in f.values()), (nm, f)
    d0, d4, d8, d10, d14 = (f[o].pop() for o in (0, 4, 8, 0x10, 0x14))
    # 驅動映像:傾印開頭是 AIL3DIG 檔頭的指標(獨立於 [drv+4] / [drv+8] 找)
    imgs = {c.ptr(k) for c in lg.calls for k in cs.PTR_ORDER
            if c.ptr(k) < REAL_TOP and c.mem[k] is not None and c.mem[k][:len(MAGIC)] == MAGIC}
    assert len(imgs) == 1, (nm, sorted(map(hex, imgs)))
    img = imgs.pop()
    seg, _rem = divmod(img, 1 << SEG_SHIFT)
    assert _rem == 0, (nm, hex(img))
    # DIG 的初始化功能那一次(0x382e9 的第一個參數是驅動描述 [drv+0];MDI 也有自己的 0x300),而且是這個驅動的第一個呼叫
    digcalls = [c for c in lg.calls if c.eip == rt(DRVCALL) and c.stack[0] == d0]
    init = [c for c in digcalls if c.stack[1] == INIT_FN]
    assert len(init) == 1 and lg.rets.get(init[0].seq) is not None, (nm, len(init))
    assert min(c.line for c in digcalls) == init[0].line, nm
    l0, l1 = init[0].line, lg.rets[init[0].seq].line
    obs: dict[tuple[int, str], dict[int, set[int]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    for c in lg.calls:
        when = "before" if c.line < l0 else ("after" if c.line > l1 else None)
        if when is None:
            continue
        for off in INIT_W:                                # 同一筆的幾格指標讀到同一處只算一次(以行號數筆)
            for w in {word(c, k, img + off) for k in cs.PTR_ORDER} - {None}:
                obs[(off, when)][w].add(c.line)
    after = {off: {w: len(ls) for w, ls in obs[(off, "after")].items()} for off in INIT_W}
    before = {off: {w: len(ls) for w, ls in obs[(off, "before")].items()} for off in INIT_W if obs[(off, "before")]}
    want = {off: (seg if v == "cs" else v) for off, v in INIT_W.items()}
    # 之後:每一筆都正好是功能 0x300 寫的值;之前:只有檔案位元組或剛配置的 0xcc,且有檔案位元組
    assert all(after[off] and set(after[off]) == {want[off]} for off in INIT_W), (nm, after, want)
    for off, cnt in before.items():
        filew = int.from_bytes(DIG[off:off + 2], "little")
        assert filew != want[off] and filew in cnt and set(cnt) <= {filew, FRESH}, (nm, hex(off), cnt)
    assert {o for o in before} >= {o for o, v in INIT_W.items() if v == "cs"}, (nm, before)
    # [drv+0x34]:0x40dd4 call 0x37910 入口的 eax(0x40da7 之後沒動)
    ms = [c for c in lg.calls if c.eip == rt(MEMSET) and c.ret == rt(AFTER_301)]
    assert len(ms) == 1, (nm, len(ms))
    d34 = ms[0].regs["eax"]
    # 混音器入口:樣本結構 [+0] 就是這個 drv(0x4969b mov edi, [ecx] → 輸出率 [edi+0x14])
    mix_drv = {c.field_at("s1", 0, 4) for c in lg.calls if c.eip == rt(MIXCALL)}
    D_ROWS[nm] = {"drv": drv, "desc": d0, "seg": seg, "d4": d4, "d8": d8, "d10": d10, "d14": d14, "d34": d34,
                  "d34_word": ms[0].field_at("eax", 0, 2), "mix_drv": sorted(x for x in mix_drv if x is not None),
                  "init_lines": [l0, l1], "before": before, "after": after}

for nm, r in D_ROWS.items():
    s16 = r["seg"] << SEG_SHIFT
    assert r["d4"] == s16 + OFF4 and r["d8"] == s16 + OFF8, (nm, r)
    assert r["d34"] == r["d8"] + PLUS34 == s16 + OFF34, (nm, r)
    assert r["d34_word"] == INIT_W[OFF34], (nm, r)
    assert r["mix_drv"] == [r["drv"]], (nm, r)
SEGS = collections.Counter(r["seg"] for r in D_ROWS.values())
assert len(SEGS) >= 2, SEGS                                   # 兩個不同的載入段都要對
SEG_TOP = SEGS.most_common(1)[0][0]
HW = {r["d14"] for r in D_ROWS.values()}
assert len(HW) == 1, HW
HW_RATE = HW.pop()


# 對照:24 種字序裡對得上全部紀錄的
def regval(r: str, seg: int) -> int:
    v = REG301[r]
    return seg if v == "cs" else v


FIT = []
for perm in itertools.permutations(["ax", "bx", "cx", "dx"]):     # perm[k] = 字 k 的暫存器
    if all((regval(perm[WIDX["seg4"]], r["seg"]) << SEG_SHIFT) + regval(perm[WIDX["off4"]], r["seg"]) == r["d4"]
           and (regval(perm[WIDX["seg8"]], r["seg"]) << SEG_SHIFT) + regval(perm[WIDX["off8"]], r["seg"]) == r["d8"]
           for r in D_ROWS.values()):
        FIT.append(" / ".join(perm))
STATIC_ORDER = " / ".join(OUT_REG[2 * k] for k in range(4))
assert STATIC_ORDER in FIT and len(FIT) == 2, (STATIC_ORDER, FIT)

# ================= (M) 兩群各 3 筆的 m =================
BASE0 = S176["prediction"]["base0"]
JIT = tuple(S176["prediction"]["jitter_window"])
PER_MIX = S176["static"]["per_sample"]["mix"]
END = S176["static"]["mix_end"] + S176["static"]["src_done"]
N_OUT = collections.Counter((b["mix"] - 1) // PER_MIX for b in S176["y_blocks"])
assert len(N_OUT) == 1, N_OUT
N_OUT = N_OUT.popitem()[0]
assert {r["d10"] for r in D_ROWS.values()} == {N_OUT}, N_OUT       # [drv+0x10] 就是一次填的輸出樣本數


def m_of(t: int) -> int | None:
    q, r = divmod(t - BASE0 - END, PER_MIX)
    return q if r == 0 else None


TRUE_T: dict[int, int] = {}                                      # 觀測區間 → 真值
WEAK = []
for gp in S176["observed"]["partial_groups"]:
    vals = sorted(int(v) for v in gp["values"])
    lo, hi = max(vals) - JIT[1], min(vals) - JIT[0]
    cands = [t for t in range(lo, hi + 1) if m_of(t) is not None]
    if gp["mode_n"] >= 3:
        assert cands == [gp["mode"]], (gp, cands)
    else:
        assert len(cands) == 1, (vals, cands)
        WEAK.append({"values": vals, "window": [lo, hi], "true": cands[0], "m": m_of(cands[0])})
    TRUE_T.update({v: cands[0] for v in vals})
assert len(WEAK) == 2, WEAK

# ================= (S) 混音器模型與音效 =================
STATIC_MIX = {0x496FD: "mov eax, 0", 0x49702: "mov edx, dword ptr [ecx + 0x3c]", 0x4969B: "mov edi, dword ptr [ecx]",
              0x4970F: "mov ebx, dword ptr [edi + 0x14]", 0x49712: "shl ebx, 0x10", 0x49715: "div ebx",
              0x4972B: "mov ebx, eax", 0x4972D: "shr ebx, 0x10", 0x49730: "shl eax, 0x10", 0x49733: "mov dword ptr [0x38b4], eax",
              0x49738: "mov eax, ebx", 0x4975B: "mov dword ptr [0x38b8], eax",
              0x49430: "cmp esi, dword ptr [0x38a8]", 0x49436: "jae 0x49456", 0x49438: "mov al, byte ptr [esi]",
              0x4943A: "add ecx, dword ptr [0x38b4]", 0x49440: "adc esi, dword ptr [0x38b8]",
              0x4944E: "cmp edi, dword ptr [0x38b0]", 0x49454: "jb 0x49430",
              0x497DA: "mov eax, esi", 0x497E0: "mov dword ptr [ecx + ebx*4 + 0x18], eax"}
for _a, _t in STATIC_MIX.items():
    assert insn(_a) == _t, (hex(_a), insn(_a), _t)
ACC0 = operand(0x497C0, "mov ecx, ")                           # 每次填緩衝重設(小數不留到下一次)
RATE = operand(0x4154E, "mov dword ptr [eax + 0x3c], ")       # AIL_init_sample 的預設(續一百六十一)
FMT = operand(0x41540, "mov dword ptr [eax + 0x34], ")        # 0 = 8 位元單聲道:0x4973b / 0x4974b 的移位都不做
assert FMT == 0
STEP = (RATE << 16) // HW_RATE
S_INT, S_FRAC = STEP >> 16, (STEP << 16) & 0xFFFFFFFF


def per_fill(acc0: int) -> int:
    """樣本夠長時一次混滿用掉幾個來源樣本(每次都從 acc0 起算,所以每次一樣)。"""
    acc, pos = acc0, 0
    for _ in range(N_OUT):
        acc += S_FRAC
        pos += S_INT + (acc >> 32)
        acc &= 0xFFFFFFFF
    assert pos > 0, (acc0, pos)                                # 每次都要前進,否則下面的模擬不會結束
    return pos


def play(length: int, acc0: int = ACC0) -> tuple[int, int] | None:
    """長 length 位元組的樣本:(混滿幾次, 最後一次輸出幾個);剛好在緩衝邊界放完時 None。

    前面剩下至少兩次份量的那幾次一定混滿,直接跳過;最後幾次逐個輸出樣本模擬。"""
    c = per_fill(acc0)
    full = max(0, length // c - 2)
    pos = full * c
    while True:
        acc, n, p0 = acc0, 0, pos
        while n < N_OUT and pos < length:
            acc += S_FRAC
            pos += S_INT + (acc >> 32)
            acc &= 0xFFFFFFFF
            n += 1
        assert pos > p0 and acc < 1 << 32, (length, pos, acc)
        if pos >= length:
            return (full, n) if n < N_OUT else None
        full += 1


# 觀測到的音效:連續混滿 k 次之後一次部分緩衝
SOUNDS: dict[tuple[int, int], collections.Counter] = collections.defaultdict(collections.Counter)
for nm, fl in S176["observed"]["fills"].items():
    k = 0
    for i, (_t, kind, span) in enumerate(fl):
        if kind == "full":
            k += 1
            assert fl[i + 1][1] in ("full", "partial"), (nm, i)
            continue
        if kind == "partial":
            SOUNDS[(k, m_of(TRUE_T[span]))][nm] += 1
        k = 0
assert all(m is not None and m % 2 == 1 for _k, m in SOUNDS), SOUNDS
# 每個部分緩衝都歸到一個音效:各份紀錄的音效數 = 續一百七十六數的部分緩衝數
assert all(sum(c[nm] for c in SOUNDS.values()) == row["kinds"]["partial"]
           for nm, row in S176["observed"]["per_log"].items()), SOUNDS

# 所有 .DAT 的頂層資源與巢狀子段
SEGTAB = []
for _p in sorted(GAME.glob("*.DAT")):
    _d = _p.read_bytes()
    try:
        _top = ud.parse_directory(_d)
    except ud.NotAContainer:
        continue
    for _i, (_o, _n) in enumerate(_top):
        _blob = _d[_o:_o + _n]
        SEGTAB.append((_p.name, _i, None, _blob))
        try:
            _sub = ud.parse_directory(_blob)
        except ud.NotAContainer:
            continue
        SEGTAB.extend((_p.name, _i, _j, _blob[_so:_so + _sn]) for _j, (_so, _sn) in enumerate(_sub))
_by_len = collections.defaultdict(list)
for row in SEGTAB:
    if row[3]:
        _by_len[len(row[3])].append(row)
_pred: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
_pred0: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
for _L in _by_len:
    _pred[play(_L)].append(_L)
    _pred0[play(_L, 0)].append(_L)
MATCH = {}
for key in SOUNDS:
    lens = _pred.get(key, [])
    assert len(lens) == 1, (key, lens)
    rows = _by_len[lens[0]]
    md5s = {hashlib.md5(r[3]).hexdigest() for r in rows}
    assert len(md5s) == 1, (key, [(r[0], r[1], r[2]) for r in rows])
    MATCH[key] = {"length": lens[0], "md5": md5s.pop(), "where": [[r[0], r[1], r[2]] for r in rows],
                  "near": sorted(x for x in _by_len if 0 < abs(x - lens[0]) <= 8)}
# 對照:累加器從 0 起算(每個來源樣本正好放兩次)時一個都對不到
CTRL0 = {key: _pred0.get(key, []) for key in SOUNDS}
assert not any(CTRL0.values()), CTRL0

_GT = {gp["mode"]: m_of(gp["mode"]) for gp in S176["observed"]["partial_groups"] if gp["mode_n"] >= 3}
_GT.update({w["true"]: w["m"] for w in WEAK})
TYPE = {t: next(MATCH[key] | {"k": key[0]} for key in MATCH if key[1] == m) for t, m in sorted(_GT.items())}
_fdo = "FDOTHER.DAT"
assert [r["where"] for r in TYPE.values()] and all(w[0] == _fdo for r in TYPE.values() for w in r["where"]), TYPE


def where(t: int) -> str:
    return " / ".join(f"#{w[1]} 第 {w[2]} 段" for w in TYPE[t]["where"])


CONC = {
    "word_order": f"回傳結構字序 = {' / '.join(OUT_REG[2 * k] for k in range(4))}(FD2.EXE 0x3f1ac .. 0x3f1d7 從 DPMI 呼叫結構 ebp-{RMCS_AT:#x} 抄回):"
                  f"[drv+4] = dx:ax、[drv+8] = cx:bx;SB16.DIG 功能 0x301 回 ax = {OFF4:#x}、bx = {OFF8:#x}、cx = dx = cs。"
                  f"{len(D_ROWS)} 份 DOSBox-X 呼叫紀錄(載入段 {' / '.join(f'{s:04x} × {n}' for s, n in sorted(SEGS.items()))})的 DIG 服務入口"
                  f"[drv+4] / [drv+8] 都是段 × 16 + {OFF4:#x} / {OFF8:#x};24 種字序有 {len(FIT)} 種對得上(cx / dx 互換,兩者都是 cs),"
                  f"靜態的 {STATIC_ORDER} 是其中之一。[drv+0x34] 由 0x40dd4 call 0x37910 入口的 eax 直接看到 = [drv+8] + {PLUS34}"
                  f"(段 {SEG_TOP:04x} 時 {(SEG_TOP << SEG_SHIFT) + OFF34:#x}),當時那個字 = {INIT_W[OFF34]:#06x}。",
    "ds_base": f"DS 基底 0:SB16.DIG 功能 0x300(派送 ds = cs)寫 "
               + "、".join(f"[{o:#x}] = {v if v == 'cs' else hex(v)}" for o, v in sorted(INIT_W.items()))
               + f";{len(D_ROWS)} 份紀錄裡遊戲以 DS:段 × 16 + 位移 讀到的,呼叫 0x300 之前只有檔案位元組與剛配置的 {FRESH:#06x},"
               f"之後每一筆都是這些值、[0xe] / [0x14] 等於自己的段。實模式寫在實體 段 × 16 + 位移,DS 讀同一個數字的位址就看到它。",
    "weak_groups": "兩群各 3 筆:" + ";".join(f"{w['values'][0]} .. {w['values'][-1]} 在雜訊窗內只有 {w['true']} 讓 m 為整數(m = {w['m']})"
                                          for w in WEAK) + "。",
    "sfx": f"混音器每次填緩衝把小數累加器設 {ACC0:#x}、步長 {RATE} × 65536 / {HW_RATE} = {STEP:#x},L 位元組的樣本放 k 次混滿加 m 個輸出"
           f"(一次放完時 m = 2L − 1)。五型各只對到一份波形:"
           + ";".join(f"{t} 型(k = {r['k']}、m = {m_of(t)})= {r['length']} 位元組,{_fdo} {where(t)}" for t, r in TYPE.items())
           + "。對照:累加器從 0 起算時一型都對不到。",
}
for _part, _key in (("[drv+4] = dx:ax、[drv+8] = cx:bx", "word_order"), ("有 2 種對得上", "word_order"), ("= 0xffff", "word_order"),
                    ("[0xe] = cs", "ds_base"), ("[0x504] = 0xffff", "ds_base"), ("段 137c 時 0x13cc4", "word_order"),
                    ("25264 .. 25273 在雜訊窗內只有 25273 讓 m 為整數(m = 181)", "weak_groups"),
                    ("27069 .. 27073 在雜訊窗內", "weak_groups"),
                    ("只有 27073 讓 m 為整數(m = 361)", "weak_groups"), ("31253 型(k = 0、m = 779)= 390 位元組,FDOTHER.DAT #31 第 9 段", "sfx"),
                    ("36793 型(k = 0、m = 1333)= 667 位元組,FDOTHER.DAT #31 第 2 段", "sfx"), ("30133 型(k = 6、m = 667)= 6478 位元組", "sfx"),
                    ("27073 型(k = 4、m = 361)= 4277 位元組,FDOTHER.DAT #77 第 1 段", "sfx")):
    assert _part in CONC[_key], (_part, CONC[_key])

OUTD = {
    "generator": rel(GEN_DIR / "ev_s178.py"),
    "exe_md5": MD5,
    "calllogs": {nm: {"path": rel(p), "md5": LOG_MD5[nm]} for nm, p in RAW.items()},
    "upstream": rel(EVIDENCE / "dig_fill_lengths_s176_20261031.json"),
    "word_order": {"rmcs_at": f"ebp-{RMCS_AT:#x}", "out_reg": {str(k): v for k, v in sorted(OUT_REG.items())}, "word_reg": WORD_REG,
                   "fn301_regs": REG301, "orders_fitting_logs": FIT, "static_order": STATIC_ORDER},
    "init_writes": {hex(k): v for k, v in sorted(INIT_W.items())},
    "logs": {nm: {"drv": hex(r["drv"]), "seg": f"{r['seg']:04x}", "drv4": hex(r["d4"]), "drv8": hex(r["d8"]), "drv10": r["d10"],
                  "drv14": r["d14"], "drv34": hex(r["d34"]), "drv34_word": hex(r["d34_word"]), "init_lines": r["init_lines"],
                  "before": {hex(o): {hex(w): n for w, n in sorted(c.items())} for o, c in sorted(r["before"].items())},
                  "after": {hex(o): {hex(w): n for w, n in sorted(c.items())} for o, c in sorted(r["after"].items())}}
             for nm, r in D_ROWS.items()},
    "weak_groups": WEAK,
    "mixer": {"acc0": hex(ACC0), "rate": RATE, "hw_rate": HW_RATE, "step": hex(STEP), "n_out": N_OUT},
    "sounds": [{"k": k, "m": m, "per_log": dict(c), **MATCH[(k, m)]} for (k, m), c in sorted(SOUNDS.items())],
    "segments_scanned": len(SEGTAB),
    "control_acc0_zero": {f"{k},{m}": v for (k, m), v in CTRL0.items()},
    "conclusion": CONC,
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, STATIC_ORDER, FIT, dict(SEGS), [(w["true"], w["m"]) for w in WEAK],
      {t: (r["length"], r["where"][0][1:]) for t, r in TYPE.items()})
