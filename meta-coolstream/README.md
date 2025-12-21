# meta-coolstream

Coolstream-specific hardware layer for Tuxbox-OS. Mirrors the OE-Alliance
meta-brands style: machine descriptions, flash/layout settings and BSP bits
for Coolstream boxes. This layer keeps Coolstream specifics out of
`meta-tuxbox` and `meta-neutrino`.

## Scope
- MACHINE descriptions for Coolstream devices (HD2/uClibc generation first).
- Hooks for external uClibc toolchain (TCMODE `external-coolstream`).
- Flash/layout settings (NAND/NOR, image types) per box.
- BSP recipes (bootloader, kernel, drivers) or bbappends as needed.

## Usage
1. Add the layer to `bblayers.conf`:
   ```
   BBLAYERS += "${TOPDIR}/../meta-coolstream"
   ```
2. Select a Coolstream machine (example Tank):
   ```
   MACHINE = "coolstream-tank"
   MACHINEBUILD = "coolstream-tank"
   ```
3. If uClibc/external toolchain is required, set in `local.conf`:
   ```
   TCMODE = "external-coolstream"
   TCLIBC = "uclibc"
   ```
   (TCMODE provided by meta-tuxbox-toolchain; toolchain tarball must be
    available.)

## Status
- Skeleton layer with Tank machine description.
- Kernel/bootloader/driver recipes are not yet ported; migrate from
  ni-buildsystem when available.

## Compatibility
- Yocto/OE: Kirkstone.
- Keeps OE-Alliance upstream untouched; all Coolstream customisations live
  here or in the toolchain layer.
