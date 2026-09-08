#!/usr/bin/env python3
"""炎龍騎士團2 — 地圖渲染(FDSHAP 圖塊 + FDFIELD 地圖 → PNG)。

== FDSHAP 圖塊庫 ==
大資源 = tileset。標頭:u16 tileW(24)、u16 tileH(24)、u16 count、然後 **u32[count] 圖塊 offset 表**
(首個 offset = 6+count*4 = 表尾)。每塊為原生 24×24 **four-mode sprite RLE**；FDSHAP_000
已實測含 mode-3 transparent spans，不能以舊的「不透明 bg-RLE」解到下一 tile。依 offset 表定位。
FDSHAP 資源「大 / 1200B」交替成對,1200B = 該 tileset 的地形控制表(300×4)。

== FDFIELD 地圖(LLLLLL 容器)==
每地圖 3 資源:構成 / 控制 / 出場(見 03-…)。**構成**:u16 W, u16 H, 然後每格 (u16 地形索引, u16 事件)。
地形索引 → FDSHAP tileset 的圖塊。

用法:
    python3 render_map.py <FDFIELD構成.bin> <FDSHAP_tileset.bin> <palette.bin> <out.png>
"""
import sys
import struct
# 2026-09-08:PIL 延遲 import(_tile_rle/decode_tileset 不需要 Pillow)。

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _tile_rle(body, width, height):
    """Native 0x4deda-compatible RLE; returns indexed pixels plus opacity mask."""
    out = bytearray(width * height)
    mask = bytearray(width * height)
    p = 0
    for y in range(height):
        x = 0
        while x < width and p < len(body):
            control = body[p]; p += 1
            count, mode = (control & 0x3f) + 1, control >> 6
            span = count * 2 if mode == 1 else count
            if x + span > width:
                break
            if mode == 0:
                if p >= len(body): break
                out[y * width + x:y * width + x + count] = bytes([body[p]]) * count
                mask[y * width + x:y * width + x + count] = b"\xff" * count; p += 1
            elif mode == 1:
                if p >= len(body): break
                out[y * width + x + 1:y * width + x + span:2] = bytes([body[p]]) * count
                mask[y * width + x + 1:y * width + x + span:2] = b"\xff" * count; p += 1
            elif mode == 2:
                if p + count > len(body): break
                out[y * width + x:y * width + x + count] = body[p:p + count]
                mask[y * width + x:y * width + x + count] = b"\xff" * count; p += count
            # mode 3 is transparent: zero-filled destination and no payload.
            x += span
    return bytes(out), bytes(mask)


def decode_tileset(path, with_masks=False):
    """回傳 indexed tiles; with_masks keeps native transparent spans distinct from index 0."""
    d = open(path, "rb").read()
    # 2026-09-08:原本沒有任何長度檢查,截斷或非 tileset 的檔案會丟出原始的
    # struct.error。decode_fdicon.load 是同一個檔頭形狀、同一類問題,同一輪一併修。
    if len(d) < 6:
        raise ValueError(f"{path}: 只有 {len(d)} bytes,連 6-byte 檔頭都不足")
    tw, th, cnt = struct.unpack_from("<HHH", d, 0)
    if not (0 < tw <= 256 and 0 < th <= 256):
        raise ValueError(f"{path}: tile 尺寸不合理 {tw}x{th}")
    if cnt == 0 or 6 + cnt * 4 > len(d):
        raise ValueError(f"{path}: offset 表宣稱 {cnt} 筆,超出檔案大小 {len(d)}")
    offs = [struct.unpack_from("<I", d, 6 + 4 * i)[0] for i in range(cnt)]
    tiles, masks = [], []
    for k in range(cnt):
        s = offs[k]
        e = offs[k + 1] if k + 1 < cnt else len(d)
        pixels, mask = _tile_rle(d[s:e], tw, th)
        tiles.append(pixels)
        masks.append(mask)
    if with_masks:
        return tw, th, tiles, masks
    return tw, th, tiles


