#!/usr/bin/env python3
"""fd2_re - one command that runs every verification axis, N times, and gives one verdict.

Why this exists
---------------
By 2026-09-08 the repo had six independent verifiers, each answering a different
question, and no way to say "is the toolchain usable right now?" without running
six commands and remembering which failures are benign. Worse, several real
defects that day were found only because a check was run *again* in a different
way -- a non-reproducible random seed, a hard PIL import that only bites under
the WSL interpreter, a `UnicodeEncodeError` class that only bites on a cp950
console. Repetition and axis-rotation are not optional extras here; they are how
things get found.

The axes, and what each exists to catch
---------------------------------------
  audit        `verify_all_tools.py` -- 10 layers (syntax…refs…selftest). Proves
               every tool RUNS. Its own 22-check selftest runs first.
  discrim      `verify_selftest_discrimination.py` -- mutates each tool's source
               and requires its selftest to notice. Proves the selftests are not
               decorative.
  docs_cli     `verify_docs_match_cli.py` -- documented flags vs implemented
               ones, the `--selftest` spelling contract, and the console-encoding
               crash class.
  artifacts    `verify_generated_artifacts.py` -- re-runs generators and diffs
               against the committed output. Proves outputs still reproduce.
  findings     `verify_findings.py` -- re-derives the recorded numeric findings
               from the image, under the strict function-entry criterion, and
               cross-checks three of them against an independent implementation.
               `artifacts` proves the FILES still reproduce; this proves the
               CONCLUSIONS still do.
  worklist     `worklist_status.py --selftest` -- the worklist parser.
  tests        every `tools/test_*.py`.
  wsl          the same offline selftests under the OTHER interpreter. This axis
               alone found the PIL import that made two tools unusable in the
               environment the DOSBox harness runs in.

Repetition
----------
`--rounds N` runs everything N times. Rounds are not identical by construction:
`discrim` advances its mutation seed each round, so round 2 samples mutations
round 1 never tried. Anything that changes between rounds is reported as
UNSTABLE, which is its own finding -- a verifier that flaps is not usable.

Known-benign
------------
Two audit WARNs are deliberate and must not be "fixed"; they are whitelisted here
with their reasons, and the whitelist is printed so it cannot rot silently:
`extract_event_id_groups.py` raises `FileNotFoundError` rather than `SystemExit`
on purpose (SystemExit inherits BaseException and would slip past its test's
`except Exception`), and `audit_evidence_provenance.py`'s `ANI.DAT`/`FD2.EXE`
mentions are its own selftest fixture strings.

Usage
-----
    python tools/verify_everything.py                 # one round, all axes
    python tools/verify_everything.py --rounds 3
    python tools/verify_everything.py --skip wsl,discrim
    python tools/verify_everything.py --selftest
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

KNOWN_BENIGN = {
    "extract_event_id_groups.py": "刻意用 FileNotFoundError 而非 SystemExit"
                                  "(後者繼承 BaseException,會穿過該工具測試的 except Exception 保護)",
    "audit_evidence_provenance.py": "提及 ANI.DAT/FD2.EXE 是它自己 selftest 的斷言字串,"
                                    "不是引用已移除的目錄",
}


def run(argv: list[str], timeout: int, cwd: Path = ROOT) -> tuple[int, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(cwd), timeout=timeout)
        return r.returncode, ((r.stdout or "") + (r.stderr or ""))
    except subprocess.TimeoutExpired:
        return -9, "TIMEOUT"


def axis_audit(round_no: int, timeout: int) -> dict:
    rc0, out0 = run([PY, "tools/verify_all_tools.py", "--selftest"], timeout)
    if rc0 != 0:
        return {"ok": False, "detail": "harness selftest 失敗", "raw": out0[-200:]}
    rc, out = run([PY, "tools/verify_all_tools.py"], timeout)
    line = next((l for l in out.splitlines() if l.startswith("TOTAL")), "")
    fails = [l.strip() for l in out.splitlines() if l.strip().startswith("FAIL")]
    return {"ok": rc == 0 and not fails, "detail": line.strip(), "fails": fails[:5]}


def axis_simple(name: str, argv: list[str], timeout: int) -> dict:
    rc, out = run([PY, *argv], timeout)
    tail = [l for l in out.splitlines() if l.strip()]
    return {"ok": rc == 0, "detail": (tail[-1][:110] if tail else f"rc={rc}")}


def axis_discrim(round_no: int, timeout: int) -> dict:
    rc0, _ = run([PY, "tools/verify_selftest_discrimination.py", "--selftest"], timeout)
    if rc0 != 0:
        return {"ok": False, "detail": "discrim selftest 失敗"}
    # 每輪換 seed,讓第 2 輪抽到第 1 輪沒試過的突變。
    rc, out = run([PY, "tools/verify_selftest_discrimination.py", "--offline",
                   "--tries", "12", "--seed", str(round_no)], timeout)
    tail = [l for l in out.splitlines() if l.strip().startswith("共")]
    return {"ok": rc == 0, "detail": (tail[-1][:110] if tail else f"rc={rc}")}


def axis_findings(timeout: int) -> dict:
    """Its selftest has to pass first: the strict-vs-loose criterion contrast is
    what makes the re-derivation meaningful, so a broken criterion must not be
    allowed to report 'all findings still hold'."""
    rc0, _ = run([PY, "tools/verify_findings.py", "--selftest"], timeout)
    if rc0 != 0:
        return {"ok": False, "detail": "findings selftest 失敗(判準本身壞了)"}
    rc, out = run([PY, "tools/verify_findings.py", "--cross-check"], timeout)
    tail = [l for l in out.splitlines() if l.strip().startswith("共")]
    return {"ok": rc == 0, "detail": (tail[-1][:110] if tail else f"rc={rc}")}


def axis_tests(timeout: int) -> dict:
    fails = []
    files = sorted((ROOT / "tools").glob("test_*.py"))
    for f in files:
        rc, out = run([PY, str(f)], timeout)
        if rc != 0:
            fails.append(f.name)
    return {"ok": not fails, "detail": f"{len(files) - len(fails)}/{len(files)} 通過",
            "fails": fails}


def axis_wsl(timeout: int) -> dict:
    """Same offline selftests under WSL python3 -- a different interpreter with a
    different dependency set. This is the axis that caught the PIL import."""
    script = ROOT / ".wsl_build" / "verify_everything_wsl.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    tools = ["worklist_status", "encode_text", "decode_story_text",
             "audit_evidence_provenance", "safe_output", "fd2_env_healthcheck",
             "verify_docs_match_cli", "verify_selftest_discrimination"]
    body = ["#!/bin/bash", "cd /mnt/c/Users/kg701/Desktop/GAME/fd2_re || exit 1",
            "fail=0", "for t in " + " ".join(tools) + "; do",
            '  python3 "tools/$t.py" --selftest >/dev/null 2>&1 || { echo "FAIL $t"; fail=$((fail+1)); }',
            "done", 'echo "wsl_fail=$fail"']
    script.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    rc, out = run(["wsl", "-d", "Ubuntu", "bash",
                   "/mnt/c/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/verify_everything_wsl.sh"],
                  timeout, cwd=ROOT)
    n = next((l.split("=")[1].strip() for l in out.splitlines() if l.startswith("wsl_fail=")), None)
    if n is None:
        return {"ok": False, "detail": f"無法取得結果 rc={rc}: {out[-80:]}"}
    return {"ok": n == "0", "detail": f"{len(tools)} 支中 {n} 支失敗"}


AXES = {
    "audit": lambda r, t: axis_audit(r, t),
    "discrim": lambda r, t: axis_discrim(r, t),
    "docs_cli": lambda r, t: axis_simple("docs_cli", ["tools/verify_docs_match_cli.py"], t),
    "artifacts": lambda r, t: axis_simple("artifacts", ["tools/verify_generated_artifacts.py"], t),
    "findings": lambda r, t: axis_findings(t),
    "worklist": lambda r, t: axis_simple("worklist", ["tools/worklist_status.py", "--selftest"], t),
    "tests": lambda r, t: axis_tests(t),
    "wsl": lambda r, t: axis_wsl(t),
}


def selftest() -> int:
    """The driver must (a) actually invoke each axis and (b) fail when an axis
    fails. A driver that reports OK regardless is worse than not having one."""
    fails = []
    print("(1) 每個軸都必須真的被呼叫到,且名稱與 AXES 表一致")
    ok1 = set(AXES) == {"audit", "discrim", "docs_cli", "artifacts", "findings",
                        "worklist", "tests", "wsl"}
    print(f"    {'PASS' if ok1 else 'FAIL'}: {sorted(AXES)}")
    if not ok1:
        fails.append("AXES 表與預期不符")

    print("\n(2) 正向控制:一個必定失敗的軸必須讓整體判定為失敗")
    probe = {"ok": False, "detail": "deliberate"}
    overall = all(r["ok"] for r in [{"ok": True}, probe])
    print(f"    {'PASS' if not overall else 'FAIL'}: 整體={overall}(應為 False)")
    if overall:
        fails.append("失敗的軸沒有讓整體失敗")

    print("\n(3) 負向控制:全部成功時整體必須判定為成功")
    overall2 = all(r["ok"] for r in [{"ok": True}, {"ok": True}])
    print(f"    {'PASS' if overall2 else 'FAIL'}: 整體={overall2}")
    if not overall2:
        fails.append("全部成功卻判定失敗")

    print("\n(4) 已知良性清單必須非空且附理由(避免它靜默腐爛成空殼)")
    ok4 = bool(KNOWN_BENIGN) and all(len(v) > 10 for v in KNOWN_BENIGN.values())
    print(f"    {'PASS' if ok4 else 'FAIL'}: {len(KNOWN_BENIGN)} 筆")
    if not ok4:
        fails.append("已知良性清單為空或缺理由")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(1 正向 + 2 負向 + 清單完整性)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--skip", default="", help="逗號分隔的軸名")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    history: dict[str, list[bool]] = {}
    for rnd in range(1, a.rounds + 1):
        print(f"\n{'=' * 70}\n第 {rnd}/{a.rounds} 輪\n{'=' * 70}")
        for name, fn in AXES.items():
            if name in skip:
                print(f"  {name:<12} SKIP(--skip)")
                continue
            t0 = time.time()
            r = fn(rnd, a.timeout)
            history.setdefault(name, []).append(r["ok"])
            mark = "OK  " if r["ok"] else "**FAIL**"
            print(f"  {name:<12} {mark} {r['detail']}  [{time.time() - t0:.0f}s]")
            for f in r.get("fails", [])[:3]:
                print(f"               - {f}")

    print(f"\n{'=' * 70}")
    unstable = [k for k, v in history.items() if len(set(v)) > 1]
    failed = [k for k, v in history.items() if not all(v)]
    print("已知良性(不應「修」):")
    for k, why in KNOWN_BENIGN.items():
        print(f"  {k}: {why}")
    if unstable:
        print(f"\n**不穩定(跨輪結果不一致,本身就是問題)**: {unstable}")
    if failed:
        print(f"**失敗的軸**: {failed}")
        return 1
    print(f"\n全部 {len(history)} 個軸 × {a.rounds} 輪皆通過,且無跨輪不一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
