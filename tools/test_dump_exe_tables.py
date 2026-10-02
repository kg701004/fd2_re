import unittest
from pathlib import Path

import dump_exe_tables
from disasm_le import object_bytes
from le_xref import parse_le

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"


class NativeItemEffectRowsTest(unittest.TestCase):
    def test_class_names_cover_native_text_indices_zero_through_twenty_eight(self):
        self.assertEqual(len(dump_exe_tables.CLASS_NAMES), 29)
        self.assertEqual(dump_exe_tables.CLASS_NAMES[26], "？？？")
        self.assertEqual(dump_exe_tables.CLASS_NAMES[27], "　　")
        self.assertEqual(dump_exe_tables.CLASS_NAMES[28], "？？？")

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

class NativeLinearTablesOnCanonicalExeTest(unittest.TestCase):
    """用真正的 canonical FD2.EXE 檢查由 linear 位址出發的表。

    2026-10-02:舊版本測試把合成資料放在工具自己寫死的 file_base(0x7A659)上,
    再從同一個位置讀回來——工具錯幾個 byte 測試都會過,所以整張移動成本表錯一個
    byte 一直沒被抓到。現在改成對照活記憶體傾印(DOSBox-X 0x1f3646,doc98
    續六十四)與 LE header 換算這兩個獨立來源。
    """

    @classmethod
    def setUpClass(cls):
        if not EXE.exists():
            raise unittest.SkipTest(f"找不到原版 EXE:{EXE}")
        cls.raw = EXE.read_bytes()
        cls.meta = parse_le(cls.raw)

    def test_native_movement_cost_rows_have_exact_29_by_20_boundary(self):
        rows = dump_exe_tables.dump_native_movement_cost_rows(self.raw)

        self.assertEqual(len(rows), 29)
        self.assertEqual(rows[0]["linear"], "0x61646")
        self.assertEqual(rows[0]["off"], "0x7a65a")
        self.assertEqual(rows[28]["linear"], hex(0x61646 + 28 * 20))
        # 活記憶體地面真相:錯一個 byte 時 row 7 會讀成 0101140102021401...
        self.assertEqual(
            bytes.fromhex(rows[7]["raw"]),
            bytes.fromhex("0114010202140101010101010101010101010101"),
        )
        self.assertEqual(
            bytes.fromhex(rows[19]["raw"]),
            bytes.fromhex("0101010101140101010101010101010101010101"),
        )
        table = object_bytes(self.raw, self.meta, 0x61646, 29 * 20)
        self.assertEqual(b"".join(bytes.fromhex(r["raw"]) for r in rows), table)

    def test_class_equip_types_match_native_rows_scanned_by_0x1c1c3(self):
        # 0x4e88e 回傳 linear 0x6188a + cls*7;0x1c1c3 掃該列 byte 0..5。
        rows = dump_exe_tables.dump_class_equip_types(self.raw)

        self.assertEqual(len(rows), 29)
        for cls, row in enumerate(rows):
            native = object_bytes(self.raw, self.meta, 0x6188A + cls * 7, 7)
            self.assertEqual(bytes(row["types"]), native[:6], cls)
            prev = object_bytes(self.raw, self.meta, 0x6188A + cls * 7 - 1, 1)
            self.assertEqual(row["raw"][0], prev[0], cls)

    def test_lin2file_matches_obj3_page_mapping(self):
        self.assertEqual(dump_exe_tables.lin2file(self.raw, 0x61646), 0x7A65A)
        self.assertEqual(dump_exe_tables.lin2file(self.raw, 0x602AD),
                         dump_exe_tables.ANCHORS["item"][0] + 1)
        with self.assertRaises(ValueError):
            dump_exe_tables.lin2file(self.raw, 0x0)


if __name__ == "__main__":
    unittest.main()
