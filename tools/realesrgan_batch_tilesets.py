#!/usr/bin/env python3
"""realesrgan_batch_tilesets.py -- upscale every map<N>/tileset.png under
remake/assets/maps into remake/assets/maps_hd/map<N>/tileset.png (parallel
tree, keeps the original assets untouched so the Go side can be switched
over deliberately rather than silently).
"""
import pathlib
import sys
import time

import torch
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from realesrgan_upscale import load_model, upscale  # noqa: E402

MAPS_DIR = pathlib.Path(__file__).parent.parent / 'remake' / 'assets' / 'maps'
OUT_DIR = pathlib.Path(__file__).parent.parent / 'remake' / 'assets' / 'maps_hd'


def main():
    tilesets = sorted(MAPS_DIR.glob('map*/tileset.png'), key=lambda p: p.parent.name)
    if not tilesets:
        print(f"no tileset.png found under {MAPS_DIR}", file=sys.stderr)
        sys.exit(1)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    weights = str(pathlib.Path(__file__).parent / 'models' / 'RealESRGAN_x4plus.pth')
    print(f"device={device}, {len(tilesets)} tilesets, loading model...")
    model = load_model(weights, device)

    t0 = time.time()
    for i, f in enumerate(tilesets):
        out_dir = OUT_DIR / f.parent.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'tileset.png'
        src = Image.open(f)
        has_alpha = src.mode == 'RGBA'
        rgb = src.convert('RGB')
        out_rgb = upscale(model, device, rgb)
        if has_alpha:
            alpha = src.split()[3]
            out_alpha = alpha.resize(out_rgb.size, Image.LANCZOS)
            out = Image.merge('RGBA', (*out_rgb.split(), out_alpha))
        else:
            out = out_rgb
        out.save(out_path)
        print(f"[{i+1}/{len(tilesets)}] {f.parent.name}: {src.size} -> {out.size}", flush=True)

    print(f"done: {len(tilesets)} tilesets in {time.time()-t0:.1f}s -> {OUT_DIR}")


if __name__ == '__main__':
    main()
