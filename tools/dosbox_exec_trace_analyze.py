#!/usr/bin/env python3
"""Translate + cross-reference a dosbox_exec_trace.sh capture against Ghidra.

Takes the deduplicated "CCCC:IIIIIIII" (live CS:EIP) address list produced by
`tools/dosbox_exec_trace.sh dedup` (see that script's header comment for the
full capture workflow, and docs/knowledge-base/98-tooling-infrastructure.md for
the worked example), translates the addresses in the main game code segment to
native/static addresses (native = live_eip - delta, delta defaults to 0x19C000
per this project's established convention -- see doc48/doc58), batches them
through tools/ghidra_batch_probe.py's `function_bounds` action in a single
analyzeHeadless invocation, and classifies every unique native address into:

  (a) in a Ghidra function whose name is still the auto-generated "FUN_xxxxxxxx"
      AND that address also appears in this repo's docs/knowledge-base/*.md --
      i.e. already investigated by a previous round (best-effort grep, not
      authoritative -- always read the matched doc section yourself).
  (b) in_function=true, FUN_-named, and NOT found in the docs grep -- Ghidra has
      already built a function boundary here, but no prior round has written it
      up. These are worth a `decompile` query before chasing further.
  (c) in_function=false -- genuinely outside any function boundary Ghidra's base
      analysis ever built. These are the real "nobody has looked here" leads:
      doc35 §9's repeated experience is that the actual montage-renderer code
      lives in exactly this kind of region (see §9.10-§9.11), because Ghidra's
      auto-analysis never walked into it from any statically-visible call.

Category (c) addresses are also clustered into contiguous-ish ranges (gap <=
--cluster-gap, default 0x40 bytes) since a real function will show up as a
run of many adjacent hit addresses, not isolated singletons.

Usage:
    python tools/dosbox_exec_trace_analyze.py trace_unique_cseip.txt \\
        --out-dir .wsl_build/trace_analysis

    # non-default segment/delta (only relevant if you captured a different CS,
    # see the segment breakdown this tool prints -- 0170 is the main game code
    # segment in this project's DOS4GW layout, other segments seen in captures
    # so far are DPMI/BIOS/interrupt-thunk segments, not game code):
    python tools/dosbox_exec_trace_analyze.py trace_unique_cseip.txt \\
        --cs 0170 --delta 0x19C000 --out-dir .wsl_build/trace_analysis

Output (written under --out-dir):
    natives.json          sorted unique native addresses actually queried
    ghidra_results.json   raw tools/ghidra_batch_probe.py output
    summary.json          classified a/b/c breakdown + category-c clusters
    summary.txt           human-readable version of the same

This script only READS FD2Analysis3 (via ghidra_batch_probe.py's -readOnly
analyzeHeadless invocation) -- it never modifies the Ghidra project.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

DEFAULT_DELTA = 0x19C000
DEFAULT_CS = "0170"
REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_trace(src: Path, cs_filter: str, delta: int) -> tuple[set[int], Counter]:
    natives: set[int] = set()
    cs_counts: Counter = Counter()
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            cs, eip = line.split(":", 1)
            cs_counts[cs] += 1
            if cs != cs_filter:
                continue
            try:
                eip_val = int(eip, 16)
            except ValueError:
                continue
            native = eip_val - delta
            if native < 0:
                continue
            natives.add(native)
    return natives, cs_counts


def run_ghidra_batch(natives: list[int], out_dir: Path, ghidra_probe_args: list[str]) -> list[dict]:
    queries = [
        {"id": f"q{i}", "address": hex(addr), "action": "function_bounds"}
        for i, addr in enumerate(natives)
    ]
    queries_path = out_dir / "queries.json"
    results_path = out_dir / "ghidra_results.json"
    queries_path.write_text(json.dumps(queries), encoding="utf-8")

    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "ghidra_batch_probe.py"),
        "--queries", str(queries_path),
        "--output", str(results_path),
        "--quiet",
        *ghidra_probe_args,
    ]
    print(f"[dosbox_exec_trace_analyze] running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"ghidra_batch_probe.py failed with exit code {proc.returncode}")

    return json.loads(results_path.read_text(encoding="utf-8"))


_DOCS_CACHE: dict[str, str] | None = None


def _load_docs_cache() -> dict[str, str]:
    global _DOCS_CACHE
    if _DOCS_CACHE is not None:
        return _DOCS_CACHE
    kb_dir = REPO_ROOT / "docs" / "knowledge-base"
    cache: dict[str, str] = {}
    if kb_dir.exists():
        for md in kb_dir.glob("*.md"):
            try:
                cache[md.name] = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    _DOCS_CACHE = cache
    return cache


import re

_HEXDIGIT_CLASS = "0-9A-Fa-f"


def grep_docs_for_address(addr: int) -> list[str]:
    """Best-effort: which docs/knowledge-base/*.md files mention this hex address
    as a genuine standalone address token (0x-prefixed or bare, but never as a
    substring of a longer hex run -- e.g. inside an MD5 hash, a URL, or a longer
    address). Not authoritative -- a hit means "go read that file", not "this
    address is fully understood". Word-boundary safety matters a lot here: an
    earlier, unguarded substring-match version of this function produced false
    "already known" hits from things like `3c0a2c935260b8ca80432b25b3600111`
    (an MD5 string containing "432b2" as a substring) and a baidu.com URL
    containing "43385" -- exactly the kind of coincidental-address-overlap trap
    doc35 §9 spent many rounds getting burned by, so this is not a hypothetical
    concern for this project."""
    hexs = f"{addr:x}"
    # optional "0x"/"0X" prefix, then the digits, with NO hex digit immediately
    # before or after (lookaround, case-insensitive) so we never match inside a
    # longer hex run (hash, longer address, etc).
    pattern = re.compile(
        rf"(?<![{_HEXDIGIT_CLASS}])(?:0[xX])?{hexs}(?![{_HEXDIGIT_CLASS}])",
        re.IGNORECASE,
    )
    hits = []
    for name, text in _load_docs_cache().items():
        if pattern.search(text):
            hits.append(name)
    return hits


def grep_docs_for_any_address(addrs: list[int]) -> list[str]:
    """Union of doc hits across every address in addrs (used for category-c
    clusters, where the interesting addresses are rarely the cluster boundary
    itself -- a prior round may have written up any address inside the span)."""
    hits: set[str] = set()
    for a in addrs:
        hits.update(grep_docs_for_address(a))
    return sorted(hits)


def cluster(addrs: list[int], gap: int) -> list[tuple[int, int]]:
    if not addrs:
        return []
    addrs = sorted(addrs)
    ranges = []
    start = prev = addrs[0]
    for a in addrs[1:]:
        if a - prev <= gap:
            prev = a
            continue
        ranges.append((start, prev))
        start = prev = a
    ranges.append((start, prev))
    return ranges


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trace_file", type=Path, help="trace_unique_cseip.txt from dosbox_exec_trace.sh dedup")
    ap.add_argument("--cs", default=DEFAULT_CS, help=f"live CS segment to translate (default {DEFAULT_CS} = main game code)")
    ap.add_argument("--delta", type=lambda s: int(s, 0), default=DEFAULT_DELTA, help=f"native = live_eip - delta (default 0x{DEFAULT_DELTA:X})")
    ap.add_argument("--cluster-gap", type=lambda s: int(s, 0), default=0x40, help="max byte gap to merge category-c addresses into one cluster (default 0x40)")
    ap.add_argument("--out-dir", type=Path, required=True, help="directory to write natives.json/ghidra_results.json/summary.{json,txt}")
    ap.add_argument("--skip-docs-grep", action="store_true", help="skip the best-effort docs/*.md grep classification pass (faster for very large in_function sets)")
    ap.add_argument("--ghidra", help="passed through to ghidra_batch_probe.py --ghidra")
    ap.add_argument("--project-dir", help="passed through to ghidra_batch_probe.py --project-dir")
    ap.add_argument("--project-name", help="passed through to ghidra_batch_probe.py --project-name")
    args = ap.parse_args()

    if not args.trace_file.exists():
        print(f"error: trace file not found: {args.trace_file}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    natives, cs_counts = parse_trace(args.trace_file, args.cs, args.delta)
    natives_sorted = sorted(natives)
    print(f"[dosbox_exec_trace_analyze] segment breakdown (unique CS:EIP by segment): {dict(cs_counts)}")
    print(f"[dosbox_exec_trace_analyze] {len(natives_sorted)} unique native addresses in CS={args.cs}")
    (args.out_dir / "natives.json").write_text(json.dumps([hex(a) for a in natives_sorted]), encoding="utf-8")

    probe_args = []
    if args.ghidra:
        probe_args += ["--ghidra", args.ghidra]
    if args.project_dir:
        probe_args += ["--project-dir", args.project_dir]
    if args.project_name:
        probe_args += ["--project-name", args.project_name]

    results = run_ghidra_batch(natives_sorted, args.out_dir, probe_args)

    addr_by_id = {r["id"]: int(r["address"], 16) for r in results}
    in_func = []
    not_in_func = []
    for r in results:
        addr = addr_by_id[r["id"]]
        res = r.get("result") or {}
        if r.get("ok") and isinstance(res, dict) and res.get("in_function") is True:
            in_func.append((addr, res))
        else:
            not_in_func.append(addr)

    func_counter: Counter = Counter()
    for addr, res in in_func:
        name = res.get("name", "?")
        start = res.get("start", "?")
        func_counter[(name, start)] += 1

    category_a = []  # FUN_ named + mentioned in docs (previously investigated)
    category_b = []  # FUN_ named + not found in docs (analyzed, undocumented)
    if not args.skip_docs_grep:
        for (name, start), count in func_counter.items():
            start_addr = int(start, 16)
            hits = grep_docs_for_address(start_addr)
            entry = {"name": name, "start": start, "unique_addr_hit_count": count, "doc_hits": hits}
            if hits:
                category_a.append(entry)
            else:
                category_b.append(entry)
        category_a.sort(key=lambda e: -e["unique_addr_hit_count"])
        category_b.sort(key=lambda e: -e["unique_addr_hit_count"])

    ranges = cluster(not_in_func, args.cluster_gap)
    category_c = []
    for s, e in ranges:
        cluster_addrs = [a for a in not_in_func if s <= a <= e]
        doc_hits = [] if args.skip_docs_grep else grep_docs_for_any_address(cluster_addrs)
        category_c.append({
            "start": hex(s), "end": hex(e), "span_bytes": e - s,
            "addr_count": len(cluster_addrs),
            "doc_hits": doc_hits,
            "previously_known": bool(doc_hits),
        })
    category_c.sort(key=lambda c: -c["span_bytes"])

    summary = {
        "trace_file": str(args.trace_file),
        "cs_filter": args.cs,
        "delta": hex(args.delta),
        "total_unique_native_addrs": len(natives_sorted),
        "in_function_count": len(in_func),
        "not_in_function_count": len(not_in_func),
        "category_a_known_documented": category_a,
        "category_b_analyzed_undocumented": category_b,
        "category_c_genuinely_unanalyzed_clusters": category_c,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = []
    lines.append(f"trace: {args.trace_file}")
    lines.append(f"{len(natives_sorted)} unique native addrs (CS={args.cs}, delta={hex(args.delta)})")
    lines.append(f"  in_function=true : {len(in_func)}")
    lines.append(f"  in_function=false: {len(not_in_func)}")
    if not args.skip_docs_grep:
        lines.append("")
        lines.append(f"category (a) known/documented functions: {len(category_a)}")
        for e in category_a[:20]:
            lines.append(f"  {e['unique_addr_hit_count']:5d}  {e['name']}  start={e['start']}  docs={e['doc_hits']}")
        lines.append("")
        lines.append(f"category (b) Ghidra-analyzed but UNDOCUMENTED functions: {len(category_b)}")
        for e in category_b[:40]:
            lines.append(f"  {e['unique_addr_hit_count']:5d}  {e['name']}  start={e['start']}")
    new_c = [c for c in category_c if not c["previously_known"]]
    known_c = [c for c in category_c if c["previously_known"]]
    lines.append("")
    lines.append(f"category (c) genuinely unanalyzed clusters (in_function=false): {len(category_c)}  ->  {len(new_c)} NEW (no doc mentions), {len(known_c)} already referenced somewhere in docs")
    lines.append(f"  -- NEW (nobody has written these up before) --")
    for c in new_c:
        lines.append(f"  0x{int(c['start'],16):X} .. 0x{int(c['end'],16):X}  span=0x{c['span_bytes']:X}  ({c['addr_count']} hit addrs)")
    lines.append(f"  -- already known (some address in range is mentioned in docs -- confirms a prior finding, not new) --")
    for c in known_c:
        lines.append(f"  0x{int(c['start'],16):X} .. 0x{int(c['end'],16):X}  span=0x{c['span_bytes']:X}  ({c['addr_count']} hit addrs)  docs={c['doc_hits']}")

    summary_txt = "\n".join(lines)
    (args.out_dir / "summary.txt").write_text(summary_txt, encoding="utf-8")
    print(summary_txt)
    print(f"\n[dosbox_exec_trace_analyze] wrote {args.out_dir}/{{natives,ghidra_results,summary}}.json and summary.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
