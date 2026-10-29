"""續一百六十一證據:evidence/timer_base_and_delay_slowdown_s161_20261028.json(續一百六十留下的 ③a 與 ①,只做靜態與既有紀錄)。

③a:續一百五十八量到 BIOS tick 落在 5.000 ms 格點 —— 這個 5 ms 是哪個計時通道設的。
①:續一百六十的標題閃爍裡,delay 每秒只跑約 7658 圈 int 21h,開機校準卻是 9057 —— 慢在哪裡。
(A) AIL 計時通道:誰登錄、各用多少頻率、PIT 取哪一個;中斷處理程式的重入路徑。全部讀 FD2.EXE 的指令。
(B) 校準在 AIL 之前:0x3dfef 由 Watcom 的初始化表在 main 之前呼叫。
(C) 確認音效:標題確認播的是 FDOTHER #77 的第 1 段,長度與取樣率。
(D) lc159b 呼叫紀錄(續一百六十,不重跑)裡每次 delay 的指令數拆解:沒遇到中斷、一般、閃爍前後段。
(0) 先對照修好的 `disasm_le.py calls`(續掃)、位元組掃描與舊版單次掃描:下面的呼叫端列表都靠它。
全部從 FD2.EXE、extracted/raw/FDOTHER/FDOTHER_077.bin、.wsl_build/lc159_live/ 與續一百五十八的證據重算;任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import hashlib
import json

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _META, _MD, dl, insn, operand  # noqa: E402

OUT = out_path("timer_base_and_delay_slowdown_s161_20261028.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
RAW = ROOT / ".wsl_build" / "lc159_live"
DELTA = 0x19C000                        # 紀錄裡的 EIP = linear + DELTA(續一百五十九 / 一百六十)
FX = dl.build_fixups(_EXE, _META)
_ep = json.loads((ROOT / "docs/data/ail_entry_points.json").read_text(encoding="utf-8"))
AIL = {v: int(k, 16) for k, v in _ep["entry_points"].items()}
_inv = json.loads((ROOT / "docs/data/function_inventory.json").read_text(encoding="utf-8"))
ENTRIES = sorted(int(e["addr"], 16) for e in (_inv.get("entries", _inv) if isinstance(_inv, dict) else _inv))


def func_of(a: int) -> int:
    """a 落在哪個函式入口之後(function_inventory 的入口表)。"""
    return ENTRIES[bisect.bisect_right(ENTRIES, a) - 1]


def rel32_callers(tgt: int) -> dict[int, str]:
    """obj1 逐位元組掃 E8 / E9 rel32 指向 tgt 的位置(不靠線性反組譯)。"""
    out = {}
    for off in range(len(_CODE) - 4):
        if _CODE[off] in (0xE8, 0xE9):
            if _CBASE + off + 5 + int.from_bytes(_CODE[off + 1:off + 5], "little", signed=True) == tgt:
                out[_CBASE + off] = "call" if _CODE[off] == 0xE8 else "jmp"
    return out


def callers(tgt: int) -> list[int]:
    """呼叫端:位元組掃描與 disasm_le 的續掃反組譯兩個來源必須一致(且都對齊)。"""
    byte = rel32_callers(tgt)
    hits, _ = dl.find_rel_callers(_MD, _CODE, _CBASE, tgt)
    assert sorted(byte) == [h[0] for h in hits] and all(h[3] for h in hits), (hex(tgt), byte, hits)
    return sorted(byte)


def fx_imm(a: int) -> int:
    """a 那一條指令裡被 fixup 的絕對位址(一條指令只能有一筆)。"""
    i = next(_MD.disasm(_CODE[a - _CBASE:a - _CBASE + 16], a, 1))
    t = [FX[x] for x in range(a, a + i.size) if x in FX]
    assert len(t) == 1, (hex(a), t)
    return t[0]


def seq(start: int, end: int) -> list[tuple[int, str]]:
    """start .. end 的指令(線性、不得中斷)。"""
    out = [(i.address, f"{i.mnemonic} {i.op_str}".strip())
           for i in _MD.disasm(_CODE[start - _CBASE:end - _CBASE], start)]
    assert out and out[-1][0] + 1 > end - 16, (hex(start), hex(end))
    return out


assert hashlib.md5(_EXE).hexdigest() == MD5

# ================= (0) 工具對照:修好的 calls 與位元組掃描、舊版單次掃描 =================
# 指向 function_inventory 入口的 call / jmp rel32(5 bytes)邊:續掃反組譯(對齊)vs 位元組掃描 vs 舊版單次掃描
_ins, _stops = dl.resync_sweep(_MD, _CODE, _CBASE)
_ents = set(ENTRIES)
SWEEP = {(i.address, int(i.op_str, 16)) for i in _ins if i.mnemonic in ("call", "jmp") and i.size == 5
         and i.op_str.startswith("0x") and int(i.op_str, 16) in _ents}
BYTES = set()
for _o in range(len(_CODE) - 4):
    if _CODE[_o] in (0xE8, 0xE9):
        _t = _CBASE + _o + 5 + int.from_bytes(_CODE[_o + 1:_o + 5], "little", signed=True)
        if _t in _ents:
            BYTES.add((_CBASE + _o, _t))
_single_end = _CBASE
for _i in _MD.disasm(_CODE, _CBASE):
    _single_end = _i.address + _i.size
assert _stops[0] == _single_end == 0x3CAE4 and len(_stops) == 42
OLD = {e for e in SWEEP if e[0] < _single_end}
_all: dict[int, list[int]] = {}
for _a, _t in SWEEP:
    _all.setdefault(_t, []).append(_a)
OLD_ZERO = sorted(t for t, c in _all.items() if all(a >= _single_end for a in c))
ONLY_BYTES = sorted(BYTES - SWEEP)
assert SWEEP <= BYTES and len(ONLY_BYTES) == 8 and not {a for a, _ in ONLY_BYTES} & {i.address for i in _ins}
assert (0x4D690, 0x4DC3A) in ONLY_BYTES and (0x460DC, 0x25BF4) in SWEEP - OLD
TOOLS = {"single_sweep_end": hex(_single_end), "resync_stops": len(_stops), "entries": len(_ents),
         "sweep_edges": len(SWEEP), "byte_edges": len(BYTES), "byte_only_unaligned": [[hex(a), hex(t)] for a, t in ONLY_BYTES],
         "edges_missed_by_old": len(SWEEP - OLD), "targets_zero_callers_in_old": len(OLD_ZERO),
         "of_which_below_old_end": len([t for t in OLD_ZERO if t < _single_end])}
assert {k: v for k, v in TOOLS.items() if k != "byte_only_unaligned"} == {
    "single_sweep_end": "0x3cae4", "resync_stops": 42, "entries": 1356, "sweep_edges": 6354, "byte_edges": 6362,
    "edges_missed_by_old": 1028, "targets_zero_callers_in_old": 244, "of_which_below_old_end": 47}, TOOLS

# ================= (A) AIL 計時通道 =================
NAME = {AIL[n]: n for n in ("AIL_register_timer", "AIL_set_timer_frequency", "AIL_set_timer_period",
                            "AIL_set_timer_divisor", "AIL_start_timer", "AIL_set_timer_user", "AIL_set_preference",
                            "AIL_install_DIG_INI", "AIL_install_MDI_INI", "AIL_install_DIG_driver_file",
                            "AIL_install_MDI_driver_file", "AIL_install_driver")}
assert {v: hex(k) for k, v in NAME.items()} == {
    "AIL_register_timer": "0x387bc", "AIL_set_timer_frequency": "0x38a10", "AIL_set_timer_period": "0x3899a",
    "AIL_set_timer_divisor": "0x38a86", "AIL_start_timer": "0x38bd9", "AIL_set_timer_user": "0x388a7",
    "AIL_set_preference": "0x37f70", "AIL_install_DIG_INI": "0x3908b", "AIL_install_MDI_INI": "0x3aa72",
    "AIL_install_DIG_driver_file": "0x39176", "AIL_install_MDI_driver_file": "0x3ab49",
    "AIL_install_driver": "0x38f2b"}
# AIL_startup 沒有標準前導,ail_entry_points 列為未解析;它的 trace 字串落在 0x37d3e 這個函式裡
STARTUP = 0x37D3E
assert [func_of(int(x, 16)) for x in _ep["_unresolved_trace_sites"]["AIL_startup"]] == [STARTUP]

# 預設值:AIL_startup 用 18 次 AIL_set_preference(n, v);內部 0x3f937 寫進 dword 陣列 0x5430c[n]
PREF: dict[int, int] = {}
_pp = seq(0x3FCAE, 0x3FD8F)
assert len(_pp) == 18 * 4
for k in range(18):
    (_, pv), (_, pn), (ca, c), (_, ad) = _pp[4 * k:4 * k + 4]
    assert pv.startswith("push ") and pn == f"push {k if k < 10 else hex(k)}" and c == f"call {AIL['AIL_set_preference']:#x}" \
        and ad == "add esp, 8", (k, pv, pn, c, ad)
    PREF[k] = int(pv.split()[1], 0)
assert callers(0x3F937) == [0x37FDD] and func_of(0x37FDD) == AIL["AIL_set_preference"]
assert insn(0x3F946) == "mov dword ptr [eax*4 + 0x430c], ebx" and fx_imm(0x3F946) == 0x5430C
PREF_BASE = 0x5430C
assert (PREF[0], PREF[10]) == (200, 120), PREF

# 計時器登錄端:公開 AIL_register_timer 與內部 0x3f236 的呼叫端各自完整列出
REG = callers(AIL["AIL_register_timer"])
REG_INT = callers(0x3F236)
assert REG == [0x3FB1B, 0x411EF, 0x43F6A] and REG_INT == [0x37E7B, 0x38820], (REG, REG_INT)
assert func_of(0x38820) == AIL["AIL_register_timer"]               # 公開版只是轉呼叫內部版
CB = {a: fx_imm(a - 5) for a in REG + [0x37E7B]}                    # 每個登錄前一條 push 的就是回呼位址
assert all(insn(a - 5).startswith("push ") for a in CB)
assert CB == {0x3FB1B: 0x3F565, 0x411EF: 0x404C0, 0x43F6A: 0x43270, 0x37E7B: 0x37C30}, CB
# 頻率:公開 set_frequency 的呼叫端與各自的引數來源
FREQ = callers(AIL["AIL_set_timer_frequency"])
assert FREQ == [0x3FB76, 0x412AE, 0x44155] and callers(0x3F3C8) == [0x37E8B, 0x38A7C]
assert func_of(0x38A7C) == AIL["AIL_set_timer_frequency"]
assert insn(0x412A3) == "mov ebx, dword ptr [0x430c]" and fx_imm(0x412A3) == PREF_BASE + 4 * 0     # DIG:pref[0]
assert insn(0x4414A) == "mov ecx, dword ptr [0x4334]" and fx_imm(0x4414A) == PREF_BASE + 4 * 10    # MDI:pref[10]
assert insn(0x37E88) == "push 0x64"                                                                # AIL_startup:100 Hz
assert insn(0x3FB6D) == "movsx eax, word ptr [eax + 0x2e]" and insn(0x3FB06) == "cmp word ptr [eax + 0x2e], 0" \
    and insn(0x3FB0B) == "jg 0x3fb16"                                                              # 驅動自己的:> 0 才登錄
# 週期與除數:set_period 只有三個呼叫端(BIOS 轉接、set_frequency 內部、set_divisor 內部),公開 set_divisor 沒人呼叫
assert callers(AIL["AIL_set_timer_period"]) == [0x3ED50, 0x3F3E6, 0x3F428]
assert callers(AIL["AIL_set_timer_divisor"]) == []
assert func_of(0x3F3E6) == 0x3F3C8 and func_of(0x3F428) == 0x3F3F8
assert [insn(0x3ED49), insn(0x3ED4E)] == ["push 0xd68d", "push 0x3c"]                               # 通道 15 = BIOS,54925 µs
BIOS_US = operand(0x3ED49, "push ")
assert [insn(a) for a in (0x3F3D8, 0x3F3DD, 0x3F3E0)] == ["mov eax, 0xf4240", "mov ebx, dword ptr [ebp + 0xc]", "div ebx"]
US_PER_S = operand(0x3F3D8, "mov eax, ")                                                                                  # 週期 µs = 1e6 // Hz
# PIT 取「所有非空通道的最小週期」:0x3ec17 掃 16 個通道,狀態非 0 才比
_mn = dict(seq(0x3EC2D, 0x3EC58))
assert _mn[0x3EC2D] == "cmp dword ptr [edi + 0x2a94], 0" and _mn[0x3EC36] == "mov eax, dword ptr [edi + 0x2b14]" \
    and _mn[0x3EC3E] == "jae 0x3ec42" and _mn[0x3EC45] == "cmp edi, 0x40" and _mn[0x3EC52] == "mov dword ptr [0x2be2], ecx"
assert insn(0x3EC59) == "call 0x3ebe4" and callers(0x3EC17) == [0x3F3B9]
assert [insn(a) for a in (0x3EBFB, 0x3EC00)] == ["mov ebx, 0x20bc", "mov ecx, 0x2710"]               # 除數 = µs × 10000 / 8380
PIT_MUL, PIT_DIV = operand(0x3EC00, "mov ecx, "), operand(0x3EBFB, "mov ebx, ")
CHANNELS = {"DIG 服務 0x404c0": US_PER_S // PREF[0], "MDI 服務 0x43270": US_PER_S // PREF[10],
            "AIL_startup 0x37c30": US_PER_S // operand(0x37E88, "push "), "BIOS 轉接(通道 15)": BIOS_US}
BASE_US = min(CHANNELS.values())
assert [k for k, v in CHANNELS.items() if v == BASE_US] == ["DIG 服務 0x404c0"] and BASE_US == 5000, CHANNELS
PIT_DIVISOR = BASE_US * PIT_MUL // PIT_DIV
assert (CHANNELS, PIT_DIVISOR) == ({"DIG 服務 0x404c0": 5000, "MDI 服務 0x43270": 8333, "AIL_startup 0x37c30": 10000,
                                    "BIOS 轉接(通道 15)": 54925}, 5966), (CHANNELS, PIT_DIVISOR)
# main 到兩個驅動的計時器登錄:每一步都是直接 call
CHAIN = {"AIL_startup": [(0x25C01, STARTUP)],
         "DIG": [(0x25C2B, 0x3908B), (0x390E5, 0x413C0), (0x41402, 0x39176), (0x391E3, 0x41300), (0x4135C, 0x40CF0)],
         "MDI": [(0x25C06, 0x3AA72), (0x3AACC, 0x44240), (0x44282, 0x3AB49), (0x3ABB6, 0x44180), (0x441DC, 0x43AD0)]}
for path in CHAIN.values():
    for k, (site, tgt) in enumerate(path):
        assert insn(site) == f"call {tgt:#x}", (hex(site), insn(site))
        assert func_of(site) == (0x25BF4 if k == 0 else path[k - 1][1]), hex(site)
assert func_of(0x411EF) == func_of(0x412AE) == func_of(0x412BA) == 0x40CF0
assert func_of(0x43F6A) == func_of(0x44155) == func_of(0x44161) == 0x43AD0 and func_of(0x37E7B) == STARTUP
assert insn(0x412BA) == insn(0x44161) == f"call {AIL['AIL_start_timer']:#x}"
# 和續一百五十八的實測對照:BIOS tick 的最佳格點週期
S158 = json.loads((EVIDENCE / "followups_s158_20261027.json").read_text(encoding="utf-8"))["bios_tick_interval"]["runs"]
GRID = {k: v["best_period_ms"] for k, v in S158.items()}
assert GRID and set(GRID.values()) == {BASE_US / 1000}, GRID

# 中斷處理程式 0x3ea8e:重入時只送 EOI 就返回,累加器不加;正常路徑先送 EOI、開中斷,才跑回呼
ISR = dict(seq(0x3EA8E, 0x3EBB4))
assert ISR[0x3EA8E] == "cmp dword ptr cs:[0x2be6], 0" and ISR[0x3EA96] == "ja 0x3ebad"
assert [ISR[a] for a in (0x3EBAD, 0x3EBAE, 0x3EBB0, 0x3EBB2, 0x3EBB3)] == \
    ["push eax", "mov al, 0x20", "out 0x20, al", "pop eax", "iretd"]
assert ISR[0x3EAB6] == "inc dword ptr [0x2be6]" and ISR[0x3EAED] == "add eax, edx" and ISR[0x3EAFD] == "inc dword ptr [edi + 0x2b54]"
_eoi, _sti, _cb = 0x3EB13, 0x3EB15, 0x3EB3C
assert (ISR[_eoi], ISR[_sti], ISR[_cb]) == ("out 0x20, al", "sti", "call dword ptr [edi + 0x2a54]")
assert _eoi < _sti < _cb < 0x3EB5D and ISR[0x3EB5D] == ISR[0x3EB91] == "dec dword ptr [0x2be6]"
assert ISR[0x3EB49] == "cmp edi, 0x3c"                                       # 回呼只跑通道 0 .. 14;15 是 BIOS 轉接
ISR_NOTE = {"reentry_check": "0x3ea8e cmp [0x52be6],0 ; ja 0x3ebad", "drop_path": "0x3ebad EOI + iretd(累加器不加)",
            "eoi_sti_before_callbacks": [hex(_eoi), hex(_sti), hex(_cb)], "reentry_dec": ["0x3eb5d", "0x3eb91"]}

# ================= (B) 校準在 AIL 之前 =================
CAL_FN = 0x3DFEF
assert callers(CAL_FN) == [] and sorted(a for a, t in FX.items() if t == CAL_FN) == [0x539B8]
XI_WALK = dict(seq(0x460EE, 0x4612D))
XI_LO, XI_HI = fx_imm(0x460EE), fx_imm(0x460F3)
assert (XI_LO, XI_HI) == (0x539B0, 0x539E0)
assert XI_WALK[0x460FA] == "mov al, 0xff" and XI_WALK[0x46108] == "ja 0x4610f" and XI_WALK[0x4610F] == "add esi, 6" \
    and XI_WALK[0x46100] == "cmp byte ptr [esi], 2" and XI_WALK[0x46121] == "call eax"   # 6 bytes 一筆,先跑優先序小的
XI = []
for a in range(XI_LO, XI_HI, operand(0x4610F, "add esi, ")):
    flag, prio = dl.object_bytes(_EXE, _META, a, 2)
    XI.append((a, flag, prio, FX.get(a + 2)))
assert (0x539B6, 0, 0x20, CAL_FN) in XI and len(XI) == 8, XI
assert callers(0x460EA) == [0x3CED5] and insn(0x3CEDC) == "call 0x4609b" and 0x3CED5 < 0x3CEDC
assert callers(0x25BF4) == [0x460DC] and func_of(0x460DC) == 0x4609B                         # main 只從 0x4609b 呼叫
_cm = seq(0x4609B, 0x460DC)                     # 從入口直線走到 main 的呼叫:沒有 ret、跳躍都留在這一段裡
assert not [t for _, t in _cm if t.startswith("ret")]
assert all(0x4609B <= int(t.split()[1], 16) <= 0x460DC for _, t in _cm if t.startswith("j")), _cm
assert insn(0x25C01) == f"call {STARTUP:#x}"                                                    # main 的第一個 AIL 呼叫
CAL_LOOP = [t for _, t in seq(0x3E00B, 0x3E014)]
DELAY_LOOP = [t for _, t in seq(0x3E04B, 0x3E054)]
assert CAL_LOOP == ["mov ah, 0x2c", "int 0x21", "inc esi", "cmp bl, dh", "je 0x3e00b"], CAL_LOOP
assert DELAY_LOOP == ["mov ah, 0x2c", "int 0x21", "cmp bl, dh", "dec esi", "jne 0x3e04b"], DELAY_LOOP
assert insn(0x3E014) == "mov dword ptr [0x41b0], esi" and fx_imm(0x3E014) == 0x541B0
assert [insn(a) for a in (0x3E02B, 0x3E032, 0x3E037)] == ["imul eax, dword ptr [0x41b0]", "add eax, 0x1f4", "mov esi, 0x3e8"]

# ================= (C) 確認音效 =================
assert insn(0x1F8D6) == "push 0x4d" and fx_imm(0x1F8D9) == 0x51A4D and insn(0x1F8DE) == "call 0x111ba"
assert dl.object_bytes(_EXE, _META, 0x51A4D, 12) == b"FDOTHER.DAT\x00"
assert insn(0x1F8E6) == "mov dword ptr [esp + 0x54], eax"
_cf = [t for _, t in seq(0x1FED3, 0x1FEE0)]
assert _cf == ["push 1", "push 1", "push dword ptr [esp + 0x5c]", "call 0x25a96"], _cf   # 兩個 push 之後 0x5c = 原本的 0x54
SFX_LOOP, SFX_IDX = operand(0x1FED3, "push "), operand(0x1FED5, "push ")   # cdecl:先推最後一個引數
_ps = dict(seq(0x25AC7, 0x25B40))
# play_sfx_a 的引數:[esp + 0x10] 表、[esp + 0x14] 段(-1 不播)、[esp + 0x18] 播放次數
assert (_ps[0x25AD5], _ps[0x25ADC], _ps[0x25B20]) == ("cmp dword ptr [esp + 0x14], -1", "mov eax, dword ptr [esp + 0x14]",
                                                       "push dword ptr [esp + 0x18]")
assert (SFX_IDX, SFX_LOOP) == (1, 1)
assert [_ps[a] for a in (0x25AE0, 0x25AEB, 0x25AF2, 0x25AF5, 0x25AF8)] == \
    ["shl eax, 2", "add edx, dword ptr [eax + 6]", "mov edx, dword ptr [eax + 6]", "mov eax, dword ptr [eax + 0xa]", "sub eax, edx"]
SFX_CALLS = [(a, t) for a, t in sorted(_ps.items()) if t.startswith("call ")]
assert [NAME.get(int(t.split()[1], 16)) or {v: k for k, v in AIL.items()}.get(int(t.split()[1], 16)) for _, t in SFX_CALLS] == \
    ["AIL_stop_sample", "AIL_init_sample", "AIL_set_sample_address", "AIL_set_sample_loop_count", "AIL_start_sample"]
# 取樣率:AIL_set_sample_playback_rate 的 5 個呼叫端都在 AIL 內部的檔案載入函式裡,從 main 沿直接呼叫到不了
# (對照組:DIG 設頻率 0x412ae 與 play_sfx_a 的 init_sample 0x25b03 都到得了)
RATE_SITES = callers(AIL["AIL_set_sample_playback_rate"])
assert RATE_SITES == [0x41BFE, 0x41CF6, 0x41D54, 0x41E78, 0x459E5], RATE_SITES
assert not {func_of(a) for a in RATE_SITES} & {int(t.split()[1], 16) for _, t in SFX_CALLS}
import callgraph_le  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
_cg = callgraph_le.CG(str(GAME / "FD2.EXE"))
_cg.build([0x25BF4])
RATE_REACHED = [a for a in RATE_SITES if a in _cg.reached]
assert RATE_REACHED == [] and {0x412AE, 0x25B03, 0x1FEDB} <= _cg.reached, RATE_REACHED
assert insn(0x39584) == "call 0x414e0" and func_of(0x39584) == AIL["AIL_init_sample"]
RATE = operand(0x4154E, "mov dword ptr [eax + 0x3c], ")
FORMAT = operand(0x41540, "mov dword ptr [eax + 0x34], ")
assert (RATE, FORMAT) == (11025, 0)
FD77 = (ROOT / "extracted/raw/FDOTHER/FDOTHER_077.bin").read_bytes()
assert FD77[:6] == b"LLLLLL"
OFFS = [int.from_bytes(FD77[6 + 4 * k:10 + 4 * k], "little") for k in range(5)]
assert OFFS[0] == 6 + 4 * 5 and OFFS[-1] == len(FD77), OFFS                                  # 4 段,最後一個位移 = 檔尾
SFX_BYTES = OFFS[SFX_IDX + 1] - OFFS[SFX_IDX]
SFX_S = SFX_BYTES / RATE
SFX_S4 = round(SFX_S, 4)
assert (SFX_BYTES, SFX_S4) == (4277, 0.3879), (SFX_BYTES, SFX_S)

# ================= (D) lc159b 的 delay 拆解 =================
META = (RAW / "lc159b_meta.txt").read_text(encoding="utf-8").splitlines()
assert META[0].split() == ["2dbf231b7f649cb8cd59d55407715f6b", "CALLLOG.TXT"] and META[1].split() == [MD5, "FD2.EXE"]
CAL = json.loads((RAW / "lc159b_post.json").read_text(encoding="utf-8"))["calib_541b0"]
assert CAL == 9057
_lines = (RAW / "lc159b_calllog_filtered.txt").read_text(encoding="ascii").splitlines()
assert _lines[0] == META[3] and "icount=1" in META[3]
DELAY = 0x3E01D
FIRST_E: dict[int, float] = {}
_open: dict[str, tuple] = {}
ROWS: list[dict] = []
for ln in _lines:
    t = ln.split()
    if t[0] not in ("E", "R"):
        continue
    kv = dict(x.split("=", 1) for x in t if "=" in x)
    i, n, tt = int(kv["i"]), int(kv["n"]), float(kv["t"])
    eip = int(t[2], 16) - DELTA
    if t[0] == "E":
        FIRST_E.setdefault(eip, tt)
    if eip != DELAY:
        continue
    if t[0] == "E":
        _open[t[1]] = (int(kv["s"].split(",")[0], 16), i, n, tt, int(t[3], 16) - DELTA)
    else:
        ms, i0, n0, t0, ret = _open.pop(t[1])
        it = (ms * CAL + 500) // 1000 or 1                          # 與 0x3e02b .. 0x3e046 相同
        ROWS.append({"ms": ms, "it": it, "di": i - i0, "dn": n - n0, "dt": tt - t0, "t0": t0, "ret": ret})
assert not _open and len(ROWS) == 969
G0 = min(FIRST_E.values())
GAME_PER_ITER, OVERHEAD = 6, 3          # 每圈的遊戲選擇子指令數與每次呼叫的固定開銷:由沒遇到中斷的 delay 精確成立
for r in ROWS:
    r["extra"] = r["di"] - GAME_PER_ITER * r["it"] - OVERHEAD   # 中斷處理程式在遊戲選擇子裡多跑的指令
FREE = [r for r in ROWS if r["extra"] == 0]
assert len(FREE) == 330 and {r["ms"] for r in FREE} == {2} and min(r["extra"] for r in ROWS) == 0
assert min(r["extra"] for r in ROWS if r["extra"]) > 50                     # 和「有中斷」之間有明顯間隙


def pool(rs: list[dict]) -> dict:
    it = sum(r["it"] for r in rs)
    return {"n": len(rs), "iter_per_s": round(it / sum(r["dt"] for r in rs) * 1000, 1),
            "instr_per_iter": round(sum(r["dn"] for r in rs) / it, 1),
            "isr_game_instr_per_iter": round(sum(r["extra"] for r in rs) / it, 1)}


BLINK = sorted((r for r in ROWS if r["ms"] == 80), key=lambda r: r["t0"])
assert len(BLINK) == 8 and FIRST_E[0x1FEF0] < BLINK[0]["t0"] and BLINK[-1]["t0"] < FIRST_E[0x1FF31]
NORMAL = [r for r in ROWS if r["ms"] >= 8 and r["ms"] != 80]
CLASSES = {"no_isr": pool(FREE), "normal_ge_8ms": pool(NORMAL), "blink_1_4": pool(BLINK[:4]),
           "blink_5": pool(BLINK[4:5]), "blink_6_8": pool(BLINK[5:])}
EPI = [round(r["extra"] / r["it"], 1) for r in BLINK]
PRE = sorted((r for r in ROWS if r["t0"] < FIRST_E[0x1FED3]), key=lambda r: r["t0"])[-4:]
PRE_EPI = [round(r["extra"] / r["it"], 1) for r in PRE]
D8 = sorted(r["extra"] / r["it"] for r in ROWS if r["ms"] == 8)
# 判準(同一類比較):確認前選單最後 4 次 delay(8) < 閃爍後 3 次 < 第 5 次 < 閃爍前 4 次 —— 中斷工作分三段,
# 前 4 次與後 3 次之間有明顯間隙。後 3 次仍高於選單,原因未查(不當成「回到一般水準」)
assert max(PRE_EPI) < min(EPI[5:]) and max(EPI[5:]) < EPI[4] < min(EPI[:4]), (PRE_EPI, EPI)
assert min(EPI[:4]) - max(EPI[5:]) > 30, EPI
# 音效從確認那一刻起播 SFX_S 秒,結束點落在第 4 次 delay 之內、第 5 次之前
CONF = FIRST_E[0x1FED3]
SFX_END = CONF + SFX_S * 1000
assert BLINK[3]["t0"] < SFX_END < BLINK[4]["t0"], (BLINK[3]["t0"], SFX_END, BLINK[4]["t0"])
RESIDUAL = round(CAL / CLASSES["no_isr"]["iter_per_s"], 4)
PRE_SITES = sorted({hex(r["ret"]) for r in PRE})
D8Q = [round(D8[len(D8) * k // 10], 1) for k in (1, 5, 9)]
TIMES = {"confirm_s": round((CONF - G0) / 1000, 4), "sfx_end_s": round((SFX_END - G0) / 1000, 4),
         "blink_delay_t0_s": [round((r["t0"] - G0) / 1000, 4) for r in BLINK]}
assert (PRE_SITES, D8Q) == (["0x1fd73"], [3.1, 14.6, 26.0]), (PRE_SITES, D8Q)
assert TIMES == {"confirm_s": 9.2878, "sfx_end_s": 9.6757,
                 "blink_delay_t0_s": [9.289, 9.3853, 9.4848, 9.5814, 9.679, 9.7722, 9.8647, 9.9559]}, TIMES
assert CLASSES == {
    "no_isr": {"n": 330, "iter_per_s": 8767.8, "instr_per_iter": 481.9, "isr_game_instr_per_iter": 0.0},
    "normal_ge_8ms": {"n": 381, "iter_per_s": 7989.6, "instr_per_iter": 530.8, "isr_game_instr_per_iter": 33.0},
    "blink_1_4": {"n": 4, "iter_per_s": 7488.0, "instr_per_iter": 571.8, "isr_game_instr_per_iter": 75.7},
    "blink_5": {"n": 1, "iter_per_s": 7837.8, "instr_per_iter": 545.1, "isr_game_instr_per_iter": 52.0},
    "blink_6_8": {"n": 3, "iter_per_s": 7833.7, "instr_per_iter": 538.8, "isr_game_instr_per_iter": 37.4}}, CLASSES
assert (EPI, PRE_EPI, RESIDUAL) == ([74.6, 76.9, 75.4, 76.0, 52.0, 36.8, 36.3, 39.1], [14.9, 15.1, 18.4, 14.5], 1.033), \
    (EPI, PRE_EPI, RESIDUAL)

OUTD = {
    "generator": rel(GEN_DIR / "ev_s161.py"),
    "exe_md5": MD5,
    "calls_tool_crosscheck": TOOLS,
    "timer_channels": {
        "preferences_0x5430c": {str(k): v for k, v in PREF.items()},
        "register_sites": {hex(a): hex(CB[a]) for a in CB},
        "register_internal_sites": [hex(a) for a in REG_INT],
        "frequency_sites": [hex(a) for a in FREQ],
        "period_us": CHANNELS,
        "driver_own_timer": "0x3fb1b 登錄 0x3f565,頻率 = 驅動描述 +0x2e(word),> 0 才登錄;值在 .DIG / .MDI 檔裡,這裡沒讀",
        "base_us": BASE_US, "pit_divisor": PIT_DIVISOR,
        "chains_from_main": {k: [[hex(s), hex(t)] for s, t in v] for k, v in CHAIN.items()},
        "s158_bios_tick_grid_ms": GRID,
        "isr": ISR_NOTE,
    },
    "calibration": {"function": hex(CAL_FN), "xi_table": [hex(XI_LO), hex(XI_HI)],
                    "xi_records": [[hex(a), f, p, hex(t) if t else None] for a, f, p, t in XI],
                    "init_walker_call": "0x3ced5 call 0x460ea", "main_call": "0x460dc call 0x25bf4",
                    "cal_loop": CAL_LOOP, "delay_loop": DELAY_LOOP},
    "confirm_sfx": {"table": "FDOTHER.DAT #0x4d(0x1f8de)", "index": SFX_IDX, "loop_count": SFX_LOOP,
                    "offsets": OFFS, "bytes": SFX_BYTES, "rate_hz": RATE, "format_field_0x34": FORMAT,
                    "duration_s": SFX_S4, "play_sfx_calls": [[hex(a), t] for a, t in SFX_CALLS]},
    "delay_decomposition": {"calllog": rel(RAW / "lc159b_calllog_filtered.txt"), "calibration": CAL,
                            "game_instr_per_iter": GAME_PER_ITER, "overhead_per_call": OVERHEAD,
                            "classes": CLASSES, "blink_isr_game_instr_per_iter": EPI,
                            "pre_confirm_last4": PRE_EPI, "pre_confirm_sites": PRE_SITES, "delay8_quantiles_10_50_90": D8Q, **TIMES,
                            "calibration_over_no_isr": RESIDUAL},
    "conclusion": {
        "3a": "5 ms 基底是 AIL 的 DIG 服務計時器(回呼 0x404c0):AIL_startup 把 pref[0] 預設成 200 Hz,"
              "DIG 驅動安裝時以它設頻率;其餘通道 120 Hz / 100 Hz / 54925 µs 都比較慢。(CODE;續一百五十八實測 5.000 ms 格點相符)",
        "1": "校準在 main 之前、AIL 之前,沒有 200 Hz 計時中斷。遊戲中 delay 沒遇到中斷時每秒 8767.8 圈;"
             "每圈多出的中斷工作:確認前選單約 15 條、閃爍前 4 次約 76 條(7488 圈 / 秒)、後 3 次約 37 條。"
             "前後段的分界落在確認音效(0.388 s)播完的那一次 delay(推論:DIG 混音);後 3 次仍高於選單,"
             "校準 / 沒中斷 = 1.033 的差距,兩者都未解釋。",
    },
}
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, "base_us", BASE_US, "classes", {k: v["iter_per_s"] for k, v in CLASSES.items()})
