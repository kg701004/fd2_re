"""續一百六十九 戰場實機(使用者 2026-10-29「永遠核准你進行實機」、2026-10-30「依照你的建議自動繼續進行處理」):
複製 lc167a 的第 33 次 Return(輸入迴圈進入之後、HUD 畫出之前),看它是否進入 0x18890(選中單位)。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點、不進除錯器;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(patch_chapter)。預測見 pred169_select.txt。

用法:
  python lc169.py entries
  python lc169.py run NAME        # 開 instance → 第 1 章戰場 → 清對話(只在面板上按)→ 一看到 E 0x117e7 就送一次 Return
                                  # → sel_0 → 等 E 0x18890 → Up → sel_up(instance 保留)
  python lc169.py down NAME       # teardown(工作目錄保留),再取 CALLLOG.TXT 的指紋並複製到 .wsl_build/lc169_live/
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
REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "tools"))
OD = REPO / ".wsl_build" / "lc169_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s169"
ENTRY_FILE = f"{ENTRY_DIR}/entries_select.txt"
DELTA = 0x19C000
# lc168a 的 26 個入口 + 0x18890(選格 / 動作分派)+ 0x17aed(角色狀態卡演出)
NATIVE = [0x3EA8E, 0x3EBAD, 0x404C0, 0x43270, 0x37C30, 0x3DFEF, 0x25BF4, 0x25C01,
          0x1F894, 0x1FC66, 0x1FD7C, 0x370F0, 0x1FE63, 0x1FED3, 0x1FEF0, 0x1FF31, 0x1FF36, 0x3E01D, 0x32326,
          0x11CAC,
          0x117E7, 0x14EF0, 0x16F55, 0x1A30B, 0x1D80B, 0x1D8BA,
          0x18890, 0x17AED]
INPUT_LOOP, SELECT, STATUS_CARD = 0x117E7, 0x18890, 0x17AED
SAT_REGION = (360, 215, 824, 520)
MAX_FRAMES, MAX_S = 200, 300.0


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
    """地圖帶的平均 HSV 飽和度(lc167a:選中單位後 89.4;lc168a 未選中 150.9)。"""
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
        out = OD / "run"
        out.mkdir(parents=True, exist_ok=True)
        log: list[str] = []
        res: dict = {"t_host": {"start": time.time()}, "marks": {}, "frames": []}

        def count(kind: str, native: int) -> int | None:
            return sw.calllog_count(name, kind, native + DELTA)

        def save(ok: bool, err: str | None) -> int:
            res.update(ok=ok, error=err, log=log)
            (OD / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps({k: v for k, v in res.items() if k not in ("log", "frames")}, ensure_ascii=False))
            print(wsl(f"md5sum {wd}/FD2.EXE; ls -la {wd}/CALLLOG.TXT"))
            return 0 if ok else 1

        r = ov.Runner({"name": name, "instance": name, "chapter": 1, "steps": steps, "keepalive": 14400}, out, True).run()
        res["runner"] = {"ok": r.ok, "error": r.error, "assertions": [(a.name, a.ok, a.detail) for a in r.assertions],
                         "shots": r.shots}
        res["t_host"]["battle"] = time.time()
        if not r.ok:
            return save(False, "runner")
        d = OD / "frames"
        d.mkdir(parents=True, exist_ok=True)
        loop_base = count("E", INPUT_LOOP)
        res["loop_E_base"] = loop_base
        if loop_base is None:
            return save(False, "calllog_unreadable")
        # 清對話:只在面板上按 Return;每張截圖也讀 E 0x117e7。一看到它增加(或 HUD 出現)就送複製的那一次 Return。
        t0, pressed = time.time(), 0
        for i in range(MAX_FRAMES):
            if time.time() - t0 > MAX_S:
                return save(False, "no_control")
            shot = sw.screenshot(name, d / f"c{i:03d}.png")
            hud, panel = sw.screen_shows_battle_hud(shot), sw.screen_shows_dialogue_panel(shot)
            loop_n = count("E", INPUT_LOOP)
            fr = {"i": i, "t_host": round(time.time(), 3), "hud": hud, "panel": panel, "loop_E": loop_n}
            res["frames"].append(fr)
            if (loop_n is not None and loop_n > loop_base) or hud:
                h_press = time.time()
                sw.send_keys(name, "Return")
                res["replica"] = {"frame": i, "t_host_press": round(h_press, 3), "pre_frame_hud": hud,
                                  "pre_frame_panel": panel, "trigger": "loop_E" if loop_n and loop_n > loop_base else "hud",
                                  "dialogue_returns_before": pressed}
                res["marks"]["after_press"] = last_t(wd)
                break
            if panel:
                sw.send_keys(name, "Return")
                pressed += 1
                fr["pressed"] = True
            else:
                time.sleep(0.3)
        else:
            return save(False, "no_control")
        time.sleep(3.0)
        sel0 = sw.screenshot(name, d / "sel_0.png")
        res["sel_0"] = {"hud": sw.screen_shows_battle_hud(sel0), "panel": sw.screen_shows_dialogue_panel(sel0),
                        "sat": saturation(sel0)}
        t1, got = time.time(), None
        while time.time() - t1 < 8.0:
            got = count("E", SELECT)
            if got:
                break
            time.sleep(0.5)
        res["after"] = {"select_E": got, "status_card_E": count("E", STATUS_CARD), "loop_E": count("E", INPUT_LOOP),
                        "wait_s": round(time.time() - t1, 2)}
        sw.send_keys(name, "Up")
        time.sleep(1.5)
        up = sw.screenshot(name, d / "sel_up.png")
        res["sel_up"] = {"hud": sw.screen_shows_battle_hud(up), "sat": saturation(up)}
        res["marks"]["end"] = last_t(wd)
        res["t_host"]["end"] = time.time()
        return save(True, None)
    if cmd == "down":
        import fd2_chapter_sweep as sw  # noqa: E402
        print(sw.teardown(name))
        time.sleep(2)
        OD.mkdir(parents=True, exist_ok=True)
        dst = sw.to_wsl_path(OD / f"{name}_CALLLOG.TXT")
        print(wsl(f"md5sum {wd}/FD2.EXE {wd}/CALLLOG.TXT; wc -l < {wd}/CALLLOG.TXT; head -1 {wd}/CALLLOG.TXT; "
                  f"cat {ENTRY_FILE}; cp {wd}/CALLLOG.TXT {dst} && ls -la {dst}", timeout=300))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
