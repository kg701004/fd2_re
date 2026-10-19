# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百三十:沒有斷點時光束炮相位迴圈畫出哪幾階 —— 呼叫紀錄只列 5 個 EIP,遊戲途中不下任何斷點
(只對原版 FD2.EXE,WSL -d Ubuntu;只改模擬器記憶體裡的單位資料)。

用法:
  python lc130.py entries                  # 在 WSL 寫入口檔(執行期 EIP)
  python lc130.py launch NAME              # 以入口檔開 instance 到第 1 章戰場(cycles 5000,harness 預設)
  python lc130.py hud NAME                 # 清對話直到戰場 HUD
  python lc130.py arm NAME                 # 停住:敵 #11 搬到 (19, 14)、slot2 = 道具 79;#1 HP 782、索爾 HP 823;
                                           #   #1..#4 設已行動、索爾清已行動;**不下斷點**;恢復
  python lc130.py endturn NAME             # 結束回合(sweep 的 confirm_end_turn)
  python lc130.py bplist NAME              # 停住印斷點清單(應為空)後恢復
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))

ENTRY_DIR = "/home/kg701004/fd2-calllog-s130"
ENTRY_FILE = f"{ENTRY_DIR}/entries_phase.txt"
# 原生位址(FD2.EXE 反組譯);執行期 = 原生 + 0x19c000
NATIVE = {
    0x152A0: "相位迴圈每圈開頭(ebx = k,寫 [0x53c1f] 之前)",
    0x12117: "draw_terrain_layer [0x51a93] == -1 分支(eax = BIOS tick)",
    0x12132: "推進 [0x53c1f](inc 之前)",
    0x12169: "取換色表之前(eax = 這次畫的階 [0x53c1f])",
    0x152BA: "redraw(1) + wait_ticks(1) 之後(eax = wait_ticks 結束時的 tick、ebx = k)",
}
DELTA = 0x19C000


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "entries":
        body = " ".join(f"{a + DELTA:x}" for a in sorted(NATIVE))
        print(wsl(f"mkdir -p {ENTRY_DIR} && printf '%s\\n' '{body}' > {ENTRY_FILE} && cat {ENTRY_FILE}"))
        return 0
    name = argv[1]
    if cmd == "launch":
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
        import cl  # noqa: E402  (cl 在 import 時設好 FD2_HARNESS_CALLLOG,下面覆寫)
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "100000000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "0"
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in ("FD2_HARNESS_CALLLOG_CAP", "FD2_HARNESS_CALLLOG_DUMP") if v not in w])
        return cl.main(["battle", name, "1"])
    if cmd == "hud":
        import fd2_chapter_sweep as sw  # noqa: E402
        log: list[str] = []
        d = HERE / "cl" / name / "hud"
        d.mkdir(parents=True, exist_ok=True)
        print(sw.ensure_battle_hud(name, d, log, "hud", max_clears=60))
        print("\n".join(log[-3:]))
        return 0
    if cmd == "endturn":
        import fd2_chapter_sweep as sw  # noqa: E402
        log = []
        d = HERE / "cl" / name / "endturn"
        d.mkdir(parents=True, exist_ok=True)
        r = sw.confirm_end_turn(name, d, log)
        print("engine_code", r.get("engine_code"))
        print("\n".join(log[-4:]))
        return 0
    from live import Live  # noqa: E402
    L = Live(name, HERE / "cl" / f"{name}_live")
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    try:
        if cmd == "arm":
            L.sm(L.ua(11, 0xE), bytes([0x00, 79]))
            L.sm(L.ua(1, 0x40), struct.pack("<h", 782))
            L.sm(L.ua(0, 0x40), struct.pack("<h", 823))
            L.sm(L.ua(11, 0), bytes([19, 14]))
            L.sm(L.ua(0, 5), bytes([0]))
            for i in (1, 2, 3, 4):
                L.sm(L.ua(i, 5), bytes([0x80]))
            u0 = L.dump(L.ua(0, 0), 2, "u0xy")
            L.sm(0x53AB1 + DELTA, struct.pack("<ii", u0[0], u0[1]))
            u11 = L.dump(L.ua(11, 0), 0x1A, "u11")
            print("ubase", hex(L.ubase), "#0 xy", tuple(u0), "#11 xy", tuple(u11[:2]), "#11 inv", u11[0xA:0x1A].hex())
        L.cmd("BPLIST")
        time.sleep(0.5)
        print("\n".join(L.pane().splitlines()[-8:]))
    finally:
        L.resume()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
