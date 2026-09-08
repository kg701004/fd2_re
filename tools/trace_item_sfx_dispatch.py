#!/usr/bin/env python3
"""fd2_re — trace every caller of a native function's `param_2`-style stdcall argument.

背景(item 1117 SFX sample-identity調查,2026-09-06)：worklist/doc57已用手動per-call-site
反組譯確認`FUN_0001c4cc`(item effect共用受擊/演出+SFX觸發迴圈)`param_2`欄位(=效果
子類型索引,用來查`0x51f33`/`0x51f54`/`0x51f75`三張33-byte表)在其中一個caller(type11/
MP恢復)的值是13——但`call_scan`後來發現真正的caller數是16個(遠比先前記錄的9個多)，
逐一手動反組譯每個call site太耗時、容易漏。這個工具自動化整個流程：

1. 用`ghidra_batch_probe.py`的`call_scan` action找出目標函式(預設`0x1c4cc`)的全部呼叫端。
2. 對每個呼叫端，先試著用`function_bounds`＋`disasm`(Ghidra自己的反組譯，對已被Ghidra
   辨識邊界的function最快)取得該call site附近的指令序列。
3. 若呼叫端不在任何已知function內(即`.object1`blind spot——Watcom stack-check prologue
   `PUSH frame_size; CALL 0x3702f`沒被`-noanalysis`自動辨識，見既有memory
   `fd2-live-ghidra-headless-probe`)，改用`call_scan(target=0x3702f)`找最近的前置
   stack-check call，回推函式真正入口(=該call位址-5，即前面那個`PUSH frame_size`)，
   再用`capstone_probe.fetch_bytes`＋本地capstone反組譯(不依賴Ghidra指令庫)從那個入口
   往後解到call site。
4. 找到`CALL <target>`後，往回收集緊鄰的PUSH系列指令(stdcall逆序：最後一個push＝
   param_1，往前數第N個push＝param_N)，回報每個引數是immediate(直接得到數值)還是
   register/memory reference(需要更深入dataflow，誠實標記為未解)。

用法:
    python tools/trace_item_sfx_dispatch.py --target 0x1c4cc --output out.json
    python tools/trace_item_sfx_dispatch.py --target 0x1c4cc --num-args 4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import capstone

import ghidra_batch_probe as gbp
import capstone_probe as cprobe

PUSH_MNEMONICS = {"push"}
STACK_CHECK_HELPER = 0x3702F


def _run_batch(queries: list[dict], *, ghidra_install, project_dir, project_name, process_name, timeout, quiet) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="trace_sfx_") as tmpdir:
        queries_path = Path(tmpdir) / "queries.json"
        output_path = Path(tmpdir) / "results.json"
        queries_path.write_text(json.dumps(queries), encoding="utf-8")
        cmd = gbp.build_command(ghidra_install, project_dir, project_name, process_name, queries_path, output_path)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if not quiet:
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)
        if not output_path.exists():
            raise RuntimeError(f"trace_item_sfx_dispatch: no output file. stdout tail:\n{proc.stdout[-2000:]}")
        return json.loads(output_path.read_text(encoding="utf-8"))


def _extract_pushes_before_call(instructions: list[dict], call_addr: int, num_args: int) -> list[dict] | None:
    """Given a flat instruction list (address order), find the CALL at call_addr and walk
    backward collecting contiguous PUSH instructions immediately before it. Returns them in
    chronological (address) order, i.e. index 0 = param_<num_args> ... index -1 = param_1.
    Returns None if the call itself isn't found or fewer than num_args pushes precede it."""
    by_addr = {int(ins["address"], 16): ins for ins in instructions}
    ordered = sorted(by_addr.keys())
    if call_addr not in by_addr:
        return None
    idx = ordered.index(call_addr)
    pushes = []
    i = idx - 1
    while i >= 0 and len(pushes) < num_args:
        ins = by_addr[ordered[i]]
        if ins["mnemonic"].lower() not in PUSH_MNEMONICS:
            break
        pushes.append(ins)
        i -= 1
    pushes.reverse()  # chronological order
    if len(pushes) < num_args:
        return None
    return pushes[-num_args:]


