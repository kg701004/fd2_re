"""ev_s157.py 的變異測試:每個變異改一個判準 / 預測,必須讓 ev_s157.py 以 AssertionError 失敗(不能是其他例外)。
變異版與輸出都在暫存目錄,不碰已提交的證據檔;先跑未變異的對照(見 _mutrun.py)。"""
from __future__ import annotations

import sys

from _mutrun import run_mutants

MUTANTS = [
    # (A) 第 1 項
    ("模式 1 改先寫再跳過", '"skip_then_write": slice(pos + 1, pos + 2 * n, 2)', '"skip_then_write": slice(pos, pos + 2 * n, 2)'),
    ("灰階基底 + 1", "px = np.where(px >= 0, (px & GREY_MASK) + GREY_BASE, -1)", "px = np.where(px >= 0, (px & GREY_MASK) + GREY_BASE + 1, -1)"),
    ("單位圖不上移", "x0, y0 = VIEW_XY[0] + CELL * cx, VIEW_XY[1] + CELL * cy + UNIT_DY", "x0, y0 = VIEW_XY[0] + CELL * cx, VIEW_XY[1] + CELL * cy"),
    ("+2 當 FDICON 組號", "def predict(slot: int, frame: int, grey: bool, order: str, fdicon_group: bool = False)",
     "def predict(slot: int, frame: int, grey: bool, order: str, fdicon_group: bool = True)"),
    ("時脈 3 不當 1", 'clk = CLK_TO if meta["c0b"] == CLK_FROM else meta["c0b"]', 'clk = meta["c0b"]'),
    ("灰階 / 彩色條件反過來", "grey = bool(f5 & GREY_BIT)", "grey = not (f5 & GREY_BIT)"),
    ("資訊框只試左側", "for x0h in (d32(0x51A0C), HUD_X_RIGHT):", "for x0h in (d32(0x51A0C),):"),
    ("兩格都寫的多寫一半也要中", "assert both[3] == 2 * sw[3] and both[2] == sw[2], (u, h)", "assert both[3] == 2 * sw[3] and both[2] == both[3], (u, h)"),
    ("對照只要求一個不全中", "assert all(h < n for h, n in A_ROWS[t]", "assert all(h == n for h, n in A_ROWS[t]"),
    # (B) 第 3 項
    ("表項不加程式基底", "struct.unpack_from(\"<I\", _D, dl.lin2file(META, 0x51D01) + 4 * k)[0] + dl.CODE_BASE",
     "struct.unpack_from(\"<I\", _D, dl.lin2file(META, 0x51D01) + 4 * k)[0]"),
    ("返回位址 call 長 5", "RET_1541F = 0x1541F + 7", "RET_1541F = 0x1541F + 5"),
    ("扣的 MP 改看剩下的", '"mp_spent": UNITS_NEG[u]["mmp"] - UNITS_NEG[u]["mp"]', '"mp_spent": UNITS_NEG[u]["mp"]'),
    ("預期法術依編號排序", 'assert [r["spell"] for r in POS] == [1, 2, 5, 7, 3, 6]', 'assert [r["spell"] for r in POS] == [1, 2, 3, 5, 6, 7]'),
    ("接續點不檢查收到的 k", 'assert c["records"][4]["eax"] == spell, row', 'assert c["records"][4]["eax"] == spell + 1, row'),
    ("場景路徑位址錯 2", "E_SPELL, E_SCENE, E_MAP, E_CALL = 0x153E7, 0x153F2, 0x1540A, 0x1541F",
     "E_SPELL, E_SCENE, E_MAP, E_CALL = 0x153E7, 0x153F0, 0x1540A, 0x1541F"),
    # (C) 第 4 項
    ("hi 含 255", "HI_MODEL = HI ", "HI_MODEL = HI + 1 "),
    ("預測改向下取整", "pred = fade6(src, RED_TGT, T, DIV, HI_MODEL)", "pred = fade6(src, RED_TGT, T, DIV, HI_MODEL, floor=True)"),
    ("上一步用同一個 t", "assert (before[:HI] == fade6(buf, RED_TGT, T + 1, DIV, HI)[:HI]).all()",
     "assert (before[:HI] == fade6(buf, RED_TGT, T, DIV, HI)[:HI]).all()"),
    ("255 寫了的對照用不改的緩衝", "pred_if_written = fade6(src, RED_TGT, T, DIV, HI + 1)[255]", "pred_if_written = fade6(buf, RED_TGT, T, DIV, HI + 1)[255]"),
    ("返回處 = call + 6", 'assert int(DAC["regs_after"]["EIP"], 16) == SITE + 5 + DELTA', 'assert int(DAC["regs_after"]["EIP"], 16) == SITE + 6 + DELTA'),
    # (D) 第 2 項
    ("跨 tick 不減 1", 'cross = [r["tick_after"] - 1 - r["ticks"][0] for r in rows]', 'cross = [r["tick_after"] - r["ticks"][0] for r in rows]'),
    ("迴圈前不記上次推進", "            last_adv = tick", "            last_adv = None"),
    ("P2 不符圈改列相符圈", "for k, (a, x) in enumerate(zip(r[\"adv\"], r[\"redraw_tick_crossings\"])) if a != x]",
     "for k, (a, x) in enumerate(zip(r[\"adv\"], r[\"redraw_tick_crossings\"])) if a == x]"),
    ("P4 要佔全部差距", 'v["child_diff_ms"] > v["redraw_diff_ms"] / 2', 'v["child_diff_ms"] > v["redraw_diff_ms"]'),
    ("P5 方向反過來", 'P["P5"] = max(_rc_med) - min(_rc_med) < min(', 'P["P5"] = max(_rc_med) - min(_rc_med) > min('),
    ("P1 第一輪預期第二輪的階", 'P["P1"] = c["drawn"] == RUN_A and e["drawn"] == RUN_B', 'P["P1"] = c["drawn"] == RUN_B and e["drawn"] == RUN_B'),
    ("貼圖只算單位層直屬", 'N[b]["eip"] in BLITS and N[b]["parent"] == s for b in sub', 'N[b]["eip"] in BLITS and N[b]["parent"] == unit_layer for b in sub'),
    ("wait 判準反過來", "assert min(w_cross) > max(w_none)", "assert max(w_cross) < min(w_none)"),
    ("讀回要求 BAD", 'all(ok == "OK " and w == g for ok, _, w, g in _rb)', 'all(ok == "BAD" and w == g for ok, _, w, g in _rb)'),
    ("名目 tick 改 60 ms", "TICK_MS = 1000 * 65536 / 1193182", "TICK_MS = 1000 * 65536 / 1093182"),
]

if __name__ == "__main__":
    sys.exit(run_mutants("ev_s157", MUTANTS))
