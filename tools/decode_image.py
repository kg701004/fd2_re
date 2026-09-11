#!/usr/bin/env python3
"""炎龍騎士團2 — .DAT 圖像解碼器(第 2 輪)。

圖像格式(已驗證):
    +0  uint16 LE  width
    +2  uint16 LE  height
    +4  pixel data,8-bit VGA 調色盤索引(mode 13h)

像素資料有兩種:
  (a) 未壓縮:body == W*H(如 FDOTHER_015 / FDOTHER_055)。
  (b) 壓縮:body < W*H(RLE,演算法見 decode_rle;第 2 輪持續驗證中)。

調色盤:預設取 FDOTHER 容器資源 #0(768B = 256×RGB,6-bit 0..63 → ×4 轉 8-bit)。
不同畫面可能切換調色盤,後輪再對應。

用法:
    python3 decode_image.py <resource.bin> <palette.bin> <out.png>
    python3 decode_image.py --batch <extracted根> <palette.bin> <out目錄>
"""
import sys
import os
import struct
import glob
# 2026-09-08:PIL 延遲 import(純解碼不需要 Pillow;模組層 hard import 會讓整支
# 工具在沒有 Pillow 的 WSL python3 下不可用)。


def load_palette(path):
    raw = open(path, "rb").read()[:768]
    pal = []
    for i in range(256):
        r, g, b = raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]
        # 6-bit VGA → 8-bit
        pal.extend([(r << 2) | (r >> 4), (g << 2) | (g >> 4), (b << 2) | (b >> 4)])
    return pal


def decode_rle(body, target):
    """RLE 解壓(第 2 輪破解):
        讀 byte c
          c >= 0x80 : 文字串(literal),接下來 (c&0x7f)+1 個 byte 原樣輸出
          c <  0x80 : 連續執行(run),下一個 byte 重複 (c+1) 次
    成功(輸出剛好 target)回傳 bytes,否則 None。"""
    out = bytearray()
    i = 0
    n = len(body)
    while i < n and len(out) < target:
        c = body[i]
        i += 1
        if c >= 0x80:
            cnt = (c & 0x7f) + 1
            out += body[i:i + cnt]
            i += cnt
        else:
            if i >= n:
                break
            out += bytes([body[i]]) * (c + 1)
            i += 1
    return bytes(out) if len(out) == target else None


