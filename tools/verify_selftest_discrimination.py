#!/usr/bin/env python3
"""fd2_re - mutation-test every tool's own `--selftest`: does it actually discriminate?

Why this exists
---------------
`tools/verify_all_tools.py`'s `selftest` layer RUNS each tool's selftest and
records whether it passed. That answers "does the selftest pass", which is not
the question that matters. **A selftest that can never fail is worth nothing**,
and this project has shipped two of them in a single day (2026-09-08):

* `decode_story_text.py`'s fault-injection check pointed at `FDTXT_000` -- a name
  table with zero speaker boxes -- so the injected fault ("erase the speaker")
  changed nothing and the check passed regardless.
* `encode_text.py`'s size guard was asserted after the buffer was fully built, so
  the real failure surfaced earlier as a bare `struct.error` and the guard was
  never reached.

Both were found by hand, by accident. This harness looks for them on purpose.

Method
------
For each tool that has a selftest: run it once (must PASS -- otherwise there is
nothing to test), then repeatedly mutate the tool's own source and re-run,
requiring at least one mutation to make the selftest FAIL.

Mutations are AST-driven so they are always syntactically valid, and are chosen
to be behaviour-changing rather than cosmetic:

    ==  <->  !=        comparison inversion
    <   <->  >=        boundary inversion
    n   ->   n + 1     constant perturbation
    True <-> False     boolean inversion

**Scoring is deliberately asymmetric.** A selftest that catches >=1 mutation is
reported DISCRIMINATING. One that catches none is reported WEAK -- *not* "broken":
a random mutation may land in a code path the selftest legitimately does not
cover, so a zero score is a prompt to look, not a verdict. The per-tool mutation
score (caught / attempted) is printed so the reader can judge.

**Use enough tries.** These selftests have mutation hit-rates around 25%, so five
attempts miss entirely about a quarter of the time -- `decode_story_text.py` was
reported WEAK at 5 tries and DISCRIMINATING at both 10 (4/10) and 20 (5/20). The
default is 12; treat anything below that as a smoke test, not a verdict.

Safety
------
Tools resolve repo paths from `__file__`, so they cannot be copied elsewhere to
be mutated. The source is therefore edited **in place** and restored in a
`finally`, and every restore is verified by SHA-256 against the original bytes.
A restore mismatch raises SystemExit immediately rather than letting the run
continue over a mutated tree.

Usage
-----
    python tools/verify_selftest_discrimination.py --list
    python tools/verify_selftest_discrimination.py --offline      # no Ghidra/DOSBox
    python tools/verify_selftest_discrimination.py --tool encode_text.py
    python tools/verify_selftest_discrimination.py --selftest
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
FDTXT = "extracted/raw/FDTXT"

# How to invoke each tool's selftest, and what it needs.
#   needs: "offline"  -- nothing beyond the repo
#          "ghidra"   -- a Ghidra headless run (slow)
#          "live"     -- a running DOSBox-X instance (skipped here)
INVOKE: dict[str, tuple[list[str], str]] = {
    "worklist_status.py":        (["--selftest"], "offline"),
    "encode_text.py":            (["selftest", FDTXT], "offline"),
    "decode_story_text.py":      (["--selftest", FDTXT], "offline"),
    "audit_evidence_provenance.py": (["--selftest"], "offline"),
    "safe_output.py":            (["--selftest"], "offline"),
    "fd2_env_healthcheck.py":    (["--selftest"], "offline"),
    # 2026-09-08:這幾支「檢查器本身」原本不在表內,等於檢查別人的東西自己沒被檢查。
    "verify_docs_match_cli.py":  (["--selftest"], "offline"),
    "verify_generated_artifacts.py": (["--selftest"], "offline"),
    "verify_everything.py":      (["--selftest"], "offline"),
    "extract_native_treasure_event_rules.py": (["--selftest"], "offline"),
    "dump_chapter_beats.py":     (["--selftest"], "offline"),
    "unpack_dat.py":             (["--selftest"], "offline"),
    "decode_sprite.py":          (["--selftest"], "offline"),
    "decode_lmi.py":             (["--selftest"], "offline"),
    "decode_dato.py":            (["--selftest"], "offline"),
    "decode_ani.py":             (["--selftest"], "offline"),
    "decode_figani.py":          (["--selftest"], "offline"),
    "decode_image.py":           (["--selftest"], "offline"),
    "query_verified_address.py": (["--selftest"], "offline"),
    "hash_fd2_reference.py":     (["--selftest"], "offline"),
    "callgraph_le.py":           (["--selftest"], "offline"),
    "dump_remap.py":             (["--selftest"], "offline"),
    "decode_fdicon.py":          (["--selftest"], "offline"),
    "sync_native_treasures.py":  (["--selftest"], "offline"),
    "sync_native_field_events.py": (["--selftest"], "offline"),
    "export_acting_resource_set.py": (["--selftest"], "offline"),
    "gtl2wopl.py":               (["--selftest"], "offline"),
    "xmi2mid.py":                (["--selftest"], "offline"),
    "render_map.py":             (["--selftest"], "offline"),
    "sync_native_join_constructor.py": (["--selftest"], "offline"),
    "export_acting_resources.py": (["--selftest"], "offline"),
    "export_engine_assets.py":    (["--selftest"], "offline"),
    "verify_truncation_robustness.py": (["--selftest"], "offline"),
    "verify_tool_hygiene.py":    (["--selftest"], "offline"),
    "capstone_probe.py":         (["--selftest"], "ghidra"),
    "verify_findings.py":        (["--selftest"], "ghidra"),
    "find_enclosing_function.py": (["--selftest"], "ghidra"),
    "image_ref_scan.py":         (["--selftest"], "ghidra"),
    "ghidra_batch_probe.py":     (["--selftest"], "ghidra"),
    "verify_native_tables_new_edition.py": (["--selftest"], "ghidra"),
    "fd2_sfx_probe.py":          (["--selftest"], "live"),
    "fd2_verified_input.py":     (["--selftest"], "live"),
    "fd2_original_verify.py":    (["--selftest"], "live"),
    "fd2_dialogue_walker.py":    (["--selftest"], "live"),
    "fd2_audio_probe.py":        (["--selftest"], "live"),
    "esp_track.py":              (["--selftest"], "live"),
    # verify_all_tools.py is excluded: its selftest already IS fault injection,
    # and mutating it while it audits the same tree is not interpretable.
}


def run_selftest(name: str, timeout: int) -> tuple[bool, str]:
    argv, _ = INVOKE[name]
    r = subprocess.run([sys.executable, str(TOOLS / name), *argv],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), timeout=timeout)
    return r.returncode == 0, (r.stdout or "")[-400:]


def exit_code_constants(tree: ast.AST) -> set[int]:
    """`id()` of every constant that IS an exit code rather than logic.

    Found by this harness's own negative control: mutating `return 0` to
    `return 1` inside a selftest makes the process exit non-zero without any
    check having run, so a selftest that verifies nothing still scores a point.
    Those mutations measure the exit path, not discrimination, and are skipped.
    """
    out: set[int] = set()

    def mark(n):
        for c in ast.walk(n):
            if isinstance(c, ast.Constant) and isinstance(c.value, (int, bool)):
                out.add(id(c))

    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            mark(node.value)
        elif isinstance(node, ast.Call):
            f = node.func
            nm = (getattr(f, "attr", None) or getattr(f, "id", None) or "")
            if nm in ("exit", "_exit", "SystemExit"):
                for arg in node.args:
                    mark(arg)
        elif isinstance(node, ast.Raise) and node.exc is not None:
            mark(node.exc)
    return out


class Mutator(ast.NodeTransformer):
    """Apply exactly one behaviour-changing edit, chosen by index."""

    def __init__(self, target: int, skip: set[int] | None = None):
        self.target, self.seen, self.applied = target, 0, None
        self.skip = skip or set()

    def _hit(self, what: str) -> bool:
        self.seen += 1
        if self.seen - 1 == self.target:
            self.applied = what
            return True
        return False

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) != 1:
            return node
        flip = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE,
                ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt}
        t = type(node.ops[0])
        if t in flip and self._hit(f"compare {t.__name__}->{flip[t].__name__}"):
            node.ops = [flip[t]()]
        return node

    def visit_Constant(self, node):
        if id(node) in self.skip:
            return node
        if isinstance(node.value, bool):
            if self._hit(f"bool {node.value}->{not node.value}"):
                return ast.copy_location(ast.Constant(value=not node.value), node)
        elif isinstance(node.value, int) and -1 <= node.value <= 0x10000:
            if self._hit(f"int {node.value}->{node.value + 1}"):
                return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return node


def count_sites(src: str) -> int:
    tree = ast.parse(src)
    m = Mutator(-1, exit_code_constants(tree))
    m.visit(tree)
    return m.seen


def mutate(src: str, idx: int) -> tuple[str | None, str]:
    tree = ast.parse(src)
    m = Mutator(idx, exit_code_constants(tree))
    tree = m.visit(tree)
    if m.applied is None:
        return None, ""
    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree), m.applied
    except Exception:
        return None, ""


def test_tool(name: str, tries: int, timeout: int, seed: int = 0) -> dict:
    path = TOOLS / name
    original = path.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    src = original.decode("utf-8")
    out: dict = {"tool": name, "needs": INVOKE[name][1]}

    ok, tail = run_selftest(name, timeout)
    out["baseline_pass"] = ok
    if not ok:
        out["verdict"] = "BASELINE_FAIL"
        out["detail"] = tail.strip().splitlines()[-1:] or [""]
        return out

    n = count_sites(src)
    out["mutation_sites"] = n
    # 種子必須穩定。原本用 `hash(name)`,而 Python 對字串的 hash **每個行程都不同**
    # (PYTHONHASHSEED 隨機化),於是同一支工具每次跑抽到不同突變、結果無法重現——
    # `decode_story_text.py` 一次判 WEAK、一次判 DISCRIMINATING 就是這樣來的,
    # 當時我誤以為只是取樣變異,其實還疊了一層不可重現性。改用 md5 固定;
    # 要刻意探索不同樣本請用 --seed(見 --passes)。
    base = int(hashlib.md5(name.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(base + seed * 7919)
    picks = rng.sample(range(n), min(tries, n)) if n else []
    caught, attempted, examples = 0, 0, []
    try:
        for idx in picks:
            mutated, what = mutate(src, idx)
            if mutated is None:
                continue
            # A mutation that breaks the file outright teaches nothing.
            try:
                ast.parse(mutated)
            except SyntaxError:
                continue
            attempted += 1
            path.write_text(mutated, encoding="utf-8")
            try:
                passed, _ = run_selftest(name, timeout)
            except subprocess.TimeoutExpired:
                passed = False
            if not passed:
                caught += 1
                if len(examples) < 3:
                    examples.append(what)
    finally:
        path.write_bytes(original)
        restored = hashlib.sha256(path.read_bytes()).hexdigest()
        out["restored_ok"] = restored == digest
        if not out["restored_ok"]:
            raise SystemExit(f"FATAL: {name} 未能還原到原始內容,已中止")

    out.update(mutations_attempted=attempted, mutations_caught=caught,
               examples=examples,
               verdict=("DISCRIMINATING" if caught else "WEAK") if attempted else "NO_SITES")
    return out


def selftest() -> int:
    """Reverse-verify this harness: a selftest known to be blind must score 0,
    and one known to be sharp must score > 0. Without both poles the score is
    not interpretable."""
    fails = []
    tmp = TOOLS / "_mutscore_probe.py"

    print("(1) 正向控制:一個真的會檢查東西的 selftest 必須被突變抓到")
    tmp.write_text(
        "import sys\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "def selftest():\n"
        "    return 0 if add(2, 2) == 4 else 1\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(selftest())\n", encoding="utf-8")
    INVOKE[tmp.name] = ([], "offline")
    sharp = test_tool(tmp.name, tries=40, timeout=60)
    ok1 = sharp["verdict"] == "DISCRIMINATING"
    print(f"    {'PASS' if ok1 else 'FAIL'}: {sharp['mutations_caught']}/{sharp['mutations_attempted']} 被抓到")
    if not ok1:
        fails.append(f"正向控制未被抓到:{sharp}")

    print("\n(2) 負向控制:一個什麼都不檢查的 selftest 必須得 0 分")
    tmp.write_text(
        "import sys\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "def selftest():\n"
        "    add(2, 2)\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(selftest())\n", encoding="utf-8")
    blind = test_tool(tmp.name, tries=40, timeout=60)
    ok2 = blind["verdict"] == "WEAK" and blind["mutations_caught"] == 0
    print(f"    {'PASS' if ok2 else 'FAIL'}: {blind['mutations_caught']}/{blind['mutations_attempted']} 被抓到(應為 0)")
    if not ok2:
        fails.append(f"負向控制被誤判為有鑑別力:{blind}")

    print("\n(3) 還原:突變後檔案必須逐位元組還原")
    ok3 = sharp.get("restored_ok") and blind.get("restored_ok")
    print(f"    {'PASS' if ok3 else 'FAIL'}: {ok3}")
    if not ok3:
        fails.append("還原檢查失敗")
    tmp.unlink(missing_ok=True)
    del INVOKE[tmp.name]

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向控制 + 負向控制 + 還原驗證)。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tool")
    ap.add_argument("--offline", action="store_true", help="只跑不需 Ghidra/DOSBox 的工具")
    ap.add_argument("--include-ghidra", action="store_true")
    # 2026-09-08:預設一度用 5,結果 `decode_story_text.py` 被判 WEAK(0/5),
    # 同一支工具在 10 次時是 4/10、20 次時是 5/20 —— 純粹是取樣變異。
    # 它的突變命中率約 25%,5 次抽不中的機率約 24%,足以每四次就誤報一次。
    # 12 次把該機率降到約 3%;真的想下結論就用 --tries 20 以上。
    ap.add_argument("--tries", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0,
                    help="位移取樣。同一支工具不同 seed 會抽到不同的突變集合")
    ap.add_argument("--passes", type=int, default=1,
                    help="連續跑 N 輪、每輪換一個 seed,累積涵蓋率(回答「多跑幾次會不會找到別的問題」)")
    ap.add_argument("--json")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.list:
        for k, (argv, needs) in sorted(INVOKE.items()):
            print(f"  {k:<40} {needs:<8} {' '.join(argv)}")
        return 0

    names = [a.tool] if a.tool else [
        k for k, (_, needs) in sorted(INVOKE.items())
        if needs == "offline" or (needs == "ghidra" and (a.include_ghidra and not a.offline))]
    rows = []
    for n in names:
        if not (TOOLS / n).exists():
            print(f"  {n:<40} 檔案不存在,跳過")
            continue
        best = None
        caught_total = attempted_total = 0
        for k in range(a.passes):
            r = test_tool(n, a.tries, a.timeout, seed=a.seed + k)
            caught_total += r.get("mutations_caught", 0)
            attempted_total += r.get("mutations_attempted", 0)
            # 跨輪取最好的判定:任何一輪抓到就是有鑑別力(WEAK 只在全部輪都 0 時成立)
            if best is None or (r["verdict"] == "DISCRIMINATING" and best["verdict"] != "DISCRIMINATING"):
                best = r
        best["mutations_caught"], best["mutations_attempted"] = caught_total, attempted_total
        best["passes"] = a.passes
        rows.append(best)
        v = best["verdict"]
        extra = (f"{caught_total}/{attempted_total} 被抓到"
                 + (f" ({a.passes} 輪累計)" if a.passes > 1 else "")
                 if attempted_total else best.get("detail", ""))
        print(f"  {n:<40} {v:<16} {extra}")
    weak = [r["tool"] for r in rows if r["verdict"] == "WEAK"]
    bad = [r["tool"] for r in rows if r["verdict"] == "BASELINE_FAIL"]
    good = sum(1 for r in rows if r["verdict"] == "DISCRIMINATING")
    print(f"\n共 {len(rows)} 個工具:有鑑別力 {good} / 弱 {len(weak)} / 基準就失敗 {len(bad)}")
    if weak:
        print(f"  弱(值得人工檢視,不等於壞):{weak}")
    if bad:
        print(f"  基準就失敗(必須先修):{bad}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  JSON -> {a.json}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
