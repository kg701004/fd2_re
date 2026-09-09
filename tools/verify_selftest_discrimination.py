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
import time
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
    "disasm_le.py":              (["--selftest"], "ghidra"),
    "event_handler_dump.py":     (["--selftest"], "ghidra"),
    "export_story_index_map.py": (["--selftest"], "offline"),
    "export_sfx.py":             (["--selftest"], "offline"),
    "font_grid.py":              (["--selftest"], "offline"),
    "patch_units_ap_dp_mv.py":   (["--selftest"], "offline"),
    "patch_units_hit_ev.py":     (["--selftest"], "offline"),
    "verify_dat_extraction_freshness.py": (["--selftest"], "offline"),
    "trace_item_sfx_dispatch.py": (["--selftest"], "offline"),
    "dosbox_exec_trace_analyze.py": (["--selftest"], "offline"),
    "audit_global_writers.py":    (["--selftest"], "offline"),
    "extract_maps.py":            (["--selftest"], "offline"),
    "render_story.py":            (["--selftest"], "offline"),
    "derive_native_argcounts.py": (["--selftest"], "offline"),
    "export_sprites.py":          (["--selftest"], "offline"),
    "extract_all.py":             (["--selftest"], "offline"),
    # 這兩支雖然是實機工具,但純邏輯(判準)已抽出可離線驗;實機取得層不涵蓋。
    "fd2_in_battle_check.py":     (["--selftest"], "offline"),
    "fd2_game_state.py":          (["--selftest"], "offline"),
    "fd2_sfx_screen_map.py":      (["--selftest"], "offline"),
    "fd2_speaker_capture.py":     (["--selftest"], "offline"),
    "fd2_battle_autoplay.py":     (["--selftest"], "offline"),
    # torch 與權重都在本機;selftest 用一個位移不變的假模型驗分塊幾何,不載權重。
    "realesrgan_upscale.py":      (["--selftest"], "offline"),
    "realesrgan_batch.py":        (["--selftest"], "offline"),
    # 寫入計畫與位址算術是離線可判的;實際 SMV 寫入需要活的 DOSBox,不涵蓋。
    "fd2_stat_override.py":       (["--selftest"], "offline"),
    "fd2_crash_capture.py":       (["--selftest"], "offline"),
    "fd2_crash_ladder.py":        (["--selftest"], "offline"),
    "fd2_zero_read_capture.py":   (["--selftest"], "offline"),
    "fd2_floodfill_stack_probe.py": (["--selftest"], "offline"),
    "char_summary.py":            (["--selftest"], "offline"),
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
    #
    # 本檔自己也不在表內,2026-09-09 明確記下理由(先前只是沒登錄,沒說為什麼)。
    # 突變自己是**會造成實際損害**的:突變體會成為那個「執行突變」的行程,而
    # 第 (3b) 題會 spawn 一個子行程再殺掉它——被突變過的殺行程邏輯可能留下孤兒
    # 行程,被突變過的 recover_orphaned_backups 可能動到別的工具的備份。
    # 代替方案不是「不驗」:本檔 selftest 的第 (1)(2) 題本來就是拿**探針檔**做
    # 正負向控制(一個真的會檢查東西的 selftest 必須被抓到、一個什麼都不檢查的
    # 必須得 0 分),那就是這支工具的鑑別力測試,只是施加在探針而非自己身上。
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


BACKUP_SUFFIX = ".premutation"


def _root_entries() -> set[str]:
    return {p.name for p in ROOT.iterdir()}


