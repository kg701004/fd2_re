import json
import os
import struct
import tempfile
import unittest

import sync_native_map_renderer_inputs as sync


class SyncNativeMapInputsTest(unittest.TestCase):
    def test_expected_inputs_reads_both_composition_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            field_dir = os.path.join(root, "FDFIELD")
            shape_dir = os.path.join(root, "FDSHAP")
            os.makedirs(field_dir)
            os.makedirs(shape_dir)
            for index in range(3):
                path = os.path.join(field_dir, f"FDFIELD_{index:03d}.bin")
                with open(path, "wb") as output:
                    if index == 0:
                        output.write(struct.pack(
                            "<HHHHHH",
                            2, 1,
                            0, 0xA540,
                            1, 0x7F80,
                        ))
                    else:
                        output.write(struct.pack("<HH", 0, 0))
            for index in range(2):
                path = os.path.join(shape_dir, f"FDSHAP_{index:03d}.bin")
                with open(path, "wb") as output:
                    output.write(
                        bytes([1, 2, 3, 4, 5, 6, 7, 8])
                        if index == 1 else bytes([0, 0, 0, 0])
                    )

            flags, modes, control = sync.expected_inputs(
                root,
                0,
                {"w": 2, "h": 1, "tiles": [0, 1]},
            )

        self.assertEqual(flags, [0x40, 0x80])
        self.assertEqual(modes, [0xA5, 0x7F])
        self.assertEqual(control, [1, 2, 3, 4, 5, 6, 7, 8])

    def test_expected_inputs_rejects_dimension_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            field_dir = os.path.join(root, "FDFIELD")
            shape_dir = os.path.join(root, "FDSHAP")
            os.makedirs(field_dir)
            os.makedirs(shape_dir)
            for index in range(3):
                with open(
                    os.path.join(field_dir, f"FDFIELD_{index:03d}.bin"),
                    "wb",
                ) as output:
                    output.write(struct.pack("<HH", 1, 1) + bytes(4))
            for index in range(2):
                with open(
                    os.path.join(shape_dir, f"FDSHAP_{index:03d}.bin"),
                    "wb",
                ) as output:
                    output.write(bytes(4))

            with self.assertRaisesRegex(
                ValueError, "editable/source dimensions differ",
            ):
                sync.expected_inputs(
                    root,
                    0,
                    {"w": 2, "h": 1, "tiles": [0, 0]},
                )

    def test_sync_map_migrates_the_overbroad_target_flag_name(self):
        with tempfile.TemporaryDirectory() as root:
            field_dir = os.path.join(root, "FDFIELD")
            shape_dir = os.path.join(root, "FDSHAP")
            os.makedirs(field_dir)
            os.makedirs(shape_dir)
            for index in range(3):
                with open(
                    os.path.join(field_dir, f"FDFIELD_{index:03d}.bin"),
                    "wb",
                ) as output:
                    output.write(
                        struct.pack("<HHHH", 1, 1, 0, 0xA540)
                        if index == 0 else struct.pack("<HH", 0, 0)
                    )
            for index in range(2):
                with open(
                    os.path.join(shape_dir, f"FDSHAP_{index:03d}.bin"),
                    "wb",
                ) as output:
                    output.write(bytes([1, 2, 3, 4]))
            map_path = os.path.join(root, "map.json")
            with open(map_path, "w", encoding="utf-8") as output:
                json.dump(
                    {
                        "w": 1,
                        "h": 1,
                        "tiles": [0],
                        "native_target_flags": [0x40],
                    },
                    output,
                )

            self.assertTrue(sync.sync_map(map_path, 0, root, True))
            with open(map_path, encoding="utf-8") as source:
                migrated = json.load(source)

        self.assertNotIn("native_target_flags", migrated)
        self.assertEqual(
            migrated["native_composition_event_bytes"],
            [0x40],
        )
        self.assertEqual(migrated["native_tile_blit_modes"], [0xA5])
        self.assertEqual(
            migrated["native_terrain_control"], [1, 2, 3, 4],
        )


if __name__ == "__main__":
    unittest.main()
