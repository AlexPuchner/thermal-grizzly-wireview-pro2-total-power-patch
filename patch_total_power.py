from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SOURCE_SHA256 = (
    "38A2FDC2A74F1763378B060F4CB69C086F062BD8CBEC4D06E30E49D28FE11956"
)
EXPECTED_OUTPUT_SHA256 = (
    "C0DC403E34BBE63F3C7EEF73A44E060A697B69C8E6EAA16CBA60957E9268A354"
)


@dataclass(frozen=True)
class Patch:
    address: int
    expected: bytes
    replacement: bytes
    description: str


PATCHES = (
    Patch(
        address=0x0800C62E,
        expected=bytes.fromhex("98 6D"),
        replacement=bytes.fromhex("58 6D"),
        description=(
            "screenCurrentView: load TotalPower (+0x54) instead of "
            "TotalCurrent (+0x58)"
        ),
    ),
    Patch(
        address=0x08009FFE,
        expected=bytes.fromhex("E6 21"),
        replacement=bytes.fromhex("0A 21"),
        description="Current total widget: move X position from 230 to 10 pixels",
    ),
    Patch(
        address=0x0801FBF8,
        expected=bytes.fromhex("3E 00 00 00"),
        replacement=bytes.fromhex("94 01 00 00"),
        description=(
            "TouchGFX text offset: existing total-current text -> appended power text"
        ),
    ),
    Patch(
        address=0x0801FBFC,
        expected=bytes.fromhex("19 00 00 00"),
        replacement=bytes.fromhex("18 00 00 00"),
        description="TouchGFX text offset: hide 'Current Monitor (A)' using empty text",
    ),
)

APPENDED_PATCHES = (
    Patch(
        address=0x0801FF5C,
        expected=b"",
        replacement=bytes.fromhex(
            "54 00 6F 00 74 00 61 00 6C 00 20 00 50 00 6F 00 77 00 65 00 "
            "72 00 20 00 2D 00 20 00 02 00 20 00 57 00 00 00"
        ),
        description="TouchGFX text: 'Total Power - {value} W'",
    ),
)


def parse_record(line: str, line_number: int) -> tuple[int, int, bytearray]:
    text = line.strip()
    if not text.startswith(":"):
        raise ValueError(f"Line {line_number}: not an Intel HEX record")
    try:
        raw = bytes.fromhex(text[1:])
    except ValueError as exc:
        raise ValueError(f"Line {line_number}: invalid hexadecimal data") from exc
    if len(raw) < 5 or len(raw) != raw[0] + 5:
        raise ValueError(f"Line {line_number}: invalid record length")
    if sum(raw) & 0xFF:
        raise ValueError(f"Line {line_number}: checksum mismatch")
    address = (raw[1] << 8) | raw[2]
    record_type = raw[3]
    return address, record_type, bytearray(raw[4:-1])


def encode_record(address: int, record_type: int, data: bytearray) -> str:
    body = bytearray((len(data), address >> 8, address & 0xFF, record_type))
    body.extend(data)
    body.append((-sum(body)) & 0xFF)
    return ":" + body.hex().upper()