def quarantine_side_effects(before: set[str]) -> list[str]:
    """把突變過的工具寫進 repo 根目錄的東西搬出去。回傳被搬走的名稱。

    2026-09-09,實際發生過並且推上了 GitHub:突變測試以 `cwd=ROOT` 執行工具
    (不能改——很多工具用 `extracted/`、`org_game/` 這類相對路徑),而**突變過的
    工具會產生真實副作用**。`export_sprites` 被突變後參數索引偏移,輸出目錄變成
    字面值 `"0"`,於是它把 12 個 FDICON sprite 寫進 repo 根目錄的 `0/`;那是
    著作權資產,而 `.gitignore` 只排除 `extracted/`,根目錄的 `0/` 不在任何忽略
    規則裡,接著就被 `git add -A` 一起提交了。

    `verify_all_tools` 的 invoke 層早就為了同一件事在空的暫存 cwd 執行工具;
    這裡不能那樣做,所以改成事後偵測:比對根目錄項目,新出現的一律**搬到 repo
    之外**並大聲報告。搬而不刪,是因為那可能是別人正在進行的工作;搬出 repo
    而不是加進 .gitignore,是因為忽略只會讓問題安靜下來,不會讓它消失。
    """
    import shutil
    import tempfile
    new = sorted(_root_entries() - before)
    if not new:
        return []
    dest = Path(tempfile.gettempdir()) / "fd2_mutation_sideeffects" / time.strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for name in new:
        shutil.move(str(ROOT / name), str(dest / name))
    print(f"** 突變過的工具在 repo 根目錄產生了 {len(new)} 個項目:{new};"
          f"已搬到 {dest}(不刪除)。**")
    return new


