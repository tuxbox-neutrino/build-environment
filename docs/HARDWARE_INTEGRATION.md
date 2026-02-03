# Hardware Integration Guide (Neutrino + libstb-hal)

This document explains how hardware support is wired up and why not every
OE-Alliance machine is ready for Neutrino out of the box.

## Contents

- [Reality Check](#reality-check)
- [Quick Glossary](#quick-glossary)
- [Where Hardware Support Lives](#where-hardware-support-lives)
- [OE-Alliance References](#oe-alliance-references)
- [libstb-hal Selection and Boxmodel Mapping](#libstb-hal-selection-and-boxmodel-mapping)
- [Integration Flow (Decision)](#integration-flow-decision)
- [MACHINE vs MACHINEBUILD](#machine-vs-machinebuild)
- [Existing Machine in meta-brands: Integration Steps](#existing-machine-in-meta-brands-integration-steps)
- [Hardware Caps: Where to Find Them](#hardware-caps-where-to-find-them)
- [Reducing BOXMODEL Branches in Neutrino](#reducing-boxmodel-branches-in-neutrino)
- [Example: Add a New Boxmodel](#example-add-a-new-boxmodel)
- [Workflow: Add a New Machine](#workflow-add-a-new-machine)
- [Verification Checklist](#verification-checklist)
- [Contributing Upstream](#contributing-upstream)

## Reality Check

- OE-Alliance provides 300+ machine definitions in `meta-brands`.
- The build system can parse/build many of them, but we only test a subset.
- Neutrino requires `libstb-hal` support. If a machine is not in the supported
  `boxmodel` list, builds or runtime behavior will break.
- Adding support is possible and welcome, but it is real bring-up work.
- For real integration you need hardware access (serial/SSH and a working
  kernel/DTB). Without a box, you can only do a best-effort build.

## Quick Glossary

- `MACHINE`: the OE-Alliance machine name you pass to the build.
- `MACHINEBUILD`: optional OEM variant for the same base machine.
- `boxtype`: coarse family (`generic`, `armbox`, `mipsbox`).
- `boxmodel`: the exact string libstb-hal expects for a box (often = `MACHINE`).
- `libstb-hal`: hardware abstraction layer used by Neutrino.

## Where Hardware Support Lives

- **Machine definitions**:
  `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`
- **Kernel/DTB/bootloader**:
  `oe-alliance/meta-brands/meta-<brand>/recipes-*`
- **Distro and images**:
  `meta-tuxbox` (image/packagegroups, distro config)
- **Neutrino and hardware abstraction**:
  `meta-neutrino` (Neutrino, `libstb-hal`)

## OE-Alliance References

OE-Alliance keeps a public inventory of machine names and vendors. It is a
useful starting point, but not a guarantee that Neutrino integration exists.

- Local (if submodule is checked out): `oe-alliance/README.md`
- Upstream: `https://github.com/oe-alliance/oe-alliance-core/blob/master/README.md`

## libstb-hal Selection and Boxmodel Mapping

`meta-tuxbox/conf/distro/tuxbox.conf` sets `FLAVOUR` (default: `tuxbox`). The
`libstb-hal` recipe includes `${FLAVOUR}.inc`, which selects the upstream repo:

- `tuxbox.inc` -> `tuxbox-neutrino/library-stb-hal`
- `ni.inc` -> `neutrino-images/ni-libstb-hal`
- `tango.inc` -> `TangoCash/libstb-hal-tangos`

Note: These forks are not guaranteed to be compatible with each other. This
guide focuses on `library-stb-hal` (tuxbox flavour). The community shares
knowledge across forks, but implementation style and commit practices can
diverge, so apply changes in the fork you actually build against.

The build passes:

- `--with-boxtype=${TARGET_ARCH}box`
- `--with-boxmodel=${MACHINE}`

Neutrino itself uses the same flags (see
`meta-neutrino/recipes-neutrino/neutrino/*.inc`). Ensure both recipes agree. If
machine naming differs, override `EXTRA_OECONF` via a bbappend.

Valid boxtype values are `generic`, `armbox`, `mipsbox`. Boxtype is a broad
hardware family, boxmodel is the exact per-device string. The `boxmodel` list is
defined in `library-stb-hal/acinclude.m4` (and similar in the other flavours).

Current boxmodels (library-stb-hal):

- generic: `generic`, `raspi`
- armbox: `hd60`, `hd61`, `multibox`, `multiboxse`, `hd51`, `bre2ze4k`, `h7`,
  `e4hdultra`, `protek4k`, `osmini4k`, `osmio4k`, `osmio4kplus`, `vusolo4k`,
  `vuduo4k`, `vuduo4kse`, `vuultimo4k`, `vuuno4k`, `vuuno4kse`, `vuzero4k`
- mipsbox: `vuduo`, `vuduo2`, `gb800se`, `osnino`, `osninoplus`, `osninopro`

If your machine name is not in this list, `configure` will fail and Neutrino
cannot run. You must add the boxmodel and hardware caps (or map `MACHINE` to an
existing boxmodel via bbappend).

## Integration Flow (Decision)

```
Start
  |
  +-- Is MACHINE already in meta-brands? -- yes --> Existing machine steps
  |                                       no  --> Add new machine steps
```

Integration map (existing meta-brands machine):

```
OE-A machine.conf -> MACHINE -> libstb-hal configure -> hardware_caps -> Neutrino
        |                |             |                    |            |
        |                |             |                    |            └─ uses libstb-hal headers/libs
        |                |             |                    └─ model-specific caps
        |                |             └─ --with-boxtype/--with-boxmodel
        |                └─ name must match a known boxmodel (or override)
        └─ kernel/DTB/drivers already exist
```

## MACHINE vs MACHINEBUILD

- `MACHINE` selects the base hardware config:
  `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`.
- `MACHINEBUILD` selects an OEM or variant for the same base machine.
  It often toggles tuners, frontpanel, branding, partitions, or image layout.
- Some OE-A layers add `MACHINEOVERRIDES` based on `MACHINEBUILD`, which lets
  recipes override settings per OEM variant.
- If a machine has no OEM variants, `MACHINEBUILD` can be omitted (or equals
  `MACHINE`).

How to find valid `MACHINEBUILD` values:

- Inspect the machine file and its includes for `MACHINEBUILD` usage or
  `MACHINEOVERRIDES`.
- In many OE-A layers, OEM variants are defined in
  `conf/machine/include/*-oem.inc` or `*oem*.inc` files.
- Quick search:

```bash
rg -n "MACHINEBUILD" oe-alliance/meta-brands/meta-<brand>/conf/machine -S
```

When integrating `libstb-hal`:

- `MACHINE`/boxmodel is the key input. `MACHINEBUILD` does **not** map to
  boxmodel automatically.
- If an OEM variant needs different caps, add a new boxmodel and map to it via
  bbappend overrides.

## Existing Machine in meta-brands: Integration Steps

If a box already exists in `oe-alliance/meta-brands`, you can skip the machine
definition work and focus on Neutrino integration:

1) **Confirm the MACHINE name.**
   - Use `make list-machines` and `make machine-info MACHINE=<name>`.
   - If OEM variants exist, set `MACHINEBUILD` accordingly.
   - The machine name must match a libstb-hal boxmodel or be mapped.

2) **Align boxtype/boxmodel between libstb-hal and Neutrino.**
   - Neutrino uses `--with-boxtype=${TARGET_ARCH}box` and
     `--with-boxmodel=${MACHINE}`.
   - If `TARGET_ARCH` yields an unsupported boxtype (e.g. `aarch64box`,
     `mipselbox`), override to `armbox` or `mipsbox` as appropriate.
   - Prefer bbappends in `meta-tuxbox` so overrides live in the distro layer.

Example overrides:

```bitbake
# meta-tuxbox/recipes-neutrino/libstb-hal/libstb-hal_git.bbappend
EXTRA_OECONF:append = " --with-boxtype=armbox --with-boxmodel=<boxmodel>"

# meta-tuxbox/recipes-neutrino/neutrino/neutrino_git.bbappend
EXTRA_OECONF:append = " --with-boxtype=armbox --with-boxmodel=<boxmodel>"
```

3) **Make libstb-hal accept the machine.**
   - Add the boxmodel to `library-stb-hal/acinclude.m4`.
   - Add caps in `libarmbox/` or `libmipsbox/` (see sections below).
   - Adjust backend code in `libarmbox/` or `libmipsbox/` if device nodes or
     IOCTLs differ for the new SoC/driver stack.

4) **Build and smoke-test on hardware.**
   - `bitbake libstb-hal -c compile`
   - `bitbake neutrino`
   - `bitbake tuxbox-image`
   - Validate `/proc/stb/info/*`, video/audio, demux, frontpanel, standby.

## Hardware Caps: Where to Find Them

`libstb-hal` exposes hardware capabilities via `hw_caps_t`:

- Struct definition: `library-stb-hal/include/hardware_caps.h`
- ARM caps: `library-stb-hal/libarmbox/hardware_caps.c`
- MIPS caps: `library-stb-hal/libmipsbox/hardware_caps.c`
- Generic/PC: `library-stb-hal/libgeneric-pc/hardware_caps.c`
- Raspberry Pi: `library-stb-hal/libraspi/hardware_caps.c`

Common fields to set:

- `has_CI`, `has_HDMI`, `has_SCART`, `can_cec`, `can_shutdown`
- `display_type`, `display_xres`, `display_yres`, display flags
- `boxmodel`, `boxvendor`, `boxname`, `boxarch`

Where to get values:

- `/proc/stb/info/*` for boxtype/model info
- Machine docs or OEM datasheets (display resolution, CI slots, HDMI)
- Existing similar models in `hardware_caps.c` (same SoC/brand)
- Device nodes (`/dev/dvb/*`, `/dev/fb*`) and frontpanel drivers

Tip for newcomers: start from a known similar model and then verify the values
on real hardware. Wrong caps can hide features or trigger wrong code paths.

## Reducing BOXMODEL Branches in Neutrino

libstb-hal was designed to isolate hardware specifics so Neutrino can stay
mostly free of `#if BOXMODEL_*` and `HAVE_*_HARDWARE` branches. In practice,
some compile-time checks still exist in Neutrino and drivers (for device node
paths, display types, PIP gating, and frontpanel behavior). This makes new
hardware bring-up require Neutrino patches and creates behavior differences
based on build-time flags instead of runtime caps.

Target state: keep boxmodel knowledge inside libstb-hal, and make Neutrino rely
on `g_info.hw_caps` or HAL helper APIs. If you need a new box-specific rule,
extend `hw_caps_t` or add a small HAL accessor, then replace `#if BOXMODEL_*`
with a runtime check.

Practical migration steps:

1) Identify `#if BOXMODEL_*` blocks in Neutrino (core + `src/driver/`).
2) Decide which capability or device detail is missing in `hw_caps_t`.
3) Add that field in `hardware_caps.h` and set it per boxmodel in
   `libarmbox/` or `libmipsbox/`.
4) Replace the compile-time branch with a runtime check (caps or helper).
5) Keep compile-time branching only for true boxtype backends, not UI logic.

If you are new, you can postpone this refactor and just add missing caps first.

## Example: Add a New Boxmodel

Example: `gb800solo` (MIPS) is defined in OE-A, but not in `libstb-hal`.
Use `gb800se` as a starting point and adjust to real hardware values.

1) Add the boxmodel to `library-stb-hal/acinclude.m4`:

```m4
AS_HELP_STRING([], [valid for mipsbox: vuduo, vuduo2, gb800se, gb800solo, osnino, osninoplus, osninopro]),
...
AM_CONDITIONAL(BOXMODEL_GB800SOLO, test "$BOXMODEL" = "gb800solo")
...
elif test "$BOXMODEL" = "gb800solo"; then
    AC_DEFINE(BOXMODEL_GB800SOLO, 1, [gb800solo])
```

2) Add hardware caps in `library-stb-hal/libmipsbox/hardware_caps.c`:

```c
#if BOXMODEL_GB800SOLO
    caps.has_CI = 1; /* verify */
    caps.can_cec = 0; /* verify */
    caps.can_shutdown = 1;
    caps.display_type = HW_DISPLAY_LINE_TEXT; /* or LED, verify */
    caps.display_xres = 16;
    caps.display_can_deepstandby = 1;
    caps.display_can_set_brightness = 1;
    caps.has_HDMI = 1;
    caps.has_SCART = 1; /* verify */
    strcpy(caps.startup_file, "");
    strcpy(caps.boxmodel, "gb800solo");
    strcpy(caps.boxvendor, "GigaBlue");
    strcpy(caps.boxname, "GB800 SOLO");
    strcpy(caps.boxarch, "BCM7325"); /* verify */
#endif
```

3) Build and test:

```bash
bitbake libstb-hal -c compile
bitbake neutrino
bitbake tuxbox-image
```

If it boots, validate HDMI, audio, demux, PIP, frontpanel, and standby.

## Workflow: Add a New Machine

If a machine is missing in `meta-brands`, add it there first and then follow
"Existing Machine in meta-brands: Integration Steps":

1) Add `oe-alliance/meta-brands/meta-<brand>/conf/machine/<machine>.conf`.
2) Set `SOC_FAMILY`, `TUNE_FEATURES`, `KERNEL_IMAGETYPE`, `KERNEL_DEVICETREE`,
   `IMAGE_FSTYPES`, `SERIAL_CONSOLE`, `MACHINE_FEATURES`.
3) Add or update `linux-<brand>_<ver>.bb` and defconfig/DTB in the same layer.
4) Verify kernel/driver bring-up (`/dev/dvb/*`, `/proc/stb/info/*`).
5) Continue with the integration steps above.

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
