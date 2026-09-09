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

**MV = `+0x3b`(u8),`--ours-mv` 會寫它。** 早先本節寫著「不碰 MV」,理由是
constructor 那份來源把 AP 記成 `+0x37` 而實測 AP 在 `+0x48`,兩套偏移看似矛盾。
A.1 已解開:那不是矛盾,是**兩組不同欄位**(`+0x37/+0x39/+0x3b/+0x3e` 是基礎值,
`+0x48/…` 是生效值),`+0x3b` 讀到索爾=4 與狀態卡 `MV·04` 相符,寫入 20 後
畫面顯示 `MV·20`。上限夾 60:可移動格是 flood fill,地圖才 ~20×60,設上萬沒有意義。

⚠⚠ **MV 不要設大(建議 8-12),而且這不只是「沒必要」——有具體的崩潰機制假說。**
doc13「flood-fill 家族」反組譯記載:移動範圍的 flood-fill 是遞迴的,而且**自己維護
一個固定位址 `0x60079` 的軟堆疊,每層 7 bytes**。該位址往上接什麼、有沒有上限,
**全專案沒有任何文件記載,沒人查過**。可達格數隨 MV 大致以面積成長:MV 4 約數十格
(軟堆疊 ~280 B),MV 25 可能數百格(數 KB)——差一個數量級。

2026-09-04 用 `--ours-mv 25` 跑自動戰鬥,四人成功行動、敵方 8→4,隨後 **FD2.EXE 直接
退回 DOS 提示字元**(debugger 顯示 CPU 在 F000 BIOS 段,Output 無錯誤訊息)。

⚠ **同日對照組已大幅削弱上面這個假說,保留是為了留下推理鏈,不是因為它成立**:
換成 `--ours-mv 10`(HP 999 / AP 99,整組數值小一個數量級)重跑,**一樣退回 DOS,
而且更快**(約 2 分鐘、第 1 回合就結束,前一次撐到第 2 回合)。數值量級與存活時間
沒有正相關,所以 MV 造成的 flood-fill 展開量**不太可能是主因**。

真正還沒被分離的共同因素只剩兩個:**覆寫本身**,以及 **autoplay 的按鍵序列**。
`0x60079` 的高度也仍然沒量到——`fd2_floodfill_stack_probe.py` 第一次跑就發現
該區段的位址對映不成立(見該檔說明),所以那個數字是「未知」,不是「已排除」。

MV 建議值維持 8-12:在成因未定的情況下,把可控變因壓在接近原始量級仍然是合理的,
只是現在要清楚:**這是保守,不是已知的修復。**

⚠ MV 是 u8,**不在 `read_array()` 的回傳欄位裡**,所以寫後驗證要單獨重讀 `+0x3b`。
2026-09-04 之前漏了這一步:MV 照寫,但驗證迴圈只跑 u16 欄位,而輸出的
「36/36 吻合」看起來像全部都驗過了。已補上,現在輸出會分別列出 u16 與 MV 的筆數。

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

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

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


def u16_le(value: int) -> tuple[int, int]:
    """u16 拆成 little-endian 的兩個位元組。寫反不會報錯,只會安靜寫出錯的數字。"""
    return (value & 0xFF, (value >> 8) & 0xFF)


def field_addr(base: int, rec_index: int, offset: int) -> int:
    """單位記錄裡某個欄位的絕對位址。"""
    return base + rec_index * STRIDE + offset


def build_plan(recs: list[dict], n: int, ours_hp: int, ours_mp: int,
               ours_ap: int, enemy_hp: int, ours_mv: int
               ) -> tuple[list[tuple[int, int, int, str]], list[tuple[int, int]]]:
    """(u16 寫入計畫, MV 的 u8 計畫)。**0 一律代表「不動這一項」。**

    2026-09-04 記載的事故:三項的預設值是 9999,而只有 MV 有「0 = 不動」的逃生口,
    所以想「只改敵方」而單下 `--enemy-hp` 時,我方也會被一起灌大——正好毀掉那種
    對照組要隔離的變因。現在四項都有這個逃生口,而這個函式讓它變成可測的。

    空槽(hp_max == 0)一律跳過:超出 `[0x53beb]` 計數的槽是殘留值,它們的 hp_max
    常常非零,會通過「非空槽」檢查而被誤寫——與 fd2_in_battle_check 第二版踩過的
    是同一個坑。
    """
    plan: list[tuple[int, int, int, str]] = []
    mv_plan: list[tuple[int, int]] = []
    for r in recs[:n]:
        i, camp = r["index"], r["camp"]
        if r["hp_max"] == 0:
            continue
        if camp == OURS:
            if ours_mv:
                mv_plan.append((i, ours_mv))
            if ours_hp:
                plan += [(i, F_HPMAX, ours_hp, "HPmax"), (i, F_HPCUR, ours_hp, "HPcur")]
            if ours_mp:
                plan += [(i, F_MPMAX, ours_mp, "MPmax"), (i, F_MPCUR, ours_mp, "MPcur")]
            if ours_ap:
                plan += [(i, F_AP, ours_ap, "AP")]
        elif camp == ENEMY:
            if enemy_hp:
                plan += [(i, F_HPMAX, enemy_hp, "HPmax"), (i, F_HPCUR, enemy_hp, "HPcur")]
    return plan, mv_plan


