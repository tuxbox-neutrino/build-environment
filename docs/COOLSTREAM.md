# Coolstream (uClibc) Builds

Coolstream HD2-Geräte benötigen eine uClibc-Toolchain. Wir kapseln das in
`meta-coolstream` (Maschinen/BSP) plus `meta-tuxbox-toolchain`
(TCMODE `external-coolstream`).

## Layer
- `meta-coolstream`: Maschinenbeschreibungen, Flash/Layout, BSP-Anpassungen.
  In `bblayers.conf` hinzufügen:
  ```
  BBLAYERS += "${TOPDIR}/../meta-coolstream"
  ```
- `meta-tuxbox-toolchain`: Externe uClibc-Toolchain.

## Toolchain
**URL**: https://sourceforge.net/projects/n4k/files/toolchains/  
**File**: `toolchain-coolstream-uclibc-armv7.tar.bz2`  
**SHA256**: `b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6`

Layout (gekürzt):
```
toolchain-coolstream-uclibc-armv7/
└── cross/arm-linux-3.10.93/
    ├── bin/arm-cortex-linux-uclibcgnueabi-gcc ...
    └── arm-cortex-linux-uclibcgnueabi/sys-root/...
```

## Build (Beispiel Tank)
```
# lokale/conf
MACHINE = "coolstream-tank"
MACHINEBUILD = "coolstream-tank"
TCMODE = "external-coolstream"
TCLIBC = "uclibc"

# Layer hinzufügen (bblayers.conf)
BBLAYERS += "${TOPDIR}/../meta-coolstream"

# Bauen
bitbake tuxbox-image
```

## Hinweise
- DISTRO bleibt `tuxbox`; libc/TCMODE für Coolstream-Maschinen explizit setzen.
- Kernel/Bootloader/Driver müssen noch aus dem ni-buildsystem migriert werden.
- HD1/Nevis-Geräte (arm1176, glibc) laufen weiter über glibc-Toolchain;
  uClibc gilt für HD2 (apollo/shiner/kronos/kronos_v2: tank, trinity, zee2,
  link, trinity duo).

### Distribution Config

**File**: `meta-tuxbox-toolchain/conf/distro/tuxbox-uclibc.conf`

```bitbake
# Inherit base Tuxbox config
require conf/distro/tuxbox.conf

# Override C library
TCLIBC = "uclibc"
TCMODE = "external-coolstream"

# Toolchain-specific settings
DISTRO_NAME = "Tuxbox-OS uClibc"
DISTRO_VERSION_append = "-uclibc"

# Disable packages incompatible with uClibc
PACKAGECONFIG_remove_pn-systemd = "resolved"  # Example
```

### External Toolchain Class

**File**: `meta-tuxbox-toolchain/classes/external-toolchain-coolstream.bbclass`

```bitbake
# Toolchain binary path
EXTERNAL_TOOLCHAIN = "${WORKDIR}/toolchain-coolstream-uclibc-armv7"
EXTERNAL_TOOLCHAIN_BIN = "${EXTERNAL_TOOLCHAIN}/cross/arm-linux-3.10.93/bin"

# Cross-compiler settings
TARGET_PREFIX = "arm-cortex-linux-uclibcgnueabi-"
CROSS_COMPILE = "${TARGET_PREFIX}"

# Sysroot
EXTERNAL_TOOLCHAIN_SYSROOT = "${EXTERNAL_TOOLCHAIN}/cross/arm-linux-3.10.93/arm-cortex-linux-uclibcgnueabi/sys-root"

# Skip native toolchain recipes
ASSUME_PROVIDED += "gcc-cross-${TARGET_ARCH}"
ASSUME_PROVIDED += "binutils-cross-${TARGET_ARCH}"
ASSUME_PROVIDED += "uclibc"

# Export environment
export PATH_prepend = "${EXTERNAL_TOOLCHAIN_BIN}:"
export CROSS_COMPILE
```

### External Toolchain Recipe

**File**: `meta-tuxbox-toolchain/recipes-core/external-toolchain/external-toolchain-coolstream.bb`

