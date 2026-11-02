"""續一百八十五證據:evidence/ai_chest_grab_0xc_s185_20261102.json(續一百八十四仍留:ai_mode_dispatch 那處 0xc)。

使用者 2026-11-02「先做第 1 項的靜態分析」。沒有實機:FD2.EXE 反組譯、函式登錄表、FDFIELD / FDSHAP。
(A) 0x13d13 那一次 0xc 只在 AI 模式 5(+0x34 低四位)的分支裡,前面的關卡依序是:ai_choose_action 回 0、
    [0x53ad5 + 事件號] 未開、find_event_cell 找到格子、移動後座標等於那一格;之後標記已開、放 0xc、+0x34 整個寫成 7。
(B) ai_mode_dispatch 的呼叫點只有友軍回合(+6 == 1)與敵方回合(+6 == 0)兩個函式:己方(+6 == 2)走不到。
(C) find_event_cell 的格子 = 地形 byte 0 & 0x60 == 0x20(不含 0x40 隱藏)且槽號 == 事件號(+0x3d = FDFIELD b2),y 外圈、x 內圈取第一格。
(D) 33 張圖每個 +0x34 低四位 == 5 的出場記錄:陣營、出場格、目標格、寶箱列;地圖 10 星之眼錨點、隱藏寶箱負對照。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import json
import re
import struct

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _MD, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import parse_field  # noqa: E402

OUT = out_path("ai_chest_grab_0xc_s185_20261102.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
NAMES = ROOT / "docs/data/function_names.json"
RAW = ROOT / "extracted/raw"
S181 = json.loads((EVIDENCE / "sfx_ui_semantics_s181_20261101.json").read_text(encoding="utf-8"))
PLAY_A, PLAY_B = 0x25A96, 0x25B45
POOL_PUSH = "push dword ptr [0x3eec]"
DISPATCH, FIND_CELL, CELL_INFO = 0x13A9F, 0x15DF3, 0x12E38
SITE_AI, SITE_CHEST = 0x13D13, 0x191A9
MODE_GRAB = 5
CHEST_MASK, CHEST_VISIBLE = 0x60, 0x20

assert S181["exe_md5"] == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_BY = {v: k for k, v in _NM.items()}
_ENT = sorted(_NM)
assert _NM[DISPATCH] == "ai_mode_dispatch" and _NM[FIND_CELL] == "find_event_cell" and _NM[CELL_INFO] == "map_cell_info"


def func_of(a: int) -> str:
    return _NM[_ENT[bisect.bisect_right(_ENT, a) - 1]]


def body(lo: int) -> list:
    """登錄入口到下一個登錄入口之間的指令。"""
    hi = _ENT[bisect.bisect_right(_ENT, lo)]
    return list(_MD.disasm(_CODE[lo - _CBASE:hi - _CBASE], lo))


def target(i) -> int | None:
    return int(i.op_str, 16) if i.mnemonic == "call" and re.fullmatch(r"0x[0-9a-f]+", i.op_str) else None


# ================= (A) 模式 5 分支的關卡(位址 -> 指令) =================
GATES = [
    (0x13AD4, "mov al, byte ptr [ebx + 0x34]", "+0x34"),
    (0x13AD7, "and al, 0xf", "低四位 = 模式"),
    (0x13AEB, "movzx ebp, byte ptr [ebx + 0x3d]", "事件號 = +0x3d"),
    (0x13C19, f"cmp eax, {MODE_GRAB}", "模式 5"),
    (0x13C1C, "jne 0x13d29", "不是 5 就跳過整段"),
    (0x13C24, "call 0x14ef0", "ai_choose_action"),
    (0x13C2E, "jne 0x13e5a", "有攻擊 / 法術動作就不搶"),
    (0x13C42, "mov eax, dword ptr [0x3ad5]", "已開旗標表"),
    (0x13C47, "movzx eax, byte ptr [eax + ebp]", ""),
    (0x13C4D, "jne 0x13b05", "已開 -> 模式 1 的備援"),
    (0x13C59, f"call {FIND_CELL:#x}", "find_event_cell(事件號, &格)"),
    (0x13C63, "jne 0x13b05", "找不到 -> 備援"),
    (0x13C77, "call 0x14b78", "move_unit_toward_point"),
    (0x13CA6, "cmp edx, eax", "移動後 x == 格 x"),
    (0x13CA8, "jne 0x13e5a", ""),
    (0x13CB7, "cmp eax, edi", "移動後 y == 格 y"),
    (0x13CB9, "jne 0x13e5a", ""),
    (0x13CCE, "movzx edx, byte ptr [eax + 0x53]", "寶箱列種類"),
    (0x13CF8, "call 0x1bb8c", "種類 0 -> unit_add_item"),
    (0x13D05, "mov byte ptr [eax + ebp], 1", "標記已開"),
    (0x13D0B, "push 0xc", "index 0xc"),
    (0x13D0D, POOL_PUSH, "UI 池"),
    (SITE_AI, f"call {PLAY_B:#x}", "handle B"),
    (0x13D20, "mov byte ptr [ebx + 0x34], 7", "之後整個 +0x34 = 7"),
    (0x13D29, "cmp eax, 7", "下一個模式"),
]
for a, want, _ in GATES:
    assert insn(a) == want, (hex(a), insn(a), want)
assert func_of(SITE_AI) == "ai_mode_dispatch" and func_of(0x13C19) == "ai_mode_dispatch"
# 0x13d13 夾在模式 5 分支內:分支從 0x13c22 起、到下一個模式的比較 0x13d29 止
assert 0x13C22 <= SITE_AI < 0x13D29

# ================= 全部登錄函式裡的 0xc 播放點、ai_mode_dispatch 的呼叫點 =================
PLAYS_0C, CALLERS = [], []
for lo in _ENT[:-1]:                           # 最後一個登錄入口沒有「下一個入口」當結尾
    if lo < _CBASE or lo >= _CBASE + len(_CODE):
        continue
    ins = body(lo)
    for k, i in enumerate(ins):
        t = target(i)
        if t in (PLAY_A, PLAY_B) and k >= 2 and f"{ins[k - 1].mnemonic} {ins[k - 1].op_str}" == POOL_PUSH \
                and ins[k - 2].mnemonic == "push" and re.fullmatch(r"0x[0-9a-f]+|[0-9]", ins[k - 2].op_str) \
                and int(ins[k - 2].op_str, 0) == 0xC:
            PLAYS_0C.append((i.address, _NM[lo], "A" if t == PLAY_A else "B"))
        if t == DISPATCH:
            CALLERS.append((i.address, _NM[lo]))
assert [(a, f) for a, f, _ in PLAYS_0C] == [(SITE_AI, "ai_mode_dispatch"), (SITE_CHEST, "field_cell_treasure_check")], PLAYS_0C
assert sorted(int(x["call"], 16) for x in S181["context"]["0xc"]) == [a for a, _, _ in PLAYS_0C]
# (B) 呼叫點與陣營條件(+6 讀進 edx)
CALLER_GATE = {0x1D876: (0x1D861, "cmp edx, 1"), 0x1D942: (0x1D906, "test edx, edx"),
               0x1D9D2: (0x1D9BE, "test edx, edx")}
assert CALLERS == [(0x1D876, "friendly_phase_dispatch"), (0x1D942, "enemy_phase_dispatch"),
                   (0x1D9D2, "enemy_phase_dispatch")], CALLERS


def camp_of(text: str) -> int:
    """陣營比較指令 -> 放行的 +6 值(`cmp edx, N` 放行 N;`test edx, edx` 放行 0)。"""
    return 0 if text == "test edx, edx" else int(re.fullmatch(r"cmp edx, (\d+)", text).group(1))


CALLER_CAMP = {}
for site, (g, want) in CALLER_GATE.items():
    assert insn(g) == want and insn(g - 4) == "movzx edx, byte ptr [eax + 6]", (hex(site), insn(g), insn(g - 4))
    CALLER_CAMP[site] = camp_of(insn(g))
DISPATCH_CAMPS = sorted(set(CALLER_CAMP.values()))
assert DISPATCH_CAMPS == [0, 1] and CALLER_CAMP[0x1D876] == 1

# ================= (C) find_event_cell / map_cell_info =================
CELL_CODE = [
    (0x15E1D, "cmp eax, dword ptr [0x3ac5]", "外圈 = 高"),
    (0x15E2A, "cmp ebx, dword ptr [0x3ac1]", "內圈 = 寬"),
    (0x15E3A, f"call {CELL_INFO:#x}", "map_cell_info(x, y, &out)"),
    (0x15E42, "movzx eax, word ptr [esp + 2]", "out+2 = 槽號"),
    (0x15E47, "mov dl, byte ptr [esp + 4]", "out+4 = 地形 byte 0"),
    (0x15E4B, f"and dl, {CHEST_MASK:#x}", ""),
    (0x15E4E, f"cmp dl, {CHEST_VISIBLE:#x}", "只有 0x20(不含 0x40 隱藏)"),
    (0x15E53, "cmp eax, esi", "槽號 == 事件號"),
    (0x15E57, "mov byte ptr [edi], bl", "第一格就寫回"),
    (0x12E4E, "imul eax, dword ptr [0x3ac1]", "y * 寬"),
    (0x12E59, "shl eax, 2", "每格 4 位元組"),
    (0x12E64, "add eax, 4", "跳過寬高"),
    (0x12E6A, "and bh, 3", "tile = word0 & 0x3ff"),
    (0x12E6D, "mov al, byte ptr [eax + 2]", ""),
    (0x12E70, "and al, 0x1f", "槽號 = byte 2 & 0x1f"),
    (0x12E80, "shl eax, 2", "地形表每列 4 位元組"),
    (0x12E86, "mov eax, dword ptr [0x3a69]", "地形表"),
]
for a, want, _ in CELL_CODE:
    assert insn(a) == want, (hex(a), insn(a), want)


def idx(p) -> int:
    return int(p.stem.split("_")[1])


FLD = sorted((RAW / "FDFIELD").glob("FDFIELD_*.bin"), key=idx)
SHP = sorted((RAW / "FDSHAP").glob("FDSHAP_*.bin"), key=idx)
assert [idx(p) for p in FLD[:99]] == list(range(99)) and [idx(p) for p in SHP[:66]] == list(range(66))


def cells(m: int) -> tuple[int, int, list]:
    """(寬, 高, [(x, y, tile, 槽號, 地形 byte0 & 0x60)]),依 find_event_cell 的掃描順序。"""
    comp, terr = FLD[m * 3].read_bytes(), SHP[m * 2 + 1].read_bytes()
    w, h = struct.unpack_from("<HH", comp, 0)
    assert len(comp) == 4 + w * h * 4 and len(terr) % 4 == 0, m
    out = []
    for y in range(h):
        for x in range(w):
            o = 4 + (y * w + x) * 4
            tile = struct.unpack_from("<H", comp, o)[0] & 0x3FF
            assert tile * 4 < len(terr), (m, x, y, tile)
            out.append((x, y, tile, comp[o + 2] & 0x1F, terr[tile * 4] & CHEST_MASK))
    return w, h, out


def find_event_cell(cl: list, ev: int) -> tuple[int, int] | None:
    return next(((x, y) for x, y, _, s, f in cl if f == CHEST_VISIBLE and s == ev), None)


# ================= 開場單位表的順序(續一百八十七補;原本 "unit" = 己方出場數 + 記錄序號,第 10 張圖差 1) =================
# 戰鬥初始化在己方之後呼叫 spawn_group(0);0x10b4e 依記錄序 0 .. [0x53be3) - 1 讀 [0x53a55] + 0x83 + k * 0x1a 的 +0x15
# (FDFIELD b21 = group),等於參數就 field_unit_construct(k);0x10c50 寫在單位表 [0x53a45] + [0x53beb] * 0x50(表尾)。
# 所以 group 0 的記錄 k = 單位「己方出場數 + k 在 group 0 記錄裡的名次」;其他 group 要等事件 spawn,單位號不能靜態定。
SPAWN_ORDER = [
    (0x10B3C, "push 0", "開場 spawn_group(0)"),
    (0x10B3E, "call 0x10b4e", ""),
    (0x10B5B, "mov edi, dword ptr [esp + 0x10]", "edi = group 參數"),
    (0x10BCC, "cmp ebx, dword ptr [0x3be3]", "記錄序 0 .. 記錄數 - 1"),
    (0x10BD4, "imul eax, ebx, 0x1a", "每筆 26 位元組"),
    (0x10BDF, "add eax, 0x83", "控制段單位陣列起點"),
    (0x10BE4, "movzx eax, byte ptr [eax + 0x15]", "b21 = group"),
    (0x10BE8, "cmp eax, edi", ""),
    (0x10BED, "push ebx", "參數 1 = 記錄序號"),
    (0x10BEE, "call 0x10c50", "field_unit_construct"),
    (0x10C69, "mov ebx, dword ptr [0x3beb]", "目前單位數"),
    (0x10C71, "shl eax, 2", ""),
    (0x10C74, "add eax, ebx", ""),
    (0x10C76, "shl eax, 4", "× 0x50"),
    (0x10C79, "mov ebx, dword ptr [0x3a45]", "單位表"),
]
for a, want, _ in SPAWN_ORDER:
    assert insn(a) == want, (hex(a), insn(a), want)
assert _NM[0x10C50] == "field_unit_construct"


# ================= (D) 33 張圖的模式 5 記錄 =================
ROWS, CAMP_RAW = [], collections.Counter()
for m in range(33):
    info = parse_field.parse_map(str(RAW), m)
    w, h, cl = cells(m)
    assert (w, h) == (info["w"], info["h"]), m
    chests = {c["slot"]: c for c in info["chests"]}
    pos = info["positions"]
    g0 = [k for k, u in enumerate(info["units"]) if u["group"] == 0]
    for k, u in enumerate(info["units"]):
        # 出場位置段第 k 筆的第 3 個值 = 記錄 b1(對齊的獨立檢查)
        assert pos[k][2] == u["raw_unit_key"], (m, k)
        if u["native_record_byte34"] & 0xF != MODE_GRAB:
            continue
        ev, b0 = u["native_record_byte3d"], u["native_record_byte6"]
        tgt = find_event_cell(cl, ev)
        assert tgt is not None and ev in chests, (m, k, ev)
        # 每個被引用的事件號只有一格可見寶箱:掃描順序(y 外圈、x 內圈)不影響選到哪一格
        assert sum(1 for _, _, _, s, f in cl if f == CHEST_VISIBLE and s == ev) == 1, (m, k, ev)
        sx, sy = pos[k][0], pos[k][1]
        CAMP_RAW[b0] += 1
        ROWS.append({"map": m, "record": k, "unit": info["own_deploy"] + g0.index(k) if u["group"] == 0 else None, "plus6": b0, "b1": u["raw_unit_key"],
                     "lv": u["lv"], "group": u["group"], "plus34": u["native_record_byte34"], "event_id": ev,
                     "spawn": [sx, sy], "target": list(tgt), "manhattan": abs(sx - tgt[0]) + abs(sy - tgt[1]),
                     "chest": {"native_type": chests[ev]["native_type"], "value": chests[ev]["value"]},
                     "reaches_dispatch": b0 in DISPATCH_CAMPS})
assert len(ROWS) == sum(CAMP_RAW.values())
REACH = [r for r in ROWS if r["reaches_dispatch"]]
SKIP = [r for r in ROWS if not r["reaches_dispatch"]]
BY_MAP = dict(sorted(collections.Counter(r["map"] for r in REACH).items()))
# 走不到的只有第 9 張圖那一筆己方(+6 == 2)
assert [(r["map"], r["plus6"]) for r in SKIP] == [(9, 2)], SKIP
assert BY_MAP == {10: 25, 12: 10, 15: 2, 18: 3}, BY_MAP
assert all(r["plus6"] == 0 and r["group"] == 0 for r in REACH)

# 錨點 1:地圖 10 星之眼 = (18,37)、tile 166、slot 0、寶箱列 00 D2 00(doc50 D2 那一行;doc25 §3.2 實機座標)
_w10, _h10, _c10 = cells(10)
_star = [c for c in _c10 if (c[0], c[1]) == (18, 37)][0]
_ch10 = {c["slot"]: c for c in parse_field.parse_map(str(RAW), 10)["chests"]}
assert _star == (18, 37, 166, 0, CHEST_VISIBLE) and (_ch10[0]["native_type"], _ch10[0]["value"]) == (0, 0xD2), _star
STAR_X, STAR_Y, STAR_TILE, STAR_SLOT, _ = _star
assert "D2 星之眼：map10 `(18,37)`，terrain166／chest slot0，control reward `00 D2 00`" in \
    (ROOT / "docs/knowledge-base/50-cutscene-script-system-design.md").read_text(encoding="utf-8")
# 負對照:地圖 10 的隱藏寶箱格(地形 & 0x60 == 0x40)只靠 & 0x60 就會被算進去,0x20 判準把它們排除
HIDDEN10 = sorted((s, x, y, f) for x, y, _, s, f in _c10 if f == 0x40)
assert HIDDEN10 == [(10, 16, 15, 0x40), (11, 33, 11, 0x40)], HIDDEN10
assert all(find_event_cell(_c10, s) is None for s, _, _, _ in HIDDEN10)
assert all(any(f & CHEST_MASK and sl == s for _, _, _, sl, f in _c10) for s, _, _, _ in HIDDEN10)

MAP10 = [r for r in REACH if r["map"] == 10]
NEAREST = min(MAP10, key=lambda r: (r["manhattan"], r["record"]))
assert (NEAREST["record"], NEAREST["manhattan"], NEAREST["target"]) == (25, 10, [24, 24])
assert sorted({r["event_id"] for r in MAP10}) == list(range(8))
# 第 10 張圖記錄 0 是 group 1(開場不建),所以盜賊記錄 k = 單位 己方出場數 + k - 1
_INFO10 = parse_field.parse_map(str(RAW), 10)
assert _INFO10["units"][0]["group"] == 1 and all(r["unit"] == _INFO10["own_deploy"] + r["record"] - 1 for r in MAP10)

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s185.py"), "exe_md5": MD5,
    "approval": "使用者 2026-11-02「先做第 1 項的靜態分析」;沒有實機",
    "upstream": {"ui_semantics": rel(EVIDENCE / "sfx_ui_semantics_s181_20261101.json"), "names": rel(NAMES)},
    "plays_0xc": [{"call": hex(a), "func": f, "handle": hd} for a, f, hd in PLAYS_0C],
    "mode5_gates": [{"addr": hex(a), "insn": s, "note": n} for a, s, n in GATES],
    "dispatch_callers": [{"call": hex(a), "func": f, "camp_check": insn(CALLER_GATE[a][0]), "plus6": CALLER_CAMP[a]}
                         for a, f in CALLERS],
    "find_event_cell": [{"addr": hex(a), "insn": s, "note": n} for a, s, n in CELL_CODE],
    "spawn_order": [{"addr": hex(a), "insn": s, "note": n} for a, s, n in SPAWN_ORDER],
    "unit_rule": "group 0 的記錄 k = 單位 己方出場數 + k 在 group 0 記錄裡的名次(開場 spawn_group(0) 依記錄序加到表尾);"
                 "非 group 0 為 null(續一百八十七更正;原本是己方出場數 + 記錄序號,第 10 張圖差 1,見續一百八十六)",
    "mode5_records": ROWS, "reaching_by_map": {str(k): v for k, v in BY_MAP.items()},
    "anchors": {"map10_star_eye": {"cell": [STAR_X, STAR_Y], "tile": STAR_TILE, "slot": STAR_SLOT,
                                   "chest": [_ch10[STAR_SLOT]["native_type"], _ch10[STAR_SLOT]["value"]]},
                "map10_hidden": [{"slot": s, "cell": [x, y], "flags": f, "find_event_cell": None} for s, x, y, f in HIDDEN10]},
    "map10_nearest": {"record": NEAREST["record"], "spawn": NEAREST["spawn"], "target": NEAREST["target"],
                      "manhattan": NEAREST["manhattan"]},
    "verification": "STATIC ANALYSIS(反組譯 + FDFIELD / FDSHAP);星之眼錨點來自 doc50",
    "conclusion": "ai_mode_dispatch 那處 0xc = AI 模式 5 的單位(友軍或敵方)走到 +0x3d 指定的可見寶箱格、開走寶箱之後;"
                  f"33 張圖走得到的模式 5 單位 {len(REACH)} 個:第 10 張圖 25、第 12 張圖 10、第 15 張圖 2、第 18 張圖 3,全是敵方、開場就出場。"
                  "第 10 張圖 8 個可見寶箱各有 3 / 4 個盜賊,最近的一個(記錄 25)離寶箱 10 格(曼哈頓)。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, BY_MAP, NEAREST["record"], NEAREST["manhattan"])
