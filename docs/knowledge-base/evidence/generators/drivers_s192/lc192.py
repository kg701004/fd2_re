"""續一百九十二 實機(使用者 2026-11-04「仍未解決 請新建工具 對應處理每個未解決項目」;「永遠核准」):
續一百九十一留下的四項 —— (1) R6 event63 不重複觸發、(2) 物理攻擊音效實機序列、(3) event 82 實機觀察、
(4) DOSBox-X 完整 pass-through mapper(真按 Ctrl+F2 / Ctrl+F5)。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu;預測寫在 pred192*.txt(跑之前)。
dosbox-x 同 lc191(~/fd2-dosbox-calllog4);入口檔是本輪自己的清單(ENTRIES,寫到 ~/fd2-calllog-s192/entries.txt)。
與 lc191 的差別:
- debugger 讀取(halt + dump)失敗時(續一百九十一 lc191a 的 real mode 讀取失敗)先 resume、等、再進 debugger 重讀,
  最多 READ_TRIES 次;全部失敗就丟例外、這個指令不送任何鍵(該步驟以非 0 結束,呼叫端用 && 串接)。
- ENTRIES 多了物理攻擊場景的分支探針(非函式入口的 EIP 也記 E:fd2_calllog_patch 是每條指令比 EIP):
  0x2ed11(0x2f7b6 算完結果、s2 = 結果結構指標)、0x2efdb(命中幀 + 命中)、0x2efea(命中幀 + 未命中)、
  0x2eff6(一般幀)、0x2f179(會心閃白分支)、0x25a96(放音效);event 81 / 82、獎勵 dispatch、town gate 寫 sel 5。
- `run NAME [CHAPTER] [mapper]`:mapper = 帶 tools/dosbox/passthrough.map(make_passthrough_map.py 產生的完整檔)。
- `wait`:等某入口的 E 筆數到 N(只讀 CALLLOG)、`poke`:寫一段遊戲記憶體並讀回(只在預測檔先寫明理由時用)。

用法(除 run / down / calls / kbd / wait 之外都先進 debugger 讀狀態或截圖判讀):
  python lc192.py run NAME [CHAPTER] [mapper]
  python lc192.py key NAME LABEL WAIT K1 [K2 ...]   # 逐鍵送出、截圖判讀文字
  python lc192.py text NAME LABEL
  python lc192.py state NAME LABEL                  # 回合、回合列、evstate、游標、單位表(含 HP)
  python lc192.py tstate NAME LABEL [SEL]           # town:章節 byte、INT 16h AL/AH、selection;給 SEL 時不符就非 0
  python lc192.py goto NAME LABEL X Y [MAX]
  python lc192.py endturn NAME LABEL
  python lc192.py hud NAME LABEL
  python lc192.py marks NAME LABEL
  python lc192.py wait NAME LABEL ENTRY N TIMEOUT   # ENTRY = ENTRIES 的鍵名
  python lc192.py poke NAME LABEL ADDR HEX          # ADDR = 執行期線性位址(十六進位)
  python lc192.py bpreg NAME LABEL EIP REG VAL CREG CVAL KEY
        # 斷點 EIP(執行期)→ 送 KEY → 停住且 CREG == CVAL 才 SR REG VAL;一律刪斷點、繼續
  python lc192.py calls NAME / kbd NAME [N] / down NAME
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
OD = REPO / ".wsl_build" / "lc192_live"

ENTRY_DIR = "/home/kg701004/fd2-calllog-s192"
ENTRY_FILE = f"{ENTRY_DIR}/entries.txt"
DOSBOX_BIN = "/home/kg701004/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x"
DOS_TIME = "12:00:54"
NAMES = ("lc192a", "lc192b", "lc192c", "lc192d", "lc192e", "lc192f", "lc192g", "lc192h")
MAPPER_SRC = REPO / "tools" / "dosbox" / "passthrough.map"
MAPPER = f"{ENTRY_DIR}/passthrough.map"
CHAPTER, REGS_AL, TOWN_SEL = 0x53C03, 0x53A8D, 0x53F4A
DELTA = 0x19C000
READ_TRIES = 6
ENTRIES = {
    "input_loop": 0x117E7, "ring": 0x16F55, "select": 0x18890, "advance": 0x1A30B, "enemy_ai": 0x1D8BA,
    "step_tail": 0x13175, "path": 0x13488, "field_event": 0x13A44,
    "ev62": 0x35BEE, "ev63": 0x35C1D, "staging": 0x35B78, "spawn": 0x10B4E, "camp_scan": 0x1A813,
    "ev81": 0x362C5, "ev82": 0x362E8, "reward_ev": 0x1AC0A, "dialog": 0x15F84,
    "attack_scene": 0x2EBE1, "result_calc": 0x2F7B6, "after_result": 0x2ED11,
    "hitframe_hit": 0x2EFDB, "hitframe_miss": 0x2EFEA, "normal_frame": 0x2EFF6, "crit_flash": 0x2F179,
    "play_sfx": 0x25A96, "town_sel5": 0x26572,
}
INPUT_LOOP, RING = ENTRIES["input_loop"], ENTRIES["ring"]
ROUND = 0x53BEF
TURN_ROWS_PTR = 0x53A55
EVSTATE_PTR = 0x53AD5
CURSOR_X, CURSOR_Y = 0x53AB1, 0x53AB5
MAP_PTR = 0x53A51
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


def u16(b: bytes, o: int = 0) -> int:
    return int.from_bytes(b[o:o + 2], "little")


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
        use_mapper = "mapper" in argv[2:]
        chap = [a for a in argv[2:] if a != "mapper"]
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = DOSBOX_BIN
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "2000000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "32"
        os.environ["FD2_HARNESS_CALLLOG_ICOUNT"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_SLICES"] = "1"
        os.environ["FD2_HARNESS_DOS_TIME"] = DOS_TIME
        os.environ["FD2_HARNESS_CALLLOG_PICEV"] = "1"
        os.environ["FD2_HARNESS_CALLLOG_KBD"] = "1"
        if use_mapper:
            src = MAPPER_SRC.as_posix().replace("C:/", "/mnt/c/")
            # 續一百九十三:harness 的 mapper_guard 要求 "<mapper>.binmd5" 列有 DOSBOX_BIN 的 md5,一起複製
            print(wsl(f"cp '{src}' {MAPPER} && cp '{src}.binmd5' {MAPPER}.binmd5 && md5sum '{src}' {MAPPER} "
                      f"&& wc -l {MAPPER} && grep -x \"$(md5sum {DOSBOX_BIN} | cut -d' ' -f1)\" {MAPPER}.binmd5"))
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
        if chap:                            # 槽 0 章節 byte(既有 patch_chapter,只改工作目錄那份 FD2.SAV)
            steps.insert(0, {"op": "patch_chapter", "value": int(chap[0])})
        out = OD / "cl"
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = ov.Runner({"name": name, "instance": name, "steps": steps, "keepalive": 14400}, out, True).run()
        res = {"ok": r.ok, "error": r.error, "t_host": [t0, time.time()], "mapper": use_mapper,
               "assertions": [(a.name, a.ok, a.detail) for a in r.assertions], "shots": r.shots}
        (out / f"{name}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        log_event(name, {"op": "run", "ok": r.ok, "mapper": use_mapper, "chapter": chap})
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

    def halted(label: str, reader):
        """進 debugger 跑 reader();任何讀取失敗 → resume、等 0.4 s、重來(最多 READ_TRIES 次)。
        成功與失敗都記進時間軸;全部失敗丟 RuntimeError(呼叫端不再送鍵)。"""
        last = None
        for k in range(READ_TRIES):
            try:
                lh.enter_debugger(name)
                if not lh.wait_halted(name):
                    raise RuntimeError("debugger 沒停住")
                v = reader()
                lh.resume(name)
                log_event(name, {"op": "read_ok", "label": label, "try": k, "eip": None})
                return v
            except (RuntimeError, ValueError) as e:  # mem_dump 失敗 / SIZE 不符 / 指標為 0
                last = e
                eip = lh.read_eip(name)
                log_event(name, {"op": "read_retry", "label": label, "try": k, "err": str(e)[:300],
                                 "eip": None if eip is None else hex(eip)})
                print(f"讀取失敗(第 {k + 1} 次,EIP {eip if eip is None else hex(eip)}):{e}")
                lh.resume(name)
                time.sleep(0.4)
        raise RuntimeError(f"{label}:{READ_TRIES} 次都讀不到:{last}")

    def cursor() -> tuple[int, int]:
        return halted("_cursor", lambda: (dump("_cx", CURSOR_X + DELTA, 1)[0], dump("_cy", CURSOR_Y + DELTA, 1)[0]))

    def read_state(label: str) -> dict:
        def rd() -> dict:
            uptr = u32(dump(f"{label}_uptr", UNITS_PTR + DELTA, 4))
            if uptr == 0:
                raise RuntimeError("單位表指標讀到 0(停在 DOS 呼叫裡?)")
            rnd = u32(dump(f"{label}_round", ROUND + DELTA, 4))
            rows_ptr = u32(dump(f"{label}_rowsptr", TURN_ROWS_PTR + DELTA, 4))
            rows = dump(f"{label}_rows", rows_ptr, 3 + 16 * 3)
            ev_ptr = u32(dump(f"{label}_evptr", EVSTATE_PTR + DELTA, 4))
            evs = dump(f"{label}_evstate", ev_ptr, 0x20)
            cx, cy = dump(f"{label}_cx", CURSOR_X + DELTA, 1)[0], dump(f"{label}_cy", CURSOR_Y + DELTA, 1)[0]
            ucnt = u32(dump(f"{label}_ucnt", UNIT_COUNT + DELTA, 4)) & 0xFF
            units = dump(f"{label}_units", uptr, UNIT_SIZE * 96)
            return {"label": label, "round": rnd, "rows_ptr": hex(rows_ptr),
                    "turn_rows": [list(rows[3 + 3 * i:6 + 3 * i]) for i in range(16)],
                    "evstate_ptr": hex(ev_ptr), "evstate": evs.hex(), "evstate_0x10": evs[0x10],
                    "evstate_0x11": evs[0x11], "cursor": [cx, cy], "units_ptr": hex(uptr), "unit_count": ucnt,
                    "units": [{"i": k, "xy": [units[k * UNIT_SIZE], units[k * UNIT_SIZE + 1]],
                               "p5": units[k * UNIT_SIZE + 5], "p6": units[k * UNIT_SIZE + 6],
                               "p7": units[k * UNIT_SIZE + 7], "p8": units[k * UNIT_SIZE + 8],
                               "hp": u16(units, k * UNIT_SIZE + 0x40), "mhp": u16(units, k * UNIT_SIZE + 0x42)}
                              for k in range(min(ucnt, 96))]}
        st = halted(label, rd)
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
    if cmd == "text":
        shot_text(argv[2])
        return 0
    if cmd == "marks":
        label = argv[2]

        def rd() -> tuple[int, int, bytes]:
            mptr = u32(dump(f"{label}_mapptr", MAP_PTR + DELTA, 4))
            hdr = dump(f"{label}_maphdr", mptr, 4)
            w_, h_ = u16(hdr, 0), u16(hdr, 2)
            return w_, h_, dump(f"{label}_map", mptr, 4 + 4 * w_ * h_)
        w, h, m = halted(label, rd)
        vals: dict[int, list] = {}
        for c in range(w * h):
            v = m[4 + 4 * c + 3]
            if v:
                vals.setdefault(v, []).append((c % w, c // w))
        log_event(name, {"op": "marks", "label": label, "w": w, "h": h,
                         "marks": {hex(k): v for k, v in vals.items()}})
        for k, v in sorted(vals.items()):
            print(hex(k), len(v), v if len(v) < 80 else v[:80])
        return 0
    if cmd == "tstate":
        label = argv[2]

        def rd() -> dict:
            ch = dump(f"{label}_chapter", CHAPTER + DELTA, 1)[0]
            al, ah = dump(f"{label}_regs", REGS_AL + DELTA, 2)
            sel = u32(dump(f"{label}_sel", TOWN_SEL + DELTA, 4))
            return {"label": label, "chapter_byte": ch, "al": al, "ah": ah, "sel": sel}
        st = halted(label, rd)
        (OD / "cl" / name / f"{label}.json").write_text(json.dumps(st) + "\n", encoding="utf-8", newline="\n")
        log_event(name, {"op": "tstate", **st})
        print(json.dumps(st))
        # 選用第 4 個參數 = 期望的 sel:不符就非 0 結束,讓 && 串接的下一個鍵不送(續一百九十二 M6b 的教訓)
        if len(argv) > 3 and st["sel"] != int(argv[3]):
            print(f"sel {st['sel']} ≠ 期望 {argv[3]},停")
            return 1
        return 0
    if cmd == "poke":
        label, addr, data = argv[2], int(argv[3], 16), bytes.fromhex(argv[4])

        def rd() -> dict:
            before = dump(f"{label}_before", addr, len(data))
            print(lh.debugger_cmd(name, f"SM 0170:{addr:x} " + " ".join(f"{x:02x}" for x in data)))
            after = dump(f"{label}_after", addr, len(data))
            if after != data:
                raise RuntimeError(f"讀回 {after.hex()} ≠ {data.hex()}")
            return {"label": label, "addr": hex(addr), "before": before.hex(), "after": after.hex()}
        st = halted(label, rd)
        log_event(name, {"op": "poke", **st})
        print(json.dumps(st))
        return 0
    if cmd == "bpreg":
        # 下斷點 → 送一個鍵 → 等停在該 EIP → 核對一個暫存器 → 改另一個暫存器 → 刪斷點 → 繼續(續一百九十二 lc192b 介入 1)
        label, eip, reg, val, creg, cval, key = (argv[2], int(argv[3], 16), argv[4].upper(), int(argv[5], 16),
                                                 argv[6].upper(), int(argv[7], 16), argv[8])

        def regs() -> dict[str, int]:
            out: dict[str, int] = {}
            for ln in lh._pane_lines(name)[:8]:     # register view 在 pane 開頭(同 read_eip)
                for p in ln.split():
                    if "=" in p:
                        k, _, v = p.partition("=")
                        try:
                            out[k] = int(v, 16)
                        except ValueError:
                            pass
            return out
        lh.enter_debugger(name)
        if not lh.wait_halted(name):
            print("debugger 沒停住")
            return 1
        print(lh.debugger_cmd(name, "BPDEL *"))
        print(lh.debugger_cmd(name, f"BP 0170:{eip:08X}"))
        lh.resume(name)
        log_event(name, {"op": "bpreg_set", "label": label, "eip": hex(eip)})
        lh.send_keys(name, [lh.resolve_key(key)])
        t0 = time.time()
        while not lh.is_halted(name):
            if time.time() - t0 > 8:
                lh.enter_debugger(name)
                lh.wait_halted(name)
                print(lh.debugger_cmd(name, "BPDEL *"))
                lh.resume(name)
                log_event(name, {"op": "bpreg_timeout", "label": label})
                print("8 秒內沒停在斷點,已刪斷點")
                return 1
            time.sleep(0.3)
        got_eip = lh.read_eip(name)
        r = regs()
        ok = got_eip == eip and r.get(creg) == cval
        rec = {"op": "bpreg_hit", "label": label, "eip": None if got_eip is None else hex(got_eip),
               "regs": {k: hex(v) for k, v in r.items() if k in ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP")},
               "check": [creg, hex(cval)], "ok": ok}
        log_event(name, rec)
        print(json.dumps(rec))
        if ok:
            print(lh.debugger_cmd(name, f"SR {reg} {val:X}"))
            r2 = regs()
            log_event(name, {"op": "bpreg_set_reg", "label": label, "reg": reg, "value": hex(val),
                             "readback": None if reg not in r2 else hex(r2[reg])})
            print("readback", reg, None if reg not in r2 else hex(r2[reg]))
            ok = r2.get(reg) == val
        print(lh.debugger_cmd(name, "BPDEL *"))
        lh.resume(name)
        return 0 if ok else 1
    if cmd == "kbd":
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
    if cmd == "wait":
        label, ent, n, tmo = argv[2], argv[3], int(argv[4]), float(argv[5])
        t0 = time.time()
        while True:
            c = count(ENTRIES[ent])
            if c is not None and c >= n:
                break
            if time.time() - t0 > tmo:
                log_event(name, {"op": "wait_timeout", "label": label, "entry": ent, "want": n, "have": c})
                shot_text(f"{label}_timeout")
                print(f"{tmo} 秒內 {ent} 沒到 {n}(現在 {c})")
                return 1
            time.sleep(1.0)
        log_event(name, {"op": "wait_done", "label": label, "entry": ent, "want": n, "have": c,
                         "dt": time.time() - t0})
        print(f"{ent} = {c}({time.time() - t0:.1f} s)")
        shot_text(label)
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
        print("units", [(u["i"], tuple(u["xy"]), hex(u["p5"]), u["p6"], u["p7"], u["p8"], u["hp"], u["mhp"])
                        for u in st["units"]])
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
        occ = [u["i"] for u in st["units"] if u["xy"] == st["cursor"] and not u["p5"] & 1]
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
