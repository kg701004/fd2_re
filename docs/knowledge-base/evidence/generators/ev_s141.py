"""續一百四十一證據:evidence/demonface_live_vs_fdother_scroll_s141_20261021.json。

doc23 §2.4⑦ 的「開場分鏡⑨ 惡魔臉 = FDOTHER #0x45 / #0x46(FDOTHER_069 / 070)捲動到頂」重做比對。當時的比對圖是
decode_sprite.py 續一百四十以前的預設(模式 1 當 literal)解的,而且用的 frame_184.png 已不在本機。
本輪輸入:原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)在 DOSBox-X 的開場連拍 93 張(.wsl_build/s141_demonface/,
t0 起 39.5–43.6 秒,不送按鍵)與 extracted/raw 的 FDOTHER_069–073(捲動立繪五幀,doc23 §2.1 的 320×735 緩衝)。

判準(與當下調色盤亮度無關):同一幀裡同一個調色盤索引只會顯示一個顏色。把五份本文(寬高讀自各自的 4 byte 標頭)疊成緩衝,
對每張實拍(遊戲區 640×400 取 2× 的左上點 = 320×200)搜尋垂直位移 dy(= 捲動迴圈的 esi,0–535),只看實拍非黑像素:
    B = 每個 RE 索引底下最常見的實拍顏色所佔比例(加權);解碼正確且對齊 → B = 1。
    A = 每個實拍顏色底下最常見的 RE 索引所佔比例(加權);不同索引可能同色,所以 A 可略低於 1。
對照:literal 解(舊預設,各自搜尋 dy)、dither 解水平平移 1 px(虛無)、黑幕之後的 logo 幀(不同的圖)。
撕裂幀(擷取時畫面正在更新)單一 dy 的 B 會低於 1:改用「上半 dy、下半 dy - 1」拼接重算(literal 與 logo 幀也給同樣的自由度);
兩種都解釋不了的照實列出,不刪掉。
"""
from __future__ import annotations

import json
import re
import struct

import numpy as np
from PIL import Image

from _evpaths import ROOT, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)

SHOTS = ROOT / ".wsl_build/s141_demonface/shots"
RAW = ROOT / "extracted/raw/FDOTHER"
OUT = out_path("demonface_live_vs_fdother_scroll_s141_20261021.json")
FRAMES = [f"FDOTHER_{n:03d}.bin" for n in range(69, 74)]   # 資源 #0x45–#0x49
WIN = 200
OX, OY = 192, 201          # 1024×768 根視窗裡遊戲區的左上角(DOSBox-X 選單列下方)
CLEAN = 0.999              # B 達到這個值才算「每個索引只對到一個顏色」


def decode(body: bytes, w: int, h: int, mode1_literal: bool) -> tuple[np.ndarray, bool]:
    """四模式 RLE 的獨立解碼(不經 tools/decode_sprite.py);透明 = 0。mode1_literal=True 是舊預設的對照。

    回傳 (像素, 是否剛好吃完本文且剛好寫滿 w×h)。
    """
    out = bytearray()
    total = w * h
    i = 0
    while len(out) < total and i < len(body):
        c = body[i]
        i += 1
        m, n = c >> 6, (c & 63) + 1
        if m == 1 and mode1_literal:
            m = 2
        if m == 0:
            out += bytes([body[i]]) * n
            i += 1
        elif m == 1:
            out += bytes([0, body[i]]) * n
            i += 1
        elif m == 2:
            out += body[i:i + n]
            i += n
        else:
            out += bytes(n)
    exact = i == len(body) and len(out) == total
    return np.frombuffer(bytes(out[:total]).ljust(total, b"\0"), dtype=np.uint8), exact


def buffer(mode1_literal: bool) -> tuple[np.ndarray, list[bool]]:
    """五幀疊成的捲動緩衝(列 = esi)與每幀是否剛好吃完寫滿。"""
    parts, exact = [], []
    for fn in FRAMES:
        d = (RAW / fn).read_bytes()
        w, h = struct.unpack_from("<HH", d, 0)
        assert w == 320, (fn, w)
        px, ok = decode(d[4:], w, h, mode1_literal)
        parts.append(px.reshape(h, w))
        exact.append(ok)
    return np.concatenate(parts), exact


