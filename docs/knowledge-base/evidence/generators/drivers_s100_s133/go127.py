# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百二十七:以 fd2_chapter_sweep 的完整隊伍存檔進章節位元組 22 的戰場(畫面第 23 章;sweep 編號 chapter_n = 23)。

只對原版 FD2.EXE。存檔由 prepare_chapter_save 產生(來源 .wsl_build/chapter_sweep/FD2_source.SAV,md5 e6d9…),
roster_cap = guard_selection_threshold(23) + 1(出戰選擇格,見記憶 續六十五)。
用法:python go127.py INST
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
import fd2_chapter_sweep as sw  # noqa: E402

CH_N = 23   # sweep 編號 = 章節位元組 + 1


def main(inst: str) -> int:
    out = Path(__file__).resolve().parent / "cl" / inst
    out.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    cap = sw.guard_selection_threshold(CH_N) + 1
    sav = out / "patched.SAV"
    sw.prepare_chapter_save(REPO / ".wsl_build/chapter_sweep/FD2_source.SAV", CH_N, sav, 0, log, roster_cap=cap)
    n = len(sw.complete_roster_ids(CH_N, cap=cap))
    log.append(f"roster_count={n} cap={cap}")
    sw.launch_instance(inst, keepalive=14400)
    time.sleep(12)
    sw.overwrite_save(inst, sav)
    for _ in range(30):
        sw.send_keys(inst, "Escape")
        time.sleep(0.3)
    sw.send_keys(inst, "Down")
    time.sleep(0.5)
    sw.send_keys(inst, "Return")
    time.sleep(2.0)
    sw.send_keys(inst, "Return")
    time.sleep(6.0)
    sw.screenshot(inst, out / "02_post_load.png")
    r = sw.attempt_camp_exit(inst, out, log, chapter_n=CH_N, roster_count=n)
    log.append(f"attempt_camp_exit -> {r}")
    sw.screenshot(inst, out / "03_after_exit.png")
    (out / "go_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("\n".join(log))
    return 0 if r else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
