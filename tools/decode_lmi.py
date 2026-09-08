#!/usr/bin/env python3
"""LMI1 容器(FDOTHER #5 等 UI sprite 集)解碼。

LMI1 結構:
  +0   char[4]  "LMI1"
  +4   uint16   sub-resource 數 N
  +6   uint32[N] 各 sub-resource offset(相對檔頭)
  各 sub-resource: uint16 w, uint16 h, 接 codec 資料(見下)

像素 codec(反組譯 FD2.EXE 0x4e916,逐像素取值):
  讀控制 byte c:
    c <= 0xC0 : c 本身就是一個像素值(literal 單 px)
    c >  0xC0 : run,長度 = c-0xC0,後跟 1 個像素值,重複該長度
  (透明 = palette index 0;run 可跨行,線性解 w*h px)
  → 純 literal 的小圖(如 1xN 血條 cell)剛好等同 raw。

用法:
  python3 decode_lmi.py <FDOTHER_005.bin> <palette.bin> <out目錄> [idx...]
  不給 idx = 列出所有 sub-resource 的 w×h;給 idx = 解出該些為 PNG(index0 透明)。
"""
import struct
import sys
import os
# 2026-09-08:PIL 改成延遲 import。純解碼(lmi_offsets/decode_pixels)不需要
# Pillow,模組層 hard import 會讓整支工具在沒有 Pillow 的 WSL python3 下
# 直接 ModuleNotFoundError。decode_text.py / decode_sprite.py 同一個坑。

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


class NotLMI(Exception):
    pass


def lmi_offsets(d):
    # 2026-09-08:原本用 `assert d[:4] == b"LMI1"`。assert 在 `python -O` 下會被
    # **整條移除**,那時餵非 LMI 檔進來不會報錯,會拿 offset 4 的兩個 byte 當成
    # 資源數去解,安靜地產出垃圾。改成真的例外。
    if d[:4] != b"LMI1":
        raise NotLMI("非 LMI1 容器")
    n = struct.unpack_from("<H", d, 4)[0]
    if 6 + n * 4 > len(d):
        raise NotLMI(f"目錄宣稱 {n} 筆,超出檔案大小 {len(d)}")
    return [struct.unpack_from("<I", d, 6 + i * 4)[0] for i in range(n)]


def decode_pixels(body, total):
    """0x4e916 codec → index bytes(透明=0)。"""
    out = bytearray()
    i = 0
    while len(out) < total and i < len(body):
        c = body[i]
        i += 1
        if c <= 0xC0:
            out.append(c)
        else:
            cnt = c - 0xC0
            # 2026-09-08:原本直接 `body[i]`,run 的控制位元組剛好落在資料尾端時
            # 會 IndexError 整支崩掉(decode_sprite.py 是同一類 bug,實測有 36 個
            # 真實子資源會踩到)。資料用完就停,交給下面 ljust 補滿。
            if i >= len(body):
                break
            v = body[i]
            i += 1
            out += bytes([v]) * cnt
    return bytes(out[:total]).ljust(total, b"\x00")