```bitbake
DESCRIPTION = "External uClibc toolchain for Coolstream Tank"
LICENSE = "GPL-2.0 & LGPL-2.1"

SRC_URI = "https://sourceforge.net/projects/n4k/files/toolchains/toolchain-coolstream-uclibc-armv7.tar.bz2"
SRC_URI[sha256sum] = "b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6"

S = "${WORKDIR}"

do_install() {
    install -d ${D}${datadir}/coolstream-toolchain
    cp -r ${S}/toolchain-coolstream-uclibc-armv7 ${D}${datadir}/coolstream-toolchain/
}

FILES_${PN} = "${datadir}/coolstream-toolchain"

INHIBIT_DEFAULT_DEPS = "1"
```

## Coolstream Machine Configuration

### Machine Config

**File**: `meta-tuxbox-toolchain/conf/machine/tank.conf`

```bitbake
#@TYPE: Machine
#@NAME: Coolstream Tank
#@DESCRIPTION: Machine configuration for Coolstream Tank (ARM Cortex-A9, uClibc)

require conf/machine/include/coolstream-common.inc

MACHINE_FEATURES = "wifi bluetooth usbhost hdmi dvb-s dvb-s2 ci"

# Kernel
PREFERRED_PROVIDER_virtual/kernel = "linux-coolstream"
PREFERRED_VERSION_linux-coolstream = "3.10.93"

# Bootloader
PREFERRED_PROVIDER_virtual/bootloader = "u-boot-coolstream"

# Architecture
TARGET_ARCH = "arm"
DEFAULTTUNE = "armv7ahf-neon"

# Image
MACHINE_ESSENTIAL_EXTRA_RDEPENDS = "kernel-modules"
MACHINE_EXTRA_RDEPENDS = "firmware-coolstream"

# Display
MACHINE_LCD_DISPLAY = "textlcd"

# Flash layout
FLASHSIZE = "128"  # MB
KERNEL_DEVICETREE = "coolstream-tank.dtb"
```

## Image Customization

### Coolstream-Specific Package Group

**File**: `meta-tuxbox-toolchain/recipes-core/packagegroups/packagegroup-coolstream.bb`

```bitbake
DESCRIPTION = "Coolstream Tank specific packages"
LICENSE = "MIT"

inherit packagegroup

RDEPENDS_${PN} = " \
    firmware-coolstream \
    kernel-module-coolstream-dvb \
    coolstream-drivers \
    libstb-hal-coolstream \
"

# Optional
RRECOMMENDS_${PN} = " \
    coolstream-tools \
"
```

### Coolstream Image

**File**: `meta-tuxbox-toolchain/recipes-distros/tuxbox/image/tuxbox-image-coolstream.bb`

```bitbake
require recipes-distros/tuxbox/image/tuxbox-image.inc

DESCRIPTION = "Tuxbox-OS image for Coolstream Tank (uClibc)"

# Add Coolstream-specific packages
IMAGE_INSTALL_append = " \
    packagegroup-coolstream \
"

# Remove packages incompatible with uClibc
IMAGE_INSTALL_remove = " \
    systemd-resolved \
"
```

## Build Workflow

### 1. Full Build

```bash
# Initialize (if not done)
./cli.py init

# Build Coolstream image
./cli.py build --machine tank --distro tuxbox-uclibc

# Or with Makefile
make image MACHINE=tank DISTRO=tuxbox-uclibc
```

**Build time**: 3-5 hours (first build with toolchain download)

### 2. Incremental Build

```bash
# Rebuild after changes
./cli.py build --machine tank --distro tuxbox-uclibc

# Clean and rebuild
./cli.py clean --machine tank
./cli.py build --machine tank --distro tuxbox-uclibc
```

### 3. Development Workflow

```bash
# Drop to devshell
./cli.py build --machine tank --distro tuxbox-uclibc --devshell

# Inside devshell, you have access to:
# - Cross-compiler: $CC, $CXX, $LD
# - Sysroot: $STAGING_DIR_TARGET
# - Build tools

# Compile individual package
bitbake neutrino -c compile -f
```

## Troubleshooting

### Toolchain Download Fails

