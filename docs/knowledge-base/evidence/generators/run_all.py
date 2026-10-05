"""重算每一份由本目錄產生器產生的證據檔,與已提交的版本逐 byte 比對。不會覆寫已提交的檔案。

結果:
    IDENTICAL      重算結果與已提交檔案完全相同。
    DRIFT          不同(產生器改過而證據沒重算,或證據被手改)—— 需要人看。
    MISSING_INPUT  產生器的輸入與 inputs_manifest.json 不符(缺檔或內容不同),沒有重算。
    ERROR          產生器執行失敗(含 assert 失敗)、或沒有產生清單上的輸出。

限制:有 3 份證據把 `str(Path)` 寫進 JSON(Windows 路徑分隔字元),逐 byte 相同只在 Windows 成立。
原始紀錄(`.wsl_build/`)與原版遊戲檔不在 git 裡(著作權與大小),其他機器上會是 MISSING_INPUT。

用法:
    python run_all.py [ev_s76 ...]     不給名稱 = 全部;全部 IDENTICAL 才 exit 0
    python run_all.py --selftest       比對器與輸入檢查的正反對照
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _evpaths import EVIDENCE, GEN_DIR, MANIFEST, MISSING_INPUT_RC


def run_one(gen: str, outputs: list[str], out_dir: Path, env_extra: dict[str, str] | None = None,
            script: Path | None = None) -> dict:
    """在 out_dir 重算 gen,回傳 {gen, verdict, detail}。"""
    env = dict(os.environ, FD2_EVIDENCE_OUT_DIR=str(out_dir), PYTHONPATH=str(GEN_DIR), **(env_extra or {}))
    env.pop("FD2_EVIDENCE_MANIFEST_BUILD", None)
    r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", str(script or GEN_DIR / f"{gen}.py")],
                       cwd=GEN_DIR, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == MISSING_INPUT_RC and "MISSING_INPUT" in r.stderr:
        return {"gen": gen, "verdict": "MISSING_INPUT", "detail": r.stderr.strip().splitlines()[1:4]}
    if r.returncode != 0:
        tail = r.stderr.strip().splitlines()
        return {"gen": gen, "verdict": "ERROR", "detail": tail[-1][:200] if tail else f"rc={r.returncode}"}
    made = sorted(p.name for p in out_dir.iterdir())
    if made != sorted(outputs):
        return {"gen": gen, "verdict": "ERROR", "detail": f"輸出 {made} != 清單 {sorted(outputs)}"}
    drift = [n for n in outputs if (out_dir / n).read_bytes() != (EVIDENCE / n).read_bytes()]
    return {"gen": gen, "verdict": "DRIFT" if drift else "IDENTICAL", "detail": drift}


def run_all(names: list[str]) -> list[dict]:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    unknown = [n for n in names if n not in man]
    if unknown:
        raise SystemExit(f"清單裡沒有:{unknown}")
    res = []
    with tempfile.TemporaryDirectory(prefix="evrun_") as td:
        for gen in names or list(man):
            d = Path(td) / gen
            d.mkdir()
            res.append(run_one(gen, man[gen]["outputs"], d))
    return res


def selftest() -> int:
    """正反對照:比對器要能說 DRIFT,輸入檢查要能說 MISSING_INPUT,未改動的產生器要 IDENTICAL。"""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))["generators"]
    gen = "ev_s65b"  # 最小、最快的一個
    outs = man[gen]["outputs"]
    fails = []
    with tempfile.TemporaryDirectory(prefix="evself_") as tdn:
        td = Path(tdn)
        # 1. 正向:原樣重算 → IDENTICAL
        (td / "a").mkdir()
        r = run_one(gen, outs, td / "a")
        if r["verdict"] != "IDENTICAL":
            fails.append(f"原樣重算應為 IDENTICAL,得到 {r}")
        # 2. 產生器多寫一個空白 → DRIFT(比對器不是瞎的)
        src = (GEN_DIR / f"{gen}.py").read_text(encoding="utf-8")
        old = 'json.dump(out, open(OUT, "w", encoding="utf-8", newline="\\n"), ensure_ascii=False, indent=1)'
        if src.count(old) != 1:
            fails.append("找不到 ev_s65b 的輸出那一行,突變對照沒有執行")
        else:
            mut = td / "mut" / f"{gen}.py"
            mut.parent.mkdir()
            mut.write_text(src.replace(old, old.replace("indent=1", "indent=2")), encoding="utf-8")
            (td / "b").mkdir()
            r = run_one(gen, outs, td / "b", script=mut)
            if r["verdict"] != "DRIFT":
                fails.append(f"改了縮排應為 DRIFT,得到 {r}")
        # 3. 遊戲目錄 / 原始紀錄不在 → MISSING_INPUT;用需要遊戲檔的 ev_s66,把 FD2_GAME_DIR 指到空目錄
        (td / "empty").mkdir()
        (td / "c").mkdir()
        r = run_one("ev_s66", man["ev_s66"]["outputs"], td / "c", env_extra={"FD2_GAME_DIR": str(td / "empty")})
        if r["verdict"] != "MISSING_INPUT" or not any("{GAME}/FD2.EXE" in x for x in r["detail"]):
            fails.append(f"遊戲目錄是空的應為 MISSING_INPUT 且點名 FD2.EXE,得到 {r}")
        # 4. 清單裡的 sha256 改一個字 → MISSING_INPUT(內容不符);改的是暫存副本,正式清單不動
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        first = next(iter(m["generators"][gen]["inputs"]))
        sha = m["generators"][gen]["inputs"][first][1]
        m["generators"][gen]["inputs"][first][1] = ("0" if sha[0] != "0" else "1") + sha[1:]
        bad_man = td / "manifest_bad.json"
        bad_man.write_bytes((json.dumps(m, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        (td / "d").mkdir()
        r = run_one(gen, outs, td / "d", env_extra={"FD2_EVIDENCE_MANIFEST": str(bad_man)})
        if r["verdict"] != "MISSING_INPUT" or not any("內容不符" in x for x in r["detail"]):
            fails.append(f"sha256 不符應為 MISSING_INPUT(內容不符),得到 {r}")
    for f in fails:
        print("FAIL", f)
    print("selftest", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--selftest"]:
        return selftest()
    res = run_all(argv)
    for r in res:
        print(f"{r['verdict']:14s} {r['gen']}  {r['detail'] or ''}")
    bad = [r for r in res if r["verdict"] != "IDENTICAL"]
    print(f"{len(res) - len(bad)}/{len(res)} IDENTICAL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
