# WireView Pro II Total Power Patch

An unofficial binary patch for the WireView Pro II firmware bundled with
WireView2 software 1.0.7. It changes page 3 (`Current`) so that the header shows
the measured total power instead of total current.

```text
Total Power - 420 W
```

The six current bars remain unchanged. The original `Current Monitor (A)` title
is hidden and the total-power text uses the smaller built-in font so that it
fits on the display.

## Supported firmware

Only the exact, untouched firmware listed below is accepted:

```text
Input file:   TG-WV-PRO2-FW.hex
WireView2:    1.0.7
Firmware:     v05 / 20260706_1047
Input SHA256: 38A2FDC2A74F1763378B060F4CB69C086F062BD8CBEC4D06E30E49D28FE11956
Output SHA256: C0DC403E34BBE63F3C7EEF73A44E060A697B69C8E6EAA16CBA60957E9268A354
```

The patcher checks both hashes and validates every Intel HEX checksum. It
refuses already modified firmware and unknown versions.

## Requirements

- Python 3.10 or newer
- A legally obtained copy of the official WireView2 Pro software 1.0.7
- The untouched `TG-WV-PRO2-FW.hex` from that software package

No Python packages are required.

## Create the patched firmware

Keep an untouched backup of the official file, then run:

```powershell
python patch_total_power.py `
  TG-WV-PRO2-FW-official.hex `
  TG-WV-PRO2-FW-total-power.hex
```

Successful output ends with:

```text
SHA256:  C0DC403E34BBE63F3C7EEF73A44E060A697B69C8E6EAA16CBA60957E9268A354
```

The generated `.hex` file is ignored by Git and must not be committed.

## Install with WireView2

1. Close `WireView2.exe`.
2. Back up its untouched `TG-WV-PRO2-FW.hex` outside the application folder.
3. Copy the generated file into the WireView2 folder.
4. Rename the generated file to exactly `TG-WV-PRO2-FW.hex`; the updater uses
   that fixed filename.
5. Start WireView2 and perform the normal firmware update.
6. Do not disconnect USB or power while the update is running.

The patch has been generated reproducibly and successfully tested on real
hardware. Modified firmware is nevertheless used at your own risk. A failed
update may require recovery through the STM32 bootloader, and firmware updates
may reset device settings.

## What the patch changes

- Reads `TotalPower` instead of `TotalCurrent` on the Current page.
- Moves the total-value widget from X=230 to X=10.
- Hides the static `Current Monitor (A)` title.
- Adds `Total Power - {value} W` as a TouchGFX UTF-16 string.
- Preserves the six existing current values and bars.

See [docs/firmware-analysis.md](docs/firmware-analysis.md) for addresses,
opcodes, text offsets, and Intel HEX details.

## Repository policy

This repository intentionally contains no vendor firmware, executables,
drivers, decompiled source, or extracted resources. It contains only original
patching tools and independently written technical documentation. Users supply
the official input file themselves.

See [THIRD_PARTY.md](THIRD_PARTY.md) for details.

## License

The original scripts and documentation in this repository are available under
the [MIT License](LICENSE). This license does not apply to vendor software or
firmware supplied by the user.

This is an unofficial project and is not affiliated with or endorsed by
Thermal Grizzly.
