"""續一百二十六:lc126_analyze.py(原 an126.py)的突變測試(原暫存 mut_an126.py,續一百三十四移進倉庫)。
把紀錄複本改錯一處,分析必須以 FAIL 結束、FAIL 清單含指定的檢查、沒有 Traceback。
由 ev_lut_circle_ramp_frame_time_ch22_post.py 以子行程執行,輸出原樣寫進證據。"""
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
SRC = ROOT / ".wsl_build" / "lc126_all"
KEYS = ("r1", "r2", "s11_frames", "s11_nof", "s12_frames")


def stop(d: dict, addr: str, k: int = 0) -> dict:
    return [s for s in d["stops"] if s.get("at") == addr][k]


def m_table(f): stop(f["r1"], "0x25e1e")["table_22"] = "0x244b6"
def m_chap(f): stop(f["r2"], "0x25e1e")["after"]["chap"] = 21
def m_ret(f): stop(f["r2"], "0x24754")["ret"] = "0x25e2f"
def m_inc(f): stop(f["r1"], "0x2495d")["g"]["chap"] = 22
def m_lut(f): f["r2"]["stops"].insert(-1, {"at": "0x2189a", "name": "入口"})
def m_crash(f): f["r2"]["stops"][-1]["pane"] = ["(Running)"]
def m_order(f):
    s = f["r2"]["stops"]
    i = next(k for k, x in enumerate(s) if x.get("at") == "0x2482e")
    j = next(k for k, x in enumerate(s) if x.get("at") == "0x24838")
    s[i], s[j] = s[j], s[i]
def m_args(f): stop(f["s11_frames"], "0x2189a")["args"] = [0, 15, 11]
def m_ret12(f): stop(f["s12_frames"], "0x2189a")["ret"] = "0x21888"
def m_radius(f): stop(f["s12_frames"], "0x2198e", 5)["radius"] += 1
def m_frames(f): f["s11_frames"]["stops"] = [s for s in f["s11_frames"]["stops"] if s.get("frame") != 9]
def m_nof(f): f["s11_nof"]["stops"].insert(1, {"at": "0x2198e", "frame": 0, "radius": 15, "tick": 0, "t": 0})
def m_ebx(f): stop(f["s11_nof"], "0x21998")["ebx"] = 9
def m_tick(f): stop(f["s11_nof"], "0x21998")["tick"] += 1


MUTANTS: list[tuple[str, Callable[[dict], None], str]] = [
    ("戰後表第 22 格改成第 21 格的值", m_table, "H r1 執行期戰後表第 22 格"),
    ("改寫後的章節索引 21", m_chap, "H r2 改寫前後的章節索引"),
    ("入口返回位址錯", m_ret, "H r2 處理器入口的返回位址"),
    ("dialog 14 之前沒有加 1", m_inc, "H r1 dialog 14 之前章節索引已加 1"),
    ("多出一次 lut 入口", m_lut, "H r2 dialog 14 之後模擬器結束、沒有進 lut"),
    ("最後沒有 E_Exit", m_crash, "H r2 dialog 14 之後模擬器結束、沒有進 lut"),
    ("兩個停點順序對調", m_order, "H r2 處理器內停點依位址遞增"),
    ("地震術每幀加 11", m_args, "T s11_frames 入口引數與返回位址"),
    ("裂地術返回位址換成地震術的", m_ret12, "T s12_frames 入口引數與返回位址"),
    ("第 5 幀半徑 +1", m_radius, "T s12_frames 十幀的序號與半徑"),
    ("少錄第 9 幀", m_frames, "T s11_frames 十幀的序號與半徑"),
    ("不停的那次多一個逐幀停點", m_nof, "T s11_nof 沒有逐幀停"),
    ("迴圈結束 ebx = 9", m_ebx, "T s11_nof 迴圈結束時 ebx = 10"),
    ("不停的那次多 1 個 tick", m_tick, "T 逐幀停與不停,入口到迴圈結束的 tick 相同"),
]


def main() -> int:
    caught = 0
    for name, fn, want in MUTANTS:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            for k in KEYS:
                shutil.copyfile(SRC / f"{k}.json", t / f"{k}.json")
            files = {k: json.loads((t / f"{k}.json").read_text(encoding="utf-8")) for k in KEYS}
            fn(files)
            for k, v in files.items():
                (t / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(HERE / "lc126_analyze.py"), str(t)], capture_output=True, text=True, encoding="utf-8")
            fail_line = next((ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")), "")
            tb = "Traceback (most recent" in (r.stdout + r.stderr)
            ok = r.returncode == 1 and want in fail_line and not tb
            caught += ok
            print(f"{'抓到' if ok else '漏掉'} {name}: rc={r.returncode} 指定檢查={want in fail_line} Traceback={tb} {fail_line[:160]}")
    print(f"突變 {len(MUTANTS)} 個,抓到 {caught},漏掉 {len(MUTANTS) - caught}")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
