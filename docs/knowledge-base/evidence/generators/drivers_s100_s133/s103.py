# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百零三:原版 FD2.EXE 第 1 章戰場,玩家逐一施放法術 9..27 與敵方 [0x53af9]=1 回合錄 LOGC(只對原版 EXE,WSL -d Ubuntu,instance s103)。

用法:
  python s103.py go                 # 開新 instance、第 1 章、走到戰場(recon 路線)
  python s103.py k <wait> <key...>  # 送鍵 → 等 → 截圖
  python s103.py shot [tag]
  python s103.py pane
  python s103.py dbg <text...>      # 除錯器指令(需已停住)
  python s103.py halt | run
  python s103.py rd <addr> [n]      # 讀記憶體(已停住;線性位址 hex)
  python s103.py units              # 傾印單位表(80 B/筆)
  python s103.py logc               # 開始錄(需已停住;會恢復執行)
  python s103.py stop <name>        # 停住、改名、去重成 <name>_unique_cseip.txt
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))
import fd2_chapter_sweep as sw  # noqa: E402
import fd2_original_verify as ov  # noqa: E402

_orig_wsl_run = sw.wsl_run


def _wsl_run_retry(cmd: str, timeout: int = 60, check: bool = False):
    """WSL 間歇性卡住(續一百零三):逾時放寬到至少 60 秒、最多試 3 次。"""
    env = dict(os.environ)
    env["MSYS_NO_PATHCONV"] = "1"
    full = ["wsl", "-d", "Ubuntu", "bash", "-c", cmd]
    for attempt in range(3):
        try:
            return subprocess.run(full, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=max(timeout, 60), env=env, check=check)
        except subprocess.TimeoutExpired:
            print(f"[retry {attempt + 1}] wsl timeout: {cmd[:80]}", file=sys.stderr)
    return subprocess.run(full, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=180, env=env, check=check)


sw.wsl_run = _wsl_run_retry
NAME = os.environ.get("S103_NAME", "s103")       # 續一百零三第二輪用 s103b
OUT = Path(__file__).resolve().parent / NAME
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
        b = None
        for _ in range(5):                  # pane 解析偶爾失敗(續一百零三):重試
            b = sw.read_mem(NAME, addr + len(out), min_bytes=min(16, n - len(out)))
            if b is not None:
                break
            time.sleep(1)
        if b is None:
            raise RuntimeError(f"read failed at {addr + len(out):#x}")
        out += b[:16]
    return bytes(out[:n])


