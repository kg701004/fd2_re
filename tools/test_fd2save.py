import struct
import unittest

import fd2save


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


if __name__ == "__main__":
    unittest.main()
