#!/usr/bin/env python3
"""fd2_zero_read_capture.py — 抓住「靜默壞讀」發生**當下**的狀態。

要查的東西
----------
2026-09-04 觀察到:`mem_read_unit_array` 會回傳整段全 0 的單位陣列,而
`MEMDUMPBIN` 回報成功、`error` 是 None、遊戲活著、指令環開在畫面上;
幾秒後同一個呼叫又完全正常。

已經分離出**兩種**失敗模式,只解釋了一種:

* **模式 1 — 未停住就 dump**:MEMDUMPBIN 根本不寫檔,shell 層會大聲報錯
  (上游 #3629)。已由 `H.wait_halted()` 擋掉。
* **模式 2 — 停住了、dump 回報成功、內容全 0**:**仍未解釋**。
  `mem_read_unit_array` 現在會重試 3 次,那會把第一次全零吃掉,
  所以**不能用它來診斷**——本工具自己走低階流程,一次都不重試。

它捕捉什麼
----------
偵測到全 0 的**那一刻**立即記下(順序照重要性排,先記最易變的):

1. `is_halted()` —— debugger 是否真的停住
2. tmux pane 尾端 —— MEMDUMPBIN 到底印了什麼(success?)
3. WSL 端 `~/fd2-run-harness-<inst>/MEMDUMP.BIN` 的存在/大小/mtime
   —— 分辨「沒寫檔」與「寫了一個全 0 的檔」
4. 本地複製到的檔案大小
5. `[0x53a45]`(陣列指標)與 `[0x53beb]`(單位數)是否仍合理
6. 截圖 —— **唯一能分辨「遊戲還在」與「已退回 DOS」的獨立訊號**
   (那兩種情況下記憶體讀值可以完全一樣,見 doc12 續四)

⚠ 本工具**只記錄,不下結論**。全 0 有多種可能來源,而區分它們正是待辦事項本身。

用法
----
    python tools/fd2_zero_read_capture.py --instance dbg1 --tries 40
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

UNIT_COUNT = 0x53BEB
ARRAY_PTR = 0x53A45


def wsl(cmd: str) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "bash", "-lc", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def capture(inst: str, tag: str, extra: dict) -> dict:
    """把當下狀態全部抓下來。順序照易變程度,先抓最易變的。"""
    snap: dict = {"tag": tag, "t": time.strftime("%H:%M:%S")}
    snap["halted"] = H.is_halted(inst)
    snap["pane_tail"] = [ln for ln in H._pane_tail(inst, 6)]
    snap["memdump_bin"] = wsl(f"ls -l --time-style=+%H:%M:%S "
                              f"~/fd2-run-harness-{inst}/MEMDUMP.BIN").strip()
    snap.update(extra)
    return snap


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--selector", default="0170")
    ap.add_argument("--tries", type=int, default=40)
    ap.add_argument("--gap", type=float, default=0.8)
    ap.add_argument("--records", type=int, default=12)
    a = ap.parse_args()

    out_dir = H.DEFAULT_SHOT_DIR / a.instance / "zerocapture"
    out_dir.mkdir(parents=True, exist_ok=True)
    dump = out_dir / "array_dump.bin"

    H.enter_debugger(a.instance)
    if not H.wait_halted(a.instance):
        print("debugger 未停住,中止(這是模式 1,不是本工具要查的)")
        return 2
    res = H.mem_read_unit_array(a.instance, a.selector, out_dir, num_records=a.records)
    if res.get("error"):
        print("基準讀取就失敗,無法建立對照:", res["error"][:120])
        H.resume(a.instance)
        return 2
    base = int(res["array_base"], 16)
    delta = int(res["delta"], 16)
    print(f"基準 OK:base={base:#x} delta={delta:#x};開始 {a.tries} 次低階讀取(不重試)")
    H.resume(a.instance)

    events, good = [], 0
    for i in range(1, a.tries + 1):
        H.enter_debugger(a.instance)
        halted = H.wait_halted(a.instance)
        try:
            dump.unlink()
        except FileNotFoundError:
            pass
        err = None
        try:
            H.mem_dump(a.instance, a.selector, f"{base:x}",
                       f"{a.records * 0x50:x}", dump)
        except Exception as exc:                       # noqa: BLE001
            err = f"{exc.__class__.__name__}: {exc}"
        data = dump.read_bytes() if dump.exists() else b""
        if err is None and len(data) == a.records * 0x50 and any(data):
            good += 1
            H.resume(a.instance)
            time.sleep(a.gap)
            continue

        # ---- 命中:立刻抓狀態,順序很重要 -------------------------------
        ptr = H.mem_read_global(a.instance, a.selector, ARRAY_PTR, 4, out_dir).get("u32")
        cnt = H.mem_read_global(a.instance, a.selector, UNIT_COUNT, 1, out_dir).get("u8")
        snap = capture(a.instance, f"try{i}", {
            "halted_before_dump": halted,
            "mem_dump_exception": err,
            "local_bytes": len(data),
            "all_zero": (len(data) > 0 and not any(data)),
            "array_ptr": hex(ptr) if ptr else None,
            "unit_count": cnt,
            "ptr_still_matches_base": (ptr == base) if ptr else None,
        })
        H.resume(a.instance)
        shot = out_dir / f"screen_try{i}.png"
        try:
            H.screenshot(a.instance, shot)
            snap["screenshot"] = str(shot)
        except Exception as exc:                       # noqa: BLE001
            snap["screenshot"] = f"失敗: {exc}"
        events.append(snap)
        print(f"\n=== 第 {i} 次命中 ===")
        print(json.dumps(snap, ensure_ascii=False, indent=1)[:1200])
        time.sleep(a.gap)

    print(f"\n總計:成功 {good}/{a.tries},捕捉到 {len(events)} 次異常")
    if events:
        (out_dir / "events.json").write_text(
            json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")
        print("明細 ->", out_dir / "events.json")
    else:
        print("**這一輪沒有重現**——不代表模式 2 不存在,只代表這段時間沒發生。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
