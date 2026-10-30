"""續一百七十:挑出校準集(drivers_s168/calib_frames.txt)沒涵蓋的章節的截圖,寫成 uncovered_frames.txt。

章節 = 路徑裡最後一個 chNN 的數字(同 ev_s170 的 chapter_tag);校準集出現過的章節、> 30、沒有標記的都不要。
只取 1024x768(HUD 樣板的座標以此為準),依像素 md5 去重(同一畫面留路徑排序最前的那張)。
另把每張的樣板吻合率與舊藍佔比判準寫到 .wsl_build/s170_review/hud_scan.csv(不提交),給人工判讀挑圖。
用法:python select_uncovered.py
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "tools"))
warnings.filterwarnings("ignore", category=DeprecationWarning)      # Pillow getdata 的棄用警告
import fd2_chapter_sweep as sw  # noqa: E402
from PIL import Image  # noqa: E402


def chapter_tag(p: str) -> int | None:
    m = re.findall(r"ch(\d+)", p)
    return int(m[-1]) if m else None


def main() -> int:
    calib = (HERE.parent / "drivers_s168" / "calib_frames.txt").read_text(encoding="utf-8").split()
    covered = {c for c in map(chapter_tag, calib) if c is not None}
    seen: set[str] = set()
    rows = []
    n_files = 0
    for p in sorted((REPO / ".wsl_build").rglob("*.png")):
        rel = p.relative_to(REPO).as_posix()
        ch = chapter_tag(rel)
        if ch is None or rel in calib or ch in covered or ch > 30:
            continue
        try:
            im = Image.open(p)
            if im.size != (1024, 768):
                continue
            im = im.convert("RGB")
        except OSError as e:
            print("unreadable", rel, e)                             # 讀不到的另外列出,不當成沒有 HUD
            continue
        n_files += 1
        h = hashlib.md5(im.tobytes()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        rows.append([rel, ch, round(sw._hud_frame_match(im, "L"), 4), round(sw._hud_frame_match(im, "R"), 4),
                     int(sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION, sw.BATTLE_HUD_RIGHT_STRIP_REGION)),
                     int(sw._box_and_strip_pass(im, sw.BATTLE_HUD_BOX_REGION_R, sw.BATTLE_HUD_LEFT_STRIP_REGION_R))])
    (HERE / "uncovered_frames.txt").write_text("".join(r[0] + "\n" for r in rows), encoding="utf-8", newline="\n")
    review = REPO / ".wsl_build" / "s170_review"
    review.mkdir(parents=True, exist_ok=True)
    with (review / "hud_scan.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["path", "ch", "mL", "mR", "oL", "oR"]] + rows)
    print("files", n_files, "unique", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
