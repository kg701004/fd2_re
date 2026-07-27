import unittest

import dump_exe_tables


class NativeItemEffectRowsTest(unittest.TestCase):
    def test_runtime_view_is_shifted_one_byte_from_normalized_rows(self):
        base = dump_exe_tables.ANCHORS["item"][0]
        stride = 0x17
        data = bytearray(base + stride * 2 + 1)
        normalized_row0 = bytes(range(0x10, 0x10 + stride))
        normalized_row1 = bytes(range(0x40, 0x40 + stride))
        data[base:base + stride] = normalized_row0
        data[base + stride:base + stride * 2] = normalized_row1
        data[base + stride * 2] = 0x7E

        rows = dump_exe_tables.dump_native_item_effect_rows(data, count=2)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["off"], hex(base + 1))
        self.assertEqual(rows[0]["linear"], "0x602ad")
        self.assertEqual(
            bytes.fromhex(rows[0]["raw"]),
            normalized_row0[1:] + normalized_row1[:1],
        )
        self.assertEqual(
            bytes.fromhex(rows[1]["raw"]),
            normalized_row1[1:] + b"\x7e",
        )

    def test_incomplete_runtime_row_is_not_exported(self):
        base = dump_exe_tables.ANCHORS["item"][0]
        data = bytearray(base + 0x17)

        self.assertEqual(
            dump_exe_tables.dump_native_item_effect_rows(data, count=1),
            [],
        )


if __name__ == "__main__":
    unittest.main()
