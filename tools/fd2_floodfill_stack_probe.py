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

SOFT_STACK_GHIDRA = 0x60079
# 已記載的鄰近全域,用來說明「寫到哪裡算危險」。都在軟堆疊**下方**,
# 所以真正未知的是它**上方**接什麼——這正是本工具要量的。
NEIGHBOURS = {0x60000: "(未命名)", 0x60060: "地形成本表指標",
              0x60068: "格陣列寬", 0x60069: "格陣列高"}


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

    diff = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    if not diff:
        print("\n兩次 dump 完全相同——**這不代表軟堆疊沒被用到**:"
              "flood-fill 可能寫入了與殘留值相同的內容,或這次按鍵沒有進到移動選格層。"
              "先確認層級(fd2_game_state)再重跑,不要把它讀成 0。")
        return 1

    print(f"\n改動的 byte 數:{len(diff)}")
    print(f"最低改動 offset:+0x{diff[0]:x}(絕對 0x{SOFT_STACK_GHIDRA + diff[0]:x})")
    print(f"**最高改動 offset:+0x{diff[-1]:x}(絕對 0x{SOFT_STACK_GHIDRA + diff[-1]:x})**")
    print(f"→ 本次 flood-fill 至少用掉 {diff[-1] + 1} bytes 軟堆疊 "
          f"≈ {(diff[-1] + 1) // 7} 層遞迴(每層 7 bytes)")
    if diff[-1] + 1 >= n:
        print("⚠ 改動一路延伸到觀察範圍邊緣——真正的高度可能更高,請加大 --bytes 重測")
    return 0


if __name__ == "__main__":
    sys.exit(main())
