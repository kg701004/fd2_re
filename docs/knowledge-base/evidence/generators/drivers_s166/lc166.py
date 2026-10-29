# 存檔:原 scratchpad 驅動腳本(續一百六十六),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百六十六 戰場實機(使用者 2026-10-29「核准戰場跑實機的部分」,核准一次):第 1 章戰場閒置時的計時中斷呼叫紀錄。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(patch_chapter)。預測見 pred166_battle.txt。

用法:
  python lc166.py entries
  python lc166.py run NAME        # 開 instance → 第 1 章 → 進戰場(續一百零八 cl.py battle 的按鍵)→ 閒置 30 秒 → 截圖(instance 保留)
  python lc166.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc166_live/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
HERE = Path(__file__).resolve().parent
OD = REPO / ".wsl_build" / "lc166_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s166"
ENTRY_FILE = f"{ENTRY_DIR}/entries_battle.txt"
DELTA = 0x19C000
NATIVE = [0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x37C30, 0x3DFEF, 0x25BF4, 0x25C01,
          0x1F894, 0x1FC66, 0x1FD7C, 0x370F0, 0x1FE63, 0x1FED3, 0x1FEF0, 0x1FF31, 0x1FF36, 0x3E01D, 0x32326,
          0x11CAC]                     # 最後一個:redraw,戰場時段標記
IDLE_S = 30.0


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "entries":
        body = " ".join(f"{a + DELTA:x}" for a in sorted(NATIVE))
        print(wsl(f"mkdir -p {ENTRY_DIR} && printf '%s\\n' '{body}' > {ENTRY_FILE} && cat {ENTRY_FILE}"))
        return 0
    name = argv[1]
    wd = f"/home/kg701004/fd2-run-harness-{name}"
    if cmd == "run":
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "100000000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "0"
        os.environ["FD2_HARNESS_CALLLOG_ICOUNT"] = "1"
        os.environ.pop("FD2_HARNESS_CALLLOG_GATE", None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT")
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in extra if v not in w])
        import fd2_original_verify as ov  # noqa: E402
        import fd2_chapter_sweep as sw  # noqa: E402
        steps = [{"op": "patch_chapter", "value": 1}, {"op": "poll_title"},
                 {"op": "keys", "keys": ["Down"], "wait": 1.0}, {"op": "shot", "label": "title_menu"},
                 {"op": "keys", "keys": ["Return"], "wait": 4.0}, {"op": "keys", "keys": ["Return"], "wait": 6.0},
                 {"op": "shot", "label": "town"}]
        for i, k in enumerate("Return,Escape,Right,Right,Right,Return,Return,Return,Return".split(",")):
            steps += [{"op": "keys", "keys": [k], "wait": 2.5}, {"op": "shot", "label": f"r{i:02d}_{k}"}]
        out = HERE / "cl"
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = ov.Runner({"name": name, "instance": name, "chapter": 1, "steps": steps, "keepalive": 14400}, out, True).run()
        t_battle = time.time()
        if r.ok:
            time.sleep(IDLE_S)
            sw.screenshot(name, out / f"{name}_after_idle.png")
        res = {"ok": r.ok, "error": r.error, "t_host": [t0, t_battle, time.time()], "idle_s": IDLE_S if r.ok else 0,
               "assertions": [(a.name, a.ok, a.detail) for a in r.assertions], "shots": r.shots}
        (out / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(res)
        print(wsl(f"md5sum {wd}/FD2.EXE; ls -la {wd}/CALLLOG.TXT; head -1 {wd}/CALLLOG.TXT | cut -c1-200"))
        return 0 if r.ok else 1
    if cmd == "down":
        import fd2_chapter_sweep as sw  # noqa: E402
        print(sw.teardown(name))
        time.sleep(2)
        OD.mkdir(parents=True, exist_ok=True)
        dst = sw.to_wsl_path(OD / f"{name}_CALLLOG.TXT")
        print(wsl(f"md5sum {wd}/FD2.EXE {wd}/CALLLOG.TXT; wc -l < {wd}/CALLLOG.TXT; cp {wd}/CALLLOG.TXT {dst} && ls -la {dst}",
                  timeout=300))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
