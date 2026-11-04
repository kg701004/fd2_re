"""續一百九十二證據(實機):evidence/live_s192_open_remainder_20261104.json。

使用者 2026-11-04「仍未解決 請新建工具 對應處理每個未解決項目」;實機「永遠核准」。原版 FD2.EXE、DOSBox-X(drivers_s192)。
續一百九十一留下的四項,各有新工具:
(1) R6 event63 不重複 —— lc192a(未修改 ch27 槽 0,lc191a 同路徑;lc192.py 的 debugger 讀取遇 real mode 會 resume 重讀,
    lc191a 停在這裡)。亞雷斯第 3 回合再走上 y = 39 → 0x35bee 第 2 次被呼叫,evstate[0x11] 仍 1、row0 仍 (2, 63, 0);
    之後敵軍走過 y = 39 也呼叫 0x35bee(返回 0x1d9f3,10 次),event63 / 0x35b78 始終 1 / 2 次、單位數 75。
    0x13a44 只在有事件的格子寫 [0x51a8f]、從不清除 —— 路過 y = 39、終點不在 y = 39 也會在行動結束 dispatch。
(2) 物理攻擊音效 —— lc192a / lc192b 的 35 個攻擊場景(0x2ebe1),每一輪攻擊 = 0x2f7b6 一次 + 0x2ed11(結果結構 s2)一次,
    之後的幀迴圈:一般幀(探針 0x2eff6)放幀 +5、命中幀命中(0x2efdb)放 +5、命中幀未命中(0x2efea)放 sub 0;
    會心(結果 +4)只走 0x2f179 閃白,音效序列與同一攻方的非會心命中相同。會心門檻表 0x524a8 的索引 = 職業 − 1(0x2f857 dec eax):
    改 [11] 為 100 後亞雷斯(職業 11)命中仍非會心,改 [10] 後他的反擊會心;lc192b 另有一次未改表的自然會心。
(3) event 82 —— lc192b(ch27 隊伍、章節 byte 29 = 第三十章 map29)。出擊選人目標寫死 19(0x2af5b),12 人名冊以斷點在
    0x2b0e3 把 EBP 改成 12 才進得了戰場;FDFIELD 單位 4(原鍵 0x7a,戰場索引 24)HP 改 1 後由亞雷斯擊殺 → 獎勵 kind 2
    (0x1ac1a)→ event 81(evstate[0x10] = 1、row0 回合 = 2)→ 第 2 回合敵方階段 0x1a85a 呼叫 event 82(對話 3、增援 group 1),
    第 1 / 3 回合敵方階段都不呼叫。
(4) 完整 pass-through mapper —— tools/dosbox/make_passthrough_map.py:DOSBox-X 自己寫出的預設 mapper(226 事件)拿掉
    Ctrl+F2 / F5 / F6 / F9 / F10 的 host 綁定。lc192c .. lc192g 帶這個檔:xdotool 真按 Ctrl+F2(ch03)、Ctrl+F5(ch06)、
    Shift+F9(章節 byte 19)、Ctrl+F10(章節 byte 20)、Ctrl+F6(章節 byte 26)全部進 guest 並揭示秘密店;錯 selection 的對照不揭示。
任何判準不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys

from _evpaths import GAME, GEN_DIR, ROOT, TOOLS, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
from _exeops import _EXE, _META, insn, operand  # noqa: E402  (_exeops 已把 tools/ 加進 sys.path)
import calllog_segments as cs  # noqa: E402
import disasm_le as dl  # noqa: E402
import unpack_dat  # noqa: E402

sys.path.insert(0, str(TOOLS / "dosbox"))
import make_passthrough_map as mpm  # noqa: E402

OUT = out_path("live_s192_open_remainder_20261104.json")
MD5 = "33464c81e6a364fd0660141139aa8e6e"
DELTA = 0x19C000
RAW = ROOT / ".wsl_build/lc192_live"
CL = RAW / "cl"
CALLLOGS = {"lc192a": "a1e50df7bf4fc02e8c48017b16d9ce0d", "lc192b": "25244d521dec6935e46e09964e4de388",
            "lc192c": "a183991bd88e2c8ab58e5915449995a8", "lc192d": "639e4b5dd6206817f4e398a88a28072c",
            "lc192e": "4cfb7462fe4ae0688226982677e14394", "lc192f": "89bb242c74ad35b9c3b5887b1a4bf59d",
            "lc192g": "d5876263d0e5efa0f952d577eecab9b2"}
MAPS = {"default_sdl2.map": "a0b4cc7055be41489d00a6c3c04387ba", "passthrough.map": "4591f38c365e72a9bde1e4edebd67b33"}
EV62, EV63, STAGING, EV81, EV82, REWARD, DIALOG, SPAWN = 0x35BEE, 0x35C1D, 0x35B78, 0x362C5, 0x362E8, 0x1AC0A, 0x15F84, 0x10B4E
CAMP_SCAN, ENEMY_AI, FIELD_EVENT, TOWN_SEL5 = 0x1A813, 0x1D8BA, 0x13A44, 0x26572
SCENE, CALC, AFTER, P_HIT, P_MISS, P_NORM, P_CRIT, SFX = (0x2EBE1, 0x2F7B6, 0x2ED11, 0x2EFDB, 0x2EFEA, 0x2EFF6,
                                                          0x2F179, 0x25A96)
PROBE = {P_HIT: "hit", P_MISS: "miss", P_NORM: "norm"}

assert hashlib.md5(_EXE).hexdigest() == MD5
_FX = dl.build_fixups(_EXE, _META)
st = lambda c: c.eip - DELTA                 # noqa: E731
rt = lambda c: c.ret - DELTA                 # noqa: E731


def calllog(name: str) -> cs.Log:
    p = RAW / f"{name}_CALLLOG.TXT"
    assert hashlib.md5(p.read_bytes()).hexdigest() == CALLLOGS[name], name
    log = cs._read(str(p), calls=True)
    assert log.calls_parsed and log.game_cs == 0x170
    return log


def state(name: str, label: str) -> dict:
    return json.loads((CL / name / f"{label}.json").read_text(encoding="utf-8"))


def keylog(name: str) -> list[dict]:
    return [json.loads(ln) for ln in (CL / f"{name}_keys.jsonl").read_text(encoding="utf-8").splitlines()]


def text_lines(name: str, shot: str) -> list[str]:
    return [ln["text"] for ln in json.loads((CL / name / f"{shot}.text.json").read_text(encoding="utf-8"))["lines"]]


def boxes(name: str, shot: str) -> list[str]:
    t = json.loads((CL / name / f"{shot}.text.json").read_text(encoding="utf-8"))
    return [b["string_hex"] for b in t["boxes"] if b["complete"] and b["file"] == "FDTXT_000.bin"]


def phase_of(log: cs.Log) -> dict[int, tuple[int, str]]:
    """每筆 E 的 seq → (回合, 'player' / 'enemy')。敵方階段 = camp_scan(0) 到下一個 camp_scan(2);
    回合 = 已經過的 camp_scan(2) 次數 + 1(0x1a78b 的 camp 2 在敵方階段尾、回合 + 1 之前,0x1a5b9)。"""
    marks = [(c.seq, c.stack[0]) for c in log.calls if st(c) == CAMP_SCAN]
    out, rnd, ph, k = {}, 1, "player", 0
    for c in log.calls:
        while k < len(marks) and marks[k][0] <= c.seq:
            camp = marks[k][1]
            if camp == 0:
                ph = "enemy"
            elif camp == 2:
                rnd, ph = rnd + 1, "player"
            k += 1
        out[c.seq] = (rnd, ph)
    return out


# ================= (A) 靜態 =================
# 0x13a44:只在有事件的格子(地形 & 0x60 == 0、slot ≠ 0、事件 id ≠ 0xff、selector 相符)寫 [0x51a8f],沒有清除分支
assert [insn(a) for a in (0x13A64, 0x13A69, 0x13A72, 0x13A87, 0x13A8D, 0x13A93, 0x13A95, 0x13A9B)] == [
    "test byte ptr [esp + 4], 0x60", "jne 0x13a9b", "je 0x13a9b", "cmp edx, 0xff", "je 0x13a9b", "jne 0x13a9b",
    "mov dword ptr [0x1a8f], edx", "add esp, 8"]
# 敵方的格子事件消費端:0x1d9ec 以 0x51b91 dispatch(返回 0x1d9f3)
assert insn(0x1D9EC) == "call dword ptr [eax*4 + 0x1b91]" and _FX[0x1D9EC + 3] == 0x51B91
# event 81 / 82
assert [insn(a) for a in (0x362CF, 0x362D4, 0x362D7, 0x362DD, 0x362E4)] == [
    "mov eax, dword ptr [0x3ad5]", "inc byte ptr [eax + 0x10]", "mov dl, byte ptr [0x3bef]", "inc dl",
    "mov byte ptr [eax + 3], dl"]
assert [insn(a) for a in (0x3631A, 0x3631E, 0x36328, 0x3636C, 0x36372)] == [
    "movzx eax, byte ptr [eax + 0x10]", "add eax, 2", "call 0x15f84", "cmp eax, 4", "call 0x10b4e"]
assert insn(0x1AC1A) == "call dword ptr [eax*4 + 0x1b91]" and insn(0x1A85A) == "call dword ptr [eax*4 + 0x1b91]"
# 出擊選人:目標 15,章節 byte > 0x1a 時 19;0x2b0e3 人數 == 目標才離開
assert [insn(a) for a in (0x2AF39, 0x2AF52, 0x2AF59, 0x2AF5B, 0x2B0DB, 0x2B0E3, 0x2B0E5)] == [
    "mov ebp, 0xf", "cmp dword ptr [0x3c03], 0x1a", "jle 0x2af60", "mov ebp, 0x13", "call 0x2b749", "cmp eax, ebp",
    "jne 0x2b0f7"]
# 物理攻擊:結果 0x2f7b6(攻, 守, &結果);命中幀分支;會心門檻表 0x524a8[職業 − 1]
assert [insn(a) for a in (0x2ED0C, 0x2ED11, 0x2EF60, 0x2EFC1, 0x2EFDD, 0x2EFEC, 0x2EFF8, 0x2F004, 0x2F009)] == [
    "call 0x2f7b6", "add esp, 0xc", "cmp byte ptr [ebx + 4], 0", "cmp dword ptr [esp + 0x18], 0",
    "movzx eax, byte ptr [ebx + 5]", "push 0", "movzx eax, byte ptr [ebx + 5]", "call 0x25a96", "add esp, 0xc"]
assert [insn(a) for a in (0x2F7D3, 0x2F853, 0x2F857, 0x2F858, 0x2F929, 0x2F9AC, 0x2F9C3, 0x2F9DA, 0x2F16E)] == [
    "mov dword ptr [esi], 1", "movzx eax, byte ptr [ebp + 0x20]", "dec eax", "mov dword ptr [esp + 0x10], eax",
    "movzx eax, byte ptr [eax + 0x24a8]", "mov dword ptr [esi], 0", "cmp edx, dword ptr [esp + 0x20]",
    "mov dword ptr [esi + 4], 1", "cmp dword ptr [esp + 0x1c], 0"]
CRIT_TABLE = 0x524A8
assert _FX[0x2F929 + 3] == CRIT_TABLE
CT = bytes(dl.object_bytes(_EXE, _META, CRIT_TABLE, 32))
assert (CT[10], CT[11], CT[24]) == (3, 12, 0), CT.hex()
# town gate 表:0x6238d + 0x1f × (章節 byte − 1);+1 = selection、+2 = BIOS 掃描碼
TOWN = 0x6238D
ROW = lambda ch: bytes(dl.object_bytes(_EXE, _META, TOWN + 0x1F * (ch - 1), 3))   # noqa: E731
assert [ROW(c)[1:] for c in (2, 5, 19, 20, 25, 26)] == [bytes([1, 0x5F]), bytes([4, 0x62]), bytes([3, 0x5C]),
                                                      bytes([4, 0x67]), bytes([4, 0x58]), bytes([0, 0x63])]
GATE_SCANS = sorted({ROW(c)[2] for c in range(1, 27) if 0x54 <= ROW(c)[2] <= 0x71})
# map29 控制段:回合列 0 休眠 82;FDFIELD 單位 1 .. 4 的原鍵 0x7d .. 0x7a、擊殺獎勵 kind 2 / 0x51(event 81)
_fd = (GAME / "FDFIELD.DAT").read_bytes()
_o, _n = unpack_dat.parse_directory(_fd)[3 * 29 + 1]
CTRL29 = _fd[_o:_o + _n]
assert tuple(CTRL29[3:6]) == (0xFF, 82, 0)
U29 = [CTRL29[0x83 + 26 * i:0x83 + 26 * (i + 1)] for i in range(5)]
assert [(u[1], u[22], u[23]) for u in U29] == [(0x7E, 2, 0x53), (0x7D, 2, 0x51), (0x7C, 2, 0x51), (0x7B, 2, 0x51),
                                               (0x7A, 2, 0x51)], [u.hex() for u in U29]

# ================= (B) mapper(tools/dosbox)=================
MAP_TXT = {}
for fn, want in MAPS.items():
    b = (TOOLS / "dosbox" / fn).read_bytes()
    assert hashlib.md5(b).hexdigest() == want and b"\r" not in b, fn
    MAP_TXT[fn] = b.decode("ascii")
assert mpm.check(MAP_TXT["default_sdl2.map"], MAP_TXT["passthrough.map"]) == []
RAW_ENTS, _tail = mpm.parse_map(MAP_TXT["default_sdl2.map"])
_new, REMOVED = mpm.strip(RAW_ENTS)
assert sorted((n, b) for n, b, _ in REMOVED) == [("hand_capmouse", "key 67 mod1"), ("hand_copyall", "key 62 mod1"),
                                                 ("hand_ejectpage", "key 59 mod1"), ("hand_paste", "key 63 mod1"),
                                                 ("hand_shutdown", "key 66 mod1")], REMOVED


def scan_to_bind(scan: int) -> str:
    """BIOS 掃描碼(Shift 0x54 .. / Ctrl 0x5e .. / Alt 0x68 .. 加 F1 .. F10)→ DOSBox-X SDL2 綁定字串。"""
    fam, n = divmod(scan - 0x54, 10)
    return f"key {58 + n} {('mod3', 'mod1', 'mod2')[fam]}"


GATE_BINDS = {hex(s): scan_to_bind(s) for s in GATE_SCANS}
assert GATE_BINDS["0x5f"] == "key 59 mod1" and GATE_BINDS["0x62"] == "key 62 mod1" and GATE_BINDS["0x5c"] == "key 66 mod3"
DEFAULT_HOST = {b: n for n, bs in RAW_ENTS if n.startswith("hand_") for b in bs}
FINAL_HOST = {b: n for n, bs in mpm.parse_map(MAP_TXT["passthrough.map"])[0] if n.startswith("hand_") for b in bs}
COLLIDE_DEFAULT = sorted((s, DEFAULT_HOST[b]) for s, b in GATE_BINDS.items() if b in DEFAULT_HOST)
assert COLLIDE_DEFAULT == [("0x5f", "hand_ejectpage"), ("0x62", "hand_copyall"), ("0x63", "hand_paste"),
                           ("0x67", "hand_capmouse")], COLLIDE_DEFAULT
assert not [b for b in GATE_BINDS.values() if b in FINAL_HOST]


def makes(log: cs.Log) -> list[int]:
    """K 紀錄的 make code(break = | 0x80 不算;0x38 = 進 debugger 的 Alt),去掉 poll_title 跳片頭的 Return。"""
    ms = [k.data for k in log.keys if k.data < 0x80 and k.data != 0x38]
    i = ms.index(0x50)
    assert i > 0 and set(ms[:i]) == {0x1C}, ms[:i]
    return ms[i:]


def tstates(name: str) -> list[tuple[str, int, int, int]]:
    return [(r["label"], r["chapter_byte"], r["ah"], r["sel"]) for r in keylog(name) if r["op"] == "tstate"]


TOWN_RUNS = {}
for name in ("lc192c", "lc192d", "lc192e", "lc192f", "lc192g"):
    run = keylog(name)[0]
    assert run["op"] == "run" and run["ok"] and run["mapper"] is True, run
    lg = calllog(name)
    TOWN_RUNS[name] = {"makes": makes(lg), "tstate": tstates(name),
                       "sel5_calls": sum(1 for c in lg.calls if st(c) == TOWN_SEL5)}
TR = TOWN_RUNS
# ch03:sel 0 真按 Ctrl+F2 → 鍵到了(AH 0x5F)但不揭示;sel 1 → 揭示
assert TR["lc192c"]["makes"] == [0x50, 0x1C, 0x1C, 0x1D, 0x3C, 0x4B, 0x1D, 0x3C], TR["lc192c"]["makes"]
assert TR["lc192c"]["tstate"] == [("m2", 2, 0x1C, 0), ("m3", 2, 0x5F, 0), ("m4a", 2, 0x4B, 1), ("m4", 2, 0x5F, 5)]
assert TR["lc192d"]["makes"] == [0x50, 0x1C, 0x1C, 0x4D, 0x1D, 0x3F]
assert TR["lc192d"]["tstate"] == [("m5a", 5, 0x1C, 0), ("m5b", 5, 0x4D, 4), ("m5", 5, 0x62, 5)]
# 章節 byte 19:Ctrl+F10 在 sel 4 到了但不是本章的鍵(預測 M6 FAIL —— 我把表的列號錯一位);sel 0 的 Shift+F9 也不揭示;sel 3 揭示
assert TR["lc192e"]["makes"] == [0x50, 0x1C, 0x1C, 0x4D, 0x1D, 0x44, 0x4B, 0x2A, 0x43, 0x4D, 0x4D, 0x2A, 0x43]
assert TR["lc192e"]["tstate"] == [("m6a", 19, 0x1C, 0), ("m6b", 19, 0x4D, 4), ("m6", 19, 0x67, 4), ("m6b1", 19, 0x4B, 0),
                                  ("m6b2", 19, 0x5C, 0), ("m6c1", 19, 0x4D, 4), ("m6c2", 19, 0x4D, 3),
                                  ("m6c3", 19, 0x5C, 5)]
assert TR["lc192f"]["makes"] == [0x50, 0x1C, 0x1C, 0x4D, 0x1D, 0x44]
assert TR["lc192f"]["tstate"] == [("m7a", 20, 0x1C, 0), ("m7b", 20, 0x4D, 4), ("m7", 20, 0x67, 5)]
assert TR["lc192g"]["makes"] == [0x50, 0x1C, 0x1C, 0x1D, 0x40]
assert TR["lc192g"]["tstate"] == [("m8a", 26, 0x1C, 0), ("m8", 26, 0x63, 5)]
assert [TR[n]["sel5_calls"] for n in TR] == [1, 1, 1, 1, 1]
# 每次揭示的 (章節 byte, 揭示前 sel, AH) 都等於表列 (+0 章節, +1 sel, +2 掃描碼);沒揭示的組合都不等於
REVEALS, NON = [], []
for n in TR:
    ts = TR[n]["tstate"]
    for (_l0, _c0, _a0, s0), (lab, ch, ah, s1) in zip(ts, ts[1:]):
        if ah >= 0x54:
            (REVEALS if s1 == 5 else NON).append((ch, s0, ah))
assert all(ROW(ch)[1:] == bytes([s0, ah]) for ch, s0, ah in REVEALS) and len(REVEALS) == 5, REVEALS
assert all(ROW(ch)[1:] != bytes([s0, ah]) for ch, s0, ah in NON) and len(NON) == 3, NON
assert boxes("lc192c", "m4_key")[-1] == "0x1f4" and boxes("lc192c", "m3_key") == ["0x1ef"]
assert all("0x1f4" in boxes(n, s) for n, s in (("lc192d", "m5_key"), ("lc192e", "m6c_key"), ("lc192f", "m7_key"),
                                               ("lc192g", "m8_key")))
assert "0x1f4" not in boxes("lc192e", "m6_key")

# ================= (C) R6:lc192a =================
LA = calllog("lc192a")
PA = phase_of(LA)
EA = [c for c in LA.calls if not c.ret_bad]
E62 = [c for c in EA if st(c) == EV62]
E63 = [c for c in EA if st(c) == EV63]
assert [hex(rt(c)) for c in E62].count("0x119a3") == 3 and [hex(rt(c)) for c in E62].count("0x1d9f3") == 10, \
    [hex(rt(c)) for c in E62]
assert len(E63) == 1 and PA[E63[0].seq] == (2, "enemy") and rt(E63[0]) == 0x1A861
assert sum(1 for c in EA if st(c) == STAGING) == 2
PLAYER62 = [(c.stack[0], PA[c.seq]) for c in E62 if rt(c) == 0x119A3]
assert PLAYER62 == [(2, (1, "player")), (2, (3, "player")), (2, (4, "player"))], PLAYER62
ENEMY62 = sorted({c.stack[0] for c in E62 if rt(c) == 0x1D9F3})
assert ENEMY62 == [63, 64, 65, 66, 67, 68, 69, 70, 73, 74] and all(PA[c.seq][1] == "enemy" for c in E62 if rt(c) == 0x1D9F3)


def last_steps(log: cs.Log, upto: int, unit_path: int) -> list[tuple]:
    """event62 之前、同一次移動(上一個 0x13488 起)的 selector 0 步。"""
    path = [c for c in log.calls if st(c) == 0x13488 and c.seq < upto][-1]
    assert path.stack[0] == unit_path, (path.stack[0], unit_path)
    return [tuple(c.stack[:3]) for c in log.calls if path.seq < c.seq < upto and st(c) == FIELD_EVENT and c.stack[2] == 0]


# 路過也算:每一次 event62 的那次移動都有一步落在 y = 39;至少一次終點不在 y = 39
PASS_THROUGH = []
for c in E62:
    stp = last_steps(LA, c.seq, c.stack[0])
    assert any(y == 39 for _x, y, _s in stp), (c.seq, stp)
    if stp[-1][1] != 39:
        PASS_THROUGH.append((c.stack[0], stp[-1][:2]))
assert len(PASS_THROUGH) >= 2 and (2, (23, 38)) in PASS_THROUGH, PASS_THROUGH
# live 狀態:第 1 回合休息後 row0 = 2;之後所有 state 讀數的 row0 / evstate[0x11] 不變
ST_LABELS = [r["label"] for r in keylog("lc192a") if r["op"] == "state"]
ROW0 = [(lab, tuple(state("lc192a", lab)["turn_rows"][0]), state("lc192a", lab)["evstate_0x11"],
         state("lc192a", lab)["round"], state("lc192a", lab)["unit_count"]) for lab in ST_LABELS]
i02 = ST_LABELS.index("s02")
assert all(r[1] == (0xFF, 63, 0) and r[2] == 0 for r in ROW0[:i02]) and ROW0[i02][1:3] == ((2, 63, 0), 1)
assert all(r[1] == (2, 63, 0) and r[2] == 1 for r in ROW0[i02:]), [r for r in ROW0[i02:] if r[1] != (2, 63, 0)]
assert max(r[3] for r in ROW0) == 7 and all(r[4] == 75 for r in ROW0 if r[3] >= 3)
# lc192.py 的重讀:每一次 read_retry 之後,同一 label 的下一筆讀取紀錄是 read_ok(第 2 次就讀到),中間沒有送鍵
RETRY = {}
for name in CALLLOGS:
    rows = keylog(name)
    for i, r in enumerate(rows):
        if r["op"] == "read_retry":
            nxt = next(x for x in rows[i + 1:] if x["op"] in ("read_ok", "read_retry", "key", "goto_step"))
            assert (nxt["op"], nxt["label"], nxt["try"]) == ("read_ok", r["label"], r["try"] + 1), (name, r, nxt)
            assert "Real mode" in r["err"], r["err"]
            RETRY[name] = RETRY.get(name, 0) + 1
assert RETRY == {"lc192a": 5, "lc192b": 1, "lc192c": 1}, RETRY
S09 = state("lc192a", "s09")
assert (S09["round"], tuple(S09["units"][2]["xy"])) == (3, (25, 39))

# ================= (D) 物理攻擊音效:lc192a + lc192b =================


def rounds_of(log: cs.Log, ph: dict) -> list[dict]:
    """攻擊場景 → 每一輪(0x2f7b6 起)的結果與幀事件;探針與 sfx 的順序原樣保留。"""
    out, cur, sc = [], None, None
    for c in log.calls:
        a = st(c)
        if a == SCENE:
            sc, cur = c.seq, None
        elif sc is None:
            continue
        elif a == CALC:
            cur = {"scene": sc, "phase": ph[c.seq], "att": c.stack[0], "tgt": c.stack[1], "res": None, "ev": [], "after": 0}
            out.append(cur)
        elif cur is None:
            continue
        elif a == AFTER:
            m = c.mem.get("s2")
            assert m is not None and len(m) >= 24, c.seq
            cur["res"] = [int.from_bytes(m[i:i + 4], "little") for i in range(0, 24, 4)]
            cur["after"] += 1
        elif a in PROBE:
            hb = c.mem.get("ebx")
            assert hb is not None, c.seq
            cur["ev"].append((PROBE[a], hb[4], hb[5]))
        elif a == P_CRIT:
            cur["ev"].append(("crit",))
        elif a == SFX and rt(c) == 0x2F009:
            cur["ev"].append(("sfx", c.stack[1], c.stack[2]))
    return out


LB = calllog("lc192b")
PB = phase_of(LB)
RA, RB = rounds_of(LA, PA), rounds_of(LB, PB)
ALL = [("lc192a", r) for r in RA] + [("lc192b", r) for r in RB]
SCENES = {(n, r["scene"]) for n, r in ALL}
assert (len(RA), len(RB), len(SCENES)) == (16, 20, 35), (len(RA), len(RB), len(SCENES))
# 每個場景都有輪;一個場景兩輪的只有 lc192b 單位 10 → 25 那一次(pred192a P1「恰 1 筆」對它不成立)
MULTI = sorted((n, s) for n, s in SCENES if sum(1 for m, r in ALL if (m, r["scene"]) == (n, s)) > 1)
assert len(MULTI) == 1 and [(r["att"], r["tgt"]) for m, r in ALL if (m, r["scene"]) == MULTI[0]] == [(10, 25), (10, 25)]
STATS = {"rounds": 0, "hit": 0, "miss": 0, "crit": 0, "sfx": 0, "sub0": 0}
for n, r in ALL:
    res = r["res"]
    assert r["after"] == 1 and res is not None, (n, r["scene"])
    miss, crit, dmg = res[0], res[1], res[5]
    assert miss in (0, 1) and crit in (0, 1) and not (miss and crit) and (dmg == 0) == (miss == 1), (n, r["scene"], res)
    ev = r["ev"]
    for i, e in enumerate(ev):
        if e[0] == "sfx":
            pv = ev[i - 1]
            assert i > 0 and pv[0] in ("hit", "miss", "norm"), (n, r["scene"], ev)
            kind, f4, f5 = pv
            if kind == "norm":
                assert f4 == 0 and e[1] == f5 != 0, (n, r["scene"], pv, e)
            elif kind == "hit":
                assert f4 != 0 and e[1] == f5 != 0, (n, r["scene"], pv, e)
            else:
                assert f4 != 0 and f5 != 0 and e[1] == 0, (n, r["scene"], pv, e)
            assert e[2] == 1
            STATS["sfx"] += 1
            STATS["sub0"] += e[1] == 0
        elif e[0] in ("hit", "miss", "norm"):
            assert i + 1 < len(ev) and ev[i + 1][0] == "sfx", (n, r["scene"], ev)     # +5 == 0 的幀不會到探針
    kinds = {e[0] for e in ev}
    assert ("hit" in kinds) <= (miss == 0) and ("miss" in kinds) <= (miss == 1), (n, r["scene"], kinds, res)
    assert ("crit" in kinds) == (crit == 1), (n, r["scene"], kinds, res)
    STATS["rounds"] += 1
    STATS["hit"] += miss == 0
    STATS["miss"] += miss
    STATS["crit"] += crit
# 另一條計數路徑:整份紀錄的探針 E 總數(不經 rounds_of 的分段)—— sfx = 三種探針總和、sub 0 = 未命中探針
PROBE_E = {k: sum(1 for lg in (LA, LB) for c in lg.calls if st(c) == a) for a, k in PROBE.items()}
assert STATS["sfx"] == sum(PROBE_E.values()) and STATS["sub0"] == PROBE_E["miss"], (STATS, PROBE_E)
assert (STATS["rounds"], STATS["hit"], STATS["miss"], STATS["crit"]) == (36, 28, 8, 2), STATS
# P6:兩次 state 讀數之間,每個守方 HP 後 = max(0, HP 前 − 期間命中輪的傷害(結果 +0x14)總和);未命中不扣
def hp_pairs(name: str, rounds: list[dict]) -> list[tuple]:
    rows = keylog(name)
    sc_order = sorted({r["scene"] for r in rounds})
    exact = []                                 # (state label, 那時已發生的場景數):前後兩筆 calls 相同才算確定
    for i, r in enumerate(rows):
        if r["op"] != "state":
            continue
        pv = [x["attack_scene"] for x in rows[:i] if x["op"] == "calls"][-1:]
        nx = [x["attack_scene"] for x in rows[i + 1:] if x["op"] == "calls"][:1]
        if pv and nx and pv == nx:
            exact.append((r["label"], pv[0]))
    out = []
    for (l1, c1), (l2, c2) in zip(exact, exact[1:]):
        if c2 == c1:
            continue
        u1, u2 = state(name, l1)["units"], state(name, l2)["units"]
        mid = [r for r in rounds if c1 < sc_order.index(r["scene"]) + 1 <= c2]
        for t in sorted({r["tgt"] for r in mid}):
            dmg = sum(r["res"][5] for r in mid if r["tgt"] == t and r["res"][0] == 0)
            out.append((l1, l2, t, u1[t]["hp"], dmg, u2[t]["hp"]))
    return out


HP_CHECK = hp_pairs("lc192a", RA) + hp_pairs("lc192b", RB)
assert len(HP_CHECK) >= 4 and all(h2 == max(0, h1 - d) for _a, _b, _t, h1, d, h2 in HP_CHECK), HP_CHECK
assert any(d == 0 for *_x, d, _h in HP_CHECK) and any(d > 0 for *_x, d, _h in HP_CHECK), HP_CHECK
# 亞雷斯(單位 2)的命中輪:會心與否,(探針, 幀 +4, +5, sub) 都只有一個命中幀 + 一次 sub 2
ARES = [(n, r) for n, r in ALL if r["att"] == 2 and r["res"][0] == 0]
SHAPE = lambda r: [e for e in r["ev"] if e[0] != "crit"]      # noqa: E731
assert {r["res"][1] for _n, r in ARES} == {0, 1} and all(SHAPE(r) == [("hit", 1, 2), ("sfx", 2, 1)] for _n, r in ARES), \
    [SHAPE(r) for _n, r in ARES]
CRITS = [(n, r["scene"], r["phase"], r["att"], r["tgt"], r["res"][5]) for n, r in ALL if r["res"][1] == 1]
NONCRIT_ARES_DMG = sorted(r["res"][5] for n, r in ARES if r["res"][1] == 0)
assert [(c[0], c[3]) for c in CRITS] == [("lc192a", 2), ("lc192b", 2)], CRITS
# 會心門檻表的改寫(lc192a keys.jsonl):[11] 改 100 的窗內亞雷斯命中仍非會心;[10] 改 100 的窗內他的反擊會心
POKES = [r for r in keylog("lc192a") if r["op"] == "poke"]
assert [(p["label"], p["addr"], p["before"], p["after"]) for p in POKES] == [
    ("p01_crit", hex(CRIT_TABLE + 11 + DELTA), "0c", "64"), ("p02_restore", hex(CRIT_TABLE + 11 + DELTA), "64", "0c"),
    ("p03_crit", hex(CRIT_TABLE + 10 + DELTA), "03", "64"), ("p04_restore", hex(CRIT_TABLE + 10 + DELTA), "64", "03")]


def scenes_seen_before(name: str, label: str) -> int:
    """該 poke 之前最後一次 `calls` 記下的攻擊場景數。"""
    rows = keylog(name)
    i = next(k for k, r in enumerate(rows) if r.get("label") == label and r["op"] == "poke")
    return [r for r in rows[:i] if r["op"] == "calls"][-1]["attack_scene"]


WIN = {p["label"]: scenes_seen_before("lc192a", p["label"]) for p in POKES}
assert WIN == {"p01_crit": 8, "p02_restore": 10, "p03_crit": 10, "p04_restore": 16}, WIN
SC_A = sorted({r["scene"] for r in RA})
IN11 = [r for r in RA if SC_A.index(r["scene"]) + 1 in range(WIN["p01_crit"] + 1, WIN["p02_restore"] + 1)]
IN10 = [r for r in RA if SC_A.index(r["scene"]) + 1 in range(WIN["p03_crit"] + 1, WIN["p04_restore"] + 1)]
assert [(r["att"], r["res"][0], r["res"][1]) for r in IN11 if r["att"] == 2] == [(2, 0, 0)]
assert [(r["att"], r["res"][0], r["res"][1]) for r in IN10 if r["att"] == 2] == [(2, 0, 1)]
assert all(r["res"][1] == 0 for r in IN10 if r["att"] != 2)            # 敵軍職業 25 → 索引 24 = 0
assert max(NONCRIT_ARES_DMG) < min(c[5] for c in CRITS), (NONCRIT_ARES_DMG, CRITS)   # 會心 DP 減半 → 傷害較大
# lc192b 的會心(亞雷斯 → 24)發生在沒有改表的 instance
assert not [r for r in keylog("lc192b") if r["op"] == "poke" and int(r["addr"], 16) - DELTA in range(CRIT_TABLE, CRIT_TABLE + 32)]

# ================= (E) event 82:lc192b =================
EB = [c for c in LB.calls if not c.ret_bad]
BP = {r["op"]: r for r in keylog("lc192b") if r["op"].startswith("bpreg")}
assert BP["bpreg_hit"]["eip"] == hex(0x2B0E3 + DELTA) and BP["bpreg_hit"]["regs"]["EAX"] == "0xc" \
    and BP["bpreg_hit"]["regs"]["EBP"] == "0x13" and BP["bpreg_set_reg"]["readback"] == "0xc", BP
assert boxes("lc192b", "k11_scr") == ["0x292"]                   # 確定要進入戰場嗎？
S00, S04, S05, S06 = (state("lc192b", x) for x in ("s00", "s04", "s05", "s06"))
assert (S00["round"], tuple(S00["turn_rows"][0]), S00["evstate_0x10"], S00["unit_count"]) == (1, (0xFF, 82, 0), 0, 27)
DEMONS = [(u["i"], u["p7"]) for u in S00["units"] if u["p7"] in (0x7E, 0x7D, 0x7C, 0x7B, 0x7A) and u["p6"] == 0]
assert DEMONS == [(20, 0x7E), (21, 0x7D), (22, 0x7C), (23, 0x7B), (24, 0x7A)], DEMONS
HP_POKE = [r for r in keylog("lc192b") if r["op"] == "poke"]
U24 = int(S00["units_ptr"], 16) + 24 * 0x50 + 0x40
assert [(p["addr"], p["before"], p["after"]) for p in HP_POKE] == [(hex(U24), "9411", "0100")]
KILL = [r for r in RB if r["att"] == 2 and r["tgt"] == 24]
assert len(KILL) == 1 and KILL[0]["res"][0] == 0 and KILL[0]["phase"] == (1, "player")
R81 = [c for c in EB if st(c) in (REWARD, EV81, EV82)]
assert [(hex(st(c)), PB[c.seq]) for c in R81] == [(hex(REWARD), (1, "player")), (hex(EV81), (1, "player")),
                                                  (hex(EV82), (2, "enemy"))], [(hex(st(c)), PB[c.seq]) for c in R81]
C81, C82 = R81[1], R81[2]
assert R81[0].seq > KILL[0]["scene"] and rt(C81) == 0x1AC1A + 7 and rt(C82) == 0x1A85A + 7
assert (S04["round"], tuple(S04["turn_rows"][0]), S04["evstate_0x10"]) == (1, (2, 82, 0), 1)
assert S04["units"][24]["hp"] == 0 and S04["units"][24]["p5"] & 1
# event 82 在第 2 回合 camp_scan(0) 之內、該階段的敵軍 AI 之前;對話參數 3、增援 group 1(返回 0x36377)
scan0 = [c for c in EB if st(c) == CAMP_SCAN and c.stack[0] == 0]
inside = [c for c in scan0 if c.seq < C82.seq][-1]
ai_after = [c for c in EB if st(c) == ENEMY_AI and c.seq > inside.seq][0]
assert PB[inside.seq] == (2, "enemy") and inside.seq < C82.seq < ai_after.seq
D82 = [c for c in EB if st(c) == DIALOG and rt(c) == 0x3632D]
SP82 = [c for c in EB if st(c) == SPAWN and rt(c) == 0x36377]
assert [c.stack[1] for c in D82] == [3] and [c.stack[0] for c in SP82] == [1] and C82.seq < D82[0].seq < SP82[0].seq < ai_after.seq
assert (S05["round"], S05["unit_count"], S06["round"], S06["unit_count"]) == (2, 27, 3, 29)
LAST_ROUND = max(PB[c.seq][0] for c in EB if st(c) == CAMP_SCAN and c.stack[0] == 2)
assert LAST_ROUND == 4 and sum(1 for c in EB if st(c) == EV82) == 1    # 第 3 回合敵方階段結束(camp 2)之後才 teardown

OUT.write_text(json.dumps({
    "generator": rel(GEN_DIR / "ev_s192.py"), "exe_md5": MD5, "calllogs_md5": CALLLOGS, "mapper_md5": MAPS,
    "r6": {"ev62_player": [[u, list(p)] for u, p in PLAYER62], "ev62_enemy_units": ENEMY62,
           "ev63_calls": len(E63), "staging_calls": 2, "pass_through": [[u, list(xy)] for u, xy in PASS_THROUGH],
           "row0_reads": [[r[0], list(r[1]), r[2], r[3], r[4]] for r in ROW0], "real_mode_retries": RETRY,
           "pred192a": {"A1": "PASS", "A2": "PASS", "A3": "PASS", "A4": "PASS"}},
    "attack_sfx": {"stats": STATS, "multi_round_scene": [MULTI[0][0], MULTI[0][1]],
                   "ares_hit_shape": [list(e) for e in SHAPE(ARES[0][1])], "ares_hit_rounds": len(ARES),
                   "hp_check": [list(h) for h in HP_CHECK], "probe_e": PROBE_E,
                   "crits": [list(c[:2]) + [list(c[2])] + list(c[3:]) for c in CRITS],
                   "ares_noncrit_damage": NONCRIT_ARES_DMG, "crit_table": {"index": "職業 − 1(0x2f857)",
                                                                           "[10]": CT[10], "[11]": CT[11], "[24]": CT[24]},
                   "poke_windows": WIN,
                   "pred192a": {"P1": "FAIL(單位 10 → 25 一個場景兩輪;每一輪恰 1 筆 0x2f7b6 + 0x2ed11)", "P2": "PASS",
                                "P3": "PASS", "P4": "PASS(lc192a 改表後、lc192b 未改表各一次)", "P5": "補 1 改由我方攻擊",
                                "P6": f"PASS({len(HP_CHECK)} 組 state 讀數之間 HP 後 = max(0, HP 前 − 命中傷害))",
                                "C1": "FAIL(改的是 [11];索引 = 職業 − 1)", "C1'": "PASS", "C2'": "PASS", "C3'": "PASS"}},
    "event82": {"sortie": {"target_ebp": "0x13", "count_eax": "0xc", "set_ebp": "0xc"},
                "demons": [[i, hex(k)] for i, k in DEMONS], "hp_poke": [hex(U24), "0x1194 → 1"],
                "kill_round": list(KILL[0]["phase"]), "ev81_ret": hex(rt(C81)), "ev82_ret": hex(rt(C82)),
                "ev82_phase": list(PB[C82.seq]), "dialog_arg": 3, "spawn_group": 1, "units": [27, 29],
                "pred192b": {"E1": "PASS", "E2": "PASS", "E3": "PASS", "E4": "PASS", "E5": "PASS",
                             "介入 1": "PASS", "介入 2": "對象更正後 PASS(補 1)"}},
    "mapper": {"removed": [[n, b, d] for n, b, d in REMOVED], "gate_scans": [hex(s) for s in GATE_SCANS],
               "default_collisions": COLLIDE_DEFAULT, "town_runs": {n: {"makes": [hex(x) for x in v["makes"]],
                                                                         "tstate": v["tstate"]} for n, v in TR.items()},
               "reveals": REVEALS, "non_reveals": NON,
               "pred192m": {"M1": "PASS", "M2": "PASS", "M3": "PASS", "M4": "PASS", "M5": "PASS",
                            "M6": "FAIL(預測的表列號錯一位)", "M6b": "FAIL(選單方向寫反,Left = +1)", "M6c": "PASS",
                            "M7": "PASS", "M8": "PASS"}},
    "conclusion": "四項都以實機關閉:event63 不重複(event62 之後再被玩家與敵軍呼叫 13 次,狀態不變);物理攻擊每一輪的 sfx 由幀 +5 與"
                  "命中結果決定、會心不改音效;event 82 由擊殺魔神 → event 81 → 下一回合敵方階段派送;完整 mapper 讓真按的"
                  " Ctrl / Shift + F 鍵全部進得了 guest。",
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print(OUT, STATS, CRITS, PASS_THROUGH, COLLIDE_DEFAULT)
