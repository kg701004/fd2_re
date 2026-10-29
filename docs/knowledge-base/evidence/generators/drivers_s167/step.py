# 存檔:原 scratchpad 驅動腳本(續一百六十七),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""lc167a 逐鍵診斷:每個按鍵後截圖,並記主機時間與 CALLLOG 尾端的 t(不進除錯器)。
用法:python step.py NAME LABEL KEY [KEY ...]   (KEY 可寫 wait:秒)"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fd2_chapter_sweep as sw  # noqa: E402
from lc167 import last_t  # noqa: E402

name, label, keys = sys.argv[1], sys.argv[2], sys.argv[3:]
wd = f"/home/kg701004/fd2-run-harness-{name}"
d = HERE / "cl" / name / "steps"
d.mkdir(parents=True, exist_ok=True)
logp = d / "steps.jsonl"
for i, k in enumerate(keys):
    if k.startswith("wait:"):
        time.sleep(float(k[5:]))
    else:
        sw.send_keys(name, k)
        time.sleep(0.8)
    h, t = last_t(wd)
    shot = d / f"{label}_{i:02d}_{k.replace(':', '')}.png"
    sw.screenshot(name, shot)
    rec = {"label": label, "i": i, "key": k, "host": h, "t": t, "shot": shot.name}
    with logp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(rec)
