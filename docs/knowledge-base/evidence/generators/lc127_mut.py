"""續一百二十七:lc127_analyze.py(原 an127.py)的突變測試(原暫存 mut_an127.py,續一百三十四移進倉庫)。
把紀錄複本改錯一處,分析必須以 FAIL 結束、FAIL 行含指定的檢查、沒有 Traceback。
由 ev_lut_ch22_post_cycles2500_chapter_tables.py 以子行程執行,輸出原樣寫進證據。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _evpaths import ROOT  # noqa: E402
RAW = ROOT / ".wsl_build"
R1 = RAW / "lc127b_live" / "r1.json"
CTL = RAW / "lc126_all" / "r1.json"
C25 = {k: RAW / "lc127d_live" / f"{k}.json" for k in ("c2500_nof", "c2500_frames")}
C50 = {k: RAW / "lc126_all" / f"{k}.json" for k in ("s11_nof", "s11_frames")}


def stop(d: dict, addr: str, k: int = 0) -> dict:
    return [s for s in d["stops"] if s.get("at") == addr][k]


def m_chap(f): stop(f["r1"], "0x25e1e")["before"]["chap"] = 1
def m_written(f): stop(f["r1"], "0x25e1e")["after"] = {"chap": 22}
def m_table(f): stop(f["r1"], "0x25e1e")["table_22"] = "0x244b6"
def m_ret(f): stop(f["r1"], "0x24754")["ret"] = "0x25e2f"
def m_inc(f): stop(f["r1"], "0x2495d")["g"]["chap"] = 22
def m_args3(f): stop(f["r1"], "0x2189a", 2)["args"] = [1, 30, 15]
def m_ret2(f): stop(f["r1"], "0x2189a", 1)["ret"] = "0x2497d"
def m_drop3(f): f["r1"]["stops"].remove(stop(f["r1"], "0x2189a", 2))
def m_radius(f): stop(f["r1"], "0x2198e", 4)["radius"] += 1
def m_frames(f): f["r1"]["stops"] = [s for s in f["r1"]["stops"] if s.get("frame") != 9]
def m_order(f):
    s = f["r1"]["stops"]
    i = next(k for k, x in enumerate(s) if x.get("at") == "0x249c4")
    j = next(k for k, x in enumerate(s) if x.get("at") == "0x249cc")
    s[i], s[j] = s[j], s[i]
def m_exit(f): f["r1"]["stops"].append({"at": "exit", "pane": ["E_Exit: Illegal descriptor type 0 for int 8"]})
def m_tick(f): stop(f["r1"], "0x249c9")["tick"] += 1
def m_c25_args(f): stop(f["c2500_nof"], "0x2189a")["args"] = [0, 15, 11]
def m_c25_radius(f): stop(f["c2500_frames"], "0x2198e", 3)["radius"] += 1
def m_c25_nof(f): f["c2500_nof"]["stops"].insert(1, {"at": "0x2198e", "frame": 0, "radius": 15, "tick": 0, "t": 0})
def m_c25_same(f): stop(f["c2500_frames"], "0x21998")["tick"] += 1
def m_c25_x1(f):  # 兩份 2500 都改成和 5000 一樣 7 tick:比例檢查要失敗,對調檢查(回掃)要變成符合
    for k in ("c2500_nof", "c2500_frames"):
        stop(f[k], "0x21998")["tick"] = stop(f[k], "0x2189a")["tick"] + 7
def m_c50(f): stop(f["s11_nof"], "0x21998")["tick"] += 4
def m_ctl(f): f["ctl"] = json.loads(json.dumps(f["r1"]))   # 對照換成會通過的紀錄:必須被抓到「對照沒有判為不符合」


MUTANTS: list[tuple[str, Callable[[dict], None], str]] = [
    ("戰後表之前章節索引 1", m_chap, "L r1 戰後表之前章節索引本來就是 22(沒有寫入)"),
    ("紀錄裡有寫入", m_written, "L r1 戰後表之前章節索引本來就是 22(沒有寫入)"),
    ("戰後表第 22 格換成第 21 格", m_table, "L r1 執行期戰後表第 22 格"),
    ("入口返回位址錯", m_ret, "L r1 處理器入口的返回位址"),
    ("dialog 14 之前沒有加 1", m_inc, "L r1 dialog 14 之前章節索引已加 1"),
    ("#3 每幀加 15", m_args3, "L r1 三次 lut 的返回位址與引數"),
    ("#2 返回位址換成 #1 的", m_ret2, "L r1 三次 lut 的返回位址與引數"),
    ("少錄 #3 入口", m_drop3, "L r1 三次 lut 的返回位址與引數"),
    ("第 4 幀半徑 +1", m_radius, "L r1 lut #1 十幀"),
    ("少錄第 9 幀", m_frames, "L r1 lut #1 十幀"),
    ("兩個停點順序對調", m_order, "L r1 處理器內停點依位址遞增"),
    ("最後模擬器結束", m_exit, "L r1 跑到 0x25e2a 返回、模擬器沒有結束"),
    ("#2 多 1 個 tick", m_tick, "L r1 #1(逐幀停)與 #2(不停)tick 數相同"),
    ("2500 不停的那次每幀加 11", m_c25_args, "T c2500_nof 入口引數與返回位址"),
    ("2500 第 3 幀半徑 +1", m_c25_radius, "T c2500_frames 十幀的序號與半徑"),
    ("2500 不停的那次多一個逐幀停點", m_c25_nof, "T c2500_nof 沒有逐幀停"),
    ("2500 逐幀停那次多 1 tick", m_c25_same, "T cycles 2500 逐幀停與不停的 tick 相同"),
    ("2500 兩份都只有 7 tick", m_c25_x1, "T cycles 減半,tick 約變兩倍(受 CPU 限制)"),
    ("5000 不停的那次多 4 tick", m_c50, "T cycles 減半,tick 約變兩倍(受 CPU 限制)"),
    ("對照換成會通過的紀錄", m_ctl, "C 續一百二十六借道紀錄(第 1 章資料)套同一檢查(對照沒有判為不符合)"),
]


def main() -> int:
    caught = 0
    for name, fn, want in MUTANTS:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            files = {"r1": json.loads(R1.read_text(encoding="utf-8")), "ctl": json.loads(CTL.read_text(encoding="utf-8"))}
            files.update({k: json.loads(v.read_text(encoding="utf-8")) for k, v in (C25 | C50).items()})
            fn(files)
            for k, v in files.items():
                (t / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(HERE / "lc127_analyze.py"), str(t / "r1.json"), str(t / "ctl.json"), str(t), str(t)],
                               capture_output=True, text=True, encoding="utf-8")
            fail_line = next((ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")), "")
            tb = "Traceback (most recent" in (r.stdout + r.stderr)
            ok = r.returncode == 1 and want in fail_line and not tb
            caught += ok
            print(f"{'抓到' if ok else '漏掉'} {name}: rc={r.returncode} 指定檢查={want in fail_line} Traceback={tb} {fail_line[:160]}")
    print(f"突變 {len(MUTANTS)} 個,抓到 {caught},漏掉 {len(MUTANTS) - caught}")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
