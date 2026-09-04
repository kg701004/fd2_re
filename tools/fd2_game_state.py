#!/usr/bin/env python3
"""fd2_game_state.py — 原版 DOSBox-X 的**遊戲狀態神諭**:回傳已證明的狀態,不是猜的。

為什麼需要這一層
----------------
2026-09-04 一整天的失敗都是同一個形狀:**每支工具各自實作了半套狀態判斷**,
而且各壞各的:

| 工具 | 它自己的判準 | 怎麼壞的 |
|---|---|---|
| drive 腳本 | `in_battle`(讀單位陣列) | 戰前演出就成立 → 之後操作全送錯層 |
| `fd2_battle_autoplay` | 讀游標全域 `[0x53ab1]` | 移動選格層用**同一組**全域 → 整輪不動 |
| `fd2_sfx_screen_map` | 讀 EIP | 沒確認停住 → 四筆假命中 |
| autoplay 回合結尾統計 | 讀 `+6` 陣營 | 在轉換窗口讀 → 把我方 idx3 算成敵方 |

共同教訓:**布林值不夠**。`ensure_browse` 回傳 False 混了「回不去」與「還輪不到你」,
呼叫端只能猜;而「讀得到單位陣列」也不等於「這些值現在可信」。
所以這裡回傳**列舉**,並且每個狀態都有自己的證明方式。

證明方式(刻意不依賴跨層共用的全域)
------------------------------------
* `BROWSE_CURSOR`：在 `0x18890`(移動選格入口)下斷點後按 Enter 會命中——
  只有從瀏覽層按才進得去,所以命中即為證明。這是**自證**,不是讀值推論。
* `TRANSITION_UNREADABLE`：單位陣列的 `+6` 陣營位元組在回合轉換瞬間會全部讀成同一值
  (實測:12 個槽全被讀成敵方)。此時**任何**基於該陣列的判斷都不可信,明確回報不可讀,
  而不是硬給一個數字。
* `IN_BATTLE_NOT_PLAYABLE`：陣列可信且雙陣營齊全,但 `0x18890` 進不去
  (戰前演出、敵方回合、動作演出進行中)。
* `NOT_IN_BATTLE`：陣列本身不通過內部一致性(見 `fd2_in_battle_check.py`)。

用法
----
    python tools/fd2_game_state.py --instance win2
    python tools/fd2_game_state.py --instance win2 --wait-playable 60
"""

from __future__ import annotations

import argparse
import enum
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

BP_MOVE_SELECT = 0x18890 + 0x19C000     # 0x1B4890
CUR_X, CUR_Y = 0x53AB1, 0x53AB5
UNIT_COUNT = 0x53BEB


class GameState(enum.Enum):
    BROWSE_CURSOR = "BROWSE_CURSOR"                   # 玩家可操作,已證明
    IN_BATTLE_NOT_PLAYABLE = "IN_BATTLE_NOT_PLAYABLE"  # 在戰鬥但現在輪不到/演出中
    TRANSITION_UNREADABLE = "TRANSITION_UNREADABLE"    # 轉換窗口,讀值不可信
    NOT_IN_BATTLE = "NOT_IN_BATTLE"
    GAME_NOT_RUNNING = "GAME_NOT_RUNNING"              # FD2.EXE 已退回 DOS(畫面判定)
    UNKNOWN = "UNKNOWN"


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


def _press(inst: str, key: str, wait: float) -> None:
    H.send_keys(inst, [H.resolve_key(key)])
    time.sleep(wait)


def read_units(inst: str, selector: str = "0170"
               ) -> tuple[int | None, list[dict], str, bool]:
    """回傳 (array_base, records, 診斷, 是否為讀取失敗)。不做狀態判斷,只負責讀。

    **最後那個布林值是必要的**:「讀到的資料說不在戰鬥」與「這次根本沒讀到」
    是兩件事,前者是結論、後者只是要重試。2026-09-04 實測到 `mem_read_unit_array`
    會間歇性回傳全 0 記錄(當時指令環就開在畫面上),若把它當成 NOT_IN_BATTLE,
    呼叫端就會在戰鬥進行中放棄——正是 autoplay「等不到可操作狀態」的形狀。
    """
    d = H.DEFAULT_SHOT_DIR / inst / "gamestate"
    cnt = H.mem_read_global(inst, selector, UNIT_COUNT, 1, d).get("u8") or 0
    if not 1 <= cnt <= 96:
        return None, [], f"[0x53beb]={cnt} 不在合理範圍", False
    res = H.mem_read_unit_array(inst, selector, d, num_records=min(cnt, 32))
    if res.get("error"):
        return None, [], f"讀取失敗:{res['error']}", True
    return int(res["array_base"], 16), res["records"][:cnt], "", False


