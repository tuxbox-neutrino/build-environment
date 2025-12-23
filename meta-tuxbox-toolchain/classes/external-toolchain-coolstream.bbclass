# BBClass for Coolstream external toolchain integration
#
# Sets up environment for cross-compilation with external uClibc toolchain

# Toolchain location (staged into native sysroot by the recipe)
EXTERNAL_TOOLCHAIN_ROOT ?= "${STAGING_DIR_NATIVE}/usr/share/coolstream-toolchain/toolchain-coolstream-uclibc-armv7"
EXTERNAL_TOOLCHAIN_BIN = "${EXTERNAL_TOOLCHAIN_ROOT}/cross/arm-linux-3.10.93/bin"
EXTERNAL_TOOLCHAIN_SYSROOT = "${EXTERNAL_TOOLCHAIN_ROOT}/cross/arm-linux-3.10.93/arm-cortex-linux-uclibcgnueabi/sys-root"

# Cross-compiler prefix
TARGET_PREFIX = "arm-cortex-linux-uclibcgnueabi-"
CROSS_COMPILE:class-target = "${TARGET_PREFIX}"

# Set compiler variables
CC:class-target = "${CROSS_COMPILE}gcc ${TOOLCHAIN_OPTIONS}"
CXX:class-target = "${CROSS_COMPILE}g++ ${TOOLCHAIN_OPTIONS}"
CPP:class-target = "${CROSS_COMPILE}gcc -E ${TOOLCHAIN_OPTIONS}"
LD:class-target = "${CROSS_COMPILE}ld ${TOOLCHAIN_OPTIONS}"
AR:class-target = "${CROSS_COMPILE}ar"
AS:class-target = "${CROSS_COMPILE}as"
RANLIB:class-target = "${CROSS_COMPILE}ranlib"
STRIP:class-target = "${CROSS_COMPILE}strip"
OBJCOPY:class-target = "${CROSS_COMPILE}objcopy"
OBJDUMP:class-target = "${CROSS_COMPILE}objdump"
NM:class-target = "${CROSS_COMPILE}nm"

# Toolchain sysroot for compiler
# Note: Do NOT override STAGING_DIR_HOST - BitBake needs the normal recipe-sysroot
# for finding OE-built packages. The toolchain sysroot is provided via --sysroot.
TOOLCHAIN_OPTIONS = "--sysroot=${EXTERNAL_TOOLCHAIN_SYSROOT}"

# Ensure the native toolchain sysroot is staged for target recipes
DEPENDS:append:class-target = " external-toolchain-coolstream-native"

# Add the recipe sysroot so OE-built libs (e.g. zlib) are discoverable.
CPPFLAGS:append:class-target = " -I${RECIPE_SYSROOT}/usr/include"
CFLAGS:append:class-target = " -I${RECIPE_SYSROOT}/usr/include"
CXXFLAGS:append:class-target = " -I${RECIPE_SYSROOT}/usr/include"
LDFLAGS:append:class-target = " -L${RECIPE_SYSROOT}/lib -L${RECIPE_SYSROOT}/usr/lib \
    -Wl,-rpath-link,${RECIPE_SYSROOT}/lib -Wl,-rpath-link,${RECIPE_SYSROOT}/usr/lib"
# Ensure pkg-config can discover OE-built libraries from the recipe sysroot.
PKG_CONFIG_LIBDIR:append:class-target = ":${RECIPE_SYSROOT}/usr/lib/pkgconfig:${RECIPE_SYSROOT}/usr/share/pkgconfig"
PKG_CONFIG_PATH:append:class-target = ":${RECIPE_SYSROOT}/usr/lib/pkgconfig:${RECIPE_SYSROOT}/usr/share/pkgconfig"

# Export to environment
export CROSS_COMPILE
export CC
export CXX
export CPP
export LD
export AR
export AS
export RANLIB
export STRIP
export OBJCOPY
export OBJDUMP
export NM

# Force use of native libtoolize, not crossscripts version
# The libtool-cross crossscripts/libtoolize has hardcoded paths to the external
# toolchain sysroot which breaks autoreconf for autotools-based recipes
LIBTOOLIZE = "${STAGING_BINDIR_NATIVE}/libtoolize"
export LIBTOOLIZE

# Add toolchain bin to PATH
PATH:append:class-target = ":${EXTERNAL_TOOLCHAIN_BIN}"

# Ensure binutils from the external toolchain are used
STRIP:class-target   = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}strip"
OBJCOPY:class-target = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}objcopy"
OBJDUMP:class-target = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}objdump"
NM:class-target      = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}nm"
AR:class-target      = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}ar"
RANLIB:class-target  = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}ranlib"
STRINGS:class-target = "${EXTERNAL_TOOLCHAIN_BIN}/${TARGET_PREFIX}strings"

# The external toolchain recipe already stages the sysroot; no additional
# task dependencies are required here.

# Disable QA checks that fail with external toolchain
INSANE_SKIP:append = " ldflags textrel"
