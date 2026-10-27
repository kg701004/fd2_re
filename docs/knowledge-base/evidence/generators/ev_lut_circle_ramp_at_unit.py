"""續一百二十二證據:evidence/lut_circle_ramp_at_unit_20261013.json。

lc122 三組實機紀錄(法術 12、法術 11、敵 #11 用道具 79)每幀的換色範圍與 doc35 §18 的圓形預測逐列比對,
另比對視窗截圖與傾印幀。原本由暫存的 mk_evidence122.py + an122.py 產生(續一百二十二);
續一百三十四移進倉庫,原始紀錄放在 .wsl_build/lc122_live/(傾印、調色盤、記錄 JSON)與 .wsl_build/lc122_shots/(視窗截圖)。
傾印幀的 PNG 與拼接圖在這裡由 .bin + 調色盤重畫(不讀暫存目錄產生的 PNG);拼接圖與已提交的 PNG 逐像素比對。
續一百五十六:形狀改成逐像素的精確預測(remap_circle_scanlines 的換色段 + FDOTHER #3 第 i 張換色表),取代邊緣容差;
另排除游標格(效果幀的底圖沒有,基準畫面的重畫有)。
"""
from __future__ import annotations

import hashlib
import json
import math
import struct

import numpy as np
from PIL import Image, ImageChops, ImageStat

from _evpaths import EVIDENCE, GAME, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)

D = ROOT / ".wsl_build" / "lc122_live"
S = ROOT / ".wsl_build" / "lc122_shots"
OUT = out_path("lut_circle_ramp_at_unit_20261013.json")
W = 320
VX0, VY0, VW, VH = 4, 4, 0x138, 0xC0  # copy_rect 貼到畫面的視窗
VX1, VY1 = VX0 + VW - 1, VY0 + VH - 1
ROWS, COLS = range(VY0, VY0 + VH), range(VX0, VX0 + VW)  # 視窗內的列 / 欄
# 亮度權重(百分比)= ITU-R BT.601 的 0.299 / 0.587 / 0.114 四捨五入;權重和當除數,灰色的亮度就是它自己
LUMA = (30, 59, 11)
assert LUMA == tuple(round(100 * w) for w in (0.299, 0.587, 0.114)), LUMA
# 視窗 = 基準畫面裡非 0 像素的外框(四周是 0 的框)
for _t in ("s12", "s11", "ai79"):
    _x0, _y0, _x1, _y1 = Image.frombytes("P", (W, 200), (D / f"{_t}_ref.bin").read_bytes()).getbbox()
    assert (_x0, _y0, _x1 - 1, _y1 - 1) == (VX0, VY0, VX1, VY1), (_t, (_x0, _y0, _x1, _y1))
from _exeops import insn, operand  # noqa: E402
# draw_unit_sprite(0x127e0):目的位址 = (y − 捲動) × 24 列 × 456 + (x − 捲動) × 0x18 + 0x75d8(0x12937),
# 視窗原點在 work buffer 的 0x8088(0x1dc85,present 的來源),所以單位圖比格子上移 (0x8088 − 0x75d8) / 456 列;
# 圖由 blit_tile24_rle(0x4e22a)畫,24 列 × 24 欄(doc35 §18、doc25 §18.1)
TILE = operand(0x128D9, "imul ebp, ebp, ")
STRIDE = operand(0x1294B, "push ")
assert STRIDE == operand(0x1DC7A, "push "), STRIDE
SPRITE_UP, _col = divmod(operand(0x1DC85, "add edx, ") - operand(0x12937, "add ebx, "), STRIDE)
assert _col == 0, _col  # 同一欄,只差列
SPR_H, SPR_W = operand(0x4E23E, "mov bl, "), operand(0x4E240, "mov bh, ")
assert SPR_W == TILE, (SPR_W, TILE)


