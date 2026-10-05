"""證據產生器的變異測試共用執行器。

每個變異只改產生器裡一個判準或預測,必須讓產生器以 AssertionError 失敗(不能是缺檔、
語法錯誤之類的其他失敗)。變異版寫在暫存目錄、輸出也導到暫存目錄,不碰已提交的證據檔。
先跑一次未變異的對照:它必須成功並重算出與已提交檔案相同的 bytes,否則變異結果沒有意義。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _evpaths import EVIDENCE, GEN_DIR, MANIFEST


def _run(script: Path, out_dir: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, FD2_EVIDENCE_OUT_DIR=str(out_dir), PYTHONPATH=str(GEN_DIR))
    env.pop("FD2_EVIDENCE_MANIFEST_BUILD", None)
    return subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", str(script)], cwd=GEN_DIR, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def run_mutants(gen: str, mutants: list[tuple[str, str, str]]) -> int:
    """執行 gen 的變異測試;全部被殺且對照通過才回傳 0。"""
    src = (GEN_DIR / f"{gen}.py").read_text(encoding="utf-8")
    outputs = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"][gen]["outputs"]
    with tempfile.TemporaryDirectory(prefix=f"mut_{gen}_") as tdn:
        td = Path(tdn)
        ctl = td / "control"
        ctl.mkdir()
        r = _run(GEN_DIR / f"{gen}.py", ctl)
        same = r.returncode == 0 and all((ctl / n).exists() and (ctl / n).read_bytes() == (EVIDENCE / n).read_bytes()
                                         for n in outputs)
        if not same:
            print(f"CONTROL FAIL {gen}: rc={r.returncode} {r.stderr[-300:]}")
            return 1
        print(f"CONTROL ok   {gen}: 未變異版重算與已提交檔案相同")
        killed = 0
        for i, (name, old, new) in enumerate(mutants):
            assert src.count(old) == 1, (name, src.count(old))
            d = td / f"m{i}"
            d.mkdir()
            script = d / f"{gen}.py"   # 檔名同產生器:require_inputs 依檔名查清單
            script.write_text(src.replace(old, new), encoding="utf-8")
            r = _run(script, d)
            ok = r.returncode != 0 and "AssertionError" in r.stderr and "Traceback" in r.stderr
            killed += ok
            print("KILLED  " if ok else "SURVIVED", name, "" if ok else r.stderr[-300:])
    print(f"{killed}/{len(mutants)} killed")
    return 0 if killed == len(mutants) else 1
