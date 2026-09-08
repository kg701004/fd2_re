#!/usr/bin/env python3
"""炎龍騎士團2 — 解碼 FDICON.B24 = 地圖單位 Q 版小人 sprite(1680 個 24×24)。

格式(同 FDSHAP tileset,但 tile 用 sprite 4-mode RLE 含透明):
  +0 u16 tileW(24)  +2 u16 tileH(24)  +4 u16 count(1680)
  +6 u32[count] offset 表(相對檔頭)
  各 tile:sprite 4-mode RLE(decode_figani.decode_rle),透明區=index 0

每角色一組連續 sprite(多方向 × 待機/走幀),即原版戰場地圖上的單位(非 FIGANI 戰鬥全身)。
輸出透明 PNG;index 0 設為透明。資產屬遊戲著作權,只在本機,不入庫。

用法:
  python3 decode_fdicon.py <FDICON.B24> <palette.bin> <out_dir> [start] [count]
  python3 decode_fdicon.py <FDICON.B24> <palette.bin> --overview <out.png> [n]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from decode_figani import decode_rle
from decode_image import load_palette
# 2026-09-08:PIL 延遲 import(容器解析不需要 Pillow;模組層 hard import 會讓
# 整支工具在沒有 Pillow 的 WSL python3 下不可用)。


class NotFDICON(Exception):
    pass


def load(path):
    d = open(path, "rb").read()
    # 2026-09-08:原本沒有任何長度檢查,餵進截斷或非 FDICON 的檔案會丟出原始的
    # `struct.error: unpack_from requires a buffer of at least N bytes`——
    # 呼叫端無法分辨「這不是 FDICON」與「這支工具有 bug」。dump_remap.parse_lmi
    # 與 decode_lmi.lmi_offsets 是同一類問題,已在同一輪一併處理。
    if len(d) < 6:
        raise NotFDICON(f"檔案只有 {len(d)} bytes,連 6-byte 檔頭都不足")
    tw, th, cnt = struct.unpack_from("<HHH", d, 0)
    if not (0 < tw <= 256 and 0 < th <= 256):
        raise NotFDICON(f"tile 尺寸不合理: {tw}x{th}")
    if cnt == 0 or 6 + cnt * 4 > len(d):
        raise NotFDICON(f"offset 表宣稱 {cnt} 筆,超出檔案大小 {len(d)}")
    offs = [struct.unpack_from("<I", d, 6 + i * 4)[0] for i in range(cnt)]
    return d, tw, th, cnt, offs


def selftest():
    """真實 FDICON.B24 + 合成容器 + 壞輸入必須丟 NotFDICON 而非原始 struct.error。

    這支的解碼核心是 `decode_figani.decode_rle`(同族 4 模式文法),所以像素層的
    正確性由那支的 selftest 負責;這裡只釘住**容器層**:檔頭、offset 表、以及
    壞輸入的失敗品質。
    """
    import tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("(1) 真實 FDICON.B24:檔頭與 offset 表必須符合已記載的形狀")
    real = os.path.join(root, "org_game", "炎龍騎士團", "FLAME2", "FDICON.B24")
    if os.path.isfile(real):
        d, tw, th, cnt, offs = load(real)
        mono = all(offs[i] <= offs[i + 1] for i in range(len(offs) - 1))
        inrange = offs[0] >= 6 + cnt * 4 and offs[-1] <= len(d)
        ok1 = (tw, th) == (24, 24) and cnt == 1680 and len(offs) == cnt and mono and inrange
        print(f"    {'PASS' if ok1 else 'FAIL'}: {tw}x{th} × {cnt} 個,"
              f"offset 單調={mono} 落在檔內={inrange}")
        if not ok1:
            fails.append(f"真實檔頭不符:{tw}x{th} cnt={cnt} mono={mono} inrange={inrange}")
    else:
        print("    SKIP: 找不到 org_game 的 FDICON.B24")

    print("\n(2) 合成容器:手算的 offset 表必須原樣讀回")
    body = b"\xC4" * 40                       # 4 個 tile 的假資料
    hdr = struct.pack("<HHH", 24, 24, 4) + b"".join(
        struct.pack("<I", 22 + i * 10) for i in range(4))
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "syn.bin")
        open(p, "wb").write(hdr + body)
        _d, tw2, th2, cnt2, offs2 = load(p)
        ok2 = (tw2, th2, cnt2) == (24, 24, 4) and offs2 == [22, 32, 42, 52]
        print(f"    {'PASS' if ok2 else 'FAIL'}: {tw2}x{th2} × {cnt2}, offs={offs2}")
        if not ok2:
            fails.append(f"合成容器讀回錯誤:{tw2}x{th2} {cnt2} {offs2}")

    print("\n(3) 壞輸入必須丟 NotFDICON(而不是原始 struct.error 或靜默解出垃圾)")
    cases = [
        ("空檔", b""),
        ("只有 5 bytes", b"\x00" * 5),
        ("tile 尺寸為 0", struct.pack("<HHH", 0, 24, 4) + b"\x00" * 16),
        ("tile 尺寸過大", struct.pack("<HHH", 9999, 24, 4) + b"\x00" * 16),
        ("count 為 0", struct.pack("<HHH", 24, 24, 0)),
        ("offset 表超出檔尾", struct.pack("<HHH", 24, 24, 9999) + b"\x00" * 8),
    ]
    with tempfile.TemporaryDirectory() as td:
        for label, blob in cases:
            p = os.path.join(td, "bad.bin")
            open(p, "wb").write(blob)
            try:
                load(p)
                print(f"    FAIL: 「{label}」沒有被擋下")
                fails.append(f"{label} 沒有被擋下")
            except NotFDICON:
                print(f"    PASS: 「{label}」-> NotFDICON")
            except Exception as exc:                          # noqa: BLE001
                print(f"    FAIL: 「{label}」丟出 {type(exc).__name__}")
                fails.append(f"{label} 丟出 {type(exc).__name__} 而非 NotFDICON")

    print("\n(4) 非恆真控制:合法容器必須通過,證明上面的守衛沒有把正常路徑也擋掉")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "ok.bin")
        open(p, "wb").write(hdr + body)
        try:
            load(p)
            ok4 = True
        except Exception:                                     # noqa: BLE001
            ok4 = False
    print(f"    {'PASS' if ok4 else 'FAIL'}: 合法合成容器通過={ok4}")
    if not ok4:
        fails.append("守衛把合法容器也擋掉了")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(真實檔頭 + 合成容器手算 + 6 種壞輸入 + 非恆真控制)。")
    return 0


def tile_img(d, tw, th, offs, i, cnt, pal):
    end = offs[i + 1] if i + 1 < cnt else len(d)
    px = decode_rle(d[offs[i]:end], tw, th, trans=0)
    from PIL import Image
    im = Image.frombytes("P", (tw, th), bytes(px))
    im.putpalette(pal)
    rgba = im.convert("RGBA")
    pix = rgba.load()
    for y in range(th):
        for x in range(tw):
            if px[y * tw + x] == 0:
                pix[x, y] = (0, 0, 0, 0)
    return rgba


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) < 4:
        print(__doc__); return 1
    path, palp = argv[1], argv[2]
    d, tw, th, cnt, offs = load(path)
    pal = load_palette(palp)

    if argv[3] == "--overview":
        out = argv[4]
        n = int(argv[5]) if len(argv) > 5 else 256
        n = min(n, cnt)
        cols = 12
        rows = (n + cols - 1) // cols
        # 注意:這個分支也直接用 Image.new / Image.NEAREST,改成延遲 import 之後
        # 必須連 Image 一起帶進來,否則會 NameError(2026-09-08 改動時漏掉一次)。
        from PIL import Image, ImageDraw
        scale = 2
        sheet = Image.new("RGB", (cols * (tw * scale + 2), rows * (th * scale + 10)), (30, 30, 40))
        dr = ImageDraw.Draw(sheet)
        for i in range(n):
            im = tile_img(d, tw, th, offs, i, cnt, pal).resize((tw * scale, th * scale), Image.NEAREST)
            x = (i % cols) * (tw * scale + 2)
            y = (i // cols) * (th * scale + 10)
            sheet.paste(im, (x, y + 9), im)
            dr.text((x, y), str(i), fill=(255, 255, 0))
        sheet.save(out)
        print(f"overview {n}/{cnt} ({tw}x{th}) -> {out}")
        return 0

    out = argv[3]
    os.makedirs(out, exist_ok=True)
    start = int(argv[4]) if len(argv) > 4 else 0
    num = int(argv[5]) if len(argv) > 5 else cnt
    for i in range(start, min(start + num, cnt)):
        tile_img(d, tw, th, offs, i, cnt, pal).save(os.path.join(out, f"icon_{i:04d}.png"))
    print(f"FDICON: {cnt} sprite {tw}x{th};導出 {min(num, cnt-start)} 個 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
