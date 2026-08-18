#!/usr/bin/env python3
import json
from pathlib import Path
import tempfile
import unittest

import export_handler_dialogue_bindings as export_tool


def write_handler(directory: Path, name: str, chapter: int, beats: list) -> Path:
    path = directory / name
    path.write_text(
        json.dumps({"schema_version": 1, "chapter": chapter, "phase": "post", "handler": "0x1000", "beats": beats}),
        encoding="utf-8",
    )
    return path


class ExportHandlerSharedCallSiteTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.handlers_dir = Path(self.directory.name)
        self.output_dir = self.handlers_dir / "out"
        self.map_path = self.handlers_dir / "count-aligned.json"

    def tearDown(self):
        self.directory.cleanup()

    def test_identical_branch_contexts_at_shared_addr_collapse_to_one_entry(self):
        # Mirrors ch15_post.json: an if/then/else where both arms dialog the
        # same call site with different text_index but no loadch override, so
        # both resolve to the same FDTXT_003/script context.
        beats = [
            {
                "op": "if",
                "source": {"addr": "0x1001"},
                "then": [
                    {"op": "dialog", "text_index": 0, "source": {"addr": "0x2000"}},
                ],
                "else": [
                    {"op": "dialog", "text_index": 1, "source": {"addr": "0x2000"}},
                ],
            },
        ]
        handler_path = write_handler(self.handlers_dir, "ch03_post.json", 3, beats)
        unique_mappings = {
            "FDTXT_003": {
                "source_dat": "FDTXT_003",
                "script": "shared_script",
                "mappings": [
                    {"string_index": 0, "targets": ["t0"]},
                    {"string_index": 1, "targets": ["t1"]},
                ],
            },
        }

        binding, report = export_tool.export_handler(
            handler_path, self.output_dir, self.map_path, unique_mappings
        )

        self.assertEqual(
            binding["dialogue_contexts"],
            {"0x2000": {"source_dat": "FDTXT_003", "script": "shared_script"}},
        )
        self.assertEqual(report["dialogue_context_count"], 1)
        self.assertEqual(report["skipped_dialogs"], [])

    def test_conflicting_branch_contexts_at_shared_addr_raise(self):
        # One arm re-selects FDTXT via loadch before reaching the shared call
        # site; the other arm keeps the handler's initial FDTXT. The two
        # branches then legitimately disagree about the active resource for
        # the same physical dialog call -- this must still fail loudly.
        beats = [
            {
                "op": "if",
                "source": {"addr": "0x1001"},
                "then": [
                    {"op": "loadch", "chapter": 5, "source": {"addr": "0x1002"}},
                    {"op": "dialog", "text_index": 0, "source": {"addr": "0x2000"}},
                ],
                "else": [
                    {"op": "dialog", "text_index": 0, "source": {"addr": "0x2000"}},
                ],
            },
        ]
        handler_path = write_handler(self.handlers_dir, "ch03_post.json", 3, beats)
        unique_mappings = {
            "FDTXT_003": {
                "source_dat": "FDTXT_003",
                "script": "else_script",
                "mappings": [{"string_index": 0, "targets": ["t0"]}],
            },
            "FDTXT_006": {
                "source_dat": "FDTXT_006",
                "script": "then_script",
                "mappings": [{"string_index": 0, "targets": ["t0"]}],
            },
        }

        with self.assertRaisesRegex(ValueError, "resolves to conflicting contexts"):
            export_tool.export_handler(handler_path, self.output_dir, self.map_path, unique_mappings)

    def test_build_exports_end_to_end_with_shared_call_site(self):
        beats = [
            {
                "op": "if",
                "source": {"addr": "0x1001"},
                "then": [
                    {"op": "dialog", "text_index": 0, "source": {"addr": "0x2000"}},
                ],
                "else": [
                    {"op": "dialog", "text_index": 1, "source": {"addr": "0x2000"}},
                ],
            },
        ]
        write_handler(self.handlers_dir, "ch03_post.json", 3, beats)
        self.map_path.write_text(
            json.dumps({
                "schema_version": 1,
                "mapping_kind": "count_aligned_only",
                "resources": [{
                    "source_dat": "FDTXT_003",
                    "script_mappings": [{
                        "status": "count_aligned",
                        "source_dat": "FDTXT_003",
                        "script": "shared_script",
                        "mappings": [
                            {"string_index": 0, "targets": ["t0"]},
                            {"string_index": 1, "targets": ["t1"]},
                        ],
                    }],
                }],
            }),
            encoding="utf-8",
        )

        planned, diagnostics = export_tool.build_exports(self.handlers_dir, self.map_path, self.output_dir)

        self.assertEqual(diagnostics["summary"]["handler_count"], 1)
        self.assertEqual(diagnostics["summary"]["dialogue_context_count"], 1)
        self.assertEqual(diagnostics["summary"]["skipped_dialogue_count"], 0)
        binding_path, binding = planned[0]
        self.assertEqual(binding_path.name, "ch03_post.json")
        self.assertEqual(
            binding["dialogue_contexts"],
            {"0x2000": {"source_dat": "FDTXT_003", "script": "shared_script"}},
        )


if __name__ == "__main__":
    unittest.main()
