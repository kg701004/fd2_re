"""續一百八十三證據:evidence/unit_name_key_s183_20261101.json(續一百八十二仍留:FDFIELD b1 的身分語意)。

使用者 2026-11-01「自動進行下一步」。沒有新實機:FD2.EXE 反組譯、FDFIELD / FDTXT 資源、續一百零七的 cl1 .. cl14 呼叫紀錄、
續一百八十二的證據(單位表基底與建構時刻)。
(A) 靜態:draw_unit_panel(0x18c6d)的記錄 = [0x53a45] + 第 3 個參數 × 0x50(esi),名字那一行是
    0x15f84([0x53a7d], byte [esi + 8] + 1, ...);[0x53a7d] = FDTXT 資源 0(fdtxt000_name_table 的 loader)。
    也就是說,單位面板顯示的名字 = FDTXT_000 第 +8 + 1 句,不分讀檔帶進來的角色或 FDFIELD 建構的單位。
(B) 每份紀錄:每一次 draw_unit_panel 之後那次 0x15f84(返回 0x18d84)的 s2,等於該單位記錄最近一次傾印的 +8 再加 1
    (單位表基底取該時刻有效的那一個,沿用續一百八十二的建構時刻);s1 傾印 = FDTXT_000 開頭。
    能對照的另外兩個獨立讀法:續一百八十二的每單位 +8(腳步音那條路)、FDFIELD 該筆記錄的 b1(建構單位 +8 = b1)。
(C) 全部 33 張圖的出場記錄:依同一規則列出 b1 + 1 那句字串是角色名 / 兵種名 / 空字串。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("unit_name_key_s183_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S178 = json.loads((EVIDENCE / "dig_word_order_sfx_s178_20261101.json").read_text(encoding="utf-8"))
S182 = json.loads((EVIDENCE / "step_unit_identity_s182_20261101.json").read_text(encoding="utf-8"))
CL = {nm: (ROOT / v["path"], v["md5"]) for nm, v in S178["calllogs"].items()}
NAMES = ROOT / "docs/data/function_names.json"
NAME_TABLE = ROOT / "docs/data/fdtxt000_name_table.json"
FLD_DIR = ROOT / "extracted/raw/FDFIELD"
FDTXT0 = ROOT / "extracted/raw/FDTXT/FDTXT_000.bin"
PANEL, DLG = 0x18C6D, 0x15F84
NAME_RET = 0x18D84                          # draw_unit_panel 裡畫名字那次 call 0x15f84 的下一條
PANEL_END = 0x18D8C                         # 0x18d87 jmp 0x1317d(5 位元組)之後;返回點落在這之內 = 直接子函式
ESI_SET = 0x18C96                           # add esi, eax(esi = 單位記錄);之前的 0x3702f 呼叫看到的是呼叫端的 esi
STRIDE = 0x50
UNIT_REGS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp")

assert hashlib.md5(_EXE).hexdigest() == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
assert _NM[PANEL] == "draw_unit_panel"
# function_names 的摘要記參數順序 (dst, stride, unit):單位索引是第 3 個
PANEL_PARAMS = next(r["summary"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]
                    if int(r["addr"], 16) == PANEL).partition("(")[2].partition(")")[0].split(", ")

# ================= (A) 靜態 =================
# 開頭 push ebx / esi / edi / ebp + sub esp, 0xc;[esp + 0x28] 是第幾個參數由框架大小算,不寫死
_PRO = [insn(a) for a in (0x18C77, 0x18C78, 0x18C79, 0x18C7A, 0x18C7B)]
assert _PRO == ["push ebx", "push esi", "push edi", "push ebp", "sub esp, 0xc"], _PRO
FRAME = 4 * 4 + 0xC
assert insn(0x18C82) == "mov edx, dword ptr [esp + 0x28]"
UNIT_ARG = (0x28 - FRAME) // 4 - 1                       # stack[] 的下標:[esp + 4] = s1 → 0
assert [insn(a) for a in (0x18C86, 0x18C88, 0x18C8B, 0x18C8D, 0x18C90, 0x18C96)] == [
    "mov eax, edx", "shl eax, 2", "add eax, edx", "shl eax, 4", "mov esi, dword ptr [0x3a45]", "add esi, eax"]
assert (1 << 2) + 1 << 4 == STRIDE
assert len(PANEL_PARAMS) == UNIT_ARG + 1 and PANEL_PARAMS[UNIT_ARG] == "unit", PANEL_PARAMS
NAME_INSNS = [insn(a) for a in (0x18D73, 0x18D77, 0x18D78, 0x18D79, 0x18D7F)]
assert NAME_INSNS == ["movzx eax, byte ptr [esi + 8]", "inc eax", "push eax", "push dword ptr [0x3a7d]",
                      f"call {DLG:#x}"], NAME_INSNS
# esi 設好之後到函式結尾沒有任何指令改 esi(子函式承接的就是單位記錄)
_BODY = list(_MD.disasm(_CODE[ESI_SET - _CBASE:PANEL_END - _CBASE], ESI_SET))
assert _BODY[-1].address == 0x18D87 and f"{_BODY[-1].mnemonic} {_BODY[-1].op_str}" == "jmp 0x1317d"
assert _BODY[-1].address + _BODY[-1].size == PANEL_END
assert [i.address for i in _BODY if i.op_str.startswith("esi") or (i.mnemonic == "pop" and i.op_str == "esi")] == [ESI_SET]
NAME_ADD = 1                                             # inc eax
NAME_FIELD = 8
# [0x53a7d] = FDTXT 資源 0(fdtxt000_name_table 的 loader 欄)
_NT = json.loads(NAME_TABLE.read_text(encoding="utf-8"))
assert "DAT_00053a7d" in _NT["_how_it_is_used"]["loader"] and "FDTXT" in _NT["_how_it_is_used"]["loader"]
FDTXT_HEAD = FDTXT0.read_bytes()[:32]
STRINGS = {}                                             # 字串索引 → (名稱, 類別)
for _k, _cat, _off in (("character_names_by_id", "角色名", 1), ("races_by_index", "69 .. 75 段", 0),
                       ("unit_types_by_index", "兵種名", 0)):
    for _i, _v in _NT[_k].items():
        assert int(_i) + _off not in STRINGS, (_k, _i)
        STRINGS[int(_i) + _off] = (_v, _cat)
EMPTY = set()                                            # 名稱表 layout 記為空的字串索引
for _k, _v in _NT["_layout_verified_programmatically"].items():
    if "empty" in _v.lower():
        _lo, _, _hi = _k.partition("..")
        EMPTY.update(range(int(_lo), int(_hi or _lo) + 1))
assert {33, 68, 76, 129, 140} <= EMPTY and not EMPTY & set(STRINGS)


def string_of(ix: int) -> tuple[str, str]:
    """FDTXT_000 第 ix 句的 (名稱, 類別);名稱表 layout 記為空的那幾段是空字串,其餘沒收的不猜。"""
    if ix in STRINGS:
        return STRINGS[ix]
    assert ix in EMPTY, ix
    return "", "空字串"


# ================= FDFIELD 出場記錄(與 ev_s182 同一讀法) =================
_FLD = sorted(FLD_DIR.glob("FDFIELD_*.bin"))
N_MAPS = 33
assert len(_FLD) == 3 * N_MAPS + 1, len(_FLD)
REC0 = 3 + 16 * 3 + 16 * 2 + 16 * 3
REC_LEN = 26
CTL = [_FLD[m * 3 + 1].read_bytes() for m in range(N_MAPS)]


def rec_b1(m: int, i: int) -> int:
    return CTL[m][REC0 + i * REC_LEN + 1]


# ================= (B) 每份紀錄 =================
# 每份紀錄的基底換表時刻:續一百八十二每個基底最早那次建構;沒有建構的(cl1)用它腳步那條路取的基底
_ROWS182 = collections.defaultdict(set)
for _r in S182["rows"]:
    _ROWS182[(_r["log"], int(_r["unit_base"], 16), _r["unit"])].add(_r["plus8"])
PAIRS = []
n_inner = collections.Counter()                          # +8 取自 draw_unit_panel 子函式傾印的次數
n_fallback = collections.Counter()                       # 子函式記滿、退回最近一次傾印的次數
for nm, (p, m5) in CL.items():
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, nm
    lg182 = S182["logs"][nm]
    first = {}
    for g in lg182["construction"]:
        b = int(g["unit_base"], 16)
        first[b] = min(first.get(b, g["seq"][0]), g["seq"][0])
    if not first:
        _bs = {int(b, 16) for b in lg182["unit_bases"]}
        assert len(_bs) == 1, nm
        first = {_bs.pop(): 0}
    order = sorted(first, key=first.get)
    starts = [first[b] for b in order]

    def base_at(seq: int, order: list[int] = order, starts: list[int] = starts) -> int:
        return order[max(0, bisect.bisect_right(starts, seq) - 1)]

    lg = cs._read(str(p), calls=True)
    last8 = {}                                           # 記錄位址 → (seq, 最近一次傾印的 +8)
    cur = None
    inner = []                                           # 這次 draw_unit_panel 裡直接呼叫的函式看到的 (esi, +8)
    got = collections.defaultdict(list)                  # (基底, 單位) → [(s2, 當時 +8)]
    for c in lg.calls:
        e = c.eip - DELTA
        if e == PANEL:
            cur = (c.seq, c.stack[UNIT_ARG])
            inner = []
        elif e == DLG and c.ret - DELTA == NAME_RET:
            assert cur is not None, (nm, c.seq)          # 每次畫名字前面都有一次 draw_unit_panel
            assert bytes(c.mem["s1"][:32]) == FDTXT_HEAD, (nm, c.seq)
            b = base_at(c.seq)
            rec = b + STRIDE * cur[1]
            # 子函式承接 draw_unit_panel 的 esi(0x18c96 之後不再改):每一個都必須正好指著這個單位的記錄,
            # 同時驗證靜態的 esi 算法與 base_at 選的基底;+8 優先用這些傾印,子函式記滿 200 次之後才退回最近一次傾印
            assert all(v == rec for v, _k in inner), (nm, c.seq, hex(rec), {hex(v) for v, _k in inner})
            if inner:
                k = inner[-1][1]
                n_inner[nm] += 1
            else:
                assert rec in last8, (nm, c.seq, cur)
                k = last8[rec][1]
                n_fallback[nm] += 1
            got[(b, cur[1])].append((c.stack[1], k))
            cur = None
        elif cur is not None and ESI_SET < c.ret - DELTA < PANEL_END and len(c.mem_prefix.get("esi", b"")) > NAME_FIELD:
            inner.append((c.regs["esi"], c.mem_prefix["esi"][NAME_FIELD]))
        for r in UNIT_REGS:
            v = c.regs[r]
            if len(c.mem_prefix.get(r, b"")) > NAME_FIELD:
                last8[v] = (c.seq, c.mem_prefix[r][NAME_FIELD])
    for (b, u), v in sorted(got.items()):
        s2s = collections.Counter(s for s, _k in v)
        assert all(s == k + NAME_ADD for s, k in v), (nm, hex(b), u, v)
        assert len(s2s) == 1, (nm, hex(b), u, s2s)
        s2 = next(iter(s2s))
        k8 = s2 - NAME_ADD
        # 獨立讀法 1:續一百八十二同一份紀錄、同一基底、同一單位的 +8(腳步那條路;沒有腳步音的單位沒有這列)
        r182 = _ROWS182.get((nm, b, u))
        if r182 is not None:
            assert r182 == {k8}, (nm, hex(b), u, r182, k8)
        # 獨立讀法 2:FDFIELD 建構的單位 +8 = 該筆記錄 b1(該基底建過哪張圖由續一百八十二定;同內容的記錄也算)
        src = [(g["map"], u - g["own_deploy"]) for g in lg182["construction"]
               if int(g["unit_base"], 16) == b and 0 <= u - g["own_deploy"] < CTL[g["map"]][2]]
        for m, i in src:
            assert rec_b1(m, i) == k8, (nm, hex(b), u, m, i, rec_b1(m, i), k8)
        nmx, cat = string_of(s2)
        assert nmx, (nm, u, s2)
        if u == 0:                                       # 單位 0 = 隊長索爾(doc58 存檔名冊 record0;續一百八十二)
            assert (k8, nmx) == (0, "索爾"), (nm, k8, nmx)
        PAIRS.append({"log": nm, "unit_base": hex(b), "unit": u, "panel_name_calls": len(v), "s2": s2, "plus8": k8,
                      "name": nmx, "string_kind": cat, "ev_s182_plus8": sorted(r182) if r182 else None,
                      "fdfield": [{"map": m, "record": i, "b1": rec_b1(m, i)} for m, i in src]})
N_CALLS = sum(x["panel_name_calls"] for x in PAIRS)
assert N_CALLS > 0 and sum(n_inner.values()) + sum(n_fallback.values()) == N_CALLS and sum(n_inner.values()) > N_CALLS // 2
FDFIELD_SHOWN = sorted({(f["map"], f["record"], f["b1"]) for x in PAIRS for f in x["fdfield"]})
assert FDFIELD_SHOWN and all(b1 >= 32 for _m, _i, b1 in FDFIELD_SHOWN)   # 建構單位畫出的名字落在兵種段
assert any(x["ev_s182_plus8"] for x in PAIRS) and any(x["ev_s182_plus8"] is None for x in PAIRS)
# 獨立對照:doc98 cl4 那列(續一百零八看畫面寫的)「索爾物理攻擊盜賊 #12」
_CL4 = next(ln for ln in (ROOT / "docs/knowledge-base/98-tooling-infrastructure.md").read_text(encoding="utf-8").splitlines()
            if ln.startswith("| cl4 |"))
assert "盜賊 #12" in _CL4
assert any(x["log"] == "cl4" and x["unit"] == 12 and x["name"] == "盜賊" for x in PAIRS)

# ================= (C) 全部出場記錄的 b1 + 1 =================
B1_TABLE = collections.defaultdict(list)                 # b1 → [(圖, 記錄)]
TRAILING = {}                                            # 圖 → 記數之後多出的整筆記錄數
for m in range(N_MAPS):
    # 控制段 byte 2 = 出場記錄筆數(parse_field.py 的 enemy_ally_total);每一筆都必須完整落在資源裡。
    # 資源大小 = 控制段 + 整數筆記錄,記數之後多出的整筆記錄另記(第 0 / 31 張各 1 筆、第 32 張 10 筆;不算出場)
    _q, _r = divmod(len(CTL[m]) - REC0, REC_LEN)
    assert _r == 0 and _q >= CTL[m][2], (m, CTL[m][2], len(CTL[m]))
    if _q > CTL[m][2]:
        TRAILING[m] = _q - CTL[m][2]
    for i in range(CTL[m][2]):
        B1_TABLE[rec_b1(m, i)].append((m, i))
assert TRAILING == {0: 1, 31: 1, 32: 10}, TRAILING
B1_ROWS = [{"b1": k, "string": k + NAME_ADD, "name": string_of(k + NAME_ADD)[0], "string_kind": string_of(k + NAME_ADD)[1],
            "records": len(v), "maps": sorted({m for m, _i in v})} for k, v in sorted(B1_TABLE.items())]
BLANK = [x for x in B1_ROWS if not x["name"]]
N_REC = sum(len(v) for v in B1_TABLE.values())
assert N_REC == sum(x["records"] for x in B1_ROWS)
assert any(x["b1"] == 48 and 32 in x["maps"] for x in BLANK) and any(x["b1"] == 66 and 32 in x["maps"] for x in BLANK)
KINDS = collections.Counter()
for x in B1_ROWS:
    KINDS[x["string_kind"]] += x["records"]

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s183.py"), "exe_md5": MD5,
    "draw_unit_panel_name": {"params": PANEL_PARAMS, "unit_param": PANEL_PARAMS[UNIT_ARG], "insns_0x18d73": NAME_INSNS, "field": NAME_FIELD, "add": NAME_ADD},
    "plus8_source": {"panel_callee_esi": dict(sorted(n_inner.items())), "latest_prior_dump": dict(sorted(n_fallback.items()))},
    "pairs": PAIRS, "fdfield_records_shown": [{"map": m, "record": i, "b1": b} for m, i, b in FDFIELD_SHOWN],
    "trailing_records_after_count": TRAILING,
    "b1_table": B1_ROWS, "b1_kinds_by_record": dict(sorted(KINDS.items())),
    "blank_name_b1": [{"b1": x["b1"], "records": x["records"], "maps": x["maps"]} for x in BLANK],
    "conclusion": f"draw_unit_panel 的名字 = FDTXT_000 第 [記錄 + 8] + 1 句(靜態);cl1 .. cl14 的 {N_CALLS} 次畫名字全部等於該單位 +8 + 1,"
                  f"與續一百八十二的 +8、FDFIELD b1 兩個獨立讀法都一致(LOG CONFIRMED)。所以 FDFIELD b1 經 +8 就是名字鍵:"
                  f"全部 {N_REC} 筆出場記錄依 b1 + 1 分成 {dict(sorted(KINDS.items()))};"
                  f"b1 + 1 落在空字串的有 {sum(x['records'] for x in BLANK)} 筆(含第 32 張圖的 48 / 66)。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, N_CALLS, len(PAIRS), N_REC, dict(KINDS))
for x in PAIRS:
    print({k: x[k] for k in ("log", "unit_base", "unit", "panel_name_calls", "s2", "name", "ev_s182_plus8", "fdfield")})
for x in BLANK:
    print("blank", x)
