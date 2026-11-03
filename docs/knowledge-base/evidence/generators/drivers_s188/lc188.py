"""續一百八十八 實機(要另行核准):續一百八十七仍留 —— 金錢箱按鍵關掉「發現 N 元」之後,旗標才變 1、錢才加。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點。
dosbox-x 與入口檔同 lc186(~/fd2-dosbox-calllog4、~/fd2-calllog-s184/entries_all.txt);不開觸發擷取。
預測寫在 pred188.txt(跑之前)。逐步推進:每個指令一步,畫面文字以 tools/fd2_screen_text.py 程式判讀。

用法:
  python lc188.py run NAME [CHAPTER]               # 同 lc186:開 instance、poll_title、截圖;instance 保留
  python lc188.py key NAME LABEL WAIT K1 [K2 ...]  # 逐鍵送出(每鍵後等 WAIT 秒)、截圖並判讀文字
  python lc188.py hud NAME LABEL                   # 同 lc186(只在面板上按 Return;E 0x117e7 增加就停)
  python lc188.py text NAME LABEL                  # 截圖、判讀文字(不送鍵)
  python lc188.py state NAME LABEL                 # 進 debugger 讀:旗標表 12 格、金錢 [0x53bf3]、金額 [0x53ae1]、
                                                   #   游標 [0x53ab1] / [0x53ab5]、anchor [0x53ab9] / [0x53abd]、單位表([0x53a45],[0x53beb] 筆);resume
  python lc188.py goto NAME LABEL X Y [MAX]        # 一次一個方向鍵把游標移到 (X, Y);每步讀游標,游標沒動就停
  python lc188.py down NAME                        # teardown(工作目錄保留),取 CALLLOG.TXT 指紋並複製到 .wsl_build/lc188_live/
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
OD = REPO / ".wsl_build" / "lc188_live"

ENTRY_FILE = "/home/kg701004/fd2-calllog-s184/entries_all.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x"
DOS_TIME = "12:00:54"
NAMES = ("lc188a",)
DELTA = 0x19C000
INPUT_LOOP, RING = 0x117E7, 0x16F55
# 讀的全域(native;執行期 + DELTA)
OPENED_PTR = 0x53AD5          # [0x53ad5] = 開箱旗標表指標(指標值已是執行期線性位址,續一百八十六)
MONEY = 0x53BF3               # 0x194e8 add dword ptr [0x3bf3], eax
AMOUNT = 0x53AE1              # 0x19477 mov dword ptr [0x3ae1], ebx(顯示「發現 N 元」之前存的金額)
CURSOR_X, CURSOR_Y = 0x53AB1, 0x53AB5   # 鏡頭目前平移到的格(正常玩法跟著游標;real_open5 以它走到 (3,8))
ANCHOR_X, ANCHOR_Y = 0x53AB9, 0x53ABD   # 持久 anchor 游標(doc10;只記錄、對照用)
UNITS_PTR, UNIT_COUNT, UNIT_SIZE = 0x53A45, 0x53BEB, 0x50
N_FLAGS = 12                  # 第 10 張圖 12 個寶箱(ev_s187 WINDOW)
STEP = {(1, 0): "Right", (-1, 0): "Left", (0, 1): "Down", (0, -1): "Up"}


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


def read_text(shot: Path) -> dict:
    """截圖文字判讀(fd2_screen_text);結果另存 <shot>.text.json。"""
    import fd2_screen_text as st  # noqa: PLC0415
    res = st.read_shot(shot, st.load_font(), st.load_strings(),
                       json.loads(st.GLYPH_MAP_PATH.read_text(encoding="utf-8")))
    shot.with_suffix(".text.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
    return res


def show_text(res: dict) -> str:
    if not res["readable"]:
        return f"讀不了:{res['error']}"
    ls = [f"({ln['x']},{ln['y']}) {ln['text']}" for ln in res["lines"]]
    bx = [f"{b['file']}#{b['string_hex']}{b['numbers'] or ''}" for b in res["boxes"] if b["complete"]]
    return f"hits={res['hits']} lines={ls} complete={bx}"


def u32(b: bytes, o: int = 0) -> int:
    return int.from_bytes(b[o:o + 4], "little")


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

    def shot_text(label: str) -> dict:
        shot = OD / "cl" / name / f"{label}.png"
        lh.screenshot(name, shot)
        res = read_text(shot)
        log_event(name, {"op": "shot", "label": label,
                         "complete": [b["string_hex"] for b in res.get("boxes", []) if b["complete"]]})
        print(shot, show_text(res))
        return res

    def dump(label: str, lin: int, ln: int) -> bytes:
        out = OD / "cl" / name / f"{label}.bin"
        _p, size = lh.mem_dump(name, "0170", f"{lin:x}", f"{ln:x}", out)
        b = out.read_bytes()
        if size != ln or len(b) != ln:
            raise RuntimeError(f"{label}: 讀到 {size} / {len(b)} bytes,要 {ln}")
        return b

    def cursor() -> tuple[int, int]:
        lh.enter_debugger(name)
        if not lh.wait_halted(name):
            raise RuntimeError("debugger 沒停住")
        x = dump("_cx", CURSOR_X + DELTA, 1)[0]
        y = dump("_cy", CURSOR_Y + DELTA, 1)[0]
        lh.resume(name)
        return x, y

    if cmd == "key":
        label, wait, keys = argv[2], float(argv[3]), argv[4:]
        for k in keys:
            log_event(name, {"op": "key", "key": k, "label": label})
            lh.send_keys(name, [lh.resolve_key(k)])
            time.sleep(wait)
        shot_text(label)
        return 0
    if cmd == "text":
        shot_text(argv[2])
        return 0
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
    if cmd == "state":
        label = argv[2]
        lh.enter_debugger(name)
        if not lh.wait_halted(name):
            print("debugger 沒停住,不讀")
            return 1
        ptr = u32(dump(f"{label}_ptr", OPENED_PTR + DELTA, 4))
        flags = list(dump(f"{label}_flags", ptr, 0x20)[:N_FLAGS])
        money = u32(dump(f"{label}_money", MONEY + DELTA, 4))
        amount = u32(dump(f"{label}_amount", AMOUNT + DELTA, 4))
        cx, cy = dump(f"{label}_cx", CURSOR_X + DELTA, 1)[0], dump(f"{label}_cy", CURSOR_Y + DELTA, 1)[0]
        ax, ay = dump(f"{label}_ax", ANCHOR_X + DELTA, 1)[0], dump(f"{label}_ay", ANCHOR_Y + DELTA, 1)[0]
        uptr = u32(dump(f"{label}_uptr", UNITS_PTR + DELTA, 4))
        ucnt = u32(dump(f"{label}_ucnt", UNIT_COUNT + DELTA, 4))
        units = dump(f"{label}_units", uptr, UNIT_SIZE * 40)
        print(lh.resume(name))
        st = {"label": label, "opened_ptr": hex(ptr), "flags": flags, "money": money, "amount": amount,
              "cursor": [cx, cy], "anchor": [ax, ay], "units_ptr": hex(uptr), "unit_count": ucnt,
              "units_xy": [[units[k * UNIT_SIZE], units[k * UNIT_SIZE + 1]] for k in range(min(ucnt, 40))]}
        (OD / "cl" / name / f"{label}.json").write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n",
                                                        encoding="utf-8", newline="\n")
        log_event(name, {"op": "state", **st})
        print(json.dumps(st, ensure_ascii=False))
        return 0
    if cmd == "goto":
        label, tx, ty = argv[2], int(argv[3]), int(argv[4])
        mx = int(argv[5]) if len(argv) > 5 else 20
        cur = cursor()
        log_event(name, {"op": "goto", "label": label, "from": cur, "to": [tx, ty]})
        for i in range(mx):
            if cur == (tx, ty):
                break
            dx = (tx > cur[0]) - (tx < cur[0])
            dy = 0 if dx else (ty > cur[1]) - (ty < cur[1])
            key = STEP[(dx, dy)]
            lh.send_keys(name, [lh.resolve_key(key)])
            time.sleep(0.6)
            nxt = cursor()
            log_event(name, {"op": "goto_step", "label": label, "i": i, "key": key, "before": cur, "after": nxt})
            print(i, key, cur, "->", nxt)
            if nxt == cur:
                print("游標沒動,停")
                shot_text(f"{label}_stuck")
                return 1
            cur = nxt
        shot_text(label)
        return 0 if cur == (tx, ty) else 1
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
