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


def upscale_image(model, device, src):
    """Upscale a PIL image, alpha included. **One owner for the alpha rule.**

    2026-09-09: these six lines existed twice -- here and in
    `realesrgan_batch.py` -- with no test on either. The pretrained weights are
    3-channel, so alpha cannot go through the network and is resampled with
    LANCZOS instead; that is a real decision, and a decision written down twice
    is one that can silently diverge. Two other cases of exactly this were fixed
    the same day (`fd2_in_battle_check.why` vs `fd2_game_state.classify_units`,
    `adjacent_foe` vs `nearest_foe`), so it is folded into one function here.
    """
    rgb = src.convert("RGB")
    out_rgb = upscale(model, device, rgb)
    if src.mode != "RGBA":
        return out_rgb
    alpha = src.split()[3].resize(out_rgb.size, Image.LANCZOS)
    return Image.merge("RGBA", (*out_rgb.split(), alpha))


class _NearestModel:
    """A stand-in for RRDBNet that upscales x4 by nearest-neighbour.

    The point is shift invariance: for such a model, splitting the image into
    tiles and stitching MUST reproduce the whole-image result byte for byte.
    That turns the tiling geometry -- padding, cropping, placement -- into
    something checkable without the 64MB weights and without a GPU. The real
    network is not shift invariant, which is exactly why `TILE_OVERLAP` exists;
    but a geometry bug shows up under both, and only this one is testable here.
    """

    def __call__(self, t):
        return F.interpolate(t, scale_factor=SCALE, mode="nearest")