def patch_firmware(input_path: Path, output_path: Path) -> str:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output must be different files")

    source_bytes = input_path.read_bytes()
    source_digest = hashlib.sha256(source_bytes).hexdigest().upper()
    if source_digest != SUPPORTED_SOURCE_SHA256:
        raise ValueError(
            "Unsupported input firmware.\n"
            f"Expected SHA256: {SUPPORTED_SOURCE_SHA256}\n"
            f"Actual SHA256:   {source_digest}\n"
            "Use an untouched TG-WV-PRO2-FW.hex from WireView2 software 1.0.7."
        )

    line_ending = "\r\n" if b"\r\n" in source_bytes else "\n"
    has_trailing_line_ending = source_bytes.endswith(b"\n")
    source_lines = source_bytes.decode("ascii").splitlines()
    memory: dict[int, int] = {}
    linear_base = 0
    segment_base = 0
    use_linear = True
    eof_seen = False

    parsed: list[tuple[int, int, bytearray, int]] = []
    for line_number, line in enumerate(source_lines, 1):
        if eof_seen:
            raise ValueError(f"Line {line_number}: record found after EOF")
        address, record_type, data = parse_record(line, line_number)
        if record_type == 0x00:
            base = linear_base if use_linear else segment_base
            absolute = base + address
            for index, value in enumerate(data):
                memory[absolute + index] = value
        elif record_type == 0x01:
            if address != 0 or data:
                raise ValueError(f"Line {line_number}: invalid EOF record")
            eof_seen = True
        elif record_type == 0x02:
            if len(data) != 2:
                raise ValueError(f"Line {line_number}: invalid segment-address record")
            segment_base = int.from_bytes(data, "big") << 4
            use_linear = False
        elif record_type == 0x04:
            if len(data) != 2:
                raise ValueError(f"Line {line_number}: invalid linear-address record")
            linear_base = int.from_bytes(data, "big") << 16
            use_linear = True
        parsed.append((address, record_type, data, line_number))

    if not eof_seen:
        raise ValueError("Intel HEX file has no EOF record")

    for patch in PATCHES:
        actual = bytes(
            memory.get(patch.address + index, -1)
            for index in range(len(patch.expected))
        )
        if actual != patch.expected:
            raise ValueError(
                f"Unexpected bytes for '{patch.description}' at "
                f"0x{patch.address:08X}: expected {patch.expected.hex(' ')}, "
                f"found {actual.hex(' ')}"
            )
        for index, value in enumerate(patch.replacement):
            memory[patch.address + index] = value

    for patch in APPENDED_PATCHES:
        occupied = [
            patch.address + index
            for index in range(len(patch.replacement))
            if patch.address + index in memory
        ]
        if occupied:
            raise ValueError(
                f"Append location for '{patch.description}' is already occupied at "
                f"0x{occupied[0]:08X}"
            )
        for index, value in enumerate(patch.replacement):
            memory[patch.address + index] = value

    output_lines: list[str] = []
    linear_base = 0
    segment_base = 0
    use_linear = True
    changed_addresses: set[int] = set()
    for address, record_type, data, _line_number in parsed:
        if record_type == 0x01:
            for patch in APPENDED_PATCHES:
                patch_base = patch.address & 0xFFFF0000
                if not use_linear or linear_base != patch_base:
                    upper = patch_base >> 16
                    output_lines.append(
                        encode_record(0, 0x04, bytearray(upper.to_bytes(2, "big")))
                    )
                    linear_base = patch_base
                    use_linear = True
                for offset in range(0, len(patch.replacement), 16):
                    absolute = patch.address + offset
                    chunk = bytearray(patch.replacement[offset : offset + 16])
                    output_lines.append(
                        encode_record(absolute & 0xFFFF, 0x00, chunk)
                    )
                    changed_addresses.update(
                        range(absolute, absolute + len(chunk))
                    )
            output_lines.append(encode_record(address, record_type, data))
            continue
        if record_type == 0x00:
            base = linear_base if use_linear else segment_base
            absolute = base + address
            for index in range(len(data)):
                patched = memory[absolute + index]
                if data[index] != patched:
                    data[index] = patched
                    changed_addresses.add(absolute + index)
        elif record_type == 0x02:
            segment_base = int.from_bytes(data, "big") << 4
            use_linear = False
        elif record_type == 0x04:
            linear_base = int.from_bytes(data, "big") << 16
            use_linear = True
        output_lines.append(encode_record(address, record_type, data))

    expected_changed = {
        patch.address + index
        for patch in PATCHES
        for index, (before, after) in enumerate(
            zip(patch.expected, patch.replacement)
        )
        if before != after
    }
    expected_changed.update(
        patch.address + index
        for patch in APPENDED_PATCHES
        for index in range(len(patch.replacement))
    )
    if changed_addresses != expected_changed:
        raise ValueError(
            "Changed-address verification failed: "
            f"expected {sorted(expected_changed)}, got {sorted(changed_addresses)}"
        )

    output_text = line_ending.join(output_lines)
    if has_trailing_line_ending:
        output_text += line_ending
    output_bytes = output_text.encode("ascii")
    output_digest = hashlib.sha256(output_bytes).hexdigest().upper()
    if output_digest != EXPECTED_OUTPUT_SHA256:
        raise ValueError(
            "Generated output verification failed.\n"
            f"Expected SHA256: {EXPECTED_OUTPUT_SHA256}\n"
            f"Actual SHA256:   {output_digest}"
        )

    output_path.write_bytes(output_bytes)
    return output_digest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Patch the WireView Pro II Current page to show total power in watts."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("TG-WV-PRO2-FW.hex"),
        help="untouched official firmware (default: TG-WV-PRO2-FW.hex)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("TG-WV-PRO2-FW-total-power.hex"),
        help="patched output file (default: TG-WV-PRO2-FW-total-power.hex)",
    )
    args = parser.parse_args()

    digest = patch_firmware(args.input, args.output)
    print(f"Created: {args.output.resolve()}")
    print(f"SHA256:  {digest}")
    for patch in PATCHES + APPENDED_PATCHES:
        print(f"0x{patch.address:08X}: {patch.description}")


if __name__ == "__main__":
    main()
