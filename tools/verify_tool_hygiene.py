#!/usr/bin/env python3
"""fd2_re - a ratchet: new tools and new artifacts cannot arrive unchecked.

Why this exists
---------------
2026-09-08. Asked why every verification round kept turning up new problems, the
honest answer was measurable: repeating a check found **nothing** (5 rounds, zero
cross-round disagreement), while every *extension* of coverage found something —
2 registry entries → 1 real bug, 3 more → 2 more issues. The defects were not
new. `safe_output.py`'s selftest had been dead since the day the file was
created. They were simply never looked at.

So the fix is not "look harder". It is to stop the unchecked surface from
growing. Every other verifier here answers *"is what we have correct?"*. This one
answers *"did something arrive without the checks that would have caught it?"* —
and it is the only one that can fail on a file nobody has thought about yet.

The ratchet
-----------
`hygiene_baseline.json` records the violations that already exist. Then:

* a violation **not** in the baseline fails the gate — that is the whole point,
  new work must arrive complete;
* a baseline entry that **no longer violates** also fails — otherwise the
  baseline rots into a permanent excuse list and silently re-grants exemptions
  for problems that were fixed years ago.

So the baseline can only shrink. `--update-baseline` re-records it deliberately,
and prints what changed in each direction so a shrink is never confused with a
quiet re-grant.

What counts as checked
----------------------
Per tool (`tools/*.py`, excluding `test_*.py`):
  docstring   a module docstring (a tool nobody can read is a tool nobody runs)
  correctness a `--selftest`/`selftest` subcommand, a `test_*.py` that
              imports/invokes it, **or** an entry in
              `verify_generated_artifacts.REGISTRY` — a generator whose output
              is regenerated and byte-diffed against the committed artifact on
              every run is checked, and checked hard: that axis is what caught
              `extract_native_treasure_event_rules.py` emitting `0x35baa` and
              `dump_native_ai_modes.py`'s missing `--source`. Counting only
              selftests marked 7 such tools as unchecked when they were in fact
              under the strongest check in the repo. (The widening is paired
              with a control in the selftest: a tool with *none* of the three
              must still be flagged, or this would just be switching the rule
              off.)
  console     no unguarded non-ASCII output (the cp950 class that silently
              killed 14 tools' output on this machine)
  shebang     LF, not CRLF (the Write tool produces CRLF here; a CR-terminated
              shebang makes the script unrunnable under WSL)
Per artifact (`docs/data/**/*.json`):
  regenerable a `verify_generated_artifacts.REGISTRY` entry, or an explicit
              `no_generator` baseline entry naming why it cannot have one

Cross-checks against the tools it depends on
--------------------------------------------
Every rule here reuses the tool that owns it rather than reimplementing it, so
the two cannot drift apart:
  * artifact coverage comes from `verify_generated_artifacts.coverage()`
  * console-encoding risk comes from `verify_docs_match_cli.console_encoding_risks()`
  * selftest detection mirrors `verify_all_tools.layer_selftest`'s two spellings,
    and `--cross-check` asserts this file's answer agrees with
    `verify_selftest_discrimination.INVOKE` on every tool that table lists —
    a disagreement means one of the two has gone stale, which is itself a finding.

Usage
-----
    python tools/verify_tool_hygiene.py                # gate: 0 = no new debt
    python tools/verify_tool_hygiene.py --cross-check  # + agreement with siblings
    python tools/verify_tool_hygiene.py --list         # current violations
    python tools/verify_tool_hygiene.py --update-baseline
    python tools/verify_tool_hygiene.py --selftest
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
BASELINE = ROOT / "docs" / "data" / "hygiene_baseline.json"

RULES = ("docstring", "correctness", "console", "shebang", "lazy_import", "regenerable")

# 延遲 import 常用的第三方名稱。把模組層 import 改成函式內延遲 import 時,很容易
# 漏掉其中一條路徑 —— 2026-09-08 改 decode_fdicon.py 時就漏了 `--overview` 分支,
# 那條路徑會 NameError。這個規則專門擋這一類。
LAZY_NAMES = ("Image", "ImageDraw", "ImageFont", "np", "numpy", "cv2")


def _module_level_imports(tree: ast.AST) -> set[str]:
    """模組層 import 進來的名稱,**包含包在 try/except ImportError 裡的**。

    第一版只看 `tree.body` 裡的 ImportFrom,結果把 7 支用
    `try: from PIL import Image / except ImportError: ...` 的檔案全報成缺 import
    —— 全是偽陽性。可選相依套件在這個 repo 就是這樣寫的。
    """
    out: set[str] = set()
    stack = list(getattr(tree, "body", []))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out |= {a.asname or a.name.split(".")[0] for a in node.names}
        elif isinstance(node, (ast.Try, ast.If, ast.With)):
            stack.extend(node.body)
            stack.extend(getattr(node, "orelse", []))
            stack.extend(getattr(node, "finalbody", []))
            for h in getattr(node, "handlers", []):
                stack.extend(h.body)
    return out


def lazy_import_gaps(src: str) -> list[str]:
    """函式用了延遲 import 的名稱,但那個函式裡沒有把它 import 進來。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    have = _module_level_imports(tree)
    gaps = []
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        used = {n.value.id for n in ast.walk(fn)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id in LAZY_NAMES}
        used |= {n.func.id for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id in LAZY_NAMES}
        used -= have
        if not used:
            continue
        local = set()
        for n in ast.walk(fn):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                local |= {a.asname or a.name.split(".")[0] for a in n.names}
        missing = used - local
        if missing:
            gaps.append(f"{fn.name}() 用了 {sorted(missing)} 但沒有 import")
    return gaps


