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
  hygiene      `verify_tool_hygiene.py` -- the ratchet. Every other axis asks
               "is what we have correct?"; this one asks "did something arrive
               without the checks that would have caught it?", and is the only
               axis that can fail on a file nobody has thought about yet. It
               fails on a violation not in the baseline AND on a baseline entry
               that no longer violates, so the backlog can only shrink.
  truncation   `verify_truncation_robustness.py` -- feeds every byte-level
               decoder truncated and corrupted input and requires it to degrade
               rather than crash. Four decoders had the same unguarded-index
               bug; 36 real sub-resources hit one of them.
  worklist     `worklist_status.py --selftest` -- the worklist parser.
  citations    `verify_address_citations.py` -- the only axis that asks whether a
               conclusion already proven WRONG is still being argued from. Every
               other axis re-derives what the docs claim; this one re-derives what
               they should have stopped claiming. `known_address_errata.json` had
               existed since 2026-08-20 and no axis read it, so 263 uncorrected
               citations of 26 disproven addresses sat in the knowledge base with
               nothing able to notice. Both-directions ratchet, like `hygiene`.
  claim_coverage
               `verify_address_claim_coverage.py` -- the denominator `findings`
               never had. `findings` reports 17/17, but 17 counts hand-registered
               conclusions, not claims: 1368 addresses are asserted in the docs to
               be function entries and only 405 carry any byte-level evidence. It
               unions three independent JVM-free signals (Watcom prologue / direct
               E8 target / fixup target) because the 541-entry prologue set is
               "functions needing a stack probe", not all functions -- 0x4ebe3 has
               40 callers and no prologue. Measurement with a ratchet on the
               unreviewed remainder, not a gate on the whole backlog.
  tests        every `tools/test_*.py`.
  wsl          the same offline selftests under the OTHER interpreter. This axis
               alone found the PIL import that made two tools unusable in the
               environment the DOSBox harness runs in.

Repetition
----------
`--rounds N` runs everything N times. Rounds are not identical by construction:
`discrim` advances its mutation seed each round, so round 2 samples mutations
round 1 never tried. Two different things can change, and they are reported
separately -- conflating them is what let a real difference hide:

* **UNSTABLE** -- the axis's pass/fail *verdict* flips between rounds. A
  verifier that flaps is not usable; this is a hard finding.
* **跨輪內容有變** -- the verdict held but the *conclusion* changed (e.g.
  discrim reporting "62 discriminating / 1 weak" then "63 / 0"). Not
  necessarily a defect -- resampling legitimately moves borderline tools, see
  `verify_selftest_discrimination.py`'s own note on `decode_story_text.py` --
  but it must be printed, with both rounds' text, not swallowed.

Until 2026-09-10 only the boolean was compared, so the second kind was
silently summarised as "no cross-round inconsistency". `axis_discrim` also
threw away the line naming *which* tool was weak, so the difference could not
be chased after the fact; it now carries that line through.

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
    # 「弱 1」而不說是哪一支,等於沒報。這一行是 discrim 自己印出來的名單,
    # 之前被整段丟棄,使得跨輪 62/1 vs 63/0 的差異事後無從追查。
    named = [l.strip() for l in out.splitlines() if l.strip().startswith("弱(")]
    return {"ok": rc == 0, "detail": (tail[-1][:110] if tail else f"rc={rc}"),
            "fails": named[:3]}


def axis_hygiene(timeout: int) -> dict:
    """Selftest first (its cross-tool checks are what stop it drifting from the
    tools that own each rule), then the gate with --cross-check."""
    rc0, _ = run([PY, "tools/verify_tool_hygiene.py", "--selftest"], timeout)
    if rc0 != 0:
        return {"ok": False, "detail": "hygiene selftest 失敗(棘輪本身壞了)"}
    rc, out = run([PY, "tools/verify_tool_hygiene.py", "--cross-check"], timeout)
    tail = [l for l in out.splitlines() if l.strip()]
    return {"ok": rc == 0, "detail": (tail[-1][:110] if tail else f"rc={rc}"),
            "fails": [l.strip() for l in out.splitlines() if "**" in l][:3]}


