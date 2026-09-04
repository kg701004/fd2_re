#!/usr/bin/env python3
"""fd2_stat_override.py — 在原版 DOSBox-X 的活體記憶體裡改戰場單位數值,用來加速驗證。

用途與界線
----------
把我方單位的 HP/MP/AP 拉高、敵方 HP 壓到 1,讓一場戰鬥能在幾回合內結束,
以便驗證**由控制流決定**的東西:勝利曲、結局演出、章節轉場、存檔行為、字模截圖。

**改過數值之後,任何依賴數值的結論都不算數**——AI 目標評分、傷害公式、命中/迴避
都會被污染。用本工具跑出來的結果必須註明「數值已被覆寫」。

(這是專案記憶裡的「DOSBox-X 活體寫入」變體。另一個「改 remake JSON」的變體已於
2026-09-01 撤回:對實際遊玩沒有效果。)

欄位偏移(全部 u16 LE)
----------------------
只用 2026-09-02 逐欄對過遊戲自己狀態卡的那一組(doc92 續四),
2026-09-04 在 ch27 又獨立對上一次(悠妮畫面 HP782/MP817 = 記憶體讀值):

    +0x40 HPcur  +0x42 HPmax  +0x44 MPcur  +0x46 MPmax
    +0x48 AP     +0x4a DP     +0x4c HIT    +0x4e DX

(cur/max 的順序於 2026-09-04 用兩個不同值 + 強制重繪實測更正;先前標反,
 因為原始驗證用的是滿血單位,cur == max 無法分辨。)

**MV 不在這組裡,本工具不碰。** 計畫檔記的 MV=`+0x3b` 來自 constructor 反組譯,
但同一份來源把 AP 記成 `+0x37`,而實測 AP 在 `+0x48`——兩套偏移互相矛盾,
在 MV 被獨立定位之前寫 `+0x3b` 有寫壞別的欄位的風險。要動 MV 請先實測定位。
(而且就算定位到也不該設上萬:可移動格是 flood fill,地圖才 ~20×60。)

陣營
----
`+0x06`:`0x02` = 我方,`0x00` = 敵方(2026-09-04 ch01/ch27 都實測一致)。

寫入與驗證
----------
DOSBox-X 的 `SMV <linear> <byte>` 一次寫一個 byte,u16 要寫兩次(LE)。
**每次執行都會在寫完後重讀整個陣列並逐欄比對**——沒有這一步,寫入靜默失敗
看起來會跟成功一模一樣(本專案已被 MEMDUMPBIN 的靜默失敗坑過)。

用法
----
    python tools/fd2_stat_override.py --instance ch01 --dry-run
    python tools/fd2_stat_override.py --instance ch01           # 套用並驗證
    python tools/fd2_stat_override.py --instance ch01 --ours-hp 9999 --enemy-hp 1
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

STRIDE = 0x50
CAMP = 0x06
F_HPCUR, F_HPMAX = 0x40, 0x42  # 2026-09-04 實測更正:cur 在前
F_MPCUR, F_MPMAX = 0x44, 0x46
F_AP = 0x48
OURS, ENEMY = 0x02, 0x00


# helper 的 mem_read_unit_array 已經把每筆記錄解好(camp/hp/mp/ap 等),
# 直接用它,不要另外重解一次 blob——多一份解碼就多一個會與畫面對不上的來源。
FIELD_BY_OFFSET = {F_HPMAX: "hp_max", F_HPCUR: "hp_cur",
                   F_MPMAX: "mp_max", F_MPCUR: "mp_cur", F_AP: "ap"}


def read_array(instance: str, selector: str, n: int) -> tuple[int, list[dict]]:
    out_dir = H.DEFAULT_SHOT_DIR / instance / "statoverride"
    res = H.mem_read_unit_array(instance, selector, out_dir, num_records=n)
    if res.get("error"):
        raise SystemExit(f"校準失敗:{res['error']}")
    return int(res["array_base"], 16), res.get("records", [])


def write_u16(instance: str, addr: int, value: int) -> None:
    for i in range(2):
        H.debugger_cmd(instance, f"SMV {addr + i:08x} {(value >> (8 * i)) & 0xFF:02x}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--count", type=int, default=16, help="要處理的記錄數(取 [0x53beb] 之內)")
    ap.add_argument("--ours-hp", type=int, default=9999)
    ap.add_argument("--ours-mp", type=int, default=9999)
    ap.add_argument("--ours-ap", type=int, default=9999)
    ap.add_argument("--enemy-hp", type=int, default=1)
    ap.add_argument("--ours-mv", type=int, default=0,
                    help="我方 MV(+0x3b,u8);0 = 不動。建議 20-30,不要設更大")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    for v in (a.ours_hp, a.ours_mp, a.ours_ap, a.enemy_hp):
        if not 0 <= v <= 0xFFFF:
            print(f"值 {v} 超出 u16 範圍,會被靜默截斷", file=sys.stderr)
            return 2

    H.enter_debugger(a.instance)
    # 只處理 [0x53beb](場上單位數)之內的記錄。超出計數的槽是殘留值,
    # 它們的 hp_max 常常非零,會通過「非空槽」檢查而被誤寫——
    # 這與 fd2_in_battle_check.py 第二版踩過的是同一個坑(檢查超出有效範圍)。
    cnt = H.mem_read_global(a.instance, a.selector, 0x53beb, 1,
                            H.DEFAULT_SHOT_DIR / a.instance / "statoverride")
    live_count = cnt.get("u8") or 0
    if not 1 <= live_count <= 96:
        raise SystemExit(f"[0x53beb] 讀到 {live_count},不像戰鬥中的單位數;中止")
    n = min(a.count, live_count)
    print(f"場上單位數 [0x53beb] = {live_count},本次處理前 {n} 筆")
    base, recs = read_array(a.instance, a.selector, n)
    if not recs:
        print("讀不到單位陣列", file=sys.stderr)
        return 2
    print(f"array base = {base:#x},記錄 {len(recs)} 筆")

    if not 0 <= a.ours_mv <= 60:
        raise SystemExit(f"MV={a.ours_mv} 超出合理範圍(0-60);可移動格是 flood fill")
    plan: list[tuple[int, int, int, str]] = []   # (rec, offset, value, label)
    mv_plan: list[tuple[int, int]] = []          # (rec, mv) —— MV 是 u8,單獨處理
    for r in recs[:n]:
        i, camp = r["index"], r["camp"]
        if r["hp_max"] == 0:
            continue                              # 空槽,跳過
        if camp == OURS:
            if a.ours_mv:
                mv_plan.append((i, a.ours_mv))
            plan += [(i, F_HPMAX, a.ours_hp, "HPmax"), (i, F_HPCUR, a.ours_hp, "HPcur"),
                     (i, F_MPMAX, a.ours_mp, "MPmax"), (i, F_MPCUR, a.ours_mp, "MPcur"),
                     (i, F_AP, a.ours_ap, "AP")]
        elif camp == ENEMY:
            plan += [(i, F_HPMAX, a.enemy_hp, "HPmax"), (i, F_HPCUR, a.enemy_hp, "HPcur")]

    print(f"預定寫入 {len(plan)} 個 u16 欄位({len(plan)*2} 次 SMV)")
    if a.dry_run:
        for rec, off, val, lab in plan[:20]:
            print(f"  idx{rec:2} {lab:5} @ {base + rec*STRIDE + off:#x} <- {val}")
        if len(plan) > 20:
            print(f"  ...(其餘 {len(plan)-20} 筆略)")
        H.resume(a.instance)
        return 0

    for rec, off, val, _ in plan:
        write_u16(a.instance, base + rec * STRIDE + off, val)
    for rec, mv in mv_plan:
        H.debugger_cmd(a.instance, f"SMV {base + rec * STRIDE + 0x3b:08x} {mv:02x}")

    # 寫後驗證:重讀並逐欄比對。沒有這一步,靜默失敗看起來就是成功。
    _, recs2 = read_array(a.instance, a.selector, n)
    by_idx = {r["index"]: r for r in recs2}
    bad = []
    for rec, off, val, lab in plan:
        got = by_idx.get(rec, {}).get(FIELD_BY_OFFSET[off])
        if got != val:
            bad.append(f"idx{rec} {lab}: 期望 {val},實得 {got}")
    print(f"驗證:{len(plan)-len(bad)}/{len(plan)} 個欄位吻合")
    for b in bad[:10]:
        print("  FAIL " + b)
    H.resume(a.instance)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
