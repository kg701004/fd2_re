#!/usr/bin/env python3
"""fd2_crash_capture.py — 武裝 `BPINT 21 4C`,跑真實的攻擊回合,在真正崩潰的
瞬間捕捉 debugger 狀態,回答 C.2/C.3 留下的問題。

背景
----
`docs/knowledge-base/SESSION-HANDOFF-2026-09-04.md` 附錄 C.2/C.3:
  * `BPINT 21 4C`(DOS `INT 21h AH=4Ch` 結束程式呼叫)這個指令**已驗證**這個
    DOSBox-X debugger build 吃(`BPLIST` 列得出來)。
  * 但**從未驗證過它會不會在真正崩潰的當下觸發**——C.2 那一輪武裝之後手動跑
    29 次攻擊序列,遊戲全程存活,崩潰沒有重現,無從驗證。
  * `docs/knowledge-base/13-battle-menu-system.md` 2026-09-05 §1-§10 這一整輪,
    今天已經用真實多回合遊玩、以及 `fd2_trial_runner.py` 的兩輪正規配對試驗
    **多次重現**這個崩潰——但**每一次都是崩潰後才發現**(截圖看到 `C:\\>`),
    從來沒有在崩潰的**當下**用武裝好的斷點去捕捉。

這支工具就是做這件事:先武裝斷點,再跑真實的 `--attack` 回合,一旦偵測到
debugger 停住(或遊戲已經退回 DOS 卻沒有停住),立刻凍結現場、存檔,不要 resume。

2026-09-05 第一版 vs 這版的差異(誠實記錄一次失敗的設計)
--------------------------------------------------------
第一版為了「排除 debugger 讀值造成干擾」,武裝之後全程盲送同一個算好一次的方向,
不重新讀取單位/敵人座標。實跑 43 輪(3 個不同 instance、mv 4/6/8)全部存活,
遠遠超出 C.16 已知的死亡率——懷疑原因是**同一個方向重複送,實際上多半打在已經
行動過的單位或不存在的落點上,根本沒有真的重跑一次完整的移動+確認流程**。

`docs/knowledge-base/13-battle-menu-system.md` 2026-09-05 §10 的第二輪正規試驗
已經證明「debugger 讀值本身是不是變因」這件事跟本工具的目的無關(該假說已被
推翻),所以**這一版改用跟 `fd2_battle_autoplay.py` 主迴圈完全相同的邏輯**——
每一輪都重新讀單位陣列、選最近的未行動我方單位、算出朝最近敵人的落點——只是
在每一輪動作**之後**額外做 `is_halted()` 檢查(這個檢查本身很輕量,只讀
tmux pane 尾端,不會像 `enter_debugger`/完整陣列讀取那樣造成明顯的額外負擔)。

用法
----
    python tools/fd2_crash_capture.py --instance vic1 --rounds 12 --mv 4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402
import fd2_battle_autoplay as AP  # noqa: E402


def capture_state(inst: str, out_dir: Path, why: str) -> dict:
    """凍結現場:截圖 + 完整 pane 內容(含暫存器)+ 已知斷點清單。不 resume。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    shot = out_dir / "crash_frame.png"
    try:
        H.screenshot(inst, shot)
    except Exception as exc:                                   # noqa: BLE001
        shot = None
        print(f"  (截圖失敗,不影響其餘捕捉:{exc})")
    pane = "\n".join(H._pane_lines(inst))                        # noqa: SLF001
    # `debugger_cmd()` 的回傳值是 shell wrapper 自己的確認字串(例如
    # "sent debugger command: BPLIST"),不是 debugger TUI 真正印出來的內容——
    # 真正的清單要另外從 pane 讀。第一版在這裡誤把 debugger_cmd() 的回傳值當成
    # BPLIST 的實際輸出印出來,是無效資訊,這裡改成送出指令後再讀一次 pane。
    try:
        H.debugger_cmd(inst, "BPLIST")
        bplist_pane = "\n".join(H._pane_lines(inst))            # noqa: SLF001
    except Exception as exc:                                    # noqa: BLE001
        bplist_pane = f"(BPLIST 失敗:{exc})"
    eip = H.read_eip(inst)
    record = {
        "why": why,
        "eip": hex(eip) if eip is not None else None,
        "shot": str(shot) if shot else None,
        "pane": pane,
    }
    (out_dir / "crash_state.txt").write_text(
        f"觸發原因:{why}\nEIP:{record['eip']}\n\n=== pane(含暫存器,停住當下)===\n"
        f"{pane}\n\n=== pane(送出 BPLIST 之後)===\n{bplist_pane}\n", encoding="utf-8")
    return record


OURS = 0x02


