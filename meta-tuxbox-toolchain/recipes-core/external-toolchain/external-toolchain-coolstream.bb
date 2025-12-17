# External uClibc toolchain for Coolstream devices
#
# Downloads and extracts the pre-built Coolstream toolchain

DESCRIPTION = "External uClibc toolchain for Coolstream Tank"
LICENSE = "GPL-2.0-only & LGPL-2.1-only"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-2.0-only;md5=801f80980d171dd6425610833a22dbe6 \
                    file://${COMMON_LICENSE_DIR}/LGPL-2.1-only;md5=1a6d268fd218675ffea8be556788b780"

# Toolchain source
TOOLCHAIN_URL = "https://sourceforge.net/projects/n4k/files/toolchains"
TOOLCHAIN_FILE = "toolchain-coolstream-uclibc-armv7.tar.bz2"

SRC_URI = "${TOOLCHAIN_URL}/${TOOLCHAIN_FILE};name=toolchain"
SRC_URI[toolchain.sha256sum] = "b7f18dfa5ad9ba607595ebdda13bc66cfe3f35f5151ab1f93cde89dc2b0b52e6"

# Alternative mirror (SourceForge backup)
SRC_URI += "https://downloads.sourceforge.net/project/n4k/toolchains/${TOOLCHAIN_FILE};name=toolchain"

S = "${WORKDIR}"

# No compilation needed
do_compile[noexec] = "1"

do_install() {
    # Install toolchain to shared work directory
    install -d ${D}${datadir}/coolstream-toolchain

    # Copy entire toolchain
    cp -a ${S}/toolchain-coolstream-uclibc-armv7 ${D}${datadir}/coolstream-toolchain/

    # Create version file
    echo "Coolstream uClibc Toolchain" > ${D}${datadir}/coolstream-toolchain/version
    echo "GCC: $(${S}/toolchain-coolstream-uclibc-armv7/cross/arm-linux-3.10.93/bin/arm-cortex-linux-uclibcgnueabi-gcc --version | head -1)" >> ${D}${datadir}/coolstream-toolchain/version || true
}

# Package files
FILES:${PN} = "${datadir}/coolstream-toolchain"

# Don't try to strip binaries from external toolchain
INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"
INHIBIT_SYSROOT_STRIP = "1"

# No default dependencies
INHIBIT_DEFAULT_DEPS = "1"

# Don't check for already-stripped binaries
INSANE_SKIP:${PN} = "already-stripped staticdev ldflags"

# Architecture-independent
PACKAGE_ARCH = "all"
