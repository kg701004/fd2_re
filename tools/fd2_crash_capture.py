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


def run_one_round(inst: str, selector: str, count: int, mv: int) -> bool:
    """跟 `fd2_battle_autoplay.py` 主迴圈同一套邏輯選單位、算落點、attack。

    回傳「這一輪有沒有真的找到單位並嘗試行動」——找不到單位(全部已行動/戰鬥已結束)
    回 False,呼叫端據此判斷要不要提早結束,不是死板地跑滿 `--rounds`。
    """
    base, snap = AP.snapshot(inst, selector, count)
    cur, units = snap[0]["cursor"], snap[1:]
    todo = [u for u in units if u["camp"] == 0x02 and u["hp"] > 0 and not (u["acted"] & 0x80)]
    if not todo:
        return False
    tgt = min(todo, key=lambda u: abs(u["x"] - cur[0]) + abs(u["y"] - cur[1]))
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


if __name__ == "__main__":
    sys.exit(main())
