# meta-tuxbox-toolchain

Yocto/OpenEmbedded layer for external toolchain support in Tuxbox-OS.

## Description

This layer provides support for external toolchains, specifically the Coolstream uClibc toolchain for Coolstream Tank set-top-boxes.

## Purpose

Coolstream devices require **uClibc** instead of the standard **glibc**, which necessitates a separate toolchain and build configuration. This layer provides:

- External toolchain integration (uClibc-based)
- Coolstream machine configurations
- uClibc-specific distribution settings
- Hardware-specific packages and drivers

## Layer Dependencies

- **meta** (openembedded-core)
- **meta-tuxbox** (Tuxbox distribution layer)

## Layer Compatibility

- **Yocto Release**: Kirkstone (4.0 LTS)
- **Layer Series**: kirkstone

## Contents

### Distribution Configuration
- `conf/distro/tuxbox-uclibc.conf` - uClibc-based distribution
- `conf/distro/include/coolstream-external-toolchain.inc` - Toolchain settings

### Machine Configurations
- `conf/machine/tank.conf` - Coolstream Tank machine
- `conf/machine/include/coolstream-common.inc` - Common Coolstream settings

### External Toolchain
- `recipes-core/external-toolchain/external-toolchain-coolstream.bb` - Toolchain recipe
- `classes/external-toolchain-coolstream.bbclass` - Toolchain integration class

### Package Groups
- `packagegroup-coolstream` - Coolstream hardware support

### Images
- `tuxbox-image-coolstream.bb` - Coolstream-optimized image

## Toolchain Details

**Source**: https://sourceforge.net/projects/n4k/files/toolchains/
**File**: `toolchain-coolstream-uclibc-armv7.tar.bz2`
**SHA256**: `b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6`

**Compiler**: GCC with uClibc
**Target**: ARM Cortex-A9
**Prefix**: `arm-cortex-linux-uclibcgnueabi-`

## Usage

### Add Layer

Add to `bblayers.conf`:

```
BBLAYERS += "/path/to/meta-tuxbox-toolchain"
```

### Build for Coolstream Tank

Set machine and distro in `local.conf`:

```
MACHINE = "tank"
DISTRO = "tuxbox-uclibc"
```

Or use environment variables:

```bash
MACHINE=tank DISTRO=tuxbox-uclibc bitbake tuxbox-image-coolstream
```

### Using Makefile

```bash
make image MACHINE=tank DISTRO=tuxbox-uclibc
```

### Using Python CLI

```bash
./cli.py build --machine tank --distro tuxbox-uclibc
```

## Build Process

1. **Toolchain Download**: First build downloads and extracts toolchain (~100MB)
2. **Toolchain Setup**: Sets up cross-compilation environment
3. **Image Build**: Builds Neutrino image with uClibc

**First build**: ~3-5 hours
**Incremental**: ~30-60 minutes

## Extending

### Adding New Coolstream Machines

1. Create machine config in `conf/machine/<machine>.conf`
2. Include common settings: `require conf/machine/include/coolstream-common.inc`
3. Define machine-specific features

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
