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
      {"id": "q6", "address": "0x53a51", "action": "bytes", "count": 16}
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

輸出格式:JSON 陣列,每筆對應輸入的 "id",含 "ok"(true/false)。單一 query 失敗不會讓整批
中斷 —— 其餘 query 照跑,失敗的那筆在輸出裡帶 "error" 說明原因。

已知環境細節(踩過的坑,詳見 memory `fd2-live-ghidra-headless-probe`):
  - project 路徑一定要用絕對路徑(相對路徑 "." 開頭會被 Ghidra 拒絕)。
  - 必須 `-readOnly`(不修改唯讀 project,前一輪 forced-disassembly 這類 in-session 變更
    收尾會被丟棄)+ `-noanalysis`(project 已經分析過,不要重跑一次完整分析)。
  - `-process "FD2.EXE"` 指的是 project 內部的 program 名稱,不是檔案路徑。
  - project owner 若卡 NotOwnerException,要先取得使用者同意修改
    `FD2Analysis3.rep/project.prp` 的 OWNER 欄位(這個 repo 已經改過,通常不會再遇到)。
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run a batch of Ghidra probe queries against FD2Analysis3 in a single "
        "analyzeHeadless invocation.",
    )
    ap.add_argument("--queries", required=True, type=Path, help="Path to queries JSON (array of query objects).")
    ap.add_argument("--output", required=True, type=Path, help="Path to write results JSON.")
    ap.add_argument("--ghidra", default=DEFAULT_GHIDRA_INSTALL, help="Ghidra install dir (contains support/analyzeHeadless.bat).")
    ap.add_argument("--project-dir", default=DEFAULT_PROJECT_DIR, help="Ghidra project directory (also used as -scriptPath).")
    ap.add_argument("--project-name", default=DEFAULT_PROJECT_NAME, help="Ghidra project name.")
    ap.add_argument("--process-name", default=DEFAULT_PROCESS_NAME, help="Program name inside the project (-process).")
    ap.add_argument("--quiet", action="store_true", help="Suppress raw analyzeHeadless stdout/stderr; only print the summary.")
    ap.add_argument("--timeout", type=int, default=600, help="Subprocess timeout in seconds (default 600).")
    args = ap.parse_args()

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