def live(path) -> tuple[np.ndarray, int]:
    """回傳 (320×200 的 24-bit 顏色, 2×2 區塊不一致的個數)。"""
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int64)[OY:OY + 400, OX:OX + 640]
    key = (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]
    tl = key[0::2, 0::2]
    bad = int(((key[0::2, 1::2] != tl) | (key[1::2, 0::2] != tl) | (key[1::2, 1::2] != tl)).sum())
    return tl, bad


def _max_share(g: np.ndarray, c: np.ndarray) -> int:
    """g 已排序;每組取最大計數的總和。"""
    starts = np.flatnonzero(np.r_[True, g[1:] != g[:-1]])
    return int(np.maximum.reduceat(c, starts).sum())


def ab(idx: np.ndarray, col: np.ndarray) -> tuple[float, float, int]:
    """(A, B, 實拍非黑像素數);idx 與 col 同形狀。"""
    m = col != 0
    n = int(m.sum())
    u, c = np.unique((idx[m].astype(np.int64) << 24) | col[m], return_counts=True)
    gi, gc = u >> 24, u & 0xFFFFFF
    b = _max_share(gi, c) / n
    o = np.argsort(gc, kind="stable")
    a = _max_share(gc[o], c[o]) / n
    return a, b, n


def scores(buf: np.ndarray, col: np.ndarray, dy: int, dx: int = 0) -> tuple[float, float, int]:
    idx = buf[dy:dy + WIN].astype(np.int64)
    if dx:
        idx = np.concatenate([idx[:, dx:], np.zeros((WIN, dx), np.int64)], axis=1)
    return ab(idx, col)


def tear(buf: np.ndarray, col: np.ndarray, d: int) -> dict:
    """撕裂假設:上面 s 列是 dy1 的畫面、下面是 dy1 - 1 的畫面(擷取時畫面剛好更新到一半)。dy1 在 d ± 1 內搜尋。"""
    bestb, arg = -1.0, None
    for dy1 in (d - 1, d, d + 1):
        if dy1 < 1 or dy1 + WIN > len(buf):
            continue
        for cut in range(1, WIN):
            idx = np.concatenate([buf[dy1:dy1 + cut], buf[dy1 - 1 + cut:dy1 - 1 + WIN]])
            b = ab(idx, col)[1]
            if b > bestb:
                bestb, arg = b, (dy1, cut)
    return {"dy_top": arg[0], "dy_bottom": arg[0] - 1, "cut_row": arg[1], "B": round(bestb, 4)}


def best(buf: np.ndarray, col: np.ndarray) -> tuple[int, float, float]:
    rs = [(dy,) + scores(buf, col, dy)[:2] for dy in range(len(buf) - WIN + 1)]
    return max(rs, key=lambda r: (r[1] + r[2], -r[0]))


(BD, EXACT_D), (BL, EXACT_L) = buffer(False), buffer(True)
assert BD.shape == (735, 320), BD.shape        # doc23 §2.1 的 320×735 緩衝
assert all(EXACT_D) and not all(EXACT_L), (EXACT_D, EXACT_L)   # dither 五幀都剛好吃完寫滿,literal 不行
DIFF = int((BD != BL).sum())
assert DIFF > 0, DIFF          # 兩種解法本來就不同,否則對照沒有意義

