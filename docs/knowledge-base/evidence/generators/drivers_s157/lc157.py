# 存檔:原 scratchpad 驅動腳本(續一百五十七),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百五十七(實機,使用者 2026-10-27 核准):指令表 0x51d01 第 1、2、5、7 格的入口 —— 敵方 AI 在 [0x53af9] = 1 時施放法術 1、2、5、7。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e),WSL -d Ubuntu;只改模擬器記憶體裡的單位資料與 [0x53af9],程式碼不動。
呼叫紀錄(修補版 dosbox-x)只列下面的 EIP,遊戲途中不下斷點。

用法:
  python lc157.py entries                 # 在 WSL 寫入口檔(執行期 EIP)
  python lc157.py launch NAME             # 以入口檔開 instance 到第 1 章戰場
  python lc157.py hud NAME                # 清對話直到戰場 HUD
  python lc157.py units NAME              # 停住、印單位、恢復
  python lc157.py arm NAME AF9 U:S ...    # 停住:[0x53af9] = AF9;敵 U 只會法術 S、MP 999、卸武器、搬到我方旁;
                                          #   我方 HP 999/999、#1..#4 已行動、索爾清已行動;恢復
  python lc157.py endturn NAME            # 結束回合(sweep 的 confirm_end_turn)
  python lc157.py log NAME                # 列呼叫紀錄裡這些 EIP 的 E 記錄(序號、EIP、eax)
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = Path(r"C:/Users/kg701/Desktop/GAME/fd2_re")
sys.path.insert(0, str(REPO / "tools"))

ENTRY_DIR = "/home/kg701004/fd2-calllog-s157"
ENTRY_FILE = f"{ENTRY_DIR}/entries_cells.txt"
# 原生位址(FD2.EXE 反組譯);執行期 = 原生 + 0x19c000
NATIVE = {
    0x153E7: "ai_spell_execute:法術 < 10,讀 [0x53af9] 之前",
    0x153F2: "[0x53af9] == 0:場景路徑(call 0x2ff01)",
    0x1540A: "[0x53af9] != 0:地圖路徑",
    0x1541F: "call [eax*4 + 0x51d01](eax = 法術 = 格)",
    0x2134B: "第 1 格(跳板)", 0x21364: "第 2 格(跳板)", 0x2137D: "第 3 格(跳板,正對照)",
    0x21449: "第 5 格(跳板)", 0x21462: "第 6 格(跳板,正對照)", 0x2147B: "第 7 格(跳板)",
    0x2121A: "第 0..3、8 格共用的接續點", 0x213AA: "第 4..7 格共用的接續點",
    0x21227: "command_generic_damage", 0x213B7: "command_generic_damage_type21",
}
DELTA = 0x19C000


def wsl(cmd: str, timeout: int = 60) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return (r.stdout + r.stderr).strip()


def bits40(ids) -> bytes:
    v = 0
    for i in ids:
        v |= 1 << i
    return v.to_bytes(5, "little")


