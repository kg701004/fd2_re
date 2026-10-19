# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續一百零八 cl4:續一百零二的受控設計(敵方 AI 施法 / 攻擊 / 道具),寫入後逐筆讀回。只對原版 FD2.EXE 的 harness instance。

python rig.py NAME dump        # 停住、列出單位 #0..#14、恢復
python rig.py NAME apply       # 停住、寫入、讀回、恢復
"""
import sys
import time

sys.path.insert(0, r"C:/Users/kg701/Desktop/GAME/fd2_re/tools")
import fd2_chapter_sweep as sw  # noqa: E402

NAME, CMD = sys.argv[1], sys.argv[2]
DELTA = 0x19C000
BASE = 0x26BDC8


def rd(addr: int, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        b = sw.read_mem(NAME, addr + len(out), min_bytes=min(16, n - len(out)))
        if b is None:
            raise RuntimeError(f"read failed at {addr + len(out):#x}")
        out += b
    return bytes(out[:n])


def halt() -> None:
    for _ in range(4):
        sw.enter_debugger(NAME)
        time.sleep(2)
        p = int.from_bytes(rd(0x53A45 + DELTA, 4), "little")
        if p == BASE:
            return
        print(f"unit ptr {p:#x} != {BASE:#x}(真實模式停點?),恢復後重試")
        sw.debugger_cmd(NAME, "RUN")
        time.sleep(2)
    raise SystemExit("無法在遊戲 selector 停住")


def resume() -> None:
    sw.debugger_cmd(NAME, "RUN")
    time.sleep(1)
    tail = [x for x in sw.capture_pane(NAME).splitlines() if x.strip()][-1:]
    print("pane:", tail)


def unit(i: int) -> bytes:
    return rd(BASE + i * 0x50, 0x50)


def show(i: int, b: bytes) -> None:
    print(f"#{i:2d} xy=({b[0]},{b[1]}) +5={b[5]:02x} +6={b[6]:02x} slots={b[0xa:0x1a].hex()} spells={b[0x1a:0x1f].hex()} "
          f"hp={int.from_bytes(b[0x40:0x42], 'little')}/{int.from_bytes(b[0x42:0x44], 'little')} "
          f"mp={int.from_bytes(b[0x44:0x46], 'little')}")


def sm(addr: int, data: bytes) -> None:
    sw.debugger_cmd(NAME, f"SM 0170:{addr:X} " + " ".join(f"{x:02X}" for x in data))
    time.sleep(0.4)
    got = rd(addr, len(data))
    if got != data:
        raise SystemExit(f"寫入 {addr:#x} 讀回 {got.hex()} != {data.hex()}")
    print(f"  SM {addr:#x} = {data.hex()} 讀回相同")


halt()
cnt = rd(0x53BEB + DELTA, 1)[0]
print("count", cnt)
us = {i: unit(i) for i in range(min(cnt, 15))}
for i, b in us.items():
    show(i, b)
if CMD == "apply":
    sol = us[0]
    u11, u12, u13 = BASE + 11 * 0x50, BASE + 12 * 0x50, BASE + 13 * 0x50
    sm(u11 + 0x1A, bytes([0, 1, 0, 0, 0]))                       # 已學法術只有 8(聖光彈)
    sm(u11 + 0x44, (100).to_bytes(2, "little"))                  # MP 100
    sm(u11 + 0xA, bytes([us[11][0xA] & ~0x40 & 0xFF]))           # slot0 卸下武器
    sm(u12 + 0, bytes([sol[0] - 1, sol[1]]))                     # 搬到索爾左邊
    sm(u13 + 0x40, (5).to_bytes(2, "little"))                    # HP 5
    sm(u13 + 0xE, bytes([0x00, 58]))                             # slot2 = 道具 58(回復類)
    for i in range(1, 5):
        if us[i][6] == 2:
            sm(BASE + i * 0x50 + 5, bytes([0x80]))               # 我方 #1..#4 已行動
    for i in (0, 11, 12, 13):
        show(i, unit(i))
resume()