def _backup_path(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def recover_orphaned_backups(root: Path = TOOLS) -> list[str]:
    """把上一次被**中途砍掉**的突變還原回去。回傳被還原的檔名。

    2026-09-09,實際發生過:本工具是**就地改寫原始碼再還原**的,而還原寫在
    `finally` 裡——正常結束與例外都救得到,但行程被 kill 時 `finally` 根本不會
    執行,檔案就停在突變狀態。更糟的是突變體是 `ast.unparse` 產生的,**註解與
    shebang 全部消失**(docstring 是 AST 節點所以留著,註解不是),當時那支工具
    還沒提交,git 也救不回來,只能整份重寫。

    所以在第一次改寫前先寫一份 sidecar 備份,還原成功就刪掉;下次啟動看到殘留的
    備份,就代表上一輪沒有正常結束——直接還原並大聲說出來。`finally` 擋不住
    SIGKILL,但落地的檔案擋得住。
    """
    restored = []
    for bak in sorted(root.glob(f"*{BACKUP_SUFFIX}")):
        target = bak.with_name(bak.name[:-len(BACKUP_SUFFIX)])
        data = bak.read_bytes()
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
            restored.append(target.name)
        bak.unlink()
    if restored:
        print(f"** 偵測到上一輪未正常結束,已從備份還原:{', '.join(restored)} **")
    return restored


def test_tool(name: str, tries: int, timeout: int, seed: int = 0) -> dict:
    path = TOOLS / name
    recover_orphaned_backups()
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
    root_before = _root_entries()
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
            # 備份必須在**第一次改寫之前**就落地,否則被砍時沒有東西可還原。
            bak = _backup_path(path)
            if not bak.exists():
                bak.write_bytes(original)
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
        out["side_effects"] = quarantine_side_effects(root_before)
        restored = hashlib.sha256(path.read_bytes()).hexdigest()
        out["restored_ok"] = restored == digest
        # 只有確定還原成功才刪備份——還原失敗時備份是最後一條退路,不能丟。
        if out["restored_ok"]:
            _backup_path(path).unlink(missing_ok=True)
        else:
            raise SystemExit(
                f"FATAL: {name} 未能還原到原始內容,已中止。"
                f"備份留在 {_backup_path(path).name}")

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

    print("\n(3b) 中斷復原:被砍掉的那一輪必須能從備份救回來(含註解與 shebang)")
    # 用**真的殺掉一個子行程**來測,不是只呼叫還原函式:`finally` 擋不住 SIGKILL,
    # 而這一題要證的正是「finally 沒跑到時還救不救得回來」。
    import subprocess as _sp
    import textwrap as _tw
    victim = TOOLS / "_kill_probe.py"
    ORIGINAL = ('#!/usr/bin/env python3\n'
                '"""probe."""\n'
                '# 這行註解是這題的重點:ast.unparse 會把它吃掉。\n'
                'import sys\n'
                'def selftest():\n'
                '    return 0\n'
                'if __name__ == "__main__":\n'
                '    sys.exit(selftest())\n')
    victim.write_bytes(ORIGINAL.encode("utf-8"))
    killer = TOOLS / "_kill_probe_runner.py"
    killer.write_text(_tw.dedent(f'''
        import sys, time, pathlib
        sys.path.insert(0, {str(TOOLS)!r})
        import verify_selftest_discrimination as V
        p = pathlib.Path({str(victim)!r})
        V._backup_path(p).write_bytes(p.read_bytes())
        p.write_text("import sys\\ndef selftest():\\n    return 0\\n", encoding="utf-8")
        time.sleep(60)
    '''), encoding="utf-8")
    proc = _sp.Popen([sys.executable, str(killer)])
    for _ in range(100):                      # 等它把備份與突變都落地
        if _backup_path(victim).exists() and victim.read_bytes() != ORIGINAL.encode("utf-8"):
            break
        time.sleep(0.05)
    proc.kill()
    proc.wait(timeout=10)
    damaged = victim.read_bytes() != ORIGINAL.encode("utf-8")
    had_backup = _backup_path(victim).exists()
    recovered = recover_orphaned_backups()
    ok3b = (damaged and had_backup
            and victim.read_bytes() == ORIGINAL.encode("utf-8")
            and victim.name in recovered
            and not _backup_path(victim).exists())
    print(f"    {'PASS' if ok3b else 'FAIL'}: 被砍當下檔案確實損毀={damaged}、"
          f"備份存在={had_backup}、還原後逐位元組相同="
          f"{victim.read_bytes() == ORIGINAL.encode('utf-8')}、備份已清除="
          f"{not _backup_path(victim).exists()}")
    if not ok3b:
        fails.append(f"中斷復原不成立:damaged={damaged}、backup={had_backup}")

    print("\n(3c) 負向控制:沒有備份的檔案不得被還原邏輯動到")
    victim.write_bytes(b"# untouched\n")
    before = victim.read_bytes()
    touched = recover_orphaned_backups()
    ok3c = not touched and victim.read_bytes() == before
    print(f"    {'PASS' if ok3c else 'FAIL'}: 還原了 {touched}(應為空)、內容未變="
          f"{victim.read_bytes() == before}")
    if not ok3c:
        fails.append(f"還原邏輯動到沒有備份的檔案:{touched}")
    victim.unlink(missing_ok=True)
    killer.unlink(missing_ok=True)
    _backup_path(victim).unlink(missing_ok=True)

    print("\n(3d) 副作用隔離:突變過的工具寫進 repo 根目錄的東西必須被搬走")
    # 2026-09-09 這件事真的發生並且推上了 GitHub(見 quarantine_side_effects
    # 的 docstring),所以這一題釘的是實際事故,不是假想。
    probe_dir = ROOT / "_sideeffect_probe"
    before = _root_entries()
    probe_dir.mkdir()
    (probe_dir / "leaked.png").write_bytes(b"\x89PNG fake")
    moved = quarantine_side_effects(before)
    ok3d = (moved == ["_sideeffect_probe"] and not probe_dir.exists())
    print(f"    {'PASS' if ok3d else 'FAIL'}: 搬走 {moved}、repo 內已不存在="
          f"{not probe_dir.exists()}")
    if not ok3d:
        fails.append(f"副作用未被隔離:{moved}、still_there={probe_dir.exists()}")
        import shutil as _sh
        _sh.rmtree(probe_dir, ignore_errors=True)

    print("\n(3e) 負向控制:沒有新增項目時不得動任何東西")
    snapshot = _root_entries()
    untouched = quarantine_side_effects(snapshot)
    ok3e = untouched == [] and _root_entries() == snapshot
    print(f"    {'PASS' if ok3e else 'FAIL'}: 搬走 {untouched}(應為空)、"
          f"根目錄未變={_root_entries() == snapshot}")
    if not ok3e:
        fails.append(f"無副作用時仍動了東西:{untouched}")

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
