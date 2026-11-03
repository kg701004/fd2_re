#!/usr/bin/env python3
"""炎龍騎士團2 — 從 DOSBox-X 截圖以程式判讀畫面上的字(字模逐點全等比對,不是 OCR 猜測)。

為什麼需要這支工具
------------------
續一百八十七「仍留」:截圖上的文字是目視判讀。以前用到截圖文字的證據(ev_s138 新遊戲開場的對白)
各自在產生器裡寫一段固定座標的比對,換一張圖就要重寫。本工具把它做成通用的:

1. `frame()`:1024 × 768 的 DOSBox-X 截圖(2 倍放大、原點 (192, 201))還原成 320 × 200;每個 2 × 2
   區塊四點必須同色(strict),否則拒絕 —— 調色盤在掃描途中改變的圖不能拿來判讀字。
2. `scan()`:**整張畫面每個位置、每個顏色**都試。判準(與 ev_s138 `glyph_at` 相同):16 × 16 窗口裡
   「等於顏色 c 的點」的位元圖要和某個字模**完全相同** —— 字模的 1 全是 c,字模的 0 沒有任何 c。
   這是全等比對:差一個點、錯一個像素位置都不算;不設門檻、不取最像的。
3. `lines()`:同一列、同一色、x 間距 16 的字連成一行(中間最多 `MAX_BLANK` 個空白格)。
4. `match_lines()`:把每一行對到 FDTXT 字串的「原生行」(以 0xFFFE 換行、0xFFFD 翻頁、開框碼切開);
   0xFFFA(數字插入)對 1 .. 10 個數字字模並取出數值,0xFFFB / 0xFFFC(執行期插入)可對任意長度。
   只回報**全行相同**(full)或**行首相同**(prefix,打字機效果顯示到一半)的對應,並列出全部候選。

整張圖找不到任何字也是結果(`hits` = 0),不是錯誤;但 `frame()` 拒絕的圖是讀不了,另外回報。

用法:
    python tools/fd2_screen_text.py SHOT.png [SHOT2.png ...] [--json OUT.json] [--no-strict]
    python tools/fd2_screen_text.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = ROOT / "extracted/raw/FDOTHER/FDOTHER_004.bin"
FDTXT_DIR = ROOT / "extracted/raw/FDTXT"
GLYPH_MAP_PATH = ROOT / "docs/data/glyph_map.json"

GW = GH = 16
GB = 32
# DOSBox-X 1024 × 768 截圖:320 × 200 的畫面 2 倍放大,左上角在 (192, 201)(ev_s138 / ev_s141 同一設定)
SHOT_SIZE, ORIGIN, SCALE = (1024, 768), (192, 201), 2
SCREEN_W, SCREEN_H = 320, 200
MAX_BLANK = 2                       # 一行裡最多容許連續 2 個空白格,再多就切成兩行
DIGITS = tuple(range(10))           # glyph 0 .. 9 = '0' .. '9'(glyph_map.json)
NUM_CODE, NEWLINE, PAGE = 0xFFFA, 0xFFFE, 0xFFFD
INSERT_CODES = {0xFFFB, 0xFFFC}     # 執行期插入(名稱等),長度不定
OPEN_BOX = {0xFFEC, 0xFFED, 0xFFEE, 0xFFEF}  # 開框碼,後面跟 1 個 operand(decode_story_text.OPEN_BOX)
STR_END = 0xFFFF
MAX_DIGITS = 10

# token 種類:glyph 值本身(int ≥ 0)、數字插入、任意插入
TOK_NUM, TOK_ANY = -1, -2


@dataclass
class Hit:
    """畫面上一個全等的字模。

    Attributes:
        y: 字模左上角的列(320 × 200 座標)。
        x: 字模左上角的欄。
        color: 字的顏色(0xRRGGBB)。
        glyphs: 點陣相同的字模索引(本字型沒有重複點陣,通常只有 1 個)。
    """

    y: int
    x: int
    color: int
    glyphs: tuple[int, ...]


@dataclass
class Line:
    """同列、同色、x 間距 16 的一串字。

    Attributes:
        y: 列。
        x: 第一個字的欄。
        color: 顏色。
        cells: 每格的候選字模;空白格為 None。
    """

    y: int
    x: int
    color: int
    cells: list[tuple[int, ...] | None] = field(default_factory=list)


@dataclass
class Match:
    """一行對到某個字串的某一原生行。

    Attributes:
        file: FDTXT 檔名。
        string: 字串序號。
        line: 該字串的第幾個原生行(0 起)。
        kind: "full"(全行相同)或 "prefix"(畫面上的行是原生行的開頭)。
        numbers: 0xFFFA 位置讀到的數值(依出現順序)。
        literal: 逐字對上的格數(數字插入、任意插入不算)。
    """

    file: str
    string: int
    line: int
    kind: str
    numbers: list[int]
    literal: int


# ---------------------------------------------------------------- 字型
def load_font(path: Path = FONT_PATH) -> bytes:
    """讀字型(FDOTHER #4,每字 32 bytes、16 × 16、高位在左)。"""
    return Path(path).read_bytes()


def glyph_index(font: bytes) -> dict[bytes, tuple[int, ...]]:
    """點陣 32 bytes → 字模索引;全空白的字模不收(空白不是可比對的證據)。"""
    idx: dict[bytes, list[int]] = {}
    for g in range(len(font) // GB):
        b = font[g * GB:(g + 1) * GB]
        if any(b):
            idx.setdefault(b, []).append(g)
    return {k: tuple(v) for k, v in idx.items()}


def blank_glyphs(font: bytes) -> set[int]:
    """全 0 的字模(畫面上是空白格)。"""
    return {g for g in range(len(font) // GB) if not any(font[g * GB:(g + 1) * GB])}


# ---------------------------------------------------------------- 畫面
def frame(path: Path | str, strict: bool = True) -> np.ndarray:
    """截圖 → 320 × 200 的 0xRRGGBB 陣列。

    Args:
        path: 1024 × 768 的 DOSBox-X 截圖,或已是 320 × 200 的圖。
        strict: True 時 2 × 2 區塊四點不同色就拒絕(ValueError)。

    Returns:
        (200, 320) 的 int64 陣列。

    Raises:
        ValueError: 尺寸不認得,或 strict 下放大區塊不一致。
    """
    from PIL import Image
    a = np.array(Image.open(path).convert("RGB")).astype(np.int64)
    h, w = a.shape[:2]
    if (w, h) == (SCREEN_W, SCREEN_H):
        v = a
    elif (w, h) == SHOT_SIZE:
        x0, y0 = ORIGIN
        b = a[y0:y0 + SCREEN_H * SCALE, x0:x0 + SCREEN_W * SCALE].reshape(SCREEN_H, SCALE, SCREEN_W, SCALE, 3)
        if strict and not (b == b[:, :1, :, :1]).all():
            raise ValueError(f"{path}: 2 × 2 放大區塊不同色(調色盤在掃描途中改變?)")
        v = b[:, 0, :, 0]
    else:
        raise ValueError(f"{path}: 尺寸 {w} × {h} 不是 {SHOT_SIZE} 或 {(SCREEN_W, SCREEN_H)}")
    return (v[..., 0] << 16) | (v[..., 1] << 8) | v[..., 2]


def scan(col: np.ndarray, gidx: dict[bytes, tuple[int, ...]]) -> list[Hit]:
    """整張畫面逐位置、逐顏色找全等的字模。

    Args:
        col: `frame()` 的結果。
        gidx: `glyph_index()` 的結果。

    Returns:
        依 (y, x, color) 排序的 Hit。
    """
    from numpy.lib.stride_tricks import sliding_window_view
    hits: list[Hit] = []
    # 加速用的必要條件:全等時窗口裡該色的點數 = 字模的 1 的個數;只打包點數對得上的位置(不改判準)
    inks = np.array(sorted({bin(int.from_bytes(k, "big")).count("1") for k in gidx}), np.int64)
    for c in np.unique(col):
        m = (col == c).astype(np.int64)
        if int(m.sum()) < int(inks[0]):
            continue
        ii = np.zeros((m.shape[0] + 1, m.shape[1] + 1), np.int64)          # 積分圖,第 0 列 / 欄是 0
        ii[1:, 1:] = m.cumsum(0).cumsum(1)
        cnt = ii[GH:, GW:] - ii[:-GH, GW:] - ii[GH:, :-GW] + ii[:-GH, :-GW]   # (H-15, W-15) 窗口點數
        ys, xs = np.nonzero(np.isin(cnt, inks))
        if not len(ys):
            continue
        win = sliding_window_view(m.astype(bool), (GH, GW))[ys, xs]       # (N, 16, 16)
        packed = np.packbits(win.reshape(len(ys), GH * GW), axis=-1)
        for k in range(len(ys)):
            gs = gidx.get(packed[k].tobytes())
            if gs:
                hits.append(Hit(int(ys[k]), int(xs[k]), int(c), gs))
    hits.sort(key=lambda h: (h.y, h.x, h.color))
    return hits


def lines(hits: list[Hit], max_blank: int = MAX_BLANK) -> list[Line]:
    """同列、同色、x 差為 16 的倍數且空白不超過 max_blank 格的字連成一行。"""
    groups: dict[tuple[int, int], list[Hit]] = {}
    for h in hits:
        groups.setdefault((h.y, h.color), []).append(h)
    out: list[Line] = []
    for (y, c), hs in groups.items():
        hs = sorted(hs, key=lambda h: h.x)
        cur: Line | None = None
        last_x = None
        for h in hs:
            if cur is not None and last_x is not None:
                d = h.x - last_x
                if d % GW == 0 and d <= GW * (max_blank + 1):     # x 已排序且同列同色不重複,d > 0
                    cur.cells.extend([None] * (d // GW - 1))
                    cur.cells.append(h.glyphs)
                    last_x = h.x
                    continue
            cur = Line(y, h.x, c, [h.glyphs])
            out.append(cur)
            last_x = h.x
    out.sort(key=lambda ln: (ln.y, ln.x, ln.color))
    return out


# ---------------------------------------------------------------- 字串
def native_lines(codes: list[int]) -> list[list[int]]:
    """FDTXT 字串切成原生行的 token 串(0xFFFE / 0xFFFD / 開框碼 + operand 是行界;0xFFFA → TOK_NUM)。"""
    out: list[list[int]] = [[]]
    i = 0
    while i < len(codes):
        c = codes[i]
        if c == STR_END:
            break
        if c in OPEN_BOX:
            out.append([])
            i += 2                      # 開框碼後面的 operand 不是字
            continue
        if c in (NEWLINE, PAGE):
            out.append([])
        elif c == NUM_CODE:
            out[-1].append(TOK_NUM)
        elif c in INSERT_CODES:
            out[-1].append(TOK_ANY)
        elif c >= 0xFF00:
            out.append([])              # 其他控制碼:當行界,不猜它的寬度
        else:
            out[-1].append(c)
        i += 1
    return [t for t in out if t]


def _match_tokens(toks: list[int], cells: list[tuple[int, ...] | None], blanks: set[int],
                  prefix: bool) -> tuple[list[int], int] | None:
    """toks 對 cells:全部對完(prefix 時 cells 可先用完)。

    Returns:
        (每個 TOK_NUM 讀到的數值, 逐字對上的格數);對不上或沒有任何逐字對上的格回 None。
        prefix 時 TOK_ANY 不可吃到行尾 —— 否則「以名稱插入開頭的句子」會是任何一行的行首。
    """
    def ok(tok: int, cell: tuple[int, ...] | None) -> bool:
        if cell is None:
            return tok in blanks
        return tok in cell

    def rec(i: int, j: int) -> tuple[list[int], int] | None:
        if j == len(cells):
            return ([], 0) if (i == len(toks) or prefix) else None
        if i == len(toks):
            return None
        t = toks[i]
        if t == TOK_NUM:
            n = 0
            while j + n < len(cells) and n < MAX_DIGITS and cells[j + n] is not None \
                    and any(g in DIGITS for g in cells[j + n]):
                n += 1
            for k in range(n, 0, -1):           # 先試最長
                r = rec(i + 1, j + k)
                if r is not None:
                    val = int("".join(str(next(g for g in cells[j + q] if g in DIGITS)) for q in range(k)))
                    return [val] + r[0], r[1]
            return None
        if t == TOK_ANY:
            top = len(cells) - j - (1 if prefix else 0)
            for k in range(top, -1, -1):
                r = rec(i + 1, j + k)
                if r is not None:
                    return r
            return None
        if not ok(t, cells[j]):
            return None
        r = rec(i + 1, j + 1)
        return None if r is None else (r[0], r[1] + 1)

    r = rec(0, 0)
    return r if r is not None and r[1] > 0 else None


def load_strings(fdtxt_dir: Path = FDTXT_DIR) -> dict[str, list[list[int]]]:
    """讀全部 FDTXT_*.bin(decode_text.parse_strings;本工具與 decode_text 同在 tools/,能 import 本工具就找得到它)。"""
    import decode_text as dt  # noqa: PLC0415
    return {p.name: dt.parse_strings(str(p)) for p in sorted(Path(fdtxt_dir).glob("FDTXT_*.bin"))}


def match_lines(scr: list[Line], strings: dict[str, list[list[int]]], blanks: set[int],
                min_prefix: int = 2) -> list[list[Match]]:
    """每個畫面行 → 全部對得上的 (檔, 字串, 原生行)。

    Args:
        scr: `lines()` 的結果。
        strings: `load_strings()` 的結果。
        blanks: `blank_glyphs()` 的結果。
        min_prefix: prefix 對應要求畫面行至少幾格(太短的行首對應沒有鑑別力)。

    Returns:
        與 scr 同長的串列,每項是該行的 Match(先 full 後 prefix)。
    """
    flat = [(fn, si, li, toks) for fn, ss in strings.items() for si, s in enumerate(ss)
            for li, toks in enumerate(native_lines(s))]
    out: list[list[Match]] = []
    for ln in scr:
        full, pre = [], []
        for fn, si, li, toks in flat:
            r = _match_tokens(toks, ln.cells, blanks, prefix=False)
            if r is not None:
                full.append(Match(fn, si, li, "full", *r))
                continue
            if len(ln.cells) >= min_prefix:
                r = _match_tokens(toks, ln.cells, blanks, prefix=True)
                if r is not None:
                    pre.append(Match(fn, si, li, "prefix", *r))
        out.append(full + pre)
    return out


@dataclass
class Box:
    """連續幾個畫面行對到同一字串的連續原生行。

    Attributes:
        file: FDTXT 檔名。
        string: 字串序號。
        rows: 畫面行在 `lines()` 結果裡的序號。
        first_line: 第一個畫面行對到的原生行。
        complete: 字串的每個原生行都對上了(第一行到最後一行、最後一行是 full)。
        numbers: 各行的數值依序合併。
    """

    file: str
    string: int
    rows: list[int]
    first_line: int
    complete: bool
    numbers: list[int]


def match_boxes(scr: list[Line], per_line: list[list[Match]], strings: dict[str, list[list[int]]],
                max_pitch: int = 2 * GH) -> list[Box]:
    """把逐行的對應連成「框」:同 x、同色、y 遞增且相鄰(中間沒有別的同 x 同色行、間距 ≤ max_pitch)的畫面行,
    對到同一字串的連續原生行。單獨一行也是一個框(rows 長 1);同一行可在不同字串的框裡,全部列出。

    只有最後一個畫面行可以是 prefix(打字機效果);中間的行必須 full。
    """
    order: dict[tuple[int, int], list[int]] = {}
    for i, ln in enumerate(scr):
        order.setdefault((ln.x, ln.color), []).append(i)
    nxt: dict[int, int] = {}
    for idxs in order.values():
        idxs.sort(key=lambda i: scr[i].y)
        for a, b in zip(idxs, idxs[1:]):
            if scr[b].y - scr[a].y <= max_pitch:       # 已依 y 排序,同 x 同色的行 y 不重複
                nxt[a] = b
    prv = {b: a for a, b in nxt.items()}
    nlines = {(fn, si): len(native_lines(s)) for fn, ss in strings.items() for si, s in enumerate(ss)}
    boxes: list[Box] = []
    for start, mm in enumerate(per_line):
        for m in mm:
            key = (m.file, m.string)
            # 框的起點:上一行沒有對到同字串的上一個原生行(否則它是別人框的中段)
            p = prv.get(start)
            if p is not None and any((q.file, q.string) == key and q.line == m.line - 1 and q.kind == "full"
                                     for q in per_line[p]):
                continue
            rows, nums, cur, li, kind = [start], list(m.numbers), start, m.line, m.kind
            while kind == "full" and cur in nxt:
                n = nxt[cur]
                hit = next((q for q in per_line[n] if (q.file, q.string) == key and q.line == li + 1), None)
                if hit is None:
                    break
                rows.append(n)
                nums += hit.numbers
                cur, li, kind = n, li + 1, hit.kind
            complete = m.line == 0 and li == nlines[key] - 1 and kind == "full"
            boxes.append(Box(m.file, m.string, rows, m.line, complete, nums))
    return boxes


def text_of(ln: Line, gmap: dict[str, str]) -> str:
    """畫面行的文字(glyph_map.json);空白格為全形空白,同點陣多字以 [a|b] 表示。"""
    parts = []
    for cell in ln.cells:
        if cell is None:
            parts.append("　")
            continue
        chs = sorted({gmap.get(str(g), f"<{g:#x}>") for g in cell})
        parts.append(chs[0] if len(chs) == 1 else "[" + "|".join(chs) + "]")
    return "".join(parts)


def read_shot(path: Path | str, font: bytes, strings: dict[str, list[list[int]]], gmap: dict[str, str],
              strict: bool = True) -> dict:
    """一張截圖的完整判讀結果(可直接寫成 JSON)。frame() 拒絕時回 {"readable": False, "error": ...}。"""
    try:
        col = frame(path, strict=strict)
    except ValueError as e:
        return {"shot": str(path), "readable": False, "error": str(e)}
    hits = scan(col, glyph_index(font))
    scr = lines(hits)
    ms = match_lines(scr, strings, blank_glyphs(font))
    return {"shot": str(path), "readable": True, "hits": len(hits),
            "lines": [{"y": ln.y, "x": ln.x, "color": f"{ln.color:#08x}", "text": text_of(ln, gmap),
                       "glyphs": [None if c is None else [hex(g) for g in c] for c in ln.cells],
                       "matches": [{"file": m.file, "string": m.string, "string_hex": hex(m.string), "line": m.line,
                                    "kind": m.kind, "numbers": m.numbers, "literal": m.literal} for m in mm]}
                      for ln, mm in zip(scr, ms)],
            "boxes": [{"file": b.file, "string": b.string, "string_hex": hex(b.string), "rows": b.rows,
                       "first_line": b.first_line, "complete": b.complete, "numbers": b.numbers}
                      for b in match_boxes(scr, ms, strings)]}


# ---------------------------------------------------------------- 合成(selftest 與預測用)
def render_line(canvas: np.ndarray, font: bytes, glyphs: list[int], x: int, y: int, color: int) -> None:
    """把字模串畫到 canvas(只畫字模的 1,背景不動)。"""
    for q, g in enumerate(glyphs):
        bits = np.unpackbits(np.frombuffer(font[g * GB:(g + 1) * GB], np.uint8)).reshape(GH, GW).astype(bool)
        blk = canvas[y:y + GH, x + q * GW:x + (q + 1) * GW]
        blk[bits] = color


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """手算點陣與合成畫面驗判準、分行、字串對應;有字型時再用真字型驗。"""
    fails: list[str] = []

    def check(name: str, cond: bool, detail: object = "") -> None:
        print(f"  {'PASS' if cond else 'FAIL'}: {name}{'' if cond else f'  {detail}'}")
        if not cond:
            fails.append(name)

    # 手算字型:g0 全空白、g1 = 左上 4 × 4 方塊、g2 = 第 0 列整列 + 第 15 列整列、g3 = 數字 '5'(假設)
    def mk(rows: dict[int, int]) -> bytes:
        return b"".join(rows.get(r, 0).to_bytes(2, "big") for r in range(GH))
    g1 = mk({0: 0xF000, 1: 0xF000, 2: 0xF000, 3: 0xF000})
    g2 = mk({0: 0xFFFF, 15: 0xFFFF})
    font = bytes(GB) + g1 + g2
    gidx = glyph_index(font)

    print("(1) 位元順序:每列 2 bytes 高位在左;全空白字模不收")
    check("g1 在索引裡", gidx.get(g1) == (1,), gidx.get(g1))
    check("空白字模不收", bytes(GB) not in gidx)
    check("blank_glyphs = {0}", blank_glyphs(font) == {0}, blank_glyphs(font))
    rng = np.random.default_rng(7)
    bg = rng.integers(0x100, 0x200, size=(40, 80)).astype(np.int64)   # 背景色都不是 0xAA0000
    can = bg.copy()
    render_line(can, font, [1], 5, 3, 0xAA0000)
    h = scan(can, gidx)
    check("g1 畫在 (x=5, y=3) → 只有一個 hit 在 (3, 5)", [(x.y, x.x, x.glyphs) for x in h] == [(3, 5, (1,))],
          [(x.y, x.x, x.color, x.glyphs) for x in h])
    # 手算:左上 4 × 4 方塊 → 位置 (3..6, 5..8) 是 0xAA0000
    check("render_line 手算點陣", bool((can[3:7, 5:9] == 0xAA0000).all()) and int((can == 0xAA0000).sum()) == 16)

    def brute(col: np.ndarray) -> list[tuple[int, int, int, tuple[int, ...]]]:
        """不用點數預篩的逐位置參考實作(對照 scan 的加速是否改變結果)。"""
        out = []
        for y in range(col.shape[0] - GH + 1):
            for x in range(col.shape[1] - GW + 1):
                blk = col[y:y + GH, x:x + GW]
                for c in np.unique(blk):
                    gs = gidx.get(np.packbits((blk == c).reshape(-1)).tobytes())
                    if gs:
                        out.append((y, x, int(c), gs))
        return sorted(out)
    cn = bg[:34, :50].copy()                 # 四角都放字(含最右下可放的位置)
    render_line(cn, font, [2], 0, 0, 0xAA0000)
    render_line(cn, font, [1], 34, 0, 0xBB0000)
    render_line(cn, font, [1], 0, 18, 0xBB0000)
    render_line(cn, font, [2], 34, 18, 0xCC0000)
    got = sorted((x.y, x.x, x.color, x.glyphs) for x in scan(cn, gidx))
    check("scan = 逐位置參考實作(四角)", got == brute(cn) and len(got) == 4, (got, brute(cn)))
    one = np.full((40, 40), 0xAA0000, np.int64)          # 單色:點數夠多,不會被最少點數那條先跳過
    check("畫面不到 16 列 / 16 欄 → 沒有 hit、不出錯",
          scan(one[:15, :], gidx) == [] and scan(one[:, :15], gidx) == [])
    c16 = bg[:16, :16].copy()
    render_line(c16, font, [1], 0, 0, 0xAA0000)
    check("剛好 16 × 16 → 一個 hit", [(x.y, x.x) for x in scan(c16, gidx)] == [(0, 0)])

    print("(2) 判準:字模的 0 出現同色就不算;字模的 1 有一點不同色就不算")
    c2 = can.copy()
    c2[3, 9] = 0xAA0000                      # 方塊右邊多一點同色(在窗口內、字模為 0)
    check("0 的位置有同色 → 原位置不算", not any((x.y, x.x) == (3, 5) for x in scan(c2, gidx)))
    c3 = can.copy()
    c3[6, 8] = 0xAB0000                      # 方塊一點改色
    check("1 的位置有一點不同色 → 不算", not any(x.glyphs == (1,) and (x.y, x.x) == (3, 5) for x in scan(c3, gidx)))
    c4 = bg.copy()
    render_line(c4, font, [1], 6, 3, 0xAA0000)
    check("右移一格 → hit 也右移一格", [(x.y, x.x) for x in scan(c4, gidx)] == [(3, 6)])

    print("(3) 分行:同列同色、間距 16 的倍數、空白 ≤ MAX_BLANK 格")
    hs = [Hit(10, 0, 1, (1,)), Hit(10, 16, 1, (2,)), Hit(10, 48, 1, (1,)), Hit(10, 112, 1, (2,)),
          Hit(10, 128, 2, (1,)), Hit(29, 0, 1, (1,)), Hit(10, 145, 1, (1,))]
    ls = lines(hs)
    got = [(ln.y, ln.x, ln.color, ln.cells) for ln in ls]
    want = [(10, 0, 1, [(1,), (2,), None, (1,)]), (10, 112, 1, [(2,)]), (10, 128, 2, [(1,)]), (10, 145, 1, [(1,)]),
            (29, 0, 1, [(1,)])]
    # 48 → 112 差 64 = 3 個空白 > MAX_BLANK → 切開;128 換色 → 另一行;145 不是 16 的倍數 → 另一行
    check("分行結果", got == want, got)
    check("空白 2 格仍同一行", len(lines([Hit(0, 0, 1, (1,)), Hit(0, 48, 1, (1,))])) == 1)
    check("空白 3 格切開", len(lines([Hit(0, 0, 1, (1,)), Hit(0, 64, 1, (1,))])) == 2)

    print("(4) 字串原生行與對應:0xFFFE 換行、0xFFFA 數字、開框碼 + operand")
    nl = native_lines([7, 8, NEWLINE, 7, NUM_CODE, 9, STR_END, 7])
    check("native_lines 切行、數字 token、結束碼", nl == [[7, 8], [7, TOK_NUM, 9]], nl)
    check("開框碼的 operand 不是字", native_lines([0xFFEF, 7, 558, 8]) == [[558, 8]],
          native_lines([0xFFEF, 7, 558, 8]))
    check("翻頁是行界", native_lines([1, PAGE, 2]) == [[1], [2]])
    check("未知控制碼(0xFF00)也是行界", native_lines([1, 0xFF00, 2]) == [[1], [2]], native_lines([1, 0xFF00, 2]))
    cells = [(7,), (5,), (0,), (0,), (0,), (9,)]
    check("數字 5000 讀出、逐字 2 格", _match_tokens([7, TOK_NUM, 9], cells, set(), False) == ([5000], 2),
          _match_tokens([7, TOK_NUM, 9], cells, set(), False))
    check("結尾字不同 → 對不上", _match_tokens([7, TOK_NUM, 8], cells, set(), False) is None)
    check("沒有數字 → TOK_NUM 對不上", _match_tokens([7, TOK_NUM, 9], [(7,), (9,)], set(), False) is None)
    check("畫面較短:full 不算、prefix 算", _match_tokens([7, 8, 9], [(7,), (8,)], set(), False) is None
          and _match_tokens([7, 8, 9], [(7,), (8,)], set(), True) == ([], 2))
    check("畫面較長:prefix 也不算", _match_tokens([7, 8], [(7,), (8,), (9,)], set(), True) is None)
    check("空白格只對空白字模", _match_tokens([7, 0, 9], [(7,), None, (9,)], {0}, False) == ([], 3)
          and _match_tokens([7, 3, 9], [(7,), None, (9,)], {0}, False) is None)
    check("任意插入可對 0 或多格", _match_tokens([7, TOK_ANY, 9], [(7,), (9,)], set(), False) == ([], 2)
          and _match_tokens([7, TOK_ANY, 9], [(7,), (1,), (2,), (9,)], set(), False) == ([], 2))
    check("prefix:任意插入不可吃到行尾(開頭是插入的句子不是任何行的行首)",
          _match_tokens([TOK_ANY, 9, 9], [(1,), (2,)], set(), True) is None
          and _match_tokens([TOK_ANY, 9, 8], [(1,), (9,)], set(), True) == ([], 1))
    check("沒有任何逐字對上的格 → 不算", _match_tokens([TOK_ANY], [(1,), (2,)], set(), False) is None)
    check("一位數", _match_tokens([7, TOK_NUM, 9], [(7,), (5,), (9,)], set(), False) == ([5], 2))
    check("數字位置不是數字 → 對不上", _match_tokens([7, TOK_NUM, 9], [(7,), (12,), (9,)], set(), False) is None)   # glyph 12 不是數字
    check("full:任意插入可吃到行尾", _match_tokens([7, TOK_ANY], [(7,), (1,)], set(), False) == ([], 1))
    check("任意插入吃剛好 1 格", _match_tokens([7, TOK_ANY, 9], [(7,), (1,), (9,)], set(), False) == ([], 2))
    check("任意插入不會往回吃(同一格不能用兩次)",
          _match_tokens([7, TOK_ANY, 7, 8], [(7,), (8,)], set(), False) is None)
    ml = match_lines([Line(0, 0, 1, [(7,), (8,)]), Line(19, 0, 1, [(7,)])], {"P.bin": [[7, 8, 9]]}, set())
    check("match_lines:prefix 列出;不到 min_prefix 格的行不算 prefix",
          [[(m.kind, m.literal) for m in mm] for mm in ml] == [[("prefix", 2)], []], ml)
    # 框:T0 = [A] / [C]、T1 = [Z] / [B];畫面 A(y 0)、B(y 19)。A 只屬 T0 第 0 行、B 只屬 T1 第 1 行 → 兩個單行框、都不完整
    A_, B_, C_, Z_ = 11, 12, 13, 14
    tstr = {"T.bin": [[A_, NEWLINE, C_], [Z_, NEWLINE, B_]]}
    sl = [Line(0, 0, 1, [(A_,)]), Line(19, 0, 1, [(B_,)])]
    bxs = [(b.string, b.rows, b.first_line, b.complete) for b in match_boxes(sl, match_lines(sl, tstr, set()), tstr)]
    check("框:不同字串的下一行不能接上;下一行屬別的字串時自己仍是框的起點",
          bxs == [(0, [0], 0, False), (1, [1], 1, False)], bxs)
    tstr2 = {"T.bin": [[A_, NEWLINE, B_]]}
    bxs2 = [(b.rows, b.complete) for b in match_boxes(sl, match_lines(sl, tstr2, set()), tstr2)]
    check("框:同一字串連續兩行 → 一個完整框,第二行不另起一框", bxs2 == [([0, 1], True)], bxs2)
    sl3 = [Line(0, 0, 1, [(A_,)]), Line(19, 0, 1, [(A_,)]), Line(38, 0, 1, [(B_,)])]
    bxs3 = [(b.rows, b.first_line, b.complete) for b in match_boxes(sl3, match_lines(sl3, tstr2, set()), tstr2)]
    check("框:第一行重複時,第二個 A 開始的才完整;第一個 A 單獨一框", bxs3 == [([0], 0, False), ([1, 2], 0, True)], bxs3)
    sl4 = [Line(0, 0, 1, [(A_,)]), Line(19 + 2 * GH, 0, 1, [(B_,)])]
    check("框:行距超過 max_pitch 不接", not any(b.complete for b in match_boxes(sl4, match_lines(sl4, tstr2, set()), tstr2)))
    ms = match_lines([Line(0, 0, 1, cells)], {"T.bin": [[1, NEWLINE, 7, NUM_CODE, 9], [7, 5, 0, 0, 0, 9]]}, set())
    got = [(m.string, m.line, m.kind, m.numbers) for m in ms[0]]
    check("match_lines 列出全部候選(數字插入與字面數字都對得上)", got == [(0, 1, "full", [5000]), (1, 0, "full", [])], got)

    print("(5) frame():2 倍放大還原;放大區塊不一致時 strict 拒絕")
    import tempfile
    from PIL import Image
    small = (np.arange(SCREEN_W * SCREEN_H, dtype=np.int64).reshape(SCREEN_H, SCREEN_W) * 2654435761) & 0xFFFFFF
    big = np.zeros((SHOT_SIZE[1], SHOT_SIZE[0], 3), np.uint8)
    rgb = np.stack([(small >> 16) & 255, (small >> 8) & 255, small & 255], -1).astype(np.uint8)
    x0, y0 = ORIGIN
    big[y0:y0 + 400, x0:x0 + 640] = rgb.repeat(2, 0).repeat(2, 1)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.png"
        Image.fromarray(big).save(p)
        check("還原等於原圖", bool((frame(p) == small).all()))
        big2 = big.copy()
        big2[y0 + 1, x0] ^= 1                # 一個區塊的左下點改色
        Image.fromarray(big2).save(p)
        try:
            frame(p)
            check("strict 拒絕不一致的區塊", False, "沒有 raise")
        except ValueError:
            check("strict 拒絕不一致的區塊", True)
        big3 = big.copy()
        for dy, dx in ((0, 1), (1, 0), (1, 1)):   # 區塊 (0, 0) 除了左上以外三點都改色
            big3[y0 + dy, x0 + dx] ^= 1
        # 調色盤在掃描途中改變時是整條掃描線(放大後的一整列)不同:只比橫向或只比縱向都會漏掉一種
        for nm, pts in (("下半列", ((1, 0), (1, 1))), ("右半欄", ((0, 1), (1, 1)))):
            b4 = big.copy()
            for dy, dx in pts:
                b4[y0 + dy, x0 + dx] ^= 1
            Image.fromarray(b4).save(p)
            try:
                frame(p)
                check(f"strict 拒絕區塊{nm}不同色", False, "沒有 raise")
            except ValueError:
                check(f"strict 拒絕區塊{nm}不同色", True)
        Image.fromarray(big3).save(p)
        check("non-strict 取每區塊左上那點", bool((frame(p, strict=False) == small).all()))
        Image.fromarray(big[:700]).save(p)
        try:
            frame(p)
            check("尺寸不對就拒絕", False, "沒有 raise")
        except ValueError:
            check("尺寸不對就拒絕", True)

    print("(6) 真字型(有 extracted/raw 時):合成 FDTXT_000 0x1aa「打開寶箱,/ 發現 5000 元!」再讀回")
    if FONT_PATH.exists() and FDTXT_DIR.exists():
        rf = load_font()
        strs = load_strings()
        s = strs["FDTXT_000.bin"][0x1AA]
        nls = native_lines(s)
        check("0x1aa 兩個原生行、第二行有數字插入", len(nls) == 2 and TOK_NUM in nls[1], nls)
        can = np.full((SCREEN_H, SCREEN_W), 0x204080, np.int64)
        l2 = [g for t in nls[1] for g in ([5, 0, 0, 0] if t == TOK_NUM else [t])]
        render_line(can, rf, nls[0], 99, 146, 0x698ACB)
        render_line(can, rf, l2, 99, 165, 0x698ACB)
        rb = blank_glyphs(rf)
        scr = lines(scan(can, glyph_index(rf)))
        check("讀回兩行、位置正確", [(ln.y, ln.x, len(ln.cells)) for ln in scr] == [(146, 99, len(nls[0])), (165, 99, len(l2))],
              [(ln.y, ln.x, len(ln.cells)) for ln in scr])
        ms = match_lines(scr, strs, rb)
        got = [[(m.file, hex(m.string), m.line, m.kind, m.numbers) for m in mm if m.kind == "full"] for mm in ms]
        # 第二行「發現 N 元!」可見 / 隱藏兩句共用;分得開的是第一行(打開寶箱 / 挖掘寶藏)
        check("逐行:第一行只有 0x1aa,第二行 0x1aa 與 0x1ae 都對上(數字 5000)",
              got == [[("FDTXT_000.bin", "0x1aa", 0, "full", [])],
                      [("FDTXT_000.bin", "0x1aa", 1, "full", [5000]), ("FDTXT_000.bin", "0x1ae", 1, "full", [5000])]], got)
        bx = [(b.file, hex(b.string), b.rows, b.complete, b.numbers) for b in match_boxes(scr, ms, strs)]
        check("框:完整對上的只有 0x1aa(兩行、5000);0x1ae 只有第二行單獨一框、不完整;第二行不另起 0x1aa 的框",
              [b for b in bx if b[3]] == [("FDTXT_000.bin", "0x1aa", [0, 1], True, [5000])]
              and ("FDTXT_000.bin", "0x1ae", [1], False, [5000]) in bx
              and sum(b[1] == "0x1aa" for b in bx) == 1, bx)
        hid = native_lines(strs["FDTXT_000.bin"][0x1AE])
        can3 = np.full((SCREEN_H, SCREEN_W), 0x204080, np.int64)
        render_line(can3, rf, hid[0], 99, 146, 0x698ACB)
        render_line(can3, rf, l2, 99, 165, 0x698ACB)
        scr3 = lines(scan(can3, glyph_index(rf)))
        bx3 = [(hex(b.string), b.complete) for b in match_boxes(scr3, match_lines(scr3, strs, rb), strs) if b.complete]
        check("對照:第一行換成「挖掘寶藏,」→ 完整的框變成 0x1ae", bx3 == [("0x1ae", True)], bx3)
        can4 = np.full((SCREEN_H, SCREEN_W), 0x204080, np.int64)
        render_line(can4, rf, nls[0], 99, 146, 0x698ACB)
        render_line(can4, rf, l2, 115, 165, 0x698ACB)       # 第二行錯開 16 → 不同欄,不是同一框
        scr4 = lines(scan(can4, glyph_index(rf)))
        check("對照:第二行不同 x → 沒有完整的框",
              not any(b.complete for b in match_boxes(scr4, match_lines(scr4, strs, rb), strs)))
        can2 = np.full((SCREEN_H, SCREEN_W), 0x204080, np.int64)
        render_line(can2, rf, [l2[0], l2[1], 6, 0, 0, 0, l2[-2], l2[-1]], 99, 165, 0x698ACB)
        ms2 = match_lines(lines(scan(can2, glyph_index(rf))), strs, rb)
        check("對照:金額換成 6000 → 讀到 6000", any(m.numbers == [6000] for m in ms2[0]), ms2)
    else:
        print("  SKIP: 沒有 extracted/raw(字型或 FDTXT),真字型題不跑")

    print(f"\n{'ALL PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="從 DOSBox-X 截圖以字模全等比對判讀畫面文字,並對到 FDTXT 字串。")
    ap.add_argument("shots", nargs="*", type=Path, help="截圖(1024 × 768 或 320 × 200)")
    ap.add_argument("--json", type=Path, help="結果寫成 JSON(既有檔必須是 JSON)")
    ap.add_argument("--no-strict", action="store_true", help="2 × 2 放大區塊不一致時仍取左上那點")
    ap.add_argument("--selftest", action="store_true", help="執行自我測試")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.shots:
        ap.print_help()
        return 2
    font, strings = load_font(), load_strings()
    gmap = json.loads(GLYPH_MAP_PATH.read_text(encoding="utf-8"))
    res = [read_shot(p, font, strings, gmap, strict=not a.no_strict) for p in a.shots]
    for r in res:
        print(f"== {r['shot']}")
        if not r["readable"]:
            print(f"  讀不了:{r['error']}")
            continue
        print(f"  hits={r['hits']} lines={len(r['lines'])}")
        for ln in r["lines"]:
            ms = "; ".join(f"{m['file']}#{m['string_hex']}.{m['line']} {m['kind']}"
                           + (f" numbers={m['numbers']}" if m["numbers"] else "") for m in ln["matches"])
            print(f"  ({ln['x']:3d},{ln['y']:3d}) {ln['color']} {ln['text']}  -> {ms or '(無對應)'}")
        for bx in r["boxes"]:
            if bx["complete"]:
                print(f"  完整框:{bx['file']}#{bx['string_hex']} 行 {bx['rows']}"
                      + (f" numbers={bx['numbers']}" if bx["numbers"] else ""))
    if a.json:
        import safe_output  # noqa: PLC0415
        out = safe_output.guard_json_output(a.json)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0 if all(r["readable"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
