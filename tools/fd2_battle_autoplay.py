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
import fd2_game_state as GS  # noqa: E402

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


BP_MOVE_SELECT = 0x18890 + 0x19C000   # 0x1B4890
BP_RING = 0x18D8C + 0x19C000          # 0x1B4D8C


def _pane(inst: str) -> str:
    import subprocess
    return subprocess.run(["wsl", "-d", "Ubuntu", "tmux", "-L", "fd2harness",
                           "capture-pane", "-t", f"harness-{inst}", "-p"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout


def _halted(inst: str) -> bool:
    return not any("(Running)" in ln for ln in _pane(inst).splitlines()[-3:])


def _eip(inst: str) -> int | None:
    if not _halted(inst):
        return None
    for ln in _pane(inst).splitlines()[:8]:
        if "EIP=" in ln:
            return int(ln.split("EIP=")[1].split()[0], 16)
    return None


def wait_playable(inst: str, tries: int = 8, gap: float = 4.0) -> bool:
    """等到玩家真的可以操作為止——**改由 `fd2_game_state` 神諭判定**。

    本檔原本自己實作這個判斷,踩過三次坑(先測後退會在指令環震盪、拿
    `in_battle` 當可操作、把「還輪不到你」當成「回不去」)。狀態判斷現在集中在
    神諭一處,這裡只負責等。
    """
    st, _ = GS.wait_playable(inst, timeout=tries * gap, gap=gap)
    return st is GS.GameState.BROWSE_CURSOR


def ensure_browse(inst: str, max_escapes: int = 6) -> bool:
    """把 UI 帶回**瀏覽游標層**,並且**證明**它真的在那一層。

    為什麼需要:本專案反覆踩到「以為在瀏覽層、其實在子畫面」。讀游標全域
    `[0x53ab1]/[0x53ab5]` **不能**判定層級——移動選格層用的是同一組全域,
    而 `DAT_00053c57` 是不會重置的殘留值。2026-09-04 有一整輪 25 次試驗
    因此全部作廢(見 doc48 §10)。

    判定方式是**自證**的:在 `0x18890`(移動選格入口)下斷點後按 Enter,
    只有從瀏覽層按才會進到那裡。命中即證明按之前在瀏覽層;隨後 Escape 一次
    退回,層級即為已知。

    回傳 True 表示已確定停在瀏覽游標層。
    """
    # 順序很重要:**先退到底,再測一次**。
    # 第一版寫成「先按 Enter 測、再按 Escape 退」,從指令環裡開始時會原地震盪——
    # 每次 Enter 又鑽進子畫面、每次 Escape 又退回環,永遠出不去(2026-09-04 實測)。
    H.enter_debugger(inst)
    H.debugger_cmd(inst, "BPDEL *")
    H.resume(inst)
    for _ in range(max_escapes):              # 無條件往外退;在瀏覽層 Escape 是 no-op
        press(inst, "cancel", 1.2)
    H.enter_debugger(inst)
    H.debugger_cmd(inst, f"BP 0170:{BP_MOVE_SELECT:08X}")
    H.resume(inst)
    press(inst, "confirm", 2.2)
    hit = _eip(inst) == BP_MOVE_SELECT
    H.enter_debugger(inst)
    H.debugger_cmd(inst, "BPDEL *")
    H.resume(inst)
    if hit:
        press(inst, "cancel", 1.5)            # 從移動選格退回瀏覽層
    return hit


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


def nearest_foe(u: dict, units: list[dict]) -> dict | None:
    foes = [v for v in units if v["camp"] == 0x00 and not (v["acted"] & 0x01) and v["hp"] > 0]
    if not foes:
        return None
    return min(foes, key=lambda v: abs(v["x"] - u["x"]) + abs(v["y"] - u["y"]))


def approach_then_act(inst: str, me: dict, foe: dict, mv: int) -> None:
    """進移動選格 → 朝敵人移動到相鄰格 → 確認落點 → 攻擊。

    2026-09-04:舊版的 `--attack` 只在**已經相鄰**時攻擊,否則原地休息。
    結果是四回合都「四人全動」但敵方數字不動——單位在原地休息,永遠靠不近。
    這一版在移動選格階段主動接近(手動實測可行:idx2 由 (8,16) 移到 (4,18)
    與敵 (3,18) 相鄰後成功攻擊)。
    """
    press(inst, "confirm", 1.8)          # → 移動選格
    # 目標:敵人的相鄰格(優先同列/同行,少一步算一步)
    tx = foe["x"] + (1 if me["x"] > foe["x"] else -1 if me["x"] < foe["x"] else 0)
    ty = foe["y"] if tx != foe["x"] else foe["y"] + (1 if me["y"] > foe["y"] else -1)
    dx, dy = tx - me["x"], ty - me["y"]
    if abs(dx) + abs(dy) > mv:           # 超出移動力就盡量靠近
        scale = mv / max(1, abs(dx) + abs(dy))
        dx, dy = int(dx * scale), int(dy * scale)
    for _ in range(abs(dx)):
        press(inst, "right" if dx > 0 else "left", 0.8)
    for _ in range(abs(dy)):
        press(inst, "down" if dy > 0 else "up", 0.8)
    press(inst, "confirm", 2.2)          # 確認落點 → 環
    press(inst, "up", 1.2)               # ring index 0 = 攻擊
    press(inst, "confirm", 3.0)          # 執行 → 目標選擇
    press(inst, "confirm", 3.0)          # 確認目標


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
    ap.add_argument("--ensure-browse", action="store_true",
                    help="只做一件事:把 UI 帶回瀏覽游標層並證明之,然後結束")
    ap.add_argument("--mv", type=int, default=30,
                    help="接近時假定的移動力(需與 fd2_stat_override --ours-mv 一致)")
    ap.add_argument("--attack", action="store_true",
                    help="相鄰有存活敵方時改為攻擊(ring index 0)而不是原地結束")
    ap.add_argument("--clear-enemy-bit0", action="store_true",
                    help="把敵方 record[+5] 清 0(還原先前實驗寫入的 raw bit0)")
    a = ap.parse_args()

    if a.ensure_browse:
        ok = ensure_browse(a.instance)
        print("已確定在瀏覽游標層" if ok else "無法確定層級(已退到底仍未命中 0x18890)")
        return 0 if ok else 1

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
        proved_this_turn = False
        for _ in range(12):                     # 上限,避免卡住無限迴圈
            # 2026-09-04 修正:每個單位動作前都**先證明**在瀏覽游標層。
            # 舊版直接依 snapshot 的游標值就開始送方向鍵,但游標全域在
            # 移動選格層是同一組,層級判斷不了——結果整輪「我方未行動 N」,
            # 一個單位都沒動(doc48 §5 記錄的已知問題)。
            # 成本考量:神諭的**自證**路徑很貴(完整陣列讀取 + 6 次 Escape + BP 武裝/解除,
            # 約 20 秒),每個單位都跑一次會讓一回合超過 30 分鐘而逾時(2026-09-04 實測)。
            # 策略:**每回合只自證一次**;同回合的後續單位改用便宜的唯讀探測,
            # 只在偵測到 TRANSITION/NOT_IN_BATTLE 時才等,而動作是否成功仍由
            # 事後的 Acted 位元驗證把關——那個檢查便宜且已經存在。
            if proved_this_turn:
                st, why = GS.probe(a.instance, prove_browse=False)
                if st is GS.GameState.TRANSITION_UNREADABLE:
                    time.sleep(3.0)
                    continue
                if st is GS.GameState.NOT_IN_BATTLE:
                    print(f"  已不在戰鬥中({why}),結束")
                    break
            else:
                if not wait_playable(a.instance):
                    print("  等不到可操作狀態(敵方回合/演出未結束?),中止本回合")
                    break
                proved_this_turn = True
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
            elif a.attack and nearest_foe(tgt, units):
                approach_then_act(a.instance, tgt, nearest_foe(tgt, units), a.mv)
            else:
                rest_unit(a.instance)
            # 事後驗證:該單位的 +5 bit7 必須真的被設起來,否則這一步是白做的。
            # 沒有這一步,失敗會安靜地累積成「跑了 N 回合、什麼都沒發生」。
            _, snap2 = snapshot(a.instance, a.selector, a.count)
            done = next((u for u in snap2[1:] if u["idx"] == tgt["idx"]), None)
            if done and not (done["acted"] & 0x80):
                print(f"  idx{tgt['idx']} 行動未生效(acted 仍為 {done['acted']:#04x}),重試一次")
                proved_this_turn = False
                if wait_playable(a.instance):
                    proved_this_turn = True
                    _, snap3 = snapshot(a.instance, a.selector, a.count)
                    move_cursor(a.instance, snap3[0]["cursor"], (tgt["x"], tgt["y"]))
                    rest_unit(a.instance)
        # 回合結尾統計必須避開轉換窗口:2026-09-04 實測,`+6` 陣營位元組在回合翻轉
        # 瞬間會全部讀成同一值,舊版因此把我方 idx3 印成敵方。神諭會明確回報
        # TRANSITION_UNREADABLE,此時**不報數字**,等到可讀再報。
        for _ in range(6):
            st, why = GS.probe(a.instance, prove_browse=False)
            if st is not GS.GameState.TRANSITION_UNREADABLE:
                break
            time.sleep(3.0)
        else:
            print(f"回合 {t}:轉換窗口持續中,本回合不報統計({why})")
            continue
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
