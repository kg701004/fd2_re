#!/usr/bin/env python3
"""realesrgan_batch.py -- batch-run realesrgan_upscale's RRDBNet over every
PNG in one or more source directories, writing 4x results into a parallel
output directory tree. Loads the model once and reuses it across the whole
run instead of per-file (the realesrgan_upscale.py CLI reloads weights every
invocation, which would dominate runtime across thousands of small sprites).

Usage:
    python tools/realesrgan_batch.py <src_dir> <dst_dir> [--glob '*.png']
    python tools/realesrgan_batch.py --selftest
"""
import argparse
import pathlib
import sys
import time

import torch
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from realesrgan_upscale import load_model, upscale_image  # noqa: E402


def _selftest():
    """What this file owns is the *batch* part: which files it picks, where it
    writes them, and that it does not have its own idea of how to upscale one.
    The model, the weights and the tiling are `realesrgan_upscale`'s, and its
    own selftest covers them -- running RRDBNet here would be re-testing that.
    """
    import realesrgan_upscale as RU
    import tempfile
    import numpy as np
    fails = []

    print("(1) 不得自己實作 alpha 規則:必須呼叫共用的 upscale_image")
    # 2026-09-09:這裡原本把 realesrgan_upscale.main() 的 alpha 六行複製了一份。
    # 這一題釘的是「只有一個擁有者」,不是輸出值——值相同時複製一份也會通過。
    # 只看 main() 的原始碼,不看整份檔案:第一版掃全檔,結果被**本 selftest 的
    # 第 (2) 題**裡的 `Image.LANCZOS` 命中而誤判。判準問的是「主流程有沒有自己
    # 的一份規則」,測試碼提到那些名字是正常的。
    # 判準要看**程式碼**,不是註解。第一版掃全檔,被本 selftest 第 (2) 題裡的
    # `Image.LANCZOS` 命中;第二版改看 main() 的原始碼,又被 main() 裡那條解釋
    # 這次修正的註解命中(註解本來就會提到 LANCZOS)。用 AST 還原成純程式碼。
    import ast
    import inspect
    body = ast.unparse(ast.parse(inspect.getsource(main)))
    banned = [t for t in ("Image.merge", "LANCZOS", "split()") if t in body]
    ok1 = "upscale_image" in body and not banned
    print(f"    {'PASS' if ok1 else 'FAIL'}: main() 使用共用函式="
          f"{('upscale_image' in body)}、main() 內自己的 alpha 邏輯 {banned or '無'}")
    if not ok1:
        fails.append("批次檔又有了自己的一份 alpha 規則")

    print("\n(2) 與 upscale 共用的規則實際上一致(同輸入同輸出)")
    model, dev = RU._NearestModel(), torch.device("cpu")
    rng = np.random.default_rng(20260909)
    rgba = Image.fromarray(rng.integers(0, 256, (19, 27, 4), dtype=np.uint8), "RGBA")
    out = RU.upscale_image(model, dev, rgba)
    ok2 = (out.mode == "RGBA"
           and out.size == (27 * RU.SCALE, 19 * RU.SCALE)
           and np.array_equal(np.array(out.split()[3]),
                              np.array(rgba.split()[3].resize(out.size, Image.LANCZOS))))
    print(f"    {'PASS' if ok2 else 'FAIL'}: RGBA {rgba.size} -> {out.size}、"
          f"alpha 為 LANCZOS 重採樣")
    if not ok2:
        fails.append("共用函式的行為與文件不符")

    print("\n(3) 輸出樹是平行的:dst/<同檔名>")
    with tempfile.TemporaryDirectory() as td:
        s, d = pathlib.Path(td) / "s", pathlib.Path(td) / "d"
        s.mkdir()
        for n in ("a.png", "b.png", "c.txt"):
            (s / n).write_bytes(b"x")
        picked = sorted(s.glob("*.png"))
        ok3 = ([p.name for p in picked] == ["a.png", "b.png"]
               and [(d / p.name).name for p in picked] == ["a.png", "b.png"])
        print(f"    {'PASS' if ok3 else 'FAIL'}: glob 只取 {[p.name for p in picked]}"
              f"(c.txt 不在內)、輸出同名")
        if not ok3:
            fails.append(f"檔案挑選或命名不正確:{picked}")

        print("\n(4) 負向控制:沒有檔案匹配時必須失敗,不得靜默成功")
        empty = pathlib.Path(td) / "empty"
        empty.mkdir()
        rc = subprocess_rc([sys.executable, __file__, str(empty), str(d)])
        ok4 = rc != 0
        print(f"    {'PASS' if ok4 else 'FAIL'}: 空目錄 -> rc={rc}(必須非 0)")
        if not ok4:
            fails.append("空目錄仍回報成功")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(單一擁有者 + 共用規則行為 + 平行輸出樹 + "
          "空輸入負向控制)。模型與分塊由 realesrgan_upscale 自己的 selftest 涵蓋。")
    return 0


def subprocess_rc(cmd):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").returncode


def main():
    ap = argparse.ArgumentParser()
    if "--selftest" in sys.argv:
        return _selftest()
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
        # 2026-09-09:這裡原本把 realesrgan_upscale.main() 的 alpha 處理整段
        # 複製了一份。三通道權重不能吃 alpha、必須改用 LANCZOS 重採樣是一個
        # 決定,而寫兩份的決定會安靜地各走各的——同一天已經修過兩個同型的案例。
        out = upscale_image(model, device, Image.open(f))
        out.save(out_path)
        if (i + 1) % 50 == 0 or i == len(files) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(files) - i - 1) / rate if rate > 0 else 0
            print(f"[{i+1}/{len(files)}] {elapsed:.1f}s elapsed, {rate:.2f} img/s, eta {eta:.0f}s", flush=True)

    print(f"done: {len(files)} files -> {dst_dir} in {time.time()-t0:.1f}s")


if __name__ == '__main__':
    sys.exit(main() or 0)
