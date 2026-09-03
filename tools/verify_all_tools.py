#!/usr/bin/env python3
"""verify_all_tools.py — repo-wide verification harness for everything in tools/.

WHY THIS EXISTS
---------------
This repo has ~100 tools accumulated across many sessions. Several verification
failures in this project's history were *silent*: a tool with a SyntaxError
produces no output at all, which looks exactly like "that tool was never run"
(see memory `a-script-that-cannot-run-is-invisible`). A tool whose hardcoded
input path no longer exists fails the same way. This harness makes the whole
tool surface answer for itself, in layers, and prints one verdict table.

LAYERS (each independently selectable with --layer)
--------------------------------------------------
  syntax     Every .py parses (ast.parse); every .sh passes `bash -n`.
             Cheapest and catches the "invisible tool" failure mode.
  structure  Static safety analysis, no execution:
               * does the module guard its work behind `if __name__ == "__main__"`?
               * if not, what module-level statements would run on import?
               * shebang / executable-bit consistency.
             The import layer *depends* on this: a module classified
             NOT_IMPORT_SAFE is deliberately NOT imported, because importing it
             would run real work (write files, launch emulators).
  imports    Import every IMPORT_SAFE module in a subprocess, in a throwaway
             cwd, with a timeout. Separates MISSING_DEP (an optional third-party
             package) from a genuine error, because those mean different things.
  deps       For a NOT_IMPORT_SAFE module, the next best thing: resolve every
             module it imports at top level, without running it.
  cli        `--help` for every tool that uses argparse. Non-argparse tools are
             NOT probed — for them `--help` is just an unrecognised argv[1] and
             many would start doing real work.
  invoke     …so the non-argparse tools get covered here instead: run each one
             with no arguments from an empty directory. Printing usage is
             healthy; a traceback that is not a missing-input error is a defect.
             Also fingerprints the worktree around every run, because a tool
             that builds paths from __file__ ignores the empty cwd entirely.
  env        Which of the two interpreters this repo uses (Windows Python, WSL
             python3) can actually satisfy each tool's third-party imports.
  refs       Every filesystem path literal in a tool is checked for existence,
             separating paths the tool *opens* (a hard failure when the tree is
             gone) from paths it merely mentions. This is what catches tools
             orphaned by the `remake/` removal.
  tests      Run every tools/test_*.py.
  selftest   Run every tool advertising a --selftest mode.

REVERSE VERIFICATION
--------------------
`--selftest` builds a throwaway tool directory containing deliberately broken
fixtures and requires this harness to *fail on them*, plus a known-good fixture
as a positive control in the identical configuration. A harness that only ever
says PASS is worthless; these fixtures prove it can say FAIL, and prove which
specific fault each layer detects. The NOT_IMPORT_SAFE fixture additionally
writes a sentinel file when executed, and the selftest asserts that sentinel was
never created — i.e. it proves the harness really did decline to import it,
rather than importing it and happening to survive.

USAGE
-----
    python tools/verify_all_tools.py                     # all layers
    python tools/verify_all_tools.py --layer syntax,refs
    python tools/verify_all_tools.py --json report.json
    python tools/verify_all_tools.py --selftest          # verify the harness
    python tools/verify_all_tools.py --only fd2save      # substring filter
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"

# This harness quotes the probed tools' own output, which is Chinese and often
# contains U+FFFD after a lossy decode. On a cp950 Windows console that kills
# the report *after* the work is done — the same class of failure this harness
# exists to find, so it must not be subject to it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError):
        pass

ALL_LAYERS = ["syntax", "structure", "imports", "deps", "cli", "invoke", "env", "refs", "tests", "selftest"]

# Tools that must never be executed by this harness: they launch emulators,
# spawn long-running background processes, or mutate the real game directory.
# They are still covered by syntax/structure/refs; only execution is withheld.
NO_EXEC = {
    "dosbox_harness.sh",
    "dosbox_exec_trace.sh",
    "fd2_dosbox_live_helper.sh",
    "fd2_live_input_helper.sh",
    "fd2_chapter_sweep.py",
    "c29_teleport_driver.py",
    "c29_teleport_driver2.py",
    "export_fm.sh",
    "export_mt32.sh",
    "export_music_ogg.sh",
    "extract_fd2_video_frame.sh",
}

# Files that are plugin scripts for an external host (IDA/Ghidra), not runnable
# standalone: they import a host-provided module that does not exist here.
HOST_PLUGINS = re.compile(r"^(ida_|ghidra_).*")

# Path literals that are legitimately absent (outputs, user machines, examples).
REF_IGNORE = re.compile(
    r"""(^/tmp/|^/dev/|^/proc/|^/home/|^/root/|^/mnt/|^/usr/|^/etc/|^/var/
        |^[A-Za-z]:[\\/]|^~|^\.wsl_build|^out/|^output|^build/|\{|\}|\*|\?)""",
    re.X,
)


# --------------------------------------------------------------------------- #
# result model
# --------------------------------------------------------------------------- #

@dataclass
class Check:
    tool: str
    layer: str
    status: str          # PASS | FAIL | SKIP | WARN
    detail: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, tool: str, layer: str, status: str, detail: str = "") -> None:
        self.checks.append(Check(tool, layer, status, detail))

    def by_status(self, status: str) -> list[Check]:
        return [c for c in self.checks if c.status == status]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.checks:
            out[c.status] = out.get(c.status, 0) + 1
        return out


def _child_env() -> dict[str, str]:
    """Environment for probed tools.

    PYTHONIOENCODING is forced to UTF-8 because this repo's tools print Chinese
    and ✓/✗ to stdout. On a Windows console (cp950) that raises
    UnicodeEncodeError *inside the tool*, which would be reported here as a
    broken tool when the tool is fine — it is the console that cannot represent
    the output. Measured on this repo: without it, tools/dump_exe_tables.py dies
    with UnicodeEncodeError on the very first line it prints, while under WSL
    the same invocation completes and passes its own numeric self-check.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(argv: list[str], timeout: int, cwd: Path | None = None,
         stdin_bytes: bytes | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run a command, never raise. Returns (rc, stdout, stderr).

    rc == -9 means the timeout fired; callers must distinguish that from a
    normal non-zero exit, because "hung" and "reported an error" are different
    findings.

    stdin is deliberately *bytes*, and the whole call then runs in binary mode:
    Python's text-mode stdin on Windows rewrites "\\n" to "\\r\\n", which would
    hand bash a CRLF script and make every shell tool fail with a bogus
    `syntax error near unexpected token $'{\\r'`. That exact false failure
    happened here before this was made binary.
    """
    try:
        cp = subprocess.run(
            argv, capture_output=True, text=stdin_bytes is None, timeout=timeout,
            cwd=str(cwd) if cwd else None,
            errors="replace" if stdin_bytes is None else None,
            input=stdin_bytes, env=env,
        )
        if stdin_bytes is not None:
            return (cp.returncode,
                    (cp.stdout or b"").decode("utf-8", "replace"),
                    (cp.stderr or b"").decode("utf-8", "replace"))
        return cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return -9, "", f"timed out after {timeout}s"
    except OSError as e:  # missing interpreter, permission, ...
        return -1, "", f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------- #
# layer: syntax
# --------------------------------------------------------------------------- #

def layer_syntax(rep: Report, pys: list[Path], shs: list[Path]) -> None:
    for p in pys:
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
            rep.add(p.name, "syntax", "PASS")
        except SyntaxError as e:
            rep.add(p.name, "syntax", "FAIL", f"line {e.lineno}: {e.msg}")
    for p in shs:
        raw = p.read_bytes()
        # Explicit CRLF check, independent of which bash we happen to resolve.
        # Git Bash accepts a CRLF script opened by PATH but real Linux bash does
        # not, so relying on `bash -n` alone gives a different verdict depending
        # on the host — and the host that matters is WSL, where these run.
        # Six scripts in this repo were CRLF and unrunnable under Linux while a
        # Git-Bash `bash -n` sweep reported all of them clean.
        if b"\r\n" in raw:
            rep.add(p.name, "syntax", "FAIL",
                    f"CRLF line endings ({raw.count(chr(13).encode() + chr(10).encode())} lines) "
                    "— Linux bash cannot run this")
            continue
        # Feed the script on stdin rather than by path: this harness runs under
        # Windows Python, where str(path) is a backslash path that bash cannot
        # open. The selftest's good.sh positive control is what caught that.
        rc, _, err = _run(["bash", "-n"], timeout=30, stdin_bytes=raw)
        if rc == 0:
            rep.add(p.name, "syntax", "PASS")
        else:
            rep.add(p.name, "syntax", "FAIL", err.strip().splitlines()[0] if err.strip() else f"rc={rc}")


# --------------------------------------------------------------------------- #
# layer: structure  (static; decides what the imports layer is allowed to touch)
# --------------------------------------------------------------------------- #

_SAFE_MODULE_LEVEL = (
    ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
    ast.ClassDef, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr,
    ast.If, ast.Try, ast.Pass,
)


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    t = node.test
    if not isinstance(t, ast.Compare) or len(t.comparators) != 1:
        return False
    left, right = t.left, t.comparators[0]
    return (
        isinstance(left, ast.Name) and left.id == "__name__"
        and isinstance(right, ast.Constant) and right.value == "__main__"
    )


def analyse_structure(path: Path) -> tuple[str, str]:
    """Return (verdict, detail). verdict in IMPORT_SAFE / NOT_IMPORT_SAFE / UNPARSEABLE."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError as e:
        return "UNPARSEABLE", f"line {e.lineno}: {e.msg}"

    has_guard = any(_is_main_guard(n) for n in tree.body)
    risky: list[str] = []
    for n in tree.body:
        if _is_main_guard(n):
            continue
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef, ast.AnnAssign, ast.Pass)):
            continue
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            continue  # docstring
        if isinstance(n, ast.Assign):
            # A plain constant/collection assignment is inert; a call is not.
            if not any(isinstance(x, ast.Call) for x in ast.walk(n.value)):
                continue
            # Common inert calls used to build module constants.
            calls = [x for x in ast.walk(n.value) if isinstance(x, ast.Call)]
            names = {
                (x.func.attr if isinstance(x.func, ast.Attribute)
                 else x.func.id if isinstance(x.func, ast.Name) else "?")
                for x in calls
            }
            if names <= {"Path", "resolve", "parent", "compile", "dict", "set", "list",
                         "tuple", "frozenset", "range", "len", "sorted", "getenv",
                         "environ", "get", "join", "dirname", "abspath", "namedtuple",
                         "bytes", "str", "int", "float", "sub", "split", "strip"}:
                continue
            risky.append(f"line {n.lineno}: module-level call in assignment")
            continue
        if isinstance(n, (ast.If, ast.Try)):
            # A module-level try/except around imports is the usual optional-dep
            # pattern; only flag if it contains a call statement.
            if any(isinstance(x, ast.Expr) and isinstance(x.value, ast.Call)
                   for x in ast.walk(n)):
                risky.append(f"line {n.lineno}: conditional module-level call")
            continue
        risky.append(f"line {getattr(n, 'lineno', '?')}: {type(n).__name__} at module level")

    if not risky:
        return "IMPORT_SAFE", "guarded" if has_guard else "no work at module level"
    return "NOT_IMPORT_SAFE", "; ".join(risky[:3]) + (f" (+{len(risky)-3} more)" if len(risky) > 3 else "")