def tool_files() -> list[Path]:
    return sorted(p for p in TOOLS.glob("*.py") if not p.name.startswith("test_"))


def has_selftest(src: str) -> bool:
    """Mirror of `verify_all_tools.layer_selftest`'s detection, deliberately.

    It requires the *interface*, not the bare word: `dump_exe_tables.py` has a
    `selftest()` function that runs as part of a normal extraction, and a looser
    match once invoked it as `--selftest`, which it read as a filename and
    crashed on.
    """
    return ("--selftest" in src
            or re.search(r"add_parser\(\s*[\"']selftest", src) is not None)


def covered_by_tests() -> set[str]:
    """Tool names some `test_*.py` imports or names. Import first: a test that
    imports the module constrains it far more than one that merely mentions it
    in a string, but both are evidence somebody wrote a check."""
    names = {p.name for p in tool_files()}
    out: set[str] = set()
    for t in TOOLS.glob("test_*.py"):
        src = t.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        if f"{a.name}.py" in names:
                            out.add(f"{a.name}.py")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if f"{node.module}.py" in names:
                        out.add(f"{node.module}.py")
        for m in re.findall(r"([a-z0-9_]+)\.py", src):
            if f"{m}.py" in names:
                out.add(f"{m}.py")
    return out


def registry_tools() -> set[str]:
    """Tools whose output is regenerated and byte-diffed every run.

    Reads `verify_generated_artifacts.REGISTRY` rather than keeping a second
    list, so the two cannot drift apart.
    """
    import verify_generated_artifacts as vg
    return {tool for _art, tool, _argv, _kind in vg.REGISTRY}


def violations() -> list[dict]:
    """Every current violation, as {kind, name, rule, detail}."""
    out: list[dict] = []
    tested = covered_by_tests()
    regen = registry_tools()

    import verify_docs_match_cli as vd
    risky = {name for name, _ in vd.console_encoding_risks()}

    for p in tool_files():
        raw = p.read_bytes()
        src = raw.decode("utf-8", errors="replace")
        if raw.startswith(b"#!") and b"\r\n" in raw.split(b"\n", 1)[0] + b"\n":
            out.append({"kind": "tool", "name": p.name, "rule": "shebang",
                        "detail": "shebang 行是 CRLF,WSL 下無法執行"})
        try:
            doc = ast.get_docstring(ast.parse(src))
        except SyntaxError:
            doc = None
            out.append({"kind": "tool", "name": p.name, "rule": "docstring",
                        "detail": "無法解析(SyntaxError)"})
        if not doc:
            out.append({"kind": "tool", "name": p.name, "rule": "docstring",
                        "detail": "沒有模組 docstring"})
        if not has_selftest(src) and p.name not in tested and p.name not in regen:
            out.append({"kind": "tool", "name": p.name, "rule": "correctness",
                        "detail": "沒有 selftest、沒有 test_*.py 涵蓋,"
                                  "也不在產物重生登錄表裡"})
        if p.name in risky:
            out.append({"kind": "tool", "name": p.name, "rule": "console",
                        "detail": "輸出非 ASCII 但沒有 reconfigure stdout"})
        for gap in lazy_import_gaps(src):
            out.append({"kind": "tool", "name": p.name, "rule": "lazy_import",
                        "detail": gap})

    import verify_generated_artifacts as vg
    _, _, missing = vg.coverage()
    for m in missing:
        out.append({"kind": "artifact", "name": m, "rule": "regenerable",
                    "detail": "沒有 verify_generated_artifacts 登錄項目"})
    return out


