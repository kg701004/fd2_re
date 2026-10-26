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


PANEL = [(4, 158, 74, 197)]
# 施法者所在的格 = 紀錄的 unit_xy − scroll(同一次記錄)
_LOG = {t: json.loads((D / f"{t}.json").read_text(encoding="utf-8"))["entry"] for t in ("s12", "s11", "ai79")}
CASTER = {t: tuple(u - s for u, s in zip(e["unit_xy"], e["scroll"])) for t, e in _LOG.items()}
assert CASTER["s12"] == CASTER["s11"], CASTER
# 有動畫的單位所在的格(畫面座標 = 格 − 捲動);排除框由格算出。施法者以外的格沒有單位表,由幀上的換色定
U1 = [unit_box(*t) for t in (CASTER["s12"], (7, 1), (6, 0), (10, 1), (2, 6), (1, 5), (0, 6))]
# 續一百五十一:原本另有 (3, 2)、(2, 0)、(1, 1) 三格,10 幀裡框內都沒有換色(沒作用),拿掉。
# 續一百五十四:(1, 8) 在視窗下緣之外,單位圖上移 6 列後最上面 6 列進到視窗(原本由 (1, 7) 往下多框的一整格蓋住)
U2 = [unit_box(*t) for t in ((12, 6), CASTER["ai79"], (1, 7), (3, 7), (2, 6), (1, 8))]
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
