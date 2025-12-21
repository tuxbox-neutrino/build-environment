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
    linux-libc-headers \
    virtual/${TARGET_PREFIX}linux-libc-headers \
    gcc-runtime \
    libssp-nonshared \
    nativesdk-gcc-runtime \
    nativesdk-libgcc \
    nativesdk-glibc \
    nativesdk-linux-libc-headers \
    gcc-cross-canadian-${TRANSLATED_TARGET_ARCH} \
    binutils-cross-canadian-${TRANSLATED_TARGET_ARCH} \
    gcc-crosssdk-${SDK_SYS} \
    binutils-crosssdk-${SDK_SYS} \
"

# Toolchain features
TOOLCHAIN_FEATURES = "toolchain-uClibc"

# Prefer the external toolchain for all compiler/libc virtuals
PREFERRED_PROVIDER_virtual/${TARGET_PREFIX}binutils = "external-toolchain-coolstream"
PREFERRED_PROVIDER_virtual/${TARGET_PREFIX}gcc = "external-toolchain-coolstream"
PREFERRED_PROVIDER_virtual/${TARGET_PREFIX}g++ = "external-toolchain-coolstream"
PREFERRED_PROVIDER_virtual/${TARGET_PREFIX}compilerlibs = "external-toolchain-coolstream"
PREFERRED_PROVIDER_virtual/${TARGET_PREFIX}linux-libc-headers = "external-toolchain-coolstream"
PREFERRED_PROVIDER_virtual/libc = "external-toolchain-coolstream"
PREFERRED_PROVIDER_linux-libc-headers = "external-toolchain-coolstream"
