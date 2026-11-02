"""續一百八十七證據:evidence/doc25_chest_flag_wait_key_s187_20261102.json(續一百八十六更正裡的「doc25 §3.2.4 開箱後全 0 原因不明」)。

使用者 2026-11-02「先將能處理的部分 依據你的建議逐項進行處理」。沒有新實機:FD2.EXE 反組譯、FDFIELD / FDSHAP、FDTXT_000 字串,
加上 2026-08-28 ch11chest 那一輪留在 .wsl_build 的結果檔、截圖與腳本;四次 stdout 讀值由 drivers_s187/extract_stdout.py 從
子代理轉錄抽出(轉錄不在 repo)。
(A) 玩家開寶箱 field_cell_treasure_check:金錢箱先顯示「發現 N 元」、wait_key_with_marker 等按鍵,之後才加錢、寫 [[0x53ad5] + 槽號] = 1;
    道具箱則是先寫旗標再等鍵。
(B) 6 次讀旗標裡 4 次在按 YES 之前、2 次在之後;YES 之後沒有再按任何鍵,YES 後 1.5 秒到約 31 秒的截圖位元組完全相同(停在「發現 5000 元」)。
    讀法本身正確(指標值直接當線性位址,續一百八十六)。所以全 0 是遊戲還沒走到寫旗標那一步,不是旗標沒寫。
(C) 開到的是 slot 9 (3,8):第 10 張圖 5000 元只有 slot 9;對話是可見寶箱的字串(421 / 426),隱藏格 (16,15) 是 slot 10、3000 元、字串 428 / 430。
(D) real_open1 .. 4 的結果檔都沒有單位站上目標格;real_open5 兩次都在寫結果檔之前當掉。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import parse_field  # noqa: E402

OUT = out_path("doc25_chest_flag_wait_key_s187_20261102.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
MAP = 10
RAW = ROOT / "extracted/raw"
SWEEP = ROOT / ".wsl_build/chapter_sweep_ch11chest"
SHOTS = SWEEP / "real_open5/shots"
STDOUT = SWEEP / "stdout_s187.json"
NAMES = ROOT / "docs/data/function_names.json"
STORY = ROOT / "docs/data/story_script.json"
DOC25 = ROOT / "docs/knowledge-base/25-battle-event-system.md"
S185 = json.loads((EVIDENCE / "ai_chest_grab_0xc_s185_20261102.json").read_text(encoding="utf-8"))
S186 = json.loads((EVIDENCE / "ai_chest_grab_live_s186_20261102.json").read_text(encoding="utf-8"))
OPENED_PTR = 0x1F6C5C                     # [0x53ad5] 的值(續一百八十六實機)
CHEST_MASK, CHEST_VISIBLE, CHEST_HIDDEN = 0x60, 0x20, 0x40
GOLD = 1

assert hashlib.md5(_EXE).hexdigest() == MD5 and S185["exe_md5"] == MD5
assert S186["globals"]["opened_flags_ptr"] == hex(OPENED_PTR), S186["globals"]
_NM = {int(r["addr"], 16): r for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}

# ================= (A) field_cell_treasure_check 的順序 =================
TREASURE = 0x190AC
WAIT_KEY, YES_NO, DIALOG = 0x16C57, 0x19953, 0x15F84
assert (_NM[TREASURE]["name"], _NM[WAIT_KEY]["name"], _NM[YES_NO]["name"]) == \
    ("field_cell_treasure_check", "wait_key_with_marker", "yes_no_prompt")
assert "等到 BIOS 鍵盤緩衝區有鍵為止" in _NM[WAIT_KEY]["summary"]
COMMON = [
    (0x190D8, "movsx edi, word ptr [esp + 2]", "edi = 槽號(map_cell_info out+2)"),
    (0x190E6, f"test byte ptr [esp + 0x10], {CHEST_MASK:#x}", "可見或隱藏寶箱格才進來"),
    (0x190F1, "mov eax, dword ptr [0x3ad5]", ""),
    (0x190F6, "movzx eax, byte ptr [edi + eax]", "旗標[槽號]"),
    (0x190FC, "jne 0x1951b", "已開就離開"),
    (0x19125, f"test byte ptr [esp + 0x10], {CHEST_VISIBLE:#x}", "可見 / 隱藏選不同字串"),
    (0x19143, "push 0x1a5", "可見:問句"),
    (0x19161, "push 0x1ac", "隱藏:問句"),
    (0x1917E, f"call {YES_NO:#x}", "yes_no_prompt"),
    (0x191D0, "movzx eax, byte ptr [edx + eax + 0x53]", "寶物列種類"),
    (0x191D7, "jne 0x19429", "種類不是 0(道具)就往金錢 / 其他"),
]
ITEM = [
    (0x19239, "call 0x1bb8c", "unit_add_item"),
    (0x1924B, "mov byte ptr [edi + eax], 1", "寫旗標"),
    (0x1925B, f"call {WAIT_KEY:#x}", "之後才等鍵"),
]
GOLD_PATH = [
    (0x19429, f"cmp eax, {GOLD}", "種類 1 = 金錢"),
    (0x19477, "mov dword ptr [0x3ae1], ebx", "金額"),
    (0x1949A, "push 0x1aa", "可見:發現 N 元"),
    (0x194B7, "push 0x1ae", "隱藏:發現 N 元"),
    (0x194C2, f"call {DIALOG:#x}", "顯示"),
    (0x194D6, f"call {WAIT_KEY:#x}", "等鍵"),
    (0x194E8, "add dword ptr [0x3bf3], eax", "之後才加錢"),
    (0x194EE, "mov eax, dword ptr [0x3ad5]", ""),
    (0x194F3, "mov byte ptr [edi + eax], 1", "最後寫旗標"),
]
for a, want, _ in COMMON + ITEM + GOLD_PATH:
    assert insn(a) == want, (hex(a), insn(a), want)
_ITEM_FLAG, _ITEM_WAIT = ITEM[1][0], ITEM[2][0]
_GOLD_WAIT, _GOLD_ADD, _GOLD_FLAG = GOLD_PATH[5][0], GOLD_PATH[6][0], GOLD_PATH[8][0]
# 道具:旗標在等鍵之前;金錢:等鍵 → 加錢 → 旗標(中間沒有往回跳的分支,0x194c2 .. 0x194f3 直線執行)
assert _ITEM_FLAG < _ITEM_WAIT and _GOLD_WAIT < _GOLD_ADD < _GOLD_FLAG
_STRAIGHT = list(_MD.disasm(_CODE[_GOLD_WAIT - _CBASE:_GOLD_FLAG + 4 - _CBASE], _GOLD_WAIT))
assert _STRAIGHT[-1].address == _GOLD_FLAG and not any(i.mnemonic.startswith(("j", "ret")) for i in _STRAIGHT), \
    [(hex(i.address), i.mnemonic) for i in _STRAIGHT]

# 字串(FDTXT_000 = [0x53a7d] 的共用文字表)
_FD0 = [c for c in json.loads(STORY.read_text(encoding="utf-8"))["chapters"] if c["fdtxt"] == "FDTXT_000"]
assert len(_FD0) == 1
TEXT = {}
for b in _FD0[0]["boxes"]:
    TEXT.setdefault(b["string_index"], []).extend(b["lines"])
STR_ASK_VIS, STR_ASK_HID, STR_GOLD_VIS, STR_GOLD_HID = 0x1A5, 0x1AC, 0x1AA, 0x1AE
assert "".join(TEXT[STR_ASK_VIS]) == "發現寶箱，要打開嗎？" and "".join(TEXT[STR_ASK_HID]) == "發現寶藏，要挖掘嗎？"
assert "".join(TEXT[STR_GOLD_VIS]) == "打開寶箱，發現元！" and "".join(TEXT[STR_GOLD_HID]) == "挖掘寶藏，發現元！"

# ================= (C) 第 10 張圖的寶箱 =================
def idx(p) -> int:
    return int(p.stem.split("_")[1])


FLD = sorted((RAW / "FDFIELD").glob("FDFIELD_*.bin"), key=idx)
SHP = sorted((RAW / "FDSHAP").glob("FDSHAP_*.bin"), key=idx)
assert idx(FLD[MAP * 3]) == MAP * 3 and idx(SHP[MAP * 2 + 1]) == MAP * 2 + 1
_comp, _terr = FLD[MAP * 3].read_bytes(), SHP[MAP * 2 + 1].read_bytes()
_w, _h = struct.unpack_from("<HH", _comp, 0)
CELLS = {}                                  # 槽號 -> [(x, y, 地形 & 0x60)]
for y in range(_h):
    for x in range(_w):
        o = 4 + (y * _w + x) * 4
        tile = struct.unpack_from("<H", _comp, o)[0] & 0x3FF
        f = _terr[tile * 4] & CHEST_MASK
        if f:
            CELLS.setdefault(_comp[o + 2] & 0x1F, []).append((x, y, f))
CHESTS = {c["slot"]: c for c in parse_field.parse_map(str(RAW), MAP)["chests"]}
assert sorted(CELLS) == sorted(CHESTS) and all(len(v) == 1 for v in CELLS.values()), CELLS
OPENED_GOLD = 5000                          # 截圖 62 / 99 的金額(doc25 也記 5000)
SLOT_OPENED = [s for s, c in CHESTS.items() if c["native_type"] == GOLD and c["value"] == OPENED_GOLD]
assert len(SLOT_OPENED) == 1
SLOT_OPENED = SLOT_OPENED[0]
assert SLOT_OPENED == 9 and CELLS[SLOT_OPENED] == [(3, 8, CHEST_VISIBLE)], CELLS[SLOT_OPENED]
DOC25_SLOT = 10                             # doc25 記的 slot10 (16,15)
assert CELLS[DOC25_SLOT] == [(16, 15, CHEST_HIDDEN)] and CHESTS[DOC25_SLOT]["value"] == 3000
assert [x["slot"] for x in S185["anchors"]["map10_hidden"]] == [DOC25_SLOT, 11]
OPENED_XY, DOC25_XY = CELLS[SLOT_OPENED][0][:2], CELLS[DOC25_SLOT][0][:2]
assert (OPENED_XY, DOC25_XY) == ((3, 8), (16, 15))
# 旗標窗口 12 格涵蓋這兩個槽號(doc25 的「超出 12 格窗口」不成立)
WINDOW = 12
assert max(SLOT_OPENED, DOC25_SLOT) < WINDOW

# ================= (B) 讀值與畫面 =================
def md5(p) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


SHOT_ASK = "53_final.png"
SHOT_AFTER = ["60_after_yes.png"] + [f"61_poll_{i}.png" for i in range(6)] + ["62_final.png", "99_recovery.png"]
H_AFTER = {md5(SHOTS / n) for n in SHOT_AFTER}
assert len(H_AFTER) == 1 and md5(SHOTS / SHOT_ASK) not in H_AFTER, H_AFTER
SO = json.loads(STDOUT.read_text(encoding="utf-8"))
RUNS = SO["runs"]
assert [r["script"] for r in RUNS] == ["recover_state.py", "continue_from_ring.py", "confirm_open_chest.py", "recover_state.py"]
assert [r["timestamp"] for r in RUNS] == sorted(r["timestamp"] for r in RUNS)
READS = []
for r in RUNS:
    for label, ptr, flags in re.findall(r"flags (\w+ \w+): \((\d+), \[([\d, ]+)\]\)", r["stdout"]):
        READS.append((r["script"], label, int(ptr), [int(v) for v in flags.split(",")]))
    for js in re.findall(r"^\{.*?^\}", r["stdout"].replace("\r\n", "\n"), re.S | re.M):
        d = json.loads(js)
        READS.append((r["script"], "state", int(d["chest_ptr"], 16), d["flags"]))
assert len(READS) == 6 and all(p == OPENED_PTR and f == [0] * WINDOW for _, _, p, f in READS), READS
_AFTER_YES = [x for x in READS if x[1] == "after YES"]
assert len(_AFTER_YES) == 1 and READS.index(_AFTER_YES[0]) == 4
N_AFTER_YES = len(READS) - READS.index(_AFTER_YES[0])      # 之後只有 recover_state(不送鍵)
assert N_AFTER_YES == 2 and READS[-1][0] == "recover_state.py"

# 讀值的腳本:指標值直接讀(沒有再加 0x19c000);YES 之後沒有再送鍵
SRC = {n: (SWEEP / n).read_text(encoding="utf-8") for n in ("confirm_open_chest.py", "recover_state.py",
                                                         "continue_from_ring.py", "real_open5.py")}
for n in ("confirm_open_chest.py", "recover_state.py", "continue_from_ring.py"):
    assert "CHEST_PTR_LIVE = 0x53AD5 + S.NATIVE_LIVE_DELTA" in SRC[n], n
    assert re.search(r"S\.read_mem\(NAME, (ptr|chest_ptr), min_bytes=16\)", SRC[n]), n
KEYS = {n: re.findall(r'S\.send_keys\(NAME, "(\w+)"\)', SRC[n]) for n in SRC if n != "real_open5.py"}
assert KEYS == {"confirm_open_chest.py": ["Return"], "recover_state.py": [], "continue_from_ring.py": ["Down", "Return"]}, KEYS
_c = SRC["confirm_open_chest.py"]
assert _c.index('send_keys(NAME, "Return")') < _c.index('print("flags after YES:", read_flags())')

# ================= (D) real_open1 .. 5 =================
RO = {}
# 結果檔有的就是 real_open1 .. 4(real_open5 沒有)
RUNS_WITH_RESULT = sorted(int(p.parent.name[len("real_open"):]) for p in SWEEP.glob("real_open*/result.json"))
for k in range(1, 5):
    r = json.loads((SWEEP / f"real_open{k}/result.json").read_text(encoding="utf-8"))
    assert r["chest_ptr"] == hex(OPENED_PTR) and r["chest_flags_before"] == r["chest_flags_after"] == [0] * WINDOW, k
    tgt = r.get("target_xy")
    after = r.get("ally_after")
    on = tgt is not None and after is not None and [after["x"], after["y"]] == tgt
    RO[k] = {"target_xy": tgt, "reached_target": r.get("reached_target"),
             "ally_after": [after["x"], after["y"]] if after else None, "ally_on_target": on}
assert sorted(RO) == RUNS_WITH_RESULT, (sorted(RO), RUNS_WITH_RESULT)
assert not any(v["ally_on_target"] for v in RO.values()), RO
# real_open2 的 reached_target 是 True 但單位讀回仍在 (2,10)(與目標 (3,8) 不同)
assert RO[2]["reached_target"] is True and RO[2]["ally_after"] == [2, 10] != RO[2]["target_xy"]
assert not (SWEEP / "real_open5/result.json").exists() and (SWEEP / "real_open5.log").stat().st_size == 0
_lines = SRC["real_open5.py"].splitlines()


def line_of(text: str) -> int:
    hits = [i + 1 for i, s in enumerate(_lines) if text in s]
    assert len(hits) == 1, (text, hits)
    return hits[0]


L_AFTER_READ = line_of("raw = S.read_mem(NAME, chest_ptr_after, min_bytes=16)")
L_CRASH_C = line_of('report["ally_moved"] = (ally_before[OFF_X]')
# 結果檔有四處寫入(三處是提早結束);正常流程是最後一處
L_WRITE = max(i + 1 for i, s in enumerate(_lines) if '(chapter_dir / "result.json").write_text' in s)
assert _lines[L_WRITE - 1].startswith('    (chapter_dir / "result.json").write_text') and _lines[L_WRITE - 2].startswith('    report["log"]')
L_CAMP = line_of("adv = S.attempt_camp_exit(NAME, shots_dir, log)")
TB = {}
for n in ("real_open5b.log", "real_open5c.log"):
    t = (SWEEP / n).read_text(encoding="utf-8")
    m = re.findall(r'real_open5\.py", line (\d+), in main', t)
    err = t.strip().splitlines()[-1].split(":")[0]
    assert len(m) == 1, n
    TB[n] = {"main_line": int(m[0]), "error": err}
assert TB == {"real_open5b.log": {"main_line": L_CAMP, "error": "FileNotFoundError"},
              "real_open5c.log": {"main_line": L_CRASH_C, "error": "TypeError"}}, TB
assert L_CAMP < L_AFTER_READ < L_CRASH_C < L_WRITE

# ================= doc25 要更正的原句 =================
_D25 = DOC25.read_text(encoding="utf-8")
DOC25_CLAIMS = ["**一個**寶箱(map10 slot10,座標(16,15),hidden=true,開出5000元",
                "slot10(對應這次真正打開的寶箱)沒有變成1",
                "已超出round4/round7讀的12格窗口"]
assert all(c in _D25 for c in DOC25_CLAIMS)

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s187.py"), "exe_md5": MD5,
    "approval": "使用者 2026-11-02「先將能處理的部分 依據你的建議逐項進行處理」;沒有新實機",
    "upstream": {"s185": rel(EVIDENCE / "ai_chest_grab_0xc_s185_20261102.json"),
                 "s186": rel(EVIDENCE / "ai_chest_grab_live_s186_20261102.json"), "names": rel(NAMES), "story": rel(STORY)},
    "treasure_check": {"func": hex(TREASURE),
                       "common": [{"addr": hex(a), "insn": s, "note": n} for a, s, n in COMMON],
                       "item": [{"addr": hex(a), "insn": s, "note": n} for a, s, n in ITEM],
                       "gold": [{"addr": hex(a), "insn": s, "note": n} for a, s, n in GOLD_PATH]},
    "strings_fdtxt000": {hex(k): "".join(TEXT[k]) for k in (STR_ASK_VIS, STR_ASK_HID, STR_GOLD_VIS, STR_GOLD_HID)},
    "map10": {"opened_gold": OPENED_GOLD, "opened_slot": SLOT_OPENED, "opened_cell": list(OPENED_XY),
              "doc25_slot": DOC25_SLOT, "doc25_cell": list(DOC25_XY),
              "doc25_slot_value": CHESTS[DOC25_SLOT]["value"], "flag_window": WINDOW},
    "screens": {"ask": {"file": SHOT_ASK, "md5": md5(SHOTS / SHOT_ASK)},
                "after_yes": {"files": SHOT_AFTER, "md5": H_AFTER.pop()},
                "visual": "目視:53 = 「發現寶箱，要打開嗎？」+ YES / NO;60 .. 62、99 = 同一句 + 「打開寶箱，發現5000元！」(字串 0x1a5 + 0x1aa,可見寶箱)"},
    "stdout": {"extracted_by": rel(GEN_DIR / "drivers_s187/extract_stdout.py"), "source_name": SO["source_name"],
               "source_sha256": SO["source_sha256"],
               "reads": [{"script": s, "label": lb, "ptr": hex(p), "flags": f} for s, lb, p, f in READS]},
    "real_open": {"result_1_4": RO, "real_open5_tracebacks": TB,
                  "real_open5_lines": {"camp_exit": L_CAMP, "after_flags_read": L_AFTER_READ,
                                       "crash_5c": L_CRASH_C, "result_write": L_WRITE}},
    "doc25_claims": DOC25_CLAIMS,
    "verification": "STATIC ANALYSIS(反組譯、FDFIELD / FDSHAP、FDTXT_000)+ 2026-08-28 原始結果檔 / 截圖雜湊 / stdout 讀值;截圖文字為目視",
    "conclusion": f"doc25 §3.2.4 開箱後旗標全 0 的讀值是真的、讀法也對,但 YES 之後的 {N_AFTER_YES} 次讀之前都沒有再按鍵:"
                  f"金錢箱在 {_GOLD_WAIT:#x} 等鍵,{_GOLD_FLAG:#x} 才寫旗標,所以讀到 0 是遊戲還停在「發現 {OPENED_GOLD} 元」;"
                  "不是旗標區塊語意錯、也不是索引超出窗口。"
                  f"開到的是 slot {SLOT_OPENED} {OPENED_XY}(可見、{OPENED_GOLD} 元),"
                  f"不是 slot {DOC25_SLOT} {DOC25_XY}(隱藏、{CHESTS[DOC25_SLOT]['value']} 元)。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, hex(_GOLD_WAIT), hex(_GOLD_FLAG), SLOT_OPENED, len(READS))
