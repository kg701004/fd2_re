"""續一百八十六證據:evidence/ai_chest_grab_live_s186_20261102.json(實機 lc186a;預測 drivers_s186/pred186.txt)。

使用者 2026-11-02「請進行實機確認」:續一百八十五仍留 —— 第 10 張圖(第 11 章)盜賊搶寶箱時 ai_mode_dispatch 那處放 0xc。
lc186a:測試存檔 slot 0 章節改 10 → LOAD → 城鎮出口 → 戰前對話 → 第 10 張圖戰場;我方不動、結束 4 個回合。
呼叫紀錄入口全部 1356 個(CAP 3000、DUMP 32,不開觸發擷取);全域、單位表、開箱旗標在敵方回合之後以 debugger 讀出(不改記憶體)。
Q1 0xc 是否在 ai_mode_dispatch 裡、經過預測的三道關;Q2 搶到之後單位與旗標的狀態;Q3 誰先搶(只記錄)。
另:[0x53ad5] 的值就是執行期線性位址(續一百八十五任務外發現第二點的更正)、第 10 張圖記錄 0 的己方以外單位排在表尾。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import collections
import hashlib
import json

from _evpaths import EVIDENCE, GEN_DIR, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, insn  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import parse_field  # noqa: E402

OUT = out_path("ai_chest_grab_live_s186_20261102.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
RAW = ROOT / ".wsl_build/lc186_live"
DRV = GEN_DIR / "drivers_s186"
PRED = DRV / "pred186.txt"
NAMES = ROOT / "docs/data/function_names.json"
FLD_RAW = ROOT / "extracted/raw"
OPEN5 = ROOT / ".wsl_build/chapter_sweep_ch11chest/real_open5.py"
S185 = json.loads((EVIDENCE / "ai_chest_grab_0xc_s185_20261102.json").read_text(encoding="utf-8"))
LOG = "lc186a"
LOG_MD5 = "86f4fa18d310c54d6146b9ece5a573dd"   # teardown 之後的指紋(lc186.py down 印出)
CAP = 3000
MAP = 10
STRIDE = 0x50
PLAY_A, PLAY_B = 0x25A96, 0x25B45
# 當下讀出的記憶體(lc186.py mem / flags):全域 0170:0x1efa40 起 0x200(= native 0x53a40 起)、單位表 38 筆、開箱旗標 0x20
# f00_flags 是第一版 flags 把指標值再加 DELTA 讀到的 0x392c5c,作廢不用(見 drivers_s186/README.md)
DUMPS = {"m00_globals": "cf4bc9775745acd4fdc5eea6a4ee3e0f", "m04_globals": "9adfe9840e6e7206d35eee95f67491a8",
         "f01_flags": "70bc8f4b72a86921468bf8e8441dce51", "f02_flags": "0bfa0a11aa2b7a1801f7bab0bf2d3df3",
         "f03_flags": "0bfa0a11aa2b7a1801f7bab0bf2d3df3", "f04_flags": "6626c1204cc18dd736629eb55d08f693",
         "u02_units": "6fb0d01da55aeb8b128357eb5560b787", "u04_units": "d7a75d4f3846da1fdff58cff51abb77b"}
# 每份讀出是在第幾個敵方回合結束之後(0 = 第一次結束回合之前)
AFTER_TURN = {"m00_globals": 0, "f01_flags": 0, "f02_flags": 2, "u02_units": 2, "f03_flags": 3,
              "f04_flags": 4, "u04_units": 4, "m04_globals": 4}
GLOBALS_LIN = 0x53A40
PTR_UNITS, PTR_OPENED, CNT_UNITS, CHAPTER = 0x53A45, 0x53AD5, 0x53BEB, 0x53C03

assert hashlib.md5(_EXE).hexdigest() == MD5
_NM = {int(r["addr"], 16): r["name"] for r in json.loads(NAMES.read_text(encoding="utf-8"))["names"]}
_BY = {v: k for k, v in _NM.items()}
DISPATCH, FIND, CHOOSE, MOVE, ADD_ITEM = (_BY[n] for n in ("ai_mode_dispatch", "find_event_cell", "ai_choose_action",
                                                           "move_unit_toward_point", "unit_add_item"))
ENEMY_PHASE, FRIENDLY_PHASE = _BY["enemy_phase_dispatch"], _BY["friendly_phase_dispatch"]
_P0C = {x["func"]: int(x["call"], 16) for x in S185["plays_0xc"]}
R_AI, R_CHEST = _P0C["ai_mode_dispatch"] + 5, _P0C["field_cell_treasure_check"] + 5
assert insn(R_AI - 5) == f"call {PLAY_B:#x}" and insn(R_CHEST - 5) == f"call {PLAY_B:#x}"
# 已開旗標:mov eax, [0x3ad5] → movzx eax, byte [eax + ebp]:遊戲把指標值直接當位址用(續一百八十五 GATES)
_G = {int(x["addr"], 16): x["insn"] for x in S185["mode5_gates"]}
assert _G[0x13C42] == "mov eax, dword ptr [0x3ad5]" and _G[0x13C47] == "movzx eax, byte ptr [eax + ebp]"
_drv = (DRV / "lc186.py").read_text(encoding="utf-8")
assert f'"FD2_HARNESS_CALLLOG_CAP"] = "{CAP}"' in _drv and '"FD2_HARNESS_CALLLOG_TRIG", ' in _drv
assert "第 10 張圖" in PRED.read_text(encoding="utf-8")


def blob(label: str) -> bytes:
    b = (RAW / "cl" / LOG / f"{label}.bin").read_bytes()
    assert hashlib.md5(b).hexdigest() == DUMPS[label], label
    return b


def g32(gb: bytes, a: int) -> int:
    return int.from_bytes(gb[a - GLOBALS_LIN:a - GLOBALS_LIN + 4], "little")


# ================= 全域(戰場開始時與第 4 個敵方回合後) =================
GL = {k: blob(k) for k in ("m00_globals", "m04_globals")}
UNIT_BASE, OPENED, N_UNITS = g32(GL["m00_globals"], PTR_UNITS), g32(GL["m00_globals"], PTR_OPENED), \
    GL["m00_globals"][CNT_UNITS - GLOBALS_LIN]
for gb in GL.values():
    assert (g32(gb, PTR_UNITS), g32(gb, PTR_OPENED), gb[CNT_UNITS - GLOBALS_LIN]) == (UNIT_BASE, OPENED, N_UNITS)
    assert gb[CHAPTER - GLOBALS_LIN] == MAP                  # 即時章節值 == 10(doc25 §3.2 的 INFERRED 這次直接讀到)

# ================= FDFIELD 第 10 張圖與當下單位表 =================
INFO = parse_field.parse_map(str(FLD_RAW), MAP)
OWN = INFO["own_deploy"]
REC = INFO["units"]
CHESTS = {c["slot"]: c for c in INFO["chests"]}
G0 = [k for k, u in enumerate(REC) if u["group"] == 0]           # 建構時就出場的記錄
M5 = [k for k in G0 if REC[k]["native_record_byte34"] & 0xF == 5]
# 記錄 1 .. 25 是 group 0、模式 5 的盜賊;記錄 0(+6 == 1、group 1)在戰前對話裡加到表尾 → 表上 = 己方 + 25 + 1
assert G0 == M5 == list(range(1, len(G0) + 1)), (G0, M5)
assert (REC[0]["group"], REC[0]["native_record_byte6"]) == (1, 1)
assert N_UNITS == OWN + len(G0) + 1 < OWN + len(REC)
TARGET = {r["record"]: tuple(r["target"]) for r in S185["mode5_records"] if r["map"] == MAP}
assert sorted(TARGET) == M5
UNITS = {k: blob(k) for k in ("u02_units", "u04_units")}
assert all(len(b) == (N_UNITS - 1) * STRIDE for b in UNITS.values())


def unit(b: bytes, i: int) -> bytes:
    return b[i * STRIDE:(i + 1) * STRIDE]


# 當下表上:單位 OWN .. OWN + 24 依序是記錄 1 .. 25(+6 / +7 / +0x3d 對上記錄),記錄 0 排在表尾(單位 N_UNITS - 1)
REC_OF = {}
for i in range(OWN, N_UNITS - 1):
    r = i - OWN + 1
    u, rec = unit(UNITS["u02_units"], i), REC[r]
    assert (u[6], u[7], u[0x3D]) == (rec["native_record_byte6"], rec["raw_unit_key"], rec["native_record_byte3d"]), (i, r)
    REC_OF[i] = r
assert all(unit(UNITS["u02_units"], i)[6] == 2 for i in range(OWN))
# 續一百八十五 JSON 的 "unit" 欄原本(己方出場數 + 記錄序號)在第 10 張圖差 1;續一百八十七改由 spawn_group(0) 的
# group 0 名次算,與當下表上一致(差 0)
S185_UNIT = {r["record"]: r["unit"] for r in S185["mode5_records"] if r["map"] == MAP}
S185_OFF = 0
assert all(S185_UNIT[r] == i + S185_OFF for i, r in REC_OF.items())
EV = {i: unit(UNITS["u02_units"], i)[0x3D] for i in REC_OF}

# ================= 呼叫紀錄 =================
p = RAW / f"{LOG}_CALLLOG.TXT"
assert hashlib.md5(p.read_bytes()).hexdigest() == LOG_MD5
head = p.open(encoding="ascii").readline()
assert head.startswith("H fd2calllog 1 ") and " entries=1356 " in head and f" cap={CAP} " in head and " dump=32 " in head, head
assert " trig=" not in head and " kbd=1" in head, head
lg = cs._read(str(p), calls=True)
CNT = collections.Counter(c.eip - DELTA for c in lg.calls)
# 這幾個入口沒記滿(記滿之後看不到);map_cell_info 記滿是預期的(find_event_cell 每次掃全圖)
for a in (DISPATCH, FIND, CHOOSE, MOVE, ADD_ITEM, ENEMY_PHASE, FRIENDLY_PHASE, PLAY_A, PLAY_B):
    assert CNT[a] < CAP, (hex(a), CNT[a])


def span(c: cs.Call) -> tuple[int, int]:
    r = lg.rets[c.seq]
    assert r.kind == "R", c.seq
    return c.line, r.line


def caller(c: cs.Call) -> int:
    return max(k for k in _NM if k <= c.ret - DELTA)


PHASES = [c for c in lg.calls if c.eip - DELTA == ENEMY_PHASE]
PH_SPANS = [span(c) for c in PHASES]
DISP = [c for c in lg.calls if c.eip - DELTA == DISPATCH]
assert {caller(c) for c in DISP} == {ENEMY_PHASE, FRIENDLY_PHASE}
FR = [c for c in DISP if caller(c) == FRIENDLY_PHASE]
EN = [c for c in DISP if caller(c) == ENEMY_PHASE]
# 己方以外的那個單位每回合一次,單位指標在 ebx = 表尾;ebx 傾印 +6 / +7 / +8 = 記錄 0 的 +6 / b1(group 1 的那一筆)
R0_UNIT = N_UNITS - 1
U_LAST = UNIT_BASE + R0_UNIT * STRIDE
assert len(FR) == len(PHASES) and {c.regs["ebx"] for c in FR} == {U_LAST}
assert all(tuple(c.mem["ebx"][6:9]) == (1, REC[0]["raw_unit_key"], REC[0]["raw_unit_key"]) for c in FR)
# 它在第一次進我方輸入迴圈之前就已在表上(戰前對話期間加入)
_first = next(c for c in lg.calls if U_LAST in c.regs.values() or U_LAST in c.stack)
_loop0 = next(c for c in lg.calls if c.eip - DELTA == _BY["battle_main_input_loop"])
assert _first.line < _loop0.line < PHASES[0].line
LAST_FIRST = {"seq": _first.seq, "func": _NM.get(_first.eip - DELTA), "ret_in": _NM[caller(_first)]}
plays = [c for c in lg.calls if c.eip - DELTA in (PLAY_A, PLAY_B)]
assert not [q for q in plays if q.ret - DELTA == R_CHEST]        # P1c:我方沒有開寶箱
P0C = [q for q in plays if q.stack[1] == 0xC]

TURN_FIND, GRABS, CHECKED = [], [], 0
opened, grabbed = set(), set()
for t, (lo, hi) in enumerate(PH_SPANS, 1):
    disp = [c for c in EN if lo < c.line < hi]
    # 每個敵方回合,25 個盜賊各一次;esi = 單位序號
    assert sorted(c.regs["esi"] for c in disp) == sorted(REC_OF), t
    nf = 0
    for c in disp:
        a, b = span(c)
        i, ev = c.regs["esi"], EV[c.regs["esi"]]
        inner = [x for x in lg.calls if a < x.line < b]
        kids = collections.Counter(x.eip - DELTA for x in inner)
        got = [x for x in P0C if a < x.line < b]
        if i in grabbed:                                     # 已搶過(+0x34 == 7):不再走模式 5
            assert not kids[CHOOSE] and not kids[FIND] and not got, (t, i)
            continue
        chs = [x for x in inner if x.eip - DELTA == CHOOSE]
        assert len(chs) == 1, (t, i, len(chs))
        ch = chs[0]
        finds = [x for x in inner if x.eip - DELTA == FIND]
        if lg.rets[ch.seq].eax != 0 or ev in opened:         # 有動作、或旗標已開:不找格子
            assert not finds and not got, (t, i)
            continue
        assert len(finds) == 1 and finds[0].stack[0] == ev, (t, i)
        nf += 1
        CHECKED += 1
        if not got:
            continue
        assert len(got) == 1, (t, i)
        q = got[0]
        # 0xc 的三道關與順序:ai_choose_action 0 → find_event_cell 0 → move_unit_toward_point → [unit_add_item] → 0xc
        seq = [x.eip - DELTA for x in inner if x.eip - DELTA in (CHOOSE, FIND, MOVE, ADD_ITEM) or x is q]
        kind = CHESTS[ev]["native_type"]
        assert seq == [CHOOSE, FIND, MOVE] + ([ADD_ITEM] if kind == 0 else []) + [PLAY_B], (t, i, seq)
        assert lg.rets[finds[0].seq].eax == 0
        assert q.eip - DELTA == PLAY_B and q.ret - DELTA == R_AI, (t, i)
        assert (q.regs["eax"], q.regs["ebp"], q.regs["ebx"]) == (OPENED, ev, UNIT_BASE + i * STRIDE), (t, i)
        opened.add(ev)
        grabbed.add(i)
        GRABS.append({"enemy_turn": t, "unit": i, "record": REC_OF[i], "event_id": ev, "cell": list(TARGET[REC_OF[i]]),
                      "chest_kind": kind, "chest_value": CHESTS[ev]["value"], "seq": q.seq, "ret": hex(q.ret - DELTA),
                      "unit_add_item": kind == 0})
    TURN_FIND.append(nf)
# 每一次 0xc 都被上面的模型認到(沒有模型以外的 0xc)
assert len(P0C) == len(GRABS) and CHECKED == sum(TURN_FIND) == CNT[FIND] and CNT[ADD_ITEM] == sum(g["unit_add_item"] for g in GRABS)
assert CNT[DISPATCH] == len(DISP) == len(EN) + len(FR)

# ================= Q2 搶到之後的記憶體 =================
FLAGS = {k: blob(k) for k in ("f01_flags", "f02_flags", "f03_flags", "f04_flags")}
for k, b in FLAGS.items():
    want = {g["event_id"] for g in GRABS if g["enemy_turn"] <= AFTER_TURN[k]}
    assert {s for s, v in enumerate(b) if v} == want and set(b) <= {0, 1}, (k, b.hex())
_last = FLAGS["f04_flags"]
HIDDEN = [x["slot"] for x in S185["anchors"]["map10_hidden"]]
NOT_TARGETED = sorted(s for s in CHESTS if s not in set(EV.values()))
assert set(HIDDEN) < set(NOT_TARGETED) and not any(_last[s] for s in NOT_TARGETED), NOT_TARGETED
STATE = {}
for k, b in UNITS.items():
    mine = [g for g in GRABS if g["enemy_turn"] <= AFTER_TURN[k]]
    for i in REC_OF:
        u = unit(b, i)
        g = [x for x in mine if x["unit"] == i]
        if not g:
            assert u[0x34] == 5 and u[0x31] == 0xFF, (k, i)
            continue
        assert len(g) == 1, (k, i)
        g = g[0]
        xy, p34, p3132 = [u[0], u[1]], u[0x34], [u[0x31], u[0x32]]
        assert p34 == 7 and p3132 == [g["chest_kind"], g["chest_value"] & 0xFF], (k, i)
        if g["enemy_turn"] == AFTER_TURN[k]:                 # 搶到的那個回合結束時一定站在寶箱格上
            assert xy == g["cell"], (k, i)
        STATE[f"{k}/unit{i}"] = {"xy": xy, "plus34": p34, "plus31_32": p3132, "on_chest": xy == g["cell"]}

# ================= Q3 與續一百八十五的對照 =================
FIRST = GRABS[0]
assert (FIRST["record"], FIRST["cell"]) == (S185["map10_nearest"]["record"], S185["map10_nearest"]["target"])
# 舊驅動 real_open5.py 讀開箱旗標的方式:讀 [0x53ad5] 的值、直接當位址讀(與遊戲 0x13c47 的用法一致)
_o5 = OPEN5.read_text(encoding="utf-8")
assert "CHEST_PTR_LIVE = 0x53AD5 + S.NATIVE_LIVE_DELTA" in _o5 and "raw = S.read_mem(NAME, chest_ptr, min_bytes=16)" in _o5
VERDICT = {"P1a": "PASS", "P1b": "PASS", "P1c": "PASS", "P2a": "PASS", "P2b": "PASS", "P2c": "PASS", "P2d": "PASS"}
assert len(GRABS) >= 1 and {g["chest_kind"] for g in GRABS} == {0, 1}   # P2d 兩種寶箱都看到才算 PASS
OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s186.py"), "exe_md5": MD5, "prediction": rel(PRED), "driver": rel(DRV / "lc186.py"),
    "approval": "使用者 2026-11-02「請進行實機確認」;一次實機,正常結束",
    "run": {"calllog": rel(p), "md5": LOG_MD5, "tail_cut": lg.tail_cut, "keys": len(lg.keys), "enemy_turns": len(PHASES),
            "dumps_md5": DUMPS},
    "globals": {"unit_base": hex(UNIT_BASE), "opened_flags_ptr": hex(OPENED), "units": N_UNITS, "chapter": MAP},
    "table": {"own_deploy": OWN, "thieves": f"單位 {min(REC_OF)} .. {max(REC_OF)} = 記錄 {min(M5)} .. {max(M5)}",
              "record0_unit": R0_UNIT, "record0_first_seen": LAST_FIRST, "s185_unit_field_offset": S185_OFF},
    "find_event_cell_per_turn": TURN_FIND, "mode5_checks": CHECKED, "grabs": GRABS, "after_grab": STATE,
    "flags": {k: b.hex() for k, b in FLAGS.items()}, "not_targeted_slots": NOT_TARGETED, "hidden_slots": HIDDEN,
    "verdict": VERDICT,
    "conclusion": f"第 10 張圖我方不動 {len(PHASES)} 個回合:敵方回合裡 ai_mode_dispatch 放 0xc {len(GRABS)} 次(返回 {hex(R_AI)}),"
                  "每次都是 ai_choose_action 0 → find_event_cell 0 → move_unit_toward_point →(物品才有 unit_add_item)→ handle B 0xc;"
                  "那個盜賊之後 +0x34 == 7、站在寶箱格、+0x31 / +0x32 = 寶物列前兩個 byte,開箱旗標該槽 = 1。"
                  f"第一個是記錄 {FIRST['record']}(續一百八十五預測的最近一個)。[0x53ad5] 的值就是線性位址。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, VERDICT, TURN_FIND, [(g["enemy_turn"], g["unit"], g["event_id"]) for g in GRABS])
