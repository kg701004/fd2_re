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


RING_SEL = 0x53C57          # 指令環目前選到第幾項(doc11 §環項 index)
RING_ATTACK = 0
RING_REST = 3


def ring_selection(inst: str, selector: str = "0170") -> int | None:
    """讀指令環目前選到哪一項。讀不到回 None(不猜)。"""
    H.enter_debugger(inst)
    v = H.mem_read_global(inst, selector, RING_SEL, 1,
                          H.DEFAULT_SHOT_DIR / inst / "ringsel").get("u8")
    H.resume(inst)
    return v


def select_ring(inst: str, want: int, key: str, selector: str = "0170") -> bool:
    """按方向鍵選環項,**回讀確認真的選中了才回 True**。

    方向鍵是絕對設值但**受該項的 enable gate 管**(doc13:834)。項目不可用時
    按鍵毫無作用,而環的選擇維持原值——後面若照樣按確認,執行的就是別的指令。
    這是整個 autoplay 裡唯一還沒被排除的「盲按」,見 attack_unit 的說明。
    """
    press(inst, key, 1.2)
    sel = ring_selection(inst, selector)
    if sel == want:
        return True
    print(f"    環選擇是 {sel}(期望 {want})——按鍵未生效,**不盲按確認**")
    return False


def attack_unit(inst: str, selector: str = "0170") -> bool:
    """已對準單位時嘗試原地攻擊。**確認環真的選在「攻擊」才按下去。**

    doc13 §「指令環4選項的動態 enable gate」記載的真實程式碼:

        if (scancode==0x48 && enableFlags[0]==0) DAT_00053c57 = 0;   // ↑ → 攻擊
        else if (scancode==0x50 && enableFlags[3]==0) DAT_00053c57 = 3; // ↓ → 待機

    ↑ 是**絕對設值**,但**有前提**:`enableFlags[0]==0`(攻擊可用)。射程內沒有候選時
    ↑ 完全不生效,`[0x53c57]` 維持原值——而舊版在這之後直接連按兩次確認,
    等於**閉著眼睛執行環裡當時選著的任何一項**。

    2026-09-04:`--attack` 的兩次執行都以 FD2.EXE 退回 DOS 收場,而
    (a) 只套用數值覆寫、零輸入靜置 3 分鐘,以及 (b) 不含 `--attack` 的完整一回合
    (四人全動),兩者都不會。成因未確定,但盲按序列是唯一還沒被排除的差異,
    所以這裡改成先驗證再按。回傳是否真的送出了攻擊。
    """
    press(inst, "confirm", 1.8)   # → 移動選格
    press(inst, "confirm", 2.2)   # 確認原地 → 開環
    if not select_ring(inst, RING_ATTACK, "up", selector):
        # 不按確認。取消退出環,把單位留給後續邏輯,而不是執行未知指令。
        press(inst, "cancel", 1.0)
        return False
    press(inst, "confirm", 3.5)   # 執行 → 目標選擇
    press(inst, "confirm", 3.5)   # 確認目標
    return True


def nearest_foe(u: dict, units: list[dict]) -> dict | None:
    foes = [v for v in units if v["camp"] == 0x00 and not (v["acted"] & 0x01) and v["hp"] > 0]
    if not foes:
        return None
    return min(foes, key=lambda v: abs(v["x"] - u["x"]) + abs(v["y"] - u["y"]))


def approach_then_act(inst: str, me: dict, foe: dict, mv: int,
                      dest_mode: str = "computed") -> None:
    """進移動選格 → 朝敵人移動到相鄰格 → 確認落點 → 攻擊。

    2026-09-04:舊版的 `--attack` 只在**已經相鄰**時攻擊,否則原地休息。
    結果是四回合都「四人全動」但敵方數字不動——單位在原地休息,永遠靠不近。
    這一版在移動選格階段主動接近(手動實測可行:idx2 由 (8,16) 移到 (4,18)
    與敵 (3,18) 相鄰後成功攻擊)。
    """
    press(inst, "confirm", 1.8)          # → 移動選格
    # 目標:敵人的相鄰格(優先同列/同行,少一步算一步)
    if dest_mode == "fixed":
        # 差分測試用:移動同樣的**步數**,但落點不是算出來朝向敵人的。
        #
        # 2026-09-04:六個手寫階梯階段、三個實例、上百輪都殺不死遊戲,而**真正的
        # autoplay 加 `--mv 0`(等於關掉移動)一次就活了下來**——同一支程式、
        # 同樣的 --attack、同樣的快照密度,只差移動。所以移動被指認。
        # 但階梯的 C/E 也移動並確認落點卻活著,長距離版(10 格)同樣活著,
        # 差別在於階梯是往固定方向亂移,autoplay 是**算出朝向敵人的落點**
        # (可能被佔據、不可達、或落在敵方身上)。
        #
        # 這個模式把「移動」與「算出來的落點」分開:兩者步數相同,只有目的地不同。
        # 手寫階梯做不到這件事,因為它一開始就不是真正的 autoplay。
        dx, dy = min(mv, 2), 0
    else:
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
    if not select_ring(inst, RING_ATTACK, "up"):
        press(inst, "cancel", 1.0)
        return
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
    if not select_ring(inst, RING_REST, "down"):
        press(inst, "cancel", 1.0)
        return
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
    ap.add_argument("--dest", choices=("computed", "fixed"), default="computed",
                    help="approach 的落點:computed=算出朝向敵人(預設)、"
                         "fixed=同步數但固定方向。**差分測試用**:讓程式碼決定變因,"
                         "而不是另外手寫一個模擬品(見 approach_then_act 的說明)")
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
        targets = [u["idx"] for u in units if u["camp"] == 0x00 and u["acted"] & 0x01]
        for idx in targets:
            H.debugger_cmd(a.instance, f"SMV {base + idx*0x50 + 5:08x} 00")
        # 寫後回讀。2026-09-04:此前這裡直接印「已清除」,SMV 靜默失敗時
        # 訊息一模一樣——講的是送出了指令,不是值真的改了。
        bad = []
        for idx in targets:
            got = H.mem_read_global(a.instance, a.selector, base + idx*0x50 + 5, 1,
                                    H.DEFAULT_SHOT_DIR / a.instance / "bit0verify",
                                    delta=0).get("u8")
            if got is None or got & 0x01:
                bad.append((idx, got))
        H.resume(a.instance)
        print(f"敵方 +5 bit0:嘗試 {len(targets)} 筆,回讀確認 {len(targets)-len(bad)} 筆"
              + ("" if not bad else f";未生效 {[i for i, _ in bad]}"))
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
                approach_then_act(a.instance, tgt, nearest_foe(tgt, units), a.mv, a.dest)
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