def classify_units(recs: list[dict]) -> tuple[GameState, str]:
    """只用單位陣列能判到的部分。**轉換窗口必須被抓出來,不能硬給數字。**"""
    live = [r for r in recs if not (r["hp_max"] == 0 and r["hp_cur"] == 0)]
    if not live:
        return GameState.NOT_IN_BATTLE, "沒有任何非空槽"
    camps = {r["camp"] for r in live}
    if camps == {0x00} or camps == {0x02}:
        # 實測:回合轉換瞬間 12 個槽會全部讀成同一陣營(2026-09-04)
        return (GameState.TRANSITION_UNREADABLE,
                f"所有 {len(live)} 個非空槽的 +6 都是 {camps.pop():#04x} —— 轉換窗口,讀值不可信")
    if not camps <= {0x00, 0x01, 0x02}:
        return GameState.NOT_IN_BATTLE, f"camp 值超出列舉:{[hex(c) for c in camps]}"
    # HP 界線刻意放寬到 u16 上限:原本的 `<= 9999` 是用來擋壞讀的,但它與本專案
    # 自己的 fd2_stat_override 工作流相衝突——覆寫寫入 9999 之後只要單位升級
    # (2026-09-04 實測:idx2 擊殺後 hp_max 變 10016)整場就會被誤判成 NOT_IN_BATTLE。
    # 擋壞讀的工作已經由更強的檢查接手:mem_read_unit_array 的全零/短讀防護,
    # 加上下面 camp 值域與 cur<=max 的內部一致性——那些是壞讀真正過不了的關卡。
    bad = [r for r in live if not (0 < r["hp_max"] <= 0xFFFF and r["hp_cur"] <= r["hp_max"])]
    if bad:
        return (GameState.NOT_IN_BATTLE,
                f"{len(bad)}/{len(live)} 筆 HP 欄位不自洽,例 idx{bad[0]['index']} "
                f"{bad[0]['hp_cur']}/{bad[0]['hp_max']}")
    return GameState.IN_BATTLE_NOT_PLAYABLE, f"陣列可信:{len(live)} 個單位,雙陣營齊全"


def probe(inst: str, selector: str = "0170", prove_browse: bool = True
          ) -> tuple[GameState, str]:
    """回傳 (狀態, 證據)。`prove_browse=False` 時只做讀值層級的判斷(較快、無副作用)。"""
    # 2026-09-04:先確認遊戲還在。退回 DOS 後這些位址仍留著舊值,單位陣列有時讀成
    # 全 0、有時讀出**成功但是垃圾**的 12 筆——兩種都與「暫時性壞讀」在記憶體上無法分辨。
    # 「讀不到」不等於「不在戰鬥」(見 read_units),而「讀得到」也不等於「遊戲還在」。
    alive, meas = H.game_alive(inst)
    if not alive:
        return (GameState.GAME_NOT_RUNNING,
                f"畫面判定 FD2.EXE 已不在執行(相異顏色 {meas['distinct_colors']}、"
                f"非黑 {meas['nonblack_ratio']});記憶體讀值是殘留,不可解讀")

    H.enter_debugger(inst)
    base, recs, err, read_failed = read_units(inst, selector)
    H.resume(inst)
    if read_failed:
        # 讀不到 ≠ 不在戰鬥。回 UNKNOWN,讓 wait_playable 繼續等而不是直接放棄。
        return GameState.UNKNOWN, err
    if err:
        return GameState.NOT_IN_BATTLE, err
    st, why = classify_units(recs)
    if st is not GameState.IN_BATTLE_NOT_PLAYABLE or not prove_browse:
        return st, why

    # 自證瀏覽層:先無條件退到底(Escape 在瀏覽層是 no-op),再按一次 Enter。
    # 順序不可反——先測後退會在指令環裡原地震盪(2026-09-04 實測)。
    H.enter_debugger(inst)
    H.debugger_cmd(inst, "BPDEL *")
    H.resume(inst)
    for _ in range(6):
        _press(inst, "cancel", 1.1)
    H.enter_debugger(inst)
    H.debugger_cmd(inst, f"BP 0170:{BP_MOVE_SELECT:08X}")
    H.resume(inst)
    _press(inst, "confirm", 2.2)
    hit = _eip(inst) == BP_MOVE_SELECT
    H.enter_debugger(inst)
    H.debugger_cmd(inst, "BPDEL *")
    H.resume(inst)
    if hit:
        _press(inst, "cancel", 1.4)          # 從移動選格退回瀏覽層
        return GameState.BROWSE_CURSOR, f"{why};`0x18890` 命中,層級已證"
    return GameState.IN_BATTLE_NOT_PLAYABLE, f"{why};但 `0x18890` 進不去(輪不到/演出中)"


def wait_playable(inst: str, timeout: float = 60.0, gap: float = 4.0
                  ) -> tuple[GameState, str]:
    """等到 BROWSE_CURSOR 或逾時。**「還輪不到你」與「回不去」是兩件事**,前者只要等。"""
    end = time.time() + timeout
    last = (GameState.UNKNOWN, "尚未探測")
    while time.time() < end:
        last = probe(inst)
        if last[0] is GameState.BROWSE_CURSOR:
            return last
        time.sleep(gap)
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--no-prove", action="store_true", help="只做讀值層級判斷,不動遊戲")
    ap.add_argument("--wait-playable", type=float, metavar="SEC")
    a = ap.parse_args()
    if a.wait_playable:
        st, why = wait_playable(a.instance, a.wait_playable)
    else:
        st, why = probe(a.instance, a.selector, prove_browse=not a.no_prove)
    print(f"{st.value}: {why}")
    return 0 if st is GameState.BROWSE_CURSOR else 1


if __name__ == "__main__":
    sys.exit(main())