def unit_box(tx: int, ty: int) -> tuple[int, int, int, int]:
    """視窗內第 (tx, ty) 格上的單位圖範圍(含端點),超出視窗的部分裁掉。"""
    x0, y0 = VX0 + TILE * tx, VY0 + TILE * ty - SPRITE_UP
    return x0, max(VY0, y0), x0 + SPR_W - 1, min(VY1, y0 + SPR_H - 1)


import disasm_le as dl  # noqa: E402(_exeops 已把 tools/ 加進 sys.path)
import unpack_dat  # noqa: E402


def dec4(body: bytes, w: int, h: int) -> np.ndarray:
    """四模式 RLE(模式 1 = 先跳過再寫,續一百三十四),回傳 h × w;-1 = 不寫。"""
    out = np.full(w * h, -1, np.int16)
    i = pos = 0
    while pos < w * h and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 0:
            out[pos:pos + n] = body[i]
            i += 1
            pos += n
        elif m == 1:
            out[pos + 1:pos + 2 * n:2] = body[i]
            i += 1
            pos += 2 * n
        elif m == 2:
            out[pos:pos + n] = list(body[i:i + n])
            i += n
            pos += n
        else:
            pos += n
    return out.reshape(h, w)


# 左下的資訊框是 draw_map_hud(0x1acf3)畫的:FDOTHER #5(`[0x53a81]`)第 (0x20e − 6) / 4 格(LMI1 目錄 +6 起每格 4 bytes),
# 由 0x4e98d 貼在視窗 (`[0x51a0c]`, 0x9d);接著在框內 (+6, +5) 貼 24 × 24 的單位圖示(blit_tile24_rle)、
# 由 (+0x2b, +8) 起畫地形 A / D 數字。`[0x51a0c]` 的值只有初值與 0x1ad3c / 0x1ad5a 兩處寫入(游標在下方左 / 右時切換,
# 之後留著),這一次是哪一個由基準畫面定:在那個位置上框的像素與資源相同(圖示與數字蓋過的除外),另一個位置一個都不同
_EXE = (GAME / "FD2.EXE").read_bytes()
_META = dl.parse_le(_EXE)
_FX = dl.build_fixups(_EXE, _META)
_XVAR = _FX[0x1AD6E]  # 0x1ad6c `add ebp, dword ptr [disp32]` 的位移欄位
assert _FX[0x1AD3E] == _FX[0x1AD5C] == _XVAR, hex(_XVAR)
PANEL_XS = sorted({struct.unpack("<i", bytes(dl.object_bytes(_EXE, _META, _XVAR, 4)))[0],
                   operand(0x1AD3C, "mov dword ptr [0x1a0c], "), operand(0x1AD5A, "mov dword ptr [0x1a0c], ")})
assert len(PANEL_XS) == 2, PANEL_XS
PANEL_ROW = operand(0x1AD64, "imul eax, edi, ")
_res, _rem = divmod(operand(0x1AD77, "add eax, dword ptr [eax + ", "]") - 6, 4)
assert _rem == 0, _rem
_fd = (GAME / "FDOTHER.DAT").read_bytes()
_o, _n = unpack_dat.parse_directory(_fd)[5]
_LMI = _fd[_o:_o + _n]
assert _LMI[:4] == b"LMI1"
_lo = [struct.unpack_from("<I", _LMI, 6 + 4 * i)[0] for i in range(struct.unpack_from("<H", _LMI, 4)[0])]
PW, PH = struct.unpack_from("<HH", _LMI, _lo[_res])
PANEL_PX = dec4(_LMI[_lo[_res] + 4:_lo[_res + 1]], PW, PH)
ICON_X, ICON_Y = operand(0x1ADBF, "add esi, "), (1 << operand(0x1ADB8, "shl esi, ")) + 1  # edi × 4 + edi 列
TERR_X, TERR_Y = operand(0x1ADE0, "add eax, "), 1 << operand(0x1ADDB, "shl eax, ")