**Symptom**: SHA256 checksum mismatch or download timeout

**Solution 1**: Manual download
```bash
cd downloads/
wget https://sourceforge.net/projects/n4k/files/toolchains/toolchain-coolstream-uclibc-armv7.tar.bz2
sha256sum toolchain-coolstream-uclibc-armv7.tar.bz2
# Verify: b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6
```

**Solution 2**: Alternative mirror
```bash
# Edit meta-tuxbox-toolchain/recipes-core/external-toolchain/external-toolchain-coolstream.bb
# Add alternative SRC_URI mirror
```

### Compiler Not Found

**Symptom**: `arm-cortex-linux-uclibcgnueabi-gcc: command not found`

**Check**:
```bash
ls downloads/toolchain-coolstream-uclibc-armv7/cross/arm-linux-3.10.93/bin/
```

**Solution**:
```bash
# Re-extract toolchain
bitbake external-toolchain-coolstream -c clean
bitbake external-toolchain-coolstream
```

### Library Compatibility Issues

**Symptom**: `error: undefined reference to __stack_chk_fail_local`

**Cause**: Mixing glibc and uClibc binaries

**Solution**: Ensure clean build
```bash
make distclean
make init
make image MACHINE=tank DISTRO=tuxbox-uclibc
```

### Kernel/Driver Issues

**Symptom**: Kernel module mismatch or driver loading fails

**Check kernel version**:
```bash
bitbake virtual/kernel -e | grep ^PV=
# Should be 3.10.93 for Coolstream
```

**Solution**:
```bash
# Force kernel rebuild
bitbake linux-coolstream -c cleansstate
bitbake linux-coolstream
```

## Advanced Topics

### Custom Toolchain

If using a different uClibc toolchain:

1. **Create new recipe**:
   ```bash
   cp meta-tuxbox-toolchain/recipes-core/external-toolchain/external-toolchain-coolstream.bb \
      meta-tuxbox-toolchain/recipes-core/external-toolchain/external-toolchain-custom.bb
   ```

2. **Update SRC_URI and checksum**

3. **Update paths** in recipe and class

4. **Set TCMODE** in distro config:
   ```
   TCMODE = "external-custom"
   ```

### Toolchain Debugging

Enable verbose logging:
```bash
# In local.conf
BB_LOGCONFIG = "bitbake-logger.conf"
VERBOSE = "1"

# Rebuild
bitbake tuxbox-image -f
```

Check compiler flags:
```bash
bitbake neutrino -e | grep ^CC=
bitbake neutrino -e | grep ^CFLAGS=
bitbake neutrino -e | grep ^LDFLAGS=
```

### Migrating from ni-buildsystem

If you have Coolstream-specific recipes from the old ni-buildsystem:

1. **Copy recipes** to `meta-tuxbox-toolchain/recipes-*/`

2. **Update syntax** for Kirkstone compatibility:
   ```bash
   # Run Yocto migration scripts
   poky/scripts/convert-overrides.py meta-tuxbox-toolchain/
   ```

3. **Fix dependencies**:
   - Check `DEPENDS` and `RDEPENDS`
   - Ensure uClibc compatibility

4. **Test build**:
   ```bash
   bitbake <package-name>
   ```

## Testing

### QEMU Testing

**Note**: Coolstream Tank is real hardware, no QEMU support.

For smoke testing, use:
```bash
# Test on HD51 or other QEMU-supported machine first
make image MACHINE=hd51

# Then build for Tank
make image MACHINE=tank DISTRO=tuxbox-uclibc
```

### Hardware Testing

1. **Build image**
2. **Extract to USB stick** (FAT32)
3. **Flash via bootloader** or recovery mode
4. **Check boot log** via serial console
5. **Verify Neutrino starts**

## References

- **Coolstream Wiki**: https://wiki.coolstream.info/
- **n4k Project**: https://sourceforge.net/projects/n4k/
- **uClibc**: https://www.uclibc.org/
- **Yocto External Toolchain**: https://docs.yoctoproject.org/dev-manual/external-toolchain.html

---

**Need help?** Ask on Tuxbox forum or open an issue.