def selftest():
    """手算 + 契約檢查 + 邊界守衛的回歸。

    這支的 RLE 是 repo 裡**唯一原本就正確守衛**的一個(`if i >= n: break`),
    2026-09-08 逐一掃全 401 個截斷長度也確實 0 例外。所以這裡的第 (3) 題是
    **回歸測試**:它是對照組,證明其他四支的修法是回到這個已知正確的形狀,
    而不是各自發明一種。

    另外它的契約與其他解碼器**不同**:輸出長度不等於 target 時回傳 `None`,
    而不是補滿。這個差異必須釘住,否則呼叫端會誤以為所有解碼器行為一致。
    """
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) 手算:c>=0x80 是 literal((c&0x7f)+1 個),c<0x80 是 run(重複 c+1 次)")
    cases = [
        ("literal 0x82 -> 3 個", b"\x82\x01\x02\x03", 3, b"\x01\x02\x03"),
        ("run 0x02 -> 重複 3 次", b"\x02\xAA", 3, b"\xAA\xAA\xAA"),
        ("run 0x00 -> 重複 1 次", b"\x00\x09", 1, b"\x09"),
        ("literal 0xFF -> 128 個", b"\xFF" + bytes(range(128)), 128, bytes(range(128))),
        ("混合", b"\x80\x11\x01\x22", 3, b"\x11\x22\x22"),
    ]
    for label, body, target, want in cases:
        got = decode_rle(body, target)
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> "
              f"{got.hex() if got else None}"
              + ("" if ok else f"(預期 {want.hex()})"))
        if not ok:
            fails.append(f"{label}: {got.hex() if got else None} != {want.hex()}")

    print("\n(2) 契約:**只有**長度恰好等於 target 才回 bytes,不足與過長都回 None")
    # 2026-09-08:第一版把「過長」寫成期望回 bytes,是我讀錯了契約——
    # `return bytes(out) if len(out) == target else None` 是嚴格相等,兩邊都回 None。
    # 這個契約與其他解碼器(補滿到 target)**不同**,呼叫端不能假設一致,所以要釘住。
    short = decode_rle(b"\x02\xAA", 999)          # 只解出 3,不足
    over = decode_rle(b"\xFF" + bytes(200), 3)    # literal 128 個,過長
    exact = decode_rle(b"\x02\xAA", 3)            # 恰好
    ok2 = short is None and over is None and exact == b"\xAA\xAA\xAA"
    print(f"    {'PASS' if ok2 else 'FAIL'}: 不足 -> {short};過長 -> {over};"
          f"恰好 -> {exact.hex() if exact else None}")
    if not ok2:
        fails.append(f"契約不符:不足={short}、過長={over}、恰好={exact}")

    print("\n(3) 回歸:run 的值位元組落在資料尾端 —— 這支本來就有守衛,是對照組")
    bad = []
    for body in (b"\x02", b"", b"\x7F", b"\x82\x01"):
        try:
            decode_rle(body, 576)
        except Exception as exc:                              # noqa: BLE001
            bad.append((body.hex(), type(exc).__name__))
    ok3 = not bad
    print(f"    {'PASS' if ok3 else 'FAIL'}: 4 個截斷輸入"
          + ("(全部安全,與 2026-09-08 逐一掃 401 個長度的結果一致)" if ok3
             else f",異常 {bad}"))
    if not ok3:
        fails.append(f"對照組竟然也會崩:{bad}")

    print("\n(4) 非恆真控制:合法輸入必須真的解出東西,不能永遠回 None")
    got4 = decode_rle(b"\x02\xAA", 3)
    ok4 = got4 == b"\xAA\xAA\xAA"
    print(f"    {'PASS' if ok4 else 'FAIL'}: 合法 run 解出 "
          f"{got4.hex() if got4 else None}")
    if not ok4:
        fails.append("合法輸入沒有解出預期結果")

    print("\n(5) 連續兩個 run:run 之後游標只前進 1(值位元組)")
    # 2026-09-11 窮舉突變測試:run 分支的 `i += 1` 改成 2 逃掉 —— 單一 run 之後已無資料。
    got5 = decode_rle(b"\x01\xAA\x01\xBB", 4)
    ok5 = got5 == b"\xAA\xAA\xBB\xBB"
    print(f"    {'PASS' if ok5 else 'FAIL'}: 01 AA 01 BB -> {got5.hex() if got5 else None}(應 aaaabbbb)")
    if not ok5:
        fails.append(f"連續 run 解錯:{got5}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(手算 + None 契約 + 守衛回歸(對照組) + 非恆真控制)。")
    return 0


def decode_image(path):
    """回傳 (w, h, indices_bytes_or_None, mode)。"""
    d = open(path, "rb").read()
    if len(d) < 6:
        return None
    w, h = struct.unpack_from("<HH", d, 0)
    body = d[4:]
    if not (0 < w <= 1024 and 0 < h <= 1024):
        return None
    if len(body) == w * h:
        return (w, h, body, "raw")
    px = decode_rle(body, w * h)
    if px is not None:
        return (w, h, px, "rle")
    return (w, h, None, "compressed")


def save_png(w, h, idx, palette, out):
    from PIL import Image
    im = Image.frombytes("P", (w, h), bytes(idx))
    im.putpalette(palette)
    im.convert("RGB").save(out)


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 2:
        print(__doc__); return 1
    if argv[1] == "--batch":
        root, palp, outdir = argv[2], argv[3], argv[4]
        pal = load_palette(palp)
        os.makedirs(outdir, exist_ok=True)
        n_raw = n_skip = 0
        for f in sorted(glob.glob(os.path.join(root, "*", "*.bin"))):
            r = decode_image(f)
            if r and r[2] is not None:
                w, h, idx, mode = r
                name = os.path.splitext(os.path.relpath(f, root).replace(os.sep, "_"))[0]
                save_png(w, h, idx, pal, os.path.join(outdir, f"{name}.png"))
                n_raw += 1
            else:
                n_skip += 1
        print(f"輸出 {n_raw} 張(未壓縮/可解),略過 {n_skip}(壓縮待解或非圖)")
        return 0
    src, palp, out = argv[1], argv[2], argv[3]
    pal = load_palette(palp)
    r = decode_image(src)
    if not r:
        print("非圖像格式"); return 1
    w, h, idx, mode = r
    if idx is None:
        print(f"{w}x{h} 壓縮({mode}),解壓未實作"); return 2
    save_png(w, h, idx, pal, out)
    print(f"{w}x{h} {mode} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
