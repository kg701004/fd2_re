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
from pathlib import Path


def audit(path: Path) -> dict:
    campaign = json.loads(path.read_text(encoding="utf-8"))
    entries = []
    for node_id, node in sorted(campaign.get("nodes", {}).items()):
        if node.get("type") not in {"story", "cutscene"}:
            continue
        entries.append({
            "id": node_id,
            "type": node.get("type"),
            "script": node.get("script", ""),
            "scene": node.get("scene", ""),
            "handler_binding": node.get("handler_binding", ""),
            "next": node.get("next", ""),
        })
    scripted = [entry for entry in entries if entry["script"]]
    return {
        "campaign": str(path),
        "story_or_cutscene_nodes": len(entries),
        "scripted_nodes": len(scripted),
        "unresolved_nodes": len(entries) - len(scripted),
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
        print(f"story/cutscene={report['story_or_cutscene_nodes']} scripted={report['scripted_nodes']} unresolved={report['unresolved_nodes']}")
        for node in report["nodes"]:
            if not node["script"]:
                print(f"UNRESOLVED {node['id']} type={node['type']} next={node['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
