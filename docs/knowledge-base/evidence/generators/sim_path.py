"""續六十七:0x4e390/0x4e42c(移動範圍泛洪)與 0x4e4f6/0x4e5cc(確認落點的路徑搜尋)的逐指令模擬。

格子 4 bytes:c0/c1 = 圖塊字(低 10 bits;c1 高 6 bits 是 mode 1 的轉彎數)、c2 = 旗標(0x40 不可進、0x80 進入後預算歸 0)、
c3 = 記號(剩餘預算;重設值 0xff)。比較用有號 byte(jle / jl / jg),扣成本用無號借位(jb)。
"""
from __future__ import annotations

import sys

sys.setrecursionlimit(20000)


def s8(v: int) -> int:
    return v - 256 if v >= 128 else v


class Grid:
    def __init__(self, raw: bytes, tt: bytes, cost: bytes) -> None:
        self.b = bytearray(raw)
        self.W, self.H = raw[0], raw[2]
        self.tt = tt
        self.cost = cost

    def idx(self, x: int, y: int) -> int:
        return 4 + 4 * (y * self.W + x)

    def mark(self, x: int, y: int) -> int:
        return self.b[self.idx(x, y) + 3]

    def enter_cost(self, x: int, y: int) -> int:
        i = self.idx(x, y)
        tile = (self.b[i] | (self.b[i + 1] << 8)) & 0x3FF
        return self.cost[self.tt[tile * 4 + 1]]


def flood1(g: Grid, sx: int, sy: int, cl: int) -> None:
    """0x4e390:起點記號 = cl,方向順序 右、左、下、上;e4be 只接受有號 cl > 記號。"""
    g.b[g.idx(sx, sy) + 3] = cl

    def enter(x: int, y: int, c: int) -> int | None:
        k = g.enter_cost(x, y)
        if c < k:
            return None
        c -= k
        i = g.idx(x, y)
        if s8(c) <= s8(g.b[i + 3]):
            return None
        f = g.b[i + 2]
        if f & 0x40:
            return None
        if f & 0x80:
            c = 0
        g.b[i + 3] = c
        return c

    def rec(x: int, y: int, c: int) -> None:
        for nx, ny, ok in ((x + 1, y, x + 1 < g.W), (x - 1, y, x > 0), (x, y + 1, y + 1 < g.H), (x, y - 1, y > 0)):
            if ok:
                r = enter(nx, ny, c)
                if r is not None:
                    rec(nx, ny, r)

    rec(sx, sy, cl)


def search0(g: Grid, sx: int, sy: int, cl: int, tx: int, ty: int) -> tuple[int, list[int]]:
    return search(g, sx, sy, cl, tx, ty, 0)


def search(g: Grid, sx: int, sy: int, cl: int, tx: int, ty: int, mode: int) -> tuple[int, list[int]]:
    """0x4e4f6:回傳 (結果, 方向陣列)。mode 0/1:結果 = 抵達目標時的深度(取 <= 目前值者,同深度後到的覆寫),沒抵達 0xff。
    mode 1 另在剩餘預算相等時,若這條路徑的方向段數 > 該格記錄的段數也接受。
    mode 2:不看 0x40/0x80、不檢查目標;每進入一個 0x40 格就把它的 (x, y) 寫進 outBuf、結果 = 1(後寫的蓋前面)。
    方向碼 3 右、1 左、0 下、2 上。"""
    g.b[g.idx(sx, sy) + 3] = cl
    st = {"res": 0xFF, "path": [], "buf": {}, "arrivals": [], "hits": []}
    stack: list[int] = []  # 每層的方向 byte

    def at_target(x: int, y: int) -> None:  # 0x4e751
        if (x, y) != (tx, ty):
            return
        d = len(stack)
        if d > st["res"]:
            return
        st["res"] = d
        st["arrivals"].append(d)
        if d:
            st["path"] = list(stack)
            for k, v in enumerate(stack):  # 0x4e751 逐 byte 寫進 outBuf(只寫 d 個)
                st["buf"][k] = v

    def enter(x: int, y: int, c: int) -> int | None:  # 0x4e680
        k = g.enter_cost(x, y)
        if c < k:
            return None
        c -= k
        i = g.idx(x, y)
        # 0x4e71f:目前路徑(含這一步)的方向段數 × 4
        runs, prev = 0, None
        for v in stack:
            if v != prev:
                runs, prev = runs + 1, v
        al = (runs << 2) & 0xFF
        if s8(c) < s8(g.b[i + 3]):
            return None
        if s8(c) == s8(g.b[i + 3]):
            if mode != 1 or al <= (g.b[i + 1] & 0xFC):
                return None
        g.b[i + 1] = (g.b[i + 1] & 3) | al  # 0x4e6ca
        if mode == 2:
            g.b[i + 3] = c
            if g.b[i + 2] & 0x40:  # 0x4e703
                st["res"] = 1
                st["buf"][0], st["buf"][1] = x, y
                st["hits"].append((x, y))
            return c
        f = g.b[i + 2]
        if f & 0x40:
            return None
        if f & 0x80:
            c = 0
        g.b[i + 3] = c
        at_target(x, y)
        return c

    def rec(x: int, y: int, c: int) -> None:  # 0x4e5cc
        stack.append(3)
        for d, nx, ny, ok in ((3, x + 1, y, x + 1 < g.W), (1, x - 1, y, x > 0), (0, x, y + 1, y + 1 < g.H),
                              (2, x, y - 1, y > 0)):
            stack[-1] = d
            if ok:
                r = enter(nx, ny, c)
                if r is not None:
                    rec(nx, ny, r)
        stack.pop()

    at_target(sx, sy)
    rec(sx, sy, cl)
    search.last = st
    search0.last = st
    return st["res"], st["path"]


def bfs_rival(g: Grid, sx: int, sy: int, cl: int, tx: int, ty: int) -> tuple[int, list[int]]:
    """對照:最少步數(BFS,同層依 右左下上 第一個找到),只用成本與 0x40/0x80 規則判可達。"""
    from collections import deque
    best = {(sx, sy): (cl, [])}
    q = deque([(sx, sy, cl, [])])
    while q:
        x, y, c, p = q.popleft()
        if (x, y) == (tx, ty):
            return len(p), p
        for d, nx, ny, ok in ((3, x + 1, y, x + 1 < g.W), (1, x - 1, y, x > 0), (0, x, y + 1, y + 1 < g.H),
                              (2, x, y - 1, y > 0)):
            if not ok:
                continue
            k = g.enter_cost(nx, ny)
            if c < k:
                continue
            f = g.b[g.idx(nx, ny) + 2]
            if f & 0x40:
                continue
            nc = 0 if f & 0x80 else c - k
            if (nx, ny) in best and best[(nx, ny)][0] >= nc:
                continue
            best[(nx, ny)] = (nc, p + [d])
            q.append((nx, ny, nc, p + [d]))
    return 0xFF, []
