"""續一百二十五證據:evidence/item79_aim_exp_reward_lines_20261014.json。

lc125 兩回合(道具 79 的瞄準與評分、經驗值累加、grant_reward_rows 種類 3 的台詞)逐項對反組譯預測。原本由暫存的
mk_evidence125.py + an125.py + mut_an125.py 產生(續一百二十五);續一百三十四移進倉庫:分析是 lc125_analyze.py、
突變是 lc125_mut.py(以子行程重跑,輸出原樣寫進證據),原始紀錄在 .wsl_build/lc125_live/(記錄 JSON 與兩張視窗截圖)。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys

from _evpaths import EVIDENCE, GAME, GEN_DIR, ROOT, out_path, require_inputs  # noqa: E402
require_inputs(__file__)
import lc125_analyze as an125  # noqa: E402

D = ROOT / ".wsl_build" / "lc125_live"
OUT = out_path("item79_aim_exp_reward_lines_20261014.json")
EXE_MD5 = "33464c81e6a364fd0660141139aa8e6e"
assert hashlib.md5((GAME / "FD2.EXE").read_bytes()).hexdigest() == EXE_MD5
KEEP = (0, 3, 5, 6, 10, 11, 15)
WHAT = {
    "a1": "round A(第 1 回合)。arm:敵 #11 搬到 (19,14)、slot2 = 道具 79,#1..#4 設已行動,法術列 3 命中率 100;"
          "#11 第一次進 ai_item_candidate_select 時把 #5、#10 搬到 (19,13)、(19,6)(續一百二十三第一輪的位置)。"
          "錄製腳本在第一個種類 3 停點之後,於遊戲執行中傾印 VGA 失敗而結束;這份是它印在 stdout 的每一站(印出時略過 units / codes / row)。",
    "a1b": "round A 的後半:以 LC_MIDRUN 從第一句台詞等按鍵處接續(斷點沿用第二階段那組)。",
    "b1": "round B(第 2 回合)。arm 同上,另把 #3 的 +7 由 0x1e 改成 0x85,讓存活目標也累加經驗值;沒有搬單位。",
}


def trim(s: dict) -> dict:
    s = dict(s)
    if isinstance(s.get("units"), list):
        s["units"] = [u for u in s["units"] if u["i"] in KEEP]
    return s


_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = an125.main()
assert _rc == 0, _buf.getvalue()[-2000:]
res = list(an125.results)
real = [r for r in res if not r["control"]]
ctl = [r for r in res if r["control"]]
mut = subprocess.run([sys.executable, str(GEN_DIR / "lc125_mut.py")], capture_output=True, text=True, encoding="utf-8")
assert mut.returncode == 0 and "漏掉 0" in mut.stdout and "Traceback (most recent" not in mut.stdout + mut.stderr, mut.stdout + mut.stderr
out: dict = {
    "date": "2026-10-14", "exe_md5": EXE_MD5,
    "method": "DOSBox-X 除錯器斷點,FDTXT_002 那一場(章節位元組 1,羅德鎮),連續 2 個回合;只改模擬器記憶體裡的單位資料與法術列 3 的命中率,程式碼不動。"
              "ai_item_candidate_select:0x1567e、0x1576e、0x157fd、0x1586a(arm 時就設)。ai_item_action 入口 0x15055 停下後才設:"
              "0x1c8e2(經驗值累加)、0x20fe5、0x21072、0x1ac2b / 0x1ac4e(種類 3)、0x2107a、0x152fd。種類 3 停點之後恢復執行,6 秒後截視窗。",
    "static": {
        "high_class_row_0x41_+7_0x85": an125.sbytes(0x61AF9 + 0x41 * 10, 10).hex(),
        "high_class_row_0x42_+7_0x86": an125.sbytes(0x61AF9 + 0x42 * 10, 10).hex(),
        "high_class_row_0x1c_+7_0x60_anchor": an125.sbytes(0x61AF9 + 0x1C * 10, 10).hex(),
        "item79_row_0x602ad": an125.ITEM79.hex(),
        "phase_table_0x51a97": list(an125.sbytes(0x51A97, 20)),
        "fixed_phase_0x51a93": an125.sbytes(0x51A93, 4).hex(),
    },
    "fdtxt": {f"FDTXT_{n:03d}": {"bytes": p.stat().st_size, "md5": hashlib.md5(p.read_bytes()).hexdigest()}
              for n, p in an125.FDTXT.items()},
    "runs": [],
    "analysis": {"script": "an125.py(暫存)", "checks": len(real), "pass": sum(bool(r["ok"]) for r in real),
                 "controls": len(ctl), "controls_fail_as_expected": sum(r["ok"] is False for r in ctl),
                 "controls_not_applicable": sum(r["ok"] is None for r in ctl), "items": res},
    "mutation": {"script": "mut_an125.py(暫存)", "stdout": mut.stdout.strip().splitlines()},
    "files": {},
}
for tag in ("a1", "a1b", "b1"):
    d = json.loads((D / f"{tag}.json").read_text(encoding="utf-8"))
    out["runs"].append({"tag": tag, "what": WHAT[tag], "stops": [trim(s) for s in d["stops"]]})

# 結論釘住:全部檢查符合、沒有對照判成符合、12 個突變全部抓到
a = out["analysis"]
assert a["pass"] == a["checks"] and a["controls_fail_as_expected"] + a["controls_not_applicable"] == a["controls"], a
assert (a["checks"], a["controls"], a["controls_not_applicable"]) == (35, 21, 5), a
assert out["mutation"]["stdout"][-1] == "突變 12 個,抓到 12,漏掉 0", out["mutation"]["stdout"][-1]

# 已提交的 PNG = 種類 3 停點之後的視窗截圖,與原始截圖逐 byte 相同
FILES = {"a1_k3_1.png": "grant_reward_rows_kind3_line_unit5_20261014.png", "a1b_k3_1.png": "grant_reward_rows_kind3_line_unit10_20261014.png"}
for src, dst in FILES.items():
    assert (EVIDENCE / dst).read_bytes() == (D / src).read_bytes(), dst
out["files"] = {dst: hashlib.md5((EVIDENCE / dst).read_bytes()).hexdigest() for dst in FILES.values()}


def write() -> None:
    js = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert b"\r" not in js
    OUT.write_bytes(js)
    print("ok", OUT.name, len(js))


if __name__ == "__main__":
    write()
