#!/usr/bin/env python3
"""fd2_sfx_screen_map.py — 把 SFX index 對應到玩家實際看到的畫面/操作(原版實機)。

背景
----
`play_sfx_a` 的 81 個呼叫端裡有 65 個 push 的是**常數 index**,已靜態解出完整
index→呼叫端對映(`docs/data/sfx_index_callers.json`,doc36 2026-09-04 段落)。
剩下的是把「呼叫端」對應到「玩家看得到的畫面」。

方法:**在呼叫點下斷點,不是在函式下斷點。**
呼叫點本身就決定 index,所以命中哪個斷點 = 播了哪個 index,**完全不必讀堆疊**。
這一點很重要,因為 `MEMDUMPBIN` 在斷點停住時會靜默失敗(上游 #3629),
在斷點現場讀參數並不可靠。

⚠ 位址提醒:doc36 第 8 輪記的 `play_sfx_a=0x026896` 是 file offset 誤當 linear
(偏差 `+0xE00`),第 9 輪已勘誤為 `0x25a96`。用舊值下斷點永遠不會命中,
而「沒命中」看起來就等於「這個動作沒有音效」——會直接產生假結論。

用法
----
    python tools/fd2_sfx_screen_map.py --instance sfx1 --arm 2,3,4,5,6,7,8,11
    python tools/fd2_sfx_screen_map.py --instance sfx1 --probe confirm
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CALLERS = REPO / "docs" / "data" / "sfx_index_callers.json"
DELTA = 0x19C000


def load_map() -> dict[int, list[int]]:
    d = json.load(CALLERS.open(encoding="utf-8"))["index_to_callers"]
    return {int(k): [int(x, 16) for x in v] for k, v in d.items()}


def load_verification() -> tuple[dict[int, int], dict[int, dict]]:
    """回傳 (已活體確認的 site→index, 已知歸屬錯誤的 site→細節)。

    **這一層是必要的,不是裝飾**:`index_to_callers` 是靜態貪婪解析的產物,
    對「被跳進的 call」會歸屬錯誤且毫無徵兆(見資料檔 `_meta.caveat`)。
    2026-09-04 實測:probe 命中 `0x32307` 時,工具照靜態表印出「index 11」,
    而該呼叫點的活體值是 9——**工具給了一個看起來正常的錯數字**。
    """
    meta = json.load(CALLERS.open(encoding="utf-8")).get("_meta", {})
    ok = {int(k, 16): v for k, v in meta.get("live_verified", {}).items()}
    bad = {int(k, 16): v for k, v in meta.get("known_misattributed", {}).items()}
    return ok, bad


def describe_hit(site: int, static_idx: int) -> str:
    """命中一個呼叫點時該怎麼講。**未經活體確認就不給裸數字。**"""
    ok, bad = load_verification()
    if site in bad:
        e = bad[site]
        return (f"呼叫點 0x{site:x} —— ⚠ **已知靜態歸屬為錯**:靜態表寫 index "
                f"{e['static_index']},活體讀到 **{e['live_index']}**。{e.get('note', '')}")
    if site in ok:
        return f"**index {ok[site]}**(已活體確認)  呼叫點 0x{site:x}"
    return (f"呼叫點 0x{site:x} —— 靜態表歸為 index {static_idx},"
            f"**但此呼叫點未經活體確認,不可當成已確認的 index**"
            f"(見 sfx_index_callers.json 的 `_meta`)")


def pane(inst: str) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "tmux", "-L", "fd2harness",
                        "capture-pane", "-t", f"harness-{inst}", "-p"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.stdout


def halted(inst: str) -> bool:
    """debugger 是否真的停住。

    **不能只讀 EIP**:register view 在執行中也會更新,所以 EIP 落在某個位址
    完全可能只是 CPU 正好經過,不是斷點命中。2026-09-04 因為漏了這一步,
    連續四筆 probe 讀到同一個 EIP 而被誤判成「每次都命中」。
    """
    tail = pane(inst).splitlines()[-3:]
    return not any("(Running)" in ln for ln in tail)


def eip(inst: str) -> str | None:
    if not halted(inst):
        return None
    for ln in pane(inst).splitlines()[:8]:
        if "EIP=" in ln:
            return ln.split("EIP=")[1].split()[0]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--arm", help="要武裝的 index,逗號分隔(例:2,3,4,5,6,7,8,11)")
    ap.add_argument("--probe", help="送出一個鍵,回報命中哪個呼叫點")
    ap.add_argument("--baseline", type=int, metavar="N",
                    help="**必須先跑**:完全不按鍵,連續觀察 N 次,列出會自己命中的呼叫點")
    ap.add_argument("--exclude", default="",
                    help="逗號分隔的呼叫點(hex),武裝時略過——放 --baseline 找到的自走點")
    ap.add_argument("--wait", type=float, default=3.0)
    a = ap.parse_args()

    m = load_map()
    site2idx: dict[int, int] = {s: i for i, ss in m.items() for s in ss}

    if a.arm:
        want = [int(x) for x in a.arm.split(",")]
        H.enter_debugger(a.instance)
        H.debugger_cmd(a.instance, "BPDEL *")
        n = 0
        skip = {int(x, 16) for x in a.exclude.split(",") if x.strip()}
        for i in want:
            for s in m.get(i, []):
                if s in skip:
                    continue
                H.debugger_cmd(a.instance, f"BP 0170:{s + DELTA:08X}")
                n += 1
        H.resume(a.instance)
        print(f"已武裝 {n} 個呼叫點(index {want})")
        return 0

    if a.baseline:
        # 沒有這一步,整個方法都是假的:某些呼叫點在每幀/待機路徑上,
        # **不按任何鍵也會命中**,於是每次 probe 都「命中」,與按了什麼無關。
        # 2026-09-04 實測:0x16546 連續三次在零輸入下自己命中,前一輪
        # 五筆「index 2 = 確認鍵」因此全部作廢。
        import time
        seen: dict[int, int] = {}
        for _ in range(a.baseline):
            H.resume(a.instance)
            time.sleep(2.5)
            e = eip(a.instance)
            if not e:
                continue
            live = int(e, 16)
            for off in range(0, 8):
                s = live - off - DELTA
                if s in site2idx:
                    seen[s] = seen.get(s, 0) + 1
                    break
        H.resume(a.instance)
        if seen:
            print("自走呼叫點(零輸入即命中),probe 時必須排除:")
            for s, c in sorted(seen.items()):
                print(f"  0x{s:x}  index {site2idx[s]}  命中 {c}/{a.baseline}")
            print("--exclude " + ",".join(f"{s:x}" for s in sorted(seen)))
        else:
            print(f"{a.baseline} 次零輸入觀察都沒有自走命中,可以進行 probe")
        return 0

    if a.probe:
        # 若停在斷點上先續跑,否則按鍵不會被遊戲收到
        if "(Running)" not in "\n".join(pane(a.instance).splitlines()[-3:]):
            H.resume(a.instance)
        H.send_keys(a.instance, [H.resolve_key(a.probe)])
        import time
        time.sleep(a.wait)
        e = eip(a.instance)
        if not e:
            print(f"{a.probe}: 沒有停在斷點上(遊戲仍在執行)→ 此動作未觸發已武裝的任何呼叫點")
            return 1
        live = int(e, 16)
        # 斷點命中後 CPU 可能已步過該指令幾個 byte,允許小範圍
        for off in range(0, 8):
            s = live - off - DELTA
            if s in site2idx:
                print(f"{a.probe}: {describe_hit(s, site2idx[s])}  (EIP={e}, 步過 {off} bytes)")
                H.resume(a.instance)
                return 0
        print(f"{a.probe}: 未命中任何已武裝的呼叫點 (EIP={e})")
        return 1

    ap.error("需要 --arm 或 --probe")
    return 2


if __name__ == "__main__":
    sys.exit(main())
