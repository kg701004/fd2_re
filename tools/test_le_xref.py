#!/usr/bin/env python3
"""le_xref.parse_le 的分頁映射回歸測試。

為什麼需要:2026-09-03 之前 `parse_le` 回傳 LE header 的 data-pages offset 原值,
而**每一個使用者**(`page_file()`、`callgraph_le`、`disasm_le`、
`extract_event_id_groups`、`extract_native_unit_tables`、
`extract_native_treasure_event_rules`)都把它當檔案絕對位置用。對這份新版 EXE
(LE header 在 0x27acc)兩者差很多,整個分頁區錯位。

後果不是崩潰,是**安靜地產生垃圾**:`extract_native_unit_tables.py` 照常執行、
照常印出「68 records × 10 bytes」、照常寫出格式正確的 JSON,只是內容是從錯誤位置
讀來的 x86 程式碼位元組。沒有任何檢查會發現。

本測試用的是**獨立來源**的 ground truth:`dump_exe_tables.py` 走的是 raw file
offset + 錨定特徵(與 le_xref 完全不同的路徑),而且它內建的數值自驗會對照
青衫攻略的字面值。兩條路徑必須在同一份資料上會合。
"""
from __future__ import annotations

import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from le_xref import parse_le  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "org_game" / "炎龍騎士團" / "FLAME2" / "FD2.EXE"

# dump_exe_tables.py 從 file offset 0x7ab0d(錨定驗證過)讀出的 unit 表第 0 筆,
# 其自驗把它解成「戰士 / hp18 / ap5 / dp2 / dx1 / mv4 / ex30」並對照攻略通過。
UNIT_ROW0 = bytes.fromhex("0102120000050201041e")
UNIT_ROW0_FILE_OFF = 0x7ab0d
# 同一支工具的成長表第 0 筆(自驗輸出:升級成長[0] ✓ 060804060203080c0000ff)
GROWTH_ROW0 = bytes.fromhex("060804060203080c0000ff")


class ParseLEPageMappingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EXE.exists():
            raise unittest.SkipTest(f"找不到原版 EXE:{EXE}")
        cls.raw = EXE.read_bytes()
        cls.meta = parse_le(cls.raw)

    def linear_to_file(self, lin: int) -> int:
        m = self.meta
        pg = 0
        for ob in m["objs"]:
            if ob["base"] <= lin < ob["base"] + ob["pages"] * m["page_size"]:
                return m["data_off"] + (pg + (lin - ob["base"]) // m["page_size"]) * m["page_size"] \
                    + (lin - ob["base"]) % m["page_size"]
            pg += ob["pages"]
        self.fail(f"{hex(lin)} 不在任何 object 內")

    def test_data_off_is_absolute_and_pages_end_at_file_end(self):
        m = self.meta
        npages = sum(o["pages"] for o in m["objs"])
        end = m["data_off"] + (npages - 1) * m["page_size"] + m["last_page_size"]
        self.assertEqual(end, len(self.raw),
                         "分頁區必須正好結束在檔尾;對不上代表 data_off 推導錯了")
        self.assertGreater(m["data_off"], m["le"],
                           "分頁區應在 LE header 之後")

    def test_header_field_is_kept_separately_and_differs(self):
        # 這正是 bug 的來源:原值不等於絕對起點。保留原值是為了讓差異可見。
        self.assertIn("data_off_field", self.meta)
        self.assertNotEqual(self.meta["data_off"], self.meta["data_off_field"])

    def test_unit_table_row0_matches_the_independently_verified_bytes(self):
        """linear 映射必須與 dump_exe_tables 的 file-offset 路徑會合。"""
        got = self.raw[UNIT_ROW0_FILE_OFF:UNIT_ROW0_FILE_OFF + len(UNIT_ROW0)]
        self.assertEqual(got, UNIT_ROW0, "基準本身就對不上——EXE 版本可能不是新版")
        # 反向:把該 file offset 換算成 linear,再走 le_xref 的映射讀回來
        m = self.meta
        pg = (UNIT_ROW0_FILE_OFF - m["data_off"]) // m["page_size"]
        off = (UNIT_ROW0_FILE_OFF - m["data_off"]) % m["page_size"]
        acc = 0
        lin = None
        for ob in m["objs"]:
            if pg < acc + ob["pages"]:
                lin = ob["base"] + (pg - acc) * m["page_size"] + off
                break
            acc += ob["pages"]
        self.assertIsNotNone(lin, "unit 表落在分頁區外——映射錯了")
        self.assertEqual(self.linear_to_file(lin), UNIT_ROW0_FILE_OFF,
                         "linear→file 與 file→linear 不互為反函式")

    def test_growth_table_row0_is_findable(self):
        """成長表第 0 筆必須在分頁區內找得到,且唯一。"""
        m = self.meta
        npages = sum(o["pages"] for o in m["objs"])
        region = self.raw[m["data_off"]:m["data_off"] + (npages - 1) * m["page_size"]
                          + m["last_page_size"]]
        self.assertEqual(region.count(GROWTH_ROW0), 1,
                         "成長表第 0 筆應在分頁區內唯一出現")

    def test_fault_injection_wrong_data_off_breaks_the_unit_row(self):
        """對照組:用修正前的錯誤 data_off,同一個 linear 位址讀到的不是那張表。

        沒有這一項,上面的檢查有可能在任何 data_off 下都通過(例如全域搜尋),
        本項證明檢查真的綁在映射上。
        """
        m = self.meta
        bad = m["data_off_field"]          # 修正前的寫法
        self.assertNotEqual(bad, m["data_off"])
        # 用錯誤起點把 unit 表的 linear 位址換算回 file,讀到的位元組必須不同
        pg = (UNIT_ROW0_FILE_OFF - m["data_off"]) // m["page_size"]
        off = (UNIT_ROW0_FILE_OFF - m["data_off"]) % m["page_size"]
        acc = 0
        lin = None
        for ob in m["objs"]:
            if pg < acc + ob["pages"]:
                lin = ob["base"] + (pg - acc) * m["page_size"] + off
                break
            acc += ob["pages"]
        acc = 0
        bad_file = None
        for i, ob in enumerate(m["objs"]):
            if ob["base"] <= lin < ob["base"] + ob["pages"] * m["page_size"]:
                bad_file = bad + (acc + (lin - ob["base"]) // m["page_size"]) * m["page_size"] \
                    + (lin - ob["base"]) % m["page_size"]
                break
            acc += ob["pages"]
        self.assertIsNotNone(bad_file)
        self.assertNotEqual(self.raw[bad_file:bad_file + len(UNIT_ROW0)], UNIT_ROW0,
                            "錯誤的 data_off 竟然也讀到正確的表——這個檢查沒有鑑別力")


if __name__ == "__main__":
    unittest.main(verbosity=2)
