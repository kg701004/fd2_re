"""續一百八十六 實機(使用者 2026-11-02「請進行實機確認」):續一百八十五仍留 —— 第 10 張圖盜賊搶寶箱的 0xc。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點。
dosbox-x 與入口檔同 lc184(~/fd2-dosbox-calllog4、~/fd2-calllog-s184/entries_all.txt,全部 1356 個);不開觸發擷取。
預測寫在 pred186.txt(跑之前)。逐鍵推進:每次 `key` 送鍵、等、截圖,時間軸寫進 cl/<NAME>_keys.jsonl。

用法:
  python lc186.py run NAME [CHAPTER]          # 開 instance(CHAPTER 有給就先改 slot 0 章節)、poll_title、截圖;instance 保留
  python lc186.py key NAME LABEL WAIT K1 [K2 ...]   # 逐鍵送出(每鍵後等 WAIT 秒)、截圖 cl/NAME/LABEL.png
  python lc186.py hud NAME LABEL              # ensure_battle_hud(panel_gate,只在面板上按 Return;E 0x117e7 增加就停)
  python lc186.py endturn NAME LABEL          # send_end_turn_keys(不進除錯器;指令環以 E 0x16f55 增加確認)
  python lc186.py count NAME                  # 讀 CALLLOG 裡幾個入口的 E 筆數(只讀檔)
  python lc186.py mem NAME LABEL LIN_HEX LEN_HEX    # 進 debugger、讀 0170:LIN 起 LEN 位元組到 cl/NAME/LABEL.bin、resume
  python lc186.py flags NAME LABEL            # 讀 [0x53ad5](執行期 0x1efad5)的指標,再讀它指向的 0x20 位元組(指標值即線性位址)
  python lc186.py down NAME                   # teardown(工作目錄保留),取 CALLLOG.TXT 指紋並複製到 .wsl_build/lc186_live/
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
OD = REPO / ".wsl_build" / "lc186_live"

ENTRY_FILE = "/home/kg701004/fd2-calllog-s184/entries_all.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x"
DOS_TIME = "12:00:54"
NAMES = ("lc186a",)
DELTA = 0x19C000
INPUT_LOOP, RING = 0x117E7, 0x16F55
WATCH = {"ai_mode_dispatch": 0x13A9F, "find_event_cell": 0x15DF3, "handle_B": 0x25B45,
         "enemy_phase_dispatch": 0x1D8BA, "input_loop": INPUT_LOOP, "ring": RING}
OPENED_PTR = 0x53AD5                        # [0x53ad5] = 開箱旗標表指標(native 值)


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
        for v in ("FD2_HARNESS_CALLLOG_GATE", "FD2_HARNESS_CALLLOG_TRIG", "FD2_HARNESS_CALLLOG_TRIGCAP",
                  "FD2_HARNESS_CALLLOG_TRIGRING", "FD2_HARNESS_CALLLOG_TRIGPRE",
                  "FD2_HARNESS_CALLLOG_TRIGT", "FD2_HARNESS_CALLLOG_SEGS", "FD2_HARNESS_CALLLOG_IO"):
            os.environ.pop(v, None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT",
                 "FD2_HARNESS_CALLLOG_SLICES", "FD2_HARNESS_DOS_TIME", "FD2_HARNESS_CALLLOG_PICEV",
                 "FD2_HARNESS_CALLLOG_KBD")
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
    import fd2_chapter_sweep as sw  # noqa: E402
    import fd2_dosbox_live_helper as lh  # noqa: E402

    def count(native: int) -> int | None:
        return sw.calllog_count(name, "E", native + DELTA)

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
    if cmd == "count":
        got = {k: count(v) for k, v in WATCH.items()}
        log_event(name, {"op": "count", **got})
        print(got)
        return 0
    if cmd == "watch":
        # 不送鍵:每 STEP 秒截圖 + 讀筆數,直到 E 0x117e7(我方輸入迴圈)比開始時多,或滿 MAX 秒
        label, step, mx = argv[2], float(argv[3]), float(argv[4])
        d = OD / "cl" / name / label
        d.mkdir(parents=True, exist_ok=True)
        base, t0, i = count(INPUT_LOOP), time.time(), 0
        if base is None:
            print("CALLLOG 讀不到")
            return 1
        while time.time() - t0 < mx:
            time.sleep(step)
            lh.screenshot(name, d / f"w{i:03d}.png")
            got = {k: count(v) for k, v in WATCH.items()}
            log_event(name, {"op": "watch", "label": label, "i": i, **got})
            print(i, round(time.time() - t0, 1), got)
            i += 1
            if (got["input_loop"] or 0) > base:
                return 0
        print("滿 MAX 秒,我方輸入迴圈沒回來")
        return 1
    if cmd == "hud":
        label = argv[2]
        d = OD / "cl" / name / label
        d.mkdir(parents=True, exist_ok=True)
        base = count(INPUT_LOOP)
        if base is None:
            print("CALLLOG 讀不到,不送鍵")
            return 1
        log: list[str] = []
        log_event(name, {"op": "hud", "label": label, "loop_E_base": base})
        ok, n = sw.ensure_battle_hud(name, d, log, label, max_clears=60, panel_gate=True,
                                     control_probe=lambda: (count(INPUT_LOOP) or 0) > base)
        log_event(name, {"op": "hud_done", "label": label, "ok": ok, "returns": n, "loop_E": count(INPUT_LOOP)})
        print(ok, n, "\n".join(log[-8:]))
        return 0 if ok else 1
    if cmd == "endturn":
        label = argv[2]
        d = OD / "cl" / name / label
        d.mkdir(parents=True, exist_ok=True)
        base = count(RING)
        if base is None:
            print("CALLLOG 讀不到,不送鍵")
            return 1
        log = []
        log_event(name, {"op": "endturn", "label": label, "ring_E_base": base})
        res = sw.send_end_turn_keys(name, d, log, ring_probe=lambda: (count(RING) or 0) > base)
        log_event(name, {"op": "endturn_done", "label": label, **{k: v for k, v in res.items() if k != "t_host"}})
        print(res, "\n".join(log[-8:]))
        return 0 if res["ok"] else 1
    if cmd in ("mem", "flags"):
        label = argv[2]
        lh.enter_debugger(name)
        if not lh.wait_halted(name):
            print("debugger 沒停住,不讀")
            return 1
        if cmd == "mem":
            lin, ln = argv[3], argv[4]
        else:
            pp = OD / "cl" / name / f"{label}_ptr.bin"
            lh.mem_dump(name, "0170", f"{OPENED_PTR + DELTA:x}", "4", pp)
            ptr = int.from_bytes(pp.read_bytes()[:4], "little")
            # 記憶體裡的指標值已是執行期線性位址(同單位表指標 0x26c8bc 直接可讀),不再加 DELTA
            # (f00_flags 第一版加了 DELTA,讀到 0x392c5c 全 0,作廢)
            lin, ln = f"{ptr:x}", "20"
            print(f"[0x53ad5] = {ptr:#x}(執行期線性位址)")
        out = OD / "cl" / name / f"{label}.bin"
        _p, size = lh.mem_dump(name, "0170", lin, ln, out)
        print(lh.resume(name))
        log_event(name, {"op": cmd, "label": label, "lin": lin, "len": ln, "size": size})
        print(out, size)
        print(lh.format_hexdump(out.read_bytes()[:0x200]))
        return 0
    if cmd == "down":
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
