"""續一百三十三證據:evidence/hud_icon_hp_digits_20261017.json。

(1) 續一百三十二只核對到「(10, 20) 的差異在 draw_map_hud 的單位圖示框裡」,框裡畫的內容沒有逐像素核對。
    這裡把框的 24 × 24 像素逐一合成:先貼 FDICON.B24 的單位圖示(表 [0x53a61] 的 cache slot × 12 + 時脈),
    再把 HP 數字(0x1875d → 0x187d6,FDOTHER #5 的 6 × 8 數字格)蓋在框的下 8 列;三幀傾印必須逐像素相符,
    而且 1680 個 sprite 裡只有一個對得上。
(2) lc131a 第 6 圈畫 6(lc131b、lc131d 畫 7):從續一百三十二已提交證據的 tick 算出原因。
全部從 .wsl_build/lc131a_moverange/{D,E,F}/、FDICON.B24、FDOTHER.DAT、FD2.EXE 與
evidence/phase_loop_runB_hud_icon_20261017.json 重算;任何判準或預測不符就 assert 失敗。
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Callable

from _evpaths import GAME, ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(ROOT / "tools"))
import disasm_le as dl  # noqa: E402
import unpack_dat  # noqa: E402

EXE, FDICON, FDOTHER = GAME / "FD2.EXE", GAME / "FDICON.B24", GAME / "FDOTHER.DAT"
RAW131 = ROOT / ".wsl_build" / "lc131a_moverange"
S132 = ROOT / "docs/knowledge-base/evidence/phase_loop_runB_hud_icon_20261017.json"
OUT = out_path("hud_icon_hp_digits_20261017.json")
ORIGIN, STRIDE, CELL = 0x8088, 456, 24
BOX_X, BOX_Y = 1 + 6, 0x9D + 5                  # 圖示框左上(視窗像素):[0x51a0c] 初值 1 + 6、列 0x9d + 5(續一百三十二)
HP_X, HP_Y = 1 + 9, 0x9D + 0x15                 # HP 數字左上:ebp + stride × 0x15 + 9
DIGIT_ADV, FULL_COLOR, PART_COLOR, WIDTH_MODE = 6, 0x1F, 0x2A, 3

# 靜態:位元組逐一釘住(FD2.EXE;obj2 位移是檔案內的未重定位值)
CODE = {
    # draw_map_hud 畫完圖示後:0x1875d(ebp + stride × 0x15 + 9, stride, 單位 +0x40, 單位 +0x42, 3)
    0x1AE8E: "0fb746400fb756426a035250576bff1501fd83c50955e8b4d8ffff83c414",
    # 0x1875d:色 = 現值 == 上限 ? 0x1f : 0x2a,再呼叫 0x187d6(dst, stride, 現值, 色, 位數)
    0x18767: "b82a0000008b54240c3b5424107505b81f000000ff74241450ff742414ff742414ff742414e84500000083c414",
    # 0x187d6 開頭:格式字串從 0x51ebf 複製 6 bytes;負值當 0
    0x187E7: "8b6c24348b4424388d7c2414bebf1e0000a566a585c07d0231c0",
    # 格式第 3 字改成 '0' + 位數 → "%0.3d";逐字元:數字格索引 = 字元 − '0' + 色,x 每位 + 6,呼叫 0x16886
    0x1883C: "8a5c244080c330885c2417508d442418508d44240850e8d2f2010083c40c31dbeb240fb6041c0344243c83e83050ff35813a0000"
             "556bc3060344243c50e808e0ffff83c410433b5c24407cd6",
    # 0x16886:src = 容器 + [容器 + 6 + 索引 × 4];0x4e98d(src, 0, 0, dst, stride, -1)(-1 = 原值複製)
    0x16891: "8b5424108b442414035482066affff742410ff7424106a006a0052e8dc80030083c418",
    0x51EBF: "25302e356400",                                   # "%0.5d"
}

_D = EXE.read_bytes()
_M = dl.parse_le(_D)
for a, hx in CODE.items():
    got = bytes(dl.object_bytes(_D, _M, a, len(hx) // 2)).hex()
    assert got == hx, (hex(a), got)

# ================= 輸入:游標下的單位 =================
g = json.loads((RAW131 / "D" / "g.json").read_text(encoding="utf-8"))
units = {t: (RAW131 / t / "units.bin").read_bytes() for t in "DEF"}
bufs = {t: (RAW131 / t / "buf.bin").read_bytes() for t in "DEF"}
assert all(len(b) == 0x25680 for b in bufs.values()) and all(len(u) == 21 * 0x50 for u in units.values())
cur = (g["cursor_x"], g["cursor_y"])
at = [i for i in range(21) if (units["D"][i * 0x50], units["D"][i * 0x50 + 1]) == cur]
assert at == [0], (cur, at)
u = {t: units[t][:0x50] for t in "DEF"}
slot, key = u["D"][2], u["D"][7]
hp = {t: struct.unpack_from("<HH", u[t], 0x40) for t in "DEF"}
assert (slot, key) == (0, 32), (slot, key)
assert all(u[t][2] == slot and u[t][7] == key for t in "DEF")
assert hp == {t: (823, 823) for t in "DEF"}, hp                  # 滿血 → 色 0x1f
# draw_map_hud 的略過條件(+7 == 0x79;+0x1f == 0xa 且 +6 == 1)都不成立
assert key != 0x79 and not (u["D"][0x1F] == 0xA and u["D"][6] == 1)


# ================= 解碼 =================
def dec4(body: bytes, w: int, h: int) -> list[int | None]:
    """四模式 RLE(高 2 bit:0 同色 run、1 隔一格、2 原值、3 透明);None = 透明。"""
    out: list[int | None] = []
    i = 0
    while len(out) < w * h and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 0:
            out += [body[i]] * n
            i += 1
        elif m == 1:
            out += [None, body[i]] * n
            i += 1
        elif m == 2:
            out += list(body[i:i + n])
            i += n
        else:
            out += [None] * n
    return (out + [None] * (w * h))[:w * h]


def mode1_runs(body: bytes, total: int) -> int:
    """四模式 RLE 裡模式 1(隔一格)的控制位元組個數;0 代表這張圖驗不到模式 1 的次序。"""
    i = n = runs = 0
    while n < total and i < len(body):
        c = body[i]
        i += 1
        m, k = c >> 6, (c & 63) + 1
        if m == 1:
            runs += 1
        if m in (0, 1):
            i += 1
            n += k * (2 if m == 1 else 1)
        elif m == 2:
            i += k
            n += k
        else:
            n += k
    return runs


def dec_c0(body: bytes, w: int, h: int) -> list[int | None]:
    """對照:0x4e916 的 0xC0 codec(c <= 0xC0 單像素,否則 run);0 = 透明。"""
    out: list[int] = []
    i = 0
    while len(out) < w * h and i < len(body):
        c = body[i]
        i += 1
        if c <= 0xC0:
            out.append(c)
        else:
            out += [body[i]] * (c - 0xC0)
            i += 1
    return [None if v == 0 else v for v in (out + [0] * (w * h))[:w * h]]


_fi = FDICON.read_bytes()
tw, th, n_spr = struct.unpack_from("<HHH", _fi, 0)
assert (tw, th, n_spr) == (24, 24, 1680)
_fo = [struct.unpack_from("<I", _fi, 6 + i * 4)[0] for i in range(n_spr)] + [len(_fi)]
SPR = [dec4(_fi[_fo[i]:_fo[i + 1]], 24, 24) for i in range(n_spr)]

_fd = FDOTHER.read_bytes()
_o, _n = unpack_dat.parse_directory(_fd)[5]
LMI = _fd[_o:_o + _n]
assert LMI[:4] == b"LMI1"
_lo = [struct.unpack_from("<I", LMI, 6 + 4 * i)[0] for i in range(struct.unpack_from("<H", LMI, 4)[0])]


def digit(idx: int, codec: Callable) -> tuple[int, int, list[int | None]]:
    w, h = struct.unpack_from("<HH", LMI, _lo[idx])
    return w, h, codec(LMI[_lo[idx] + 4:], w, h)


def compose(sidx: int | None, color: int = FULL_COLOR, codec: Callable = dec4, adv: int = DIGIT_ADV,
            dy: int = 0, value: int = 823) -> list[int | None]:
    """圖示框 24 × 24 的合成:sprite(None = 不畫)再蓋 "%0.3d" 的數字格;None = 兩者都透明(露出地形)。"""
    comp = list(SPR[sidx]) if sidx is not None else [None] * 576
    for j, ch in enumerate(f"{value:03d}"):
        w, h, px = digit(int(ch) + color, codec)
        for k, v in enumerate(px):
            x, y = HP_X - BOX_X + adv * j + k % w, HP_Y - BOX_Y + dy + k // w
            if v is not None and 0 <= x < 24 and 0 <= y < 24:
                comp[y * 24 + x] = v
    return comp


BOX = {t: [bufs[t][ORIGIN + (BOX_Y + k // 24) * STRIDE + BOX_X + k % 24] for k in range(576)] for t in "DEF"}


def mismatch(comp: list[int | None], t: str) -> tuple[int, int]:
    known = [k for k in range(576) if comp[k] is not None]
    return len(known), sum(comp[k] != BOX[t][k] for k in known)


# ================= (1) 逐像素:1455 個非空白 sprite 裡只有一個對得上 =================
# 全透明的 sprite 合成後只剩數字格,一定「全中」,不能算對上;只比有不透明像素的 sprite
blank = [i for i in range(n_spr) if all(v is None for v in SPR[i])]
assert len(blank) == 225, len(blank)
exact = {t: [i for i in range(n_spr) if i not in blank and mismatch(compose(i), t)[1] == 0] for t in "DEF"}
assert exact == {"D": [key * 12 + 1], "E": [key * 12 + 1], "F": [key * 12 + 0]}, exact
fit = {t: mismatch(compose(exact[t][0]), t) for t in "DEF"}
assert fit == {"D": (463, 0), "E": (463, 0), "F": (478, 0)}, fit

# 對照:換色組(非滿血)、換 codec、數字間距 7、數字上下錯一列、不畫數字、換 cycle —— 都必須對不上
controls = {
    "color_0x2a": {t: mismatch(compose(exact[t][0], color=PART_COLOR), t) for t in "DF"},
    "codec_c0": {t: mismatch(compose(exact[t][0], codec=dec_c0), t) for t in "DF"},
    "advance_7": {t: mismatch(compose(exact[t][0], adv=7), t) for t in "DF"},
    "digits_dy_-1": {t: mismatch(compose(exact[t][0], dy=-1), t) for t in "DF"},
    "digits_dy_+1": {t: mismatch(compose(exact[t][0], dy=1), t) for t in "DF"},
    "no_digits": {t: mismatch(SPR[exact[t][0]], t) for t in "DF"},
    "swap_cycle": {"D": mismatch(compose(exact["F"][0]), "D"), "F": mismatch(compose(exact["D"][0]), "F")},
    "hp_822": {t: mismatch(compose(exact[t][0], value=822), t) for t in "DF"},
}
for name, c in controls.items():
    assert all(bad > 0 for _, bad in c.values()), (name, c)
# 實測值釘住(已知像素數、不符數)
assert controls == {
    "color_0x2a": {"D": (463, 63), "F": (478, 63)}, "codec_c0": {"D": (465, 124), "F": (481, 122)},
    "advance_7": {"D": (466, 70), "F": (481, 69)}, "digits_dy_-1": {"D": (463, 108), "F": (470, 101)},
    "digits_dy_+1": {"D": (464, 97), "F": (479, 95)}, "no_digits": {"D": (455, 93), "F": (462, 85)},
    "swap_cycle": {"D": (478, 287), "F": (463, 272)}, "hp_822": {"D": (463, 15), "F": (478, 15)}}, controls
# 只看數字格:三個數字自己的不透明像素(不含 sprite)也要全中
digits_only = {t: mismatch(compose(None), t) for t in "DEF"}
assert all(bad == 0 and known > 0 for known, bad in digits_only.values()), digits_only

# 兩幀都露出地形的像素(sprite、數字都透明)三幀相同;D-F 的差異全部落在合成有值的像素
cD, cF = compose(exact["D"][0]), compose(exact["F"][0])
both_open = [k for k in range(576) if cD[k] is None and cF[k] is None]
assert all(BOX["D"][k] == BOX["E"][k] == BOX["F"][k] for k in both_open)
diff_DF = {k for k in range(576) if BOX["D"][k] != BOX["F"][k]}
assert BOX["D"] == BOX["E"]
assert diff_DF <= {k for k in range(576) if cD[k] is not None or cF[k] is not None}
assert {k for k in range(576) if cD[k] is not None and cF[k] is not None and cD[k] != cF[k]} <= diff_DF
# 與續一百三十二相接:框內落在 (10, 20) 格(視窗 x 24..47、列 168..191,同 ev_s132 的 seed)的差異 = 那 53 個像素
in_cell_10_20 = sum(CELL <= BOX_X + k % 24 < 2 * CELL and 7 * CELL <= BOX_Y + k // 24 < 8 * CELL for k in diff_DF)
assert in_cell_10_20 == 53, in_cell_10_20
# 範圍:用到的兩張 sprite 與數字 8、2、3 都沒有模式 1,模式 1 的次序(先透明或先上色)這裡驗不到
used_mode1 = {**{f"sprite_{s}": mode1_runs(_fi[_fo[s]:_fo[s + 1]], 576) for s in (exact["D"][0], exact["F"][0])},
              **{f"digit_{c}": mode1_runs(LMI[_lo[FULL_COLOR + int(c)] + 4:], 48) for c in "823"}}
assert sum(used_mode1.values()) == 0, used_mode1
# 正向對照:同一組數字格裡「5」(#36)有 1 個模式 1,計數函式要數得到
mode1_digits = [mode1_runs(LMI[_lo[FULL_COLOR + d] + 4:], 48) for d in range(10)]
assert mode1_digits == [0, 0, 0, 0, 0, 1, 0, 0, 0, 0], mode1_digits
_s132 = json.loads(S132.read_text(encoding="utf-8"))
# 續一百三十二的列帶差異(x < 48、列在框內,框外 0 個)= 這裡框內的差異數
assert len(diff_DF) == _s132["hud_pairs"]["D-F"]["band_diffs"] == _s132["hud_pairs"]["E-F"]["band_diffs"], len(diff_DF)

# ================= (2) lc131a 第 6 圈畫 6 =================
s132 = _s132["runs"]
r6 = {}
for n in ("lc131a", "lc131b", "lc131d"):
    r = s132[n]
    k4 = r["tick_at_draw"][3]                    # 三份都在第 4 圈推進
    assert r["adv"][3] == 1, (n, r["adv"])
    k6 = r["tick_at_draw"][5]
    r6[n] = {"tick_k4": k4, "tick_k6": k6, "gap": k6 - k4,
             "crossings_k4_k5": r["redraw_tick_crossings"][3:5], "adv_k5_k6": r["adv"][4:6],
             "drawn_k6": r["drawn"][5]}
assert r6["lc131a"]["gap"] == 2 and r6["lc131a"]["adv_k5_k6"] == [0, 0] and r6["lc131a"]["drawn_k6"] == 6, r6
assert r6["lc131a"]["crossings_k4_k5"] == [0, 0], r6
for n in ("lc131b", "lc131d"):
    assert r6[n]["gap"] >= 3 and r6[n]["adv_k5_k6"] == [0, 1] and r6[n]["drawn_k6"] == 7, r6
    assert r6[n]["crossings_k4_k5"][1] == 1, r6  # 第 5 圈 redraw 跨了 1 個 tick

ev = {
    "_meta": {"topic": "續一百三十三:draw_map_hud 單位圖示框逐像素 = FDICON 單位圖示 + HP 數字格;lc131a 第 6 圈畫 6 的原因",
              "exe": rel(EXE), "exe_md5": hashlib.md5(_D).hexdigest(),
              "assets": {rel(FDICON): hashlib.sha256(_fi).hexdigest(), rel(FDOTHER): hashlib.sha256(_fd).hexdigest()},
              "raw": {f"{t}/{f}": hashlib.sha256((RAW131 / t / f).read_bytes()).hexdigest()
                      for t in "DEF" for f in ("buf.bin", "units.bin")} | {"D/g.json": hashlib.sha256((RAW131 / "D" / "g.json").read_bytes()).hexdigest()},
              "s132_evidence": rel(S132),
              "generator": "evidence/generators/ev_s133.py(變異測試 mut_s133.py)",
              "harness": "傾印是續一百三十一的 D/E/F(DOSBox-X 除錯器,停在 draw_terrain_layer 入口,緩衝是上一幀畫完的畫面);本輪沒有開新的 instance"},
    "static_code": {hex(a): hx for a, hx in CODE.items()},
    "cursor_unit": {"index": at[0], "cell": list(cur), "slot_+2": slot, "key_+7": key, "hp_+40_+42": hp["D"]},
    "box_view_px": {"x0": BOX_X, "y0": BOX_Y, "hp_x0": HP_X, "hp_y0": HP_Y},
    "blank_sprites": len(blank),
    "exact_sprite_matches_nonblank": exact,
    "fit_known_bad": fit,
    "digits_only_known_bad": digits_only,
    "controls_known_bad": controls,
    "mode1_runs_in_used_cells": used_mode1,
    "both_transparent_pixels": len(both_open),
    "diff_D_F_in_box": len(diff_DF),
    "diff_D_F_in_cell_10_20": in_cell_10_20,
    "lc131a_k6": r6,
    "status": {
        "hud_icon_pixels": "CODE + LOG CONFIRMED:圖示框 24 × 24 = FDICON sprite 再蓋 HP 數字。D、E 是 sprite 385、F 是 384"
                           "(第 32 組 = 游標下索爾的 +7,cycle 1 / 0),1455 個非空白 sprite 裡各只有這一個對得上(已知像素 463 / 478 個全中;"
                           "另 225 個全透明的 sprite 合成後只剩數字格,不算);"
                           "HP 823 / 823 滿血,數字格 = FDOTHER #5 的 #31 + 位數(四模式 RLE),間距 6,蓋在框的下 8 列。"
                           "換色組 0x2a、0xC0 codec、間距 7、上下錯一列、不畫數字、對調 cycle、HP 822 都對不上。"
                           "範圍:用到的 sprite 與數字 8、2、3 都沒有模式 1(隔一格),所以模式 1 的次序這裡沒有驗到",
        "cache_slot": "INFERRED:單位 +2 = 0(cache slot 0)的 12 格對到 FDICON 第 32 組(+7 = 32);cache 本身沒有傾印,是由像素唯一相符推得",
        "clock": "INFERRED:D、E 的 [0x53c0b] 是 1 或 3(HUD 把 3 當 1),F 是 0;時脈值沒有傾印",
        "s132_link": "D-F 在框內的差異有 " + str(len(diff_DF)) + " 個像素,其中落在 (10, 20) 格(視窗 x 24..47、列 168..191)的 53 個就是續一百三十一那 53 個;"
                     "兩幀都透明的像素(地形)三幀相同",
        "lc131a_k6": "LOG CONFIRMED(續一百三十二已提交的 tick):三份都在第 4 圈推進;lc131a 第 4、5 圈 redraw 都沒跨 tick,"
                     "第 6 圈的 tick 只比上次推進多 2(不大於 2)所以不推進、畫 6;lc131b、lc131d 第 5 圈跨 1 個 tick,差 3、4,第 6 圈推進、畫 7。"
                     "redraw 為什麼有時跨、有時不跨沒有量",
    },
}


def write() -> None:
    OUT.write_text(json.dumps(ev, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ok", OUT.name, len(OUT.read_bytes()))


if __name__ == "__main__":
    write()
