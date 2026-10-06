"""存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。

續六十九:落到地圖外的單位與「亂碼劇情對話」、0x12d7b / 0x12cea 的游標語意。
用法:python t_ev.py <inst> <tag> <keys逗號> [idle=3] [cont=1] [keepbp=1]
停點:
  0x12cea 入口 —— 引數 (x, y)、游標 [0x53ab1]/[0x53ab5]、捲動 [0x53aa9]/[0x53aad]、[0x51a83]
  0x12dab(0x12d7b 的 ret)—— 游標;[esp+4] 是單位索引,對照單位 x, y
  0x13a44 field_event_lookup 入口 —— (ret, x, y, selector);格子位址 = grid + 4 + 4*(y*W + x),傾印 8 bytes
  0x13a64(0x12e38 回來後)—— out 8 bytes(tile、旗標/slot、地形表列)
  0x13a95 —— EDX = 寫入 [0x51a8f] 的事件編號
  0x1d95c / 0x1d9ec / 0x1d890 —— 事件分派:EAX = 事件編號,處理函式 = [0x51b91 + EAX*4]
"""
import struct
import sys

from drv import run, stack
from live import DELTA, ROOT, Live

inst, tag, keys = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
opts = dict(a.split("=", 1) for a in sys.argv[4:])
L = Live(inst, ROOT / ".wsl_build/ctr/v7/ch25")
assert L.halt()
G = L.d32(0x53A51 + DELTA)
W = L.d32(0x53AC1 + DELTA)
H = L.d32(0x53AC5 + DELTA)
GN = 4 + 4 * W * H
EV = L.d32(0x53A55 + DELTA)
print("grid", hex(G), W, H, "event_tbl", hex(EV), flush=True)


def cur(L: Live) -> dict:
    b = L.dump(0x53AA9 + DELTA, 0x20, "cur")
    sx, sy, cx, cy, rx, ry, mw, mh = struct.unpack("<8i", b)
    return {"scroll": [sx, sy], "cursor": [cx, cy], "screen": [rx, ry], "wh": [mw, mh]}


def h_cea(L, rec, n):
    a = stack(L, rec, 3, f"{tag}_{n}_args")
    rec["ret"] = hex(a[0] - DELTA)
    rec["xy"] = a[1:]
    rec.update(cur(L))
    rec["a83"] = L.d32(0x51A83 + DELTA)


def h_d7b_ret(L, rec, n):
    a = stack(L, rec, 2, f"{tag}_{n}_args")
    rec["ret"] = hex(a[0] - DELTA)
    rec["unit"] = a[1]
    u = L.dump(L.ua(a[1]), 2, f"{tag}_{n}_uxy")
    rec["unit_xy"] = list(u)
    rec.update(cur(L))


def h_fel(L, rec, n):
    a = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["ret"] = hex(a[0] - DELTA)
    x, y, sel = a[1], a[2], a[3]
    rec["x"], rec["y"], rec["sel"] = x, y, sel
    off = 4 + 4 * (y * W + x)
    rec["cell_off"] = off
    rec["in_grid"] = off + 4 <= GN
    rec["cell"] = list(L.dump(G + off, 4, f"{tag}_{n}_cell"))
    if not rec["in_grid"]:
        # 地圖陣列結尾到這一格之後 16 bytes 全部留存
        L.dump(G + GN, off + 16 - GN, f"{tag}_{n}_past_grid")
        rec["past_grid_dump"] = f"{tag}_{n}_past_grid"
        rec["event_tbl"] = list(L.dump(EV + 0x33, 64, f"{tag}_{n}_evtbl"))


def h_out(L, rec, n):
    rec["out"] = list(L.dump(rec["esp"], 8, f"{tag}_{n}_out"))


def h_evw(L, rec, n):
    rec["event_id"] = rec["edx"]


def h_disp(L, rec, n):
    e = rec["eax"]
    rec["event_id"] = e
    rec["handler"] = hex(L.d32(0x51B91 + DELTA + 4 * e) - DELTA)
    rec["unit"] = rec.get("esi")  # 分派前 push esi:目前的單位索引


BPS = [0x12CEA, 0x12DAB, 0x13A44, 0x13A64, 0x13A95, 0x1D890, 0x1D95C, 0x1D9EC]
if opts.get("lite") == "1":  # 逐步移動每格都進 0x13a44:省掉 0x13a64(out 可由格子 + 地形表重算)
    BPS.remove(0x13A64)
steps = run(L, tag, keys, None if opts.get("cont") == "1" else BPS,
            {0x12CEA: h_cea, 0x12DAB: h_d7b_ret, 0x13A44: h_fel, 0x13A64: h_out, 0x13A95: h_evw,
             0x1D890: h_disp, 0x1D95C: h_disp, 0x1D9EC: h_disp},
            idle_n=int(opts.get("idle", "3")))
if opts.get("keepbp") != "1":  # 結束時清斷點並恢復,否則之後的按鍵送進停住的遊戲
    assert L.halt()
    L.cmd("BPDEL *")
    L.resume()
