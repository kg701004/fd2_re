#!/usr/bin/env python3
"""Small, dependency-free regression tests for raw constructor projection."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import export_units


def table(record_size, records):
    return {
        "count": len(records),
        "record_size": record_size,
        "records": [{"bytes_hex": bytes(row).hex()} for row in records],
    }


class NativeConstructorProjectionTest(unittest.TestCase):
    def test_high_branch_uses_word_plus_two_times_level(self):
        high = [bytearray(10) for _ in range(1)]
        high[0][2:4] = (0x0102).to_bytes(2, "little")
        high[0][4] = 7
        tables = {"tables": {"high_class": table(10, high)}}
        self.assertEqual(export_units.native_record_word42_for_raw_unit_key(tables, 0x44, 3), 0x0306)
        self.assertEqual(export_units.native_record_word46_for_raw_unit_key(tables, 0x44, 3), 21)

    def test_lower_branch_uses_word_plus_three_and_aux_byte_six(self):
        lower = [bytearray(24) for _ in range(1)]
        lower[0][3:5] = (0x0102).to_bytes(2, "little")
        lower[0][5:7] = (0x0203).to_bytes(2, "little")
        aux = [bytearray(11) for _ in range(1)]
        aux[0][6] = 4
        aux[0][8] = 5
        tables = {"tables": {
            "lower_class": table(24, lower),
            "lower_aux": table(11, aux),
        }}
        self.assertEqual(export_units.native_record_word42_for_raw_unit_key(tables, 0, 4), 0x0102 + 12)
        self.assertEqual(export_units.native_record_word46_for_raw_unit_key(tables, 0, 4), 0x0203 + 15)

    def test_malformed_or_missing_provenance_fails_closed(self):
        tables = {"tables": {"high_class": table(10, [bytearray(9)])}}
        self.assertIsNone(export_units.native_record_word42_for_raw_unit_key(tables, 0x44, 1))
        self.assertIsNone(export_units.native_record_word46_for_raw_unit_key(tables, 0x44, 1))
        self.assertIsNone(export_units.native_record_word42_for_raw_unit_key({}, 0x44, 1))
        self.assertIsNone(export_units.native_record_word46_for_raw_unit_key({}, 0x44, 1))
        self.assertIsNone(export_units.native_record_word42_for_raw_unit_key(tables, 0x44, 0))
        self.assertIsNone(export_units.native_record_word46_for_raw_unit_key(tables, 0x44, 0))

    def test_high_branch_ap_dp_mv(self):
        # record: RA CL HP(lo,hi) MP AP DP DX MV EX
        high = [bytearray(10) for _ in range(1)]
        high[0][5] = 30  # AP growth
        high[0][6] = 18  # DP growth
        high[0][7] = 6   # DX growth (unused here, just kept realistic)
        high[0][8] = 6   # MV, flat
        tables = {"tables": {"high_class": table(10, high)}}
        self.assertEqual(export_units.native_ap_for_raw_unit_key(tables, 0x44, 14), 30 * 14)
        self.assertEqual(export_units.native_dp_for_raw_unit_key(tables, 0x44, 14), 18 * 14)
        self.assertEqual(export_units.native_mv_for_raw_unit_key(tables, 0x44), 6)
        # MV takes no level argument and must not scale with level.
        self.assertEqual(export_units.native_mv_for_raw_unit_key(tables, 0x44), export_units.native_mv_for_raw_unit_key(tables, 0x44))

    def test_lower_branch_ap_dp_mv(self):
        # lower_class record: ... MV@+7 ... AP_base@+0x12(word) DP_base@+0x14(word) ...
        lower = [bytearray(24) for _ in range(1)]
        lower[0][7] = 4  # MV, flat
        lower[0][0x12:0x14] = (100).to_bytes(2, "little")  # AP base word
        lower[0][0x14:0x16] = (50).to_bytes(2, "little")   # DP base word
        aux = [bytearray(11) for _ in range(1)]
        aux[0][0] = 3  # AP growth (aux+0)
        aux[0][2] = 2  # DP growth (aux+2)
        tables = {"tables": {
            "lower_class": table(24, lower),
            "lower_aux": table(11, aux),
        }}
        self.assertEqual(export_units.native_ap_for_raw_unit_key(tables, 0, 15), 3 * 15 + 100)
        self.assertEqual(export_units.native_dp_for_raw_unit_key(tables, 0, 15), 2 * 15 + 50)
        self.assertEqual(export_units.native_mv_for_raw_unit_key(tables, 0), 4)

    def test_ap_dp_mv_malformed_or_missing_provenance_fails_closed(self):
        tables = {"tables": {"high_class": table(10, [bytearray(9)])}}
        self.assertIsNone(export_units.native_ap_for_raw_unit_key(tables, 0x44, 1))
        self.assertIsNone(export_units.native_dp_for_raw_unit_key(tables, 0x44, 1))
        self.assertIsNone(export_units.native_mv_for_raw_unit_key(tables, 0x44))
        self.assertIsNone(export_units.native_ap_for_raw_unit_key({}, 0x44, 1))
        self.assertIsNone(export_units.native_dp_for_raw_unit_key({}, 0x44, 1))
        self.assertIsNone(export_units.native_mv_for_raw_unit_key({}, 0x44))
        self.assertIsNone(export_units.native_ap_for_raw_unit_key(tables, 0x44, 0))
        self.assertIsNone(export_units.native_dp_for_raw_unit_key(tables, 0x44, 0))

    def test_real_fixture_has_expected_raw_dimensions(self):
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "exe_tables", "native_unit_tables.json")
        with open(path, encoding="utf-8") as f:
            tables = json.load(f)
        self.assertEqual((tables["tables"]["high_class"]["count"], tables["tables"]["high_class"]["record_size"]), (68, 10))
        self.assertEqual((tables["tables"]["lower_class"]["count"], tables["tables"]["lower_class"]["record_size"]), (32, 24))
        self.assertEqual((tables["tables"]["lower_aux"]["count"], tables["tables"]["lower_aux"]["record_size"]), (68, 11))
        self.assertIsInstance(export_units.native_record_word42_for_raw_unit_key(tables, 0x44, 1), int)
        self.assertIsInstance(export_units.native_record_word42_for_raw_unit_key(tables, 0, 1), int)
        self.assertIsInstance(export_units.native_record_word46_for_raw_unit_key(tables, 0x44, 1), int)
        self.assertIsInstance(export_units.native_record_word46_for_raw_unit_key(tables, 0, 1), int)
        self.assertIsInstance(export_units.native_ap_for_raw_unit_key(tables, 0x44, 1), int)
        self.assertIsInstance(export_units.native_ap_for_raw_unit_key(tables, 0, 1), int)
        self.assertIsInstance(export_units.native_dp_for_raw_unit_key(tables, 0x44, 1), int)
        self.assertIsInstance(export_units.native_dp_for_raw_unit_key(tables, 0, 1), int)
        self.assertIsInstance(export_units.native_mv_for_raw_unit_key(tables, 0x44), int)
        self.assertIsInstance(export_units.native_mv_for_raw_unit_key(tables, 0), int)


if __name__ == "__main__":
    unittest.main()
