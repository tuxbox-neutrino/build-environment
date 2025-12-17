# Coolstream External Toolchain Configuration

# Toolchain mode
TCMODE = "external-coolstream"

# Toolchain paths (will be set by external-toolchain recipe)
EXTERNAL_TOOLCHAIN ?= "${TMPDIR}/work-shared/external-toolchain"

# Target prefix
TARGET_PREFIX = "arm-cortex-linux-uclibcgnueabi-"

# Skip native toolchain recipes
ASSUME_PROVIDED += " \
    gcc-cross-${TARGET_ARCH} \
    binutils-cross-${TARGET_ARCH} \
    uclibc \
    virtual/${TARGET_PREFIX}gcc \
    virtual/${TARGET_PREFIX}g++ \
    virtual/${TARGET_PREFIX}gcc-initial \
    virtual/${TARGET_PREFIX}binutils \
    virtual/${TARGET_PREFIX}libc-for-gcc \
    virtual/${TARGET_PREFIX}compilerlibs \
"

# Toolchain features
TOOLCHAIN_FEATURES = "toolchain-uClibc"
