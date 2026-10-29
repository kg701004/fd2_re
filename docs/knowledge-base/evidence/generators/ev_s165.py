"""續一百六十五證據:evidence/reentry_catchup_mdi_driver_s165_20261029.json(續一百六十四「仍留」的離線分析;沒有實機)。

使用者 2026-10-29「剩下沒解的 請依照你的建議逐項進行處理」。只用續一百六十三已錄的 lc163a 呼叫紀錄、FD2.EXE 反組譯
與遊戲目錄裡的 MDI 驅動 SBPRO2.MDI(16 位元反組譯),不重跑。
(A) 續一百六十四沒歸類的那一次重入(3665.216 ms):中斷處理程式 0x3ea8e 的路徑長度可由程式碼逐段數出
    (進入 18 條 + 16 個通道格各 5 條 + 每個啟用通道多 5 條 + 每次溢位多 2 條 …);用它對紀錄:
    前兩次中斷走「鎖住、不叫回呼」的路徑,待辦數累積,第三次一口氣補叫 MDI 2 次、DIG 3 次;
    重入落在第一次 MDI 的 int 31h 返回點,只是之後接的是第二次 MDI(9 條)而不是 DIG(14 條)。
(B) MDI 驅動呼叫期間擋住 IRQ 的是誰:MDI.INI 指定 SBPRO2.MDI;它的 int 66h 分派器 0x132 一進來就 cli,
    0x502(MDI 服務唯一呼叫的功能)的可達指令沒有 sti / popf / iret / int,分派器 0x1b1 的 iret 才還原 IF。
    紀錄上 MDI 型重入之後到下一筆的非遊戲指令固定 302(DIG 型是 69),而之前的非遊戲指令隨驅動工作量變;
    所以中斷是在驅動的工作做完之後、int 31h 返回前的同一點收的。
(C) 校準每次 int 21h 多出的非遊戲指令:遊戲中 delay(2) 的每次呼叫並不是定值;量出它的範圍與時段差,
    校準的值落在範圍之外;BIOS tick 要多貴才解釋得了。原因仍沒找到。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import statistics
import struct

import capstone

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
import _exeops as X  # noqa: E402
from _exeops import insn  # noqa: E402
import callgraph_le as cg  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("reentry_catchup_mdi_driver_s165_20261029.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DRV_MD5 = "8879265bf3b414346f66c326389e32ae"
RAW = ROOT / ".wsl_build" / "lc163_live"
DELTA = 0x19C000
S163 = json.loads((EVIDENCE / "timer_interrupt_loss_s163_20261029.json").read_text(encoding="utf-8"))
S164 = json.loads((EVIDENCE / "interrupt_off_sections_s164_20261029.json").read_text(encoding="utf-8"))
ISR, REENTRY, DIG, MDI, DELAY, CAL_FN = 0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x3E01D, 0x3DFEF
EPI, EPI_CHAIN, CB_RET = 0x3EB9D, 0x3EB69, 0x3EB42

# ================= 原始紀錄(同續一百六十四;E 另外留 ret / esp / ss) =================
META = (RAW / "lc163a_meta.txt").read_text(encoding="utf-8").splitlines()
CALLLOG_MD5 = S163["run"]["calllog_md5"]
assert META[0].split() == [CALLLOG_MD5, "CALLLOG.TXT"] and META[1].split() == [MD5, "FD2.EXE"], META
_text = (RAW / "lc163a_CALLLOG.TXT").read_text(encoding="ascii")
assert _text.count("\n") == int(META[2]) == S163["run"]["lines"]
REC: list[dict] = []
for ln in _text.splitlines()[1:]:
    p = ln.split()
    if p[0] not in ("E", "R", "A"):
        continue
    kv = dict(x.split("=", 1) for x in p if "=" in x)
    if "t" not in kv:                    # 最後一筆被 teardown 截斷(續一百六十三)
        continue
    r = {"k": p[0], "seq": int(p[1]), "eip": int(p[2], 16) - DELTA, "i": int(kv["i"]), "n": int(kv["n"]), "t": float(kv["t"])}
    if p[0] == "E":
        r.update(ret=int(p[3], 16) - DELTA, esp=int(p[4], 16), ss=int(p[5], 16), s=kv["s"])
    elif p[0] == "A":
        r.update(at=int(p[3], 16) - DELTA)
    REC.append(r)
assert len(REC) == S164["source_run"]["records"]
_isr_e = [r["t"] for r in REC if r["k"] == "E" and r["eip"] in (ISR, REENTRY)]


def walk(start: int, end: int) -> list[str]:
    """[start, end) 逐條反組譯的文字;遇到解不出的位元組就 assert 失敗。"""
    out = []
    for ins in dl.sweep_range(X._MD, X._CODE, X._CBASE, start, end):
        assert not isinstance(ins, tuple), (hex(start), ins)
        out.append(f"{ins.mnemonic} {ins.op_str}".strip())
    return out


def at(addr: int) -> str:
    return insn(addr).strip()


def clean(e: dict, r: dict) -> bool:
    """E 到 R 之間沒有任何中斷處理程式進入(0x3ea8e / 0x3ebad)。"""
    return bisect.bisect_right(_isr_e, e["t"]) == bisect.bisect_left(_isr_e, r["t"])


# ================= (A) 中斷處理程式的路徑長度(靜態) =================
PRE = walk(ISR, 0x3EADE)                          # 進入到通道迴圈之前(含進入那條)
assert PRE[0] == "cmp dword ptr cs:[0x2be6], 0" and PRE[-1] == "mov edi, 0" and len(PRE) == 19, PRE
SLOT_IDLE = walk(0x3EADE, 0x3EAE7)[:2] + walk(0x3EB09, 0x3EB11)      # 類型不是 2:cmp、jne、add、cmp、jb
SLOT_ACTIVE = walk(0x3EADE, 0x3EAF7) + walk(0x3EB03, 0x3EB11)         # 啟用、沒溢位
OVERFLOW = walk(0x3EAF7, 0x3EB03)                                      # 溢位:sub、inc 待辦數
assert SLOT_IDLE[1] == "jne 0x3eb09" and OVERFLOW == ["sub eax, dword ptr [edi + 0x2b14]", "inc dword ptr [edi + 0x2b54]"]
assert walk(0x3EB09, 0x3EB11) == ["add edi, 4", "cmp edi, 0x40", "jb 0x3eade"]                   # 16 格
AFTER_SCAN = walk(0x3EB11, 0x3EB1F)
assert AFTER_SCAN == ["mov al, 0x20", "out 0x20, al", "sti", "cmp dword ptr [0x2bea], 0", "jg 0x3eb4e"]   # 鎖住就不叫回呼
LOCKED_END = walk(0x3EB4E, 0x3EB57)[:2] + walk(0x3EB91, EPI)          # 沒有轉接待辦:cmp、je、dec、mov ss
assert LOCKED_END == ["cmp dword ptr [0x2b90], 0", "je 0x3eb91", "dec dword ptr [0x2be6]", "mov ss, word ptr [0x35fc]"]
SCAN_SKIP = walk(0x3EB24, 0x3EB2D)[:2] + walk(0x3EB46, 0x3EB4E)       # 這格沒待辦:cmp、je、add、cmp、jb
CALL_SEQ = walk(0x3EB24, CB_RET)                                       # 這格有待辦:cmp、je、dec、…、call
assert walk(0x3EB46, 0x3EB4E) == ["add edi, 4", "cmp edi, 0x3c", "jb 0x3eb24"] and CALL_SEQ[-1] == "call dword ptr [edi + 0x2a54]"
assert walk(0x3EB1F, 0x3EB24) == ["mov edi, 0"] and walk(CB_RET, 0x3EB46) == ["mov esp, esi", "jmp 0x3eb24"]
NSLOT = 16
_scan = len(PRE) - 1 + NSLOT * len(SLOT_IDLE)


def locked_di(k: int, j: int) -> int:
    """鎖住時 E(0x3ea8e)到自己 A(0x3eb9d)的遊戲指令數;k 個啟用通道、j 次溢位(A 那條也算)。"""
    return _scan + k * (len(SLOT_ACTIVE) - len(SLOT_IDLE)) + j * len(OVERFLOW) + len(AFTER_SCAN) + len(LOCKED_END) + 1


def first_cb_di(k: int, j: int, slot: int) -> int:
    """沒鎖時 E(0x3ea8e)到第一個回呼 E 的遊戲指令數;第一個有待辦的格是 slot。"""
    return (_scan + k * (len(SLOT_ACTIVE) - len(SLOT_IDLE)) + j * len(OVERFLOW) + len(AFTER_SCAN) + 1
            + slot * len(SCAN_SKIP) + len(CALL_SEQ) + 1)


SAME_SLOT_AGAIN = len(walk(CB_RET, 0x3EB46)) - 1 + len(CALL_SEQ) + 1   # 回呼 R(0x3eb42 那條)之後同一格再叫:jmp + CALL_SEQ + 進入
# k = 3(MDI 格 0、DIG 格 1、轉接 BIOS 格 15)用紀錄驗:200 Hz 期每一次「進入 → 第一個回呼」都要等於某個 j 的預測
_dig0 = next(r["t"] for r in REC if r["k"] == "E" and r["eip"] == DIG)
K = 3
_first = collections.Counter()
for p, q in zip(REC, REC[1:]):
    if p["k"] == "E" and p["eip"] == ISR and p["t"] > _dig0 and q["k"] == "E" and q["eip"] in (MDI, DIG):
        _first[(q["eip"], q["i"] - p["i"])] += 1
FIRST_FIT = {f"{'MDI' if e == MDI else 'DIG'} {d}": c for (e, d), c in sorted(_first.items())}
_pred_first = {(MDI, first_cb_di(K, j, 0)) for j in range(1, 4)} | {(DIG, first_cb_di(K, j, 1)) for j in range(1, 3)}
assert set(_first) <= _pred_first and sum(_first.values()) > 5000, (_first, _pred_first)
assert FIRST_FIT == {"DIG 134": 1969, "DIG 136": 197, "MDI 131": 2955, "MDI 133": 296}, FIRST_FIT
assert first_cb_di(K, 2, 0) == 131 and first_cb_di(K, 1, 1) == 134 and locked_di(K, 1) == 125 and SAME_SLOT_AGAIN == 9
# 同一格連叫兩次的 R → E 在整份紀錄都是 9 條(只有 3 次,其中 2 次是 3665 ms 那次補叫的 DIG)
_again = collections.Counter(q["i"] - p["i"] for p, q in zip(REC, REC[1:])
                             if p["k"] == "R" and q["k"] == "E" and p["eip"] == q["eip"] and q["eip"] in (MDI, DIG) and q["ret"] == CB_RET)
assert _again == {SAME_SLOT_AGAIN: 3}, _again

# ================= (A) 3665.216 ms 那一次 =================
_other = S164["interrupt_off"]["other"]
assert len(_other) == 1 and _other[0]["next"] == "E 0x43270"
_ri = next(k for k, r in enumerate(REC) if r["k"] == "E" and r["eip"] == REENTRY and round(r["t"], 3) == _other[0]["t"])
RE_E, NXT = REC[_ri], REC[_ri + 1]
assert REC[_ri - 1]["k"] == "E" and REC[_ri - 1]["eip"] == ISR and NXT["k"] == "E" and NXT["eip"] == MDI and NXT["ret"] == CB_RET
_isr_idx = [k for k, r in enumerate(REC[:_ri - 1]) if r["k"] == "E" and r["eip"] == ISR]
OUTER = REC[_isr_idx[-1]]                                              # 被重入的那一次(回呼還在跑)
_cb = [r for r in REC[_isr_idx[-1] + 1:] if r["k"] == "E" and r["eip"] in (MDI, DIG) and r["ret"] == CB_RET]
_end = next(k for k in range(_ri, len(REC)) if REC[k]["k"] == "A" and REC[k]["eip"] == ISR and REC[k]["at"] in (EPI, EPI_CHAIN))
_cb = [r for r in _cb if r["i"] < REC[_end]["i"]]
CATCHUP = ["MDI" if r["eip"] == MDI else "DIG" for r in _cb]
assert CATCHUP == ["MDI", "MDI", "DIG", "DIG", "DIG"], CATCHUP
assert REC[_isr_idx[-1] + 1]["eip"] == MDI and REC[_isr_idx[-1] + 1]["i"] - OUTER["i"] == first_cb_di(K, 2, 0)
# 前兩次中斷:進入到自己的 A 之間沒有回呼,指令數 = 鎖住的路徑(j = 1、2)
PREV2 = []
for k in _isr_idx[-3:-1]:
    e = REC[k]
    a = next(x for x in REC[k + 1:] if x["k"] == "A" and x["eip"] == ISR and x["seq"] == e["seq"])
    inner = [x for x in REC[k + 1:REC.index(a)] if x["k"] == "E"]
    PREV2.append({"t": round(e["t"], 3), "di_to_A": a["i"] - e["i"], "A_at": hex(a["at"]), "callbacks": len(inner)})
assert [x["t"] for x in PREV2] == [3648.295, 3653.296], PREV2
assert [x["di_to_A"] for x in PREV2] == [locked_di(K, 1), locked_di(K, 2)] and all(x["callbacks"] == 0 and x["A_at"] == hex(EPI) for x in PREV2), PREV2
# 待辦數:DIG 每格都溢位(5000 µs / 5000 µs),j 多出來的是 MDI;前兩次 + 這一次 → DIG 3、MDI 2(轉接格沒有,A 都在 0x3eb9d)
_j = [(x["di_to_A"] - locked_di(K, 0)) // len(OVERFLOW) for x in PREV2] + [
    (REC[_isr_idx[-1] + 1]["i"] - OUTER["i"] - first_cb_di(K, 0, 0)) // len(OVERFLOW)]
assert _j == [1, 2, 2], _j
PENDING = {"DIG": len(_j), "MDI": sum(_j) - len(_j)}
assert PENDING == {"DIG": CATCHUP.count("DIG"), "MDI": CATCHUP.count("MDI")}
_mdi_tail = S164["interrupt_off"]["static_tail"]["mdi_after_int31_return"]
_rest = S164["interrupt_off"]["static_tail"]["reentry_rest"]
PRED_3665 = _rest + _mdi_tail + 1 + SAME_SLOT_AGAIN
assert NXT["i"] - RE_E["i"] == PRED_3665 == _other[0]["di"] == 57, (NXT["i"] - RE_E["i"], PRED_3665)
assert PRED_3665 == S164["interrupt_off"]["predicted_di"]["mdi_driver_return"] - S164["interrupt_off"]["normal_tail"]["mdi_R_to_dig_E"] + SAME_SLOT_AGAIN
CASE_3665 = {"t": _other[0]["t"], "late_ms": _other[0]["late_ms"], "outer_isr_t": round(OUTER["t"], 3),
             "previous_two_isr": PREV2, "catchup_callbacks": CATCHUP, "pending_from": PENDING,
             "di_reentry_to_next": NXT["i"] - RE_E["i"],
             "predicted": f"{_rest} + {_mdi_tail} + 1 + {SAME_SLOT_AGAIN}(同一格再叫 MDI)= {PRED_3665}"}
assert CASE_3665["outer_isr_t"] == 3658.263, CASE_3665
MDI_TYPE_TOTAL = S164["interrupt_off"]["reentry_classes"]["mdi_driver_return"] + 1
assert MDI_TYPE_TOTAL == S163["reentry"]["callback_running"]["MDI"] == 15

# ================= (B) MDI 驅動:SBPRO2.MDI =================
_ini = (GAME / "MDI.INI").read_text(encoding="ascii").splitlines()
_drv_line = [ln.split() for ln in _ini if ln.startswith("DRIVER")]
assert _drv_line == [["DRIVER", "SBPRO2.MDI"]], _drv_line
DRV = (GAME / "SBPRO2.MDI").read_bytes()
assert hashlib.md5(DRV).hexdigest() == DRV_MD5 and DRV[:8] == b"AIL3MDI\x1a"
_md16 = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)


def d16(a: int, buf: bytes = DRV):
    for i in _md16.disasm(buf[a:a + 16], a, count=1):
        return i
    raise AssertionError(f"SBPRO2.MDI {a:#x} 解不出")


def line16(a: int, b: int) -> list[tuple[int, str]]:
    out = []
    while a < b:
        i = d16(a)
        out.append((a, f"{i.mnemonic} {i.op_str}".strip()))
        a += i.size
    assert a == b, hex(a)
    return out


def reach16(seed: int, buf: bytes = DRV) -> tuple[dict, list]:
    """從 seed 遞迴走 16 位元可達指令(跟 jcc / jmp / call / loop;ret / iret 停)。回傳 {位址: 指令}、間接轉移清單。"""
    seen, work, indirect = {}, [seed], []
    while work:
        a = work.pop()
        while a not in seen:
            i = d16(a, buf)
            seen[a] = i
            m = i.mnemonic
            if m in ("ret", "retf", "iret"):
                break
            if m in ("ljmp", "lcall"):
                indirect.append((hex(a), f"{m} {i.op_str}"))
                break
            if m == "call" or m.startswith("j") or m.startswith("loop"):
                if i.op_str.isdigit() or i.op_str.startswith("0x"):      # capstone 把 < 10 的目標印成十進位
                    work.append(int(i.op_str, 0))
                else:
                    indirect.append((hex(a), f"{m} {i.op_str}"))
                if m == "jmp":
                    break
            a += i.size
    return seen, indirect


# 走法自測:sti 只能經 loop 的目標到(0: jmp 5;2: nop;3: sti;4: ret;5: loop 2;7: ret)
_fx, _fi = reach16(0, bytes.fromhex("eb0390fbc3e2fbc3"))
assert sorted(_fx) == [0, 2, 3, 4, 5, 7] and _fi == [] and _fx[3].mnemonic == "sti", sorted(_fx)
ENTRY = struct.unpack_from("<H", DRV, 0x34)[0]
DISP = line16(ENTRY, 0x1B2)
_dt = dict(DISP)
assert ENTRY == 0x132 and _dt[0x132] == "cmp ax, 0x300" and _dt[0x137] == "cmp ax, 0x5ff" and _dt[0x13C] == "cmp bx, word ptr cs:[0x32]"
assert _dt[0x143] == "cli" and _dt[0x1B1] == "iret" and [a for a, s in DISP if s in ("sti", "popf", "pushf")] == []
assert _dt[0x181] == "mov si, 0x118" and _dt[0x184] == "sub ax, 0x200" and _dt[0x190] == "call word ptr [bx + si]"
assert d16(0x1B2).op_str == "word ptr cs:[0x36], 0" and d16(0x1C2).mnemonic == "ljmp"           # 不是給它的就轉給舊向量
TABLE_500 = list(struct.unpack_from("<7H", DRV, 0x118))
FN = 0x502
FN_ENTRY = TABLE_500[FN - 0x500]
SEEN, IND = reach16(FN_ENTRY)
KINDS = {m: sorted(hex(a) for a, i in SEEN.items() if i.mnemonic == m) for m in ("cli", "sti", "popf", "pushf", "iret", "int", "in", "out")}
assert FN_ENTRY == 0x3ED8 and IND == [] and len(SEEN) == 1315, (hex(FN_ENTRY), IND, len(SEEN))
assert all(KINDS[m] == [] for m in ("cli", "sti", "popf", "pushf", "iret", "int")) and len(KINDS["in"]) == len(KINDS["out"]) == 2, KINDS
# 遊戲端:MDI 服務可達的每個驅動呼叫都推 0x502;呼叫結構的旗標取自 pushf(此時 IF = 1),所以驅動的 iret 還原 IF = 1
_g = cg.CG(str(GAME / "FD2.EXE"))
_g.build([MDI])
DRV_CALLS = sorted(a for a, t in _g.calls.items() if t == 0x382E9 and a in _g.reached)
_push = {a: next((b for b in range(a - 12, a) if b in _g.reached and at(b) == f"push {FN:#x}"), None) for a in DRV_CALLS}
assert None not in _push.values(), _push
assert [hex(a) for a in DRV_CALLS] == ["0x4229c", "0x42354", "0x42e5c", "0x42f2d", "0x4396b"] and len(_push) == 5, DRV_CALLS
assert sorted(hex(a) for a in _g.reached if at(a) == "int 0x31") == ["0x3d7b5", "0x3d82e", "0x3f1a2"]
assert at(0x3D7B1) == "mov ah, 5" and at(0x3D7B3) == "mov al, 1" and at(0x3D82A) == "mov ah, 0" and at(0x3D82C) == "mov al, 6"   # 另兩處是 0501h / 0006h
assert walk(0x3F14B, 0x3F153) == ["pushf", "pop ax", "mov word ptr [ebp - 0x1a], ax"] and at(0x3F19F) == "lea edi, [ebp - 0x3a]"
assert 0x3A - 0x1A == 0x20 and at(0x3F156) == "mov word ptr [ebp - 0x1e], ax" and 0x3A - 0x1E == 0x1C          # 結構 +0x20 旗標、+0x1c EAX
assert at(0x3F188) == "movsx ebx, word ptr [ebx + 0x32]" and at(0x3F18C) == "mov word ptr [ebp - 0x2a], bx"  # BX = 驅動自己 +0x32 的字

# 紀錄:重入之後到下一筆的非遊戲指令。DIG 型在保護模式遊戲程式碼收中斷,MDI 型(含 3665.216)在 int 31h 服務裡
POST = {"DIG": collections.Counter(), "MDI": collections.Counter()}
PRE_NG = {"DIG": [], "MDI": []}
for k, r in enumerate(REC):
    if not (r["k"] == "E" and r["eip"] == REENTRY):
        continue
    q, isr, prev = REC[k + 1], REC[k - 1], REC[k - 2]
    if q["k"] == "A" and q["eip"] == REENTRY:
        typ = "DIG"
    elif q["k"] == "E" and q["eip"] in (DIG, MDI) and prev["k"] == "E" and prev["eip"] == MDI:
        typ = "MDI"
    else:
        raise AssertionError(("未歸類的重入", r["t"]))
    POST[typ][(q["n"] - r["n"]) - (q["i"] - r["i"])] += 1
    PRE_NG[typ].append((isr["n"] - prev["n"]) - (isr["i"] - prev["i"]))
assert sum(POST["DIG"].values()) == S164["interrupt_off"]["reentry_classes"]["dig_restore"] and sum(POST["MDI"].values()) == MDI_TYPE_TOTAL
POST_MODE = {t: POST[t].most_common(1)[0][0] for t in POST}
assert POST_MODE == {"DIG": 69, "MDI": 302} and POST["MDI"][302] == 14 and POST["DIG"][69] + POST["DIG"][70] == 62, POST
PRE_RANGE = {"MDI": [min(PRE_NG["MDI"]), max(PRE_NG["MDI"])], "DIG": sorted(set(PRE_NG["DIG"]))}
assert PRE_RANGE["MDI"][1] - PRE_RANGE["MDI"][0] > 5000 and PRE_RANGE["DIG"] == [229]                       # 之前隨驅動工作量變,之後固定
AFTER_ACCEPT = POST_MODE["MDI"] - POST_MODE["DIG"]
# 對照:沒被打斷的 MDI 服務,有驅動呼叫的那幾類非遊戲指令也隨遊戲指令數變(不是常數)
_mdi_ng = sorted({(r["n"] - e["n"]) - (r["i"] - e["i"]) for e, r in
                  [(p, q) for p, q in zip(REC, REC[1:]) if p["k"] == "E" and p["eip"] == MDI and q["k"] == "R" and q["eip"] == MDI]
                  if 0 < (r["n"] - e["n"]) - (r["i"] - e["i"]) < 2000})
MDI_NG_SUMMARY = {"distinct": len(_mdi_ng), "range": [min(_mdi_ng), max(_mdi_ng)]}
assert MDI_NG_SUMMARY == {"distinct": 91, "range": [761, 1938]}, MDI_NG_SUMMARY
DRIVER = {"mdi_ini_driver": "SBPRO2.MDI", "md5": DRV_MD5, "int66_dispatcher": f"{ENTRY:#x}(標頭 +0x34)",
          "dispatcher_cli": "0x143", "dispatcher_iret": "0x1b1", "function_table_500": [hex(x) for x in TABLE_500],
          "function_called_by_mdi_service": f"{FN:#x} → {FN_ENTRY:#x}", "reachable_insns": len(SEEN), "reachable_kinds": KINDS,
          "game_driver_calls": {hex(a): hex(b) for a, b in _push.items()},
          "rm_call_flags_from": "0x3f14b pushf → [ebp-0x1a] = 呼叫結構 +0x20",
          "post_nongame": {t: dict(sorted(POST[t].items())) for t in POST}, "pre_nongame": PRE_RANGE,
          "nongame_after_accept_beyond_dig": AFTER_ACCEPT,
          "uninterrupted_mdi_nongame_lt_2000": MDI_NG_SUMMARY}

# ================= (C) 校準:delay(2) 每次呼叫的非遊戲指令 =================
_pairs = {}
_open = {}
for r in REC:
    if r["eip"] != DELAY:
        continue
    if r["k"] == "E":
        _open[r["seq"]] = r
    elif r["k"] == "R" and r["seq"] in _open:
        _pairs[r["seq"]] = (_open.pop(r["seq"]), r)
_fixed = S164["calibration"]["delay_fixed_game_insns"] + 5 * 18
_d2 = [(e, r) for e, r in _pairs.values() if int(e["s"].split(",")[0], 16) == 2]
assert all(clean(e, r) == (r["i"] - e["i"] == _fixed) for e, r in _d2)       # 遇到中斷一定多遊戲指令(ISR 在遊戲 selector)
_dc = sorted((e["t"], (r["n"] - e["n"]) - (r["i"] - e["i"]), r["t"] - e["t"]) for e, r in _d2 if clean(e, r))
assert len(_dc) == S164["calibration"]["delay_clean_count"] == 243, len(_dc)
_med = statistics.median(x for _, x, _ in _dc)
OUTLIER = [(round(t, 1), x) for t, x, _ in _dc if x - _med > 100]
_body = [(t, x, d) for t, x, d in _dc if x - _med <= 100]
assert OUTLIER == [(4003.7, 9105)] and 9105 - _med > 500, OUTLIER            # 多一個沒記錄到的中斷(約一次反射的成本)
DELAY_NG_RANGE = [min(x for _, x, _ in _body), max(x for _, x, _ in _body)]
PER_INT21_RANGE = [round(v / 18, 2) for v in DELAY_NG_RANGE]
# 時段:最大的時間空檔把 delay 分成片頭 / 新遊戲開場兩群
_ts = [t for t, _, _ in _body]
_gap_i = max(range(1, len(_ts)), key=lambda k: _ts[k] - _ts[k - 1])
assert _ts[_gap_i] - _ts[_gap_i - 1] > 3000
_ph = {"early": _body[:_gap_i], "late": _body[_gap_i:]}
PHASE = {}
for nm, v in _ph.items():
    ng = [x for _, x, _ in v]
    PHASE[nm] = {"t_ms": [round(v[0][0], 1), round(v[-1][0], 1)], "n": len(v), "nongame_mean": round(statistics.mean(ng), 2),
                 "nongame_range": [min(ng), max(ng)], "ms_median": round(statistics.median(d for _, _, d in v), 4),
                 "insn_per_ms": round(sum(x + _fixed for _, x, _ in v) / sum(d for _, _, d in v), 1)}
assert PHASE["early"]["nongame_mean"] - PHASE["late"]["nongame_mean"] > 3 and PHASE["early"]["ms_median"] > PHASE["late"]["ms_median"]
NG_CAL = S164["calibration"]["nongame_per_int21_calibration"]
CAL_ABOVE = round(NG_CAL[0] - PER_INT21_RANGE[1], 2)
assert CAL_ABOVE > 4, CAL_ABOVE                                               # 校準的下界也高過遊戲中最大值
# 只靠 BIOS tick 要解釋的話,每個 tick 要多少非遊戲指令(續一百六十四:28 個 tick、AIL 前樣本 689 條)
_x = S164["calibration"]["int21_calls_range"]
_ex = S164["calibration"]["excess_per_int21_after_ticks"]
_tk = S164["calibration"]["bios_tick_samples_pre_ail"][0]["extra_nongame"]
_nt = -(-S164["calibration"]["bios_ticks_in_calibration"] // 1)
TICK_NEEDED = [round(_ex[0] * _x[1] / _nt + _tk), round(_ex[1] * _x[0] / _nt + _tk)]
assert TICK_NEEDED[0] > 3 * _tk, TICK_NEEDED
CALIB = {"delay_clean_nongame_range": DELAY_NG_RANGE, "per_int21_range": PER_INT21_RANGE, "outlier": OUTLIER,
         "phase": PHASE, "calibration_per_int21": NG_CAL, "calibration_above_delay_max": CAL_ABOVE,
         "tick_cost_needed_to_explain": TICK_NEEDED, "tick_sample_pre_ail": _tk, "insn_per_ms_calibration": S164["calibration"]["insn_per_ms"]["calibration"]}
assert (DELAY_NG_RANGE, PER_INT21_RANGE, CAL_ABOVE, TICK_NEEDED) == ([8558, 8577], [475.44, 476.5], 4.99, [2608, 4007]), CALIB
assert {k: (v["t_ms"], v["n"], v["nongame_mean"], v["ms_median"], v["insn_per_ms"]) for k, v in PHASE.items()} == {
    "early": ([3745.1, 7794.8], 140, 8568.87, 2.0643, 4207.4), "late": ([11520.5, 13309.6], 102, 8563.49, 2.054, 4225.3)}, PHASE

CONC = {
    "reentry_3665": f"續一百六十四沒歸類的那一次也是 MDI 型:前兩次中斷({PREV2[0]['t']} / {PREV2[1]['t']} ms)走鎖住的路徑"
                    f"({PREV2[0]['di_to_A']} / {PREV2[1]['di_to_A']} 條,= 鎖住、{K} 個啟用通道、溢位 1 / 2 次),回呼沒叫、待辦累積;"
                    f"{CASE_3665['outer_isr_t']} ms 那次補叫 MDI 2 次、DIG 3 次。重入落在第一次 MDI 的 int 31h 返回點,"
                    f"之後接第二次 MDI({SAME_SLOT_AGAIN} 條)而不是 DIG(14 條),所以是 {CASE_3665['predicted']}。"
                    f"MDI 型因此共 {MDI_TYPE_TOTAL} 次(= 續一百六十三「MDI 還沒返回」的 15)。",
    "mdi_driver": f"MDI 驅動是 SBPRO2.MDI(MDI.INI)。int 66h 分派器 0x132 一進來就 cli(0x143),MDI 服務唯一呼叫的功能 0x502({FN_ENTRY:#x})"
                  f"可達 {len(SEEN)} 條指令裡沒有 sti / popf / iret / int,也沒有間接轉移;分派器 0x1b1 的 iret 才把旗標還原成呼叫結構裡的值"
                  f"(遊戲 0x3f14b pushf,IF = 1)。紀錄上 MDI 型重入之後到下一筆的非遊戲指令 {MDI_TYPE_TOTAL} 次裡 {POST['MDI'][302]} 次是 302,DIG 型 {sum(POST['DIG'].values())} 次裡 {POST['DIG'][69] + POST['DIG'][70]} 次是 69 / 70,"
                  f"之前的非遊戲指令 {PRE_RANGE['MDI'][0]} .. {PRE_RANGE['MDI'][1]} 隨驅動工作量變:中斷是在驅動做完之後、"
                  f"int 31h 返回前的同一點收的(比 DIG 型多 {AFTER_ACCEPT} 條非遊戲指令)。所以擋住 IRQ 的是驅動整段關中斷;"
                  f"收的那一點正好在驅動 iret 還是稍後的 DOS/4GW 返回路徑,沒查(DOS/4GW 沒反組譯)。",
    "calibration": f"遊戲中沒遇到中斷的 delay(2) 每次非遊戲指令不是定值:{DELAY_NG_RANGE[0]} .. {DELAY_NG_RANGE[1]}"
                   f"(每次 int 21h {PER_INT21_RANGE[0]} .. {PER_INT21_RANGE[1]}),片頭時段平均 {PHASE['early']['nongame_mean']}、"
                   f"新遊戲開場 {PHASE['late']['nongame_mean']},每次時間 {PHASE['early']['ms_median']} / {PHASE['late']['ms_median']} ms。"
                   f"校準的 {NG_CAL[0]} .. {NG_CAL[1]} 比遊戲中最大值還多 {CAL_ABOVE} 條,不是同一段程式的正常起伏;"
                   f"若全算給 BIOS tick,每個 tick 要 {TICK_NEEDED[0]} .. {TICK_NEEDED[1]} 條(AIL 前唯一樣本 {_tk} 條)。原因仍沒找到。",
}
for _part, _key in (("125 / 127 條", "reentry_3665"), ("(3648.295 / 3653.296 ms)", "reentry_3665"), ("12716 .. 18551", "mdi_driver"),
                     ("校準的 481.49 .. 484.51", "calibration"), ("4 + 43 + 1 + 9(同一格再叫 MDI)= 57", "reentry_3665"),
                     ("共 15 次", "reentry_3665"), ("可達 1315 條指令", "mdi_driver"), ("15 次裡 14 次是 302", "mdi_driver"), ("63 次裡 62 次是 69 / 70", "mdi_driver"),
                     ("多 233 條", "mdi_driver"), ("8558 .. 8577", "calibration"), ("475.44 .. 476.5", "calibration"),
                     ("還多 4.99 條", "calibration"), ("2608 .. 4007 條", "calibration")):
    assert _part in CONC[_key], (_part, CONC[_key])

ISR_PATH_PIN = {"pre": 18, "slots": 16, "slot_idle": 5, "slot_active": 10, "overflow": 2, "after_scan": 5,
                "locked_end": 4, "scan_skip": 5, "call_seq": 7, "same_slot_again": 9, "active_channels": 3}
OUTD = {
    "generator": rel(GEN_DIR / "ev_s165.py"),
    "exe_md5": MD5,
    "approval": "使用者 2026-10-29「剩下沒解的 請依照你的建議逐項進行處理」;離線分析,沒有實機",
    "source_run": {"calllog": rel(RAW / "lc163a_CALLLOG.TXT"), "calllog_md5": CALLLOG_MD5, "records": len(REC)},
    "isr_path": {"pre": len(PRE) - 1, "slots": NSLOT, "slot_idle": len(SLOT_IDLE), "slot_active": len(SLOT_ACTIVE),
                 "overflow": len(OVERFLOW), "after_scan": len(AFTER_SCAN), "locked_end": len(LOCKED_END),
                 "scan_skip": len(SCAN_SKIP), "call_seq": len(CALL_SEQ), "same_slot_again": SAME_SLOT_AGAIN,
                 "active_channels": K, "first_callback_fit": FIRST_FIT, "same_slot_again_log": dict(_again)},
    "reentry_3665": CASE_3665,
    "mdi_driver": DRIVER,
    "calibration": CALIB,
    "conclusion": CONC,
}
assert {k: OUTD["isr_path"][k] for k in ISR_PATH_PIN} == ISR_PATH_PIN, OUTD["isr_path"]
OUT.write_text(json.dumps(OUTD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", OUT.name, CATCHUP, POST_MODE, DELAY_NG_RANGE, CAL_ABOVE)
