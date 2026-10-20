"""續一百三十七證據:evidence/remaining_items_offline_20261020.json。

續一百三十六「仍留的」逐項找離線做得到的部分:
(A) lc131a 為什麼進城堡劇情:三份呼叫紀錄(lc131a / b / d)在光束迴圈之後都有同一段死亡演出(unit_death_sweep 0x1db65);
    b、d 之後沒有任何地形重畫,a 隔 216 個 BIOS tick 後建立新場景(0x10b4e)並走位 210 幀(0x13185)。
    0x13185 只有 walk_path 與新遊戲開場(戰前章節表第 0 格 0x3231b)兩個直接呼叫者;60 個章節劇情入口裡只有第 0 格走得到它。
    建立場景那幾幀的 ESP 比紀錄開頭(LOAD 進第 1 格)低 4,和由堆疊深度推出的「標題 → 新遊戲 → 0x3231b」相符;
    勝利路徑(戰後 0x22f37、之後的戰前第 2 格)會高 12 / 16。所以 lc131a 是勝負碼 1 → 資源 #79 → 標題 → 新遊戲的開場,不是過關。
(B) [0x51a93] 有沒有經指標被寫:目標落在 0x51a00 .. 0x51a97 的 fixup 全部分類;取位址的只有 6 個檔名字串(只交給 load_res,
    load_res 只把它交給 fopen 與錯誤訊息),沒有帶暫存器的寫入,資料區沒有指向這一段的指標。三份實機傾印都是 -1。
(C) 指令表第 1、2、5、7 格:索引是法術編號;FDFIELD 的 initial_command_mask(建構時複製到 +0x1a..+0x1d)
    有 24 / 35 / 46 / 14 個敵方單位會法術 1 / 2 / 5 / 7,不是死碼(入口仍沒有實機紀錄)。
(D) 防拷兩處無條件跳躍的形狀:都是 cmp 之後緊接 EB rel8、比較結果沒人讀、jmp 之後的指令沒有任何東西指到;
    全 EXE 可達指令裡同時符合這兩點的只有這兩處。把 EB 改回條件跳躍,孤立的程式碼就接回去。這是編譯後的位元組修補,誰改的仍判定不了。
(E) 地圖 25 的實機截圖(.wsl_build/ctr/terr/ch26/s1.png):捲動 (9, 39),視窗裡沒有圖塊 38。
(E2) 地形的模式 1 在畫面上:格子比對與「索引 → 顏色」表只用模式 0 / 2 的像素,模式 1 的像素由三種畫法各自預測。
    地圖 25(參考版 EXE)4 個長度 1 的 run、地圖 29(2026-08-30,EXE md5 沒有紀錄)16 個 run(含圖塊 167 的長度 2),
    全部只有「先跳過再寫」符合。
全部從 FD2.EXE、extracted/raw 的 FDFIELD / FDSHAP、.wsl_build 的呼叫紀錄、傾印與截圖重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import hashlib
import json
import struct
import sys

import numpy as np
from PIL import Image

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import callgraph_le as cgm  # noqa: E402
import disasm_le as dl  # noqa: E402
import parse_field as pf  # noqa: E402

EXE_P = GAME / "FD2.EXE"
LOGS = ROOT / ".wsl_build/lc131_runB_calllogs"
S131 = ROOT / ".wsl_build/lc131a_moverange"
RAW = ROOT / "extracted/raw"
SHOT25 = ROOT / ".wsl_build/ctr/terr/ch26/s1.png"     # 目錄名是顯示章節 = 章節 byte + 1,所以是地圖 25
REGISTRY = ROOT / "docs/data/function_names.json"
OUT = out_path("remaining_items_offline_20261020.json")
RELOC = 0x19C000                                      # 呼叫紀錄的 EIP = 靜態位址 + 0x19c000(續一百三十)

_D = EXE_P.read_bytes()
EXE_MD5 = hashlib.md5(_D).hexdigest()
assert EXE_MD5 == "33464c81e6a364fd0660141139aa8e6e", EXE_MD5
META = dl.parse_le(_D)
CODE, BASE = dl.load_code(_D, META)
END = BASE + len(CODE)
MD = dl._capstone()
FX = cgm.fixup_map(_D, META)
G = cgm.CG(str(EXE_P))
SEEDS = sorted({v for v in FX.values() if BASE <= v < END} | set(cgm.DEFAULT_SEEDS))
G.build(SEEDS)
ENTRIES = sorted(set(G.calls.values()) | set(SEEDS))
NAMES = {int(e["addr"], 16): e["name"] for e in json.loads(REGISTRY.read_text(encoding="utf-8"))["names"]}


def insn_in(code: bytes, a: int):
    return next(MD.disasm(code[a - BASE:a - BASE + 15], a), None)


_cache: dict[int, object] = {}


def insn(a: int):
    if a not in _cache:
        _cache[a] = insn_in(CODE, a)
    return _cache[a]


def func_of(a: int) -> int:
    return ENTRIES[bisect.bisect_right(ENTRIES, a) - 1]


def covering(site: int):
    a = func_of(site)
    while a <= site:
        i = insn(a)
        assert i is not None, hex(a)
        if a < site < a + i.size:
            return i
        a += i.size
    raise AssertionError(f"{site:#x} 沒有被指令涵蓋")


def e8_sites(target: int, code: bytes = CODE) -> list[int]:
    return [BASE + i for i in range(len(code) - 5)
            if code[i] == 0xE8 and BASE + i + 5 + struct.unpack_from("<i", code, i + 1)[0] == target]


def text(a: int, b: int) -> list[str]:
    """[a, b) 逐指令的「位址: 助記符 運算元」。"""
    out = []
    while a < b:
        i = insn(a)
        out.append(f"{a:#x}: {i.mnemonic} {i.op_str}".rstrip())
        a += i.size
    return out


# 直接呼叫的遞移閉包(間接呼叫不算)
callee: dict[int, set[int]] = {}
callers: dict[int, set[int]] = {}
for _s, _t in G.calls.items():
    callee.setdefault(func_of(_s), set()).add(_t)
    callers.setdefault(_t, set()).add(func_of(_s))


def reach(e: int) -> set[int]:
    seen, todo = set(), [e]
    while todo:
        f = todo.pop()
        if f not in seen:
            seen.add(f)
            todo.extend(callee.get(f, ()))
    return seen


def depths(entry: int, want) -> dict[int, int]:
    """函式入口之後壓入的 bytes(不含返回位址),沿兩路分支走;回傳 {符合 want 的 call 位址: 深度},深度不一致就 assert。"""
    seen: dict[int, int] = {}
    out: dict[int, int] = {}
    todo = [(entry, 0)]
    while todo:
        a, d = todo.pop()
        while True:
            if a in seen:
                assert seen[a] == d, (hex(entry), hex(a), seen[a], d)
                break
            seen[a] = d
            i = insn(a)
            m, op = i.mnemonic, i.op_str
            if m == "push":
                d += 2 if op.startswith("word") else 4
            elif m == "pop":
                d -= 4
            elif m == "sub" and op.startswith("esp, "):
                d += int(op.split(", ")[1], 16)
            elif m == "add" and op.startswith("esp, "):
                d -= int(op.split(", ")[1], 16)
            elif m == "call":
                if want(op):
                    out[a] = d
                if op == "0x3702f":                    # Watcom 堆疊檢查:push N; call 0x3702f,callee 以 ret 4 收掉 N
                    d -= 4
            if m.startswith("ret"):
                break
            if m == "jmp":
                if op.startswith("0x"):
                    a = int(op, 16)
                    continue
                break
            if m.startswith("j") and op.startswith("0x"):
                todo.append((int(op, 16), d))
            a += i.size
    return out


# ================= (A) lc131a 的城堡劇情 =================
# 勝負判定:戰場跳表 0x51b19 第 1 格 = 0x206c5;預設段 0x205be 寫 2,有活著的 +6 == 0 單位就寫 0,單位 0 的 +5 bit0 設了就寫 1;
# 第 1 格再查 5 .. 10,全部 bit0 設了也寫 1
assert FX[0x51B19 + 4] == 0x206C5 and FX[0x51B19] == 0x205B4
CHECK_DEFAULT = text(0x205BE, 0x205DA) + text(0x2067D, 0x206C5)
assert CHECK_DEFAULT == [
    "0x205be: push 8", "0x205c3: call 0x3702f", "0x205c8: push ebx", "0x205c9: mov dword ptr [0x3ecc], 2",
    "0x205d3: xor edx, edx", "0x205d5: jmp 0x2067e",
    "0x2067d: inc edx", "0x2067e: cmp edx, dword ptr [0x3beb]", "0x20684: jge 0x206ae", "0x20686: mov eax, edx",
    "0x20688: shl eax, 2", "0x2068b: add eax, edx", "0x2068d: shl eax, 4", "0x20690: mov ebx, dword ptr [0x3a45]",
    "0x20696: add eax, ebx", "0x20698: movzx ebx, byte ptr [eax + 6]", "0x2069c: test ebx, ebx", "0x2069e: jne 0x2067d",
    "0x206a0: test byte ptr [eax + 5], 1", "0x206a4: jne 0x2067d", "0x206a6: mov dword ptr [0x3ecc], ebx",
    "0x206ac: jmp 0x2067d", "0x206ae: mov eax, dword ptr [0x3a45]", "0x206b3: test byte ptr [eax + 5], 1",
    "0x206b7: je 0x206c3", "0x206b9: mov dword ptr [0x3ecc], 1", "0x206c3: pop ebx", "0x206c4: ret"], CHECK_DEFAULT
CHECK_1 = text(0x206C5, 0x20707)
assert CHECK_1[3:] == [
    "0x206d0: call 0x205be", "0x206d5: mov edx, 5", "0x206da: jmp 0x206dd", "0x206dc: inc edx", "0x206dd: cmp edx, 0xb",
    "0x206e0: jge 0x206fb", "0x206e2: mov eax, edx", "0x206e4: shl eax, 2", "0x206e7: lea ebx, [edx + eax]",
    "0x206ea: shl ebx, 4", "0x206ed: mov eax, dword ptr [0x3a45]", "0x206f2: test byte ptr [ebx + eax + 5], 1",
    "0x206f7: je 0x20705", "0x206f9: jmp 0x206dc", "0x206fb: mov dword ptr [0x3ecc], 1", "0x20705: pop ebx",
    "0x20706: ret"], CHECK_1
# main:碼 1 → 0x22e5c(資源 #79)→ esi = 1 → 0x25e74 → 不是 0 / -1 → edi(標題的回傳)為 0 → 回 0x25db1 → 再呼叫標題 0x25ebb
MAIN_1 = text(0x25DB1, 0x25E02) + text(0x25E74, 0x25E97)
assert MAIN_1 == [
    "0x25db1: push 0", "0x25db3: push 0x12", "0x25db5: call 0x25977", "0x25dba: add esp, 8", "0x25dbd: call 0x25ebb",
    "0x25dc2: mov edx, eax", "0x25dc4: mov edi, eax", "0x25dc6: test eax, eax", "0x25dc8: jne 0x25e88",
    "0x25dce: call 0x117e7", "0x25dd3: mov esi, eax", "0x25dd5: cmp dword ptr [0x3ecc], 1", "0x25ddc: jne 0x25e02",
    "0x25dde: mov byte ptr [0x1aac], 0", "0x25de5: call 0x22e5c", "0x25dea: mov byte ptr [0x1aac], 1",
    "0x25df1: mov dword ptr [0x3ecc], 0", "0x25dfb: mov esi, 1", "0x25e00: jmp 0x25e74",
    "0x25e74: test esi, esi", "0x25e76: je 0x25dce", "0x25e7c: cmp esi, -1", "0x25e7f: jne 0x25e8f",
    "0x25e81: mov edi, 1", "0x25e86: jmp 0x25e8f", "0x25e88: cmp eax, -1", "0x25e8b: jne 0x25e8f",
    "0x25e8d: xor edi, eax", "0x25e8f: test edi, edi", "0x25e91: je 0x25db1"], MAIN_1
# 碼 2:戰後表 [章節*4 + 0x51de9] → 0x26152 → 戰前表 [章節*4 + 0x51d71](0x25e23 / 0x25e3a)
assert text(0x25E1E, 0x25E3A)[1] == "0x25e23: call dword ptr [eax*4 + 0x1de9]"
assert insn(0x25E3A).op_str == "dword ptr [eax*4 + 0x1d71]" and insn(0x25F10).op_str == insn(0x260F5).op_str == insn(0x25E3A).op_str
OPEN = [FX[0x51D71 + 4 * k] for k in range(30)]
POST = [FX[0x51DE9 + 4 * k] for k in range(30)]
assert OPEN[0] == 0x3231B and OPEN[1] == 0x32D18 and OPEN[2] == 0x32E8C and POST[1] == 0x22F37

STEP, CTOR, DEATH, BEAM = 0x13185, 0x10B4E, 0x1DB65, 0x152A0
assert sorted(callers[STEP]) == [0x13488, 0x3231B] and NAMES.get(0x13488) == "walk_path"
assert NAMES.get(DEATH) == "unit_death_sweep" and NAMES.get(0x22E5C) == "show_result_resource_79"
reach_step = {f"open[{k}]": STEP in reach(e) for k, e in enumerate(OPEN)} | {f"post[{k}]": STEP in reach(e) for k, e in enumerate(POST)}
assert [k for k, v in reach_step.items() if v] == ["open[0]"], reach_step
reach_ctor = {k: CTOR in reach(e) for k, e in (("open[0]", OPEN[0]), ("open[1]", OPEN[1]), ("open[2]", OPEN[2]), ("post[1]", POST[1]))}
assert all(reach_ctor.values()), reach_ctor
# 標題序列、資源 #79、繼續遊戲(0x10010)都不會走到建立場景;資源 #79 與標題序列也不畫地形(紀錄上的空白)
assert not any(CTOR in reach(e) for e in (0x1F894, 0x22E5C, 0x10010))
assert not any(0x11CAC in reach(e) for e in (0x1F894, 0x22E5C))
assert STEP in reach(0x117E7)                          # 戰場迴圈經 walk_path 也會走位(所以要用 ESP 分)

# 堆疊深度:各劇情入口呼叫 0x10b4e 時、標題 / main 呼叫劇情入口時
IND_OPEN = "dword ptr [eax*4 + 0x1d71]"
IND_POST = "dword ptr [eax*4 + 0x1de9]"
d_ctor = {k: sorted(set(depths(e, lambda op: op == "0x10b4e").values()))
          for k, e in (("open[0]", OPEN[0]), ("open[1]", OPEN[1]), ("open[2]", OPEN[2]), ("post[1]", POST[1]))}
assert d_ctor == {"open[0]": [8], "open[1]": [4], "open[2]": [4], "post[1]": [8]}, d_ctor
d_title = depths(0x25EBB, lambda op: op == IND_OPEN)
assert d_title == {0x25F10: 12, 0x260F5: 12}, d_title       # 新遊戲(0x25f10)與讀檔(0x260f5)同一深度
d_main = depths(0x25BF4, lambda op: op in ("0x25ebb", IND_OPEN, IND_POST))
assert d_main == {0x25DBD: 12, 0x25E23: 12, 0x25E3A: 12}, d_main


def esp_at_ctor(chain: list[int]) -> int:
    """由 main 呼叫點起:每一層 -深度 -4(返回位址)。回傳相對值。"""
    return -sum(d + 4 for d in chain)


PRED = {"load_open1": esp_at_ctor([12, 12, 4]), "new_open0": esp_at_ctor([12, 12, 8]),
        "victory_post1": esp_at_ctor([12, 8]), "victory_open2": esp_at_ctor([12, 4])}
REL = {k: v - PRED["load_open1"] for k, v in PRED.items()}
assert REL == {"load_open1": 0, "new_open0": -4, "victory_post1": 12, "victory_open2": 16}, REL


def recs(name: str) -> list[list[str]]:
    return [ln.split() for ln in (LOGS / name).read_text(encoding="utf-8").splitlines() if ln.startswith("E ")]


def stack(p: list[str]) -> list[int]:
    s = next(x for x in p if x.startswith("s="))[2:]
    return [int(w, 16) for w in s.split(",")]


def caller_of(p: list[str]) -> int | None:
    """堆疊裡第一個落在程式碼裡的值(重畫 0x11cac 的直接呼叫者的返回位址)。"""
    for v in stack(p):
        if BASE <= v - RELOC < END:
            return v - RELOC
    return None


R = {n: recs(f"{n}.txt") for n in ("lc131a", "lc131b", "lc131d")}
LOG = {}
for n, rs in R.items():
    eip = [int(p[2], 16) - RELOC for p in rs]
    beam = [k for k, e in enumerate(eip) if e == BEAM]
    cal = [caller_of(p) for p in rs]
    death = [k for k, c in enumerate(cal) if c is not None and func_of(c) == DEATH]
    assert len(beam) == 8 and death, (n, len(beam), len(death))
    pre_death = [k for k in death if k < beam[0]]
    after = rs[death[-1] + 1:]
    LOG[n] = {"records": len(rs), "beam_rounds": len(beam), "death_frames": len(death),
              "death_returns": sorted({hex(cal[k]) for k in death}), "death_before_beam": len(pre_death),
              "death_after_last_beam": death[0] - beam[-1], "records_after_death": len(after)}
# 三份的死亡演出:都在最後一圈光束之後、幀數與返回位址相同;光束之前沒有
assert len({(v["death_frames"], tuple(v["death_returns"])) for v in LOG.values()}) == 1, LOG
assert all(v["death_before_beam"] == 0 for v in LOG.values()) and LOG["lc131a"]["death_frames"] == 33
assert [LOG[n]["records_after_death"] for n in R] == [457, 5, 5], LOG
assert [LOG[n]["death_after_last_beam"] for n in R] == [15, 16, 16], LOG    # 最後一圈光束之後十幾筆就開始
assert LOG["lc131a"]["death_returns"] == ["0x1dcd9", "0x1dd86"]
# b、d:之後只剩幾幀一般重畫,沒有建立場景也沒有走位
for n in ("lc131b", "lc131d"):
    tail = R[n][-LOG[n]["records_after_death"]:]
    assert LOG[n]["records_after_death"] <= 6 and all(func_of(caller_of(p)) == 0x11CAC for p in tail), n
# a:BIOS tick(0x12117 那一站的 EAX = [0x46c] 低 16 位)在死亡演出後跳 216,接著建立場景 3 幀、走位 210 幀
ra = R["lc131a"]
ka = len(ra) - LOG["lc131a"]["records_after_death"]
tick = [(k, int(p[6], 16) & 0xFFFF) for k, p in enumerate(ra) if int(p[2], 16) - RELOC == 0x12117]
assert insn(0x12114).op_str == "eax, word ptr [eax]" and insn(0x1210F).op_str == "eax, 0x46c"
gaps = [((t2 - t1) & 0xFFFF, k1, k2) for (k1, t1), (k2, t2) in zip(tick, tick[1:])]
big_after = [g for g in gaps if g[1] >= ka - 10 and g[0] > 20]
TICK_GAP = big_after[0][0]
assert len(big_after) == 1 and TICK_GAP == 216, big_after
k_ctor = [k for k in range(ka, len(ra)) if func_of(caller_of(ra[k])) == CTOR]
k_step = [k for k in range(ka, len(ra)) if func_of(caller_of(ra[k])) == STEP]
assert k_ctor == [big_after[0][2], big_after[0][2] + 1, big_after[0][2] + 2] and len(k_step) == 210 and min(k_step) > max(k_ctor)
esp = lambda p: int(p[4], 16)  # noqa: E731
ctor_start = [esp(ra[k]) for k in range(len(ra)) if k < 3]
assert [func_of(caller_of(ra[k])) for k in range(3)] == [CTOR] * 3
ctor_after = sorted({esp(ra[k]) for k in k_ctor})
assert ctor_start == [0x1F1610] * 3 and ctor_after == [0x1F160C], (ctor_start, ctor_after)
OBS = ctor_after[0] - ctor_start[0]
assert OBS == REL["new_open0"] and [k for k, v in REL.items() if v == OBS] == ["new_open0"], (OBS, REL)
# 走位:死亡之後的 210 幀 ESP 一致,比戰場內 walk_path 的走位淺 0xc4
step_in_battle = sorted({esp(p) for n in R for k, p in enumerate(R[n]) if k < (ka if n == "lc131a" else len(R[n]))
                         and caller_of(p) is not None and func_of(caller_of(p)) == STEP})
step_after = sorted({esp(ra[k]) for k in k_step})
assert step_in_battle == [0x1F1538] and step_after == [0x1F15FC], (step_in_battle, step_after)
# 第 1 章(章節 byte 1):單位 5 .. 10 是 +6 == 1 的 NPC,敵方 +6 == 0 有 10 個,D 那一幀都活著
ub = (S131 / "D/units.bin").read_bytes()
U = [ub[i * 80:(i + 1) * 80] for i in range(len(ub) // 80)]
NPC_D, ENEMY_D = [u[6] for u in U[5:11]], sum(u[6] == 0 for u in U)
assert NPC_D == [1] * 6 and ENEMY_D == 10 and all(u[5] & 1 == 0 for u in U) and len(U) == 21

A = {"result_check_table_0x51b19": {"slot0": "0x205b4", "slot1": "0x206c5"}, "check_default": CHECK_DEFAULT, "check_1": CHECK_1,
     "main_code1_to_title": MAIN_1, "calllogs": LOG, "calllog_files": [rel(LOGS / f"{n}.txt") for n in R],
     "lc131a_after_death": {"bios_tick_gap": TICK_GAP, "ctor_frames": len(k_ctor), "walk_frames": len(k_step),
                            "esp_ctor_log_start": hex(ctor_start[0]), "esp_ctor_after_death": hex(ctor_after[0]),
                            "esp_walk_in_battle": hex(step_in_battle[0]), "esp_walk_after_death": hex(step_after[0])},
     "step_0x13185_direct_callers": sorted(hex(c) for c in callers[STEP]),
     "story_entries_reaching_0x13185": [k for k, v in reach_step.items() if v],
     "ctor_call_depths": d_ctor, "title_depths": {hex(k): v for k, v in d_title.items()},
     "main_depths": {hex(k): v for k, v in d_main.items()},
     "esp_prediction_relative_to_load_open1": REL, "esp_observed_relative": OBS,
     "units_D": {"npc_5_10_camp": NPC_D, "enemies": ENEMY_D}}

# ================= (B) [0x51a93] 能不能經指標被寫 =================
GATE, LO, HI = 0x51A93, 0x51A00, 0x51A97 + 20
REGS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")


def classify(lo: int, hi: int) -> dict[str, list]:
    cls: dict[str, list] = {}
    for s in sorted(x for x, v in FX.items() if lo <= v < hi):
        v = FX[s]
        if not (BASE <= s < END):
            cls.setdefault("data_ptr", []).append([hex(s), hex(v)])
            continue
        i = covering(s)
        m, op = i.mnemonic, i.op_str
        shown = hex(v - next(o["base"] for o in META["objs"] if o["base"] <= v < o["base"] + o["vsize"]))
        inner = op[op.index("[") + 1:op.index("]")] if "[" in op else ""
        if m == "lea" or shown not in inner:          # fixup 在立即值(取位址),不是記憶體位移
            k = "addr_of" if m in ("push", "mov", "lea") else "other"
        else:
            dst = op.find("[") < op.find(",") if "," in op else True
            w = (dst and m not in ("cmp", "test", "push")) or m in ("inc", "dec")
            k = ("indexed_" if any(r in inner for r in REGS) else "direct_") + ("write" if w else "read")
        cls.setdefault(k, []).append([hex(v), hex(i.address), f"{m} {op}"])
    return cls


CB = classify(LO, HI)
CB_N = {k: len(v) for k, v in CB.items()}
assert CB_N == {"addr_of": 91, "direct_write": 163, "direct_read": 66, "indexed_read": 12}, CB_N
assert sorted({r[0] for r in CB["addr_of"]}) == ["0x51a43", "0x51a4d", "0x51a59", "0x51a65", "0x51a70", "0x51a79"]
GATE_REFS = [r for r in CB["direct_read"] if r[0] == hex(GATE)]
assert GATE_REFS == [["0x51a93", "0x12106", "cmp dword ptr [0x1a93], -1"],
                                                            ["0x51a93", "0x1215a", "mov eax, dword ptr [0x1a93]"]]
assert not [r for r in CB["direct_write"] if r[0] == hex(GATE)]
assert sorted({r[0] for r in CB["indexed_read"]}) == ["0x51a12", "0x51a2a", "0x51a97"]
# 取位址的 6 個都是 NUL 結尾的檔名,結尾都在 0x51a83 之前;每一處都是 load_res 的第 1 個引數(push 之後下一個指令前沒有別的 push)
STR = {}
for t in sorted({int(r[0], 16) for r in CB["addr_of"]}):
    b = bytes(dl.object_bytes(_D, META, t, 16))
    STR[hex(t)] = b[:b.index(0)].decode("ascii")
    assert t + b.index(0) < 0x51A83
assert list(STR.values()) == ["FDTXT.DAT", "FDOTHER.DAT", "FDFIELD.DAT", "FDSHAP.DAT", "DATO.DAT", "FDMUS.DAT"], STR
recv = {}
for r in CB["addr_of"]:
    a = int(r[1], 16)
    assert insn(a).mnemonic == "push", r
    a += insn(a).size
    while insn(a).mnemonic != "call":
        assert insn(a).mnemonic != "push", r
        a += insn(a).size
    recv[insn(a).op_str] = recv.get(insn(a).op_str, 0) + 1
assert recv == {"0x111ba": CB_N["addr_of"]}, recv
# load_res 裡第 1 個引數的堆疊槽只被讀兩次:交給 fopen(0x37324)與錯誤訊息(0x37119)
ARG1 = []
_seen: dict[int, int] = {}
_todo = [(0x111BA, 0)]
while _todo:
    a, d = _todo.pop()
    while a not in _seen:
        _seen[a] = d
        i = insn(a)
        m, op = i.mnemonic, i.op_str
        if "esp + " in op:
            k = int(op.split("esp + ")[1].split("]")[0], 16)
            if k - d == 4:
                ARG1.append(f"{a:#x}: {m} {op}")
        if m == "push":
            d += 4
        elif m == "pop":
            d -= 4
        elif m == "add" and op.startswith("esp, "):
            d -= int(op.split(", ")[1], 16)
        elif m == "call" and op == "0x3702f":
            d -= 4
        if m.startswith("ret") or (m == "jmp" and not op.startswith("0x")):
            break
        if m == "jmp":
            a = int(op, 16)
            continue
        if m.startswith("j") and op.startswith("0x"):
            _todo.append((int(op, 16), d))
        a += i.size
assert ARG1 == ["0x111dd: push dword ptr [esp + 0x14]", "0x111ef: push dword ptr [esp + 0x10]",
                "0x11262: push dword ptr [esp + 0x14]"], ARG1
ARG1_TO = []
for row in ARG1:
    a = int(row.split(":")[0], 16)
    while insn(a).mnemonic != "call":
        a += insn(a).size
    ARG1_TO.append(NAMES.get(int(insn(a).op_str, 16)))
assert ARG1_TO == ["fopen", "printf", "printf"], ARG1_TO         # 開檔、開檔失敗訊息、配置失敗訊息
# 0x51a00 以下最近被取位址的是 C 執行期的表(只讀)
lower = classify(0x51900, LO)
LOWER = sorted({r[0] for r in lower["addr_of"]})
assert LOWER == ["0x51944", "0x5195e", "0x519bc"], lower["addr_of"]
assert "indexed_write" not in lower and "data_ptr" not in lower
# 正對照:同一個分類器在 [0x53ecc] 找得到寫入
c53 = classify(0x53ECC, 0x53ED0)
assert len(c53["direct_write"]) == 32 and not c53.get("addr_of"), {k: len(v) for k, v in c53.items()}
live_gate = [json.loads((S131 / t / "g.json").read_text(encoding="utf-8"))["sel_51a93"] for t in "DEF"]
assert live_gate == [-1, -1, -1]
B = {"fixup_classes_0x51a00_0x51aab": CB_N, "gate_refs": GATE_REFS,
     "addr_of_strings": STR, "addr_of_receivers": recv, "load_res_arg1_uses": ARG1, "load_res_arg1_passed_to": ARG1_TO,
     "lower_addr_of": LOWER, "control_0x53ecc_direct_writes": len(c53["direct_write"]),
     "live_D_E_F": live_gate}

# ================= (C) 指令表第 1、2、5、7 格 =================
MAPS = [pf.parse_map(str(RAW), m) for m in range(33)]
SPELL = {s: {"enemy": 0, "ally": 0, "own": 0, "maps": set()} for s in range(10)}
for mp in MAPS:
    for u in mp["units"]:
        mask = int.from_bytes(bytes(u["initial_command_mask"]), "little")
        for s in range(10):
            if mask >> s & 1:
                SPELL[s][u["camp"]] += 1
                SPELL[s]["maps"].add(mp["map"])
SPELL = {s: {**v, "maps": sorted(v["maps"])} for s, v in SPELL.items()}
assert [SPELL[s]["enemy"] for s in (1, 2, 5, 7)] == [24, 35, 46, 14], SPELL
assert all(SPELL[s]["enemy"] > 0 for s in (0, 3, 4, 6))          # 正對照:有入口紀錄的第 0、3、4、6 格
assert SPELL[8]["enemy"] == 0 and SPELL[8]["ally"] == 1          # 第 8 格(續五十二)不是敵方的法術
assert [(v["enemy"], v["ally"], v["own"]) for v in SPELL.values()] == [
    (22, 0, 0), (24, 1, 0), (35, 0, 1), (4, 0, 0), (14, 1, 0), (46, 1, 0), (62, 0, 1), (14, 0, 0), (0, 1, 0), (10, 0, 0)], SPELL
C = {"spell_mask_counts_0_9": SPELL, "maps_parsed": len(MAPS)}

# ================= (D) 防拷兩處無條件跳躍 =================
PATCH = {0x118AA: ("803d443a000000" "eb07" "e8fe260200" "ebf0", 0x118A3, 0x75),
         0x34233: ("39d8" "ebe9" "c644243401" "ebe2", 0x34231, 0x74)}
for site, (hx, start, _orig) in PATCH.items():
    assert bytes(dl.object_bytes(_D, META, start, len(hx) // 2)).hex() == hx, hex(site)
assert e8_sites(0x33FAF) == [0x118AC] and not [s for s, v in FX.items() if v == 0x33FAF]
assert NAMES.get(0x33FAF) == "copy_protection_password_check"
FLAG_READERS = ("j", "set", "cmov", "adc", "sbb", "pushf", "lahf", "rcl", "rcr", "loop")


def shapes(code: bytes, extra: list[int]):
    ins = lambda a: insn(a) if code is CODE else insn_in(code, a)  # noqa: E731
    seen: set[int] = set()
    todo = [e for e in ENTRIES if BASE <= e < END] + extra
    while todo:
        a = todo.pop()
        while a is not None and BASE <= a < END and a not in seen:
            i = ins(a)
            if i is None:
                break
            seen.add(a)
            m = i.mnemonic
            if m == "jmp":
                a = int(i.op_str, 16) if i.op_str.startswith("0x") else None
                continue
            if m.startswith("ret"):
                break
            if (m.startswith("j") or m.startswith("loop") or m == "call") and i.op_str.startswith("0x"):
                todo.append(int(i.op_str, 16))      # 直接呼叫也跟進(反事實裡 0x33faf 由 0x118ac 接回來)
            a += i.size
    tg = set(G.calls.values()) | {v for v in FX.values() if BASE <= v < END}
    for a in seen:
        i = ins(a)
        if i.mnemonic.startswith("j") and i.op_str.startswith("0x"):
            tg.add(int(i.op_str, 16))
        if i.mnemonic == "call" and i.op_str.startswith("0x"):
            tg.add(int(i.op_str, 16))
    jcc = jmp = 0
    rows = []
    for a in sorted(seen):
        i = ins(a)
        if i.mnemonic not in ("cmp", "test") or a + i.size not in seen:
            continue
        j = ins(a + i.size)
        if j.mnemonic == "jmp" and j.op_str.startswith("0x"):
            jmp += 1
            t = ins(int(j.op_str, 16))
            dead = not t.mnemonic.startswith(FLAG_READERS)
            orphan = j.address + j.size not in tg
            rows.append({"jmp": hex(j.address), "bytes": j.bytes.hex(), "target_insn": t.mnemonic,
                         "flags": "dead" if dead else "read", "fallthrough": "orphan" if orphan else "referenced"})
        elif j.mnemonic.startswith("j"):
            jcc += 1
    return len(seen), jcc, jmp, rows


n_ins, n_jcc, n_jmp, ROWS = shapes(CODE, [0x33FAF])
both = [r["jmp"] for r in ROWS if r["flags"] == "dead" and r["fallthrough"] == "orphan"]
assert both == ["0x118aa", "0x34233"], ROWS
assert n_jmp == 10 and n_jcc == 4780 and n_ins == 71313, (n_ins, n_jcc, n_jmp)
assert sum(r["flags"] == "read" for r in ROWS) == 7                # 迴圈旋轉:跳到條件跳躍,比較結果在那裡被讀
assert [r["jmp"] for r in ROWS if r["flags"] == "dead" and r["fallthrough"] == "referenced"] == ["0x3e1fe"], ROWS
# 不加 0x33faf 當入口時,0x34233 根本走不到(防拷函式唯一的呼叫點在 0x118aa 跳過的那一行)
assert [r["jmp"] for r in shapes(CODE, [])[3] if r["flags"] == "dead" and r["fallthrough"] == "orphan"] == ["0x118aa"]
# 反事實:兩個 EB 改回條件跳躍(0x118aa → 75 jne,續一百二十一實機用的值;0x34233 → 74 je),孤立的位址消失、防拷函式接回去
pc = bytearray(CODE)
for site, (_hx, _s, orig) in PATCH.items():
    assert pc[site - BASE] == 0xEB
    pc[site - BASE] = orig
pc = bytes(pc)
_n2, _j2, _m2, rows2 = shapes(pc, [])
ORPH2 = [r for r in rows2 if r["fallthrough"] == "orphan"]
assert not ORPH2, rows2
assert _n2 == n_ins + 4 and _j2 == n_jcc + 2, (_n2, _j2)          # 接回 0x118ac / 0x118b1 / 0x34235 / 0x3423a;兩個比較又有條件跳躍讀
PB = {hex(k): v[0] for k, v in PATCH.items()}
assert all(bytes(dl.object_bytes(_D, META, PATCH[int(k, 16)][1], len(v) // 2)).hex() == v and v[2 * (int(k, 16) - PATCH[int(k, 16)][1]):][:2] == "eb"
           for k, v in PB.items()), PB
D = {"patch_bytes": PB, "copyprot_callers": ["0x118ac"],
     "reachable_insns_with_0x33faf": n_ins, "cmp_test_then_jcc": n_jcc, "cmp_test_then_jmp": n_jmp, "rows": ROWS,
     "dead_flags_and_orphan": both, "counterfactual_restored": {"reachable_insns": _n2, "cmp_test_then_jcc": _j2, "orphans": len(ORPH2)}}

# ================= (E) 地圖 25 的實機截圖 =================
CELL, VW, VH = 24, 13, 8
img = Image.open(SHOT25)
assert img.size == (1024, 768) and img.mode == "P"
arr = np.array(img.convert("RGB")).astype(np.int32)


def uniform2x(x0: int, y0: int) -> float:
    b = arr[y0:y0 + 400, x0:x0 + 640].reshape(200, 2, 320, 2, 3)
    return float((b == b[:, :1, :, :1]).all(axis=(1, 3, 4)).mean())


U2 = {f"{x},{y}": uniform2x(x, y) for x, y in ((192, 201), (192, 200), (193, 201))}
assert U2["192,201"] == 1.0 and max(U2["192,200"], U2["193,201"]) < 0.5, U2
blk = arr[201:601, 192:832].reshape(200, 2, 320, 2, 3)[:, 0, :, 0]
COL = (blk[..., 0] << 16) | (blk[..., 1] << 8) | blk[..., 2]


def shap_tiles(blob: bytes) -> list[np.ndarray]:
    w, h, n = struct.unpack_from("<HHH", blob, 0)
    assert (w, h) == (CELL, CELL)
    off = [struct.unpack_from("<I", blob, 6 + i * 4)[0] for i in range(n)] + [len(blob)]
    out = []
    for s in range(n):
        b = blob[off[s]:off[s + 1]]
        px = np.full(576, -1, np.int16)
        i = pos = 0
        while pos < 576 and i < len(b):
            c = b[i]
            i += 1
            m, k = c >> 6, (c & 63) + 1
            if m == 0:
                px[pos:pos + k] = b[i]
                i += 1
                pos += k
            elif m == 1:
                for j in range(k):
                    px[pos + 2 * j + 1] = b[i]
                i += 1
                pos += 2 * k
            elif m == 2:
                px[pos:pos + k] = list(b[i:i + k])
                i += k
                pos += k
            else:
                pos += k
        out.append(px)
    return out


TILES = shap_tiles((RAW / "FDSHAP/FDSHAP_050.bin").read_bytes())
fb = (RAW / "FDFIELD/FDFIELD_075.bin").read_bytes()
W25, H25 = struct.unpack_from("<HH", fb, 0)
IDX = [struct.unpack_from("<H", fb, 4 + 4 * k)[0] for k in range(W25 * H25)]
CELLS38 = [(k % W25, k // W25) for k, t in enumerate(IDX) if t == 38]
assert (W25, H25) == (31, 47) and len(CELLS38) == 7


def relabel(a: np.ndarray) -> bytes:
    _u, first = np.unique(a, return_index=True)
    order = {int(a[i]): r for r, i in enumerate(sorted(first))}
    return bytes(order[int(v)] for v in a)


TSIG = [(t >= 0, relabel(t[t >= 0])) if (t >= 0).sum() >= 400 else None for t in TILES]
_hit: dict = {}


def hit(t: int, cx: int, cy: int) -> bool:
    if TSIG[t] is None:
        return False
    if (t, cx, cy) not in _hit:
        scr = COL[4 + CELL * cy:4 + CELL * cy + CELL, 4 + CELL * cx:4 + CELL * cx + CELL].reshape(576)
        _hit[(t, cx, cy)] = relabel(scr[TSIG[t][0]]) == TSIG[t][1]
    return _hit[(t, cx, cy)]


SC = sorted(((sum(hit(IDX[(sy + cy) * W25 + sx + cx], cx, cy) for cy in range(VH) for cx in range(VW)), sx, sy)
             for sy in range(H25 - VH + 1) for sx in range(W25 - VW + 1)), reverse=True)
(best, SX, SY), second = SC[0], SC[1][0]
assert (best, SX, SY) == (55, 9, 39) and second == 26, SC[:3]
vis38 = [c for c in CELLS38 if SX <= c[0] < SX + VW and SY <= c[1] < SY + VH]
assert vis38 == []
E = {"screenshot": rel(SHOT25), "uniform_2x2": U2, "scroll": [SX, SY], "cells_consistent": best, "runner_up": second,
     "tile38_cells": CELLS38, "tile38_visible": vis38,
     "note": "地圖 25 視窗 13 × 8 格;這一幀看不到圖塊 38,長度 2 的模式 1 仍沒有畫面證據。"}


# (E2) 地形的模式 1 在畫面上:格子比對與「索引 → 顏色」表只用模式 0 / 2 的像素,模式 1 的像素再由三種畫法各自預測(不循環)
F25 = ROOT / ".wsl_build/ctr/terr/ch26/shots/campexit_009_dialogue04.png"    # 2026-10-01,harness 複本 md5 = 參考版
F29 = ROOT / ".wsl_build/round_ch30wf/shots/campexit_014_dialogue07.png"     # 2026-08-30,當時的 EXE 複本 md5 沒有紀錄(見 note)


def split_tiles(blob: bytes) -> list[tuple[np.ndarray, list[tuple[int, int, int]]]]:
    """每張圖塊:模式 0 / 2 的索引(其餘 -1)與模式 1 的 run (起點, k, 值)。"""
    w, h, n = struct.unpack_from("<HHH", blob, 0)
    assert (w, h) == (CELL, CELL)
    off = [struct.unpack_from("<I", blob, 6 + i * 4)[0] for i in range(n)] + [len(blob)]
    out = []
    for s in range(n):
        b = blob[off[s]:off[s + 1]]
        px = np.full(576, -1, np.int16)
        m1 = []
        i = pos = 0
        while pos < 576 and i < len(b):
            c = b[i]
            i += 1
            mm, k = c >> 6, (c & 63) + 1
            if mm == 0:
                px[pos:pos + k] = b[i]
                i += 1
                pos += k
            elif mm == 1:
                m1.append((pos, k, b[i]))
                i += 1
                pos += 2 * k
            elif mm == 2:
                px[pos:pos + k] = list(b[i:i + k])
                i += k
                pos += k
            else:
                pos += k
        out.append((px, m1))
    return out


def frame(path) -> np.ndarray:
    a = np.array(Image.open(path).convert("RGB")).astype(np.int64)
    b = a[201:601, 192:832].reshape(200, 2, 320, 2, 3)
    assert (b == b[:, :1, :, :1]).all(), path
    v = b[:, 0, :, 0]
    return (v[..., 0] << 16) | (v[..., 1] << 8) | v[..., 2]


def mode1_on_screen(path, m: int) -> dict:
    col = frame(path)
    tl = split_tiles((RAW / f"FDSHAP/FDSHAP_{2 * m:03d}.bin").read_bytes())
    fbm = (RAW / f"FDFIELD/FDFIELD_{3 * m:03d}.bin").read_bytes()
    w, h = struct.unpack_from("<HH", fbm, 0)
    idx = [struct.unpack_from("<H", fbm, 4 + 4 * k)[0] for k in range(w * h)]

    def cell(cx: int, cy: int) -> np.ndarray:
        return col[4 + CELL * cy:4 + CELL * cy + CELL, 4 + CELL * cx:4 + CELL * cx + CELL].reshape(576)

    def ok(t: int, scr: np.ndarray) -> bool:
        px = tl[t][0]
        mk = px >= 0
        if mk.sum() < 300:
            return False
        a, b = px[mk].astype(np.int64), scr[mk]
        return len(np.unique(a * (1 << 24) + b)) == len(np.unique(a)) == len(np.unique(b))

    def score(sx: int, sy: int) -> int:
        return sum(ok(idx[(sy + cy) * w + sx + cx], cell(cx, cy)) for cy in range(VH) for cx in range(VW))

    sc = sorted(((score(sx, sy), sx, sy) for sy in range(h - VH + 1) for sx in range(w - VW + 1)), reverse=True)
    (n_ok, sx, sy), runner = sc[0], sc[1][0]
    cmap: dict[int, set[int]] = {}
    good = []
    for cy in range(VH):
        for cx in range(VW):
            t = idx[(sy + cy) * w + sx + cx]
            scr = cell(cx, cy)
            if ok(t, scr):
                good.append((cx, cy, t))
                px = tl[t][0]
                for i in np.nonzero(px >= 0)[0]:
                    cmap.setdefault(int(px[i]), set()).add(int(scr[i]))
    conflicts = sum(len(v) > 1 for v in cmap.values())
    colors = [c for v in cmap.values() for c in v]
    reverse_conflicts = len(colors) - len(set(colors))
    orders = {"skip_then_value": [0, 0], "value_then_skip": [0, 0], "value_both": [0, 0]}
    runs = []
    for cx, cy, t in good:
        scr = cell(cx, cy)
        for p, k, val in tl[t][1]:
            if len(cmap.get(val, ())) != 1:
                continue
            c = next(iter(cmap[val]))
            wr = all(scr[p + 2 * j + 1] == c for j in range(k))
            sk = all(scr[p + 2 * j] == c for j in range(k))
            runs.append({"cell": [sx + cx, sy + cy], "tile": t, "pos": p, "k": k, "value": val, "write_ok": wr, "skip_is_value": sk})
            orders["skip_then_value"][0 if wr else 1] += 1
            orders["value_then_skip"][0 if sk else 1] += 1
            orders["value_both"][0 if wr and sk else 1] += 1
    return {"file": rel(path), "map": m, "scroll": [sx, sy], "cells_consistent": n_ok, "runner_up": runner,
            "indices": len(cmap), "conflicts": conflicts, "reverse_conflicts": reverse_conflicts,
            "runs": len(runs), "k_hist": {str(k): sum(r["k"] == k for r in runs) for k in sorted({r["k"] for r in runs})},
            "orders": orders, "long_runs": [r for r in runs if r["k"] > 1]}


M25 = mode1_on_screen(F25, 25)
assert (M25["scroll"], M25["cells_consistent"], M25["conflicts"], M25["reverse_conflicts"]) == ([9, 0], 45, 0, 0), M25
assert M25["runs"] == 4 and M25["k_hist"] == {"1": 4}, M25
assert M25["orders"] == {"skip_then_value": [4, 0], "value_then_skip": [0, 4], "value_both": [0, 4]}, M25["orders"]
M29 = mode1_on_screen(F29, 29)
assert (M29["scroll"], M29["cells_consistent"], M29["conflicts"], M29["reverse_conflicts"]) == ([16, 7], 89, 0, 0), M29
assert M29["runs"] == 16 and M29["k_hist"] == {"1": 15, "2": 1}, M29
assert M29["orders"] == {"skip_then_value": [16, 0], "value_then_skip": [0, 16], "value_both": [0, 16]}, M29["orders"]
assert [(r["cell"], r["tile"], r["k"]) for r in M29["long_runs"]] == [([23, 10], 167, 2)], M29["long_runs"]
assert all(x["runner_up"] * 2 < x["cells_consistent"] for x in (M25, M29))
assert (M25["runner_up"], M29["runner_up"]) == (19, 34), (M25["runner_up"], M29["runner_up"])
# 地圖 29 那一輪的 EXE 複本:doc58 記載同期 ~/fd2-run/FD2.EXE 與參考版只差成長表 252 bytes(檔案位移 502624 起)。
# 由 LE 頁面配置算:那一段在第 3 個物件(0x60000 起的資料),程式碼物件的檔案範圍不含它;四個繪製函式都在程式碼物件裡
PSZ, DOFF = META["page_size"], META["data_off"]
ranges, f0 = [], DOFF
for o in META["objs"]:
    ranges.append((f0, f0 + o["pages"] * PSZ, o["base"]))
    f0 += o["pages"] * PSZ
PATCH_OFF, PATCH_LEN = 502624, 252
obj_of_patch = [r[2] for r in ranges if r[0] <= PATCH_OFF and PATCH_OFF + PATCH_LEN <= r[1]]
assert obj_of_patch == [0x60000] and ranges[0][2] == BASE, (obj_of_patch, ranges)
blit_file = {hex(a): ranges[0][0] + (a - BASE) for a in (0x4E016, 0x4E0A2, 0x4E1A6, 0x4E22A)}
assert all(ranges[0][0] <= v < ranges[0][1] for v in blit_file.values())
assert all(int(k, 16) in NAMES for k in blit_file), blit_file
CODE_RANGE = [ranges[0][0], ranges[0][1]]
assert CODE_RANGE == [DOFF, DOFF + META["objs"][0]["pages"] * PSZ] == [221204, 479252], CODE_RANGE
E2 = {"map25_reference_exe": M25, "map29_supporting": M29,
      "map29_exe_note": "2026-08-30 那一輪的 FD2.EXE md5 沒有紀錄;doc58 記載同期的 ~/fd2-run/FD2.EXE 與參考版只差檔案位移 502624 起 252 bytes(成長表)",
      "patch_region_object": hex(obj_of_patch[0]), "code_object_file_range": CODE_RANGE,
      "blit_fn_file_offsets": blit_file}

ev = {"note": "FD2.EXE md5 " + EXE_MD5 + "。(A) 靜態分析 + DOSBox-X 呼叫紀錄(續一百三十一);(B)(D) 靜態分析;(C) 資產解析;"
              "(E) DOSBox-X 截圖(續六十五那一輪,原版)。lc131a 的「新遊戲」由 ESP 與呼叫者推得,標題畫面上是哪一個按鍵選的沒有紀錄。",
      "A_lc131a_castle_is_new_game_opening": A, "B_gate_0x51a93_never_written": B, "C_cmd_slots_1_2_5_7_have_casters": C,
      "D_copyprot_byte_patches": D, "E_map25_frame_without_tile38": E,
      "E2_terrain_mode1_on_screen": E2}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", "A obs", OBS, "B addr_of", len(CB["addr_of"]), "C", [SPELL[s]["enemy"] for s in (1, 2, 5, 7)],
      "D", both, "E", (SX, SY, best, second), "E2", M25["orders"]["skip_then_value"], M29["orders"]["skip_then_value"])
