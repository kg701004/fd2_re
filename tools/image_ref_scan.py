#!/usr/bin/env python3
"""fd2_re - scan the whole EXE image for every reference to an address.

Why this exists
---------------
Under this project's `-noanalysis` Ghidra setup, `xref_to` is known-incomplete:
it routinely returns 0 refs for addresses that demonstrably are referenced
(the `.object1` blind spot, recorded across doc35/doc58/trace_item_sfx_dispatch).
Several open questions are stuck precisely on "xref_to found nothing, so we
cannot find the caller" -- for example worklist item 212's spawned question
(`0x35854`'s runtime trigger path: "目前查無任何已知靜態呼叫者").

`ghidra_batch_probe.py`'s `call_scan` already brute-forces E8 call sites, but
only calls. This tool covers the three reference forms that matter here, over
the raw image bytes, independent of any function boundary database:

  call    E8 <rel32>   where site+5+rel32 == target
  jmp     E9 <rel32>   same arithmetic (tail-calls / thunks)
  absolute <imm32>     any little-endian dword equal to the target address,
                       which covers `mov reg,imm32`, `push imm32`, and the
                       disp32 of `lea reg,[abs]` / `mov reg,[abs]`

Absolute hits are reported separately because a raw dword match can also be a
coincidence in data (the tool says how many, and shows context bytes, rather
than pretending every hit is code).

Usage
-----
    python tools/image_ref_scan.py --target 0x35854
    python tools/image_ref_scan.py --target 0x615fe --kinds abs
    python tools/image_ref_scan.py --selftest

Verification design (why you can trust the output)
--------------------------------------------------
`--selftest` runs four independent checks:

1. Forward, call form: `0x2ac7d` must be found called from `0x2ac63`
   (established 2026-09-07 via Ghidra `call_scan`, an independent tool).
2. Forward, absolute form: `0x6238d` must appear at `0x4e817` and `0x615fe`
   at `0x4e7e8` -- both are DATA refs Ghidra's `xref_to` itself reports, so
   this cross-checks two independent implementations against each other.
3. Rival/negative control: scanning for `target+1` must NOT reproduce the same
   hit set. Without this, a scanner that (say) matched on any nearby dword
   would look just as "correct" on check 1-2.
4. Fault injection: with the rel32 arithmetic deliberately off by one, the
   known call site must disappear -- proving the arithmetic is load-bearing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ghidra_batch_probe as gbp  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# The readable code/data blocks, as reported by ghidra_batch_probe's call_scan.
# Do NOT scan a flat 0..end range: address 0 is unmapped and the fetch fails.
BLOCKS = (
    (0x10000, 0x4EF28),   # .object1
    (0x50000, 0x556AF),   # .object2
    (0x60000, 0x634D1),   # .object3
)
CHUNK = 0x8000


def _fetch(start: int, count: int, **kw) -> bytes:
    """Pull raw image bytes through ghidra_batch_probe's `bytes` action."""
    queries, offs = [], []
    off = 0
    while off < count:
        n = min(CHUNK, count - off)
        queries.append({"id": f"b{off}", "address": hex(start + off), "action": "bytes", "count": n})
        offs.append(off)
        off += n
    with tempfile.TemporaryDirectory(prefix="imgref_") as d:
        qp, op = Path(d) / "q.json", Path(d) / "o.json"
        qp.write_text(json.dumps(queries), encoding="utf-8")
        cmd = gbp.build_command(kw.get("ghidra", gbp.DEFAULT_GHIDRA_INSTALL),
                                kw.get("project_dir", gbp.DEFAULT_PROJECT_DIR),
                                kw.get("project_name", gbp.DEFAULT_PROJECT_NAME),
                                kw.get("process_name", gbp.DEFAULT_PROCESS_NAME), qp, op)
        subprocess.run(cmd, capture_output=True, text=True, timeout=kw.get("timeout", 900))
        if not op.exists():
            raise RuntimeError("image_ref_scan: analyzeHeadless produced no output")
        results = {r["id"]: r for r in json.loads(op.read_text(encoding="utf-8"))}
    out = bytearray()
    for off in offs:
        r = results[f"b{off}"]
        if not r.get("ok"):
            raise RuntimeError(f"image_ref_scan: chunk at +{off:#x} failed: {r}")
        out += bytes.fromhex(r["result"]["hex"])
    return bytes(out)