def pick_unit(cursor: tuple[int, int], units: list[dict]) -> dict | None:
    """這一輪要操作誰:離游標最近、**還沒行動過**的我方存活單位。沒有就回 None。

    「還沒行動過」是承重的,不是保險。本檔 docstring 記載的第一版失敗就是這一點:
    當時盲送同一個算好一次的方向、不重讀單位,實跑 43 輪(3 個 instance、mv 4/6/8)
    **全部存活**,遠高於 C.16 已知的死亡率——因為重複的方向多半打在**已經行動過**
    的單位或不存在的落點上,根本沒有真的重跑一次完整的移動+確認流程。

    位元用 `fd2_battle_autoplay.BIT_ACTED`(0x80),不再寫裸數字:`record[+5]` 同時
    還有 bit0(死亡／隱藏),兩者名字都叫 `acted`,混用過一次就很難再看出來。
    這裡問的是「我方這回合還能不能動」,所以用 bit7。
    """
    todo = [u for u in units
            if u["camp"] == OURS and u["hp"] > 0 and not (u["acted"] & AP.BIT_ACTED)]
    if not todo:
        return None
    return min(todo, key=lambda u: AP.manhattan(u, {"x": cursor[0], "y": cursor[1]}))


def run_one_round(inst: str, selector: str, count: int, mv: int) -> bool:
    """跟 `fd2_battle_autoplay.py` 主迴圈同一套邏輯選單位、算落點、attack。

    回傳「這一輪有沒有真的找到單位並嘗試行動」——找不到單位(全部已行動/戰鬥已結束)
    回 False,呼叫端據此判斷要不要提早結束,不是死板地跑滿 `--rounds`。
    """
    base, snap = AP.snapshot(inst, selector, count)
    cur, units = snap[0]["cursor"], snap[1:]
    tgt = pick_unit(cur, units)
    if tgt is None:
        return False
    AP.move_cursor(inst, cur, (tgt["x"], tgt["y"]))
    if AP.adjacent_foe(tgt, units):
        AP.attack_unit(inst, selector)
    else:
        foe = AP.nearest_foe(tgt, units)
        if foe is None:
            AP.rest_unit(inst)
        else:
            AP.approach_then_act(inst, tgt, foe, mv, "computed", selector=selector, count=count)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--rounds", type=int, default=12,
                    help="最多跑幾輪單位行動(C.16 mv4 條件通常撐不過一輪半就死,"
                         "但每輪都是真實選單位+算落點,不是重複同一個動作)")
    ap.add_argument("--mv", type=int, default=4)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    out_dir = Path(a.out) if a.out else (H.DEFAULT_SHOT_DIR / a.instance / "crash_capture")

    # ---- 武裝 BPINT 21 4C ----
    H.enter_debugger(a.instance)
    H.debugger_cmd(a.instance, "BPDEL *")
    H.debugger_cmd(a.instance, "BPINT 21 4C")
    H.resume(a.instance)
    print("已武裝 BPINT 21 4C,開始跑真實攻擊回合(每輪都重新選單位/算落點)")

    for r in range(1, a.rounds + 1):
        acted = run_one_round(a.instance, a.selector, a.count, a.mv)
        if H.is_halted(a.instance):
            print(f"第 {r} 輪之後偵測到 debugger 停住——凍結現場")
            rec = capture_state(a.instance, out_dir,
                                why=f"is_halted()==True,第 {r} 輪之後")
            print(f"EIP={rec['eip']}")
            print(f"詳細寫入 {out_dir}/crash_state.txt(未 resume,現場保留)")
            return 0
        if not acted:
            print(f"第 {r} 輪:找不到可行動單位(可能戰鬥已結束或轉場中),停止")
            break
        print(f"第 {r} 輪:未停住,繼續")

    alive, meas = H.game_alive(a.instance)
    if not alive:
        print("跑完/中止後,debugger 從未停住,但畫面顯示遊戲已經退回 DOS——"
              "**BPINT 沒有攔到這次結束**,不是乾淨的 INT 21 AH=4C 呼叫,"
              "或者呼叫發生在偵測窗口之間被錯過。")
        H.enter_debugger(a.instance)
        rec = capture_state(a.instance, out_dir,
                            why="game_alive()==False 但 BPINT 從未觸發")
        print(f"詳細寫入 {out_dir}/crash_state.txt")
        return 1
    print(f"遊戲仍存活,BPINT 未觸發——這次沒有重現崩潰"
          "(C.16 是機率性的,不代表機制不存在,見 fd2_trial_runner.py 的方法論)。")
    return 3


def _u(idx=0, camp=OURS, x=0, y=0, hp=10, acted=0):
    return {"idx": idx, "camp": camp, "x": x, "y": y, "hp": hp, "acted": acted}


