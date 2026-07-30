#!/usr/bin/env python3
import json
from pathlib import Path
import tempfile
import unittest

import sync_native_selector_fields as sync


class NativeTableVersionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.manifest = Path(self.directory.name) / "reference.json"
        self.manifest.write_text(
            json.dumps({
                "files": [{
                    "file": "FD2.EXE",
                    "size": 357074,
                    "md5": "b97caf2239a27a896069d03549d96e1e",
                    "sha256": "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f",
                }],
            }),
            encoding="utf-8",
        )
        self.tables = {
            "source": "FD2.EXE",
            "source_size": 357074,
            "source_md5": "b97caf2239a27a896069d03549d96e1e",
            "source_sha256": "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f",
        }

    def tearDown(self):
        self.directory.cleanup()

    def test_accepts_reference_executable(self):
        sync.validate_native_tables(self.tables, self.manifest)

    def test_rejects_unbound_table_dump(self):
        bad = dict(self.tables)
        del bad["source_md5"]
        with self.assertRaisesRegex(ValueError, "source_md5"):
            sync.validate_native_tables(bad, self.manifest)

    def test_rejects_different_executable_hash(self):
        bad = dict(self.tables)
        bad["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_sha256"):
            sync.validate_native_tables(bad, self.manifest)


if __name__ == "__main__":
    unittest.main()
