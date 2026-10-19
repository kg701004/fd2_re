"""續一百二十五:lc125_analyze.py(原 an125.py)的突變測試(原暫存 mut_an125.py,續一百三十四移進倉庫)。
把紀錄複本改錯一處,分析必須以 FAIL 結束、FAIL 清單含指定的檢查、沒有 Traceback。
由 ev_item79_aim_exp_reward_lines.py 以子行程執行,輸出原樣寫進證據。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _evpaths import ROOT  # noqa: E402
SRC = ROOT / ".wsl_build" / "lc125_live"


def stop(d: dict, addr: str, k: int = 0) -> dict:
    return [s for s in d["stops"] if s["at"] == addr][k]


def m_score(f): stop(f["b1"], "0x157fd")["score"] += 1
def m_cells(f): stop(f["b1"], "0x1576e")["cells"].insert(2, [19, 14])
def m_targets(f): stop(f["b1"], "0x157fd")["targets"] = [0]
def m_best(f): stop(f["a1"], "0x1586a")["best"].update(x=20, y=14)
def m_exp_a(f): stop(f["a1"], "0x1c8e2")["eax_add"] += 1
def m_exp_b(f): stop(f["b1"], "0x1c8e2")["eax_add"] = 40
def m_loop(f): stop(f["a1"], "0x20fe5")["exp"] = 7
def m_payload(f): stop(f["a1"], "0x1ac2b")["payload"] = 12
def m_match(f): stop(f["a1b"], "0x1ac2b")["file_match"]["FDTXT_002"] = False
def m_enemy(f): next(u for u in stop(f["b1"], "0x1567e")["units"] if u["i"] == 15)["camp"] = 1
def m_table(f): stop(f["b1"], "0x15055")["table"]["FDTXT_002"]["diff_bytes"] = 5
def m_rows(f): stop(f["a1"], "0x21072")["rows"] = "030b00001000" + "1d0070010100"


MUTANTS: list[tuple[str, Callable[[dict], None], str]] = [
    ("分數 +1", m_score, "S b1#0 分數"),
    ("施放點多出中心", m_cells, "S b1#0 施放點"),
    ("目標少一個", m_targets, "S b1#0 有目標的施放點與目標"),
    ("同分時換成後者", m_best, "S a1#0 同分不換"),
    ("陣亡目標的經驗值 +1", m_exp_a, "E a1 #5 累加"),
    ("存活目標不縮放", m_exp_b, "E b1 #3 累加"),
    ("迴圈結束的經驗值 +1", m_loop, "E a1 迴圈結束的 [0x53ec8]"),
    ("payload 改 12", m_payload, "K a1 種類 3 停點的 payload"),
    ("第 16 條字碼不符", m_match, "K a1 第 16 條 = FDTXT_002 第 16 條"),
    ("直線上的敵人改成友軍", m_enemy, "S b1#0 有目標的施放點與目標"),
    ("文字表差 5 bytes", m_table, "K b1 入口的文字表"),
    ("第 2 列種類改 0", m_rows, "K a1 種類 3 停點的 payload"),
]


def main() -> int:
    caught = 0
    for name, fn, want in MUTANTS:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            for p in SRC.glob("*.json"):
                shutil.copyfile(p, t / p.name)
            files = {k: json.loads((t / f"{k}.json").read_text(encoding="utf-8")) for k in ("a1", "a1b", "b1")}
            fn(files)
            for k, v in files.items():
                (t / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(HERE / "lc125_analyze.py"), str(t)], capture_output=True, text=True, encoding="utf-8")
            fail_line = next((ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")), "")
            ok = r.returncode == 1 and want in fail_line and "Traceback" not in (r.stdout + r.stderr)
            caught += ok
            print(f"{'抓到' if ok else '漏掉'} {name}: rc={r.returncode} 指定檢查={want in fail_line} "
                  f"Traceback={'Traceback' in (r.stdout + r.stderr)} {fail_line[:160]}")
    print(f"突變 {len(MUTANTS)} 個,抓到 {caught},漏掉 {len(MUTANTS) - caught}")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
