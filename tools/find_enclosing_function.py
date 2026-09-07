#!/usr/bin/env python3
"""fd2_re - recover the enclosing function entry for an address Ghidra never boundaried.

Why this exists
---------------
Under `-noanalysis`, Ghidra leaves large parts of `.object1` without function
boundaries, so `function_bounds` answers `in_function: false` and `decompile`
refuses outright. This project has repeatedly worked around that by hand, using
the fact that essentially every function in this EXE opens with the Watcom
stack-check prologue:

    push <frame_size>
    call 0x3702f

so the function entry is `(address of that call) - 5`. That backtrack was done
by hand for `0x25186` -> `0x250cc` (worklist item 857) and, in a different form,
inside `trace_item_sfx_dispatch.py`. This tool makes it a single command with an
explicit failure mode instead of an ad-hoc scan each time.

What it does NOT do
-------------------
It reports the nearest preceding stack-check prologue, which is the entry only
if the target really is inside that function. If the preceding function ended
before the target (a gap, alignment padding, or data), the answer would be
wrong -- so the tool also reports whether the candidate's body actually reaches
the target without hitting a terminating `ret`/`jmp` first, and says
`reaches_target: False` rather than quietly returning a plausible-looking entry.

Usage
-----
    python tools/find_enclosing_function.py --address 0x25186
    python tools/find_enclosing_function.py --selftest

Verification design
-------------------
`--selftest` runs four checks:

1. Forward, un-boundaried case: `0x25186` must resolve to `0x250cc` -- the value
   derived by hand on 2026-09-07 and used to close worklist item 857.
2. Cross-tool agreement: for addresses Ghidra DOES boundary, this tool's answer
   must equal Ghidra's own `function_bounds.start`. Two independent mechanisms
   agreeing is stronger than either alone.
3. Negative control: an address inside a data block (`0x6238d`, the town table)
   must NOT be reported as living in a function whose body reaches it.
4. Fault injection: with the prologue signature changed to a call target that is
   not the stack-check helper, check 1 must fail to find anything -- proving the
   signature is what drives the result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capstone_probe as cprobe  # noqa: E402
import ghidra_batch_probe as gbp  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STACK_CHECK = 0x3702F
DEFAULT_BACK = 0x600


def _bytes(start: int, count: int) -> bytes:
    q = [{"id": "b", "address": hex(start), "action": "bytes", "count": count}]
    with tempfile.TemporaryDirectory(prefix="fef_") as d:
        qp, op = Path(d) / "q.json", Path(d) / "o.json"
        qp.write_text(json.dumps(q), encoding="utf-8")
        subprocess.run(gbp.build_command(gbp.DEFAULT_GHIDRA_INSTALL, gbp.DEFAULT_PROJECT_DIR,
                                         gbp.DEFAULT_PROJECT_NAME, gbp.DEFAULT_PROCESS_NAME,
                                         qp, op), capture_output=True, text=True, timeout=300)
        r = json.loads(op.read_text(encoding="utf-8"))[0]
    if not r.get("ok"):
        raise RuntimeError(f"byte fetch failed: {r}")
    return bytes.fromhex(r["result"]["hex"])


def find_entry(address: int, back: int = DEFAULT_BACK, stack_check: int = STACK_CHECK) -> dict:
    """Nearest preceding `call <stack_check>`; entry = that call - 5."""
    start = max(0x10000, address - back)
    data = _bytes(start, address - start + 8)
    sites = []
    for i in range(len(data) - 5):
        if data[i] != 0xE8:
            continue
        rel = int.from_bytes(data[i + 1:i + 5], "little", signed=True)
        site = start + i
        if site + 5 + rel == stack_check and site < address:
            sites.append(site)
    if not sites:
        return {"address": hex(address), "found": False,
                "note": f"no `call {stack_check:#x}` within {back:#x} bytes before the address"}
    call_site = sites[-1]
    entry = call_site - 5
    # does the candidate's body actually reach the target?
    span = address - entry + 16
    ins = cprobe.disassemble(entry, cprobe.fetch_bytes(entry, span, quiet=True))
    reaches, terminator = True, None
    for t in ins:
        a = int(t["address"], 16)
        if a >= address:
            break
        m = t["mnemonic"].lower()
        if m == "ret":
            reaches, terminator = False, t
            continue
        if m == "jmp":
            # An unconditional jump only ends the function if it leaves the span
            # we are walking. A forward jump to a later address inside the span
            # is ordinary control flow (loop head, if/else join) -- treating it
            # as a terminator was the first version's bug, caught by --selftest
            # on 0x25186 (`0x25105: jmp 0x2511d` is a loop, not an exit).
            try:
                dest = int(t["operands"].strip(), 16)
            except ValueError:
                continue
            if dest < entry or dest > address:
                reaches, terminator = False, t
    return {
        "address": hex(address),
        "found": True,
        "entry": hex(entry),
        "stack_check_call_at": hex(call_site),
        "prologue": f"{ins[0]['mnemonic']} {ins[0]['operands']}" if ins else "?",
        "reaches_target": reaches,
        "terminator_before_target": (f"{terminator['address']}: {terminator['mnemonic']} "
                                     f"{terminator['operands']}") if terminator else None,
    }


def _ghidra_bounds(address: int) -> dict:
    q = [{"id": "fb", "address": hex(address), "action": "function_bounds"}]
    with tempfile.TemporaryDirectory(prefix="fefb_") as d:
        qp, op = Path(d) / "q.json", Path(d) / "o.json"
        qp.write_text(json.dumps(q), encoding="utf-8")
        subprocess.run(gbp.build_command(gbp.DEFAULT_GHIDRA_INSTALL, gbp.DEFAULT_PROJECT_DIR,
                                         gbp.DEFAULT_PROJECT_NAME, gbp.DEFAULT_PROCESS_NAME,
                                         qp, op), capture_output=True, text=True, timeout=300)
        return json.loads(op.read_text(encoding="utf-8"))[0]["result"]


def selftest() -> int:
    fails: list[str] = []

    print("(1) forward, un-boundaried: 0x25186 should resolve to 0x250cc")
    r = find_entry(0x25186)
    ok = r.get("entry") == "0x250cc" and r.get("reaches_target")
    print(f"    {'PASS' if ok else 'FAIL'}: {r}")
    if not ok:
        fails.append(f"0x25186 -> {r.get('entry')} (reaches={r.get('reaches_target')})")

    print("\n(2) cross-tool agreement with Ghidra on addresses it DID boundary")
    for probe in (0x2AC90, 0x15F30, 0x1F250):
        g = _ghidra_bounds(probe)
        if not g.get("in_function"):
            print(f"    skip 0x{probe:x}: Ghidra has no boundary here")
            continue
        mine = find_entry(probe)
        agree = mine.get("entry") == g["start"]
        print(f"    {'PASS' if agree else 'FAIL'} 0x{probe:x}: mine={mine.get('entry')} ghidra={g['start']}")
        if not agree:
            fails.append(f"0x{probe:x}: mine={mine.get('entry')} vs ghidra={g['start']}")

    print("\n(3) negative control: a data-block address must not claim a reaching function")
    r = find_entry(0x6238D, back=0x400)
    if r.get("found") and r.get("reaches_target"):
        fails.append("0x6238d was reported as inside a function body that reaches it")
        print(f"    FAIL: {r}")
    else:
        print(f"    PASS: found={r.get('found')} reaches={r.get('reaches_target')}")

    print("\n(4) fault injection: wrong prologue signature must break check 1")
    r = find_entry(0x25186, stack_check=STACK_CHECK + 0x10)
    if r.get("entry") == "0x250cc":
        fails.append("fault injection still produced 0x250cc -- the signature is not load-bearing")
        print("    FAIL: unchanged")
    else:
        print(f"    PASS: entry now {r.get('entry')} (found={r.get('found')})")

    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print("  -", f)
        return 1
    print("\n--selftest passed (2 forward + 2 reverse checks).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--address", type=lambda s: int(s, 0))
    ap.add_argument("--back", type=lambda s: int(s, 0), default=DEFAULT_BACK)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.address is None:
        ap.error("need --address (or --selftest)")
    print(json.dumps(find_entry(args.address, args.back), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
