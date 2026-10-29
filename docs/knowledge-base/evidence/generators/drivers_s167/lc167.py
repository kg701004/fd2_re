# 存檔:原 scratchpad 驅動腳本(續一百六十七),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百六十七 戰場實機(使用者 2026-10-29「永遠核准你進行實機」):第 1 章戰場玩家回合閒置 / 結束回合 / 敵方回合的計時中斷呼叫紀錄。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點、不進除錯器;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(patch_chapter)。預測見 pred167_turns.txt。

用法:
  python lc167.py entries
  python lc167.py run NAME        # 開 instance → 第 1 章戰場 → 清對話 → 閒置 30 秒 → 結束回合 → 等敵方回合結束 → 閒置 25 秒(instance 保留)
  python lc167.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc167_live/
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
HERE = Path(__file__).resolve().parent
OD = REPO / ".wsl_build" / "lc167_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s167"
ENTRY_FILE = f"{ENTRY_DIR}/entries_turns.txt"
DELTA = 0x19C000
NATIVE = [0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x37C30, 0x3DFEF, 0x25BF4, 0x25C01,
          0x1F894, 0x1FC66, 0x1FD7C, 0x370F0, 0x1FE63, 0x1FED3, 0x1FEF0, 0x1FF31, 0x1FF36, 0x3E01D, 0x32326,
          0x11CAC,                     # redraw(續一百六十六的戰場時段標記)
          # 續一百六十七:回合時段標記
          0x117E7, 0x14EF0, 0x16F55, 0x1A30B, 0x1D80B, 0x1D8BA]
ENEMY_PHASE = 0x1D8BA
IDLE_P_S, IDLE_P2_S, ENEMY_WAIT_S = 30.0, 25.0, 240.0


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def last_t(wd: str) -> tuple[float, float | None]:
    """(主機時間, CALLLOG.TXT 尾端最後一筆完整記錄的 t);只讀檔,不停模擬器。"""
    h = time.time()
    tail = wsl(f"tail -c 4000 {wd}/CALLLOG.TXT").splitlines()
    # 最後一行可能還沒寫完(緩衝寫入),丟掉;第一行是從中間切的,也丟掉
    ts = [m.group(1) for ln in tail[1:-1] if (m := re.search(r" t=([0-9]+\.[0-9]+)$", ln))]
    return h, (float(ts[-1]) if ts else None)


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
        log: list[str] = []
        res: dict = {"t_host": {"start": time.time()}, "marks": {}}

        def save(ok: bool, err: str | None) -> int:
            res.update(ok=ok, error=err, log=log)
            (out / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps({k: v for k, v in res.items() if k != "log"}, ensure_ascii=False))
            print("\n".join(log[-6:]))
            print(wsl(f"md5sum {wd}/FD2.EXE; ls -la {wd}/CALLLOG.TXT"))
            return 0 if ok else 1

        r = ov.Runner({"name": name, "instance": name, "chapter": 1, "steps": steps, "keepalive": 14400}, out, True).run()
        res["runner"] = {"ok": r.ok, "error": r.error, "assertions": [(a.name, a.ok, a.detail) for a in r.assertions],
                         "shots": r.shots}
        res["t_host"]["battle"] = time.time()
        if not r.ok:
            return save(False, "runner")
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        hud_ok, clears = sw.ensure_battle_hud(name, d, log, "hud", max_clears=60)
        res["hud"] = {"ok": hud_ok, "clears": clears}
        if not hud_ok:
            return save(False, "hud")
        # P:玩家回合閒置
        res["marks"]["P_a"] = last_t(wd)
        time.sleep(IDLE_P_S)
        res["marks"]["P_b"] = last_t(wd)
        sw.screenshot(name, d / "p_idle_end.png")
        # 結束回合(不進除錯器;同 confirm_end_turn 的按鍵)
        found, _ = sw.find_empty_adjacent_tile(name, d, log)
        res["empty_tile"] = found
        if not found:
            return save(False, "empty_tile")
        res["t_host"]["ring"] = time.time()
        sw.send_keys(name, "Return")
        time.sleep(0.6)
        sw.send_keys(name, "Down")
        time.sleep(0.4)
        sw.send_keys(name, "Return")
        time.sleep(0.8)
        sw.screenshot(name, d / "end_turn_prompt.png")
        sw.send_keys(name, "Return")
        res["t_host"]["yes"] = time.time()
        # 等 enemy_phase_dispatch 的 R(只 grep 檔案)
        pat = f"^R [0-9]+ {ENEMY_PHASE + DELTA:08x} "
        t0, n_shot, got = time.time(), 0, ""
        while time.time() - t0 < ENEMY_WAIT_S:
            time.sleep(5.0)
            n_shot += 1
            sw.screenshot(name, d / f"wait_{n_shot:02d}.png")
            got = wsl(f"grep -c -E '{pat}' {wd}/CALLLOG.TXT")
            if got.strip() not in ("", "0"):
                break
        res["t_host"]["enemy_done"] = time.time()
        res["enemy_wait"] = {"grep": got, "shots": n_shot}
        if got.strip() in ("", "0"):
            return save(False, "enemy_phase_timeout")
        # P2:第二個玩家回合閒置
        time.sleep(3.0)
        res["marks"]["P2_c"] = last_t(wd)
        time.sleep(IDLE_P2_S)
        res["marks"]["P2_d"] = last_t(wd)
        sw.screenshot(name, d / "p2_idle_end.png")
        res["t_host"]["end"] = time.time()
        return save(True, None)
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
