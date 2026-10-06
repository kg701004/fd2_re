"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

續六十六 項目 2:AI 模式(+0x34 低四位)8 的敵方回合路徑。
用法:python mode8.py <inst> <tag> <unit> <byte34_hex> <rest_unit> <dir>
- unit 的 +0x34 設成 byte34;其他敵人(+6 == 0 且 +5 bit0 清)麻痺 9;[0x53af9] = 1。
- 我方除 rest_unit 外設已行動;rest_unit 由 Escape 跳到、往 dir 移一格、休息,結束玩家回合。
- 斷點:0x13aef(分派 EAX = 模式、ESI = 單位)、0x14ef0(ai_choose_action 入口)、0x13e5a(共用收尾)、0x1548e(ai_attack_execute)、
  0x13512(unit_set_flag5_bit7 入口)。之後由 phase_log.sh 逐停點記錄。
"""
import os
import subprocess
import sys
import time

from live import DELTA, ROOT, Live

inst, tag, unit, b34, rest, d = sys.argv[1:7]
unit, rest = int(unit), int(rest)
L = Live(inst, ROOT / ".wsl_build/ctr/v3/ch19", 0x26BFC0)
assert L.halt()
u = L.units(f"{tag}_pre0_units")
n = len(u) // 80
L.sm(0x53AF9 + DELTA, b"\x01")
L.sm(L.ua(unit, 0x34), bytes([int(b34, 16)]))
L.sm(L.ua(unit, 0x26), b"\x00")
if os.environ.get("NOSPELL"):
    # 清法術與 MP,讓 ai_choose_action 只剩物理攻擊
    L.sm(L.ua(unit, 0x1A), b"\x00" * 5)
    L.sm(L.ua(unit, 0x44), b"\x00" * 4)
for i in range(n):
    r = u[i * 80:(i + 1) * 80]
    if i != unit and r[6] != 2 and not r[5] & 1:
        L.sm(L.ua(i, 0x26), b"\x09")
    if r[6] == 2 and not r[5] & 1 and i != rest:
        L.sm(L.ua(i, 5), b"\x80")
u = L.units(f"{tag}_pre_units")
print("unit", unit, "xy", (u[unit * 80], u[unit * 80 + 1]), "b34", hex(u[unit * 80 + 0x34]), "n", n)
L.cmd("BPDEL *")
for a in (0x13AEF, 0x14EF0, 0x13E5A, 0x1548E, 0x13512, 0x15311, 0x15055):
    L.cmd(f"BP 0170:{a + DELTA:x}")
L.resume()
time.sleep(1)
for k, w in (("Escape", 1.5), ("Return", 1.5), (d, 1.0), ("Return", 3.0)):
    L.key(k, w)
L.shot(f"{tag}_ring")
L.key("Down", 1.3)
L.key("Return", 2.5)
S = r"/c/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
D = "/c/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/v3/ch19"
# Windows 的 "bash" 會解析成 WSL,這裡固定用 Git Bash
subprocess.run([r"C:\Program Files\Git\bin\bash.exe", "-c",
                f"rm -f {D}/{tag}_stops.txt; IDLE=8 bash {S}/phase_log.sh {inst} {D} {tag} 26bfc0 {n * 80:x}"])
assert L.halt()
L.cmd("BPDEL *")
L.units(f"{tag}_post_units")
L.resume()
L.shot(f"{tag}_after")