def selftest():
    """`_tile_rle` 與其他五支同族 RLE 的差別在於它**同時回傳 mask**。

    那個 mask 不是裝飾:它把「原生透明跨距」與「值剛好是 index 0 的像素」分開。
    少了它,地圖 tile 的透明區與黑色像素會被混為一談。所以這裡的手算案例每一個
    都同時檢查 pixels 與 mask —— 只驗 pixels 會讓 mask 的邏輯完全沒被涵蓋。

    另外這支的三個模式**原本就都有邊界守衛**(2026-09-08 逐一前綴實測 0 例外),
    是繼 decode_image 之後第二個對照組;而 decode_tileset 的檔頭則沒有,同輪補上。
    """
    import os
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) 逐模式手算:pixels 與 mask 必須同時正確")
    cases = [
        # (說明, body, w, h, 預期 pixels, 預期 mask)
        ("00 色彩 run c=0x02 -> 3", b"\x02\xAA", 4, 1,
         b"\xAA\xAA\xAA\x00", b"\xff\xff\xff\x00"),
        ("10 literal c=0x82 -> 3", b"\x82\x01\x02\x03", 4, 1,
         b"\x01\x02\x03\x00", b"\xff\xff\xff\x00"),
        ("11 透明 c=0xC2 -> 3(留 0 且 mask 也是 0)", b"\xC2", 4, 1,
         b"\x00\x00\x00\x00", b"\x00\x00\x00\x00"),
        # mode 1 佔 2×count 寬,只寫奇數位;偶數位留透明(mask 0)
        ("01 dither c=0x41 -> count 2,span 4", b"\x41\x55", 4, 1,
         b"\x00\x55\x00\x55", b"\x00\xff\x00\xff"),
    ]
    for label, body, w, h, want_px, want_mask in cases:
        px, mask = _tile_rle(body, w, h)
        ok = px == want_px and mask == want_mask
        print(f"    {'PASS' if ok else 'FAIL'}: {label} -> px {px.hex()} mask {mask.hex()}"
              + ("" if ok else f"(預期 {want_px.hex()} / {want_mask.hex()})"))
        if not ok:
            fails.append(f"{label}: {px.hex()}/{mask.hex()} != {want_px.hex()}/{want_mask.hex()}")

    print("\n(2) 關鍵區別:index 0 的**像素**與**透明**在 mask 上必須不同")
    px_zero, m_zero = _tile_rle(b"\x00\x00", 2, 1)      # 色彩 run,值 = 0,count 1
    px_tr, m_tr = _tile_rle(b"\xC0", 2, 1)              # 透明 skip,count 1
    ok2 = px_zero[0] == px_tr[0] == 0 and m_zero[0] == 0xFF and m_tr[0] == 0
    print(f"    {'PASS' if ok2 else 'FAIL'}: 兩者 pixel 都是 0,但 mask "
          f"{m_zero[0]:#x}(實心)vs {m_tr[0]:#x}(透明)")
    if not ok2:
        fails.append("mask 沒有把 index-0 像素與透明分開 —— 這正是它存在的理由")

    print("\n(3) span 超出寬度時必須停下該列,不得寫出界")
    px3, m3 = _tile_rle(b"\x3F\xAA", 4, 2)             # count 64,遠超 width 4
    ok3 = len(px3) == 8 and len(m3) == 8 and set(m3) == {0}
    print(f"    {'PASS' if ok3 else 'FAIL'}: 輸出 {len(px3)} px,mask 唯一值 {sorted(set(m3))}")
    if not ok3:
        fails.append(f"超寬 span 沒有被擋:{len(px3)} px, mask {sorted(set(m3))}")

    print("\n(4) 截斷窮舉:三個模式原本就有守衛,逐一前綴必須 0 例外")
    body = b"\x02\xAA\x82\x01\x02\x03\xC2\x41\x55"
    bad = {}
    for cut in range(len(body) + 1):
        try:
            p, m = _tile_rle(body[:cut], 8, 4)
            if len(p) != 32 or len(m) != 32:
                bad["長度不符"] = bad.get("長度不符", 0) + 1
        except Exception as exc:                              # noqa: BLE001
            bad[type(exc).__name__] = bad.get(type(exc).__name__, 0) + 1
    ok4 = not bad
    print(f"    {'PASS' if ok4 else 'FAIL'}: {len(body) + 1} 個前綴"
          + ("全部安全且長度正確" if ok4 else f",問題 {bad}"))
    if not ok4:
        fails.append(f"截斷處理有問題:{bad}")

    print("\n(5) decode_tileset 的檔頭守衛(同輪新增)+ 真實 FDSHAP")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        for label, blob in (("空檔", b""), ("尺寸為 0", struct.pack("<HHH", 0, 24, 4)),
                            ("offset 表超出檔尾", struct.pack("<HHH", 24, 24, 9999))):
            q = os.path.join(td, "bad.bin")
            open(q, "wb").write(blob)
            try:
                decode_tileset(q)
                print(f"    FAIL: 「{label}」沒有被擋下")
                fails.append(f"{label} 沒有被擋下")
            except ValueError:
                print(f"    PASS: 「{label}」-> ValueError")
            except Exception as exc:                          # noqa: BLE001
                print(f"    FAIL: 「{label}」丟出 {type(exc).__name__}")
                fails.append(f"{label} 丟出 {type(exc).__name__}")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, "extracted", "raw", "FDSHAP")
    ok5 = False
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            try:
                tw, th, tiles = decode_tileset(os.path.join(d, fn))
            except (ValueError, struct.error, OSError):
                continue
            if tiles and all(len(t) == tw * th for t in tiles):
                ok5 = True
                print(f"    PASS: {fn} -> {tw}x{th} × {len(tiles)} 個 tile,長度全部正確")
                break
    if not ok5:
        print("    FAIL: 沒有任何真實 FDSHAP 解出合法 tileset")
        fails.append("真實 FDSHAP 解不出 tileset —— 正向那半是空的")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(4 模式 pixels+mask 手算 + index0/透明的區別 + "
          "超寬 span + 截斷窮舉 + 檔頭守衛與真實 FDSHAP)。")
    return 0


def load_palette(path):
    raw = open(path, "rb").read()[:768]
    pal = []
    for i in range(256):
        r, g, b = raw[i*3], raw[i*3+1], raw[i*3+2]
        pal += [(r << 2) | (r >> 4), (g << 2) | (g >> 4), (b << 2) | (b >> 4)]
    return pal


def render(fieldp, shapp, palp, out):
    pal = load_palette(palp)
    tw, th, tiles = decode_tileset(shapp)
    d = open(fieldp, "rb").read()
    w, h = struct.unpack_from("<HH", d, 0)
    from PIL import Image
    img = Image.new("P", (w * tw, h * th), 0)
    img.putpalette(pal)
    for cy in range(h):
        for cx in range(w):
            ti = struct.unpack_from("<H", d, 4 + (cy * w + cx) * 4)[0]
            if ti < len(tiles):
                img.paste(Image.frombytes("P", (tw, th), tiles[ti]), (cx * tw, cy * th))
    img.convert("RGB").save(out)
    print(f"{w}x{h} 地圖({w*tw}x{h*th}px) -> {out}  (tileset {len(tiles)} tiles)")


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 5:
        print(__doc__); return 1
    render(argv[1], argv[2], argv[3], argv[4])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