def layer_structure(rep: Report, pys: list[Path]) -> dict[str, str]:
    verdicts: dict[str, str] = {}
    for p in pys:
        raw = p.read_bytes()
        # A shebang line ending in CR is not a shebang: Linux reports
        # `env: 'python3<CR>': No such file or directory` and the tool cannot
        # be run directly at all, even though `python3 tools/x.py` still works
        # and every syntax check passes. 56 of this repo's 82 shebanged tools
        # were in that state until 2026-09-03. Checked here rather than in
        # `syntax` because the file is perfectly valid Python either way.
        first_line = raw.split(b"\n", 1)[0]
        if raw.startswith(b"#!") and first_line.endswith(b"\r"):
            rep.add(p.name, "structure", "FAIL",
                    "shebang line ends with CR — cannot be executed directly under Linux")
            verdicts[p.name] = "UNPARSEABLE"
            continue
        v, detail = analyse_structure(p)
        verdicts[p.name] = v
        if v == "IMPORT_SAFE":
            rep.add(p.name, "structure", "PASS", detail)
        elif v == "UNPARSEABLE":
            rep.add(p.name, "structure", "FAIL", detail)
        else:
            rep.add(p.name, "structure", "WARN", f"runs work on import — {detail}")
    return verdicts


# --------------------------------------------------------------------------- #
# layer: imports
# --------------------------------------------------------------------------- #

