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
import json
import re
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
RAW = "extracted/raw"
FDFIELD = "org_game/炎龍騎士團/FLAME2/FDFIELD.DAT"

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
    # 2026-09-08 新增。加進來的第一次執行就抓到真東西:treasure 那支把一個
    # **已經是新版位址**的常數又加了一次版本位移(+0x356),輸出 `0x35baa`——
    # 落在指令中段,根本不是函式。已改成從事件跳表 0x51b91 讀(且走 fixup),
    # 並加上序頭檢查與 --selftest。field 那支一次就逐位元組相同。
    ("docs/data/native_field_event_rules.json",
     "extract_native_field_event_rules.py", [EXE, "{out}"], "bytes"),
    ("docs/data/native_treasure_event_rules.json",
     "extract_native_treasure_event_rules.py", [EXE, "{out}"], "bytes"),
    # 2026-09-08 第二批。這三個是 exe_tables/ 目錄項目與 fdfield 那支「不是
    # dump_exe_tables.py 產出」的那幾個檔——原本落在登錄表的視線外。
    # native_unit_tables.json 當時只差 source_size/md5/sha256 三個欄位(記的是
    # 已遺失的舊版 EXE),**所有表格資料逐位元組相同**,即單位表跨版本沒有變動;
    # 本輪重生把來源更正成實際存在的那一版。
    ("docs/data/exe_tables/native_unit_tables.json",
     "extract_native_unit_tables.py", [EXE, "{out}"], "bytes"),
    ("docs/data/exe_tables/terrain.json",
     "dump_terrain_table.py", [RAW, "{out}"], "bytes"),
    # --source 不給就寫成 null;省掉它會產生一個「只有 provenance 不同」的假漂移。
    ("docs/data/fdfield_native_ai_modes.json", "dump_native_ai_modes.py",
     ["--source", FDFIELD, RAW, "{out}"], "bytes"),
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

    print("\n(6) 涵蓋率報告必須兩邊都對:登錄的不算未涵蓋,未登錄的一定要出現在清單裡")
    total, covered, missing = coverage()
    reg_sample = "docs/data/native_treasure_event_rules.json"      # 直接登錄
    dir_sample = "docs/data/exe_tables/spell.json"                 # 經 dir 模式涵蓋
    ok_a = reg_sample not in missing and dir_sample not in missing
    # 負向:隨便一個沒登錄的產物必須被列出來,否則這個報告只是印個好看的數字
    ok_b = len(missing) > 0 and all((ROOT / m).exists() for m in missing[:20])
    ok_c = total == covered + len(missing)
    print(f"    {'PASS' if ok_a else 'FAIL'}: 已登錄的兩個樣本(含 dir 模式)不在未涵蓋清單")
    print(f"    {'PASS' if ok_b else 'FAIL'}: 未涵蓋清單有 {len(missing)} 項且都是真實存在的檔")
    print(f"    {'PASS' if ok_c else 'FAIL'}: {total} = {covered} + {len(missing)}")
    if not (ok_a and ok_b and ok_c):
        fails.append(f"涵蓋率報告不正確(total={total} covered={covered} missing={len(missing)})")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向/負向各 1 + 同大小案例 + overrides 放行與攔截的配對控制 "
          "+ 不改動已提交檔案 + 涵蓋率報告的正反向對照)。")
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


def coverage() -> tuple[int, int, list[str]]:
    """已提交的 docs/data 產物中,有幾個真的被這張登錄表涵蓋。

    2026-09-08:加這個是因為「共 12 項:相同 12」讀起來像「全部都對」,但它其實
    只說了登錄表裡那幾項——**沒有登錄項目的產物,在這份報告裡完全不存在**,
    而那才是大多數。乾淨的總計會藏起缺席的列,所以把分母印出來。
    """
    registered = set()
    for art, _, _, kind in REGISTRY:
        p = ROOT / art
        if kind == "dir" and p.is_dir():
            registered.update(str(q.relative_to(ROOT)).replace("\\", "/")
                              for q in p.rglob("*.json"))
        else:
            registered.add(art)
    all_art = sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                     for p in (ROOT / "docs/data").rglob("*.json"))
    missing = [a for a in all_art if a not in registered]
    return len(all_art), len(all_art) - len(missing), missing


def no_generator_set() -> set[str]:
    """已由 hygiene 棘輪**證明沒有產生器**的產物。

    2026-09-08:分母要一路誠實。「110 個從未被重生比對過」在 40 個已證明沒有
    產生器之後就變成誤導 —— 那 40 個不是「還沒做」,是「這條路不適用」。
    來源是 `docs/data/hygiene_baseline.json` 的 `permanent: no_generator`,
    而那個標記本身由 `verify_tool_hygiene` 第 (3b) 項每次實跑驗證(它會回頭呼叫
    本檔的 `discover()`,只要有人寫了產生器就會失敗)。兩邊互相牽制,不會各自漂移。
    """
    p = ROOT / "docs" / "data" / "hygiene_baseline.json"
    if not p.exists():
        return set()
    try:
        entries = json.loads(p.read_text(encoding="utf-8")).get("entries", [])
    except (OSError, ValueError):
        return set()
    return {e["name"] for e in entries
            if e.get("rule") == "regenerable" and e.get("permanent") == "no_generator"}


