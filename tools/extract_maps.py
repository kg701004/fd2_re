#!/usr/bin/env python3
"""炎龍騎士團2 — 批次抽取全部戰場地圖成 PNG。

FDFIELD.DAT(解包後)每 3 個資源 = 一張地圖(構成 / 控制 / 出場);共 33 張。
構成資源:u16 W, u16 H, 然後每格 (u16 地形索引, u16 事件)。
配對:地圖 N 用 FDSHAP **解包序 2N**(doc05 §1 實測;map9 配 FDSHAP_018 即該規則)。
tileset 格式見 render_map / doc 01 §8。

用法:
    python3 extract_maps.py <raw解包根> <palette.bin> <out目錄>
       raw 解包根需含 raw/FDFIELD/ 與 raw/FDSHAP/(unpack_dat 產出)
    python3 extract_maps.py --selftest
"""
import sys
import os
import re
import glob
import struct

sys.path.insert(0, os.path.dirname(__file__))
from render_map import decode_tileset, load_palette
from PIL import Image

MAP_COUNT = 33          # FDFIELD 每 3 資源一組
FIELD_STRIDE = 3
TILESET_STRIDE = 2      # 地圖 N → FDSHAP 解包序 2N


def resource_index(path):
    """從 `FDSHAP_018.bin` 這種檔名取出解包序號;非此形狀回 None。"""
    m = re.search(r"_(\d+)\.bin$", os.path.basename(path))
    return int(m.group(1)) if m else None


def index_resources(dirpath):
    """解包序號 → 路徑。

    2026-09-09:原本是 `big = [f for f in shp if size > 2000]` 再取 `big[m]`,
    也就是用「第 m 個大檔」當地圖 m 的 tileset——但 docstring 寫的規則是「解包序
    2N」,兩個判準不同。目前碰巧一致(33 個 >2000 的檔剛好就是偶數序 0..64),
    可是只要 FDSHAP 少解包出一個檔,後面每一張圖都會整體位移配到別人的 tileset。
    實測拿掉 FDSHAP_020 後,map10 會拿 FDSHAP_022 靜默畫完,越界格數 0/1575——
    完全不報錯、圖整張錯。而且 tile 索引越界檢查本身只能抓到約 1/3 的錯配對
    (相鄰偏移實測 10~12/33),靠它兜底並不夠。改成依檔名序號查表,缺哪個資源就
    只讓那一張圖失敗,不會拖累其他圖。同類 bug:verify_dat_extraction_freshness。
    """
    out = {}
    for f in glob.glob(os.path.join(dirpath, "*.bin")):
        i = resource_index(f)
        if i is not None:
            out[i] = f
    return out


def tileset_path(shap_index, m):
    """地圖 m 的 tileset 路徑;缺資源就丟例外(而不是往後借一個)。"""
    want = m * TILESET_STRIDE
    if want not in shap_index:
        raise FileNotFoundError(
            f"map{m:02d} 需要 FDSHAP 解包序 {want}(2×{m}),但該資源不存在")
    return shap_index[want]


def field_path(field_index, m):
    want = m * FIELD_STRIDE
    if want not in field_index:
        raise FileNotFoundError(
            f"map{m:02d} 需要 FDFIELD 解包序 {want}(3×{m}),但該資源不存在")
    return field_index[want]


def read_field_header(path):
    """回傳 (w, h, raw);尺寸不合理回 (None, None, raw)。"""
    d = open(path, "rb").read()
    if len(d) < 4:
        return None, None, d
    w, h = struct.unpack_from("<HH", d, 0)
    if not (0 < w < 200 and 0 < h < 200):
        return None, None, d
    return w, h, d


def max_tile_index(d, w, h):
    return max(struct.unpack_from("<H", d, 4 + i * 4)[0] for i in range(w * h))


