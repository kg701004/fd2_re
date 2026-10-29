# 存檔:原 scratchpad 驅動腳本(續一百六十八),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""離線掃描歷史 hudcheck 截圖:對話框藍色比例的分佈(校準 screen_shows_dialogue_panel 用)。"""
from __future__ import annotations

import json
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
import fd2_chapter_sweep as sw  # noqa: E402
from PIL import Image  # noqa: E402

ROOTS = [Path(r"C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build"),
         Path(sys.argv[1])]
TOP = (360, 215, 640, 370)
BOT = (360, 430, 640, 585)


def frac(im: Image.Image, r: tuple[int, int, int, int]) -> float:
    px = list(im.crop(r).getdata())
    return sum(1 for p in px if sw._is_hud_blue(p)) / len(px)


seqs: dict[str, list[tuple[int, Path]]] = defaultdict(list)
for root in ROOTS:
    for f in root.rglob("hudcheck_*.png"):
        m = re.match(r"(hudcheck_.+?)(?:_clear(\d+))?$", f.stem)
        if not m:
            continue
        k = str(f.parent / m.group(1))
        seqs[k].append((-1 if m.group(2) is None else int(m.group(2)), f))
rows = []
for k, lst in seqs.items():
    lst.sort()
    for i, (n, f) in enumerate(lst):
        try:
            im = Image.open(f).convert("RGB")
        except Exception as e:  # noqa: BLE001
            rows.append({"seq": k, "n": n, "f": str(f), "err": repr(e)})
            continue
        if im.size != (1024, 768):
            rows.append({"seq": k, "n": n, "f": str(f), "err": f"size {im.size}"})
            continue
        rows.append({"seq": k, "n": n, "f": str(f), "hud": sw.screen_shows_battle_hud(f),
                     "top": round(frac(im, TOP), 3), "bot": round(frac(im, BOT), 3)})
out = Path(__file__).with_name("scan_frames.json")
out.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
ok = [r for r in rows if "err" not in r]
print("frames", len(rows), "ok", len(ok), "seqs", len(seqs))
hud = [r for r in ok if r["hud"]]
print("HUD frames", len(hud), "max band among HUD frames", max(max(r["top"], r["bot"]) for r in hud))
# HUD 出現前最後一張(同一序列)
pre = []
for k in seqs:
    s = [r for r in ok if r["seq"] == k]
    for a, b in zip(s, s[1:]):
        if b["hud"] and not a["hud"]:
            pre.append(a)
print("pre-HUD frames", len(pre))
for r in pre:
    print(round(max(r["top"], r["bot"]), 3), r["f"][-90:])