def panel_match(tag: str, px: int) -> tuple[int, list[tuple[int, int]]]:
    """資訊框貼在視窗 (px, PANEL_ROW) 時:框內與基準畫面相同的像素數、不同的像素(框內座標)。"""
    ref = np.frombuffer((D / f"{tag}_ref.bin").read_bytes(), np.uint8).reshape(-1, W)
    x0, y0 = VX0 + px, VY0 + PANEL_ROW
    known = PANEL_PX >= 0
    same = known & (ref[y0:y0 + PH, x0:x0 + PW] == PANEL_PX)
    return int(same.sum()), [(int(x), int(y)) for y, x in zip(*np.nonzero(known & ~same))]


PANEL_AT = {}
for _t in ("s12", "s11"):
    _hit = [(px, *panel_match(_t, px)) for px in PANEL_XS]
    (_px, _same, _bad), = [h for h in _hit if h[1]]  # 只有一個位置有相同的像素
    assert all(ICON_X <= x < ICON_X + SPR_W and ICON_Y <= y < ICON_Y + SPR_H or x >= TERR_X and y >= TERR_Y
               for x, y in _bad), (_t, _bad[:5])
    PANEL_AT[_t] = _px
assert PANEL_AT["s12"] == PANEL_AT["s11"], PANEL_AT
PANEL = [(VX0 + PANEL_AT["s12"], VY0 + PANEL_ROW, VX0 + PANEL_AT["s12"] + PW - 1, min(VY1, VY0 + PANEL_ROW + PH - 1))]
# 施法者所在的格 = 紀錄的 unit_xy − scroll(同一次記錄)
_LOG = {t: json.loads((D / f"{t}.json").read_text(encoding="utf-8"))["entry"] for t in ("s12", "s11", "ai79")}
CASTER = {t: tuple(u - s for u, s in zip(e["unit_xy"], e["scroll"])) for t, e in _LOG.items()}
assert CASTER["s12"] == CASTER["s11"], CASTER
# 單位所在的格:該格的單位圖位置上正好畫著某一張 FDICON 單位圖(可見像素全部相同、至少一個可見),10 幀相同;
# 施法者的格(紀錄)要在裡面。基準畫面不用:游標框與資訊框蓋住了幾個單位。
# (續一百五十五以前是手寫的格;續一百五十一拿掉的 (3, 2)、(2, 0)、(1, 1) 這裡也比對不到單位圖。)
_fi = (GAME / "FDICON.B24").read_bytes()
_tw, _th, _ns = struct.unpack_from("<HHH", _fi, 0)
assert (_tw, _th) == (SPR_W, SPR_H), (_tw, _th)
_fo = [struct.unpack_from("<I", _fi, 6 + 4 * i)[0] for i in range(_ns)] + [len(_fi)]
ICONS = np.stack([dec4(_fi[_fo[k]:_fo[k + 1]], SPR_W, SPR_H) for k in range(_ns)])
ICON_ON = ICONS >= 0