def render_map(field_path_, tiles, tw, th, pal, out):
    """回傳 (w, h, 越界格數);表頭不合理回 None。"""
    w, h, d = read_field_header(field_path_)
    if w is None:
        return None
    img = Image.new("P", (w * tw, h * th), 0)
    img.putpalette(pal)
    oob = 0
    for cy in range(h):
        for cx in range(w):
            ti = struct.unpack_from("<H", d, 4 + (cy * w + cx) * 4)[0]
            if ti < len(tiles):
                img.paste(Image.frombytes("P", (tw, th), tiles[ti]), (cx * tw, cy * th))
            else:
                oob += 1
    img.convert("RGB").save(out)
    return (w, h, oob)


def main(argv):
    if len(argv) > 1 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 4:
        print(__doc__)
        return 1
    raw, palp, out = argv[1], argv[2], argv[3]
    os.makedirs(out, exist_ok=True)
    pal = load_palette(palp)
    fidx = index_resources(os.path.join(raw, "FDFIELD"))
    sidx = index_resources(os.path.join(raw, "FDSHAP"))
    n = min(MAP_COUNT, (max(fidx) + 1) // FIELD_STRIDE if fidx else 0)
    done = 0
    for m in range(n):
        try:
            tw, th, tiles = decode_tileset(tileset_path(sidx, m))
            r = render_map(field_path(fidx, m), tiles, tw, th, pal,
                           os.path.join(out, f"map{m:02d}.png"))
            if r:
                w, h, oob = r
                warn = f"  **{oob} 格 tile 索引越界(可能配錯 tileset)**" if oob else ""
                print(f"map{m:02d}: {w}x{h} ({w*tw}x{h*th}px, {len(tiles)} tiles){warn}")
                done += 1
        except Exception as e:
            print(f"map{m:02d}: 失敗 {e}")
    print(f"\n完成 {done}/{n} 張地圖 -> {out}")
    return 0


RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "extracted", "raw")

# 各自獨立記錄過、且都是承重的尺寸(不是為了湊測試才量的):
#   map0  24×24  doc25 §7.6,反組譯戰場重繪鏈時用來判定「圖比視窗窄」的那張
#   map1  27×21  doc50,PAN camera origin→像素 (14,2)→(336,48) 的推導基礎
#   map9  31×45  doc05 §1,ch10 戰場資產確認,並同時實測出 2N 配對規則
#   map32 18×51  doc23,渲染成 432×1224 後逐像素對齊 dosbox 參考圖與原版錄影
DOC_ANCHORS = {0: (24, 24), 1: (27, 21), 9: (31, 45), 32: (18, 51)}
TILE_PX = 24            # doc50「原版 tile=24px」;map32 的 432×1224 亦由此得出


