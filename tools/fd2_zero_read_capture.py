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

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

UNIT_COUNT = 0x53BEB
ARRAY_PTR = 0x53A45


def wsl(cmd: str) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "bash", "-lc", cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def classify_read(err: str | None, data: bytes, expected_len: int) -> tuple[bool, str]:
    """(這次讀取算不算成功, 失敗種類)。**四種失敗必須分得開,不能都叫「讀失敗」。**

    這支工具存在的理由就是這個區別:模式 1(未停住就 dump)MEMDUMPBIN 根本不寫檔,
    模式 2(停住、回報成功、內容全 0)才是還沒解釋的那個。如果把「沒有檔案」和
    「檔案裡全是 0」都歸成同一種失敗,這兩個模式在資料裡就再也分不開,而分開它們
    正是待辦事項本身。短讀也要獨立成一類——長度不足的檔案不是「全 0」,把它算進去
    會讓模式 2 的計數虛高。

    回傳的種類:
        ""            成功
        "exception"   mem_dump 自己丟例外
        "no_file"     完全沒有檔案(0 bytes)
        "short_read"  有檔案但長度不足
        "all_zero"    長度正確但整段是 0  <- 這才是模式 2
    """
    if err is not None:
        return False, "exception"
    if not data:
        return False, "no_file"
    if len(data) != expected_len:
        return False, "short_read"
    if not any(data):
        return False, "all_zero"
    return True, ""


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
        ok, kind = classify_read(err, data, a.records * 0x50)
        if ok:
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
            "failure_kind": kind,          # exception / no_file / short_read / all_zero
            "all_zero": kind == "all_zero",
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


RECORD_LEN = 0x50


def selftest() -> int:
    """讀取分類那一層。實機 dump 需要活的 DOSBox,不在範圍內——但**四種失敗
    分不分得開**完全是離線可判的,而分開它們正是這支工具的待辦事項本身。"""
    fails = []
    n = 12 * RECORD_LEN

    print("(1) 四種失敗必須各自獨立,不能都叫「讀失敗」")
    cases = {
        "exception": classify_read("OSError: x", b"", n),
        "no_file": classify_read(None, b"", n),
        "short_read": classify_read(None, bytes(n - 1), n),
        "all_zero": classify_read(None, bytes(n), n),
    }
    wrong = {k: v for k, (ok, v) in cases.items() if ok or v != k}
    print(f"    {'PASS' if not wrong else 'FAIL'}: "
          + ("四種各自回傳自己的種類" if not wrong else str(wrong)))
    if wrong:
        fails.append(f"失敗種類分不開:{wrong}")

    print("\n(2) 本工具存在的理由:「沒寫檔」與「寫了全 0 的檔」必須分得開")
    # 模式 1 不寫檔、模式 2 寫出全 0 的檔。混成一類,兩個模式在資料裡就再也
    # 分不開,而分開它們正是待辦事項。
    _, no_file = classify_read(None, b"", n)
    _, zeros = classify_read(None, bytes(n), n)
    ok2 = no_file == "no_file" and zeros == "all_zero" and no_file != zeros
    print(f"    {'PASS' if ok2 else 'FAIL'}: 0 bytes -> {no_file!r}、"
          f"{n} 個 0 -> {zeros!r}")
    if not ok2:
        fails.append(f"兩個模式被混為一類:{no_file} / {zeros}")

    print("\n(3) 短讀不得被算成全 0(否則模式 2 的計數會虛高)")
    _, short_zero = classify_read(None, bytes(n - 1), n)   # 內容也全是 0,但長度不足
    ok3 = short_zero == "short_read"
    print(f"    {'PASS' if ok3 else 'FAIL'}: 長度 {n-1} 的全 0 檔 -> {short_zero!r}"
          f"(應 short_read,不是 all_zero)")
    if not ok3:
        fails.append(f"短讀被算成全 0:{short_zero}")

    print("\n(4) 正向:長度正確且有內容才算成功")
    good = bytearray(n)
    good[3] = 0x01                       # 只要有一個非零位元組就不是全 0
    ok_good, kind_good = classify_read(None, bytes(good), n)
    long_data = classify_read(None, bytes(n + 1), n)       # 過長也不算成功
    ok4 = ok_good and kind_good == "" and long_data == (False, "short_read")
    print(f"    {'PASS' if ok4 else 'FAIL'}: 有內容且長度正確 -> 成功、"
          f"長度過長 -> {long_data[1]!r}")
    if not ok4:
        fails.append(f"成功判定不正確:{ok_good}/{kind_good}/{long_data}")

    print("\n(5) 非平凡性 + 邊界")
    kinds = {classify_read(e, d, n)[1] for e, d in
             (("E", b""), (None, b""), (None, bytes(n - 1)), (None, bytes(n)),
              (None, bytes(n - 1) + b"\x01"))}
    ok5 = len(kinds) == 5 and classify_read(None, b"\x01", 1) == (True, "")
    print(f"    {'PASS' if ok5 else 'FAIL'}: 五種輸入得出 {len(kinds)} 種結果 "
          f"{sorted(kinds)}、長度 1 的非零資料算成功")
    if not ok5:
        fails.append(f"分類不隨輸入變化:{sorted(kinds)}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(四種失敗互相獨立 + 兩個模式分得開 + 短讀不混入 "
          "+ 成功判定 + 非平凡性)。實機 dump 未涵蓋,見 docstring。")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