_IMPORT_SNIPPET = textwrap.dedent(
    """
    import importlib.util, os, sys, traceback
    # Put the script's own directory on sys.path, exactly as running
    # `python tools/foo.py` would. Without this, every tool that imports a
    # sibling module in tools/ reports a bogus MISSING_DEP.
    sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[1])))
    spec = importlib.util.spec_from_file_location("_probe_mod", sys.argv[1])
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except ModuleNotFoundError as e:
        print("MISSING_DEP:" + (e.name or str(e)))
        sys.exit(3)
    except SystemExit as e:
        print("SYSTEM_EXIT:" + str(e.code))
        sys.exit(4)
    except BaseException:
        traceback.print_exc()
        sys.exit(5)
    print("OK")
    """
)


_DEPS_SNIPPET = textwrap.dedent(
    """
    import importlib.util, json, os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[1])))
    bad = []
    for name in json.loads(sys.argv[2]):
        try:
            if importlib.util.find_spec(name) is None:
                bad.append(name)
        except BaseException as e:
            bad.append(f"{name} ({type(e).__name__})")
    print(json.dumps(bad))
    """
)


def _top_level_imports(path: Path) -> list[str]:
    """Module names imported at module level, without executing anything."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    names: list[str] = []
    for n in tree.body:
        if isinstance(n, ast.Import):
            names += [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            names.append(n.module.split(".")[0])
    return sorted(set(names))


def layer_imports(rep: Report, pys: list[Path], verdicts: dict[str, str], tmp: Path) -> None:
    snippet = tmp / "_import_probe.py"
    snippet.write_text(_IMPORT_SNIPPET, encoding="utf-8")
    deps_snippet = tmp / "_deps_probe.py"
    deps_snippet.write_text(_DEPS_SNIPPET, encoding="utf-8")
    sandbox = tmp / "sandbox"
    sandbox.mkdir(exist_ok=True)
    for p in pys:
        if verdicts.get(p.name) != "IMPORT_SAFE":
            # Executing it would do real work, so verify the next best thing:
            # that every module it imports at module level actually resolves.
            # A tool whose dependency vanished is otherwise invisible until the
            # day someone runs it.
            rep.add(p.name, "imports", "SKIP", "not import-safe (see structure layer)")
            if HOST_PLUGINS.match(p.name):
                rep.add(p.name, "deps", "SKIP",
                        "external-host plugin — idaapi/ghidra modules exist only inside the host")
                continue
            deps = _top_level_imports(p)
            if not deps:
                rep.add(p.name, "deps", "SKIP", "no top-level imports")
                continue
            rc, out, err = _run([sys.executable, str(deps_snippet), str(p), json.dumps(deps)],
                                timeout=60, cwd=sandbox, env=_child_env())
            if rc != 0:
                rep.add(p.name, "deps", "FAIL", f"dependency probe failed: {err.strip()[:120]}")
                continue
            try:
                bad = json.loads(out.strip() or "[]")
            except json.JSONDecodeError:
                rep.add(p.name, "deps", "FAIL", f"dependency probe output unparseable: {out[:80]!r}")
                continue
            if bad:
                rep.add(p.name, "deps", "FAIL", f"unresolved: {', '.join(bad)}")
            else:
                rep.add(p.name, "deps", "PASS", f"all {len(deps)} module-level deps resolve")
            continue
        if HOST_PLUGINS.match(p.name):
            rep.add(p.name, "imports", "SKIP", "external-host plugin (IDA/Ghidra)")
            continue
        rc, out, err = _run([sys.executable, str(snippet), str(p)], timeout=60, cwd=sandbox, env=_child_env())
        if rc == 0:
            rep.add(p.name, "imports", "PASS")
        elif rc == 3:
            rep.add(p.name, "imports", "WARN", out.strip())
        elif rc == -9:
            rep.add(p.name, "imports", "FAIL", "hung on import")
        else:
            last = [l for l in (err or out).strip().splitlines() if l.strip()]
            rep.add(p.name, "imports", "FAIL", last[-1] if last else f"rc={rc}")


# --------------------------------------------------------------------------- #
# layer: cli
# --------------------------------------------------------------------------- #

def layer_cli(rep: Report, pys: list[Path], tmp: Path) -> None:
    sandbox = tmp / "sandbox"
    sandbox.mkdir(exist_ok=True)
    for p in pys:
        src = p.read_text(encoding="utf-8", errors="replace")
        if "argparse" not in src:
            rep.add(p.name, "cli", "SKIP", "no argparse — --help would be a real argv")
            continue
        if p.name in NO_EXEC:
            rep.add(p.name, "cli", "SKIP", "on the no-exec list")
            continue
        rc, out, err = _run([sys.executable, str(p), "--help"], timeout=60, cwd=sandbox, env=_child_env())
        if rc == -9:
            rep.add(p.name, "cli", "FAIL", "--help hung")
        elif rc == 0 and ("usage" in out.lower() or "usage" in err.lower()):
            rep.add(p.name, "cli", "PASS")
        elif rc == 0:
            rep.add(p.name, "cli", "WARN", "exit 0 but printed no usage text")
        else:
            last = [l for l in (err or out).strip().splitlines() if l.strip()]
            rep.add(p.name, "cli", "FAIL", f"rc={rc}: {last[-1] if last else ''}")


# --------------------------------------------------------------------------- #
# layer: invoke
# --------------------------------------------------------------------------- #

_USAGE_HINT = re.compile(r"(usage|用法|Usage|USAGE)", re.I)


def _worktree_state() -> list[str]:
    """`git status --porcelain` lines, or [] when git is unavailable.

    Used as a before/after fingerprint around each probed tool. Includes
    untracked files, which is what caught a tool recreating a deleted tree.

    Limitation, stated rather than papered over: gitignored output trees
    (extracted/, org_game/) do not show up here, so a tool writing its normal
    output there is invisible to this check — which is the intent. What it
    catches is a tool writing somewhere it should not, e.g. resurrecting a
    removed source tree.
    """
    rc, out, _ = _run(["git", "-C", str(REPO), "status", "--porcelain"], timeout=120)
    return sorted(out.splitlines()) if rc == 0 else []


def layer_invoke(rep: Report, pys: list[Path], tmp: Path,
                 state_fn=None) -> None:
    """Run every non-argparse tool with no arguments, in an empty directory.

    These 60-odd tools take positional sys.argv and so cannot be probed with
    --help (the cli layer skips them), which left the largest group in the repo
    with no execution coverage at all. Running them argument-less from a
    scratch cwd is safe: their inputs are relative paths like
    `org_game/.../FD2.EXE` and `extracted/`, none of which exist there, so a
    tool that ignores its own usage check fails immediately on a missing file
    instead of touching anything real.

    A tool that prints usage and exits is healthy. A traceback is a defect: it
    means the tool's front door is broken before it ever reads an argument.
    """
    sandbox = tmp / "invoke_sandbox"
    sandbox.mkdir(exist_ok=True)
    state_fn = state_fn or _worktree_state
    baseline = state_fn()
    for p in pys:
        src = p.read_text(encoding="utf-8", errors="replace")
        if "argparse" in src or p.name.startswith("test_") or p.name in NO_EXEC:
            continue
        if HOST_PLUGINS.match(p.name):
            rep.add(p.name, "invoke", "SKIP", "external-host plugin")
            continue
        rc, out, err = _run([sys.executable, str(p)], timeout=120, cwd=sandbox,
                            env=_child_env())
        # An empty cwd does NOT sandbox a tool that builds its paths from
        # __file__ — those write into the repo wherever they are run from.
        # tools/export_sfx.py did exactly that during this layer's first run and
        # recreated part of the deleted remake/ tree. Attribute any worktree
        # change to the tool that was just run, and say so.
        after = state_fn()
        touched = sorted(set(after) - set(baseline))
        if touched:
            baseline = after
        # 記成旗標而不是另開一筆:同一個 (tool, layer) 出現兩列時,後寫的那列會
        # 蓋掉前一列,於是「逃出 cwd」這個警告在工具其他方面通過的那一刻就消失了。
        escaped = (f";而且寫到 cwd 之外:{', '.join(touched[:4])}" if touched else "")

        def verdict(status, detail):
            rep.add(p.name, "invoke", "WARN" if touched else status, detail + escaped)

        blob = out + err
        if rc == -9:
            verdict("FAIL", "hung with no arguments")
        elif "Traceback (most recent call last)" in blob:
            last = [l for l in blob.strip().splitlines() if l.strip()]
            tail = last[-1] if last else ""
            # A missing-input error in an empty cwd only proves the tool has no
            # usage guard — it says nothing about whether the tool works when
            # given its real inputs, and calling that a failure would be a false
            # positive against every tool that must run from the repo root.
            # Any other exception type is a genuine front-door defect.
            if re.search(r"(FileNotFoundError|IsADirectoryError|NotADirectoryError)", tail):
                verdict("WARN", "no usage guard: crashes on a missing input instead of printing usage")
            else:
                verdict("FAIL", f"traceback: {tail[:140]}")
        elif _USAGE_HINT.search(blob):
            verdict("PASS", "prints usage")
        elif rc != 0:
            last = [l for l in blob.strip().splitlines() if l.strip()]
            verdict("PASS", f"exits {rc}: {last[-1][:100] if last else 'no output'}")
        elif blob.strip():
            # Exit 0 with real output and no usage banner: a tool whose documented
            # default is to just do its job (tools/export_sfx.py extracts the UI SFX
            # pool with no arguments). Reporting that as "no error" was misleading —
            # it printed 17 lines of results.
            last = [l for l in blob.strip().splitlines() if l.strip()]
            verdict("PASS", f"ran with no args: {last[-1][:100]}")
        else:
            # Exit 0 and *silent*. This is the real defect shape, and the reason the
            # check exists: char_summary.py used to build a sheet with nothing on it
            # and save it without printing a single line, so success and doing
            # nothing were indistinguishable.
            verdict("WARN", "exit 0 with no output at all — cannot tell success from doing nothing")


# --------------------------------------------------------------------------- #
# layer: env  (which interpreter can actually run which tool)
# --------------------------------------------------------------------------- #

def layer_env(rep: Report, pys: list[Path], tmp: Path) -> None:
    """Report third-party deps per tool against BOTH interpreters this repo uses.

    Half the toolchain runs under Windows Python (Pillow/numpy/capstone/torch
    live there) and half under WSL (where the DOSBox-X harness lives). Measured
    2026-09-03: the WSL python3 has *none* of the four, so `python3 tools/x.py`
    on a Pillow tool fails with ModuleNotFoundError — which reads as a broken
    tool but is a wrong-interpreter error. This layer names which is which.
    """
    stdlib = set(sys.stdlib_module_names)
    local = {p.stem for p in pys}
    probe = tmp / "_avail.py"
    probe.write_text(
        "import importlib.util, json, sys\n"
        "print(json.dumps({m: importlib.util.find_spec(m) is not None "
        "for m in json.loads(sys.argv[1])}))\n",
        encoding="utf-8",
    )

    wanted: dict[str, list[str]] = {}
    for p in pys:
        ext = sorted({m for m in _all_imports(p)
                      if m not in stdlib and m not in local and not m.startswith("_")})
        if ext:
            wanted[p.name] = ext
    every = sorted({m for v in wanted.values() for m in v})
    if not every:
        return

    def availability(argv_prefix: list[str], cwd: Path | None) -> dict[str, bool]:
        rc, out, _ = _run(argv_prefix + [json.dumps(every)], timeout=180, cwd=cwd)
        try:
            return json.loads(out.strip().splitlines()[-1]) if rc == 0 and out.strip() else {}
        except (json.JSONDecodeError, IndexError):
            return {}

    win = availability([sys.executable, str(probe)], None)
    wsl_probe = "/tmp/_fd2_avail_probe.py"
    _run(["wsl.exe", "-e", "bash", "-lc",
          f"cat > {wsl_probe}"], timeout=60, stdin_bytes=probe.read_bytes())
    rc, out, _ = _run(["wsl.exe", "-e", "bash", "-lc",
                       f"python3 {wsl_probe} '{json.dumps(every)}'"], timeout=180)
    try:
        wsl = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except (json.JSONDecodeError, IndexError):
        wsl = {}

    for name, mods in sorted(wanted.items()):
        if HOST_PLUGINS.match(name):
            rep.add(name, "env", "SKIP", f"runs inside IDA/Ghidra ({', '.join(mods)})")
            continue
        miss_win = [m for m in mods if not win.get(m, False)]
        miss_wsl = [m for m in mods if not wsl.get(m, False)] if wsl else None
        if not miss_win and miss_wsl:
            rep.add(name, "env", "WARN",
                    f"Windows-python only — WSL lacks {', '.join(miss_wsl)}")
        elif miss_win and miss_wsl is not None and not miss_wsl:
            rep.add(name, "env", "WARN",
                    f"WSL-python only — Windows lacks {', '.join(miss_win)}")
        elif miss_win:
            rep.add(name, "env", "FAIL",
                    f"runnable nowhere: missing {', '.join(sorted(set(miss_win) | set(miss_wsl or [])))}")
        else:
            rep.add(name, "env", "PASS", f"both interpreters have {', '.join(mods)}")


def _all_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            mods.add(n.module.split(".")[0])
    return mods


# --------------------------------------------------------------------------- #
# layer: refs
# --------------------------------------------------------------------------- #

_PATH_LIT = re.compile(r"""["']([A-Za-z0-9_./\\-]{4,}\.(?:py|sh|json|md|DAT|EXE|B24|bin|txt|csv|png))["']""")
# Directory literals too: `remake/assets/sprites` has no extension, so the
# file-suffix pattern above missed it entirely and apply_hd_assets.py's
# dependence on the removed tree went unreported until the invoke layer ran it.
#
# The first segment is pinned to an actual repo tree. An unanchored "word/word"
# pattern matched sed expressions ("s/instance"), colour pairs ("black/grey")
# and screen labels ("X19/X14") — five false FAILs, every one of them a string
# that merely contains a slash.
_REPO_TREES = (
    # present today
    "docs", "tools", "extracted", "org_game", "references", "docker",
    "FD2_ghidra_projects",
    # removed 2026-09-02 with remake/ — the whole point of this check
    "remake", "assets",
)
_DIR_LIT = re.compile(
    r"""["'](""" + "|".join(_REPO_TREES) + r""")((?:/[A-Za-z0-9_.-]+){1,6})/?["']"""
)

# Call names whose string arguments the tool will actually try to open. A path
# literal reaching one of these is a hard failure when the tree is gone; a
# literal that merely appears in a docstring, a --help example, or as a value
# the tool *writes into* generated output is not — conflating the two produced
# three false FAILs here (gen_campaign, test_gen_campaign, fd2_live_input_helper)
# alongside two true ones.
_OPENING_CALLS = {"open", "Path", "read_text", "read_bytes", "load", "loads",
                  "exists", "is_file", "glob", "rglob", "listdir", "add_argument"}


def _opened_literals(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = (node.func.attr if isinstance(node.func, ast.Attribute)
              else node.func.id if isinstance(node.func, ast.Name) else "")
        if fn not in _OPENING_CALLS:
            continue
        args = list(node.args)
        if fn == "add_argument":
            # only the default= value is a path the tool will open
            args = [kw.value for kw in node.keywords if kw.arg == "default"]
        for a in args:
            for sub in ast.walk(a):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.add(sub.value)
    return out


def layer_refs(rep: Report, files: list[Path], skip_self: bool = True) -> None:
    for p in files:
        # This file embeds deliberately-dangling path literals as selftest
        # fixtures, so scanning itself always reports a false positive.
        if skip_self and p.name == Path(__file__).name:
            rep.add(p.name, "refs", "SKIP", "self (contains fault-injection fixtures)")
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        opened = _opened_literals(p) if p.suffix == ".py" else set()
        missing: list[str] = []
        mentioned: list[str] = []
        seen: set[str] = set()
        lits = [m.group(1) for m in _PATH_LIT.finditer(src)]
        lits += [m.group(1) + m.group(2) for m in _DIR_LIT.finditer(src)]
        for lit in lits:
            if lit in seen:
                continue
            seen.add(lit)
            if REF_IGNORE.search(lit) or "/" not in lit and "\\" not in lit:
                continue
            norm = lit.replace("\\", "/")
            if (REPO / norm).exists() or (TOOLS / norm).exists():
                continue
            # A path under a directory that itself no longer exists is the
            # interesting case (the remake/ removal); anything else is likely an
            # output file the tool creates.
            top = norm.split("/", 1)[0]
            if not (REPO / top).exists():
                (missing if (lit in opened or p.suffix != ".py") else mentioned).append(lit)
        if missing:
            rep.add(p.name, "refs", "FAIL",
                    f"OPENS a path in a removed tree: {', '.join(sorted(missing)[:4])}")
        elif mentioned:
            rep.add(p.name, "refs", "WARN",
                    f"mentions a removed tree (docstring/output value, not opened): "
                    f"{', '.join(sorted(mentioned)[:3])}")
        else:
            rep.add(p.name, "refs", "PASS")


# --------------------------------------------------------------------------- #
# layer: tests
# --------------------------------------------------------------------------- #

def _wsl_repo_path() -> str | None:
    """REPO as WSL sees it, or None if this is not a Windows drive path."""
    s = str(REPO)
    if len(s) > 2 and s[1] == ":":
        return "/mnt/" + s[0].lower() + s[2:].replace("\\", "/")
    return None


def layer_tests_sh(rep: Report, shs: list[Path]) -> None:
    """Shell test suites, run under WSL — not Git Bash.

    tools/test_dosbox_harness_ports.sh exercises the harness's flock-based port
    reservation, and Git Bash ships no `flock`: under it the test reports a
    spurious "running instance did not hold its port" failure and then dies on
    `flock: command not found`. WSL is where the harness actually runs, so WSL
    is where its regression test is meaningful.
    """
    wsl_repo = _wsl_repo_path()
    for p in shs:
        if not p.name.startswith("test_"):
            continue
        if wsl_repo is None:
            rep.add(p.name, "tests", "SKIP", "no WSL path mapping for this repo")
            continue
        rc, out, err = _run(
            ["wsl.exe", "-e", "bash", "-lc",
             f"cd {wsl_repo} && bash tools/{p.name}"], timeout=1800)
        blob = (out + err).strip()
        tail = [l for l in blob.splitlines() if l.strip()]
        if rc == 0 and "failed: 0" in blob:
            rep.add(p.name, "tests", "PASS", tail[-1][:120] if tail else "")
        elif rc == -9:
            rep.add(p.name, "tests", "FAIL", "timed out")
        else:
            rep.add(p.name, "tests", "FAIL", f"rc={rc}: {tail[-1][:160] if tail else ''}")


def layer_tests(rep: Report, pys: list[Path]) -> None:
    for p in pys:
        if not p.name.startswith("test_"):
            continue
        rc, out, err = _run([sys.executable, str(p)], timeout=600, cwd=REPO, env=_child_env())
        blob = (out + err).strip()
        if rc == 0:
            tail = [l for l in blob.splitlines() if l.strip()]
            rep.add(p.name, "tests", "PASS", tail[-1][:120] if tail else "")
        elif rc == -9:
            rep.add(p.name, "tests", "FAIL", "timed out")
        else:
            tail = [l for l in blob.splitlines() if l.strip()]
            rep.add(p.name, "tests", "FAIL", f"rc={rc}: {tail[-1][:160] if tail else ''}")


# --------------------------------------------------------------------------- #
# layer: selftest
# --------------------------------------------------------------------------- #

def layer_selftest(rep: Report, files: list[Path], skip_self: bool = True) -> None:
    for p in files:
        if skip_self and p.name == Path(__file__).name:
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        # Two spellings exist in this repo: a --selftest flag, and a `selftest`
        # subcommand (fd2_audio_probe.py). Match both, but require the actual
        # interface rather than the bare word: dump_exe_tables.py merely has a
        # selftest() function that runs as part of a normal extraction, and a
        # looser match invoked it as `--selftest`, which it read as an input
        # filename and crashed on.
        sub = re.search(r"add_parser\(\s*[\"']selftest", src) is not None
        if "--selftest" not in src and not sub:
            continue
        if p.name in NO_EXEC:
            rep.add(p.name, "selftest", "SKIP", "on the no-exec list")
            continue
        flag = "selftest" if (sub and "--selftest" not in src) else "--selftest"
        argv = ([sys.executable, str(p), flag] if p.suffix == ".py"
                else ["bash", str(p), flag])
        rc, out, err = _run(argv, timeout=900, cwd=REPO, env=_child_env())
        blob = (out + err).strip()
        tail = [l for l in blob.splitlines() if l.strip()]
        if rc == 0:
            rep.add(p.name, "selftest", "PASS", tail[-1][:140] if tail else "")
        elif rc == -9:
            rep.add(p.name, "selftest", "FAIL", "timed out")
        else:
            rep.add(p.name, "selftest", "FAIL", f"rc={rc}: {tail[-1][:160] if tail else ''}")


# --------------------------------------------------------------------------- #
# discovery + driver
# --------------------------------------------------------------------------- #

def discover(tools_dir: Path, only: str | None) -> tuple[list[Path], list[Path]]:
    pys, shs = [], []
    for p in sorted(tools_dir.rglob("*")):
        if "__pycache__" in p.parts or not p.is_file():
            continue
        if only and only not in p.name:
            continue
        if p.suffix == ".py":
            pys.append(p)
        elif p.suffix == ".sh":
            shs.append(p)
    return pys, shs


def run_layers(layers: list[str], tools_dir: Path, only: str | None = None,
               skip_self: bool = True, state_fn=None) -> Report:
    rep = Report()
    pys, shs = discover(tools_dir, only)
    verdicts: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="fd2_verify_") as td:
        tmp = Path(td)
        if "syntax" in layers:
            layer_syntax(rep, pys, shs)
        if "structure" in layers or "imports" in layers:
            verdicts = layer_structure(rep, pys) if "structure" in layers else {
                p.name: analyse_structure(p)[0] for p in pys
            }
        if "imports" in layers:
            layer_imports(rep, pys, verdicts, tmp)
        if "cli" in layers:
            layer_cli(rep, pys, tmp)
        if "invoke" in layers:
            layer_invoke(rep, pys, tmp, state_fn=state_fn)
        if "env" in layers:
            layer_env(rep, pys, tmp)
        if "refs" in layers:
            layer_refs(rep, pys + shs, skip_self=skip_self)
        if "tests" in layers:
            layer_tests(rep, pys)
            layer_tests_sh(rep, shs)
        if "selftest" in layers:
            layer_selftest(rep, pys + shs, skip_self=skip_self)
    return rep


def print_report(rep: Report, verbose: bool) -> None:
    order = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}
    for layer in ALL_LAYERS:
        rows = [c for c in rep.checks if c.layer == layer]
        if not rows:
            continue
        counts: dict[str, int] = {}
        for c in rows:
            counts[c.status] = counts.get(c.status, 0) + 1
        summary = "  ".join(f"{k}={counts[k]}" for k in ("PASS", "WARN", "SKIP", "FAIL") if k in counts)
        print(f"\n=== {layer}  ({summary}) ===")
        for c in sorted(rows, key=lambda c: (order[c.status], c.tool)):
            if c.status == "PASS" and not verbose:
                continue
            if c.status == "SKIP" and not verbose:
                continue
            print(f"  {c.status:4}  {c.tool:38}  {c.detail}")
    print("\n" + "=" * 72)
    counts = rep.counts()
    print("TOTAL  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))


# --------------------------------------------------------------------------- #
# selftest: reverse verification of THIS harness
# --------------------------------------------------------------------------- #

_FIXTURES: dict[str, str] = {
    # positive control: must pass every layer it participates in
    "good_tool.py": textwrap.dedent(
        """
        #!/usr/bin/env python3
        \"\"\"A well-formed tool.\"\"\"
        import argparse

        def main():
            ap = argparse.ArgumentParser(description="fixture")
            ap.add_argument("--x")
            ap.parse_args()

        if __name__ == "__main__":
            main()
        """
    ),
    # syntax layer must FAIL
    "broken_syntax.py": "def f(:\n    pass\n",
    # structure layer must WARN, imports layer must SKIP, and the sentinel
    # must NOT be created (proof the harness really declined to import).
    "no_guard.py": textwrap.dedent(
        """
        import pathlib
        pathlib.Path("SENTINEL_EXECUTED").write_text("boom")
        print("side effect ran")
        """
    ),
    # imports layer must FAIL with MISSING_DEP -> WARN
    "missing_dep.py": textwrap.dedent(
        """
        import definitely_not_a_real_module_xyz

        if __name__ == "__main__":
            pass
        """
    ),
    # imports layer must FAIL (real error, not a missing dep)
    "import_raises.py": textwrap.dedent(
        """
        raise_me = 1 / 0

        if __name__ == "__main__":
            pass
        """
    ),
    # cli layer must FAIL: uses argparse but crashes before parse_args
    "help_crashes.py": textwrap.dedent(
        """
        import argparse, sys

        def main():
            raise RuntimeError("boom before parse_args")
            argparse.ArgumentParser().parse_args()

        if __name__ == "__main__":
            main()
        """
    ),
    # refs layer must FAIL: it will actually open a path in a tree that is gone
    "dead_ref.py": textwrap.dedent(
        """
        from pathlib import Path

        def main():
            return Path("definitely_no_such_tree_xyz/thing.json").read_text()

        if __name__ == "__main__":
            main()
        """
    ),
    # paired control for the one above: the same dangling path, but only as a
    # value the tool emits — must be WARN, not FAIL. Without this pair, a refs
    # layer that flagged every string literal would look equally "correct".
    "mentioned_ref.py": textwrap.dedent(
        """
        TEMPLATE = {"script": "definitely_no_such_tree_xyz/thing.json"}

        if __name__ == "__main__":
            print(TEMPLATE)
        """
    ),
    # invoke layer must WARN: succeeds silently, so "worked" and "did nothing"
    # look identical from outside.
    "silent_success.py": textwrap.dedent(
        """
        import sys

        if __name__ == "__main__":
            sys.exit(0)
        """
    ),
    # paired control: same exit code, but it says what it did -> PASS.
    # Without the pair, a rule keyed on exit status alone would treat both the
    # same and this layer would be measuring nothing.
    "loud_success.py": textwrap.dedent(
        """
        if __name__ == "__main__":
            print("wrote 3 files to ./out")
        """
    ),
    # invoke layer must WARN: writes outside its cwd, via a __file__-relative
    # path, exactly like tools/export_sfx.py did when it recreated remake/.
    "writes_outside.py": textwrap.dedent(
        """
        import pathlib
        (pathlib.Path(__file__).parent / "ESCAPED_OUTPUT.txt").write_text("x")
        print("wrote next to myself")
        """
    ),
    # structure layer must FAIL: valid Python, but its shebang ends with CR so
    # Linux cannot exec it. Written as CRLF bytes by the selftest, not here.
    "crlf_shebang.py": textwrap.dedent(
        """
        #!/usr/bin/env python3
        \"\"\"Valid Python whose shebang is unusable.\"\"\"

        if __name__ == "__main__":
            pass
        """
    ),
    # tests layer must FAIL
    "test_failing.py": "import sys\nsys.exit(1)\n",
    # tests layer must PASS
    "test_passing.py": "print('ok')\n",
    # selftest layer must FAIL
    "selftest_broken.py": textwrap.dedent(
        """
        import sys
        if "--selftest" in sys.argv:
            print("deliberately failing selftest")
            sys.exit(1)
        """
    ),
}

# The good.sh control deliberately contains a brace-function and a for/do/done
# loop. An earlier one-liner version passed even when the harness was corrupting
# the script with CRLF, because `echo ok\r` is still valid bash — the control was
# easier than the real signal it was standing in for. These constructs are the
# ones that actually break under CRLF (`$'{\r'`, `$'do\r'`), which is what every
# real .sh in this repo uses.
_FIXTURE_SH = {
    "good.sh": (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "greet() {\n"
        "    local who=$1\n"
        "    echo \"hi $who\"\n"
        "}\n"
        "for i in 1 2 3; do\n"
        "    greet \"$i\"\n"
        "done\n"
    ),
    "broken.sh": "#!/usr/bin/env bash\nif [ 1 -eq 1 ]; then\n  echo unterminated\n",
}


def _expect(results: dict[tuple[str, str], str], tool: str, layer: str, want: str,
            failures: list[str], why: str) -> None:
    got = results.get((tool, layer), "<no such check>")
    if got != want:
        failures.append(f"{tool} / {layer}: expected {want}, got {got}  ({why})")


def selftest() -> int:
    print("verify_all_tools selftest — reverse verification with deliberate faults\n")
    with tempfile.TemporaryDirectory(prefix="fd2_verify_selftest_") as td:
        fx = Path(td) / "tools"
        fx.mkdir()
        for name, body in _FIXTURES.items():
            # newline="" is load-bearing: without it, Windows writes every
            # fixture as CRLF, which made the good_tool.py positive control trip
            # the shebang check the moment that check was added. Only
            # crlf_shebang.py is supposed to have CR line endings.
            text = body.lstrip("\n")
            if name == "crlf_shebang.py":
                text = text.replace("\n", "\r\n")
            (fx / name).write_text(text, encoding="utf-8", newline="")
        for name, body in _FIXTURE_SH.items():
            (fx / name).write_bytes(body.encode("utf-8"))
        # Regression fixture for a bug this harness actually had: it used to
        # hand bash a CRLF-translated copy of every script and report all 12
        # real .sh tools as broken. good.sh (LF) must pass and crlf.sh (the
        # same bytes with CRLF) must fail — one without the other proves
        # nothing, since a harness that corrupts everything fails both and a
        # harness that checks nothing passes both.
        (fx / "crlf.sh").write_bytes(
            _FIXTURE_SH["good.sh"].replace("\n", "\r\n").encode("utf-8"))

        def watch_fixture_dir():
            return sorted(q.name for q in fx.iterdir())

        rep = run_layers(ALL_LAYERS, fx, skip_self=False, state_fn=watch_fixture_dir)
        results = {(c.tool, c.layer): c.status for c in rep.checks}

        failures: list[str] = []

        # --- positive control, identical configuration -----------------------
        _expect(results, "good_tool.py", "syntax", "PASS", failures, "positive control")
        _expect(results, "good_tool.py", "structure", "PASS", failures, "positive control")
        _expect(results, "good_tool.py", "imports", "PASS", failures, "positive control")
        _expect(results, "good_tool.py", "cli", "PASS", failures, "positive control")
        _expect(results, "good_tool.py", "refs", "PASS", failures, "positive control")
        _expect(results, "good.sh", "syntax", "PASS", failures,
                "positive control (sh, uses brace-fn + for/do/done)")
        _expect(results, "crlf.sh", "syntax", "FAIL", failures,
                "paired control: same script with CRLF must fail")

        # --- fault injection: each layer must detect its own fault -----------
        _expect(results, "broken_syntax.py", "syntax", "FAIL", failures, "SyntaxError must not be silent")
        _expect(results, "broken.sh", "syntax", "FAIL", failures, "bash -n must catch it")
        _expect(results, "no_guard.py", "structure", "WARN", failures, "unguarded module work")
        _expect(results, "crlf_shebang.py", "structure", "FAIL", failures,
                "a CR-terminated shebang is not executable on Linux")
        _expect(results, "no_guard.py", "imports", "SKIP", failures, "must decline to import it")
        _expect(results, "no_guard.py", "deps", "PASS", failures, "deps still checked statically")
        _expect(results, "missing_dep.py", "imports", "WARN", failures, "optional dep != broken tool")
        _expect(results, "import_raises.py", "imports", "FAIL", failures, "real import error")
        _expect(results, "help_crashes.py", "cli", "FAIL", failures, "--help must not crash")
        _expect(results, "dead_ref.py", "refs", "FAIL", failures, "opens a path in a removed tree")
        _expect(results, "mentioned_ref.py", "refs", "WARN", failures,
                "paired control: same path, only mentioned -> WARN not FAIL")
        _expect(results, "silent_success.py", "invoke", "WARN", failures,
                "exit 0 with no output is indistinguishable from doing nothing")
        _expect(results, "loud_success.py", "invoke", "PASS", failures,
                "paired control: same exit code, but it reports what it did")
        _expect(results, "writes_outside.py", "invoke", "WARN", failures,
                "a tool writing outside its cwd must be attributed to that tool")
        _expect(results, "test_failing.py", "tests", "FAIL", failures, "failing test must fail")
        _expect(results, "test_passing.py", "tests", "PASS", failures, "passing test must pass")
        _expect(results, "selftest_broken.py", "selftest", "FAIL", failures, "failing selftest must fail")

        # --- the strong one: prove the skip was a real skip -------------------
        # If the harness had imported no_guard.py, this sentinel would exist.
        sentinels = list(Path(td).rglob("SENTINEL_EXECUTED"))
        if sentinels:
            failures.append(
                f"no_guard.py WAS executed (sentinel at {sentinels[0]}) — the "
                "structure/imports gate is not actually preventing execution"
            )

        # --- the timeout path, tested directly --------------------------------
        rc, _, err = _run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=2)
        if rc != -9 or "timed out" not in err:
            failures.append(f"timeout path did not fire: rc={rc} err={err!r}")
        rc, _, _ = _run([sys.executable, "-c", "print(1)"], timeout=30)
        if rc != 0:
            failures.append("control: a trivial command should succeed under _run")

        total = 22
        print(f"checks: {total - len(failures)}/{total} passed")
        for f in failures:
            print("  FAIL  " + f)
        if not failures:
            print("\nAll reverse-verification checks passed: the harness detects every "
                  "injected fault, passes the positive control, and provably does NOT "
                  "execute tools it classifies as unsafe to import.")
        return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layer", default=",".join(ALL_LAYERS),
                    help="comma-separated subset of: " + ",".join(ALL_LAYERS))
    ap.add_argument("--only", help="substring filter on tool filename")
    ap.add_argument("--json", help="write the full machine-readable report here")
    ap.add_argument("-v", "--verbose", action="store_true", help="also list PASS/SKIP rows")
    ap.add_argument("--selftest", action="store_true", help="reverse-verify this harness")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    layers = [l.strip() for l in args.layer.split(",") if l.strip()]
    bad = [l for l in layers if l not in ALL_LAYERS]
    if bad:
        print(f"unknown layer(s): {bad}", file=sys.stderr)
        return 2

    rep = run_layers(layers, TOOLS, args.only)
    print_report(rep, args.verbose)
    if args.json:
        Path(args.json).write_text(
            json.dumps([asdict(c) for c in rep.checks], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    return 1 if rep.by_status("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
