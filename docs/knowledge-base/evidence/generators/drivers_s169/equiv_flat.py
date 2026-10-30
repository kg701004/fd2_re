"""`_flat_blue_fraction` 的 `counts.get(p, 0) + 1` int 1->2 突變是否等價(續一百六十九 --exhaustive 補跑)。

突變版 = 每色計數 ×2:最多色(含平手時 dict 插入順序的先後)不變,比例 2n / 2s 與 n / s 是同一個有理數,
int 真除法正確捨入,所以應逐位相同。這裡在 827 張校準截圖(drivers_s168/calib_frames.txt)的兩條帶上實測;
對照組是突變 0->1(每色 +1),它必須在同一批資料上看得出差異,否則這份比對本身沒有鑑別力。

截圖在 .wsl_build/(不提交);缺檔會算進 missing。用法:python equiv_flat.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "tools"))
import fd2_chapter_sweep as m  # noqa: E402
from PIL import Image  # noqa: E402


def flat_with_start(im, region: tuple[int, int, int, int], start: int, step: int) -> float:
    """`_flat_blue_fraction` 的同構版本,計數改為 counts.get(p, start) + step。"""
    counts: dict[tuple[int, int, int], int] = {}
    for p in im.crop(region).getdata():
        counts[p] = counts.get(p, start) + step
    color, n = max(counts.items(), key=lambda kv: kv[1])
    return n / sum(counts.values()) if m._is_hud_blue(color) else 0.0


def main() -> int:
    frames = (REPO / "docs/knowledge-base/evidence/generators/drivers_s168/calib_frames.txt").read_text(
        encoding="utf-8").split()
    bands = missing = nonzero = differ = control = 0
    for rel in frames:
        f = REPO / rel
        if not f.exists():
            missing += 1
            continue
        im = Image.open(f).convert("RGB")
        for band in m.DIALOGUE_PANEL_BANDS:
            a = m._flat_blue_fraction(im, band)
            bands += 1
            nonzero += a != 0.0
            differ += a != flat_with_start(im, band, 0, 2)      # 受測突變 1->2
            control += a != flat_with_start(im, band, 1, 1)     # 對照突變 0->1
    print(f"frames={len(frames)} missing={missing} bands={bands} nonzero={nonzero} "
          f"differ(1->2)={differ} control_differ(0->1)={control}")
    ok = missing == 0 and nonzero > 0 and differ == 0 and control > 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
