"""續一百九十一證據(靜態):evidence/static_s191_open_items_20261104.json(91-worklist 6 個 open_static 的 EXE 層判準)。

使用者 2026-11-04「open_static 7 項、open_live 2 項 請完整進行驗證及處理」。沒有新實機,只讀原版 FD2.EXE 與遊戲資料檔
(FDFIELD.DAT / FDSHAP.DAT)與 lc191a 的單位表傾印。分析由 s191 子代理 A .. G 做(各自 facts / check 全過),這裡把每項
結論所依據的關鍵指令與可計算的表重新驗一次:
(A) 0x51b91 全域事件表 90 格:58 .. 89 = event_handler_58 .. 89;引用表的 code 只有 8 處(4 個 dispatcher);85 .. 89 空;
    每圖 selector:格子 59 / 60 / 61 / 62 / 65 / 69 / 75 / 80 / 84、回合列(含休眠)63 / 65 / 66 / 68 / 70 / 74 / 76 / 79 / 82、
    寶箱 58;event 82 的生產端 = map29 回合列 0(0xff, 82, camp 0),由 event 81 在 0x362e4 啟動。
(B) FD2.SAV:四槽 0x312b + 4 × 0xa28 = 0x59cb = 檔長,slot3 metadata +36 .. +39 = checksum dword(0x59c7);整個 code
    以絕對位移碰到四槽 metadata +10 .. +39 的只有 checksum 那幾處(另 1 處 0x180e6 是畫面座標);選槽 Delete 改寫成 Esc。
(C) 單位 0x50 record:+2 / +3 / +4 / +7 / +8 / +9 / +0x1a .. +0x1e / +0x3c 的關鍵讀寫指令;lc191a 63 筆單位值域檢查。
(D) 法術場景 phase handler 表 0x524c6(10 格)、池 [0x54153](32 處)、[0x5411f] / [0x54117] 0 處、法術 → FDOTHER 表 0x526d9;
    物理攻擊:命中幀未命中放 sub 0、命中放幀 +5,會心不進 sfx;池 = FDOTHER #48 .. #53(表 0x526e3),六池 sub 0 同一段。
(E) 0x2bce5 不是入口(0x2bb33 內的 jge);結局角色卡 0x31529(兩個呼叫端)、portrait 框 0x3200b;0x2fb2c 只由轉職 0x2abcc 呼叫。
(G) 選目標迴圈只有 redraw(0),確認不合法直接回讀鍵;指令環停用 = 格號 3 × 項目 + 2 × 可用 + 閃爍;範圍格只比 0xff。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import struct

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, _META, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import disasm_le as dl  # noqa: E402
import unpack_dat  # noqa: E402

OUT = out_path("static_s191_open_items_20261104.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
NAMES = ROOT / "docs/data/function_names.json"
assert hashlib.md5(_EXE).hexdigest() == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_FX = dl.build_fixups(_EXE, _META)
_CNT = collections.Counter(_FX.values())


def check(table: dict[int, str]) -> None:
    """每個位址的指令文字必須正好是表裡那一句。"""
    bad = {hex(a): (insn(a), t) for a, t in table.items() if insn(a) != t}
    assert not bad, bad


def calls_to(target: int) -> list[int]:
    """code 裡 E8 rel32 指到 target 的位置(位元組掃描,不依賴線性反組譯對齊)。"""
    out = []
    for i in range(len(_CODE) - 5):
        if _CODE[i] == 0xE8 and _CBASE + i + 5 + int.from_bytes(_CODE[i + 1:i + 5], "little", signed=True) == target:
            out.append(_CBASE + i)
    return out


# ================= (A) 全域事件表 =================
TABLE, N_EV = 0x51B91, 90
ENTRY = [_FX.get(TABLE + 4 * i) for i in range(N_EV)]
assert all(ENTRY[i] is not None and _NM.get(ENTRY[i]) == f"event_handler_{i}" for i in range(58, N_EV)), \
    [(i, hex(ENTRY[i] or 0), _NM.get(ENTRY[i] or 0)) for i in range(58, N_EV) if _NM.get(ENTRY[i] or 0) != f"event_handler_{i}"]
assert ENTRY[58] == 0x35854 and ENTRY[85] == 0x3642E and ENTRY[89] == 0x3644E
TABLE_SITES = sorted(a for a, t in _FX.items() if TABLE <= t < TABLE + 4 * N_EV and a < 0x50000)
assert [a - 3 for a in TABLE_SITES] == [0x1199C, 0x1712D, 0x19511, 0x1A85A, 0x1AC1A, 0x1D890, 0x1D95C, 0x1D9EC]
assert all(insn(a - 3) == "call dword ptr [eax*4 + 0x1b91]" for a in TABLE_SITES)
check({0x3642E: "push 4", 0x36433: "call 0x3702f", 0x36438: "ret ", 0x36439: "push 4", 0x36439 + 5: "jmp 0x36433", 0x36440: "push 4",
       0x36440 + 5: "jmp 0x36433", 0x36447: "push 4", 0x36447 + 5: "jmp 0x36433", 0x3644E: "push 4", 0x3644E + 5: "jmp 0x36433", 0x13A95: "mov dword ptr [0x1a8f], edx",
       0x362E4: "mov byte ptr [eax + 3], dl", 0x362C5: "push 4"})
assert ENTRY[81] == 0x362C5 and ENTRY[82] == 0x362E8
_fd = (GAME / "FDFIELD.DAT").read_bytes()
_sh = (GAME / "FDSHAP.DAT").read_bytes()
_dfd, _dsh = unpack_dat.parse_directory(_fd), unpack_dat.parse_directory(_sh)
N_MAPS = len(_dfd) // 3


def _res(data: bytes, d: list, i: int) -> bytes:
    o, n = d[i]
    return data[o:o + n]


PER_MAP = {}
for m in range(N_MAPS):
    comp, ctrl, terr = _res(_fd, _dfd, 3 * m), _res(_fd, _dfd, 3 * m + 1), _res(_sh, _dsh, 2 * m + 1)
    w, h = struct.unpack_from("<HH", comp, 0)
    used = collections.Counter()           # slot → 格數
    for c in range(w * h):
        tile, word = struct.unpack_from("<HH", comp, 4 + 4 * c)
        if word & 0x1F and terr[(tile & 0x3FF) * 4] & 0x60 == 0:
            used[(word & 0x1F) - 1] += 1
    field = sorted({ctrl[0x33 + 2 * s] for s in used if ctrl[0x33 + 2 * s] != 0xFF})
    turn = sorted({ctrl[3 + 3 * s + 1] for s in range(16) if ctrl[3 + 3 * s + 1] != 0xFF})
    treasure = sorted({struct.unpack_from("<H", ctrl, 0x54 + 3 * s)[0] for s in range(16)
                       if ctrl[0x53 + 3 * s] not in (0, 1)})
    rec = {"field": [x for x in field if x >= 58], "turn": [x for x in turn if x >= 58],
           "treasure": [x for x in treasure if x >= 58], "turn_row0": list(ctrl[3:6]),
           "field_cells": {str(ctrl[0x33 + 2 * s]): n for s, n in sorted(used.items()) if ctrl[0x33 + 2 * s] >= 58 and ctrl[0x33 + 2 * s] != 0xFF}}
    if rec["field"] or rec["turn"] or rec["treasure"]:
        PER_MAP[m] = rec
FIELD_IDS = sorted({x for r in PER_MAP.values() for x in r["field"]})
TURN_IDS = sorted({x for r in PER_MAP.values() for x in r["turn"]})
TREASURE_IDS = sorted({x for r in PER_MAP.values() for x in r["treasure"]})
assert FIELD_IDS == [59, 60, 61, 62, 65, 69, 75, 80, 84], FIELD_IDS
assert TURN_IDS == [63, 65, 66, 68, 70, 74, 76, 79, 82], TURN_IDS
assert TREASURE_IDS == [58] and PER_MAP[25]["treasure"] == [58], (TREASURE_IDS, PER_MAP.get(25))
# map26 event 62 = y = 39 整列 31 格((15,47) 也是 slot 1,但地形 0x20 走寶箱路徑,不算)
assert PER_MAP[26]["field_cells"]["62"] == 31, PER_MAP[26]
assert PER_MAP[29]["turn_row0"] == [0xFF, 82, 0] and sorted(PER_MAP) == [25, 26, 27, 28, 29], sorted(PER_MAP)
assert not set(range(85, 90)) & (set(FIELD_IDS) | set(TURN_IDS) | set(TREASURE_IDS))

# ================= (B) FD2.SAV =================
SLOT0, SLOT_SIZE, META, FILE_LEN, CHECKSUM = 0x312B, 0xA28, 0x28, 0x59CB, 0x59C7
META_OFF = 0xA00                            # 每槽:roster 0xa00 在前,metadata 0x28 在 +0xa00
assert SLOT0 + 4 * SLOT_SIZE == FILE_LEN and FILE_LEN - 4 == CHECKSUM
assert SLOT0 + 3 * SLOT_SIZE + META_OFF + 36 == CHECKSUM   # slot3 metadata +36 .. +39 就是 checksum
assert META_OFF + META == SLOT_SIZE
check({0x297B6: "mov dword ptr [esi + 0x59c7], eax", 0x1A102: "mov dword ptr [esi + 0x59c7], eax",
       0x100B5: "cmp eax, dword ptr [ebp + 0x59c7]", 0x1FDEC: "cmp eax, dword ptr [esi + 0x59c7]",
       0x4DF16: "sub ecx, 4", 0x29791: "mov byte ptr [ebx + 9], al", 0x29D0A: "mov byte ptr [0x3a8e], 1",
       0x296F3: "push 0xff", 0x296F9: "call 0x37910", 0x19FCD: "mov byte ptr [ebx + 0x3b2b], 0xff"})
META_TAIL = {SLOT0 + i * SLOT_SIZE + META_OFF + off for i in range(4) for off in range(10, META)}
_DISP = re.compile(r"\+ (0x[0-9a-f]+)\]")
HITS = collections.defaultdict(list)
pos = 0
while pos < len(_CODE):                                    # 線性掃全部 obj1;解不出的位元組跳 1
    i = next(_MD.disasm(_CODE[pos:pos + 16], _CBASE + pos, 1), None)
    if i is None:
        pos += 1
        continue
    for d in _DISP.findall(i.op_str):
        if int(d, 16) in META_TAIL:
            HITS[int(d, 16)].append(i.address)
    pos += i.size
META_HITS = {hex(k): [hex(a) for a in v] for k, v in sorted(HITS.items()) if k in META_TAIL}
# 正對照:checksum 的 4 個讀寫站(上面逐條驗過)必須被同一掃描找到;另 1 處是畫面緩衝位移
# (0x455d = 55 × 320 + 157,前一條 push 0x140 是畫面寬),不是存檔 buffer
assert META_HITS == {"0x455d": ["0x180e6"], "0x59c7": ["0x100b5", "0x1a102", "0x1fdec", "0x297b6"]}, META_HITS
assert insn(0x180E6) == "lea eax, [edi + 0x455d]" and insn(0x180E1) == "push 0x140" and insn(0x180ED) == "call 0x187d6"
assert 0x455D == SLOT0 + SLOT_SIZE + META_OFF + 10 == 55 * 320 + 157

# ================= (C) 單位 record =================
check({0x18D73: "movzx eax, byte ptr [esi + 8]", 0x1291E: "imul edi, edi, 0xc", 0x12893: "mov ecx, 0x720",
       0x1289F: "mov ecx, 0xfffffffc", 0x128AB: "mov ecx, 0xfffff8e0", 0x128B2: "mov ecx, 4", 0x128E2: "imul ebx, ecx",
       0x10A92: "movzx eax, byte ptr [ebx + 7]", 0x10F02: "mov byte ptr [edx + 9], 0", 0x11349: "mov byte ptr [esi + 9], 0",
       0x1C29E: "cmp dword ptr [esp], 5", 0x10F7F: "push 4", 0x10F99: "mov byte ptr [eax + 0x1e], 0",
       0x1A97F: "cmp edi, 6", 0x1B69C: "push 3", 0x1E309: "movzx eax, byte ptr [esi + 0x3c]",
       0x10FDD: "mov byte ptr [edx + 0x3c], 0xff"})
_U = (ROOT / ".wsl_build/lc191_live/cl/lc191a/s00_units.bin").read_bytes()
N_UNITS = 63
assert hashlib.md5(_U).hexdigest() == "5d85c303b762f5315a6d84b1081e0c13" and len(_U) >= N_UNITS * 0x50


def u16(r: bytes, o: int) -> int:
    return int.from_bytes(r[o:o + 2], "little")


def violations(hp: int, mhp: int, mp: int, mmp: int, p9: int = 9, px: int = 0, py: int = 1) -> int:
    """63 筆單位記錄(含 +5 bit0 不在場的)違反值域的筆數(偏移是參數,對照用)。"""
    bad = 0
    for k in range(N_UNITS):
        r = _U[k * 0x50:(k + 1) * 0x50]
        bad += not (r[px] < 31 and r[py] < 57 and r[3] <= 3 and r[6] <= 2 and r[p9] == 0 and
                    u16(r, hp) <= u16(r, mhp) and u16(r, mp) <= u16(r, mmp))
    return bad


V_OK = violations(0x40, 0x42, 0x44, 0x46)
# 對照:x / y 對調(第 26 張圖 31 × 57)、+9 改讀 +8。HP / MaxHP 對調不能當對照:開戰時全員滿血,對調照樣全過
V_NULL = {"xy_swapped": violations(0x40, 0x42, 0x44, 0x46, px=1, py=0), "p9_is_p8": violations(0x40, 0x42, 0x44, 0x46, p9=8)}
V_DEGENERATE = violations(0x42, 0x40, 0x44, 0x46)
assert V_OK == 0 and all(v > 0 for v in V_NULL.values()), (V_OK, V_NULL)

# ================= (D) 法術場景音效 =================
check({0x30451: "mov eax, ebp", 0x30469: "call dword ptr [eax*4 + 0x24c6]", 0x30284: "mov dword ptr [0x4153], eax",
       0x2D99A: "mov dword ptr [0x4153], eax", 0x2E68E: "mov dword ptr [0x414b], eax", 0x2E69F: "mov dword ptr [0x414f], eax",
       0x1C7FE: "cmp edx, dword ptr [esp + 0x70]", 0x1D414: "cmp eax, 9", 0x153DE: "cmp dword ptr [0x3c2f], 0xa"})
assert _FX[0x30469 + 3] == 0x524C6
SPELL_HANDLERS = [_FX[0x524C6 + 4 * i] for i in range(10)]
assert SPELL_HANDLERS == [0x2B996, 0x2BB33, 0x2BD6C, 0x2BFD9, 0x2C217, 0x2C441, 0x2C67D, 0x2CAFC, 0x2CCF4, 0x2CE1A]
SPELL_POOL = list(dl.object_bytes(_EXE, _META, 0x526D9, 10))
assert SPELL_POOL == [82, 82, 83, 84, 85, 86, 87, 88, 89, 90]
POOL_REFS = {hex(t): _CNT[t] for t in (0x5411F, 0x54117, 0x54153, 0x5414B, 0x5414F)}
assert POOL_REFS == {"0x5411f": 0, "0x54117": 0, "0x54153": 32, "0x5414b": 16, "0x5414f": 5}, POOL_REFS
# 物理攻擊(scene_attack_sequence 0x2ebe1 的主幀迴圈,子代理 I):命中幀(幀標頭 +4 ≠ 0)命中放 +5、未命中放 sub 0;一般幀放 +5;
# 命中旗標 = 結果[0](0x2f7d3 預設 1 未命中,0x2f9ac 命中清 0);會心 = 結果[4](0x2f9da),只在 0x2f16e 接到閃白,不進 sfx idx
check({0x2EFC1: "cmp dword ptr [esp + 0x18], 0", 0x2EFDD: "movzx eax, byte ptr [ebx + 5]", 0x2EFEC: "push 0",
       0x2EFF8: "movzx eax, byte ptr [ebx + 5]", 0x2EFFD: "push dword ptr [esp + 0xc4]", 0x2F004: "call 0x25a96",
       0x2ED0C: "call 0x2f7b6", 0x2F7D3: "mov dword ptr [esi], 1", 0x2F9AC: "mov dword ptr [esi], 0",
       0x2F9DA: "mov dword ptr [esi + 4], 1", 0x2F16E: "cmp dword ptr [esp + 0x1c], 0",
       0x31507: "movzx eax, byte ptr [eax + 4]", 0x3150B: "movzx eax, byte ptr [esp + eax - 1]",
       0x25AEB: "add edx, dword ptr [eax + 6]", 0x2E6C2: "push dword ptr [0x414b]", 0x2E708: "push dword ptr [0x414f]"})
ATTACK_POOLS = list(dl.object_bytes(_EXE, _META, 0x526E3, 6))
assert ATTACK_POOLS == [48, 49, 50, 51, 52, 53], ATTACK_POOLS
_fo = (GAME / "FDOTHER.DAT").read_bytes()
_dfo = unpack_dat.parse_directory(_fo)
SUB0 = {}
for r in ATTACK_POOLS:                                 # play_sfx:子樣本 = 容器 + dword[容器 + 6 + idx × 4](0x25aeb)
    c = _res(_fo, _dfo, r)
    a0, a1 = struct.unpack_from("<II", c, 6)
    assert c[:6] == b"LLLLLL" and 6 < a0 < a1 <= len(c), (r, a0, a1)   # 前提:巢狀容器、範圍非空(空字串 md5 會讓下一行恆真)
    SUB0[r] = hashlib.md5(c[a0:a1]).hexdigest()
assert len(set(SUB0.values())) == 1, SUB0             # 六個池的 sub 0(揮空音)是同一段
SUB1 = {}
for r in ATTACK_POOLS:                                 # 對照:sub 1 各池不同
    c = _res(_fo, _dfo, r)
    a1, a2 = struct.unpack_from("<II", c, 10)
    SUB1[r] = hashlib.md5(c[a1:a2]).hexdigest()
assert len(set(SUB1.values())) == len(ATTACK_POOLS), SUB1

# ================= (E) 結局 renderer =================
check({0x2BCE5: "jge 0x2bd27", 0x31529: "push 0x80", 0x315C3: "call 0x111ba", 0x3167B: "push 0x7d0",
       0x31688: "cmp dword ptr [0x3c03], 0x1a", 0x3200B: "call 0x168b6", 0x3205F: "call 0x4ebff", 0x321CD: "call 0x11eb0"})
CALLERS = {hex(t): [hex(a) for a in calls_to(t)] for t in (0x2BCE5, 0x31529, 0x2FB2C, 0x2AA00)}
assert CALLERS == {"0x2bce5": [], "0x31529": ["0x2545d", "0x25970"], "0x2fb2c": ["0x2abcc"], "0x2aa00": ["0x29f48"]}, CALLERS
assert SPELL_HANDLERS[1] < 0x2BCE5 < SPELL_HANDLERS[2]     # 0x2bce5 落在法術 1 的 phase handler 裡
N_LOAD_RES = len(calls_to(0x111BA))
assert N_LOAD_RES == 132, N_LOAD_RES

# ================= (G) 選目標 / 指令環 =================
check({0x117A9: "call 0x12dac", 0x12DD4: "call 0x11cac", 0x11CE8: "call 0x11eee", 0x11CF0: "call 0x122dc",
       0x11CF5: "call 0x127a9", 0x11D0A: "call 0x1acf3", 0x1173F: "cmp ebx, 0xff", 0x1175F: "call 0x14742",
       0x11709: "je 0x117a9", 0x11719: "cmp edi, 5", 0x17A85: "add eax, dword ptr [0x3c13]", 0x1783A: "cmp dword ptr [ebx], 0",
       0x121FE: "cmp edx, 0xff", 0x12945: "test byte ptr [esp], 0x80", 0x1CFD7: "mov eax, 0xcd", 0x1CFE6: "mov eax, 0xc9",
       0x1D6A4: "cmp esi, eax", 0x18DE5: "mov dword ptr [eax], 1", 0x18EA0: "mov dword ptr [eax + 4], 1",
       0x18EB9: "movzx eax, byte ptr [esi + 0x27]", 0x18E83: "mov dword ptr [eax + 8], 1"})
assert _NM.get(0x115B6) == "target_cursor_loop" and calls_to(0x12DAC) and 0x117A9 in calls_to(0x12DAC)

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s191b.py"), "exe_md5": MD5,
    "A_event_dispatch": {"handlers_58_89": {str(i): hex(ENTRY[i]) for i in range(58, N_EV)},
                         "table_call_sites": [hex(a - 3) for a in TABLE_SITES],
                         "per_map_ids_ge_58": {str(k): v for k, v in sorted(PER_MAP.items())},
                         "field_ids": FIELD_IDS, "turn_ids": TURN_IDS, "treasure_ids": TREASURE_IDS,
                         "empty_handlers": [85, 86, 87, 88, 89]},
    "B_save": {"slot_end": hex(SLOT0 + 4 * SLOT_SIZE), "checksum": hex(CHECKSUM), "meta_tail_abs_hits": META_HITS,
               "delete_key_becomes_esc": "0x29d0a mov byte ptr [0x3a8e], 1"},
    "C_unit_record": {"live_units_checked": N_UNITS, "violations": V_OK, "null_violations": V_NULL,
                      "hp_mhp_swapped_violations_degenerate": V_DEGENERATE},
    "D_spell_sfx": {"phase_handlers": [hex(a) for a in SPELL_HANDLERS], "spell_pool_fdother": SPELL_POOL, "pool_fixups": POOL_REFS,
                    "attack_pools_fdother": ATTACK_POOLS, "attack_pool_sub0_md5": SUB0[48], "attack_pool_sub1_distinct": len(set(SUB1.values()))},
    "E_ending": {"callers": CALLERS, "load_res_calls": N_LOAD_RES},
    "G_target_ui": {"redraw_only_in_target_loop": True},
    "conclusion": "六個 open_static 的關鍵指令與可計算表在原版 FD2.EXE 上全部成立;詳細推論見 doc98 續一百九十一。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, FIELD_IDS, TURN_IDS, TREASURE_IDS, META_HITS, V_OK, V_NULL, CALLERS)