def rotate() -> None:
    """已停住時:LOGCPU.TXT 改名成下一個 raw_<NAME>_<k>.TXT,再 LOGC(會恢復執行);印出舊檔是否已停止成長。"""
    k = len(wsl(f"ls {WD}/raw_{NAME}_*.TXT 2>/dev/null").split())
    old = f"{WD}/raw_{NAME}_{k}.TXT"
    print(wsl(f"mv {WD}/LOGCPU.TXT {old} && stat -c %s {old}"))
    dbg("LOGC 7FFFFFFF")             # 錄製中再下 LOGC = 關檔停錄(續一百零三實測),所以要再下一次才開新檔
    time.sleep(2)
    if "No such file" in wsl(f"stat -c %s {WD}/LOGCPU.TXT"):
        if running():
            sw.enter_debugger(NAME)
            wait_halt(20)
        dbg("LOGC 7FFFFFFF")
    time.sleep(3)
    print("rotated ->", old, "old size now", wsl(f"stat -c %s {old}"), "new", wsl(f"stat -c %s {WD}/LOGCPU.TXT"))


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
        r = ov.Runner({"name": NAME, "instance": NAME, "chapter": 1, "steps": steps}, OUT, True).run()
        print("ok", r.ok, [(a.name, a.ok, a.detail) for a in r.assertions])
        print(wsl(f"md5sum {WD}/FD2.EXE"))
    elif cmd == "k":
        sw.send_keys(NAME, *argv[2:])
        time.sleep(float(argv[1]))
        print(shot("_".join(argv[2:])[:40]))
    elif cmd == "hold":               # hold <wait> <key> [按住秒數]:keydown → 按住 → keyup(半速時 xdotool key 太快會漏)
        hold_s = float(argv[3]) if len(argv) > 3 else 0.6
        st = f"$HOME/.fd2-harness/instances/{NAME}.state"
        print(wsl(rf'P=$(grep -oP "^DISPLAY_PORT=\K.*" {st}); export DISPLAY=127.0.0.1:$P; '
                  f'W=$(xdotool search --name DOSBox | head -1); xdotool windowfocus --sync $W; '
                  f'xdotool keydown --window $W {argv[2]}; sleep {hold_s}; xdotool keyup --window $W {argv[2]}; echo held $W'))
        time.sleep(float(argv[1]))
        print(shot("hold_" + argv[2]))
    elif cmd == "cast":               # cast <法術> [目標方向鍵...]:索爾(#0)只留這個法術、清已行動、MP 補滿、游標放回索爾,再走一次施法
        sp = int(argv[1])
        bits = [0, 0, 0, 0]
        bits[sp // 8] |= 1 << (sp % 8)
        th = 0x26bdc8
        sw.enter_debugger(NAME)
        wait_halt(20)
        for i, v in enumerate(bits):
            sw.write_byte(NAME, th + 0x1a + i, v)
        sw.write_byte(NAME, th + 5, 0)
        sw.write_byte(NAME, th + 0x44, 0x25)
        sw.write_byte(NAME, th + 0x45, 0x03)
        x, y = rd(th, 2)
        sw.write_byte(NAME, 0x53ab1 + 0x19c000, x)
        sw.write_byte(NAME, 0x53ab5 + 0x19c000, y)
        b = rd(th, 0x48)
        print(f"set spell {sp}: spells={b[0x1a:0x1f].hex()} +5={b[5]:02x} mp={int.from_bytes(b[0x44:0x46], 'little')} "
              f"cursor={rd(0x53ab1 + 0x19c000, 1)[0]},{rd(0x53ab5 + 0x19c000, 1)[0]}")
        st = wsl(f"stat -c %s {WD}/LOGCPU.TXT")
        if not st.isdigit():
            raise SystemExit(f"LOGCPU.TXT 不存在,沒有在錄:{st}")
        size = int(st)
        if size > 20_000_000_000:
            rotate()
        else:
            dbg("RUN")
        time.sleep(3)
        seq = [("Return", 8), ("Return", 8), ("Left", 7), ("Return", 8), ("Return", 8)]
        seq += [(k, 7) for k in argv[2:]] + [("Return", 25)]
        for k, w in seq:
            sw.send_keys(NAME, k)
            time.sleep(w)
        print(shot(f"cast{sp}"))
        sw.enter_debugger(NAME)
        wait_halt(20)
        b = rd(th, 0x48)
        mp = int.from_bytes(b[0x44:0x46], "little")
        cost = {9: 30, 10: 18, 11: 45, 12: 80, 13: 3, 14: 10, 15: 20, 16: 40, 17: 5, 18: 5, 19: 8, 20: 5, 21: 5,
                22: 8, 23: 20, 25: 24, 26: 8, 27: 10}[sp]
        print(f"after spell {sp}: +5={b[5]:02x} mp={mp} drop={805 - mp} cost={cost} "
              f"({'CAST' if 805 - mp == cost else 'MISMATCH'})")
        dbg("RUN")
        time.sleep(2)
    elif cmd == "rotate":
        rotate()
    elif cmd == "enemy":              # 敵方回合設定(需已停住):我方 #1..#4 已行動、五人 HP 9999;盜賊 #12..#20 各會法術 0..8
        pos = {12: (18, 12), 13: (18, 13), 14: (18, 15), 15: (18, 16), 16: (17, 13), 17: (17, 14), 18: (17, 15),
               19: (19, 12), 20: (19, 16)}
        base = 0x26bdc8
        for i in range(5):
            u = base + i * 80
            for off, v in ((0x40, 0x0F), (0x41, 0x27), (0x42, 0x0F), (0x43, 0x27)):
                sw.write_byte(NAME, u + off, v)
            if i:
                sw.write_byte(NAME, u + 5, 0x80)
        for idx, (x, y) in pos.items():
            u = base + idx * 80
            sp = idx - 12
            bits = [0, 0, 0, 0, 0]
            bits[sp // 8] |= 1 << (sp % 8)
            sw.write_byte(NAME, u, x)
            sw.write_byte(NAME, u + 1, y)
            sw.write_byte(NAME, u + 0xa, 0)                 # 拿掉武器旗標,只能施法
            for j, v in enumerate(bits):
                sw.write_byte(NAME, u + 0x1a + j, v)
            for off, v in ((0x44, 100), (0x45, 0), (0x46, 100), (0x47, 0)):
                sw.write_byte(NAME, u + off, v)
        sw.write_byte(NAME, 0x53af9 + 0x19c000, 1)
        print("[0x53af9] =", rd(0x53af9 + 0x19c000, 1).hex())
        for i in list(range(5)) + [11] + list(pos):
            b = rd(base + i * 80, 0x48)
            print(f"#{i:2d} xy=({b[0]},{b[1]}) +5={b[5]:02x} slot0={b[0xa]:02x} spells={b[0x1a:0x1f].hex()} "
                  f"hp={int.from_bytes(b[0x40:0x42], 'little')}/{int.from_bytes(b[0x42:0x44], 'little')} "
                  f"mp={int.from_bytes(b[0x44:0x46], 'little')}")
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
        dbg("RUN")                       # 不送 BPDEL *:debugger-cmd 經 bash,* 會被展開成檔名
        time.sleep(2)
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
    elif cmd == "wr":                 # wr <線性位址 hex> <bytes hex...>(需已停住;寫後讀回)
        a = int(argv[1], 16)
        vals = [int(x, 16) for x in argv[2:]]
        for i, v in enumerate(vals):
            sw.write_byte(NAME, a + i, v)
        got = rd(a, len(vals))
        print("readback", got.hex(), "OK" if list(got) == vals else "MISMATCH")
    elif cmd == "size":
        print(wsl(f"stat -c %s {WD}/LOGCPU.TXT"))
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
