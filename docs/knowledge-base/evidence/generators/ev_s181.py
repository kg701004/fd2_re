"""續一百八十一證據:evidence/sfx_ui_semantics_s181_20261101.json(續一百八十仍留:UI 池 index 1 / 5 / 6 / 8 / 0xc 的語意)。

使用者 2026-11-01「全部依照你的建議自動進行處理」。沒有新實機:FD2.EXE 反組譯、函式登錄表,與續一百零七的 cl1 .. cl14 呼叫紀錄。
(P) index 5 / 6:放它們的函式都用同一套面板動畫 —— 展開迴圈在固定兩格放 5、收起迴圈在固定兩格放 6。
    `unit_info_cards` 的順序:展開(info_card_open_anim,5 × 2)→ 等鍵 → 有已習得法術才「裝備卡收走(6)→ 畫法術列表 → 列表展開(5)→ 等鍵」
    → 收起(6 × 2)。cl1 .. cl14 每一次 `unit_info_cards` 裡實際播放的呼叫點順序,必須等於由 `unit_list_bits_1a` 回傳值預測的順序。
    2026-09-04 實機記「5 是開頭、6 是較後段」、09-08 記「5 = 開、6 = 關」,都是這個順序的一段,不是兩種說法。
(Q) index 1 / 8 / 0xc:呼叫點前後的指令(按鍵比較、接著呼叫的函式、所在函式名)。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
import re

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402

OUT = out_path("sfx_ui_semantics_s181_20261101.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
S178 = json.loads((EVIDENCE / "dig_word_order_sfx_s178_20261101.json").read_text(encoding="utf-8"))
S180 = json.loads((EVIDENCE / "sfx_ui_pool_table_s180_20261101.json").read_text(encoding="utf-8"))
CL = {nm: (ROOT / v["path"], v["md5"]) for nm, v in S178["calllogs"].items()}
NAMES = ROOT / "docs/data/function_names.json"
PLAY_A, PLAY_B = 0x25A96, 0x25B45
POOL_PUSH = "push dword ptr [0x3eec]"

assert hashlib.md5(_EXE).hexdigest() == MD5 and S180["exe_md5"] == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_BY = {v: k for k, v in _NM.items()}
_ENT = sorted(_NM)


def func_of(a: int) -> str:
    return _NM[_ENT[bisect.bisect_right(_ENT, a) - 1]]


def body(name: str) -> list:
    """登錄入口到下一個登錄入口之間的指令。"""
    lo = _BY[name]
    hi = _ENT[bisect.bisect_right(_ENT, lo)]
    return list(_MD.disasm(_CODE[lo - _CBASE:hi - _CBASE], lo))


def target(i) -> int | None:
    return int(i.op_str, 16) if i.mnemonic == "call" and re.fullmatch(r"0x[0-9a-f]+", i.op_str) else None


def plays(ins: list) -> list[tuple[int, int, int]]:
    """(呼叫點, index, 播放函式):call 前一條推 UI 池、再前一條推 index 常數。"""
    out = []
    for k, i in enumerate(ins):
        if target(i) in (PLAY_A, PLAY_B) and f"{ins[k - 1].mnemonic} {ins[k - 1].op_str}" == POOL_PUSH:
            out.append((i.address, int(ins[k - 2].op_str, 0), target(i)))
    return out


def frames(ins: list, site: int) -> tuple[str, list[int]]:
    """播放點所在迴圈放音的兩格:往回找緊接著的「cmp ebx, a; je; cmp ebx, b; jne」或「test ebx, ebx; je; cmp ebx, b; jne」。"""
    k = next(n for n, i in enumerate(ins) if i.address == site)
    w = [f"{i.mnemonic} {i.op_str}" for i in ins[k - 8:k - 3]]
    m = re.fullmatch(r"(cmp ebx, (\w+)|test ebx, ebx)\|je 0x\w+\|cmp ebx, (\w+)\|jne 0x\w+", "|".join(w[-4:]))
    assert m, (hex(site), w)
    first = 0 if m[1] == "test ebx, ebx" else int(m[2], 0)
    # 迴圈起始值:跳進迴圈條件的那條 jmp 前一條是 mov ebx, N 或 xor ebx, ebx;第一格就要放音(起始值在兩格之中)
    cond = ins[k - 9].address
    (j,) = [n for n, i in enumerate(ins) if i.mnemonic == "jmp" and i.op_str == hex(cond)]
    init = f"{ins[j - 1].mnemonic} {ins[j - 1].op_str}"
    start = 0 if init == "xor ebx, ebx" else int(re.fullmatch(r"mov ebx, (\w+)", init)[1], 0)
    assert start in (first, int(m[3], 0)), (hex(site), init, first, m[3])
    return w[0], sorted([first, int(m[3], 0)])


# ================= (P) index 5 / 6:面板展開 / 收起 =================
OPEN_ANIM, CARDS, SORTIE, SAVE = "info_card_open_anim", "unit_info_cards", "sortie_member_select", "save_slot_selector"
B_OPEN, B_CARDS, B_SORTIE, B_SAVE = body(OPEN_ANIM), body(CARDS), body(SORTIE), body(SAVE)
P_OPEN, P_CARDS, P_SORTIE, P_SAVE = plays(B_OPEN), plays(B_CARDS), plays(B_SORTIE), plays(B_SAVE)
assert [k for _a, k, _t in P_OPEN] == [5] and [k for _a, k, _t in P_CARDS] == [6, 5, 6], (P_OPEN, P_CARDS)
# 出擊選人 / 存檔欄另有游標(0)、無效(7)等,只取 5 / 6:各恰好一處
P_SORTIE, P_SAVE = [x for x in P_SORTIE if x[1] in (5, 6)], [x for x in P_SAVE if x[1] in (5, 6)]
assert sorted(k for _a, k, _t in P_SORTIE) == [5, 6] and [k for _a, k, _t in P_SAVE] == [5], (P_SORTIE, P_SAVE)
(S_OPEN,), (S_SWAP, S_LIST, S_CLOSE) = [a for a, _k, _t in P_OPEN], [a for a, _k, _t in P_CARDS]
S_SORTIE = {k: a for a, k, _t in P_SORTIE}
S_SO_OPEN, S_SO_CLOSE = S_SORTIE[5], S_SORTIE[6]
((S_SAVE, _k5, _t5),) = P_SAVE
# 兩格:展開迴圈在 0xb 與 5、收起迴圈在 0 與 7;兩個函式用同一套
F = {"open": frames(B_OPEN, S_OPEN), "close": frames(B_CARDS, S_CLOSE),
     "sortie_open": frames(B_SORTIE, S_SO_OPEN), "sortie_close": frames(B_SORTIE, S_SO_CLOSE)}
assert F["open"][1] == F["sortie_open"][1] and F["close"][1] == F["sortie_close"][1] and F["open"][1] != F["close"][1], F
# 迴圈方向:展開由 0xb 往下數(出口 jl)、收起由 0 往上數到 0xb(出口 jg);兩個函式相同
_dir = {k: v[0].split()[0] for k, v in F.items()}
assert _dir == {"open": "jl", "sortie_open": "jl", "close": "jg", "sortie_close": "jg"}, _dir

# unit_info_cards 的呼叫順序(只看有登錄名的直接呼叫與 UI 池播放)
SEQ = []
for k, i in enumerate(B_CARDS):
    t = target(i)
    if t in (PLAY_A, PLAY_B):
        SEQ.append(f"play {int(B_CARDS[k - 2].op_str, 0)}")
    elif t in _NM and _NM[t] in (OPEN_ANIM, "wait_key_with_marker", "unit_list_bits_1a", "draw_command_list", "info_card_present_frame"):
        if not SEQ or SEQ[-1] != _NM[t]:
            SEQ.append(_NM[t])
assert SEQ == [OPEN_ANIM, "wait_key_with_marker", "unit_list_bits_1a", "play 6", "draw_command_list", "play 5",
               "wait_key_with_marker", "info_card_present_frame", "play 6"], SEQ
# unit_list_bits_1a 回 0 就跳過「收走 → 列表 → 展開」那一段,直接到收起
_k = next(n for n, i in enumerate(B_CARDS) if _NM.get(target(i)) == "unit_list_bits_1a")
assert [B_CARDS[_k + 2].mnemonic, B_CARDS[_k + 3].mnemonic] == ["test", "je"], B_CARDS[_k + 2:_k + 4]
SKIP_TO = int(B_CARDS[_k + 3].op_str, 16)
assert S_LIST < SKIP_TO < S_CLOSE, hex(SKIP_TO)
_wk = [i.address for i in B_CARDS if _NM.get(target(i)) == "wait_key_with_marker"]
assert len(_wk) == 2 and _wk[0] < S_SWAP < S_LIST < _wk[1] < SKIP_TO < S_CLOSE, list(map(hex, _wk))


def predict(has_spells: bool) -> list[int]:
    o = [S_OPEN] * len(F["open"][1])
    return o + ([S_SWAP, S_LIST] if has_spells else []) + [S_CLOSE] * len(F["close"][1])


# cl1 .. cl14:每一次 unit_info_cards 裡 UI 池的播放點順序 = 預測
_POOL_IDX = {int(k, 0): v for k, v in S180["ui_pool"].items()}
OBS = collections.Counter()
N_CARDS = 0
CAPPED = collections.Counter()
CAP = 200                                  # 續一百零七:每個入口記前 200 次
for nm, (p, m5) in CL.items():
    assert hashlib.md5(p.read_bytes()).hexdigest() == m5, p
    lg = cs._read(str(p), calls=True)
    # play_sfx_a 記滿 200 次之後的就看不到(續一百零七的記錄上限);只比對記得到的前段
    _pa = [d.line for d in lg.calls if d.eip - DELTA == PLAY_A]
    capped_after = _pa[-1] if len(_pa) == CAP else None
    for c in lg.calls:
        if c.eip - DELTA == _BY[CARDS] and c.seq in lg.rets and lg.rets[c.seq].kind == "R":
            lo, hi = c.line, lg.rets[c.seq].line
            N_CARDS += 1
            inner = [d for d in lg.calls if lo < d.line < hi]
            # 只取 unit_info_cards 本體那一次(返回位址 = 該 call + 5);列表繪製裡還會再呼叫
            bits = [lg.rets[d.seq].eax for d in inner if d.eip - DELTA == _BY["unit_list_bits_1a"] and d.seq in lg.rets
                    and d.ret - DELTA == B_CARDS[_k].address + B_CARDS[_k].size]
            got = [d.ret - DELTA - 5 for d in inner if d.eip - DELTA in (PLAY_A, PLAY_B)]
            assert len(bits) == 1, (nm, c.line, bits)
            exp = predict(bits[0] != 0)
            if capped_after is not None and hi > capped_after:
                assert got == exp[:len(got)], (nm, c.line, list(map(hex, got)), list(map(hex, exp)))
                CAPPED[nm] += 1
                continue
            assert got == exp, (nm, c.line, list(map(hex, got)), list(map(hex, exp)))
            OBS[("has_spells" if bits[0] else "no_spells", len(got))] += 1
assert OBS and all(n > 0 for n in OBS.values()), OBS
# 每一次 unit_info_cards 都恰好計進完整或截斷其中一邊
assert sum(OBS.values()) + sum(CAPPED.values()) == N_CARDS, (OBS, CAPPED, N_CARDS)

# ================= (Q) index 1 / 8 / 0xc:呼叫點前後 =================
SITES = {int(k, 0): [int(s["call"], 16) for s in v["sites"]] for k, v in S180["ui_pool"].items() if int(k, 0) in (1, 8, 0xC)}
CTX = {}
for k, sites in sorted(SITES.items()):
    rows = []
    for a in sites:
        ins = body(func_of(a))
        n = next(j for j, i in enumerate(ins) if i.address == a)
        before = [f"{i.mnemonic} {i.op_str}" for i in ins[max(0, n - 12):n]]
        after = next((_NM[target(i)] for i in ins[n + 1:] if target(i) in _NM), None)
        callees_before = [_NM[target(i)] for i in ins[max(0, n - 12):n] if target(i) in _NM]
        rows.append({"call": hex(a), "func": func_of(a), "handle": "B" if target(ins[n]) == PLAY_B else "A",
                     "cmp_before": [s for s in before if s.startswith("cmp ")], "calls_before": callees_before, "next_call": after})
    CTX[k] = rows
# 1:town_hub_main 按鍵 0x1c / 0x20 時放,接著進 town_hub_select
(_r1,) = CTX[1]
assert _r1["func"] == "town_hub_main" and {"cmp eax, 0x1c", "cmp eax, 0x20"} <= set(_r1["cmp_before"]) and _r1["next_call"] == "town_hub_select", _r1
# 8:行動環開 / 收兩處
assert sorted(r["func"] for r in CTX[8]) == ["action_ring_close", "action_ring_open"], CTX[8]
# 0xc:都走 handle B;一處緊接在 unit_add_item 之後,一處在 yes_no_prompt 之後(回答 1)
assert all(r["handle"] == "B" for r in CTX[0xC]), CTX[0xC]
_c = {r["func"]: r for r in CTX[0xC]}
assert "unit_add_item" in _c["ai_mode_dispatch"]["calls_before"], _c
assert "yes_no_prompt" in _c["field_cell_treasure_check"]["calls_before"] and "cmp ebx, 1" in _c["field_cell_treasure_check"]["cmp_before"], _c

SEM = {
    "1": "城鎮選單確認(town_hub_main 按鍵 0x1c / 0x20 → town_hub_select)",
    "5": "面板展開(資訊卡、法術列表、出擊選人、存檔欄)",
    "6": "面板收起(資訊卡換到法術列表前、資訊卡與出擊選人關閉)",
    "8": "行動環開啟 / 收起(同一個音)",
    "0xc": "取得道具(寶箱 yes / no 回答「是」、unit_add_item 之後;handle B 與 handle A 疊播)",
}
assert set(SEM) == {("0x%x" % k if k >= 10 else str(k)) for k in (1, 5, 6, 8, 0xC)}
OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s181.py"), "exe_md5": MD5,
    "upstream": {"calllogs": rel(EVIDENCE / "dig_word_order_sfx_s178_20261101.json"),
                 "ui_pool": rel(EVIDENCE / "sfx_ui_pool_table_s180_20261101.json"), "names": rel(NAMES)},
    "panel": {"open_frames": F["open"][1], "close_frames": F["close"][1],
              "sites": {"open": hex(S_OPEN), "swap_to_spells": hex(S_SWAP), "spell_list_open": hex(S_LIST), "close": hex(S_CLOSE),
                        "sortie_open": hex(S_SO_OPEN), "sortie_close": hex(S_SO_CLOSE), "save_slot_open": hex(S_SAVE)},
              "unit_info_cards_order": SEQ,
              "cl_unit_info_cards": {f"{a}/{n}": v for (a, n), v in sorted(OBS.items())},
              "cl_unit_info_cards_past_play_cap": dict(sorted(CAPPED.items()))},
    "context": {("0x%x" % k if k >= 10 else str(k)): v for k, v in CTX.items()},
    "semantics": SEM,
    "verification": "STATIC ANALYSIS(反組譯)+ LOG CONFIRMED(cl1 .. cl14 每一次 unit_info_cards 的播放順序與靜態預測相同);語意名稱取自呼叫情境與登錄函式名,是 INFERRED",
    "conclusion": f"5 = 面板展開、6 = 面板收起:展開迴圈在第 {F['open'][1]} 格放 5、收起迴圈在第 {F['close'][1]} 格放 6,"
                  f"資訊卡與出擊選人用同一套;cl1 .. cl14 的 {sum(OBS.values())} 次 unit_info_cards 播放順序全部與預測相同。"
                  "2026-09-04 與 09-08 兩次實機各看到其中一段,不矛盾。1 = 城鎮選單確認、8 = 行動環開 / 收、0xc = 取得道具。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT)
