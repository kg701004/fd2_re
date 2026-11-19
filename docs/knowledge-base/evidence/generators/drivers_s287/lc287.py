"""續二百八十七 實機(使用者 2026-11-19「依照你的建議自動逐項進行」;實機「永遠核准」):
0x52dfc 計時器 ISR 堆疊高水位、0x53730 / 0x54630 兩個 DOS extender 緩衝在 DOSBox-X 下是否被寫。

只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL -d Ubuntu、預設 harness dosbox-x;預測在 pred287.txt(跑之前)。
不寫記憶體、不下斷點;讀取 = debugger MEMDUMPBIN 0170(執行期位址 = LE 線性 + 0x19C000,續一百九十二)。

用法:
  python lc287.py run NAME          # 開機到標題選單(fd2_original_verify poll_title),instance 留著
  python lc287.py dump NAME LABEL   # 進 debugger 讀 4 段 + 對照字串,寫 .bin 與 LABEL.json,再 resume
  python lc287.py key NAME KEY WAIT # 送一個鍵,等 WAIT 秒
  python lc287.py down NAME
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
import fd2_dosbox_live_helper as lh  # noqa: E402

OD = REPO / ".wsl_build" / "lc287_live"
DELTA = 0x19C000
RANGES = {"isr_stack": (0x52DFC, 0x800 + 8), "sysreg": (0x53730, 0x40), "fa20": (0x54630, 0x80),
          "ctl_dos4g": (0x51760, 0x10), "ctl_tz": (0x516F0, 3), "fpu": (0x527F4, 2), "emu_flags": (0x53920, 2)}


def log_event(name: str, rec: dict) -> None:
    OD.mkdir(parents=True, exist_ok=True)
    with (OD / f"{name}_keys.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"t": time.time(), **rec}, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, name = argv[0], argv[1]
    if cmd == "run":
        import fd2_original_verify as ov  # noqa: PLC0415
        steps = [{"op": "poll_title", "max_tries": 30, "wait": 1.0}, {"op": "shot", "label": "title_menu"}]
        OD.mkdir(parents=True, exist_ok=True)
        r = ov.Runner({"name": name, "instance": name, "steps": steps, "keepalive": 7200}, OD, True).run()
        res = {"ok": r.ok, "error": r.error, "assertions": [(a.name, a.ok, a.detail) for a in r.assertions]}
        log_event(name, {"op": "run", **res})
        print(res)
        return 0 if r.ok else 1
    if cmd == "key":
        key, wait = argv[2], float(argv[3])
        print(lh.send_keys(name, [key]))
        log_event(name, {"op": "key", "key": key})
        time.sleep(wait)
        return 0
    if cmd == "dump":
        label = argv[2]
        out = OD / name / label
        got = {}
        # 停在 real mode(DOS / BIOS 呼叫中)時 0170 不是選擇子:resume、等、重進,最多 8 次(同 lc192 READ_TRIES)
        for attempt in range(8):
            print(lh.enter_debugger(name))
            if not lh.wait_halted(name, timeout=8.0):
                print(lh.resume(name))
                raise SystemExit("debugger 沒有停住,不讀")
            # 標題畫面一直停在 real mode(等鍵的 BIOS 呼叫):第 4 次起改用選擇子 0 = 平面線性讀(helper 的建議);
            # 讀到的是不是本程式的資料區由對照字串 ctl_ok 判定,不成立整筆作廢
            sel = "0170" if attempt < 3 else "0"
            try:
                for k, (lin, n) in RANGES.items():
                    p, size = lh.mem_dump(name, sel, f"{lin + DELTA:x}", f"{n:x}", out / f"{k}.bin")
                    b = p.read_bytes()
                    if size != n or len(b) != n:
                        raise RuntimeError(f"{k}: 讀到 {size} / {len(b)},要 {n}")
                    got[k] = b.hex()
                log_event(name, {"op": "read_ok", "label": label, "attempt": attempt})
                break
            except RuntimeError as e:
                got = {}
                log_event(name, {"op": "read_retry", "label": label, "attempt": attempt, "err": str(e)[-200:]})
            finally:
                print(lh.resume(name))
            time.sleep(0.4)
        if not got:
            raise SystemExit("8 次都讀不到(一直停在 real mode)")
        st = bytes.fromhex(got["isr_stack"])[:0x800]
        nz = [i for i, x in enumerate(st) if x]
        rec = {"label": label, "ctl_ok": bytes.fromhex(got["ctl_dos4g"]) == b"RATIONAL DOS/4G\0"
               and bytes.fromhex(got["ctl_tz"]) == b"TZ\0",
               "isr_lowest_nonzero": hex(0x52DFC + nz[0]) if nz else None,
               "isr_high_water": (0x800 - nz[0]) if nz else 0,
               "sysreg_nonzero": [i for i, x in enumerate(bytes.fromhex(got["sysreg"])) if x],
               "fa20_nonzero": [i for i, x in enumerate(bytes.fromhex(got["fa20"])) if x],
               "fpu": got["fpu"], "emu_flags": got["emu_flags"], "raw": got}
        (out / f"{label}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        log_event(name, {"op": "dump", "label": label})
        print({k: v for k, v in rec.items() if k != "raw"})
        return 0 if rec["ctl_ok"] else 1
    if cmd == "down":
        print(lh.teardown(name))
        log_event(name, {"op": "down"})
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
