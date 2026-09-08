#!/usr/bin/env python3
"""炎龍騎士團2 — sprite RLE 解碼器(第 3 輪,反組譯還原)。

從 FD2.EXE `0x4EB52`(24×24 sprite 解碼器)反組譯出的 4 模式 RLE 文法。
控制 byte c:高 2 bit = 模式,低 6 bit → count = (c & 0x3F) + 1:

    00xxxxxx  色彩 run     讀 1 像素,重複 count 次
    01xxxxxx  dither/scaled 讀 1 像素,隔位寫,佔 2×count 寬(陰影用)
    10xxxxxx  literal      讀 count 個像素原樣
    11xxxxxx  透明 skip     跳過 count 像素(留底 = 透明)

像素可經 remap 表轉換(原版 [ebp+eax]);本工具預設 identity。

⚠ 狀態:此文法對應 EXE 內 **24×24** 解碼器。FIGANI 戰鬥動畫(任意寬)使用
同家族的**另一參數化變體**(模式/位元配置略不同),套用本文法可精確消耗位元組但
渲染未對齊 → 待反組譯 0x4E000–0x4F800 對應變體後修正。詳見
docs/knowledge-base/06-animation-format.md。

用法:
    python3 decode_sprite.py <frame.bin> <w> <h> <palette.bin> <out.png>
"""
import os
import sys
import struct
# 2026-09-08:PIL 改成延遲 import。純解碼(decode_rle_sprite)不需要 Pillow,
# 但模組層 hard import 會讓整支工具在沒有 Pillow 的 WSL python3 下直接
# ModuleNotFoundError —— 而 DOSBox 測試環境正是跑在那個直譯器上。
# decode_text.py 先前踩過同一個坑。

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def decode_rle_sprite(body, width, height, trans=0, mode01="literal"):
    """4 模式 sprite RLE → 像素 bytes(transparent=trans)。"""
    out = bytearray()
    total = width * height
    i = 0
    n = len(body)
    while len(out) < total and i < n:
        c = body[i]; i += 1
        mode = c >> 6
        cnt = (c & 0x3F) + 1
        # 2026-09-08:模式 0 與 dither 分支原本直接 `body[i]` 取值位元組,控制
        # 位元組剛好落在資料尾端時會 IndexError **整支崩掉**;而模式 2/3 用切片,
        # 截斷時只是少寫幾個像素。同一個函式對同一種壞輸入有兩種行為,其中一種是
        # 崩潰。截斷的子資源在這個 repo 是真實情況(FIGANI 用的是另一參數化變體,
        # 套用本文法會提早耗盡),所以統一成「資料用完就停,交給下面 ljust 補滿」。
        if mode == 0 or (mode == 1 and mode01 != "literal"):
            if i >= n:
                break
            v = body[i]; i += 1
            if mode == 0:                  # 色彩 run
                out += bytes([v]) * cnt
            else:                          # dither:隔位寫,佔 2×count 寬
                out += bytes([trans, v]) * cnt
        elif mode == 3:                    # 透明 skip
            out += bytes([trans]) * cnt
        else:                              # literal(模式 2,以及預設參數化的模式 1)
            out += body[i:i + cnt]; i += cnt
    return bytes(out[:total]).ljust(total, bytes([trans]))


