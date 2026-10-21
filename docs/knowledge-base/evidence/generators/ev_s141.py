"""續一百四十一證據(續一百四十二更正與加強):evidence/demonface_live_vs_fdother_scroll_s141_20261021.json。

doc23 §2.4⑦ 的「開場分鏡⑨ 惡魔臉 = FDOTHER #0x45 / #0x46(FDOTHER_069 / 070)捲動到頂」重做比對。當時的比對圖是
decode_sprite.py 續一百四十以前的預設(模式 1 當 literal)解的,而且用的 frame_184.png 已不在本機。
輸入:原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)在 DOSBox-X 的開場連拍 93 張(.wsl_build/s141_demonface/,
t0 起 39.5–44.1 秒,不送按鍵)、extracted/raw 的 FDOTHER_069–073(捲動立繪五幀,doc23 §2.1 的 320×735 緩衝)、
捲動用的兩份調色盤(FDOTHER #0x65 / #0x66)、ANI_000 / ANI_001,以及原版 FD2.EXE 本身(讀 title_seq 的觸發常數)。

判準一(與調色盤無關):同一幀裡同一個調色盤索引只會顯示一個顏色。對每張實拍(遊戲區 640×400 取 2× 的左上點 = 320×200)
搜尋垂直位移 dy(= 捲動迴圈的 esi,0–535),只看實拍非黑像素:
    B = 每個 RE 索引底下最常見的實拍顏色所佔比例(加權);解碼正確且對齊 → B = 1。
    A = 每個實拍顏色底下最常見的 RE 索引所佔比例(加權);不同索引可能同色,所以 A 可略低於 1。
判準二(續一百四十二,絕對):實拍顏色 = 調色盤 6-bit 值以 (v << 2) | (v >> 4) 擴成 8-bit 後的 RGB,逐像素相等。
    捲動段只有 #0x65 / #0x66 兩份調色盤;撕裂幀(畫面正在更新)的每個像素來自 dy - 1、dy、dy + 1 之一。
    對照(literal 解、平移 1 px、ANI 幀對捲動緩衝)給同樣的自由度。
title_seq 的觸發(doc39 §10.5;位址綁原版 md5,直接讀 EXE 位元組):
    esi == 0x19 → wrapper 0x1f81e:清成黑畫面、播 ANI #0(金鎖)。黑幕之後那段是 ANI #0,不是 logo(續一百四十一誤標)。
    esi 命中 0x5204e 的表 → 換成 #0x66 調色盤,11 步後換回 #0x65(捲動中的閃光)。
這次連拍只拍到 dy 103 → 26 與 ANI #0 的前段:esi 24 → 0、esi == 10 的浮空城插播、esi == 0 的停留 1000ms、
之後的轉場(doc23 §2.4⑤ 的紅閃光)都不在拍攝範圍內,本證據對它們不下結論。
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys

import numpy as np
from PIL import Image

from _evpaths import GAME, ROOT, TOOLS, out_path, rel, require_inputs  # noqa: E402
require_inputs(__file__)
sys.path.insert(0, str(TOOLS))
import decode_ani  # noqa: E402
from disasm_le import object_bytes  # noqa: E402
from le_xref import parse_le  # noqa: E402

SHOTS = ROOT / ".wsl_build/s141_demonface/shots"
RAW = ROOT / "extracted/raw/FDOTHER"
ANI = ROOT / "extracted/raw/ANI"
EXE = GAME / "FD2.EXE"
OUT = out_path("demonface_live_vs_fdother_scroll_s141_20261021.json")
FRAMES = [f"FDOTHER_{n:03d}.bin" for n in range(69, 74)]   # 資源 #0x45–#0x49
WIN = 200
OX, OY = 192, 201          # 1024×768 根視窗裡遊戲區的左上角(DOSBox-X 選單列下方)
CLEAN = 0.999              # B 達到這個值才算「每個索引只對到一個顏色」
CTRL_MAX = 0.99            # 絕對判準下,對照給同樣自由度也不能到這裡
MIN_PX = 1000              # ANI 段非黑像素少於這個數的幀(幾乎全黑)不拿來定幀序
MD5 = "33464c81e6a364fd0660141139aa8e6e"


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


def rgb(pal6: bytes) -> np.ndarray:
    """768 byte 的 6-bit 調色盤 → 每個索引的 24-bit 顏色(DOSBox-X 的擴展:(v << 2) | (v >> 4))。"""
    a = np.frombuffer(bytes(pal6), dtype=np.uint8).reshape(256, 3).astype(np.int64)
    a = (a << 2) | (a >> 4)
    return (a[:, 0] << 16) | (a[:, 1] << 8) | a[:, 2]


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


def shifted(buf: np.ndarray, dx: int) -> np.ndarray:
    """整個緩衝往左平移 dx 欄(右邊補 0);dx = 0 原樣。"""
    if not dx:
        return buf
    return np.concatenate([buf[:, dx:], np.zeros((len(buf), dx), buf.dtype)], axis=1)


def scores(buf: np.ndarray, col: np.ndarray, dy: int) -> tuple[float, float, int]:
    return ab(buf[dy:dy + WIN].astype(np.int64), col)


def best(buf: np.ndarray, col: np.ndarray) -> tuple[int, float, float]:
    rs = [(dy,) + scores(buf, col, dy)[:2] for dy in range(len(buf) - WIN + 1)]
    return max(rs, key=lambda r: (r[1] + r[2], -r[0]))


def exact_under(buf: np.ndarray, col: np.ndarray, dy: int, pals: dict) -> list[str]:
    """單一 dy、整張(含黑)逐像素等於哪幾份調色盤的顏色。"""
    idx = buf[dy:dy + WIN]
    return [k for k, P in pals.items() if bool((P[idx] == col).all())]


def pal_split(buf: np.ndarray, col: np.ndarray, dy: int, pals: dict) -> dict | None:
    """單一 dy 下畫面掃描途中換了調色盤:上面整列是舊調色盤、下面整列是新調色盤,中間最多一列正在換。

    正在換的那一列:調色盤是從索引 0 往上逐個寫入(0x11d40),所以這一列裡已顯示新顏色的索引都小於仍是舊顏色的索引。
    回傳 {"top", "bottom", "mixed_row", "new_idx", "old_idx"};不符合時回傳 None。
    """
    idx = buf[dy:dy + WIN]
    for top, bottom in ((a, b) for a in pals for b in pals if a != b):
        et, eb = pals[top][idx] == col, pals[bottom][idx] == col
        rt, rb = et.all(axis=1), eb.all(axis=1)
        y0 = 0
        while y0 < WIN and rt[y0]:
            y0 += 1
        y1 = y0
        while y1 < WIN and not rb[y1]:
            y1 += 1
        if y0 == 0 or y0 == WIN or not rb[y1:].all() or y1 - y0 > 1 or not rt[:y0].all():
            continue
        if y1 == y0:
            return {"top": top, "bottom": bottom, "mixed_row": None, "new_idx": [], "old_idx": []}
        row, ok = idx[y0], et[y0] | eb[y0]
        dif = pals[top][row] != pals[bottom][row]
        new = sorted(set(row[dif & eb[y0]].tolist()))
        old = sorted(set(row[dif & et[y0] & ~eb[y0]].tolist()))
        if ok.all() and new and old and max(new) < min(old):
            return {"top": top, "bottom": bottom, "mixed_row": y0, "new_idx": new, "old_idx": old}
    return None


def free(buf: np.ndarray, col: np.ndarray, dy: int, pals: dict) -> float:
    """撕裂假設下的絕對判準:實拍非黑像素裡,等於某個 P[buf[c + y, x]](c ∈ {dy-1, dy, dy+1},P ∈ pals)的比例。"""
    ok = np.zeros(col.shape, bool)
    for c in (dy - 1, dy, dy + 1):
        if 0 <= c and c + WIN <= len(buf):
            idx = buf[c:c + WIN]
            for P in pals.values():
                ok |= P[idx] == col
    m = col != 0
    return float(ok[m].mean())


def bands(buf: np.ndarray, col: np.ndarray, dy: int, pals: dict) -> list[str]:
    """逐列標出整列等於哪個 (c, 調色盤);整列對不上單一來源、但每個像素都有來源的記 mixed,否則 ?。壓成區段。"""
    lab = []
    for y in range(WIN):
        hit, ok = None, np.zeros(320, bool)
        for c in (dy, dy - 1, dy + 1, dy - 2, dy + 2):
            if not (0 <= c and c + y < len(buf)):
                continue
            for k, P in pals.items():
                eq = P[buf[c + y]] == col[y]
                ok |= eq
                if hit is None and eq.all():
                    hit = f"{c}/{k}"
        lab.append(hit or ("mixed" if ok.all() else "?"))
    out, s = [], 0
    for y in range(1, WIN + 1):
        if y == WIN or lab[y] != lab[s]:
            out.append(f"{s}-{y - 1}:{lab[s]}")
            s = y
    return out


def ani_colours(fn: str) -> list[np.ndarray]:
    """用 tools/decode_ani.py 的 VM 逐幀執行,回傳每幀的 24-bit 顏色(VM 當下的調色盤)。"""
    d = (ANI / fn).read_bytes()
    hd = decode_ani.parse_header(d)
    pal, fb = bytearray(768), bytearray(320 * 200)
    out = []
    for _i, _cs, cc, _r0, _r1, sc in decode_ani.iter_frames(d, hd["frame_count"]):
        decode_ani.run_vm(sc, cc, pal, fb)
        out.append(rgb(pal)[np.frombuffer(bytes(fb), dtype=np.uint8).reshape(200, 320)])
    return out


def ani_match(F: list[np.ndarray], col: np.ndarray) -> dict:
    """單幀完全相等的幀號;沒有的話,相鄰兩幀逐像素擇一(畫面正在更新)的最高比例。"""
    hits = [k for k, f in enumerate(F) if bool((f == col).all())]
    if hits:
        return {"exact": hits, "frac": 1.0}
    fr, k = max((float(((F[k] == col) | (F[k + 1] == col)).mean()), k) for k in range(len(F) - 1))
    return {"exact": [], "pair": [k, k + 1], "frac": round(fr, 4)}


# ---- 原版 FD2.EXE:title_seq 捲動迴圈的觸發常數(doc23 §2.1、doc39 §10.5)----
EXE_B = EXE.read_bytes()
assert hashlib.md5(EXE_B).hexdigest() == MD5, "只用原版 FD2.EXE"
LE = parse_le(EXE_B)


def code(lin: int, n: int) -> bytes:
    return object_bytes(EXE_B, LE, lin, n)


assert code(0x1fa85, 5) == b"\xbe\x17\x02\x00\x00"           # mov esi, 0x217:從 535 往下捲
assert code(0x1fadd, 2) == b"\x83\xfe"                        # cmp esi, imm8
T_ANI = code(0x1fadd, 3)[2]                                    # = 0x19
assert code(0x1fae2, 6)[0::2] == b"\x6a\x6a\x6a"              # push C; push B; push A → wrapper 0x1f81e(A, B, C)
ANI_INDEX = code(0x1fae6, 2)[1]                                # A = ANI 資源索引
assert code(0x1f8c8, 5) == b"\xb9\x0f\x00\x00\x00"           # mov ecx, 15:表有 15 個 dword
assert code(0x1f8cf, 5) == b"\xbe\x4e\x20\x00\x00"           # mov esi, 0x204e(fixup → 0x5204e)
assert code(0x1fbb7, 8) == b"\x0f\xb6\x44\x24\x58\x3b\x34\x84"   # movzx eax, [esp+0x58];cmp esi, [esp+eax*4]
assert code(0x1fbd9, 1) == b"\x6a" and code(0x1fc0f, 1) == b"\x6a"
PAL_FLASH, PAL_BASE = code(0x1fbd9, 2)[1], code(0x1fc0f, 2)[1]   # 命中換 0x66、到期換回 0x65
assert code(0x1fc08, 4) == b"\x83\x7c\x24\x4c"                # cmp [esp+0x4c], imm8
FLASH_STEPS = code(0x1fc08, 5)[4]                              # = 11
TABLE = list(struct.unpack("<15I", code(0x5204e, 60)))
assert TABLE[-1] == 1000 and all(x > y for x, y in zip(TABLE, TABLE[1:-1])), TABLE   # 遞減,1000 當結尾
assert T_ANI not in TABLE

PALS = {f"#{PAL_BASE:#x}": rgb((RAW / f"FDOTHER_{PAL_BASE:03d}.bin").read_bytes()),
        f"#{PAL_FLASH:#x}": rgb((RAW / f"FDOTHER_{PAL_FLASH:03d}.bin").read_bytes())}
BASE_K, FLASH_K = list(PALS)
FLASH_IDX = np.flatnonzero(PALS[BASE_K] != PALS[FLASH_K])
assert 0 < len(FLASH_IDX) < 256, len(FLASH_IDX)


def in_flash(dy: int) -> bool:
    """dy 落在某個命中值 h 的閃光區間 [h - FLASH_STEPS, h] 內(兩端那一步換盤發生在複製之後,兩種都可能)。"""
    return any(h - FLASH_STEPS <= dy <= h for h in TABLE[:-1])


def strictly_flash(dy: int) -> bool:
    return any(h - FLASH_STEPS < dy < h for h in TABLE[:-1])


(BD, EXACT_D), (BL, EXACT_L) = buffer(False), buffer(True)
assert BD.shape == (735, 320), BD.shape        # doc23 §2.1 的 320×735 緩衝
assert all(EXACT_D) and not all(EXACT_L), (EXACT_D, EXACT_L)   # dither 五幀都剛好吃完寫滿,literal 不行
DIFF = int((BD != BL).sum())
assert DIFF > 0, DIFF          # 兩種解法本來就不同,否則對照沒有意義
BS = shifted(BD, 1)

META = json.loads((SHOTS.parent / "meta.json").read_text(encoding="utf-8"))
assert META["exe_md5"] == MD5, META["exe_md5"]   # 只用原版
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
        na, nb, _ = scores(BS, col, dy)
        r.update(dither={"dy": dy, "A": round(a, 4), "B": round(b, 4)},
                 literal={"dy": ldy, "A": round(la, 4), "B": round(lb, 4)},
                 dither_shift1px={"A": round(na, 4), "B": round(nb, 4)},
                 abs_exact=exact_under(BD, col, dy, PALS),
                 abs_free={"dither": round(free(BD, col, dy, PALS), 4), "literal": round(free(BL, col, ldy, PALS), 4),
                           "dither_shift1px": round(free(BS, col, dy, PALS), 4)})
    rows.append(r)

# 分段:第一段連續全黑之前 = 捲動畫面,之後 = esi == T_ANI 觸發的 ANI 插播
black = [k for k, r in enumerate(rows) if r["nonblack"] == 0]
assert black, "沒有黑幕"
g0 = black[0]
g1 = g0
while g1 + 1 < len(rows) and rows[g1 + 1]["nonblack"] == 0:
    g1 += 1
pre, gap, post = rows[:g0], rows[g0:g1 + 1], rows[g1 + 1:]
assert pre and post, (len(pre), len(post))
assert all(r["nonblack"] for r in post), "ANI 段又出現全黑"

clean = [r for r in pre if r["dither"]["B"] >= CLEAN]
torn = [r for r in pre if r["dither"]["B"] < CLEAN]
for r in torn:
    r["abs_bands"] = bands(BD, col_of[r["shot"]], r["dither"]["dy"], PALS)
unexplained = [r for r in pre if r["abs_free"]["dither"] < 1.0]
# 1. 捲動幀:單一 dy 下每個 RE 索引只對到一個實拍顏色(反方向也幾乎一對一)
assert len(clean) >= 0.75 * len(pre), (len(clean), len(pre))
assert all(r["dither"]["A"] >= 0.98 for r in clean), [r["shot"] for r in clean if r["dither"]["A"] < 0.98]
# 2. 絕對判準:乾淨幀整張逐像素等於某一份調色盤的顏色;每一張捲動幀(含撕裂)的非黑像素都來自 dy - 1 / dy / dy + 1
for r in clean:
    if not r["abs_exact"]:
        r["abs_pal_split"] = pal_split(BD, col_of[r["shot"]], r["dither"]["dy"], PALS)
split = [r for r in clean if not r["abs_exact"]]
assert all(r["abs_pal_split"] for r in split), [r["shot"] for r in split if not r["abs_pal_split"]]
# 換盤發生在那一步複製之後:上 #0x66 下 #0x65 只能在到期那一步(h - FLASH_STEPS),上 #0x65 下 #0x66 只能在命中那一步(h)
for r in split:
    s, d = r["abs_pal_split"], r["dither"]["dy"]
    want = [h - FLASH_STEPS for h in TABLE[:-1]] if s["top"] == FLASH_K else TABLE[:-1]
    assert d in want, (r["shot"], d, s)
assert not unexplained, [(r["shot"], r["abs_free"]["dither"]) for r in unexplained]
assert all("?" not in "".join(r["abs_bands"]) for r in torn), [r["shot"] for r in torn if "?" in "".join(r["abs_bands"])]
# 3. literal 解(舊預設):判準一沒有一張到 0.9;判準二給同樣的撕裂自由度也到不了 CTRL_MAX
assert max(r["literal"]["B"] for r in pre) < 0.9, max(r["literal"]["B"] for r in pre)
assert all(r["literal"]["B"] < r["dither"]["B"] for r in clean)
assert max(r["abs_free"]["literal"] for r in pre) < CTRL_MAX, max(r["abs_free"]["literal"] for r in pre)
# 4. 虛無:同一個 dy 平移 1 px,兩種判準都掉下來
assert max(r["dither_shift1px"]["B"] for r in clean) < 0.9, max(r["dither_shift1px"]["B"] for r in clean)
assert max(r["abs_free"]["dither_shift1px"] for r in pre) < CTRL_MAX, max(r["abs_free"]["dither_shift1px"] for r in pre)
# 5. 負對照:ANI 段(不同的圖)對捲動緩衝用同一套搜尋也對不上
assert max(r["dither"]["B"] for r in post) < 0.9, max(r["dither"]["B"] for r in post)
assert max(r["abs_free"]["dither"] for r in post) < CTRL_MAX, max(r["abs_free"]["dither"] for r in post)
# 6. 捲動方向:乾淨幀與撕裂幀的 dy 隨時間只減不增(視窗往緩衝頂端走)
dys = [r["dither"]["dy"] for r in sorted(clean + torn, key=lambda r: r["t"])]
assert all(x >= y for x, y in zip(dys, dys[1:])), dys
assert dys[0] > dys[-1], dys
# 7. 閃光:只用 #0x66 才對得上的幀都在表上某個命中值之後 FLASH_STEPS 步內;只用 #0x65 的幀不在區間內部
pal_rows = [r for r in clean if len(r["abs_exact"]) == 1]
flash = [r for r in pal_rows if r["abs_exact"] == [FLASH_K]]
base = [r for r in pal_rows if r["abs_exact"] == [BASE_K]]
assert flash and base, (len(flash), len(base))
assert all(in_flash(r["dither"]["dy"]) for r in flash), [(r["shot"], r["dither"]["dy"]) for r in flash if not in_flash(r["dither"]["dy"])]
assert not any(strictly_flash(r["dither"]["dy"]) for r in base), [(r["shot"], r["dither"]["dy"]) for r in base if strictly_flash(r["dither"]["dy"])]
lo, hi = dys[-1], dys[0]
expected_hits = sorted(h for h in TABLE[:-1] if h - FLASH_STEPS <= hi and h >= lo)
seen_hits = sorted({h for r in flash for h in TABLE[:-1] if h - FLASH_STEPS <= r["dither"]["dy"] <= h})
assert seen_hits == expected_hits, (seen_hits, expected_hits)
# 8. 黑幕的位置:最後一張捲動畫面在 esi == T_ANI 之前 1–2 步(0x1f81e 先把畫面清黑)
last_dy = pre[-1]["dither"]["dy"]
assert pre[-1] in clean and 1 <= last_dy - T_ANI <= 2, (pre[-1]["shot"], last_dy, T_ANI)
# 9. 黑幕之後是 ANI #ANI_INDEX:非幾乎全黑的幀都逐像素等於某一幀(或相鄰兩幀正在更新),幀號隨時間不減;ANI #1(logo「2」)對不上
F0 = ani_colours(f"ANI_{ANI_INDEX:03d}.bin")
F1 = ani_colours("ANI_001.bin")
assert ANI_INDEX != 1
for r in post:
    r["ani"] = ani_match(F0, col_of[r["shot"]])
    r["ani_control_001"] = ani_match(F1, col_of[r["shot"]])
solid = [r for r in post if r["nonblack"] >= MIN_PX]
assert len(solid) >= 0.75 * len(post), (len(solid), len(post))
assert all(r["ani"]["frac"] >= CLEAN for r in solid), [(r["shot"], r["ani"]["frac"]) for r in solid if r["ani"]["frac"] < CLEAN]
assert sum(bool(r["ani"]["exact"]) for r in solid) >= 0.6 * len(solid)
seq_k = [min(r["ani"]["exact"]) if r["ani"]["exact"] else r["ani"]["pair"][0] for r in solid]
assert all(x <= y for x, y in zip(seq_k, seq_k[1:])) and seq_k[0] < seq_k[-1], seq_k
assert max(r["ani_control_001"]["frac"] for r in solid) < 0.9, max(r["ani_control_001"]["frac"] for r in solid)

span_s = round(clean[-1]["t"] - clean[0]["t"], 2)
rate = round((clean[0]["dither"]["dy"] - clean[-1]["dither"]["dy"]) / span_s, 1)
tear_dir = {"top_newer": 0, "bottom_newer": 0, "other": 0}
for r in torn:
    cs = [int(b.split(":")[1].split("/")[0]) for b in r["abs_bands"] if b.split(":")[1] not in ("mixed", "?")]
    srcs = [c for k, c in enumerate(cs) if k == 0 or c != cs[k - 1]]
    tear_dir["top_newer" if srcs == sorted(srcs) and len(srcs) == 2 else
             "bottom_newer" if srcs == sorted(srcs, reverse=True) and len(srcs) == 2 else "other"] += 1
ev = {"note": "原版 FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e,DOSBox-X(core=normal、cycles=5000)開場連拍 93 張,"
              "不送按鍵;FDOTHER / ANI 取自 extracted/raw,觸發常數直接讀原版 FD2.EXE。LOG CONFIRMED(實拍)+ STATIC ANALYSIS(資產解碼、反組譯)。"
              "續一百四十二更正:黑幕之後那段是 esi == 0x19 觸發的 ANI #0(金鎖),續一百四十一誤標為 logo;"
              "續一百四十一「沒有捲到 esi = 0 再停 1000ms」「沒有紅閃光」是拍攝範圍不夠造成的誤判,撤回。"
              "檔名的時間是呼叫 import 之前取的,一張約 0.04 秒,實際截取時刻晚一點。",
      "inputs": {"shots_dir": rel(SHOTS), "meta": rel(SHOTS.parent / "meta.json"),
                 "fdother": [rel(RAW / fn) for fn in FRAMES],
                 "palettes": [rel(RAW / f"FDOTHER_{PAL_BASE:03d}.bin"), rel(RAW / f"FDOTHER_{PAL_FLASH:03d}.bin")],
                 "ani": [rel(ANI / f"ANI_{ANI_INDEX:03d}.bin"), rel(ANI / "ANI_001.bin")], "exe": rel(EXE)},
      "title_seq": {"esi_start": 0x217, "ani_trigger_esi": T_ANI, "ani_index": ANI_INDEX,
                    "flash_table_0x5204e": TABLE, "flash_palette": PAL_FLASH, "base_palette": PAL_BASE,
                    "flash_steps": FLASH_STEPS, "flash_palette_indices_differ": FLASH_IDX.tolist()},
      "criterion": {"B": "每個 RE 索引底下最常見實拍顏色的比例(加權,只看實拍非黑像素)", "clean_threshold": CLEAN,
                    "A": "每個實拍顏色底下最常見 RE 索引的比例", "dy": "320×735 緩衝的起始列 = 捲動迴圈 esi",
                    "abs_exact": "單一 dy、整張(含黑)逐像素等於哪份調色盤的 8-bit 顏色((v << 2) | (v >> 4))",
                    "abs_free": "實拍非黑像素裡,等於 dy - 1 / dy / dy + 1 在兩份調色盤之一下顏色的比例;對照給同樣自由度",
                    "abs_bands": "撕裂幀逐列的來源(c/調色盤);mixed = 同一列裡左右來源不同", "control_max": CTRL_MAX,
                    "ani": "ANI 幀以 tools/decode_ani.py 的 VM 逐幀執行;整張相等的幀號,或相鄰兩幀逐像素擇一的比例",
                    "ani_min_nonblack": MIN_PX},
      "buffer": {"frames": FRAMES, "shape": list(BD.shape), "dither_exact": EXACT_D, "literal_exact": EXACT_L,
                 "dither_vs_literal_pixels_differ": DIFF},
      "segments": {"scroll": len(pre), "scroll_clean": len(clean), "scroll_torn": len(torn),
                   "scroll_torn_direction": tear_dir, "scroll_unexplained": [r["shot"] for r in unexplained],
                   "scroll_palette_base": len(base), "scroll_palette_flash": len(flash),
                   "black_gap": len(gap), "black_gap_t": [gap[0]["t"], gap[-1]["t"]],
                   "ani_insert": len(post), "ani_insert_solid": len(solid),
                   "ani_frames_seen": [seq_k[0], max(max(r["ani"]["exact"] or r["ani"]["pair"]) for r in solid)],
                   "ani_frame_count": len(F0)},
      "scroll_dy": {"first": dys[0], "last_before_black": last_dy, "rows_per_s": rate,
                    "t_first": pre[0]["t"], "t_last_before_black": pre[-1]["t"], "flash_hits_seen": seen_hits},
      "max_control": {"literal_B_scroll": max(r["literal"]["B"] for r in pre),
                      "dither_shift1px_B_clean": max(r["dither_shift1px"]["B"] for r in clean),
                      "ani_vs_scroll_B": max(r["dither"]["B"] for r in post),
                      "literal_abs_free": max(r["abs_free"]["literal"] for r in pre),
                      "dither_shift1px_abs_free": max(r["abs_free"]["dither_shift1px"] for r in pre),
                      "ani_vs_scroll_abs_free": max(r["abs_free"]["dither"] for r in post),
                      "ani001_vs_ani_insert": max(r["ani_control_001"]["frac"] for r in solid)},
      "not_covered": ["esi 24 → 0 的捲動", "esi == 10 的浮空城插播(0x1f73f)", "esi == 0 的停留 1000ms",
                      "捲動迴圈結束後的轉場(doc23 §2.4⑤ 的紅閃光)"],
      "rows": rows,
      "finding": f"捲動幀 {len(pre)} 張:{len(clean)} 張單一 dy 下 B = 1,而且整張逐像素等於 #0x65 或 #0x66 調色盤的顏色;"
                 f"{len(torn)} 張是撕裂(每個非黑像素都來自 dy - 1 / dy / dy + 1,上新下舊 {tear_dir['top_newer']}、"
                 f"上舊下新 {tear_dir['bottom_newer']}、其他 {tear_dir['other']}),沒有解釋不了的。"
                 f"#0x66 閃光出現在表上命中值 {seen_hits} 之後 {FLASH_STEPS} 步內。dy 從 {dys[0]} 單調減到 {last_dy}"
                 f"(約 {rate} 列/秒),在 esi == {T_ANI} 清黑 {len(gap)} 張,接著是 ANI #{ANI_INDEX} 第 {seq_k[0]} 幀起"
                 f"(共 {len(F0)} 幀),拍到第 {max(max(r['ani']['exact'] or r['ani']['pair']) for r in solid)} 幀為止。",
      "conclusion": "分鏡⑨的惡魔臉就是 FDOTHER_069–073 疊成的捲動緩衝捲向頂端(#0x45 / #0x46)的畫面:dither 解逐像素對上,"
                    "舊的 literal 解對不上。實拍的時間順序與 title_seq 的觸發常數一致(閃光表、esi == 0x19 的 ANI #0 插播)。"
                    f"連拍在 ANI #{ANI_INDEX} 播到第 {max(max(r['ani']['exact'] or r['ani']['pair']) for r in solid)} 幀(共 {len(F0)} 幀)時結束,esi 24 → 0、浮空城插播、esi == 0 的停留與之後的轉場都沒拍到,本證據對它們不下結論。"}
OUT.write_bytes((json.dumps(ev, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
print("ok", len(pre), len(clean), len(torn), len(unexplained), len(gap), len(post), dys[0], last_dy, seen_hits, tear_dir)
