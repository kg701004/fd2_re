# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
"""續六十八 0x14121 全流程停點。用法:python t_f.py <inst> <tag> <keys逗號> [idle=3]
0x14121 入口(返回位址、unit、a2;傾印單位)、0x14132(sub esp,8 之後的 8 byte 區域 = 未初始化的 outBuf)、
0x141b0(呼叫 0x4e4f6:10 參數、地圖、成本列)、0x141b5(EAX、outBuf、地圖)、0x141cd(0xff 出口)、
0x141e2(重設後的區域 8 byte)、0x12cea(鏡頭 x, y)、0x14215(0x14b78 的 4 參數 + [0x51a83])、
0x1421d(0x14b78 回傳)、0x14230(最終 EAX + [0x51a83])、0x13e9c / 0x13fd4 入口、0x13aef(分派)。
"""
import sys

from drv import run, stack
from live import DELTA, ROOT, Live

inst, tag, keys = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
opts = dict(a.split("=", 1) for a in sys.argv[4:])
L = Live(inst, ROOT / ".wsl_build/ctr/v5/ch25")
assert L.halt()
G = L.d32(0x53A51 + DELTA)
hdr = L.dump(G, 4, "wh")
W, H = hdr[0], hdr[2]
GN = 4 + 4 * W * H
ctx: dict = {}


def a83(L: Live) -> int:
    return L.d32(0x51A83 + DELTA)


def h_entry(L, rec, n):
    a = stack(L, rec, 3, f"{tag}_{n}_args")
    ctx["unit"] = a[1]
    rec["ret"] = hex(a[0] - DELTA)
    rec["unit"], rec["a2"] = a[1], a[2]
    L.units(f"{tag}_{n}_units")
    rec["dump"] = f"{tag}_{n}_units"


def h_local(L, rec, n):
    rec["local"] = list(L.dump(rec["esp"], 8, f"{tag}_{n}_local"))
    # inject=<unit>:在 0x14132 把未初始化的 outBuf([esp+4..5])改成 (0,0),強制走「找到的座標 = 自己」分支
    if rec["eip"] == "0x14132" and opts.get("inject") and ctx.get("unit") == int(opts["inject"]):
        L.sm(rec["esp"] + 4, bytes(2))
        rec["injected_local"] = list(L.dump(rec["esp"], 8, f"{tag}_{n}_local2"))


def h_call(L, rec, n):
    a = stack(L, rec, 10, f"{tag}_{n}_args")
    rec["args"] = a
    ctx["out"] = a[4]
    L.dump(G, GN, f"{tag}_{n}_pre")
    rec["cost"] = list(L.dump(a[0], 0x14, f"{tag}_{n}_cost"))
    rec["dump"] = f"{tag}_{n}_pre"


def h_ret(L, rec, n):
    L.dump(G, GN, f"{tag}_{n}_post")
    rec["outbuf"] = list(L.dump(ctx["out"], 8, f"{tag}_{n}_outbuf"))
    rec["dump"] = f"{tag}_{n}_post"


def h_mv(L, rec, n):
    rec["args"] = stack(L, rec, 4, f"{tag}_{n}_args")
    rec["a83"] = a83(L)


def h_end(L, rec, n):
    rec["a83"] = a83(L)


def h_args3(L, rec, n):
    a = stack(L, rec, 3, f"{tag}_{n}_args")
    rec["ret"] = hex(a[0] - DELTA)
    rec["args"] = a[1:]


BPS = [0x14121, 0x14132, 0x141B0, 0x141B5, 0x141CD, 0x141E2, 0x14203, 0x14215, 0x1421D, 0x14230,
       0x13E9C, 0x13FD4, 0x13AEF]
steps = run(L, tag, keys, None if opts.get("cont") == "1" else BPS,
            {0x14121: h_entry, 0x14132: h_local, 0x141B0: h_call, 0x141B5: h_ret, 0x141E2: h_local,
             0x14215: h_mv, 0x14230: h_end, 0x14203: h_args3, 0x13E9C: h_args3, 0x13FD4: h_args3},
            idle_n=int(opts.get("idle", "3")))
print("grid", hex(G), W, H)
if opts.get("keepbp") != "1":  # 結束時清斷點,否則下一次命中會讓遊戲停住、按鍵送進停住的遊戲
    assert L.halt()
    L.cmd("BPDEL *")
    L.resume()
