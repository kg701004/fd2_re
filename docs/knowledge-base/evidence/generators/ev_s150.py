"""續一百五十證據:evidence/palette_fade_index255_emulated_s150_20261023.json(模擬,沒有執行遊戲)。

續一百四十八 / 一百四十九留下「0x2df01 / 0x11df2 對索引 255 的處理只有 EXE 位元組」。這裡用 x86_pal_emu
直接執行原版 FD2.EXE(md5 33464c81…)這三個函式的位元組,記錄 out 0x3c8 / 0x3c9,解讀成 DAC 寫入:
  A. 0x2df01(0, 0xff, t, R, G, B):寫到的索引 = 0..254(255 不寫),值逐筆 = ev_s145 的 fade6(hi = 255)。
     fade6 是從 ev_s145.py 原始碼抽出來執行的那個函式,不是重寫。
  B. 0x11df2(0, 0xff, add):寫 0..255(255 也寫),值 = min(src + add, 0x3f)。
  C. 0x11d40(0, 0xff, s):寫 0..255,值 = max(src − s, 0)。
  D. ev_s145 的兩段實際序列(紅閃光、logo → 白 → 標題),參數取 ev_s145 已提交的證據:每一步之後的 DAC 與模型相同;
     兩份調色盤的索引 255 本來就是 (0x3f, 0x3f, 0x3f),所以「255 不寫」在這兩段沒有可見差異(兩張索引圖也沒用到 255)。
對照(必須判為不符):fade6 改向下取整。故障注入(只改直譯器讀到的位元組):0x2dfbd jl → jle、0x11e1e jg → jge、
0x11d6c jg → jge、除數 0x28 → 0x29,每個都要以預期的那一種方式不符。
"""
from __future__ import annotations

import ast
import hashlib
import json
import random
import sys

import numpy as np

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, TOOLS, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(TOOLS))
import x86_pal_emu as X  # noqa: E402
from disasm_le import object_bytes  # noqa: E402
from le_xref import parse_le  # noqa: E402

