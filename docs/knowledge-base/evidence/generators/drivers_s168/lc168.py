# 存檔:原 scratchpad 驅動腳本(續一百六十八),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百六十八 戰場實機(使用者 2026-10-29「永遠核准你進行實機」):驗證 ensure_battle_hud(panel_gate) 與
send_end_turn_keys 兩道閘門在第 1 章戰場一次走完。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點、不進除錯器;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(patch_chapter)。預測見 pred168_gates.txt。
結束回合失敗就停(rc 1),不做手動補救。

用法:
  python lc168.py entries
  python lc168.py run NAME        # 開 instance → 第 1 章戰場 → 清對話(panel_gate)→ 狀態檢查 → 閒置 30 秒
                                  # → 結束回合(逐步確認)→ 等敵方回合結束 → 閒置 25 秒(instance 保留)
  python lc168.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc168_live/
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
OD = REPO / ".wsl_build" / "lc168_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s168"
ENTRY_FILE = f"{ENTRY_DIR}/entries_turns.txt"
DELTA = 0x19C000
# 與 lc167 相同的 26 個入口(呼叫紀錄可以和 lc167a 直接比較)
NATIVE = [0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x37C30, 0x3DFEF, 0x25BF4, 0x25C01,
          0x1F894, 0x1FC66, 0x1FD7C, 0x370F0, 0x1FE63, 0x1FED3, 0x1FEF0, 0x1FF31, 0x1FF36, 0x3E01D, 0x32326,
          0x11CAC,
          0x117E7, 0x14EF0, 0x16F55, 0x1A30B, 0x1D80B, 0x1D8BA]
INPUT_LOOP, RING, ENEMY_PHASE = 0x117E7, 0x16F55, 0x1D8BA
IDLE_P_S, IDLE_P2_S, ENEMY_WAIT_S = 30.0, 25.0, 240.0
SAT_REGION = (360, 215, 824, 520)


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def last_t(wd: str) -> tuple[float, float | None]:
    """(主機時間, CALLLOG.TXT 尾端最後一筆完整記錄的 t);只讀檔,不停模擬器。"""
    h = time.time()
    tail = wsl(f"tail -c 4000 {wd}/CALLLOG.TXT").splitlines()
    ts = [m.group(1) for ln in tail[1:-1] if (m := re.search(r" t=([0-9]+\.[0-9]+)$", ln))]
    return h, (float(ts[-1]) if ts else None)


def saturation(png: Path) -> float | None:
    """地圖帶的平均 HSV 飽和度(lc167a:選中單位後 89.4,未選中 133.5 .. 161.4)。"""
    if not png.exists():
        return None
    from PIL import Image, ImageStat
    return round(ImageStat.Stat(Image.open(png).convert("HSV").crop(SAT_REGION)).mean[1], 1)


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
        res: dict = {"t_host": {"start": time.time()}, "marks": {}, "counts": {}}

        def count(kind: str, native: int) -> int | None:
            return sw.calllog_count(name, kind, native + DELTA)

        def save(ok: bool, err: str | None) -> int:
            res.update(ok=ok, error=err, log=log)
            (out / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps({k: v for k, v in res.items() if k != "log"}, ensure_ascii=False))
            print("\n".join(log[-8:]))
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
        # 閘門 1:只在面板上按 Return;看不到面板就等,等滿再問 CALLLOG 是否已進入 battle_main_input_loop
        loop_base = count("E", INPUT_LOOP)
        res["counts"]["loop_E_base"] = loop_base
        if loop_base is None:
            return save(False, "calllog_unreadable")

        def control_probe() -> bool:
            c = count("E", INPUT_LOOP)
            return c is not None and c > loop_base
        hud_ok, clears = sw.ensure_battle_hud(name, d, log, "hud", max_clears=60, panel_gate=True,
                                              control_probe=control_probe)
        res["hud"] = {"ok": hud_ok, "clears": clears,
                      "wait_frames": len(list(d.glob("hudcheck_hud_wait*.png"))),
                      "fallback_returns": sum("fallback Return" in ln for ln in log),
                      "probe_stop": any("control_probe says" in ln for ln in log)}
        res["t_host"]["hud"] = time.time()
        if not hud_ok:
            return save(False, "hud")
        # 進入閒置前的狀態檢查(Q3):讀 CALLLOG 前先等 3 秒,讓 flush 追上
        time.sleep(3.0)
        pre = sw.screenshot(name, d / "state_pre_idle.png")
        res["state_pre_idle"] = {"hud": sw.screen_shows_battle_hud(pre), "panel": sw.screen_shows_dialogue_panel(pre),
                                 "sat": saturation(pre), "loop_E": count("E", INPUT_LOOP), "ring_E": count("E", RING)}
        # P:玩家回合閒置
        res["marks"]["P_a"] = last_t(wd)
        time.sleep(IDLE_P_S)
        res["marks"]["P_b"] = last_t(wd)
        sw.screenshot(name, d / "p_idle_end.png")
        # 閘門 2:結束回合,每一步確認後才送下一個鍵
        ring_base = count("E", RING)
        res["counts"]["ring_E_base"] = ring_base
        if ring_base is None:
            return save(False, "calllog_unreadable")

        def ring_probe() -> bool:
            c = count("E", RING)
            return c is not None and c > ring_base
        end = sw.send_end_turn_keys(name, d, log, ring_probe=ring_probe, probe_timeout_s=8.0)
        res["end_turn"] = end
        firsts = sorted(p.name for p in d.glob("findempty_001_*.png"))
        res["findempty_first_move"] = {"shot": firsts[0] if firsts else None,
                                       "sat": saturation(d / firsts[0]) if firsts else None}
        if not end["ok"]:
            sw.screenshot(name, d / "end_turn_failed.png")
            return save(False, f"end_turn_{end['stage']}")
        # 等 enemy_phase_dispatch 的 R(只 grep 檔案)
        t0, n_shot, got = time.time(), 0, None
        while time.time() - t0 < ENEMY_WAIT_S:
            time.sleep(5.0)
            n_shot += 1
            sw.screenshot(name, d / f"wait_{n_shot:02d}.png")
            got = count("R", ENEMY_PHASE)
            if got:
                break
        res["t_host"]["enemy_done"] = time.time()
        res["enemy_wait"] = {"R_count": got, "shots": n_shot, "s": round(time.time() - t0, 1)}
        if not got:
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
