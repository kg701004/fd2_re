#!/usr/bin/env python3
"""fd2_re - does each tool's docstring describe the CLI the tool actually has?

Why this exists
---------------
2026-09-08: `safe_output.py` advertised a `--selftest` that crashed on its very
first line (a `UnicodeEncodeError` printing "✓" to a cp950 console), so all seven
of its checks had been dead for as long as the file existed. "The docs say it has
a selftest" had never been checked against "the code accepts that flag and that
flag does something".

**Two different mismatches, and this file checks both** -- the distinction is
worth stating because the first version of this docstring conflated them:

* *docs vs code*: the usage block promises a flag the code does not implement.
* *tool vs repo convention*: `encode_text.py`'s docstring and code agreed with
  each other (both said `selftest`) yet still failed the repo-wide audit, which
  invokes `--selftest` everywhere. Internal consistency is not enough; the
  `--selftest` spelling is a cross-tool contract and is checked separately.

For the docs-vs-code half it compares, statically, for every tool:

* **Documented flags** -- every `--flag` that appears in a `Usage`/`用法` block
  or in a `python … tools/X.py …` example inside the module docstring.
* **Implemented flags** -- every string literal passed to `add_argument(...)`,
  plus every literal compared against `sys.argv[...]` (this repo has ~65 tools
  with no argparse at all, which dispatch on `argv[1]`).

A documented flag with no implementation is reported MISSING; that is the
`encode_text` shape. The reverse (implemented but undocumented) is reported as
INFO only -- plenty of tools have internal flags that are deliberately not in
the usage block.

Nothing is executed. This is a static reader, so it is safe to run against tools
that would otherwise launch emulators or overwrite files.

Usage
-----
    python tools/verify_docs_match_cli.py
    python tools/verify_docs_match_cli.py --show-info
    python tools/verify_docs_match_cli.py --selftest
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TOOLS = Path(__file__).resolve().parent
FLAG = re.compile(r"(?<![\w-])(--[a-zA-Z][\w-]*)")


def documented_flags(doc: str) -> set[str]:
    """Flags that the module docstring tells a reader to type.

    Only lines that look like an invocation count. A flag mentioned in prose
    ("--selftest is fault injection") is not a usage claim, and treating it as
    one produced false positives on the first version of this checker.
    """
    out: set[str] = set()
    for line in doc.splitlines():
        s = line.strip()
        if not s:
            continue
        looks_like_cmd = (s.startswith(("python", "python3", "bash", "$")) or
                          re.match(r"^tools/\S+\.(py|sh)\b", s))
        if looks_like_cmd:
            out |= set(FLAG.findall(s))
    return out


def implemented_flags(tree: ast.AST) -> set[str]:
    """Flags the code can actually act on: argparse options, plus literals the
    module compares `sys.argv` against (the no-argparse dispatch style)."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = getattr(node.func, "attr", None)
            if fn in ("add_argument", "add_parser"):
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        out.add(a.value)
        elif isinstance(node, ast.Compare):
            for side in [node.left, *node.comparators]:
                if isinstance(side, ast.Constant) and isinstance(side.value, str):
                    out.add(side.value)
                elif isinstance(side, (ast.List, ast.Tuple)):
                    for e in side.elts:
                        if isinstance(e, ast.Constant) and isinstance(e.value, str):
                            out.add(e.value)
    return out


def check(path: Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"tool": path.name, "verdict": "SYNTAX", "detail": str(e)[:80]}
    doc = ast.get_docstring(tree) or ""
    if not doc.strip():
        return {"tool": path.name, "verdict": "NO_DOC"}
    d, i = documented_flags(doc), implemented_flags(tree)
    missing = sorted(d - i)
    return {"tool": path.name, "verdict": "MISSING" if missing else "OK",
            "documented": sorted(d), "missing": missing,
            "undocumented": sorted(f for f in i if f.startswith("--") and f not in d)}


def _encodable(c: str, enc: str) -> bool:
    """`c` 能否以 `enc` 編碼。2026-09-11 從 console_encoding_risks 的巢狀函式抽出:
    巢狀時 selftest 打不到它,`return True` 改成 False(每個字元都判成編不出)逃掉。"""
    try:
        c.encode(enc)
        return True
    except Exception:                                             # noqa: BLE001
        return False


