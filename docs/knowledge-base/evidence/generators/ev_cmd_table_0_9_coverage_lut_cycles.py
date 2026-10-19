"""續一百二十九證據:evidence/cmd_table_0_9_coverage_lut_cycles_20261016.json。

指令表 0x51d01 第 0..9 格的實機覆蓋(靜態 + 既有軌跡)與 lut_circle_ramp_at_unit 在 cycles 2500 / 10000 的時間。
原本由暫存的 mk_evidence129.py + an129.py + an129t.py + mut129.py 產生(續一百二十九);續一百三十四移進倉庫:
靜態 / 軌跡是 lc129_analyze.py、計時是 lc129t_analyze.py、突變是 lc129_mut.py(子行程重跑,輸出原樣寫進證據)。
verify_event_dispatch_table.py 與 docs/data/live_exec_addresses.json 取續一百二十九提交時的 git blob(_blobtools.py)。
原始紀錄在 .wsl_build/lc129a_live/、.wsl_build/lc129d_live/;量測前寫下的預測與兩個 cycles 包裝腳本在 .wsl_build/lc129_texts/。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from _evpaths import GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
import lc129t_analyze as an129t  # noqa: E402
from _blobtools import LIVE_JSON  # noqa: E402

RAW = ROOT / ".wsl_build"
TXT = RAW / "lc129_texts"
OUT = out_path("cmd_table_0_9_coverage_lut_cycles_20261016.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
RUNS = {
    "c2500_s12_nof": ("lc129a_live", "第 1 章戰場,cycles 2500(dosbox-x-c2500);索爾只留裂地術(法術 12)、MP 805,盜賊 #11 搬到 (19,14)、HP 9999;只停入口、迴圈結束、redraw(0) 之後。"),
    "c2500_s12_frames": ("lc129a_live", "同一場再施放一次裂地術(+5 清 0、MP 回 805),逐幀停。"),
    "c10000_s11_nof": ("lc129d_live", "第 1 章戰場,cycles 10000(dosbox-x-c10000);索爾只留地震術(法術 11),其餘同上;只停兩端。"),
    "c10000_s12_nof": ("lc129d_live", "同一場改成只留裂地術,只停兩端。"),
    "c10000_s12_frames": ("lc129d_live", "同一場再施放一次裂地術,逐幀停。"),
}
TRACE_S103C0 = "24c05f4091730e1114659c5065911b5ba45b2fcae2703ca8e303d215e87c6e4e"
TRACE_S103A = "d01dd2c26e97dd6f34b8d399ca55429bc64378fd6a43d3fae6c42c8966ade333"

with tempfile.TemporaryDirectory(prefix="ev129_") as _td:
    _js = Path(_td) / "an129.json"
    a = subprocess.run([sys.executable, str(GEN_DIR / "lc129_analyze.py"), "--json", str(_js)],
                       capture_output=True, text=True, encoding="utf-8", cwd=GEN_DIR)
    assert a.returncode == 0 and a.stdout.strip().endswith("ALL PASS") and "Traceback" not in a.stderr, a.stdout + a.stderr
    static = json.loads(_js.read_text(encoding="utf-8"))
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = an129t.main([])
assert _rc == 0 and _buf.getvalue().strip().endswith("ALL OK"), _buf.getvalue()[-1500:]
mut = subprocess.run([sys.executable, str(GEN_DIR / "lc129_mut.py")], capture_output=True, text=True, encoding="utf-8", cwd=GEN_DIR)
assert mut.returncode == 0 and "漏掉 0" in mut.stdout and "Traceback (most recent" not in mut.stdout + mut.stderr, mut.stdout + mut.stderr
live_meta = LIVE_JSON["_meta"]
assert TRACE_S103C0 in live_meta["trace_sha256"] and TRACE_S103A in live_meta["trace_sha256"]
out: dict = {
    "date": "2026-10-16", "exe_md5": EXE_MD5,
    "cmd_table_0_9": {
        "method": "STATIC ANALYSIS(FD2.EXE 位元組 + capstone 解碼)+ 既有實機軌跡 docs/data/live_exec_addresses.json + 既有 evidence;本輪沒有為這一項執行遊戲。",
        "table_0x51d01_0_9": static["table"],
        "stub_shape": {"說明": "跳板 = push 0x14; call __CHK; push [esp+0xc] ×2; push k; jmp 目標;值為 [k, 目標],null 表示不是跳板",
                       "rows": static["shapes"]},
        "ran_in_traces": static["ran"],
        "traces": {
            "s103c0_spell27_enemy_phase": {"sha256": TRACE_S103C0,
                                           "doc98": "續一百零四:玩家法術 27 → NPC / 敵方回合,[0x53af9]=1;含 0x1541f 與第 0、3、4、6 格入口"},
            "s103a_spells_9_12": {"sha256": TRACE_S103A, "doc98": "含第 9 格入口 0x214ad"},
        },
        "earlier_breakpoint_evidence": {
            "ai_spell_path_20260929.json C1": "[0x53af9]=1、法術 8:spell_damage_resolve 返回 0x212a4(command_generic_damage 內)",
            "spell9_path_20260930.json A2": "[0x53af9]=1、法術 9:0x214ad 返回 0x15426",
        },
        "checks": static["checks"],
    },
    "lut_cycles": {
        "method": "DOSBox-X 除錯器斷點(core=normal);harness 固定 cycles=5000,包裝腳本只把那一個參數換成 2500 / 10000"
                  "(執行中的 dosbox-x 程序參數讀到 cycles=2500 / cycles=10000,包裝腳本各記錄換了 1 處)。"
                  "只改模擬器記憶體裡的資料(索爾已學法術、+5、MP;盜賊 #11 位置與 HP),程式碼不動。計時讀線性 0x46c 的 BIOS tick(約 54.93 ms)。",
        "key_delivery": "cycles 2500 下 harness 的 send-keys(xdotool key,按下即放)有幾次沒被遊戲讀到;改用暫存 holdkey.sh"
                        "(同一個視窗 keydown → 0.3 秒 → keyup)後每一鍵都有反應。harness 沒有改。",
        "prediction_before_measuring": (TXT / "pred129.txt").read_text(encoding="utf-8"),
        "wrappers": {"dosbox-x-c2500": (TXT / "dosbox-x-c2500").read_text(encoding="utf-8"),
                     "dosbox-x-c10000": (TXT / "dosbox-x-c10000").read_text(encoding="utf-8")},
        "runs": [{"tag": t, "instance": sub.replace("_live", ""), "what": w,
                  "stops": json.loads((RAW / sub / f"{t}.json").read_text(encoding="utf-8"))["stops"]}
                 for t, (sub, w) in RUNS.items()],
        "entry_to_loop_end_ticks": an129t.MEAS,
        "older_runs": "5000_11 / 5000_12 取自 lut_circle_ramp_frame_time_ch22_post_20261015.json(續一百二十六);"
                      "2500_11 取自 lut_ch22_post_cycles2500_chapter_tables_20261015.json(續一百二十七)",
        "checks": an129t.results,
    },
    "mutation": mut.stdout.strip().splitlines(),
}

# 結論釘住:跑過的格 0、3、4、6、9;每個 cycles × 法術的 tick;預測(量測前寫下)與 an129t 用的區間相同
assert out["cmd_table_0_9"]["ran_in_traces"] == [0, 3, 4, 6, 9]
assert all(ok for _, ok, _ in out["cmd_table_0_9"]["checks"]) and len(out["cmd_table_0_9"]["checks"]) == 10
assert out["lut_cycles"]["entry_to_loop_end_ticks"] == {"2500_11": [16, 16], "2500_12": [22, 22], "5000_11": [7, 7], "5000_12": [10],
                                                       "10000_11": [3], "10000_12": [5, 5]}, out["lut_cycles"]["entry_to_loop_end_ticks"]
assert all(r["ok"] != r["control"] for r in an129t.results)
# 量測前寫下的預測區間就是 an129t 判定用的區間
pred = out["lut_cycles"]["prediction_before_measuring"]
assert "cycles 2500 裂地術:約 20 tick(容許 17..24)" in pred and "cycles 10000 地震術:約 3..4 tick(容許 2..5)" in pred
assert "cycles 10000 裂地術:約 5 tick(容許 4..7)" in pred and an129t.PRED == {(2500, 12): (17, 24), (10000, 11): (2, 5), (10000, 12): (4, 7)}
assert out["mutation"][-1] == "抓到 15 / 15,漏掉 0", out["mutation"][-1]


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
