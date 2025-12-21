SUMMARY = "Coolstream third-party USB/WLAN drivers (CLOSED)"
DESCRIPTION = "Extra binary modules/config for Coolstream (e.g. Ralink rt5572sta for nevis)."
LICENSE = "CLOSED"
LIC_FILES_CHKSUM = ""

SRC_URI = "git://github.com/tuxbox-neutrino/drivers-third-party-cst.git;protocol=https;branch=master"
SRCREV = "4151410e2d6f886f6bea64ea5ad7181aefff7c45"

S = "${WORKDIR}/git"

INHIBIT_DEFAULT_DEPS = "1"

PACKAGE_ARCH = "${MACHINE_ARCH}"
COMPATIBLE_MACHINE = "coolstream-nevis"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    # rt5572sta module (built for 2.6.34.13-nevis)
    if [ -f ${S}/USB/network/Ralink/rt5572sta/lib/modules/2.6.34.13-nevis/rt5572sta.ko ]; then
        install -d ${D}/lib/modules/2.6.34.13-nevis/extra
        install -m 0644 ${S}/USB/network/Ralink/rt5572sta/lib/modules/2.6.34.13-nevis/rt5572sta.ko \
            ${D}/lib/modules/2.6.34.13-nevis/extra/
    fi

    # Config
    if [ -f ${S}/USB/network/Ralink/rt5572sta/etc/Wireless/RT2870STA/RT2870STA.dat ]; then
        install -d ${D}/etc/Wireless/RT2870STA
        install -m 0644 ${S}/USB/network/Ralink/rt5572sta/etc/Wireless/RT2870STA/RT2870STA.dat \
            ${D}/etc/Wireless/RT2870STA/RT2870STA.dat
    fi
}

FILES:${PN} = "/lib/modules /etc/Wireless"
RDEPENDS:${PN} += "cst-drivers"
