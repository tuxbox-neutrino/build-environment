# Hardware Integration Guide (Neutrino + libstb-hal)

This document explains how hardware support is wired up and why not every
OE-Alliance machine is ready for Neutrino out of the box.

## Contents

- [Reality Check](#reality-check)
- [Where Hardware Support Lives](#where-hardware-support-lives)
- [libstb-hal Selection and Boxmodel Mapping](#libstb-hal-selection-and-boxmodel-mapping)
- [Workflow: Add a New Machine](#workflow-add-a-new-machine)
- [Verification Checklist](#verification-checklist)
- [Contributing Upstream](#contributing-upstream)

## Reality Check

- OE-Alliance provides 300+ machine definitions in `meta-brands`.
- The build system can parse/build many of them, but we only test a subset.
- Neutrino requires `libstb-hal` support. If a machine is not in the supported
  `boxmodel` list, builds or runtime behavior will break.
- Adding support is possible and welcome, but it is real bring-up work.

## Where Hardware Support Lives

- **Machine definitions**:
  `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`
- **Kernel/DTB/bootloader**:
  `oe-alliance/meta-brands/meta-<brand>/recipes-*`
- **Distro and images**:
  `meta-tuxbox` (image/packagegroups, distro config)
- **Neutrino and hardware abstraction**:
  `meta-neutrino` (Neutrino, `libstb-hal`)

## libstb-hal Selection and Boxmodel Mapping

`meta-tuxbox/conf/distro/tuxbox.conf` sets `FLAVOUR` (default: `tuxbox`). The
`libstb-hal` recipe includes `${FLAVOUR}.inc`, which selects the upstream repo:

- `tuxbox.inc` -> `tuxbox-neutrino/library-stb-hal`
- `ni.inc` -> `neutrino-images/ni-libstb-hal`
- `tango.inc` -> `TangoCash/libstb-hal-tangos`

The build passes:

- `--with-boxtype=${TARGET_ARCH}box`
- `--with-boxmodel=${MACHINE}`

Neutrino itself uses the same flags (see
`meta-neutrino/recipes-neutrino/neutrino/*.inc`). Ensure both recipes agree. If
your machine naming differs, override `EXTRA_OECONF` via a bbappend.

Valid boxtype values are `generic`, `armbox`, `mipsbox`. The `boxmodel` list is
defined in `library-stb-hal/acinclude.m4` (and similar in the other flavours).

Current boxmodels (library-stb-hal):

- generic: `generic`, `raspi`
- armbox: `hd60`, `hd61`, `multibox`, `multiboxse`, `hd51`, `bre2ze4k`, `h7`,
  `e4hdultra`, `protek4k`, `osmini4k`, `osmio4k`, `osmio4kplus`, `vusolo4k`,
  `vuduo4k`, `vuduo4kse`, `vuultimo4k`, `vuuno4k`, `vuuno4kse`, `vuzero4k`
- mipsbox: `vuduo`, `vuduo2`, `gb800se`, `osnino`, `osninoplus`, `osninopro`

If your machine name is not in this list, `configure` will fail and Neutrino
cannot run. You must add the boxmodel and hardware caps.

## Workflow: Add a New Machine

1) **Ensure OE-A machine support exists (or add it).**
   - Add `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`.
   - Set key values: `SOC_FAMILY`, `TUNE_FEATURES`, `KERNEL_IMAGETYPE`,
     `KERNEL_DEVICETREE`, `IMAGE_FSTYPES`, `SERIAL_CONSOLE`, `MACHINE_FEATURES`.
   - Set providers as needed:
     `PREFERRED_PROVIDER_virtual/kernel`,
     `PREFERRED_PROVIDER_virtual/bootloader`.
   - Add or update `linux-<brand>_<ver>.bb` and defconfig/DTB in the same layer.

2) **Verify kernel/driver bring-up.**
   - DVB nodes exist: `/dev/dvb/adapter0/...`
   - STB info exists: `/proc/stb/info/*`
   - Frontpanel/remote drivers load at boot.

3) **Integrate `libstb-hal`.**
   - Pick the correct flavour repo via `FLAVOUR` (default: `tuxbox`).
   - Add the new boxmodel in `library-stb-hal/acinclude.m4`:
     - Extend the `--with-boxmodel` list.
     - Add `AM_CONDITIONAL(BOXMODEL_<NAME>, ...)`.
     - Add `AC_DEFINE(BOXMODEL_<NAME>, 1, [...])`.
   - Add hardware caps in the backend:
     - `libarmbox/hardware_caps.c` for ARM
     - `libmipsbox/hardware_caps.c` for MIPS
     - Fill in `caps` fields (vendor/name/arch, display, HDMI/CI, PIP, etc.).
   - Adjust backend code in `libarmbox/` or `libmipsbox/` if device nodes or
     IOCTLs differ for the new SoC/driver stack.

4) **Build and test.**
   - `bitbake libstb-hal -c compile` (fast check)
   - `bitbake neutrino` and `bitbake tuxbox-image`
   - Test on hardware: audio/video, demux, PIP, frontpanel, HDMI-CEC, standby.

5) **Upstream contributions.**
   - Send `libstb-hal` changes to the selected upstream repo first.
   - For machine/kernel/bootloader changes, update the OE-A layer first, then
     update the submodule pointer in this repo.

## Verification Checklist

- `configure` accepts your `--with-boxtype` and `--with-boxmodel`
- `libstb-hal` builds and installs headers into `STAGING_INCDIR/libstb-hal`
- Neutrino links and starts
- `caps` values match the real hardware (display, HDMI, CI, PIP)
- Image boots and basic device functions work

## Contributing Upstream

New hardware enablement is split across upstreams:

- **libstb-hal**: add boxmodel + backend adjustments in the chosen repo.
- **OE-Alliance meta-brands**: add machine config, kernel/bootloader, DTBs.
- **This repo**: update submodule pointers after upstream changes are merged.
