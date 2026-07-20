# Firmware analysis notes

These notes describe the observations needed to reproduce the total-power
patch. They are independently written and do not contain decompiled vendor
source code or firmware data.

## Firmware layout

The supported Intel HEX image maps the STM32 application at `0x08000000`.

```text
Official image end: 0x0801FF5B
Patched image end:  0x0801FF7F
Linker-region end:  0x0801FFFF
Space after patch:  128 bytes
```

The local firmware contains five TouchGFX views:

1. `screenMainView`
2. `screenSimpleView`
3. `screenCurrentView`
4. `screenTempView`
5. `screenStatusView`

Relevant `screenCurrentView` locations:

```text
Constructor:   0x0800C410
Widget update: 0x0800C424
View setup:    0x0800C668
VTable:        0x0801EE40
```

## Sensor model

The sensor model contains six entries with voltage, current, and power data.
Current values are located at the following model offsets:

```text
0x10, 0x1C, 0x28, 0x34, 0x40, 0x4C
```

The corresponding power values are four bytes later:

```text
0x14, 0x20, 0x2C, 0x38, 0x44, 0x50
```

The totals used by the Current page are:

```text
TotalPower:   +0x54
TotalCurrent: +0x58
```

Both totals use a compatible thousands-based scale, so the existing numeric
formatting can be reused for watts without adding new arithmetic code.

## Binary changes

| Address | Original | Patched | Purpose |
| --- | --- | --- | --- |
| `0x0800C62E` | `98 6D` | `58 6D` | Load `TotalPower` instead of `TotalCurrent` |
| `0x08009FFE` | `E6 21` | `0A 21` | Move the total widget from X=230 to X=10 |
| `0x0801FBF8` | `3E 00 00 00` | `94 01 00 00` | Point typed-text ID 37 to the appended string |
| `0x0801FBFC` | `19 00 00 00` | `18 00 00 00` | Replace the Current-page title with empty text |

The new UTF-16LE text is appended at `0x0801FF5C`:

```text
Total Power - <wildcard> W\0
```

TouchGFX represents the numeric wildcard with code point `0x0002`. The text
occupies 36 bytes. Typed-text ID 37 retains typography 2, the smaller built-in
font used by the original total-current field.

## Intel HEX checksums

Each Intel HEX record contains:

```text
byte count + address + record type + data + checksum
```

The checksum is the two's complement of the least-significant byte of the sum
of every preceding byte in that record:

```text
checksum = (-sum(record_without_checksum)) & 0xFF
```

Consequently, the sum of all decoded bytes in a valid record is zero modulo
256. The patcher validates all input records and regenerates the checksum for
every output record.

## Safety properties of the patcher

Before creating output, `patch_total_power.py` verifies:

- the complete SHA-256 digest of the source file;
- all Intel HEX record checksums and the EOF record;
- the original bytes at every patched address;
- that the appended range is unused;
- the exact set of changed addresses;
- the complete SHA-256 digest of the generated file.

The input and output paths must be different, preventing accidental in-place
replacement of the only firmware copy.
