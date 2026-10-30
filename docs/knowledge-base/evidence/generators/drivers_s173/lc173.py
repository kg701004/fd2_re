"""續一百七十三 實機(使用者「永遠核准你進行實機」):開機 → 標題 → START,驗 FD2_CALLLOG_IO / FD2_CALLLOG_KBD。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點。步驟與 lc172 相同
(poll_title → Return,START 之後等 16 秒),入口檔沿用 lc163a 的 entries_3b.txt;
dosbox-x 是 ~/fd2-dosbox-calllog3(~/fd2-dosbox-calllog2 的複本,以續一百七十三的 fd2_calllog_patch.py --upgrade 重編;
calllog2 留給續一百七十二的證據)。預測寫在 pred173.txt(跑之前)。

用法:
  python lc173.py run NAME        # 開 instance、poll_title、截圖、Return(START)、等 16 秒、截圖(instance 保留);截圖在 .wsl_build/lc173_live/cl/
  python lc173.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc173_live/
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
OD = REPO / ".wsl_build" / "lc173_live"

ENTRY_FILE = "/home/kg701004/fd2-calllog-s163/entries_3b.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog3/dosbox-x/src/dosbox-x"
# lc173a:3000 .. 24000 ms 全錄 G,DMA_DAC 開始(續一百七十二 3189.84 ms)前後 3150 .. 3250 ms 逐條(驗 O / N 的 eip);
# I/O:DMA 8 / 16 位元(0-f、c0-df)與頁(81-8f)、PIC(20-21、a0-a1)、PIT(40-43)、鍵盤(60、64)、SB(220-22f)、OPL(388-38b)。
SEGS = {"lc173a": "3000-3150,3150-3250:x,3250-24000"}
IO = {"lc173a": "0-f,20-21,40-43,60,64,81-8f,a0-a1,c0-df,220-22f,388-38b"}
DOS_TIME = {"lc173a": "12:00:54"}


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
        os.environ["FD2_HARNESS_CALLLOG_PICEV"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_IO"] = IO[name]
        os.environ["FD2_HARNESS_CALLLOG_KBD"] = "1"
        os.environ.pop("FD2_HARNESS_CALLLOG_GATE", None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT", "FD2_HARNESS_CALLLOG_SEGS",
                 "FD2_HARNESS_CALLLOG_SLICES", "FD2_HARNESS_DOS_TIME", "FD2_HARNESS_CALLLOG_PICEV",
                 "FD2_HARNESS_CALLLOG_IO", "FD2_HARNESS_CALLLOG_KBD")
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
        print(wsl(f"md5sum {wd}/FD2.EXE; ls -la {wd}/CALLLOG.TXT; head -1 {wd}/CALLLOG.TXT | cut -c1-300"))
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
