"""續一百三十四證據:evidence/fdicon_mode1_order_map_units_20261017.json。

續一百三十三「仍留的」:四模式 RLE 的模式 1(隔一格)是「先透明再上色」還是「先上色再透明」,在 HUD 圖示框上驗不到
(用到的 sprite 與數字格都沒有模式 1)。同一組傾印的地圖上,敵方單位 #5(+7 = 134)的圖示有模式 1:
(1) 靜態:blit_tile24_rle 0x4e22a 的模式 1 分支是 `lodsb; inc edi; stosb`(先跳一格再寫),地圖單位由 0x1295a 呼叫它,
    原點 0x75d8 = 0x8088 − 6 × 456(上移 6 列);旗標 bit 7 改呼叫灰階版 0x4e1a6(值 = (v & 7) + 0x18)。
(2) 傾印:單位 #5 的 24 × 24 逐像素對 FDICON,模式 1 那一格「跳過的像素」露出背景、「寫入的像素」是原值;
    對調次序、兩格都寫、灰階版都對不上。
全部從 .wsl_build/lc131a_moverange/{D,E,F}/、FDICON.B24、FD2.EXE 與
evidence/hud_icon_hp_digits_20261017.json 重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402

EXE, FDICON = GAME / "FD2.EXE", GAME / "FDICON.B24"
RAW131 = ROOT / ".wsl_build" / "lc131a_moverange"
S133 = ROOT / "docs/knowledge-base/evidence/hud_icon_hp_digits_20261017.json"
OUT = out_path("fdicon_mode1_order_map_units_20261017.json")
ORIGIN, STRIDE, CELL, UNIT_ORIGIN = 0x8088, 456, 24, 0x75D8
VIEW_W, VIEW_H = 13, 8
GREY_MASK, GREY_BASE = 7, 0x18
ENEMY = 5                                        # 單位 #5:+7 = 134,圖示每個姿勢都有模式 1

# 靜態:位元組逐一釘住(FD2.EXE)
CODE = {
    # 0x4e22a 每列開頭:bl = 24 列、bh = 24 欄(每列重新計數)
    0x4E23E: "b318b718",
    # 0x4e22a 模式 1(高 2 bit = 01):cl = 低 6 bit + 1;bh −= 2cl;lodsb 一次;迴圈 inc edi(跳過)再 stosb(寫)
    0x4E25D: "c0e902fec12af92af9ac47aae2fc",
    # 0x4e1a6 灰階版:ah = 7、dl = 0x18、bl = bh = 24
    0x4E1BA: "b407b218b318b718",
    # 0x4e1a6 模式 1:同樣先 inc edi 再 stosb,但值是 (v & 7) + 0x18
    0x4E1E1: "c0e902fec12af92af9ac22c402c247aae2fc",
    # 地圖單位(0x1295a):索引 = slot × 12 + 姿勢 × 3 + 時脈,表 [0x53a61];dst += 0x75d8;[esp] bit 7 → 0x4e1a6,否則 0x4e22a
    0x1291E: "6bff0c89f0c1e00229f001f801d08b15613a00008b048201d081c3d875000085db0f8c01e2fffff60424807516"
             "68c80100008b15493a000001d35350e8cbb80300eb1468c80100008b15493a000001da5250e831b8030083c40c",
}

_D = EXE.read_bytes()
_M = dl.parse_le(_D)
for a, hx in CODE.items():
    got = bytes(dl.object_bytes(_D, _M, a, len(hx) // 2)).hex()
    assert got == hx, (hex(a), got)
# 灰階版的常數取自釘住的位元組:mov ah, 7(遮罩)、mov dl, 0x18(基底)
assert (int(CODE[0x4E1BA][2:4], 16), int(CODE[0x4E1BA][6:8], 16)) == (GREY_MASK, GREY_BASE)
# 0x75d8 = 視窗原點 0x8088 往上 6 條掃描線(doc25 §18.1 的 0xab0 = 6 × 456)
assert UNIT_ORIGIN == ORIGIN - 6 * STRIDE
UNIT_DY = (UNIT_ORIGIN - ORIGIN) // STRIDE

# ================= FDICON:逐 run 解析 =================
_fi = FDICON.read_bytes()
tw, th, n_spr = struct.unpack_from("<HHH", _fi, 0)
assert (tw, th, n_spr) == (24, 24, 1680)
_fo = [struct.unpack_from("<I", _fi, 6 + i * 4)[0] for i in range(n_spr)] + [len(_fi)]


def parse_runs(body: bytes) -> list[tuple[int, int, int, bytes]]:
    """四模式 RLE 逐 run:(模式, 起點像素, 涵蓋像素數, 值);模式 1 涵蓋 2 × (低 6 bit + 1) 格。"""
    out: list[tuple[int, int, int, bytes]] = []
    i = pos = 0
    while pos < 576 and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 0:
            out.append((0, pos, n, body[i:i + 1]))
            i += 1
        elif m == 1:
            out.append((1, pos, 2 * n, body[i:i + 1]))
            i += 1
            n *= 2
        elif m == 2:
            out.append((2, pos, n, body[i:i + n]))
            i += n
        else:
            out.append((3, pos, n, b""))
        pos += n
    return out


RUNS = [parse_runs(_fi[_fo[s]:_fo[s + 1]]) for s in range(n_spr)]
# 組語每列重新從 24 倒數(bh),逐列解;這裡整張平鋪解。兩者相同的前提:沒有 run 跨列,且每張剛好 576 格
assert all(sum(r[2] for r in rs) == 576 for rs in RUNS)
crossing = sum(1 for rs in RUNS for _, p, n, _v in rs if p // 24 != (p + n - 1) // 24)
assert crossing == 0, crossing
mode1_sprites = [s for s in range(n_spr) if any(r[0] == 1 for r in RUNS[s])]
mode1_runs = sum(1 for rs in RUNS for r in rs if r[0] == 1)
assert (len(mode1_sprites), mode1_runs) == (450, 818), (len(mode1_sprites), mode1_runs)


def render(s: int, order: str = "skip_then_value", grey: bool = False) -> list[int | None]:
    """依 run 畫出 sprite;order 是模式 1 的次序假說;grey = 0x4e1a6 的 (v & 7) + 0x18。None = 不寫。"""
    px: list[int | None] = [None] * 576
    for m, p, n, v in RUNS[s]:
        vals: list[int | None]
        if m == 0:
            vals = [v[0]] * n
        elif m == 1:
            pair = {"skip_then_value": [None, v[0]], "value_then_skip": [v[0], None], "value_both": [v[0], v[0]]}[order]
            vals = pair * (n // 2)
        elif m == 2:
            vals = list(v)
        else:
            vals = [None] * n
        if grey:
            vals = [None if x is None else (x & GREY_MASK) + GREY_BASE for x in vals]
        px[p:p + n] = vals
    return px


# ================= 傾印:地圖上的單位 =================
G = {t: json.loads((RAW131 / t / "g.json").read_text(encoding="utf-8")) for t in "DEF"}
units = {t: (RAW131 / t / "units.bin").read_bytes() for t in "DEF"}
bufs = {t: (RAW131 / t / "buf.bin").read_bytes() for t in "DEF"}
assert all(len(b) == 0x25680 for b in bufs.values()) and all(len(u) == 21 * 0x50 for u in units.values())
assert all((G[t]["scroll_x"], G[t]["scroll_y"], G[t]["view_w"], G[t]["view_h"]) == (9, 13, VIEW_W, VIEW_H) for t in "DEF")
SX, SY = G["D"]["scroll_x"], G["D"]["scroll_y"]
ue = {t: units[t][ENEMY * 0x50:(ENEMY + 1) * 0x50] for t in "DEF"}
EX, EY, EKEY = ue["D"][0], ue["D"][1], ue["D"][7]
assert all((ue[t][0], ue[t][1], ue[t][7]) == (EX, EY, EKEY) for t in "DEF")
assert (EX, EY, EKEY, ue["D"][6]) == (16, 14, 134, 1), (EX, EY, EKEY, ue["D"][6])   # 敵方(camp 1)
assert SX <= EX < SX + VIEW_W and SY + 1 <= EY < SY + VIEW_H                          # 在視窗內、上移 6 列也不出界
# 這組 12 格每個姿勢都有模式 1
grp_mode1 = [sum(r[0] == 1 for r in RUNS[EKEY * 12 + j]) for j in range(12)]
assert grp_mode1 == [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0], grp_mode1

BX, BY = (EX - SX) * CELL, (EY - SY) * CELL + UNIT_DY


def mismatch(px: list[int | None], t: str, bx: int = BX, by: int = BY) -> tuple[int, int]:
    known = [k for k in range(576) if px[k] is not None]
    return len(known), sum(px[k] != bufs[t][ORIGIN + (by + k // 24) * STRIDE + bx + k % 24] for k in known)


blank = [s for s in range(n_spr) if all(r[0] == 3 for r in RUNS[s])]
assert len(blank) == 225, len(blank)
# 1455 個非空白 sprite 在這個位置只有一個全中(全透明的不算:沒有像素可比)
exact = {t: [s for s in range(n_spr) if s not in blank and mismatch(render(s), t)[1] == 0] for t in "DEF"}
assert exact == {"D": [EKEY * 12 + 1], "E": [EKEY * 12 + 1], "F": [EKEY * 12 + 0]}, exact
fit = {t: mismatch(render(exact[t][0]), t) for t in "DEF"}
assert fit == {"D": (437, 0), "E": (437, 0), "F": (442, 0)}, fit
# 時脈與續一百三十三的索爾一致:同一幀的 [0x53c0b] 由 HUD 圖示推得 D、E 為 cycle 1、F 為 0
_s133 = json.loads(S133.read_text(encoding="utf-8"))
sol_cycle = {t: _s133["exact_sprite_matches_nonblank"][t][0] % 12 for t in "DEF"}
assert sol_cycle == {t: exact[t][0] % 12 for t in "DEF"} == {"D": 1, "E": 1, "F": 0}, sol_cycle
# 上下錯一列對不上:上移 6 列是唯一的位置
shift = {dy: {t: mismatch(render(exact[t][0]), t, BX, BY + dy) for t in "DF"} for dy in (-1, 1)}
assert all(bad > 0 for d in shift.values() for _, bad in d.values()), shift
assert shift == {-1: {"D": (437, 338), "F": (442, 336)}, 1: {"D": (437, 338), "F": (442, 336)}}, shift

# ================= 模式 1 的像素 =================
m1_pixels = {}
for t in "DEF":
    s = exact[t][0]
    rs = [r for r in RUNS[s] if r[0] == 1]
    assert len(rs) == 1 and rs[0][2] == 2, rs                 # 只有一個模式 1,長度 1(兩格)
    _, p, _n, v = rs[0]
    skip_px, val_px = (BX + p % 24, BY + p // 24), (BX + (p + 1) % 24, BY + (p + 1) // 24)
    got_skip = bufs[t][ORIGIN + skip_px[1] * STRIDE + skip_px[0]]
    got_val = bufs[t][ORIGIN + val_px[1] * STRIDE + val_px[0]]
    m1_pixels[t] = {"sprite": s, "cell_xy": [p % 24, p // 24], "value": v[0], "buf_at_skipped": got_skip,
                    "buf_at_written": got_val}
    # 判準:寫入的格 = 原值;跳過的格 ≠ 原值(所以「先寫」或「兩格都寫」會在跳過那格露餡)
    assert got_val == v[0] and got_skip != v[0], m1_pixels[t]
assert m1_pixels["D"]["sprite"] != m1_pixels["F"]["sprite"] and m1_pixels["D"]["cell_xy"] != m1_pixels["F"]["cell_xy"]
# 位置與 render() 一致:跳過的格在合成裡是透明、寫入的格是值;實測值釘住
for t in "DEF":
    cx, cy = m1_pixels[t]["cell_xy"]
    px = render(m1_pixels[t]["sprite"])
    assert px[cy * 24 + cx] is None and px[cy * 24 + cx + 1] == m1_pixels[t]["value"], (t, cx, cy)
    assert bufs[t][ORIGIN + (BY + cy) * STRIDE + BX + cx] == m1_pixels[t]["buf_at_skipped"]
assert {t: (m["cell_xy"], m["buf_at_skipped"]) for t, m in m1_pixels.items()} == {
    "D": ([20, 22], 109), "E": ([20, 22], 109), "F": ([20, 20], 107)}, m1_pixels

# 對照:對調次序、兩格都寫、灰階版 —— 都必須對不上(不符數逐一釘住)
controls = {
    "value_then_skip": {t: mismatch(render(exact[t][0], "value_then_skip"), t) for t in "DF"},
    "value_both": {t: mismatch(render(exact[t][0], "value_both"), t) for t in "DF"},
    "grey_0x4e1a6": {t: mismatch(render(exact[t][0], grey=True), t) for t in "DF"},
}
for name, c in controls.items():
    assert all(bad > 0 for _, bad in c.values()), (name, c)
assert controls == {
    "value_then_skip": {"D": (437, 1), "F": (442, 1)}, "value_both": {"D": (438, 1), "F": (443, 1)},
    "grey_0x4e1a6": {"D": (437, 437), "F": (442, 442)}}, controls

ev = {
    "_meta": {"topic": "續一百三十四:四模式 RLE 模式 1 的次序(先跳過再寫),以地圖上敵方單位 #5 的 FDICON 圖示驗",
              "exe": rel(EXE), "exe_md5": hashlib.md5(_D).hexdigest(),
              "assets": {rel(FDICON): hashlib.sha256(_fi).hexdigest()},
              "raw": {f"{t}/{f}": hashlib.sha256((RAW131 / t / f).read_bytes()).hexdigest()
                      for t in "DEF" for f in ("buf.bin", "units.bin", "g.json")},
              "s133_evidence": rel(S133),
              "generator": "evidence/generators/ev_s134.py(變異測試 mut_s134.py)",
              "harness": "傾印是續一百三十一的 D/E/F(DOSBox-X 除錯器,停在 draw_terrain_layer 入口,緩衝是上一幀畫完的畫面);本輪沒有開新的 instance"},
    "static_code": {hex(a): hx for a, hx in CODE.items()},
    "unit_draw": {"origin": hex(UNIT_ORIGIN), "dy_rows": UNIT_DY, "scroll": [SX, SY]},
    "fdicon_runs": {"sprites": n_spr, "blank": len(blank), "row_crossing_runs": crossing,
                    "sprites_with_mode1": len(mode1_sprites), "mode1_runs": mode1_runs},
    "enemy_unit": {"index": ENEMY, "cell": [EX, EY], "key_+7": EKEY, "group_mode1_runs": grp_mode1},
    "exact_sprite_matches_nonblank": exact,
    "fit_known_bad": fit,
    "row_shift_known_bad": {str(k): v for k, v in shift.items()},
    "mode1_pixels": m1_pixels,
    "controls_known_bad": controls,
    "status": {
        "mode1_order": "CODE + LOG CONFIRMED:模式 1 = 先跳過一格再寫值(0x4e25d 的 inc edi; stosb)。"
                       "敵方單位 #5 的圖示 D、E 是 sprite 1609、F 是 1608(+7 = 134,cycle 1 / 0),1455 個非空白 sprite 裡各只有這一個全中"
                       "(已知像素 437 / 442 個);兩張各有一個模式 1(長度 1),寫入的格是原值 254,跳過的格露出背景 109 / 107。"
                       "對調次序、兩格都寫、灰階版 0x4e1a6 都對不上。",
        "scope": "只驗到長度 1 的模式 1,共兩個(兩張 sprite 各一);較長的模式 1 run 沒有在畫面上出現。"
                 "FDICON 全部 818 個模式 1 run(450 張)與其他 run 都不跨列,所以整張平鋪解與組語逐列解相同",
        "unit_draw_origin": "CODE + LOG CONFIRMED:地圖單位的原點 0x75d8 = 0x8088 − 6 × 456(上移 6 列);上下錯一列對不上",
        "draw_list_entry": "INFERRED:單位 #5 走 0x4e22a(旗標 bit 7 清除)、姿勢 0、時脈 1 / 0 是由像素推得;繪製清單 [0x53a45] 沒有傾印",
        "clock": "與續一百三十三的索爾一致:同一幀的時脈 D、E 為 1、F 為 0",
    },
}


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
