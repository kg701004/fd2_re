#!/usr/bin/env python3
"""Audit campaign story/cutscene script wiring without guessing mappings.

This is intentionally read-only. A chapter-number match is not enough to
choose a scene: one story JSON can contain pre-battle, post-battle, and branch
scenes. The tool reports coverage and leaves unresolved nodes for evidence
review.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def audit(path: Path) -> dict:
    campaign = json.loads(path.read_text(encoding="utf-8"))
    entries = []
    generated_dir = path.parent.parent / "cutscenes" / "bindings" / "generated"
    for node_id, node in sorted(campaign.get("nodes", {}).items()):
        if node.get("type") not in {"story", "cutscene"}:
            continue
        if node.get("script"):
            role = "direct_script"
        elif node.get("handler_binding"):
            role = "handler_bound"
        elif node_id.startswith("retreat_"):
            role = "authored_retreat"
        elif node_id.startswith("rumor_"):
            role = "authored_rumor"
        elif node_id.startswith("postbattle_"):
            role = "unbound_postbattle"
        else:
            role = "generic_story_fallback"
        generated_binding = ""
        if node_id.startswith("postbattle_"):
            match = re.fullmatch(r"postbattle_ch(\d+)_persist", node_id)
            handler_name = f"ch{int(match.group(1)) - 1:02d}_post.json" if match else ""
            candidate = generated_dir / handler_name
            if candidate.exists():
                generated_binding = str(candidate)
        entries.append({
            "id": node_id,
            "type": node.get("type"),
            "coverage_role": role,
            "script": node.get("script", ""),
            "scene": node.get("scene", ""),
            "handler_binding": node.get("handler_binding", ""),
            "generated_binding_skeleton": generated_binding,
            "next": node.get("next", ""),
        })
    counts = {}
    for entry in entries:
        counts[entry["coverage_role"]] = counts.get(entry["coverage_role"], 0) + 1
    scripted = counts.get("direct_script", 0)
    handler_bound = counts.get("handler_bound", 0)
    fallback = len(entries) - scripted - handler_bound
    skeletons = sum(bool(entry["generated_binding_skeleton"]) for entry in entries)
    unbound_skeletons = sum(
        bool(entry["generated_binding_skeleton"])
        and not entry["handler_binding"]
        for entry in entries
    )
    return {
        "campaign": str(path),
        "story_or_cutscene_nodes": len(entries),
        "scripted_nodes": scripted,
        "handler_bound_nodes": handler_bound,
        "fallback_nodes_without_script_or_handler": fallback,
        "generated_binding_skeletons": skeletons,
        "unbound_generated_binding_skeletons": unbound_skeletons,
        "coverage_roles": counts,
        "nodes": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", default="remake/assets/scenarios/campaign_full.json", type=Path)
    parser.add_argument("--json", action="store_true", help="emit the complete node list as JSON")
    args = parser.parse_args()
    report = audit(args.campaign)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"story/cutscene={report['story_or_cutscene_nodes']} "
            f"scripted={report['scripted_nodes']}"
        )
        print(
            f"handler_bound={report['handler_bound_nodes']} "
            f"fallback_without_script_or_handler={report['fallback_nodes_without_script_or_handler']} "
            f"generated_skeletons={report['generated_binding_skeletons']} "
            f"unbound_generated_skeletons={report['unbound_generated_binding_skeletons']}"
        )
        for node in report["nodes"]:
            if node["coverage_role"] not in {"direct_script", "handler_bound"}:
                print(f"{node['coverage_role'].upper()} {node['id']} type={node['type']} next={node['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