def selftest():
    """逐模式手算 + 不變量 + 故障注入。

    這個文法是從 EXE `0x4EB52` 反組譯還原的,所以每個模式都能寫出**手算的**
    預期輸出——只跑真實 sprite 只能證明「不崩」,證明不了控制位元組的解讀正確。
    cnt = (c & 0x3F) + 1;高 2 bit 選模式。
    """
    fails = []

    print("(1) 逐模式手算(cnt = (c & 0x3F) + 1)")
    cases = [
        ("00 色彩 run   c=0x02 -> cnt 3", b"\x02\xAA", 3, 1, {}, b"\xAA\xAA\xAA"),
        ("10 literal    c=0x82 -> cnt 3", b"\x82\x01\x02\x03", 3, 1, {}, b"\x01\x02\x03"),
        ("11 透明 skip  c=0xC4 -> cnt 5", b"\xC4", 5, 1, {"trans": 7},
         b"\x07" * 5),
        # 01 的兩種參數化都要釘住:預設是 literal,dither 變體會輸出 2×cnt
        ("01 預設 literal c=0x42 -> cnt 3", b"\x42\x11\x22\x33", 3, 1, {}, b"\x11\x22\x33"),
        ("01 dither     c=0x41 -> cnt 2, 2×寬", b"\x41\x55", 4, 1,
         {"trans": 0, "mode01": "dither"}, b"\x00\x55\x00\x55"),
        # 上面 5 個案例的控制位元組 bit5 都是 0,所以 `c>>6` 與 `c>>5` 會落在
        # 同一個分支 —— 第 (4) 題的負對照因此驗不出東西(它自己抓到了)。
        # 這兩個把 bit5 設起來,才真的把「模式取高 2 bit」釘住。
        ("00 色彩 run(bit5=1) c=0x22 -> cnt 35,截到 3", b"\x22\xAA", 3, 1, {},
         b"\xAA\xAA\xAA"),
        ("00 色彩 run(bit5=1) c=0x21 -> cnt 34,截到 2", b"\x21\xBB", 2, 1, {},
         b"\xBB\xBB"),
    ]
    for label, body, w, h, kw, want in cases:
        got = decode_rle_sprite(body, w, h, **kw)
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> {got.hex()}"
              + ("" if ok else f"(預期 {want.hex()})"))
        if not ok:
            fails.append(f"{label}: {got.hex()} != {want.hex()}")

    print("\n(2) 不變量:輸出長度永遠等於 width×height,不論輸入多短或多長")
    bad = []
    for body in (b"", b"\x02", b"\x3F\xAA", b"\xFF" * 40, b"\x82" + b"\x01" * 2):
        for w, h in ((24, 24), (5, 3), (1, 1)):
            n = len(decode_rle_sprite(body, w, h))
            if n != w * h:
                bad.append((body[:4].hex(), w, h, n))
    ok2 = not bad
    print(f"    {'PASS' if ok2 else 'FAIL'}: 15 組組合"
          + ("" if ok2 else f",長度不符 {bad[:3]}"))
    if not bad:
        pass
    else:
        fails.append(f"輸出長度不等於 w×h:{bad[:3]}")

    print("\n(3) 截斷是靜默的 —— 明確釘住這個行為,別讓它變成沒人知道的假設")
    # literal 宣稱 cnt=8 但 body 只剩 2 bytes:解碼器不會報錯,會補 trans 到滿。
    got3 = decode_rle_sprite(b"\x87\x01\x02", 8, 1, trans=0xEE)
    ok3 = got3 == b"\x01\x02" + b"\xEE" * 6
    print(f"    {'PASS' if ok3 else 'FAIL'}: {got3.hex()}(預期 0102 + EE×6)")
    if not ok3:
        fails.append(f"截斷行為與記載不符:{got3.hex()}")

    print("\n(4) 故障注入:改掉模式判定(mode>>6 -> mode>>5),手算案例必須失敗")
    # 用一個獨立實作把「模式取自高 2 bit」這件事本身當成待測項,而不是只信程式碼。
    def wrong(body, width, height, trans=0):
        out = bytearray(); i = 0
        while len(out) < width * height and i < len(body):
            c = body[i]; i += 1
            mode = c >> 5                       # 故意錯:取高 3 bit
            cnt = (c & 0x3F) + 1
            if mode == 0:
                v = body[i]; i += 1; out += bytes([v]) * cnt
            elif mode == 3:
                out += bytes([trans]) * cnt
            else:
                out += body[i:i + cnt]; i += cnt
        return bytes(out[:width * height]).ljust(width * height, bytes([trans]))
    diffs = sum(1 for label, body, w, h, kw, want in cases
                if kw.get("mode01") != "dither"
                and wrong(body, w, h, kw.get("trans", 0)) != want)
    ok4 = diffs >= 2
    print(f"    {'PASS' if ok4 else 'FAIL'}: 錯誤實作在 {diffs} 個案例上與預期不符"
          f"(至少要 2 個,否則這些案例分辨不出模式判定)")
    if not ok4:
        fails.append("手算案例對「模式取幾個 bit」沒有鑑別力")

    print("\n(5) 真實資料:解一個真的 sprite 子資源,長度與消耗都要合理")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "extracted", "raw", "FIGANI")
    real = None
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d))[:1]:
            real = os.path.join(d, fn)
    if real:
        body = open(real, "rb").read()
        px = decode_rle_sprite(body, 24, 24)
        nz = sum(1 for b in px if b)
        ok5 = len(px) == 576 and nz > 0
        print(f"    {'PASS' if ok5 else 'FAIL'}: {os.path.basename(real)} -> "
              f"{len(px)} px,非透明 {nz}")
        if not ok5:
            fails.append(f"真實 sprite 解出 {len(px)} px / 非透明 {nz}")
    else:
        print("    SKIP: 找不到 extracted/raw/FIGANI")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(4 模式手算 + 長度不變量 + 截斷行為 + "
          "模式判定的故障注入 + 真實資料)。")
    return 0


def load_palette(path):
    raw = open(path, "rb").read()[:768]
    pal = []
    for i in range(256):
        r, g, b = raw[i*3], raw[i*3+1], raw[i*3+2]
        pal += [(r << 2) | (r >> 4), (g << 2) | (g >> 4), (b << 2) | (b >> 4)]
    return pal


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 6:
        print(__doc__); return 1
    body = open(argv[1], "rb").read()
    w, h = int(argv[2]), int(argv[3])
    pal = load_palette(argv[4])
    px = decode_rle_sprite(body, w, h)
    from PIL import Image
    im = Image.frombytes("P", (w, h), px)
    im.putpalette(pal)
    im.convert("RGB").save(argv[5])
    print(f"{w}x{h} -> {argv[5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