def selftest() -> int:
    fails = []
    fidx = index_resources(os.path.join(RAW, "FDFIELD"))
    sidx = index_resources(os.path.join(RAW, "FDSHAP"))
    if not fidx or not sidx:
        print(f"缺少 {RAW} 下的 FDFIELD/FDSHAP,無法自我驗證", file=sys.stderr)
        return 1

    print("(1) 文件錨點:4 張獨立記錄過的地圖尺寸必須逐一相符")
    for m, (ew, eh) in sorted(DOC_ANCHORS.items()):
        w, h, _ = read_field_header(field_path(fidx, m))
        ok = (w, h) == (ew, eh)
        print(f"    {'PASS' if ok else 'FAIL'}: map{m:02d} = {w}x{h}(記錄 {ew}x{eh})")
        if not ok:
            fails.append(f"map{m} 尺寸 {w}x{h} != 記錄 {ew}x{eh}")

    print("\n(2) 結構不變量:33 張的檔長必須剛好 4 + w*h*4")
    bad = []
    for m in range(MAP_COUNT):
        w, h, d = read_field_header(field_path(fidx, m))
        if w is None or len(d) != 4 + w * h * 4:
            bad.append(m)
    print(f"    {'PASS' if not bad else 'FAIL'}: 33/33 相符" if not bad
          else f"    FAIL: 不符的圖 {bad}")
    if bad:
        fails.append(f"檔長不變量不符:{bad}")

    print("\n(3) 2N 配對交叉驗證 + 非平凡性對照(相鄰偏移必須被抓到)")
    counts = {}
    for i in sidx:
        try:
            counts[i] = len(decode_tileset(sidx[i])[2])
        except Exception:
            counts[i] = None
    def pairing_failures(off):
        n = 0
        for m in range(MAP_COUNT):
            w, h, d = read_field_header(field_path(fidx, m))
            c = counts.get(m * TILESET_STRIDE + off)
            if c is None or max_tile_index(d, w, h) >= c:
                n += 1
        return n
    f0, fp2, fm2 = pairing_failures(0), pairing_failures(2), pairing_failures(-2)
    ok3 = f0 == 0 and fp2 > 0 and fm2 > 0
    print(f"    {'PASS' if ok3 else 'FAIL'}: 2N 失敗 {f0}/33、"
          f"2N+2 失敗 {fp2}/33、2N-2 失敗 {fm2}/33")
    if not ok3:
        fails.append(f"配對檢查無鑑別力或正解失敗:{f0}/{fp2}/{fm2}")

    print("\n(4) tile 幾何:所有 tileset 必須是 24×24,map32 因此是 432×1224")
    sizes = set()
    for m in range(MAP_COUNT):
        tw, th, _ = decode_tileset(tileset_path(sidx, m))
        sizes.add((tw, th))
    w32, h32, _ = read_field_header(field_path(fidx, 32))
    ok4 = sizes == {(TILE_PX, TILE_PX)} and (w32 * TILE_PX, h32 * TILE_PX) == (432, 1224)
    print(f"    {'PASS' if ok4 else 'FAIL'}: tile 尺寸集合 {sizes}、"
          f"map32 = {w32*TILE_PX}x{h32*TILE_PX}px")
    if not ok4:
        fails.append(f"tile 幾何不符:{sizes} / map32 {w32}x{h32}")

    print("\n(5) 缺檔回歸(本次修的 bug):少一個 FDSHAP 只能讓該張圖失敗,不得位移")
    hole = dict(sidx)
    hole.pop(20, None)                       # map10 的 tileset
    try:
        tileset_path(hole, 10)
        raised = False
    except FileNotFoundError:
        raised = True
    others = all(tileset_path(hole, m) == sidx[m * TILESET_STRIDE]
                 for m in (9, 11, 20, 32))
    # 舊寫法(第 m 個 >2000 的檔)在同一情況下會靜默把 FDSHAP_022 給 map10:
    big = sorted(f for f in sidx.values() if os.path.getsize(f) > 2000)
    old_big = [f for f in big if resource_index(f) != 20]
    old_would_shift = resource_index(old_big[10]) == 22
    ok5 = raised and others and old_would_shift
    print(f"    {'PASS' if ok5 else 'FAIL'}: map10 拋錯={raised}、"
          f"map9/11/20/32 仍各自正確={others}、舊寫法會位移到 FDSHAP_022={old_would_shift}")
    if not ok5:
        fails.append(f"缺檔行為不正確:{raised}/{others}/{old_would_shift}")

    print("\n(6) 負向控制:表頭不合理的構成資源必須被判為非地圖")
    import tempfile
    ok6 = True
    with tempfile.TemporaryDirectory() as td:
        for name, hdr in (("zero", b"\x00\x00\x10\x00"), ("huge", b"\x2c\x01\x10\x00")):
            p = os.path.join(td, f"X_{name}.bin")
            open(p, "wb").write(hdr + b"\x00" * 64)
            w, h, _ = read_field_header(p)
            if w is not None:
                ok6 = False
    print(f"    {'PASS' if ok6 else 'FAIL'}: w=0 與 w=300 都被拒")
    if not ok6:
        fails.append("表頭範圍檢查失效")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(4 文件錨點 + 結構不變量 + 配對交叉驗證與非平凡性對照 "
          "+ tile 幾何 + 缺檔位移回歸 + 負向控制)。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
