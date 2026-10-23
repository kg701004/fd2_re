"""續一百二十三證據:evidence/ai_item_action_item79_flow_20261013.json。

lc123 兩輪(敵 #11 用道具 79)的斷點紀錄、調色盤迴圈、八個相位幀的亮帶分析。原本由暫存的 mk_evidence123.py + an123.py
產生(續一百二十三);續一百三十四移進倉庫,原始紀錄放在 .wsl_build/lc123_live/(傾印、調色盤、記錄 JSON、
調色盤迴圈停下時的視窗截圖)與 .wsl_build/lc123_shots/(戰敗後的標題畫面截圖)。
三張拼接圖在這裡由原始資料重畫,與已提交的 PNG 逐像素比對(對照圖的文字標籤不比,只比貼上的畫面)。
"""
from __future__ import annotations

import hashlib
import json
import math

from PIL import Image, ImageChops, ImageStat

from _evpaths import EVIDENCE, GAME, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)

D = ROOT / ".wsl_build" / "lc123_live"
S = ROOT / ".wsl_build" / "lc123_shots"
OUT = out_path("ai_item_action_item79_flow_20261013.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
FRAMES = [f"ph{k}" for k in range(1, 9)]
KEEP_UNITS = (0, 3, 5, 10, 11)
DUMPS = ["151a7", "151b7", "151dd", "1528c"] + FRAMES + ["152e5", "152f5", "152fd"]
WHAT = {"runA": "索爾 HP 823(滿)。敵 #11 在 (19,14),瞄準點 (19,13),目標 #5、#10(友軍 NPC)",
        "runB": "下一回合,索爾 HP 設成 3(敵方回合開始時讀到 167)。瞄準點 (20,14),目標 #0 索爾、#3"}


DIGITS = 2  # 亮度取到小數兩位(EXPECT 的亮帶值是同一個位數)
SCR_W, SCR_H = 320, 200  # mode 13h,傾印 = 線性 0xa0000 起 64000 bytes
TILE = 24


def map_area(tag: str, name: str) -> tuple[int, int, int, int]:
    """非 0 像素的外框(含端點)。"""
    raw = (D / f"{tag}_{name}.bin").read_bytes()
    assert len(raw) == SCR_W * SCR_H, len(raw)
    x0, y0, x1, y1 = Image.frombytes("P", (SCR_W, SCR_H), raw).getbbox()
    return x0, y0, x1 - 1, y1 - 1


MAP = map_area("runA", "ph1")
assert all(map_area(t, n) == MAP for t in ("runA", "runB") for n in DUMPS), MAP
_mx0, _my0, _mx1, _my1 = MAP
assert (_mx1 - _mx0 + 1) % TILE == 0 and (_my1 - _my0 + 1) % TILE == 0, MAP


def clip(rect: tuple[int, int, int, int]) -> list[int]:
    """右下角夾在地圖區內(輸出用)。"""
    x0, y0, x1, y1 = rect
    return [x0, y0, min(x1, _mx1), min(y1, _my1)]


def shift(rect: tuple[int, int, int, int], dx: int, dy: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    return x0 + dx, y0 + dy, x1 + dx, y1 + dy


# ---------------- 亮帶分析(原 an123.py) ----------------
def lum_table(tag: str) -> list[float]:
    """6 位元調色盤 R+G+B 的平均(滿刻度 63)。"""
    pal = (D / f"{tag}_1528c_pal.bin").read_bytes()
    return [((pal[i * 3] & 63) + (pal[i * 3 + 1] & 63) + (pal[i * 3 + 2] & 63)) / 3 for i in range(256)]


def rect_mean(raw: bytes, lum: list[float], rect: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = rect
    tot = n = 0
    for y in range(max(_my0, y0), min(_my1, y1) + 1):
        row = raw[y * SCR_W + max(_mx0, x0): y * SCR_W + min(_mx1, x1) + 1]
        tot += sum(lum[v] for v in row)
        n += len(row)
    return tot / n if n else float("nan")


def band_rects(log: dict) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int], bool]:
    """亮帶、對照帶(畫面座標,含端點)與是不是直的。使用者座標取 build_target_candidates 的起點引數,延伸點與捲動取 camera_step_to 返回時的值。"""
    st = {s["at"]: s for s in log["stops"]}
    ux, uy = st["0x150f6"]["args"][3], st["0x150f6"]["args"][4]
    g = st["0x1528c"]["g"]
    fx, fy, sx, sy = g["target_x"], g["target_y"], g["scroll_x"], g["scroll_y"]
    cx0, cx1 = sorted((ux, fx))
    cy0, cy1 = sorted((uy, fy))
    band = ((cx0 - sx) * TILE + _mx0, (cy0 - sy) * TILE + _my0, (cx1 - sx + 1) * TILE + _mx0 - 1, (cy1 - sy + 1) * TILE + _my0 - 1)
    vertical = ux == fx
    ctl = shift(band, -TILE, 0) if vertical else shift(band, 0, -TILE)
    return band, ctl, vertical


def analyse(tag: str, wrong: bool = False) -> dict:
    """八個相位幀:亮帶、對照帶、整個地圖區的平均亮度;wrong = 對照(亮帶垂直移兩格)。"""
    log = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    lum = lum_table(tag)
    band, ctl, vertical = band_rects(log)
    if wrong:
        dx, dy = (2 * TILE, 0) if vertical else (0, 2 * TILE)
        _, _, bx1, by1 = band
        if bx1 + dx > _mx1 or by1 + dy > _my1:
            dx, dy = -dx, -dy
        band = shift(band, dx, dy)
    phases = [s["phase"] for s in log["stops"] if s["at"] == "0x152ba"]
    forced = [s["ebx"] for s in log["stops"] if s["at"] == "0x152ba"]
    rows = []
    for k, name in enumerate(FRAMES):
        raw = (D / f"{tag}_{name}.bin").read_bytes()
        rows.append({"frame": name, "forced_phase_EBX": forced[k], "phase_read_at_stop": phases[k],
                     "band": round(rect_mean(raw, lum, band), DIGITS), "control": round(rect_mean(raw, lum, ctl), DIGITS),
                     "map_area": round(rect_mean(raw, lum, MAP), DIGITS)})
    # 亮帶 = 使用者到延伸點的整格範圍;對照帶 = 同大小、往垂直方向錯開一格,完全不重疊
    bx0, by0, bx1, by1 = band
    cx0, cy0, cx1, cy1 = ctl
    assert (bx0 - _mx0) % TILE == 0 and (by0 - _my0) % TILE == 0 and (bx1 + 1 - _mx0) % TILE == 0, band
    assert (cx1 - cx0, cy1 - cy0) == (bx1 - bx0, by1 - by0) and abs(cx0 - bx0) + abs(cy0 - by0) == TILE, (band, ctl)
    return {"tag": tag, "band_rect": clip(band), "control_rect": clip(ctl), "rows": rows}


def verdict(res: dict) -> list[str]:
    """亮度只跟停下時的相位有關、相位小的比大的亮 4 以上、對照帶變動 < 1.5;回傳不符合的理由。"""
    rows = sorted(res["rows"], key=lambda r: r["phase_read_at_stop"])
    b = [r["band"] for r in rows]
    c = [r["control"] for r in rows]
    if any(math.isnan(v) for v in b + c):
        return ["有區域在畫面外,算不出來"]
    bad = []
    for (r0, r1), (b0, b1) in zip(zip(rows, rows[1:]), zip(b, b[1:])):
        same = r0["phase_read_at_stop"] == r1["phase_read_at_stop"]
        if same and abs(b0 - b1) >= 0.1:
            bad.append(f"相位 {r0['phase_read_at_stop']} 的兩站亮度差 {abs(b0 - b1):.2f}")
        if not same and b1 - b0 > 0.1:
            bad.append(f"相位 {r1['phase_read_at_stop']} 比 {r0['phase_read_at_stop']} 亮")
    b_first, *_, b_last = b
    if b_first - b_last < 4:
        bad.append(f"亮帶頭尾只差 {b_first - b_last:.2f}")
    if max(c) - min(c) > 1.5:
        bad.append(f"對照帶變動 {max(c) - min(c):.2f}")
    return bad


def reversed_phases(res: dict) -> dict:
    """對照:把各站讀到的相位倒過來配,亮度應該不再隨相位變暗。"""
    ph = [r["phase_read_at_stop"] for r in res["rows"]][::-1]
    return {**res, "rows": [{**r, "phase_read_at_stop": p} for r, p in zip(res["rows"], ph)]}


# ---------------- 整理(原 mk_evidence123.py) ----------------
def trim(stop: dict) -> dict:
    s = dict(stop)
    if "units" in s:
        s["units"] = [{k: u[k] for k in ("i", "x", "y", "f5", "camp", "hp", "mhp", "inv")} for u in s["units"] if u["i"] in KEEP_UNITS]
    return s


def window_crop(tag: str, name: str) -> Image.Image:
    return Image.open(D / f"{tag}_{name}.png").convert("RGB").crop((192, 201, 832, 601)).resize((320, 200))


def window_means(tag: str) -> list[dict]:
    """調色盤迴圈停下時的視窗截圖(地圖區)平均 RGB。停下時視窗還是上一步的畫面,所以標的是「停在哪一步」。"""
    out = []
    for name in ("pal64", "pal48", "pal32", "pal16", "pal00", "151dd"):
        im = window_crop(tag, name)
        n = im.width * im.height
        out.append({"stopped_at": "迴圈結束(0x151dd)" if name == "151dd" else f"delta = {int(name.removeprefix('pal'))}",
                    "mean_rgb": [round(s / n, 1) for s in ImageStat.Stat(im).sum]})
    return out


def pal_of(tag: str, name: str) -> bytes:
    """相位幀沒有另外傾印調色盤:用最近一站的(與當時 sheet123.py 相同)。"""
    f = D / f"{tag}_{name}_pal.bin"
    if not f.exists():
        f = D / f"{tag}_1528c_pal.bin"
    return bytes(min(255, (v & 0x3F) * 255 // 63) for v in f.read_bytes())


def sheet_tiles_match(tag: str, committed: Image.Image) -> bool:
    """對照圖(4 欄,每格 324 × 216,畫面貼在 (+2, +14)):每一站的畫面區與傾印重畫逐像素相同。"""
    for n, name in enumerate(DUMPS):
        im = Image.frombytes("P", (320, 200), (D / f"{tag}_{name}.bin").read_bytes())
        im.putpalette(pal_of(tag, name))
        x, y = (n % 4) * 324 + 2, (n // 4) * 216 + 14
        if ImageChops.difference(committed.crop((x, y, x + 320, y + 200)), im.convert("RGB")).getbbox() is not None:
            return False
    return committed.size == (4 * 324, 4 * 216)


out: dict = {
    "date": "2026-10-13", "exe_md5": EXE_MD5,
    "method": "DOSBox-X 除錯器斷點,第 1 章戰場,敵 #11 的道具欄第 2 格放道具 79(只改模擬器記憶體裡的單位資料)。"
              "斷點(native):0x15055 入口、0x150f6 build_target_candidates 返回、0x151a7 圓形換色返回、0x151b7、"
              "0x151ce(調色盤迴圈每一圈)、0x151dd、0x1528c camera_step_to 返回、0x152ba(相位迴圈每一圈)、0x152e5、"
              "0x20c6f item_effect_dispatch 入口、0x152f5 返回、0x152fd;另有 0x22e5c 與 0x25ebb。"
              "畫面是停下時傾印線性 0xa0000 起 64000 bytes,配 [0x53a65] 指到的 768 bytes 調色盤重建。",
    "runs": [], "files": {}}
for tag in ("runA", "runB"):
    log = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    assert log["pal"] == list(range(64, -1, -1)) and log["phase"] == list(range(1, 9)) and not log.get("stray")
    res = analyse(tag)
    bad = verdict(res)
    wbad = verdict(analyse(tag, wrong=True))
    rbad = verdict(reversed_phases(res))
    assert not bad and wbad and rbad, (tag, bad, wbad, rbad)
    pal_first, *_, pal_last = log["pal"]
    out["runs"].append({
        "tag": tag, "what": WHAT[tag],
        "stops": [trim(s) for s in log["stops"]],
        "palette_loop_EBX_at_0x151ce": {"count": len(log["pal"]), "first": pal_first, "last": pal_last,
                                        "strictly_descending_by_1": True},
        "palette_loop_window_screenshots": window_means(tag),
        "strip": {**res, "verdict": "PASS", "control_wrong_position": "FAIL", "control_reasons": wbad,
                  "control_reversed_phases": "FAIL", "control_reversed_reasons": rbad},
        "dump_md5": {n: hashlib.md5((D / f"{tag}_{n}.bin").read_bytes()).hexdigest() for n in DUMPS}})
# 結論釘住:停站順序與靜態相同;候選(build_target_candidates 輸出的前兩個 byte)、相位、目標的 HP 變化
ORDER = ["0x15055", "0x150f6", "0x151a7", "0x151b7", "0x151dd", "0x1528c"] + ["0x152ba"] * 8 + ["0x152e5", "0x20c6f", "0x152f5", "0x152fd"]
EXPECT = {"runA": {"targets": [5, 10], "phases": [2, 2, 4, 4, 5, 7, 7, 8], "after": {0: (823, 0), 3: (867, 0), 5: (0, 1), 10: (0, 1)},
                   "band": [29.22, 29.22, 26.07, 26.07, 25.39, 22.75, 22.75, 21.61], "reasons": (1, 8, 4)},
          "runB": {"targets": [0, 3], "phases": [1, 3, 3, 5, 5, 7, 7, 9], "after": {0: (0, 1), 3: (493, 0), 5: (0, 1), 10: (0, 1)},
                   "band": [27.24, 24.75, 24.75, 22.9, 22.92, 20.78, 20.78, 18.62], "reasons": (1, 5, 4)}}
for run in out["runs"]:
    st = {s["at"]: s for s in run["stops"]}
    e = EXPECT[run["tag"]]
    assert [s["at"] for s in run["stops"]] == ORDER, run["tag"]
    assert st["0x150f6"]["eax"] == st["0x20c6f"]["count"] == len(e["targets"]), run["tag"]
    assert list(bytes.fromhex(st["0x20c6f"]["targets"])[:2]) == e["targets"] and st["0x20c6f"]["targets"] == st["0x150f6"]["out"]
    assert [r["phase_read_at_stop"] for r in run["strip"]["rows"]] == e["phases"], run["tag"]
    assert [r["band"] for r in run["strip"]["rows"]] == e["band"], run["tag"]
    # 對照的不符合理由:位置錯兩格 1 條(頭尾差不到 4);相位倒過來配時「相位大的比較亮」各 4 條
    wr, rr = run["strip"]["control_reasons"], run["strip"]["control_reversed_reasons"]
    assert (len(wr), len(rr), sum(" 比 " in x and x.endswith("亮") for x in rr)) == e["reasons"], (wr, rr)
    assert {u["i"]: (u["hp"], u["f5"]) for u in st["0x152f5"]["units"] if u["i"] != 11} == e["after"], run["tag"]
assert out["runs"][1]["stops"][0]["units"][0]["hp"] == 167      # runB 入口:索爾 3 → 167(結束回合時休息)
lose = json.loads((D / "runB_lose.json").read_text(encoding="utf-8"))
assert [(s["at"], s["g"]["result"]) for s in lose["stops"]] == [("0x22e5c", 1), ("0x25ebb", 0)], lose["stops"]
out["after_runB"] = {"what": "runB 的 ai_item_action 返回之後,只留 0x22e5c 與 0x25ebb 兩個斷點",
                     "stops": [trim(s) for s in lose["stops"]]}
out["shared_epilogue_probe"] = {
    "what": "第一次把收尾斷點下在 0x15309,玩家回合選取索爾時就停了(ai_item_action 入口的斷點沒有停過)",
    "EIP_native": "0x15309", "ESP": "0x1f157c", "EBX": "0x720", "EDI": "0x1c8",
    "return_address_at_ESP_plus_0x34_native": "0x18d84",
    "static": "0x164e3 jmp 0x15309(0x15f84 的結尾)、0x1cfa8 jge 0x15309(draw_command_list);0x18d7f call 0x15f84 在 draw_unit_panel 裡"}

# 已提交的 PNG:對照圖與調色盤視窗圖由原始資料重畫後逐像素相同;標題畫面與原始截圖逐 byte 相同
FILES = ["ai_item_action_item79_flow_runA_20261013.png", "ai_item_action_item79_flow_runB_20261013.png",
         "ai_item_action_item79_palette_window_20261013.png", "ai_item_action_item79_defeat_title_20261013.png"]
for tag, dst in (("runA", FILES[0]), ("runB", FILES[1])):
    assert sheet_tiles_match(tag, Image.open(EVIDENCE / dst).convert("RGB")), dst
pal_sheet = Image.new("RGB", (6 * 322, 200))
for i, name in enumerate(("pal64", "pal48", "pal32", "pal16", "pal00", "151dd")):
    pal_sheet.paste(window_crop("runA", name), (i * 322, 0))
assert ImageChops.difference(Image.open(EVIDENCE / FILES[2]).convert("RGB"), pal_sheet).getbbox() is None
assert (EVIDENCE / FILES[3]).read_bytes() == (S / "040_B2.png").read_bytes()
out["files"] = {dst: hashlib.md5((EVIDENCE / dst).read_bytes()).hexdigest() for dst in FILES}


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