META = json.loads((SHOTS.parent / "meta.json").read_text(encoding="utf-8"))
assert META["exe_md5"] == "33464c81e6a364fd0660141139aa8e6e", META["exe_md5"]   # 只用原版
files = sorted(SHOTS.glob("shot_*.png"))
assert len(files) == META["shots"] == 93, (len(files), META["shots"])
rows = []
col_of = {}
for p in files:
    t = float(re.fullmatch(r"shot_(\d+\.\d+)\.png", p.name).group(1))
    col, bad = live(p)
    col_of[p.name] = col
    nonblack = int((col != 0).sum())
    r = {"shot": p.name, "t": t, "nonblack": nonblack, "uneven_2x2": bad}
    if nonblack:
        dy, a, b = best(BD, col)
        ldy, la, lb = best(BL, col)
        na, nb, _ = scores(BD, col, dy, dx=1)
        r.update(dither={"dy": dy, "A": round(a, 4), "B": round(b, 4)},
                 literal={"dy": ldy, "A": round(la, 4), "B": round(lb, 4)},
                 dither_shift1px={"A": round(na, 4), "B": round(nb, 4)})
    rows.append(r)

# 分段:第一段連續全黑之前 = 捲動畫面,之後 = logo
black = [k for k, r in enumerate(rows) if r["nonblack"] == 0]
assert black, "沒有黑幕"
g0 = black[0]
g1 = g0
while g1 + 1 < len(rows) and rows[g1 + 1]["nonblack"] == 0:
    g1 += 1
pre, gap, post = rows[:g0], rows[g0:g1 + 1], rows[g1 + 1:]
assert pre and post, (len(pre), len(post))
assert all(r["nonblack"] for r in post), "logo 段又出現全黑"

TEAR_OK = 0.99            # 撕裂拼接後的門檻(拼接點附近一兩列可能正在寫入)
for r in pre + post:
    if r["dither"]["B"] < CLEAN:
        r["dither_tear"] = tear(BD, col_of[r["shot"]], r["dither"]["dy"])
        r["literal_tear"] = tear(BL, col_of[r["shot"]], r["literal"]["dy"])
clean = [r for r in pre if r["dither"]["B"] >= CLEAN]
torn = [r for r in pre if r["dither"]["B"] < CLEAN and r["dither_tear"]["B"] >= TEAR_OK]
unexplained = [r for r in pre if r["dither"]["B"] < CLEAN and r["dither_tear"]["B"] < TEAR_OK]
# 1. 捲動幀:單一 dy 下每個 RE 索引只對到一個實拍顏色(反方向也幾乎一對一);不是的,幾乎都是差一列的撕裂
assert len(clean) >= 0.75 * len(pre), (len(clean), len(pre))
assert all(r["dither"]["A"] >= 0.98 for r in clean), [r["shot"] for r in clean if r["dither"]["A"] < 0.98]
assert len(unexplained) <= 0.05 * len(pre), [r["shot"] for r in unexplained]
# 2. literal 解(舊預設):同樣的搜尋(含撕裂拼接)沒有一張到 0.9
assert max(r["literal"]["B"] for r in pre) < 0.9, max(r["literal"]["B"] for r in pre)
assert all(r["literal_tear"]["B"] < 0.9 for r in pre if "literal_tear" in r), [r["shot"] for r in pre if r.get("literal_tear", {}).get("B", 0) >= 0.9]
assert all(r["literal"]["B"] < r["dither"]["B"] for r in clean)
# 3. 虛無:同一個 dy 平移 1 px 就掉到 0.9 以下
assert max(r["dither_shift1px"]["B"] for r in clean) < 0.9, max(r["dither_shift1px"]["B"] for r in clean)
# 4. 負對照:logo 幀(不同的圖)用同一套搜尋(含撕裂拼接)也到不了 0.9
assert max(r["dither"]["B"] for r in post) < 0.9, max(r["dither"]["B"] for r in post)
assert all(r["dither_tear"]["B"] < 0.9 for r in post), [r["dither_tear"] for r in post]
# 5. 捲動方向:乾淨幀與撕裂幀(取上半)的 dy 隨時間只減不增(視窗往緩衝頂端走)
seq = [(r["t"], r["dither"]["dy"] if r in clean else r["dither_tear"]["dy_top"]) for r in clean + torn]
dys = [d for _, d in sorted(seq)]
assert all(x >= y for x, y in zip(dys, dys[1:])), dys
assert dys[0] > dys[-1], dys
# 6. 黑幕前最後一張的位置:沒有捲到 dy = 0
last_dy = pre[-1]["dither"]["dy"]
assert pre[-1] in clean and last_dy > 0, (pre[-1]["shot"], last_dy)

