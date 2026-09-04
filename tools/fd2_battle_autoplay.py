#!/usr/bin/env python3
"""fd2_battle_autoplay.py — 在原版 DOSBox-X 上自動推進一場戰鬥(配合數值覆寫用)。

用途:把「讓一場戰鬥跑完」變成可重複的步驟,以便驗證由控制流決定的東西
(勝利曲、結局演出、章節轉場)。搭配 `fd2_stat_override.py` 使用。

**改過數值之後,任何依賴數值的結論都不算數**——見 `fd2_stat_override.py` 的說明。

已知的操作序列(2026-09-04 原版實測,逐段斷點確認,見 doc13 該日段落):

    瀏覽游標對準單位 → Enter(進 0x18890 移動選格)
                     → Enter(確認落點)
                     → ↓(ring index 3)→ Enter   ⇒ 該單位行動結束(record[+5] |= 0x80)

方向鍵在**瀏覽游標**時移動游標格 `[0x53ab1]/[0x53ab5]`;在**環**裡改的是
`DAT_00053c57`。兩者長得一樣但層級不同,所以本工具每一步都用**記憶體**確認
狀態,不用畫面(戰場畫面持續動畫,截圖比對在那裡不帶資訊,見 doc48 §9.2)。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

CUR_X, CUR_Y = 0x53AB1, 0x53AB5


def snapshot(inst: str, sel: str, n: int) -> tuple[int, list[dict]]:
    H.enter_debugger(inst)
    res = H.mem_read_unit_array(inst, sel, H.DEFAULT_SHOT_DIR / inst / "autoplay",
                                num_records=n)
    if res.get("error"):
        H.resume(inst)
        raise SystemExit(f"校準失敗:{res['error']}")
    units = []
    for r in res["records"]:
        raw = bytes.fromhex(r["raw_hex"])
        units.append({"idx": r["index"], "x": raw[0], "y": raw[1],
                      "camp": r["camp"], "acted": r["acted"], "hp": r["hp_cur"]})
    cx = H.mem_read_global(inst, sel, CUR_X, 1, H.DEFAULT_SHOT_DIR / inst / "autoplay")["u8"]
    cy = H.mem_read_global(inst, sel, CUR_Y, 1, H.DEFAULT_SHOT_DIR / inst / "autoplay")["u8"]
    base = int(res["array_base"], 16)
    H.resume(inst)
    return base, [{"cursor": (cx, cy)}] + units


def press(inst: str, key: str, wait: float = 1.1) -> None:
    H.send_keys(inst, [H.resolve_key(key)])
    time.sleep(wait)


def move_cursor(inst: str, cur: tuple[int, int], dst: tuple[int, int]) -> None:
    dx, dy = dst[0] - cur[0], dst[1] - cur[1]
    for _ in range(abs(dx)):
        press(inst, "right" if dx > 0 else "left", 0.9)
    for _ in range(abs(dy)):
        press(inst, "down" if dy > 0 else "up", 0.9)


def attack_unit(inst: str) -> None:
    """已對準單位、且射程內有敵方候選時,原地攻擊。

    ring index 0 = 攻擊(doc13 §1)。射程內沒有候選時該方向會被 disable,
    按 ↑ 完全沒有反應(不是沒送到鍵),此時本函式等同白按,靠呼叫端用
    record[+5] bit0 是否新增來判斷有沒有真的打到。
    """
    press(inst, "confirm", 1.8)   # → 移動選格
    press(inst, "confirm", 2.2)   # 確認原地
    press(inst, "up", 1.2)        # ring index 0 = 攻擊
    press(inst, "confirm", 3.5)   # 執行 → 目標選擇
    press(inst, "confirm", 3.5)   # 確認目標


def adjacent_foe(u: dict, units: list[dict]) -> bool:
    return any(v["camp"] == 0x00 and not (v["acted"] & 0x01)
               and abs(v["x"] - u["x"]) + abs(v["y"] - u["y"]) == 1
               for v in units)


def rest_unit(inst: str) -> None:
    """已對準單位時,讓它原地結束行動。"""
    press(inst, "confirm", 1.8)   # → 移動選格
    press(inst, "confirm", 2.2)   # 確認原地
    press(inst, "down", 1.2)      # ring index 3
    press(inst, "confirm", 3.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--turns", type=int, default=1, help="要跑幾個我方回合")
    ap.add_argument("--attack", action="store_true",
                    help="相鄰有存活敵方時改為攻擊(ring index 0)而不是原地結束")
    ap.add_argument("--clear-enemy-bit0", action="store_true",
                    help="把敵方 record[+5] 清 0(還原先前實驗寫入的 raw bit0)")
    a = ap.parse_args()

    base, snap = snapshot(a.instance, a.selector, a.count)
    units = snap[1:]

    if a.clear_enemy_bit0:
        H.enter_debugger(a.instance)
        for u in units:
            if u["camp"] == 0x00 and u["acted"] & 0x01:
                H.debugger_cmd(a.instance, f"SMV {base + u['idx']*0x50 + 5:08x} 00")
        H.resume(a.instance)
        print("已清除敵方 +5 bit0")
        base, snap = snapshot(a.instance, a.selector, a.count)
        units = snap[1:]

    for t in range(1, a.turns + 1):
        for _ in range(8):                      # 上限,避免卡住無限迴圈
            base, snap = snapshot(a.instance, a.selector, a.count)
            cur, units = snap[0]["cursor"], snap[1:]
            todo = [u for u in units
                    if u["camp"] == 0x02 and u["hp"] > 0 and not (u["acted"] & 0x80)]
            if not todo:
                break
            tgt = min(todo, key=lambda u: abs(u["x"] - cur[0]) + abs(u["y"] - cur[1]))
            move_cursor(a.instance, cur, (tgt["x"], tgt["y"]))
            if a.attack and adjacent_foe(tgt, units):
                attack_unit(a.instance)
            else:
                rest_unit(a.instance)
        base, snap = snapshot(a.instance, a.selector, a.count)
        units = snap[1:]
        left = sum(1 for u in units if u["camp"] == 0x02 and not (u["acted"] & 0x80))
        alive = [u["idx"] for u in units if u["camp"] == 0x00 and not (u["acted"] & 0x01)]
        print(f"回合 {t}:我方未行動 {left};敵方存活 {len(alive)} {alive}")
        if not alive:
            print("敵方已全滅")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
