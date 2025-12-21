SUMMARY = "Coolstream binary drivers and firmware"
DESCRIPTION = "Prebuilt kernel modules and firmware for Coolstream boxes (CLOSED source)."
LICENSE = "CLOSED"
LIC_FILES_CHKSUM = ""

SRC_URI = "git://github.com/tuxbox-neutrino/drivers-bin-cst.git;protocol=https;branch=master"
SRCREV = "146403d83abf7bf996845f14da22142081994e65"

S = "${WORKDIR}/git"

INHIBIT_DEFAULT_DEPS = "1"

PACKAGES = "${PN} ${PN}-firmware"
FILES:${PN} = "/lib/modules"
FILES:${PN}-firmware = "/lib/firmware"
RRECOMMENDS:${PN} += "${PN}-firmware"

PACKAGE_ARCH = "${MACHINE_ARCH}"
COMPATIBLE_MACHINE = "(coolstream-nevis|coolstream-apollo|coolstream-shiner|coolstream-kronos|coolstream-kronos-v2)"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

python __anonymous() {
    m = d.getVar("MACHINE") or ""
    if m in ("coolstream-apollo", "coolstream-shiner"):
        d.setVar("CST_SUBDIR", "apollo-3.x")
        d.setVar("CST_MODDIR", "3.10.93")
    elif m in ("coolstream-kronos", "coolstream-kronos-v2"):
        d.setVar("CST_SUBDIR", "kronos-3.x")
        d.setVar("CST_MODDIR", "3.10.93")
    elif m == "coolstream-nevis":
        d.setVar("CST_SUBDIR", "nevis")
        d.setVar("CST_MODDIR", "2.6.34.13-nevis")
    else:
        bb.fatal("Unsupported MACHINE for cst-drivers: %s" % m)
}

do_install() {
    # Kernel modules
    if [ -d ${S}/${CST_SUBDIR}/drivers/${CST_MODDIR} ]; then
        install -d ${D}/lib/modules/${CST_MODDIR}
        cp -a ${S}/${CST_SUBDIR}/drivers/${CST_MODDIR}/* ${D}/lib/modules/${CST_MODDIR}/
    fi

    # Firmware
    if [ -d ${S}/${CST_SUBDIR}/firmware ]; then
        install -d ${D}/lib/firmware
        cp -a ${S}/${CST_SUBDIR}/firmware/* ${D}/lib/firmware/
    fi
}
