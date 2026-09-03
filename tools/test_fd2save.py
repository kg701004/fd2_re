import struct
import unittest
from pathlib import Path

import fd2save

# Real FD2.SAV files are never committed to this repository (see the module
# docstring), but when this test runs on a machine that already has one from
# prior live-verification sessions, exercise the round-trip and the proven
# character-id field against real bytes instead of only synthetic data. Skip
# quietly everywhere else (e.g. CI, a fresh checkout).
_CANDIDATE_REAL_SAVES = [
    Path(r"C:\Users\kg701\Desktop\GAME\FD2\FD2.SAV"),
    Path(r"C:\Users\kg701\Desktop\GAME\FD2_ch21_test.SAV"),
    Path(r"C:\Users\kg701\Desktop\GAME\FD2_ch23_test.SAV"),
]

# Known-good persistent-slot-0 recruitment order for the above files, as
# cross-checked 2026-08-21 against docs/data/exe_tables/characters.json and
# the live DOSBox-X verification in doc58 "續十一" (2026-08-18): 索爾/悠妮/
# 亞雷斯/蓋亞/哈諾/希莉亞/鐵諾/瑪琳/貝克威/凱麗/洛娜/索菲亞/萊汀.
_KNOWN_SLOT0_CHAR_IDS = [0, 9, 4, 30, 1, 8, 2, 10, 13, 12, 5, 11, 6]


