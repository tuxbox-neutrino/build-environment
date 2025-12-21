SUMMARY = "Coolstream HD2 Linux kernel 3.10.93"
DESCRIPTION = "Coolstream kernel for apollo/shiner/kronos/kronos_v2"
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=d7810fab7487fb0aad327b76f1be7cd7"

PV = "3.10.93"

SRC_URI = "git://github.com/tuxbox-neutrino/linux-kernel-cst.git;protocol=https;branch=cst_3.10.93"
SRC_URI:append:coolstream-apollo = " file://kernel-apollo.defconfig"
SRC_URI:append:coolstream-shiner = " file://kernel-apollo.defconfig"
SRC_URI:append:coolstream-kronos = " file://kernel-kronos.defconfig"
SRC_URI:append:coolstream-kronos-v2 = " file://kernel-kronos.defconfig"

SRCREV = "c439541d636ab4126270d416418629b8fdddf08e"

S = "${WORKDIR}/git"

inherit kernel

COMPATIBLE_MACHINE = "(coolstream-apollo|coolstream-shiner|coolstream-kronos|coolstream-kronos-v2)"
PACKAGE_ARCH = "${MACHINE_ARCH}"

KERNEL_IMAGETYPE ?= "uImage"

python __anonymous() {
    m = d.getVar("MACHINE") or ""
    if m in ("coolstream-apollo", "coolstream-shiner"):
        d.setVar("CST_DEFCONFIG", "kernel-apollo.defconfig")
    elif m in ("coolstream-kronos", "coolstream-kronos-v2"):
        d.setVar("CST_DEFCONFIG", "kernel-kronos.defconfig")
    else:
        bb.fatal("Unsupported MACHINE for linux-coolstream 3.10.93: %s" % m)
}

do_configure() {
    oe_runmake mrproper
    cp ${WORKDIR}/${CST_DEFCONFIG} ${S}/.config
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