EXE_P = GAME / "FD2.EXE"
RAW = ROOT / "extracted/raw/FDOTHER"
S145 = EVIDENCE / "afterlock_live_title_transition_s145_20261021.json"
OUT = out_path("palette_fade_index255_emulated_s150_20261023.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
EXE = EXE_P.read_bytes()
assert hashlib.md5(EXE).hexdigest() == MD5
LE = parse_le(EXE)
FADE, ADD, SUB = 0x2DF01, 0x11DF2, 0x11D40

# 迴圈上界那幾條指令(故障注入改的就是這些位元組)
BOUNDS = {"0x2dfb9": ("cmp ebx, [esp+0x18]", "3b 5c 24 18"), "0x2dfbd": ("jl 0x2df21", "0f 8c"),
          "0x11e1c": ("cmp ebx, edi", "39 fb"), "0x11e1e": ("jg(共用收尾)", "0f 8f"),
          "0x11d6a": ("cmp ebx, edi", "39 fb"), "0x11d6c": ("jg(共用收尾)", "0f 8f"),
          "0x2df17": ("mov ebp, 0x28", "bd 28 00 00 00")}
for a, (_, hx) in BOUNDS.items():
    b = bytes.fromhex(hx)
    assert object_bytes(EXE, LE, int(a, 16), len(b)) == b, (a, object_bytes(EXE, LE, int(a, 16), len(b)).hex())

# ev_s145 的 fade6(從原始碼抽出那一個函式定義來執行)
_src = (GEN_DIR / "ev_s145.py").read_text(encoding="utf-8")
_defs = [n for n in ast.parse(_src).body if isinstance(n, ast.FunctionDef) and n.name == "fade6"]
assert len(_defs) == 1
_ns: dict = {"np": np}
exec(compile(ast.Module(_defs, []), "ev_s145.py", "exec"), _ns)
fade6 = _ns["fade6"]

# ev_s145 已提交的證據裡的 EXE 常數
C145 = json.loads(S145.read_text(encoding="utf-8"))["exe_constants"]
DIV = C145["fade_0x2df01"]["div"]
HI_RED, HI_TITLE = C145["fade_0x2df01"]["hi_exclusive"]
T0 = C145["transition_esi_start"]
RED_TGT = tuple(C145["transition_target_rgb6"])
W_TGT = tuple(C145["title_fade"]["target_rgb6"])
W_ESI = C145["title_fade"]["esi"]
W_ADD, SAT = C145["white_0x11df2_add"], C145["white_saturate"]
PAL_BASE, TITLE_PAL = C145["flash_base_pal"][1], C145["title_img_pal"][1]
IDX255_USED = json.loads(S145.read_text(encoding="utf-8"))["measurements"]["index_255_used"]
assert (DIV, HI_RED, HI_TITLE, SAT) == (0x28, 0xFF, 0xFF, 0x3F)

PAL6 = {n: (RAW / f"FDOTHER_{n:03d}.bin").read_bytes() for n in (PAL_BASE, TITLE_PAL)}
REAL = [PAL6[PAL_BASE], PAL6[TITLE_PAL]]


def arr(pal: bytes) -> np.ndarray:
    return np.frombuffer(pal, dtype=np.uint8).reshape(256, 3).astype(np.int64)


# 合成調色盤(6-bit):隨機、0..0x3f 依序循環(每個分量都走過 0..0x3f)、全 0、全 0x3f
_rng = random.Random(150)
SYN = [bytes(_rng.randrange(SAT + 1) for _ in range(768)), bytes(k % (SAT + 1) for k in range(768)),
       bytes(768), bytes([SAT]) * 768]
assert all(max(p) <= SAT for p in SYN + REAL)
assert all(set(arr(SYN[1])[:, c].tolist()) == set(range(SAT + 1)) for c in range(3))
TGTS = (RED_TGT, W_TGT)
ALL_T = range(DIV + 1)                 # 0x2df01 的 t:0..0x28 每一步
ADDS, SUBS = (0, 1, 0x20, W_ADD), (0, 1, 0x10, 0x40)


def check(pals: list[bytes], patches: dict[int, bytes] | None = None, floor: bool = False,
          stop_first: bool = False) -> dict:
    """A / B / C 三組;回傳各組 [呼叫數, 不符種類的清單]。stop_first:那一組出現第一筆不符就不再呼叫(對照用)。"""
    res = {"A": [0, []], "B": [0, []], "C": [0, []]}

    def go(g: str) -> bool:
        return not (stop_first and res[g][1])

    for pal in pals:
        src = arr(pal)
        for tgt in TGTS:
            for t in ALL_T:
                if not go("A"):
                    break
                d = X.run(EXE, LE, FADE, [0, 0xFF, t, *tgt], pal, patches)
                res["A"][0] += 1
                if sorted(d) != list(range(255)):
                    res["A"][1].append("index_set")
                elif any(tuple(int(v) for v in e) != d[i] for i, e in enumerate(fade6(src, tgt, t, DIV, 255, floor=floor)[:255])):
                    res["A"][1].append("value")
        for add in ADDS:
            if go("B"):
                d = X.run(EXE, LE, ADD, [0, 0xFF, add], pal, patches)
                res["B"][0] += 1
                if sorted(d) != list(range(256)):
                    res["B"][1].append("index_set")
                elif any(d[i] != tuple(min(int(v) + add, SAT) for v in src[i]) for i in d):
                    res["B"][1].append("value")
        for s in SUBS:
            if go("C"):
                d = X.run(EXE, LE, SUB, [0, 0xFF, s], pal, patches)
                res["C"][0] += 1
                if sorted(d) != list(range(256)):
                    res["C"][1].append("index_set")
                elif any(d[i] != tuple(max(int(v) - s, 0) for v in src[i]) for i in d):
                    res["C"][1].append("value")
    return res


def kinds(r: dict) -> dict:
    """對照只輸出各組不符的種類(stop_first 下呼叫數取決於第一筆不符出現在哪,不輸出)。"""
    return {g: sorted(set(b)) for g, (_, b) in r.items()}


_base = check(SYN + REAL)
base = {g: {"n": n, "mismatch": len(b)} for g, (n, b) in _base.items()}
NP = len(SYN + REAL)
assert base == {"A": {"n": NP * len(TGTS) * len(ALL_T), "mismatch": 0}, "B": {"n": NP * len(ADDS), "mismatch": 0},
                "C": {"n": NP * len(SUBS), "mismatch": 0}}, base
floor_ctrl = kinds(check(REAL, floor=True, stop_first=True))
# 故障注入:(位址, 原位元組, 改成);原位元組先對 EXE 斷言,改錯位址就對不上
INJ = {"0x2dfbd jl→jle": (0x2DFBD, b"\x0f\x8c", b"\x0f\x8e"), "0x11e1e jg→jge": (0x11E1E, b"\x0f\x8f", b"\x0f\x8d"),
       "0x11d6c jg→jge": (0x11D6C, b"\x0f\x8f", b"\x0f\x8d"), "除數 0x28→0x29": (0x2DF18, b"\x28", b"\x29")}
for _a, _old, _new in INJ.values():
    assert object_bytes(EXE, LE, _a, len(_old)) == _old and len(_new) == len(_old), hex(_a)
inj = {k: kinds(check(REAL, {a: new}, stop_first=True)) for k, (a, _, new) in INJ.items()}

assert floor_ctrl == {"A": ["value"], "B": [], "C": []}, floor_ctrl
# 每個注入只在它那一組、以預期的方式不符
EXPECT = {"0x2dfbd jl→jle": ("A", "index_set"), "0x11e1e jg→jge": ("B", "index_set"),
          "0x11d6c jg→jge": ("C", "index_set"), "除數 0x28→0x29": ("A", "value")}
for k, (grp, kind) in EXPECT.items():
    assert {g: v for g, v in inj[k].items() if v} == {grp: [kind]}, (k, inj[k])


def sequence(pal: bytes, calls: list[tuple[int, list[int]]], model) -> tuple[int, set]:
    """依序執行 calls,DAC 從全 0 開始;每一步之後與 model(步, 前一個 DAC) 比。回傳(步數, DAC[255] 出現過的值)。"""
    dac = np.zeros((256, 3), dtype=np.int64)
    seen = set()
    for k, (fn, args) in enumerate(calls):
        prev = dac.copy()
        for i, v in X.run(EXE, LE, fn, args, pal).items():
            dac[i] = v
        exp = model(k, prev)
        assert (dac == exp).all(), (k, hex(fn), args, np.argwhere(dac != exp)[:3].tolist())
        seen.add(tuple(int(v) for v in dac[255]))
    return len(calls), seen


def keep255(new: np.ndarray, prev: np.ndarray) -> np.ndarray:
    out = new.copy()
    out[255] = prev[255]          # 0x2df01 不寫 255:DAC[255] 保留前一個值(不是調色盤的值)
    return out


P_RED, P_TITLE = arr(PAL6[PAL_BASE]), arr(PAL6[TITLE_PAL])
red_calls = [(SUB, [0, 0xFF, 0])] + [(FADE, [0, HI_RED, t, *RED_TGT]) for t in range(T0, -1, -1)]
red_n, red_255 = sequence(PAL6[PAL_BASE], red_calls,
                          lambda k, prev: P_RED if k == 0 else keep255(fade6(P_RED, RED_TGT, T0 + 1 - k, DIV, 255), prev))
title_calls = ([(SUB, [0, 0xFF, 0]), (ADD, [0, 0xFF, W_ADD])]
               + [(FADE, [0, HI_TITLE, t, *W_TGT]) for t in range(W_ESI[0], W_ESI[1] + 1)])
title_n, title_255 = sequence(
    PAL6[TITLE_PAL], title_calls,
    lambda k, prev: P_TITLE if k == 0 else np.minimum(P_TITLE + W_ADD, SAT) if k == 1
    else keep255(fade6(P_TITLE, W_TGT, W_ESI[0] + k - 2, DIV, 255), prev))
WHITE = (SAT, SAT, SAT)
assert tuple(P_RED[255]) == tuple(P_TITLE[255]) == WHITE and red_255 == title_255 == {WHITE}, (red_255, title_255)
assert IDX255_USED == {"red": False, "title": False}, IDX255_USED

ev = {
    "date": "2026-10-23", "exe_md5": MD5, "exe": rel(EXE_P),
    "method": "模擬(SIMULATED):x86_pal_emu 直接執行 EXE 位元組(capstone 解碼),記錄 out 0x3c8 / 0x3c9;沒有執行遊戲。",
    "bound_instructions": {a: {"asm": s, "bytes": hx} for a, (s, hx) in BOUNDS.items()},
    "model": "ev_s145.py 的 fade6(原始碼抽出執行)",
    "constants_from": rel(S145),
    "inputs": {f"FDOTHER_{n:03d}": hashlib.sha256(PAL6[n]).hexdigest() for n in sorted(PAL6)},
    "palettes": {"synthetic": "隨機(seed 150)、0..0x3f 依序循環、全 0、全 0x3f", "real": [f"FDOTHER_{n:03d}" for n in sorted(PAL6)],
                 "t": f"0..{DIV}"},
    "checks": base,
    "controls_note": "對照與故障注入只用兩份實際調色盤,每組出現第一筆不符就停,只輸出不符的種類",
    "floor_control": floor_ctrl, "injections": inj,
    "sequences": {"red_flash": {"calls": red_n, "dac255_values": sorted(red_255)},
                  "logo_white_title": {"calls": title_n, "dac255_values": sorted(title_255)}},
    "palette_index255": {f"FDOTHER_{PAL_BASE:03d}": list(map(int, P_RED[255])), f"FDOTHER_{TITLE_PAL:03d}": list(map(int, P_TITLE[255]))},
    "index_255_used_s145": IDX255_USED,
    "conclusion": [
        f"0x2df01 寫索引 0..254、不寫 255(jl,hi 不含);0x11df2 與 0x11d40 寫 0..255(jg,hi 含在內):"
        f"{sum(v['n'] for v in base.values())} 次呼叫全部與模型相同",
        "fade6 的 hi = 255 把索引 255 設成調色盤值,實際是 DAC 保留前一個值;兩份調色盤的 255 本來就是白、"
        "兩段序列的 DAC[255] 始終是白,兩張索引圖也沒用到 255,所以這個差別在這段開場看不到",
        "對照(向下取整)與 4 個故障注入都以預期的方式判為不符",
    ],
    "not_covered": ["實機 DAC 讀值(這段開場沒有可見後果,沒有做)"],
}
js = (json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
assert b"\r" not in js
OUT.write_bytes(js)
print("ok", OUT.name, sum(v["n"] for v in base.values()), red_n, title_n)
