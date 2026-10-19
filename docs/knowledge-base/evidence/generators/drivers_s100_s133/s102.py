# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百零二:原版 FD2.EXE 第 1 章戰場,只在敵方回合錄 LOGC(只對原版 EXE,WSL -d Ubuntu,instance s102)。

用法:
  python s102.py go                 # 開新 instance、第 1 章、走到戰場(recon 路線)
  python s102.py k <wait> <key...>  # 送鍵 → 等 → 截圖
  python s102.py shot [tag]
  python s102.py pane
  python s102.py dbg <text...>      # 除錯器指令(需已停住)
  python s102.py halt | run
  python s102.py rd <addr> [n]      # 讀記憶體(已停住;線性位址 hex)
  python s102.py units              # 傾印單位表(80 B/筆)
  python s102.py logc               # 開始錄(需已停住;會恢復執行)
  python s102.py stop <name>        # 停住、改名、去重成 <name>_unique_cseip.txt
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
import fd2_chapter_sweep as sw  # noqa: E402
import fd2_original_verify as ov  # noqa: E402

NAME = "s102"
OUT = Path(__file__).resolve().parent / "s102"
WD = f"/home/kg701004/fd2-run-harness-{NAME}"


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def pane() -> str:
    return wsl(f"tmux -L fd2harness capture-pane -t harness-{NAME} -p")


def running() -> bool:
    lines = [x for x in pane().splitlines() if x.strip()]
    return bool(lines) and "Running" in lines[-1]


def wait_halt(max_s: float = 30) -> bool:
    t0 = time.time()
    while time.time() - t0 < max_s:
        if not running():
            return True
        time.sleep(1)
    return False


def dbg(text: str) -> None:
    sw.debugger_cmd(NAME, text)
    time.sleep(0.5)


_n = [0]


def shot(tag: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    k = len(list(OUT.glob("*.png"))) + 1
    p = OUT / f"{k:03d}_{tag}.png"
    sw.screenshot(NAME, p)
    return p


def rd(addr: int, n: int = 16) -> bytes:
    out = bytearray()
    while len(out) < n:
        b = sw.read_mem(NAME, addr + len(out), min_bytes=min(16, n - len(out)))
        if b is None:
            raise RuntimeError(f"read failed at {addr + len(out):#x}")
        out += b[:16]
    return bytes(out[:n])


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "go":
        keys = "Return,Return,Return,Escape,Right,Right,Right,Return,Return,Return,Return".split(",")
        steps = [{"op": "patch_chapter", "value": 1}, {"op": "poll_title"},
                 {"op": "keys", "keys": ["Down"], "wait": 1.0}, {"op": "shot", "label": "title_menu"}]
        for i, k in enumerate(keys):
            steps += [{"op": "keys", "keys": [k], "wait": 4.0 if k == "Return" and i < 2 else 2.2},
                      {"op": "shot", "label": f"r{i:02d}_{k}"}]
        OUT.mkdir(parents=True, exist_ok=True)
        r = ov.Runner({"name": "s102", "instance": NAME, "chapter": 1, "steps": steps}, OUT, True).run()
        print("ok", r.ok, [(a.name, a.ok, a.detail) for a in r.assertions])
        print(wsl(f"md5sum {WD}/FD2.EXE"))
    elif cmd == "k":
        sw.send_keys(NAME, *argv[2:])
        time.sleep(float(argv[1]))
        print(shot("_".join(argv[2:])[:40]))
    elif cmd == "shot":
        print(shot(argv[1] if len(argv) > 1 else "s"))
    elif cmd == "pane":
        print(pane())
    elif cmd == "dbg":
        dbg(" ".join(argv[1:]))
        print("\n".join(pane().splitlines()[-6:]))
    elif cmd == "halt":
        sw.enter_debugger(NAME)
        print("halted", wait_halt(20))
    elif cmd == "run":
        dbg("BPDEL *")
        dbg("RUN")
        print("running", running())
    elif cmd == "rd":
        a = int(argv[1], 16)
        n = int(argv[2], 16) if len(argv) > 2 else 16
        b = rd(a, n)
        for i in range(0, len(b), 16):
            print(f"{a + i:08x} " + " ".join(f"{x:02x}" for x in b[i:i + 16]))
    elif cmd == "units":
        ptr = int.from_bytes(rd(0x53a45 + 0x19c000, 4), "little")
        cnt = rd(0x53beb + 0x19c000, 1)[0]
        print(f"ptr {ptr:#x} count {cnt}")
        if ptr != 0x26bdc8:
            print("WARNING: unexpected unit pointer (real-mode halt?)")
            return 1
        for i in range(cnt):
            b = rd(ptr + i * 80, 80)
            print(f"#{i:2d} @{ptr + i * 80:08x} xy=({b[0]},{b[1]}) +5={b[5]:02x} +7={b[7]:02x} +8={b[8]:02x} "
                  f"slot0={b[0xa]:02x},{b[0xb]:02x} spells={b[0x1a:0x1f].hex()} "
                  f"hp={int.from_bytes(b[0x40:0x42], 'little')}/{int.from_bytes(b[0x42:0x44], 'little')} "
                  f"mp={int.from_bytes(b[0x44:0x46], 'little')}/{int.from_bytes(b[0x46:0x48], 'little')}")
    elif cmd == "logc":
        print(wsl(f"ls -la {WD}/LOGCPU.TXT 2>&1"))
        dbg("LOGC 7FFFFFFF")
        time.sleep(2)
        print("running", running(), wsl(f"stat -c %s {WD}/LOGCPU.TXT"))
    elif cmd == "stop":
        name = argv[1]
        if running():
            sw.enter_debugger(NAME)
            wait_halt(20)
        print(wsl(f"cd {WD} && mv LOGCPU.TXT raw_{name}.TXT && ls -la raw_{name}.TXT && head -2 raw_{name}.TXT "
                  f"&& awk '!seen[$0]++' raw_{name}.TXT > {name}_unique_cseip.txt && wc -l {name}_unique_cseip.txt",
                  timeout=3600))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
