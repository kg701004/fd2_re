"""續一百三十六證據:evidence/move_range_highlight_scope_20261019.json。

續一百三十一「仍留的」:移動範圍的明暗(`draw_terrain_layer` 對地圖格 byte3 != 0xff 的格用換色表重畫)只量了第 1 章、
索爾一個單位;其他章節、敵方單位沒有量。這一份把能離線做的部分做完:
(A) 換色表:`[0x53a6d]` 在整個 EXE 只有一處寫入(main 0x25bf4 開頭 `0x111ba("FDOTHER.DAT", 舊值, 3)`,
    main 只由 C 執行期呼叫一次、那一段沒有迴圈),其餘 12 處都是讀;第 1 章(續一百三十一)與第 25 章(地圖 24,續七十三)
    兩份實機傾印的 `[0x53a6d]` 都是 0x1fd6c4,指到的內容與 FDOTHER_003 逐 byte 相同。`[0x51a93]` 只有兩處讀、初值 -1。
    所以換色表與換色條件跟章節無關。
(B) 敵方單位:寫 byte3 的三個入口(0x4e390 泛洪、0x4e4f6 路徑搜尋、0x14818 範圍收集)的每一個呼叫點,
    從呼叫返回處往後走函式內的控制流,到清除 0x4df4c 為止;AI 端 7 個函式的 14 個呼叫點在清除之前都走不到重畫
    (0x11cac / 0x11eee,遞移),玩家端有 7 個走得到(其中 0x1894d 就是續一百三十一實機看到明暗的那一條)。
    重畫兩個函式沒有任何 fixup 指到(沒有被取位址,不會經函式指標或中斷被呼叫)。玩家按 Enter 只有 `+6 == 2`
    才進 0x18890;其他陣營走 `unit_info_cards`(0x17aed),它的遞移呼叫裡沒有任何 byte3 寫入入口。
    所以敵方(與 NPC)單位的移動範圍不會以明暗顯示(靜態分析)。
全部從 FD2.EXE、extracted/raw/FDOTHER/FDOTHER_003.bin 與 .wsl_build 的兩份實機傾印重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import hashlib
import json
import struct
import sys

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import callgraph_le as cgm  # noqa: E402
import disasm_le as dl  # noqa: E402

EXE_P = GAME / "FD2.EXE"
FDOTHER3 = ROOT / "extracted/raw/FDOTHER/FDOTHER_003.bin"
S131 = ROOT / ".wsl_build/lc131a_moverange/D"          # 第 1 章(續一百三十一)
V12 = ROOT / ".wsl_build/ctr/v12/ch25"                 # 第 25 章 = 地圖 24(續七十三)
REGISTRY = ROOT / "docs/data/function_names.json"
OUT = out_path("move_range_highlight_scope_20261019.json")
HEAP_BASE, GLOBALS_BASE = 0x1E0000, 0x53A00            # 續七十三:geo1_heap.bin 的執行期起點、geo1_globals.bin 的靜態起點

REMAP_PTR, GATE_GLOBAL, MAP_PTR = 0x53A6D, 0x51A93, 0x53A51
CLEAR = 0x4DF4C                                        # 0x4df4c:全圖 byte3 = 0xff、旗標清掉
DRAWS = {0x11EEE}                                      # draw_terrain_layer(換色在這裡;redraw 0x11cac 經它,下面另驗)
NO_DRAW = {0x3702F}                                    # Watcom 堆疊檢查:xchg [esp+4], eax; call 0x37042;溢位才 jmp 0x3cee3 結束程式
BYTE3_ENTRIES = (0x4E390, 0x4E4F6, 0x14818)            # 寫 byte3 的三個入口(泛洪、路徑搜尋、範圍收集)
FAMILY = range(0x4E000, 0x4F000)                       # 泛洪家族內部互相呼叫,不算呼叫點
AI_FUNCS = {0x14121: "ai_move_toward_reachable_opponent", 0x14237: "ai_physical_candidate_select",
            0x14B78: "move_unit_toward_point", 0x15055: "ai_item_action", 0x15311: "ai_spell_execute",
            0x1567E: "ai_item_candidate_select", 0x1598A: "ai_spell_candidate_select"}
PLAYER_FUNCS = {0x18890: None, 0x18D8C: "player_action_ring", 0x1BBDC: "player_item_action", 0x1CFF0: "player_spell_select"}

_D = EXE_P.read_bytes()
EXE_MD5 = hashlib.md5(_D).hexdigest()
assert EXE_MD5 == "33464c81e6a364fd0660141139aa8e6e", EXE_MD5
META = dl.parse_le(_D)
CODE, BASE = dl.load_code(_D, META)
END = BASE + len(CODE)
MD = dl._capstone()
FX = cgm.fixup_map(_D, META)
_cache: dict[int, object] = {}


def insn(a: int):
    """位址 a 起的一個指令(capstone)。"""
    if a not in _cache:
        _cache[a] = next(MD.disasm(CODE[a - BASE:a - BASE + 15], a), None)
    return _cache[a]


def call_sites(target: int) -> list[int]:
    """全部 E8 rel32 直接呼叫點(之後再要求每一點都在可達反組譯的指令起點上)。"""
    return [BASE + i for i in range(len(CODE) - 5)
            if CODE[i] == 0xE8 and BASE + i + 5 + struct.unpack_from("<i", CODE, i + 1)[0] == target]


# ---------- 可達反組譯與函式入口(callgraph_le) ----------
G = cgm.CG(str(EXE_P))
SEEDS = sorted({v for v in FX.values() if BASE <= v < END} | set(cgm.DEFAULT_SEEDS))
G.build(SEEDS)
ENTRIES = sorted(set(G.calls.values()) | set(SEEDS))


def func_of(a: int) -> int:
    return ENTRIES[bisect.bisect_right(ENTRIES, a) - 1]


def covering(site: int):
    """從最近的函式入口線性解碼,回傳涵蓋 site(fixup 位置)的那個指令。"""
    a = func_of(site)
    while a <= site:
        i = insn(a)
        assert i is not None, hex(a)
        if a < site < a + i.size:
            return i
        a += i.size
    raise AssertionError(f"{site:#x} 沒有被指令涵蓋")


def walk(start: int, stop_at_clear: bool) -> dict:
    """函式內控制流走訪:不進 call;條件跳兩路都走;無條件跳跟隨;stop_at_clear 時 call 0x4df4c 那一路停止。"""
    seen: set[int] = set()
    todo = [start]
    targets: set[int] = set()
    indirect: set[int] = set()
    clears: set[int] = set()
    uncleared = False
    while todo:
        a = todo.pop()
        while a is not None and a not in seen and BASE <= a < END:
            seen.add(a)
            i = insn(a)
            if i is None:
                break
            m = i.mnemonic.split()[-1]
            nxt = a + i.size
            if m == "call":
                if i.op_str.startswith("0x"):
                    t = int(i.op_str, 16)
                    if t == CLEAR and stop_at_clear:
                        clears.add(a)
                        a = None
                        continue
                    targets.add(t)
                else:
                    indirect.add(a)
                a = nxt
            elif m == "jmp":
                if i.op_str.startswith("0x"):
                    a = int(i.op_str, 16)
                else:
                    indirect.add(a)
                    a = None
            elif m.startswith("j") or m.startswith("loop"):
                if i.op_str.startswith("0x"):
                    todo.append(int(i.op_str, 16))
                a = nxt
            elif m in ("ret", "retn", "retf", "iretd"):
                uncleared = True
                a = None
            else:
                a = nxt
    return {"targets": targets, "indirect": indirect, "clears": clears, "uncleared": uncleared}


_draws: dict[int, str] = {}


def draws(f: int, transitive: bool = True, stack: tuple = ()) -> str:
    """f 會不會(遞移)走到重畫:'yes' / 'no' / 'unknown'(間接呼叫或遞迴)。"""
    if f in DRAWS:
        return "yes"
    if f in NO_DRAW or not (BASE <= f < END):
        return "no"
    if not transitive:
        return "no"
    if f in _draws:
        return _draws[f]
    if f in stack:
        return "unknown"
    w = walk(f, False)
    res = "no"
    for t in sorted(w["targets"]):
        r = draws(t, True, stack + (f,))
        if r == "yes":
            res = "yes"
            break
        if r == "unknown":
            res = "unknown"
    if res == "no" and w["indirect"]:
        res = "unknown"
    _draws[f] = res
    return res


# ================= (A) 換色表與換色條件 =================
refs_remap = []
for s in sorted(x for x, v in FX.items() if v == REMAP_PTR and BASE <= x < END):
    i = covering(s)
    write = i.op_str.startswith("dword ptr [0x3a6d],")
    refs_remap.append({"at": hex(i.address), "func": hex(func_of(i.address)), "insn": f"{i.mnemonic} {i.op_str}", "write": write})
writes = [r for r in refs_remap if r["write"]]
assert len(refs_remap) == 13 and [r["at"] for r in writes] == ["0x25cc6"], refs_remap
assert all(r["insn"] in ("mov edx, dword ptr [0x3a6d]", "mov ebx, dword ptr [0x3a6d]", "mov eax, dword ptr [0x3a6d]",
                         "push dword ptr [0x3a6d]") for r in refs_remap if not r["write"]), refs_remap
# 唯一的寫入:main 開頭載入 FDOTHER.DAT 第 3 項(位元組逐一釘住)
LOAD = bytes(dl.object_bytes(_D, META, 0x25CB1, 0x1A)).hex()
assert LOAD == "6a03" "ff356d3a0000" "684d1a0000" "e8f7b4feff" "83c40c" "a36d3a0000", LOAD
assert bytes(dl.object_bytes(_D, META, 0x51A4D, 12)) == b"FDOTHER.DAT\x00"


def back_edges(e: int, site: int) -> list[list[str]]:
    """函式 e 裡從 site 之後跳回 [e, site] 的邊(有就表示 site 可能在迴圈裡重複執行)。"""
    back = []
    seen, todo = set(), [e]
    while todo:
        a = todo.pop()
        while a is not None and a not in seen and BASE <= a < END:
            seen.add(a)
            i = insn(a)
            m = i.mnemonic
            if (m == "jmp" or m.startswith("j") or m.startswith("loop")) and i.op_str.startswith("0x"):
                t = int(i.op_str, 16)
                if a > site and e <= t <= site:
                    back.append([hex(a), hex(t)])
                if m == "jmp":
                    a = t
                    continue
                todo.append(t)
                a = a + i.size
            elif m == "jmp" or m.startswith("ret"):
                a = None
            else:
                a = a + i.size
    assert site in seen, (hex(site), hex(e))
    return back


def once_chain(site: int) -> list[dict]:
    """往上走呼叫鏈:每一層的函式沒有從 site 之後跳回 [入口, site] 的邊,且只有一個直接呼叫點、沒有 fixup 指到;
    到沒有直接呼叫點、只被 fixup 指到的那一層(程式進入點)為止。"""
    chain = []
    while True:
        e = func_of(site)
        back = back_edges(e, site)
        cs = call_sites(e)
        fr = sorted(hex(s) for s, v in FX.items() if v == e)
        chain.append({"site": hex(site), "func": hex(e), "back_edges": back, "callers": [hex(c) for c in cs], "fixup_refs": fr})
        if len(cs) != 1 or fr or back:
            return chain
        site = cs[0]


chain = once_chain(0x25CC6)
assert [c["func"] for c in chain] == ["0x25bf4", "0x4609b", "0x3cd2a"], chain
assert all(not c["back_edges"] for c in chain) and chain[-1]["callers"] == [] and chain[-1]["fixup_refs"], chain
assert cgm.DEFAULT_SEEDS == [0x25BF4]
# 正對照:0x11943(呼叫 0x18890)在 do { } while (eax == 0) 迴圈裡,回跳偵測必須看得到 0x1194d -> 0x11942
LOOP_CONTROL = back_edges(func_of(0x11943), 0x11943)
assert func_of(0x11943) == 0x117E7 and ["0x1194d", "0x11942"] in LOOP_CONTROL, LOOP_CONTROL

refs_gate = []
for s in sorted(x for x, v in FX.items() if v == GATE_GLOBAL):
    i = covering(s)
    refs_gate.append({"at": hex(i.address), "insn": f"{i.mnemonic} {i.op_str}"})
assert refs_gate == [{"at": "0x12106", "insn": "cmp dword ptr [0x1a93], -1"},
                     {"at": "0x1215a", "insn": "mov eax, dword ptr [0x1a93]"}], refs_gate
gate_init = struct.unpack("<i", bytes(dl.object_bytes(_D, META, GATE_GLOBAL, 4)))[0]
assert gate_init == -1

# 實機:兩章的 [0x53a6d] 與它指到的內容
f3 = FDOTHER3.read_bytes()
assert len(f3) == 5990 and f3[:4] == b"LMI1" and struct.unpack_from("<H", f3, 4)[0] == 0x17
ch1_ptr = json.loads((S131 / "g.json").read_text(encoding="utf-8"))["remap_res"]
ch1_res = (S131 / "remap_res.bin").read_bytes()
gl = (V12 / "geo1_globals.bin").read_bytes()
ch25_ptr = struct.unpack_from("<I", gl, REMAP_PTR - GLOBALS_BASE)[0]
heap = (V12 / "geo1_heap.bin").read_bytes()
ch25_res = heap[ch25_ptr - HEAP_BASE:ch25_ptr - HEAP_BASE + len(f3)]
assert ch1_ptr == ch25_ptr == 0x1FD6C4, (hex(ch1_ptr), hex(ch25_ptr))
assert len(ch1_res) == 4096 and ch1_res == f3[:4096]
assert ch25_res == f3
# 換色表的位置由 FDOTHER_003 自己的目錄(+6 起每項一個 u32)算;draw_terrain_layer 用的階是三角表 0x51a97(20 項)的值
N_ENT = struct.unpack_from("<H", f3, 4)[0]
OFFS = [struct.unpack_from("<I", f3, 6 + 4 * i)[0] for i in range(N_ENT)]
# 目錄是 N + 1 個偏移,最後一個是檔長;第一項緊接在目錄之後,每項 256 bytes
assert struct.unpack_from("<I", f3, 6 + 4 * N_ENT)[0] == len(f3) and OFFS[0] == 6 + 4 * (N_ENT + 1)
assert all(OFFS[i + 1] - OFFS[i] == 0x100 for i in range(N_ENT - 1)) and OFFS[-1] + 0x100 == len(f3)
TRI = list(bytes(dl.object_bytes(_D, META, 0x51A97, 20)))
assert TRI == [min(i, 20 - i) for i in range(20)], TRI
LV_LAST_END = OFFS[max(TRI) + 1]                       # 最高階那一項的結尾 = 下一項的起點
# 第 1 章只傾印 4096 bytes:涵蓋畫明暗用到的 lv 0 .. 10,但沒涵蓋全部 23 項(第 25 章比了整份)
assert LV_LAST_END <= len(ch1_res) < OFFS[-1] + 0x100, (hex(LV_LAST_END), len(ch1_res))
# 對照:只比到 4095 byte、或把第 25 章的指標錯開 4 byte,都必須不相等(比較本身能說不)
assert heap[ch25_ptr - HEAP_BASE + 4:ch25_ptr - HEAP_BASE + 4 + len(f3)] != f3
assert ch1_res[:4096] != (f3[:4095] + bytes([f3[4095] ^ 1]))

A = {"remap_ptr_refs": refs_remap, "single_write_load_bytes": LOAD, "load_name_at_0x51a4d": "FDOTHER.DAT",
     "write_runs_once_chain": chain, "back_edge_control_0x11943": LOOP_CONTROL, "gate_0x51a93_refs": refs_gate, "gate_0x51a93_initial": gate_init,
     "fdother003": {"file": rel(FDOTHER3), "size": len(f3), "sha256": hashlib.sha256(f3).hexdigest(), "entries": N_ENT},
     "live": {"ch1_s131": {"remap_ptr": hex(ch1_ptr), "dump_bytes": len(ch1_res), "equals_fdother003_prefix": True,
                           "files": [rel(S131 / "g.json"), rel(S131 / "remap_res.bin")]},
              "ch25_map24_s73": {"remap_ptr": hex(ch25_ptr), "bytes_at_ptr": len(ch25_res), "equals_fdother003": True,
                                 "files": [rel(V12 / "geo1_globals.bin"), rel(V12 / "geo1_heap.bin")]}},
     "phase_levels_0x51a97": TRI, "table_offsets_lv0_10": [hex(OFFS[lv]) for lv in sorted(set(TRI))],
     "tables_lv0_10_end": hex(LV_LAST_END)}

# ================= (B) byte3 寫入點之後到清除之前會不會重畫 =================
names = {int(e["addr"], 16): e["name"] for e in json.loads(REGISTRY.read_text(encoding="utf-8"))["names"]}
for f, n in {**AI_FUNCS, **PLAYER_FUNCS}.items():
    assert n is None or names.get(f) == n, (hex(f), names.get(f), n)
reached = G.reached
sites = []
for tgt in BYTE3_ENTRIES:
    for s in call_sites(tgt):
        if s in FAMILY:
            continue
        assert s in reached, f"{s:#x} 不在可達反組譯的指令起點上"
        f = func_of(s)
        if f in BYTE3_ENTRIES:                         # 0x14818 自己裡面那一次 0x4e390 由 0x14818 的呼叫點涵蓋
            continue
        side = "ai" if f in AI_FUNCS else "player" if f in PLAYER_FUNCS else None
        assert side, f"{s:#x} 在未分類的函式 {f:#x}"
        w = walk(s + 5, True)
        d = sorted(hex(t) for t in w["targets"] if draws(t) != "no")
        raw = walk(s + 5, False)                       # 對照:不理會清除
        d_raw = sorted(hex(t) for t in raw["targets"] if draws(t) == "yes")
        d_direct = sorted(hex(t) for t in w["targets"] if t in DRAWS)  # 對照:不遞移
        sites.append({"entry": hex(tgt), "site": hex(s), "func": hex(f), "name": names.get(f), "side": side,
                      "clears": sorted(hex(c) for c in w["clears"]), "ret_uncleared": w["uncleared"],
                      "indirect": sorted(hex(x) for x in w["indirect"]), "draw_before_clear": d,
                      "rival_ignore_clear_draws": bool(d_raw), "rival_direct_only_draws": bool(d_direct)})
ai = [x for x in sites if x["side"] == "ai"]
assert {int(x["func"], 16) for x in sites} == set(AI_FUNCS) | set(PLAYER_FUNCS), sorted({x["func"] for x in sites})
# redraw 的位址取自 0x152a0 相位迴圈裡 redraw(1) 那一個 call(續一百二十五);它經 draw_terrain_layer(遞移)
_rc = insn(0x152A8)
assert _rc.mnemonic == "call" and _rc.size == 5, (_rc.mnemonic, _rc.op_str)
REDRAW = int(_rc.op_str, 16)
assert REDRAW in ENTRIES and draws(REDRAW) == "yes" and REDRAW not in DRAWS, hex(REDRAW)
pl = [x for x in sites if x["side"] == "player"]
assert len(sites) == 27 and len(ai) == 14 and len(pl) == 13, (len(sites), len(ai), len(pl))
assert all(not x["draw_before_clear"] and not x["ret_uncleared"] and not x["indirect"] and x["clears"] for x in ai), ai
PLAYER_DRAW = ["0x1894d", "0x18f6a", "0x1bd43", "0x1becf", "0x1d1c9", "0x1d2bf", "0x1d38e"]
assert sorted(x["site"] for x in pl if x["draw_before_clear"]) == PLAYER_DRAW, pl
assert all(x["draw_before_clear"] in (["0x115b6"], ["0x115b6", "0x18b84"]) for x in pl if x["draw_before_clear"]), pl
assert all(not x["ret_uncleared"] for x in pl)
# 正對照:0x1894d(選自己的單位)就是續一百三十一實機看到明暗的那一條
assert next(x for x in pl if x["site"] == "0x1894d")["draw_before_clear"]
# 對照:不理會清除時 AI 端有呼叫點走得到重畫(清除才是分界);只看直接呼叫時玩家端一個都找不到(必須遞移)
rival_ai_ignore_clear = sorted(x["site"] for x in ai if x["rival_ignore_clear_draws"])
assert len(rival_ai_ignore_clear) >= 1, rival_ai_ignore_clear
assert not any(x["rival_direct_only_draws"] for x in pl)

# 重畫沒有被取位址;fixup 表本身的健全度
fx_draw = {hex(t): sorted(hex(s) for s, v in FX.items() if v == t) for t in sorted(DRAWS | {REDRAW, CLEAR, *BYTE3_ENTRIES})}
assert all(not v for v in fx_draw.values()), fx_draw
dispatch = [FX.get(0x51B91 + 4 * i) for i in range(90)]          # 正對照:事件跳表 0x51b91 的 90 個槽
assert all(v is not None and BASE <= v < END for v in dispatch)
objs = META["objs"]


def obj_base(v: int):
    return next((o["base"] for o in objs if o["base"] <= v < o["base"] + o["vsize"]), None)


code_fx = [(s, v) for s, v in FX.items() if BASE <= s < END - 4]
fx_bad = [hex(s) for s, v in code_fx if obj_base(v) is None or struct.unpack_from("<I", CODE, s - BASE)[0] != v - obj_base(v)]
assert len(code_fx) == 7536 and not fx_bad, (len(code_fx), fx_bad[:5])

# 地圖指標當引數只傳給這幾個函式(push [0x53a51] 之後的第一個 call;0x4e8a5 那一次是 0x14818 內 0x4e390 的引數)
recv: dict[str, int] = {}
for s in sorted(x for x, v in FX.items() if v == MAP_PTR and BASE <= x < END):
    i = covering(s)
    if i.mnemonic != "push":
        continue
    a = i.address + i.size
    while insn(a).mnemonic != "call":
        a += insn(a).size
    k = insn(a).op_str
    recv[k] = recv.get(k, 0) + 1
assert recv == {"0x111ba": 3, "0x4df4c": 32, "0x4e4f6": 5, "0x4e390": 5, "0x4e8a5": 1, "0x3776e": 1}, recv

# 玩家按 Enter:+6 == 2 才進 0x18890,否則 unit_info_cards;0x18890 只有這一個呼叫點
GATE = bytes(dl.object_bytes(_D, META, 0x118EA, 4)).hex() + "|" + bytes(dl.object_bytes(_D, META, 0x11912, 0x36)).hex()
assert GATE == ("0fb65006|83fa02750ef640058075080fb6402685c0740b56e8c2610000" "83c404eb1f6a016a07ff35ec3e0000e857410100"
                "83c40c56e8486f0000"), GATE
assert call_sites(0x18890) == [0x11943] and names.get(0x17AED) == "unit_info_cards"
closure, todo = set(), [0x17AED]
while todo:
    f = todo.pop()
    if f in closure or not (BASE <= f < END):
        continue
    closure.add(f)
    todo += list(walk(f, False)["targets"])
writers_in_info = sorted(hex(x) for x in closure & {*BYTE3_ENTRIES, 0x146D1, 0x4E42C, 0x4E5CC, 0x18890})
assert writers_in_info == [] and REDRAW in closure, (writers_in_info, len(closure))

B = {"byte3_entries": [hex(x) for x in BYTE3_ENTRIES], "call_sites": sites,
     "ai_sites": len(ai), "player_sites": len(pl), "player_sites_drawing_before_clear": PLAYER_DRAW,
     "rival_ignore_clear_ai_sites_drawing": rival_ai_ignore_clear,
     "no_fixup_to": fx_draw, "dispatch_0x51b91_slots_with_code_fixup": len(dispatch),
     "code_fixups_checked": len(code_fx), "code_fixups_raw_mismatch": len(fx_bad),
     "map_ptr_push_receivers": recv, "enter_gate_bytes": GATE, "info_cards_closure_size": len(closure),
     "info_cards_closure_byte3_writers": writers_in_info}

ev = {"note": "FD2.EXE md5 " + EXE_MD5 + "。(A) 靜態(fixup 引用逐一解碼)+ 兩份實機記憶體傾印(DOSBox-X;第 1 章 續一百三十一、"
              "第 25 章 = 地圖 24 續七十三);(B) 靜態分析:函式內控制流走訪 + 遞移呼叫,沒有實機。"
              "範圍:只談 0x4e390 / 0x4e4f6 / 0x14818 寫的 byte3;重畫裡的 0x122dc 依 [0x51a83] 模式在游標周圍寫 byte3 = 0"
              "(模式 6 是道具 79 的亮帶,續一百二十三),不是泛洪範圍,不在本表。",
      "A_remap_table_chapter_independent": A, "B_enemy_ranges_never_drawn": B}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", "remap refs", len(refs_remap), "sites", len(sites), "ai", len(ai), "player draw", len(PLAYER_DRAW),
      "rival ai", len(rival_ai_ignore_clear), "closure", len(closure))