def axis_truncation(timeout: int) -> dict:
    """Selftest first: its fault injection is what makes a clean run mean
    anything -- "7/7 safe" from a checker that cannot detect an unguarded
    decoder is not a result."""
    rc0, _ = run([PY, "tools/verify_truncation_robustness.py", "--selftest"], timeout)
    if rc0 != 0:
        return {"ok": False, "detail": "truncation selftest 失敗(故障注入抓不到)"}
    rc, out = run([PY, "tools/verify_truncation_robustness.py"], timeout)
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
             "verify_docs_match_cli", "verify_selftest_discrimination",
             # 2026-09-11:純位元組/fixup 工具,刻意不相依 capstone —— 放進本軸
             # 正是為了讓「哪天又在模組層要求反組譯器」立刻在這裡失敗。
             "derive_ail_entry_points", "verify_event_dispatch_table"]
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
    "hygiene": lambda r, t: axis_hygiene(t),
    "truncation": lambda r, t: axis_truncation(t),
    "worklist": lambda r, t: axis_simple("worklist", ["tools/worklist_status.py", "--selftest"], t),
    "citations": lambda r, t: axis_simple("citations", ["tools/verify_address_citations.py"], t),
    "claim_coverage": lambda r, t: axis_simple(
        "claim_coverage", ["tools/verify_address_claim_coverage.py"], t),
    "tests": lambda r, t: axis_tests(t),
    "wsl": lambda r, t: axis_wsl(t),
}


def classify_rounds(history: dict[str, list[bool]],
                    details: dict[str, list[str]]) -> tuple[list, list, list]:
    """跨輪分類器,回傳 (unstable, drifted, failed)。

    抽成獨立函式的原因:selftest 原本用字面值就地重算 `all(...)`,那只驗證了
    「我在 selftest 裡寫的那行對不對」,`main()` 真正跑的那行有 bug 也照過。
    現在兩邊呼叫同一個函式,成對案例才真的釘得住它。
    """
    unstable = [k for k, v in history.items() if len(set(v)) > 1]
    failed = [k for k, v in history.items() if not all(v)]
    drifted = [k for k, v in details.items()
               if k not in unstable and len(set(v)) > 1]
    return unstable, drifted, failed


