#!/usr/bin/env python3
"""realesrgan_batch.py -- batch-run realesrgan_upscale's RRDBNet over every
PNG in one or more source directories, writing 4x results into a parallel
output directory tree. Loads the model once and reuses it across the whole
run instead of per-file (the realesrgan_upscale.py CLI reloads weights every
invocation, which would dominate runtime across thousands of small sprites).

Usage:
    python tools/realesrgan_batch.py <src_dir> <dst_dir> [--glob '*.png']
"""
import argparse
import pathlib
import sys
import time

import torch
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from realesrgan_upscale import load_model, upscale  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src_dir')
    ap.add_argument('dst_dir')
    ap.add_argument('--glob', default='*.png')
    args = ap.parse_args()

    src_dir = pathlib.Path(args.src_dir)
    dst_dir = pathlib.Path(args.dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(src_dir.glob(args.glob))
    if not files:
        print(f"no files matched {args.glob} under {src_dir}", file=sys.stderr)
        sys.exit(1)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    weights = str(pathlib.Path(__file__).parent / 'models' / 'RealESRGAN_x4plus.pth')
    print(f"device={device}, {len(files)} files, loading model...")
    model = load_model(weights, device)

    t0 = time.time()
    for i, f in enumerate(files):
        out_path = dst_dir / f.name
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
        if (i + 1) % 50 == 0 or i == len(files) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(files) - i - 1) / rate if rate > 0 else 0
            print(f"[{i+1}/{len(files)}] {elapsed:.1f}s elapsed, {rate:.2f} img/s, eta {eta:.0f}s", flush=True)

    print(f"done: {len(files)} files -> {dst_dir} in {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
