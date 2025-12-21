SUMMARY = "Coolstream HD1 Linux kernel 2.6.34.15"
DESCRIPTION = "Coolstream kernel for nevis-based boxes"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=d7810fab7487fb0aad327b76f1be7cd7"

PV = "2.6.34.15"

# Branch to be created/pinned in tuxbox-neutrino/linux-kernel-cst
SRC_URI = "git://github.com/tuxbox-neutrino/linux-kernel-cst.git;protocol=https;branch=2.6.34.15-cnxt \
           file://kernel-nevis.defconfig"

# Placeholder SRCREV: update to the actual commit after branch push
SRCREV = "946a1153cdf14b00476427b56487e0aac4321e77"

S = "${WORKDIR}/git"

inherit kernel

COMPATIBLE_MACHINE = "coolstream-nevis"
PACKAGE_ARCH = "${MACHINE_ARCH}"

KERNEL_IMAGETYPE ?= "uImage"

do_configure() {
    oe_runmake mrproper
    cp ${WORKDIR}/kernel-nevis.defconfig ${S}/.config
    oe_runmake olddefconfig
}

do_compile() {
    unset LDFLAGS
    oe_runmake ${KERNEL_IMAGETYPE}
    oe_runmake modules
}

do_install() {
    install -d ${D}/boot
    install -m 0644 ${KERNEL_OUTPUT} ${D}/boot/${KERNEL_IMAGETYPE}
    install -d ${D}/lib/modules/${KERNEL_VERSION}
    oe_runmake INSTALL_MOD_PATH=${D} modules_install
}

FILES:${KERNEL_PACKAGE_NAME}-image = "/boot/${KERNEL_IMAGETYPE}"
