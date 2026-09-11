#!/usr/bin/env python3
"""炎龍騎士團2 — FIGANI 戰鬥動畫逐幀解碼器(第 3 輪,反組譯還原完成)。

從 FD2.EXE 反組譯出的 sprite RLE 解碼器(參數化版 0x4F43D)逐指令還原。
**完整破解**:能把任一 FIGANI 動畫逐幀解出透明 sprite。

== 容器(FIGANI.DAT)==
LLLLLL 容器(見 unpack_dat.py)→ 每個資源 = 一段動畫。
動畫:u16 frameCount @0、u32[frameCount] 幀 offset @+8(frameCount = (offsets[0]-8)/4)。

== 每幀 ==
13-byte 標頭:
  +0  u16 boundW     顯示/外框寬
  +2  u16 boundH     顯示/外框高
  +4  u16 = 0
  +6  u16 = 2
  +8  u8  = 0
  +9  u16 W          點陣解碼寬(realW)
  +11 u16 H          點陣解碼高(realH)
  +13 …  RLE 像素資料(解碼到 W×H)

== RLE(4 模式;控制 byte 高 2 bit = 模式,低 6 bit → count=(c&0x3F)+1)==
  00  色彩 run       讀 1 像素,重複 count 次
  01  dither/陰影    讀 1 像素,輸出 [透明,值]×count(隔位寫,佔 2×count 寬)
  10  literal        讀 count 個像素原樣
  11  透明 skip      跳過 count(留底=透明)

調色盤:FDOTHER 資源 #0(見 decode_image.py)。透明色預設 index 0。

用法:
    python3 decode_figani.py frames <FIGANI_NNN.bin> <palette.bin> <out目錄>
    python3 decode_figani.py gif    <FIGANI_NNN.bin> <palette.bin> <out.gif>
    python3 decode_figani.py info   <FIGANI_NNN.bin>
"""
import sys
import os
import struct
# 2026-09-08:PIL 延遲 import(純解碼不需要 Pillow;模組層 hard import 會讓整支
# 工具在沒有 Pillow 的 WSL python3 下不可用)。


def load_palette(path):
    raw = open(path, "rb").read()[:768]
    pal = []
    for i in range(256):
        r, g, b = raw[i*3], raw[i*3+1], raw[i*3+2]
        pal += [(r << 2) | (r >> 4), (g << 2) | (g >> 4), (b << 2) | (b >> 4)]
    return pal


def decode_rle(body, w, h, trans=0):
    total = w * h
    out = bytearray()
    i = 0
    n = len(body)
    while len(out) < total and i < n:
        c = body[i]; i += 1
        mode = c >> 6
        cnt = (c & 0x3F) + 1
        # 2026-09-08:模式 0 與 1 原本直接 `body[i]` 取值位元組,控制位元組剛好是
        # 最後一個 byte 時 IndexError 整支崩掉。這是本 repo 第 5 個同類實例
        # (decode_sprite / decode_lmi / decode_dato / decode_ani 之後)。
        if mode in (0, 1):
            if i >= n:
                break
            v = body[i]; i += 1
            if mode == 0:                   # 色彩 run
                out += bytes([v]) * cnt
            else:                           # dither / 陰影
                out += bytes([trans, v]) * cnt
        elif mode == 2:                     # literal
            out += body[i:i + cnt]; i += cnt
        else:                               # 透明 skip
            out += bytes([trans]) * cnt
    return bytes(out[:total]).ljust(total, bytes([trans]))