_IMAGE_CACHE: dict[tuple[int, int], bytes] = {}


def block_bytes(start: int, end: int, **kw) -> bytes:
    key = (start, end)
    if key not in _IMAGE_CACHE:
        _IMAGE_CACHE[key] = _fetch(start, end - start, **kw)
    return _IMAGE_CACHE[key]


def scan(target: int, *, kinds: tuple[str, ...] = ("call", "jmp", "abs"),
         rel_bias: int = 0, **kw) -> dict[str, list[dict]]:
    """`rel_bias` is only for --selftest fault injection; leave it 0."""
    hits: dict[str, list[dict]] = {k: [] for k in kinds}
    for base, end in BLOCKS:
        _scan_block(target, base, end, kinds, rel_bias, hits, **kw)
    return hits


def _scan_block(target, base, end, kinds, rel_bias, hits, **kw) -> None:
    data = block_bytes(base, end, **kw)
    for i in range(len(data) - 5):
        op = data[i]
        if op in (0xE8, 0xE9):
            kind = "call" if op == 0xE8 else "jmp"
            if kind not in hits:
                continue
            rel = int.from_bytes(data[i + 1:i + 5], "little", signed=True)
            if base + i + 5 + rel + rel_bias == target:
                hits[kind].append({"at": hex(base + i), "context": data[max(0, i - 3):i + 5].hex()})
    if "abs" in hits:
        needle = target.to_bytes(4, "little")
        start = 0
        while True:
            j = data.find(needle, start)
            if j < 0:
                break
            hits["abs"].append({"at": hex(base + j),
                                "context": data[max(0, j - 6):j + 6].hex()})
            start = j + 1


# --------------------------------------------------------------------------
def selftest(**kw) -> int:
    fails: list[str] = []

    print("(1) forward, call form: 0x2ac7d should be called from 0x2ac63")
    h = scan(0x2AC7D, kinds=("call",), **kw)
    calls = {x["at"] for x in h["call"]}
    ok = "0x2ac63" in calls
    print(f"    {'PASS' if ok else 'FAIL'}: {sorted(calls)}")
    if not ok:
        fails.append("0x2ac63 not found as a caller of 0x2ac7d")

    print("\n(2) forward, absolute form: cross-check two DATA refs Ghidra also reports")
    for tgt, want in ((0x6238D, "0x4e817"), (0x615FE, "0x4e7e8")):
        h = scan(tgt, kinds=("abs",), **kw)
        ats = {x["at"] for x in h["abs"]}
        # Ghidra reports the instruction address; the raw dword sits a couple of
        # bytes later inside that instruction, so accept a small window.
        near = any(abs(int(a, 16) - int(want, 16)) <= 6 for a in ats)
        print(f"    {'PASS' if near else 'FAIL'} 0x{tgt:x}: {sorted(ats)} (expect one near {want})")
        if not near:
            fails.append(f"0x{tgt:x}: no absolute ref near {want}")

    print("\n(3) rival/negative control: scanning target+1 must not give the same hits")
    a = scan(0x2AC7D, kinds=("call",), **kw)["call"]
    b = scan(0x2AC7D + 1, kinds=("call",), **kw)["call"]
    if {x["at"] for x in a} == {x["at"] for x in b}:
        fails.append("target+1 produced an identical hit set -- the scan is not address-specific")
        print("    FAIL: identical")
    else:
        print(f"    PASS: {len(a)} hit(s) for the target vs {len(b)} for target+1")

    print("\n(4) fault injection: bias the rel32 arithmetic by 1, the known call must vanish")
    biased = {x["at"] for x in scan(0x2AC7D, kinds=("call",), rel_bias=1, **kw)["call"]}
    if "0x2ac63" in biased:
        fails.append("rel32 arithmetic is not load-bearing: biased scan still found 0x2ac63")
        print("    FAIL: still found")
    else:
        print("    PASS: vanished under injected fault")

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
    ap.add_argument("--target", type=lambda s: int(s, 0))
    ap.add_argument("--kinds", default="call,jmp,abs")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.target is None:
        ap.error("need --target (or --selftest)")

    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    hits = scan(args.target, kinds=kinds)
    for kind in kinds:
        rows = hits.get(kind, [])
        print(f"{kind}: {len(rows)} hit(s)")
        for r in rows[:40]:
            print(f"   {r['at']}  ctx {r['context']}")
        if len(rows) > 40:
            print(f"   ... {len(rows) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