def console_encoding_risks() -> list[tuple[str, str]]:
    """Tools that print characters the local console cannot encode.

    2026-09-08: `safe_output.py` and `dump_exe_tables.py` were both **entirely
    unusable** on this machine because they print `✓`/`✗`/`⚠` and the default
    console codepage here is cp950, which has no U+2713. The first such `print`
    raises `UnicodeEncodeError`, so the tool dies part-way and looks broken for
    an unrelated reason — `dump_exe_tables.py`'s own "自驗結果" block had never
    once executed. A sweep found 13 tools in this state.

    The repo-wide fix is `sys.stdout.reconfigure(encoding="utf-8")`, so the check
    is: does the file contain a symbol the console codepage lacks *without*
    reconfiguring? Detection uses the live `locale.getpreferredencoding()` rather
    than hardcoding cp950, so it stays meaningful on a UTF-8 machine (where it
    correctly reports nothing).

    **Known blind spot**: a tool that writes the symbol as an escape
    (`print("\u2713")`) carries no such character in its source, so this scan
    misses it while the runtime crash is identical. Found while writing this
    check's own positive control, which failed for exactly that reason. Every
    tool in this repo writes the literal character, so the scan is adequate
    today -- but a clean run is not proof of absence for escape-written output.
    """
    import locale
    enc = locale.getpreferredencoding(False) or "utf-8"
    probe = "✓✗✔✘→←↑↓─│┌┐└┘█▓░●○★☆⚠✅❌"

    def encodable(c: str) -> bool:
        return _encodable(c, enc)

    risky = {c for c in probe if not encodable(c)}
    out = []
    if not risky:
        return out
    for p in sorted(TOOLS.glob("*.py")):
        if p.name.startswith("_"):
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        used = "".join(sorted({c for c in risky if c in src}))
        if used and "reconfigure(encoding" not in src:
            out.append((p.name, f"輸出含主控台({enc})編不出的符號 {used},且未設 stdout 編碼"))
    return out


def convention_violations() -> list[tuple[str, str]]:
    """Cross-tool contract: if a tool has a selftest at all, `--selftest` must
    reach it. `tools/verify_all_tools.py` invokes exactly that spelling on every
    tool, so a tool that only answers to a positional `selftest` is reported as
    FAIL by the repo-wide audit for a reason that has nothing to do with its
    behaviour -- which is what happened to `encode_text.py` on 2026-09-08.

    The rule mirrors the audit's own selection logic rather than demanding one
    spelling. `verify_all_tools.py` picks the positional `selftest` when it sees
    an `add_parser("selftest")` and no literal `--selftest` in the file; a
    subcommand-style tool is therefore fine. The first version of this check
    ignored that and flagged `fd2_audio_probe.py`, which the audit invokes
    correctly -- a false positive found by checking the complaint instead of
    trusting it. What actually breaks is the narrow case below: the text
    `--selftest` appears somewhere in the file (so the audit chooses that
    spelling) while nothing implements it.
    """
    out = []
    for p in sorted(TOOLS.glob("*.py")):
        if p.name.startswith("_"):
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        impl = implemented_flags(tree)
        has_sub = re.search(r"add_parser\(\s*[\"']selftest", src) is not None
        audit_uses = "selftest" if (has_sub and "--selftest" not in src) else "--selftest"
        if audit_uses == "--selftest" and "--selftest" in src and "--selftest" not in impl:
            out.append((p.name, "檔案裡有 --selftest 字樣(稽核會用它)但沒有實作"))
    return out


