"""續一百八十證據(二):evidence/sfx_dialogue_step_s180b_20261101.json(續一百七十九仍留:sfx_02 / sfx_09 各對到哪一句對話、哪個單位走路)。

使用者 2026-11-01「依照你的建議自動繼續進行處理」。沒有新實機:續一百零七的 cl1 .. cl14 呼叫紀錄(每個入口前 200 次,指標處 32 位元組)、
FDTXT 各資源(extracted/raw/FDTXT)、docs/data/glyph_map.json、函式登錄表。
(W) 打字音:每次 typewriter_tick(0x164e8,每次都放 UI 池 index 2)歸到最內層包住它的 dialog(0x15f84)呼叫 —— dialog 的第 1 個參數是
    文字表(指標處 32 位元組 = 某個 FDTXT 資源的開頭 word 位移表,只對得到一個)、第 2 個是字串索引(doc14 九參數表)。
    歸不到的那些,都在 dialog 已記滿 200 次的紀錄裡、落在最後一次記到的 dialog 返回之後(記錄上限,不是沒有 dialog)。
(U) 腳步音:play_step_sfx(0x32230)第 1 個參數 = 單位索引(doc35 §16.4 拿它查職業與 0x1f183);依呼叫端函式與單位索引分組。
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
import disasm_le as dl  # noqa: E402
import decode_story_text as dst  # noqa: E402
import decode_text as dt  # noqa: E402

OUT = out_path("sfx_dialogue_step_s180b_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S178 = json.loads((EVIDENCE / "dig_word_order_sfx_s178_20261101.json").read_text(encoding="utf-8"))
CL = {nm: (ROOT / v["path"], v["md5"]) for nm, v in S178["calllogs"].items()}
FDTXT = ROOT / "extracted/raw/FDTXT"
NAMES = ROOT / "docs/data/function_names.json"
DIALOG, TYPE, STEP = 0x15F84, 0x164E8, 0x32230
CAP = 200                                  # 續一百零七:每個入口記前 200 次

assert hashlib.md5(_EXE).hexdigest() == MD5
# typewriter_tick 每次都放 index 2(不經條件);play_step_sfx 第 1 個參數在 [esp + 0x30](sub esp, 0x24 + push esi / edi 之後)
assert [insn(a) for a in (0x1653C, 0x1653E, 0x16546)] == ["push 1", "push 2", "call 0x25a96"]
assert insn(0x3224E) == "push dword ptr [esp + 0x30]" and insn(0x3223C) == "sub esp, 0x24"

_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_ENT = sorted(_NM)


def func_of(a: int) -> str:
    return _NM[_ENT[bisect.bisect_right(_ENT, a) - 1]]


assert _NM[TYPE] == "typewriter_tick" and _NM[STEP] == "play_step_sfx"
# typewriter_tick 的靜態呼叫端:都在 dialog(0x15f84)本體裡(doc14:逐字顯示時每字一次)
_tw_hits, _ = dl.find_rel_callers(_MD, _CODE, _CBASE, TYPE)
TW_SITES = {a for a, _m, _o, _al in _tw_hits}
_dlg_end = min(e for e in _ENT if e > DIALOG)
assert len(TW_SITES) == 2 and all(DIALOG < a < _dlg_end for a in TW_SITES), (sorted(map(hex, TW_SITES)), hex(_dlg_end))
RES = {int(p.stem.split("_")[1]): p for p in sorted(FDTXT.glob("FDTXT_*.bin"))}
assert len(RES) > 1 and sorted(RES) == list(range(len(RES))), sorted(RES)[:5]
STRS = {i: dt.parse_strings(str(p)) for i, p in RES.items()}


def text_of(res: int, idx: int) -> dict:
    """第一個對話框的說話者與第一行(說話者是執行期單位時 decode_story_text 寫 unit#n)。"""
    boxes = dst.decode_string(STRS[res][idx])
    spk, lines = boxes[0]
    return {"boxes": len(boxes), "first_speaker": spk, "first_line": lines[0]}


# ================= (W) 打字音 → 對話 =================
TW = collections.Counter()               # (FDTXT 資源, 字串索引) → 次數
TW_LOG: dict[str, dict] = {}
for nm, (p, m5) in CL.items():
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, p
    lg = cs._read(str(p), calls=True)
    dlg = [c for c in lg.calls if c.eip - DELTA == DIALOG]
    assert all(c.seq in lg.rets and lg.rets[c.seq].kind == "R" for c in dlg), nm
    spans = [(c.line, lg.rets[c.seq].line, c) for c in dlg]
    last = max((b for _a, b, _c in spans), default=0)
    tws = [c for c in lg.calls if c.eip - DELTA == TYPE]
    assert {c.ret - DELTA - 5 for c in tws} <= TW_SITES, nm                     # 只由 dialog 本體的兩處呼叫
    n_att = 0
    for c in tws:
        enc = [s for s in spans if s[0] < c.line < s[1]]
        if not enc:
            # 歸不到:dialog 已記滿,且在最後一次記到的 dialog 返回之後
            assert len(dlg) == CAP and c.line > last, (nm, c.line, len(dlg), last)
            continue
        assert len(enc) == 1, (nm, c.line, len(enc))       # 前提:逐字顯示的 dialog 不巢狀(名字插入的遞迴呼叫不在這裡出現)
        d = enc[0][2]
        (res,) = [i for i, b in RES.items() if b.read_bytes()[:len(d.mem_prefix["s1"])] == d.mem_prefix["s1"]]
        idx = d.stack[1]                                    # 第 2 個參數:字串索引
        assert 0 <= idx < len(STRS[res]), (nm, res, idx)
        TW[(res, idx)] += 1
        n_att += 1
    TW_LOG[nm] = {"typewriter_calls": len(tws), "attributed": n_att, "dialog_calls": len(dlg), "dialog_capped": len(dlg) == CAP}
N_TW = sum(v["typewriter_calls"] for v in TW_LOG.values())
N_ATT = sum(v["attributed"] for v in TW_LOG.values())
assert N_ATT == sum(TW.values()) and 0 < N_ATT < N_TW
assert all(v["attributed"] == v["typewriter_calls"] or v["dialog_capped"] for v in TW_LOG.values())
DIALOGUE = [{"fdtxt": res, "string_index": idx, "typewriter_calls": n, **text_of(res, idx)}
            for (res, idx), n in sorted(TW.items(), key=lambda kv: (-kv[1], kv[0]))]
assert all(d["first_line"] for d in DIALOGUE)

# ================= (U) 腳步音 → 單位 =================
STEPS = collections.Counter()            # (呼叫端函式, 單位索引) → 次數
_st_hits, _ = dl.find_rel_callers(_MD, _CODE, _CBASE, STEP)
STEP_SITES = {a for a, _m, _o, _al in _st_hits}
N_STEP = 0
for nm, (p, _m5) in CL.items():
    lg = cs._read(str(p), calls=True)
    for c in lg.calls:
        if c.eip - DELTA == STEP:
            assert c.ret - DELTA - 5 in STEP_SITES, (nm, hex(c.ret - DELTA))   # 每次都來自某個靜態呼叫端
            STEPS[(func_of(c.ret - DELTA), c.stack[0])] += 1
            N_STEP += 1
assert sum(STEPS.values()) == N_STEP
# func_of 取「包住該位址的那個登錄入口」:入口本身與入口 + 1 都要回到同一個名字
assert func_of(STEP) == func_of(STEP + 1) == "play_step_sfx" and func_of(TYPE + 1) == "typewriter_tick"
assert STEPS and all(0 <= u < 0x40 for _f, u in STEPS)                         # 單位索引(不是指標)
STEP_ROWS = [{"caller": f, "unit": u, "calls": n} for (f, u), n in sorted(STEPS.items(), key=lambda kv: (-kv[1], kv[0]))]
assert all((-a["calls"], a["caller"], a["unit"]) < (-b["calls"], b["caller"], b["unit"]) for a, b in zip(STEP_ROWS, STEP_ROWS[1:]))
STEP_UNITS = sorted({u for _f, u in STEPS})
STEP_CALLERS = sorted({f for f, _u in STEPS})

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s180b.py"), "exe_md5": MD5,
    "upstream": {"calllogs": rel(EVIDENCE / "dig_word_order_sfx_s178_20261101.json"), "fdtxt": rel(FDTXT), "names": rel(NAMES)},
    "typewriter": {"per_log": TW_LOG, "calls": N_TW, "attributed": N_ATT, "dialogue": DIALOGUE},
    "step": {"rows": STEP_ROWS, "units": STEP_UNITS, "callers": STEP_CALLERS},
    "conclusion": f"cl1 .. cl14 的 {N_TW} 次打字音(index 2)有 {N_ATT} 次歸到確切的字串,共 {len(DIALOGUE)} 句;其餘都在 dialog 記滿 "
                  f"{CAP} 次之後。腳步音(index 9 / 0xa / 0xb)來自 {len(STEP_CALLERS)} 個呼叫端函式、{len(STEP_UNITS)} 個單位索引;"
                  "單位索引對到哪個角色要看當時的單位表,本證據沒有對。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT)
