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

The zero score's denominator (2026-09-10)
-----------------------------------------
`fd2_chapter_sweep.py` was reported WEAK (0/12) at several seeds. Taken at face
value that says "the selftest is useless", so a whole layer of paired screen-
predicate tests was added to it and fault-injection-verified -- and the score
barely moved (0/12 -> 1/12). The number was not measuring what it appeared to.

Mutation sites are sampled uniformly over the WHOLE FILE (`rng.sample`). That
tool is 3568 lines / 57 functions, nearly all of it tmux/xdotool/debugger code
no offline selftest can execute. The expected catch rate is therefore pinned in
the single digits by *file composition*, no matter how good the selftest is --
and "WEAK" could not distinguish "the selftest is weak" from "every mutation
landed where the selftest cannot reach". A verdict whose rival explanation
predicts the same observation points work in the wrong direction, which is
exactly what happened.

So each mutation is now classified by where it landed, using the lines the
selftest actually executes (traced via `trace.Trace` over `selftest()`):

* landed on a line the selftest executes, and that line is NOT inside the
  selftest itself -- the only mutations that carry evidence. Escapes here are
  printed individually ("逃掉但執行得到"), because those are the actionable ones.
* landed inside `selftest`/`_selftest_*` -- mutating a test's own input or
  assertion. Two real examples: `(10, 10, 61)` -> `(11, 10, 61)` and
  `natural_join_order(0)` -> `(1)`; both perturbed inputs have the same correct
  answer, so escaping proves nothing.
* landed on a line the selftest never runs -- no evidence either way.

New verdict **UNREACHABLE_SAMPLE**: attempted > 0 but not one mutation reached
executable product code. That run says nothing about selftest quality and must
not be read as WEAK. WEAK now means what it claims: a reachable product-code
mutation survived.

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

Stability (2026-09-11)
----------------------
Three successive full sweeps reported 16 -> 2 -> 5 new real gaps and never
converged. Two causes, both in this harness, not in the tools:

