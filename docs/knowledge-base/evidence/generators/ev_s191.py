"""續一百九十一證據(實機):evidence/live_s191_event63_town_gate_20261104.json。

使用者 2026-11-04「open_static 7 項、open_live 2 項 請完整進行驗證及處理」;實機「永遠核准」。原版 FD2.EXE、DOSBox-X(drivers_s191)。
91-worklist 兩個 open_live:
(1) MAP26-EVENT63-E2-PLAYER-PATH —— lc191a:未修改的 ch27 存檔(槽 0)一般玩家路徑。亞雷斯 (14,55) → (26,39) 一次移動 28 步
    (上 16、右 12、左 0),每一步提交都以 selector 0 呼叫 0x13a44(新 x, 新 y, 0),返回位址全是 0x1317a:四個方向的步函式
    都落到同一段共用尾端(doc25「只有向左步」錯,pred191.txt Q1 FAIL)。0x13a44 只把 event id 寫進 [0x51a8f],行動結束後
    輸入迴圈 0x1199c 才 dispatch → event62 0x35bee 一次(參數 = 單位 2);live row0 回合 byte 255 → 2、evstate[0x11] 0 → 1。
    第 1 回合敵方階段 0x1a813(0) 不呼叫 event63;第 2 回合敵方階段 0x1a813(0) 之內(返回 0x1a861)、敵軍 AI 0x1d8ba 之前
    呼叫 0x35c1d 一次:0x35b78(3,27,1) 再 (15,27,2),各自 0x135dd → 0x10b4e → 0x3790a(300) → 0x11df2(0,255,255)
    → 0x3790a(200) → 0x11df2(0,255,0) → 0x11cac(0) → 0x3790a(400);模擬時間 300 / 200 / 400 ms 各在 ±60 ms 內。
    單位表 63 → 75 筆;新增 12 人不在 (3,27) / (15,27)(那是鏡頭座標),pred191b R5 的寫法 FAIL。
(2) UI-VIS-TOWN secret gate —— lc191b:ch03 hub,K 紀錄(guest 鍵盤控制器收到的 scan code)證明 xdotool 的 ctrl+F1 進得去
    (01d 03b,AH 0x5E)、單送 F2 進得去(03c,AH 0x3C),但 ctrl+F2 只有 01d、沒有 03c(window / xtest 兩種送法一樣),
    ctrl+F5 也只有 01d、沒有 03f。lc191c:帶只列 7 個事件的 mapper 檔 → 整場沒有任何 K(mapper 檔讀得到就不建預設綁定)。
    lc191d / lc191e:以 debugger 在 BIOS 鍵盤緩衝(BDA 0x41e..)放 0x5F00 / 0x6200,INT 16h 讀到的值與真按鍵相同:
    ch03 sel 1 → AH 0x5F、sel 5、標籤 FDTXT 0x1f4「？？？」;ch06 sel 4 → AH 0x62、sel 5;對照(錯章 / 錯 selection)sel 不變。
    gate 在遊戲端沒有其他前置條件;之前不觸發是 host 端(DOSBox-X 預設 Ctrl+F2 = ejectpage、Ctrl+F5 = copyall)吃掉了鍵。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct

from _evpaths import GAME, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, _META, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402
import unpack_dat  # noqa: E402

OUT = out_path("live_s191_event63_town_gate_20261104.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
RAW = ROOT / ".wsl_build/lc191_live"
CL = RAW / "cl"
CALLLOGS = {"lc191a": "f5e060d46ba0598d6912c7472eb8fc82", "lc191b": "06ecabbc345421546124d228831c22a8",
            "lc191c": "e855b8e29b161bb465106950f6c4bfbe", "lc191d": "3063cd50768ca91f40df2c20dd1f7a6f",
            "lc191e": "c2387a3a149257bc75300600f9c9da97"}
NAMES = ROOT / "docs/data/function_names.json"
FIELD_EVENT, STEP_TAIL_RET = 0x13A44, 0x1317A
STEPS = {0x12EAA: "down", 0x1300D: "left", 0x13185: "up", 0x13315: "right"}
DIR = {"down": (0, 1), "left": (-1, 0), "up": (0, -1), "right": (1, 0)}
PATH, EV62, EV63, STAGING, PAN, SPAWN, DELAY, PALETTE, REDRAW = (0x13488, 0x35BEE, 0x35C1D, 0x35B78, 0x135DD,
                                                                 0x10B4E, 0x3790A, 0x11DF2, 0x11CAC)
CAMP_SCAN, ENEMY_AI = 0x1A813, 0x1D8BA
TOL_MS = 60                                  # 一個 BIOS tick 約 55 ms

assert hashlib.md5(_EXE).hexdigest() == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
assert _NM[EV62] == "event_handler_62" and _NM[EV63] == "event_handler_63", (_NM[EV62], _NM[EV63])
_FX = dl.build_fixups(_EXE, _META)

# ================= (A) 靜態 =================
# 四個方向的步函式都到 0x13175 呼叫 0x13a44(x, y, 0):下 0x12fea inc y → 0x12ff0 → 0x13008 jmp 0x13167;上 0x1330a dec y
# → 0x13310 jmp 0x12ff0;右 0x13455 inc x → 0x1345b jmp 0x1314f;左 0x13149 dec x 直接落下
assert [insn(a) for a in (0x134C2, 0x134C8, 0x134CF, 0x134D5, 0x134DD, 0x134B8)] == [
    "cmp eax, 1", "call 0x1300d", "cmp eax, 2", "call 0x13185", "call 0x13315", "call 0x12eaa"]
assert [insn(a) for a in (0x12FEA, 0x13008, 0x1330A, 0x13310, 0x13455, 0x1345B, 0x13149)] == [
    "inc dword ptr [0x3ab5]", "jmp 0x13167", "dec dword ptr [0x3ab5]", "jmp 0x12ff0",
    "inc dword ptr [0x3ab1]", "jmp 0x1314f", "dec dword ptr [0x3ab1]"]
assert [insn(a) for a in (0x13167, 0x13169, 0x1316F, 0x13175)] == [
    "push 0", "push dword ptr [0x3ab5]", "push dword ptr [0x3ab1]", "call 0x13a44"]
assert STEP_TAIL_RET == 0x13175 + 5
# 0x13a44 只寫 [0x51a8f];player 路徑在輸入迴圈行動結束後 dispatch,選取時清成 0xff
assert _FX[0x1198A + 2] == _FX[0x13A95 + 2] == _FX[0x188BD + 2] == 0x51A8F
assert insn(0x1199C) == "call dword ptr [eax*4 + 0x1b91]" and _FX[0x1199C + 3] == 0x51B91
assert insn(0x188BD) == "mov dword ptr [0x1a8f], 0xff"
# event62 / event63 / 0x35b78
assert [insn(a) for a in (0x35BFD, 0x35C03, 0x35C09, 0x35C10, 0x35C18)] == [
    "cmp byte ptr [eax + 0x11], 0", "mov dl, byte ptr [0x3bef]", "inc dl", "mov byte ptr [eax + 3], dl",
    "mov byte ptr [eax + 0x11], 1"]
STAGE1 = (operand(0x35C2B, "push "), operand(0x35C29, "push "), operand(0x35C27, "push "))
STAGE2 = (operand(0x35C39, "push "), operand(0x35C37, "push "), operand(0x35C35, "push "))
assert insn(0x35C2D) == "call 0x35b78" and insn(0x35C3B) == "jmp 0x3566e" and insn(0x3566E) == "call 0x35b78"
assert (STAGE1, STAGE2) == ((3, 27, 1), (15, 27, 2)), (STAGE1, STAGE2)
D_SPAWN, D_WHITE, D_TAIL = operand(0x35BA0, "push "), operand(0x35BC1, "push "), operand(0x35722, "push ")
assert [insn(a) for a in (0x35B8A, 0x35B98, 0x35BA5, 0x35BB9, 0x35BC6, 0x35BD7, 0x35BE1, 0x35BE9, 0x35727)] == [
    "call 0x135dd", "call 0x10b4e", "call 0x3790a", "call 0x11df2", "call 0x3790a", "call 0x11df2", "call 0x11cac",
    "jmp 0x35722", "call 0x3790a"]
assert (D_SPAWN, D_WHITE, D_TAIL) == (300, 200, 400)
# 敵方階段:0x1a554 呼叫 0x1a813(0) → 0x1a58f 敵軍 AI → 0x1a5b9 回合 + 1;0x1a813 以 0x51b91 dispatch
assert [insn(a) for a in (0x1A552, 0x1A554, 0x1A58F, 0x1A5B9, 0x1A85A)] == [
    "push 0", "call 0x1a813", "call 0x1d8ba", "inc dword ptr [0x3bef]", "call dword ptr [eax*4 + 0x1b91]"]

# map26 的格子事件:FDFIELD 第 3N+1 個資源(控制段)field row、構成(3N)每格 word1 低 5 位、FDSHAP 2N+1 地形 byte0
MAP = 26
_fd = (GAME / "FDFIELD.DAT").read_bytes()
_sh = (GAME / "FDSHAP.DAT").read_bytes()
_dfd, _dsh = unpack_dat.parse_directory(_fd), unpack_dat.parse_directory(_sh)


def _res(data: bytes, d: list, i: int) -> bytes:
    o, n = d[i]
    return data[o:o + n]


COMP, CTRL, TERR = _res(_fd, _dfd, 3 * MAP), _res(_fd, _dfd, 3 * MAP + 1), _res(_sh, _dsh, 2 * MAP + 1)
W, H = struct.unpack_from("<HH", COMP, 0)
TURN_ROWS = [tuple(CTRL[3 + 3 * s:6 + 3 * s]) for s in range(16)]
FIELD_ROWS = [tuple(CTRL[0x33 + 2 * s:0x35 + 2 * s]) for s in range(16)]
assert TURN_ROWS[0] == (0xFF, 63, 0) and FIELD_ROWS[0] == (62, 0), (TURN_ROWS[0], FIELD_ROWS[0])
EV62_CELLS = []
for c in range(W * H):
    tile, word = struct.unpack_from("<HH", COMP, 4 + 4 * c)
    slot = word & 0x1F
    if slot == 1 and TERR[(tile & 0x3FF) * 4] & 0x60 == 0:     # 0x13a64 地形 & 0x60 == 0 才是格子事件
        EV62_CELLS.append((c % W, c // W))
assert (W, H) == (31, 57) and EV62_CELLS == [(x, 39) for x in range(W)], EV62_CELLS[:4]

# ================= (B) lc191a =================
def calllog(name: str) -> cs.Log:
    p = RAW / f"{name}_CALLLOG.TXT"
    assert hashlib.md5(p.read_bytes()).hexdigest() == CALLLOGS[name], name
    return cs._read(str(p), calls=True)


def blob(name: str, label: str) -> bytes:
    return (CL / name / f"{label}.bin").read_bytes()


def state(name: str, label: str) -> dict:
    return json.loads((CL / name / f"{label}.json").read_text(encoding="utf-8"))


LA = calllog("lc191a")
assert LA.calls_parsed and LA.game_cs == 0x170
E = [c for c in LA.calls if not c.ret_bad]
st = lambda c: c.eip - DELTA                 # noqa: E731
rt = lambda c: c.ret - DELTA                 # noqa: E731
t_ret = lambda c: LA.rets[c.seq].ic[2]       # noqa: E731
t_in = lambda c: c.ic[2]                     # noqa: E731
ev62 = [c for c in E if st(c) == EV62]
ev63 = [c for c in E if st(c) == EV63]
assert len(ev62) == 1 and len(ev63) == 1, (len(ev62), len(ev63))
E62, E63 = ev62[0], ev63[0]
# 那一次移動:event62 之前最後一個 0x13488,參數 = 單位 2;到 event62 之間的每一步
paths = [c for c in E if st(c) == PATH and c.seq < E62.seq]
P = paths[-1]
assert P.stack[0] == 2 and E62.stack[0] == 2 and rt(E62) == 0x1199C + 7, (P.stack[0], E62.stack[0], hex(rt(E62)))
seg = [c for c in E if P.seq < c.seq < E62.seq]
steps = [STEPS[st(c)] for c in seg if st(c) in STEPS]
fe = [c for c in seg if st(c) == FIELD_EVENT and rt(c) == STEP_TAIL_RET]
# 其他 0x13a44:行動結束(指令環 ↓)時 0x18890 內 0x18b0c 那一次,selector 1
OTHER_FE = [(hex(rt(c)), tuple(c.stack[:3])) for c in seg if st(c) == FIELD_EVENT and rt(c) != STEP_TAIL_RET]
assert len(fe) == len(steps) == 28 and OTHER_FE == [(hex(0x18B0C + 5), (26, 39, 1))], (len(fe), len(steps), OTHER_FE)
_s01 = state("lc191a", "s00")
START = tuple(next(u["xy"] for u in _s01["units"] if u["i"] == 2))
pos, walk = START, []
for d, c in zip(steps, fe):
    pos = (pos[0] + DIR[d][0], pos[1] + DIR[d][1])
    assert (c.stack[0], c.stack[1], c.stack[2]) == (pos[0], pos[1], 0), (d, pos, c.stack[:3])
    walk.append(pos)
STEP_COUNT = {d: steps.count(d) for d in DIR}
assert START == (14, 55) and pos == (26, 39) and STEP_COUNT == {"down": 0, "left": 0, "up": 16, "right": 12}, STEP_COUNT
assert [p for p in walk if p[1] == 39] == [(26, 39)]           # 只有最後一步落在 y = 39,而且是向上步
# 行動結束前後的 live 狀態(debugger 讀):s01 移動後、休息前;s02 休息後
RB = lambda name, lab: blob("lc191a", f"{lab}_{name}")         # noqa: E731
for lab, ev11, turn0 in (("s01", 0, 0xFF), ("s02", 1, 2)):
    rows, evs, rnd = RB("rows", lab), RB("evstate", lab), RB("round", lab)
    assert (evs[0x11], rows[3], rows[4], rows[5], int.from_bytes(rnd, "little")) == (ev11, turn0, 63, 0, 1), lab
# 第 1 / 第 2 回合敵方階段:每一個 ret 0x1a559 的 0x1a813(0) 與它之後第一個敵軍 AI
scans = [c for c in E if st(c) == CAMP_SCAN and rt(c) == 0x1A554 + 5 and c.seq > E62.seq]
ais = [c for c in E if st(c) == ENEMY_AI and rt(c) == 0x1A58F + 5]
phases = []
for sc in scans:
    ai = min((a for a in ais if a.seq > sc.seq), key=lambda a: a.seq)
    phases.append({"scan_seq": sc.seq, "ai_seq": ai.seq, "ev63_inside": sc.seq < E63.seq < ai.seq})
assert len(phases) >= 2 and [p["ev63_inside"] for p in phases[:2]] == [False, True], phases
assert rt(E63) == 0x1A85A + 7 and E63.stack[0] == 0
# event63 之內
inner = [c for c in E if E63.seq < c.seq < phases[1]["ai_seq"] and st(c) in (STAGING, PAN, SPAWN, DELAY, PALETTE)]
SEQ = [(st(c), rt(c), tuple(c.stack[:3]) if st(c) in (STAGING, PALETTE) else tuple(c.stack[:2]) if st(c) == PAN
        else (c.stack[0],)) for c in inner]
EXPECT = []
for (x, y, g), r_stage in ((STAGE1, 0x35C32), (STAGE2, 0x35673)):
    EXPECT += [(STAGING, r_stage, (x, y, g)), (PAN, 0x35B8F, (x, y)), (SPAWN, 0x35B9D, (g,)), (DELAY, 0x35BAA, (D_SPAWN,)),
               (PALETTE, 0x35BBE, (0, 0xFF, 0xFF)), (DELAY, 0x35BCB, (D_WHITE,)), (PALETTE, 0x35BDC, (0, 0xFF, 0)),
               (DELAY, 0x3572C, (D_TAIL,))]
assert SEQ == EXPECT, SEQ
redraws = [c for c in E if E63.seq < c.seq < phases[1]["ai_seq"] and st(c) == REDRAW and rt(c) == 0x35BE6]
assert len(redraws) == 2 and all(c.stack[0] == 0 for c in redraws)
TIMING = []
for k in (0, 8):
    sp, d300, w, d200, rs, d400 = inner[k + 2], inner[k + 3], inner[k + 4], inner[k + 5], inner[k + 6], inner[k + 7]
    TIMING.append({"spawn_ret_to_white_in_ms": round(t_in(w) - t_ret(sp), 3), "delay300_ms": round(t_ret(d300) - t_in(d300), 3),
                   "white_to_restore_in_ms": round(t_in(rs) - t_ret(w), 3), "delay200_ms": round(t_ret(d200) - t_in(d200), 3),
                   "delay400_ms": round(t_ret(d400) - t_in(d400), 3)})
for tm in TIMING:
    assert abs(tm["delay300_ms"] - D_SPAWN) <= TOL_MS and abs(tm["spawn_ret_to_white_in_ms"] - D_SPAWN) <= TOL_MS, tm
    assert abs(tm["delay200_ms"] - D_WHITE) <= TOL_MS and abs(tm["white_to_restore_in_ms"] - D_WHITE) <= TOL_MS, tm
    assert abs(tm["delay400_ms"] - D_TAIL) <= TOL_MS, tm
# 單位表:s04(第 2 回合玩家階段)63 筆 → s06(event63 之後)75 筆;新增者的出場位置(已被 AI 移動的,由第一步回推)
S04, S06 = state("lc191a", "s04"), state("lc191a", "s06")
assert (S04["round"], S04["unit_count"], S06["unit_count"]) == (2, 63, 75)
NEW = {u["i"]: tuple(u["xy"]) for u in S06["units"] if u["i"] >= S04["unit_count"]}
assert sorted(NEW) == list(range(63, 75))
SPAWN_XY = {}                                # 每個新單位 event63 之後第一次移動的起點(第一步座標減該步方向)
for p in (c for c in E if st(c) == PATH and c.seq > E63.seq and c.stack[0] in NEW):
    if p.stack[0] in SPAWN_XY:
        continue
    first_step = next(c for c in E if c.seq > p.seq and st(c) in STEPS)
    first_fe = next(c for c in E if c.seq > first_step.seq and st(c) == FIELD_EVENT)
    d = DIR[STEPS[st(first_step)]]
    SPAWN_XY[p.stack[0]] = (first_fe.stack[0] - d[0], first_fe.stack[1] - d[1])
# 12 人之後都移動過;每人回推的起點 = s06(debugger 讀)的位置(兩個來源互相核對),所以 s06 讀到的是出場位置
assert sorted(SPAWN_XY) == sorted(NEW)
STILL = sorted(i for i in NEW if NEW[i] == SPAWN_XY[i])
assert STILL == list(range(63, 75)), STILL
G1 = [SPAWN_XY[i] for i in range(63, 69)]
G2 = [SPAWN_XY[i] for i in range(69, 75)]
assert all(7 <= x <= 10 and 29 <= y <= 32 for x, y in G1) and all(20 <= x <= 23 and 29 <= y <= 32 for x, y in G2), (G1, G2)
assert (3, 27) not in SPAWN_XY.values() and (15, 27) not in SPAWN_XY.values()
# R6 沒有走成:lc191a 的紀錄在第 3 回合玩家階段(最後一個 E 0x117e7)之後沒有新的 0x13488 / 0x35bee
last_input = max(c.seq for c in LA.calls if st(c) == 0x117E7)
assert not any(st(c) in (PATH, EV62) and c.seq > last_input for c in LA.calls)

# ================= (C) town secret gate =================
TOWN = 0x6238D
assert _FX[0x4E817 + 2] == TOWN and insn(0x4E817) == "lea edx, [0x238d]" and insn(0x4E80F) == "dec eax" and insn(0x4E810) == "mov edx, 0x1f"
ROW = lambda ch: bytes(dl.object_bytes(_EXE, _META, TOWN + 0x1F * (ch - 1), 3))   # noqa: E731
assert ROW(2)[1:] == bytes([1, 0x5F]) and ROW(5)[1:] == bytes([4, 0x62]), (ROW(2).hex(), ROW(5).hex())
assert [insn(a) for a in (0x2648D, 0x2655E, 0x26562, 0x26566, 0x2656A, 0x26572)] == [
    "mov byte ptr [0x3a8e], 0x10", "movzx ebx, byte ptr [eax + 2]", "cmp edx, ebx", "movzx eax, byte ptr [eax + 1]",
    "cmp eax, dword ptr [0x3f4a]", "mov dword ptr [0x3f4a], 5"]


def makes(log: cs.Log) -> list[int]:
    """K 紀錄的 make code(break = data | 0x80 的不算;0x38 = 進 debugger 的 Alt)。"""
    return [k.data for k in log.keys if k.data < 0x80 and k.data != 0x38]


TS = {}
for name, labels in (("lc191b", ("ts00", "ts01", "ts02", "ts03", "ts04", "ts05", "ts06")),
                     ("lc191d", ("td00", "td01", "td02")), ("lc191e", ("te00", "te01", "te02", "te03"))):
    for lab in labels:
        TS[lab] = state(name, lab)
pick = lambda lab: (TS[lab]["chapter_byte"], TS[lab]["ah"], TS[lab]["sel"])   # noqa: E731
LB = calllog("lc191b")
MB = makes(LB)
# lc191b 送鍵順序:poll_title 的 Return ×6、Down Return Return(LOAD)、ctrl+F1、Left、ctrl+F2(window)、ctrl+F2(xtest)、F2、ctrl+F5
# —— 兩次 ctrl+F2 與 ctrl+F5 都只有 Ctrl(0x1d),F2(0x3c)/ F5(0x3f)沒進 guest;單送的 F2 進得去


def after_title(ms: list[int]) -> list[int]:
    """去掉 poll_title 跳片頭的 Return(次數每次不同)到第一個 Down 為止。"""
    i = ms.index(0x50)
    assert i > 0 and set(ms[:i]) == {0x1C}, ms[:i]
    return ms[i:]


assert after_title(MB) == [0x50, 0x1C, 0x1C, 0x1D, 0x3B, 0x4B, 0x1D, 0x1D, 0x3C, 0x1D], [hex(x) for x in MB]
assert 0x3F not in MB
assert [pick(x) for x in ("ts00", "ts01", "ts02", "ts03", "ts04", "ts05", "ts06")] == [
    (2, 0x1C, 0), (2, 0x5E, 0), (2, 0x4B, 1), (2, 0x4B, 1), (2, 0x4B, 1), (2, 0x3C, 1), (2, 0x3C, 1)]
LC = calllog("lc191c")
assert LC.keys == [] and not (CL / "lc191c" / "tc00.json").exists()
LD, LE = calllog("lc191d"), calllog("lc191e")
assert after_title(makes(LD)) == [0x50, 0x1C, 0x1C, 0x4B] and after_title(makes(LE)) == [0x50, 0x1C, 0x1C, 0x4D]
assert [pick(x) for x in ("td00", "td01", "td02")] == [(2, 0x4B, 1), (2, 0x5F, 5), (2, 0x62, 5)]
assert [pick(x) for x in ("te00", "te01", "te02", "te03")] == [(5, 0x1C, 0), (5, 0x62, 0), (5, 0x4D, 4), (5, 0x62, 5)]
INJECTS = []
for name in ("lc191d", "lc191e"):
    for ln in (CL / f"{name}_keys.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if r["op"] == "inject":
            assert r["readback_ok"] and r["head"] == r["tail"], r
            INJECTS.append({"instance": name, "label": r["label"], "word": r["word"]})
assert [(x["instance"], x["word"]) for x in INJECTS] == [("lc191d", "0x5f00"), ("lc191d", "0x6200"),
                                                          ("lc191e", "0x6200"), ("lc191e", "0x6200")]


def label_box(name: str, shot: str) -> list[str]:
    t = json.loads((CL / name / f"{shot}.text.json").read_text(encoding="utf-8"))
    return [b["string_hex"] for b in t["boxes"] if b["complete"] and b["file"] == "FDTXT_000.bin" and
            int(b["string_hex"], 16) >= 0x1EF]


assert label_box("lc191b", "b05_ctrlf2") == ["0x1f0"] and label_box("lc191d", "d04_after_inject") == ["0x1f4"]
assert label_box("lc191e", "e03_right") == ["0x1f3"] and label_box("lc191e", "e04_after") == ["0x1f4"]

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s191.py"), "exe_md5": MD5, "calllogs_md5": CALLLOGS,
    "event63": {
        "static": {"ev62_cells_map26": f"y = 39, x 0..{W - 1}({len(EV62_CELLS)} 格)", "turn_row0": list(TURN_ROWS[0]),
                   "step_tail_call": "0x13175(四個方向共用)", "dispatch": "0x1199c([0x51a8f])",
                   "staging": [list(STAGE1), list(STAGE2)], "delays_ms": [D_SPAWN, D_WHITE, D_TAIL]},
        "move": {"unit": 2, "from": list(START), "to": list(pos), "steps": STEP_COUNT, "field_event_calls": len(fe),
                 "field_event_ret": hex(STEP_TAIL_RET)},
        "ev62": {"seq": E62.seq, "ret": hex(rt(E62)), "arg_unit": E62.stack[0],
                 "row0_turn_before_after": [0xFF, 2], "evstate_0x11_before_after": [0, 1], "round": 1},
        "enemy_phases": phases[:2], "ev63": {"seq": E63.seq, "ret": hex(rt(E63))},
        "ev63_sequence": [[hex(a), hex(r), list(args)] for a, r, args in SEQ], "timing_ms": TIMING,
        "units_before_after": [S04["unit_count"], S06["unit_count"]],
        "spawn_xy": {str(k): list(v) for k, v in sorted(SPAWN_XY.items())},
        "pred191": "Q1 FAIL(前提「只有向左步」錯),其餘由 pred191b 取代",
        "pred191b": {"R1": "PASS", "R2": "PASS", "R3": "PASS", "R4": "PASS(另多 0x35722 的 0x3790a(400),未預測)",
                     "R5": "FAIL(出場位置不是 (3,27) / (15,27),那是 0x135dd 的鏡頭座標)", "R6": "NOT TESTED"}},
    "town_gate": {
        "table_rows": {"ch03": ROW(2).hex(), "ch06": ROW(5).hex()}, "lc191b_make_codes_after_title": [hex(x) for x in after_title(MB)],
        "tstate": {k: pick(k) for k in TS}, "injects": INJECTS,
        "pred191c": {"T1": "PASS", "T2": "PASS", "T3": "FAIL(K 只有 01d,沒有 03c)", "T5": "FAIL(xtest 同樣)",
                     "T6": "PASS", "T7": "K 只有 01d,沒有 03f", "T8": "作廢(mapper 檔讓所有鍵失效)", "T10": "PASS", "T11": "PASS",
                     "T12": "PASS"}},
    "conclusion": "event62 → event63 在未修改的 ch27 玩家路徑完整發生:y = 39 的任何一步(本次是向上步)寫入 [0x51a8f],行動結束 dispatch "
                  "event62;下一回合敵方階段、敵軍 AI 之前 event63 兩輪增援與白閃,時序 300 / 200 / 400 ms 吻合。town secret gate 在 ch03 / ch06 "
                  "遊戲端正常(BIOS 緩衝放 0x5F00 / 0x6200 即揭示);xdotool 的 ctrl+F2 / ctrl+F5 被 DOSBox-X host 綁定吃掉。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, STEP_COUNT, TIMING, phases[:2], [hex(x) for x in MB])
