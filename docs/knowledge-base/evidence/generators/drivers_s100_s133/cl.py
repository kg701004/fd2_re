# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百零八:以修補版 dosbox-x(FD2_HARNESS_CALLLOG)照既有路線錄函式呼叫紀錄(只對原版 FD2.EXE,WSL -d Ubuntu)。

用法:
  python cl.py town NAME [CH]        # 開 instance、LOAD 第 0 格(章節位元組 CH,預設 1)→ 城鎮(_TO_TOWN 路線)
  python cl.py battle NAME [CH]      # 同上再走 recon 路線到戰場(s102 的 go)
  python cl.py k NAME WAIT KEY...    # 送鍵(逐鍵)→ 等 → 截圖
  python cl.py shot NAME [tag]
  python cl.py pane NAME
  python cl.py size NAME             # CALLLOG.TXT 大小 / 行數 / 最後一行
  python cl.py md5 NAME
  python cl.py pull NAME             # 複製 CALLLOG.TXT -> fd2_re/.wsl_build/NAME_CALLLOG.TXT
  python cl.py down NAME             # teardown(工作目錄保留)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
os.environ["FD2_HARNESS_DOSBOX_BIN"] = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
os.environ["FD2_HARNESS_CALLLOG"] = "/home/kg701004/fd2-dosbox-calllog/entries.txt"
_w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
os.environ["WSLENV"] = ":".join(_w + [v for v in ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG") if v not in _w])
import fd2_chapter_sweep as sw  # noqa: E402
import fd2_original_verify as ov  # noqa: E402

OUTROOT = Path(__file__).resolve().parent / "cl"


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def shot(name: str, tag: str) -> Path:
    d = OUTROOT / name
    d.mkdir(parents=True, exist_ok=True)
    k = len(list(d.glob("*.png"))) + 1
    p = d / f"{k:03d}_{tag}.png"
    sw.screenshot(name, p)
    return p


def to_town(chapter: int) -> list[dict]:
    return [{"op": "patch_chapter", "value": chapter}, {"op": "poll_title"},
            {"op": "keys", "keys": ["Down"], "wait": 1.0}, {"op": "shot", "label": "title_menu"},
            {"op": "keys", "keys": ["Return"], "wait": 4.0}, {"op": "keys", "keys": ["Return"], "wait": 6.0},
            {"op": "shot", "label": "town"}]


def main(argv: list[str]) -> int:
    cmd, name = argv[0], (argv[1] if len(argv) > 1 else "")
    wd = f"/home/kg701004/fd2-run-harness-{name}"
    if cmd in ("town", "battle"):
        ch = int(argv[2]) if len(argv) > 2 else 1
        steps = to_town(ch)
        if cmd == "battle":
            for i, k in enumerate("Return,Escape,Right,Right,Right,Return,Return,Return,Return".split(",")):
                steps += [{"op": "keys", "keys": [k], "wait": 2.5}, {"op": "shot", "label": f"r{i:02d}_{k}"}]
        OUTROOT.mkdir(parents=True, exist_ok=True)
        r = ov.Runner({"name": name, "instance": name, "chapter": ch, "steps": steps, "keepalive": 14400},
                      OUTROOT, True).run()
        print("ok", r.ok, r.error, [(a.name, a.ok, a.detail) for a in r.assertions])
        print(wsl(f"md5sum {wd}/FD2.EXE; ls -la {wd}/CALLLOG.TXT; head -1 {wd}/CALLLOG.TXT"))
    elif cmd == "k":
        sw.send_keys(name, *argv[3:])
        time.sleep(float(argv[2]))
        print(shot(name, "_".join(argv[3:])[:40]))
    elif cmd == "rx":
        for _ in range(int(argv[2])):
            sw.send_keys(name, "Return")
            time.sleep(1.2)
            sw.send_keys(name, "Escape")
            time.sleep(1.2)
        print(shot(name, "rx"))
    elif cmd == "shot":
        print(shot(name, argv[2] if len(argv) > 2 else "s"))
    elif cmd == "pane":
        print(sw.capture_pane(name))
    elif cmd == "size":
        print(wsl(f"stat -c %s {wd}/CALLLOG.TXT; wc -l < {wd}/CALLLOG.TXT; grep -c '^E' {wd}/CALLLOG.TXT; "
                  f"tail -c 300 {wd}/CALLLOG.TXT | tail -1 | cut -c1-120"))
    elif cmd == "md5":
        print(wsl(f"md5sum {wd}/FD2.EXE"))
    elif cmd == "pull":
        dst = REPO / ".wsl_build" / f"{name}_CALLLOG.TXT"
        print(wsl(f"cp {wd}/CALLLOG.TXT {sw.to_wsl_path(dst)} && ls -la {sw.to_wsl_path(dst)} && tail -3 {wd}/CALLLOG.TXT | cut -c1-80"))
    elif cmd == "down":
        print(sw.teardown(name))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
