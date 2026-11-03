"""續一百八十八證據:evidence/chest_screen_text_s188_20261103.json(續一百八十七「仍留」:截圖文字是目視)。

使用者 2026-11-03「仍留與風險的部分 請新建或優化完善工具 進行處裡」;實機一次(lc188a,使用者「永遠核准」)。
新工具 tools/fd2_screen_text.py:整張截圖每個位置、每個顏色做字模全等比對,再對到 FDTXT 字串的原生行。
(A) 真截圖對照:ev_s138 以固定座標比對的新遊戲開場對白(lc131a_endturn 兩張),工具整張掃描得到同一串字模、同一位置,
    而且整張圖沒有其他字。
(B) ch11chest 開箱序列(real_open5/shots 以數字開頭的 29 張,相同位元組的只讀一次):問句 0x1a5 第一次出現在 51_wait_confirmed;
    YES 之後 9 張(位元組相同,算 1 張)= 0x1a5 + 0x1aa、數字 5000;第一行「打開寶箱,」只對上 0x1aa(可見寶箱),
    隱藏寶箱 0x1ae 只對上第二行、不完整。其他張沒有 0x1aa。續一百八十七的「目視」改為程式判讀。
(C) 按鍵之後:99_recovery 之後第一次送鍵是 finish_massKill 的一次 Return,隨後的 70_clear0 畫面上沒有任何字(訊息關了)。
    但那之後沒有讀旗標或金錢,finish_final.SAV 與開場存檔位元組相同(遊戲沒存檔),所以「按鍵後旗標變 1」離線仍無讀值。
(E) 實機 lc188a:索菲亞(單位 11)從 (2,10) 走到 (3,8)、指令環 ↓、YES → 旗標[9] 0、錢不變、[0x53ae1] = 5000;按一次 Return →
    旗標[9] = 1、錢 + 5000。呼叫紀錄:wait_key_with_marker 從 0x194d6 進來一次,中間只有除錯器 Alt 與那個 Return,回傳 0x1c。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys

from _evpaths import EVIDENCE, ROOT, TOOLS, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(TOOLS))
import fd2_screen_text as ST  # noqa: E402
import calllog_segments as cs  # noqa: E402

OUT = out_path("chest_screen_text_s188_20261103.json")
SWEEP = ROOT / ".wsl_build/chapter_sweep_ch11chest"
SHOTS = SWEEP / "real_open5/shots"
ENDT = ROOT / ".wsl_build/lc131a_endturn"
S138 = json.loads((EVIDENCE / "remaining_items_offline_s138_20261020.json").read_text(encoding="utf-8"))["A_title_key_after_game_over"]
S187 = json.loads((EVIDENCE / "doc25_chest_flag_wait_key_s187_20261102.json").read_text(encoding="utf-8"))
FD0 = "FDTXT_000.bin"
STR_ASK_VIS, STR_GOLD_VIS, STR_GOLD_HID = 0x1A5, 0x1AA, 0x1AE
OPENED_GOLD = 5000

FONT, STRS = ST.load_font(), ST.load_strings()
GMAP = json.loads(ST.GLYPH_MAP_PATH.read_text(encoding="utf-8"))
assert len(STRS) == 35
# 字串號與 ev_s187 一致
assert S187["strings_fdtxt000"][hex(STR_ASK_VIS)] == "發現寶箱，要打開嗎？", S187["strings_fdtxt000"]
assert S187["map10"]["opened_gold"] == OPENED_GOLD


def md5(p) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def read(p) -> dict:
    return ST.read_shot(p, FONT, STRS, GMAP)


def complete(r: dict) -> list[tuple[str, int, list[int]]]:
    return sorted((b["file"], b["string"], b["numbers"]) for b in r["boxes"] if b["complete"])


def n_cells(r: dict) -> int:
    """各行非空白格數合計 = 屬於某一行的 hit 數。"""
    return sum(sum(c is not None for c in ln["glyphs"]) for ln in r["lines"])


# ================= (A) 真截圖對照:ev_s138 的開場對白 =================
G138 = [int(g, 16) for g in S138["dialogue_glyphs"]]
X138, Y138 = S138["dialogue_xy"]
A = {}
for name in ("post_end_turn.png", "after_end3.png"):
    r = read(ENDT / name)
    assert r["readable"] and len(r["lines"]) == 1, r
    ln = r["lines"][0]
    cells = [[int(g, 16) for g in c] for c in ln["glyphs"]]
    # 工具找到的那一行從 x = 95 起(多一個『),ev_s138 從 x = 111 比 6 個字;同一列、同一串
    k = (X138 - ln["x"]) // ST.GW
    assert (X138 - ln["x"]) % ST.GW == 0 and ln["y"] == Y138 and k >= 0, (ln["x"], ln["y"])
    assert cells[k:k + len(G138)] == [[g] for g in G138], cells
    full = [(m["file"], m["string"], m["line"]) for m in ln["matches"] if m["kind"] == "full"]
    assert full == [(w[0], w[1], 4) for w in S138["dialogue"][name]["windows"]] == [("FDTXT_033.bin", 0, 4)], full
    assert r["hits"] == n_cells(r) == len(cells) == k + len(G138), (r["hits"], n_cells(r))   # 『 + ev_s138 的 6 個字;整張圖沒有別的字
    A[name] = {"md5": md5(ENDT / name), "line_xy": [ln["x"], ln["y"]], "text": ln["text"], "s138_offset_cells": k,
               "full_matches": [list(f) for f in full], "hits": r["hits"]}

# ================= (B) ch11chest 開箱序列 =================
SEQ = sorted(p for p in SHOTS.glob("*.png") if re.match(r"\d", p.name))
assert len(SEQ) == 29, [p.name for p in SEQ]
BY_MD5: dict[str, list[str]] = {}
for p in SEQ:
    BY_MD5.setdefault(md5(p), []).append(p.name)
RES = {h: read(SHOTS / names[0]) for h, names in BY_MD5.items()}
SHOT = {p.name: RES[md5(p)] for p in SEQ}

UNREADABLE = sorted(n for n, r in SHOT.items() if not r["readable"])
ASK = sorted(n for n, r in SHOT.items() if r["readable"] and complete(r) == [(FD0, STR_ASK_VIS, [])])
GOLD = sorted(n for n, r in SHOT.items() if r["readable"] and complete(r) == [(FD0, STR_ASK_VIS, []), (FD0, STR_GOLD_VIS, [OPENED_GOLD])])
NOTEXT = sorted(n for n, r in SHOT.items() if r["readable"] and r["hits"] == 0)
assert sorted(UNREADABLE + ASK + GOLD + NOTEXT) == sorted(SHOT), \
    {n: (r["readable"], r.get("hits"), complete(r)) for n, r in SHOT.items() if n not in UNREADABLE + ASK + GOLD + NOTEXT}
# 續一百八十七目視的 9 張 = 程式判讀 0x1a5 + 0x1aa(5000) 的全部
assert GOLD == sorted(S187["screens"]["after_yes"]["files"]), GOLD
assert len({md5(SHOTS / n) for n in GOLD}) == 1                       # 9 張位元組相同 = 1 張證據
assert S187["screens"]["ask"]["file"] in ASK and min(ASK) == "51_wait_confirmed.png", ASK
assert UNREADABLE == ["40_selected.png"], UNREADABLE
assert "70_clear0.png" in NOTEXT and "99_recovery.png" in GOLD
# 金額那一行可見 / 隱藏共用;分得開的是第一行「打開寶箱,」
G0 = SHOT[GOLD[0]]
L1 = [(m["file"], m["string"], m["line"]) for m in G0["lines"][1]["matches"] if m["kind"] == "full"]
L2 = [(m["file"], m["string"], m["line"], m["numbers"]) for m in G0["lines"][2]["matches"] if m["kind"] == "full"]
assert L1 == [(FD0, STR_GOLD_VIS, 0)], L1
assert L2 == [(FD0, STR_GOLD_VIS, 1, [OPENED_GOLD]), (FD0, STR_GOLD_HID, 1, [OPENED_GOLD])], L2
assert not any(b["string"] == STR_GOLD_HID and b["complete"] for b in G0["boxes"])
assert G0["hits"] == n_cells(G0) == 23                                 # 3 行 10 + 5 + 8 個字,畫面上沒有別的字
B = {"shots": rel(SHOTS), "n_files": len(SEQ), "n_distinct": len(BY_MD5),
     "unreadable": UNREADABLE, "ask_only": ASK, "ask_and_gold": GOLD, "no_text": NOTEXT,
     "gold_lines": [{"xy": [ln["x"], ln["y"]], "text": ln["text"],
                     "full": [[m["file"], hex(m["string"]), m["line"], m["numbers"]] for m in ln["matches"] if m["kind"] == "full"]}
                    for ln in G0["lines"]],
     "gold_hits": G0["hits"]}

# ================= (C) 按鍵之後 =================
FIN = (SWEEP / "finish_massKill.py").read_text(encoding="utf-8")
LOG = (SWEEP / "finish.log").read_text(encoding="utf-8").splitlines()
# finish_massKill 一開始逐次 Return + 截圖 70_clear{i},畫面有 HUD 就停;紀錄說第 1 次就停 → 只送了 1 次
assert 'S.send_keys(NAME, "Return")\n        time.sleep(0.8)\n        shot = shots_dir / f"70_clear{i}.png"' in FIN
assert LOG[1:3] == ["  LOG: battle HUD recovered after 1 clear-Return(s)", "  LOG: post-chest dialogue clear: ok=True"], LOG[:3]
assert sorted(p.name for p in SHOTS.glob("70_clear*.png")) == ["70_clear0.png"]
# 時間序(檔案時間):99_recovery < 70_clear0 < 80_pre_end_turn
T = {n: (SHOTS / n).stat().st_mtime for n in ("99_recovery.png", "70_clear0.png", "80_pre_end_turn.png")}
assert T["99_recovery.png"] < T["70_clear0.png"] < T["80_pre_end_turn.png"], T
# 之後沒有讀旗標 / 金錢;存檔沒變
READ_AFTER = bool(re.search(r"0x53ad5|0x53bf3|CHEST_PTR|read_flags", FIN, re.I))
assert not READ_AFTER
# 99_recovery 是 recover_state.py 拍的,它不送鍵 → 金額訊息之後的第一個鍵是 finish_massKill 的這次 Return
REC = (SWEEP / "recover_state.py").read_text(encoding="utf-8")
assert "99_recovery.png" in REC and "send_keys" not in REC
assert "S.read_mem(" in FIN and all("UNIT_ACTED_OFFSET" in ln for ln in FIN.splitlines() if "S.read_mem(" in ln)
SAV0 = ROOT / ".wsl_build/chapter_sweep_ch11bp/test_ch11/patched.SAV"
SAV1 = SWEEP / "finish_final.SAV"
assert "S.overwrite_save(NAME, patched_sav)" in (SWEEP / "real_open5.py").read_text(encoding="utf-8")
assert md5(SAV0) == md5(SAV1), (md5(SAV0), md5(SAV1))
C = {"first_key_after_gold": "finish_massKill.py 第一次 Return(之前的 recover_state.py 沒有 send_keys)",
     "after_key_shot": "70_clear0.png", "after_key_hits": SHOT["70_clear0.png"]["hits"],
     "mtime_order": ["99_recovery.png", "70_clear0.png", "80_pre_end_turn.png"],
     "flag_or_money_read_after_key": READ_AFTER, "save_md5_start": md5(SAV0), "save_md5_final": md5(SAV1)}

# ================= (E) 實機 lc188a(2026-11-03,使用者「永遠核准」;drivers_s188/lc188.py) =================
MD5_EXE = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
WAIT_KEY, GOLD_WAIT_CALL = 0x16C57, 0x194D6
OPENED_PTR, SLOT, UNIT, START_XY, CHEST_XY = 0x1F6C5C, 9, 11, [2, 10], [3, 8]
LIVE = ROOT / ".wsl_build/lc188_live"
CLD = LIVE / "cl/lc188a"
FP = (LIVE / "lc188a_fingerprint.txt").read_text(encoding="utf-8").split()
CALLLOG = LIVE / "lc188a_CALLLOG.TXT"
FP_EXE, FP_CALLLOG, FP_LINES = FP[0], FP[2], int(FP[4])
assert FP_EXE == MD5_EXE and FP[1] == "FD2.EXE" and FP[3] == "CALLLOG.TXT" and FP_CALLLOG == md5(CALLLOG), FP
# 金錢路徑的等鍵呼叫:E8 rel32,回返位址 = 0x194d6 + 5
GOLD_INSN = {int(g["addr"], 16): g["insn"] for g in S187["treasure_check"]["gold"]}
assert GOLD_INSN[GOLD_WAIT_CALL] == f"call {WAIT_KEY:#x}", GOLD_INSN
RET = GOLD_WAIT_CALL + 5

EVT = [json.loads(ln) for ln in (LIVE / "cl/lc188a_keys.jsonl").read_text(encoding="utf-8").splitlines()]
POS = {e["label"]: i for i, e in enumerate(EVT) if e["op"] == "state"}
STL = ("s00", "s0r", "s01", "s02", "s03")
ST_ = {lb: json.loads((CLD / f"{lb}.json").read_text(encoding="utf-8")) for lb in STL}
assert list(POS) == list(STL) and all(POS[a] < POS[b] for a, b in zip(STL, STL[1:])), POS
assert all(v["opened_ptr"] == hex(OPENED_PTR) for v in ST_.values()), {k: v["opened_ptr"] for k, v in ST_.items()}


def keys_between(a: str, b: str) -> list[str]:
    return [e["key"] for e in EVT[POS[a] + 1:POS[b]] if e["op"] in ("key", "goto_step")]


assert ST_["s00"]["units_xy"][UNIT] == START_XY and ST_["s0r"]["units_xy"][UNIT] == CHEST_XY
assert ST_["s00"]["flags"] == ST_["s0r"]["flags"] == ST_["s01"]["flags"] == [0] * 12
KB = {f"{a}->{b}": keys_between(a, b) for a, b in zip(STL, STL[1:])}
assert KB == {"s00->s0r": ["Left"] * 16 + ["Return", "Right", "Up", "Up", "Return"], "s0r->s01": ["Down", "Return"],
              "s01->s02": ["Return"], "s02->s03": ["Return"]}, KB
S1, S2, S3 = ST_["s01"], ST_["s02"], ST_["s03"]
# Q1:YES 之後、按鍵之前 —— 旗標、錢不變,只有金額 [0x53ae1] = 5000
assert S2["flags"] == S1["flags"] and S2["money"] == S1["money"] and S2["amount"] == OPENED_GOLD != S1["amount"], (S1, S2)
# Q2:再按一次 Return —— 旗標[9] = 1、其他 11 格不變,錢 + 5000
assert S3["flags"][SLOT] == 1 and [f for i, f in enumerate(S3["flags"]) if i != SLOT] == \
    [f for i, f in enumerate(S2["flags"]) if i != SLOT], S3["flags"]
assert S3["money"] - S2["money"] == OPENED_GOLD and S3["amount"] == S2["amount"], (S2["money"], S3["money"])

# 畫面(本產生器重新判讀,並與實機當時存的 .text.json 一致)
TXL = ("k08_ring_confirm", "t02", "t02b", "t03")
TX = {lb: read(CLD / f"{lb}.png") for lb in TXL}
for lb in TXL:
    saved = json.loads((CLD / f"{lb}.text.json").read_text(encoding="utf-8"))
    assert saved["lines"] == TX[lb]["lines"] and saved["boxes"] == TX[lb]["boxes"], lb
assert complete(TX["k08_ring_confirm"]) == [(FD0, STR_ASK_VIS, [])]
assert complete(TX["t02"]) == complete(TX["t02b"]) == [(FD0, STR_ASK_VIS, []), (FD0, STR_GOLD_VIS, [OPENED_GOLD])]
assert TX["t03"]["readable"] and TX["t03"]["hits"] == 0

# 呼叫紀錄:等鍵函式從 0x194d6 進來一次,回傳 Return 掃描碼;中間只有除錯器的 Alt 與那一個 Return
LG = cs._read(str(CALLLOG), calls=True)
N_LINES = CALLLOG.read_bytes().count(b"\n")      # 與 wc -l 同義
# teardown 時最後一筆寫到一半(沒有換行),_read 已丟掉那一行
assert LG.calls_parsed and LG.tail_cut
GOLD_E = [c for c in LG.calls if c.eip == WAIT_KEY + DELTA and c.ret == RET + DELTA]
assert len(GOLD_E) == 1, [(c.seq, hex(c.ret)) for c in GOLD_E]
CALL = GOLD_E[0]
CALL_ID = CALL.seq
RT = LG.rets[CALL_ID]
assert RT.kind == "R" and RT.entry == CALL.eip, RT
MAKES = [k.data for k in LG.keys if CALL.line < k.line < RT.line and not k.data & 0x80]
SC_RETURN, SC_ALT = 0x1C, 0x38
RET_SC = RT.eax
assert N_LINES == FP_LINES, (N_LINES, FP_LINES)
assert MAKES[-1] == SC_RETURN and set(MAKES[:-1]) <= {SC_ALT} and RET_SC == SC_RETURN, (MAKES, RET_SC)
# ebx = 金額(0x19477 mov [0x3ae1], ebx)、edi = 槽號(0x190d8 movsx edi;0x194f3 mov byte ptr [edi + eax], 1)
assert (CALL.regs["ebx"], CALL.regs["edi"]) == (OPENED_GOLD, SLOT), {k: hex(v) for k, v in CALL.regs.items()}
assert GOLD_INSN[0x19477] == "mov dword ptr [0x3ae1], ebx" and GOLD_INSN[0x194F3] == "mov byte ptr [edi + eax], 1"
E_ = {"approval": "使用者 2026-11-03「永遠核准」(問「是否核准用 lc188.py 跑一次實機」)", "instance": "lc188a",
      "fingerprint": {"exe_md5": FP_EXE, "calllog_md5": FP_CALLLOG, "calllog_lines": N_LINES},
      "states": {lb: {k: ST_[lb][k] for k in ("flags", "money", "amount")} | {"unit11_xy": ST_[lb]["units_xy"][UNIT]}
                 for lb in STL},
      "keys_between": KB,
      "screens": {lb: complete(TX[lb]) for lb in TXL},
      "wait_key_call": {"caller_ret": hex(RET), "call_id": CALL_ID, "makes_between": [hex(k) for k in MAKES],
                        "returned": hex(RET_SC), "ebx": hex(CALL.regs["ebx"]), "edi": hex(CALL.regs["edi"])},
      "money_delta": S3["money"] - S2["money"]}

RESULT = {
    "note": "續一百八十八:截圖文字改由 tools/fd2_screen_text.py 程式判讀(字模全等比對,不是 OCR 猜測)。",
    "tool": {"path": "tools/fd2_screen_text.py", "criterion": "16 × 16 窗口裡等於某色的點陣與字模完全相同(字模的 1 全是該色、0 沒有該色)",
             "line_rule": f"同列同色、x 間距 16 的倍數、空白 ≤ {ST.MAX_BLANK} 格"},
    "A_control_s138_dialogue": A,
    "B_chest_sequence": B,
    "C_after_key": C,
    "E_live_lc188a": E_,
    "conclusion": "LOG CONFIRMED(DOSBox-X 截圖,程式判讀):YES 之後畫面是 FDTXT_000 0x1a5 + 0x1aa、金額 5000(可見寶箱;0x1ae 隱藏寶箱不完整);"
                  "續一百八十七的目視判讀成立。之後第一次 Return 訊息就關了(70_clear0 沒有字)。"
                  "2026-08-28 那輪按鍵之後沒有讀值;續一百八十八實機 lc188a(LOG CONFIRMED,原版 FD2.EXE、DOSBox-X 除錯器讀值 + 呼叫紀錄):"
                  "YES 後旗標[9] 0、錢不變、[0x53ae1] = 5000,遊戲停在 0x194d6 的等鍵;按一次 Return 之後旗標[9] = 1、錢 + 5000。"
                  "pred188.txt 的 Q1 .. Q3 全部成立。",
}
OUT.write_text(json.dumps(RESULT, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT)
