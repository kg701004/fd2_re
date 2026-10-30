"""續一百七十二 實機(使用者「永遠核准你進行實機」):開機 → 標題 → START,錄 G / S / I 加時間片欄位,DOS 時鐘先設好。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點。步驟與續一百六十三 lc163a 相同
(poll_title → Return),START 之後等 16 秒(續一百七十一是 8 秒);入口檔沿用 lc163a 的 entries_3b.txt;
dosbox-x 是 ~/fd2-dosbox-calllog2 以續一百七十二的 fd2_calllog_patch.py --upgrade 重編(多 FD2_CALLLOG_SLICES)。
另設 FD2_HARNESS_DOS_TIME(FD2.EXE 之前 TIME)讓 DOS 秒數 0 落在片頭 delay 裡;預測寫在 pred172.txt(跑之前)。

用法:
  python lc172.py run NAME        # 開 instance、poll_title、截圖、Return(START)、等 16 秒、截圖(instance 保留);截圖在 .wsl_build/lc172_live/cl/
  python lc172.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc172_live/
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
OD = REPO / ".wsl_build" / "lc172_live"

ENTRY_FILE = "/home/kg701004/fd2-calllog-s163/entries_3b.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog2/dosbox-x/src/dosbox-x"
# lc172a:3000 .. 24000 ms 全錄 G(含續一百七十一的空窗 3400 .. 3700、START 前後、新遊戲開場),
# 3800 / 6300 ms 各 10 ms 逐條(與 lc171b 相同的 delay 時段)。
# lc172b:設定與 lc172a 相同,另開 FD2_CALLLOG_PICEV(每 100 ms 各 PIC 事件處理函式的次數),找片頭每 ms 多出約 22 個時間片的來源;
# 同時是 lc172a 的重做(DH = 0 那一秒、時間片欄位要再出現一次)。
SEGS = {"lc172a": "3000-3800,3800-3810:x,3810-6300,6300-6310:x,6310-24000",
        "lc172b": "3000-3800,3800-3810:x,3810-6300,6300-6310:x,6310-24000"}
DOS_TIME = {"lc172a": "12:00:54", "lc172b": "12:00:54"}
PICEV = {"lc172a": "0", "lc172b": "1"}


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    cmd, name = argv
    wd = f"/home/kg701004/fd2-run-harness-{name}"
    if cmd == "run":
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = DOSBOX_BIN
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "100000000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "0"
        os.environ["FD2_HARNESS_CALLLOG_ICOUNT"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_SEGS"] = SEGS[name]
        os.environ["FD2_HARNESS_CALLLOG_SLICES"] = "1"
        os.environ["FD2_HARNESS_DOS_TIME"] = DOS_TIME[name]
        os.environ["FD2_HARNESS_CALLLOG_PICEV"] = PICEV[name]
        os.environ.pop("FD2_HARNESS_CALLLOG_GATE", None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT", "FD2_HARNESS_CALLLOG_SEGS",
                 "FD2_HARNESS_CALLLOG_SLICES", "FD2_HARNESS_DOS_TIME", "FD2_HARNESS_CALLLOG_PICEV")
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in extra if v not in w])
        import fd2_original_verify as ov  # noqa: E402
        steps = [{"op": "poll_title", "max_tries": 30, "wait": 1.0}, {"op": "shot", "label": "title_menu"},
                 {"op": "keys", "keys": ["Return"], "wait": 16.0}, {"op": "shot", "label": "after_start"}]
        out = OD / "cl"                     # 截圖與 run json 不進 repo
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = ov.Runner({"name": name, "instance": name, "steps": steps, "keepalive": 14400}, out, True).run()
        res = {"ok": r.ok, "error": r.error, "t_host": [t0, time.time()],
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