span_s = round(clean[-1]["t"] - clean[0]["t"], 2)
rate = round((clean[0]["dither"]["dy"] - clean[-1]["dither"]["dy"]) / span_s, 1)
ev = {"note": "原版 FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e,DOSBox-X(core=normal、cycles=5000)開場連拍 93 張,"
              "不送按鍵;FDOTHER_069–073 取自 extracted/raw。LOG CONFIRMED(實拍)+ STATIC ANALYSIS(資產解碼)。",
      "inputs": {"shots_dir": rel(SHOTS), "meta": rel(SHOTS.parent / "meta.json"),
                 "fdother": [rel(RAW / fn) for fn in FRAMES]},
      "criterion": {"B": "每個 RE 索引底下最常見實拍顏色的比例(加權,只看實拍非黑像素)", "clean_threshold": CLEAN,
                    "A": "每個實拍顏色底下最常見 RE 索引的比例", "dy": "320×735 緩衝的起始列 = 捲動迴圈 esi",
                    "tear": "上面 cut_row 列取 dy_top、下面取 dy_top - 1,拼接後 B ≥ TEAR_OK 算撕裂幀", "tear_threshold": TEAR_OK},
      "buffer": {"frames": FRAMES, "shape": list(BD.shape), "dither_exact": EXACT_D, "literal_exact": EXACT_L,
                 "dither_vs_literal_pixels_differ": DIFF},
      "segments": {"scroll": len(pre), "scroll_clean": len(clean), "scroll_torn_one_row": len(torn),
                   "scroll_unexplained": [r["shot"] for r in unexplained],
                   "black_gap": len(gap), "black_gap_t": [gap[0]["t"], gap[-1]["t"]], "logo": len(post)},
      "scroll_dy": {"first": dys[0], "last_before_black": last_dy, "rows_per_s": rate,
                    "t_first": pre[0]["t"], "t_last_before_black": pre[-1]["t"]},
      "max_B": {"literal_scroll": max(r["literal"]["B"] for r in pre),
                "literal_tear_scroll": max(r["literal_tear"]["B"] for r in pre if "literal_tear" in r),
                "dither_shift1px_clean": max(r["dither_shift1px"]["B"] for r in clean),
                "dither_logo": max(r["dither"]["B"] for r in post),
                "dither_tear_logo": max(r["dither_tear"]["B"] for r in post)},
      "rows": rows,
      "finding": f"捲動幀 {len(pre)} 張:{len(clean)} 張單一 dy 下 B = 1(每個索引只對到一個實拍顏色)、A ≥ 0.98;"
                 f"{len(torn)} 張是差一列的撕裂(拼接後 B ≥ {TEAR_OK});{len(unexplained)} 張兩種都解釋不了,照實列出。"
                 "literal 解(含撕裂拼接)、平移 1 px、logo 幀都到不了 0.9。dy 從 "
                 f"{dys[0]} 單調減到 {last_dy}(約 {rate} 列/秒),接著全黑 {len(gap)} 張、再進 logo。",
      "conclusion": "分鏡⑨的惡魔臉就是 FDOTHER_069–073 疊成的捲動緩衝捲向頂端(#0x45 / #0x46)的畫面:dither 解逐像素對上,"
                    "舊的 literal 解對不上。"
                    f"這次實拍裡捲動在 dy = {last_dy} 就切黑,沒有看到 doc23 §2.4⑦ 推導的「捲到 esi = 0 再停 1000ms」;"
                    "黑幕裡沒有紅閃光(取樣約 0.04 秒一張,更短的閃光排除不了)。"}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", len(pre), len(clean), len(torn), len(unexplained), len(gap), len(post), dys[0], last_dy)