def selftest() -> int:
    """Positive and negative controls, written to disk and read back, so the
    checker is exercised through its real entry point rather than in-process."""
    fails = []
    tmp = TOOLS / "_docscli_probe.py"
    try:
        print("(1) 正向控制:文件寫了一個程式碼沒有的旗標 → 必須報 MISSING")
        tmp.write_text('"""t\n\nUsage\n-----\n    python tools/x.py --ghost\n"""\n'
                       'import argparse\n'
                       'argparse.ArgumentParser().add_argument("--real")\n', encoding="utf-8")
        r = check(tmp)
        ok1 = r["verdict"] == "MISSING" and r["missing"] == ["--ghost"]
        print(f"    {'PASS' if ok1 else 'FAIL'}: {r}")
        if not ok1:
            fails.append("未能抓到文件有、程式碼沒有的旗標")

        print("\n(2) 負向控制:文件與程式碼一致 → 必須報 OK")
        tmp.write_text('"""t\n\nUsage\n-----\n    python tools/x.py --real\n"""\n'
                       'import argparse\n'
                       'argparse.ArgumentParser().add_argument("--real")\n', encoding="utf-8")
        r = check(tmp)
        ok2 = r["verdict"] == "OK"
        print(f"    {'PASS' if ok2 else 'FAIL'}: {r}")
        if not ok2:
            fails.append("一致的情況被誤報")

        print("\n(3) 散文中提到的旗標不算使用宣告(第一版的誤報來源)")
        tmp.write_text('"""t\n\n--ghost is discussed here but never offered.\n\n'
                       'Usage\n-----\n    python tools/x.py --real\n"""\n'
                       'import argparse\n'
                       'argparse.ArgumentParser().add_argument("--real")\n', encoding="utf-8")
        r = check(tmp)
        ok3 = r["verdict"] == "OK"
        print(f"    {'PASS' if ok3 else 'FAIL'}: {r}")
        if not ok3:
            fails.append("把散文提及誤當成使用宣告")

        print("\n(4) 無 argparse 的 argv 分派工具也要算數")
        tmp.write_text('"""t\n\nUsage\n-----\n    python tools/x.py selftest\n"""\n'
                       'import sys\n'
                       'if sys.argv[1] == "selftest":\n    pass\n', encoding="utf-8")
        r = check(tmp)
        ok4 = r["verdict"] == "OK"
        print(f"    {'PASS' if ok4 else 'FAIL'}: {r}")
        if not ok4:
            fails.append("argv 分派式工具被誤報")

        print("\n(5) 主控台編碼檢查:必須抓到「用了編不出的符號卻沒設 stdout 編碼」")
        import locale
        enc = locale.getpreferredencoding(False) or "utf-8"
        try:
            "✓".encode(enc)
            applicable = False
        except Exception:
            applicable = True
        if not applicable:
            # 在 UTF-8 主控台上這個檢查本來就不該報任何東西,強行斷言會是假通過。
            print(f"    SKIP: 本機主控台是 {enc},編得出 ✓,此檢查在此環境不適用")
        else:
            # 兩個坑,兩個都是這個正向控制自己踩出來的:
            # (1) 探針檔名不能以 `_` 開頭 —— `console_encoding_risks()` 會跳過那些,
            #     用 tmp(_docscli_probe.py)當探針時它永遠抓不到。
            # (2) 探針內容必須放**真的字元**。寫成 "\\u2713" 只是把跳脫序列的字面
            #     文字寫進檔案,原始碼裡並沒有該字元,掃描自然掃不到。
            enc_probe = TOOLS / "zz_encoding_probe.py"
            enc_probe.write_text('"""t"""\nprint("✓ ok")\n', encoding="utf-8")
            ok5 = enc_probe.name in [t for t, _ in console_encoding_risks()]
            print(f"    {'PASS' if ok5 else 'FAIL'}: 明確違規檔被抓到={ok5}")
            if not ok5:
                fails.append("主控台編碼檢查抓不到明確的違規檔")
            # 負向控制:同一個檔案補上 reconfigure 後就不該再被抓,
            # 否則這個檢查等於「只要出現該符號就報」,對已修好的檔案會永遠誤報。
            enc_probe.write_text('"""t"""\nimport sys\n'
                                 'sys.stdout.reconfigure(encoding="utf-8")\n'
                                 'print("✓ ok")\n', encoding="utf-8")
            ok5b = enc_probe.name not in [t for t, _ in console_encoding_risks()]
            print(f"    {'PASS' if ok5b else 'FAIL'}: 已修好的檔案不再被抓={ok5b}")
            if not ok5b:
                fails.append("主控台編碼檢查對已修好的檔案仍誤報")
    finally:
        tmp.unlink(missing_ok=True)
        (TOOLS / "zz_encoding_probe.py").unlink(missing_ok=True)

    print("\n(6) _encodable 兩側:cp950 編得出 'a'、編不出 '✓'")
    # 2026-09-11 窮舉突變測試:巢狀的 encodable 打不到,`return True` 改 False 逃掉。
    ok6 = _encodable("a", "cp950") and not _encodable("✓", "cp950")
    print(f"    {'PASS' if ok6 else 'FAIL'}: 'a'={_encodable('a', 'cp950')}、'✓'={_encodable('✓', 'cp950')}")
    if not ok6:
        fails.append("_encodable 判斷不對")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(2 正向 + 3 負向;正向含編碼檢查的違規探針)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show-info", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    rows = [check(p) for p in sorted(TOOLS.glob("*.py")) if not p.name.startswith("_")]
    bad = [r for r in rows if r["verdict"] == "MISSING"]
    conv = convention_violations()
    for t, why in conv:
        print(f"  CONVENTION {t:<38} {why}")
    enc = console_encoding_risks()
    for t, why in enc:
        print(f"  ENCODING   {t:<38} {why}")
    for r in bad:
        print(f"  MISSING  {r['tool']:<40} 文件寫了但程式碼沒有:{r['missing']}")
    if a.show_info:
        for r in rows:
            if r["verdict"] == "OK" and r.get("undocumented"):
                print(f"  info     {r['tool']:<40} 有但未寫進用法:{r['undocumented'][:6]}")
    n_ok = sum(1 for r in rows if r["verdict"] == "OK")
    n_nodoc = sum(1 for r in rows if r["verdict"] == "NO_DOC")
    print(f"\n共 {len(rows)} 支:一致 {n_ok} / 文件旗標缺實作 {len(bad)} / 無 docstring {n_nodoc}")
    if conv:
        print(f"  另有 {len(conv)} 支違反 --selftest 拼法慣例")
    if enc:
        print(f"  另有 {len(enc)} 支有主控台編碼崩潰風險")
    return 1 if (bad or conv or enc) else 0


if __name__ == "__main__":
    raise SystemExit(main())