def selftest() -> int:
    """選單位那一層。武裝斷點、送鍵、偵測凍結需要活的 DOSBox,不在範圍內——
    但**選錯單位**正是第一版失敗的原因,而那完全是離線可判的。"""
    fails = []
    cursor = (5, 5)

    print("(1) 第一版失敗的根因:已行動過的單位不得被選中")
    # 盲送同方向、不重讀單位,實跑 43 輪全部存活——因為重複的方向多半打在已經
    # 行動過的單位上,根本沒有真的重跑一次完整流程。
    units = [_u(0, OURS, 5, 6, 10, AP.BIT_ACTED), _u(1, OURS, 5, 9, 10, 0)]
    picked = pick_unit(cursor, units)
    ok1 = picked is not None and picked["idx"] == 1
    print(f"    {'PASS' if ok1 else 'FAIL'}: 選中 idx{picked['idx'] if picked else None}"
          f"(idx0 較近但已行動,應選較遠的 idx1)")
    if not ok1:
        fails.append(f"選到已行動的單位:{picked}")

    print("\n(2) 對照:同一組單位,若 idx0 未行動就必須選它(否則第 (1) 題只是距離)")
    units2 = [_u(0, OURS, 5, 6, 10, 0), _u(1, OURS, 5, 9, 10, 0)]
    p2 = pick_unit(cursor, units2)
    ok2 = p2 is not None and p2["idx"] == 0
    print(f"    {'PASS' if ok2 else 'FAIL'}: 選中 idx{p2['idx'] if p2 else None}(應 0,最近)")
    if not ok2:
        fails.append(f"距離判定不正確:{p2}")

    print("\n(3) 陣營與存活:敵方、死亡的我方都不得被選")
    units3 = [_u(0, 0x00, 5, 6, 10, 0), _u(1, OURS, 5, 7, 0, 0), _u(2, OURS, 5, 9, 10, 0)]
    p3 = pick_unit(cursor, units3)
    ok3 = p3 is not None and p3["idx"] == 2
    print(f"    {'PASS' if ok3 else 'FAIL'}: 選中 idx{p3['idx'] if p3 else None}"
          f"(idx0 敵方、idx1 HP=0,應選 idx2)")
    if not ok3:
        fails.append(f"陣營或存活篩選不正確:{p3}")

    print("\n(4) 兩個位元不得混用:bit0(死亡/隱藏)不該擋下我方選取")
    # record[+5] 的 bit0 是死亡／隱藏、bit7 才是已行動(見 fd2_battle_autoplay
    # 的常數說明)。這裡問的是「還能不能動」,所以只看 bit7;HP>0 的存活判斷
    # 由 hp 欄位負責,不要拿 bit0 來重複做一次還做錯。
    units4 = [_u(0, OURS, 5, 6, 10, AP.BIT_INACTIVE)]
    p4 = pick_unit(cursor, units4)
    ok4 = (p4 is not None and p4["idx"] == 0
           and pick_unit(cursor, [_u(0, OURS, 5, 6, 10, AP.BIT_ACTED)]) is None)
    print(f"    {'PASS' if ok4 else 'FAIL'}: bit0 置起仍可選={p4 is not None}、"
          f"bit7 置起不可選")
    if not ok4:
        fails.append("bit0/bit7 在選單位時被混用")

    print("\n(5) 非平凡性 + 負向控制")
    all_acted = [_u(i, OURS, 5, 6 + i, 10, AP.BIT_ACTED) for i in range(3)]
    picks = {(pick_unit(cursor, u) or {}).get("idx") for u in (units, units2, units3)}
    ok5 = (pick_unit(cursor, all_acted) is None and pick_unit(cursor, []) is None
           and len(picks) == 3)
    print(f"    {'PASS' if ok5 else 'FAIL'}: 全部已行動 -> None、空陣列 -> None、"
          f"三組輸入選出 {len(picks)} 個不同單位 {sorted(x for x in picks if x is not None)}")
    if not ok5:
        fails.append(f"選取結果不隨輸入變化:{picks}")

    print("\n(6) HP=1 的單位算存活;距離用游標的 x 對 x、y 對 y")
    # 2026-09-11 窮舉突變測試:`hp > 0` 與 `cursor[0]` 改掉逃掉 —— 既有案例的游標 x == y,
    # 也沒有 HP=1 的單位。游標 (0,10):A 在 (0,9) 距離 1、B 在 (10,0) 距離 20;
    # x/y 對調時 A 變 11、B 變 10,就會選到 B。
    u_a = {"camp": OURS, "hp": 1, "acted": 0, "x": 0, "y": 9}
    u_b = {"camp": OURS, "hp": 5, "acted": 0, "x": 10, "y": 0}
    got6 = pick_unit((0, 10), [u_a, u_b])
    ok6 = got6 is u_a
    print(f"    {'PASS' if ok6 else 'FAIL'}: 選到 {'A' if got6 is u_a else 'B' if got6 is u_b else got6}(應 A)")
    if not ok6:
        fails.append("HP=1 被當成死亡,或游標 x/y 對應錯誤")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(第一版失敗根因的回歸 + 距離對照 + 陣營與存活 "
          "+ 兩個位元不混用 + 非平凡性)。斷點與凍結捕捉未涵蓋,見 docstring。")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
