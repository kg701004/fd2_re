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
import functools
import json
import locale
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

RULES = ("docstring", "correctness", "console", "shebang", "lazy_import", "regenerable",
         "exit_code")

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


def docstring_console_risk(src: str, encoding: str | None = None) -> str | None:
    """`print(__doc__)` + docstring 含主控台編不出的字元 = 執行即崩。

    `encoding` 不給就用本機 locale(實際使用情境);給了就用指定的編碼。
    2026-09-09 加這個參數是因為第 (2d) 題的**正對照原本依賴執行環境**:在
    `PYTHONUTF8=1` / `python -X utf8` 之下 `↔` 編得出來,偵測器正確地什麼都
    不報,而斷言「必須抓到」於是失敗,訊息卻寫得像偵測邏輯壞了。判準本身
    (「這份 docstring 在編碼 E 下印得出來嗎」)跟跑測試的機器無關,不該由
    機器的 locale 決定測得到測不到。

    2026-09-08:`verify_docs_match_cli.console_encoding_risks()` 只看 print 的
    **字面字串**,所以完全看不到這條路徑。實測 `disasm_le.py` 與 `le_xref.py`
    的 docstring 都含 `↔`,而兩支在無參數時都會 `print(__doc__)` —— 在 cp950
    主控台上那一行直接 UnicodeEncodeError,看起來像「工具壞了」。這正是本 repo
    已經修過 15 支的同一個類別,只是換了一條路徑進來。
    """
    if "reconfigure" in src:
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    doc = ast.get_docstring(tree) or ""
    if not doc:
        return None
    prints_doc = any(
        isinstance(n, ast.Call) and getattr(n.func, "id", None) == "print"
        and any(isinstance(a, ast.Name) and a.id == "__doc__" for a in n.args)
        for n in ast.walk(tree))
    if not prints_doc:
        return None
    enc = encoding or locale.getpreferredencoding(False)
    try:
        doc.encode(enc)
    except (UnicodeEncodeError, LookupError):
        bad = sorted({c for c in doc if not _encodable(c, enc)})
        return (f"print(__doc__) 但 docstring 含 {enc} 編不出的字元 "
                f"{bad[:5]} —— 無參數執行時會 UnicodeEncodeError")
    return None


def _encodable(ch: str, enc: str) -> bool:
    try:
        ch.encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


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


