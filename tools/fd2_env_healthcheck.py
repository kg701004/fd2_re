#!/usr/bin/env python3
"""fd2_env_healthcheck.py — 一次呼叫判定一個活體 instance 是否真的健康，
取代這次 session 反覆手動做的「list-sessions + capture-pane + xwininfo」
三步驟診斷序列。

背景
----
2026-09-06 這次 session 累積踩到三種完全不同、但表面症狀都很像的失敗：

1. **XIO fatal IO error**（Xvfb display 碰撞，`13-battle-menu-system.md`
   2026-09-05 已記載）：tmux pane 裡直接看得到
   `XIO: fatal IO error ... on X server`字樣。
2. **視窗從 X server window tree 消失，但 process 仍回應**：
   `xwininfo -root -tree` 顯示 `0 children`，但 tmux pane 同時顯示
   `(Running)` 或一個乾淨的 `I->` debugger prompt——這次 session 對三個
   完全獨立的新 instance(`spk6`/`spk7`/`spk8`)都重現過這個訊號，不是單一
   instance 的偶發問題。
3. **真正的 DOS-level 退出**（`C.16`本身，這個工具的原始調查對象）：
   螢幕會是乾淨的 `C:\\>` 提示字元，process 也真的結束。

過去的作法是看到 `status` 顯示 `LAUNCHER no` 或任何 `enter-debugger`/`key`
呼叫失敗，就直接假設「C.16 崩潰發生」並呼叫 `teardown`——**在 teardown 之前
從未真的讀過 tmux pane 內容**，導致上面三種完全不同的失敗被混為一談，
也讓最關鍵的診斷證據（pane 文字）在能讀之前就被 teardown 摧毀。

這支工具把「先讀證據，再決定要不要 teardown」變成一個不會漏掉的固定流程，
一次呼叫回傳明確分類，而不是要求呼叫端每次都記得手動做三個步驟。

用法
----
    python tools/fd2_env_healthcheck.py --instance spk9

回傳 verdict 是以下五種之一：
    healthy              — tmux 活著、視窗在 window tree 裡、pane 沒有錯誤字樣
    xio_display_collision — pane 裡看到 XIO fatal IO error 字樣
    window_vanished       — tmux 活著、pane 正常，但 window tree 是 0 children
    clean_dos_exit        — pane 看得到 `C:\\>` 提示字元
    no_tmux_session       — tmux session 根本不存在（真的已經 teardown 或從未啟動）

**這支工具本身不做 teardown**——診斷跟處置分開，呼叫端依 verdict 自己決定
下一步（例如 xio_display_collision/window_vanished 這兩種環境問題通常代表
需要換一個全新 instance，不代表 C.16 真的發生；clean_dos_exit 才是真正
需要記錄成 C.16 資料點的情況）。

多重驗證(2026-09-06)
----
`--selftest` 對 window-tree/pane 解析邏輯本身做正反向驗證，不需要真的啟動
DOSBox-X：①正確辨識一段真實截取到的`0 children`輸出為`window_vanished`
(前提是同一段pane沒有XIO字樣，也不是clean_dos_exit)；②正確辨識一段含
`XIO: fatal IO error`的pane為`xio_display_collision`，即使該次window tree
剛好也是空的(XIO判斷必須比window-vanished判斷有更高優先權，因為XIO本身
就會導致視窗消失，兩個訊號同時出現時不該誤判成window_vanished這個較不
明確的分類)；③正確辨識`C:\\>`為`clean_dos_exit`；④正常pane(`(Running)`
且window tree有至少1個child)判為`healthy`；⑤負對照——刻意餵一段完全空白
的pane內容，驗證這個工具誠實回報`unknown`而不是硬猜成上述任何一種。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

# 2026-09-08:本檔輸出含 cp950 編不出的符號(✓/✗/⚠)。在本機主控台(cp950)下,
# 第一個含該符號的 print 就會 UnicodeEncodeError 崩潰,而且崩得像「工具壞了」
# ——dump_exe_tables.py 與 safe_output.py 都真的因此整支不能用。全 repo 統一作法。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TMUX_SOCKET = "fd2harness"


def _tmux_session_name(instance: str) -> str:
    return f"harness-{instance}"


def tmux_session_exists(instance: str) -> bool:
    r = H.wsl_argv_run(["tmux", "-L", TMUX_SOCKET, "has-session", "-t", _tmux_session_name(instance)])
    return r.returncode == 0


def capture_pane(instance: str, lines: int = 40) -> str:
    r = H.wsl_argv_run(["tmux", "-L", TMUX_SOCKET, "capture-pane", "-t", _tmux_session_name(instance), "-p"])
    if r.returncode != 0:
        return ""
    text = r.stdout or ""
    return "\n".join(text.splitlines()[-lines:])


def _parse_child_count(out: str) -> int | None:
    """純函式，拆出來讓 --selftest 能直接餵字串測，不必每次都真的呼叫 xwininfo。"""
    for line in out.splitlines():
        line = line.strip()
        # xwininfo's own output is asymmetric: "0 children." (period, no list
        # follows) vs "N child:"/"N children:" (colon, a list of N windows
        # follows) for N>=1 -- 2026-09-06 caught live against a genuinely
        # healthy instance: the period-only check below missed every real
        # "1 child:" case and reported healthy instances as unknown.
        if line.endswith("children.") or line.endswith("child."):
            try:
                return int(line.split()[0])
            except (ValueError, IndexError):
                return None
        if line.endswith("children:") or line.endswith("child:"):
            try:
                return int(line.split()[0])
            except (ValueError, IndexError):
                return None
    return None


def window_child_count(instance: str, display_port: str = "199") -> int | None:
    """回傳該 display 的 window tree 子視窗數；查不到（wsl/xwininfo 本身失敗）回傳 None，
    跟「查到 0 個」明確分開，不能把兩者混為一談。"""
    r = H.wsl_argv_run(["bash", "-c", f"DISPLAY=127.0.0.1:{display_port} xwininfo -root -tree 2>&1"])
    out = r.stdout or ""
    if r.returncode != 0 and "children" not in out and "child:" not in out:
        return None
    return _parse_child_count(out)


def classify(pane_text: str, child_count: int | None) -> str:
    """純函式，不做任何 I/O——這是 --selftest 要驗證的核心邏輯，拆出來才能
    不啟動活體 instance 也能測。"""
    if not pane_text.strip() and child_count is None:
        return "unknown"
    if "XIO: fatal IO error" in pane_text or "XIO:  fatal IO error" in pane_text:
        return "xio_display_collision"
    if "C:\\>" in pane_text or "C:\\>" in pane_text.replace("\\\\", "\\"):
        return "clean_dos_exit"
    if child_count == 0:
        return "window_vanished"
    if child_count is not None and child_count > 0:
        return "healthy"
    return "unknown"


def healthcheck(instance: str) -> dict:
    if not tmux_session_exists(instance):
        return {"instance": instance, "verdict": "no_tmux_session", "pane": "", "child_count": None}
    pane = capture_pane(instance)
    children = window_child_count(instance)
    verdict = classify(pane, children)
    return {"instance": instance, "verdict": verdict, "pane": pane, "child_count": children}


SELFTEST_CASES = [
    ("window_vanished_no_xio", "DEBUG: Memory dump binary success.\n(Running)", 0, "window_vanished"),
    ("xio_wins_over_zero_children",
     'XIO:  fatal IO error 0 (Success) on X server "127.0.0.1:199"\n'
     "      after 98748 requests (98748 known processed) with 0 events remaining.",
     0, "xio_display_collision"),
    ("clean_dos_exit", "Starting MS-DOS...\n\nC:\\>", 1, "clean_dos_exit"),
    ("healthy_running", "DEBUG: Memory dump binary success.\n(Running)", 1, "healthy"),
    ("healthy_debugger_prompt", "DEBUG: Breakpoints deleted.\nI-> _", 1, "healthy"),
    ("blank_pane_is_unknown_not_guessed", "", None, "unknown"),
]


# 真實案例回歸鎖：2026-09-06對一個真正健康的活體instance(hctest)做端對端驗證時，
# `_parse_child_count`錯把這段真實xwininfo輸出判成None(誤判成healthy instance
# 是unknown)——根因是xwininfo在child數>=1時用冒號結尾("1 child:")，只有剛好0個
# child時才用句點("0 children.")，原本的parser只認句點。這是端對端測試抓到、
# 純合成self-test案例抓不到的真實bug，原始輸出逐字保留在這裡防止回歸。
REAL_XWININFO_ONE_CHILD = """xwininfo: Window id: 0x21f (the root window) (has no name)

  Root window id: 0x21f (the root window) (has no name)
  Parent window id: 0x0 (none)
     1 child:
     0x200009 "DOSBox-X 2026.07.02: FD2 - 5000 cycles/ms": ("dosbox-x" "dosbox-x")  640x417+192+184  +192+184
