# meta-tuxbox-toolchain

Yocto/OpenEmbedded layer for external toolchain support in Tuxbox-OS.

## Description

This layer provides support for external toolchains, specifically the Coolstream
uClibc toolchain for Coolstream HD2 devices.

## Purpose

Coolstream HD2 devices require **uClibc** instead of the standard **glibc**,
which necessitates a separate toolchain and build configuration. This layer
provides:

- External toolchain integration (uClibc-based)
- uClibc-specific distribution settings

Machine configurations, kernels, drivers, and image composition live in
`meta-coolstream`.

## Layer Dependencies

- **meta** (openembedded-core)
- **meta-tuxbox** (Tuxbox distribution layer)
- **meta-coolstream** (Coolstream machine definitions)

## Layer Compatibility

- **Yocto Release**: Kirkstone (4.0 LTS)
- **Layer Series**: kirkstone

## Contents

### Distribution Configuration
- `conf/distro/tuxbox-uclibc.conf` - uClibc-based distribution
- Toolchain defaults used by Coolstream machines

### External Toolchain
- `recipes-core/external-toolchain/external-toolchain-coolstream.bb` - Toolchain recipe
- `classes/external-toolchain-coolstream.bbclass` - Toolchain integration class

## Toolchain Details

**Source**: https://sourceforge.net/projects/n4k/files/toolchains/
**File**: `toolchain-coolstream-uclibc-armv7.tar.bz2`
**SHA256**: `c3017d17ce442fce4fcb3cf9c77d574617bd8db1f8ea741b0d2960c2b2acdeab`

**Compiler**: GCC with uClibc
**Target**: ARM Cortex-A9
**Prefix**: `arm-cortex-linux-uclibcgnueabi-`

## Notes

- uClibc builds use the `proxy-libintl` stub library for `virtual/libintl`.
- Architecture QA checks are skipped for uClibc builds because
  `linux-uclibcgnueabi` is not recognized by the upstream ELF map.

## Usage

### Add Layer

Add to `bblayers.conf`:

```
BBLAYERS += "/path/to/meta-tuxbox-toolchain"
```

### Build for Coolstream (HD2) devices

Set machine and distro in `local.conf`:

```
MACHINE = "coolstream-tank"
MACHINEBUILD = "coolstream-tank"
DISTRO = "tuxbox"
```

Or use environment variables:

```bash
MACHINE=coolstream-tank MACHINEBUILD=coolstream-tank DISTRO=tuxbox bitbake tuxbox-image
```

### Using Makefile

```bash
make image MACHINE=coolstream-tank MACHINEBUILD=coolstream-tank DISTRO=tuxbox
```

### Using Python CLI

```bash
./cli.py build --machine coolstream-tank --distro tuxbox
```

## Build Process

1. **Toolchain Download**: First build downloads and extracts toolchain
2. **Toolchain Setup**: Sets up cross-compilation environment
3. **Image Build**: Builds Tuxbox image with uClibc

**First build**: ~3-5 hours
**Incremental**: ~30-60 minutes

## Extending

### Adding New Coolstream Machines

Machine configurations belong in `meta-coolstream/conf/machine/`. This layer
only provides the external toolchain integration.

### Adding Custom Firmware

Place firmware recipes in `recipes-bsp/firmware/`

### Custom Drivers

Place driver recipes in `recipes-bsp/drivers/`

## Troubleshooting

See [COOLSTREAM.md](../docs/COOLSTREAM.md) in main documentation.

## License

MIT License (for layer infrastructure)

Individual recipes may have different licenses.

## Maintainer

Tuxbox Neutrino Team