def unit_cells(tag: str, i: int) -> list[tuple[int, int]]:
    """第 i 幀上畫著 FDICON 單位圖的格(含視窗下緣外、圖的上緣進到視窗的那一列)。"""
    f = np.frombuffer((D / f"{tag}_f{i:02d}.bin").read_bytes(), np.uint8).reshape(-1, W)
    cells = []
    for ty in range(-(-(VH + SPRITE_UP) // TILE)):  # 圖的第 0 列 <= 視窗最後一列的格
        for tx in range(VW // TILE):
            x0, y0, x1, y1 = unit_box(tx, ty)
            top = VY0 + TILE * ty - SPRITE_UP
            s, m = ICONS[:, y0 - top:y1 + 1 - top], ICON_ON[:, y0 - top:y1 + 1 - top]
            if (((s == f[y0:y1 + 1, x0:x1 + 1]) | ~m).all(axis=(1, 2)) & m.any(axis=(1, 2))).any():
                cells.append((tx, ty))
    return cells


CELLS = {t: unit_cells(t, 0) for t in _LOG}
assert all(unit_cells(t, i) == CELLS[t] for t in CELLS for i in range(1, 10)), "單位格不是 10 幀都相同"
assert CELLS["s12"] == CELLS["s11"] and all(CASTER[t] in CELLS[t] for t in CELLS), (CELLS, CASTER)
U1 = [unit_box(*c) for c in CELLS["s12"]]
U2 = [unit_box(*c) for c in CELLS["ai79"]]

# remap_circle_scanlines(0x219ad):列 y 在 [y_start, y_end) 裡、且 cy − r < y < cy + r(0x21a29 jle、0x21a35 jge 跳過)才換;
# 半寬 hw = trunc(sqrt(r² − dy²) × scale / [0x501f0]),換 [max(0, cx − hw), min(cx + hw, 0x138)) 這一段(0x219cc 起:
# 起點 cx − hw、長度 hw + min(hw, 0x138 − cx),所以右端不含),逐 byte buf[x] = lut[buf[x]](0x4deec)。
# 0x2189a 的呼叫(0x21942 起)push scale 0xc、列範圍 [0, 0xc0);lut = [0x53a6d] 資源的第 i 項(0x21928)。
SCALE = operand(0x2194A, "push ")
assert (operand(0x21948, "push "), operand(0x21943, "push ")) == (0, VH)
assert operand(0x219D6, "cmp edx, ") == VW
DIV, = struct.unpack("<d", bytes(dl.object_bytes(_EXE, _META, _FX[0x21A7A], 8)))  # fdiv qword ptr [0x501f0]
# [0x53a6d] 唯一的寫入是 main 0x25cc6,載入 FDOTHER.DAT 的第 (0x25cb1 push) 項(ev_s136);0x21922 讀的是同一個位址
assert _FX[0x21924] == _FX[0x25CC7], (hex(_FX[0x21924]), hex(_FX[0x25CC7]))
_o, _n = unpack_dat.parse_directory(_fd)[operand(0x25CB1, "push ")]
_BANK = _fd[_o:_o + _n]
_LUT6 = operand(0x21928, "mov edi, dword ptr [edx + eax*4 + ", "]")


def bank_lut(k: int) -> np.ndarray:
    """[0x53a6d] 資源的第 k 張換色表(資源 + [資源 + k × 4 + 6] 起 256 bytes)。"""
    return np.frombuffer(_BANK, np.uint8, 256, struct.unpack_from("<I", _BANK, _LUT6 + 4 * k)[0])


LUTS = [bank_lut(i) for i in range(10)]
# 游標格:redraw(0x11cac)在地形層之後、單位層之前呼叫 draw_move_range_overlay(0x122dc):依 [0x51a83] 的模式在游標格
# (與周圍)貼 [0x53a4d](main 0x25c92 載入 FDOTHER.DAT 第 (0x25c7d push) 項)的 24 × 24 圖,0x126f7 貼在格子本身、
# 不像單位圖上移(位移只有視窗原點 0x8088),blit_tile24_rle;模式 6 不貼圖,只把游標格 byte3 清 0(0x126d0),
# 由 draw_terrain_layer 以三角表 0x51a97 的階選 [0x53a6d] 的表畫那一格(0x12164),階隨時間變。
# 效果幀的底圖是 0x2189a 自己畫的地形層,基準畫面是效果結束後的重畫,所以游標格兩邊不同。游標在施法者上:
# 這一格以外都照預測,這一格的差別則由上面兩種畫法逐像素解釋(s12 / s11 是貼圖,ai79 是 byte3 換色的階不同)。
assert _FX[0x1277B] == _FX[0x25C93], (hex(_FX[0x1277B]), hex(_FX[0x25C93]))
assert insn(0x1279C) == "call 0x4e22a" and operand(0x12795, "add eax, ") == operand(0x1DC85, "add edx, ")
assert operand(0x12771, "imul edx, edx, ") == TILE
_o, _n = unpack_dat.parse_directory(_fd)[operand(0x25C7D, "push ")]
_R1 = _fd[_o:_o + _n]
_l1 = [struct.unpack_from("<I", _R1, 6 + 4 * i)[0] for i in range(struct.unpack_from("<H", _R1, 4)[0])] + [len(_R1)]
OVERLAY_PX = np.stack([dec4(_R1[a:b], SPR_W, SPR_H) for a, b in zip(_l1, _l1[1:])])
_TRI = bytes(dl.object_bytes(_EXE, _META, _FX[0x1216C], operand(0x12138, "cmp dword ptr [0x3c1f], ")))
HI_STEPS = sorted(set(_TRI))  # byte3 換色可能用到的表


def cell_box(tx: int, ty: int) -> tuple[int, int, int, int]:
    """視窗內第 (tx, ty) 格本身(含端點,0x126f7 的貼圖位置),超出視窗的部分裁掉。"""
    x0, y0 = VX0 + TILE * tx, VY0 + TILE * ty
    return x0, y0, x0 + SPR_W - 1, min(VY1, y0 + SPR_H - 1)


def cursor_cell_cause(tag: str, units: list[tuple[int, int, int, int]]) -> list:
    """施法者那一格(單位框外)基準畫面與效果幀底圖的差別:貼了 FDOTHER #1 哪一項,或 byte3 換色用了哪兩張表。"""
    x0, y0, x1, y1 = cell_box(*CASTER[tag])
    ref = np.frombuffer((D / f"{tag}_ref.bin").read_bytes(), np.uint8).reshape(-1, W)[y0:y1 + 1, x0:x1 + 1]
    fs = np.stack([np.frombuffer((D / f"{tag}_f{i:02d}.bin").read_bytes(), np.uint8).reshape(-1, W)[y0:y1 + 1, x0:x1 + 1]
                   for i in range(10)])
    free = np.ones(ref.shape, bool)
    for a, b, c, d in units:
        free[max(0, b - y0):max(0, d + 1 - y0), max(0, a - x0):max(0, c + 1 - x0)] = False
    pasted = [k for k, e in enumerate(OVERLAY_PX[:, :ref.shape[0]])
              if (free & (e >= 0)).any() and (ref[free & (e >= 0)] == e[free & (e >= 0)]).all()]
    if pasted:
        return ["FDOTHER#1", pasted]
    # 每個像素:有沒有一個 R 讓 10 幀都 = 第 i 張表[T_a[R]]、基準 = T_b[R]
    seen = np.stack([np.stack(LUTS)[:, bank_lut(a)] for a in HI_STEPS])  # 階 × 幀 × R
    pairs = []
    for ia, a in enumerate(HI_STEPS):
        for b in HI_STEPS:
            tb = bank_lut(b)
            if a != b and all(((seen[ia] == fs[:, y, x][:, None]).all(axis=0) & (tb == ref[y, x])).any()
                              for y, x in zip(*np.nonzero(free))):
                pairs.append([a, b])
    return ["FDOTHER#3", pairs]


CURSOR = {t: [cell_box(*CASTER[t])] for t in _LOG}
CURSOR_CAUSE = {t: cursor_cell_cause(t, U1 if t != "ai79" else U2) for t in _LOG}
assert CURSOR_CAUSE == {"s12": ["FDOTHER#1", [0]], "s11": ["FDOTHER#1", [0]], "ai79": ["FDOTHER#3", [[8, 9]]]}, CURSOR_CAUSE
RUNS = [("s12", "玩家施放裂地術(法術 12,command_handler_12)", 276, 42, 30, 16, PANEL + U1 + CURSOR["s12"]),
        ("s11", "玩家施放地震術(法術 11,command_handler_11)", 276, 42, 15, 10, PANEL + U1 + CURSOR["s11"]),
        ("ai79", "敵 #11 在敵方回合使用道具 79(ai_item_action)", 276, 162, 80, -4, U2 + CURSOR["ai79"])]
SHOTS = {"s12": ["060_Return", "061_live12", "062_live12", "063_live12", "064_live12"],
         "s11": sorted(p.stem for p in S.glob("*_live11.png"))}
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5


def analyse(tag: str, cx: int, cy: int, r0: int, step: int, excl: list[tuple[int, ...]],
            right: int = 0, lut_shift: int = 0) -> list[dict]:
    """每幀與預測逐像素比:預測 = 基準畫面在換色段(remap_circle_scanlines)經第 i 張表換色,其餘不變;排除框內不比。
    right / lut_shift 只給對照用(右端多含幾格、換色表錯開幾幀)。"""
    ref = np.frombuffer((D / f"{tag}_ref.bin").read_bytes(), np.uint8).reshape(-1, W)
    pal = (D / f"{tag}_pal.bin").read_bytes()
    wr, wg, wb = LUMA
    lum = np.array([(r * wr + g * wg + b * wb) / sum(LUMA) for r, g, b in struct.iter_unpack("BBB", pal)])
    true = (cx, cy, r0, step, right, lut_shift) == (*_TRUE.get(tag, ()), 0, 0)
    need = NEED.setdefault(tuple(excl), {k: 0 for k in range(len(excl))}) if true else {}
    keep = np.zeros(ref.shape, bool)
    keep[VY0:VY1 + 1, VX0:VX1 + 1] = True
    for a, b, c, d in excl:
        keep[b:d + 1, a:c + 1] = False
    # 排除框含端點:與逐點列舉的另一種寫法相同
    assert set(zip(*np.nonzero(~keep[VY0:VY1 + 1, VX0:VX1 + 1]))) == {
        (y - VY0, x - VX0) for a, b, c, d in excl for y in range(b, d + 1) for x in range(a, c + 1)
        if VY0 <= y <= VY1 and VX0 <= x <= VX1}, tag
    rows = []
    for i in range(10):
        f = np.frombuffer((D / f"{tag}_f{i:02d}.bin").read_bytes(), np.uint8).reshape(-1, W)
        r = r0 + step * i
        lut = LUTS[(i + lut_shift) % 10]
        span = np.zeros(ref.shape, bool)
        for y in range(VH):  # 視窗內的列 = 呼叫給的 [0, 0xc0)
            if cy - r < y < cy + r:
                hw = int(math.sqrt(r * r - (cy - y) ** 2) * SCALE / DIV)
                span[VY0 + y, VX0 + max(0, cx - hw):VX0 + min(cx + hw + right, VW)] = True
        bad = f != np.where(span, lut[ref], ref)
        for k, (a, b_, c, d) in enumerate(excl):
            if k in need:
                need[k] += int(bad[b_:d + 1, a:c + 1].sum())
        changed = (f != ref) & keep
        rows.append({"i": i, "r": r, "inside_px": int((span & keep).sum()), "changed_in": int((changed & span).sum()),
                     "changed_out": int((changed & ~span).sum()), "same_in": int((span & keep & (lut[ref] == ref)).sum()),
                     "mismatch": int((bad & keep).sum()),
                     "mean_lum_delta": round(float((lum[f] - lum[ref])[changed & span].mean()), 2) if (changed & span).any() else None})
    return rows


def verdict(rows: list[dict]) -> list[int]:
    """不符合的幀:排除框外有任何一個像素與預測不同。"""
    return [r["i"] for r in rows if r["mismatch"]]


def vertical_extent(tag: str, i: int, sx: int, excl: list[tuple[int, ...]]) -> tuple[int | None, int | None]:
    """圓心那一欄左右 3 像素內,被換色的最上 / 最下一列(被排除的不算)。"""
    ref = (D / f"{tag}_ref.bin").read_bytes()
    f = (D / f"{tag}_f{i:02d}.bin").read_bytes()
    ys = [y for y in ROWS for x in range(sx - 3, sx + 4)
          if VX0 <= x <= VX1 and f[y * W + x] != ref[y * W + x] and not any(a <= x <= c and b <= y <= d for a, b, c, d in excl)]
    return (min(ys), max(ys)) if ys else (None, None)


def frame_rgb(tag: str, i: int) -> Image.Image:
    """傾印幀轉 RGB(6 位元調色盤 × 255 // 63,與當時 lc122.py png 相同)。"""
    pal = bytes(min(255, (v & 0x3F) * 255 // 63) for v in (D / f"{tag}_pal.bin").read_bytes())
    im = Image.frombytes("P", (320, 200), (D / f"{tag}_f{i:02d}.bin").read_bytes())
    im.putpalette(pal)
    return im.convert("RGB")


def sheet(tag: str) -> Image.Image:
    """10 幀拼接圖:5 × 2,每格 324 × 204,底色洋紅(與當時的拼接指令相同)。"""
    sh = Image.new("RGB", (320 * 5 + 4 * 4, 200 * 2 + 4), (255, 0, 255))
    for k in range(10):
        sh.paste(frame_rgb(tag, k), ((k % 5) * 324, (k // 5) * 204))
    return sh


_TRUE = {tag: (cx, cy, r0, step) for tag, _w, cx, cy, r0, step, _e in RUNS}  # 實測參數(對照組不計排除框)
NEED: dict = {}  # 排除框組 → 每個框在用它的各輪裡被換色的像素數
out: dict = {"date": "2026-10-13", "exe_md5": EXE_MD5,
             "method": "DOSBox-X 除錯器斷點:0x2189a 入口讀堆疊;0x2198e(每幀 copy_rect 之後)讀 EBX / ESI 並傾印線性 0xa0000 起 64000 bytes;"
                       "調色盤取 [0x53a65] 指到的 768 bytes(6 位元);基準畫面是同一視角、沒有效果的一幀。",
             "runs": [], "window_screenshot_match": []}
for tag, what, cx, cy, r0, step, excl in RUNS:
    log = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    rows = analyse(tag, cx, cy, r0, step, excl)
    bad = verdict(rows)
    assert not bad, (tag, bad)
    ctl = {}
    for name, a, kw in (("圓心 x 偏 3", (cx + 3, cy, r0, step), {}), ("每幀增量反號", (cx, cy, r0, -step), {}),
                        ("起始半徑 +6", (cx, cy, r0 + 6, step), {}), ("起始半徑 -6", (cx, cy, r0 - 6, step), {}),
                        ("右端含 cx + hw", (cx, cy, r0, step), {"right": 1}), ("換色表錯開一幀", (cx, cy, r0, step), {"lut_shift": 1})):
        ctl[name] = "FAIL" if verdict(analyse(tag, *a, excl, **kw)) else "PASS"
    assert set(ctl.values()) == {"FAIL"}, ctl
    for r in rows:
        top, bot = vertical_extent(tag, r["i"], cx + VX0, excl)
        r["centre_col_top_y"], r["centre_col_bottom_y"] = top, bot
        r["frame_md5"] = hashlib.md5((D / f"{tag}_f{r['i']:02d}.bin").read_bytes()).hexdigest()
    assert [f["radius"] for f in log["frames"]] == [r0 + step * i for i in range(10)]
    out["runs"].append({"tag": tag, "what": what, "entry": log["entry"], "ai_item_action": log.get("ai_item_action"),
                        "frames_radius_ESI": [f["radius"] for f in log["frames"]], "screen_centre": [cx + VX0, cy + VY0],
                        "excluded_rects": excl, "cursor_cell": CURSOR[tag][0], "cursor_cell_cause": CURSOR_CAUSE[tag],
                        "shape": rows, "controls": ctl})
# 每個排除框都有用:用它的那幾輪裡,框內在某一幀與預測不同(單位圖不換色 / 面板 / 游標格)
out["remap_model"] = {"scale": SCALE, "divisor": DIV, "rows": "cy - r < y < cy + r", "span": "[max(0, cx - hw), min(cx + hw, 0x138))",
                      "lut_bank": f"FDOTHER #{operand(0x25CB1, 'push ')}", "highlight_steps": HI_STEPS}
assert all(all(v.values()) for v in NEED.values()), NEED
neg = json.loads((D / "ai.json").read_text(encoding="utf-8"))
out["negative_run"] = {"what": "敵 #11 使用道具 38(道具列 +0x10 = 2):ai_item_action 有進,整個敵方回合 0x2189a 的斷點沒有停",
                       "ai_item_action": neg["ai_item_action"], "frames": len(neg["frames"])}
for tag, shots in SHOTS.items():
    fr = {f"{tag}_f{i:02d}": frame_rgb(tag, i) for i in range(10)}
    for name in shots:
        im = Image.open(S / f"{name}.png").convert("RGB").crop((192, 201, 832, 601)).resize((320, 200), Image.NEAREST)
        sc = sorted((sum(ImageStat.Stat(ImageChops.difference(im, f)).mean) / 3, k) for k, f in fr.items())
        (d_best, k_best), (d_2nd, k_2nd), *_ = sc
        out["window_screenshot_match"].append({"screenshot": name, "best": k_best, "mean_abs_diff": round(d_best, 3),
                                               "second": k_2nd, "second_diff": round(d_2nd, 3)})
# 判準:每張視窗截圖只對上一幀(最接近 < 0.5,次接近 > 1.0),而且依截圖時間順序對到的幀不倒退
wm = out["window_screenshot_match"]
assert all(w["mean_abs_diff"] < 0.5 < 1.0 < w["second_diff"] for w in wm), wm
for tag in SHOTS:
    seq = [int(w["best"][-2:]) for w in wm if w["best"].startswith(tag + "_")]
    assert len(seq) == len(SHOTS[tag]) and seq == sorted(seq), (tag, seq)
assert [w["best"] for w in wm] == ["s12_f01", "s12_f04", "s12_f06", "s12_f07", "s12_f08", "s11_f01", "s11_f01", "s11_f02",
                                   "s11_f04", "s11_f05", "s11_f06", "s11_f07", "s11_f08", "s11_f08"], wm
# 記錄裡的圓心、起始半徑、增量與分析參數相同;負對照:道具 38 整個敵方回合沒有停在 0x2189a
for (tag, _w, cx, cy, r0, step, _e), run in zip(RUNS, out["runs"]):
    assert (run["entry"]["centre"], run["entry"]["radius0"], run["entry"]["step"]) == ([cx, cy], r0, step), tag
assert out["negative_run"]["frames"] == 0 and out["negative_run"]["ai_item_action"]["unit"] == 11

# 已提交的 PNG:拼接圖由傾印重畫後逐像素相同;視窗截圖與原始截圖逐 byte 相同
SHEETS = {"lut_circle_ramp_spell12_frames_20261013.png": "s12", "lut_circle_ramp_spell11_frames_20261013.png": "s11",
          "lut_circle_ramp_item79_frames_20261013.png": "ai79"}
for dst, tag in SHEETS.items():
    committed = Image.open(EVIDENCE / dst).convert("RGB")
    assert ImageChops.difference(committed, sheet(tag)).getbbox() is None, dst
WINDOW = ("lut_circle_ramp_spell12_window_20261013.png", S / "060_Return.png")
assert (EVIDENCE / WINDOW[0]).read_bytes() == WINDOW[1].read_bytes()
out["files"] = {dst: hashlib.md5((EVIDENCE / dst).read_bytes()).hexdigest() for dst in [*SHEETS, WINDOW[0]]}


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
