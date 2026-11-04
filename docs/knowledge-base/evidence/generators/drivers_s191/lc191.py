"""續一百九十一 實機(使用者 2026-11-04「open_static 7 項、open_live 2 項 請完整進行驗證及處理」;「永遠核准」):
91-worklist MAP26-EVENT63-E2-PLAYER-PATH —— 未修改的 ch27 一般玩家路徑:y = 39 向左一步觸發 event62,下一回合敵方階段前 event63。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;不改記憶體、不下斷點;debugger 只讀。
dosbox-x 同 lc186(~/fd2-dosbox-calllog4);入口檔是本輪自己的小清單(ENTRIES,寫到 ~/fd2-calllog-s191/entries.txt),
CAP 放大到 2000000,熱函式(0x3790a 延遲、0x11df2 調色盤)整場都不會記滿。
預測寫在 pred191.txt(跑之前)。畫面文字以 tools/fd2_screen_text.py 程式判讀。

用法:
  python lc191.py run NAME                         # 開 instance(槽 0 是 ch27,不 patch 章節)、poll_title、截圖;instance 保留
  python lc191.py key NAME LABEL WAIT K1 [K2 ...]  # 逐鍵送出(每鍵後等 WAIT 秒)、截圖並判讀文字
  python lc191.py hud NAME LABEL                   # 只在面板上按 Return,直到 E 0x117e7 增加
  python lc191.py text NAME LABEL                  # 截圖、判讀文字(不送鍵)
  python lc191.py state NAME LABEL                 # 進 debugger 讀:回合 [0x53bef]、live 回合列([0x53a55] 起 3 + 16×3)、
                                                   #   事件狀態([0x53ad5] 起 0x20)、游標、單位表;resume
  python lc191.py goto NAME LABEL X Y [MAX]        # 一次一個方向鍵把游標移到 (X, Y);每步讀游標,游標沒動就停
  python lc191.py endturn NAME LABEL               # 游標格必須沒有單位(state 讀)→ Return → 等 E 0x16f55 增加 → Down → Return
                                                   #   → 截圖要讀到「結束」字樣才 Return(YES)
  python lc191.py calls NAME                       # 各入口目前的 E 筆數(只讀檔)
  python lc191.py down NAME                        # teardown,取 CALLLOG.TXT 指紋並複製到 .wsl_build/lc191_live/
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
OD = REPO / ".wsl_build" / "lc191_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s191"
ENTRY_FILE = f"{ENTRY_DIR}/entries.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x"
DOS_TIME = "12:00:54"
NAMES = ("lc191a", "lc191b", "lc191c", "lc191d", "lc191e")
MAPPER = f"{ENTRY_DIR}/passthrough_s191.map"   # lc191c / lc191d:解除 hand_copyall(Ctrl+F5)/ hand_ejectpage(Ctrl+F2)
CHAPTER, REGS_AL, TOWN_SEL = 0x53C03, 0x53A8D, 0x53F4A   # s191_H:章節 byte、union REGS(AL, AH)、town selection
DELTA = 0x19C000
# 靜態位址(執行期 + DELTA)
ENTRIES = {
    "input_loop": 0x117E7, "ring": 0x16F55, "select": 0x18890, "advance": 0x1A30B, "friendly": 0x1D80B,
    "enemy_ai": 0x1D8BA, "status_card": 0x17AED,
    "step_b0": 0x12EAA, "step_left": 0x1300D, "step_b2": 0x13185, "step_b3": 0x13315, "path": 0x13488,
    "field_event": 0x13A44,
    "ev62": 0x35BEE, "ev63": 0x35C1D, "staging": 0x35B78, "pan": 0x135DD, "spawn": 0x10B4E,
    "delay": 0x3790A, "palette": 0x11DF2, "redraw": 0x11CAC, "camp_scan": 0x1A813, "post_scan": 0x1A866,
    "recalc": 0x1B750, "step_sfx": 0x32230,
}
INPUT_LOOP, RING = ENTRIES["input_loop"], ENTRIES["ring"]
ROUND = 0x53BEF               # 0x1a5b9 inc dword ptr [0x3bef]
TURN_ROWS_PTR = 0x53A55       # 0x1a831 mov ecx, dword ptr [0x3a55];列 = ptr + 3*i,+3 回合、+4 event、+5 camp
EVSTATE_PTR = 0x53AD5         # 0x35bf8 mov eax, dword ptr [0x3ad5];event62 讀寫 +0x11
CURSOR_X, CURSOR_Y = 0x53AB1, 0x53AB5
MAP_PTR = 0x53A51             # 地圖構成指標(續五十二 collect_targets_in_range 讀法:+7 + 4*(y*W + x) 是標記)
UNITS_PTR, UNIT_COUNT, UNIT_SIZE = 0x53A45, 0x53BEB, 0x50
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
        lines = "\\n".join(f"{a + DELTA:08x}" for a in sorted(set(ENTRIES.values())))
        print(wsl(f"mkdir -p {ENTRY_DIR} && printf '{lines}\\n' > {ENTRY_FILE} && wc -l {ENTRY_FILE} && md5sum {ENTRY_FILE}"))
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = DOSBOX_BIN
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "2000000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "32"
        os.environ["FD2_HARNESS_CALLLOG_ICOUNT"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_SLICES"] = "1"
        os.environ["FD2_HARNESS_DOS_TIME"] = DOS_TIME
        os.environ["FD2_HARNESS_CALLLOG_PICEV"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_KBD"] = "1"
        if name == "lc191c":
            os.environ["FD2_HARNESS_MAPPER"] = MAPPER
        else:
            os.environ.pop("FD2_HARNESS_MAPPER", None)
        for v in ("FD2_HARNESS_CALLLOG_GATE", "FD2_HARNESS_CALLLOG_TRIG", "FD2_HARNESS_CALLLOG_TRIGCAP",
                  "FD2_HARNESS_CALLLOG_TRIGRING", "FD2_HARNESS_CALLLOG_TRIGPRE",
                  "FD2_HARNESS_CALLLOG_TRIGT", "FD2_HARNESS_CALLLOG_SEGS", "FD2_HARNESS_CALLLOG_IO"):
            os.environ.pop(v, None)
        extra = ("FD2_HARNESS_DOSBOX_BIN", "FD2_HARNESS_CALLLOG", "FD2_HARNESS_CALLLOG_CAP",
                 "FD2_HARNESS_CALLLOG_DUMP", "FD2_HARNESS_CALLLOG_ICOUNT",
                 "FD2_HARNESS_CALLLOG_SLICES", "FD2_HARNESS_DOS_TIME", "FD2_HARNESS_CALLLOG_PICEV",
                 "FD2_HARNESS_CALLLOG_KBD", "FD2_HARNESS_MAPPER")
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in extra if v not in w])
        import fd2_original_verify as ov  # noqa: E402
        steps = [{"op": "poll_title", "max_tries": 30, "wait": 1.0}, {"op": "shot", "label": "title_menu"}]
        if len(argv) > 2:                   # lc191b:槽 0 章節 byte(既有 patch_chapter,只改工作目錄那份 FD2.SAV)
            steps.insert(0, {"op": "patch_chapter", "value": int(argv[2])})
        out = OD / "cl"                    # 截圖與 run json 不進 repo
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = ov.Runner({"name": name, "instance": name, "steps": steps, "keepalive": 14400}, out, True).run()
        res = {"ok": r.ok, "error": r.error, "t_host": [t0, time.time()],
               "assertions": [(a.name, a.ok, a.detail) for a in r.assertions], "shots": r.shots}
        (out / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        log_event(name, {"op": "run", "ok": r.ok})
        print(res)
        print(wsl(f"md5sum {wd}/FD2.EXE {wd}/FD2.SAV; ls -la {wd}/CALLLOG.TXT; head -1 {wd}/CALLLOG.TXT | cut -c1-300"))
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
                         "complete": [b["string_hex"] for b in res.get("boxes", []) if b["complete"]],
                         "lines": [ln["text"] for ln in res.get("lines", [])]})
        print(shot, show_text(res))
        return res

    def dump(label: str, lin: int, ln: int) -> bytes:
        out = OD / "cl" / name / f"{label}.bin"
        _p, size = lh.mem_dump(name, "0170", f"{lin:x}", f"{ln:x}", out)
        b = out.read_bytes()
        if size != ln or len(b) != ln:
            raise RuntimeError(f"{label}: 讀到 {size} / {len(b)} bytes,要 {ln}")
        return b

    def halt() -> None:
        lh.enter_debugger(name)
        if not lh.wait_halted(name):
            raise RuntimeError("debugger 沒停住")

    def cursor() -> tuple[int, int]:
        halt()
        x = dump("_cx", CURSOR_X + DELTA, 1)[0]
        y = dump("_cy", CURSOR_Y + DELTA, 1)[0]
        lh.resume(name)
        return x, y

    def read_state(label: str) -> dict:
        halt()
        uptr = u32(dump(f"{label}_uptr", UNITS_PTR + DELTA, 4))
        if uptr == 0:
            lh.resume(name)
            raise RuntimeError("單位表指標讀到 0(停在 DOS 呼叫裡?),不讀")
        rnd = u32(dump(f"{label}_round", ROUND + DELTA, 4))
        rows_ptr = u32(dump(f"{label}_rowsptr", TURN_ROWS_PTR + DELTA, 4))
        rows = dump(f"{label}_rows", rows_ptr, 3 + 16 * 3)
        ev_ptr = u32(dump(f"{label}_evptr", EVSTATE_PTR + DELTA, 4))
        evs = dump(f"{label}_evstate", ev_ptr, 0x20)
        cx, cy = dump(f"{label}_cx", CURSOR_X + DELTA, 1)[0], dump(f"{label}_cy", CURSOR_Y + DELTA, 1)[0]
        ucnt = u32(dump(f"{label}_ucnt", UNIT_COUNT + DELTA, 4)) & 0xFF
        units = dump(f"{label}_units", uptr, UNIT_SIZE * 96)
        print(lh.resume(name))
        st = {"label": label, "round": rnd, "rows_ptr": hex(rows_ptr),
              "turn_rows": [list(rows[3 + 3 * i:6 + 3 * i]) for i in range(16)],
              "evstate_ptr": hex(ev_ptr), "evstate": evs.hex(), "evstate_0x11": evs[0x11],
              "cursor": [cx, cy], "units_ptr": hex(uptr), "unit_count": ucnt,
              "units": [{"i": k, "xy": [units[k * UNIT_SIZE], units[k * UNIT_SIZE + 1]],
                         "p5": units[k * UNIT_SIZE + 5], "p7": units[k * UNIT_SIZE + 7],
                         "p8": units[k * UNIT_SIZE + 8]} for k in range(min(ucnt, 96))]}
        (OD / "cl" / name / f"{label}.json").write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n",
                                                        encoding="utf-8", newline="\n")
        log_event(name, {"op": "state", **{k: v for k, v in st.items() if k != "units"}})
        return st

    if cmd == "key":
        label, wait, keys = argv[2], float(argv[3]), argv[4:]
        for k in keys:
            log_event(name, {"op": "key", "key": k, "label": label})
            lh.send_keys(name, [lh.resolve_key(k)])
            time.sleep(wait)
        shot_text(label)
        return 0
    if cmd == "xkey":
        # 同 key,但 harness 改用 XTEST(FD2_HARNESS_KEY_MODE=xtest:xdotool key --clearmodifiers)
        os.environ["FD2_HARNESS_KEY_MODE"] = "xtest"
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        if "FD2_HARNESS_KEY_MODE" not in w:
            os.environ["WSLENV"] = ":".join(w + ["FD2_HARNESS_KEY_MODE"])
        label, wait, keys = argv[2], float(argv[3]), argv[4:]
        for k in keys:
            log_event(name, {"op": "xkey", "key": k, "label": label})
            lh.send_keys(name, [lh.resolve_key(k)])
            time.sleep(wait)
        shot_text(label)
        return 0
    if cmd == "text":
        shot_text(argv[2])
        return 0
    if cmd == "marks":
        # 選取單位後的移動範圍:地圖構成 [0x53a51](4 bytes 標頭 w, h,之後每格 4 bytes),每格 +3 是範圍標記
        label = argv[2]
        halt()
        mptr = u32(dump(f"{label}_mapptr", MAP_PTR + DELTA, 4))
        hdr = dump(f"{label}_maphdr", mptr, 4)
        w, h = int.from_bytes(hdr[:2], "little"), int.from_bytes(hdr[2:], "little")
        m = dump(f"{label}_map", mptr, 4 + 4 * w * h)
        lh.resume(name)
        vals: dict[int, list] = {}
        for c in range(w * h):
            v = m[4 + 4 * c + 3]
            if v:
                vals.setdefault(v, []).append((c % w, c // w))
        log_event(name, {"op": "marks", "label": label, "w": w, "h": h,
                         "marks": {hex(k): v for k, v in vals.items()}})
        for k, v in sorted(vals.items()):
            print(hex(k), len(v), "ymin", min(p[1] for p in v), v if len(v) < 80 else v[:80])
        return 0
    if cmd == "tstate":
        # town hub:章節 byte、INT 16h 結果(AL, AH)、selection;只讀
        label = argv[2]
        halt()
        ch = dump(f"{label}_chapter", CHAPTER + DELTA, 1)[0]
        al, ah = dump(f"{label}_regs", REGS_AL + DELTA, 2)
        sel = u32(dump(f"{label}_sel", TOWN_SEL + DELTA, 4))
        lh.resume(name)
        st = {"label": label, "chapter_byte": ch, "al": al, "ah": ah, "sel": sel}
        (OD / "cl" / name / f"{label}.json").write_text(json.dumps(st) + "\n", encoding="utf-8", newline="\n")
        log_event(name, {"op": "tstate", **st})
        print(json.dumps(st))
        return 0
    if cmd == "inject":
        # BIOS 鍵盤緩衝注入一個 word(INT 16h 讀到的 AX = scan<<8 | ascii);只動 BDA 0x41a..0x43d,不動遊戲記憶體
        label, word = argv[2], int(argv[3], 16)
        halt()
        ht = dump(f"{label}_bda_before", 0x41A, 4)
        head, tail = int.from_bytes(ht[:2], "little"), int.from_bytes(ht[2:], "little")
        if not (0x1E <= head <= 0x3C and 0x1E <= tail <= 0x3C) or head != tail:
            lh.resume(name)
            print("BDA head / tail 不是空緩衝", hex(head), hex(tail), "不寫")
            return 1
        nt = tail + 2 if tail < 0x3C else 0x1E
        print(lh.debugger_cmd(name, f"SM 0170:{0x400 + tail:x} {word & 0xFF:02x} {word >> 8:02x}"))
        print(lh.debugger_cmd(name, f"SM 0170:41c {nt & 0xFF:02x} {nt >> 8:02x}"))
        buf = dump(f"{label}_bda_slot", 0x400 + tail, 2)
        ht2 = dump(f"{label}_bda_after", 0x41A, 4)
        ok = int.from_bytes(buf, "little") == word and int.from_bytes(ht2[2:], "little") == nt
        log_event(name, {"op": "inject", "label": label, "word": hex(word), "head": hex(head), "tail": hex(tail),
                         "new_tail": hex(nt), "readback_ok": ok})
        print("readback", buf.hex(), ht2.hex(), ok)
        lh.resume(name)
        return 0 if ok else 1
    if cmd == "kbd":
        # 最近 N 筆 K 紀錄(guest 鍵盤控制器收到的 scan code)
        n = int(argv[2]) if len(argv) > 2 else 12
        out = wsl(f"grep -E '^K ' {wd}/CALLLOG.TXT | tail -{n}")
        log_event(name, {"op": "kbd", "tail": out.splitlines()})
        print(out)
        return 0
    if cmd == "calls":
        res = {k: count(a) for k, a in ENTRIES.items()}
        log_event(name, {"op": "calls", **res})
        print(json.dumps(res))
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
        ok, n = sw.ensure_battle_hud(name, d, log, label, max_clears=80, panel_gate=True,
                                     control_probe=lambda: (count(INPUT_LOOP) or 0) > base)
        log_event(name, {"op": "hud_done", "label": label, "ok": ok, "returns": n, "loop_E": count(INPUT_LOOP)})
        print(ok, n, "\n".join(log[-8:]))
        return 0 if ok else 1
    if cmd == "state":
        st = read_state(argv[2])
        brief = {k: v for k, v in st.items() if k not in ("units", "turn_rows", "evstate")}
        print(json.dumps(brief, ensure_ascii=False))
        print("rows", st["turn_rows"][:3])
        print("units", [(u["i"], tuple(u["xy"]), hex(u["p5"]), u["p7"], u["p8"]) for u in st["units"]])
        return 0
    if cmd == "goto":
        label, tx, ty = argv[2], int(argv[3]), int(argv[4])
        mx = int(argv[5]) if len(argv) > 5 else 30
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
    if cmd == "endturn":
        label = argv[2]
        st = read_state(f"{label}_pre")
        occ = [u["i"] for u in st["units"] if u["xy"] == st["cursor"]]
        if occ:
            print("游標格有單位", occ, "不開環")
            return 1
        base = count(RING)
        if base is None:
            print("CALLLOG 讀不到,不送鍵")
            return 1
        log_event(name, {"op": "endturn", "label": label, "ring_E_base": base, "cursor": st["cursor"]})
        lh.send_keys(name, [lh.resolve_key("Return")])
        t0 = time.time()
        while (count(RING) or 0) <= base:
            if time.time() - t0 > 8:
                shot_text(f"{label}_ring_timeout")
                print("8 秒內沒有新的 E 0x16f55,停(沒送 Down)")
                return 1
            time.sleep(0.5)
        time.sleep(0.4)
        lh.send_keys(name, [lh.resolve_key("Down")])
        time.sleep(0.5)
        lh.send_keys(name, [lh.resolve_key("Return")])
        time.sleep(1.0)
        res = shot_text(f"{label}_prompt")
        if not any("結束" in ln["text"] for ln in res.get("lines", [])):
            print("畫面沒有「結束」字樣,停(沒送 YES)")
            return 1
        log_event(name, {"op": "endturn_yes", "label": label})
        lh.send_keys(name, [lh.resolve_key("Return")])
        time.sleep(1.0)
        shot_text(f"{label}_after")
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
