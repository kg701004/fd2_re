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


if __name__ == "__main__":
    unittest.main()
