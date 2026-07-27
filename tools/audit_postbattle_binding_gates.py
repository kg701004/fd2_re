#!/usr/bin/env python3
"""Report evidence gates for unbound postbattle handler bindings.

This is deliberately read-only: it never promotes a generated skeleton and
never infers a runtime meaning from a chapter number.  It compares each
handler beat's original call-site address with the address-keyed fields in the
generated binding, so the remaining work is explicit and reviewable.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = {
    "loadch": "loadch",
    "load_ch_text": "loadch",
    "pan": "pan",
    "dialog": "dialog",
    "act": "act",
    "layout_units": "layout",
}


def walk(beats):
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        yield beat
        yield from walk(beat.get("then", []))
        yield from walk(beat.get("else", []))


def audit(campaign_path: Path, handlers_dir: Path, generated_dir: Path) -> dict:
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    rows = []
    for node_id, node in sorted(campaign.get("nodes", {}).items()):
        if node.get("type") != "cutscene" or not node_id.startswith("postbattle_"):
            continue
        stem = node_id.removeprefix("postbattle_").removesuffix("_persist")
        handler_path = handlers_dir / f"{stem}_post.json"
        binding_path = generated_dir / f"{stem}_post.json"
        handler = json.loads(handler_path.read_text(encoding="utf-8")) if handler_path.exists() else {}
        binding = json.loads(binding_path.read_text(encoding="utf-8")) if binding_path.exists() else {}
        overrides = binding.get("overrides", {})
        contexts = binding.get("dialogue_contexts", {})
        gaps = []
        ops = Counter()
        for beat in walk(handler.get("beats", [])):
            op = beat.get("op")
            ops[op] += 1
            field = REQUIRED_FIELDS.get(op)
            if not field:
                continue
            source = beat.get("source") or {}
            addr = source.get("addr")
            covered = False
            override = overrides.get(addr, {}) if isinstance(addr, str) else {}
            if field == "dialog":
                covered = isinstance(override, dict) and "dialog" in override
                covered = covered or (isinstance(addr, str) and addr in contexts)
            else:
                covered = isinstance(override, dict) and field in override
            if not covered:
                gaps.append({"op": op, "source_addr": addr, "required": field})
        if node.get("handler_binding"):
            status = "active"
        elif not handler_path.exists() or not binding_path.exists():
            status = "blocked"
        elif gaps:
            status = "blocked"
        else:
            # A complete generated mapping is evidence for the next review,
            # not permission to activate it in campaign_full.json.
            status = "unbound_mapping_complete"
        rows.append({
            "node": node_id,
            "handler": str(handler_path),
            "generated_binding": str(binding_path) if binding_path.exists() else "",
            "active_handler_binding": node.get("handler_binding", ""),
            "operation_counts": dict(sorted(ops.items())),
            "mapping_gaps": gaps,
            "status": status,
        })
    status_counts = Counter(row["status"] for row in rows)
    gap_counts = Counter(gap["required"] for row in rows for gap in row["mapping_gaps"])
    return {
        "campaign": str(campaign_path),
        "postbattle_nodes": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "mapping_gap_counts": dict(sorted(gap_counts.items())),
        "nodes": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("campaign", nargs="?", type=Path, default=Path("remake/assets/scenarios/campaign_full.json"))
    args = parser.parse_args()
    root = args.campaign.parent.parent
    report = audit(args.campaign, root / "cutscenes/handlers", root / "cutscenes/bindings/generated")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"postbattle_nodes={report['postbattle_nodes']} status={report['status_counts']}")
        print(f"mapping_gaps={report['mapping_gap_counts']}")
        for row in report["nodes"]:
            print(f"{row['status'].upper()} {row['node']} gaps={len(row['mapping_gaps'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