def discarded_exit_code(src: str) -> list[str]:
    """`__main__` 區塊裡把 `main()`/`selftest()` 的離開碼丟掉的地方。

    2026-09-10 實際發生:`sync_native_treasures.py` 與 `sync_native_field_events.py`
    的 `__main__` 是裸呼叫 `main()`,而 `main()` 會 `return selftest()`。於是
    `--selftest` **印出 SELFTEST FAILED 之後仍然 exit 0** —— 所有以離開碼判斷的
    呼叫端(verify_all_tools 的 selftest 層、突變測試的基準與捕捉判定)都只看到通過,
    那兩支工具因此長期被判 WEAK:它們的 selftest 根本不可能失敗。

    這是「管線吃掉離開碼」那一類的靜態版本,而且更隱蔽:訊息還是照印,只有離開碼
    是啞的。故意只在 `main()` 真的會回傳值時才報,避免對回傳 None 的工具誤報。
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    # 只看 `main`/`selftest` —— 依慣例承載離開碼的就這兩個。第一版寫成「任何會
    # 回傳值的函式」,立刻誤報 `gtl2wopl.py`:它的 `build_wopl()` 回傳的是
    # `(n_mel, n_perc)` 這種資料,丟掉完全正確,而且它的 selftest 路徑本來就寫了
    # `sys.exit(selftest())`。丟掉資料回傳值不是缺陷,丟掉離開碼才是。
    EXIT_CARRIERS = ("main", "selftest")
    returns_value = {
        n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in EXIT_CARRIERS
        and any(isinstance(s, ast.Return) and s.value is not None for s in ast.walk(n))
    }
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.If) and "__main__" in ast.dump(node.test)):
            continue
        for stmt in node.body:
            if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                    and getattr(stmt.value.func, "id", None) in returns_value):
                out.append(f"__main__ 裸呼叫 {stmt.value.func.id}(),"
                           f"離開碼被丟棄(失敗仍會 exit 0)")
    return out


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
        for detail in discarded_exit_code(src):
            out.append({"kind": "tool", "name": p.name, "rule": "exit_code",
                        "detail": detail})
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
        doc_risk = docstring_console_risk(src)
        if doc_risk and p.name not in risky:
            out.append({"kind": "tool", "name": p.name, "rule": "console",
                        "detail": doc_risk})
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


REFERENCE_FILES = ROOT / "docs" / "data" / "fd2-reference-files.json"


@functools.lru_cache(maxsize=1)
def _repo_size_index() -> dict[int, tuple[Path, ...]]:
    """檔案大小 -> repo 內該大小的檔案。整棵樹只走一次。

    走一次約 4.6 秒(extracted/ 底下有上萬個檔),而 _proves_lost_input 是
    每個永久豁免項目呼叫一次的——同一輪裡重複走樹就是上一批剛修過的那種
    效能回歸。索引與要找哪個 md5 無關,所以算一次就好。
    """
    idx: dict[int, list[Path]] = {}
    for f in ROOT.rglob("*"):
        if ".git" in f.parts:
            continue
        try:
            if f.is_file():
                idx.setdefault(f.stat().st_size, []).append(f)
        except OSError:
            continue
    return {k: tuple(v) for k, v in idx.items()}


def _repo_files_of_size(size: int | None) -> tuple[Path, ...]:
    if not size:
        return ()
    return _repo_size_index().get(size, ())


def _proves_lost_input(name: str) -> tuple[bool, str]:
    """證明「這個產物的產生器輸入已經不存在」——重生比對這條路本身不適用。

    這跟 `no_generator` 是不同的情況:產生器可能還在(甚至還跑得動),但它
    吃的那個位元組序列已經沒了,所以「重跑一次比對輸出」在定義上做不到。
    `docs/data/ida/fd2_xrefs.json` 是已知的一例——它記錄的輸入是
    357074 bytes 的舊版 FD2.EXE,而現行的是 509158 bytes,兩者是不同的
    二進位檔;使用者已於 2026-09-09 確認舊版永久刪除。裝上 IDA 也解不了,
    因為缺的是輸入不是工具。

    宣稱是可證偽的,而且有三層:
      1. 產物自己必須記錄 `input_md5`——沒有記錄就無從主張;
      2. 那個 md5 必須正好是 `fd2-reference-files.json` 裡某個檔案的
         **previous_edition**(已退役的版本),而不是現行基準。若日後基準
         改回去、或那筆記錄被移除,這裡立刻失敗;
      3. repo 內若出現任何一份 md5 相符的檔案,宣稱立刻失敗——輸入回來了,
         就該回頭重生比對。

    要建立一份**現行版本**的等價產物是另一件事,不是這一項的重生。
    """
    import hashlib
    p = ROOT / name
    if not p.exists():
        return False, "檔案不存在"
    try:
        art = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                      # noqa: BLE001
        return False, f"讀不出來:{type(exc).__name__}"
    md5 = art.get("input_md5") or art.get("source_md5")
    size = art.get("input_size") or art.get("source_size")
    if not md5:
        return False, "產物沒有記錄 input_md5,無從主張輸入已遺失"
    if not REFERENCE_FILES.exists():
        return False, f"找不到 {REFERENCE_FILES.name},無法核對版本身分"
    ref = json.loads(REFERENCE_FILES.read_text(encoding="utf-8"))
    retired, current = set(), set()
    for f in ref.get("files", []):
        if f.get("md5"):
            current.add(f["md5"])
        prev = f.get("previous_edition") or {}
        if prev.get("md5"):
            retired.add(prev["md5"])
    if md5 in current:
        return False, f"{md5[:8]} 是**現行基準**,輸入還在——請直接重生比對"
    if md5 not in retired:
        return False, f"{md5[:8]} 不在參考檔登錄的已退役版本裡,身分不明"
    for f in _repo_files_of_size(size):
        try:
            if hashlib.md5(f.read_bytes()).hexdigest() == md5:
                return False, f"{f.relative_to(ROOT)} 的 md5 就是它——輸入回來了"
        except OSError:
            continue
    return True, f"輸入 {md5[:8]}({size} bytes)是已退役版本,repo 內不存在"


def _json_string_values(node) -> list[str]:
    """遞迴取出所有字串**值**(不含 key)。判準只看值,key 名稱不算自述。"""
    out: list[str] = []
    stack = [node]
    while stack:
        o = stack.pop()
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return out


def _proves_remake_derived(name: str) -> tuple[bool, str]:
    """證明「這個產物是已移除的 remake 產生的」——所以它沒有、也不會再有產生器。

    這跟 `no_generator` 與 `lost_input`都不同:產生器**曾經存在**(是 remake 的
    Go 測試,例如 `TestCampaignTownPreparationInputTrace`),但整個 `remake/` 已於
    2026-09-02 依使用者指示移除,理由是「remake 驗證過的資料本身就有問題,驗出來的
    也會有問題」。所以這些檔案既不能重生,其內容依專案自己的規則也不算證據。
    刪不刪是另一件事——它們是 worklist 既有記錄的一部分,保留但標明來源。

    宣稱是可證偽的,三層:
      1. 檔案必須**自述**為 remake 產出(某個字串**值**裡提到 remake,例如
         `source_campaign: remake/...`、`format: remake-json-v1`、
         `artifacts: ...-remake.png`)。只看值不看 key,免得靠欄位名蒙混;
      2. repo 內不得存在 `remake/` 目錄——它一旦回來,這些就重新變成可重生的,
         宣稱必須立刻失敗,逼人回頭處理;
      3. 不得有任何工具在寫入語境提到這個檔名(與 `no_generator` 同一條判準)。
    """
    import verify_generated_artifacts as vg
    p = ROOT / name
    if not p.exists():
        return False, "檔案不存在"
    try:
        art = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                      # noqa: BLE001
        return False, f"讀不出來:{type(exc).__name__}"
    marks = [s for s in _json_string_values(art) if "remake" in s.lower()]
    if not marks:
        return False, "檔案沒有自述為 remake 產出,不能用這個理由豁免"
    if (ROOT / "remake").exists():
        return False, "remake/ 回來了 —— 這些產物重新變成可重生的,請回頭處理"
    for tool, arts in vg.discover():
        if name in arts:
            return False, f"{tool} 看起來會產生它 —— 宣稱不成立"
    return True, f"自述 remake 產出({marks[0][:44]}),remake/ 已移除且無產生器"


PERMANENT_PROOFS = {
    "ida_embedded": _proves_ida_embedded,
    "no_generator": _proves_no_generator,
    "lost_input": _proves_lost_input,
    "remake_derived": _proves_remake_derived,
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

    # 2026-09-09:上面那條只比「未涵蓋」的原始集合,兩邊一直是一致的——但**扣掉永久
    # 豁免之後的「實際待處理」曾經不一致**:本檔說 0 筆,而 vg 說 7 個,因為 vg 的
    # `no_generator_set()` 只認 `no_generator` 一種永久豁免,後來新增的 `lost_input`
    # 與 `remake_derived` 它看不到。兩支工具對**同一批檔案**給出不同答案,而它們本來
    # 就是設計成互相牽制的。原始集合一致掩蓋了這件事,所以這裡改比最終那個數字。
    exempt = {e["name"] for e in load_baseline().get("entries", [])
              if e.get("rule") == "regenerable" and e.get("permanent")}
    mine_pending = mine - exempt
    vg_pending = set(missing) - vg.no_generator_set()
    out.append((mine_pending == vg_pending,
                f"與 verify_generated_artifacts 的**實際待處理**一致"
                f"(本工具 {len(mine_pending)} 筆 / vg {len(vg_pending)} 個)"
                + (f":只在一邊的 {sorted(mine_pending ^ vg_pending)[:3]}"
                   if mine_pending != vg_pending else "")))

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

    print("\n(2c2) `_encodable` 必須真的分辨得出「可編」與「不可編」,不能恆為同一個答案")
    # 現有的 (2d) 只驗 docstring_console_risk 的 is-None/is-not-None,兩種情況都
    # 至少有一個字元判定 True 或至少一個判定 False,不管 _encodable 內部答案對不對
    # 都能通過 —— 因為它只在「整份 docstring 編不出來」時才被呼叫,這時不論每個
    # 字元各自真假,`bad` 集合是否為空的結論不變。直接測 _encodable 本身。
    ok2c2 = _encodable("a", "cp950") is True and _encodable("↔", "cp950") is False
    print(f"    {'PASS' if ok2c2 else 'FAIL'}: ASCII 'a' 可編={_encodable('a', 'cp950')}(應 True)、"
          f"'↔' 可編={_encodable(chr(0x2194), 'cp950')}(應 False)")
    if not ok2c2:
        fails.append("_encodable 對可編/不可編字元給出同一個答案")

    print("\n(2d) docstring 編碼風險:print(__doc__) 這條路徑的配對控制")
    # verify_docs_match_cli 只看 print 的字面字串,看不到 print(__doc__)。
    # disasm_le.py / le_xref.py 的 docstring 都含 `↔`,兩支無參數執行時都會崩,
    # 而 console 規則報 0 筆 —— 用修正前的真實形狀當正對照,不是合成案例。
    pre = '"""說明 linear ↔ file 的對應。"""\nimport sys\ndef main():\n    print(__doc__)\n'
    post = ('"""說明 linear ↔ file 的對應。"""\nimport sys\n'
            'sys.stdout.reconfigure(encoding="utf-8")\ndef main():\n    print(__doc__)\n')
    plain = '"""Plain ASCII doc."""\ndef main():\n    print(__doc__)\n'
    noprint = '"""說明 linear ↔ file 的對應。"""\ndef main():\n    return 0\n'
    # 編碼寫死成 cp950。這一題問的是判準——「這份 docstring 在 cp950 下印得
    # 出來嗎」——而那跟跑測試的機器用什麼 locale 無關。原本用環境 locale,於是
    # 在 `python -X utf8` 下 `↔` 編得出來、偵測器正確地不報,斷言卻失敗。
    okA = docstring_console_risk(pre, "cp950") is not None
    okB = docstring_console_risk(post, "cp950") is None
    okC = docstring_console_risk(plain, "cp950") is None
    okD = docstring_console_risk(noprint, "cp950") is None
    # 非平凡性:同一份會被 cp950 擋下的原始碼,在 utf-8 下必須**不**被報——
    # 否則「抓到」可能只是因為它永遠都報。
    okE = docstring_console_risk(pre, "utf-8") is None
    ok2d = okA and okB and okC and okD and okE
    print(f"    {'PASS' if okA else 'FAIL'}: 修正前的真實形狀(cp950)-> 抓到")
    print(f"    {'PASS' if okB else 'FAIL'}: 已 reconfigure -> 不算")
    print(f"    {'PASS' if okC else 'FAIL'}: 純 ASCII docstring -> 不算")
    print(f"    {'PASS' if okD else 'FAIL'}: 沒有 print(__doc__) -> 不算")
    print(f"    {'PASS' if okE else 'FAIL'}: 同一份原始碼在 utf-8 下 -> 不算(非平凡性)")
    if not ok2d:
        fails.append(f"docstring 編碼偵測失衡:cp950 抓到={okA}、utf-8 不報={okE}、"
                     f"三種不該報的分別為 {okB}/{okC}/{okD}")

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

    print("\n(3b2) `_proves_ida_embedded` 的診斷訊息必須真的是**最後一行**,不是倒數第二行")
    # (3b) 只驗 prover(...) 的布林值,detail 字串從沒被比對過 —— 該函式的
    # ok 判定(returncode/ModuleNotFoundError/ida 三個條件)根本不依賴 tail,
    # 所以 tail[-1] 改成 tail[-2] 不會讓 (3b) 有任何感覺。直接對真實 ida_* 檔案
    # 跑一次,拿 detail 與獨立重算的最後一行交叉比對。
    ida_names = [e["name"] for e in perm if e.get("permanent") == "ida_embedded"]
    if ida_names:
        name = ida_names[0]
        ok3c_ok, detail = _proves_ida_embedded(name)
        import subprocess as _sp
        rp = _sp.run([sys.executable, str(TOOLS / name)], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", timeout=120)
        err_lines = [l for l in (rp.stderr or "").strip().splitlines() if l.strip()]
        want_last = err_lines[-1][:70] if err_lines else f"rc={rp.returncode}"
        ok3c = ok3c_ok and detail == want_last
        print(f"    {'PASS' if ok3c else 'FAIL'}: {name} 的 detail={detail!r},"
              f"獨立重算的最後一行={want_last!r}")
        if not ok3c:
            fails.append(f"_proves_ida_embedded 的 detail 不是最後一行:{detail!r} != {want_last!r}")
    else:
        print("    SKIP: 基準線裡沒有 ida_embedded 條目")

    print("\n(3c) lost_input 的配對控制:三種不成立的情況都必須被擋下")
    # 正例只證明它會說 True。這三個反例來自 repo 裡真的存在的產物,分別對應
    # 「輸入還在」「沒有記錄輸入」「身分不明」——少了它們,一個永遠回 True 的
    # 實作也會通過上一題。
    lost_cases = [
        ("docs/data/ida/fd2_xrefs.json", True, "輸入是已退役版本"),
        ("docs/data/exe_tables/native_unit_tables.json", False, "輸入是現行基準"),
        ("docs/data/glyph_map.json", False, "沒有記錄 input_md5"),
    ]
    lost_bad = []
    for art, want, why in lost_cases:
        if not (ROOT / art).exists():
            lost_bad.append(f"{art} 不存在")
            continue
        got, detail = _proves_lost_input(art)
        if got != want:
            lost_bad.append(f"{art}({why}): 得 {got},應 {want} —— {detail}")
    both_poles = {w for _, w, _ in lost_cases} == {True, False}
    ok3c = not lost_bad and both_poles
    print(f"    {'PASS' if ok3c else 'FAIL'}: 3 個真實產物"
          + ("全部相符,且正反例俱在" if ok3c else f",不符 {lost_bad}"))
    if not ok3c:
        fails.append(f"lost_input 配對控制不成立:{lost_bad}")
    elif not perm:
        fails.append("基準線裡沒有任何永久豁免 —— 若確實沒有,請移除這條檢查")

    print("\n(3d) remake_derived 也要配對:真的是 remake 產出的過、原版側的必須不過")
    # 這 6 個 trace 的 `source_campaign` 指向 remake/、圖是 *-remake.png、
    # `format` 寫 remake-json-v1,而產生它們的 remake Go 測試已隨目錄一起移除。
    # 負例挑原版側的產物:它們同樣沒有 remake 出身,絕不能靠這個理由被豁免。
    remake_cases = [
        ("docs/data/ui-traces/town-shop-ch02.json", True, "source_campaign 指向 remake/"),
        ("docs/data/ui-traces/save-town-boundary-ch02.json", True, "format = remake-json-v1"),
        ("docs/data/native_argcounts.json", False, "原版 EXE 推導,與 remake 無關"),
        ("docs/data/glyph_map.json", False, "原版側的人工 RE 記錄"),
    ]
    rd_bad = []
    for art, want, why in remake_cases:
        if not (ROOT / art).exists():
            rd_bad.append(f"{art} 不存在")
            continue
        got, detail = _proves_remake_derived(art)
        if got != want:
            rd_bad.append(f"{art}({why}): 得 {got},應 {want} —— {detail}")
    ok3d = not rd_bad and {w for _, w, _ in remake_cases} == {True, False}
    print(f"    {'PASS' if ok3d else 'FAIL'}: {len(remake_cases)} 個真實產物"
          + ("全部相符,且正反例俱在" if ok3d else f",不符 {rd_bad}"))
    if not ok3d:
        fails.append(f"remake_derived 配對控制不成立:{rd_bad}")

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

    print("\n(5b) exit_code 規則的五個成對案例(丟掉離開碼要報,丟掉資料不報)")
    # 2026-09-10 真的發生過:兩支工具的 __main__ 裸呼叫 main(),於是 --selftest
    # 印出 SELFTEST FAILED 仍然 exit 0,以離開碼判斷的呼叫端全都只看到通過。
    # 第一版規則寫成「任何會回傳值的函式」,立刻誤報 gtl2wopl 的資料回傳 ——
    # 那個形狀就放在下面當負向控制,免得規則為了抓真陽性而變得過寬。
    exit_cases = [
        ("裸呼叫 main(),main 回傳離開碼", True,
         "def main():\n    return 1\nif __name__ == '__main__':\n    main()\n"),
        ("raise SystemExit(main())", False,
         "def main():\n    return 1\nif __name__ == '__main__':\n"
         "    raise SystemExit(main())\n"),
        ("裸呼叫資料函式(gtl2wopl 的形狀)", False,
         "def build(x):\n    return (1, 2)\nif __name__ == '__main__':\n    build(3)\n"),
        ("main 回傳 None,裸呼叫", False,
         "def main():\n    print('x')\nif __name__ == '__main__':\n    main()\n"),
        ("裸呼叫 selftest()", True,
         "def selftest():\n    return 1\nif __name__ == '__main__':\n    selftest()\n"),
    ]
    wrong = [lbl for lbl, want, src in exit_cases
             if bool(discarded_exit_code(src)) != want]
    ok5b = not wrong
    print(f"    {'PASS' if ok5b else 'FAIL'}: {len(exit_cases)} 個案例"
          + ("全部正確" if ok5b else f",判錯 {wrong}"))
    if not ok5b:
        fails.append(f"exit_code 規則的成對案例判錯:{wrong}")

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
          "+ lost_input / remake_derived 兩組永久豁免證明的正反例 "
          "+ exit_code 規則的五個成對案例 + 非恆假 + 三項跨工具交叉驗證)。")
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
