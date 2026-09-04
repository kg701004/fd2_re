#!/usr/bin/env python3
"""fd2_trial_runner.py — 每個條件跑 N 次全新實例,比較**發生率**,不比較單次結果。

為什麼需要這支工具
------------------
2026-09-04 的教訓(交接檔 C.12):FD2.EXE 退回 DOS 這件事是**機率性**的。
在發現這一點之前,整條調查都用單次執行在下因果結論:

* `--attack --mv 4` 死了 6 次 → 我當成「必死」
* `--mv 0` 活了 1 次 → 我當成「移動被指認」
* 後來 `--dest computed`(同樣的必死配置)**也活了** → 前兩個推論同時失效

**單次結果無法分辨「條件的效果」與「run-to-run 變異」。** 要比較的是發生率。

而且每次重複必須從**相同起始狀態**開始。存檔狀態快照做不到(C.13:mapper 對合成按鍵
不可達,組合鍵與單鍵都試過),所以改用**每次試驗開全新實例**——起點由建構方式保證一致,
比在同一實例上反覆跑更乾淨(C.12 的 par2 就是因為戰場已被前一次執行改過而不算乾淨重複)。

牆鐘靠並行壓下來:10 次試驗串行約 110 分鐘,4 個實例並行約 30 分鐘。

它刻意不做的事
--------------
**不替你宣告哪個條件比較危險。** 小樣本下 3/5 與 1/5 看起來有差,實際上分不出來;
本工具只回報次數與一個保守的判讀門檻,把「這樣夠不夠下結論」留給讀的人。
今天已經有一整段調查毀在「看起來有差就當成有差」。

編排上的三個坑(今天各踩過一次,已寫進實作)
--------------------------------------------
1. `launch <name> <keepalive>` **會阻塞**整個 keepalive 秒數——它就是持有者。
   不能用 `&&` 串後續步驟,要背景啟動後**輪詢 tmux session 出現**。
2. 殺掉 launch 行程會連帶拆掉實例。
3. 存活判定一律用 `H.game_alive()`(多幀畫面),**絕不用記憶體**:退回 DOS 後那些位址
   仍留著舊值,陣列有時讀成全 0、有時讀出成功但是垃圾的 12 筆(C.9)。

用法
----
    python tools/fd2_trial_runner.py --trials 5 --workers 3 \\
        --cond "mv4:--turns 3 --mv 4 --attack" \\
        --cond "mv0:--turns 3 --mv 0 --attack"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd2_dosbox_live_helper as H  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
HELPER_SH = "./tools/fd2_dosbox_live_helper.sh"


def wsl(cmd: str, timeout: int = 120) -> str:
    r = subprocess.run(["wsl", "-d", "Ubuntu", "bash", "-lc", cmd],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def session_exists(inst: str) -> bool:
    return f"harness-{inst}:" in wsl("tmux -L fd2harness ls")


def launch(inst: str, keepalive: int = 3600) -> subprocess.Popen:
    """背景啟動,並等 tmux session 真的出現。

    `launch` 是 keepalive 持有者,**不會返回**——所以不能等它結束,要等 session 出現。
    """
    p = subprocess.Popen(["wsl", "-d", "Ubuntu", "bash", "-lc",
                          f"cd /mnt/c/Users/kg701/Desktop/GAME/fd2_re && "
                          f"{HELPER_SH} launch {inst} {keepalive}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        if session_exists(inst):
            return p
        time.sleep(2)
    raise RuntimeError(f"{inst}: tmux session 未在時限內出現")


def teardown(inst: str) -> None:
    wsl(f"cd /mnt/c/Users/kg701/Desktop/GAME/fd2_re && {HELPER_SH} teardown {inst}")


def drive(inst: str, log: Path) -> bool:
    r = subprocess.run(["bash", "tools/fd2_drive_to_playable.sh", inst, "boot"],
                       cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    log.write_text(r.stdout or "", encoding="utf-8")
    return "READY" in (r.stdout or "")


def run_condition(inst: str, args: list[str], log: Path) -> None:
    subprocess.run([sys.executable, "-u", "tools/fd2_stat_override.py",
                    "--instance", inst, "--ours-hp", "0", "--ours-mp", "0",
                    "--ours-ap", "0", "--ours-mv", "0", "--enemy-hp", "1"],
                   cwd=REPO, capture_output=True, text=True, timeout=900)
    r = subprocess.run([sys.executable, "-u", "tools/fd2_battle_autoplay.py",
                        "--instance", inst] + args,
                       cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    log.write_text(r.stdout or "", encoding="utf-8")


def one_trial(cond_name: str, cond_args: list[str], out_dir: Path,
              results: list, lock: threading.Lock) -> None:
    inst = f"t{uuid.uuid4().hex[:6]}"
    rec = {"condition": cond_name, "instance": inst}
    try:
        launch(inst)
        if not drive(inst, out_dir / f"{inst}_drive.log"):
            rec["outcome"] = "drive_failed"       # 不計入分母:它沒測到條件
        else:
            alive0, _ = H.game_alive(inst)
            if not alive0:
                rec["outcome"] = "dead_before_condition"
            else:
                run_condition(inst, cond_args, out_dir / f"{inst}_run.log")
                alive, meas = H.game_alive(inst)
                rec["outcome"] = "survived" if alive else "exited"
                rec["frames"] = [f["distinct_colors"] for f in meas["frames"]]
    except Exception as exc:                       # noqa: BLE001
        rec["outcome"] = f"error: {exc.__class__.__name__}: {exc}"[:200]
    finally:
        try:
            teardown(inst)
        except Exception:                          # noqa: BLE001
            pass
    with lock:
        results.append(rec)
        print(f"  [{cond_name}] {inst}: {rec['outcome']}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cond", action="append", required=True,
                    metavar="NAME:ARGS", help="條件,可重複。例:'mv4:--turns 3 --mv 4 --attack'")
    ap.add_argument("--trials", type=int, default=5, help="每個條件跑幾次")
    ap.add_argument("--workers", type=int, default=3, help="同時幾個實例")
    ap.add_argument("--out", default=None, help="輸出目錄")
    a = ap.parse_args()

    conds = []
    for c in a.cond:
        name, _, rest = c.partition(":")
        if not rest:
            print(f"條件格式應為 NAME:ARGS,收到 {c!r}", file=sys.stderr)
            return 2
        conds.append((name, rest.split()))

    out_dir = Path(a.out) if a.out else (H.DEFAULT_SHOT_DIR / "trials" /
                                         time.strftime("%Y%m%d_%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"條件 {len(conds)} 個 × {a.trials} 次,{a.workers} 個實例並行 -> {out_dir}")

    jobs = [(n, args) for n, args in conds for _ in range(a.trials)]
    results: list = []
    lock = threading.Lock()
    sem = threading.Semaphore(a.workers)

    def worker(n, args):
        with sem:
            one_trial(n, args, out_dir, results, lock)

    threads = [threading.Thread(target=worker, args=j) for j in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("\n===== 結果 =====")
    summary = {}
    for name, _ in conds:
        rs = [r for r in results if r["condition"] == name]
        counted = [r for r in rs if r["outcome"] in ("survived", "exited")]
        died = sum(1 for r in counted if r["outcome"] == "exited")
        excluded = len(rs) - len(counted)
        summary[name] = {"died": died, "counted": len(counted), "excluded": excluded}
        print(f"  {name}: 退回 DOS {died}/{len(counted)}"
              + (f"(另有 {excluded} 次未計入:驅動失敗或起點就已離開)" if excluded else ""))

    # 刻意不做顯著性宣告,只給一個保守的可讀性提示。
    print("\n判讀提醒:**本工具不宣告哪個條件比較危險。**")
    print("  小樣本下 3/5 與 1/5 看起來有差,實際上分不出來——這正是 C.12 那次誤判的形狀。")
    print("  要主張差異,至少該讓兩個條件的區間不重疊;現在的樣本數通常做不到。")
    (out_dir / "results.json").write_text(
        json.dumps({"summary": summary, "trials": results}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n明細 -> {out_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