"""
REAL_XWININFO_ZERO_CHILDREN = """xwininfo: Window id: 0x21f (the root window) (has no name)

  Root window id: 0x21f (the root window) (has no name)
  Parent window id: 0x0 (none)
     0 children.
"""


def selftest() -> int:
    fails = []
    parse_cases = [
        ("real_xwininfo_one_child_colon_form", REAL_XWININFO_ONE_CHILD, 1),
        ("real_xwininfo_zero_children_period_form", REAL_XWININFO_ZERO_CHILDREN, 0),
    ]
    for name, raw, expected in parse_cases:
        got = _parse_child_count(raw)
        if got != expected:
            fails.append(f"  FAIL {name}: expected {expected!r}, got {got!r}")
        else:
            print(f"  ok   {name} -> {got}")
    for name, pane, children, expected in SELFTEST_CASES:
        got = classify(pane, children)
        if got != expected:
            fails.append(f"  FAIL {name}: expected {expected!r}, got {got!r}")
        else:
            print(f"  ok   {name} -> {got}")
    total = len(parse_cases) + len(SELFTEST_CASES)
    if fails:
        print("\n".join(fails), file=sys.stderr)
        print(f"\n{len(fails)}/{total} 個案例失敗", file=sys.stderr)
        return 1
    print(f"\n全部 {total} 個案例通過（純函式測試，未啟動任何活體 instance）。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if not a.instance:
        print("必須提供 --instance（或用 --selftest 做純邏輯自我測試）", file=sys.stderr)
        return 2

    result = healthcheck(a.instance)
    print(f"instance={result['instance']}")
    print(f"verdict={result['verdict']}")
    print(f"window_child_count={result['child_count']}")
    if result["verdict"] != "no_tmux_session":
        print("--- pane (最後 40 行) ---")
        print(result["pane"])
    if result["verdict"] in ("xio_display_collision", "window_vanished"):
        print("\n⚠ 這是已知的環境層問題，不是C.16——不建議把這次觀察記錄成C.16的新資料點。"
              "建議直接teardown這個instance、換一個全新的重試。", file=sys.stderr)
    elif result["verdict"] == "clean_dos_exit":
        print("\n⚠ 這才是真正值得記錄成C.16資料點的情況——乾淨的DOS退出，不是環境問題。",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