def write_u16(instance: str, addr: int, value: int) -> None:
    for i, byte in enumerate(u16_le(value)):
        H.debugger_cmd(instance, f"SMV {addr + i:08x} {byte:02x}")


MV_MAX = 60          # 可移動格是 flood fill,地圖才 ~20x60,設上萬沒有意義
MV_ADVISED = (8, 12)  # 見 docstring 的 DOS-exit 段落:保守,不是已知的修復


def _rec(index=0, camp=OURS, hp_max=100, hp_cur=100):
    return {"index": index, "camp": camp, "hp_max": hp_max, "hp_cur": hp_cur}


def selftest() -> int:
    """寫入計畫與位址算術的對照。實際寫入需要活的 DOSBox,不在範圍內——
    但**決定要寫什麼、寫到哪裡**完全是離線可判的,而那正是 2026-09-04 出事的地方。"""
    fails = []

    print("(1) 2026-09-04 事故回歸:只改敵方時不得動到我方")
    # 三項的預設值是 9999,而當時只有 MV 有「0 = 不動」的逃生口,於是想做
    # 「只改敵方」的對照組時,我方也被一起灌大——正好毀掉要隔離的變因。
    units = [_rec(0, OURS, 50, 40), _rec(1, ENEMY, 30, 30), _rec(2, OURS, 60, 60)]
    plan, mv = build_plan(units, 3, ours_hp=0, ours_mp=0, ours_ap=0,
                          enemy_hp=1, ours_mv=0)
    touched_ours = {i for i, _, _, _ in plan if units[i]["camp"] == OURS}
    ok1 = (not touched_ours and mv == []
           and {i for i, _, _, _ in plan} == {1}
           and sorted(lab for _, _, _, lab in plan) == ["HPcur", "HPmax"])
    print(f"    {'PASS' if ok1 else 'FAIL'}: 我方被動到的 {touched_ours or '無'}、"
          f"只寫 idx{sorted({i for i, _, _, _ in plan})} 的 HPcur/HPmax")
    if not ok1:
        fails.append(f"只改敵方仍動到我方:{touched_ours}")

    print("\n(2) 對照:不給逃生口(沿用 9999 預設)時我方確實會被寫")
    # 沒有這一題,第 (1) 題對一個「永遠什麼都不寫」的實作也會通過。
    plan2, mv2 = build_plan(units, 3, 9999, 9999, 9999, 1, 10)
    ours2 = {i for i, _, _, _ in plan2 if units[i]["camp"] == OURS}
    ok2 = ours2 == {0, 2} and {i for i, _ in mv2} == {0, 2} and len(plan2) == 12
    print(f"    {'PASS' if ok2 else 'FAIL'}: 我方 idx{sorted(ours2)} 被寫、"
          f"MV 計畫 {len(mv2)} 筆、u16 共 {len(plan2)} 筆")
    if not ok2:
        fails.append(f"預設路徑沒有寫入我方:{ours2} / {len(plan2)}")

    print("\n(3) 空槽必須跳過(超出計數的殘留值曾經被誤寫)")
    with_empty = [_rec(0, OURS, 0, 0), _rec(1, ENEMY, 30, 30), _rec(2, OURS, 60, 60)]
    plan3, mv3 = build_plan(with_empty, 3, 9999, 0, 0, 1, 9)
    ok3 = 0 not in {i for i, _, _, _ in plan3} and 0 not in {i for i, _ in mv3}
    print(f"    {'PASS' if ok3 else 'FAIL'}: idx0(hp_max=0)未被寫入")
    if not ok3:
        fails.append("空槽被寫入")

    print("\n(4) u16 是 little-endian,且位址 = base + idx*STRIDE + offset")
    # 位元組序寫反不會報錯,只會安靜寫出錯的數字;STRIDE/offset 算錯會寫到別人身上。
    le_cases = [(0, (0x00, 0x00)), (1, (0x01, 0x00)), (0x1234, (0x34, 0x12)),
                (9999, (0x0F, 0x27)), (0xFFFF, (0xFF, 0xFF))]
    le_bad = [(v, e, u16_le(v)) for v, e in le_cases if u16_le(v) != e]
    addr_ok = (field_addr(0x1000, 0, F_HPCUR) == 0x1040
               and field_addr(0x1000, 1, F_HPCUR) == 0x1000 + STRIDE + 0x40
               and field_addr(0x1000, 3, F_AP) == 0x1000 + 3 * 0x50 + 0x48)
    ok4 = not le_bad and addr_ok and STRIDE == 0x50
    print(f"    {'PASS' if ok4 else 'FAIL'}: LE 5 例相符={not le_bad}、"
          f"位址算術相符={addr_ok}、STRIDE={STRIDE:#x}")
    if not ok4:
        fails.append(f"LE 或位址算術不正確:{le_bad} / {addr_ok}")

    print("\n(5) cur/max 兩個都寫(2026-09-04 更正過順序,不是只寫一個)")
    plan5, _ = build_plan([_rec(0, OURS, 50, 10)], 1, 777, 0, 0, 0, 0)
    offs = {off for _, off, _, _ in plan5}
    ok5 = (offs == {F_HPCUR, F_HPMAX} and F_HPCUR == 0x40 and F_HPMAX == 0x42
           and all(v == 777 for _, _, v, _ in plan5))
    print(f"    {'PASS' if ok5 else 'FAIL'}: 寫入偏移 {sorted(hex(o) for o in offs)}"
          f"(cur=0x40 在前、max=0x42)")
    if not ok5:
        fails.append(f"cur/max 寫入不完整:{offs}")

    print("\n(6) 非平凡性 + 負向控制")
    empty_plan, empty_mv = build_plan([], 0, 9999, 9999, 9999, 1, 10)
    sizes = {len(build_plan(units, 3, h, 0, 0, e, 0)[0])
             for h, e in ((0, 0), (0, 1), (1, 0), (1, 1))}
    ok6 = (empty_plan == [] and empty_mv == [] and len(sizes) >= 3
           and MV_MAX == 60 and MV_ADVISED == (8, 12))
    print(f"    {'PASS' if ok6 else 'FAIL'}: 空輸入 -> 空計畫、"
          f"四種旗標組合得出 {len(sizes)} 種計畫大小 {sorted(sizes)}")
    if not ok6:
        fails.append(f"計畫不隨輸入變化:{sorted(sizes)}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(只改敵方的事故回歸 + 反向對照 + 空槽跳過 "
          "+ LE 與位址算術 + cur/max 完整 + 非平凡性)。實際寫入未涵蓋,見 docstring。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    if "--selftest" in sys.argv:
        return selftest()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--count", type=int, default=16, help="要處理的記錄數(取 [0x53beb] 之內)")
    ap.add_argument("--ours-hp", type=int, default=9999)
    ap.add_argument("--ours-mp", type=int, default=9999)
    ap.add_argument("--ours-ap", type=int, default=9999)
    ap.add_argument("--enemy-hp", type=int, default=1)
    ap.add_argument("--ours-mv", type=int, default=0,
                    help="我方 MV(+0x3b,u8);0 = 不動。**建議 8-12**,見下方 MV 上限說明")
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
    plan, mv_plan = build_plan(recs, n, a.ours_hp, a.ours_mp, a.ours_ap,
                               a.enemy_hp, a.ours_mv)

    print(f"預定寫入 {len(plan)} 個 u16 欄位({len(plan)*2} 次 SMV)")
    if a.dry_run:
        for rec, off, val, lab in plan[:20]:
            print(f"  idx{rec:2} {lab:5} @ {field_addr(base, rec, off):#x} <- {val}")
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
    # MV 是 u8,不在 read_array 的回傳欄位裡,**必須單獨重讀**。
    # 2026-09-04:此前這裡只驗 u16 的 plan,MV 寫了卻從不驗證——一支賣點就是
    # 「寫後自驗」的工具漏驗自己寫的欄位,而輸出的 "36/36 吻合" 讀起來像全部都驗過了。
    for rec, mv in mv_plan:
        addr = base + rec * STRIDE + 0x3B
        got = H.mem_read_global(a.instance, a.selector, addr, 1,
                                H.DEFAULT_SHOT_DIR / a.instance / "statverify",
                                delta=0).get("u8")
        if got != mv:
            bad.append(f"idx{rec} mv: 期望 {mv},實得 {got}")
    total = len(plan) + len(mv_plan)
    print(f"驗證:{total-len(bad)}/{total} 個欄位吻合"
          f"(u16 {len(plan)} 筆 + MV u8 {len(mv_plan)} 筆)")
    for b in bad[:10]:
        print("  FAIL " + b)
    H.resume(a.instance)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
