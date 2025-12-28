SUMMARY = "Coolstream HD1 Linux kernel 2.6.34.15"
DESCRIPTION = "Coolstream kernel for nevis-based boxes"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=d7810fab7487fb0aad327b76f1be7cd7"

# Branch pinned in tuxbox-neutrino/linux-kernel-cst
SRC_URI = "git://github.com/tuxbox-neutrino/linux-kernel-cst.git;protocol=https;branch=${PV}-cnxt \
           file://kernel-nevis.defconfig"

SRCREV = "5a714bd8440e62f6a367d0fe569fe4ae9a21912e"

S = "${WORKDIR}/git"

inherit kernel

COMPATIBLE_MACHINE = "coolstream-nevis"
PACKAGE_ARCH = "${MACHINE_ARCH}"

KERNEL_IMAGETYPE ?= "uImage"

do_configure() {
    install -d ${B}
    oe_runmake -C ${S} O=${B} mrproper
    cp ${WORKDIR}/kernel-nevis.defconfig ${B}/.config
    oe_runmake -C ${S} O=${B} olddefconfig
}

do_compile() {
    unset LDFLAGS
    oe_runmake -C ${S} O=${B} ${KERNEL_IMAGETYPE}
    oe_runmake -C ${S} O=${B} modules
}

do_install() {
    install -d ${D}/boot
    install -m 0644 ${B}/${KERNEL_OUTPUT_DIR}/${KERNEL_IMAGETYPE} ${D}/boot/${KERNEL_IMAGETYPE}
    install -d ${D}/lib/modules/${KERNEL_VERSION}
    oe_runmake -C ${S} O=${B} INSTALL_MOD_PATH=${D} modules_install
}

FILES:${KERNEL_PACKAGE_NAME}-image = "/boot/${KERNEL_IMAGETYPE}"
