"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
由 dump_collect.sh 呼叫。

在 collect_targets_in_range 返回點(0x149f0)的傾印上,離線重算目標清單並與程式輸出比對。

用法:collect_check.py <stack.bin> <map.bin> <units.bin> [outbuf.bin]
第一次呼叫(沒有 outbuf)只印出堆疊參數,讓呼叫端知道 outBuf 位址。
"""
import struct
import sys

W, H, N = 27, 21, 21
DELTA = 0x19C000

stack = open(sys.argv[1], "rb").read()
cells = open(sys.argv[2], "rb").read()
units = open(sys.argv[3], "rb").read()

count, = struct.unpack_from("<I", stack, 0)
ret, ox, oy, out, rng, thr, sel = struct.unpack_from("<7I", stack, 0x14)
print(f"count={count} ret={ret:#x} (static {ret - DELTA:#x}) origin=({ox},{oy}) out={out:#x} range={rng} thr={thr} sel={sel}")


def mark(x: int, y: int) -> int:
    return cells[7 + 4 * (y * W + x)]


pred = []
for i in range(N):
    r = units[i * 80:(i + 1) * 80]
    x, y, f5, side = r[0], r[1], r[5], r[6]
    m = mark(x, y) if x < W and y < H else 0xFF
    ok_side = {0: side == 0, 1: side != 0, 2: side == 1, 3: side == 2}.get(sel, False)
    inc = not (f5 & 1) and m != 0xFF and ok_side
    why = []
    if f5 & 1:
        why.append("+5 bit0")
    if m == 0xFF:
        why.append("cell unmarked")
    if not ok_side:
        why.append("side")
    print(f"  unit {i:2d} ({x:2d},{y:2d}) side={side} f5={f5:#04x} mark={m:#04x} dist={abs(x - ox) + abs(y - oy):2d} -> {'IN' if inc else 'out: ' + ','.join(why)}")
    if inc:
        pred.append(i)
print("predicted:", pred)

print("marks (.. = 0xff):")
for y in range(H):
    print("  %2d " % y + " ".join(".." if mark(x, y) == 0xFF else "%02x" % mark(x, y) for x in range(W)))

if len(sys.argv) > 4:
    ob = open(sys.argv[4], "rb").read()
    actual = list(ob[:count])
    print("actual   :", actual)
    print("MATCH" if actual == pred else "MISMATCH")