def selftest() -> int:
    """`_classify_operand` 決定一個 push 是「常數 sfx index」還是「執行期才知道的值」。

    分錯的後果不是崩潰,是**憑空生出一個 sfx index**(把暫存器當成常數)或
    **漏掉一個已知常數**(把立即數當成暫存器)。所以這裡逐一釘住實際行為,
    包含幾個容易忽略的邊界。

    刻意記錄一個**已知的寬鬆處**:`int(operand, 0)` 會接受 Python 的底線分隔
    數字(`"1_0"` -> 10)與二/八進位字面(`"0b101"` -> 5)。capstone 不會產生
    這些寫法,所以實務上碰不到;但這代表分類器接受的比它該接受的寬,寫在這裡
    以免日後有人把它當成嚴格的 x86 立即數解析器來用。
    """
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    print("(1) capstone 實際會產生的兩類 operand 必須分對")
    cases = [
        ("0x11", "immediate", 17),
        ("1", "immediate", 1),
        ("0x0", "immediate", 0),
        ("eax", "register_or_memory", None),
        ("dword ptr [eax + 0x10]", "register_or_memory", None),
        ("word ptr [ebp - 8]", "register_or_memory", None),
    ]
    for op, kind, val in cases:
        got = _classify_operand(op)
        ok = got["kind"] == kind and got.get("value") == val
        print(f"    {'PASS' if ok else 'FAIL'}: {op!r:26} -> {got['kind']}"
              f"{'' if val is None else ' = ' + str(got.get('value'))}")
        if not ok:
            fails.append(f"{op!r} 分類成 {got}")

    print("\n(2) 前後空白不得影響分類(capstone 的 op_str 常帶空白)")
    ok2 = _classify_operand(" 0x20 ") == {"kind": "immediate", "value": 32,
                                          "raw": "0x20"}
    print(f"    {'PASS' if ok2 else 'FAIL'}: ' 0x20 ' -> {_classify_operand(' 0x20 ')}")
    if not ok2:
        fails.append("空白沒有被正確處理(raw 應為去空白後的字串)")

    print("\n(3) 不完整/空 operand 必須落到 register_or_memory,不能丟例外")
    for op in ("0x", "", "   ", "ptr"):
        try:
            got = _classify_operand(op)
            ok = got["kind"] == "register_or_memory"
            print(f"    {'PASS' if ok else 'FAIL'}: {op!r:8} -> {got['kind']}")
            if not ok:
                fails.append(f"{op!r} 被當成 immediate")
        except Exception as exc:                              # noqa: BLE001
            print(f"    FAIL: {op!r} 丟出 {type(exc).__name__}")
            fails.append(f"{op!r} 丟出 {type(exc).__name__}")

    print("\n(4) 已知的寬鬆處:記錄現況,而不是假裝它不存在")
    loose = {op: _classify_operand(op).get("value")
             for op in ("1_0", "0b101", "0o17", "-5")}
    ok4 = loose == {"1_0": 10, "0b101": 5, "0o17": 15, "-5": -5}
    print(f"    {'PASS' if ok4 else 'FAIL'}: {loose}")
    print("    (capstone 不產生這些寫法,所以實務上碰不到;此題只是把現況釘住,"
          "行為若改變會被看見)")
    if not ok4:
        fails.append(f"寬鬆處的行為變了:{loose}")

    print("\n(5) 非恆真控制:兩類必須真的分得開,不能全部落到同一邊")
    kinds = {_classify_operand(o)["kind"] for o in ("0x11", "eax")}
    ok5 = len(kinds) == 2
    print(f"    {'PASS' if ok5 else 'FAIL'}: 分出 {sorted(kinds)}")
    if not ok5:
        fails.append("兩類 operand 被分到同一邊 —— 分類器沒有鑑別力")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(兩類分類 + 空白處理 + 不完整輸入 + 已知寬鬆處 + "
          "非恆真控制)。")
    return 0


def _classify_operand(operand: str) -> dict:
    operand = operand.strip()
    try:
        # capstone renders plain immediates as bare hex/decimal (e.g. "0x11", "1")
        value = int(operand, 0)
        return {"kind": "immediate", "value": value, "raw": operand}
    except ValueError:
        return {"kind": "register_or_memory", "raw": operand}