def selftest() -> int:
    """The driver must (a) actually invoke each axis and (b) fail when an axis
    fails. A driver that reports OK regardless is worse than not having one."""
    fails = []
    print("(1) 每個軸都必須真的被呼叫到,且名稱與 AXES 表一致")
    ok1 = set(AXES) == {"audit", "discrim", "docs_cli", "artifacts", "findings",
                        "hygiene", "truncation", "worklist", "citations",
                        "claim_coverage", "tests", "wsl"}
    print(f"    {'PASS' if ok1 else 'FAIL'}: {sorted(AXES)}")
    if not ok1:
        fails.append("AXES 表與預期不符")

    print("\n(2) 正向控制:一個必定失敗的軸必須讓整體判定為失敗")
    _, _, f2 = classify_rounds({"a": [True, True], "b": [False, False]},
                               {"a": ["x", "x"], "b": ["y", "y"]})
    print(f"    {'PASS' if f2 == ['b'] else 'FAIL'}: failed={f2}(應為 ['b'])")
    if f2 != ["b"]:
        fails.append("失敗的軸沒有讓整體失敗")

    print("\n(3) 負向控制:全部成功且結論一字不差時,三個清單都必須是空的")
    u3, d3, f3 = classify_rounds({"a": [True, True]}, {"a": ["同一句", "同一句"]})
    ok3 = not u3 and not d3 and not f3
    print(f"    {'PASS' if ok3 else 'FAIL'}: unstable={u3} drifted={d3} failed={f3}")
    if not ok3:
        fails.append("全部成功卻報出不一致")

    print("\n(3b) 成對案例:判定翻轉 = UNSTABLE;判定相同而內容變 = 內容漂移")
    #     右邊那組正是 2026-09-10 真實漏掉的那筆:兩輪都 ok=True,只有數字不同。
    u_flip, d_flip, _ = classify_rounds({"a": [True, False]}, {"a": ["p", "q"]})
    u_same, d_same, _ = classify_rounds(
        {"discrim": [True, True]},
        {"discrim": ["共 63 個工具:有鑑別力 62 / 弱 1 / 基準就失敗 0",
                     "共 63 個工具:有鑑別力 63 / 弱 0 / 基準就失敗 0"]})
    ok3b = (u_flip == ["a"] and d_flip == []          # 翻轉只算一次,不重複計為漂移
            and u_same == [] and d_same == ["discrim"])
    print(f"    {'PASS' if ok3b else 'FAIL'}: 翻轉→unstable={u_flip},drifted={d_flip};"
          f" 同判定→unstable={u_same},drifted={d_same}")
    if not ok3b:
        fails.append("UNSTABLE 與內容漂移沒有被正確分開")

    print("\n(3c) 非平凡性:若把內容比對拿掉,(3b) 右邊那組必須變成偵測不到")
    #     沒有這個控制,(3b) 可能只是被別的條件湊巧判對。
    blind = [k for k, v in {"discrim": [True, True]}.items() if len(set(v)) > 1]
    ok3c = blind == [] and d_same == ["discrim"]
    print(f"    {'PASS' if ok3c else 'FAIL'}: 只看布林值={blind}(舊行為,應為空)"
          f",看內容={d_same}")
    if not ok3c:
        fails.append("內容漂移檢查是平凡的(只看布林值也偵測得到)")

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
    print("\n--selftest passed(1 正向 + 2 負向 + UNSTABLE/內容漂移的成對案例"
          "與非平凡性控制 + 清單完整性)。")
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
    details: dict[str, list[str]] = {}
    for rnd in range(1, a.rounds + 1):
        print(f"\n{'=' * 70}\n第 {rnd}/{a.rounds} 輪\n{'=' * 70}")
        for name, fn in AXES.items():
            if name in skip:
                print(f"  {name:<12} SKIP(--skip)")
                continue
            t0 = time.time()
            r = fn(rnd, a.timeout)
            history.setdefault(name, []).append(r["ok"])
            details.setdefault(name, []).append(r["detail"])
            mark = "OK  " if r["ok"] else "**FAIL**"
            print(f"  {name:<12} {mark} {r['detail']}  [{time.time() - t0:.0f}s]")
            for f in r.get("fails", [])[:3]:
                print(f"               - {f}")

    print(f"\n{'=' * 70}")
    # 判定跨輪相同、但結論內容不同 —— 舊版只比對 ok 布林值,所以 discrim
    # 的「62 有鑑別力/1 弱」對「63/0」兩輪都是 ok=True,被歸為「無不一致」。
    # 這種漂移不必然是缺陷(discrim 每輪換 seed,抽樣本來就會動),但它
    # 絕不該被一句「無跨輪不一致」蓋掉:是哪一支、飄多少,要看得見。
    unstable, drifted, failed = classify_rounds(history, details)
    print("已知良性(不應「修」):")
    for k, why in KNOWN_BENIGN.items():
        print(f"  {k}: {why}")
    if unstable:
        print(f"\n**不穩定(跨輪判定不一致,本身就是問題)**: {unstable}")
    if drifted:
        print("\n跨輪判定相同但**結論內容有變**(不必然是缺陷,但必須看得見):")
        for k in drifted:
            for i, d in enumerate(details[k], 1):
                print(f"  {k} 第{i}輪: {d}")
    if failed:
        print(f"**失敗的軸**: {failed}")
        return 1
    tailmsg = "" if drifted else ",且無跨輪不一致"
    print(f"\n全部 {len(history)} 個軸 × {a.rounds} 輪皆通過{tailmsg}。")
    if drifted:
        print(f"跨輪內容有變的軸:{drifted}(見上)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
