# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百一十四:帶 DOS 環境變數(FD2_HARNESS_DOS_SET)開 instance 到標題畫面為止(只對原版 FD2.EXE)。

用法: python cl_title.py NAME "AIL_DEBUG=AILDBG.TXT"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
os.environ["FD2_HARNESS_DOSBOX_BIN"] = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
os.environ["FD2_HARNESS_CALLLOG"] = "/home/kg701004/fd2-dosbox-calllog/entries.txt"
os.environ["FD2_HARNESS_DOS_SET"] = sys.argv[2]
_w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
os.environ["WSLENV"] = ":".join(_w + [v for v in ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_DOS_SET")
                                      if v not in _w])
import fd2_original_verify as ov  # noqa: E402

OUTROOT = Path(__file__).resolve().parent / "cl"
name = sys.argv[1]
steps = [{"op": "patch_chapter", "value": 1}, {"op": "poll_title"}, {"op": "shot", "label": "title"}]
r = ov.Runner({"name": name, "instance": name, "chapter": 1, "steps": steps, "keepalive": 14400}, OUTROOT, True).run()
print("ok", r.ok, r.error, [(a.name, a.ok, a.detail) for a in r.assertions])