def discover() -> list[tuple[str, list[str]]]:
    """Propose (tool, artifacts) pairs for the uncovered backlog.

    The registry is curated on purpose — a name match is a lead, not proof, and
    every entry here has to be confirmed by an actual regeneration. But going
    through 109 uncovered artifacts by hand needs a starting list, and writing
    that list as a throwaway script is exactly the habit that produced a false
    mismatch earlier today. So it lives here, next to the registry it feeds.

    A tool is proposed only if it *writes* (json.dump / open(...,"w") /
    write_text) and mentions the artifact's basename; readers are excluded,
    which is what separates `char_summary.py` (reads characters.json, emits a
    PNG) from a real generator.
    """
    _, _, missing = coverage()
    by_base: dict[str, list[str]] = {}
    for m in missing:
        by_base.setdefault(Path(m).name, []).append(m)
    # 2026-09-08:第一版只要求「這支工具會寫檔」且「原始碼裡提到這個檔名」,
    # 結果把一堆**讀取者**列成候選(七支工具都提到 glyph_map.json,沒有一支產生它)。
    # 改成要求檔名出現在**寫入語境**:同一行或前後兩行內有寫入呼叫,或該行本身
    # 是把路徑指派給看起來像輸出的變數。仍然只是線索,但雜訊少很多。
    WRITE = re.compile(r"json\.dump|write_text\(|\bopen\([^)]*[\"']w[\"btx+]*[\"']"
                       r"|\bout\w*\s*=|\bdst\w*\s*=|--output|--json\b")
    out = []
    for tool in sorted((ROOT / "tools").glob("*.py")):
        if tool.name.startswith("test_") or tool.name.startswith("verify_"):
            continue
        src = tool.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"json\.dump|write_text\(|open\([^)]*[\"']w[\"btx+]*[\"']", src):
            continue
        lines = src.splitlines()
        hits = set()
        for i, line in enumerate(lines):
            for base, arts in by_base.items():
                if base not in line:
                    continue
                ctx = "\n".join(lines[max(0, i - 2):i + 3])
                if WRITE.search(ctx):
                    hits.update(arts)
        if hits:
            out.append((tool.name, sorted(hits)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true",
                    help="列出未涵蓋產物的候選產生器(是線索,不是證明——每一項仍須實跑確認)")
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--coverage", action="store_true",
                    help="列出所有沒有登錄項目、因此從未被重生比對過的已提交產物")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.discover:
        props = discover()
        print(f"未涵蓋產物的候選產生器 {len(props)} 支"
              f"(**線索,不是證明**——每一項都要實跑重生比對過才可登錄):")
        for tool, arts in props:
            print(f"  {tool}")
            for x in arts:
                print(f"      {x}")
        return 0
    if a.coverage:
        total, covered, missing = coverage()
        nogen = no_generator_set()
        pending = [m for m in missing if m not in nogen]
        print(f"docs/data 已提交 JSON {total} 個:登錄表涵蓋 {covered} 個、"
              f"已證明沒有產生器 {len(nogen)} 個、**尚待處理 {len(pending)} 個**")
        print("\n尚待處理(有機會登錄,或需要查清楚):")
        for m in pending:
            print("  ", m)
        print("\n已證明沒有產生器(人工記錄的 RE 分析/工具狀態檔;"
              "宣稱由 hygiene 第 (3b) 項驗證):")
        for m in sorted(nogen):
            print("  ", m)
        return 0
    rows = run_all(a.only, a.timeout)
    drift = [r for r in rows if r["verdict"] == "DRIFT"]
    err = [r for r in rows if r["verdict"] == "ERROR"]
    total, covered, missing = coverage()
    print(f"\n共 {len(rows)} 項:相同 {sum(1 for r in rows if r['verdict']=='IDENTICAL')}"
          f" / 漂移 {len(drift)} / 無法執行 {len(err)}")
    # 分母跟著印,否則上面那行讀起來像「全部產物都對」;而未涵蓋的那堆還要再拆一次,
    # 否則「已證明沒有產生器」會被混進「還沒做」裡,讓剩餘量看起來比實際多。
    nogen = no_generator_set()
    pending = [m for m in missing if m not in nogen]
    print(f"涵蓋率:docs/data 的 {total} 個已提交 JSON 中,{covered} 個有登錄項目、"
          f"{len(nogen)} 個**已證明沒有產生器**(重生比對不適用)、"
          f"{len(pending)} 個**尚待處理**(`--coverage` 可列出)")
    if drift:
        print("  **漂移(需人工判斷是工具變了還是產物被手改)**:", [r["artifact"] for r in drift])
    if err:
        print("  **無法執行**:", [(r["artifact"], r.get("detail", "")[:60]) for r in err])
    return 1 if (drift or err) else 0


if __name__ == "__main__":
    raise SystemExit(main())