class FD2SaveTest(unittest.TestCase):
    def test_native_envelope_round_trip_and_checksum(self):
        plain = bytearray((i * 37 + 11) & 0xFF for i in range(fd2save.FILE_SIZE))
        stored = fd2save.encode(bytes(plain))
        self.assertNotEqual(stored, bytes(plain))
        decoded = fd2save.decode(stored)
        expected = bytearray(plain)
        struct.pack_into("<I", expected, fd2save.CHECKSUM_OFFSET, fd2save.checksum(expected))
        self.assertEqual(decoded, bytes(expected))

    def test_checksum_rejects_tamper(self):
        stored = bytearray(fd2save.encode(bytes(fd2save.FILE_SIZE)))
        stored[0x123] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            fd2save.decode(bytes(stored))

    def test_slot_bounds_are_exact_and_bounded(self):
        self.assertEqual(fd2save.slot_bounds(0), (0x312B, 0x3B53))
        self.assertEqual(fd2save.slot_bounds(3), (0x4FA3, 0x59CB))
        with self.assertRaises(ValueError):
            fd2save.slot_bounds(4)

    def test_summary_exposes_verified_empty_sentinel_only(self):
        plain = bytearray(fd2save.FILE_SIZE)
        start, _ = fd2save.slot_bounds(0)
        plain[start + fd2save.ROSTER_SIZE] = 0xFF
        report = fd2save.summarize(bytes(plain))
        self.assertIn("slot=0", report)
        self.assertIn("chapter=0xff empty=True", report)

    def test_summary_uses_ida_verified_current_runtime_count_offsets(self):
        plain = bytearray(fd2save.FILE_SIZE)
        header = fd2save.CURRENT_RUNTIME_OFFSET
        plain[header + 0] = 3
        plain[header + 1] = 12
        plain[header + 2] = 7
        plain[header + 9] = 4
        report = fd2save.summarize(bytes(plain))
        self.assertIn("turn_counter=0x03", report)
        self.assertIn("runtime_count=0x0c", report)
        self.assertIn("chapter=0x07", report)
        self.assertIn("persistent_count=0x04", report)
        self.assertNotIn("persistent_count=0x03", report)

    def test_roster_character_ids_reads_proven_offset(self):
        plain = bytearray(fd2save.FILE_SIZE)
        start, _ = fd2save.slot_bounds(0)
        ids = [0, 9, 4, 30, 1]
        for i, char_id in enumerate(ids):
            plain[start + i * fd2save.UNIT_SIZE + fd2save.UNIT_CHARACTER_ID_OFFSET] = char_id
        self.assertEqual(
            fd2save.roster_character_ids(bytes(plain), 0, count=len(ids)), ids
        )

    def test_roster_character_ids_defaults_to_full_roster(self):
        plain = bytearray(fd2save.FILE_SIZE)
        self.assertEqual(
            len(fd2save.roster_character_ids(bytes(plain), 0)), fd2save.ROSTER_UNITS
        )

    def test_roster_inventory_reads_proven_flag_and_item_offsets(self):
        plain = bytearray(fd2save.FILE_SIZE)
        start, _ = fd2save.slot_bounds(0)
        record = start + 2 * fd2save.UNIT_SIZE  # unit index 2
        # slot0/1: always-occupied starting items (flag 0x40 per FUN_000112a5)
        plain[record + fd2save.UNIT_INVENTORY_FLAG_OFFSET + 0] = 0x40
        plain[record + fd2save.UNIT_INVENTORY_ITEM_OFFSET + 0] = 0x1F
        plain[record + fd2save.UNIT_INVENTORY_FLAG_OFFSET + 2] = 0x40
        plain[record + fd2save.UNIT_INVENTORY_ITEM_OFFSET + 2] = 0xA3
        # slot2: occupied optional item (flag 0x00)
        plain[record + fd2save.UNIT_INVENTORY_FLAG_OFFSET + 4] = 0x00
        plain[record + fd2save.UNIT_INVENTORY_ITEM_OFFSET + 4] = 0x5B
        # slot3..7: empty (flag 0x80); item byte left as native stale garbage
        for i in range(3, 8):
            plain[record + fd2save.UNIT_INVENTORY_FLAG_OFFSET + 2 * i] = 0x80
            plain[record + fd2save.UNIT_INVENTORY_ITEM_OFFSET + 2 * i] = 0xC9
        cells = fd2save.roster_inventory(bytes(plain), 0, 2)
        self.assertEqual(len(cells), fd2save.UNIT_INVENTORY_SLOT_COUNT)
        self.assertEqual(cells[0], (0x40, 0x1F))
        self.assertEqual(cells[1], (0x40, 0xA3))
        self.assertEqual(cells[2], (0x00, 0x5B))
        self.assertEqual(cells[3], (0x80, 0xC9))
        # only the non-empty (flag bit 0x80 clear) cells surface as "items"
        self.assertEqual(
            fd2save.roster_inventory_items(bytes(plain), 0, 2), [0x1F, 0xA3, 0x5B]
        )

    def test_build_join_record_matches_known_go_projection_for_char12(self):
        """Cross-check against TestNativeJoinConstructorMaterializesKeliFromRawTables
        (remake/internal/campaign/native_join_constructor_test.go): character id
        12 ("凱麗") is known-answer Lv10/class8/MV5/MaxHP151/MaxMP0/BaseAP80/
        BaseDP69/DX10. This Python port must reproduce those exact record bytes.
        """
        # 2026-09-03:這張表已用現存的新版 EXE 重生並進版到 docs/data/,
        # 這兩條測試自此恢復實際執行(先前因 remake/ 移除而 skip)。
        # 保留存在性檢查只是為了在檔案被誤刪時給出可讀訊息,不是永久缺口。
        self.assertTrue(fd2save.JOIN_CONSTRUCTOR_TABLE_PATH.exists(),
                        "docs/data/native_join_constructor.json 應已進版")
        table = fd2save.load_join_constructor_table()
        record = fd2save.build_join_record(12, table)
        self.assertEqual(len(record), fd2save.UNIT_SIZE)
        self.assertEqual(record[0x07], 12)
        self.assertEqual(record[0x08], 12)
        self.assertEqual(record[0x21], 10)  # level
        self.assertEqual(record[0x20], 8)  # class
        self.assertEqual(record[0x3B], 5)  # MV
        self.assertEqual(struct.unpack_from("<H", record, 0x40)[0], 151)  # HP cur
        self.assertEqual(struct.unpack_from("<H", record, 0x42)[0], 151)  # HP max
        self.assertEqual(struct.unpack_from("<H", record, 0x44)[0], 0)  # MP cur
        self.assertEqual(struct.unpack_from("<H", record, 0x46)[0], 0)  # MP max
        self.assertEqual(struct.unpack_from("<H", record, 0x37)[0], 80)  # base AP
        self.assertEqual(struct.unpack_from("<H", record, 0x39)[0], 69)  # base DP
        self.assertEqual(struct.unpack_from("<H", record, 0x3E)[0], 10)  # DX
        # Known inventory projection from the same Go test: flags
        # [0x40,0x40,0x80,0x80,0x80,0x80,0x80,0x80], items [0x3e,0xac,...].
        flags_items = [
            (record[0x0A + 2 * i], record[0x0B + 2 * i]) for i in range(8)
        ]
        self.assertEqual(
            [f for f, _ in flags_items],
            [0x40, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80],
        )
        self.assertEqual(flags_items[0][1], 0x3E)
        self.assertEqual(flags_items[1][1], 0xAC)

    def test_append_roster_members_extends_count_and_rejects_duplicates(self):
        plain = bytearray(fd2save.FILE_SIZE)
        start, _ = fd2save.slot_bounds(0)
        meta_start = start + fd2save.ROSTER_SIZE
        plain[meta_start] = 0x1A  # chapter
        plain[meta_start + 1] = 3  # roster_count
        for i, char_id in enumerate([0, 9, 4]):
            plain[start + i * fd2save.UNIT_SIZE + fd2save.UNIT_CHARACTER_ID_OFFSET] = char_id
        # 2026-09-03:這張表已用現存的新版 EXE 重生並進版到 docs/data/,
        # 這兩條測試自此恢復實際執行(先前因 remake/ 移除而 skip)。
        # 保留存在性檢查只是為了在檔案被誤刪時給出可讀訊息,不是永久缺口。
        self.assertTrue(fd2save.JOIN_CONSTRUCTOR_TABLE_PATH.exists(),
                        "docs/data/native_join_constructor.json 應已進版")
        table = fd2save.load_join_constructor_table()
        mutated = fd2save.append_roster_members(bytes(plain), 0, [30, 1, 8], table)
        self.assertEqual(mutated[meta_start + 1], 6)
        self.assertEqual(
            fd2save.roster_character_ids(mutated, 0, count=6), [0, 9, 4, 30, 1, 8]
        )
        # original 3 records must be byte-identical (untouched)
        self.assertEqual(
            mutated[start:start + 3 * fd2save.UNIT_SIZE],
            bytes(plain)[start:start + 3 * fd2save.UNIT_SIZE],
        )
        # duplicate id (already present) must be rejected
        with self.assertRaisesRegex(ValueError, "already present"):
            fd2save.append_roster_members(mutated, 0, [9], table)
        # overflowing the 32-record buffer must be rejected
        with self.assertRaises(ValueError):
            fd2save.append_roster_members(bytes(plain), 0, list(range(31)), table)

    def test_set_slot_chapter_only_touches_that_slot_metadata_byte(self):
        plain = bytearray(fd2save.FILE_SIZE)
        start0, _ = fd2save.slot_bounds(0)
        start1, _ = fd2save.slot_bounds(1)
        plain[start0 + fd2save.ROSTER_SIZE] = 0x0A
        plain[start1 + fd2save.ROSTER_SIZE] = 0x05
        mutated = fd2save.set_slot_chapter(bytes(plain), 0, 0x1B)
        self.assertEqual(mutated[start0 + fd2save.ROSTER_SIZE], 0x1B)
        self.assertEqual(mutated[start1 + fd2save.ROSTER_SIZE], 0x05)


