"""續一百二十六證據:evidence/lut_circle_ramp_frame_time_ch22_post_20261015.json。

lc126 / lc126b / lc126c 五份實機紀錄(章節索引 22 的戰後處理器、lut_circle_ramp_at_unit 每幀的模擬時間)逐項檢查。
原本由暫存的 mk_evidence126.py + an126.py + mut_an126.py 產生(續一百二十六);續一百三十四移進倉庫:
分析是 lc126_analyze.py、突變是 lc126_mut.py(以子行程重跑,輸出原樣寫進證據),原始紀錄在 .wsl_build/lc126_all/。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
import lc126_analyze as an126  # noqa: E402

D = ROOT / ".wsl_build" / "lc126_all"
OUT = out_path("lut_circle_ramp_frame_time_ch22_post_20261015.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
WHAT = {
    "r1": "第 1 章戰場(章節位元組 1)。0x1d8aa 停下時把 [0x53ecc] 寫成 2、0x25e1e 停下時把 [0x53c03] 寫成 22,讓 0x25e23 呼叫戰後表第 22 格;"
          "處理器裡只在入口、dialog 14 之前與 delay / lut / flicker 前後下斷點。dialog 14 之前那一站之後模擬器結束。",
    "r2": "同 r1(新 instance),另在處理器前半每個呼叫點下斷點、每按一次 Return 截圖,定位結束的位置。",
    "s11_frames": "第 1 章戰場,索爾施放地震術(法術 11);盜賊 #11 搬到 (19,14)、HP 9999。入口、每幀、迴圈結束、redraw(0) 之後各讀 BIOS tick。",
    "s11_nof": "同一場再施放一次地震術(索爾 +5 清 0),只停入口、迴圈結束與 redraw(0) 之後。",
    "s12_frames": "同一場施放裂地術(法術 12),逐幀停。",
}

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = an126.main()
assert _rc == 0, _buf.getvalue()[-2000:]
res = list(an126.results)
real = [r for r in res if not r["control"]]
ctl = [r for r in res if r["control"]]
mut = subprocess.run([sys.executable, str(GEN_DIR / "lc126_mut.py")], capture_output=True, text=True, encoding="utf-8")
assert mut.returncode == 0 and "漏掉 0" in mut.stdout and "Traceback (most recent" not in mut.stdout + mut.stderr, mut.stdout + mut.stderr
out: dict = {
    "date": "2026-10-15", "exe_md5": EXE_MD5,
    "method": "DOSBox-X 除錯器斷點(core=normal、cycles=5000,tools/dosbox_harness.sh);只改模擬器記憶體裡的資料,程式碼不動。"
              "計時讀線性 0x46c 的 BIOS tick(1 tick = 65536 / 1193182 秒 ≈ 54.93 ms);停在除錯器時模擬器不跑,所以 tick 是模擬時間。"
              "執行中隔 10.71 秒(含兩次停住)讀兩次,tick 增加 112(lc126,設定前的檢查)。",
    "static": {
        "post_table_0x51de9_22": hex(an126.HANDLER),
        "ret_after_0x25e23": hex(an126.HANDLER_RET),
        "ch22_post_lut_pushes": {hex(k): v for k, v in an126.LUT_CALLS_22.items()},
        "spell_lut_pushes": {str(k): {"call": hex(v[0]), "radius_start_step": v[1]} for k, v in an126.SPELL.items()},
        "table_ranges": "0x51d01 + 28*4 = 0x51d71(戰前章節表),0x51d71 + 30*4 = 0x51de9(戰後章節表),0x51de9 + 30*4 = 0x51e61",
    },
    "runs": [],
    "timing": an126.timing,
    "analysis": {"script": "an126.py(暫存)", "checks": len(real), "pass": sum(bool(r["ok"]) for r in real),
                 "controls": len(ctl), "controls_fail_as_expected": sum(r["ok"] is False for r in ctl),
                 "controls_not_applicable": sum(r["ok"] is None for r in ctl), "items": res},
    "mutation": {"script": "mut_an126.py(暫存)", "stdout": mut.stdout.strip().splitlines()},
}
for tag in ("r1", "r2", "s11_frames", "s11_nof", "s12_frames"):
    d = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    st = [{k: v for k, v in s.items() if k != "u0"} for s in d["stops"]]
    out["runs"].append({"tag": tag, "what": WHAT[tag], "stops": st})

# 結論釘住:全部檢查符合、沒有對照判成符合、突變全部抓到
a = out["analysis"]
assert a["pass"] == a["checks"] and a["controls_fail_as_expected"] + a["controls_not_applicable"] == a["controls"], a
assert (a["checks"], a["controls"], a["controls_not_applicable"]) == (21, 1, 0), a
assert out["mutation"]["stdout"][-1] == "突變 14 個,抓到 14,漏掉 0", out["mutation"]["stdout"][-1]
# 計時:地震術 7 tick(逐幀停與不停相同)、裂地術 10 tick;每步 tick 加總 = 入口到迴圈結束
tm = {t["tag"]: t for t in out["timing"]}
assert {k: t["ticks_entry_to_loop_end"] for k, t in tm.items()} == {"s11_frames": 7, "s11_nof": 7, "s12_frames": 10}, tm
assert all(sum(t["tick_steps"]) == t["ticks_entry_to_loop_end"] for t in tm.values() if t["tick_steps"]), tm
# 靜態:戰後表第 22 格與三次 lut 的引數(第 3 次與裂地術相同)
assert (an126.HANDLER, an126.HANDLER_RET) == (0x24754, 0x25E2A)
assert list(an126.LUT_CALLS_22.values()) == [[1, 15, 10], [1, 15, 10], [1, 30, 16]] and an126.SPELL[12][1] == [30, 16]


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
