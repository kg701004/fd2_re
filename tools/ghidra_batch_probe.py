#!/usr/bin/env python3
"""fd2_re — Ghidra 批次探測 wrapper。

背景:過去每次要查一個新位址(反組譯/decompile/xref/function bounds/raw bytes),都要寫一支
新的 `GhidraScript` 子類別(見 `FD2_ghidra_projects/Probe*.java`,已累積上百支),然後跑一次
`analyzeHeadless`——每次都重付 JVM 啟動 + project 載入的固定成本(實測約 2-4 秒 headless
startup + project open,批次跑一次能省下這筆成本 N-1 次)。

這支工具改成「一次 JVM 啟動,查一整份清單」:你把要查的位址都寫進一份 JSON 清單
(`--queries`),本工具組出正確的 `analyzeHeadless` command line 並執行 Ghidra 端的
`FD2_ghidra_projects/ProbeBatch.java`(通用 GhidraScript,支援 disasm / decompile / xref_to /
xref_from / function_bounds / bytes 六種 action),把結果寫成一份 JSON(`--output`)。

用法:
    python tools/ghidra_batch_probe.py --queries queries.json --output results.json
    python tools/ghidra_batch_probe.py --queries queries.json --output results.json --quiet
    python tools/ghidra_batch_probe.py --queries queries.json --output results.json \\
        --ghidra "C:/tools/ghidra_12.1.2_PUBLIC" \\
        --project-dir "C:/Users/kg701/Desktop/GAME/FD2_ghidra_projects" \\
        --project-name FD2Analysis3

queries.json 格式(陣列,每筆一個 query):
    [
      {"id": "q1", "address": "0x14818", "action": "disasm", "max_bytes": 480},
      {"id": "q2", "address": "0x2ff01", "action": "decompile"},
      {"id": "q3", "address": "0x53a51", "action": "xref_to"},
      {"id": "q4", "address": "0x14818", "action": "function_bounds"},
      {"id": "q5", "address": "0x24d22", "action": "xref_from"},
      {"id": "q6", "address": "0x53a51", "action": "bytes", "count": 16},
      {"id": "q7", "address": "0x205da", "action": "call_scan"},
      {"id": "q8", "address": "0x1a678", "action": "file_offset"}
    ]

action 說明(對應 ProbeBatch.java 的實作):
  - disasm:            從 address 開始,flow-directed 反組譯(仿照舊 ProbeCommand1012.java
                        的 getInstructionAt/.getNext() 手法),直到 RET / 無條件 JMP 或
                        max_bytes(預設 480)上限為止。
  - decompile:         address 所在 function 的 Ghidra decompiler 偽代碼;address 不在任何
                        已知 function 內則回傳失敗(ok=false)。
  - xref_to:           所有引用/呼叫這個位址的來源清單。
  - xref_from:         若 address 落在已知 function 內,列出該 function 整個 body 對外的所有
                        引用(呼叫/資料參照);不在 function 內則只列該單一位址自己的引用。
  - function_bounds:   address 所在 function 的名稱/起訖/大小;不在任何已知 function 內則
                        回傳 {"in_function": false}(不是失敗,是明確的空結果)。
  - bytes:              從 address 開始 N bytes(`count`,預設 32)的 hex dump,不反組譯。
  - call_scan:          (2026-08-21新增)窮舉整個程式映像(跳過重複的`.image`超集區塊),逐byte找
                        `E8`(CALL rel32)opcode、計算目標位址,回傳所有目標等於`address`的呼叫點,
                        每筆額外用 Ghidra 真實反組譯器在該位址強制解碼一次確認是不是合法 CALL 指令
                        (`confirmed_call_instruction`)。**這是`xref_to`不可靠時的替代方案**——本
                        project 的`-noanalysis`模式下,`getReferencesTo()`只找得到「剛好已經被某次
                        probe 反組譯過」的呼叫點(親測:`xref_to 0x205da`只回3筆,`call_scan`才找到
                        真正的28筆,與doc25既有記錄的「28個直接caller」精確吻合)。呼叫多、位址範圍大
                        時較慢(全EXE約需額外1-2秒),但比手動窮舉可靠。
  - file_offset:        (2026-09-06新增)把 address 換算成它在原始 FD2.EXE 檔案裡的真實offset,
                        **不是套一個固定 delta**。背景:這個LE格式執行檔用分頁表載入,實體檔案
                        裡的分頁順序跟線性記憶體位址順序不一致——親測過兩個位址只差877 bytes
                        (同一個function內),換算出的檔案offset卻差了0x600,證明「位址+常數=
                        檔案offset」這種假設在跨分頁時一定會悄悄算錯。實作上原本想用 Ghidra
                        自己的 FileBytes API(`MemoryBlockSourceInfo.getFileBytesOffset`)這個
                        「正規」做法,但親測這個專案的 loader 完全沒有填 FileBytes(每個 block
                        都回傳空的)——已改成退而求其次但**驗證有效**的做法:從 Ghidra 記憶體讀
                        `probe_length`(預設24)bytes,直接對真正的 EXE 檔案(`currentProgram.
                        getExecutablePath()`)做內容搜尋,回傳所有命中位置+是否唯一
                        (`unique`)。**命中不唯一時不要相信任何一個offset**,加大`probe_length`
                        重跑。這是本session手動驗證3個位址時用過、證實可靠的方法,現在是內建
                        action,不用再手動寫Python重複做。**注意**:`getExecutablePath()`回傳
                        的是這個Ghidra project當初import時記錄的路徑,親測是別台機器的舊路徑
                        (這台機器不存在)——這個action預設會先用它,不存在就回報清楚的note而
                        不是裝作成功;需要query帶`"exe_path"`(這台機器的真實EXE路徑,如
                        `C:/Users/kg701/Desktop/GAME/FD2/FD2.EXE`)覆寫。

輸出格式:JSON 陣列,每筆對應輸入的 "id",含 "ok"(true/false)。單一 query 失敗不會讓整批
中斷 —— 其餘 query 照跑,失敗的那筆在輸出裡帶 "error" 說明原因。

已知環境細節(踩過的坑,詳見 memory `fd2-live-ghidra-headless-probe`):
  - project 路徑一定要用絕對路徑(相對路徑 "." 開頭會被 Ghidra 拒絕)。
  - 必須 `-readOnly`(不修改唯讀 project,前一輪 forced-disassembly 這類 in-session 變更
    收尾會被丟棄)+ `-noanalysis`(project 已經分析過,不要重跑一次完整分析)。
  - `-process "FD2.EXE"` 指的是 project 內部的 program 名稱,不是檔案路徑。
  - project owner 若卡 NotOwnerException,要先取得使用者同意修改
    `FD2Analysis3.rep/project.prp` 的 OWNER 欄位(這個 repo 已經改過,通常不會再遇到)。
  - (2026-08-28新增)**必須用原生 Windows Python 執行,不能透過 WSL2 bash 呼叫**——
    `--project-dir`/`--ghidra` 預設值都是 Windows 形式路徑(`C:/...`),`analyzeHeadless.bat`
    本身也是 Windows batch。若在 WSL2 的 Python(POSIX `pathlib.Path`)下跑本工具,
    `Path("C:/Users/.../FD2_ghidra_projects")` 會被當成*相對*路徑處理(不認得磁碟機代號),
    `.exists()`檢查會在錯誤的目錄下找,產生誤導性的
    `ProbeBatch.java not found in project dir C:/...`錯誤——這不是專案真的少了這支腳本
    (它確實在`C:/Users/kg701/Desktop/GAME/FD2_ghidra_projects/ProbeBatch.java`),純粹是
    WSL2 Python 路徑解讀方式不同造成的假錯誤。正確用法:在 PowerShell/cmd 下直接
    `python tools/ghidra_batch_probe.py ...`。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_GHIDRA_INSTALL = r"C:/tools/ghidra_12.1.2_PUBLIC"
DEFAULT_PROJECT_DIR = r"C:/Users/kg701/Desktop/GAME/FD2_ghidra_projects"
DEFAULT_PROJECT_NAME = "FD2Analysis3"
DEFAULT_PROCESS_NAME = "FD2.EXE"
DEFAULT_EXE_PATH = r"C:/Users/kg701/Desktop/GAME/FD2/FD2.EXE"
SCRIPT_NAME = "ProbeBatch.java"


def build_command(
    ghidra_install: str,
    project_dir: str,
    project_name: str,
    process_name: str,
    queries_path: Path,
    output_path: Path,
) -> list[str]:
    analyze_headless = str(Path(ghidra_install) / "support" / "analyzeHeadless.bat")
    return [
        analyze_headless,
        str(Path(project_dir).resolve()).replace("\\", "/"),
        project_name,
        "-process",
        process_name,
        "-readOnly",
        "-noanalysis",
        "-scriptPath",
        str(Path(project_dir).resolve()).replace("\\", "/"),
        "-postScript",
        SCRIPT_NAME,
        str(queries_path.resolve()).replace("\\", "/"),
        str(output_path.resolve()).replace("\\", "/"),
    ]


# ===========================================================================================
# --selftest: fault-injection-style regression check, not just "did it run without an exception".
#
# Every assertion below is pinned to a SPECIFIC value independently established and verified by
# hand on 2026-09-06 (cross-checked against Capstone, against raw content-search in the actual
# EXE file, and bidirectionally -- offset-to-content-to-address as well as address-to-content-to
# -offset). If a future Ghidra upgrade, a ProbeBatch.java edit, or a different EXE copy silently
# changes any of these outputs, this catches it immediately instead of leaving future sessions to
# rediscover the same page-mapping/stale-path traps from scratch (see the "never assume a
# constant address-to-file-offset delta" lesson in this project's persistent memory).
# ===========================================================================================

def _selftest_queries() -> list[dict]:
    return [
        {"id": "st_bytes", "address": "0x1a30b", "action": "bytes", "count": 16},
        {"id": "st_disasm", "address": "0x1a30b", "action": "disasm", "max_bytes": 40},
        {"id": "st_decompile", "address": "0x16559", "action": "decompile"},
        {"id": "st_function_bounds", "address": "0x1a30b", "action": "function_bounds"},
        {"id": "st_call_scan", "address": "0x187d6", "action": "call_scan"},
        {
            "id": "st_file_offset",
            "address": "0x1a678",
            "action": "file_offset",
            "exe_path": DEFAULT_EXE_PATH,
        },
    ]


# analyzeHeadless 的 stdout/stderr 不保證是 UTF-8:Windows 端的錯誤訊息(例如「專案被鎖住」)
# 會以系統 ANSI codepage(此機為 CP950)輸出。本工具在 `-X utf8` 下跑時 `text=True` 會嚴格用
# UTF-8 解碼,一個 0xbd 就讓 wrapper 自己丟 UnicodeDecodeError——**真正的錯誤訊息因此完全看不到**,
# 症狀看起來像「Ghidra 壞了」。實際踩到過一次(2026-09-11,前一次被砍掉的 run 留下 .lock)。
# 明確指定 errors="replace":壞位元組變成 U+FFFD,訊息照樣印得出來。
PIPE_ENCODING = "utf-8"
PIPE_ERRORS = "replace"


def _run_selftest_check(name: str, condition: bool, detail: str, failures: list[str]) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + ("" if condition else f" -- {detail}"))
    if not condition:
        failures.append(f"{name}: {detail}")


def run_selftest(args: argparse.Namespace) -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ghidra_batch_probe_selftest_") as tmpdir:
        queries_path = Path(tmpdir) / "queries.json"
        output_path = Path(tmpdir) / "results.json"
        queries_path.write_text(json.dumps(_selftest_queries()), encoding="utf-8")

        cmd = build_command(
            args.ghidra, args.project_dir, args.project_name, args.process_name,
            queries_path, output_path,
        )
        print("[ghidra_batch_probe --selftest] running known-ground-truth queries...")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding=PIPE_ENCODING, errors=PIPE_ERRORS,
                                  timeout=args.timeout)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"error: could not run analyzeHeadless for selftest: {e}", file=sys.stderr)
            return 3
        if proc.returncode != 0 or not output_path.exists():
            print("error: selftest batch itself failed to run -- see output below", file=sys.stderr)
            sys.stderr.write((proc.stdout or "") + (proc.stderr or ""))
            return 3

        results = {r["id"]: r for r in json.loads(output_path.read_text(encoding="utf-8"))}

        def get(qid: str):
            r = results.get(qid)
            return r.get("result") if r and r.get("ok") else None

        # 管線解碼設定本身要有回歸檢查:這一項不碰 Ghidra,直接叫一個子行程吐出**非 UTF-8**
        # 位元組(CP950 的「專案」二字),用與 analyzeHeadless 完全相同的 subprocess 參數去讀。
        # 故障注入的形式:同一段位元組改用 errors="strict" 必須真的丟 UnicodeDecodeError——
        # 若哪天它不丟了,代表這個檢查已經測不到東西,要一起改。
        cp950 = b"\xb1M\xae\xd7 locked; see log\n"
        probe = [sys.executable, "-c",
                 "import sys; sys.stdout.buffer.write(%r)" % cp950]
        decoded = subprocess.run(probe, capture_output=True, text=True,
                                 encoding=PIPE_ENCODING, errors=PIPE_ERRORS).stdout
        try:
            cp950.decode(PIPE_ENCODING)          # strict:必須失敗,否則樣本沒有鑑別力
            strict_raises = False
        except UnicodeDecodeError:
            strict_raises = True
        _run_selftest_check(
            "non-UTF-8 pipe output survives decoding (and the sample really is non-UTF-8)",
            strict_raises and "locked; see log" in decoded,
            f"strict_raises={strict_raises} decoded={decoded!r}",
            failures,
        )

        r = get("st_bytes")
        _run_selftest_check(
            "bytes @ 0x1a30b matches known-good content",
            bool(r) and r.get("hex") == "68 34 00 00 00 e8 1a cd 01 00 53 56 57 55 83 ec",
            f"got {r.get('hex') if r else None!r}",
            failures,
        )

        r = get("st_disasm")
        first = (r or {}).get("instructions", [{}])[0] if r else {}
        _run_selftest_check(
            "disasm @ 0x1a30b first instruction is PUSH 0x34",
            bool(r) and first.get("mnemonic") == "PUSH" and first.get("operands") == "0x34",
            f"got {first!r}",
            failures,
        )

        r = get("st_decompile")
        code = (r or {}).get("code", "")
        _run_selftest_check(
            "decompile @ 0x16559 contains the known if/else on DAT_00053c67",
            "DAT_00053c67 != 0x9017" in code and "FUN_0004ebff" in code and "FUN_0004ec31" in code,
            f"code={code!r}",
            failures,
        )

        r = get("st_function_bounds")
        _run_selftest_check(
            "function_bounds @ 0x1a30b matches known start/end",
            bool(r) and r.get("start") == "0x1a30b" and r.get("end") == "0x1a7bc",
            f"got {r!r}",
            failures,
        )

        r = get("st_call_scan")
        hit_addrs = {h.get("call_addr") for h in (r or {}).get("hits", [])}
        _run_selftest_check(
            "call_scan @ 0x187d6 finds both known FUN_0001a30b call sites",
            {"0x1a678", "0x1a6fa"}.issubset(hit_addrs),
            f"hits={sorted(hit_addrs)}",
            failures,
        )

        r = get("st_file_offset")
        _run_selftest_check(
            "file_offset @ 0x1a678 resolves to the known-unique offset 0x4068c",
            bool(r) and r.get("unique") is True and r.get("file_offsets") == ["0x4068c"],
            f"got {r!r}",
            failures,
        )

        # Independent cross-check with NO Ghidra involvement at all: read the raw EXE file
        # directly in Python and confirm the bytes at the reported offset really do start with
        # the same content `bytes` reported Ghidra's memory holds at 0x1a30b. This is the
        # reverse-direction half of the loop (offset -> content), complementing the forward
        # half (address -> content -> offset) that st_file_offset already checks.
        exe_path = Path(DEFAULT_EXE_PATH)
        if exe_path.is_file():
            raw = exe_path.read_bytes()
            probe_hex = "e859e1ffff83c4146a46e883d2010083c40483fe08759568"
            probe = bytes.fromhex(probe_hex)
            file_off = 0x4068c
            actual = raw[file_off:file_off + len(probe)]
            _run_selftest_check(
                "reverse check: raw file bytes at 0x4068c match expected content "
                "(zero Ghidra involvement in this read)",
                actual == probe,
                f"got {actual.hex()!r}",
                failures,
            )
        else:
            print(f"  [SKIP] reverse file-content check -- {exe_path} not present on this machine")

    print()
    if failures:
        print(f"selftest FAILED: {len(failures)} check(s) did not hold:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("selftest PASSED: all known-ground-truth checks hold.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run a batch of Ghidra probe queries against FD2Analysis3 in a single "
        "analyzeHeadless invocation.",
    )
    ap.add_argument("--queries", type=Path, help="Path to queries JSON (array of query objects).")
    ap.add_argument("--output", type=Path, help="Path to write results JSON.")
    ap.add_argument("--ghidra", default=DEFAULT_GHIDRA_INSTALL, help="Ghidra install dir (contains support/analyzeHeadless.bat).")
    ap.add_argument("--project-dir", default=DEFAULT_PROJECT_DIR, help="Ghidra project directory (also used as -scriptPath).")
    ap.add_argument("--project-name", default=DEFAULT_PROJECT_NAME, help="Ghidra project name.")
    ap.add_argument("--process-name", default=DEFAULT_PROCESS_NAME, help="Program name inside the project (-process).")
    ap.add_argument("--quiet", action="store_true", help="Suppress raw analyzeHeadless stdout/stderr; only print the summary.")
    ap.add_argument("--timeout", type=int, default=600, help="Subprocess timeout in seconds (default 600).")
    ap.add_argument("--selftest", action="store_true", help="Run a fault-injection-style regression check against known ground truth instead of a queries file.")
    args = ap.parse_args()

    if args.selftest:
        return run_selftest(args)

    if not args.queries or not args.output:
        print("error: --queries and --output are required unless --selftest is given", file=sys.stderr)
        return 2

    if not args.queries.exists():
        print(f"error: queries file not found: {args.queries}", file=sys.stderr)
        return 2

    script_path = Path(args.project_dir) / SCRIPT_NAME
    if not script_path.exists():
        print(f"error: {SCRIPT_NAME} not found in project dir {args.project_dir}", file=sys.stderr)
        print("       (expected at FD2_ghidra_projects/ProbeBatch.java)", file=sys.stderr)
        return 2

    try:
        queries = json.loads(args.queries.read_text(encoding="utf-8"))
        if not isinstance(queries, list):
            raise ValueError("queries JSON must be a top-level array")
    except Exception as e:
        print(f"error: failed to parse queries JSON: {e}", file=sys.stderr)
        return 2

    cmd = build_command(
        args.ghidra, args.project_dir, args.project_name, args.process_name, args.queries, args.output,
    )

    print(f"[ghidra_batch_probe] {len(queries)} queries, launching analyzeHeadless...")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=PIPE_ENCODING,
            errors=PIPE_ERRORS,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"error: analyzeHeadless timed out after {args.timeout}s", file=sys.stderr)
        return 3
    except FileNotFoundError as e:
        print(f"error: could not launch analyzeHeadless.bat ({e}); check --ghidra path", file=sys.stderr)
        return 3
    elapsed = time.time() - t0

    if not args.quiet:
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)

    combined = (proc.stdout or "") + (proc.stderr or "")
    if "ProbeBatch: " in combined:
        for line in combined.splitlines():
            if line.strip().startswith("ProbeBatch: ") or "ProbeBatch: " in line:
                print(f"[ghidra_batch_probe] {line.split('ProbeBatch: ', 1)[-1].strip()}")
                break

    if proc.returncode != 0:
        print(
            f"error: analyzeHeadless exited with code {proc.returncode} after {elapsed:.1f}s "
            "(see output above)",
            file=sys.stderr,
        )
        return proc.returncode

    if not args.output.exists():
        print(
            f"error: analyzeHeadless exited 0 but {args.output} was not created; "
            "check the log above for a script-level exception",
            file=sys.stderr,
        )
        return 4

    try:
        results = json.loads(args.output.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"error: results file {args.output} is not valid JSON: {e}", file=sys.stderr)
        return 4

    ok = sum(1 for r in results if r.get("ok"))
    failed = len(results) - ok
    print(
        f"[ghidra_batch_probe] done in {elapsed:.1f}s: {len(results)} results "
        f"({ok} ok, {failed} failed) -> {args.output}"
    )
    if failed:
        for r in results:
            if not r.get("ok"):
                print(f"  FAILED id={r.get('id')} address={r.get('address')} action={r.get('action')}: {r.get('error')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