def show(L) -> list[bytes]:
    n = L.d32(0x53BEB + DELTA) & 0xFF
    b = L.units("units", n)
    rows = [b[i * 80:(i + 1) * 80] for i in range(n)]
    print("ubase", hex(L.ubase), "count", n)
    for i, r in enumerate(rows):
        sp = int.from_bytes(r[0x1A:0x1F], "little")
        hp, mhp = struct.unpack_from("<hh", r, 0x40)
        mp, mmp = struct.unpack_from("<hh", r, 0x44)
        print(f"#{i:2d} x={r[0]:2d} y={r[1]:2d} +5={r[5]:02x} +6={r[6]:02x} hp={hp}/{mhp} mp={mp}/{mmp} "
              f"+2={r[2]} +3={r[3]} +4={r[4]} +26={r[0x26]} w={r[0xA]:02x} spells={[k for k in range(40) if sp >> k & 1]}")
    return rows


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "entries":
        body = " ".join(f"{a + DELTA:x}" for a in sorted(NATIVE))
        print(wsl(f"mkdir -p {ENTRY_DIR} && printf '%s\\n' '{body}' > {ENTRY_FILE} && cat {ENTRY_FILE}"))
        return 0
    name = argv[1]
    wd = f"/home/kg701004/fd2-run-harness-{name}"
    if cmd == "launch":
        os.environ["FD2_HARNESS_DOSBOX_BIN"] = "/home/kg701004/fd2-dosbox-calllog/dosbox-x/src/dosbox-x"
        import cl  # noqa: E402  (cl 在 import 時設好 FD2_HARNESS_CALLLOG,下面覆寫)
        os.environ["FD2_HARNESS_CALLLOG"] = ENTRY_FILE
        os.environ["FD2_HARNESS_CALLLOG_CAP"] = "1000"
        os.environ["FD2_HARNESS_CALLLOG_DUMP"] = "0"
        w = [x for x in os.environ.get("WSLENV", "").split(":") if x]
        os.environ["WSLENV"] = ":".join(w + [v for v in ("FD2_HARNESS_CALLLOG_CAP", "FD2_HARNESS_CALLLOG_DUMP") if v not in w])
        return cl.main(["battle", name, "1"])
    if cmd in ("hud", "endturn"):
        import fd2_chapter_sweep as sw  # noqa: E402
        log: list[str] = []
        d = HERE / "cl" / name / cmd
        d.mkdir(parents=True, exist_ok=True)
        if cmd == "hud":
            print(sw.ensure_battle_hud(name, d, log, "hud", max_clears=60))
        else:
            print("engine_code", sw.confirm_end_turn(name, d, log).get("engine_code"))
        print("\n".join(log[-4:]))
        return 0
    if cmd == "log":
        want = "|".join(f"{a + DELTA:08x}" for a in NATIVE)
        out = wsl(f"md5sum {wd}/FD2.EXE; grep -E '^E [0-9]+ ({want}) ' {wd}/CALLLOG.TXT | cut -d' ' -f1-7", timeout=180)
        for ln in out.splitlines():
            f = ln.split()
            if f and f[0] == "E":
                print(f[1], f[2], NATIVE.get(int(f[2], 16) - DELTA, "?"), "eax", f[6])
            else:
                print(ln)
        return 0
    from live import Live  # noqa: E402
    L = Live(name, HERE / "cl" / f"{name}_live")
    if not L.halt():
        print("停不進遊戲內容")
        return 1
    try:
        if cmd == "units":
            show(L)
        elif cmd == "arm":
            af9 = int(argv[2])
            plan = [tuple(int(x) for x in a.split(":")) for a in argv[3:]]
            rows = show(L)
            sx, sy = rows[0][0], rows[0][1]
            # 上下兩格留空(結束回合要從空格開指令環)
            near = [(sx + 1, sy), (sx - 1, sy), (sx + 1, sy + 1), (sx - 1, sy - 1), (sx + 1, sy - 1), (sx - 1, sy + 1)]
            for (u, s), (x, y) in zip(plan, near):
                L.sm(L.ua(u, 0x1A), bits40((s,)))
                L.sm(L.ua(u, 0x44), struct.pack("<hh", 999, 999))
                L.sm(L.ua(u, 0xA), bytes([0]))
                L.sm(L.ua(u, 0), bytes([x, y]))
            for i, r in enumerate(rows):
                if r[6] == 2:  # 我方
                    L.sm(L.ua(i, 0x40), struct.pack("<hh", 999, 999))
                    L.sm(L.ua(i, 5), bytes([0 if i == 0 else 0x80]))
            L.sm(0x53AF9 + DELTA, bytes([af9]))
            print("after arm, [0x53af9] =", L.dump(0x53AF9 + DELTA, 1, "af9")[0])
            show(L)
        elif cmd == "grey":  # U:KEY:ACTED ...:+2 = 圖示鍵、+3 = 0(姿勢 0)、+5 = 0x80(已行動 → 0x4e1a6 灰階)或 0
            for a in argv[2:]:
                u, key, acted = (int(x) for x in a.split(":"))
                L.sm(L.ua(u, 2), bytes([key, 0]))
                L.sm(L.ua(u, 5), bytes([0x80 if acted else 0]))
            show(L)
        elif cmd == "sprtab":  # 傾印 [0x53a61] 指到的單位圖表(前 N bytes)
            p = L.d32(0x53A61 + DELTA)
            nb = int(argv[2], 0)
            od = REPO / ".wsl_build" / "lc157_live"
            od.mkdir(parents=True, exist_ok=True)
            (od / "sprtab.bin").write_bytes(L.dump(p, nb, "sprtab"))
            print("ptr", hex(p), "bytes", nb)
        elif cmd == "dump":  # 傾印畫面、調色盤、捲動、幀計數、單位,存到 OUTDIR/TAG_*
            import json
            tag = argv[2]
            od = REPO / ".wsl_build" / "lc157_live"
            od.mkdir(parents=True, exist_ok=True)
            (od / f"{tag}_vga.bin").write_bytes(L.dump(0xA0000, 64000, "vga"))
            (od / f"{tag}_pal.bin").write_bytes(L.dump(L.d32(0x53A65 + DELTA), 768, "pal"))
            n = L.d32(0x53BEB + DELTA) & 0xFF
            (od / f"{tag}_units.bin").write_bytes(L.units("units", n))
            meta = {"scroll": list(struct.unpack("<ii", L.dump(0x53AA9 + DELTA, 8, "scroll"))),
                    "c0b": L.d32(0x53C0B + DELTA), "c07": L.d32(0x53C07 + DELTA), "a04": L.dump(0x53A04 + DELTA, 1, "a04")[0],
                    "count": n, "ubase": L.ubase}
            (od / f"{tag}_meta.json").write_text(json.dumps(meta), encoding="utf-8")
            print(meta)
    finally:
        L.resume()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
