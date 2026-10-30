# 存檔:原 scratchpad 驅動腳本(續一百七十一),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百七十一 實機(使用者「永遠核准你進行實機」):開機 → 標題 → START,錄 FD2_CALLLOG_SEGS 的非遊戲段與中斷。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點。步驟與續一百六十三 lc163a 相同
(poll_title → Return → 8 秒),入口檔沿用 lc163a 的 entries_3b.txt;差別只在 dosbox-x 換成 ~/fd2-dosbox-calllog2
(fd2_calllog_patch.py --upgrade 後重編)並設 FD2_HARNESS_CALLLOG_SEGS。

時間窗(模擬 ms)依 instance 名稱取 SEGS:校準 0x3dfef 1781 .. 3296(續一百六十三 lc163a)、片頭 delay 3745 .. 7794。

用法:
  python lc171.py run NAME        # 開 instance、poll_title、截圖、Return(START)、等 8 秒、截圖(instance 保留);截圖在 .wsl_build/lc171_live/cl/
  python lc171.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc171_live/
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
OD = REPO / ".wsl_build" / "lc171_live"

ENTRY_FILE = "/home/kg701004/fd2-calllog-s163/entries_3b.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog2/dosbox-x/src/dosbox-x"
# lc171a:校準與片頭都錄 G,各一段 10 ms 逐條(5000 ms 那段事後查到不在 delay 迴圈裡)。
# lc171b:只錄逐條 —— 校準 2000 ms(與 lc171a 對照)、delay 3800 / 6300 ms(lc171a 的 G 紀錄裡 delay int 21h 最密的時段)。
SEGS = {"lc171a": "1700-2000,2000-2010:x,2010-3400,3700-5000,5000-5010:x,5010-7900",
        "lc171b": "2000-2010:x,3800-3810:x,6300-6310:x"}


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
        os.environ.pop("FD2_HARNESS_CALLLOG_GATE", None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT", "FD2_HARNESS_CALLLOG_SEGS")
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in extra if v not in w])
        import fd2_original_verify as ov  # noqa: E402
        steps = [{"op": "poll_title", "max_tries": 30, "wait": 1.0}, {"op": "shot", "label": "title_menu"},
                 {"op": "keys", "keys": ["Return"], "wait": 8.0}, {"op": "shot", "label": "after_start"}]
        out = OD / "cl"                     # 截圖與 run json 不進 repo(lc171a / b 當時寫在本目錄的 cl/,事後搬到這裡)
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
