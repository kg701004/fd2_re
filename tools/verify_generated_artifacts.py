#!/usr/bin/env python3
"""fd2_re - re-run each generator and prove its committed output still reproduces.

Why this exists
---------------
2026-09-08, measured: of 99 tools in `tools/`, only 38 have a `--selftest` or are
covered by a `test_*.py`. For the other **61 the repo-wide audit proves only that
they run** -- syntax parses, imports resolve, no crash on startup. Nothing checks
that what they emit is still correct.

For the subset that emits a *committed* artifact there is a cheap, strong check
that needs no new test fixtures: **run the generator again and diff**. It caught a
real drift the day it was first tried by hand -- `docs/data/story_script.json` had
been generated before `decode_story_text.py`'s `PORT` table was corrected against
the game's own name table, so the committed file still said 賽可邦勒 where the
tool now says 塞可邦勒 (90 bytes across three names).

What a result means
-------------------
* `IDENTICAL` -- the committed file is exactly what the current tool produces.
* `DRIFT` -- it is not. Either the tool changed and the artifact was never
  regenerated, or the artifact was hand-edited. **Both need a human**; this tool
  never rewrites a committed file.
* `ERROR` -- the generator could not run (missing input, wrong interpreter…).
  Reported, not hidden: a generator that cannot run is a worse problem than drift.

Honest limits
-------------
* The registry is **curated**, not discovered. 125 of the 135 JSON files under
  `docs/data` do not name the tool that made them, so they cannot be matched
  automatically. Entries here were each confirmed by hand.
* `IDENTICAL` proves *reproducibility*, not *correctness*. If the tool has always
  been wrong, its output reproduces wrongly. This complements the selftest layer,
  it does not replace it.

Usage
-----
    python tools/verify_generated_artifacts.py
    python tools/verify_generated_artifacts.py --only story_script
    python tools/verify_generated_artifacts.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EXE = "org_game/炎龍騎士團/FLAME2/FD2.EXE"
FDTXT = "extracted/raw/FDTXT"

# (artifact, tool, argv template, mode). "{out}" is replaced by a temp path.
#
# `mode` exists because a byte-diff is the wrong question for two real artifacts
# in this repo, and pretending otherwise produced two false DRIFT reports on the
# first run:
#   "bytes"      exact equality (the default, and the strongest).
#   "gen_keys"   only the TOP-LEVEL KEYS the generator emitted must match; keys
#                present solely in the committed file are human enrichment and
#                are listed, not failed. `item_sfx_tables.json` is this shape --
#                its `tables` block reproduces byte-identically while
#                `per_type_lookup` needs an input file no longer in the repo and
#                `_remaining_callers_dataflow_*` is hand-written analysis.
#   "overrides"  like gen_keys, but the committed file carries a
#                `manual_overrides` map and the entries it names are ALLOWED to
#                differ -- and *nothing else may*. That is strictly stronger than
#                skipping the file: it re-proves each round that the documented
#                overrides are still the only deviation. `command_labels.json`
#                has exactly two (ids 9 and 27, each with a written reason).
# Every entry was confirmed by hand -- see the docstring on why this is curated.
REGISTRY: list[tuple[str, str, list[str], str]] = [
    ("docs/data/event_id_groups.json", "extract_event_id_groups.py", ["{out}"], "bytes"),
    ("docs/data/story_script.json", "decode_story_text.py",
     ["--script-json", FDTXT, "{out}"], "bytes"),
    ("docs/data/command_labels.json", "export_command_labels.py",
     [f"{FDTXT}/FDTXT_000.bin", "{out}"], "overrides"),
    ("docs/data/item_labels.json", "export_item_labels.py",
     [f"{FDTXT}/FDTXT_000.bin", "{out}"], "bytes"),
    # 原本照 docstring 用 `--types-json docs/data/item_sfx_dispatch_types.json`,
    # 但那個輸入檔**不在 repo 裡**——工具的用法行本身已過期(同日一併修正)。
    ("docs/data/item_sfx_tables.json", "dump_item_sfx_tables.py",
     ["--output", "{out}"], "gen_keys"),
    ("docs/data/sfx_static_reachability.json", "fd2_sfx_static_reachability.py",
     ["--json", "{out}"], "bytes"),
    ("docs/data/exe_tables", "dump_exe_tables.py", [EXE, "{out}"], "dir"),
]


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot() -> dict[str, str]:
    """Hash every committed artifact in the registry, so the run can prove it did
    not touch any of them. A verifier that silently rewrites what it verifies is
    worse than no verifier."""
    out = {}
    for art, _, _, kind in REGISTRY:
        p = ROOT / art
        if kind != "dir" and p.exists():
            out[art] = _hash(p)
        elif kind == "dir" and p.is_dir():
            for f in sorted(p.glob("*.json")):
                out[f"{art}/{f.name}"] = _hash(f)
    return out


def _compare_curated(art: str, tool: str, committed: Path, regen: Path, kind: str) -> dict:
    """Compare a committed artifact that is generator output PLUS human curation.

    Rule for both modes: **every top-level key the generator emitted must match.**
    Keys only in the committed file are enrichment and are reported, not failed.
    In `overrides` mode the committed file additionally names entries that are
    permitted to differ, and the check asserts those are the ONLY differences --
    so a real regression inside a curated file still shows up.
    """
    import json
    try:
        c = json.loads(committed.read_text(encoding="utf-8"))
        g = json.loads(regen.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"artifact": art, "tool": tool, "verdict": "ERROR",
                "detail": f"JSON 解析失敗: {exc}"[:120]}
    if not isinstance(c, dict) or not isinstance(g, dict):
        return {"artifact": art, "tool": tool, "verdict": "ERROR",
                "detail": "curated 模式只支援頂層 dict"}

    overrides = c.get("manual_overrides") or {}
    allowed = {str(k) for k in overrides} if kind == "overrides" else set()
    bad, extra = [], sorted(set(c) - set(g))
    for k in g:
        if k not in c:
            bad.append(f"+{k}(重生有、committed 無)")
        elif c[k] == g[k]:
            continue
        elif kind == "overrides" and isinstance(c[k], list) and isinstance(g[k], list) \
                and len(c[k]) == len(g[k]):
            # 逐項比對:只有被 manual_overrides 指名的項目可以不同。
            for i, (x, y) in enumerate(zip(c[k], g[k])):
                if x == y:
                    continue
                ident = str(x.get("command_id", i)) if isinstance(x, dict) else str(i)
                if ident not in allowed:
                    bad.append(f"{k}[{ident}]")
        else:
            bad.append(k)
    return {"artifact": art, "tool": tool,
            "verdict": "IDENTICAL" if not bad else "DRIFT",
            "curated_keys": extra, "allowed_overrides": sorted(allowed),
            "unexpected": bad[:6]}


def check_one(art: str, tool: str, argv: list[str], kind: str, timeout: int) -> dict:
    p = ROOT / art
    if not p.exists():
        return {"artifact": art, "tool": tool, "verdict": "MISSING_ARTIFACT"}
    with tempfile.TemporaryDirectory(prefix="regen_") as td:
        out = Path(td) / ("regen.json" if kind == "file" else "regen_dir")
        real = [a.replace("{out}", str(out)) for a in argv]
        r = subprocess.run([sys.executable, str(ROOT / "tools" / tool), *real],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=timeout)
        if kind != "dir":
            if not out.exists():
                tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
                return {"artifact": art, "tool": tool, "verdict": "ERROR",
                        "detail": (tail[-1][:120] if tail else f"rc={r.returncode}")}
            if kind == "bytes":
                same = p.read_bytes() == out.read_bytes()
                return {"artifact": art, "tool": tool,
                        "verdict": "IDENTICAL" if same else "DRIFT",
                        "sizes": None if same else [p.stat().st_size, out.stat().st_size]}
            return _compare_curated(art, tool, p, out, kind)
        # directory: compare only the files the generator actually produced
        if not out.is_dir():
            tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            return {"artifact": art, "tool": tool, "verdict": "ERROR",
                    "detail": (tail[-1][:120] if tail else f"rc={r.returncode}")}
        made = sorted(f.name for f in out.glob("*.json"))
        drift = [n for n in made
                 if not (p / n).exists() or (p / n).read_bytes() != (out / n).read_bytes()]
        return {"artifact": art, "tool": tool,
                "verdict": "IDENTICAL" if not drift else "DRIFT",
                "produced": len(made), "drifted": drift[:6],
                "not_from_this_tool": len([f for f in p.glob('*.json')]) - len(made)}


def selftest() -> int:
    """Controls in both directions, plus proof the comparator is not blind."""
    fails = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        a, b = d / "a.json", d / "b.json"
        a.write_text('{"x": 1}\n', encoding="utf-8")

        print("(1) 負向控制:內容相同必須判為相同")
        shutil.copy(a, b)
        ok1 = a.read_bytes() == b.read_bytes()
        print(f"    {'PASS' if ok1 else 'FAIL'}: {ok1}")
        if not ok1:
            fails.append("相同內容被判為不同")

        print("\n(2) 正向控制:改一個位元組必須判為不同")
        b.write_text('{"x": 2}\n', encoding="utf-8")
        ok2 = a.read_bytes() != b.read_bytes()
        print(f"    {'PASS' if ok2 else 'FAIL'}: {ok2}")
        if not ok2:
            fails.append("被改動的內容仍被判為相同")

        print("\n(3) 大小相同但內容不同也必須抓到(story_script 的真實形狀)")
        # 那次真實漂移就是「同大小、90 個位元組不同」,只比大小會整個漏掉。
        a.write_text('{"n": "賽"}\n', encoding="utf-8")
        b.write_text('{"n": "塞"}\n', encoding="utf-8")
        ok3 = (a.stat().st_size == b.stat().st_size) and (a.read_bytes() != b.read_bytes())
        print(f"    {'PASS' if ok3 else 'FAIL'}: 同大小={a.stat().st_size == b.stat().st_size}, 判為不同={a.read_bytes() != b.read_bytes()}")
        if not ok3:
            fails.append("同大小不同內容沒被抓到")

    print("\n(4) overrides 模式必須只放行被指名的項目 —— 否則放寬等於關掉檢查")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        base = {"entries": [{"command_id": 0, "label": "A"},
                            {"command_id": 9, "label": "人工值"}],
                "manual_overrides": {"9": {"reason": "測試"}}}
        gen = {"entries": [{"command_id": 0, "label": "A"},
                           {"command_id": 9, "label": "原始解碼"}]}
        c, g = d / "c.json", d / "g.json"
        import json as _j
        c.write_text(_j.dumps(base), encoding="utf-8")
        g.write_text(_j.dumps(gen), encoding="utf-8")
        r1 = _compare_curated("t", "t", c, g, "overrides")
        ok4a = r1["verdict"] == "IDENTICAL"
        print(f"    {'PASS' if ok4a else 'FAIL'}: 被指名的覆寫(id 9)不算漂移 -> {r1['verdict']}")
        if not ok4a:
            fails.append(f"合法覆寫被誤判為漂移:{r1}")
        # 正向控制:動一個「沒有被指名」的項目,必須被抓到。
        gen["entries"][0]["label"] = "B"
        g.write_text(_j.dumps(gen), encoding="utf-8")
        r2 = _compare_curated("t", "t", c, g, "overrides")
        ok4b = r2["verdict"] == "DRIFT" and any("0" in x for x in r2["unexpected"])
        print(f"    {'PASS' if ok4b else 'FAIL'}: 未被指名的 id 0 改動必須抓到 -> "
              f"{r2['verdict']} {r2.get('unexpected')}")
        if not ok4b:
            fails.append(f"overrides 模式漏掉未指名的改動:{r2}")

    print("\n(5) 安全性:實際跑一輪後,所有已提交產物的雜湊必須完全不變")
    before = snapshot()
    run_all(timeout=900, quiet=True)
    after = snapshot()
    changed = [k for k in before if before[k] != after.get(k)]
    print(f"    {'PASS' if not changed else 'FAIL'}: {len(before)} 個產物,變動 {len(changed)} 個"
          + (f" {changed[:4]}" if changed else ""))
    if changed:
        fails.append(f"本工具改動了已提交產物:{changed[:4]}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向/負向各 1 + 同大小案例 + overrides 放行與攔截的配對控制 "
          "+ 不改動已提交檔案)。")
    return 0


def run_all(only: str | None = None, timeout: int = 900, quiet: bool = False) -> list[dict]:
    rows = []
    for art, tool, argv, kind in REGISTRY:
        if only and only not in art and only not in tool:
            continue
        r = check_one(art, tool, argv, kind, timeout)
        rows.append(r)
        if quiet:
            continue
        v = r["verdict"]
        extra = ""
        if v == "DRIFT":
            extra = f" {r.get('unexpected') or r.get('drifted') or r.get('sizes')}"
        elif v == "ERROR":
            extra = f" {r.get('detail','')}"
        elif v == "IDENTICAL" and "produced" in r:
            extra = f" ({r['produced']} 個檔;另有 {r['not_from_this_tool']} 個非此工具產出)"
        elif v == "IDENTICAL" and r.get("curated_keys"):
            extra = (f" (產生器鍵全數一致;人工增補鍵 {r['curated_keys']}"
                     + (f";允許覆寫 {r['allowed_overrides']}" if r.get("allowed_overrides") else "") + ")")
        print(f"  {r['verdict']:<16} {art:<44} <- {tool}{extra}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    rows = run_all(a.only, a.timeout)
    drift = [r for r in rows if r["verdict"] == "DRIFT"]
    err = [r for r in rows if r["verdict"] == "ERROR"]
    print(f"\n共 {len(rows)} 項:相同 {sum(1 for r in rows if r['verdict']=='IDENTICAL')}"
          f" / 漂移 {len(drift)} / 無法執行 {len(err)}")
    if drift:
        print("  **漂移(需人工判斷是工具變了還是產物被手改)**:", [r["artifact"] for r in drift])
    if err:
        print("  **無法執行**:", [(r["artifact"], r.get("detail", "")[:60]) for r in err])
    return 1 if (drift or err) else 0


if __name__ == "__main__":
    raise SystemExit(main())
