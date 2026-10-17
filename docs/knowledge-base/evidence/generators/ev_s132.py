"""續一百三十二證據:evidence/phase_loop_runB_hud_icon_20261017.json。

(1) 續一百三十一記成「四次都沒錄到 0x152a0」的三份呼叫紀錄(lc131a、lc131b、lc131d)其實都錄到了光束炮八圈相位迴圈:
    當時等待用的 grep 寫成 `^E [0-9]* 1b12a0`,紀錄裡的 EIP 是補零的 `001b12a0`,所以永遠數到 0。
    這三份都是續一百二十三第二輪的擺法(#5、#10 不在光束線上,索爾 HP 167),途中沒有斷點。
(2) 續一百三十一 (10, 20) 那 53 個像素:是 draw_map_hud 在畫面左下角畫的游標格單位圖示,不是旁邊單位的圖。
全部從 .wsl_build/lc131_runB_calllogs/、.wsl_build/lc130a_phase_eips.txt、.wsl_build/lc131a_moverange/{D,E,F}/
與 FD2.EXE 重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

EXE = GAME / "FD2.EXE"
LOGS = {n: ROOT / ".wsl_build" / "lc131_runB_calllogs" / f"{n}.txt" for n in ("lc131a", "lc131b", "lc131d")}
LOG_A = ROOT / ".wsl_build" / "lc130a_phase_eips.txt"          # 續一百三十:第一輪擺法、沒有斷點
S123 = ROOT / "docs/knowledge-base/evidence/ai_item_action_item79_flow_20261013.json"
RAW131 = ROOT / ".wsl_build" / "lc131a_moverange"
OUT = out_path("phase_loop_runB_hud_icon_20261017.json")
DELTA = 0x19C000                 # 原生 linear + DELTA = 執行期 EIP
E_START, E_TICK, E_ADV, E_DRAW, E_END = (a + DELTA for a in (0x152A0, 0x12117, 0x12132, 0x12169, 0x152BA))
ORIGIN, STRIDE, CELL = 0x8088, 456, 24   # redraw 傳給 draw_terrain_layer / draw_map_hud 的 dst = 緩衝 + 0x8088、stride 456

# 靜態:位元組逐一釘住(FD2.EXE;obj2 位移是檔案內的未重定位值)
CODE = {
    # wait_ticks(n):入口讀 BIOS tick [0x46c] 存到 [0x53a2c],迴圈到差 >= n,離開前再讀一次(eax = 離開時的 tick)
    0x17AB3: "8b542404b86c0400000fbf00a32c3a0000b86c0400000fbf002b052c3a000085c07d05050000010039d07ce5"
             "b86c0400000fbf00a32c3a0000c3",
    # 相位迴圈:[0x53c1f] = k;redraw(1);wait_ticks(1);k++ 到 8
    0x152A0: "891d1f3c00006a01e8ffc9ffff83c4046a01e8f227000083c4044383fb097ce0",
    # redraw(1) 略過 palette_cycle_tick
    0x11CBC: "837c2408007505e854c60300",
    # draw_map_hud:[0x51a0c] 只在游標視窗位置符合時改成 0xf2 / 1;ebp = dst + stride × 0x9d + [0x51a0c]
    0x1AD2A: "833dbd3a0000057e15833db93a0000037d0cc7050c1a0000f2000000eb1c833dbd3a0000057e13833db93a0000097e0a"
             "c7050c1a00000100000069c79d00000001c5032d0c1a0000",
    # draw_map_hud:單位圖示 = 表 [0x53a61][單位 +2 × 12 + [0x53c0b](3 當 1)],blit_tile24_rle 到 ebp + stride × 5 + 6
    0x1AE4D: "0fb656026bd20ca10b3c000083f8037505b80100000001d08b15613a00008b048201d0894424085789f8c1e00201f801e8"
             "83c00650ff742410e89f330300",
}
HUD_ROW, HUD_DY, HUD_DX = 0x9D, 5, 6


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


_D = EXE.read_bytes()
_M = dl.parse_le(_D)
for a, hx in CODE.items():
    got = bytes(dl.object_bytes(_D, _M, a, len(hx) // 2)).hex()
    assert got == hx, (hex(a), got)
_o = dl.lin2file(_M, 0x51A0C)
HUD_X0 = struct.unpack_from("<i", _D, _o)[0]
assert HUD_X0 == 1, HUD_X0                       # 初值 1;另一個可能值 0xf2 在畫面右側


# ================= (1) 相位迴圈 =================
def parse(path: Path) -> tuple[str, list[tuple[int, int, int, int]], list[str]]:
    header, recs, lines = None, [], []
    for ln in path.read_text(encoding="ascii").split("\n"):
        if ln.startswith("H "):
            header = ln
        elif ln.startswith("E "):
            p = ln.split(" ")
            recs.append((int(p[1]), int(p[2], 16), int(p[6], 16), int(p[7], 16)))
            lines.append(ln)
    assert header is not None and "entries=5 " in header and "dump=0 " in header, header
    assert [r[0] for r in recs] == list(range(1, len(recs) + 1)), "seq 不連續"
    assert {r[1] for r in recs} <= {E_START, E_TICK, E_ADV, E_DRAW, E_END}
    return header, recs, lines


def cut(recs: list[tuple[int, int, int, int]]) -> dict:
    """切出唯一的八圈迴圈;記迴圈前最後一次推進的 tick 與迴圈前後一般重繪的 tick 差。"""
    loops, cur, last_tick, last_adv, pre_last = [], None, None, None, []
    ticks_before, ticks_after, end_seen = [], [], False
    for seq, eip, eax, ebx in recs:
        if eip == E_START:
            assert cur is None, f"seq {seq}:上一圈沒有收尾"
            if ebx == 1:
                loops.append([])
                pre_last.append(last_adv)
            cur = {"k": ebx, "ticks": [], "adv": 0, "drawn": [], "tick_after": None, "k_after": None}
        elif cur is None:
            if eip == E_TICK:
                last_tick = eax & 0xFFFF
                (ticks_after if end_seen else ticks_before).append(last_tick)
            elif eip == E_ADV:
                last_adv = last_tick
        elif eip == E_TICK:
            cur["ticks"].append(eax & 0xFFFF)
        elif eip == E_ADV:
            cur["adv"] += 1
        elif eip == E_DRAW:
            cur["drawn"].append(eax)
        elif eip == E_END:
            cur["tick_after"], cur["k_after"] = eax & 0xFFFF, ebx
            loops[-1].append(cur)
            cur, end_seen = None, True
    assert cur is None and len(loops) == 1, len(loops)
    gaps = lambda ts: [(b - a) & 0xFFFF for a, b in zip(ts, ts[1:])]    # noqa: E731
    return {"loop": loops[0], "last0": pre_last[0], "gaps_before12": gaps(ticks_before[-13:]),
            "gaps_after_first": gaps(ticks_after[:13])}


def judge(loop: list[dict], last0: int | None, drawn: list[int]) -> dict[str, bool]:
    """與 ev_s130 相同的判準;drawn 是被判的每圈階(實測或對照假設)。"""
    j: dict[str, bool] = {}
    j["八圈 k = 1..8 依序"] = [f["k"] for f in loop] == list(range(1, 9))
    j["每圈收尾 ebx 仍是 k"] = all(f["k_after"] == f["k"] for f in loop)
    j["每圈只畫一次地形、走 -1 分支一次"] = all(len(f["drawn"]) == 1 and len(f["ticks"]) == 1 for f in loop)
    j["畫的階 ∈ {k, k + 1}"] = all(d in (f["k"], f["k"] + 1) for d, f in zip(drawn, loop))
    j["推進 ⇔ 畫 k + 1"] = all(f["adv"] <= 1 and (f["adv"] == 1) == (d == f["k"] + 1) for d, f in zip(drawn, loop))
    ok, last = last0 is not None, last0
    for f in loop:
        t = f["ticks"][0] if f["ticks"] else None
        if t is None or last is None:
            ok = False
            continue
        if ((t - last > 2) or (t < last)) != (f["adv"] == 1):
            ok = False
        if f["adv"] == 1:
            last = t
    j["推進 ⇔ tick − 上次推進 > 2(含第 1 圈)"] = ok
    return j


def crossings(loop: list[dict]) -> list[int]:
    """每圈 redraw 期間跨過幾個 tick 邊界:wait_ticks(1) 離開時 tick = 入口 tick + 1,所以 = 收尾 tick − 1 − 畫地形時的 tick。"""
    return [f["tick_after"] - 1 - f["ticks"][0] for f in loop]


s123 = json.loads(S123.read_text(encoding="utf-8"))
runs123 = [[r["phase_read_at_stop"] for r in run["strip"]["rows"]] for run in s123["runs"]]
RUN_A, RUN_B = runs123
assert RUN_A == [2, 2, 4, 4, 5, 7, 7, 8] and RUN_B == [1, 3, 3, 5, 5, 7, 7, 9], runs123

runs: dict[str, dict] = {}
query_bug: dict[str, dict] = {}
for name, path in {"lc130a": LOG_A, **LOGS}.items():
    header, recs, lines = parse(path)
    c = cut(recs)
    loop = c["loop"]
    drawn = [f["drawn"][0] for f in loop]
    j = judge(loop, c["last0"], drawn)
    assert all(j.values()), (name, j)
    ctl_k = judge(loop, c["last0"], [f["k"] for f in loop])                  # 對照:畫的就是 k
    ctl_shift = judge(loop, c["last0"], [drawn[(i + 1) % 8] for i in range(8)])
    assert not all(ctl_k.values()) and not all(ctl_shift.values()), (name, ctl_k, ctl_shift)
    runs[name] = {"raw_sha256": sha(path), "E_records": len(recs), "drawn": drawn, "adv": [f["adv"] for f in loop],
                  "tick_at_draw": [f["ticks"][0] for f in loop], "tick_after": [f["tick_after"] for f in loop],
                  "last_adv_before_loop": c["last0"], "redraw_tick_crossings": crossings(loop),
                  "normal_redraw_gaps_before_loop": c["gaps_before12"],
                  "normal_redraw_gaps_after_loop": c["gaps_after_first"], "checks": j}
    if name != "lc130a":
        # 續一百三十一的等待條件:沒有補零的 EIP 永遠數到 0;補零後是 8
        query_bug[name] = {"old_pattern_1b12a0": sum(1 for ln in lines if ln.split(" ")[2] == "1b12a0"),
                           "padded_001b12a0": sum(1 for ln in lines if ln.split(" ")[2] == "001b12a0")}
        assert query_bug[name] == {"old_pattern_1b12a0": 0, "padded_001b12a0": 8}, query_bug[name]

# 實測:第二輪擺法、沒有斷點的兩份(lc131b、lc131d)與續一百二十三第二輪(有斷點)逐圈相同;lc131a 前 5 圈相同
assert runs["lc131b"]["drawn"] == runs["lc131d"]["drawn"] == RUN_B
assert runs["lc131a"]["drawn"] == [1, 3, 3, 5, 5, 6, 8, 8]
assert runs["lc130a"]["drawn"] == RUN_A
# 對照:「第二輪不同是斷點造成的」—— 那沒有斷點時第二輪擺法應畫出第一輪的階;不成立
assert all(runs[n]["drawn"] != RUN_A for n in LOGS)
# 量之前寫下的推論(續一百三十一 doc35):第二輪每 2 圈推進一次,每兩圈至少 3 tick。第一輪不滿足
two = {n: [r["tick_after"][i + 1] - r["tick_at_draw"][i] for i in range(0, 8, 2)] for n, r in runs.items()}
assert all(min(two[n]) >= 3 for n in ("lc131b", "lc131d")), two
assert two == {"lc130a": [3, 2, 2, 2], "lc131a": [4, 3, 3, 3], "lc131b": [5, 3, 4, 4], "lc131d": [3, 4, 3, 4]}, two
assert min(two["lc130a"]) < 3, two
assert all(runs[n]["adv"] == [0, 1, 0, 1, 0, 1, 0, 1] for n in ("lc131b", "lc131d"))
# 差在每圈 redraw 的長度:第一輪 8 圈裡 7 圈 redraw 沒有跨 tick;第二輪擺法 8 圈裡至少 6 圈跨了 1 個以上
cross = {n: r["redraw_tick_crossings"] for n, r in runs.items()}
assert sum(x == 0 for x in cross["lc130a"]) == 7, cross
assert all(sum(x >= 1 for x in cross[n]) >= 6 for n in ("lc131b", "lc131d")), cross
# 迴圈前後的一般畫面:四份都是每幀 1 tick(差異只在迴圈內)
assert all(r["normal_redraw_gaps_before_loop"][-7:] == [1] * 7 for r in runs.values()), {n: r["normal_redraw_gaps_before_loop"] for n, r in runs.items()}

# ================= (2) (10, 20) 那 53 個像素 = HUD 單位圖示 =================
bufs = {t: (RAW131 / t / "buf.bin").read_bytes() for t in "DEF"}
units = (RAW131 / "D" / "units.bin").read_bytes()
assert all(len(b) == 0x25680 for b in bufs.values())
pos = {(units[i * 80], units[i * 80 + 1]) for i in range(len(units) // 80)}
assert (9, 20) not in pos and (10, 20) not in pos, "(9, 20) / (10, 20) 有單位"
icon = (HUD_X0 + HUD_DX, HUD_X0 + HUD_DX + CELL - 1, HUD_ROW + HUD_DY, HUD_ROW + HUD_DY + CELL - 1)   # x0, x1, y0, y1(視窗像素)


def px(b: bytes, x: int, y: int) -> int:
    return b[ORIGIN + y * STRIDE + x]


def blob(a: str, b: str) -> dict:
    """(10, 20) 格內差異像素所在的 4 連通塊;另算 x < 48、列在圖示框內的差異是否全在框內。"""
    A, B = bufs[a], bufs[b]
    diff = {(x, y) for y in range(8 * CELL) for x in range(13 * CELL) if px(A, x, y) != px(B, x, y)}
    seed = {p for p in diff if CELL <= p[0] < 2 * CELL and 7 * CELL <= p[1] < 8 * CELL}
    comp, st = set(seed), list(seed)
    while st:
        x, y = st.pop()
        for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if q in diff and q not in comp:
                comp.add(q)
                st.append(q)
    band = {p for p in diff if p[0] < 2 * CELL and icon[2] <= p[1] <= icon[3]}
    inbox = {p for p in band if icon[0] <= p[0] <= icon[1]}
    bb = [min(x for x, _ in comp), max(x for x, _ in comp), min(y for _, y in comp), max(y for _, y in comp)] if comp else None
    return {"in_cell_10_20": len(seed), "component": len(comp), "bbox": bb, "band_diffs": len(band),
            "band_outside_icon": len(band - inbox)}


hud = {f"{a}-{b}": blob(a, b) for a, b in (("D", "E"), ("D", "F"), ("E", "F"))}
assert hud["D-E"] == {"in_cell_10_20": 0, "component": 0, "bbox": None, "band_diffs": 0, "band_outside_icon": 0}, hud
for k in ("D-F", "E-F"):
    h = hud[k]
    assert h["in_cell_10_20"] == 53, h
    assert (h["component"], h["band_diffs"]) == (259, 303), h            # 實測值釘住(4 連通、列帶範圍)
    x0, x1, y0, y1 = h["bbox"]
    assert icon[0] <= x0 and x1 <= icon[1] and (y0, y1) == (icon[2], icon[3]), (h, icon)    # 列剛好是圖示框的 24 列
    assert h["band_outside_icon"] == 0, h
# 對照:單位圖(draw_unit_sprite)只依方向橫移 ±4 px;站在 (9, 20) 或 (10, 20) 的單位圖都框不住這一塊
for cx in (9, 10):
    vx = (cx - 9) * CELL
    assert not (vx - 4 <= hud["D-F"]["bbox"][0] and hud["D-F"]["bbox"][1] <= vx + CELL - 1 + 4), cx

ev = {
    "_meta": {"topic": "續一百三十二:續一百二十三第二輪的擺法在沒有斷點時畫的階(更正續一百三十一的 BLOCKED);"
                       "(10, 20) 那 53 個像素是 draw_map_hud 的單位圖示",
              "exe": rel(EXE), "exe_md5": hashlib.md5(_D).hexdigest(),
              "raw": {"calllogs": {n: rel(p) for n, p in {"lc130a": LOG_A, **LOGS}.items()},
                      "moverange": {f"{t}/{f}": sha(RAW131 / t / f) for t in "DEF" for f in ("buf.bin",)} | {"D/units.bin": sha(RAW131 / "D" / "units.bin")}},
              "generator": "evidence/generators/ev_s132.py(變異測試 mut_s132.py)",
              "harness": "DOSBox-X(tools/dosbox_harness.sh 預設 cycles 5000);原版 FD2.EXE;呼叫紀錄只列 5 個 EIP,途中不下斷點;"
                         "lc131a/b/d 的擺法同續一百二十三第二輪(#11 在 (19, 14)、道具 79,索爾 HP 167;#5、#10 設倒下(a、b)或搬走(d))"},
    "static_code": {hex(a): hx for a, hx in CODE.items()},
    "hud_x0_initial_51a0c": HUD_X0,
    "s123_breakpoint_runs": {"runA": RUN_A, "runB": RUN_B},
    "runs": runs,
    "ticks_per_two_iterations": two,
    "query_bug_s131": query_bug,
    "hud_icon_box_view_px": {"x": icon[:2], "y": icon[2:]},
    "hud_pairs": hud,
    "status": {
        "s131_blocked_retracted": "LOG CONFIRMED:續一百三十一的「四次都沒錄到 0x152a0」是查詢寫錯 —— 等待條件 grep `^E [0-9]* 1b12a0`,"
                                  "紀錄的 EIP 是補零的 001b12a0;lc131a、b、d 三份各有 8 筆(lc131c 停在城鎮,沒有走到戰場)",
        "runB_levels": "LOG CONFIRMED:第二輪擺法、沒有斷點的 lc131b、lc131d 逐圈畫 1、3、3、5、5、7、7、9,與續一百二十三第二輪(有斷點)相同;"
                       "lc131a(之前做過選取與 Esc、改過游標)是 1、3、3、5、5、6、8、8。第二輪不同不是斷點造成的",
        "cause": "LOG CONFIRMED + 反組譯:每圈 = redraw(1) + wait_ticks(1),wait_ticks 等到 tick 換掉為止;推進條件是 tick − 上次推進 > 2。"
                 "第一輪 8 圈裡 7 圈 redraw 沒有跨 tick(每圈 1 tick);第二輪擺法 redraw 大多跨 1 個 tick(每圈 2 tick),"
                 "所以每兩圈推進一次、畫 k、k + 1 交替。迴圈前後的一般畫面四份都是每幀 1 tick",
        "cause_open": "NOT CONFIRMED:第二輪擺法的 redraw 為什麼比較久(鏡頭位置、亮帶方向或畫面內容)沒有量",
        "s131_inference": "量之前寫下的推論「第二輪每兩圈至少 3 tick」符合(lc131b、lc131d);第一輪不符合",
        "hud_icon": "CODE + LOG CONFIRMED:(10, 20) 那 53 個像素所在的差異塊外框落在 draw_map_hud 的單位圖示框"
                    "(視窗 x 7..30、列 162..185,[0x51a0c] 初值 1)內,列剛好是框的 24 列;圖示框列帶內沒有框外差異;"
                    "(9, 20)、(10, 20) 沒有單位,單位圖的 ±4 px 位移框不住。續一百三十一寫的「旁邊單位的圖(推論)」更正。"
                    "圖示的影格內容(表 [0x53a61]、時脈 [0x53c0b])沒有逐像素核對",
    },
}


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
