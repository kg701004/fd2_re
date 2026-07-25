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


if __name__ == "__main__":
    unittest.main()
