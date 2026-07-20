import tempfile
import unittest
from pathlib import Path

import patch_total_power as patcher


class IntelHexTests(unittest.TestCase):
    def test_encode_and_parse_round_trip(self) -> None:
        data = bytearray.fromhex("58 6D 00 FF")
        encoded = patcher.encode_record(0xC62E, 0x00, data)

        address, record_type, decoded = patcher.parse_record(encoded, 1)

        self.assertEqual(address, 0xC62E)
        self.assertEqual(record_type, 0x00)
        self.assertEqual(decoded, data)
        self.assertEqual(sum(bytes.fromhex(encoded[1:])) & 0xFF, 0)

    def test_invalid_checksum_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            patcher.parse_record(":0400000001020304F3", 7)


class PatchDefinitionTests(unittest.TestCase):
    def test_replacements_keep_original_instruction_sizes(self) -> None:
        for item in patcher.PATCHES:
            self.assertEqual(len(item.expected), len(item.replacement))

    def test_appended_touchgfx_text(self) -> None:
        text = patcher.APPENDED_PATCHES[0].replacement.decode("utf-16le")
        self.assertEqual(text, "Total Power - \x02 W\x00")

    def test_input_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            firmware = Path(temporary_directory) / "firmware.hex"
            with self.assertRaisesRegex(ValueError, "different files"):
                patcher.patch_firmware(firmware, firmware)

    def test_unknown_firmware_is_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unknown.hex"
            output = Path(temporary_directory) / "output.hex"
            source.write_text(":00000001FF\n", encoding="ascii")

            with self.assertRaisesRegex(ValueError, "Unsupported input firmware"):
                patcher.patch_firmware(source, output)

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