def key(v: dict) -> tuple[str, str]:
    return (v["name"], v["rule"])


# 永久豁免的種類 -> 驗證這個宣稱的函式。
#
# 2026-09-08:「永久豁免」如果只是基準線裡的一個字串,它就是一張沒人查的免死金牌
# ——而且會混進「還沒做」的數字裡,讓剩餘量看起來比實際可清的多。所以每一種豁免
# 都要有**可執行的證明**,由 selftest 每次重跑。
def _proves_ida_embedded(name: str) -> tuple[bool, str]:
    """跑一次,必須因為 IDA 內嵌模組不存在而失敗。

    這比「檔案裡有 import ida_*」強:後者只是文字比對,前者證明它在這台機器的
    一般 python 下**確實不可執行**,因此不可能有 selftest。
    """
    import subprocess
    p = TOOLS / name
    if not p.exists():
        return False, "檔案不存在"
    r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    err = (r.stderr or "")
    ok = r.returncode != 0 and "ModuleNotFoundError" in err and "ida" in err
    tail = [l for l in err.strip().splitlines() if l.strip()]
    return ok, (tail[-1][:70] if tail else f"rc={r.returncode}")


def _proves_no_generator(name: str) -> tuple[bool, str]:
    """證明「這個產物沒有產生器」——所以重生比對這條路本身不適用。

    這不是把檢查關掉:證明的內容是**可證偽的**。`verify_generated_artifacts.discover()`
    會掃全部工具,找出在寫入語境裡提到這個檔名的候選;只要有人日後寫了產生器,
    這個宣稱就會立刻失敗,逼人回來重新處理。

    repo 裡大多數 `docs/data` JSON 是人工記錄的 RE 分析結果(反組譯發現、dispatch
    表、位址庫),本來就沒有東西可以重生。把它們留在「還沒做」裡,只會讓剩餘量
    看起來比實際可清的多。
    """
    import verify_generated_artifacts as vg
    if not (ROOT / name).exists():
        return False, "檔案不存在"
    for tool, arts in vg.discover():
        if name in arts:
            return False, f"{tool} 看起來會產生它 —— 宣稱不成立,請登錄或查清楚"
    return True, "沒有任何工具在寫入語境提到它"


PERMANENT_PROOFS = {
    "ida_embedded": _proves_ida_embedded,
    "no_generator": _proves_no_generator,
}


