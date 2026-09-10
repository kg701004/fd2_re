#!/usr/bin/env python3
"""炎龍騎士團2 — DATO.DAT 人物頭像解碼器(第 6 輪)。

DATO.DAT(LLLLLL 容器,137 資源)= 對話頭像。每資源結構:
    +0  uint32[4]  4 個子圖 offset(= 講話嘴型 4 幀)
    各子圖:  uint16 W, uint16 H(多為 80×80), 然後 RLE 像素

RLE codec(反組譯自 0x4F716,與 sprite/背景不同的簡式):
    讀 byte b:
      b <= 0xC0 : 字面像素(值 = b)
      b >  0xC0 : run,重複 (b - 0xC0) 次下一個 byte
無透明(頭像為矩形實心)。調色盤:FDOTHER 資源 #0。
頭像在對話框由 0xFFEF 控制碼依說話者肖像 ID 載入(見 14-text-control-codes)。

用法:
    python3 decode_dato.py frames <DATO_NNN.bin> <palette.bin> <out目錄>
    python3 decode_dato.py --batch <raw/DATO目錄> <palette.bin> <out目錄>
"""
import sys
import os
import struct
import glob
# 2026-09-08:PIL 改成延遲 import。純解碼(rle)不需要 Pillow,模組層 hard import
# 會讓整支工具在沒有 Pillow 的 WSL python3 下直接 ModuleNotFoundError
# ——decode_text / decode_sprite / decode_lmi 都踩過同一個坑。

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def load_palette(path):
    raw = open(path, "rb").read()[:768]
    pal = []
    for i in range(256):
        r, g, b = raw[i*3], raw[i*3+1], raw[i*3+2]
        pal += [(r << 2) | (r >> 4), (g << 2) | (g >> 4), (b << 2) | (b >> 4)]
    return pal


def rle(body, total):
    out = bytearray()
    i = 0
    n = len(body)
    while len(out) < total and i < n:
        b = body[i]; i += 1
        if b <= 0xC0:
            out.append(b)
        else:
            # 2026-09-08:原本直接 `body[i]`,run 的控制位元組落在資料尾端時
            # IndexError 整支崩掉。以真實 FIGANI 前綴掃 401 個截斷長度,實測
            # 有 10 個會踩到。decode_sprite / decode_lmi / decode_ani 同一類。
            if i >= n:
                break
            v = body[i]; i += 1
            out += bytes([v]) * (b - 0xC0)
    return bytes(out[:total]).ljust(total, b"\0")


def selftest():
    """手算 codec + 截斷回歸 + 跨工具同族對照。

    這支的 codec 與 `decode_lmi.decode_pixels` 是同一族(<=0xC0 是單一 literal,
    >0xC0 是 (c-0xC0) 次的 run)。兩支各自獨立實作,所以第 (3) 題拿它們互相對照
    ——比只驗自己的預期值強:要一起錯才騙得過去。
    """
    fails = []

    print("(1) codec 手算")
    cases = [
        ("literal 0x05", b"\x05", 1, b"\x05"),
        ("邊界 0xC0 仍是 literal", b"\xC0", 1, b"\xC0"),
        ("run 0xC3 -> 3 次", b"\xC3\x77", 3, b"\x77\x77\x77"),
        ("混合", b"\x01\xC2\x09\x02", 4, b"\x01\x09\x09\x02"),
        ("不足時補 0", b"\x01", 4, b"\x01\x00\x00\x00"),
    ]
    for label, body, total, want in cases:
        got = rle(body, total)
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> {got.hex()}"
              + ("" if ok else f"(預期 {want.hex()})"))
        if not ok:
            fails.append(f"{label}: {got.hex()} != {want.hex()}")

    print("\n(2) 回歸:run 的控制位元組落在資料尾端,以前會 IndexError 整支崩掉")
    try:
        got2 = rle(b"\x01\xC5", 6)
        ok2 = got2 == b"\x01" + b"\x00" * 5
        shown = got2.hex()
    except IndexError:
        ok2, shown = False, "(IndexError)"
    print(f"    {'PASS' if ok2 else 'FAIL'}: {shown}")
    if not ok2:
        fails.append("截斷的 run 沒有被安全處理")

    print("\n(3) 跨工具對照:同族 codec 的獨立實作必須給出相同結果")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from decode_lmi import decode_pixels
        diff = [c[0] for c in cases if decode_pixels(c[1], c[2]) != rle(c[1], c[2])]
        ok3 = not diff
        print(f"    {'PASS' if ok3 else 'FAIL'}: 5 個案例"
              + ("全部一致" if ok3 else f",不一致 {diff}"))
        if not ok3:
            fails.append(f"與 decode_lmi 同族 codec 不一致:{diff}")
    except ImportError as exc:
        print(f"    SKIP: 無法 import decode_lmi({exc})")

    print("\n(4) 不變量:輸出長度永遠等於 total,不論輸入多短")
    bad = [(b.hex(), t, len(rle(b, t)))
           for b in (b"", b"\xC5", b"\x01" * 9, b"\xFF" * 5)
           for t in (1, 8, 576) if len(rle(b, t)) != t]
    ok4 = not bad
    print(f"    {'PASS' if ok4 else 'FAIL'}: 12 組組合"
          + ("" if ok4 else f",不符 {bad[:3]}"))
    if not ok4:
        fails.append(f"輸出長度不等於 total:{bad[:3]}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(codec 手算 + 截斷回歸 + 跨工具同族對照 + 長度不變量)。")
    return 0


def frames(path):
    """回傳 [(w,h,pixels), ...](通常 4 幀)。"""
    return frames_bytes(open(path, "rb").read())


def frames_bytes(d):
    """`frames` 的 bytes 核心 —— 見 `decode_fdicon.load_bytes` 的說明。這支同樣
    容易被誤認為已涵蓋:它的 `rle` 在截斷登錄表上,但**幀 offset 表**這一層不是。"""
    if len(d) < 16:
        return []
    offs = [struct.unpack_from("<I", d, 4 * i)[0] for i in range(4)]
    if offs[0] != 0x10:
        return []
    out = []
    for k in range(4):
        o = offs[k]
        end = offs[k + 1] if k + 1 < 4 else len(d)
        if o + 4 > len(d):
            continue
        w, h = struct.unpack_from("<HH", d, o)
        if not (0 < w <= 256 and 0 < h <= 256):
            continue
        out.append((w, h, rle(d[o + 4:end], w * h)))
    return out


def save(path, palp, outdir):
    pal = load_palette(palp)
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    for k, (w, h, px) in enumerate(frames(path)):
        from PIL import Image
        im = Image.frombytes("P", (w, h), px)
        im.putpalette(pal)
        im.convert("RGB").save(os.path.join(outdir, f"{base}_m{k}.png"))


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 4:
        print(__doc__); return 1
    if argv[1] == "--batch":
        src, palp, out = argv[2], argv[3], argv[4]
        n = 0
        for f in sorted(glob.glob(os.path.join(src, "*.bin"))):
            if frames(f):
                save(f, palp, out); n += 1
        print(f"{n} 個頭像 -> {out}")
        return 0
    save(argv[2], argv[3], argv[4])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
