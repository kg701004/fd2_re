#!/usr/bin/env python3
"""fd2_floodfill_stack_probe.py — 量測移動範圍 flood-fill 的軟堆疊實際長到多高。

為什麼要量
----------
doc13「flood-fill 家族」反組譯記載:移動範圍計算是遞迴的,而且**不用 x86 呼叫堆疊**,
改用一個**固定位址 `0x60079` 的軟堆疊,每層 7 bytes**(word XY + byte 預算 + dword 格指標)。

該位址往上接什麼、有沒有上限,**全專案沒有任何文件記載**——`0x60079` 在整個
knowledge-base 只出現過那一次。這在正常遊玩下無所謂(MV 4-6,可達格數十),
但本專案會用 `fd2_stat_override --ours-mv` 放大 MV 來加速驗證,可達格數大致隨面積成長,
軟堆疊用量跟著放大一個數量級。

2026-09-04 用 `--ours-mv 25` 跑自動戰鬥,四人成功行動、敵方 8→4,隨後 FD2.EXE
**直接退回 DOS 提示字元**。成因未定,但在有人真的量過這個結構之前,沒有依據能說它無關。

方法(先量基準,再量放大後,兩者相減)
--------------------------------------
1. 進到瀏覽游標層(呼叫端負責,本工具不驅動 UI)。
2. dump `0x60079` 往後 N bytes 當**基準**。
3. 觸發一次移動範圍計算:選取單位(confirm)進入移動選格層,那一步就會跑 flood-fill。
4. 再 dump 一次,與基準逐位元組比對,回報**最後一個被改動的 offset**——那就是這次
   flood-fill 實際用到的軟堆疊高度。
5. 用不同 MV 重複,看高度怎麼隨 MV 成長。

⚠ 這量的是「有沒有被寫過」,不是「遞迴最深到哪」——被寫過的最高位置是遞迴深度的下界,
   而且殘留值可能來自更早的計算,所以**基準必須在同一場戰鬥內、緊接著取**。
⚠ 若最後被改動的 offset 逼近或超過某個已知結構的起點,才構成「會壓壞東西」的證據;
   本工具只給數字,**不替你下結論**。

用法
----
    python tools/fd2_floodfill_stack_probe.py --instance win3 --bytes 0x2000
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SOFT_STACK_GHIDRA = 0x60079
# 已記載的鄰近全域,用來說明「寫到哪裡算危險」。都在軟堆疊**下方**,
# 所以真正未知的是它**上方**接什麼——這正是本工具要量的。
NEIGHBOURS = {0x60000: "(未命名)", 0x60060: "地形成本表指標",
              0x60068: "格陣列寬", 0x60069: "格陣列高"}


BYTES_PER_LEVEL = 7      # doc13:word XY + byte 預算 + dword 格指標
GRID_MIN, GRID_MAX = 4, 64   # 實際地圖最小 18×26、最大 50×50,界線刻意放寬


def addr_check(w: int | None, h: int | None) -> tuple[bool, str]:
    """位址對映是否成立。**這一關過不了時,任何量測結果都不是「沒被用到」。**

    2026-09-04 第一次跑就踩到:`mem_read_global` 用程式碼校準出的 delta,其
    docstring 宣稱「executable is flat, so code and data share one load-time
    delta」——**對 0x60xxx 不成立**。當時 `[0x60068]`/`[0x60069]` 讀到 0/0
    (真實地圖是 24×24),整段 dump 全 0,於是「兩次 dump 完全相同」看起來像是
    「flood-fill 沒用到軟堆疊」。正對照:同一時刻 0x53xxx 的全域(BGM/單位數/
    陣列指標)全部正確,所以問題只在這個區段的位址對映,不是 debugger 壞了。
    """
    if not w or not h or not (GRID_MIN <= w <= GRID_MAX and GRID_MIN <= h <= GRID_MAX):
        return False, (f"[0x60068]/[0x60069] 讀到 {w}/{h},不是合理的格陣列尺寸。"
                       "**這代表 0x60xxx 的位址對映不成立,不是「軟堆疊沒被用到」。**")
    return True, f"格陣列 {w}×{h}"


def analyse_diff(before: bytes, after: bytes, want: int) -> dict:
    """比較兩次 dump。回傳 kind ∈ {short_read, no_change, measured}。

    `no_change` **必須是自己的一種狀態**,不能回 0:兩次 dump 相同不代表軟堆疊
    沒被用到——flood-fill 可能寫入了與殘留值相同的內容,或這次按鍵根本沒進到
    移動選格層。回 0 會被讀成「量到了,答案是 0」,那是把讀取失敗當成負面結果。
    """
    if len(before) < want or len(after) < want:
        return {"kind": "short_read",
                "before_len": len(before), "after_len": len(after)}
    diff = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    if not diff:
        return {"kind": "no_change"}
    high = diff[-1]
    return {"kind": "measured", "changed": len(diff), "low": diff[0], "high": high,
            "bytes_used": high + 1, "levels": (high + 1) // BYTES_PER_LEVEL,
            "hit_edge": high + 1 >= want}


def dump(inst: str, selector: str, addr: int, n: int, tag: str) -> bytes:
    d = H.DEFAULT_SHOT_DIR / inst / "ffstack"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{tag}.bin"
    try:
        out.unlink()
    except FileNotFoundError:
        pass
    # delta=0 不適用:0x60079 是 Ghidra 位址,要讓 helper 自己加載入位移。
    res = H.mem_read_global(inst, selector, addr, n, d)
    raw = res.get("raw_hex")
    return bytes.fromhex(raw) if raw else b""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--bytes", default="0x1000",
                    help="從 0x60079 往後 dump 幾個 byte(預設 0x1000)")
    ap.add_argument("--settle", type=float, default=2.0)
    a = ap.parse_args()
    n = int(a.bytes, 0)

    print(f"軟堆疊起點 0x{SOFT_STACK_GHIDRA:x},本次觀察 {n} bytes")
    print("已記載的鄰近全域(皆在軟堆疊下方,故上方是未知區):")
    for addr, what in sorted(NEIGHBOURS.items()):
        print(f"  0x{addr:x}  {what}")

    # ---- 位址自我檢查:先證明這一段真的讀得到,再談測量 ----------------------
    # 2026-09-04 第一次跑就踩到:`mem_read_global` 用程式碼校準出的 delta,其
    # docstring 宣稱「executable is flat, so code and data share one load-time
    # delta」——**對 0x60xxx 不成立**。當時 0x60068/0x60069 讀到 0/0(真實地圖是
    # 24×24),整段 dump 全 0,於是「兩次 dump 完全相同」看起來像是「flood-fill
    # 沒用到軟堆疊」。正對照:同一時刻 0x53xxx 的全域(BGM/單位數/陣列指標)全部正確,
    # 所以問題只在這個區段的位址對映,不是 debugger 壞了。
    H.enter_debugger(a.instance)
    w = H.mem_read_global(a.instance, a.selector, 0x60068, 1,
                          H.DEFAULT_SHOT_DIR / a.instance / "ffstack").get("u8")
    h = H.mem_read_global(a.instance, a.selector, 0x60069, 1,
                          H.DEFAULT_SHOT_DIR / a.instance / "ffstack").get("u8")
    H.resume(a.instance)
    ok_addr, addr_msg = addr_check(w, h)
    if not ok_addr:
        print(f"\n位址自我檢查失敗:{addr_msg}")
        print("要用這支工具,得先用簽章搜尋(例如在活體記憶體裡找該地圖的寬高位元組組合)")
        print("為這個區段獨立求出 delta;`mem_read_global` 的程式碼 delta 在此不適用。")
        return 2
    print(f"位址自我檢查通過:{addr_msg}")

    H.enter_debugger(a.instance)
    before = dump(a.instance, a.selector, SOFT_STACK_GHIDRA, n, "before")
    H.resume(a.instance)
    if len(before) < n:
        print(f"基準 dump 只拿到 {len(before)}/{n} bytes,中止(讀取失敗,不是結果)")
        return 2

    # 觸發一次 flood-fill:瀏覽層按確認進入移動選格層。
    H.send_keys(a.instance, [H.resolve_key("confirm")])
    time.sleep(a.settle)

    H.enter_debugger(a.instance)
    after = dump(a.instance, a.selector, SOFT_STACK_GHIDRA, n, "after")
    H.resume(a.instance)
    if len(after) < n:
        print(f"事後 dump 只拿到 {len(after)}/{n} bytes,中止")
        return 2

    r = analyse_diff(before, after, n)
    if r["kind"] == "no_change":
        print("\n兩次 dump 完全相同——**這不代表軟堆疊沒被用到**:"
              "flood-fill 可能寫入了與殘留值相同的內容,或這次按鍵沒有進到移動選格層。"
              "先確認層級(fd2_game_state)再重跑,不要把它讀成 0。")
        return 1

    print(f"\n改動的 byte 數:{r['changed']}")
    print(f"最低改動 offset:+0x{r['low']:x}(絕對 0x{SOFT_STACK_GHIDRA + r['low']:x})")
    print(f"**最高改動 offset:+0x{r['high']:x}(絕對 0x{SOFT_STACK_GHIDRA + r['high']:x})**")
    print(f"→ 本次 flood-fill 至少用掉 {r['bytes_used']} bytes 軟堆疊 "
          f"≈ {r['levels']} 層遞迴(每層 {BYTES_PER_LEVEL} bytes)")
    if r["hit_edge"]:
        print("⚠ 改動一路延伸到觀察範圍邊緣——真正的高度可能更高,請加大 --bytes 重測")
    return 0


def selftest() -> int:
    """位址自我檢查與差異分析。實機 dump 需要活的 DOSBox,不在範圍內——但這兩層
    正是 2026-09-04 出錯的地方,而它們完全離線可判。"""
    fails = []

    print("(1) 2026-09-04 事故:讀到 0/0 必須判成「對映不成立」,不是「沒被用到」")
    ok_bad, msg_bad = addr_check(0, 0)
    ok_good, msg_good = addr_check(24, 24)
    ok1 = (not ok_bad and "位址對映不成立" in msg_bad and "沒被用到" in msg_bad
           and ok_good and "24×24" in msg_good)
    print(f"    {'PASS' if ok1 else 'FAIL'}: 0/0 -> 拒絕且訊息點名對映問題、"
          f"24×24 -> 通過")
    if not ok1:
        fails.append(f"位址自我檢查不正確:{ok_bad}/{ok_good}")

    print("\n(2) 界線:真實地圖尺寸都要過,明顯的殘留值都要擋")
    # 實測 33 張地圖最小 18×26、最大 50×50(見 extract_maps 的錨點)。
    real = [(24, 24), (27, 21), (18, 26), (50, 50), (31, 45), (18, 51)]
    junk = [(0, 24), (24, 0), (None, 24), (3, 24), (65, 24), (255, 255)]
    bad_real = [g for g in real if not addr_check(*g)[0]]
    bad_junk = [g for g in junk if addr_check(*g)[0]]
    ok2 = not bad_real and not bad_junk
    print(f"    {'PASS' if ok2 else 'FAIL'}: 6 個真實尺寸全過(不過的 {bad_real})、"
          f"6 個殘留值全擋(漏放的 {bad_junk})")
    if not ok2:
        fails.append(f"界線不正確:real={bad_real} junk={bad_junk}")

    print("\n(3) 「兩次相同」必須是自己的狀態,不能回 0")
    # 回 0 會被讀成「量到了,答案是 0」——那是把讀取失敗當成負面結果。
    same = analyse_diff(bytes(64), bytes(64), 64)
    ok3 = same["kind"] == "no_change" and "bytes_used" not in same
    print(f"    {'PASS' if ok3 else 'FAIL'}: 相同 -> {same['kind']!r},"
          f"且**不提供** bytes_used")
    if not ok3:
        fails.append(f"no_change 被當成量到 0:{same}")

    print("\n(4) 高度換算:最高改動 offset -> bytes -> 層數(每層 7 bytes)")
    before = bytes(64)
    after = bytearray(64)
    after[3] = 1
    after[20] = 1                      # 最高改動 offset = 20 -> 21 bytes -> 3 層
    r = analyse_diff(before, bytes(after), 64)
    edge = bytearray(64)
    edge[63] = 1                       # 一路到邊緣 -> hit_edge
    r_edge = analyse_diff(before, bytes(edge), 64)
    ok4 = (r["kind"] == "measured" and r["changed"] == 2 and r["low"] == 3
           and r["high"] == 20 and r["bytes_used"] == 21 and r["levels"] == 3
           and not r["hit_edge"] and r_edge["hit_edge"] and BYTES_PER_LEVEL == 7)
    print(f"    {'PASS' if ok4 else 'FAIL'}: high=20 -> {r['bytes_used']} bytes / "
          f"{r['levels']} 層、改動到第 63 byte -> hit_edge={r_edge['hit_edge']}")
    if not ok4:
        fails.append(f"高度換算不正確:{r}")

    print("\n(4b) `levels`/`hit_edge` 的 +1 必須**恰好是** +1,不能是 +2")
    # (4) 的 high=20 剛好讓 `(high+1)//7` 與 `(high+2)//7` 樓地板除法算出同一個
    # 商(21//7=22//7=3),`hit_edge` 的兩個門檻也都離邊界太遠——突變測試量到
    # 這兩個字面值單獨逃掉。用會分岔的數字直接配對釘住。
    levels_before = bytearray(64); levels_before[5] = 1                 # high=5
    r_levels = analyse_diff(bytes(64), bytes(levels_before), 64)
    ok4b_levels = r_levels["levels"] == 0          # (5+1)//7=0;改 +2 會變成 1
    edge_buf = bytearray(64); edge_buf[10] = 1                          # high=10
    r_edge2 = analyse_diff(bytes(64), bytes(edge_buf), want=12)
    ok4b_edge = not r_edge2["hit_edge"]             # 10+1=11<12;改 +2 會變成 12>=12=True
    ok4b = ok4b_levels and ok4b_edge
    print(f"    {'PASS' if ok4b else 'FAIL'}: high=5 -> levels={r_levels['levels']}(應 0);"
          f"high=10,want=12 -> hit_edge={r_edge2['hit_edge']}(應 False)")
    if not ok4b:
        fails.append(f"levels/hit_edge 的 +1 不對:levels={r_levels['levels']}, "
                     f"hit_edge={r_edge2['hit_edge']}")

    print("\n(5) 短讀必須獨立成一類,且鄰近全域都在軟堆疊下方")
    short = analyse_diff(bytes(10), bytes(64), 64)
    above = {hex(a): v for a, v in NEIGHBOURS.items() if a >= SOFT_STACK_GHIDRA}
    ok5 = (short["kind"] == "short_read" and not above
           and analyse_diff(bytes(64), bytes(10), 64)["kind"] == "short_read")
    print(f"    {'PASS' if ok5 else 'FAIL'}: 任一側短讀 -> short_read、"
          f"NEIGHBOURS 位於軟堆疊上方的 {above or '無'}(上方才是未知區)")
    if not ok5:
        fails.append(f"短讀或鄰近全域假設不成立:{short} / {above}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(2026-09-04 對映失敗的回歸 + 尺寸界線雙向 + "
          "no_change 獨立狀態 + 高度換算 + 短讀與鄰近全域)。實機 dump 未涵蓋。")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