class FD2SaveRealFileTest(unittest.TestCase):
    """Optional live-data checks: only run when a real FD2.SAV is present on
    disk (never committed here). These are the tests that actually answer
    "can this module's field offsets be trusted", not just "is the codec
    self-consistent" — see doc58 "續三十二" 2026-08-21 follow-up.
    """

    def _first_available_save(self):
        for path in _CANDIDATE_REAL_SAVES:
            if path.is_file():
                return path
        return None

    def test_real_save_round_trips_byte_for_byte(self):
        path = self._first_available_save()
        if path is None:
            self.skipTest("no real FD2.SAV found on this machine")
        stored = path.read_bytes()
        plain = fd2save.decode(stored)
        reencoded = fd2save.encode(plain)
        self.assertEqual(reencoded, stored)
        # decoding the re-encoded bytes must reproduce the same plaintext
        self.assertEqual(fd2save.decode(reencoded), plain)

    def test_real_save_slot0_character_ids_match_known_roster(self):
        path = self._first_available_save()
        if path is None:
            self.skipTest("no real FD2.SAV found on this machine")
        plain = fd2save.decode(path.read_bytes())
        meta_start = fd2save.SLOT_OFFSET + fd2save.ROSTER_SIZE
        roster_count = plain[meta_start + 1]
        char_ids = fd2save.roster_character_ids(plain, 0, count=roster_count)
        # Every file we have locally starts from the same base save, so the
        # populated prefix always matches the same known recruitment order.
        self.assertEqual(char_ids, _KNOWN_SLOT0_CHAR_IDS[:roster_count])

    def test_real_saves_inventory_flag_bytes_are_within_known_value_set(self):
        """Sanity check (doc58 "續三十四", 2026-08-21), not a known-value
        comparison: every decoded flag byte across every populated
        unit/slot in every real save on this machine must be one of the
        exact three values FUN_000112a5 ever writes to that offset
        (0x00/0x40/0x80). Any other byte would mean the offset is wrong.
        """
        checked_any_file = False
        for path in _CANDIDATE_REAL_SAVES:
            if not path.is_file():
                continue
            checked_any_file = True
            plain = fd2save.decode(path.read_bytes())
            for slot in range(fd2save.SLOT_COUNT):
                start, _ = fd2save.slot_bounds(slot)
                meta = plain[start + fd2save.ROSTER_SIZE : start + fd2save.SLOT_SIZE]
                chapter = meta[0]
                roster_count = meta[1]
                if chapter == 0xFF or not (0 < roster_count <= fd2save.ROSTER_UNITS):
                    continue
                for unit in range(roster_count):
                    for flag, _item in fd2save.roster_inventory(plain, slot, unit):
                        self.assertIn(
                            flag,
                            (0x00, 0x40, 0x80),
                            f"{path.name} slot={slot} unit={unit}: "
                            f"unexpected inventory flag byte {flag:#04x}",
                        )
        if not checked_any_file:
            self.skipTest("no real FD2.SAV found on this machine")


if __name__ == "__main__":
    unittest.main()
