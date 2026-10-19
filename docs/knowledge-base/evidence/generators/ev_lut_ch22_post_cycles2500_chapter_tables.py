"""續一百二十七證據:evidence/lut_ch22_post_cycles2500_chapter_tables_20261015.json。

正式第 22 章戰後處理器(lc127b)、cycles 2500 計時(lc127d)與 0x51d01 起 88 格三張表的靜態對照。原本由暫存的
mk_evidence127.py + an127.py + mut_an127.py + tbl127.py 產生(續一百二十七);續一百三十四移進倉庫:
分析是 lc127_analyze.py、突變是 lc127_mut.py(以子行程重跑,輸出原樣寫進證據),88 格對照在這裡重算
(名稱取續一百二十七提交前那一版 function_names.json,以 git blob 鎖定)。原始紀錄在 .wsl_build/lc127b_live/、
.wsl_build/lc127d_live/(含 cycles 包裝腳本 dosbox-x-c2500)與 .wsl_build/lc126_all/。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import struct
import subprocess
import sys

from _evpaths import GAME, GEN_DIR, ROOT, git_blob, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
import lc127_analyze as an127  # noqa: E402

RAW = ROOT / ".wsl_build"
OUT = out_path("lut_ch22_post_cycles2500_chapter_tables_20261015.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
# 續一百二十七提交(450e8545)之前的 docs/data/function_names.json
NAMES_BLOB = "cfcd2455732a624b1c57d44e3cf84141775bc617"
RUNS = {
    "ch22_r1": (RAW / "lc127b_live" / "r1.json",
                "正式第 22 章戰場:fd2_chapter_sweep.prepare_chapter_save(chapter_n=23,roster_cap=16)產生的完整隊伍存檔,章節位元組 22;"
                "出戰選擇後經 attempt_camp_exit 進戰場。0x1d8aa 停下時把 [0x53ecc] 寫成 2,我方用系統環 END 結束回合;"
                "0x25e1e 只記錄 [0x53c03](= 22,沒有寫入)。處理器裡在呼叫點、delay / lut / flicker 前後下斷點,lut #1 逐幀停。"),
    "c2500_nof": (RAW / "lc127d_live" / "c2500_nof.json",
                  "第 1 章戰場,cycles 2500(dosbox-x-c2500 包裝只把 harness 的 cycles=5000 換成 2500);索爾施放地震術,"
                  "盜賊 #11 搬到 (19,14)、HP 9999;只停入口、迴圈結束、redraw(0) 之後。"),
    "c2500_frames": (RAW / "lc127d_live" / "c2500_frames.json", "同一場再施放一次地震術,逐幀停。"),
}


def entry(base: int, i: int) -> int:
    """表格第 i 格(檔案裡是 obj1 內的位移,載入時加 obj1 基底 0x10000)。"""
    return struct.unpack("<I", an127.A.sbytes(base + 4 * i, 4))[0] + 0x10000


def table_rows() -> list[dict]:
    """0x51d01 起 88 格:指令表 28 格、戰前章節表 30 格、戰後章節表 30 格(原 tbl127.py)。"""
    fn = json.loads(git_blob(NAMES_BLOB, "docs/data/function_names.json"))
    by = {int(x["addr"], 16): x for x in fn["names"]}
    rows = []
    for i in range(88):
        a = entry(0x51D01, i)
        tbl, ch = ("cmd", i) if i < 28 else (("pre", i - 28) if i < 58 else ("post", i - 58))
        n = by.get(a)
        rows.append({"index": i, "slot": hex(0x51D01 + 4 * i), "table": tbl, "chapter_or_cmd": ch, "addr": hex(a),
                     "name": n["name"] if n else None, "conf": n["confidence"] if n else None})
    # 用各表自己的基底讀同一格必須一致(三張表首尾相接)
    for r in rows:
        if r["table"] == "pre":
            assert entry(0x51D71, r["chapter_or_cmd"]) == int(r["addr"], 16)
        if r["table"] == "post":
            assert entry(0x51DE9, r["chapter_or_cmd"]) == int(r["addr"], 16)
    return rows


_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = an127.main()
assert _rc == 0 and "PASS" in _buf.getvalue(), _buf.getvalue()[-2000:]
res = list(an127.results)
real = [r for r in res if not r["control"]]
ctl = [r for r in res if r["control"]]
mut = subprocess.run([sys.executable, str(GEN_DIR / "lc127_mut.py")], capture_output=True, text=True, encoding="utf-8")
assert mut.returncode == 0 and "漏掉 0" in mut.stdout and "Traceback (most recent" not in mut.stdout + mut.stderr, mut.stdout + mut.stderr
rows = table_rows()
# 表結束:第 89 格(0x51e61)不在程式段;戰前 / 戰後 60 格全部登記為 command_handler_*
nxt = entry(0x51D01, 88)
assert not (0x10000 <= nxt < 0x50000) and nxt == 0x13140101, hex(nxt)
assert sum(1 for r in rows if r["table"] != "cmd" and (r["name"] or "").startswith("command_handler_")) == 60
out: dict = {
    "date": "2026-10-15", "exe_md5": EXE_MD5,
    "method": "DOSBox-X 除錯器斷點(core=normal;harness cycles=5000,cycles 2500 那兩份經包裝腳本只換 cycles);"
              "只改模擬器記憶體裡的資料,程式碼不動。"
              "計時讀線性 0x46c 的 BIOS tick(約 54.93 ms);停在除錯器時模擬器不跑。",
    "abandoned_first_attempt": {
        "instance": "lc127",
        "note": "先用 cl.py battle 把預設存檔的章節位元組改成 22:出戰選擇格只有 12 名候選、目標 15,選不滿。"
                "在 0x2b0e3 cmp eax, ebp 把 EBP 改成已選人數(兩次:11、12),遊戲兩次都顯示「本章希爾法必須出場」退回選擇畫面"
                "(這份存檔沒有希爾法)。放棄這個 instance,沒有任何紀錄出自它。"},
    "ch22_roster": "prepare_chapter_save 的完整隊伍 16 人(roster_cap=16),選擇格 15 名全選,遊戲自己的 cmp eax, ebp 成立後進戰場,沒有改暫存器。",
    "cycles_wrapper": (RAW / "lc127d_live" / "dosbox-x-c2500").read_text(encoding="utf-8"),
    "static_tables": {"rows": rows, "next_after_0x51e61": "0x13140101(不在程式段,表結束)",
                      "pre_table_calls": ["0x25e3a", "0x25f10", "0x260f5"], "post_table_call": "0x25e23"},
    "runs": [],
    "analysis": {"script": "an127.py(暫存)", "checks": len(real), "pass": sum(bool(r["ok"]) for r in real),
                 "controls": len(ctl), "controls_fail_as_expected": sum(r["ok"] is False for r in ctl), "items": res},
    "mutation": {"script": "mut_an127.py(暫存)", "stdout": mut.stdout.strip().splitlines()},
}
for tag, (p, what) in RUNS.items():
    d = json.loads(p.read_text(encoding="utf-8"))
    st = [{k: v for k, v in s.items() if k != "u0"} for s in d["stops"]]
    out["runs"].append({"tag": tag, "what": what, "stops": st})

# 結論釘住:全部檢查符合、對照全部判為不符合、突變全部抓到;包裝腳本只換 cycles
a = out["analysis"]
assert a["pass"] == a["checks"] and a["controls_fail_as_expected"] == a["controls"], a
assert (a["checks"], a["controls"]) == (21, 2), a
assert out["mutation"]["stdout"][-1] == "突變 20 個,抓到 20,漏掉 0", out["mutation"]["stdout"][-1]
assert 'a="config -set cycles=2500"' in out["cycles_wrapper"] and out["cycles_wrapper"].count("cycles=") == 3


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