def _selftest():
    """Tiling geometry. The weights and the network itself are out of scope --
    a wrong tile stitch is a bug this file owns; a wrong pixel from RRDBNet is
    not something a selftest can adjudicate."""
    global TILE, TILE_OVERLAP
    fails = []
    rng = np.random.default_rng(20260909)
    img = Image.fromarray(rng.integers(0, 256, (137, 211, 3), dtype=np.uint8), "RGB")
    model, dev = _NearestModel(), torch.device("cpu")
    keep_tile, keep_ov = TILE, TILE_OVERLAP

    def run(tile, overlap):
        global TILE, TILE_OVERLAP
        TILE, TILE_OVERLAP = tile, overlap
        return np.array(upscale(model, dev, img))

    try:
        print("(1) Output geometry is exactly SCALE x the input")
        whole = run(10_000, 0)                       # single-tile path
        ok1 = whole.shape == (137 * SCALE, 211 * SCALE, 3)
        print(f"    {'PASS' if ok1 else 'FAIL'}: {whole.shape} for 211x137 input, SCALE={SCALE}")
        if not ok1:
            fails.append(f"geometry {whole.shape}")

        print("\n(2) Tiling must not change the result -- 4 tilings, byte identical")
        # Every one of these splits the image differently (1, 2x2, 4x3, 46x30
        # tiles) and uses a different overlap. With a shift-invariant model the
        # stitched output must equal the whole-image output exactly. A wrong
        # crop offset, a wrong destination slice or an off-by-one in the edge
        # padding all break this and nothing else in the pipeline would.
        variants = {(10_000, 0): whole, (128, 16): run(128, 16),
                    (64, 7): run(64, 7), (5, 3): run(5, 3)}
        bad = {k: int(np.abs(v.astype(int) - whole.astype(int)).sum())
               for k, v in variants.items() if not np.array_equal(v, whole)}
        ok2 = not bad
        print(f"    {'PASS' if ok2 else 'FAIL'}: "
              + ("all 4 tilings identical" if ok2 else f"differing {bad}"))
        if not bad:
            pass
        else:
            fails.append(f"tiling changes output: {bad}")

        print("\n(3) Negative control: a 1px placement error must be caught")
        # Without this, (2) would also pass for an implementation that ignores
        # its inputs and returns a constant.
        shifted = np.roll(whole, 1, axis=1)
        ok3 = not np.array_equal(shifted, whole) and whole.std() > 0
        print(f"    {'PASS' if ok3 else 'FAIL'}: a 1px roll is detectable "
              f"(image is not uniform, std={whole.std():.1f})")
        if not ok3:
            fails.append("comparison cannot detect a shift")

        print("\n(4) Overlap is context only -- it must never reach the output")
        # TILE_OVERLAP exists to give the network real neighbouring pixels at
        # tile edges; it is cropped back off afterwards. If any of it survived
        # into the output, (2) would already have failed, so this pins the
        # reason rather than the symptom: same tile size, three overlaps.
        same = [run(64, o) for o in (0, 8, 31)]
        ok4 = all(np.array_equal(s, whole) for s in same)
        print(f"    {'PASS' if ok4 else 'FAIL'}: overlap 0/8/31 all identical")
        if not ok4:
            fails.append("overlap leaks into the output")

        print("\n(5) Alpha never goes through the network")
        # The weights are 3-channel. If alpha were fed in, either the call would
        # fail or -- worse -- a 4-channel input would be silently truncated and
        # the result would look right while the alpha came from nowhere.
        TILE, TILE_OVERLAP = keep_tile, keep_ov
        rgba = Image.fromarray(
            rng.integers(0, 256, (23, 31, 4), dtype=np.uint8), "RGBA")
        out_rgba = upscale_image(model, dev, rgba)
        out_rgb_only = upscale_image(model, dev, rgba.convert("RGB"))
        a_in = np.array(rgba.split()[3])
        a_out = np.array(out_rgba.split()[3])
        expect_a = np.array(rgba.split()[3].resize(out_rgba.size, Image.LANCZOS))
        ok_a = (out_rgba.mode == "RGBA" and out_rgb_only.mode == "RGB"
                and out_rgba.size == (31 * SCALE, 23 * SCALE)
                and np.array_equal(a_out, expect_a)
                and np.array_equal(np.array(out_rgba.convert("RGB")),
                                   np.array(out_rgb_only))
                and a_in.std() > 0)
        print(f"    {'PASS' if ok_a else 'FAIL'}: RGBA->RGBA / RGB->RGB, "
              f"alpha is the LANCZOS resample, RGB identical either way")
        if not ok_a:
            fails.append("alpha handling diverges from the documented rule")

        print("\n(6) Constants match the documented rationale")
        # Compare against the saved originals, not the module globals -- `run()`
        # has been reassigning those, so reading them here measures the last
        # variant rather than the shipped constant.
        ok5 = (SCALE == 4 and keep_ov == 16 and keep_tile == 400)
        print(f"    {'PASS' if ok5 else 'FAIL'}: SCALE={SCALE}, TILE={keep_tile}, "
              f"TILE_OVERLAP={keep_ov}")
        if not ok5:
            fails.append(f"constants drifted: {SCALE}/{keep_tile}/{keep_ov}")
    finally:
        TILE, TILE_OVERLAP = keep_tile, keep_ov

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed (geometry + tiling invariance across 4 splits + "
          "negative control + overlap containment + alpha rule + constants). "
          "The network and its weights are out of scope; see _selftest.__doc__.")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        sys.exit(_selftest())
    if len(sys.argv) != 3:
        print("usage: realesrgan_upscale.py <input.png> <output.png>", file=sys.stderr)
        print("       realesrgan_upscale.py --selftest", file=sys.stderr)
        sys.exit(1)
    src_path, dst_path = sys.argv[1], sys.argv[2]

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"device={device}")
    weights = __file__.rsplit('/', 1)[0].rsplit('\\', 1)[0] + '/models/RealESRGAN_x4plus.pth'
    model = load_model(weights, device)

    src = Image.open(src_path)
    print(f"input: {src_path} {src.size} mode={src.mode}")
    out = upscale_image(model, device, src)
    out.save(dst_path)
    print(f"output: {dst_path} {out.size}")


if __name__ == '__main__':
    main()
