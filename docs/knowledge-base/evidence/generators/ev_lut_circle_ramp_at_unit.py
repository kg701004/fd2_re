"""續一百二十二證據:evidence/lut_circle_ramp_at_unit_20261013.json。

lc122 三組實機紀錄(法術 12、法術 11、敵 #11 用道具 79)每幀的換色範圍與 doc35 §18 的圓形預測逐列比對,
另比對視窗截圖與傾印幀。原本由暫存的 mk_evidence122.py + an122.py 產生(續一百二十二);
續一百三十四移進倉庫,原始紀錄放在 .wsl_build/lc122_live/(傾印、調色盤、記錄 JSON)與 .wsl_build/lc122_shots/(視窗截圖)。
傾印幀的 PNG 與拼接圖在這裡由 .bin + 調色盤重畫(不讀暫存目錄產生的 PNG);拼接圖與已提交的 PNG 逐像素比對。
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
from _exeops import operand  # noqa: E402
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
RUNS = [("s12", "玩家施放裂地術(法術 12,command_handler_12)", 276, 42, 30, 16, PANEL + U1),
        ("s11", "玩家施放地震術(法術 11,command_handler_11)", 276, 42, 15, 10, PANEL + U1),
        ("ai79", "敵 #11 在敵方回合使用道具 79(ai_item_action)", 276, 162, 80, -4, U2)]
SHOTS = {"s12": ["060_Return", "061_live12", "062_live12", "063_live12", "064_live12"],
         "s11": sorted(p.stem for p in S.glob("*_live11.png"))}
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5


def analyse(tag: str, cx: int, cy: int, r0: int, step: int, excl: list[tuple[int, ...]]) -> list[dict]:
    """每幀與基準畫面比:預測圓(半寬 = int(sqrt(r^2 - dy^2) * 12 / 10))外的換色像素、邊緣列與亮度變化。"""
    ref = (D / f"{tag}_ref.bin").read_bytes()
    pal = (D / f"{tag}_pal.bin").read_bytes()
    wr, wg, wb = LUMA
    lum = [(r * wr + g * wg + b * wb) / sum(LUMA) for r, g, b in struct.iter_unpack("BBB", pal)]
    need = NEED.setdefault(tuple(excl), {k: 0 for k in range(len(excl))}) if (cx, cy, r0, step) == _TRUE.get(tag) else {}
    sx, sy = cx + VX0, cy + VY0

    def masked(x: int, y: int) -> bool:
        return any(a <= x <= c and b <= y <= d for a, b, c, d in excl)

    rows = []
    for i in range(10):
        f = (D / f"{tag}_f{i:02d}.bin").read_bytes()
        r = r0 + step * i
        inside = out_changed = in_changed = edge_rows = edge_ok = 0
        lum_d: list[float] = []  # 圓內每個換色像素的亮度差
        over: list[tuple[int, int]] = []
        for y in ROWS:
            dy = y - sy
            hw = int(math.sqrt(r * r - dy * dy) * 12 / 10) if abs(dy) <= r else None
            diff_x = [x for x in COLS if f[y * W + x] != ref[y * W + x]]
            xs = [x for x in diff_x if not masked(x, y)]
            for x in diff_x:
                for k, (a, b_, c, d) in enumerate(excl):
                    if k in need:
                        need[k] += a <= x <= c and b_ <= y <= d
            for x in xs:
                if hw is None or abs(x - sx) > hw:
                    out_changed += 1
                    if len(over) < 4:
                        over.append((x, y))
                else:
                    in_changed += 1
                    lum_d.append(lum[f[y * W + x]] - lum[ref[y * W + x]])
            if hw is None:
                continue
            # 圓內 = 與上面「圓內換色」同一個條件(|x − 圓心| <= 半寬)
            inside += sum(abs(x - sx) <= hw and not masked(x, y) for x in COLS)
            for edge, sign in ((sx - hw, 1), (sx + hw, -1)):
                if not VX0 <= edge <= VX1 or hw < 3 or any(masked(edge + sign * k, y) for k in range(3)):
                    continue
                edge_rows += 1
                hit = [x for x in xs if 0 <= (x - edge) * sign <= 2]
                edge_ok += bool(hit)
        # 未排除的換色像素:圓內 + 圓外 = 另外數的總數
        assert in_changed + out_changed == sum(f[y * W + x] != ref[y * W + x] and not masked(x, y)
                                               for y in ROWS for x in COLS), (tag, i)
        rows.append({"i": i, "r": r, "inside_px": inside, "changed_in": in_changed, "changed_out": out_changed,
                     "edge_rows": edge_rows, "edge_ok": edge_ok,
                     "mean_lum_delta": round(sum(lum_d) / in_changed, 2) if in_changed else None, "over": over})
    return rows


def verdict(rows: list[dict]) -> list[int]:
    """不符合的幀:預測外有換色、看得到的邊緣列 < 20,或邊緣命中 < 90%。"""
    return [r["i"] for r in rows if r["changed_out"] or r["edge_rows"] < 20 or r["edge_ok"] < 0.9 * r["edge_rows"]]


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
    for name, a in (("圓心 x 偏 3", (cx + 3, cy, r0, step)), ("每幀增量反號", (cx, cy, r0, -step)),
                    ("起始半徑 +6", (cx, cy, r0 + 6, step)), ("起始半徑 -6", (cx, cy, r0 - 6, step))):
        ctl[name] = "FAIL" if verdict(analyse(tag, *a, excl)) else "PASS"
    assert set(ctl.values()) == {"FAIL"}, ctl
    for r in rows:
        r.pop("over")
        top, bot = vertical_extent(tag, r["i"], cx + VX0, excl)
        r["centre_col_top_y"], r["centre_col_bottom_y"] = top, bot
        r["frame_md5"] = hashlib.md5((D / f"{tag}_f{r['i']:02d}.bin").read_bytes()).hexdigest()
    assert [f["radius"] for f in log["frames"]] == [r0 + step * i for i in range(10)]
    out["runs"].append({"tag": tag, "what": what, "entry": log["entry"], "ai_item_action": log.get("ai_item_action"),
                        "frames_radius_ESI": [f["radius"] for f in log["frames"]], "screen_centre": [cx + VX0, cy + VY0],
                        "excluded_rects": excl, "shape": rows, "controls": ctl})
# 每個排除框都有用:用它的那幾輪裡,框內在某一幀有換色(單位動畫 / 面板)
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
