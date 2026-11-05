"""續一百九十三證據(靜態 + 既有實機紀錄):evidence/static_s193_sortie_softlock_20261105.json。

使用者 2026-11-05「依照你的建議自動進行處理」—— 續一百九十二附帶發現「出擊目標人數寫死 15 / 19」的後續:
名冊人數不足目標時,原版會不會卡住?
(A) 靜態(原版 FD2.EXE):
    - sortie_member_select(0x2af28)只有兩個出口:人數 == 目標(EDI = 1,回傳 1)與 Esc / Del(0x2b67f 把 Del 0x53 改成 1;
      EDI = −1,0x2b42d 回傳 0)。進入時先把 0x1e bytes 選取旗標清零(0x2af4a)。
    - 呼叫端一 town_hub_main(0x26351):章節旗標表 0x523e7[章節 byte] ≠ 0 的章節(byte 22 / 23 / 24 / 27 / 28 / 29)
      直接進選人,回傳 0 就跳回 0x26347 再叫一次;這段沒有任何名冊人數比較。
    - 呼叫端二 town_hub_select(0x267e6):先比名冊人數([0x53bfb] > 0x10,章節 byte > 0x1a 時 > 0x14),不足就略過選人;
      回傳 0 就離開設施(0x29867)。
    ⇒ 旗標章節裡 [0x53bfb] − 1 < 目標時,選人畫面只能 Esc,而 Esc 立刻再進同一畫面:無出口(只能重開)。
(B) 名冊人數只會變多:[0x53bfb] 的寫入只有 0x1144c inc(入隊 0x112a5)、0x25efa 歸零(新遊戲)與三個讀檔還原;
    依 docs/data/chapter_beats 的入隊 op 數,正常劇情進到旗標章節時的名冊下界都超過門檻(扣掉所有帶條件的處理常式、
    再把章節對應錯一位也成立)。
(C) 實機(既有紀錄 lc192b,續一百九十二;章節 byte 29、12 人可選、目標 19):0x19a 詢問(返回 0x262d5 = town_hub_main)後進入
    → Esc(K 01)→ 以 EDI = −1 離開 → 中間沒有 0x19a 詢問就再進入;之後斷點把 EBP 改 12 才以 EDI = 1 離開。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json

from _evpaths import GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _CBASE, _CODE, _EXE, _MD, _META, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402

OUT = out_path("static_s193_sortie_softlock_20261105.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
LC192B = ROOT / ".wsl_build/lc192_live/lc192b_CALLLOG.TXT"
LC192B_MD5 = "25244d521dec6935e46e09964e4de388"
BEATS = ROOT / "docs/data/chapter_beats"
SELECT, SFX, DIALOG, JOIN, ROSTER_N = 0x2AF28, 0x25A96, 0x15F84, 0x112A5, 0x53BFB
FLAG_TABLE, CHAPTER = 0x523E7, 0x53C03

assert hashlib.md5(_EXE).hexdigest() == MD5
_FX = dl.build_fixups(_EXE, _META)
INSNS, _stops = dl.resync_sweep(_MD, _CODE, _CBASE)
BY_ADDR = {i.address: i for i in INSNS}


def run(a: int, b: int) -> list[str]:
    """線性掃描(resync_sweep)在 [a, b) 的指令文字。"""
    return [f"{i.mnemonic} {i.op_str}" for i in INSNS if a <= i.address < b]


# ================= (A) 靜態 =================
# 選人迴圈的兩個出口
assert [insn(a) for a in (0x2B0A4, 0x2B0AE, 0x2B0B1, 0x2B0B3)] == [
    "call 0x2b67f", "cmp eax, 1", "jne 0x2b0b8", "mov edi, 0xffffffff"]
assert [insn(a) for a in (0x2B0DB, 0x2B0E3, 0x2B0E5, 0x2B0E7)] == [
    "call 0x2b749", "cmp eax, ebp", "jne 0x2b0f7", "mov edi, 1"]
assert [insn(a) for a in (0x2B1B1, 0x2B1B3)] == ["test edi, edi", "je 0x2b099"]
assert [insn(a) for a in (0x2B34F, 0x2B352, 0x2B42D, 0x2B42F)] == [
    "cmp edi, 1", "jne 0x2b42d", "xor edi, edi", "mov eax, edi"]
# 迴圈內寫 EDI 的只有那兩處(其餘出口不存在)
EDI_WRITES = [i.address for i in INSNS if 0x2B099 <= i.address < 0x2B1B9 and i.op_str.startswith("edi,")
              and i.mnemonic not in ("cmp", "test")]
assert EDI_WRITES == [0x2B0B3, 0x2B0E7], [hex(a) for a in EDI_WRITES]
# 0x2b67f:Del(0x53)改成 1,和 Esc 同一條路
assert [insn(a) for a in (0x2B731, 0x2B734, 0x2B736)] == ["cmp eax, 0x53", "jne 0x2b73d", "mov byte ptr [0x3a8e], 1"]
# 進入時清零選取旗標(memset(flags, 0, 0x1e))
assert [insn(a) for a in (0x2AF3E, 0x2AF42, 0x2AF44, 0x2AF4A)] == [
    "xor edi, edi", "push 0x1e", "push edi", "call 0x37910"]

# 呼叫端一:town_hub_main —— 章節旗標 → 0x19a 詢問 → 選人;回傳 0 再叫一次
assert [insn(a) for a in (0x2626D, 0x26272, 0x26279, 0x262C0, 0x262C5, 0x262D0)] == [
    "mov eax, dword ptr [0x3c03]", "cmp byte ptr [eax + 0x23e7], 0", "je 0x2637f", "push 0xa9524", "push 0x19a",
    "call 0x15f84"]
assert [insn(a) for a in (0x26347, 0x26351, 0x26360, 0x26362)] == [
    "mov eax, dword ptr [0x3bf7]", "call 0x2af28", "test eax, eax", "je 0x26347"]
CALLER1 = run(0x2626D, 0x26364)
assert not any("0x3bfb" in t for t in CALLER1), "town_hub_main 的旗標路徑比了名冊人數"
# 呼叫端二:town_hub_select —— 名冊人數門檻 → 選人;回傳 0 離開設施
assert [insn(a) for a in (0x267B8, 0x267BF, 0x267C1, 0x267C8, 0x267CA, 0x267D1, 0x267D3, 0x267DA)] == [
    "cmp dword ptr [0x3c03], 0x1b", "jge 0x267ca", "cmp dword ptr [0x3bfb], 0x10", "jg 0x267dc",
    "cmp dword ptr [0x3c03], 0x1a", "jle 0x267fd", "cmp dword ptr [0x3bfb], 0x14", "jle 0x267fd"]
assert [insn(a) for a in (0x267E6, 0x267F5, 0x267F7)] == ["call 0x2af28", "test eax, eax", "je 0x29867"]
CALLERS = sorted(a for a, *_ in dl.find_rel_callers(_MD, _CODE, _CBASE, SELECT)[0])
assert CALLERS == [0x26351, 0x267E6], [hex(a) for a in CALLERS]
# 目標人數(續一百九十二已核):15,章節 byte > 0x1a 時 19
assert [insn(a) for a in (0x2AF39, 0x2AF52, 0x2AF5B)] == ["mov ebp, 0xf", "cmp dword ptr [0x3c03], 0x1a", "mov ebp, 0x13"]
TARGET = lambda ch: 19 if ch > 0x1A else 15     # noqa: E731
# 章節旗標表:直接進選人的章節 byte
assert _FX[0x26272 + 2] == FLAG_TABLE
FLAGS = bytes(dl.object_bytes(_EXE, _META, FLAG_TABLE, 30))
FLAGGED = [i for i, b in enumerate(FLAGS) if b]
assert FLAGGED == [22, 23, 24, 27, 28, 29] and set(FLAGS) == {0, 1}, FLAGS.hex()

# ================= (B) 名冊人數只會變多 =================
def containing(site: int):
    """覆蓋 fixup 位置 site 的那條對齊指令。"""
    for a in range(site - 1, site - 8, -1):
        i = BY_ADDR.get(a)
        if i is not None and a + i.size > site:
            return i
    raise AssertionError(hex(site))


REFS = sorted(s for s, t in _FX.items() if t == ROSTER_N)
SITES = [containing(s) for s in REFS]
assert all("0x3bfb" in i.op_str for i in SITES)
WRITES = sorted((i.address, f"{i.mnemonic} {i.op_str}") for i in SITES
                if i.op_str.split(",")[0].endswith("[0x3bfb]") and i.mnemonic not in ("cmp", "push", "test"))
assert WRITES == [(0x1041E, "mov dword ptr [0x3bfb], eax"), (0x1144C, "inc dword ptr [0x3bfb]"),
                  (0x25EFA, "mov dword ptr [0x3bfb], 0"), (0x26070, "mov dword ptr [0x3bfb], eax"),
                  (0x2999A, "mov dword ptr [0x3bfb], eax")], WRITES
# 三個 mov eax 都是讀檔:前一條從存檔緩衝取 byte(+9 / +1)
assert insn(0x1041A) == "movzx eax, byte ptr [esi + 9]"
assert insn(0x2606C) == "movzx eax, byte ptr [ebx + 1]" and insn(0x29996) == "movzx eax, byte ptr [ebx + 1]"
assert insn(0x26067) == "mov dword ptr [0x3c03], eax" and insn(0x29991) == "mov dword ptr [0x3c03], eax"
JOIN_CALLS = sorted(a for a, *_ in dl.find_rel_callers(_MD, _CODE, _CBASE, JOIN)[0])
assert len(JOIN_CALLS) == 28 and 0x1144C > JOIN and all(a not in range(0x2AF28, 0x2B4FB) for a in JOIN_CALLS)

# chapter_beats:入隊 op(0x112a5)
COND_OPS = {"if", "roster_has", "party_has_item"}
HANDLERS = []
for p in sorted(BEATS.glob("ch??_*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    top = [b for b in d["beats"] if b["op"] == "join"]
    nested = [x for b in d["beats"] for k in ("then", "else") for x in (b.get(k) or []) if x.get("op") == "join"]
    HANDLERS.append((int(p.name[2:4]), p.stem[5:], len(top), len(nested),
                     any(b["op"] in COND_OPS for b in d["beats"])))
assert all(j["target"] == hex(JOIN) for p in BEATS.glob("ch??_*.json")
           for j in json.loads(p.read_text(encoding="utf-8"))["beats"] if j["op"] == "join")
assert sum(h[2] for h in HANDLERS) == 26 and sum(h[3] for h in HANDLERS) == 2
assert max(h[0] for h in HANDLERS) == 29 and len(FLAGS) == 30


def roster_bounds(ch: int) -> tuple[int, int]:
    """進章節 byte ch 的城鎮時的名冊人數:(全部無巢狀入隊, 保守下界)。
    保守下界:只算章節 < ch − 1 的處理常式(章節對應錯一位也成立),且整個處理常式有任何條件 op 就不算。"""
    plain = sum(h[2] for h in HANDLERS if h[0] < ch)
    strict = sum(h[2] for h in HANDLERS if h[0] < ch - 1 and not h[4])
    return plain, strict


BOUNDS = {ch: roster_bounds(ch) for ch in FLAGGED}
# 可選人數 = [0x53bfb] − 1(第 0 格固定;0x2b75f / 0x2b765)
assert [insn(a) for a in (0x2B75F, 0x2B765, 0x2B766)] == ["mov edx, dword ptr [0x3bfb]", "dec edx", "cmp eax, edx"]
MARGIN = {ch: (BOUNDS[ch][0] - 1 - TARGET(ch), BOUNDS[ch][1] - 1 - TARGET(ch)) for ch in FLAGGED}
assert all(m[1] >= 0 for m in MARGIN.values()) and min(m[1] for m in MARGIN.values()) == 1, MARGIN
assert BOUNDS == {22: (22, 19), 23: (24, 19), 24: (24, 19), 27: (26, 21), 28: (26, 21), 29: (26, 21)}, BOUNDS

# ================= (C) 既有實機紀錄 lc192b =================
assert hashlib.md5(LC192B.read_bytes()).hexdigest() == LC192B_MD5
LOG = cs._read(str(LC192B), calls=True)
assert LOG.calls_parsed and LOG.game_cs == 0x170
EV = []
for c in LOG.calls:
    s, r = c.eip - DELTA, c.ret - DELTA
    if s == SFX and r in (0x2B08F, 0x2B1F6):
        EV.append((c.line, "in" if r == 0x2B08F else "out", c.stack[1], c.regs["edi"], c.regs["ebp"]))
    elif s == DIALOG and c.stack[1] == 0x19A:
        EV.append((c.line, "ask", hex(r), 0, 0))
for k in LOG.keys:
    if k.data in (0x01, 0x53):
        EV.append((k.line, "esc" if k.data == 1 else "del", 0, 0, 0))
EV.sort()
SEQ = [(e[1], e[2], e[3] & 0xFFFFFFFF, e[4]) for e in EV]
assert SEQ == [("ask", "0x262d5", 0, 0), ("in", 5, 0, 0x13), ("in", 5, 0, 0x13), ("esc", 0, 0, 0),
               ("out", 6, 0xFFFFFFFF, 0x13), ("out", 6, 0xFFFFFFFF, 0x13), ("in", 5, 0, 0x13), ("in", 5, 0, 0x13),
               ("out", 6, 1, 0xC), ("out", 6, 1, 0xC)], SEQ
# 0x262d5 是 0x262d0 call 0x15f84 的返回:town_hub_main 的旗標路徑;lc192b 的章節 byte 29 在旗標表裡
assert insn(0x262D0) == "call 0x15f84" and 29 in FLAGGED
# 兩次進入之間沒有城鎮的入口(0x19a 詢問只在第一次之前)
I_OUT1 = SEQ.index(("out", 6, 0xFFFFFFFF, 0x13))
assert all(e[0] != "ask" for e in SEQ[I_OUT1:])

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s193.py"), "exe_md5": MD5, "calllog": {"lc192b": LC192B_MD5},
    "select_exits": {"accept": {"edi": 1, "at": "0x2b0e7", "returns": 1},
                     "cancel": {"edi": -1, "at": "0x2b0b3", "keys": ["Esc 0x01", "Del 0x53 → 0x01(0x2b736)"], "returns": 0}},
    "callers": {"0x26351": {"function": "town_hub_main", "gate": "章節旗標 0x523e7[章節 byte] ≠ 0,不比名冊人數",
                            "on_cancel": "je 0x26347(再叫一次選人)"},
                "0x267e6": {"function": "town_hub_select", "gate": "[0x53bfb] > 0x10(章節 byte > 0x1a 時 > 0x14),不足就略過選人",
                            "on_cancel": "je 0x29867(離開設施)"}},
    "flagged_chapter_bytes": FLAGGED,
    "roster_count_writes": [[hex(a), t] for a, t in WRITES], "join_call_sites": len(JOIN_CALLS),
    "roster_bounds": {str(ch): {"plain": BOUNDS[ch][0], "conservative": BOUNDS[ch][1], "target": TARGET(ch),
                                "selectable_margin": list(MARGIN[ch])} for ch in FLAGGED},
    "lc192b_sequence": [list(e) for e in SEQ],
    "conclusion": "旗標章節(byte 22 / 23 / 24 / 27 / 28 / 29)由 town_hub_main 直接進選人,沒有名冊人數門檻,取消後立刻再進:"
                  "[0x53bfb] − 1 < 目標時無出口(lc192b 的 12 人存檔在 byte 29 即是,只能重開)。名冊人數只增不減,"
                  "正常劇情到這些章節的保守下界都達到門檻,所以只有非正常進度的存檔(改章節 byte、早期合成存檔)會遇到。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, FLAGGED, BOUNDS, MARGIN, SEQ)