def trace(
    target: int,
    num_args: int,
    *,
    ghidra_install: str,
    project_dir: str,
    project_name: str,
    process_name: str,
    timeout: int,
    quiet: bool,
) -> list[dict]:
    # Step 1: find every caller of `target`.
    call_scan_results = _run_batch(
        [{"id": "cs", "address": hex(target), "action": "call_scan"}],
        ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
        process_name=process_name, timeout=timeout, quiet=quiet,
    )
    hits = call_scan_results[0]["result"]["hits"]

    unresolved_addrs = [int(h["call_addr"], 16) for h in hits if h.get("in_function") is None]
    stack_check_starts: dict[int, int] = {}
    if unresolved_addrs:
        # Step 3 prep: find every call to the stack-check helper, to recover function entries
        # for call sites Ghidra's -noanalysis pass never boundaried (the ".object1" blind spot).
        sc_results = _run_batch(
            [{"id": "sc", "address": hex(STACK_CHECK_HELPER), "action": "call_scan"}],
            ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
            process_name=process_name, timeout=timeout, quiet=quiet,
        )
        sc_hits = sorted(int(h["call_addr"], 16) for h in sc_results[0]["result"]["hits"])
        for addr in unresolved_addrs:
            candidates = [c for c in sc_hits if c < addr]
            if candidates:
                nearest = max(candidates)
                stack_check_starts[addr] = nearest - 5  # the PUSH frame_size right before CALL 0x3702f

    report = []
    for h in hits:
        call_addr = int(h["call_addr"], 16)
        entry = {
            "call_addr": h["call_addr"],
            "in_function": h.get("in_function"),
        }
        try:
            if h.get("in_function"):
                fb = _run_batch(
                    [{"id": "fb", "address": hex(call_addr), "action": "function_bounds"}],
                    ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
                    process_name=process_name, timeout=timeout, quiet=quiet,
                )[0]["result"]
                if not fb.get("in_function"):
                    raise RuntimeError("function_bounds disagrees with call_scan's in_function hint")
                func_start = int(fb["start"], 16)
                func_size = fb["size"]
                entry["function_start"] = fb["start"]
                # Prefer Ghidra's own flow-directed disasm (fast, single call) but it silently
                # truncates at the first unconditional JMP/RET it walks into -- which can be
                # BEFORE our target call if the function has multiple disjoint branches (observed
                # for FUN_00020c6f, a large multi-branch dispatcher). Fall back to a purely linear
                # capstone decode of the whole function body (byte-for-byte, ignores control flow)
                # whenever the call address isn't actually present in what Ghidra returned.
                disasm = _run_batch(
                    [{"id": "d", "address": hex(func_start), "action": "disasm", "length": min(func_size + 16, 2000)}],
                    ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
                    process_name=process_name, timeout=timeout, quiet=quiet,
                )[0]["result"]
                instructions = disasm["instructions"]
                if not any(int(ins["address"], 16) == call_addr for ins in instructions):
                    entry["resolved_via"] = "capstone_linear_from_function_start (ghidra disasm truncated before call site)"
                    data = cprobe.fetch_bytes(
                        func_start, func_size + 16,
                        ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
                        process_name=process_name, timeout=timeout, quiet=quiet,
                    )
                    instructions = cprobe.disassemble(func_start, data)
                else:
                    entry["resolved_via"] = "ghidra_disasm_from_function_start"
            else:
                if call_addr not in stack_check_starts:
                    entry["error"] = "not in a known function, and no preceding stack-check call found to recover entry"
                    report.append(entry)
                    continue
                func_start = stack_check_starts[call_addr]
                entry["resolved_via"] = "stack_check_prologue_backtrack+capstone"
                entry["function_start"] = hex(func_start)
                length = (call_addr - func_start) + 16
                data = cprobe.fetch_bytes(
                    func_start, length,
                    ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
                    process_name=process_name, timeout=timeout, quiet=quiet,
                )
                instructions = cprobe.disassemble(func_start, data)

            pushes = _extract_pushes_before_call(instructions, call_addr, num_args)
            if pushes is None:
                entry["error"] = "could not find call site or fewer than num_args contiguous pushes before it"
                report.append(entry)
                continue

            args = []
            for i, ins in enumerate(pushes):
                param_index = num_args - i  # pushes[0] is param_<num_args>, last is param_1
                classified = _classify_operand(ins["operands"])
                classified["param"] = f"param_{param_index}"
                classified["push_addr"] = ins["address"]
                args.append(classified)
            entry["args"] = args
        except Exception as exc:  # noqa: BLE001 - report per-call-site failures, don't abort the sweep
            entry["error"] = f"{type(exc).__name__}: {exc}"
        report.append(entry)

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=lambda s: int(s, 0), help="Address of the function whose callers to trace (e.g. 0x1c4cc).")
    ap.add_argument("--num-args", type=int, default=4, help="Number of stdcall arguments to try to recover (default 4).")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--output", type=Path, help="Optional path to write the full report as JSON.")
    ap.add_argument("--ghidra", default=gbp.DEFAULT_GHIDRA_INSTALL)
    ap.add_argument("--project-dir", default=gbp.DEFAULT_PROJECT_DIR)
    ap.add_argument("--project-name", default=gbp.DEFAULT_PROJECT_NAME)
    ap.add_argument("--process-name", default=gbp.DEFAULT_PROCESS_NAME)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.target is None:
        ap.error("需要 --target(或用 --selftest)")

    report = trace(
        args.target, args.num_args,
        ghidra_install=args.ghidra, project_dir=args.project_dir, project_name=args.project_name,
        process_name=args.process_name, timeout=args.timeout, quiet=args.quiet,
    )

    for entry in report:
        line = f"{entry['call_addr']} (in {entry.get('in_function') or entry.get('function_start', '?')}, via {entry.get('resolved_via', 'n/a')})"
        if "error" in entry:
            line += f" -> ERROR: {entry['error']}"
        else:
            arg_strs = [f"{a['param']}={a['raw']}" for a in entry["args"]]
            line += " -> " + ", ".join(arg_strs)
        print(line)

    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[trace_item_sfx_dispatch] wrote report for {len(report)} call sites to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
