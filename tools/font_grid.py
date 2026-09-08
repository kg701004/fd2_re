#!/usr/bin/env python3
"""炎龍騎士團2 — 字模網格渲染(供建立 glyph→Unicode 對照表)。

把自製字型(FDOTHER 資源 #4,1824 個 16×16 字模)分批渲染成帶索引標籤的大網格,
方便人工 / 多模態逐格判讀,建立 glyph 索引 → Unicode 對照表。

用法:
    python3 font_grid.py <FDOTHER_004.bin> <start> <count> <out.png> [scale] [cols]
"""
import sys
from PIL import Image, ImageDraw

GW = GH = 16
GB = 32


def render_glyph(font, idx, scale):
    g = font[idx * GB: idx * GB + GB]
    im = Image.new("L", (GW, GH), 0)
    if len(g) >= GB:
        px = im.load()
        for r in range(GH):
            bits = (g[r * 2] << 8) | g[r * 2 + 1]
            for c in range(GW):
                if bits & (0x8000 >> c):
                    px[c, r] = 255
    return im.resize((GW * scale, GH * scale), Image.NEAREST)


def selftest():
    """位元解包 + 兩個已記錄結論的回歸。

    `render_glyph` 的核心是把每列 2 bytes 當成 16 個位元、高位在左展開。這種
    位元順序錯了不會崩,只會讓整張字模左右翻轉或錯位 —— 而字模是拿來人工判讀
    建 glyph→Unicode 對照表的,錯了會一路錯進對照表。所以第 (1) 題用**手算的
    點陣**驗,不是只看「畫得出東西」。

    第 (3) 題釘住一個已記錄的 RE 結論:遊戲自己的資料裡有**兩個字**——
    glyph 64(名稱表寫的「塞」)與 glyph 904(對白裡的「賽」)——它們的點陣
    在 32 bytes 中有 25 bytes 不同,所以 glyph_map 沒有錯,是原版真的用了兩個字。
    """
    import os
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) 位元順序:每列 2 bytes、高位在左,用手算點陣驗")
    # 第 0 列 = 0x8001 -> 最左與最右各一點;第 1 列 = 0x0180 -> 中間兩點
    font = bytearray(32)
    font[0], font[1] = 0x80, 0x01
    font[2], font[3] = 0x01, 0x80
    im = render_glyph(bytes(font), 0, 1)
    px = im.load()
    row0 = [px[c, 0] for c in range(GW)]
    row1 = [px[c, 1] for c in range(GW)]
    ok1 = (row0 == [255] + [0] * 14 + [255]
           and row1 == [0] * 7 + [255, 255] + [0] * 7)
    print(f"    {'PASS' if ok1 else 'FAIL'}: 第0列 {''.join('#' if v else '.' for v in row0)}")
    print(f"    {'PASS' if ok1 else 'FAIL'}: 第1列 {''.join('#' if v else '.' for v in row1)}")
    if not ok1:
        fails.append("位元順序不符手算(高位應在左)")

    print("\n(2) 越界字模必須回全黑,而不是崩或讀到鄰格")
    try:
        im2 = render_glyph(b"\x00" * 32, 999, 1)
        p2 = im2.load()
        ok2 = all(p2[c, r] == 0 for r in range(GH) for c in range(GW))
    except Exception as exc:                                  # noqa: BLE001
        ok2 = False
        print(f"    FAIL: 丟出 {type(exc).__name__}")
    else:
        print(f"    {'PASS' if ok2 else 'FAIL'}: 越界索引 -> 全黑")
    if not ok2:
        fails.append("越界字模沒有安全處理")

    print("\n(3) 回歸:字型檔 1824 個字模;glyph 64(塞)與 904(賽)點陣差 25/32 bytes")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = os.path.join(root, "extracted", "raw", "FDOTHER", "FDOTHER_004.bin")
    if os.path.isfile(fp):
        raw = open(fp, "rb").read()
        n = len(raw) // GB
        a = raw[64 * GB:65 * GB]
        b = raw[904 * GB:905 * GB]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        ok3 = n == 1824 and diff == 25
        print(f"    {'PASS' if ok3 else 'FAIL'}: {n} 個字模(應 1824)、"
              f"差 {diff}/32 bytes(應 25)")
        if not ok3:
            fails.append(f"字型檔或塞/賽點陣與記載不符:{n} 個、差 {diff}")

        print("\n(4) 非恆真控制:同一個字模與自己比必須 0 差異,且兩者都不是全空")
        same = sum(1 for x, y in zip(a, a) if x != y)
        ok4 = same == 0 and any(a) and any(b)
        print(f"    {'PASS' if ok4 else 'FAIL'}: 自比差 {same}、"
              f"glyph64 非空={bool(any(a))}、glyph904 非空={bool(any(b))}")
        if not ok4:
            fails.append("非恆真控制失敗:字模全空或自比不為 0")
    else:
        print("    SKIP: 找不到 FDOTHER_004.bin")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(位元順序手算 + 越界處理 + 字模數與塞/賽點陣回歸 + "
          "非恆真控制)。")
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    # 沒帶參數時印用法,而不是讓 argv[1] 直接 IndexError——這是本 repo 其他
    # 同類工具一致的行為(2026-09-03 全工具驗證時發現只有本檔漏了)。
    if len(argv) < 5:
        print(__doc__)
        return 1
    font = open(argv[1], "rb").read()
    start = int(argv[2]); count = int(argv[3]); out = argv[4]
    scale = int(argv[5]) if len(argv) > 5 else 3
    cols = int(argv[6]) if len(argv) > 6 else 12
    gw = GW * scale
    cellw = gw + 30          # 留索引標籤空間
    cellh = gh = GH * scale + 16
    rows = (count + cols - 1) // cols
    img = Image.new("RGB", (cols * cellw + 4, rows * cellh + 4), (20, 20, 24))
    dr = ImageDraw.Draw(img)
    for k in range(count):
        idx = start + k
        cx = (k % cols) * cellw + 2
        cy = (k // cols) * cellh + 2
        dr.text((cx, cy), f"{idx}", fill=(120, 200, 120))      # 十進位索引
        gly = render_glyph(font, idx, scale).convert("RGB")
        img.paste(gly, (cx, cy + 12))
    img.save(out)
    print(f"glyph {start}..{start+count-1} -> {out}  ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
