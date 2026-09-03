#!/usr/bin/env python3
"""apply_hd_assets.py -- wire the Real-ESRGAN 4x-upscaled tile/sprite assets
(remake/assets/maps_hd, remake/assets/sprites_hd) into the live asset paths
the Go loader actually reads (remake/assets/maps/map<N>/tileset.png,
remake/assets/sprites/). Originals are preserved alongside with a .orig4x
suffix so this is reversible without re-running the upscaler.

map.json's tileW/tileH are DELIBERATELY left untouched: that field is also
read by the native indexed rendering pipeline, which hard-requires the
original 24px native tile size (see cmd/fd2/main.go's loadMap/
tileCellScaleFor and hasHDNativeTerrain) -- the Go loader detects the
upscaled tileset.png by comparing its real pixel size against
cols*tileW at load time instead, so no JSON edit is needed or wanted here.

Both live asset trees are gitignored (player-derived, not checked in), so
this only touches local working files.

> **2026-09-03 全工具驗證:本工具目前無作用對象。** 它寫入的 `remake/assets/sprites`
> 已隨 `remake/` 移除(2026-09-02)。fd2_re 的 HD 素材流程(Real-ESRGAN)本身仍有效,
> 但沒有 remake 端可以套用。
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent.parent / 'remake' / 'assets'
MAPS = ROOT / 'maps'
MAPS_HD = ROOT / 'maps_hd'
SPRITES = ROOT / 'sprites'
SPRITES_HD = ROOT / 'sprites_hd'


def apply_maps():
    n = 0
    for hd_dir in sorted(MAPS_HD.glob('map*')):
        live_dir = MAPS / hd_dir.name
        tileset = live_dir / 'tileset.png'
        tileset_hd = hd_dir / 'tileset.png'
        if not tileset.exists():
            print(f"skip {hd_dir.name}: missing tileset.png in {live_dir}")
            continue
        backup = live_dir / 'tileset.png.orig4x'
        if not backup.exists():
            shutil.copy2(tileset, backup)
        shutil.copy2(tileset_hd, tileset)
        print(f"{hd_dir.name}: tileset.png -> HD (map.json untouched)")
        n += 1
    print(f"maps: {n} updated")

    # remake/assets/tileset.png is a SEPARATE, legacy flat-file duplicate of
    # map0's tileset.png -- byte-identical to map0's pre-upscale original --
    # used as the hardcoded MVP-fallback default (cmd/fd2/main.go's
    # loadGame() calls g.loadMap("assets") unconditionally at startup, before
    # any campaign node has picked a real per-map directory). It is easy to
    # miss because it lives outside remake/assets/maps/ entirely; without
    # this, the HD upscale would be invisible in ordinary play despite every
    # per-map tileset.png being correctly swapped (caught by live screenshot
    # verification, not by any unit test -- see PR discussion).
    flat = ROOT / 'tileset.png'
    map0_hd = MAPS_HD / 'map0' / 'tileset.png'
    if flat.exists() and map0_hd.exists():
        flat_backup = ROOT / 'tileset.png.orig4x'
        if not flat_backup.exists():
            shutil.copy2(flat, flat_backup)
        shutil.copy2(map0_hd, flat)
        print("assets/tileset.png (flat MVP-fallback default) -> HD")

    # assets/map.json (same flat-fallback location) turned out to be a STALE,
    # incomplete duplicate of maps/map0/map.json -- missing
    # native_terrain_control and several other native-pipeline fields
    # entirely (confirmed identical on every field they DO share). That
    # staleness silently makes native indexed presentation fail for this one
    # location ("editable field does not match native FDSHAP controls"),
    # regardless of any tileset.png swap -- caught only by live-testing an
    # actual battle through this exact fallback path, not by any unit test.
    # Replacing it with the complete map0 copy fixes a real pre-existing gap,
    # not just something this HD-asset pass introduced.
    flat_json = ROOT / 'map.json'
    map0_json = MAPS / 'map0' / 'map.json'
    if flat_json.exists() and map0_json.exists():
        flat_json_backup = ROOT / 'map.json.orig4x'
        if not flat_json_backup.exists():
            shutil.copy2(flat_json, flat_json_backup)
        shutil.copy2(map0_json, flat_json)
        print("assets/map.json (flat MVP-fallback default) -> complete map0 copy (was stale/incomplete)")


def apply_sprites():
    backup_dir = ROOT / 'sprites_orig4x'
    if not backup_dir.exists():
        shutil.copytree(SPRITES, backup_dir)
        print(f"sprites backed up -> {backup_dir}")
    n = 0
    for f in sorted(SPRITES_HD.glob('*.png')):
        shutil.copy2(f, SPRITES / f.name)
        n += 1
    print(f"sprites: {n} replaced with 4x versions")


if __name__ == '__main__':
    apply_maps()
    apply_sprites()
