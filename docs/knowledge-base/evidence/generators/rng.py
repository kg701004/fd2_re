"""續六十八:rand(0x4ebe3)模型與狀態列舉。

rand:ax = [0x627b8];ax = rol3(ax + 0x9014);寫回;回傳 eax = ax(0..65535,零延伸)。
所以每次呼叫的回傳值就是新的 16-bit 狀態;rand()%k 用無號值取餘數。
"""
from __future__ import annotations

from typing import Callable


def nxt(s: int) -> int:
    """下一個狀態(= 下一次 rand 的回傳值)。"""
    v = (s + 0x9014) & 0xFFFF
    return ((v << 3) | (v >> 13)) & 0xFFFF


def prv(s: int) -> int:
    """上一個狀態(nxt 的反函數)。"""
    v = ((s >> 3) | (s << 13)) & 0xFFFF
    return (v - 0x9014) & 0xFFFF


assert all(prv(nxt(s)) == s for s in range(0, 0x10000, 97))
_seen = set()
_s = 0
for _ in range(0x10000):
    _seen.add(_s)
    _s = nxt(_s)
PERIOD_FROM_0 = len(_seen)


def enumerate_states(seq: list[tuple[str, Callable[[int], bool] | None]]) -> list[dict]:
    """seq:依序每次 rand 呼叫的 (名稱, 條件);條件收 rand 回傳值。回傳所有滿足的起始狀態與每次的值。

    起始狀態 s0 指第一次呼叫「之前」的狀態;第 i 次呼叫回傳 nxt^(i+1)(s0)。
    """
    out = []
    for s0 in range(0x10000):
        s = s0
        vals = []
        ok = True
        for name, cond in seq:
            s = nxt(s)
            vals.append(s)
            if cond is not None and not cond(s):
                ok = False
                break
        if ok:
            out.append({"s0": s0, "vals": vals})
    return out