def load_baseline(path: Path = BASELINE) -> dict:
    if not path.exists():
        return {"_policy": "", "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def compare(current: list[dict], base: dict) -> tuple[list[dict], list[dict]]:
    """Returns (new violations, baseline entries that no longer violate)."""
    cur = {key(v) for v in current}
    known = {(e["name"], e["rule"]) for e in base.get("entries", [])}
    new = [v for v in current if key(v) not in known]
    fixed = [e for e in base.get("entries", []) if (e["name"], e["rule"]) not in cur]
    return new, fixed


def cross_check() -> list[tuple[bool, str]]:
    """Agree with the siblings that own each rule, or say so.

    Running the same logic twice is not corroboration, so these compare against a
    *different* tool's independently maintained view.
    """
    out = []
    import verify_selftest_discrimination as vs
    tested = covered_by_tests()
    disagree = []
    for name in vs.INVOKE:
        p = TOOLS / name
        if not p.exists():
            disagree.append(f"{name}(INVOKE 列了但檔案不存在)")
            continue
        if not has_selftest(p.read_text(encoding="utf-8", errors="replace")):
            disagree.append(f"{name}(INVOKE 說有 selftest,本工具偵測不到)")
    out.append((not disagree,
                f"與 verify_selftest_discrimination.INVOKE 一致"
                + (f":不符 {disagree}" if disagree else f"({len(vs.INVOKE)} 支全數相符)")))

    import verify_generated_artifacts as vg
    total, covered, missing = vg.coverage()
    mine = {v["name"] for v in violations() if v["rule"] == "regenerable"}
    out.append((mine == set(missing),
                f"與 verify_generated_artifacts.coverage() 一致"
                f"(未涵蓋 {len(missing)} 個 / 本工具算出 {len(mine)} 個)"))

    # 有 selftest 的工具集合,必須被 verify_all_tools 的 selftest 層實際執行過。
    # 這裡不重跑那個(很慢),只確認兩邊對「哪些工具有 selftest」的判定同源:
    # 本檔的 has_selftest() 是照抄它的兩種拼法,若上游改了而這裡沒跟上,
    # INVOKE 那條交叉檢查會先炸,所以這條只斷言集合非空且合理。
    withself = [p.name for p in tool_files()
                if has_selftest(p.read_text(encoding="utf-8", errors="replace"))]
    out.append((len(withself) >= 20,
                f"偵測到 {len(withself)} 支有 selftest(過少代表偵測邏輯壞了)"))
    return out


def selftest() -> int:
    import tempfile
    fails = []

    print("(1) 故障注入:一支缺 docstring、缺 selftest 的工具必須被抓到")
    probe = TOOLS / "zz_hygiene_probe.py"
    probe.write_text("x = 1\n", encoding="utf-8", newline="\n")
    try:
        v = violations()
        got = {r["rule"] for r in v if r["name"] == probe.name}
        ok1 = {"docstring", "correctness"} <= got
        print(f"    {'PASS' if ok1 else 'FAIL'}: 抓到 {sorted(got)}")
        if not ok1:
            fails.append(f"注入的壞工具只被抓到 {sorted(got)}")

        print("\n(2) 配對控制:同一支補齊之後必須不再被抓到 —— 否則規則恆為真")
        probe.write_text('"""說明。"""\nimport argparse\n'
                         'def main():\n'
                         '    ap = argparse.ArgumentParser()\n'
                         '    ap.add_argument("--selftest", action="store_true")\n',
                         encoding="utf-8", newline="\n")
        v2 = violations()
        got2 = {r["rule"] for r in v2 if r["name"] == probe.name}
        ok2 = not ({"docstring", "correctness"} & got2)
        print(f"    {'PASS' if ok2 else 'FAIL'}: 剩餘 {sorted(got2) or '無'}")
        if not ok2:
            fails.append(f"補齊後仍被抓到 {sorted(got2)}")
    finally:
        probe.unlink(missing_ok=True)

    print("\n(2b) correctness 三種來源的配對控制:三者皆無仍必須被抓到")
    # 「在產物登錄表裡也算通過」是一個放寬。放寬與「把規則關掉」只差一步,所以這裡
    # 同時測兩邊:登錄表裡的工具放行,而三種來源都沒有的工具**必須**照樣被抓到。
    regen = registry_tools()
    tested = covered_by_tests()
    withself = {p.name for p in tool_files()
                if has_selftest(p.read_text(encoding="utf-8", errors="replace"))}
    v3 = {r["name"] for r in violations() if r["rule"] == "correctness"}
    passed_by_regen = sorted(regen - withself - tested)
    leaked = [n for n in passed_by_regen if n in v3]
    none_of_three = sorted({p.name for p in tool_files()} - withself - tested - regen)
    missed = [n for n in none_of_three if n not in v3]
    ok2b = not leaked and not missed and passed_by_regen and none_of_three
    print(f"    {'PASS' if ok2b else 'FAIL'}: 只靠登錄表通過的 {len(passed_by_regen)} 支"
          f"(仍被抓到的 {leaked or '無'});三者皆無的 {len(none_of_three)} 支"
          f"(漏抓的 {missed or '無'})")
    if not ok2b:
        fails.append(f"correctness 放寬失衡:漏放 {leaked}、漏抓 {missed}")

    print("\n(3) 棘輪必須雙向:未登錄的違規要失敗,已修好的登錄項目也要失敗")
    cur = [{"kind": "tool", "name": "a.py", "rule": "docstring", "detail": ""}]
    base_empty = {"entries": []}
    base_stale = {"entries": [{"name": "a.py", "rule": "docstring", "reason": "x"},
                              {"name": "gone.py", "rule": "docstring", "reason": "x"}]}
    new1, fixed1 = compare(cur, base_empty)
    new2, fixed2 = compare(cur, base_stale)
    ok3 = (len(new1) == 1 and not fixed1) and (not new2 and len(fixed2) == 1
                                               and fixed2[0]["name"] == "gone.py")
    print(f"    {'PASS' if ok3 else 'FAIL'}: 未登錄新違規={len(new1)}(應 1)、"
          f"已登錄不再違規={len(fixed2)}(應 1,且是 gone.py)")
    if not ok3:
        fails.append("棘輪比對不正確")

    print("\n(2c) lazy_import 規則的配對控制:漏 import 要抓到,包在 try 裡的不算漏")
    # 這條規則是為了擋「把模組層 import 改成延遲 import 時漏掉某條路徑」——
    # 2026-09-08 改 decode_fdicon.py 時真的漏了一次(`--overview` 分支會 NameError)。
    # 但第一版的偵測把 `try: from PIL import Image / except ImportError:` 這種
    # **可選相依**的寫法全報成缺 import,7 個全是偽陽性。兩邊都要測。
    miss = lazy_import_gaps(
        "def f():\n    return Image.new('RGB', (1, 1))\n")
    okA = len(miss) == 1
    tryform = lazy_import_gaps(
        "try:\n    from PIL import Image\nexcept ImportError:\n    Image = None\n"
        "def f():\n    return Image.new('RGB', (1, 1))\n")
    okB = not tryform
    local = lazy_import_gaps(
        "def f():\n    from PIL import Image\n    return Image.new('RGB', (1, 1))\n")
    okC = not local
    ok2c = okA and okB and okC
    print(f"    {'PASS' if okA else 'FAIL'}: 真的漏 import -> 抓到 {len(miss)} 筆(應 1)")
    print(f"    {'PASS' if okB else 'FAIL'}: 模組層 try/except import -> {tryform or '不算漏'}")
    print(f"    {'PASS' if okC else 'FAIL'}: 函式內延遲 import -> {local or '不算漏'}")
    if not ok2c:
        fails.append(f"lazy_import 規則失衡:漏抓={not okA}、"
                     f"try 形式偽陽性={bool(tryform)}、函式內偽陽性={bool(local)}")

    print("\n(3b) 每一筆「永久豁免」都要有可執行的證明,不能只是基準線裡的一句話")
    base_p = load_baseline()
    perm = [e for e in base_p.get("entries", []) if e.get("permanent")]
    unproven, disproven = [], []
    for e in perm:
        kind = e.get("permanent")
        prover = PERMANENT_PROOFS.get(kind)
        if prover is None:
            unproven.append(f"{e['name']}({kind}:沒有對應的驗證函式)")
            continue
        ok, detail = prover(e["name"])
        if not ok:
            disproven.append(f"{e['name']}: {detail}")
    ok3b = perm and not unproven and not disproven
    print(f"    {'PASS' if ok3b else 'FAIL'}: {len(perm)} 筆永久豁免,"
          f"無法驗證 {unproven or '無'},驗證不成立 {disproven or '無'}")
    if unproven or disproven:
        fails.append(f"永久豁免的宣稱站不住:{(unproven + disproven)[:3]}")
    elif not perm:
        fails.append("基準線裡沒有任何永久豁免 —— 若確實沒有,請移除這條檢查")

    print("\n(4) 基準線每一筆都要指向真實存在的東西,且附理由(避免腐爛成免死金牌)")
    base = load_baseline()
    bad = []
    for e in base.get("entries", []):
        if e.get("rule") not in RULES:
            bad.append(f"{e.get('name')}: 未知規則 {e.get('rule')}")
        elif not str(e.get("reason", "")).strip():
            bad.append(f"{e.get('name')}: 沒有理由")
        elif e["rule"] == "regenerable":
            if not (ROOT / e["name"]).exists():
                bad.append(f"{e['name']}: 檔案不存在")
        elif not (TOOLS / e["name"]).exists():
            bad.append(f"{e['name']}: 工具不存在")
    ok4 = not bad
    print(f"    {'PASS' if ok4 else 'FAIL'}: {len(base.get('entries', []))} 筆"
          + (f",問題 {bad[:3]}" if bad else ""))
    if not ok4:
        fails.append(f"基準線有問題:{bad[:3]}")

    print("\n(5) 規則不能恆為假:在真實工作區上,每條工具規則都要能算出結果")
    v = violations()
    kinds = {r["rule"] for r in v}
    tools_n = len(tool_files())
    ok5 = tools_n > 50 and "regenerable" in kinds
    print(f"    {'PASS' if ok5 else 'FAIL'}: 掃到 {tools_n} 支工具、"
          f"違規種類 {sorted(kinds)}")
    if not ok5:
        fails.append("掃描範圍或規則明顯不對")

    print("\n(6) 交叉驗證:與擁有各條規則的兄弟工具必須一致")
    for ok, msg in cross_check():
        print(f"    {'PASS' if ok else 'FAIL'}: {msg}")
        if not ok:
            fails.append(msg)

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(故障注入 + 配對控制 + 雙向棘輪 + 基準線完整性 "
          "+ 非恆假 + 三項跨工具交叉驗證)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--cross-check", action="store_true")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    cur = violations()
    base = load_baseline()
    new, fixed = compare(cur, base)

    if a.list:
        by_rule: dict[str, list[str]] = {}
        for v in cur:
            by_rule.setdefault(v["rule"], []).append(v["name"])
        for rule in RULES:
            names = sorted(by_rule.get(rule, []))
            print(f"\n{rule}({len(names)} 筆):")
            for n in names:
                print("  ", n)
        return 0

    if a.update_baseline:
        prev = {(e["name"], e["rule"]): e for e in base.get("entries", [])}
        entries = []
        for v in sorted(cur, key=lambda x: (x["rule"], x["name"])):
            old = prev.get(key(v), {})
            ent = {"name": v["name"], "rule": v["rule"],
                   "reason": old.get("reason", "既有存量,尚未處理")}
            # permanent 是「這一筆永遠不可能清掉」的標記,由 selftest 逐筆實跑驗證
            # (見 PERMANENT_PROOFS)。重建基準線時必須保留,否則證明過的豁免會
            # 悄悄退回成「還沒做」,讓剩餘量看起來比實際可清的多。
            if old.get("permanent"):
                ent["permanent"] = old["permanent"]
            entries.append(ent)
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(
            {"_policy": "本檔是棘輪基準線:只准變短。新違規不得加入,"
                        "除非附上具體理由;不再違規的項目必須移除,否則會誤放行。"
                        "由 tools/verify_tool_hygiene.py --update-baseline 產生。",
             "entries": entries}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"基準線已更新:{len(base.get('entries', []))} -> {len(entries)} 筆"
              f"(新增 {len(new)}、移除 {len(fixed)})")
        for v in new:
            print(f"  + {v['rule']:<12} {v['name']}")
        for e in fixed:
            print(f"  - {e['rule']:<12} {e['name']}")
        return 0

    perm = [e for e in base.get("entries", []) if e.get("permanent")]
    print(f"目前違規 {len(cur)} 筆,基準線 {len(base.get('entries', []))} 筆"
          f"(其中**永久豁免 {len(perm)} 筆**,實際待處理 {len(cur) - len(perm)} 筆)")
    # 分母要誠實:把「永遠不可能清」和「還沒做」混在同一個數字裡,會讓進度看起來
    # 比實際差,也會讓終點看起來比實際遠。
    if a.cross_check:
        print("\n跨工具交叉驗證:")
        bad_x = False
        for ok, msg in cross_check():
            print(f"  {'一致' if ok else '**不一致**'} {msg}")
            bad_x |= not ok
        if bad_x:
            print("\n**與兄弟工具不一致** —— 其中一邊已經過期,先查清楚再繼續。")
            return 1

    if new:
        print(f"\n**新增 {len(new)} 筆未登錄的違規(這就是這道閘門的目的)**:")
        for v in new:
            print(f"  {v['rule']:<12} {v['name']}: {v['detail']}")
    if fixed:
        print(f"\n**基準線有 {len(fixed)} 筆已經不再違規,必須移除**"
              f"(留著會替未來的同名問題免費放行):")
        for e in fixed:
            print(f"  {e['rule']:<12} {e['name']}")
    if not new and not fixed:
        print("沒有新增未登錄的違規,基準線也沒有過期項目。")
    return 1 if (new or fixed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
