#!/usr/bin/env python3
"""炎龍騎士團2 — 劇情 / 對話渲染器(把 FDTXT 章節畫成可讀 PNG)。

文本結構(第 3 輪解出):每個 FDTXT 資源 = 一章。資源內每個字串可含多段對白,
段落格式:[對話控制碼 0xFFxx][說話者肖像 ID][『][對白 glyph...][』]。

本工具**只畫字模,不畫說話者名字**——這是刻意的,且與原版一致:控制碼
0xFFEC..0xFFEF 後接的說話者 id operand,原版渲染器 `0x15F84` 是當成二進位
參數消耗、從不畫出(doc40)。要帶說話者的可讀輸出請用 `decode_story_text.py`
(它有完整的 glyph→UTF-8 表與說話者歸屬)。

2026-09-09:本檔原本有一份 32 筆的 `PORTRAIT` 肖像 ID→角色名表,**定義後從未
被任何程式碼引用**,而 docstring 把「說話者肖像 ID → 角色名」寫成本工具的功能。
兩者都已移除/改正:名表與 `docs/data/exe_tables/characters.json` 逐筆相同,是重複
的死碼(諷刺的是它比當時 `char_summary.py` 真正在用的那份還齊全,見 91-worklist 584)。

- 控制碼 0xFFxx:視為換行(段落分隔)。
- 0xFFEC..0xFFEF 後接一個 operand word(說話者 id)**必須跳過**;早期漏跳會讓
  id 洩漏成字模、被誤認成「說話者字母代號」(decode_story_text.py 檔頭記載的
  2026-08-30 修正就是同一件事的另一半)。
- glyph 索引 < 0x720(= 1824,字型 FDOTHER 資源 #4 的實際字模數)用自製字型渲染;
  實測全部 34 個 FDTXT 共 52605 個字模索引沒有一個越界。

輸出 = 分頁 PNG(本機對照用;劇本屬遊戲著作權,不入版控)。

用法:
    python3 render_story.py <FDTXT_NNN.bin> <FDOTHER_004.bin> <out前綴>
    python3 render_story.py --all <raw/FDTXT目錄> <FDOTHER_004.bin> <out目錄>
    python3 render_story.py --selftest
"""
import sys
import os
import glob
import struct
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from decode_text import parse_strings, load_font, render_glyph

CELL = 18
COLS = 28
LINES_PER_PAGE = 42
TR = 0  # 背景

CONTROL_MIN = 0xFF00
SPEAKER_LO, SPEAKER_HI = 0xFFEC, 0xFFEF   # 這四個後面跟一個 operand word


def lay_out(strings, skip_speaker_operand=True):
    """把整章拆成 render rows。每 row = list of ('g',code) glyph;'sep' 為段間距。

    `skip_speaker_operand=False` 只給 selftest 用來重現 2026-08-30 修好的
    「說話者 id 洩漏成字模」那個 bug,正常路徑永遠是 True。
    """
    rows = []
    for s in strings:
        line = []
        n = len(s)
        i = 0
        while i < n:
            c = s[i]
            if c >= CONTROL_MIN:        # 對話控制碼 → 換行
                if line:
                    rows.append(line); line = []
                if skip_speaker_operand and SPEAKER_LO <= c <= SPEAKER_HI and i + 1 < n:
                    i += 1
            else:
                line.append(c)
                if len(line) >= COLS:
                    rows.append(line); line = []
            i += 1
        if line:
            rows.append(line)
        rows.append("sep")
    return rows


def paginate(rows):
    pages = []
    buf = []
    cnt = 0
    for r in rows:
        buf.append(r)
        if r != "sep":
            cnt += 1
        if cnt >= LINES_PER_PAGE and r == "sep":
            pages.append(buf); buf = []; cnt = 0
    if buf:
        pages.append(buf)
    return pages


def render_chapter(txt_path, font, out_prefix):
    strings = parse_strings(txt_path)
    pages = paginate(lay_out(strings))
    for pi, pg in enumerate(pages):
        h = sum(CELL if r != "sep" else 6 for r in pg) + 8
        im = Image.new("L", (COLS * CELL + 12, h), 18)
        y = 4
        for r in pg:
            if r == "sep":
                y += 6; continue
            x = 4
            for c in r:
                im.paste(render_glyph(font, c), (x, y)); x += CELL
            y += CELL
        im.save(f"{out_prefix}_p{pi}.png")
    return len(pages), len(strings)


def main(argv):
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 4:
        print(__doc__); return 1
    if argv[1] == "--all":
        src, fontp, outdir = argv[2], argv[3], argv[4]
        font, _ = load_font(fontp)
        os.makedirs(outdir, exist_ok=True)
        for f in sorted(glob.glob(os.path.join(src, "*.bin"))):
            base = os.path.splitext(os.path.basename(f))[0]
            np_, ns = render_chapter(f, font, os.path.join(outdir, base))
            print(f"{base}: {ns} 字串 -> {np_} 頁")
        return 0
    font, _ = load_font(argv[2])
    np_, ns = render_chapter(argv[1], font, argv[3])
    print(f"{ns} 字串 -> {np_} 頁")
    return 0


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FDTXT_DIR = os.path.join(REPO, "extracted", "raw", "FDTXT")
FONT_RES = os.path.join(REPO, "extracted", "raw", "FDOTHER", "FDOTHER_004.bin")

# 2026-08-30 修正前的症狀:FDTXT_032 會多出 40 個字模,值就是說話者 id 直方圖。
# 40 同時也是該資源已記錄的 utterance 數(export_story_index_map 的回歸值)。
LEAK_032_COUNT = 40
LEAK_032_HIST = {0: 17, 1: 12, 3: 3, 4: 8}
GLYPH_TOTAL = 52605          # 全部 34 個 FDTXT 的字模數(不含控制碼)
FONT_GLYPHS = 0x720          # = 1824,FDOTHER #4 的實際字模數