def selftest():
    """手算 4 模式 + 截斷回歸 + 與 decode_sprite 的跨工具對照。

    這支與 `decode_sprite.decode_rle_sprite` 是同一族文法的兩個參數化:模式 1 在
    這裡固定是 dither,在那裡預設是 literal。所以第 (3) 題用
    `mode01="dither"` 去對照兩個**獨立實作**,其餘三個模式必須逐位元組一致。
    """
    import os as _os
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) 手算(cnt = (c & 0x3F) + 1,高 2 bit 選模式)")
    cases = [
        ("00 色彩 run c=0x02 -> 3", b"\x02\xAA", 3, 1, b"\xAA\xAA\xAA"),
        ("01 dither  c=0x41 -> 2,佔 2×寬", b"\x41\x55", 4, 1, b"\x00\x55\x00\x55"),
        ("10 literal c=0x82 -> 3", b"\x82\x01\x02\x03", 3, 1, b"\x01\x02\x03"),
        ("11 透明   c=0xC4 -> 5", b"\xC4", 5, 1, b"\x00" * 5),
        ("00 bit5=1 c=0x22 -> 35,截到 3", b"\x22\xAA", 3, 1, b"\xAA\xAA\xAA"),
    ]
    for label, body, w, h, want in cases:
        got = decode_rle(body, w, h)
        ok = got == want
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> {got.hex()}"
              + ("" if ok else f"(預期 {want.hex()})"))
        if not ok:
            fails.append(f"{label}: {got.hex()} != {want.hex()}")

    print("\n(2) 回歸:模式 0/1 的值位元組落在資料尾端,以前 IndexError 整支崩掉")
    bad = []
    for body in (b"\x02", b"\x41", b"\x22", b"\x82"):
        try:
            n = len(decode_rle(body, 24, 24))
            if n != 576:
                bad.append((body.hex(), n))
        except Exception as exc:                              # noqa: BLE001
            bad.append((body.hex(), type(exc).__name__))
    ok2 = not bad
    print(f"    {'PASS' if ok2 else 'FAIL'}: 4 個截斷控制位元組"
          + ("" if ok2 else f",異常 {bad}"))
    if not ok2:
        fails.append(f"截斷仍不安全:{bad}")

    print("\n(2b) 模式 0/1 讀值後的游標必須**恰好前進 1**,不能是 2")
    # (1) 的案例都只有單一 token(讀完值,串流剛好結束),游標多跳 1 byte 不會被
    # 後面任何東西讀到,測不出差異。用兩個連續 token 才能讓第二個控制位元組
    # 被錯誤位移的游標讀歪。
    two_tokens = decode_rle(b"\x00\xAA\x00\xBB", 2, 1)     # 兩個「c=0(色彩run,cnt=1)」token
    ok2b = two_tokens == b"\xAA\xBB"
    print(f"    {'PASS' if ok2b else 'FAIL'}: 兩個連續 token -> {two_tokens.hex()}(應 aabb)")
    if not ok2b:
        fails.append(f"模式 0 讀值後的游標位移不對:{two_tokens.hex()} != aabb")

    print("\n(3) 跨工具對照:同族文法的獨立實作(decode_sprite)必須一致")
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    try:
        from decode_sprite import decode_rle_sprite
        diff = [c[0] for c in cases
                if decode_rle_sprite(c[1], c[2], c[3], mode01="dither") != decode_rle(c[1], c[2], c[3])]
        ok3 = not diff
        print(f"    {'PASS' if ok3 else 'FAIL'}: 5 個案例"
              + ("全部一致" if ok3 else f",不一致 {diff}"))
        if not ok3:
            fails.append(f"與 decode_sprite 同族文法不一致:{diff}")
    except ImportError as exc:
        print(f"    SKIP: 無法 import decode_sprite({exc})")

    print("\n(4) 不變量 + 非恆真控制")
    lens = {len(decode_rle(b, w, h)) == w * h
            for b in (b"", b"\xFF" * 30, b"\x82\x01") for w, h in ((24, 24), (3, 2))}
    filled = decode_rle(b"\x3F\x77", 64, 1)          # run 長度 64,應寫滿
    ok4 = lens == {True} and filled == b"\x77" * 64
    print(f"    {'PASS' if ok4 else 'FAIL'}: 長度不變量 {lens};"
          f"合法 run 寫滿 {filled[:4].hex()}…({filled.count(0x77)}/64)")
    if not ok4:
        fails.append("長度不變量或非恆真控制失敗")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(4 模式手算 + 截斷回歸 + 跨工具同族對照 + "
          "不變量與非恆真控制)。")
    return 0


def parse_anim(d):
    """回傳 [(realW, realH, body_bytes), ...]。"""
    nf = struct.unpack_from("<H", d, 0)[0]
    offs = [struct.unpack_from("<I", d, 8 + 4 * i)[0] for i in range(nf)]
    frames = []
    for fi in range(nf):
        o = offs[fi]
        end = offs[fi + 1] if fi + 1 < nf else len(d)
        if o + 13 > len(d):
            continue
        w = struct.unpack_from("<H", d, o + 9)[0]
        h = struct.unpack_from("<H", d, o + 11)[0]
        if not (0 < w <= 1024 and 0 < h <= 1024):
            continue
        frames.append((w, h, d[o + 13:end]))
    return frames


def render_frame(w, h, body, pal, trans=0):
    px = decode_rle(body, w, h, trans)
    from PIL import Image
    im = Image.frombytes("P", (w, h), px)
    im.putpalette(pal)
    im.info["transparency"] = trans  # index trans(預設0)為透明,convert RGBA 時轉 alpha=0
    return im


def cmd_frames(src, palp, outdir):
    d = open(src, "rb").read()
    pal = load_palette(palp)
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    frames = parse_anim(d)
    for fi, (w, h, body) in enumerate(frames):
        im = render_frame(w, h, body, pal)
        im.convert("RGBA").save(os.path.join(outdir, f"{base}_f{fi:02d}.png"))  # 保留透明背景
    print(f"{base}: {len(frames)} 幀 -> {outdir}")


def cmd_gif(src, palp, out):
    d = open(src, "rb").read()
    pal = load_palette(palp)
    frames = parse_anim(d)
    if not frames:
        print("無幀"); return
    W = max(w for w, h, _ in frames)
    H = max(h for w, h, _ in frames)
    ims = []
    for w, h, body in frames:
        from PIL import Image
        canvas = Image.new("P", (W, H), 0)
        canvas.putpalette(pal)
        canvas.paste(render_frame(w, h, body, pal), (0, H - h))
        ims.append(canvas.convert("RGB"))
    ims[0].save(out, save_all=True, append_images=ims[1:], duration=120, loop=0)
    print(f"{len(ims)} 幀 -> {out}")


def cmd_info(src):
    d = open(src, "rb").read()
    frames = parse_anim(d)
    print(f"{os.path.basename(src)}: {len(frames)} 幀")
    for fi, (w, h, body) in enumerate(frames):
        print(f"  幀{fi}: {w}x{h}  壓縮={len(body)}B")


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 3:
        print(__doc__); return 1
    cmd = argv[1]
    if cmd == "frames":
        cmd_frames(argv[2], argv[3], argv[4])
    elif cmd == "gif":
        cmd_gif(argv[2], argv[3], argv[4])
    elif cmd == "info":
        cmd_info(argv[2])
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