def selftest():
    """手算 codec + 目錄解析 + 兩個剛修掉的崩潰/靜默類 bug 的回歸測試。"""
    import os
    fails = []

    print("(1) codec 手算:c<=0xC0 是單一 literal,c>0xC0 是 (c-0xC0) 次的 run")
    cases = [
        ("literal 0x05", b"\x05", 1, b"\x05"),
        ("邊界 0xC0 仍是 literal", b"\xC0", 1, b"\xC0"),
        ("run 0xC3 -> 3 次", b"\xC3\x77", 3, b"\x77\x77\x77"),
        ("混合", b"\x01\xC2\x09\x02", 4, b"\x01\x09\x09\x02"),
        ("不足時補 0", b"\x01", 4, b"\x01\x00\x00\x00"),
    ]
    for label, body, total, want in cases:
        got = decode_pixels(body, total)
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> {got.hex()}"
              + ("" if ok else f"(預期 {want.hex()})"))
        if not ok:
            fails.append(f"{label}: {got.hex()} != {want.hex()}")

    print("\n(2) 回歸:run 的控制位元組落在資料尾端,以前會 IndexError 整支崩掉")
    try:
        got2 = decode_pixels(b"\x01\xC5", 6)
        ok2 = got2 == b"\x01" + b"\x00" * 5
    except IndexError:
        ok2 = False
        got2 = b"(IndexError)"
    print(f"    {'PASS' if ok2 else 'FAIL'}: {got2 if isinstance(got2, bytes) else got2}")
    if not ok2:
        fails.append("截斷的 run 沒有被安全處理")

    print("\n(3) 目錄解析 + 故障注入(magic / 目錄超出檔尾都要丟 NotLMI)")
    good = b"LMI1" + struct.pack("<H", 2) + struct.pack("<I", 14) + struct.pack("<I", 20) + b"x" * 12
    got3 = lmi_offsets(good)
    ok3 = got3 == [14, 20]
    print(f"    {'PASS' if ok3 else 'FAIL'}: 正向 {got3}(預期 [14, 20])")
    if not ok3:
        fails.append(f"目錄解析錯誤 {got3}")
    for label, blob in (("magic 不對", b"XXXX" + struct.pack("<H", 1) + b"\x00" * 8),
                        ("目錄超出檔尾", b"LMI1" + struct.pack("<H", 9999) + b"\x00" * 4)):
        try:
            lmi_offsets(blob)
            print(f"    FAIL: 「{label}」沒有被擋下")
            fails.append(f"{label} 沒有被擋下")
        except NotLMI:
            print(f"    PASS: 「{label}」-> NotLMI")

    print("\n(4) 回歸:改用真例外而非 assert —— 在 -O 模式下也必須擋得住")
    import subprocess
    src = ("import sys; sys.path.insert(0, r'%s')\n"
           "from decode_lmi import lmi_offsets, NotLMI\n"
           "try:\n"
           "    lmi_offsets(b'XXXX' + b'\\x01\\x00' + b'\\x00'*8)\n"
           "    print('LEAK')\n"
           "except NotLMI:\n"
           "    print('BLOCKED')\n") % os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, "-O", "-c", src], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    ok4 = "BLOCKED" in (r.stdout or "")
    print(f"    {'PASS' if ok4 else 'FAIL'}: python -O 下 -> {(r.stdout or r.stderr or '').strip()[:60]}")
    if not ok4:
        fails.append("python -O 下非 LMI 檔沒有被擋下(assert 會被移除)")

    print("\n(5) 真實資料:FDOTHER 裡至少要有一個真的 LMI1 容器解得開")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "extracted", "raw", "FDOTHER")
    hits = 0
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            try:
                if lmi_offsets(open(os.path.join(d, fn), "rb").read()):
                    hits += 1
            except (NotLMI, OSError, struct.error):
                continue
    ok5 = hits > 0
    print(f"    {'PASS' if ok5 else 'FAIL'}: 解得開的 LMI1 容器 {hits} 個")
    if not ok5:
        fails.append("找不到任何真實 LMI1 容器 —— 正向那半是空的")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(codec 手算 + 截斷回歸 + 目錄故障注入 + "
          "-O 模式回歸 + 真實資料)。")
    return 0


def load_palette(path):
    """VGA DAC 6-bit(0-63)→ 8-bit:(v<<2)|(v>>4),同 decode_sprite。"""
    p = open(path, "rb").read()
    return [tuple((v << 2) | (v >> 4) for v in (p[i * 3], p[i * 3 + 1], p[i * 3 + 2]))
            for i in range(256)]


def sub_to_png(d, offs, idx, prgb, out_path):
    o = offs[idx]
    w, h = struct.unpack_from("<HH", d, o)
    end = offs[idx + 1] if idx + 1 < len(offs) else len(d)
    px = decode_pixels(d[o + 4:end], w * h)
    from PIL import Image
    img = Image.new("RGBA", (w, h))
    pix = img.load()
    for y in range(h):
        for x in range(w):
            ci = px[y * w + x]
            pix[x, y] = (0, 0, 0, 0) if ci == 0 else (*prgb[ci], 255)
    img.save(out_path)
    return w, h


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 4:
        print(__doc__)
        return 1
    d = open(argv[1], "rb").read()
    prgb = load_palette(argv[2])
    outdir = argv[3]
    offs = lmi_offsets(d)
    os.makedirs(outdir, exist_ok=True)
    if len(argv) == 4:
        for i, o in enumerate(offs):
            w, h = struct.unpack_from("<HH", d, o)
            print(f"#{i} @{hex(o)} {w}x{h}")
        return 0
    for a in argv[4:]:
        idx = int(a)
        w, h = sub_to_png(d, offs, idx, prgb, os.path.join(outdir, f"lmi_{idx:03d}.png"))
        print(f"#{idx} -> {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
