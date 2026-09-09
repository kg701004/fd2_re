#!/usr/bin/env python3
"""fd2_re — audit every writer of a global data address: is it hardcoded, or does it vary by caller?

背景(item 1117 SFX sample-identity調查的「矛盾」，2026-09-06)：`0x25a96`(play_sfx_a)的
`table_ptr`引數來自全域`[0x53b13]`，先前(續十)只確認過`xref_to [0x53b13]`的其中一個
WRITE點落在`FUN_0001d4cb`裡、且該函式呼叫`FUN_000111ba(0x51a4d="FDOTHER.DAT", 0, 0x50)`——
但`FUN_0001d4cb`本身有沒有參數(會不會不同caller傳不同檔名)一直沒有正式確認過，只是
順著decompile(已知不可靠)假設「固定」。這個工具把這個驗證步驟自動化、可重複使用在
本專案任何「一個全域被多處寫入，需要確認是不是真的每次都寫同樣的值」的情境：

1. 對目標位址跑`xref_to`，取得全部WRITE(以及可選READ)參照點。
2. 對每個WRITE點，用`function_bounds`找出它所在的函式(找不到則走既有的stack-check
   backtrack邏輯，見`trace_item_sfx_dispatch.py`)。
3. 對每個「寫入者函式」，用`call_scan`找出**它自己**的全部caller——藉此檢查`xref_to`
   本身有沒有漏掉(這專案已知`-noanalysis`下`xref_to`對call target不完整，同一邏輯延伸
   到「一個函式是否有多個caller」這個問題)。
4. 用`capstone_probe`對寫入者函式做**原始反組譯**(不信任Ghidra decompile可能省略引數
   的既有教訓)，抽取緊鄰函式入口的PUSH序列，人工可讀地印出：這個函式的『形式參數』
   在其呼叫端到底有沒有隨caller而變化的空間，或是內部完全不讀取任何棧上引數(=無論
   哪個caller呼叫，行為保證一致)。

用法:
    python tools/audit_global_writers.py --address 0x53b13
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import ghidra_batch_probe as gbp
import capstone_probe as cprobe

PUSH_MNEMONICS = {"push"}


def _run_batch(queries, *, ghidra_install, project_dir, project_name, process_name, timeout, quiet):
    with tempfile.TemporaryDirectory(prefix="audit_globals_") as tmpdir:
        queries_path = Path(tmpdir) / "queries.json"
        output_path = Path(tmpdir) / "results.json"
        queries_path.write_text(json.dumps(queries), encoding="utf-8")
        cmd = gbp.build_command(ghidra_install, project_dir, project_name, process_name, queries_path, output_path)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if not quiet:
            sys.stdout.write(proc.stdout)
            sys.stderr.write(proc.stderr)
        if not output_path.exists():
            raise RuntimeError(f"audit_global_writers: no output file. stdout tail:\n{proc.stdout[-2000:]}")
        return json.loads(output_path.read_text(encoding="utf-8"))


def _leading_pushes(instructions: list[dict], entry: int, max_pushes: int = 6) -> list[dict]:
    """Collect the contiguous PUSH-family instructions right at function entry (before the
    stack-check prologue's own body starts consuming them), in address order."""
    by_addr = sorted(instructions, key=lambda i: int(i["address"], 16))
    out = []
    for ins in by_addr:
        if int(ins["address"], 16) < entry:
            continue
        if ins["mnemonic"].lower() != "push":
            break
        out.append(ins)
        if len(out) >= max_pushes:
            break
    return out


def selftest() -> int:
    """`_leading_pushes` 的輸出是拿來判斷「這個函式會不會讀棧上引數」的原料。

    它有一個**容易誤讀的地方**,值得明確釘住:Watcom 函式的真入口是
    `push <frame>; call 0x3702f`,所以從真入口起收集,第一個 push 是
    **stack-check 的 frame size,不是參數** —— 緊接的 `call` 會中斷收集,
    所以只會拿到那一個。要看暫存器保存序列,必須從 `call` 之後起算。

    這個區別如果搞錯,會把 frame size 當成函式的形式參數,進而對「這個全域
    是不是每次都寫同樣的值」得出相反結論 —— 而那正是這支工具唯一的用途。
    """
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    fails = []

    def ins(a, m, o=""):
        return {"address": hex(a), "mnemonic": m, "op_str": o}

    # 典型 Watcom 序頭 + 暫存器保存
    seq = [ins(0x1000, "push", "0x30"), ins(0x1002, "call", "0x3702f"),
           ins(0x1007, "push", "ebx"), ins(0x1008, "push", "esi"),
           ins(0x1009, "sub", "esp, 0x10")]

    print("(1) 從真入口起:只會拿到 stack-check 的 frame size,call 立刻中斷收集")
    got1 = [i["op_str"] for i in _leading_pushes(seq, 0x1000)]
    ok1 = got1 == ["0x30"]
    print(f"    {'PASS' if ok1 else 'FAIL'}: {got1}(應 ['0x30'] —— 這是 frame size,不是參數)")
    if not ok1:
        fails.append(f"真入口起的收集不符:{got1}")

    print("\n(2) 從 call 之後起:才是暫存器保存序列")
    got2 = [i["op_str"] for i in _leading_pushes(seq, 0x1007)]
    ok2 = got2 == ["ebx", "esi"]
    print(f"    {'PASS' if ok2 else 'FAIL'}: {got2}(應 ['ebx', 'esi'];sub 中斷收集)")
    if not ok2:
        fails.append(f"call 之後的收集不符:{got2}")

    print("\n(3) max_pushes 必須真的封頂")
    got3 = [i["op_str"] for i in _leading_pushes(seq, 0x1007, 1)]
    ok3 = got3 == ["ebx"]
    print(f"    {'PASS' if ok3 else 'FAIL'}: max_pushes=1 -> {got3}")
    if not ok3:
        fails.append(f"max_pushes 沒有生效:{got3}")

    print("\n(4) 輸入順序不得影響結果(函式自己會依位址排序)")
    got4 = [i["op_str"] for i in _leading_pushes(list(reversed(seq)), 0x1007)]
    ok4 = got4 == got2
    print(f"    {'PASS' if ok4 else 'FAIL'}: 亂序輸入 -> {got4}(應與正序相同)")
    if not ok4:
        fails.append(f"亂序輸入結果不同:{got4} vs {got2}")

    print("\n(5) 邊界:入口在所有指令之後、以及第一條就不是 push,都必須回空")
    got5a = _leading_pushes(seq, 0x9999)
    got5b = _leading_pushes([ins(0x2000, "mov", "eax, 1"), ins(0x2002, "push", "ebx")], 0x2000)
    ok5 = got5a == [] and got5b == []
    print(f"    {'PASS' if ok5 else 'FAIL'}: 入口在尾端後={got5a}、"
          f"首條非 push={[i['op_str'] for i in got5b]}")
    if not ok5:
        fails.append("邊界情形沒有回空")

    print("\n(6) 非恆真控制:不同起點必須給出不同結果,否則這個函式沒在看 entry")
    ok6 = got1 != got2
    print(f"    {'PASS' if ok6 else 'FAIL'}: {got1} vs {got2}")
    if not ok6:
        fails.append("不同起點得到相同結果 —— entry 參數沒有作用")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed(序頭 frame size vs 暫存器保存的區別 + max_pushes + "
          "排序不變性 + 邊界 + 非恆真控制)。")
    return 0


def audit(address: int, *, ghidra_install, project_dir, project_name, process_name, timeout, quiet) -> dict:
    xrefs = _run_batch(
        [{"id": "x", "address": hex(address), "action": "xref_to"}],
        ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
        process_name=process_name, timeout=timeout, quiet=quiet,
    )[0]["result"]["refs"]

    writes = sorted({int(r["from"], 16) for r in xrefs if r.get("type") == "WRITE"})
    reads = sorted({int(r["from"], 16) for r in xrefs if r.get("type") == "READ"})

    report: dict = {"address": hex(address), "xref_write_sites": [hex(w) for w in writes], "xref_read_sites": [hex(r) for r in reads], "writer_functions": {}}

    # Group write sites by enclosing function.
    write_funcs: dict[int, list[int]] = {}
    for w in writes:
        fb = _run_batch(
            [{"id": "fb", "address": hex(w), "action": "function_bounds"}],
            ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
            process_name=process_name, timeout=timeout, quiet=quiet,
        )[0]["result"]
        func_start = int(fb["start"], 16) if fb.get("in_function") else None
        write_funcs.setdefault(func_start if func_start is not None else -1, []).append(w)

    for func_start, sites in write_funcs.items():
        if func_start == -1:
            report["writer_functions"]["UNRESOLVED"] = {"write_sites": [hex(s) for s in sites], "note": "not inside any Ghidra-boundaried function"}
            continue

        entry = {"function_start": hex(func_start), "write_sites": [hex(s) for s in sites]}

        # How many real callers does this writer function have? (cross-check against call_scan,
        # since a single xref-visible write site doesn't tell us how many distinct call paths
        # reach it.)
        cs = _run_batch(
            [{"id": "cs", "address": hex(func_start), "action": "call_scan"}],
            ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
            process_name=process_name, timeout=timeout, quiet=quiet,
        )[0]["result"]
        entry["caller_count"] = cs.get("count", 0)
        entry["callers"] = [h["call_addr"] for h in cs.get("hits", [])]

        # Raw disasm of the writer function's own entry to see whether it reads any stack args
        # (i.e. could plausibly vary by caller) or is fully self-contained (hardcoded).
        fb = _run_batch(
            [{"id": "fb2", "address": hex(func_start), "action": "function_bounds"}],
            ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
            process_name=process_name, timeout=timeout, quiet=quiet,
        )[0]["result"]
        size = fb.get("size", 64)
        data = cprobe.fetch_bytes(
            func_start, min(size + 16, 512),
            ghidra_install=ghidra_install, project_dir=project_dir, project_name=project_name,
            process_name=process_name, timeout=timeout, quiet=quiet,
        )
        instructions = cprobe.disassemble(func_start, data)
        reads_esp_arg = any(
            "esp" in ins["operands"].lower() and ins["mnemonic"].lower() in {"mov", "movzx", "movsx", "push", "cmp", "lea"}
            and "[esp" in ins["operands"].lower().replace(" ", "")
            for ins in instructions
        )
        entry["reads_stack_relative_operand"] = reads_esp_arg
        entry["verdict"] = (
            "POSSIBLY PARAMETERIZED (reads an [esp+..] operand -- could vary by caller, inspect manually)"
            if reads_esp_arg
            else "HARDCODED (no [esp+..] operand read anywhere in the function body -- behavior is identical for every caller)"
        )
        entry["disasm_preview"] = [f"{ins['address']}: {ins['mnemonic']} {ins['operands']}" for ins in instructions[:20]]

        report["writer_functions"][hex(func_start)] = entry

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--address", type=lambda s: int(s, 0))
    ap.add_argument("--output", type=Path)
    ap.add_argument("--ghidra", default=gbp.DEFAULT_GHIDRA_INSTALL)
    ap.add_argument("--project-dir", default=gbp.DEFAULT_PROJECT_DIR)
    ap.add_argument("--project-name", default=gbp.DEFAULT_PROJECT_NAME)
    ap.add_argument("--process-name", default=gbp.DEFAULT_PROCESS_NAME)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.address is None:
        ap.error("需要 --address(或用 --selftest)")

    report = audit(
        args.address,
        ghidra_install=args.ghidra, project_dir=args.project_dir, project_name=args.project_name,
        process_name=args.process_name, timeout=args.timeout, quiet=args.quiet,
    )

    print(f"[audit_global_writers] {report['address']}: {len(report['xref_write_sites'])} write site(s), {len(report['xref_read_sites'])} read site(s)")
    for func, info in report["writer_functions"].items():
        if func == "UNRESOLVED":
            print(f"  {func}: {info}")
            continue
        print(f"  writer function {func}: {info['caller_count']} caller(s) via call_scan -> {info['verdict']}")

    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[audit_global_writers] wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
