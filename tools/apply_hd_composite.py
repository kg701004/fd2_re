#!/usr/bin/env python3
"""apply_hd_composite.py -- wire the Real-ESRGAN-upscaled whole-map composite
images (remake/assets/maps_native_composite_hd/mapN.png) into the live path
the Go loader actually reads (remake/assets/maps/mapN/map_composite.png).

This exists because per-tile upscaling (apply_hd_assets.py) upscales each
tile in isolation on the tileset sheet, which produces visible seams where
identical tiles repeat adjacently on the real map -- the model has no way to
know what will end up next to what. Compositing each map into one whole
image first (cmd/compose-map-image) and upscaling THAT instead gives the
model true tile-to-tile adjacency, so cmd/fd2's Draw() can draw one image
per frame instead of a tile grid, with no seam possible.

map_composite.png is optional -- loadMap()/loadMapComposite() fall back to
the existing tile-grid renderer for any map that doesn't have one, so this
script only needs to cover maps that were actually run through
cmd/compose-map-image + tools/realesrgan_batch.py.

Live asset trees are gitignored (player-derived, not checked in), so this
only touches local working files.

> **2026-09-03 全工具驗證:本工具目前無作用對象。** 它讀寫的
> `remake/assets/maps_native_composite_hd/` 與 `remake/assets/maps/` 已隨 `remake/`
> 移除(2026-09-02)。無參數執行會安靜地 exit 0(glob 到 0 個檔),不是成功。
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent.parent / 'remake' / 'assets'
MAPS = ROOT / 'maps'
COMPOSITE_HD = ROOT / 'maps_native_composite_hd'


def main():
    n = 0
    for hd_file in sorted(COMPOSITE_HD.glob('map*.png')):
        live_dir = MAPS / hd_file.stem
        if not live_dir.is_dir():
            print(f"skip {hd_file.name}: no live map dir {live_dir}")
            continue
        shutil.copy2(hd_file, live_dir / 'map_composite.png')
        print(f"{hd_file.stem}: map_composite.png installed")
        n += 1
    print(f"maps: {n} composites installed")

    # remake/assets/map_composite.png is the flat MVP-fallback default's
    # counterpart to the flat tileset.png/map.json fix in
    # apply_hd_assets.py -- g.loadMap("assets") is called unconditionally at
    # startup before any campaign node picks a real per-map directory, and
    # that flat location is map0's content (confirmed byte-identical
    # tileset.png earlier), so it gets map0's composite too.
    flat = ROOT / 'map_composite.png'
    map0_hd = COMPOSITE_HD / 'map0.png'
    if map0_hd.exists():
        shutil.copy2(map0_hd, flat)
        print("assets/map_composite.png (flat MVP-fallback default) -> map0 composite")


if __name__ == '__main__':
    main()
