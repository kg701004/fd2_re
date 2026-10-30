"""續一百七十版的 HUD 邊框樣板變異(工具只看樣板):每個變異都必須讓 --selftest 印出 SELFTEST FAILED。
drivers_s169/mut_frame.py 是對續一百六十九的工具寫的,其中「樣板不優先」「拿掉退回藍佔比」兩個的目標程式碼這輪已拿掉;
這裡保留其餘 7 個,另加「加回退回藍佔比」(窮舉變異只改既有程式碼,加不回整段)。
變異版放在暫存目錄(連同 fd2save.py 等同目錄模組),不改 repo 內的檔案。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
TOOLS = Path(__file__).resolve().parents[5] / "tools"
SRC = (TOOLS / "fd2_chapter_sweep.py").read_text(encoding="utf-8")

# 等價變異(不列):`>=` 改 `>`。樣板 868 個像素,吻合率不可能恰為 0.8(0.8 × 868 = 694.4),兩者在所有輸入上相同。
MUTANTS = [
    ("門檻 0.85", "BATTLE_HUD_FRAME_MATCH_MIN = 0.8", "BATTLE_HUD_FRAME_MATCH_MIN = 0.85"),
    ("門檻 0.7", "BATTLE_HUD_FRAME_MATCH_MIN = 0.8", "BATTLE_HUD_FRAME_MATCH_MIN = 0.7"),
    ("只查左側", 'for side in ("L", "R"):\n        if _hud_frame_match', 'for side in ("L",):\n        if _hud_frame_match'),
    ("右側不加位移", '\n    dx = 0 if side == "L" else BATTLE_HUD_FRAME_DX_R', "\n    dx = 0"),   # 只對 _hud_frame_match(selftest 的 with_frame 也有同一行)
    ("不檢查尺寸", "    if im.size != (1024, 768):\n        return 0.0\n    dx", "    dx"),
    ("線段不含右端點", "        for x in range(x0, x1 + 1):\n            total += 1", "        for x in range(x0, x1):\n            total += 1"),
    ("吻合不比顏色", "hit += px[x + dx, y] == color", "hit += 1"),
    ("加回退回藍佔比", "            return side\n    return None\n",
     "            return side\n    if _box_and_strip_pass(im, BATTLE_HUD_BOX_REGION, BATTLE_HUD_RIGHT_STRIP_REGION):\n"
     "        return \"L\"\n    return None\n"),
]

killed = 0
with tempfile.TemporaryDirectory() as root:
    # 模組用 Path(__file__).parent.parent 找 docs/data/chapter_beats,暫存目錄要照同樣的結構擺
    td = Path(root) / "tools"
    td.mkdir()
    shutil.copytree(TOOLS.parent / "docs" / "data" / "chapter_beats", Path(root) / "docs" / "data" / "chapter_beats")
    for f in TOOLS.glob("*.py"):
        shutil.copy(f, td)
    for label, old, new in MUTANTS:
        n = SRC.count(old)
        if n != 1:
            print(f"BAD PATTERN ({n}x): {label}")
            continue
        (td / "fd2_chapter_sweep.py").write_text(SRC.replace(old, new), encoding="utf-8", newline="\n")
        r = subprocess.run([sys.executable, "-W", "ignore", str(td / "fd2_chapter_sweep.py"), "--selftest"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=td, timeout=300)
        out = r.stdout + r.stderr
        ok = r.returncode != 0 and "SELFTEST FAILED" in out and "Traceback" not in out
        killed += ok
        print(f"{'KILLED' if ok else 'SURVIVED'}: {label} (rc={r.returncode}{', Traceback' if 'Traceback' in out else ''})")
print(f"{killed}/{len(MUTANTS)} killed")
sys.exit(0 if killed == len(MUTANTS) else 1)