* Sampling picked site **indices**, and an index is AST visit order: one extra
  constant anywhere shifts every later index. `decode_fdicon.py` gained only
  selftest checks, yet its two 12-mutation samples shared 2 mutations. Each fix
  therefore chased a fresh sample. Sites now carry a **stable key** (enclosing
  function | line text | mutation # occurrence) and sampling ranks by its hash.
* The reach trace called `selftest()` with no arguments, so tools whose selftest
  takes CLI arguments (`encode_text.py`, `decode_story_text.py`) or is named
  `_selftest` were never traced. It now runs the exact INVOKE command line.

`--exhaustive` drops sampling altogether: every site on product code the
selftest executes is mutated. The result depends only on the source, so it is
reproducible and can reach zero. Proven equivalent mutants are registered in
`docs/data/equivalent_mutants.json` (stable key + reason + evidence) and are
subtracted; a registered entry that gets caught (the registry is wrong) or no
longer matches any site (stale) fails the run.

Usage
-----
    python tools/verify_selftest_discrimination.py --list
    python tools/verify_selftest_discrimination.py --offline      # no Ghidra/DOSBox
    python tools/verify_selftest_discrimination.py --offline --exhaustive
    python tools/verify_selftest_discrimination.py --tool encode_text.py --exhaustive
    python tools/verify_selftest_discrimination.py --equivalents docs/data/equivalent_mutants.json
    python tools/verify_selftest_discrimination.py --tool decode_image.py --tries 20 --seed 3 --passes 2 --timeout 300 --json out.json
    python tools/verify_selftest_discrimination.py --include-ghidra
    python tools/verify_selftest_discrimination.py --selftest
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
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
    # 2026-09-09 補進來:它是把原始 beats 變成下游真正消費的 IR 的轉換層,
    # 卻一直沒有 --selftest,因此從來沒被突變測試掃過。
    "export_handler_scripts.py": (["--selftest"], "offline"),
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
    "derive_item_row_fields.py":  (["--selftest"], "offline"),
    "derive_ail_entry_points.py": (["--selftest"], "offline"),
    "verify_event_dispatch_table.py": (["--selftest"], "offline"),
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
    # 整支是 NO_EXEC 的實機掃描,但名冊推導那一層由已提交的 chapter_beats 決定,離線可判。
    "fd2_chapter_sweep.py":       (["--selftest"], "offline"),
    "char_summary.py":            (["--selftest"], "offline"),
    "verify_truncation_robustness.py": (["--selftest"], "offline"),
    "verify_tool_hygiene.py":    (["--selftest"], "offline"),
    "verify_address_citations.py": (["--selftest"], "offline"),
    "text_proximity.py": (["--selftest"], "offline"),
    "verify_address_claim_coverage.py": (["--selftest"], "offline"),
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

    2026-09-10 -- this was far too broad, and the reachability work above is what
    exposed it. It marked every constant inside **every `return` anywhere in the
    file**, so ordinary logic like `return a + 3`, `return w * 2`, `return v &
    0xff` was silently excluded from mutation across all 63 tools: a whole class
    of product code the harness could never test, invisible because excluded
    sites are simply never counted. The exclusion now matches what it claims --
    a return whose value **is** a bare int/bool constant, inside a function whose
    return value really does become the process exit code (`selftest`/`main`).
    `exit()`/`SystemExit`/`raise` stay excluded wherever they appear.

    Corroboration that the old rule was wrong, not merely loose: this harness's
    own blind negative control (check 2) is a selftest that calls `add()` and
    asserts nothing, and `add` is `return a + 3`. Under the old rule that `3` was
    unmutatable, so the probe scored 0 for the wrong reason -- the only mutations
    left were in the selftest's own arguments. With the rule narrowed, the probe
    scores 0 because a genuinely reachable product mutation survives, which is
    exactly what the control is supposed to demonstrate.
    """
    out: set[int] = set()

    def mark(n):
        for c in ast.walk(n):
            if isinstance(c, ast.Constant) and isinstance(c.value, (int, bool)):
                out.add(id(c))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name in ("selftest", "main") or node.name.startswith("_selftest")):
            for sub in ast.walk(node):
                # 只跳過「整個回傳值就是一個裸常數」的情形,不跳過運算式裡的常數。
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Constant):
                    mark(sub.value)
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

    def __init__(self, target: int, skip: set[int] | None = None, record: bool = False):
        self.target, self.seen, self.applied = target, 0, None
        self.applied_line: int | None = None
        self.skip = skip or set()
        # 突變點的穩定識別需要「所在函式」;`sites` 只在列舉模式(record=True)收集。
        self.scope: list[str] = []
        self.sites: list[tuple[int | None, str, str]] | None = [] if record else None

    def _scoped(self, node):
        # 走訪順序與預設的 generic_visit 完全相同,只多記一層範圍名稱 —— 突變點的
        # 編號因此不變(以全部工具的突變點序列逐一比對過)。
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()
        return node

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped

    def _hit(self, what: str, node=None) -> bool:
        self.seen += 1
        # 記下突變落在哪一行,才能回答「這個突變 selftest 跑得到嗎」。
        line = getattr(node, "lineno", None)
        if self.sites is not None:
            self.sites.append((line, what, ".".join(self.scope) or "<module>"))
        if self.seen - 1 == self.target:
            self.applied = what
            self.applied_line = line
            return True
        return False

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) != 1:
            return node
        flip = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE,
                ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt}
        t = type(node.ops[0])
        if t in flip and self._hit(f"compare {t.__name__}->{flip[t].__name__}", node):
            node.ops = [flip[t]()]
        return node

    def visit_Constant(self, node):
        if id(node) in self.skip:
            return node
        if isinstance(node.value, bool):
            if self._hit(f"bool {node.value}->{not node.value}", node):
                return ast.copy_location(ast.Constant(value=not node.value), node)
        elif isinstance(node.value, int) and -1 <= node.value <= 0x10000:
            if self._hit(f"int {node.value}->{node.value + 1}", node):
                return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return node


def mutate_at(src: str, idx: int) -> tuple[str | None, str, int | None]:
    """套用第 idx 個突變,回傳 (突變後原始碼, 突變種類, 落點行號)。"""
    tree = ast.parse(src)
    m = Mutator(idx, exit_code_constants(tree))
    tree = m.visit(tree)
    if m.applied is None:
        return None, "", None
    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree), m.applied, m.applied_line
    except Exception:
        return None, "", None


def list_sites(src: str) -> list[dict]:
    """列出每個突變點:編號、行號、突變種類、所在函式,以及**穩定鍵**。

    2026-09-11:抽樣原本以 `rng.sample(range(n))` 挑**編號**,而編號是 AST 走訪順序,
    檔案任何一處多一個常數,後面的編號全部位移。實測只補了 selftest 題目、產品碼沒動
    的 `decode_fdicon.py`,前後兩次抽到的 12 個突變只有 2 個相同 —— 每次修補都在追
    一組新樣本,三輪複掃的新缺口 16 -> 2 -> 5 不會收斂。穩定鍵是「所在函式 | 該行
    文字 | 突變種類 # 同鍵序號」,不含行號與編號,不相干的編輯動不到它。
    """
    tree = ast.parse(src)
    m = Mutator(-1, exit_code_constants(tree), record=True)
    m.visit(tree)
    lines = src.splitlines()
    seen: dict[str, int] = {}
    out = []
    for idx, (line, what, scope) in enumerate(m.sites or []):
        text = " ".join(lines[line - 1].split()) if line and line <= len(lines) else ""
        base = f"{scope}|{text}|{what}"
        occ = seen.get(base, 0)
        seen[base] = occ + 1
        out.append({"idx": idx, "line": line, "what": what, "func": scope,
                    "text": text, "key": f"{base}#{occ}"})
    return out


def stable_picks(name: str, sites: list[dict], tries: int, seed: int = 0) -> list[int]:
    """依穩定鍵的雜湊挑出 `tries` 個突變點,回傳其編號。

    新增的突變點只可能**擠掉**原本入選的少數幾個,不會把整組樣本重新洗牌;同一份
    原始碼與同一個 seed 永遠得到同一組。`--seed` 仍可刻意換一組樣本。
    """
    ranked = sorted(sites, key=lambda s: hashlib.sha1(
        f"{name}|{seed}|{s['key']}".encode("utf-8")).hexdigest())
    return [s["idx"] for s in ranked[:tries]]


# --------------------------------------------------------------------------
# 「這個突變,selftest 有機會看到嗎?」
#
# 2026-09-10:`fd2_chapter_sweep.py` 連續在數個 seed 被判 WEAK(0/12)。我先
# 照字面把它當成「selftest 不夠力」,補了一整層畫面判準的成對測試並以故障注入
# 確認有效——分數卻幾乎沒動(seed 1 由 0/12 變 1/12,seed 3/4 仍是 0/12)。
#
# 原因不在被測工具,在這個度量本身:突變落點是 `rng.sample(range(n))`,對**全檔**
# 均勻抽樣。那支工具 3568 行、57 個函式,其中絕大多數是 tmux/xdotool/除錯器的
# 實機層,任何離線 selftest 都執行不到;可測核心只佔一小塊,於是期望捕捉率被
# 檔案組成壓在個位數,和 selftest 寫得多好無關。
#
# 這正是「若對立假說預測同樣的觀測值,這個檢查就是裝飾」:WEAK 這個判定原本
# 無法分辨「selftest 沒用」與「樣本全落在實機層」。所以這裡把 selftest 實際
# 執行過的行號量出來,把兩者分開報——而不是繼續把工程力氣投進一個不會動的數字。
# --------------------------------------------------------------------------

# 2026-09-11:原本以 `mod.selftest()` **不帶參數**直接呼叫。`encode_text.py`
# (`selftest(src, g2c, c2g)`)與 `decode_story_text.py`(`selftest(src)`)的
# selftest 需要命令列給的參數,於是追蹤**每一次**都失敗、落點永遠未知 ——
# 後者正是歷史上 WEAK/DISCRIMINATING 來回翻轉的那支。現在改成用與 run_selftest
# **完全相同的命令列**(INVOKE 的 argv,runpy 以 __main__ 執行),只記錄 selftest
# 框架(含其呼叫的同檔函式)存活期間執行到的行,語意與舊版「只算 selftest 期間」
# 相同。selftest 從未被呼叫時回報錯誤,不當成「0 行可達」。
_TRACE_SNIPPET = """
import json, os, runpy, sys
sys.path.insert(0, {tools!r})
target = os.path.normcase(os.path.abspath({target!r}))
sys.argv = [{target!r}, *{argv!r}]
lines, depth, entered, norm = set(), [0], [False], {{}}
ENTRY = ("selftest", "_selftest")   # safe_output / realesrgan_* 的進入點叫 _selftest

def _in_target(code):
    f = code.co_filename
    if f not in norm:
        norm[f] = os.path.normcase(os.path.abspath(f)) == target
    return norm[f]

def _local(frame, event, arg):
    if event == "line" and depth[0] > 0:
        lines.add(frame.f_lineno)
    elif event == "return" and frame.f_code.co_name in ENTRY:
        depth[0] -= 1
    return _local

def _global(frame, event, arg):
    if not _in_target(frame.f_code):
        return None
    if frame.f_code.co_name in ENTRY:
        depth[0] += 1
        entered[0] = True
    return _local

err = None
sys.settrace(_global)
try:
    runpy.run_path({target!r}, run_name="__main__")
except SystemExit:
    pass
except BaseException as e:
    err = "run: %s" % e
finally:
    sys.settrace(None)
if not entered[0]:
    print(json.dumps({{"error": err or "selftest() 從未被呼叫"}}))
else:
    print(json.dumps({{"lines": sorted(lines)}}))
"""


def verdict_for(attempted: int, caught: int, reach_known: bool, reachable: int) -> str:
    """由「試了幾個/抓到幾個/落點知不知道/其中幾個可達產品碼」定判定。

    抽成函式是為了讓 selftest 打得到**真正跑的那一份**;就地重算一遍只驗證了
    selftest 自己寫的那行對不對。`reach_known` 為 False 時不得宣稱
    UNREACHABLE_SAMPLE——追蹤失敗是「不知道」,不是「沒有可達突變」。
    """
    if not attempted:
        return "NO_SITES"
    if caught:
        return "DISCRIMINATING"
    if reach_known and reachable == 0:
        return "UNREACHABLE_SAMPLE"
    return "WEAK"


def selftest_own_lines(src: str) -> set[int]:
    """selftest 自己(及其 `_selftest_*` 輔助函式)佔用的行號。

    突變落在這裡面時,改的是**測試自己的輸入或斷言**,不是被測邏輯。實測到的
    兩個例子:`(10, 10, 61)` 被改成 `(11, 10, 61)`、`natural_join_order(0)` 被
    改成 `(1)` —— 兩者的正確答案都沒變,所以「沒被抓到」完全不代表 selftest 弱。
    把兩側分開算,逃掉的產品碼突變才是真正該修的線索。
    """
    lines: set[int] = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "selftest" in node.name:
            lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return lines


def executed_lines(name: str, timeout: int) -> tuple[set[int] | None, str]:
    """回傳 (selftest 真正執行過的行號集合, 說明)。拿不到就回 (None, 原因) ——
    拿不到不等於「沒有可達行」,那是兩件事,不可混為一談。"""
    target = str((TOOLS / name).resolve())
    code = _TRACE_SNIPPET.format(tools=str(TOOLS), target=target, argv=list(INVOKE[name][0]))
    try:
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "追蹤逾時"
    out = (r.stdout or "").strip().splitlines()
    for line in reversed(out):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if "lines" in d:
            return set(d["lines"]), f"{len(d['lines'])} 行"
        return None, d.get("error", "未知")
    return None, "追蹤沒有輸出"


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


_VG = None


def _vg():
    """verify_generated_artifacts 模組。必須在任何突變**之前**載入(main 會先呼叫):
    窮舉輪到 verify_generated_artifacts.py 本身時,磁碟上的它是突變過的,那時才 import
    就會拿到突變版的比對邏輯。"""
    global _VG
    if _VG is None:
        import verify_generated_artifacts as mod
        _VG = mod
    return _VG


def _artifacts_notice(rows: list, timeout: int) -> bool:
    """在突變狀態下重生該工具登錄的產物;任一項漂移或無法執行,即 artifacts 軸會抓到
    這個突變。逾時也算抓到 —— 那一軸會失敗,不會安靜通過。"""
    for row in rows:
        try:
            verdict = _vg().check_one(*row, timeout)["verdict"]
        except subprocess.TimeoutExpired:
            return True
        if verdict in ("DRIFT", "ERROR"):
            return True
    return False


def test_tool(name: str, tries: int, timeout: int, seed: int = 0,
              exhaustive: bool = False, equivalents: dict | None = None,
              artifact_rows: list | None = None) -> dict:
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

    sites = list_sites(src)
    out["mutation_sites"] = len(sites)
    caught, attempted, examples = 0, 0, []
    escapes: list[dict] = []
    caught_keys: set[str] = set()
    reach_lines, reach_why = executed_lines(name, timeout)
    own_lines = selftest_own_lines(src)
    out["executed_lines"] = (len(reach_lines) if reach_lines is not None else None)
    out["executed_lines_note"] = reach_why
    product = [s for s in sites if reach_lines is not None
               and s["line"] in reach_lines and s["line"] not in own_lines]
    if exhaustive:
        # 窮舉:selftest 執行得到的產品碼上**每一個**突變點都測。沒有亂數,結果只取決
        # 於原始碼 —— 同一份程式碼跑幾次都一樣,修掉一個缺口只會讓逃逸數變少。
        if reach_lines is None:
            out["verdict"] = "NO_REACH_TRACE"
            out["detail"] = [f"落點追蹤失敗({reach_why}),無法窮舉"]
            return out
        picks = [s["idx"] for s in product]
    else:
        # 種子必須穩定:2026-09-08 原本用 `hash(name)`,PYTHONHASHSEED 讓它每個行程都
        # 不同;之後改成 md5(name) 固定種子,卻仍以**編號**抽樣,檔案一變整組重洗
        # (見 list_sites)。現在以穩定鍵雜湊挑選,`--seed` 仍可刻意換一組。
        picks = stable_picks(name, sites, tries, seed)
    by_idx = {s["idx"]: s for s in sites}
    # 2026-09-11:selftest 逃掉、但該工具有登錄產生器時,在突變狀態下重生產物比對。
    # artifacts 軸每輪都跑,它抓得到的突變在整個驗證體系裡並沒有漏 —— 這不是等價,
    # 是「由另一軸覆蓋」,而且每次窮舉都重新實證,不靠人工登錄。前提:未突變時重生
    # 必須逐位元組相同,否則每個突變都會看起來「被抓到」。
    probe_rows: list = []
    if exhaustive:
        rows = (artifact_rows if artifact_rows is not None
                else [r for r in _vg().REGISTRY if r[1] == name])
        if rows:
            base = [_vg().check_one(*r, timeout)["verdict"] for r in rows]
            if all(v == "IDENTICAL" for v in base):
                probe_rows = rows
            else:
                out["artifact_probe"] = f"未突變時重生就不相同({base}),本工具不啟用"
    covered: list[str] = []
    reachable_attempted = reachable_caught = 0
    root_before = _root_entries()
    try:
        for idx in picks:
            mutated, what, at_line = mutate_at(src, idx)
            if mutated is None:
                continue
            # A mutation that breaks the file outright teaches nothing.
            try:
                ast.parse(mutated)
            except SyntaxError:
                continue
            attempted += 1
            in_reach = reach_lines is not None and at_line in reach_lines
            in_product = in_reach and at_line not in own_lines
            if in_product:
                reachable_attempted += 1
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
                if in_product:
                    reachable_caught += 1
                    caught_keys.add(by_idx[idx]["key"])
                if len(examples) < 3:
                    examples.append(what)
            elif in_product:
                # 逃掉的、而且 selftest 明明執行得到的突變——這才是真正該修的線索,
                # 也是唯一能區分「selftest 不夠力」與「樣本沒落到可測範圍」的證據。
                s = by_idx[idx]
                if probe_rows and _artifacts_notice(probe_rows, timeout):
                    covered.append(s["key"])
                else:
                    escapes.append({"line": at_line, "what": what, "func": s["func"],
                                    "text": s["text"], "key": s["key"]})
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

    # 等價突變登錄表:已證明任何 selftest 都不可能抓到的突變,從逃逸清單扣除 —— 否則
    # 窮舉的逃逸數永遠歸不了零,也就不會再有人讀它。登錄表本身同樣要被檢查:登錄為
    # 等價卻被抓到 = 登錄錯了;窮舉時找不到該突變點 = 條目過期(原始碼已改)。
    registered = (equivalents or {}).get(name, {})
    real = [e for e in escapes if e["key"] not in registered]
    out.update(mutations_attempted=attempted, mutations_caught=caught,
               examples=examples,
               reachable_attempted=reachable_attempted,
               reachable_caught=reachable_caught,
               # 2026-09-11:原本截成前 5 個(`escapes[:5]`),`verify_truncation_robustness`
               # 報 0/6 卻只列得出 3 個 —— 總數與明細對不上。現在全列。
               reachable_escapes=[f"L{e['line']}: {e['what']}" for e in real],
               reachable_escape_details=real,
               equivalent_escapes=[e["key"] for e in escapes if e["key"] in registered],
               covered_by_artifacts=covered,
               # 被 artifacts 軸抓到 = 突變改變了產物 = 行為變了,同樣推翻「等價」的主張。
               registry_contradicted=sorted(k for k in registered
                                            if k in caught_keys or k in covered),
               registry_stale=(sorted(set(registered) - {s["key"] for s in product})
                               if exhaustive else []),
               exhaustive=exhaustive)
    # 一個突變都沒落在 selftest 執行得到的產品碼上時,這一輪對 selftest 的品質
    # **沒有提供任何證據**,報成 WEAK 會把力氣導向錯的地方。判定邏輯見 verdict_for。
    out["verdict"] = verdict_for(attempted, caught,
                                 reach_lines is not None, reachable_attempted)
    return out


def selftest() -> int:
    """Reverse-verify this harness: a selftest known to be blind must score 0,
    and one known to be sharp must score > 0. Without both poles the score is
    not interpretable."""
    fails = []
    tmp = TOOLS / "_mutscore_probe.py"

    print("(1) 正向控制:一個真的會檢查東西的 selftest 必須被突變抓到")
    # 探針的前提要寫明:`add` 裡必須有一個**產品碼側、且 selftest 真的會執行到**
    # 的可突變判準(`a > 100`)。原本兩個探針的 add 都只是 `return a + b`,一個
    # 可突變的常數或比較都沒有——於是負向控制得 0 分的真正原因是「無處可突變」,
    # 而不是它宣稱的「selftest 什麼都不檢查」。兩者的觀測值相同,證據力卻不同。
    tmp.write_text(
        "import sys\n"
        "def add(a, b):\n"
        "    if a > 100:\n"
        "        return -1\n"
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
        "    if a > 100:\n"
        "        return -1\n"
        "    return a + b\n"
        "def selftest():\n"
        "    add(2, 2)\n"
        "    return 0\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(selftest())\n", encoding="utf-8")
    blind = test_tool(tmp.name, tries=40, timeout=60)
    # 0 分不夠——還要確認**確實有可達的產品碼突變逃掉**,否則「無處可突變」也是 0 分,
    # 兩種情形的觀測值一樣但意義相反,這正是 2026-09-10 UNREACHABLE_SAMPLE 要分開的事。
    ok2 = (blind["verdict"] == "WEAK" and blind["mutations_caught"] == 0
           and blind["reachable_attempted"] > 0)
    print(f"    {'PASS' if ok2 else 'FAIL'}: {blind['mutations_caught']}/{blind['mutations_attempted']} 被抓到"
          f"(應為 0),其中可達產品碼 {blind['reachable_attempted']} 個(必須 >0,"
          f"否則 0 分的原因是無處可突變):{blind.get('reachable_escapes')}")
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

    print("\n(4) 落點分類:selftest 自己的行 vs 產品碼,必須分得開")
    probe_src = (
        "def add(a, b):\n"
        "    return a + 3\n"
        "def selftest():\n"
        "    assert add(1, 1) == 4\n"
        "    return 0\n")
    own = selftest_own_lines(probe_src)
    ok4 = own == {3, 4, 5} and 2 not in own
    print(f"    {'PASS' if ok4 else 'FAIL'}: selftest 佔用 {sorted(own)}"
          f"(應為 [3, 4, 5]),產品碼第 2 行不在其中={2 not in own}")
    if not ok4:
        fails.append(f"selftest_own_lines 分不出兩側:{sorted(own)}")

    print("\n(4b) 成對案例:UNREACHABLE_SAMPLE 只在『沒有任何產品碼突變可達』時成立")
    # 這是 2026-09-10 真正發生過的形狀:0/12 被抓到,但 12 個突變沒有一個落在
    # selftest 執行得到的產品碼上——那一輪對 selftest 品質沒有提供任何證據,
    # 報成 WEAK 會把工程力氣導向錯的地方。
    got = (verdict_for(12, 0, True, 0),    # 全落在實機層/測試自己 -> 無證據
           verdict_for(12, 0, True, 1),    # 有一個可達卻逃掉 -> 真的弱
           verdict_for(12, 1, True, 1),    # 抓到 -> 有鑑別力
           verdict_for(12, 0, False, 0))   # 追蹤失敗:不知道就不能宣稱無證據
    want = ("UNREACHABLE_SAMPLE", "WEAK", "DISCRIMINATING", "WEAK")
    ok4b = got == want
    print(f"    {'PASS' if ok4b else 'FAIL'}: {got}")
    if not ok4b:
        fails.append(f"判定分類不符:{got} != {want}")

    print("\n(4c) 非平凡性:上面四組若只看 caught,前三組會擠成同一個答案")
    collapsed = {("DISCRIMINATING" if c else "WEAK") for _, c, _, _ in
                 [(12, 0, True, 0), (12, 0, True, 1), (12, 1, True, 1)]}
    ok4c = len(collapsed) == 2 and len(set(got[:3])) == 3
    print(f"    {'PASS' if ok4c else 'FAIL'}: 只看 caught 得到 {len(collapsed)} 種、"
          f"加上落點得到 {len(set(got[:3]))} 種")
    if not ok4c:
        fails.append("落點資訊沒有帶來新的區分力")

    print("\n(5) 穩定鍵:開頭插入不相干的突變點,其餘的鍵不變,樣本只會被擠掉、不會重洗")
    body = "".join(f"def f{i}(x):\n    return x + {i} if x > {i * 3} else x - {i}\n"
                   for i in range(1, 13))
    extra = "def unrelated(y):\n    return y * 7 + 11 if y != 5 else 2\n"
    s_old, s_new = list_sites(body), list_sites(extra + body)
    key_old = {s["idx"]: s["key"] for s in s_old}
    key_new = {s["idx"]: s["key"] for s in s_new}
    idx_of_old = {s["key"]: s["idx"] for s in s_old}
    old_keys = set(idx_of_old)
    # 前提:插入真的讓編號位移了,否則這題測不到舊版的問題。
    shifted = any(idx_of_old[s["key"]] != s["idx"] for s in s_new if s["key"] in idx_of_old)
    pick_old = {key_old[i] for i in stable_picks("p.py", s_old, 8)}
    pick_new = {key_new[i] for i in stable_picks("p.py", s_new, 8)}
    # 對照:舊的「依編號抽樣」在同樣的編輯下會重洗 —— 證明下面的判準有能力說不。
    import random as _rnd
    by_index_old = {key_old[i] for i in _rnd.Random(1).sample(range(len(s_old)), 8)}
    by_index_new = {key_new[i] for i in _rnd.Random(1).sample(range(len(s_new)), 8)}
    ok5 = (old_keys <= set(key_new.values()) and shifted
           and (pick_new & old_keys) <= pick_old
           and stable_picks("p.py", s_new, 8) == stable_picks("p.py", s_new, 8)
           and not (by_index_new & old_keys) <= by_index_old)
    print(f"    {'PASS' if ok5 else 'FAIL'}: 編號位移={shifted}、舊鍵全數保留="
          f"{old_keys <= set(key_new.values())}、穩定鍵樣本只被擠掉="
          f"{(pick_new & old_keys) <= pick_old}、對照(依編號)確實重洗="
          f"{not (by_index_new & old_keys) <= by_index_old}")
    if not ok5:
        fails.append("穩定鍵抽樣在不相干的編輯下仍重洗了樣本")

    print("\n(6) 窮舉:可重現,登錄表的扣除/登錄錯誤/過期三種情形分得開")
    # 前提:add 裡恰好 3 個可達產品碼突變點 —— `>` 反轉與 `-1` 改 `-2` 會被抓到,
    # `100 -> 101` 不會(selftest 用 150,兩個門檻都擋得住),所以恰好 1 個逃逸。
    exh = TOOLS / "_mutscore_exh_probe.py"
    exh.write_text(
        "import sys\n"
        "def add(a, b):\n"
        "    if a > 100:\n"
        "        return -1\n"
        "    return a + b\n"
        "def selftest():\n"
        "    return 0 if add(2, 2) == 4 and add(150, 0) == -1 else 1\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(selftest())\n", encoding="utf-8")
    INVOKE[exh.name] = ([], "offline")
    esc_key = "add|if a > 100:|int 100->101#0"
    caught_key = "add|if a > 100:|compare Gt->LtE#0"
    bogus_key = "add|return a + b|int 9->10#0"
    try:
        r1 = test_tool(exh.name, tries=0, timeout=60, exhaustive=True)
        r2 = test_tool(exh.name, tries=0, timeout=60, exhaustive=True)
        reg = {exh.name: {k: {} for k in (esc_key, caught_key, bogus_key)}}
        r3 = test_tool(exh.name, tries=0, timeout=60, exhaustive=True, equivalents=reg)
    finally:
        exh.unlink(missing_ok=True)
        _backup_path(exh).unlink(missing_ok=True)
        del INVOKE[exh.name]
    det1 = [e["key"] for e in r1.get("reachable_escape_details", [])]
    det2 = [e["key"] for e in r2.get("reachable_escape_details", [])]
    ok6 = (det1 == det2 == [esc_key]
           and r1.get("reachable_attempted") == 3 and r1.get("reachable_caught") == 2
           and r3.get("reachable_escapes") == [] and r3.get("equivalent_escapes") == [esc_key]
           and r3.get("registry_contradicted") == [caught_key]
           and r3.get("registry_stale") == [bogus_key])
    print(f"    {'PASS' if ok6 else 'FAIL'}: 兩次窮舉逃逸 {det1} / {det2}(應相同且只有 100->101)、"
          f"可達 {r1.get('reachable_caught')}/{r1.get('reachable_attempted')}(應 2/3);"
          f"登錄後逃逸={r3.get('reachable_escapes')}、等價={r3.get('equivalent_escapes')}、"
          f"登錄錯誤={r3.get('registry_contradicted')}、過期={r3.get('registry_stale')}")
    if not ok6:
        fails.append(f"窮舉或登錄表判定不對:{det1} {det2} {r3}")

    print("\n(6b) 登錄表格式:缺理由、重複鍵必須丟例外,不能被當成空登錄表")
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        eq_path = Path(td) / "eq.json"

        def _load(entries):
            eq_path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
            try:
                return load_equivalents(eq_path)
            except ValueError:
                return "ValueError"
        good = {"tool": "t.py", "key": "k", "reason": "r", "evidence": "e"}
        ok6b = (_load([good]) == {"t.py": {"k": good}}
                and _load([dict(good, reason="")]) == "ValueError"
                and _load([good, dict(good)]) == "ValueError"
                and load_equivalents(Path(td) / "missing.json") == {})
    print(f"    {'PASS' if ok6b else 'FAIL'}: 正常條目可讀、缺理由/重複鍵丟例外、檔案不存在=空")
    if not ok6b:
        fails.append("等價突變登錄表的格式驗證不對")

    print("\n(7) 落點追蹤:需要命令列參數的 selftest 要追得到;從未被呼叫要回報錯誤")
    # 2026-09-11 前,`encode_text.py`/`decode_story_text.py` 的追蹤每次都失敗
    # (selftest 需要參數),落點永遠未知。這題用同形狀的探針釘住修法。
    tp = TOOLS / "_trace_probe.py"
    tp.write_text("import sys\n"
                  "def selftest(src):\n"
                  "    return 0 if len(src) == 1 else 1\n"
                  "if __name__ == '__main__':\n"
                  "    sys.exit(selftest(sys.argv[1]))\n", encoding="utf-8")
    INVOKE[tp.name] = (["x"], "offline")
    try:
        with_arg, _ = executed_lines(tp.name, 60)
        tp.write_text("import sys\n"
                      "def check():\n"
                      "    return 0\n"
                      "if __name__ == '__main__':\n"
                      "    sys.exit(check())\n", encoding="utf-8")
        never, never_why = executed_lines(tp.name, 60)
        r7 = test_tool(tp.name, tries=0, timeout=60, exhaustive=True)
        # safe_output / realesrgan_* 的進入點叫 `_selftest`,也要追得到。
        tp.write_text("import sys\n"
                      "def _selftest():\n"
                      "    return 0 if 1 + 1 == 2 else 1\n"
                      "if __name__ == '__main__':\n"
                      "    sys.exit(_selftest())\n", encoding="utf-8")
        underscored, _ = executed_lines(tp.name, 60)
    finally:
        tp.unlink(missing_ok=True)
        _backup_path(tp).unlink(missing_ok=True)
        del INVOKE[tp.name]
    ok7 = (with_arg == {3} and underscored == {3} and never is None
           and r7.get("verdict") == "NO_REACH_TRACE")
    print(f"    {'PASS' if ok7 else 'FAIL'}: 帶參數的 selftest 追到 {with_arg}(應 {{3}})、"
          f"`_selftest` 追到 {underscored}(應 {{3}})、"
          f"從未呼叫 -> {never_why!r}、窮舉判定 {r7.get('verdict')}(應 NO_REACH_TRACE)")
    if not ok7:
        fails.append(f"落點追蹤不對:{with_arg} / {never_why} / {r7.get('verdict')}")

    print("\n(8) artifacts 探針:selftest 逃掉但產物漂移 -> 由 artifacts 軸覆蓋;對照組不同就不啟用")
    # 前提:f 裡恰好 4 個可達產品碼突變點。`>` 反轉讓 selftest 失敗(抓到);`3 -> 4` 讓
    # selftest 照過、產物卻由 15 變 20(artifacts 抓到);`1 -> 2` 與 `else 0 -> 1` 對 f(5)
    # 沒有影響(真逃逸)。三種結果各至少一個,判準才分得出來。
    ap_tool = TOOLS / "_art_probe.py"
    art = TOOLS / "_art_probe.json"
    ap_tool.write_text(
        "import json, sys\n"
        "def f(a):\n"
        "    return a * 3 if a > 1 else 0\n"
        "def selftest():\n"
        "    return 0 if f(5) > 0 else 1\n"
        "if __name__ == '__main__':\n"
        "    if sys.argv[1:] == ['--selftest']:\n"
        "        sys.exit(selftest())\n"
        "    open(sys.argv[1], 'w').write(json.dumps(f(5)))\n", encoding="utf-8")
    INVOKE[ap_tool.name] = (["--selftest"], "offline")
    rows8 = [(art.relative_to(ROOT).as_posix(), ap_tool.name, ["{out}"], "bytes")]
    try:
        art.write_text("15", encoding="utf-8")
        r8 = test_tool(ap_tool.name, tries=0, timeout=60, exhaustive=True, artifact_rows=rows8)
        art.write_text("999", encoding="utf-8")     # 對照組:未突變時就不相同
        r8b = test_tool(ap_tool.name, tries=0, timeout=60, exhaustive=True, artifact_rows=rows8)
    finally:
        for p in (ap_tool, art, _backup_path(ap_tool)):
            p.unlink(missing_ok=True)
        del INVOKE[ap_tool.name]
    line8 = "f|return a * 3 if a > 1 else 0|"
    esc8 = sorted(e["key"] for e in r8.get("reachable_escape_details", []))
    esc8b = [e["key"] for e in r8b.get("reachable_escape_details", [])]
    ok8 = (r8.get("covered_by_artifacts") == [line8 + "int 3->4#0"]
           and esc8 == sorted([line8 + "int 1->2#0", line8 + "int 0->1#0"])
           and r8.get("reachable_attempted") == 4 and r8.get("reachable_caught") == 1
           and not r8b.get("covered_by_artifacts")
           and "不啟用" in (r8b.get("artifact_probe") or "")
           and line8 + "int 3->4#0" in esc8b)
    print(f"    {'PASS' if ok8 else 'FAIL'}: 覆蓋 {r8.get('covered_by_artifacts')}(應只有 3->4)、"
          f"逃逸 {len(esc8)}(應 2)、selftest 抓到 {r8.get('reachable_caught')}/"
          f"{r8.get('reachable_attempted')}(應 1/4);對照組:覆蓋 {r8b.get('covered_by_artifacts')}"
          f"(應空)、3->4 回到逃逸={line8 + 'int 3->4#0' in esc8b}")
    if not ok8:
        fails.append(f"artifacts 探針判定不對:{r8.get('covered_by_artifacts')} / {esc8} / "
                     f"{r8b.get('artifact_probe')}")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(正向控制 + 負向控制(含『0 分的原因』檢定)+ "
          "還原驗證 + 落點分類的成對案例與非平凡性控制 + 穩定鍵抽樣(含依編號的對照)+ "
          "窮舉可重現與登錄表三態 + 帶參數/未呼叫的落點追蹤)。")
    return 0


EQUIVALENTS = ROOT / "docs" / "data" / "equivalent_mutants.json"


def load_equivalents(path: Path = EQUIVALENTS) -> dict[str, dict[str, dict]]:
    """讀等價突變登錄表,回傳 {工具: {穩定鍵: 條目}}。

    檔案不存在 = 空登錄表;格式錯、缺理由、重複鍵一律丟例外 —— 讀不懂的登錄表
    不能被當成「沒有等價突變」,那會把錯誤變成安靜的全部重報。

    `kind`(預設 equivalent):
      equivalent  任何輸入下行為都不變(數學、函式庫行為、呼叫形狀實測)。
      cosmetic    行為**有變**,但只變在給人看的診斷文字(訊息截斷長度、顯示格式),
                  不影響資料、exit code 或任何被程式讀取的輸出。刻意不釘:為它寫斷言
                  就是釘一個不承重的常數。它不是等價,所以必須分開標記。
      tuning      政策性數值(逾時秒數、健全性下限這類),±1 只在極端情形行為才不同,
                  而且沒有「正確值」可言,只有「夠寬鬆」。同樣不是等價,分開標記。
    三者一樣受檢:被 selftest 或 artifacts 軸抓到即登錄錯誤,找不到即過期。
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict]] = {}
    for e in data["entries"]:
        if not (e.get("tool") and e.get("key") and e.get("reason") and e.get("evidence")):
            raise ValueError(f"等價突變條目缺欄位(tool/key/reason/evidence 皆必填):{e}")
        if e.get("kind", "equivalent") not in ("equivalent", "cosmetic", "tuning"):
            raise ValueError(f"等價突變條目的 kind 只能是 equivalent、cosmetic 或 tuning:{e}")
        slot = out.setdefault(e["tool"], {})
        if e["key"] in slot:
            raise ValueError(f"等價突變條目重複:{e['tool']} {e['key']}")
        slot[e["key"]] = e
    return out


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
    ap.add_argument("--exhaustive", action="store_true",
                    help="不抽樣:selftest 執行得到的產品碼上每個突變點都測。結果只取決於"
                         "原始碼、可重現、可歸零;有未登錄的逃逸、登錄表錯誤或過期時 exit 1")
    ap.add_argument("--equivalents", default=str(EQUIVALENTS),
                    help="等價突變登錄表(預設 docs/data/equivalent_mutants.json)")
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

    equivalents = load_equivalents(Path(a.equivalents))
    if a.exhaustive:
        _vg()   # 在任何突變之前載入 artifacts 比對邏輯(見 _vg 的說明)
    names = [a.tool] if a.tool else [
        k for k, (_, needs) in sorted(INVOKE.items())
        if needs == "offline" or (needs == "ghidra" and (a.include_ghidra and not a.offline))]
    rows = []
    passes = 1 if a.exhaustive else a.passes
    for n in names:
        if not (TOOLS / n).exists():
            print(f"  {n:<40} 檔案不存在,跳過")
            continue
        best = None
        caught_total = attempted_total = 0
        reach_caught_total = reach_attempted_total = 0
        escapes_all: dict[str, dict] = {}
        contradicted: set[str] = set()
        covered_all: set[str] = set()
        for k in range(passes):
            r = test_tool(n, a.tries, a.timeout, seed=a.seed + k,
                          exhaustive=a.exhaustive, equivalents=equivalents)
            caught_total += r.get("mutations_caught", 0)
            attempted_total += r.get("mutations_attempted", 0)
            reach_caught_total += r.get("reachable_caught", 0)
            reach_attempted_total += r.get("reachable_attempted", 0)
            for e in r.get("reachable_escape_details", []):
                escapes_all.setdefault(e["key"], e)
            contradicted.update(r.get("registry_contradicted", []))
            covered_all.update(r.get("covered_by_artifacts", []))
            # 跨輪取最好的判定:任何一輪抓到就是有鑑別力(WEAK 只在全部輪都 0 時成立)
            if best is None or (r["verdict"] == "DISCRIMINATING" and best["verdict"] != "DISCRIMINATING"):
                best = r
        best["mutations_caught"], best["mutations_attempted"] = caught_total, attempted_total
        # 2026-09-11:`reachable_*` 先前只累加在單輪的 r 裡,跨輪沒有合併,所以
        # `--passes>1` 時報表引用的是**最後留下那一輪**的可達數,與 caught_total
        # 的口徑不一致。既然要把它升成標題數字,口徑就必須對齊。
        best["reachable_caught"] = reach_caught_total
        best["reachable_attempted"] = reach_attempted_total
        # 逃逸同理:原本只留「最好那一輪」的,其他輪找到的線索被丟掉。依穩定鍵跨輪去重。
        best["reachable_escape_details"] = list(escapes_all.values())
        best["reachable_escapes"] = [f"L{e['line']}: {e['what']}" for e in escapes_all.values()]
        best["registry_contradicted"] = sorted(contradicted)
        best["covered_by_artifacts"] = sorted(covered_all)
        best["passes"] = passes
        rows.append(best)
        v = best["verdict"]
        reach = best.get("reachable_attempted") or 0
        reach_ok = best.get("reachable_caught") or 0
        # 2026-09-11:標題數字改成**可達比例**。原本印的是 `caught/tries`(例如 4/12),
        # 但那個分母是「亂數突變落在哪」,不是「selftest 該負責的範圍」—— 實測
        # `verify_address_citations.py` 的 4/12 看起來很差,真相是 12 個突變裡只有 3 個
        # 落在 selftest 執行得到的行,而那 3 個**全部被抓到**(3/3)。
        # 把 artifact 的形狀當成品質分數,是本專案已經踩過的形狀
        # (見 feedback_score_can_measure_the_artifacts_shape)。原始數字沒有拿掉,
        # 降級成次要資訊。
        if attempted_total:
            head = (f"可達突變 {reach_ok}/{reach} 抓到" if reach
                    else "可達突變 0 個(本輪對品質未提供證據)")
            tail = (f"全部 {caught_total}/{attempted_total}"
                    + (f",{a.passes} 輪累計" if a.passes > 1 else "")
                    + f";其餘 {attempted_total - reach} 個落在 selftest 執行不到的行")
            extra = f"{head}({tail})"
        else:
            extra = best.get("detail", "")
        print(f"  {n:<40} {v:<16} {extra}")
        for e in best.get("reachable_escapes", []):
            print(f"      逃掉但執行得到:{e}")
        if best.get("equivalent_escapes"):
            print(f"      已登錄的等價突變 {len(best['equivalent_escapes'])} 個(不計入逃逸)")
        if best.get("covered_by_artifacts"):
            print(f"      selftest 逃掉、但 artifacts 軸抓到 {len(best['covered_by_artifacts'])} 個"
                  f"(突變狀態下重生產物漂移或無法執行)")
        if best.get("artifact_probe"):
            print(f"      ** {best['artifact_probe']}")
        for key in best.get("registry_contradicted", []):
            print(f"      ** 登錄為等價卻被抓到(登錄表錯誤):{key}")
        for key in best.get("registry_stale", []):
            print(f"      ** 登錄表條目在窮舉時找不到(已過期):{key}")
    weak = [r["tool"] for r in rows if r["verdict"] == "WEAK"]
    unreach = [r["tool"] for r in rows if r["verdict"] == "UNREACHABLE_SAMPLE"]
    bad = [r["tool"] for r in rows if r["verdict"] == "BASELINE_FAIL"]
    noreach = [r["tool"] for r in rows if r["verdict"] == "NO_REACH_TRACE"]
    good = sum(1 for r in rows if r["verdict"] == "DISCRIMINATING")
    print(f"\n共 {len(rows)} 個工具:有鑑別力 {good} / 弱 {len(weak)} / "
          f"樣本沒落到可測範圍 {len(unreach)} / 基準就失敗 {len(bad)}"
          + (f" / 落點無法追蹤 {len(noreach)}" if noreach else ""))
    # 「67 支全部有鑑別力」是真的,但它與「有 24 支存在逃掉的可達突變」可以同時為真。
    # 只印前者會讓後者消失 —— 那正是本專案反覆踩到的形狀,所以兩個數字並列,
    # 而且把可達逃逸總數印出來:它是**可以歸零**的,不像判定欄位永遠好看。
    esc_rows = [r for r in rows if r.get("reachable_escapes")]
    esc_total = sum(len(r.get("reachable_escapes") or []) for r in rows)
    cov_total = sum(len(r.get("covered_by_artifacts") or []) for r in rows)
    if cov_total:
        print(f"  selftest 逃掉、但 artifacts 軸在突變狀態下抓到:共 {cov_total} 個"
              f"(不計入逃逸;每次窮舉重新實證,不靠登錄)")
    if esc_rows:
        print(f"  仍有**逃掉但確實被執行到**的突變:{len(esc_rows)} 支工具、共 {esc_total} 個"
              f"(判定欄位看不到這個;逐支明細見上方「逃掉但執行得到」)")
        worst = sorted(esc_rows, key=lambda r: -len(r["reachable_escapes"]))[:5]
        print("    最多的幾支:"
              + "、".join(f"{r['tool']}×{len(r['reachable_escapes'])}" for r in worst))
        # 「執行得到」不等於「改了看得出來」。實測 verify_truncation_robustness.py 的
        # 6 個可達突變全部是**等價突變**:把 DECODERS 登錄表裡的 576->577、24->25、
        # filler*64->65 改掉之後,該工具正常執行的輸出**逐位元組相同** —— 沒有任何
        # selftest 能抓到一個不改變行為的改動。把這種當成待辦會重演 2026-09-10 那次
        # 為了一個不可能動的分數白寫一小時測試的事。
        print("    注意:逃掉不一定等於缺口。先確認它是不是**等價突變** —— 對該工具做一次"
              "正常執行,突變前後輸出若逐位元組相同,就沒有任何 selftest 抓得到它。")
    else:
        print("  沒有任何「逃掉但確實被執行到」的突變。")
    if unreach:
        print(f"  樣本沒落到可測範圍(這一輪對 selftest 品質未提供證據,"
              f"不是「弱」):{unreach}")
    if weak:
        print(f"  弱(值得人工檢視,不等於壞):{weak}")
    if bad:
        print(f"  基準就失敗(必須先修):{bad}")
    if noreach:
        print(f"  落點無法追蹤(不知道 ≠ 沒有可達突變,先修追蹤):{noreach}")
    contra_total = sum(len(r.get("registry_contradicted") or []) for r in rows)
    stale_total = sum(len(r.get("registry_stale") or []) for r in rows)
    if contra_total or stale_total:
        print(f"  等價突變登錄表有問題:登錄錯誤 {contra_total}、過期 {stale_total}(明細見上方 **)")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  JSON -> {a.json}")
    if a.exhaustive:
        failed = bool(bad or noreach or esc_total or contra_total or stale_total)
        print(f"  窮舉結論:{'未歸零' if failed else '歸零'}(未登錄的可達逃逸 {esc_total}、"
              f"登錄錯誤 {contra_total}、過期 {stale_total}、落點無法追蹤 {len(noreach)}、"
              f"基準失敗 {len(bad)})")
        return 1 if failed else 0
    # 登錄為等價卻被抓到,代表登錄表的主張是錯的,抽樣模式碰到也要失敗。
    return 1 if (bad or contra_total) else 0


if __name__ == "__main__":
    raise SystemExit(main())
