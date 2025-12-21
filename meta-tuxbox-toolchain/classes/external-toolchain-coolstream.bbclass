# BBClass for Coolstream external toolchain integration
#
# Sets up environment for cross-compilation with external uClibc toolchain

# Toolchain location (staged into native sysroot by the recipe)
EXTERNAL_TOOLCHAIN_ROOT ?= "${STAGING_DIR_NATIVE}${datadir}/coolstream-toolchain/toolchain-coolstream-uclibc-armv7"
EXTERNAL_TOOLCHAIN_BIN = "${EXTERNAL_TOOLCHAIN_ROOT}/cross/arm-linux-3.10.93/bin"
EXTERNAL_TOOLCHAIN_SYSROOT = "${EXTERNAL_TOOLCHAIN_ROOT}/cross/arm-linux-3.10.93/arm-cortex-linux-uclibcgnueabi/sys-root"

# Cross-compiler prefix
TARGET_PREFIX = "arm-cortex-linux-uclibcgnueabi-"
CROSS_COMPILE = "${TARGET_PREFIX}"

# Set compiler variables
CC = "${CROSS_COMPILE}gcc ${TOOLCHAIN_OPTIONS}"
CXX = "${CROSS_COMPILE}g++ ${TOOLCHAIN_OPTIONS}"
CPP = "${CROSS_COMPILE}gcc -E ${TOOLCHAIN_OPTIONS}"
LD = "${CROSS_COMPILE}ld ${TOOLCHAIN_OPTIONS}"
AR = "${CROSS_COMPILE}ar"
AS = "${CROSS_COMPILE}as"
RANLIB = "${CROSS_COMPILE}ranlib"
STRIP = "${CROSS_COMPILE}strip"
OBJCOPY = "${CROSS_COMPILE}objcopy"
OBJDUMP = "${CROSS_COMPILE}objdump"
NM = "${CROSS_COMPILE}nm"

# Sysroot
STAGING_DIR_HOST = "${EXTERNAL_TOOLCHAIN_SYSROOT}"
STAGING_DIR_TARGET = "${EXTERNAL_TOOLCHAIN_SYSROOT}"

# Toolchain options
TOOLCHAIN_OPTIONS = "--sysroot=${EXTERNAL_TOOLCHAIN_SYSROOT}"

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

# Add toolchain bin to PATH
export PATH := "${EXTERNAL_TOOLCHAIN_BIN}:${PATH}"

# The external toolchain recipe already stages the sysroot; no additional
# task dependencies are required here.

# Disable QA checks that fail with external toolchain
INSANE_SKIP:append = " ldflags textrel"
