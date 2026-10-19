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

from PIL import Image, ImageChops, ImageStat

from _evpaths import EVIDENCE, GAME, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)

D = ROOT / ".wsl_build" / "lc122_live"
S = ROOT / ".wsl_build" / "lc122_shots"
OUT = out_path("lut_circle_ramp_at_unit_20261013.json")
W = 320
VX0, VY0, VW, VH = 4, 4, 0x138, 0xC0  # copy_rect 貼到畫面的視窗
VX1, VY1 = VX0 + VW - 1, VY0 + VH - 1
PANEL = [(4, 158, 74, 197)]
U1 = [(268, 16, 291, 51), (172, 16, 195, 51), (148, 4, 171, 27), (244, 16, 267, 51), (52, 136, 75, 171), (28, 112, 51, 147),
      (4, 136, 27, 171)]
U2 = [(292, 136, 315, 171), (76, 40, 99, 75), (52, 4, 75, 27), (28, 16, 51, 51), (268, 136, 291, 171), (28, 160, 51, 195),
      (76, 160, 99, 195), (52, 136, 75, 171)]
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
    lum = [(pal[i * 3] * 30 + pal[i * 3 + 1] * 59 + pal[i * 3 + 2] * 11) / 100 for i in range(256)]
    sx, sy = cx + VX0, cy + VY0

    def masked(x: int, y: int) -> bool:
        return any(a <= x <= c and b <= y <= d for a, b, c, d in excl)

    rows = []
    for i in range(10):
        f = (D / f"{tag}_f{i:02d}.bin").read_bytes()
        r = r0 + step * i
        inside = out_changed = in_changed = edge_rows = edge_ok = 0
        lum_d = 0.0
        over: list[tuple[int, int]] = []
        for y in range(VY0, VY1 + 1):
            dy = y - sy
            hw = int(math.sqrt(r * r - dy * dy) * 12 / 10) if abs(dy) <= r else -1
            xs = [x for x in range(VX0, VX1 + 1) if f[y * W + x] != ref[y * W + x] and not masked(x, y)]
            for x in xs:
                if hw < 0 or abs(x - sx) > hw:
                    out_changed += 1
                    if len(over) < 4:
                        over.append((x, y))
                else:
                    in_changed += 1
                    lum_d += lum[f[y * W + x]] - lum[ref[y * W + x]]
            if hw < 0:
                continue
            inside += sum(1 for x in range(max(VX0, sx - hw), min(VX1, sx + hw) + 1) if not masked(x, y))
            for edge, sign in ((sx - hw, 1), (sx + hw, -1)):
                if not VX0 <= edge <= VX1 or hw < 3 or any(masked(edge + sign * k, y) for k in range(3)):
                    continue
                edge_rows += 1
                hit = [x for x in xs if 0 <= (x - edge) * sign <= 2]
                edge_ok += bool(hit)
        rows.append({"i": i, "r": r, "inside_px": inside, "changed_in": in_changed, "changed_out": out_changed,
                     "edge_rows": edge_rows, "edge_ok": edge_ok,
                     "mean_lum_delta": round(lum_d / in_changed, 2) if in_changed else None, "over": over})
    return rows


def verdict(rows: list[dict]) -> list[int]:
    """不符合的幀:預測外有換色、看得到的邊緣列 < 20,或邊緣命中 < 90%。"""
    return [r["i"] for r in rows if r["changed_out"] or r["edge_rows"] < 20 or r["edge_ok"] < 0.9 * r["edge_rows"]]


def vertical_extent(tag: str, i: int, sx: int, excl: list[tuple[int, ...]]) -> tuple[int | None, int | None]:
    """圓心那一欄左右 3 像素內,被換色的最上 / 最下一列(被排除的不算)。"""
    ref = (D / f"{tag}_ref.bin").read_bytes()
    f = (D / f"{tag}_f{i:02d}.bin").read_bytes()
    ys = [y for y in range(4, 196) for x in range(sx - 3, sx + 4)
          if 4 <= x <= 315 and f[y * 320 + x] != ref[y * 320 + x] and not any(a <= x <= c and b <= y <= d for a, b, c, d in excl)]
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
        top, bot = vertical_extent(tag, r["i"], cx + 4, excl)
        r["centre_col_top_y"], r["centre_col_bottom_y"] = top, bot
        r["frame_md5"] = hashlib.md5((D / f"{tag}_f{r['i']:02d}.bin").read_bytes()).hexdigest()
    assert [f["radius"] for f in log["frames"]] == [r0 + step * i for i in range(10)]
    out["runs"].append({"tag": tag, "what": what, "entry": log["entry"], "ai_item_action": log.get("ai_item_action"),
                        "frames_radius_ESI": [f["radius"] for f in log["frames"]], "screen_centre": [cx + 4, cy + 4],
                        "excluded_rects": excl, "shape": rows, "controls": ctl})
neg = json.loads((D / "ai.json").read_text(encoding="utf-8"))
out["negative_run"] = {"what": "敵 #11 使用道具 38(道具列 +0x10 = 2):ai_item_action 有進,整個敵方回合 0x2189a 的斷點沒有停",
                       "ai_item_action": neg["ai_item_action"], "frames": len(neg["frames"])}
for tag, shots in SHOTS.items():
    fr = {f"{tag}_f{i:02d}": frame_rgb(tag, i) for i in range(10)}
    for name in shots:
        im = Image.open(S / f"{name}.png").convert("RGB").crop((192, 201, 832, 601)).resize((320, 200), Image.NEAREST)
        sc = sorted((sum(ImageStat.Stat(ImageChops.difference(im, f)).mean) / 3, k) for k, f in fr.items())
        out["window_screenshot_match"].append({"screenshot": name, "best": sc[0][1], "mean_abs_diff": round(sc[0][0], 3),
                                               "second": sc[1][1], "second_diff": round(sc[1][0], 3)})
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
