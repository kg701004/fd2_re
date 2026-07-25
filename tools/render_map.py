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
from PIL import Image


def _tile_rle(body, width, height):
    """Native 0x4deda-compatible 24×24 RLE; transparent spans remain index 0."""
    out = bytearray(width * height)
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
                out[y * width + x:y * width + x + count] = bytes([body[p]]) * count; p += 1
            elif mode == 1:
                if p >= len(body): break
                out[y * width + x + 1:y * width + x + span:2] = bytes([body[p]]) * count; p += 1
            elif mode == 2:
                if p + count > len(body): break
                out[y * width + x:y * width + x + count] = body[p:p + count]; p += count
            # mode 3 is transparent: zero-filled destination and no payload.
            x += span
    return bytes(out)


def decode_tileset(path):
    """回傳 (tileW, tileH, [tile_pixels...]),依 offset 表定位(無漂移)。"""
    d = open(path, "rb").read()
    tw, th, cnt = struct.unpack_from("<HHH", d, 0)
    offs = [struct.unpack_from("<I", d, 6 + 4 * i)[0] for i in range(cnt)]
    tiles = []
    for k in range(cnt):
        s = offs[k]
        e = offs[k + 1] if k + 1 < cnt else len(d)
        tiles.append(_tile_rle(d[s:e], tw, th))
    return tw, th, tiles


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
    if len(argv) < 5:
        print(__doc__); return 1
    render(argv[1], argv[2], argv[3], argv[4])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