def _glyphs(rows):
    return [c for r in rows if r != "sep" for c in r]


def selftest() -> int:
    import collections
    fails = []
    if not os.path.isdir(FDTXT_DIR):
        print(f"缺少 {FDTXT_DIR},無法自我驗證", file=sys.stderr)
        return 1
    ss032 = parse_strings(os.path.join(FDTXT_DIR, "FDTXT_032.bin"))

    print("(1) 歷史 bug 回歸:不跳 operand 必須精確重現當初的洩漏量與值分布")
    good = _glyphs(lay_out(ss032, skip_speaker_operand=True))
    bad = _glyphs(lay_out(ss032, skip_speaker_operand=False))
    leaked = collections.Counter(bad) - collections.Counter(good)
    ok1 = (len(bad) - len(good) == LEAK_032_COUNT and dict(leaked) == LEAK_032_HIST)
    print(f"    {'PASS' if ok1 else 'FAIL'}: 洩漏 {len(bad)-len(good)} 個"
          f"(應 {LEAK_032_COUNT}),值分布 {dict(sorted(leaked.items()))}")
    if not ok1:
        fails.append(f"洩漏回歸不符:{len(bad)-len(good)} / {dict(leaked)}")

    print("\n(2) 跨工具判準交叉驗證:operand 數 vs count_logical_utterances")
    from export_story_index_map import count_logical_utterances
    def band(s):
        n = 0; i = 0
        while i < len(s):
            if SPEAKER_LO <= s[i] <= SPEAKER_HI and i + 1 < len(s):
                n += 1; i += 1
            i += 1
        return n
    same, differ = 0, {}
    for f in sorted(glob.glob(os.path.join(FDTXT_DIR, "*.bin"))):
        ss = parse_strings(f)
        b = sum(band(s) for s in ss)
        u = sum(count_logical_utterances(s) for s in ss)
        if b == u and b > 0:
            same += 1
        elif b != u:
            differ[os.path.basename(f)] = (b, u)
    # 026 的差額必須恰好等於「有 utterance 但沒有說話者 operand」的字串數
    ss026 = parse_strings(os.path.join(FDTXT_DIR, "FDTXT_026.bin"))
    unq = [i for i, s in enumerate(ss026)
           if count_logical_utterances(s) > 0 and band(s) == 0]
    d026 = differ.get("FDTXT_026.bin", (0, 0))
    ok2 = (same == 29 and len(differ) == 5
           and d026[1] - d026[0] == len(unq) == 2 and unq == [2, 3])
    print(f"    {'PASS' if ok2 else 'FAIL'}: 34 檔中 {same} 個完全相同、"
          f"{len(differ)} 個不同;026 差 {d026[1]-d026[0]},無引號字串 {unq}")
    if not ok2:
        fails.append(f"跨工具判準不符:same={same} differ={differ} unq={unq}")

    print("\n(3) 字型邊界:所有字模索引必須 < 0x720,且越界索引不得崩潰")
    font, nglyph = load_font(FONT_RES)
    tot = 0; over = 0
    for f in sorted(glob.glob(os.path.join(FDTXT_DIR, "*.bin"))):
        for s in parse_strings(f):
            for c in s:
                if c < CONTROL_MIN:
                    tot += 1
                    if c >= FONT_GLYPHS:
                        over += 1
    blank = render_glyph(font, nglyph + 5)
    ok3 = (nglyph == FONT_GLYPHS and tot == GLYPH_TOTAL and over == 0
           and blank.size == (16, 16) and not blank.getbbox())
    print(f"    {'PASS' if ok3 else 'FAIL'}: 字模數 {nglyph}(= 0x720)、"
          f"共 {tot} 個索引、越界 {over} 個、越界渲染回空圖 {not blank.getbbox()}")
    if not ok3:
        fails.append(f"字型邊界不符:{nglyph}/{tot}/{over}")

    print("\n(4) 折行:第 COLS+1 個字模必須落到下一 row(手算)")
    rows = lay_out([[7] * (COLS + 1) + [0xFFFF]])
    ok4 = (len([r for r in rows if r != "sep"]) == 2
           and len(rows[0]) == COLS and len(rows[1]) == 1)
    print(f"    {'PASS' if ok4 else 'FAIL'}: {COLS+1} 個字模 -> "
          f"{[len(r) for r in rows if r != 'sep']}")
    if not ok4:
        fails.append(f"折行不符:{[len(r) for r in rows if r != 'sep']}")

    print("\n(5) 非平凡性 + 負向控制")
    counts = {}
    for res in ("026", "032", "033"):
        counts[res] = len([r for r in
                           lay_out(parse_strings(os.path.join(FDTXT_DIR, f"FDTXT_{res}.bin")))
                           if r != "sep"])
    empty = _glyphs(lay_out([[], [0xFFFE, 0xFFFF]]))
    ok5 = len(set(counts.values())) == 3 and all(v > 0 for v in counts.values()) and empty == []
    print(f"    {'PASS' if ok5 else 'FAIL'}: 三章 row 數 {counts} 互異、"
          f"純控制碼字串產生 {len(empty)} 個字模")
    if not ok5:
        fails.append(f"非平凡性/負向控制不符:{counts} / {empty}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(歷史 bug 回歸 + 跨工具判準交叉驗證 + 字型邊界 "
          "+ 折行手算 + 非平凡性與負向控制)。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
