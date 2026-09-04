#!/usr/bin/env python3
"""fd2_crash_ladder.py — 用階梯式單變因測試,找出讓 FD2.EXE 退回 DOS 的那個動作。

背景
----
2026-09-04 已用同實例對照確立:`fd2_battle_autoplay --attack` 會讓遊戲退回 DOS,
不含 `--attack` 的同樣三回合則不會(見交接檔 C.10)。但**攻擊本身沒有執行**
(`select_ring` 回報環選到 2 就退出),所以死因不在攻擊結算,而在 `--attack`
才會走的 `approach_then_act` 那條路上的某個動作。

兩條路徑的差異只有幾個動作:

    rest_unit(活)        : 選單位 → 確認原地 → ↓ → 確認
    approach_then_act(死): 選單位 → **方向鍵移動** → 確認**新落點** → ↑ → 確認 ×2

方法
----
一次只加一個動作,每階段重複 N 輪並在每輪後用**畫面**判存活,死在哪一階就鎖定哪個動作。
階梯刻意包含一個**已知會活**的階段(B),當作正對照——若連 B 都死,就代表死因不在
這幾個動作,而在更外層(例如 `ensure_browse` 本身或單純的重複次數),
那樣的結果同樣有用,但結論完全不同。

    A  ensure_browse 單獨重複
    B  A + 選單位 + 確認原地 + ↓ + 確認        (= rest_unit,已知會活)
    C  A + 選單位 + **移動** + 確認新落點       (不碰指令環)
    D  C + ↑ + 確認 ×2                        (= approach_then_act 全套)

⚠ 存活判定一律用 `H.game_alive()`(多幀畫面)。**不要用記憶體**:退回 DOS 後
`[0x53a45]`/`[0x53beb]` 仍留著舊值,單位陣列有時讀成全 0、有時讀出成功但是垃圾的
12 筆——兩者都與「暫時性壞讀」無法分辨(交接檔 C.9)。

用法
----
    python tools/fd2_crash_ladder.py --instance lad1 --rounds 4
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_battle_autoplay as A  # noqa: E402
import fd2_dosbox_live_helper as H  # noqa: E402


_round_no = {"n": 0}
PROVE_EVERY = 4          # 每幾輪做一次「有證明的」層級復位


def browse_reset(inst: str) -> None:
    """把 UI 帶回瀏覽層。**大部分輪次用便宜版,每 PROVE_EVERY 輪做一次有證明的版本。**

    為什麼可以省:`ensure_browse` 的完整版每次要 30-60 秒(BPDEL、6 次取消、下斷點、
    確認、讀 EIP、再 BPDEL、退回),佔了每輪約 70 秒裡的大頭。而它是**每一階都相同的
    設定步驟,不是受測變因**——階段 A 已經證明它單獨跑 16 輪無害。

    為什麼不能全省:層級一旦漂移,後續按鍵會送錯層,測試會**悄悄地**失去意義
    (本專案反覆踩過這個坑)。所以保留週期性的**有證明**復位當作漂移偵測:
    便宜版只做「無條件退到底」(Escape 在瀏覽層是 no-op),完整版才下斷點自證。
    """
    _round_no["n"] += 1
    if _round_no["n"] % PROVE_EVERY == 1:
        A.ensure_browse(inst)                 # 有證明的版本
    else:
        for _ in range(6):                    # 便宜版:只退到底
            A.press(inst, "cancel", 1.0)


def stage_a(inst: str) -> None:
    A.ensure_browse(inst)                     # A 測的就是它本身,不可替換


def stage_b(inst: str) -> None:
    browse_reset(inst)
    A.press(inst, "confirm", 1.6)          # 選單位 → 移動選格
    A.press(inst, "confirm", 2.0)          # 確認原地 → 開環
    A.select_ring(inst, A.RING_REST, "down")
    A.press(inst, "confirm", 2.5)


def stage_c(inst: str) -> None:
    browse_reset(inst)
    A.press(inst, "confirm", 1.6)          # 選單位 → 移動選格
    A.press(inst, "right", 0.8)            # **移動到新格**
    A.press(inst, "right", 0.8)
    A.press(inst, "confirm", 2.2)          # 確認新落點
    A.press(inst, "cancel", 1.2)           # 退出,不碰指令環


def stage_d(inst: str) -> None:
    browse_reset(inst)
    A.press(inst, "confirm", 1.6)
    A.press(inst, "right", 0.8)
    A.press(inst, "right", 0.8)
    A.press(inst, "confirm", 2.2)          # 確認新落點 → 開環
    A.select_ring(inst, A.RING_ATTACK, "up")
    A.press(inst, "confirm", 2.5)
    A.press(inst, "confirm", 2.5)


def stage_e(inst: str) -> None:
    """D + **在瀏覽層跨地圖移動游標**。

    2026-09-04:A-D 各跑到 16 輪都不死,而同一個實例緊接著跑一次
    `autoplay --attack` 就退回 DOS(正對照,證明實例本身有能力死)。
    所以死因在 autoplay 做、階梯沒做的事,而 `move_cursor` 是其中最明顯的一項——
    階梯永遠只操作游標當下那個單位,autoplay 則會把游標移到指定單位。
    """
    browse_reset(inst)
    for _ in range(4):                     # 跨地圖移動游標(autoplay 的 move_cursor)
        A.press(inst, "right", 0.7)
    for _ in range(3):
        A.press(inst, "down", 0.7)
    A.press(inst, "confirm", 1.6)
    A.press(inst, "right", 0.8)
    A.press(inst, "confirm", 2.2)
    A.select_ring(inst, A.RING_ATTACK, "up")
    A.press(inst, "confirm", 2.5)
    A.press(inst, "confirm", 2.5)


READS_PER_ROUND = 10


def stage_f(inst: str) -> None:
    """**反覆的 debugger 讀取循環**(autoplay 的 snapshot),UI 動作只做一次。

    第一版是「每輪先跑完整的 stage_e,再讀 3 次」,那把成本花在錯的地方:
    UI 動作在 C/D/E 已經各自被排除過,**受測變因是讀取本身**。
    每輪重跑那些動作只是讓一輪從 ~25 秒變成 ~70 秒,而且把兩個變因混在一起。

    改成:UI 動作只做一次把層級帶回瀏覽層,然後把讀取次數拉高。
    一次 `mem_read_unit_array` 要做簽章搜尋(2MB dump)+ 陣列 dump,
    所以「讀取密度」才是這一階真正在施加的壓力——autoplay 每個單位動作前後都做一次。
    """
    browse_reset(inst)
    for _ in range(READS_PER_ROUND):
        H.enter_debugger(inst)
        H.wait_halted(inst)
        H.mem_read_unit_array(inst, "0170",
                              H.DEFAULT_SHOT_DIR / inst / "ladder", num_records=12)
        H.resume(inst)
        time.sleep(0.2)


STAGES = [
    ("A  ensure_browse 單獨", stage_a),
    ("B  + 原地確認 + 休息(已知會活,正對照)", stage_b),
    ("C  + 移動到新格 + 確認落點(不碰環)", stage_c),
    ("D  + 指令環 ↑ + 確認 ×2(全套)", stage_d),
    ("E  + 瀏覽層跨地圖移動游標", stage_e),
    ("F  + 反覆讀單位陣列(autoplay 的 snapshot)", stage_f),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--rounds", type=int, default=4, help="每階段重複幾輪")
    ap.add_argument("--only", help="只跑指定階段,例如 C")
    a = ap.parse_args()

    alive, m = H.game_alive(a.instance)
    print(f"起點:{'存活' if alive else '**已離開**'} "
          f"(幀 {[f['distinct_colors'] for f in m['frames']]})", flush=True)
    if not alive:
        print("起點就不在了,無法測試")
        return 2

    for label, fn in STAGES:
        if a.only and not label.startswith(a.only):
            continue
        print(f"\n===== 階段 {label} =====", flush=True)
        for r in range(1, a.rounds + 1):
            fn(a.instance)
            alive, m = H.game_alive(a.instance)
            frames = [f["distinct_colors"] for f in m["frames"]]
            print(f"  第 {r} 輪:{'存活' if alive else '**已離開**'}  幀 {frames}", flush=True)
            if not alive:
                print(f"\n*** 死在階段【{label}】第 {r} 輪 ***")
                print("*** 該階段比前一個通過的階段多出的動作,就是嫌疑動作 ***")
                return 1
            time.sleep(0.5)
        print(f"  階段 {label}:{a.rounds} 輪全部存活", flush=True)

    print("\n全部階段都存活——死因不在這些動作裡,需要擴大階梯")
    return 0


if __name__ == "__main__":
    sys.exit(main())
