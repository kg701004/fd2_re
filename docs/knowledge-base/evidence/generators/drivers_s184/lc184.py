"""續一百八十四 實機(使用者 2026-11-02「請全部實機執行進行確認」):續一百八十一 .. 一百八十三的三項仍留。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點。
dosbox-x 同 lc181(~/fd2-dosbox-calllog4);入口檔是全部 1356 個(~/fd2-calllog-s184/entries_all.txt)。
預測寫在 pred184.txt(跑之前)。逐鍵推進:每次 `key` 送鍵、等、截圖,時間軸寫進 cl/<NAME>_keys.jsonl。

用法:
  python lc184.py run NAME [CHAPTER]          # 開 instance(CHAPTER 有給就先改 slot 0 章節)、poll_title、截圖;instance 保留
  python lc184.py key NAME LABEL WAIT K1 [K2 ...]   # 逐鍵送出(每鍵後等 WAIT 秒)、截圖 cl/NAME/LABEL.png
  python lc184.py mem NAME LABEL LIN_HEX LEN_HEX    # 進 debugger、讀 0170:LIN 起 LEN 位元組到 cl/NAME/LABEL.bin、resume
  python lc184.py down NAME                   # teardown(工作目錄保留),取 CALLLOG.TXT 指紋並複製到 .wsl_build/lc184_live/
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
OD = REPO / ".wsl_build" / "lc184_live"

ENTRY_FILE = "/home/kg701004/fd2-calllog-s184/entries_all.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x"
DOS_TIME = "12:00:54"
TRIG = "ng:375,ng:302-303"
TRIGCAP = "40"
NAMES = ("lc184a", "lc184b")


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def log_event(name: str, rec: dict) -> None:
    """時間軸:主機時間 + 動作,之後與截圖、K 紀錄對齊。"""
    out = OD / "cl"
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"{name}_keys.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"t": time.time(), **rec}, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, name = argv[0], argv[1]
    wd = f"/home/kg701004/fd2-run-harness-{name}"
    if name not in NAMES:
        print("instance 名稱只能是", NAMES)
        return 2
    if cmd == "run":
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = DOSBOX_BIN
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "3000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "32"
        os.environ["FD2_HARNESS_CALLLOG_ICOUNT"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_SLICES"] = "1"
        os.environ["FD2_HARNESS_DOS_TIME"] = DOS_TIME
        os.environ["FD2_HARNESS_CALLLOG_PICEV"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_KBD"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_TRIG"] = TRIG
        os.environ["FD2_HARNESS_CALLLOG_TRIGCAP"] = TRIGCAP
        for v in ("FD2_HARNESS_CALLLOG_GATE", "FD2_HARNESS_CALLLOG_TRIGRING", "FD2_HARNESS_CALLLOG_TRIGPRE",
                  "FD2_HARNESS_CALLLOG_TRIGT", "FD2_HARNESS_CALLLOG_SEGS", "FD2_HARNESS_CALLLOG_IO"):
            os.environ.pop(v, None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT",
                 "FD2_HARNESS_CALLLOG_SLICES", "FD2_HARNESS_DOS_TIME", "FD2_HARNESS_CALLLOG_PICEV",
                 "FD2_HARNESS_CALLLOG_KBD", "FD2_HARNESS_CALLLOG_TRIG", "FD2_HARNESS_CALLLOG_TRIGCAP")
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in extra if v not in w])
        import fd2_original_verify as ov  # noqa: E402
        steps = [{"op": "poll_title", "max_tries": 30, "wait": 1.0}, {"op": "shot", "label": "title_menu"}]
        if len(argv) > 2:
            steps.insert(0, {"op": "patch_chapter", "value": int(argv[2])})
        out = OD / "cl"                     # 截圖與 run json 不進 repo
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = ov.Runner({"name": name, "instance": name, "steps": steps, "keepalive": 14400}, out, True).run()
        res = {"ok": r.ok, "error": r.error, "t_host": [t0, time.time()],
               "assertions": [(a.name, a.ok, a.detail) for a in r.assertions], "shots": r.shots}
        (out / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        log_event(name, {"op": "run", "ok": r.ok})
        print(res)
        print(wsl(f"md5sum {wd}/FD2.EXE; ls -la {wd}/CALLLOG.TXT; head -1 {wd}/CALLLOG.TXT | cut -c1-300"))
        return 0 if r.ok else 1
    import fd2_dosbox_live_helper as lh  # noqa: E402
    if cmd == "key":
        label, wait, keys = argv[2], float(argv[3]), argv[4:]
        for k in keys:
            log_event(name, {"op": "key", "key": k, "label": label})
            lh.send_keys(name, [lh.resolve_key(k)])
            time.sleep(wait)
        shot = OD / "cl" / name / f"{label}.png"
        lh.screenshot(name, shot)
        log_event(name, {"op": "shot", "label": label})
        print(shot)
        return 0
    if cmd == "mem":
        label, lin, ln = argv[2], argv[3], argv[4]
        lh.enter_debugger(name)
        if not lh.wait_halted(name):
            print("debugger 沒停住,不讀")
            return 1
        out = OD / "cl" / name / f"{label}.bin"
        _p, size = lh.mem_dump(name, "0170", lin, ln, out)
        print(lh.resume(name))
        log_event(name, {"op": "mem", "label": label, "lin": lin, "len": ln, "size": size})
        print(out, size)
        print(lh.format_hexdump(out.read_bytes()[:0x200]))
        return 0
    if cmd == "down":
        import fd2_chapter_sweep as sw  # noqa: E402
        print(sw.teardown(name))
        time.sleep(2)
        OD.mkdir(parents=True, exist_ok=True)
        dst = sw.to_wsl_path(OD / f"{name}_CALLLOG.TXT")
        log_event(name, {"op": "down"})
        print(wsl(f"md5sum {wd}/FD2.EXE {wd}/CALLLOG.TXT; wc -l < {wd}/CALLLOG.TXT; cp {wd}/CALLLOG.TXT {dst} && ls -la {dst}",
                  timeout=600))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
