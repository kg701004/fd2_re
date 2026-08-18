#!/usr/bin/env python3
"""realesrgan_upscale.py -- minimal, dependency-free (beyond torch+pillow)
Real-ESRGAN x4plus inference, used because the official `realesrgan`/`basicsr`
PyPI packages fail to install on this machine's Python 3.13 (their setup.py
has a known-broken get_version() that raises KeyError under modern
setuptools/Python). This reimplements just the RRDBNet generator
architecture (public, documented in the official repo's
basicsr/archs/rrdbnet_arch.py) and loads the official pretrained
RealESRGAN_x4plus.pth weights directly with torch.

Usage:
    python tools/realesrgan_upscale.py <input.png> <output.png>

RGB is upscaled through the network; alpha (if present) is upscaled
separately via high-quality Lanczos resampling since the pretrained weights
are 3-channel only.
"""
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
import numpy as np


class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat=64, num_grow_ch=32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat, num_grow_ch=32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x):
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32):
        super().__init__()
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode='nearest')))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode='nearest')))
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        return out


def load_model(weights_path, device):
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32)
    state = torch.load(weights_path, map_location=device)
    state = state.get('params_ema', state.get('params', state))
    model.load_state_dict(state)
    model.eval()
    model.to(device)
    return model


SCALE = 4
# Max input-tile edge (pre-upscale pixels) that comfortably avoids CUDA OOM
# on consumer GPUs for this network. RRDBNet's activation memory scales with
# input area, so large composite images (up to 1200x1536px) must be split
# into tiles small enough to fit; individual tileset sheets (<=432x1224)
# never needed this and continue to run in a single pass since a tile size
# larger than the whole image degenerates to exactly that.
TILE = 400
# Overlap (pre-upscale pixels) of extra context pulled in from neighboring
# pixels around each tile before upscaling, then cropped back off after --
# gives the network real adjacent content at tile edges instead of a hard
# border, so the stitched output has no visible tile-boundary seam (the
# ironic failure mode this whole compositing effort exists to avoid).
TILE_OVERLAP = 16


def _run_tile(model, device, arr_tile):
    t = torch.from_numpy(arr_tile).permute(2, 0, 1).unsqueeze(0).to(device)
    with torch.no_grad():
        out = model(t)
    return out.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()


def upscale(model, device, img_rgb):
    arr = np.array(img_rgb).astype(np.float32) / 255.0
    h, w = arr.shape[:2]

    if h <= TILE and w <= TILE:
        out = _run_tile(model, device, arr)
        return Image.fromarray((out * 255.0).round().astype(np.uint8))

    out = np.zeros((h * SCALE, w * SCALE, 3), dtype=np.float32)
    y = 0
    while y < h:
        tile_h = min(TILE, h - y)
        x = 0
        while x < w:
            tile_w = min(TILE, w - x)
            pad_y0 = min(TILE_OVERLAP, y)
            pad_x0 = min(TILE_OVERLAP, x)
            pad_y1 = min(TILE_OVERLAP, h - (y + tile_h))
            pad_x1 = min(TILE_OVERLAP, w - (x + tile_w))

            src = arr[y - pad_y0:y + tile_h + pad_y1, x - pad_x0:x + tile_w + pad_x1]
            res = _run_tile(model, device, src)

            crop_top = pad_y0 * SCALE
            crop_left = pad_x0 * SCALE
            res = res[crop_top:crop_top + tile_h * SCALE, crop_left:crop_left + tile_w * SCALE]

            out[y * SCALE:(y + tile_h) * SCALE, x * SCALE:(x + tile_w) * SCALE] = res
            x += tile_w
        y += tile_h

    return Image.fromarray((out * 255.0).round().astype(np.uint8))


def main():
    if len(sys.argv) != 3:
        print("usage: realesrgan_upscale.py <input.png> <output.png>", file=sys.stderr)
        sys.exit(1)
    src_path, dst_path = sys.argv[1], sys.argv[2]

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"device={device}")
    weights = __file__.rsplit('/', 1)[0].rsplit('\\', 1)[0] + '/models/RealESRGAN_x4plus.pth'
    model = load_model(weights, device)

    src = Image.open(src_path)
    has_alpha = src.mode == 'RGBA'
    rgb = src.convert('RGB')
    print(f"input: {src_path} {src.size} mode={src.mode}")

    out_rgb = upscale(model, device, rgb)

    if has_alpha:
        alpha = src.split()[3]
        out_alpha = alpha.resize(out_rgb.size, Image.LANCZOS)
        out = Image.merge('RGBA', (*out_rgb.split(), out_alpha))
    else:
        out = out_rgb

    out.save(dst_path)
    print(f"output: {dst_path} {out.size}")


if __name__ == '__main__':
    main()
