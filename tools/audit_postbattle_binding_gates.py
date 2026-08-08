#!/usr/bin/env python3
"""Report evidence gates for unbound postbattle handler bindings.

This is deliberately read-only: it never promotes a generated skeleton.  The
native main loop proves that player battle N dispatches raw ch(N-1)_post, so
the audit also rejects an active binding whose raw handler index does not
match that relation.  It compares each handler beat's original call-site
address with the address-keyed fields in the generated binding, so the
remaining work is explicit and reviewable.
"""
from __future__ import annotations

import argparse
import json
import re
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


def has_proven_native_semantics(beat: dict) -> bool:
    """Mirror only exact, source-keyed native lowerings accepted by runtime.

    This list must stay narrower than generic native targets: 0x11d40 has many
    register-driven and partial-range callers whose semantics remain blocked.
    """
    source = beat.get("source") or {}
    key = (source.get("addr"), source.get("target"), beat.get("native_target"))
    if key == ("0x23599", "0x11d40", "0x11d40"):
        return beat.get("raw_args") == [64, 255, 0]
    if key in {
        ("0x23623", "0x1f882", "0x1f882"),
        ("0x23eba", "0x1f882", "0x1f882"),
    }:
        # The exporter preserves the no-argument helper's caller register
        # snapshot as provenance; it is not an argument list.
        return beat.get("raw_args") in ([], ["ebx", "esi", "edi"])
    if key in {
        ("0x23628", "0x13536", "0x13536"),
        ("0x23ebf", "0x13536", "0x13536"),
    }:
        return beat.get("raw_args") == []
    return False


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
        match = re.fullmatch(r"postbattle_ch(\d+)_persist", node_id)
        if not match:
            continue
        stem = f"ch{int(match.group(1)) - 1:02d}"
        handler_path = handlers_dir / f"{stem}_post.json"
        binding_path = generated_dir / f"{stem}_post.json"
        expected_active_binding = f"assets/cutscenes/bindings/{stem}_post.json"
        active_binding = node.get("handler_binding", "")
        inline_beat_count = len(node.get("beats", []))
        active_path = campaign_path.parent.parent.parent / active_binding if active_binding else None
        evidence_binding_path = (
            active_path
            if active_binding == expected_active_binding and active_path is not None and active_path.exists()
            else binding_path
        )
        handler = json.loads(handler_path.read_text(encoding="utf-8")) if handler_path.exists() else {}
        binding = json.loads(evidence_binding_path.read_text(encoding="utf-8")) if evidence_binding_path.exists() else {}
        overrides = binding.get("overrides", {})
        dialogue_overrides = binding.get("dialogue_overrides", {})
        contexts = binding.get("dialogue_contexts", {})
        gaps = []
        ops = Counter()
        for beat in walk(handler.get("beats", [])):
            op = beat.get("op")
            ops[op] += 1
            if op == "unknown":
                if has_proven_native_semantics(beat):
                    continue
                source = beat.get("source") or {}
                gaps.append({"op": op, "source_addr": source.get("addr"), "required": "native_semantics"})
                continue
            field = REQUIRED_FIELDS.get(op)
            if not field:
                continue
            source = beat.get("source") or {}
            addr = source.get("addr")
            covered = False
            override = overrides.get(addr, {}) if isinstance(addr, str) else {}
            # A single native call site can receive branch-local immediates.
            # Authored bindings may scope the override as ``addr#acting_id``;
            # preserve that provenance instead of treating the shared call as
            # an uncovered generic operation.
            if op == "act" and isinstance(addr, str) and isinstance(beat.get("acting_id"), int):
                scoped = overrides.get(f"{addr}#{beat['acting_id']}")
                if isinstance(scoped, dict):
                    override = scoped
            if field == "dialog":
                covered = isinstance(override, dict) and "dialog" in override
                covered = covered or (isinstance(addr, str) and addr in contexts)
                text_index = beat.get("text_index")
                if isinstance(addr, str) and isinstance(text_index, int):
                    covered = covered or f"{addr}#{text_index}" in dialogue_overrides
            else:
                covered = isinstance(override, dict) and field in override
            if not covered:
                gaps.append({"op": op, "source_addr": addr, "required": field})
        if active_binding and active_binding != expected_active_binding:
            status = "active_index_mismatch"
        elif active_binding and binding.get("evidence_only"):
            status = "active_evidence_only"
        elif active_binding:
            status = "active"
        elif inline_beat_count:
            # An unbound postbattle with inline beats bypasses the runtime's
            # empty-node guard and can silently skip the native handler.
            status = "unbound_inline_beats"
        elif not handler_path.exists() or not binding_path.exists():
            status = "blocked"
        elif binding.get("evidence_only"):
            # Typed raw operations may have no compiler gap while their
            # indexed renderer is still absent.  An evidence-only binding is
            # never a complete campaign mapping; keep the node blocked until
            # an authored, runnable binding replaces it.
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
            "evidence_binding": str(evidence_binding_path) if evidence_binding_path.exists() else "",
            "expected_handler_binding": expected_active_binding,
            "active_handler_binding": active_binding,
            "inline_beat_count": inline_beat_count,
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
