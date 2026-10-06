"""地形修正規則(`scene_attack_resolve` 0x2f89a..0x2f921 與 `unit_uses_move_cost_row19` 的靜態規則)。

`ev_terrain_modifier` 以斷點讀值逐案驗證這組規則(T1~T7);`ev_attack_path_selection` 用同一組規則
從地圖傾印算出每一擊的地形修正。兩者共用此模組,規則只寫一次。
"""
from __future__ import annotations

import struct
from collections.abc import Callable

# AP / DP 地形修正百分比表(依地形類型索引);產生器另以執行期傾印 t_mods.bin 驗證
AP_PCT = [5, 0, -5, -5, -5, 0]
DP_PCT = [0, 0, 10, 10, -5, 0]


def map_size(cells: bytes) -> tuple[int, int]:
    """地圖格傾印([0x53a51] 指向的區塊)開頭的寬、高(各 u16)。"""
    return struct.unpack_from("<HH", cells, 0)


def terrain_type(cells: bytes, tt: bytes, x: int, y: int) -> int:
    """(x, y) 的地形類型 = 地形表第 tile 列的 byte 1;tile = 地圖格 u16 & 0x3ff。

    Args:
        cells: 地圖格傾印(4 byte 標頭後每格 4 byte)。
        tt: 地形表傾印([0x53a69],每列 4 byte)。
        x: 欄。
        y: 列。

    Returns:
        地形類型(AP_PCT / DP_PCT 的索引)。
    """
    w, h = map_size(cells)
    assert 0 <= x < w and 0 <= y < h, (x, y, w, h)
    tile = struct.unpack_from("<H", cells, 4 + 4 * (y * w + x))[0] & 0x3FF
    return tt[tile * 4 + 1]


def gated(r: bytes) -> bool:
    """unit_uses_move_cost_row19 的靜態規則:為真時該方的地形修正被跳過。

    Args:
        r: 單位記錄(80 byte)。
    """
    if r[7] == 0x1C:
        return False
    return r[0x20] == 0x13 or r[0x1F] in (4, 5)


def tdiv(a: int, b: int) -> int:
    """idiv:向零截斷。"""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def modifier(value: int, pct: list[int], ttype: int, r: bytes) -> int | None:
    """單方的地形修正;被跳過時回傳 None。

    Args:
        value: 該方的 AP(攻方)或 DP(守方)。
        pct: AP_PCT 或 DP_PCT。
        ttype: 該方所在格的地形類型。
        r: 該方的單位記錄。
    """
    return None if gated(r) else tdiv(value * pct[ttype], 100)


def exchange(ap: int, dp: int, ra: bytes, rd: bytes, type_of: Callable[[bytes], int]) -> tuple[int | None, int | None, int]:
    """一次攻擊的地形修正與不含亂數項的傷害。

    「攻方修正看攻方所在格、守方修正看守方所在格」寫在這裡,兩個產生器共用:
    `ev_terrain_modifier` 的 T3~T5、T7 攻守雙方站在不同類型的格子,把兩方的格子對調會被斷點讀值擋下;
    `ev_attack_path_selection` 的資料裡雙方都站在類型 0,自己擋不下這種錯。

    Args:
        ap: 攻方 AP。
        dp: 守方 DP。
        ra: 攻方單位記錄。
        rd: 守方單位記錄。
        type_of: 單位記錄 → 該單位出手 / 被打時所在格的地形類型。

    Returns:
        (攻方修正, 守方修正, 傷害);修正被跳過時為 None。
    """
    apm = modifier(ap, AP_PCT, type_of(ra), ra)
    dpm = modifier(dp, DP_PCT, type_of(rd), rd)
    return apm, dpm, max(0, (ap + (apm or 0) - dp - (dpm or 0)) * 9 // 10)
